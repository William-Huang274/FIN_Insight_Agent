"""Fail closed before exposing a held-out retrieval set to an experiment."""
from hashlib import sha256
import json

LEGACY_POLICY = {'dense_candidates':24,'lexical_candidates':12,'graph_candidates':12,
                 'fusion':'rrf_k60','returned_limit':20}
DEFAULT_STRATEGY = {'candidate_policy':'balanced.v1','query_planning':None,
                    'metadata_policy':'original.v1','reranker':None,'returned_limit':20}


def strategy_from_policy(policy=None):
    if policy is None or policy == LEGACY_POLICY:
        return dict(DEFAULT_STRATEGY)
    if (not isinstance(policy,dict) or set(policy)!=set(DEFAULT_STRATEGY)
        or policy['candidate_policy'] not in {'balanced.v1','dense_expanded.v1','needs_balanced.v1'}
        or policy['query_planning'] not in {None,'conservative.v1','conservative.v2','conservative.v3','conservative.v4','conservative.v5'}
        or policy['metadata_policy'] not in {'original.v1','sec_cover.v2'}
        or policy['reranker'] not in {None,'qwen3-rerank','qwen3.7-text-rerank'}
        or type(policy['returned_limit']) is not int or policy['returned_limit']!=20):
        raise ValueError('unsupported_frozen_retrieval_strategy')
    return dict(policy)


def policy_digest(policy):
    return sha256(json.dumps(policy, sort_keys=True, separators=(',', ':'),
                             ensure_ascii=False).encode()).hexdigest()


def validate_heldout_freeze(dataset, split, *, candidate_policy=None,
                            query_planning=None, metadata_policy='original.v1',
                            check_runtime=False, manual_plan=False):
    if split != 'heldout' or dataset.get('evaluation_role') == 'historical_regression':
        return
    freeze = dataset.get('freeze', {})
    if freeze.get('status') != 'frozen':
        raise ValueError('heldout_requires_frozen_dataset_and_policy')
    # Development results are supposed to be examined. Only unseen held-out
    # results are required; do not mislabel a tuned development set as unseen.
    if freeze.get('heldout_prior_results_exposed', freeze.get('prior_results_exposed')) is not False:
        raise ValueError('heldout_independence_unconfirmed')
    policy = freeze.get('ranking_policy')
    if not isinstance(policy, dict) or not policy:
        raise ValueError('heldout_explicit_ranking_policy_required')
    if policy_digest(policy) != freeze.get('ranking_policy_sha256'):
        raise ValueError('heldout_ranking_policy_digest_mismatch')
    strategy_from_policy(policy)
    if dataset.get('policy') != policy:
        raise ValueError('heldout_dataset_policy_differs_from_freeze')
    for field in ('index_digest','index_file_sha256'):
        digest = dataset.get(field, '')
        if len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
            raise ValueError('heldout_exact_index_digest_required')
    if manual_plan:
        raise ValueError('heldout_manual_source_routing_forbidden')
    if check_runtime and (policy.get('candidate_policy') != candidate_policy
                          or policy.get('query_planning') != query_planning
                          or policy.get('metadata_policy') != metadata_policy):
        raise ValueError('heldout_runtime_policy_mismatch')
