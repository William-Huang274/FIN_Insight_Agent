from __future__ import annotations

import json
from pathlib import Path

from sec_agent.agent_contracts import validate_agent_activation_plan
from sec_agent.agent_registry import (
    SCHEMA_VERSION,
    agent_registry_by_id,
    allowed_source_families,
    export_agent_registry,
    get_agent_contract,
    known_agent_ids,
    list_agent_registry,
    validate_agent_registry,
)
from sec_agent.mcp_contracts import list_mcp_tool_contracts


EXPECTED_AGENT_IDS = {
    "research_lead",
    "universe_relationship",
    "sec_operator",
    "eight_k_operator",
    "market_operator",
    "industry_operator",
    "coverage_reflection",
    "fundamental_analyst",
    "industry_supply_chain_analyst",
    "market_valuation_analyst",
    "risk_counterevidence_analyst",
    "judgment_plan_aggregator",
    "memo_writer",
    "verifier",
    "renderer",
}


def test_agent_registry_is_valid_and_covers_step2_agents() -> None:
    registry = list_agent_registry()
    result = validate_agent_registry(registry)

    assert result["status"] == "pass"
    assert result["schema_version"] == SCHEMA_VERSION
    assert {entry["agent_id"] for entry in registry} == EXPECTED_AGENT_IDS
    assert known_agent_ids() == EXPECTED_AGENT_IDS
    assert {"primary_sec_filing", "market_snapshot", "industry_snapshot", "run_artifact"} <= allowed_source_families()


def test_registry_tools_exist_or_are_future_marked() -> None:
    mcp_tool_names = {contract["name"] for contract in list_mcp_tool_contracts()}

    for entry in list_agent_registry():
        for tool_name in entry["allowed_tools"]:
            assert tool_name in mcp_tool_names
        for future_tool in entry["future_tools"]:
            assert future_tool["status"] in {"future", "disabled"}
            assert future_tool["name"]


def test_permission_matrix_hard_rules_match_step2() -> None:
    registry = agent_registry_by_id()

    assert registry["memo_writer"]["allowed_tools"] == []
    assert registry["renderer"]["allowed_tools"] == []
    assert registry["verifier"]["tool_permission"] == "inspect_only"
    assert registry["research_lead"]["tool_permission"] == "request_only"
    assert registry["sec_operator"]["allowed_tools"] == [
        "sec_search_filings",
        "sec_milvus_semantic_search",
        "sec_query_exact_value_ledger",
    ]
    assert registry["eight_k_operator"]["allowed_tools"] == ["sec_search_filings"]
    assert registry["market_operator"]["allowed_tools"] == ["market_get_snapshot"]
    assert registry["industry_operator"]["allowed_tools"] == ["industry_get_snapshot"]
    assert all("raw_source_read" not in entry["allowed_data_views"] for entry in registry.values())
    assert {agent_id for agent_id, entry in registry.items() if entry["route_authority"] == "execute_route"} == {
        "sec_operator",
        "eight_k_operator",
        "market_operator",
        "industry_operator",
    }


def test_registry_export_json_has_no_private_paths_or_secret_markers(tmp_path: Path) -> None:
    output = tmp_path / "agent_registry.json"
    payload = export_agent_registry(output)

    assert output.exists()
    persisted = json.loads(output.read_text(encoding="utf-8"))
    assert persisted["schema_version"] == payload["schema_version"]
    assert len(persisted["agents"]) == len(payload["agents"])
    text = output.read_text(encoding="utf-8")
    for marker in ("data/raw_private", "data/processed_private", "data/indexes", ".env", "BEGIN PRIVATE KEY", "sk-"):
        assert marker not in text


def test_activation_plan_validator_accepts_static_registry_context() -> None:
    registry = agent_registry_by_id()
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
        "skip_agents": [
            {"agent": "market_operator", "reason": "No market or valuation claim requested."},
        ],
        "allowed_source_families": ["primary_sec_filing", "industry_snapshot", "relationship_graph"],
        "model_policy_hint": {"research_lead": "balanced", "memo_writer": "strong", "renderer": "none"},
        "max_tool_calls_total": 10,
        "max_second_pass_rounds": 2,
        "max_repair_rounds": 1,
        "scope_mode": "full_universe",
        "relationship_scope_rationale": "The user asked for supply-chain readthrough, so relationship expansion is required.",
    }

    result = validate_agent_activation_plan(
        payload,
        agent_registry=registry,
        allowed_source_families=allowed_source_families(),
    )

    assert result["status"] == "pass"


def test_registry_validator_fails_on_permission_violations() -> None:
    registry = list_agent_registry()
    bad = dict(get_agent_contract("memo_writer"))
    bad["agent_id"] = "bad_memo_writer"
    bad["tool_permission"] = "none"
    bad["allowed_tools"] = ["sec_search_filings"]
    bad["allowed_data_views"] = ["raw_source_read"]
    bad["route_authority"] = "execute_route"

    result = validate_agent_registry([*registry, bad])
    error_types = {error["type"] for error in result["errors"]}

    assert result["status"] == "fail"
    assert "none_permission_agent_has_tools" in error_types
    assert "raw_source_read_forbidden" in error_types
    assert "execute_route_reserved_for_operator" in error_types


def test_registry_validator_fails_on_unknown_skill_ids() -> None:
    registry = list_agent_registry()
    bad = dict(get_agent_contract("fundamental_analyst"))
    bad["agent_id"] = "bad_skill_agent"
    bad["skill_ids"] = ["shared_evidence_boundary", "not_a_registered_skill"]

    result = validate_agent_registry([*registry, bad])
    error_types = {error["type"] for error in result["errors"]}

    assert result["status"] == "fail"
    assert "unknown_skill_id" in error_types
