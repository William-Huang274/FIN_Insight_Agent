"""Read-only working-paper projection. Callers must authorize the thread first."""
from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool
from sec_agent.agent_runtime.working_memory_tools import memory_for, memory_enabled
import sqlite3
from pydantic import BaseModel, Field
from typing import Literal


class WorkingNoteRevision(BaseModel):
    note_id: str = Field(min_length=1,max_length=64)
    version: int = Field(ge=1)
    instruction: str = Field(min_length=1,max_length=8000)
    model: Literal['deepseek-v4-flash','deepseek-v4-pro'] = 'deepseek-v4-flash'
    harness: Literal['native','hermes'] = 'native'


async def revise_working_note(service, thread_id, owner, body):
    from .conversations import SURFACE, GRAPH
    if not service.research_profile:
        raise HTTPException(503,'本部署未启用模型运行')
    import os
    if body.harness=='hermes' and not os.environ.get('FINSIGHT_HERMES_URL'):
        raise HTTPException(503,'本部署尚未连接 Hermes')
    note = await working_notes_view(thread_id,owner,note_id=body.note_id)
    if not note.get('found') or note['version'] != body.version:
        raise HTTPException(409,'底稿版本已变化，请读取最新版本后再提交意见')
    target = {k:note[k] for k in ('id','title','actor','version')}
    target['workspace'] = str(thread_id)
    thread = await service.sdk.threads.create(metadata={'surface':SURFACE,'graph':GRAPH,'owner_id':owner,
        'title':'底稿修订 · '+note['title'][:60],'working_note_target':target,'harness':body.harness})
    run = await service.sdk.runs.create(thread['thread_id'],GRAPH,
        input={'messages':[{'role':'user','content':body.instruction}]},
        config={'configurable':{'conversation_model':body.model,'permission_mode':'request_standard'}},
        stream_mode=['custom','messages-tuple'],stream_resumable=True,multitask_strategy='reject',
        metadata={'surface':SURFACE,'request_message':body.instruction,'model':body.model,
                  'permission_mode':'request_standard','working_note_target':target})
    return {'thread_id':thread['thread_id'],'run_id':run['run_id'],
            'notice':'已交给该底稿的责任角色处理；修改保留版本，正式报告不会被直接覆盖。'}


async def working_notes_view(thread_id, owner, *, query="", note_id=None, version=None, offset=0, download=False):
    if not memory_enabled():
        return {"enabled": False, "items": [], "notice": "本部署尚未启用持久工作底稿。"}
    def read():
        memory = memory_for({}, "reader", owner=owner, workspace=str(thread_id))
        if download:
            return memory.export_markdown(note_id, version=version)
        if note_id:
            return memory.read(note_id, version=version, offset=offset)
        from sec_agent.agent_runtime.working_memory_search import search_working_papers
        return {"enabled": True, **search_working_papers(memory,query,offset=offset)}
    try:
        value = await run_in_threadpool(read)
    except (OSError, sqlite3.Error):
        raise HTTPException(503, "工作底稿暂不可读取；未删除正文，也不影响查看已有报告。") from None
    if note_id and value.get("found") is False:
        raise HTTPException(404, "当前研究空间没有此底稿或版本")
    return value
