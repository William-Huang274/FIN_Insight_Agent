"""Offline SDK projection and native-state evidence retention, not quality A/B."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path

import httpx
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import SecretStr

from sec_agent.agent_runtime.deepseek_structured_agents import DeepSeekStructuredAgentAdapter, ReasoningPreservingChatDeepSeek, load_deepseek_structured_agent_config
from sec_agent.agent_runtime.dell_case_convergence_agent import build_case_output_agent
from sec_agent.agent_runtime.dell_case_review_agent import case_chat_model
from sec_agent.agent_runtime.model_context import project_tool_history
from sec_agent.agent_runtime.research_session_runtime import load_research_runtime_profile


def history():
    rows = [HumanMessage(content="Synthetic source and protocol retention fixture.")]
    for i, name in enumerate(("read_source_document", "calculate_research_metric", "get_research_method", "query_company_financial_facts", "read_current_workpaper")):
        rows.append(AIMessage(content="", additional_kwargs={"reasoning_content": f"private reasoning {i}"},
            tool_calls=[{"name": name, "args": {"source_id": f"fixture-{i}"}, "id": f"read-{i}", "type": "tool_call"}]))
        rows.append(ToolMessage(name=name, tool_call_id=f"read-{i}", content=(f"original result {i} " * 100),
            artifact={"source": i}, status="error" if i == 3 else "success"))
    return rows


def test_native_edit_only_changes_request_copy_and_retains_errors_methods_calculations():
    rows = history()
    before = deepcopy(rows)
    projected = project_tool_history(rows, trigger_tokens=1, keep=1)
    assert rows == before
    assert [m.tool_call_id for m in projected if isinstance(m, ToolMessage)] == [f"read-{i}" for i in range(5)]
    assert projected[2].response_metadata["context_editing"]["cleared"] and projected[2].artifact is None
    assert projected[4:] == rows[4:]
    assert [m for m in projected if isinstance(m, AIMessage)] == [m for m in rows if isinstance(m, AIMessage)]
    assert project_tool_history(rows) is rows


def test_current_runtime_supplies_same_policy_to_legacy_and_native_model_factories():
    profile, _ = load_research_runtime_profile(Path(__file__).resolve().parents[1])
    base = load_deepseek_structured_agent_config(profile["model_config"])
    base = base.model_copy(update={"agentic_message_history": True})
    adapter = DeepSeekStructuredAgentAdapter.from_config(config=base, api_key=SecretStr("offline-fixture"), context_editing=profile["context_editing"])
    native = case_chat_model(base.profile_for("specialist"), base.token_budget_basis["specialist"], base, SecretStr("offline-fixture"), context_editing=profile["context_editing"])
    for model in [*adapter._chat_models.values(), native]:
        assert model.tool_context_trigger_tokens == 50000 and model.tool_context_keep == 6
        assert "tool_context_trigger_tokens" not in model.model_dump()


def test_sync_and_async_sdk_wire_clears_read_bodies_not_reasoning_or_tool_pairs():
    rows, requests = history(), []
    original = deepcopy(rows)
    def serve(request):
        body = json.loads(request.content)
        requests.append(body)
        assert "tool_context_trigger_tokens" not in body and "tool_context_keep" not in body
        sent = body["messages"]
        assert "Older read result omitted" in sent[2]["content"]
        for index in range(5):
            assert sent[1 + 2 * index]["reasoning_content"] == f"private reasoning {index}"
            assert sent[2 + 2 * index]["tool_call_id"] == f"read-{index}"
        return httpx.Response(200, json={"id": "offline-response", "object": "chat.completion", "created": 1,
            "model": "deepseek-v4-pro", "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": "fixture only"}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110}})
    with httpx.Client(transport=httpx.MockTransport(serve)) as client:
        model = ReasoningPreservingChatDeepSeek(model="deepseek-v4-pro", api_key=SecretStr("offline-fixture"),
            http_client=client, max_retries=0, use_responses_api=False, tool_context_trigger_tokens=1, tool_context_keep=1)
        assert model.invoke(rows).usage_metadata["total_tokens"] == 110
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(serve)) as client:
            model = ReasoningPreservingChatDeepSeek(model="deepseek-v4-pro", api_key=SecretStr("offline-fixture"),
                http_async_client=client, max_retries=0, use_responses_api=False, tool_context_trigger_tokens=1, tool_context_keep=1)
            assert (await model.ainvoke(rows)).usage_metadata["total_tokens"] == 110
    asyncio.run(run())
    assert len(requests) == 2 and rows == original


def test_native_checkpoint_and_citation_validation_retain_cleared_sql_observation():
    from test_research_convergence import artifact_fixture
    artifacts = artifact_fixture()
    fact = {"numeric_fact_id": "NUMFACT::fixture", "ticker": "DELL", "metric_id": "revenue", "value_decimal": "100",
        "unit": "USD", "period_end": "2026-05-01", "numeric_fact_authority": True}
    body = {"authority_state": "s2_numeric_fact_query_result", "results": [{"status": "resolved", "facts": [fact]}]}
    rows = [HumanMessage(content="Use the observed SQL fixture without new research."),
        AIMessage(content="", additional_kwargs={"reasoning_content": "private SQL rationale"}, tool_calls=[
            {"name": "query_company_financial_facts", "args": {"ticker": "DELL"}, "id": "sql", "type": "tool_call"}]),
        ToolMessage(name="query_company_financial_facts", tool_call_id="sql", content=json.dumps(body), artifact=deepcopy(body)),
        AIMessage(content="", tool_calls=[{"name": "get_research_method", "args": {"method_id": "writer"}, "id": "method", "type": "tool_call"}]),
        ToolMessage(name="get_research_method", tool_call_id="method", content="Synthetic writer method, not an answer.")]
    original = deepcopy(rows)
    def serve(request):
        sent = json.loads(request.content)["messages"]
        assert any("Older read result omitted" in m.get("content", "") for m in sent if m["role"] == "tool")
        report = {"title": "Cited fixture report", "narrative_markdown": "Synthetic numeric observation binding, not financial-quality evidence. " * 4 + "[NUMFACT::fixture]"}
        return httpx.Response(200, json={"id": "offline-native", "object": "chat.completion", "created": 1, "model": "deepseek-v4-pro",
            "choices": [{"index": 0, "finish_reason": "tool_calls", "message": {"role": "assistant", "content": "", "tool_calls": [
                {"id": "submit", "type": "function", "function": {"name": "submit_case_report", "arguments": json.dumps({"report": report})}}]}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 30, "total_tokens": 130}})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(serve)) as client:
            model = ReasoningPreservingChatDeepSeek(model="deepseek-v4-pro", api_key=SecretStr("offline-fixture"),
                http_async_client=client, max_retries=0, use_responses_api=False, tool_context_trigger_tokens=1, tool_context_keep=1)
            agent = build_case_output_agent(role="writer", model=model, tools=[], artifacts=artifacts, limits={"model_calls": 2, "tool_calls": 3})
            agent.checkpointer = InMemorySaver()
            cfg = {"configurable": {"thread_id": "context-fixture"}}
            result = await agent.ainvoke({"messages": rows}, cfg)
            assert result["output"]["citations"]["NUMFACT::fixture"]["sources"][0]["value_decimal"] == "100"
            saved = await agent.aget_state(cfg)
            observed = next(m for m in saved.values["messages"] if isinstance(m, ToolMessage) and m.tool_call_id == "sql")
            assert observed.artifact == body and observed.content == json.dumps(body)
    asyncio.run(run())
    assert all(a.content == b.content for a, b in zip(rows, original))
