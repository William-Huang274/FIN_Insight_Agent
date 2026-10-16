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
