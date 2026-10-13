"""Opt-in real business intake -> native persisted queue; deterministic graph only.

No production ports, source volumes or model provider credentials. Own compose
services are stopped (not deleted); private logs, DB volume and receipts survive.
"""
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import time
from uuid import uuid4

import httpx
import psycopg
import pytest

from tests.integration.test_java_intake_stack import ROOT, port, ready

COMPOSE = ROOT / 'deploy/qualification/intake_native.compose.yaml'
pytestmark = pytest.mark.skipif(os.getenv('FIN_INTAKE_NATIVE_QUALIFICATION') != '1',
    reason='explicit isolated native lifecycle qualification required')


def wait_for(check, seconds=60):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = check()
        if value:
            return value
        time.sleep(.2)
    raise AssertionError('native_lifecycle_observation_timeout; inspect retained attempt')


class Stack:
    compose_files = (COMPOSE,)
    graph_fixture = ROOT / 'tests/integration/fixtures/intake_native_graph.py'
    synthetic_components = ['research graph', 'library binding', 'local identity']
    def __init__(self):
        from dotenv import dotenv_values
        self.output = Path(os.environ['FIN_NATIVE_ATTEMPT_DIR']).resolve()
        self.output.mkdir(parents=True, exist_ok=False)
        self.state = self.output / 'state'
        self.events = self.output / 'events'
        self.events.mkdir()
        (self.state / 'calls').mkdir(parents=True)
        self.project = 'fin-intake-native-' + uuid4().hex[:12]
        self.docker = os.getenv('FINSIGHT_TEST_DOCKER') or shutil.which('docker')
        self.java = os.getenv('FINSIGHT_TEST_JAVA') or shutil.which('java')
        assert self.docker and self.java
        self.jar = Path(os.environ['FINSIGHT_INTAKE_TEST_JAR']).resolve()
        assert self.jar.is_file()
        self.native_port, self.pg_port, self.bff_port, self.java_port = [port() for _ in range(4)]
        assert len({self.native_port, self.pg_port, self.bff_port, self.java_port}) == 4
        assert not {self.native_port, self.pg_port, self.bff_port, self.java_port} & {18165, 18765}
        key = os.getenv('LANGSMITH_API_KEY') or dotenv_values(os.getenv('FIN_NATIVE_LICENSE_ENV', ROOT / '.env')).get('LANGSMITH_API_KEY')
        assert key, 'existing_development_license_required'
        assert os.getenv('FIN_PROBE_SUBNET'), 'explicit_unused_subnet_required'
        image = os.environ['FIN_PROBE_IMAGE']
        assert image.startswith('sha256:'), 'exact_local_image_id_required'
        inspected = json.loads(subprocess.check_output([self.docker, 'image', 'inspect', image], text=True, timeout=30))[0]
        present = [e.partition('=')[0] for e in inspected['Config'].get('Env', []) if e.partition('=')[2]
            and any(t in e.partition('=')[0].upper() for t in ('API_KEY', 'TOKEN', 'SECRET'))]
        assert not present, f'image_has_credential_environment_names:{present}'
        versions = json.loads(subprocess.check_output([self.docker, 'run', '--rm', '--network', 'none',
            '--entrypoint', 'python', image, '-c',
            "import json,importlib.metadata as m; print(json.dumps({k:m.version(k) for k in ['langgraph-api','langgraph','psycopg']}))"],
            text=True, timeout=60))
        assert versions == {'langgraph-api': '0.13.3', 'langgraph': '1.2.11', 'psycopg': '3.3.4'}, 'unqualified_native_image_versions'
        self.password, self.shared = secrets.token_urlsafe(24), secrets.token_urlsafe(48)
        # Child processes cannot inherit a model provider key or the main deployment settings.
        self.env = {k: v for k, v in os.environ.items() if not any(t in k.upper() for t in ('API_KEY', 'TOKEN', 'SECRET'))
            and not k.startswith(('FINSIGHT_', 'FIN_REPO_', 'LANGCHAIN_', 'LANGSMITH_'))}
        self.env.update(LANGSMITH_API_KEY=key, FIN_PROBE_PASSWORD=self.password, FIN_PROBE_IMAGE=image,
            FIN_PROBE_API_PORT=str(self.native_port), FIN_PROBE_PG_PORT=str(self.pg_port),
            FIN_PROBE_EVIDENCE=self.events.as_posix(), FIN_PROBE_AUDIT=(self.state / 'calls').as_posix(),
            FIN_INTAKE_NATIVE_QUALIFICATION='1', FINSIGHT_LOCAL_STATE_ROOT=str(self.state),
            PYTHONPATH=os.pathsep.join([str(ROOT / 'src'), str(ROOT)]), PYTHONDONTWRITEBYTECODE='1',
            FINSIGHT_REPORT_SESSION_API_URL=f'http://127.0.0.1:{self.native_port}',
            FINSIGHT_BUSINESS_SHARED_SECRET=self.shared, FINSIGHT_BUSINESS_API_URL=f'http://127.0.0.1:{self.java_port}',
            FINSIGHT_PYTHON_INTAKE_URL=f'http://127.0.0.1:{self.bff_port}', FINSIGHT_BUSINESS_PORT=str(self.java_port),
            FINSIGHT_BUSINESS_JDBC_URL=f'jdbc:postgresql://127.0.0.1:{self.pg_port}/business',
            FINSIGHT_BUSINESS_DB_USER='probe', FINSIGHT_BUSINESS_DB_PASSWORD=self.password)
        self.redactions = [key, self.password, self.shared]
        self.processes, self.logs, self.rows = [], [], []
        self.ordinal = 0
        self.native = httpx.Client(base_url=f'http://127.0.0.1:{self.native_port}', timeout=15, trust_env=False)
        self.bff = httpx.Client(base_url=f'http://127.0.0.1:{self.bff_port}', timeout=50, trust_env=False,
            headers={'X-Workbench-Request': '1'})
        graph = self.graph_fixture
        sources = ['tests/integration/test_java_intake_native.py', graph.relative_to(ROOT).as_posix(),
            'tests/integration/fixtures/intake_native_web.py', 'deploy/qualification/intake_native.compose.yaml',
            'apps/workbench/backend/api/v1/report_sessions.py']
        self.save('environment', {'project': self.project, 'git_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
            'dirty': bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip()),
            'source_hashes': {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in sources},
            'ports': {'native': self.native_port, 'postgres': self.pg_port, 'bff': self.bff_port, 'java': self.java_port},
            'image': image, 'versions': versions, 'graph_sha256': hashlib.sha256(graph.read_bytes()).hexdigest(),
            'jar_sha256': hashlib.sha256(self.jar.read_bytes()).hexdigest(), 'fixture': str(graph.relative_to(ROOT)),
            'real_services': ['BFF', 'Spring Boot', 'PostgreSQL', 'Redis', 'Agent Server'],
            'synthetic': self.synthetic_components, 'provider_calls': 0})

    def save(self, name, value):
        (self.output / (name + '.json')).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')

    def compose(self, *args):
        self.ordinal += 1
        files = [arg for path in self.compose_files for arg in ('-f', str(path))]
        result = subprocess.run([self.docker, 'compose', *files, '-p', self.project, *args],
            env=self.env, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=180)
        output = result.stdout + result.stderr
        for value in self.redactions:
            output = output.replace(value, '[REDACTED]')
        (self.output / f'compose-{self.ordinal:02d}.log').write_text(output, encoding='utf-8')
        assert result.returncode == 0, f'compose failed; see redacted log {self.ordinal}'

    def healthy(self):
        def check():
            try:
                return self.native.get('/ok').status_code == 200
            except httpx.HTTPError:
                return False
        wait_for(check)

    def audit_container(self):
        ids = subprocess.check_output([self.docker, 'ps', '-q', '--filter', 'label=com.docker.compose.project=' + self.project,
            '--filter', 'label=com.docker.compose.service=api'], text=True, timeout=30).split()
        assert len(ids) == 1
        row = json.loads(subprocess.check_output([self.docker, 'inspect', ids[0]], text=True, timeout=30))[0]
        env = dict(e.split('=', 1) for e in row['Config']['Env'])
        presence = {k: bool(v) for k, v in env.items() if any(t in k.upper() for t in ('API_KEY', 'TOKEN', 'SECRET'))}
        assert not any(v for k, v in presence.items() if k != 'LANGSMITH_API_KEY'), 'provider_credentials_in_test_container'
        assert json.loads(env['LANGSERVE_GRAPHS']) == {'research_session': '/probe/intake_native_graph.py:graph'}
        self.save('container-contract', {'credential_presence_only': presence, 'registered_graph': env['LANGSERVE_GRAPHS'],
            'mount_destinations': [m['Destination'] for m in row['Mounts']]})

    def boot(self, which):
        args = [self.java, '-jar', str(self.jar)] if which == 'java' else [sys.executable, '-m', 'uvicorn',
            'tests.integration.fixtures.intake_native_web:app', '--host', '127.0.0.1', '--port', str(self.bff_port)]
        log = (self.output / f'{which}-{len(self.logs)}.log').open('w', encoding='utf-8')
        self.logs.append(log)
        # The BFF/Java do not need even the development license key.
        env = {k: v for k, v in self.env.items() if k != 'LANGSMITH_API_KEY'}
        process = subprocess.Popen(args, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        self.processes.append(process)
        ready(f'http://127.0.0.1:{self.java_port}/v1/tasks' if which == 'java' else f'http://127.0.0.1:{self.bff_port}/auth/status', process)
        return process

    def request(self, client, method, path, **kwargs):
        response = client.request(method, path, **kwargs)
        assert response.is_success, (response.status_code, response.text[:1200])
        return response.json() if response.content else None

    def state_of(self, tid):
        return self.request(self.native, 'GET', f'/threads/{tid}/state')

    def runs(self, tid):
        return self.request(self.native, 'GET', f'/threads/{tid}/runs')

    def terminal(self, tid, rid, status='success', seconds=60):
        row = wait_for(lambda: next((r for r in self.runs(tid) if r['run_id'] == rid and r['status'] not in ('pending', 'running')), None), seconds)
        assert row['status'] == status, row
        return row

    def events_for(self, tid, phase):
        path = self.events / 'graph-events.jsonl'
        rows = []
        for line in path.read_text().splitlines() if path.exists() else []:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row['thread_id'] == tid and row['phase'] == phase:
                rows.append(row)
        return rows

    def record(self, case, **values):
        self.rows.append({'case': case, **values})
        self.save('lifecycle-matrix', {'execution': 'real-native-queue-deterministic-graph', 'provider_calls': 0, 'cases': self.rows})


@pytest.fixture(scope='module')
def stack():
    s = Stack()
    try:
        s.compose('up', '-d', '--pull', 'never', 'api')
        s.healthy()
        s.audit_container()
        with psycopg.connect(host='127.0.0.1', port=s.pg_port, dbname='probe', user='probe', password=s.password, autocommit=True) as connection:
            connection.execute('CREATE DATABASE business')
        s.web = s.boot('bff')
        s.business = s.boot('java')
        yield s
    finally:
        for process in s.processes:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=20)
        for log in s.logs:
            log.close()
        try:
            s.compose('logs', '--no-color')
        finally:
            s.compose('stop', '-t', '5')
            s.bff.close()
            s.native.close()


def test_business_to_native_persistence_cancel_continue_and_crash_recovery(stack):
    s = stack
    project = str(uuid4())
    s.request(s.bff, 'PUT', '/api/v1/projects', json={'revision': 0, 'projects': [{'id': project, 'name': 'Native fixture project'}], 'assignments': {}, 'pinned': []})
    execution = {'mode': 'auto', 'model': 'default', 'branch_ids': [], 'continuation_scope': 'original_plan'}

    def create(label):
        key = str(uuid4())
        body = {'project_id': project, 'title': label, 'question': 'Synthetic lifecycle ' + label, 'execution': execution}
        task = s.request(s.bff, 'POST', '/api/v1/business/tasks', headers={'Idempotency-Key': key}, json=body)
        assert task['prepare']['status'] == 'received'
        tid = task['thread_id']
        assert tid == task['id'] and not s.runs(tid)
        assert s.request(s.bff, 'POST', '/api/v1/business/tasks', headers={'Idempotency-Key': key}, json=body)['id'] == tid
        started = s.request(s.bff, 'POST', f'/api/v1/business/tasks/{tid}/start', json={})
        assert started['start']['status'] == 'received'
        rid = started['start']['result']['run_id']
        assert s.request(s.bff, 'POST', f'/api/v1/business/tasks/{tid}/start', json={})['start']['result']['run_id'] == rid
        assert len(s.runs(tid)) == 1
        return tid, rid

    tid, rid = create('first')
    s.terminal(tid, rid)
    assert s.state_of(tid)['next'] == ['handoff']
    row = s.runs(tid)[0]
    assert row['metadata']['execution'] == execution
    assert all(event['execution'] == execution for event in s.events_for(tid, 'prepared'))
    route = f'/api/v1/research-sessions/{tid}'
    audit = s.state / 'calls' / tid / rid / 'model-call-events.jsonl'
    saved = audit.read_bytes()
    try:
        audit.write_text('{"call_id":"unknown","event":"started"}', encoding='utf-8')
        assert s.bff.post(route + '/continue-remaining').status_code == 409
        assert len(s.runs(tid)) == 1
    finally:
        audit.write_bytes(saved)
    continued = s.request(s.bff, 'POST', route + '/continue-remaining')
    s.terminal(tid, continued['run_id'])
    snapshot = s.request(s.bff, 'GET', route)
    assert snapshot['report_version'] == 1
    current = next(r for r in s.runs(tid) if r['run_id'] == continued['run_id'])
    assert current['metadata']['execution'] == execution
    assert current['metadata']['continued_from_run_id'] == rid
    versions = s.request(s.bff, 'GET', route + '/report-versions')['versions']
    checkpoint = versions[0]['checkpoint_id']
    report = s.request(s.bff, 'GET', route + '/report-versions/' + checkpoint)
    s.record('business-create-deduplicate-explicit-continue', task_id=tid, first_run=rid, continued_run=continued['run_id'], checkpoint=checkpoint)

    # All own services restart with their original storage, not the main deployment.
    for process in (s.web, s.business):
        process.terminate(); process.wait(timeout=20)
    s.compose('stop', '-t', '5', 'api', 'redis', 'postgres')
    s.compose('up', '-d', '--pull', 'never', 'api')
    s.healthy()
    s.web, s.business = s.boot('bff'), s.boot('java')
    assert s.request(s.bff, 'GET', route + '/report-versions/' + checkpoint) == report
    assert len(s.runs(tid)) == 2
    assert s.request(s.bff, 'POST', f'/api/v1/business/tasks/{tid}/reconcile', json={})['start']['result']['run_id'] == rid
    s.record('all-services-restart-readback', task_id=tid, checkpoint=checkpoint, native_runs=2)

    slow, slow_run = create('slow-cancel')
    wait_for(lambda: s.events_for(slow, 'work_started'))
    queued, queued_run = create('queued')
    assert next(r for r in s.runs(queued) if r['run_id'] == queued_run)['status'] == 'pending'
    s.request(s.bff, 'POST', f'/api/v1/research-sessions/{slow}/runs/{slow_run}/cancel')
    s.terminal(slow, slow_run, 'interrupted')
    assert s.state_of(slow)['values']['prepared']
    s.terminal(queued, queued_run)
    assert s.bff.post(f'/api/v1/research-sessions/{slow}/continue-remaining').status_code == 409
    assert len(s.runs(slow)) == 1  # Arbitrary cancelled node is not a research handoff.
    late = s.bff.post(route + f'/runs/{continued["run_id"]}/cancel')
    assert late.status_code in (200, 409)
    assert s.request(s.bff, 'GET', route + '/report-versions/' + checkpoint) == report
    s.record('queue-cancel-and-late-completion', cancelled_task=slow, cancelled_run=slow_run, queued_task=queued, late_cancel_http=late.status_code)

    crashed, crash_run = create('slow-crash')
    wait_for(lambda: s.events_for(crashed, 'work_started'))
    s.compose('kill', '-s', 'SIGKILL', 'api')
    (s.events / ('release-' + crashed)).touch()
    s.compose('start', 'api')
    s.healthy()
    # Locked native crash sweeper may require two minutes. This is not an RTO claim.
    began = time.monotonic()
    s.terminal(crashed, crash_run, seconds=300)
    assert len(s.events_for(crashed, 'prepared')) == 1
    assert len(s.runs(crashed)) == 1
    restarted = s.request(s.bff, 'POST', f'/api/v1/research-sessions/{crashed}/continue-remaining')
    s.terminal(crashed, restarted['run_id'])
    assert s.state_of(crashed)['values']['execution_seen'] == execution
    s.record('native-hard-kill-same-run-recovery', task_id=crashed, original_run=crash_run,
        continued_run=restarted['run_id'], seconds_after_health=time.monotonic() - began,
        completed_prepare_attempts=1, work_attempts=len(s.events_for(crashed, 'work_started')))
