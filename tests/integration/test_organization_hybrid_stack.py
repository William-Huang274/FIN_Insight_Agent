"""Historical real vectors with real BFF/Java/PostgreSQL current authority."""
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
import socket
from uuid import uuid4

import httpx
import psycopg
import pytest

from apps.workbench.backend.business_transport import delegate
from sec_agent.research_foundation.asset_workspace import AssetWorkspace
from sec_agent.research_foundation.organization_execution_access import (
    OrganizationExecutionAuthority, OrganizationExecutionReader, OrganizationExecutionUnavailable)
from sec_agent.research_foundation.organization_source_navigation import OrganizationSourceNavigation
from sec_agent.research_foundation.organization_hybrid_retrieval import preparation_nodes, publish_prepared_index
from tests.integration.test_organization_graph_native import OrganizationGraphStack
from tests.integration.test_java_intake_native import wait_for

pytestmark = pytest.mark.skipif(not os.getenv('FIN_ORGANIZATION_HYBRID_CASES'), reason='explicit historical hybrid manifest required')


def test_historical_vectors_current_authority_and_scoped_caches(monkeypatch):
    connect = socket.socket.connect
    def local_only(sock, address):
        if isinstance(address, tuple) and address[0] not in {'127.0.0.1','::1','localhost'}:
            raise AssertionError('historical_hybrid_driver_forbids_external_network')
        return connect(sock, address)
    monkeypatch.setattr(socket.socket, 'connect', local_only)
    source = Path(os.environ['FIN_ORGANIZATION_HYBRID_CASES']).resolve()
    spec = json.loads(source.read_text(encoding='utf8'))
    for case in spec['cases']:
        assert case['documents'][1]['cosine'] > case['documents'][0]['cosine']
        for doc in case['documents']:
            path = (source.parent/doc['file']).resolve()
            assert path.is_relative_to(source.parent) and sha256(path.read_bytes()).hexdigest() == doc['sha256']
    s = OrganizationGraphStack()
    environment = json.loads((s.output/'environment.json').read_text())
    environment.update(real_services=['BFF','Spring Boot','PostgreSQL'], synthetic=['qualification identity'],
        native_service_started=False, retrieval='real historical 1024d vectors and cached query embeddings; local BM25/RRF')
    s.save('environment', environment)
    monkeypatch.setenv('FINSIGHT_BUSINESS_SHARED_SECRET', s.shared)
    def api(method, path, body=None):
        return s.request(s.bff, method, '/api/v1/business/workspaces'+path,
            **({'json':body} if body is not None else {}))
    def bind(project, resources, question):
        draft, execution = str(uuid4()), str(uuid4())
        prepared = api('POST', f'/projects/{project}/research-drafts', {'id':draft, 'title':'Historical hybrid isolation',
            'question':question, 'research_as_of':spec['as_of'], 'resource_ids':resources})
        path = f'/v1/workspaces/projects/{project}/research-drafts/{draft}/execution-bindings'
        body = json.dumps({'id':execution, 'manifest_digest':prepared['manifest_digest']}, separators=(',', ':')).encode()
        with httpx.Client(trust_env=False) as client:
            result = client.post(f'http://127.0.0.1:{s.java_port}'+path, content=body,
                headers={'Content-Type':'application/json', 'Authorization':'Bearer '+delegate('oidc:alice','POST',path,body)})
            assert result.status_code == 200, result.text
        return OrganizationExecutionReader(AssetWorkspace(s.state/'project-library'/'organization-assets'),
            OrganizationExecutionAuthority(base_url=f'http://127.0.0.1:{s.java_port}', secret=s.runtime_secret,
                execution_id=execution, manifest_digest=prepared['manifest_digest']))
    results = []
    try:
        s.compose('up','-d','--pull','never','postgres')
        def ready():
            try:
                with psycopg.connect(host='127.0.0.1',port=s.pg_port,dbname='probe',user='probe',password=s.password,connect_timeout=2): return True
            except psycopg.OperationalError: return False
        wait_for(ready)
        with psycopg.connect(host='127.0.0.1',port=s.pg_port,dbname='probe',user='probe',password=s.password,autocommit=True) as db:
            db.execute('CREATE DATABASE business')
        business = s.boot('java'); s.boot('bff')
        assets = AssetWorkspace(s.state/'project-library')
        private = str(uuid4())
        assets.library.save('oidc:alice', 0, {'projects':[{'id':private,'name':'Historical copies'}], 'assignments':{},'pinned':[]})
        root = s.output/'prepared-indexes'
        for case in spec['cases']:
            tenants = []
            for label in ('A','B'):
                org, space, project = [str(uuid4()) for _ in range(3)]
                api('POST','/organizations',{'id':org,'name':'Historical '+case['id']+' '+label,'display_name':'Alice'})
                api('POST','/spaces',{'id':space,'organization_id':org,'name':'Independent publications'})
                api('POST','/projects',{'id':project,'organization_id':org,'name':'Hybrid isolation','description':'Engineering only'})
                resources = []
                for doc in case['documents']:
                    name = label+'-'+doc['file']
                    assets.library.documents.add(assets.library.scope('oidc:alice',private),name,(source.parent/doc['file']).read_bytes())
                    ref = next(x['current']['ref'] for x in assets.catalog('oidc:alice',private)['items'] if x['current']['title']==name)
                    rid = str(uuid4())
                    s.request(s.bff,'POST','/api/v1/asset-workspace/spaces/publish',json={'id':rid,'space_id':space,'ref':ref})
                    revision = api('GET',f'/projects/{project}')['revision']
                    api('POST',f'/projects/{project}/resources/{rid}',{'revision':revision,'linked':True})
                    resources.append(rid)
                all_reader = bind(project,resources,case['query'])
                _, nodes = preparation_nodes(all_reader,workbench_url='http://localhost')
                by_digest = {d['sha256']:d for d in case['documents']}
                assert len(nodes)==2 and all(n['content_sha256'] in by_digest for n in nodes)
                publish_prepared_index(root,org,nodes,[by_digest[n['content_sha256']]['vector'] for n in nodes],
                    {case['query']:case['query_vector']},model=spec['model'],provenance=spec['provenance'])
                # Each organization freezes a different versioned source, while
                # both physical indexes contain the same two historical texts.
                selected = resources[0 if label=='A' else 1]
                reader = bind(project,[selected],case['query'])
                nav = OrganizationSourceNavigation(reader,workbench_url='http://localhost',retrieval_root=root)
                request = {'source_space':'organization','operation':'search','query':case['query']}
                first = nav.navigate(request)
                assert first.items and not first.items[0]['retrieval']['cache_hit']
                assert {x['organization_source']['resource_id'] for x in first.items}=={selected}
                receipt = first.items[0]['retrieval']
                assert receipt['dense_node_ids']==receipt['candidate_node_ids']==[first.items[0]['node_id']]
                hit = nav.navigate(request)
                assert hit.items[0]['retrieval']['cache_hit']
                citation = nav.navigate(hit.items[0]['readback']).items[0]
                assert citation['content_sha256']==case['documents'][0 if label=='A' else 1]['sha256']
                assert not first.items[0]['writer_citable'] and citation['writer_citable']
                tenants.append({'org':org,'nav':nav,'reader':reader,'selected':selected,'request':request,
                    'result':first.model_dump(mode='json'),'citation':citation,'resources':resources})
            a,b = tenants
            assert a['citation']['passage_id'] != b['citation']['passage_id']
            for left,right in ((a,b),(b,a)):
                with pytest.raises(OrganizationExecutionUnavailable): left['nav'].navigate(right['citation']['readback'])
                with sqlite3.connect(root/left['org']/'rank-cache.sqlite') as db:
                    cached = db.execute('SELECT value FROM ranks').fetchall()
                assert len(cached)==1 and right['citation']['node_id'] not in cached[0][0]
                assert left['citation']['passage'] not in cached[0][0]
            if not results:
                business.terminate(); business.wait(timeout=20); business=s.boot('java')
                restored = OrganizationSourceNavigation(a['reader'],workbench_url='http://localhost',retrieval_root=root)
                restored.restore([{'status':'success','content':[a['citation']]}])
                assert restored.source(a['citation']['passage_id'])==a['citation']
                assert restored.navigate(a['request']).items[0]['retrieval']['cache_hit']
                if count := int(os.environ.get('FIN_RETRIEVAL_CAPACITY_REQUESTS', '0')):
                    from tests.integration.qualification_retrieval_load import qualify
                    qualify(s, tenants, root, count=count)
            current=s.request(s.bff,'GET',f"/api/v1/asset-workspace/spaces/resources/{a['selected']}")
            api('POST',f"/resources/{a['selected']}/revoke",{'revision':current['permission_revision']})
            with pytest.raises(OrganizationExecutionUnavailable): a['nav'].navigate(a['request'])
            with pytest.raises(OrganizationExecutionUnavailable): a['nav'].source(a['citation']['passage_id'])
            assert b['nav'].navigate(b['request']).items[0]['retrieval']['cache_hit']
            assert b['nav'].source(b['citation']['passage_id'])==b['citation']
            results.append({'id':case['id'],'stronger_unselected_cosine':case['documents'][1]['cosine'],
                'selected_cosine':case['documents'][0]['cosine'],'organizations':[{'id':t['org'],'result':t['result'],
                    'citation':t['citation']} for t in tenants], 'cross_org_read_denied':True,
                'revoked_A_cache_and_citation_denied':True,'B_still_readable':True})
            s.save('hybrid-progress',{'cases':results,'provider_calls':0})
        s.save('hybrid-result',{'status':'passed','cases':results,'provider_calls':0,'java_restart':True,
            'driver_external_network_blocked':True,
            'native_service_started':False,'financial_quality':'not_assessed','provenance':spec['provenance']})
    finally:
        for process in s.processes:
            if process.poll() is None: process.terminate(); process.wait(timeout=20)
        for log in s.logs: log.close()
        try: s.compose('logs','--no-color')
        finally: s.compose('stop','-t','5'); s.bff.close(); s.native.close()
