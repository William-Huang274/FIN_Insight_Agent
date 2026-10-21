"""Actual BFF signatures/receipts/custody; native SDK fault injection, no models."""
import asyncio
from copy import deepcopy
from hashlib import sha256
import json
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from test_java_research_intake import intake, request
from test_organization_research_inputs import fixture
from test_organization_execution_access import runtime_grant


@pytest.fixture
def organization(intake, monkeypatch):
    shared, preparation = fixture(intake.service.attachment_store.root.parent / 'project-library')
    grant = runtime_grant(preparation)
    body = {'contract_version': 'organization_native_preparation.v1', 'execution_id': grant['execution_id'],
            'project_id': grant['project_id'], 'manifest_digest': grant['manifest_digest'],
            'execution': {'mode': 'auto', 'model': 'default', 'branch_ids': [], 'continuation_scope': 'original_plan'}}
    raw = json.dumps(body, separators=(',', ':')).encode()
    grant.update(prepare_request=body, prepare_request_digest='sha256:' + sha256(raw).hexdigest(),
                 prepare_operation_id=str(uuid4()), title='Organization synthetic research',
                 question='Use the pinned organization evidence without personal memory.')
    state = {'status': 200, 'creates': 0, 'authority_calls': 0, 'fault': None}
    async def authority(actor, method, path, body=None):
        assert actor == 'oidc:alice' and method == 'GET'
        assert path == f"projects/{grant['project_id']}/execution-bindings/{grant['execution_id']}/preparation-access"
        state['authority_calls'] += 1
        if state['status'] != 200: raise HTTPException(state['status'], 'synthetic revoked')
        return deepcopy(grant)
    monkeypatch.setattr('apps.workbench.backend.business_transport.space_business_request', authority)
    create = intake.service.sdk.threads.create
    async def native_create(*, metadata, thread_id, if_exists):
        assert if_exists == 'raise'
        state['creates'] += 1
        if thread_id in intake.threads:
            raise httpx.HTTPStatusError('native identity collision', request=httpx.Request('POST', 'http://native/threads'), response=httpx.Response(409))
        result = await create(metadata=metadata, thread_id=thread_id)
        if state['fault'] == 'lost_reply': raise httpx.ReadTimeout('persisted then lost native reply')
        if state['fault'] == 'revoke_after_create': state['status'] = 404
        return result
    monkeypatch.setattr(intake.service.sdk.threads, 'create', native_create)
    async def search(**kwargs): return list(intake.threads.values())
    intake.service.sdk.threads.search = search
    monkeypatch.setattr('apps.workbench.backend.authentication.OIDCBackend.verify', lambda self, token: 'oidc:alice')
    return SimpleNamespace(intake=intake, grant=grant, body=body, state=state, shared=shared)


def prepare(client, s):
    return request(client, 'organization/prepare', s.body, s.grant['prepare_operation_id'])


def state(client, s):
    return request(client, f"organization/executions/{s.grant['execution_id']}/state?project_id={s.grant['project_id']}")


def test_org_thread_is_atomic_frozen_and_not_a_personal_research(organization, monkeypatch):
    s = organization
    with TestClient(s.intake.app()) as c:
        saved = prepare(c, s)
        assert saved.status_code == 200, saved.text
        tid = s.grant['execution_id']
        meta = s.intake.threads[tid]['metadata']
        assert meta['owner_id'] == 'organization:' + s.grant['organization_id']
        assert meta['surface'] == 'organization_research_workbench'
        assert meta['organization_execution']['prepare_operation_id'] == s.grant['prepare_operation_id']
        assert meta['organization_run_configuration']['configurable']['finsight_execution'] == s.body['execution']
        assert not {'asset_context', 'studio_assistant_id', 'business_intake'} & meta.keys()
        assert not s.intake.library.index('oidc:alice')['assignments']
        assert s.intake.service.attachment_store.list(tid) == [] and not s.intake.runs
        monkeypatch.setattr('apps.workbench.backend.organization_native_drafts.default_configuration', lambda: pytest.fail('must use saved configuration'))
        assert prepare(c, s).json() == saved.json()
        assert state(c, s).json() == saved.json()
        headers = {'Authorization': 'Bearer synthetic', 'X-Workbench-Request': '1'}
        assert c.get('/api/v1/research-sessions', headers=headers).json() == []
        assert c.get(f'/api/v1/research-sessions/{tid}', headers=headers).status_code == 404
        assert c.post(f'/api/v1/research-sessions/{tid}/start', headers=headers).status_code == 404
        assert s.state['creates'] == 1
        s.state['status'] = 404
        assert prepare(c, s).status_code == 404  # Authorization precedes cached receipt.
        assert state(c, s).status_code == 404
    s.state['status'] = 200
    with TestClient(s.intake.app()) as c:
        assert prepare(c, s).json() == saved.json() and s.state['creates'] == 1


def test_organization_can_prepare_while_personal_execution_is_disabled(organization):
    s = organization
    s.intake.service.organization_research_profile = s.intake.service.research_profile
    s.intake.service.research_profile = None
    with TestClient(s.intake.app()) as c:
        assert prepare(c, s).status_code == 200
        headers = {'Authorization': 'Bearer synthetic', 'X-Workbench-Request': '1'}
        assert c.get('/api/v1/research-session-config', headers=headers).json()['fresh_research_enabled'] is False
        assert not s.intake.runs


@pytest.mark.parametrize('fault', ['lost_reply', 'revoke_after_create'])
def test_uncertain_native_create_only_reconciles_original_thread(organization, fault):
    s = organization
    s.state['fault'] = fault
    with TestClient(s.intake.app(), raise_server_exceptions=False) as c:
        first = prepare(c, s)
        assert first.status_code == (500 if fault == 'lost_reply' else 409)
        assert len(s.intake.threads) == 1 and not s.intake.runs
        s.state.update(status=200, fault=None)
        replay = prepare(c, s)
        assert replay.status_code == 409 and replay.json()['submission_status'] == 'unknown'
        recovered = state(c, s)
        assert recovered.status_code == 200, recovered.text
        assert recovered.json()['thread_id'] == s.grant['execution_id']
        assert s.state['creates'] == 1


@pytest.mark.parametrize('fault', ['identity', 'configuration', 'operation', 'foreign_thread', 'unexpected_run'])
def test_reconciliation_never_repairs_or_overwrites_mismatched_native_state(organization, fault):
    s = organization
    with TestClient(s.intake.app()) as c:
        assert prepare(c, s).status_code == 200
        thread = s.intake.threads[s.grant['execution_id']]
        if fault == 'identity': thread['metadata']['owner_id'] = 'oidc:alice'
        if fault == 'configuration': thread['metadata']['organization_run_configuration']['configurable']['finsight_execution']['model'] = 'deepseek-v4-pro'
        if fault == 'operation': thread['metadata']['organization_execution']['prepare_operation_id'] = str(uuid4())
        if fault == 'foreign_thread': thread['thread_id'] = str(uuid4())
        if fault == 'unexpected_run': s.intake.runs[s.grant['execution_id']] = [{'run_id': str(uuid4())}]
        before = deepcopy(s.intake.threads)
        assert state(c, s).status_code == 409
        assert s.intake.threads == before and s.state['creates'] == 1


def test_altered_request_and_missing_original_stop_before_native_create(organization, monkeypatch):
    s = organization
    with TestClient(s.intake.app()) as c:
        altered = deepcopy(s.body); altered['execution']['model'] = 'deepseek-v4-pro'
        assert request(c, 'organization/prepare', altered, s.grant['prepare_operation_id']).status_code == 409
        # Use actual original storage with injected corruption at the read boundary.
        from sec_agent.research_foundation.task_attachments import TaskAttachmentStore
        get = TaskAttachmentStore.get
        monkeypatch.setattr(TaskAttachmentStore, 'get', lambda self, *a, **k: {**get(self, *a, **k), 'body': b'corrupt'})
        assert prepare(c, s).status_code == 409
        assert s.state['creates'] == 0 and not s.intake.threads


def test_conflicting_native_uuid_is_never_overwritten(organization):
    s = organization
    tid = s.grant['execution_id']
    original = {'thread_id': tid, 'metadata': {'owner_id': 'someone-else', 'surface': 'research_workbench'}, 'status': 'idle'}
    s.intake.threads[tid] = deepcopy(original)
    with TestClient(s.intake.app(), raise_server_exceptions=False) as c:
        assert prepare(c, s).status_code == 500
        assert state(c, s).status_code == 409
    assert s.intake.threads[tid] == original


def test_actual_research_factory_rejects_org_before_host_models_or_memory(monkeypatch):
    from sec_agent.agent_runtime.research_session_runtime import research_session_graph
    monkeypatch.setattr('sec_agent.agent_runtime.agent_server_entry._require_langsmith_execution_environment', lambda config: None)
    monkeypatch.setenv('FINSIGHT_RESEARCH_SESSION_ENABLED', '1')
    monkeypatch.delenv('FIN_REPO_ROOT', raising=False)  # Reading settings would fail: the guard must precede it.
    async def get(tid): return {'metadata': {'surface': 'organization_research_workbench', 'organization_execution': {'execution_id': tid}}}
    monkeypatch.setattr('langgraph_sdk.get_client', lambda: SimpleNamespace(threads=SimpleNamespace(get=get)))
    async def exercise():
        with pytest.raises(ValueError, match='organization_research_runtime_not_enabled'):
            async with research_session_graph({'configurable': {'thread_id': str(uuid4()), 'run_id': str(uuid4())}}, SimpleNamespace(execution_runtime=True)):
                pytest.fail('organization graph cannot enter the personal runtime')
    asyncio.run(exercise())
