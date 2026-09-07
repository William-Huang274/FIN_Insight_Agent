"""Research responsibility wiring on native LangGraph; not another runtime.

Models decide what is wrong. FIN checks declared owners and source bindings.
Native nodes/checkpoints retain each attempt. One automatic correction round
is allowed; unresolved data/ownership or a second material failure goes to HITL.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import operator
from typing import Annotated, Any
from typing_extensions import TypedDict

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, Send

from .dell_case_convergence_agent import ReportReview, report_model_view, review_responsibility_errors


class ResearchConvergenceState(TypedDict, total=False):
    revisions: Annotated[dict[str, Any], operator.or_]
    synthesis: dict[str, Any]
    synthesis_review: dict[str, Any]
    report: dict[str, Any]
    report_review: dict[str, Any]
    pending_feedback: dict[str, list[dict[str, Any]]]
    author_completed: Annotated[dict[str, int], operator.or_]
    correction_round: int
    active_review: str
    route: str
    stop_reason: str | None
    phase: str
    artifact_history: Annotated[list[dict[str, Any]], operator.add]
    actor_metrics: Annotated[list[dict[str, Any]], operator.add]
    # Only native Send inputs contain a selected paper, not browser input.
    paper_id: str


def route_material_findings(review, artifacts, *, stage, round_index):
    """Use the reviewer's explicit responsibility, never keyword/NLP rules."""
    parsed = ReportReview.model_validate(review)
    errors = review_responsibility_errors(parsed, artifacts, required=True)
    if errors:
        raise ValueError("invalid_review_responsibility:" + json.dumps(errors))
    feedback, blocked, writer = {}, list(parsed.unresolved_data_requests), False
    for finding in parsed.findings:
        if finding.severity != "material":
            continue
        if finding.responsibility in {"data_tool", "human"}:
            blocked.append(f"{finding.responsibility}:{finding.finding_id}:{finding.diagnosis}")
        elif finding.responsibility == "writer":
            writer = True
        elif finding.responsibility == "research":
            for pid in finding.paper_ids:
                feedback.setdefault(pid, []).append({
                    "finding_id": f"{stage}:{round_index}:{finding.finding_id}", "original_finding_id": finding.finding_id,
                    "reviewer": stage, "paper_id": pid, "severity": "material",
                    "problematic_quote": finding.report_quote,
                    "quote_context": "Exact quote from the reviewed synthesis/report, not necessarily your workpaper.",
                    "diagnosis": finding.diagnosis, "requested_change": finding.requested_change,
                })
    return {"feedback": feedback, "blocked": blocked, "writer": writer}


def build_research_convergence_graph(*, artifacts, question, feedback, research_review_context,
                                     make_agent, max_parallel_authors=2, existing_state=None, human_feedback=None):
    """A current-task graph: authors -> Lead -> research review -> report review.

    make_agent reuses native create_agent and current read-only MCP tools. It is
    called only for an actually needed actor, with that actor's own message state.
    Old standalone convergence and old review sessions retain their legacy graph.
    """
    if not 1 <= max_parallel_authors <= 12:
        raise ValueError("invalid_author_parallelism")
    if not set(feedback).issubset(p["paper_id"] for p in artifacts.catalog()["papers"]):
        raise ValueError("unknown_initial_responsible_paper")
    graph = StateGraph(ResearchConvergenceState)

    def event(actor, event, **details):
        get_stream_writer()({"kind": "stage", "actor": actor, "event": event,
            "recorded_at": datetime.now(timezone.utc).isoformat(), **details})

    def initialize(_):
        previous = {key: deepcopy(existing_state[key]) for key in
            ("revisions", "synthesis", "synthesis_review", "report", "report_review") if existing_state and key in existing_state}
        return {**previous, "pending_feedback": deepcopy(feedback), "correction_round": 0,
                "stop_reason": None, "active_review": "report_review"}

    def initial_route(state):
        if not existing_state:
            return "prepare_authors"
        review = state["report_review"]
        return "route_review" if review.get("unresolved_data_requests") or any(f["severity"] == "material" for f in review["findings"]) else "writer"

    def ready_authors(state):
        return [pid for pid in sorted(state["pending_feedback"])
            if state.get("author_completed", {}).get(pid) != state["correction_round"]][:max_parallel_authors]

    def prepare_authors(state):
        unresolved = any(r["disposition"] == "unresolved" for row in state.get("revisions", {}).values()
                         for r in row["finding_responses"])
        return {"stop_reason": "unresolved_data_or_author_response"} if unresolved and not ready_authors(state) else {}

    def author_routes(state):
        if state.get("stop_reason"):
            return "finish"
        ids = ready_authors(state)
        return [Send("responsible_author", {**state, "paper_id": pid}) for pid in ids] if ids else "lead_synthesis"

    async def invoke(role, state, config, *, paper_id=None):
        current = artifacts.with_revisions(state.get("revisions", {}))
        actor = "author_" + paper_id if paper_id else role
        round_index = state["correction_round"]
        event(actor, "started", correction_round=round_index, paper_id=paper_id)
        own_feedback = deepcopy(state["pending_feedback"].get(paper_id, [])) if paper_id else None
        if paper_id:
            expected = {f["finding_id"] for f in own_feedback}
            # An explicitly requested later repair must answer older unresolved
            # items too, rather than losing them or leaving an unfixable marker.
            for row in state.get("revisions", {}).get(paper_id, {}).get("finding_responses", []):
                if row["disposition"] == "unresolved" and row["finding_id"] not in expected:
                    own_feedback.append({"finding_id": row["finding_id"], "paper_id": paper_id,
                        "severity": "material", "diagnosis": "Previously unresolved author response: " + row["explanation"],
                        "requested_change": "Recheck this unresolved item against permitted sources; correct or disagree with evidence, otherwise retain unresolved."})
        agent = make_agent(role, current, feedback=own_feedback, paper_id=paper_id,
                           correction_round=round_index, revising_report=bool(state.get("report")))
        value = {"revisions": deepcopy(state.get("revisions", {})),
                 "synthesis": deepcopy(state.get("synthesis", {}))}
        body = {"question": question, "research_as_of": artifacts.research_as_of}
        if human_feedback:
            body.update(human_feedback=human_feedback, human_feedback_is_not_evidence=True)
        if paper_id:
            # A fresh responsibility invocation, NOT a resumed private history.
            value = {}
            body.update(paper_id=paper_id, original_workpaper=current.read_paper(paper_id),
                        sources=current.read_paper(paper_id, "sources"), findings=own_feedback)
        else:
            body.update(catalog=current.catalog(),
                author_responses={pid: row["finding_responses"] for pid, row in state.get("revisions", {}).items()})
            if role == "synthesis":
                body["independent_research_review"] = deepcopy(research_review_context)
                if state.get("synthesis"):
                    body["previous_synthesis"] = report_model_view(state["synthesis"])
                if round_index:
                    body["revision_request"] = deepcopy(state[state["active_review"]])
            elif role == "writer":
                body["research_synthesis"] = report_model_view(state["synthesis"])
                body["research_review"] = deepcopy(state["synthesis_review"])
                if state.get("report"):
                    value["report"] = deepcopy(state["report"])
                    body.update(report=report_model_view(state["report"]), revision_request=deepcopy(state["report_review"]))
                    value["request_action"] = "revise"
            else:
                target = "synthesis" if role == "research_verifier" else "report"
                value["report"] = deepcopy(state[target])
                body.update(review_target="lead_synthesis" if target == "synthesis" else "final_report",
                            report=report_model_view(state[target]))
                if role == "report_verifier":
                    body["research_synthesis"] = report_model_view(state["synthesis"])
                if round_index:
                    body["previous_review"] = deepcopy(state.get("synthesis_review" if role == "research_verifier" else "report_review", {}))
        value["messages"] = [HumanMessage(content=json.dumps(body, ensure_ascii=False))]
        # An explicitly retried parent can reach a child whose native loop ended
        # without its required submission. Reopen only that completed child via
        # the documented Command API; retain its own messages and accepted peers.
        saved = await agent.aget_state(config)
        if saved.values.get("messages") and not saved.next and not saved.values.get("output"):
            value = Command(goto="model", update={"messages": [HumanMessage(content=
                "The previous attempt ended without an accepted structured submission. It did NOT complete this role. "
                "Continue from your retained source reads, correct the rejected submission and call your submission tool. "
                "The host has restarted only this failed role; do not repeat unrelated research.")]})
        result = await agent.ainvoke(value, config)
        if not result.get("output"):
            raise ValueError(f"research_actor_ended_without_submission:{actor}")
        output = deepcopy(result["output"])
        metrics = {"actor": actor, "correction_round": round_index,
            "model_calls": sum(isinstance(m, AIMessage) for m in result.get("messages", [])),
            "tool_calls": sum(isinstance(m, ToolMessage) for m in result.get("messages", []))}
        event(actor, "outcome", status="submitted", correction_round=round_index, paper_id=paper_id)
        updates = {"actor_metrics": [metrics], "artifact_history": [{"actor": actor, "correction_round": round_index, "output": output}]}
        if paper_id:
            previous = state.get("revisions", {}).get(paper_id, {})
            output = deepcopy(output)
            output["sources"] = {**previous.get("sources", {}), **output.get("sources", {})}
            responses = {f["finding_id"]: f for f in previous.get("finding_responses", [])}
            responses.update({f["finding_id"]: f for f in output["finding_responses"]})
            output["finding_responses"] = list(responses.values())
            updates.update(revisions={paper_id: output}, author_completed={paper_id: round_index})
        else:
            target = {"synthesis": "synthesis", "research_verifier": "synthesis_review", "writer": "report", "report_verifier": "report_review"}[role]
            updates[target] = output
            if role.endswith("verifier"):
                updates["active_review"] = target
        return updates

    async def author(state, config: RunnableConfig):
        return await invoke("repair", state, config, paper_id=state["paper_id"])

    def actor_node(role):
        async def execute(state, config: RunnableConfig):
            return await invoke(role, state, config)
        return execute

    def route_review(state):
        stage = state["active_review"]
        routed = route_material_findings(state[stage], artifacts,
            stage=stage, round_index=state["correction_round"])
        unresolved = [r for row in state.get("revisions", {}).values()
                      for r in row["finding_responses"] if r["disposition"] == "unresolved"]
        needs_change = bool(routed["feedback"] or routed["writer"])
        if routed["blocked"] or unresolved:
            return {"route": "finish", "stop_reason": "unresolved_data_or_author_response",
                    "pending_feedback": routed["feedback"]}
        if not needs_change:
            return {"route": "writer" if stage == "synthesis_review" else "finish", "stop_reason": None}
        if state["correction_round"] >= 1:
            return {"route": "finish", "stop_reason": "material_findings_remain_after_targeted_correction",
                    "pending_feedback": routed["feedback"]}
        # Expression in a Lead brief belongs to the Lead; expression in a report
        # belongs to Writer. Research corrections always revisit the Lead.
        route = "prepare_authors" if routed["feedback"] else "lead_synthesis" if stage == "synthesis_review" else "writer"
        event("responsibility_router", "handoff", status=route, correction_round=1,
              responsible_paper_ids=sorted(routed["feedback"]))
        return {"route": route, "pending_feedback": routed["feedback"], "correction_round": 1}

    def finish(state):
        if state.get("stop_reason"):
            phase = "case_report_needs_revision" if state.get("report") else "research_convergence_needs_attention"
        else:
            phase = "case_report_ready_for_human_review"
        return {"phase": phase}

    graph.add_node("initialize", initialize)
    graph.add_node("prepare_authors", prepare_authors)
    graph.add_node("responsible_author", author)
    for name, role in (("lead_synthesis", "synthesis"), ("research_verifier", "research_verifier"),
                       ("writer", "writer"), ("report_verifier", "report_verifier")):
        graph.add_node(name, actor_node(role))
    graph.add_node("route_review", route_review)
    graph.add_node("finish", finish)
    graph.add_edge(START, "initialize")
    graph.add_conditional_edges("initialize", initial_route, ["prepare_authors", "route_review", "writer"])
    graph.add_conditional_edges("prepare_authors", author_routes, ["responsible_author", "lead_synthesis", "finish"])
    graph.add_edge("responsible_author", "prepare_authors")
    graph.add_edge("lead_synthesis", "research_verifier")
    graph.add_edge("research_verifier", "route_review")
    graph.add_edge("writer", "report_verifier")
    graph.add_edge("report_verifier", "route_review")
    graph.add_conditional_edges("route_review", lambda state: state["route"],
        ["writer", "prepare_authors", "lead_synthesis", "finish"])
    graph.add_edge("finish", END)
    return graph
