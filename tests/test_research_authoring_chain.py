"""Adversarial offline chain checks; assertions concern contracts, not financial truth."""
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest
from langchain_core.messages import ToolMessage
from test_research_authoring import initialized, section
from test_research_workpapers import paper, dep
from sec_agent.agent_runtime.research_authoring import authoring_context_replacements, material_context_replacements
from sec_agent.agent_runtime.research_graph_contracts import canonical_sha256
from sec_agent.agent_runtime.research_workpapers import WorkpaperConflict


def message(key, value, name='read_authoring_context'):
    return ToolMessage(tool_call_id=key,name=name,content=json.dumps(value))


def status(s,report=None):
    with s.connection() as db:
        return {i['id']:i['status'] for i in s.authoring._issues(db,s.authoring._state(db),report)}


def test_prose_regression_reopens_only_related_issue_and_blocks_binding(tmp_path):
    s,*_=initialized(tmp_path)
    initial={'narrative_markdown':'Summary.\n\nCost old.\n\nCompetition old.'}
    fixed={'narrative_markdown':'Summary.\n\nCost revised.\n\nCompetition revised.'}
    for key in ('cost','competition'):
        s.authoring.open_issue(1,dict(id=key,section_ids=[key],kind='expression',question='Correct this claim',quote=f'{key.capitalize()} old.'),initial)
        s.authoring.resolve(key,1,'revised','Updated the affected assertion',[],fixed,
            prose_uses=[dict(section_id=key,excerpt=f'{key.capitalize()} revised.')])
    assert status(s)=={'cost':'resolved','competition':'resolved'}
    changed={**fixed,'narrative_markdown':fixed['narrative_markdown'].replace('Cost revised.','Cost old.')}
    assert status(s,changed)=={'cost':'open','competition':'resolved'}
    snap=s.prepare('root',['cost','competition'],'Basis')
    with pytest.raises(WorkpaperConflict,match='resolve_authoring'):
        s.bind(snap['snapshot_id'],canonical_sha256(changed),report=changed)
    unrelated={**fixed,'narrative_markdown':fixed['narrative_markdown']+'\n\nUnrelated appendix.'}
    assert set(status(s,unrelated).values())=={'resolved'}
    s.authoring.observe_report(changed)
    assert initialized_store(s).authoring.context()['issues'][0]['id']=='cost'


def initialized_store(s):
    from sec_agent.agent_runtime.research_workpapers import ResearchWorkpapers
    return ResearchWorkpapers(s.path,root_id='authorized-root',question='AI procurement outlook',as_of='2026-11-14',check=lambda:None)


def test_incremental_invalidation_and_notifications(tmp_path):
    s,*_=initialized(tmp_path)
    report={'narrative_markdown':'Cost resolved.'}
    s.authoring.open_issue(1,dict(id='cost',section_ids=['cost'],kind='expression',question='Unit?',quote='Cost resolved.'),report)
    s.authoring.resolve('cost',1,'retained','Unit is already defined',[],report)
    snap=s.prepare('root',['cost','competition'],'Basis')
    cursor=s.catalog(limit=20)['next_cursor']
    no_op=s.authoring.update(1,{'reason':'No change'},'noop')
    assert no_op['unchanged'] and no_op['revision']==1
    s.authoring.update(1,dict(reason='Reorder',sections=[section('cost',['cost'],99)]),'order')
    assert not s.snapshot(snap['snapshot_id'])['understanding_changed']
    assert status(s)['cost']=='resolved'
    s.register('optional','root','An unadopted lead');s.publish('optional',0,paper(),{},'optional')
    view=s.snapshot(snap['snapshot_id'])
    assert not view['changed_topics'] and view['unselected_updates']==['optional']
    update=s.catalog(after=cursor)
    assert [t['topic_id'] for t in update['topics']]==['optional']
    assert len(s.catalog(after=cursor,include_catalog=True)['topics'])==4
    s.publish('cost',1,paper('New cost premise'),{},'changed')
    assert s.snapshot(snap['snapshot_id'])['changed_topics']==['cost']


def test_scoped_context_has_short_thesis_and_explicit_history(tmp_path):
    s,cost,competition,thesis=initialized(tmp_path)
    competition['rationale']='Unrelated complete reasoning. '*180
    thesis['depends_on']=['cost','competition']
    s.authoring.update(1,dict(reason='Two branch comparison',judgments=[competition,thesis]),'both')
    local=s.authoring.context(['cost']);whole=s.authoring.context()
    assert set(local['judgments'])=={'cost'}
    assert set(local['lead_overview'])=={'thesis'}
    assert [r['topic_id'] for r in local['materials']]==['cost']
    assert len(json.dumps(local))<len(json.dumps(whole))*.5
    assert local['lead_overview']['thesis']['conditions']==thesis['conditions']
    review=s.authoring.review_handoff()
    assert review['lead_judgments']['thesis']['depends_on']==['cost','competition']
    assert 'rationale' in review['changed_judgments']['competition']
    assert review['readback']['arguments']['revision']==2


def test_live_surface_replacement_restore_and_identical_dedup(tmp_path):
    s,*_=initialized(tmp_path);old=s.authoring.context(['cost'])
    s.authoring.update(1,dict(reason='Order',sections=[section('cost',['cost'],3)]),'o')
    current=s.authoring.context(['cost'])
    messages=[message('old',old),message('new',current),message('again',current)]
    assert not authoring_context_replacements(messages,[{'receipt_id':'old'}],current)
    replacements=authoring_context_replacements(messages,[{'receipt_id':k} for k in ('old','new','again')],current)
    assert {r['receipt_id'] for r in replacements}=={'old','new'}
    assert all(r['receipt']['result']['current_view_receipt_id']=='again' for r in replacements)
    restored=authoring_context_replacements(messages,[{'receipt_id':'old','retired':True}],current)
    assert restored[0]['receipt']['result']['judgments']==old['judgments']
    assert replacements[0]['receipt']['result']['original_readback']['tool']=='read_saved_result'
    s.authoring.update(2,dict(reason='Remove provisional section',remove_sections=['cost']),'remove')
    removed=authoring_context_replacements(messages,[{'receipt_id':'old','retired':True}],
        lambda sections,history:s.authoring.context(sections,include_history=history))
    assert removed[0]['receipt']['result']['judgments']==old['judgments']


def test_material_windows_dedup_restore_identity_and_pairing(tmp_path):
    s,*_=initialized(tmp_path)
    def read(offset=0,length=24000,rev=1):
        value=s.read('root','cost',rev,offset=offset,max_characters=length)
        return {**value,'result_digest':canonical_sha256(value)}
    full=read();length=len(full['body']);half=length//2
    a,b=read(0,half),read(half,length-half)
    messages=[message('full',full,'read_research_workpaper'),message('a',a,'read_synthesis_material'),message('b',b,'read_synthesis_material')]
    candidates=[{'receipt_id':k} for k in ('full','a','b')]
    replacement=material_context_replacements(messages,candidates)
    assert len(replacement)==1 and replacement[0]['receipt_id']=='full'
    assert replacement[0]['receipt']['result']['active_window_receipts']==['a','b']
    assert not material_context_replacements(messages,[{'receipt_id':'full'},{'receipt_id':'a'}])
    restored=material_context_replacements(messages,[{'receipt_id':'full','retired':True,'context_state':'duplicate_material_window'},{'receipt_id':'a'}])
    assert restored[0]['receipt']['result']['body']==full['body']
    wrong={**b,'digest':'different-version'}
    assert not material_context_replacements(messages[:2]+[message('b',wrong,'read_synthesis_material')],candidates)
    assert json.loads(messages[0].content)['body']==full['body']


def test_dependency_feedback_carries_actual_delta(tmp_path):
    s,cost,*_=initialized(tmp_path)
    cost['conditions']='Changed review costs'
    s.authoring.update(1,dict(reason='New observed premise',judgments=[cost]),'cost2')
    impact=s.authoring.context()['requires_reassessment']['thesis'][0]
    assert impact['changed_fields']['conditions']=={'before':'Same scope and period','after':'Changed review costs'}


def test_parallel_branch_publication_and_recovery_preserve_unaffected_basis(tmp_path):
    s,cost,competition,thesis=initialized(tmp_path)
    frozen=s.prepare('root',['cost','competition'],'Both branches')
    def publish(key):
        return s.publish(key,1,paper('Changed '+key),{},'parallel-'+key)
    with ThreadPoolExecutor(2) as pool:
        results=list(pool.map(publish,['cost','competition']))
    assert {r['topic_id'] for r in results}=={'cost','competition'}
    restored=initialized_store(s)
    assert set(restored.snapshot(frozen['snapshot_id'])['changed_topics'])=={'cost','competition'}
    cost['workpapers']=[dep(restored,'root','cost')]
    competition['workpapers']=[dep(restored,'root','competition')]
    restored.authoring.update(1,dict(reason='Adopt both exact current papers',judgments=[cost,competition]),'adopt')
    assert set(restored.authoring.context()['requires_reassessment'])=={'thesis'}
    restored.authoring.update(2,dict(reason='Reassess the same thesis against new basis',judgments=[thesis]),'thesis')
    assert not restored.authoring.context()['requires_reassessment']
    assert restored.read('root','cost',1)['finding']=='cost'


@pytest.mark.anyio
async def test_full_adversarial_replay(tmp_path):
    from scripts.engineering.replay_authoring_chain import run
    result=await run(tmp_path)
    assert len(result['checks'])>=24 and all(result['checks'].values())
    assert result['paid_model_calls']==0


@pytest.mark.anyio
async def test_direct_investigation_uses_real_tool_receipts_and_rejects_invented(tmp_path):
    from langchain_core.tools import tool
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
    from sec_agent.agent_runtime.conversation_agent import GrantedTool
    from sec_agent.agent_runtime.harness_business_tools import HarnessBusinessTools
    from sec_agent.agent_runtime.research_workpaper_tools import workpaper_tools
    s,*_=initialized(tmp_path)
    @tool
    def read_source_document(query: str):
        """Synthetic successful primary read."""
        return {'text':'Observed source','query':query}
    report={'narrative_markdown':'Cost condition.'}
    s.authoring.open_issue(1,dict(id='gap',section_ids=['cost'],kind='missing_link',question='Check the mechanism',quote='Cost condition.'),report)
    async with AsyncSqliteSaver.from_conn_string(str(tmp_path/'state.sqlite')) as saver:
        root=HarnessBusinessTools(checkpointer=saver,grants=[GrantedTool(read_source_document,'read','fixture'),*workpaper_tools(s)],
            thread_id='root',check=lambda:None)
        await root.initialize({'question':'Test','messages':[],'report':report,'report_version':1})
        args=dict(issue_id='gap',base_revision=1,disposition='retained',explanation='Direct source resolves the relationship',result_workpapers=[],report_version=1)
        bad=await root.execute('resolve_authoring_issue',{**args,'evidence_receipt_ids':['invented']})
        assert 'successfully_observed' in json.loads(bad.content)['error']
        source=await root.execute('read_source_document',{'query':'Own investigation'})
        good=await root.execute('resolve_authoring_issue',{**args,'evidence_receipt_ids':[source.tool_call_id],
            'prose_uses':[dict(section_id='cost',excerpt='Cost condition.')]})
        assert json.loads(good.content)['saved']
        assert status(s)['gap']=='resolved'
        assert s.evidence(source.tool_call_id)['data']['tool_call_id']==source.tool_call_id


@pytest.fixture
def anyio_backend():return 'asyncio'


@pytest.mark.anyio
async def test_review_native_input_and_repeated_request_are_version_bound(tmp_path):
    from contextlib import nullcontext
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
    from sec_agent.agent_runtime.harness_business_tools import HarnessBusinessTools
    from sec_agent.agent_runtime.harness_consultations import HarnessConsultations
    from sec_agent.agent_runtime.harness_delegate import delegation_payload
    s,*_=initialized(tmp_path);calls=[]
    async def native(**kwargs):
        request=kwargs['request'];bridge=kwargs['bridge'];calls.append(delegation_payload(request))
        assert 'read_authoring_context' in bridge.tools and 'update_research_understanding' not in bridge.tools
        view=await bridge.execute('read_authoring_context',{'revision':request['current_understanding']['understanding_revision']})
        assert json.loads(view.content)['lead_judgment_ids']==['thesis']
        await bridge.execute('publish_research_workpaper',{'base_revision':0,'workpaper':paper('Synthetic review of current explanation')})
        return 'Review finding saved.'
    async with AsyncSqliteSaver.from_conn_string(str(tmp_path/'review.sqlite')) as saver:
        service=HarnessConsultations(directory=tmp_path/'jobs',saver=saver,grants=[],tid='review',rid='one',
            check=lambda:None,scope=nullcontext,budget=object(),environment={},model='fixture',basis={},as_of='2026-11-14',
            public_sink=lambda _:None,research_question='Independent original scope',native_delegate=native,workspace=s)
        root=HarnessBusinessTools(grants=service.tools(),checkpointer=saver,thread_id='review',check=lambda:None)
        service.parent=root
        await root.initialize({'question':'Original','messages':[],'report':{'narrative_markdown':'Actual current prose'},'report_version':1})
        args=dict(question='Review current explanation',context='Challenge assumptions',purpose='review',use_current_report=True)
        first=json.loads((await root.execute('consult_research_agent',args)).content)
        await service.tasks[first['task_id']]
        second=json.loads((await root.execute('consult_research_agent',args)).content)
        assert second['reused'] and second['task_id']==first['task_id'] and len(calls)==1
        assert calls[0]['research_task']['question']=='Independent original scope'
        assert calls[0]['report']['narrative_markdown']=='Actual current prose'
        assert calls[0]['current_understanding']['lead_judgments']['thesis']['depends_on']==['cost']
        await service.ensure_finished();await service.close()
