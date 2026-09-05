"""Lead/worker plumbing qualification, not a financial or paid-model verdict."""
from copy import deepcopy
import json
from pathlib import Path
from threading import Barrier

import httpx
import pytest
from pydantic import SecretStr, ValidationError

from sec_agent.agent_runtime.dell_lead_research_graph import build_dell_lead_research_graph
from sec_agent.agent_runtime.dell_reference_vertical_contracts import canonical_sha256
from sec_agent.agent_runtime.dell_specialist_agentic_graph import SpecialistAgenticInput
from sec_agent.agent_runtime.deepseek_structured_agents import (
    DeepSeekStructuredAgentAdapter, ReasoningPreservingChatDeepSeek,
)
from test_dell_specialist_agentic_graph import _input
from test_dell_workpaper_review_graph import _seed


BRANCHES = ("Q5_SUPPLY_AND_PRICE", "Q6_MODEL_COMPUTE_DEMAND")
CATALOG = [{"branch_id": key, "objective": "Synthetic task qualification; no research answer."} for key in BRANCHES]


def _task(key="price", branch=BRANCHES[0], dependencies=()):
    return {"task_id": "task:" + key, "owner_role": "research_analyst",
            "objective": "按已披露资料自主研究供应或行业需求，说明依据及局限。",
            "dependency_ids": list(dependencies), "coverage_obligation_ids": [branch],
            "success_criteria": ["自主读取来源，不将上游底稿冒充证据。"],
            "requested_capability_refs": ["capability:dell:reviewed-evidence"],
            "expected_output_kinds": ["branch_notebook", "claim_ledger"], "materiality": "high"}


def _call(request, name, **args):
    return {"action": {"action": "native_tool_batch", "context_digest": request["context_digest"],
            "tool_calls": [{"id": f'lead-{request["progress"]["turn_index"]}', "name": name,
                "args": {"context_digest": request["context_digest"], "reason_summary": "确定性资格测试。", **args}}]}}


def _stop(request, *, incomplete=(), ready=False):
    return _call(request, "SubmitResearchHandoffAction", disposition="ready_for_review" if ready else "needs_attention",
                 synthesis_notes="确定性工具流转测试，不是研究结论。", acknowledged_incomplete_task_ids=list(incomplete))


def _worker_result(task, seed):
    result = deepcopy(seed)
    result["task"].update(task_id=task["task_id"], branch_id=task["coverage_obligation_ids"][0], objective=task["objective"])
    result["agent_id"] = "specialist:" + task["task_id"]
    result["notebook"].update(task_id=task["task_id"], branch_id=task["coverage_obligation_ids"][0], agent_id=result["agent_id"])
    result["notebook"]["notebook_digest"] = canonical_sha256({k: v for k, v in result["notebook"].items() if k != "notebook_digest"})
    return result


def _graph(model, worker, *, seed=None, **kwargs):
    seed = seed or _seed()
    value = SpecialistAgenticInput.model_validate_json(json.dumps(_input()))
    return build_dell_lead_research_graph(expected_input=value, research_question="Dell 供给价格与行业需求的关联是什么？",
        branch_catalog=CATALOG, allowed_branch_ids=BRANCHES, seed_workpapers={seed["task"]["task_id"]: seed},
        model_turn=model, run_child=worker, **kwargs).compile(), value


def test_lead_parallel_workers_then_dynamic_dependent_task_without_rewriting_seed():
    seed = _seed()
    original, seen, workers = deepcopy(seed), [], []
    barrier = Barrier(2, timeout=4)

    def model(request):
        seen.append(request)
        if len(seen) == 1:
            return _call(request, "DelegateResearchTasksAction", tasks=[
                _task(dependencies=(seed["task"]["task_id"],)), _task("compute", BRANCHES[1])])
        if len(seen) == 2:
            assert len(json.loads(request["tool_results"][0]["content"])["task_results"]) == 2
            return _call(request, "DelegateResearchTasksAction", tasks=[_task("followup", dependencies=("task:price", "task:compute"))])
        return _stop(request, ready=True)

    def worker(task, dependencies, config):
        workers.append(task["task_id"])
        if task["task_id"] in {"task:price", "task:compute"}:
            barrier.wait()  # Actual independent LangGraph Send workers must overlap.
        else:
            assert set(dependencies) == {"task:price", "task:compute"}
        return _worker_result(task, seed)

    graph, value = _graph(model, worker, seed=seed)
    result = graph.invoke(value.model_dump(mode="json"))
    assert result["phase"] == "research_ready_for_review"
    assert len(result["tasks"]) == len(result["task_results"]) == 3
    assert workers[-1] == "task:followup" and len(seen) == 3 and seed == original
    assert all(row["runtime_receipt"] is None for row in result["lead_turns"])
    assert "final_submission" not in result  # Handoff is not a financial report.


@pytest.mark.parametrize("defect", ["cycle", "dependency", "duplicate", "capability", "authority", "branch", "status", "schema", "invalid_json", "multiple_mutations", "premature_completion"])
def test_invalid_lead_action_reaches_next_turn_without_worker_execution(defect):
    seen, executions = [], []
    def model(request):
        seen.append(request)
        if len(seen) > 1:
            assert all(row["status"] == "error" for row in request["tool_results"])
            return _stop(request)
        task = _task()
        tasks = [task]
        if defect == "cycle":
            task["dependency_ids"] = ["task:compute"]
            tasks.append(_task("compute", BRANCHES[1], ("task:price",)))
        elif defect == "dependency": task["dependency_ids"] = ["task:unknown"]
        elif defect == "duplicate": tasks.append(deepcopy(task))
        elif defect == "capability": task["requested_capability_refs"] = ["arbitrary-shell"]
        elif defect == "authority": task["required_authority_refs"] = ["admin"]
        elif defect == "branch": task["coverage_obligation_ids"] = ["Q7_EXPORT_CONTROL_CHINA"]
        elif defect == "status": task["status"] = "completed"
        elif defect == "schema": task["objective"] = ""
        if defect == "premature_completion": return _stop(request, ready=True)
        call = _call(request, "DelegateResearchTasksAction", tasks=tasks)
        if defect == "invalid_json": call["action"]["tool_calls"][0].update(args='{"tasks":', type="invalid_tool_call")
        elif defect == "multiple_mutations":
            second = deepcopy(call["action"]["tool_calls"][0]); second["id"] += "-second"
            call["action"]["tool_calls"].append(second)
        return call
    graph, value = _graph(model, lambda *args: executions.append(args))
    result = graph.invoke(value.model_dump(mode="json"))
    assert not executions and result["phase"] == "research_needs_attention" and len(seen) == 2


def test_native_sdk_lead_history_keeps_own_reasoning_and_exact_tool_feedback():
    from test_dell_deepseek_structured_agents import _config
    seen, wires, events = [], [], []
    def transport(request):
        wire = json.loads(request.content); wires.append(wire)
        current = seen[-1]
        if len(wires) == 1:
            name, arguments = "DelegateResearchTasksAction", '{"tasks":'
        else:
            call = _stop(current)["action"]["tool_calls"][0]
            name, arguments = call["name"], json.dumps(call["args"])
        return httpx.Response(200, json={"id": "synthetic-lead-wire", "object": "chat.completion", "created": 1,
            "model": "deepseek-v4-pro", "choices": [{"index": 0, "finish_reason": "tool_calls", "message": {
                "role": "assistant", "content": "", "reasoning_content": "synthetic private planning reasoning",
                "tool_calls": [{"id": f"wire-{len(wires)}", "type": "function", "function": {"name": name, "arguments": arguments}}]}}],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}})
    client = httpx.Client(transport=httpx.MockTransport(transport))
    model = ReasoningPreservingChatDeepSeek(model="deepseek-v4-pro", api_key=SecretStr("offline-no-network"),
        http_client=client, max_retries=0, use_responses_api=False)
    config = _config().model_copy(update={"agentic_message_history": True, "thinking": "enabled"})
    adapter = DeepSeekStructuredAgentAdapter(config=config, chat_models={role: model for role in ("planner", "specialist", "counter", "lead")}, audit_sink=events.append)
    def turn(request):
        seen.append(request)
        result = adapter.lead_research_turn(request)
        # The mock SDK receipt is validated, but this test must not claim paid execution.
        assert result["runtime_receipt"]["kind"] == "model"
        return result
    graph, value = _graph(turn, lambda *args: pytest.fail("invalid plan must not run workers"), turn_source="provider_model")
    try: result = graph.invoke(value.model_dump(mode="json"))
    finally: client.close()
    assert result["phase"] == "research_needs_attention" and len(wires) == 2
    assert {row["function"]["name"] for row in wires[0]["tools"]} == {"DelegateResearchTasksAction", "ContinueResearchTasksAction", "SubmitResearchHandoffAction"}
    assert wires[1]["messages"][2]["reasoning_content"] == "synthetic private planning reasoning"
    assert wires[1]["messages"][3]["tool_call_id"] == "wire-1"
    assert "Expecting value" in wires[1]["messages"][3]["content"]
    assert "workpapers" not in json.loads(wires[1]["messages"][3]["content"])["current_context"]
    assert all("semantic_input" not in event and "raw_response" not in event for event in events)


@pytest.mark.local_data_integration
def test_actual_a5_to_two_delegated_real_mcp_loops_zero_provider():
    from test_dell_specialist_agentic_composition import RUNTIME_ENVIRONMENT, _assert_assets
    from sec_agent.agent_runtime.dell_specialist_agentic_composition import open_dell_specialist_scripted_qualification_composition
    _assert_assets()
    path = Path("Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/q1_specialist_paid_shadow/attempts/20260906-dell-q1-agentic-review-repair-a5/specialist-final-state.private.json")
    if not path.exists(): pytest.skip("accepted A5 artifact unavailable")
    original = path.read_bytes(); seed = json.loads(original)["values"]["target_state"]
    seen = []
    def lead(request):
        seen.append(request)
        if len(seen) == 1:
            tasks = [_task(dependencies=(seed["task"]["task_id"],)), _task("compute", BRANCHES[1], (seed["task"]["task_id"],))]
            for task in tasks:
                task["requested_capability_refs"] = ["capability:dell:source-document-read", "capability:dell:financial-fact-query"]
            return _call(request, "DelegateResearchTasksAction", tasks=tasks)
        return _stop(request, incomplete=("task:price", "task:compute"))
    def worker(task, dependencies, config):
        turns = []
        def scripted(request):
            turns.append(request)
            common = {"context_digest": request["context_digest"], "reason_summary": "真实本地工具的零模型测试。"}
            if len(turns) == 1: return {**common, "action": "request_source", "selection": {"operation": "catalog"}}
            if len(turns) == 2: return {**common, "action": "request_finance", "intent": {"ticker": "DELL", "metric_ids": ["revenue"],
                "granularity": "quarter_discrete", "selection_mode": "exact_period_end", "period_end": "2026-05-01"}}
            return {**common, "action": "request_human_review", "blocker_code": "zero_model_qualification_complete_not_research_pass"}
        with open_dell_specialist_scripted_qualification_composition(run_id="lead-local-qualification", run_invocation_id="lead-local-qualification-1",
            branch_id=task["coverage_obligation_ids"][0], environment=RUNTIME_ENVIRONMENT, scripted_model_turn=scripted,
            source_read_enabled=True, research_task=task, dependency_workpapers=dependencies) as child:
            result = child.graph.invoke(child.graph_input.model_dump(mode="json"), config=config)
        assert len(result["notebook"]["observations"]) == 2
        assert all(row["status"] == "success" for row in result["notebook"]["observations"])
        return result
    with open_dell_specialist_scripted_qualification_composition(run_id="lead-local-qualification", run_invocation_id="lead-local-qualification-1",
        branch_id="Q1_ISSUER_TRUTH", environment=RUNTIME_ENVIRONMENT, scripted_model_turn=lambda _: None, source_read_enabled=True) as parent:
        graph = build_dell_lead_research_graph(expected_input=parent.graph_input, research_question="零模型资格：验证双研究任务实际 MCP 流转。",
            branch_catalog=CATALOG, allowed_branch_ids=BRANCHES, seed_workpapers={seed["task"]["task_id"]: seed},
            model_turn=lead, run_child=worker).compile()
        result = graph.invoke(parent.graph_input.model_dump(mode="json"))
    assert result["phase"] == "research_needs_attention" and len(result["task_results"]) == 2, seen[1]["tool_results"]
    assert all(row["status"] == "needs_attention" for row in result["task_results"])
    assert path.read_bytes() == original and len(seen) == 2


@pytest.mark.local_data_integration
def test_q6_actual_source_passage_can_reach_review_without_claiming_reviewed_route_completion():
    from test_dell_specialist_agentic_composition import RUNTIME_ENVIRONMENT, _assert_assets
    from sec_agent.agent_runtime.dell_specialist_agentic_composition import open_dell_specialist_scripted_qualification_composition
    from sec_agent.agent_runtime.dell_specialist_agentic_graph import SpecialistNotebook, SubmitWorkpaperAction, _submission_errors
    _assert_assets()
    calls = []
    def model(request):
        calls.append(request)
        base = {"context_digest": request["context_digest"], "reason_summary": "Zero-model source binding test, not a research verdict."}
        items = [item for obs in request["notebook"]["observations"] for item in obs["content"]]
        if len(calls) == 1:
            return {**base, "action": "request_source", "selection": {"operation": "search", "query": "MLPerf Inference", "limit": 20}}
        if len(calls) == 2:
            row = next(row for row in items if row.get("issuer_id") == "MLCOMMONS")
            return {**base, "action": "request_source", "selection": {"operation": "read", "document_id": row["document_id"], "node_id": row["node_id"]}}
        if len(calls) > 3:
            return {**base, "action": "request_human_review", "blocker_code": "source_binding_test_rejected"}
        passage = next(row for row in items if row.get("result_state") == "source_bound_passage")
        return {**base, "action": "submit_workpaper", "terminal_state": "supported", "thesis": "Offline binding fixture only.",
            "mechanism": "A parsed primary-source passage is not Reviewed Evidence or S2 NumericFact.",
            "narrative_markdown": "This is a source-binding test, not a finding about Dell demand.",
            "claims": [{"claim_id": "fixture", "kind": "reported_fact", "materiality": "medium",
                "statement": "Source-binding fixture only.", "evidence_ids": [passage["passage_id"]],
                "citation_quotes": {passage["passage_id"]: passage["passage"][:80]},
                "authority_note": "Parsed source; no S2 numeric authority or independent semantic approval."}],
            "counterevidence": ["Benchmark results do not prove Dell shipments."], "what_would_change": ["Source or interpretation correction."],
            "open_gaps": ["Reviewed F9 metadata remains incomplete; local source binding is not coverage or a public-information gap."]}
    with open_dell_specialist_scripted_qualification_composition(run_id="lead-source-binding", run_invocation_id="lead-source-binding-1",
        branch_id=BRANCHES[1], environment=RUNTIME_ENVIRONMENT, scripted_model_turn=model, source_read_enabled=True) as c:
        state = c.graph.invoke(c.graph_input.model_dump(mode="json"))
    assert state["phase"] == "specialist_submission_accepted", state["notebook"]["feedback"]
    notebook = SpecialistNotebook.model_validate_json(json.dumps(state["notebook"]))
    action = SubmitWorkpaperAction.model_validate_json(json.dumps(state["final_submission"]))
    assert notebook.satisfied_route_obligation_ids == () and notebook.model_turn_count == 3
    assert _submission_errors(action.model_copy(update={"open_gaps": ()}), notebook)
    bad_claim = action.claims[0].model_copy(update={"citation_quotes": {action.claims[0].evidence_ids[0]: "FABRICATED_SOURCE_QUOTE"}})
    assert any("source_quote_not_in_observed_passage" in error for error in _submission_errors(action.model_copy(update={"claims": (bad_claim,)}), notebook))
    assert any("required_route_unsatisfied" in error for error in _submission_errors(action, notebook.model_copy(update={"source_read_enabled": False})))


@pytest.mark.local_data_integration
def test_actual_lead_a1_q6_tool_replay_returns_submission_errors_without_runtime_crash():
    from test_dell_specialist_agentic_composition import RUNTIME_ENVIRONMENT, _assert_assets
    from sec_agent.agent_runtime.dell_specialist_agentic_composition import open_dell_specialist_scripted_qualification_composition
    from sec_agent.agent_runtime.dell_specialist_agentic_graph import SpecialistNotebook, SubmitWorkpaperAction, _submission_errors
    _assert_assets()
    root = Path("Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/q1_specialist_paid_shadow/attempts/20260906-dell-lead-two-topic-a1")
    if not (root / "failed-receipt.json").exists(): pytest.skip("actual failed Lead A1 not available")
    archived = [json.loads(line) for line in (root / "model-context-reasoning.private.jsonl").read_text(encoding="utf-8").splitlines()]
    turns = [row for row in archived if row["actor"].startswith("specialist:Q6_MODEL_COMPUTE_DEMAND:")]
    parent = json.loads((root / "specialist-final-state.private.json").read_text(encoding="utf-8"))["values"]
    assignment = next(task for task in parent["tasks"] if task["coverage_obligation_ids"] == [BRANCHES[1]])
    seen, submission_errors = [], []
    def replay(request):
        seen.append(request)
        if len(seen) > len(turns):
            return {"action": "request_human_review", "context_digest": request["context_digest"],
                    "reason_summary": "Offline replay exhausted; no provider invoked or financial pass.", "blocker_code": "offline_replay_complete"}
        # Replay keeps exact model arguments and references except the new local
        # context binding. It never modifies the archived model response.
        calls = deepcopy(turns[len(seen)-1]["raw_response"]["tool_calls"])
        for call in calls:
            call["args"]["context_digest"] = request["context_digest"]
            if call["name"] == "SubmitWorkpaperAction":
                try:
                    action = SubmitWorkpaperAction.model_validate_json(json.dumps(call["args"]))
                except ValidationError:
                    continue  # Original bad schema still goes unchanged to ToolNode.
                notebook = SpecialistNotebook.model_validate_json(json.dumps(request["notebook"]))
                submission_errors.extend(_submission_errors(action, notebook))
        return {"action": "native_tool_batch", "context_digest": request["context_digest"], "tool_calls": calls}
    with open_dell_specialist_scripted_qualification_composition(run_id="lead-a1-q6-local-replay", run_invocation_id="lead-a1-q6-local-replay-1",
        branch_id=BRANCHES[1], environment=RUNTIME_ENVIRONMENT, scripted_model_turn=replay, source_read_enabled=True,
        research_task=assignment, dependency_workpapers={}, max_model_turns=16, max_tool_actions=24) as c:
        result = c.graph.invoke(c.graph_input.model_dump(mode="json"), config={"recursion_limit": 128})
    assert result["phase"] == "specialist_human_review_handoff_emitted"
    assert any("source_quote_not_in_observed_passage" in error for error in submission_errors)
    assert not any("reference_identity_conflict:SOURCELOC::" in error for error in submission_errors), submission_errors
    assert seen[-1]["notebook"]["feedback"][-1]["code"] == "specialist_submission_reference_validation_failed"


def test_full_runtime_feedback_is_preserved_and_citable_identity_conflicts_still_fail():
    from sec_agent.agent_runtime.dell_specialist_agentic_graph import SpecialistNotebook, SubmitWorkpaperAction, _feedback, _submission_errors
    message = "; ".join(f"source_quote_not_in_observed_passage:passage{i}:claim=claim{i}" for i in range(100))
    result = _feedback("submission_rejected", message, owner_layer="agent", next_actions=("correct_claim_ledger",))
    assert len(message) > 2000 and result.message == message
    seed = _seed()
    notebook = SpecialistNotebook.model_validate_json(json.dumps(seed["notebook"]))
    action = SubmitWorkpaperAction.model_validate_json(json.dumps(seed["final_submission"]))
    obs = next(obs for obs in notebook.observations if any(ref.writer_citable for ref in obs.references))
    ref = next(ref for ref in obs.references if ref.writer_citable)
    conflicting = ref.model_copy(update={"artifact_digest": "f" * 64 if ref.artifact_digest != "f" * 64 else "e" * 64})
    copied = obs.model_copy(update={"references": (conflicting,)})
    errors = _submission_errors(action, notebook.model_copy(update={"observations": (*notebook.observations, copied)}))
    assert f"reference_identity_conflict:{ref.ref_id}" in errors
