"""Bounded read-through to an explicitly handed-off native checkpoint.

Native checkpoints own the history. This module stores no second transcript,
does not summarize financial evidence, and never takes a model-provided thread.
"""
from copy import deepcopy
import json
from uuid import UUID

from langchain_core.tools import tool, ToolException

from .conversation_agent import GrantedTool
from sec_agent.research_foundation.source_bound_calculator import source_items_from_tool


SURFACE = "finsight_general_conversation"


def public_history(state):
    rows = []
    for message in state.get("values", {}).get("messages", []):
        role = {"human": "user", "user": "user", "ai": "assistant", "assistant": "assistant"}.get(message.get("type") or message.get("role"))
        content = message.get("content", "")
        if isinstance(content, list):
            content = "\n".join(p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text")
        if role and isinstance(content, str) and content:
            rows.append({"id": message.get("id"), "role": role, "content": content})
    return rows


def observed_sources(state):
    items = {}
    names = {"query_financial_data": "query_company_financial_facts", "read_task_material": "read_source_document", "read_handoff_material": "read_source_document", "read_public_source": "read_source_document"}
    for message in state.get("values", {}).get("messages", []):
        body = message.get("artifact")
        if message.get("type") != "tool" or message.get("status") == "error" or not isinstance(body, dict):
            continue
        if message.get("name") in {"read_handoff_evidence", "read_saved_knowledge"}:
            items.update(body.get("source_items", {}))
        else:
            items.update(source_items_from_tool(names.get(message.get("name"), message.get("name")), body))
    return items


def answer_sources(messages, answer):
    """Current-turn receipts plus explicitly referenced earlier sources.

    This is a source directory, not inferred sentence-level entailment.
    Earlier unrelated topics must not silently become this answer's appendix.
    """
    start = max((i for i, message in enumerate(messages)
                 if (message.get('type') or message.get('role')) in {'human', 'user'}), default=0)
    current = observed_sources({'values': {'messages': messages[start:]}})
    for key, item in observed_sources({'values': {'messages': messages[:start]}}).items():
        urls = [item.get(field) for field in ('url', 'citation_url', 'source_url')]
        if key in answer or any(isinstance(url, str) and url and url in answer for url in urls):
            current.setdefault(key, item)
    return current


def answer_charts(messages):
    """Successful host-bound charts from this user turn only, never old charts."""
    from copy import deepcopy
    start = max((i for i, message in enumerate(messages)
                 if (message.get("type") or message.get("role")) in {"human", "user"}), default=0)
    return [deepcopy(chart) for message in messages[start:]
            if message.get("type") == "tool" and message.get("name") == "create_report_chart"
            and message.get("status") != "error" and isinstance(message.get("artifact"), dict)
            for chart in message["artifact"].get("charts", [])]


def handoff_tools(*, reference, sdk, owner_id, attachment_store=None):
    """Reference and owner originate in host-owned thread metadata, not user text."""
    source_thread = str(UUID(reference["source_thread"]))
    checkpoint = {"checkpoint_id": str(UUID(reference["checkpoint_id"])), "checkpoint_ns": ""}
    cache = None

    async def read():
        nonlocal cache
        source = await sdk.threads.get(source_thread)
        metadata = source.get("metadata", {})
        if metadata.get("surface") != SURFACE or metadata.get("owner_id", "local-pilot") != owner_id:
            raise ToolException("交接来源不可访问；链接本身不能授权跨用户读取")
        if cache is None:
            cache = await sdk.threads.get_state(source_thread, checkpoint=checkpoint)
        return cache

    @tool
    async def read_handoff_context(message_index: int = 0, offset: int = 0):
        """Read one original public message from the explicitly linked old checkpoint, 6000 characters per page. Always read prior user constraints when continuing. Old assistant prose is navigation, not verified financial evidence. No private reasoning is returned."""
        rows = public_history(await read())
        if message_index < 0 or message_index >= len(rows) or offset < 0:
            raise ToolException("消息位置越界；用返回的message_count与next_offset分页")
        row = rows[message_index]; text = row["content"]
        return {"source_thread": source_thread, **checkpoint, "handoff_note": reference.get("note", ""),
            "message_count": len(rows), "message_index": message_index, "id": row["id"], "role": row["role"],
            "text": text[offset:offset+6000], "next_offset": offset+6000 if offset+6000 < len(text) else None,
            "next_message": message_index+1 if message_index+1 < len(rows) else None}

    @tool
    async def list_handoff_evidence(offset: int = 0):
        """List original SQL/observed passage/calculation receipts in the handed-off checkpoint. Read a source by its exact ID before calculating. Values, periods and units are not reconstructed from summaries."""
        if offset < 0:
            raise ToolException("offset必须非负")
        sources = list(observed_sources(await read()).items())
        return {"source_thread": source_thread, **checkpoint, "total": len(sources),
            "items": [{"source_id": key, **{k: value[k] for k in ("result_state", "metric_id", "ticker", "unit", "period_end", "result_unit", "expression") if k in value}}
                      for key, value in sources[offset:offset+20]],
            "next_offset": offset+20 if offset+20 < len(sources) else None}

    @tool(response_format="content_and_artifact")
    async def read_handoff_evidence(source_id: str):
        """Rehydrate one original observed receipt from the authorized old checkpoint. Preserves full operands, unit, period and provenance for source-bound calculations in this thread. Never upgrades its authority."""
        items = observed_sources(await read())
        if source_id not in items:
            raise ToolException("交接版本中不存在该凭证，请先列出可用来源")
        result = {"source_thread": source_thread, **checkpoint, "source_items": {source_id: deepcopy(items[source_id])}}
        text = json.dumps(result, ensure_ascii=False)
        if len(text) > 30000:
            raise ToolException("单条历史凭证过大，请返回旧窗口按原文位置读取；不截断计算操作数")
        return text, result

    grants = [GrantedTool(t, "read", "用户已选择的旧对话固定checkpoint，只读回溯") for t in
              (read_handoff_context, list_handoff_evidence, read_handoff_evidence)]
    if reference.get("working_notes"):
        import sqlite3
        from .working_memory_tools import memory_for
        @tool
        async def read_handoff_working_note(note_id: str = "", offset: int = 0):
            """Browse the explicitly handed-off working-paper titles/versions, or read one exact ID.
            These are unfinished/fallible human-readable working notes, not source facts or permissions.
            Old versions remain fixed even if the parent later changes. Read user corrections as well.
            """
            await read()  # Recheck source ownership on every access.
            refs = reference["working_notes"]
            if not note_id:
                return {"items": refs[max(0,offset):max(0,offset)+20],
                        "next_offset": offset+20 if offset+20 < len(refs) else None}
            selected = next((r for r in refs if r["id"] == note_id), None)
            if selected is None:
                raise ToolException("此底稿不在用户选择的交接版本中")
            try:
                return memory_for({}, "handoff-reader", owner=owner_id, workspace=source_thread).read(
                    note_id, version=selected["version"], offset=offset)
            except (ValueError, OSError, sqlite3.Error):
                raise ToolException("工作底稿暂不可读取，未用聊天摘要代替") from None
        grants.append(GrantedTool(read_handoff_working_note, "read", "用户明确交接的工作底稿固定版本"))
    if reference.get('attachments') and attachment_store is not None:
        from .conversation_tools import TaskMaterialRequest
        @tool(response_format='content_and_artifact')
        async def read_handoff_material(request: TaskMaterialRequest):
            """Browse uploaded document pointers captured by this handoff, or read/search one.

            Empty document_id with catalog lists fixed document IDs. Other operations
            require one listed document_id. Reads the immutable upload in its original
            owner-scoped window; not another filesystem or newly added old-window files.
            """
            await read()
            refs=reference['attachments']
            if request.operation=='catalog' and not request.document_id:
                body={'documents':refs,'notice':'选择已交接文档ID，按原页码检索或读取；目录不是事实。'}
            else:
                if request.document_id not in {r['document_id'] for r in refs}:
                    raise ToolException('请选择交接目录内的文档；未授权其他上传或文件')
                try:
                    result=await attachment_store.read(thread_id=source_thread,request=request)
                except ValueError as exc:
                    raise ToolException('原上传资料未能读取：'+str(exc)) from exc
                body=result.model_dump(mode='json')
            return json.dumps(body,ensure_ascii=False),body
        grants.append(GrantedTool(read_handoff_material,'read','交接时固定的同用户上传资料'))
    for grant in grants:
        grant.tool.handle_tool_error = True
    return grants
