import pytest
from retrieval.query_document_date import document_date,matches_document_date
from sec_agent.research_foundation.organization_query_plan import plan_query,document_constraint_states


@pytest.mark.parametrize('query',['In Alpha 10-Q 2025-11-19, find cash at 2025-10-26.',
    'Alpha的10-Q 2025-11-19中现金有多少？','Alpha Form 10-Q · 2025-11-19'])
def test_literal_filing_date_remains_separate_from_fact_date(query):
    plan=plan_query(query,{},policy='conservative.v5')
    assert plan['constraint']['document_date']=='2025-11-19'
    assert 'period_end' not in plan['constraint']
    rows={'filed':{'form':'10-Q','period_end':'2025-10-26','publication_date':'2025-11-19'},
          'ended':{'form':'10-Q','period_end':'2025-11-19','publication_date':'2025-12-01'},
          'other':{'form':'10-Q','period_end':'2025-07-27','publication_date':'2025-08-27'},
          'unknown':{'form':'10-Q'}}
    assert document_constraint_states(rows,plan)=={'filed':'match','ended':'match','other':'mismatch','unknown':'unknown'}


@pytest.mark.parametrize('query',['In the 10-Q compare cash at 2025-11-19 and 2024-11-19.',
    '10-Q 2025-11-19 and 10-Q 2024-11-19','10-Q 2025-02-30'])
def test_fact_dates_multi_document_or_invalid_dates_do_not_become_one_filter(query):
    assert document_date(query,'10-Q') is None


def test_unknown_alternative_date_role_is_not_false_mismatch():
    assert matches_document_date({'publication_date':'2025-12-01'},'2025-11-19') is None
    assert matches_document_date({'period_end':'2025-11-19'},'2025-11-19') is True


def test_filing_label_date_does_not_erase_two_cash_fact_dates():
    from retrieval.fact_period_matching import query_period_requirements
    from retrieval.organization_search_needs import compile_needs
    query='In Alpha 10-Q 2025-11-19, what cash and cash equivalents was reported at 2025-10-26 and 2025-01-26?'
    expected=[{'kind':'date','value':'2025-10-26'},{'kind':'date','value':'2025-01-26'}]
    assert query_period_requirements(query)['targets']==expected
    needs=compile_needs(query,plan_query(query,{},policy='conservative.v5'))
    assert [n['period_target'] for n in needs['needs'] if n.get('concept')=='cash_equivalents']==expected
