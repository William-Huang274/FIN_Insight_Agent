from copy import deepcopy
import json

from langchain_core.messages import HumanMessage, ToolMessage

from sec_agent.agent_runtime.research_context_view import current_context, public_operation, working_view
from test_revision_task_context import fixture, context, view


def test_new_revision_replaces_prior_task_guidance_but_keeps_original_readback():
    rows = fixture()
    first = json.loads(rows[1].content)
    first['task_context']['user_revision_request'] = 'OLD COMPLETED REVISION'
    rows[1].content = json.dumps(first)
    latest = context()
    latest['task_context']['revision_feedback'] = [{'finding_id': 'NEW'}]
    rows.append(HumanMessage(content=json.dumps(latest), additional_kwargs={
        'fin_research_stage_boundary': 'accepted_submission_to_revision'}))
    original = deepcopy(rows)
    result = view(rows)
    assert 'user_revision_request' not in result['current_context']['task_context']
    assert result['current_context']['task_context']['revision_feedback'] == [{'finding_id': 'NEW'}]
    assert len(result['current_materials']) == 7
    old_task = next(r for r in result['operation_catalog'] if r['tool'] == 'PriorRevisionTaskContext')
    assert public_operation(rows, old_task['tool_call_id'])['receipt']['result']['user_revision_request'] == 'OLD COMPLETED REVISION'
    assert public_operation(rows, 'runtime:initial-context')['receipt']['result']['task_context']['user_revision_request'] == 'OLD COMPLETED REVISION'
    assert rows == original


def test_full_snapshots_replace_removed_fields_partial_legacy_deltas_still_merge():
    first = HumanMessage(content=json.dumps({'task_context': {'research_question': 'Q', 'user_revision_request': 'LIVE'}}))
    partial = ToolMessage(tool_call_id='old', content=json.dumps({'current_context': {'task_context': {'progress': 'read'}}}))
    assert current_context([first, partial])['task_context']['user_revision_request'] == 'LIVE'
    replacement = ToolMessage(tool_call_id='new', content=json.dumps({'current_context': {
        'task_context_snapshot': True, 'task_context': {'research_question': 'Q'}}}))
    result = current_context([first, partial, replacement])
    assert result == {'task_context': {'research_question': 'Q'}}
    resumed = ToolMessage(tool_call_id='resume', content=json.dumps({'current_context': {
        'task_context_snapshot': True, 'task_context': {'research_question': 'Q', 'user_revision_request': 'CURRENT'}}}))
    assert current_context([first, partial, replacement, resumed])['task_context']['user_revision_request'] == 'CURRENT'
