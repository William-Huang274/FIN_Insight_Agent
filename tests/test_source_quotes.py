import pytest

from sec_agent.research_foundation.source_quotes import contains_source_quote


@pytest.mark.parametrize("quote", [
    "Revenue increased\nby 12.3 %.",
    "Revenue increased by 12.3%.",
    "Revenue   increased by 12.3 % .",
])
def test_pdf_layout_whitespace_is_not_a_new_assertion(quote):
    assert contains_source_quote("Revenue increased\nby 12.3 %. Costs decreased.", quote)


@pytest.mark.parametrize("source,quote", [
    ("Revenue 12.3%", "Revenue 12.4%"),
    ("Revenue -12.3%", "Revenue 12.3%"),
    ("Revenue 1 234", "Revenue 1234"),
    ("Revenue $12 million", "Revenue $12 billion"),
    ("Revenue did not grow.", "Revenue did grow."),
    ("A increased. B decreased. C was flat.", "A increased. C was flat."),
    ("FY2025 revenue", "FY2024 revenue"),
    ("Costs decreased", "Costs Decreased"),
    ("Revenue increased", "Revenueincreased"),
    ("Revenue increased", " \n "),
])
def test_financial_changes_and_noncontiguous_spans_still_fail(source, quote):
    assert not contains_source_quote(source, quote)


def test_separate_exact_spans_can_be_validated_independently():
    source = "A increased. B decreased. C was flat."
    assert all(contains_source_quote(source, quote) for quote in ["A increased.", "C was flat."])
