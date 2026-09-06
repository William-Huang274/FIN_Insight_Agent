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
from langgraph.types import Command, interrupt
from langgraph_sdk.runtime import ServerRuntime
from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

from .deepseek_structured_agents import DeepSeekModelProfile, TokenBudgetBasis, load_deepseek_structured_agent_config
from .dell_case_artifacts import DellCaseArtifacts
from .dell_case_convergence_agent import build_case_output_agent, report_citations, CaseReport, ReportReview
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


def build_report_session_graph(*, writer, verifier, artifacts, initial, audits=None, quick_writer=None):
    """One human request, native agentic work, then another real interrupt.

    There is no automatic rewrite-until-PASS edge. Report acceptance is a human
    review state only, never release/Evidence/SQL authority.
    """
    audits = audits or {}
    graph = StateGraph(SessionState, input_schema=SessionInput)

    def initialize(state):
        if state.get("initialized"):
            raise ValueError("existing_session_requires_native_interrupt_resume_not_restart")
        return {"initialized": True, "report": deepcopy(initial["report"]),
            "report_review": deepcopy(initial["report_review"]), "revisions": deepcopy(initial["revisions"]),
            "report_version": 1, "phase": "needs_revision", "conversation": [], "model_events": []}

    def human_review(state):
        response = interrupt({"kind": "dell_report_review", "report_version": state["report_version"],
            "phase": state["phase"], "actions": ["ask", "revise", "accept"],
            "notice": "Acceptance is local human report review, not automatic release or financial authority."})
        action = ReviewAction.model_validate(response)
        if action.action == "accept":
            review = state["report_review"]
            if review.get("unresolved_data_requests") or any(f["severity"] == "material" for f in review["findings"]):
                raise ValueError("material_findings_require_revision_before_acceptance")
            return Command(update={"phase": "human_reviewed_not_released"}, goto=END)
        if not action.message.strip():
            raise ValueError("human_question_or_revision_feedback_required")
        target = "quick_writer" if action.answer_mode == "quick" else "writer"
        if target == "quick_writer" and quick_writer is None:
            raise ValueError("quick_answer_not_configured")
        return Command(update={"request_action": action.action, "message": action.message,
            "phase": "working", "conversation": [{"role": "user", "content": action.message,
                "action": action.action, "answer_mode": action.answer_mode}]}, goto=target)

    def seed(state, role):
        view = artifacts.with_revisions(state["revisions"])
        body = {"research_as_of": artifacts.research_as_of, "catalog": view.catalog()}
        if role in {"writer", "quick_writer"}:
            # Do not repeat the large citation object: canonical IDs resolve via tools.
            body.update(request_action=state["request_action"], user_message=state["message"],
                public_conversation=[{k: m[k] for k in ("role", "content")} for m in state.get("conversation", [])[:-1]])
            if role == "quick_writer":
                body["report_overview"] = {"title": state["report"]["title"], "version": state["report_version"],
                    "read_on_demand": "read_current_report for the complete current prose; use relevant sources for facts."}
            else:
                body["revision_request"] = {"prior_report": {k: state["report"][k] for k in ("title", "narrative_markdown")},
                    "independent_review": state["report_review"], "human_feedback_is_not_evidence": True}
        else:
            body["report"] = {k: state["report"][k] for k in ("title", "narrative_markdown")}
            if state["report"].get("applied_edits"):
                body["revision_context"] = {"applied_edits": state["report"]["applied_edits"],
                    "previous_review": state["report_review"],
                    "method": "Incremental review after a complete prior report review: inspect every edit and unresolved finding, and scan unchanged context for contradiction or regression. Prior reviewers can be wrong. Read original sources where needed; do not reread all ten papers by ritual or assume unchanged text is automatically correct."}
        get_stream_writer()({"kind": "stage", "actor": role, "event": "started", "recorded_at": datetime.now(timezone.utc).isoformat()})
        return {"messages": [HumanMessage(content=json.dumps(body, ensure_ascii=False))],
            "revisions": state["revisions"], "report": state["report"], "request_action": state["request_action"]}

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
        material = bool(review.get("unresolved_data_requests")) or any(f["severity"] == "material" for f in review["findings"])
        return {"report_version": state["report_version"] + (state["last_output_kind"] == "report"),
            "phase": "needs_revision" if material else "ready_for_human_review"}

    graph.add_node("initialize", initialize)
    agents = {"writer": writer, "verifier": verifier}
    if quick_writer is not None:
        agents["quick_writer"] = quick_writer
    graph.add_node("human_review", human_review, destinations=(*agents, END))
    for role, agent in agents.items():
        graph.add_node(role, RunnableLambda(lambda s, r=role: seed(s, r)) | agent | RunnableLambda(lambda s, r=role: collect(s, r)))
    graph.add_node("finish", finish)
    graph.add_edge(START, "initialize")
    graph.add_edge("initialize", "human_review")
    graph.add_conditional_edges("writer", lambda s: "finish" if s["last_output_kind"] == "answer" else "verifier")
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
    if resolved != initial["report"]["citations"]:
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
    audit_root.mkdir(parents=True, exist_ok=True)
    lock = Lock()
    def sink(name):
        def write(event):
            with lock, (audit_root / name).open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(event, ensure_ascii=False) + "\n")
        return write
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
                    public_sink=sink("model-call-events.jsonl"), private_sink=sink("model-context-reasoning.private.jsonl"), stream_public=True)
                agents[role] = build_case_output_agent(role="writer" if quick else role, model=case_chat_model(profile, basis, model_config, SecretStr(os.environ["DEEPSEEK_API_KEY"])),
                    tools=tools, artifacts=artifacts, limits=quick_limits if quick else settings["node_limits"][role], audit=audits[role],
                    report_revision=True, allow_answers=role != "verifier", answer_only=quick)
            yield build_report_session_graph(**agents, artifacts=artifacts, initial=initial, audits=audits).compile(
                name="dell_report_session").with_config({"recursion_limit": 240})
