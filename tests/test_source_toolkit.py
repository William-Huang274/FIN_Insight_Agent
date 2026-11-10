import asyncio
import json
from uuid import uuid4

from sec_agent.agent_runtime.source_toolkit import source_tools, source_catalog, CAPABILITIES
from sec_agent.agent_runtime.conversation_agent import research_system_prompt
from sec_agent.agent_runtime.answer_review_provider import review_tool_names
from sec_agent.agent_runtime.conversation_tools import SAVED_RESULT_TOOLS
from sec_agent.agent_runtime.harness_business_tools import model_receipt
from langchain_core.messages import ToolMessage


def test_single_factory_preserves_native_contracts_and_paths(tmp_path, monkeypatch):
    for name in ('FIN_AKTOOLS_MCP_URL', 'HITHINK_FINANCE_API_KEY', 'OPENDART_API_KEY'):
        monkeypatch.delenv(name, raising=False)
    grants = source_tools(thread_id=str(uuid4()), run_id=str(uuid4()),
                          method_digest='a'*64, cache_root=tmp_path, research_as_of='2026-06-30')
    names = [g.tool.name for g in grants]
    assert len(names) == len(set(names)) == 5
    assert 'discover_source_tools' in names
    assert set(names) <= set(review_tool_names(names))
    assert set(names) <= SAVED_RESULT_TOOLS
    async def read():
        _, result = await grants[0].tool.coroutine()
        by_name = {v['tool']: v for v in result['tools']}
        assert by_name['query_hithink']['configured'] is False
        assert by_name['read_public_source']['configured'] is True
        assert set(by_name) == set(CAPABILITIES)
        _, unavailable = await grants[0].tool.coroutine(tool_name='query_hithink')
        assert unavailable['status'] == 'unavailable_tool'
        _, schema = await grants[0].tool.coroutine(tool_name='read_public_source')
        original = next(g.tool for g in grants if g.tool.name == 'read_public_source')
        assert schema['input_schema'] == original.tool_call_schema.model_json_schema()
        assert 'search_language' in schema['input_schema']['properties']
        projected = model_receipt(ToolMessage(content=json.dumps(schema),
            name='discover_source_tools', tool_call_id='catalog-schema'))
        assert projected['result']['input_schema'] == schema['input_schema']
    asyncio.run(read())
    prompt = research_system_prompt(names)
    assert 'discover_source_tools' in prompt and '同一个研究 MCP' in prompt
    assert 'query_hithink' not in prompt


def test_configured_native_domains_and_catalog_grouping(tmp_path, monkeypatch):
    monkeypatch.setenv('HITHINK_FINANCE_API_KEY', 'test')
    monkeypatch.setenv('OPENDART_API_KEY', 'test')
    monkeypatch.setenv('FIN_AKTOOLS_MCP_URL', 'http://127.0.0.1:22847/mcp')
    grants = source_tools(thread_id=str(uuid4()), run_id=str(uuid4()),
                          method_digest='a'*64, cache_root=tmp_path)
    assert set(g.tool.name for g in grants) == set(CAPABILITIES) | {'discover_source_tools'}
    _, data = asyncio.run(grants[0].tool.coroutine(group='data'))
    assert all(r['configured'] and r['group'] == 'data' for r in data['tools'])
    assert len(data['tools']) == 3
