from __future__ import annotations

import json
from typing import Any

from sec_agent.specialist_llm import (
    ROUTE_SOURCE,
    SPECIALIST_ROUTER_ENV,
    SpecialistLLMConfig,
    build_specialist_request_from_state,
    extract_specialist_memolet_json,
    route_specialist_memolet_llm,
    route_specialists_from_env,
)


def test_specialist_llm_accepts_valid_memolet_json() -> None:
    fake = _FakeChat([json.dumps(_memolet("fundamental_analyst"))])

    result = route_specialist_memolet_llm(
        "fundamental_analyst",
        _request(),
        config=_config(),
        call_chat_completion=fake,
    )

    assert result["source"] == ROUTE_SOURCE
    assert result["status"] == "pass"
    assert result["memolet"]["agent_id"] == "fundamental_analyst"
    assert result["validation"]["status"] == "pass"
    assert fake.calls[0]["response_format"] == {"type": "json_object"}
    assert "tools" not in fake.calls[0]
    assert "Do not call tools" in fake.calls[0]["messages"][0]["content"]
    assert "Fundamental Analysis Skill" in fake.calls[0]["messages"][0]["content"]
    assert "Shared Evidence Boundary Skill" in fake.calls[0]["messages"][0]["content"]


def test_specialist_llm_parses_fenced_json() -> None:
    memolet = _memolet("market_valuation_analyst", source_family="market_snapshot")
    fake = _FakeChat([f"```json\n{json.dumps(memolet)}\n```"])

    result = route_specialist_memolet_llm(
        "market_valuation_analyst",
        _request(source_family="market_snapshot"),
        config=_config(),
        call_chat_completion=fake,
    )

    assert extract_specialist_memolet_json(f"```json\n{json.dumps(memolet)}\n```") == memolet
    assert result["status"] == "pass"
    assert result["memolet"]["observations"][0]["source_families"] == ["market_snapshot"]
    assert "Market Valuation Analysis Skill" in fake.calls[0]["messages"][0]["content"]


def test_specialist_llm_supports_industry_supply_chain_skill() -> None:
    memolet = _memolet("industry_supply_chain_analyst", source_family="industry_snapshot")
    fake = _FakeChat([json.dumps(memolet)])

    result = route_specialist_memolet_llm(
        "industry_supply_chain_analyst",
        _request(source_family="industry_snapshot"),
        config=_config(),
        call_chat_completion=fake,
    )

    assert result["status"] == "pass"
    assert result["memolet"]["agent_id"] == "industry_supply_chain_analyst"
    assert "Industry Supply Chain Analysis Skill" in fake.calls[0]["messages"][0]["content"]
    assert "Skill v0.2" in fake.calls[0]["messages"][0]["content"]


def test_specialist_llm_passes_relationship_summary_as_bounded_prompt_input() -> None:
    memolet = _memolet("industry_supply_chain_analyst", source_family="relationship_graph", evidence_ref="rel_ref_1")
    fake = _FakeChat([json.dumps(memolet)])
    request = _request(source_family="industry_snapshot")
    request["relationship_summary"] = {
        "scope_mode": "expanded",
        "relationships": [
            {
                "evidence_ref": "rel_ref_1",
                "source_family": "relationship_graph",
                "ticker": "NVDA",
                "related_ticker": "MSFT",
                "summary": "MSFT is bounded relationship hypothesis context for NVDA demand.",
            }
        ],
    }

    result = route_specialist_memolet_llm(
        "industry_supply_chain_analyst",
        request,
        config=_config(),
        call_chat_completion=fake,
    )

    user_prompt = fake.calls[0]["messages"][1]["content"]
    assert result["status"] == "pass"
    assert "relationship_summary" in user_prompt
    assert "rel_ref_1" in user_prompt


def test_specialist_llm_prompt_uses_deep_research_observation_budget() -> None:
    fake = _FakeChat([json.dumps(_memolet("fundamental_analyst"))])
    request = _request()
    request["execution_mode"] = "deep_research"
    request["input_budget"] = {
        "prompt_bounded_evidence_row_budget": 24,
        "data_view_bounded_evidence_row_budget": 32,
    }

    result = route_specialist_memolet_llm(
        "fundamental_analyst",
        request,
        config=_config(),
        call_chat_completion=fake,
    )

    user_prompt = fake.calls[0]["messages"][1]["content"]
    assert result["status"] == "pass"
    assert "2-4 supported fundamental ClaimCards" in user_prompt
    assert "ClaimCard v0.3" in user_prompt
    assert '"execution_mode": "deep_research"' in user_prompt
    assert "input_budget" in user_prompt
    assert "output_contract" in user_prompt


def test_specialist_llm_repairs_truncated_json_with_compact_prompt() -> None:
    fake = _FakeChat(
        [
            {"content": '{"schema_version": "sec_agent_specialist_memolet_v0.1", "observations": [', "finish_reason": "length", "output_tokens": 3000},
            json.dumps(_memolet("fundamental_analyst")),
        ]
    )

    result = route_specialist_memolet_llm(
        "fundamental_analyst",
        _request(),
        config=_config(),
        call_chat_completion=fake,
    )

    repair_prompt = fake.calls[1]["messages"][1]["content"]
    assert result["status"] == "pass"
    assert result["routing_trace"]["repair_attempts"] == 1
    assert result["model_diagnostics"]["finish_reasons"] == ["length", "stop"]
    assert "Use this compact input JSON only" in repair_prompt
    assert "at most 2 observations" in repair_prompt


def test_specialist_llm_repairs_invalid_json_then_passes() -> None:
    fake = _FakeChat(["not json", json.dumps(_memolet("risk_counterevidence_analyst"))])

    result = route_specialist_memolet_llm(
        "risk_counterevidence_analyst",
        _request(),
        config=_config(),
        call_chat_completion=fake,
    )

    assert result["status"] == "pass"
    assert result["routing_trace"]["repair_attempts"] == 1
    assert len(fake.calls) == 2
    assert "Repair the previous SpecialistMemolet response" in fake.calls[1]["messages"][1]["content"]


def test_specialist_llm_retries_provider_error_then_passes() -> None:
    fake = _FakeChat(
        [
            {
                "status": "provider_error",
                "failure_reason": "URLError: transient provider failure",
            },
            json.dumps(_memolet("industry_supply_chain_analyst", source_family="industry_snapshot")),
        ]
    )

    result = route_specialist_memolet_llm(
        "industry_supply_chain_analyst",
        _request(source_family="industry_snapshot"),
        config=_config(),
        call_chat_completion=fake,
    )

    assert result["status"] == "pass"
    assert result["routing_trace"]["attempt_count"] == 2
    assert result["routing_trace"]["repair_attempts"] == 1
    assert result["model_diagnostics"]["calls"][0]["status"] == "provider_error"
    assert "Repair the previous output" in fake.calls[1]["messages"][1]["content"]


def test_specialist_llm_fails_closed_after_repair_budget() -> None:
    invalid = _memolet("fundamental_analyst")
    invalid["observations"][0]["evidence_refs"] = []
    fake = _FakeChat([json.dumps(invalid), json.dumps(invalid)])

    result = route_specialist_memolet_llm(
        "fundamental_analyst",
        _request(),
        config=SpecialistLLMConfig(
            llm_backend="unit",
            base_url="http://unit.test",
            chat_completions_path="/chat/completions",
            model="unit-model",
            api_key_env="UNIT_API_KEY",
            max_repair_attempts=1,
        ),
        call_chat_completion=fake,
    )

    assert result["status"] == "fail"
    assert result["memolet"] == {}
    assert result["rejected_memolet"]["observations"][0]["evidence_refs"] == []
    assert result["routing_trace"]["repair_attempts"] == 1
    assert "validation_failed" in result["failure_reason"]


def test_specialist_llm_salvages_single_no_ref_observation_when_supported_claims_remain() -> None:
    memolet = _memolet("risk_counterevidence_analyst")
    memolet["observations"].append(
        {
            "claim": "Risk observation missing refs should not enter supported plan.",
            "claim_type": "business_observation",
            "evidence_refs": [],
            "source_families": ["primary_sec_filing"],
            "confidence": "low",
            "unsupported": False,
        }
    )
    fake = _FakeChat([json.dumps(memolet)])

    result = route_specialist_memolet_llm(
        "risk_counterevidence_analyst",
        _request(),
        config=_config(),
        call_chat_completion=fake,
    )

    assert result["status"] == "pass"
    assert result["routing_trace"]["salvage_policy"] == "drop_supported_observations_with_missing_or_unknown_evidence_refs"
    assert len(result["memolet"]["observations"]) == 1
    assert result["memolet"]["unsupported_claims"][0]["reason"] == "dropped_from_supported_observations_missing_or_unknown_evidence_refs"
    assert result["validation"]["warnings"][-1]["type"] == "supported_observation_dropped_missing_or_unknown_evidence_refs"


def test_specialist_llm_rejects_direct_tool_calls_before_validation() -> None:
    fake = _FakeChat(
        [
            {
                "content": "",
                "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "sec_search_filings"}}],
            },
            json.dumps(_memolet("fundamental_analyst")),
        ]
    )

    result = route_specialist_memolet_llm(
        "fundamental_analyst",
        _request(),
        config=_config(),
        call_chat_completion=fake,
    )

    assert result["status"] == "pass"
    assert result["routing_trace"]["repair_attempts"] == 1


def test_specialist_llm_fails_unknown_agent_without_model_call() -> None:
    fake = _FakeChat([json.dumps(_memolet("fundamental_analyst"))])

    result = route_specialist_memolet_llm(
        "memo_writer",
        _request(),
        config=_config(),
        call_chat_completion=fake,
    )

    assert result["status"] == "fail"
    assert result["validation"]["errors"][0]["type"] == "invalid_specialist_agent"
    assert fake.calls == []


def test_specialist_env_router_returns_none_for_mock_mode() -> None:
    assert route_specialists_from_env({SPECIALIST_ROUTER_ENV: "mock"}) is None


def test_specialist_env_router_runs_active_specialists_with_bounded_state() -> None:
    fake = _FakeChat(
        [
            json.dumps(_memolet("fundamental_analyst", source_family="primary_sec_filing", evidence_ref="ledger_ref_1")),
            json.dumps(_memolet("market_valuation_analyst", source_family="market_snapshot", evidence_ref="market_ref_1")),
        ]
    )
    router = route_specialists_from_env(
        {
            SPECIALIST_ROUTER_ENV: "llm",
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
            "user_query": "Compare bounded evidence.",
            "agent_activation_plan": {
                "activate_agents": ["fundamental_analyst", "market_valuation_analyst"],
                "allowed_source_families": ["primary_sec_filing", "market_snapshot"],
            },
            "runtime_ledger_rows": [
                {
                    "metric_id": "ledger_ref_1",
                    "source_family": "primary_sec_filing",
                    "ticker": "NVDA",
                    "metric": "revenue",
                    "value": "130.5B",
                    "summary": "NVDA annual revenue row.",
                }
            ],
            "market_snapshot_rows": [
                {
                    "evidence_ref": "market_ref_1",
                    "source_family": "market_snapshot",
                    "ticker": "NVDA",
                    "summary": "NVDA event-window return row.",
                    "snapshot_id": "snap_1",
                    "as_of_date": "2026-05-30",
                }
            ],
        }
    )

    assert [row["agent_id"] for row in result["specialist_outputs"]] == ["fundamental_analyst", "market_valuation_analyst"]
    assert all(row["status"] == "pass" for row in result["specialist_outputs"])
    assert len(result["specialist_route_results"]) == 2
    assert "raw_response" not in json.dumps(result)


def test_specialist_env_router_skips_conditional_specialist_without_signal() -> None:
    fake = _FakeChat(
        [
            json.dumps(_memolet("fundamental_analyst", source_family="primary_sec_filing", evidence_ref="ledger_ref_1")),
        ]
    )
    router = route_specialists_from_env(
        {
            SPECIALIST_ROUTER_ENV: "llm",
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
            "user_query": "Analyze bounded fundamentals.",
            "agent_activation_plan": {
                "activate_agents": ["fundamental_analyst", "market_valuation_analyst"],
                "agent_priorities": {
                    "fundamental_analyst": "primary",
                    "market_valuation_analyst": "conditional",
                },
                "allowed_source_families": ["primary_sec_filing"],
            },
            "runtime_ledger_rows": [
                {
                    "metric_id": "ledger_ref_1",
                    "source_family": "primary_sec_filing",
                    "ticker": "NVDA",
                    "metric": "revenue",
                    "summary": "NVDA annual revenue row.",
                }
            ],
        }
    )

    assert [row["agent_id"] for row in result["specialist_outputs"]] == ["fundamental_analyst"]
    assert len(fake.calls) == 1
    skipped = [row for row in result["specialist_route_results"] if row["status"] == "skipped"]
    assert skipped[0]["agent_id"] == "market_valuation_analyst"


def test_build_specialist_request_from_state_sanitizes_rows() -> None:
    request = build_specialist_request_from_state(
        "fundamental_analyst",
        {
            "user_query": "Analyze fundamentals.",
            "runtime_ledger_rows": [
                {
                    "metric_id": "ledger_ref_1",
                    "source_family": "primary_sec_filing",
                    "ticker": "MSFT",
                    "metric": "capex",
                    "value": 123,
                    "summary": "x" * 1200,
                    "private_path": "data/raw_private/not_exposed",
                }
            ],
        },
    )

    assert request["known_evidence_refs"] == ["ledger_ref_1"]
    assert request["bounded_evidence_rows"][0]["evidence_ref"] == "ledger_ref_1"
    assert "private_path" not in request["bounded_evidence_rows"][0]
    assert len(request["bounded_evidence_rows"][0]["summary"]) <= 400


def test_build_specialist_request_from_state_supports_industry_relationship_rows() -> None:
    request = build_specialist_request_from_state(
        "industry_supply_chain_analyst",
        {
            "industry_snapshot_rows": [
                {
                    "evidence_ref": "industry_ref_1",
                    "source_family": "industry_snapshot",
                    "ticker": "NVDA",
                    "summary": "Data center power demand remains a sector constraint.",
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

    assert set(request["known_evidence_refs"]) == {"industry_ref_1", "rel_ref_1"}
    assert {row["source_family"] for row in request["bounded_evidence_rows"]} == {"industry_snapshot", "relationship_graph"}
    assert request["relationship_summary"]["relationships"][0]["evidence_ref"] == "rel_ref_1"


def test_build_specialist_request_from_state_balances_industry_prompt_rows_for_relationship_refs() -> None:
    request = build_specialist_request_from_state(
        "industry_supply_chain_analyst",
        {
            "industry_snapshot_rows": [
                {
                    "evidence_ref": f"industry_ref_{index}",
                    "source_family": "industry_snapshot",
                    "summary": f"Industry context row {index}.",
                }
                for index in range(1, 25)
            ],
            "universe_relationship_plan": {
                "relationships": [
                    {
                        "ticker": "NVDA",
                        "related_ticker": "MSFT",
                        "relationship_type": "customer",
                        "evidence_refs": [f"rel_ref_{index}"],
                        "notes": f"Relationship hypothesis row {index}.",
                    }
                    for index in range(1, 5)
                ]
            },
        },
    )

    relationship_rows = [row for row in request["bounded_evidence_rows"] if row["source_family"] == "relationship_graph"]

    assert relationship_rows
    assert "rel_ref_1" in request["known_evidence_refs"]
    assert request["relationship_summary"]["relationships"]


def test_risk_specialist_request_excludes_relationship_rows() -> None:
    request = build_specialist_request_from_state(
        "risk_counterevidence_analyst",
        {
            "agent_activation_plan": {"execution_mode": "deep_research"},
            "runtime_ledger_rows": [
                {"metric_id": "sec_ref", "source_family": "primary_sec_filing", "summary": "Risk factor evidence."},
            ],
            "universe_relationship_plan": {
                "relationships": [
                    {
                        "ticker": "NVDA",
                        "related_ticker": "MSFT",
                        "relationship_type": "customer",
                        "evidence_refs": ["rel_ref_1"],
                        "notes": "Relationship hypothesis belongs to industry specialist.",
                    }
                ]
            },
        },
    )

    assert "relationship_summary" not in request or not request["relationship_summary"]
    assert {row["source_family"] for row in request["bounded_evidence_rows"]} == {"primary_sec_filing"}
    assert "rel_ref_1" not in request["known_evidence_refs"]


def test_build_specialist_request_from_state_uses_deep_research_prompt_budget() -> None:
    request = build_specialist_request_from_state(
        "fundamental_analyst",
        {
            "user_query": "Deep research fundamentals.",
            "agent_activation_plan": {"execution_mode": "deep_research"},
            "runtime_ledger_rows": [
                {
                    "metric_id": f"ledger_ref_{index}",
                    "source_family": "primary_sec_filing",
                    "ticker": "NVDA",
                    "metric": "revenue",
                    "value": str(index),
                    "summary": f"Revenue evidence row {index}.",
                }
                for index in range(1, 31)
            ],
        },
    )

    assert request["execution_mode"] == "deep_research"
    assert len(request["bounded_evidence_rows"]) == 24
    assert request["input_budget"]["prompt_bounded_evidence_row_budget"] == 24
    assert request["input_budget"]["data_view_bounded_evidence_row_budget"] == 32
    assert request["input_budget"]["prompt_summary_char_policy"] == "source_family_tiered_v0_1"
    assert "ledger_ref_24" in request["known_evidence_refs"]


def test_specialist_prompt_uses_source_family_summary_budgets() -> None:
    request = build_specialist_request_from_state(
        "risk_counterevidence_analyst",
        {
            "agent_activation_plan": {"execution_mode": "deep_research"},
            "runtime_ledger_rows": [
                {"metric_id": "sec_ref", "source_family": "primary_sec_filing", "summary": "s" * 900},
            ],
            "market_snapshot_rows": [
                {"evidence_ref": "market_ref", "source_family": "market_snapshot", "summary": "m" * 900},
            ],
            "industry_snapshot_rows": [
                {"evidence_ref": "industry_ref", "source_family": "industry_snapshot", "summary": "i" * 900},
            ],
            "universe_relationship_plan": {
                "relationships": [
                    {
                        "evidence_refs": ["rel_ref"],
                        "relationship_type": "supplier",
                        "notes": "r" * 900,
                    }
                ]
            },
        },
    )

    by_family = {row["source_family"]: row for row in request["bounded_evidence_rows"]}

    assert len(by_family["primary_sec_filing"]["summary"]) <= 334
    assert len(by_family["market_snapshot"]["summary"]) <= 314
    assert len(by_family["industry_snapshot"]["summary"]) <= 354

    industry_request = build_specialist_request_from_state(
        "industry_supply_chain_analyst",
        {
            "agent_activation_plan": {"execution_mode": "deep_research"},
            "industry_snapshot_rows": [
                {"evidence_ref": "industry_ref", "source_family": "industry_snapshot", "summary": "i" * 900},
            ],
            "universe_relationship_plan": {
                "relationships": [
                    {
                        "evidence_refs": ["rel_ref"],
                        "relationship_type": "supplier",
                        "notes": "r" * 900,
                    }
                ]
            },
        },
    )
    industry_by_family = {row["source_family"]: row for row in industry_request["bounded_evidence_rows"]}
    assert len(industry_by_family["relationship_graph"]["summary"]) <= 434


def test_risk_specialist_prompt_uses_compact_v0_3_output_contract() -> None:
    fake = _FakeChat([json.dumps(_memolet("risk_counterevidence_analyst"))])
    request = _request()
    request["execution_mode"] = "deep_research"

    result = route_specialist_memolet_llm(
        "risk_counterevidence_analyst",
        request,
        config=_config(),
        call_chat_completion=fake,
    )

    user_prompt = fake.calls[0]["messages"][1]["content"]
    assert result["status"] == "pass"
    assert "2-3 supported risk ClaimCards" in user_prompt
    assert "risk_compact_schema_v0_3" in user_prompt
    assert '"unsupported_claim_cap": 2' in user_prompt
    assert '"conflict_cap": 2' in user_prompt


def test_build_specialist_request_includes_output_contract_caps() -> None:
    request = build_specialist_request_from_state(
        "risk_counterevidence_analyst",
        {
            "agent_activation_plan": {"execution_mode": "deep_research"},
            "runtime_ledger_rows": [
                {"metric_id": "sec_ref", "source_family": "primary_sec_filing", "summary": "Risk factor evidence."},
            ],
        },
    )

    assert request["output_contract"]["policy"] == "risk_compact_schema_v0_3"
    assert request["input_budget"]["unsupported_claim_cap"] == 2
    assert request["input_budget"]["conflict_cap"] == 2


class _FakeChat:
    def __init__(self, responses: list[Any]) -> None:
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    def __call__(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        response = self.responses[min(len(self.calls) - 1, len(self.responses) - 1)]
        if isinstance(response, dict):
            status = str(response.get("status") or "ok")
            content = str(response.get("content") or "")
            tool_calls = response.get("tool_calls") or []
            failure_reason = str(response.get("failure_reason") or "")
            finish_reason = str(response.get("finish_reason") or "stop")
            output_tokens = int(response.get("output_tokens") or 20)
        else:
            status = "ok"
            content = str(response)
            tool_calls = []
            failure_reason = ""
            finish_reason = "stop"
            output_tokens = 20
        return {
            "status": status,
            "provider": kwargs["llm_backend"],
            "model": kwargs["model"],
            "role": kwargs["role"],
            "profile": kwargs["profile"],
            "content": content,
            "message": {"content": content, "tool_calls": tool_calls},
            "tool_calls": tool_calls,
            "finish_reason": finish_reason,
            "latency_ms": 1,
            "input_tokens": 10,
            "output_tokens": output_tokens,
            "total_tokens": 10 + output_tokens,
            "cost_estimate": None,
            "failure_reason": failure_reason,
            "trace_tags": kwargs.get("trace_tags") or {},
            "raw_response": {},
        }


def _config() -> SpecialistLLMConfig:
    return SpecialistLLMConfig(
        llm_backend="unit",
        base_url="http://unit.test",
        chat_completions_path="/chat/completions",
        model="unit-model",
        api_key_env="UNIT_API_KEY",
    )


def _request(*, source_family: str = "primary_sec_filing") -> dict[str, Any]:
    return {
        "user_query": "Compare bounded evidence.",
        "known_evidence_refs": ["ref_1"],
        "bounded_evidence_rows": [
            {
                "evidence_ref": "ref_1",
                "source_family": source_family,
                "summary": "Bounded evidence row.",
                "ticker": "NVDA",
                "period_role": "annual",
            }
        ],
    }


def _memolet(agent_id: str, *, source_family: str = "primary_sec_filing", evidence_ref: str = "ref_1") -> dict[str, Any]:
    return {
        "schema_version": "sec_agent_specialist_memolet_v0.1",
        "agent_id": agent_id,
        "status": "pass",
        "evidence_boundary": "bounded_rows_only",
        "summary": "Bounded local memolet.",
        "observations": [
            {
                "claim": "Bounded observation supported by the input evidence.",
                "claim_type": "business_observation",
                "evidence_refs": [evidence_ref],
                "source_families": [source_family],
                "confidence": "medium",
                "unsupported": False,
                "caveats": [],
            }
        ],
        "unsupported_claims": [],
        "conflicts": [],
        "confidence": "medium",
    }
