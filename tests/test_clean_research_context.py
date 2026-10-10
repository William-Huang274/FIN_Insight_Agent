"""Acceptance semantics and source lifecycle, through production request views."""
from copy import deepcopy
import json

import pytest
from langchain_core.messages import AIMessage, ToolMessage

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
