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


@pytest.mark.parametrize('name',['_hidden','a.b','a-b','变量','x'*33])
def test_unsafe_or_unsupported_names_remain_rejected(name):
    with pytest.raises(ValueError,match='ascii_identifier'):
        run(name=name)
