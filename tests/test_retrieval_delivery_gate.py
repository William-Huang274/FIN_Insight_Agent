from copy import deepcopy

from scripts.engineering.retrieval_delivery_gate import evaluate,score,SLICES
from scripts.engineering.retrieval_delivery_gate import source_cluster_interval
from scripts.engineering.retrieval_evaluation_freeze import DEFAULT_STRATEGY, policy_digest


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
    policy=dict(DEFAULT_STRATEGY)
    dataset={'questions':questions,'evaluation_role':'independent_source_first','index_digest':'a'*64,
             'index_file_sha256':'b'*64,'policy':policy,
             'freeze':{'status':'frozen','prior_results_exposed':False,'ranking_policy':dict(policy),
                       'ranking_policy_sha256':policy_digest(policy)}}
    report={'samples':samples,'status':'completed','dataset_sha256':'dataset',
            'index_digest':'a'*64,'index_file_sha256':'b'*64,'ranking_policy_sha256':policy_digest(policy)}
    return dataset,report


def test_complete_synthetic_contract_passes_quality_only():
    dataset,report=fixture()
    result=evaluate(dataset,report,dataset_digest='dataset')
    assert result['quality_gate_passed'] and not result['S2_passed']
    assert result['metrics']['recall10']['family_macro']==1
    assert result['negative_correct']==20


def test_policy_digest_cannot_be_an_arbitrary_matching_report_label():
    dataset,report=fixture()
    dataset['freeze']['ranking_policy_sha256']=report['ranking_policy_sha256']='same-but-not-a-policy-digest'
    assert 'invalid_dataset_or_strategy_freeze' in evaluate(dataset,report,dataset_digest='dataset')['failures']


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


def test_source_correlation_joins_families_transitively_without_changing_macro():
    rows = [{'family': 'one', 'source_groups': ['a'], 'score': 0.},
            {'family': 'one', 'source_groups': ['a'], 'score': 1.},
            {'family': 'two', 'source_groups': ['a', 'b'], 'score': 1.},
            {'family': 'three', 'source_groups': ['b'], 'score': 0.}]
    result = source_cluster_interval(rows, 'score')
    assert result == {'clusters': 1, 'interval': [.5, .5]}


def test_development_exposure_does_not_invalidate_an_unseen_heldout_set():
    dataset, report = fixture()
    dataset['freeze'].update(prior_results_exposed=True, heldout_prior_results_exposed=False,
                             development_prior_results_exposed=True)
    result = evaluate(dataset, report, dataset_digest='dataset')
    assert result['quality_gate_passed']
    assert result['metrics']['recall10']['source_connected_clusters'] == 40
