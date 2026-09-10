"""LangGraph node using the pinned Hermes native runs API, not a second scheduler."""
import asyncio
import hashlib
import json
import os
from datetime import datetime, timezone

import httpx
from langchain_core.messages import AIMessage
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.config import get_stream_writer

from .working_memory_tools import memory_for


def bind_session(owner, workspace, actor, target=None):
    session = hashlib.sha256(json.dumps([owner,workspace,actor,(target or {}).get('id')]).encode()).hexdigest()
    memory = memory_for({},actor,owner=owner,workspace=workspace)
    with memory.connection() as db:
        db.execute('CREATE TABLE IF NOT EXISTS working_hermes_bindings(session TEXT PRIMARY KEY, owner TEXT, workspace TEXT, actor TEXT, target TEXT)')
        db.execute('INSERT OR IGNORE INTO working_hermes_bindings VALUES(?,?,?,?,?)',(session,owner,workspace,actor,json.dumps(target)))
        db.commit()
    return session


def build_hermes_graph(*, owner, workspace, actor, model, target=None, task_context='',public_sink=None):
    async def execute(state,config):
        session = bind_session(owner,workspace,actor,target)
        endpoint = os.environ['FINSIGHT_HERMES_URL'].rstrip('/')
        headers = {'Authorization':'Bearer '+os.environ['FINSIGHT_HERMES_TOKEN']}
        writer = get_stream_writer()
        def emit(event):
            event = {'actor':actor,'recorded_at':datetime.now(timezone.utc).isoformat(),**event}
            if public_sink: public_sink(event)
            writer(event)
        ids = config['configurable']
        message = next(m.content for m in reversed(state['messages']) if m.type=='human')
        from .working_memory_tools import WORKING_MEMORY_GUIDANCE
        body = {'input':message,'session_id':session,'model':model,
            'instructions':'You are FinSight. Answer in the user language. Working papers are fallible, not verified sources. '
                'Respect user corrections and disclose missing tools. Available tools only read or write task working papers. '
                'Do not claim to run SQL, search the web, alter user files or revise the final report. '+WORKING_MEMORY_GUIDANCE+task_context}
        remote_id = None
        async with httpx.AsyncClient(timeout=30,trust_env=False) as client:
            try:
                response = await client.post(endpoint+'/v1/runs',headers={**headers,'Idempotency-Key':str(ids['run_id'])},json=body)
                response.raise_for_status();remote_id=response.json()['run_id']
                emit({'kind':'stage','event':'started','objective':'Hermes 已接收本轮任务，使用当前工作底稿与保存的会话。','remote_run_id':remote_id})
                # Native API owns idempotency, transcript, cancellation and execution.
                async with client.stream('GET',endpoint+f'/v1/runs/{remote_id}/events',headers=headers,timeout=240) as stream:
                    stream.raise_for_status()
                    async for line in stream.aiter_lines():
                        if not line.startswith('data:'): continue
                        value=json.loads(line[5:])
                        name=value.get('event','')
                        if name=='message.delta':
                            writer({'kind':'assistant_delta','id':remote_id,'text':value.get('delta','')})
                        elif name.startswith('tool.'):
                            emit({'kind':'tool','event':name,'tool':value.get('tool','工作底稿工具')})
                response=await client.get(endpoint+f'/v1/runs/{remote_id}',headers=headers)
                response.raise_for_status(); result=response.json()
                if result.get('status')!='completed' or not result.get('output'):
                    raise RuntimeError('hermes_run_incomplete_'+str(result.get('status')))
                usage=result.get('usage') or {}
                total=usage.get('total_tokens')
                receipt=f' 本轮 Hermes 累计报告 {total:,} tokens（多次调用合计，不是当前上下文长度）。' if isinstance(total,int) else ' 本轮用量暂未取得。'
                emit({'kind':'stage','event':'completed','objective':'本轮完成，工作底稿与会话已保存。'+receipt,'remote_run_id':remote_id})
                return {'messages':[AIMessage(id=remote_id,content=result['output'])]}
            except BaseException:
                if remote_id:
                    try: await asyncio.shield(client.post(endpoint+f'/v1/runs/{remote_id}/stop',headers=headers))
                    except Exception: pass
                emit({'kind':'stage','event':'failure','status':'error','objective':'Hermes 本轮未完成；已保存底稿仍保留，未自动重跑。','remote_run_id':remote_id})
                raise
    graph=StateGraph(MessagesState);graph.add_node('hermes',execute)
    graph.add_edge(START,'hermes');graph.add_edge('hermes',END)
    return graph.compile()
