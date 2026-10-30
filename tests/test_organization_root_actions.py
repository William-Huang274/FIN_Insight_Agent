"""Continuous root actions use durable receipts and current authorization."""
from copy import deepcopy
from hashlib import sha256
import json
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from test_java_research_intake import intake, request
from test_organization_native_drafts import organization
from test_organization_work_session import continuous
from sec_agent.agent_runtime.organization_native_contract import run_request
from sec_agent.agent_runtime.organization_continuation_contract import baseline_digest


@pytest.fixture
def root(continuous, monkeypatch):
    s = continuous
    tid = s.grant['execution_id']
    previous = str(uuid4())
    s.intake.runs[tid] = [{'thread_id': tid, 'run_id': previous, 'status': 'success',
                           **run_request(s.intake.threads[tid], s.start_grant)}]
    s.baseline = {'checkpoint': {'checkpoint_id': str(uuid4())}, 'next': [],
        'values': {'question': s.grant['question'], 'messages': [{'role': 'assistant', 'content': 'Existing answer'}],
                   'task_outcome': {'run_id': previous}}}
    payload = {k: s.start_grant['start_request'][k] for k in ('execution_id', 'project_id', 'manifest_digest',
        'prepare_operation_id', 'configuration_digest', 'research_as_of')}
    payload.update(contract_version='organization_root_action.v1', command_id=str(uuid4()), previous_run_id=previous,
        checkpoint_id=s.baseline['checkpoint']['checkpoint_id'], state_digest=baseline_digest(s.baseline),
        action='continue', message='Explain the existing answer with the same sources', delivery_intent='answer', require_report_review=False)
    s.action_grant = {k: v for k, v in s.start_grant.items() if not k.startswith('start_')}
    s.action_grant.update(report_command_id=payload['command_id'], report_action_request=payload,
        report_action_operation_id=str(uuid4()), report_action_request_digest='sha256:'+sha256(json.dumps(payload, separators=(',', ':')).encode()).hexdigest())
    s.action_body = payload
    async def authority(actor, method, path, body=None):
        assert actor == 'oidc:alice'
        assert path.endswith('/'+payload['command_id']+'/access')
        if s.state['status'] != 200: raise HTTPException(s.state['status'], 'revoked')
        return deepcopy(s.action_grant)
    monkeypatch.setattr('apps.workbench.backend.organization_report_actions.space_business_request', authority)
    monkeypatch.setenv('FINSIGHT_ORGANIZATION_REPORT_ACTIONS_ENABLED', '1')
    async def state(t, **kwargs): return deepcopy(s.baseline)
    s.intake.service.sdk.threads.get_state = state
    async def create(t, graph, **kwargs):
        assert 'command' not in kwargs and kwargs['multitask_strategy'] == 'reject'
        assert kwargs['input'] == (None if payload['action'] == 'recover' else
            {'question': s.grant['question'], 'messages': [{'role': 'user', 'content': payload['message']}]})
        s.actual = deepcopy(kwargs)
        run = {'thread_id': t, 'run_id': str(uuid4()), 'status': 'pending', 'metadata': kwargs['metadata']}
        s.intake.runs[t].append(deepcopy(run))
        if s.state['fault'] == 'lost_reply': raise httpx.ReadTimeout('saved then lost')
        return run
    s.intake.service.sdk.runs.create = create
    s.usage = {'recorded_requests': 1, 'unknown_or_pending_requests': 0, 'partial_audit': False}
    monkeypatch.setattr('apps.workbench.backend.api.v1.report_sessions.public_run_usage', lambda *a: ([], s.usage))
    return s


def submit(c, s):
    return request(c, 'organization/root-actions', s.action_body, s.action_grant['report_action_operation_id'])


def reconcile(c, s):
    return request(c, f"organization/executions/{s.grant['execution_id']}/root-actions/{s.action_body['command_id']}?project_id={s.grant['project_id']}")


def test_root_action_replay_reconcile_and_revocation(root):
    s = root
    with TestClient(s.intake.app()) as c:
        accepted = submit(c, s)
        assert accepted.status_code == 200, accepted.text
        assert submit(c, s).json() == reconcile(c, s).json() == accepted.json()
    with TestClient(s.intake.app()) as c:
        assert submit(c, s).json() == accepted.json()
        s.state['status'] = 404
        assert submit(c, s).status_code == reconcile(c, s).status_code == 404
    assert len(s.intake.runs[s.grant['execution_id']]) == 2


def test_lost_root_reply_is_reconciled_without_new_model_run(root):
    s = root; s.state['fault'] = 'lost_reply'
    with TestClient(s.intake.app(), raise_server_exceptions=False) as c:
        assert submit(c, s).status_code in (409, 500)
        s.state['fault'] = None
        assert submit(c, s).json()['submission_status'] == 'unknown'
        assert reconcile(c, s).status_code == 200
    assert len(s.intake.runs[s.grant['execution_id']]) == 2


def test_failed_root_recovery_is_explicit_idempotent_and_does_not_replace_history(root):
    s = root
    s.action_body['action'] = 'recover'
    s.baseline['next'] = ['work']
    s.baseline['metadata'] = {'run_id': s.action_body['previous_run_id']}
    s.action_body['state_digest'] = baseline_digest(s.baseline)
    s.action_grant['report_action_request_digest'] = 'sha256:'+sha256(json.dumps(s.action_body, separators=(',', ':')).encode()).hexdigest()
    s.intake.runs[s.grant['execution_id']][0]['status'] = 'error'
    original = deepcopy(s.baseline)
    with TestClient(s.intake.app()) as c:
        accepted = submit(c, s)
        assert accepted.status_code == 200, accepted.text
        assert submit(c, s).json() == reconcile(c, s).json() == accepted.json()
    assert s.baseline == original
    assert s.actual['input'] is None and 'checkpoint_id' not in s.actual
    assert s.intake.runs[s.grant['execution_id']][0]['status'] == 'error'


@pytest.mark.parametrize('fault', ['pending', 'checkpoint', 'history', 'outcome', 'usage', 'disabled', 'old_route'])
def test_wrong_root_baseline_or_route_cannot_dispatch(root, monkeypatch, fault):
    s = root
    if fault == 'pending': s.baseline['next'] = ['work']
    elif fault == 'checkpoint': s.baseline['checkpoint']['checkpoint_id'] = str(uuid4())
    elif fault == 'history': s.baseline['values']['messages'] = []
    elif fault == 'outcome': s.baseline['values']['task_outcome']['run_id'] = str(uuid4())
    elif fault == 'usage': s.usage['unknown_or_pending_requests'] = 1
    elif fault == 'disabled': monkeypatch.setenv('FINSIGHT_ON_DEMAND_ENABLED', '0')
    with TestClient(s.intake.app()) as c:
        response = (request(c, 'organization/report-actions', s.action_body, s.action_grant['report_action_operation_id'])
                    if fault == 'old_route' else submit(c, s))
        assert response.status_code in (409, 503), response.text
    assert len(s.intake.runs[s.grant['execution_id']]) == 1
