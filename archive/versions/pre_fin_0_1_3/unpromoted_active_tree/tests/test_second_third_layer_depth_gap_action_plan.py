from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "data_expansion"
    / "build_second_third_layer_depth_gap_action_plan.py"
)
SPEC = importlib.util.spec_from_file_location("build_second_third_layer_depth_gap_action_plan", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_action_plan_assigns_lane_specific_routes_and_boundaries() -> None:
    rows = MODULE.build_action_plan(
        matrix_rows=[
            {
                "ticker": "NVDA",
                "company_name": "NVIDIA Corporation",
                "dimensions": {
                    "product_spec_depth": {
                        "target_depth_met": False,
                        "status": "official_product_taxonomy_or_catalog_ready",
                        "gap_class": "product_spec_parser_depth_gap",
                        "reason": "catalog exists",
                        "next_action": "parse specs",
                    },
                    "market_liquidity_depth": {"target_depth_met": True},
                },
            },
            {
                "ticker": "BLK",
                "company_name": "BlackRock, Inc.",
                "dimensions": {
                    "customer_deployment_depth": {
                        "target_depth_met": False,
                        "status": "missing_customer_deployment_signal",
                        "gap_class": "customer_deployment_public_source_gap",
                        "reason": "no client deployment row",
                        "next_action": "search customer rows",
                    }
                },
            },
        ],
        lane_rows=[
            {"ticker": "NVDA", "primary_lane_id": "V1", "primary_lane_name": "Semiconductors / AI Infrastructure"},
            {"ticker": "BLK", "primary_lane_id": "V6", "primary_lane_name": "Banks / Financials / Capital Markets"},
        ],
        family_rows=[
            {
                "ticker": "NVDA",
                "family_id": "gpu_accelerator",
                "family_name": "GPU / Accelerator",
                "query_terms": ["GPU", "Blackwell"],
                "route_ids": ["official_product_surface"],
            }
        ],
    )

    assert len(rows) == 2
    nvda = next(row for row in rows if row["ticker"] == "NVDA")
    blk = next(row for row in rows if row["ticker"] == "BLK")
    assert "architecture_whitepaper_or_technology_brief" in nvda["recommended_source_routes"]
    assert "run_family_specific_spec_parser_on_existing_official_product_surface_or_catalog" in nvda["recommended_source_routes"]
    assert nvda["family_scope"][0]["family_id"] == "gpu_accelerator"
    assert "client_asset_or_platform_deployment_if_disclosed" in blk["recommended_source_routes"]
    assert "no company-wide order value" in blk["claim_boundary"]


def test_product_kpi_gap_source_type_uses_verifier_candidate_presence() -> None:
    rows = MODULE.build_action_plan(
        matrix_rows=[
            {
                "ticker": "ANET",
                "company_name": "Arista Networks",
                "dimensions": {
                    "product_kpi_depth": {
                        "target_depth_met": False,
                        "status": "classified_product_kpi_exact_gap",
                        "gap_class": "filings_taxonomy_available_but_value_unit_period_product_kpi_absent",
                        "reason": "taxonomy exists but no exact row",
                        "next_action": "run parser",
                    }
                },
            },
            {
                "ticker": "IR",
                "company_name": "Ingersoll Rand",
                "dimensions": {
                    "product_kpi_depth": {
                        "target_depth_met": False,
                        "status": "classified_product_kpi_exact_gap",
                        "gap_class": "filings_taxonomy_available_but_value_unit_period_product_kpi_absent",
                        "reason": "taxonomy exists but segment orders need table relation repair",
                        "next_action": "run parser",
                    }
                },
            },
            {
                "ticker": "MCHP",
                "company_name": "Microchip",
                "dimensions": {
                    "product_kpi_depth": {
                        "target_depth_met": False,
                        "status": "classified_product_kpi_exact_gap",
                        "gap_class": "filings_taxonomy_available_but_value_unit_period_product_kpi_absent",
                        "reason": "taxonomy exists but no exact row",
                        "next_action": "run parser",
                    }
                },
            },
        ],
        lane_rows=[
            {"ticker": "ANET", "primary_lane_id": "V1"},
            {"ticker": "IR", "primary_lane_id": "V7"},
            {"ticker": "MCHP", "primary_lane_id": "V1"},
        ],
        family_rows=[],
        product_kpi_verifier_rows=[
            {
                "ticker": "ANET",
                "verifier_reason": "missing_table_coordinates_or_exact_row_binding",
                "row_label": "North America",
                "product_or_segment": "North America",
                "citation_sample": "Net sales by geography [TABLE_START] North America | 2025 | 1,000",
            },
            {
                "ticker": "ANET",
                "verifier_reason": "missing_table_coordinates_or_exact_row_binding",
                "row_label": "Operating expenses",
                "product_or_segment": "Technology support",
                "citation_sample": "Expenses [TABLE_START] Technology support | 2025 | 100",
            },
            {
                "ticker": "IR",
                "verifier_reason": "segment_table_contains_mixed_financial_columns",
                "row_label": "Segment Orders",
                "product_or_segment": "Segment Orders",
                "column_label": "2025",
                "citation_sample": "Segment Results [TABLE_START] Segment Orders | 2025 | 5706.6",
            },
        ],
    )

    by_ticker = {row["ticker"]: row for row in rows}
    assert by_ticker["ANET"]["source_gap_type"] == "non_promotable_public_disclosure_boundary"
    assert by_ticker["ANET"]["product_kpi_verifier_candidate_count"] == 2
    assert by_ticker["ANET"]["product_kpi_verifier_top_reasons"]["missing_table_coordinates_or_exact_row_binding"] == 2
    assert by_ticker["IR"]["source_gap_type"] == "source_specific_table_relation_parser_gap"
    assert by_ticker["MCHP"]["source_gap_type"] == "company_disclosure_value_candidate_absent_or_locator_gap"
    assert by_ticker["MCHP"]["product_kpi_verifier_candidate_count"] == 0
