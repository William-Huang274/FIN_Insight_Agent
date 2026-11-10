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
        assert calls[0]['research_task']=={'question':'original','as_of':'2026-11-06','review_scope':'delegated_question'}
        assert 'author_task' not in json.loads(got.content)
        assert calls[0]['dispatch_lane']=='consult:'+key
        await service.ensure_finished()
        await service.close()


@pytest.mark.anyio
async def test_review_preserves_original_scope_and_returns_author_actions(tmp_path, monkeypatch):
    calls = []
    async def provider(**kwargs):
        calls.append(kwargs)
        return 'Independent objection and proposed action.'
    monkeypatch.setattr('sec_agent.agent_runtime.harness_consultations.independent_review', provider)
    async with AsyncSqliteSaver.from_conn_string(str(tmp_path/'scope.sqlite')) as saver:
        service = HarnessConsultations(directory=tmp_path/'jobs', saver=saver, grants=[], tid='t', rid='r',
            check=lambda:None, scope=lambda:__import__('contextlib').nullcontext(), budget=object(), environment={},
            model='gpt-6.1-sol', basis={}, as_of='2026-11-06', public_sink=lambda x:None,
            research_question='Compare adoption and economics across user groups')
        bridge = HarnessBusinessTools(grants=service.tools(), checkpointer=saver, thread_id='t', check=lambda:None)
        service.parent = bridge
        await bridge.initialize({'question':'An author summary must not replace the admitted task',
            'messages':[], 'report':{'narrative_markdown':'Original manuscript'}, 'report_version':1})
        result = await bridge.execute('consult_research_agent', dict(question='Check one revenue figure',
            context='Author believes market is settled', purpose='review', use_current_report=True))
        key = json.loads(result.content)['task_id']
        await service.tasks[key]
        assert calls[0]['research_task']['question']=='Compare adoption and economics across user groups'
        assert calls[0]['research_task']['review_scope']=='current_report'
        assert calls[0]['question']=='Check one revenue figure\nAuthor believes market is settled'
        assert calls[0]['message'].content=='Original manuscript'
        got = await bridge.execute('read_research_agent_result',dict(task_id=key))
        from sec_agent.agent_runtime.answer_review import report_revision_task
        payload=json.loads(got.content)
        assert payload['author_task']==report_revision_task()
        assert payload['opinion']=='Independent objection and proposed action.'
        saved=json.loads((tmp_path/'jobs'/f'{key}.json').read_text())
        assert saved['request']['research_task']==calls[0]['research_task']
        assert 'original_research_task' not in bridge.tools['consult_research_agent'].tool_call_schema.model_json_schema()['properties']
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
async def test_child_uses_run_context_after_submitting_memory_scope_exits(tmp_path, monkeypatch):
    from sec_agent.agent_runtime.working_memory_tools import native_memory_scope
    from sec_agent.agent_runtime.working_memory import WorkingMemoryAccessDenied
    entered = asyncio.Event(); proceed = asyncio.Event(); valid = True
    def check():
        if not valid:
            raise WorkingMemoryAccessDenied('revoked')
    scope = lambda: native_memory_scope('owner', 'workspace', access_check=check, allow_remote_search=False)
    @tool
    def read_source_document(query: str):
        """Read under the admitted workspace."""
        return {'text':query}
    grants = [GrantedTool(read_source_document, 'read', 'authorized')]
    async def provider(**kwargs):
        entered.set(); await proceed.wait()
        result = await kwargs['bridge'].execute('read_source_document', {'query':'exact original'})
        return result.content
    monkeypatch.setattr('sec_agent.agent_runtime.harness_consultations.independent_review',provider)
    async with AsyncSqliteSaver.from_conn_string(str(tmp_path/'s.sqlite')) as saver:
        service = HarnessConsultations(directory=tmp_path/'jobs', saver=saver, grants=grants,
            tid='t', rid='r', check=check, scope=scope, budget=object(), environment={},
            model='gpt-6.1-sol', basis={}, as_of='2026-11-06', public_sink=lambda x:None)
        with scope():
            first=await service.submit('Check','Context','review',False,[],{'messages':[]})
            await entered.wait()
        proceed.set()
        await service.tasks[first['task_id']]
        assert json.loads((tmp_path/'jobs'/(first['task_id']+'.json')).read_text())['status']=='completed'
        valid=False
        with pytest.raises(WorkingMemoryAccessDenied):
            await service.submit('Other','Context','review',False,[],{'messages':[]})
        await service.close()


@pytest.mark.parametrize('error_type', ['WorkingMemoryAccessDenied', 'CancelledError', 'DispatchBlocked'])
def test_scope_failure_replay_requires_all_received_and_priced(tmp_path, error_type):
    from contextlib import contextmanager
    rows = [{'status':'received','actual_micros':10,'response':{'stop_required':False}}]
    @contextmanager
    def connection():
        yield SimpleNamespace(execute=lambda *a:SimpleNamespace(fetchall=lambda:rows))
    service=HarnessConsultations(directory=tmp_path/'jobs',saver=None,grants=[],tid='t',rid='new',
        check=lambda:None,scope=lambda:None,budget=SimpleNamespace(owner='o',budget='b',store=SimpleNamespace(connection=connection)),
        environment={},model='gpt-6.1-sol',basis={},as_of='2026-11-06',public_sink=lambda x:None)
    record={'error_type':error_type,'scope':'t:old'}
    assert service.settled_scope_failure('key',record)
    for bad in [{'status':'unknown'}, {'status':'dispatched'}, {'actual_micros':None}, {'response':{'stop_required':True}}]:
        old=rows[0].copy();rows[0].update(bad)
        assert not service.settled_scope_failure('key',record)
        rows[0]=old
    rows.clear()
    assert not service.settled_scope_failure('key',record)


def test_transport_recovery_matches_signed_unknown_ledger(tmp_path):
    from contextlib import contextmanager
    rows = [dict(call_id='paid', status='received', actual_micros=10, response={'stop_required':False}),
            dict(call_id='failed', status='unknown', actual_micros=None, response=None)]
    @contextmanager
    def connection():
        yield SimpleNamespace(execute=lambda *a:SimpleNamespace(fetchall=lambda:rows))
    service=HarnessConsultations(directory=tmp_path/'jobs',saver=None,grants=[],tid='t',rid='new',
        check=lambda:None,scope=lambda:None,budget=SimpleNamespace(owner='o',budget='b',store=SimpleNamespace(connection=connection)),
        environment={},model='gpt-6.1-sol',basis={},as_of='2026-11-06',public_sink=lambda x:None)
    record={'error_type':'ConnectError','scope':'t:old'}
    assert not service.authorized_provider_failure('key',record,None)
    assert not service.authorized_provider_failure('key',record,{'unknown_call_ids':['other']})
    permit={'unknown_call_ids':['failed']}
    assert service.authorized_provider_failure('key',record,permit)
    for status in ('dispatched','reserved','received'):
        rows[1]['status']=status
        assert not service.authorized_provider_failure('key',record,permit)
    rows[1]['status']='unknown'
    rows[0]['response']['stop_required']=True
    assert not service.authorized_provider_failure('key',record,permit)


@pytest.mark.anyio
async def test_explicit_settled_dispatch_recovery_rechecks_gate_and_preserves_history(tmp_path, monkeypatch):
    from contextlib import contextmanager, nullcontext
    from sec_agent.adapters.model_dispatch_store import DispatchBlocked
    funded = False
    attempts = []
    rows = [dict(status='received', actual_micros=10, response={'stop_required':False})]
    @contextmanager
    def connection():
        yield SimpleNamespace(execute=lambda *a:SimpleNamespace(fetchall=lambda:rows))
    async def provider(**kwargs):
        attempts.append(kwargs)
        if not funded:
            raise DispatchBlocked('research_budget_exhausted_delivery_reserve_preserved')
        return 'Completed from saved responses and observations'
    monkeypatch.setattr('sec_agent.agent_runtime.harness_consultations.independent_review',provider)
    monkeypatch.setattr('sec_agent.adapters.explicit_run_recovery.verified_permit',lambda *a,**k:None)
    async with AsyncSqliteSaver.from_conn_string(str(tmp_path/'state.sqlite')) as saver:
        service=HarnessConsultations(directory=tmp_path/'jobs',saver=saver,grants=[],tid='t',rid='old',
            check=lambda:None,scope=nullcontext,
            budget=SimpleNamespace(owner='o',budget='b',store=SimpleNamespace(connection=connection)),
            environment={'FINSIGHT_ORGANIZATION_RUNTIME_SECRET':'fixture'},model='gpt-6.1-sol',basis={},
            as_of='2026-11-06',public_sink=lambda x:None)
        out=await service.submit('Original question','Original context','review',False,[],{'messages':[]})
        key=out['task_id']; path=tmp_path/'jobs'/(key+'.json')
        with pytest.raises(DispatchBlocked):
            await service.tasks[key]
        original=json.loads(path.read_text())
        assert original['failure_code']=='research_budget_exhausted_delivery_reserve_preserved'
        assert len(attempts)==1
        service.rid='still-unfunded'
        await service.recover_cancelled('old',tmp_path/'audit')
        with pytest.raises(DispatchBlocked):
            await service.tasks[key]
        assert json.loads((tmp_path/'jobs'/'history'/key/'old.json').read_text())==original
        assert json.loads(path.read_text())['status']=='failed'
        funded=True;service.rid='funded'
        await service.recover_cancelled('still-unfunded',tmp_path/'audit')
        await service.tasks[key]
        current=json.loads(path.read_text())
        assert current['status']=='completed' and current['request']==original['request']
        assert attempts[-1]['previous_scope']=='t:still-unfunded'
        assert len(attempts)==3
        await service.close()


@pytest.mark.anyio
async def test_transport_recovery_preserves_request_and_failed_record(tmp_path, monkeypatch):
    import httpx
    from contextlib import contextmanager, nullcontext
    rows=[dict(call_id='failed',status='unknown',actual_micros=None,response=None)]
    @contextmanager
    def connection():
        yield SimpleNamespace(execute=lambda *a:SimpleNamespace(fetchall=lambda:rows))
    budget=SimpleNamespace(owner='o',budget='b',store=SimpleNamespace(connection=connection))
    calls=[]
    async def provider(**kw):
        calls.append(kw)
        if len(calls)==1: raise httpx.ConnectError('fixture')
        return 'Independent result'
    monkeypatch.setattr('sec_agent.agent_runtime.harness_consultations.independent_review',provider)
    monkeypatch.setattr('sec_agent.adapters.explicit_run_recovery.verified_permit',lambda *a,**kw:{'unknown_call_ids':['failed']})
    async with AsyncSqliteSaver.from_conn_string(str(tmp_path/'s.sqlite')) as saver:
        def service(rid):
            return HarnessConsultations(directory=tmp_path/'jobs',saver=saver,grants=[],tid='t',rid=rid,
                check=lambda:None,scope=nullcontext,budget=budget,
                environment={'FINSIGHT_ORGANIZATION_RUNTIME_SECRET':'fixture'},model='gpt-6.1-sol',basis={},
                as_of='2026-11-06',public_sink=lambda x:None)
        first=service('old')
        result=await first.submit('Original question','Original context','investigate',False,[],{'messages':[]})
        key=result['task_id']
        with pytest.raises(httpx.ConnectError): await first.tasks[key]
        await first.close()
        second=service('new')
        await second.recover_cancelled('old',tmp_path/'audit')
        await second.tasks[key]
        assert calls[1]['question']==calls[0]['question']
        assert calls[1]['previous_scope']=='t:old'
        assert json.loads((tmp_path/'jobs'/'history'/key/'old.json').read_text())['error_type']=='ConnectError'
        assert rows[0]['status']=='unknown' and rows[0]['actual_micros'] is None
        await second.close()


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
