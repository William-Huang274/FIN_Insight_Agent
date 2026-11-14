import pytest
import json
from scripts.engineering.replay_research_handoffs import replay


@pytest.mark.anyio
async def test_actual_tools_three_level_handoff_and_authoring(tmp_path):
    result=await replay(tmp_path)
    assert all(result['checks'].values())
    assert result['completion_order'][0]=='供应商竞争'
    assert result['first_handoff_characters']<result['full_competitor_body_characters']
    assert (tmp_path/'replay.html').is_file()


@pytest.fixture
def anyio_backend():
    return 'asyncio'


@pytest.mark.anyio
async def test_report_delivery_requires_actual_current_research_binding(tmp_path):
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
    from sec_agent.agent_runtime.harness_artifact_tools import artifact_tools
    from sec_agent.agent_runtime.harness_business_tools import HarnessBusinessTools
    from sec_agent.agent_runtime.research_workpapers import ResearchWorkpapers
    from sec_agent.agent_runtime.research_workpaper_tools import workpaper_tools
    from sec_agent.agent_runtime.working_memory import WorkingMemory
    from scripts.engineering.replay_research_handoffs import paper
    from test_on_demand_research import artifact_fixture, report
    sources=artifact_fixture()
    workspace=ResearchWorkpapers(tmp_path/'research.sqlite',root_id='task',question='Task',as_of='2026-11-14',check=lambda:None)
    memory=WorkingMemory(tmp_path/'notes.sqlite',owner='owner',workspace='task',actor='lead')
    grants=artifact_tools(artifacts=lambda _:sources,memory=memory,delivery_intent='report',require_review=False,research_workspace=workspace)+workpaper_tools(workspace)
    async with AsyncSqliteSaver.from_conn_string(str(tmp_path/'tools.sqlite')) as saver:
        bridge=HarnessBusinessTools(grants=grants,checkpointer=saver,thread_id='task',check=lambda:None)
        await bridge.initialize({'question':'Task','messages':[]})
        candidate={k:v for k,v in report(sources).items() if k!='citations'}
        assert (await bridge.execute('save_research_report',{'report':candidate,'base_version':0})).status=='success'
        assert (await bridge.execute('publish_research_workpaper',{'base_revision':0,'workpaper':paper('Current research')})).status=='success'
        rejected=await bridge.execute('deliver_current_report',{'version':1})
        assert json.loads(rejected.content)['error']=='bind_current_report_to_research_snapshot'
        assert not (await bridge.state()).get('delivery')
        frozen=json.loads((await bridge.execute('prepare_research_synthesis',{'topic_ids':['root'],'scope_rationale':'Covers the fictional task'})).content)
        args={'snapshot_id':frozen['snapshot_id'],'report_version':1}
        early=await bridge.execute('bind_research_synthesis',args)
        assert json.loads(early.content)['error']=='read_selected_argument_before_delivery'
        await bridge.execute('read_synthesis_material',{'snapshot_id':frozen['snapshot_id'],'topic_id':'root'})
        assert json.loads((await bridge.execute('bind_research_synthesis',args)).content)['bound']
        delivered=await bridge.execute('deliver_current_report',{'version':1})
        assert delivered.status=='success' and (await bridge.state())['delivery']
        await bridge.begin_command('continue')
        await bridge.execute('publish_research_workpaper',{'base_revision':1,'workpaper':paper('Changed research')})
        late=await bridge.execute('deliver_current_report',{'version':1})
        assert json.loads(late.content)['error']=='research_changed_refresh_synthesis'
        assert not (await bridge.state()).get('delivery')


@pytest.mark.anyio
async def test_restored_unfinished_nested_job_is_not_silently_cleared(tmp_path):
    from contextlib import nullcontext
    from sec_agent.agent_runtime.harness_consultations import HarnessConsultations
    service=HarnessConsultations(directory=tmp_path,saver=None,grants=[],tid='t',rid='r',
        check=lambda:None,scope=nullcontext,budget=object(),environment={},model='fixture',basis={},as_of='2026-11-14',public_sink=None)
    path=tmp_path/('a'*64+'.json')
    path.write_text(json.dumps({'status':'failed','scope':'t:old','request':{}}))
    with pytest.raises(RuntimeError,match='unfinished_persisted'):
        await service.ensure_finished()
    assert not service.tasks  # No automatic paid retry.


@pytest.mark.anyio
async def test_nested_cancel_recovery_preserves_jobs_and_sources(tmp_path,monkeypatch):
    import asyncio
    from contextlib import nullcontext
    from langchain_core.tools import tool
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
    from sec_agent.agent_runtime.conversation_agent import GrantedTool
    from sec_agent.agent_runtime.harness_consultations import HarnessConsultations
    from sec_agent.agent_runtime.harness_business_tools import HarnessBusinessTools
    from sec_agent.agent_runtime.research_workpapers import ResearchWorkpapers
    from scripts.engineering.replay_research_handoffs import paper
    gate=asyncio.Event(); entered=asyncio.Event(); reads=[]; invocations=[]
    @tool
    def read_source_document(query:str):
        """Read one fixed fixture."""
        reads.append(query);return {'source_id':'fixture','text':'Exact source remains available'}
    workspace=ResearchWorkpapers(tmp_path/'work.sqlite',root_id='t',question='Root',as_of='2026-11-14',check=lambda:None)
    async def native(**kw):
        bridge=kw['bridge']; request=kw['request']; invocations.append((request['question'],kw['previous_scope']))
        if request['question']=='Topic':
            if not kw['previous_scope']:
                result=await bridge.execute('consult_research_agent',dict(question='Worker',context='Scope',purpose='investigate'))
                child=json.loads(result.content)['task_id']
            else:
                child=next(iter(kw['consultations'].tasks))
            await kw['consultations'].tasks[child]
            await bridge.execute('read_research_agent_result',{'task_id':child})
        else:
            if not kw['previous_scope']:
                await bridge.execute('read_source_document',{'query':'one source'})
            entered.set(); await gate.wait()
        result=await bridge.execute('publish_research_workpaper',{'base_revision':0,'workpaper':paper(request['question'])})
        assert json.loads(result.content)['saved']
        return 'Complete persisted result'
    # This fixture authorizes recovery explicitly. Production still checks its signed permit and ledger.
    monkeypatch.setattr('sec_agent.adapters.explicit_run_recovery.verified_permit',lambda *a,**k:{'unknown_call_ids':[]})
    async with AsyncSqliteSaver.from_conn_string(str(tmp_path/'state.sqlite')) as saver:
        grants=[GrantedTool(read_source_document,'read','fixture')]
        def make(run):
            service=HarnessConsultations(directory=tmp_path/'jobs',saver=saver,grants=grants,tid='t',rid=run,
                check=lambda:None,scope=nullcontext,budget=object(),environment={'FINSIGHT_ORGANIZATION_RUNTIME_SECRET':'fixture'},
                model='fixture',basis={},as_of='2026-11-14',public_sink=None,native_delegate=native,topic_delegate=native,workspace=workspace)
            bridge=HarnessBusinessTools(grants=grants+service.tools(),checkpointer=saver,thread_id='t',check=lambda:None)
            service.parent=bridge;return service,bridge
        first,root=make('old');await root.initialize({'question':'Root','messages':[]})
        result=await root.execute('consult_research_agent',dict(question='Topic',context='Scope',purpose='investigate',topic_lead=True))
        key=json.loads(result.content)['task_id']
        await asyncio.wait_for(entered.wait(),5)
        await first.close()
        assert json.loads((tmp_path/'jobs'/(key+'.json')).read_text())['status']=='failed'
        second,restored=make('new');await restored.initialize({})
        gate.set()
        try:
            await second.recover_cancelled('old',tmp_path/'audit')
            await asyncio.wait_for(second.tasks[key],10)
            await second.ensure_finished()
            assert reads==['one source']
            assert invocations.count(('Topic','t:old'))==1 and invocations.count(('Worker','t:old'))==1
            assert len(list((tmp_path/'jobs').glob('*.json')))==1
        finally:
            await second.close()


@pytest.mark.anyio
async def test_shared_capacity_waits_for_release_without_dispatch_or_wave_barrier(tmp_path):
    import asyncio
    from contextlib import nullcontext
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
    from sec_agent.agent_runtime.harness_consultations import HarnessConsultations
    from sec_agent.agent_runtime.harness_business_tools import HarnessBusinessTools
    events=[asyncio.Event() for _ in range(8)]
    async with AsyncSqliteSaver.from_conn_string(str(tmp_path/'state.sqlite')) as saver:
        service=HarnessConsultations(directory=tmp_path/'jobs',saver=saver,grants=[],tid='t',rid='r',
            check=lambda:None,scope=nullcontext,budget=object(),environment={},model='fixture',basis={},as_of='2026-11-14',public_sink=None)
        bridge=HarnessBusinessTools(grants=service.tools(),checkpointer=saver,thread_id='t',check=lambda:None)
        service.parent=bridge;await bridge.initialize({'question':'Root','messages':[]})
        for index,event in enumerate(events):
            key=str(index)*64
            service.tasks[key]=asyncio.create_task(event.wait())
            (service.directory/(key+'.json')).write_text(json.dumps({'request':{},'status':'running'}))
        try:
            receipt=await bridge.execute('consult_research_agent',dict(question='Next relation',context='Scope',purpose='investigate'))
            assert json.loads(receipt.content)['status']=='capacity_wait'
            assert len(service.tasks)==8
            assert (await service.dispatch_ready(timeout=0))['status']=='waiting'
            events[0].set();await service.tasks['0'*64]
            assert (await service.dispatch_ready(timeout=0))['status']=='ready'
            assert sum(not task.done() for task in service.tasks.values())==7
        finally:
            await service.close()
