from __future__ import annotations

import json
from typing import Any

from sec_agent.specialist_llm import (
    ROUTE_SOURCE,
    SPECIALIST_ROUTER_ENV,
    SpecialistLLMConfig,
    build_shared_specialist_context,
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
    assert "Skill v0.3" in fake.calls[0]["messages"][0]["content"]


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
    payload = json.loads(user_prompt.split("Input JSON:\n", 1)[1])
    assert payload["execution_mode"] == "deep_research"
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
    assert result["shared_specialist_context"]["schema_version"] == "sec_agent_shared_specialist_context_v0.1"
    assert result["shared_specialist_context"]["context_digest"].startswith("sha256:")
    assert len(result["specialist_route_results"]) == 2
    assert result["specialist_route_results"][0]["task_card_schema_version"] == "sec_agent_specialist_task_card_v0.1"
    assert result["specialist_route_results"][0]["assigned_memo_slot"] == "fundamentals"
    assert result["specialist_route_results"][0]["required_claim_slot_count"] >= 1
    assert result["specialist_route_results"][0]["shared_context_digest"].startswith("sha256:")
    assert result["specialist_route_results"][0]["prompt_bounded_evidence_row_count"] == 1
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
    assert "snapshot_id" not in request["bounded_evidence_rows"][0]
    assert "as_of_date" not in request["bounded_evidence_rows"][0]


def test_specialist_prompt_uses_compact_json_payload() -> None:
    fake = _FakeChat([json.dumps(_memolet("fundamental_analyst"))])
    request = _request()
    request["bounded_evidence_rows"][0]["snapshot_id"] = ""
    request["bounded_evidence_rows"][0]["as_of_date"] = ""

    result = route_specialist_memolet_llm(
        "fundamental_analyst",
        request,
        config=_config(),
        call_chat_completion=fake,
    )

    user_prompt = fake.calls[0]["messages"][1]["content"]
    payload = json.loads(user_prompt.split("Input JSON:\n", 1)[1])
    row = payload["bounded_evidence_rows"][0]
    assert result["status"] == "pass"
    assert '\n  "bounded_evidence_rows"' not in user_prompt
    assert "snapshot_id" not in row
    assert "as_of_date" not in row
    assert row["evidence_ref"] == "ref_1"


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
    assert len(request["bounded_evidence_rows"]) == 16
    assert request["input_budget"]["prompt_bounded_evidence_row_budget"] == 16
    assert request["input_budget"]["data_view_bounded_evidence_row_budget"] == 32
    assert request["input_budget"]["prompt_summary_char_policy"] == "source_family_tiered_v0_2_compact"
    assert "ledger_ref_16" in request["known_evidence_refs"]


def test_build_specialist_request_from_state_uses_supporting_priority_prompt_budget() -> None:
    request = build_specialist_request_from_state(
        "risk_counterevidence_analyst",
        {
            "user_query": "Deep research risk lens.",
            "agent_activation_plan": {
                "execution_mode": "deep_research",
                "activate_agents": ["risk_counterevidence_analyst"],
                "agent_priorities": {"risk_counterevidence_analyst": "supporting"},
            },
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
            "market_snapshot_rows": [
                {
                    "evidence_ref": f"market_ref_{index}",
                    "source_family": "market_snapshot",
                    "ticker": "NVDA",
                    "summary": f"Market evidence row {index}.",
                }
                for index in range(1, 11)
            ],
        },
    )

    assert request["input_budget"]["agent_priority"] == "supporting"
    assert request["input_budget"]["data_view_bounded_evidence_row_budget"] == 20
    assert request["input_budget"]["prompt_bounded_evidence_row_budget"] == 12
    assert len(request["bounded_evidence_rows"]) == 12
    assert {row["source_family"] for row in request["bounded_evidence_rows"]} == {"primary_sec_filing", "market_snapshot"}


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

    assert len(by_family["primary_sec_filing"]["summary"]) <= 254
    assert len(by_family["market_snapshot"]["summary"]) <= 234
    assert len(by_family["industry_snapshot"]["summary"]) <= 254

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
    assert len(industry_by_family["relationship_graph"]["summary"]) <= 294


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
    payload = json.loads(user_prompt.split("Input JSON:\n", 1)[1])
    assert payload["output_contract"]["unsupported_claim_cap"] == 2
    assert payload["output_contract"]["conflict_cap"] == 2


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


def test_build_specialist_request_from_state_includes_task_card_and_claim_slots() -> None:
    request = build_specialist_request_from_state(
        "fundamental_analyst",
        {
            "user_query": "Compare NVDA fundamentals.",
            "query_contract": {
                "focus_tickers": ["NVDA"],
                "search_scope_tickers": ["NVDA", "AMD"],
            },
            "agent_activation_plan": {
                "execution_mode": "deep_research",
                "agent_priorities": {"fundamental_analyst": "primary"},
            },
            "evidence_requirement_plan": {
                "requirements": [
                    {
                        "requirement_id": "req_revenue",
                        "task_id": "fundamental_revenue",
                        "question_zh": "Need reported revenue and margin.",
                        "priority": "primary",
                        "tickers": ["NVDA"],
                        "source_families": ["primary_sec_filing"],
                        "evidence_routes": ["ledger_first", "filing_text"],
                        "metric_families": ["revenue", "gross_margin"],
                    }
                ]
            },
            "runtime_ledger_rows": [
                {
                    "metric_id": "ledger_ref_1",
                    "source_family": "primary_sec_filing",
                    "ticker": "NVDA",
                    "metric": "revenue",
                    "summary": "NVDA revenue evidence.",
                }
            ],
        },
    )

    task_card = request["assigned_task_card"]
    assert task_card["schema_version"] == "sec_agent_specialist_task_card_v0.1"
    assert task_card["assigned_memo_slot"] == "fundamentals"
    assert task_card["relevant_requirements"][0]["requirement_id"] == "req_revenue"
    assert request["required_claim_slots"][0]["slot_id"] == "fundamentals_reported_fact"
    assert request["counterclaim_slots"][0]["slot_kind"] == "counterclaim_or_gap"


def test_industry_task_card_requires_relationship_claim_slot_when_relationship_rows_exist() -> None:
    request = build_specialist_request_from_state(
        "industry_supply_chain_analyst",
        {
            "agent_activation_plan": {"execution_mode": "deep_research"},
            "evidence_requirement_plan": {
                "requirements": [
                    {
                        "requirement_id": "req_relationship",
                        "task_id": "relationship_scope",
                        "question_zh": "Need relationship graph context.",
                        "source_families": ["relationship_graph"],
                        "evidence_routes": ["relationship_graph"],
                    }
                ]
            },
            "universe_relationship_plan": {
                "relationships": [
                    {
                        "ticker": "NVDA",
                        "related_ticker": "MSFT",
                        "relationship_type": "customer",
                        "evidence_refs": ["rel_ref_1"],
                        "notes": "MSFT cloud capex readthrough hypothesis.",
                    }
                ]
            },
        },
    )

    slot_ids = {slot["slot_id"] for slot in request["required_claim_slots"]}
    assert "relationship_graph_hypothesis" in slot_ids
    assert request["assigned_task_card"]["relevant_requirements"][0]["source_families"] == ["relationship_graph"]


def test_specialist_prompt_passes_task_card_and_slots() -> None:
    fake = _FakeChat([json.dumps(_memolet("fundamental_analyst"))])
    request = _request()
    request["assigned_task_card"] = {"agent_id": "fundamental_analyst", "assigned_memo_slot": "fundamentals"}
    request["required_claim_slots"] = [{"slot_id": "fundamentals_reported_fact", "memo_slot": "fundamentals"}]
    request["counterclaim_slots"] = [{"slot_id": "fundamentals_material_gap", "slot_kind": "counterclaim_or_gap"}]

    result = route_specialist_memolet_llm(
        "fundamental_analyst",
        request,
        config=_config(),
        call_chat_completion=fake,
    )

    user_prompt = fake.calls[0]["messages"][1]["content"]
    assert result["status"] == "pass"
    assert "assigned_task_card" in user_prompt
    assert "required_claim_slots" in user_prompt
    assert "fundamentals_reported_fact" in user_prompt
    assert "Each supported observation should satisfy one required_claim_slot" in user_prompt
    payload = json.loads(user_prompt.split("Input JSON:\n", 1)[1])
    assert payload["known_evidence_refs"]["count"] == 1
    assert "cite only evidence_ref values visible" in user_prompt


def test_shared_specialist_context_compacts_common_scope() -> None:
    context = build_shared_specialist_context(
        {
            "user_query": "Compare AI infrastructure exposure.",
            "query_contract": {"focus_tickers": ["NVDA"], "search_scope_tickers": ["NVDA", "AMD", "MSFT"]},
            "agent_activation_plan": {"execution_mode": "deep_research", "allowed_source_families": ["primary_sec_filing"]},
            "runtime_ledger_rows": [{"metric_id": "ledger_ref_1"}],
            "multi_agent_reflection_report": {
                "sufficiency_level": "bounded_enough",
                "missing_requirements": [{"requirement_id": "req_1"}],
                "bounded_answer_allowed": True,
            },
        }
    )

    assert context["execution_mode"] == "deep_research"
    assert context["focus_tickers"] == ["NVDA"]
    assert context["coverage"]["missing_requirement_count"] == 1
    assert context["source_boundaries"]["ledger_row_count"] == 1
    assert context["context_digest"].startswith("sha256:")


def test_build_specialist_request_rank_selects_slot_relevant_rows_over_prefix_rows() -> None:
    request = build_specialist_request_from_state(
        "fundamental_analyst",
        {
            "user_query": "Analyze gross margin quality.",
            "agent_activation_plan": {"execution_mode": "deep_research"},
            "evidence_requirement_plan": {
                "requirements": [
                    {
                        "requirement_id": "req_margin",
                        "task_id": "fundamental_margin",
                        "question_zh": "Need gross margin evidence.",
                        "priority": "primary",
                        "tickers": ["NVDA"],
                        "source_families": ["primary_sec_filing"],
                        "metric_families": ["gross_margin"],
                    }
                ]
            },
            "runtime_ledger_rows": [
                {
                    "metric_id": f"ledger_ref_{index}",
                    "source_family": "primary_sec_filing",
                    "ticker": "NVDA",
                    "metric": "revenue",
                    "summary": f"Revenue evidence row {index}.",
                }
                for index in range(1, 29)
            ]
            + [
                {
                    "metric_id": "ledger_ref_margin",
                    "source_family": "primary_sec_filing",
                    "ticker": "NVDA",
                    "metric": "gross_margin",
                    "summary": "Gross margin expanded on data-center mix and operating leverage.",
                }
            ],
        },
    )

    selected_refs = {row["evidence_ref"] for row in request["bounded_evidence_rows"]}
    assert "ledger_ref_margin" in selected_refs


def test_build_specialist_request_preserves_comparative_focus_ticker_prompt_rows() -> None:
    request = build_specialist_request_from_state(
        "fundamental_analyst",
        {
            "user_query": "Compare NVDA and AMD fundamentals.",
            "agent_activation_plan": {"execution_mode": "standard_memo"},
            "query_contract": {"focus_tickers": ["NVDA", "AMD"], "search_scope_tickers": ["NVDA", "AMD"]},
            "runtime_ledger_rows": [
                {
                    "metric_id": f"amd_ref_{index}",
                    "source_family": "primary_sec_filing",
                    "ticker": "AMD",
                    "metric": "revenue",
                    "summary": f"AMD revenue evidence row {index}.",
                }
                for index in range(1, 30)
            ]
            + [
                {
                    "metric_id": "nvda_ref_1",
                    "source_family": "primary_sec_filing",
                    "ticker": "NVDA",
                    "metric": "gross_margin",
                    "summary": "NVDA gross margin evidence row.",
                }
            ],
        },
    )

    tickers = {row["ticker"] for row in request["bounded_evidence_rows"]}

    assert {"NVDA", "AMD"} <= tickers
    assert request["prompt_row_distribution"]["by_ticker"]["NVDA"] >= 1
    assert request["input_coverage_summary"]["focus_ticker_primary_row_counts"]["NVDA"] >= 1


def test_build_specialist_request_soft_balances_comparative_prompt_rows() -> None:
    request = build_specialist_request_from_state(
        "fundamental_analyst",
        {
            "user_query": "Compare NVDA and AMD fundamentals.",
            "agent_activation_plan": {"execution_mode": "standard_memo"},
            "query_contract": {"focus_tickers": ["NVDA", "AMD"], "search_scope_tickers": ["NVDA", "AMD"]},
            "runtime_ledger_rows": [
                {
                    "metric_id": f"amd_ref_{index}",
                    "source_family": "primary_sec_filing",
                    "ticker": "AMD",
                    "metric": "revenue",
                    "summary": f"AMD revenue evidence row {index}.",
                }
                for index in range(1, 25)
            ]
            + [
                {
                    "metric_id": f"nvda_ref_{index}",
                    "source_family": "primary_sec_filing",
                    "ticker": "NVDA",
                    "metric": "revenue",
                    "summary": f"NVDA revenue evidence row {index}.",
                }
                for index in range(1, 25)
            ],
        },
    )

    distribution = request["prompt_row_distribution"]["by_ticker"]

    assert distribution["NVDA"] >= 5
    assert distribution["AMD"] >= 5


def test_build_specialist_request_preserves_comparative_metric_diversity() -> None:
    request = build_specialist_request_from_state(
        "fundamental_analyst",
        {
            "user_query": "Compare NVDA and AMD revenue, margins, cash flow, and capex.",
            "agent_activation_plan": {"execution_mode": "standard_memo"},
            "query_contract": {"focus_tickers": ["NVDA", "AMD"], "search_scope_tickers": ["NVDA", "AMD"]},
            "runtime_ledger_rows": [
                {
                    "metric_id": f"amd_capex_ref_{index}",
                    "source_family": "primary_sec_filing",
                    "ticker": "AMD",
                    "metric": "capital_expenditure_proxy",
                    "summary": f"AMD property and equipment row {index}.",
                }
                for index in range(1, 20)
            ]
            + [
                {
                    "metric_id": "amd_revenue_ref",
                    "source_family": "primary_sec_filing",
                    "ticker": "AMD",
                    "metric": "revenue",
                    "summary": "AMD revenue evidence row.",
                },
                {
                    "metric_id": "nvda_revenue_ref",
                    "source_family": "primary_sec_filing",
                    "ticker": "NVDA",
                    "metric": "revenue",
                    "summary": "NVDA revenue evidence row.",
                },
                {
                    "metric_id": "nvda_margin_ref",
                    "source_family": "primary_sec_filing",
                    "ticker": "NVDA",
                    "metric": "gross_margin",
                    "summary": "NVDA gross margin evidence row.",
                },
            ]
            + [
                {
                    "metric_id": f"nvda_cash_ref_{index}",
                    "source_family": "primary_sec_filing",
                    "ticker": "NVDA",
                    "metric": "operating_cash_flow",
                    "summary": f"NVDA cash flow evidence row {index}.",
                }
                for index in range(1, 20)
            ],
        },
    )

    metrics = request["prompt_row_distribution"]["by_metric"]

    assert metrics["revenue"] >= 2
    assert metrics["gross_margin"] >= 1
    assert metrics["capital_expenditure_proxy"] >= 1


def test_build_risk_specialist_request_prioritizes_comparative_market_rows() -> None:
    request = build_specialist_request_from_state(
        "risk_counterevidence_analyst",
        {
            "user_query": "Compare NVDA and AMD fundamentals and market risks.",
            "agent_activation_plan": {"execution_mode": "standard_memo"},
            "query_contract": {"focus_tickers": ["NVDA", "AMD"], "search_scope_tickers": ["NVDA", "AMD"]},
            "runtime_ledger_rows": [
                {
                    "metric_id": f"amd_ref_{index}",
                    "source_family": "primary_sec_filing",
                    "ticker": "AMD",
                    "metric": "revenue",
                    "summary": f"AMD revenue row {index}.",
                }
                for index in range(1, 20)
            ]
            + [
                {
                    "metric_id": f"nvda_ref_{index}",
                    "source_family": "primary_sec_filing",
                    "ticker": "NVDA",
                    "metric": "revenue",
                    "summary": f"NVDA revenue row {index}.",
                }
                for index in range(1, 20)
            ],
            "market_snapshot_rows": [
                {"evidence_ref": "market_nvda", "source_family": "market_snapshot", "ticker": "NVDA", "summary": "NVDA market row."},
                {"evidence_ref": "market_amd", "source_family": "market_snapshot", "ticker": "AMD", "summary": "AMD market row."},
            ],
        },
    )

    distribution = request["prompt_row_distribution"]

    assert distribution["by_source_family"]["market_snapshot"] == 2
    assert distribution["by_ticker_source_family"]["NVDA|market_snapshot"] == 1
    assert distribution["by_ticker_source_family"]["AMD|market_snapshot"] == 1


def test_build_risk_specialist_request_prioritizes_untickered_industry_rows() -> None:
    request = build_specialist_request_from_state(
        "risk_counterevidence_analyst",
        {
            "user_query": "Compare XOM and CVX fundamentals and commodity risks.",
            "agent_activation_plan": {"execution_mode": "standard_memo"},
            "query_contract": {"focus_tickers": ["XOM", "CVX"], "search_scope_tickers": ["XOM", "CVX"]},
            "runtime_ledger_rows": [
                {
                    "metric_id": f"xom_ref_{index}",
                    "source_family": "primary_sec_filing",
                    "ticker": "XOM",
                    "metric": "cash_flow",
                    "summary": f"XOM cash-flow row {index}.",
                }
                for index in range(1, 20)
            ]
            + [
                {
                    "metric_id": f"cvx_ref_{index}",
                    "source_family": "primary_sec_filing",
                    "ticker": "CVX",
                    "metric": "cash_flow",
                    "summary": f"CVX cash-flow row {index}.",
                }
                for index in range(1, 20)
            ],
            "industry_snapshot_rows": [
                {"evidence_ref": "oil_ref", "source_family": "industry_snapshot", "summary": "Oil price context."},
                {"evidence_ref": "gas_ref", "source_family": "industry_snapshot", "summary": "Gas price context."},
            ],
        },
    )

    distribution = request["prompt_row_distribution"]

    assert distribution["by_source_family"]["industry_snapshot"] == 2


def test_specialist_output_contract_caps_gap_payload_before_aggregation() -> None:
    memolet = _memolet("fundamental_analyst")
    memolet["observations"].append(
        {
            "claim": "Unsupported observation should move out of supported observations.",
            "unsupported": True,
            "evidence_refs": [],
            "source_families": ["primary_sec_filing"],
        }
    )
    memolet["unsupported_claims"] = [
        {"claim": f"Unsupported gap {index}", "reason": "not in bounded evidence"}
        for index in range(1, 4)
    ]
    fake = _FakeChat([json.dumps(memolet)])
    request = _request()
    request["execution_mode"] = "deep_research"
    request["output_contract"] = {
        "policy": "fundamental_compact_claim_cards_v0_3",
        "supported_observation_target": "2-4",
        "unsupported_claim_cap": 1,
        "conflict_cap": 2,
    }

    result = route_specialist_memolet_llm(
        "fundamental_analyst",
        request,
        config=_config(),
        call_chat_completion=fake,
    )

    assert result["status"] == "pass"
    assert len(result["memolet"]["observations"]) == 1
    assert len(result["memolet"]["unsupported_claims"]) == 1
    assert result["memolet"]["metadata"]["output_contract_overflow"]["unsupported_claim_overflow_count"] == 3


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
