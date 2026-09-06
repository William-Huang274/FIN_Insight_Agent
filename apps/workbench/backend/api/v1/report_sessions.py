"""Thin local Workbench BFF for the native Dell review graph.

No generic proxy, application queue, checkpoint store or private-message route.
The native server owns sessions/runs/concurrency. Browser inputs cannot select
graphs, credentials, paths, model budgets or arbitrary checkpoint updates.
"""
from __future__ import annotations

import json
import re
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

SURFACE = "dell_report_workbench"
GRAPH = "dell_report_session"
RESEARCH_GRAPH = "research_session"
PUBLIC_EVENT_FIELDS = frozenset({"kind", "actor", "event", "status", "call_id", "tool", "recorded_at",
    "model", "thinking", "reasoning_effort", "elapsed_ms", "input_tokens", "output_tokens", "total_tokens",
    "cache_hit_tokens", "cache_miss_tokens", "reasoning_tokens", "usage_reported", "error_type", "http_status_code",
    "max_output_tokens", "valid_tool_call_count", "invalid_tool_call_count", "success_scope", "run_id",
    "task_id", "objective", "responsible_author_count", "correction_round", "paper_id"})


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
    ids = {e["call_id"] for e in events if e.get("call_id")}
    outcomes = {e["call_id"]: e for e in events if e.get("call_id") and e.get("event") == "outcome"}
    totals = {key: sum(e[key] for e in outcomes.values() if isinstance(e.get(key), int))
              for key in ("input_tokens", "output_tokens", "total_tokens")}
    return events, {"recorded_requests": len(ids), "reported_requests": sum(isinstance(e.get("total_tokens"), int) for e in outcomes.values()),
        "unknown_or_pending_requests": sum(not isinstance(outcomes.get(i, {}).get("total_tokens"), int) for i in ids),
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


def public_cost_estimate(events):
    from scripts.qualification.dell_q1_specialist_paid_shadow.audit_token_cost import OFF_PEAK, PRICE_AS_OF, cost_parts, peak_multiplier
    starts = {e["call_id"]: e for e in events if e.get("call_id") and e.get("event") == "started"}
    outcomes = {e["call_id"]: e for e in events if e.get("call_id") and e.get("event") == "outcome"}
    amount, priced = 0.0, 0
    for call_id, outcome in outcomes.items():
        start = starts.get(call_id, {})
        model = start.get("model") or outcome.get("model")
        counts = [outcome.get(key) for key in ("cache_hit_tokens", "cache_miss_tokens", "output_tokens")]
        timestamp = start.get("recorded_at") or outcome.get("recorded_at")
        if model in OFF_PEAK and timestamp and all(type(n) is int and n >= 0 for n in counts):
            amount += sum(cost_parts(model, *counts, peak_multiplier(timestamp)).values())
            priced += 1
    return {"known_cny": round(amount, 6), "priced_requests": priced, "unknown_or_pending_requests": len(set(starts) | set(outcomes)) - priced,
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
    title: str = Field(default="Dell AI 基础设施 · 全案审阅", min_length=1, max_length=120)
    mode: Literal["review", "research"] = "review"
    question: str | None = Field(default=None, min_length=10, max_length=16000)
    defer_start: bool = False


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
            "title": t.get("metadata", {}).get("title", "Dell 研究会话")} for t in threads]

    @router.get("/research-session-config")
    async def configuration():
        profile = getattr(service, "research_profile", None)
        return {"fresh_research_enabled": profile is not None, **(deepcopy(profile) if profile else {})}

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
        if body.defer_start and body.mode != "research":
            raise HTTPException(422, "只有新研究支持先上传资料")
        metadata = {"surface": SURFACE, "title": body.title, "graph": graph, "mode": body.mode}
        if body.defer_start:
            metadata["pending_question"] = payload["question"]
        thread = await service.sdk.threads.create(metadata=metadata)
        if body.defer_start:
            return {"thread_id": thread["thread_id"], "run_id": None, "status": "draft"}
        run = await service.sdk.runs.create(thread["thread_id"], graph, input=payload, stream_mode="custom",
            stream_subgraphs=True, stream_resumable=True, multitask_strategy="reject", metadata={"surface": SURFACE, "human_action": body.mode})
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
            input=ResearchRequest(question=question).model_dump(mode="json"), stream_mode="custom", stream_subgraphs=True,
            stream_resumable=True, multitask_strategy="reject", metadata={"surface": SURFACE, "human_action": "research"})
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
        runs = await service.sdk.runs.list(str(thread_id), limit=10)
        projection = public_state(state)
        if not runs and thread.get("metadata", {}).get("pending_question"):
            projection.update(question=thread["metadata"]["pending_question"], phase="draft", case_profile="dell_growth_quality")
        public_runs = []
        for run in runs:
            events, usage = public_run_usage(service.audit_root, thread_id, run["run_id"])
            projection["model_events"].extend(events)
            public_runs.append({**{k: run.get(k) for k in ("run_id", "status", "created_at")},
                "human_action": run.get("metadata", {}).get("human_action"),
                "answer_mode": run.get("metadata", {}).get("answer_mode"), "usage": usage})
            public_runs[-1]["cost_estimate"] = public_cost_estimate(events)
        if thread.get("status") == "error":
            projection["can_continue_remaining"] = can_restart_remaining_node(thread, state, runs[0] if runs else None,
                public_runs[0]["usage"] if public_runs else None)
        return {"thread_id": str(thread_id), "status": thread["status"], "title": thread.get("metadata", {}).get("title"),
            **projection, "can_abandon_question": bool(can_abandon_question(thread, state, runs[0] if runs else None)),
            "is_draft": bool(thread.get("metadata", {}).get("pending_question")) and not runs,
            "research_guidance": deepcopy(thread.get("metadata", {}).get("research_guidance", [])),
            "attachments": service.attachment_store.list(thread_id) if service.attachment_store else [],
            "runs": public_runs}

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
            stream_mode="custom", stream_subgraphs=True, stream_resumable=True, multitask_strategy="reject",
            metadata={"surface": SURFACE, "human_action": "return_stopped_question" if stopped else "abandon_failed_question", "model_calls_requested": 0})
        return {"run_id": run["run_id"], "status": run["status"], "model_retry_requested": False}

    @router.post("/research-sessions/{thread_id}/actions")
    async def action(thread_id: UUID, body: ReviewAction, request: Request):
        browser_write(request)
        state = await service.state(thread_id)
        if not review_interrupts(state):
            raise HTTPException(409, "当前不在人工审阅点；运行中请先等待或停止，不会自动重发模型调用")
        if body.action == "accept" and not public_state(state)["can_accept"]:
            raise HTTPException(409, "仍有重大问题，不能标记人工审阅通过")
        if body.action != "accept" and not body.message.strip():
            raise HTTPException(422, "请填写问题或修订意见")
        thread = await service.owned_thread(thread_id)
        run = await service.sdk.runs.create(str(thread_id), graph_for_thread(thread), command={"resume": body.model_dump()},
            stream_mode="custom", stream_subgraphs=True, stream_resumable=True, multitask_strategy="reject",
            metadata={"surface": SURFACE, "human_action": body.action, "answer_mode": body.answer_mode})
        return {"run_id": run["run_id"], "status": run["status"]}

    @router.post("/research-sessions/{thread_id}/runs/{run_id}/cancel")
    async def cancel(thread_id: UUID, run_id: UUID, request: Request):
        browser_write(request)
        await service.owned_thread(thread_id)
        await service.sdk.runs.cancel(str(thread_id), str(run_id), action="interrupt", wait=True)
        return {"cancel_requested": True, "notice": "保留已完成内容；未知供应商用量不记零。不会自动重发。"}

    @router.get("/research-sessions/{thread_id}/source")
    async def source(thread_id: UUID, source_id: str, offset: int = 0):
        state = await service.state(thread_id)
        values = state.get("values", {})
        citations = [values.get("report", {}).get("citations", {})]
        citations += [values.get("synthesis", {}).get("citations", {}), values.get("research_synthesis", {}).get("citations", {})]
        citations += [m.get("citations", {}) for m in values.get("conversation", [])]
        available = {s["source_id"] for group in citations for c in group.values() for s in c["sources"]}
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
    async def export(thread_id: UUID, format: Literal["md", "pdf", "docx", "pptx"]):
        state = await service.state(thread_id)
        report = state.get("values", {}).get("report")
        if not report:
            raise HTTPException(409, "报告尚未生成，不能导出空结果")
        from apps.workbench.backend.application.report_delivery import export_report
        data, mime = await run_in_threadpool(export_report, report, format,
            review_status="报告导出快照，请以工作台中当前的人工审阅状态为准")
        return Response(data, media_type=mime, headers={"Content-Disposition": f'attachment; filename="finsight-research.{format}"',
            "X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"})

    @router.get("/research-sessions/{thread_id}/report/charts/{index}.png")
    async def report_chart(thread_id: UUID, index: int):
        state = await service.state(thread_id)
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

    return router
