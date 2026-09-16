"""Asset contract, real storage and native draft adapters; zero model requests."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from apps.workbench.backend.api.v1.asset_workspace import build_asset_workspace_router
from apps.workbench.backend.api.v1.conversations import build_conversations_router
from sec_agent.research_foundation.asset_workspace import AssetWorkspace, AssetContextRequest, asset_context_prompt
from sec_agent.research_foundation.asset_backup import backup_assets, restore_assets
from test_project_research_materials import prepared, WRITE
from test_project_library import app_at, index, PROJECT, WRITE as AUTH_WRITE
from test_project_financial_facts import mapped_task


def setup(tmp_path):
    app, service, calls, tid, library, project, doc, _ = prepared(tmp_path)
    app.include_router(build_asset_workspace_router(tmp_path/'project-library'), prefix='/api/v1')
    app.include_router(build_conversations_router(service), prefix='/api/v1')
    service.audit_root = tmp_path/'audit'
    return TestClient(app), service, calls, tid, AssetWorkspace(tmp_path/'project-library'), project


def selection(workspace, project):
    return workspace.catalog('local-pilot', project)['items'][0]['current']['ref']


def context(client, ref, version=0):
    response=client.post('/api/v1/asset-workspace/contexts',headers=WRITE,json={
        'schema_version':'asset_context.v1','question':'Read this saved asset and identify what still needs verification.',
        'refs':[ref],'memory_version':version})
    assert response.status_code==200,response.text
    return response.json()


@pytest.mark.parametrize('destination',['research','conversation'])
def test_pinned_handoff_survives_edit_and_revocation_blocks_dispatch(tmp_path,destination):
    client, service, calls, tid, workspace, project=setup(tmp_path)
    ref=selection(workspace,project)
    assert client.put('/api/v1/asset-workspace/profile',headers=WRITE,json={'version':0,'body':'Focus on cash conversion; keep period and unit.'}).status_code==200
    saved=context(client,ref,1)
    endpoint='/api/v1/research-sessions' if destination=='research' else '/api/v1/conversations/drafts'
    draft={'mode':'research','defer_start':True} if destination=='research' else {}
    result=client.post(endpoint,headers=WRITE,json={**draft,'asset_context_id':saved['context_id']})
    assert result.status_code==200,result.text
    assert not any(c[0]=='run' for c in calls)
    metadata=asyncio.run(service.sdk.threads.get(tid))['metadata']
    assert metadata['asset_context']==saved
    assert saved['question'] in asset_context_prompt(metadata)
    assert 'Focus on cash conversion' in asset_context_prompt(metadata)
    copies=service.attachment_store.list(tid)
    assert len(copies)==1 and copies[0]['project_origin']['document_id']==ref['version_id']
    original=service.attachment_store.get(tid,copies[0]['document_id'])['body']
    edit=client.post('/api/v1/asset-workspace/documents',headers=WRITE,json={'project_id':project,'base_ref':ref,'title':'Updated.md','text':'New user hypothesis, not a verified fact.'})
    assert edit.status_code==200,edit.text
    restored=AssetWorkspace(workspace.library.documents.root)
    assert len(next(a for a in restored.catalog('local-pilot',project)['items'] if a['asset_id']==ref['asset_id'])['versions'])==2
    assert service.attachment_store.get(tid,copies[0]['document_id'])['body']==original
    status=client.get('/api/v1/asset-workspace/contexts/'+saved['context_id']).json()
    assert status['source_status'][0]['status']=='newer_version_available'
    assert status['refs']==[ref]
    workspace.library.set_access('local-pilot',project,'document',ref['version_id'],True)
    assert client.get('/api/v1/asset-workspace/contexts/'+saved['context_id']).json()['source_status'][0]['status']=='unavailable'
    assert client.post(endpoint,headers=WRITE,json={**draft,'asset_context_id':saved['context_id']}).status_code==409
    start=f'/api/v1/research-sessions/{tid}/start' if destination=='research' else f'/api/v1/conversations/{tid}/messages'
    response=client.post(start,headers=WRITE,**({'json':{'message':'Continue with this asset.'}} if destination=='conversation' else {}))
    assert response.status_code==409,response.text
    assert not any(c[0]=='run' for c in calls)


def test_contract_validation_conflicts_and_concurrent_revision(tmp_path):
    client, _, calls, _, workspace, project=setup(tmp_path)
    ref=selection(workspace,project)
    url='/api/v1/asset-workspace/contexts'
    valid={'schema_version':'asset_context.v1','question':'Check the original material before answering.','refs':[ref],'memory_version':0}
    for change,status in [({'schema_version':'asset_context.v2'},422),({'owner':'bob'},422),({'refs':[ref,ref]},422),
                          ({'refs':[{**ref,'digest':'0'*64}]},409),({'memory_version':1},409)]:
        assert client.post(url,headers=WRITE,json={**valid,**change}).status_code==status
    saved=context(client,ref)
    assert client.post('/api/v1/research-sessions',headers=WRITE,json={'mode':'research','defer_start':True,'asset_context_id':saved['context_id'],'question':'Different question'}).status_code==422
    assert client.post('/api/v1/research-sessions',headers=WRITE,json={'mode':'research','asset_context_id':saved['context_id']}).status_code==422
    assert not calls
    def edit(i):return client.post('/api/v1/asset-workspace/documents',headers=WRITE,json={'project_id':project,'base_ref':ref,'title':'Revision','text':f'New text {i}'})
    with ThreadPoolExecutor(2) as pool:results=list(pool.map(edit,range(2)))
    assert sorted(r.status_code for r in results)==[200,409]
    profile='/api/v1/asset-workspace/profile'
    assert client.put(profile,headers=WRITE,json={'version':0,'body':'My preference'}).json()['version']==1
    assert client.put(profile,headers=WRITE,json={'version':0,'body':'Stale preference'}).status_code==409
    assert client.get(profile).json()['body']=='My preference'
    assert client.put(profile,headers=WRITE,json={'version':1,'body':''}).json()=={'version':2,'body':''}


def test_owner_isolation_and_foreign_origin(tmp_path,monkeypatch):
    app=app_at(tmp_path,monkeypatch)
    app.include_router(build_asset_workspace_router(tmp_path),prefix='/api/v1')
    client=TestClient(app)
    client.put('/api/v1/projects',headers=AUTH_WRITE,json=index())
    client.post('/api/v1/asset-workspace/documents',headers=AUTH_WRITE,json={'project_id':PROJECT,'title':'Private','text':'Private evidence'})
    ref=client.get(f'/api/v1/asset-workspace/projects/{PROJECT}',headers=AUTH_WRITE).json()['items'][0]['current']['ref']
    body={'schema_version':'asset_context.v1','question':'Examine my private document carefully.','refs':[ref],'memory_version':0}
    saved=client.post('/api/v1/asset-workspace/contexts',headers=AUTH_WRITE,json=body).json()
    bob={**AUTH_WRITE,'Authorization':'Bearer bob'}
    for path in [f'/projects/{PROJECT}',f'/contexts/{saved["context_id"]}']:
        assert client.get('/api/v1/asset-workspace'+path,headers=bob).status_code==404
    assert client.post('/api/v1/asset-workspace/read',headers=bob,json=ref).status_code==404
    assert client.post('/api/v1/asset-workspace/contexts',headers=bob,json=body).status_code==404
    client.put('/api/v1/asset-workspace/profile',headers=AUTH_WRITE,json={'version':0,'body':'Alice private preference'})
    assert client.get('/api/v1/asset-workspace/profile',headers=bob).json()=={'version':0,'body':''}
    assert client.put('/api/v1/asset-workspace/profile',headers={**AUTH_WRITE,'Origin':'https://untrusted.example'},json={'version':1,'body':'Forged'}).status_code==403


@pytest.mark.parametrize('destination',['research','conversation'])
def test_copy_failure_keeps_native_draft_unrunnable(tmp_path,monkeypatch,destination):
    client, service, calls, tid, workspace, project=setup(tmp_path)
    saved=context(client,selection(workspace,project))
    def fail(*args):raise OSError('private-host-path')
    monkeypatch.setattr(service.attachment_store,'copy_project_materials',fail)
    endpoint='/api/v1/research-sessions' if destination=='research' else '/api/v1/conversations/drafts'
    draft={'mode':'research','defer_start':True} if destination=='research' else {}
    response=client.post(endpoint,headers=WRITE,json={**draft,'asset_context_id':saved['context_id']})
    assert response.status_code==409 and tid in response.text and 'private-host-path' not in response.text
    start=f'/api/v1/research-sessions/{tid}/start' if destination=='research' else f'/api/v1/conversations/{tid}/messages'
    assert client.post(start,headers=WRITE,**({'json':{'message':'Continue'}} if destination=='conversation' else {})).status_code==409
    assert not any(c[0]=='run' for c in calls)


def test_backup_restore_preserves_versions_profiles_contexts_and_sec_originals(tmp_path):
    client, _, _, _, workspace, project=setup(tmp_path)
    ref=selection(workspace,project)
    workspace.save_profile('local-pilot','Preserve my exact preference',0)
    saved=context(client,ref,1)
    client.post('/api/v1/asset-workspace/documents',headers=WRITE,json={'project_id':project,'base_ref':ref,'title':'New','text':'New content'})
    scope=workspace.library.scope('local-pilot',project);version=str(uuid4())
    folder=workspace.sec.root/scope/version/'raw'/'SYN';folder.mkdir(parents=True)
    sources=[]
    for kind in ['sec_companyfacts','sec_submissions']:
        raw=json.dumps({'facts':{}} if kind=='sec_companyfacts' else {'filings':{}}).encode()
        (folder/(kind+'.json')).write_bytes(raw)
        (folder/(kind+'.metadata.json')).write_text('{"synthetic":true}')
        sources.append({'kind':kind,'sha256':sha256(raw).hexdigest(),'url':'https://data.sec.gov/synthetic'})
    with workspace.library.documents.connect() as db:
        db.execute('INSERT INTO project_sec_versions VALUES(?,?,?)',(scope,version,json.dumps({'version':version,'cik':'0000000001','ticker':'SYN','status':'complete','requested_at':'2026-09-16','sources':sources})))
    manifest=backup_assets(workspace.library.documents.root,tmp_path/'backup')
    assert not manifest['native_threads_included'] and len(manifest['files'])==5
    restore_assets(tmp_path/'backup',tmp_path/'restored')
    restored=AssetWorkspace(tmp_path/'restored')
    assert restored.context('local-pilot',saved['context_id'])==saved
    assert restored.profile('local-pilot')=={'version':1,'body':'Preserve my exact preference'}
    assert restored.catalog('local-pilot',project)==workspace.catalog('local-pilot',project)
    sec_ref=next(a for a in restored.catalog('local-pilot',project)['items'] if a['kind']=='sec')['current']['ref']
    assert restored.read('local-pilot',sec_ref)['concept_total']==0
    with pytest.raises(KeyError):restored.context('bob',saved['context_id'])
    with pytest.raises(FileExistsError):restore_assets(tmp_path/'backup',tmp_path/'restored')
    (tmp_path/'backup'/'attachments.sqlite').write_bytes(b'corrupted')
    with pytest.raises(ValueError,match='integrity'):restore_assets(tmp_path/'backup',tmp_path/'bad-restore')
    assert not (tmp_path/'bad-restore').exists()


@pytest.mark.parametrize('destination',['research','conversation'])
def test_sec_context_reaches_actual_assistant_financial_tools(mapped_task,destination):
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
    from langgraph.checkpoint.memory import InMemorySaver
    from sec_agent.agent_runtime.conversation_agent import build_conversation_agent
    from sec_agent.agent_runtime.conversation_tools import conversation_tools
    from test_conversation_agent import ScriptedTools
    client,service,calls,tid,sec,project,version,_=mapped_task
    root=sec.library.documents.root
    client.app.include_router(build_asset_workspace_router(root),prefix='/api/v1')
    client.app.include_router(build_conversations_router(service),prefix='/api/v1')
    workspace=AssetWorkspace(root)
    saved=context(client,selection(workspace,project))
    endpoint='/api/v1/research-sessions' if destination=='research' else '/api/v1/conversations/drafts'
    body={'mode':'research','defer_start':True} if destination=='research' else {}
    response=client.post(endpoint,headers=WRITE,json={**body,'asset_context_id':saved['context_id']})
    assert response.status_code==200,response.text
    grants=conversation_tools(thread_id=tid,attachment_store=service.attachment_store)
    def model():return ScriptedTools(responses=[AIMessage(content='',tool_calls=[{'id':'read','name':'query_financial_data','type':'tool_call','args':{
        'ticker':'MSFT','fiscal_years':[2025],'research_as_of':'2025-07-31','granularity':'fiscal_year','metric_ids':['revenue','operating_income']}}]),AIMessage(content='Read synthetic financial data.')])
    agent=build_conversation_agent(model=model(),grants=grants,permission_mode='request_standard',checkpointer=InMemorySaver())
    result=agent.invoke({'messages':[HumanMessage(content='Read the selected snapshot.')]},{'configurable':{'thread_id':tid}})
    receipt=next(m for m in result['messages'] if isinstance(m,ToolMessage))
    assert receipt.status=='success'
    assert receipt.artifact['project_binding']['project_origin']['sec_version']==version
    facts=[fact for row in receipt.artifact['results'] for fact in row['facts']]
    assert [f['value_decimal'] for f in facts]==['120','30']
    assert all(f['project_origin']['sec_version']==version for f in facts)
    sec.library.set_access('local-pilot',project,'sec',version,True)
    # Revocation after constructing the agent must still block its existing tool.
    blocked=build_conversation_agent(model=model(),grants=grants,permission_mode='request_standard',checkpointer=InMemorySaver()).invoke(
        {'messages':[HumanMessage(content='Try again.')]},{'configurable':{'thread_id':tid}})
    assert next(m for m in blocked['messages'] if isinstance(m,ToolMessage)).status=='error'
    assert not any(c[0]=='run' for c in calls)
