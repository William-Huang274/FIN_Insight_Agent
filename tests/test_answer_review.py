from types import SimpleNamespace
import json
import pytest

from sec_agent.agent_runtime.answer_review import PREFIX, target, version, apply_response


def test_review_lineage_does_not_confuse_first_run_and_later_failed_attempt(tmp_path):
    from uuid import uuid4
    from sec_agent.agent_runtime.answer_review_provider import review_scope_related
    tid,first,failed,current=map(str,[uuid4(),uuid4(),uuid4(),uuid4()])
    args=dict(scope=tid+':'+current,previous_scope=tid+':'+first,
              predecessor_scope=None,lineage_root=tmp_path)
    assert not review_scope_related(tid+':'+failed,**args)
    path=tmp_path/tid/failed/'answer-review-origin.json';path.parent.mkdir(parents=True)
    path.write_text(json.dumps({'run_id':first}),encoding='utf8')
    assert review_scope_related(tid+':'+failed,**args)
    assert not review_scope_related(str(uuid4())+':'+failed,**args)
    path.write_text(json.dumps({'run_id':str(uuid4())}),encoding='utf8')
    assert not review_scope_related(tid+':'+failed,**args)


@pytest.mark.anyio
async def test_review_retry_uses_actual_predecessor_permit_and_preserves_unknown(monkeypatch):
    from sec_agent.agent_runtime.answer_review_provider import authorized_review_retry
    wire='unchanged provider input';basis={'harness_execution_scope':'thread:later-resume'}
    unknown={'call_id':'failed','status':'unknown','basis':basis,
             'fingerprint':version(wire+json.dumps(basis,sort_keys=True))}
    rows={};store=SimpleNamespace(lookup=lambda owner,budget,key:rows.get(key))
    permits=[]
    def permit(root,thread,run,**kw):
        permits.append((thread,run));return {'unknown_call_ids':['failed']}
    monkeypatch.setattr('sec_agent.adapters.explicit_run_recovery.verified_permit',permit)
    args=dict(wire=wire,previous_scope='thread:first-run',predecessor_scope='thread:later-resume',
              same_consultation=False,audit_root='audit',secret='fixture')
    key,result=await authorized_review_retry(store,'owner','budget','original',unknown,**args)
    assert (key,result)==('original:retry:failed',None)
    assert permits==[('thread','later-resume')] and unknown['status']=='unknown'
    for change in ({'wire':'changed input'}, {'predecessor_scope':'other:run'}):
        assert await authorized_review_retry(store,'owner','budget','original',unknown,**{**args,**change})==('original',unknown)
    monkeypatch.setattr('sec_agent.adapters.explicit_run_recovery.verified_permit',lambda *a,**kw:None)
    assert await authorized_review_retry(store,'owner','budget','original',unknown,**args)==('original',unknown)
    rows['original:retry:failed']={'status':'received','call_id':'saved-result'}
    assert await authorized_review_retry(store,'owner','budget','original',unknown,**args)==('original:retry:failed',rows['original:retry:failed'])


def test_challenge_is_bound_to_answer_and_author():
    body = '📘原稿。原稿。'
    msg = SimpleNamespace(type='ai', content=body, additional_kwargs={'harness_session_id':'author'})
    data = dict(version=version(body), offset=4, quote='原稿', question='')
    command = PREFIX+json.dumps(data)
    assert target(command, [msg], 'author')[1] is msg
    with pytest.raises(ValueError, match='author_session'):
        target(command, [msg], 'checker')
    with pytest.raises(ValueError, match='passage_changed'):
        target(PREFIX+json.dumps({**data,'offset':2}), [msg], 'author')


def test_question_only_is_version_bound_and_requires_a_question():
    msg = SimpleNamespace(type='ai',content='a',additional_kwargs={'harness_session_id':'author'})
    data = dict(version=version('a'),offset=0,quote='',question='What supports the segment estimate?')
    assert target(PREFIX+json.dumps(data),[msg],'author')[0].question == data['question']
    with pytest.raises(ValueError, match='requires_passage'):
        target(PREFIX+json.dumps({**data,'question':''}),[msg],'author')


def test_report_review_binds_complete_artifact_not_delivery_summary():
    from sec_agent.agent_runtime.answer_review import author_input
    from sec_agent.agent_runtime.research_graph_contracts import canonical_sha256
    report = {'title':'Complete report', 'narrative_markdown':'Full evidence and interpretation.',
              'citations':{'source-1':{'sources':[{'source_id':'source-1'}]}}}
    msg = SimpleNamespace(type='ai', content='Report delivered.', additional_kwargs={'harness_session_id':'author'})
    command = PREFIX+json.dumps(dict(artifact='report',version=canonical_sha256(report),quote='',offset=0,
                                    question='Check the main explanation.'))
    selected, original = target(command,[msg],'author',report=report,report_version=7)
    assert original.content == report['narrative_markdown']
    assert original.additional_kwargs['citation_bindings'] == report['citations']
    request = json.loads(author_input(selected,original,'Independent opinion'))
    assert request['report_version'] == 7
    assert 'edit_research_report' in request['task'] and 'deliver_current_report' in request['task']
    assert request['original_answer'] != msg.content
    assert '不预设保留旧结构' in request['task']
    assert '增量保存是写入方式' in request['task']
    assert '局部修改受影响' not in request['task']
    resumed = json.loads(author_input(selected, original, 'Independent opinion',
        current_report_version=9, recovery_command='Continue after source transport repair.'))
    assert resumed['report_version'] == 7 and resumed['current_report']['version'] == 9
    assert resumed['current_command'] == 'Continue after source transport repair.'
    assert resumed['current_report']['readback']['tool'] == 'read_current_report'
    assert resumed['original_answer'] == original.content
    with pytest.raises(ValueError,match='report_version_unavailable'):
        target(command,[msg],'author',report={**report,'citations':{}},report_version=7)
    with pytest.raises(ValueError,match='author_session'):
        target(command,[msg],'other',report=report,report_version=7)


def test_reviewer_consumes_maintained_method_and_only_authorized_tools():
    from sec_agent.agent_runtime.answer_review_provider import reviewer_instructions, review_tool_names
    from sec_agent.research_foundation.research_methods import get_research_method
    method = get_research_method('verifier')
    instructions = reviewer_instructions()
    assert method['resource_digest'] in instructions and method['content'] in instructions
    assert instructions.count(method['content']) == 1
    assert not any(name in instructions for name in ('Arm', 'Qualcomm', 'NBC', '2027'))
    assert review_tool_names({'read_source_document':object(),'save_research_report':object()}) == ('read_source_document',)
    allowed = review_tool_names(dict.fromkeys(['get_research_method','read_public_source','read_legislation',
        'read_market_prices','calculate_research_metric','edit_research_report','WriteWorkingNote']))
    assert set(allowed) == {'get_research_method','read_public_source','read_legislation','read_market_prices','calculate_research_metric'}


def test_reviewer_repairable_read_feedback_and_execution_stop_are_distinct():
    from langchain_core.messages import ToolMessage
    from sec_agent.agent_runtime.answer_review_provider import review_tool_feedback, review_tool_names
    result = ToolMessage(content=json.dumps({'code':'source_not_observed',
        'readback':{'tool':'browse_context','arguments':{'region':'sources'}}}),
        status='error',name='read_research_source',tool_call_id='failed-read')
    assert json.loads(review_tool_feedback(result))['status']=='error'
    assert 'browse_context' in review_tool_names({'browse_context':None,'read_saved_result':None})
    for bad in (result.model_copy(update={'artifact':{'execution_stop':True}}),
                result.model_copy(update={'content':'source_integrity_mismatch'})):
        with pytest.raises(ValueError,match='source_tool_failed'):
            review_tool_feedback(bad)


def test_author_receives_observed_fields_for_selected_citations_only():
    from sec_agent.agent_runtime.answer_review import author_input, Challenge
    ref, other = 'REF-' + 'a'*16, 'REF-' + 'b'*16
    quote = f'收入增速减去成本增速（Sales − Costs）[{ref}]'
    body = f'{quote}。另一段[{other}]。'
    msg = SimpleNamespace(content=body, additional_kwargs={'citation_bindings':{
        ref:{'source':{'expression':'a-b','result_unit':'USD','value_decimal':'0'}},
        other:{'source':{'publication_date':'2026-01-02'}}}})
    challenge = Challenge(version=version(body), quote=quote, offset=0, question='')
    data = json.loads(author_input(challenge, msg, '独立意见'))
    assert data['cited_receipt_fields'] == {ref:{'expression':'a-b','result_unit':'USD','value_decimal':'0'}}
    assert data['runtime_observations'][0]['operands'] == ['Sales','Costs']
    assert data['independent_review'] == '独立意见'


def test_author_replacements_are_atomic_and_relative_to_original():
    body = 'One two three.'
    def patch(*pairs):
        return apply_response(body,json.dumps({'reason':'Compared to source','edits':[dict(before=a,after=b) for a,b in pairs]}))[0]
    assert patch(('One','two'),('two','zero')) == 'two zero three.'
    assert patch() == body
    with pytest.raises(ValueError, match='overlapping'):
        patch(('One two','one'),('two','other'))
    with pytest.raises(ValueError, match='not_unique'):
        patch(('two','one'),('absent','new'))


def test_compaction_keeps_passage_and_exact_table_readback():
    from sec_agent.agent_runtime.answer_review_provider import compact_tool_history
    readback = {'tool': 'read_saved_result', 'arguments': {'tool_call_id':'r1'}}
    item = {'citation_handle':'REF-1','passage':'Original table introduction',
            'source_structure':{'tables':['large table']}}
    raw = json.dumps({'receipt_id':'r1','original_readback':readback,'result':{'items':[item]}})
    original = [dict(type='function_call',call_id='a'),dict(type='function_call_output',call_id='a',output=raw)]
    projected = compact_tool_history(original,set())
    row = json.loads(projected[-1]['output'])['result']['items'][0]
    assert row == {'citation_handle':'REF-1','passage':item['passage'],'structure_readback':readback}
    assert original[-1]['output'] == raw


def test_incomplete_usage_is_not_zero_and_no_review_reasoning_is_public():
    from sec_agent.agent_runtime.answer_review_provider import public_usage_event
    saved = {'stop_required':True,'usage':{},'output':[{'private':'reviewer context'}]}
    public = public_usage_event('call','reviewer',saved)
    assert public['usage_reported'] is False
    assert 'total_tokens' not in public and 'output' not in public


def test_pressure_preserves_input_pairs_and_receipt_readback():
    from sec_agent.agent_runtime.answer_review_provider import fit_review_receipts
    receipt = json.dumps({'receipt_id':'original','result':'x'*8000})
    body = {'input':[{'role':'user','content':'original question'},
                     {'type':'function_call','call_id':'sdk-call'},
                     {'type':'function_call_output','call_id':'sdk-call','output':receipt}]}
    assert len(fit_review_receipts(body, 3000)) < 3000
    output = body['input'][-1]
    assert output['call_id'] == 'sdk-call'
    assert json.loads(output['output'])['original_readback']['arguments']['tool_call_id'] == 'original'
    assert body['input'][0]['content'] == 'original question'


def test_review_pressure_keeps_the_new_batch_even_above_soft_target():
    from sec_agent.agent_runtime.answer_review_provider import fit_review_receipts
    body = {'input':[]}
    for idx in ('earlier', 'current'):
        raw = json.dumps({'receipt_id':idx, 'result':'x'*9000})
        body['input'].extend([{'type':'function_call','call_id':idx},
                              {'type':'function_call_output','call_id':idx,'output':raw}])
    assert len(fit_review_receipts(body, 5000, keep_current=True)) > 5000
    assert json.loads(body['input'][1]['output'])['original_readback']['arguments']['tool_call_id'] == 'earlier'
    assert body['input'][-1]['output'] == raw


def test_review_projection_preserves_prefix_pairs_replay_and_original_readback():
    from copy import deepcopy
    from sec_agent.agent_runtime.answer_review_provider import ReviewReceiptProjection
    history=[{'role':'user','content':'unchanged question'}]
    def batch(call, result):
        return [{'type':'function_call','call_id':call},
                {'type':'function_call_output','call_id':call,'output':json.dumps(result)}]
    history += batch('first',{'receipt_id':'wrapper','result':{'original_tool_call_id':'real-source',
        'json_pointer':'/items/0/passage','content':'x'*18000}})
    history += batch('current',{'receipt_id':'new-source','result':'new evidence'})
    original=deepcopy(history); projection=ReviewReceiptProjection(); body={'input':history}
    wire=projection.project(body,history,set(),10000)
    prefix=deepcopy(body['input'])
    rb=json.loads(prefix[2]['output'])['original_readback']['arguments']
    assert rb=={'tool_call_id':'real-source','offset':0,'json_pointer':'/items/0/passage'}
    assert history==original and prefix[-1]==history[-1]
    history += batch('next',{'receipt_id':'small','result':'next evidence'})
    next_wire=projection.project(body,history,set(),10000)
    assert body['input'][:len(prefix)]==prefix
    replay=ReviewReceiptProjection(); replay_body={'input':[]}
    assert replay.project(replay_body,original,set(),10000)==wire
    assert replay.project(replay_body,history,set(),10000)==next_wire
    assert [x['call_id'] for x in body['input'] if x.get('type')=='function_call']==[
        x['call_id'] for x in body['input'] if x.get('type')=='function_call_output']
def test_related_wording_keeps_unchanged_closing_claim_and_exact_offsets():
    from sec_agent.agent_runtime.revision_context import related_wording
    base = "Pipeline closures reduced repairs for both districts.\n\nBoth districts recorded fewer repairs."
    proposed = base.replace('reduced repairs for both districts', 'changed the available repair hours')
    opinion = 'Available repair hours measure exposure. Fewer repairs in both districts requires comparable observations.'
    matches = related_wording(base, proposed, opinion)
    assert any(row['verbatim_in_base'] and 'Both districts recorded fewer repairs.' in row['excerpt'] for row in matches)
    assert all(proposed.startswith(row['excerpt'], row['offset']) for row in matches)
    assert related_wording(base, proposed, '') == []

def test_review_preview_uses_selected_version_and_rejects_ambiguous_edits():
    from sec_agent.agent_runtime.quantitative_prose import quantitative_prose_tool
    source = 'Both districts recorded fewer repairs.'
    tool = quantitative_prose_tool('old answer', lambda: (source, source)).tool
    runtime = SimpleNamespace(state={'messages': []})
    candidate = 'Both districts recorded fewer repairs in June.'
    result = tool.func(runtime, edits=[{'before':source, 'after':candidate}])
    assert any(row['excerpt'] == candidate for row in result['related_wording'])
    feedback = tool.func(runtime, edits=[{'before':'old answer', 'after':'unrelated'}])
    assert feedback['status'] == 'proposal_needs_correction' and feedback['anchor_counts'] == [0]
