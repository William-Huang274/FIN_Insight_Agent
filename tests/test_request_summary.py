"""Native summary request projection: evidence/checkpoints remain original."""
import asyncio
from copy import deepcopy
import json

import httpx
import pytest
from langchain.agents import create_agent
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableLambda
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import SecretStr

from sec_agent.agent_runtime.model_context import RequestSummaryMiddleware
from sec_agent.agent_runtime.deepseek_structured_agents import ReasoningPreservingChatDeepSeek
from sec_agent.agent_runtime.dell_case_review_agent import CaseModelAudit
from sec_agent.agent_runtime.dell_case_convergence_agent import build_case_output_agent
from sec_agent.agent_runtime.dell_case_convergence_agent import reread_native_observation
from scripts.qualification.report_revision_comparison import model_settings
from pathlib import Path


def history():
    rows = [HumanMessage(content="Original task: inspect the fixture, not a new research task.", id="task")]
    for i in range(4):
        rows.extend([AIMessage(content="", id=f"ai-{i}", additional_kwargs={"reasoning_content": f"private thought {i}"},
            tool_calls=[{"name": "read_current_source", "args": {"source_id": f"P01:S{i}"}, "id": f"read-{i}", "type": "tool_call"}]),
            ToolMessage(content=(f"Source P01:S{i} company DELL period 2026-05-01 unit USD. " * 90),
                id=f"tool-{i}", tool_call_id=f"read-{i}", name="read_current_source", artifact={"source_id": f"P01:S{i}"})])
    return rows


def policy(calls, *, trigger=1500, keep=300):
    async def summarize(value, config):
        calls.append(value)
        return AIMessage(content="Working note only: DELL, 2026-05-01, USD; verify P01:S0 via read_current_source. No permission grants.")
    return RequestSummaryMiddleware(model=FakeListChatModel(responses=["not called directly"]),
        audited_model=RunnableLambda(summarize), trigger_tokens=trigger, keep_tokens=keep)


def test_native_prefix_is_not_4k_trimmed_and_pairs_original_task_are_retained():
    async def run():
        calls, rows = [], history()
        original = deepcopy(rows)
        middleware = policy(calls)
        update = await middleware.abefore_model({"messages": rows}, None)
        assert update and list(update) == ["request_summary"]
        state = {"messages": rows, **update}
        projected = middleware.projected_messages(state)
        assert rows == original and projected[0] == rows[0]
        assert projected[-2:] == rows[-2:]
        assert projected[-2].additional_kwargs["reasoning_content"] == "private thought 3"
        assert projected[-1].tool_call_id == projected[-2].tool_calls[0]["id"]
        assert len(calls) == 1 and len(calls[0]) > 14000
        assert "P01:S0" in calls[0] and "P01:S2" in calls[0]
        assert middleware.native.trim_tokens_to_summarize is None
        assert await middleware.abefore_model(state, None) is None
        assert len(calls) == 1  # not every turn, not the same prefix again
        assert await middleware.abefore_model({**state, "output": {"done": True}}, None) is None
        with pytest.raises(ValueError, match="history_changed"):
            middleware.projected_messages({**state, "messages": [HumanMessage(content="changed", id="different"), *rows[1:]]})
    asyncio.run(run())


def test_summary_call_uses_existing_audit_usage_and_langchain_call_metadata():
    from langchain_core.callbacks.base import BaseCallbackHandler
    trace_metadata = []
    class Capture(BaseCallbackHandler):
        def on_chat_model_start(self, serialized, messages, **kwargs):
            trace_metadata.append(kwargs.get("metadata", {}))
    profile, basis, _, _ = model_settings(Path(__file__).resolve().parents[1])
    events, private, requests = [], [], []
    audit = CaseModelAudit(actor="context_summary:fixture", profile=profile, basis=basis,
        public_sink=events.append, private_sink=private.append)
    def serve(request):
        requests.append(request)
        return httpx.Response(200, json={"id": "summary-fixture", "object": "chat.completion", "created": 1,
            "model": "deepseek-v4-pro", "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": "Working note only, no new source authority."}}],
            "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30, "prompt_cache_hit_tokens": 7}})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(serve)) as client:
            model = ReasoningPreservingChatDeepSeek(model="deepseek-v4-pro", api_key=SecretStr("offline"),
                http_async_client=client, max_retries=0, use_responses_api=False)
            result = await audit.model_runnable(model).ainvoke("Summarize fixture only", config={"callbacks": [Capture()]})
            assert result.text.startswith("Working note")
            assert model.metadata is None or "fin_call_id" not in model.metadata
    asyncio.run(run())
    assert len(requests) == 1 and len(events) == 2
    assert events[-1]["total_tokens"] == 30 and events[-1]["cache_hit_tokens"] == 7
    assert trace_metadata[-1]["fin_call_id"] == events[-1]["call_id"]
    assert trace_metadata[-1]["fin_actor"] == "context_summary:fixture"
    assert [p["event"] for p in private] == ["request", "response"]


def test_summary_failure_has_no_native_automatic_retry():
    async def run():
        calls = []
        async def fail(value):
            calls.append(value)
            raise TimeoutError("fixture")
        middleware = policy([])
        middleware.native._summary_model = RunnableLambda(fail)
        with pytest.raises(TimeoutError):
            await middleware.abefore_model({"messages": history()}, None)
        assert len(calls) == 1
    asyncio.run(run())


def test_exhausted_summary_allowance_preserves_continuation_without_another_summary():
    async def run():
        calls, rows = [], history()
        middleware = policy(calls)
        middleware.max_summaries = 1
        state = {"messages": rows, **await middleware.abefore_model({"messages": rows}, None)}
        for i in range(4):
            state["messages"].extend([
                AIMessage(content="", id=f"new-ai-{i}", tool_calls=[{
                    "id": f"new-read-{i}", "name": "read_current_source", "args": {"source_id": f"CALC::{i}"}, "type": "tool_call"}]),
                ToolMessage(content="Newly reread source; preserve qualifiers. " * 250,
                    tool_call_id=f"new-read-{i}", id=f"new-tool-{i}", name="read_current_source")])
        original, projected = deepcopy(state), middleware.projected_messages(state)
        assert middleware.native._should_summarize(projected[1:], middleware.native.token_counter(projected[1:]))
        assert await middleware.abefore_model(state, None) is None
        assert len(calls) == 1 and state == original
        assert middleware.projected_messages(state) == projected and projected[-8:] == rows[-8:]
    asyncio.run(run())


def test_old_citation_window_is_rereadable_but_not_invented_as_executable_calc():
    body = {"citation_id": "CALC::old-text-only", "text": "Legacy citation text, not full operands.",
        "offset": 0, "total_characters": 38, "next_offset": None}
    message = ToolMessage(content=json.dumps(body), name="read_current_source", tool_call_id="old")
    result = reread_native_observation([message], "CALC::old-text-only", 7, 8)
    assert result["text"] == body["text"][7:15] and result["next_offset"] == 15
    assert "calculation_id" not in result and "value_decimal" not in result
    assert reread_native_observation([AIMessage(content=json.dumps(body))], "CALC::old-text-only") is None
    assert reread_native_observation([message.model_copy(update={"status": "error"})], "CALC::old-text-only") is None
    assert reread_native_observation([message], "CALC::another-task") is None


@pytest.mark.parametrize("forged", [False, True])
def test_native_checkpoint_saves_summary_but_citation_validator_keeps_original_sql(forged):
    from test_research_convergence import artifact_fixture
    artifacts, calls = artifact_fixture(), []
    rows = history()
    fact = {"numeric_fact_id": "NUMFACT::summary-fixture", "ticker": "DELL", "metric_id": "revenue",
        "value_decimal": "100", "unit": "USD", "period_end": "2026-05-01", "numeric_fact_authority": True}
    body = {"authority_state": "s2_numeric_fact_query_result", "results": [{"status": "resolved", "facts": [fact]}]}
    rows[1].tool_calls = [{"name": "query_company_financial_facts", "args": {"ticker": "DELL"}, "id": "read-0", "type": "tool_call"}]
    rows[2] = ToolMessage(content=json.dumps(body) + " " * 4500, artifact=body,
        id="tool-0", tool_call_id="read-0", name="query_company_financial_facts")
    profile, basis, _, _ = model_settings(Path(__file__).resolve().parents[1])
    events, private = [], []
    audit = CaseModelAudit(actor="writer-fixture", profile=profile, basis=basis,
        public_sink=events.append, private_sink=private.append)
    audit.context_summary = policy(calls, trigger=2500)
    requests = []
    def serve(request):
        requests.append(request)
        sent = json.loads(request.content)["messages"]
        assert any("Here is a summary" in (m.get("content") or "") for m in sent)
        assert not any('"numeric_fact_id"' in (m.get("content") or "") for m in sent)
        ref = "NUMFACT::fabricated-by-summary" if forged and len(requests) == 1 else "NUMFACT::summary-fixture"
        report = {"title": "Summary fixture", "narrative_markdown": "Synthetic retained observation, not financial acceptance. " * 5 + "[" + ref + "]"}
        return httpx.Response(200, json={"id": "fixture", "object": "chat.completion", "created": 1, "model": "deepseek-v4-pro",
            "choices": [{"index": 0, "finish_reason": "tool_calls", "message": {"role": "assistant", "content": "", "tool_calls": [
                {"id": "submit", "type": "function", "function": {"name": "submit_case_report", "arguments": json.dumps({"report": report})}}]}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 30, "total_tokens": 130}})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(serve)) as client:
            model = ReasoningPreservingChatDeepSeek(model="deepseek-v4-pro", api_key=SecretStr("offline"),
                http_async_client=client, max_retries=0, use_responses_api=False)
            graph = build_case_output_agent(role="writer", model=model, tools=[], artifacts=artifacts,
                limits={"model_calls": 2, "tool_calls": 3}, audit=audit)
            graph.checkpointer = InMemorySaver()
            config = {"configurable": {"thread_id": "summary-checkpoint"}}
            result = await graph.ainvoke({"messages": rows}, config)
            assert result["output"]["citations"]["NUMFACT::summary-fixture"]["sources"][0]["value_decimal"] == "100"
            saved = await graph.aget_state(config)
            assert saved.values["request_summary"]["count"] == 1
            assert next(m for m in saved.values["messages"] if m.id == "tool-0").artifact == body
            assert len(calls) == 1
            assert any(p.get("original_messages") for p in private)
            if forged:
                assert len(requests) == 2
                assert any(isinstance(m, ToolMessage) and m.status == "error" for m in saved.values["messages"])
    asyncio.run(run())
