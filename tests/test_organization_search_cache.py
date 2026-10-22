"""Warm responses skip original blobs only while storage AND authority are current."""
from copy import deepcopy
import sqlite3

import pytest

from retrieval.query_embeddings import QueryEmbeddingSource
from sec_agent.research_foundation.organization_source_navigation import OrganizationSourceNavigation
from sec_agent.research_foundation.organization_execution_access import OrganizationExecutionUnavailable
from test_organization_index_release import prepared, Api, MODEL


def setup(tmp_path, monkeypatch):
    reader, state, _, _, directory, _ = prepared(tmp_path)
    nav = OrganizationSourceNavigation(reader, workbench_url='http://localhost', retrieval_root=tmp_path/'indices')
    api = Api()
    nav.hybrid.query_source = QueryEmbeddingSource(tmp_path/'query-cache', api, model=MODEL)
    reads = []
    original = reader._read_storage
    def read(*args):
        reads.append(args[0])
        return original(*args)
    monkeypatch.setattr(reader, '_read_storage', read)
    request = {'source_space': 'organization', 'operation': 'search', 'query': 'revenue'}
    first = nav.navigate(request)
    assert reads
    reads.clear()
    return nav, reader, state, directory, request, first, reads, api


def test_warm_skips_originals_rechecks_authority_and_keeps_readback_live(tmp_path, monkeypatch):
    nav, reader, state, _, request, first, reads, api = setup(tmp_path, monkeypatch)
    calls = state['calls']
    warm = nav.navigate(request)
    assert not reads and state['calls'] >= calls + 2 and api.calls == 1
    assert warm.items[0]['retrieval']['response_cache_hit']
    assert warm.items[0]['retrieval']['provider_calls'] == 0
    assert warm.items[0]['preview'] == first.items[0]['preview']
    # A caller cannot mutate a subsequent cached result.
    warm.items[0]['title'] = 'poison'
    assert nav.navigate(request).items[0]['title'] != 'poison'
    original = nav.navigate(first.items[0]['readback'])
    assert reads and original.items[0]['writer_citable']
    state['status'] = 404
    with pytest.raises(OrganizationExecutionUnavailable):
        nav.navigate(request)
    with pytest.raises(OrganizationExecutionUnavailable):
        nav.navigate(first.items[0]['readback'])


@pytest.mark.parametrize('fault', ['body', 'delete', 'local_revoke', 'wal_write'])
def test_storage_changes_invalidate_even_when_java_grant_is_unchanged(tmp_path, monkeypatch, fault):
    nav, reader, state, _, request, _, reads, _ = setup(tmp_path, monkeypatch)
    frozen = deepcopy(state['grant'])
    db = sqlite3.connect(reader.workspace.library.documents.path)
    try:
        if fault == 'wal_write':
            db.execute('PRAGMA journal_mode=WAL')
            # Warm again after the journal-mode change; next committed WAL
            # write must invalidate even without a checkpoint into the DB.
            nav.navigate(request)
            reads.clear()
        if fault == 'local_revoke':
            manifest = reader._grant()[1]
            item = manifest['inputs'][0]
            reader.workspace.library.set_access('organization:'+manifest['organization_id'],
                item['space_id'], 'document', item['ref']['version_id'], True)
        elif fault == 'delete':
            db.execute('DELETE FROM attachments')
            db.commit()
        else:
            db.execute('UPDATE attachments SET body=?', (b'corrupted original',))
            db.commit()
        with pytest.raises((OrganizationExecutionUnavailable, KeyError)):
            nav.navigate(request)
        assert reads and state['grant'] == frozen
    finally:
        db.close()


@pytest.mark.parametrize('fault', ['matrix', 'index', 'missing_database', 'revoke_during_hit', 'write_during_hit'])
def test_cache_hit_cannot_hide_corruption_or_racing_revocation(tmp_path, monkeypatch, fault):
    nav, reader, state, directory, request, _, reads, _ = setup(tmp_path, monkeypatch)
    if fault == 'matrix':
        (directory/'vectors.npy').write_bytes(b'bad')
    elif fault == 'index':
        (directory/'index.json').write_text('{}')
    elif fault == 'missing_database':
        # Exercise the observer's unavailable-storage boundary without relying
        # on Windows allowing unlink of an open SQLite connection.
        nav._search_cache.path = tmp_path/'missing.sqlite'
    else:
        from sec_agent.research_foundation import organization_index_release as releases
        load = releases.load_release
        def race(*args, **kwargs):
            result = load(*args, **kwargs)
            if fault == 'revoke_during_hit':
                state['status'] = 404
            else:
                with sqlite3.connect(reader.workspace.library.documents.path) as db:
                    db.execute('UPDATE attachments SET body=?', (b'changed during hit',))
            return result
        monkeypatch.setattr(releases, 'load_release', race)
    with pytest.raises((ValueError, OSError, OrganizationExecutionUnavailable)):
        nav.navigate(request)
    assert not reads


def test_scope_change_reuses_projection_but_new_session_rechecks_originals(tmp_path, monkeypatch):
    nav, reader, _, _, request, first, reads, _ = setup(tmp_path, monkeypatch)
    scoped = nav.navigate({**request, 'document_id': first.items[0]['document_id']})
    assert not reads and scoped.items[0]['retrieval']['projection_cache_hits'] == 1
    assert not scoped.items[0]['retrieval'].get('response_cache_hit')
    reads.clear()
    other = OrganizationSourceNavigation(reader, workbench_url='http://localhost', retrieval_root=tmp_path/'indices')
    other.hybrid.query_source = nav.hybrid.query_source
    other.navigate(request)
    assert reads


def test_concurrent_same_session_hits_are_isolated_and_authorized(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    nav, _, state, _, request, first, reads, _ = setup(tmp_path, monkeypatch)
    calls = state['calls']
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: nav.navigate(request), range(8)))
    assert not reads and state['calls'] >= calls + 16
    assert all(r.items[0]['retrieval']['response_cache_hit'] for r in results)
    results[0].items[0]['title'] = 'changed'
    assert all(r.items[0]['title'] == first.items[0]['title'] for r in results[1:])
