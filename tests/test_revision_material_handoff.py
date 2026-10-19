"""Revision reentry retires episodes, not evidence or actual accounting."""
from copy import deepcopy
import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from sec_agent.agent_runtime.author_revision import revision_material_handoff
from sec_agent.agent_runtime.research_context_view import working_view, public_operation
from sec_agent.agent_runtime.specialist_graph import _model_request, SpecialistNotebook
from test_revision_scope_budget import revision_state
from test_context_retirement import batch


def test_revision_has_one_submission_protocol_and_legacy_first_draft_is_unchanged():
    state = revision_state()
    notebook = SpecialistNotebook.model_validate_json(json.dumps(state['notebook']))
    local = _model_request(state=state, notebook=notebook, allow_workpaper_field_edits=True)
    assert {'save_workpaper_edits', 'finalize_workpaper_revision'} <= set(local['allowed_actions'])
    assert 'revise_workpaper' not in local['allowed_actions']
    assert 'submit_workpaper' not in local['allowed_actions']
    assert 'full_replacement' not in local['submission_to_repair']['submission_contract']
    legacy = _model_request(state=state, notebook=notebook, allow_workpaper_field_edits=False)
    assert 'submit_workpaper' in legacy['allowed_actions']
    assert 'revise_workpaper' not in legacy['allowed_actions']


def context():
    return {'allowed_actions': ['read_research_history', 'revise_workpaper'],
            'task_context': {'assignment': {'objective': 'Original question'}},
            'submission_to_repair': {'candidate': {'thesis': 'Existing thesis'}},
            'execution_budget': {'remaining_model_turns': 1},
            'progress': {'model_turn_count': 25}}


def history():
    return [HumanMessage(content=json.dumps(context())),
        *batch('first', 'RequestSourceAction', {}, {'passage_id': 'P1', 'passage': 'Necessary FY2027 fact'}),
        *batch('later', 'RequestSourceAction', {}, {'passage_id': 'P2', 'passage': 'Additional fact'},
               reasoning='OLD BROAD REWRITE PLAN', context=context())]


def test_reentry_keeps_visible_material_readbacks_candidate_budget_and_raw_journal():
    rows = history(); before = deepcopy(rows)
    canonical = revision_material_handoff(rows, context())
    projected = working_view(canonical)
    assert rows == before and canonical[:-1] == before
    assert not any(isinstance(m, AIMessage) for m in projected)
    view = json.loads(next(m.content for m in projected if m.additional_kwargs.get('fin_research_working_view')))
    assert {r['passage_id'] for r in view['current_materials']} == {'P1', 'P2'}
    assert view['current_context']['execution_budget'] == context()['execution_budget']
    assert view['current_context']['submission_to_repair'] == context()['submission_to_repair']
    for cid in ('first', 'later'):
        assert public_operation(canonical, cid) == public_operation(before, cid)
    assert working_view(projected) == projected
    # Further reading does not complete the current revision working set.
    later = [*canonical, *batch('next', 'RequestSourceAction', {}, {'passage_id': 'P3', 'passage': 'New original'})]
    later_view = working_view(later)
    assert any(isinstance(m, AIMessage) for m in later_view)


def test_incomplete_or_failed_batches_cannot_be_hidden():
    rows = history()
    with pytest.raises(ValueError, match='complete_tool_pairs'):
        revision_material_handoff(rows[:-1], context())
    rows[-1] = rows[-1].model_copy(update={'status': 'error'})
    with pytest.raises(ValueError, match='successful_read_boundary'):
        revision_material_handoff(rows, context())
    with pytest.raises(ValueError, match='requires_candidate'):
        revision_material_handoff(history(), {})


def test_rejected_state_and_submission_stay_current():
    rows = history()
    rows.extend(batch('edit', 'ReviseWorkpaperAction', {}, {'accepted': False}))
    with pytest.raises(ValueError, match='requires_read_boundary'):
        revision_material_handoff(rows, context())


def test_normal_revision_transition_retains_cohort_through_reads_and_save():
    rows = history()
    rows.extend(batch('accepted', 'SubmitWorkpaperAction', {}, {'accepted': True}))
    rows.append(HumanMessage(content=json.dumps(context()),
        additional_kwargs={'fin_research_stage_boundary': 'accepted_submission_to_revision'}))
    rows.extend(batch('read-original', 'RequestSourceAction', {},
        {'passage_id': 'P3', 'passage': 'New source needed for revision'}))
    rows.extend(batch('save-draft', 'SaveWorkpaperEditsAction', {}, {'saved': True, 'accepted': False}))
    view = json.loads(next(m.content for m in working_view(rows)
        if m.additional_kwargs.get('fin_research_working_view')))
    assert view['material_focus'] == 'revision_working_set'
    assert {m['passage_id'] for m in view['current_materials']} == {'P2', 'P3'}
    assert public_operation(rows, 'first')['receipt']['result']['passage_id'] == 'P1'


@pytest.mark.parametrize('pressure', [False, True])
def test_adapter_reentry_reaches_actual_sdk_with_only_edit_submission_and_saved_sources(pressure):
    import httpx
    from sec_agent.agent_runtime.deepseek_structured_agents import DeepSeekStructuredAgentAdapter
    from test_deepseek_structured_agents import _config, _models
    from test_research_context_checkpoint import model
    state = revision_state()
    request = _model_request(state=state, notebook=SpecialistNotebook.model_validate_json(json.dumps(state['notebook'])),
        allow_workpaper_field_edits=True, remaining_model_requests=1)
    request['allowed_actions'].append('read_research_history')
    request['allowed_actions'].append('update_research_state')
    request['tool_results'] = [{'tool_call_id': 'later', 'name': 'RequestSourceAction', 'status': 'success',
                              'content': json.dumps({'passage_id': 'P2', 'passage': 'Additional fact'})}]
    wires = []
    def serve(req):
        wire = json.loads(req.content); wires.append(wire)
        names = {t['function']['name'] for t in wire['tools']}
        assert {'SaveWorkpaperEditsAction', 'FinalizeWorkpaperRevisionAction'} <= names
        assert not {'ReviseWorkpaperAction', 'SubmitWorkpaperAction'} & names
        assert not any(m['role'] == 'assistant' for m in wire['messages'])
        encoded = json.dumps(wire, ensure_ascii=False)
        assert 'Necessary FY2027 fact' in encoded and 'Additional fact' in encoded
        assert 'OLD BROAD REWRITE PLAN' not in encoded
        assert 'Context size reminder' not in encoded
        assert 'native_draft_checkpoint' in encoded
        return httpx.Response(200, json={'id': 'offline', 'object': 'chat.completion', 'created': 1,
            'model': 'deepseek-v4-flash', 'choices': [{'index': 0, 'finish_reason': 'tool_calls', 'message': {
                'role': 'assistant', 'content': '', 'tool_calls': [{'id': 'read-again', 'type': 'function',
                'function': {'name': 'ReadResearchHistoryAction', 'arguments': json.dumps({
                    'section': 'operation', 'tool_call_id': 'first', 'reason_summary': 'Read exact original'})}}]}}]})
    chat = model(http_client=httpx.Client(transport=httpx.MockTransport(serve)),
                 research_checkpoint_tokens=1 if pressure else None)
    models = _models(); models['specialist'] = chat
    adapter = DeepSeekStructuredAgentAdapter(config=_config().model_copy(update={
        'agentic_message_history': True, 'runtime_context_binding': True}), chat_models=models)
    adapter._agentic_history[request['agent_id']] = history()[:-1]
    adapter._revision_material_handoffs = {request['agent_id']}
    adapter.specialist_model_turn(request)
    assert len(wires) == 1
    assert request['agent_id'] not in adapter._revision_material_handoffs
    saved = adapter._agentic_history[request['agent_id']]
    assert public_operation(saved, 'first') == public_operation(history(), 'first')


def test_pressure_notice_and_reads_do_not_retire_revision_materials():
    rows = revision_material_handoff(history(), context())
    notice = SystemMessage(content='Context size reminder', additional_kwargs={'fin_context_checkpoint_instruction': True})
    def view(messages):
        return json.loads(next(m.content for m in working_view(messages)
                               if m.additional_kwargs.get('fin_research_working_view')))
    before = deepcopy(rows)
    carried = view([*rows, notice])
    assert carried['material_focus'] == 'revision_working_set'
    assert {r['passage_id'] for r in carried['current_materials']} == {'P1', 'P2'}
    assert rows == before
    later = [*rows, *batch('next', 'RequestSourceAction', {}, {'passage_id': 'P3', 'passage': 'New original'}), notice]
    assert view(later)['material_focus'] == 'revision_working_set'
    assert {'P1', 'P2'} <= {r['passage_id'] for r in view(later)['current_materials']}


def test_revision_set_survives_saves_errors_restart_and_can_be_explicitly_reselected():
    from langchain_core.messages import messages_from_dict, messages_to_dict
    rows = revision_material_handoff(history(), context())
    def visible(messages):
        out = working_view(messages)
        v = json.loads(next(m.content for m in out if m.additional_kwargs.get('fin_research_working_view')))
        return v, json.dumps([m.model_dump() for m in out])
    for cid, name, receipt, status in [
        ('calc', 'RequestCalculationAction', {'calculation_id': 'CALC::new', 'value_decimal': '2'}, 'success'),
        ('save-1', 'SaveWorkpaperEditsAction', {'saved': True, 'submitted': False, 'accepted': False}, 'success'),
        ('bad-save', 'SaveWorkpaperEditsAction', {'saved': False, 'error': 'bad_path'}, 'error'),
        ('save-2', 'SaveWorkpaperEditsAction', {'saved': True, 'submitted': False, 'accepted': False}, 'success'),
        ('final-bad', 'FinalizeWorkpaperRevisionAction', {'accepted': False, 'error': 'missing_quote'}, 'error'),
    ]:
        rows.extend(batch(cid, name, {}, receipt, status=status))
        rows = messages_from_dict(json.loads(json.dumps(messages_to_dict(rows))))
        v, text = visible(rows)
        assert v['material_focus'] == 'revision_working_set'
        assert 'Necessary FY2027 fact' in text and 'Additional fact' in text
        assert 'CALC::new' in text
        assert public_operation(rows, 'first')['receipt']['result']['passage_id'] == 'P1'
    rows.extend(batch('select', 'UpdateResearchStateAction', {'working_state': {'retain_source_ids': ['P2']}},
                      {'accepted': True}))
    v, text = visible(rows)
    assert [m['passage_id'] for m in v['current_materials']] == ['P2']
    assert 'Necessary FY2027 fact' not in text
    assert public_operation(rows, 'first')['receipt']['result']['passage'] == 'Necessary FY2027 fact'
    rows.extend(batch('select-none', 'UpdateResearchStateAction', {'retain_source_ids': []}, {'accepted': True}))
    assert visible(rows)[0]['current_materials'] == []
    rows.extend(batch('reread', 'RequestSourceAction', {}, {'passage_id': 'P1', 'passage': 'Necessary FY2027 fact'}))
    rows.extend(batch('saved-again', 'SaveWorkpaperEditsAction', {}, {'saved': True, 'accepted': False}))
    assert [m['passage_id'] for m in visible(rows)[0]['current_materials']] == ['P1']
    rows.extend(batch('final-ok', 'FinalizeWorkpaperRevisionAction', {}, {'accepted': True}))
    assert visible(rows)[0]['material_focus'] != 'revision_working_set'


def test_revision_explicit_release_keeps_exact_readback_and_later_read_reopens():
    rows = revision_material_handoff(history(), context())
    def material_ids(messages):
        v = json.loads(next(m.content for m in working_view(messages)
                            if m.additional_kwargs.get('fin_research_working_view')))
        return {m['passage_id'] for m in v['current_materials']}
    rows.extend(batch('release', 'UpdateResearchStateAction', {}, {'accepted': True,
        'context_release': {'source_ids': ['P1'], 'through_model_turn': 30}}))
    assert material_ids(rows) == {'P2'}
    assert public_operation(rows, 'first')['receipt']['result']['passage'] == 'Necessary FY2027 fact'
    rows.extend(batch('reopen', 'ReadResearchHistoryAction', {'section': 'operation', 'tool_call_id': 'first'},
        {'historical_record': public_operation(rows, 'first')}))
    rows.extend(batch('save', 'SaveWorkpaperEditsAction', {}, {'saved': True, 'accepted': False}))
    assert material_ids(rows) == {'P1', 'P2'}
    rows.append(HumanMessage(content=json.dumps(context()),
        additional_kwargs={'fin_research_stage_boundary': 'accepted_submission_to_revision'}))
    v = json.loads(next(m.content for m in working_view(rows)
                        if m.additional_kwargs.get('fin_research_working_view')))
    assert v['material_focus'] == 'revision_working_set'
    assert {m['passage_id'] for m in v['current_materials']} == {'P1', 'P2'}
    rows.extend(batch('new-stage-save', 'SaveWorkpaperEditsAction', {}, {'saved': True, 'accepted': False}))
    assert material_ids(rows) == {'P1', 'P2'}
