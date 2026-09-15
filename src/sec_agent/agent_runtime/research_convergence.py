"""Research responsibility wiring on native LangGraph; not another runtime.

Models decide what is wrong. FIN checks declared owners and source bindings.
Native nodes/checkpoints retain each attempt. One automatic correction round
is allowed; unresolved data/ownership or a second material failure goes to HITL.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from difflib import unified_diff
import json
import operator
from typing import Annotated, Any
from typing_extensions import TypedDict

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, Send

from .report_synthesis_agent import ReportReview, report_model_view, review_responsibility_errors, paper_revision_input
from .research_execution_plan import ResearchExecutionPlan
from .research_graph_contracts import canonical_sha256


def research_decision_context(artifacts, current, state, *, question, research_review_context):
    """Rebuild version/issue navigation from native artifacts, not a model summary.

    Version changes are mechanical facts; their financial consequences still
    require the Lead's judgment. No finding is marked resolved by this view.
    """
    papers = []
    versions = {}
    for row in current.catalog()["papers"]:
        pid = row["paper_id"]
        before, after = artifacts.read_paper(pid), current.read_paper(pid)
        old = {c["claim_id"]: c for c in before["claims"]}
        new = {c["claim_id"]: c for c in after["claims"]}
        baseline, version = canonical_sha256(before), canonical_sha256(after)
        versions[pid] = version
        papers.append({"paper_id": pid, "baseline_digest": baseline, "current_digest": version,
            "baseline_status": "current_version" if baseline == version else "superseded_version_not_a_financial_verdict",
            "changed_claim_ids": sorted(k for k in old.keys() | new.keys() if old.get(k) != new.get(k)),
            "changed_prose_fields": [key for key in ("thesis", "mechanism", "narrative_markdown",
                "counterevidence", "what_would_change", "open_gaps") if before.get(key) != after.get(key)],
            "open_gaps": deepcopy(after.get("open_gaps", [])),
            "pending_findings": deepcopy(state.get("pending_feedback", {}).get(pid, [])),
            "author_responses": deepcopy(state.get("revisions", {}).get(pid, {}).get("finding_responses", [])),
            "response_status_notice": "Author responses are assertions, not independent closure. Recheck affected claims AND prose.",
            "read_tool": "read_current_workpaper", "arguments": {"paper_id": pid},
            "source_catalog_arguments": {"paper_id": pid, "section": "sources"}})
    prior = next((row for row in reversed(state.get("artifact_history", []))
                  if row.get("actor") == "synthesis"), None)
    basis = (prior or {}).get("decision_context", {}).get("paper_version_digests")
    synthesis_status = ("absent" if not state.get("synthesis") else
                        "current_paper_versions_not_automatic_approval" if basis == versions else
                        "requires_reassessment_against_current_papers")
    return {"question": question, "research_as_of": current.research_as_of,
        "paper_version_digests": versions, "papers": papers, "previous_synthesis_status": synthesis_status,
        "review_unresolved_data_requests": {role: deepcopy(row.get("unresolved_data_requests", []))
            for role, row in research_review_context.items() if role in {"counter", "verifier"}},
        "incomplete_review_records": deepcopy(research_review_context.get("incomplete_review_records", {})),
        "latest_stage_review": {"stage": state.get("active_review"),
            "review": deepcopy(state.get(state.get("active_review", ""), {}))},
        "current_stage": {"correction_round": state.get("correction_round", 0),
            "pending_finding_ids": {pid: [f["finding_id"] for f in rows]
                for pid, rows in state.get("pending_feedback", {}).items()}},
        "usage": "Current native version/issue navigation, NOT new evidence or a compressed research conclusion. "
            "Read current workpapers and relevant original sources with the offered readers before dependent judgment. "
            "Reconcile support, counterevidence, period and scope; explain which old interpretations remain valid, "
            "are withdrawn or unresolved. Never use superseded wording as a current premise merely because it "
            "appears in earlier messages. A corrected citation does not prove the associated prose was repaired. "
            "Preserve unresolved issues and original source identities; do not restart unaffected research."}


class ResearchConvergenceState(TypedDict, total=False):
    workpaper_confirmation: dict[str, Any]
    confirmation_history: Annotated[list[dict[str, Any]], operator.add]
    unchanged_corrections: Annotated[list[str], operator.add]
    lead_decision: dict[str, Any]
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
                                     make_agent, max_parallel_authors=2, existing_state=None, human_feedback=None,
                                     execution_plan=None, hierarchical=False, max_correction_rounds=1,
                                     run_author=None, review_revisions=None):
    """A current-task graph: authors -> Lead -> research review -> report review.

    make_agent reuses native create_agent and current read-only MCP tools. It is
    called only for an actually needed actor, with that actor's own message state.
    Old standalone convergence and old review sessions retain their legacy graph.
    """
    if not 1 <= max_parallel_authors <= 12:
        raise ValueError("invalid_author_parallelism")
    if not 1 <= max_correction_rounds <= 3:
        raise ValueError("invalid_correction_round_limit")
    if not set(feedback).issubset(p["paper_id"] for p in artifacts.catalog()["papers"]):
        raise ValueError("unknown_initial_responsible_paper")
    graph = StateGraph(ResearchConvergenceState)
    plan = ResearchExecutionPlan.model_validate(execution_plan) if execution_plan else None
    depth = plan.depth if plan else "extended"  # old persisted sessions keep their contract
    if depth == "focused" and len(artifacts.catalog()["papers"]) != 1:
        raise ValueError("focused_plan_requires_one_self_contained_workpaper")

    def event(actor, event, **details):
        get_stream_writer()({"kind": "stage", "actor": actor, "event": event,
            "recorded_at": datetime.now(timezone.utc).isoformat(), **details})

    def initialize(_):
        previous = {key: deepcopy(existing_state[key]) for key in
            ("revisions", "synthesis", "synthesis_review", "report", "report_review") if existing_state and key in existing_state}
        return {**previous, "pending_feedback": deepcopy(feedback), "correction_round": 0,
                "stop_reason": None, "active_review": "report_review"}

    def initial_route(state):
        if hierarchical and not existing_state:
            return "lead_decision"
        if not existing_state:
            return "prepare_authors" if feedback or depth != "focused" else "prepare_focused_report"
        review = state["report_review"]
        return "route_review" if review.get("unresolved_data_requests") or any(f["severity"] == "material" for f in review["findings"]) else "writer"

    def ready_authors(state):
        return [pid for pid in sorted(state["pending_feedback"])
            if state.get("author_completed", {}).get(pid) != state["correction_round"]][:max_parallel_authors]

    def prepare_authors(state):
        if state.get("unchanged_corrections"):
            return {"stop_reason": "author_claimed_correction_without_research_change"}
        unresolved = any(r["disposition"] == "unresolved" for row in state.get("revisions", {}).values()
                         for r in row["finding_responses"])
        return {"stop_reason": "unresolved_data_or_author_response"} if unresolved and not ready_authors(state) else {}

    def author_routes(state):
        if state.get("stop_reason"):
            return "finish"
        ids = ready_authors(state)
        return [Send("responsible_author", {**state, "paper_id": pid}) for pid in ids] if ids else (
            "confirm_workpapers" if review_revisions else "lead_synthesis" if hierarchical or depth == "extended" else "prepare_focused_report" if depth == "focused" else "writer")

    def prepare_focused_report(state):
        from .report_synthesis_agent import report_citations
        current = artifacts.with_revisions(state.get("revisions", {}))
        paper = current.read_paper("P01")
        prose = paper["narrative_markdown"] + "\n\n## 判断与依据\n\n" + "\n\n".join(
            c["statement"] + f" [P01:{c['claim_id']}]" for c in paper["claims"])
        report = {"title": paper["thesis"], "narrative_markdown": prose,
            "citations": report_citations(prose, current), "charts": []}
        event("research", "output", status="candidate", objective=prose)
        return {"report": report}

    async def invoke(role, state, config, *, paper_id=None):
        current = artifacts.with_revisions(state.get("revisions", {}))
        actor = "author_" + paper_id if paper_id else role
        round_index = state["correction_round"]
        event(actor, "started", correction_round=round_index, paper_id=paper_id)
        own_feedback = deepcopy(state["pending_feedback"].get(paper_id, [])) if paper_id else None
        if role == "lead_decision":
            own_feedback = deepcopy(state["pending_feedback"])
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
        decision_context = None
        if human_feedback:
            body.update(human_feedback=human_feedback, human_feedback_is_not_evidence=True)
        if paper_id:
            # A fresh responsibility invocation, NOT a resumed private history.
            value = {}
            body.update(paper_revision_input(current, paper_id, own_feedback))
        else:
            decision_context = research_decision_context(artifacts, current, state,
                question=question, research_review_context=research_review_context)
            body["research_decision_context"] = decision_context
            if state.get("workpaper_confirmation"):
                body["independent_current_workpaper_confirmation"] = deepcopy(state["workpaper_confirmation"])
            body.update(catalog=current.catalog(),
                author_responses={pid: row["finding_responses"] for pid, row in state.get("revisions", {}).items()})
            if hierarchical:
                body["lead_issue_decision"] = deepcopy(state.get("lead_decision"))
            if role == "lead_decision":
                body["findings_to_handle"] = deepcopy(state["pending_feedback"])
                body["independent_research_review"] = deepcopy(research_review_context)
            elif role == "synthesis":
                body["independent_research_review"] = deepcopy(research_review_context)
                if state.get("synthesis"):
                    body["previous_synthesis"] = report_model_view(state["synthesis"])
                if round_index:
                    body["revision_request"] = deepcopy(state[state["active_review"]])
            elif role == "writer":
                body["research_synthesis"] = report_model_view(state["synthesis"]) if state.get("synthesis") else None
                body["research_review"] = deepcopy(state.get("synthesis_review", research_review_context))
                if plan:
                    body["execution_plan"] = plan.model_dump(mode="json")
                    body["instruction"] = "Answer only the user's scope. Read relevant workpapers on demand and integrate them directly. Do not repeat unchanged source queries; re-query only for a concrete missing/contradictory field. Retain evidence, limitations and necessary checks. Charts are optional when they do not help this question."
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
                    body["research_synthesis"] = report_model_view(state["synthesis"]) if state.get("synthesis") else None
                    body["completed_research_reviews"] = deepcopy(research_review_context)
                    body["instruction"] = "Independently verify the report's material claims and transformations against actual sources. Prior reviews are navigation and completed-work records, not evidence or automatic approval. Reuse immutable source/calculation bindings; do not re-query an unchanged value merely to recreate its ID. Explain your inspection scope and any need to reopen prior work. No unrelated research expansion."
                    reports = [r["output"] for r in state.get("artifact_history", []) if r["actor"] == "writer"]
                    baseline = reports[-2] if len(reports) > 1 else (existing_state or {}).get("report")
                    if baseline and reports:
                        body["report_changes_from_previous_review"] = "\n".join(unified_diff(
                            json.dumps(report_model_view(baseline), ensure_ascii=False, indent=2).splitlines(),
                            json.dumps(report_model_view(reports[-1]), ensure_ascii=False, indent=2).splitlines(),
                            fromfile="previously_reviewed_report", tofile="current_report", lineterm=""))
                        body["instruction"] += " This is a correction review: verify closure of prior findings, changed text/charts and newly introduced consequences. Reopen unchanged research only for a stated material reason; do not automatically repeat a full-case review."
                if round_index or existing_state:
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
        updates = {"actor_metrics": [metrics], "artifact_history": [{"actor": actor, "correction_round": round_index, "output": output,
            **({"decision_context": deepcopy(decision_context)} if decision_context is not None else {})}]}
        if paper_id:
            previous = state.get("revisions", {}).get(paper_id, {})
            output = deepcopy(output)
            output["sources"] = {**previous.get("sources", {}), **output.get("sources", {})}
            responses = {f["finding_id"]: f for f in previous.get("finding_responses", [])}
            responses.update({f["finding_id"]: f for f in output["finding_responses"]})
            output["finding_responses"] = list(responses.values())
            from .workpaper_changes import workpaper_changes
            output["runtime_changes"] = workpaper_changes(current.read_paper(paper_id),
                artifacts.with_revisions({**state.get("revisions", {}), paper_id: output}).read_paper(paper_id))
            updates.update(revisions={paper_id: output}, author_completed={paper_id: round_index})
            # Exact no-change is an execution fact, not a semantic quality verdict.
            # Do not spend on downstream synthesis when an author claims a repair
            # yet has changed no research content at all.
            revised = artifacts.with_revisions({**state.get("revisions", {}), paper_id: output})
            if any(r["disposition"] == "corrected" for r in result["output"]["finding_responses"]):
                before, after = current.read_paper(paper_id), revised.read_paper(paper_id)
                fields = ("thesis", "mechanism", "claims", "narrative_markdown", "counterevidence", "what_would_change", "open_gaps")
                if all(before.get(k) == after.get(k) for k in fields):
                    updates["unchanged_corrections"] = [paper_id]
        else:
            target = {"lead_decision": "lead_decision", "synthesis": "synthesis", "research_verifier": "synthesis_review", "writer": "report", "report_verifier": "report_review"}[role]
            updates[target] = output
            if role.endswith("verifier"):
                updates["active_review"] = target
        return updates

    async def author(state, config: RunnableConfig):
        if run_author:
            from .workpaper_changes import workpaper_changes
            pid = state["paper_id"]
            current = artifacts.with_revisions(state.get("revisions", {}))
            event("author_" + pid, "started", paper_id=pid, correction_round=state["correction_round"])
            output = await run_author(pid, state, config)
            after = artifacts.with_revisions({**state.get("revisions", {}), pid: output})
            changes = workpaper_changes(current.read_paper(pid), after.read_paper(pid))
            output = {**output, "runtime_changes": changes}
            event("author_" + pid, "outcome", status="submitted_pending_independent_confirmation",
                paper_id=pid, runtime_changes=changes)
            updates = {"revisions": {pid: output}, "author_completed": {pid: state["correction_round"]},
                "artifact_history": [{"actor": "author_" + pid, "correction_round": state["correction_round"],
                    "output": {k: v for k, v in output.items() if k != "author_state"}}]}
            if (any(r["disposition"] == "corrected" for r in output["finding_responses"])
                    and not changes["changed_claim_ids"] and not any(r["path"] != "/task_note" for r in changes["locations"])):
                updates["unchanged_corrections"] = [pid]
            return updates
        return await invoke("repair", state, config, paper_id=state["paper_id"])

    async def confirm_workpapers(state, config: RunnableConfig):
        from .case_review_agent import CaseReview, case_review_scope_digest, validate_finding_confirmation
        from .research_session import responsible_author_feedback
        from .workpaper_changes import confirmation_context
        context = confirmation_context(artifacts, state.get("revisions", {}), state["pending_feedback"])
        current = artifacts.with_revisions(state.get("revisions", {}))
        result = await review_revisions(current, context, config)
        record = {"context": context, "review": result, "correction_round": state["correction_round"]}
        update = {"workpaper_confirmation": record, "confirmation_history": [record],
            "artifact_history": [{"actor": "independent_workpaper_confirmation", "correction_round": state["correction_round"], "output": record}]}
        if result.get("scope_digest") != case_review_scope_digest(current, question):
            return {**update, "stop_reason": "independent_confirmation_stale_version"}
        if result.get("phase") != "case_review_ready_for_convergence":
            return {**update, "stop_reason": "independent_confirmation_incomplete"}
        for role in ("counter", "verifier"):
            validate_finding_confirmation(CaseReview.model_validate(result[role]["review"]), context, current)
        pending = responsible_author_feedback(result, current)
        for rows in pending.values():
            for finding in rows:
                finding["finding_id"] = f"confirmation:{state['correction_round']}:" + finding["finding_id"]
        event("independent_workpaper_confirmation", "outcome", status="findings_returned_to_lead" if pending else "confirmed_pending_lead_judgment",
            objective="新版底稿独立复核完成；" + ("仍有需处理的问题，已集中交回研究负责人。" if pending else "已记录逐项确认，等待研究负责人作最终判断。"))
        return {**update, "pending_feedback": pending}

    def actor_node(role):
        async def execute(state, config: RunnableConfig):
            return await invoke(role, state, config)
        return execute

    def after_decision(state):
        decision = state["lead_decision"]
        if decision["action"] == "stop":
            return "decision_stop"
        if (decision["action"] == "repair" and state.get("workpaper_confirmation")
                and state["correction_round"] >= max_correction_rounds):
            return "correction_limit_stop"
        return "apply_lead_repairs" if decision["action"] == "repair" else "lead_synthesis"

    def apply_lead_repairs(state):
        dispositions = {(d["paper_id"], d["finding_id"]): d for d in state["lead_decision"]["dispositions"]}
        feedback = {}
        for pid, rows in state["pending_feedback"].items():
            for finding in rows:
                decision = dispositions[(pid, finding["finding_id"])]
                if decision["disposition"] == "repair":
                    feedback.setdefault(pid, []).append({**finding, "requested_change": decision["requested_change"],
                        "lead_rationale": decision["rationale"], "expected_progress": decision["expected_progress"]})
        for finding in state["lead_decision"].get("new_findings", []):
            if finding["disposition"] == "repair":
                feedback.setdefault(finding["paper_id"], []).append({
                    **finding, "reviewer": "lead_decision", "severity": "material",
                    "diagnosis": finding["rationale"], "lead_rationale": finding["rationale"]})
        repeated = any(state.get("author_completed", {}).get(pid) == state["correction_round"] for pid in feedback)
        return {"pending_feedback": feedback, "correction_round": state["correction_round"] + int(repeated)}

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
        if state["correction_round"] >= max_correction_rounds:
            return {"route": "finish", "stop_reason": "material_findings_remain_after_targeted_correction",
                    "pending_feedback": routed["feedback"]}
        # Expression in a Lead brief belongs to the Lead; expression in a report
        # belongs to Writer. Research corrections always revisit the Lead.
        route = ("lead_decision" if hierarchical and routed["feedback"] else "prepare_authors") if routed["feedback"] else "lead_synthesis" if stage == "synthesis_review" else "writer"
        event("responsibility_router", "handoff", status=route, correction_round=state["correction_round"] + 1,
              responsible_paper_ids=sorted(routed["feedback"]))
        return {"route": route, "pending_feedback": routed["feedback"], "correction_round": state["correction_round"] + 1}

    def finish(state):
        if state.get("stop_reason"):
            phase = "case_report_needs_revision" if state.get("report") else "research_convergence_needs_attention"
        else:
            phase = "case_report_ready_for_human_review"
        return {"phase": phase}

    graph.add_node("initialize", initialize)
    graph.add_node("lead_decision", actor_node("lead_decision"))
    graph.add_node("apply_lead_repairs", apply_lead_repairs)
    graph.add_node("decision_stop", lambda _: {"stop_reason": "lead_retained_unresolved_research"})
    graph.add_node("correction_limit_stop", lambda _: {"stop_reason": "material_findings_remain_after_targeted_correction"})
    graph.add_edge("correction_limit_stop", "finish")
    graph.add_node("confirm_workpapers", confirm_workpapers)
    graph.add_conditional_edges("confirm_workpapers", lambda s: "finish" if s.get("stop_reason") else "lead_decision", ["finish", "lead_decision"])
    graph.add_conditional_edges("lead_decision", after_decision, ["decision_stop", "correction_limit_stop", "apply_lead_repairs", "lead_synthesis"])
    graph.add_edge("decision_stop", "finish")
    graph.add_edge("apply_lead_repairs", "prepare_authors")
    graph.add_node("prepare_authors", prepare_authors)
    graph.add_node("prepare_focused_report", prepare_focused_report)
    graph.add_node("responsible_author", author)
    for name, role in (("lead_synthesis", "synthesis"), ("research_verifier", "research_verifier"),
                       ("writer", "writer"), ("report_verifier", "report_verifier")):
        graph.add_node(name, actor_node(role))
    graph.add_node("route_review", route_review)
    graph.add_node("finish", finish)
    graph.add_edge(START, "initialize")
    graph.add_conditional_edges("initialize", initial_route, ["lead_decision", "prepare_authors", "prepare_focused_report", "route_review", "writer"])
    graph.add_conditional_edges("prepare_authors", author_routes, ["responsible_author", "confirm_workpapers", "lead_synthesis", "writer", "prepare_focused_report", "finish"])
    graph.add_edge("prepare_focused_report", "report_verifier")
    graph.add_edge("responsible_author", "prepare_authors")
    graph.add_edge("lead_synthesis", "research_verifier")
    graph.add_edge("research_verifier", "route_review")
    graph.add_edge("writer", "report_verifier")
    graph.add_edge("report_verifier", "route_review")
    graph.add_conditional_edges("route_review", lambda state: state["route"],
        ["lead_decision", "writer", "prepare_authors", "lead_synthesis", "finish"])
    graph.add_edge("finish", END)
    return graph
