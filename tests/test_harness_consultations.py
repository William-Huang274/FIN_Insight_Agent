import asyncio
import json
from types import SimpleNamespace

import pytest
from langchain_core.tools import tool
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from sec_agent.agent_runtime.conversation_agent import GrantedTool, research_system_prompt
from sec_agent.agent_runtime.harness_business_tools import HarnessBusinessTools
from sec_agent.agent_runtime.harness_consultations import HarnessConsultations


@pytest.fixture
def anyio_backend():
    return 'asyncio'


@pytest.mark.anyio
async def test_consultation_actual_tool_schema_read_merge_and_replay(tmp_path, monkeypatch):
    calls = []
    @tool
    def read_source_document(query: str):
        """Read an authorized original."""
        return {'passage_id':'PASSAGE::fixture', 'text':'Original evidence: 42.'}
    @tool
    def read_saved_result(tool_call_id: str):
        """Read a previous receipt."""
        return {}
    grants = [GrantedTool(t,'read','authorized') for t in (read_source_document,read_saved_result)]
    async def provider(**kwargs):
        calls.append(kwargs)
        assert 'consult_research_agent' not in kwargs['bridge'].tools
        receipt = await kwargs['bridge'].execute('read_source_document', {'query':'chosen by investigator'})
        return 'Independent interpretation; evidence '+receipt.tool_call_id
    monkeypatch.setattr('sec_agent.agent_runtime.harness_consultations.independent_review',provider)
    async with AsyncSqliteSaver.from_conn_string(str(tmp_path/'state.sqlite')) as saver:
        service = HarnessConsultations(directory=tmp_path/'jobs',saver=saver,grants=grants,tid='t',rid='r',
            check=lambda:None,scope=lambda:__import__('contextlib').nullcontext(),budget=object(),environment={},
            model='gpt-6.1-sol',basis={},as_of='2026-11-06',public_sink=lambda x:None)
        bridge=HarnessBusinessTools(grants=grants+service.tools(),checkpointer=saver,thread_id='t',check=lambda:None)
        service.parent=bridge
        await bridge.initialize({'question':'original','messages':[]})
        schema=bridge.tools['consult_research_agent'].tool_call_schema.model_json_schema()
        assert 'runtime' not in schema['properties'] and 'purpose' in schema['required']
        prompt=research_system_prompt(bridge.tools)
        assert 'consult_research_agent is an available' in prompt
        assert 'read_research_agent_result' in prompt
        args=dict(question='Which explanation?',context='Current reasoning',purpose='investigate',method_ids=['research_loop'])
        result=await bridge.execute('consult_research_agent',args)
        assert result.status=='success'
        key=json.loads(result.content)['task_id']
        await service.tasks[key]
        got=await bridge.execute('read_research_agent_result',dict(task_id=key,wait_seconds=0))
        assert got.status=='success' and 'Independent interpretation' in got.content
        state=await bridge.state()
        assert any(getattr(m,'name','')=='read_source_document' for m in state['messages'])
        await bridge.execute('consult_research_agent',args)
        assert len(calls)==1
        assert '设备' not in calls[0]['message'].content  # no operator example injected as evidence
        assert calls[0]['assignment_kind']=='investigate'
        await service.ensure_finished()
        await service.close()


@pytest.mark.anyio
async def test_failure_blocks_parent_and_never_resubmits(tmp_path, monkeypatch):
    async def fail(**kwargs):
        raise ConnectionError('paid usage unknown')
    monkeypatch.setattr('sec_agent.agent_runtime.harness_consultations.independent_review',fail)
    async with AsyncSqliteSaver.from_conn_string(str(tmp_path/'s.sqlite')) as saver:
        service=HarnessConsultations(directory=tmp_path/'jobs',saver=saver,grants=[],tid='t',rid='r',
            check=lambda:None,scope=lambda:__import__('contextlib').nullcontext(),budget=object(),environment={},
            model='gpt-6.1-sol',basis={},as_of='2026-11-06',public_sink=lambda x:None)
        service.parent=SimpleNamespace(failed_receipt=None,access=lambda:None)
        out=await service.submit('Check','Reason','review',False,[],{'messages':[]})
        with pytest.raises(ConnectionError):
            await service.tasks[out['task_id']]
        assert service.parent.failed_receipt
        with pytest.raises(RuntimeError,match='requires_recovery'):
            await service.submit('Check','Reason','review',False,[],{'messages':[]})
        await service.close()
