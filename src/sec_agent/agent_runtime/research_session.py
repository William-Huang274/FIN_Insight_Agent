"""Thin product composition of existing native research and report subgraphs.

The parent maps this task's submitted artifacts, never saved Dell answers or
another agent's message history. LangGraph owns execution and persistence.
Provider/data resources are opened by the supplied phase Runnables.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Literal

from langchain_core.runnables import RunnableConfig
from langgraph.config import get_stream_writer
from langgraph.graph import START, END
from langgraph.types import interrupt
from pydantic import BaseModel, ConfigDict, Field

from .dell_case_artifacts import DellCaseArtifacts
from .dell_case_review_agent import CaseReview
from .dell_report_session import SessionState, build_report_session_graph
from .dell_workpaper_review_graph import validate_workpaper_state


class ResearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    case_profile: Literal["dell_growth_quality"] = "dell_growth_quality"
    question: str = Field(min_length=10, max_length=16000)


class ResearchSessionState(SessionState, total=False):
    case_profile: str
    question: str
    research_as_of: str
    snapshot_id: str
    case_papers: list[dict[str, Any]]
    research_tasks: list[dict[str, Any]]
    research_outcomes: list[dict[str, Any]]
    research_handoff: dict[str, Any] | None
    research_attempt_history: list[dict[str, Any]]
    continue_remaining_research: bool
    case_review: dict[str, Any]
    author_feedback: dict[str, list[dict[str, Any]]]
    research_stop_reason: str | None
    synthesis: dict[str, Any]
    synthesis_review: dict[str, Any]
    convergence_history: list[dict[str, Any]]


def current_task_artifacts(state):
    return DellCaseArtifacts(state["case_papers"])


def can_continue_remaining_research(state):
    return (state.get("phase") == "research_needs_attention" and bool(state.get("case_papers"))
            and not state.get("case_review") and not state.get("report"))


def responsible_author_feedback(case_review, artifacts):
    """Route actual material findings; advisory points go to the Writer.

    Reviewer IDs are namespaced to avoid Counter and Verifier both using F1.
    The original finding remains unchanged in the persisted review artifact.
    """
    papers = {row["paper_id"] for row in artifacts.catalog()["papers"]}
    feedback = {}
    for role in ("counter", "verifier"):
        row = case_review.get(role, {})
        if row.get("status") != "review_submitted":
            raise ValueError("research_review_incomplete_no_silent_convergence")
        review = CaseReview.model_validate(row["review"])
        if {assessment.paper_id for assessment in review.assessments} != papers:
            raise ValueError("research_review_paper_scope_mismatch")
        for finding in review.findings:
            if finding.paper_id not in papers:
                raise ValueError("research_finding_unknown_responsible_paper")
            if finding.severity == "material":
                item = finding.model_dump(mode="json")
                item.update(finding_id=f"{role}:{finding.finding_id}", reviewer=role,
                            original_finding_id=finding.finding_id)
                feedback.setdefault(finding.paper_id, []).append(item)
    return feedback


def _stage(actor, event, **details):
    get_stream_writer()({"kind": "stage", "actor": actor, "event": event,
                        "recorded_at": datetime.now(timezone.utc).isoformat(), **details})


def build_research_session_graph(*, research, review, converge, writer, verifier, quick_writer=None, revise_research=None):
    """One fresh research request -> real artifacts -> review -> report -> HITL.

    Existing report session nodes handle subsequent ask/revise/accept actions;
    the research nodes have no edge back from that loop. No hidden whole-case
    retry, automatic reviewer-until-PASS loop, or user-controlled host settings.
    """
    async def revision_handler(state, config: RunnableConfig):
        result = await revise_research.ainvoke(state, config)
        if result.get("phase") not in {"case_report_needs_revision", "case_report_ready_for_human_review"}:
            raise ValueError("research_revision_terminal_unrecognized")
        if not result.get("report") or not result.get("report_review"):
            raise ValueError("research_revision_missing_report")
        return {**{key: deepcopy(result[key]) for key in ("report", "report_review", "revisions", "synthesis", "synthesis_review") if key in result},
            "convergence_history": [*state.get("convergence_history", []), *deepcopy(result.get("artifact_history", []))],
            "research_stop_reason": result.get("stop_reason"),
            "phase": "needs_revision" if result["phase"] == "case_report_needs_revision" else "ready_for_human_review",
            "report_version": state["report_version"] + (result["report"] != state["report"]),
            "last_output_kind": "report"}

    graph = build_report_session_graph(
        writer=writer, verifier=verifier, quick_writer=quick_writer,
        artifacts=current_task_artifacts,
        initial=lambda state: {key: state[key] for key in ("report", "report_review", "revisions", "phase")},
        state_schema=ResearchSessionState, input_schema=ResearchRequest, start_at_initialize=False,
        revision_handler=revision_handler if revise_research is not None else None,
    )

    async def run_research(state, config: RunnableConfig, *, continuing=False):
        if continuing:
            if not can_continue_remaining_research(state):
                raise ValueError("only_incomplete_research_can_continue_remaining_tasks")
        elif state.get("initialized") or state.get("case_papers") or state.get("research_tasks"):
            raise ValueError("fresh_research_cannot_restart_existing_session")
        request = ResearchRequest.model_validate({key: state[key] for key in ("question", "case_profile") if key in state})
        payload = request.model_dump(mode="json")
        retained = deepcopy(state.get("case_papers", [])) if continuing else []
        if continuing:
            # Only native state from this same task, never browser or old-case seeds.
            payload["completed_workpapers"] = retained
        _stage("lead", "started", status="continue_remaining" if continuing else "fresh")
        result = await research.ainvoke(payload, config)
        outcomes = result.get("task_results", [])
        papers = [*retained, *[validate_workpaper_state(row["agent_state"]) for row in outcomes if row["status"] == "submitted"]]
        paper_ids = [row["task"]["task_id"] for row in papers]
        if len(paper_ids) != len(set(paper_ids)):
            raise ValueError("continuation_must_not_rerun_submitted_workpapers")
        # Canonical source checks occur before any of these papers reach review.
        artifacts = DellCaseArtifacts(papers) if papers else None
        ready = result.get("phase") == "research_ready_for_review" and bool(papers)
        _stage("lead", "outcome", status="handoff" if ready else "needs_attention")
        prior_done = {row["task"]["task_id"] for row in retained}
        new_tasks = deepcopy(result.get("tasks", []))
        new_outcomes = [{"task_id": row["task_id"], "status": row["status"]} for row in outcomes]
        attempt = {"run_id": config.get("configurable", {}).get("run_id"), "continued": continuing,
                   "tasks": new_tasks, "outcomes": new_outcomes, "phase": result.get("phase"),
                   "recorded_at": datetime.now(timezone.utc).isoformat()}
        history = deepcopy(state.get("research_attempt_history", []))
        if continuing and not history:
            # Compatibility with a task started before this public projection.
            # The original native checkpoint/run remains authoritative.
            history.append({"run_id": None, "origin": "preceding_native_checkpoint",
                "tasks": deepcopy(state.get("research_tasks", [])), "outcomes": deepcopy(state.get("research_outcomes", [])),
                "phase": state["phase"]})
        return {"case_profile": request.case_profile, "case_papers": papers,
            "research_tasks": [*[t for t in state.get("research_tasks", []) if t["task_id"] in prior_done], *new_tasks],
            "research_outcomes": [*[{"task_id": key, "status": "submitted"} for key in prior_done], *new_outcomes],
            "research_attempt_history": [*history, attempt],
            "continue_remaining_research": False,
            "research_handoff": deepcopy(result.get("lead_handoff")),
            "research_as_of": artifacts.research_as_of if artifacts else "",
            "snapshot_id": artifacts.snapshot_id if artifacts else "",
            "phase": "research_reviewing" if ready else "research_needs_attention",
            "research_stop_reason": None if ready else result.get("stop_reason") or "research_incomplete"}

    async def research_node(state, config: RunnableConfig):
        return await run_research(state, config)

    async def remaining_research_node(state, config: RunnableConfig):
        return await run_research(state, config, continuing=True)

    async def review_node(state, config: RunnableConfig):
        _stage("case_review", "started")
        result = await review.ainvoke({"question": state["question"], "case_papers": state["case_papers"]}, config)
        artifacts = current_task_artifacts(state)
        feedback = responsible_author_feedback(result, artifacts)
        _stage("case_review", "outcome", status="handoff", responsible_author_count=len(feedback))
        return {"case_review": deepcopy(result), "author_feedback": feedback, "phase": "research_writing"}

    async def converge_node(state, config: RunnableConfig):
        _stage("convergence", "started")
        result = await converge.ainvoke({"question": state["question"], "case_papers": state["case_papers"],
            "feedback": state["author_feedback"], "case_review": state["case_review"],
            "research_handoff": state["research_handoff"]}, config)
        retained = {key: deepcopy(result.get(key, {})) for key in ("synthesis", "synthesis_review")}
        retained.update(convergence_history=deepcopy(result.get("artifact_history", [])),
                        revisions=deepcopy(result.get("revisions", {})))
        if result.get("phase") == "research_convergence_needs_attention":
            return {**retained, "phase": "research_needs_attention", "research_stop_reason": result["stop_reason"]}
        if not result.get("report") or not result.get("report_review"):
            raise ValueError("research_report_incomplete_no_silent_delivery")
        if result.get("phase") not in {"case_report_needs_revision", "case_report_ready_for_human_review"}:
            raise ValueError("research_report_terminal_unrecognized")
        phase = "needs_revision" if result["phase"] == "case_report_needs_revision" else "ready_for_human_review"
        _stage("convergence", "outcome", status=phase)
        return {**retained, "report": deepcopy(result["report"]), "report_review": deepcopy(result["report_review"]),
                "phase": phase, "research_stop_reason": result.get("stop_reason")}

    def attention(state):
        response = interrupt({"kind": "research_needs_attention", "reason": state["research_stop_reason"],
            "completed_papers": len(state["case_papers"]),
            "actions": ["acknowledge", *(["continue_remaining"] if can_continue_remaining_research(state) else [])],
            "notice": "Submitted work and failed/unfinished tasks remain visible. No report was accepted; no automatic retry."})
        if isinstance(response, dict) and response.get("action") == "continue_remaining" and can_continue_remaining_research(state):
            return {"continue_remaining_research": True}
        if not isinstance(response, dict) or response.get("action") != "acknowledge":
            raise ValueError("incomplete_research_cannot_be_accepted_as_a_report")
        return {"phase": "research_incomplete_acknowledged"}

    graph.add_node("research", research_node)
    graph.add_node("remaining_research", remaining_research_node)
    graph.add_node("case_review", review_node)
    graph.add_node("convergence", converge_node)
    graph.add_node("research_attention", attention)
    graph.add_edge(START, "research")
    graph.add_conditional_edges("research", lambda state: "case_review" if state["phase"] == "research_reviewing" else "research_attention")
    graph.add_conditional_edges("remaining_research", lambda state: "case_review" if state["phase"] == "research_reviewing" else "research_attention")
    graph.add_edge("case_review", "convergence")
    graph.add_conditional_edges("convergence", lambda state: "research_attention" if state["phase"] == "research_needs_attention" else "initialize")
    graph.add_conditional_edges("research_attention", lambda state: "remaining_research" if state.get("continue_remaining_research") else END)
    return graph
