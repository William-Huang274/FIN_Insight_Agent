"""Signed multi-round transport and actual resume checks; no provider calls."""
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
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from test_java_research_intake import intake, request
from test_organization_native_drafts import organization
from test_organization_native_start import starting, start
from test_case_review_agent import artifacts, call
from test_report_session import setup_session
from sec_agent.agent_runtime.organization_continuation_contract import baseline_digest
from sec_agent.agent_runtime.organization_report_action_contract import (
    action_request, validate_baseline, check_resumed_action,
)
from sec_agent.agent_runtime.organization_native_runtime import admit
from sec_agent.agent_runtime.report_session import ReviewAction, build_report_session_graph
from sec_agent.agent_runtime.targeted_revision import report_digest


@pytest.fixture
def reporting(starting, monkeypatch):
    s = starting
    with TestClient(s.intake.app()) as c:
        first = start(c, s).json()
    tid = s.grant['execution_id']
    s.intake.runs[tid][0]['status'] = 'success'
    s.baseline = {'checkpoint': {'checkpoint_id': str(uuid4()), 'thread_id': tid},
        'next': ['human_review'], 'tasks': [{'interrupts': [{'value': {'kind': 'dell_report_review'}}]}],
        'values': {'question': s.grant['question'], 'report_version': 1, 'report': {'title': 'Static report'},
                   'phase': 'ready_for_human_review'}}
    p = {k: s.start_body[k] for k in ('execution_id', 'project_id', 'manifest_digest', 'prepare_operation_id',
                                     'configuration_digest', 'research_as_of')}
    p.update(contract_version='organization_report_action.v1', command_id=str(uuid4()), previous_run_id=first['run_id'],
        checkpoint_id=s.baseline['checkpoint']['checkpoint_id'], state_digest=baseline_digest(s.baseline),
        report_version=1, report_digest=report_digest(s.baseline['values']['report']),
        action='ask', message='Explain this report', answer_mode='quick', target=None)
    s.action_body = p
    s.action_grant = {k: deepcopy(v) for k, v in s.start_grant.items() if not k.startswith('start_')}
    s.action_grant.update(report_command_id=p['command_id'], report_action_request=p,
        report_action_operation_id=str(uuid4()),
        report_action_request_digest='sha256:' + sha256(json.dumps(p, separators=(',', ':')).encode()).hexdigest())

    async def authority(actor, method, path, body=None):
        assert actor == 'oidc:alice' and path.endswith(f"/report-commands/{s.action_grant['report_command_id']}/access")
        if s.state['status'] != 200:
            raise HTTPException(s.state['status'], 'revoked')
        return deepcopy(s.action_grant)
    monkeypatch.setattr('apps.workbench.backend.organization_report_actions.space_business_request', authority)
    monkeypatch.setenv('FINSIGHT_ORGANIZATION_REPORT_ACTIONS_ENABLED', '1')
    async def state(t, **kw):
        return deepcopy(s.baseline)
    s.intake.service.sdk.threads.get_state = state
    async def create(t, graph, **kwargs):
        assert 'input' not in kwargs and kwargs['multitask_strategy'] == 'reject'
        s.actual = deepcopy(kwargs)
        run = {'thread_id': t, 'run_id': str(uuid4()), 'metadata': kwargs['metadata'], 'status': 'pending'}
        s.intake.runs[t].append(deepcopy(run))
        if s.state['fault'] == 'lost_reply':
            raise httpx.ReadTimeout('persisted before reply loss')
        if s.state['fault'] == 'revoke_after_create':
            s.state['status'] = 404
        return run
    s.intake.service.sdk.runs.create = create
    s.usage = {'recorded_requests': 1, 'unknown_or_pending_requests': 0, 'partial_audit': False}
    monkeypatch.setattr('apps.workbench.backend.api.v1.report_sessions.public_run_usage', lambda *a: ([], s.usage))
    return s


def submit(c, s):
    return request(c, 'organization/report-actions', s.action_body, s.action_grant['report_action_operation_id'])


def reconcile(c, s):
    return request(c, f"organization/executions/{s.grant['execution_id']}/report-actions/{s.action_grant['report_command_id']}?project_id={s.grant['project_id']}")


def test_signed_action_replays_after_restart_but_rechecks_current_permission(reporting):
    s = reporting
    with TestClient(s.intake.app()) as c:
        result = submit(c, s)
        assert result.status_code == 200, result.text
        assert s.actual['command']['resume'] == {'action': 'ask', 'message': 'Explain this report', 'answer_mode': 'quick'}
        assert submit(c, s).json() == reconcile(c, s).json() == result.json()
    with TestClient(s.intake.app()) as c:
        assert submit(c, s).json() == result.json()
        s.state['status'] = 404
        assert submit(c, s).status_code == reconcile(c, s).status_code == 404
    assert len(s.intake.runs[s.grant['execution_id']]) == 2


@pytest.mark.parametrize('fault', ['lost_reply', 'revoke_after_create'])
def test_uncertain_action_is_query_only(reporting, fault):
    s = reporting
    s.state['fault'] = fault
    with TestClient(s.intake.app(), raise_server_exceptions=False) as c:
        assert submit(c, s).status_code in (409, 500)
        s.state.update(status=200, fault=None)
        assert submit(c, s).json()['submission_status'] == 'unknown'
        assert reconcile(c, s).status_code == 200
    assert len(s.intake.runs[s.grant['execution_id']]) == 2


def test_preflight_crash_is_known_not_dispatched_but_never_retried(reporting, monkeypatch):
    s = reporting
    def crash(*args):
        raise RuntimeError('interrupted before SDK boundary')
    monkeypatch.setattr('apps.workbench.backend.organization_report_actions.verify_storage', crash)
    with TestClient(s.intake.app(), raise_server_exceptions=False) as c:
        assert submit(c, s).status_code == 500
        assert submit(c, s).json()['submission_status'] == 'unknown'
        response = reconcile(c, s)
        assert response.status_code == 409
        assert response.json()['submission_status'] == 'not_dispatched'
        s.state['status'] = 404
        assert reconcile(c, s).status_code == 404
    assert len(s.intake.runs[s.grant['execution_id']]) == 1


def test_sdk_timeout_without_visible_run_is_still_unknown(reporting):
    s = reporting
    async def crash(*args, **kwargs):
        raise httpx.ReadTimeout('server acceptance cannot be inferred')
    s.intake.service.sdk.runs.create = crash
    with TestClient(s.intake.app(), raise_server_exceptions=False) as c:
        assert submit(c, s).status_code == 500
        result = reconcile(c, s)
        assert result.status_code == 409
        assert result.json().get('submission_status') != 'not_dispatched'
    assert len(s.intake.runs[s.grant['execution_id']]) == 1


@pytest.mark.parametrize('fault', ['checkpoint', 'report', 'version', 'interrupt', 'busy', 'failed',
                                 'unknown_usage', 'partial_audit', 'missing_audit', 'configuration', 'operation', 'payload'])
def test_stale_or_unauthorized_action_never_dispatches(reporting, fault):
    s = reporting
    tid = s.grant['execution_id']
    if fault == 'checkpoint': s.baseline['checkpoint']['checkpoint_id'] = str(uuid4())
    elif fault == 'report': s.baseline['values']['report']['title'] = 'Changed'
    elif fault == 'version': s.baseline['values']['report_version'] = 2
    elif fault == 'interrupt': s.baseline['tasks'] = []
    elif fault == 'busy': s.intake.threads[tid]['status'] = 'busy'
    elif fault == 'failed': s.intake.runs[tid][0]['status'] = 'error'
    elif fault == 'unknown_usage': s.usage['unknown_or_pending_requests'] = 1
    elif fault == 'partial_audit': s.usage['partial_audit'] = True
    elif fault == 'missing_audit': s.usage = None
    elif fault == 'configuration': s.intake.threads[tid]['metadata']['configuration_digest'] = 'bad'
    elif fault == 'operation': s.action_grant['report_action_operation_id'] = str(uuid4())
    else: s.action_body['execution'] = {'mode': 'single'}
    with TestClient(s.intake.app()) as c:
        response = request(c, 'organization/report-actions', s.action_body,
            str(uuid4()) if fault == 'operation' else s.action_grant['report_action_operation_id'])
        assert response.status_code == 409, response.text
    assert len(s.intake.runs[tid]) == 1


def test_multiple_questions_same_report_and_old_receipt_beyond_first_page(reporting):
    s = reporting
    tid = s.grant['execution_id']
    with TestClient(s.intake.app()) as c:
        first = submit(c, s)
        assert first.status_code == 200, first.text
        first_grant = deepcopy(s.action_grant)
        s.intake.runs[tid][-1]['status'] = 'success'
        s.baseline['checkpoint']['checkpoint_id'] = str(uuid4())
        s.baseline['values']['conversation'] = [{'role': 'assistant', 'content': 'Static first answer'}]
        s.action_body.update(command_id=str(uuid4()), previous_run_id=first.json()['run_id'],
            checkpoint_id=s.baseline['checkpoint']['checkpoint_id'], state_digest=baseline_digest(s.baseline),
            message='A different second question')
        s.action_grant.update(report_command_id=s.action_body['command_id'], report_action_operation_id=str(uuid4()),
            report_action_request_digest='sha256:' + sha256(json.dumps(s.action_body, separators=(',', ':')).encode()).hexdigest())
        assert submit(c, s).status_code == 200
        assert s.action_body['report_version'] == 1
        # The original operation must remain resolvable after many later rounds.
        s.intake.runs[tid][0:0] = [{'run_id': str(uuid4()), 'status': 'success', 'metadata': {}} for _ in range(105)]
        s.action_grant = first_grant
        assert reconcile(c, s).json()['run_id'] == first.json()['run_id']


@pytest.mark.parametrize('fault', [None, 'citation', 'version', 'checkpoint', 'request_id', 'reused'])
def test_targeted_revision_uses_saved_citation_and_exact_request(reporting, fault):
    s = reporting
    s.baseline['values']['report']['citations'] = {'C1': {'claim': {'statement': 'Saved claim'}, 'sources': []}}
    p = s.action_body
    p.update(action='revise', answer_mode='deep', report_digest=report_digest(s.baseline['values']['report']))
    p['target'] = {'request_id': p['command_id'], 'citation_id': 'C1', 'base_version': 1,
                   'base_digest': p['report_digest'], 'base_checkpoint': p['checkpoint_id']}
    if fault == 'citation': p['target']['citation_id'] = 'NotInReport'
    elif fault == 'version': p['target']['base_version'] = 2
    elif fault == 'checkpoint': p['target']['base_checkpoint'] = str(uuid4())
    elif fault == 'request_id': p['target']['request_id'] = str(uuid4())
    elif fault == 'reused': s.baseline['values']['handled_revision_request_ids'] = [p['command_id']]
    p['state_digest'] = baseline_digest(s.baseline)
    s.action_grant['report_action_request_digest'] = 'sha256:' + sha256(json.dumps(p, separators=(',', ':')).encode()).hexdigest()
    with TestClient(s.intake.app()) as c:
        result = submit(c, s)
        assert result.status_code == (409 if fault else 200), result.text
    assert len(s.intake.runs[s.grant['execution_id']]) == (1 if fault else 2)


@pytest.mark.parametrize('fault', [None, 'config', 'snapshot', 'receipt', 'previous_status'])
def test_native_action_admission_before_opening_resources(reporting, fault):
    s = reporting
    grant = deepcopy(s.action_grant)
    tid, rid = grant['execution_id'], str(uuid4())
    thread = s.intake.threads[tid]
    args = action_request(thread, grant)
    grant['authorized_run_id'] = rid
    run = {'thread_id': tid, 'run_id': rid, 'status': 'running', **args}
    async def get(t, r):
        return deepcopy(run) if r == rid else {'run_id': r, 'status': 'error' if fault == 'previous_status' else 'success'}
    async def saved(t):
        return deepcopy(s.baseline)
    class Authority:
        run_id = rid
        def __call__(self):
            return grant
    config = deepcopy(args['config'])
    if fault == 'config': config['configurable']['finsight_organization_start'] = {}
    elif fault == 'snapshot': s.baseline['values']['report_version'] += 1
    elif fault == 'receipt': run['metadata']['organization_dispatch_digest'] = 'bad'
    native = SimpleNamespace(runs=SimpleNamespace(get=get), threads=SimpleNamespace(get_state=saved))
    if fault:
        with pytest.raises(ValueError):
            asyncio.run(admit(native, config, thread, Authority()))
    else:
        assert asyncio.run(admit(native, config, thread, Authority())) == grant


@pytest.mark.parametrize('tamper', ['message', 'accept', 'execution'])
def test_actual_human_review_rejects_changed_resume_before_any_writer(artifacts, tamper):
    async def run():
        _, _, initial, _ = setup_session(artifacts)
        initial['question'] = 'Fixed organization question'
        grant = {'question': initial['question'], 'report_action_request': {
            'report_version': 1, 'report_digest': report_digest(initial['report']),
            'action': 'ask', 'message': 'Authorized question', 'answer_mode': 'deep', 'target': None}}
        def check(values, action):
            # Standalone report state has no research question channel.
            check_resumed_action({**values, 'question': initial['question']}, action, grant)
        from langchain_core.runnables import RunnableLambda
        calls = []
        def writer(value):
            calls.append(value)
            raise AssertionError('Unauthorized writer must not execute')
        graph = build_report_session_graph(writer=RunnableLambda(writer), verifier=RunnableLambda(writer),
            artifacts=artifacts, initial=initial, review_action_check=check).compile(checkpointer=InMemorySaver())
        cfg = {'configurable': {'thread_id': str(uuid4())}}
        await graph.ainvoke({'open': True}, cfg)
        action = {'action': 'ask', 'message': 'Authorized question'}
        if tamper == 'message': action['message'] = 'Unapproved question'
        elif tamper == 'accept': action = {'action': 'accept'}
        else: action['execution'] = {'mode': 'auto'}
        with pytest.raises(ValueError, match='resumed_action_mismatch'):
            await graph.ainvoke(Command(resume=action), cfg)
        assert not calls
        assert (await graph.aget_state(cfg)).values['report'] == initial['report']
    asyncio.run(run())
