"""Saved path corrections remain drafts until explicitly finalized."""
from copy import deepcopy

import pytest

from sec_agent.agent_runtime.specialist_graph import (
    WorkpaperEditError, apply_workpaper_edits, SpecialistAgenticDependencies,
    build_specialist_agentic_state_graph,
)
from sec_agent.agent_runtime.deepseek_structured_agents import _NATIVE_SPECIALIST_SYSTEM_PROMPT
from test_workpaper_partial_edits import paper, edit_action, text_edit
from test_connected_revision_loop import submitted_original
from test_specialist_graph import _input, _ToolPorts
from test_specialist_tool_batch import _batch


@pytest.mark.parametrize('field,value', [('changes', 'Existing note'), ('finding_responses', [])])
def test_misplaced_nested_field_reports_exact_path_without_mutating(field, value):
    original = paper()
    original['task_note'][field] = value
    snapshot = deepcopy(original)
    with pytest.raises(WorkpaperEditError) as caught:
        apply_workpaper_edits(original, edit_action(original, [
            {'path': '/' + field, 'old_value': value, 'new_value': value}]))
    assert caught.value.issues[0]['suggested_path'] == '/task_note/' + field
    assert original == snapshot


def test_saved_batch_path_feedback_then_explicit_finalize():
    from sec_agent.agent_runtime.specialist_graph import save_workpaper_revision
    original = submitted_original()
    # Initialize a real review revision before freezing its failed edit batch.
    builder = build_specialist_agentic_state_graph(dependencies=SpecialistAgenticDependencies(
        model_turn=lambda _: pytest.fail('initialize only'), evidence_tool=_ToolPorts().evidence,
        finance_tool=_ToolPorts().finance, allow_workpaper_field_edits=True),
        recovery_state=original, revision_feedback=[{'finding_id': 'F1', 'diagnosis': 'Check fixture.'}])
    stream = builder.compile().stream(_input(), stream_mode='values')
    next(stream); state = next(stream); stream.close()
    candidate = state['last_submission_attempt']['arguments']
    answer = [{'finding_id': 'F1', 'disposition': 'corrected', 'explanation': 'Corrected fixture fragment.'}]
    wrong = {'path': '/finding_responses', 'old_value': [], 'new_value': answer}
    state['pending_workpaper_revision'] = save_workpaper_revision(edit_action(candidate, [text_edit(), wrong]))
    seen = []
    def turn(request):
        seen.append(request)
        repair = request['submission_to_repair']
        if len(seen) == 2:
            assert request['revision_submission_status']['accepted'] is False
            return _batch(request, [{'action': 'finalize_workpaper_revision', 'reason_summary': 'Submit saved version.',
                'draft_digest': repair['base_submission_digest']}])
        assert repair['candidate'] == candidate
        check = repair['pending_edit_validation']
        assert check['issues'][0]['suggested_path'] == '/task_note/finding_responses'
        assert 'FinalizeWorkpaperRevisionAction submits the saved draft_digest' in repair['submission_contract']['local_revision']
        return _batch(request, [{'action': 'save_workpaper_edits', 'operation_id': 'repair-path', 'reason_summary': 'Repair only saved path.',
            'base_submission_digest': repair['base_submission_digest'],
            'pending_revision_digest': check['pending_revision_digest'],
            'edit_corrections': [{'edit_index': 1, 'edit': {**wrong, 'path': '/task_note/finding_responses'}}]}])
    graph = build_specialist_agentic_state_graph(dependencies=SpecialistAgenticDependencies(
        model_turn=turn, evidence_tool=_ToolPorts().evidence, finance_tool=_ToolPorts().finance,
        allow_workpaper_field_edits=True), recovery_state=state).compile()
    result = graph.invoke(_input(), {'recursion_limit': 30})
    assert len(seen) == 2
    assert result['phase'] == 'specialist_submission_accepted'
    assert result['final_submission']['claims'] == original['final_submission']['claims']
    assert result['final_submission']['task_note']['finding_responses'] == answer
    assert 'FinalizeWorkpaperRevisionAction' in _NATIVE_SPECIALIST_SYSTEM_PROMPT
    assert 'To finish, call SubmitWorkpaperAction;' not in _NATIVE_SPECIALIST_SYSTEM_PROMPT
