"""One saved change and an independent read can execute without a second model turn."""
from copy import deepcopy
import pytest

from sec_agent.agent_runtime.specialist_graph import (
    SpecialistAgenticDependencies, SpecialistAgenticInput, build_specialist_agentic_state_graph,
)
from test_revision_scope_budget import revision_state
from test_specialist_graph import _ToolPorts, _finance_action
from test_specialist_tool_batch import _batch


@pytest.mark.parametrize('bad_save,read_failure', [(False, False), (False, True), (True, False)])
@pytest.mark.parametrize('save_first', [True, False])
def test_independent_results_persist_and_shared_budget_stops_without_finalization(bad_save, read_failure, save_first):
    s = revision_state(); before = deepcopy(s); seen = []; ports = _ToolPorts(); reads = []
    def finance(payload):
        reads.append(payload)
        if read_failure: raise RuntimeError('fixture source failure')
        return ports.finance(payload)
    def turn(r):
        seen.append(r)
        save = {'action': 'save_workpaper_edits', 'operation_id': 'fixture-save',
            'reason_summary': 'Independent saved field.', 'base_submission_digest': r['submission_to_repair']['base_submission_digest'],
            'edits': [{'op': 'set_field', 'path': '/missing' if bad_save else '/thesis', 'value': 'Persisted fixture thesis.'}]}
        read = _finance_action()({})
        read['intent']['period_end'] = '2026-04-30'
        return _batch(r, [save, read] if save_first else [read, save])
    deps = SpecialistAgenticDependencies(model_turn=turn, evidence_tool=ports.evidence, finance_tool=finance,
        allow_workpaper_field_edits=True, remaining_model_requests=lambda: 1-len(seen))
    result = build_specialist_agentic_state_graph(dependencies=deps, recovery_state=s).compile().invoke(
        {k:s[k] for k in SpecialistAgenticInput.model_fields if k in s}, {'recursion_limit': 30})
    assert len(seen) == len(reads) == 1 and s == before
    assert result['last_submission_attempt'] == before['last_submission_attempt']
    assert not result.get('final_submission')
    if bad_save:
        assert not result.get('workpaper_draft') and result['pending_workpaper_revision']
    else:
        assert result['workpaper_draft']['saved_batches'] == 1
        assert result['workpaper_draft']['arguments']['thesis'] == 'Persisted fixture thesis.'
    assert result['review_reason'] == 'shared_model_request_ceiling_reached_no_silent_completion'
    assert result['notebook']['model_turn_count'] == s['notebook']['model_turn_count'] + 1


@pytest.mark.parametrize('second', ['save', 'finalize'])
def test_multiple_writes_or_save_and_finalize_are_not_executed(second):
    s = revision_state(); ports = _ToolPorts(); seen = []
    def turn(r):
        seen.append(r)
        save = {'action':'save_workpaper_edits', 'operation_id':'first', 'reason_summary':'Fixture.',
            'base_submission_digest':r['submission_to_repair']['base_submission_digest'],
            'edits':[{'op':'set_field','path':'/thesis','value':'Must not be applied.'}]}
        other = {**save, 'operation_id':'second'} if second=='save' else {
            'action':'finalize_workpaper_revision', 'reason_summary':'Fixture.', 'draft_digest':save['base_submission_digest']}
        return _batch(r,[save,other])
    result=build_specialist_agentic_state_graph(dependencies=SpecialistAgenticDependencies(model_turn=turn,
        evidence_tool=ports.evidence, finance_tool=ports.finance, allow_workpaper_field_edits=True,
        remaining_model_requests=lambda:1-len(seen)),recovery_state=s).compile().invoke(
        {k:s[k] for k in SpecialistAgenticInput.model_fields if k in s})
    assert len(seen)==1 and not result.get('workpaper_draft') and not result.get('final_submission')
    assert result['notebook']['tool_action_count']==s['notebook']['tool_action_count']
