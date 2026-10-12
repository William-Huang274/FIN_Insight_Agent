"""History retirement is a request view, never an acceptance or source edit."""
from copy import deepcopy
import json

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from sec_agent.agent_runtime.model_context import coalesce_context_snapshots, pressure_read_history, task_boundary_history


def batch(cid, name, args, result, *, reasoning='old private episode', context=None, status='success'):
    return [AIMessage(content='', tool_calls=[{'id': cid, 'name': name, 'args': args}],
                      additional_kwargs={'reasoning_content': reasoning}),
        ToolMessage(tool_call_id=cid, name=name, status=status,
                    content=json.dumps({'result': result, **({'current_context': context} if context else {})}))]


def test_invalid_and_flat_old_notes_retire_only_after_a_later_accepted_state():
    invalid = AIMessage(content='', invalid_tool_calls=[{'id': 'bad', 'name': 'UpdateResearchStateAction',
        'args': '{invalid proposal ' * 1000, 'error': 'parser echoed proposal ' * 1000}],
        additional_kwargs={'reasoning_content': 'private old draft'})
    error = ToolMessage(tool_call_id='bad', name='UpdateResearchStateAction', status='error',
        content=json.dumps({'result': {'accepted': False, 'feedback': [{'code': 'invalid_json'}]}}))
    note = {'current_subtask': 'Compare periods', 'retain_source_ids': [], 'findings': ['Current finding ' * 100]}
    rows = [HumanMessage(content='Original question'), invalid, error,
        *batch('saved', 'UpdateResearchStateAction', note, {'accepted': True, 'working_state': note}),
        *batch('pending', 'UpdateResearchStateAction', {'current_subtask': 'New pending draft ' * 500},
               {'accepted': False, 'feedback': [{'code': 'missing_objective'}]}, status='error')]
    original = deepcopy(rows)
    out = task_boundary_history(rows)
    archived = json.loads(out[1].content)
    assert 'invalid proposal' not in archived['invalid_tool_calls'][0]['args']
    assert 'not accepted' in archived['invalid_tool_calls'][0]['error']
    assert json.loads(out[2].content)['result']['feedback'] == [{'code': 'invalid_json'}]
    assert 'superseded_working_state' in json.loads(out[3].content)['tool_calls'][0]['args']
    assert json.loads(out[4].content)['result']['working_state'] == note
    assert out[-2:] == rows[-2:] and rows == original
    assert out == task_boundary_history(out)
    # Without acceptance, the invalid draft and its parser response stay repairable.
    assert task_boundary_history(rows[:3]) == rows[:3]


def test_pressure_retires_only_complete_consumed_pairs_without_losing_pinned_sources():
    note = {'retain_source_ids': ['PIN'], 'findings': ['Current accepted note']}
    context = {'task_context': {'research_working_state': note, 'assignment': 'Original question'}}
    pinned = {'observations': [{'kind': 'evidence', 'status': 'success', 'content': [
        {'passage_id': 'PIN', 'passage': 'Actual USD FY2027 original ' * 100}], 'references': [{'ref_id': 'PIN'}]}]}
    rows = [HumanMessage(content=json.dumps(context)),
        *batch('pin', 'RequestSourceAction', {'selection': {'node_id': 'PIN'}}, pinned),
        *batch('old', 'RequestSourceAction', {'selection': {'node_id': 'OLD'}}, {'text': 'Old read ' * 1000}),
        *batch('new', 'RequestSourceAction', {'selection': {'node_id': 'NEW'}}, {'text': 'Latest original'})]
    original = deepcopy(rows)
    out = pressure_read_history(rows)
    assert out[-2:] == rows[-2:]
    assert isinstance(out[1], HumanMessage) and json.loads(out[2].content)['result'] == pinned
    assert 'read_tool' in json.loads(out[4].content)['original_content']
    assert 'OLD' in out[4].content and 'Old read ' not in out[4].content
    assert out == pressure_read_history(out) and rows == original
    incomplete = AIMessage(content='', tool_calls=[{'id': 'unpaired', 'name': 'RequestSourceAction', 'args': {}}],
        additional_kwargs={'reasoning_content': 'Required for unpaired native call'})
    out = pressure_read_history([*rows[:3], incomplete, *rows[-2:]])
    assert out[3] == incomplete


def test_accepted_state_and_cumulative_feedback_share_values_across_archived_and_live_handoffs():
    state = {'current_subtask': 'Compare', 'findings': ['Source-backed finding ' * 100],
        'reference_issues': [{'id': 'invalid', 'reason': 'Original validation issue ' * 100}]}
    feedback = {'code': 'specific_failure', 'message': 'Original actionable error ' * 100}
    first = HumanMessage(content=json.dumps({'name': 'UpdateResearchStateAction', 'status': 'success',
        'result': {'accepted': True, 'working_state': state, 'reference_issues': state['reference_issues']},
        'current_context': {'progress': {'feedback': [feedback]}}}), additional_kwargs={'fin_checkpoint_archive': True})
    second = ToolMessage(tool_call_id='next', content=json.dumps({'result': {'fresh': 'new data'},
        'current_context': {'task_context': {'research_working_state': state},
            'progress': {'feedback': [feedback, {'code': 'new_error'}]}}}))
    rows = [first, second]
    out = coalesce_context_snapshots(rows)
    b = json.loads(out[1].content)
    assert b['current_context']['task_context']['research_working_state']['identical_snapshot_retained_at'] == {
        'message_index': 0, 'field': 'result.working_state'}
    assert b['current_context']['progress']['feedback'][0]['identical_snapshot_retained_at'] == {
        'message_index': 0, 'field': 'current_context.progress.feedback[0]'}
    assert b['current_context']['progress']['feedback'][1] == {'code': 'new_error'}
    assert json.loads(out[0].content)['result']['working_state'] == state
    assert coalesce_context_snapshots(out) == out
