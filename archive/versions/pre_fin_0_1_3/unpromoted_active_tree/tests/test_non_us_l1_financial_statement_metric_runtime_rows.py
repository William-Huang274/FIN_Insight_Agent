from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "data_expansion"
    / "build_non_us_l1_financial_statement_metric_runtime_rows.py"
)
SPEC = importlib.util.spec_from_file_location("build_non_us_l1_financial_statement_metric_runtime_rows", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_parse_non_us_financial_metrics_handles_tw_summary_unit_and_current_year() -> None:
    text = """
項目 110年 111年 112年 113年 114年
營業收入 5,994,174 6,626,997 6,162,221 6,859,615 8,103,105
營業毛利 362,127 400,085 387,947 428,946 498,161
營業利益 148,959 173,788 166,528 200,607 259,223
財務數據及獲利能力分析
單位：百萬新台幣
"""

    metrics = MODULE.parse_financial_metrics(
        text=text,
        ticker="2317.TW",
        candidate={"fiscal_year": 2025},
    )

    by_family = {row["metric_family"]: row for row in metrics}
    assert by_family["revenue"]["value"] == 8103105000000.0
    assert by_family["revenue"]["unit"] == "TWD"
    assert by_family["operating_income"]["period"] == "FY2025"


def test_parse_non_us_financial_metrics_handles_renesas_year_ended_table() -> None:
    text = """
Summary of Consolidated Financial Results (IFRS basis)
 Three months ended December 31, 2025 The year ended December 31, 2025
 Billion yen % of revenue Billion yen % of revenue
 Revenue 351.5 100.0 1,321.2 100.0
 Gross profit 207.3 59.0 753.8 57.1
 Operating profit 67.2 19.1 201.2 15.2
"""

    metrics = MODULE.parse_financial_metrics(
        text=text,
        ticker="6723.T",
        candidate={"fiscal_year": 2025},
    )

    by_family = {row["metric_family"]: row for row in metrics}
    assert by_family["revenue"]["value"] == 1321200000000.0
    assert by_family["gross_profit"]["value"] == 753800000000.0
    assert by_family["operating_income"]["unit"] == "JPY"


def test_parent_segment_alias_projects_fdxf_from_fdx_parent_segment_table() -> None:
    result = MODULE.build_parent_segment_alias_rows(
        product_kpi_rows=[
            {
                "ticker": "FDX",
                "source_url": "https://www.sec.gov/fdx.htm",
                "citation_span": "FedEx Freight segment | 1,489 | 1,821 | (18)",
                "evidence_ref": "PRODUCTKPI::FDX::SEGMENT",
                "filing_type": "10-K",
            }
        ],
        company_by_ticker={"FDXF": {"company_name": "FedEx Freight"}},
        target_tickers={"FDXF"},
        generated_at="2026-06-19T00:00:00Z",
    )

    assert len(result["rows"]) == 1
    row = result["rows"][0]
    assert row["ticker"] == "FDXF"
    assert row["product_or_segment"] == "FedEx Freight segment"
    assert row["value"] == 1489000000.0
