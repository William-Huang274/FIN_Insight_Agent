from __future__ import annotations

import json
from typing import Any

from sec_agent.langgraph_orchestrator import build_multi_agent_orchestration_graph, make_multi_agent_smoke_state
from sec_agent.universe_relationship_llm import (
    ROUTE_SOURCE,
    UNIVERSE_ROUTER_ENV,
    UniverseRelationshipLLMConfig,
    _compact_relationship_lookup,
    extract_universe_relationship_plan_json,
    route_universe_relationship_from_env,
    route_universe_relationship_llm,
)


def test_universe_relationship_llm_accepts_valid_plan_json() -> None:
    fake = _FakeChat([json.dumps(_plan())])

    result = route_universe_relationship_llm(
        _request(),
        config=_config(),
        call_chat_completion=fake,
    )

    assert result["source"] == ROUTE_SOURCE
    assert result["status"] == "pass"
    assert result["universe_relationship_plan"]["relationships"][0]["related_ticker"] == "MSFT"
    assert result["universe_relationship_plan"]["included_ticker_contracts"][0]["included_ticker"] == "NVDA"
    assert "Relationship Universe Skill" in fake.calls[0]["messages"][0]["content"]
    assert "included_ticker_contracts" in fake.calls[0]["messages"][0]["content"]
    assert "downstream_operator_owner" in fake.calls[0]["messages"][0]["content"]
    assert "Do not call tools" in fake.calls[0]["messages"][0]["content"]


def test_universe_relationship_llm_repairs_invalid_json_then_passes() -> None:
    fake = _FakeChat(["not-json", json.dumps(_plan())])

    result = route_universe_relationship_llm(
        _request(),
        config=_config(max_repair_attempts=1),
        call_chat_completion=fake,
    )

    assert result["status"] == "pass"
    assert result["routing_trace"]["repair_attempts"] == 1
    assert len(fake.calls) == 2
    assert "Repair the previous output" in fake.calls[1]["messages"][1]["content"]


def test_universe_relationship_llm_can_require_economic_link_map() -> None:
    fake = _FakeChat([json.dumps(_plan_with_economic_link_map())])

    result = route_universe_relationship_llm(
        _request(),
        config=UniverseRelationshipLLMConfig(
            llm_backend="unit",
            base_url="http://unit.test",
            chat_completions_path="/chat/completions",
            model="unit-model",
            api_key_env="UNIT_API_KEY",
            max_repair_attempts=0,
            require_economic_link_map=True,
        ),
        call_chat_completion=fake,
    )

    assert result["status"] == "pass"
    assert result["universe_relationship_plan"]["economic_link_map"]["links"][0]["link_type"] == "demand_driver"
    assert "economic_link_map" in fake.calls[0]["messages"][0]["content"]


def test_universe_relationship_llm_completes_all_lookup_relationships_when_model_drops_them() -> None:
    empty_plan = _plan()
    empty_plan["relationships"] = []
    fake = _FakeChat([json.dumps(empty_plan)])

    result = route_universe_relationship_llm(
        _request(),
        config=_config(max_repair_attempts=0),
        call_chat_completion=fake,
    )

    assert result["status"] == "pass"
    assert result["universe_relationship_validation"]["status"] == "pass"
    assert result["universe_relationship_plan"]["relationships"][0]["evidence_refs"] == ["rel_nvda_msft"]
    assert result["universe_relationship_plan"]["metadata"]["deterministic_completed_relationship_count"] == 1


def test_universe_relationship_llm_completes_omitted_lookup_edges() -> None:
    request = _request()
    request["source_inventory"] = {"available_tickers": ["NVDA", "MSFT", "AMZN"]}
    request["relationship_lookup"]["relationships"].append(
        {
            "ticker": "NVDA",
            "related_ticker": "AMZN",
            "relationship_type": "sector",
            "direction": "cloud_capex_readthrough",
            "metrics_to_check": ["capex"],
            "evidence_source_needed": ["primary_sec_filing"],
            "evidence_refs": ["rel_nvda_amzn"],
            "inclusion_rationale": "AMZN is included by bounded relationship evidence.",
            "claim_scope": "scope_or_hypothesis_only",
        }
    )
    fake = _FakeChat([json.dumps(_plan())])

    result = route_universe_relationship_llm(
        request,
        config=_config(max_repair_attempts=0),
        call_chat_completion=fake,
    )

    plan = result["universe_relationship_plan"]
    refs = {ref for row in plan["relationships"] for ref in row["evidence_refs"]}
    assert result["status"] == "pass"
    assert refs == {"rel_nvda_msft", "rel_nvda_amzn"}
    assert plan["metadata"]["deterministic_completed_relationship_count"] == 1


def test_universe_relationship_env_router_returns_none_for_mock() -> None:
    assert route_universe_relationship_from_env({UNIVERSE_ROUTER_ENV: "mock"}) is None


def test_universe_relationship_env_router_runs_from_graph_state() -> None:
    fake = _FakeChat([json.dumps(_plan())])
    router = route_universe_relationship_from_env(
        {
            UNIVERSE_ROUTER_ENV: "llm",
            "LLM_BACKEND": "unit",
            "BASE_URL": "http://unit.test",
            "MODEL_NAME": "unit-model",
            "API_KEY_ENV": "UNIT_API_KEY",
        },
        call_chat_completion=fake,
    )

    assert router is not None
    result = router(
        {
            "user_query": "AI capex readthrough",
            "agent_activation_plan": {
                "scope_mode": "full_universe",
                "focus_tickers": ["NVDA"],
                "relationship_scope_rationale": "Supply-chain readthrough.",
            },
            "relationship_graph_observation": _lookup(),
            "project_inventory": {"available_tickers": ["NVDA", "MSFT"]},
        }
    )

    assert result["status"] == "pass"
    assert result["universe_relationship_validation"]["status"] == "pass"


def test_universe_relationship_lookup_compaction_prioritizes_requested_scope_tickers() -> None:
    lookup = {
        "status": "ok",
        "focus_tickers": ["NVDA", "DELL"],
        "relationships": [
            _relationship("NVDA", "DELL", "rel_nvda_dell"),
            _relationship("NVDA", "HPE", "rel_nvda_hpe"),
            _relationship("NVDA", "SMCI", "rel_nvda_smci"),
            _relationship("NVDA", "ANET", "rel_nvda_anet"),
            _relationship("NVDA", "MRVL", "rel_nvda_mrvl"),
            _relationship("NVDA", "VRT", "rel_nvda_vrt"),
        ],
        "summary": {"claim_scope": "scope_or_hypothesis_only"},
    }

    compact = _compact_relationship_lookup(
        lookup,
        source_inventory={"available_tickers": ["NVDA", "DELL", "HPE", "SMCI", "ANET", "MRVL", "VRT"]},
        max_relationships=3,
        priority_tickers=["NVDA", "DELL", "ANET", "VRT"],
    )

    refs = [ref for row in compact["relationships"] for ref in row["evidence_refs"]]
    assert refs == ["rel_nvda_dell", "rel_nvda_anet", "rel_nvda_vrt"]
    assert compact["included_tickers"] == ["NVDA", "DELL", "ANET", "VRT"]


def test_graph_deep_research_runs_universe_relationship_node(tmp_path) -> None:
    graph = build_multi_agent_orchestration_graph()
    result = graph.invoke(
        make_multi_agent_smoke_state(
            user_query="分析 NVDA AI cloud capex 产业链传导。",
            output_dir=tmp_path,
            query_contract={
                "task_type": "open_analysis",
                "search_scope_tickers": ["NVDA"],
                "focus_tickers": ["NVDA"],
                "years": [2026],
                "filing_types": ["10-Q", "8-K"],
                "source_tiers": ["primary_sec_filing", "company_authored_unaudited_sec_filing"],
                "metric_families": ["capex", "revenue"],
            },
            focus_tickers=["NVDA"],
            search_scope_tickers=["NVDA"],
        ),
        config={"configurable": {"thread_id": "unit-universe-graph"}},
    )

    assert result["agent_activation_plan"]["execution_mode"] == "deep_research"
    assert result["universe_relationship_plan"]["source_family"] == "relationship_graph"
    assert result["universe_relationship_validation"]["status"] == "pass"
    assert result["relationship_graph_observation"]["artifact_refs"][0]["path_boundary"] == "path_not_exposed_in_agent_state"
    assert any(
        req.get("claim_scope") == "relationship_hypothesis_not_financial_fact"
        for req in result["evidence_requirement_plan"]["requirements"]
    )


def test_extract_universe_relationship_plan_json_accepts_fenced_json() -> None:
    payload = _plan()
    assert extract_universe_relationship_plan_json(f"```json\n{json.dumps(payload)}\n```") == payload


class _FakeChat:
    def __init__(self, responses: list[Any]) -> None:
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    def __call__(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        response = self.responses[min(len(self.calls) - 1, len(self.responses) - 1)]
        content = str(response.get("content") if isinstance(response, dict) else response or "")
        tool_calls = response.get("tool_calls") if isinstance(response, dict) else []
        return {
            "status": "ok",
            "provider": kwargs["llm_backend"],
            "model": kwargs["model"],
            "role": kwargs["role"],
            "profile": kwargs["profile"],
            "content": content,
            "message": {"content": content, "tool_calls": tool_calls},
            "tool_calls": tool_calls or [],
            "finish_reason": "stop",
            "latency_ms": 1,
            "input_tokens": 10,
            "output_tokens": 20,
            "total_tokens": 30,
            "failure_reason": "",
            "raw_response": {},
        }


def _config(max_repair_attempts: int = 2) -> UniverseRelationshipLLMConfig:
    return UniverseRelationshipLLMConfig(
        llm_backend="unit",
        base_url="http://unit.test",
        chat_completions_path="/chat/completions",
        model="unit-model",
        api_key_env="UNIT_API_KEY",
        max_repair_attempts=max_repair_attempts,
    )


def _request() -> dict[str, Any]:
    return {
        "user_query": "AI capex readthrough",
        "activation_plan": {
            "scope_mode": "full_universe",
            "focus_tickers": ["NVDA"],
            "relationship_scope_rationale": "Supply-chain readthrough.",
        },
        "relationship_lookup": _lookup(),
        "source_inventory": {"available_tickers": ["NVDA", "MSFT"]},
    }


def _lookup() -> dict[str, Any]:
    return {
        "status": "ok",
        "focus_tickers": ["NVDA"],
        "relationships": [
            {
                "ticker": "NVDA",
                "related_ticker": "MSFT",
                "relationship_type": "customer",
                "direction": "downstream_customer",
                "metrics_to_check": ["cloud_capex"],
                "evidence_source_needed": ["primary_sec_filing", "industry_snapshot"],
                "evidence_refs": ["rel_nvda_msft"],
                "inclusion_rationale": "MSFT is included as a cloud capex readthrough hypothesis.",
                "claim_scope": "scope_or_hypothesis_only",
            }
        ],
        "summary": {"claim_scope": "scope_or_hypothesis_only"},
    }


def _relationship(ticker: str, related_ticker: str, evidence_ref: str) -> dict[str, Any]:
    return {
        "ticker": ticker,
        "related_ticker": related_ticker,
        "relationship_type": "sector",
        "direction": "sector_depth_peer",
        "metrics_to_check": ["revenue"],
        "evidence_source_needed": ["relationship_graph"],
        "evidence_refs": [evidence_ref],
        "inclusion_rationale": f"{related_ticker} is included by bounded relationship evidence.",
        "claim_scope": "scope_or_hypothesis_only",
    }


def _plan() -> dict[str, Any]:
    return {
        "scope_mode": "full_universe",
        "focus_tickers": ["NVDA"],
        "expanded_tickers": ["NVDA", "MSFT"],
        "included_tickers": ["NVDA", "MSFT"],
        "relationship_scope_rationale": "Supply-chain readthrough.",
        "relationships": [
            {
                "ticker": "NVDA",
                "related_ticker": "MSFT",
                "relationship_type": "customer",
                "direction": "downstream_customer",
                "metrics_to_check": ["cloud_capex"],
                "evidence_source_needed": ["primary_sec_filing", "industry_snapshot"],
                "evidence_refs": ["rel_nvda_msft"],
                "inclusion_rationale": "MSFT is included as a cloud capex readthrough hypothesis.",
                "claim_scope": "scope_or_hypothesis_only",
            }
        ],
        "source_family": "relationship_graph",
    }


def _plan_with_economic_link_map() -> dict[str, Any]:
    plan = _plan()
    plan["economic_link_map"] = {
        "schema_version": "sec_agent_economic_link_map_v0.1",
        "map_scope": "relationship_hypothesis",
        "focus_tickers": ["NVDA"],
        "entities": [
            {
                "ticker": "NVDA",
                "role": "direct AI compute beneficiary",
                "evidence_refs": ["rel_nvda_msft"],
                "confidence": "medium",
                "materiality": "high",
                "missing_confirmations": ["No customer-level order data in relationship graph."],
            },
            {
                "ticker": "MSFT",
                "role": "cloud capex demand proxy",
                "evidence_refs": ["rel_nvda_msft"],
                "confidence": "medium",
                "materiality": "medium",
                "missing_confirmations": ["No confirmed direct purchase edge."],
            },
        ],
        "links": [
            {
                "source": "MSFT",
                "target": "NVDA",
                "link_type": "demand_driver",
                "mechanism": "Cloud capex can support AI accelerator demand, but the relationship row is hypothesis-only.",
                "direction": "positive",
                "materiality": "high",
                "confidence": "medium",
                "metric_implications": ["cloud_capex", "data_center_revenue"],
                "evidence_refs": ["rel_nvda_msft"],
                "claim_scope": "economic_mechanism_hypothesis_only",
                "missing_confirmations": ["No direct supplier/customer filing confirmation."],
            }
        ],
        "mechanisms": [
            {
                "driver": "cloud capex",
                "affected_entities": ["NVDA", "MSFT"],
                "metric_implications": ["cloud_capex", "data_center_revenue"],
                "confirming_indicators": ["capex growth", "data center revenue"],
                "disconfirming_indicators": ["capex slowdown"],
                "evidence_refs": ["rel_nvda_msft"],
                "confidence": "medium",
            }
        ],
        "investment_implications": [
            {
                "claim": "NVDA/MSFT belongs in the AI capex transmission research scope.",
                "so_what": "Specialists should verify capex and data center revenue before any stronger memo claim.",
                "entity_scope": ["NVDA", "MSFT"],
                "confidence": "medium",
                "supporting_refs": ["rel_nvda_msft"],
                "missing_confirmations": ["No direct edge confirmation."],
            }
        ],
        "source_boundary": "relationship_graph_hypothesis_only",
    }
    return plan
