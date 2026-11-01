import json
from copy import deepcopy
from types import SimpleNamespace

import pytest
from langchain_core.tools import tool
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from sec_agent.agent_runtime.conversation_agent import GrantedTool
from sec_agent.agent_runtime.conversation_tools import conversation_tools
from sec_agent.agent_runtime.harness_business_tools import HarnessBusinessTools
from sec_agent.agent_runtime.source_result_view import source_result_view


@pytest.fixture
def anyio_backend():
    return 'asyncio'


@pytest.mark.anyio
async def test_native_text_lane_has_receipt_and_preserves_canonical_readback(tmp_path):
    identity = {'digest': 'source-revision', 'source_truncated': True, 'capture': 'provenance ' * 200}
    raw = {'operation': 'outline', 'read_only': True, 'source_snapshot_sha256': 'snapshot',
           'items': [{'node_id': str(i), 'organization_source': identity, 'writer_citable': False,
                      'readback': {'operation': 'read', 'node_id': str(i)}} for i in range(20)]}
    @tool(response_format='content_and_artifact')
    def read_source_document():
        """Synthetic directory, not source truth."""
        return json.dumps(raw), raw
    grants = [GrantedTool(read_source_document, 'read', 'fixture')]
    grants += [g for g in conversation_tools(thread_id='t') if g.tool.name == 'read_saved_result']
    async with AsyncSqliteSaver.from_conn_string(str(tmp_path / 'tools.sqlite')) as saver:
        bridge = HarnessBusinessTools(grants=grants, checkpointer=saver, thread_id='t', check=lambda: None)
        await bridge.initialize({'messages': []})
        response = await bridge.call_tool(None, SimpleNamespace(name='read_source_document', arguments={}))
        # The upstream client uses content text only, not structured_content.
        view = json.loads(response.content[0].text)
        key = view['original_readback']['arguments']['tool_call_id']
        assert key == view['receipt_id'] and len(response.content[0].text) < len(json.dumps(raw)) / 3
        saved = (await bridge.state())['messages'][-1]
        assert json.loads(saved.content) == saved.artifact == raw
        restored = await bridge.execute('read_saved_result', {'tool_call_id': key, 'json_pointer': '/items/3/organization_source'})
        assert json.loads(json.loads(restored.content)['content']) == identity


def test_shared_original_fields_are_lossless_and_never_merge_period_conflicts():
    common = {'source_digest': 'a' * 64, 'source_url': 'https://source.invalid/' * 20,
              'complete_original_document': False}
    raw = {'operation': 'search', 'read_only': True, 'source_snapshot_sha256': 'a',
           'items': [{'document_id': 'D', 'original_source': {**common, 'char_start': i, 'period': str(i)}} for i in range(3)]}
    old = deepcopy(raw)
    view = source_result_view(raw)
    import jsonpointer
    for actual, expected in zip(view['items'], raw['items']):
        recovered = {**jsonpointer.resolve_pointer(view, actual['original_source_ref'][1:]), **actual['original_source']}
        assert recovered == expected['original_source']
        assert actual['original_source']['period'] == expected['original_source']['period']
    assert raw == old and source_result_view(view) == view


@pytest.mark.anyio
async def test_report_draft_and_exact_field_windows_are_available_without_accepting(tmp_path):
    from sec_agent.agent_runtime.harness_artifact_tools import artifact_tools
    from test_on_demand_research import artifact_fixture, report
    artifacts = artifact_fixture()
    candidate = {k: v for k, v in report(artifacts).items() if k != 'citations'}
    grants = artifact_tools(artifacts=lambda _: artifacts, memory=None, delivery_intent='answer', require_review=False)
    assert not {'deliver_current_report', 'deliver_working_note'} & {g.tool.name for g in grants}
    async with AsyncSqliteSaver.from_conn_string(str(tmp_path / 'tools.sqlite')) as saver:
        bridge = HarnessBusinessTools(grants=grants, checkpointer=saver, thread_id='t', check=lambda: None)
        await bridge.initialize({'messages': []})
        rejected = await bridge.execute('save_research_report', {'report': {**candidate, 'title': 'x'}, 'base_version': 0})
        assert rejected.status == 'error'
        draft = json.loads((await bridge.execute('read_current_report', {'view': 'draft'})).content)
        assert not draft['accepted'] and draft['base_version'] == 0
        assert draft['text'] == candidate['narrative_markdown']
        assert not (await bridge.state()).get('delivery') and not (await bridge.state()).get('report')
        saved = await bridge.execute('repair_report_fields', {'fields': {'title': candidate['title']}, 'base_version': 0})
        assert saved.status == 'success'
        read = json.loads((await bridge.execute('read_current_report', {'offset': 4, 'max_characters': 31})).content)
        assert read['text'] == candidate['narrative_markdown'][4:35] and read['base_version'] == 1
        assert json.loads((await bridge.execute('read_current_report', {'view': 'draft'})).content)['found'] is False


def test_small_explicit_read_windows_are_admitted_and_source_replies_discoverable():
    from langchain_core.messages import ToolMessage
    from sec_agent.agent_runtime.context_records import browse_checkpoint
    from sec_agent.research_foundation.organization_source_request import OrganizationSourceRequest
    request = OrganizationSourceRequest(operation='read', document_id='DOC::one', node_id='NODE::one', max_characters=500, character_offset=0)
    assert request.max_characters == 500
    with pytest.raises(ValueError):
        OrganizationSourceRequest(operation='read', max_characters=0)
    view = browse_checkpoint([ToolMessage(content='original', name='read_research_source', tool_call_id='saved')], 'sources')
    assert view['items'][0]['key'] == 'saved' and view['items'][0]['read_tool'] == 'read_saved_result'


def test_calculation_factoring_keeps_operands_and_conflicting_provenance():
    from sec_agent.agent_runtime.harness_business_tools import model_receipt
    from langchain_core.messages import ToolMessage
    provenance = {'period': '2026', 'unit': 'USD million', 'source_truncated': True}
    raw = {'calculation_id': 'CALC::one', 'expression': 'a / b', 'result_state': 'non_authoritative_metric',
           'operands': {'a': {'source_id': 'S', 'value_decimal': '20', 'quote': '20 | 10', 'source_provenance': provenance},
                        'b': {'source_id': 'S', 'value_decimal': '10', 'quote': '20 | 10', 'source_provenance': provenance}},
           'value_decimal': '2', 'result_unit': 'ratio', 'financial_semantics_verified': False}
    view = model_receipt(ToolMessage(content=json.dumps(raw), name='calculate_research_metric', tool_call_id='t'))['result']
    import jsonpointer
    for k, operand in view['operands'].items():
        recovered = {key: value for key, value in operand.items() if key != 'source_provenance_ref'}
        recovered['source_provenance'] = jsonpointer.resolve_pointer(view, operand['source_provenance_ref'][1:])
        assert recovered == raw['operands'][k]
    assert view['value_decimal'] == '2' and not view['financial_semantics_verified']
    raw['operands']['b']['source_provenance'] = {**provenance, 'period': '2025'}
    assert 'shared_source_provenance' not in source_result_view(raw)
