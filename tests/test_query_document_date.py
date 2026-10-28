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


@pytest.mark.parametrize('label',[
    'June 30, 2026 10-Q', '10-Q June 30, 2026',
    '2026-06-30 10-Q', '2026年6月30日的10-Q', '10-Q 2026年6月30日',
    '2026 年 6 月 30 日的 10-Q', '10-Q 2026 年 6 月 30 日'])
def test_document_date_word_order_and_language_share_selector(label):
    from retrieval.fact_period_matching import query_period_requirements
    from retrieval.query_document_date import mask_label_dates
    query=f'Using Cedar {label}, compare cash as of 2025-12-31 and 2024-12-31.'
    plan=plan_query(query,{},policy='conservative.v5')
    assert plan['constraint']['document_date']=='2026-06-30'
    assert query_period_requirements(query)['targets']==[
        {'kind':'date','value':'2025-12-31'},{'kind':'date','value':'2024-12-31'}]
    masked=mask_label_dates(query)
    assert len(masked)==len(query) and masked.index('2025-12-31')==query.index('2025-12-31')
    rows={'right':{'form':'10-Q','period_end':'2026-06-30','publication_date':'2026-08-05'},
          'wrong':{'form':'10-Q','period_end':'2025-06-30','publication_date':'2025-08-06'}}
    assert document_constraint_states(rows,plan)=={'right':'match','wrong':'mismatch'}


@pytest.mark.parametrize('query',[
    'June 30, 2026 and June 30, 2025 balances in the 10-Q',
    'June 30, 2026 10-Q and June 30, 2025 10-Q',
    'February 30, 2026 10-Q', '2026年2月30日的10-Q',
    'June 30, 2026 10-Q/A'])
def test_dates_cannot_cross_prose_or_select_one_of_multiple_filing_labels(query):
    assert document_date(query,'10-Q') is None


def test_amendment_label_is_preserved_and_its_date_is_not_a_fact_date():
    from retrieval.query_document_date import mask_label_dates
    query='June 30, 2026 10-Q/A, cash as of December 31, 2025'
    assert document_date(query,'10-Q/A')['value']=='2026-06-30'
    assert 'June 30, 2026' not in mask_label_dates(query)
    assert 'December 31, 2025' in mask_label_dates(query)
