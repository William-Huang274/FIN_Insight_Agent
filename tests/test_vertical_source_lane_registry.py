from __future__ import annotations

from sec_agent.vertical_source_lane_registry import build_vertical_source_lane_registry, validate_vertical_source_lane_registry


def test_vertical_source_lane_registry_assigns_primary_and_secondary_lanes() -> None:
    universe_rows = [
        {"ticker": "NVDA", "company_name": "NVIDIA Corporation", "sector": "Information Technology", "category": "semiconductors", "sec_download_eligible": "true"},
        {"ticker": "AAPL", "company_name": "Apple Inc.", "sector": "Information Technology", "category": "consumer electronics", "sec_download_eligible": "true"},
        {"ticker": "CRM", "company_name": "Salesforce", "sector": "Information Technology", "category": "software_saas", "sec_download_eligible": "true"},
        {"ticker": "LLY", "company_name": "Eli Lilly", "sector": "Health Care", "category": "pharma", "sec_download_eligible": "true"},
        {"ticker": "TSLA", "company_name": "Tesla", "sector": "Consumer Discretionary", "category": "automotive", "sec_download_eligible": "true"},
        {"ticker": "JPM", "company_name": "JPMorgan Chase", "sector": "Financials", "category": "banking", "sec_download_eligible": "true"},
        {"ticker": "XOM", "company_name": "Exxon Mobil", "sector": "Energy", "category": "oil gas", "sec_download_eligible": "true"},
        {"ticker": "COST", "company_name": "Costco", "sector": "Consumer Staples", "category": "retail", "sec_download_eligible": "true"},
        {"ticker": "MSFT", "company_name": "Microsoft", "sector": "Information Technology", "category": "software cloud devices", "sec_download_eligible": "true"},
        {"ticker": "DELL", "company_name": "Dell Technologies", "sector": "Information Technology", "category": "Information Technology", "sec_download_eligible": "true"},
    ]
    product_nodes = [
        {"ticker": "NVDA", "source_id": "sec_edgar_apis", "industry_schema": "consumer_electronics_semiconductor_hardware", "evidence_layer": "company_disclosed_verified_product_kpi", "promotion_status": "runtime_fact_allowed"},
        {"ticker": "AAPL", "source_id": "company_product_pages", "industry_schema": "consumer_electronics_semiconductor_hardware", "evidence_layer": "official_company_product_surface", "promotion_status": "context_or_lead_available"},
    ]
    product_gaps = [
        {
            "ticker": "NVDA",
            "gap_type": "commercial_market_tracker_gap_after_public_source_check",
            "missing_metric": "vendor_share",
            "commercial_sources_that_would_fill": ["IDC", "Counterpoint"],
        }
    ]
    source_rows = [
        {"source_id": "sec_edgar_apis", "layer_id": "L1", "evidence_graph_status": "exact_authority_ready", "exact_value_authority_ready": True},
        {"source_id": "company_product_pages", "layer_id": "L2", "evidence_graph_status": "runtime_ready_context", "runtime_ready_context": True},
        {"source_id": "channel_pricing_quotations", "layer_id": "L3", "evidence_graph_status": "runtime_ready_context", "runtime_ready_context": True},
    ]

    registry = build_vertical_source_lane_registry(
        universe_rows=universe_rows,
        product_nodes=product_nodes,
        product_gaps=product_gaps,
        product_metric_rows=[],
        official_product_rows=[],
        source_capability_rows=source_rows,
        generated_at="2026-06-17T00:00:00Z",
    )

    assignments = {row["ticker"]: row for row in registry["company_assignments"]}
    assert registry["validation"]["status"] == "pass"
    assert registry["company_count"] == 10
    assert assignments["NVDA"]["primary_lane_id"] == "V1"
    assert assignments["AAPL"]["primary_lane_id"] == "V2"
    assert assignments["CRM"]["primary_lane_id"] == "V3"
    assert assignments["LLY"]["primary_lane_id"] == "V4"
    assert assignments["TSLA"]["primary_lane_id"] == "V5"
    assert assignments["JPM"]["primary_lane_id"] == "V6"
    assert assignments["XOM"]["primary_lane_id"] == "V7"
    assert assignments["COST"]["primary_lane_id"] == "V8"
    assert assignments["MSFT"]["primary_lane_id"] == "V3"
    assert "V1" in assignments["MSFT"]["secondary_lane_ids"]
    assert "V2" in assignments["MSFT"]["secondary_lane_ids"]
    assert assignments["DELL"]["primary_lane_id"] == "V1"
    assert "V2" in assignments["DELL"]["secondary_lane_ids"]
    assert assignments["NVDA"]["product_taxonomy_status"] == "product_kpi_ready"
    assert assignments["AAPL"]["product_taxonomy_status"] == "official_surface_context_ready"
    assert registry["summary"]["by_primary_lane"]["V1"] == 2


def test_vertical_source_lane_registry_validation_rejects_missing_primary() -> None:
    validation = validate_vertical_source_lane_registry(
        assignments=[{"ticker": "BAD", "primary_lane_id": "VX", "lane_source_requirements": {"L1": []}}],
        lanes=[],
        company_count=1,
    )

    assert validation["status"] == "fail"
    assert any(error["type"] == "invalid_primary_lane" for error in validation["errors"])


def test_vertical_source_lane_registry_does_not_misclassify_auto_substrings() -> None:
    registry = build_vertical_source_lane_registry(
        universe_rows=[
            {"ticker": "ADP", "company_name": "Automatic Data Processing", "sector": "Industrials", "category": "human capital management"},
            {"ticker": "ADSK", "company_name": "Autodesk", "sector": "Information Technology", "category": "design software"},
            {"ticker": "ROK", "company_name": "Rockwell Automation", "sector": "Industrials", "category": "industrial automation"},
            {"ticker": "AZO", "company_name": "AutoZone", "sector": "Consumer Discretionary", "category": "retail"},
            {"ticker": "TSLA", "company_name": "Tesla", "sector": "Consumer Discretionary", "category": "automotive"},
            {"ticker": "XPEV", "company_name": "XPENG INC.", "sector": "Consumer Discretionary", "category": "electric vehicles"},
        ],
        product_nodes=[],
        product_gaps=[],
        product_metric_rows=[],
        official_product_rows=[],
        source_capability_rows=[],
        generated_at="2026-06-23T00:00:00Z",
    )

    assignments = {row["ticker"]: row for row in registry["company_assignments"]}
    assert assignments["ADP"]["primary_lane_id"] == "V3"
    assert assignments["ADSK"]["primary_lane_id"] == "V3"
    assert assignments["ROK"]["primary_lane_id"] == "V7"
    assert assignments["AZO"]["primary_lane_id"] == "V8"
    assert assignments["TSLA"]["primary_lane_id"] == "V5"
    assert assignments["XPEV"]["primary_lane_id"] == "V5"
