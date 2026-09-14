"""Opt-in Docker qualification of the locked native queue, not a replacement runtime.

FIN_NATIVE_QUALIFICATION=1 and FIN_NATIVE_ATTEMPT_DIR (new directory) are required.
Only synthetic graph inputs are used. All created services are stopped, not deleted.
"""
import json
import hashlib
import os
from pathlib import Path
import secrets
import subprocess
import time
from uuid import uuid4

import httpx
import pytest


ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / 'deploy/qualification/agent_server.compose.yaml'
pytestmark = pytest.mark.skipif(os.getenv('FIN_NATIVE_QUALIFICATION') != '1',
                                reason='explicit isolated Docker qualification only')


class NativeProbe:
    def __init__(self, output, env, project):
        self.output, self.env, self.project = output, env, project
        self.client = httpx.Client(base_url='http://127.0.0.1:18414', timeout=15, trust_env=False)
        self.ordinal = 0

    def compose(self, *args):
        self.ordinal += 1
        result = subprocess.run(['docker', 'compose', '-f', str(COMPOSE), '-p', self.project, *args],
                                env=self.env, capture_output=True, text=True, timeout=180)
        body = result.stdout + result.stderr
        for name in ('LANGSMITH_API_KEY', 'FIN_E1_POSTGRES_PASSWORD'):
            body = body.replace(self.env[name], '[REDACTED]')
        (self.output / f'compose-{self.ordinal:02d}.log').write_text(body, encoding='utf-8')
        if result.returncode != 0:
            # Do not let pytest render raw CompletedProcess stderr with credentials.
            raise AssertionError(f'compose {args} failed; see redacted compose-{self.ordinal:02d}.log')
        return result.stdout

    def request(self, method, path, **kwargs):
        response = self.client.request(method, path, **kwargs)
        response.raise_for_status()
        return response.json() if response.content else None

    def wait(self, condition, *, seconds=60):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            value = condition()
            if value:
                return value
            time.sleep(.2)
        raise AssertionError('native_probe_condition_timeout')

    def healthy(self):
        def check():
            try:
                return self.client.get('/ok').status_code == 200
            except httpx.TransportError:
                return False
        self.wait(check)

    def events(self, label, phase):
        rows = []
        for path in (self.output / 'events').glob('*.jsonl'):
            for line in path.read_text(encoding='utf-8').splitlines():
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue  # An active writer may not have finished its final line yet.
                if row['label'] == label and row['phase'] == phase:
                    rows.append(row)
        return rows

    def start(self, label, delay=0, review=False):
        thread = self.request('POST', '/threads', json={'metadata': {'qualification': self.project}})['thread_id']
        run = self.request('POST', f'/threads/{thread}/runs', json={
            'assistant_id': 'runtime_probe', 'input': {'label': label, 'delay_seconds': delay,
                                                     'require_review': review},
            'multitask_strategy': 'reject',
        })
        return thread, run['run_id']

    def run(self, pair):
        return self.request('GET', f'/threads/{pair[0]}/runs/{pair[1]}')

    def state(self, pair):
        return self.request('GET', f'/threads/{pair[0]}/state')

    def terminal(self, pair, expected='success', seconds=60):
        try:
            result = self.wait(lambda: (r if (r := self.run(pair))['status'] not in ('pending', 'running') else None),
                               seconds=seconds)
        except AssertionError:
            self.save(f'timeout-{pair[1]}', {'run': self.run(pair), 'state': self.state(pair),
                                            'observation_seconds': seconds})
            raise
        assert result['status'] == expected, result
        return result

    def save(self, name, value):
        (self.output / f'{name}.json').write_text(json.dumps(value, indent=2), encoding='utf-8')


@pytest.fixture(scope='module')
def native():
    from dotenv import dotenv_values
    output = Path(os.environ['FIN_NATIVE_ATTEMPT_DIR']).resolve()
    assert output.is_relative_to(ROOT / '.local/fin014'), 'attempt_must_be_in_ignored_qualification_root'
    output.mkdir(parents=True, exist_ok=False)
    (output / 'events').mkdir()
    key = os.getenv('LANGSMITH_API_KEY') or dotenv_values(ROOT / '.env').get('LANGSMITH_API_KEY')
    assert key, 'existing_development_account_key_missing'
    image = json.loads(subprocess.check_output(['docker', 'image', 'inspect',
                                               'finsight-dell-report-workbench-langgraph-api']))[0]['Id']
    versions = json.loads(subprocess.check_output([
        'docker', 'run', '--rm', '--network', 'none', '--entrypoint', 'python', image, '-c',
        "import importlib.metadata as m,json; print(json.dumps({k:m.version(k) for k in ['langgraph-api','langgraph','psycopg']}))",
    ], text=True))
    assert versions == {'langgraph-api': '0.13.3', 'langgraph': '1.2.11', 'psycopg': '3.3.4'}
    project = 'fin014-e1-' + uuid4().hex[:12]
    env = dict(os.environ, LANGSMITH_API_KEY=key, FIN_E1_POSTGRES_PASSWORD=secrets.token_hex(24),
               FIN_E1_IMAGE=image, FIN_E1_EVIDENCE_DIR=(output / 'events').as_posix())
    assert env.get('FIN_E1_SUBNET'), 'explicit_inspected_subnet_required'
    probe = NativeProbe(output, env, project)
    probe.save('environment', {'project': project, 'image': image, 'versions': versions, 'fixture_graph_model_calls': 0,
                              'git_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                              'graph': 'tests/integration/fixtures/native_runtime_probe.py',
                              'graph_sha256': hashlib.sha256((ROOT / 'tests/integration/fixtures/native_runtime_probe.py').read_bytes()).hexdigest()})
    try:
        probe.compose('up', '-d', '--pull', 'never', 'api')
        probe.healthy()
        yield probe
    finally:
        try:
            probe.compose('logs', '--no-color')
        finally:
            probe.compose('--profile', 'peer', 'stop', '-t', '5')
            probe.client.close()


def test_native_queue_reject_cancel_and_resume(native):
    long = native.start('queue-long', 30)
    native.wait(lambda: native.events('queue-long', 'work_started'))
    short = native.start('queue-short')
    assert native.run(short)['status'] == 'pending'
    duplicate = native.client.post(f'/threads/{long[0]}/runs', json={
        'assistant_id': 'runtime_probe', 'input': {'label': 'must-not-run'}, 'multitask_strategy': 'reject'})
    assert duplicate.status_code == 409
    native.request('POST', f'/threads/{long[0]}/runs/{long[1]}/cancel', params={'wait': 1, 'action': 'interrupt'})
    native.terminal(long, 'interrupted')
    native.terminal(short)
    paused = native.state(long)
    assert paused['values']['prepared'] is True
    assert not paused['values'].get('completed')
    # Adjust synthetic delay through native state update, then resume checkpoint.
    native.request('POST', f'/threads/{long[0]}/state', json={'values': {'delay_seconds': 0}})
    resumed = native.request('POST', f'/threads/{long[0]}/runs', json={'assistant_id': 'runtime_probe', 'input': None})
    native.terminal((long[0], resumed['run_id']))
    assert len(native.events('queue-long', 'prepared')) == 1
    native.save('queue_cancel_resume', {'long': long, 'short': short, 'resumed': resumed['run_id'],
                                       'paused': paused, 'final': native.state(long)})


def test_native_human_interrupt_releases_capacity(native):
    review = native.start('review-pause', review=True)
    # 0.13.3 marks this invocation successful but the thread interrupted.
    # This differs from explicit cancellation of a running invocation.
    native.terminal(review, 'success')
    assert native.request('GET', f'/threads/{review[0]}')['status'] == 'interrupted'
    paused = native.state(review)
    assert paused['next'] == ['review']
    assert any(task.get('interrupts') for task in paused['tasks'])
    short = native.start('during-review')
    native.terminal(short)
    resumed = native.request('POST', f'/threads/{review[0]}/runs', json={
        'assistant_id': 'runtime_probe', 'command': {'resume': True}})
    native.terminal((review[0], resumed['run_id']))
    assert native.state(review)['values']['reviewed'] is True
    assert len(native.events('review-pause', 'work_started')) == 1
    native.save('human_interrupt', {'review': review, 'other': short, 'resumed': resumed['run_id']})


def test_native_worker_restart_retains_checkpoint(native):
    pair = native.start('restart-work', 12)
    native.wait(lambda: native.events('restart-work', 'work_started'))
    native.compose('stop', '-t', '8', 'api')
    native.compose('start', 'api')
    native.healthy()
    native.terminal(pair, seconds=90)
    assert native.state(pair)['values']['completed'] is True
    assert len(native.events('restart-work', 'prepared')) == 1
    native.save('worker_restart', {'run': pair, 'state': native.state(pair),
                                   'node_attempts': native.events('restart-work', 'work_started')})


def test_two_native_workers_share_queue_but_not_single_worker_capacity(native):
    long = native.start('peer-long', 25)
    original = native.wait(lambda: native.events('peer-long', 'work_started'))[0]
    native.compose('--profile', 'peer', 'up', '-d', '--pull', 'never', 'peer')
    short = native.start('peer-short')
    native.terminal(short)
    other = native.events('peer-short', 'work_started')[0]
    assert other['worker'] != original['worker']
    assert not native.events('peer-long', 'work_finished')
    native.request('POST', f'/threads/{long[0]}/runs/{long[1]}/cancel', params={'wait': 1})
    native.terminal(long, 'interrupted')
    native.save('two_workers', {'long': long, 'short': short, 'worker_one': original,
                                'worker_two': other, 'per_worker_capacity': 1,
                                'observed_deployment_concurrency_at_least': 2})


def test_native_hard_kill_recovery_keeps_completed_steps(native):
    # Keep only one worker so the hard-kill victim is known.
    native.compose('--profile', 'peer', 'stop', '-t', '5', 'peer')
    pair = native.start('hard-kill-work', 12)
    native.wait(lambda: native.events('hard-kill-work', 'work_started'))
    native.compose('kill', '-s', 'SIGKILL', 'api')
    native.compose('start', 'api')
    native.healthy()
    # Official crash sweeper runs every 2 minutes. This is an observation
    # window, not a user-facing RTO; the prior 100s failed attempt is retained.
    observed_at = time.monotonic()
    native.terminal(pair, seconds=300)
    recovery_seconds = time.monotonic() - observed_at
    assert native.state(pair)['values']['completed'] is True
    assert len(native.events('hard-kill-work', 'prepared')) == 1
    native.save('hard_kill', {'run': pair, 'state': native.state(pair),
                              'seconds_after_api_health': recovery_seconds,
                              'node_attempts': native.events('hard-kill-work', 'work_started')})
