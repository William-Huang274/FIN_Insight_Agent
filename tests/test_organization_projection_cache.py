"""New-query reuse keeps fresh authorization, exact ranking and live readback."""
from copy import deepcopy
from contextlib import closing
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
    key, _, size = next(iter(cache.entries.values()))
    with closing(sqlite3.connect(cache.path)) as db, db:
        db.execute('UPDATE projections SET payload=? WHERE resource_id=?', (b'x' * size, key))
    with pytest.raises(ValueError, match='projection_cache_integrity'):
        nav.navigate({**request, 'query': 'new question'})
    assert api.calls == 1
    directory = Path(cache.directory.name)
    cache.reset(('new authority', 'new storage'))
    assert not directory.exists() and not cache.entries and cache.size == 0


def test_deleted_cache_row_rebuilds_from_live_authorized_original(tmp_path, monkeypatch):
    nav, _, _, _, request, _, reads, _ = setup(tmp_path, monkeypatch)
    cache = nav._projection_cache
    resource = next(iter(cache.entries))
    with closing(sqlite3.connect(cache.path)) as db, db:
        db.execute('DELETE FROM projections WHERE resource_id=?', (resource,))
    reads.clear()
    result = nav.navigate({**request, 'query':'new question'})
    assert result.items and reads
    assert resource in cache.entries


def test_cache_corruption_fails_before_query_provider(tmp_path, monkeypatch):
    nav, _, _, _, request, _, _, api = setup(tmp_path, monkeypatch)
    with closing(sqlite3.connect(nav._projection_cache.path)) as db, db:
        db.execute('DROP TABLE projections')
    calls = api.calls
    with pytest.raises(ValueError, match='projection_cache_integrity'):
        nav.navigate({**request, 'query':'new question'})
    assert api.calls == calls


def test_projection_database_handles_close_before_directory_cleanup(tmp_path, monkeypatch):
    import gc
    import weakref
    nav, _, _, _, _, _, _, _ = setup(tmp_path, monkeypatch)
    cache = nav._projection_cache
    directory = Path(cache.directory.name)
    assert cache.db.execute('PRAGMA cache_size').fetchone()[0] == -2048
    assert cache.db.execute('PRAGMA mmap_size').fetchone()[0] == 0
    reference = weakref.ref(cache)
    nav._projection_cache = None
    del cache
    gc.collect()
    assert reference() is None and not directory.exists()


def test_failed_cache_insert_does_not_publish_an_entry(tmp_path, monkeypatch):
    nav, _, _, _, request, _, reads, _ = setup(tmp_path, monkeypatch)
    cache = nav._projection_cache
    with closing(sqlite3.connect(cache.path)) as db, db:
        db.execute('DELETE FROM projections')
        db.execute("CREATE TRIGGER refuse_insert BEFORE INSERT ON projections BEGIN SELECT RAISE(ABORT, 'fixture'); END")
    cache.entries.clear()
    cache.size = 0
    reads.clear()
    result = nav.navigate({**request, 'query':'new question'})
    assert result.items and reads and cache.admission_disabled
    assert not cache.entries and cache.size == 0


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


def test_new_query_reuses_statistics_but_storage_generation_discards_them(tmp_path, monkeypatch):
    nav, reader, _, _, request, _, reads, _ = setup(tmp_path, monkeypatch, publish_lexical=False)
    stats = nav._projection_cache.lexical_statistics
    assert stats.entry is not None and not stats.hit
    result = nav.navigate({**request, 'query': 'different revenue question'})
    assert result.items and stats.hit and not reads
    assert stats.postings_hit and stats.postings is not None
    # A real unrelated commit changes the observer epoch even if the Java
    # grant and all original rows stay unchanged. Rebuild rather than reuse.
    with closing(sqlite3.connect(reader.workspace.library.documents.path)) as db, db:
        db.execute('CREATE TABLE statistics_epoch_probe(value INTEGER)')
    nav.navigate({**request, 'query': 'next revenue question'})
    assert reads and not stats.hit
    assert not stats.postings_hit


def test_verified_new_query_does_not_unpack_any_node_terms(tmp_path, monkeypatch):
    nav, _, _, _, request, _, reads, _ = setup(tmp_path, monkeypatch, publish_lexical=False)
    def unexpected(*args):
        raise AssertionError('query should decode requested posting columns only')
    monkeypatch.setattr('sec_agent.research_foundation.organization_projection_cache.unpack_terms', unexpected)
    result = nav.navigate({**request, 'query':'different revenue question'})
    assert result.items and not reads and nav._projection_cache.lexical_statistics.postings_hit


def test_lexical_statistics_does_not_authorize_revoked_query(tmp_path, monkeypatch):
    nav, _, state, _, request, _, reads, api = setup(tmp_path, monkeypatch, publish_lexical=False)
    assert nav._projection_cache.lexical_statistics.entry is not None
    calls = api.calls
    state['status'] = 404
    with pytest.raises(OrganizationExecutionUnavailable):
        nav.navigate({**request, 'query': 'new revenue query'})
    assert not reads and api.calls == calls


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


@pytest.mark.parametrize('fault', ['magic', 'header_length', 'negative_body', 'short_body',
                                  'trailing_bytes', 'negative_position', 'short_header'])
def test_binary_projection_frame_rejects_inconsistent_boundaries(fault):
    import json
    import zlib
    from sec_agent.research_foundation.organization_projection_cache import _FRAME, _MAGIC
    value = ('document', [{'node_id': 'node', 'content': '现金流 🧾'}], {}, {})
    encoded, _ = encode_projection(value)
    raw = zlib.decompress(encoded)
    _, length = _FRAME.unpack_from(raw)
    end = _FRAME.size + length
    metadata, binary = json.loads(raw[_FRAME.size:end]), raw[end:]
    if fault == 'magic':
        raw = b'WRONG' + raw[5:]
    elif fault == 'header_length':
        raw = _FRAME.pack(_MAGIC, len(raw) + 1) + raw[_FRAME.size:]
    elif fault == 'short_body':
        raw = raw[:-1]
    elif fault == 'trailing_bytes':
        raw += b'x'
    elif fault == 'short_header':
        raw = b'OP'
    else:
        if fault == 'negative_body':
            metadata[4][0][0] = -1
        else:
            metadata[1][0][2] = -1
        header = json.dumps(metadata).encode()
        raw = _FRAME.pack(_MAGIC, len(header)) + header + binary
    with pytest.raises(ValueError, match='projection_cache_invalid_frame'):
        decode_projection(zlib.compress(raw))


def test_projection_shares_immutable_values_but_not_mutable_metadata():
    title = 'Repeated long source identity with unicode 组织资料'
    rows = [{'node_id': str(i), 'content': 'cash flow', 'title': title,
             'original_source': {'source_id': title}} for i in range(4100)]
    value = ('doc', rows, {}, {})
    packed, _ = encode_projection(value)
    first = decode_projection(packed)
    second = decode_projection(packed)
    assert [dict(row) for row in first[1]] == rows
    assert first[1][0]['title'] is first[1][-1]['title']
    assert first[1][0]['title'] is first[1][-1]['original_source']['source_id']
    assert first[1][0]['title'] is not second[1][0]['title']
    first[1][0]['original_source']['source_id'] = 'mutated'
    assert first[1][-1]['original_source']['source_id'] == title
    assert second[1][0]['original_source']['source_id'] == title


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
