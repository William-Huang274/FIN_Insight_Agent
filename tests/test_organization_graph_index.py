from copy import deepcopy
import sqlite3
from types import SimpleNamespace
from uuid import uuid4

import pytest

from test_organization_candidate_index import prepared, query
from test_organization_execution_access import runtime_at, runtime_grant
from sec_agent.research_foundation.organization_graph_index import project, build, candidates, preparation_graph
from sec_agent.research_foundation.organization_hybrid_retrieval import preparation_nodes, publish_prepared_index
from sec_agent.research_foundation.organization_index_release import load_release
from sec_agent.research_foundation.organization_source_navigation import OrganizationSourceNavigation
from sec_agent.research_foundation.organization_source_projection import PROJECTION
from sec_agent.research_foundation.source_document_navigation import SourceDocumentRequest
from sec_agent.research_foundation.organization_execution_access import OrganizationExecutionUnavailable


def graph_fixture(tmp_path,monkeypatch):
    import test_organization_complete_sources as fixtures
    original=fixtures.database
    def database(path,text):
        sid=original(path,text)
        with sqlite3.connect(path) as db:
            for name in ('subject','object','predicate','published_at','valid_from','valid_to'):
                db.execute('ALTER TABLE edges ADD COLUMN '+name+' TEXT')
            db.execute("UPDATE edges SET subject='ENTITY::A',object='ENTITY::B',predicate='supplies',published_at='2025-02-01'")
        return sid
    monkeypatch.setattr(fixtures,'database',database)
    _,reader,_,_,grant=prepared(tmp_path,monkeypatch)
    graphs=preparation_graph(reader)
    org,nodes=preparation_nodes(reader,workbench_url='http://localhost')
    release=str(uuid4());vec=[1.]+[0.]*1023
    linked={link['node_id'] for graph in graphs for link in graph['links']}
    vectors=[([-1.]+[0.]*1023) if row['node_id'] in linked else vec for row in nodes]
    publish_prepared_index(tmp_path/'indices',org,nodes,vectors,
        {'disclosure':vec,'USD millions':vec,'unmatchedliteralqz':vec},model='qwen3.7-text-embedding',provenance={'fixture':True},
        release_id=release,projection=PROJECTION,graph_sources=graphs)
    directory,_,_,contract=load_release(tmp_path/'indices',org,release)
    grant['manifest']['retrieval_index']=contract
    reader,state=runtime_at(SimpleNamespace(workspace=reader.workspace),runtime_grant(grant))
    return OrganizationSourceNavigation(reader,workbench_url='http://localhost',retrieval_root=tmp_path/'indices'),reader,state,directory,grant


def test_frozen_graph_search_candidates_and_raw_citations_remain_authorized(tmp_path,monkeypatch):
    nav,reader,state,directory,grant=graph_fixture(tmp_path,monkeypatch)
    request=query(entity_id='ENTITY::A')
    first=nav.navigate(request)
    receipt=first.items[0]['retrieval']
    assert receipt['mode']=='organization-cosine-bm25-graph-rrf.v1'
    assert len(receipt['graph_node_ids'])==2
    assert set(receipt['graph_node_ids'])<=set(receipt['candidate_node_ids'])
    assert receipt['candidate_body_reads']<=48
    assert {e['subject'] for e in receipt['graph_evidence']}=={'ENTITY::A'}
    assert nav.navigate(request).items[0]['retrieval']['response_cache_hit']
    document=nav._identity(grant['manifest']['inputs'][0])
    scoped=nav.navigate(query(entity_id='ENTITY::A',document_id=document))
    assert len(scoped.items[0]['retrieval']['graph_node_ids'])==1
    assert {e['document'] for e in scoped.items[0]['retrieval']['graph_evidence']}=={document}
    node=scoped.items[0]['retrieval']['graph_node_ids'][0]
    read=nav.navigate({'source_space':'organization','operation':'read','document_id':document,'node_id':node})
    assert read.items[0]['result_state']=='source_bound_passage'
    assert nav.navigate(query(entity_id='ENTITY::A',graph_direction='incoming')).items[0]['retrieval']['graph_node_ids']==[]
    state['status']=404
    with pytest.raises(OrganizationExecutionUnavailable):nav.navigate(request)
    with pytest.raises(OrganizationExecutionUnavailable):
        nav.navigate({'source_space':'organization','operation':'read','document_id':document,'node_id':node})


@pytest.mark.parametrize('fault',['file','stale_original'])
def test_graph_corruption_or_version_mismatch_cannot_return_cached_results(tmp_path,monkeypatch,fault):
    nav,reader,_,directory,_=graph_fixture(tmp_path,monkeypatch)
    if fault=='file':
        nav.navigate(query(entity_id='ENTITY::A'))
        with sqlite3.connect(directory/'graph.sqlite') as db:
            db.execute("UPDATE edges SET subject='FORGED'")
    else:
        original=reader._read_storage
        def changed(*args):
            result=deepcopy(original(*args))
            result['source_bundle']['edges'][0]['subject']='FORGED'
            return result
        monkeypatch.setattr(reader,'_read_storage',changed)
    with pytest.raises(ValueError):nav.navigate(query(entity_id='ENTITY::A'))


def test_nonpublished_graph_and_two_hop_do_not_fall_back_to_public_library(tmp_path,monkeypatch):
    nav,*_=prepared(tmp_path,monkeypatch)
    with pytest.raises(ValueError,match='graph_not_published'):
        nav.navigate(query(entity_id='ENTITY::A'))
    for changes in ({'graph_depth':2},{'operation':'related'},{'source_space':'local'}):
        with pytest.raises(ValueError):SourceDocumentRequest.model_validate(query(entity_id='ENTITY::A',**changes))


def test_graph_channel_adds_evidence_missing_from_dense_and_lexical_candidates(tmp_path,monkeypatch):
    nav,*_=graph_fixture(tmp_path,monkeypatch)
    baseline=nav.navigate(query(query='unmatchedliteralqz')).items[0]['retrieval']
    augmented=nav.navigate(query(query='unmatchedliteralqz',entity_id='ENTITY::A')).items[0]['retrieval']
    assert baseline['lexical_node_ids']==[]
    assert augmented['graph_node_ids']
    assert not set(augmented['graph_node_ids']) & set(baseline['candidate_node_ids'])
    assert set(augmented['graph_node_ids'])<=set(augmented['candidate_node_ids'])
    assert not augmented['cache_hit'] and augmented['provider_calls']==0


def test_other_organization_cannot_use_a_known_graph_directory(tmp_path,monkeypatch):
    first=tmp_path/'first';second=tmp_path/'second'
    first.mkdir();second.mkdir()
    with monkeypatch.context() as patch:
        a,_,_,_,_=graph_fixture(first,patch)
        result=a.navigate(query(entity_id='ENTITY::A'))
        assert result.items[0]['retrieval']['graph_node_ids']
    with monkeypatch.context() as patch:
        b,_,_,_,_=graph_fixture(second,patch)
        b.hybrid.root=first/'indices'
        with pytest.raises(ValueError):b.navigate(query(entity_id='ENTITY::A'))


def test_authorized_graph_filtering_precedes_quota_and_preserves_status_and_time(tmp_path):
    # More hidden links than the quota must not displace visible evidence.
    edges=[];links=[];records=[]
    for i in range(30):
        node=f'n{i}';edge=f'e{i}'
        edges.append(dict(id=edge,subject='A',object='B',predicate='supplies',status='announced',
                          published_at='2020-01-01',valid_from=None,valid_to=None))
        links.append(dict(edge_id=edge,node_id=node,content_sha256='a'*64,evidence_index=0))
        records.append(dict(node_id=node,document_id='doc',content_sha256='a'*64))
    edges[25]['status']='needs_semantic_review'
    edges[26]['valid_to']='2020-01-02'
    edges[27]['published_at']='2030-01-01'
    path=tmp_path/'graph.sqlite'
    build(path,[dict(document_id='doc',edges=edges,links=links)],records)
    rows=[dict(node_id=r['node_id'],parent_document_id='doc',content_sha256=r['content_sha256']) for r in records[24:]]
    request=SourceDocumentRequest.model_validate(query(entity_id='A'))
    ids,evidence=candidates(path,rows,request,'2025-01-01',[])
    assert ids==['n24','n28','n29']
    assert all(e['status']=='announced' for e in evidence)  # Not promoted to confirmed facts.
    assert candidates(path,rows,request.model_copy(update={'graph_predicates':('owns',)}),'2025-01-01',[])[0]==[]
    assert candidates(path,rows,request.model_copy(update={'entity_id':'hidden-other-entity'}),'2025-01-01',[])[0]==[]


@pytest.mark.parametrize('fault',['edge_source','link_chunk','span','node_digest'])
def test_graph_publication_rejects_invalid_evidence_identity(tmp_path,monkeypatch,fault):
    nav,reader,_,_,grant=graph_fixture(tmp_path,monkeypatch)
    before,manifest,bindings=reader._grant()
    item=manifest['inputs'][0]
    bundle=deepcopy(reader._read_storage(item['resource_id'],manifest,bindings)['source_bundle'])
    if fault=='edge_source':bundle['edges'][0]['source_id']='foreign'
    elif fault=='link_chunk':bundle['edge_chunk_links'][0]['chunk_id']='foreign'
    elif fault=='span':bundle['edge_chunk_links'][0]['span_end']=0
    else:
        projected=project(bundle,nav._identity(item))
        with pytest.raises(ValueError,match='node_version'):
            build(tmp_path/'bad.sqlite',[projected],[dict(node_id=l['node_id'],document_id=projected['document_id'],content_sha256='b'*64) for l in projected['links']])
        return
    with pytest.raises(ValueError):project(bundle,nav._identity(item))
