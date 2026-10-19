"""Offline execution-view tests; no claim about the author's financial reasoning."""
from copy import deepcopy
import json

from sec_agent.agent_runtime.research_context_view import compact_current_context, public_operation
from test_revision_task_context import context, fixture, view


def revision():
    c = context()
    p = c['submission_to_repair']['candidate']
    p['claims'] = [{'claim_id': 'C1', 'statement': 'Target claim'},
                   {'claim_id': 'C2', 'statement': 'Unchanged other claim'}]
    p['narrative_markdown'] = 'Before. Target prose. After.'
    c['task_context']['revision_feedback'][0]['problematic_quote'] = 'Target prose.'
    c['task_context']['working_state_guidance'] = 'Write a plan and checkpoint note.'
    c['task_context']['accepted_revision_baseline']['submission'] = deepcopy(p)
    return c


def test_fragment_keeps_exact_targets_and_full_field_reads():
    from langchain_core.messages import HumanMessage
    c = revision(); before = deepcopy(c); out = compact_current_context(c)
    repair = out['submission_to_repair']; task = out['task_context']
    assert c == before and 'candidate' not in repair
    assert repair['current_fragment']['claims'] == [c['submission_to_repair']['candidate']['claims'][0]]
    assert repair['current_fragment']['exact_prose_matches'] == [
        {'path': '/narrative_markdown', 'offset': 8, 'text': 'Target prose.'}]
    assert task['revision_step']['scope'] == 'focus_not_edit_allowlist'
    assert 'working_state_guidance' not in task
    assert task['revision_progress']['submitted'] is False
    for field, read in repair['field_reads'].items():
        r = public_operation([HumanMessage(content=json.dumps(c))], read['arguments']['tool_call_id'])
        assert r['receipt']['result'] == c['submission_to_repair']['candidate'][field]


def test_successful_save_is_progress_not_error_or_acceptance():
    c = revision(); repair = c['submission_to_repair']
    repair['last_edit_feedback'] = {'saved': True, 'submitted': False, 'accepted': False}
    repair['draft_state'] = {'saved_batches': 1, 'changed_paths': ['/claims/0/statement'],
                             'latest_changed_paths': ['/claims/0/statement']}
    out = compact_current_context(json.loads(json.dumps(c)))
    assert out['task_context']['revision_step']['kind'] == 'edit_finding_fragment'
    assert out['task_context']['revision_progress']['saved_batches'] == 1
    import jsonpointer
    value_at = out['submission_to_repair']['latest_saved_fields']['/claims/0/statement']['current_value_at']
    assert jsonpointer.resolve_pointer({'current_context': out}, value_at) == 'Target claim'
    repair['last_edit_feedback'] = {'batch_applied': False, 'error': 'stale digest'}
    out = compact_current_context(c)
    assert out['task_context']['revision_step']['kind'] == 'repair_current_error'
    assert out['submission_to_repair']['last_edit_feedback']['error'] == 'stale digest'


def test_old_response_does_not_complete_new_finding_and_current_response_is_only_author_disposition():
    c = revision(); p = c['submission_to_repair']['candidate']
    response = {'finding_id': 'F1', 'disposition': 'corrected', 'explanation': 'Old response'}
    p['task_note']['finding_responses'] = [response]
    c['task_context']['accepted_revision_baseline']['submission'] = deepcopy(p)
    assert compact_current_context(c)['task_context']['revision_step']['pending_finding_ids'] == ['F1']
    c['submission_to_repair']['draft_state'] = {'saved_batches': 1,
        'changed_paths': ['/task_note/finding_responses'], 'latest_changed_paths': ['/task_note/finding_responses']}
    p['task_note']['finding_responses'] = [{**response, 'explanation': 'New author response'}]
    out = compact_current_context(c)
    assert out['task_context']['revision_step']['kind'] == 'reconcile_saved_draft'
    assert out['task_context']['revision_step']['author_responded_finding_ids'] == ['F1']
    assert out['task_context']['revision_progress']['submitted'] is False
    c['submission_to_repair']['validation_feedback'] = {'binding': 'current_candidate', 'issues': ['Bad source']}
    out = compact_current_context(c)
    assert out['task_context']['revision_step']['kind'] == 'repair_current_error'


def test_high_pressure_revision_does_not_require_a_separate_note_or_drop_materials():
    from sec_agent.agent_runtime.model_context import research_checkpoint_request
    from sec_agent.agent_runtime.deepseek_structured_agents import _native_function_schema
    from sec_agent.agent_runtime.specialist_graph import SaveWorkpaperEditsAction
    from sec_agent.agent_runtime.research_working_state import UpdateResearchStateAction
    from test_research_context_checkpoint import model
    rows = fixture(); before = deepcopy(rows)
    tools = {'SaveWorkpaperEditsAction': SaveWorkpaperEditsAction,
             'UpdateResearchStateAction': UpdateResearchStateAction}
    clean, available, notice = research_checkpoint_request(rows, model=model(research_checkpoint_tokens=1),
        native_tools=tools, schema=_native_function_schema, runtime_context_binding=True, max_input_characters=1)
    assert notice is None and available == tools and rows == before
    assert not any(m.additional_kwargs.get('fin_context_checkpoint_instruction') for m in clean)
    assert view(clean)['current_materials'] == view(rows)['current_materials']
    assert len(view(clean)['current_materials']) == 7


def test_empty_budget_does_not_become_a_new_allowance_in_view():
    c = revision(); c['execution_budget']['remaining_model_turns'] = 0
    out = compact_current_context(c)
    assert out['execution_window']['current_request_authorized'] is False
    assert c['execution_budget']['remaining_model_turns'] == 0


def test_revision_without_note_reminder_still_hits_real_adapter_input_limit():
    import httpx
    import pytest
    from sec_agent.agent_runtime.deepseek_structured_agents import (
        DeepSeekStructuredAgentAdapter, DeepSeekStructuredAgentError)
    from test_deepseek_structured_agents import _config, _models, _agentic_turn_request
    from test_research_context_checkpoint import model
    events = []
    def forbidden(request):
        raise AssertionError('Input limit must block transport')
    with httpx.Client(transport=httpx.MockTransport(forbidden)) as client:
        models = _models(); models['specialist'] = model(http_client=client, research_checkpoint_tokens=1)
        config = _config().model_copy(update={'agentic_message_history': True, 'runtime_context_binding': True})
        config = config.model_copy(update={'token_budget_basis': {**config.token_budget_basis,
            'specialist': config.token_budget_basis['specialist'].model_copy(update={'max_input_characters': 10000})}})
        adapter = DeepSeekStructuredAgentAdapter(config=config, chat_models=models, audit_sink=events.append)
        request = _agentic_turn_request(); c = revision()
        request['task_context'] = c['task_context']
        request['submission_to_repair'] = c['submission_to_repair']
        request['task_context']['revision_feedback'][0]['source_checks'] = ['Necessary material ' * 10000]
        request['allowed_actions'] += ['save_workpaper_edits', 'finalize_workpaper_revision', 'update_research_state']
        with pytest.raises(DeepSeekStructuredAgentError, match='deepseek_specialist_input_character_limit_exceeded'):
            adapter.specialist_model_turn(request)
    blocked = next(e for e in events if e.get('status') == 'blocked_before_transport_input_limit')
    assert blocked['context_checkpoint'] is None
    assert blocked['provider_call_attempted'] is False
