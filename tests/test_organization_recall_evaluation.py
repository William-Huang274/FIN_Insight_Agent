from copy import deepcopy
from hashlib import sha256
from types import SimpleNamespace

import pytest

from scripts.engineering.organization_recall_evaluation import (
    POLICY, bind_labels, evaluate, evidence_group_metrics, score_response, summarize,
    validate_questions, verify_equivalent_quote,
)
from sec_agent.research_foundation.organization_source_navigation import OrganizationSourceNavigation
from sec_agent.research_foundation.organization_source_projection import chunk_node_id


@pytest.fixture
def fixture():
    body = 'Alpha invested USD 2 billion in Beta; the deal completed in March.'
    digest = sha256(body.encode()).hexdigest()
    bundle = {'library_sha256': 'snapshot', 'source': {'id': 'source', 'vintage': 'dated_original',
        'published_at': '2026-03-01', 'metadata': '{}'},
        'chunks': [{'id': 'chunk', 'body': body, 'digest': digest}],
        'edges': [{'id': 'edge', 'subject': 'COMPANY::alpha', 'object': 'COMPANY::beta', 'status': 'completed'}],
        'edge_chunk_links': [{'edge_id': 'edge', 'chunk_id': 'chunk'}]}
    question = {'id': 'q1', 'family': 'f1', 'split': 'development', 'query': 'What did Alpha invest in Beta?',
        'as_of': '2026-09-23', 'entity_id': 'COMPANY::alpha', 'entity_alias': 'Alpha',
        'evidence': [{'source_id': 'source', 'chunk_id': 'chunk', 'body_sha256': digest,
                      'quote': 'USD 2 billion'}]}
    dataset = {'evaluation_role': 'independent_source_first', 'library_sha256': 'snapshot',
               'policy': dict(POLICY), 'questions': [question]}
    item = {'resource_id': 'resource', 'ref': {'version': 'v1'}}
    manifest = {'inputs': [item], 'research_as_of': '2026-09-23'}
    document = OrganizationSourceNavigation._identity(item)
    node = chunk_node_id(document, 'chunk') + ':leaf'
    index = {'records': [{'node_id': node, 'document_id': document, 'content_sha256': digest}]}
    return dataset, {'source': bundle}, manifest, index, node


def test_original_to_exact_publication_mapping(fixture):
    dataset, bundles, manifest, index, node = fixture
    rows = validate_questions(dataset, bundles)
    assert bind_labels(rows, manifest, {'source': 'resource'}, index) == {'q1': [node]}
    manifest['inputs'][0]['ref']['version'] = 'v2'
    with pytest.raises(ValueError, match='label_not_in_frozen_index'):
        bind_labels(rows, manifest, {'source': 'resource'}, index)


@pytest.mark.parametrize('defect,match', [
    ('quote', 'quote_not'), ('digest', 'digest_mismatch'), ('source', 'snapshot_mismatch'),
    ('cutoff', 'not_available'), ('entity', 'explicit_in_question'), ('edge', 'no_bound_source_edge'),
])
def test_rejects_bad_labels_before_search(fixture, defect, match):
    dataset, bundles, *_ = fixture
    row = dataset['questions'][0]
    if defect == 'quote': row['evidence'][0]['quote'] = 'USD 20 billion'
    if defect == 'digest': bundles['source']['chunks'][0]['body'] += ' changed'
    if defect == 'source': bundles['source']['library_sha256'] = 'other'
    if defect == 'cutoff': row['as_of'] = '2026-02-01'
    if defect == 'entity': row['entity_alias'] = 'NVIDIA'
    if defect == 'edge': row['entity_id'] = 'COMPANY::unrelated'
    with pytest.raises(ValueError, match=match): validate_questions(dataset, bundles)


def test_no_family_or_source_leakage_and_historical_role_is_explicit(fixture):
    dataset, bundles, *_ = fixture
    other = deepcopy(dataset['questions'][0]); other.update(id='q2', split='heldout')
    dataset['questions'].append(other)
    with pytest.raises(ValueError, match='family_crosses'): validate_questions(dataset, bundles)
    other['family'] = 'f2'
    with pytest.raises(ValueError, match='source_crosses'): validate_questions(dataset, bundles)
    dataset['evaluation_role'] = 'historical_regression'
    assert len(validate_questions(dataset, bundles)) == 2


def test_policy_is_frozen_before_independent_retrieval(fixture):
    dataset, bundles, *_ = fixture
    dataset['policy']['dense_candidates'] = 100
    with pytest.raises(ValueError, match='frozen_evaluation_policy_mismatch'):
        validate_questions(dataset, bundles)


def result(graph=False):
    receipt = {'index_digest': 'index',
        'mode': 'organization-cosine-bm25-graph-rrf.v1' if graph else 'organization-cosine-bm25-rrf.v1',
        'dense_node_ids': ['wrong', 'gold'],
        'lexical_node_ids': ['wrong'], 'candidate_node_ids': ['wrong', 'gold'], 'graph_node_ids': ['gold']}
    return SimpleNamespace(items=[{'node_id': 'wrong', 'retrieval': receipt}])


def test_candidate_hit_does_not_count_as_returned_hit():
    scored = score_response(result(graph=True), ['gold'], index_digest='index', graph=True)
    assert scored['metrics']['fused_candidates']['known_hit@5'] == 1
    assert scored['metrics']['returned']['known_hit@5'] == 0
    assert scored['metrics']['graph_candidates']['mrr@40'] == 1
    with pytest.raises(ValueError, match='index_mismatch'):
        score_response(result(), ['gold'], index_digest='other')


def test_duplicate_rank_and_unexplained_empty_are_errors():
    response = result(); response.items[0]['retrieval']['dense_node_ids'] = ['gold', 'gold']
    with pytest.raises(ValueError, match='duplicate_ranked'):
        score_response(response, ['gold'], index_digest='index')
    with pytest.raises(ValueError, match='execution_diagnosis'):
        score_response(SimpleNamespace(items=[]), ['gold'], index_digest='index')


def test_response_must_obey_frozen_policy_and_quotas():
    with pytest.raises(ValueError, match='response_policy_mismatch'):
        score_response(result(graph=True), ['gold'], index_digest='index')
    response = result(); response.items[0]['retrieval']['dense_node_ids'] = list(map(str, range(25)))
    with pytest.raises(ValueError, match='response_policy_quota_mismatch'):
        score_response(response, ['gold'], index_digest='index')


def test_expanded_reranking_strategy_is_verified_on_actual_response(fixture):
    strategy = {'candidate_policy': 'dense_expanded.v1', 'query_planning': 'conservative.v1',
                'metadata_policy':'sec_cover.v2', 'reranker': 'qwen3-rerank', 'returned_limit': 20}
    response = result()
    receipt = response.items[0]['retrieval']
    receipt.update(mode='organization-cosine-bm25-qwen-rerank.v1',
                   candidate_policy='dense_expanded.v1',
                   rerank_response={'model':'qwen3-rerank'}, reranked_node_ids=['gold','wrong'])
    response.organization_query_plan = {'policy':'conservative.v1','metadata_policy':'sec_cover.v2'}
    requests, saved = [], []
    class Navigation:
        def navigate(self, request):
            requests.append(request)
            return response
    rows = fixture[0]['questions']
    samples = evaluate(rows, {'q1':['gold']}, Navigation(), index_digest='index',
                       strategy=strategy, save=lambda name,data:saved.append(data))
    assert requests[0]['organization_query_planning'] == 'conservative.v1'
    assert requests[0]['organization_metadata_policy'] == 'sec_cover.v2'
    assert saved[0]['strategy'] == strategy
    assert samples[0]['metrics']['reranked_candidates']['mrr@40'] == 1
    assert samples[0]['metrics']['returned']['known_hit@10'] == 0
    for field, value, error in (
        ('candidate_policy','balanced.v1','candidate_policy_mismatch'),
        ('rerank_response',{'model':'other'},'rerank_model_mismatch'),
        ('reranked_node_ids',['gold'],'differ_from_union'),
    ):
        broken = deepcopy(response); broken.items[0]['retrieval'][field] = value
        with pytest.raises(ValueError, match=error):
            score_response(broken, ['gold'], index_digest='index', strategy=strategy)
    response.organization_query_plan = None
    with pytest.raises(ValueError, match='query_plan_mismatch'):
        score_response(response, ['gold'], index_digest='index', strategy=strategy)


def test_family_average_and_incomplete_runs():
    def sample(identity, family, score):
        return {'id': identity, 'family': family, 'status': 'completed', 'metrics': {'returned': {'hit': score}}}
    samples = [sample('a', 'one', 1), sample('b', 'one', 1), sample('c', 'two', 0)]
    summary = summarize(samples, ['a', 'b', 'c'])
    assert summary['metrics']['returned']['hit'] == {'question_mean': 2/3, 'family_mean': .5}
    assert summarize(samples, ['a', 'b', 'c', 'd'])['metrics'] is None
    samples.append({'id': 'd', 'status': 'failed'})
    assert summarize(samples, ['a', 'b', 'c', 'd'])['failed'] == 1
    assert summarize(samples, ['a', 'b', 'c', 'd'])['metrics'] is None


def test_failure_persisted_without_retry_or_document_prefilter(fixture):
    dataset, *_ = fixture
    calls, saved = [], []
    class Navigation:
        def navigate(self, request):
            calls.append(request)
            raise PermissionError('revoked')
    with pytest.raises(PermissionError):
        evaluate(dataset['questions'], {'q1': ['gold']}, Navigation(), index_digest='index',
                 save=lambda name, data: saved.append(data), graph=True)
    assert len(calls) == 1 and 'document_id' not in calls[0]
    assert calls[0]['entity_id'] == 'COMPANY::alpha' and calls[0]['limit'] == 20
    assert saved[0]['samples'][0]['status'] == 'failed'
    assert saved[0]['summary']['metrics'] is None


def test_equivalent_copies_count_once_but_other_required_fact_stays_missing():
    groups = [['old', 'new'], ['other-fact']]
    measured = evidence_group_metrics(['new', 'new', 'old'], groups)
    assert measured['known_recall@5'] == .5 and measured['all_known_hit@5'] == 0
    assert evidence_group_metrics(['new', 'other-fact'], groups)['all_known_hit@5'] == 1
    with pytest.raises(ValueError, match='positive_evidence_groups'):
        evidence_group_metrics(['new'], [[]])


@pytest.mark.parametrize('fault', [None, 'url', 'published_at', 'known_at', 'quote', 'digest'])
def test_equivalence_requires_original_version_and_exact_quote(fixture, fault):
    dataset, bundles, *_ = fixture
    anchor = dataset['questions'][0]['evidence'][0]
    original = bundles['source']; original['source']['url'] = 'https://example.test/annual'
    candidate = deepcopy(original); candidate['source']['id'] = 'other'
    candidate['chunks'][0]['id'] = 'other-chunk'
    candidate['chunks'][0]['body'] = original['chunks'][0]['body'].replace(' ', '\n')
    candidate['chunks'][0]['digest'] = sha256(candidate['chunks'][0]['body'].encode()).hexdigest()
    alternative = dict(source_id='other', chunk_id='other-chunk', body_sha256=candidate['chunks'][0]['digest'])
    if fault == 'url': candidate['source']['url'] = 'https://example.test/quarter'
    if fault == 'published_at': candidate['source']['published_at'] = '2026-04-01'
    if fault == 'known_at': candidate['source']['metadata'] = '{"known_at":"2026-04-01"}'
    if fault == 'quote':
        candidate['chunks'][0]['body'] = candidate['chunks'][0]['body'].replace('2', '20')
        candidate['chunks'][0]['digest'] = alternative['body_sha256'] = sha256(candidate['chunks'][0]['body'].encode()).hexdigest()
    if fault == 'digest': alternative['body_sha256'] = 'wrong'
    if fault:
        with pytest.raises(ValueError, match='equivalent_evidence'):
            verify_equivalent_quote(anchor, original, alternative, candidate)
    else:
        verify_equivalent_quote(anchor, original, alternative, candidate)
