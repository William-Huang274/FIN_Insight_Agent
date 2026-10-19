"""A resumed author and data composition share one checkpoint, no paid model."""
from copy import deepcopy

import pytest

from sec_agent.agent_runtime.author_revision import author_continuation_options
from sec_agent.agent_runtime.specialist_graph import (
    SpecialistAgenticDependencies, SpecialistAgenticInput, build_specialist_agentic_state_graph,
)
from test_revision_scope_budget import revision_state
from test_specialist_graph import _ToolPorts


def options(state):
    return {'recovery_state': deepcopy(state), 'research_task': state['task'],
            'revision_feedback': [{'finding_id': 'old-new-revision-trigger'}],
            'run_invocation_id': 'do-not-reset-invocation', 'remaining_model_requests': lambda: 1}


def test_resume_initializes_normally_without_resetting_candidate_draft_or_limits():
    state = revision_state()
    state['workpaper_draft'] = {'saved_edits': ['already persisted draft must survive']}
    before = deepcopy(state)
    original_options = options(state)
    bound = author_continuation_options(original_options, state)
    assert bound['remaining_model_requests'] is original_options['remaining_model_requests']
    assert bound['revision_feedback'] is None
    assert original_options['revision_feedback'] and state == before
    ports = _ToolPorts()
    stream = build_specialist_agentic_state_graph(dependencies=SpecialistAgenticDependencies(
        model_turn=lambda _: pytest.fail('offline initialization only'),
        evidence_tool=ports.evidence, finance_tool=ports.finance),
        recovery_state=bound['recovery_state'], revision_feedback=bound['revision_feedback']).compile().stream(
            {k: state[k] for k in SpecialistAgenticInput.model_fields if k in state}, stream_mode='values')
    next(stream)
    restored = next(stream)
    stream.close()
    for key in ('workpaper_draft', 'last_submission_attempt', 'max_model_turns', 'max_tool_actions'):
        assert restored[key] == state[key]
    assert restored['notebook']['observations'] == state['notebook']['observations']
    assert restored['notebook']['model_turn_count'] == state['notebook']['model_turn_count']


@pytest.mark.parametrize('key,value', [('agent_id', 'another-author'), ('run_id', 'another-case'),
    ('pending_action', {'action': 'request_source'}), ('final_submission', {'accepted': True})])
def test_resume_rejects_cross_scope_and_unsettled_or_finished_states(key, value):
    state = revision_state()
    kwargs = options(state)
    state[key] = value
    with pytest.raises(ValueError, match='author_continuation_'):
        author_continuation_options(kwargs, state)


def test_explicit_remaining_allowance_aligns_ceiling_and_executes_without_resetting_history():
    from test_specialist_graph import _evidence_action
    from test_specialist_tool_batch import _batch
    state = revision_state()
    count = state['notebook']['model_turn_count']
    state['max_model_turns'] = count  # expired previous one-call authorization
    before = deepcopy(state)
    remaining, requests = [2], []
    kwargs = {**options(state), 'remaining_model_requests': lambda: remaining[0]}
    bound = author_continuation_options(kwargs, state, authorized_model_requests=2)
    assert bound['recovery_state']['max_model_turns'] == count + 2
    assert state == before
    for key in state.keys() - {'max_model_turns'}:
        assert bound['recovery_state'][key] == state[key]
    def turn(request):
        requests.append(request)
        remaining[0] -= 1
        return _batch(request, [_evidence_action()({})])
    ports = _ToolPorts()
    restored = bound['recovery_state']
    result = build_specialist_agentic_state_graph(dependencies=SpecialistAgenticDependencies(
        model_turn=turn, evidence_tool=ports.evidence, finance_tool=ports.finance,
        remaining_model_requests=kwargs['remaining_model_requests']), recovery_state=restored).compile().invoke(
            {k: restored[k] for k in SpecialistAgenticInput.model_fields if k in restored}, {'recursion_limit': 30})
    assert len(requests) == 2
    assert [r['execution_budget']['remaining_model_turns'] for r in requests] == [2, 1]
    assert result['notebook']['model_turn_count'] == count + 2
    assert result['run_invocation_id'] == state['run_invocation_id']
    assert result['notebook']['model_turn_records'][:count] == state['notebook']['model_turn_records']
    assert result['review_reason'] == 'shared_model_request_ceiling_reached_no_silent_completion'
    assert result['final_submission'] is None


@pytest.mark.parametrize('invalid', [-1, True, '2', 1.5])
def test_invalid_explicit_authorization_never_changes_recovered_state(invalid):
    state = revision_state()
    before = deepcopy(state)
    with pytest.raises(ValueError, match='authorized_budget_invalid'):
        author_continuation_options(options(state), state, authorized_model_requests=invalid)
    assert state == before


def test_explicit_authorization_cannot_exceed_shared_remainder_and_zero_stays_stopped():
    state = revision_state()
    with pytest.raises(ValueError, match='exceeds_shared_remaining'):
        author_continuation_options(options(state), state, authorized_model_requests=2)
    bound = author_continuation_options(options(state), state, authorized_model_requests=0)
    assert bound['recovery_state']['max_model_turns'] == state['notebook']['model_turn_count']
