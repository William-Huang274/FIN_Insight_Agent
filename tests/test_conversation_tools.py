"""Native checkpoint rehydration must retain operands, not just answer prose."""
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver

from sec_agent.agent_runtime.conversation_agent import build_conversation_agent
from sec_agent.agent_runtime.conversation_tools import conversation_tools
from test_conversation_agent import ScriptedTools


def test_recreated_agent_calculates_from_checkpoint_artifacts_and_isolates_threads():
    checkpoint = InMemorySaver()
    config = {"configurable": {"thread_id": "source-owner"}}
    tools = conversation_tools(thread_id="source-owner")
    first = build_conversation_agent(model=ScriptedTools(responses=[AIMessage(content="Read the source.")]),
        grants=tools, permission_mode="request_standard", checkpointer=checkpoint)
    receipt = {"authority_state": "s2_numeric_fact_query_result", "results": [{"status": "resolved", "facts": [
        {"numeric_fact_id": "fixture-2024", "numeric_fact_authority": True, "value_decimal": "100", "unit": "USD", "period_end": "2024-12-31"},
        {"numeric_fact_id": "fixture-2025", "numeric_fact_authority": True, "value_decimal": "125", "unit": "USD", "period_end": "2025-12-31"}]}]}
    first.invoke({"messages": [HumanMessage(content="Read synthetic protocol facts, not real company results."),
        AIMessage(content="", tool_calls=[{"name": "query_financial_data", "args": {}, "id": "read-1", "type": "tool_call"}]),
        ToolMessage(content="Source receipts", artifact=receipt, name="query_financial_data", tool_call_id="read-1")]}, config)
    request = {"expression": "(current / prior - 1) * 100", "operands": {
        "current": {"source_id": "fixture-2025"}, "prior": {"source_id": "fixture-2024"}},
        "result_unit": "percent", "rationale": "Synthetic same-unit annual growth protocol check."}
    def recreated():
        return build_conversation_agent(model=ScriptedTools(responses=[AIMessage(content="", tool_calls=[{
            "name": "calculate_research_metric", "args": {"request": request}, "id": "calc-1", "type": "tool_call"}]), AIMessage(content="Done")]),
            grants=conversation_tools(thread_id="source-owner"), permission_mode="request_standard", checkpointer=checkpoint)
    result = recreated().invoke({"messages": [HumanMessage(content="Now calculate the growth from the sources already read.")]}, config)
    calculated = next(m.artifact for m in result["messages"] if isinstance(m, ToolMessage) and m.name == "calculate_research_metric")
    assert calculated["value_decimal"] == "25.00"
    assert calculated["operands"]["prior"]["period_end"] == "2024-12-31"
    assert calculated["numeric_fact_authority"] is False
    other = recreated().invoke({"messages": [HumanMessage(content="Reuse those IDs from another conversation.")]},
        {"configurable": {"thread_id": "different-owner"}})
    error = next(m for m in other["messages"] if isinstance(m, ToolMessage))
    assert error.status == "error" and error.artifact is None
