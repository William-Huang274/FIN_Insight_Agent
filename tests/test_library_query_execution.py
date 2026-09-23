"""Execution equivalence and isolation, not financial recall certification."""
import json
import sqlite3

import pytest

from retrieval.library_chunks import build_chunks, edge_evidence, edge_evidence_batch
from sec_agent.research_foundation import research_library as module
from test_research_library import publish


def chunk_library(tmp_path):
    _, path, manifest = publish(tmp_path)
    build_chunks(path)
    manifest['sha256'] = module.digest_file(path)
    path.with_suffix('.sqlite.manifest.json').write_text(json.dumps(manifest), encoding='utf8')
    return module.ResearchLibrary(path)


def test_validation_shared_without_sharing_request_environment(tmp_path, monkeypatch):
    _, path, _ = publish(tmp_path)
    original = module.digest_file
    scans = []
    def digest(p):
        scans.append(str(p))
        return original(p)
    monkeypatch.setattr(module, 'digest_file', digest)
    first = module.ResearchLibrary(path, retrieval_environment={'scope':'first'})
    second = module.ResearchLibrary(path, retrieval_environment={'scope':'second'})
    assert len(scans) == 1
    assert first.retrieval_environment == {'scope':'first'}
    assert second.retrieval_environment == {'scope':'second'}
    with sqlite3.connect(path) as db:
        db.execute("UPDATE passages SET body='changed'")
    with pytest.raises(ValueError, match='integrity'):
        module.ResearchLibrary(path)
    assert len(scans) == 2


def test_fts_qualification_precedes_limit_and_scores_unchanged(tmp_path):
    lib = chunk_library(tmp_path)
    with sqlite3.connect(lib.path) as db:
        # A stronger global match is outside eligible document scope.
        db.execute("INSERT INTO chunk_search VALUES('outside','unpublished','','supply supply supply')")
    expression = '"supply"'
    old = lib._query('SELECT c.id FROM chunk_search f JOIN retrieval_chunks c ON c.id=f.id '
        'WHERE chunk_search MATCH ? AND c.source_id=? ORDER BY bm25(chunk_search,0,0,0.3,1.0) LIMIT 1', (expression,'DOC'))
    ids = lib.search_chunk_ids(expression,['DOC'],limit=1)
    assert ids == [r['id'] for r in old]
    assert lib.search(['supply'],'2024-01-01',limit=1) == []
    assert lib.search(['supply'],'2026-01-01',source_ids=['missing'],limit=1) == []
    assert lib.search_chunk_ids(expression,['DOC'],edge_ids=['AB'],limit=1) == ids
    assert lib.search_chunk_ids(expression,['DOC'],edge_ids=[],limit=1) == []


def test_batched_evidence_matches_original_including_dynamic_gap(tmp_path, monkeypatch):
    lib = chunk_library(tmp_path)
    expected = {eid:edge_evidence(lib,eid) for eid in ['AB','dynamic']}
    calls = []; original = lib._query
    def query(sql, parameters=()):
        calls.append(sql)
        return original(sql, parameters)
    monkeypatch.setattr(lib,'_query',query)
    assert edge_evidence_batch(lib,['AB','dynamic']) == expected
    assert len(calls) == 2
    graph = lib.graph_search('A','2026-01-01')
    assert graph['edges'][0]['evidence'] == expected['AB'][0]
    assert graph['edges'][0]['parent_evidence'][0]['id'] == 'PASSAGE::p'
    assert lib.graph_search('A','2026-01-01',max_edges=0)['truncated']
