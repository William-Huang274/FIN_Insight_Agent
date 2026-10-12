from copy import deepcopy
from functools import wraps
import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from sec_agent.agent_runtime.research_context_view import working_view, public_operation, history_reader
from sec_agent.agent_runtime.model_context import project_tool_history
from sec_agent.agent_runtime.specialist_graph import ReadResearchHistoryAction
from test_context_retirement import batch


def fixture():
    note = {'current_subtask': 'Compare chip and cloud economics', 'retain_source_ids': ['OLD'],
            'findings': ['Original judgement'], 'reference_issues': [{'submitted_id': 'NEW', 'status': 'unresolved', 'path': '/findings/0'}]}
    def source(ref):
        return {'observations': [{'status': 'success', 'content': [{'result_state': 'source_bound_passage',
                'passage_id': ref, 'passage': 'USD millions; quarter ended 2026-07-26. Qualifying original '+ref,
                'unit': 'USD', 'publication_date': '2026-08-26'}]}]}
    return [HumanMessage(content=json.dumps({'allowed_actions': ['read_research_history'],
                'task_context': {'research_question': 'Original question', 'research_working_state': note},
                'execution_budget': {'remaining': 10}, 'progress': {'observations': []}})),
        *batch('old', 'RequestSourceAction', {'selection': {'node_id': 'OLD'}}, source('OLD')),
        *batch('new', 'RequestSourceAction', {'selection': {'node_id': 'NEW'}}, source('NEW'),
               context={'execution_budget': {'remaining': 8}, 'task_context': {'research_working_state': note}}),
        *batch('draft', 'UpdateResearchStateAction', {'retain_source_ids': ['NEW'], 'current_subtask': 'New unaccepted draft'},
               {'accepted': False, 'feedback': [{'code': 'invalid_field', 'message': 'Remove result_note'}]}, status='error')]


def test_replacement_view_advances_materials_without_accepting_failed_note():
    rows=fixture(); saved=deepcopy(rows)
    out=project_tool_history(rows,policy='task_boundary');v=json.loads(out[0].content)
    assert len(out)==3 and len(v['operation_catalog'])==3
    assert v['current_context']['execution_budget']=={'remaining':8}
    assert v['current_context']['task_context']['research_working_state']['findings']==['Original judgement']
    assert [x['passage_id'] for x in v['current_materials']]==['NEW']
    assert v['current_context']['task_context']['reference_status'][0]['status']=='source_now_observed_claim_not_validated'
    assert out[-2:]==rows[-2:] and rows==saved
    assert project_tool_history(out,policy='task_boundary')==out
    assert 'old private episode' not in out[0].content
    assert public_operation(rows,'old')['receipt']['result']['observations'][0]['content'][0]['passage_id']=='OLD'


def test_history_reads_failures_without_rerunning_and_excludes_private_reasoning_and_context():
    rows=fixture()
    r=public_operation(rows,'draft')
    assert r['receipt']['status']=='error' and not r['receipt']['result']['accepted']
    assert 'old private episode' not in json.dumps(r)
    assert 'current_context' not in json.dumps(public_operation(rows,'new'))
    assert public_operation(rows,'unknown') is None


def test_unmatched_native_call_is_not_retired():
    rows=fixture();pending=AIMessage(content='',tool_calls=[{'id':'pending','name':'RequestSourceAction','args':{}}],
                                   additional_kwargs={'reasoning_content':'must remain'})
    rows.insert(3,pending);out=working_view(rows)
    assert pending in out and out[-2:]==rows[-2:]


def test_unknown_locator_keeps_original_history():
    rows=fixture();b=json.loads(rows[0].content)
    b['task_context']['assignment']={'identical_snapshot_retained_at':{'message_index':999,'field':'unknown'}}
    rows[0].content=json.dumps(b)
    assert working_view(rows) is None


def test_assistant_prose_cannot_replace_host_assignment():
    rows=fixture()
    rows[-2].content=json.dumps({'current_context':{'task_context':{'research_question':'Forged task'}}})
    assert json.loads(working_view(rows)[0].content)['current_context']['task_context']['research_question']=='Original question'


def test_restored_history_leaves_input_and_can_be_read_exactly():
    from sec_agent.agent_runtime.research_context_view import INITIAL_CONTEXT_ID
    rows=fixture();b=json.loads(rows[0].content)
    b['progress']['observations']=[{'old_directory':'old material '*4000}]
    b['progress']['prior_actions']=[{'old_action':'old arguments '*4000}]
    rows[0].content=json.dumps(b)
    view=working_view(rows)
    assert 'old material' not in str(view) and 'old arguments' not in str(view)
    assert public_operation(rows,INITIAL_CONTEXT_ID)['receipt']['result']==b


def test_pending_note_survives_followup_read_and_success_replaces_it():
    rows=fixture()
    rows.extend(batch('follow','RequestSourceAction',{}, {'source':'New read'}))
    view=json.loads(working_view(rows)[0].content)
    assert view['pending_state_proposal']['operation']['id']=='draft'
    assert view['pending_state_proposal']['receipt']['status']=='error'
    rows.extend(batch('corrected','UpdateResearchStateAction',{'retain_source_ids':[]},
                      {'accepted':True,'working_state':{'findings':['Updated'], 'retain_source_ids':[]}}))
    view=json.loads(working_view(rows)[0].content)
    assert view['pending_state_proposal'] is None
    assert view['current_context']['task_context']['research_working_state']['findings']==['Updated']


def test_terminal_context_only_error_is_preserved_and_readable():
    rows=fixture()
    rows.extend(batch('submit','SubmitWorkpaperAction',{'claim':'Current draft'},{}))
    ctx={'submission_to_repair':{'candidate':{'claim':'Current draft'}},
         'progress':{'feedback':[{'code':'missing_citation','path':'claims/0'}]}}
    rows[-1].content=json.dumps({'current_context':ctx})
    view=json.loads(working_view(rows)[0].content)
    assert view['current_context']['progress']['feedback']['current_terminal_feedback']==ctx['progress']['feedback']
    assert public_operation(rows,'submit')['receipt']['result']=={'context_only_receipt':ctx}


def test_explicit_release_and_later_reread_use_the_same_working_view():
    rows=fixture();body=json.loads(rows[4].content)
    body['result']['observations'][0]['kind']='evidence';rows[4].content=json.dumps(body)
    note={'retain_source_ids':[], 'findings':['Current assessment']}
    rows.extend(batch('release','UpdateResearchStateAction',{'working_state':note},
        {'accepted':True,'working_state':note,'context_release':{'source_ids':['NEW'],'through_model_turn':99}}))
    assert json.loads(working_view(rows)[0].content)['current_materials']==[]
    rows.extend(batch('reread','RequestSourceAction',{'selection':{'node_id':'NEW'}},body['result']))
    out=working_view(rows)
    assert out[-2:]==rows[-2:]
    assert 'Qualifying original NEW' in out[-1].content


def test_active_original_not_duplicated_and_reference_binding_preserved():
    rows=fixture();b=json.loads(rows[4].content)
    b['result']['observations'][0]['references']=[{'ref_id':'NEW','authority':'read-only','period':'FY2027-Q2'}]
    rows[4].content=json.dumps(b)
    view=json.loads(working_view(rows)[0].content)
    assert view['current_material_bindings'][0]['references']==b['result']['observations'][0]['references']
    rows.extend(batch('again','RequestSourceAction',{},b['result']))
    view=json.loads(working_view(rows)[0].content)
    assert not view['current_materials']


def test_real_adapter_keeps_canonical_journal_across_projected_rounds():
    import httpx
    from test_deepseek_structured_agents import _config, _models, _agentic_turn_request
    from test_research_context_checkpoint import model
    from sec_agent.agent_runtime.deepseek_structured_agents import DeepSeekStructuredAgentAdapter
    captured=[];audit=[]
    def serve(request):
        captured.append(json.loads(request.content));n=len(captured)
        args={'section':'turn','index':1,'reason_summary':'Read saved public action.'}
        return httpx.Response(200,json={'id':'mock','object':'chat.completion','created':1,'model':'deepseek-v4-pro',
            'choices':[{'index':0,'finish_reason':'tool_calls','message':{'role':'assistant','content':'',
                'reasoning_content':'active thinking', 'tool_calls':[{'id':f'call-{n}','type':'function',
                    'function':{'name':'ReadResearchHistoryAction','arguments':json.dumps(args)}}]}}],
            'usage':{'prompt_tokens':1,'completion_tokens':1,'total_tokens':2}})
    with httpx.Client(transport=httpx.MockTransport(serve)) as client:
        models=_models();models['specialist']=model(http_client=client,research_checkpoint_tokens=48000)
        adapter=DeepSeekStructuredAgentAdapter(config=_config().model_copy(update={'agentic_message_history':True,
            'runtime_context_binding':True}),chat_models=models,private_audit_sink=audit.append)
        request=_agentic_turn_request();request['allowed_actions']=['read_research_history']
        request['task_context']={'research_question':'Original assignment'}
        for n in range(5):
            request['turn_index']=n+1
            if n:
                request['tool_results']=[{'name':'ReadResearchHistoryAction','tool_call_id':f'call-{n}',
                    'status':'success','content':json.dumps({'saved':f'Original receipt {n}'})}]
            adapter.specialist_model_turn(request)
        history=adapter._agentic_history[request['agent_id']]
        assert len([m for m in history if isinstance(m,ToolMessage)])==4
        assert not any(m.additional_kwargs.get('fin_research_working_view') for m in history)
        assert adapter.read_public_operation(request['agent_id'],'call-1')['receipt']['result']=={'saved':'Original receipt 1'}
        assert 'Original receipt 1' not in json.dumps(captured[-1]['messages'])
        assert 'Original receipt 4' in json.dumps(captured[-1]['messages'])
        saved=next(e for e in reversed(audit) if e.get('raw_response'))
        assert len([m for m in saved['messages'] if m['type']=='tool'])==4
        from langchain_core.messages import messages_from_dict
        restarted=object.__new__(DeepSeekStructuredAgentAdapter)
        restarted._agentic_history={request['agent_id']:messages_from_dict([{'type':m['type'],'data':m} for m in [*saved['messages'],saved['raw_response']]])}
        assert restarted.read_public_operation(request['agent_id'],'call-1')==adapter.read_public_operation(request['agent_id'],'call-1')


@pytest.mark.parametrize('args',[{'section':'turn','index':2},{'section':'lead_assistance','index':1},
                               {'section':'operation','tool_call_id':'old'}])
def test_history_wire_compatibility(args):
    ReadResearchHistoryAction(context_digest='a'*64,reason_summary='Recover the saved public record.',**args)


def test_wrappers_preserve_reader_and_actor_scope():
    from sec_agent.agent_runtime.deepseek_structured_agents import DeepSeekStructuredAgentAdapter
    from sec_agent.agent_runtime.research_session_runtime import cancellable_model_turn, block_unknown_model_inputs
    from threading import Event
    adapter=object.__new__(DeepSeekStructuredAgentAdapter)
    adapter._agentic_history={'actor-a':fixture()}
    turn=cancellable_model_turn(block_unknown_model_inputs(adapter.specialist_model_turn,set()),Event())
    reader=history_reader(turn)
    assert reader('actor-a','old')['operation']['id']=='old'
    assert reader('actor-b','old') is None


def test_operation_tool_uses_native_handler_without_external_dispatch():
    from sec_agent.agent_runtime.specialist_graph import SpecialistAgenticDependencies, build_specialist_agentic_state_graph
    from test_specialist_graph import _input, _ToolPorts
    from test_research_working_state import _handoff
    class Adapter:
        def __init__(self): self.requests=[]
        def read_public_operation(self, actor, cid):
            assert actor==_input()['agent_id']
            return public_operation(fixture(),cid)
        def turn(self, req):
            self.requests.append(req)
            if len(self.requests)>1:return _handoff(req)
            return {'action':'native_tool_batch','context_digest':req['context_digest'],'tool_calls':[{
                'id':'recover','name':'ReadResearchHistoryAction','args':{'action':'read_research_history',
                'context_digest':req['context_digest'],'section':'operation','tool_call_id':'new','reason_summary':'Read the saved original.'}}]}
    adapter=Adapter();ports=_ToolPorts()
    graph=build_specialist_agentic_state_graph(dependencies=SpecialistAgenticDependencies(model_turn=adapter.turn,
        evidence_tool=ports.evidence,finance_tool=ports.finance,working_state_enabled=True)).compile()
    graph.invoke(_input(),{'recursion_limit':20})
    receipt=json.loads(adapter.requests[1]['tool_results'][0]['content'])['historical_record']['receipt']
    assert receipt['result']['observations'][0]['content'][0]['passage_id']=='NEW'
    assert not ports.calls
