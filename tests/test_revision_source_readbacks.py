from copy import deepcopy
import json
import pytest
from langchain_core.messages import HumanMessage
from langchain_core.utils.function_calling import convert_to_openai_tool
from sec_agent.agent_runtime.research_context_view import working_view, public_operation, history_operation_page
from sec_agent.agent_runtime.specialist_graph import ReadResearchHistoryAction
from test_context_retirement import batch


def fixture():
    context = {'allowed_actions': ['read_research_history'], 'task_context': {
        'revision_feedback': [{'reference_navigation': {'locations': [{'status': 'ambiguous',
            'candidates': [{'canonical_ids': ['PASSAGE::WEB::a']},
                           {'canonical_ids': ['PASSAGE::WEB::missing']}]}]}}]},
        'progress': {'observations': []}}
    original = {'passage_id': 'PASSAGE::WEB::a', 'passage': 'Reported result with conditions.',
                'source_locator': {'content_sha256': 'same-hash'}}
    messages = [HumanMessage(content=json.dumps(context)),
        *batch('source-read', 'RequestSourceAction', {}, {'observations': [
            {'status': 'success', 'content': [original]}]}),
        *batch('last', 'UpdateResearchStateAction', {}, {'accepted': True})]
    return messages, original


def test_projected_revision_routes_read_exact_actor_originals_without_mutating_archive():
    messages, original = fixture()
    before = deepcopy(messages)
    view = json.loads(working_view(messages)[0].content)
    location = view['current_context']['task_context']['revision_feedback'][0]['reference_navigation']['locations'][0]
    assert location['status'] == 'ambiguous'
    candidate, missing = location['candidates']
    args = candidate['saved_reads'][0]['arguments']
    action = ReadResearchHistoryAction.model_validate_json(json.dumps({'context_digest': 'x', **args}))
    assert action.tool_call_id == 'source-read' and action.index is None
    result = history_operation_page(public_operation(messages, action.tool_call_id), source_ids=action.source_ids)
    assert result['receipt']['result']['selected_materials'] == [original]
    assert missing['saved_reads'] == []
    assert missing['unlocated_source_ids'] == ['PASSAGE::WEB::missing']
    assert messages == before
    assert public_operation([], action.tool_call_id) is None


def test_navigation_only_or_failed_receipts_do_not_become_original_readbacks():
    messages, _ = fixture()
    messages[2].content = json.dumps({'result': {'content': [
        {'passage_id': 'PASSAGE::WEB::a', 'preview': 'Only a candidate'}]}})
    for status in ('success', 'error'):
        messages[2].status = status
        view = json.loads(working_view(messages)[0].content)
        candidate = view['current_context']['task_context']['revision_feedback'][0]['reference_navigation']['locations'][0]['candidates'][0]
        assert candidate['saved_reads'] == []


@pytest.mark.parametrize('extra', [{}, {'index': 1}])
def test_source_ids_alone_cannot_bypass_operation_locator(extra):
    with pytest.raises(ValueError, match='copy section=operation'):
        ReadResearchHistoryAction.model_validate_json(json.dumps(dict(context_digest='x', section='operation',
            source_ids=['PASSAGE::WEB::a'], reason_summary='Read original', **extra)))


def test_wire_schema_explains_conditional_fields():
    schema = convert_to_openai_tool(ReadResearchHistoryAction)['function']
    assert 'operation requires tool_call_id and forbids index' in schema['description']
    fields = schema['parameters']['properties']
    assert 'Cannot be used alone' in fields['source_ids']['description']
    assert 'Required for operation' in fields['tool_call_id']['description']
    assert 'cannot replace tool_call_id' in fields['index']['description']
