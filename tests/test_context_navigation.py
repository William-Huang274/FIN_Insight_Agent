"""Adversarial retrieval and real checkpoint tests; no model-quality claim."""
import asyncio
from copy import deepcopy
import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from sec_agent.agent_runtime.context_navigation import browse_checkpoint, public_text
from sec_agent.agent_runtime.conversation_agent import build_conversation_agent
from sec_agent.agent_runtime.conversation_tools import conversation_tools
from sec_agent.agent_runtime.model_context import RequestSummaryMiddleware
from test_conversation_agent import ScriptedTools


def retained_history():
    return [HumanMessage(id="task", content="Compare Acme CFO across FY2024 and FY2025."),
        AIMessage(id="query", content="", tool_calls=[{"name": "query_financial_data",
            "args": {"ticker": "ACME", "metric_id": "operating_cash_flow", "fiscal_years": [2024, 2025]},
            "id": "opaque-7a", "type": "tool_call"}]),
        ToolMessage(id="receipt", name="query_financial_data", tool_call_id="opaque-7a",
            content='{"FY2024":100,"FY2025":80,"unit":"USD million","metric":"CFO"}'),
        HumanMessage(id="correction", content="Correction: compare CFO, not cash balances. Do not rerun the completed query."),
        AIMessage(id="old-prose", content="Old unsupported interpretation: cash decreased."),
        HumanMessage(id="continue", content="Continue from the saved result.")]


def test_live_qualification_only_advertises_the_three_budgeted_readers():
    from scripts.qualification.context_navigation_roundtrip import recovery_grants
    assert {g.tool.name for g in recovery_grants("fixture")} == {
        "browse_context", "read_context_turn", "read_saved_result"}


def summary_record(rows, end=5):
    return {"prefix_end": end, "first_original_id": rows[0].id, "last_original_id": rows[end-1].id,
            "count": 1, "message": HumanMessage(content="Lossy summary: cash fell; numbers omitted.").model_dump(mode="json")}


def test_regions_keys_failures_and_literal_fallback():
    rows = retained_history()
    rows.append(ToolMessage(name="read_public_source", tool_call_id="source", content="CFO prose"))
    rows.append(ToolMessage(name="query_financial_data", tool_call_id="failed", content="SQL unavailable", status="error"))
    numbers = browse_checkpoint(rows, "numbers", "ACME")["items"]
    assert [r["key"] for r in numbers] == ["opaque-7a"]
    assert numbers[0]["read_tool"] == "read_saved_result"
    assert browse_checkpoint(rows, "sources")["items"][0]["key"] == "source"
    assert all(r["region"] == "conversation" for r in browse_checkpoint(rows, "conversation")["items"])
    assert browse_checkpoint(rows, "numbers", "经营现金流")["total_matches"] == 0
    # An alias miss has an explicit blank-browse fallback; no semantic claim.
    failed = browse_checkpoint(rows, "numbers")["items"][0]
    assert failed["status"] == "error" and failed["read_tool"] is None


def test_old_index_pagination_and_no_reasoning_export():
    rows = [HumanMessage(id=str(i), content=f"turn {i}") for i in range(27)]
    assert browse_checkpoint(rows, "conversation")["next_offset"] == 12
    assert [r["key"] for r in browse_checkpoint(rows, "conversation", offset=24)["items"]] == ["2", "1", "0"]
    msg = AIMessage(content=[{"type": "reasoning", "reasoning": "private"}, {"type": "text", "text": "public"}],
                    additional_kwargs={"reasoning_content": "private"})
    assert public_text(msg) == "public"


def test_metadata_search_does_not_lose_keys_beyond_display_preview():
    rows = [AIMessage(content="", tool_calls=[{"name":"query_financial_data", "id":"long-args",
        "args":{"description":"x" * 700,"ticker":"OMEGA","fiscal_years":[2023]}}]),
        ToolMessage(name="query_financial_data",tool_call_id="long-args",content="retained")]
    assert browse_checkpoint(rows,"numbers","OMEGA")["items"][0]["key"] == "long-args"


def test_lossy_summary_cannot_replace_latest_omitted_user_correction():
    rows = retained_history()
    state = {"messages": rows, "request_summary": summary_record(rows)}
    original = deepcopy(state)
    projected = RequestSummaryMiddleware.projected_messages(state)
    assert projected[-2] == rows[3]
    assert rows[2] not in projected
    assert RequestSummaryMiddleware.projected_messages(state, pin_user=False)[-1] == rows[-1]
    assert state == original
    state["messages"][4] = AIMessage(id="replacement", content="changed")
    with pytest.raises(ValueError, match="history_changed"):
        RequestSummaryMiddleware.projected_messages(state)


def test_compacted_checkpoint_reopens_and_tools_retrieve_original_not_summary(tmp_path):
    async def run():
        path = str(tmp_path / "checkpoint.sqlite")
        config = {"configurable": {"thread_id": "one"}}
        rows = retained_history()
        async with AsyncSqliteSaver.from_conn_string(path) as saver:
            initial = build_conversation_agent(model=ScriptedTools(responses=[AIMessage(content="saved")]),
                grants=conversation_tools(thread_id="one"), permission_mode="request_standard", checkpointer=saver)
            await initial.ainvoke({"messages": rows}, config)
        responses = [AIMessage(content="", tool_calls=[{"name":"browse_context", "args":{"region":"numbers"}, "id":"browse"}]),
            AIMessage(content="", tool_calls=[{"name":"read_saved_result", "args":{"tool_call_id":"opaque-7a"}, "id":"read"}]),
            AIMessage(content="Recovered original CFO observation.")]
        # Use the real request projection but prohibit a new summarizer call.
        from langchain_core.runnables import RunnableLambda
        model = ScriptedTools(responses=responses)
        middleware = RequestSummaryMiddleware(model=model, audited_model=RunnableLambda(lambda _: "unused"),
            trigger_tokens=10000, keep_tokens=1000)
        async with AsyncSqliteSaver.from_conn_string(path) as saver:
            graph = build_conversation_agent(model=model, grants=conversation_tools(thread_id="one"),
                permission_mode="request_standard", checkpointer=saver, middleware=[middleware])
            result = await graph.ainvoke({"request_summary": summary_record(rows)}, config)
            recovered = next(m for m in result["messages"] if isinstance(m, ToolMessage) and m.tool_call_id == "read")
            body = json.loads(recovered.content)
            assert body["content"] == rows[2].content and body["new_tool_dispatch"] is False
            assert any(m.id == "receipt" and m.content == rows[2].content for m in result["messages"])
            other = await graph.aget_state({"configurable":{"thread_id":"other"}})
            assert not other.values
    asyncio.run(run())


def test_repeat_native_compaction_retains_boundary_and_latest_correction():
    async def run():
        from langchain_core.runnables import RunnableLambda
        model = ScriptedTools(responses=[AIMessage(content="unused")])
        summaries = []
        def summarize(_):
            summaries.append(1)
            return AIMessage(content="Deliberately lossy abstract.")
        middleware = RequestSummaryMiddleware(model=model, audited_model=RunnableLambda(summarize),
            trigger_tokens=450, keep_tokens=150, max_summaries=2)
        rows = [HumanMessage(id="start", content="Keep this original task.")]
        for i in range(16):
            cls = HumanMessage if i % 4 == 0 else AIMessage
            rows.append(cls(id=f"m{i}", content=(f"Original {i} " * 100)))
        state = {"messages": rows}
        for attempt in range(2):
            update = await middleware.abefore_model(state, None)
            assert update
            state.update(update)
            projected = middleware.projected_messages(state)
            end = state["request_summary"]["prefix_end"]
            latest = next(m for m in reversed(rows[1:end]) if isinstance(m, HumanMessage))
            assert latest in projected and projected[-1] == rows[-1]
            if attempt == 0:
                rows.extend([HumanMessage(id="new-correction", content="Cancel the old plan. " * 100),
                    AIMessage(id="new-work", content="New progress " * 200), AIMessage(id="tail", content="Pending next step.")])
        assert len(summaries) == 2
        assert any(m.id == "m0" for m in state["messages"])
    asyncio.run(run())
