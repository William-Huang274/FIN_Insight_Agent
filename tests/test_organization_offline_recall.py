from hashlib import sha256
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from scripts.engineering.diagnose_organization_retrieval_candidates import frozen_cosine_scores, main
from retrieval.query_embeddings import QueryEmbeddingSource
from retrieval.qwen_api import RetrievalResponse
from sec_agent.research_foundation.organization_graph_index import project
from sec_agent.research_foundation.organization_hybrid_retrieval import publish_prepared_index
from sec_agent.research_foundation.organization_source_navigation import OrganizationSourceNavigation
from sec_agent.research_foundation.organization_source_projection import source_nodes, PROJECTION


def setup(tmp_path, monkeypatch, receipt):
    intake = tmp_path/'intake'; intake.mkdir()
    checkpoint = tmp_path/'checkpoint'; checkpoint.mkdir()
    def write(path, value): path.write_text(json.dumps(value), encoding='utf8')
    body = 'Alpha cash revenue improved during the fiscal year.'
    digest = sha256(body.encode()).hexdigest()
    item = {'resource_id': str(uuid4()), 'title': 'Alpha annual report', 'ref': {'digest': digest}}
    bundle = {'library_sha256': 'snapshot', 'text': body, 'source': {'id': 'source', 'digest': digest,
        'url': 'https://example.test/report', 'metadata': '{}', 'vintage': 'dated_original', 'published_at': '2026-01-01'},
        'chunks': [{'id': 'chunk', 'body': body, 'digest': digest, 'context': '', 'parent_id': 'parent',
            'locator': 'text-part:1', 'char_start': 0, 'char_end': len(body), 'source_char_start': 0,
            'source_char_end': len(body), 'embedding_input_sha256': sha256(('\n'+body).encode()).hexdigest()}],
        'edges': [], 'edge_chunk_links': []}
    write(intake/'source.json', bundle)
    write(intake/'result.json', {'status': 'verified', 'library_sha256': 'snapshot',
        'sources': [{'source_id': 'source', 'directory': '.', 'chunks': 1,
                     'files': {'source.json': sha256((intake/'source.json').read_bytes()).hexdigest()}}],
        'source_index': {'embedding_model': 'qwen3.7-text-embedding', 'matrix_sha256': 'a'*64}})
    document = OrganizationSourceNavigation._identity(item)
    nodes = [r for r in source_nodes(bundle, document, item, 'http://localhost') if r['node_kind'] == 'text']
    organization, release = str(uuid4()), str(uuid4())
    publish_prepared_index(tmp_path/'indices', organization, nodes, [[1.]+[0.]*1023],
        {'Alpha cash': [1.]+[0.]*1023}, model='qwen3.7-text-embedding',
        provenance={'source_intake_sha256': sha256((intake/'result.json').read_bytes()).hexdigest()},
        release_id=release, projection=PROJECTION, graph_sources=[project(bundle, document)])
    directory = tmp_path/'indices'/organization/'releases'/release
    write(checkpoint/'manifest.json', {'publication': {'resources': {'source': item['resource_id']},
        'grants': {'source': {'id': item['resource_id'], 'binding': {'ref': item['ref']}}}}})
    write(tmp_path/'questions.json', {'evaluation_role': 'historical_regression', 'library_sha256': 'snapshot',
        'questions': [{'id': 'q1', 'family': 'f1', 'split': 'development', 'query': 'Alpha cash',
            'as_of': '2026-09-23', 'evidence': [{'source_id': 'source', 'chunk_id': 'chunk',
                'body_sha256': digest, 'quote': 'cash revenue improved'}]}]})
    class Api:
        embedding_model = 'qwen3.7-text-embedding'
        rerank_model = 'qwen3-rerank'
        def embed(self, texts):
            return RetrievalResponse([[1.]+[0.]*1023], {}, 'fixture', self.embedding_model)
    source = QueryEmbeddingSource(tmp_path/'query-cache', Api(), model=Api.embedding_model)
    source.embed('Alpha cash' if receipt else 'a different question', scope='public-recall-qualification',
                 index_digest='a'*64, model=Api.embedding_model, dimensions=1024)
    args = ['offline', '--intake', str(intake), '--dataset', str(tmp_path/'questions.json'),
        '--index-directory', str(directory), '--matrix', str(directory/'vectors.npy'),
        '--publication-checkpoint', str(checkpoint), '--query-cache', str(tmp_path/'query-cache'),
        '--output', str(tmp_path/'output'), '--split', 'all']
    monkeypatch.setattr('sys.argv', args)
    monkeypatch.setattr('psutil.virtual_memory', lambda: SimpleNamespace(available=2*2**30))
    return tmp_path/'output', tmp_path/'query-cache/records-v1.sqlite'


def test_offline_full_scope_uses_immutable_index_and_readonly_receipt(tmp_path, monkeypatch):
    output, cache = setup(tmp_path, monkeypatch, True)
    before = sha256(cache.read_bytes()).hexdigest()
    main()
    result = json.loads((output/'result.json').read_text(encoding='utf8'))
    assert result['status'] == 'completed' and result['provider_calls'] == 0
    assert result['candidate_sources'] == result['candidate_chunks'] == 1
    assert result['samples'][0]['metrics']['fused_candidates']['known_hit@5'] == 1
    assert not result['S2_passed'] and sha256(cache.read_bytes()).hexdigest() == before


def test_missing_receipt_is_recorded_failure_without_network_fallback(tmp_path, monkeypatch):
    output, cache = setup(tmp_path, monkeypatch, False)
    before = sha256(cache.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match='successful_query_receipt_required'):
        main()
    result = json.loads((output/'result.json').read_text(encoding='utf8'))
    assert result['status'] == result['samples'][0]['status'] == 'failed'
    assert 'summary' not in result and result['provider_calls'] == 0
    assert sha256(cache.read_bytes()).hexdigest() == before


def test_automatic_planner_retains_unknown_sources_without_mutating_receipts(tmp_path, monkeypatch):
    import sys
    output, cache = setup(tmp_path, monkeypatch, True)
    before = sha256(cache.read_bytes()).hexdigest()
    monkeypatch.setattr(sys, 'argv', [*sys.argv, '--query-planning', 'conservative.v1'])
    main()
    report = json.loads((output/'result.json').read_text(encoding='utf8'))
    sample = report['samples'][0]
    assert report['query_planning'] == 'conservative.v1'
    assert sample['query_plan']['selected_sources'] == 1
    assert sample['known_evidence_excluded'] == []
    assert sample['metrics']['fused_candidates']['known_hit@5'] == 1
    assert sha256(cache.read_bytes()).hexdigest() == before


def test_planner_scope_depends_on_query_and_catalog_not_labels():
    from scripts.engineering.diagnose_organization_retrieval_candidates import planned_records
    records = [{'document_id': x, 'node_id': x} for x in ['a', 'b', 'u']]
    metadata = {'a': {'issuer_id':'ISSUER::acme', 'company_name':'Acme'},
                'b': {'issuer_id':'ISSUER::beta', 'company_name':'Beta'}, 'u':{}}
    selected, receipt = planned_records(records, metadata, 'Acme revenue')
    assert [r['node_id'] for r in selected] == ['a', 'u']
    assert receipt['unknown_sources_retained'] == 1
    assert planned_records(records, metadata, 'Compare Acme and Beta')[0] == records


def test_scoring_releases_mapping_and_keeps_exact_owned_scores(tmp_path, monkeypatch):
    import gc
    import weakref
    import numpy as np
    from sec_agent.research_foundation.organization_vector_math import cosine_scores
    matrix = np.zeros((3, 1024), dtype=np.float32)
    matrix[0, 0] = 1; matrix[1, 0] = -1; matrix[2, 1] = 1
    path = tmp_path/'vectors.npy'; np.save(path, matrix)
    original = np.load
    references = []
    def tracked(*args, **kwargs):
        mapped = original(*args, **kwargs)
        references.append(weakref.ref(mapped))
        return mapped
    monkeypatch.setattr(np, 'load', tracked)
    scores = frozen_cosine_scores(path, [2, 0, 1], matrix[0], 3)
    np.testing.assert_array_equal(scores, cosine_scores(matrix, [2, 0, 1], matrix[0]))
    gc.collect()
    assert references[0]() is None and scores.flags.owndata
    with pytest.raises(ValueError, match='matrix_shape_mismatch'):
        frozen_cosine_scores(path, [0], matrix[0], 1)


def test_filter_diagnostic_retains_baseline_and_reports_excluded_evidence(tmp_path, monkeypatch):
    import sys
    output, cache = setup(tmp_path, monkeypatch, True)
    plan = {'role': 'development_query_only_manual_constraints', 'queries': {'q1': {
        'query_sha256': sha256(b'Alpha cash').hexdigest(),
        'variants': [{'name': 'explicit-form', 'constraint': {'form': '10-K'},
                      'basis': 'Manual scenario; not an automatic parser', 'unresolved': ['fiscal year']}]}}}
    path = tmp_path/'plan.json'
    path.write_text(json.dumps(plan), encoding='utf8')
    monkeypatch.setattr(sys, 'argv', [*sys.argv, '--source-filter-plan', str(path)])
    before = sha256(cache.read_bytes()).hexdigest()
    main()
    report = json.loads((output/'result.json').read_text(encoding='utf8'))
    sample = report['samples'][0]
    assert sample['metrics']['fused_candidates']['known_hit@5'] == 1
    assert len(sample['filter_diagnostics']) == 2
    for variant in sample['filter_diagnostics']:
        assert variant['coverage']['unknown_sources'] == 1 and variant['candidate_chunks'] == 0
        assert variant['known_evidence_excluded'] == sample['gold']
        assert variant['metrics']['fused_candidates']['known_hit@5'] == 0
    assert sha256(cache.read_bytes()).hexdigest() == before


@pytest.mark.parametrize('fault', ['query', 'heldout', 'answer_id'])
def test_filter_plan_rejects_changed_query_heldout_or_answer_identity(fault):
    from scripts.engineering.organization_filter_diagnosis import validate_plan
    row = {'id': 'q', 'split': 'development', 'query': 'Example query'}
    variant = {'name': 'issuer', 'constraint': {'issuer_id': 'ISSUER'}, 'basis': 'query text', 'unresolved': []}
    plan = {'role': 'development_query_only_manual_constraints', 'queries': {'q': {
        'query_sha256': sha256(row['query'].encode()).hexdigest(), 'variants': [variant]}}}
    assert validate_plan(plan, [row])
    if fault == 'query': row['query'] = 'changed'
    elif fault == 'heldout': row['split'] = 'heldout'
    else: variant['constraint'] = {'source_id': 'answer-source'}
    with pytest.raises(ValueError): validate_plan(plan, [row])
