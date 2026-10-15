"""Resumed local revisions keep sources and see the live shared allowance."""
from copy import deepcopy
import json

import pytest

from sec_agent.agent_runtime.specialist_graph import (
    SpecialistAgenticDependencies, SpecialistNotebook, _model_request,
    build_specialist_agentic_state_graph,
)
from sec_agent.agent_runtime.revision_guidance import AUTHOR_REVISION_GUIDANCE
from test_connected_revision_loop import submitted_original
from test_specialist_graph import _input, _ToolPorts, _evidence_action
from test_specialist_tool_batch import _batch


def revision_state():
    ports = _ToolPorts()
    graph = build_specialist_agentic_state_graph(
        dependencies=SpecialistAgenticDependencies(model_turn=lambda _: None,
            evidence_tool=ports.evidence, finance_tool=ports.finance),
        recovery_state=submitted_original(), revision_feedback=[{'finding_id': 'F1'}]).compile()
    stream = graph.stream(_input(), stream_mode='values')
    next(stream)
    state = next(stream)
    stream.close()
    return state


def test_resume_replaces_old_scope_without_changing_task_candidate_or_sources():
    state = revision_state()
    state['task_context']['revision_instruction'] = 'Keep the whole assignment in scope.'
    before = deepcopy(state)
    request = _model_request(state=state, notebook=SpecialistNotebook.model_validate_json(json.dumps(state['notebook'])),
        allow_workpaper_field_edits=True, remaining_model_requests=3)
    assert state == before
    assert request['task'] == state['task']
    assert request['notebook']['observations'] == state['notebook']['observations']
    assert request['submission_to_repair']['candidate'] == state['last_submission_attempt']['arguments']
    assert request['task_context']['revision_feedback'] == [{'finding_id': 'F1'}]
    assert request['task_context']['revision_instruction'] == AUTHOR_REVISION_GUIDANCE
    guidance = request['submission_to_repair']['revision_guidance']
    assert 'Keep the whole assignment' not in guidance
    assert 'Unchanged requested fields block submission' not in guidance
    assert 'does not itself block submission' in guidance


@pytest.mark.parametrize('remaining', [0, 1, 3, 100, None])
def test_effective_budget_is_minimum_not_new_author_quota(remaining):
    state = revision_state()
    node = state['max_model_turns'] - state['notebook']['model_turn_count']
    request = _model_request(state=state, notebook=SpecialistNotebook.model_validate_json(json.dumps(state['notebook'])),
        remaining_model_requests=remaining)
    budget = request['execution_budget']
    assert budget['remaining_model_turns'] == (node if remaining is None else min(node, remaining))
    if remaining is not None:
        assert budget['shared_remaining_model_requests'] == remaining
        assert budget['node_remaining_model_turns'] == node


def test_shared_allowance_refreshes_each_turn_and_zero_stops_before_model():
    ports = _ToolPorts()
    seen = []
    remaining = [2]
    def turn(request):
        seen.append(request['execution_budget'])
        remaining[0] -= 1
        return _batch(request, [_evidence_action()({})])
    result = build_specialist_agentic_state_graph(dependencies=SpecialistAgenticDependencies(
        model_turn=turn, evidence_tool=ports.evidence, finance_tool=ports.finance,
        remaining_model_requests=lambda: remaining[0])).compile().invoke(_input())
    assert [row['remaining_model_turns'] for row in seen] == [2, 1]
    assert result['review_reason'] == 'shared_model_request_ceiling_reached_no_silent_completion'
    assert result['final_submission'] is None
    assert result['notebook']['model_turn_count'] == 2


@pytest.mark.parametrize('invalid', [-1, True, '3'])
def test_invalid_shared_budget_does_not_call_model(invalid):
    ports = _ToolPorts()
    def unexpected(_):
        pytest.fail('model must not run')
    with pytest.raises(RuntimeError, match='shared_model_request_budget_invalid'):
        build_specialist_agentic_state_graph(dependencies=SpecialistAgenticDependencies(
            model_turn=unexpected, evidence_tool=ports.evidence, finance_tool=ports.finance,
            remaining_model_requests=lambda: invalid)).compile().invoke(_input())
