from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "data_expansion"
    / "build_sec_financial_statement_metric_runtime_rows.py"
)
SPEC = importlib.util.spec_from_file_location("build_sec_financial_statement_metric_runtime_rows", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_sec_financial_statement_runtime_rows_select_latest_parser_backed_metrics() -> None:
    rows = [
        _fact("MSFT", "revenue", 2023, "FY", "10-K", "2023-07-31", 211000000000),
        _fact("MSFT", "revenue", 2024, "FY", "10-K", "2024-07-30", 245000000000),
        _fact("MSFT", "assets", 2024, "Q3", "10-Q", "2024-04-25", 484000000000, period_role="instant"),
        _fact("MSFT", "other_companyfacts", 2024, "FY", "10-K", "2024-07-30", 1),
        _fact("NVDA", "net_income", 2025, "FY", "10-K", "2025-02-26", 72880000000),
    ]

    result = MODULE.build_sec_financial_statement_metric_runtime_rows(
        fact_rows=rows,
        universe={"MSFT", "NVDA"},
        generated_at="2026-06-18T00:00:00Z",
    )

    runtime = result["rows"]
    assert {row["ticker"] for row in runtime} == {"MSFT", "NVDA"}
    msft_revenue = next(row for row in runtime if row["ticker"] == "MSFT" and row["metric_family"] == "revenue")
    assert msft_revenue["value"] == 245000000000
    assert msft_revenue["source_id"] == "sec_financial_statement_data_sets"
    assert msft_revenue["statement_or_section"] == "income_statement"
    assert msft_revenue["exact_value_authority"] is True
    assert "product_sales_without_product_kpi" in msft_revenue["forbidden_claims"]
    assert not any(row["metric_family"] == "other_companyfacts" for row in runtime)


def test_sec_financial_statement_runtime_summary_reports_uncovered_tickers() -> None:
    result = MODULE.build_sec_financial_statement_metric_runtime_rows(
        fact_rows=[_fact("MSFT", "revenue", 2024, "FY", "10-K", "2024-07-30", 245000000000)],
        universe={"MSFT", "TSM"},
        generated_at="2026-06-18T00:00:00Z",
    )
    summary = MODULE.build_summary(
        rows=result["rows"],
        rejections=result["rejections"],
        universe={"MSFT", "TSM"},
        generated_at="2026-06-18T00:00:00Z",
        input_facts=Path("facts.jsonl"),
        output_rows=Path("rows.jsonl"),
        output_rejections=Path("reject.jsonl"),
    )

    assert summary["runtime_ticker_count"] == 1
    assert summary["uncovered_tickers"] == ["TSM"]


def test_sec_financial_statement_runtime_rows_include_working_capital_metrics() -> None:
    rows = [
        _fact("NVDA", "accounts_receivable", 2025, "FY", "10-K", "2025-02-26", 23065000000, period_role="instant"),
        _fact("NVDA", "inventory", 2025, "FY", "10-K", "2025-02-26", 10398000000, period_role="instant"),
        _fact("NVDA", "accounts_payable", 2025, "FY", "10-K", "2025-02-26", 4975000000, period_role="instant"),
        _fact("NVDA", "deferred_revenue", 2025, "FY", "10-K", "2025-02-26", 2974000000, period_role="instant"),
        _fact("NVDA", "current_liabilities", 2025, "FY", "10-K", "2025-02-26", 16305000000, period_role="instant"),
        _fact("NVDA", "short_term_debt", 2025, "FY", "10-K", "2025-02-26", 1250000000, period_role="instant"),
    ]

    result = MODULE.build_sec_financial_statement_metric_runtime_rows(
        fact_rows=rows,
        universe={"NVDA"},
        generated_at="2026-06-18T00:00:00Z",
        max_metrics_per_ticker=24,
    )

    by_family = {row["metric_family"]: row for row in result["rows"]}
    assert {
        "accounts_receivable",
        "inventory",
        "accounts_payable",
        "deferred_revenue",
        "current_liabilities",
        "short_term_debt",
    } <= set(by_family)
    assert by_family["inventory"]["statement_or_section"] == "balance_sheet"
    assert by_family["accounts_receivable"]["exact_value_authority"] is True
    assert "product_sales_without_product_kpi" in by_family["short_term_debt"]["forbidden_claims"]


def test_sec_runtime_prefers_date_proven_annual_over_ten_k_q4_with_raw_fy_label() -> None:
    annual = _fact("DELL", "revenue", 2025, "FY", "10-K", "2025-03-25", 95567000000)
    annual.update({"start_date": "2024-02-03", "end_date": "2025-01-31", "period_end": "2025-01-31"})
    q4 = _fact("DELL", "revenue", 2025, "FY", "10-K", "2025-03-25", 23931000000)
    q4.update(
        {
            "fact_id": "SECFACT::DELL::revenue::2025::Q4",
            "start_date": "2024-11-02",
            "end_date": "2025-01-31",
            "period_end": "2025-01-31",
            # Reproduce the stale v0.1 label: runtime must recompute from dates.
            "period_role": "annual",
        }
    )

    result = MODULE.build_sec_financial_statement_metric_runtime_rows(
        fact_rows=[q4, annual],
        universe={"DELL"},
        generated_at="2026-08-06T00:00:00Z",
    )

    row = result["rows"][0]
    assert row["value"] == 95567000000
    assert row["period_role"] == "annual"
    assert row["duration_days"] == 364
    assert row["period"] == "FY2025-FY"
    assert row["source_filed_at"] == "2025-03-25"
    assert row["published_at"] == "2025-03-25"
    assert row["as_of_date"] == ""
    assert row["snapshot_at"] == "2026-08-06T00:00:00Z"


def _fact(
    ticker: str,
    metric_family: str,
    fiscal_year: int,
    fiscal_period: str,
    form_type: str,
    filed_date: str,
    value: float,
    *,
    period_role: str = "annual",
) -> dict[str, object]:
    concept_by_metric = {
        "revenue": "Revenues",
        "assets": "Assets",
        "accounts_receivable": "AccountsReceivableNetCurrent",
        "inventory": "InventoryNet",
        "accounts_payable": "AccountsPayableCurrent",
        "deferred_revenue": "ContractWithCustomerLiabilityCurrent",
        "current_liabilities": "LiabilitiesCurrent",
        "short_term_debt": "ShortTermBorrowings",
        "net_income": "NetIncomeLoss",
        "other_companyfacts": "TradingSecurities",
    }
    return {
        "fact_id": f"SECFACT::{ticker}::{metric_family}::{fiscal_year}::{fiscal_period}",
        "ticker": ticker,
        "company_name": f"{ticker} Inc.",
        "metric_family": metric_family,
        "label": metric_family.replace("_", " ").title(),
        "taxonomy": "us-gaap",
        "concept": concept_by_metric.get(metric_family, metric_family.title().replace("_", "")),
        "value": value,
        "unit": "USD",
        "start_date": "" if period_role == "instant" else f"{fiscal_year}-01-01",
        "period_end": f"{fiscal_year}-12-31",
        "end_date": f"{fiscal_year}-12-31",
        "fiscal_year": fiscal_year,
        "fiscal_period": fiscal_period,
        "period_role": period_role,
        "form_type": form_type,
        "filed_date": filed_date,
        "accession_number": f"000-{ticker}-{fiscal_year}",
        "source_url": f"https://data.sec.gov/api/xbrl/companyfacts/CIK{ticker}.json",
    }
