"""Read-only working-paper projection. Callers must authorize the thread first."""
from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool
from sec_agent.agent_runtime.working_memory_tools import memory_for, memory_enabled
import sqlite3


async def working_notes_view(thread_id, owner, *, query="", note_id=None, version=None, offset=0, download=False):
    if not memory_enabled():
        return {"enabled": False, "items": [], "notice": "本部署尚未启用持久工作底稿。"}
    def read():
        memory = memory_for({}, "reader", owner=owner, workspace=str(thread_id))
        if download:
            return memory.export_markdown(note_id, version=version)
        if note_id:
            return memory.read(note_id, version=version, offset=offset)
        return {"enabled": True, **memory.search(query, offset=offset)}
    try:
        value = await run_in_threadpool(read)
    except (OSError, sqlite3.Error):
        raise HTTPException(503, "工作底稿暂不可读取；未删除正文，也不影响查看已有报告。") from None
    if note_id and value.get("found") is False:
        raise HTTPException(404, "当前研究空间没有此底稿或版本")
    return value
