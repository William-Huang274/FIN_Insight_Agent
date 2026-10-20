"""Historical cards selected/saved/published/linked by real browser, BFF and Java."""
import json
import asyncio
import os
from pathlib import Path
import shutil
import subprocess
from uuid import uuid4

import psycopg
import httpx
import pytest

from sec_agent.research_foundation.asset_workspace import AssetWorkspace
from sec_agent.research_foundation.research_library import open_library
from apps.workbench.backend.business_transport import delegate
from sec_agent.research_foundation.organization_execution_access import (
    OrganizationExecutionAuthority, OrganizationExecutionReader, OrganizationExecutionUnavailable,
    build_organization_evidence_server)
from sec_agent.research_foundation.organization_source_navigation import OrganizationSourceNavigation
from tests.integration.test_organization_graph_native import OrganizationGraphStack, ROOT
from tests.integration.test_java_intake_native import wait_for

pytestmark = pytest.mark.skipif(os.getenv('FIN_METRIC_BROWSER_QUALIFICATION') != '1',
    reason='explicit isolated historical browser qualification required')


def test_metric_cards_browser_publication_and_current_permissions(monkeypatch):
    spec = json.loads(Path(os.environ['FIN_STRUCTURED_SQL_CASES']).read_text(encoding='utf8'))
    library = Path(os.environ['FIN_METRIC_PUBLIC_LIBRARY'])
    assert open_library(library).manifest['sha256'] == spec['library_sha256']
    s = OrganizationGraphStack()
    monkeypatch.setenv('FINSIGHT_BUSINESS_SHARED_SECRET', s.shared)
    s.env['FINSIGHT_RESEARCH_LIBRARY_PATH'] = str(library)
    private, org, space, project = [str(uuid4()) for _ in range(4)]
    def api(method, path, body=None):
        return s.request(s.bff, method, '/api/v1/business/workspaces'+path,
                         **({'json':body} if body is not None else {}))
    try:
        s.compose('up', '-d', '--pull', 'never', 'postgres')
        def ready():
            try:
                with psycopg.connect(host='127.0.0.1', port=s.pg_port, dbname='probe',
                                     user='probe', password=s.password, connect_timeout=2):
                    return True
            except psycopg.OperationalError:
                return False
        wait_for(ready)
        with psycopg.connect(host='127.0.0.1', port=s.pg_port, dbname='probe',
                             user='probe', password=s.password, autocommit=True) as db:
            db.execute('CREATE DATABASE business')
        s.boot('java')
        s.boot('bff')
        assets = AssetWorkspace(s.state/'project-library')
        assets.library.save('oidc:alice', 0, {'projects':[{'id':private,'name':'历史指标选取'}],
                                              'assignments':{}, 'pinned':[]})
        api('POST', '/organizations', {'id':org,'name':'数据卡验收组织','display_name':'Alice'})
        api('POST', '/spaces', {'id':space,'organization_id':org,'name':'团队指标资料'})
        api('POST', '/projects', {'id':project,'organization_id':org,'name':'历史经营指标核对','description':'旧 case，无模型调用'})
        output = s.output/'browser'
        env = {k:v for k,v in s.env.items() if k != 'LANGSMITH_API_KEY'}
        env.update(FIN_METRIC_BROWSER_ORIGIN=f'http://127.0.0.1:{s.bff_port}',
                   FIN_METRIC_BROWSER_OUTPUT=str(output), FIN_METRIC_PRIVATE_PROJECT=private,
                   FIN_METRIC_TEAM_PROJECT=project, FIN_METRIC_SPACE=space)
        node = os.getenv('FINSIGHT_TEST_NODE') or shutil.which('node')
        assert node
        run = subprocess.run([node,'e2e/metric-card-live.mjs'], cwd=ROOT/'apps/workbench/frontend',
                             env=env, capture_output=True, text=True, encoding='utf8', errors='replace', timeout=480)
        s.save('browser-process', {'returncode':run.returncode,'stdout':run.stdout,'stderr':run.stderr})
        assert run.returncode == 0, run.stderr[-5000:]
        result = json.loads((output/'result.json').read_text(encoding='utf8'))
        assert len(result['results']) == 4
        if os.getenv('FIN_METRIC_PUBLICATION_REPLY_LOSS') == '1':
            assert len(result['recoveries']) == 1
            recovery = result['recoveries'][0]
            assert recovery['query_without_resubmit'] and recovery['reload_preserved']
            with psycopg.connect(host='127.0.0.1', port=s.pg_port, dbname='business',
                                 user='probe', password=s.password) as db:
                assert db.execute("SELECT count(*) FROM space_resource WHERE space_id=%s",
                                  (space,)).fetchone()[0] == 4
                assert db.execute("SELECT count(*) FROM resource_space_audit WHERE action='resource_publish' AND target=%s",
                                  (recovery['resource_id'],)).fetchone()[0] == 1
        readers = []
        for draft in result['drafts']:
            execution = str(uuid4())
            path = f"/v1/workspaces/projects/{project}/research-drafts/{draft['id']}/execution-bindings"
            body = json.dumps({'id':execution,'manifest_digest':draft['manifest_digest']},separators=(',',':')).encode()
            with httpx.Client(trust_env=False) as client:
                bound = client.post(f'http://127.0.0.1:{s.java_port}'+path, content=body,
                    headers={'Content-Type':'application/json','Authorization':'Bearer '+delegate('oidc:alice','POST',path,body)})
                assert bound.status_code == 200, bound.text
            reader = OrganizationExecutionReader(AssetWorkspace(s.state/'project-library'/'organization-assets'),
                OrganizationExecutionAuthority(base_url=f'http://127.0.0.1:{s.java_port}',
                    secret=s.runtime_secret, execution_id=execution, manifest_digest=draft['manifest_digest']))
            readers.append(reader)
            if draft['verification_status'] == 409:
                for item in result['results']:
                    with pytest.raises(OrganizationExecutionUnavailable):
                        reader.read_rows(item['resource_id'])
                    with pytest.raises(OrganizationExecutionUnavailable):
                        reader.read_text(item['resource_id'])
                continue
            navigation = OrganizationSourceNavigation(reader,workbench_url=f'http://127.0.0.1:{s.bff_port}')
            catalog = reader.catalog()
            for item in result['results']:
                expected = next(r for c in spec['cases'] for r in c['snapshot']['rows'] if r['id']==item['record_id'])
                assert reader.read_rows(item['resource_id'])['rows'] == [expected]
                assert expected['id'] in reader.read_text(item['resource_id'],limit=16000)['text']
                selected = next(i for i in catalog['items'] if i['resource_id']==item['resource_id'])
                original = navigation.navigate({'source_space':'organization','operation':'read',
                    'document_id':navigation._identity(selected),'limit':20})
                assert any(expected['id'] in p['passage'] for p in original.items)
                assert not original.numeric_fact_authority
            async def tools():
                from mcp import Client
                async with Client(build_organization_evidence_server(reader),raise_exceptions=False) as client:
                    for item in result['results']:
                        answer = await client.call_tool('read_organization_evidence_rows', {'resource_id':item['resource_id']})
                        assert not answer.is_error and answer.structured_content['rows'][0]['id']==item['record_id']
            asyncio.run(tools())
        viewer = {'Authorization':'Bearer qualification-viewer'}
        invite = str(uuid4())
        api('POST', f'/organizations/{org}/invites', {'token':invite})
        s.request(s.bff,'POST','/api/v1/business/workspaces/join',headers=viewer,
                  json={'token':invite,'display_name':'Reader'})
        revision = api('GET', f'/projects/{project}')['revision']
        api('POST', f'/projects/{project}/members', {'revision':revision,'subject':'oidc:viewer','role':'viewer'})
        for item in result['results']:
            expected = next(r for c in spec['cases'] for r in c['snapshot']['rows'] if r['id']==item['record_id'])
            ref = next(a['current']['ref'] for a in assets.catalog('oidc:alice',private)['items']
                       if a['current']['ref']['version_id']==item['document_id'])
            assert assets.read('oidc:alice',ref)['capture']['rows'] == [expected]
            url = '/api/v1/asset-workspace/spaces/resources/'+item['resource_id']
            published = s.request(s.bff,'GET',url)
            assert published['capture']['rows'] == [expected]
            assert s.bff.get(url, headers=viewer).status_code == 404
        api('POST', f'/spaces/{space}/members', {'subject':'oidc:viewer','role':'reader'})
        for item in result['results']:
            url = '/api/v1/asset-workspace/spaces/resources/'+item['resource_id']
            row = s.request(s.bff,'GET',url,headers=viewer)
            assert row['capture']['rows'][0]['id'] == item['record_id']
            api('POST', f"/resources/{item['resource_id']}/revoke", {'revision':row['permission_revision']})
            assert s.bff.get(url,headers=viewer).status_code == 404
            with pytest.raises(OrganizationExecutionUnavailable):
                readers[-1].read_rows(item['resource_id'])
        s.save('metric-browser-result', {'cases':result['results'],'provider_calls':0,'response_mocks':0,
            'publication_recovery':result.get('recoveries', []),
            'research_drafts':result['drafts'],'native_navigation_and_mcp_rows':True,
            'early_cutoff_blocked_in_verification_and_native_reads':True,
            'real_services':['browser','BFF','Spring Boot','PostgreSQL','SQLite asset custody'],
            'synthetic':['login identity','organization/project setup'],'native_started':False,
            'project_membership_does_not_grant_sources':True,'revocation_checked':True,
            'financial_quality':'not_assessed','library_sha256':spec['library_sha256']})
    finally:
        for p in s.processes:
            if p.poll() is None:
                p.terminate()
                p.wait(timeout=20)
        for log in s.logs:
            log.close()
        try:
            s.compose('logs','--no-color')
        finally:
            s.compose('stop','-t','5')
            s.bff.close()
            s.native.close()
