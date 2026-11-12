"""Research judgments remain model-owned; journal/identity checks are deterministic."""
import json
from contextlib import nullcontext

import pytest
from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from sec_agent.agent_runtime.conversation_agent import GrantedTool
from sec_agent.agent_runtime.harness_business_tools import HarnessBusinessTools
from sec_agent.agent_runtime.harness_consultations import HarnessConsultations
from sec_agent.agent_runtime.harness_artifact_tools import artifact_tools
from sec_agent.agent_runtime.research_actions import research_action_view


@pytest.fixture
def anyio_backend():
    return 'asyncio'


@pytest.mark.anyio
async def test_model_action_survives_import_restart_and_drives_version_bound_disposition(tmp_path, monkeypatch):
    from test_on_demand_research import artifact_fixture, report
    artifacts = artifact_fixture()
    candidate = {k:v for k,v in report(artifacts).items() if k!='citations'}
    observed = []

    @tool
    def read_source_document(query: str):
        """Read an authorized source."""
        return {'text':'Two customer cohorts have opposite renewal outcomes.'}

    async def provider(**kwargs):
        observed.append(kwargs)
        child = kwargs['bridge']
        assert 'record_research_assessment' in child.tools
        assert 'respond_research_action' not in child.tools
        assert 'save_research_report' not in child.tools
        if len(observed) > 1:
            inherited = [m for m in (await child.state())['messages']
                         if m.name == 'respond_research_action' and json.loads(m.content).get('recorded')]
            assert len(inherited) == 1
            read = await child.execute('read_saved_result', {'tool_call_id': inherited[0].tool_call_id})
            audit = json.loads(read.content)
            assert audit['source_evidence'] is False
            assert json.loads(audit['content'])['rationale'].startswith('Model explains')
        evidence = await child.execute('read_source_document', {'query':'Model selected cohort comparison'})
        receipt = await child.execute('record_research_assessment', {
            'finding':'The observed large cohort renews; the small cohort remains unmeasured.',
            'scope_explanation':'The original question concerns several business models; the current evidence covers one.',
            'actions':[{'question_or_claim':'All customers renew', 'gap':'Only one cohort observed',
                'consequence':'Retention and market size could change', 'next_action':'Compare renewal outcomes or narrow the population'}]})
        assert json.loads(receipt.content)['recorded']
        return 'Model-authored objection; evidence '+evidence.tool_call_id

    monkeypatch.setattr('sec_agent.agent_runtime.harness_consultations.independent_review', provider)
    source_grants = [GrantedTool(read_source_document,'read','source')]
    from sec_agent.agent_runtime.conversation_tools import conversation_tools
    source_grants += [g for g in conversation_tools(thread_id='t') if g.tool.name == 'read_saved_result']
    art_grants = artifact_tools(artifacts=lambda _:artifacts,memory=None,delivery_intent='report',require_review=False)
    db = str(tmp_path/'state.sqlite')
    async with AsyncSqliteSaver.from_conn_string(db) as saver:
        service = HarnessConsultations(directory=tmp_path/'jobs',saver=saver,grants=source_grants,
            tid='t',rid='r',check=lambda:None,scope=nullcontext,budget=object(),environment={},
            model='fixture',basis={},as_of='2026-11-09',public_sink=None,research_question='Global adoption and business models')
        bridge = HarnessBusinessTools(grants=source_grants+art_grants+service.tools(),
            checkpointer=saver,thread_id='t',check=lambda:None)
        service.parent = bridge
        await bridge.initialize({'question':'Author summary', 'messages':[]})
        saved = await bridge.execute('save_research_report',{'report':candidate,'base_version':0})
        assert json.loads(saved.content)['saved']
        args = {'question':'Review main conclusion','context':'Consider coverage','purpose':'review','use_current_report':True}
        receipt = await bridge.execute('consult_research_agent',args)
        key = json.loads(receipt.content)['task_id']
        await service.tasks[key]
        got = await bridge.execute('read_research_agent_result',{'task_id':key})
        imported = json.loads(got.content)
        assert imported['assessment']['scope_explanation'].startswith('The original')
        assert imported['assessment']['finding'].startswith('The observed')
        issue = imported['assessment']['actions'][0]['action_id']
        assert observed[0]['research_task']['question']=='Global adoption and business models'
        assert research_action_view(await bridge.state())['pending_material']==[issue]

        context = await bridge.execute('read_current_report', {'field':'synthesis_context','max_characters':12000})
        working = json.loads(json.loads(context.content)['text'])
        assert working['report_version']==1
        assert working['current_research']['investigations'][0]['finding'].startswith('The observed')
        assert working['research_actions']['awaiting_independent_resolution']==[issue]
        assert working['research_actions']['actions'][0]['review_readback']['arguments']['tool_call_id']==got.tool_call_id
        # Reading again imports no duplicate obligations and dispatches no model.
        await bridge.execute('read_research_agent_result',{'task_id':key})
        await bridge.execute('consult_research_agent',args)
        assert len(observed)==1
        assert len(research_action_view(await bridge.state())['actions'])==1
        stopped = await bridge.execute('deliver_current_report',{'version':1})
        assert stopped.status=='success' and json.loads(stopped.content)['delivered'] is False
        assert not (await bridge.state()).get('delivery') and not bridge.failed_receipt
        await service.close()

    async with AsyncSqliteSaver.from_conn_string(db) as saver:
        bridge = HarnessBusinessTools(grants=source_grants+art_grants,checkpointer=saver,thread_id='t',check=lambda:None)
        await bridge.initialize({})
        state = await bridge.state()
        assert research_action_view(state)['pending_material']==[issue]
        evidence = [m.tool_call_id for m in state['messages'] if getattr(m,'name',None)=='read_source_document']
        response = {'action_id':issue,'disposition':'rebutted','rationale':'Model explains why the cited evidence supports its scope',
            'current_quote':candidate['narrative_markdown'],'evidence_receipts':['not-a-receipt'],'report_version':1}
        rejected = await bridge.execute('respond_research_action',response)
        assert not json.loads(rejected.content)['recorded'] and rejected.status=='success'
        response['evidence_receipts']=evidence
        rejected = await bridge.execute('respond_research_action',{**response,'current_quote':'Proposed wording never saved'})
        assert not json.loads(rejected.content)['recorded']
        accepted = await bridge.execute('respond_research_action',response)
        assert json.loads(accepted.content)['recorded']
        # Reviewer can read the original audit without author's write tools.
        service.parent, service.saver = bridge, saver
        second = await service.submit(question='Review replacement', context='Current argument',
                                      purpose='review', use_report=True, methods=[], state=await bridge.state())
        await service.tasks[second['task_id']]
        assert len(observed) == 2
        delivered = await bridge.execute('deliver_current_report',{'version':1})
        assert json.loads(delivered.content)['research_action_status']['independent_clearance'] is False
        assert json.loads(delivered.content)['research_action_status']['awaiting_independent_resolution']==[issue]
        # A model can give a bad rebuttal: the host only verified its identity.
        # Any changed report invalidates the old response, never silently clears it.
        await bridge.execute('repair_report_fields',{'fields':{'title':'A changed current title'},'base_version':1})
        blocked = await bridge.execute('deliver_current_report',{'version':2})
        assert json.loads(blocked.content)['status']=='research_actions_need_disposition'
        assert research_action_view(await bridge.state())['pending_material']==[issue]


def test_legacy_opinion_and_unimported_child_record_never_become_scope_approval():
    old = ToolMessage(name='read_research_agent_result',tool_call_id='old',content=json.dumps({
        'task_id':'legacy','status':'completed','purpose':'review','opinion':'No errors found'}))
    child = ToolMessage(name='record_research_assessment',tool_call_id='child',content=json.dumps({
        'recorded':True,'task_id':'unimported','actions':[{'action_id':'not-imported','material':True}]}))
    view = research_action_view({'messages':[old,child]})
    assert not view['actions'] and not view['pending_material']
    assert len(view['unstructured_results'])==1
    assert view['coverage']=='recorded_model_issues_only_not_exhaustive'


def test_imported_empty_assessment_does_not_manufacture_work():
    msg = ToolMessage(name='read_research_agent_result',tool_call_id='read',content=json.dumps({
        'task_id':'review','status':'completed','assessment':{'scope_explanation':'Evidence fits the limited question','actions':[]}}))
    view = research_action_view({'messages':[msg]})
    assert not view['actions'] and not view['pending_material'] and not view['unstructured_results']


@pytest.mark.anyio
async def test_review_can_retire_known_old_action_without_automatic_semantic_approval(tmp_path):
    from sec_agent.agent_runtime.research_actions import assessment_tool
    action={'action_id':'old:issue','question_or_claim':'Claim','gap':'Gap',
            'consequence':'Could change conclusion','next_action':'Check evidence','material':True}
    old=ToolMessage(name='read_research_agent_result',tool_call_id='old',content=json.dumps({
        'task_id':'old','status':'completed','assessment':{'actions':[action]}}))
    grant=assessment_tool('new',{'purpose':'review','report':{'title':'Current','narrative_markdown':'Current evidence'}},[action])
    async with AsyncSqliteSaver.from_conn_string(str(tmp_path/'review.sqlite')) as saver:
        bridge=HarnessBusinessTools(grants=[grant],checkpointer=saver,thread_id='review',check=lambda:None)
        assert 'record_research_assessment' in bridge.checkpoint_only
        await bridge.initialize({'messages':[]})
        args={'scope_explanation':'Checked the new evidence and actual current wording',
              'actions':[],'resolved_action_ids':['unknown']}
        wrong=await bridge.execute('record_research_assessment',args)
        assert not json.loads(wrong.content)['recorded']
        got=await bridge.execute('record_research_assessment',{**args,'resolved_action_ids':['old:issue']})
        assessment=json.loads(got.content)
        imported=ToolMessage(name='read_research_agent_result',tool_call_id='new',content=json.dumps({
            'task_id':'new','status':'completed','assessment':assessment,'reviewed_report_digest':assessment['reviewed_report_digest']}))
        current={'title':'Current','narrative_markdown':'Current evidence'}
        view=research_action_view({'messages':[old,imported],'report':current})
        assert not view['pending_material']
        assert not view['awaiting_independent_resolution']
        assert view['actions'][0]['reviewer_resolution']['status']=='reviewer_reported_resolved_not_runtime_certification'
        changed=research_action_view({'messages':[old,imported],
            'report':{**current,'title':'A stronger replacement claim'}})
        assert changed['pending_material']==['old:issue']
        assert changed['awaiting_independent_resolution']==['old:issue']
        assert not changed['actions'][0]['resolution_current']
        assert changed['actions'][0]['reviewer_resolution']  # history retained


def test_worked_methods_are_selectable_and_catalog_discloses_them():
    from sec_agent.research_foundation.research_methods import get_research_method, select_method_section, METHOD_TOOL_GUIDANCE
    method = get_research_method('industry_product')
    section = '从生成成本到价值归属：完整调查例题'
    selected = select_method_section(method, section)['content']
    assert '教学假设' in selected and '13.3%' in selected
    assert '## 执行顺序' not in selected
    assert section in METHOD_TOOL_GUIDANCE


def test_working_view_keeps_current_note_identity_without_copying_body_or_grading_repetition():
    from langchain_core.messages import AIMessage
    from sec_agent.agent_runtime.research_actions import synthesis_working_view
    def call(key, name, args):
        return AIMessage(content='', tool_calls=[{'id':key,'name':name,'args':args}])
    def result(key, name, value):
        return ToolMessage(name=name, tool_call_id=key, content=json.dumps(value))
    messages = [call('n1','WriteWorkingNote',{'title':'Customer renewal','body':'Old claim'}),
        result('n1','WriteWorkingNote',{'saved':True,'note_id':'stable','version':1}),
        call('n2','WriteWorkingNote',{'title':'Customer renewal','body':'Current narrower claim'}),
        result('n2','WriteWorkingNote',{'saved':True,'note_id':'stable','version':2}),
        call('n3','WriteWorkingNote',{'title':'Customer renewal','body':'Unsaved claim'}),
        result('n3','WriteWorkingNote',{'saved':False,'note_id':'stable','current_version':2})]
    for key, offset in [('s1',0),('s2',0),('s3',6000)]:
        messages += [call(key,'read_public_source',{'source_id':'original','offset':offset}),
            result(key,'read_public_source',{'text':'Exact source'})]
    view = synthesis_working_view({'question':'Investment decision','messages':messages})
    current = view['current_research']
    assert view['report_version']==0  # useful before a report exists
    assert len(current['working_notes'])==1
    note = current['working_notes'][0]
    assert note['observed_version']==2 and note['title']=='Customer renewal'
    assert note['readback']['arguments']=={'note_id':'stable'}  # current scoped read, not stale version
    assert 'Old claim' not in json.dumps(view) and 'Unsaved claim' not in json.dumps(view)
    assert current['repeated_observations']==[{'tool':'read_public_source','receipt_ids':['s1','s2']}]
    assert 'adequacy' in current['progress_interpretation']
    assert 'stop' not in current and 'quality_pass' not in current


def test_reviewer_has_read_only_note_access_and_forward_method_entry():
    from sec_agent.agent_runtime.answer_review_provider import review_tool_names
    from sec_agent.research_foundation.research_methods import get_research_method, METHOD_TOOL_GUIDANCE
    names = review_tool_names(['ReadWorkingNote','SearchWorkingNotes','WriteWorkingNote','save_research_report'])
    assert names==('ReadWorkingNote','SearchWorkingNotes')
    for method, section in [('research_loop','从核心发现到交叉验证'),
                            ('scenario_sensitivity','从公开事实到前瞻判断')]:
        assert section in METHOD_TOOL_GUIDANCE
        chapter = get_research_method(method, section)
        assert '教学假设' in chapter['content']
