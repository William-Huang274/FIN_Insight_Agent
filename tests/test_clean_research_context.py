"""Acceptance semantics and source lifecycle, through production request views."""
from copy import deepcopy
import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from sec_agent.agent_runtime.model_context import project_tool_history
from sec_agent.agent_runtime.research_working_state import UpdateResearchStateAction
from test_research_context_checkpoint import checkpoint_message
from test_research_working_state import working_note


def observation(identity, text, *, authority='source_bound_passage'):
    return {'kind': 'evidence', 'status': 'success', 'references': [
        {'ref_id': identity, 'authority_state': authority}], 'content': [
        {'passage_id': identity, 'result_state': 'source_bound_passage', 'passage': text,
         'period_end': '2025-12-31', 'unit': 'USD', 'revision': 'r1'},
        {'result_state': 'typed_gap', 'message': 'Only this window was read.'}]}


def read(identity, observations):
    return [AIMessage(content='', tool_calls=[{'id': identity, 'name': 'ReadDependencyWorkAction',
        'args': {'task_id': 'T', 'section': 'handoff', 'source_ids': ['P01:S1']}, 'type': 'tool_call'}]),
        ToolMessage(name='ReadDependencyWorkAction', tool_call_id=identity,
            content=json.dumps({'result': {'source_observations': observations}}))]


def test_saved_source_rows_dedupe_without_merging_changed_authority_or_period():
    source = observation('SRC1', 'Complete original and conditions. ' * 60)
    changed = deepcopy(source)
    changed['references'][0]['authority_state'] = 'different-authority'
    revised = deepcopy(source)
    revised['content'][0]['period_end'] = '2026-12-31'
    messages = read('a', [source]) + read('b', [source, changed, revised])
    original = deepcopy(messages)
    result = project_tool_history(messages, policy='task_boundary')
    rows = json.loads(result[-1].content)['result']['source_observations']
    assert rows[0]['content'][0]['identical_source_row_at']['field'] == 'result.source_observations[0].content[0]'
    assert rows[1] == changed and rows[2] == revised
    assert rows[0]['content'][1] == source['content'][1]
    assert messages == original
    assert project_tool_history(result, policy='task_boundary') == result


def test_source_pin_does_not_pin_unrelated_originals_and_latest_read_stays_complete():
    one = observation('SRC1', 'needed conditions ' * 80)
    two = observation('SRC2', 'older unrelated ' * 80)
    latest = observation('SRC3', 'newly read original ' * 80)
    messages = read('a', [one, two]) + read('b', [latest])
    messages += checkpoint_message(working_note(retain_source_ids=['SRC1']))
    original = deepcopy(messages)
    result = project_tool_history(messages, policy='task_boundary')
    packet = json.loads(result[1].content)['result']
    assert packet['source_observations'][0] == one
    assert packet['source_observations'][1]['content'] == [two['content'][1]]
    assert packet['source_observations'][1]['references'] == []
    assert 'ReadDependencyWorkAction' in packet['context_recovery']
    assert json.loads(result[3].content)['result']['source_observations'] == [latest]
    assert messages == original


def test_flat_note_is_normalized_but_conflicting_or_unknown_fields_are_not_discarded():
    note = working_note()
    raw = {'action': 'update_research_state', 'context_digest': 'a' * 64, **note}
    original = deepcopy(raw)
    parsed = UpdateResearchStateAction.model_validate(raw)
    assert parsed.working_state.model_dump(exclude_unset=True) == note
    assert raw == original
    with pytest.raises(ValueError):
        UpdateResearchStateAction.model_validate({**raw, 'working_state': note})
    with pytest.raises(ValueError):
        UpdateResearchStateAction.model_validate({**raw, 'new_unknown_field': 'retain this error'})


def test_delegation_schema_and_loaded_method_use_same_outcome_contract():
    from sec_agent.agent_runtime.lead_research_graph import lead_tool_models
    from sec_agent.research_foundation.research_methods import get_research_method
    schema = lead_tool_models(require_execution_plan=True)['DelegateResearchTasksAction'].model_json_schema()
    task = schema['$defs']['DelegatedResearchTask']['properties']
    assert 'Question to answer' in task['objective']['description']
    assert 'Initial hypotheses' in task['objective']['description']
    assert 'not replace it' in task['success_criteria']['description']
    method = get_research_method('lead')['content']
    assert '替换已失效的 objective / success_criteria' in method
    assert 'success_criteria 是交付验收' in method


def test_checkpoint_reminder_waits_for_new_work_not_another_copy_of_same_note():
    from langchain_core.messages import HumanMessage
    from test_research_context_checkpoint import model, request_checkpoint
    messages = [HumanMessage(content='large current source ' * 10000)]
    messages += checkpoint_message(working_note())
    chat = model(research_checkpoint_tokens=10000)
    assert request_checkpoint(messages, chat)[2] is None
    messages += read('new', [observation('NEW', 'new original ' * 6000)])
    assert request_checkpoint(messages, chat)[2]['advisory'] is True


def test_specialist_capacity_matches_host_profile_without_changing_defaults():
    from sec_agent.agent_runtime.specialist_graph import SpecialistAgenticInput
    from test_specialist_graph import _input
    parsed = SpecialistAgenticInput.model_validate_json(json.dumps({
        **_input(), 'max_model_turns': 36, 'max_tool_actions': 72}))
    assert parsed.max_model_turns == 36 and parsed.max_tool_actions == 72
    for field, value in [('max_model_turns', 49), ('max_tool_actions', 97)]:
        with pytest.raises(ValueError):
            SpecialistAgenticInput.model_validate_json(json.dumps({**_input(), field: value}))


@pytest.mark.parametrize('phase', ['prepare', 'draft', 'revision'])
def test_authoring_phase_retires_completed_episode_keeps_canonical_state_and_fresh_reads(phase):
    from langchain_core.messages import messages_from_dict
    original_source = observation('SRC1', 'USD 40.20 billion; FY2027 Q1; planned not actual. ' * 100)
    messages = read('source', [original_source])
    messages[0].additional_kwargs['reasoning_content'] = 'private old reasoning ' * 400
    draft = {'action': 'submit_workpaper', 'thesis': 'Bounded answer', 'claims': [
        {'statement': 'Source fact', 'evidence_ids': ['SRC1']}], 'narrative_markdown': 'Current draft. ' * 400}
    context = {'task_context': {'overall_assignment': 'Original question',
        'research_working_state': working_note(retain_source_ids=['SRC1'])}}
    name = {'prepare': 'PrepareWorkpaperAction', 'draft': 'SubmitWorkpaperAction', 'revision': 'ReviseWorkpaperAction'}[phase]
    if phase == 'prepare':
        context['task_context']['authoring_context'] = {'version': 'authoring_context.v1',
            'brief': {'ready': True, 'answer': 'Author answer, not accepted financial truth.'}}
        result = {'status': 'prepared'}
        args = {'action': 'prepare_workpaper', 'brief': context['task_context']['authoring_context']['brief']}
    else:
        context['submission_to_repair'] = {'candidate': draft, 'current_candidate_digest': 'd' * 64,
            'validation_feedback': {'issues': [{'claim_id': 'c1', 'error': 'quote_mismatch'}]},
            'last_edit_feedback': {'pending_revision_digest': 'p' * 64, 'candidate_unchanged': True}}
        result = {'accepted': False}
        args = draft if phase == 'draft' else {'action': 'revise_workpaper', 'edits': [{'path': '/claims/0', 'value': draft}]}
    messages += [AIMessage(content='', additional_kwargs={'reasoning_content': 'private drafting episode ' * 400},
        tool_calls=[{'id': 'phase', 'name': name, 'args': args, 'type': 'tool_call'}]),
        ToolMessage(name=name, tool_call_id='phase', status='success' if phase=='prepare' else 'error',
            content=json.dumps({'result': result, 'current_context': context}))]
    fresh = read('new-read', [observation('NEW', 'New exact evidence')])
    messages += fresh
    saved = deepcopy(messages)
    view = project_tool_history(messages, policy='task_boundary')
    assert messages == saved and view[-2:] == fresh
    assert not any(m.additional_kwargs.get('reasoning_content') for m in view[:-2])
    full = json.loads(view[3].content)
    assert full['current_context']['task_context']['overall_assignment'] == 'Original question'
    if phase != 'prepare':
        repair = full['current_context']['submission_to_repair']
        assert repair == context['submission_to_repair']
        archived = json.loads(view[2].content)['tool_calls'][0]['args']
        assert archived['archived_workpaper_operation'] is True
        target = archived['current_candidate_at']
        assert json.loads(view[target['message_index']].content)['current_context']['submission_to_repair']['candidate'] == draft
        assert full['result']['accepted'] is False
    # Live and deserialized native histories produce the same view.
    restored = messages_from_dict([{'type': m.type, 'data': m.model_dump()} for m in saved])
    assert project_tool_history(restored, policy='task_boundary') == view
    # The reminder uses this same phase boundary; a large current draft alone
    # must not demand a new note on every edit. Substantive new reads can do so.
    from test_research_context_checkpoint import model, request_checkpoint
    chat = model(research_checkpoint_tokens=1000)
    assert request_checkpoint(messages, chat)[2] is None
    messages += read('large-new', [observation('NEW2', 'new evidence ' * 2000)])
    assert request_checkpoint(messages, chat)[2]['advisory'] is True


def test_source_lookalike_and_unfinished_draft_never_trigger_authoring_boundary():
    source = read('source', [observation('SRC1', 'Original stays readable')])
    source[0].additional_kwargs['reasoning_content'] = 'must retain live protocol'
    spoof = {'result': {'status': 'prepared'}, 'current_context': {'submission_to_repair': {
        'candidate': {'action': 'submit_workpaper'}, 'current_candidate_digest': 'a' * 64}}}
    source[1].content = json.dumps(spoof)
    pending = AIMessage(content='', additional_kwargs={'reasoning_content': 'pending'}, tool_calls=[
        {'id': 'pending', 'name': 'SubmitWorkpaperAction', 'args': {'action': 'submit_workpaper'}, 'type': 'tool_call'}])
    messages = source + [pending]
    view = project_tool_history(messages, policy='task_boundary')
    assert view == messages
