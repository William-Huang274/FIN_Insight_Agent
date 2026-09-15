"""Native delegation, original evidence handoff and Lead decisions without paid calls."""
from copy import deepcopy
import asyncio
import json

from sec_agent.agent_runtime.specialist_graph import SpecialistAgenticDependencies, build_specialist_agentic_state_graph
from sec_agent.agent_runtime.lead_issue_decision import LeadIssueDecision, decision_errors
from test_specialist_graph import _input, _ToolPorts
from test_workpaper_review_graph import _seed
from test_research_convergence import exercise_case


def test_domain_helper_has_separate_input_and_source_read_preserves_original_observation():
    child = _seed()
    child['private_history'] = 'PRIVATE_HELPER_HISTORY'
    inputs, model_inputs = [], []
    spec = {'subtask_id': 'numbers', 'objective': 'Check only the reported metric and its original period, not the entire domain thesis.',
        'success_criteria': ['Preserve the original period and source identity.'],
        'relieved_work': 'Parent will not repeat the initial metric extraction and calculation.',
        'retained_parent_work': 'Parent integrates this metric with demand counterevidence and the overall thesis.', 'source_hints': []}
    def helper(task, state, config):
        inputs.append(task)
        return deepcopy(child)
    def model(request):
        model_inputs.append(request)
        assert 'PRIVATE_HELPER_HISTORY' not in json.dumps(request)
        n = len(model_inputs)
        if n == 1:
            name, args = 'DelegateSubtasksAction', {'action': 'delegate_subtasks', 'tasks': [spec]}
        elif n == 2:
            name, args = 'ReadDelegatedWorkAction', {'action': 'read_delegated_work', 'subtask_id': 'numbers', 'section': 'workpaper'}
        elif n == 3:
            body = json.loads(request['tool_results'][0]['content'])
            assert body['workpaper'] == child['final_submission']
            name, args = 'ReadDelegatedWorkAction', {'action': 'read_delegated_work', 'subtask_id': 'numbers', 'section': 'source',
                'source_observation_ref': body['sources'][0]['source_observation_ref']}
        else:
            assert request['notebook']['observations'][0] == child['notebook']['observations'][0]
            return {'action': 'request_human_review', 'context_digest': request['context_digest'],
                'reason_summary': 'Synthetic evidence handoff checked, no financial approval.', 'blocker_code': 'fixture_done'}
        return {'action': 'native_tool_batch', 'context_digest': request['context_digest'], 'tool_calls': [{
            'id': f'call-{n}', 'name': name, 'args': {**args, 'context_digest': request['context_digest'],
                'reason_summary': 'Perform only the bounded task or read the exact saved artifact.'}}]}
    ports = _ToolPorts()
    graph = build_specialist_agentic_state_graph(dependencies=SpecialistAgenticDependencies(
        model_turn=model, evidence_tool=ports.evidence, finance_tool=ports.finance, subtask_runner=helper)).compile()
    result = graph.invoke(_input(), {'recursion_limit': 25})
    assert len(inputs) == 1 and not ports.calls
    assert result['delegated_work']['numbers']['result']['private_history'] == 'PRIVATE_HELPER_HISTORY'
    assert result['notebook']['model_turn_count'] == 4


def test_integrated_route_now_includes_lead_decision_and_final_judgment_when_enabled():
    result, sequence, contexts = asyncio.run(exercise_case(depth='integrated', hierarchical=True))
    roles = [r[0] for r in sequence]
    assert roles == ['lead_decision', 'synthesis', 'research_verifier', 'writer', 'report_verifier']
    assert result['phase'] == 'case_report_ready_for_human_review'
    assert result['lead_decision']['action'] == 'synthesize'


def test_material_finding_reaches_lead_before_targeted_repair():
    result, sequence, _ = asyncio.run(exercise_case(depth='integrated', hierarchical=True, research_owner='research'))
    roles = [r[0] for r in sequence]
    assert roles.index('lead_decision', 1) < roles.index('repair') < roles.index('writer')
    assert [r[1] for r in sequence if r[0] == 'repair'] == ['P02']
    assert result['lead_decision']['dispositions'][0]['disposition'] == 'repair'


def test_lead_cannot_silently_drop_finding_or_disagree_without_sources():
    feedback = {'P01': [{'finding_id': 'F1'}]}
    decision = LeadIssueDecision(summary='The fixture has a material question that must remain visible.', action='synthesize')
    assert decision_errors(decision, feedback, {'P01'})
    decision = LeadIssueDecision(summary='The fixture has a material question that must remain visible.', action='synthesize',
        dispositions=[{'paper_id': 'P01', 'finding_id': 'F1', 'disposition': 'disagree_with_sources',
            'rationale': 'The supplied interpretation should be independently checked against the original source.',
            'expected_progress': 'Review the exact original source.'}])
    assert decision_errors(decision, feedback, {'P01'})


def test_lead_discovers_issue_before_synthesis_without_reviewer_finding():
    result, sequence, _ = asyncio.run(exercise_case(hierarchical=True, discovered_issue=True))
    assert [r[0] for r in sequence][:3] == ['lead_decision', 'repair', 'synthesis']
    assert result['revisions']['P02']['finding_responses'][0]['finding_id'] == 'lead_new_scope'


def test_claimed_repair_with_unchanged_paper_stops_before_more_paid_roles():
    result, sequence, _ = asyncio.run(exercise_case(hierarchical=True, research_owner='research', unchanged_repair=True))
    assert result['stop_reason'] == 'author_claimed_correction_without_research_change'
    assert [r[0] for r in sequence][-1] == 'repair'
