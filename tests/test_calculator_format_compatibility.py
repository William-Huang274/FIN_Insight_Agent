"""Mechanical format compatibility must not infer units or change source values."""
from copy import deepcopy

import pytest

from sec_agent.research_foundation.method_submission import decode_submission
from sec_agent.research_foundation.method_worker import WorkerAction
from sec_agent.research_foundation.source_bound_calculator import SourceBoundCalculation, calculate_from_sources


def run(literal='1,000', quote='Population 1000 people', name='N_total', unit='people'):
    source={'result_state':'source_bound_passage','writer_citable':True,
            'numeric_fact_authority':False,'passage':quote}
    request=SourceBoundCalculation(expression=name+'-1',operands={name:{
        'source_id':'PASSAGE::fixture','literal':literal,'quote':quote}},
        result_unit=unit,rationale='Protocol fixture; no financial conclusion.')
    return calculate_from_sources(request,lambda _:source)


def test_grouping_and_case_keep_original_input_and_audit():
    result=run()
    assert result['value_decimal']=='999'
    assert result['expression']=='N_total-1'
    operand=result['operands']['N_total']
    assert operand['literal']=='1,000' and operand['quote']=='Population 1000 people'
    parsed=operand['runtime_compatibility_parse']
    assert parsed['rule']=='numeric_thousands_grouping_v1'
    assert parsed['matched_text']=='1000'
    assert not parsed['semantic_inference']
    assert result['runtime_compatibility_parse']['original_expression_and_names_preserved']
    assert not result['financial_semantics_verified']


def test_case_is_not_folded_and_units_are_not_rewritten():
    unit='respondent records; '+ 'scope remains conditional and requires semantic review. '*2
    request={'action':'calculate','result':None,'calculations':[{
        'expression':'A-a','operands':{
            'A':{'source_id':'P','literal':'1000','quote':'Counts 1000 and 2'},
            'a':{'source_id':'P','literal':'2','quote':'Counts 1000 and 2'}},
        'result_unit':unit,'rationale':'Capital and lowercase variables are distinct.'}]}
    before=deepcopy(request)
    action,_=decode_submission(request,WorkerAction)
    result=calculate_from_sources(action.calculations[0],lambda _:dict(
        result_state='source_bound_passage',writer_citable=True,passage='Counts 1000 and 2'))
    assert result['value_decimal']=='998' and result['result_unit']==unit
    assert request==before
    assert not result['financial_semantics_verified']


@pytest.mark.parametrize('literal,quote',[
    ('1,000','Population -1000 people'),
    ('1,000','Population 1000.1 people'),
    ('1,000','Population 10000 people'),
    ('1,000','ID x1000'),
    ('1,000','Population 1.000 people'),
    ('1,000','Population 1e3 people'),
    ('1,000','First 1000 second 1000'),
    ('1,000','Population 10,00 people'),
])
def test_grouping_compatibility_rejects_changed_or_ambiguous_values(literal,quote):
    with pytest.raises(ValueError,match='numeric_literal_not_in_exact_source_quote'):
        run(literal,quote)


def test_exact_lowercase_request_keeps_existing_receipt_shape():
    result=run(literal='1000',name='n')
    assert 'runtime_compatibility_parse' not in result
    assert 'runtime_compatibility_parse' not in result['operands']['n']


@pytest.mark.parametrize('literal,quote', [
    ('1,000', 'Today that number exceeds 1,000, doubling in two months.'),
    ('1000', 'Today that number exceeds 1,000, doubling in two months.'),
    ('1,000', 'The total was 1,000.'),
    ('1,000', 'The total was 1000. It increased.'),
    ('1,000.25', 'The total was 1,000.25, as reported.'),
])
def test_punctuation_after_complete_number_is_not_a_numeric_continuation(literal, quote):
    result = run(literal, quote)
    assert result['operands']['N_total']['quote'] == quote
    assert result['operands']['N_total']['literal'] == literal
    assert not result['financial_semantics_verified']
    assert result['value_decimal'] == ('999.25' if '.25' in literal else '999')


@pytest.mark.parametrize('literal,quote', [
    ('1,000', 'The total was 1,000,000, as reported.'),
    ('1,000', 'The total was 1,000.25, as reported.'),
    ('25', 'The total was 1,000.25, as reported.'),
    ('000', 'The total was 1,000, as reported.'),
])
def test_punctuation_compatibility_still_rejects_partial_numeric_tokens(literal, quote):
    with pytest.raises(ValueError, match='numeric_literal_not_in_exact_source_quote'):
        run(literal, quote)


@pytest.mark.parametrize('name',['_hidden','a.b','a-b','鍙橀噺','x'*33])
def test_unsafe_or_unsupported_names_remain_rejected(name):
    with pytest.raises(ValueError,match='ascii_identifier'):
        run(name=name)


TABLE = "Operating cash flow | 27,747 | | 39,069 |\nInvesting activities | | | |\nPurchases | (22,446) | | (44,924) |"
LAYOUT_QUOTE = TABLE.replace("Investing activities | | | |", "Investing activities | | |")


def layout_calculation(body=TABLE, quote=LAYOUT_QUOTE):
    request = SourceBoundCalculation(expression='a-b', operands={
        'a': {'source_id': 'P08:S007', 'literal': '27,747', 'quote': quote},
        'b': {'source_id': 'P08:S007', 'literal': '22,446', 'quote': quote}},
        result_unit='USD million', rationale='Subtract reported capex magnitude.')
    before = request.model_dump()
    result = calculate_from_sources(request, lambda _: dict(result_state='source_bound_passage',
        writer_citable=True, passage=body, period_end='2025-09-30'))
    assert request.model_dump() == before
    return result


def test_unique_table_layout_restores_exact_original_without_changing_proposal():
    result = layout_calculation()
    assert result['value_decimal'] == '5301'
    for operand in result['operands'].values():
        assert operand['quote'] == TABLE
        assert operand['source_id'] == 'P08:S007'
        recovery = operand['quote_layout_recovery']
        assert recovery['original_input'] == LAYOUT_QUOTE
        assert recovery['normalized_result'] == TABLE
        assert recovery['method'] == 'unique_table_nonempty_cells_v1'
        assert not recovery['financial_semantics_verified']
        assert operand['source_provenance']['period_end'] == '2025-09-30'
    assert not result['financial_semantics_verified']
    exact = layout_calculation(quote=TABLE)
    assert all('quote_layout_recovery' not in x for x in exact['operands'].values())


@pytest.mark.parametrize('body,quote', [
    (TABLE + '\n' + TABLE, LAYOUT_QUOTE),
    (TABLE, LAYOUT_QUOTE.replace('(22,446)', '22,446')),
    (TABLE, LAYOUT_QUOTE.replace('39,069', '39,068')),
    (TABLE, LAYOUT_QUOTE.replace('Purchases', 'Revenue')),
    (TABLE, LAYOUT_QUOTE.replace('Investing activities | | |\n', '')),
])
def test_table_recovery_rejects_ambiguous_or_semantically_changed_quote(body, quote):
    with pytest.raises(ValueError, match='operand_quote_not_in_observed_source'):
        layout_calculation(body, quote)
