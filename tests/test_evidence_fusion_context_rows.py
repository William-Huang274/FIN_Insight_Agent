from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "data_expansion" / "build_evidence_fusion_context_rows.py"
SPEC = importlib.util.spec_from_file_location("build_evidence_fusion_context_rows", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_product_evidence_rows_preserve_fact_context_and_gap_boundaries() -> None:
    rows = MODULE.build_product_evidence_rows(
        fact_rows=[
            {
                "fact_id": "fact_aapl_services_2024",
                "ticker": "AAPL",
                "company": "Apple Inc.",
                "fiscal_year": 2024,
                "period": "FY2024",
                "metric_family": "product_revenue",
                "metric_name": "product revenue",
                "product_or_segment": "Services",
                "unit": "USD",
                "value": 96169000000,
                "raw_value_text": "96,169",
                "citation_span": "Services | 96,169",
            }
        ],
        node_rows=[
            {
                "node_id": "node_review",
                "ticker": "AAPL",
                "company": "Apple Inc.",
                "source_id": "sec_targeted_repair_candidate_review",
                "evidence_layer": "company_disclosed_repair_candidate",
                "promotion_status": "review_queue_not_runtime_fact",
                "record_count": 2,
                "allowed_claims": ["candidate product-KPI evidence for manual/parser review"],
                "forbidden_claims": ["runtime product KPI fact"],
            }
        ],
        gap_rows=[
            {
                "gap_id": "gap_channel_inventory",
                "ticker": "AAPL",
                "company": "Apple Inc.",
                "missing_metric": "channel_inventory",
                "why_public_sources_do_not_fill": "Channel inventory requires commercial tracker data.",
            }
        ],
        generated_at="2026-06-12T00:00:00+00:00",
    )

    by_ref = {row["evidence_ref"]: row for row in rows}
    assert by_ref["fact_aapl_services_2024"]["promotion_status"] == "runtime_fact_allowed"
    assert by_ref["fact_aapl_services_2024"]["exact_value_authority"] is True
    assert by_ref["node_review"]["claim_scope"] == "review_queue_not_runtime_fact"
    assert by_ref["node_review"]["exact_value_authority"] is False
    assert by_ref["gap_channel_inventory"]["promotion_status"] == "gap_exposed_not_fallback"
    assert by_ref["gap_channel_inventory"]["context_only"] is True


def test_public_source_context_rows_are_context_only() -> None:
    rows = MODULE.build_public_source_context_rows(
        inventory_rows=[
            {
                "row_id": "public_inventory_census_2023",
                "source_id": "census_data_api",
                "source_family": "macro_industry_indicator",
                "runtime_source_family": "industry_snapshot",
                "bounded_evidence_eligible": True,
                "promotion_status": "promoted_macro_context",
                "claim_scope": "demographic_or_macro_context_only",
                "allowed_claims": ["macro_context"],
                "forbidden_claims": ["company_sales_or_operating_metric"],
                "attributes": {"metric_name": "B01001_001E", "value": "332387540", "year": "2023"},
            }
        ],
        normalized_evidence_rows=[
            {
                "evidence_id": "PUBLICSOURCE::openfda_api::snapshot",
                "source_id": "openfda_api",
                "primary_source_family": "official_product_status",
                "claim_scope": "regulatory_product_context_only",
                "summary": "openFDA normalized product status rows.",
            }
        ],
        generated_at="2026-06-12T00:00:00+00:00",
    )

    assert len(rows) == 2
    assert {row["source_family"] for row in rows} == {"public_source_context"}
    assert all(row["context_only"] is True for row in rows)
    assert all(row["exact_value_authority"] is False for row in rows)
    assert rows[0]["claim_scope"] == "demographic_or_macro_context_only"
    assert rows[1]["claim_scope"] == "public_context_only"
    assert rows[1]["source_claim_scope"] == "regulatory_product_context_only"
    assert rows[1]["underlying_source_family"] == "official_product_status"
