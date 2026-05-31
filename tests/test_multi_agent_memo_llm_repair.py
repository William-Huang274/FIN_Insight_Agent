from __future__ import annotations

import json
from typing import Any

from sec_agent.langgraph_orchestrator import build_multi_agent_orchestration_graph, make_multi_agent_smoke_state
from sec_agent.memo_llm import (
    MEMO_ROUTE_SOURCE,
    MEMO_ROUTER_ENV,
    MemoLLMConfig,
    extract_json_object,
    memo_writer_from_env,
    route_memo_writer_llm,
    route_verifier_llm,
    verifier_from_env,
)
from sec_agent.multi_agent_contracts import (
    aggregate_specialist_judgment_plan,
    repair_multi_agent_memo_draft,
    verify_multi_agent_memo_draft,
)


def test_repair_multi_agent_memo_removes_raw_tool_and_bad_claims() -> None:
    judgment = _judgment()
    bad_memo = {
        "answer_status": "draft",
        "direct_answer": "Supported capex claim. Unsupported customer claim.",
        "raw_rows_consumed": True,
        "tool_calls_requested": [{"tool": "sec_search_filings"}],
        "memo_claims": [
            {"claim": "Supported capex claim.", "evidence_refs": ["capex_ref"], "source_families": ["primary_sec_filing"]},
            {"claim": "No refs claim."},
        ],
    }
    verification = verify_multi_agent_memo_draft(bad_memo, judgment)

    repaired = repair_multi_agent_memo_draft(bad_memo, verification, judgment)
    repaired_verification = verify_multi_agent_memo_draft(repaired, judgment)

    assert repaired["raw_rows_consumed"] is False
    assert repaired["tool_calls_requested"] == []
    assert repaired["removed_claims"][0]["reason"] == "missing_evidence_refs"
    assert repaired_verification["status"] == "pass"


def test_graph_verifier_repairs_once_then_reverifies(tmp_path) -> None:
    def injected_specialists(_state: dict) -> dict:
        return {
            "specialist_outputs": [
                {
                    "agent_id": "fundamental_analyst",
                    "observations": [
                        {
                            "claim": "Supported capex claim.",
                            "evidence_refs": ["capex_ref"],
                            "source_families": ["primary_sec_filing"],
                        }
                    ],
                }
            ]
        }

    def bad_memo(_state: dict) -> dict:
        return {
            "memo_answer": {
                "answer_status": "draft",
                "direct_answer": "Supported capex claim.",
                "raw_rows_consumed": True,
                "tool_calls_requested": [{"tool": "sec_search_filings"}],
                "memo_claims": [
                    {"claim": "Supported capex claim.", "evidence_refs": ["capex_ref"], "source_families": ["primary_sec_filing"]}
                ],
            }
        }

    graph = build_multi_agent_orchestration_graph(run_specialist_analysts=injected_specialists, memo_writer=bad_memo)
    result = graph.invoke(
        make_multi_agent_smoke_state(
            user_query="写一段投研 memo，比较 NVDA 和 AMD 的基本面。",
            output_dir=tmp_path,
            query_contract=_query_contract(["NVDA", "AMD"]),
            focus_tickers=["NVDA", "AMD"],
            search_scope_tickers=["NVDA", "AMD"],
        ),
        config={"configurable": {"thread_id": "unit-verifier-repair"}},
    )

    assert result["claim_verification"]["status"] == "pass"
    assert result["claim_verification"]["repair"]["status"] == "pass"
    assert result["memo_answer"]["verifier_repair_attempted"] is True
    assert result["memo_answer"]["tool_calls_requested"] == []


def test_memo_writer_llm_accepts_valid_memo_json() -> None:
    fake = _FakeChat([json.dumps(_memo())])

    result = route_memo_writer_llm(
        _state(),
        config=_config(),
        call_chat_completion=fake,
    )

    assert result["memo_route_result"]["status"] == "pass"
    assert result["memo_route_result"]["finish_reasons"] == ["stop"]
    assert result["memo_answer"]["llm_route_source"] == MEMO_ROUTE_SOURCE
    assert result["memo_answer"]["raw_rows_consumed"] is False
    assert result["memo_answer"]["memo_outline"]
    assert "Memo Writer Skill" in fake.calls[0]["messages"][0]["content"]
    assert "ClaimCard" in fake.calls[0]["messages"][1]["content"]
    assert "memo_outline" in fake.calls[0]["messages"][1]["content"]
    assert "memo_thesis_plan" in fake.calls[0]["messages"][1]["content"]
    assert "memo_writer_data_view" not in fake.calls[0]["messages"][1]["content"]
    assert "memo_writer_v0_4_thesis_led_claim_cards_no_duplicate_data_view" in fake.calls[0]["messages"][1]["content"]
    assert "do_not_emit_supported_claims" in fake.calls[0]["messages"][1]["content"]


def test_memo_writer_llm_flattens_nested_memo_draft_json() -> None:
    fake = _FakeChat([json.dumps({"memo_draft": _memo()})])

    result = route_memo_writer_llm(
        _state(),
        config=_config(),
        call_chat_completion=fake,
    )

    assert result["memo_route_result"]["status"] == "pass"
    assert result["memo_answer"]["direct_answer"] == "Supported capex claim."
    assert "memo_draft" not in result["memo_answer"]


def test_memo_writer_llm_uses_compact_repair_prompt_after_length() -> None:
    fake = _FakeChat(
        [
            {"content": '{"answer_status": "draft", "memo_claims": [', "finish_reason": "length", "output_tokens": 2600},
            json.dumps(_memo()),
        ]
    )

    result = route_memo_writer_llm(
        _state(),
        config=_config(),
        call_chat_completion=fake,
    )

    repair_prompt = fake.calls[1]["messages"][1]["content"]
    assert result["memo_route_result"]["status"] == "pass"
    assert result["memo_route_result"]["repair_attempts"] == 1
    assert "Use this compact input JSON only" in repair_prompt
    assert "memo_writer_data_view" not in repair_prompt
    assert "direct_answer <= 360 characters" in repair_prompt
    assert "unsupported_claims_excluded <= 2" in repair_prompt


def test_memo_writer_prompt_uses_slot_balanced_v0_3_caps() -> None:
    claims = [
        {
            "claim_id": f"claim_{index}",
            "agent_id": "fundamental_analyst",
            "claim": f"Supported claim {index}.",
            "claim_type": "company_reported_financial_fact",
            "memo_slot": ["thesis", "fundamentals", "industry_relationship", "market_valuation", "risk_counterevidence"][index % 5],
            "evidence_refs": [f"ref_{index}"],
            "source_families": ["primary_sec_filing"],
            "materiality": "high",
        }
        for index in range(12)
    ]
    claims[0]["claim_type"] = "investment_thesis_synthesis"
    judgment = {
        "schema_version": "sec_agent_specialist_judgment_plan_v0.1",
        "status": "pass",
        "supported_claims": claims,
        "unsupported_claims": [
            {"agent_id": "risk_counterevidence_analyst", "claim": f"Unsupported {index}", "reason": "missing evidence"}
            for index in range(5)
        ],
        "conflicts": [
            {"agent_id": "risk_counterevidence_analyst", "claim": f"Conflict {index}", "reason": "mixed evidence"}
            for index in range(4)
        ],
        "memo_outline": [
            {"memo_slot": slot, "status": "supported"}
            for slot in ["thesis", "fundamentals", "industry_relationship", "market_valuation", "risk_counterevidence"]
        ],
        "memo_writer_allowed": True,
    }
    fake = _FakeChat(
        [
            json.dumps(
                {
                    "answer_status": "draft",
                    "direct_answer": "Supported claim 0.",
                    "memo_claims": [
                        {
                            "claim_id": "claim_0",
                            "claim": "Supported claim 0.",
                            "claim_type": "investment_thesis_synthesis",
                            "evidence_refs": ["ref_0"],
                            "source_families": ["primary_sec_filing"],
                        }
                    ],
                }
            )
        ]
    )

    result = route_memo_writer_llm(
        {
            "user_query": "Write a memo.",
            "verified_judgment_plan": judgment,
            "specialist_verification": {"memo_writer_allowed": True},
        },
        config=_config(),
        call_chat_completion=fake,
    )

    payload = extract_json_object(fake.calls[0]["messages"][1]["content"]) or {}
    compact = payload["verified_judgment_plan"]
    assert result["memo_route_result"]["status"] == "pass"
    assert len(compact["supported_claims"]) == 5
    assert compact["supported_claims"][0]["claim_type"] == "investment_thesis_synthesis"
    assert len(compact["unsupported_claims"]) == 2
    assert len(compact["conflicts"]) == 2
    assert "memo_thesis_plan" in compact
    assert payload["memo_output_contract"]["memo_claims_max"] == 5


def test_memo_env_router_returns_none_for_mock_mode() -> None:
    assert memo_writer_from_env({MEMO_ROUTER_ENV: "mock"}) is None
    assert verifier_from_env({MEMO_ROUTER_ENV: "mock"}) is None


def test_verifier_llm_cannot_override_deterministic_fail() -> None:
    result = route_verifier_llm(
        {
            **_state(),
            "memo_answer": {
                "answer_status": "draft",
                "raw_rows_consumed": True,
                "memo_claims": [{"claim": "No refs."}],
            },
        },
        config=_config(),
        call_chat_completion=_FakeChat([json.dumps({"status": "pass", "errors": []})]),
    )

    assert result["claim_verification"]["status"] == "fail"
    assert result["claim_verification"]["llm_verifier_skipped"] == "deterministic_gate_failed"


def test_verifier_llm_downgrades_bounded_block_completeness_failure() -> None:
    result = route_verifier_llm(
        {
            **_state(),
            "memo_answer": {
                "answer_status": "blocked_by_specialist_verification",
                "direct_answer": "Evidence constraints blocked full memo generation.",
                "raw_rows_consumed": False,
                "tool_calls_requested": [],
                "memo_claims": [],
                "bounded_answer_allowed": True,
            },
        },
        config=_config(),
        call_chat_completion=_FakeChat([json.dumps({"status": "fail", "errors": [{"type": "insufficient_evidence"}]})]),
    )

    assert result["claim_verification"]["status"] == "pass"
    assert result["claim_verification"]["warnings"][0]["type"] == "bounded_block_verifier_warning_downgraded"


def test_verifier_llm_downgrades_soft_failure_after_deterministic_pass() -> None:
    fake = _FakeChat([json.dumps({"status": "fail", "errors": [{"type": "memo_not_detailed_enough"}]})])
    result = route_verifier_llm(
        _state(),
        config=_config(),
        call_chat_completion=fake,
    )

    assert result["claim_verification"]["status"] == "pass"
    assert any(
        item["type"] == "deterministic_pass_verifier_warning_downgraded"
        for item in result["claim_verification"]["warnings"]
    )
    user_prompt = fake.calls[0]["messages"][1]["content"]
    assert "verified_judgment_inventory" in user_prompt
    assert "verifier_data_view" not in user_prompt
    assert "supported_evidence_refs" in user_prompt


def test_graph_repairs_injected_verifier_failure_once(tmp_path) -> None:
    calls: list[dict[str, Any]] = []

    def injected_specialists(_state: dict) -> dict:
        return {
            "specialist_outputs": [
                {
                    "agent_id": "fundamental_analyst",
                    "observations": [
                        {
                            "claim": "Supported capex claim.",
                            "evidence_refs": ["capex_ref"],
                            "source_families": ["primary_sec_filing"],
                        }
                    ],
                }
            ]
        }

    def injected_verifier(state: dict) -> dict:
        calls.append(dict(state.get("memo_answer") or {}))
        if len(calls) == 1:
            return {
                "claim_verification": {
                    "status": "fail",
                    "errors": [{"type": "memo_claim_without_evidence_refs", "index": 1}],
                    "bounded_answer_allowed": True,
                },
                "specialist_verification": state.get("specialist_verification") or {},
            }
        return {
            "claim_verification": {"status": "pass", "errors": [], "warnings": []},
            "specialist_verification": state.get("specialist_verification") or {},
        }

    graph = build_multi_agent_orchestration_graph(run_specialist_analysts=injected_specialists, verifier=injected_verifier)
    result = graph.invoke(
        make_multi_agent_smoke_state(
            user_query="写一段投研 memo，比较 NVDA 和 AMD 的基本面。",
            output_dir=tmp_path,
            query_contract=_query_contract(["NVDA", "AMD"]),
            focus_tickers=["NVDA", "AMD"],
            search_scope_tickers=["NVDA", "AMD"],
        ),
        config={"configurable": {"thread_id": "unit-injected-verifier-repair"}},
    )

    assert len(calls) == 2
    assert result["claim_verification"]["status"] == "pass"
    assert result["claim_verification"]["repair"]["status"] == "pass"


def test_extract_json_object_accepts_fenced_json() -> None:
    payload = {"status": "pass"}
    assert extract_json_object(f"```json\n{json.dumps(payload)}\n```") == payload


class _FakeChat:
    def __init__(self, responses: list[Any]) -> None:
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    def __call__(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        response = self.responses[min(len(self.calls) - 1, len(self.responses) - 1)]
        content = str(response.get("content") if isinstance(response, dict) else response or "")
        tool_calls = response.get("tool_calls") if isinstance(response, dict) else []
        finish_reason = str(response.get("finish_reason") or "stop") if isinstance(response, dict) else "stop"
        output_tokens = int(response.get("output_tokens") or 20) if isinstance(response, dict) else 20
        return {
            "status": "ok",
            "provider": kwargs["llm_backend"],
            "model": kwargs["model"],
            "role": kwargs["role"],
            "profile": kwargs["profile"],
            "content": content,
            "message": {"content": content, "tool_calls": tool_calls},
            "tool_calls": tool_calls or [],
            "finish_reason": finish_reason,
            "latency_ms": 1,
            "input_tokens": 10,
            "output_tokens": output_tokens,
            "total_tokens": 10 + output_tokens,
            "failure_reason": "",
            "raw_response": {},
        }


def _config() -> MemoLLMConfig:
    return MemoLLMConfig(
        llm_backend="unit",
        base_url="http://unit.test",
        chat_completions_path="/chat/completions",
        model="unit-model",
        api_key_env="UNIT_API_KEY",
    )


def _state() -> dict[str, Any]:
    judgment = _judgment_without_unsupported()
    memo = _memo()
    memo["memo_thesis_plan"] = judgment["memo_thesis_plan"]
    memo["memo_generation_policy"] = "thesis_led_claim_cards_v0_1"
    return {
        "user_query": "Write a memo.",
        "verified_judgment_plan": judgment,
        "judgment_plan": judgment,
        "specialist_verification": {"memo_writer_allowed": True},
        "memo_answer": memo,
    }


def _judgment() -> dict[str, Any]:
    return aggregate_specialist_judgment_plan(
        [
            {
                "agent_id": "fundamental_analyst",
                "observations": [
                    {
                        "claim": "Supported capex claim.",
                        "evidence_refs": ["capex_ref"],
                        "source_families": ["primary_sec_filing"],
                    }
                ],
                "unsupported_claims": [{"claim": "Unsupported customer claim.", "reason": "not in bounded evidence"}],
            }
        ]
    )


def _judgment_without_unsupported() -> dict[str, Any]:
    return aggregate_specialist_judgment_plan(
        [
            {
                "agent_id": "fundamental_analyst",
                "observations": [
                    {
                        "claim": "Supported capex claim.",
                        "evidence_refs": ["capex_ref"],
                        "source_families": ["primary_sec_filing"],
                    }
                ],
            }
        ]
    )


def _memo() -> dict[str, Any]:
    return {
        "answer_status": "draft",
        "direct_answer": "Supported capex claim.",
        "memo_claims": [
            {"claim": "Supported capex claim.", "evidence_refs": ["capex_ref"], "source_families": ["primary_sec_filing"]}
        ],
    }


def _query_contract(tickers: list[str]) -> dict[str, Any]:
    return {
        "task_type": "open_analysis",
        "search_scope_tickers": tickers,
        "focus_tickers": tickers,
        "years": [2026],
        "filing_types": ["10-Q"],
        "source_tiers": ["primary_sec_filing"],
        "metric_families": ["capex"],
    }
