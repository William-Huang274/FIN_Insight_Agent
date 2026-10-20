"""One historical case across browser, authority, retrieval and native delivery."""
from hashlib import sha256
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
from uuid import uuid4
from xml.etree.ElementTree import fromstring
from zipfile import ZipFile

import httpx
import psycopg
import pytest

from apps.workbench.backend.business_transport import delegate
from sec_agent.research_foundation.asset_workspace import AssetWorkspace
from sec_agent.research_foundation.organization_execution_access import (
    OrganizationExecutionAuthority, OrganizationExecutionReader, OrganizationExecutionUnavailable)
from sec_agent.research_foundation.organization_hybrid_retrieval import preparation_nodes, publish_prepared_index
from sec_agent.research_foundation.organization_source_navigation import OrganizationSourceNavigation
from sec_agent.research_foundation.research_library import open_library
from tests.integration.test_organization_delivery_stack import DeliveryStack
from tests.integration.test_organization_graph_native import ROOT

pytestmark = pytest.mark.skipif(os.getenv('FIN_HISTORICAL_DELIVERY_QUALIFICATION') != '1',
    reason='explicit isolated historical delivery qualification required')


class HistoricalDeliveryStack(DeliveryStack):
    compose_files = (*DeliveryStack.compose_files, ROOT/'deploy/qualification/historical_delivery.compose.yaml')
    graph_fixture = ROOT/'tests/integration/fixtures/historical_delivery_graph.py'
    registered_graph = '/probe/historical_delivery_graph.py:graph'
    synthetic_components = ['qualification identity', 'scripted model decisions', 'labelled static report producer']

    def browser(self, project, label, **kwargs):
        result = super().browser(project, label, **kwargs)
        if kwargs.get('mode') == 'denied':
            return result
        from pypdf import PdfReader
        from bs4 import BeautifulSoup
        output = self.output/label
        spec = json.loads((self.historical/'case.json').read_text(encoding='utf8'))
        texts = {'html':BeautifulSoup((output/'report.html').read_text(encoding='utf8'),'html.parser').get_text(),
            'md':(output/'report.md').read_text(encoding='utf8'),
            'pdf':'\n'.join(page.extract_text() or '' for page in PdfReader(output/'report.pdf').pages)}
        for fmt in ('docx', 'pptx'):
            with ZipFile(output/f'report.{fmt}') as archive:
                names = ['word/document.xml'] if fmt == 'docx' else [
                    name for name in archive.namelist() if name.endswith('.xml') and
                    name.startswith(('ppt/slides/slide', 'ppt/notesSlides/notesSlide'))]
                texts[fmt] = '\n'.join(''.join(fromstring(archive.read(name)).itertext()) for name in names)
        checks = {fmt:{'historical_text':'NVIDIA 10-K 2026' in text,
            'metric_identity':spec['metric_record_id'] in text,
            'static_label':'Engineering fixture only' in text} for fmt,text in texts.items()}
        self.save(label+'-export-content', checks)
        assert all(all(check.values()) for check in checks.values()), checks
        return result

    def __init__(self):
        super().__init__()
        self.historical = self.output/'historical'
        self.historical.mkdir()
        self.env['FIN_PROBE_HISTORICAL_ROOT'] = self.historical.as_posix()
        self.env['FINSIGHT_RESEARCH_LIBRARY_PATH'] = os.environ['FIN_METRIC_PUBLIC_LIBRARY']
        paths = ['tests/integration/test_historical_delivery_stack.py',
            'tests/integration/test_organization_delivery_stack.py',
            'tests/integration/fixtures/historical_delivery_graph.py',
            'tests/integration/fixtures/organization_delivery_graph.py',
            'tests/integration/fixtures/organization_native_graph.py',
            'deploy/qualification/historical_delivery.compose.yaml',
            'apps/workbench/frontend/e2e/metric-card-live.mjs',
            'apps/workbench/frontend/e2e/organization-live-delivery.mjs']
        self.save('unified-source-contract', {'sources':{p:sha256((ROOT/p).read_bytes()).hexdigest() for p in paths},
            'runtime_sources':{p.relative_to(ROOT).as_posix():sha256(p.read_bytes()).hexdigest()
                for p in sorted((ROOT/'src/sec_agent').rglob('*.py'))},
            'frontend_build':{p.relative_to(ROOT/'apps/workbench/frontend/dist').as_posix():sha256(p.read_bytes()).hexdigest()
                for p in sorted((ROOT/'apps/workbench/frontend/dist').rglob('*')) if p.is_file()}})


def test_historical_case_unified_business_delivery(monkeypatch):
    hybrid_path = Path(os.environ['FIN_ORGANIZATION_HYBRID_CASES'])
    hybrid = json.loads(hybrid_path.read_text(encoding='utf8'))
    case = next(c for c in hybrid['cases'] if c['id'] == 'nvidia_concentration')
    metrics_path = Path(os.environ['FIN_STRUCTURED_SQL_CASES'])
    metrics = json.loads(metrics_path.read_text(encoding='utf8'))
    metric = next(c for c in metrics['cases'] if c['entity_id'] == 'NVIDIA')['snapshot']['rows'][0]
    assert open_library(Path(os.environ['FIN_METRIC_PUBLIC_LIBRARY'])).manifest['sha256'] == metrics['library_sha256']
    inputs_before = {str(p):sha256(p.read_bytes()).hexdigest() for p in
        [hybrid_path, metrics_path, *(hybrid_path.parent/d['file'] for d in case['documents'])]}
    for d in case['documents']:
        assert inputs_before[str(hybrid_path.parent/d['file'])] == d['sha256']
    s = HistoricalDeliveryStack()
    monkeypatch.setenv('FINSIGHT_BUSINESS_SHARED_SECRET', s.shared)
    def api(method, path, body=None):
        return s.request(s.bff, method, '/api/v1/business/workspaces'+path,
                         **({'json':body} if body is not None else {}))
    def reader(execution, digest):
        return OrganizationExecutionReader(AssetWorkspace(s.state/'project-library'/'organization-assets'),
            OrganizationExecutionAuthority(base_url=f'http://127.0.0.1:{s.java_port}', secret=s.runtime_secret,
                execution_id=execution, manifest_digest=digest))
    try:
        s.compose('up','-d','--pull','never','api'); s.healthy(); s.audit_container()
        with psycopg.connect(host='127.0.0.1',port=s.pg_port,dbname='probe',user='probe',password=s.password,autocommit=True) as db:
            db.execute('CREATE DATABASE business')
        business, web = s.boot('java'), s.boot('bff')
        org, space, project, private = [str(uuid4()) for _ in range(4)]
        api('POST','/organizations',{'id':org,'name':'Historical unified organization','display_name':'Alice'})
        api('POST','/spaces',{'id':space,'organization_id':org,'name':'Historical team inputs'})
        api('POST','/projects',{'id':project,'organization_id':org,'name':'NVIDIA historical delivery','description':'No financial quality claim'})
        assets = AssetWorkspace(s.state/'project-library')
        assets.library.save('oidc:alice',0,{'projects':[{'id':private,'name':'Historical originals'}],'assignments':{},'pinned':[]})
        text_resources = []
        for index, document in enumerate(case['documents']):
            title = f'Historical NVIDIA excerpt {index}.txt'
            assets.library.documents.add(assets.library.scope('oidc:alice',private),title,
                                         (hybrid_path.parent/document['file']).read_bytes())
            ref = next(r['current']['ref'] for r in assets.catalog('oidc:alice',private)['items'] if r['current']['title']==title)
            rid = str(uuid4())
            s.request(s.bff,'POST','/api/v1/asset-workspace/spaces/publish',json={'id':rid,'space_id':space,'ref':ref})
            api('POST',f'/projects/{project}/resources/{rid}',{'revision':api('GET',f'/projects/{project}')['revision'],'linked':True})
            text_resources.append(rid)
        # Reuse the maintained actual card UI, including persisted reply loss,
        # without creating another test system or substituting business APIs.
        output = s.output/'browser-card'
        env = {k:v for k,v in s.env.items() if k != 'LANGSMITH_API_KEY'}
        env.update(FIN_METRIC_BROWSER_QUALIFICATION='1', FIN_METRIC_PUBLICATION_REPLY_LOSS='1',
            FIN_METRIC_CASE_ENTITY='NVIDIA',FIN_METRIC_SKIP_PREPARATION='1',
            FIN_METRIC_BROWSER_ORIGIN=f'http://127.0.0.1:{s.bff_port}',FIN_METRIC_BROWSER_OUTPUT=str(output),
            FIN_METRIC_PRIVATE_PROJECT=private,FIN_METRIC_TEAM_PROJECT=project,FIN_METRIC_SPACE=space)
        run = subprocess.run([os.environ['FINSIGHT_TEST_NODE'],'e2e/metric-card-live.mjs'],
            cwd=ROOT/'apps/workbench/frontend',env=env,capture_output=True,text=True,encoding='utf8',errors='replace',timeout=240)
        s.save('card-browser-process',{'returncode':run.returncode,'stdout':run.stdout,'stderr':run.stderr})
        assert run.returncode == 0, run.stderr[-4000:]
        card_result = json.loads((output/'result.json').read_text(encoding='utf8'))
        assert len(card_result['results']) == len(card_result['recoveries']) == 1
        card = card_result['results'][0]
        # A separate host preparation grant reads the exact projection used by
        # retrieval. The unused stronger excerpt remains physically indexed.
        prepared = api('POST',f'/projects/{project}/research-drafts',{'id':str(uuid4()),'title':'Index preparation only',
            'question':case['query'],'research_as_of':hybrid['as_of'],'resource_ids':[*text_resources,card['resource_id']]})
        eid = str(uuid4())
        path = f"/v1/workspaces/projects/{project}/research-drafts/{prepared['id']}/execution-bindings"
        body = json.dumps({'id':eid,'manifest_digest':prepared['manifest_digest']},separators=(',',':')).encode()
        with httpx.Client(trust_env=False) as client:
            response = client.post(f'http://127.0.0.1:{s.java_port}'+path,content=body,
                headers={'Content-Type':'application/json','Authorization':'Bearer '+delegate('oidc:alice','POST',path,body)})
            assert response.status_code == 200, response.text
        prep_reader = reader(eid, prepared['manifest_digest'])
        _, all_nodes = preparation_nodes(prep_reader,workbench_url='https://qualification.invalid')
        docs = {d['sha256']:d for d in case['documents']}
        nodes = [n for n in all_nodes if n['content_sha256'] in docs]
        assert len(nodes) == 2
        index_digest = publish_prepared_index(s.historical/'indexes',org,nodes,
            [docs[n['content_sha256']]['vector'] for n in nodes],{case['query']:case['query_vector']},
            model=hybrid['model'],provenance=hybrid['provenance'])
        identities = {i['resource_id']:OrganizationSourceNavigation._identity(i) for i in prepared['manifest']['inputs']}
        spec = {'query':case['query'],'text_resource':text_resources[0],'text_document':identities[text_resources[0]],
            'card_resource':card['resource_id'],'card_document':identities[card['resource_id']],'metric_record_id':metric['id']}
        (s.historical/'case.json').write_text(json.dumps(spec),encoding='utf8')
        s.env.update(FIN_DELIVERY_EXPECTED_TEXT='NVIDIA 10-K 2026',FIN_DELIVERY_QUESTION=case['query'],
            FIN_DELIVERY_AS_OF=hybrid['as_of'],FIN_DELIVERY_SOURCE_TITLES=json.dumps([
                'Historical NVIDIA excerpt 0.txt', 'Historical card 1 '+metric['company_name']+'.md']))

        normal = s.browser(project,'browser-normal')
        tid, draft_id = normal['execution'], normal['draft']
        read = f'/api/v1/organization-projects/{project}/research/{tid}'
        draft = api('GET',f'/projects/{project}/research-drafts/{draft_id}')
        assert {i['resource_id'] for i in draft['manifest']['inputs']} == {text_resources[0],card['resource_id']}
        assert len(s.runs(tid)) == 2 and len(s.turns(tid)) == 7
        frozen = reader(tid,draft['manifest_digest'])
        assert frozen.read_rows(card['resource_id'])['rows'] == [metric]
        with pytest.raises(OrganizationExecutionUnavailable): frozen.read_text(text_resources[1])
        snapshot = s.request(s.bff,'GET',read)
        report, checkpoint = snapshot['report'], snapshot['checkpoint_id']
        assert len(report['citations']) == 2 and metric['id'] in report['narrative_markdown']
        sources = [c['sources'][0] for c in report['citations'].values()]
        assert {c['organization_source']['resource_id'] for c in sources} == {text_resources[0],card['resource_id']}
        for source in sources:
            assert source['organization_source']['execution_id'] == tid
            s.request(s.bff,'GET',read+'/source',params={'source_id':source['source_id']})
        nav = OrganizationSourceNavigation(frozen,workbench_url='https://qualification.invalid',retrieval_root=s.historical/'indexes')
        query = {'source_space':'organization','operation':'search','document_id':spec['text_document'],'query':case['query']}
        # The native worker already warmed the cache with the same grant.
        hits = nav.navigate(query)
        assert hits.items[0]['retrieval']['cache_hit']
        source_ids = {r['run_id'] for r in s.runs(tid)}
        for stage in ('preparation','start','continuation'):
            assert s.request(s.bff,'POST',read+'/reconcile/'+stage,json={})['status']=='received'
        assert {r['run_id'] for r in s.runs(tid)} == source_ids
        invite = str(uuid4())
        api('POST',f'/organizations/{org}/invites',{'token':invite})
        viewer = {'Authorization':'Bearer qualification-viewer'}
        s.request(s.bff,'POST','/api/v1/business/workspaces/join',headers=viewer,json={'token':invite,'display_name':'Reader'})
        api('POST',f'/projects/{project}/members',{'revision':api('GET',f'/projects/{project}')['revision'],'subject':'oidc:viewer','role':'viewer'})
        assert s.bff.get(read,headers=viewer).status_code == 404
        api('POST',f'/spaces/{space}/members',{'subject':'oidc:viewer','role':'reader'})
        # Native test-fixture state update, not a user revision workflow: retain
        # two actual PostgreSQL checkpoints so export cannot silently use latest.
        newer_report = deepcopy(report)
        newer_report['narrative_markdown'] += '\n\nSTATIC_SECOND_VERSION_MARKER'
        updated = s.request(s.native,'POST',f'/threads/{tid}/state',
            json={'values':{'report':newer_report,'report_version':2},'as_node':'initialize'})
        s.save('static-second-report-checkpoint',updated)
        newer_snapshot = s.request(s.bff,'GET',read)
        newer_checkpoint = newer_snapshot['checkpoint_id']
        assert newer_snapshot['report'] == newer_report and newer_checkpoint != checkpoint
        assert newer_snapshot['report_version'] == 2
        for process in (business,web): process.terminate(); process.wait(timeout=20)
        s.compose('stop','-t','5','api','redis','postgres'); s.compose('up','-d','--pull','never','api'); s.healthy()
        s.boot('java'); s.boot('bff')
        restored = s.request(s.bff,'GET',read)
        assert restored['report'] == newer_report and restored['checkpoint_id'] == newer_checkpoint
        old_saved = s.request(s.bff,'GET',read+'/report',params={'checkpoint_id':checkpoint})
        assert old_saved['report'] == report and old_saved['report_version'] == 1
        for label, selected, has_marker in [('old',checkpoint,False),('new',newer_checkpoint,True)]:
            downloaded = s.bff.get(read+'/report/export/html',headers=viewer,params={'checkpoint_id':selected})
            assert downloaded.status_code == 200
            assert ('STATIC_SECOND_VERSION_MARKER' in downloaded.text) is has_marker
            assert 'NVIDIA 10-K 2026' in downloaded.text and metric['id'] in downloaded.text
            (s.output/f'report-version-{label}.html').write_bytes(downloaded.content)
        s.browser(project,'browser-restarted',mode='viewer',execution=tid)
        assert nav.navigate(query).items[0]['retrieval']['cache_hit']
        assert s.bff.post(read+'/start',headers=viewer,json={}).status_code == 404
        assert s.bff.get(f'/api/v1/research-sessions/{tid}',headers=viewer).status_code == 404
        lost = s.browser(project,'browser-lost-replies',title='Synthetic lost organization reply')
        assert lost['execution'] != tid and len(s.runs(lost['execution'])) == 2 and len(s.turns(lost['execution'])) == 7
        assert len((s.state/'native-start-observations.jsonl').read_text().splitlines()) == 4
        assert len((s.state/'native-create-observations.jsonl').read_text().splitlines()) == 2
        # Revoke the card, not the quoted text: ALL-source authorization must
        # invalidate cached text retrieval and report derivatives as well.
        current = s.request(s.bff,'GET',f"/api/v1/asset-workspace/spaces/resources/{card['resource_id']}")
        api('POST',f"/resources/{card['resource_id']}/revoke",{'revision':current['permission_revision']})
        for headers in ({},viewer):
            for suffix in ['', '/report', *['/source?source_id='+c['source_id'] for c in sources],
                           *['/report/export/'+fmt for fmt in ('html','md','pdf','docx','pptx')],
                           '/runs/'+snapshot['run_id']+'/events']:
                assert s.bff.get(read+suffix,headers=headers).status_code == 404
        for selected in (checkpoint,newer_checkpoint):
            for fmt in ('md','html'):
                assert s.bff.get(read+'/report/export/'+fmt,params={'checkpoint_id':selected}).status_code == 404
        with pytest.raises(OrganizationExecutionUnavailable): nav.navigate(query)
        with pytest.raises(OrganizationExecutionUnavailable): frozen.read_rows(card['resource_id'])
        s.browser(project,'browser-revoked',mode='denied',execution=tid)
        assert {r['run_id'] for r in s.runs(tid)} == source_ids
        with psycopg.connect(host='127.0.0.1',port=s.pg_port,dbname='business',user='probe',password=s.password) as db:
            assert db.execute('SELECT count(*) FROM space_resource WHERE space_id=%s',(space,)).fetchone()[0] == 3
            assert db.execute("SELECT count(*) FROM resource_space_audit WHERE action='resource_publish' AND target=%s",(card['resource_id'],)).fetchone()[0] == 1
        assert all(sha256(Path(p).read_bytes()).hexdigest()==h for p,h in inputs_before.items())
        s.save('historical-delivery-result',{'case':case['id'],'entity':'NVIDIA','provider_calls':0,
            'native_threads':2,'native_runs':4,'scripted_responses':14,'publication_reply_loss_recovered':True,
            'native_search_miss_then_hit':True,'unselected_source_rejected':True,'metric_rows_exact':True,
            'index_digest':index_digest,'source_hashes':inputs_before,'normal_execution':tid,'lost_execution':lost['execution'],
            'draft':draft_id,'manifest_digest':draft['manifest_digest'],'checkpoint':checkpoint,
            'second_checkpoint':newer_checkpoint,'selected_html_versions_after_restart':True,
            'version_fixture':'explicit native state update; not a user revision or reviewer workflow',
            'source_resources':[text_resources[0],card['resource_id']],
            'exports':['html','md','pdf','docx','pptx'],'all_five_owned_services_restarted':True,
            'card_revocation_denies_text_cache_and_all_report_reads':True,
            'financial_quality':'not_assessed','real_oidc':'not_assessed',
            'runtime_identity_evidence':['environment.json','unified-source-contract.json'],
            'report_producer':'labelled static fixture using actual orientation receipts'})
    finally:
        for process in s.processes:
            if process.poll() is None: process.terminate(); process.wait(timeout=20)
        for log in s.logs: log.close()
        try: s.compose('logs','--no-color')
        finally: s.compose('stop','-t','5'); s.bff.close(); s.native.close()
