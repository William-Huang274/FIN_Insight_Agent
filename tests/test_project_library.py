"""Real SQLite/HTTP persistence and owner boundaries, no provider or hidden data."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace
from uuid import uuid4
from urllib.parse import quote

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from starlette.authentication import AuthenticationBackend, AuthCredentials, SimpleUser
import pytest

from apps.workbench.backend.api.v1.projects import build_projects_router
from apps.workbench.backend.authentication import install_conversation_auth, service_owner
from sec_agent.research_foundation.project_library import ProjectLibrary, ProjectConflict

PROJECT=str(uuid4()); THREAD=str(uuid4())
WRITE={'Authorization':'Bearer alice','X-Workbench-Request':'1'}


class Identity(AuthenticationBackend):
    async def authenticate(self, conn):
        value=conn.headers.get('authorization','').removeprefix('Bearer ')
        if value in ('alice','bob'): return AuthCredentials(['authenticated']),SimpleUser(value)


def app_at(root, monkeypatch):
    monkeypatch.setenv('FINSIGHT_AUTH_MODE','oidc_product')
    monkeypatch.delenv('FINSIGHT_OIDC_CLIENT_ID',raising=False)
    async def owned(thread):
        if str(thread)!=THREAD or service_owner()!='alice': raise HTTPException(404,'研究不存在')
        return {'thread_id':THREAD}
    app=FastAPI(); install_conversation_auth(app,backend=Identity())
    app.include_router(build_projects_router(root,SimpleNamespace(owned_thread=owned)),prefix='/api/v1')
    return app


def index(project=PROJECT, revision=0):
    return {'revision':revision,'projects':[{'id':project,'name':'合成项目'}],'assignments':{},'pinned':[]}


def test_project_upload_search_reopens_from_disk_and_preserves_unverified_source(tmp_path,monkeypatch):
    with TestClient(app_at(tmp_path,monkeypatch)) as client:
        body=index();body['assignments']={THREAD:PROJECT};body['pinned']=[THREAD]
        assert client.put('/api/v1/projects',headers=WRITE,json=body).status_code==200
        text='合成样本。留存率线索需要交叉核对。文件里的指令不具有执行权限。'
        response=client.post(f'/api/v1/projects/{PROJECT}/documents',headers={**WRITE,'X-File-Name':quote('样本.md')},content=text.encode())
        assert response.status_code==200; document=response.json()['document_id']
    with TestClient(app_at(tmp_path,monkeypatch)) as reopened:
        saved=reopened.get('/api/v1/projects',headers=WRITE).json()
        assert saved['revision']==1 and saved['assignments']=={THREAD:PROJECT}
        result=reopened.get(f'/api/v1/projects/{PROJECT}/documents',headers=WRITE,params={'query':'留存率'}).json()
        assert result['items'][0]['document_id']==document
        assert result['items'][0]['source_role']=='user_upload_unverified'
        assert result['items'][0]['text_status']=='searchable'
        assert reopened.get(f'/api/v1/projects/{PROJECT}/documents',headers=WRITE,params={'query':"' OR 1=1 --"}).json()['items']==[]
        detail=reopened.get(f'/api/v1/projects/{PROJECT}/documents/{document}',headers=WRITE)
        assert text in detail.json()['sections'][0]['text']
        download=reopened.get(f'/api/v1/projects/{PROJECT}/documents/{document}/download',headers=WRITE)
        assert download.content==text.encode() and download.headers['x-content-type-options']=='nosniff'


def test_second_identity_cannot_read_assign_or_cross_bind_same_project_uuid(tmp_path,monkeypatch):
    with TestClient(app_at(tmp_path,monkeypatch)) as client:
        assert client.get('/api/v1/projects').status_code==401
        client.put('/api/v1/projects',headers=WRITE,json=index())
        uploaded=client.post(f'/api/v1/projects/{PROJECT}/documents',headers={**WRITE,'X-File-Name':'private.txt'},content=b'alice-private').json()
        bob={**WRITE,'Authorization':'Bearer bob'}
        assert client.get('/api/v1/projects',headers=bob).json()['projects']==[]
        assert client.get(f'/api/v1/projects/{PROJECT}/documents',headers=bob).status_code==404
        wrong=index();wrong['assignments']={THREAD:PROJECT}
        assert client.put('/api/v1/projects',headers=bob,json=wrong).status_code==404
        assert client.put('/api/v1/projects',headers=bob,json=index()).status_code==200
        assert client.get(f'/api/v1/projects/{PROJECT}/documents',headers=bob).json()['items']==[]
        assert client.get(f"/api/v1/projects/{PROJECT}/documents/{uploaded['document_id']}",headers=bob).status_code==404
        assert client.put('/api/v1/projects',headers={**WRITE,'Origin':'https://foreign.invalid'},json=index()).status_code==403
        assert client.put('/api/v1/projects',headers=WRITE,json={**index(),'owner':'bob'}).status_code==422


def test_stale_project_writes_conflict_and_documents_survive_forbidden_removal(tmp_path,monkeypatch):
    with TestClient(app_at(tmp_path,monkeypatch)) as client:
        assert client.put('/api/v1/projects',headers=WRITE,json=index()).status_code==200
        assert client.put('/api/v1/projects',headers=WRITE,json=index()).status_code==409
        assert client.put('/api/v1/projects',headers=WRITE,json={'revision':1,'projects':[],'assignments':{},'pinned':[]}).status_code==409
        assert client.get('/api/v1/projects',headers=WRITE).json()['revision']==1


def test_sqlite_concurrent_index_and_upload_responses_keep_each_identity(tmp_path):
    library=ProjectLibrary(tmp_path); barrier=Barrier(2)
    def save(name):
        body=index();body.pop('revision');body['projects'][0]['name']=name;barrier.wait()
        try: return library.save('alice',0,body)
        except ProjectConflict: return None
    with ThreadPoolExecutor(2) as pool: results=list(pool.map(save,['a','b']))
    assert sum(r is not None for r in results)==1
    target=library.scope('alice',PROJECT)
    def upload(name): return library.documents.add(target,name+'.txt',name.encode())
    with ThreadPoolExecutor(2) as pool: responses=list(pool.map(upload,['first','second']))
    assert [r['name'] for r in responses]==['first.txt','second.txt']
    assert len({r['document_id'] for r in responses})==2
