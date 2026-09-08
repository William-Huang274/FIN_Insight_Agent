"""A handoff retrieves native evidence, never summarized or cross-owner values."""
import asyncio
from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver

from sec_agent.agent_runtime.conversation_handoff import handoff_tools, public_history, SURFACE
from sec_agent.agent_runtime.conversation_tools import conversation_tools
from sec_agent.agent_runtime.conversation_agent import build_conversation_agent
from test_conversation_agent import ScriptedTools


def test_pinned_handoff_rehydrates_financial_operands_and_rejects_owner_change():
    thread, checkpoint = str(uuid4()), str(uuid4()); reads=[]
    source = {"metadata":{"surface":SURFACE,"owner_id":"alice"}}
    receipt = {"authority_state":"s2_numeric_fact_query_result","results":[{"status":"resolved","facts":[
        {"numeric_fact_id":"before","numeric_fact_authority":True,"value_decimal":"100","unit":"USD","period_end":"2024-12-31"},
        {"numeric_fact_id":"after","numeric_fact_authority":True,"value_decimal":"125","unit":"USD","period_end":"2025-12-31"}]}]}
    state={"values":{"messages":[{"type":"human","id":"u1","content":"Only compare same units; original correction."},
        {"type":"ai","content":"public conclusion","additional_kwargs":{"reasoning_content":"PRIVATE"}},
        {"type":"tool","name":"query_financial_data","artifact":receipt}]}}
    original=deepcopy(state)
    async def get(source_id): assert source_id==thread;return source
    async def get_state(source_id, **kwargs): reads.append(kwargs);return state
    sdk=SimpleNamespace(threads=SimpleNamespace(get=get,get_state=get_state))
    grants=handoff_tools(reference={"source_thread":thread,"checkpoint_id":checkpoint,"note":"Continue exact evidence"},sdk=sdk,owner_id="alice")
    async def run():
        context=await grants[0].tool.ainvoke({})
        assert context["text"]==state["values"]["messages"][0]["content"] and "PRIVATE" not in str(context)
        assert (await grants[1].tool.ainvoke({}))["total"]==2
        model=ScriptedTools(responses=[AIMessage(content="",tool_calls=[
            {"name":"read_handoff_evidence","args":{"source_id":"before"},"id":"r1","type":"tool_call"},
            {"name":"read_handoff_evidence","args":{"source_id":"after"},"id":"r2","type":"tool_call"}]),
            AIMessage(content="",tool_calls=[{"name":"calculate_research_metric","id":"calc","type":"tool_call","args":{"request":{
                "expression":"(new / old - 1) * 100","operands":{"new":{"source_id":"after"},"old":{"source_id":"before"}},
                "result_unit":"percent","rationale":"Synthetic identical unit/year comparison"}}}]),AIMessage(content="25%")])
        agent=build_conversation_agent(model=model,grants=grants+conversation_tools(thread_id="child"),permission_mode="request_standard",checkpointer=InMemorySaver())
        result=await agent.ainvoke({"messages":[HumanMessage(content="Continue from original receipts")]},{"configurable":{"thread_id":"child"}})
        calc=next(m.artifact for m in result["messages"] if isinstance(m,ToolMessage) and m.name=="calculate_research_metric")
        assert calc["value_decimal"]=="25.00" and calc["operands"]["old"]["period_end"]=="2024-12-31"
        source["metadata"]["owner_id"]="bob"
        denied=await grants[2].tool.ainvoke({"source_id":"before"})
        assert "不可访问" in denied
    asyncio.run(run())
    assert reads==[{"checkpoint":{"checkpoint_id":checkpoint,"checkpoint_ns":""}}] and state==original
    assert "PRIVATE" not in str(public_history(state))
