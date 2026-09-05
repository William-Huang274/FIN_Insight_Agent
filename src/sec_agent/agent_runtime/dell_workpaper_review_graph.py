"""LangGraph evaluator/optimizer composition using the existing agentic subgraph.

This owns only FIN artifact handoff, finding disposition and revision semantics.
Scheduling, parallelism and checkpoints stay in LangGraph/Agent Server. It is a
bounded Q1 collaboration slice, not a full-case Lead planner or a resume engine.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
import json
import operator
from typing import Annotated, Any, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from .dell_reference_vertical_contracts import canonical_sha256
from .dell_specialist_agentic_graph import (
    SpecialistAgenticInput, SpecialistCollaborationContext, SpecialistNotebook,
    SubmitReviewAction, SubmitWorkpaperAction, _review_submission_errors,
)


class DellWorkpaperReviewError(ValueError):
    pass


class WorkpaperReviewState(TypedDict, total=False):
    # Same public entry input; the source artifact is loaded by the host, not API input.
    schema_version: str
    run_id: str
    run_invocation_id: str
    agent_id: str
    task: dict[str, Any]
    required_route_obligation_ids: list[str]
    l0_context: dict[str, Any]
    max_model_turns: int
    max_tool_actions: int
    collaboration_context: dict[str, Any] | None
    target_state: dict[str, Any]
    review_round: int
    review_results: Annotated[list[dict[str, Any]], operator.add]
    repair_results: Annotated[list[dict[str, Any]], operator.add]
    phase: str
    review_stop_reason: str | None
    final_submission: dict[str, Any] | None
    inherited_review_findings: list[dict[str, Any]]
    # Only present in Send worker inputs, never externally supplied authority.
    review_role: str


def validate_workpaper_state(value: Mapping[str, Any]) -> dict[str, Any]:
    state = dict(value.get("values", value))
    notebook = SpecialistNotebook.model_validate_json(json.dumps(state["notebook"]))
    submission = SubmitWorkpaperAction.model_validate_json(json.dumps(state["final_submission"]))
    if state.get("phase") != "specialist_submission_accepted" or notebook.status != "submitted":
        raise DellWorkpaperReviewError("review_source_not_a_submitted_workpaper")
    if (notebook.agent_id != state["agent_id"] or notebook.branch_id != state["task"]["branch_id"]
        or notebook.task_revision != state["task"]["revision"]):
        raise DellWorkpaperReviewError("review_source_identity_mismatch")
    return {"agent_id": notebook.agent_id, "task": state["task"],
            "notebook": notebook.model_dump(mode="json"),
            "final_submission": submission.model_dump(mode="json"),
            "phase": state["phase"]}


def collaboration_context(target: Mapping[str, Any], mode: str,
                          findings: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return SpecialistCollaborationContext.model_validate_json(json.dumps({
        "mode": mode, "target_agent_id": target["agent_id"],
        "target_submission": target["final_submission"],
        "target_notebook": target["notebook"], "findings": findings or [],
    })).model_dump(mode="json")


ChildRunner = Callable[[str, Mapping[str, Any], RunnableConfig], Mapping[str, Any]]


def _merge_observations(target, rows):
    """Create a handoff view; never modify the archived source workpaper."""
    target = json.loads(json.dumps(target))
    notebook = target["notebook"]
    observations = {o["observation_digest"]: o for o in notebook["observations"]}
    for row in rows:
        for observation in row["agent_state"]["notebook"]["observations"]:
            observations.setdefault(observation["observation_digest"], observation)
    notebook["observations"] = list(observations.values())
    notebook["notebook_digest"] = canonical_sha256({k: v for k, v in notebook.items() if k != "notebook_digest"})
    return target


def _review_seed(value):
    """An explicitly authorized new run may consume a stopped review artifact.

    This is artifact handoff, not server/conversation resume or an automatic retry.
    Previous model calls are not copied into the new run's execution counters.
    """
    state = dict(value.get("values", value))
    if "target_state" not in state:
        return validate_workpaper_state(state), []
    partial_error = state.get("phase") == "reviewing" and any(t.get("error") for t in value.get("tasks", []))
    if not partial_error and (state.get("phase") != "review_cycle_needs_attention"
        or state.get("review_stop_reason") != "material_findings_remain_after_one_revision"):
        raise DellWorkpaperReviewError("review_successor_requires_stopped_author_findings")
    target = validate_workpaper_state(state["target_state"])
    rows = [row for row in state["review_results"] if row["round"] == state["review_round"]]
    roles = {r["role"] for r in rows}
    if (not 1 <= len(rows) <= 2 or len(roles) != len(rows) or not roles.issubset({"counter", "verifier"})
        or (not partial_error and len(rows) != 2)):
        raise DellWorkpaperReviewError("review_successor_reviews_incomplete")
    findings = []
    for row in rows:
        review = SubmitReviewAction.model_validate_json(json.dumps(row["review"]))
        notebook = SpecialistNotebook.model_validate_json(json.dumps(row["agent_state"]["notebook"]))
        if (row["target_digest"] != canonical_sha256(target["final_submission"])
            or row["agent_state"].get("phase") != "specialist_submission_accepted"
            or not notebook.agent_id.startswith(row["role"] + ":")
            or _review_submission_errors(review, notebook, collaboration_context(target, row["role"]))):
            raise DellWorkpaperReviewError("review_successor_finding_binding_invalid")
        findings.extend(review.model_dump(mode="json")["findings"])
    material = [f for f in findings if f["severity"] in {"high", "medium"}]
    if not material or any(f["responsible_owner"] != "author" for f in material):
        raise DellWorkpaperReviewError("review_successor_not_an_author_repair")
    return _merge_observations(target, rows), findings


def build_dell_workpaper_review_graph(*, expected_input: SpecialistAgenticInput | None,
                                     seed_state: Mapping[str, Any] | None,
                                     run_child: ChildRunner) -> StateGraph:
    """Two independent reviewers, at most one author repair, then fresh review."""
    seed, inherited_findings = _review_seed(seed_state) if seed_state is not None else (None, [])
    if expected_input is not None:
        l0 = expected_input.l0_context
        for key in ("owner_data_gate_decision_digest", "source_route_catalog_digest", "inventory_snapshot_digest"):
            if seed["notebook"][key] != getattr(l0, key):
                raise DellWorkpaperReviewError("review_seed_current_data_binding_mismatch")
        if (seed["task"]["snapshot_id"] != expected_input.task.snapshot_id
            or seed["task"]["research_as_of"] != expected_input.task.research_as_of
            or seed["task"]["branch_id"] != expected_input.task.branch_id):
            raise DellWorkpaperReviewError("review_seed_case_binding_mismatch")
    expected_digest = canonical_sha256(expected_input) if expected_input else None

    def initialize(state):
        if expected_digest is None or seed is None:
            raise DellWorkpaperReviewError("review_schema_only_graph_not_executable")
        body = dict(state)
        # LangGraph initializes additive reducer channels before START.
        for key in ("review_results", "repair_results"):
            if body.pop(key, []) != []:
                raise DellWorkpaperReviewError("review_entry_cannot_supply_prior_results")
        parsed = SpecialistAgenticInput.model_validate_json(json.dumps(body))
        if canonical_sha256(parsed) != expected_digest or parsed.collaboration_context is not None:
            raise DellWorkpaperReviewError("review_entry_input_mismatch")
        return {"target_state": seed, "review_round": 0, "review_results": [],
                "repair_results": [], "final_submission": seed["final_submission"],
                "inherited_review_findings": inherited_findings,
                "phase": "author_repair_required" if inherited_findings else "reviewing", "review_stop_reason": None}

    def dispatch(state):
        return [Send("reviewer", {"review_role": role, "review_round": state["review_round"],
                                  "target_state": state["target_state"]})
                for role in ("verifier", "counter")]

    def reviewer(state, config: RunnableConfig):
        role = state["review_role"]
        target = state["target_state"]
        result = dict(run_child(role, collaboration_context(target, role), config))
        accepted = result.get("phase") == "specialist_submission_accepted"
        review = None
        if accepted:
            review = SubmitReviewAction.model_validate_json(json.dumps(result["final_submission"]))
            if review.target_submission_digest != canonical_sha256(target["final_submission"]):
                raise DellWorkpaperReviewError("review_result_target_mismatch")
        return {"review_results": [{"role": role, "round": state["review_round"],
                "target_digest": canonical_sha256(target["final_submission"]),
                "review": review.model_dump(mode="json") if review else None, "agent_state": result}]}

    def disposition(state):
        rows = [row for row in state["review_results"] if row["round"] == state["review_round"]]
        if len(rows) != 2 or {row["role"] for row in rows} != {"verifier", "counter"}:
            raise DellWorkpaperReviewError("review_parallel_barrier_incomplete")
        if any(row["review"] is None for row in rows):
            return {"phase": "review_cycle_needs_attention", "review_stop_reason": "reviewer_did_not_submit"}
        findings = [f for row in rows for f in row["review"]["findings"] if f["severity"] in {"high", "medium"}]
        if not findings:
            return {"phase": "review_cycle_accepted", "review_stop_reason": None}
        if any(f["responsible_owner"] != "author" for f in findings):
            return {"phase": "review_cycle_needs_attention", "review_stop_reason": "finding_requires_data_tool_or_human_owner"}
        if state["review_round"] >= 1:
            return {"phase": "review_cycle_needs_attention", "review_stop_reason": "material_findings_remain_after_one_revision"}
        return {"phase": "author_repair_required"}

    def repair(state, config: RunnableConfig):
        rows = [row for row in state["review_results"] if row["round"] == state["review_round"]]
        findings = ([f for row in rows for f in row["review"]["findings"]]
                    if rows else state["inherited_review_findings"])
        # Evidence read by either reviewer accompanies its finding. Preserve
        # source observation identities; do not turn candidate data into Evidence.
        target = _merge_observations(state["target_state"], rows)
        result = dict(run_child("repair", collaboration_context(target, "repair", findings), config))
        update = {"repair_results": [{"parent_submission_digest": canonical_sha256(state["target_state"]["final_submission"]),
                                       "findings": findings, "agent_state": result}]}
        if result.get("phase") != "specialist_submission_accepted":
            return {**update, "phase": "review_cycle_needs_attention", "review_stop_reason": "author_did_not_submit_revision"}
        revised = validate_workpaper_state(result)
        if (revised["agent_id"] != state["target_state"]["agent_id"]
            or revised["task"]["revision"] != state["target_state"]["task"]["revision"] + 1):
            raise DellWorkpaperReviewError("repair_owner_changed")
        return {**update, "target_state": revised, "review_round": state["review_round"] + 1,
                "final_submission": revised["final_submission"], "phase": "reviewing"}

    graph = StateGraph(WorkpaperReviewState, input_schema=SpecialistAgenticInput)
    graph.add_node("initialize_review", initialize)
    graph.add_node("reviewer", reviewer)
    graph.add_node("review_disposition", disposition)
    graph.add_node("responsible_author_repair", repair)
    graph.add_edge(START, "initialize_review")
    graph.add_conditional_edges("initialize_review",
        lambda state: "responsible_author_repair" if state["phase"] == "author_repair_required" else dispatch(state),
        ["reviewer", "responsible_author_repair"])
    graph.add_edge("reviewer", "review_disposition")
    graph.add_conditional_edges("review_disposition", lambda state: "repair" if state["phase"] == "author_repair_required" else "end",
                                {"repair": "responsible_author_repair", "end": END})
    graph.add_conditional_edges("responsible_author_repair", lambda state: dispatch(state) if state["phase"] == "reviewing" else END,
                                ["reviewer", END])
    return graph
