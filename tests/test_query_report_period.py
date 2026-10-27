import pytest
from retrieval.query_report_period import explicit_report_period, comparison_starts_with_date


@pytest.mark.parametrize('query', [
    "Acme's 10-Q for November 27, 2025: cash versus November 28, 2024",
    'Acme 10-Q for the quarter ended November 27, 2025 cash',
    'Acme截至2025年11月27日的10-Q中，区分当期和上期现金',
    'Acme截至2025年11月27日季度报告的回购支出',
    'Acme截至2025年11月27日的季度披露，对比2024年11月28日',
])
def test_explicit_report_date_is_separate_from_compared_fact_date(query):
    assert explicit_report_period(query)['value'] == '2025-11-27'


@pytest.mark.parametrize('query', [
    'Acme 10-Q filed on November 27, 2025',
    'Acme November 27, 2025 10-Q',
    'Cash as of November 27, 2025 in the annual report',
    'Acme FY2025 Q1 cash balance',
    'Compare 10-Q for November 27, 2025 and 10-Q for November 28, 2024',
    'Acme于2025年11月27日提交的10-Q',
    '10-Q for February 30, 2025',
])
def test_ambiguous_periods_and_filing_dates_do_not_narrow_scope(query):
    assert explicit_report_period(query) is None


def test_temporal_comparison_does_not_invent_an_unknown_company():
    assert comparison_starts_with_date('对比2024年12月31日的余额', 2)
    assert comparison_starts_with_date('compare December 31, 2024 cash', 7)
    assert not comparison_starts_with_date('compare Unknown and Acme on December 31, 2024', 7)
    assert not comparison_starts_with_date('对比另一家公司在2024年12月31日的余额', 2)
