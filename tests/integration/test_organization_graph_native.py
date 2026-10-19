"""Real organization graph in Agent Server, static provider and current Java ACL.

Docker Desktop host gateway only. No shared deployment, real OIDC or financial
quality claim; own service processes/containers are stopped and evidence retained.
"""
import json
import os
import secrets
import subprocess
from uuid import uuid4

import httpx
import psycopg
import pytest

from apps.workbench.backend.business_transport import delegate
from sec_agent.research_foundation.asset_workspace import AssetWorkspace
from sec_agent.agent_runtime.research_orientation import orientation_public_handoff
from sec_agent.agent_runtime.organization_native_contract import run_request
from sec_agent.agent_runtime.organization_continuation_contract import baseline_digest, continuation_request
from tests.integration.test_java_intake_native import Stack, COMPOSE, ROOT, wait_for

pytestmark = pytest.mark.skipif(os.getenv('FIN_ORGANIZATION_GRAPH_QUALIFICATION') != '1',
    reason='explicit isolated real organization graph qualification required')


class OrganizationGraphStack(Stack):
    compose_files = (COMPOSE, ROOT/'deploy/qualification/organization_graph.compose.yaml')
    graph_fixture = ROOT/'tests/integration/fixtures/organization_native_graph.py'
    synthetic_components = ['provider adapter', 'trace export gate', 'OIDC identity', 'original document']
    registered_graph = '/probe/organization_native_graph.py:graph'
    real_components = ['native factory','research parent graph','Lead graph','MCP','Java authority','SDK','queue','checkpoint']

    def __init__(self):
        super().__init__()
        self.runtime_secret = secrets.token_urlsafe(48)
        self.redactions.append(self.runtime_secret)
        assets = self.state/'project-library'/'organization-assets'
        assets.mkdir(parents=True)
        settings = self.output/'settings'
        settings.mkdir()
        (settings/'settings.json').write_text(json.dumps({'audit_root':'/probe-audit',
            'workbench_url':'https://qualification.invalid',
            'research_library':'/forbidden-library', 'conversation_fact_mart':'/forbidden-facts'}))
        self.env.update(FIN_ORGANIZATION_NATIVE_QUALIFICATION='1', FINSIGHT_ORGANIZATION_START_ENABLED='1',
            FINSIGHT_ORGANIZATION_RUNTIME_SECRET=self.runtime_secret,
            FIN_PROBE_ORGANIZATION_ASSETS=assets.as_posix(), FIN_PROBE_SETTINGS=settings.as_posix())
        self.bff.headers['Authorization']='Bearer qualification-alice'

    def audit_container(self):
        ids = subprocess.check_output([self.docker,'ps','-q','--filter','label=com.docker.compose.project='+self.project,
            '--filter','label=com.docker.compose.service=api'],text=True,timeout=15).split()
        assert len(ids)==1
        row=json.loads(subprocess.check_output([self.docker,'inspect',ids[0]],text=True,timeout=15))[0]
        env=dict(v.split('=',1) for v in row['Config']['Env'])
        present={k:bool(v) for k,v in env.items() if any(s in k.upper() for s in ('API_KEY','TOKEN','SECRET'))}
        assert not any(v for k,v in present.items() if k not in ('LANGSMITH_API_KEY','FINSIGHT_ORGANIZATION_RUNTIME_SECRET'))
        assert env['LANGSMITH_TRACING']=='false'
        assert json.loads(env['LANGSERVE_GRAPHS'])=={'research_session':self.registered_graph}
        assert env['FINSIGHT_BUSINESS_API_URL']==f'http://host.docker.internal:{self.java_port}'
        mounts={m['Destination']:m for m in row['Mounts']}
        assert not mounts['/qualification/src']['RW'] and not mounts['/qualification/configs']['RW']
        import hashlib
        paths=['tests/integration/fixtures/organization_native_graph.py','deploy/qualification/organization_graph.compose.yaml',
            'src/sec_agent/agent_runtime/organization_native_runtime.py','src/sec_agent/agent_runtime/research_session_runtime.py',
            'src/sec_agent/research_foundation/organization_execution_access.py']
        self.save('organization-container-contract',{'credential_presence_only':present,'mounts':list(mounts),
            'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths},
            'real':self.real_components,
            'substitutions':self.synthetic_components,
            'provider_calls':0})

    def turns(self,tid):
        path=self.events/'model-turns.jsonl'
        return [r for r in map(json.loads,path.read_text().splitlines()) if r['thread_id']==tid] if path.exists() else []

    def denied_run(self,tid,rid):
        self.terminal(tid,rid,status='error',seconds=60)
        # An unrelated worker failure must not count as a permission denial.
        self.compose('logs','--no-color','api')
        records=[]
        for line in (self.output/f'compose-{self.ordinal:02d}.log').read_text(encoding='utf-8').splitlines():
            try:row=json.loads(line[line.index('{'):])
            except (ValueError,json.JSONDecodeError):continue
            if row.get('run_id')==rid:records.append(row)
        assert any('OrganizationExecutionUnavailable' in str(r.get('exception','')) for r in records)


def test_real_native_organization_orientation_restart_and_mid_run_revocation(monkeypatch):
    s=OrganizationGraphStack()
    monkeypatch.setenv('FINSIGHT_BUSINESS_SHARED_SECRET',s.shared)
    java=httpx.Client(base_url=f'http://127.0.0.1:{s.java_port}',timeout=60,trust_env=False)
    def api(method,path,body=None):
        return s.request(s.bff,method,'/api/v1/business/workspaces'+path,**({'json':body} if body is not None else {}))
    def internal(method,path,body=None,status=200):
        path='/v1/workspaces'+path
        raw=b'' if body is None else json.dumps(body,separators=(',',':')).encode()
        response=java.request(method,path,content=raw,headers={'Content-Type':'application/json',
            'Authorization':'Bearer '+delegate('oidc:alice',method,path,raw)})
        assert response.status_code==status,response.text
        return response.json()
    try:
        s.compose('up','-d','--pull','never','api');s.healthy();s.audit_container()
        with psycopg.connect(host='127.0.0.1',port=s.pg_port,dbname='probe',user='probe',password=s.password,autocommit=True) as conn:
            conn.execute('CREATE DATABASE business')
        business,web=s.boot('java'),s.boot('bff')
        org,space,project,resource,private=[str(uuid4()) for _ in range(5)]
        api('POST','/organizations',{'id':org,'name':'Static graph organization','display_name':'Alice'})
        api('POST','/spaces',{'id':space,'organization_id':org,'name':'Team originals'})
        api('POST','/projects',{'id':project,'organization_id':org,'name':'Static graph project','description':'No financial quality claim'})
        source=AssetWorkspace(s.state/'project-library')
        source.library.save('oidc:alice',0,{'projects':[{'id':private,'name':'Private original'}],'assignments':{},'pinned':[]})
        source.library.documents.add(source.library.scope('oidc:alice',private),'Original.md',b'Synthetic pinned organization evidence.')
        ref=source.catalog('oidc:alice',private)['items'][0]['current']['ref']
        s.request(s.bff,'POST','/api/v1/asset-workspace/spaces/publish',json={'id':resource,'space_id':space,'ref':ref})
        api('POST',f'/projects/{project}/resources/{resource}',{'revision':1,'linked':True})
        def start(question,execution=None):
            draft,tid=str(uuid4()),str(uuid4())
            prepared=api('POST',f'/projects/{project}/research-drafts',{'id':draft,'title':question,'question':question,
                'research_as_of':'2026-10-12','resource_ids':[resource]})
            path=f'/projects/{project}/execution-bindings/{tid}'
            options=execution or {'mode':'auto','model':'default','branch_ids':[],'continuation_scope':'original_plan'}
            receipt=s.request(s.bff,'POST',f'/api/v1/organization-projects/{project}/research-drafts/{draft}/prepare',
                json={'execution_id':tid,'manifest_digest':prepared['manifest_digest'],'execution':options})
            assert receipt['status']=='received'
            frozen=s.request(s.native,'GET',f'/threads/{tid}')['metadata']['organization_run_configuration']['configurable']['finsight_execution']
            assert frozen==receipt['execution'] and frozen['require_all_branches'] is options.get('require_all_branches',False)
            started=s.request(s.bff,'POST',f'/api/v1/organization-projects/{project}/research/{tid}/start',json={})
            assert started['status']=='received',started
            return tid,started['run_id'],path
        tid,rid,path=start('Read the fixed original, without making a financial conclusion.',
            {'mode':'standard','model':'default','branch_ids':[],'continuation_scope':'original_plan','require_all_branches':True})
        s.terminal(tid,rid,seconds=90)
        values=s.state_of(tid)['values']
        assert values['phase']=='research_orientation_submitted',values.get('phase')
        assert len(s.turns(tid))==3 and values['research_orientation']['semantic_acceptance']=='not_assessed'
        orientation=values['research_orientation']
        assert orientation['findings'][0]['evidence_spans'][0]['quote']=='Synthetic pinned organization evidence.'
        assert orientation_public_handoff(orientation)['source_readbacks']['O2']['passages'][0]['organization_source']['execution_id']==tid
        assert s.request(s.bff,'POST',f'/api/v1/organization-projects/{project}/research/{tid}/start',json={})['run_id']==rid
        assert len(s.runs(tid))==1
        # Product read authorization is distinct from run admission. This viewer
        # has no creator/researcher role and gains no source access by joining.
        invite=str(uuid4())
        api('POST',f'/organizations/{org}/invites',{'token':invite})
        viewer_headers={'Authorization':'Bearer qualification-viewer'}
        joined=s.bff.post('/api/v1/business/workspaces/join',json={'token':invite,'display_name':'Static viewer'},headers=viewer_headers)
        assert joined.status_code==200,joined.text
        revision=api('GET',f'/projects/{project}')['revision']
        api('POST',f'/projects/{project}/members',{'revision':revision,'subject':'oidc:viewer','role':'viewer'})
        read_path=f'/api/v1/organization-projects/{project}/research/{tid}'
        assert s.bff.get(read_path,headers=viewer_headers).status_code==404
        api('POST',f'/spaces/{space}/members',{'subject':'oidc:viewer','role':'reader'})
        visible=s.bff.get(read_path,headers=viewer_headers)
        assert visible.status_code==200,visible.text
        assert visible.json()['read_only'] is True and visible.json()['run_id']==rid
        assert visible.headers['cache-control']=='no-store'
        assert s.bff.get(read_path+'/control',headers=viewer_headers).json()=={'can_operate':False}
        assert s.bff.post(read_path+'/start',json={},headers=viewer_headers).status_code==404
        assert not any(v for k,v in visible.json().items() if k.startswith('can_'))
        assert s.bff.get(f'/api/v1/research-sessions/{tid}',headers=viewer_headers).status_code==404
        assert s.bff.get(read_path+f'/runs/{uuid4()}/events',headers=viewer_headers).status_code==404
        assert s.bff.get(read_path+'/report/export/md',headers=viewer_headers).status_code==409
        for p in (business,web):p.terminate();p.wait(timeout=20)
        s.compose('stop','-t','5','api','redis','postgres');s.compose('up','-d','--pull','never','api');s.healthy()
        s.boot('java');s.boot('bff')
        assert internal('POST',path+'/start-reconcile',{})['run_id']==rid
        assert s.state_of(tid)['values']['research_orientation']==orientation and len(s.turns(tid))==3
        assert s.bff.get(read_path,headers=viewer_headers).status_code==200
        # Even direct access to the test native API cannot reuse a Java command
        # for another run. Product users never receive this native credential.
        grant=internal('GET',path+'/start-access')
        thread=s.request(s.native,'GET',f'/threads/{tid}')
        extra=s.request(s.native,'POST',f'/threads/{tid}/runs',json={
            'assistant_id':'research_session',**run_request(thread,grant),'multitask_strategy':'reject'})
        s.denied_run(tid,extra['run_id'])
        assert len(s.turns(tid))==3 and internal('GET',path+'/start')['run_id']==rid
        assert s.state_of(tid)['values']['research_orientation']==orientation
        # A distinct command promotes an exact completed checkpoint; no models
        # are called when reconciling or replaying the same business request.
        promoted_tid,initial_rid,promoted_path=start('Qualify explicit continuation without claiming a financial result.')
        s.terminal(promoted_tid,initial_rid,seconds=90)
        baseline=s.state_of(promoted_tid)
        body={'previous_run_id':initial_rid,'checkpoint_id':baseline['checkpoint']['checkpoint_id'],
              'state_digest':baseline_digest(baseline)}
        promoted_read=f'/api/v1/organization-projects/{project}/research/{promoted_tid}'
        preview=s.request(s.bff,'GET',promoted_read+'/continuation-preview')
        assert preview==body
        continued=s.request(s.bff,'POST',promoted_read+'/continue',json=preview)
        assert continued['status']=='received',continued
        continued_rid=continued['run_id']
        # Server run status is success for a persisted graph interrupt; the
        # checkpoint, rather than transport status, proves the human handoff.
        s.terminal(promoted_tid,continued_rid,seconds=90)
        promoted_snapshot=s.state_of(promoted_tid)
        assert 'research_attention' in promoted_snapshot['next']
        assert any(t.get('interrupts') for t in promoted_snapshot['tasks'])
        promoted_state=promoted_snapshot['values']
        assert promoted_state['phase']=='research_needs_attention' and not promoted_state.get('report')
        assert promoted_state['research_orientation']==baseline['values']['research_orientation']
        assert len(s.turns(promoted_tid))==4
        assert s.request(s.bff,'POST',promoted_read+'/continue',json=preview)['run_id']==continued_rid
        assert s.request(s.bff,'POST',promoted_read+'/reconcile/continuation',json={})['run_id']==continued_rid
        assert len(s.runs(promoted_tid))==2
        promoted_read=f'/api/v1/organization-projects/{project}/research/{promoted_tid}'
        response=s.bff.get(promoted_read,headers=viewer_headers)
        assert response.status_code==200 and response.json()['run_id']==continued_rid,response.text
        continuation_grant=internal('GET',promoted_path+'/continuation-access')
        promoted_thread=s.request(s.native,'GET',f'/threads/{promoted_tid}')
        duplicate=s.request(s.native,'POST',f'/threads/{promoted_tid}/runs',json={
            'assistant_id':'research_session',**continuation_request(promoted_thread,continuation_grant),'multitask_strategy':'reject'})
        s.denied_run(promoted_tid,duplicate['run_id'])
        assert len(s.turns(promoted_tid))==4
        revoked_tid,revoked_rid,revoked_path=start('Revoke during static model response; stop before the next source read.')
        wait_for(lambda:(s.events/(revoked_tid+'.ready')).exists(),seconds=60)
        current=s.request(s.bff,'GET',f'/api/v1/asset-workspace/spaces/resources/{resource}')
        api('POST',f'/resources/{resource}/revoke',{'revision':current['permission_revision']})
        for suffix in ('','/report','/source?source_id=ORG:S1','/report/export/md',f'/runs/{rid}/events'):
            assert s.bff.get(read_path+suffix,headers=viewer_headers).status_code==404
        (s.events/(revoked_tid+'.release')).write_text('release scripted response after committed Java revocation')
        s.denied_run(revoked_tid,revoked_rid)
        assert len(s.turns(revoked_tid))==2
        assert not s.state_of(revoked_tid)['values'].get('research_orientation')
        internal('GET',revoked_path+'/start',status=404)
        internal('POST',path+'/start-reconcile',{},status=404)
        assert s.bff.get(promoted_read,headers=viewer_headers).status_code==404
        assert len(s.runs(tid))==2 and len(s.runs(revoked_tid))==1
        s.save('organization-graph-result',{'normal':{'thread_id':tid,'run_id':rid,'phase':values['phase'],'scripted_turns':3},
            'revoked':{'thread_id':revoked_tid,'run_id':revoked_rid,'status':'error','scripted_turns':2},
            'unauthorized_extra_run':{'run_id':extra['run_id'],'status':'error','additional_model_turns':0},
            'continuation':{'thread_id':promoted_tid,'run_id':continued_rid,'phase':promoted_state['phase'],
                'scripted_turns':4,'duplicate_run_denied':duplicate['run_id'],'preliminary_artifact_preserved':True},
            'all_services_restart':True,'native_runs':6,'provider_calls':0,'semantic_acceptance':'not_assessed',
            'product_read_authorization':'real viewer BFF snapshot and denial for every read route after source revocation; actual report export covered by static report renderer tests'})
    finally:
        for p in s.processes:
            if p.poll() is None:p.terminate();p.wait(timeout=20)
        for log in s.logs:log.close()
        try:s.compose('logs','--no-color')
        finally:
            s.compose('stop','-t','5');java.close();s.bff.close();s.native.close()
