"""Frozen organization preparation, actual SQLite custody, synthetic authority; no models."""
from copy import deepcopy
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from apps.workbench.backend.api.v1.asset_workspace import build_asset_workspace_router
from apps.workbench.backend.business_transport import build_business_gateway
from apps.workbench.backend.organization_research_inputs import validate_grant, verify_storage
from apps.workbench.backend.space_assets import SpaceAssets
from test_project_library import app_at, WRITE
from test_resource_spaces import source_at


def fixture(root, *, body=b'Pinned original evidence.'):
    source, ref = source_at(root, body=body)
    org, project, draft, space, resource = [str(uuid4()) for _ in range(5)]
    shared = SpaceAssets(root / 'organization-assets')
    binding = shared.publish(source, 'alice', resource, org, space, ref)
    manifest = {'contract_version': 'organization_research_inputs.v1', 'draft_id': draft,
                'project_id': project, 'organization_id': org,
                'visibility_policy': 'current_project_and_all_inputs', 'research_as_of': '2026-10-12',
                'inputs': [{'resource_id': resource, 'space_id': space, 'resource_revision': 1,
                            'title': 'Synthetic original', 'resource_type': 'files', 'ref': deepcopy(binding['ref'])}]}
    grant = {'id': draft, 'project_id': project, 'organization_id': org, 'manifest': manifest,
             'manifest_digest': 'sha256:' + 'a' * 64,
             'inputs': [{'resource_id': resource, 'binding': binding}]}
    return shared, grant


@pytest.mark.parametrize('fault', ['project', 'organization', 'duplicate', 'missing', 'version', 'space', 'digest'])
def test_malformed_material_authority_is_rejected_before_storage(tmp_path, fault):
    _, original = fixture(tmp_path)
    grant = deepcopy(original)
    if fault == 'project': grant['manifest']['project_id'] = str(uuid4())
    if fault == 'organization': grant['inputs'][0]['binding']['organization_id'] = str(uuid4())
    if fault == 'duplicate': grant['inputs'] *= 2
    if fault == 'missing': grant['inputs'] = []
    if fault == 'version': grant['inputs'][0]['binding']['ref']['version_id'] = str(uuid4())
    if fault == 'space': grant['manifest']['inputs'][0]['space_id'] = str(uuid4())
    if fault == 'digest': grant['manifest_digest'] = 'unverified'
    with pytest.raises(HTTPException) as error:
        validate_grant(grant, original['project_id'], original['id'])
    assert error.value.status_code == 502


def test_storage_verifies_original_bytes_and_never_substitutes_version(tmp_path, monkeypatch):
    shared, grant = fixture(tmp_path)
    org, inputs = validate_grant(grant, grant['project_id'], grant['id'])
    assert verify_storage(shared, org, inputs) == [
        {'resource_id': inputs[0]['resource_id'], 'ref': inputs[0]['binding']['ref']}]
    get = shared.workspace.library.documents.get
    def corrupt(*args, **kwargs):
        return {**get(*args, **kwargs), 'body': b'Corrupted stored original.'}
    monkeypatch.setattr(shared.workspace.library.documents, 'get', corrupt)
    with pytest.raises(HTTPException) as error: verify_storage(shared, org, inputs)
    assert error.value.status_code == 409
    monkeypatch.setattr(shared.workspace.library.documents, 'get', get)
    absent = deepcopy(inputs)
    absent[0]['binding']['ref']['version_id'] = str(uuid4())
    with pytest.raises(HTTPException) as error: verify_storage(shared, org, absent)
    assert error.value.status_code == 409
    assert verify_storage(shared, org, inputs)[0]['ref'] == inputs[0]['binding']['ref']


def test_bff_rechecks_after_io_blocks_private_proxy_and_never_creates_run(tmp_path, monkeypatch):
    import apps.workbench.backend.business_transport as transport
    _, grant = fixture(tmp_path)
    state = {'calls': 0, 'fault': None}
    async def authority(actor, method, path, body=None):
        assert actor == 'alice' and method == 'POST'
        assert path == f"projects/{grant['project_id']}/research-drafts/{grant['id']}/material-access"
        state['calls'] += 1
        if state['fault'] == 'revoke' and state['calls'] == 2:
            raise HTTPException(404, '准备单或所选资料不可访问')
        result = deepcopy(grant)
        if state['fault'] == 'changed' and state['calls'] == 2:
            result['manifest_digest'] = 'sha256:' + 'b' * 64
        return result
    monkeypatch.setattr(transport, 'space_business_request', authority)
    monkeypatch.setenv('FINSIGHT_RESOURCE_SPACES_ENABLED', '1')
    monkeypatch.setenv('FINSIGHT_BUSINESS_API_URL', 'http://127.0.0.1:9')
    monkeypatch.setenv('FINSIGHT_BUSINESS_SHARED_SECRET', 'synthetic-test-secret-with-at-least-32-bytes')
    app = app_at(tmp_path, monkeypatch)
    app.include_router(build_asset_workspace_router(tmp_path), prefix='/api/v1')
    app.include_router(build_business_gateway(), prefix='/api/v1')
    path = f"/api/v1/asset-workspace/organization-projects/{grant['project_id']}/research-drafts/{grant['id']}/verify"
    with TestClient(app) as client:
        assert client.post(path, headers={**WRITE, 'Origin': 'https://foreign.invalid'}, json={}).status_code == 403
        assert state['calls'] == 0
        response = client.post(path, headers=WRITE, json={})
        assert response.status_code == 200, response.text
        assert response.headers['cache-control'] == 'no-store'
        result = response.json()
        assert result['status'] == 'inputs_verified' and result['execution_enabled'] is False
        assert 'binding' not in str(result) and 'Pinned original evidence.' not in str(result)
        assert not {'thread_id', 'run_id'} & result.keys()
        assert state['calls'] == 2
        for fault, status in [('revoke', 404), ('changed', 409)]:
            state.update(calls=0, fault=fault)
            response = client.post(path, headers=WRITE, json={})
            assert response.status_code == status, response.text
            assert 'inputs_verified' not in response.text and state['calls'] == 2
        state.update(calls=0, fault=None)
        private = f"/api/v1/business/workspaces/projects/{grant['project_id']}/research-drafts/{grant['id']}/material-access"
        assert client.post(private, headers=WRITE, json={}).status_code == 404
        assert state['calls'] == 0
