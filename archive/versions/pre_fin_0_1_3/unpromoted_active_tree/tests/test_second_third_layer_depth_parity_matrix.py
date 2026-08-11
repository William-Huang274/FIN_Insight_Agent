from __future__ import annotations

from sec_agent.layer_acceptance_gates import (
    SECOND_THIRD_LAYER_DEPTH_PARITY_SCHEMA_VERSION,
    build_second_third_layer_depth_parity_matrix,
)


def test_depth_parity_passes_when_all_five_dimensions_have_strong_runtime_rows() -> None:
    payload = build_second_third_layer_depth_parity_matrix(
        company_universe_rows=[{"ticker": "NVDA"}],
        product_kpi_closeout_rows=[{"ticker": "NVDA", "status": "product_kpi_exact_ready"}],
        product_kpi_rows=[
            _row(
                ticker="NVDA",
                source_file="company_reported_product_operating_metric_runtime_rows_v0_1.jsonl",
                source_role="company_disclosed_product_kpi",
                structured_fact_status="exact_fact_materialized",
                exact_value_authority=True,
            )
        ],
        product_spec_rows=[
            _row(
                ticker="NVDA",
                source_file="r17_product_family_evidence_runtime_rows_v0_1.jsonl",
                source_role="technical_product_spec",
                structured_context_type="technical_product_spec",
            )
        ],
        customer_deployment_rows=[
            _row(
                ticker="NVDA",
                source_file="targeted_supply_chain_official_relationship_context_rows_v0_1.jsonl",
                source_role="official_customer_order_or_deployment_event",
                counterparty="xAI",
            )
        ],
        capital_market_rows=[
            _row(
                ticker="NVDA",
                source_file="capital_funding_ownership_context_rows_v0_1.jsonl",
                source_role="capital_structure_disclosure",
                exact_value_authority=True,
            ),
            _row(
                ticker="NVDA",
                source_file="sec_capital_market_event_context_rows_v0_1.jsonl",
                source_role="beneficial_ownership_filing_event",
            ),
        ],
        market_liquidity_rows=[
            _row(
                ticker="NVDA",
                source_file="market_liquidity_driver_context_rows_v0_1.jsonl",
                source_role="market_liquidity_driver",
                metric_name="volume",
            )
        ],
        company_count=1,
    )

    assert payload["schema_version"] == SECOND_THIRD_LAYER_DEPTH_PARITY_SCHEMA_VERSION
    assert payload["status"] == "pass"
    assert payload["parity_status"] == "pass"
    assert payload["metrics"]["full_depth_target_met_company_count"] == 1
    assert payload["backfill_queue"] == []


def test_depth_parity_rejects_generic_product_surface_as_product_spec_depth() -> None:
    payload = build_second_third_layer_depth_parity_matrix(
        company_universe_rows=[{"ticker": "AAPL"}],
        product_kpi_closeout_rows=[{"ticker": "AAPL", "status": "business_segment_metric_ready"}],
        product_kpi_rows=[],
        product_spec_rows=[
            _row(
                ticker="AAPL",
                source_file="official_product_surface_context_rows_v0_1.jsonl",
                source_id="company_product_pages",
                structured_context_type="official_product_taxonomy_context",
            )
        ],
        customer_deployment_rows=[],
        capital_market_rows=[],
        market_liquidity_rows=[],
        company_count=1,
    )

    company = payload["company_rows"][0]
    assert payload["status"] == "pass"
    assert payload["parity_status"] == "fail"
    assert company["dimensions"]["product_kpi_depth"]["status"] == "business_segment_metric_ready_not_product_exact"
    assert company["dimensions"]["product_spec_depth"]["status"] == "official_product_taxonomy_or_catalog_ready"
    assert company["dimensions"]["product_spec_depth"]["target_depth_met"] is False
    assert "product_spec_depth" in company["missing_target_depth_dimensions"]


def test_depth_parity_accepts_strict_product_profile_projector_rows() -> None:
    payload = build_second_third_layer_depth_parity_matrix(
        company_universe_rows=[{"ticker": "NOW"}],
        product_kpi_closeout_rows=[{"ticker": "NOW", "status": "product_kpi_exact_gap"}],
        product_kpi_rows=[],
        product_spec_rows=[
            _row(
                ticker="NOW",
                source_file="company_disclosed_product_profile_context_rows_v0_1.jsonl",
                source_role="official_product_profile_spec",
                source_id="official_product_profile_parser",
                structured_context_type="official_product_profile_spec",
            )
        ],
        customer_deployment_rows=[],
        capital_market_rows=[],
        market_liquidity_rows=[],
        company_count=1,
    )

    product_profile = payload["company_rows"][0]["dimensions"]["product_spec_depth"]
    assert product_profile["status"] == "product_spec_or_business_profile_ready"
    assert product_profile["target_depth_met"] is True


def test_depth_parity_keeps_missing_market_liquidity_as_classified_gap() -> None:
    payload = build_second_third_layer_depth_parity_matrix(
        company_universe_rows=[{"ticker": "MSFT"}],
        product_kpi_closeout_rows=[{"ticker": "MSFT", "status": "product_kpi_exact_gap"}],
        product_kpi_rows=[],
        product_spec_rows=[],
        customer_deployment_rows=[],
        capital_market_rows=[],
        market_liquidity_rows=[],
        company_count=1,
    )

    market = payload["company_rows"][0]["dimensions"]["market_liquidity_depth"]
    assert market["status"] == "missing_market_liquidity_runtime_rows"
    assert market["gap_class"] == "market_liquidity_source_not_materialized"
    assert payload["metrics"]["backfill_queue_counts"]["market_liquidity_depth::market_liquidity_source_not_materialized"] == 1


def test_depth_parity_accepts_runtime_allowed_company_disclosed_brand_kpi_rows() -> None:
    payload = build_second_third_layer_depth_parity_matrix(
        company_universe_rows=[{"ticker": "DECK"}],
        product_kpi_closeout_rows=[{"ticker": "DECK", "status": "product_kpi_exact_ready"}],
        product_kpi_rows=[
            {
                "_source_file": "r17_known_public_product_kpi_repair_runtime_rows_v0_1.jsonl",
                "ticker": "DECK",
                "evidence_ref": "r17_known_public_product_kpi:unit",
                "source_url": "https://ir.example.com/deck",
                "promotion_status": "runtime_fact_allowed",
                "claim_boundary": "company IR brand net sales row",
                "claim_types": ["company_disclosed_product_kpi"],
                "metric_family": "product_revenue",
                "product_or_segment": "HOKA",
                "period": "FY2025",
                "unit": "USD",
                "value": 2233000000.0,
            }
        ],
        product_spec_rows=[],
        customer_deployment_rows=[],
        capital_market_rows=[],
        market_liquidity_rows=[],
        company_count=1,
    )

    product_kpi = payload["company_rows"][0]["dimensions"]["product_kpi_depth"]
    assert product_kpi["status"] == "exact_product_or_business_kpi_ready"
    assert product_kpi["target_depth_met"] is True


def test_depth_parity_accepts_industry_operating_metric_exact_slots_as_business_kpi() -> None:
    payload = build_second_third_layer_depth_parity_matrix(
        company_universe_rows=[{"ticker": "BLK"}],
        product_kpi_closeout_rows=[{"ticker": "BLK", "status": "business_segment_metric_ready"}],
        product_kpi_rows=[
            {
                "_source_file": "industry_operating_metric_slot_rows_v0_1.jsonl",
                "ticker": "BLK",
                "evidence_ref": "industry_operating_metric:blk:aum",
                "source_url": "https://www.sec.gov/Archives/example/blk.htm",
                "promotion_status": "runtime_fact_allowed",
                "claim_boundary": "company-disclosed AUM row",
                "claim_types": ["company_disclosed_industry_operating_metric"],
                "allowed_claims": ["company_disclosed_industry_operating_metric"],
                "metric_family": "aum",
                "product_or_segment": "Assets under management",
                "period": "FY2024",
                "unit": "USD",
                "value": 11000000000000.0,
            }
        ],
        product_spec_rows=[],
        customer_deployment_rows=[],
        capital_market_rows=[],
        market_liquidity_rows=[],
        company_count=1,
    )

    business_kpi = payload["company_rows"][0]["dimensions"]["product_kpi_depth"]
    assert business_kpi["status"] == "exact_product_or_business_kpi_ready"
    assert business_kpi["target_depth_met"] is True


def test_depth_parity_accepts_company_disclosed_revenue_mix_percent_rows() -> None:
    payload = build_second_third_layer_depth_parity_matrix(
        company_universe_rows=[{"ticker": "ADI"}],
        product_kpi_closeout_rows=[{"ticker": "ADI", "status": "product_kpi_exact_gap"}],
        product_kpi_rows=[
            {
                "_source_file": "company_disclosed_product_business_mix_runtime_rows_v0_1.jsonl",
                "ticker": "ADI",
                "evidence_ref": "company_disclosed_product_business_mix:adi:industrial",
                "source_url": "https://www.sec.gov/Archives/example/adi.htm",
                "promotion_status": "runtime_fact_allowed",
                "claim_boundary": "company-disclosed revenue mix percent only",
                "claim_types": ["company_disclosed_product_kpi", "company_disclosed_business_mix_metric"],
                "allowed_claims": ["product_business_revenue_mix_percent"],
                "metric_family": "product_business_revenue_mix_percent",
                "product_or_segment": "Industrial",
                "period": "FY2024",
                "unit": "percent_of_revenue",
                "value": 54.0,
            }
        ],
        product_spec_rows=[],
        customer_deployment_rows=[],
        capital_market_rows=[],
        market_liquidity_rows=[],
        company_count=1,
    )

    business_mix = payload["company_rows"][0]["dimensions"]["product_kpi_depth"]
    assert business_mix["status"] == "exact_product_or_business_kpi_ready"
    assert business_mix["target_depth_met"] is True


def test_depth_parity_accepts_bounded_channel_distribution_proxy_for_customer_dimension() -> None:
    payload = build_second_third_layer_depth_parity_matrix(
        company_universe_rows=[{"ticker": "COST"}],
        product_kpi_closeout_rows=[{"ticker": "COST", "status": "product_kpi_exact_gap"}],
        product_kpi_rows=[],
        product_spec_rows=[],
        customer_deployment_rows=[
            _row(
                ticker="COST",
                source_file="family_channel_distributor_context_rows_v0_1.jsonl",
                source_id="channel_distributor_locator",
                structured_context_type="channel_distributor_locator_context",
            )
        ],
        capital_market_rows=[],
        market_liquidity_rows=[],
        company_count=1,
    )

    distribution = payload["company_rows"][0]["dimensions"]["customer_deployment_depth"]
    assert distribution["status"] == "customer_distribution_or_adoption_proxy_ready"
    assert distribution["target_depth_met"] is True
    assert "inventory" in distribution["next_action"]


def test_depth_parity_accepts_app_marketplace_adoption_proxy_for_customer_dimension() -> None:
    payload = build_second_third_layer_depth_parity_matrix(
        company_universe_rows=[{"ticker": "AAPL"}],
        product_kpi_closeout_rows=[{"ticker": "AAPL", "status": "product_kpi_exact_gap"}],
        product_kpi_rows=[],
        product_spec_rows=[],
        customer_deployment_rows=[
            _row(
                ticker="AAPL",
                source_file="broad_app_store_platform_context_rows_v0_1.jsonl",
                source_id="app_store_rankings",
                structured_context_type="app_marketplace_context",
            )
        ],
        capital_market_rows=[],
        market_liquidity_rows=[],
        company_count=1,
    )

    adoption = payload["company_rows"][0]["dimensions"]["customer_deployment_depth"]
    assert adoption["status"] == "customer_distribution_or_adoption_proxy_ready"
    assert adoption["target_depth_met"] is True
    assert "sell-through" in adoption["next_action"]


def test_depth_parity_accepts_company_disclosed_operating_footprint_for_customer_dimension() -> None:
    payload = build_second_third_layer_depth_parity_matrix(
        company_universe_rows=[{"ticker": "BLK"}],
        product_kpi_closeout_rows=[{"ticker": "BLK", "status": "product_kpi_exact_gap"}],
        product_kpi_rows=[],
        product_spec_rows=[],
        customer_deployment_rows=[
            {
                "_source_file": "industry_operating_metric_slot_rows_v0_1.jsonl",
                "ticker": "BLK",
                "evidence_ref": "industry_operating_metric:blk:aum",
                "source_role": "aum",
                "source_id": "company_sec_filing",
                "source_url": "https://www.sec.gov/Archives/example/blk.htm",
                "parser_status": "value_unit_period_product_citation_parser_pass",
                "promotion_status": "runtime_fact_allowed",
                "claim_boundary": "company-disclosed AUM row",
                "claim_types": ["company_disclosed_industry_operating_metric"],
                "allowed_claims": ["company_disclosed_industry_operating_metric"],
                "metric_family": "aum",
                "product_or_segment": "Assets under management",
                "period": "FY2024",
                "unit": "USD",
                "value": 11000000000000.0,
            }
        ],
        capital_market_rows=[],
        market_liquidity_rows=[],
        company_count=1,
    )

    footprint = payload["company_rows"][0]["dimensions"]["customer_deployment_depth"]
    assert footprint["status"] == "business_operating_footprint_signal_ready"
    assert footprint["target_depth_met"] is True
    assert "operating-footprint" in footprint["next_action"]


def test_depth_parity_accepts_company_disclosed_same_store_component_for_customer_dimension() -> None:
    payload = build_second_third_layer_depth_parity_matrix(
        company_universe_rows=[{"ticker": "AVB"}],
        product_kpi_closeout_rows=[{"ticker": "AVB", "status": "product_kpi_exact_gap"}],
        product_kpi_rows=[],
        product_spec_rows=[],
        customer_deployment_rows=[
            {
                "_source_file": "industry_operating_metric_slot_rows_v0_1.jsonl",
                "ticker": "AVB",
                "evidence_ref": "industry_operating_metric:avb:same-store-component",
                "source_role": "same_store_revenue_growth_component",
                "source_id": "company_sec_filing",
                "source_url": "https://www.sec.gov/Archives/example/avb.htm",
                "parser_status": "industry_operating_metric_slot_parser_pass",
                "promotion_status": "runtime_fact_allowed",
                "claim_boundary": "company-disclosed same-store revenue growth component only",
                "claim_types": ["company_disclosed_industry_operating_metric"],
                "allowed_claims": ["company_disclosed_industry_operating_metric"],
                "metric_family": "same_store_revenue_growth_component",
                "product_or_segment": "Lease rates",
                "period": "FY2024",
                "unit": "percent_change_component",
                "value": 2.2,
            }
        ],
        capital_market_rows=[],
        market_liquidity_rows=[],
        company_count=1,
    )

    footprint = payload["company_rows"][0]["dimensions"]["customer_deployment_depth"]
    assert footprint["status"] == "business_operating_footprint_signal_ready"
    assert footprint["target_depth_met"] is True


def test_depth_parity_accepts_regulated_product_context_as_bounded_customer_proxy() -> None:
    payload = build_second_third_layer_depth_parity_matrix(
        company_universe_rows=[{"ticker": "ABBV"}],
        product_kpi_closeout_rows=[{"ticker": "ABBV", "status": "product_kpi_exact_gap"}],
        product_kpi_rows=[],
        product_spec_rows=[],
        customer_deployment_rows=[
            {
                "_source_file": "targeted_regulated_auto_official_api_context_rows_v0_1.jsonl",
                "ticker": "ABBV",
                "evidence_ref": "targeted_clinicaltrials_api:abbv",
                "requirement_id": "regulated_product_context",
                "source_id": "clinicaltrials_api",
                "source_url": "https://clinicaltrials.gov/api/v2/studies?query.spons=AbbVie&pageSize=2",
                "structured_context_type": "regulated_product_context",
                "parser_status": "source_specific_context_parser_pass",
                "claim_boundary": "Regulatory record supports product/trial/application existence and status context only.",
                "allowed_claims": ["regulated_product_context", "trial_or_regulatory_status_context"],
            }
        ],
        capital_market_rows=[],
        market_liquidity_rows=[],
        company_count=1,
    )

    regulated = payload["company_rows"][0]["dimensions"]["customer_deployment_depth"]
    assert regulated["status"] == "regulated_product_or_identity_context_ready"
    assert regulated["target_depth_met"] is True
    assert "do not infer customer wins" in regulated["next_action"]


def test_depth_parity_accepts_deferred_revenue_as_customer_contract_footprint() -> None:
    payload = build_second_third_layer_depth_parity_matrix(
        company_universe_rows=[{"ticker": "ANET"}],
        product_kpi_closeout_rows=[{"ticker": "ANET", "status": "product_kpi_exact_gap"}],
        product_kpi_rows=[],
        product_spec_rows=[],
        customer_deployment_rows=[
            {
                "_source_file": "sec_financial_statement_metric_runtime_rows_v0_1.jsonl",
                "ticker": "ANET",
                "evidence_ref": "sec_financial_statement_metric:contract-liability",
                "source_id": "sec_financial_statement_data_sets",
                "source_url": "https://data.sec.gov/api/xbrl/companyfacts/CIK0001596532.json",
                "parser_status": "value_unit_period_product_citation_parser_pass",
                "structured_fact_status": "exact_fact_materialized",
                "claim_boundary": "SEC CompanyFacts contract liability row; no product KPI authority.",
                "metric_family": "deferred_revenue",
                "metric_name": "Contract with Customer, Liability, Current",
                "period": "FY2025-FY",
                "unit": "USD",
                "value": 4002600000.0,
                "exact_value_authority": True,
                "can_support_company_exact_fact": True,
            }
        ],
        capital_market_rows=[],
        market_liquidity_rows=[],
        company_count=1,
    )

    contract = payload["company_rows"][0]["dimensions"]["customer_deployment_depth"]
    assert contract["status"] == "customer_contract_liability_footprint_ready"
    assert contract["target_depth_met"] is True
    assert "do not infer customer names" in contract["next_action"]


def test_depth_parity_accepts_customer_operating_footprint_signal_rows() -> None:
    payload = build_second_third_layer_depth_parity_matrix(
        company_universe_rows=[{"ticker": "PGR"}],
        product_kpi_closeout_rows=[{"ticker": "PGR", "status": "product_kpi_exact_gap"}],
        product_kpi_rows=[],
        product_spec_rows=[],
        customer_deployment_rows=[
            {
                "_source_file": "customer_operating_footprint_signal_runtime_rows_v0_1.jsonl",
                "ticker": "PGR",
                "evidence_ref": "customer_operating_footprint_signal:pgr:premium",
                "source_role": "financial_services_operating_metric",
                "source_id": "sec_companyfacts_operating_footprint",
                "source_url": "https://data.sec.gov/api/xbrl/companyfacts/CIK0000080661.json",
                "parser_status": "value_unit_period_product_citation_parser_pass",
                "structured_fact_status": "exact_fact_materialized",
                "allowed_claims": ["company_disclosed_industry_operating_metric"],
                "claim_types": ["company_disclosed_industry_operating_metric"],
                "claim_boundary": "insurance premium operating footprint only",
                "metric_family": "insurance_premiums_or_policies",
                "metric_name": "Direct Premiums Written",
                "period": "FY2025-FY",
                "unit": "USD",
                "value": 84208000000.0,
                "exact_value_authority": True,
                "can_support_company_exact_fact": True,
            }
        ],
        capital_market_rows=[],
        market_liquidity_rows=[],
        company_count=1,
    )

    footprint = payload["company_rows"][0]["dimensions"]["customer_deployment_depth"]
    assert footprint["status"] == "business_operating_footprint_signal_ready"
    assert footprint["target_depth_met"] is True


def test_depth_parity_accepts_customer_contract_footprint_from_operating_projector() -> None:
    payload = build_second_third_layer_depth_parity_matrix(
        company_universe_rows=[{"ticker": "FLNC"}],
        product_kpi_closeout_rows=[{"ticker": "FLNC", "status": "product_kpi_exact_gap"}],
        product_kpi_rows=[],
        product_spec_rows=[],
        customer_deployment_rows=[
            {
                "_source_file": "customer_operating_footprint_signal_runtime_rows_v0_1.jsonl",
                "ticker": "FLNC",
                "evidence_ref": "customer_operating_footprint_signal:flnc:rpo",
                "source_role": "customer_contract_liability_footprint",
                "source_id": "sec_companyfacts_operating_footprint",
                "source_url": "https://data.sec.gov/api/xbrl/companyfacts/CIK0001868941.json",
                "parser_status": "value_unit_period_product_citation_parser_pass",
                "structured_fact_status": "exact_fact_materialized",
                "claim_boundary": "RPO customer contract footprint only; no order value or product revenue authority.",
                "metric_family": "remaining_performance_obligation",
                "metric_name": "Revenue, Remaining Performance Obligation, Amount",
                "period": "FY2026-Q2",
                "unit": "USD",
                "value": 5600000000.0,
                "exact_value_authority": True,
                "can_support_company_exact_fact": True,
            }
        ],
        capital_market_rows=[],
        market_liquidity_rows=[],
        company_count=1,
    )

    contract = payload["company_rows"][0]["dimensions"]["customer_deployment_depth"]
    assert contract["status"] == "customer_contract_liability_footprint_ready"
    assert contract["target_depth_met"] is True
    assert "do not infer customer names" in contract["next_action"]


def test_depth_parity_accepts_store_count_as_operating_footprint() -> None:
    payload = build_second_third_layer_depth_parity_matrix(
        company_universe_rows=[{"ticker": "POOL"}],
        product_kpi_closeout_rows=[{"ticker": "POOL", "status": "product_kpi_exact_gap"}],
        product_kpi_rows=[],
        product_spec_rows=[],
        customer_deployment_rows=[
            {
                "_source_file": "customer_operating_footprint_signal_runtime_rows_v0_1.jsonl",
                "ticker": "POOL",
                "evidence_ref": "customer_operating_footprint_signal:pool:stores",
                "source_role": "store_or_location_footprint",
                "source_id": "sec_companyfacts_operating_footprint",
                "source_url": "https://data.sec.gov/api/xbrl/companyfacts/CIK0000945841.json",
                "parser_status": "value_unit_period_product_citation_parser_pass",
                "structured_fact_status": "exact_fact_materialized",
                "claim_boundary": "Store count operating footprint only; no sales or sell-through authority.",
                "metric_family": "store_or_location_count",
                "metric_name": "Number of Stores",
                "period": "FY2025-FY",
                "unit": "NumberOfReportingUnit",
                "value": 456,
                "exact_value_authority": True,
                "can_support_company_exact_fact": True,
            }
        ],
        capital_market_rows=[],
        market_liquidity_rows=[],
        company_count=1,
    )

    footprint = payload["company_rows"][0]["dimensions"]["customer_deployment_depth"]
    assert footprint["status"] == "business_operating_footprint_signal_ready"
    assert footprint["target_depth_met"] is True


def test_depth_parity_accepts_filing_operating_footprint_context_rows() -> None:
    payload = build_second_third_layer_depth_parity_matrix(
        company_universe_rows=[{"ticker": "STLD"}],
        product_kpi_closeout_rows=[{"ticker": "STLD", "status": "product_kpi_exact_gap"}],
        product_kpi_rows=[],
        product_spec_rows=[],
        customer_deployment_rows=[
            {
                "_source_file": "filing_operating_footprint_context_rows_v0_1.jsonl",
                "ticker": "STLD",
                "evidence_ref": "filing_operating_footprint:stld:sheet_steel",
                "source_role": "production_or_throughput",
                "source_id": "sec_or_fpi_annual_operating_footprint_filing",
                "source_url": "https://www.sec.gov/Archives/example/stld.htm",
                "parser_status": "value_unit_period_product_citation_parser_pass",
                "structured_fact_status": "exact_fact_materialized",
                "claim_boundary": "Annual filing production-volume row only.",
                "metric_family": "production_or_throughput",
                "metric_name": "sheet steel produced",
                "product_or_segment": "sheet steel operations",
                "period": "FY2025",
                "unit": "tons",
                "value": 10_000_000.0,
                "exact_value_authority": True,
                "can_support_company_exact_fact": True,
            }
        ],
        capital_market_rows=[],
        market_liquidity_rows=[],
        company_count=1,
    )

    footprint = payload["company_rows"][0]["dimensions"]["customer_deployment_depth"]
    assert footprint["status"] == "business_operating_footprint_signal_ready"
    assert footprint["target_depth_met"] is True


def test_depth_parity_does_not_accept_product_revenue_as_customer_dimension_footprint() -> None:
    payload = build_second_third_layer_depth_parity_matrix(
        company_universe_rows=[{"ticker": "SHOP"}],
        product_kpi_closeout_rows=[{"ticker": "SHOP", "status": "product_kpi_exact_gap"}],
        product_kpi_rows=[],
        product_spec_rows=[],
        customer_deployment_rows=[
            {
                "_source_file": "company_reported_product_operating_metric_runtime_rows_v0_1.jsonl",
                "ticker": "SHOP",
                "evidence_ref": "product_revenue:shop:subscription",
                "source_role": "product_revenue",
                "source_id": "company_sec_filing",
                "source_url": "https://www.sec.gov/Archives/example/shop.htm",
                "parser_status": "value_unit_period_product_citation_parser_pass",
                "promotion_status": "runtime_fact_allowed",
                "claim_boundary": "company-disclosed product revenue row",
                "metric_family": "product_revenue",
                "product_or_segment": "Subscription Solutions",
                "period": "FY2024",
                "unit": "USD",
                "value": 100.0,
            }
        ],
        capital_market_rows=[],
        market_liquidity_rows=[],
        company_count=1,
    )

    customer_dimension = payload["company_rows"][0]["dimensions"]["customer_deployment_depth"]
    assert customer_dimension["status"] == "missing_customer_deployment_signal"
    assert customer_dimension["target_depth_met"] is False


def test_depth_parity_accepts_non_us_backlog_or_orders_as_customer_footprint() -> None:
    payload = build_second_third_layer_depth_parity_matrix(
        company_universe_rows=[{"ticker": "373220.KS"}],
        product_kpi_closeout_rows=[{"ticker": "373220.KS", "status": "product_kpi_exact_gap"}],
        product_kpi_rows=[],
        product_spec_rows=[],
        customer_deployment_rows=[
            {
                "_source_file": "non_us_product_kpi_local_disclosure_runtime_rows_v0_1.jsonl",
                "ticker": "373220.KS",
                "evidence_ref": "non_us_product_kpi_l1:lges:ess_backlog",
                "source_id": "company_reported_product_operating_metrics",
                "source_url": "https://news.lgensol.com/company-news/press-releases/4303/",
                "parser_status": "value_unit_period_product_citation_parser_pass",
                "structured_fact_status": "exact_fact_materialized",
                "allowed_claims": ["company_disclosed_product_kpi", "backlog_or_orders"],
                "claim_types": ["company_disclosed_product_kpi", "company_reported_product_operating_fact"],
                "claim_boundary": "Issuer-disclosed backlog/order row; no customer identity, revenue, ASP, sell-through, or share authority.",
                "metric_family": "backlog_or_orders",
                "metric_name": "ESS battery order backlog",
                "product_or_segment": "ESS battery",
                "period": "FY2025",
                "unit": "GWh",
                "value": 120.0,
                "exact_value_authority": True,
                "can_support_company_exact_fact": True,
            }
        ],
        capital_market_rows=[],
        market_liquidity_rows=[],
        company_count=1,
    )

    customer_dimension = payload["company_rows"][0]["dimensions"]["customer_deployment_depth"]
    assert customer_dimension["status"] == "business_operating_footprint_signal_ready"
    assert customer_dimension["target_depth_met"] is True
    assert "do not infer revenue" in customer_dimension["next_action"]


def test_depth_parity_does_not_accept_non_us_product_revenue_as_customer_dimension() -> None:
    payload = build_second_third_layer_depth_parity_matrix(
        company_universe_rows=[{"ticker": "300750.SZ"}],
        product_kpi_closeout_rows=[{"ticker": "300750.SZ", "status": "product_kpi_exact_gap"}],
        product_kpi_rows=[],
        product_spec_rows=[],
        customer_deployment_rows=[
            {
                "_source_file": "non_us_product_kpi_local_disclosure_runtime_rows_v0_1.jsonl",
                "ticker": "300750.SZ",
                "evidence_ref": "non_us_product_kpi_l1:catl:product_revenue",
                "source_id": "company_reported_product_operating_metrics",
                "source_url": "http://static.cninfo.com.cn/finalpage/2026-03-10/1225002214.PDF",
                "parser_status": "value_unit_period_product_citation_parser_pass",
                "structured_fact_status": "exact_fact_materialized",
                "allowed_claims": ["company_disclosed_product_kpi", "product_revenue"],
                "claim_types": ["company_disclosed_product_kpi", "company_reported_product_operating_fact"],
                "claim_boundary": "Product revenue exact row only; not a customer deployment, order, channel, or operating footprint signal.",
                "metric_family": "product_revenue",
                "metric_name": "product revenue",
                "product_or_segment": "动力电池系统",
                "period": "FY2025",
                "unit": "CNY",
                "value": 316506369000.0,
                "exact_value_authority": True,
                "can_support_company_exact_fact": True,
            }
        ],
        capital_market_rows=[],
        market_liquidity_rows=[],
        company_count=1,
    )

    customer_dimension = payload["company_rows"][0]["dimensions"]["customer_deployment_depth"]
    assert customer_dimension["status"] == "missing_customer_deployment_signal"
    assert customer_dimension["target_depth_met"] is False


def test_depth_parity_does_not_accept_sec_revenue_as_customer_contract_footprint() -> None:
    payload = build_second_third_layer_depth_parity_matrix(
        company_universe_rows=[{"ticker": "ANET"}],
        product_kpi_closeout_rows=[{"ticker": "ANET", "status": "product_kpi_exact_gap"}],
        product_kpi_rows=[],
        product_spec_rows=[],
        customer_deployment_rows=[
            {
                "_source_file": "sec_financial_statement_metric_runtime_rows_v0_1.jsonl",
                "ticker": "ANET",
                "evidence_ref": "sec_financial_statement_metric:revenue",
                "source_id": "sec_financial_statement_data_sets",
                "source_url": "https://data.sec.gov/api/xbrl/companyfacts/CIK0001596532.json",
                "parser_status": "value_unit_period_product_citation_parser_pass",
                "structured_fact_status": "exact_fact_materialized",
                "claim_boundary": "SEC CompanyFacts revenue row; no product KPI authority.",
                "metric_family": "revenue",
                "metric_name": "Revenue from Contract with Customer, Excluding Assessed Tax",
                "period": "FY2025-FY",
                "unit": "USD",
                "value": 9005700000.0,
                "exact_value_authority": True,
                "can_support_company_exact_fact": True,
            }
        ],
        capital_market_rows=[],
        market_liquidity_rows=[],
        company_count=1,
    )

    customer_dimension = payload["company_rows"][0]["dimensions"]["customer_deployment_depth"]
    assert customer_dimension["status"] == "missing_customer_deployment_signal"
    assert customer_dimension["target_depth_met"] is False


def test_depth_parity_accepts_non_us_primary_capital_disclosure_without_sec_event_route() -> None:
    payload = build_second_third_layer_depth_parity_matrix(
        company_universe_rows=[{"ticker": "005930.KS"}],
        product_kpi_closeout_rows=[{"ticker": "005930.KS", "status": "product_kpi_exact_gap"}],
        product_kpi_rows=[],
        product_spec_rows=[],
        customer_deployment_rows=[],
        capital_market_rows=[
            {
                "_source_file": "non_us_l1_financial_statement_metric_runtime_rows_v0_1.jsonl",
                "ticker": "005930.KS",
                "evidence_ref": "non_us_l1:samsung:liabilities",
                "source_id": "company_ir_reports",
                "source_url": "https://dart.fss.or.kr/example",
                "parser_status": "value_unit_period_product_citation_parser_pass",
                "structured_fact_status": "exact_fact_materialized",
                "claim_boundary": "local annual report balance-sheet row",
                "metric_family": "liabilities",
                "metric_name": "Total liabilities",
                "period": "FY2025",
                "unit": "KRW",
                "value": 285850383000000.0,
                "exact_value_authority": True,
                "can_support_company_exact_fact": True,
            }
        ],
        market_liquidity_rows=[],
        company_count=1,
    )

    capital = payload["company_rows"][0]["dimensions"]["capital_market_detail_depth"]
    assert capital["status"] == "non_us_primary_capital_disclosure_ready"
    assert capital["target_depth_met"] is True
    assert "local primary capital" in capital["next_action"]


def _row(
    *,
    ticker: str,
    source_file: str,
    source_role: str = "",
    source_id: str = "source",
    structured_context_type: str = "context",
    structured_fact_status: str = "bounded_context_fact_materialized",
    exact_value_authority: bool = False,
    counterparty: str = "",
    metric_name: str = "",
) -> dict:
    return {
        "_source_file": source_file,
        "ticker": ticker,
        "evidence_ref": f"{ticker}:{source_file}:{source_role or source_id}",
        "source_role": source_role,
        "source_id": source_id,
        "source_url": "https://example.com/source",
        "parser_status": "parser_pass",
        "claim_boundary": "bounded test row",
        "structured_context_type": structured_context_type,
        "structured_fact_status": structured_fact_status,
        "exact_value_authority": exact_value_authority,
        "counterparty": counterparty,
        "metric_name": metric_name,
    }
