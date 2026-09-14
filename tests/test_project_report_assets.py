"""Project report exports retain native versions and do not become source facts."""
from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4
import asyncio

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest

from apps.workbench.backend.api.v1.projects import build_projects_router
from apps.workbench.backend.authentication import install_conversation_auth, service_owner
from sec_agent.agent_runtime.targeted_revision import report_digest
from sec_agent.research_foundation.project_library import ProjectLibrary
from sec_agent.research_foundation.task_attachments import TaskAttachmentStore
from sec_agent.research_foundation.source_document_navigation import SourceDocumentRequest
from test_project_library import Identity, WRITE, PROJECT, THREAD, index


@pytest.fixture
def prepared(tmp_path,monkeypatch):
    monkeypatch.setenv('FINSIGHT_AUTH_MODE','oidc_product')
    monkeypatch.delenv('FINSIGHT_OIDC_CLIENT_ID',raising=False)
    report={'title':'合成成果','narrative_markdown':'旧版判断：合成线索仍待核验。','citations':{},'charts':[]}
    state={'checkpoint':{'checkpoint_id':str(uuid4())},'next':['human_review'],
           'values':{'report':report,'report_version':1,'phase':'needs_revision','private_messages':'PRIVATE_NOT_FOR_EXPORT'}}
    async def owned(thread):
        if str(thread)!=THREAD or service_owner()!='alice':raise HTTPException(404,'研究不存在')
    async def report_state(thread,checkpoint=None):
        await owned(thread)
        return deepcopy(state)
    app=FastAPI();install_conversation_auth(app,backend=Identity())
    app.include_router(build_projects_router(tmp_path,SimpleNamespace(owned_thread=owned,report_state=report_state,
        attachment_store=TaskAttachmentStore(tmp_path/'attachments'))),prefix='/api/v1')
    client=TestClient(app)
    assert client.put('/api/v1/projects',headers=WRITE,json=index()).status_code==200
    return client,state,ProjectLibrary(tmp_path)


def save(client,state,**changes):
    return client.post(f'/api/v1/projects/{PROJECT}/reports',headers=WRITE,json={
        'thread_id':THREAD,'report_digest':report_digest(state['values']['report']),**changes})


def test_saved_versions_search_and_task_copy_keep_report_authority(prepared,tmp_path):
    client,state,library=prepared
    first=save(client,state);assert first.status_code==200,first.text
    assert first.json()['search_status']=='saved_text_searchable'
    assert save(client,state).json()['document_id']==first.json()['document_id']
    old=library.documents.get(library.scope('alice',PROJECT),first.json()['document_id'])
    state['values'].update(report_version=2,phase='human_completed',report_revision_reason='人工修改：撤回归因',human_edits=[{'number':1}])
    state['values']['report']['narrative_markdown']='新版判断：仅保留观察，不作因果归因。'
    state['checkpoint']['checkpoint_id']=str(uuid4())
    second=save(client,state);assert second.status_code==200,second.text
    assert second.json()['document_id']!=first.json()['document_id']
    reopened=ProjectLibrary(library.documents.root)
    assert len(reopened.search('alice',PROJECT)['items'])==2
    latest=reopened.search('alice',PROJECT,'不作因果')['items']
    assert len(latest)==1 and latest[0]['source_role']=='project_research_artifact'
    origin=latest[0]['project_origin']['research_origin']
    assert origin['report_version']==2 and origin['human_edit_count']==1
    assert 'PRIVATE_NOT_FOR_EXPORT' not in client.get(f"/api/v1/projects/{PROJECT}/documents/{second.json()['document_id']}/download",headers=WRITE).text
    assert reopened.documents.get(library.scope('alice',PROJECT),first.json()['document_id'])['body']==old['body']
    task=TaskAttachmentStore(tmp_path/'new-task');tid=str(uuid4())
    row=reopened.documents.get(library.scope('alice',PROJECT),second.json()['document_id'])
    selected=task.copy_project_materials(tid,PROJECT,[row])
    read=asyncio.run(task.read(thread_id=tid,request=SourceDocumentRequest(source_space='uploads',operation='read',document_id=selected[0]['document_id'])))
    passages=[i for i in read.items if i.get('passage')]
    assert passages and all(i['source_role']=='project_research_artifact' and not i['numeric_fact_authority'] for i in passages)
    assert all(i['project_origin']['research_origin']==origin for i in passages)
    assert '不作因果' in str(read) and '旧版判断' not in str(read)


def test_stale_incomplete_forged_and_foreign_snapshot_are_rejected(prepared):
    client,state,library=prepared
    assert save(client,state,report_digest='0'*64).status_code==409
    assert save(client,state,thread_id=str(uuid4())).status_code==404
    assert save(client,state,report={'narrative_markdown':'forged'}).status_code==422
    bob={**WRITE,'Authorization':'Bearer bob'}
    assert client.put('/api/v1/projects',headers=bob,json=index()).status_code==200
    assert client.post(f'/api/v1/projects/{PROJECT}/reports',headers=bob,json={'thread_id':THREAD,'report_digest':report_digest(state['values']['report'])}).status_code==404
    state['next']=['verifier']
    assert save(client,state).status_code==409
    assert library.search('alice',PROJECT)['items']==[]


def test_parse_failure_leaves_no_success_or_partial_asset(prepared,monkeypatch):
    client,state,library=prepared
    from sec_agent.research_foundation import task_attachments
    def fail(*args):raise ValueError('synthetic_parse_failure')
    monkeypatch.setattr(task_attachments,'parse_document',fail)
    assert save(client,state).status_code==422
    assert library.search('alice',PROJECT)['items']==[]


def test_confirmation_only_change_is_not_deduplicated_into_unreviewed_snapshot(prepared):
    client,state,library=prepared
    draft=save(client,state).json()
    state['values']['phase']='human_reviewed_not_released'
    state['checkpoint']['checkpoint_id']=str(uuid4())
    confirmed=save(client,state).json()
    assert confirmed['document_id']!=draft['document_id']
    assert confirmed['project_origin']['research_origin']['phase']=='human_reviewed_not_released'
    assert save(client,state).json()['document_id']==confirmed['document_id']
    assert len(library.search('alice',PROJECT)['items'])==2
