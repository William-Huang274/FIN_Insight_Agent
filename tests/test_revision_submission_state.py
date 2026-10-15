from copy import deepcopy
import json

import pytest
from langchain_core.messages import ToolMessage

from sec_agent.agent_runtime.revision_submission_state import revision_attempt_view, restore_accepted_receipt
from sec_agent.agent_runtime.research_graph_contracts import canonical_sha256


def fixture():
    submission = {'action': 'submit_workpaper', 'context_digest': 'context', 'thesis': 'Original finding'}
    return {'agent_id': 'author', 'task_context': {'accepted_revision_baseline': {
        'submission': submission, 'submission_digest': canonical_sha256(submission), 'through_model_turn': 5}},
        'last_submission_attempt': {'arguments': deepcopy(submission), 'accepted': False, 'feedback': []},
        'notebook': {'model_turn_records': [{'turn_index': 5, 'context_digest': 'context',
            'action': submission, 'runtime_receipt': {'actor': 'author', 'request_digest': 'request'}}]}}


def test_unsubmitted_legacy_revision_is_not_failed_and_input_is_immutable():
    state = fixture(); before = deepcopy(state)
    view = revision_attempt_view(state)
    assert view['accepted'] is None and view['submission_status'] == 'not_submitted'
    assert view['arguments'] == before['last_submission_attempt']['arguments']
    assert state == before


@pytest.mark.parametrize('kind', ['direct', 'batch', 'feedback', 'tool_id', 'bad_baseline'])
def test_real_rejections_and_unverified_baselines_are_not_promoted(kind):
    state = fixture(); state['last_submission_attempt']['submission_status'] = 'not_submitted'
    if kind in ('direct', 'batch'):
        action = {'action': 'submit_workpaper'} if kind == 'direct' else {
            'action': 'native_tool_batch', 'tool_calls': [{'name': 'ReviseWorkpaperAction'}]}
        state['notebook']['model_turn_records'].append({'turn_index': 6, 'action': action})
    elif kind == 'feedback': state['last_submission_attempt']['feedback'] = [{'code': 'actual_error'}]
    elif kind == 'tool_id': state['last_submission_attempt']['tool_call_id'] = 'new-submit'
    else: state['task_context']['accepted_revision_baseline']['submission_digest'] = 'wrong'
    result = revision_attempt_view(state)
    assert result['accepted'] is False and 'submission_status' not in result


@pytest.mark.parametrize('kind', ['matched', 'other_call', 'real_failure', 'other_actor', 'bad_baseline'])
def test_only_audit_bound_empty_false_receipt_is_restored(tmp_path, kind):
    state = fixture()
    if kind == 'bad_baseline': state['task_context']['accepted_revision_baseline']['submission_digest'] = 'wrong'
    payload = {'result': {'accepted': False, 'feedback': [], 'validation_issues': []}, 'current_context': {'preserve': True}}
    if kind == 'real_failure': payload['result']['feedback'] = [{'code': 'quote_error'}]
    message = ToolMessage(content=json.dumps(payload), tool_call_id='accepted-call', name='SubmitWorkpaperAction', status='error')
    path = tmp_path/'audit.jsonl'
    event = {'actor': 'other' if kind == 'other_actor' else 'author', 'request_digest': 'request',
             'raw_response': {'tool_calls': [{'id': 'other-call' if kind == 'other_call' else 'accepted-call', 'name': 'SubmitWorkpaperAction'}]}}
    path.write_text(json.dumps(event)+'\n', encoding='utf8'); original_bytes = path.read_bytes()
    result = restore_accepted_receipt([message], state, [path])
    assert json.loads(message.content)['result']['accepted'] is False
    assert path.read_bytes() == original_bytes
    assert json.loads(result[0].content)['current_context'] == {'preserve': True}
    assert json.loads(result[0].content)['result']['accepted'] is (kind == 'matched')


def test_initialized_native_revision_retains_accepted_terminal_and_unsubmitted_candidate():
    from test_connected_revision_loop import submitted_original
    from test_specialist_graph import _input, _ToolPorts
    from sec_agent.agent_runtime.specialist_graph import (
        SpecialistAgenticDependencies, build_specialist_agentic_state_graph, SpecialistNotebook, _model_request)
    original = submitted_original()
    ports = _ToolPorts()
    graph = build_specialist_agentic_state_graph(dependencies=SpecialistAgenticDependencies(
        model_turn=lambda _: pytest.fail('no model'), evidence_tool=ports.evidence, finance_tool=ports.finance),
        recovery_state=original, revision_feedback=[{'finding_id': 'F1'}]).compile()
    events = graph.stream(_input(), stream_mode='values'); next(events); state = next(events); events.close()
    assert state['last_submission_attempt']['accepted'] is None
    request = _model_request(state=state, notebook=SpecialistNotebook.model_validate_json(json.dumps(state['notebook'])))
    assert request['revision_submission_status']['status'] == 'not_submitted'
    from sec_agent.agent_runtime.deepseek_structured_agents import _project_agentic_specialist_request
    assert _project_agentic_specialist_request(request)['revision_submission_status'] == request['revision_submission_status']
    assert request.get('terminal_result', {}).get('accepted') is not False
    assert request['task_context']['accepted_revision_baseline']['submission'] == original['final_submission']
