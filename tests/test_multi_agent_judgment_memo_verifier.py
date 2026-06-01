from __future__ import annotations

from sec_agent.multi_agent_contracts import (
    aggregate_specialist_judgment_plan,
    build_multi_agent_memo_draft,
    verify_multi_agent_memo_draft,
    verify_specialist_outputs_for_memo,
)
from sec_agent.langgraph_orchestrator import _node_multi_agent_renderer, build_multi_agent_orchestration_graph, make_multi_agent_smoke_state


def test_judgment_plan_carries_boundaries_and_excludes_unsupported_claims() -> None:
    judgment = aggregate_specialist_judgment_plan(
        [
            {
                "agent_id": "fundamental_analyst",
                "observations": [
                    {
                        "claim": "AMD capex is supported by the filing row.",
                        "claim_type": "reported_financial_fact",
                        "evidence_refs": ["amd_capex_ref"],
                        "source_families": ["primary_sec_filing"],
                        "confidence": "high",
                    }
                ],
            },
            {
                "agent_id": "risk_counterevidence_analyst",
                "unsupported_claims": [{"claim": "A named customer shifted orders.", "reason": "not in bounded evidence"}],
                "conflicts": [{"claim": "Management caveats demand visibility.", "reason": "8-K commentary"}],
            },
        ],
        reflection_report={
            "bounded_answer_allowed": True,
            "missing_requirements": [{"requirement_id": "req_backlog", "source_family_gaps": ["company_authored_unaudited_sec_filing"]}],
        },
        evidence_requirement_plan={
            "requirements": [{"requirement_id": "req_capex", "source_families": ["primary_sec_filing"]}]
        },
        tool_ledger_summary={"tool_call_count": 2},
    )

    assert judgment["memo_writer_allowed"] is True
    assert judgment["memo_constraints"]["blocked_reasons"] == []
    assert "exclude_unsupported_specialist_claims_and_render_as_limitations" in judgment["memo_constraints"]["required_caveats"]
    assert judgment["memo_constraints"]["forbidden_inputs"] == ["raw_rows", "physical_paths", "tool_calls", "retrieval_requests"]
    assert len(judgment["unsupported_claims"]) == 1
    assert len(judgment["conflicts"]) == 1
    assert {item["source_family"] for item in judgment["source_boundary_notes"]} >= {"primary_sec_filing", "coverage_gap"}


def test_memo_writer_consumes_verified_plan_and_blocks_when_not_allowed() -> None:
    judgment = aggregate_specialist_judgment_plan(
        [
            {
                "agent_id": "risk_counterevidence_analyst",
                "unsupported_claims": [{"claim": "Unsupported customer claim", "reason": "not in bounded evidence"}],
            }
        ]
    )
    verification = verify_specialist_outputs_for_memo([], judgment_plan=judgment)

    memo = build_multi_agent_memo_draft(judgment, specialist_verification=verification)

    assert memo["answer_status"] == "blocked_by_specialist_verification"
    assert memo["consumed_input_views"] == ["verified_judgment_plan", "verified_summary"]
    assert memo["raw_rows_consumed"] is False
    assert memo["tool_calls_requested"] == []
    assert "Unsupported customer claim" not in memo["direct_answer"]


def test_memo_writer_preserves_counterevidence_and_missing_evidence_when_allowed() -> None:
    judgment = aggregate_specialist_judgment_plan(
        [
            {
                "agent_id": "fundamental_analyst",
                "observations": [
                    {
                        "claim": "NVDA revenue growth is supported by filed company evidence.",
                        "claim_type": "reported_financial_fact",
                        "evidence_refs": ["nvda_revenue_ref"],
                        "source_families": ["primary_sec_filing"],
                        "confidence": "high",
                    }
                ],
            },
            {
                "agent_id": "risk_counterevidence_analyst",
                "conflicts": [{"claim": "Risk factors still cite demand uncertainty.", "reason": "risk text"}],
            },
        ],
        reflection_report={"missing_requirements": [{"requirement_id": "req_margin", "task_id": "margin"}]},
    )
    verification = verify_specialist_outputs_for_memo([], judgment_plan=judgment)

    memo = build_multi_agent_memo_draft(judgment, specialist_verification=verification)

    assert memo["answer_status"] == "draft"
    assert memo["memo_claims"][0]["evidence_refs"] == ["nvda_revenue_ref"]
    assert memo["counterevidence"][0]["claim"] == "Risk factors still cite demand uncertainty."
    assert memo["missing_evidence"][0]["requirement_id"] == "req_margin"
    assert memo["source_boundary"]


def test_memo_writer_allows_supported_claims_while_excluding_unsupported_claims() -> None:
    judgment = aggregate_specialist_judgment_plan(
        [
            {
                "agent_id": "fundamental_analyst",
                "observations": [
                    {
                        "claim": "NVDA reported demand strength in filed evidence.",
                        "claim_type": "reported_financial_fact",
                        "evidence_refs": ["nvda_demand_ref"],
                        "source_families": ["primary_sec_filing"],
                        "confidence": "high",
                    }
                ],
            },
            {
                "agent_id": "risk_counterevidence_analyst",
                "unsupported_claims": [{"claim": "A named customer shifted orders.", "reason": "not in bounded evidence"}],
            },
        ]
    )
    verification = verify_specialist_outputs_for_memo([], judgment_plan=judgment)

    memo = build_multi_agent_memo_draft(judgment, specialist_verification=verification)

    assert verification["status"] == "pass"
    assert verification["memo_writer_allowed"] is True
    assert memo["answer_status"] == "draft"
    assert memo["memo_claims"][0]["claim"] == "NVDA reported demand strength in filed evidence."
    assert memo["unsupported_claims_excluded"][0]["claim"] == "A named customer shifted orders."
    assert any(item["type"] == "unsupported_excluded" for item in memo["caveats"])


def test_failed_specialist_is_rendered_as_partial_scope_caveat() -> None:
    judgment = aggregate_specialist_judgment_plan(
        [
            {
                "agent_id": "fundamental_analyst",
                "observations": [
                    {
                        "claim": "JPM revenue growth is supported by filed evidence.",
                        "claim_type": "reported_financial_fact",
                        "evidence_refs": ["jpm_revenue_ref"],
                        "source_families": ["primary_sec_filing"],
                        "confidence": "high",
                    }
                ],
            },
            {
                "agent_id": "industry_supply_chain_analyst",
                "status": "blocked",
                "summary": "Specialist route failed closed.",
                "unsupported_claims": [
                    {
                        "type": "specialist_route_failed",
                        "claim": "industry_supply_chain_analyst did not produce accepted specialist output; do not present this lens as fully analyzed.",
                        "reason": "provider_error: transient failure",
                    }
                ],
                "metadata": {"route_failure": True},
            },
        ]
    )
    verification = verify_specialist_outputs_for_memo([], judgment_plan=judgment)

    memo = build_multi_agent_memo_draft(judgment, specialist_verification=verification)

    assert verification["status"] == "pass"
    assert judgment["memo_writer_allowed"] is True
    assert judgment["blocked_specialist_agents"] == ["industry_supply_chain_analyst"]
    assert "state_failed_specialist_and_partial_scope" in judgment["memo_constraints"]["required_caveats"]
    assert any(item["type"] == "specialist_route_failed" for item in memo["caveats"])
    assert memo["answer_status"] == "draft"


def test_verifier_blocks_unsupported_claim_text_and_raw_or_tool_access() -> None:
    judgment = aggregate_specialist_judgment_plan(
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
                "unsupported_claims": [{"claim": "Unsupported customer claim", "reason": "not in bounded evidence"}],
            }
        ]
    )
    bad_memo = {
        "answer_status": "draft",
        "direct_answer": "Unsupported customer claim",
        "raw_rows_consumed": True,
        "tool_calls_requested": [{"tool": "sec_search_filings"}],
        "memo_claims": [{"claim": "Supported capex claim.", "evidence_refs": ["capex_ref"], "source_families": ["primary_sec_filing"]}],
    }

    result = verify_multi_agent_memo_draft(bad_memo, judgment)
    error_types = {item["type"] for item in result["errors"]}

    assert result["status"] == "fail"
    assert "unsupported_claim_entered_memo" in error_types
    assert "memo_writer_raw_rows_forbidden" in error_types
    assert "memo_writer_tool_calls_forbidden" in error_types
    assert result["repair_instruction"]


def test_verifier_blocks_context_source_as_company_financial_fact() -> None:
    judgment = aggregate_specialist_judgment_plan(
        [
            {
                "agent_id": "market_valuation_analyst",
                "observations": [
                    {
                        "claim": "Market reaction was positive.",
                        "claim_type": "market_or_valuation_context",
                        "evidence_refs": ["market_ref"],
                        "source_families": ["market_snapshot"],
                    }
                ],
            }
        ]
    )
    bad_memo = {
        "answer_status": "draft",
        "memo_claims": [
            {
                "claim": "Company reported revenue grew.",
                "claim_type": "reported_financial_fact",
                "evidence_refs": ["market_ref"],
                "source_families": ["market_snapshot"],
            }
        ],
    }

    result = verify_multi_agent_memo_draft(bad_memo, judgment)
    error_types = {item["type"] for item in result["errors"]}

    assert result["status"] == "fail"
    assert "context_source_used_as_reported_financial_fact" in error_types
    assert "market_claim_missing_as_of_date" in error_types


def test_verifier_blocks_draft_that_drops_thesis_led_contract() -> None:
    judgment = aggregate_specialist_judgment_plan(
        [
            {
                "agent_id": "fundamental_analyst",
                "observations": [
                    {
                        "claim": "NVDA revenue evidence supports upside because reported growth strengthens the thesis.",
                        "claim_type": "reported_financial_fact",
                        "ticker_scope": ["NVDA"],
                        "metric_scope": ["revenue"],
                        "memo_slot": "fundamentals",
                        "materiality": "high",
                        "direction": "positive",
                        "evidence_refs": ["nvda_revenue_ref"],
                        "source_families": ["primary_sec_filing"],
                        "confidence": "high",
                    }
                ],
            }
        ]
    )
    bad_memo = {
        "answer_status": "draft",
        "direct_answer": "NVDA revenue evidence supports upside.",
        "memo_claims": [
            {
                "claim": "NVDA revenue evidence supports upside because reported growth strengthens the thesis.",
                "claim_type": "reported_financial_fact",
                "evidence_refs": ["nvda_revenue_ref"],
                "source_families": ["primary_sec_filing"],
            }
        ],
    }

    result = verify_multi_agent_memo_draft(bad_memo, judgment)
    error_types = {item["type"] for item in result["errors"]}

    assert result["status"] == "fail"
    assert "memo_writer_did_not_carry_memo_thesis_plan" in error_types
    assert "memo_generation_policy_not_thesis_led" in error_types


def test_renderer_keeps_verified_draft_memo_surface_when_bounded() -> None:
    result = _node_multi_agent_renderer(
        {
            "bounded_answer_allowed": True,
            "claim_verification": {"status": "pass"},
            "memo_answer": {
                "answer_status": "draft",
                "direct_answer": "Thesis-led memo answer.",
                "memo_claims": [{"claim": "Supported claim.", "evidence_refs": ["ref_1"]}],
                "source_boundary": "verified judgment plan only",
            },
        }
    )

    assert result["rendered_answer"].startswith("Thesis-led memo answer.")
    assert "Bounded evidence note" in result["rendered_answer"]
    assert not result["rendered_answer"].startswith("Bounded answer only")


def test_graph_step13_keeps_verified_plan_and_verifier_constraints(tmp_path) -> None:
    def injected_specialists(_state: dict) -> dict:
        return {
            "specialist_outputs": [
                {
                    "agent_id": "fundamental_analyst",
                    "observations": [
                        {
                            "claim": "NVDA capex is supported by filed evidence.",
                            "claim_type": "reported_financial_fact",
                            "evidence_refs": ["nvda_capex_ref"],
                            "source_families": ["primary_sec_filing"],
                        }
                    ],
                },
                {
                    "agent_id": "risk_counterevidence_analyst",
                    "conflicts": [{"claim": "Risk factors cite demand uncertainty.", "reason": "risk text"}],
                },
            ]
        }

    graph = build_multi_agent_orchestration_graph(run_specialist_analysts=injected_specialists)
    result = graph.invoke(
        make_multi_agent_smoke_state(
            user_query="写一段投研 memo，比较 NVDA 和 AMD 的基本面、管理层解释、市场反应和估值分歧。",
            output_dir=tmp_path,
            query_contract=_query_contract(["NVDA", "AMD"], source_tiers=["primary_sec_filing", "company_authored_unaudited_sec_filing", "market_snapshot"]),
            focus_tickers=["NVDA", "AMD"],
            search_scope_tickers=["NVDA", "AMD"],
        ),
        config={"configurable": {"thread_id": "unit-step13-verified-plan"}},
    )

    assert result["judgment_plan"]["memo_writer_allowed"] is True
    assert result["verified_judgment_plan"]["conflicts"][0]["claim"] == "Risk factors cite demand uncertainty."
    assert result["memo_answer"]["consumed_input_views"] == ["verified_judgment_plan", "verified_summary"]
    assert result["memo_answer"]["raw_rows_consumed"] is False
    assert result["claim_verification"]["status"] == "pass"
    assert "NVDA capex is supported" in result["rendered_answer"]


def test_graph_verifier_blocks_injected_memo_writer_violation(tmp_path) -> None:
    def injected_memo(_state: dict) -> dict:
        return {
            "memo_answer": {
                "answer_status": "draft",
                "direct_answer": "A raw unsupported claim was included.",
                "raw_rows_consumed": True,
                "tool_calls_requested": [{"tool": "sec_search_filings"}],
                "memo_claims": [{"claim": "No evidence refs."}],
            }
        }

    graph = build_multi_agent_orchestration_graph(memo_writer=injected_memo)
    result = graph.invoke(
        make_multi_agent_smoke_state(
            user_query="写一段投研 memo，比较 NVDA 和 AMD 的基本面、管理层解释、市场反应和估值分歧。",
            output_dir=tmp_path,
            query_contract=_query_contract(["NVDA", "AMD"], source_tiers=["primary_sec_filing", "company_authored_unaudited_sec_filing", "market_snapshot"]),
            focus_tickers=["NVDA", "AMD"],
            search_scope_tickers=["NVDA", "AMD"],
        ),
        config={"configurable": {"thread_id": "unit-step13-verifier-blocks"}},
    )

    repair = result["claim_verification"].get("repair") or {}
    error_types = {item["type"] for item in repair.get("previous_errors") or []}

    assert result["claim_verification"]["status"] == "pass"
    assert repair["status"] == "pass"
    assert "memo_writer_raw_rows_forbidden" in error_types
    assert "memo_writer_tool_calls_forbidden" in error_types
    assert result["memo_answer"]["answer_status"] == "blocked_by_verifier_repair"
    assert result["bounded_answer_allowed"] is True
    assert result["rendered_answer"].startswith("Bounded answer only")


def _query_contract(tickers: list[str], *, source_tiers: list[str] | None = None) -> dict:
    return {
        "task_type": "open_analysis",
        "search_scope_tickers": tickers,
        "focus_tickers": tickers,
        "years": [2026],
        "filing_types": ["10-Q", "8-K"],
        "source_tiers": source_tiers or ["primary_sec_filing"],
        "metric_families": ["capex"],
        "decomposed_tasks": [
            {
                "task_id": "unit_task",
                "question_zh": "unit task",
                "priority": "primary",
                "required_tickers": tickers,
                "required_metric_families": ["capex"],
            }
        ],
    }
