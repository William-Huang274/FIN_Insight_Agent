from copy import deepcopy
from functools import wraps
import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from sec_agent.agent_runtime.research_context_view import history_operation_page, working_view, public_operation, history_reader
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


def test_navigation_only_source_action_does_not_retire_current_originals():
    rows = [HumanMessage(content=json.dumps({'allowed_actions': ['read_research_history'],
        'task_context': {'research_question': 'Compare current source text'}, 'progress': {'observations': []}}))]
    source = {'observations': [{'status': 'success', 'content': [{'result_state': 'source_bound_passage',
        'passage_id': 'SOURCE-A', 'passage': 'The complete first source passage.'}]}]}
    rows.extend(batch('read-a', 'RequestSourceAction', {'selection': {'operation': 'read'}}, source))
    rows.extend(batch('search-b', 'RequestSourceAction', {'selection': {'operation': 'search'}}, {
        'observations': [{'status': 'success', 'content': [{'result_state': 'retrieval_candidate',
            'node_id': 'NODE-B', 'preview': 'Navigation only, not readable source text.'}]}]}))

    out = working_view(rows)
    rendered = json.dumps([message.model_dump(mode='json') for message in out], ensure_ascii=False)
    assert 'The complete first source passage.' in rendered
    assert [row['passage_id'] for row in json.loads(out[0].content)['current_materials']] == ['SOURCE-A']


def test_implicit_material_cohort_keeps_two_adjacent_reads_for_comparison():
    rows = [HumanMessage(content=json.dumps({'allowed_actions': ['read_research_history'],
        'task_context': {'research_question': 'Compare adjacent reported periods'}, 'progress': {'observations': []}}))]
    def result(ref):
        return {'observations': [{'status': 'success', 'content': [{'result_state': 'source_bound_passage',
            'passage_id': ref, 'passage': 'Complete original for ' + ref}]}]}
    rows.extend(batch('read-a', 'RequestSourceAction', {}, result('SOURCE-A')))
    rows.extend(batch('read-b', 'RequestSourceAction', {}, result('SOURCE-B')))
    rows.extend(batch('read-c', 'RequestSourceAction', {}, result('SOURCE-C')))

    out = working_view(rows)
    rendered = json.dumps([message.model_dump(mode='json') for message in out], ensure_ascii=False)
    assert 'Complete original for SOURCE-A' not in rendered
    assert 'Complete original for SOURCE-B' in rendered
    assert 'Complete original for SOURCE-C' in rendered
    view = json.loads(out[0].content)
    assert view['material_focus'] == 'implicit_recent_material_cohort'

    rows.extend(batch('consume-c', 'RequestSourceAction', {'selection': {'operation': 'search'}}, {
        'observations': [{'status': 'success', 'content': [{'result_state': 'retrieval_candidate',
            'node_id': 'NODE-D', 'preview': 'Navigation after the comparison turn.'}]}]}))
    out = working_view(rows)
    rendered = json.dumps([message.model_dump(mode='json') for message in out], ensure_ascii=False)
    assert 'Complete original for SOURCE-B' not in rendered
    assert 'Complete original for SOURCE-C' in rendered


def test_history_reads_failures_without_rerunning_and_excludes_private_reasoning_and_context():
    rows=fixture()
    r=public_operation(rows,'draft')
    assert r['receipt']['status']=='error' and not r['receipt']['result']['accepted']
    assert 'old private episode' not in json.dumps(r)
    assert 'current_context' not in json.dumps(public_operation(rows,'new'))
    assert public_operation(rows,'unknown') is None


def test_large_history_operation_pages_or_returns_exact_selected_material_without_mutation():
    record = {
        'operation': {'id': 'large-read', 'name': 'RequestSourceAction', 'args': {'selection': {'document_id': 'WEB::call'}}},
        'receipt': {'status': 'success', 'result': {'observations': [{'content': [
            {'passage_id': 'PASSAGE::A', 'passage': 'A' * 15_000},
            {'passage_id': 'PASSAGE::B', 'passage': 'B' * 15_000},
        ]}]}},
    }
    saved = deepcopy(record)
    page = history_operation_page(record, max_characters=12_000)
    assert page['total_characters'] > 12_000
    assert len(page['serialized_record_window']) == 12_000
    assert page['next_offset'] == 12_000
    selected = history_operation_page(record, source_ids=('PASSAGE::B',))
    assert [row['passage_id'] for row in selected['receipt']['result']['selected_materials']] == ['PASSAGE::B']
    assert selected['available_source_ids'] == ['PASSAGE::A', 'PASSAGE::B']
    assert record == saved


@pytest.mark.parametrize('accepted', [True, False])
def test_submission_history_returns_exact_receipt_and_explicit_full_record_pages(accepted):
    record = {'operation': {'id': 'submit', 'name': 'SubmitWorkpaperAction',
        'args': {'narrative_markdown': 'long financial analysis ' * 2000}},
        'receipt': {'status': 'success' if accepted else 'error', 'result': {
            'accepted': accepted, 'feedback': [] if accepted else [{'code': 'quote_error'}]}},
        'notice': 'Original public operation'}
    before = deepcopy(record)
    receipt = history_operation_page(record)
    assert receipt['receipt'] == record['receipt']
    assert 'args' not in receipt['operation'] and 'serialized_record_window' not in receipt
    assert receipt['record_read']['arguments']['view'] == 'record'
    offset, windows = 0, []
    while True:
        page = history_operation_page(record, view='record', offset=offset, max_characters=1000)
        assert 'args' not in page['operation']
        windows.append(page['serialized_record_window'])
        if page['next_read'] is None:
            break
        assert page['next_read']['arguments']['view'] == 'record'
        offset = page['next_read']['arguments']['offset']
    assert json.loads(''.join(windows)) == record
    assert record == before


def test_large_receipt_has_own_cursor_and_no_duplicate_argument_body():
    record = {'operation': {'id': 'failed', 'name': 'SubmitWorkpaperAction', 'args': {'large': 'X'*30000}},
        'receipt': {'status': 'error', 'result': {'accepted': False, 'feedback': ['Q'*30000]}}}
    first = history_operation_page(record, view='receipt', max_characters=1000)
    assert first['total_characters'] == len(json.dumps(record['receipt'], ensure_ascii=False, separators=(',', ':')))
    assert first['next_read']['arguments']['view'] == 'receipt'
    assert 'X'*100 not in json.dumps(first) and 'args' not in first['operation']
    # An old cursor without a new view must keep its original full-record scope.
    legacy = history_operation_page(record, offset=1000, max_characters=1000)
    assert legacy['view'] == 'record'


def test_pending_old_history_read_reprojects_from_canonical_record_without_changing_archive():
    rows = fixture()
    rows.extend(batch('submit', 'SubmitWorkpaperAction', {'narrative_markdown': 'old manuscript '*2000},
                      {'accepted': True, 'feedback': []}))
    rows.extend(batch('read-submit', 'ReadResearchHistoryAction', {'section': 'operation', 'tool_call_id': 'submit'},
        {'historical_record': {'operation': {'args': 'duplicate old manuscript'},
                               'serialized_record_window': 'duplicate old manuscript'}}))
    saved = deepcopy(rows)
    out = working_view(rows)
    result = json.loads(out[-1].content)['result']['historical_record']
    assert result['receipt']['result']['accepted'] is True
    assert result['record_read']['arguments']['tool_call_id'] == 'submit'
    assert 'narrative_markdown' not in json.dumps(result)
    assert rows == saved


def test_history_view_omission_preserves_old_action_wire_identity():
    old = {'action': 'read_research_history', 'context_digest': 'a'*64,
        'section': 'operation', 'tool_call_id': 'call', 'index': None,
        'offset': 0, 'max_characters': 12000, 'source_ids': [], 'reason_summary': 'Read saved data'}
    assert ReadResearchHistoryAction.model_validate_json(json.dumps(old)).model_dump(mode='json') == old
    explicit = ReadResearchHistoryAction.model_validate_json(json.dumps({**old, 'view': 'record'}))
    assert explicit.model_dump(mode='json')['view'] == 'record'


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


def test_revision_boundary_archives_completed_terminal_but_keeps_readback_and_later_errors():
    rows=fixture()
    rows.extend(batch('accepted-draft','SubmitWorkpaperAction',{'thesis':'Saved paper'}, {'accepted':True}))
    context={'allowed_actions':['read_research_history','revise_workpaper'],
        'task_context':{'research_question':'Original question','revision_feedback':[{'finding_id':'F1'}]},
        'submission_to_repair':{'candidate':{'thesis':'Saved paper'},'current_candidate_digest':'current'}}
    rows.append(HumanMessage(content=json.dumps(context),
        additional_kwargs={'fin_research_stage_boundary':'accepted_submission_to_revision'}))
    original=deepcopy(rows)
    result=working_view(rows); view=json.loads(result[0].content)
    assert not any(isinstance(m,(AIMessage,ToolMessage)) for m in result)
    assert view['current_context']['submission_to_repair']['current_candidate_digest']=='current'
    assert next(r for r in view['operation_catalog'] if r['tool_call_id']=='accepted-draft')['accepted'] is True
    assert public_operation(rows,'accepted-draft')['receipt']['result']=={'accepted':True}
    assert rows==original
    rows.extend(batch('new-read','ReadResearchHistoryAction',{}, {'error':'invalid_locator'}))
    result=working_view(rows)
    assert result[-2].tool_calls[0]['id']=='new-read'
    assert result[-1].tool_call_id=='new-read'
    assert 'invalid_locator' in result[-1].content
    assert not any(isinstance(m,AIMessage) and m.tool_calls[0]['id']=='accepted-draft' for m in result)
    # Even a stage marker must never consume an incomplete tool exchange.
    unpaired=deepcopy(original);unpaired.insert(-1,AIMessage(content='',tool_calls=[
        {'id':'unfinished','name':'RequestSourceAction','args':{}}]))
    result=working_view(unpaired)
    assert any(isinstance(m,AIMessage) and m.tool_calls[0]['id']=='unfinished' for m in result)


@pytest.mark.parametrize('accepted', [True,False])
def test_adapter_revision_starts_after_old_terminal_and_keeps_real_rejection(accepted):
    import httpx
    from langchain_core.messages import SystemMessage
    from test_deepseek_structured_agents import _config, _models, _agentic_turn_request
    from test_research_context_checkpoint import model
    from sec_agent.agent_runtime.deepseek_structured_agents import DeepSeekStructuredAgentAdapter
    captured=[]
    def serve(request):
        captured.append(json.loads(request.content))
        return httpx.Response(200,json={'id':'mock','object':'chat.completion','created':1,'model':'deepseek-v4-pro',
            'choices':[{'index':0,'finish_reason':'tool_calls','message':{'role':'assistant','content':'',
                'reasoning_content':'new stage thinking','tool_calls':[{'id':'new-call','type':'function',
                    'function':{'name':'ReadResearchHistoryAction','arguments':json.dumps({'section':'operation',
                        'tool_call_id':'old-submit','reason_summary':'Read exact saved receipt.'})}}]}}],
            'usage':{'prompt_tokens':1,'completion_tokens':1,'total_tokens':2}})
    with httpx.Client(transport=httpx.MockTransport(serve)) as client:
        models=_models();models['specialist']=model(http_client=client,research_checkpoint_tokens=48000)
        adapter=DeepSeekStructuredAgentAdapter(config=_config().model_copy(update={'agentic_message_history':True,
            'runtime_context_binding':True}),chat_models=models)
        request=_agentic_turn_request();request.update(turn_index=6,allowed_actions=['read_research_history'],
            terminal_result={'accepted':accepted,'feedback':[] if accepted else ['real_error']},
            revision_submission_status={'status':'not_submitted' if accepted else 'rejected',
                'baseline_accepted':True,'baseline_digest':'version'},
            task_context={'research_question':'Original assignment','revision_feedback':[{'finding_id':'F1'}],
                'accepted_revision_baseline':{'through_model_turn':5,'submission_digest':'version'}})
        request['notebook']['model_turn_count']=5
        adapter._agentic_history[request['agent_id']]=[SystemMessage(content='Original system'),
            HumanMessage(content=json.dumps({'allowed_actions':['read_research_history'],
                'task_context':{'research_question':'Original assignment'}})),
            AIMessage(content='',tool_calls=[{'id':'old-submit','name':'SubmitWorkpaperAction','args':{'thesis':'Saved'}}],
                additional_kwargs={'reasoning_content':'old completed reasoning'})]
        adapter.specialist_model_turn(request)
        history=adapter._agentic_history[request['agent_id']]
        receipt=adapter.read_public_operation(request['agent_id'],'old-submit')['receipt']
        assert receipt['result']['accepted'] is accepted
        if accepted:
            assert isinstance(history[-2],HumanMessage)
            assert history[-2].additional_kwargs['fin_research_stage_boundary']=='accepted_submission_to_revision'
            assert 'current_context' not in json.loads(history[-3].content)
            assert [m['role'] for m in captured[0]['messages']]==['system','user']
            assert 'old completed reasoning' not in json.dumps(captured[0])
            view=json.loads(captured[0]['messages'][1]['content'])
            assert next(r for r in view['operation_catalog'] if r['tool_call_id']=='old-submit')['accepted'] is True
            from langchain_core.messages import messages_from_dict
            # Restart from the complete journal, then keep the next error live.
            adapter._agentic_history[request['agent_id']]=messages_from_dict([
                {'type':m.type,'data':m.model_dump(mode='json')} for m in history])
            request['turn_index']=7
            request['notebook']['model_turn_count']=6
            request.pop('terminal_result')
            request['tool_results']=[{'name':'ReadResearchHistoryAction','tool_call_id':'new-call',
                'status':'error','content':json.dumps({'error':'current_locator_error'})}]
            adapter.specialist_model_turn(request)
            assert 'current_locator_error' in captured[1]['messages'][-1]['content']
            assert captured[1]['messages'][-2]['tool_calls'][0]['id']=='new-call'
            assert adapter.read_public_operation(request['agent_id'],'old-submit')['receipt']['result']['accepted'] is True
            assert sum(bool(m.additional_kwargs.get('fin_research_stage_boundary'))
                       for m in adapter._agentic_history[request['agent_id']])==1
        else:
            assert receipt['status']=='error'
            assert captured[0]['messages'][-1]['role']=='tool'
            assert 'real_error' in captured[0]['messages'][-1]['content']


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


@pytest.mark.parametrize('reads', [1, 3])
def test_operation_tool_uses_native_handler_without_external_dispatch(reads):
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
            if len(self.requests)>reads:return _handoff(req)
            return {'action':'native_tool_batch','context_digest':req['context_digest'],'tool_calls':[{
                'id':'recover-'+str(len(self.requests)),'name':'ReadResearchHistoryAction','args':{'action':'read_research_history',
                'context_digest':req['context_digest'],'section':'operation','tool_call_id':'new','reason_summary':'Read the saved original.'}}]}
    adapter=Adapter();ports=_ToolPorts()
    graph=build_specialist_agentic_state_graph(dependencies=SpecialistAgenticDependencies(model_turn=adapter.turn,
        evidence_tool=ports.evidence,finance_tool=ports.finance,working_state_enabled=True)).compile()
    state=graph.invoke({**_input(), 'max_tool_actions':1},{'recursion_limit':20})
    for request in adapter.requests[1:]:
        receipt=json.loads(request['tool_results'][0]['content'])['historical_record']['receipt']
        assert receipt['result']['observations'][0]['content'][0]['passage_id']=='NEW'
    assert state['notebook']['tool_action_count']==1
    assert len(state['notebook']['dispatched_action_digests'])==1
    assert not ports.calls
