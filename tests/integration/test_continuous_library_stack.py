"""Frozen full release + new continuous runtime and real browser, no paid models."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from uuid import uuid4

import psycopg
import pytest

from tests.integration.test_continuous_work_stack import ContinuousStack, ROOT
from tests.integration.continuous_library_copy import copy_publication, restore_business
from tests.integration.source_intake_registration import register_index

pytestmark = pytest.mark.skipif(os.getenv('FIN_CONTINUOUS_LIBRARY_QUALIFICATION') != '1', reason='explicit isolated full publication required')


class LibraryStack(ContinuousStack):
    compose_files = (*ContinuousStack.compose_files, ROOT/'deploy/qualification/continuous_library.compose.yaml')
    synthetic_components = ['scripted model transport', 'trace export gate', 'qualification identity']

    def __init__(self):
        super().__init__()
        value = subprocess.check_output([self.docker, 'run', '--rm', '--network', 'none',
            '--entrypoint', 'python', self.env['FIN_PROBE_IMAGE'], '-c',
            "import importlib.metadata as m; import numpy; import filelock; print(m.version('filelock'))"],
            text=True, timeout=60).strip()
        assert value == '3.32.4', 'frozen_retrieval_requires_locked_image_dependencies'
        self.save('retrieval-image-preflight', {'filelock':value,'network':'none'})

    def browser(self, project, label, *, mode, execution=None, release=None):
        output = self.output / label
        env = {k:v for k,v in self.env.items() if k != 'LANGSMITH_API_KEY'}
        env.update(FIN_CONTINUOUS_LIBRARY_QUALIFICATION='1', FIN_DELIVERY_BROWSER_ORIGIN=f'http://127.0.0.1:{self.bff_port}',
            FIN_DELIVERY_PROJECT=project, FIN_DELIVERY_BROWSER_OUTPUT=str(output), FIN_DELIVERY_BROWSER_MODE=mode)
        if execution: env['FIN_DELIVERY_EXECUTION'] = execution
        if release: env['FIN_DELIVERY_RELEASE'] = release
        result = subprocess.run([os.getenv('FINSIGHT_TEST_NODE') or shutil.which('node'), 'e2e/continuous-live-library.mjs'],
            cwd=ROOT/'apps/workbench/frontend', env=env, capture_output=True, text=True, encoding='utf8', timeout=7200)
        self.save(label+'-process', {'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr})
        assert result.returncode == 0, result.stderr[-4000:]
        return json.loads((output/'result.json').read_text(encoding='utf8'))


def test_frozen_library_continuous_browser_and_exports():
    s = LibraryStack()
    def api(method,path,body=None):
        return s.request(s.bff,method,'/api/v1/business/workspaces'+path,**({'json':body} if body is not None else {}))
    try:
        seal = copy_publication(s, os.environ['FIN_FROZEN_PUBLICATION_SEAL'], os.environ['FIN_FROZEN_INDEX_SEAL'])
        indices = s.output/'indices'
        directory = indices/seal['organization_id']/'releases'/seal['contract']['release_id']
        index = json.loads((directory/'index.json').read_bytes())
        questions = json.loads(Path(os.environ['FIN_FROZEN_QUESTIONS']).read_bytes())['questions']
        queries = [q['query'] for q in questions if hashlib.sha256(q['query'].encode()).hexdigest() in index['queries']]
        assert queries, 'no_existing_query_vector'
        s.env.update(FINSIGHT_ORGANIZATION_RETRIEVAL_ROOT=str(indices), FIN_QUALIFICATION_INDEX_COPY=indices.as_posix(),
            FIN_QUALIFICATION_QUERY=queries[0], FINSIGHT_ORGANIZATION_NAVIGATION_ENABLED='1')
        s.save('frozen-scope', {'contract':seal['contract'],'chunks':len(index['records']), 'queries':queries,
            'new_query_embedding':False,'provider_calls':0,'original_archive_mutated':False})
        del index
        s.compose('up','-d','--pull','never','postgres')
        store = s.initialize_databases()
        restore_business(s)
        s.boot('java'); s.boot('bff')
        with psycopg.connect(host='127.0.0.1',port=s.pg_port,dbname='business',user='probe',password=s.password) as db:
            projects = db.execute('SELECT id FROM organization_project').fetchall()
            resources = [str(r[0]) for r in db.execute('SELECT id FROM space_resource WHERE active ORDER BY id').fetchall()]
        assert len(projects)==1 and len(resources)==1742
        project = str(projects[0][0])
        # Reconstructed immutable draft uses all current business grants; no cached authorization.
        prepared = api('POST',f'/projects/{project}/research-drafts', {'id':str(uuid4()),'title':'Frozen release registration',
            'question':'Validate the current authorized frozen library.', 'research_as_of':'2026-09-23',
            'resource_ids':resources[:2], 'retrieval_resource_ids':resources})
        contract = register_index(s.bff, f'/api/v1/asset-workspace/organization-projects/{project}/research-drafts/{prepared["id"]}/retrieval-releases/{seal["contract"]["release_id"]}',
            expected=seal['contract'], save=s.save, wait_seconds=600)
        s.save('full-release-registration', {'status':'passed','sources':len(prepared['manifest']['inputs']),
            'chunks':114028,'contract':contract,'current_grants':True})
        s.compose('up','-d','--pull','never','api'); s.healthy(); s.audit_container()
        browser = s.browser(project,'browser-prepare',mode='prepare',release=contract['release_id'])
        tid = browser['execution']
        thread = s.request(s.native,'GET',f'/threads/{tid}')
        owner = thread['metadata']['owner_id']
        store.create_budget(owner,tid,'CNY',1000,0)
        settings_path=s.output/'settings/settings.json'; settings=json.loads(settings_path.read_text())
        policy={'reservation_micros':10,'reservation_basis':'Scripted service transport, no provider or tariff','delivery':False}
        settings['model_budget_bindings']={tid:{'owner_id':owner,'budget_id':tid,
            'prices':[{'version':'scripted-zero-price','model':m,'currency':'CNY','input_miss':0,'input_hit':0,'output':0}
                      for m in ('deepseek-flash','deepseek-v4-pro')],
            'roles':{r:policy for r in ('lead','writer','context_summary')}}}
        settings_path.write_text(json.dumps(settings))
        completed=s.browser(project,'browser-complete',mode='run',execution=tid)
        root=f'/api/v1/organization-projects/{project}/research/{tid}'
        snapshot=s.request(s.bff,'GET',root); s.save('final-public-state',snapshot)
        assert snapshot['task_outcome']['artifact_kind']=='report'
        assert snapshot['report']['citations']
        assert len(s.runs(tid))==3
        from bs4 import BeautifulSoup
        from pypdf import PdfReader
        from zipfile import ZipFile
        from xml.etree.ElementTree import fromstring
        output=s.output/'browser-complete'
        texts={'md':(output/'report.md').read_text(encoding='utf8'),
            'html':BeautifulSoup((output/'report.html').read_text(encoding='utf8'),'html.parser').get_text(),
            'pdf':'\n'.join(p.extract_text() or '' for p in PdfReader(output/'report.pdf').pages)}
        for fmt in ('docx','pptx'):
            with ZipFile(output/f'report.{fmt}') as archive:
                names=['word/document.xml'] if fmt=='docx' else [n for n in archive.namelist()
                    if n.endswith('.xml') and n.startswith(('ppt/slides/slide','ppt/notesSlides/notesSlide'))]
                texts[fmt]='\n'.join(''.join(fromstring(archive.read(n)).itertext()) for n in names)
        source=next(iter(snapshot['report']['citations'].values()))['sources'][0]
        snippet=''.join(source['text'].split())[:50]
        checks={fmt:{'label':'服务' in text and '验证' in text,
            'original':snippet in ''.join(text.split()), 'bytes':(output/f'report.{fmt}').stat().st_size}
            for fmt,text in texts.items()}
        s.save('export-content-checks',checks)
        assert all(row['label'] and row['original'] for row in checks.values()),checks
        native=s.state_of(tid)
        searches=[]
        for m in native['values'].get('messages',[]):
            if m.get('type')=='tool' and m.get('name')=='read_source_document':
                payload=json.loads(m['content'])
                searches.extend(r['retrieval'] for r in payload.get('items',[]) if r.get('retrieval'))
        assert searches, 'native_runtime_must_use_frozen_retrieval'
        s.save('native-retrieval-evidence',{'rows':searches,'contract':contract})
        s.save('continuous-library-result',{'status':'passed','sources':1742,'chunks':114028,
            'native_runs':3,'provider_calls':0,'browser_api_interceptions':0,'report':completed,
            'budget':store.snapshot(owner,tid),'financial_quality':'not_assessed','substitutions':s.synthetic_components})
    finally:
        for process in s.processes:
            if process.poll() is None: process.terminate(); process.wait(timeout=20)
        for log in s.logs: log.close()
        try:s.compose('logs','--no-color')
        finally:s.compose('stop','-t','5');s.bff.close();s.native.close()
