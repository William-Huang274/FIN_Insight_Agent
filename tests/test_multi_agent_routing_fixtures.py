from __future__ import annotations

import json
from pathlib import Path

from sec_agent.agent_contracts import DEFAULT_GLOBAL_LIMITS
from sec_agent.multi_agent_router import ROUTER_SOURCE, route_multi_agent_activation


FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "multi_agent_activation_cases_v0_1.jsonl"


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
