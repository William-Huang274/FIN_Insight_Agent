from __future__ import annotations

import json

from sec_agent.multi_agent_runtime import (
    build_evidence_fusion_bundle,
    build_agent_data_view,
    build_multi_agent_evidence_requirement_plan,
    compile_multi_agent_retrieval_plan,
    merge_universe_relationship_evidence_requirements,
    plan_reflection_gate,
    validate_multi_agent_evidence_requirement_plan,
)


def test_multi_agent_evidence_requirements_attach_source_and_operator_owners() -> None:
    plan = build_multi_agent_evidence_requirement_plan(
        _query_contract(),
        activation_plan={
            "allowed_source_families": [
                "primary_sec_filing",
                "company_authored_unaudited_sec_filing",
                "market_snapshot",
                "industry_snapshot",
            ]
        },
    )

    by_route = {
        route: req
        for req in plan["requirements"]
        for route in req["evidence_routes"]
    }

    assert plan["multi_agent_evidence_requirement_validation"]["status"] == "pass"
    assert by_route["ledger_first"]["operator_owners"] == ["sec_operator"]
    assert by_route["filing_text"]["source_families"] == ["primary_sec_filing"]
    assert by_route["8k_commentary"]["operator_owners"] == ["eight_k_operator"]
    assert by_route["market_snapshot"]["source_families"] == ["market_snapshot"]
    assert by_route["industry_snapshot"]["operator_owners"] == ["industry_operator"]
    assert all(req["planner_boundary"] == "business_need_only_no_physical_paths" for req in plan["requirements"])


def test_multi_agent_evidence_requirement_validation_rejects_source_and_owner_mismatch() -> None:
    result = validate_multi_agent_evidence_requirement_plan(
        {
            "schema_version": "sec_agent_retrieval_plan_v0.1",
            "requirements": [
                {
                    "requirement_id": "req_market",
                    "evidence_routes": ["market_snapshot"],
                    "source_families": ["primary_sec_filing"],
                    "operator_owners": ["sec_operator"],
                }
            ],
        },
        activation_plan={"allowed_source_families": ["primary_sec_filing"]},
    )
    error_types = {item["type"] for item in result["errors"]}

    assert result["status"] == "fail"
    assert "source_family_mismatch" in error_types
    assert "operator_owner_mismatch" in error_types
    assert "source_family_not_allowed_for_activation" in error_types


def test_evidence_requirement_validation_allows_context_only_product_sources_with_sec_routes() -> None:
    result = validate_multi_agent_evidence_requirement_plan(
        {
            "schema_version": "sec_agent_evidence_requirement_plan_v0.1",
            "requirements": [
                {
                    "requirement_id": "req_product_evidence",
                    "evidence_routes": ["filing_text", "8k_commentary"],
                    "source_families": [
                        "primary_sec_filing",
                        "company_authored_unaudited_sec_filing",
                        "company_product_evidence_graph",
                        "public_source_context",
                    ],
                    "operator_owners": ["sec_operator", "eight_k_operator"],
                }
            ],
        },
        activation_plan={
            "allowed_source_families": [
                "primary_sec_filing",
                "company_authored_unaudited_sec_filing",
                "company_product_evidence_graph",
                "public_source_context",
            ]
        },
    )

    assert result["status"] == "pass"
    assert result["errors"] == []


def test_evidence_requirement_validation_allows_compatible_sec_exact_source_families() -> None:
    result = validate_multi_agent_evidence_requirement_plan(
        {
            "schema_version": "sec_agent_evidence_requirement_plan_v0.1",
            "requirements": [
                {
                    "requirement_id": "req_sec_exact_context",
                    "evidence_routes": ["filing_text"],
                    "source_families": [
                        "primary_sec_filing",
                        "company_authored_unaudited_sec_filing",
                    ],
                    "operator_owners": ["sec_operator"],
                }
            ],
        },
        activation_plan={
            "allowed_source_families": [
                "primary_sec_filing",
                "company_authored_unaudited_sec_filing",
            ]
        },
    )

    assert result["status"] == "pass"
    assert result["errors"] == []


def test_run_artifact_evidence_route_maps_to_coverage_reflection() -> None:
    result = validate_multi_agent_evidence_requirement_plan(
        {
            "schema_version": "sec_agent_evidence_requirement_plan_v0.1",
            "requirements": [
                {
                    "requirement_id": "req_run_artifact",
                    "evidence_routes": ["run_artifact"],
                    "source_families": ["run_artifact"],
                    "operator_owners": ["coverage_reflection"],
                }
            ],
        },
        activation_plan={"allowed_source_families": ["run_artifact"]},
    )

    assert result["status"] == "pass"
    assert result["errors"] == []


def test_relationship_graph_evidence_route_maps_to_universe_relationship() -> None:
    result = validate_multi_agent_evidence_requirement_plan(
        {
            "schema_version": "sec_agent_evidence_requirement_plan_v0.1",
            "requirements": [
                {
                    "requirement_id": "req_relationship_scope",
                    "evidence_routes": ["relationship_graph"],
                    "source_families": ["relationship_graph"],
                    "operator_owners": ["universe_relationship"],
                }
            ],
        },
        activation_plan={"allowed_source_families": ["relationship_graph"]},
    )

    assert result["status"] == "pass"
    assert result["errors"] == []


def test_milvus_semantic_route_maps_to_explicit_semantic_source_family() -> None:
    result = validate_multi_agent_evidence_requirement_plan(
        {
            "schema_version": "sec_agent_evidence_requirement_plan_v0.1",
            "requirements": [
                {
                    "requirement_id": "req_semantic",
                    "evidence_routes": ["milvus_semantic"],
                    "source_families": ["milvus_semantic"],
                    "operator_owners": ["sec_operator"],
                }
            ],
        },
        activation_plan={"allowed_source_families": ["milvus_semantic"]},
    )

    assert result["status"] == "pass"
    assert result["errors"] == []


def test_evidence_fusion_promotes_runtime_product_fact_scope() -> None:
    bundle = build_evidence_fusion_bundle(
        {
            "product_evidence_rows": [
                {
                    "evidence_ref": "prod_nvda_dc_revenue",
                    "source_family": "company_product_evidence_graph",
                    "ticker": "NVDA",
                    "product_or_segment": "Data Center",
                    "metric_family": "product_revenue",
                    "value": "47,525",
                    "unit": "USD millions",
                    "promotion_status": "runtime_fact_allowed",
                }
            ]
        }
    )

    row = bundle["authority_rows"][0]

    assert row["source_family"] == "company_product_evidence_graph"
    assert row["authority_tier"] == "company_disclosed_product_kpi_fact"
    assert row["claim_scope"] == "company_disclosed_product_kpi_fact"
    assert row["exact_value_authority"] is True
    assert row["runtime_fact_allowed"] is True
    assert bundle["summary"]["product_runtime_fact_count"] == 1
    assert bundle["summary"]["exact_authority_row_count"] == 1


def test_evidence_fusion_keeps_public_source_context_out_of_exact_authority() -> None:
    bundle = build_evidence_fusion_bundle(
        {
            "public_source_context_rows": [
                {
                    "evidence_ref": "openfda_lly_context",
                    "source_family": "public_source_context",
                    "underlying_source_family": "openfda",
                    "ticker": "LLY",
                    "metric": "adverse_event_context",
                    "summary": "openFDA context lead",
                    "exact_value_authority": True,
                }
            ]
        }
    )

    row = bundle["authority_rows"][0]

    assert row["source_family"] == "public_source_context"
    assert row["authority_tier"] == "context_or_proxy"
    assert row["exact_value_authority"] is False
    assert row["context_only"] is True
    assert bundle["summary"]["public_exact_authority_violation_count"] == 0


def test_evidence_fusion_keeps_milvus_semantic_out_of_exact_values() -> None:
    bundle = build_evidence_fusion_bundle(
        {
            "context_rows": [
                {
                    "evidence_ref": "sem_amd_ai",
                    "source_family": "primary_sec_filing",
                    "retrieval_route": "milvus_semantic",
                    "vector_kind": "narrative_chunk",
                    "ticker": "AMD",
                    "summary": "semantic recall hit for AI demand commentary",
                    "exact_value_authority": True,
                }
            ]
        }
    )

    row = bundle["authority_rows"][0]

    assert row["source_family"] == "milvus_semantic"
    assert row["semantic_supplement"] is True
    assert row["claim_scope"] == "filing_semantic_recall_supplement_only"
    assert row["exact_value_authority"] is False
    assert bundle["summary"]["semantic_exact_authority_violation_count"] == 0


def test_evidence_fusion_builds_bounded_gap_register() -> None:
    bundle = build_evidence_fusion_bundle(
        {
            "source_gaps": [
                {
                    "gap_id": "gap_rx_sales",
                    "source_family": "company_product_evidence_graph",
                    "ticker": "PFE",
                    "metric_family": "product_revenue",
                    "product_or_segment": "Eliquis",
                    "reason": "commercial tracker required for true prescription volume",
                }
            ],
            "product_evidence_rows": [
                {
                    "evidence_ref": "gap_region_schema",
                    "source_family": "company_product_evidence_graph",
                    "ticker": "MDT",
                    "metric_family": "product_revenue",
                    "promotion_status": "gap_exposed_not_fallback",
                    "reason": "regional columns require product-region revenue schema",
                }
            ],
        }
    )

    register = bundle["bounded_gap_register"]
    gap_types = {row["gap_id"]: row["gap_type"] for row in register["gaps"]}

    assert register["gap_count"] == 2
    assert gap_types["gap_rx_sales"] == "commercial_tracker_gap"
    assert gap_types["gap_region_schema"] == "parser_schema_gap"
    assert all(row["claim_boundary"] == "do_not_fill_with_generic_fallback_or_proxy_fact" for row in register["gaps"])


def test_plan_reflection_gate_rejects_required_source_family_missing_from_inventory() -> None:
    report = plan_reflection_gate(
        {
            "execution_mode": "standard_memo",
            "activate_agents": ["research_lead", "sec_operator", "coverage_reflection", "memo_writer", "verifier", "renderer"],
            "allowed_source_families": ["primary_sec_filing", "company_product_evidence_graph"],
            "metadata": {"required_source_families": ["company_product_evidence_graph"]},
        },
        activation_validation={"status": "pass"},
        source_inventory={
            "available_source_families": ["primary_sec_filing"],
            "source_family_availability": {
                "company_product_evidence_graph": {"status": "unavailable", "available": False},
            },
        },
    )

    assert report["status"] == "fail"
    assert {error["type"] for error in report["errors"]} == {"required_source_family_unavailable"}
    assert report["repair_requests"][0]["action"] == "repair_activation_plan_before_retrieval"


def test_plan_reflection_gate_rejects_milvus_when_runtime_unavailable() -> None:
    report = plan_reflection_gate(
        {
            "execution_mode": "focused_answer",
            "activate_agents": ["research_lead", "sec_operator", "coverage_reflection", "memo_writer", "verifier", "renderer"],
            "allowed_source_families": ["primary_sec_filing", "milvus_semantic"],
        },
        activation_validation={"status": "pass"},
        source_inventory={
            "available_source_families": ["primary_sec_filing"],
            "milvus_runtime": {"status": "unavailable", "available": False, "location": "none"},
        },
    )

    assert report["status"] == "fail"
    assert {error["type"] for error in report["errors"]} == {"milvus_semantic_requested_but_unavailable"}


def test_plan_reflection_gate_rejects_live_web_without_scope_policy() -> None:
    report = plan_reflection_gate(
        {
            "execution_mode": "standard_memo",
            "activate_agents": ["research_lead", "coverage_reflection", "memo_writer", "verifier", "renderer"],
            "allowed_source_families": ["primary_sec_filing", "live_public_web_context"],
        },
        activation_validation={"status": "pass"},
        source_inventory={
            "available_source_families": ["primary_sec_filing", "live_public_web_context"],
            "live_public_web_context": {
                "status": "policy_available",
                "available": True,
                "web_scope_policy_ids": ["major_financial_news"],
            },
        },
    )

    assert report["status"] == "fail"
    assert {error["type"] for error in report["errors"]} == {"live_web_scope_policy_required"}


def test_plan_reflection_gate_rejects_wrong_industry_schema_for_playbook_candidates() -> None:
    report = plan_reflection_gate(
        {
            "execution_mode": "standard_memo",
            "activate_agents": ["research_lead", "sec_operator", "coverage_reflection", "memo_writer", "verifier", "renderer"],
            "allowed_source_families": ["primary_sec_filing"],
            "metadata": {"industry_schema": "banks", "selected_playbook_ids": ["banks"]},
        },
        activation_validation={"status": "pass"},
        source_inventory={
            "available_source_families": ["primary_sec_filing"],
            "playbook_candidates": [{"playbook_id": "semiconductors", "industry_schema": "semiconductors"}],
        },
    )

    assert report["status"] == "fail"
    error_types = {error["type"] for error in report["errors"]}
    assert "industry_schema_not_supported_by_inventory_playbooks" in error_types
    assert "selected_playbook_not_in_inventory_candidates" in error_types


def test_plan_reflection_exposes_playbook_forbidden_claims_for_verifier() -> None:
    report = plan_reflection_gate(
        {
            "execution_mode": "standard_memo",
            "activate_agents": ["research_lead", "sec_operator", "industry_operator", "coverage_reflection", "memo_writer", "verifier", "renderer"],
            "allowed_source_families": ["primary_sec_filing", "industry_snapshot"],
            "metadata": {"industry_schema": "banks", "selected_playbook_ids": ["banks"]},
        },
        activation_validation={"status": "pass"},
        source_inventory={
            "available_source_families": ["primary_sec_filing", "industry_snapshot"],
            "source_family_availability": {
                "primary_sec_filing": {"status": "available", "available": True},
                "industry_snapshot": {"status": "available", "available": True},
            },
            "playbook_candidates": [
                {
                    "playbook_id": "banks",
                    "industry_schema": "banks",
                    "default_source_families": ["primary_sec_filing", "industry_snapshot"],
                    "source_family_policy": {"industry_snapshot": {"allowed_claims": ["rate_cycle_context"]}},
                    "forbidden_claims": ["macro_rate_as_company_NII"],
                    "commercial_gap_policy": {"card_spend": ["issuer_disclosure"]},
                    "specialist_routing": {"industry_supply_chain_analyst": "medium"},
                }
            ],
        },
    )

    assert report["status"] == "pass"
    assert report["playbook_policy"]["selected_playbook_ids"] == ["banks"]
    assert "macro_rate_as_company_NII" in report["playbook_policy"]["forbidden_claims"]
    assert "playbook_forbidden_claims_available_for_verifier" in {item["type"] for item in report["warnings"]}


def test_relationship_requirements_are_capped_by_activation_tool_budget() -> None:
    base = {
        "schema_version": "sec_agent_evidence_requirement_plan_v0.1",
        "requirements": [
            {
                "requirement_id": "req_base",
                "evidence_routes": ["ledger_first", "filing_text"],
                "source_families": ["primary_sec_filing"],
                "operator_owners": ["sec_operator"],
            }
        ],
    }
    relationship_plan = {
        "relationships": [
            {
                "ticker": "NVDA",
                "related_ticker": ticker,
                "relationship_type": "sector",
                "evidence_refs": [f"rel_nvda_{ticker.lower()}"],
                "inclusion_rationale": "Sector readthrough hypothesis.",
                "evidence_source_needed": [
                    "primary_sec_filing",
                    "company_authored_unaudited_sec_filing",
                    "market_snapshot",
                    "industry_snapshot",
                ],
            }
            for ticker in ("DELL", "ANET", "SMCI")
        ]
    }

    merged = merge_universe_relationship_evidence_requirements(
        base,
        relationship_plan,
        activation_plan={
            "activate_agents": ["universe_relationship"],
            "allowed_source_families": [
                "primary_sec_filing",
                "company_authored_unaudited_sec_filing",
                "market_snapshot",
                "industry_snapshot",
            ],
            "max_tool_calls_total": 5,
        },
    )

    added_routes = sum(
        len(req["evidence_routes"])
        for req in merged["requirements"]
        if str(req.get("requirement_id") or "").startswith("req_relationship")
    )
    assert added_routes == 2
    assert merged["relationship_evidence_requirement_policy"]["max_added_routes"] == 2
    assert merged["multi_agent_evidence_requirement_validation"]["status"] == "pass"


def test_compiled_retrieval_routes_are_capped_by_agent_permission_matrix() -> None:
    plan = {
        "requirements": [
            {
                "requirement_id": f"req_{index}",
                "task_id": f"task_{index}",
                "question_zh": "Need filing text.",
                "tickers": ["NVDA"],
                "years": [2026],
                "filing_types": ["10-Q"],
                "source_tiers": ["primary_sec_filing"],
                "evidence_routes": ["filing_text"],
            }
            for index in range(1, 7)
        ]
    }

    retrieval_plan = compile_multi_agent_retrieval_plan(
        plan,
        query_contract={
            "focus_tickers": ["NVDA"],
            "search_scope_tickers": ["NVDA"],
            "years": [2026],
            "filing_types": ["10-Q"],
            "source_tiers": ["primary_sec_filing"],
        },
        activation_plan={"max_tool_calls_total": 12},
    )

    assert len(retrieval_plan["routes"]) == 4
    assert retrieval_plan["route_budget_pruning"]["dropped_route_count"] == 2
    assert {route["retrieval_route"] for route in retrieval_plan["routes"]} == {"filing_text"}


def test_standard_compiled_retrieval_routes_coalesce_same_scope_before_budget() -> None:
    plan = {
        "requirements": [
            {
                "requirement_id": "req_revenue",
                "task_id": "fundamentals_revenue",
                "question_zh": "Need filing text for revenue.",
                "tickers": ["NVDA", "AMD"],
                "years": [2026],
                "filing_types": ["10-Q"],
                "source_tiers": ["primary_sec_filing"],
                "metric_families": ["revenue"],
                "evidence_routes": ["filing_text"],
            },
            {
                "requirement_id": "req_margin",
                "task_id": "fundamentals_margin",
                "question_zh": "Need filing text for margins.",
                "tickers": ["AMD", "NVDA"],
                "years": [2026],
                "filing_types": ["10-Q"],
                "source_tiers": ["primary_sec_filing"],
                "metric_families": ["gross_margin"],
                "evidence_routes": ["filing_text"],
            },
        ]
    }

    retrieval_plan = compile_multi_agent_retrieval_plan(
        plan,
        query_contract={
            "focus_tickers": ["NVDA", "AMD"],
            "search_scope_tickers": ["NVDA", "AMD"],
            "years": [2026],
            "filing_types": ["10-Q"],
            "source_tiers": ["primary_sec_filing"],
        },
        activation_plan={"execution_mode": "standard_memo", "max_tool_calls_total": 12},
    )

    assert len(retrieval_plan["routes"]) == 1
    assert retrieval_plan["routes"][0]["metric_families"] == ["revenue", "gross_margin"]
    assert retrieval_plan["route_coalescing"]["original_route_count"] == 2
    assert retrieval_plan["summary"]["route_count"] == 1


def test_research_lead_data_view_is_summary_inventory_and_artifact_refs_only() -> None:
    view = build_agent_data_view(
        "research_lead",
        {
            "run_id": "unit_run",
            "agent_activation_plan": {"execution_mode": "focused_answer", "allowed_source_families": ["primary_sec_filing"]},
            "project_inventory": {"source_families": ["primary_sec_filing"], "private_path": "data/raw_private/source.json"},
            "artifact_refs": {"context": "data/raw_private/context.json"},
            "context_rows": [{"evidence_ref": "sec_ref_1", "summary": "Should not be exposed to lead."}],
        },
    )

    payload = json.dumps(view, ensure_ascii=False)
    assert view["status"] == "pass"
    assert "bounded_evidence_rows" not in view
    assert "source_inventory" in view
    assert "artifact_refs" in view
    assert "data/raw_private" not in payload
    assert "private_path" not in payload


def test_research_lead_data_view_compacts_full_inventory_to_brief_v02() -> None:
    view = build_agent_data_view(
        "research_lead",
        {
            "project_inventory": {
                "schema_version": "project_source_inventory_v0.1",
                "inventory_digest": "digest123",
                "company_count": 1,
                "filing_count": 1,
                "years": [2025],
                "form_types": {"10-K": 1},
                "source_tiers": {"primary_sec_filing": 1},
                "available_source_families": ["primary_sec_filing", "milvus_semantic"],
                "manifest_path": "data/raw_private/source.jsonl",
                "indexes": {"bm25_index_dir": "data/indexes/bm25/sec"},
                "companies": [{"ticker": "NVDA", "private_path": "data/raw_private/nvda.json"}],
                "milvus_runtime": {
                    "source_family": "milvus_semantic",
                    "status": "cloud_available",
                    "available": True,
                    "location": "cloud",
                    "exact_value_authority": False,
                    "summary_path": "data/processed_private/milvus/summary.json",
                },
            }
        },
    )

    payload = json.dumps(view, ensure_ascii=False)
    inventory = view["source_inventory"]

    assert inventory["schema_version"] == "project_inventory_brief_v0.2"
    assert inventory["milvus_runtime"]["status"] == "cloud_available"
    assert "companies" not in inventory
    assert "data/raw_private" not in payload
    assert "data/processed_private" not in payload
    assert "data/indexes" not in payload


def test_industry_supply_chain_data_view_uses_bounded_industry_and_relationship_rows() -> None:
    view = build_agent_data_view(
        "industry_supply_chain_analyst",
        {
            "industry_snapshot_rows": [
                {
                    "evidence_ref": "industry_ref_1",
                    "source_family": "industry_snapshot",
                    "ticker": "NVDA",
                    "summary": "Data center power demand remains a sector constraint.",
                    "private_path": "data/raw_private/industry.json",
                }
            ],
            "universe_relationship_plan": {
                "relationships": [
                    {
                        "ticker": "NVDA",
                        "related_ticker": "MSFT",
                        "relationship_type": "customer",
                        "evidence_refs": ["rel_ref_1"],
                        "notes": "MSFT is included as a cloud capex readthrough hypothesis.",
                    }
                ]
            },
        },
    )

    rows = view["bounded_evidence_rows"]
    payload = json.dumps(view, ensure_ascii=False)
    assert {row["source_family"] for row in rows} == {"industry_snapshot", "relationship_graph"}
    assert {row["evidence_ref"] for row in rows} == {"industry_ref_1", "rel_ref_1"}
    assert "private_path" not in payload
    assert "data/raw_private" not in payload


def test_product_data_view_exposes_bounded_gap_when_product_sources_requested_but_empty() -> None:
    view = build_agent_data_view(
        "product_technology_analyst",
        {
            "agent_activation_plan": {
                "execution_mode": "deep_research",
                "activate_agents": ["product_technology_analyst"],
            },
            "query_contract": {
                "focus_tickers": ["NVDA", "DELL"],
                "search_scope_tickers": ["NVDA", "DELL", "ANET", "VRT"],
                "source_tiers": ["company_product_evidence_graph", "public_source_context"],
                "metric_families": ["product_revenue", "orders_backlog"],
            },
            "product_evidence_rows": [],
            "public_source_context_rows": [],
            "context_rows": [],
        },
    )

    rows = view["bounded_evidence_rows"]
    families = {row["source_family"] for row in rows}

    assert {"company_product_evidence_graph", "public_source_context"} <= families
    assert {row["promotion_status"] for row in rows} == {"gap_exposed_not_fallback"}
    assert {row["claim_scope"] for row in rows} == {"bounded_gap_only"}
    assert all(row["exact_value_authority"] is False for row in rows)
    assert all("Do not fill with generic SEC or market proxy facts" in row["summary"] for row in rows)


def test_supporting_specialist_data_view_uses_priority_budget() -> None:
    view = build_agent_data_view(
        "risk_counterevidence_analyst",
        {
            "agent_activation_plan": {
                "execution_mode": "deep_research",
                "activate_agents": ["risk_counterevidence_analyst"],
                "agent_priorities": {"risk_counterevidence_analyst": "supporting"},
            },
            "context_rows": [
                {
                    "evidence_ref": f"risk_ref_{index}",
                    "source_family": "primary_sec_filing",
                    "summary": f"Risk evidence row {index}.",
                }
                for index in range(40)
            ],
        },
    )

    assert view["input_budget"]["agent_priority"] == "supporting"
    assert view["input_budget"]["bounded_evidence_row_budget"] == 20
    assert len(view["bounded_evidence_rows"]) == 20


def test_comparative_fundamental_data_view_preserves_focus_ticker_primary_rows() -> None:
    view = build_agent_data_view(
        "fundamental_analyst",
        {
            "agent_activation_plan": {"execution_mode": "standard_memo"},
            "query_contract": {"focus_tickers": ["NVDA", "AMD"]},
            "runtime_ledger_rows": [
                {
                    "metric_id": f"amd_ref_{index}",
                    "source_family": "primary_sec_filing",
                    "ticker": "AMD",
                    "metric": "revenue",
                    "summary": f"AMD revenue row {index}.",
                }
                for index in range(1, 40)
            ]
            + [
                {
                    "metric_id": f"nvda_ref_{index}",
                    "source_family": "primary_sec_filing",
                    "ticker": "NVDA",
                    "metric": "revenue",
                    "summary": f"NVDA revenue row {index}.",
                }
                for index in range(1, 4)
            ],
        },
    )

    rows = view["bounded_evidence_rows"]
    tickers = {row["ticker"] for row in rows}

    assert {"NVDA", "AMD"} <= tickers
    assert view["bounded_row_distribution"]["by_ticker"]["NVDA"] >= 1
    assert view["bounded_row_distribution"]["by_ticker_source_family"]["NVDA|primary_sec_filing"] >= 1


def test_comparative_fundamental_data_view_soft_balances_focus_tickers() -> None:
    view = build_agent_data_view(
        "fundamental_analyst",
        {
            "agent_activation_plan": {"execution_mode": "standard_memo"},
            "query_contract": {"focus_tickers": ["NVDA", "AMD"]},
            "runtime_ledger_rows": [
                {
                    "metric_id": f"amd_ref_{index}",
                    "source_family": "primary_sec_filing",
                    "ticker": "AMD",
                    "metric": "revenue",
                    "summary": f"AMD revenue row {index}.",
                }
                for index in range(1, 40)
            ]
            + [
                {
                    "metric_id": f"nvda_ref_{index}",
                    "source_family": "primary_sec_filing",
                    "ticker": "NVDA",
                    "metric": "revenue",
                    "summary": f"NVDA revenue row {index}.",
                }
                for index in range(1, 40)
            ],
        },
    )

    distribution = view["bounded_row_distribution"]["by_ticker"]

    assert distribution["NVDA"] >= 10
    assert distribution["AMD"] >= 10


def test_comparative_risk_data_view_preserves_market_snapshot_rows() -> None:
    view = build_agent_data_view(
        "risk_counterevidence_analyst",
        {
            "agent_activation_plan": {"execution_mode": "standard_memo"},
            "query_contract": {"focus_tickers": ["NVDA", "AMD"]},
            "runtime_ledger_rows": [
                {
                    "metric_id": f"amd_ref_{index}",
                    "source_family": "primary_sec_filing",
                    "ticker": "AMD",
                    "metric": "revenue",
                    "summary": f"AMD revenue row {index}.",
                }
                for index in range(1, 30)
            ]
            + [
                {
                    "metric_id": f"nvda_ref_{index}",
                    "source_family": "primary_sec_filing",
                    "ticker": "NVDA",
                    "metric": "revenue",
                    "summary": f"NVDA revenue row {index}.",
                }
                for index in range(1, 30)
            ],
            "market_snapshot_rows": [
                {"evidence_ref": "market_nvda", "source_family": "market_snapshot", "ticker": "NVDA", "summary": "NVDA market row."},
                {"evidence_ref": "market_amd", "source_family": "market_snapshot", "ticker": "AMD", "summary": "AMD market row."},
            ],
        },
    )

    distribution = view["bounded_row_distribution"]

    assert distribution["by_source_family"]["market_snapshot"] == 2
    assert distribution["by_ticker"]["NVDA"] >= 1
    assert distribution["by_ticker"]["AMD"] >= 1


def test_comparative_risk_data_view_preserves_untickered_industry_rows() -> None:
    view = build_agent_data_view(
        "risk_counterevidence_analyst",
        {
            "agent_activation_plan": {"execution_mode": "standard_memo"},
            "query_contract": {"focus_tickers": ["XOM", "CVX"]},
            "runtime_ledger_rows": [
                {
                    "metric_id": f"xom_ref_{index}",
                    "source_family": "primary_sec_filing",
                    "ticker": "XOM",
                    "metric": "cash_flow",
                    "summary": f"XOM cash-flow row {index}.",
                }
                for index in range(1, 30)
            ]
            + [
                {
                    "metric_id": f"cvx_ref_{index}",
                    "source_family": "primary_sec_filing",
                    "ticker": "CVX",
                    "metric": "cash_flow",
                    "summary": f"CVX cash-flow row {index}.",
                }
                for index in range(1, 30)
            ],
            "industry_snapshot_rows": [
                {"evidence_ref": "oil_ref", "source_family": "industry_snapshot", "summary": "Oil commodity context."},
                {"evidence_ref": "gas_ref", "source_family": "industry_snapshot", "summary": "Gas commodity context."},
            ],
        },
    )

    distribution = view["bounded_row_distribution"]

    assert distribution["by_source_family"]["industry_snapshot"] == 2


def test_memo_writer_data_view_only_contains_verified_summary() -> None:
    view = build_agent_data_view(
        "memo_writer",
        {
            "context_rows": [{"evidence_ref": "sec_ref_1", "summary": "Raw row not allowed.", "path": "data/raw_private/sec.txt"}],
            "judgment_plan": {
                "supported_claims": [{"claim": "Supported claim", "evidence_refs": ["sec_ref_1"]}],
                "memo_constraints": {"source_boundary": "primary_sec_filing only"},
            },
            "specialist_verification": {"status": "pass", "memo_writer_allowed": True},
        },
    )
    payload = json.dumps(view, ensure_ascii=False)

    assert view["allowed_data_views"] == ["verified_summary"]
    assert "bounded_evidence_rows" not in view
    assert "context_rows" not in payload
    assert "data/raw_private" not in payload
    assert view["verified_summary"]["memo_writer_allowed"] is True


def _query_contract() -> dict:
    return {
        "focus_tickers": ["NVDA"],
        "search_scope_tickers": ["NVDA", "AMD"],
        "years": [2026],
        "filing_types": ["10-Q", "8-K"],
        "source_tiers": ["primary_sec_filing", "company_authored_unaudited_sec_filing"],
        "metric_families": ["revenue", "capex"],
        "evidence_requirement_plan": {
            "requirements": [
                {
                    "requirement_id": "req_sec",
                    "task_id": "fundamental",
                    "question": "Need reported fundamentals.",
                    "tickers": ["NVDA"],
                    "years": [2026],
                    "filing_types": ["10-Q"],
                    "source_tiers": ["primary_sec_filing"],
                    "metric_families": ["revenue"],
                    "evidence_routes": ["ledger_first", "filing_text"],
                },
                {
                    "requirement_id": "req_8k",
                    "task_id": "commentary",
                    "question": "Need management commentary.",
                    "tickers": ["NVDA"],
                    "years": [2026],
                    "filing_types": ["8-K"],
                    "source_tiers": ["company_authored_unaudited_sec_filing"],
                    "metric_families": ["capex"],
                    "evidence_routes": ["8k_commentary"],
                },
                {
                    "requirement_id": "req_market",
                    "task_id": "market",
                    "question": "Need market reaction.",
                    "tickers": ["NVDA"],
                    "years": [2026],
                    "filing_types": ["10-Q"],
                    "source_tiers": ["primary_sec_filing"],
                    "evidence_routes": ["market_snapshot"],
                },
                {
                    "requirement_id": "req_industry",
                    "task_id": "industry",
                    "question": "Need industry context.",
                    "tickers": ["NVDA"],
                    "years": [2026],
                    "filing_types": ["10-Q"],
                    "source_tiers": ["primary_sec_filing"],
                    "evidence_routes": ["industry_snapshot"],
                },
            ]
        },
    }
