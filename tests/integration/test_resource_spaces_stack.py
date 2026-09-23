"""Real signed BFF -> Spring/PostgreSQL authority plus organization SQLite custody.

Login principals are synthetic. Requires explicit built JAR and Docker; no models.
"""
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import time
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from apps.workbench.backend.api.v1.asset_workspace import build_asset_workspace_router
from apps.workbench.backend.business_transport import build_business_gateway
from test_project_library import app_at, WRITE
from test_resource_spaces import source_at
from tests.integration.test_java_intake_stack import port, ready

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.skipif(not os.environ.get('FINSIGHT_INTAKE_TEST_JAR'), reason='explicit built Java intake JAR required')


def test_real_space_publication_grants_revocation_and_restart(tmp_path, monkeypatch):
    docker = os.environ.get('FINSIGHT_TEST_DOCKER') or shutil.which('docker')
    java = os.environ.get('FINSIGHT_TEST_JAVA') or shutil.which('java')
    assert docker and java
    jar = Path(os.environ['FINSIGHT_INTAKE_TEST_JAR']).resolve(); assert jar.is_file()
    processes, logs, container = [], [], None
    def run(args): return subprocess.check_output([docker,*args],text=True,stderr=subprocess.STDOUT).strip()
    try:
        password = secrets.token_urlsafe(24)
        container = run(['run','--rm','-d','--label','finsight.qualification=resource-spaces',
            '-e','POSTGRES_PASSWORD='+password,'-p','127.0.0.1::5432','postgres:16.15-alpine'])
        pg_port = run(['port',container,'5432/tcp']).rsplit(':',1)[1]
        deadline = time.monotonic()+30
        while subprocess.run([docker,'exec',container,'pg_isready','-U','postgres'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode:
            assert time.monotonic()<deadline; time.sleep(.3)
        java_port = port()
        for key,value in {'FINSIGHT_RESOURCE_SPACES_ENABLED':'1','FINSIGHT_AUTH_MODE':'oidc_product',
            'FINSIGHT_BUSINESS_SHARED_SECRET':secrets.token_urlsafe(48),
            'FINSIGHT_BUSINESS_API_URL':f'http://127.0.0.1:{java_port}'}.items(): monkeypatch.setenv(key,value)
        env = {**os.environ,'FINSIGHT_BUSINESS_PORT':str(java_port),
            'FINSIGHT_BUSINESS_JDBC_URL':f'jdbc:postgresql://127.0.0.1:{pg_port}/postgres',
            'FINSIGHT_BUSINESS_DB_USER':'postgres','FINSIGHT_BUSINESS_DB_PASSWORD':password,
            'FINSIGHT_PYTHON_INTAKE_URL':'http://127.0.0.1:9'}
        def start():
            log=(tmp_path/f'business-{len(logs)}.log').open('w',encoding='utf-8'); logs.append(log)
            p=subprocess.Popen([java,'-jar',str(jar)],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT); processes.append(p)
            ready(f'http://127.0.0.1:{java_port}/v1/workspaces',p); return p
        business = start()
        source, ref = source_at(tmp_path/'project-library')
        def app():
            application=app_at(tmp_path/'project-library',monkeypatch)
            application.include_router(build_asset_workspace_router(tmp_path/'project-library'),prefix='/api/v1')
            application.include_router(build_business_gateway(),prefix='/api/v1')
            return application
        org, team, invite, resource = [str(uuid4()) for _ in range(4)]
        bob={**WRITE,'Authorization':'Bearer bob'}
        with TestClient(app()) as client:
            def api(method,path,body=None,headers=WRITE,status=200):
                response=client.request(method,'/api/v1/business/workspaces'+path,headers=headers,**({'json':body} if body is not None else {}))
                assert response.status_code==status,response.text
                return response.json()
            created=api('POST','/organizations',{'id':org,'name':'Synthetic organization','display_name':'Alice'})
            personal=created['spaces'][0]['id']
            api('POST',f'/organizations/{org}/invites',{'token':invite})
            joined=api('POST','/join',{'token':invite,'display_name':'Bob'},headers=bob)
            assert all(s['id']!=personal for s in joined['spaces'])
            api('POST','/spaces',{'id':team,'organization_id':org,'name':'Research team'})
            api('GET',f'/spaces/{team}/resources',headers=bob,status=404)
            api('POST',f'/spaces/{team}/members',{'subject':'bob','role':'manager'})
            # Bob owns a separate original and publishes it to organization custody.
            source.library.save('bob',0,{'projects':[{'id':ref['project_id'],'name':'Bob private project'}],'assignments':{},'pinned':[]})
            source.library.documents.add(source.library.scope('bob',ref['project_id']),'Bob.md',b'Organization keeps this after author departure.')
            bob_ref=source.catalog('bob',ref['project_id'])['items'][0]['current']['ref']
            publication={'id':resource,'space_id':team,'ref':bob_ref}
            endpoint='/api/v1/asset-workspace/spaces/publish'
            first=client.post(endpoint,headers=bob,json=publication)
            assert first.status_code==200,first.text
            assert client.post(endpoint,headers=bob,json=publication).json()==first.json()
            rows=api('GET',f'/spaces/{team}/resources')['items']
            assert len(rows)==1 and 'binding' not in rows[0]
            assert api('GET',f'/spaces/{team}/resources?type=database')['items']==[]
            assert api('GET',f'/spaces/{team}/resources?query=%25')['items']==[]
            read=f'/api/v1/asset-workspace/spaces/resources/{resource}'
            assert client.get(read,headers=WRITE).json()['text']=='Organization keeps this after author departure.'
            # Original private file withdrawal does not retract explicit publication.
            source.library.set_access('bob',bob_ref['project_id'],'document',bob_ref['version_id'],True)
            api('POST',f'/organizations/{org}/remove-member',{'subject':'bob'})
            assert client.get(read,headers=bob).status_code==404
            assert client.get(read,headers=WRITE).status_code==200
            api('POST','/resources',{},status=404) # binding registration is BFF-only
        business.terminate();business.wait(timeout=20);business=start()
        with TestClient(app()) as client:
            result=client.get(read,headers=WRITE)
            assert result.status_code==200,result.text
            assert result.json()['text']=='Organization keeps this after author departure.'
            assert result.headers['cache-control']=='no-store'
            denied=client.post('/api/v1/asset-workspace/read',headers=WRITE,json=result.json()['version']['ref'])
            assert denied.status_code==404 # cannot bypass Java with ordinary owner APIs
            response=client.post(f'/api/v1/business/workspaces/resources/{resource}/revoke',headers=WRITE,json={'revision':result.json()['permission_revision']})
            assert response.status_code==200,response.text
            assert client.get(read,headers=WRITE).status_code==404
            assert client.get(read,headers=bob).status_code==404
            assert client.get(f'/api/v1/business/workspaces/spaces/{team}/resources',headers=WRITE).json()['items']==[]
    finally:
        for process in processes:
            if process.poll() is None: process.terminate();process.wait(timeout=20)
        for log in logs: log.close()
        if container:
            assert run(['inspect','--format','{{index .Config.Labels "finsight.qualification"}}',container])=='resource-spaces'
            run(['rm','-f',container])
