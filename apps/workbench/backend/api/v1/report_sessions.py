"""Thin local Workbench BFF for the native Dell review graph.

No generic proxy, application queue, checkpoint store or private-message route.
The native server owns sessions/runs/concurrency. Browser inputs cannot select
graphs, credentials, paths, model budgets or arbitrary checkpoint updates.
"""
from __future__ import annotations

import json
import re
from difflib import unified_diff
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit, unquote, quote
from uuid import UUID

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse, Response
from starlette.concurrency import run_in_threadpool
from langgraph_sdk.client import LangGraphClient
from pydantic import BaseModel, ConfigDict, Field

from sec_agent.agent_runtime.dell_report_session import ReviewAction, abandoned_question_update
from sec_agent.agent_runtime.targeted_revision import report_digest, validate_revision_target
from .research_studio import build_studio_router, run_configuration, owned_configuration
from sec_agent.agent_runtime.execution_options import ExecutionOptions

SURFACE = "dell_report_workbench"
GRAPH = "dell_report_session"
RESEARCH_GRAPH = "research_session"
PUBLIC_EVENT_FIELDS = frozenset({"kind", "actor", "event", "status", "call_id", "tool", "recorded_at",
    "model", "thinking", "reasoning_effort", "elapsed_ms", "input_tokens", "output_tokens", "total_tokens",
    "cache_hit_tokens", "cache_miss_tokens", "reasoning_tokens", "usage_reported", "error_type", "http_status_code",
    "max_output_tokens", "valid_tool_call_count", "invalid_tool_call_count", "success_scope", "run_id",
    "task_id", "objective", "responsible_author_count", "correction_round", "paper_id", "input_characters", "max_input_characters", "provider_call_attempted"})


def public_run_usage(audit_root, thread_id, run_id):
    """Read the existing public audit sink, including failed native nodes.

    No new store or billing authority; private message/reasoning files are never
    opened. The directory is host configured, IDs come from owned native runs.
    """
    if audit_root is None:
        return [], None
    root = Path(audit_root).resolve()
    path = (root / str(UUID(str(thread_id))) / str(UUID(str(run_id))) / "model-call-events.jsonl").resolve()
    if not path.is_relative_to(root):
        raise ValueError("public_audit_path_outside_configured_root")
    if not path.is_file():
        return [], None  # unavailable is not a measured zero
    events, partial = [], False
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            partial = True  # append in progress/corruption; do not claim complete usage
            continue
        if not isinstance(raw, dict):
            partial = True
            continue
        if event := public_event({"kind": "model", **raw, "run_id": str(run_id)}):
            events.append(event)
    recovery = path.parent / "public-output-recovery.json"
    if recovery.is_file() and recovery.resolve().is_relative_to(root):
        recovered = json.loads(recovery.read_text(encoding="utf-8"))
        if recovered.get("origin") == "explicit_submission_projection_not_acceptance":
            events.extend(p for row in recovered.get("events", [])
                if (p := public_event({**row, "run_id": str(run_id)})) and p.get("kind") == "stage")
    ids = {e["call_id"] for e in events if e.get("kind") == "model" and e.get("call_id")}
    outcomes = {e["call_id"]: e for e in events if e.get("kind") == "model" and e.get("call_id") and e.get("event") == "outcome"}
    not_attempted = {i for i, e in outcomes.items() if e.get("provider_call_attempted") is False}
    possible_calls = ids - not_attempted
    totals = {key: sum(e[key] for e in outcomes.values() if isinstance(e.get(key), (int, float)) and not isinstance(e.get(key), bool))
              for key in ("input_tokens", "output_tokens", "total_tokens", "cache_hit_tokens", "cache_miss_tokens", "elapsed_ms")}
    return events, {"recorded_requests": len(ids), "reported_requests": sum(isinstance(e.get("total_tokens"), int) for e in outcomes.values()),
        "not_attempted_requests": len(not_attempted),
        "unknown_or_pending_requests": sum(not isinstance(outcomes.get(i, {}).get("total_tokens"), int) for i in possible_calls),
        "unknown_cache_requests": sum(not all(isinstance(outcomes.get(i, {}).get(k), int) for k in ("cache_hit_tokens", "cache_miss_tokens")) for i in possible_calls),
        "unknown_elapsed_requests": sum(not isinstance(outcomes.get(i, {}).get("elapsed_ms"), (int, float)) for i in possible_calls),
        "partial_audit": partial, **totals}


def public_event(value):
    if not isinstance(value, dict):
        return None
    result = {k: v for k, v in value.items() if k in PUBLIC_EVENT_FIELDS and isinstance(v, (str, int, float, bool, type(None)))}
    if result.get("kind") == "task":
        result["dependency_ids"] = [v for v in value.get("dependency_ids", []) if isinstance(v, str)][:24]
    if result.get("actor") == "responsibility_router":
        result["responsible_paper_ids"] = [v for v in value.get("responsible_paper_ids", [])
            if isinstance(v, str) and re.fullmatch(r"P\d{2}", v)][:24]
    return result if result.get("kind") in {"model", "tool", "stage", "task"} else None


def public_native_failures(state, run):
    """Project the latest native checkpoint's failure without raw exception data.

    Checkpoints belong to the native server. Never assign their current failure
    to an older run or expose provider payloads, filesystem paths or credentials.
    """
    events = []
    for index, task in enumerate(state.get("tasks", [])):
        raw = task.get("error")
        if not isinstance(raw, str) or not raw:
            continue
        match = re.match(r"(ValueError|RuntimeError|TypeError|TimeoutError)\(['\"]([a-z_]{3,96})(?=[:'\"])", raw)
        error_type, code = match.groups() if match else ("NativeNodeError", None)
        summary = "原生运行节点失败；已产生的候选输出保留，未通过的产物不会作为正式报告。"
        if code == "research_bundle_invalid_citations":
            summary = "研究底稿未通过交接时的引用校验，因而停止生成报告。已提交的候选底稿仍可查看。"
        elif code:
            summary = "原生节点返回执行错误，已产生的候选输出保留。"
        if code:
            summary += f"\n\n系统错误代码：`{code}`。此为运行系统的记录，并非模型自行解释。"
        actor = task.get("name", "research")
        actor = actor if isinstance(actor, str) and re.fullmatch(r"[a-z_]{1,80}", actor) else "research"
        events.append({"kind": "stage", "actor": actor, "event": "failure", "status": "error",
            "error_type": error_type, "objective": summary, "run_id": run["run_id"],
            "call_id": f"native-failure:{run['run_id']}:{index}",
            "recorded_at": run.get("updated_at") or run.get("created_at")})
    return events


def public_cost_estimate(events):
    from scripts.qualification.dell_q1_specialist_paid_shadow.audit_token_cost import OFF_PEAK, PRICE_AS_OF, cost_parts, peak_multiplier
    starts = {e["call_id"]: e for e in events if e.get("kind", "model") == "model" and e.get("call_id") and e.get("event") == "started"}
    outcomes = {e["call_id"]: e for e in events if e.get("kind", "model") == "model" and e.get("call_id") and e.get("event") == "outcome"}
    amount, priced = 0.0, 0
    not_attempted = {i for i, e in outcomes.items() if e.get("provider_call_attempted") is False}
    for call_id, outcome in outcomes.items():
        if call_id in not_attempted:
            continue
        start = starts.get(call_id, {})
        model = start.get("model") or outcome.get("model")
        counts = [outcome.get(key) for key in ("cache_hit_tokens", "cache_miss_tokens", "output_tokens")]
        timestamp = start.get("recorded_at") or outcome.get("recorded_at")
        if model in OFF_PEAK and timestamp and all(type(n) is int and n >= 0 for n in counts):
            amount += sum(cost_parts(model, *counts, peak_multiplier(timestamp)).values())
            priced += 1
    return {"known_cny": round(amount, 6), "priced_requests": priced, "not_attempted_requests": len(not_attempted),
        "unknown_or_pending_requests": len((set(starts) | set(outcomes)) - not_attempted) - priced,
        "price_as_of": PRICE_AS_OF, "notice": "按已报告用量和公开分时单价估算，不是账单；未知/进行中请求未计入。"}


def review_interrupts(state):
    items = list(state.get("interrupts") or [])
    for task in state.get("tasks", []):
        items.extend(task.get("interrupts") or [])
    return [i for i in items if isinstance(i, dict) and isinstance(i.get("value"), dict)
        and i["value"].get("kind") == "dell_report_review"]


def public_state(state):
    values = state.get("values", {})
    result = {k: deepcopy(values[k]) for k in ("report", "report_review", "report_version", "phase", "conversation",
        "question", "case_profile", "research_as_of", "snapshot_id", "research_stop_reason") if k in values}
    outcomes = {row["task_id"]: row["status"] for row in values.get("research_outcomes", [])}
    result["research_tasks"] = [{**{key: deepcopy(row[key]) for key in ("task_id", "owner_role", "objective", "dependency_ids") if key in row},
        "status": outcomes.get(row["task_id"], row.get("status", "planned"))} for row in values.get("research_tasks", [])]
    from sec_agent.agent_runtime.research_session import can_continue_remaining_research
    result["can_continue_remaining"] = can_continue_remaining_research(values)
    result["research_attempt_history"] = [{key: deepcopy(row[key]) for key in ("run_id", "phase", "outcomes") if key in row}
        for row in values.get("research_attempt_history", [])]
    result["research_failures"] = []
    for row in values.get("research_failed_workpapers", []):
        agent = row.get("agent_state") or {}
        attempt = agent.get("last_submission_attempt") or {}
        arguments = attempt.get("arguments")
        # Only explicit deliverable prose is public. Invalid JSON, raw tool
        # payloads, private reasoning and checkpoint notebooks stay server-side.
        candidate = {key: arguments[key] for key in ("thesis", "mechanism", "narrative_markdown", "summary")
            if isinstance(arguments, dict) and isinstance(arguments.get(key), str)}
        notebook = agent.get("notebook") or {}
        records = notebook.get("model_turn_records") or []
        last_action = records[-1].get("action", {}) if records else {}
        # This is the model's explicit public handoff rationale, not reasoning
        # text and not a host-generated claim that unfinished work succeeded.
        explanation = last_action.get("reason_summary") if last_action.get("action") == "request_human_review" else None
        result["research_failures"].append({"run_id": row.get("run_id"), "task_id": row.get("task_id"),
            "reason": agent.get("review_reason"), "candidate": candidate,
            "model_explanation": explanation if isinstance(explanation, str) else None,
            "accepted": False,
            "validation_issues": [{key: deepcopy(item[key]) for key in ("location", "type", "message") if key in item}
                for item in attempt.get("validation_issues", []) if isinstance(item, dict)],
            "feedback_codes": list(dict.fromkeys(item["code"] for item in
                (attempt.get("feedback") or notebook.get("feedback", [])[-10:])
                if isinstance(item, dict) and isinstance(item.get("code"), str))),
            "model_turns": notebook.get("model_turn_count"), "tool_actions": notebook.get("tool_action_count"),
            "saved_observations": len(notebook.get("observations", []))})
    # Public source-bound deliverables, not private agent message histories.
    result["research_synthesis"] = {key: deepcopy(values["synthesis"][key]) for key in ("title", "narrative_markdown")
        if key in values.get("synthesis", {})}
    if values.get("synthesis_review"):
        result["synthesis_review"] = deepcopy(values["synthesis_review"])
    result["workpaper_reviews"] = []
    for actor in ("counter", "verifier"):
        review = values.get("case_review", {}).get(actor, {}).get("review")
        if not review:
            continue
        result["workpaper_reviews"].append({"actor": actor, "summary": review["summary"],
            "findings": [{key: deepcopy(row[key]) for key in ("finding_id", "paper_id", "severity",
                "problematic_quote", "diagnosis", "requested_change") if key in row} for row in review.get("findings", [])]})
    result["responsibility_history"] = [{"actor": row["actor"], "correction_round": row["correction_round"]}
        for row in values.get("convergence_history", [])]
    result["model_events"] = [p for e in values.get("model_events", []) if (p := public_event({"kind": "model", **e}))]
    result["can_respond"] = bool(review_interrupts(state))
    result["report_digest"] = report_digest(values["report"]) if values.get("report") else None
    result["can_accept"] = result["can_respond"] and result.get("phase") == "ready_for_human_review"
    # No tasks, raw native messages, private checkpoints or source filesystem paths.
    return result


def can_abandon_question(thread, state, last_run=None):
    tasks = state.get("tasks") or []
    # Some native error-handler failures expose no pending tasks in state.
    # Use the latest server-owned run metadata, never browser-supplied state.
    missing_task_failure = (not tasks and last_run and last_run.get("status") == "error"
        and last_run.get("metadata", {}).get("human_action") == "ask"
        and last_run.get("metadata", {}).get("surface") == SURFACE)
    return (thread.get("status") == "error" and not review_interrupts(state)
        and state.get("values", {}).get("request_action") == "ask"
        and bool(state.get("values", {}).get("report"))
        and (missing_task_failure or (bool(tasks)
            and all(t.get("name") in {"writer", "quick_writer"} and t.get("error") for t in tasks))))


def can_restart_remaining_node(thread, state, last_run, usage):
    tasks = state.get("tasks", [])
    return bool(thread.get("status") == "error" and len(tasks) == 1
        and tasks[0].get("name") in {"remaining_research", "convergence"} and tasks[0].get("error")
        and last_run and last_run.get("metadata", {}).get("human_action") in {"research", "continue_remaining"}
        and usage and usage["recorded_requests"] > 0 and not usage["unknown_or_pending_requests"] and not usage["partial_audit"])


class NewSession(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(default="新研究任务", min_length=1, max_length=120)
    mode: Literal["review", "research"] = "review"
    question: str | None = Field(default=None, min_length=10, max_length=16000)
    defer_start: bool = False
    studio_assistant_id: UUID | None = None
    execution: ExecutionOptions | None = None


class ResearchGuidance(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    message: str = Field(min_length=1, max_length=4000)


def graph_for_thread(thread):
    graph = thread.get("metadata", {}).get("graph", GRAPH)
    if graph not in {GRAPH, RESEARCH_GRAPH}:
        raise HTTPException(409, "会话的执行入口不受本工作台支持")
    return graph


class ReportSessionService:
    def __init__(self, api_url, artifacts, *, sdk=None, audit_root=None, research_profile=None, attachment_store=None):
        parsed = urlsplit(api_url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "langgraph-api"} or parsed.username or parsed.query or parsed.fragment:
            raise ValueError("report_session_server_must_be_local")
        self.http = httpx.AsyncClient(base_url=api_url, trust_env=False, transport=httpx.AsyncHTTPTransport(retries=0),
            timeout=httpx.Timeout(300, connect=5))
        self.sdk = sdk or LangGraphClient(self.http)
        self.artifacts = artifacts
        self.audit_root = audit_root
        self.research_profile = deepcopy(research_profile)
        self.attachment_store = attachment_store

    async def owned_thread(self, thread_id):
        thread = await self.sdk.threads.get(str(thread_id))
        if thread.get("metadata", {}).get("surface") != SURFACE:
            raise HTTPException(404, "研究会话不存在")
        return thread

    async def state(self, thread_id):
        await self.owned_thread(thread_id)
        return await self.sdk.threads.get_state(str(thread_id))

    async def report_state(self, thread_id, checkpoint_id=None):
        if checkpoint_id is None:
            return await self.state(thread_id)
        await self.owned_thread(thread_id)
        state = await self.sdk.threads.get_state(str(thread_id), checkpoint_id=str(checkpoint_id))
        if not report_snapshot(state):
            raise HTTPException(404, "该历史记录没有完成的报告版本")
        return state

    async def all_runs(self, thread_id):
        """Read native pagination; do not call ten recent runs a session total."""
        rows, offset = {}, 0
        while True:
            page = await self.sdk.runs.list(str(thread_id), limit=100, offset=offset)
            rows.update({row["run_id"]: row for row in page})
            if len(page) < 100:
                return list(rows.values())
            offset += len(page)

    async def report_history(self, thread_id, before=None):
        if before is None:
            return await self.sdk.threads.get_history(str(thread_id), limit=10)
        # API 0.13.3 POST rejects SDK string cursors and fails on its own
        # CheckpointConfig shape. Its documented GET cursor route works.
        response = await self.http.get(f"/threads/{thread_id}/history",
            params={"limit": 10, "before": str(before)})
        response.raise_for_status()
        return response.json()


def report_snapshot(state):
    """Only completed human-review snapshots, not intermediate Writer output."""
    values = state.get("values", {})
    return bool(values.get("report") and values.get("report_version") and (
        "human_review" in state.get("next", []) or values.get("phase") == "human_reviewed_not_released"))


def build_report_sessions_router(service):
    router = APIRouter()

    def browser_write(request):
        # A cross-site form/opaque fetch must not be able to start paid work.
        if request.headers.get("x-workbench-request") != "1":
            raise HTTPException(403, "缺少本地工作台请求标识")
        origin = request.headers.get("origin")
        if origin:
            allowed = {str(request.base_url).rstrip("/"), "http://127.0.0.1:5173", "http://localhost:5173"}
            if origin not in allowed:
                raise HTTPException(403, "拒绝跨站点执行请求")

    @router.get("/research-sessions")
    async def sessions():
        threads = await service.sdk.threads.search(metadata={"surface": SURFACE}, limit=50)
        return [{"thread_id": t["thread_id"], "status": t["status"], "updated_at": t["updated_at"],
            "title": t.get("metadata", {}).get("title", "研究任务"),
            "phase": (t.get("values") or {}).get("phase"),
            "studio_assistant_id": t.get("metadata", {}).get("studio_assistant_id")} for t in threads]

    @router.get("/research-session-config")
    async def configuration():
        profile = getattr(service, "research_profile", None)
        return {"fresh_research_enabled": profile is not None, "legacy_review_enabled": service.artifacts is not None,
            **(deepcopy(profile) if profile else {})}

    @router.get("/research-studio")
    async def research_studio():
        # Public, answer-free packaged methods; no caller-selected file paths or secrets.
        from sec_agent.research_foundation.research_methods import METHODS, get_research_method
        return {"methods": [get_research_method(key) for key in METHODS],
            "origin": "workbench_packaged_methods", "editable_runtime": False,
            "notice": "方法为本地工作台源码版本；草稿不发布到运行服务。运行图单独从原生服务读取。"}

    @router.get("/research-studio/graph/{kind}")
    async def research_studio_graph(kind: Literal["research", "review"]):
        graph_id = RESEARCH_GRAPH if kind == "research" else GRAPH
        try:
            graph = await service.sdk.assistants.get_graph(graph_id)
        except httpx.HTTPError as exc:
            raise HTTPException(502, "原生运行图暂不可读取，请稍后重试") from exc
        # Node data may include implementation details; expose only IDs and topology.
        return {"graph_id": graph_id, "origin": "native_runtime", "editable_runtime": False,
            "nodes": [{"id": str(n["id"])} for n in graph.get("nodes", [])],
            "edges": [{"source": str(e["source"]), "target": str(e["target"]),
                "conditional": bool(e.get("conditional"))} for e in graph.get("edges", [])]}

    @router.get("/research-sessions/{thread_id}/report-versions")
    async def report_versions(thread_id: UUID, before: UUID | None = None):
        await service.owned_thread(thread_id)
        history = await service.report_history(thread_id, before)
        versions = {}
        for state in history:
            if not report_snapshot(state):
                continue
            values = state["values"]
            number = values["report_version"]
            versions.setdefault(number, {"version": number, "checkpoint_id": state["checkpoint"]["checkpoint_id"],
                "created_at": state.get("created_at"), "title": values["report"]["title"],
                "reason": values.get("report_revision_reason") or "历史版本未单独记录修订原因"})
        return {"versions": list(versions.values()),
            "next_cursor": history[-1]["checkpoint"]["checkpoint_id"] if len(history) == 10 else None}

    @router.get("/research-sessions/{thread_id}/report-versions/{checkpoint_id}")
    async def report_version(thread_id: UUID, checkpoint_id: UUID):
        state = await service.report_state(thread_id, checkpoint_id)
        values = state["values"]
        return {"report": values["report"], "report_version": values["report_version"],
            "report_digest": report_digest(values["report"]),
            "report_review": values.get("report_review"), "reason": values.get("report_revision_reason"),
            "checkpoint_id": str(checkpoint_id)}

    @router.get("/research-sessions/{thread_id}/report-diff")
    async def report_diff(thread_id: UUID, before: UUID, after: UUID | None = None):
        old = (await service.report_state(thread_id, before))["values"]
        current = await service.report_state(thread_id, after)
        if not report_snapshot(current):
            raise HTTPException(409, "当前修订尚未完成，请完成后比较，或选择已完成的历史版本")
        new = current["values"]
        if not new.get("report"):
            raise HTTPException(409, "报告尚未生成")
        return {"before_version": old["report_version"], "after_version": new["report_version"],
            "reason": new.get("report_revision_reason") or "历史版本未单独记录修订原因",
            "diff": "\n".join(unified_diff(old["report"]["narrative_markdown"].splitlines(),
                new["report"]["narrative_markdown"].splitlines(), fromfile=f"v{old['report_version']}",
                tofile=f"v{new['report_version']}", lineterm="")),
            "charts_changed": old["report"].get("charts", []) != new["report"].get("charts", []),
            "citations_changed": old["report"].get("citations", {}) != new["report"].get("citations", {})}

    @router.post("/research-sessions")
    async def create(body: NewSession, request: Request):
        browser_write(request)
        graph, payload = GRAPH, {"open": True}
        if body.mode == "research":
            profile = getattr(service, "research_profile", None)
            if not profile:
                raise HTTPException(503, "完整新研究入口尚未在本部署启用；不会退回旧报告冒充新研究")
            from sec_agent.agent_runtime.research_session import ResearchRequest
            graph = RESEARCH_GRAPH
            payload = ResearchRequest(question=body.question or profile["default_question"]).model_dump(mode="json")
        elif body.question is not None:
            raise HTTPException(422, "研究问题请使用新研究模式；打开旧报告不执行研究")
        elif service.artifacts is None:
            raise HTTPException(409, "本部署未配置旧报告；可以创建新研究或打开任务历史")
        if body.defer_start and body.mode != "research":
            raise HTTPException(422, "只有新研究支持先上传资料")
        metadata = {"surface": SURFACE, "title": body.title, "graph": graph, "mode": body.mode}
        if body.execution:
            if graph != RESEARCH_GRAPH:
                raise HTTPException(422, "运行模式选择仅适用于研究任务")
            try:
                body.execution.validate_catalog((service.research_profile or {}).get("branch_topics", []))
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc
            metadata["execution"] = body.execution.model_dump()
        if body.studio_assistant_id:
            if graph != RESEARCH_GRAPH:
                raise HTTPException(422, "研究配置需要新研究模式")
            _, studio = await owned_configuration(service, body.studio_assistant_id)
            metadata.update(studio_assistant_id=str(body.studio_assistant_id), studio_configuration_title=studio.title,
                studio_configuration_digest=studio.digest)
        if body.defer_start:
            metadata["pending_question"] = payload["question"]
        thread = await service.sdk.threads.create(metadata=metadata)
        if body.defer_start:
            return {"thread_id": thread["thread_id"], "run_id": None, "status": "draft"}
        run = await service.sdk.runs.create(thread["thread_id"], graph, input=payload, stream_mode="custom",
            config=await run_configuration(service, thread),
            stream_subgraphs=True, stream_resumable=True, multitask_strategy="reject", metadata={"surface": SURFACE, "human_action": body.mode, "execution": metadata.get("execution"), "request_message": payload.get("question")})
        return {"thread_id": thread["thread_id"], "run_id": run["run_id"], "status": run["status"]}

    @router.post("/research-sessions/{thread_id}/start")
    async def start_draft(thread_id: UUID, request: Request):
        browser_write(request)
        thread = await service.owned_thread(thread_id)
        question = thread.get("metadata", {}).get("pending_question")
        if graph_for_thread(thread) != RESEARCH_GRAPH or not service.research_profile or not question:
            raise HTTPException(409, "这不是待启动的新研究任务")
        if await service.sdk.runs.list(str(thread_id), limit=1):
            raise HTTPException(409, "本任务已有启动记录，请查看状态；不会重复启动付费研究")
        from sec_agent.agent_runtime.research_session import ResearchRequest
        run = await service.sdk.runs.create(str(thread_id), RESEARCH_GRAPH,
            config=await run_configuration(service, thread),
            input=ResearchRequest(question=question).model_dump(mode="json"), stream_mode="custom", stream_subgraphs=True,
            stream_resumable=True, multitask_strategy="reject", metadata={"surface": SURFACE, "human_action": "research", "execution": thread.get("metadata", {}).get("execution"), "request_message": question})
        return {"thread_id": str(thread_id), "run_id": run["run_id"], "status": run["status"]}

    @router.post("/research-sessions/{thread_id}/guidance")
    async def guidance(thread_id: UUID, body: ResearchGuidance, request: Request):
        browser_write(request)
        thread = await service.owned_thread(thread_id)
        if graph_for_thread(thread) != RESEARCH_GRAPH or thread.get("status") != "busy":
            raise HTTPException(409, "此入口仅用于研究运行中的补充意见；结束后请使用追问或修订")
        metadata = thread.get("metadata", {})
        items = list(metadata.get("research_guidance", []))
        if len(items) >= 12:
            raise HTTPException(409, "本任务已有12条运行中意见，请等待处理后在人工点继续")
        items.append({"message": body.message, "created_at": datetime.now(timezone.utc).isoformat()})
        await service.sdk.threads.update(str(thread_id), metadata={"research_guidance": items})
        return {"recorded": True, "notice": "已保存到原生任务。后续研究/审查/写作阶段交接时读取；不打断正在生成的模型回复，不绕过工具权限。"}

    @router.post("/research-sessions/{thread_id}/acknowledge-incomplete")
    async def acknowledge_incomplete(thread_id: UUID, request: Request):
        browser_write(request)
        thread = await service.owned_thread(thread_id)
        state = await service.sdk.threads.get_state(str(thread_id))
        interrupts = [*state.get("interrupts", []), *[i for task in state.get("tasks", []) for i in task.get("interrupts", [])]]
        if graph_for_thread(thread) != RESEARCH_GRAPH or not any(i.get("value", {}).get("kind") == "research_needs_attention" for i in interrupts):
            raise HTTPException(409, "当前没有待确认的未完成研究交接")
        run = await service.sdk.runs.create(str(thread_id), RESEARCH_GRAPH, command={"resume": {"action": "acknowledge"}},
            config=await run_configuration(service, thread),
            multitask_strategy="reject", metadata={"surface": SURFACE, "human_action": "acknowledge_incomplete", "model_calls_requested": 0})
        return {"run_id": run["run_id"], "notice": "只确认已查看；不接受报告、不重跑研究。"}

    @router.post("/research-sessions/{thread_id}/continue-remaining")
    async def continue_remaining(thread_id: UUID, request: Request):
        browser_write(request)
        thread = await service.owned_thread(thread_id)
        state = await service.sdk.threads.get_state(str(thread_id))
        interrupts = [*state.get("interrupts", []), *[i for task in state.get("tasks", []) for i in task.get("interrupts", [])]]
        handoff = any(i.get("value", {}).get("kind") == "research_needs_attention" for i in interrupts)
        known_failure = False
        if not handoff and thread.get("status") == "error":
            last_runs = await service.sdk.runs.list(str(thread_id), limit=1)
            if last_runs:
                _, usage = public_run_usage(service.audit_root, thread_id, last_runs[0]["run_id"])
                known_failure = can_restart_remaining_node(thread, state, last_runs[0], usage)
        if (graph_for_thread(thread) != RESEARCH_GRAPH or thread.get("status") == "busy"
                or not (public_state(state)["can_continue_remaining"] or known_failure)
                or not (handoff or known_failure)):
            raise HTTPException(409, "仅未完成研究交接或用量已知的接续失败可继续；未知结果不重发，不跳过审查或重跑已交稿")
        invocation = {"input": None} if known_failure else {"command": {"resume": {"action": "continue_remaining"}}}
        run = await service.sdk.runs.create(str(thread_id), RESEARCH_GRAPH, **invocation,
            config=await run_configuration(service, thread),
            stream_mode="custom", stream_subgraphs=True, stream_resumable=True, multitask_strategy="reject",
            metadata={"surface": SURFACE, "human_action": "continue_remaining"})
        return {"run_id": run["run_id"], "status": run["status"], "notice": "新调用只完成缺项；保留已提交底稿和原失败，不重发旧请求。"}

    def attachments():
        if service.attachment_store is None:
            raise HTTPException(503, "本部署尚未配置任务资料存储")
        return service.attachment_store

    @router.get("/research-sessions/{thread_id}/attachments")
    async def list_attachments(thread_id: UUID):
        await service.owned_thread(thread_id)
        return attachments().list(thread_id)

    @router.post("/research-sessions/{thread_id}/attachments")
    async def upload(thread_id: UUID, request: Request):
        browser_write(request)
        thread = await service.owned_thread(thread_id)
        if graph_for_thread(thread) != RESEARCH_GRAPH or thread.get("status") == "busy":
            raise HTTPException(409, "请在新研究开始前或安全人工点上传，不修改运行中资料")
        from sec_agent.research_foundation.task_attachments import MAX_BYTES
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > MAX_BYTES:
                raise HTTPException(413, "单文件上限20MiB")
        filename = unquote(request.headers.get("x-filename", ""))
        try:
            return await run_in_threadpool(attachments().add, thread_id, filename, bytes(body))
        except (ValueError, UnicodeError) as exc:
            raise HTTPException(422, str(exc)) from None
        except Exception:
            raise HTTPException(422, "文件解析失败，未启动模型。请检查文件是否加密、损坏或为不支持的格式。") from None

    @router.get("/research-sessions/{thread_id}/attachments/{document_id}")
    async def download_attachment(thread_id: UUID, document_id: str):
        await service.owned_thread(thread_id)
        try:
            row = attachments().get(thread_id, document_id)
        except ValueError:
            raise HTTPException(404, "本任务没有这份资料") from None
        return Response(row["body"], media_type="application/octet-stream", headers={
            "Content-Disposition": "attachment; filename*=UTF-8''" + quote(row["name"], safe=""),
            "X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"})

    @router.get("/research-sessions/{thread_id}")
    async def snapshot(thread_id: UUID):
        thread = await service.owned_thread(thread_id)
        state = await service.sdk.threads.get_state(str(thread_id))
        runs = await service.all_runs(thread_id)
        projection = public_state(state)
        if not runs and thread.get("metadata", {}).get("pending_question"):
            projection.update(question=thread["metadata"]["pending_question"], phase="draft", case_profile="dell_growth_quality")
        public_runs = []
        for run in runs:
            events, usage = public_run_usage(service.audit_root, thread_id, run["run_id"])
            if run is runs[0] and thread.get("status") == "error" and run.get("status") == "error":
                events.extend(public_native_failures(state, run))
            projection["model_events"].extend(events)
            public_runs.append({**{k: run.get(k) for k in ("run_id", "status", "created_at")},
                "revision_target": run.get("metadata", {}).get("revision_target"),
                "human_action": run.get("metadata", {}).get("human_action"),
                "request_message": run.get("metadata", {}).get("request_message"),
                "execution": run.get("metadata", {}).get("execution"),
                "answer_mode": run.get("metadata", {}).get("answer_mode"), "usage": usage})
            public_runs[-1]["cost_estimate"] = public_cost_estimate(events)
            from ...application.context_usage import request_context_usage
            public_runs[-1]["context_usage"] = request_context_usage(events)
            public_runs[-1]["model_calls_requested"] = run.get("metadata", {}).get("model_calls_requested")
            if run.get("status") not in {"pending", "running"} and run.get("created_at") and run.get("updated_at"):
                public_runs[-1]["elapsed_ms"] = max(0, round((datetime.fromisoformat(run["updated_at"].replace("Z", "+00:00"))
                    - datetime.fromisoformat(run["created_at"].replace("Z", "+00:00"))).total_seconds()*1000))
        usages = [r["usage"] for r in public_runs if r["usage"] is not None]
        cumulative = {key: sum(u.get(key, 0) for u in usages) for key in (
            "recorded_requests", "reported_requests", "not_attempted_requests", "unknown_or_pending_requests", "input_tokens", "output_tokens",
            "total_tokens", "cache_hit_tokens", "cache_miss_tokens", "unknown_cache_requests", "unknown_elapsed_requests", "elapsed_ms")}
        cumulative.update(native_runs=len(public_runs), known_cny=round(sum(r["cost_estimate"]["known_cny"] for r in public_runs), 6),
            unpriced_requests=sum(r["cost_estimate"]["unknown_or_pending_requests"] for r in public_runs),
            missing_audit_runs=sum(r["usage"] is None and r.get("model_calls_requested") != 0 for r in public_runs),
            partial_audit=any(u["partial_audit"] for u in usages),
            notice="本任务全部原生运行的已知用量；并行模型耗时为求和，不是墙钟时间。外部导入修订费用另见版本原因，缺失用量不计零。")
        if thread.get("status") == "error":
            projection["can_continue_remaining"] = can_restart_remaining_node(thread, state, runs[0] if runs else None,
                public_runs[0]["usage"] if public_runs else None)
        return {"thread_id": str(thread_id), "status": thread["status"], "title": thread.get("metadata", {}).get("title"),
            **projection, "execution": thread.get("metadata", {}).get("execution"), "can_abandon_question": bool(can_abandon_question(thread, state, runs[0] if runs else None)),
            "is_draft": bool(thread.get("metadata", {}).get("pending_question")) and not runs,
            "can_upload": service.attachment_store is not None and graph_for_thread(thread) == RESEARCH_GRAPH and thread.get("status") != "busy",
            "research_guidance": deepcopy(thread.get("metadata", {}).get("research_guidance", [])),
            "attachments": service.attachment_store.list(thread_id) if service.attachment_store else [],
            "runs": public_runs, "cumulative_usage": cumulative}

    @router.post("/research-sessions/{thread_id}/abandon-question")
    async def abandon_question(thread_id: UUID, request: Request):
        browser_write(request)
        thread = await service.owned_thread(thread_id)
        state = await service.sdk.threads.get_state(str(thread_id))
        last_runs = await service.sdk.runs.list(str(thread_id), limit=1)
        if not can_abandon_question(thread, state, last_runs[0] if last_runs else None):
            raise HTTPException(409, "仅已停止或失败且未交稿的追问可返回原报告；不跳过报告复核或重试运行")
        stopped = bool(last_runs and last_runs[0].get("status") == "interrupted")
        # Official checkpoint update changes only public request disposition.
        # as_node does NOT execute finish or any model; its only successor is
        # human_review. The failed run/checkpoint and report remain untouched.
        checkpoint = await service.sdk.threads.update_state(str(thread_id),
            abandoned_question_update(state["values"], "已停止这次追问并返回报告审阅。" if stopped else "已放弃这次失败的追问并返回报告审阅。"), as_node="finish")
        run = await service.sdk.runs.create(str(thread_id), graph_for_thread(thread), input=None, checkpoint=checkpoint["checkpoint"],
            config=await run_configuration(service, thread),
            stream_mode="custom", stream_subgraphs=True, stream_resumable=True, multitask_strategy="reject",
            metadata={"surface": SURFACE, "human_action": "return_stopped_question" if stopped else "abandon_failed_question", "model_calls_requested": 0})
        return {"run_id": run["run_id"], "status": run["status"], "model_retry_requested": False}

    @router.post("/research-sessions/{thread_id}/actions")
    async def action(thread_id: UUID, body: ReviewAction, request: Request):
        browser_write(request)
        if body.target:
            await service.owned_thread(thread_id)
            for previous in await service.all_runs(thread_id):
                meta = previous.get("metadata", {})
                if meta.get("revision_target", {}).get("request_id") == str(body.target.request_id):
                    if (meta["revision_target"] != body.target.model_dump(mode="json")
                            or meta.get("revision_feedback_digest") != report_digest(body.message)
                            or meta.get("execution") != (body.execution.model_dump() if body.execution else None)):
                        raise HTTPException(409, "相同请求标识不能提交不同修订内容")
                    return {"run_id": previous["run_id"], "status": previous["status"], "existing_request": True}
        state = await service.state(thread_id)
        if body.target:
            try:
                validate_revision_target(state.get("values", {}), body.target)
                baseline = await service.report_state(thread_id, body.target.base_checkpoint)
                validate_revision_target(baseline.get("values", {}), body.target)
            except ValueError as exc:
                raise HTTPException(409, str(exc)) from exc
        if not review_interrupts(state):
            raise HTTPException(409, "当前不在人工审阅点；运行中请先等待或停止，不会自动重发模型调用")
        if body.action == "accept" and not public_state(state)["can_accept"]:
            raise HTTPException(409, "仍有重大问题，不能标记人工审阅通过")
        if body.action != "accept" and not body.message.strip():
            raise HTTPException(422, "请填写问题或修订意见")
        thread = await service.owned_thread(thread_id)
        if body.execution:
            if graph_for_thread(thread) != RESEARCH_GRAPH:
                raise HTTPException(422, "旧报告审阅入口不支持切换研究模式")
            try:
                body.execution.validate_catalog((service.research_profile or {}).get("branch_topics", []))
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc
        run = await service.sdk.runs.create(str(thread_id), graph_for_thread(thread), command={"resume": body.model_dump(mode="json", exclude_none=True)},
            config=await run_configuration(service, thread, body.execution.model_dump() if body.execution else None),
            stream_mode="custom", stream_subgraphs=True, stream_resumable=True, multitask_strategy="reject",
            metadata={"surface": SURFACE, "human_action": body.action, "answer_mode": body.answer_mode, "request_message": body.message,
                "execution": body.execution.model_dump() if body.execution else thread.get("metadata", {}).get("execution"),
                **({"revision_target": body.target.model_dump(mode="json"), "revision_feedback_digest": report_digest(body.message)} if body.target else {})})
        return {"run_id": run["run_id"], "status": run["status"]}

    @router.post("/research-sessions/{thread_id}/runs/{run_id}/cancel")
    async def cancel(thread_id: UUID, run_id: UUID, request: Request):
        browser_write(request)
        await service.owned_thread(thread_id)
        await service.sdk.runs.cancel(str(thread_id), str(run_id), action="interrupt", wait=True)
        return {"cancel_requested": True, "notice": "保留已完成内容；未知供应商用量不记零。不会自动重发。"}

    @router.get("/research-sessions/{thread_id}/source")
    async def source(thread_id: UUID, source_id: str, offset: int = 0, checkpoint_id: UUID | None = None):
        state = await service.report_state(thread_id, checkpoint_id) if checkpoint_id else await service.state(thread_id)
        values = state.get("values", {})
        citations = [values.get("report", {}).get("citations", {})]
        citations += [values.get("synthesis", {}).get("citations", {}), values.get("research_synthesis", {}).get("citations", {})]
        citations += [m.get("citations", {}) for m in values.get("conversation", [])]
        available = {s["source_id"] for group in citations for c in group.values() for s in c["sources"]}
        from sec_agent.research_foundation.report_charts import chart_source_records
        chart_sources = {**chart_source_records(values.get("synthesis", {})),
                         **chart_source_records(values.get("report", {}))}
        if source_id not in available and source_id in chart_sources:
            if offset < 0:
                raise HTTPException(422, "来源阅读范围不合法")
            source = chart_sources[source_id]
            text = source["text"]
            return {**source, "text": text[offset:offset + 16000],
                    "next_offset": offset + 16000 if offset + 16000 < len(text) else None}
        if source_id not in available:
            raise HTTPException(404, "来源未与本会话已提交内容绑定")
        if not re.fullmatch(r"P\d{2}:S\d+", source_id):
            source = next(s for group in citations for c in group.values() for s in c["sources"] if s["source_id"] == source_id)
            if offset < 0:
                raise HTTPException(422, "来源阅读范围不合法")
            if "text" not in source:
                return deepcopy(source)
            text = source.get("text", "")
            return {**deepcopy(source), "text": text[offset:offset + 16000],
                "next_offset": offset + 16000 if offset + 16000 < len(text) else None}
        try:
            if "case_papers" in values:
                from sec_agent.agent_runtime.research_session import current_task_artifacts
                artifacts = current_task_artifacts(values)
            else:
                artifacts = service.artifacts
            return artifacts.with_revisions(values.get("revisions", {})).read_source(source_id, offset, 16000)
        except ValueError:
            raise HTTPException(422, "来源或阅读范围不合法") from None

    @router.get("/research-sessions/{thread_id}/report/export/{format}")
    async def export(thread_id: UUID, format: Literal["md", "pdf", "docx", "pptx"], request: Request, checkpoint_id: UUID | None = None):
        state = await service.report_state(thread_id, checkpoint_id) if checkpoint_id else await service.state(thread_id)
        report = state.get("values", {}).get("report")
        if not report:
            raise HTTPException(409, "报告尚未生成，不能导出空结果")
        from apps.workbench.backend.application.report_delivery import export_report
        data, mime = await run_in_threadpool(export_report, report, format,
            review_status="报告导出快照，请以工作台中当前的人工审阅状态为准", public_base_url=str(request.base_url))
        version = state.get("values", {}).get("report_version", "snapshot")
        return Response(data, media_type=mime, headers={"Content-Disposition": f'attachment; filename="finsight-research-v{version}.{format}"',
            "X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"})

    @router.get("/research-sessions/{thread_id}/report/charts/{index}.png")
    async def report_chart(thread_id: UUID, index: int, checkpoint_id: UUID | None = None):
        state = await service.report_state(thread_id, checkpoint_id) if checkpoint_id else await service.state(thread_id)
        charts = state.get("values", {}).get("report", {}).get("charts", [])
        if index < 0 or index >= len(charts):
            raise HTTPException(404, "报告中没有这个图表")
        from apps.workbench.backend.application.report_delivery import chart_png
        return Response(await run_in_threadpool(chart_png, charts[index]), media_type="image/png", headers={"Cache-Control": "no-store"})

    # This narrow path matches the official JS SDK's joinStream API. All other
    # generic native endpoints remain unexposed by this BFF.
    @router.get("/agent/threads/{thread_id}/runs/{run_id}/stream")
    async def stream(thread_id: UUID, run_id: UUID, request: Request):
        await service.owned_thread(thread_id)
        # These runs are created with stream_resumable=True. Replay retained
        # events on initial attach/refresh; never restart the model run.
        last_id = request.headers.get("last-event-id") or "0-0"
        if last_id and not re.fullmatch(r"[0-9]+-[0-9]+", last_id):
            raise HTTPException(422, "无效的事件续读位置")
        async def events():
            async for part in service.sdk.runs.join_stream(str(thread_id), str(run_id), last_event_id=last_id):
                if part.event.split("|", 1)[0] != "custom":
                    continue
                data = public_event(part.data)
                if data is None:
                    continue
                prefix = f"id: {part.id}\n" if part.id and re.fullmatch(r"[0-9]+-[0-9]+", part.id) else ""
                yield prefix + "event: custom\ndata: " + json.dumps(data, ensure_ascii=False) + "\n\n"
        return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})

    router.include_router(build_studio_router(service, browser_write))
    return router
