"""Real BFF route/custody with synthetic current Java authorities; no providers."""
from copy import deepcopy
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from apps.workbench.backend.api.v1.asset_workspace import build_asset_workspace_router
from apps.workbench.backend import organization_navigation as module
from test_organization_research_inputs import fixture
from test_organization_execution_access import runtime_grant, runtime_at
from test_project_library import app_at, WRITE


@pytest.fixture
def endpoint(tmp_path, monkeypatch):
    import apps.workbench.backend.business_transport as transport
    shared, grant = fixture(tmp_path)
    runtime = runtime_grant(grant)
    grant['manifest_digest'] = runtime['manifest_digest']
    reader, runtime_state = runtime_at(shared, runtime)
    monkeypatch.setenv('FINSIGHT_ORGANIZATION_NAVIGATION_ENABLED', '1')
    monkeypatch.setenv('FINSIGHT_BUSINESS_API_URL', 'http://127.0.0.1:9')
    monkeypatch.setenv('FINSIGHT_ORGANIZATION_RUNTIME_SECRET', 'unused-test-runtime-secret')
    monkeypatch.setenv('FINSIGHT_ORGANIZATION_RETRIEVAL_ROOT', str(tmp_path/'indices'))
    monkeypatch.delenv('FINSIGHT_ORGANIZATION_TABLE_COMPLETION', raising=False)
    state = {'calls': 0, 'denied': False, 'deny_at': None}
    state['document'] = module.OrganizationSourceNavigation._identity(grant['manifest']['inputs'][0])
    state['navigation_payloads'] = []
    async def business(actor, method, path, body=None):
        assert method == 'POST'
        state['calls'] += 1
        if actor != 'alice' or state['denied'] or state['deny_at'] == state['calls']:
            raise HTTPException(404, 'no access')
        if path.endswith('/navigation-access'):
            if runtime_state['status'] != 200:
                raise HTTPException(404, 'execution denied')
            state['navigation_payloads'].append(deepcopy(body))
            current = deepcopy(runtime_state['grant'])
            return {'contract_version': 'organization_navigation_access.v1',
                'binding': {k:v for k,v in current.items() if k not in {'manifest_text','inputs'}},
                **({'grant': current} if body['include_grant'] else {})}
        assert path.endswith('/material-access')
        return deepcopy(grant)
    monkeypatch.setattr(transport, 'space_business_request', business)
    app = app_at(tmp_path, monkeypatch)
    app.include_router(build_asset_workspace_router(tmp_path), prefix='/api/v1')
    path = (f"/api/v1/asset-workspace/organization-projects/{grant['project_id']}"
        f"/research-drafts/{grant['id']}/executions/{runtime['execution_id']}/navigate")
    with TestClient(app) as client:
        yield client, path, state, runtime_state


def test_http_custody_and_warm_authorization(endpoint):
    client, path, state, _ = endpoint
    request = {'source_space': 'organization', 'operation': 'catalog', 'document_id': state['document']}
    result = client.post(path, json=request, headers=WRITE)
    assert result.status_code == 200, result.text
    assert result.headers['cache-control'] == 'no-store'
    doc = result.json()['items'][0]['document_id']
    read = {'source_space': 'organization', 'operation': 'read', 'document_id': doc}
    for _ in range(2):
        result = client.post(path, json=read, headers=WRITE)
        assert result.status_code == 200, result.text
        assert result.json()['items'][0]['passage'] == 'Pinned original evidence.'
    assert state['calls'] > 4
    assert state['navigation_payloads'][0]['include_grant'] is True
    assert all(not p['include_grant'] for p in state['navigation_payloads'][1:])
    assert client.post(path, json=read, headers={**WRITE, 'Authorization': 'Bearer bob'}).status_code == 404
    state['denied'] = True
    assert client.post(path, json=read, headers=WRITE).status_code == 404


@pytest.mark.parametrize('fault', ['runtime_revoked', 'other_execution', 'other_draft', 'late_user_revocation'])
def test_http_no_result_on_binding_or_current_authority_failure(endpoint, fault):
    client, path, state, runtime = endpoint
    if fault == 'runtime_revoked': runtime['status'] = 404
    if fault == 'other_execution': path = path.replace(runtime['grant']['execution_id'], str(uuid4()))
    if fault == 'other_draft': runtime['grant']['draft_id'] = str(uuid4())
    if fault == 'late_user_revocation': state['deny_at'] = 3
    result = client.post(path, headers=WRITE, json={'source_space': 'organization', 'operation': 'catalog',
                                                   'document_id': state['document']})
    assert result.status_code in (404, 409), result.text
    assert 'Pinned original evidence.' not in result.text and 'items' not in result.json()


def test_http_scope_csrf_optin_and_observation_boundary(endpoint, monkeypatch):
    client, path, state, _ = endpoint
    body = {'source_space': 'organization', 'operation': 'catalog'}
    assert client.post(path, json=body, headers={**WRITE, 'Origin': 'https://foreign.invalid'}).status_code == 403
    assert state['calls'] == 0
    for operation in ('catalog', 'outline', 'read'):
        response = client.post(path, headers=WRITE, json={'source_space': 'organization', 'operation': operation})
        assert response.status_code == 422
        assert 'Pinned original evidence.' not in response.text
    for space, operation in [('library', 'search'), ('organization', 'observations'), ('organization', 'data')]:
        assert client.post(path, headers=WRITE, json={'source_space': space, 'operation': operation}).status_code == 422
    monkeypatch.setenv('FINSIGHT_ORGANIZATION_NAVIGATION_ENABLED', '0')
    assert client.post(path, json=body, headers=WRITE).status_code == 503


def test_bounded_admission_rejects_before_work():
    from sec_agent.research_foundation.source_document_navigation import SourceDocumentRequest
    service = module.OrganizationNavigationService(None, None, wait_seconds=0)
    service._lock.acquire()
    try:
        with pytest.raises(HTTPException) as error:
            service.navigate('a', 'p', 'd', 'e', 'http://localhost',
                SourceDocumentRequest(source_space='organization', operation='search', query='evidence'))
        assert error.value.status_code == 429
        assert not service._sessions
    finally:
        service._lock.release()


def test_frozen_payload_decode_is_independent_but_never_an_authorization_lease(tmp_path, monkeypatch):
    _, grant = fixture(tmp_path)
    runtime = runtime_grant(grant)
    grant['manifest_digest'] = runtime['manifest_digest']
    state = {'calls': 0, 'denied': False}
    def invoke(business, actor, method, path, body):
        state['calls'] += 1
        if state['denied']:
            raise HTTPException(404, 'revoked')
        return {'contract_version': 'organization_navigation_access.v1',
            'binding': {k:v for k,v in runtime.items() if k not in {'manifest_text','inputs'}},
            **({'grant': deepcopy(runtime)} if body['include_grant'] else {})}
    monkeypatch.setattr(module.from_thread, 'run', invoke)
    authority = module.UserExecutionAuthority('alice', grant['project_id'], grant['id'],
        runtime['execution_id'], grant, None)
    first = authority()
    first['inputs'][0]['binding']['ref']['digest'] = 'corrupted-caller-copy'
    first['manifest_text'] = '{}'
    second = authority()
    assert second == runtime and state['calls'] == 2
    state['denied'] = True
    with pytest.raises(HTTPException):
        authority()
    assert state['calls'] == 3
