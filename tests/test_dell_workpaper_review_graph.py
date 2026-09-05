"""Review collaboration contracts; scripted fixtures are not model quality proof."""
from copy import deepcopy
import json
from pathlib import Path
from threading import Barrier

import pytest

from sec_agent.agent_runtime.dell_reference_vertical_contracts import canonical_sha256
from sec_agent.agent_runtime.dell_specialist_agentic_graph import (
    DellSpecialistAgenticDependencies, DellSpecialistAgenticGraphError,
    SpecialistAgenticInput, SpecialistNotebook, SubmitReviewAction,
    _review_submission_errors, build_dell_specialist_agentic_state_graph,
)
from sec_agent.agent_runtime.dell_workpaper_review_graph import (
    DellWorkpaperReviewError, _review_seed,
    build_dell_workpaper_review_graph, collaboration_context, validate_workpaper_state,
)
from test_dell_specialist_agentic_graph import (
    _input, _run, _ScriptedModel, _ToolPorts, _evidence_action, _finance_action, _submission,
)


def _seed():
    return _run(_ScriptedModel([_evidence_action(), _finance_action(), _submission()]), _ToolPorts())


def _review(request, *, material=False, owner="author"):
    ctx = request["collaboration_context"]
    target = ctx["target_submission"]
    return {"action": "submit_review", "context_digest": request["context_digest"],
            "reason_summary": "确定性测试审查，不是模型质量证明。",
            "target_submission_digest": canonical_sha256(target),
            "verdict": "repair_required" if material else "no_material_finding",
            "coverage_notes": "Fixture: checked the supplied prose and observed references; no financial truth claim.",
            "findings": [{"finding_id": "fixture-finding", "severity": "medium", "category": "uncertainty",
                "target_quote": target["narrative_markdown"], "affected_claim_ids": [],
                "evidence_refs": [], "rationale": "Deterministic fixture requires an explicit revision.",
                "required_change": "Revise the bounded interpretation.", "responsible_owner": owner}] if material else []}


def _child_input(context, base=None):
    value = deepcopy(base or _input())
    value["collaboration_context"] = context
    value["agent_id"] = (context["target_agent_id"] if context["mode"] == "repair"
                         else f'{context["mode"]}:Q1_ISSUER_TRUTH:r{context["target_notebook"]["task_revision"]}')
    value["task"]["revision"] = context["target_notebook"]["task_revision"] + (1 if context["mode"] == "repair" else 0)
    return value


def _execute(context, model, *, base=None):
    ports = _ToolPorts()
    graph = build_dell_specialist_agentic_state_graph(dependencies=DellSpecialistAgenticDependencies(
        model_turn=model, evidence_tool=ports.evidence, finance_tool=ports.finance)).compile()
    return graph.invoke(_child_input(context, base), {"recursion_limit": 80})


@pytest.mark.parametrize("defect,expected", [("anchor", "review_anchor_not_in_target"),
    ("reference", "review_unobserved_reference"), ("claim", "review_unknown_target_claim"),
    ("revision", "review_target_revision_mismatch")])
def test_review_rejects_wrong_anchor_reference_claim_or_revision(defect, expected):
    seed = _seed()
    ctx = collaboration_context(seed, "verifier")
    review = _review({"collaboration_context": ctx, "context_digest": "a" * 64}, material=True)
    if defect == "anchor":
        review["findings"][0]["target_quote"] = "invented quote"
    elif defect == "reference":
        review["findings"][0]["evidence_refs"] = ["invented-ref"]
    elif defect == "claim":
        review["findings"][0]["affected_claim_ids"] = ["invented-claim"]
    else:
        review["target_submission_digest"] = "0" * 64
    errors = _review_submission_errors(SubmitReviewAction.model_validate_json(json.dumps(review)),
        SpecialistNotebook.model_validate_json(json.dumps(seed["notebook"])), ctx)
    assert expected in errors[0]


def test_review_validation_feedback_is_a_real_next_turn_not_a_data_action():
    seen = []
    def model(request):
        seen.append(request)
        action = _review(request, material=True)
        if len(seen) == 1:
            action["findings"][0]["target_quote"] = "not in original"
        return {"action": "native_tool_batch", "context_digest": request["context_digest"], "tool_calls": [
            {"id": f"review-{len(seen)}", "name": "SubmitReviewAction", "args": action}]}
    result = _execute(collaboration_context(_seed(), "verifier"), model)
    assert result["phase"] == "specialist_submission_accepted"
    assert result["notebook"]["model_turn_count"] == 2 and result["notebook"]["tool_action_count"] == 0
    assert "review_anchor_not_in_target" in seen[1]["tool_results"][0]["content"]


def test_single_specialist_cannot_submit_review_and_reviewer_cannot_write_report():
    seed = _seed()
    seen = []
    def model(request):
        seen.append(request)
        if len(seen) == 1:
            return {**_submission()(request), "context_digest": request["context_digest"]}
        return _review(request)
    result = _execute(collaboration_context(seed, "counter"), model)
    assert len(seen) == 2
    assert seen[1]["notebook"]["feedback"][-1]["code"] == "specialist_action_not_available_in_current_runtime"
    assert result["final_submission"]["action"] == "submit_review"
    assert _review_submission_errors(SubmitReviewAction.model_validate_json(json.dumps(_review(
        {"collaboration_context": collaboration_context(seed, "verifier"), "context_digest": "a" * 64}))),
        SpecialistNotebook.model_validate_json(json.dumps(seed["notebook"])), None) == ("review_role_not_authorized",)


def test_reviewers_parallel_isolated_then_original_owner_repair_and_fresh_review():
    seed = _seed()
    original = deepcopy(seed)
    seen, barrier = [], Barrier(2, timeout=10)
    def run_child(role, ctx, config):
        seen.append(deepcopy(ctx))
        if role != "repair" and ctx["target_notebook"]["task_revision"] == 0:
            barrier.wait()
        if role == "repair":
            def model(request):
                result = _submission()(request)
                return {**result, "context_digest": request["context_digest"],
                        "narrative_markdown": "修订稿：有依据的有界结论。"}
        else:
            model = lambda request: _review(request, material=ctx["target_notebook"]["task_revision"] == 0)
        return _execute(ctx, model)
    expected = SpecialistAgenticInput.model_validate_json(json.dumps(_input()))
    result = build_dell_workpaper_review_graph(expected_input=expected, seed_state=seed,
        run_child=run_child).compile().invoke(expected.model_dump(mode="json"), {"max_concurrency": 2})
    assert seed == original
    assert result["phase"] == "review_cycle_accepted"
    assert len(result["review_results"]) == 4 and len(result["repair_results"]) == 1
    assert result["repair_results"][0]["agent_state"]["agent_id"] == original["agent_id"]
    assert result["final_submission"]["narrative_markdown"].startswith("修订稿")
    first = [c for c in seen if c["target_notebook"]["task_revision"] == 0 and c["mode"] != "repair"]
    assert len(first) == 2 and all(c["findings"] == [] for c in first)
    assert len({r["target_digest"] for r in result["review_results"]}) == 2


@pytest.mark.parametrize("case,reason", [("no_submission", "reviewer_did_not_submit"),
    ("data", "finding_requires_data_tool_or_human_owner"), ("still_material", "material_findings_remain_after_one_revision")])
def test_failure_or_unresolved_finding_never_becomes_pass(case, reason):
    seed = _seed()
    def run_child(role, ctx, config):
        if role == "repair":
            return _execute(ctx, lambda req: {**_submission()(req), "context_digest": req["context_digest"]})
        if case == "no_submission" and role == "counter":
            return _execute(ctx, lambda req: {"action": "request_human_review", "context_digest": req["context_digest"],
                "reason_summary": "Fixture unavailable.", "blocker_code": "fixture_unavailable"})
        return _execute(ctx, lambda req: _review(req, material=True, owner="data" if case == "data" else "author"))
    expected = SpecialistAgenticInput.model_validate_json(json.dumps(_input()))
    result = build_dell_workpaper_review_graph(expected_input=expected, seed_state=seed,
        run_child=run_child).compile().invoke(expected.model_dump(mode="json"))
    assert result["phase"] == "review_cycle_needs_attention" and result["review_stop_reason"] == reason


def _stopped_review():
    def run_child(role, ctx, config):
        return _execute(ctx, (lambda req: {**_submission()(req), "context_digest": req["context_digest"]})
                        if role == "repair" else (lambda req: _review(req, material=True)))
    expected = SpecialistAgenticInput.model_validate_json(json.dumps(_input()))
    return build_dell_workpaper_review_graph(expected_input=expected, seed_state=_seed(),
        run_child=run_child).compile().invoke(expected.model_dump(mode="json"))


def test_stopped_artifact_successor_repairs_first_without_replaying_old_model_calls():
    stopped = _stopped_review()
    original, calls = deepcopy(stopped), []
    def run_child(role, ctx, config):
        calls.append(role)
        if role == "repair":
            assert ctx["target_notebook"]["task_revision"] == 1 and ctx["findings"]
            model = lambda req: {**_submission()(req), "context_digest": req["context_digest"],
                                 "narrative_markdown": "第二版，旧审查制品驱动的新调用。"}
        else:
            assert ctx["target_notebook"]["task_revision"] == 2 and not ctx["findings"]
            model = lambda req: _review(req)
        return _execute(ctx, model)
    expected = SpecialistAgenticInput.model_validate_json(json.dumps(_input()))
    result = build_dell_workpaper_review_graph(expected_input=expected, seed_state=stopped,
        run_child=run_child).compile().invoke(expected.model_dump(mode="json"))
    assert calls[0] == "repair" and sorted(calls[1:]) == ["counter", "verifier"]
    assert result["phase"] == "review_cycle_accepted"
    assert result["target_state"]["task"]["revision"] == 2
    assert len(result["review_results"]) == 2 and len(result["repair_results"]) == 1
    assert stopped == original


@pytest.mark.parametrize("defect", ["not_stopped", "wrong_target", "wrong_anchor", "wrong_owner", "missing_reviewer"])
def test_successor_rejects_invalid_or_non_author_handoff_before_model(defect):
    stopped = _stopped_review()
    rows = [r for r in stopped["review_results"] if r["round"] == 1]
    if defect == "not_stopped":
        stopped["phase"] = "review_cycle_accepted"
    elif defect == "wrong_target":
        rows[0]["review"]["target_submission_digest"] = "0" * 64
    elif defect == "wrong_anchor":
        rows[0]["review"]["findings"][0]["target_quote"] = "not in the target"
    elif defect == "wrong_owner":
        rows[0]["review"]["findings"][0]["responsible_owner"] = "data"
    else:
        stopped["review_results"].remove(rows[0])
    with pytest.raises(DellWorkpaperReviewError):
        _review_seed(stopped)


@pytest.mark.local_data_integration
def test_real_a1_feedback_identifies_only_invalid_claim_quotes_and_preserves_accepted_span():
    from sec_agent.agent_runtime.dell_specialist_agentic_graph import SubmitWorkpaperAction, _submission_errors
    path = Path("Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/q1_specialist_paid_shadow/attempts/20260905-dell-q1-agentic-review-repair-a1/specialist-final-state.private.json")
    if not path.exists():
        pytest.skip("immutable A1 artifact unavailable")
    original = path.read_bytes()
    state = json.loads(original)["values"]
    notebook = SpecialistNotebook.model_validate_json(json.dumps(state["repair_results"][0]["agent_state"]["notebook"]))
    submission = notebook.model_turn_records[0].action
    assert isinstance(submission, SubmitWorkpaperAction)
    errors = _submission_errors(submission, notebook)
    assert len(errors) == 2
    assert all("claim=C8:" in e or "claim=C9:" in e for e in errors)
    assert all("claim=C7:" not in e for e in errors)
    body = submission.model_dump(mode="json")
    passage_id = next(ref for claim in body["claims"] for ref in claim["evidence_ids"] if ref.startswith("PASSAGE::"))
    passage = next(item["passage"] for obs in notebook.observations for item in obs.content if item.get("passage_id") == passage_id)
    # Two unchanged, independently contiguous snippets; this proves reference syntax,
    # not their entailment of the fixture claims. Semantic review remains separate.
    for claim in body["claims"]:
        if passage_id in claim["evidence_ids"]:
            claim["citation_quotes"][passage_id] = [passage[:80], passage[-80:]]
    assert not _submission_errors(SubmitWorkpaperAction.model_validate_json(json.dumps(body)), notebook)
    quoted = next(c for c in body["claims"] if passage_id in c["evidence_ids"])
    quoted["citation_quotes"][passage_id][1] = "fabricated span"
    assert "quote_index=1:" in _submission_errors(SubmitWorkpaperAction.model_validate_json(json.dumps(body)), notebook)[0]
    quoted["citation_quotes"][passage_id] = []
    assert _submission_errors(SubmitWorkpaperAction.model_validate_json(json.dumps(body)), notebook)
    seed, pending = _review_seed(state)
    assert seed["task"]["revision"] == 1 and any(f["category"] == "financial_reasoning" for f in pending)
    from test_dell_specialist_agentic_composition import RUNTIME_ENVIRONMENT
    from sec_agent.agent_runtime.dell_specialist_agentic_composition import open_dell_specialist_scripted_qualification_composition
    seen = []
    def driver(request):
        seen.append(request)
        if len(seen) == 1:
            return {"action": "request_source", "context_digest": request["context_digest"],
                    "reason_summary": "Actual revision-two source catalog read, no model.", "selection": {"operation": "catalog"}}
        return {"action": "request_human_review", "context_digest": request["context_digest"],
                "reason_summary": "End scripted compatibility check, not a research verdict.", "blocker_code": "qualification_done"}
    with open_dell_specialist_scripted_qualification_composition(run_id="test:a1-successor", run_invocation_id="test:a1-successor:1",
        branch_id="Q1_ISSUER_TRUTH", environment=RUNTIME_ENVIRONMENT, scripted_model_turn=driver,
        source_read_enabled=True, collaboration_context=collaboration_context(seed, "repair", pending)) as opened:
        assert opened.graph_input.task.revision == 2
        result = opened.graph.invoke(opened.graph_input.model_dump(mode="json"))
    assert result["notebook"]["tool_action_count"] == 1
    assert result["notebook"]["observations"][-1]["status"] == "success"
    assert path.read_bytes() == original


def test_collaboration_rejects_wrong_scope_before_model():
    ctx = collaboration_context(_seed(), "verifier")
    ctx["target_notebook"]["inventory_snapshot_digest"] = "0" * 64
    ctx["target_notebook"]["notebook_digest"] = canonical_sha256(
        {k: v for k, v in ctx["target_notebook"].items() if k != "notebook_digest"})
    with pytest.raises(DellSpecialistAgenticGraphError, match="collaboration_data_scope_mismatch"):
        _execute(ctx, lambda _: pytest.fail("must not call model"))


def test_actual_sdk_reviewer_tool_schema_and_actor_history_isolation():
    import httpx
    from pydantic import SecretStr
    from sec_agent.agent_runtime.deepseek_structured_agents import DeepSeekStructuredAgentAdapter, ReasoningPreservingChatDeepSeek
    from test_dell_deepseek_structured_agents import _config
    wires, private, public = [], [], []
    seed = _seed()
    def respond(req):
        wire = json.loads(req.content)
        wires.append(wire)
        first = json.loads(wire["messages"][1]["content"])
        mode = first["collaboration_context"]["mode"]
        context = first["context_digest"]
        if wire["messages"][-1]["role"] == "tool":
            last = json.loads(wire["messages"][-1]["content"])
            context = last.get("current_context", last)["context_digest"]
        action = _review({"collaboration_context": collaboration_context(seed, mode), "context_digest": context}, material=True)
        if len(wire["messages"]) == 2:
            action["findings"][0]["target_quote"] = "invalid first quote to prove real feedback"
        return httpx.Response(200, json={"id": f"mock-{len(wires)}", "object": "chat.completion", "created": 1,
            "model": "deepseek-v4-pro", "choices": [{"index": 0, "finish_reason": "tool_calls", "message": {
            "role": "assistant", "content": "", "reasoning_content": f"private-{mode}-fixture",
            "tool_calls": [{"id": f"call-{len(wires)}", "type": "function", "function": {
                "name": "SubmitReviewAction", "arguments": json.dumps(action)}}]}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}})
    model = ReasoningPreservingChatDeepSeek(model="deepseek-v4-pro", api_key=SecretStr("mock-no-network"),
        http_client=httpx.Client(transport=httpx.MockTransport(respond)), max_retries=0, use_responses_api=False,
        extra_body={"thinking": {"type": "enabled"}})
    config = _config().model_copy(update={"thinking": "enabled", "agentic_message_history": True})
    adapter = DeepSeekStructuredAgentAdapter(config=config,
        chat_models={r: model for r in ("planner", "specialist", "counter", "lead")},
        private_audit_sink=private.append, audit_sink=public.append)
    for role in ("counter", "verifier"):
        ports = _ToolPorts()
        graph = build_dell_specialist_agentic_state_graph(dependencies=DellSpecialistAgenticDependencies(
            model_turn=adapter.specialist_model_turn, evidence_tool=ports.evidence,
            finance_tool=ports.finance, turn_source="provider_model")).compile()
        result = graph.invoke(_child_input(collaboration_context(seed, role)))
        assert result["final_submission"]["action"] == "submit_review"
    assert len(wires) == 4
    assert all({t["function"]["name"] for t in w["tools"]} == {
        "RequestEvidenceAction", "RequestSourceAction", "RequestFinanceAction", "RequestHumanReviewAction", "SubmitReviewAction"} for w in wires)
    assert len(wires[2]["messages"]) == 2
    assert "private-counter-fixture" in json.dumps(wires[1]) and "private-counter-fixture" not in json.dumps(wires[2:])
    assert "private-" not in json.dumps(public) and "private-verifier-fixture" in json.dumps(private)


def test_review_authority_requires_explicit_scope_and_three_node_budgets(tmp_path):
    from test_dell_specialist_paid_shadow import _authority
    from test_dell_deepseek_structured_agents import _config
    from sec_agent.agent_runtime.dell_specialist_paid_shadow import DellQ1SpecialistPaidShadowAuthority
    from pydantic import ValidationError
    body = _authority(tmp_path).model_dump(mode="json", exclude={"decision_digest"})
    body.update(workflow="workpaper_review_repair", serving_mode="q1_workpaper_review_repair_v1",
        other_model_nodes_authorized=True, source_read_enabled=True, private_reasoning_audit_authorized=True,
        review_scope={"seed_state_relative_path": "fixture-seed/specialist-final-state.private.json", "seed_state_sha256": "a" * 64,
            "node_budgets": {role: _config().token_budget_basis["specialist"].model_dump(mode="json")
                             for role in ("counter", "verifier", "repair")},
            "max_reviewer_model_turns": 6, "max_reviewer_tool_actions": 8, "max_author_revisions": 1})
    def validate(data):
        return DellQ1SpecialistPaidShadowAuthority.model_validate_json(json.dumps(
            {**data, "decision_digest": canonical_sha256(data)}))
    assert validate(body).review_scope.max_author_revisions == 1
    bad = deepcopy(body)
    bad["other_model_nodes_authorized"] = False
    with pytest.raises(ValidationError, match="review_scope_authority_mismatch"):
        validate(bad)
    bad = deepcopy(body)
    bad["review_scope"]["node_budgets"].pop("counter")
    with pytest.raises(ValidationError, match="review_node_budget_set_invalid"):
        validate(bad)
    bad = deepcopy(body)
    bad["review_scope"]["seed_state_relative_path"] = "../secret.json"
    with pytest.raises(ValidationError):
        validate(bad)


@pytest.mark.local_data_integration
def test_real_r11_seed_handoff_approved_composition_no_model_no_rewrite():
    from test_dell_specialist_agentic_composition import RUNTIME_ENVIRONMENT, _assert_assets
    from sec_agent.agent_runtime.dell_specialist_agentic_composition import (
        open_dell_specialist_receipted_composition, open_dell_specialist_scripted_qualification_composition)
    from sec_agent.agent_runtime.deepseek_structured_agents import _project_agentic_specialist_request
    _assert_assets()
    path = Path("Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/q1_specialist_paid_shadow/attempts/20260905-dell-q1-native-tool-batch-enabled-r11/specialist-final-state.private.json")
    original = path.read_bytes()
    seed = validate_workpaper_state(json.loads(original))
    captured = []
    def turn(request):
        captured.append(request)
        # This test checks the real data composition and handoff; no new data call.
        return _review(request)
    with open_dell_specialist_receipted_composition(run_id="review-test", run_invocation_id="review-test-invocation",
        branch_id="Q1_ISSUER_TRUTH", turn_source="saved_response_replay", model_turn=turn,
        environment=RUNTIME_ENVIRONMENT, source_read_enabled=True,
        collaboration_context=collaboration_context(seed, "verifier")) as opened:
        graph_input = opened.graph_input.model_dump(mode="json")
        assert graph_input["agent_id"] == "verifier:Q1_ISSUER_TRUTH:r0"
        # Production composition includes the exact seed and pins its complete graph input.
        assert graph_input["collaboration_context"]["target_submission"] == seed["final_submission"]
    ctx = collaboration_context(seed, "verifier")
    # Run the shared graph with scripted qualification attribution; not a paid-model receipt.
    ports = _ToolPorts()
    graph = build_dell_specialist_agentic_state_graph(dependencies=DellSpecialistAgenticDependencies(
        model_turn=turn, evidence_tool=ports.evidence, finance_tool=ports.finance)).compile()
    result = graph.invoke(graph_input)
    projected = _project_agentic_specialist_request(captured[0])
    assert len(projected["progress"]["observations"]) == len(seed["notebook"]["observations"])
    assert "target_notebook" not in projected["collaboration_context"]
    assert "model_turn_records" not in json.dumps(projected["collaboration_context"])
    assert result["final_submission"]["action"] == "submit_review"
    real_requests = []
    def real_mcp_driver(request):
        real_requests.append(request)
        if len(real_requests) == 1:
            return {"action": "request_source", "context_digest": request["context_digest"],
                    "reason_summary": "Read the approved source catalog in this reviewer role.", "selection": {"operation": "catalog"}}
        return _review(request)
    with open_dell_specialist_scripted_qualification_composition(run_id="review-mcp-test", run_invocation_id="review-mcp-invocation",
        branch_id="Q1_ISSUER_TRUTH", scripted_model_turn=real_mcp_driver,
        environment=RUNTIME_ENVIRONMENT, source_read_enabled=True,
        collaboration_context=collaboration_context(seed, "counter")) as opened:
        live_data_result = opened.graph.invoke(opened.graph_input.model_dump(mode="json"))
    assert live_data_result["notebook"]["tool_action_count"] == 1
    assert live_data_result["notebook"]["observations"][-1]["status"] == "success"
    assert live_data_result["notebook"]["observations"][-1]["content"]
    assert path.read_bytes() == original
