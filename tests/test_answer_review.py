from types import SimpleNamespace
import json
import pytest

from sec_agent.agent_runtime.answer_review import PREFIX, target, version, apply_response


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
