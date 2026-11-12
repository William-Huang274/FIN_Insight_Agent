"""Native checkpoint rehydration must retain operands, not just answer prose."""
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
import pytest

from sec_agent.agent_runtime.conversation_agent import build_conversation_agent
from sec_agent.agent_runtime.conversation_tools import conversation_tools
from test_conversation_agent import ScriptedTools


def test_source_only_agent_consumes_method_without_financial_database():
    grants = conversation_tools(thread_id='source-only')
    assert 'query_financial_data' not in {g.tool.name for g in grants}
    model = ScriptedTools(responses=[AIMessage(content='', tool_calls=[{
        'name': 'get_research_method', 'args': {'method_id': 'finance'},
        'id': 'method-read', 'type': 'tool_call'}]), AIMessage(content='Method read.')])
    agent = build_conversation_agent(model=model, grants=grants, permission_mode='request_standard',
                                    checkpointer=InMemorySaver())
    result = agent.invoke({'messages': [HumanMessage(content='Read the packaged finance method.')]},
                          {'configurable': {'thread_id': 'source-only'}})
    response = next(m for m in result['messages'] if isinstance(m, ToolMessage))
    assert response.name == 'get_research_method' and response.status == 'success'
    assert len(response.content) > 1000


def test_saved_result_json_pointer_returns_exact_item_without_new_dispatch():
    import json
    from types import SimpleNamespace
    from langchain_core.tools import ToolException
    reader=next(g.tool for g in conversation_tools(thread_id="pointer") if g.tool.name=="read_saved_result")
    item={"passage_id":"PASSAGE::p", "text":"exact qualifiers", "period":"FY2025", "unit":"USD"}
    rows=[ToolMessage(name="read_source_document",tool_call_id="saved",content=json.dumps({"items":[item]}))]
    runtime=SimpleNamespace(state={"messages":rows})
    result=reader.func(tool_call_id="saved",runtime=runtime,json_pointer="/items/0")
    assert json.loads(result["content"])==item and result["new_tool_dispatch"] is False
    assert reader.func(tool_call_id="saved",runtime=runtime,json_pointer="/items/0/text",offset=6,max_characters=4)["content"]=="qual"
    selection = reader.func(tool_call_id="saved",runtime=runtime,json_pointer="/items/3")
    assert selection['result_state'] == 'field_selection_required'
    assert selection['field_index']['fields'][0]['json_pointer'] == '/items'
    assert json.loads(reader.func(**selection['readback']['arguments'],runtime=runtime)['content']) == {'items':[item]}
    with pytest.raises(ToolException):
        reader.func(tool_call_id="saved",runtime=SimpleNamespace(state={"messages":[]}),json_pointer="/items/0")


def test_saved_result_field_navigation_preserves_raw_offsets_and_values():
    import json
    from types import SimpleNamespace
    from langchain_core.tools import ToolException
    reader = next(g.tool for g in conversation_tools(thread_id="fields") if g.tool.name == "read_saved_result")
    value = {"operands": {"a/b~": {"literal": "1,000", "provenance": "x" * 15000}},
             "value_decimal": "0.654737657570672122", "financial_semantics_verified": False}
    raw = json.dumps(value)
    saved = ToolMessage(name="calculate_research_metric", tool_call_id="calc", content=raw)
    runtime = SimpleNamespace(state={"messages": [saved]})
    result = reader.func(tool_call_id="calc", runtime=runtime, offset=6700, max_characters=1200)
    assert result["content"] == raw[6700:7900]
    fields = {r["json_pointer"]: r for r in result["field_index"]["fields"]}
    assert fields["/value_decimal"]["value"] == value["value_decimal"]
    assert fields["/financial_semantics_verified"]["value"] is False
    assert "value" not in fields["/operands"]
    nested = reader.func(tool_call_id="calc", runtime=runtime, json_pointer="/operands")
    pointer = nested["field_index"]["fields"][0]["json_pointer"]
    assert pointer == "/operands/a~1b~0"
    assert json.loads(reader.func(tool_call_id="calc", runtime=runtime, json_pointer=pointer,
                                  max_characters=24000)["content"]) == value["operands"]["a/b~"]
    assert saved.content == raw and result["new_tool_dispatch"] is False
    saved.content = "not JSON"
    assert "field_index" not in reader.func(tool_call_id="calc", runtime=runtime)
    with pytest.raises(ToolException):
        reader.func(tool_call_id="calc", runtime=runtime, json_pointer="")


def test_saved_read_wrapper_returns_original_entry_without_reinterpreting_requested_field():
    import json
    from types import SimpleNamespace
    from langchain_core.tools import ToolException
    reader = next(g.tool for g in conversation_tools(thread_id='wrapper') if g.tool.name=='read_saved_result')
    data = ToolMessage(name='read_public_source',tool_call_id='source',content=json.dumps({'items':[{'passage':'exact original'}]}))
    state = SimpleNamespace(state={'messages':[data]})
    first = reader.func(tool_call_id='source',json_pointer='/items/0/passage',runtime=state)
    wrapper = ToolMessage(name='read_saved_result',tool_call_id='wrapper',content=json.dumps(first))
    state.state['messages'].append(wrapper)
    result = reader.func(tool_call_id='wrapper',json_pointer='/items/0/passage',runtime=state,max_characters=14000)
    assert result['result_state']=='original_result_selection_required'
    assert result['previously_read_field']=='/items/0/passage'
    assert 'json_pointer' not in result['readback']['arguments']
    assert json.loads(reader.func(**result['readback']['arguments'],runtime=state)['content'])=={'items':[{'passage':'exact original'}]}
    assert result['new_tool_dispatch'] is False
    with pytest.raises(ToolException):
        reader.func(tool_call_id='wrapper',runtime=SimpleNamespace(state={'messages':[wrapper]}))


def test_saved_result_field_index_is_bounded_and_does_not_truncate_values():
    from sec_agent.agent_runtime.context_records import saved_result_field_index
    index = saved_result_field_index({str(i): "x" * 161 for i in range(100)})
    assert len(index["fields"]) == 32 and index["remaining_fields"] == 68
    assert all("value" not in r and r["characters"] == 161 for r in index["fields"])
    assert saved_result_field_index([None, False, 3])["fields"][2] == {"json_pointer": "/2", "kind": "scalar", "value": 3}


@pytest.mark.parametrize('name', ['respond_research_action', 'record_research_assessment'])
def test_saved_audit_receipt_is_readable_but_not_source_evidence(name):
    import json
    from types import SimpleNamespace
    from sec_agent.agent_runtime.harness_business_tools import actionable_tool_feedback, model_receipt
    from sec_agent.agent_runtime.conversation_tools import calculator_observations
    from langchain_core.tools import ToolException
    reader = next(g.tool for g in conversation_tools(thread_id='audit') if g.tool.name == 'read_saved_result')
    raw = json.dumps({'disposition':'revised', 'report_digest':'old-version', 'rationale':'Original judgment'})
    original = ToolMessage(name=name, tool_call_id='audit-id', content=raw)
    runtime = SimpleNamespace(state={'messages':[original]})
    result = reader.func(tool_call_id='audit-id', runtime=runtime)
    assert result['content'] == raw and result['source_evidence'] is False
    assert result['result_state'] == 'saved_audit_receipt' and result['new_tool_dispatch'] is False
    assert model_receipt(original)['original_readback']['arguments']['tool_call_id'] == 'audit-id'
    assert calculator_observations([original]) == {}
    assert reader.func(tool_call_id='audit-id', runtime=runtime, json_pointer='/report_digest')['content'] == 'old-version'
    with pytest.raises(ToolException) as exc:
        reader.func(tool_call_id='audit-id', runtime=SimpleNamespace(state={'messages':[]}))
    rejected = ToolMessage(name='read_saved_result', tool_call_id='rejected', status='error', content=str(exc.value))
    assert actionable_tool_feedback(rejected)
    feedback = json.loads(rejected.content)
    assert feedback['source_evidence'] is False and 'content' not in feedback


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
