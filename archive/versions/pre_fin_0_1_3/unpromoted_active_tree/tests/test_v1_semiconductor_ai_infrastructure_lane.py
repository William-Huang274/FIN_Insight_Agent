from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = Path("scripts/data_expansion/build_v1_semiconductor_ai_infrastructure_lane.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("build_v1_semiconductor_ai_infrastructure_lane", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_v1_lane_package_builds_playbooks_coverage_and_cases() -> None:
    module = _load_module()
    registry = {
        "registry_digest": "fixture",
        "lanes": [
            {
                "lane_id": "V1",
                "lane_name": "Semiconductors / AI Infrastructure",
                "industry_schema": "semiconductors_hardware",
                "primary_ticker_count": 3,
                "ticker_count": 5,
                "representative_tickers": ["NVDA", "DELL", "ASML"],
                "primary_ticker_universe": ["NVDA", "DELL", "ASML"],
                "ticker_universe": ["NVDA", "DELL", "ASML", "MSFT", "AAPL"],
                "product_taxonomy_scope": ["GPU/accelerator", "AI server/rack", "lithography"],
                "l1_required_facts": ["segment/product revenue", "inventory", "capex"],
                "l1_financial_statement_focus": ["revenue by segment", "inventory", "capex"],
                "l1_company_disclosed_kpi_focus": ["product revenue", "backlog/orders"],
                "l2_trusted_context_sources": ["mainstream_financial_news"],
                "l2_regulatory_or_official_sources": ["export_control_regulators"],
                "l2_official_product_surface_sources": ["company_product_pages"],
                "l3_proxy_sources": ["channel_pricing_quotations", "job_postings_hiring_signals"],
                "l4_discovery_sources": ["common_crawl_index", "unverified_self_media_forums"],
                "public_data_ceiling": ["cannot prove shipments/share"],
                "expected_commercial_gaps": ["IDC shipments/share"],
                "product_coverage_summary": {"product_kpi_ready_ticker_count": 1, "official_product_surface_ticker_count": 3},
                "gap_summary": {"commercial_gap_count": 8},
                "lane_source_coverage_gate": {"status": "gap", "summary": {"requirement_count": 10, "gap_requirement_count": 2, "fail_requirement_count": 0}},
            }
        ],
        "company_assignments": [
            {"ticker": "NVDA", "primary_lane_id": "V1"},
            {"ticker": "DELL", "primary_lane_id": "V1"},
            {"ticker": "ASML", "primary_lane_id": "V1"},
            {"ticker": "MSFT", "primary_lane_id": "V3", "secondary_lane_ids": ["V1"]},
            {"ticker": "AAPL", "primary_lane_id": "V2", "secondary_lane_ids": []},
        ],
    }

    package = module.build_v1_lane_package(registry)

    assert package["validation"]["status"] == "pass"
    assert package["coverage"]["primary_ticker_count"] == 3
    assert len(package["representative_cases"]) == 3
    assert "Financial Statement Focus" in package["analyst_playbook"]
    assert "L4 must stay" in package["source_playbook"]
    assert all("L4_direct_claim_forbidden" in case["eval_gates"] for case in package["representative_cases"])
    assert all(
        "capital_and_financing" in case["required_dimension_ids"]
        and "product_and_production" in case["required_dimension_ids"]
        for case in package["representative_cases"]
    )
