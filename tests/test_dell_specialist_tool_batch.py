"""Native call cardinality, per-call boundaries, and immutable R6 offline replay."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr

from sec_agent.agent_runtime.dell_specialist_agentic_graph import (
    DellSpecialistAgenticDependencies, DellSpecialistAgenticGraphError,
    SpecialistNotebook, build_dell_specialist_agentic_state_graph,
)
from sec_agent.agent_runtime.deepseek_structured_agents import (
    DeepSeekStructuredAgentAdapter, ReasoningPreservingChatDeepSeek,
)
from test_dell_specialist_agentic_graph import _input, _evidence_action, _finance_action, _submission, _ToolPorts


def _batch(request, actions):
    names = {"request_evidence": "RequestEvidenceAction", "request_finance": "RequestFinanceAction",
             "request_source": "RequestSourceAction", "request_human_review": "RequestHumanReviewAction",
             "submit_workpaper": "SubmitWorkpaperAction"}
    return {"action": "native_tool_batch", "context_digest": request["context_digest"], "tool_calls": [
        {"id": f"call-{n}", "name": names[action["action"]], "type": "tool_call",
         "args": {**action, "context_digest": request["context_digest"]}} for n, action in enumerate(actions)]}


def _handoff(request):
    return {"action": "request_human_review", "context_digest": request["context_digest"],
            "reason_summary": "Offline fixture complete, not financial research.", "blocker_code": "offline_complete"}


def _exercise(mutate=lambda batch: None, max_actions=12, source_enabled=True):
    requests, ports = [], _ToolPorts()
    actions = [_evidence_action()({}), _finance_action()({}),
               {**_finance_action()({}), "intent": {"ticker": "DELL", "metric_ids": ["cash_and_equivalents"],
                 "granularity": "instant", "selection_mode": "latest_on_or_before"}},
               {"action": "request_source", "reason_summary": "Read catalog", "selection": {"operation": "catalog"}}]

    def model(request):
        requests.append(request)
        if len(requests) > 1:
            return _handoff(request)
        batch = _batch(request, actions)
        mutate(batch)
        return batch

    def evidence(request):
        if request["action"]["action"] != "request_source":
            return ports.evidence(request)
        ports.calls.append(request)
        return ports._observation(request, kind="evidence", references=[], content=[{"catalog": "fixture"}])

    graph_input = _input()
    graph_input["l0_context"]["source_read_enabled"] = source_enabled
    graph_input["max_tool_actions"] = max_actions
    graph = build_dell_specialist_agentic_state_graph(dependencies=DellSpecialistAgenticDependencies(
        model_turn=model, evidence_tool=evidence, finance_tool=ports.finance)).compile()
    result = graph.invoke(graph_input, config={"recursion_limit": 32})
    SpecialistNotebook.model_validate_json(json.dumps(result["notebook"]))
    return result, requests, ports.calls


def test_four_reads_are_one_model_turn_four_actions_with_all_results():
    result, requests, calls = _exercise()
    assert len(calls) == 4 and len(requests) == 2
    first = requests[1]["notebook"]
    assert (first["model_turn_count"], first["tool_action_count"]) == (1, 4)
    assert len(first["model_turn_records"]) == 1 and len(first["observations"]) == 4
    assert [row["tool_call_id"] for row in requests[1]["tool_results"]] == [f"call-{n}" for n in range(4)]
    assert {call["action"]["context_digest"] for call in calls} == {requests[0]["context_digest"]}
    assert len({call["action_attempt_id"] for call in calls}) == 4
    assert result["final_submission"] is None


@pytest.mark.parametrize("defect,code", [
    ("bad_schema", "specialist_tool_arguments_invalid"),
    ("wrong_tag", "specialist_tool_arguments_invalid"),
    ("context", "specialist_model_turn_context_binding_invalid"),
    ("route", "specialist_evidence_route_not_assigned"),
    ("unknown", "not a valid tool"),
    ("duplicate_request", "duplicate_tool_request_blocked_before_dispatch"),
    ("invalid_json", "specialist_tool_arguments_json_invalid"),
])
def test_one_invalid_call_does_not_discard_three_valid_reads(defect, code):
    def mutate(batch):
        call = batch["tool_calls"][0]
        if defect == "bad_schema":
            call["args"]["arbitrary_file"] = "D:/forbidden"
        elif defect == "wrong_tag":
            call["args"]["action"] = "request_finance"
        elif defect == "context":
            call["args"]["context_digest"] = "0" * 64
        elif defect == "route":
            call["args"]["minimum_route_obligation_id"] = "other-branch"
        elif defect == "unknown":
            call["name"] = "UnregisteredTool"
        elif defect == "invalid_json":
            call.update(type="invalid_tool_call", args='{"reason_summary":"bad "quote""}')
        else:
            call["name"] = "RequestFinanceAction"
            call["args"] = deepcopy(batch["tool_calls"][1]["args"])
    _, requests, calls = _exercise(mutate)
    assert len(calls) == 3
    results = requests[1]["tool_results"]
    assert len(results) == 4
    failed = [row for row in results if row["status"] == "error"]
    assert len(failed) == 1 and code in failed[0]["content"]


def test_source_profile_denial_and_tool_ceiling_remain_effective():
    _, requests, calls = _exercise(source_enabled=False)
    assert len(calls) == 3
    assert "not_available" in requests[1]["tool_results"][-1]["content"]
    result, requests, calls = _exercise(max_actions=2)
    assert len(calls) == 2 and len(requests) == 1
    assert result["notebook"]["tool_action_count"] == 2
    assert result["human_review_handoff"]["trigger"] == "tool_action_ceiling"
    assert [row["status"] for row in result["tool_results"]] == ["success", "success", "error", "error"]


def test_terminal_mixed_with_reads_returns_errors_without_any_dispatch():
    def mutate(batch):
        batch["tool_calls"][0] = {"id": "call-0", "name": "RequestHumanReviewAction", "type": "tool_call",
                                  "args": _handoff({"context_digest": batch["context_digest"]})}
    result, requests, calls = _exercise(mutate)
    assert not calls and result["final_submission"] is None
    assert len(requests[1]["tool_results"]) == 4
    assert all("terminal_action_must_be_alone" in row["content"] for row in requests[1]["tool_results"])


@pytest.mark.parametrize("defect", ["missing", "duplicate"])
def test_invalid_call_ids_reject_before_dispatch(defect):
    def mutate(batch):
        if defect == "missing":
            batch["tool_calls"][0].pop("id")
        else:
            batch["tool_calls"][0]["id"] = batch["tool_calls"][1]["id"]
    with pytest.raises(DellSpecialistAgenticGraphError, match="specialist_model_action_invalid"):
        _exercise(mutate)


@pytest.mark.local_data_integration
def test_immutable_r6_response_real_mcp_and_sdk_four_result_continuation(monkeypatch):
    from test_dell_deepseek_structured_agents import _config
    from test_dell_specialist_agentic_composition import RUNTIME_ENVIRONMENT, _assert_assets
    from sec_agent.agent_runtime.dell_specialist_agentic_composition import open_dell_specialist_receipted_composition
    _assert_assets()
    root = Path("Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/q1_specialist_paid_shadow/attempts/20260905-dell-q1-source-read-thinking-enabled-r6")
    audit_path, state_path = root / "model-context-reasoning.private.jsonl", root / "diagnostic-state-after-failure.private.json"
    if not audit_path.exists():
        pytest.skip("immutable R6 private counterexample unavailable")
    original_bytes = audit_path.read_bytes(), state_path.read_bytes()
    audit = json.loads(original_bytes[0].decode("utf-8").strip())
    old = json.loads(original_bytes[1])["values"]
    raw = audit["raw_response"]
    requests, wires, public = [], [], []
    # A historical replay uses its historical disclosed capability context,
    # not a new input digest after current capability disclosure is corrected.
    import sec_agent.agent_runtime.dell_specialist_agentic_composition as module
    from sec_agent.agent_runtime.dell_specialist_agentic_graph import SpecialistL0Context
    build_input = module._build_graph_input

    def historical_input(**kwargs):
        current = build_input(**kwargs)
        return current.model_copy(update={"l0_context": SpecialistL0Context.model_validate_json(json.dumps(old["l0_context"]))})

    monkeypatch.setattr(module, "_build_graph_input", historical_input)

    def respond(req):
        wires.append(json.loads(req.content))
        if len(wires) == 1:
            assert requests[-1]["context_digest"] == raw["tool_calls"][0]["args"]["context_digest"]
            calls = raw["tool_calls"]
            reasoning = raw["additional_kwargs"]["reasoning_content"]
        else:
            calls = [{"id": "offline-terminal", "name": "RequestHumanReviewAction", "args": _handoff(requests[-1])}]
            reasoning = "Synthetic offline stop; no additional provider inference."
        return httpx.Response(200, json={"id": "offline-r6-replay", "object": "chat.completion", "created": 1,
            "model": "deepseek-v4-pro", "choices": [{"index": 0, "finish_reason": "tool_calls", "message": {
                "role": "assistant", "content": "", "reasoning_content": reasoning,
                "tool_calls": [{"id": call["id"], "type": "function", "function": {
                    "name": call["name"], "arguments": json.dumps(call["args"])}} for call in calls]}}],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}})

    client = httpx.Client(transport=httpx.MockTransport(respond))
    model = ReasoningPreservingChatDeepSeek(model="deepseek-v4-pro", api_key=SecretStr("offline-no-network"),
        http_client=client, max_retries=0, use_responses_api=False, extra_body={"thinking": {"type": "enabled"}})
    config = _config().model_copy(update={"thinking": "enabled", "agentic_message_history": True})
    adapter = DeepSeekStructuredAgentAdapter(config=config,
        chat_models={role: model for role in ("planner", "specialist", "counter", "lead")}, audit_sink=public.append)

    def replay(request):
        requests.append(request)
        result = adapter.specialist_model_turn(request)
        result["runtime_receipt"].update(kind="host", actor="dell_specialist_saved_response_replay", usage_reported=None)
        return result

    # Same historical input only in an in-memory OFFLINE graph; no Agent Server
    # run/resume, provider network, artifact writes or original receipt changes.
    with open_dell_specialist_receipted_composition(run_id=old["run_id"], run_invocation_id=old["run_invocation_id"],
        branch_id="Q1_ISSUER_TRUTH", turn_source="saved_response_replay", model_turn=replay,
        max_model_turns=old["max_model_turns"], max_tool_actions=old["max_tool_actions"],
        source_read_enabled=True, environment=RUNTIME_ENVIRONMENT) as composition:
        result = composition.graph.invoke(composition.graph_input.model_dump(mode="json"), config={"recursion_limit": 32})
    client.close()
    notebook = result["notebook"]
    assert (notebook["model_turn_count"], notebook["tool_action_count"]) == (2, 4)
    assert len(wires) == 2 and len(notebook["observations"]) == 4
    assert all(not row["model_execution_evidence"] for row in notebook["model_turn_records"])
    messages = wires[1]["messages"]
    prior = next(message for message in messages if message["role"] == "assistant")
    assert sha256(prior["reasoning_content"].encode()).digest() == sha256(raw["additional_kwargs"]["reasoning_content"].encode()).digest()
    replies = [message for message in messages if message["role"] == "tool"]
    assert [message["tool_call_id"] for message in replies] == [call["id"] for call in raw["tool_calls"]]
    assert [json.loads(call["function"]["arguments"]) for call in prior["tool_calls"]] == [call["args"] for call in raw["tool_calls"]]
    assert all(len(json.loads(message["content"])["result"]["observations"]) == 1 for message in replies)
    items = [item for observation in notebook["observations"] for item in observation["content"]]
    assert any(item.get("result_state") == "numeric_fact" for item in items)
    assert any(item.get("result_state") == "reviewed_evidence" for item in items)
    assert any(item.get("document_id") for item in items)
    assert "reasoning_content" not in json.dumps(public) and "reasoning_content" not in json.dumps(notebook)
    assert original_bytes == (audit_path.read_bytes(), state_path.read_bytes())


@pytest.mark.parametrize("result_defect", ["missing", "wrong_id"])
def test_missing_or_misattributed_batch_feedback_stops_before_next_transport(result_defect):
    from langchain_core.messages import AIMessage
    from sec_agent.agent_runtime.deepseek_structured_agents import DeepSeekStructuredAgentError
    from test_dell_deepseek_structured_agents import _config, _agentic_turn_request
    request = _agentic_turn_request()
    adapter = DeepSeekStructuredAgentAdapter(
        config=_config().model_copy(update={"agentic_message_history": True}),
        chat_models={role: object() for role in ("planner", "specialist", "counter", "lead")})
    adapter._agentic_history[request["agent_id"]] = [AIMessage(content="", tool_calls=[
        {"id": "expected", "name": "RequestFinanceAction", "args": {}, "type": "tool_call"}])]
    if result_defect == "wrong_id":
        request["tool_results"] = [{"tool_call_id": "wrong", "content": "{}"}]
    with pytest.raises(DeepSeekStructuredAgentError, match="specialist_(native_tool_results_missing|tool_result_call_ids_mismatch)"):
        adapter.specialist_model_turn(request)


def _terminal_feedback_sdk_graph(*, saved_raw=None):
    """Offline model responses, actual SDK/ToolNode/history; not paid research."""
    from test_dell_deepseek_structured_agents import _config
    requests, wires, public, ports = [], [], [], _ToolPorts()

    def respond(req):
        wires.append(json.loads(req.content))
        request, n = requests[-1], len(wires)
        if n == 1:
            calls = _batch(request, [_evidence_action()({}), _finance_action()({})])["tool_calls"]
        else:
            action = _submission()(request)
            if n == 2:
                if saved_raw is not None:
                    # Replay exact R9 arguments except the new in-memory context
                    # binding. No original run/resume or artifact mutation.
                    action = {**deepcopy(saved_raw["tool_calls"][0]["args"]),
                              "context_digest": request["context_digest"]}
                else:
                    action["claims"][0]["evidence_ids"] = []
            elif saved_raw is not None:
                action = _handoff(request)
            elif n == 3:
                # Schema now valid, but an invented reference must still fail
                # the unchanged financial acceptance validator.
                action["claims"][0]["evidence_ids"] = ["E:invented"]
            calls = _batch(request, [action])["tool_calls"]
        reasoning = (saved_raw["additional_kwargs"]["reasoning_content"]
                     if saved_raw is not None and n == 2 else "Synthetic private reasoning, not evidence.")
        return httpx.Response(200, json={"id": f"offline-terminal-{n}", "object": "chat.completion", "created": 1,
            "model": "deepseek-v4-pro", "choices": [{"index": 0, "finish_reason": "tool_calls", "message": {
                "role": "assistant", "content": "", "reasoning_content": reasoning,
                "tool_calls": [{"id": call["id"], "type": "function", "function": {
                    "name": call["name"], "arguments": json.dumps(call["args"])}} for call in calls]}}],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        model = ReasoningPreservingChatDeepSeek(model="deepseek-v4-pro", api_key=SecretStr("offline-no-network"),
            http_client=client, max_retries=0, use_responses_api=False, extra_body={"thinking": {"type": "enabled"}})
        adapter = DeepSeekStructuredAgentAdapter(
            config=_config().model_copy(update={"thinking": "enabled", "agentic_message_history": True}),
            chat_models={role: model for role in ("planner", "specialist", "counter", "lead")}, audit_sink=public.append)

        def model_turn(request):
            requests.append(request)
            # Explicit scripted qualification: no mock response is model proof.
            return adapter.specialist_model_turn(request)["action"]

        graph = build_dell_specialist_agentic_state_graph(dependencies=DellSpecialistAgenticDependencies(
            model_turn=model_turn, evidence_tool=ports.evidence, finance_tool=ports.finance)).compile()
        result = graph.invoke(_input(), config={"recursion_limit": 32})
    assert len(ports.calls) == 2  # Submissions/feedback never dispatch data tools.
    assert "reasoning_content" not in json.dumps(result) + json.dumps(public)
    return result, requests, wires


def test_terminal_schema_feedback_then_semantic_feedback_then_corrected_submission():
    result, requests, wires = _terminal_feedback_sdk_graph()
    assert len(requests) == 4
    feedback = json.loads(requests[2]["tool_results"][0]["content"])["feedback"][0]
    assert feedback["owner_layer"] == "agent"
    assert '"loc": ["claims", 0]' in feedback["message"]
    assert "reported_fact_requires_evidence" in feedback["message"]
    assert '"input"' not in feedback["message"] and '"ctx"' not in feedback["message"]
    wire_feedback = json.loads(wires[2]["messages"][-1]["content"])["result"]
    assert wire_feedback["feedback"][0] == feedback
    assert "unknown_evidence_id:E:invented" in json.dumps(requests[3]["notebook"]["feedback"])
    assert result["phase"] == "specialist_submission_accepted"
    assert (result["notebook"]["model_turn_count"], result["notebook"]["tool_action_count"]) == (4, 2)
    assert result["final_submission"]["claims"][0]["evidence_ids"] == ["E:DELL:Q1"]


@pytest.mark.parametrize("terminal", ["submission", "handoff"])
def test_valid_single_terminal_batch_uses_existing_control_route_not_data_port(terminal):
    ports, requests = _ToolPorts(), []

    def model(request):
        requests.append(request)
        if len(requests) == 1:
            return _batch(request, [_evidence_action()({}), _finance_action()({})])
        return _batch(request, [_submission()(request) if terminal == "submission" else _handoff(request)])

    graph = build_dell_specialist_agentic_state_graph(dependencies=DellSpecialistAgenticDependencies(
        model_turn=model, evidence_tool=ports.evidence, finance_tool=ports.finance)).compile()
    result = graph.invoke(_input(), config={"recursion_limit": 32})
    assert len(requests) == 2 and len(ports.calls) == 2
    assert result["notebook"]["tool_action_count"] == 2
    if terminal == "submission":
        assert result["phase"] == "specialist_submission_accepted"
    else:
        assert result["human_review_handoff"]["trigger"] == "model_request"


@pytest.mark.local_data_integration
def test_immutable_r9_missing_evidence_ids_reach_model_as_field_errors():
    audit_path = Path("Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/q1_specialist_paid_shadow/attempts/"
                      "20260905-dell-q1-native-tool-batch-enabled-r9/model-context-reasoning.private.jsonl")
    if not audit_path.exists():
        pytest.skip("immutable R9 private counterexample unavailable")
    original = audit_path.read_bytes()
    raw = json.loads(original.decode("utf-8").splitlines()[-1])["raw_response"]
    result, requests, wires = _terminal_feedback_sdk_graph(saved_raw=raw)
    feedback = requests[2]["tool_results"][0]
    message = json.loads(feedback["content"])["feedback"][0]["message"]
    assert feedback["status"] == "error"
    assert '"loc": ["claims", 11]' in message and '"loc": ["claims", 13]' in message
    assert message.count("reported_fact_requires_evidence") == 2
    previous_assistant = [m for m in wires[2]["messages"] if m["role"] == "assistant"][-1]
    assert previous_assistant["reasoning_content"] == raw["additional_kwargs"]["reasoning_content"]
    assert result["final_submission"] is None  # Counterexample is NOT repaired research proof.
    assert result["human_review_handoff"]["trigger"] == "model_request"
    assert audit_path.read_bytes() == original
