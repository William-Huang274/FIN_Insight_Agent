from copy import deepcopy
import pytest
from scripts.engineering.summarize_reviewed_span_evaluation import summarize


def fixture():
    questions = [{'id':str(i), 'family':str(i), 'language':'en', 'question_kind':kind,
                  'reviewed_spans':[{}]} for i,kind in enumerate(
                      ['positive_fact_request','false_premise_corrective_evidence'])]
    dataset = {'evaluation_role':'independent_source_first','questions':questions,
               'freeze':{'status':'frozen','heldout_prior_results_exposed':False,
                         'acceptance':{'positive_complete_evidence_at10':.9,
                                       'counterclaim_corrective_evidence_at10':.9,'known_group_recall_at10':.95}}}
    metric = {'complete':True,'group_recall':1.,'groups':[True]}
    report = {'status':'completed','plan_sha256':'p','samples':[
        {'id':q['id'],'span_metrics':{'selected':deepcopy(metric)},
         'metrics':{'selected':{'complete':False}}} for q in questions]}
    return dataset,report,{'dataset_sha256':'d'}


def run(d,r,p):
    return summarize(d,r,p,dataset_sha256='d',plan_sha256='p')


def test_overlapping_cover_pass_is_separate_from_exact_ids_and_delivery():
    d,r,p=fixture();result=run(d,r,p)
    assert result['batch_quality_passed'] and not result['S2_passed']
    assert not result['rows'][0]['strict_minimum_cover_complete10']


def test_missing_or_failed_execution_cannot_shrink_denominator():
    d,r,p=fixture();r['samples'].pop()
    result=run(d,r,p)
    assert not result['batch_quality_passed'] and result['expected']==2
    assert result['by_kind']['false_premise_corrective_evidence']['family_macro_complete10']==0
    d,r,p=fixture();r['status']='failed'
    assert not run(d,r,p)['batch_quality_passed']


def test_duplicate_results_and_altered_label_digest_rejected():
    d,r,p=fixture();r['samples'].append(deepcopy(r['samples'][0]))
    with pytest.raises(ValueError,match='duplicate'):run(d,r,p)
    d,r,p=fixture();p['dataset_sha256']='changed'
    with pytest.raises(ValueError,match='identity'):run(d,r,p)


def test_exposed_labels_or_inconsistent_metric_cannot_pass():
    d,r,p=fixture();d['freeze']['heldout_prior_results_exposed']=True
    with pytest.raises(ValueError,match='unexposed'):run(d,r,p)
    d,r,p=fixture();r['samples'][0]['span_metrics']['selected']['groups']=[False]
    with pytest.raises(ValueError,match='inconsistent'):run(d,r,p)


def test_known_label_defect_blocks_pass_even_when_numeric_thresholds_pass():
    d,r,p=fixture()
    r['label_review_errors']=[{'reason':'repeated header selected preceding statement','family':'0'}]
    result=run(d,r,p)
    assert not result['batch_quality_passed']
    assert result['by_kind']['positive_fact_request']['complete10']==1
    assert result['label_review_errors']==r['label_review_errors']


def test_nonfinite_metrics_and_unscored_question_types_are_rejected():
    d,r,p=fixture();r['samples'][0]['span_metrics']['selected']['group_recall']=float('nan')
    with pytest.raises(ValueError,match='inconsistent'):run(d,r,p)
    d,r,p=fixture();d['questions'][0]['question_kind']='unscored'
    with pytest.raises(ValueError,match='unsupported_question_kind'):run(d,r,p)
