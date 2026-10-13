"""Real organization draft persistence; synthetic identity and reply loss, zero runs."""
import json
import os
from uuid import uuid4

import httpx
import psycopg
import pytest

from apps.workbench.backend.business_transport import delegate
from sec_agent.research_foundation.asset_workspace import AssetWorkspace
from tests.integration.test_java_intake_native import Stack

pytestmark = pytest.mark.skipif(
    os.getenv('FIN_ORGANIZATION_NATIVE_QUALIFICATION') != '1'
    or os.getenv('FIN_INTAKE_NATIVE_QUALIFICATION') != '1',
    reason='explicit isolated organization/native qualification required')


def test_organization_native_draft_reply_loss_restart_and_revocation(monkeypatch):
    s = Stack()
    s.env['FIN_ORGANIZATION_NATIVE_QUALIFICATION'] = '1'
    s.bff.headers['Authorization'] = 'Bearer qualification-alice'
    monkeypatch.setenv('FINSIGHT_BUSINESS_SHARED_SECRET', s.shared)
    java = httpx.Client(base_url=f'http://127.0.0.1:{s.java_port}', timeout=60, trust_env=False)
    def api(method, path, body=None):
        return s.request(s.bff, method, '/api/v1/business/workspaces' + path,
            **({'json': body} if body is not None else {}))
    def internal(method, path, body=None, status=200):
        raw = b'' if body is None else json.dumps(body, separators=(',', ':')).encode()
        path = '/v1/workspaces' + path
        response = java.request(method, path, content=raw, headers={
            'Content-Type': 'application/json', 'Authorization': 'Bearer ' + delegate('oidc:alice', method, path, raw)})
        assert response.status_code == status, response.text
        return response.json()
    try:
        s.compose('up', '-d', '--pull', 'never', 'api')
        s.healthy()
        s.audit_container()
        with psycopg.connect(host='127.0.0.1', port=s.pg_port, dbname='probe', user='probe', password=s.password, autocommit=True) as conn:
            conn.execute('CREATE DATABASE business')
        business, web = s.boot('java'), s.boot('bff')
        org, space, project, resource, private = [str(uuid4()) for _ in range(5)]
        api('POST', '/organizations', {'id': org, 'name': 'Synthetic organization', 'display_name': 'Alice'})
        api('POST', '/spaces', {'id': space, 'organization_id': org, 'name': 'Synthetic team'})
        api('POST', '/projects', {'id': project, 'organization_id': org, 'name': 'Synthetic research', 'description': 'Static draft qualification'})
        source = AssetWorkspace(s.state / 'project-library')
        source.library.save('oidc:alice', 0, {'projects': [{'id': private, 'name': 'Private source'}], 'assignments': {}, 'pinned': []})
        source.library.documents.add(source.library.scope('oidc:alice', private), 'Original.md', b'Synthetic pinned organization evidence.')
        ref = source.catalog('oidc:alice', private)['items'][0]['current']['ref']
        s.request(s.bff, 'POST', '/api/v1/asset-workspace/spaces/publish', json={'id': resource, 'space_id': space, 'ref': ref})
        api('POST', f'/projects/{project}/resources/{resource}', {'revision': 1, 'linked': True})
        execution = {'mode': 'auto', 'model': 'default', 'branch_ids': [], 'continuation_scope': 'original_plan'}
        drafts = []
        for label, expected in [('Synthetic normal draft', 'received'), ('Synthetic lost organization reply', 'unknown')]:
            draft, tid = str(uuid4()), str(uuid4())
            prepared = api('POST', f'/projects/{project}/research-drafts', {'id': draft, 'title': label,
                'question': 'Read the fixed evidence later; do not run any research now.',
                'research_as_of': '2026-10-12', 'resource_ids': [resource]})
            internal('POST', f'/projects/{project}/research-drafts/{draft}/execution-bindings',
                {'id': tid, 'manifest_digest': prepared['manifest_digest']})
            path = f'/projects/{project}/execution-bindings/{tid}'
            saved = internal('POST', path + '/prepare', {'execution': execution})
            assert saved['status'] == expected and saved['native_execution_enabled'] is False
            assert internal('POST', path + '/prepare', {'execution': execution}) == saved
            native = s.request(s.native, 'GET', f'/threads/{tid}')
            meta = native['metadata']
            assert meta['owner_id'] == 'organization:' + org and meta['surface'] == 'organization_research_workbench'
            assert meta['organization_execution']['manifest_digest'] == prepared['manifest_digest']
            assert meta['organization_execution']['prepare_operation_id'] == saved['operation_id']
            assert not s.runs(tid)
            assert s.bff.get(f'/api/v1/research-sessions/{tid}').status_code == 404
            assert s.bff.post(f'/api/v1/research-sessions/{tid}/start').status_code == 404
            drafts.append({'thread_id': tid, 'path': path, 'metadata': meta, 'before_restart': saved})
        assert s.request(s.bff, 'GET', '/api/v1/research-sessions') == []
        assert source.library.index('oidc:alice')['assignments'] == {}
        observations = s.state / 'native-create-observations.jsonl'
        assert len(observations.read_text().splitlines()) == 2
        for process in (business, web):
            process.terminate()
            process.wait(timeout=20)
        s.compose('stop', '-t', '5', 'api', 'redis', 'postgres')
        s.compose('up', '-d', '--pull', 'never', 'api')
        s.healthy()
        s.boot('java')
        s.boot('bff')
        for item in drafts:
            result = internal('POST', item['path'] + '/reconcile', {})
            assert result['status'] == 'received'
            assert result['operation_id'] == item['before_restart']['operation_id']
            assert result['result']['configuration_digest'] == item['metadata']['configuration_digest']
            assert s.request(s.native, 'GET', f"/threads/{item['thread_id']}")['metadata'] == item['metadata']
            assert internal('POST', item['path'] + '/prepare', {'execution': execution}) == result
            assert not s.runs(item['thread_id'])
            item['after_restart'] = result
        assert len(observations.read_text().splitlines()) == 2
        visible = s.request(s.bff, 'GET', f'/api/v1/asset-workspace/spaces/resources/{resource}')
        api('POST', f'/resources/{resource}/revoke', {'revision': visible['permission_revision']})
        for item in drafts:
            internal('GET', item['path'] + '/preparation', status=404)
            internal('POST', item['path'] + '/reconcile', {}, status=404)
            assert not s.runs(item['thread_id'])
        s.save('organization-native-drafts', {'real_services': ['Spring Boot', 'BFF', 'PostgreSQL', 'Redis', 'Agent Server'],
            'synthetic': ['OIDC principal', 'evidence', 'post-persistence reply loss'],
            'native_create_count': 2, 'native_run_count': 0, 'provider_calls': 0,
            'current_acl_after_revocation': '404', 'all_services_restart': True, 'drafts': drafts})
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
            java.close()
            s.bff.close()
            s.native.close()
