from __future__ import annotations

from sec_agent.product_intelligence_depth import (
    AI_SEMIS_PRODUCT_EVIDENCE_PACK_SCHEMA_VERSION,
    build_ai_semis_product_evidence_packs,
    compact_ai_semis_product_evidence_pack_refs,
)
from sec_agent.multi_agent_runtime import build_agent_data_view
from sec_agent.supervising_analyst import build_supervising_analyst_pack


def _route_row(ticker: str = "TST") -> dict:
    return {
        "ticker": ticker,
        "company_name": "Test Semi",
        "family_id": "gpu_accelerator",
        "family_name": "GPU / Accelerator",
        "primary_lane_id": "V1",
        "group_results": [
            {
                "group_id": "company_disclosure",
                "status": "pass",
                "route_statuses": {"primary_company_disclosure": "seed_available_not_materialized"},
            },
            {
                "group_id": "official_product_spec",
                "status": "pass",
                "route_statuses": {"official_product_surface": "runtime_family_row_available"},
            },
            {
                "group_id": "technology_or_ecosystem_signal",
                "status": "pass",
                "route_statuses": {"technology_research_proxy": "seed_available_not_materialized"},
            },
        ],
    }


def _pig_pack_row(ticker: str = "TST") -> dict:
    return {
        "ticker": ticker,
        "company_name": "Test Semi",
        "schema_version": "finsight_product_intelligence_company_pack_v0_1",
        "status": "pass_with_gaps",
        "product_family_count": 1,
        "product_slot_count": 2,
        "product_profile_count": 3,
        "technical_spec_count": 0,
        "product_kpi_exact_count": 0,
        "industry_operating_metric_count": 0,
        "customer_deployment_signal_count": 0,
        "channel_signal_count": 0,
        "supply_chain_signal_count": 0,
        "competitive_edge_count": 0,
        "gap_count": 1,
        "pack_json": {
            "family_ids": ["gpu_accelerator"],
            "representative_product_slots": [
                {
                    "product_slot_id": "slot_1",
                    "family_id": "gpu_accelerator",
                    "family_name": "GPU / Accelerator",
                    "product_slot_name": "Accelerator Family",
                    "claim_boundary": "taxonomy only",
                }
            ],
            "representative_product_profile_or_specs": [
                {
                    "source_row_id": "profile_1",
                    "ticker": ticker,
                    "product_family": "GPU / Accelerator",
                    "product_or_segment": "Accelerator Family",
                    "metric_name": "product_or_service_profile",
                    "claim_boundary": "official profile only",
                }
            ],
            "representative_exact_kpis": [],
            "representative_operating_metrics": [],
            "representative_deployment_rows": [],
            "representative_relationship_edges": [],
        },
    }


def test_route_only_seed_rows_do_not_count_as_evidence_depth() -> None:
    packs, gate, gap_queue = build_ai_semis_product_evidence_packs(
        route_gate_rows=[_route_row()],
        product_intelligence_pack_rows=[_pig_pack_row()],
        source_rows_by_layer={},
        generated_at="2026-06-27T00:00:00Z",
    )

    pack = packs[0]
    assert pack["schema_version"] == AI_SEMIS_PRODUCT_EVIDENCE_PACK_SCHEMA_VERSION
    assert pack["layers"]["product_profile"]["status"] == "evidence_ready"
    assert pack["layers"]["product_spec_architecture"]["status"] == "absent"
    assert pack["layers"]["product_spec_architecture"]["route_materialization"]["materialized_route_available"] is True
    assert pack["layers"]["product_spec_architecture"]["route_materialization"]["counts_as_evidence"] is False
    assert pack["layers"]["product_performance_proxy"]["route_materialization"]["seed_or_route_only_roles"] == [
        "technology_research_proxy"
    ]
    assert pack["depth_status"] == "needs_deep_repair"
    assert gate["status"] == "needs_repair"
    assert gap_queue[0]["action_status"] == "needs_deep_repair"


def test_product_page_value_does_not_become_product_kpi_exact() -> None:
    profile_row = {
        "ticker": "TST",
        "source_id": "company_product_pages",
        "product_family": "GPU / Accelerator",
        "product_or_segment": "Accelerator Family",
        "metric_name": "product revenue",
        "value": "100",
        "unit": "USD",
        "claim_boundary": "product page context only",
    }

    packs, _, _ = build_ai_semis_product_evidence_packs(
        route_gate_rows=[_route_row()],
        product_intelligence_pack_rows=[_pig_pack_row()],
        source_rows_by_layer={"product_profile": [profile_row]},
        generated_at="2026-06-27T00:00:00Z",
    )

    assert packs[0]["layers"]["product_profile"]["row_count"] >= 2
    assert packs[0]["layers"]["product_kpi_exact"]["status"] == "absent"
    assert "Product-KPI exact remains strict" in packs[0]["layers"]["product_kpi_exact"]["claim_boundary"]


def test_deployment_and_proxy_layers_are_context_not_exact_kpi() -> None:
    deployment_row = {
        "ticker": "TST",
        "source_id": "official_customer_deployment_surface",
        "source_role": "official_customer_order_or_deployment_event",
        "product_family": "GPU / Accelerator",
        "product_or_segment": "Accelerator Family",
        "customer": "Cloud Buyer",
        "source_url": "https://example.com/customer",
        "claim_boundary": "deployment context only",
    }
    proxy_row = {
        "ticker": "TST",
        "source_id": "openalex_api",
        "product_family": "GPU / Accelerator",
        "metric_name": "openalex_work_search_result",
        "value": 7,
        "unit": "cited_by_count",
        "claim_boundary": "research proxy only",
    }

    packs, _, _ = build_ai_semis_product_evidence_packs(
        route_gate_rows=[_route_row()],
        product_intelligence_pack_rows=[_pig_pack_row()],
        source_rows_by_layer={
            "customer_deployment_adoption": [deployment_row],
            "product_performance_proxy": [proxy_row],
        },
        generated_at="2026-06-27T00:00:00Z",
    )

    pack = packs[0]
    assert pack["layers"]["customer_deployment_adoption"]["status"] == "evidence_ready"
    assert pack["layers"]["customer_deployment_adoption"]["exact_value_authority"] is False
    assert pack["layers"]["product_performance_proxy"]["status"] == "evidence_ready"
    assert pack["layers"]["product_kpi_exact"]["status"] == "absent"
    assert pack["layers"]["product_relationship_graph"]["status"] == "evidence_ready"
    assert pack["depth_status"] == "pass"


def test_explicit_depth_pack_ref_can_be_consumed_from_state() -> None:
    explicit = _explicit_depth_pack()

    ref = compact_ai_semis_product_evidence_pack_refs(
        {"ai_semis_product_evidence_pack": explicit},
        tickers=["NVDA"],
        autoload=False,
    )

    assert ref["pack_count"] == 1
    assert ref["packs"][0]["ticker"] == "NVDA"
    assert ref["packs"][0]["layer_statuses"]["product_spec_architecture"] == "evidence_ready"


def test_research_lead_and_product_agent_receive_depth_pack_ref() -> None:
    state = {
        "run_id": "unit_product_depth_runtime",
        "focus_tickers": ["NVDA"],
        "query_contract": {"focus_tickers": ["NVDA"]},
        "agent_activation_plan": {
            "execution_mode": "deep_research",
            "activate_agents": ["product_technology_analyst"],
            "agent_priorities": {"product_technology_analyst": "primary"},
        },
        "pre_memo_fact_selection": {"approved_facts": [], "rejected_facts": []},
        "fundamental_statement_pack": {"statement_line_items": [], "analysis_gaps": []},
        "verified_judgment_plan": {"supported_claims": []},
        "ai_semis_product_evidence_pack": _explicit_depth_pack(),
    }

    supervising_pack = build_supervising_analyst_pack(state)
    product_bridge = supervising_pack["product_bridge_pack"]
    data_view = build_agent_data_view("product_technology_analyst", state)

    assert product_bridge["product_evidence_pack_ref"]["pack_count"] == 1
    assert product_bridge["coverage"]["has_product_evidence_pack"] is True
    assert product_bridge["coverage"]["product_evidence_depth_status_counts"] == {"pass": 1}
    assert data_view["product_evidence_pack_ref"]["pack_count"] == 1
    assert data_view["role_context"]["product_evidence_pack_required"] is True


def _explicit_depth_pack() -> dict:
    return {
        "ticker": "NVDA",
        "company_name": "NVIDIA Corporation",
        "depth_status": "pass",
        "strict_depth_status": "pass",
        "evidence_role_count": 6,
        "family_ids": ["gpu_accelerator"],
        "layers": {
            "product_profile": {"status": "detailed_profile_ready"},
            "product_spec_architecture": {"status": "evidence_ready"},
            "product_kpi_exact": {"status": "absent"},
        },
    }
