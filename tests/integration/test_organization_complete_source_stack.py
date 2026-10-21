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
from time import perf_counter
from uuid import uuid4

import httpx
import psycopg
import pytest
from mcp import Client

from apps.workbench.backend.business_transport import delegate
from retrieval.source_hybrid import CachedRetrieval
from scripts.data_retrieval.replay_cached_library_scenarios import ReadOnlyReceipts
from sec_agent.research_foundation.asset_workspace import AssetWorkspace
from sec_agent.research_foundation.project_source_captures import CaptureRequest, save_capture
from sec_agent.research_foundation.organization_execution_access import OrganizationExecutionAuthority, OrganizationExecutionReader, OrganizationExecutionUnavailable, build_organization_evidence_server
from sec_agent.research_foundation.organization_hybrid_retrieval import preparation_nodes, publish_prepared_index
from sec_agent.research_foundation.organization_source_navigation import OrganizationSourceNavigation, build_organization_source_server
from sec_agent.research_foundation.organization_source_projection import PROJECTION, validate_source_cutoff
from tests.integration.test_organization_graph_native import OrganizationGraphStack
from tests.integration.test_java_intake_native import wait_for
from tests.integration.source_intake_diagnostics import SourceBundles, SourceVectors, PhaseDiagnostics, file_sha256

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
    unified_scope=os.getenv('FIN_COMPLETE_SOURCE_UNIFIED_SCOPE')=='1'
    global_probe=os.getenv('FIN_COMPLETE_SOURCE_GLOBAL_PROBE')=='1'
    if global_probe:
        assert unified_scope and storage_probe
    if not storage_probe:
        assert {row['source_id'] for row in intake['sources']}=={e['source_id'] for q in questions for e in q['evidence']}
    library=Path(os.environ['FIN_COMPLETE_SOURCE_LIBRARY']).resolve()
    attempt=Path(os.environ['FIN_NATIVE_ATTEMPT_DIR']).resolve()
    if attempt.exists():
        raise FileExistsError('qualification_requires_new_attempt_directory')
    preflight=attempt.with_name(attempt.name+'-input-check.json')
    if preflight.exists():
        raise FileExistsError('qualification_requires_new_input_check_record')
    def input_progress(count,status):
        preflight.write_text(json.dumps({'status':status,'verified_source_files':count,
            'expected_sources':len(intake['sources']),'services_started':False}),encoding='utf8')
    input_progress(0,'running')
    def verify_intake_files():
        for row in intake['sources']:
            folder=root/row['directory']
            assert all(file_sha256(folder/name)==value for name,value in row['files'].items())
    bundles, vectors = SourceBundles(), SourceVectors()
    for ordinal,row in enumerate(intake['sources'],1):
        folder=root/row['directory']
        assert all(file_sha256(folder/name)==value for name,value in row['files'].items())
        mapping=json.loads((folder/'vector-map.json').read_text(encoding='utf8'))
        bundles[row['source_id']]=folder/'source.json'
        for r in mapping:
            vectors[r['chunk_id']]=(folder/'vectors.npy',r['vector_index'])
        if ordinal % 100 == 0:
            input_progress(ordinal,'running')
    input_progress(len(intake['sources']),'passed')
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
    diagnostic=PhaseDiagnostics(s.save)
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
        resources={};captures=[];date_denials=[]
        for sid,bundle in bundles.items():
            source_started=perf_counter()
            # Same maintained capture service as POST /captures; no payload supplied as source facts.
            request=CaptureRequest(project_id=private,title=bundle['source']['title'][:120],selection={
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
                             'schema_version':json.loads(raw)['schema_version'],'repeat_save_same_version':True,
                             'save_publish_link_verify_seconds':perf_counter()-source_started})
            s.save('complete-source-publication-progress',{'status':'running','sources':captures})
        # All originals were saved/published unchanged. Unknown availability
        # must still fail at the real authorized runtime read boundary.
        for sid in list(bundles):
            bundle=bundles[sid]
            try:
                validate_source_cutoff(bundle,'2026-09-23')
            except ValueError:
                assert storage_probe, 'historical evaluation unexpectedly includes unavailable source'
                rejected=api('POST',f'/projects/{project}/research-drafts',{
                    'id':str(uuid4()),'title':'Unavailable source','question':'Must not read undated material.',
                    'research_as_of':'2026-09-23','resource_ids':[resources[sid]]})
                blocked=bind(project,rejected)
                with pytest.raises(OrganizationExecutionUnavailable):blocked.read_text(resources[sid])
                with pytest.raises(OrganizationExecutionUnavailable):preparation_nodes(blocked,workbench_url='http://localhost')
                date_denials.append({'source_id':sid,'original_vintage':bundle['source']['vintage'],
                                    'published_at':bundle['source']['published_at'],'runtime_read_denied':True})
                for chunk in bundle['chunks']:vectors.pop(chunk['id'])
                del bundles[sid];del resources[sid]
        assert bundles, 'no eligible source for real organization retrieval'
        s.save('complete-source-date-denials',date_denials)
        results=[];contracts=[];node_reads=[]
        # Existing product limit is 12 explicitly selected resources per draft.
        # Batch intake qualification does not establish corpus-wide retrieval.
        async def exercise(batch,nodes,nav,reader):
            async with Client(build_organization_source_server(nav), raise_exceptions=False) as client:
                for sid,bundle in batch.items():
                    leaves=[n for n in nodes if n['original_source']['source_id']==sid]
                    indexed='node_recovery' in bundle
                    tail=max(leaves,key=lambda n:n['original_source']['char_end' if indexed else 'source_char_end'])
                    if not indexed:
                        if len(bundle['text'])>110000:
                            assert tail['original_source']['source_char_start']>100000
                        assert not bundle['text'][tail['original_source']['source_char_end']:].strip()
                    query={'source_space':'organization','operation':'search','document_id':tail['parent_document_id'],
                           'query':selected_questions[sid]['query']}
                    response=await client.call_tool('read_source_document',{'request':query})
                    assert not response.is_error
                    found=response.structured_content['items']
                    assert found and all(r['original_source']['source_id']==sid for r in found)
                    if unified_scope:
                        expected='selected' if sid in list(batch)[:2] else 'retrieval_candidate'
                        assert all(r['organization_source']['input_role']==expected for r in found)
                    cached=await client.call_tool('read_source_document',{'request':query})
                    assert cached.structured_content['items'][0]['retrieval']['cache_hit']
                    request={'source_space':'organization','operation':'read','document_id':tail['parent_document_id'],
                             'node_id':tail['node_id'],'max_characters':16000}
                    read=await client.call_tool('read_source_document',{'request':request})
                    assert not read.is_error
                    passage=read.structured_content['items'][0]
                    assert passage['passage']==tail['content'] and not passage['truncated']
                    assert passage['original_source']==tail['original_source']
                    if indexed:
                        from retrieval.library_node_recovery import node_body
                        async with Client(build_organization_evidence_server(reader),raise_exceptions=False) as original_client:
                            directory=await original_client.call_tool('read_organization_evidence',{'resource_id':resources[sid]})
                            assert not directory.is_error and directory.structured_content['text_scope']=='indexed_node_directory'
                            originals=bundle['node_recovery']['nodes']
                            selected_originals=(originals if all(n['node_kind']=='read_item' for n in originals)
                                                else [next(n for n in originals if n['node_kind']==kind)
                                                      for kind in sorted({n['node_kind'] for n in originals})])
                            for original in selected_originals:
                                kind=original['node_kind']
                                offset=0;parts=[]
                                while True:
                                    response=await original_client.call_tool('read_organization_evidence',{
                                        'resource_id':resources[sid],'node_id':original['node_id'],'offset':offset,'limit':16000})
                                    assert not response.is_error
                                    data=response.structured_content
                                    assert data['original_node']=={k:v for k,v in original.items() if k not in {'content','model_text'}}
                                    assert not data['complete_original_document'] and data['text_scope']=='original_indexed_node'
                                    parts.append(data['text']);offset=data['next_offset']
                                    if offset is None:break
                                assert ''.join(parts)==node_body(original)
                                node_reads.append({'source_id':sid,'node_id':original['node_id'],'kind':kind,
                                                   'characters':len(node_body(original)),'read_pages':len(parts)})
                    results.append({'source_id':sid,'candidate_chunks':len(leaves),
                        'tail_char_start':None if indexed else tail['original_source']['source_char_start'],
                        'position_basis':'original_indexed_node_characters' if indexed else 'parsed_source_text',
                        'tail_sha256':passage['content_sha256'],'readback':passage['readback'],'cache_hit':True,
                        'index_digest':found[0]['retrieval']['index_digest'],'provider_calls':found[0]['retrieval']['provider_calls']})
                    s.save('complete-source-progress',{'sources':results,'status':'running'})
        ids=list(bundles)
        batch_size=len(ids) if unified_scope else 12
        if unified_scope:assert len(ids)>12
        global_searches=[]
        for start in range(0,len(ids),batch_size):
            batch=bundles.subset(ids[start:start+batch_size])
            payload={'id':str(uuid4()),'title':'Complete inputs','question':'Read the selected complete disclosures.',
                     'research_as_of':'2026-09-23','resource_ids':[resources[sid] for sid in batch]}
            if unified_scope:
                payload['retrieval_resource_ids']=payload['resource_ids']
                payload['resource_ids']=payload['resource_ids'][:2]
            with diagnostic.phase('prepare_all_candidates'):
                original=api('POST',f'/projects/{project}/research-drafts',payload)
            reader=bind(project,original)
            with diagnostic.phase('authorized_original_projection',profile=global_probe):
                _,nodes=preparation_nodes(reader,workbench_url='http://localhost')
            assert len(nodes)==sum(len(bundle['chunks']) for bundle in batch.values())
            release=str(uuid4())
            with diagnostic.phase('publish_index'):
                # Memory-mapped test inputs must still be the exact verified
                # successful receipts at publication; they are not ACL caches.
                verify_intake_files()
                publish_prepared_index(indices,org,nodes,vectors.projected(nodes),queries,
                    model=model,provenance={'source_intake_sha256':sha256((root/'result.json').read_bytes()).hexdigest()},
                    release_id=release,projection=PROJECTION)
            with diagnostic.phase('register_index_against_all_originals'):
                contract=s.request(s.bff,'POST',f'/api/v1/asset-workspace/organization-projects/{project}/research-drafts/{original["id"]}/retrieval-releases/{release}/register',json={})
            payload.update(id=str(uuid4()),retrieval_release_id=release)
            frozen=api('POST',f'/projects/{project}/research-drafts',payload)
            assert frozen['manifest']['retrieval_index']==contract
            assert api('GET',f'/projects/{project}/research-drafts/{original["id"]}')==original
            reader=bind(project,frozen)
            nav=OrganizationSourceNavigation(reader,workbench_url='http://localhost',retrieval_root=indices)
            if unified_scope:
                assert len(frozen['manifest']['input_selection']['selected_resource_ids'])==2
                assert len(frozen['manifest']['inputs'])==len(batch)
                query={'source_space':'organization','operation':'search','query':next(iter(queries))}
                with diagnostic.phase('global_search_cold',profile=global_probe):
                    found=nav.navigate(query)
                assert found.items
                assert all(r['original_source']['source_id'] in batch for r in found.items)
                with diagnostic.phase('global_search_warm',profile=global_probe):
                    cached=nav.navigate(query)
                assert cached.items[0]['retrieval']['cache_hit']
                global_searches.append({'query':query,'retrieval':found.items[0]['retrieval'],
                    'returned_sources':list({r['original_source']['source_id'] for r in found.items}),
                    'authorized_sources':len(batch),'indexed_chunks':len(nodes),'cache_hit':True})
            first_result=len(results)
            # Global plumbing probe still publishes/verifies every original and
            # ranks the entire scope. Per-source filtered search is sampled by
            # original contract; prior type-specific acceptance remains separate.
            read_batch=batch
            if global_probe:
                samples={}
                for sid,bundle in batch.items():
                    kind=('node' if 'node_recovery' in bundle else 'archive' if 'archive_recovery' in bundle else 'text')
                    samples.setdefault(kind,sid)
                read_batch=batch.subset(list(dict.fromkeys([*list(batch)[:2],*samples.values(),list(batch)[-1]])))
            with diagnostic.phase('sampled_original_readback',profile=global_probe):
                asyncio.run(exercise(read_batch,nodes,nav,reader))
            # Revoke a candidate that was NOT explicitly selected; all current
            # dependencies must still protect cached search, reports and reads.
            revoke_sid=list(batch)[-1] if unified_scope else next(iter(batch))
            first=resources[revoke_sid]
            current=s.request(s.bff,'GET',f'/api/v1/asset-workspace/spaces/resources/{first}')
            api('POST',f'/resources/{first}/revoke',{'revision':current['permission_revision']})
            with pytest.raises(OrganizationExecutionUnavailable):nav.navigate(results[first_result]['readback'])
            with pytest.raises(OrganizationExecutionUnavailable):nav.navigate({'source_space':'organization','operation':'search','query':next(iter(queries))})
            if 'node_recovery' in batch[revoke_sid]:
                original=batch[revoke_sid]['node_recovery']['nodes'][0]
                with pytest.raises(OrganizationExecutionUnavailable):reader.read_text(first,node_id=original['node_id'])
            contracts.append(contract)
        verify_intake_files()
        s.save('complete-source-result',{'status':'passed','sources':results,'frozen_contracts':contracts,
            'revoked_cache_and_readback_denied':True,'provider_calls':0,'research_runs':0,
            'recall_or_capacity_evaluation':False,'candidate_chunks':len(vectors),'identity':'qualification login',
            'max_explicit_sources_per_draft':12,'separate_index_batches':len(contracts),
            'corpus_wide_retrieval':unified_scope,'corpus_scope':'selected intake artifact only',
            'global_probe':global_probe,'published_sources':len(bundles),'searched_sources':len(bundles),
            'per_source_filtered_readback_count':len(results),
            'global_searches':global_searches,'non_selected_candidate_revocation_tested':unified_scope,
            'captures':captures,'node_reads':node_reads,'date_denials':date_denials,'query_is_storage_probe':storage_probe})
    except BaseException as exc:
        s.save('failure',{'error_type':type(exc).__name__,'published_sources':len(captures) if 'captures' in locals() else 0,
                          'phase_diagnostics':'phase-diagnostics.json','provider_calls':0})
        raise
    finally:
        for process in s.processes:
            if process.poll() is None: process.terminate();process.wait(timeout=20)
        for log in s.logs: log.close()
        try:s.compose('logs','--no-color')
        finally:s.compose('stop','-t','5');s.bff.close();s.native.close()
