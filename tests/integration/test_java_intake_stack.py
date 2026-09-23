"""Optional real BFF -> Spring -> PostgreSQL -> BFF process qualification.

Requires a built JAR and Docker. Native execution alone is synthetic; all HTTP,
delegation, project/doc/receipt stores, migrations and process restarts are real.
"""
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import time
from uuid import uuid4

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.skipif(not os.environ.get('FINSIGHT_INTAKE_TEST_JAR'), reason='explicit built Java intake JAR required')


def port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0)); return s.getsockname()[1]


def ready(url, process):
    deadline = time.monotonic()+60
    while time.monotonic()<deadline:
        if process.poll() is not None: raise AssertionError('qualification process exited; inspect retained local logs')
        try:
            if httpx.get(url, timeout=1, trust_env=False).status_code in (200,401): return
        except httpx.HTTPError: pass
        time.sleep(.3)
    raise AssertionError('qualification process did not become ready')


def test_real_cross_language_stack_recovers_after_both_processes_restart(tmp_path):
    docker = os.environ.get('FINSIGHT_TEST_DOCKER') or shutil.which('docker')
    java = os.environ.get('FINSIGHT_TEST_JAVA') or shutil.which('java')
    assert docker and java
    jar = Path(os.environ['FINSIGHT_INTAKE_TEST_JAR']).resolve(); assert jar.is_file()
    name = 'finsight-intake-qualification-'+uuid4().hex[:12]
    password = secrets.token_urlsafe(24)
    processes, logs = [], []
    container = None
    def run(args): return subprocess.check_output([docker, *args], text=True, stderr=subprocess.STDOUT).strip()
    try:
        container = run(['run','--rm','-d','--name',name,'--label','finsight.qualification=java-intake',
            '-e','POSTGRES_PASSWORD='+password,'-p','127.0.0.1::5432','postgres:16.15-alpine'])
        pg_port = run(['port',container,'5432/tcp']).rsplit(':',1)[1]
        deadline=time.monotonic()+30
        while subprocess.run([docker,'exec',container,'pg_isready','-U','postgres'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode:
            assert time.monotonic()<deadline; time.sleep(.3)
        bff_port, java_port = port(),port()
        env = {**os.environ,'PYTHONPATH':os.pathsep.join([str(ROOT/'src'),str(ROOT)]),
            'FINSIGHT_INTAKE_QUALIFICATION':'1','FINSIGHT_LOCAL_STATE_ROOT':str(tmp_path/'state'),
            'FINSIGHT_BUSINESS_SHARED_SECRET':secrets.token_urlsafe(48),'FINSIGHT_BUSINESS_API_URL':f'http://127.0.0.1:{java_port}',
            'FINSIGHT_PYTHON_INTAKE_URL':f'http://127.0.0.1:{bff_port}','FINSIGHT_BUSINESS_PORT':str(java_port),
            'FINSIGHT_BUSINESS_JDBC_URL':f'jdbc:postgresql://127.0.0.1:{pg_port}/postgres',
            'FINSIGHT_BUSINESS_DB_USER':'postgres','FINSIGHT_BUSINESS_DB_PASSWORD':password}
        def start(which):
            args = [java,'-jar',str(jar)] if which=='java' else [sys.executable,'-m','uvicorn','tests.integration.fixtures.java_intake_web:app','--host','127.0.0.1','--port',str(bff_port)]
            log=(tmp_path/f'{which}-{len(logs)}.log').open('w',encoding='utf-8');logs.append(log)
            p=subprocess.Popen(args,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT);processes.append(p)
            ready(f'http://127.0.0.1:{java_port}/v1/tasks' if which=='java' else f'http://127.0.0.1:{bff_port}/auth/status',p)
            return p
        bff = start('bff'); business = start('java')
        with httpx.Client(base_url=f'http://127.0.0.1:{bff_port}',timeout=50,trust_env=False,
                headers={'X-Workbench-Request':'1'}) as client:
            project, other = str(uuid4()),str(uuid4())
            response=client.put('/api/v1/projects',json={'revision':0,'projects':[{'id':project,'name':'同名项目'},{'id':other,'name':'同名项目'}],'assignments':{},'pinned':[]})
            assert response.status_code==200,response.text
            upload=client.post(f'/api/v1/projects/{project}/documents',headers={'X-File-Name':'synthetic.txt'},content=b'Synthetic source for engineering only.').json()
            key=str(uuid4())
            body={'project_id':project,'title':'Synthetic lost response','question':'Read the synthetic document for engineering qualification only.',
                'document_ids':[upload['document_id']],'execution':{'mode':'auto','model':'default','branch_ids':[]}}
            created=client.post('/api/v1/business/tasks',headers={'Idempotency-Key':key},json=body)
            assert created.status_code==200,created.text
            task=created.json();tid=task['id'];assert task['prepare']['status']=='received' and task['thread_id']==tid
            assert client.post('/api/v1/business/tasks',headers={'Idempotency-Key':key},json=body).json()['id']==tid
            assert client.get('/api/v1/business/tasks',params={'project_id':other}).json()['items']==[]
            native=json.loads((tmp_path/'state/synthetic-native.json').read_text())
            assert len(native['threads'])==1 and native['runs']=={}
            started=client.post(f'/api/v1/business/tasks/{tid}/start',json={})
            assert started.status_code==200,started.text
            assert started.json()['start']['status']=='unknown'
            # Both processes really stop; PostgreSQL and existing receipt store remain.
            business.terminate();business.wait(timeout=20);bff.terminate();bff.wait(timeout=20)
            bff=start('bff');business=start('java')
            assert client.get(f'/api/v1/business/tasks/{tid}').json()['start']['status']=='unknown'
            assert client.post(f'/api/v1/business/tasks/{tid}/start',json={}).json()['start']['status']=='unknown'
            reconciled=client.post(f'/api/v1/business/tasks/{tid}/reconcile',json={})
            assert reconciled.status_code==200,reconciled.text
            task=reconciled.json();assert task['start']['status']=='received'
            native=json.loads((tmp_path/'state/synthetic-native.json').read_text())
            assert len(native['threads'])==1 and len(native['runs'][tid])==1
            assert task['start']['result']['run_id']==native['runs'][tid][0]['run_id']
            assert native['threads'][tid]['metadata']['research_as_of']==task['binding']['research_as_of']
            assert client.get('/api/v1/projects').json()['assignments'][tid]==project
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate();process.wait(timeout=20)
        for log in logs:log.close()
        if container:
            # Only remove the exact disposable container created by this test.
            assert run(['inspect','--format','{{index .Config.Labels "finsight.qualification"}}',container])=='java-intake'
            run(['rm','-f',container])
