from __future__ import annotations

from sec_agent.non_financial_signal_authority import (
    attach_non_financial_signal_authority,
    classify_non_financial_signal_authority,
    validate_signal_claim_authority,
)


def test_official_product_spec_is_thesis_driver_not_financial_fact() -> None:
    row = attach_non_financial_signal_authority(
        {
            "evidence_ref": "r17_nvda_h100_memory",
            "source_family": "public_source_context",
            "runtime_source_family": "public_source_context",
            "source_layer_id": "L2",
            "source_id": "official_nvidia_product_page",
            "ticker": "NVDA",
            "source_role": "technical_product_spec",
            "runtime_contract": "ProductSpecSlot",
            "metric_name": "GPU memory",
            "value": 80,
            "unit": "GB",
            "source_url": "https://www.nvidia.com/en-us/data-center/h100/",
        }
    )

    assert row["signal_authority_type"] == "technical_fact"
    assert row["thesis_driver_authority"] is True
    assert row["exact_financial_fact_authority"] is False
    assert "product_revenue" in row["forbidden_claims"]
    assert "technical_product_spec" in row["allowed_non_financial_claims"]


def test_customer_deployment_signal_cannot_support_order_value() -> None:
    row = attach_non_financial_signal_authority(
        {
            "evidence_ref": "r17_nvda_xai_colossus",
            "source_family": "public_source_context",
            "source_layer_id": "L2",
            "source_id": "official_nvidia_customer_deployment_news",
            "ticker": "NVDA",
            "source_role": "customer_deployment_proxy",
            "runtime_contract": "CustomerDeploymentProxy",
            "metric_name": "xAI Colossus deployment",
            "value": 100000,
            "unit": "GPUs",
            "source_url": "https://nvidianews.nvidia.com/news/spectrum-x-ethernet-networking-xai-colossus",
        }
    )

    ok = validate_signal_claim_authority({"claim_type": "deployment_signal"}, [row])
    bad = validate_signal_claim_authority({"claim_type": "customer_order_value"}, [row])

    assert ok["status"] == "pass"
    assert ok["authority"] == "non_financial_thesis_driver_authority"
    assert bad["status"] == "fail"
    assert "exact_financial" in bad["reason"]


def test_official_customer_order_event_is_thesis_driver_but_not_revenue_authority() -> None:
    row = attach_non_financial_signal_authority(
        {
            "evidence_ref": "event:aehr:hyperscale",
            "source_family": "public_source_context",
            "source_layer_id": "L2",
            "source_id": "supplier_customer_official_news",
            "ticker": "AEHR",
            "source_role": "official_customer_order_or_deployment_event",
            "runtime_contract": "official_customer_order_or_deployment_event",
            "counterparty": "Lead hyperscale AI customer",
            "product_or_segment": "FOX-XP wafer-level test systems",
            "event_type": "customer_order",
            "event_scale_text": "$41 million",
            "source_url": "https://www.aehr.com/2026/04/production-order/",
        }
    )

    ok = validate_signal_claim_authority({"claim_type": "official_customer_order_or_deployment_event"}, [row])
    bad = validate_signal_claim_authority({"claim_type": "backlog"}, [row])

    assert row["signal_authority_type"] == "customer_order_or_deployment_event_signal"
    assert row["thesis_driver_authority"] is True
    assert ok["status"] == "pass"
    assert bad["status"] == "fail"
    assert "backlog" in row["forbidden_claims"]


def test_company_disclosed_operating_metric_has_exact_scope_but_not_product_kpi_scope() -> None:
    row = attach_non_financial_signal_authority(
        {
            "evidence_ref": "r17_msft_azure_revenue",
            "source_family": "company_product_evidence_graph",
            "source_layer_id": "L1",
            "source_id": "company_ir_annual_report",
            "ticker": "MSFT",
            "source_role": "industry_operating_metric",
            "runtime_contract": "IndustryOperatingMetricSlot",
            "promotion_status": "runtime_fact_allowed",
            "exact_value_authority": True,
            "metric_name": "Azure revenue",
            "value": 75_000_000_000,
            "unit": "USD",
            "period": "FY2025",
            "source_url": "https://www.microsoft.com/investor/reports/ar25/index.html",
        }
    )

    authority = classify_non_financial_signal_authority(row)
    assert authority["signal_authority_type"] == "industry_operating_signal"
    assert authority["exact_financial_fact_authority"] is True
    assert authority["thesis_driver_authority"] is True
    assert "product_revenue" in authority["forbidden_claim_types"]


def test_l4_or_untrusted_signal_stays_weak_lead_only() -> None:
    row = attach_non_financial_signal_authority(
        {
            "evidence_ref": "weak_forum_post",
            "source_family": "public_source_context",
            "source_layer_id": "L4",
            "source_id": "reddit_unverified_forum",
            "source_role": "market_expectation_proxy",
            "ticker": "NVDA",
            "source_url": "https://example.invalid/forum",
        }
    )

    assert row["signal_promotion_level"] == "weak_lead_only"
    assert row["thesis_driver_authority"] is False


def test_official_product_surface_source_role_is_not_generic_context() -> None:
    row = attach_non_financial_signal_authority(
        {
            "evidence_ref": "official_product_surface:nvda:h100",
            "source_family": "public_source_context",
            "source_layer": "L2",
            "source_id": "company_product_pages",
            "ticker": "NVDA",
            "source_role": "official_product_surface",
            "sample_urls": ["https://www.nvidia.com/en-us/data-center/h100/"],
            "claim_boundary": "Official product existence, specs, and positioning only.",
        }
    )

    assert row["signal_authority_type"] == "technical_fact"
    assert row["thesis_driver_authority"] is True
    assert "technical_product_spec" in row["allowed_non_financial_claims"]


def test_macro_official_context_source_role_is_macro_driver_signal() -> None:
    row = attach_non_financial_signal_authority(
        {
            "evidence_ref": "macro:fred:fedfunds",
            "source_family": "public_source_context",
            "source_layer": "L2",
            "source_id": "fred_api",
            "ticker": "NVDA",
            "source_role": "macro_official_context",
            "sample_urls": ["https://api.stlouisfed.org/fred/series/observations?series_id=FEDFUNDS"],
            "claim_boundary": "Official macro context only; no issuer revenue inference.",
        }
    )

    assert row["signal_authority_type"] == "macro_driver_signal"
    assert row["thesis_driver_authority"] is True
