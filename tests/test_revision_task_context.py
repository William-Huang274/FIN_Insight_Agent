"""Revision task handoff, not a model-quality or financial-accuracy test."""
from copy import deepcopy
import json

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from sec_agent.agent_runtime.author_revision import revision_material_handoff
from sec_agent.agent_runtime.research_context_view import (
    compact_current_context, public_operation, working_view,
)
from test_context_retirement import batch


def context():
    candidate = {'thesis': 'Current answer', 'open_gaps': ['Optional reconciliation still open'],
                 'task_note': {'coverage': [{'criterion': 'OLD CRITERION', 'status': 'not_completed'}]}}
    return {
        'allowed_actions': ['read_research_history', 'request_source', 'request_calculation', 'revise_workpaper'],
        'branch': {'objective': 'OLD FULL RESEARCH PLAN', 'tool_binding_id': 'B', 'research_as_of': '2026-09-24'},
        'execution_budget': {'remaining_model_turns': 1},
        'task_context': {
            'research_question': 'Original user question',
            'assignment': {'objective': 'OLD FULL RESEARCH PLAN', 'success_criteria': ['OLD CRITERION'],
                           'task_id': 'T1', 'requested_capability_refs': ['sources']},
            'task_scope': 'Old objective defines current work',
            'overall_assignment': 'OLD FULL RESEARCH PLAN',
            'authoring_context': {'brief': {'argument_plan': ['OLD OUTLINE']}, 'basis': {'task': 'original'}},
            'authoring_instruction': 'Evaluate all preparation changes',
            'changes_since_preparation': ['observations_digest'],
            'accepted_revision_baseline': {'through_model_turn': 2, 'submission': deepcopy(candidate)},
            'revision_feedback': [{'finding_id': 'F1', 'claim_ids': ['C1'], 'source_checks': ['original']}],
            'revision_instruction': 'Repair active findings and affected conclusions.',
        },
        'submission_to_repair': {'candidate': candidate, 'validation_feedback': {'issues': ['CURRENT ERROR']},
                                 'edit_progress': ['CURRENT EDIT'], 'base_submission_digest': 'a' * 64},
    }


def fixture():
    c = context()
    rows = [SystemMessage(content='Author identity'), HumanMessage(content=json.dumps(c))]
    reads = [batch(f'read-{i}', 'RequestSourceAction', {'reason_summary': 'OLD RESTORE EVERYTHING PURPOSE'},
                   {'passage_id': f'P{i}', 'passage': f'Original {i}: period, unit, conditions intact.'})
             for i in range(7)]
    rows.append(AIMessage(content='', tool_calls=[pair[0].tool_calls[0] for pair in reads]))
    rows.extend(pair[1] for pair in reads)
    rows = revision_material_handoff(rows, c)
    rows.append(SystemMessage(content='Context size reminder',
                              additional_kwargs={'fin_context_checkpoint_instruction': True}))
    return rows


def view(rows):
    return json.loads(next(m.content for m in working_view(rows)
                          if m.additional_kwargs.get('fin_research_working_view')))


def test_revision_view_has_one_live_task_and_exact_background_readbacks():
    rows = fixture(); saved = deepcopy(rows); v = view(rows); c = v['current_context']; t = c['task_context']
    assert rows == saved
    repair = c['submission_to_repair']
    assert repair['validation_feedback'] == context()['submission_to_repair']['validation_feedback']
    record = public_operation(rows, repair['candidate_readback']['arguments']['tool_call_id'])
    assert record['receipt']['result'] == context()['submission_to_repair']['candidate']
    assert c['allowed_actions'] == context()['allowed_actions']
    assert 'execution_budget' not in c
    assert c['execution_window']['current_request_authorized'] is True
    record = public_operation(rows, c['execution_window']['budget_readback']['arguments']['tool_call_id'])
    assert record['receipt']['result'] == context()['execution_budget']
    assert t['research_question'] == 'Original user question'
    assert t['revision_feedback'] == context()['task_context']['revision_feedback']
    assert 'objective' not in c['branch'] and c['branch']['tool_binding_id'] == 'B'
    assert 'success_criteria' not in t['assignment'] and t['assignment']['requested_capability_refs'] == ['sources']
    assert 'authoring_context' not in t and 'authoring_instruction' not in t and 'task_scope' not in t
    assert 'OLD OUTLINE' not in json.dumps(v) and 'OLD FULL RESEARCH PLAN' not in json.dumps(v)
    assert 'OLD RESTORE EVERYTHING PURPOSE' not in json.dumps(v)
    assert t['revision_task']['completion_basis'] == ['active_findings', 'current_validation_errors', 'necessary_consequences']
    assert t['revision_task']['optional_updates'] == 'not_required_for_this_revision'
    assert len(v['current_materials']) == 7
    for read in t['research_background']['reads'].values():
        record = public_operation(rows, read['arguments']['tool_call_id'])
        assert record and record['receipt']['status'] == 'success'
    restored = public_operation(rows, t['research_background']['reads']['authoring_context']['arguments']['tool_call_id'])
    assert restored['receipt']['result'] == context()['task_context']['authoring_context']
    for i in range(7):
        cat = next(r for r in v['operation_catalog'] if r['tool_call_id'] == f'read-{i}')
        assert cat['source_ids'] == [f'P{i}'] and 'purpose' not in cat
        original = public_operation(rows, cat['tool_call_id'])
        assert original['operation']['args']['reason_summary'] == 'OLD RESTORE EVERYTHING PURPOSE'
        assert original['receipt']['result'] == v['current_materials'][i]
    assert working_view(working_view(rows)) == working_view(rows)


def test_current_error_pending_edits_and_later_material_lifecycle_remain_live():
    rows = fixture()
    rows.extend(batch('edit', 'ReviseWorkpaperAction', {'reason_summary': 'CURRENT REVISION ATTEMPT'},
                      {'accepted': False, 'issues': ['new error']}, status='error'))
    projected = working_view(rows)
    research_messages = [m for m in projected if not m.additional_kwargs.get('fin_context_checkpoint_instruction')]
    assert research_messages[-2:] == rows[-2:]
    assert view(rows)['current_context']['submission_to_repair']['edit_progress'] == ['CURRENT EDIT']
    # Reading alone does not retire materials needed for the pending revision.
    later = [*fixture(), *batch('new', 'RequestSourceAction', {}, {'passage_id': 'P8', 'passage': 'Next original'})]
    later.extend(batch('consumed', 'UpdateResearchStateAction', {}, {'accepted': True}))
    assert view(later)['material_focus'] == 'revision_working_set'
    assert len(view(later)['current_materials']) == 8


def test_first_draft_keeps_original_plan_and_preparation():
    c = context(); del c['task_context']['accepted_revision_baseline']
    saved = deepcopy(c); out = compact_current_context(c)
    assert c == saved
    assert out['branch']['objective'] == 'OLD FULL RESEARCH PLAN'
    assert out['task_context']['authoring_context'] == c['task_context']['authoring_context']
    assert 'revision_task' not in out['task_context']


def test_native_revision_accepts_related_edits_with_unrelated_gaps_still_open():
    from sec_agent.agent_runtime.specialist_graph import SpecialistAgenticDependencies, build_specialist_agentic_state_graph
    from sec_agent.agent_runtime.workpaper_review_graph import validate_workpaper_state
    from test_connected_revision_loop import submitted_original
    from test_specialist_graph import _input, _ToolPorts
    from test_specialist_tool_batch import _batch
    from test_workpaper_partial_edits import edit_action, text_edit

    original = submitted_original(authoring=True)
    saved = validate_workpaper_state(original)
    # This is a deterministic author response; no provider or financial claim.
    def turn(request):
        candidate = request['submission_to_repair']['candidate']
        answers = [{'finding_id': 'F1', 'disposition': 'corrected', 'explanation': 'Corrected fixture and related prose.'}]
        return _batch(request, [edit_action(candidate, [
            text_edit(),
            {'op': 'str_replace', 'path': '/thesis', 'old_string': candidate['thesis'],
             'new_string': candidate['thesis'] + ' Related fixture clarification.'},
            {'op': 'replace', 'path': '/open_gaps', 'old_value': candidate['open_gaps'],
             'new_value': ['Unrelated optional investigation remains open.']},
            {'op': 'upsert_coverage', 'assessment': {'criterion': 'Optional broader investigation',
             'status': 'not_completed', 'explanation': 'Not needed for the current fixture correction.'}},
            {'path': '/task_note/finding_responses', 'old_value': [], 'new_value': answers},
        ]).model_dump(mode='json')])
    result = build_specialist_agentic_state_graph(dependencies=SpecialistAgenticDependencies(
        model_turn=turn, evidence_tool=_ToolPorts().evidence, finance_tool=_ToolPorts().finance,
        allow_workpaper_field_edits=True, authoring_enabled=True), recovery_state=saved,
        revision_feedback=[{'finding_id': 'F1'}]).compile().invoke(_input())
    assert result['phase'] == 'specialist_submission_accepted'
    paper = result['final_submission']
    assert paper['thesis'].endswith('Related fixture clarification.')
    assert paper['open_gaps'] == ['Unrelated optional investigation remains open.']
    assert paper['task_note']['coverage'][-1]['status'] == 'not_completed'
    assert paper['claims'] == original['final_submission']['claims']
    assert result['notebook']['observations'] == original['notebook']['observations']
