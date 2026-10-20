"""Real browser/BFF/Java/PostgreSQL/queue delivery; explicitly static report writer."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from uuid import uuid4

import psycopg
import pytest

from sec_agent.research_foundation.asset_workspace import AssetWorkspace
from tests.integration.test_organization_graph_native import OrganizationGraphStack, ROOT

pytestmark = pytest.mark.skipif(os.getenv('FIN_ORGANIZATION_DELIVERY_QUALIFICATION') != '1',
    reason='explicit isolated business delivery qualification required')


class DeliveryStack(OrganizationGraphStack):
    compose_files = (*OrganizationGraphStack.compose_files, ROOT/'deploy/qualification/organization_delivery.compose.yaml')
    graph_fixture = ROOT/'tests/integration/fixtures/organization_delivery_graph.py'
    registered_graph = '/probe/organization_delivery_graph.py:graph'
    synthetic_components = [*OrganizationGraphStack.synthetic_components, 'downstream report producer']
    real_components = ['initial orientation parent/Lead/MCP','native organization factory and admission',
        'Java authority','SDK','queue','checkpoint','browser','BFF','report renderers']

    def browser(self, project, label, *, mode='create', execution=None, title=None):
        output = self.output/label
        env = {k:v for k,v in self.env.items() if k != 'LANGSMITH_API_KEY'}
        env.update(FIN_ORGANIZATION_DELIVERY_QUALIFICATION='1',
            FIN_DELIVERY_BROWSER_ORIGIN=f'http://127.0.0.1:{self.bff_port}',
            FIN_DELIVERY_PROJECT=project, FIN_DELIVERY_BROWSER_OUTPUT=str(output), FIN_DELIVERY_BROWSER_MODE=mode)
        if execution: env['FIN_DELIVERY_EXECUTION'] = execution
        if title: env['FIN_DELIVERY_TITLE'] = title
        node = os.getenv('FINSIGHT_TEST_NODE') or shutil.which('node')
        assert node, 'node_required_for_real_browser'
        result = subprocess.run([node, 'e2e/organization-live-delivery.mjs'],
            cwd=ROOT/'apps/workbench/frontend', env=env, capture_output=True, text=True,
            encoding='utf-8', errors='replace', timeout=300)
        self.save(label+'-process', {'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr})
        assert result.returncode == 0, result.stderr[-4000:]
        observed = json.loads((output/'result.json').read_text(encoding='utf-8'))
        if mode != 'denied':
            for suffix,magic in [('md',b'#'),('pdf',b'%PDF'),('docx',b'PK'),('pptx',b'PK')]:
                body = (output/('report.'+suffix)).read_bytes()
                assert body.startswith(magic), suffix
            expected = self.env.get('FIN_DELIVERY_EXPECTED_TEXT', 'Synthetic pinned organization evidence.')
            assert expected in (output/'report.md').read_text(encoding='utf8')
        return observed


def test_real_business_delivery_browser_restart_unknown_and_revocation(monkeypatch):
    s = DeliveryStack()
    monkeypatch.setenv('FINSIGHT_BUSINESS_SHARED_SECRET', s.shared)
    def api(method,path,body=None):
        return s.request(s.bff,method,'/api/v1/business/workspaces'+path,**({'json':body} if body is not None else {}))
    try:
        s.compose('up','-d','--pull','never','api'); s.healthy(); s.audit_container()
        with psycopg.connect(host='127.0.0.1',port=s.pg_port,dbname='probe',user='probe',password=s.password,autocommit=True) as conn:
            conn.execute('CREATE DATABASE business')
        business,web = s.boot('java'),s.boot('bff')
        org,space,project,resource,private = [str(uuid4()) for _ in range(5)]
        api('POST','/organizations',{'id':org,'name':'Static delivery organization','display_name':'Alice'})
        api('POST','/spaces',{'id':space,'organization_id':org,'name':'Team originals'})
        api('POST','/projects',{'id':project,'organization_id':org,'name':'Business delivery qualification','description':'Static only'})
        assets = AssetWorkspace(s.state/'project-library')
        assets.library.save('oidc:alice',0,{'projects':[{'id':private,'name':'Private original'}],'assignments':{},'pinned':[]})
        assets.library.documents.add(assets.library.scope('oidc:alice',private),'Original.md',b'Synthetic pinned organization evidence.')
        ref = assets.catalog('oidc:alice',private)['items'][0]['current']['ref']
        s.request(s.bff,'POST','/api/v1/asset-workspace/spaces/publish',json={'id':resource,'space_id':space,'ref':ref})
        api('POST',f'/projects/{project}/resources/{resource}',{'revision':1,'linked':True})

        # The browser creates the draft, prepares, starts, confirms continuation,
        # refreshes, reads the exact citation and downloads all four real formats.
        normal = s.browser(project,'browser-normal')
        tid = normal['execution']; read = f'/api/v1/organization-projects/{project}/research/{tid}'
        assert len(s.runs(tid)) == 2 and len(s.turns(tid)) == 4
        snapshot = s.request(s.bff,'GET',read)
        assert snapshot['phase'] == 'ready_for_human_review' and snapshot['checkpoint_id']
        report,checkpoint = snapshot['report'],snapshot['checkpoint_id']
        citation = report['citations']['C1']['sources'][0]
        assert citation['organization_source']['execution_id'] == tid
        assert citation['text'] == 'Synthetic pinned organization evidence.'
        run_ids = {r['run_id'] for r in s.runs(tid)}
        for stage in ('preparation','start','continuation'):
            assert s.request(s.bff,'POST',read+'/reconcile/'+stage,json={})['status'] == 'received'
        assert {r['run_id'] for r in s.runs(tid)} == run_ids

        invite = str(uuid4()); api('POST',f'/organizations/{org}/invites',{'token':invite})
        viewer = {'Authorization':'Bearer qualification-viewer'}
        assert s.bff.post('/api/v1/business/workspaces/join',headers=viewer,json={'token':invite,'display_name':'Reader'}).status_code == 200
        revision = api('GET',f'/projects/{project}')['revision']
        api('POST',f'/projects/{project}/members',{'revision':revision,'subject':'oidc:viewer','role':'viewer'})
        assert s.bff.get(read,headers=viewer).status_code == 404
        api('POST',f'/spaces/{space}/members',{'subject':'oidc:viewer','role':'reader'})

        # Restart only the five services owned by this uniquely named fixture.
        for process in (business,web): process.terminate(); process.wait(timeout=20)
        s.compose('stop','-t','5','api','redis','postgres');s.compose('up','-d','--pull','never','api');s.healthy()
        s.boot('java');s.boot('bff')
        resumed = s.request(s.bff,'GET',read)
        assert resumed['report'] == report and resumed['checkpoint_id'] == checkpoint
        s.browser(project,'browser-after-restart',mode='viewer',execution=tid)
        assert {r['run_id'] for r in s.runs(tid)} == run_ids and len(s.turns(tid)) == 4
        assert s.bff.post(read+'/start',headers=viewer,json={}).status_code == 404
        assert s.bff.get(f'/api/v1/research-sessions/{tid}',headers=viewer).status_code == 404

        # Inject response loss only AFTER actual thread/run persistence. Browser
        # reload and explicit reconciliation must recover the same operations.
        lost = s.browser(project,'browser-lost-replies',title='Synthetic lost organization reply')
        lost_tid = lost['execution']
        assert lost_tid != tid and len(s.runs(lost_tid)) == 2 and len(s.turns(lost_tid)) == 4
        observations = [json.loads(x) for x in (s.state/'native-start-observations.jsonl').read_text().splitlines()]
        assert len(observations) == 4
        assert len((s.state/'native-create-observations.jsonl').read_text().splitlines()) == 2
        # Every renderer and historical checkpoint is denied after current source revocation.
        current = s.request(s.bff,'GET',f'/api/v1/asset-workspace/spaces/resources/{resource}')
        api('POST',f'/resources/{resource}/revoke',{'revision':current['permission_revision']})
        paths = ['', '/report', '/source?source_id='+citation['source_id'],
            *['/report/export/'+fmt for fmt in ('md','pdf','docx','pptx')],
            '/runs/'+snapshot['run_id']+'/events']
        for suffix in paths:
            assert s.bff.get(read+suffix,headers=viewer).status_code == 404
        assert s.bff.get(read+'/report/export/md',params={'checkpoint_id':checkpoint}).status_code == 404
        s.browser(project,'browser-revoked',mode='denied',execution=tid)
        assert len(s.runs(tid)) == 2 and len(s.runs(lost_tid)) == 2
        s.save('business-delivery-result',{'normal_execution':tid,'lost_reply_execution':lost_tid,
            'native_threads':2,'native_runs':4,'scripted_responses':8,'provider_calls':0,
            'all_five_owned_services_restart':True,'browser_api_interceptions':0,'exports':['md','pdf','docx','pptx'],
            'current_acl_after_restart_and_revocation':True,'report_producer':'static labelled fixture',
            'financial_quality':'not_assessed','real_oidc':'not_assessed',
            'sources':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in
                ['tests/integration/test_organization_delivery_stack.py','tests/integration/fixtures/organization_delivery_graph.py',
                 'apps/workbench/frontend/e2e/organization-live-delivery.mjs','deploy/qualification/organization_delivery.compose.yaml']}})
    finally:
        for process in s.processes:
            if process.poll() is None: process.terminate(); process.wait(timeout=20)
        for log in s.logs: log.close()
        try:s.compose('logs','--no-color')
        finally:s.compose('stop','-t','5');s.bff.close();s.native.close()
