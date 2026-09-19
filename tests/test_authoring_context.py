import asyncio
from copy import deepcopy
import json
import pytest

from sec_agent.agent_runtime.authoring_context import bind_authoring, validate_authoring, stage_methods
from test_research_convergence import exercise_case

BRIEF={'answer':'Scoped answer','argument_plan':['Evidence then inference'],
       'decisions':['Do not infer causation'],'material_conditions':['Same population'],
       'unresolved':[],'ready':True}


def test_bound_public_state_is_lossless_and_rejects_changed_evidence_or_owner():
    basis={'sources':[{'id':'p1','period':'2025','revision':2}], 'issues':['Preserve denominator']}
    packet=bind_authoring(BRIEF,owner='expert',stage='workpaper',basis=basis)
    assert packet['basis']==basis and packet['brief']==BRIEF
    validate_authoring(packet,owner='expert',basis=basis)
    with pytest.raises(ValueError):validate_authoring(packet,owner='other',basis=basis)
    basis['sources'][0]['revision']=3
    with pytest.raises(ValueError):validate_authoring(packet,owner='expert',basis=basis)
    assert packet['basis']['sources'][0]['revision']==2


def test_stage_disclosure_replaces_research_method_but_preserves_semantics():
    prep=stage_methods('prepare_report'); final=stage_methods('report')
    assert [m['method_id'] for m in prep['methods']]==['finance','lead','writer']
    assert [m['method_id'] for m in final['methods']]==['writer']
    assert prep['core_semantics']==final['core_semantics']
    assert all(m['selection']!='full_resource' for m in final['methods'])
    survey=stage_methods('workpaper',domain='survey_analysis')
    assert [m['method_id'] for m in survey['methods']]==['writer','survey_analysis']
    assert survey['methods'][0]['selection']==['先确定交付对象：报告或专题底稿']


def test_native_mcp_method_envelope_preserves_receipt_and_stage_content():
    from sec_agent.research_foundation.research_methods import get_research_method
    def native(method_id):
        return {'method':get_research_method(method_id),'mcp_receipt':{'id':'actual-envelope-fixture'}}
    methods=stage_methods('prepare_workpaper',domain='survey_analysis',reader=native)['methods']
    assert all(m['content'] and m['mcp_receipt']['id']=='actual-envelope-fixture' for m in methods)
    assert all(m['runtime_compatibility_parse']=='receipted_method_envelope.v1' for m in methods)


def test_real_convergence_lead_prepares_before_writing_and_reprepares_on_revision():
    result, sequence, models=asyncio.run(exercise_case(hierarchical=True,authoring_stages=True,terminal_owner='writer'))
    roles=[r[0] for r in sequence]
    assert roles==['lead_decision','synthesis','research_verifier','prepare','writer','report_verifier','prepare','writer','report_verifier']
    for round_ in (0,1):
        model=models[('writer',None,round_)]
        payload=json.loads(model.contexts[0][1].content)
        assert payload['authoring_context']['owner']=='research_lead'
        assert payload['authoring_context']['brief']['material_conditions']==['Same period only']
        assert 'SAME responsible research Lead' in model.contexts[0][0].content
        assert len(model.contexts[0]) == 2  # New current-version input, no previous draft/tool transcript.
    assert result['phase']=='case_report_ready_for_human_review'
    assert result['authoring_context']['basis']['report_review']['findings']


def test_preparation_with_unresolved_material_work_never_reaches_writer():
    result,sequence,_=asyncio.run(exercise_case(hierarchical=True,authoring_stages=True,author_ready=False))
    assert 'writer' not in [r[0] for r in sequence]
    assert result['stop_reason']=='lead_preparation_retains_material_research'


def test_specialist_preparation_preserves_sources_and_replaces_static_role_method():
    from test_specialist_graph import _input, _ScriptedModel, _ToolPorts, _evidence_action, _finance_action, _submission, _action
    from sec_agent.agent_runtime.specialist_graph import SpecialistAgenticDependencies, build_specialist_agentic_state_graph
    model=_ScriptedModel([_evidence_action(),_finance_action(),
        _action('prepare_workpaper',brief=BRIEF),_submission()])
    tools=_ToolPorts(); initial=_input()
    initial['l0_context']['skill_summaries'][0]['role_method']={'content':'OBSOLETE WHOLE ROLE PROMPT'}
    graph=build_specialist_agentic_state_graph(dependencies=SpecialistAgenticDependencies(
        model_turn=model,evidence_tool=tools.evidence,finance_tool=tools.finance,authoring_enabled=True)).compile()
    result=graph.invoke(initial,{'recursion_limit':50})
    assert result.get('final_submission')
    before,after=model.requests[2:4]
    assert 'submit_workpaper' not in before['allowed_actions']
    assert 'submit_workpaper' in after['allowed_actions']
    assert after['task_context']['authoring_context']['brief']==BRIEF
    assert 'OBSOLETE WHOLE ROLE PROMPT' not in json.dumps(after)
    assert after['task_context']['stage_methods']['stage']=='workpaper'
    assert result['notebook']['model_turn_count']==4


def test_provider_writing_request_starts_fresh_but_restores_prepared_state():
    import httpx
    from pydantic import SecretStr
    from sec_agent.agent_runtime.deepseek_structured_agents import DeepSeekStructuredAgentAdapter, ReasoningPreservingChatDeepSeek
    from test_deepseek_structured_agents import _config, _models, _agentic_turn_request
    request=_agentic_turn_request(); request['task_context']={'obsolete_dispatch':'DO_NOT_CARRY_THIS_PROMPT'}
    seen=[]
    def serve(wire):
        seen.append(json.loads(wire.content))
        return httpx.Response(200,json={'id':'offline','object':'chat.completion','created':1,
            'model':'deepseek-v4-pro','choices':[{'index':0,'finish_reason':'tool_calls','message':{
                'role':'assistant','content':'','tool_calls':[{'id':'stop','type':'function','function':{
                    'name':'RequestHumanReviewAction','arguments':json.dumps({'action':'request_human_review',
                        'context_digest':request['context_digest'],'reason_summary':'Offline fixture'})}}]}}],
            'usage':{'prompt_tokens':100,'completion_tokens':30,'total_tokens':130}})
    with httpx.Client(transport=httpx.MockTransport(serve)) as client:
        models=_models();models['specialist']=ReasoningPreservingChatDeepSeek(model='deepseek-v4-pro',
            api_key=SecretStr('offline'),http_client=client,max_retries=0,use_responses_api=False)
        adapter=DeepSeekStructuredAgentAdapter(config=_config().model_copy(update={'agentic_message_history':True}),chat_models=models)
        adapter.specialist_model_turn(request)
        request['task_context']={'authoring_context':bind_authoring(BRIEF,owner='expert',stage='workpaper',
            basis={'source':'retained original period and denominator'}),'stage_methods':stage_methods('workpaper')}
        adapter.specialist_model_turn(request)
    assert len(seen[1]['messages'])==2
    assert 'DO_NOT_CARRY_THIS_PROMPT' not in json.dumps(seen[1])
    assert 'retained original period and denominator' in json.dumps(seen[1])
    assert 'Same population' in json.dumps(seen[1])


@pytest.mark.parametrize('change',[{'version':2},{'enabled':'yes'},{'context_version':'unknown.v9'}])
def test_unknown_authoring_protocol_cannot_silently_start(tmp_path,change):
    from pathlib import Path
    from sec_agent.agent_runtime.research_session_runtime import load_research_runtime_profile
    relative=Path('configs/research/runtime/research_session.json')
    profile=json.loads(relative.read_text(encoding='utf-8'))
    profile['authoring'].update(change)
    target=tmp_path/relative; target.parent.mkdir(parents=True)
    target.write_text(json.dumps(profile),encoding='utf-8')
    with pytest.raises(ValueError,match='authoring_configuration_invalid'):
        load_research_runtime_profile(tmp_path)


def test_saved_research_can_resume_only_authoring_and_unready_is_not_format_failure():
    from sec_agent.research_foundation.method_worker import compile_method_worker
    from test_specialist_delegation import READS, paper
    original=paper(); seen=[]
    async def blocked(actor,payload,schema):
        seen.append(payload['authoring_phase'])
        return {**BRIEF,'ready':False,'unresolved':['Unresolved core finding']}
    args=dict(actor='expert',payload={'read_results':READS,'instructions':'Research'},record=lambda *a:None,
        runtime_submissions=True,authoring_stages=True,entry_phase='prepare_workpaper')
    seed={'action':{'action':'finish','result':original},'observations':[],'tool_rounds':1}
    stopped=asyncio.run(compile_method_worker(call=blocked,**args).ainvoke(deepcopy(seed)))
    assert stopped['authoring_blocked'] and not stopped.get('submission_failure')
    assert seen==['prepare_workpaper']
    async def finish(actor,payload,schema):
        seen.append(payload['authoring_phase'])
        return BRIEF if payload['authoring_phase']=='prepare_workpaper' else original
    completed=asyncio.run(compile_method_worker(call=finish,**args).ainvoke(deepcopy(seed)))
    assert seen==['prepare_workpaper','prepare_workpaper','workpaper']
    assert completed['tool_rounds']==1
    assert completed['action']['result']['summary']==original['summary']
