import json
from sec_agent.agent_runtime.professional_roles import child_assignment, resolve_professional
from sec_agent.agent_runtime.specialist_composition import _bind_research_task
from sec_agent.agent_runtime.studio_configuration import bind_specialist_method
from sec_agent.agent_runtime.authoring_context import stage_methods
from test_lead_research_graph import _task
from test_specialist_graph import _input
from sec_agent.agent_runtime.specialist_graph import SpecialistAgenticInput


def test_native_production_assignment_has_survey_context_and_methods_only():
    raw = _input()
    raw['l0_context']['capability_summaries'].append({'capability_ref':'capability:dell:source-document-read','purpose':'Read original survey'})
    value = SpecialistAgenticInput.model_validate_json(json.dumps(raw))
    task = _task(branch=value.task.branch_id)
    task['requested_capability_refs']=['capability:dell:source-document-read']
    task['professional'] = {'profile':'survey_analysis', 'purpose':'Assess a survey observation for later demand research', 'source_hints':['DOC']}
    resolved = resolve_professional(task['professional'])
    bound = _bind_research_task(bind_specialist_method(value, resolved['method']), task, {})
    assert bound.task_context['professional']['profile'] == 'survey_analysis'
    assert bound.task_context['research_question'] == task['objective']
    assert 'dependency_workpapers' not in bound.task_context
    assert [m['method_id'] for m in stage_methods('workpaper', domain=resolved['domain'])['methods']] == ['writer','survey_analysis']


def test_child_does_not_inherit_parent_professional_or_global_context():
    parent = {**_task(), 'professional':{'profile':'survey_analysis','purpose':'Parent'}, 'private_history':['secret'], 'question':'global report'}
    spec = dict(subtask_id='n', objective='Bounded source study', success_criteria=['Read original'], source_hints=['DOC'])
    child = child_assignment(parent, spec)
    assert 'professional' not in child and 'private_history' not in child and 'question' not in child
    spec['professional'] = {'profile':'survey_analysis','purpose':'Measure adoption'}
    assert child_assignment(parent,spec)['professional']['profile'] == 'survey_analysis'


def test_provider_wire_does_not_reintroduce_financial_role_or_require_parent_papers():
    import httpx
    from pydantic import SecretStr
    from test_deepseek_structured_agents import _config, _agentic_turn_request, _agentic_action
    from sec_agent.agent_runtime.deepseek_structured_agents import DeepSeekStructuredAgentAdapter, ReasoningPreservingChatDeepSeek
    request=_agentic_turn_request()
    request['task_context']={'professional':{'profile':'survey_analysis','purpose':'Check an original survey'},
        'assignment':{'task_id':'survey-test'},'dependency_references':[]}
    wires=[]
    def respond(req):
        wires.append(json.loads(req.content))
        return httpx.Response(200,json={'id':'mock','object':'chat.completion','created':1,'model':'deepseek-v4-pro',
            'choices':[{'index':0,'finish_reason':'tool_calls','message':{'role':'assistant','content':'','reasoning_content':'Synthetic audit only',
                'tool_calls':[{'id':'a','type':'function','function':{'name':'RequestHumanReviewAction','arguments':json.dumps(_agentic_action(context_digest=request['context_digest']))}}]}}],
            'usage':{'prompt_tokens':10,'completion_tokens':5,'total_tokens':15}})
    model=ReasoningPreservingChatDeepSeek(model='deepseek-v4-pro',api_key=SecretStr('mock-no-network'),
        http_client=httpx.Client(transport=httpx.MockTransport(respond)),max_retries=0,use_responses_api=False)
    config=_config().model_copy(update={'agentic_message_history':True,'thinking':'enabled'})
    adapter=DeepSeekStructuredAgentAdapter(config=config,chat_models={r:model for r in ('planner','specialist','counter','lead')})
    adapter.specialist_model_turn(request)
    system=wires[0]['messages'][0]['content']
    assert '调查分析专业执行者' in system and 'autonomous financial-research Specialist' not in system
    semantic=json.loads(wires[0]['messages'][1]['content'])
    assert not semantic['branch']['evidence_requests'] and not semantic['branch']['fact_requests']
    assert semantic['task_context']['assignment']['task_id']=='survey-test'


def test_lead_dispatches_professional_and_collects_native_workpaper():
    from sec_agent.agent_runtime.lead_research_graph import build_lead_research_graph
    from test_lead_research_graph import _call, _stop, _worker_result
    from test_workpaper_review_graph import _seed
    raw=_input()
    raw['l0_context']['capability_summaries'].append({'capability_ref':'capability:dell:source-document-read','purpose':'Original-source reading'})
    value=SpecialistAgenticInput.model_validate_json(json.dumps(raw))
    task=_task(branch=value.task.branch_id)
    task['requested_capability_refs']=['capability:dell:source-document-read']
    task['professional']={'profile':'survey_analysis','purpose':'Bounded survey work'}
    seen=[]
    def lead(request):
        return _stop(request,ready=True) if seen else _call(request,'DelegateResearchTasksAction',tasks=[task])
    def worker(assignment, dependencies, config):
        seen.append(assignment)
        assert assignment['professional']['profile']=='survey_analysis' and not dependencies
        return _worker_result(assignment,_seed())
    graph=build_lead_research_graph(expected_input=value,research_question='调查能够支持哪些判断？',
        branch_catalog=[{'branch_id':value.task.branch_id,'objective':'Scoped survey'}],allowed_branch_ids=(value.task.branch_id,),
        seed_workpapers={},model_turn=lead,run_child=worker).compile()
    state=graph.invoke(value.model_dump(mode='json'))
    assert len(seen)==1 and state['phase']=='research_ready_for_review'
