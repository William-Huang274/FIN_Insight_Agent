import asyncio
import json
from uuid import uuid4

from sec_agent.agent_runtime.conversation_web import public_web_tool
from sec_agent.research_foundation.external_sources import ConversationSourceScope
from test_dell_web_source_navigation import _reader


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
