"""Read-only working-paper projection. Callers must authorize the thread first."""
from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool
from sec_agent.agent_runtime.working_memory_tools import memory_for, memory_enabled
import sqlite3
from pydantic import BaseModel, Field, ConfigDict
from typing import Literal


class WorkingNoteRevision(BaseModel):
    note_id: str = Field(min_length=1,max_length=64)
    version: int = Field(ge=1)
    instruction: str = Field(min_length=1,max_length=8000)
    model: Literal['deepseek-v4-flash','deepseek-v4-pro'] = 'deepseek-v4-flash'
    harness: Literal['native','hermes'] = 'native'


class ContextEdit(BaseModel):
    model_config = ConfigDict(extra='forbid')
    body: str = Field(max_length=6000)
    version: int = Field(ge=0)


class WorkingNoteEdit(BaseModel):
    model_config = ConfigDict(extra='forbid')
    note_id: str = Field(min_length=1,max_length=64)
    version: int = Field(ge=1)
    body: str = Field(min_length=1,max_length=200000)


async def edit_context(thread_id, owner, body):
    from sec_agent.agent_runtime.user_context import save_user_context
    if not memory_enabled(): raise HTTPException(503,'持久记忆未启用')
    result = await run_in_threadpool(save_user_context,owner,str(thread_id),body.body,body.version)
    if not result.get('saved'): raise HTTPException(409,result.get('reason','保存失败'))
    return {**result,'notice':'已保存。后续运行读取最新版；不会启动模型或改写已有报告。'}


async def edit_working_note(thread_id, owner, body):
    note = await working_notes_view(thread_id,owner,note_id=body.note_id)
    if note['version'] != body.version: raise HTTPException(409,'底稿已更新，请重新读取后编辑')
    if note['actor']=='user_context' and len(body.body)>6000: raise HTTPException(422,'研究要求最多6000字符')
    memory = memory_for({},note['actor'],owner=owner,workspace=str(thread_id))
    result = await run_in_threadpool(memory.save,note['title'],body.body,body.version)
    if not result.get('saved'): raise HTTPException(409,result.get('reason','保存失败'))
    return {**result,'notice':'已保存新版本。旧版保留；这是工作底稿修订，不代表事实已核验或正式报告已更新。'}


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


async def working_notes_view(thread_id, owner, *, query="", note_id=None, version=None, offset=0, download=False, checkpoint=None):
    from ...application.checkpoint_papers import checkpoint_papers
    legacy = checkpoint_papers(checkpoint) if checkpoint else []
    if note_id and note_id.startswith('checkpoint:'):
        row = next((r for r in legacy if r['id']==note_id), None)
        if row is None or version not in (None,1): raise HTTPException(404,'该历史底稿不在当前研究中')
        if download: return {'markdown':row['body'],'title':row['title'],'version':1}
        start=max(0,offset)
        return {**row,'body':row['body'][start:start+6000], 'next_offset':start+6000 if start+6000<len(row['body']) else None}
    if not memory_enabled():
        return {"enabled": False, "items": [], 'checkpoint_items':[{k:v for k,v in r.items() if k!='body'} for r in legacy], "notice": "本部署尚未启用持久工作底稿。"}
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
    if not note_id:
        value['checkpoint_items']=[{k:v for k,v in row.items() if k!='body'} for row in legacy
            if not query.strip() or query.casefold() in (row['title']+row['body']).casefold()]
    return value


def install_edit_routes(router, prefix, authorize, sdk):
    """Use existing owner checks and transactional note revisions; no paid run."""
    from uuid import UUID
    from fastapi import Request
    from ...authentication import current_owner

    async def writable(thread_id, request):
        if request.headers.get('x-workbench-request')!='1': raise HTTPException(403,'缺少工作台请求标识')
        thread=await authorize(thread_id,request)
        if thread.get('status')=='busy': raise HTTPException(409,'请先等待或停止当前运行，再保存修改')
        return thread

    @router.get(prefix+'/{thread_id}/user-context')
    async def get_context(thread_id: UUID, request: Request):
        await authorize(thread_id,request)
        from sec_agent.agent_runtime.user_context import current_user_context
        return await run_in_threadpool(current_user_context,current_owner(request),str(thread_id))

    @router.put(prefix+'/{thread_id}/user-context')
    async def put_context(thread_id: UUID, request: Request, body: ContextEdit):
        await writable(thread_id,request)
        return await edit_context(thread_id,current_owner(request),body)

    @router.put(prefix+'/{thread_id}/working-notes')
    async def put_note(thread_id: UUID, request: Request, body: WorkingNoteEdit):
        thread=await writable(thread_id,request)
        target=thread.get('metadata',{}).get('working_note_target')
        if target:
            # Revision windows edit the same already-authorized parent workspace.
            parent=await sdk.threads.get(target['workspace'])
            if parent.get('metadata',{}).get('owner_id','local-pilot')!=current_owner(request): raise HTTPException(404,'底稿不存在')
            if parent.get('status')=='busy': raise HTTPException(409,'原研究运行中，请先等待或停止')
            thread_id=target['workspace']
        return await edit_working_note(thread_id,current_owner(request),body)
