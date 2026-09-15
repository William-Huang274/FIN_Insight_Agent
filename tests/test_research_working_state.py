"""Phase cleanup and stalled-expert recovery on native graphs, with no paid calls."""
from copy import deepcopy
import json
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from sec_agent.agent_runtime.model_context import project_tool_history
from sec_agent.agent_runtime.research_working_state import progress_after_tools
from sec_agent.agent_runtime.specialist_graph import SpecialistAgenticDependencies, build_specialist_agentic_state_graph
from sec_agent.agent_runtime.research_assistance import build_lead_assistance_graph
from sec_agent.agent_runtime.deepseek_structured_agents import _project_request
from test_specialist_graph import _input, _evidence_action, _ToolPorts
from test_specialist_tool_batch import _batch, _handoff


def working_note(**updates):
    return {"current_subtask": "Compare the actual quarter and guidance period", "phase_status": "completed",
        "findings": [{"finding": "Fixture quarterly quantity, not an annual composition", "source_ids": ["SOURCE-A"],
            "limitations": "Quarterly actual, fixture units, not annual guidance."}],
        "retain_source_ids": ["SOURCE-B"], "rejected_interpretations": ["The quarterly ratio is not the annual composition."],
        "open_questions": ["Annual composition remains unknown."], "next_step": "Read the next original section for the annual scope.",
        "last_task_detail": "Compared two original periods and retained the numerical qualifiers and both source records.", **updates}


def source_messages(i):
    return [AIMessage(content="Old search intention, not a verified finding.", tool_calls=[{
        "name": "RequestSourceAction", "args": {"selection": {"node_id": i}}, "id": i, "type": "tool_call"}]),
        ToolMessage(name="RequestSourceAction", tool_call_id=i, content=json.dumps({"ref_id": i,
            "passage": "Original numbers and period qualifiers. " * 300}))]


def test_phase_cleanup_keeps_active_material_sources_and_original_records():
    rows = [HumanMessage(content="Overall research and exact latest user requirement."), *source_messages("SOURCE-A"),
        *source_messages("SOURCE-B"), *source_messages("SOURCE-C")]
    assert project_tool_history(rows, policy="task_boundary", trigger_tokens=1, keep=1) == rows
    rows += [AIMessage(content="", tool_calls=[{"name": "UpdateResearchStateAction", "id": "note", "args": {}, "type": "tool_call"}]),
        ToolMessage(name="UpdateResearchStateAction", tool_call_id="note", content=json.dumps({"result": {"accepted": True, "working_state": working_note()}, "current_context": {"progress": {}}})),
        *source_messages("SOURCE-D"), *source_messages("SOURCE-E")]
    before=deepcopy(rows)
    projected=project_tool_history(rows, policy="task_boundary", trigger_tokens=1, keep=1)
    assert rows == before
    for i in (2,4,10,12): assert projected[i] == rows[i]
    assert "Original numbers" not in projected[6].content
    assert '"node_id":"SOURCE-C"' in projected[6].content
    assert projected[8] == rows[8]  # latest task detail and invalidated interpretation


def test_rejected_phase_note_cannot_clear_any_evidence():
    rows=[*source_messages("SOURCE-A"), ToolMessage(name="UpdateResearchStateAction", tool_call_id="bad",
        content=json.dumps({"accepted": True, "working_state": working_note()}), status="error")]
    assert project_tool_history(rows, policy="task_boundary") == rows


def test_no_progress_uses_result_content_not_new_receipt_ids():
    obs={"status":"success","kind":"evidence","references":[],"content":[{"text":"Same observed result"}],"observation_digest":"old"}
    before={"observations":[obs]}
    after={"observations":[obs,{**obs,"observation_digest":"different-runtime-receipt"}]}
    assert progress_after_tools(before,after,{"consecutive_no_new_observations":1},has_reads=True)["status"] == "warn"
    after['observations'].append({**obs,'content':[{'text':'New original window'}]})
    assert progress_after_tools(before,after,{},has_reads=True)['consecutive_no_new_observations'] == 0


def test_stalled_expert_gets_warning_then_lead_help_in_same_task_without_reset():
    requests, helps = [], []
    ports=_ToolPorts()
    def model(request):
        requests.append(deepcopy(request))
        if request['task_context'].get('lead_assistance'):
            return _handoff(request)
        return _batch(request,[_evidence_action()({})])
    def help(state, config):
        helps.append(deepcopy(state))
        assert state['notebook']['model_turn_count'] == 5
        return {'disposition':'continue','diagnosis':'The current fixture query repeats the same successful observation.',
            'next_action':'Inspect the next original section and retain the already read evidence.',
            'expected_progress':'A different original window or an explicit remaining evidence gap.'}
    graph=build_specialist_agentic_state_graph(dependencies=SpecialistAgenticDependencies(model_turn=model,
        evidence_tool=ports.evidence,finance_tool=ports.finance,working_state_enabled=True,lead_assistance=help)).compile()
    seed=_input();seed['max_model_turns']=12;seed['max_tool_actions']=24
    result=graph.invoke(seed,{'recursion_limit':60})
    assert len(helps)==1 and result['notebook']['model_turn_count']==6
    assert requests[-1]['task']['task_id']==requests[0]['task']['task_id']
    assert any(r['task_context']['runtime_progress'].get('status')=='warn' for r in requests)
    assert result['lead_assistance_history'][0]['disposition']=='continue'


def test_native_lead_consultation_receives_source_result_before_guidance():
    requests=[]
    base={'agent_id':'lead:fixture-assistance','research_question':'Current whole task', 'research_as_of':'2025-07-25T23:59:59Z',
        'branch_catalog':[],'required_branch_ids':[],'capabilities':[],'capacity':{},'workpapers':[],'tasks':[]}
    def model(request):
        _project_request('lead',request,specialist_mode='agentic_lead')
        requests.append(request)
        if len(requests)==1:
            name,args='RequestSourceAction',{'action':'request_source','selection':{'operation':'catalog','source_space':'uploads'}}
        else:
            assert 'original available source' in json.dumps(request['tool_results'])
            name,args='ProvideResearchGuidanceAction',{'disposition':'continue','diagnosis':'The actual catalog exposes the next source window to inspect.',
                'next_action':'Read the actual next original window and revise the incorrect old location.',
                'expected_progress':'New source context answers the remaining period question.'}
        return {'action':{'action':'native_tool_batch','context_digest':request['context_digest'], 'tool_calls':[{
            'id':str(len(requests)),'name':name,'args':{**args,'context_digest':request['context_digest'],'reason_summary':'Resolve the specific fixture blockage.'}}]}}
    graph=build_lead_assistance_graph(request_base=base,model_turn=model,source_reader=lambda selection:{'catalog':'original available source'},
        source_spaces={'uploads'},turn_source='scripted_qualification').compile()
    result=graph.invoke({}, {'recursion_limit':16})
    assert result['guidance']['disposition']=='continue' and result['turns']==2


def test_repeated_failure_after_bounded_lead_help_stops_without_resetting_allowance():
    calls,helps=[],[]
    ports=_ToolPorts()
    def model(request):
        calls.append(request)
        return _batch(request,[_evidence_action()({})])
    def help(state, config):
        helps.append(state['notebook']['model_turn_count'])
        return {'disposition':'continue','diagnosis':'The same original fixture is repeatedly read without new observations.',
            'next_action':'Use a different source window or explicitly retain the unfilled evidence gap.',
            'expected_progress':'A new original observation, not a restatement of the old source.'}
    seed=_input();seed['max_model_turns']=24;seed['max_tool_actions']=40
    graph=build_specialist_agentic_state_graph(dependencies=SpecialistAgenticDependencies(model_turn=model,
        evidence_tool=ports.evidence,finance_tool=ports.finance,working_state_enabled=True,lead_assistance=help)).compile()
    result=graph.invoke(seed,{'recursion_limit':100})
    assert helps==[5,9] and len(calls)==13
    assert result['review_reason']=='repeated_no_progress_after_lead_assistance'
    assert result['max_model_turns']==24 and result['notebook']['model_turn_count']==13


def test_unobserved_working_state_source_is_rejected_without_clearing_authority():
    calls=[];ports=_ToolPorts()
    def model(request):
        calls.append(request)
        if len(calls)>1:return _handoff(request)
        return {'action':'native_tool_batch','context_digest':request['context_digest'],'tool_calls':[{
            'id':'note','name':'UpdateResearchStateAction','args':{'action':'update_research_state',
                'context_digest':request['context_digest'],'reason_summary':'Record an unsupported fixture note.', 'working_state':working_note()}}]}
    graph=build_specialist_agentic_state_graph(dependencies=SpecialistAgenticDependencies(model_turn=model,
        evidence_tool=ports.evidence,finance_tool=ports.finance,working_state_enabled=True)).compile()
    result=graph.invoke(_input(),{'recursion_limit':20})
    assert not result.get('research_working_state')
    assert 'working_state_unknown_source' in json.dumps(calls[-1]['tool_results'])


def test_lead_assistance_uses_existing_sdk_schema_and_bound_receipt_without_network():
    import httpx
    from pydantic import SecretStr
    from sec_agent.agent_runtime.deepseek_structured_agents import DeepSeekStructuredAgentAdapter, ReasoningPreservingChatDeepSeek
    from test_deepseek_structured_agents import _config, _models
    captured=[]
    guidance={'disposition':'continue','diagnosis':'The existing expert needs a different actual original source window.',
        'next_action':'Use the next original block exposed by the source catalog without repeating old reads.',
        'expected_progress':'Find the missing period qualifier or explicitly retain the unresolved gap.',
        'reason_summary':'Provide targeted fixture recovery, no research answer.'}
    def serve(request):
        body=json.loads(request.content);captured.append(body)
        assert {t['function']['name'] for t in body['tools']} == {'RequestSourceAction','ProvideResearchGuidanceAction'}
        assert 'helping an existing expert' in body['messages'][0]['content']
        return httpx.Response(200,json={'id':'fixture','object':'chat.completion','created':1,'model':'deepseek-v4-pro',
            'choices':[{'index':0,'finish_reason':'tool_calls','message':{'role':'assistant','content':'','tool_calls':[
                {'id':'guide','type':'function','function':{'name':'ProvideResearchGuidanceAction','arguments':json.dumps(guidance)}}]}}],
            'usage':{'prompt_tokens':100,'completion_tokens':30,'total_tokens':130}})
    base={'agent_id':'lead:fixture-assistance','research_question':'Current whole task','research_as_of':'2025-07-25T23:59:59Z',
        'branch_catalog':[],'required_branch_ids':[],'capabilities':[],'capacity':{},'workpapers':[],'tasks':[]}
    with httpx.Client(transport=httpx.MockTransport(serve)) as client:
        models=_models();models['lead']=ReasoningPreservingChatDeepSeek(model='deepseek-v4-pro',api_key=SecretStr('offline-fixture'),http_client=client,max_retries=0,use_responses_api=False)
        adapter=DeepSeekStructuredAgentAdapter(config=_config().model_copy(update={'agentic_message_history':True,'runtime_context_binding':True}),chat_models=models)
        graph=build_lead_assistance_graph(request_base=base,model_turn=adapter.lead_research_turn,source_reader=lambda _: {},source_spaces={'uploads'}).compile()
        result=graph.invoke({}, {'recursion_limit':16})
    assert result['guidance']['disposition']=='continue' and len(captured)==1
