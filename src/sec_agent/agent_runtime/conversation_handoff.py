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
    names = {"query_financial_data": "query_company_financial_facts", "read_task_material": "read_source_document"}
    for message in state.get("values", {}).get("messages", []):
        body = message.get("artifact")
        if message.get("type") != "tool" or message.get("status") == "error" or not isinstance(body, dict):
            continue
        if message.get("name") == "read_handoff_evidence":
            items.update(body.get("source_items", {}))
        else:
            items.update(source_items_from_tool(names.get(message.get("name"), message.get("name")), body))
    return items


def handoff_tools(*, reference, sdk, owner_id):
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
    for grant in grants:
        grant.tool.handle_tool_error = True
    return grants
