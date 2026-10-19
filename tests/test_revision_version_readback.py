from copy import deepcopy
import json

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from sec_agent.agent_runtime.deepseek_structured_agents import _agentic_semantic_value
from sec_agent.agent_runtime.research_context_view import public_operation, history_operation_page, working_view
from test_revision_document_read import fixture, ROOT


def history():
    context = fixture()
    context['submission_to_repair']['draft_state'] = {'saved_batches': 3}
    context['submission_to_repair']['candidate']['narrative_markdown'] *= 900
    result = {'historical_failure': {'saved': False, 'error': 'stale_base'},
              'current_recovered_save': {'result': {'saved': True, 'submitted': False,
                  'draft_digest': 'b' * 64, 'request_digest': 'host-private'}}}
    return [HumanMessage(content=json.dumps(context)),
            AIMessage(content='', tool_calls=[{'id': 'save', 'name': 'SaveWorkpaperEditsAction', 'args': {}}]),
            ToolMessage(name='SaveWorkpaperEditsAction', tool_call_id='save', status='error',
                        content=json.dumps({'result': _agentic_semantic_value(result), 'current_context': context}))]


def test_revision_handles_survive_projection_but_internal_hashes_do_not():
    raw = {'draft_result': {'saved': True, 'draft_digest': 'b' * 64, 'request_digest': 'internal'},
           'pending': {'pending_revision_digest': 'c' * 64, 'current_base_submission_digest': 'a' * 64},
           'observation_digest': 'internal', 'runtime_receipt': {'secret': 'private'}}
    projected = _agentic_semantic_value(raw)
    assert projected['draft_result'] == {'saved': True, 'draft_digest': 'b' * 64}
    assert projected['pending'] == raw['pending']
    assert 'internal' not in json.dumps(projected) and 'private' not in json.dumps(projected)
    assert _agentic_semantic_value(projected) == projected


def test_historical_save_keeps_its_version_and_failure_beside_current_candidate_version():
    rows = history(); before = deepcopy(rows)
    record = public_operation(rows, 'save')
    page = history_operation_page(record, view='receipt', max_characters=4000)
    assert page['current_version']['base_submission_digest'] == 'a' * 64
    assert page['current_version']['saved_batches'] == 3
    assert page['receipt']['status'] == 'error'
    assert page['receipt']['result']['historical_failure']['saved'] is False
    assert page['receipt']['result']['current_recovered_save']['result']['draft_digest'] == 'b' * 64
    read = page['current_version']['version_read']['arguments']['tool_call_id']
    assert public_operation(rows, read)['receipt']['result'] == 'a' * 64
    assert public_operation([], 'save') is None and rows == before


def test_every_candidate_page_has_version_without_changing_existing_record_offsets():
    rows = history(); before = deepcopy(rows)
    record = public_operation(rows, ROOT)
    legacy_record = {k: v for k, v in record.items() if k != 'current_version'}
    expected = json.dumps(legacy_record, ensure_ascii=False, separators=(',', ':'))
    for view in ('record', 'receipt'):
        offset = 0; pieces = []
        while True:
            page = history_operation_page(record, view=view, offset=offset, max_characters=1000)
            assert page['current_version']['base_submission_digest'] == 'a' * 64
            assert len(page['serialized_record_window']) <= 1000
            pieces.append(page['serialized_record_window'])
            if page['next_offset'] is None: break
            offset = page['next_offset']
        if view == 'record': assert ''.join(pieces) == expected
    assert rows == before


def test_current_version_advances_with_host_context_not_model_or_historical_save():
    rows = history()
    c = json.loads(rows[0].content); c['submission_to_repair']['base_submission_digest'] = 'd' * 64
    rows.append(HumanMessage(content=json.dumps(c)))
    rows.append(AIMessage(content='Current version is ' + 'e' * 64))
    for cid in ('save', ROOT, ROOT + '/claims/0'):
        assert public_operation(rows, cid)['current_version']['base_submission_digest'] == 'd' * 64
    # A new non-revision stage must not inherit an old edit handle.
    rows.append(HumanMessage(content=json.dumps({'allowed_actions': [], 'task_context': {}})))
    assert 'current_version' not in public_operation(rows, 'save')


def test_pending_read_reprojection_supplies_version_and_retains_original_read_receipt():
    rows = history()
    original = public_operation(rows, ROOT)
    old = history_operation_page(original, view='record', max_characters=1000)
    old.pop('current_version')
    rows += [AIMessage(content='', tool_calls=[{'id': 'read', 'name': 'ReadResearchHistoryAction',
        'args': {'section': 'operation', 'tool_call_id': ROOT, 'view': 'record', 'max_characters': 1000}}]),
        ToolMessage(name='ReadResearchHistoryAction', tool_call_id='read', content=json.dumps({'result': {'historical_record': old}}))]
    before = deepcopy(rows)
    projected = working_view(rows)
    result = json.loads(next(m.content for m in projected if isinstance(m, ToolMessage) and m.tool_call_id == 'read'))
    assert result['result']['historical_record']['current_version']['base_submission_digest'] == 'a' * 64
    assert rows == before


def test_native_adapter_delivers_save_version_and_current_version_in_real_wire(monkeypatch):
    from test_deepseek_structured_agents import _config, _models, _agentic_turn_request
    from test_research_context_checkpoint import model
    from sec_agent.agent_runtime.deepseek_structured_agents import DeepSeekStructuredAgentAdapter
    from sec_agent.agent_runtime import model_context
    captured = []
    class OfflineStop(BaseException): pass
    original = model_context.research_checkpoint_request
    def capture(messages, **kw):
        result = original(messages, **kw)
        captured.extend(result[0])
        raise OfflineStop()
    monkeypatch.setattr(model_context, 'research_checkpoint_request', capture)
    models = _models(); models['specialist'] = model()
    adapter = DeepSeekStructuredAgentAdapter(config=_config().model_copy(update={
        'agentic_message_history': True, 'runtime_context_binding': True}), chat_models=models)
    req = _agentic_turn_request(); req['allowed_actions'] = ['read_research_history']
    req['submission_to_repair'] = fixture()['submission_to_repair']
    req['tool_results'] = [{'name': 'SaveWorkpaperEditsAction', 'tool_call_id': 'save', 'status': 'success',
        'content': json.dumps({'draft_result': {'saved': True, 'draft_digest': 'a' * 64}})}]
    adapter._agentic_history[req['agent_id']] = history()[:-1]
    try: adapter.specialist_model_turn(req)
    except OfflineStop: pass
    else: raise AssertionError('Transport was not stopped')
    body = json.loads(next(m.content for m in captured if isinstance(m, ToolMessage) and m.tool_call_id == 'save'))['result']
    assert body['draft_result']['draft_digest'] == 'a' * 64
    assert body['current_version']['base_submission_digest'] == 'a' * 64
