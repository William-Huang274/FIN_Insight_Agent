"""Review collaboration contracts; scripted fixtures are not model quality proof."""
from copy import deepcopy
import json
from pathlib import Path
from threading import Barrier

import pytest

from sec_agent.agent_runtime.research_graph_contracts import canonical_sha256
from sec_agent.agent_runtime.specialist_graph import (
    SpecialistAgenticDependencies, SpecialistAgenticGraphError,
    SpecialistAgenticInput, SpecialistNotebook, SubmitReviewAction,
    _review_submission_errors, build_specialist_agentic_state_graph,
)
from sec_agent.agent_runtime.workpaper_review_graph import (
    WorkpaperReviewError, _review_seed,
    build_workpaper_review_graph, collaboration_context, validate_workpaper_state,
)
from test_specialist_graph import (
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
    graph = build_specialist_agentic_state_graph(dependencies=SpecialistAgenticDependencies(
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
    result = build_workpaper_review_graph(expected_input=expected, seed_state=seed,
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
    result = build_workpaper_review_graph(expected_input=expected, seed_state=seed,
        run_child=run_child).compile().invoke(expected.model_dump(mode="json"))
    assert result["phase"] == "review_cycle_needs_attention" and result["review_stop_reason"] == reason


def _stopped_review():
    def run_child(role, ctx, config):
        return _execute(ctx, (lambda req: {**_submission()(req), "context_digest": req["context_digest"]})
                        if role == "repair" else (lambda req: _review(req, material=True)))
    expected = SpecialistAgenticInput.model_validate_json(json.dumps(_input()))
    return build_workpaper_review_graph(expected_input=expected, seed_state=_seed(),
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
    result = build_workpaper_review_graph(expected_input=expected, seed_state=stopped,
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
    with pytest.raises(WorkpaperReviewError):
        _review_seed(stopped)


def test_completed_sibling_findings_survive_error_but_fresh_review_still_requires_both_roles():
    stopped = _stopped_review()
    stopped["phase"] = "reviewing"
    stopped["review_stop_reason"] = None
    stopped["review_results"] = [r for r in stopped["review_results"] if r["round"] == 1 and r["role"] == "verifier"]
    with pytest.raises(WorkpaperReviewError):
        _review_seed({"values": stopped, "tasks": []})  # active/incomplete is not a stopped artifact
    envelope = {"values": stopped, "tasks": [{"name": "reviewer", "error": "known completed truncated response"}]}
    _, findings = _review_seed(envelope)
    assert findings
    calls = []
    def run_child(role, ctx, config):
        calls.append(role)
        return _execute(ctx, (lambda req: {**_submission()(req), "context_digest": req["context_digest"]})
                        if role == "repair" else (lambda req: _review(req)))
    expected = SpecialistAgenticInput.model_validate_json(json.dumps(_input()))
    result = build_workpaper_review_graph(expected_input=expected, seed_state=envelope,
        run_child=run_child).compile().invoke(expected.model_dump(mode="json"))
    assert calls[0] == "repair" and sorted(calls[1:]) == ["counter", "verifier"]
    assert result["phase"] == "review_cycle_accepted" and len(result["review_results"]) == 2


def test_failed_fanout_without_collected_reviews_reuses_author_but_reviews_both_again():
    state = {"phase": "reviewing", "review_results": [], "review_round": 0, "target_state": _seed()}
    with pytest.raises(WorkpaperReviewError):
        _review_seed({"values": state, "tasks": []})
    envelope = {"values": state, "tasks": [{"name": "reviewer", "error": "invalid JSON and sibling cancellation"}]}
    original, calls = deepcopy(envelope), []
    def run_child(role, ctx, config):
        calls.append(role)
        assert role in {"counter", "verifier"} and not ctx["findings"]
        return _execute(ctx, _review)
    expected = SpecialistAgenticInput.model_validate_json(json.dumps(_input()))
    result = build_workpaper_review_graph(expected_input=expected, seed_state=envelope,
        run_child=run_child).compile().invoke(expected.model_dump(mode="json"))
    assert sorted(calls) == ["counter", "verifier"]
    assert result["phase"] == "review_cycle_accepted" and not result["repair_results"]
    assert result["target_state"]["final_submission"] == state["target_state"]["final_submission"]
    assert envelope == original


def test_collaboration_rejects_wrong_scope_before_model():
    ctx = collaboration_context(_seed(), "verifier")
    ctx["target_notebook"]["inventory_snapshot_digest"] = "0" * 64
    ctx["target_notebook"]["notebook_digest"] = canonical_sha256(
        {k: v for k, v in ctx["target_notebook"].items() if k != "notebook_digest"})
    with pytest.raises(SpecialistAgenticGraphError, match="collaboration_data_scope_mismatch"):
        _execute(ctx, lambda _: pytest.fail("must not call model"))


def test_review_authority_requires_explicit_scope_and_three_node_budgets(tmp_path):
    from test_model_execution_policy import _authority
    from test_deepseek_structured_agents import _config
    from sec_agent.agent_runtime.model_execution_policy import ModelExecutionAuthority
    from pydantic import ValidationError
    body = _authority(tmp_path).model_dump(mode="json", exclude={"decision_digest"})
    body.update(workflow="workpaper_review_repair", serving_mode="q1_workpaper_review_repair_v1",
        other_model_nodes_authorized=True, source_read_enabled=True, private_reasoning_audit_authorized=True,
        review_scope={"seed_state_relative_path": "fixture-seed/specialist-final-state.private.json", "seed_state_sha256": "a" * 64,
            "node_budgets": {role: _config().token_budget_basis["specialist"].model_dump(mode="json")
                             for role in ("counter", "verifier", "repair")},
            "max_reviewer_model_turns": 6, "max_reviewer_tool_actions": 8, "max_author_revisions": 1})
    def validate(data):
        return ModelExecutionAuthority.model_validate_json(json.dumps(
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
