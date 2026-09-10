"""Memory readers stay scoped and raw; summaries never replace canonical records."""
from types import SimpleNamespace
from uuid import uuid4
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.tools import ToolException
from apps.workbench.backend.api.v1.conversations import build_conversations_router, SURFACE, GRAPH
from apps.workbench.backend.application.conversation_context import context_status
from sec_agent.agent_runtime.hermes_context_tools import execute_context_tool


def test_hermes_native_rows_are_public_and_exact():
    rows=[{'id':4,'role':'user','content':'取消旧计划，仅保留 NOVA FY2024。'},
          {'id':5,'role':'assistant','content':[{'type':'reasoning','text':'PRIVATE'},{'type':'text','text':'保留原始记录'}], 'reasoning':'PRIVATE'},
          {'id':6,'role':'tool','content':'PRIVATE_TOOL'},
          {'id':7,'role':'assistant','content':'Lossy summary','is_compaction_summary':True}]
    result=execute_context_tool('browse_context',{'region':'conversation'},rows)
    assert [r['key'] for r in result['items']]==['5','4']
    assert 'PRIVATE' not in str(result)
    assert execute_context_tool('read_context_turn',{'message_id':'4'},rows)['text']==rows[0]['content']
    assert execute_context_tool('browse_context',{'region':'numbers'},rows)['items']==[]
    with pytest.raises(ToolException):execute_context_tool('read_context_turn',{'message_id':'6'},rows)
    with pytest.raises(ValueError):execute_context_tool('browse_context',{'region':'conversation','session_id':'other-owner'},rows)


def test_failed_summary_status_retains_originals():
    state={'values':{'messages':[{'type':'human','id':'first','content':'只做当期观察'}],
        'request_summary_failure':{'reason':'timeout','original_history_retained':True}}}
    result=context_status(state)
    assert result['summary_status']=='failed' and result['original_history_retained']
    assert result['original_message_count']==result['projected_message_count']==1
    assert result['summary_text']==''


def test_context_routes_owner_and_receipt_region_boundaries():
    tid=str(uuid4())
    thread={'metadata':{'surface':SURFACE,'graph':GRAPH,'owner_id':'local-pilot'}}
    async def get(_):return thread
    async def state(_):return {'values':{'messages':[
        {'type':'human','id':'u1','content':'NOVA FY2024'},
        {'type':'ai','id':'a1','content':'','tool_calls':[{'name':'query_financial_data','id':'number1','args':{'ticker':'NOVA'}}]},
        {'type':'tool','id':'r1','tool_call_id':'number1','name':'query_financial_data','content':'207 百万美元，FY2024'}]}}
    app=FastAPI();app.include_router(build_conversations_router(SimpleNamespace(sdk=SimpleNamespace(threads=SimpleNamespace(get=get,get_state=state)))))
    with TestClient(app) as client:
        base=f'/conversations/{tid}/context'
        assert client.get(base,params={'region':'numbers'}).json()['items'][0]['key']=='number1'
        assert client.get(base+'/read',params={'region':'numbers','key':'number1'}).json()['text']=='207 百万美元，FY2024'
        assert client.get(base+'/read',params={'region':'sources','key':'number1'}).status_code==404
        assert client.get(base+'/read',params={'key':'number1'}).status_code==404
        assert client.get(base,params={'offset':-1}).status_code==422
        thread['metadata']['owner_id']='bob'
        assert client.get(base).status_code==404
        assert client.get(base+'/read',params={'key':'u1'}).status_code==404
