"""New-query reuse keeps fresh authorization, exact ranking and live readback."""
from copy import deepcopy
from pathlib import Path
import sqlite3

import pytest

from test_organization_search_cache import setup
from test_organization_complete_sources import complete_fixture
from sec_agent.research_foundation.organization_projection_cache import (
    OrganizationProjectionCache, encode_projection, decode_projection)
from sec_agent.research_foundation.organization_source_projection import source_nodes
from sec_agent.research_foundation.organization_source_navigation import OrganizationSourceNavigation
from sec_agent.research_foundation.organization_execution_access import OrganizationExecutionUnavailable


def content(result):
    return [{k: v for k, v in row.items() if k != 'retrieval'} for row in result.items]


def test_response_hit_reports_no_projection_reads_for_current_request(tmp_path, monkeypatch):
    nav, _, state, _, request, _, reads, _ = setup(tmp_path, monkeypatch)
    query = {**request, 'query': 'different revenue question'}
    projected = nav.navigate(query)
    assert projected.items[0]['retrieval']['projection_cache_hits'] > 0
    reads.clear()
    calls = state['calls']
    cached = nav.navigate(query)
    receipt = cached.items[0]['retrieval']
    assert receipt['response_cache_hit']
    assert receipt['projection_cache_hits'] == 0
    assert receipt['provider_calls'] == 0
    assert not reads and state['calls'] >= calls + 2
    assert content(cached) == content(projected)


def test_new_query_and_filtered_scope_equal_full_original_path(tmp_path, monkeypatch):
    nav, reader, state, directory, request, first, reads, api = setup(tmp_path, monkeypatch)
    for changes in ({'query': 'different revenue question'},
                    {'query': 'revenue', 'document_id': first.items[0]['document_id']},
                    {'query': 'question', 'limit': 1,
                     'document_id': first.items[0]['document_id']}):
        reads.clear()
        calls = state['calls']
        actual = nav.navigate({**request, **changes})
        assert not reads and state['calls'] >= calls + 2
        assert actual.items[0]['retrieval']['projection_cache_hits'] > 0
        with sqlite3.connect(directory/'rank-cache.sqlite') as ranks:
            ranks.execute('DELETE FROM ranks')
        baseline = OrganizationSourceNavigation(reader, workbench_url='http://localhost', retrieval_root=tmp_path/'indices')
        baseline.hybrid.query_source = nav.hybrid.query_source
        expected = baseline._navigate({**request, **changes})
        assert not expected.items[0]['retrieval']['cache_hit']
        assert reads and content(actual) == content(expected)
        for key in ('dense_node_ids', 'lexical_node_ids', 'candidate_node_ids'):
            assert actual.items[0]['retrieval'][key] == expected.items[0]['retrieval'][key]
    reads.clear()
    nav.navigate(actual.items[0]['readback'])
    assert reads  # Complete originals are never served by this cache.


@pytest.mark.parametrize('fault', ['body', 'delete', 'local_revoke', 'wal', 'java_revoke'])
def test_changed_storage_or_authority_blocks_new_query(tmp_path, monkeypatch, fault):
    nav, reader, state, _, request, _, reads, api = setup(tmp_path, monkeypatch)
    if fault == 'java_revoke':
        state['status'] = 404
    elif fault == 'local_revoke':
        manifest = reader._grant()[1]
        row = manifest['inputs'][0]
        reader.workspace.library.set_access('organization:'+manifest['organization_id'],
                                           row['space_id'], 'document', row['ref']['version_id'], True)
    else:
        with sqlite3.connect(reader.workspace.library.documents.path) as db:
            if fault == 'wal':
                db.execute('PRAGMA journal_mode=WAL')
                nav.navigate(request)
            if fault == 'delete':
                db.execute('DELETE FROM attachments')
            else:
                db.execute('UPDATE attachments SET body=?', (b'bad',))
    provider_calls = api.calls
    with pytest.raises((OrganizationExecutionUnavailable, KeyError)):
        nav.navigate({**request, 'query': 'a new question'})
    assert api.calls == provider_calls


@pytest.mark.parametrize('fault', ['write', 'revoke'])
def test_change_while_reusing_projection_never_returns_result(tmp_path, monkeypatch, fault):
    nav, reader, state, _, request, _, _, api = setup(tmp_path, monkeypatch)
    get = nav._projection_cache.get
    def changed(resource):
        result = get(resource)
        if fault == 'write':
            with sqlite3.connect(reader.workspace.library.documents.path) as db:
                db.execute('UPDATE attachments SET body=?', (b'changed during projection reuse',))
        else:
            state['status'] = 404
        return result
    monkeypatch.setattr(nav._projection_cache, 'get', changed)
    with pytest.raises(OrganizationExecutionUnavailable):
        nav.navigate({**request, 'query': 'new question'})
    assert api.calls == 1


def test_cached_bytes_cannot_be_changed_or_carried_to_another_generation(tmp_path, monkeypatch):
    nav, _, _, _, request, _, _, api = setup(tmp_path, monkeypatch)
    cache = nav._projection_cache
    filename, _, size = next(iter(cache.entries.values()))
    path = Path(cache.directory.name)/filename
    path.write_bytes(b'x' * size)
    with pytest.raises(ValueError, match='projection_cache_integrity'):
        nav.navigate({**request, 'query': 'new question'})
    assert api.calls == 1
    directory = Path(cache.directory.name)
    cache.reset(('new authority', 'new storage'))
    assert not directory.exists() and not cache.entries and cache.size == 0


def test_complete_chunk_codec_preserves_nodes_without_decoded_corpus(tmp_path, monkeypatch):
    _, ref, _, _, _, _, bundle, _ = complete_fixture(tmp_path, monkeypatch, repeats=80)
    nodes = source_nodes(bundle, 'ORGDOC::fixture', {'title':'中文 🧾', 'ref':ref}, 'http://localhost')
    value = ('ORGDOC::fixture', nodes, {'ref':ref}, {r['node_id']:r['original_source'] for r in nodes})
    packed, _ = encode_projection(value)
    actual = decode_projection(packed)
    assert actual[0] == value[0] and actual[2:] == value[2:]
    assert [dict(r) for r in actual[1]] == [dict(r) for r in nodes]
    assert actual[1][0]._metadata is actual[1][1]._metadata
    assert actual[1][0]._body is actual[1][1]._body
    from retrieval.text import tokenize
    from collections import Counter
    for row in actual[1]:
        expected_tokens = tokenize(row['content'])
        terms = row.lexical_counts()
        assert terms.length == len(expected_tokens)
        assert list(terms.counts.items()) == list(Counter(expected_tokens).items())
    cache = OrganizationProjectionCache(tmp_path/'cache', limit=len(packed)-1)
    cache.reset('generation')
    cache.put('resource', value)
    assert cache.get('resource') is None and cache.size == 0
    assert cache.directory is None


def test_new_query_reuses_token_counts_without_retokenizing_originals(tmp_path, monkeypatch):
    nav, _, _, _, request, _, reads, _ = setup(tmp_path, monkeypatch)
    from sec_agent.research_foundation import organization_projection_cache as module
    def unexpected_tokenization(_):
        raise AssertionError('cached projections must not rebuild token counts')
    monkeypatch.setattr(module, 'pack_terms', unexpected_tokenization)
    reads.clear()
    result = nav.navigate({**request, 'query': 'different revenue question'})
    assert result.items and not reads
    assert result.items[0]['retrieval']['projection_cache_hits'] > 0


@pytest.mark.parametrize('text', ['', '[]', '现金流与收入 收入', 'cash cash flow rare-a'])
def test_projection_terms_preserve_model_text_and_original_lookup(text):
    from retrieval.query_bm25 import lexical_document, lexical_scores
    rows = [{'node_id': 'node', 'content': 'different body', 'model_text': text,
             'original_source': {'source_id':'source'}}]
    value = ('document', rows, {}, {'node': {'overridden':True}, 'extra': {'id':'extra'}})
    encoded, _ = encode_projection(value)
    actual = decode_projection(encoded)
    assert [dict(row) for row in actual[1]] == rows
    assert actual[3] == value[3]
    import numpy as np
    for query in (['cash', 'cash'], ['收入'], ['unknown']):
        expected = lexical_scores([lexical_document(rows[0])], query)
        result = lexical_scores([lexical_document(actual[1][0])], query)
        np.testing.assert_array_equal(expected[0], result[0])
        assert expected[1:] == result[1:]


def test_cache_value_mutation_does_not_change_next_query(tmp_path, monkeypatch):
    nav, _, _, _, request, _, _, _ = setup(tmp_path, monkeypatch)
    resource = next(iter(nav._projection_cache.entries))
    value = nav._projection_cache.get(resource)
    original = deepcopy(value[2])
    value[2]['ref']['digest'] = 'bad'
    assert nav._projection_cache.get(resource)[2] == original


def test_cache_disk_pressure_disables_admission_without_losing_original_path(tmp_path, monkeypatch):
    nav, _, _, _, request, _, reads, _ = setup(tmp_path, monkeypatch)
    cache = nav._projection_cache
    cache.reset(None)
    from types import SimpleNamespace
    from sec_agent.research_foundation import organization_projection_cache as module
    monkeypatch.setattr(module.shutil, 'disk_usage', lambda _: SimpleNamespace(free=0))
    first = nav.navigate({**request, 'query': 'new query'})
    assert reads and first.items and not cache.entries and cache.admission_disabled
    reads.clear()
    second = nav.navigate({**request, 'query': 'another query'})
    assert reads and second.items and not cache.entries
