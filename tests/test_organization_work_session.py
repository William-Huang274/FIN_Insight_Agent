"""Versioned root admission and real native parent loop, no supplier calls."""
import asyncio
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from langchain.agents.middleware import AgentMiddleware

from test_java_research_intake import intake
from test_organization_native_drafts import organization, prepare
from test_organization_source_navigation import navigation, read_first
from sec_agent.agent_runtime.organization_native_contract import run_request, validate_start


@pytest.fixture
def continuous(organization, monkeypatch):
    s = organization
    monkeypatch.setenv('FINSIGHT_ON_DEMAND_ENABLED', '1')
    s.body['contract_version'] = 'organization_native_preparation.v2'
    s.body['execution']['delivery_intent'] = 'answer'
    s.grant['prepare_request_digest'] = 'sha256:' + sha256(json.dumps(s.body, separators=(',', ':')).encode()).hexdigest()
    with TestClient(s.intake.app()) as client:
        receipt = prepare(client, s)
    assert receipt.status_code == 200, receipt.text
    grant = deepcopy(s.grant)
    payload = {key: grant[key] for key in ('execution_id', 'project_id', 'manifest_digest', 'prepare_operation_id')}
    payload.update(contract_version='organization_native_start.v2', stage='work_session',
        research_as_of=json.loads(grant['manifest_text'])['research_as_of'] + 'T23:59:59+00:00',
        configuration_digest=receipt.json()['configuration_digest'])
    grant.update(start_request=payload, start_operation_id=str(uuid4()), configuration_digest=payload['configuration_digest'],
        start_request_digest='sha256:' + sha256(json.dumps(payload, separators=(',', ':')).encode()).hexdigest())
    s.start_grant = grant
    return s


def test_new_preparation_accepts_answer_but_never_aliases_orientation(continuous):
    grant = continuous.start_grant
    thread = continuous.intake.threads[grant['execution_id']]
    args = run_request(thread, grant)
    assert args['input'] == {'question': grant['question'], 'messages': [{'role': 'user', 'content': grant['question']}]}
    grant['start_request']['stage'] = 'orientation'
    with pytest.raises(ValueError, match='contract_mismatch'):
        validate_start(grant)


def test_parent_source_view_preserves_delegated_evidence_but_not_model_claims(navigation):
    from langchain_core.messages import ToolMessage
    from sec_agent.agent_runtime.organization_work_session import artifact_reader
    nav, state, _ = navigation
    original = read_first(nav).items[0]
    identity = original['passage_id']
    data = SimpleNamespace(foundation_binding=SimpleNamespace(case_id='test-root', research_as_of='2026-10-12',
        snapshot_id='frozen', foundation_digest='frozen'), decision_digest='decision',
        source_route_catalog_digest='catalog', inventory_snapshot_digest='inventory')
    result = artifact_reader(data, nav, {'messages': [
        ToolMessage(name='read_delegated_evidence', tool_call_id='read1', content='paged view', artifact={'source_items': {identity: original}}),
        AIMessage(content='Unsupported claims are not observations')], 'synthesis': {'sources': [{'passage_id': 'forged'}]}})
    assert result.source_snapshot() == {identity: original}
    assert artifact_reader(data, nav, {'messages': [ToolMessage(name='read_delegated_evidence', tool_call_id='bad',
        content='failed', status='error', artifact={'source_items': {identity: original}})]}).source_snapshot() == {}


@pytest.mark.parametrize('next_delivery', ['answer', 'workpaper', 'report'])
def test_native_work_session_uses_same_parent_and_does_not_start_old_graph(continuous, tmp_path, monkeypatch, next_delivery):
    from sec_agent.agent_runtime import research_session_runtime as runtime
    from sec_agent.research_foundation.organization_execution_access import OrganizationExecutionAuthority
    s = continuous
    grant = deepcopy(s.start_grant)
    tid, rid = grant['execution_id'], str(uuid4())
    thread = s.intake.threads[tid]
    args = run_request(thread, grant)
    config = deepcopy(args['config'])
    config['configurable'].update(thread_id=tid, run_id=rid)
    grant['authorized_run_id'] = rid
    resources = {key: grant[key] for key in ('contract_version', 'execution_id', 'thread_id', 'project_id', 'draft_id',
        'organization_id', 'manifest_digest', 'status', 'native_execution_enabled', 'manifest_text', 'inputs')}
    monkeypatch.setattr(OrganizationExecutionAuthority, 'request', lambda self, path, body: deepcopy(grant if path.endswith('/admit-start') else resources))
    async def get_run(t, r): return {'thread_id': tid, 'run_id': rid, 'status': 'running', **args}
    async def get_thread(t): return deepcopy(thread)
    saved_state = {'values': {}}
    async def saved(t, **kwargs): return deepcopy(saved_state)
    async def close(): pass
    native = SimpleNamespace(runs=SimpleNamespace(get=get_run), threads=SimpleNamespace(get=get_thread, get_state=saved),
                             http=SimpleNamespace(client=SimpleNamespace(aclose=close)))
    monkeypatch.setattr('langgraph_sdk.get_client', lambda: native)
    monkeypatch.setattr('sec_agent.agent_runtime.agent_server_entry._require_langsmith_execution_environment', lambda _: None)
    settings = tmp_path / 'settings.json'
    settings.write_text(json.dumps({'workbench_url': 'https://workbench.example.test', 'audit_root': str(tmp_path / 'audit')}))
    env = {'FIN_REPO_ROOT': str(Path(__file__).resolve().parents[1]), 'FINSIGHT_REPORT_SESSION_SETTINGS': str(settings),
        'FINSIGHT_RESEARCH_SESSION_ENABLED': '1', 'FINSIGHT_ORGANIZATION_START_ENABLED': '1',
        'FINSIGHT_BUSINESS_API_URL': 'http://127.0.0.1:9', 'FINSIGHT_WORKING_MEMORY_PATH': str(tmp_path / 'memory.sqlite'),
        'FINSIGHT_ORGANIZATION_RUNTIME_SECRET': 'synthetic-only-native-work-session',
        'FINSIGHT_ORGANIZATION_ASSETS_ROOT': str(s.intake.service.attachment_store.root.parent / 'project-library' / 'organization-assets'),
        'DEEPSEEK_API_KEY': 'offline-not-a-key'}
    for key, value in env.items(): monkeypatch.setenv(key, value)
    monkeypatch.delenv('FINSIGHT_ORGANIZATION_TASK_ACTIONS_ENABLED', raising=False)
    monkeypatch.setattr('sec_agent.agent_runtime.research_budget.budget_from_host',
        lambda *a, **k: SimpleNamespace(guard=lambda *a: None))
    class Model(FakeMessagesListChatModel):
        def bind_tools(self, *args, **kwargs):
            from langchain_core.utils.function_calling import convert_to_openai_tool
            for current in args[0]:
                schema = convert_to_openai_tool(current)['function']
                if schema['name'] == 'read_source_document':
                    request = schema['parameters']['properties']['request']['properties']
                    assert request['source_space']['const'] == 'organization'
                    assert request['source_space']['default'] == 'organization'
                    assert 'company_section' not in request
            return self
    monkeypatch.setattr('sec_agent.agent_runtime.case_review_agent.case_chat_model',
        lambda *a, **k: Model(responses=[AIMessage(content='已回答当前问题；没有启动完整研报流程。')]))
    monkeypatch.setattr('sec_agent.agent_runtime.conversation_summary.summary_middleware', lambda *a, **k: AgentMiddleware())
    monkeypatch.setattr(runtime, 'build_research_session_graph', lambda **k: pytest.fail('old stage graph entered'))
    async def exercise():
        async with runtime.research_session_graph(config, SimpleNamespace(execution_runtime=True)) as graph:
            return await graph.ainvoke(args['input'], config)
    result = asyncio.run(exercise())
    assert result['task_outcome']['artifact_kind'] == 'answer'
    assert result['task_outcome']['execution_status'] == 'submitted'
    assert not result.get('report') and not result.get('research_operation')
    # A second admitted user turn carries native history, not an old report
    # stage or a newly invented task. Validate the actual guarded parent again.
    from sec_agent.agent_runtime.organization_continuation_contract import baseline_digest
    from sec_agent.agent_runtime.organization_report_action_contract import action_request
    from langchain_core.messages import message_to_dict, HumanMessage
    previous = rid
    saved_state.update(values={**result, 'messages': [message_to_dict(m)['data'] for m in result['messages']]},
                       checkpoint={'checkpoint_id': str(uuid4())}, next=[])
    payload = {k: grant['start_request'][k] for k in ('execution_id', 'project_id', 'manifest_digest',
        'prepare_operation_id', 'configuration_digest', 'research_as_of')}
    payload.update(contract_version='organization_root_action.v1', command_id=str(uuid4()), previous_run_id=previous,
        checkpoint_id=saved_state['checkpoint']['checkpoint_id'], state_digest=baseline_digest(saved_state), action='continue', message='Continue the same question',
        delivery_intent=next_delivery, require_report_review=False)
    grant = {k: v for k, v in grant.items() if not k.startswith('start_')}
    rid = str(uuid4())
    grant.update(authorized_run_id=rid, report_command_id=payload['command_id'], report_action_request=payload,
        report_action_operation_id=str(uuid4()), report_action_request_digest='sha256:'+sha256(json.dumps(payload, separators=(',', ':')).encode()).hexdigest())
    args = action_request(thread, grant)
    config = deepcopy(args['config']); config['configurable'].update(thread_id=tid, run_id=rid)
    monkeypatch.setenv('FINSIGHT_ORGANIZATION_REPORT_ACTIONS_ENABLED', '1')
    monkeypatch.setattr(OrganizationExecutionAuthority, 'request', lambda self, path, body: deepcopy(grant if path.endswith('/admit-report-action') else resources))
    async def continued_run(t, r):
        return {'run_id': previous, 'status': 'success'} if r == previous else {'thread_id': tid, 'run_id': rid, 'status': 'running', **args}
    native.runs.get = continued_run
    if next_delivery == 'workpaper':
        from langchain_core.outputs import ChatResult, ChatGeneration
        class WorkingPaperModel(Model):
            def _generate(self, messages, stop=None, run_manager=None, **kwargs):
                last = messages[-1]
                if getattr(last, 'name', '') == 'WriteWorkingNote':
                    receipt = json.loads(last.content)
                    assert receipt['saved'] is True
                    call = {'name': 'deliver_working_note', 'id': 'deliver-note',
                            'args': {'note_id': receipt['note_id'], 'version': receipt['version']}}
                else:
                    call = {'name': 'WriteWorkingNote', 'id': 'save-note',
                            'args': {'title': 'Current answer explained', 'body': 'Saved current understanding, with its limits.'}}
                return ChatResult(generations=[ChatGeneration(message=AIMessage(content='', tool_calls=[call]))])
        monkeypatch.setattr('sec_agent.agent_runtime.case_review_agent.case_chat_model',
            lambda *a, **k: WorkingPaperModel(responses=[AIMessage(content='unused')]))
    phase_calls = []
    if next_delivery == 'report':
        from langchain_core.outputs import ChatResult, ChatGeneration
        from langchain_core.runnables import RunnableConfig, RunnableLambda
        from sec_agent.agent_runtime.research_operation import bind_operation
        from test_on_demand_research import artifact_fixture
        monkeypatch.setattr('sec_agent.agent_runtime.organization_work_session.artifact_reader',
                            lambda *args: artifact_fixture())
        class ReportModel(Model):
            def _generate(self, messages, stop=None, run_manager=None, **kwargs):
                catalog = next((json.loads(m.content) if isinstance(m.content, str) else m.content for m in reversed(messages)
                                if getattr(m, 'name', '') == 'research_object_catalog'), None)
                produced = catalog and next((r for r in catalog if r['id'] == 'report'), None)
                if produced:
                    name, body = 'deliver_research_result', {'object_id': 'report', 'digest': produced['digest']}
                elif catalog and not phase_calls:
                    name, body = 'request_research_operation', {'request': {'action': 'compose',
                        'purpose': 'Explain the current evidence', 'basis': {r['id']: r['digest'] for r in catalog}}}
                else:
                    name, body = 'research_object_catalog', {}
                return ChatResult(generations=[ChatGeneration(message=AIMessage(content='', tool_calls=[
                    {'name': name, 'id': name+str(len(messages)), 'args': body}]))])
        monkeypatch.setattr('sec_agent.agent_runtime.case_review_agent.case_chat_model',
            lambda *a, **k: ReportModel(responses=[AIMessage(content='unused')]))
        # Keep the real phase selector and its configuration equality check;
        # replace only the expensive actor executor, not the parent handoff.
        def bound_phases(**kwargs):
            async def operate(state, config: RunnableConfig):
                selected = runtime.execution_from_config(config)
                assert selected == kwargs['execution']
                assert selected.delivery_intent == 'report'
                assert selected.model == s.body['execution'].get('model', 'default')
                phase_calls.append(selected)
                value = {'title': 'Qualification report', 'narrative_markdown': 'Synthetic engineering output', 'charts': []}
                bound = bind_operation(state['research_operation'], kwargs['artifact_reader'](state), state)
                return {'report': value, 'operation_result': {**bound, 'status': 'submitted', 'output': value}}
            return {'operate': RunnableLambda(operate)}
        monkeypatch.setattr(runtime, '_create_bound_research_phases', bound_phases)
    async def continue_work(injected=False):
        async with runtime.research_session_graph(config, SimpleNamespace(execution_runtime=True)) as graph:
            value = {**result, 'messages': [*result['messages'], HumanMessage(content=payload['message'])]}
            if injected: value['report'] = {'title': 'Forged saved artifact'}
            return await graph.ainvoke(value, config)
    continued = asyncio.run(continue_work())
    assert continued['task_outcome']['run_id'] == rid
    assert continued['task_outcome']['artifact_kind'] == next_delivery
    assert continued['task_outcome']['execution_status'] == 'submitted'
    assert len(continued['messages']) > len(result['messages'])
    if next_delivery == 'report':
        assert len(phase_calls) == 1
        assert continued['report']['title'] == 'Qualification report'
        assert config['configurable']['finsight_execution']['delivery_intent'] == 'answer'
    if next_delivery == 'workpaper':
        from sec_agent.agent_runtime.working_memory import WorkingMemory
        memory = WorkingMemory(env['FINSIGHT_WORKING_MEMORY_PATH'], owner='organization:' + grant['organization_id'],
                               workspace=tid, actor='research_partner')
        delivered = continued['delivery']
        saved_note = memory.read(delivered['artifact_id'], version=delivered['artifact_version'])
        assert saved_note['body'] == 'Saved current understanding, with its limits.'
    with pytest.raises(ExceptionGroup) as rejected:
        asyncio.run(continue_work(injected=True))
    def leaves(error):
        return [leaf for child in error.exceptions for leaf in leaves(child)] if isinstance(error, BaseExceptionGroup) else [error]
    assert any(isinstance(e, ValueError) and str(e) == 'organization_work_state_injection:report' for e in leaves(rejected.value))
