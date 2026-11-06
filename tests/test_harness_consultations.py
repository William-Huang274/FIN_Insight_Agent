import asyncio
import json
from types import SimpleNamespace

import pytest
from langchain_core.tools import tool
from langchain_core.messages import ToolMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from sec_agent.agent_runtime.conversation_agent import GrantedTool, research_system_prompt
from sec_agent.agent_runtime.harness_business_tools import HarnessBusinessTools
from sec_agent.agent_runtime.harness_consultations import HarnessConsultations


@pytest.fixture
def anyio_backend():
    return 'asyncio'


@pytest.mark.anyio
async def test_consultation_retry_chain_reuses_latest_record_without_dispatch():
    from copy import deepcopy
    from sec_agent.agent_runtime.answer_review_provider import saved_consultation_attempt
    basis={'harness_execution_scope':'t:old','harness_dispatch_lane':'consult:k'}
    first={'status':'unknown','call_id':'a','basis':basis}
    second={'status':'unknown','call_id':'b','basis':{**basis,'harness_execution_scope':'t:next'}}
    third={'status':'received','call_id':'c','basis':{**basis,'harness_execution_scope':'t:later'}}
    first['basis']={k:v for k,v in basis.items() if k!='harness_dispatch_lane'}  # pre-lane dispatch
    root='answer-review:consult-k:1'
    rows={root+':retry:a':second,root+':retry:a:retry:b':third}
    original=deepcopy(rows)
    store=SimpleNamespace(lookup=lambda o,b,k:rows.get(k))
    key,row=await saved_consultation_attempt(store,'owner','budget',root,first,'t:current','consult:k')
    assert key==root+':retry:a:retry:b' and row is third and rows==original
    for scope,lane in [('other:current','consult:k'),('t:current','consult:other'),('t:current',None)]:
        assert await saved_consultation_attempt(store,'owner','budget',root,first,scope,lane)==(root,first)


@pytest.mark.anyio
async def test_pre_dispatch_consultation_recovery_requires_zero_dispatch_proof(tmp_path,monkeypatch):
    from sec_agent.agent_runtime.harness_acp_session import _persist
    observed=[]; initializations=[]
    original_initialize=HarnessBusinessTools.initialize
    async def initialize(self,admitted_state,**kwargs):
        initializations.append(kwargs.get('recovering',False))
        return await original_initialize(self,admitted_state,**kwargs)
    monkeypatch.setattr(HarnessBusinessTools,'initialize',initialize)
    async def provider(**kwargs):
        observed.append(kwargs);return 'Saved opinion'
    monkeypatch.setattr('sec_agent.agent_runtime.harness_consultations.independent_review',provider)
    monkeypatch.setattr('sec_agent.adapters.explicit_run_recovery.verified_permit',lambda *a,**k:{'verified':True})
    monkeypatch.setattr('sec_agent.adapters.explicit_run_recovery.verified_preparation_recovery',lambda *a,**k:None)
    request=dict(question='Original question',context='Context',purpose='review',report=None,method_text='')
    old=dict(request=request,status='failed',scope='t:paid',error_type='CancelledError')
    stopped=dict(request=request,status='failed',scope='t:preparation',previous_scope='t:paid',error_type='ValueError')
    key='a'*64;directory=tmp_path/'jobs'
    _persist(directory/'history'/key/'paid.json',old);_persist(directory/(key+'.json'),stopped)
    async with AsyncSqliteSaver.from_conn_string(str(tmp_path/'s.sqlite')) as saver:
        service=HarnessConsultations(directory=directory,saver=saver,grants=[],tid='t',rid='next',check=lambda:None,
            scope=lambda:__import__('contextlib').nullcontext(),budget=object(),environment={'FINSIGHT_ORGANIZATION_RUNTIME_SECRET':'fixture'},
            model='gpt-6.1-sol',basis={},as_of='2026-11-06',public_sink=lambda x:None)
        await service.child(key).initialize({'question':'Original question','messages':[]})
        with pytest.raises(RuntimeError,match='separate_reconciliation'):
            await service.recover_cancelled('preparation',tmp_path/'audit')
        assert not observed
        monkeypatch.setattr('sec_agent.adapters.explicit_run_recovery.verified_preparation_recovery',lambda *a,**k:{'dispatch_rows':0})
        await service.recover_cancelled('preparation',tmp_path/'audit');await service.tasks[key]
        assert observed[0]['previous_scope']=='t:paid'
        assert initializations[-1] is True
        assert observed[0]['message'].content=='Context'
        assert json.loads((directory/'history'/key/'preparation.json').read_text())==stopped
        await service.close()


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
        assert calls[0]['dispatch_lane']=='consult:'+key
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


@pytest.mark.anyio
async def test_explicit_recovery_retries_saved_failed_read_not_arbitrary_failure(tmp_path, monkeypatch):
    from langchain_core.tools import ToolException
    fixed = False
    executions = []
    @tool
    def read_source_document(query: str):
        """Read an authorized original."""
        executions.append(query)
        if not fixed:
            raise ToolException('old wrapper limit')
        return {'text':'original', 'query':query}
    read_source_document.handle_tool_error = True
    grants = [GrantedTool(read_source_document, 'read', 'authorized')]
    async def provider(**kwargs):
        receipt = await kwargs['bridge'].execute('read_source_document', {'query':'unchanged proposal'})
        if receipt.status == 'error':
            raise ValueError('answer_review_source_tool_failed:'+receipt.tool_call_id)
        return 'Opinion from actual read'
    monkeypatch.setattr('sec_agent.agent_runtime.harness_consultations.independent_review', provider)
    monkeypatch.setattr('sec_agent.adapters.explicit_run_recovery.verified_permit', lambda *a,**k:None)
    async with AsyncSqliteSaver.from_conn_string(str(tmp_path/'state.sqlite')) as saver:
        def service(rid):
            return HarnessConsultations(directory=tmp_path/'jobs', saver=saver, grants=grants,
                tid='t',rid=rid,check=lambda:None,scope=lambda:__import__('contextlib').nullcontext(),
                budget=object(),environment={'FINSIGHT_ORGANIZATION_RUNTIME_SECRET':'fixture'},
                model='gpt-6.1-sol',basis={},as_of='2026-11-06',public_sink=lambda x:None)
        first=service('old')
        out=await first.submit('Check','Context','review',False,[],{'messages':[]})
        key=out['task_id']
        with pytest.raises(ValueError,match='source_tool_failed'):
            await first.tasks[key]
        await first.close()
        fixed=True
        resumed=service('new')
        await resumed.recover_cancelled('old',tmp_path/'audit')
        await resumed.tasks[key]
        assert executions==['unchanged proposal','unchanged proposal']
        old=json.loads((tmp_path/'jobs'/'history'/key/'old.json').read_text())
        assert old['status']=='failed' and old['failure_code'].startswith('answer_review_source_tool_failed:')
        assert json.loads((tmp_path/'jobs'/(key+'.json')).read_text())['status']=='completed'
        assert 'failure_code' not in json.loads((tmp_path/'jobs'/(key+'.json')).read_text())
        assert any(m.type=='tool' and m.status=='error' for m in (await resumed.child(key).state())['messages'])
        await resumed.close()


@pytest.mark.anyio
async def test_host_wait_uses_durable_explicit_read_not_submission(tmp_path, monkeypatch):
    finish=asyncio.Event()
    async def provider(**kwargs):
        await finish.wait()
        return 'Completed independent work'
    monkeypatch.setattr('sec_agent.agent_runtime.harness_consultations.independent_review', provider)
    async with AsyncSqliteSaver.from_conn_string(str(tmp_path/'state.sqlite')) as saver:
        service=HarnessConsultations(directory=tmp_path/'jobs',saver=saver,grants=[],tid='t',rid='r',
            check=lambda:None,scope=lambda:__import__('contextlib').nullcontext(),budget=object(),environment={},
            model='gpt-6.1-sol',basis={},as_of='2026-11-06',public_sink=lambda x:None)
        bridge=HarnessBusinessTools(grants=service.tools(),checkpointer=saver,thread_id='t',check=lambda:None)
        service.parent=bridge
        await bridge.initialize({'question':'original','messages':[]})
        result=await bridge.execute('consult_research_agent',dict(question='Independent issue',context='Why it matters',purpose='investigate'))
        key=json.loads(result.content)['task_id']
        assert await service.dispatch_ready(timeout=0)=={'status':'ready'}  # other useful author work allowed
        await bridge.execute('read_research_agent_result',dict(task_id=key,wait_seconds=0))
        assert await service.dispatch_ready(timeout=0)=={'status':'waiting'}
        waiter=asyncio.create_task(service.dispatch_ready(timeout=10))
        await asyncio.sleep(.01); waiter.cancel()
        with pytest.raises(asyncio.CancelledError): await waiter
        assert not service.tasks[key].cancelled()  # cancelling host wait is not losing child state
        finish.set();await service.tasks[key]
        assert await service.dispatch_ready(timeout=0)=={'status':'ready'}
        got=await bridge.execute('read_research_agent_result',dict(task_id=key))
        assert json.loads(got.content)['status']=='completed'
        await service.close()


@pytest.mark.anyio
async def test_cancelled_consultation_requires_permit_and_reuses_exact_target(tmp_path, monkeypatch):
    observed=[]
    async def cancelled(**kwargs):
        observed.append(kwargs)
        raise asyncio.CancelledError()
    monkeypatch.setattr('sec_agent.agent_runtime.harness_consultations.independent_review',cancelled)
    monkeypatch.setattr('sec_agent.adapters.explicit_run_recovery.verified_permit',lambda *a,**kw:None)
    async with AsyncSqliteSaver.from_conn_string(str(tmp_path/'s.sqlite')) as saver:
        def service(rid):
            item=HarnessConsultations(directory=tmp_path/'jobs',saver=saver,grants=[],tid='t',rid=rid,
                check=lambda:None,scope=lambda:__import__('contextlib').nullcontext(),budget=object(),
                environment={'FINSIGHT_ORGANIZATION_RUNTIME_SECRET':'fixture'},model='gpt-6.1-sol',basis={},
                as_of='2026-11-06',public_sink=lambda x:None)
            item.parent=SimpleNamespace(failed_receipt=None,access=lambda:None)
            return item
        first=service('old')
        result=await first.submit('Original question','Original context','review',True,[],
                                 {'messages':[],'report':{'narrative_markdown':'Original report'}})
        key=result['task_id']
        with pytest.raises(asyncio.CancelledError):await first.tasks[key]
        await first.close()
        stopped=(tmp_path/'jobs'/(key+'.json')).read_bytes()
        second=service('new')
        with pytest.raises(RuntimeError,match='explicit_paid_retry_authorization'):
            await second.recover_cancelled('old',tmp_path/'audit')
        assert (tmp_path/'jobs'/(key+'.json')).read_bytes()==stopped
        assert len(observed)==1
        monkeypatch.setattr('sec_agent.adapters.explicit_run_recovery.verified_permit',lambda *a,**kw:{'verified':True})
        async def completed(**kwargs):
            observed.append(kwargs)
            return 'Actual independent opinion'
        monkeypatch.setattr('sec_agent.agent_runtime.harness_consultations.independent_review',completed)
        async def parent_state():
            return {'messages':[ToolMessage(name='consult_research_agent',tool_call_id='actual',
                content=json.dumps({'task_id':key,'status':'running'}))]}
        second.parent.state=parent_state
        # An intermediate recovery stopped before provider preparation; use the
        # real outstanding task receipt and its original signed authorization.
        await second.recover_cancelled('interrupted-preparation',tmp_path/'audit')
        await second.tasks[key]
        assert observed[1]['message'].content==observed[0]['message'].content=='Original report'
        assert observed[1]['question']==observed[0]['question']
        assert observed[1]['command_id']==observed[0]['command_id']
        assert observed[1]['previous_scope']=='t:old' and observed[1]['scope']=='t:new'
        assert json.loads((tmp_path/'jobs'/'history'/key/'old.json').read_text())['status']=='failed'
        assert json.loads((tmp_path/'jobs'/(key+'.json')).read_text())['status']=='completed'
        await second.close()
