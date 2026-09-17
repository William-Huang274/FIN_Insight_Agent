"""Within-phase continuity, native SDK payloads and bounded blockage handling."""
from copy import deepcopy
import json

import httpx
import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from pydantic import SecretStr

from sec_agent.agent_runtime.deepseek_structured_agents import (
    DeepSeekStructuredAgentAdapter, DeepSeekStructuredAgentError,
    ReasoningPreservingChatDeepSeek, _native_function_schema,
)
from sec_agent.agent_runtime.model_context import research_checkpoint_request, task_boundary_history
from sec_agent.agent_runtime.research_working_state import UpdateResearchStateAction
from sec_agent.agent_runtime.specialist_graph import SpecialistAgenticDependencies, build_specialist_agentic_state_graph
from test_research_working_state import source_messages, working_note
from test_specialist_graph import _input, _ToolPorts
from test_specialist_tool_batch import _handoff


def checkpoint_message(note, *, accepted=True):
    return [AIMessage(content="Current task remains unfinished.", tool_calls=[{
        "name": "UpdateResearchStateAction", "id": "checkpoint", "args": {}, "type": "tool_call"}]),
        ToolMessage(name="UpdateResearchStateAction", tool_call_id="checkpoint", status="success" if accepted else "error",
            content=json.dumps({"result": {"accepted": accepted, "checkpoint": True, "working_state": note},
                "current_context": {"task_context": {"overall_assignment": "Original scope", "last_task": "Still unfinished"}}}))]


def model(**updates):
    return ReasoningPreservingChatDeepSeek(model="deepseek-v4-pro", api_key=SecretStr("offline-fixture"),
        tool_context_policy="task_boundary", max_retries=0, use_responses_api=False, **updates)


def request_checkpoint(rows, chat):
    return research_checkpoint_request(rows, model=chat, native_tools={"UpdateResearchStateAction": UpdateResearchStateAction},
        runtime_context_binding=True, schema=_native_function_schema, max_input_characters=2000000)


def test_configurable_140k_272k_threshold_counts_wire_input_without_sending():
    rows=[HumanMessage(content="Original assignment " + "x" * 600000)]
    initial=deepcopy(rows)
    _, tools, pressure=request_checkpoint(rows,model(research_checkpoint_tokens=140000))
    assert pressure["estimated_input_tokens"] > 140000
    assert pressure["reason"] == "token_threshold"
    assert set(tools)=={"UpdateResearchStateAction"}
    assert request_checkpoint(rows,model(research_checkpoint_tokens=272000))[2] is None
    assert rows==initial


def test_mixed_language_pressure_uses_reported_wire_density_without_sharing_agents():
    from sec_agent.agent_runtime.model_context import research_input_pressure
    chat = model(research_checkpoint_tokens=140000, max_tokens=32000)
    measured = AIMessage(content="", response_metadata={"fin_runtime_input_measurement": {
        "model": chat.model_name, "input_characters": 500000, "provider_input_tokens": 175000}})
    pressure = research_input_pressure("x" * 400000, [measured], chat)
    assert pressure["estimated_input_tokens"] >= 140000
    assert pressure["calibration_samples"] == 1
    # A separate agent/history must not inherit usage from another conversation.
    assert research_input_pressure("x" * 400000, [], chat)["estimated_input_tokens"] < 140000
    assert research_input_pressure("研究" * 200000, [], chat)["estimated_input_tokens"] > 200000
    measured.response_metadata["fin_runtime_input_measurement"]["model"] = "another-model"
    assert research_input_pressure("x" * 400000, [measured], chat)["calibration_samples"] == 0


def test_future_completion_and_actual_tool_batch_trigger_before_character_ceiling():
    chat = model(research_checkpoint_tokens=272000, max_tokens=32000)
    rows = [HumanMessage(content="Scope " + "x" * 450000),
        AIMessage(content="", tool_calls=[{"name":"RequestSourceAction","id":"read", "args":{}, "type":"tool_call"}]),
        ToolMessage(content="Fresh source " + "y" * 20000, tool_call_id="read")]
    original = deepcopy(rows)
    projected, _, notice = research_checkpoint_request(rows, model=chat,
        native_tools={"UpdateResearchStateAction":UpdateResearchStateAction}, runtime_context_binding=True,
        schema=_native_function_schema, max_input_characters=600000)
    assert notice["reason"] == "input_character_headroom"
    assert notice["growth_reserve_characters"] > 160000
    assert projected[:-1] == rows and rows == original
    assert projected[-1].additional_kwargs['fin_context_checkpoint_instruction'] is True
    assert 'CURRENT REQUEST STATE: context_checkpoint_required=true' in projected[-1].content
    assert 'overrides allowed_actions' in projected[-1].content


def test_exact_assignment_copy_reuses_original_human_message_but_keeps_latest_handoff():
    from sec_agent.agent_runtime.model_context import coalesce_context_snapshots
    context = {"assignment": {"objective": "Compare two quarters", "units": "USD/share"}}
    rows = [HumanMessage(content=json.dumps({"task_context":context})),
        ToolMessage(tool_call_id="first",content=json.dumps({"result":{"text":"original source"}, "current_context":{"task_context":context}})),
        ToolMessage(tool_call_id="latest",content=json.dumps({"result":{"error":"keep this"}, "current_context":{"task_context":context}}))]
    original = deepcopy(rows)
    result = coalesce_context_snapshots(rows)
    assert result[0] == rows[0] and result[-1] == rows[-1] and rows == original
    body = json.loads(result[1].content)
    assert body["result"] == {"text":"original source"}
    assert body["current_context"]["task_context"]["identical_snapshot_retained_at"] == {"message_index":0,"field":"task_context"}
    # A future user message cannot be described as an earlier retained copy.
    reordered = [rows[1], rows[0], rows[2]]
    assert coalesce_context_snapshots(reordered)[0] == rows[1]


def test_working_phase_checkpoint_preserves_exact_material_evidence_and_recent_batch():
    rows=[HumanMessage(content="Overall assignment; no annual inference from quarter."),
        *source_messages("SOURCE-A"), *source_messages("SOURCE-B"), *source_messages("SOURCE-C"), *source_messages("LATEST")]
    rows[2].content=json.dumps({"ref_id":"SOURCE-A", "value":"66.6666666667", "period":"2025-Q2",
        "unit":"percent", "denominator":"Q2 capital expenditure", "revision":"issuer-call-v1", "status":"actual"})
    rows += checkpoint_message(working_note(phase_status="working"))
    rows += source_messages("UNCONSUMED")
    original=deepcopy(rows)
    projection=task_boundary_history(rows)
    for i in (0,2,4,8,10,11,12): assert projection[i]==rows[i]
    assert "Original numbers" not in projection[6].content
    assert '"node_id":"SOURCE-C"' in projection[6].content
    assert "before using" in projection[6].content.lower()
    assert rows==original
    # A later projection always starts from original records, not prior summaries.
    assert task_boundary_history(rows)==projection


def test_rejected_checkpoint_and_unfinished_uncheckpointed_phase_never_release_reads():
    rows=[*source_messages("SOURCE-C"), *checkpoint_message(working_note(phase_status="working"),accepted=False)]
    assert task_boundary_history(rows)==rows


def test_cited_draft_and_calculation_sources_survive_even_if_omitted_from_working_note():
    rows=[*source_messages("DRAFT"),*source_messages("OPERAND"),*source_messages("UNUSED"),*source_messages("LATEST")]
    rows += [AIMessage(content="",tool_calls=[{"name":"SubmitWorkpaperAction","id":"draft","args":{
        "claims":[{"evidence_ids":["DRAFT"]}]},"type":"tool_call"}]),
        ToolMessage(content="Rejected draft; original citation still needed for repair.",tool_call_id="draft",status="error"),
        AIMessage(content="",tool_calls=[{"name":"RequestCalculationAction","id":"calc","args":{
            "operands":{"a":{"source_id":"OPERAND","literal":"66.6666666667"}}},"type":"tool_call"}]),
        ToolMessage(content='{"result":"66.6666666667"}',tool_call_id="calc")]
    rows += checkpoint_message(working_note(phase_status="working",findings=[],retain_source_ids=[]))
    projected=task_boundary_history(rows)
    assert projected[1]==rows[1] and projected[3]==rows[3]
    assert "Original numbers" not in projected[5].content
    assert projected[9]==rows[9] and projected[11]==rows[11]


def test_unrelated_body_does_not_become_pinned_by_its_repeated_control_context():
    rows=[*source_messages("SOURCE-A"),*source_messages("UNUSED"),*source_messages("LATEST")]
    rows[3].content=json.dumps({"result":{"ref_id":"UNUSED","text":"Large unrelated body"},
        "current_context":{"task_context":{"working_state":working_note(),"lead_instruction":"Preserve the actual original assignment"}}})
    rows+=checkpoint_message(working_note(phase_status="working"))
    projection=task_boundary_history(rows)
    assert "Large unrelated body" not in projection[3].content
    assert "Preserve the actual original assignment" in projection[3].content
    assert projection[1]==rows[1]


def test_checkpoint_keeps_failed_observations_even_inside_successful_tool_envelope():
    failed=source_messages("FAILED")
    failed[1].content=json.dumps({"result":{"observations":[{"status":"failure","failure":{"code":"timeout"}}]}})
    rows=[*failed,*source_messages("LATEST"),*checkpoint_message(working_note(phase_status="working"))]
    assert task_boundary_history(rows)[1]==rows[1]


def test_actual_sdk_checkpoint_then_continuation_preserves_readers_and_originals():
    rows=[HumanMessage(content="Overall research scope"),*source_messages("SOURCE-C"),*source_messages("LATEST")]
    rows[2].content=json.dumps({"ref_id":"SOURCE-C","text":"Original recoverable historical source. "*20000})
    original=deepcopy(rows);captured=[]
    def serve(request):
        captured.append(json.loads(request.content))
        return httpx.Response(200,json={"id":"fixture","object":"chat.completion","created":1,"model":"deepseek-v4-pro",
            "choices":[{"index":0,"finish_reason":"stop","message":{"role":"assistant","content":"fixture"}}],
            "usage":{"prompt_tokens":100,"completion_tokens":1,"total_tokens":101}})
    with httpx.Client(transport=httpx.MockTransport(serve)) as client:
        chat=model(http_client=client,research_checkpoint_tokens=140000)
        initial,tools,pressure=request_checkpoint(rows,chat)
        assert pressure
        chat.bind_tools([_native_function_schema(t,runtime_context_binding=True) for t in tools.values()]).invoke(initial)
        rows += checkpoint_message(working_note(phase_status="working",findings=[],retain_source_ids=[]))
        continuation,tools,pressure=request_checkpoint(rows,chat)
        assert pressure is None
        chat.bind_tools([_native_function_schema(t,runtime_context_binding=True) for t in tools.values()]).invoke(continuation)
    assert "Original recoverable historical source." in json.dumps(captured[0])
    assert "Original recoverable historical source." not in json.dumps(captured[1])
    assert "SOURCE-C" in json.dumps(captured[1]) and "read_tool" in json.dumps(captured[1])
    assert "Annual composition remains unknown" in json.dumps(captured[1])
    assert rows[:len(original)]==original


def test_same_checkpoint_cannot_be_repaid_when_protected_context_still_exceeds_threshold():
    rows=[HumanMessage(content="Original task"),*source_messages("SOURCE-A"),
        *checkpoint_message(working_note(phase_status="working"))]
    with pytest.raises(ValueError,match="research_context_checkpoint_insufficient"):
        request_checkpoint(rows,model(research_checkpoint_tokens=1))


def test_accepted_checkpoint_archives_completed_reasoning_without_losing_exact_results():
    rows = [HumanMessage(content="User scope: quarter only"), *source_messages("SOURCE-A")]
    rows[1].additional_kwargs['reasoning_content'] = 'private old analysis ' * 20000
    rows += checkpoint_message(working_note(phase_status='working'))
    rows += source_messages('FRESH')
    rows[-2].additional_kwargs['reasoning_content'] = 'active reasoning must remain'
    original = deepcopy(rows)
    projected = task_boundary_history(rows)
    assert rows == original
    assert projected[0] == rows[0] and projected[-2:] == rows[-2:]
    operation = json.loads(projected[1].content)
    result = json.loads(projected[2].content)
    assert operation['tool_calls'] == rows[1].tool_calls
    assert result['original_content'] == rows[2].content
    assert result['tool_call_id'] == rows[2].tool_call_id
    assert 'NOT a user instruction' in result['notice']
    assert 'private old analysis' not in json.dumps([m.model_dump() for m in projected])
    # No accepted checkpoint, or an ordinary completed phase, retires reasoning.
    assert task_boundary_history(rows[:3])[1] == rows[1]
    rejected = deepcopy(rows); rejected[4].status = 'error'
    assert task_boundary_history(rejected)[1] == rows[1]


def test_checkpoint_archive_never_splits_pending_calls_and_keeps_error_text():
    rows = [*source_messages('SOURCE-A')]
    rows[0].additional_kwargs['reasoning_content'] = 'private completed'
    rows[1].status = 'error'; rows[1].content = 'timeout: not source absence'
    pending = AIMessage(content='pending',additional_kwargs={'reasoning_content':'still active'},
        tool_calls=[{'name':'RequestSourceAction','id':'unfinished','args':{},'type':'tool_call'}])
    rows += [pending, *checkpoint_message(working_note(phase_status='working'))]
    projected = task_boundary_history(rows)
    assert projected[2] == pending
    assert json.loads(projected[1].content)['status'] == 'error'
    assert json.loads(projected[1].content)['original_content'] == rows[1].content


@pytest.mark.parametrize("reason", ["research_context_checkpoint_insufficient", "research_context_checkpoint_input_limit_exceeded"])
def test_context_blockage_notifies_lead_once_and_never_restarts_the_expert_allowance(reason):
    ports=_ToolPorts();helps=[];calls=[]
    def turn(request):
        calls.append(request)
        raise DeepSeekStructuredAgentError(reason)
    def help(state,config):
        helps.append(state)
        return {"disposition":"continue", "diagnosis":"Required joint evidence still exceeds the current window.",
            "next_action":"Preserve the joint comparison and examine a bounded subquestion assignment.",
            "expected_progress":"The original task must continue only if the required source set fits."}
    graph=build_specialist_agentic_state_graph(dependencies=SpecialistAgenticDependencies(model_turn=turn,
        evidence_tool=ports.evidence,finance_tool=ports.finance,working_state_enabled=True,lead_assistance=help)).compile()
    result=graph.invoke(_input(),{"recursion_limit":20})
    assert len(helps)==1 and len(calls)==2
    assert result["review_reason"]=="research_context_checkpoint_unresolved"
    assert result["notebook"]["model_turn_count"]==0  # both blocks were pre-transport


def test_checkpoint_cannot_silently_drop_an_open_question():
    calls=[];ports=_ToolPorts()
    base=working_note(phase_status="working",findings=[],retain_source_ids=[])
    def turn(request):
        calls.append(request)
        if len(calls)>2:return _handoff(request)
        note=base if len(calls)==1 else {**base,"open_questions":[]}
        return {"action":"native_tool_batch","context_digest":request["context_digest"],"tool_calls":[{
            "name":"UpdateResearchStateAction","id":str(len(calls)),"args":{
                "action":"update_research_state","context_digest":request["context_digest"],
                "reason_summary":"Preserve the current unfinished investigation.","checkpoint":len(calls)==2,"working_state":note}}]}
    graph=build_specialist_agentic_state_graph(dependencies=SpecialistAgenticDependencies(model_turn=turn,
        evidence_tool=ports.evidence,finance_tool=ports.finance,working_state_enabled=True)).compile()
    result=graph.invoke(_input(),{"recursion_limit":20})
    assert result["research_working_state"]["open_questions"]==base["open_questions"]
    assert "working_state_checkpoint_lost_issues" in json.dumps(calls[-1]["tool_results"])


def test_actual_sdk_uses_audited_author_turn_for_checkpoint_and_native_acceptance():
    from test_deepseek_structured_agents import _config, _models
    captured=[];events=[];private=[];ports=_ToolPorts()
    note=working_note(phase_status="working",findings=[],retain_source_ids=[])
    def serve(request):
        body=json.loads(request.content);captured.append(body)
        assert {t["function"]["name"] for t in body["tools"]}=={"UpdateResearchStateAction","RequestHumanReviewAction"}
        assert "Runtime context checkpoint required" in json.dumps(body["messages"])
        assert body['messages'][-1]['role'] == 'system'
        assert 'CURRENT REQUEST STATE' in body['messages'][-1]['content']
        args={"action":"update_research_state","reason_summary":"Save the unresolved research step.","checkpoint":True,"working_state":note}
        return httpx.Response(200,json={"id":"fixture","object":"chat.completion","created":1,"model":"deepseek-v4-pro",
            "choices":[{"index":0,"finish_reason":"tool_calls","message":{"role":"assistant","content":"","tool_calls":[{
                "id":"checkpoint","type":"function","function":{"name":"UpdateResearchStateAction","arguments":json.dumps(args)}}]}}],
            "usage":{"prompt_tokens":100,"completion_tokens":30,"total_tokens":130}})
    with httpx.Client(transport=httpx.MockTransport(serve)) as client:
        models=_models();models["specialist"]=model(http_client=client,research_checkpoint_tokens=1)
        configured=_config().model_copy(update={"agentic_message_history":True,"runtime_context_binding":True})
        adapter=DeepSeekStructuredAgentAdapter(config=configured,chat_models=models,audit_sink=events.append,
            private_audit_sink=private.append)
        graph=build_specialist_agentic_state_graph(dependencies=SpecialistAgenticDependencies(
            model_turn=adapter.specialist_model_turn,turn_source="provider_model",
            evidence_tool=ports.evidence,finance_tool=ports.finance,working_state_enabled=True)).compile()
        result=graph.invoke(_input(),{"recursion_limit":20})
    assert result["research_working_state"]["last_task_detail"]==note["last_task_detail"]
    assert result["research_working_state"]["phase_status"]=="working"
    assert len(captured)==1 and result["notebook"]["model_turn_count"]==1
    assert any(e.get("context_checkpoint") for e in events)
    assert result["review_reason"]=="research_context_checkpoint_unresolved"
    response = next(e['raw_response'] for e in private if e.get('raw_response'))
    assert response['response_metadata']['fin_runtime_input_measurement']['provider_input_tokens'] == 100
    assert 'fin_runtime_input_measurement' not in json.dumps(captured)


def test_oversized_checkpoint_has_diagnostic_notice_and_never_calls_transport():
    from test_deepseek_structured_agents import _config, _models, _agentic_turn_request
    events=[]
    def forbidden(request):
        raise AssertionError("Oversized checkpoint must not reach transport")
    with httpx.Client(transport=httpx.MockTransport(forbidden)) as client:
        models=_models(); models['specialist']=model(http_client=client,research_checkpoint_tokens=1)
        config=_config().model_copy(update={'agentic_message_history':True,'runtime_context_binding':True})
        config=config.model_copy(update={'token_budget_basis':{**config.token_budget_basis,
            'specialist':config.token_budget_basis['specialist'].model_copy(update={'max_input_characters':10000})}})
        adapter=DeepSeekStructuredAgentAdapter(config=config,chat_models=models,audit_sink=events.append)
        request=_agentic_turn_request()
        request['allowed_actions']=[*request['allowed_actions'],'update_research_state']
        request['task_context']={'overall_assignment':'x'*20000}
        with pytest.raises(DeepSeekStructuredAgentError,match='research_context_checkpoint_input_limit_exceeded'):
            adapter.specialist_model_turn(request)
    blocked=next(e for e in events if e.get('status')=='blocked_before_transport_input_limit')
    assert blocked['context_checkpoint']['trigger_tokens']==1
    assert blocked['provider_call_attempted'] is False
