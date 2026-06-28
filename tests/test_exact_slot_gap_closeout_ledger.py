from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "data_expansion"
    / "build_exact_slot_gap_closeout_ledger.py"
)
SPEC = importlib.util.spec_from_file_location("build_exact_slot_gap_closeout_ledger", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_channel_provider_only_attempt_is_classified():
    rows = MODULE.build_gap_closeout_rows(
        gap_rows=[
            {
                "gap_id": "gap:NVDA:channel",
                "ticker": "NVDA",
                "company_name": "NVIDIA",
                "requirement_id": "channel_offer_proxy",
                "gap_class": "source_gap",
                "source_gate_gap_type": "company_specific_runtime_row_missing",
            }
        ],
        attempts=[
            {
                "ticker": "NVDA",
                "provider": "cdw_product",
                "status": "skipped_product_mismatch",
                "url": "https://www.cdw.com/product/example",
            }
        ],
        sec_financial_summary={},
        generated_at="2026-06-18T00:00:00Z",
    )

    assert rows[0]["closeout_class"] == "public_source_exhausted_gap"
    assert rows[0]["closeout_reason"] == "cdw_channel_search_no_verified_sku_price_availability_match"
    assert rows[0]["attempt_count"] == 1


def test_openalex_attempt_classifies_technology_research_gap_as_exhausted():
    rows = MODULE.build_gap_closeout_rows(
        gap_rows=[
            {
                "gap_id": "gap:AMAT:technology",
                "ticker": "AMAT",
                "company_name": "Applied Materials",
                "requirement_id": "technology_research_proxy",
                "gap_class": "source_gap",
                "source_gate_gap_type": "company_specific_runtime_row_missing",
            }
        ],
        attempts=[
            {
                "ticker": "AMAT",
                "source_id": "openalex_api",
                "provider": "openalex",
                "status": "no_issuer_topic_bound_works",
                "api_url": "https://api.openalex.org/works?search=Applied+Materials+etch",
            }
        ],
        sec_financial_summary={},
        generated_at="2026-06-18T00:00:00Z",
    )

    assert rows[0]["closeout_class"] == "public_source_exhausted_gap"
    assert rows[0]["closeout_reason"] == "openalex_no_issuer_topic_bound_research_proxy"
    assert rows[0]["attempt_count"] == 1


def test_patentsview_missing_key_classifies_technology_gap_as_adapter_repair_needed():
    rows = MODULE.build_gap_closeout_rows(
        gap_rows=[
            {
                "gap_id": "gap:NVDA:technology",
                "ticker": "NVDA",
                "company_name": "NVIDIA",
                "requirement_id": "technology_research_proxy",
                "gap_class": "source_gap",
                "source_gate_gap_type": "company_specific_runtime_row_missing",
            }
        ],
        attempts=[
            {
                "ticker": "NVDA",
                "source_id": "patentsview_api",
                "provider": "patentsview",
                "status": "missing_patentsview_api_key",
                "api_url": "https://search.patentsview.org/api/v1/patent/",
            }
        ],
        sec_financial_summary={},
        generated_at="2026-06-18T00:00:00Z",
    )

    assert rows[0]["closeout_class"] == "adapter_or_locator_deep_repair_needed"
    assert rows[0]["closeout_reason"] == "patentsview_api_key_missing_or_patentsearch_unavailable"
    assert rows[0]["attempt_count"] == 1


def test_supply_chain_official_relationship_attempt_is_not_mixed_with_public_order():
    rows = MODULE.build_gap_closeout_rows(
        gap_rows=[
            {
                "gap_id": "gap:AEHR:supply_chain",
                "ticker": "AEHR",
                "company_name": "Aehr Test Systems",
                "requirement_id": "supply_chain_official_relationship",
                "gap_class": "source_gap",
                "source_gate_gap_type": "company_specific_runtime_row_missing",
            }
        ],
        attempts=[
            {
                "ticker": "AEHR",
                "source_id": "supplier_customer_official_news",
                "status": "official_page_missing_required_aliases",
                "source_url": "https://www.aehr.com/example",
                "reason": "counterparty missing",
            }
        ],
        sec_financial_summary={},
        generated_at="2026-06-18T00:00:00Z",
    )

    assert rows[0]["closeout_class"] == "public_source_exhausted_gap"
    assert rows[0]["closeout_reason"] == "official_supply_chain_relationship_page_no_issuer_counterparty_bound_row"
    assert rows[0]["attempt_count"] == 1


def test_non_us_public_order_gap_requires_jurisdiction_adapter_before_closeout():
    rows = MODULE.build_gap_closeout_rows(
        gap_rows=[
            {
                "gap_id": "gap:1211.HK:public_order",
                "ticker": "1211.HK",
                "company_name": "BYD Company Limited",
                "requirement_id": "public_order_proxy",
                "gap_class": "source_gap",
                "source_gate_gap_type": "company_specific_runtime_row_missing",
            }
        ],
        attempts=[
            {
                "ticker": "1211.HK",
                "source_id": "public_tenders_contracts_orders",
                "provider": "usaspending",
                "status": "no_recipient_bound_award",
            }
        ],
        sec_financial_summary={},
        generated_at="2026-06-18T00:00:00Z",
    )

    assert rows[0]["closeout_class"] == "adapter_or_locator_deep_repair_needed"
    assert rows[0]["closeout_reason"] == "hk_public_order_local_tender_adapter_required"


def test_non_us_public_order_local_tender_attempt_can_close_public_boundary():
    rows = MODULE.build_gap_closeout_rows(
        gap_rows=[
            {
                "gap_id": "gap:1211.HK:public_order",
                "ticker": "1211.HK",
                "company_name": "BYD Company Limited",
                "requirement_id": "public_order_proxy",
                "gap_class": "source_gap",
                "source_gate_gap_type": "company_specific_runtime_row_missing",
            }
        ],
        attempts=[
            {
                "ticker": "1211.HK",
                "source_id": "public_tenders_contracts_orders",
                "provider": "hk_open_data_contract_awards",
                "status": "no_supplier_bound_award_or_no_structured_award_endpoint",
            }
        ],
        sec_financial_summary={},
        generated_at="2026-06-18T00:00:00Z",
    )

    assert rows[0]["closeout_class"] == "public_source_exhausted_gap"
    assert rows[0]["closeout_reason"] == "hk_local_tender_no_supplier_bound_award_or_no_structured_award_endpoint"


def test_developer_attempt_classifies_unmaterialized_official_seed_gap():
    rows = MODULE.build_gap_closeout_rows(
        gap_rows=[
            {
                "gap_id": "gap:SNPS:developer",
                "ticker": "SNPS",
                "company_name": "Synopsys",
                "requirement_id": "developer_ecosystem_proxy",
                "gap_class": "source_gap",
                "source_gate_gap_type": "company_specific_runtime_row_missing",
            }
        ],
        attempts=[
            {
                "ticker": "SNPS",
                "source_id": "developer_ecosystem_github_npm_pypi_huggingface",
                "provider": "github",
                "status": "unusable_response",
                "api_url": "https://api.github.com/repos/synopsys-sig/detect",
                "reason": "http_404",
            }
        ],
        sec_financial_summary={},
        generated_at="2026-06-18T00:00:00Z",
    )

    assert rows[0]["closeout_class"] == "public_source_exhausted_gap"
    assert rows[0]["closeout_reason"] == "developer_ecosystem_official_seed_fetch_or_binding_failed"
    assert rows[0]["attempt_count"] == 1


def test_developer_materialized_attempt_for_non_gap_ticker_does_not_create_closeout_row():
    rows = MODULE.build_gap_closeout_rows(
        gap_rows=[
            {
                "gap_id": "gap:APH:developer",
                "ticker": "APH",
                "company_name": "Amphenol",
                "requirement_id": "developer_ecosystem_proxy",
                "gap_class": "source_gap",
                "source_gate_gap_type": "company_specific_runtime_row_missing",
            }
        ],
        attempts=[
            {
                "ticker": "S",
                "source_id": "developer_ecosystem_github_npm_pypi_huggingface",
                "provider": "github",
                "status": "materialized",
                "api_url": "https://api.github.com/repos/sentinel-one/example",
            },
            {
                "ticker": "APH",
                "source_id": "developer_ecosystem_github_npm_pypi_huggingface",
                "provider": "github",
                "status": "no_verified_official_seed",
                "reason": "official_seed_not_found",
            },
        ],
        sec_financial_summary={},
        generated_at="2026-06-18T00:00:00Z",
    )

    assert [row["ticker"] for row in rows] == ["APH"]
    assert rows[0]["closeout_class"] == "public_source_exhausted_gap"
    assert rows[0]["attempt_status_counts"] == {"no_verified_official_seed": 1}


def test_product_kpi_closeout_distinguishes_surface_from_exact_kpi():
    rows = MODULE.build_product_kpi_closeout_rows(
        coverage_rows=[
            {"ticker": "AAPL", "company_name": "Apple", "exact_ready_requirement_count": 3},
            {"ticker": "MSFT", "company_name": "Microsoft", "exact_ready_requirement_count": 3},
            {"ticker": "ABNB", "company_name": "Airbnb", "exact_ready_requirement_count": 3},
            {"ticker": "ADBE", "company_name": "Adobe", "exact_ready_requirement_count": 3},
        ],
        product_slots=[
            {"ticker": "AAPL", "slot_status": "product_kpi_exact_slot", "product_slot_name": "Mac"},
            {"ticker": "MSFT", "slot_status": "official_surface_slot", "product_slot_name": "Copilot"},
        ],
        product_kpi_runtime_rows=[
            {
                "ticker": "MSFT",
                "evidence_ref": "fact:msft:azure",
                "product_or_segment": "Azure",
                "metric_name": "product revenue",
                "value": 10,
                "unit": "USD",
                "period": "FY2024",
                "product_node_type": "product_family",
            },
            {
                "ticker": "ABNB",
                "evidence_ref": "fact:abnb:na",
                "product_or_segment": "North America",
                "metric_name": "product revenue",
                "value": 10,
                "unit": "USD",
                "period": "FY2024",
                "product_node_type": "asset_or_product_family",
            },
            {
                "ticker": "ADBE",
                "evidence_ref": "fact:adbe:business",
                "product_or_segment": "Business Professionals and Consumers",
                "metric_name": "product revenue",
                "value": 10,
                "unit": "USD",
                "period": "FY2024",
                "product_node_type": "business_line",
            },
        ],
        product_kpi_summary={"status": "pass"},
        generated_at="2026-06-18T00:00:00Z",
    )

    by_ticker = {row["ticker"]: row for row in rows}
    assert by_ticker["AAPL"]["status"] == "product_kpi_exact_gap"
    assert by_ticker["AAPL"]["runtime_product_kpi_exact_row_count"] == 0
    assert by_ticker["MSFT"]["status"] == "product_kpi_exact_ready"
    assert by_ticker["MSFT"]["runtime_product_kpi_exact_row_count"] == 1
    assert by_ticker["ABNB"]["status"] == "geographic_or_non_product_metric_only"
    assert by_ticker["ADBE"]["status"] == "business_segment_metric_ready"
