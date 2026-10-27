import pytest

from scripts.engineering.retrieval_evaluation_freeze import policy_digest, validate_heldout_freeze


def frozen():
    policy = {'candidate_policy': 'dense_expanded.v1', 'query_planning': 'conservative.v1',
              'metadata_policy': 'sec_cover.v2', 'reranker': 'qwen3-rerank', 'returned_limit': 20}
    return {'evaluation_role': 'independent_source_first', 'index_digest': 'a'*64,
            'index_file_sha256': 'b'*64, 'policy': dict(policy),
            'freeze': {'status': 'frozen', 'heldout_prior_results_exposed': False,
                       'development_prior_results_exposed': True, 'ranking_policy': policy,
                       'ranking_policy_sha256': policy_digest(policy)}}


def test_heldout_policy_is_checked_before_embeddings_or_candidates():
    data = frozen()
    validate_heldout_freeze(data, 'heldout')
    validate_heldout_freeze(data, 'heldout', candidate_policy='dense_expanded.v1',
                            query_planning='conservative.v1', metadata_policy='sec_cover.v2', check_runtime=True)
    with pytest.raises(ValueError, match='runtime_policy_mismatch'):
        validate_heldout_freeze(data, 'heldout', candidate_policy='balanced.v1', check_runtime=True)
    with pytest.raises(ValueError, match='manual_source_routing'):
        validate_heldout_freeze(data, 'heldout', manual_plan=True)


@pytest.mark.parametrize('change,error', [
    (lambda d: d['freeze'].update(status='authoring'), 'frozen_dataset'),
    (lambda d: d['freeze'].update(heldout_prior_results_exposed=True), 'independence'),
    (lambda d: d['freeze'].pop('ranking_policy'), 'explicit_ranking_policy'),
    (lambda d: d['freeze']['ranking_policy'].update(reranker='different'), 'policy_digest'),
    (lambda d: d.update(index_digest='not-a-digest'), 'index_digest'),
    (lambda d: d.pop('index_file_sha256'), 'index_digest'),
    (lambda d: d['policy'].update(candidate_policy='balanced.v1'), 'differs_from_freeze'),
])
def test_incomplete_or_changed_freeze_cannot_expose_holdout(change, error):
    data = frozen(); change(data)
    with pytest.raises(ValueError, match=error):
        validate_heldout_freeze(data, 'heldout')


def test_development_and_historical_diagnostics_remain_available():
    validate_heldout_freeze({'evaluation_role': 'independent_source_first'}, 'development')
    validate_heldout_freeze({'evaluation_role': 'historical_regression'}, 'heldout')


@pytest.mark.parametrize('policy',['needs_window.v2','needs_window.v3'])
def test_source_window_strategy_must_be_explicitly_frozen_and_match_runtime(policy):
    data=frozen()
    data['policy']['candidate_policy']=policy
    data['freeze']['ranking_policy']=dict(data['policy'])
    data['freeze']['ranking_policy_sha256']=policy_digest(data['policy'])
    validate_heldout_freeze(data,'heldout',candidate_policy=policy,
        query_planning='conservative.v1',metadata_policy='sec_cover.v2',check_runtime=True)
    with pytest.raises(ValueError,match='runtime_policy_mismatch'):
        validate_heldout_freeze(data,'heldout',candidate_policy='needs_balanced.v1',
            query_planning='conservative.v1',metadata_policy='sec_cover.v2',check_runtime=True)
    data['freeze']['ranking_policy']['candidate_policy']='needs_window.v999'
    data['policy']=dict(data['freeze']['ranking_policy'])
    data['freeze']['ranking_policy_sha256']=policy_digest(data['policy'])
    with pytest.raises(ValueError,match='unsupported_frozen'):
        validate_heldout_freeze(data,'heldout')


def test_new_reranker_is_frozen_and_cannot_be_changed_without_new_digest():
    data=frozen()
    data['policy']['reranker']='qwen3.7-text-rerank'
    data['freeze']['ranking_policy']=dict(data['policy'])
    data['freeze']['ranking_policy_sha256']=policy_digest(data['policy'])
    validate_heldout_freeze(data,'heldout')
    data['freeze']['ranking_policy']['reranker']='qwen3-rerank'
    with pytest.raises(ValueError,match='policy_digest'):
        validate_heldout_freeze(data,'heldout')
