from copy import deepcopy
import json
import os

import jsonpointer
import pytest
from langchain_core.messages import AIMessage, HumanMessage

from sec_agent.agent_runtime.research_context_view import working_view, public_operation
from test_context_retirement import batch


def state():
    return {'findings': ['Current finding with essential condition. ' * 15],
            'retain_source_ids': ['P1'], 'next_step': 'Explain the mechanism. ' * 15}


def base(note):
    return [HumanMessage(content=json.dumps({'turn_index': 10,
        'allowed_actions': ['read_research_history'], 'progress': {'observations': []},
        'task_context': {'assignment': {'objective': 'Original question'}, 'research_working_state': note}})),
        *batch('source', 'RequestSourceAction', {}, {'passage_id': 'P1',
            'passage': 'Exact source, scope and definition. ' * 20, 'period': 'FY2027', 'unit': 'USD'})]


def expanded(value, view):
    if isinstance(value, dict):
        if set(value) == {'current_value_at'}:
            return deepcopy(jsonpointer.resolve_pointer(view, value['current_value_at']))
        return {k: expanded(v, view) for k, v in value.items()}
    if isinstance(value, list):
        return [expanded(v, view) for v in value]
    return value


def test_accepted_copies_resolve_exactly_and_original_journal_is_unchanged():
    note = state(); rows = base(note)
    args = {**note, 'reason_summary': 'Save progress', 'resolved_questions': ['Past question']}
    receipt = {'accepted': True, 'working_state': {**note, 'reference_issues': [{'status': 'unresolved'}]}}
    rows.extend(batch('save', 'UpdateResearchStateAction', args, receipt))
    saved = deepcopy(rows); out = working_view(rows); view = json.loads(out[0].content)
    assert 'current_value_at' in str(out[-2:])
    assert expanded(out[-2].tool_calls[0]['args'], view) == args
    assert expanded(json.loads(out[-1].content)['result'], view) == receipt
    assert out[-2].additional_kwargs == rows[-2].additional_kwargs
    assert out[-2].tool_calls[0]['id'] == out[-1].tool_call_id == 'save'
    assert rows == saved and working_view(out) == out
    assert public_operation(rows, 'save')['receipt']['result'] == receipt


@pytest.mark.parametrize('status,accepted', [('error', False), ('success', False), ('success', None), ('error', True)])
def test_unaccepted_or_failed_identical_proposal_is_never_compacted(status, accepted):
    note = state(); rows = base(note)
    receipt = {'working_state': note, 'accepted': accepted, 'feedback': 'Repair this field'}
    rows.extend(batch('bad', 'UpdateResearchStateAction', note, receipt, status=status))
    assert working_view(rows)[-2:] == rows[-2:]


def test_pending_call_and_different_argument_are_not_assumed_accepted():
    note = state(); rows = base(note)
    proposed = {**note, 'findings': ['A different proposed finding']}
    rows.extend(batch('ok', 'UpdateResearchStateAction', proposed, {'accepted': True, 'working_state': note}))
    out = working_view(rows)
    assert out[-2].tool_calls[0]['args']['findings'] == proposed['findings']
    pending = AIMessage(content='', tool_calls=[{'id': 'pending', 'name': 'UpdateResearchStateAction', 'args': note}])
    rows.append(pending)
    assert working_view(rows)[-1] == pending


def test_acknowledgement_without_saved_state_does_not_rewrite_proposal():
    rows = base(state())
    rows.extend(batch('ack', 'UpdateResearchStateAction', state(), {'accepted': True}))
    assert working_view(rows)[-2:] == rows[-2:]


def test_preparation_and_basis_share_current_objects_but_keep_digest_and_conditions():
    note = state(); rows = base(note)
    brief = {'answer': 'Answer with its required condition. ' * 20, 'ready': True}
    authoring = {'version': 'authoring_context.v1', 'brief': brief, 'basis_digest': 'original-version',
                 'basis': {'working_state': note, 'source_checks': ['Material counterevidence']},
                 'financial_acceptance': False}
    args = {'brief': brief, 'reason_summary': 'Ready to write'}
    rows.extend(batch('prep', 'PrepareWorkpaperAction', args, {'status': 'prepared'},
        context={'task_context': {'authoring_context': authoring}}))
    saved = deepcopy(rows); out = working_view(rows); view = json.loads(out[0].content)
    projected = view['current_context']['task_context']['authoring_context']
    assert expanded(projected, view) == authoring
    assert expanded(out[-2].tool_calls[0]['args'], view) == args
    assert public_operation(rows, 'prep')['operation']['args'] == args and rows == saved


def test_stable_material_prefix_survives_new_turn_but_released_material_exits():
    note = state(); rows = base(note)
    rows.extend(batch('save', 'UpdateResearchStateAction', note, {'accepted': True, 'working_state': note}))
    first = working_view(rows)[0].content
    body = json.loads(rows[0].content); body['turn_index'] += 1; rows[0].content = json.dumps(body)
    second = working_view(rows)[0].content
    assert len(os.path.commonprefix([first, second])) > len(json.dumps(note))
    assert json.loads(first)['current_materials'] == json.loads(second)['current_materials']
    assert list(json.loads(first))[:2] == ['current_materials', 'current_material_bindings']
    # A later source read, followed by explicit selection, releases the earlier source.
    rows.extend(batch('next', 'RequestSourceAction', {}, {'passage_id': 'P2', 'passage': 'New source'}))
    changed = {**note, 'retain_source_ids': ['P2']}
    rows.extend(batch('release', 'UpdateResearchStateAction', changed, {'accepted': True, 'working_state': changed}))
    assert 'Exact source, scope' not in working_view(rows)[0].content


def test_tool_order_is_deterministic_without_adding_inactive_tools():
    from sec_agent.agent_runtime.deepseek_structured_agents import _NATIVE_SPECIALIST_TOOLS, specialist_tools_for_actions
    allowed = ['request_source', 'read_research_history', 'prepare_workpaper', 'submit_workpaper']
    selected = specialist_tools_for_actions(_NATIVE_SPECIALIST_TOOLS, allowed)
    shuffled = specialist_tools_for_actions(dict(reversed(list(_NATIVE_SPECIALIST_TOOLS.items()))), allowed)
    assert list(selected) == list(shuffled)
    a = specialist_tools_for_actions(selected, ['request_source', 'read_research_history', 'prepare_workpaper'])
    b = specialist_tools_for_actions(selected, ['request_source', 'read_research_history', 'submit_workpaper'])
    assert list(a)[:-1] == list(b)[:-1]
    assert list(a)[-1] == 'PrepareWorkpaperAction' and list(b)[-1] == 'SubmitWorkpaperAction'
