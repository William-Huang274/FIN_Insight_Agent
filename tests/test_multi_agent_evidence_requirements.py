from __future__ import annotations

import json

from sec_agent.multi_agent_runtime import (
    build_agent_data_view,
    build_multi_agent_evidence_requirement_plan,
    compile_multi_agent_retrieval_plan,
    merge_universe_relationship_evidence_requirements,
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
