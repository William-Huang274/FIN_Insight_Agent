from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "data_expansion" / "build_company_product_evidence_graph.py"
SPEC = importlib.util.spec_from_file_location("build_company_product_evidence_graph", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _source_matrix() -> dict[str, dict[str, object]]:
    return {
        "sec_edgar_apis": {
            "source_id": "sec_edgar_apis",
            "information_strength_tier": "S5_primary_authority",
            "materialization_status": "materialized",
            "sec_structured_fact_row_count": 10,
        },
        "company_ir_reports": {
            "source_id": "company_ir_reports",
            "information_strength_tier": "S5_primary_authority",
            "materialization_status": "materialized",
            "downloaded_document_row_count": 2,
        },
        "company_product_pages": {
            "source_id": "company_product_pages",
            "information_strength_tier": "S4_company_authored_operating_context",
            "materialization_status": "materialized",
            "extended_materialization_record_count": 1,
        },
        "nhtsa_vpic_api": {
            "source_id": "nhtsa_vpic_api",
            "information_strength_tier": "S3_official_regulatory_product_context",
            "materialization_status": "materialized",
            "normalized_snapshot_record_count": 4,
        },
        "fred_api": {
            "source_id": "fred_api",
            "information_strength_tier": "S2_official_macro_industry_context",
            "materialization_status": "materialized",
            "industry_snapshot_observation_count": 7,
        },
    }


def _strategy() -> dict[str, object]:
    return {
        "industry_source_plan": {
            "app_software_consumer_internet": {
                "external_metrics": ["downloads", "active_users"],
                "commercial_market_tracker_sources": ["Sensor Tower"],
            },
            "automotive": {
                "external_metrics": ["registrations"],
                "commercial_market_tracker_sources": ["S&P Global Mobility"],
            },
        }
    }


def test_sec_verified_facts_are_runtime_and_repair_candidates_are_review_only() -> None:
    universe_rows = [
        {
            "ticker": "SOFT",
            "company_name": "Software Co",
            "country": "United States",
            "universe_tier": "test",
            "sector": "Software",
            "category": "SaaS",
        }
    ]
    taxonomy_rows = [
        {
            "ticker": "SOFT",
            "industry_schema": "app_software_consumer_internet",
            "normalized_product_label": "Cloud Product",
        }
    ]
    sec_fact_rows = [
        {
            "ticker": "SOFT",
            "fact_id": "accepted-1",
            "metric_family": "downloads",
            "repair_promotion_status": "monotonic_repair_promoted",
        },
        {
            "ticker": "SOFT",
            "fact_id": "accepted-2",
            "metric_family": "unit_sales_or_deliveries",
            "repair_promotion_status": "operating_metric_repair_promoted",
        }
    ]
    repair_candidate_rows = [
        {
            "ticker": "SOFT",
            "fact_id": "candidate-1",
            "metric_family": "active_users",
        }
    ]

    graph_rows, node_rows, gap_rows = MODULE.build_evidence_graph(
        universe_rows=universe_rows,
        strategy=_strategy(),
        source_matrix=_source_matrix(),
        snapshot_summary={"successful_sources": []},
        taxonomy_rows=taxonomy_rows,
        sec_fact_rows=sec_fact_rows,
        repair_candidate_rows=repair_candidate_rows,
        generated_at="2026-06-11T00:00:00+00:00",
    )

    by_source = {row["source_id"]: row for row in node_rows}
    assert graph_rows[0]["sec_verified_product_kpi_fact_count"] == 2
    assert graph_rows[0]["monotonic_repair_fact_count"] == 1
    assert graph_rows[0]["operating_metric_repair_fact_count"] == 1
    assert graph_rows[0]["sec_repair_candidate_count"] == 1
    assert by_source["sec_product_kpi_parser_verified"]["promotion_status"] == "runtime_fact_allowed"
    assert by_source["sec_product_kpi_parser_verified"]["monotonic_repair_fact_count"] == 1
    assert by_source["sec_product_kpi_parser_verified"]["operating_metric_repair_fact_count"] == 1
    assert by_source["sec_targeted_repair_candidate_review"]["promotion_status"] == "review_queue_not_runtime_fact"
    assert "runtime product KPI fact" in by_source["sec_targeted_repair_candidate_review"]["forbidden_claims"]
    assert all(row["missing_metric"] != "downloads" for row in gap_rows)
    assert any(row["missing_metric"] == "active_users" for row in gap_rows)


def test_commercial_gaps_are_exposed_only_after_public_sources_checked() -> None:
    universe_rows = [
        {
            "ticker": "AUTO",
            "company_name": "Auto Co",
            "country": "United States",
            "universe_tier": "test",
            "sector": "Automotive",
            "category": "Vehicle OEM",
        }
    ]

    graph_rows, node_rows, gap_rows = MODULE.build_evidence_graph(
        universe_rows=universe_rows,
        strategy=_strategy(),
        source_matrix=_source_matrix(),
        snapshot_summary={"successful_sources": []},
        taxonomy_rows=[],
        sec_fact_rows=[],
        repair_candidate_rows=[],
        generated_at="2026-06-11T00:00:00+00:00",
    )

    commercial_gap = next(row for row in gap_rows if row["gap_type"] == "commercial_market_tracker_gap_after_public_source_check")
    company_kpi_gap = next(row for row in gap_rows if row["gap_type"] == "company_disclosed_product_kpi_not_verified")
    nhtsa_node = next(row for row in node_rows if row["source_id"] == "nhtsa_vpic_api")

    assert graph_rows[0]["company_disclosed_kpi_gap"] is True
    assert commercial_gap["gap_status"] == "expose_to_agent_as_gap_not_fallback"
    assert "nhtsa_vpic_api" in commercial_gap["public_sources_checked"]
    assert commercial_gap["commercial_sources_that_would_fill"] == ["S&P Global Mobility"]
    assert nhtsa_node["promotion_status"] == "context_or_lead_available"
    assert "company product sales" in nhtsa_node["forbidden_claims"]
    assert company_kpi_gap["gap_status"] == "public_source_gap_or_parser_review_required"
