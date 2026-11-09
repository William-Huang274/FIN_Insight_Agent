import json
from hashlib import sha256
import pytest
from sec_agent.research_foundation.source_bound_calculator import SourceBoundCalculation, calculate_from_sources, OperandSourceError
from sec_agent.research_foundation.source_quotes import literal_contexts, resolve_quote
from sec_agent.agent_runtime.conversation_tools import operand_source_feedback
from sec_agent.agent_runtime.harness_business_tools import model_receipt
from langchain_core.messages import ToolMessage


def fixture(rows=1):
    row = {'start_utc': '2026-01-01T15:00:00Z', 'end_utc': '2026-01-01T16:00:00Z', 'close': 119.7699966430664}
    text = '{}\n' + '\n'.join([json.dumps(row)]*rows)
    item = dict(source_kind='market_observations', result_state='source_bound_passage', writer_citable=True,
                passage=text, content_sha256=sha256(text.encode()).hexdigest())
    return item, {k: row[k] for k in ('start_utc','end_utc')} | {'field':'close'}


def test_exact_field_preserves_raw_value_and_context():
    item, selector = fixture()
    req = SourceBoundCalculation(expression='a/2', operands={'a':{'source_id':'p','observation_field':selector}}, result_unit='USD', rationale='fixture')
    out = calculate_from_sources(req, lambda _: item)
    assert out['value_decimal'] == '59.8849983215332'
    assert out['operands']['a']['observation_field'] == selector
    assert not out['financial_semantics_verified']


@pytest.mark.parametrize('change', ['date','field','duplicate','literal','digest'])
def test_no_guessing_record_or_field(change):
    item, selector = fixture(2 if change=='duplicate' else 1)
    operand={'source_id':'p','observation_field':selector}
    if change=='date':selector['end_utc']='2026-01-02T16:00:00Z'
    if change=='field':selector['field']='adjusted_close'
    if change=='literal':operand['literal']='119.77'
    if change=='digest':item['content_sha256']='bad'
    req=SourceBoundCalculation(expression='a/2',operands={'a':operand},result_unit='USD',rationale='fixture')
    with pytest.raises(OperandSourceError):calculate_from_sources(req,lambda _:item)


def test_rounded_quote_feedback_does_not_execute_or_modify():
    item,_=fixture()
    req=SourceBoundCalculation(expression='a/2',operands={'a':{'source_id':'p','literal':'119.77','quote':'"close": 119.77'}},result_unit='USD',rationale='fixture')
    with pytest.raises(OperandSourceError) as err:calculate_from_sources(req,lambda _:item)
    feedback=operand_source_feedback(err.value,[])
    assert feedback['observed_fields'][0]['value_decimal']=='119.7699966430664'
    assert req.operands['a'].literal=='119.77'
    receipt=model_receipt(ToolMessage(name='calculate_research_metric',tool_call_id='x',status='error',content=json.dumps(feedback)))
    assert receipt['execution_stop'] is False
    fatal=model_receipt(ToolMessage(name='calculate_research_metric',tool_call_id='x',status='error',content='storage failed'))
    assert fatal['execution_stop'] is True


def test_table_candidates_keep_headers_and_multiple_matches_without_accepting_quote():
    text='Period Q3 Q2\nTangible book value (TBV) (non-GAAP)\n107.64 111.09\nOther period\n107.64'
    quote='Tangible book value (non-GAAP) 107.64'
    assert resolve_quote(text,quote)[0] not in text
    windows=literal_contexts(text,'107.64')
    assert len(windows)==2 and all(w['total_matches']==2 for w in windows)
    assert 'Period Q3 Q2' in windows[0]['text']
