import copy

from sec_agent.agent_runtime.source_fact_checks import (
    fact_consistency_issues, source_fact_hints, with_source_fact_hints,
)


def test_currency_table_and_inline_conversion_preserve_original():
    text = 'Net Revenue (US$ billions) 40.20\nRevenue US$44.6 billion and US$45.8 billion.'
    hints = source_fact_hints(text)
    assert {a['display_zh'] for a in hints['amounts']} == {'402.00 亿美元', '446.0 亿美元', '458.0 亿美元'}
    original = {'result_state': 'source_bound_passage', 'passage': text, 'content_sha256': 'unchanged'}
    before = copy.deepcopy(original)
    displayed = with_source_fact_hints(original)
    assert original == before and displayed['passage'] == text
    assert displayed['content_sha256'] == 'unchanged'
    assert len(fact_consistency_issues('收入40.20亿美元，指引45.8亿美元', [text])) == 2
    assert not fact_consistency_issues('收入402亿美元，指引446–458亿美元', [text])


def test_same_mantissa_legitimate_distinct_amount_not_rejected():
    text = 'Revenue US$40.2 billion. A separate cost US$4.02 billion.'
    assert not fact_consistency_issues('另一成本40.2亿美元', [text])
    assert not fact_consistency_issues('收入40.2 billion美元', [text])
    assert not fact_consistency_issues('成本40.2亿美元', ['Revenue NT$40.2 billion'])
    assert not fact_consistency_issues('成本40.2亿美元', ['Revenue $40.2 billion'])


def test_fiscal_not_calendar_and_mixed_periods_left_for_review():
    text = 'First Quarter Fiscal 2027. Quarter ended April 26, 2026.'
    assert fact_consistency_issues('2026财年Q1收入', [text])[0]['code'] == 'explicit_fiscal_year_conflict'
    assert not fact_consistency_issues('FY2027 Q1，截至2026-04-26', [text])
    assert not fact_consistency_issues('2026年4月季度', [text])
    assert not fact_consistency_issues('2026财年比较', [text + ' Compared with fiscal 2026.'])
    assert not fact_consistency_issues('2027财年', ['Quarter ended April 2026.'])


def test_navigation_snippets_are_not_numeric_evidence():
    row = {'result_state': 'retrieval_candidate', 'passage': 'US$40.2 billion'}
    assert with_source_fact_hints(row) == row
