"""Project organization and owner-scoped catalogue; real SQLite, no model calls."""
from uuid import uuid4

from fastapi.testclient import TestClient

from apps.workbench.backend.api.v1.asset_workspace import build_asset_workspace_router
from sec_agent.research_foundation.asset_workspace import AssetWorkspace
from test_project_library import app_at, index, PROJECT, WRITE


def test_project_settings_persist_legacy_clients_preserve_metadata_and_conflicts(tmp_path, monkeypatch):
    with TestClient(app_at(tmp_path,monkeypatch)) as client:
        body=index()
        body['projects'][0].update(description='资本开支与现金流',archived=True)
        assert client.put('/api/v1/projects',headers=WRITE,json=body).status_code==200
        legacy=index(revision=1)
        legacy['projects'][0]['name']='修改名称'
        result=client.put('/api/v1/projects',headers=WRITE,json=legacy)
        assert result.status_code==200
        assert result.json()['projects'][0]=={'id':PROJECT,'name':'修改名称','description':'资本开支与现金流','archived':True}
        assert client.put('/api/v1/projects',headers=WRITE,json=legacy).status_code==409
    with TestClient(app_at(tmp_path,monkeypatch)) as client:
        saved=client.get('/api/v1/projects',headers=WRITE).json()
        saved['projects'][0]['archived']=False
        assert client.put('/api/v1/projects',headers=WRITE,json=saved).json()['projects'][0]['archived'] is False
        assert client.get('/api/v1/projects',headers={**WRITE,'Authorization':'Bearer bob'}).json()['projects']==[]


def test_global_catalog_pagination_filter_identity_and_readback(tmp_path,monkeypatch):
    app=app_at(tmp_path,monkeypatch)
    app.include_router(build_asset_workspace_router(tmp_path),prefix='/api/v1')
    workspace=AssetWorkspace(tmp_path)
    second=str(uuid4())
    body=index();body['projects'].append({'id':second,'name':'同名资料的另一个项目','archived':True})
    with TestClient(app) as client:
        assert client.put('/api/v1/projects',headers=WRITE,json=body).status_code==200
        refs=[]
        for project in (PROJECT,second):
            scope=workspace.library.scope('alice',project)
            first=workspace.library.documents.add(scope,'shared-title.md',b'original text')
            workspace.library.documents.add(scope,'other.md',b'other text')
            workspace.library.documents.add(scope,'shared-title.md',b'revised text',revision={'parent':first['document_id'],'change_kind':'correction','note':'user edit'})
            refs.append(workspace.catalog('alice',project)['items'][0]['current']['ref'])
        endpoint='/api/v1/asset-workspace/catalog'
        first=client.get(endpoint,headers=WRITE,params={'limit':2})
        assert first.headers['cache-control']=='no-store'
        assert first.json()['next_offset']==2
        last=client.get(endpoint,headers=WRITE,params={'offset':2,'limit':2}).json()
        assert last['next_offset'] is None
        rows=first.json()['items']+last['items']
        assert len(rows)==4  # Version families, not six immutable versions.
        assert len({(r['project_id'],r['asset_id']) for r in rows})==4
        found=client.get(endpoint,headers=WRITE,params={'project_id':second,'query':'SHARED','role':'document'}).json()['items']
        assert len(found)==1 and found[0]['current']['sequence']==2
        assert found[0]['project_archived'] is True
        assert found[0]['current']['ref']==refs[1]
        assert client.post('/api/v1/asset-workspace/read',headers=WRITE,json=refs[1]).json()['text']=='revised text'
        assert client.get(endpoint,headers=WRITE,params={'project_id':str(uuid4())}).status_code==404
        assert client.get(endpoint,headers=WRITE,params={'limit':101}).status_code==422
        assert client.get(endpoint,headers=WRITE,params={'role':'invalid'}).status_code==422
        assert client.get(endpoint,headers=WRITE,params={'query':"' OR 1=1 --"}).json()['items']==[]
        bob={**WRITE,'Authorization':'Bearer bob'}
        assert client.get(endpoint,headers=bob).json()['items']==[]
        assert client.get(endpoint,headers=bob,params={'project_id':PROJECT}).status_code==404
        assert client.post('/api/v1/asset-workspace/read',headers=bob,json=refs[0]).status_code==404
        assert client.get(endpoint).status_code==401
        workspace.library.set_access('alice',second,'document',refs[1]['version_id'],True)
        assert client.post('/api/v1/asset-workspace/read',headers=WRITE,json=refs[1]).status_code==409
