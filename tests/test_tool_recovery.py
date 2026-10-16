from copy import deepcopy
import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from sec_agent.agent_runtime.research_graph_contracts import canonical_sha256
from sec_agent.agent_runtime.tool_recovery import recheck_failed_calculation
from sec_agent.agent_runtime.research_context_view import working_view, public_operation
from sec_agent.agent_runtime.specialist_graph import SpecialistAgenticDependencies, build_specialist_agentic_state_graph
from sec_agent.research_foundation.source_bound_calculator import ObservedSourceRegistry
from test_specialist_graph import _input, _ToolPorts


def failed_state():
    request = {'expression': 'a / b', 'operands': {
        'a': {'source_id': 'PASSAGE::sample', 'literal': '15', 'quote': '15 to 25 years'},
        'b': {'source_id': 'PASSAGE::sample', 'literal': '25', 'quote': '15 to 25 years'}},
        'result_unit': 'ratio', 'rationale': 'A fixture arithmetic ratio, not financial validation.'}
    def model(r):
        return {'action': 'native_tool_batch', 'context_digest': r['context_digest'], 'tool_calls': [{
            'id': 'failed-calc', 'name': 'RequestCalculationAction', 'type': 'tool_call', 'args': {
                'action': 'request_calculation', 'request': request, 'context_digest': r['context_digest'],
                'reason_summary': 'Fixture source-bound calculation.'}}]}
    def finance(_):
        raise ValueError('source_id_not_observed_in_this_tool_session')
    ports = _ToolPorts()
    graph = build_specialist_agentic_state_graph(dependencies=SpecialistAgenticDependencies(
        model_turn=model, evidence_tool=ports.evidence, finance_tool=finance))
    events = graph.compile().stream(_input(), stream_mode='values')
    for state in events:
        if state.get('tool_results'):
            break
    events.close()
    state = deepcopy(state)
    # The MCP transport exposes this typed source-registration error. The
    # generic exception test port deliberately redacts exception text.
    error = json.loads(state['tool_results'][0]['content'])
    error['calculator_error'] = 'source_id_not_observed_in_this_tool_session'
    state['tool_results'][0]['content'] = json.dumps(error)
    passage = {'passage_id': 'PASSAGE::sample', 'passage': '15 to 25 years',
        'result_state': 'source_bound_passage', 'writer_citable': True, 'numeric_fact_authority': False}
    obs = ports._observation({'action_attempt_id': 'prior-source-read', 'request_digest': 'a'*64},
        kind='evidence', references=[], content=[passage])
    state['notebook']['observations'].append(obs)
    rehash(state)
    return state


def rehash(state):
    state['notebook']['notebook_digest'] = canonical_sha256({k: v for k, v in state['notebook'].items() if k != 'notebook_digest'})


def test_exact_local_execution_preserves_history_budget_and_idempotent_result():
    state = failed_state(); original = deepcopy(state)
    restored = recheck_failed_calculation(state, 'failed-calc')
    assert state == original
    check = restored['task_context']['tool_recovery_checks'][-1]
    assert check['outcome']['status'] == 'success'
    result = check['outcome']['result']
    assert result['value_decimal'] == '0.6'
    assert not result['financial_semantics_verified']
    assert ObservedSourceRegistry(restored['notebook']['observations']).get(result['calculation_id']) == result
    assert restored['tool_results'] == original['tool_results']
    assert restored['notebook']['observations'][:-1] == original['notebook']['observations']
    for key in ('model_turn_records', 'model_turn_count', 'tool_action_count', 'dispatched_action_digests'):
        assert restored['notebook'][key] == original['notebook'][key]
    assert restored['max_model_turns'] == original['max_model_turns']
    assert recheck_failed_calculation(restored, 'failed-calc') == restored


def test_missing_source_records_new_failure_never_false_recovery():
    state = failed_state()
    state['notebook']['observations'].pop(); rehash(state)
    restored = recheck_failed_calculation(state, 'failed-calc')
    assert restored['task_context']['tool_recovery_checks'][-1]['outcome']['status'] == 'failure'
    assert restored['notebook'] == state['notebook']


@pytest.mark.parametrize('mutation', ['owner', 'pending', 'call', 'error'])
def test_rejects_wrong_owner_inflight_unrelated_call_or_failure(mutation):
    state = failed_state()
    call = 'failed-calc'
    if mutation == 'owner': state['agent_id'] = 'other'
    if mutation == 'pending': state['pending_action'] = {'action': 'request_calculation'}
    if mutation == 'call': call = 'not-current'
    if mutation == 'error': state['tool_results'][0]['content'] = 'unrelated failure'
    with pytest.raises(ValueError): recheck_failed_calculation(state, call)


def test_model_view_distinguishes_old_error_and_new_execution_without_fake_tool_turn():
    state = failed_state(); restored = recheck_failed_calculation(state, 'failed-calc')
    call = state['notebook']['model_turn_records'][-1]['action']['tool_calls'][0]
    context = {'allowed_actions': ['read_research_history'], 'task_context': restored['task_context']}
    rows = [SystemMessage(content='Fixture'), HumanMessage(content=json.dumps(context)), AIMessage(content='', tool_calls=[call]),
        ToolMessage(name='RequestCalculationAction', tool_call_id='failed-calc', status='error',
                    content=json.dumps({'result': json.loads(state['tool_results'][0]['content']), 'current_context': context}))]
    before = deepcopy(rows)
    view = working_view(rows)
    reply = next(m for m in view if isinstance(m, ToolMessage))
    body = json.loads(reply.content)['result']
    assert reply.status == 'error' and body['current_execution_check']['status'] == 'success'
    assert body['historical_failure'] == json.loads(state['tool_results'][0]['content'])
    assert rows == before and working_view(view) == view
    assert len([m for m in view if isinstance(m, AIMessage)]) == 1
    operation = public_operation(rows, 'runtime:context:/task_context/tool_recovery_checks/0')
    assert '0.6' in json.dumps(operation)


def test_real_semantic_projection_preserves_exact_call_binding_and_is_repeatable():
    from sec_agent.agent_runtime.deepseek_structured_agents import _agentic_semantic_value
    state = failed_state(); restored = recheck_failed_calculation(state, 'failed-calc')
    check = restored['task_context']['tool_recovery_checks'][0]
    projected = _agentic_semantic_value(check)
    assert projected['binding']['request_fingerprint'] == check['binding']['request_digest']
    assert projected['outcome']['status'] == 'success'
    assert _agentic_semantic_value(projected) == projected


def test_changed_source_is_rechecked_and_failure_does_not_reuse_previous_success():
    state = recheck_failed_calculation(failed_state(), 'failed-calc')
    # Remove the old source observation, preserving its successful calculation
    # and historic failure. A different source snapshot cannot reuse the check.
    state['notebook']['observations'] = [o for o in state['notebook']['observations']
        if o['action_attempt_id'] != 'prior-source-read']
    rehash(state)
    restored = recheck_failed_calculation(state, 'failed-calc')
    checks = restored['task_context']['tool_recovery_checks']
    assert [c['outcome']['status'] for c in checks] == ['success', 'failure']
    assert checks[0]['check_id'] != checks[1]['check_id']
    assert restored['notebook'] == state['notebook']


def test_normal_initializer_keeps_recovery_result_without_model_call():
    from sec_agent.agent_runtime.author_revision import author_continuation_options
    state = recheck_failed_calculation(failed_state(), 'failed-calc')
    options = author_continuation_options({'recovery_state': state, 'research_task': state['task']}, state)
    ports = _ToolPorts()
    graph = build_specialist_agentic_state_graph(dependencies=SpecialistAgenticDependencies(
        model_turn=lambda _: pytest.fail('offline initialization must not invoke model'),
        evidence_tool=ports.evidence, finance_tool=ports.finance), recovery_state=options['recovery_state'])
    events = graph.compile().stream(_input(), stream_mode='values')
    next(events); initialized = next(events); events.close()
    assert initialized['task_context']['tool_recovery_checks'] == state['task_context']['tool_recovery_checks']
    assert initialized['notebook']['observations'] == state['notebook']['observations']
    assert initialized['tool_results'] == state['tool_results']
    assert not ports.calls
