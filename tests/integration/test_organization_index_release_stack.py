"""Java frozen release -> real native MCP query embedding, no paid generation.

One new public query is authorized per attempt. Do not rerun a failed/unknown
paid request with a new organization ID; inspect the retained receipt first.
"""
from hashlib import sha256
import json
import os
from pathlib import Path
from uuid import uuid4

import httpx
import psycopg
import pytest

from apps.workbench.backend.business_transport import delegate
from sec_agent.research_foundation.asset_workspace import AssetWorkspace
from sec_agent.research_foundation.organization_execution_access import OrganizationExecutionReader, OrganizationExecutionAuthority
from sec_agent.research_foundation.organization_hybrid_retrieval import preparation_nodes, publish_prepared_index
from sec_agent.research_foundation.organization_source_navigation import OrganizationSourceNavigation
from sec_agent.adapters.local_records import LocalRecords
from tests.integration.test_organization_capacity_stack import CapacityStack, available_memory
from tests.integration.test_organization_graph_native import ROOT

pytestmark = pytest.mark.skipif(os.getenv('FIN_PAID_QUERY_QUALIFICATION') != '1',
    reason='explicit isolated paid embedding scope required')


class IndexStack(CapacityStack):
    compose_files = (*CapacityStack.compose_files, ROOT/'deploy/qualification/index_release.compose.yaml')
    allowed_provider_keys = ('QWEN_API_KEY',)

    def __init__(self):
        super().__init__()
        assert os.environ.get('QWEN_API_KEY')
        self.indexes = self.output/'indexes'
        self.indexes.mkdir()
        self.query = 'What does NVIDIA disclose about revenue concentration among its direct customers?'
        self.env.update(FINSIGHT_ORGANIZATION_RETRIEVAL_ROOT=str(self.indexes),
            FIN_PROBE_ORGANIZATION_INDEXES=self.indexes.as_posix(),
            FINSIGHT_ORGANIZATION_QUERY_EMBEDDING='qwen', QWEN_API_KEY=os.environ['QWEN_API_KEY'],
            FIN_PROBE_ORGANIZATION_QUERY=self.query)
        self.redactions.append(os.environ['QWEN_API_KEY'])
        self.save('TokenBudgetBasis', {'purpose':'One real native organization source search on Java frozen index',
            'input_scale':{'queries':1,'utf8_bytes':len(self.query.encode()),'query_sha256':sha256(self.query.encode()).hexdigest()},
            'required_output':'1024 finite values, original identity and provider receipt',
            'quality_risk':'Single-document connectivity only, not recall accuracy',
            'reasoning_profile':'Embedding only; research decisions scripted',
            'limits':{'requests':1,'max_retries':0,'timeout_seconds':45},
            'stop_behavior':'Stop on error; retain failed/unknown receipt; never rerun paid attempt automatically',
            'authorization':'User explicitly authorizes paid embedding, 2026-10-20'})


def test_java_frozen_release_native_new_query_and_publication_change(monkeypatch):
    memory = available_memory()
    assert memory is None or memory >= 2*1024**3, 'host_memory_below_isolated_stack_start_line'
    cases_path = Path(os.environ['FIN_ORGANIZATION_HYBRID_CASES'])
    cases = json.loads(cases_path.read_text())
    document = next(c for c in cases['cases'] if c['id']=='nvidia_concentration')['documents'][0]
    body = (cases_path.parent/document['file']).read_bytes()
    assert sha256(body).hexdigest() == document['sha256']
    s = IndexStack()
    monkeypatch.setenv('FINSIGHT_BUSINESS_SHARED_SECRET',s.shared)
    # A local post-run cache read may only reuse the receipt produced by native.
    monkeypatch.setenv('FINSIGHT_ORGANIZATION_QUERY_EMBEDDING','qwen')
    def api(method,path,data=None):
        return s.request(s.bff,method,'/api/v1/business/workspaces'+path,**({'json':data} if data is not None else {}))
    def bind(draft, digest, project, execution):
        path=f'/v1/workspaces/projects/{project}/research-drafts/{draft}/execution-bindings'
        encoded=json.dumps({'id':execution,'manifest_digest':digest},separators=(',',':')).encode()
        with httpx.Client(trust_env=False,timeout=30) as client:
            result=client.post(f'http://127.0.0.1:{s.java_port}'+path,content=encoded,
                headers={'Content-Type':'application/json','Authorization':'Bearer '+delegate('oidc:alice','POST',path,encoded)})
            assert result.status_code==200
        return OrganizationExecutionReader(AssetWorkspace(s.state/'project-library'/'organization-assets'),
            OrganizationExecutionAuthority(base_url=f'http://127.0.0.1:{s.java_port}',secret=s.runtime_secret,
                execution_id=execution,manifest_digest=digest))
    try:
        s.compose('up','-d','--pull','never','api');s.healthy();s.audit_container()
        with psycopg.connect(host='127.0.0.1',port=s.pg_port,dbname='probe',user='probe',password=s.password,autocommit=True) as db:
            db.execute('CREATE DATABASE business')
        s.boot('java');s.boot('bff')
        org,space,project,private,resource,draft,release = [str(uuid4()) for _ in range(7)]
        api('POST','/organizations',{'id':org,'name':'Frozen index qualification','display_name':'Owner'})
        api('POST','/spaces',{'id':space,'organization_id':org,'name':'Historical originals'})
        api('POST','/projects',{'id':project,'organization_id':org,'name':'Pinned retrieval','description':'No paid research model'})
        assets=AssetWorkspace(s.state/'project-library')
        assets.library.save('oidc:alice',0,{'projects':[{'id':private,'name':'Original'}],'assignments':{},'pinned':[]})
        assets.library.documents.add(assets.library.scope('oidc:alice',private),'NVIDIA.txt',body)
        ref=assets.catalog('oidc:alice',private)['items'][0]['current']['ref']
        s.request(s.bff,'POST','/api/v1/asset-workspace/spaces/publish',json={'id':resource,'space_id':space,'ref':ref})
        api('POST',f'/projects/{project}/resources/{resource}',{'revision':1,'linked':True})
        payload={'id':draft,'title':'Index source preparation','question':s.query,
                 'research_as_of':cases['as_of'],'resource_ids':[resource]}
        old=api('POST',f'/projects/{project}/research-drafts',payload)
        original_reader=bind(draft,old['manifest_digest'],project,str(uuid4()))
        _, nodes=preparation_nodes(original_reader,workbench_url='http://localhost')
        assert len(nodes)==1 and nodes[0]['content_sha256']==document['sha256']
        def publish(identifier):
            publish_prepared_index(s.indexes,org,nodes,[document['vector']],{},model=cases['model'],
                provenance=cases['provenance'],release_id=identifier)
            path=f'/api/v1/asset-workspace/organization-projects/{project}/research-drafts/{draft}/retrieval-releases/{identifier}/register'
            return s.request(s.bff,'POST',path,json={})
        contract=publish(release)
        payload.update(id=str(uuid4()),title='Pinned live query',retrieval_release_id=release)
        frozen=api('POST',f'/projects/{project}/research-drafts',payload)
        assert frozen['manifest']['retrieval_index']==contract
        assert api('GET',f'/projects/{project}/research-drafts/{draft}')==old
        execution=str(uuid4())
        prepared=s.request(s.bff,'POST',f'/api/v1/organization-projects/{project}/research-drafts/{payload["id"]}/prepare',
            json={'execution_id':execution,'manifest_digest':frozen['manifest_digest'],
                  'execution':{'mode':'auto','model':'default','branch_ids':[],'continuation_scope':'original_plan'}})
        assert prepared['status']=='received'
        # Publish before actual run: the original preparation must not drift.
        newer=publish(str(uuid4()))
        assert newer['index_digest']!=contract['index_digest']
        started=s.request(s.bff,'POST',f'/api/v1/organization-projects/{project}/research/{execution}/start',json={})
        assert started['status']=='received'
        s.terminal(execution,started['run_id'],seconds=120)
        state=s.state_of(execution)['values']
        assert state['phase']=='research_orientation_submitted' and len(s.turns(execution))==3
        assert state['research_orientation']['findings'][0]['evidence_spans'][0]['quote'] in body.decode()
        # Inspect durable receipts without asking the provider a second time.
        with LocalRecords(s.indexes/'query-cache') as cache:
            keys=[r[0] for r in cache.db.execute('SELECT key FROM records')]
            receipts=[cache.get(k) for k in keys]
        assert len(receipts)==1 and receipts[0]['status']=='completed'
        assert receipts[0]['result']['model']==cases['model']
        # Explicit second read goes through the same Java current-ACL path.
        reader=OrganizationExecutionReader(original_reader.workspace,OrganizationExecutionAuthority(
            base_url=f'http://127.0.0.1:{s.java_port}',secret=s.runtime_secret,
            execution_id=execution,manifest_digest=frozen['manifest_digest']))
        nav=OrganizationSourceNavigation(reader,workbench_url='http://localhost',retrieval_root=s.indexes)
        response=nav.navigate({'source_space':'organization','operation':'search','query':s.query})
        metadata=response.items[0]['retrieval']
        assert metadata['provider_calls']==0 and metadata['index_digest']==contract['index_digest']
        s.save('frozen-index-result',{'contract':contract,'newer_contract':newer,
            'execution_id':execution,'run_id':started['run_id'],'paid_embedding_calls':1,
            'paid_generation_calls':0,'receipt':{k:v for k,v in receipts[0]['result'].items() if k!='values'},
            'cache_read':metadata,'source_sha256':document['sha256']})
    finally:
        for process in s.processes:
            if process.poll() is None:process.terminate();process.wait(timeout=20)
        for log in s.logs:log.close()
        try:s.compose('logs','--no-color')
        finally:s.compose('stop','-t','5');s.bff.close();s.native.close()
