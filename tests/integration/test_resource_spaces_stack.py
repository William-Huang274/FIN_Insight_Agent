"""Real signed BFF -> Spring/PostgreSQL authority plus organization SQLite custody.

Login principals are synthetic. Requires explicit built JAR and Docker; no models.
"""
import os
import asyncio
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
from apps.workbench.backend.business_transport import space_business_request
from sec_agent.research_foundation.organization_execution_access import (
    OrganizationExecutionAuthority, OrganizationExecutionReader, OrganizationExecutionUnavailable,
    build_organization_evidence_server,
)
from sec_agent.research_foundation.asset_workspace import AssetWorkspace

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
            'FINSIGHT_ORGANIZATION_RUNTIME_SECRET':secrets.token_urlsafe(48),
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
            # The project authority is Java only; no Python project-index or assets are copied.
            project = str(uuid4())
            config = client.get('/api/v1/business/config', headers=WRITE).json()
            assert config['organization_projects'] and not config['team_collaboration']
            create_project = {'id':project,'organization_id':org,'name':'Synthetic team project','description':'No model calls'}
            api('POST','/projects',create_project)
            api('GET',f'/projects/{project}',headers=bob,status=404)
            api('POST',f'/projects/{project}/members',{'revision':1,'subject':'bob','role':'researcher'})
            assert api('GET',f'/projects/{project}',headers=bob)['role']=='researcher'
            assert all(p['id']!=project for p in client.get('/api/v1/projects',headers=WRITE).json()['projects'])
            # Ordinary private project routes do not turn organization membership into asset access.
            assert client.get(f'/api/v1/asset-workspace/projects/{project}',headers=bob).status_code==404
            for action in ('start','prepare','access'):
                api('POST',f'/projects/{project}/{action}',{},status=404)
            assert client.post('/api/v1/business/workspaces/projects',headers={**WRITE,'Origin':'https://foreign.invalid'},json=create_project).status_code==403
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
            # Real BFF signatures and Java membership checks govern both project catalog and content.
            project_read=f'/api/v1/asset-workspace/organization-projects/{project}/resources/{resource}'
            assert client.get(project_read,headers=bob).status_code==404
            api('POST',f'/projects/{project}/resources/{resource}',{'revision':2,'linked':True},headers=bob,status=403)
            api('POST',f'/projects/{project}/resources/{resource}',{'revision':2,'linked':True})
            assert api('GET',f'/projects/{project}/resources',headers=bob)['items'][0]['id']==resource
            assert api('GET',f'/spaces/{team}/resources?project_id={project}',headers=bob)['items'][0]['id']==resource
            assert client.get(project_read,headers=bob).json()['text']=='Organization keeps this after author departure.'
            api('POST',f'/projects/{project}/resources/{resource}/access',{},status=404)
            api('POST',f'/spaces/{team}/members',{'subject':'bob','role':'remove'})
            assert api('GET',f'/projects/{project}/resources',headers=bob)['items']==[]
            assert client.get(project_read,headers=bob).status_code==404
            api('POST',f'/spaces/{team}/members',{'subject':'bob','role':'manager'})
            read=f'/api/v1/asset-workspace/spaces/resources/{resource}'
            assert client.get(read,headers=WRITE).json()['text']=='Organization keeps this after author departure.'
            draft = str(uuid4())
            preparation = {'id':draft,'title':'Synthetic immutable preparation',
                'question':'Verify the stored evidence version without creating an Agent run.',
                'research_as_of':'2026-10-12','resource_ids':[resource]}
            drafts = f'/projects/{project}/research-drafts'
            prepared = api('POST',drafts,preparation,headers=bob)
            assert api('POST',drafts,preparation,headers=bob) == prepared
            assert prepared['execution_enabled'] is False
            assert not {'thread_id','run_id','binding'} & prepared.keys()
            verify = f'/api/v1/asset-workspace/organization-projects/{project}/research-drafts/{draft}/verify'
            checked = client.post(verify,headers=bob,json={})
            assert checked.status_code == 200,checked.text
            assert checked.json()['manifest_digest'] == prepared['manifest_digest']
            assert checked.json()['status'] == 'inputs_verified'
            api('POST',drafts+f'/{draft}/material-access',{},status=404)
            # Internal server binding only. Browser cannot register a native identity.
            execution_id, admin_execution = str(uuid4()), str(uuid4())
            binding_path=f'projects/{project}/research-drafts/{draft}/execution-bindings'
            binding_body={'id':execution_id,'manifest_digest':prepared['manifest_digest']}
            api('POST','/'+binding_path,binding_body,headers=bob,status=404)
            bound=asyncio.run(space_business_request('bob','POST',binding_path,binding_body))
            assert bound['thread_id']==execution_id and bound['native_execution_enabled'] is False
            assert asyncio.run(space_business_request('bob','POST',binding_path,binding_body))==bound
            asyncio.run(space_business_request('alice','POST',binding_path,{**binding_body,'id':admin_execution}))
            def runtime(identifier):
                authority=OrganizationExecutionAuthority(base_url=f'http://127.0.0.1:{java_port}',
                    secret=os.environ['FINSIGHT_ORGANIZATION_RUNTIME_SECRET'],execution_id=identifier,
                    manifest_digest=prepared['manifest_digest'])
                return OrganizationExecutionReader(AssetWorkspace(tmp_path/'project-library'/'organization-assets'),authority)
            bob_reader,admin_reader=runtime(execution_id),runtime(admin_execution)
            async def read_mcp(reader):
                from mcp import Client
                async with Client(build_organization_evidence_server(reader),raise_exceptions=False) as tools:
                    return await tools.call_tool('read_organization_evidence',{'resource_id':resource})
            tool_result=asyncio.run(read_mcp(bob_reader))
            assert not tool_result.is_error,tool_result
            assert tool_result.structured_content['text']=='Organization keeps this after author departure.'
            from sec_agent.research_foundation.organization_source_navigation import OrganizationSourceNavigation, build_organization_source_server
            bob_navigation = OrganizationSourceNavigation(bob_reader, workbench_url='http://testserver')
            async def read_original(navigation):
                from mcp import Client
                async with Client(build_organization_source_server(navigation), raise_exceptions=False) as tools:
                    catalog = await tools.call_tool('read_source_document', {'request': {'source_space':'organization','operation':'catalog'}})
                    assert not catalog.is_error, catalog
                    result = await tools.call_tool('read_source_document', {'request': {'source_space':'organization','operation':'read',
                        'document_id':catalog.structured_content['items'][0]['document_id']}})
                    assert not result.is_error, result
                    return result.structured_content['items'][0]
            citation = asyncio.run(read_original(bob_navigation))
            assert citation['passage']=='Organization keeps this after author departure.'
            assert citation['organization_source']['ref']==prepared['manifest']['inputs'][0]['ref']
            # Original private file withdrawal does not retract explicit publication.
            source.library.set_access('bob',bob_ref['project_id'],'document',bob_ref['version_id'],True)
            api('POST',f'/organizations/{org}/remove-member',{'subject':'bob'})
            api('GET',f'/projects/{project}',headers=bob,status=404)
            api('GET',f'/projects/{project}/members',headers=bob,status=404)
            api('GET',drafts+f'/{draft}',headers=bob,status=404)
            assert client.post(verify,headers=bob,json={}).status_code == 404
            assert api('GET',drafts+f'/{draft}') == prepared
            assert api('GET','/projects',headers=bob)['items']==[]
            assert client.get(read,headers=bob).status_code==404
            assert client.get(read,headers=WRITE).status_code==200
            assert asyncio.run(read_mcp(bob_reader)).is_error
            with pytest.raises(OrganizationExecutionUnavailable): bob_navigation.source(citation['passage_id'])
            assert not asyncio.run(read_mcp(admin_reader)).is_error
            api('POST','/resources',{},status=404) # binding registration is BFF-only
        business.terminate();business.wait(timeout=20);business=start()
        # The same reader object obtains fresh Java authority after process restart.
        assert admin_reader.read_text(resource)['text']=='Organization keeps this after author departure.'
        admin_navigation = OrganizationSourceNavigation(admin_reader, workbench_url='http://testserver')
        admin_citation = asyncio.run(read_original(admin_navigation))
        with pytest.raises(OrganizationExecutionUnavailable): bob_reader.check()
        with TestClient(app()) as client:
            saved=client.get(f'/api/v1/business/workspaces/projects/{project}',headers=WRITE)
            assert saved.status_code==200 and saved.json()['revision']==3
            assert client.get(f'/api/v1/business/workspaces/projects/{project}',headers=bob).status_code==404
            assert client.post('/api/v1/business/workspaces/projects',headers=WRITE,json=create_project).json()['revision']==3
            assert client.get(project_read,headers=WRITE).status_code==200
            assert client.get(project_read,headers=bob).status_code==404
            assert client.get('/api/v1/business/workspaces'+drafts+f'/{draft}',headers=WRITE).json() == prepared
            checked = client.post(verify,headers=WRITE,json={})
            assert checked.status_code == 200,checked.text
            assert checked.json()['manifest_digest'] == prepared['manifest_digest']
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
            assert client.get(project_read,headers=WRITE).status_code==404
            assert client.get('/api/v1/business/workspaces'+drafts+f'/{draft}',headers=WRITE).status_code == 404
            assert client.post(verify,headers=WRITE,json={}).status_code == 404
            with pytest.raises(OrganizationExecutionUnavailable): admin_reader.read_text(resource)
            with pytest.raises(OrganizationExecutionUnavailable): admin_navigation.source(admin_citation['passage_id'])
            closed=asyncio.run(space_business_request('alice','POST',f'projects/{project}/execution-bindings/{admin_execution}/close'))
            assert closed['status']=='closed'
            assert client.get(f'/api/v1/business/workspaces/projects/{project}/resources',headers=WRITE).json()['items']==[]
            assert client.get(f'/api/v1/business/workspaces/spaces/{team}/resources',headers=WRITE).json()['items']==[]
    finally:
        for process in processes:
            if process.poll() is None: process.terminate();process.wait(timeout=20)
        for log in logs: log.close()
        if container:
            assert run(['inspect','--format','{{index .Config.Labels "finsight.qualification"}}',container])=='resource-spaces'
            run(['rm','-f',container])
