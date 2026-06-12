from __future__ import annotations

from sec_agent.langgraph_orchestrator import _multi_agent_specialists_active
from sec_agent.multi_agent_runtime import build_agent_data_view
from sec_agent.product_spec_pack import PRODUCT_SPEC_PACK_SCHEMA_VERSION, build_product_spec_pack, validate_product_spec_pack
from sec_agent.specialist_llm import build_specialist_request_from_state


def _product_pack_state() -> dict:
    return {
        "run_id": "unit_product_pack_run",
        "agent_activation_plan": {
            "execution_mode": "standard_memo",
            "activate_agents": ["product_technology_analyst"],
            "agent_priorities": {"product_technology_analyst": "primary"},
        },
        "product_evidence_rows": [
            {
                "evidence_ref": "product_fact_h100_revenue",
                "source_family": "company_product_evidence_graph",
                "promotion_status": "runtime_fact_allowed",
                "exact_value_authority": True,
                "ticker": "NVDA",
                "product_or_segment": "Data Center GPU",
                "metric_family": "product_revenue",
                "value": "47.5",
                "unit": "USD billions",
                "period": "FY2025",
                "source_id": "sec_product_kpi_parser_verified",
            },
            {
                "evidence_ref": "official_spec_h100_memory",
                "source_family": "live_public_web_context",
                "source_class": "company_official_product_surface",
                "ticker": "NVDA",
                "product_family": "Data Center GPU",
                "model_name": "H100 SXM",
                "spec_name": "memory_capacity",
                "value": "80",
                "unit": "GB",
                "region": "US",
                "effective_date": "2024-01-01",
                "source_id": "nvidia_h100_product_page",
            },
            {
                "evidence_ref": "generation_hopper_blackwell",
                "source_family": "live_public_web_context",
                "source_class": "company_official_product_surface",
                "ticker": "NVDA",
                "prior_model": "H100 SXM",
                "current_model": "B200 SXM",
                "comparable_dimensions": ["memory_capacity", "compute_throughput"],
                "source_id": "nvidia_architecture_page",
            },
            {
                "evidence_ref": "comparable_h100_mi300x",
                "source_family": "public_source_context",
                "source_class": "developer_documentation",
                "ticker": "NVDA",
                "product_model_id": "ProductModel::h100",
                "competitor_product_model_id": "ProductModel::amd_mi300x",
                "comparable_dimensions": ["memory_capacity", "memory_bandwidth"],
                "region": "US",
                "source_id": "developer_comparison_note",
            },
            {
                "evidence_ref": "gap_channel_inventory",
                "source_family": "company_product_evidence_graph",
                "promotion_status": "gap_exposed_not_fallback",
                "ticker": "NVDA",
                "missing_metric": "channel_inventory",
                "gap_type": "commercial_market_tracker_gap_after_public_source_check",
                "why_public_sources_do_not_fill": "Channel inventory requires commercial tracker coverage.",
                "commercial_sources_that_would_fill": ["IDC tracker"],
            },
        ],
        "public_source_context_rows": [
            {
                "evidence_ref": "commerce_h100_offer",
                "source_family": "live_public_web_context",
                "source_class": "commerce_product_surface",
                "claim_types": ["sku", "price", "availability"],
                "ticker": "NVDA",
                "product_family": "Data Center GPU",
                "model_name": "H100 SXM",
                "channel_name": "Amazon Business",
                "price": "$24,999",
                "currency": "USD",
                "availability": "listed",
                "configuration": "SXM 80GB",
                "region": "US",
                "observed_at": "2026-06-12",
                "source_id": "amazon_business_h100_listing",
            },
            {
                "evidence_ref": "field_inquiry_h100_lead_time",
                "source_family": "public_source_context",
                "source_class": "field_inquiry_note",
                "ticker": "NVDA",
                "model_name": "H100 SXM",
                "provider_role": "public distributor sales desk",
                "inquiry_target": "H100 SXM 80GB availability",
                "inquiry_time": "2026-06-12T10:00:00Z",
                "region": "US",
                "raw_record_ref": "inquiry_note_001",
                "confidence": "low",
                "source_id": "analyst_inquiry_log",
            },
            {
                "evidence_ref": "bad_channel_sell_through",
                "source_family": "live_public_web_context",
                "source_class": "commerce_product_surface",
                "ticker": "NVDA",
                "model_name": "H100 SXM",
                "price": "$24,999",
                "currency": "USD",
                "availability": "listed",
                "region": "US",
                "observed_at": "2026-06-12",
                "claim_scope": "sell_through",
                "exact_value_authority": True,
                "source_id": "bad_commerce_listing",
            },
            {
                "evidence_ref": "bad_comparable_missing_dimensions",
                "source_family": "public_source_context",
                "source_class": "developer_documentation",
                "ticker": "NVDA",
                "product_model_id": "ProductModel::h100",
                "competitor_product_model_id": "ProductModel::amd_mi300x",
                "source_id": "bad_comparison_note",
            },
        ],
    }


def test_product_spec_pack_builds_gated_product_objects_and_rejections() -> None:
    pack = build_product_spec_pack(_product_pack_state())

    assert pack["schema_version"] == PRODUCT_SPEC_PACK_SCHEMA_VERSION
    assert pack["status"] == "pass"
    assert pack["summary"]["product_kpi_ref_count"] == 1
    assert pack["summary"]["product_spec_count"] == 1
    assert pack["summary"]["generation_edge_count"] == 1
    assert pack["summary"]["competitive_comparable_edge_count"] == 1
    assert pack["summary"]["channel_offer_count"] == 1
    assert pack["summary"]["field_inquiry_note_count"] == 1
    assert pack["summary"]["commercial_gap_count"] == 1

    offer = pack["channel_offers"][0]
    assert offer["claim_scope"] == "price_availability_configuration_context_only"
    assert offer["exact_value_authority"] is False
    assert {"company_sales", "sell_through", "market_share", "company_ASP", "channel_inventory"} <= set(offer["forbidden_claims"])

    note = pack["field_inquiry_notes"][0]
    assert note["claim_scope"] == "qualitative_channel_lead_only"
    assert note["exact_value_authority"] is False
    assert "authority_fact" in note["forbidden_claims"]

    rejection_reasons = {row["reason"] for row in pack["rejected_objects"]}
    assert "channel_offer_forbidden_promotion_attempt" in rejection_reasons
    assert "competitive_comparable_required_fields_missing" in rejection_reasons


def test_product_spec_pack_validation_blocks_boundary_misuse() -> None:
    pack = build_product_spec_pack(_product_pack_state())
    broken = dict(pack)
    broken["channel_offers"] = [dict(pack["channel_offers"][0], exact_value_authority=True)]

    validation = validate_product_spec_pack(broken)

    assert validation["status"] == "fail"
    assert any(error["type"] == "channel_offer_exact_authority_forbidden" for error in validation["errors"])


def test_product_agent_data_view_and_specialist_request_carry_product_spec_pack() -> None:
    state = _product_pack_state()

    view = build_agent_data_view("product_technology_analyst", state)
    request = build_specialist_request_from_state("product_technology_analyst", state)

    assert view["role_context"]["product_spec_pack_required"] is True
    assert view["product_spec_pack_ref"]["summary"]["channel_offer_count"] == 1
    assert request["product_spec_pack"]["summary"]["product_spec_count"] == 1
    assert request["output_contract"]["policy"] == "product_technology_product_spec_pack_claim_cards_v0_2"
    assert "ProductSpecPack" in request["output_contract"]["required_outputs"]
    assert "commerce_h100_offer" in request["known_evidence_refs"]
    assert "field_inquiry_h100_lead_time" in request["known_evidence_refs"]


def test_product_only_activation_counts_as_specialist_subgraph_active() -> None:
    assert _multi_agent_specialists_active({"agent_activation_plan": {"activate_agents": ["product_technology_analyst"]}}) is True
