"""Offline native-input and MCP evidence, not a financial-quality evaluation."""
import asyncio
import json
from hashlib import sha256

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from mcp import Client

from sec_agent.research_foundation.research_methods import (
    BASIC_RESEARCH_GUIDANCE, FIRST_METHODS, get_research_method, select_method_section,
)
from sec_agent.agent_runtime.conversation_agent import build_conversation_agent
from sec_agent.agent_runtime.conversation_tools import conversation_tools
from test_conversation_agent import ScriptedTools
from test_research_mcp import _build_server


class CaptureInputs(ScriptedTools):
    seen: list = []

    def _generate(self, messages, *args, **kwargs):
        self.seen.append(list(messages))
        return super()._generate(messages, *args, **kwargs)


@pytest.mark.parametrize("method_id", FIRST_METHODS)
def test_each_method_reaches_native_model_and_can_resume_without_duplicate_guidance(method_id):
    resource = get_research_method(method_id)
    section = resource["sections"][1]
    response = get_research_method(method_id, section)
    model = CaptureInputs(responses=[
        AIMessage(content="", tool_calls=[{"name": "get_research_method",
            "args": {"method_id": method_id, "section": section}, "id": "method-1", "type": "tool_call"}]),
        AIMessage(content="Synthetic teaching read, no research claim."),
        AIMessage(content="Synthetic follow-up, existing observations retained.")])
    grants = [g for g in conversation_tools(thread_id="teaching") if g.tool.name == "get_research_method"]
    agent = build_conversation_agent(model=model, grants=grants,
        permission_mode="request_standard", checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": method_id}}
    agent.invoke({"messages": [HumanMessage(content="Read the relevant method chapter.")]}, config)
    agent.invoke({"messages": [HumanMessage(content="Continue from the chapter just read.")]}, config)
    assert len(model.seen) == 3
    for messages in model.seen:
        prompt = str(messages[0].content)
        assert prompt.count(BASIC_RESEARCH_GUIDANCE.strip()) == 1
        assert "scenario_sensitivity：" in prompt
        assert "Before the first substantive financial judgment" not in prompt
        assert "first call get_research_method" not in prompt
    receipt = next(m for m in model.seen[1] if isinstance(m, ToolMessage))
    value = json.loads(receipt.content)
    assert value["content"] == response["content"]
    assert value["resource_digest"] == sha256(resource["content"].encode()).hexdigest()
    assert value["content_digest"] == sha256(value["content"].encode()).hexdigest()
    assert value["grants_authority"] is False
    assert any(isinstance(m, ToolMessage) and m.content == receipt.content for m in model.seen[2])


def test_mcp_section_selection_and_compatibility_alias_have_one_source():
    async def run():
        async with Client(_build_server(), raise_exceptions=False) as client:
            catalog = (await client.call_tool("get_research_method", {})).structured_content
            for key in FIRST_METHODS:
                row = next(r for r in catalog["methods"] if r["method_id"] == key)
                chapter = await client.call_tool("get_research_method", {"method_id": key, "section": row["sections"][0]})
                assert not chapter.is_error
                assert chapter.structured_content == get_research_method(key, row["sections"][0])
            bad = await client.call_tool("get_research_method", {"method_id": "finance", "section": "../../.env"})
            assert bad.is_error
    asyncio.run(run())
    assert get_research_method("finance", "财务质量与日期桥接")["content"] in get_research_method("financial_quality")["content"]


def test_frozen_custom_method_selection_never_substitutes_current_packaged_content():
    custom = {"method_id": "finance", "content": "# Frozen\n## Own chapter\nHistorical text\n",
              "grants_authority": False, "answer_free": True, "content_version": 91}
    projected = select_method_section(custom, "Own chapter")
    assert projected["content_version"] == 91 and "Historical text" in projected["content"]
    assert custom.get("selection") is None
    with pytest.raises(ValueError, match="unknown_method_section"):
        select_method_section(custom, "利润桥与现金桥例题")


def test_worked_examples_are_arithmetically_consistent():
    assert [100*u*(p-.6)-50 for u,p in [(.5,2),(.7,2),(.7,1.4)]] == pytest.approx([20,48,6])
    assert 50/(100*(2-.6)) == pytest.approx(.357142857)
    assert (20+50)/(100*(1.4-.6)) == pytest.approx(.875)
    assert 11/(.10-.02) == pytest.approx(137.5)
    assert 400+20-150 == 270
    assert 280+20-100+60 == 260


def test_guidance_preserves_readable_canonical_chinese_and_single_resource():
    assert "你是与用户共同推进工作的研究伙伴" in BASIC_RESEARCH_GUIDANCE
    assert "选定有价值且可执行的动作后就执行" in BASIC_RESEARCH_GUIDANCE
    assert "\ufffd" not in BASIC_RESEARCH_GUIDANCE
    for key in FIRST_METHODS:
        assert "\ufffd" not in get_research_method(key)["content"]
