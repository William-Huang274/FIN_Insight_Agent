from copy import deepcopy

from scripts.engineering.retrieval_delivery_gate import evaluate,score,SLICES


def fixture():
    questions=[];samples=[]
    for i in range(60):
        for language in ('en','zh'):
            q={'id':f'q{i}-{language}','family':f'f{i}','split':'development' if i<20 else 'heldout',
               'language':language,'topic':SLICES[i%6],'business_entities':[f'company{i%20}'],
               'source_groups':[f'source{i}'],'label_review':{'status':'reviewed'},'expected_groups':[[f'n{i}']]}
            questions.append(q)
            if i>=20:samples.append({'id':q['id'],'status':'completed','unauthorized_items':0,
                'invalid_identity_items':0,'gold_groups':q['expected_groups'],
                'rankings':{'candidate_union':[f'n{i}'],'returned':[f'n{i}']}})
    for i in range(20):
        questions.append({'id':f'absent{i}','family':f'absent{i}','split':'heldout','answerability':'absent_in_frozen_scope',
                          'scope_review':{'status':'reviewed'}})
        samples.append({'id':f'absent{i}','status':'completed','unauthorized_items':0,
                        'invalid_identity_items':0,'decision':'insufficient_evidence'})
    dataset={'questions':questions,'evaluation_role':'independent_source_first','index_digest':'index',
             'freeze':{'status':'frozen','prior_results_exposed':False,'ranking_policy_sha256':'policy'}}
    report={'samples':samples,'status':'completed','dataset_sha256':'dataset',
            'index_digest':'index','ranking_policy_sha256':'policy'}
    return dataset,report


def test_complete_synthetic_contract_passes_quality_only():
    dataset,report=fixture()
    result=evaluate(dataset,report,dataset_digest='dataset')
    assert result['quality_gate_passed'] and not result['S2_passed']
    assert result['metrics']['recall10']['family_macro']==1
    assert result['negative_correct']==20


def test_missing_or_failed_samples_never_disappear_from_denominator():
    dataset,report=fixture()
    report['samples'].pop(0)
    report['samples'][0]['status']='failed'
    result=evaluate(dataset,report,dataset_digest='dataset')
    assert not result['quality_gate_passed']
    assert result['metrics']['recall10']['family_macro']==39/40
    assert len(result['samples'])==80


def test_returned_and_candidate_recall_and_required_units_are_different():
    m=score(['a','b'],['a'],[['a','equivalent-a'],['b']])
    assert m=={'candidate_recall48':1.,'recall10':.5,'mrr10':1.,'all_required10':0.}


def test_small_exposed_dataset_and_cross_split_sources_fail_even_with_perfect_scores():
    dataset,report=fixture()
    dataset['questions'][40]['source_groups']=['source0']
    dataset['freeze']['prior_results_exposed']=True
    result=evaluate(dataset,report,dataset_digest='dataset')
    assert not result['quality_gate_passed']
    assert 'equivalent_source_crosses_split' in result['failures']
    assert 'independent_status_unconfirmed' in result['failures']


def test_result_cannot_replace_labels_policy_or_forget_permission_checks():
    dataset,report=fixture()
    report['samples'][0]['gold_groups']=[['different']]
    report['samples'][1].pop('unauthorized_items')
    report['ranking_policy_sha256']='changed'
    result=evaluate(dataset,report,dataset_digest='dataset')
    assert {'result_labels_differ_from_frozen_labels','authorization_not_verified_clean',
            'frozen_ranking_policy_mismatch'}<=set(result['failures'])


def test_bad_language_slice_does_not_hide_behind_pooled_score():
    dataset,report=fixture()
    for sample in report['samples']:
        if sample['id'].endswith('-zh'):sample['rankings']['returned']=[]
    result=evaluate(dataset,report,dataset_digest='dataset')
    assert 'slice_below_target_zh' in result['failures']
    assert result['slices']['en']['recall10']==1
