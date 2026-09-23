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


def test_one_topic_first_preserves_other_scope_without_fake_evidence():
    result = bind_test_submission(submission())
    assert result['contract_version'] == 'research_orientation.v2'
    assert len(result['topics']) == 1 and len(result['scope_map']) == 2
    assert result['scope_map'][1]['status'] == 'needs_discovery'
    assert result['semantic_acceptance'] == 'not_assessed'


def test_deferred_topic_requires_valid_scope_and_acyclic_dependencies():
    args = submission()
    args['topics'].append({**args['topics'][0], 'topic_id': 'T2', 'activation': 'deferred', 'depends_on': ['T1']})
    args['scope_map'][1].update(status='planned', topic_ids=['T2'])
    assert bind_test_submission(args)['topics'][1]['depends_on'] == ['T1']
    args['topics'][0].update(activation='deferred', depends_on=['T2'])
    with pytest.raises(ValueError, match='acyclic'): bind_test_submission(args)


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
        orientation_only=True, orientation_context={'catalog_navigation': 'library'},
        source_reader=reader or (lambda _: read_result()), max_lead_turns=4, **kwargs).compile()
    return graph, value


def call(req, name, args):
    return {'action': {'action': 'native_tool_batch', 'context_digest': req['context_digest'],
        'tool_calls': [{'id': str(req['progress']['turn_index']), 'name': name,
                       'args': {'context_digest': req['context_digest'], **args}}]}}


def test_orientation_read_submit_keeps_full_provenance_and_stops():
    seen=[]
    def model(req):
        seen.append(req)
        assert req['workpapers'] == req['branch_catalog'] == req['tasks'] == []
        if len(seen)==1:
            return call(req,'RequestSourceAction',{'reason_summary':'阅读原文。',
                 'action':'request_source',
                 'selection':{'source_space':'library','operation':'read','document_id':'DOC::test'}})
        assert json.loads(req['tool_results'][0]['content'])['read_ref']=='O1'
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
        assert payload['orientation_context']=={'catalog_navigation':'library','finding_original_read_refs':[], 'all_observed_refs':[]}
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
