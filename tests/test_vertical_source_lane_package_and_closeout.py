from __future__ import annotations

from sec_agent.vertical_source_lane_closeout import build_lane_source_coverage_closeout
from sec_agent.vertical_source_lane_package import build_vertical_lane_package
from pathlib import Path
import importlib.util


def test_vertical_lane_package_builds_non_v1_cases() -> None:
    registry = {
        "registry_digest": "fixture",
        "lanes": [
            {
                "lane_id": "V3",
                "lane_name": "SaaS / Cloud / Developer Products",
                "industry_schema": "software_saas",
                "subvertical": "software_cloud_developer_products",
                "primary_ticker_count": 3,
                "ticker_count": 3,
                "representative_tickers": ["MSFT", "CRM", "NOW"],
                "primary_ticker_universe": ["MSFT", "CRM", "NOW"],
                "ticker_universe": ["MSFT", "CRM", "NOW"],
                "key_products_or_services": ["cloud platform", "SaaS subscription"],
                "product_taxonomy_scope": ["cloud infrastructure", "workflow"],
                "l1_required_facts": ["segment revenue", "RPO"],
                "l1_financial_statement_focus": ["subscription revenue", "deferred revenue"],
                "l1_company_disclosed_kpi_focus": ["RPO", "customer count"],
                "l2_trusted_context_sources": ["mainstream_financial_news"],
                "l2_regulatory_or_official_sources": ["official_docs"],
                "l2_official_product_surface_sources": ["company_product_pages"],
                "l3_proxy_sources": ["developer_ecosystem_github_npm_pypi_huggingface"],
                "l4_discovery_sources": ["common_crawl_index"],
                "public_data_ceiling": ["developer activity is proxy only"],
                "expected_commercial_gaps": ["private cloud usage"],
                "product_coverage_summary": {},
                "gap_summary": {"commercial_gap_count": 1},
                "lane_source_coverage_gate": {
                    "status": "gap",
                    "requirements": [
                        {"requirement_id": "primary_company_disclosure"},
                        {"requirement_id": "official_product_surface"},
                    ],
                    "summary": {"requirement_count": 2, "gap_requirement_count": 1, "fail_requirement_count": 0},
                },
            }
        ],
        "company_assignments": [
            {"ticker": "MSFT", "primary_lane_id": "V3", "secondary_lane_ids": []},
            {"ticker": "CRM", "primary_lane_id": "V3", "secondary_lane_ids": []},
            {"ticker": "NOW", "primary_lane_id": "V3", "secondary_lane_ids": []},
        ],
    }

    package = build_vertical_lane_package(registry, "V3")

    assert package["validation"]["status"] == "pass"
    assert package["coverage"]["lane_id"] == "V3"
    assert len(package["representative_cases"]) == 3
    assert "Financial Statement Focus" in package["analyst_playbook"]
    assert all("source_gap_classification_required" in case["eval_gates"] for case in package["representative_cases"])


def test_lane_closeout_filters_other_lane_bridge_rows() -> None:
    lane = {
        "lane_id": "V2",
        "lane_name": "Consumer Electronics / Hardware Devices",
        "industry_schema": "generic_public_research",
        "primary_ticker_universe": ["AAPL"],
        "ticker_universe": ["AAPL"],
        "expected_commercial_gaps": [],
        "lane_source_coverage_gate": {
            "status": "pass",
            "requirements": [
                {"requirement_id": "primary_company_disclosure", "status": "pass"},
                {"requirement_id": "official_product_surface", "status": "pass"},
                {"requirement_id": "trusted_external_context", "status": "pass"},
                {"requirement_id": "macro_official_context", "status": "pass"},
            ],
        },
    }
    source_rows = [
        {"source_id": "sec_edgar_apis", "layer_id": "L1", "evidence_graph_status": "exact_authority_ready"},
        {"source_id": "company_product_pages", "layer_id": "L2", "evidence_graph_status": "runtime_ready_context"},
        {"source_id": "mainstream_financial_news", "layer_id": "L2", "evidence_graph_status": "runtime_ready_context"},
        {"source_id": "fred_api", "layer_id": "L2", "evidence_graph_status": "runtime_ready_context"},
    ]
    base = {
        "ticker": "AAPL",
        "structured_fact_status": "bounded_context_fact_materialized",
        "issuer_binding_status": "issuer_mentioned_in_snapshot",
        "product_binding_status": "product_mentioned_in_snapshot",
        "counterparty_binding_status": "not_bound",
    }
    observed_rows = [
        {**base, "source_id": "sec_edgar_apis", "source_layer_id": "L1", "structured_fact_status": "exact_fact_materialized"},
        {**base, "source_id": "company_product_pages", "source_layer_id": "L2"},
        {**base, "source_id": "mainstream_financial_news", "source_layer_id": "L2"},
        {**base, "source_id": "fred_api", "source_layer_id": "L2"},
        {
            **base,
            "source_id": "industry_association_reports",
            "source_layer_id": "L2",
            "context_scope": "v1_lane_context_routed_to_representative_ticker",
            "evidence_ref": "v1_trusted_external_context:fixture",
        },
    ]

    payload = build_lane_source_coverage_closeout(
        lane_coverage=lane,
        source_layer_capability_rows=source_rows,
        observed_rows=observed_rows,
        generated_at="2026-06-17T00:00:00Z",
    )

    assert payload["status"] == "pass"
    assert payload["summary"]["observed_runtime_row_count"] == 4
    assert payload["summary"]["source_gap_requirement_count"] == 0


def test_vertical_lane_public_context_row_is_bounded_and_lane_scoped() -> None:
    script = _load_script("build_vertical_lane_public_context_rows")
    row = script.make_context_row(
        {
            "lane_id": "V5",
            "source_id": "channel_pricing_quotations",
            "source_class": "channel_pricing_snapshot",
            "url": "https://example.com/model",
            "provider": "Example",
            "title": "Example model page",
            "product_terms": ["vehicle", "configuration"],
            "claim_boundary": "Public channel context only.",
        },
        ticker="GM",
        body="<html><title>GM vehicle configuration</title><body>GM vehicle configuration context</body></html>",
        content_type="text/html",
        raw_path=Path("raw.html"),
        generated_at="2026-06-17T00:00:00Z",
        source_layer_id="L3",
        structured_context_type="channel_offer_context",
        issuer_binding_status="issuer_mentioned_in_snapshot",
        product_binding_status="product_mentioned_in_snapshot",
        counterparty_binding_status="not_bound",
        text_prefix="GM channel context",
    )

    assert row["lane_id"] == "V5"
    assert row["context_only"] is True
    assert row["can_support_company_exact_fact"] is False
    assert row["exact_value_authority"] is False
    assert row["source_specific_parser"] == "vertical_lane_public_context_probe_parser_v0_1"
    assert "issuer_revenue" in row["forbidden_claims"]


def _load_script(name: str):
    path = Path("scripts/data_expansion") / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
