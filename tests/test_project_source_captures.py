"""Source selection to real project storage, task tools and recovery; no models."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import sqlite3
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from test_data_library import library as source_library
from test_project_research_materials import prepared, WRITE
from apps.workbench.backend.api.v1.asset_workspace import build_asset_workspace_router
from apps.workbench.backend.api.v1.conversations import build_conversations_router
from sec_agent.research_foundation.asset_workspace import AssetWorkspace
from sec_agent.research_foundation.asset_backup import backup_assets, restore_assets
from sec_agent.research_foundation.source_document_navigation import SourceDocumentRequest
from sec_agent.research_foundation.task_attachments import TaskAttachmentStore, task_material_catalog


def setup(tmp_path, source_library):
    source, root = source_library
    app, service, calls, tid, library, project, _, _ = prepared(tmp_path/'runtime')
    app.include_router(build_asset_workspace_router(library.documents.root, attachments_root=root, fact_mart=root/'mart.sqlite'),prefix='/api/v1')
    app.include_router(build_conversations_router(service),prefix='/api/v1')
    service.audit_root = tmp_path/'audit'
    return TestClient(app), source, root, service, calls, tid, AssetWorkspace(library.documents.root), project


def selections(source):
    doc = source.get('/api/v1/data-library/sources/DOC::MSFT2025').json()
    page = source.get('/api/v1/data-library/financials?ticker=MSFT&fiscal_year=2025').json()
    return [dict(kind='library', document_id='DOC::MSFT2025',snapshot=doc['snapshot'],section_ids=[doc['sections'][0]['selection_id']]),
            dict(kind='financial',query=page['selection_query'],snapshot=page['snapshot'],row_ids=[page['items'][0]['selection_id']])]


def save(client, project, selection, note='My unverified hypothesis'):
    response = client.post('/api/v1/asset-workspace/captures',headers=WRITE,json={'project_id':project,'selection':selection,'note':note,'title':selection['kind']})
    assert response.status_code == 200, response.text
    return response.json()


def reference(workspace, project, saved):
    return next(v['ref'] for a in workspace.catalog('local-pilot',project)['items'] for v in a['versions'] if v['ref']['version_id']==saved['document_id'])


@pytest.mark.parametrize('destination',['research','conversation'])
def test_both_sources_copy_exact_versions_to_native_draft_and_actual_tools(tmp_path, source_library, destination):
    client, source, root, service, calls, tid, workspace, project = setup(tmp_path,source_library)
    saved = [save(client,project,s) for s in selections(source)]
    refs = [reference(workspace,project,s) for s in saved]
    result=client.post('/api/v1/asset-workspace/contexts',headers=WRITE,json={'schema_version':'asset_context.v1',
        'question':'Read both selected sources and verify period and unit.','memory_version':0,'refs':refs})
    assert result.status_code==200, result.text
    context=result.json()
    endpoint='/api/v1/research-sessions' if destination=='research' else '/api/v1/conversations/drafts'
    body={'mode':'research','defer_start':True} if destination=='research' else {}
    response=client.post(endpoint,headers=WRITE,json={**body,'asset_context_id':context['context_id']})
    assert response.status_code==200,response.text
    copies=service.attachment_store.list(tid)
    assert len(copies)==2
    for original,copy in zip(saved,copies):
        assert copy['digest']==original['digest']
        assert copy['project_origin']['asset_capture']==original['project_origin']['asset_capture']
        read=asyncio.run(service.attachment_store.read(thread_id=tid,request=SourceDocumentRequest(
            source_space='uploads',operation='read',document_id=copy['document_id'],limit=20)))
        content='\n'.join(i['passage'] for i in read.items)
        assert 'My unverified hypothesis' in content and '用户批注（非来源事实）' in content
        assert all(i['project_origin']['asset_capture'] for i in read.items)
        assert not read.numeric_fact_authority
    financial=service.attachment_store.get(tid,copies[1]['document_id'])['body']
    assert b'"value_decimal": "100"' in financial and b'"unit": "USD"' in financial
    assert b'2025-06-30' in financial and b'2025-09-01' in financial
    assert task_material_catalog(copies)[1]['source_selection']['kind']=='financial'
    # The original mart changes after the task was prepared: fixed input stays intact.
    with sqlite3.connect(root/'mart.sqlite') as db:db.execute("UPDATE company_fact_observations SET value_decimal='999'")
    assert service.attachment_store.get(tid,copies[1]['document_id'])['body']==financial
    changed=client.put('/api/v1/asset-workspace/captures/note',headers=WRITE,json={'base_ref':refs[1],'note':'Updated user opinion'})
    assert changed.status_code==200,changed.text
    assert service.attachment_store.get(tid,copies[1]['document_id'])['body']==financial
    assert client.get('/api/v1/asset-workspace/contexts/'+context['context_id']).json()['source_status'][1]['status']=='newer_version_available'
    workspace.library.set_access('local-pilot',project,'document',refs[1]['version_id'],True)
    with pytest.raises(ValueError):service.attachment_store.get(tid,copies[1]['document_id'])
    assert not any(c[0]=='run' for c in calls)


def test_browser_snapshot_conflict_and_forged_selection_do_not_save(tmp_path,source_library):
    client,source,root,_,_,_,workspace,project=setup(tmp_path,source_library)
    selected=selections(source)
    count=len(workspace.library.documents.list(workspace.library.scope('local-pilot',project)))
    for s in [dict(selected[0],snapshot='0'*64),dict(selected[0],section_ids=['S::HPE2025']),
              dict(selected[1],row_ids=['f'*64]),dict(selected[1],row_ids=selected[1]['row_ids']*2)]:
        r=client.post('/api/v1/asset-workspace/captures',headers=WRITE,json={'project_id':project,'title':'Attempt','selection':s})
        assert r.status_code==409,r.text
    with sqlite3.connect(root/'mart.sqlite') as db:db.execute("UPDATE company_fact_observations SET unit='EUR'")
    r=client.post('/api/v1/asset-workspace/captures',headers=WRITE,json={'project_id':project,'title':'Changed','selection':selected[1]})
    assert r.status_code==409
    assert len(workspace.library.documents.list(workspace.library.scope('local-pilot',project)))==count


def test_idempotency_concurrent_notes_source_protection_and_recovery(tmp_path,source_library):
    client,source,_,_,_,_,workspace,project=setup(tmp_path,source_library)
    s=selections(source)[0]
    saved=save(client,project,s)
    assert save(client,project,s)['document_id']==saved['document_id']
    ref=reference(workspace,project,saved)
    assert client.post('/api/v1/asset-workspace/documents',headers=WRITE,json={'project_id':project,'base_ref':ref,'title':'Forged','text':'Alter original'}).status_code==409
    scope=workspace.library.scope('local-pilot',project)
    with pytest.raises(ValueError,match='固定来源不可替换'):
        workspace.library.documents.add(scope,'bypass.md',b'Alter original',revision={'parent':saved['document_id'],'change_kind':'correction'})
    def change(i):return client.put('/api/v1/asset-workspace/captures/note',headers=WRITE,json={'base_ref':ref,'note':f'Opinion {i}'})
    with ThreadPoolExecutor(2) as pool:responses=list(pool.map(change,range(2)))
    assert sorted(r.status_code for r in responses)==[200,409]
    newer=next(r.json() for r in responses if r.status_code==200)
    newref=reference(workspace,project,newer)
    assert workspace.read('local-pilot',newref)['capture']['snapshot_digest']==workspace.read('local-pilot',ref)['capture']['snapshot_digest']
    context=client.post('/api/v1/asset-workspace/contexts',headers=WRITE,json={'schema_version':'asset_context.v1',
        'question':'Read this exact version after recovery.','memory_version':0,'refs':[newref]}).json()
    backup_assets(workspace.library.documents.root,tmp_path/'backup')
    restore_assets(tmp_path/'backup',tmp_path/'restored')
    restored=AssetWorkspace(tmp_path/'restored')
    assert restored.read('local-pilot',newref)==workspace.read('local-pilot',newref)
    assert restored.context('local-pilot',context['context_id'])['refs']==[newref]
    with pytest.raises(KeyError):restored.read('bob',newref)
    # Integrity failures must not reach a new handoff or note version.
    with restored.library.documents.connect() as db:db.execute('UPDATE attachment_captures SET note=? WHERE object_id=?',('tampered',newer['document_id']))
    with pytest.raises(ValueError,match='完整性'):restored.resolve('local-pilot',newref)
    workspace.library.set_access('local-pilot',project,'document',ref['version_id'],True)
    duplicate=client.post('/api/v1/asset-workspace/captures',headers=WRITE,json={
        'project_id':project,'title':'library','note':'My unverified hypothesis','selection':s})
    assert duplicate.status_code==409  # idempotent retry cannot restore revoked use


def test_owner_and_origin_cannot_be_supplied_by_client(tmp_path,source_library):
    client,source,_,_,_,_,workspace,project=setup(tmp_path,source_library)
    selection=selections(source)[1]
    foreign=str(uuid4());workspace.library.save('bob',0,{'projects':[{'id':foreign,'name':'Private'}],'assignments':{},'pinned':[]})
    payload={'project_id':foreign,'title':'Private write','selection':selection}
    assert client.post('/api/v1/asset-workspace/captures',headers=WRITE,json=payload).status_code==404
    payload['project_id']=project
    assert client.post('/api/v1/asset-workspace/captures',headers={**WRITE,'Origin':'https://untrusted.example'},json=payload).status_code==403
    assert client.post('/api/v1/asset-workspace/captures',headers=WRITE,json={**payload,'source_role':'official_fact'}).status_code==422
