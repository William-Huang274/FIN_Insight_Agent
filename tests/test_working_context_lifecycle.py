"""Current state replacement and local repair on the native graph; no provider."""
from copy import deepcopy
import json

from sec_agent.agent_runtime.research_working_state import merge_research_subtasks
from sec_agent.agent_runtime.specialist_graph import SpecialistAgenticDependencies, build_specialist_agentic_state_graph
from test_research_working_state import working_note
from test_research_subtasks import task, update
from test_specialist_graph import _input, _ToolPorts, _evidence_action
from test_specialist_tool_batch import _batch, _handoff


def repair(req, args):
    return {'action': 'native_tool_batch', 'context_digest': req['context_digest'], 'tool_calls': [{
        'name': 'UpdateResearchStateAction', 'id': 'local-repair', 'type': 'tool_call', 'args': args}]}


def test_omitted_parent_is_preserved_but_explicit_null_is_validated():
    prior = {'subtasks': [{**task('parent'), 'status': 'split'}, task('child', parent_id='parent')]}
    original = deepcopy(prior)
    assert merge_research_subtasks(prior, [{'task_id': 'child', 'next_step': 'Read terms'}])[1]['parent_id'] == 'parent'
    import pytest
    with pytest.raises(ValueError, match='split task needs children'):
        merge_research_subtasks(prior, [{'task_id': 'child', 'parent_id': None}])
    assert prior == original


def test_rejected_draft_survives_reads_and_restart_then_local_repair():
    ports = _ToolPorts(); requests = []
    base = working_note(phase_status='working', findings=[], retain_source_ids=[], open_questions=[],
        rejected_interpretations=[f'Old judgment {i}' for i in range(17)])
    proposed = {**base, 'rejected_interpretations': [f'Revised judgment {i}' for i in range(29)],
        'subtasks': [{**task('parent'), 'status': 'in_progress'}, task('child', parent_id='parent')]}
    original = deepcopy(proposed)
    def turn(req):
        requests.append(req)
        if len(requests) == 1: return update(req, base)
        if len(requests) == 2: return update(req, proposed)
        if len(requests) == 3:
            receipt = json.loads(req['tool_results'][0]['content'])['working_state_update']
            assert receipt['pending_update_digest']
            assert req['task_context']['research_working_state']['subtasks'] == []
            return _batch(req, [_evidence_action()(req)])  # Error does not close research tools.
        return _handoff(req)
    deps = lambda fn: SpecialistAgenticDependencies(model_turn=fn, evidence_tool=ports.evidence,
        finance_tool=ports.finance, working_state_enabled=True)
    seed = {**_input(), 'max_model_turns': 10, 'max_tool_actions': 12}
    first = build_specialist_agentic_state_graph(dependencies=deps(turn)).compile().invoke(seed)
    assert len(ports.calls) == 1 and first['pending_working_state_update']['working_state'] == proposed
    saved = deepcopy(first); resumed = []
    def resume(req):
        resumed.append(req)
        if len(resumed) > 1: return _handoff(req)
        pending = req['task_context']['pending_working_state_update']
        return repair(req, {'action': 'update_research_state', 'context_digest': req['context_digest'],
            'reason_summary': 'Correct just the parent status; retain all proposed research.',
            'pending_update_digest': pending['digest'],
            'edits': [{'path': '/subtasks/0/status', 'value': 'split'}]})
    final = build_specialist_agentic_state_graph(dependencies=deps(resume), recovery_state=first).compile().invoke(
        {**seed, 'run_invocation_id': 'local-note-repair'})
    assert final['pending_working_state_update'] is None
    note = final['research_working_state']
    assert note['subtasks'][0]['status'] == 'split'
    assert note['rejected_interpretations'] == proposed['rejected_interpretations']
    assert final['notebook']['tool_action_count'] == first['notebook']['tool_action_count'] + 1
    assert final['notebook']['model_turn_count'] == first['notebook']['model_turn_count'] + 2
    assert first == saved and proposed == original and len(ports.calls) == 1


def test_schema_failure_can_be_fixed_without_resending_note():
    ports = _ToolPorts(); calls = []
    bad = working_note(phase_status='working', findings=[], retain_source_ids=[])
    bad['phase_status'] = 'typo'
    def turn(req):
        calls.append(req)
        if len(calls) == 1: return update(req, bad)
        if len(calls) == 2:
            pending = req['task_context']['pending_working_state_update']
            return repair(req, {'action': 'update_research_state', 'context_digest': req['context_digest'],
                'reason_summary': 'Repair the invalid enum.', 'pending_update_digest': pending['digest'],
                'edits': [{'path': '/phase_status', 'value': 'working'}]})
        return _handoff(req)
    result = build_specialist_agentic_state_graph(dependencies=SpecialistAgenticDependencies(model_turn=turn,
        evidence_tool=ports.evidence, finance_tool=ports.finance, working_state_enabled=True)).compile().invoke(_input())
    assert result['research_working_state']['phase_status'] == 'working'
    assert result['pending_working_state_update'] is None
    assert not ports.calls
