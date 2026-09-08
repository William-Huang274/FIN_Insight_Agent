"""Local general-conversation BFF. Native server owns runs and checkpoints."""
from typing import Literal
from uuid import UUID
from urllib.parse import unquote
import json
import re

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field

from .report_sessions import public_run_usage, public_cost_estimate, public_event
from ...application.context_usage import request_context_usage
from sec_agent.agent_runtime.conversation_handoff import public_history, observed_sources

SURFACE = "finsight_general_conversation"
GRAPH = "conversation_session"


class ConversationMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    message: str = Field(min_length=1, max_length=16000)
    model: Literal["deepseek-v4-flash", "deepseek-v4-pro"] = "deepseek-v4-flash"
    permission_mode: Literal["request_standard", "approve_for_me", "full_access"] = "request_standard"


class ConversationDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(default="新对话", min_length=1, max_length=80)


class ConversationHandoff(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    checkpoint_id: UUID
    note: str = Field(min_length=1, max_length=2000)


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
        if not service.research_profile:
            raise HTTPException(503, "本部署未启用模型运行")
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
    @router.post("/drafts")
    async def draft(body: ConversationDraft, request: Request):
        browser_write(request)
        thread = await service.sdk.threads.create(metadata={"surface": SURFACE, "graph": GRAPH, "title": body.title})
        return {"thread_id": thread["thread_id"], "model_calls": 0}
    @router.post("/{thread_id}/attachments")
    async def upload(thread_id: UUID, request: Request):
        browser_write(request)
        thread = await owned(thread_id)
        if thread.get("status") == "busy":
            raise HTTPException(409, "请等待本轮完成后再补充资料")
        if service.attachment_store is None:
            raise HTTPException(503, "本部署未配置对话资料存储")
        from sec_agent.research_foundation.task_attachments import MAX_BYTES
        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > MAX_BYTES:
                raise HTTPException(413, "单文件上限20MiB")
            body.extend(chunk)
        try:
            return await run_in_threadpool(service.attachment_store.add, thread_id,
                unquote(request.headers.get("x-filename", "")), bytes(body))
        except (ValueError, UnicodeError) as exc:
            raise HTTPException(422, str(exc)) from None
        except Exception:
            raise HTTPException(422, "文件解析失败；未启动模型，请检查格式或文件内容") from None
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
    @router.get("/{thread_id}/handoff-preview")
    async def handoff_preview(thread_id: UUID):
        thread = await owned(thread_id)
        if thread.get("status") == "busy":
            raise HTTPException(409, "本轮运行中，请先等待完成或停止再交接")
        state = await service.sdk.threads.get_state(str(thread_id))
        if not state.get("checkpoint", {}).get("checkpoint_id"):
            raise HTTPException(409, "当前没有可交接的已保存对话")
        messages = public_history(state)
        return {"source_thread": str(thread_id), "title": thread.get("metadata", {}).get("title"),
            "checkpoint_id": state["checkpoint"]["checkpoint_id"], "message_count": len(messages),
            "evidence_count": len(observed_sources(state)), "status": thread.get("status"),
            "latest_user_request": next((m["content"][:2000] for m in reversed(messages) if m["role"] == "user"), ""),
            "notice": "新窗口按需读取这个固定版本的公开对话和原始工具凭证；不复制全部历史，不把摘要或旧回答当已核实事实。未读入的上传文件仍在旧窗口。"}
    @router.post("/{thread_id}/handoff")
    async def handoff(thread_id: UUID, body: ConversationHandoff, request: Request):
        browser_write(request)
        source = await owned(thread_id)
        if source.get("status") == "busy":
            raise HTTPException(409, "请先等待本轮完成或停止")
        state = await service.sdk.threads.get_state(str(thread_id))
        if state.get("checkpoint", {}).get("checkpoint_id") != str(body.checkpoint_id):
            raise HTTPException(409, "对话已变化，请重新查看交接内容")
        if any(t.get("interrupts") for t in state.get("tasks", [])):
            raise HTTPException(409, "请先处理待批准的操作；新窗口不会继承待执行授权")
        metadata = source.get("metadata", {})
        target = await service.sdk.threads.create(metadata={"surface": SURFACE, "graph": GRAPH,
            "owner_id": metadata.get("owner_id", "local-pilot"),
            "title": ("接续 · " + (metadata.get("title") or "对话"))[:80],
            "handoff": {"source_thread": str(thread_id), "checkpoint_id": str(body.checkpoint_id), "note": body.note}})
        return {"thread_id": target["thread_id"], "model_calls": 0}
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
            "attachments": service.attachment_store.list(thread_id) if getattr(service, "attachment_store", None) else [],
            "handoff": thread.get("metadata", {}).get("handoff"),
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
