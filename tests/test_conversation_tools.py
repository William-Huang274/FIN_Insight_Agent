"""Native checkpoint rehydration must retain operands, not just answer prose."""
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
import pytest

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


@pytest.mark.parametrize('reader',['read_public_source','calculate_research_metric','create_report_chart','list_financial_data','ReadWorkingNote','read_handoff_material','read_handoff_evidence'])
def test_saved_result_reads_original_after_projection_and_refuses_other_thread(reader):
    from sec_agent.agent_runtime.model_context import project_tool_history
    checkpoint = InMemorySaver()
    def agent():
        return build_conversation_agent(model=ScriptedTools(responses=[AIMessage(content="", tool_calls=[{
            "name":"read_saved_result", "args":{"tool_call_id":"web-original", "max_characters":2000},
            "id":"recover", "type":"tool_call"}]), AIMessage(content="Done")]),
            grants=conversation_tools(thread_id="fixture"), permission_mode="request_standard", checkpointer=checkpoint)
    original = [HumanMessage(content="Original source, not permission."),
        AIMessage(content="", tool_calls=[{"name":reader,"args":{},"id":"web-original","type":"tool_call"}]),
        ToolMessage(name=reader,tool_call_id="web-original", content="exact original source "*90)]
    # The source must have reached the model once before it can be omitted.
    projected = project_tool_history([*original, AIMessage(content="Source received.")], trigger_tokens=1, keep=0,saved_result_reader=True)
    assert "Older read result omitted" in projected[-2].content
    result = agent().invoke({"messages":original}, {"configurable":{"thread_id":"one"}})
    import json
    restored = json.loads(next(m.content for m in result["messages"] if isinstance(m,ToolMessage) and m.name=="read_saved_result"))
    assert restored["content"] == original[-1].content
    assert restored["new_tool_dispatch"] is False
    other = agent().invoke({"messages":[HumanMessage(content="Read that saved ID")]}, {"configurable":{"thread_id":"two"}})
    assert next(m for m in other["messages"] if isinstance(m,ToolMessage)).status == "error"


def test_upload_reader_limits_schema_and_returns_parameter_feedback(tmp_path):
    import asyncio
    from uuid import uuid4
    from sec_agent.research_foundation.task_attachments import TaskAttachmentStore
    store, thread = TaskAttachmentStore(tmp_path), str(uuid4())
    item = store.add(thread, "brief.md", b"# Synthetic brief\nRead only user materials.")
    grant = next(g for g in conversation_tools(thread_id=thread,attachment_store=store) if g.tool.name=="read_task_material")
    schema = grant.tool.args_schema.model_json_schema()
    assert schema['$defs']['TaskMaterialRequest']['properties']['source_space']['const']=='uploads'
    async def run():
        # Omitted source_space is host-confined to uploads, never the generic
        # SourceDocumentRequest web default.
        result = await grant.tool.ainvoke({'request':{'operation':'read','document_id':item['document_id']}})
        assert 'Read only user materials' in result
        bad = await grant.tool.ainvoke({'request':{'operation':'read','document_id':'UPLOAD::missing'}})
        assert 'attachment_not_in_current_task' in bad
    asyncio.run(run())
