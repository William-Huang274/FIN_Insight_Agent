"""Local general-conversation BFF. Native server owns runs and checkpoints."""
from typing import Literal
from uuid import UUID
import json
import re

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from .report_sessions import public_run_usage, public_cost_estimate, public_event
from ...application.context_usage import request_context_usage

SURFACE = "finsight_general_conversation"
GRAPH = "conversation_session"


class ConversationMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    message: str = Field(min_length=1, max_length=16000)
    model: Literal["deepseek-v4-flash", "deepseek-v4-pro"] = "deepseek-v4-flash"
    permission_mode: Literal["request_standard", "approve_for_me", "full_access"] = "request_standard"


def public_messages(state):
    result = []
    for message in state.get("values", {}).get("messages", []):
        role = {"human": "user", "ai": "assistant", "user": "user", "assistant": "assistant"}.get(message.get("type") or message.get("role"))
        if not role:
            continue
        content = message.get("content", "")
        if isinstance(content, list):
            content = "\n".join(p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text")
        if isinstance(content, str) and content:
            result.append({"id": message.get("id"), "role": role, "content": content})
    return result


def public_message_delta(data):
    """Native messages-tuple projection: assistant text only, never reasoning/tools."""
    if not isinstance(data, list) or len(data) != 2 or not isinstance(data[0], dict):
        return None
    chunk = data[0]
    if chunk.get("type") not in {"AIMessageChunk", "ai"} or not chunk.get("id"):
        return None
    content = chunk.get("content", "")
    if isinstance(content, list):
        content = "".join(p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text")
    return {"id": chunk["id"], "text": content} if isinstance(content, str) and content else None


def build_conversations_router(service):
    router = APIRouter(prefix="/conversations")
    def browser_write(request):
        if request.headers.get("x-workbench-request") != "1":
            raise HTTPException(403, "缺少本地工作台请求标识")
    async def owned(thread_id):
        thread = await service.sdk.threads.get(str(thread_id))
        metadata = thread.get("metadata", {})
        if metadata.get("surface") != SURFACE or metadata.get("graph") != GRAPH:
            raise HTTPException(404, "对话不存在")
        return thread
    async def invoke(thread_id, body):
        return await service.sdk.runs.create(str(thread_id), GRAPH,
            input={"messages": [{"role": "user", "content": body.message}]},
            config={"configurable": {"conversation_model": body.model, "permission_mode": body.permission_mode}},
            stream_mode=["custom", "messages-tuple"], stream_resumable=True, multitask_strategy="reject",
            metadata={"surface": SURFACE, "request_message": body.message, "model": body.model, "permission_mode": body.permission_mode})
    @router.get("")
    async def list_conversations():
        threads = await service.sdk.threads.search(metadata={"surface": SURFACE}, limit=100)
        return [{"thread_id": t["thread_id"], "title": t.get("metadata", {}).get("title"), "status": t.get("status")} for t in threads]
    @router.post("")
    async def create(body: ConversationMessage, request: Request):
        browser_write(request)
        if not service.research_profile:
            raise HTTPException(503, "本部署未启用模型运行")
        # Validate the actual deployed graph before creating a paid-capable thread.
        await service.sdk.assistants.get_graph(GRAPH)
        thread = await service.sdk.threads.create(metadata={"surface": SURFACE, "graph": GRAPH, "title": body.message[:80]})
        run = await invoke(thread["thread_id"], body)
        return {"thread_id": thread["thread_id"], "run_id": run["run_id"]}
    @router.post("/{thread_id}/messages")
    async def message(thread_id: UUID, body: ConversationMessage, request: Request):
        browser_write(request)
        thread = await owned(thread_id)
        if thread.get("status") == "busy":
            raise HTTPException(409, "当前轮次仍在运行，请等待或停止后再发送")
        state = await service.sdk.threads.get_state(str(thread_id))
        if any(t.get("interrupts") for t in state.get("tasks", [])):
            raise HTTPException(409, "请先处理当前等待批准的操作")
        run = await invoke(thread_id, body)
        return {"thread_id": str(thread_id), "run_id": run["run_id"]}
    @router.get("/{thread_id}")
    async def get_conversation(thread_id: UUID):
        thread = await owned(thread_id)
        state = await service.sdk.threads.get_state(str(thread_id))
        runs = await service.sdk.runs.list(str(thread_id), limit=100)
        events, public_runs = [], []
        for run in runs:
            activity, usage = public_run_usage(service.audit_root, thread_id, run["run_id"])
            events.extend(activity)
            public_runs.append({"run_id": run["run_id"], "status": run["status"], "created_at": run.get("created_at"),
                "usage": usage, "context_usage": request_context_usage(activity), "cost_estimate": public_cost_estimate(activity)})
        return {"thread_id": str(thread_id), "title": thread.get("metadata", {}).get("title"), "status": thread.get("status"),
            "messages": public_messages(state), "events": events, "runs": public_runs,
            "permissions_notice": "当前仅提供本对话资料/已配置财务快照的读取和计算；三档模式均不授权修改用户原文件。OS sandbox和可写工具尚未开放。"}
    @router.post("/{thread_id}/stop")
    async def stop(thread_id: UUID, request: Request):
        browser_write(request)
        await owned(thread_id)
        runs = await service.sdk.runs.list(str(thread_id), limit=100)
        for run in runs:
            if run["status"] in {"pending", "running"}:
                await service.sdk.runs.cancel(str(thread_id), run["run_id"], action="interrupt")
        return {"status": "interrupt_requested"}
    @router.get("/{thread_id}/runs/{run_id}/stream")
    async def stream(thread_id: UUID, run_id: UUID, request: Request):
        await owned(thread_id)
        last_id = request.headers.get("last-event-id") or "0-0"
        if not re.fullmatch(r"[0-9]+-[0-9]+", last_id):
            raise HTTPException(422, "无效的续读位置")
        async def events():
            async for part in service.sdk.runs.join_stream(str(thread_id), str(run_id), last_event_id=last_id):
                if part.event.split("|", 1)[0] in {"messages", "messages-tuple"}:
                    delta = public_message_delta(part.data)
                    if delta:
                        prefix = f"id: {part.id}\n" if part.id and re.fullmatch(r"[0-9]+-[0-9]+", part.id) else ""
                        yield prefix + "event: assistant_delta\ndata: " + json.dumps(delta, ensure_ascii=False) + "\n\n"
                    continue
                if part.event.split("|", 1)[0] != "custom":
                    continue
                event = public_event(part.data)
                if event is not None:
                    prefix = f"id: {part.id}\n" if part.id and re.fullmatch(r"[0-9]+-[0-9]+", part.id) else ""
                    yield prefix + "event: custom\ndata: " + json.dumps(event, ensure_ascii=False) + "\n\n"
        return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-store"})
    return router
