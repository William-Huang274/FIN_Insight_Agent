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


def test_graph_filters_before_budget_direction_each_hop_and_no_future(tmp_path,monkeypatch):
    _,path,manifest=publish(tmp_path)
    with sqlite3.connect(path) as db:
        # Many reviewed holdings cannot crowd out a requested supplier edge.
        for i in range(90):
            db.execute("INSERT INTO edges(id,subject,object,predicate,source_id,locator,published_at,valid_from,valid_to,status,qualifiers) SELECT ?,subject,object,'reported_security_position',source_id,locator,published_at,valid_from,valid_to,status,qualifiers FROM edges WHERE id='AB'",(f'holding-{i}',))
        db.execute("INSERT INTO edges(id,subject,object,predicate,source_id,locator,published_at,valid_from,valid_to,status,qualifiers) SELECT 'BC','B','C','supply',source_id,locator,published_at,valid_from,valid_to,status,qualifiers FROM edges WHERE id='AB'")
        db.execute("INSERT INTO edges(id,subject,object,predicate,source_id,locator,published_at,valid_from,valid_to,status,qualifiers) SELECT 'CA','C','A','supply',source_id,locator,'2028-01-01',valid_from,valid_to,status,qualifiers FROM edges WHERE id='AB'")
        db.execute("INSERT INTO edges(id,subject,object,predicate,source_id,locator,published_at,valid_from,valid_to,status,qualifiers) SELECT 'mention','A','C','co_mentions',source_id,locator,published_at,valid_from,valid_to,'needs_semantic_review',qualifiers FROM edges WHERE id='AB'")
    manifest['sha256']=module.digest_file(path)
    path.with_suffix('.sqlite.manifest.json').write_text(json.dumps(manifest))
    lib=module.ResearchLibrary(path)
    calls=[];original=lib._query
    def query(sql,args=()):
        calls.append(sql);return original(sql,args)
    monkeypatch.setattr(lib,'_query',query)
    result=lib.graph_search('A','2026-01-01',depth=2,predicates=['supply'],direction='outgoing',review='reviewed')
    assert [r['id'] for r in result['edges']]==['AB','BC'] and not result['truncated']
    assert len([sql for sql in calls if 'SELECT e.* FROM edges' in sql])==2
    assert lib.graph_search('A','2026-01-01',direction='incoming')['edges']==[]
    assert 'mention' not in [r['id'] for r in lib.graph_search('A','2026-01-01',review='reviewed',max_edges=1000)['edges']]
    assert lib.graph_search('A','2026-01-01',max_edges=2)['truncated']


def test_graph_filter_wire_compatibility_and_text_independence(tmp_path):
    from sec_agent.research_foundation.source_document_navigation import SourceDocumentRequest
    legacy=SourceDocumentRequest(operation='catalog').model_dump(mode='json')
    assert not {'graph_predicates','graph_direction','graph_review'} & legacy.keys()
    with pytest.raises(ValueError,match='graph_filters_require'):
        SourceDocumentRequest(operation='search',query='supply',graph_review='reviewed')
    lib=chunk_library(tmp_path)
    req=SourceDocumentRequest(source_space='library',operation='search',entity_id='A',query='supply',graph_predicates=['missing_type'])
    result=lib.navigate(req,'2026-01-01')
    assert any(r.get('node_id','').startswith('CHUNK::') for r in result.items)
    assert not any(r.get('predicate') for r in result.items)
