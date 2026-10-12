"""Real process deaths + signed HTTP + PG/SQLite; native execution is a disk fake.

No Agent Server, model, production records or automatic provider retry.
Retains fault-matrix.json and service logs under pytest's case directory.
"""
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import httpx
import psycopg
import pytest
from tests.integration.test_java_intake_stack import port, ready, ROOT

pytestmark = pytest.mark.skipif(not os.environ.get('FINSIGHT_INTAKE_TEST_JAR'), reason='explicit built Java intake JAR required')


def until(check, seconds=30):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        if check(): return
        time.sleep(.1)
    raise AssertionError('fault point not reached; inspect retained logs')


def test_process_fault_matrix_never_blindly_redispatches(tmp_path):
    docker=os.environ.get('FINSIGHT_TEST_DOCKER') or shutil.which('docker')
    java=os.environ.get('FINSIGHT_TEST_JAVA') or shutil.which('java')
    assert docker and java
    jar=Path(os.environ['FINSIGHT_INTAKE_TEST_JAR']).resolve();assert jar.is_file()
    processes,logs,rows=[],[],[];container=None
    root=tmp_path/'state';root.mkdir()
    def cli(*args):return subprocess.check_output([docker,*args],text=True,stderr=subprocess.STDOUT,timeout=60).strip()
    def record(**row):
        rows.append(row)
        (tmp_path/'fault-matrix.json').write_text(json.dumps({'execution':'synthetic-native','paid_calls':0,'cases':rows},ensure_ascii=False,indent=2),encoding='utf-8')
    try:
        password=secrets.token_urlsafe(24)
        container=cli('run','--rm','-d','--label','finsight.qualification=intake-faults','-e','POSTGRES_PASSWORD='+password,'-p','127.0.0.1::5432','postgres:16.15-alpine')
        (tmp_path/'container-id.txt').write_text(container,encoding='utf-8')
        pgport=cli('port',container,'5432/tcp').rsplit(':',1)[1]
        until(lambda:subprocess.run([docker,'exec',container,'pg_isready','-U','postgres'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=10).returncode==0)
        bffport,javaport=port(),port()
        env={**os.environ,'PYTHONPATH':os.pathsep.join([str(ROOT/'src'),str(ROOT)]),'FINSIGHT_INTAKE_QUALIFICATION':'1',
            'FINSIGHT_LOCAL_STATE_ROOT':str(root),'FINSIGHT_BUSINESS_SHARED_SECRET':secrets.token_urlsafe(48),
            'FINSIGHT_BUSINESS_API_URL':f'http://127.0.0.1:{javaport}','FINSIGHT_PYTHON_INTAKE_URL':f'http://127.0.0.1:{bffport}',
            'FINSIGHT_BUSINESS_PORT':str(javaport),'FINSIGHT_BUSINESS_JDBC_URL':f'jdbc:postgresql://127.0.0.1:{pgport}/postgres',
            'FINSIGHT_BUSINESS_DB_USER':'postgres','FINSIGHT_BUSINESS_DB_PASSWORD':password}
        def boot(which):
            args=[java,'-jar',str(jar)] if which=='java' else [sys.executable,'-m','uvicorn','tests.integration.fixtures.java_intake_web:app','--host','127.0.0.1','--port',str(bffport)]
            f=(tmp_path/f'{which}-{len(logs)}.log').open('w',encoding='utf-8');logs.append(f)
            p=subprocess.Popen(args,cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT);processes.append(p)
            ready(f'http://127.0.0.1:{javaport}/v1/tasks' if which=='java' else f'http://127.0.0.1:{bffport}/auth/status',p);return p
        bff,business=boot('bff'),boot('java')
        def native():return json.loads((root/'synthetic-native.json').read_text())
        def count(tid):return len(native()['runs'].get(tid,[]))
        def arm(name,point):
            (root/'fault-control.json').write_text(json.dumps({'case':name,'point':point}))
        def release(name):(root/('release-'+name)).touch()
        def entered(name):until(lambda:(root/('entered-'+name)).exists())
        def death(p):p.kill();p.wait(timeout=15);assert p.returncode!=0
        with httpx.Client(base_url=f'http://127.0.0.1:{bffport}',timeout=50,trust_env=False,headers={'X-Workbench-Request':'1'}) as client, ThreadPoolExecutor(max_workers=20) as pool:
            project=str(uuid4());r=client.put('/api/v1/projects',json={'revision':0,'projects':[{'id':project,'name':'Synthetic fault matrix'}],'assignments':{},'pinned':[]});assert r.status_code==200,r.text
            def create(key,title):
                return client.post('/api/v1/business/tasks',headers={'Idempotency-Key':key},json={'project_id':project,'title':title,'question':'Synthetic question; never contact a model.'})
            def post(tid,action):return client.post(f'/api/v1/business/tasks/{tid}/{action}',json={})
            key=str(uuid4());responses=list(pool.map(lambda _:create(key,'concurrent'),range(20)))
            assert all(r.status_code==200 for r in responses)
            ids={r.json()['id'] for r in responses};assert len(ids)==1;tid=ids.pop()
            starts=list(pool.map(lambda _:post(tid,'start'),range(20)))
            assert all(r.status_code==200 for r in starts) and count(tid)==1
            assert len(native()['threads'])==1
            conflict=create(key,'different-content');assert conflict.status_code==409
            record(case='20-duplicate-create-and-start',submission_key=key,task_id=tid,requests=20,start_requests=20,threads=len(native()['threads']),native_dispatches=count(tid),conflict_http=409)

            # Java dies before persisting the request: no task has been accepted yet.
            name='java-before-request-persist';arm(name,'before_binding_reply');key=str(uuid4())
            future=pool.submit(create,key,name);entered(name);death(business);release(name)
            business=boot('java');first=future.result();assert first.status_code==503
            r=create(key,name);assert r.status_code==200,r.text;task=r.json();assert task['prepare']['status']=='received'
            assert count(task['id'])==0
            record(case=name,submission_key=key,task_id=task['id'],first_http=first.status_code,prepared_after_explicit_resubmit=True,native_dispatches=0)

            cases=[('python-before-effect','before_native_start','bff',0),('python-after-effect','after_native_start','bff',1),
                ('python-after-receipt','after_receipt_save','bff',1),('java-after-dispatch','after_native_start','java',1),
                ('java-during-result-write','after_native_start','java-write',1)]
            for name,point,victim,expected in cases:
                key=str(uuid4());r=create(key,name);assert r.status_code==200,r.text;task=r.json();tid=task['id'];arm(name,point)
                future=pool.submit(post,tid,'start');entered(name)
                lock=None
                try:
                    if victim=='java-write':
                        lock=psycopg.connect(host='127.0.0.1',port=int(pgport),user='postgres',password=password,dbname='postgres')
                        lock.execute("SELECT task_id FROM research_command WHERE task_id=%s AND phase='start' FOR UPDATE",(tid,))
                        release(name)
                        with psycopg.connect(host='127.0.0.1',port=int(pgport),user='postgres',password=password,dbname='postgres',autocommit=True) as probe:
                            until(lambda:probe.execute("SELECT count(*) FROM pg_stat_activity WHERE cardinality(pg_blocking_pids(pid))>0 AND query LIKE 'UPDATE research_command SET status=%'").fetchone()[0]>0)
                        death(business)
                    elif victim=='bff':death(bff)
                    else:death(business);release(name)
                finally:
                    if lock:lock.rollback();lock.close()
                if victim=='bff':bff=boot('bff')
                else:business=boot('java')
                try:first_http=future.result().status_code
                except httpx.HTTPError:first_http='connection_lost'
                state=client.get(f'/api/v1/business/tasks/{tid}');assert state.status_code==200,state.text
                before=state.json()['start']['status']
                # Killing the JDBC client does not guarantee cancellation of an
                # UPDATE already accepted by PG. After releasing the row lock,
                # that autocommit statement may finish without its Java caller.
                # Both outcomes require persisted proof, never another dispatch.
                assert before in ({'unknown','received'} if victim=='java-write' else {'unknown'})
                with psycopg.connect(host='127.0.0.1',port=int(pgport),user='postgres',password=password,dbname='postgres') as probe:
                    stored,body=probe.execute("SELECT status,response_body FROM research_command WHERE task_id=%s AND phase='start'",(tid,)).fetchone()
                assert before==('unknown' if stored=='dispatching' else stored)
                if before=='received':
                    assert body['run_id']==state.json()['start']['result']['run_id']==native()['runs'][tid][0]['run_id']
                assert count(tid)==expected
                assert post(tid,'start').json()['start']['status']==before
                checked=post(tid,'reconcile');assert checked.status_code==200,checked.text
                result=checked.json();expected_state='received' if expected else 'unknown'
                assert result['start']['status']==expected_state and count(tid)==expected
                if expected:assert result['start']['result']['run_id']==native()['runs'][tid][0]['run_id']
                for _ in range(2):assert post(tid,'reconcile').json()['start']['status']==expected_state
                assert count(tid)==expected
                record(case=name,task_id=tid,submission_key=key,operation_id=result['start']['operation_id'],first_http=first_http,
                       before_reconcile=before,database_state=stored,after_reconcile=expected_state,native_dispatches=count(tid),
                       run_id=result['start'].get('result',{}).get('run_id'),reconcile_repeats=2)
            # Real log lines carry exact IDs but never the synthetic request content.
            java_logs=''.join(p.read_text(encoding='utf-8') for p in tmp_path.glob('java-*.log'))
            bff_logs=''.join(p.read_text(encoding='utf-8') for p in tmp_path.glob('bff-*.log'))
            assert f'task_id={tid}' in java_logs and result['start']['operation_id'] in java_logs
            assert f'submission_key={key}' in java_logs
            assert f'task_id={tid}' in bff_logs and result['start']['operation_id'] in bff_logs
            assert 'Synthetic question; never contact a model.' not in java_logs+bff_logs
    finally:
        for p in processes:
            if p.poll() is None:p.terminate();p.wait(timeout=20)
        for f in logs:f.close()
        if container:
            try:
                assert cli('inspect','--format','{{index .Config.Labels "finsight.qualification"}}',container)=='intake-faults'
                cli('rm','-f',container)
            except (subprocess.SubprocessError, AssertionError) as error:
                (tmp_path/'cleanup-required.json').write_text(json.dumps({'container_id':container,'error_type':type(error).__name__}),encoding='utf-8')
                raise
