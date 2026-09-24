"""Pre-research provenance and stopping tests; no financial-quality assertion."""
import json

import httpx
import pytest
from pydantic import SecretStr

from sec_agent.agent_runtime.lead_research_graph import build_lead_research_graph
from sec_agent.agent_runtime.specialist_graph import SpecialistAgenticInput
from sec_agent.agent_runtime.research_orientation import SubmitResearchOrientationAction, bind_orientation
from sec_agent.agent_runtime.research_orientation import OrientationLibraryReadAction
from sec_agent.agent_runtime.deepseek_structured_agents import DeepSeekStructuredAgentAdapter, ReasoningPreservingChatDeepSeek
from test_specialist_graph import _input
from test_deepseek_structured_agents import _config


def submission(ref='O1'):
    return dict(reason_summary='形成了可追溯的初步认识。', disposition='ready_for_topic_design',
        overview='测试初步认识，不作财务结论。',
        findings=[dict(finding_id='F1', judgment='测试材料中披露了一个待核项目。', kind='observation',
                       read_refs=[ref], unresolved='实际履约仍需核查。')],
        topics=[dict(topic_id='T1', question='该项目当前处于什么阶段？', why_now='项目的履约阶段影响对总题的判断。',
                     finding_ids=['F1'], professional_roles=['项目财务'], source_dimensions=['D4'],
                     next_evidence='项目合同与进度原件。', success_criteria=['区分承诺和履约。'],
                     activation='next_wave', depends_on=[], activation_reason='先核定供电承诺状态。',
                     revisit_when='取得合同和接网进度后重新安排下游研究。')],
        scope_map=[dict(question='供电项目是否兑现？', status='planned', topic_ids=['T1'],
                        reason='已有原文可开展研究。', revisit_when='T1返回时复评。'),
                   dict(question='采用与收入是否兑现？', status='needs_discovery', topic_ids=[],
                        reason='还需读取客户与云服务商披露。', revisit_when='补读后形成下一专题。')],
        coverage_and_gaps='其余问题仍需后续研究，不冒充已完成。')


def read_result():
    return {'status': 'success', 'items': [{'result_state': 'source_bound_passage', 'passage': 'Test original.',
            'passage_id': 'PASSAGE::test', 'document_id': 'DOC::test', 'content_sha256': 'f'*64}]}


def blocked_submission():
    args = submission()
    args.update(disposition='needs_attention', findings=[], topics=[], scope_map=[dict(
        question='总题资料尚待取得', status='needs_discovery', topic_ids=[],
        reason='当前来源读取受阻。', revisit_when='资料恢复后重新预研究。')])
    return args


def bind_test_submission(args):
    action = SubmitResearchOrientationAction.model_validate({**args, 'context_digest': 'a'*64})
    return bind_orientation(action, [{'read_ref': 'O1', 'selection': {'operation': 'read'}, 'result': read_result()}])


@pytest.mark.parametrize('problem', [None, 'missing', 'wrong_window', 'invented_quote'])
def test_current_citations_bind_exact_window_and_verbatim_text(problem):
    args = submission()
    span = dict(read_ref='O1', passage_id='PASSAGE::test', quote='Test\n original.')
    if problem == 'wrong_window': span['passage_id'] = 'PASSAGE::other'
    if problem == 'invented_quote': span['quote'] = 'Test original with 2300 GW.'
    args['findings'][0]['evidence_spans'] = [] if problem == 'missing' else [span]
    action = SubmitResearchOrientationAction.model_validate({**args, 'context_digest': 'a'*64})
    observations = [{'read_ref': 'O1', 'selection': {'operation': 'read'}, 'result': read_result()},
                    {'read_ref': 'O2', 'selection': {'operation': 'read'}, 'result': {
                        'status': 'success', 'items': [{**read_result()['items'][0],
                            'passage_id': 'PASSAGE::other', 'passage': 'Test original with 2300 GW.'}]}}]
    if problem:
        with pytest.raises(ValueError, match='orientation_evidence_spans|orientation_excerpt'):
            bind_orientation(action, observations, require_evidence_spans=True)
    else:
        assert bind_orientation(action, observations, require_evidence_spans=True)['findings']


def test_one_topic_first_preserves_other_scope_without_fake_evidence():
    result = bind_test_submission(submission())
    assert result['contract_version'] == 'research_orientation.v2'
    assert len(result['topics']) == 1 and len(result['scope_map']) == 2
    assert result['scope_map'][1]['status'] == 'needs_discovery'
    assert result['semantic_acceptance'] == 'not_assessed'


def test_hypothesis_keeps_public_justification_without_fabricating_source_text():
    args = submission()
    args['findings'][0].update(kind='hypothesis', judgment='该项目可能形成后续需求。',
        rationale_summary='原文仅确认项目。一般机制是项目执行带来采购；假设项目未取消，后续查合同。',
        evidence_spans=[dict(read_ref='O1', passage_id='PASSAGE::test', quote='Test original.')])
    action = SubmitResearchOrientationAction.model_validate({**args, 'context_digest': 'a'*64})
    result = bind_orientation(action, [{'read_ref': 'O1', 'selection': {'operation': 'read'},
        'result': read_result()}], require_evidence_spans=True)
    assert result['findings'][0]['rationale_summary'] == args['findings'][0]['rationale_summary']
    assert result['semantic_acceptance'] == 'not_assessed'
    args['findings'][0]['evidence_spans'][0]['quote'] = 'The project has secured orders.'
    with pytest.raises(ValueError, match='orientation_excerpt'):
        bind_orientation(SubmitResearchOrientationAction.model_validate({**args, 'context_digest': 'a'*64}),
            [{'read_ref': 'O1', 'selection': {'operation': 'read'}, 'result': read_result()}],
            require_evidence_spans=True)


def test_resource_deferred_task_has_no_false_dependency_and_preserves_real_handoff():
    args = submission()
    args['topics'].extend([
        {**args['topics'][0], 'topic_id': 'T2', 'activation': 'deferred', 'depends_on': [],
         'activation_reason': '先做最重要问题，空出资源后取证。'},
        {**args['topics'][0], 'topic_id': 'T3', 'activation': 'deferred', 'depends_on': ['T1', 'T2'],
         'dependency_input': 'T1项目时序和T2采购明细均返回后，综合核对期间和重复计数。'}])
    args['scope_map'][0]['topic_ids'] = ['T1', 'T2', 'T3']
    result = bind_test_submission(args)
    assert result['topics'][1]['depends_on'] == []
    assert result['topics'][2]['dependency_input'] == args['topics'][2]['dependency_input']


def test_public_planning_handoff_preserves_claims_excerpts_and_readbacks_not_raw_windows():
    from copy import deepcopy
    from sec_agent.agent_runtime.research_orientation import orientation_public_handoff
    from sec_agent.agent_runtime.research_graph_contracts import canonical_sha256
    artifact = bind_test_submission(submission())
    artifact['findings'][0]['evidence_spans'] = [dict(read_ref='O1', passage_id='PASSAGE::test', quote='Test original.')]
    before = deepcopy(artifact)
    projected = orientation_public_handoff(artifact)
    assert projected['findings'] == artifact['findings']
    assert projected['topics'] == artifact['topics'] and projected['scope_map'] == artifact['scope_map']
    assert projected['source_readbacks']['O1']['passages'][0]['content_sha256'] == 'f'*64
    assert projected['source_readbacks']['O1']['selection'] == {'operation': 'read'}
    assert projected['upstream_artifact_sha256'] == canonical_sha256(artifact)
    assert 'runtime_provenance' not in projected and 'passage' not in projected['source_readbacks']['O1']['passages'][0]
    projected['findings'][0]['judgment'] = 'Changed downstream copy'
    assert artifact == before


def test_deferred_topic_requires_valid_scope_and_acyclic_dependencies():
    args = submission()
    args['topics'].append({**args['topics'][0], 'topic_id': 'T2', 'activation': 'deferred', 'depends_on': ['T1']})
    args['scope_map'][1].update(status='planned', topic_ids=['T2'])
    assert bind_test_submission(args)['topics'][1]['depends_on'] == ['T1']
    args['topics'][0].update(activation='deferred', depends_on=['T2'])
    with pytest.raises(ValueError, match='acyclic'): bind_test_submission(args)


def test_shortened_cross_references_report_all_paths_without_guessing_identity():
    args = submission()
    args['findings'][0]['finding_id'] = 'F1-project-status'
    args['topics'][0].update(topic_id='T1-project', depends_on=['T2'], activation='deferred')
    args['topics'].append({**args['topics'][0], 'topic_id': 'T2-evidence',
                          'depends_on': [], 'activation': 'next_wave'})
    args['scope_map'][0]['topic_ids'] = ['T1', 'T2']
    with pytest.raises(ValueError, match='orientation_invalid_references') as caught:
        bind_test_submission(args)
    details = json.loads(str(caught.value).split(': ', 1)[1])
    assert {e['path'] for e in details['errors']} == {
        'topics[0].finding_ids', 'topics[0].depends_on', 'topics[1].finding_ids', 'scope_map[0].topic_ids'}
    assert details['available_finding_ids'] == ['F1-project-status']
    assert details['available_topic_ids'] == ['T1-project', 'T2-evidence']
    assert args['topics'][0]['finding_ids'] == ['F1']
    for topic in args['topics']: topic['finding_ids'] = ['F1-project-status']
    args['topics'][0]['depends_on'] = ['T2-evidence']
    args['scope_map'][0]['topic_ids'] = ['T1-project', 'T2-evidence']
    assert list(bind_test_submission(args)['topics'][0]['depends_on']) == ['T2-evidence']


@pytest.mark.parametrize('problem', ['unknown_dependency', 'early_activation', 'unknown_topic', 'orphan_topic', 'no_wave'])
def test_schedule_contract_rejects_unexecutable_or_unmapped_plan(problem):
    args = submission()
    if problem == 'unknown_dependency': args['topics'][0]['depends_on'] = ['absent']
    if problem == 'early_activation': args['topics'][0]['depends_on'] = ['T1']
    if problem == 'unknown_topic': args['scope_map'][0]['topic_ids'] = ['absent']
    if problem == 'orphan_topic': args['scope_map'].pop(0)
    if problem == 'no_wave': args['topics'][0]['activation'] = 'deferred'
    with pytest.raises(ValueError, match='orientation_'): bind_test_submission(args)


def make_graph(model, reader= None, **kwargs):
    data = _input()
    data['l0_context']['capability_summaries'][0]['source_spaces'] = ['library']
    value = SpecialistAgenticInput.model_validate_json(json.dumps(data))
    graph = build_lead_research_graph(expected_input=value, research_question='AI采用与投入怎样兑现？',
        branch_catalog=[{'branch_id': value.task.branch_id}], allowed_branch_ids=(value.task.branch_id,),
        seed_workpapers={}, model_turn=model, run_child=lambda *_: pytest.fail('orientation must never dispatch'),
        orientation_only=True, orientation_context=kwargs.pop('orientation_context', {'catalog_navigation': 'library'}),
        source_reader=reader or (lambda _: read_result()), max_lead_turns=4, **kwargs).compile()
    return graph, value


def call(req, name, args):
    return {'action': {'action': 'native_tool_batch', 'context_digest': req['context_digest'],
        'tool_calls': [{'id': str(req['progress']['turn_index']), 'name': name,
                       'args': {'context_digest': req['context_digest'], **args}}]}}


def test_runtime_enforces_excerpt_binding_and_accepts_corrected_submission():
    turns = []
    def model(req):
        turns.append(req)
        if len(turns) == 1:
            return call(req, 'RequestSourceAction', {'action': 'request_source', 'reason_summary': 'Read original.',
                'selection': {'source_space': 'library', 'operation': 'read', 'document_id': 'DOC::test'}})
        args = submission()
        if len(turns) == 3:
            args['findings'][0]['evidence_spans'] = [dict(read_ref='O1', passage_id='PASSAGE::test', quote='Test original.')]
        return call(req, 'SubmitResearchOrientationAction', args)
    graph, value = make_graph(model, orientation_context={'require_evidence_spans': True})
    result = graph.invoke(value.model_dump(mode='json'))
    assert result['phase'] == 'research_orientation_submitted'
    assert len(turns) == 3


def test_tool_budget_rejects_whole_batch_before_any_source_side_effect():
    calls=[]
    def model(req):
        calls.append(req)
        assert req['capacity']['max_lead_tool_actions'] == 1
        result=call(req,'RequestSourceAction',{'action':'request_source','reason_summary':'Read sources.',
            'selection':{'source_space':'library','operation':'catalog'}})
        tool=result['action']['tool_calls'][0]
        result['action']['tool_calls'].append({**tool,'id':'second'})
        return result
    graph,value=make_graph(model,reader=lambda _:pytest.fail('over-budget batch must not execute'),
                           max_lead_tool_actions=1)
    result=graph.invoke(value.model_dump(mode='json'))
    assert result['stop_reason']=='lead_tool_action_ceiling'
    assert result['lead_tool_actions_used']==0 and len(calls)==1


def test_tool_budget_exact_boundary_keeps_submission_and_stops_without_extra_model_call():
    calls=[]
    def model(req):
        calls.append(req)
        assert req['progress']['lead_tool_actions_remaining']==3-len(calls)
        if len(calls)==1:
            return call(req,'RequestSourceAction',{'action':'request_source','reason_summary':'Read original.',
                'selection':{'source_space':'library','operation':'read','document_id':'DOC::test'}})
        return call(req,'SubmitResearchOrientationAction',submission())
    graph,value=make_graph(model,max_lead_tool_actions=2)
    result=graph.invoke(value.model_dump(mode='json'))
    assert result['phase']=='research_orientation_submitted'
    assert result['lead_tool_actions_used']==2 and len(calls)==2


def test_invalid_tool_attempt_consumes_budget_without_reissuing_model_request():
    calls=[]
    def model(req):
        calls.append(req)
        return call(req,'RequestSourceAction',{'action':'request_source','reason_summary':'Invalid selection.',
            'selection':{'source_space':'library','operation':'related'}})
    graph,value=make_graph(model,reader=lambda _:pytest.fail('invalid request'),max_lead_tool_actions=1)
    result=graph.invoke(value.model_dump(mode='json'))
    assert result['stop_reason']=='lead_tool_action_ceiling'
    assert result['lead_tool_actions_used']==1 and len(calls)==1


def test_independent_note_write_does_not_reject_original_reads(monkeypatch):
    from sec_agent.agent_runtime import working_memory_tools as memory
    monkeypatch.setattr(memory, 'memory_enabled', lambda: True)
    saved=[]
    monkeypatch.setattr(memory, 'execute_memory_tool', lambda name,args,config,role: saved.append(name) or {'saved':True})
    turns=[]
    def model(req):
        turns.append(req)
        if len(turns)==1:
            result=call(req,'RequestSourceAction',{'action':'request_source','reason_summary':'Read original.',
                'selection':{'source_space':'library','operation':'read','document_id':'DOC::test'}})
            result['action']['tool_calls'].insert(0, {'id':'note','name':'WriteWorkingNote',
                'args':{'title':'Review','content':'Prior findings only.','mode':'append','base_version':0}})
            return result
        assert req['progress']['planning_source_checks']==1
        return call(req,'SubmitResearchOrientationAction',submission())
    graph,value=make_graph(model,max_lead_tool_actions=3)
    result=graph.invoke(value.model_dump(mode='json'))
    assert saved==['WriteWorkingNote']
    assert result['phase']=='research_orientation_submitted'
    assert result['lead_tool_actions_used']==3
    assert result['research_orientation']['runtime_provenance']['O1']['result']==read_result()


def test_orientation_read_submit_keeps_full_provenance_and_stops():
    seen=[]
    def model(req):
        seen.append(req)
        assert req['workpapers'] == req['branch_catalog'] == req['tasks'] == []
        if len(seen)==1:
            return call(req,'RequestSourceAction',{'reason_summary':'阅读原文。',
                 'action':'request_source',
                 'selection':{'source_space':'library','operation':'read','document_id':'DOC::test'}})
        reply=json.loads(req['tool_results'][0]['content'])
        assert reply['read_ref']=='O1'
        assert reply['reading_scope']['evidence_kind']=='original_window'
        assert req['orientation_context']['observation_index']==[reply['reading_scope']]
        return call(req,'SubmitResearchOrientationAction',submission())
    graph,value=make_graph(model)
    result=graph.invoke(value.model_dump(mode='json'))
    assert result['phase']=='research_orientation_submitted' and len(seen)==2
    assert not result['task_results'] and not result['tasks']
    assert result['research_orientation']['runtime_provenance']['O1']['result']==read_result()
    assert result['research_orientation']['semantic_acceptance']=='not_assessed'


@pytest.mark.parametrize('operation,status,ref',[('catalog','success','O1'),('read','failure','O1'),('read','success','O9')])
def test_metadata_failed_reads_and_invented_refs_cannot_ground_findings(operation,status,ref):
    a=SubmitResearchOrientationAction.model_validate({**submission(ref),'context_digest':'a'*64})
    result=read_result();result['status']=status
    with pytest.raises(ValueError,match='successful_original'):
        bind_orientation(a,[{'read_ref':'O1','selection':{'operation':operation},'result':result}])


def test_retrieval_failure_can_stop_honestly_without_fake_evidence():
    def model(req):
        args=blocked_submission()
        return call(req,'SubmitResearchOrientationAction',args)
    graph,value=make_graph(model)
    result=graph.invoke(value.model_dump(mode='json'))
    assert result['research_orientation']['disposition']=='needs_attention'
    assert result['research_orientation']['runtime_provenance']=={}


@pytest.mark.parametrize('operation,status,items,expected',[
    ('read','success',[{'result_state':'retrieval_candidate','preview':'Chapter menu'}],'navigation_only'),
    ('search','success',[{'result_state':'retrieval_candidate','preview':'Matching text'}],'navigation_only'),
    ('read','failure',read_result()['items'],'execution_failure'),
    ('read','success',read_result()['items'],'original_window'),
])
def test_reading_scope_never_promotes_transport_success_or_window_end(operation,status,items,expected):
    from sec_agent.agent_runtime.research_orientation import observation_scope
    observation={'read_ref':'O1','selection':{'operation':operation},
        'result':{'status':status,'items':items+[{'result_state':'typed_gap','navigation':{'next_offset':None}}]}}
    before=json.dumps(observation)
    scope=observation_scope(observation)
    assert scope['evidence_kind']==expected
    assert scope['eligible_finding_reference']==(expected=='original_window')
    assert not scope['whole_document_review_established'] and not scope['public_non_disclosure_established']
    assert json.dumps(observation)==before


def test_orientation_library_default_and_invalid_routes_rejected_before_tool():
    base={'context_digest':'a'*64,'action':'request_source','reason_summary':'导航。'}
    parsed=OrientationLibraryReadAction.model_validate({**base,'selection':{'operation':'catalog'}})
    assert parsed.selection.source_space=='library' and parsed.selection.max_characters==8000
    for selection in [{'operation':'catalog','source_space':'local'},
                      {'operation':'outline','source_space':'library','document_id':'DOC::test'}]:
        with pytest.raises(ValueError):OrientationLibraryReadAction.model_validate({**base,'selection':selection})


def test_orientation_native_wire_excludes_execution_tools_and_old_role_prompt():
    wires=[]
    def transport(request):
        wire=json.loads(request.content);wires.append(wire)
        assert {t['function']['name'] for t in wire['tools']}=={'RequestSourceAction','SubmitResearchOrientationAction','ReportResearchIssuesAction'}
        assert 'preliminary research' in wire['messages'][0]['content']
        assert 'whole-question scope_map' in wire['messages'][0]['content']
        assert 'research_as_of' in wire['messages'][0]['content']
        assert 'One task covers one disclosed obligation' not in wire['messages'][0]['content']
        read_schema=next(t['function']['parameters'] for t in wire['tools'] if t['function']['name']=='RequestSourceAction')
        assert read_schema['properties']['selection']['properties']['source_space']['const']=='library'
        payload=json.loads(wire['messages'][1]['content'])
        assert payload['orientation_context']=={'catalog_navigation':'library','finding_original_read_refs':[], 'all_observed_refs':[], 'observation_index':[]}
        args=blocked_submission();args.update(context_digest=payload['context_digest'])
        return httpx.Response(200,json={'id':'offline','object':'chat.completion','created':1,'model':'deepseek-v4-pro',
            'choices':[{'index':0,'finish_reason':'tool_calls','message':{'role':'assistant','content':'',
            'reasoning_content':'offline fixture','tool_calls':[{'id':'stop','type':'function',
            'function':{'name':'SubmitResearchOrientationAction','arguments':json.dumps(args)}}]}}],
            'usage':{'prompt_tokens':0,'completion_tokens':0,'total_tokens':0}})
    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        model=ReasoningPreservingChatDeepSeek(model='deepseek-v4-pro',api_key=SecretStr('offline'),http_client=client,max_retries=0,use_responses_api=False)
        config=_config().model_copy(update={'agentic_message_history':True,'thinking':'enabled'})
        adapter=DeepSeekStructuredAgentAdapter(config=config,chat_models={r:model for r in ('planner','specialist','counter','lead')})
        graph,value=make_graph(adapter.lead_research_turn,turn_source='provider_model')
        result=graph.invoke(value.model_dump(mode='json'))
    assert result['phase']=='research_orientation_submitted' and len(wires)==1
