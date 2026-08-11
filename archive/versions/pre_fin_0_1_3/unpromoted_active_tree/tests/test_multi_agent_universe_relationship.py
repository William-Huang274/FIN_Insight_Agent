from __future__ import annotations

from sec_agent.multi_agent_contracts import (
    evidence_requirements_from_universe_relationship_plan,
    normalize_universe_relationship_plan,
    validate_universe_relationship_plan,
)
from sec_agent.multi_agent_runtime import build_agent_data_view


def test_universe_relationship_plan_records_included_excluded_scope_guard_and_evidence_needs() -> None:
    plan = normalize_universe_relationship_plan(
        {
            "scope_mode": "sector_representative",
            "focus_tickers": ["NVDA"],
            "expanded_tickers": ["NVDA", "AMD", "MSFT"],
            "included_tickers": ["NVDA", "AMD", "MSFT"],
            "excluded_tickers": ["INTC"],
            "relationship_scope_rationale": "AI capex readthrough requires peer and customer hypotheses.",
            "budget": {"max_expanded_tickers": 5, "max_relationships": 8},
            "relationships": [
                {
                    "ticker": "NVDA",
                    "related_ticker": "AMD",
                    "relationship_type": "competitor",
                    "direction": "peer",
                    "financial_link_type": "ai_accelerator_competition",
                    "metrics_to_check": ["data_center_revenue", "gross_margin"],
                    "evidence_source_needed": ["primary_sec_filing", "market_snapshot"],
                    "evidence_refs": ["rel_nvda_amd_peer"],
                    "inclusion_rationale": "AMD is included as a direct accelerator peer hypothesis.",
                },
                {
                    "ticker": "NVDA",
                    "related_ticker": "MSFT",
                    "relationship_type": "customer",
                    "direction": "downstream_customer",
                    "metrics_to_check": ["cloud_capex", "data_center_capex"],
                    "evidence_source_needed": ["primary_sec_filing", "industry_snapshot"],
                    "evidence_refs": ["rel_nvda_msft_cloud"],
                    "inclusion_rationale": "MSFT is included as a cloud capex demand readthrough hypothesis.",
                },
            ],
        }
    )
    result = validate_universe_relationship_plan(
        plan,
        known_evidence_refs={"rel_nvda_amd_peer", "rel_nvda_msft_cloud"},
        source_inventory={"available_tickers": ["NVDA", "AMD", "MSFT", "INTC"]},
    )

    assert result["status"] == "pass"
    assert plan["included_tickers"] == ["NVDA", "AMD", "MSFT"]
    assert plan["excluded_tickers"] == ["INTC"]
    assert plan["scope_guard"]["financial_fact_policy"] == "relationship_graph_hypothesis_only"
    assert plan["relationships"][0]["claim_scope"] == "scope_or_hypothesis_only"
    assert plan["relationships"][0]["edge_schema_version"] == "sec_agent_relationship_edge_v0.3"
    assert plan["relationships"][0]["edge_id"].startswith("rel_edge_")
    assert plan["relationships"][0]["from_ticker"] == "NVDA"
    assert plan["relationships"][0]["to_ticker"] == "AMD"
    assert plan["relationships"][0]["metric_links"] == ["data_center_revenue", "gross_margin"]
    assert plan["evidence_requirements"][0]["claim_scope"] == "relationship_hypothesis_not_financial_fact"
    assert plan["evidence_requirements"][1]["source_families"] == ["primary_sec_filing", "industry_snapshot"]


def test_relationship_expansion_requires_evidence_inventory_and_budget_guard() -> None:
    expanded = ["NVDA", "AMD", "MSFT", "AMZN"]
    result = validate_universe_relationship_plan(
        {
            "scope_mode": "full_universe",
            "focus_tickers": ["NVDA"],
            "expanded_tickers": expanded,
            "included_tickers": expanded,
            "budget": {"max_expanded_tickers": 2},
            "relationships": [
                {
                    "ticker": "NVDA",
                    "related_ticker": "AMD",
                    "relationship_type": "competitor",
                    "evidence_refs": ["rel_nvda_amd"],
                    "inclusion_rationale": "Peer hypothesis.",
                }
            ],
        },
        known_evidence_refs={"rel_nvda_amd"},
        source_inventory={"available_tickers": ["NVDA", "AMD"]},
    )
    error_types = {item["type"] for item in result["errors"]}

    assert result["status"] == "fail"
    assert "relationship_scope_rationale_required" in error_types
    assert "relationship_expansion_budget_exceeded" in error_types
    assert "relationship_ticker_not_in_source_inventory" in error_types
    assert "expanded_ticker_without_relationship_evidence" in error_types


def test_relationship_inventory_gate_ignores_query_scope_tickers() -> None:
    result = validate_universe_relationship_plan(
        {
            "scope_mode": "full_universe",
            "focus_tickers": ["NVDA"],
            "expanded_tickers": ["AMD"],
            "included_tickers": ["NVDA", "AMD"],
            "relationship_scope_rationale": "Peer hypothesis.",
            "relationships": [
                {
                    "ticker": "NVDA",
                    "related_ticker": "AMD",
                    "relationship_type": "competitor",
                    "evidence_refs": ["rel_nvda_amd"],
                    "inclusion_rationale": "Peer hypothesis.",
                }
            ],
        },
        known_evidence_refs={"rel_nvda_amd"},
        source_inventory={"tickers": ["NVDA"]},
    )

    assert "relationship_ticker_not_in_source_inventory" not in {item["type"] for item in result["errors"]}


def test_relationship_claim_scope_cannot_support_reported_financial_fact() -> None:
    result = validate_universe_relationship_plan(
        {
            "scope_mode": "sector_representative",
            "focus_tickers": ["NVDA"],
            "expanded_tickers": ["NVDA", "TSM"],
            "relationship_scope_rationale": "Supplier exposure hypothesis.",
            "relationships": [
                {
                    "ticker": "NVDA",
                    "related_ticker": "TSM",
                    "relationship_type": "supplier",
                    "evidence_refs": ["rel_nvda_tsm"],
                    "inclusion_rationale": "Supplier dependency hypothesis.",
                    "claim_scope": "reported_financial_fact",
                }
            ],
        },
        known_evidence_refs={"rel_nvda_tsm"},
        source_inventory={"available_tickers": ["NVDA", "TSM"]},
    )

    assert result["status"] == "fail"
    assert result["errors"][0]["type"] == "relationship_claim_scope_must_be_hypothesis_only"


def test_universe_relationship_evidence_requirements_stay_business_level_no_routes() -> None:
    requirements = evidence_requirements_from_universe_relationship_plan(
        {
            "focus_tickers": ["NVDA"],
            "relationships": [
                {
                    "ticker": "NVDA",
                    "related_ticker": "MSFT",
                    "relationship_type": "customer",
                    "direction": "downstream_customer",
                    "metrics_to_check": ["cloud_capex"],
                    "evidence_source_needed": ["primary_sec_filing", "industry_snapshot"],
                    "inclusion_rationale": "Verify cloud capex readthrough with separate company and industry evidence.",
                }
            ],
        }
    )

    assert requirements[0]["analysis_intent"] == "relationship_hypothesis_verification"
    assert requirements[0]["tickers"] == ["NVDA", "MSFT"]
    assert requirements[0]["planner_boundary"] == "business_need_only_no_physical_paths"
    assert "evidence_routes" not in requirements[0]
    assert "tool_name" not in requirements[0]


def test_industry_supply_chain_data_view_treats_relationship_rows_as_hypothesis_context() -> None:
    view = build_agent_data_view(
        "industry_supply_chain_analyst",
        {
            "universe_relationship_plan": {
                "relationships": [
                    {
                        "ticker": "NVDA",
                        "related_ticker": "MSFT",
                        "relationship_type": "customer",
                        "evidence_refs": ["rel_nvda_msft"],
                        "inclusion_rationale": "Cloud capex readthrough hypothesis.",
                        "notes": "Scope hypothesis only.",
                    }
                ]
            },
            "industry_snapshot_rows": [
                {
                    "evidence_ref": "industry_power_ref",
                    "source_family": "industry_snapshot",
                    "summary": "Power availability is a deployment constraint.",
                }
            ],
        },
    )

    relationship_rows = [row for row in view["bounded_evidence_rows"] if row["source_family"] == "relationship_graph"]

    assert relationship_rows
    assert "hypothesis" in relationship_rows[0]["summary"].lower()
    assert {row["source_family"] for row in view["bounded_evidence_rows"]} == {"industry_snapshot", "relationship_graph"}


def test_industry_supply_chain_data_view_balances_relationship_rows_when_industry_rows_fill_cap() -> None:
    view = build_agent_data_view(
        "industry_supply_chain_analyst",
        {
            "universe_relationship_plan": {
                "relationships": [
                    {
                        "ticker": "NVDA",
                        "related_ticker": "MSFT",
                        "relationship_type": "customer",
                        "evidence_refs": [f"rel_ref_{index}"],
                        "inclusion_rationale": f"Relationship hypothesis {index}.",
                    }
                    for index in range(1, 5)
                ]
            },
            "industry_snapshot_rows": [
                {
                    "evidence_ref": f"industry_ref_{index}",
                    "source_family": "industry_snapshot",
                    "summary": f"Industry context row {index}.",
                }
                for index in range(1, 25)
            ],
        },
    )

    rows = view["bounded_evidence_rows"]
    relationship_rows = [row for row in rows if row["source_family"] == "relationship_graph"]

    assert len(rows) == 16
    assert len(relationship_rows) >= 3
    assert "rel_ref_1" in {row["evidence_ref"] for row in relationship_rows}


def test_deep_research_industry_data_view_expands_budget_and_relationship_quota() -> None:
    view = build_agent_data_view(
        "industry_supply_chain_analyst",
        {
            "agent_activation_plan": {"execution_mode": "deep_research"},
            "universe_relationship_plan": {
                "relationships": [
                    {
                        "ticker": "NVDA",
                        "related_ticker": f"REL{index}",
                        "relationship_type": "customer",
                        "evidence_refs": [f"rel_ref_{index}"],
                        "inclusion_rationale": f"Relationship hypothesis {index}.",
                    }
                    for index in range(1, 9)
                ]
            },
            "industry_snapshot_rows": [
                {
                    "evidence_ref": f"industry_ref_{index}",
                    "source_family": "industry_snapshot",
                    "summary": f"Industry context row {index}.",
                }
                for index in range(1, 45)
            ],
        },
    )

    rows = view["bounded_evidence_rows"]
    relationship_rows = [row for row in rows if row["source_family"] == "relationship_graph"]

    assert len(rows) == 32
    assert len(relationship_rows) >= 6
    assert view["input_budget"]["bounded_evidence_row_budget"] == 32
    assert view["input_budget"]["min_relationship_rows"] == 6
    assert len(view["relationship_summary"]["relationships"]) == 8


def test_industry_supply_chain_data_view_falls_back_to_relationship_lookup_rows_when_plan_is_empty() -> None:
    view = build_agent_data_view(
        "industry_supply_chain_analyst",
        {
            "universe_relationship_plan": {"relationships": []},
            "relationship_graph_observation": {
                "relationship_rows": [
                    {
                        "evidence_ref": "lookup_rel_ref_1",
                        "source_family": "relationship_graph",
                        "ticker": "SRE",
                        "related_ticker": "XEL",
                        "relationship_type": "sector_peer",
                        "summary": "Utilities bounded relationship hypothesis.",
                    }
                ]
            },
            "industry_snapshot_rows": [
                {
                    "evidence_ref": "industry_power_ref",
                    "source_family": "industry_snapshot",
                    "summary": "Power availability is a deployment constraint.",
                }
            ],
        },
    )

    relationship_rows = [row for row in view["bounded_evidence_rows"] if row["source_family"] == "relationship_graph"]

    assert relationship_rows
    assert relationship_rows[0]["evidence_ref"] == "lookup_rel_ref_1"
    assert view["relationship_summary"]["relationships"][0]["evidence_ref"] == "lookup_rel_ref_1"
