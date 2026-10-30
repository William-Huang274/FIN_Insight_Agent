from financial_facts.acquisition_window import within_financial_window, financial_period_floor
import pytest


def test_comparative_fact_window_independent_of_filing_catalogue():
    plan={'filings_since':'2023-09-01','financial_period_since':'2022-01-01','as_of':'2026-09-20'}
    fact={'end':'2022-12-31','filed':'2024-02-13'}
    assert within_financial_window(fact,plan)
    assert plan['filings_since']=='2023-09-01'
    assert not within_financial_window({**fact,'filed':'2026-09-21'},plan)
    assert not within_financial_window({**fact,'end':'2021-12-31'},plan)


def test_legacy_window_preserved_and_missing_dates_not_assumed():
    plan={'filings_since':'2023-09-01','as_of':'2026-09-20'}
    assert financial_period_floor(plan)=='2023-09-01'
    assert not within_financial_window({'end':'2022-12-31','filed':'2024-02-13'},plan)
    assert not within_financial_window({'end':'2024-12-31'},plan)
    with pytest.raises(ValueError):financial_period_floor({**plan,'financial_period_since':'2027-01-01'})
