from __future__ import annotations

import json
from pathlib import Path

from sec_agent.agent_contracts import DEFAULT_GLOBAL_LIMITS
from sec_agent.eval_case_catalog import expand_case_catalog
from sec_agent.industry_playbooks import load_playbook_registry, match_playbook_candidates
from sec_agent.multi_agent_router import ROUTER_SOURCE, route_multi_agent_activation


FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "multi_agent_activation_cases_v0_1.jsonl"
VNEXT_50_CASE_CATALOG_PATH = Path(__file__).resolve().parent / "fixtures" / "fin_agent_vnext_50_case_catalog_v0_1.json"


def _fixture_rows() -> list[dict]:
    rows = []
    with FIXTURE_PATH.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def test_multi_agent_routing_fixtures_exact_mode_and_validation() -> None:
    rows = _fixture_rows()
    assert len(rows) == 5
    correct_modes = 0

    for row in rows:
        result = route_multi_agent_activation(row)
        plan = result["activation_plan"]
        active = set(plan["activate_agents"])

        assert result["source"] == ROUTER_SOURCE
        assert result["validation"]["status"] == "pass", row["case_id"]
        assert plan["execution_mode"] == row["expected_execution_mode"], row["case_id"]
        correct_modes += 1
        assert set(row["required_agents"]) <= active, row["case_id"]
        assert not (set(row["forbidden_agents"]) & active), row["case_id"]
        assert plan["max_tool_calls_total"] <= row["max_tool_calls_total_lte"]
        assert plan["max_tool_calls_total"] <= DEFAULT_GLOBAL_LIMITS["max_tool_calls_total"]
        assert plan["max_second_pass_rounds"] <= DEFAULT_GLOBAL_LIMITS["max_second_pass_rounds"]
        assert plan["max_repair_rounds"] <= DEFAULT_GLOBAL_LIMITS["max_repair_rounds"]

    assert correct_modes == len(rows)


def test_multi_agent_routing_fixtures_all_skipped_agents_have_reasons() -> None:
    for row in _fixture_rows():
        plan = route_multi_agent_activation(row)["activation_plan"]

        assert all(item["agent_id"] and item["reason"] for item in plan["skip_agents"]), row["case_id"]
        assert not (set(plan["activate_agents"]) & {item["agent_id"] for item in plan["skip_agents"]})


def test_run_artifact_inspection_does_not_activate_evidence_retrieval() -> None:
    case = next(row for row in _fixture_rows() if row["case_id"] == "ma_run_coverage_inspect")

    plan = route_multi_agent_activation(case)["activation_plan"]

    assert plan["allowed_source_families"] == ["run_artifact"]
    assert "coverage_reflection" in plan["activate_agents"]
    assert {"sec_operator", "eight_k_operator", "market_operator", "industry_operator"}.isdisjoint(plan["activate_agents"])


def test_deep_research_carries_relationship_rationale_and_bounded_budget() -> None:
    case = next(row for row in _fixture_rows() if row["case_id"] == "ma_ai_capex_supply_chain_deep")

    plan = route_multi_agent_activation(case)["activation_plan"]

    assert plan["execution_mode"] == "deep_research"
    assert plan["scope_mode"] == "full_universe"
    assert plan["relationship_scope_rationale"]
    assert "relationship_graph" in plan["allowed_source_families"]
    assert plan["max_tool_calls_total"] == 12
    assert plan["agent_priorities"]["industry_supply_chain_analyst"] == "primary"
    assert plan["agent_priorities"]["risk_counterevidence_analyst"] == "supporting"


def test_market_snapshot_source_does_not_force_market_valuation_specialist() -> None:
    plan = route_multi_agent_activation(
        {
            "prompt": "诊断 NVDA 与 DELL 的基本面、产品证据、AI server 需求传导、供应链和反证风险。",
            "focus_tickers": ["NVDA", "DELL"],
            "search_scope_tickers": ["NVDA", "DELL", "MSFT", "AMZN", "GOOGL"],
            "context": {
                "execution_mode": "deep_research",
                "source_tiers": [
                    "primary_sec_filing",
                    "company_authored_unaudited_sec_filing",
                    "market_snapshot",
                    "industry_snapshot",
                    "relationship_graph",
                    "company_product_evidence_graph",
                ],
            },
        }
    )["activation_plan"]

    assert "market_operator" in plan["activate_agents"]
    assert "market_snapshot" in plan["allowed_source_families"]
    assert "market_valuation_analyst" not in plan["activate_agents"]


def test_ai_semis_catalog_paid_specialists_match_deterministic_activation() -> None:
    catalog = json.loads(VNEXT_50_CASE_CATALOG_PATH.read_text(encoding="utf-8"))
    cases = expand_case_catalog(
        catalog,
        case_ids=[
            "fin_deep_ai_infra_nvda_dell_capex_023",
            "fin_deep_semicap_asml_amat_lrcx_klac_cycle_025",
        ],
    )

    for case in cases:
        plan = route_multi_agent_activation(case)["activation_plan"]
        active_specialists = {agent for agent in plan["activate_agents"] if agent.endswith("_analyst")}

        assert active_specialists == set(case["expected_paid_specialist_agents"]), case["case_id"]
        assert "market_valuation_analyst" not in active_specialists
        assert plan["agent_priorities"]["risk_counterevidence_analyst"] == "supporting"


def test_forced_context_mode_still_passes_validator() -> None:
    result = route_multi_agent_activation(
        {
            "prompt": "Compare NVDA and AMD with market reaction.",
            "focus_tickers": ["NVDA", "AMD"],
            "search_scope_tickers": ["NVDA", "AMD"],
            "context": {"execution_mode": "standard_memo"},
        }
    )

    assert result["activation_plan"]["execution_mode"] == "standard_memo"
    assert result["validation"]["status"] == "pass"


def test_product_technology_intent_activates_product_specialist() -> None:
    result = route_multi_agent_activation(
        {
            "prompt": "Compare AAPL and MSFT product revenue, product taxonomy, and public proxy gaps.",
            "focus_tickers": ["AAPL", "MSFT"],
            "search_scope_tickers": ["AAPL", "MSFT"],
            "context": {
                "execution_mode": "standard_memo",
                "query_contract": {
                    "metric_families": ["product_revenue"],
                    "source_tiers": ["primary_sec_filing", "company_product_evidence_graph"],
                },
            },
        }
    )
    plan = result["activation_plan"]

    assert result["validation"]["status"] == "pass"
    assert "product_technology_analyst" in plan["activate_agents"]
    assert "company_product_evidence_graph" in plan["allowed_source_families"]
    assert plan["agent_priorities"]["product_technology_analyst"] == "primary"


def test_same_query_uses_different_playbook_source_policy_by_industry_schema() -> None:
    registry = load_playbook_registry()
    consumer_inventory = _inventory_with_playbook(
        match_playbook_candidates({"consumer electronics hardware": {"AAPL", "MSFT"}}, registry),
        available=[
            "primary_sec_filing",
            "company_authored_unaudited_sec_filing",
            "company_product_evidence_graph",
            "public_source_context",
        ],
    )
    bank_inventory = _inventory_with_playbook(
        match_playbook_candidates({"banks": {"JPM", "C"}}, registry),
        available=[
            "primary_sec_filing",
            "company_authored_unaudited_sec_filing",
            "industry_snapshot",
            "market_snapshot",
        ],
    )
    base = {
        "prompt": "Compare these peers' business drivers for a standard memo.",
        "context": {"execution_mode": "standard_memo"},
    }

    consumer_plan = route_multi_agent_activation(
        {**base, "focus_tickers": ["AAPL", "MSFT"], "search_scope_tickers": ["AAPL", "MSFT"], "source_inventory": consumer_inventory}
    )["activation_plan"]
    bank_plan = route_multi_agent_activation(
        {**base, "focus_tickers": ["JPM", "C"], "search_scope_tickers": ["JPM", "C"], "source_inventory": bank_inventory}
    )["activation_plan"]

    assert consumer_plan["metadata"]["industry_schema"] == "consumer_electronics"
    assert "product_technology_analyst" in consumer_plan["activate_agents"]
    assert "company_product_evidence_graph" in consumer_plan["allowed_source_families"]
    assert "public_source_context" in consumer_plan["allowed_source_families"]
    assert bank_plan["metadata"]["industry_schema"] == "banks"
    assert "product_technology_analyst" not in bank_plan["activate_agents"]
    assert "industry_snapshot" in bank_plan["allowed_source_families"]
    assert "market_snapshot" in bank_plan["allowed_source_families"]


def _inventory_with_playbook(candidates: list[dict], *, available: list[str]) -> dict:
    return {
        "playbook_candidates": candidates,
        "available_source_families": available,
        "source_family_availability": {
            family: {"status": "available", "available": True, "row_count": 1}
            for family in available
        },
    }
