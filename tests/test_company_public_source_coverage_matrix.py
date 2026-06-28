from __future__ import annotations

from sec_agent.company_public_source_coverage_matrix import build_company_public_source_coverage_matrix


def test_company_public_source_coverage_matrix_builds_issuer_level_gaps() -> None:
    assignments = [
        {
            "ticker": "AAPL",
            "company_name": "Apple Inc.",
            "primary_lane_id": "V2",
            "primary_lane_name": "Consumer Electronics / Hardware Devices",
            "secondary_lane_ids": [],
            "sec_download_eligible": True,
            "global_public_download_eligible": True,
            "product_taxonomy_status": "product_kpi_ready",
            "product_coverage": {
                "product_node_count": 3,
                "product_kpi_ready": True,
                "official_surface_ready": True,
                "commercial_gap_count": 2,
                "missing_metrics": {"shipments": 1},
            },
            "expected_commercial_gaps": ["IDC/Counterpoint device shipments/share"],
            "public_data_ceiling": ["public channels cannot prove sell-through"],
        }
    ]
    observed_rows = [
        {
            "ticker": "AAPL",
            "source_id": "company_reported_product_operating_metrics",
            "source_layer_id": "L1",
            "parser_status": "value_unit_period_product_citation_parser_pass",
            "structured_fact_status": "exact_fact_materialized",
            "exact_value_authority": True,
            "can_support_company_exact_fact": True,
            "issuer_binding_status": "issuer_mentioned_in_snapshot",
            "product_binding_status": "product_mentioned_in_snapshot",
            "product_family": "iPhone",
            "evidence_ref": "PRODUCTKPI::AAPL::IPHONE",
        },
        {
            "ticker": "AAPL",
            "source_id": "company_product_pages",
            "source_layer_id": "L2",
            "parser_status": "source_specific_context_parser_pass",
            "structured_fact_status": "bounded_context_fact_materialized",
            "exact_value_authority": False,
            "can_support_company_exact_fact": False,
            "issuer_binding_status": "company_domain_bound",
            "product_binding_status": "product_mentioned_in_snapshot",
            "product_family": "iPhone",
            "evidence_ref": "OFFICIALPRODUCT::AAPL::IPHONE",
        },
    ]
    source_capability_rows = [
        {"source_id": "company_reported_product_operating_metrics", "layer_id": "L1", "evidence_graph_status": "exact_authority_ready"},
        {"source_id": "company_product_pages", "layer_id": "L2", "evidence_graph_status": "runtime_ready_context"},
        {"source_id": "channel_pricing_quotations", "layer_id": "L3", "evidence_graph_status": "runtime_ready_context"},
        {"source_id": "app_store_rankings", "layer_id": "L3", "evidence_graph_status": "runtime_ready_context"},
        {"source_id": "platform_reviews_rankings_downloads", "layer_id": "L3", "evidence_graph_status": "runtime_ready_context"},
        {"source_id": "job_postings_hiring_signals", "layer_id": "L3", "evidence_graph_status": "runtime_ready_context"},
        {"source_id": "fred_api", "layer_id": "L2", "evidence_graph_status": "runtime_ready_context"},
        {"source_id": "mainstream_financial_news", "layer_id": "L2", "evidence_graph_status": "runtime_ready_context"},
    ]

    matrix = build_company_public_source_coverage_matrix(
        company_assignments=assignments,
        observed_rows=observed_rows,
        source_capability_rows=source_capability_rows,
        generated_at="2026-06-18T00:00:00Z",
    )

    row = matrix["rows"][0]
    by_req = {item["requirement_id"]: item for item in row["source_role_matrix"]}
    assert matrix["validation"]["status"] == "pass"
    assert row["status"] == "gap"
    assert by_req["primary_company_disclosure"]["status"] == "pass"
    assert by_req["official_product_surface"]["status"] == "pass"
    assert by_req["channel_offer_proxy"]["status"] == "gap"
    assert by_req["channel_offer_proxy"]["gap_class"] == "source_gap"
    assert by_req["channel_offer_proxy"]["gap_type"] == "company_specific_runtime_row_missing"
    assert row["product_family_summary"]["family_count"] == 1
    assert matrix["summary"]["repair_queue_count"] > 0
    assert matrix["repair_queue"][0]["ticker"] == "AAPL"


def test_company_public_source_coverage_matrix_fails_l3_exact_authority() -> None:
    assignments = [
        {
            "ticker": "AAPL",
            "company_name": "Apple Inc.",
            "primary_lane_id": "V2",
            "primary_lane_name": "Consumer Electronics / Hardware Devices",
        }
    ]
    observed_rows = [
        {
            "ticker": "AAPL",
            "source_id": "channel_pricing_quotations",
            "source_layer_id": "L3",
            "parser_status": "source_specific_context_parser_pass",
            "structured_fact_status": "bounded_context_fact_materialized",
            "exact_value_authority": True,
            "issuer_binding_status": "issuer_mentioned_in_snapshot",
            "product_binding_status": "product_mentioned_in_snapshot",
            "product_family": "iPhone",
        }
    ]

    matrix = build_company_public_source_coverage_matrix(
        company_assignments=assignments,
        observed_rows=observed_rows,
        source_capability_rows=[],
        generated_at="2026-06-18T00:00:00Z",
    )

    row = matrix["rows"][0]
    by_req = {item["requirement_id"]: item for item in row["source_role_matrix"]}
    assert row["status"] == "fail"
    assert by_req["channel_offer_proxy"]["status"] == "fail"
    assert by_req["channel_offer_proxy"]["gap_type"] == "non_l1_exact_authority_violation"
    assert matrix["validation"]["status"] == "fail"


def test_company_public_source_coverage_matrix_uses_family_route_applicability() -> None:
    assignments = [
        {
            "ticker": "AAPL",
            "company_name": "Apple Inc.",
            "primary_lane_id": "V2",
            "primary_lane_name": "Consumer Electronics / Hardware Devices",
        }
    ]
    observed_rows = [
        {
            "ticker": "AAPL",
            "source_id": "company_reported_product_operating_metrics",
            "source_layer_id": "L1",
            "parser_status": "value_unit_period_product_citation_parser_pass",
            "structured_fact_status": "exact_fact_materialized",
            "exact_value_authority": True,
            "issuer_binding_status": "issuer_mentioned_in_snapshot",
            "product_binding_status": "product_mentioned_in_snapshot",
            "product_family": "Mac",
        },
        {
            "ticker": "AAPL",
            "source_id": "company_product_pages",
            "source_layer_id": "L2",
            "parser_status": "source_specific_context_parser_pass",
            "structured_fact_status": "bounded_context_fact_materialized",
            "issuer_binding_status": "company_domain_bound",
            "product_binding_status": "product_mentioned_in_snapshot",
            "product_family": "Mac",
        },
    ]

    matrix = build_company_public_source_coverage_matrix(
        company_assignments=assignments,
        observed_rows=observed_rows,
        source_capability_rows=[],
        family_source_route_plan_rows=[
            {"ticker": "AAPL", "route_id": "primary_company_disclosure"},
            {"ticker": "AAPL", "route_id": "official_product_surface"},
        ],
        generated_at="2026-06-18T00:00:00Z",
    )

    row = matrix["rows"][0]
    by_req = {item["requirement_id"]: item for item in row["source_role_matrix"]}
    assert sorted(by_req) == ["official_product_surface", "primary_company_disclosure"]
    assert row["status"] == "pass"


def test_company_public_source_coverage_matrix_adds_observed_dynamic_capital_roles() -> None:
    matrix = build_company_public_source_coverage_matrix(
        company_assignments=[
            {
                "ticker": "A",
                "company_name": "Agilent Technologies",
                "primary_lane_id": "V4",
                "primary_lane_name": "Pharma / Biotech / Medtech",
            }
        ],
        observed_rows=[
            {
                "ticker": "A",
                "source_id": "sec_annual_debt_footnote_chunk",
                "source_role": "capital_structure_disclosure",
                "source_layer_id": "L1",
                "parser_status": "parser_pass",
                "structured_fact_status": "bounded_context_fact_materialized",
                "issuer_binding_status": "issuer_mentioned_in_snapshot",
                "product_binding_status": "not_applicable",
                "exact_value_authority": True,
                "evidence_ref": "A:debt",
            },
            {
                "ticker": "A",
                "source_id": "sec_ownership_and_13f",
                "source_role": "lagged_ownership_context",
                "source_layer_id": "L3",
                "parser_status": "parser_pass",
                "structured_fact_status": "bounded_context_fact_materialized",
                "issuer_binding_status": "issuer_mentioned_in_snapshot",
                "product_binding_status": "not_applicable",
                "exact_value_authority": False,
                "evidence_ref": "13f:A",
            },
            {
                "ticker": "A",
                "source_id": "sec_financial_statement_data_sets",
                "source_role": "working_capital_liquidity",
                "source_layer_id": "L1",
                "parser_status": "parser_pass",
                "structured_fact_status": "exact_fact_materialized",
                "issuer_binding_status": "issuer_mentioned_in_snapshot",
                "product_binding_status": "not_applicable",
                "exact_value_authority": True,
                "evidence_ref": "A:inventory",
            },
        ],
        source_capability_rows=[],
        family_source_route_plan_rows=[],
        generated_at="2026-06-24T00:00:00Z",
    )

    row = matrix["rows"][0]
    by_req = {item["requirement_id"]: item for item in row["source_role_matrix"]}
    assert by_req["capital_structure_disclosure"]["status"] == "pass"
    assert by_req["lagged_ownership_context"]["status"] == "pass"
    assert by_req["working_capital_liquidity"]["status"] == "pass"


def test_company_public_source_coverage_matrix_records_not_applicable_app_route_exemption() -> None:
    assignments = [
        {
            "ticker": "GTLB",
            "company_name": "GitLab Inc.",
            "primary_lane_id": "V3",
            "primary_lane_name": "Software / Cloud / Developer Products",
        }
    ]
    observed_rows = [
        {
            "ticker": "GTLB",
            "source_id": "company_reported_product_operating_metrics",
            "source_layer_id": "L1",
            "parser_status": "value_unit_period_product_citation_parser_pass",
            "structured_fact_status": "exact_fact_materialized",
            "exact_value_authority": True,
            "issuer_binding_status": "issuer_mentioned_in_snapshot",
            "product_binding_status": "product_mentioned_in_snapshot",
            "product_family": "DevSecOps platform",
        },
        {
            "ticker": "GTLB",
            "source_id": "company_product_pages",
            "source_layer_id": "L2",
            "parser_status": "source_specific_context_parser_pass",
            "structured_fact_status": "bounded_context_fact_materialized",
            "issuer_binding_status": "company_domain_bound",
            "product_binding_status": "product_mentioned_in_snapshot",
            "product_family": "DevSecOps platform",
        },
    ]

    matrix = build_company_public_source_coverage_matrix(
        company_assignments=assignments,
        observed_rows=observed_rows,
        source_capability_rows=[],
        family_source_route_plan_rows=[
            {"ticker": "GTLB", "route_id": "primary_company_disclosure"},
            {"ticker": "GTLB", "route_id": "official_product_surface"},
            {"ticker": "GTLB", "route_id": "app_rank_store_proxy"},
        ],
        generated_at="2026-06-18T00:00:00Z",
    )

    row = matrix["rows"][0]
    by_req = {item["requirement_id"]: item for item in row["source_role_matrix"]}
    assert sorted(by_req) == ["official_product_surface", "primary_company_disclosure"]
    assert row["source_role_exemptions"][0]["requirement_id"] == "app_rank_store_proxy"
    assert row["source_role_exemptions"][0]["status"] == "not_applicable_after_source_probe"
    assert not any(item["requirement_id"] == "app_rank_store_proxy" for item in matrix["repair_queue"])


def test_company_public_source_coverage_matrix_records_developer_route_exemption_after_probe() -> None:
    assignments = [
        {
            "ticker": "DIOD",
            "company_name": "Diodes Incorporated",
            "primary_lane_id": "V1",
            "primary_lane_name": "Semiconductors / AI Infrastructure",
        }
    ]
    observed_rows = [
        {
            "ticker": "DIOD",
            "source_id": "company_reported_product_operating_metrics",
            "source_layer_id": "L1",
            "parser_status": "value_unit_period_product_citation_parser_pass",
            "structured_fact_status": "exact_fact_materialized",
            "exact_value_authority": True,
            "issuer_binding_status": "issuer_mentioned_in_snapshot",
            "product_binding_status": "product_mentioned_in_snapshot",
            "product_family": "Connectivity products",
        },
        {
            "ticker": "DIOD",
            "source_id": "company_product_pages",
            "source_layer_id": "L2",
            "parser_status": "source_specific_context_parser_pass",
            "structured_fact_status": "bounded_context_fact_materialized",
            "issuer_binding_status": "company_domain_bound",
            "product_binding_status": "product_mentioned_in_snapshot",
            "product_family": "Connectivity products",
        },
    ]

    matrix = build_company_public_source_coverage_matrix(
        company_assignments=assignments,
        observed_rows=observed_rows,
        source_capability_rows=[],
        family_source_route_plan_rows=[
            {"ticker": "DIOD", "route_id": "primary_company_disclosure"},
            {"ticker": "DIOD", "route_id": "official_product_surface"},
            {"ticker": "DIOD", "route_id": "developer_ecosystem_proxy"},
        ],
        generated_at="2026-06-18T00:00:00Z",
    )

    row = matrix["rows"][0]
    by_req = {item["requirement_id"]: item for item in row["source_role_matrix"]}
    assert sorted(by_req) == ["official_product_surface", "primary_company_disclosure"]
    assert row["source_role_exemptions"][0]["requirement_id"] == "developer_ecosystem_proxy"
    assert "official product surface" in row["source_role_exemptions"][0]["reason"]
    assert "GitHub/npm developer activity" in row["source_role_exemptions"][0]["reason"]
    assert not any(item["requirement_id"] == "developer_ecosystem_proxy" for item in matrix["repair_queue"])


def test_company_public_source_coverage_matrix_accepts_distributor_locator_for_channel_offer() -> None:
    matrix = build_company_public_source_coverage_matrix(
        company_assignments=[
            {
                "ticker": "PCRFY",
                "company_name": "Panasonic Holdings Corporation",
                "primary_lane_id": "V7",
                "primary_lane_name": "Industrial / Automation / Power Equipment",
            }
        ],
        observed_rows=[
            {
                "ticker": "PCRFY",
                "source_id": "channel_distributor_locator",
                "underlying_source_id": "channel_distributor_locator",
                "source_layer_id": "L3",
                "parser_status": "source_specific_context_parser_pass",
                "structured_fact_status": "bounded_context_fact_materialized",
                "exact_value_authority": False,
                "issuer_binding_status": "issuer_mentioned_in_snapshot",
                "product_binding_status": "product_mentioned_in_snapshot",
                "product_or_segment": "Industrial Equipment",
                "evidence_ref": "channel_distributor:PCRFY",
            }
        ],
        source_capability_rows=[],
        family_source_route_plan_rows=[
            {"ticker": "PCRFY", "route_id": "channel_offer_proxy"},
        ],
        generated_at="2026-06-23T00:00:00Z",
    )

    row = matrix["rows"][0]
    by_req = {item["requirement_id"]: item for item in row["source_role_matrix"]}
    assert row["status"] == "pass"
    assert by_req["channel_offer_proxy"]["status"] == "pass"
    assert by_req["channel_offer_proxy"]["observed_source_ids"] == ["channel_distributor_locator"]


def test_company_public_source_coverage_matrix_accepts_official_product_page_for_non_us_auto_identity() -> None:
    matrix = build_company_public_source_coverage_matrix(
        company_assignments=[
            {
                "ticker": "XPEV",
                "company_name": "XPeng Inc.",
                "primary_lane_id": "V5",
                "primary_lane_name": "Auto / Mobility",
            }
        ],
        observed_rows=[
            {
                "ticker": "XPEV",
                "source_id": "company_product_pages",
                "source_class": "company_product_page",
                "source_layer_id": "L2",
                "parser_status": "source_specific_context_parser_pass",
                "structured_fact_status": "bounded_context_fact_materialized",
                "exact_value_authority": False,
                "issuer_binding_status": "company_domain_bound",
                "product_binding_status": "product_mentioned_in_snapshot",
                "product_family": "General Auto / Mobility",
                "evidence_ref": "official_product_surface:XPEV",
            }
        ],
        source_capability_rows=[],
        family_source_route_plan_rows=[
            {"ticker": "XPEV", "route_id": "auto_product_identity_context"},
        ],
        generated_at="2026-06-23T00:00:00Z",
    )

    row = matrix["rows"][0]
    by_req = {item["requirement_id"]: item for item in row["source_role_matrix"]}
    assert row["status"] == "pass"
    assert by_req["auto_product_identity_context"]["status"] == "pass"
    assert by_req["auto_product_identity_context"]["observed_source_ids"] == ["company_product_pages"]


def test_company_public_source_coverage_matrix_keeps_official_event_separate_from_public_order_proxy() -> None:
    matrix = build_company_public_source_coverage_matrix(
        company_assignments=[
            {
                "ticker": "CRDO",
                "company_name": "Credo Technology Group Holding Ltd",
                "primary_lane_id": "V1",
                "primary_lane_name": "Semiconductors / AI Infrastructure",
            }
        ],
        observed_rows=[
            {
                "ticker": "CRDO",
                "source_id": "supplier_customer_official_news",
                "source_class": "supplier_customer_official_news",
                "source_layer_id": "L2",
                "parser_status": "source_specific_context_parser_pass",
                "structured_fact_status": "bounded_context_fact_materialized",
                "runtime_ready_context": True,
                "bounded_structured_context": True,
                "exact_value_authority": False,
                "can_support_company_exact_fact": False,
                "issuer_binding_status": "issuer_mentioned_in_snapshot",
                "counterparty_binding_status": "counterparty_mentioned_in_snapshot",
                "product_binding_status": "product_mentioned_in_snapshot",
                "product_or_segment": "Active electrical cable customer deployment",
                "counterparty": "Microsoft",
                "fact_label": "Credo official Microsoft SONiC deployment event",
                "event_type": "customer_deployment",
                "evidence_ref": "targeted_supply_chain_official_relationship:CRDO",
                "source_url": "https://credosemi.com/news/example",
            }
        ],
        source_capability_rows=[
            {
                "source_id": "supplier_customer_official_news",
                "layer_id": "L2",
                "evidence_graph_status": "runtime_ready_context",
            },
            {
                "source_id": "public_tenders_contracts_orders",
                "layer_id": "L3",
                "evidence_graph_status": "runtime_ready_context",
            },
        ],
        family_source_route_plan_rows=[
            {"ticker": "CRDO", "route_id": "public_order_proxy"},
            {"ticker": "CRDO", "route_id": "official_customer_order_or_deployment_event"},
        ],
        generated_at="2026-06-23T00:00:00Z",
    )

    row = matrix["rows"][0]
    by_req = {item["requirement_id"]: item for item in row["source_role_matrix"]}
    public_order = by_req["public_order_proxy"]
    official_event = by_req["official_customer_order_or_deployment_event"]
    assert row["status"] == "gap"
    assert public_order["status"] == "gap"
    assert public_order["observed_source_ids"] == []
    assert official_event["status"] == "pass"
    assert official_event["observed_source_ids"] == ["supplier_customer_official_news"]
    assert official_event["entity_bound_row_count"] == 1
    assert public_order["exact_authority_violation_count"] == 0
    assert "Public tender/award/order snapshot" in public_order["claim_boundary"]
