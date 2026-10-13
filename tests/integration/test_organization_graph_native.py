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
from tests.integration.test_java_intake_native import Stack, COMPOSE, ROOT, wait_for

pytestmark = pytest.mark.skipif(os.getenv('FIN_ORGANIZATION_GRAPH_QUALIFICATION') != '1',
    reason='explicit isolated real organization graph qualification required')


class OrganizationGraphStack(Stack):
    compose_files = (COMPOSE, ROOT/'deploy/qualification/organization_graph.compose.yaml')
    graph_fixture = ROOT/'tests/integration/fixtures/organization_native_graph.py'
    synthetic_components = ['provider adapter', 'trace export gate', 'OIDC identity', 'original document']

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
        assert json.loads(env['LANGSERVE_GRAPHS'])=={'research_session':'/probe/organization_native_graph.py:graph'}
        assert env['FINSIGHT_BUSINESS_API_URL']==f'http://host.docker.internal:{self.java_port}'
        mounts={m['Destination']:m for m in row['Mounts']}
        assert not mounts['/qualification/src']['RW'] and not mounts['/qualification/configs']['RW']
        import hashlib
        paths=['tests/integration/fixtures/organization_native_graph.py','deploy/qualification/organization_graph.compose.yaml',
            'src/sec_agent/agent_runtime/organization_native_runtime.py','src/sec_agent/agent_runtime/research_session_runtime.py',
            'src/sec_agent/research_foundation/organization_execution_access.py']
        self.save('organization-container-contract',{'credential_presence_only':present,'mounts':list(mounts),
            'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths},
            'real':['native factory','research parent graph','Lead graph','MCP','Java authority','SDK','queue','checkpoint'],
            'substitutions':['scripted provider adapter','trace export gate (tracing disabled)','synthetic OIDC'],
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
            internal('POST',f'/projects/{project}/research-drafts/{draft}/execution-bindings',{'id':tid,'manifest_digest':prepared['manifest_digest']})
            path=f'/projects/{project}/execution-bindings/{tid}'
            options=execution or {'mode':'auto','model':'default','branch_ids':[],'continuation_scope':'original_plan'}
            receipt=internal('POST',path+'/prepare',{'execution':options})
            assert receipt['status']=='received'
            frozen=s.request(s.native,'GET',f'/threads/{tid}')['metadata']['organization_run_configuration']['configurable']['finsight_execution']
            assert frozen==receipt['execution'] and frozen['require_all_branches'] is options.get('require_all_branches',False)
            started=internal('POST',path+'/start',{'research_as_of':'2026-10-12T12:00:00+08:00'})
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
        assert internal('POST',path+'/start',{'research_as_of':'2026-10-12T12:00:00+08:00'})['run_id']==rid
        assert len(s.runs(tid))==1
        for p in (business,web):p.terminate();p.wait(timeout=20)
        s.compose('stop','-t','5','api','redis','postgres');s.compose('up','-d','--pull','never','api');s.healthy()
        s.boot('java');s.boot('bff')
        assert internal('POST',path+'/start-reconcile',{})['run_id']==rid
        assert s.state_of(tid)['values']['research_orientation']==orientation and len(s.turns(tid))==3
        # Even direct access to the test native API cannot reuse a Java command
        # for another run. Product users never receive this native credential.
        grant=internal('GET',path+'/start-access')
        thread=s.request(s.native,'GET',f'/threads/{tid}')
        extra=s.request(s.native,'POST',f'/threads/{tid}/runs',json={
            'assistant_id':'research_session',**run_request(thread,grant),'multitask_strategy':'reject'})
        s.denied_run(tid,extra['run_id'])
        assert len(s.turns(tid))==3 and internal('GET',path+'/start')['run_id']==rid
        assert s.state_of(tid)['values']['research_orientation']==orientation
        revoked_tid,revoked_rid,revoked_path=start('Revoke during static model response; stop before the next source read.')
        wait_for(lambda:(s.events/(revoked_tid+'.ready')).exists(),seconds=60)
        current=s.request(s.bff,'GET',f'/api/v1/asset-workspace/spaces/resources/{resource}')
        api('POST',f'/resources/{resource}/revoke',{'revision':current['permission_revision']})
        (s.events/(revoked_tid+'.release')).write_text('release scripted response after committed Java revocation')
        s.denied_run(revoked_tid,revoked_rid)
        assert len(s.turns(revoked_tid))==2
        assert not s.state_of(revoked_tid)['values'].get('research_orientation')
        internal('GET',revoked_path+'/start',status=404)
        internal('POST',path+'/start-reconcile',{},status=404)
        assert len(s.runs(tid))==2 and len(s.runs(revoked_tid))==1
        s.save('organization-graph-result',{'normal':{'thread_id':tid,'run_id':rid,'phase':values['phase'],'scripted_turns':3},
            'revoked':{'thread_id':revoked_tid,'run_id':revoked_rid,'status':'error','scripted_turns':2},
            'unauthorized_extra_run':{'run_id':extra['run_id'],'status':'error','additional_model_turns':0},
            'all_services_restart':True,'native_runs':3,'provider_calls':0,'semantic_acceptance':'not_assessed',
            'product_read_authorization':'not covered; test operator reads isolated native SDK directly'})
    finally:
        for p in s.processes:
            if p.poll() is None:p.terminate();p.wait(timeout=20)
        for log in s.logs:log.close()
        try:s.compose('logs','--no-color')
        finally:
            s.compose('stop','-t','5');java.close();s.bff.close();s.native.close()
