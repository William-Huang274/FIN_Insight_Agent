"""Real Java/BFF/native persistence with scripted model transport, no paid API."""
import json
import os
from pathlib import Path
import secrets
from uuid import uuid4

import psycopg
from psycopg import sql
import pytest

from tests.integration.test_organization_graph_native import OrganizationGraphStack, ROOT
from tests.integration.test_java_intake_native import wait_for
from sec_agent.adapters.model_dispatch_store import ModelDispatchStore
from sec_agent.research_foundation.asset_workspace import AssetWorkspace

pytestmark = pytest.mark.skipif(os.getenv('FIN_CONTINUOUS_WORK_QUALIFICATION') != '1',
    reason='explicit isolated continuous-work integration required')


class ContinuousStack(OrganizationGraphStack):
    graph_fixture = ROOT / 'tests/integration/fixtures/continuous_work_graph.py'
    registered_graph = '/probe/continuous_work_graph.py:graph'
    compose_files = (*OrganizationGraphStack.compose_files, ROOT / 'deploy/qualification/continuous_work.compose.yaml')
    synthetic_components = ['scripted model transport', 'trace export gate', 'qualification identity', 'synthetic original']

    def __init__(self):
        super().__init__()
        password = secrets.token_hex(24)
        self.budget_password = password
        self.redactions.append(password)
        self.env.update(FINSIGHT_ON_DEMAND_ENABLED='1', FINSIGHT_ORGANIZATION_REPORT_ACTIONS_ENABLED='1',
            FINSIGHT_WORKING_MEMORY_PATH=str(self.state / 'calls/working-memory.sqlite'),
            JAVA_TOOL_OPTIONS='-Xms32m -Xmx192m -XX:+UseSerialGC -XX:ActiveProcessorCount=2',
            FIN_PROBE_BUDGET_DSN=f'postgresql://budget_worker:{password}@postgres:5432/budget')

    def initialize_databases(self):
        def connect(name, **kw):
            return psycopg.connect(host='127.0.0.1', port=self.pg_port, dbname=name,
                user='probe', password=self.password, connect_timeout=2, **kw)
        def ready():
            try:
                with connect('probe'): return True
            except psycopg.OperationalError: return False
        wait_for(ready)
        with connect('probe', autocommit=True) as db:
            db.execute('CREATE DATABASE business')
            db.execute('CREATE DATABASE budget')
        dsn = f'postgresql://probe:{self.password}@127.0.0.1:{self.pg_port}/budget'
        store = ModelDispatchStore(dsn)
        store.install()
        with store.connection() as db:
            db.execute((ROOT / 'src/sec_agent/agent_runtime/sql/004_model_dispatch_access_v1.sql').read_text())
            db.execute(sql.SQL('CREATE ROLE budget_worker LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS').format(sql.Literal(self.budget_password)))
            db.execute('GRANT fin_model_worker TO budget_worker')
        return store


def test_continuous_answer_workpaper_restart_close_and_revocation():
    s = ContinuousStack()
    def api(method, path, body=None):
        return s.request(s.bff, method, '/api/v1/business/workspaces' + path,
            **({'json': body} if body is not None else {}))
    try:
        s.compose('up', '-d', '--pull', 'never', 'postgres')
        store = s.initialize_databases()
        s.compose('up', '-d', '--pull', 'never', 'api')
        s.healthy(); s.audit_container()
        business, web = s.boot('java'), s.boot('bff')
        org, space, project, resource, private, draft, tid = [str(uuid4()) for _ in range(7)]
        api('POST', '/organizations', {'id': org, 'name': 'Continuous qualification', 'display_name': 'Alice'})
        api('POST', '/spaces', {'id': space, 'organization_id': org, 'name': 'Test sources'})
        api('POST', '/projects', {'id': project, 'organization_id': org, 'name': 'Continuous work', 'description': 'No financial claim'})
        assets = AssetWorkspace(s.state / 'project-library')
        assets.library.save('oidc:alice', 0, {'projects': [{'id': private, 'name': 'Private original'}], 'assignments': {}, 'pinned': []})
        assets.library.documents.add(assets.library.scope('oidc:alice', private), 'Original.md', b'Synthetic pinned organization evidence.')
        ref = assets.catalog('oidc:alice', private)['items'][0]['current']['ref']
        s.request(s.bff, 'POST', '/api/v1/asset-workspace/spaces/publish', json={'id': resource, 'space_id': space, 'ref': ref})
        api('POST', f'/projects/{project}/resources/{resource}', {'revision': 1, 'linked': True})
        prepared = api('POST', f'/projects/{project}/research-drafts', {'id': draft, 'title': 'Continuous test',
            'question': 'Read the authorized original and answer.', 'research_as_of': '2026-10-12', 'resource_ids': [resource]})
        receipt = s.request(s.bff, 'POST', f'/api/v1/organization-projects/{project}/research-drafts/{draft}/prepare', json={
            'execution_id': tid, 'manifest_digest': prepared['manifest_digest'],
            'execution': {'mode': 'auto', 'model': 'default', 'branch_ids': [], 'continuation_scope': 'original_plan',
                          'delivery_intent': 'answer', 'require_report_review': False}})
        assert receipt['status'] == 'received', receipt
        thread = s.request(s.native, 'GET', f'/threads/{tid}')
        owner = thread['metadata']['owner_id']
        store.create_budget(owner, tid, 'CNY', 1000, 0)
        settings_path = s.output / 'settings/settings.json'
        settings = json.loads(settings_path.read_text())
        policy = {'reservation_micros': 10, 'reservation_basis': 'Deterministic service test; no provider network or tariff', 'delivery': False}
        settings['model_budget_bindings'] = {tid: {'owner_id': owner, 'budget_id': tid,
            'prices': [{'version': 'synthetic-zero-price', 'model': m, 'currency': 'CNY', 'input_miss': 0, 'input_hit': 0, 'output': 0}
                       for m in ('deepseek-flash', 'deepseek-v4-pro')],
            'roles': {'lead': policy, 'context_summary': policy}}}
        settings_path.write_text(json.dumps(settings))
        root = f'/api/v1/organization-projects/{project}/research/{tid}'
        started = s.request(s.bff, 'POST', root + '/start', json={})
        s.terminal(tid, started['run_id'], seconds=120)
        initial = s.request(s.bff, 'GET', root)
        s.save('initial-public-state', initial)
        assert initial['task_outcome']['artifact_kind'] == 'answer', initial
        assert 'authorized original was read' in json.dumps(initial)
        preview = s.request(s.bff, 'GET', root + '/task-action-preview')
        command = {'id': str(uuid4()), 'action': 'continue', 'message': 'Now save a working paper from the same evidence.',
            'delivery_intent': 'workpaper', 'require_report_review': False,
            **{k: preview[k] for k in ('previous_run_id', 'checkpoint_id', 'state_digest')}}
        submitted = s.request(s.bff, 'POST', root + '/task-commands', json=command)
        s.terminal(tid, submitted['run_id'], seconds=120)
        finished = s.request(s.bff, 'GET', root)
        s.save('continued-public-state', finished)
        assert finished['task_outcome']['artifact_kind'] == 'workpaper', finished
        note_path = root + '/workpaper?checkpoint_id=' + finished['checkpoint_id']
        note = s.request(s.bff, 'GET', note_path)
        assert 'same authorized original' in json.dumps(note)
        assert len(s.runs(tid)) == 2
        for process in (business, web): process.terminate(); process.wait(timeout=20)
        s.compose('stop', '-t', '5', 'api', 'redis', 'postgres')
        s.compose('up', '-d', '--pull', 'never', 'api'); s.healthy()
        s.boot('java'); s.boot('bff')
        assert s.request(s.bff, 'GET', note_path) == note
        assert s.request(s.bff, 'POST', root + '/task-commands/' + command['id'] + '/reconcile', json={})['run_id'] == submitted['run_id']
        assert len(s.runs(tid)) == 2
        stopped = s.request(s.bff, 'POST', root + '/stop', json={})
        assert stopped['execution_closed'] is True
        assert s.request(s.bff, 'GET', note_path) == note
        assert s.bff.get(root + '/task-action-preview').status_code == 409
        current = s.request(s.bff, 'GET', f'/api/v1/asset-workspace/spaces/resources/{resource}')
        api('POST', f'/resources/{resource}/revoke', {'revision': current['permission_revision']})
        assert s.bff.get(root).status_code == 404
        assert s.bff.get(note_path).status_code == 404
        snapshot = store.snapshot(owner, tid)
        assert snapshot['known'] == snapshot['held'] == snapshot['unsettled'] == 0
        s.save('continuous-result', {'status': 'passed', 'provider_calls': 0, 'native_runs': 2,
            'real_budget_role_and_settlement': True, 'restart_preserved_note': True,
            'closed_read_only': True, 'revocation': True, 'substitutions': s.synthetic_components,
            'frozen_full_index_tested': False, 'financial_quality': 'not_assessed'})
    finally:
        for process in s.processes:
            if process.poll() is None: process.terminate(); process.wait(timeout=20)
        for log in s.logs: log.close()
        try: s.compose('logs', '--no-color')
        finally:
            s.compose('stop', '-t', '5')
            s.bff.close(); s.native.close()
