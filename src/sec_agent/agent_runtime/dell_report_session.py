"""Bounded Dell report review on native Agent Server, not another runtime.

The already-researched case is host-pinned. Native thread/run IDs are the session
IDs. Each human action gets private per-invocation agent histories; only cited
outputs and explicit public feedback cross agents or reach the Workbench.
"""
from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from copy import deepcopy
from pathlib import Path
from threading import Lock
from typing import Annotated, Any, Literal
from typing_extensions import TypedDict
import operator
from functools import lru_cache
from datetime import datetime, timezone
from uuid import UUID

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig, RunnableLambda
from langgraph.config import get_stream_writer
from langgraph.graph import START, END, StateGraph
from langgraph.errors import NodeError
from langgraph.types import Command, interrupt
from langgraph_sdk.runtime import ServerRuntime
from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

from .deepseek_structured_agents import DeepSeekModelProfile, TokenBudgetBasis, load_deepseek_structured_agent_config
from .dell_case_artifacts import DellCaseArtifacts
from .dell_case_convergence_agent import build_case_output_agent, report_citations, report_model_view, CaseReport, ReportReview
from .dell_case_review_agent import CaseModelAudit, case_chat_model, case_mcp_tools


class ReviewAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["ask", "revise", "accept"]
    message: str = Field(default="", max_length=16000)
    answer_mode: Literal["quick", "deep"] = "deep"

    @model_validator(mode="after")
    def quick_only_for_questions(self):
        if self.answer_mode == "quick" and self.action != "ask":
            raise ValueError("quick_mode_is_only_for_questions")
        return self


class SessionInput(TypedDict):
    open: Literal[True]


class SessionState(TypedDict, total=False):
    initialized: bool
    report: dict[str, Any]
    report_review: dict[str, Any]
    revisions: dict[str, Any]
    report_version: int
    phase: str
    request_action: str
    message: str
    conversation: Annotated[list[dict], operator.add]
    model_events: Annotated[list[dict], operator.add]
    last_output_kind: str


def abandoned_question_update(state, reason):
    """Abandon only a failed question, never approve or rewrite a report."""
    if state.get("request_action") != "ask" or not state.get("report"):
        raise ValueError("only_failed_question_can_return_to_prior_report")
    review = state["report_review"]
    material = bool(state.get("research_stop_reason") or review.get("unresolved_data_requests")) or any(f["severity"] == "material" for f in review["findings"])
    return {"last_output_kind": "failed_question", "phase": "needs_revision" if material else "ready_for_human_review",
        "conversation": [{"role": "system", "content": reason + " 本次没有交出答案；已有报告和失败记录保留。不会自动重试，请按需要提出新的问题。"}]}


def build_report_session_graph(*, writer, verifier, artifacts, initial, audits=None, quick_writer=None,
                               state_schema=SessionState, input_schema=SessionInput, start_at_initialize=True, revision_handler=None):
    """One human request, native agentic work, then another real interrupt.

    There is no automatic rewrite-until-PASS edge. Report acceptance is a human
    review state only, never release/Evidence/SQL authority.
    """
    audits = audits or {}
    graph = StateGraph(state_schema, input_schema=input_schema)

    def initialize(state):
        if state.get("initialized"):
            raise ValueError("existing_session_requires_native_interrupt_resume_not_restart")
        material = initial(state) if callable(initial) else initial
        return {"initialized": True, "report": deepcopy(material["report"]),
            "report_review": deepcopy(material["report_review"]), "revisions": deepcopy(material["revisions"]),
            "report_version": 1, "phase": material.get("phase", "needs_revision"), "conversation": [], "model_events": []}

    def human_review(state):
        response = interrupt({"kind": "dell_report_review", "report_version": state["report_version"],
            "phase": state["phase"], "actions": ["ask", "revise", "accept"],
            "notice": "Acceptance is local human report review, not automatic release or financial authority."})
        action = ReviewAction.model_validate(response)
        if action.action == "accept":
            review = state["report_review"]
            if (state.get("research_stop_reason") or review.get("unresolved_data_requests") or any(f["severity"] == "material" for f in review["findings"])
                    or any(r["disposition"] == "unresolved" for v in state.get("revisions", {}).values()
                           for r in v.get("finding_responses", []))):
                raise ValueError("material_findings_require_revision_before_acceptance")
            return Command(update={"phase": "human_reviewed_not_released"}, goto=END)
        if not action.message.strip():
            raise ValueError("human_question_or_revision_feedback_required")
        target = "quick_writer" if action.answer_mode == "quick" else "writer"
        if action.action == "revise" and revision_handler is not None:
            target = "research_revision"
        if target == "quick_writer" and quick_writer is None:
            raise ValueError("quick_answer_not_configured")
        return Command(update={"request_action": action.action, "message": action.message,
            "phase": "working", "conversation": [{"role": "user", "content": action.message,
                "action": action.action, "answer_mode": action.answer_mode}]}, goto=target)

    def seed(state, role):
        current_artifacts = artifacts(state) if callable(artifacts) else artifacts
        view = current_artifacts.with_revisions(state["revisions"])
        body = {"research_as_of": current_artifacts.research_as_of, "catalog": view.catalog()}
        if state.get("question"):
            body["research_question"] = state["question"]
        if role in {"writer", "quick_writer"}:
            # Do not repeat the large citation object: canonical IDs resolve via tools.
            body.update(request_action=state["request_action"], user_message=state["message"],
                public_conversation=[{k: m[k] for k in ("role", "content")} for m in state.get("conversation", [])[:-1]])
            if role == "quick_writer":
                body["report_overview"] = {"title": state["report"]["title"], "version": state["report_version"],
                    "read_on_demand": "read_current_report for the complete current prose; use relevant sources for facts."}
            else:
                body["revision_request"] = {"prior_report": report_model_view(state["report"]),
                    "independent_review": state["report_review"], "human_feedback_is_not_evidence": True}
        else:
            body["report"] = report_model_view(state["report"])
            if state["report"].get("applied_edits"):
                body["revision_context"] = {"applied_edits": state["report"]["applied_edits"],
                    "previous_review": state["report_review"],
                    "method": "Incremental review after a complete prior report review: inspect every edit and unresolved finding, and scan unchanged context for contradiction or regression. Prior reviewers can be wrong. Read original sources where needed; do not reread all ten papers by ritual or assume unchanged text is automatically correct."}
        get_stream_writer()({"kind": "stage", "actor": role, "event": "started", "recorded_at": datetime.now(timezone.utc).isoformat()})
        return {"messages": [HumanMessage(content=json.dumps(body, ensure_ascii=False))],
            "revisions": state["revisions"], "report": state["report"], "request_action": state["request_action"],
            **({"case_papers": state["case_papers"]} if "case_papers" in state else {})}

    def collect(state, role):
        output = state.get("output")
        if not output:
            raise ValueError(f"session_agent_ended_without_submission:{role}")
        events = deepcopy(audits[role].events) if role in audits else []
        if role in audits:
            audits[role].events.clear()
        get_stream_writer()({"kind": "stage", "actor": role, "event": "outcome", "status": "handoff", "recorded_at": datetime.now(timezone.utc).isoformat()})
        if role == "verifier":
            return {"report_review": output, "model_events": events}
        if output.get("kind") == "answer":
            return {"last_output_kind": "answer", "model_events": events,
                "conversation": [{"role": "assistant", "content": output["answer_markdown"], "citations": output["citations"]}]}
        return {"report": output, "last_output_kind": "report", "model_events": events}

    def finish(state):
        review = state["report_review"]
        material = (bool(state.get("research_stop_reason") or review.get("unresolved_data_requests"))
            or any(f["severity"] == "material" for f in review["findings"])
            or any(r["disposition"] == "unresolved" for v in state.get("revisions", {}).values()
                   for r in v.get("finding_responses", [])))
        return {"report_version": state["report_version"] + (state["last_output_kind"] == "report"),
            "phase": "needs_revision" if material else "ready_for_human_review"}

    def question_error(state, error: NodeError):
        from langchain.agents.middleware.model_call_limit import ModelCallLimitExceededError
        from langchain.agents.middleware.tool_call_limit import ToolCallLimitExceededError
        recognized = isinstance(error.error, (ModelCallLimitExceededError, ToolCallLimitExceededError)) or (
            isinstance(error.error, ValueError) and str(error.error) in {
                "case_review_input_ceiling_before_transport", "case_review_truncated_no_partial_acceptance"})
        if state.get("request_action") != "ask" or not recognized:
            raise error.error
        update = abandoned_question_update(state, "本次追问触及执行预算或输出截断，已停止。")
        audit = audits.get(error.node)
        if audit is not None:
            update["model_events"] = deepcopy(audit.events)
            audit.events.clear()
        get_stream_writer()({"kind": "stage", "actor": error.node, "event": "outcome", "status": "error",
            "error_type": type(error.error).__name__, "recorded_at": datetime.now(timezone.utc).isoformat()})
        return Command(update=update, goto="finish")

    graph.add_node("initialize", initialize)
    agents = {"writer": writer, "verifier": verifier}
    if quick_writer is not None:
        agents["quick_writer"] = quick_writer
    graph.add_node("human_review", human_review, destinations=(*agents, *(("research_revision",) if revision_handler is not None else ()), END))
    if revision_handler is not None:
        graph.add_node("research_revision", revision_handler)
        graph.add_edge("research_revision", "human_review")
    for role, agent in agents.items():
        graph.add_node(role, RunnableLambda(lambda s, r=role: seed(s, r)) | agent | RunnableLambda(lambda s, r=role: collect(s, r)),
            error_handler=question_error if role != "verifier" else None)
    graph.add_node("finish", finish)
    if start_at_initialize:
        graph.add_edge(START, "initialize")
    graph.add_edge("initialize", "human_review")
    graph.add_conditional_edges("writer", lambda s: "verifier" if s["last_output_kind"] == "report" else "finish")
    graph.add_edge("verifier", "finish")
    if quick_writer is not None:
        graph.add_edge("quick_writer", "finish")
    graph.add_edge("finish", "human_review")
    return graph


def load_quick_answer_config(model_config_path):
    """Checked-in task profile next to the existing deployment config, never browser-selected."""
    path = Path(model_config_path).with_name("fin_ia_0_1_3_dell_report_quick_answer_v1_0.json")
    settings = json.loads(path.read_text(encoding="utf-8"))
    profile = DeepSeekModelProfile.model_validate(settings["model_profile"])
    basis = TokenBudgetBasis.model_validate_json(json.dumps(settings["token_budget_basis"]))
    if profile.model != "deepseek-v4-flash" or profile.thinking != "disabled" or basis.reasoning_profile != "agentic_message_history_thinking_disabled":
        raise ValueError("quick_answer_profile_budget_mismatch")
    return profile, basis, settings["limits"]


def session_audit_sinks(audit_root):
    """Reuse the local public/private call files; no new telemetry backend."""
    audit_root = Path(audit_root)
    audit_root.mkdir(parents=True, exist_ok=True)
    lock = Lock()
    def sink(name):
        def write(event):
            with lock, (audit_root / name).open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(event, ensure_ascii=False) + "\n")
        return write
    return sink("model-call-events.jsonl"), sink("model-context-reasoning.private.jsonl")


def compatible_archived_citations(resolved, archived):
    """Only missing additive locator metadata may differ in pre-migration reports.

    All saved claims, source IDs, text, values, periods and existing locator
    values still compare exactly. The immutable archived report is not rewritten.
    """
    candidate = deepcopy(resolved)
    additive = {"source_locator", "parser_page_start", "parser_page_end", "page_semantics",
        "section_path", "document_id", "node_id", "company", "issuer_id", "content_sha256"}
    for ref, row in candidate.items():
        old = archived.get(ref, {})
        for source, saved in zip(row.get("sources", []), old.get("sources", [])):
            for key in additive - saved.keys():
                source.pop(key, None)
    return candidate == archived


def load_session_materials(settings):
    from .dell_specialist_paid_shadow import file_sha256
    paths = {key: Path(settings[key + "_path"]) for key in ("bundle", "report")}
    for key, path in paths.items():
        if file_sha256(path) != settings[key + "_sha256"]:
            raise ValueError(f"session_{key}_binding_invalid")
    bundle = json.loads(paths["bundle"].read_text(encoding="utf-8"))
    state = json.loads(paths["report"].read_text(encoding="utf-8"))["values"]
    artifacts = DellCaseArtifacts(bundle["papers"])
    initial = {k: deepcopy(state[k]) for k in ("report", "report_review", "revisions")}
    view = artifacts.with_revisions(initial["revisions"])
    resolved = report_citations(CaseReport.model_validate({k: initial["report"][k] for k in ("title", "narrative_markdown")}), view)
    if not compatible_archived_citations(resolved, initial["report"]["citations"]):
        raise ValueError("session_report_citation_binding_invalid")
    ReportReview.model_validate(initial["report_review"])
    return artifacts, initial


@lru_cache(maxsize=1)
def _schema_graph():
    from langchain_core.language_models.chat_models import BaseChatModel
    class UnavailableModel(BaseChatModel):
        @property
        def _llm_type(self):
            return "schema-only"
        def _generate(self, *args, **kwargs):
            raise RuntimeError("schema_only_execution_unavailable")
    agents = {role: build_case_output_agent(role=role, model=UnavailableModel(), tools=[], artifacts=None,
        limits={"model_calls": 16, "tool_calls": 48}, report_revision=True, allow_answers=role == "writer")
        for role in ("writer", "verifier")}
    agents["quick_writer"] = build_case_output_agent(role="writer", model=UnavailableModel(), tools=[], artifacts=None,
        limits={"model_calls": 8, "tool_calls": 24}, allow_answers=True, answer_only=True)
    return build_report_session_graph(**agents, artifacts=None, initial={}).compile(name="dell_report_session")


@asynccontextmanager
async def dell_report_session_graph(config: RunnableConfig, runtime: ServerRuntime):
    if runtime.execution_runtime is None:
        yield _schema_graph()
        return
    from mcp import Client
    from .dell_agent_server_data_composition import open_dell_approved_data_composition
    from .dell_agent_server_entry import _require_langsmith_execution_environment
    _require_langsmith_execution_environment(config)
    ids = config["configurable"]
    thread_id, run_id = str(UUID(str(ids["thread_id"]))), str(UUID(str(ids["run_id"])))
    settings = json.loads(Path(os.environ["FINSIGHT_REPORT_SESSION_SETTINGS"]).read_text(encoding="utf-8"))
    if settings.get("owner_scope") != "funded_local_dell_report_review_only":
        raise ValueError("session_owner_scope_required")
    artifacts, initial = load_session_materials(settings)
    model_config = load_deepseek_structured_agent_config(settings["model_config_path"])
    quick_profile, quick_basis, quick_limits = load_quick_answer_config(settings["model_config_path"])
    audit_root = Path(settings["audit_root"]) / thread_id / run_id
    public_sink, private_sink = session_audit_sinks(audit_root)
    invocation = "invocation:dell:workbench:" + run_id
    with open_dell_approved_data_composition(run_invocation_id=invocation, source_read_enabled=True,
            live_web_read_enabled=True, case_artifacts=artifacts) as data:
        if (artifacts.case_id != data.foundation_binding.case_id or artifacts.foundation_digest != data.foundation_binding.foundation_digest
                or artifacts.snapshot_id != data.foundation_binding.snapshot_id
                or artifacts.owner_data_gate_decision_digest != data.decision_digest
                or artifacts.inventory_snapshot_digest != data.inventory_snapshot_digest
                or artifacts.source_route_catalog_digest != data.source_route_catalog_digest):
            raise ValueError("session_data_authority_mismatch")
        async with Client(data.mcp_server, raise_exceptions=False, read_timeout_seconds=120) as client:
            args = {"research_as_of": artifacts.research_as_of, "data_snapshot_id": artifacts.snapshot_id, "execution_attempt_id": invocation}
            binding = await client.call_tool("get_dell_research_method", {"branch_ids": sorted({p["branch_id"] for p in artifacts.catalog()["papers"]}), **args})
            if binding.is_error:
                raise ValueError("session_method_binding_failed")
            tools = await case_mcp_tools(client, run_scope=binding.structured_content["run_scope"], method_arguments=args)
            agents, audits = {}, {}
            for role in ("writer", "verifier", "quick_writer"):
                quick = role == "quick_writer"
                basis = quick_basis if quick else TokenBudgetBasis.model_validate_json(json.dumps(settings["node_budgets"][role]))
                profile = quick_profile if quick else model_config.profile_for("specialist" if role == "writer" else "verifier")
                if basis.reasoning_profile != "agentic_message_history_thinking_" + profile.thinking:
                    raise ValueError("session_budget_thinking_mismatch")
                audits[role] = CaseModelAudit(actor=role, profile=profile, basis=basis,
                    public_sink=public_sink, private_sink=private_sink, stream_public=True)
                agents[role] = build_case_output_agent(role="writer" if quick else role, model=case_chat_model(profile, basis, model_config, SecretStr(os.environ["DEEPSEEK_API_KEY"])),
                    tools=tools, artifacts=artifacts, limits=quick_limits if quick else settings["node_limits"][role], audit=audits[role],
                    report_revision=True, allow_answers=role != "verifier", answer_only=quick)
            yield build_report_session_graph(**agents, artifacts=artifacts, initial=initial, audits=audits).compile(
                name="dell_report_session").with_config({"recursion_limit": 240})
