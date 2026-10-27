"""Disk staging preserves publication identity and rejects unapproved input."""
import json
import sqlite3
import zlib
from uuid import uuid4

import pytest

from retrieval.prepared_node_store import PreparedNodeStore
from sec_agent.research_foundation.organization_execution_access import OrganizationExecutionUnavailable
from sec_agent.research_foundation.organization_hybrid_retrieval import preparation_nodes, publish_prepared_index
from test_organization_hybrid_retrieval import setup


def test_staging_requires_seal_and_detects_changed_payload(tmp_path):
    store = PreparedNodeStore(tmp_path/'staged.sqlite')
    try:
        rows = [{'node_id':'a', 'content':'中文正文'}, {'node_id':'b', 'content':'Second'}]
        store.extend(rows)
        with pytest.raises(ValueError, match='not_sealed'): list(store)
        with pytest.raises(sqlite3.IntegrityError): store.extend([rows[0]])
        store.seal()
        assert list(store) == rows and store[-1] == rows[-1] and store[:] == rows
        with pytest.raises(ValueError, match='already_sealed'): store.extend([])
        with pytest.raises(FileExistsError): PreparedNodeStore(store.path)
        store.db.execute('UPDATE nodes SET payload=? WHERE position=0', (zlib.compress(b'{}'),))
        with pytest.raises(ValueError, match='row_changed'): store[0]
    finally:
        store.close()


def test_projected_store_publishes_identical_vectors_lexical_and_navigation(tmp_path):
    from sec_agent.research_foundation.organization_index_release import CHUNK_PROJECTION
    reader, state, org, rows = setup(tmp_path/'source')
    store = PreparedNodeStore(tmp_path/'staged.sqlite')
    try:
        staged_org, staged = preparation_nodes(reader, workbench_url='http://localhost', node_store=store)
        assert staged is store and staged_org == org and list(staged) == rows
        release = str(uuid4())
        vectors = [[1.] + [0.]*1023 for _ in rows]
        manifests = []
        for name, nodes in [('list', rows), ('disk', staged)]:
            publish_prepared_index(tmp_path/name, org, nodes, vectors, {},
                model='qwen3.7-text-embedding', provenance={'scope':'deterministic test'},
                release_id=release, projection=CHUNK_PROJECTION)
            directory = tmp_path/name/org/'releases'/release
            manifests.append(json.loads((directory/'index.json').read_bytes()))
        assert manifests[0] == manifests[1]
        for name in ('vectors.npy', 'lexical.sqlite', 'navigation.sqlite'):
            assert (tmp_path/'list'/org/'releases'/release/name).read_bytes() == (tmp_path/'disk'/org/'releases'/release/name).read_bytes()
    finally:
        store.close()


def test_final_revocation_keeps_disk_rows_unreadable(tmp_path, monkeypatch):
    reader, state, _, _ = setup(tmp_path/'source')
    store = PreparedNodeStore(tmp_path/'staged.sqlite')
    check = reader._after
    def revoke(before):
        state['status'] = 404
        check(before)
    monkeypatch.setattr(reader, '_after', revoke)
    try:
        with pytest.raises(OrganizationExecutionUnavailable):
            preparation_nodes(reader, workbench_url='http://localhost', node_store=store)
        assert not store.sealed
        with pytest.raises(ValueError, match='not_sealed'): list(store)
    finally:
        store.close()


def test_projection_stages_before_bulk_authority_returns(tmp_path, monkeypatch):
    reader, _, _, expected = setup(tmp_path/'source')
    store = PreparedNodeStore(tmp_path/'staged.sqlite')
    project_sources = reader._project_sources
    depth = 0
    def inspect(resource_ids, project):
        nonlocal depth
        if depth:
            return project_sources(resource_ids, project)
        def checked(resource_id, result):
            returned = project(resource_id, result)
            assert returned is None  # No retained per-source rows in the bulk result.
            assert len(store) > 0  # Already on disk before the bulk method returns.
            assert not store.sealed
            with pytest.raises(ValueError, match='not_sealed'):
                list(store)
            return returned
        depth += 1
        try:
            return project_sources(resource_ids, checked)
        finally:
            depth -= 1
    monkeypatch.setattr(reader, '_project_sources', inspect)
    try:
        _, rows = preparation_nodes(reader, workbench_url='http://localhost', node_store=store)
        assert list(rows) == expected
    finally:
        store.close()
