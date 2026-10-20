"""Isolated ordinary browser -> Java durable commands -> real native HITL."""
import json
import hashlib
import os
import subprocess
from uuid import uuid4

import psycopg
import pytest

from sec_agent.research_foundation.asset_workspace import AssetWorkspace
from tests.integration.test_organization_delivery_stack import DeliveryStack
from tests.integration.test_organization_graph_native import OrganizationGraphStack, ROOT

pytestmark = pytest.mark.skipif(os.getenv('FIN_ORGANIZATION_REPORT_ACTIONS_QUALIFICATION') != '1',
    reason='explicit isolated organization report action qualification required')


class ReportActionsStack(DeliveryStack):
    compose_files = (*OrganizationGraphStack.compose_files, ROOT/'deploy/qualification/organization_report_actions.compose.yaml')
    graph_fixture = ROOT/'tests/integration/fixtures/organization_report_actions_graph.py'
    registered_graph = '/probe/organization_report_actions_graph.py:graph'
    synthetic_components = [*OrganizationGraphStack.synthetic_components, 'initial report, answer, revision and review producers']
    real_components = [*OrganizationGraphStack.real_components, 'human_review node', 'report version rules', 'browser', 'BFF']

    def __init__(self):
        super().__init__()
        self.env.update(FIN_ORGANIZATION_REPORT_ACTIONS_QUALIFICATION='1',
                        FINSIGHT_ORGANIZATION_REPORT_ACTIONS_ENABLED='1')
        self.release_files = sorted({*subprocess.check_output(['git', 'diff', '--name-only', '--', 'src', 'apps', 'tests', 'deploy'],
            cwd=ROOT, text=True).splitlines(), *subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard',
            '--', 'src', 'apps', 'tests', 'deploy'], cwd=ROOT, text=True).splitlines()})
        self.source_hashes = {p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in self.release_files}
        self.save('release-source-preflight', {'sources': self.source_hashes,
            'frontend': {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in (ROOT/'apps/workbench/frontend/dist').rglob('*') if p.is_file()}})


def test_browser_multiround_report_actions_restart_and_revocation(monkeypatch):
    s = ReportActionsStack()
    monkeypatch.setenv('FINSIGHT_BUSINESS_SHARED_SECRET', s.shared)
    def api(method, path, body=None):
        return s.request(s.bff, method, '/api/v1/business/workspaces' + path, **({'json': body} if body is not None else {}))
    try:
        s.compose('up', '-d', '--pull', 'never', 'api'); s.healthy(); s.audit_container()
        with psycopg.connect(host='127.0.0.1', port=s.pg_port, dbname='probe', user='probe', password=s.password, autocommit=True) as conn:
            conn.execute('CREATE DATABASE business')
        business, web = s.boot('java'), s.boot('bff')
        org, space, project, resource, private = [str(uuid4()) for _ in range(5)]
        api('POST', '/organizations', {'id': org, 'name': 'Static report actions', 'display_name': 'Alice'})
        api('POST', '/spaces', {'id': space, 'organization_id': org, 'name': 'Team originals'})
        api('POST', '/projects', {'id': project, 'organization_id': org, 'name': 'Report actions qualification', 'description': 'Static only'})
        assets = AssetWorkspace(s.state/'project-library')
        assets.library.save('oidc:alice', 0, {'projects': [{'id': private, 'name': 'Private original'}], 'assignments': {}, 'pinned': []})
        assets.library.documents.add(assets.library.scope('oidc:alice', private), 'Original.md', b'Synthetic pinned organization evidence.')
        ref = assets.catalog('oidc:alice', private)['items'][0]['current']['ref']
        s.request(s.bff, 'POST', '/api/v1/asset-workspace/spaces/publish', json={'id': resource, 'space_id': space, 'ref': ref})
        api('POST', f'/projects/{project}/resources/{resource}', {'revision': 1, 'linked': True})
        normal = s.browser(project, 'browser-create')
        tid = normal['execution']
        read = f'/api/v1/organization-projects/{project}/research/{tid}'
        initial = s.request(s.bff, 'GET', read)
        assert initial['report_version'] == 1 and s.state_of(tid)['next'] == ['human_review']
        env = {k: v for k, v in s.env.items() if k != 'LANGSMITH_API_KEY'}
        env.update(FIN_DELIVERY_BROWSER_ORIGIN=f'http://127.0.0.1:{s.bff_port}',
                   FIN_DELIVERY_PROJECT=project, FIN_DELIVERY_EXECUTION=tid,
                   FIN_DELIVERY_BROWSER_OUTPUT=str(s.output/'browser-actions'))
        result = subprocess.run([os.environ['FINSIGHT_TEST_NODE'], 'e2e/organization-live-report-actions.mjs'],
            cwd=ROOT/'apps/workbench/frontend', env=env, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=400)
        s.save('browser-actions-process', {'returncode': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr})
        assert result.returncode == 0, result.stderr[-4000:]
        snapshot = s.request(s.bff, 'GET', read)
        commands = s.request(s.bff, 'GET', read+'/report-commands')['items']
        assert len(s.runs(tid)) == 6 and len(commands) == 4 and all(c['status'] == 'received' for c in commands)
        assert snapshot['report_version'] == 2 and len(snapshot['conversation']) == 7
        assert [c['report_version'] for c in reversed(commands)] == [1, 1, 1, 2]
        # Only our five services are restarted; durable commands and native state
        # must recover without another dispatch or a repeated output producer.
        for process in (business, web):
            process.terminate(); process.wait(timeout=20)
        s.compose('stop', '-t', '5', 'api', 'redis', 'postgres')
        s.compose('up', '-d', '--pull', 'never', 'api'); s.healthy()
        s.boot('java'); s.boot('bff')
        recovered = s.request(s.bff, 'GET', read)
        assert recovered['report'] == snapshot['report'] and recovered['conversation'] == snapshot['conversation']
        assert recovered['checkpoint_id'] == snapshot['checkpoint_id']
        for command in commands:
            assert s.request(s.bff, 'POST', read+f"/report-commands/{command['id']}/reconcile", json={})['run_id'] == command['run_id']
        assert len(s.runs(tid)) == 6
        current = s.request(s.bff, 'GET', f'/api/v1/asset-workspace/spaces/resources/{resource}')
        api('POST', f'/resources/{resource}/revoke', {'revision': current['permission_revision']})
        for suffix in ('', '/report-commands', '/report-action-preview', '/report/export/md'):
            assert s.bff.get(read+suffix).status_code == 404
        assert s.bff.post(read+f"/report-commands/{commands[0]['id']}/reconcile", json={}).status_code == 404
        assert {p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in s.release_files} == s.source_hashes
        s.save('release-source-postflight', {'unchanged': True, 'sources': s.source_hashes})
        s.save('report-actions-result', {'native_runs': 6, 'report_commands': 4, 'report_versions': 2,
            'same_report_multiple_questions': True, 'lost_reply_reconciled': True,
            'five_owned_services_restart': True, 'current_revocation': True,
            'browser_api_interceptions': 0, 'provider_calls': 0, 'financial_quality': 'not_assessed',
            'static_substitutions': s.synthetic_components})
    finally:
        for process in s.processes:
            if process.poll() is None:
                process.terminate(); process.wait(timeout=20)
        for log in s.logs:
            log.close()
        try:
            s.compose('logs', '--no-color')
        finally:
            s.compose('stop', '-t', '5'); s.bff.close(); s.native.close()
