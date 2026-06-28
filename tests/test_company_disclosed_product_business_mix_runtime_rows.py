from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "data_expansion"
    / "build_company_disclosed_product_business_mix_runtime_rows.py"
)
SPEC = importlib.util.spec_from_file_location("build_company_disclosed_product_business_mix_runtime_rows", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_projects_company_disclosed_revenue_mix_percent() -> None:
    rows, rejects = MODULE.build_company_disclosed_product_business_mix_runtime_rows(
        [_verifier_row()],
        generated_at="2026-06-25T00:00:00Z",
    )

    assert not rejects
    assert len(rows) == 1
    row = rows[0]
    assert row["source_id"] == "company_disclosed_product_business_mix_metrics"
    assert row["structured_context_type"] == "company_disclosed_product_business_mix_percent_fact"
    assert row["exact_value_authority"] is True
    assert row["metric_family"] == "product_business_revenue_mix_percent"
    assert row["unit"] == "percent_of_revenue"
    assert "absolute_product_revenue" in row["forbidden_claims"]


def test_projects_promotable_company_disclosed_product_line_revenue_amount() -> None:
    rows, rejects = MODULE.build_company_disclosed_product_business_mix_runtime_rows(
        [
            _verifier_row(
                ticker="CME",
                company="CME Group",
                verifier_class="promotable_product_category_or_product_line_metric",
                source_specific_parser="sec_cash_markets_business_transaction_fee_table_v0_1",
                product_or_segment="EBS foreign exchange transaction fees",
                matched_product_alias="EBS foreign exchange transaction fees",
                product_node_type="category_or_brand_family",
                row_label="EBS foreign exchange transaction fees",
                column_label="2025",
                period="FY2025",
                fiscal_year=2025,
                unit="USD",
                unit_category="currency",
                value=132600000.0,
                raw_value_text="$ 132.6",
                citation_sample="Cash Markets Business transaction fees [TABLE_START] EBS foreign exchange transaction fees | 132.6 | 131.6 | 1",
            )
        ],
        generated_at="2026-06-25T00:00:00Z",
    )

    assert not rejects
    assert len(rows) == 1
    row = rows[0]
    assert row["source_id"] == "company_disclosed_product_business_revenue_metrics"
    assert row["structured_context_type"] == "company_disclosed_product_business_revenue_amount_fact"
    assert row["metric_family"] == "product_revenue"
    assert row["unit"] == "USD"
    assert "company_disclosed_product_revenue" in row["allowed_claims"]
    assert "market_share" in row["forbidden_claims"]
    assert "absolute_product_revenue" not in row["forbidden_claims"]


def test_rejects_region_channel_and_growth_percent_rows() -> None:
    candidates = [
        _verifier_row(product_or_segment="North America", row_label="North America"),
        _verifier_row(product_or_segment="Distributors", row_label="Distributors"),
        _verifier_row(column_label="YoY growth", raw_value_text="12%", unit="percent", unit_category="percent"),
    ]
    rows, rejects = MODULE.build_company_disclosed_product_business_mix_runtime_rows(
        candidates,
        generated_at="2026-06-25T00:00:00Z",
    )

    assert rows == []
    reasons = {row["rejection_reason"] for row in rejects}
    assert "region_or_geography_mix_not_product_business_mix" in reasons
    assert "channel_or_customer_mix_not_product_business_mix" in reasons
    assert "change_or_growth_percentage_not_revenue_mix_level" in reasons


def test_summary_reports_ticker_and_rejection_counts(tmp_path: Path) -> None:
    runtime_rows, rejection_rows = MODULE.build_company_disclosed_product_business_mix_runtime_rows(
        [_verifier_row(), _verifier_row(product_or_segment="Customers", row_label="Customers")],
        generated_at="2026-06-25T00:00:00Z",
    )
    summary = MODULE.build_summary(
        verifier_rows=[_verifier_row()],
        runtime_rows=runtime_rows,
        rejection_rows=rejection_rows,
        generated_at="2026-06-25T00:00:00Z",
        output_rows=tmp_path / "rows.jsonl",
        output_rejections=tmp_path / "rejects.jsonl",
    )

    assert summary["status"] == "pass"
    assert summary["runtime_row_count"] == 1
    assert summary["runtime_ticker_count"] == 1
    assert summary["rejection_count"] == 1


def _verifier_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "ticker": "ADI",
        "company": "ANALOG DEVICES INC",
        "fact_id": "PRODUCTKPI::ADI::product_revenue::STRUCTURED::1",
        "verifier_id": "product_kpi_source_specific_verifier:1",
        "source_id": "company_product_kpi_facts_structured_metric_parser",
        "source_url": "https://www.sec.gov/Archives/edgar/data/6281/example.htm",
        "source_document_id": "ADI_2024_10K_ITEM8",
        "metric_family": "product_revenue",
        "metric_name": "product revenue",
        "product_or_segment": "Industrial",
        "matched_product_alias": "Industrial",
        "product_node_id": "PRODUCTNODE::ADI::industrial",
        "product_node_type": "segment",
        "product_link_method": "structured_row_label_alias_exact",
        "period": "FY2024",
        "fiscal_year": 2024,
        "unit": "percent_of_revenue",
        "unit_category": "percent_of_revenue",
        "value": 54.0,
        "raw_value_text": "54%",
        "row_label": "Industrial",
        "column_label": "Percent of Fiscal 2024 Revenue",
        "citation_sample": "row=Industrial | column=Percent of Fiscal 2024 Revenue | value=54% | table_context=% of Total Revenue",
    }
    row.update(overrides)
    return row
