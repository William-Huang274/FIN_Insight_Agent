import asyncio
import json
from types import SimpleNamespace
from uuid import uuid4

from sec_agent.agent_runtime.conversation_web import public_web_tool
from sec_agent.research_foundation.external_sources import ConversationSourceScope
from test_web_source_navigation import _reader


def test_public_web_restores_discovery_between_runs_and_uses_task_cutoff(tmp_path):
    from langchain_core.messages import ToolMessage
    tid = str(uuid4())
    first, _, _ = _reader()
    second, _, text = _reader()
    a = public_web_tool(thread_id=tid, run_id=str(uuid4()), method_digest='a'*64,
        cache_root=tmp_path, reader=first, research_as_of='2026-09-23').tool
    b = public_web_tool(thread_id=tid, run_id=str(uuid4()), method_digest='a'*64,
        cache_root=tmp_path, reader=second, research_as_of='2026-09-23').tool
    async def check():
        visible, artifact = await a.coroutine(operation='search', query='public filing')
        assert '2026-09-23' in json.loads(visible)['search_coverage']['research_as_of']
        assert 'web_navigation_receipts' not in json.loads(visible)
        doc = json.loads(visible)['items'][0]['document_id']
        runtime = SimpleNamespace(state={'messages': [ToolMessage(name='read_public_source',
            tool_call_id='search', content=visible, artifact=artifact)]})
        read, _ = await b.coroutine(operation='read', document_id=doc, max_characters=1000, runtime=runtime)
        assert json.loads(read)['items'][0]['passage'] == text[:1000]
        assert next(iter(second._candidates.values()))[0].research_as_of.startswith('2026-09-23')
    asyncio.run(check())


def test_general_web_reuses_readers_without_claiming_financial_review(tmp_path):
    reader,fetcher,text=_reader()
    grant=public_web_tool(thread_id=str(uuid4()),run_id=str(uuid4()),method_digest="a"*64,
        cache_root=tmp_path,reader=reader)
    async def run():
        search=json.loads(await grant.tool.ainvoke({"operation":"search","query":"official HTTP caching"}))
        item=search["items"][0]
        assert item["result_state"]=="retrieval_candidate" and not item["writer_citable"]
        read=json.loads(await grant.tool.ainvoke({"operation":"read","document_id":item["document_id"],"max_characters":2000}))
        ambiguous=await grant.tool.ainvoke({"operation":"read","document_id":item["document_id"],"query":"ignored search"})
        assert "Use operation=search" in ambiguous
        assert read["items"][0]["passage"]==text[:2000]
        assert not read["items"][0]["numeric_fact_authority"]
        assert read["evidence_admission_performed"] is False
        within=json.loads(await grant.tool.ainvoke({"operation":"search","document_id":item["document_id"],"query":"source fixture"}))
        assert within["items"] and all(hit["writer_citable"] for hit in within["items"])
        start=within["items"][0]["source_locator"]["character_start"]
        for hit in within["items"]:
            locator=hit["source_locator"]
            assert hit["passage"]==text.strip()[locator["character_start"]:locator["character_end"]]
        from sec_agent.research_foundation.source_bound_calculator import source_items_from_tool
        assert len(source_items_from_tool("read_source_document",within))==len(within["items"])
        selected=json.loads(await grant.tool.ainvoke({"operation":"read","document_id":item["document_id"],"offset":start,"max_characters":2000}))
        assert selected["items"][0]["passage"]==text.strip()[start:start+2000]
        denied=await grant.tool.ainvoke({"operation":"read","document_id":"WEB::another-thread"})
        assert "not_discovered" in denied
        scope=next(iter(reader._candidates.values()))[0]
        assert scope.case_id and scope.data_snapshot_id=="conversation-public-sources-v1"
    asyncio.run(run())
    assert len(fetcher.calls)==1


def test_search_feedback_is_specific_and_the_method_is_callable():
    from sec_agent.agent_runtime.conversation_web import web_read_feedback
    from sec_agent.research_foundation.research_methods import get_research_method
    def feedback(*attempts, items=()):
        return web_read_feedback({'items':items,'execution_receipt':{'attempts':list(attempts)}})
    mixed = {'date_filter_counts':{'after_cutoff':3,'origin_403':2}}
    date_hint, denied = feedback(mixed)
    assert date_hint['count'] == 3
    assert get_research_method(**date_hint['method_readback']['arguments'])['selection'] == '数据版本与当前研究入口'
    assert denied['kind'] == 'origin_403' and 'method_readback' not in denied
    assert feedback({'failure_code':'capture_http_status_403'}) == [denied]
    assert feedback(mixed, items=[{'document_id':'ok'}]) == []
    assert feedback({}) == []
    reasons = feedback({'failure_code':'exa_mcp_rate_limited'}, {'failure_code':'ddgs_reported_no_results'})
    assert [r['kind'] for r in reasons] == ['search_rate_limited','fallback_empty']
    assert all('method_readback' not in r for r in reasons)
