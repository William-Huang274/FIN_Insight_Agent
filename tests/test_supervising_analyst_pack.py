from __future__ import annotations

from sec_agent.supervising_analyst import build_supervising_analyst_pack


def test_supervising_analyst_pack_builds_financial_product_and_graph_layers() -> None:
    state = {
        "run_id": "unit_ai_infra",
        "user_query": "AI capex readthrough to server suppliers",
        "pre_memo_fact_selection": {
            "approved_facts": [
                {
                    "selection_id": "f1",
                    "ticker": "GOOGL",
                    "canonical_metric_id": "financial_metric:capex",
                    "period_key": "fiscal:2026:Q1:qtd",
                    "value": "5111.0",
                    "numeric_value": "5111.0",
                    "unit": "usd_millions",
                    "evidence_ref": "ref:googl_capex",
                    "source_family": "primary_sec_filing",
                    "selection_status": "approved",
                },
                {
                    "selection_id": "f2",
                    "ticker": "DELL",
                    "canonical_metric_id": "product_kpi:product_revenue",
                    "product_or_segment": "AI-optimized servers",
                    "period_key": "fiscal:2026:2026",
                    "value": "16132.0",
                    "numeric_value": "16132.0",
                    "unit": "usd_millions",
                    "evidence_ref": "ref:dell_ai_servers",
                    "source_family": "company_authored_unaudited_sec_filing",
                    "selection_status": "approved",
                },
                {
                    "selection_id": "f3",
                    "ticker": "DELL",
                    "canonical_metric_id": "product_kpi:product_revenue",
                    "product_or_segment": "Total ISG net revenue",
                    "period_key": "fiscal:2026:2026:qtd",
                    "value": "29.0",
                    "numeric_value": "29.0",
                    "unit": "usd_billions",
                    "evidence_ref": "ref:dell_isg",
                    "source_family": "company_authored_unaudited_sec_filing",
                    "selection_status": "approved",
                },
            ],
            "rejected_facts": [
                {
                    "selection_id": "r1",
                    "ticker": "MSFT",
                    "canonical_metric_id": "financial_metric:capex",
                    "period_key": "fiscal:2026:Q3:qtd",
                    "reject_reason": "blocking_gate_failed",
                    "conflict_types": ["source_priority_conflict"],
                    "claim_boundary": "unresolved_or_blocked_reconciliation_group_not_memo_eligible",
                }
            ],
        },
        "fundamental_statement_pack": {
            "statement_line_items": [],
            "peer_comparisons": [],
            "analysis_gaps": [],
        },
        "verified_judgment_plan": {
            "supported_claims": [
                {
                    "claim_id": "relationship_1",
                    "claim_type": "relationship_hypothesis",
                    "claim": "MSFT and AMZN are sector-depth peers but direct supplier links are not confirmed.",
                    "ticker_scope": ["MSFT", "AMZN", "DELL"],
                    "metric_scope": ["capex", "supplier_revenue"],
                    "source_families": ["relationship_graph"],
                    "evidence_refs": ["sector_depth_pack:test"],
                }
            ]
        },
    }

    pack = build_supervising_analyst_pack(state)

    assert pack["validation"]["status"] == "pass"
    assert pack["summary"]["product_kpi_count"] >= 2
    assert pack["summary"]["capital_edge_count"] >= 3
    ratios = pack["financial_analysis_model"]["derived_ratios"]
    assert any(row["ratio_name"] == "product_revenue_mix" and row["ticker"] == "DELL" for row in ratios)
    edge_types = {row["edge_type"] for row in pack["capital_transmission_graph"]["edges"]}
    assert "buyer_capex_demand_signal" in edge_types
    assert "supplier_product_revenue_readthrough" in edge_types
    assert "relationship_hypothesis_only" in edge_types
    assert pack["financial_analysis_model"]["numeric_reconciler"]["blocked_fact_count"] == 1
    assert pack["research_lead_synthesis_plan"]["writer_directives"]


def test_supervising_analyst_pack_flags_product_context_without_exact_kpi() -> None:
    state = {
        "run_id": "unit_product_context",
        "verified_judgment_plan": {
            "supported_claims": [
                {
                    "claim_id": "asml_context",
                    "claim_type": "official_product_surface_context",
                    "claim": "ASML official product context names EUV, DUV, and Installed Base Management.",
                    "ticker_scope": ["ASML"],
                    "source_families": ["live_public_web_context"],
                    "evidence_refs": ["official:asml_products"],
                }
            ]
        },
        "pre_memo_fact_selection": {"approved_facts": [], "rejected_facts": []},
        "fundamental_statement_pack": {"statement_line_items": [], "analysis_gaps": []},
    }

    pack = build_supervising_analyst_pack(state)

    product = pack["product_bridge_pack"]
    assert product["coverage"]["has_official_context_without_exact_kpi"] is True
    assert product["coverage"]["has_company_disclosed_product_kpi"] is False
    finding_types = {row["type"] for row in pack["supervision_findings"]["findings"]}
    assert "product_bridge_gap" in finding_types


def test_supervising_analyst_pack_consumes_product_intelligence_graph_context() -> None:
    state = {
        "run_id": "unit_product_intelligence_bridge",
        "focus_tickers": ["NVDA"],
        "query_contract": {"focus_tickers": ["NVDA"]},
        "pre_memo_fact_selection": {"approved_facts": [], "rejected_facts": []},
        "fundamental_statement_pack": {"statement_line_items": [], "analysis_gaps": []},
        "verified_judgment_plan": {"supported_claims": []},
        "product_intelligence_company_pack": {
            "schema_version": "finsight_product_intelligence_company_pack_v0_1",
            "ticker": "NVDA",
            "company_name": "NVIDIA Corporation",
            "status": "pass_with_gaps",
            "representative_exact_kpis": [
                {
                    "source_row_id": "pig_exact:nvda_dc_revenue",
                    "ticker": "NVDA",
                    "product_family": "Data Center",
                    "product_or_segment": "Data Center",
                    "metric_name": "segment revenue",
                    "fact_type": "product_kpi:segment_revenue",
                    "value": "115.2",
                    "unit": "USD billions",
                    "period": "FY2026",
                    "claim_boundary": "company disclosed segment revenue only",
                }
            ],
            "representative_product_profile_or_specs": [
                {
                    "source_row_id": "pig_spec:blackwell_memory",
                    "ticker": "NVDA",
                    "product_family": "GPU / Accelerator",
                    "product_or_segment": "Blackwell GPU",
                    "metric_name": "memory_capacity",
                    "value": "192",
                    "unit": "GB",
                    "period": "2025",
                    "claim_boundary": "official spec context only",
                }
            ],
            "representative_deployment_rows": [
                {
                    "source_row_id": "pig_deploy:cloud_blackwell",
                    "ticker": "NVDA",
                    "product_or_segment": "Blackwell GPU",
                    "counterparty": "major cloud customer",
                    "metric_name": "official deployment announcement",
                    "period": "2026",
                    "claim_boundary": "official deployment context only; no order value authority",
                }
            ],
            "representative_relationship_edges": [
                {
                    "edge_id": "pig_edge:nvda_amd_competes",
                    "authority_type": "competitive_context_candidate",
                    "can_enter_evidence_bundle": True,
                    "edge_type": "COMPETES_WITH",
                    "from_node_id": "company_product_family:NVDA:gpu_accelerator",
                    "to_node_id": "company_product_family:AMD:gpu_accelerator",
                },
                {
                    "edge_id": "pig_edge:nvda_dell_supply",
                    "authority_type": "supply_chain_signal",
                    "can_enter_evidence_bundle": True,
                    "edge_type": "COMPONENT_INPUT_TO",
                    "from_node_id": "company_product_family:NVDA:gpu_accelerator",
                    "to_node_id": "company_product_family:DELL:server_oem",
                },
            ],
        },
    }

    pack = build_supervising_analyst_pack(state)
    product = pack["product_bridge_pack"]

    assert pack["validation"]["status"] == "pass"
    assert product["product_intelligence_pack_ref"]["pack_count"] == 1
    assert product["coverage"]["has_product_intelligence_graph"] is True
    assert product["coverage"]["has_company_disclosed_product_kpi"] is True
    assert product["coverage"]["has_technical_spec_context"] is True
    assert product["coverage"]["has_customer_deployment_signal"] is True
    assert product["coverage"]["has_supply_chain_signal"] is True
    assert product["coverage"]["has_competitive_context"] is True
    assert product["customer_deployment_context"][0]["claim_boundary"].startswith("official deployment")
    assert pack["dimension_evidence_portfolio_ref"]["schema_version"] == "finsight_dimension_evidence_portfolio_ref_v0_1"
    assert pack["summary"]["dimension_ready_count"] >= 1
    synthesis_ref = pack["research_lead_synthesis_plan"]["dimension_evidence_portfolio_ref"]
    assert any(row["dimension_id"] == "product_and_production" for row in synthesis_ref["dimensions"])
