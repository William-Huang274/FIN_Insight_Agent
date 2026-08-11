from __future__ import annotations

import json
from typing import Any

from sec_agent.multi_agent_runtime import build_agent_data_view, specialist_activation_decisions
from sec_agent.specialist_llm import (
    ROUTE_SOURCE,
    SPECIALIST_ROUTER_ENV,
    SpecialistLLMConfig,
    _compact_capital_macro_pack_for_prompt,
    _compact_fundamental_statement_pack_for_prompt,
    _compact_fundamental_peer_statement_panel_for_prompt,
    _compact_prompt_row,
    _compact_product_spec_pack_for_prompt,
    _specialist_input_coverage_summary,
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


def test_specialist_llm_supports_product_technology_skill() -> None:
    memolet = _memolet("product_technology_analyst", source_family="company_product_evidence_graph")
    memolet["observations"][0].update(
        {
            "claim_type": "company_disclosed_product_kpi",
            "memo_slot": "product_technology",
            "metric_scope": ["product_revenue"],
        }
    )
    fake = _FakeChat([json.dumps(memolet)])
    request = _request(source_family="company_product_evidence_graph")
    request["bounded_evidence_rows"][0].update(
        {
            "promotion_status": "runtime_fact_allowed",
            "exact_value_authority": True,
            "metric_family": "product_revenue",
            "product_or_segment": "Data Center",
        }
    )

    result = route_specialist_memolet_llm(
        "product_technology_analyst",
        request,
        config=_config(),
        call_chat_completion=fake,
    )

    assert result["status"] == "pass"
    assert result["memolet"]["agent_id"] == "product_technology_analyst"
    assert result["memolet"]["observations"][0]["memo_slot"] == "product_technology"
    assert "Product Technology Analysis Skill v0.1" in fake.calls[0]["messages"][0]["content"]


def test_fundamental_specialist_prompt_compacts_pack_headers_and_panel_metadata() -> None:
    long_text = "long nested header " * 80
    statement_pack = _compact_fundamental_statement_pack_for_prompt(
        {
            "schema_version": "fundamental_pack_v1",
            "industry_focus_policy": {"very_large_policy_blob": long_text, "status": "ready"},
            "summary": {"line_item_count": 10, "large_summary_blob": long_text},
            "source_boundary": {"large_boundary_blob": long_text, "status": "bounded"},
            "statement_line_items": [
                {
                    "evidence_ref": "stmt_ref_1",
                    "source_family": "primary_sec_filing",
                    "ticker": "DELL",
                    "metric_family": "revenue",
                    "display_value": "$29.0B",
                    "summary": long_text,
                }
            ],
        },
        agent_id="fundamental_analyst",
    )
    peer_panel = _compact_fundamental_peer_statement_panel_for_prompt(
        {
            "schema_version": "peer_panel_v1",
            "summary": {"large_summary_blob": long_text, "row_count": 99},
            "analysis_gates": {"large_gate_blob": long_text, "status": "pass"},
            "peer_comparable_metric_panel": {
                "large_panel_blob": long_text,
                "comparisons": [
                    {
                        "comparison_id": "cmp_1",
                        "evidence_ref": "peer_ref_1",
                        "source_family": "primary_sec_filing",
                        "ticker": "DELL",
                        "metric_family": "gross_margin",
                        "display_value": "6.0%",
                        "summary": long_text,
                    }
                ],
            },
        },
        agent_id="fundamental_analyst",
    )

    packed_text = json.dumps({"statement": statement_pack, "peer": peer_panel}, ensure_ascii=False)
    assert "stmt_ref_1" in packed_text
    assert "peer_ref_1" in packed_text
    assert long_text not in packed_text
    assert "metadata_ref_only_nested_payload_omitted" in packed_text


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
    assert "2-3 supported fundamental ClaimCards" in user_prompt
    assert "ClaimCard v0.3" in user_prompt
    payload = json.loads(user_prompt.split("Input JSON:\n", 1)[1])
    assert payload["execution_mode"] == "deep_research"
    assert "input_budget" in user_prompt
    assert "output_contract" in user_prompt


def test_specialist_llm_prompt_uses_compact_context_projection() -> None:
    fake = _FakeChat([json.dumps(_memolet("fundamental_analyst"))])
    request = _request()
    request["execution_mode"] = "deep_research"
    request["shared_context"] = {
        "schema_version": "shared",
        "user_query": "x" * 800,
        "execution_mode": "deep_research",
        "focus_tickers": ["NVDA", "DELL"],
        "prompt_policy": {
            "role_payload_policy": "specialist_receives_only_role_task_and_selected_visible_rows",
            "source_layer_policy": "source layer policy " + ("too long " * 120),
        },
    }
    request["role_context"] = {
        "schema_version": "role",
        "agent_id": "fundamental_analyst",
        "analyst_lens": "company_reported_fundamentals_and_management_commentary",
        "dimension_evidence_portfolio_ref": {
            "large_nested_payload": {
                f"item_{index}": "this should be compacted away " * 20
                for index in range(20)
            }
        },
        "fundamental_statement_pack_policy": "three statement policy " + ("long " * 80),
    }

    result = route_specialist_memolet_llm(
        "fundamental_analyst",
        request,
        config=_config(),
        call_chat_completion=fake,
    )

    user_prompt = fake.calls[0]["messages"][1]["content"]
    payload = json.loads(user_prompt.split("Input JSON:\n", 1)[1])
    assert result["status"] == "pass"
    assert len(json.dumps(payload["shared_context"], ensure_ascii=False)) < 900
    assert len(json.dumps(payload["role_context"], ensure_ascii=False)) < 1300
    assert "too long too long too long" not in user_prompt
    assert "this should be compacted away" not in user_prompt


def test_specialist_input_coverage_suppresses_false_manifest_gap_when_rows_are_visible() -> None:
    rows = [
        {"ticker": "NVDA", "source_family": "primary_sec_filing", "evidence_ref": "nvda_10q"},
        {"ticker": "DELL", "source_family": "company_authored_unaudited_sec_filing", "evidence_ref": "dell_8k"},
    ]
    state = {
        "focus_tickers": ["NVDA", "DELL"],
        "source_gaps": [
            {
                "ticker": "NVDA",
                "source_family": "company_authored_unaudited_sec_filing",
                "reason_code": "not_in_manifest_for_mcp_route_scope",
            },
            {
                "ticker": "DELL",
                "source_family": "company_authored_unaudited_sec_filing",
                "reason_code": "not_in_manifest_for_mcp_route_scope",
            },
        ],
    }

    summary = _specialist_input_coverage_summary("fundamental_analyst", rows, state)

    assert summary["focus_ticker_primary_row_counts"] == {"NVDA": 1, "DELL": 1}
    assert summary["focus_ticker_source_gap_reasons"] == {}


def test_specialist_input_coverage_does_not_inherit_sec_gap_for_non_sec_role() -> None:
    rows = [
        {"ticker": "NVDA", "source_family": "relationship_graph", "evidence_ref": "rel_1"},
    ]
    state = {
        "focus_tickers": ["NVDA"],
        "source_gaps": [
            {
                "ticker": "NVDA",
                "source_family": "company_authored_unaudited_sec_filing",
                "reason_code": "not_in_manifest_for_mcp_route_scope",
            }
        ],
    }

    summary = _specialist_input_coverage_summary("industry_supply_chain_analyst", rows, state)

    assert summary["focus_ticker_source_gap_reasons"] == {}


def test_specialist_prompt_preserves_machine_evidence_refs_without_truncation() -> None:
    long_ref = "MARKET_SNAPSHOT::20260530_market_yahoo_chart_full238_6m_bars_3m_fmp_key_metrics_price_return_relative_peer_context"
    compact = _compact_prompt_row(
        {
            "ticker": "DELL",
            "source_family": "market_snapshot",
            "evidence_ref": long_ref,
            "evidence_refs": [long_ref],
            "summary": "x" * 400,
        }
    )

    assert compact["evidence_ref"] == long_ref
    assert compact["evidence_refs"] == [long_ref]
    assert "...[truncated]" not in compact["evidence_ref"]
    assert "...[truncated]" in compact["summary"]


def test_specialist_route_restores_truncated_machine_evidence_ref_before_claim_card() -> None:
    long_ref = "MARKET_SNAPSHOT::20260530_market_yahoo_chart_full238_6m_bars_3m_fmp_key_metrics_price_return_relative_peer_context"
    truncated_ref = long_ref[:80].rstrip() + "...[truncated]"
    request = _request(source_family="market_snapshot")
    request["known_evidence_refs"] = [long_ref]
    request["bounded_evidence_rows"][0]["evidence_ref"] = long_ref
    fake = _FakeChat([json.dumps(_memolet("market_valuation_analyst", source_family="market_snapshot", evidence_ref=truncated_ref))])

    result = route_specialist_memolet_llm(
        "market_valuation_analyst",
        request,
        config=_config(),
        call_chat_completion=fake,
    )

    assert result["status"] == "pass"
    assert result["memolet"]["observations"][0]["evidence_refs"] == [long_ref]
    assert any(
        warning.get("type") == "truncated_evidence_refs_restored_from_known_refs"
        for warning in result["validation"]["warnings"]
    )


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


def test_specialist_llm_demotes_all_no_ref_risk_observations_to_unsupported() -> None:
    memolet = _memolet("risk_counterevidence_analyst")
    for observation in memolet["observations"]:
        observation["evidence_refs"] = []
    fake = _FakeChat([json.dumps(memolet)])

    result = route_specialist_memolet_llm(
        "risk_counterevidence_analyst",
        _request(),
        config=_config(),
        call_chat_completion=fake,
    )

    assert result["status"] == "pass"
    assert result["routing_trace"]["salvage_policy"] == "drop_supported_observations_with_missing_or_unknown_evidence_refs"
    assert result["memolet"]["observations"] == []
    assert result["memolet"]["unsupported_claims"][0]["reason"] == "dropped_from_supported_observations_missing_or_unknown_evidence_refs"
    assert result["validation"]["warnings"][-1]["removed_count"] == 1


def test_specialist_llm_demotes_single_ref_temporal_observation_without_row_support() -> None:
    memolet = _memolet("fundamental_analyst", evidence_ref="pfe_ref")
    memolet["observations"][0]["claim"] = (
        "PFE management guides for approximately 4% product revenue growth in full-year 2026, "
        "signaling moderate demand recovery but no blockbuster acceleration."
    )
    request = _request()
    request["known_evidence_refs"] = ["pfe_ref"]
    request["bounded_evidence_rows"] = [
        {
            "evidence_ref": "pfe_ref",
            "source_family": "company_authored_unaudited_sec_filing",
            "ticker": "PFE",
            "summary": "Management guidance calls for approximately 4% product revenue growth in full-year 2026.",
        }
    ]
    fake = _FakeChat([json.dumps(memolet)])

    result = route_specialist_memolet_llm(
        "fundamental_analyst",
        request,
        config=_config(),
        call_chat_completion=fake,
    )

    assert result["status"] == "pass"
    assert result["routing_trace"]["salvage_policy"] == "demote_single_ref_temporal_observations"
    assert result["memolet"]["observations"] == []
    assert result["memolet"]["unsupported_claims"][0]["reason"] == (
        "demoted_single_ref_temporal_observation_without_row_level_comparison_support"
    )
    assert result["validation"]["warnings"][0]["type"] == "single_ref_temporal_observation_demoted"


def test_specialist_llm_allows_single_ref_temporal_observation_with_row_level_comparison() -> None:
    memolet = _memolet("fundamental_analyst", evidence_ref="jpm_ref")
    memolet["observations"][0]["claim"] = "JPM reported 1Q26 net revenue of $23.4 billion, up 19% YoY."
    request = _request()
    request["known_evidence_refs"] = ["jpm_ref"]
    request["bounded_evidence_rows"] = [
        {
            "evidence_ref": "jpm_ref",
            "source_family": "primary_sec_filing",
            "ticker": "JPM",
            "summary": "1Q26 net revenue was $23.4 billion, up 19% YoY.",
        }
    ]
    fake = _FakeChat([json.dumps(memolet)])

    result = route_specialist_memolet_llm(
        "fundamental_analyst",
        request,
        config=_config(),
        call_chat_completion=fake,
    )

    assert result["status"] == "pass"
    assert "salvage_policy" not in result["routing_trace"]
    assert len(result["memolet"]["observations"]) == 1


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
    assert result["specialist_route_results"][0]["activation_decision"] == "run"
    assert result["specialist_route_results"][0]["matched_requirement_count"] == 0
    assert result["specialist_route_results"][0]["explicit_intent"] is False
    assert "activation_reason" in result["specialist_route_results"][0]
    fingerprint = result["specialist_route_results"][0]["input_pack_fingerprint"]
    assert fingerprint["schema_version"] == "sec_agent_specialist_input_pack_fingerprint_v0_1"
    assert fingerprint["digest"].startswith("sha256:")
    assert fingerprint["known_evidence_ref_count"] >= 1
    assert "ledger_ref_1" in fingerprint["known_evidence_refs"]
    assert fingerprint["component_summaries"]["bounded_evidence_rows"]["item_count"] == 1
    assert fingerprint["policy"] == "fingerprint_only_no_prompt_text_persisted_v0_1"
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
                "execution_mode": "standard_memo",
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
    assert skipped[0]["activation_decision"] == "skipped"
    assert skipped[0]["matched_requirement_count"] == 0
    assert skipped[0]["activation_reason"] == "supporting_specialist_skipped_no_matching_required_item_or_explicit_intent"


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

    assert "ledger_ref_1" in request["known_evidence_refs"]
    assert request["bounded_evidence_rows"][0]["evidence_ref"] == "ledger_ref_1"
    assert "private_path" not in request["bounded_evidence_rows"][0]
    assert len(request["bounded_evidence_rows"][0]["summary"]) <= 400
    assert "snapshot_id" not in request["bounded_evidence_rows"][0]
    assert "as_of_date" not in request["bounded_evidence_rows"][0]


def test_build_specialist_request_includes_role_source_layer_distribution() -> None:
    request = build_specialist_request_from_state(
        "product_technology_analyst",
        {
            "user_query": "Analyze product evidence.",
            "agent_activation_plan": {
                "execution_mode": "deep_research",
                "activate_agents": ["product_technology_analyst"],
            },
            "source_layer_capability_audit": {
                "rows": [
                    {
                        "source_id": "company_ir_reports",
                        "layer_id": "L1",
                        "evidence_graph_status": "staging_parser_gate_pending",
                        "specialist_slots": ["product_technology"],
                        "context_or_proxy_allowed": True,
                        "exact_value_authority_ready": False,
                        "can_support_company_exact_fact": False,
                    },
                    {
                        "source_id": "company_product_pages",
                        "layer_id": "L2",
                        "evidence_graph_status": "structured_not_promoted",
                        "specialist_slots": ["product_technology"],
                        "context_or_proxy_allowed": True,
                        "exact_value_authority_ready": False,
                        "can_support_company_exact_fact": False,
                    },
                    {
                        "source_id": "ecommerce_major_platforms",
                        "layer_id": "L3",
                        "evidence_graph_status": "not_registered",
                        "specialist_slots": ["product_technology"],
                        "context_or_proxy_allowed": False,
                        "exact_value_authority_ready": False,
                        "can_support_company_exact_fact": False,
                    },
                ]
            },
        },
    )

    distribution = request["source_layer_distribution"]
    assert distribution["role"] == "product_technology_analyst"
    assert distribution["coverage_status"] == "gap"
    assert distribution["selected_by_layer"] == {"L1": 1, "L2": 1}
    assert distribution["selected_missing_required_layers"] == ["L3"]
    assert request["shared_context"]["role_source_layer_distribution"]["gap_roles"] == ["product_technology_analyst"]


def test_specialist_prompt_includes_compact_source_layer_distribution() -> None:
    fake = _FakeChat([json.dumps(_memolet("product_technology_analyst", source_family="company_product_evidence_graph"))])
    request = _request(source_family="company_product_evidence_graph")
    request["agent_id"] = "product_technology_analyst"
    request["source_layer_distribution"] = {
        "schema_version": "finsight_role_source_layer_selector_v0_1",
        "role": "product_technology_analyst",
        "coverage_status": "gap",
        "candidate_count": 3,
        "selected_count": 2,
        "repairable_candidate_count": 2,
        "not_registered_count": 1,
        "required_layers": ["L1", "L2", "L3"],
        "selected_by_layer": {"L1": 1, "L2": 1},
        "selected_missing_required_layers": ["L3"],
        "selected_sources": [
            {
                "source_id": "company_product_pages",
                "layer_id": "L2",
                "evidence_graph_status": "structured_not_promoted",
                "claim_scope": "product_existence_spec_or_launch_context",
                "source_entity_role": "product_or_platform_context",
                "issuer_binding_status": "company_domain_bound",
                "product_binding_status": "product_mentioned_in_snapshot",
            }
        ],
    }

    result = route_specialist_memolet_llm(
        "product_technology_analyst",
        request,
        config=_config(),
        call_chat_completion=fake,
    )

    user_prompt = fake.calls[0]["messages"][1]["content"]
    payload = json.loads(user_prompt.split("Input JSON:\n", 1)[1])
    assert result["status"] == "pass"
    assert payload["source_layer_distribution"]["coverage_status"] == "gap"
    assert payload["source_layer_distribution"]["selected_missing_required_layers"] == ["L3"]
    selected_source = payload["source_layer_distribution"]["selected_sources"][0]
    assert selected_source["source_entity_role"] == "product_or_platform_context"
    assert selected_source["issuer_binding_status"] == "company_domain_bound"


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


def test_risk_specialist_request_keeps_required_exact_financial_rows_from_compact_fusion_bundle() -> None:
    request = build_specialist_request_from_state(
        "risk_counterevidence_analyst",
        {
            "user_query": "Assess AI infra thesis risks across hyperscaler capex and DELL margin quality.",
            "agent_activation_plan": {
                "execution_mode": "deep_research",
                "activate_agents": ["risk_counterevidence_analyst"],
            },
            "query_contract": {
                "focus_tickers": ["NVDA", "AMD", "GOOGL", "DELL"],
                "search_scope_tickers": ["NVDA", "AMD", "GOOGL", "DELL", "AMZN", "MSFT"],
            },
            "evidence_fusion_bundle": {
                "authority_rows": [
                    {
                        "evidence_ref": "capex_ref_amzn",
                        "source_family": "primary_sec_filing",
                        "claim_scope": "reported_financial_fact",
                        "ticker": "AMZN",
                        "metric": "capital_expenditure_proxy",
                        "summary": "AMZN capital expenditure increased for AI infrastructure.",
                        "evidence_requirement_ids": ["req_hyperscaler_capex"],
                    },
                    {
                        "evidence_ref": "capex_ref_msft",
                        "source_family": "primary_sec_filing",
                        "claim_scope": "reported_financial_fact",
                        "ticker": "MSFT",
                        "metric": "capital_expenditure_proxy",
                        "summary": "MSFT capital additions provide a second hyperscaler capex data point.",
                        "evidence_requirement_ids": ["req_hyperscaler_capex"],
                    },
                    {
                        "evidence_ref": "margin_ref_dell",
                        "source_family": "company_authored_unaudited_sec_filing",
                        "claim_scope": "reported_financial_fact",
                        "ticker": "DELL",
                        "metric": "operating_income",
                        "summary": "DELL operating income row relevant to AI server margin quality.",
                        "evidence_requirement_ids": ["req_dell_margin_quality"],
                    },
                    {
                        "evidence_ref": "market_ref_nvda",
                        "source_family": "market_snapshot",
                        "claim_scope": "context_or_proxy_only",
                        "ticker": "NVDA",
                        "summary": "NVDA market snapshot context.",
                    },
                    {
                        "evidence_ref": "rel_ref_nvda_dell",
                        "source_family": "relationship_graph",
                        "claim_scope": "scope_or_hypothesis_only",
                        "ticker": "NVDA",
                        "related_ticker": "DELL",
                        "relationship_type": "supplier",
                        "summary": "NVIDIA GPU supply to DELL AI servers is relationship context.",
                    },
                ]
            },
        },
    )

    refs = {row["evidence_ref"] for row in request["bounded_evidence_rows"]}
    families = request["prompt_row_distribution"]["by_source_family"]

    assert "capex_ref_amzn" in refs
    assert "capex_ref_msft" in refs
    assert "margin_ref_dell" in refs
    assert "capex_ref_amzn" in request["known_evidence_refs"]
    assert "capex_ref_msft" in request["known_evidence_refs"]
    assert "margin_ref_dell" in request["known_evidence_refs"]
    assert "rel_ref_nvda_dell" in refs
    assert families["primary_sec_filing"] >= 1
    assert families["company_authored_unaudited_sec_filing"] >= 1
    assert families["relationship_graph"] >= 1


def test_agent_data_view_source_family_bundle_selects_role_specific_rows() -> None:
    state = {
        "user_query": "Assess NVDA AI demand.",
        "query_contract": {"focus_tickers": ["NVDA"], "search_scope_tickers": ["NVDA", "AMD"]},
        "agent_activation_plan": {
            "execution_mode": "standard_memo",
            "activate_agents": ["fundamental_analyst", "market_valuation_analyst"],
            "allowed_source_families": ["primary_sec_filing", "market_snapshot", "industry_snapshot", "relationship_graph"],
        },
        "project_inventory": {
            "schema_version": "project_source_inventory_v0.1",
            "universe": {"ticker_count": 2},
            "indexes": {"manifest_path": "D:/FIN_Insight_Agent/data/raw_private/sec/index.json"},
            "milvus_runtime": {"available": True, "location": "cloud", "handle": "private-handle"},
        },
        "bounded_gap_register": {
            "schema_version": "sec_agent_bounded_gap_register_v0.1",
            "gap_count": 1,
            "gaps": [
                {
                    "gap_id": "gap_nvda_sell_through",
                    "source_family": "market_snapshot",
                    "gap_type": "commercial_tracker_gap",
                    "ticker": "NVDA",
                    "metric": "sell_through",
                    "repairability": "commercial_tracker_required",
                    "claim_boundary": "do_not_fill_with_generic_fallback_or_proxy_fact",
                }
            ],
            "summary": {"commercial_tracker_gap_count": 1},
        },
        "context_rows": [
            {
                "evidence_ref": "sec_semantic_ref",
                "source_family": "primary_sec_filing",
                "ticker": "NVDA",
                "summary": "Typed semantic SEC evidence about supplier demand.",
                "retrieval_route": "milvus_semantic",
                "vector_kind": "relationship_context",
            }
        ],
        "market_snapshot_rows": [
            {
                "evidence_ref": "market_ref",
                "source_family": "market_snapshot",
                "ticker": "NVDA",
                "summary": "Timestamped market valuation context.",
            }
        ],
        "industry_snapshot_rows": [
            {
                "evidence_ref": "industry_ref",
                "source_family": "industry_snapshot",
                "summary": "Industry electricity demand context.",
            }
        ],
        "universe_relationship_plan": {
            "relationships": [
                {
                    "ticker": "NVDA",
                    "related_ticker": "MSFT",
                    "relationship_type": "customer",
                    "evidence_refs": ["rel_ref_1"],
                    "notes": "Relationship hypothesis only.",
                }
            ]
        },
    }

    fundamental = build_agent_data_view("fundamental_analyst", state)
    market = build_agent_data_view("market_valuation_analyst", state)
    industry = build_agent_data_view("industry_supply_chain_analyst", state)
    risk = build_agent_data_view("risk_counterevidence_analyst", state)

    fundamental_bundle = fundamental["source_family_bundle"]
    assert fundamental["schema_version"] == "sec_agent_agent_data_view_v0.3"
    assert fundamental["global_context_ref"]["context_digest"].startswith("sha256:")
    assert fundamental["global_context"]["selected_playbook_ids"] == []
    assert fundamental["global_context"]["source_boundary_registry"]["milvus_runtime"]["location"] == "cloud"
    assert fundamental["role_context"]["role_context_type"] == "specialist"
    assert fundamental["role_context"]["private_context_policy"] == "private_operator_context_excluded"
    assert fundamental["role_context"]["raw_rows_visible"] is False
    assert fundamental["context_digest"].startswith("sha256:")
    assert fundamental["bounded_gap_refs"][0]["gap_id"] == "gap_nvda_sell_through"
    serialized = json.dumps(fundamental, ensure_ascii=False)
    assert "data/raw_private" not in serialized
    assert "private-handle" not in serialized
    assert fundamental_bundle["selected_source_families"] == ["primary_sec_filing"]
    assert fundamental_bundle["semantic_supplement_row_count"] == 1
    assert fundamental_bundle["semantic_vector_kinds"] == ["relationship_context"]
    assert "milvus_semantic_rows_cannot_prove_exact_values_without_ledger_or_filing_quote" in fundamental_bundle["forbidden_claim_scopes"]
    assert fundamental["bounded_evidence_rows"][0]["semantic_supplement"] is True
    assert fundamental["bounded_evidence_rows"][0]["exact_value_authority"] is False

    assert market["source_family_bundle"]["selected_source_families"] == ["market_snapshot"]
    assert market["source_family_bundle"]["context_only_source_families"] == ["market_snapshot"]
    assert "market_snapshot_cannot_prove_company_reported_fundamentals_or_overwrite_sec_facts" in market["source_family_bundle"]["forbidden_claim_scopes"]

    assert industry["source_family_bundle"]["selected_source_families"] == ["industry_snapshot", "relationship_graph"]
    assert industry["source_family_bundle"]["context_only_source_families"] == ["industry_snapshot", "relationship_graph"]

    assert set(risk["source_family_bundle"]["selected_source_families"]) == {"primary_sec_filing", "market_snapshot", "industry_snapshot"}
    assert "relationship_graph" not in {row["source_family"] for row in risk["bounded_evidence_rows"]}


def test_agent_data_view_routes_product_evidence_and_public_source_context_rows() -> None:
    state = {
        "query_contract": {"focus_tickers": ["AAPL"]},
        "agent_activation_plan": {
            "metadata": {
                "playbook_policy": {
                    "selected_playbook_ids": ["consumer_electronics"],
                    "forbidden_claims": ["sell_through_without_tracker"],
                    "commercial_gap_policy": {"sell_through": ["Circana", "NielsenIQ"]},
                }
            }
        },
        "product_evidence_rows": [
            {
                "evidence_ref": "product_fact_aapl_services_2024",
                "source_family": "company_product_evidence_graph",
                "ticker": "AAPL",
                "metric": "product_revenue",
                "product_or_segment": "Services",
                "value": "96.2 billion USD",
                "promotion_status": "runtime_fact_allowed",
                "claim_scope": "company_disclosed_product_kpi_fact",
                "exact_value_authority": True,
                "summary": "AAPL disclosed Services revenue for FY2024.",
            },
            {
                "evidence_ref": "product_review_candidate",
                "source_family": "company_product_evidence_graph",
                "ticker": "AAPL",
                "metric": "candidate_product_revenue",
                "promotion_status": "review_queue_not_runtime_fact",
                "claim_scope": "review_queue_not_runtime_fact",
                "summary": "A review-only candidate should not enter fundamental bounded rows.",
            },
            {
                "evidence_ref": "product_gap_aapl_channel_inventory",
                "source_family": "company_product_evidence_graph",
                "ticker": "AAPL",
                "metric": "channel_inventory",
                "promotion_status": "gap_exposed_not_fallback",
                "claim_scope": "source_gap_only",
                "summary": "Channel inventory requires commercial tracker data.",
            },
        ],
        "public_source_context_rows": [
            {
                "evidence_ref": "public_fred_api_context",
                "source_family": "public_source_context",
                "source_id": "fred_api",
                "underlying_source_family": "macro_industry_indicator",
                "metric": "macro_time_series_observation",
                "claim_scope": "industry_context_only",
                "context_only": True,
                "exact_value_authority": False,
                "summary": "FRED context row for macro/industry conditions.",
            }
        ],
    }

    fundamental = build_agent_data_view("fundamental_analyst", state)
    product = build_agent_data_view("product_technology_analyst", state)
    industry = build_agent_data_view("industry_supply_chain_analyst", state)
    risk = build_agent_data_view("risk_counterevidence_analyst", state)

    fundamental_refs = {row["evidence_ref"] for row in fundamental["bounded_evidence_rows"]}
    assert "product_fact_aapl_services_2024" in fundamental_refs
    assert "product_review_candidate" not in fundamental_refs
    assert "public_fred_api_context" not in fundamental_refs
    assert "company_product_evidence_graph" in fundamental["source_family_bundle"]["selected_source_families"]
    assert "company_product_evidence_graph_requires_runtime_fact_allowed_for_product_kpi_claims" in fundamental["source_family_bundle"]["forbidden_claim_scopes"]

    product_refs = {row["evidence_ref"] for row in product["bounded_evidence_rows"]}
    assert {"product_fact_aapl_services_2024", "product_review_candidate", "product_gap_aapl_channel_inventory", "public_fred_api_context"} <= product_refs
    assert product["assigned_task_card"]["assigned_memo_slot"] == "product_technology"
    assert product["required_claim_slots"][1]["slot_id"] == "company_disclosed_product_kpi"
    assert product["required_claim_slots"][1]["claim_type_allowlist"] == ["company_disclosed_product_kpi"]
    assert product["counterclaim_slots"][0]["slot_id"] == "product_commercial_tracker_gap"
    assert "public_source_context" in product["source_family_bundle"]["context_only_source_families"]
    assert "company_product_evidence_graph_requires_runtime_fact_allowed_for_product_kpi_claims" in product["source_family_bundle"]["forbidden_claim_scopes"]
    assert product["source_family_bundle"]["selected_playbook_ids"] == ["consumer_electronics"]
    assert "sell_through_without_tracker" in product["source_family_bundle"]["playbook_forbidden_claims"]
    assert "sell_through_without_tracker" in product["source_family_bundle"]["forbidden_claim_scopes"]
    assert product["forbidden_claim_scopes"] == product["source_family_bundle"]["forbidden_claim_scopes"]

    industry_families = {row["source_family"] for row in industry["bounded_evidence_rows"]}
    assert {"company_product_evidence_graph", "public_source_context"} <= industry_families
    assert "public_source_context_cannot_prove_company_reported_product_sales_market_share_or_profitability" in industry["source_family_bundle"]["forbidden_claim_scopes"]

    risk_families = {row["source_family"] for row in risk["bounded_evidence_rows"]}
    assert {"company_product_evidence_graph", "public_source_context"} <= risk_families


def test_specialist_request_preserves_public_web_entity_binding_metadata() -> None:
    request = build_specialist_request_from_state(
        "industry_supply_chain_analyst",
        {
            "user_query": "Analyze Dell supply-chain relationship context.",
            "query_contract": {"focus_tickers": ["DELL"]},
            "agent_activation_plan": {
                "execution_mode": "standard_memo",
                "activate_agents": ["industry_supply_chain_analyst"],
            },
            "context_rows": [
                {
                    "evidence_ref": "public_web_supply_news_dell",
                    "source_family": "live_public_web_context",
                    "ticker": "DELL",
                    "source_class": "supplier_customer_official_news",
                    "structured_context_type": "official_supply_chain_news_context",
                    "summary": "Official partner news says Dell was named as supplier for a customer AI server deployment.",
                    "context_only": True,
                    "exact_value_authority": False,
                    "issuer_binding_status": "issuer_mentioned_in_snapshot",
                    "product_binding_status": "not_bound",
                    "counterparty_binding_status": "relationship_context_candidate",
                    "entity_binding_claim_boundary": "Binding metadata does not promote shipment or order-volume authority.",
                    "entity_binding": {
                        "issuer_binding_status": "issuer_mentioned_in_snapshot",
                        "product_binding_status": "not_bound",
                        "counterparty_binding_status": "relationship_context_candidate",
                        "source_entity_role": "supplier_customer_or_partner_context",
                        "issuer_matched_terms": ["DELL"],
                        "binding_claim_boundary": "Binding metadata does not promote shipment or order-volume authority.",
                    },
                }
            ],
        },
    )

    row = next(item for item in request["bounded_evidence_rows"] if item["evidence_ref"] == "public_web_supply_news_dell")
    distribution = request["prompt_row_distribution"]

    assert row["source_entity_role"] == "supplier_customer_or_partner_context"
    assert row["issuer_binding_status"] == "issuer_mentioned_in_snapshot"
    assert row["counterparty_binding_status"] == "relationship_context_candidate"
    assert row["entity_binding"]["issuer_matched_terms"] == ["DELL"]
    assert distribution["by_source_entity_role"] == {"supplier_customer_or_partner_context": 1}
    assert distribution["by_issuer_binding_status"] == {"issuer_mentioned_in_snapshot": 1}


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
    assert request["input_budget"]["data_view_bounded_evidence_row_budget"] == 48
    assert request["input_budget"]["prompt_summary_char_policy"] == "source_family_tiered_v0_2_compact"
    assert "ledger_ref_16" in request["known_evidence_refs"]
    assert "ledger_ref_17" not in request["known_evidence_refs"]


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
                    "summary": f"Revenue pressure risk evidence row {index}.",
                }
                for index in range(1, 31)
            ],
            "market_snapshot_rows": [
                {
                    "evidence_ref": f"market_ref_{index}",
                    "source_family": "market_snapshot",
                    "ticker": "NVDA",
                    "summary": f"Market risk evidence row {index}.",
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


def test_specialist_prompt_filters_role_specific_refs_before_fingerprinting() -> None:
    state = {
        "user_query": "Analyze AI infrastructure semicap product, deployment, and risk evidence.",
        "query_contract": {"focus_tickers": ["AMAT", "LRCX"], "search_scope_tickers": ["AMAT", "LRCX"]},
        "agent_activation_plan": {
            "execution_mode": "deep_research",
            "activate_agents": [
                "product_technology_analyst",
                "industry_supply_chain_analyst",
                "risk_counterevidence_analyst",
            ],
            "agent_priorities": {
                "product_technology_analyst": "primary",
                "industry_supply_chain_analyst": "primary",
                "risk_counterevidence_analyst": "supporting",
            },
        },
        "runtime_ledger_rows": [
            {
                "metric_id": "amat_revenue_plain",
                "source_family": "primary_sec_filing",
                "ticker": "AMAT",
                "metric": "revenue",
                "summary": "AMAT revenue increased in the quarter.",
            },
            {
                "metric_id": "lrcx_export_risk",
                "source_family": "primary_sec_filing",
                "ticker": "LRCX",
                "metric": "export_restriction_risk",
                "summary": "Export control risk and China exposure could constrain sales.",
            },
        ],
        "product_evidence_rows": [
            {
                "evidence_ref": "amat_product_profile",
                "source_family": "company_product_evidence_graph",
                "ticker": "AMAT",
                "source_role": "official_product_surface",
                "metric": "product_architecture",
                "product_family": "wafer_fab_equipment",
                "promotion_status": "context_or_lead_available",
                "summary": "AMAT product architecture and process-control platform context.",
            },
            {
                "evidence_ref": "amat_customer_deployment",
                "source_family": "company_product_evidence_graph",
                "ticker": "AMAT",
                "source_role": "official_customer_deployment_surface",
                "structured_context_type": "customer_deployment_signal",
                "metric": "customer_deployment",
                "promotion_status": "context_or_lead_available",
                "summary": "Customer deployment and supplier relationship signal for a foundry capacity expansion.",
            },
        ],
        "industry_snapshot_rows": [
            {
                "evidence_ref": "semicap_cycle_context",
                "source_family": "industry_snapshot",
                "ticker": "AMAT",
                "metric": "wafer_fab_equipment_cycle",
                "summary": "Semicap wafer fab equipment cycle and foundry demand context.",
            }
        ],
    }

    product = build_specialist_request_from_state("product_technology_analyst", state)
    industry = build_specialist_request_from_state("industry_supply_chain_analyst", state)
    risk = build_specialist_request_from_state("risk_counterevidence_analyst", state)

    product_refs = {row["evidence_ref"] for row in product["bounded_evidence_rows"]}
    industry_refs = {row["evidence_ref"] for row in industry["bounded_evidence_rows"]}
    risk_refs = {row["evidence_ref"] for row in risk["bounded_evidence_rows"]}

    assert "amat_product_profile" in product_refs
    assert "amat_customer_deployment" not in product_refs
    assert "amat_customer_deployment" in industry_refs
    assert "amat_product_profile" not in industry_refs
    assert "lrcx_export_risk" in risk_refs
    assert "amat_revenue_plain" not in risk_refs
    assert "amat_product_profile" not in risk_refs


def test_specialist_prompt_uses_source_family_summary_budgets() -> None:
    request = build_specialist_request_from_state(
        "risk_counterevidence_analyst",
        {
            "agent_activation_plan": {"execution_mode": "deep_research"},
            "runtime_ledger_rows": [
                {"metric_id": "sec_ref", "source_family": "primary_sec_filing", "summary": "risk " + "s" * 900},
            ],
            "market_snapshot_rows": [
                {"evidence_ref": "market_ref", "source_family": "market_snapshot", "summary": "risk " + "m" * 900},
            ],
            "industry_snapshot_rows": [
                {"evidence_ref": "industry_ref", "source_family": "industry_snapshot", "summary": "risk " + "i" * 900},
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
            "focus_tickers": ["NVDA"],
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
    assert request["required_claim_slots"][0]["slot_id"] == "fundamentals_three_statement_quality"
    assert request["counterclaim_slots"][0]["slot_kind"] == "counterclaim_or_gap"
    assert request["method_runtime_pack"]["status"] == "runtime_injected"
    assert request["method_runtime_pack"]["lane"] == "ai_semis"
    assert "three_statement_peer_panel" in request["method_runtime_pack"]["active_method_ids"]
    assert request["specialist_runtime_rubric"]["role_runtime_mission"].startswith("Bridge product")
    assert "product_to_financial_bridge" in request["specialist_runtime_rubric"]["must_answer"]
    assert "judgment_candidates" in request["output_contract"]["required_outputs"]
    assert "business_mechanism" in request["output_contract"]["judgment_candidate_contract"]["required_fields"]


def test_specialist_activation_matches_chinese_industry_and_risk_requirements() -> None:
    decisions = specialist_activation_decisions(
        {
            "agent_activation_plan": {
                "execution_mode": "deep_research",
                "activate_agents": [
                    "industry_supply_chain_analyst",
                    "risk_counterevidence_analyst",
                ],
                "agent_priorities": {
                    "industry_supply_chain_analyst": "primary",
                    "risk_counterevidence_analyst": "supporting",
                },
            },
            "evidence_requirement_plan": {
                "requirements": [
                    {
                        "requirement_id": "req_orders",
                        "task_id": "订单积压出货周期",
                        "question_zh": "分析订单、积压、出货周期和客户集中度。",
                        "priority": "primary",
                    },
                    {
                        "requirement_id": "req_export_risk",
                        "task_id": "出口限制监管风险",
                        "question_zh": "分析出口限制、监管和地缘风险。",
                        "priority": "supporting",
                    },
                ]
            },
        }
    )

    by_agent = {row["agent_id"]: row for row in decisions}
    assert by_agent["industry_supply_chain_analyst"]["decision"] == "run"
    assert by_agent["industry_supply_chain_analyst"]["matched_requirement_count"] >= 1
    assert by_agent["risk_counterevidence_analyst"]["decision"] == "run"
    assert by_agent["risk_counterevidence_analyst"]["matched_requirement_count"] >= 1

    intent_only = specialist_activation_decisions(
        {
            "user_query": "分析 ASML、AMAT、LRCX、KLAC 的订单、积压、出货周期、客户集中度、出口限制和监管风险。",
            "agent_activation_plan": {
                "execution_mode": "deep_research",
                "activate_agents": [
                    "industry_supply_chain_analyst",
                    "risk_counterevidence_analyst",
                ],
                "agent_priorities": {
                    "industry_supply_chain_analyst": "primary",
                    "risk_counterevidence_analyst": "supporting",
                },
            },
        }
    )
    intent_by_agent = {row["agent_id"]: row for row in intent_only}
    assert intent_by_agent["industry_supply_chain_analyst"]["decision"] == "run"
    assert intent_by_agent["industry_supply_chain_analyst"]["explicit_intent"] is True
    assert intent_by_agent["risk_counterevidence_analyst"]["decision"] == "run"
    assert intent_by_agent["risk_counterevidence_analyst"]["explicit_intent"] is True


def test_prompt_pack_compaction_caps_large_product_and_fundamental_rows() -> None:
    product_pack = {
        "schema_version": "product_spec_pack_unit",
        "summary": {"product_spec_count": 20},
        "product_specs": [
            {
                "evidence_ref": f"spec_{index}",
                "summary": "H100 spec " + ("very long " * 80),
                "empty": "",
            }
            for index in range(12)
        ],
        "customer_deployment_signals": [
            {"evidence_ref": f"deploy_{index}", "notes": "deployment " + ("detail " * 80)}
            for index in range(12)
        ],
    }
    compact_product = _compact_product_spec_pack_for_prompt(product_pack, agent_id="product_technology_analyst")

    assert len(compact_product["product_specs"]) == 3
    assert compact_product["customer_deployment_signals"] == []
    assert compact_product["role_projection_policy"] == "product_prompt_specs_kpi_channel_only_v0_1"
    assert "customer_deployment_signals" in compact_product["excluded_sections"]
    assert len(compact_product["product_specs"][0]["summary"]) <= 200
    assert "empty" not in compact_product["product_specs"][0]

    panel = {
        "schema_version": "fundamental_panel_unit",
        "summary": {"line_item_count": 20},
        "analysis_gates": {"three_statement_coverage": True},
        "three_statement_metric_panel": {
            "statement_type_counts": {"income_statement": 12},
            "statements": [{"evidence_ref": f"stmt_{index}", "summary": "row " * 120} for index in range(10)],
        },
        "peer_comparable_metric_panel": {
            "comparisons": [{"evidence_ref": f"peer_{index}", "description": "peer " * 120} for index in range(10)]
        },
        "analysis_gaps": [{"evidence_ref": f"gap_{index}", "rationale": "gap " * 100} for index in range(10)],
    }
    compact_panel = _compact_fundamental_peer_statement_panel_for_prompt(panel, agent_id="fundamental_analyst")

    assert len(compact_panel["three_statement_metric_panel"]["statements"]) == 3
    assert len(compact_panel["peer_comparable_metric_panel"]["comparisons"]) == 5
    assert len(compact_panel["analysis_gaps"]) == 5
    assert len(compact_panel["peer_comparable_metric_panel"]["comparisons"][0]["description"]) <= 240


def test_capital_macro_pack_prompt_is_role_projected_not_duplicated_wholesale() -> None:
    pack = {
        "schema_version": "capital_macro_pack_unit",
        "summary": {"input_row_count": 42},
        "debt_instruments": [{"evidence_ref": "debt_ref", "summary": "Debt maturity row."}],
        "ownership_positions": [{"evidence_ref": "ownership_ref", "summary": "13F holder row."}],
        "insider_transactions": [{"evidence_ref": "insider_ref", "summary": "Form 4 row."}],
        "macro_drivers": [{"evidence_ref": "macro_ref", "summary": "Rate driver row."}],
        "company_exposure_edges": [{"evidence_ref": "exposure_ref", "summary": "Capex exposure edge."}],
        "vertical_official_objects": [{"evidence_ref": "vertical_ref", "summary": "EIA/FRED context row."}],
        "rejected_objects": [{"evidence_ref": "reject_ref", "summary": "Rejected weak proxy row."}],
    }

    fundamental = _compact_capital_macro_pack_for_prompt(pack, agent_id="fundamental_analyst")
    industry = _compact_capital_macro_pack_for_prompt(pack, agent_id="industry_supply_chain_analyst")
    risk = _compact_capital_macro_pack_for_prompt(pack, agent_id="risk_counterevidence_analyst")

    assert fundamental["role_projection_policy"].endswith("fundamental_capital_structure")
    assert "debt_instruments" in fundamental
    assert "ownership_positions" in fundamental
    assert "macro_drivers" not in fundamental
    assert "vertical_official_objects" not in fundamental

    assert industry["role_projection_policy"].endswith("industry_exposure_edges")
    assert "macro_drivers" in industry
    assert "vertical_official_objects" in industry
    assert "debt_instruments" not in industry
    assert "ownership_positions" not in industry

    assert risk["role_projection_policy"].endswith("risk_counterevidence")
    assert "debt_instruments" in risk
    assert "rejected_objects" in risk
    assert "ownership_positions" not in risk
    assert "vertical_official_objects" not in risk

    assert set(fundamental["included_sections"]) != set(industry["included_sections"])
    assert set(industry["included_sections"]) != set(risk["included_sections"])


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


def test_specialist_prompt_passes_source_family_bundle() -> None:
    fake = _FakeChat([json.dumps(_memolet("fundamental_analyst", evidence_ref="sec_semantic_ref"))])
    request = build_specialist_request_from_state(
        "fundamental_analyst",
        {
            "context_rows": [
                {
                    "evidence_ref": "sec_semantic_ref",
                    "source_family": "primary_sec_filing",
                    "ticker": "NVDA",
                    "summary": "Typed semantic SEC evidence.",
                    "retrieval_route": "milvus_semantic",
                    "vector_kind": "paraphrase_context",
                }
            ]
        },
    )

    result = route_specialist_memolet_llm(
        "fundamental_analyst",
        request,
        config=_config(),
        call_chat_completion=fake,
    )

    user_prompt = fake.calls[0]["messages"][1]["content"]
    payload = json.loads(user_prompt.split("Input JSON:\n", 1)[1])
    assert result["status"] == "pass"
    assert request["source_family_bundle"]["semantic_supplement_row_count"] == 1
    assert payload["source_family_bundle"]["semantic_supplement_row_count"] == 1
    assert payload["bounded_evidence_rows"][0]["semantic_supplement"] is True
    assert payload["bounded_evidence_rows"][0]["exact_value_authority"] is False
    assert "Use source_family_bundle to enforce selected source families" in user_prompt
    assert "typed_milvus_rows_are_sec_recall_supplements_not_exact_value_authority" in user_prompt


def test_product_specialist_demotes_product_kpi_without_exact_authority() -> None:
    memolet = _memolet("product_technology_analyst", source_family="public_source_context", evidence_ref="public_proxy_ref")
    memolet["observations"][0].update(
        {
            "claim": "The public proxy row proves product revenue momentum.",
            "claim_type": "company_disclosed_product_kpi",
            "memo_slot": "product_technology",
            "metric_scope": ["product_revenue"],
        }
    )
    fake = _FakeChat([json.dumps(memolet)])
    request = {
        "user_query": "Analyze product KPI.",
        "known_evidence_refs": ["public_proxy_ref"],
        "bounded_evidence_rows": [
            {
                "evidence_ref": "public_proxy_ref",
                "source_family": "public_source_context",
                "summary": "Public proxy context only.",
                "context_only": True,
                "exact_value_authority": False,
            }
        ],
        "output_contract": {
            "policy": "product_technology_claim_cards_v0_1",
            "supported_observation_target": "1-3",
            "unsupported_claim_cap": 2,
            "conflict_cap": 1,
        },
    }

    result = route_specialist_memolet_llm(
        "product_technology_analyst",
        request,
        config=_config(),
        call_chat_completion=fake,
    )

    assert result["status"] == "pass"
    assert result["memolet"]["observations"] == []
    assert result["memolet"]["unsupported_claims"][0]["reason"] == (
        "demoted_product_kpi_without_company_disclosed_exact_authority"
    )
    assert result["routing_trace"]["salvage_policy"] == "demote_product_kpi_without_exact_authority"
    assert result["validation"]["warnings"][-1]["type"] == "product_kpi_observation_demoted"


def test_product_specialist_keeps_product_kpi_with_exact_authority() -> None:
    memolet = _memolet("product_technology_analyst", source_family="company_product_evidence_graph", evidence_ref="product_fact_ref")
    memolet["observations"][0].update(
        {
            "claim": "The company-disclosed product KPI supports the product thesis.",
            "claim_type": "company_disclosed_product_kpi",
            "memo_slot": "product_technology",
            "metric_scope": ["product_revenue"],
        }
    )
    fake = _FakeChat([json.dumps(memolet)])
    request = {
        "user_query": "Analyze product KPI.",
        "known_evidence_refs": ["product_fact_ref"],
        "bounded_evidence_rows": [
            {
                "evidence_ref": "product_fact_ref",
                "source_family": "company_product_evidence_graph",
                "promotion_status": "runtime_fact_allowed",
                "exact_value_authority": True,
                "context_only": False,
                "metric_family": "product_revenue",
                "product_or_segment": "Services",
                "summary": "Company-disclosed Services product revenue.",
            }
        ],
    }

    result = route_specialist_memolet_llm(
        "product_technology_analyst",
        request,
        config=_config(),
        call_chat_completion=fake,
    )

    assert result["status"] == "pass"
    assert len(result["memolet"]["observations"]) == 1
    assert result["memolet"]["unsupported_claims"] == []
    assert "salvage_policy" not in result["routing_trace"]


def test_specialist_demotes_numeric_claim_when_cited_row_has_different_number() -> None:
    memolet = _memolet("market_valuation_analyst", source_family="market_snapshot", evidence_ref="dell_market_ref")
    memolet["observations"][0].update(
        {
            "claim": "DELL returned 1.8% over the 3-month period.",
            "claim_type": "market_context",
            "memo_slot": "market_valuation",
            "metric_scope": ["return_3m"],
        }
    )
    fake = _FakeChat([json.dumps(memolet)])
    request = {
        "user_query": "Analyze DELL market reaction.",
        "known_evidence_refs": ["dell_market_ref"],
        "bounded_evidence_rows": [
            {
                "evidence_ref": "dell_market_ref",
                "source_family": "market_snapshot",
                "metric": "return_3m",
                "value": "176.4%",
                "summary": "DELL 3-month return was 176.4% as of 2026-05-29.",
                "as_of_date": "2026-05-29",
            }
        ],
    }

    result = route_specialist_memolet_llm(
        "market_valuation_analyst",
        request,
        config=_config(),
        call_chat_completion=fake,
    )

    assert result["status"] == "pass"
    assert result["memolet"]["observations"] == []
    assert result["memolet"]["unsupported_claims"][0]["reason"] == "demoted_numeric_claim_without_cited_row_support"
    assert result["routing_trace"]["salvage_policy"] == "demote_numeric_claim_without_cited_row_support"


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


def test_fundamental_request_keeps_required_non_focus_hyperscaler_capex_rows() -> None:
    request = build_specialist_request_from_state(
        "fundamental_analyst",
        {
            "user_query": "Assess AI infrastructure demand and DELL margin quality.",
            "agent_activation_plan": {
                "execution_mode": "deep_research",
                "activate_agents": ["fundamental_analyst"],
            },
            "query_contract": {
                "focus_tickers": ["NVDA", "AMD", "GOOGL", "DELL"],
                "search_scope_tickers": ["NVDA", "AMD", "GOOGL", "DELL", "AMZN", "MSFT"],
            },
            "evidence_fusion_bundle": {
                "authority_rows": [
                    {
                        "evidence_ref": "dell_margin_ref",
                        "source_family": "primary_sec_filing",
                        "claim_scope": "reported_financial_fact",
                        "ticker": "DELL",
                        "metric": "gross_margin",
                        "summary": "DELL gross margin row for margin-quality analysis.",
                        "evidence_requirement_ids": ["req_dell_margin_quality"],
                    },
                    {
                        "evidence_ref": "amzn_capex_ref",
                        "source_family": "primary_sec_filing",
                        "claim_scope": "reported_financial_fact",
                        "ticker": "AMZN",
                        "metric": "capital_expenditure_proxy",
                        "summary": "AMZN capex row required for hyperscaler demand context.",
                        "evidence_requirement_ids": ["req_hyperscaler_capex"],
                    },
                    {
                        "evidence_ref": "msft_capex_ref",
                        "source_family": "primary_sec_filing",
                        "claim_scope": "reported_financial_fact",
                        "ticker": "MSFT",
                        "metric": "capital_expenditure_proxy",
                        "summary": "MSFT capex row required for hyperscaler demand context.",
                        "evidence_requirement_ids": ["req_hyperscaler_capex"],
                    },
                ]
                + [
                    {
                        "evidence_ref": f"focus_ref_{ticker}_{index}",
                        "source_family": "company_authored_unaudited_sec_filing",
                        "claim_scope": "company_disclosed_context_only",
                        "ticker": ticker,
                        "metric": "revenue",
                        "summary": f"{ticker} context row {index}.",
                    }
                    for ticker in ("NVDA", "AMD", "GOOGL", "DELL")
                    for index in range(1, 6)
                ]
            },
        },
    )

    refs = {row["evidence_ref"] for row in request["bounded_evidence_rows"]}

    assert "dell_margin_ref" in refs
    assert "amzn_capex_ref" in refs
    assert "msft_capex_ref" in refs
    assert "amzn_capex_ref" in request["known_evidence_refs"]
    assert "msft_capex_ref" in request["known_evidence_refs"]


def test_build_product_specialist_request_balances_comparative_prompt_rows() -> None:
    product_rows = []
    for ticker in ("NVDA", "AMD", "GOOGL", "DELL"):
        for index in range(1, 9):
            product_rows.append(
                {
                    "evidence_ref": f"product_slot::{ticker}::{index}",
                    "source_family": "company_product_evidence_graph",
                    "ticker": ticker,
                    "product_family": "GPU / Accelerator" if ticker != "DELL" else "AI Server / Rack OEM",
                    "product_or_segment": f"{ticker} accelerator architecture product {index}",
                    "promotion_status": "runtime_context_taxonomy_only",
                    "claim_scope": "product_taxonomy_context",
                    "summary": f"product slot; {ticker} accelerator architecture product {index}; bounded product context.",
                }
            )
    request = build_specialist_request_from_state(
        "product_technology_analyst",
        {
            "user_query": "Compare NVDA, AMD, GOOGL, and DELL AI infrastructure products.",
            "product_intelligence_runtime_autoload": False,
            "agent_activation_plan": {
                "execution_mode": "deep_research",
                "activate_agents": ["product_technology_analyst"],
            },
            "query_contract": {
                "focus_tickers": ["NVDA", "AMD", "GOOGL", "DELL"],
                "search_scope_tickers": ["NVDA", "AMD", "GOOGL", "DELL"],
            },
            "product_evidence_rows": product_rows,
        },
    )

    distribution = request["prompt_row_distribution"]["by_ticker"]

    assert distribution == {"NVDA": 4, "AMD": 4, "GOOGL": 4, "DELL": 4}


def test_build_product_specialist_request_includes_relationship_summary_for_product_bridge() -> None:
    product_rows = [
        {
            "evidence_ref": f"product_slot::{ticker}::1",
            "source_family": "company_product_evidence_graph",
            "ticker": ticker,
            "product_family": "GPU / Accelerator" if ticker != "DELL" else "AI Server / Rack OEM",
            "product_or_segment": f"{ticker} AI infrastructure product",
            "promotion_status": "runtime_context_taxonomy_only",
            "claim_scope": "product_taxonomy_context",
            "summary": f"{ticker} AI product bounded context.",
        }
        for ticker in ("NVDA", "AMD", "GOOGL", "DELL")
    ]
    request = build_specialist_request_from_state(
        "product_technology_analyst",
        {
            "user_query": "Compare NVDA, AMD, GOOGL, and DELL AI infrastructure products and deployment links.",
            "product_intelligence_runtime_autoload": False,
            "agent_activation_plan": {
                "execution_mode": "deep_research",
                "activate_agents": ["product_technology_analyst"],
            },
            "query_contract": {
                "focus_tickers": ["NVDA", "AMD", "GOOGL", "DELL"],
                "search_scope_tickers": ["NVDA", "AMD", "GOOGL", "DELL"],
            },
            "product_evidence_rows": product_rows,
            "universe_relationship_plan": {
                "relationships": [
                    {
                        "ticker": "NVDA",
                        "related_ticker": "DELL",
                        "relationship_type": "supplier",
                        "source_family": "relationship_graph",
                        "evidence_ref": "rel_nvda_dell_gpu_supply",
                        "summary": "NVIDIA GPU supply to DELL AI servers is bounded relationship context.",
                    },
                    {
                        "ticker": "AMD",
                        "related_ticker": "DELL",
                        "relationship_type": "supplier",
                        "source_family": "relationship_graph",
                        "evidence_refs": ["rel_amd_dell_accelerator_option"],
                        "notes": "AMD accelerator option in DELL server context.",
                    },
                    {
                        "ticker": "DELL",
                        "related_ticker": "GOOGL",
                        "relationship_type": "customer",
                        "source_family": "relationship_graph",
                        "evidence_ref": "rel_dell_googl_cloud_customer",
                        "summary": "DELL server OEM context can be evaluated against cloud customer deployment.",
                    },
                ]
            },
        },
    )

    rel_refs = {row["evidence_ref"] for row in request["relationship_summary"]["relationships"]}
    slot_ids = {slot["slot_id"] for slot in request["required_claim_slots"]}

    assert "product_relationship_deployment_context" in slot_ids
    assert "rel_nvda_dell_gpu_supply" in rel_refs
    assert "rel_amd_dell_accelerator_option" in rel_refs
    assert "rel_dell_googl_cloud_customer" in rel_refs
    assert rel_refs <= set(request["known_evidence_refs"])
    assert request["relationship_summary"]["financial_fact_policy"] == "relationship_graph_hypothesis_only"


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
