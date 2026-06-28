from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "data_expansion" / "build_company_gap_docket.py"
SPEC = importlib.util.spec_from_file_location("build_company_gap_docket", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_company_gap_docket_builds_source_and_product_rows() -> None:
    rows = MODULE.build_company_gap_docket_rows(
        source_closeout_rows=[
            {
                "ticker": "NVDA",
                "company_name": "NVIDIA",
                "primary_lane_id": "V1",
                "requirement_id": "channel_offer_proxy",
                "closeout_class": "public_source_exhausted_gap",
                "closeout_reason": "cdw_channel_search_no_verified_sku_price_availability_match",
                "attempt_count": 3,
            },
            {
                "ticker": "2330.TW",
                "company_name": "TSMC",
                "primary_lane_id": "V1",
                "requirement_id": "public_order_proxy",
                "closeout_class": "public_source_exhausted_gap",
                "closeout_reason": "usaspending_no_recipient_bound_award_or_api_fetch_gap",
            },
        ],
        product_kpi_diagnostic_rows=[
            {
                "ticker": "ASML",
                "company_name": "ASML",
                "primary_lane_id": "V1",
                "product_kpi_status": "product_kpi_exact_gap",
                "diagnostic_class": "verifier_business_segment_column_group_required",
                "diagnostic_reason": "source_specific_verifier_business_segment_mixed_table_needs_column_group:segment_table_contains_mixed_financial_columns",
                "strict_candidate_count": 2,
            },
            {
                "ticker": "AAPL",
                "company_name": "Apple",
                "primary_lane_id": "V2",
                "product_kpi_status": "product_kpi_exact_ready",
                "diagnostic_class": "ready_product_kpi_exact",
            },
        ],
        coverage_rows=[
            {"ticker": "NVDA", "coverage_status": "partial_exact_ready", "exact_gap_requirement_count": 1},
            {"ticker": "ASML", "coverage_status": "partial_exact_ready", "exact_gap_requirement_count": 0},
        ],
        family_assignment_rows=[
            {"ticker": "NVDA", "family_id": "gpu_accelerator", "family_name": "GPU / Accelerator"},
            {"ticker": "ASML", "family_id": "semicap_lithography", "family_name": "Semicap Lithography"},
        ],
        family_route_plan_rows=[
            {
                "ticker": "NVDA",
                "route_id": "channel_offer_proxy",
                "route_plan_id": "route:nvda:channel",
                "family_id": "gpu_accelerator",
                "route_status": "not_materialized",
                "source_ids": ["cdw"],
            }
        ],
        generated_at="2026-06-19T00:00:00Z",
    )

    by_key = {(row["docket_type"], row["ticker"], row["requirement_id"]): row for row in rows}
    assert by_key[("source_role", "NVDA", "channel_offer_proxy")]["cluster_id"] == "channel_offer_distributor_marketplace_adapter"
    assert by_key[("source_role", "2330.TW", "public_order_proxy")]["cluster_id"] == "public_order_non_us_local_tender_adapter"
    assert by_key[("product_kpi", "ASML", "product_kpi_exact_slot")]["cluster_id"] == "product_kpi_column_group_schema_verifier"
    assert ("product_kpi", "AAPL", "product_kpi_exact_slot") not in by_key
    assert by_key[("source_role", "NVDA", "channel_offer_proxy")]["family_ids"] == ["gpu_accelerator"]


def test_company_gap_docket_summary_requires_no_unclassified_rows() -> None:
    rows = [
        {
            "ticker": "A",
            "docket_type": "source_role",
            "requirement_id": "channel_offer_proxy",
            "cluster_id": "channel_offer_distributor_marketplace_adapter",
            "priority": "high",
            "completion_state": "needs_adapter_batch",
            "primary_lane_id": "V1",
            "family_ids": ["gpu_accelerator"],
        },
        {
            "ticker": "B",
            "docket_type": "product_kpi",
            "requirement_id": "product_kpi_exact_slot",
            "cluster_id": "product_kpi_non_us_ir_local_exchange_parser",
            "priority": "high",
            "completion_state": "needs_non_us_disclosure_adapter",
            "primary_lane_id": "V1",
            "family_ids": ["memory"],
        },
    ]
    clusters = MODULE.build_adapter_cluster_queue(docket_rows=rows, generated_at="2026-06-19T00:00:00Z")
    summary = MODULE.build_summary(
        docket_rows=rows,
        cluster_rows=clusters,
        generated_at="2026-06-19T00:00:00Z",
        output_docket=Path("docket.jsonl"),
        output_clusters=Path("clusters.jsonl"),
        output_report=Path("report.md"),
    )

    assert summary["status"] == "pass"
    assert summary["docket_count"] == 2
    assert summary["source_role_gap_docket_count"] == 1
    assert summary["product_kpi_gap_docket_count"] == 1
    assert summary["unclassified_docket_count"] == 0
    assert len(clusters) == 2
