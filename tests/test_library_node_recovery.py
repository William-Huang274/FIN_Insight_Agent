from contextlib import closing
from copy import deepcopy
import json
import sqlite3
from types import SimpleNamespace
from uuid import uuid4

import pytest

from test_library_source_bundle import database, vectors_for
from test_organization_execution_access import runtime_at, runtime_grant
from test_organization_research_inputs import fixture as space_fixture
from retrieval.library_chunks import split_parent
from retrieval.library_node_recovery import NodeRecoveryCatalog, validate_nodes, validate_bundle, FORMAT
from retrieval.library_source_bundle import build_source_bundle, compact_source_bundle, expand_source_bundle, text_digest
from retrieval.library_vectors import digest
from scripts.data_retrieval.prepare_indexed_node_recovery import prepare
from scripts.data_retrieval.prepare_library_source_bundles import prepare as export
from sec_agent.research_foundation.asset_workspace import AssetWorkspace
from sec_agent.research_foundation.project_source_captures import CaptureRequest, save_capture
from sec_agent.research_foundation.organization_source_projection import source_nodes
from sec_agent.research_foundation.organization_execution_access import OrganizationExecutionUnavailable
from sec_agent.research_foundation.organization_source_navigation import OrganizationSourceNavigation


def original_fixture(root):
    (root/'published').mkdir();(root/'originals').mkdir()
    dbpath=root/'published/library.sqlite';sid=database(dbpath,'placeholder')
    raw_digest='a'*64
    nodes=[]
    # Table and narrative are alternate stored surfaces, not substrings of the
    # section. Concatenation/global source offsets would assert a false order.
    for identifier,kind,body in [('section','section','Revenue section overview.'),
                                 ('table','table','| USD million | 2024 |\n| Revenue | 12.5 |'),
                                 ('child','chunk','\n'.join(f'Original narrative line {i}.' for i in range(1000))),
                                 ('mixed','mixed_prose_span','Footnote: fiscal year ended December 31.')]:
        nodes.append(dict(node_id=identifier,node_kind=kind,content=body,model_text='Navigation only\n'+body,
                          parent_document_id=sid,parent_section_id='section',section_path=['Part II','Revenue'],
                          page_start=2,page_end=3,content_sha256=text_digest(body),raw_body_sha256=raw_digest,
                          stable_url='https://example.test/report',fiscal_period='FY2024',period_end='2024-12-31',
                          publication_date='2025-02-01',numeric_authority=False))
    parents=[dict(id=n['node_id'],source_id=sid,body=n['content'],digest=n['content_sha256'],
                  locator=str(n['section_path'])+' / '+str(n['page_start'])) for n in nodes]
    with closing(sqlite3.connect(dbpath)) as db,db:
        db.row_factory=sqlite3.Row
        db.execute('UPDATE sources SET digest=?,metadata=?',(raw_digest,json.dumps({'origin':'existing_library'})))
        for table in ('passages','retrieval_chunks','edges','edge_chunk_links','edge_chunk_coverage'):db.execute(f'DELETE FROM {table}')
        db.executemany('INSERT INTO passages VALUES(:id,:source_id,:locator,:body,:digest)',parents)
        chunks=[c for p in parents for c in split_parent(p,'Filing')]
        db.executemany('INSERT INTO retrieval_chunks VALUES(:id,:source_id,:parent_id,:ordinal,:char_start,:char_end,:body,:digest,:locator,:context,:kind,:flags)',chunks)
        source=dict(db.execute('SELECT * FROM sources').fetchone())
    path=root/'originals/nodes.jsonl';path.write_text('\n'.join(json.dumps(n) for n in nodes),encoding='utf8')
    return dbpath,sid,path,source,parents,nodes


def ready(root):
    path,sid,nfile,source,parents,nodes=original_fixture(root)
    manifest=prepare(path,nfile,digest(nfile),[sid],root/'recovery')
    catalog=NodeRecoveryCatalog(root/'recovery/catalog.json',digest(root/'recovery/catalog.json'))
    with closing(sqlite3.connect(path)) as db:
        db.row_factory=sqlite3.Row
        bundle=build_source_bundle(db,sid,digest(path),node_catalog=catalog)
    return path,sid,nfile,source,parents,nodes,catalog,bundle


def test_indexed_node_capture_preserves_hierarchy_and_organization_readback(tmp_path,monkeypatch):
    path,sid,nfile,source,parents,nodes,catalog,bundle=ready(tmp_path)
    assert bundle['format']==FORMAT and bundle['node_recovery']['nodes']==nodes
    assert 'Revenue | 12.5' not in bundle['text'] and 'node_id' in bundle['text']
    assert all('source_char_start' not in c for c in bundle['chunks'])
    assert expand_source_bundle(compact_source_bundle(bundle))==bundle
    vectors_for(bundle,tmp_path/'vectors')
    result=export(path,tmp_path/'vectors',[sid],tmp_path/'export',node_catalog=catalog)
    assert result['status']=='verified' and result['sources'][0]['parsed_characters'] is None
    from scripts.data_retrieval.audit_library_source_intake import audit
    inventory=audit(path,tmp_path/'inventory.json',tmp_path/'vectors','2026-09-23',node_catalog=catalog)
    assert inventory['intake_statuses']=={'indexed_node_set_recoverable':1}
    assert inventory['verified_vectors']==len(bundle['chunks'])
    assert 'parsed_characters' not in inventory['sources'][0]
    import sec_agent.research_foundation.research_library as lm
    monkeypatch.setattr(lm,'open_library',lambda _:SimpleNamespace(path=path,manifest={'sha256':digest(path)}))
    monkeypatch.setenv('FINSIGHT_LIBRARY_NODE_CATALOG',str(tmp_path/'recovery/catalog.json'))
    monkeypatch.setenv('FINSIGHT_LIBRARY_NODE_SHA256',digest(tmp_path/'recovery/catalog.json'))
    private=AssetWorkspace(tmp_path/'private');project=str(uuid4())
    private.library.save('alice',0,{'projects':[{'id':project,'name':'Filings'}],'assignments':{},'pinned':[]})
    req=CaptureRequest(project_id=project,title='10-K',selection={'kind':'library_source','document_id':sid,'snapshot':digest(path)})
    saved=save_capture(private,'alice',req,None,None,path)
    assert save_capture(private,'alice',req,None,None,path)['document_id']==saved['document_id']
    ref=private.catalog('alice',project)['items'][0]['versions'][0]['ref']
    assert private.read('alice',ref)['capture']['selection_mode']=='indexed_node_set'
    shared,grant=space_fixture(tmp_path/'shared')
    org,space,rid=grant['organization_id'],grant['manifest']['inputs'][0]['space_id'],str(uuid4())
    binding=shared.publish(private,'alice',rid,org,space,ref)
    grant['manifest']['inputs']=[{**grant['manifest']['inputs'][0],'resource_id':rid,'ref':binding['ref'],'resource_type':'knowledge'}]
    grant['inputs']=[{'resource_id':rid,'binding':binding}]
    nfile.unlink();(tmp_path/'recovery/catalog.json').unlink()
    reader,state=runtime_at(shared,runtime_grant(grant))
    directory=reader.read_text(rid)
    assert directory['text_scope']=='indexed_node_directory' and not directory['complete_original_document']
    table=reader.read_text(rid,node_id='table')
    assert table['text']==nodes[1]['content'] and table['original_node']['fiscal_period']=='FY2024'
    assert not table['original_node']['numeric_authority']
    first=reader.read_text(rid,limit=16000,node_id='child')
    second=reader.read_text(rid,offset=first['next_offset'],limit=16000,node_id='child')
    assert first['text']+second['text']==nodes[2]['content']
    with pytest.raises(ValueError,match='not_in_selected'):reader.read_text(rid,node_id='other-document')
    nav=OrganizationSourceNavigation(reader,workbench_url='http://localhost')
    found=nav.navigate({'source_space':'organization','operation':'search','query':'Revenue'})
    chosen=next(r for r in found.items if r['original_source']['original_node_kind']=='table')
    read=nav.navigate(chosen['readback']).items[0]
    assert read['passage']==nodes[1]['content'] and read['original_source']['original_parent_section_id']=='section'
    assert not read['original_source']['complete_original_document'] and not read['numeric_fact_authority']
    state['status']=404
    with pytest.raises(OrganizationExecutionUnavailable):reader.read_text(rid,node_id='table')
    with pytest.raises(OrganizationExecutionUnavailable):nav.navigate(chosen['readback'])


@pytest.mark.parametrize('fault',['missing','duplicate','wrong_source','raw_digest','body','locator','node_hash','cross_section','section_cycle'])
def test_original_node_identity_hierarchy_and_coverage_fail_closed(tmp_path,fault):
    path,sid,nfile,source,parents,nodes=original_fixture(tmp_path)
    if fault=='missing':nodes.pop()
    if fault=='duplicate':nodes[-1]=deepcopy(nodes[0])
    if fault=='wrong_source':nodes[1]['parent_document_id']='other'
    if fault=='raw_digest':nodes[1]['raw_body_sha256']='0'*64
    if fault=='body':parents[1]['body']='changed table'
    if fault=='locator':parents[1]['locator']='page 9'
    if fault=='node_hash':nodes[1]['content_sha256']='0'*64
    if fault=='cross_section':nodes[1]['parent_section_id']='another-document-section'
    if fault=='section_cycle':nodes[0]['parent_section_id']='table'
    with pytest.raises(ValueError):validate_nodes(source,parents,nodes)


@pytest.mark.parametrize('fault',['node_payload','directory','chunk_span','chunk_source','parent_digest'])
def test_persisted_node_reference_snapshot_corruption(tmp_path,fault):
    *_,bundle=ready(tmp_path)
    compact=compact_source_bundle(bundle)
    if fault=='node_payload':compact['node_recovery']['nodes'][0]['period_end']='2099-01-01'
    if fault=='directory':compact['text']+='untrusted'
    if fault=='chunk_span':compact['chunks'][0]['char_end']+=1
    if fault=='chunk_source':compact['chunks'][0]['source_id']='other'
    if fault=='parent_digest':compact['parents'][0]['digest']='0'*64
    with pytest.raises(ValueError):expand_source_bundle(compact)


def test_node_catalog_requires_pinned_original_and_library(tmp_path):
    path,sid,nfile,source,parents,nodes=original_fixture(tmp_path)
    with pytest.raises(ValueError,match='original_node_file_digest'):
        prepare(path,nfile,'0'*64,[sid],tmp_path/'failed')
    assert json.loads((tmp_path/'failed/catalog.json').read_text())['status']=='failed'
    prepare(path,nfile,digest(nfile),[sid],tmp_path/'recovery')
    with pytest.raises(ValueError,match='catalog_digest'):NodeRecoveryCatalog(tmp_path/'recovery/catalog.json','0'*64)
    catalog=NodeRecoveryCatalog(tmp_path/'recovery/catalog.json',digest(tmp_path/'recovery/catalog.json'))
    with pytest.raises(ValueError,match='library_mismatch'):catalog.recover(source,parents,'0'*64)
    with closing(sqlite3.connect(path)) as db:
        db.row_factory=sqlite3.Row
        with pytest.raises(ValueError,match='catalog_required'):build_source_bundle(db,sid,digest(path))
