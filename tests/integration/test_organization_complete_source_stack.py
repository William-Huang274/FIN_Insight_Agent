"""Full parsed sources through real BFF/Java/Postgres and production MCP tools.

Explicit private artifacts; qualification login only. No Agent run or paid call.
This is intake acceptance, deliberately not recall or capacity measurement.
"""
import asyncio
from hashlib import sha256
import json
import os
from pathlib import Path
import socket
from types import SimpleNamespace
from uuid import uuid4

import httpx
import numpy as np
import psycopg
import pytest
from mcp import Client

from apps.workbench.backend.business_transport import delegate
from retrieval.source_hybrid import CachedRetrieval
from scripts.data_retrieval.replay_cached_library_scenarios import ReadOnlyReceipts
from sec_agent.research_foundation.asset_workspace import AssetWorkspace
from sec_agent.research_foundation.project_source_captures import CaptureRequest, save_capture
from sec_agent.research_foundation.organization_execution_access import OrganizationExecutionAuthority, OrganizationExecutionReader, OrganizationExecutionUnavailable
from sec_agent.research_foundation.organization_hybrid_retrieval import preparation_nodes, publish_prepared_index
from sec_agent.research_foundation.organization_source_navigation import OrganizationSourceNavigation, build_organization_source_server
from sec_agent.research_foundation.organization_source_projection import PROJECTION
from tests.integration.test_organization_graph_native import OrganizationGraphStack
from tests.integration.test_java_intake_native import wait_for

pytestmark = pytest.mark.skipif(not os.getenv('FIN_COMPLETE_SOURCE_INTAKE'), reason='explicit full-source intake artifacts required')


def test_complete_sources_real_authority_publication_frozen_index_and_readback(monkeypatch):
    connect = socket.socket.connect
    def local_only(sock, address):
        if isinstance(address, tuple) and address[0] not in {'127.0.0.1','::1','localhost'}:
            raise AssertionError('complete_source_acceptance_forbids_external_network')
        return connect(sock, address)
    monkeypatch.setattr(socket.socket,'connect',local_only)
    root=Path(os.environ['FIN_COMPLETE_SOURCE_INTAKE']).resolve()
    intake=json.loads((root/'result.json').read_text(encoding='utf8'))
    assert intake['status']=='verified'
    dataset=Path(os.environ['FIN_COMPLETE_SOURCE_QUESTIONS'])
    questions=json.loads(dataset.read_text(encoding='utf8'))['questions']
    storage_probe=os.getenv('FIN_COMPLETE_SOURCE_STORAGE_PROBE')=='1'
    if not storage_probe:
        assert {row['source_id'] for row in intake['sources']}=={e['source_id'] for q in questions for e in q['evidence']}
    library=Path(os.environ['FIN_COMPLETE_SOURCE_LIBRARY']).resolve()
    bundles, vectors = {}, {}
    for row in intake['sources']:
        folder=root/row['directory']
        assert all(sha256((folder/name).read_bytes()).hexdigest()==value for name,value in row['files'].items())
        bundle=json.loads((folder/'source.json').read_text(encoding='utf8'))
        matrix=np.load(folder/'vectors.npy',allow_pickle=False)
        mapping=json.loads((folder/'vector-map.json').read_text(encoding='utf8'))
        bundles[row['source_id']]=bundle
        vectors.update({r['chunk_id']:matrix[r['vector_index']] for r in mapping})
    model=intake['source_index']['embedding_model']
    namespace=sha256(json.dumps(['index-query.v1','public-recall-qualification',
        intake['source_index']['matrix_sha256'],model,1024],separators=(',',':')).encode()).hexdigest()
    queries={}
    selected_questions={sid:(questions[0] if storage_probe else next(q for q in questions if q['evidence'][0]['source_id']==sid)) for sid in bundles}
    with ReadOnlyReceipts(Path(os.environ['FIN_COMPLETE_SOURCE_QUERY_CACHE'])) as cache:
        client=CachedRetrieval(cache,SimpleNamespace(embedding_model=model,rerank_model='qwen3-rerank'),namespace)
        for q in selected_questions.values():
            saved=cache.get(client.key('embedding',[q['query']]))
            assert saved and saved['status']=='completed' and saved['result']['model']==model
            queries[q['query']]=saved['result']['values'][0]
    s=OrganizationGraphStack()
    indices=s.output/'indices'
    s.env['FINSIGHT_ORGANIZATION_RETRIEVAL_ROOT']=str(indices)
    monkeypatch.setenv('FINSIGHT_BUSINESS_SHARED_SECRET',s.shared)
    s.save('complete-source-scope',dict(sources=list(bundles),candidate_chunks=len(vectors),
        login='qualification identity; not real OIDC validation',services=['BFF','Java','PostgreSQL'],
        tools='production organization MCP on host; native Agent run not started',
        recall_or_capacity_evaluation=False,provider_calls=0,
        query_scope='reused query for storage/authorization plumbing, no relevance assertion' if storage_probe else 'historical source queries'))
    def api(method,path,body=None):
        return s.request(s.bff,method,'/api/v1/business/workspaces'+path,**({'json':body} if body is not None else {}))
    def bind(project,prepared):
        execution=str(uuid4())
        path=f'/v1/workspaces/projects/{project}/research-drafts/{prepared["id"]}/execution-bindings'
        raw=json.dumps({'id':execution,'manifest_digest':prepared['manifest_digest']},separators=(',',':')).encode()
        with httpx.Client(trust_env=False,timeout=30) as client:
            response=client.post(f'http://127.0.0.1:{s.java_port}'+path,content=raw,
                headers={'Content-Type':'application/json','Authorization':'Bearer '+delegate('oidc:alice','POST',path,raw)})
            assert response.status_code==200,response.text
        return OrganizationExecutionReader(AssetWorkspace(s.state/'project-library'/'organization-assets'),
            OrganizationExecutionAuthority(base_url=f'http://127.0.0.1:{s.java_port}',secret=s.runtime_secret,
                execution_id=execution,manifest_digest=prepared['manifest_digest']))
    try:
        s.compose('up','-d','--pull','never','postgres')
        def ready():
            try:
                with psycopg.connect(host='127.0.0.1',port=s.pg_port,dbname='probe',user='probe',password=s.password,connect_timeout=2): return True
            except psycopg.OperationalError: return False
        wait_for(ready)
        with psycopg.connect(host='127.0.0.1',port=s.pg_port,dbname='probe',user='probe',password=s.password,autocommit=True) as db:
            db.execute('CREATE DATABASE business')
        s.boot('java');s.boot('bff')
        org,space,project,private=[str(uuid4()) for _ in range(4)]
        api('POST','/organizations',{'id':org,'name':'Complete source intake','display_name':'Owner'})
        api('POST','/spaces',{'id':space,'organization_id':org,'name':'Full parsed disclosures'})
        api('POST','/projects',{'id':project,'organization_id':org,'name':'Source compatibility','description':'No recall claim'})
        assets=AssetWorkspace(s.state/'project-library')
        assets.library.save('oidc:alice',0,{'projects':[{'id':private,'name':'Public originals'}],'assignments':{},'pinned':[]})
        resources={};captures=[]
        for sid,bundle in bundles.items():
            # Same maintained capture service as POST /captures; no payload supplied as source facts.
            request=CaptureRequest(project_id=private,title=bundle['source']['title'],selection={
                'kind':'library_source','document_id':sid,'snapshot':intake['library_sha256']})
            saved=save_capture(assets,'oidc:alice',request,None,None,library)
            assert save_capture(assets,'oidc:alice',request,None,None,library)['document_id']==saved['document_id']
            ref=next(v['ref'] for a in assets.catalog('oidc:alice',private)['items'] for v in a['versions'] if v['ref']['version_id']==saved['document_id'])
            rid=str(uuid4())
            s.request(s.bff,'POST','/api/v1/asset-workspace/spaces/publish',json={'id':rid,'space_id':space,'ref':ref})
            revision=api('GET',f'/projects/{project}')['revision']
            api('POST',f'/projects/{project}/resources/{rid}',{'revision':revision,'linked':True})
            resources[sid]=rid
            assert assets.read_source('oidc:alice',ref)['source_bundle']==bundle
            with assets.library.documents.connect() as db:
                raw=db.execute('SELECT snapshot FROM attachment_captures WHERE object_id=?',(saved['document_id'],)).fetchone()[0]
            captures.append({'source_id':sid,'snapshot_bytes':len(raw.encode()),'text_characters':len(bundle['text']),
                             'schema_version':json.loads(raw)['schema_version'],'repeat_save_same_version':True})
        payload={'id':str(uuid4()),'title':'Complete inputs','question':'Read the selected complete disclosures.',
                 'research_as_of':'2026-09-23','resource_ids':list(resources.values())}
        original=api('POST',f'/projects/{project}/research-drafts',payload)
        reader=bind(project,original)
        _,nodes=preparation_nodes(reader,workbench_url='http://localhost')
        assert len(nodes)==len(vectors)
        release=str(uuid4())
        publish_prepared_index(indices,org,nodes,[vectors[n['original_source']['id']] for n in nodes],queries,
            model=model,provenance={'source_intake_sha256':sha256((root/'result.json').read_bytes()).hexdigest()},
            release_id=release,projection=PROJECTION)
        contract=s.request(s.bff,'POST',f'/api/v1/asset-workspace/organization-projects/{project}/research-drafts/{original["id"]}/retrieval-releases/{release}/register',json={})
        payload.update(id=str(uuid4()),retrieval_release_id=release)
        frozen=api('POST',f'/projects/{project}/research-drafts',payload)
        assert frozen['manifest']['retrieval_index']==contract
        assert api('GET',f'/projects/{project}/research-drafts/{original["id"]}')==original
        reader=bind(project,frozen)
        nav=OrganizationSourceNavigation(reader,workbench_url='http://localhost',retrieval_root=indices)
        results=[]
        async def exercise():
            async with Client(build_organization_source_server(nav), raise_exceptions=False) as client:
                for sid,bundle in bundles.items():
                    leaves=[n for n in nodes if n['original_source']['source_id']==sid]
                    tail=max(leaves,key=lambda n:n['original_source']['source_char_end'])
                    assert tail['original_source']['source_char_start']>100000
                    query={'source_space':'organization','operation':'search','document_id':tail['parent_document_id'],
                           'query':selected_questions[sid]['query']}
                    response=await client.call_tool('read_source_document',{'request':query})
                    assert not response.is_error
                    found=response.structured_content['items']
                    assert found and all(r['original_source']['source_id']==sid for r in found)
                    cached=await client.call_tool('read_source_document',{'request':query})
                    assert cached.structured_content['items'][0]['retrieval']['cache_hit']
                    request={'source_space':'organization','operation':'read','document_id':tail['parent_document_id'],
                             'node_id':tail['node_id'],'max_characters':16000}
                    read=await client.call_tool('read_source_document',{'request':request})
                    assert not read.is_error
                    passage=read.structured_content['items'][0]
                    assert passage['passage']==tail['content'] and not passage['truncated']
                    assert passage['original_source']==tail['original_source']
                    results.append({'source_id':sid,'candidate_chunks':len(leaves),'tail_char_start':tail['original_source']['source_char_start'],
                        'tail_sha256':passage['content_sha256'],'readback':passage['readback'],'cache_hit':True,
                        'index_digest':found[0]['retrieval']['index_digest'],'provider_calls':found[0]['retrieval']['provider_calls']})
                    s.save('complete-source-progress',{'sources':results,'status':'running'})
        asyncio.run(exercise())
        first=next(iter(resources.values()))
        current=s.request(s.bff,'GET',f'/api/v1/asset-workspace/spaces/resources/{first}')
        api('POST',f'/resources/{first}/revoke',{'revision':current['permission_revision']})
        with pytest.raises(OrganizationExecutionUnavailable): nav.navigate(results[0]['readback'])
        with pytest.raises(OrganizationExecutionUnavailable): nav.navigate({'source_space':'organization','operation':'search','query':next(iter(queries))})
        s.save('complete-source-result',{'status':'passed','sources':results,'frozen_contract':contract,
            'revoked_cache_and_readback_denied':True,'provider_calls':0,'research_runs':0,
            'recall_or_capacity_evaluation':False,'candidate_chunks':len(nodes),'identity':'qualification login',
            'captures':captures,'query_is_storage_probe':storage_probe})
    finally:
        for process in s.processes:
            if process.poll() is None: process.terminate();process.wait(timeout=20)
        for log in s.logs: log.close()
        try:s.compose('logs','--no-color')
        finally:s.compose('stop','-t','5');s.bff.close();s.native.close()
