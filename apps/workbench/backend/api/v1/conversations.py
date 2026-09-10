"""Local general-conversation BFF. Native server owns runs and checkpoints."""
from typing import Literal
from uuid import UUID
from urllib.parse import unquote
import json
import re

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse, Response
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field

from .report_sessions import public_run_usage, public_cost_estimate, public_event
from ...application.context_usage import request_context_usage
from ...authentication import current_owner
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


class ConversationApproval(BaseModel):
    model_config = ConfigDict(extra="forbid")
    checkpoint_id: UUID
    interrupt_id: str = Field(min_length=1, max_length=100)
    decisions: list[Literal["approve", "reject"]] = Field(min_length=1, max_length=12)


def pending_approvals(state):
    return [{"id": item["id"], "value": item["value"]}
        for task in state.get("tasks", []) for item in task.get("interrupts", [])
        if isinstance(item.get("value"), dict) and item["value"].get("action_requests")]


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
            result.append({"id": message.get("id"), "role": role, "content": content,
                           "final_answer": role == "assistant" and not message.get("tool_calls")})
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
    async def owned(thread_id, request):
        thread = await service.sdk.threads.get(str(thread_id))
        metadata = thread.get("metadata", {})
        if (metadata.get("surface") != SURFACE or metadata.get("graph") != GRAPH
                or metadata.get("owner_id", "local-pilot") != current_owner(request)):
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
    async def list_conversations(request: Request):
        owner = current_owner(request)
        filters = {"surface": SURFACE, **({"owner_id": owner} if owner != "local-pilot" else {})}
        threads = await service.sdk.threads.search(metadata=filters, limit=100)
        threads = [t for t in threads if t.get("metadata", {}).get("owner_id", "local-pilot") == owner]
        return [{"thread_id": t["thread_id"], "title": t.get("metadata", {}).get("title"), "status": t.get("status")} for t in threads]
    @router.post("")
    async def create(body: ConversationMessage, request: Request):
        browser_write(request)
        if not service.research_profile:
            raise HTTPException(503, "本部署未启用模型运行")
        # Validate the actual deployed graph before creating a paid-capable thread.
        await service.sdk.assistants.get_graph(GRAPH)
        thread = await service.sdk.threads.create(metadata={"surface": SURFACE, "graph": GRAPH, "title": body.message[:80], "owner_id": current_owner(request)})
        run = await invoke(thread["thread_id"], body)
        return {"thread_id": thread["thread_id"], "run_id": run["run_id"]}
    @router.post("/drafts")
    async def draft(body: ConversationDraft, request: Request):
        browser_write(request)
        thread = await service.sdk.threads.create(metadata={"surface": SURFACE, "graph": GRAPH, "title": body.title, "owner_id": current_owner(request)})
        return {"thread_id": thread["thread_id"], "model_calls": 0}
    @router.post("/{thread_id}/attachments")
    async def upload(thread_id: UUID, request: Request):
        browser_write(request)
        thread = await owned(thread_id, request)
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
        thread = await owned(thread_id, request)
        if thread.get("status") == "busy":
            raise HTTPException(409, "当前轮次仍在运行，请等待或停止后再发送")
        state = await service.sdk.threads.get_state(str(thread_id))
        if any(t.get("interrupts") for t in state.get("tasks", [])):
            raise HTTPException(409, "请先处理当前等待批准的操作")
        run = await invoke(thread_id, body)
        return {"thread_id": str(thread_id), "run_id": run["run_id"]}
    @router.post("/{thread_id}/approvals")
    async def approve(thread_id: UUID, body: ConversationApproval, request: Request):
        browser_write(request)
        thread = await owned(thread_id, request)
        if thread.get("status") == "busy":
            raise HTTPException(409, "本轮已在运行，请刷新操作状态")
        state = await service.sdk.threads.get_state(str(thread_id))
        pending = next((item for item in pending_approvals(state) if item["id"] == body.interrupt_id), None)
        if (state.get("checkpoint") or {}).get("checkpoint_id") != str(body.checkpoint_id) or not pending:
            raise HTTPException(409, "待批准操作已变化或已处理，请刷新后核对")
        if len(body.decisions) != len(pending["value"]["action_requests"]):
            raise HTTPException(422, "每个待执行动作都需要明确的决定")
        sources = observed_sources(state)
        for action, decision in zip(pending["value"]["action_requests"], body.decisions):
            if decision == "approve" and action.get("name") == "save_sources_to_knowledge":
                ids = action.get("args", {}).get("source_ids")
                if not isinstance(ids, list) or not ids or any(not isinstance(key, str) or key not in sources for key in ids):
                    raise HTTPException(422, "待保存来源不在本对话已读凭证中；请拒绝后让模型修正，不会猜测编号")
        runs = await service.sdk.runs.list(str(thread_id), limit=1)
        # Agent Server can complete a run successfully at an intentional graph
        # interrupt. The current thread/checkpoint/action is the approval gate.
        if thread.get("status") != "interrupted" or not runs or runs[0]["status"] not in {"interrupted", "success"}:
            raise HTTPException(409, "原运行当前不在等待批准状态")
        previous = runs[0].get("metadata", {})
        selected = ConversationMessage(message="批准恢复", model=previous["model"], permission_mode=previous["permission_mode"])
        run = await service.sdk.runs.create(str(thread_id), GRAPH,
            command={"resume": {body.interrupt_id: {"decisions": [{"type": d} for d in body.decisions]}}},
            config={"configurable": {"conversation_model": selected.model, "permission_mode": selected.permission_mode}},
            stream_mode=["custom", "messages-tuple"], stream_resumable=True, multitask_strategy="reject",
            metadata={"surface": SURFACE, "model": selected.model, "permission_mode": selected.permission_mode,
                "approval": {"checkpoint_id": str(body.checkpoint_id), "interrupt_id": body.interrupt_id, "decisions": body.decisions}})
        return {"thread_id": str(thread_id), "run_id": run["run_id"]}
    @router.get("/{thread_id}/handoff-preview")
    async def handoff_preview(thread_id: UUID, request: Request):
        thread = await owned(thread_id, request)
        if thread.get("status") == "busy":
            raise HTTPException(409, "本轮运行中，请先等待完成或停止再交接")
        state = await service.sdk.threads.get_state(str(thread_id))
        if not (state.get("checkpoint") or {}).get("checkpoint_id"):
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
        source = await owned(thread_id, request)
        if source.get("status") == "busy":
            raise HTTPException(409, "请先等待本轮完成或停止")
        state = await service.sdk.threads.get_state(str(thread_id))
        if (state.get("checkpoint") or {}).get("checkpoint_id") != str(body.checkpoint_id):
            raise HTTPException(409, "对话已变化，请重新查看交接内容")
        if any(t.get("interrupts") for t in state.get("tasks", [])):
            raise HTTPException(409, "请先处理待批准的操作；新窗口不会继承待执行授权")
        metadata = source.get("metadata", {})
        from sec_agent.agent_runtime.working_memory_tools import memory_enabled, memory_for
        notes, memory_notice = [], None
        if memory_enabled():
            import sqlite3
            try:
                notes = await run_in_threadpool(lambda: memory_for({}, "handoff", owner=current_owner(request),
                    workspace=str(thread_id)).manifest())
            except (OSError, sqlite3.Error):
                memory_notice = "工作底稿索引暂不可读取，未纳入本次交接；原底稿未删除。"
        target = await service.sdk.threads.create(metadata={"surface": SURFACE, "graph": GRAPH,
            "owner_id": metadata.get("owner_id", "local-pilot"),
            "title": ("接续 · " + (metadata.get("title") or "对话"))[:80],
            "handoff": {"source_thread": str(thread_id), "checkpoint_id": str(body.checkpoint_id), "note": body.note,
                        **({"working_notes": notes} if notes else {}),
                        **({"working_memory_notice": memory_notice} if memory_notice else {})}})
        return {"thread_id": target["thread_id"], "model_calls": 0,
                **({"working_notes_count": len(notes)} if notes else {}),
                **({"notice": memory_notice} if memory_notice else {})}
    @router.get("/{thread_id}")
    async def get_conversation(thread_id: UUID, request: Request):
        thread = await owned(thread_id, request)
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
            "checkpoint_id": (state.get("checkpoint") or {}).get("checkpoint_id"), "approvals": pending_approvals(state),
            "approval_sources": {key: {"title": item.get("title") or " / ".join(str(item[k]) for k in ("ticker","metric_id","period_end","unit") if item.get(k)) or "已读来源",
                "preview": str(item.get("passage") or item.get("value_decimal") or item.get("expression") or "")[:1200],
                "source_url": item.get("source_url") or next(iter(item.get("citation_urls") or []), None),
                "source_role": item.get("source_role") or item.get("result_state"),
                "unit": item.get("unit"), "period_start": item.get("period_start"), "period_end": item.get("period_end"),
                "accession_numbers": item.get("accession_numbers", [])}
                for key,item in observed_sources(state).items() if any(key in action.get("args",{}).get("source_ids",[])
                    for pending in pending_approvals(state) for action in pending["value"]["action_requests"]
                    if action.get("name")=="save_sources_to_knowledge" and isinstance(action.get("args",{}).get("source_ids"),list))},
            "attachments": service.attachment_store.list(thread_id) if getattr(service, "attachment_store", None) else [],
            "handoff": thread.get("metadata", {}).get("handoff"),
            "permissions_notice": "资料和财务快照只读。部署启用隔离Python时，请求标准逐次批准；代我批准/完全访问仅在空白临时容器内执行。各档均未开放用户原文件、宿主终端或服务器写入。"}
    @router.post("/{thread_id}/stop")
    async def stop(thread_id: UUID, request: Request):
        browser_write(request)
        await owned(thread_id, request)
        runs = await service.sdk.runs.list(str(thread_id), limit=100)
        for run in runs:
            if run["status"] in {"pending", "running"}:
                await service.sdk.runs.cancel(str(thread_id), run["run_id"], action="interrupt")
        return {"status": "interrupt_requested"}
    @router.get("/{thread_id}/messages/{message_id}/export/{format}")
    async def export_answer(thread_id: UUID, message_id: str, format: Literal["md", "pdf", "docx"], checkpoint_id: UUID, request: Request):
        thread = await owned(thread_id, request)
        state = await service.sdk.threads.get_state(str(thread_id), checkpoint={"checkpoint_id": str(checkpoint_id), "checkpoint_ns": ""})
        messages = state.get("values", {}).get("messages", [])
        index = next((i for i, m in enumerate(messages) if m.get("id") == message_id), None)
        if index is None:
            raise HTTPException(404, "这个保存版本中没有该回答")
        chosen = public_messages({"values": {"messages": [messages[index]]}})
        if not chosen or not chosen[0]["final_answer"]:
            raise HTTPException(409, "请选择一条已保存的完整回答，不能导出工具活动或私有推理")
        # Only sources read before this answer enter its source directory. This
        # directory is not an inferred sentence-to-source citation mapping.
        sources = observed_sources({"values": {"messages": messages[:index]}})
        citations = {key: {"sources": [{**item, "source_id": key,
            "title": item.get("title") or " / ".join(str(item[k]) for k in ("ticker", "metric_id", "period_end", "unit") if item.get(k)) or "已读取凭证",
            **({"calculation": item} if key.startswith("CALC::") else {})}]} for key, item in sources.items()}
        # Thread titles may be clipped prompts, not document titles. Preserve the
        # saved answer verbatim and use a compact neutral cover heading.
        from sec_agent.agent_runtime.conversation_handoff import answer_charts
        report = {"title": "FinSight · 已保存回答",
            "narrative_markdown": chosen[0]["content"], "citations": citations, "charts": answer_charts(messages[:index])}
        from ...application.report_delivery import export_report
        data, mime = await run_in_threadpool(export_report, report, format,
            review_status="已保存回答的固定版本；来源目录列出本回答之前已读凭证，不代表逐句引用或金融结论已核验。")
        return Response(data, media_type=mime, headers={"Content-Disposition": f'attachment; filename="finsight-answer.{format}"',
            "X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"})
    @router.get("/{thread_id}/runs/{run_id}/stream")
    async def stream(thread_id: UUID, run_id: UUID, request: Request):
        await owned(thread_id, request)
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
    @router.get("/{thread_id}/working-notes")
    async def notes(thread_id: UUID, request: Request, query: str = "", note_id: str | None = None,
                    version: int | None = None, offset: int = 0, download: bool = False):
        await owned(thread_id, request)
        from .working_notes import working_notes_view
        return await working_notes_view(thread_id, current_owner(request), query=query, note_id=note_id,
                                        version=version, offset=offset, download=download)

    return router
