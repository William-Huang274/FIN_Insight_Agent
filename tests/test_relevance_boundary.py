from hashlib import sha256
import pytest
from retrieval.relevance_boundary import fit,validate,partition


PIPELINE={'model':'test-reranker','policy':'test.v1','index_digest':'f'*64}


def reviewed(prefix,count=120):
    return [{'query_sha256':sha256(f'{prefix} q{i%12}'.encode()).hexdigest(),
        'content_sha256':sha256(f'{prefix} body{i}'.encode()).hexdigest(),
        'source_document_sha256':sha256(f'{prefix} doc{i%12}'.encode()).hexdigest(),
        'score':.9 if i<100 else .3,'grade':3 if i<100 else 0,
        'review_reason':'Explicit fixture label, not a research evaluation.'} for i in range(count)]


def calibration():
    return fit(reviewed('train'),pipeline=PIPELINE,minimum_precision=.9,minimum_results=40,minimum_questions=8)


def test_maximum_supported_coverage_and_exact_threshold_ties():
    fitted=calibration()
    assert fitted['fit']['threshold']==.9 and fitted['fit']['accepted']==100
    assert fitted['independent_validation'] is None
    # Mixed correct/incorrect items with the same score cannot be separated
    # by their source, gold label, company or ordering in the review file.
    rows=reviewed('ties')
    for row in rows:row['score']=.9
    with pytest.raises(ValueError,match='no_supported_boundary'):
        fit(rows,pipeline=PIPELINE,minimum_precision=.9,minimum_results=40,minimum_questions=8)


def test_high_wrong_scores_cannot_be_hidden_by_threshold_selection():
    rows=reviewed('bad')
    for row in rows:row['score']=.8 if row['grade'] else .99
    with pytest.raises(ValueError,match='no_supported_boundary'):
        fit(rows,pipeline=PIPELINE,minimum_precision=.9,minimum_results=40,minimum_questions=8)


def test_judgment_completeness_consistency_and_repeat_counting():
    rows=reviewed('train');fitted=calibration()
    assert fit(rows+rows,pipeline=PIPELINE,minimum_precision=.9,minimum_results=40,
               minimum_questions=8)==fitted
    with pytest.raises(ValueError,match='conflicting_pair'):
        fit(rows+[{**rows[0],'grade':0}],pipeline=PIPELINE,minimum_precision=.9,
            minimum_results=40,minimum_questions=8)
    for key,value in [('grade',None),('review_reason',''),('score',float('nan')),('score',True)]:
        with pytest.raises(ValueError,match='complete_review'):
            fit([{**rows[0],key:value}],pipeline=PIPELINE,minimum_precision=.9,
                minimum_results=40,minimum_questions=8)


def test_independent_review_requires_new_sources_and_new_questions():
    fitted=calibration()
    for rows in (reviewed('train'),[{**r,'source_document_sha256':reviewed('train')[i]['source_document_sha256']}
                                  for i,r in enumerate(reviewed('holdout'))]):
        with pytest.raises(ValueError,match='disjoint'):
            validate(fitted,rows,pipeline=PIPELINE)
    result=validate(fitted,reviewed('holdout'),pipeline=PIPELINE)
    assert result['status']=='passed' and result['precision']==1 and result['pooled_recall']==1


def test_insufficient_results_remain_short_without_padding_and_order_is_preserved():
    fitted=calibration();evidence=validate(fitted,reviewed('holdout'),pipeline=PIPELINE)
    rows=[{'node_id':n} for n in ['a','b','c']]
    selected,receipt=partition(rows,{'a':.91,'b':.2,'c':.97},fitted,pipeline=PIPELINE,validation=evidence,limit=10)
    assert selected==[rows[0],rows[2]]
    assert receipt['uncertain_candidate_ids']==['b']
    assert receipt['result_state']=='fewer_supported_candidates_than_requested'
    assert receipt['unknown_or_absent_disclosure'] is False
    assert 'fixed_k' in receipt['precision_denominator']


def test_failed_validation_or_pipeline_drift_cannot_enable_boundary():
    fitted=calibration();bad=[{**r,'grade':0} for r in reviewed('badholdout')]
    evidence=validate(fitted,bad,pipeline=PIPELINE)
    assert evidence['status']=='failed'
    with pytest.raises(ValueError,match='independent_validation'):
        partition([],{},fitted,pipeline=PIPELINE,validation=evidence,limit=10)
    good=validate(fitted,reviewed('holdout'),pipeline=PIPELINE)
    with pytest.raises(ValueError,match='independent_validation'):
        partition([],{},fitted,pipeline={**PIPELINE,'model':'other'},validation=good,limit=10)
    changed={**fitted,'fit':{**fitted['fit'],'threshold':.1}}
    with pytest.raises(ValueError,match='independent_validation'):
        partition([],{},changed,pipeline=PIPELINE,validation=good,limit=10)
