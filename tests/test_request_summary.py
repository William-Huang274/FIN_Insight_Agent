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


def test_rolling_summary_requires_new_user_turn_and_keeps_original_history():
    async def run():
        calls=[]
        middleware=policy(calls,trigger=500,keep=100)
        middleware.per_user_turn=True
        rows=history()
        rows.extend([AIMessage(content='Already completed original research. '*200,id='answer'),
                     HumanMessage(content='Cancel attribution; observations only.',id='correction')])
        original=deepcopy(rows)
        update=await middleware.abefore_model({'messages':rows},None)
        assert update['request_summary']['last_summary_user_id']=='correction'
        state={'messages':rows,**update}
        assert await middleware.abefore_model(state,None) is None
        assert len(calls)==1 and rows==original
        rows.extend([AIMessage(content='Observed only, no revived plan. '*200,id='answer2'),
                     HumanMessage(content='Continue with the source index only.',id='next-user')])
        update2=await middleware.abefore_model(state,None)
        assert update2['request_summary']['count']==2 and len(calls)==2
        projected=middleware.projected_messages({'messages':rows,**update2})
        assert projected[0]==original[0] and projected[-1]==rows[-1]
    asyncio.run(run())


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




def test_summary_failure_has_no_native_automatic_retry():
    async def run():
        calls = []
        async def fail(value):
            calls.append(value)
            raise TimeoutError("fixture")
        middleware = policy([])
        middleware.native._summary_model = RunnableLambda(fail)
        state={"messages": history()}
        original=deepcopy(state)
        state.update(await middleware.abefore_model(state,None))
        assert state["request_summary_failure"]["automatic_retry"] is False
        assert state["messages"]==original["messages"]
        assert await middleware.abefore_model(state,None) is None
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
