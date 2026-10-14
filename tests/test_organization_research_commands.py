"""Browser boundary: current authority, exact commands and no cached business state."""
from copy import deepcopy
from uuid import uuid4

from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest

from test_java_research_intake import intake
from test_organization_native_drafts import organization
from test_organization_native_start import starting
from test_organization_native_continuation import continuing


@pytest.fixture
def browser(continuing, monkeypatch):
    s = continuing
    monkeypatch.setattr('apps.workbench.backend.authentication.OIDCBackend.verify', lambda self, token: 'oidc:alice')
    s.root = f"/api/v1/organization-projects/{s.grant['project_id']}/research/{s.grant['execution_id']}"
    s.headers = {'Authorization': 'Bearer synthetic', 'X-Workbench-Request': '1', 'Idempotency-Key': str(uuid4())}
    s.commands = []
    s.control = {'manifest_text': s.grant['manifest_text'], 'preparation': 'received', 'start': 'received', 'continuation': 'absent'}
    async def java(owner, method, suffix, body=None):
        assert owner == 'oidc:alice'
        s.commands.append((method, suffix, body))
        if s.state['status'] != 200:
            raise HTTPException(s.state['status'], 'revoked')
        if suffix.endswith('/control'): return deepcopy(s.control)
        if suffix.endswith('/execution-bindings'): return {'status': 'bound'}
        return {'status': s.state.get('reply_status', 'unknown')}
    monkeypatch.setattr('apps.workbench.backend.organization_research_commands.space_business_request', java)
    async def authority(project, execution):
        if s.state['status'] != 200: raise HTTPException(404, 'revoked')
        return {**s.start_grant, 'reader': 'oidc:alice', 'run_id': s.continue_body['previous_run_id']}
    monkeypatch.setattr('apps.workbench.backend.organization_research_reads.read_authority', authority)
    return s


def test_preview_is_read_only_and_exact_confirmation_delegates(browser):
    s = browser
    with TestClient(s.intake.app()) as c:
        preview = c.get(s.root + '/continuation-preview', headers=s.headers)
        assert preview.status_code == 200, preview.text
        body = preview.json()
        assert body == {k: s.continue_body[k] for k in ('previous_run_id', 'checkpoint_id', 'state_digest')}
        assert all(call[0] == 'GET' for call in s.commands)
        assert c.post(s.root + '/continue', json=body, headers=s.headers).json()['status'] == 'unknown'
        assert s.commands[-1][2] == body
        assert len(s.intake.runs[s.grant['execution_id']]) == 1  # SDK not dispatched by browser wrapper.
        assert c.post(s.root + '/continue', json={**body, 'model': 'other'}, headers=s.headers).status_code == 422


@pytest.mark.parametrize('fault', ['pending', 'unknown_usage', 'empty_usage', 'report', 'not_success', 'prior_command'])
def test_preview_refuses_unsafe_predecessor(browser, fault):
    s = browser
    if fault == 'pending': s.baseline['next'] = ['research']
    if fault == 'unknown_usage': s.usage['unknown_or_pending_requests'] = 1
    if fault == 'empty_usage': s.usage['recorded_requests'] = 0
    if fault == 'report': s.baseline['values']['report'] = {'title': 'old'}
    if fault == 'not_success': s.intake.runs[s.grant['execution_id']][0]['status'] = 'pending'
    if fault == 'prior_command': s.control['continuation'] = 'unknown'
    with TestClient(s.intake.app()) as c:
        assert c.get(s.root + '/continuation-preview', headers=s.headers).status_code == 409
    assert all(call[0] == 'GET' for call in s.commands)


def test_reconcile_rechecks_java_before_same_browser_receipt_and_after_revocation(browser):
    s = browser
    with TestClient(s.intake.app()) as c:
        path = s.root + '/reconcile/continuation'
        assert c.post(path, json={}, headers=s.headers).json()['status'] == 'unknown'
        s.state['reply_status'] = 'received'
        response = c.post(path, json={}, headers=s.headers)
        assert response.json()['status'] == 'received'
        assert response.headers['cache-control'] == 'no-store'
        s.state['status'] = 404
        assert c.post(path, json={}, headers=s.headers).status_code == 404
        assert c.get(s.root + '/control', headers=s.headers).status_code == 404
    assert [call[1].rsplit('/', 1)[-1] for call in s.commands[:3]] == ['continuation-reconcile'] * 3


@pytest.mark.parametrize('headers', [{}, {'X-Workbench-Request': '1', 'Origin': 'https://untrusted.invalid'}])
def test_browser_write_guard_before_java(browser, headers):
    s = browser
    with TestClient(s.intake.app()) as c:
        response = c.post(s.root + '/start', json={}, headers={'Authorization': 'Bearer synthetic', **headers})
        assert response.status_code == 403
    assert s.commands == []


def test_start_uses_fixed_cutoff_and_prepare_preserves_identity(browser):
    s = browser
    with TestClient(s.intake.app()) as c:
        assert c.post(s.root + '/start', json={}, headers=s.headers).status_code == 200
        import json
        assert s.commands[-1][2] == {'research_as_of': json.loads(s.grant['manifest_text'])['research_as_of'] + 'T23:59:59+00:00'}
        draft = str(uuid4())
        path = f"/api/v1/organization-projects/{s.grant['project_id']}/research-drafts/{draft}/prepare"
        body = {'execution_id': s.grant['execution_id'], 'manifest_digest': s.grant['manifest_digest'],
                'execution': {'mode': 'auto', 'model': 'default', 'branch_ids': []}}
        assert c.post(path, json=body, headers=s.headers).status_code == 200
        assert s.commands[-2][2] == {'id': body['execution_id'], 'manifest_digest': body['manifest_digest']}
        assert s.commands[-1][2] == {'execution': body['execution']}
