from __future__ import annotations

from sec_agent.exact_slot_contracts import (
    CONTRACTS_BY_REQUIREMENT_ID,
    audit_row_against_exact_slot_contract,
    build_exact_slot_coverage_matrix,
    build_exact_slot_rows,
)


def test_company_reported_product_kpi_promotes_to_l1_exact_company_fact_slot() -> None:
    row = {
        "ticker": "AAPL",
        "source_id": "company_reported_product_operating_metrics",
        "source_layer_id": "L1",
        "source_url": "https://www.sec.gov/aapl.htm",
        "product_or_segment": "iPhone",
        "metric_name": "product revenue",
        "value": 201183000000,
        "unit": "USD",
        "period": "FY2024",
        "citation_span": "iPhone | 201,183",
        "parser_status": "value_unit_period_product_citation_parser_pass",
        "issuer_binding_status": "issuer_mentioned_in_snapshot",
        "product_binding_status": "product_mentioned_in_snapshot",
        "evidence_ref": "PRODUCTKPI::AAPL::IPHONE",
        "can_support_company_exact_fact": True,
    }

    payload = build_exact_slot_rows([row], generated_at="2026-06-18T00:00:00Z")

    assert payload["exact_slot_row_count"] == 2
    slot = next(row for row in payload["exact_rows"] if row["requirement_id"] == "primary_company_disclosure")
    assert slot["requirement_id"] == "primary_company_disclosure"
    assert slot["can_support_company_exact_fact"] is True


def test_sec_financial_statement_metric_promotes_to_l1_primary_disclosure_slot() -> None:
    row = {
        "ticker": "MSFT",
        "source_id": "sec_financial_statement_data_sets",
        "source_layer_id": "L1",
        "source_url": "https://data.sec.gov/api/xbrl/companyfacts/CIK0000789019.json",
        "metric_name": "Revenues",
        "value": 245122000000,
        "unit": "USD",
        "period": "FY2024-FY",
        "statement_or_section": "income_statement",
        "citation_span": "SEC CompanyFacts 10-K reports Revenues = 245122000000 USD for FY2024.",
        "filing_type": "10-K",
        "source_document_id": "0000950170-24-087843",
        "parser_status": "value_unit_period_product_citation_parser_pass",
        "issuer_binding_status": "issuer_mentioned_in_snapshot",
        "can_support_company_exact_fact": True,
    }

    payload = build_exact_slot_rows([row], generated_at="2026-06-18T00:00:00Z")

    assert payload["exact_slot_row_count"] == 1
    slot = payload["exact_rows"][0]
    assert slot["requirement_id"] == "primary_company_disclosure"
    assert slot["slot_kind"] == "company_reported_financial_statement_metric"
    assert slot["can_support_company_exact_fact"] is True
    assert "product_sales_without_product_kpi" in slot["forbidden_claims"]


def test_company_ir_financial_statement_metric_promotes_to_l1_primary_disclosure_slot() -> None:
    row = {
        "ticker": "IFX.DE",
        "source_id": "company_ir_reports",
        "source_layer_id": "L1",
        "source_url": "https://www.infineon.com/annual-report",
        "metric_name": "Revenue",
        "value": 14662000000,
        "unit": "EUR",
        "period": "FY2025",
        "statement_or_section": "income_statement",
        "citation_span": "Revenue by segment 14,662 14,955 | parsed_unit=EUR_millions",
        "source_document_id": "infineon-annual-report-2025",
        "parser_status": "value_unit_period_product_citation_parser_pass",
        "issuer_binding_status": "issuer_mentioned_in_snapshot",
        "can_support_company_exact_fact": True,
    }

    payload = build_exact_slot_rows([row], generated_at="2026-06-19T00:00:00Z")

    assert payload["exact_slot_row_count"] == 1
    slot = payload["exact_rows"][0]
    assert slot["requirement_id"] == "primary_company_disclosure"
    assert slot["slot_kind"] == "company_reported_financial_statement_metric"
    assert slot["source_id"] == "company_ir_reports"


def test_company_reported_product_kpi_also_satisfies_official_product_surface_requirement() -> None:
    row = {
        "ticker": "AAPL",
        "source_id": "company_reported_product_operating_metrics",
        "source_layer_id": "L1",
        "source_url": "https://www.sec.gov/aapl.htm",
        "product_or_segment": "Services",
        "metric_name": "product revenue",
        "value": 96169000000,
        "unit": "USD",
        "period": "FY2024",
        "citation_span": "Services | 96,169",
        "parser_status": "value_unit_period_product_citation_parser_pass",
        "issuer_binding_status": "issuer_mentioned_in_snapshot",
        "product_binding_status": "product_mentioned_in_snapshot",
        "evidence_ref": "PRODUCTKPI::AAPL::SERVICES",
        "can_support_company_exact_fact": True,
    }

    payload = build_exact_slot_rows([row], generated_at="2026-06-18T00:00:00Z")

    by_requirement = {slot["requirement_id"]: slot for slot in payload["exact_rows"]}
    assert set(by_requirement) == {"primary_company_disclosure", "official_product_surface"}
    assert by_requirement["official_product_surface"]["slot_kind"] == "company_reported_product_kpi_as_official_product_surface"


def test_official_product_surface_is_exact_product_surface_but_not_company_exact_fact() -> None:
    row = {
        "ticker": "NVDA",
        "source_id": "company_product_pages",
        "source_layer_id": "L2",
        "source_url": "https://www.nvidia.com/en-us/data-center/h100/",
        "source_title": "NVIDIA H100 Tensor Core GPU",
        "product_or_segment": "H100 Tensor Core GPU",
        "parser_status": "source_specific_context_parser_pass",
        "issuer_binding_status": "company_domain_bound",
        "product_binding_status": "product_mentioned_in_snapshot",
        "evidence_ref": "official_product_surface::nvda::h100",
        "can_support_company_exact_fact": False,
    }

    payload = build_exact_slot_rows([row], generated_at="2026-06-18T00:00:00Z")

    assert payload["exact_slot_row_count"] == 1
    slot = payload["exact_rows"][0]
    assert slot["requirement_id"] == "official_product_surface"
    assert slot["can_support_company_exact_fact"] is False


def test_official_product_catalog_parser_status_satisfies_product_surface_slot() -> None:
    row = {
        "ticker": "NVDA",
        "source_id": "company_product_pages",
        "source_layer_id": "L2",
        "source_url": "https://www.nvidia.com/en-us/data-center/",
        "fact_label": "H100 Tensor Core GPU",
        "product_or_segment": "H100 Tensor Core GPU",
        "parser_status": "official_product_catalog_parser_pass",
        "issuer_binding_status": "company_domain_bound",
        "product_binding_status": "product_mentioned_in_snapshot",
        "evidence_ref": "official_product_catalog::nvda::h100",
        "can_support_company_exact_fact": False,
    }

    payload = build_exact_slot_rows([row], generated_at="2026-06-19T00:00:00Z")

    assert payload["exact_slot_row_count"] == 1
    slot = payload["exact_rows"][0]
    assert slot["requirement_id"] == "official_product_surface"
    assert slot["slot_kind"] == "official_product_surface"


def test_sec_product_taxonomy_satisfies_official_surface_without_company_exact_fact() -> None:
    row = {
        "ticker": "DELL",
        "source_id": "sec_product_taxonomy_normalized",
        "source_layer_id": "L1",
        "source_url": "https://www.sec.gov/Archives/edgar/data/1571996/dell-10k.htm",
        "source_title": "SEC product taxonomy: Cloud Native Infrastructure Solutions",
        "product_or_segment": "Cloud Native Infrastructure Solutions",
        "parser_status": "source_specific_context_parser_pass",
        "issuer_binding_status": "issuer_mentioned_in_snapshot",
        "product_binding_status": "product_mentioned_in_snapshot",
        "can_support_company_exact_fact": False,
    }

    payload = build_exact_slot_rows([row], generated_at="2026-06-18T00:00:00Z")

    assert payload["exact_slot_row_count"] == 1
    slot = payload["exact_rows"][0]
    assert slot["requirement_id"] == "official_product_surface"
    assert slot["slot_kind"] == "sec_product_taxonomy_context"
    assert slot["can_support_company_exact_fact"] is False


def test_macro_exposure_bridge_satisfies_macro_context_without_company_exact_fact() -> None:
    row = {
        "ticker": "NVDA",
        "source_id": "fred_api",
        "source_layer_id": "L2",
        "api_route": "https://api.stlouisfed.org/fred/series/observations?series_id=FEDFUNDS",
        "product_or_segment": "FEDFUNDS",
        "macro_driver_id": "FEDFUNDS",
        "macro_driver_name": "Federal funds effective rate",
        "value": 3.63,
        "unit": "percent",
        "period": "2026-05-01",
        "parser_status": "source_specific_context_parser_pass",
        "issuer_binding_status": "macro_exposure_bridge_context",
        "product_binding_status": "product_mentioned_in_snapshot",
        "can_support_company_exact_fact": False,
    }

    payload = build_exact_slot_rows([row], generated_at="2026-06-18T00:00:00Z")

    slot = next(row for row in payload["exact_rows"] if row["requirement_id"] == "macro_official_context")
    assert slot["requirement_id"] == "macro_official_context"
    assert slot["can_support_company_exact_fact"] is False
    assert slot["source_url"].startswith("https://api.stlouisfed.org/")


def test_nhtsa_make_model_row_uses_product_aliases_for_auto_identity_slot() -> None:
    row = {
        "ticker": "TSLA",
        "source_id": "nhtsa_vpic_api",
        "source_layer_id": "L2",
        "api_route": "https://vpic.nhtsa.dot.gov/api/vehicles/GetModelsForMake/Tesla?format=json",
        "source_entity_name": "Tesla",
        "product_or_segment": "Model S",
        "metric_name": "NHTSA_MAKE_MODEL",
        "identifier": "Tesla:Model S",
        "identifier_type": "NHTSA_MAKE_MODEL",
        "parser_status": "normalized_record_projector_pass",
        "issuer_binding_status": "issuer_mentioned_in_snapshot",
        "product_binding_status": "product_mentioned_in_snapshot",
        "can_support_company_exact_fact": False,
    }

    payload = build_exact_slot_rows([row], generated_at="2026-06-18T00:00:00Z")

    assert payload["exact_slot_row_count"] == 1
    slot = payload["exact_rows"][0]
    assert slot["requirement_id"] == "auto_product_identity_context"
    assert slot["slot_values"]["make"] == "Tesla"
    assert slot["slot_values"]["model"] == "Model S"


def test_official_auto_model_page_satisfies_auto_identity_context_for_non_us_issuer() -> None:
    row = {
        "ticker": "XPEV",
        "source_id": "company_product_pages",
        "source_layer_id": "L2",
        "source_url": "https://www.xpeng.com/",
        "fact_label": "XPENG model page",
        "fact_value": "Models X9 P7+ G9 G6 P7",
        "product_or_segment": "General Auto / Mobility",
        "parser_status": "source_specific_context_parser_pass",
        "issuer_binding_status": "company_domain_bound",
        "product_binding_status": "product_mentioned_in_snapshot",
        "can_support_company_exact_fact": False,
    }

    payload = build_exact_slot_rows([row], generated_at="2026-06-23T00:00:00Z")

    assert payload["exact_slot_row_count"] == 2
    by_requirement = {slot["requirement_id"]: slot for slot in payload["exact_rows"]}
    assert by_requirement["auto_product_identity_context"]["slot_kind"] == "official_vehicle_identity_record"
    assert by_requirement["auto_product_identity_context"]["exact_company_fact_allowed"] is False


def test_automatic_substring_product_page_does_not_enter_auto_identity_context() -> None:
    row = {
        "ticker": "ADP",
        "source_id": "company_product_pages",
        "source_layer_id": "L2",
        "source_url": "https://www.automatic.com/products",
        "source_title": "Automatic product page",
        "product_or_segment": "SaaS CRM / Workflow",
        "parser_status": "source_specific_context_parser_pass",
        "issuer_binding_status": "company_domain_bound",
        "product_binding_status": "product_mentioned_in_snapshot",
        "can_support_company_exact_fact": False,
    }

    payload = build_exact_slot_rows([row], generated_at="2026-06-23T00:00:00Z")

    assert payload["exact_slot_row_count"] == 1
    assert payload["exact_rows"][0]["requirement_id"] == "official_product_surface"


def test_channel_offer_fact_value_is_normalized_into_price_and_availability_slot() -> None:
    row = {
        "ticker": "AAPL",
        "source_id": "channel_pricing_quotations",
        "source_layer_id": "L3",
        "source_url": "https://www.cdw.com/product/macbook/1",
        "channel_product_name": "Apple MacBook Pro",
        "channel_product_id": "1",
        "fact_value": "brand=Apple; sku=1; price=2329.99 ; availability=In Stock",
        "parser_status": "source_specific_context_parser_pass",
        "issuer_binding_status": "issuer_mentioned_in_snapshot",
        "product_binding_status": "product_mentioned_in_snapshot",
        "can_support_company_exact_fact": False,
    }

    payload = build_exact_slot_rows([row], generated_at="2026-06-18T00:00:00Z")

    assert payload["exact_slot_row_count"] == 1
    slot = payload["exact_rows"][0]
    assert slot["slot_values"]["price"] == 2329.99
    assert slot["slot_values"]["availability"] == "In Stock"


def test_channel_distributor_locator_satisfies_channel_requirement_without_price() -> None:
    row = {
        "ticker": "DE",
        "source_id": "channel_distributor_locator",
        "source_layer_id": "L3",
        "source_url": "https://dealerlocator.deere.com/servlet/country=US?locale=en_US",
        "fact_label": "Deere Find a Dealer",
        "channel_name": "official dealer locator",
        "product_or_segment": "Industrial Equipment",
        "parser_status": "source_specific_context_parser_pass",
        "issuer_binding_status": "issuer_mentioned_in_snapshot",
        "can_support_company_exact_fact": False,
    }

    payload = build_exact_slot_rows([row], generated_at="2026-06-18T00:00:00Z")

    assert payload["exact_slot_row_count"] == 1
    slot = payload["exact_rows"][0]
    assert slot["requirement_id"] == "channel_offer_proxy"
    assert slot["slot_kind"] == "public_channel_distributor_locator"
    assert slot["slot_values"]["channel_name"] == "official dealer locator"


def test_official_customer_order_or_deployment_event_is_separate_from_public_order_exact() -> None:
    row = {
        "ticker": "AEHR",
        "source_id": "supplier_customer_official_news",
        "source_layer_id": "L2",
        "source_url": "https://www.aehr.com/2026/04/production-order/",
        "counterparty": "Lead hyperscale AI customer",
        "product_or_segment": "FOX-XP wafer-level test systems",
        "fact_label": "Aehr receives record production order from lead hyperscale AI customer",
        "event_type": "customer_order",
        "event_date": "2026-04",
        "event_scale_text": "$41 million; $92 million",
        "parser_status": "source_specific_context_parser_pass",
        "issuer_binding_status": "issuer_mentioned_in_snapshot",
        "counterparty_binding_status": "counterparty_mentioned_in_snapshot",
        "product_binding_status": "product_mentioned_in_snapshot",
        "can_support_company_exact_fact": False,
    }

    payload = build_exact_slot_rows([row], generated_at="2026-06-24T00:00:00Z")

    by_requirement = {slot["requirement_id"]: slot for slot in payload["exact_rows"]}
    assert "supply_chain_official_relationship" in by_requirement
    assert "official_customer_order_or_deployment_event" in by_requirement
    assert "public_order_proxy" not in by_requirement
    event_slot = by_requirement["official_customer_order_or_deployment_event"]
    assert event_slot["slot_kind"] == "official_customer_order_or_deployment_event"
    assert event_slot["source_role"] == "official_customer_order_or_deployment_event"
    assert event_slot["can_support_company_exact_fact"] is False
    assert "official_customer_order_or_deployment_event" in event_slot["allowed_claims"]
    assert "backlog" in event_slot["forbidden_claims"]


def test_supplier_customer_official_news_without_event_marker_does_not_enter_event_slot() -> None:
    row = {
        "ticker": "QCOM",
        "source_id": "supplier_customer_official_news",
        "source_layer_id": "L2",
        "source_url": "https://example.com/partner-directory",
        "counterparty": "Example Partner",
        "product_or_segment": "partner directory listing",
        "fact_label": "Example Partner listed in directory",
        "parser_status": "source_specific_context_parser_pass",
        "issuer_binding_status": "issuer_mentioned_in_snapshot",
        "counterparty_binding_status": "counterparty_mentioned_in_snapshot",
        "product_binding_status": "product_mentioned_in_snapshot",
        "can_support_company_exact_fact": False,
    }

    payload = build_exact_slot_rows([row], generated_at="2026-06-24T00:00:00Z")

    assert {slot["requirement_id"] for slot in payload["exact_rows"]} == {"supply_chain_official_relationship"}


def test_context_row_without_required_metric_fields_remains_rejected_attempt() -> None:
    contract = CONTRACTS_BY_REQUIREMENT_ID["channel_offer_proxy"][0]
    audit = audit_row_against_exact_slot_contract(
        {
            "ticker": "AAPL",
            "source_id": "channel_pricing_quotations",
            "source_layer_id": "L3",
            "source_url": "https://www.cdw.com/product/macbook/1",
            "parser_status": "source_specific_context_parser_pass",
            "issuer_binding_status": "issuer_mentioned_in_snapshot",
            "product_binding_status": "product_mentioned_in_snapshot",
        },
        contract,
    )

    assert audit["status"] == "structured_field_gap"
    assert "price" in audit["missing_fields"]


def test_exact_slot_coverage_matrix_requires_exact_slot_not_source_gate_pass_only() -> None:
    company_matrix_rows = [
        {
            "ticker": "NVDA",
            "company_name": "NVIDIA Corporation",
            "primary_lane_id": "V1",
            "source_role_matrix": [
                {
                    "requirement_id": "official_product_surface",
                    "dimension": "product_and_production",
                    "status": "pass",
                    "gap_class": "pass",
                    "gap_type": "",
                    "layer_ids": ["L1", "L2"],
                    "source_ids": ["company_product_pages"],
                },
                {
                    "requirement_id": "channel_offer_proxy",
                    "dimension": "product_and_production",
                    "status": "pass",
                    "gap_class": "pass",
                    "gap_type": "",
                    "layer_ids": ["L3"],
                    "source_ids": ["channel_pricing_quotations"],
                },
            ],
        }
    ]
    exact_rows = [
        {
            "exact_slot_id": "exact_slot:nvda:surface",
            "ticker": "NVDA",
            "requirement_id": "official_product_surface",
            "slot_kind": "official_product_surface",
            "source_layer_id": "L2",
            "source_url": "https://www.nvidia.com/h100",
        }
    ]

    coverage = build_exact_slot_coverage_matrix(
        company_source_matrix_rows=company_matrix_rows,
        exact_slot_rows=exact_rows,
        generated_at="2026-06-18T00:00:00Z",
    )

    assert coverage["status"] == "gap"
    row = coverage["rows"][0]
    assert row["coverage_status"] == "partial_exact_ready"
    statuses = {item["requirement_id"]: item["status"] for item in row["source_role_exact_slot_matrix"]}
    assert statuses["official_product_surface"] == "exact_slot_ready"
    assert statuses["channel_offer_proxy"] == "exact_slot_gap"
