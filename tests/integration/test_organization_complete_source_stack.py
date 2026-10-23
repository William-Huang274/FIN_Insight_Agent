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
from tests.integration.source_intake_runtime import CompleteSourceStack
from tests.integration.test_java_intake_native import wait_for
from tests.integration.source_intake_diagnostics import SourceBundles, SourceVectors, PhaseDiagnostics, file_sha256, source_coverage, source_readback_targets
from tests.integration.source_intake_checkpoint import load_checkpoint, save_checkpoint, restore_checkpoint, verify_restored_publication

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
    batch_binding=None
    full_intake_sources=len(intake['sources'])
    if os.getenv('FIN_COMPLETE_SOURCE_BATCH_PLAN'):
        from scripts.engineering.source_intake_batches import select_batch
        plan_path=Path(os.environ['FIN_COMPLETE_SOURCE_BATCH_PLAN'])
        plan=json.loads(plan_path.read_text(encoding='utf8'))
        batch_binding=json.loads(os.environ['FIN_COMPLETE_SOURCE_BATCH_BINDING'])
        number=int(os.environ['FIN_COMPLETE_SOURCE_BATCH_NUMBER'])
        assert batch_binding['batch_number']==number
        assert batch_binding['plan_sha256']==file_sha256(plan_path)
        assert Path(plan['intake_root']).resolve()==root
        intake['sources']=select_batch(plan,intake,number,file_sha256(root/'result.json'))
    dataset=Path(os.environ['FIN_COMPLETE_SOURCE_QUESTIONS'])
    questions=json.loads(dataset.read_text(encoding='utf8'))['questions']
    storage_probe=os.getenv('FIN_COMPLETE_SOURCE_STORAGE_PROBE')=='1'
    unified_scope=os.getenv('FIN_COMPLETE_SOURCE_UNIFIED_SCOPE')=='1'
    global_probe=os.getenv('FIN_COMPLETE_SOURCE_GLOBAL_PROBE')=='1'
    lifecycle_probe=os.getenv('FIN_COMPLETE_SOURCE_LIFECYCLE_PROBE')=='1'
    graph_probe=os.getenv('FIN_COMPLETE_SOURCE_GRAPH_PROBE')=='1'
    graph_checks=[]
    lifecycles=[]
    if lifecycle_probe:
        assert global_probe and unified_scope
    if batch_binding:
        assert storage_probe and not unified_scope and not global_probe
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
    additional_queries={}
    selected_questions={sid:(questions[0] if storage_probe else next(q for q in questions if q['evidence'][0]['source_id']==sid)) for sid in bundles}
    with ReadOnlyReceipts(Path(os.environ['FIN_COMPLETE_SOURCE_QUERY_CACHE'])) as cache:
        client=CachedRetrieval(cache,SimpleNamespace(embedding_model=model,rerank_model='qwen3-rerank'),namespace)
        for q in selected_questions.values():
            saved=cache.get(client.key('embedding',[q['query']]))
            assert saved and saved['status']=='completed' and saved['result']['model']==model
            queries[q['query']]=saved['result']['values'][0]
        if global_probe:
            for q in questions:
                if q['query'] in queries:
                    continue
                saved=cache.get(client.key('embedding',[q['query']]))
                if saved and saved['status']=='completed' and saved['result']['model']==model:
                    additional_queries[q['query']]=saved['result']['values'][0]
                    break
            assert additional_queries, 'cross-query probe requires two existing successful query vectors'
    semantic_rows = []
    semantic_dataset = None
    if os.getenv('FIN_COMPLETE_SOURCE_SEMANTIC_DATASET'):
        from scripts.engineering.organization_recall_evaluation import validate_questions
        semantic_path = Path(os.environ['FIN_COMPLETE_SOURCE_SEMANTIC_DATASET'])
        semantic_dataset = json.loads(semantic_path.read_text(encoding='utf8'))
        validate_questions(semantic_dataset, bundles)
        semantic_split = os.environ['FIN_COMPLETE_SOURCE_SEMANTIC_SPLIT']
        assert semantic_split in {'development', 'heldout'}
        semantic_rows = [row for row in semantic_dataset['questions'] if row['split'] == semantic_split]
        assert unified_scope and global_probe and lifecycle_probe and graph_probe and semantic_rows
        assert semantic_dataset['intake_sha256'] == file_sha256(root/'result.json')
        assert semantic_dataset['scope']['candidate_sources'] == len(bundles)
        assert semantic_dataset['scope']['candidate_chunks'] == len(vectors)
        # Successful receipts are prepared separately under an explicit budget.
        # This service test remains loopback-only and cannot submit paid calls.
        with ReadOnlyReceipts(Path(os.environ['FIN_COMPLETE_SOURCE_SEMANTIC_CACHE'])) as cache:
            client = CachedRetrieval(cache, SimpleNamespace(embedding_model=model, rerank_model='qwen3-rerank'), namespace)
            for row in semantic_rows:
                saved = cache.get(client.key('embedding', [row['query']]))
                assert saved and saved['status'] == 'completed' and saved['result']['model'] == model
                additional_queries[row['query']] = saved['result']['values'][0]
    checkpoint_path=os.getenv('FIN_COMPLETE_SOURCE_RESUME')
    pause_after=int(os.getenv('FIN_COMPLETE_SOURCE_PAUSE_AFTER','0'))
    write_checkpoint=os.getenv('FIN_COMPLETE_SOURCE_WRITE_CHECKPOINT')=='1' or pause_after>0
    checkpoint_binding=None; restored=None; replay_review=None
    if checkpoint_path or write_checkpoint:
        from scripts.engineering.source_intake_batches import baseline
        checkpoint_binding={'baseline':baseline(),'intake_sha256':file_sha256(root/'result.json'),
            'source_ids':list(bundles),'storage_probe':storage_probe,'unified_scope':unified_scope,
            'global_probe':global_probe,'batch_binding':batch_binding,
            'query_vectors_sha256':sha256(json.dumps(queries,sort_keys=True).encode()).hexdigest()}
        if checkpoint_path:
            review_path=os.getenv('FIN_COMPLETE_SOURCE_REPLAY_REVIEW')
            if review_path:
                replay_review=json.loads(Path(review_path).read_text(encoding='utf8'))
                import subprocess
                source=replay_review['source_baseline']['git_head']
                target=checkpoint_binding['baseline']['git_head']
                diff=subprocess.check_output(['git','diff','--binary',source,target])
                paths=subprocess.check_output(['git','diff','--name-only',source,target],text=True).splitlines()
                if sha256(diff).hexdigest()!=replay_review['git_diff_sha256'] or paths!=replay_review['changed_paths']:
                    raise ValueError('checkpoint_replay_review_diff_mismatch')
            restored=load_checkpoint(checkpoint_path,checkpoint_binding,replay_review)
        completed=len(restored['publication']['captures']) if restored else 0
        if pause_after and not completed<pause_after<=len(bundles):
            raise ValueError('checkpoint_pause_must_advance_within_full_scope')
    s=CompleteSourceStack()
    diagnostic=PhaseDiagnostics(s.save)
    indices=s.output/'indices'
    s.env['FINSIGHT_ORGANIZATION_RETRIEVAL_ROOT']=str(indices)
    monkeypatch.setenv('FINSIGHT_BUSINESS_SHARED_SECRET',s.shared)
    s.save('complete-source-scope',dict(sources=list(bundles),candidate_chunks=len(vectors),
        login='qualification identity; not real OIDC validation',services=['BFF','Java','PostgreSQL'],
        tools='production organization MCP on host; native Agent run not started',
        recall_or_capacity_evaluation=False,provider_calls=0,
        query_scope='reused query for storage/authorization plumbing, no relevance assertion' if storage_probe else 'historical source queries'))
    if semantic_rows:
        s.save('semantic-scope', {'dataset_sha256': file_sha256(semantic_path),
            'evaluation_role': semantic_dataset['evaluation_role'], 'split': semantic_split,
            'question_ids': [r['id'] for r in semantic_rows], 'sources': len(bundles), 'chunks': len(vectors),
            'scope': 'complete frozen organization grant; no document prefilter',
            'provider_calls_in_service_run': 0, 'label_validation': 'original_digest_and_quote',
            'financial_answer_quality_assessed': False, 'capacity_assessed': False})
    def api(method,path,body=None):
        if method == 'POST' and path.endswith('/access'):
            # Access grants are an internal Java contract, deliberately absent
            # from the browser BFF allowlist. Use its normal actor delegation.
            route='/v1/workspaces'+path
            raw=b'' if body is None else json.dumps(body,separators=(',',':')).encode()
            with httpx.Client(trust_env=False,timeout=30) as client:
                return s.request(client,method,f'http://127.0.0.1:{s.java_port}'+route,
                    content=raw,headers={'Content-Type':'application/json',
                    'Authorization':'Bearer '+delegate('oidc:alice',method,route,raw)})
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
        if restored:
            restore_checkpoint(s,checkpoint_path,restored)
        s.boot('java');s.boot('bff')
        with psycopg.connect(host='127.0.0.1',port=s.pg_port,dbname='business',user='probe',password=s.password) as db:
            settings={name:db.execute('SHOW '+name).fetchone()[0] for name in (
                'shared_buffers','work_mem','maintenance_work_mem','max_connections','max_parallel_workers',
                'fsync','synchronous_commit','full_page_writes')}
            assert all(settings[name]=='on' for name in ('fsync','synchronous_commit','full_page_writes'))
            s.save('postgres-settings',settings)
        assets=AssetWorkspace(s.state/'project-library')
        resources={};captures=[];date_denials=[];source_refs=[]
        if restored:
            prior=restored['publication']
            org,space,project,private=[prior[k] for k in ('org','space','project','private')]
            shared_assets=AssetWorkspace(s.state/'project-library'/'organization-assets')
            verify_restored_publication(api,assets,shared_assets,bundles,prior)
            resources=dict(prior['resources']);captures=list(prior['captures']);source_refs=list(prior['source_refs'])
            s.save('publication-restore',{'status':'verified','sources':len(captures),
                'origin_attempt':restored['origin_attempt'],'manifest_sha256':file_sha256(Path(checkpoint_path)/'manifest.json'),
                'replay_review':replay_review,
                'scope':'restored fixture, not uninterrupted run; all retrieval stages execute again'})
        else:
            org,space,project,private=[str(uuid4()) for _ in range(4)]
            api('POST','/organizations',{'id':org,'name':'Complete source intake','display_name':'Owner'})
            api('POST','/spaces',{'id':space,'organization_id':org,'name':'Full parsed disclosures'})
            api('POST','/projects',{'id':project,'organization_id':org,'name':'Source compatibility','description':'No recall claim'})
            assets.library.save('oidc:alice',0,{'projects':[{'id':private,'name':'Public originals'}],'assignments':{},'pinned':[]})
        def checkpoint():
            verify_intake_files()
            grants={sid:api('POST',f'/projects/{project}/resources/{rid}/access') for sid,rid in resources.items()}
            payload=dict(org=org,space=space,project=project,private=private,resources=resources,
                captures=captures,source_refs=source_refs,grants=grants,
                project_state=api('GET',f'/projects/{project}'),members=api('GET',f'/organizations/{org}/members'))
            return save_checkpoint(s,checkpoint_binding,payload)
        for sid,bundle in bundles.items():
            if sid in resources:
                continue  # Verified again above against restored Java ACL and both original stores.
            source_started=perf_counter()
            # Same maintained capture service as POST /captures; no payload supplied as source facts.
            request=CaptureRequest(project_id=private,title=bundle['source']['title'][:120],selection={
                'kind':'library_source','document_id':sid,'snapshot':intake['library_sha256']})
            saved=save_capture(assets,'oidc:alice',request,None,None,library)
            assert save_capture(assets,'oidc:alice',request,None,None,library)['document_id']==saved['document_id']
            ref=assets.document_version('oidc:alice',private,saved['document_id'])['ref']
            source_refs.append(ref)
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
            if pause_after==len(captures):
                path=checkpoint()
                s.save('publication-pause',{'status':'publication_checkpoint_only','sources':len(captures),
                    'required_sources':len(bundles),'checkpoint':str(path),'S2_passed':False,'provider_calls':0})
                return
        # Still verify complete catalogue visibility, once over the final scope.
        catalog_refs=[v['ref'] for a in assets.catalog('oidc:alice',private)['items'] for v in a['versions']]
        assert len(catalog_refs)==len(captures)
        assert len({ref['version_id'] for ref in catalog_refs})==len(captures)
        assert sorted(catalog_refs,key=lambda ref:ref['version_id'])==sorted(source_refs,key=lambda ref:ref['version_id'])
        if write_checkpoint:
            checkpoint()
            s.boot('java');s.boot('bff')
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
        async def exercise(batch,targets,nav,reader):
            async with Client(build_organization_source_server(nav), raise_exceptions=False) as client:
                for sid,bundle in batch.items():
                    indexed='node_recovery' in bundle
                    tail=targets[sid]['tail']
                    assert targets[sid]['position_key']==('char_end' if indexed else 'source_char_end')
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
                    results.append({'source_id':sid,'candidate_chunks':targets[sid]['candidate_chunks'],
                        'tail_char_start':None if indexed else tail['original_source']['source_char_start'],
                        'position_basis':'original_indexed_node_characters' if indexed else 'parsed_source_text',
                        'tail_sha256':passage['content_sha256'],'readback':passage['readback'],'cache_hit':True,
                        'index_digest':found[0]['retrieval']['index_digest'],'provider_calls':found[0]['retrieval']['provider_calls']})
                    s.save('complete-source-progress',{'sources':results,'status':'running'})
        # The publication checkpoint retains its exact original query binding.
        # Additional verification queries belong to this new index/run only,
        # after restoration and current-authority validation have completed.
        s.save('retrieval-query-scope',{
            'publication_queries_sha256':sha256(json.dumps(queries,sort_keys=True).encode()).hexdigest(),
            'additional_queries':[{ 'query':q, 'vector_sha256':sha256(json.dumps(v).encode()).hexdigest()}
                                  for q,v in additional_queries.items()],
            'source':'existing_successful_query_receipts','provider_calls':0})
        queries.update(additional_queries)
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
            graph_sources=None
            if graph_probe:
                from sec_agent.research_foundation.organization_graph_index import preparation_graph
                graph_sources=preparation_graph(reader)
            with diagnostic.phase('publish_index'):
                # Memory-mapped test inputs must still be the exact verified
                # successful receipts at publication; they are not ACL caches.
                verify_intake_files()
                publish_prepared_index(indices,org,nodes,vectors.projected(nodes),queries,
                    model=model,provenance={'source_intake_sha256':sha256((root/'result.json').read_bytes()).hexdigest()},
                    release_id=release,projection=PROJECTION,graph_sources=graph_sources)
            # Registration and cold searches reconstruct authorized originals.
            # Do not keep a second full corpus alive in this driver.
            indexed_chunks=len(nodes)
            targets=source_readback_targets(nodes)
            assert set(targets)==set(batch)
            assert all(targets[sid]['candidate_chunks']==len(bundle['chunks']) for sid,bundle in batch.items())
            del nodes
            with diagnostic.phase('register_index_against_all_originals'):
                from tests.integration.source_intake_registration import register_index
                from sec_agent.research_foundation.organization_index_release import load_release
                expected=load_release(indices,org,release)[3]
                contract=register_index(s.bff,
                    f'/api/v1/asset-workspace/organization-projects/{project}/research-drafts/{original["id"]}/retrieval-releases/{release}',
                    expected=expected,save=s.save)
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
                original_reads=[]
                capture_checks=[]
                from sec_agent.research_foundation import project_source_captures as capture_module
                read_capture=capture_module.read_capture
                def counted_capture(*args):
                    capture_checks.append(args[1]['id'])
                    return read_capture(*args)
                monkeypatch.setattr(capture_module,'read_capture',counted_capture)
                read_storage=reader._read_storage
                def counted_read(*args):
                    original_reads.append(args[0])
                    return read_storage(*args)
                monkeypatch.setattr(reader,'_read_storage',counted_read)
                if global_probe:
                    # Run the independent full-original reference before the
                    # optimized lifecycle retains its full-scope metadata.
                    # Only bounded response/candidate IDs survive this phase;
                    # both paths still read the same frozen index and grant.
                    import gc
                    import sqlite3
                    second={**query,'query':list(queries)[1]}
                    reference=OrganizationSourceNavigation(reader,workbench_url='http://localhost',retrieval_root=indices)
                    with diagnostic.phase('global_new_query_original_reference',profile=True):
                        full=reference._navigate(second)
                    assert not full.items[0]['retrieval']['cache_hit']
                    reference_original_reads=len(original_reads)
                    assert reference_original_reads==len(capture_checks)==len(batch)
                    del reference
                    gc.collect()
                    # Do not let reference scoring prepopulate production
                    # ranking caches and turn the new-query check into a hit.
                    with sqlite3.connect(indices/org/'releases'/release/'rank-cache.sqlite') as ranks:
                        ranks.execute('DELETE FROM ranks')
                    original_reads.clear();capture_checks.clear()
                prewarm_original_reads=0
                lifecycle=None
                if lifecycle_probe:
                    from sec_agent.research_foundation.organization_retrieval_lifecycle import OrganizationRetrievalLifecycle
                    lifecycle=OrganizationRetrievalLifecycle(reader,workbench_url='http://localhost',
                        retrieval_root=indices,grant=reader._grant()[0])
                    lifecycles.append(lifecycle)
                    with diagnostic.phase('global_retrieval_prepare',profile=True):
                        lifecycle.prepare()
                    prewarm_original_reads=len(original_reads)
                    assert prewarm_original_reads==len(capture_checks)==len(batch)
                    original_reads.clear();capture_checks.clear()
                    nav=lifecycle.navigation()
                with diagnostic.phase('global_search_cold',profile=global_probe):
                    found=nav.navigate(query)
                assert found.items
                cold_original_reads=len(original_reads)
                assert cold_original_reads==(0 if lifecycle_probe else len(batch))
                cold_capture_checks=len(capture_checks)
                assert cold_capture_checks==(0 if lifecycle_probe else len(batch))
                original_reads.clear()
                capture_checks.clear()
                assert all(r['original_source']['source_id'] in batch for r in found.items)
                with diagnostic.phase('global_search_warm',profile=global_probe):
                    cached=nav.navigate(query)
                assert cached.items[0]['retrieval']['cache_hit']
                assert cached.items[0]['retrieval']['response_cache_hit']
                assert not original_reads, 'warm response unexpectedly reread source originals'
                assert not capture_checks, 'warm response unexpectedly reparsed source captures'
                # All ranking/source/preview/readback fields remain identical;
                # only the per-request cache/provider receipt may change.
                assert [{k:v for k,v in row.items() if k!='retrieval'} for row in found.items]==[
                    {k:v for k,v in row.items() if k!='retrieval'} for row in cached.items]
                cross_query=None
                if global_probe:
                    if lifecycle is not None:
                        nav=lifecycle.navigation()  # A distinct research-stage observation scope.
                    with diagnostic.phase('global_new_query_projection_reuse',profile=True):
                        reused=nav.navigate(second)
                    assert reused.items and not original_reads and not capture_checks
                    candidate_only = reused.items[0]['retrieval'].get('candidate_only',False)
                    if candidate_only:
                        assert nav._projection_cache is None
                        assert reused.items[0]['retrieval']['source_generation_original_reads']==0
                        assert 0 < reused.items[0]['retrieval']['candidate_body_reads'] <= 36
                        assert len(nav._candidate_index.rows)==len(vectors)
                    else:
                        assert reused.items[0]['retrieval']['projection_cache_hits']==len(batch)
                    assert not reused.items[0]['retrieval'].get('response_cache_hit')
                    published_lexical = reused.items[0]['retrieval']['lexical_source']=='published_release'
                    if published_lexical:
                        if not candidate_only:
                            assert nav._projection_cache.lexical_statistics.entry is None
                            assert not nav._projection_cache.include_terms
                        statistics_bytes=postings_bytes=0
                    else:
                        assert nav._projection_cache.lexical_statistics.hit
                        assert nav._projection_cache.lexical_statistics.postings_hit
                        statistics_bytes=len(nav._projection_cache.lexical_statistics.entry[1])
                        postings_bytes=nav._projection_cache.lexical_statistics.postings_bytes
                    assert not reused.items[0]['retrieval']['cache_hit']
                    assert [{k:v for k,v in row.items() if k!='retrieval'} for row in reused.items]==[
                        {k:v for k,v in row.items() if k!='retrieval'} for row in full.items]
                    for field in ('dense_node_ids','lexical_node_ids','candidate_node_ids'):
                        assert reused.items[0]['retrieval'][field]==full.items[0]['retrieval'][field]
                    cross_query={'query':second['query'],'original_reads':0,'capture_checks':0,
                        'projection_hits':0 if candidate_only else len(batch),
                        'projection_bytes':0 if candidate_only else nav._projection_cache.size,
                        'candidate_only':candidate_only,
                        'candidate_body_reads':reused.items[0]['retrieval'].get('candidate_body_reads'),
                        'published_lexical':published_lexical,
                        'lexical_statistics_hit':not published_lexical,'lexical_statistics_bytes':statistics_bytes,
                        'lexical_postings_hit':not published_lexical,'lexical_postings_bytes':postings_bytes,
                        'same_version_reference_original_reads':reference_original_reads,
                        'ranks_and_items_equal':True,'provider_calls':0}
                    original_reads.clear();capture_checks.clear()
                    if lifecycle is not None:
                        with sqlite3.connect(reader.workspace.library.documents.path) as db:
                            db.execute('CREATE TABLE lifecycle_unrelated_write (value INTEGER)')
                        with diagnostic.phase('global_background_refresh',profile=False):
                            with pytest.raises(OrganizationExecutionUnavailable,match='refresh_pending'):
                                nav.navigate(second)
                            # This is a host-side drain of a full corpus scan,
                            # not a query latency SLO. Record timeout/progress
                            # independently; ordinary queries still fail closed.
                            refresh_timeout=float(os.getenv('FIN_COMPLETE_SOURCE_REFRESH_TIMEOUT_SECONDS','300'))
                            assert 0 < refresh_timeout <= 600
                            try:
                                refresh_status=lifecycle.wait_for_refresh(refresh_timeout)
                            finally:
                                s.save('retrieval-refresh',{'timeout_seconds':refresh_timeout,
                                    **lifecycle.status(),'original_reads':len(original_reads),
                                    'capture_checks':len(capture_checks),'expected_sources':len(batch)})
                            assert refresh_status['state']=='ready' and refresh_status['generation']==2
                        assert len(original_reads)==len(capture_checks)==len(batch)
                        original_reads.clear();capture_checks.clear()
                        refreshed=nav.navigate(second)
                        assert not original_reads and not capture_checks
                        assert [{k:v for k,v in row.items() if k!='retrieval'} for row in refreshed.items]==[
                            {k:v for k,v in row.items() if k!='retrieval'} for row in full.items]
                        cross_query['background_refresh_original_reads']=len(batch)
                        cross_query['background_refresh_generation']=2
                monkeypatch.setattr(reader,'_read_storage',read_storage)
                monkeypatch.setattr(capture_module,'read_capture',read_capture)
                global_searches.append({'query':query,'retrieval':found.items[0]['retrieval'],
                    'returned_sources':list({r['original_source']['source_id'] for r in found.items}),
                    'authorized_sources':len(batch),'indexed_chunks':indexed_chunks,'cache_hit':True,
                    'prewarm_original_reads':prewarm_original_reads,'lifecycle_probe':lifecycle_probe,
                    'cold_original_reads':cold_original_reads,'warm_original_reads':0,
                    'cold_capture_checks':cold_capture_checks,'warm_capture_checks':0,
                    'cross_query_projection':cross_query,
                    'response_cache_hit':True,'warm_result_identity_unchanged':True})
            graph_request=None
            if graph_probe:
                eligible_edges=[edge for source in graph_sources for edge in source['edges']
                    if edge['id'] in {link['edge_id'] for link in source['links']}
                    and edge['status']!='needs_semantic_review' and edge['published_at'][:10]<=payload['research_as_of']
                    and (not edge.get('valid_from') or edge['valid_from'][:10]<=payload['research_as_of'])
                    and (not edge.get('valid_to') or edge['valid_to'][:10]>=payload['research_as_of'])]
                assert eligible_edges,'explicit graph probe needs a dated source-bound edge'
                graph_request={'source_space':'organization','operation':'search','query':next(iter(queries)),
                               'entity_id':eligible_edges[0]['subject']}
                with diagnostic.phase('organization_graph_search_and_readback',profile=True):
                    graph_found=nav.navigate(graph_request)
                    receipt=graph_found.items[0]['retrieval']
                    assert receipt['graph_node_ids'] and len(receipt['graph_node_ids'])<=12
                    assert receipt['candidate_body_reads']<=48
                    evidence=receipt['graph_evidence'][0]
                    read=nav.navigate({'source_space':'organization','operation':'read',
                        'document_id':evidence['document'],'node_id':evidence['node']})
                    assert read.items[0]['result_state']=='source_bound_passage'
                    scoped=nav.navigate({**graph_request,'document_id':evidence['document']})
                    assert all(e['document']==evidence['document'] for e in scoped.items[0]['retrieval']['graph_evidence'])
                    assert nav.navigate(graph_request).items
                    assert nav.navigate(graph_request).items[0]['retrieval']['response_cache_hit']
                graph_checks.append({'request':graph_request,'graph_candidates':len(receipt['graph_node_ids']),
                    'candidate_bodies':receipt['candidate_body_reads'],'original_readback':True,'scope_filter':True,
                    'frozen_graph':contract,'provider_calls':receipt['provider_calls']})
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
            if semantic_rows:
                from scripts.engineering.organization_recall_evaluation import bind_labels, evaluate
                labels = bind_labels(semantic_rows, frozen['manifest'], resources,
                                     nav.hybrid.load_frozen(frozen['manifest'])[1])
                s.save('semantic-label-bindings', labels)
                with diagnostic.phase('semantic_hybrid_development' if semantic_split == 'development' else 'semantic_hybrid_heldout'):
                    evaluate(semantic_rows, labels, nav, index_digest=contract['index_digest'], save=s.save)
                with diagnostic.phase('semantic_graph_development' if semantic_split == 'development' else 'semantic_graph_heldout'):
                    evaluate(semantic_rows, labels, nav, index_digest=contract['index_digest'], save=s.save, graph=True)
            with diagnostic.phase('sampled_original_readback',profile=global_probe):
                asyncio.run(exercise(read_batch,targets,nav,reader))
            # Revoke a candidate that was NOT explicitly selected; all current
            # dependencies must still protect cached search, reports and reads.
            revoke_sid=list(batch)[-1] if unified_scope else next(iter(batch))
            first=resources[revoke_sid]
            current=s.request(s.bff,'GET',f'/api/v1/asset-workspace/spaces/resources/{first}')
            api('POST',f'/resources/{first}/revoke',{'revision':current['permission_revision']})
            if graph_request is not None:
                with pytest.raises(OrganizationExecutionUnavailable):nav.navigate(graph_request)
                graph_checks[-1]['revoked_cached_graph_denied']=True
            with pytest.raises(OrganizationExecutionUnavailable):nav.navigate(results[first_result]['readback'])
            with pytest.raises(OrganizationExecutionUnavailable):nav.navigate({'source_space':'organization','operation':'search','query':next(iter(queries))})
            if global_probe:
                with pytest.raises(OrganizationExecutionUnavailable):nav.navigate({
                    'source_space':'organization','operation':'search','query':list(queries)[1]})
            # exercise() last warmed this exact filtered request. Prove a
            # resident response cannot outlive revocation, not just a miss.
            last_sid=list(read_batch)[-1]
            with pytest.raises(OrganizationExecutionUnavailable):nav.navigate({
                'source_space':'organization','operation':'search',
                'document_id':targets[last_sid]['tail']['parent_document_id'],
                'query':selected_questions[last_sid]['query']})
            if 'node_recovery' in batch[revoke_sid]:
                original=batch[revoke_sid]['node_recovery']['nodes'][0]
                with pytest.raises(OrganizationExecutionUnavailable):reader.read_text(first,node_id=original['node_id'])
            contracts.append(contract)
        verify_intake_files()
        s.save('complete-source-result',{'status':'passed','sources':results,'frozen_contracts':contracts,
            'publication_restored':bool(restored),
            'cross_baseline_fixture_replay':bool(replay_review),
            'publication_source_baseline':restored['binding']['baseline'] if restored else None,
            'execution_baseline':checkpoint_binding['baseline'] if checkpoint_binding else None,
            'publication_origin_attempt':restored['origin_attempt'] if restored else str(s.output),
            'batch_binding':batch_binding,'full_intake_sources':full_intake_sources,
            'revoked_cache_and_readback_denied':True,'provider_calls':0,'research_runs':0,
            'recall_or_capacity_evaluation':False,'candidate_chunks':len(vectors),'identity':'qualification login',
            'max_explicit_sources_per_draft':12,'separate_index_batches':len(contracts),
            'corpus_wide_retrieval':unified_scope,'corpus_scope':'selected intake artifact only',
            'global_probe':global_probe,'graph_checks':graph_checks,
            **source_coverage(captures,bundles,results,global_searches),
            'global_searches':global_searches,'non_selected_candidate_revocation_tested':unified_scope,
            'captures':captures,'node_reads':node_reads,'date_denials':date_denials,'query_is_storage_probe':storage_probe})
    except BaseException as exc:
        s.save('failure',{'error_type':type(exc).__name__,'published_sources':len(captures) if 'captures' in locals() else 0,
                          'phase_diagnostics':'phase-diagnostics.json','provider_calls':0})
        raise
    finally:
        for lifecycle in lifecycles:
            lifecycle.close()
        try:s.postgres_memory_evidence()
        except Exception as exc:s.save('postgres-memory',{'status':'unavailable','error_type':type(exc).__name__})
        for process in s.processes:
            if process.poll() is None: process.terminate();process.wait(timeout=20)
        for log in s.logs: log.close()
        try:s.compose('logs','--no-color')
        finally:s.compose('stop','-t','5');s.bff.close();s.native.close()
