from __future__ import annotations

import pytest

from sec_agent.agent_contracts import (
    AgentActivationPlan,
    SCHEMA_VERSION,
    assert_valid_agent_activation_plan,
    validate_agent_activation_plan,
)


def _focused_plan() -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "execution_mode": "focused_answer",
        "activate_agents": [
            "research_lead",
            "sec_operator",
            "coverage_reflection",
            "memo_writer",
            "verifier",
            "renderer",
        ],
        "skip_agents": [
            {"agent": "universe_relationship", "reason": "User requested a focused company scope."},
            {"agent": "market_operator", "reason": "No market or valuation claim requested."},
        ],
        "allowed_source_families": ["primary_sec_filing", "company_authored_unaudited_sec_filing"],
        "model_policy_hint": {
            "research_lead": "balanced",
            "memo_writer": "strong",
            "verifier": "strong",
        },
        "agent_priorities": {
            "research_lead": "primary",
            "sec_operator": "primary",
            "memo_writer": "primary",
            "verifier": "supporting",
            "renderer": "primary",
        },
        "max_tool_calls_total": 6,
        "max_second_pass_rounds": 1,
        "max_repair_rounds": 1,
        "scope_mode": "focused_peer",
        "focus_tickers": ["MSFT"],
        "search_scope_tickers": ["MSFT"],
        "reasoning_summary": "Single-company focused answer.",
    }


def test_focused_activation_plan_passes_and_normalizes() -> None:
    result = validate_agent_activation_plan(_focused_plan())

    assert result["status"] == "pass"
    assert result["errors"] == []
    assert result["plan"]["schema_version"] == SCHEMA_VERSION
    assert result["plan"]["skip_agents"][0]["agent_id"] == "universe_relationship"
    assert result["plan"]["focus_tickers"] == ["MSFT"]
    assert result["plan"]["agent_priorities"]["verifier"] == "supporting"


def test_assert_valid_returns_dataclass() -> None:
    plan = assert_valid_agent_activation_plan(_focused_plan())

    assert isinstance(plan, AgentActivationPlan)
    assert plan.execution_mode == "focused_answer"
    assert plan.activate_agents[-1] == "renderer"


def test_unknown_agent_and_source_family_fail() -> None:
    payload = _focused_plan()
    payload["activate_agents"] = [*payload["activate_agents"], "portfolio_manager"]
    payload["allowed_source_families"] = ["primary_sec_filing", "external_news"]

    result = validate_agent_activation_plan(payload)
    error_types = {error["type"] for error in result["errors"]}

    assert result["status"] == "fail"
    assert "unknown_agent" in error_types
    assert "unknown_source_family" in error_types


def test_invalid_mode_model_profile_and_budget_fail() -> None:
    payload = _focused_plan()
    payload["execution_mode"] = "chat_followup"
    payload["model_policy_hint"] = {"research_lead": "deepseek-pro"}
    payload["max_tool_calls_total"] = 99

    result = validate_agent_activation_plan(payload)
    error_types = {error["type"] for error in result["errors"]}

    assert "invalid_execution_mode" in error_types
    assert "invalid_model_profile" in error_types
    assert "budget_exceeds_global_limit" in error_types


def test_invalid_agent_priority_fails_closed() -> None:
    payload = _focused_plan()
    payload["agent_priorities"] = {"memo_writer": "urgent", "universe_relationship": "primary"}

    result = validate_agent_activation_plan(payload)
    error_types = {error["type"] for error in result["errors"]}

    assert result["status"] == "fail"
    assert "invalid_agent_priority" in error_types
    assert "agent_priority_for_inactive_agent" in error_types


def test_skip_agent_reason_is_required() -> None:
    payload = _focused_plan()
    payload["skip_agents"] = [{"agent": "universe_relationship", "reason": ""}]

    result = validate_agent_activation_plan(payload)

    assert result["status"] == "fail"
    assert result["errors"][0]["type"] == "skip_agent_reason_required"


def test_required_agent_missing_fails() -> None:
    payload = _focused_plan()
    payload["activate_agents"] = ["research_lead", "sec_operator", "renderer"]

    result = validate_agent_activation_plan(payload)

    assert result["status"] == "fail"
    assert "coverage_reflection" in result["errors"][0]["agent_ids"]
    assert "memo_writer" in result["errors"][0]["agent_ids"]
    assert "verifier" in result["errors"][0]["agent_ids"]


def test_deterministic_lookup_rejects_deep_agents_and_memo_writer() -> None:
    payload = {
        "execution_mode": "deterministic_lookup",
        "activate_agents": ["research_lead", "universe_relationship", "memo_writer", "renderer"],
        "skip_agents": [],
        "allowed_source_families": ["run_artifact"],
        "model_policy_hint": {"renderer": "none"},
        "max_tool_calls_total": 1,
        "max_second_pass_rounds": 0,
        "max_repair_rounds": 0,
    }

    result = validate_agent_activation_plan(payload)

    assert result["status"] == "fail"
    assert result["errors"][0]["type"] == "agent_not_allowed_for_execution_mode"
    assert set(result["errors"][0]["agent_ids"]) == {"memo_writer", "universe_relationship"}


def test_focused_scope_expansion_requires_rationale() -> None:
    payload = _focused_plan()
    payload["scope_mode"] = "full_universe"
    payload["search_scope_tickers"] = ["NVDA", "AMD", "MSFT", "AMZN", "GOOGL", "META"]

    result = validate_agent_activation_plan(payload)

    assert result["status"] == "fail"
    assert any(error["type"] == "focused_scope_expansion_without_rationale" for error in result["errors"])


def test_deep_research_requires_relationship_rationale() -> None:
    payload = {
        "execution_mode": "deep_research",
        "activate_agents": [
            "research_lead",
            "universe_relationship",
            "sec_operator",
            "industry_operator",
            "coverage_reflection",
            "memo_writer",
            "verifier",
            "renderer",
        ],
        "skip_agents": [],
        "allowed_source_families": ["primary_sec_filing", "industry_snapshot"],
        "model_policy_hint": {"research_lead": "balanced", "memo_writer": "strong"},
        "max_tool_calls_total": 10,
        "max_second_pass_rounds": 2,
        "max_repair_rounds": 1,
        "scope_mode": "full_universe",
    }

    result = validate_agent_activation_plan(payload)

    assert result["status"] == "fail"
    assert any(error["type"] == "relationship_scope_rationale_required" for error in result["errors"])


def test_industry_supply_chain_agent_requires_industry_or_relationship_scope() -> None:
    payload = {
        "execution_mode": "standard_memo",
        "activate_agents": [
            "research_lead",
            "sec_operator",
            "eight_k_operator",
            "market_operator",
            "coverage_reflection",
            "fundamental_analyst",
            "industry_supply_chain_analyst",
            "market_valuation_analyst",
            "risk_counterevidence_analyst",
            "judgment_plan_aggregator",
            "memo_writer",
            "verifier",
            "renderer",
        ],
        "skip_agents": [{"agent": "universe_relationship", "reason": "No relationship expansion requested."}],
        "allowed_source_families": ["primary_sec_filing", "company_authored_unaudited_sec_filing", "market_snapshot"],
        "model_policy_hint": {"research_lead": "balanced", "memo_writer": "strong", "verifier": "strong"},
        "max_tool_calls_total": 10,
        "max_second_pass_rounds": 1,
        "max_repair_rounds": 1,
    }

    result = validate_agent_activation_plan(payload)

    assert result["status"] == "fail"
    assert any(
        error["type"] == "industry_supply_chain_agent_requires_industry_or_relationship_scope"
        for error in result["errors"]
    )


def test_agent_registry_permission_checks_fail_closed() -> None:
    payload = _focused_plan()
    registry = {
        "research_lead": {"tool_permission": "request_only", "allowed_tools": ["sec_search_filings"]},
        "sec_operator": {"tool_permission": "bounded_execute", "allowed_tools": ["market_get_snapshot"]},
        "coverage_reflection": {"tool_permission": "orchestrate_subgraph", "allowed_tools": []},
        "memo_writer": {"tool_permission": "none", "allowed_tools": ["run_read_artifact"]},
        "verifier": {"tool_permission": "bounded_execute", "allowed_tools": ["sec_query_exact_value_ledger"]},
        "renderer": {"tool_permission": "none", "allowed_tools": []},
    }

    result = validate_agent_activation_plan(payload, agent_registry=registry)
    error_types = {error["type"] for error in result["errors"]}

    assert result["status"] == "fail"
    assert "research_lead_retrieval_tools_forbidden" in error_types
    assert "operator_tool_not_allowed" in error_types
    assert "agent_must_not_have_tools" in error_types
    assert "verifier_must_be_inspect_only" in error_types
    assert "verifier_retrieval_tools_forbidden" in error_types


def test_assert_valid_raises_on_invalid_plan() -> None:
    payload = _focused_plan()
    payload["allowed_source_families"] = []

    with pytest.raises(ValueError, match="allowed_source_families_required"):
        assert_valid_agent_activation_plan(payload)
