from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "data_expansion"
    / "build_capital_funding_ownership_context_rows.py"
)
SPEC = importlib.util.spec_from_file_location("build_capital_funding_ownership_context_rows", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_capital_funding_ownership_projection_separates_capital_and_lagged_ownership() -> None:
    rows, summary = MODULE.build_capital_funding_ownership_context_rows(
        capital_ownership_rows=[
            {
                "object_type": "DebtInstrument",
                "company_id": "A",
                "source_id": "sec_annual_debt_footnote_chunk",
                "evidence_ref": "A:debt",
                "principal": "300",
                "currency": "USD millions",
                "maturity_date": "2026-09-22",
                "coupon": "3.05%",
                "source_statement": "The notes mature on September 22, 2026.",
            },
            {
                "object_type": "OwnershipPosition",
                "company_id": "AAPL",
                "source_id": "sec_ownership_and_13f",
                "evidence_ref": "13f:aapl",
                "investor_id": "Example Fund",
                "report_period": "2026-03-31",
                "filing_date": "2026-05-15",
                "not_realtime_flag": True,
                "shares": "100",
                "value": "123",
            },
        ],
        financial_statement_rows=[
            {
                "ticker": "NVDA",
                "company_name": "NVIDIA",
                "source_id": "sec_financial_statement_data_sets",
                "evidence_ref": "NVDA:inventory",
                "metric_family": "inventory",
                "metric_name": "Inventory, Net",
                "value": 10398000000,
                "unit": "USD",
                "period": "FY2025-FY",
                "period_end": "2025-01-26",
                "filing_date": "2025-02-26",
                "citation_span": "SEC CompanyFacts reports Inventory, Net = 10398000000 USD.",
            }
        ],
        generated_at="2026-06-24T00:00:00Z",
    )

    by_role = {row["source_role"]: row for row in rows}
    assert summary["row_count"] == 3
    assert by_role["capital_structure_disclosure"]["source_layer_id"] == "L1"
    assert by_role["capital_structure_disclosure"]["exact_value_authority"] is True
    assert by_role["lagged_ownership_context"]["source_layer_id"] == "L3"
    assert by_role["lagged_ownership_context"]["exact_value_authority"] is False
    assert "realtime_flow" in by_role["lagged_ownership_context"]["forbidden_claims"]
    assert by_role["working_capital_liquidity"]["source_layer_id"] == "L1"
    assert by_role["working_capital_liquidity"]["metric_family"] == "inventory"
    assert by_role["working_capital_liquidity"]["exact_value_authority"] is True
    assert "product_sales_without_product_kpi" in by_role["working_capital_liquidity"]["forbidden_claims"]
