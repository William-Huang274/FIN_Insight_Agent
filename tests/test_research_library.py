import json
from hashlib import sha256
import sqlite3

import pytest

from sec_agent.research_foundation.research_snapshot import build_snapshot, ResearchSnapshot
from sec_agent.research_foundation.research_library import publish_library, ResearchLibrary
from sec_agent.research_foundation.source_document_navigation import SourceDocumentRequest


def publish(tmp_path):
    origin = tmp_path/'diagnostic.sqlite'
    sources = [dict(id='DOC', title='Public release', url='https://example.test/filing',
        published_at='2025-01-01', vintage='dated_original', access_state='readable', digest='a'*64)]
    passages = [dict(id='PASSAGE::p', source_id='DOC', locator='p1', body='A announced supply to B. Contract is prospective.')]
    entities = [dict(id=n, name=n, kind='company') for n in ('A','B','C')]
    edges = [dict(id='AB', subject='A', object='B', predicate='supply', source_id='DOC', locator='p1', published_at='2025-01-01', status='announced', qualifiers={'not_delivered':True})]
    build_snapshot(origin, sources, passages, entities=entities, edges=edges, observations=[dict(id='O',kind='capacity',source_id='DOC',entity='A',period='2025',unit='MW',payload={'value':10,'status':'planned'})])
    target = tmp_path/'published.sqlite'
    manifest = publish_library(target, [origin], public_sources_confirmed=True)
    return origin, target, manifest


def test_publish_separates_diagnostic_and_production_and_preserves_graph_evidence(tmp_path):
    origin, target, manifest = publish(tmp_path)
    with pytest.raises(ValueError, match='snapshot_not_complete'):
        ResearchSnapshot(target)
    with pytest.raises(FileNotFoundError):
        ResearchLibrary(origin)
    library = ResearchLibrary(target)
    request = SourceDocumentRequest(source_space='library', operation='search', query='supply', entity_id='A')
    result = library.navigate(request, '2025-02-01')
    assert result.total_matches == 2 and result.items[1]['qualifiers']['not_delivered']
    assert result.items[0]['title']=='Public release'
    assert result.items[0]['publication_date']=='2025-01-01'
    assert result.items[0]['source_vintage']=='dated_original'
    assert result.items[0]['source_known_at'] is None
    assert result.items[1]['evidence'][0]['id'] == 'PASSAGE::p'
    result = library.navigate(SourceDocumentRequest(source_space='library', operation='read', document_id='DOC', node_id='PASSAGE::p'), '2025-02-01')
    assert result.items[0]['passage_id'] == 'PASSAGE::p'
    assert result.items[0]['content_sha256'] == sha256(result.items[0]['passage'].encode()).hexdigest()
    assert result.source_snapshot_sha256 == manifest['sha256']
    assert not result.numeric_fact_authority
    observations=library.navigate(SourceDocumentRequest(source_space='library',operation='observations',entity_id='A'),'2025-02-01')
    assert observations.items[0]['payload']['status']=='planned'
    assert observations.items[0]['unit']=='MW' and not observations.items[0]['numeric_fact_authority']


def test_time_filters_relationships_and_sources_and_missing_is_typed(tmp_path):
    _, target, _ = publish(tmp_path)
    library = ResearchLibrary(target)
    assert library.graph_search('A', '2024-01-01')['edges'] == []
    assert library.graph_search('unknown','2025-02-01')['status'] == 'unknown_entity'
    request = SourceDocumentRequest(source_space='library', operation='read', document_id='DOC')
    assert library.navigate(request, '2024-01-01').execution_receipt.status == 'scope_ineligible'
    request = SourceDocumentRequest(source_space='library', operation='read', document_id='missing')
    assert 'unknown_source' in library.navigate(request, '2025-02-01').notice


def test_catalog_recency_keeps_future_gap_and_search_does_not_invent_publication_date(tmp_path):
    origin=tmp_path/'origin.sqlite'
    sources=[dict(id=identity,title='Example report '+identity,url='https://example.test/'+identity,
                  published_at=day,vintage='known_as_of' if day is None else 'dated_original',
                  access_state='readable',digest=identity,metadata={'known_at':'2025-01-01'} if day is None else {})
             for identity,day in [('A-old','2024-01-01'),('Z-new','2025-01-01'),('B-future','2027-01-01'),('C-unknown',None)]]
    build_snapshot(origin,sources,[dict(id='P'+s['id'],source_id=s['id'],locator='p1',body='Example supply evidence.') for s in sources])
    target=tmp_path/'published.sqlite'
    publish_library(target,[origin],public_sources_confirmed=True)
    library=ResearchLibrary(target,retrieval_environment={})
    catalog=library.navigate(SourceDocumentRequest(source_space='library',operation='catalog',query='Example report'),'2025-02-01')
    docs=[i for i in catalog.items if 'document_id' in i]
    assert [i['document_id'] for i in docs]==['Z-new','A-old','C-unknown','B-future']
    assert docs[-1]['eligible'] is False
    result=library.navigate(SourceDocumentRequest(source_space='library',operation='search',query='supply',document_id='C-unknown'),'2025-02-01')
    assert result.items[0]['publication_date'] is None
    assert result.items[0]['source_known_at']=='2025-01-01'


def test_release_integrity_and_no_overwrite(tmp_path):
    origin, target, _ = publish(tmp_path)
    with pytest.raises(FileExistsError):
        publish_library(target, [origin], public_sources_confirmed=True)
    with sqlite3.connect(target) as db:
        db.execute("UPDATE passages SET body='wrong'")
    with pytest.raises(ValueError, match='integrity'):
        ResearchLibrary(target)


def test_request_compatibility_and_scope():
    legacy = SourceDocumentRequest(operation='catalog').model_dump(mode='json')
    assert 'graph_depth' not in legacy and 'entity_id' not in legacy
    with pytest.raises(ValueError, match='graph_navigation_requires_library'):
        SourceDocumentRequest(operation='related', entity_id='A')


def test_public_scope_requires_confirmation(tmp_path):
    with pytest.raises(ValueError, match='public_source_scope'):
        publish_library(tmp_path/'bad.sqlite', [])


def test_active_release_mutation_rejected_before_model_reads(tmp_path):
    _, target, _ = publish(tmp_path)
    library=ResearchLibrary(target)
    with sqlite3.connect(target) as db:
        db.execute("UPDATE edges SET predicate='fabricated'")
    with pytest.raises(ValueError,match='changed_during_run'):
        library.navigate(SourceDocumentRequest(source_space='library',operation='related',entity_id='A'),'2025-02-01')


def test_backup_restores_original_library_graph_and_sources(tmp_path):
    from test_service_backup import setup
    from sec_agent.research_foundation.asset_set_backup import backup_asset_set, restore_asset_set
    _, target, manifest=publish(tmp_path/'library_source')
    args=setup(tmp_path/'assets')
    backup_asset_set(args['project_root'],args['task_root'],tmp_path/'backup',research_library=target)
    receipt=restore_asset_set(tmp_path/'backup',tmp_path/'restore')
    restored=ResearchLibrary(receipt['global_sources']['research_library'])
    assert restored.manifest['sha256']==manifest['sha256']
    assert restored.graph_search('A','2025-02-01')['edges'][0]['object']=='B'
    assert restored.read('DOC','2025-02-01')['items'][0]['id']=='PASSAGE::p'
