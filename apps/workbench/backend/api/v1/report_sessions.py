"""Thin local Workbench BFF for the native Dell review graph.

No generic proxy, application queue, checkpoint store or private-message route.
The native server owns sessions/runs/concurrency. Browser inputs cannot select
graphs, credentials, paths, model budgets or arbitrary checkpoint updates.
"""
from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from langgraph_sdk.client import LangGraphClient
from pydantic import BaseModel, ConfigDict, Field

from sec_agent.agent_runtime.dell_report_session import ReviewAction

SURFACE = "dell_report_workbench"
GRAPH = "dell_report_session"
PUBLIC_EVENT_FIELDS = frozenset({"kind", "actor", "event", "status", "call_id", "tool", "recorded_at",
    "model", "thinking", "reasoning_effort", "elapsed_ms", "input_tokens", "output_tokens", "total_tokens",
    "cache_hit_tokens", "cache_miss_tokens", "reasoning_tokens", "usage_reported", "error_type", "http_status_code",
    "max_output_tokens", "valid_tool_call_count", "invalid_tool_call_count", "success_scope"})


def public_event(value):
    if not isinstance(value, dict):
        return None
    result = {k: v for k, v in value.items() if k in PUBLIC_EVENT_FIELDS and isinstance(v, (str, int, float, bool, type(None)))}
    return result if result.get("kind") in {"model", "tool", "stage"} else None


def review_interrupts(state):
    items = list(state.get("interrupts") or [])
    for task in state.get("tasks", []):
        items.extend(task.get("interrupts") or [])
    return [i for i in items if isinstance(i, dict) and isinstance(i.get("value"), dict)
        and i["value"].get("kind") == "dell_report_review"]


def public_state(state):
    values = state.get("values", {})
    result = {k: deepcopy(values[k]) for k in ("report", "report_review", "report_version", "phase", "conversation") if k in values}
    result["model_events"] = [p for e in values.get("model_events", []) if (p := public_event({"kind": "model", **e}))]
    result["can_respond"] = bool(review_interrupts(state))
    result["can_accept"] = result["can_respond"] and result.get("phase") == "ready_for_human_review"
    # No tasks, raw native messages, private checkpoints or source filesystem paths.
    return result


class NewSession(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(default="Dell AI 基础设施 · 全案审阅", min_length=1, max_length=120)


class ReportSessionService:
    def __init__(self, api_url, artifacts, *, sdk=None):
        parsed = urlsplit(api_url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "langgraph-api"} or parsed.username or parsed.query or parsed.fragment:
            raise ValueError("report_session_server_must_be_local")
        self.http = httpx.AsyncClient(base_url=api_url, trust_env=False, transport=httpx.AsyncHTTPTransport(retries=0),
            timeout=httpx.Timeout(300, connect=5))
        self.sdk = sdk or LangGraphClient(self.http)
        self.artifacts = artifacts

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

    @router.post("/research-sessions")
    async def create(body: NewSession, request: Request):
        browser_write(request)
        thread = await service.sdk.threads.create(metadata={"surface": SURFACE, "title": body.title})
        run = await service.sdk.runs.create(thread["thread_id"], GRAPH, input={"open": True}, stream_mode="custom",
            stream_subgraphs=True, stream_resumable=True, multitask_strategy="reject", metadata={"surface": SURFACE})
        return {"thread_id": thread["thread_id"], "run_id": run["run_id"], "status": run["status"]}

    @router.get("/research-sessions/{thread_id}")
    async def snapshot(thread_id: UUID):
        thread = await service.owned_thread(thread_id)
        state = await service.sdk.threads.get_state(str(thread_id))
        runs = await service.sdk.runs.list(str(thread_id), limit=10)
        return {"thread_id": str(thread_id), "status": thread["status"], "title": thread.get("metadata", {}).get("title"),
            **public_state(state), "runs": [{k: r.get(k) for k in ("run_id", "status", "created_at")} for r in runs]}

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
        run = await service.sdk.runs.create(str(thread_id), GRAPH, command={"resume": body.model_dump()},
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
        citations += [m.get("citations", {}) for m in values.get("conversation", [])]
        available = {s["source_id"] for group in citations for c in group.values() for s in c["sources"]}
        if source_id not in available:
            raise HTTPException(404, "来源未与本会话已提交内容绑定")
        try:
            return service.artifacts.with_revisions(values.get("revisions", {})).read_source(source_id, offset, 16000)
        except ValueError:
            raise HTTPException(422, "来源或阅读范围不合法") from None

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
