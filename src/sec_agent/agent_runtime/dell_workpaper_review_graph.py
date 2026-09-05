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
    SubmitReviewAction, SubmitWorkpaperAction,
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
    # Only present in Send worker inputs, never externally supplied authority.
    review_role: str


def validate_workpaper_state(value: Mapping[str, Any]) -> dict[str, Any]:
    state = dict(value.get("values", value))
    notebook = SpecialistNotebook.model_validate_json(json.dumps(state["notebook"]))
    submission = SubmitWorkpaperAction.model_validate_json(json.dumps(state["final_submission"]))
    if state.get("phase") != "specialist_submission_accepted" or notebook.status != "submitted":
        raise DellWorkpaperReviewError("review_source_not_a_submitted_workpaper")
    if notebook.agent_id != state["agent_id"] or notebook.branch_id != state["task"]["branch_id"]:
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


def build_dell_workpaper_review_graph(*, expected_input: SpecialistAgenticInput | None,
                                     seed_state: Mapping[str, Any] | None,
                                     run_child: ChildRunner) -> StateGraph:
    """Two independent reviewers, at most one author repair, then fresh review."""
    seed = validate_workpaper_state(seed_state) if seed_state is not None else None
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
                "phase": "reviewing", "review_stop_reason": None}

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
        findings = [f for row in state["review_results"] if row["round"] == state["review_round"]
                    for f in row["review"]["findings"]]
        # Evidence read by either reviewer accompanies its finding. Preserve
        # source observation identities; do not turn candidate data into Evidence.
        target = json.loads(json.dumps(state["target_state"]))
        old_notebook = target["notebook"]
        observations = {o["observation_digest"]: o for o in old_notebook["observations"]}
        for row in state["review_results"]:
            if row["round"] == state["review_round"]:
                for observation in row["agent_state"]["notebook"]["observations"]:
                    observations.setdefault(observation["observation_digest"], observation)
        # A derived handoff view, NOT an in-place mutation of the original notebook.
        old_notebook["observations"] = list(observations.values())
        old_notebook["notebook_digest"] = canonical_sha256({k: v for k, v in old_notebook.items() if k != "notebook_digest"})
        result = dict(run_child("repair", collaboration_context(target, "repair", findings), config))
        update = {"repair_results": [{"parent_submission_digest": canonical_sha256(state["target_state"]["final_submission"]),
                                       "findings": findings, "agent_state": result}]}
        if result.get("phase") != "specialist_submission_accepted":
            return {**update, "phase": "review_cycle_needs_attention", "review_stop_reason": "author_did_not_submit_revision"}
        revised = validate_workpaper_state(result)
        if revised["agent_id"] != state["target_state"]["agent_id"]:
            raise DellWorkpaperReviewError("repair_owner_changed")
        return {**update, "target_state": revised, "review_round": state["review_round"] + 1,
                "final_submission": revised["final_submission"], "phase": "reviewing"}

    graph = StateGraph(WorkpaperReviewState, input_schema=SpecialistAgenticInput)
    graph.add_node("initialize_review", initialize)
    graph.add_node("reviewer", reviewer)
    graph.add_node("review_disposition", disposition)
    graph.add_node("responsible_author_repair", repair)
    graph.add_edge(START, "initialize_review")
    graph.add_conditional_edges("initialize_review", dispatch, ["reviewer"])
    graph.add_edge("reviewer", "review_disposition")
    graph.add_conditional_edges("review_disposition", lambda state: "repair" if state["phase"] == "author_repair_required" else "end",
                                {"repair": "responsible_author_repair", "end": END})
    graph.add_conditional_edges("responsible_author_repair", lambda state: dispatch(state) if state["phase"] == "reviewing" else END,
                                ["reviewer", END])
    return graph
