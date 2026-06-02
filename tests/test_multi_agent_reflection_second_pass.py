from __future__ import annotations

from sec_agent.multi_agent_runtime import (
    compile_second_pass_retrieval_plan,
    normalize_reflection_report,
    quality_reflection_report_from_judgment,
    record_second_pass_outcome,
    reflection_report_from_coverage,
    reflection_report_from_tool_observations,
    second_pass_evidence_requirement_plan_from_reflection,
    should_execute_second_pass,
)
from sec_agent.tool_call_ledger import (
    LOOP_BREAK_NO_INCREMENTAL_EVIDENCE,
    LOOP_BREAK_SECOND_PASS_BUDGET_EXHAUSTED,
    LoopBudget,
    ToolCallLedger,
)


def test_reflection_report_triggers_second_pass_for_searchable_gap() -> None:
    report = reflection_report_from_coverage(
        {
            "summary": {"coverage_complete": False, "primary_task_support_complete": False},
            "tasks": [
                {
                    "task_id": "amd_capex",
                    "support_level": "insufficient",
                    "missing_focus_tickers": ["AMD"],
                    "missing_years": [2026],
                    "missing_filing_types": ["10-Q"],
                    "missing_source_tiers": ["primary_sec_filing"],
                    "missing_metric_families": ["capex"],
                }
            ],
        },
        source_available=True,
    )
    decision = should_execute_second_pass(report, ToolCallLedger())

    assert report["sufficiency_level"] == "partial"
    assert report["second_pass_requests"][0]["tickers"] == ["AMD"]
    assert decision["allowed"] is True
    assert decision["request_count"] == 1


def test_reflection_binds_gap_to_evidence_requirement_source_and_operator() -> None:
    report = reflection_report_from_coverage(
        _coverage_gap(),
        source_available=True,
        evidence_requirement_plan=_evidence_requirement_plan(),
        tool_ledger_summary={"tool_call_count": 2, "second_pass_rounds": 0},
    )

    missing = report["missing_requirements"][0]
    request = report["second_pass_requests"][0]

    assert report["source_available"] is True
    assert missing["requirement_id"] == "req_amd_capex"
    assert missing["source_family_gaps"] == ["primary_sec_filing"]
    assert missing["operator_owners"] == ["sec_operator"]
    assert request["parent_requirement_id"] == "req_amd_capex"
    assert request["source_family_gaps"] == ["primary_sec_filing"]
    assert request["evidence_routes"] == ["ledger_first", "filing_text"]
    assert request["compile_policy"] == "deterministic_compiler_required"
    assert report["tool_ledger_summary"]["tool_call_count"] == 2


def test_tool_observation_reflection_triggers_second_pass_without_coverage_matrix() -> None:
    report = reflection_report_from_tool_observations(
        {
            "routes": [
                {
                    "route_id": "route_req_amd_capex_filing",
                    "retrieval_route": "filing_text",
                    "evidence_requirement_id": "req_amd_capex",
                    "task_id": "amd_capex",
                }
            ]
        },
        evidence_requirement_plan=_evidence_requirement_plan(),
        tool_observations=[
            {
                "route_id": "route_req_amd_capex_filing",
                "retrieval_route": "filing_text",
                "status": "ok",
                "row_count": 0,
            }
        ],
        tool_ledger_summary={"tool_call_count": 1, "second_pass_rounds": 0},
    )
    decision = should_execute_second_pass(report, ToolCallLedger())

    assert report["trigger"] == "coverage_reflection_tool_observations"
    assert report["sufficiency_level"] == "partial"
    assert report["missing_requirements"][0]["requirement_id"] == "req_amd_capex"
    assert report["second_pass_requests"][0]["evidence_routes"] == ["ledger_first", "filing_text"]
    assert decision["allowed"] is True


def test_tool_observation_reflection_marks_permission_block_as_not_retriable() -> None:
    report = reflection_report_from_tool_observations(
        {
            "routes": [
                {
                    "route_id": "route_rel",
                    "retrieval_route": "relationship_graph",
                    "evidence_requirement_id": "req_rel",
                    "task_id": "relationship_scope",
                }
            ]
        },
        evidence_requirement_plan={
            "requirements": [
                {
                    "requirement_id": "req_rel",
                    "task_id": "relationship_scope",
                    "priority": "supporting",
                    "source_families": ["relationship_graph"],
                    "evidence_routes": ["relationship_graph"],
                }
            ]
        },
        tool_observations=[
            {
                "route_id": "route_rel",
                "retrieval_route": "relationship_graph",
                "status": "blocked",
                "error": "agent_not_bounded_execute:universe_relationship",
                "row_count": 0,
            }
        ],
    )
    decision = should_execute_second_pass(report, ToolCallLedger())

    assert report["sufficiency_level"] == "insufficient"
    assert report["source_available"] is False
    assert report["second_pass_requests"] == []
    assert decision["reason"] == "source_not_available"


def test_second_pass_requests_compile_through_deterministic_retrieval_plan() -> None:
    report = reflection_report_from_coverage(
        _coverage_gap(),
        source_available=True,
        evidence_requirement_plan=_evidence_requirement_plan(),
    )

    second_pass_plan = second_pass_evidence_requirement_plan_from_reflection(report, _evidence_requirement_plan())
    retrieval_plan = compile_second_pass_retrieval_plan(
        report,
        _evidence_requirement_plan(),
        query_contract=_query_contract(),
        case={"case_id": "unit_second_pass", "prompt": "AMD capex?", "companies": ["AMD"], "years": [2026]},
    )

    route_names = {route["retrieval_route"] for route in retrieval_plan["routes"]}
    requirement_ids = {route["evidence_requirement_id"] for route in retrieval_plan["routes"]}

    assert second_pass_plan["multi_agent_evidence_requirement_validation"]["status"] == "pass"
    assert second_pass_plan["requirements"][0]["parent_requirement_id"] == "req_amd_capex"
    assert route_names == {"ledger_first", "filing_text"}
    assert requirement_ids == {"req_amd_capex_second_pass_1"}
    assert retrieval_plan["second_pass_evidence_requirement_plan"]["source"] == "reflection_second_pass_requests"


def test_second_pass_compiler_overrides_stale_query_contract_requirements() -> None:
    report = reflection_report_from_coverage(
        _coverage_gap(),
        source_available=True,
        evidence_requirement_plan=_evidence_requirement_plan(),
    )
    stale_contract = {
        **_query_contract(),
        "evidence_requirements": [
            {
                "requirement_id": "stale_market_req",
                "task_id": "stale_market",
                "tickers": ["AMD"],
                "source_families": ["market_snapshot"],
                "evidence_routes": ["market_snapshot"],
            }
        ],
    }

    retrieval_plan = compile_second_pass_retrieval_plan(
        report,
        _evidence_requirement_plan(),
        query_contract=stale_contract,
        case={"case_id": "unit_second_pass", "prompt": "AMD capex?", "companies": ["AMD"], "years": [2026]},
    )

    route_names = {route["retrieval_route"] for route in retrieval_plan["routes"]}
    requirement_ids = {route["evidence_requirement_id"] for route in retrieval_plan["routes"]}
    assert route_names == {"ledger_first", "filing_text"}
    assert requirement_ids == {"req_amd_capex_second_pass_1"}


def test_second_pass_compiler_caps_routes_by_remaining_total_tool_budget() -> None:
    report = reflection_report_from_coverage(
        _coverage_gap(),
        source_available=True,
        evidence_requirement_plan=_evidence_requirement_plan(),
    )

    retrieval_plan = compile_second_pass_retrieval_plan(
        report,
        _evidence_requirement_plan(),
        query_contract=_query_contract(),
        case={"case_id": "unit_second_pass", "prompt": "AMD capex?", "companies": ["AMD"], "years": [2026]},
        activation_plan={"max_tool_calls_total": 12},
        used_tool_calls_total=11,
    )

    pruning = retrieval_plan["route_budget_pruning"]
    assert len(retrieval_plan["routes"]) == 1
    assert pruning["used_tool_calls_total"] == 11
    assert pruning["remaining_tool_calls_total"] == 1
    assert pruning["dropped_route_count"] == 1
    assert pruning["dropped_routes"][0]["reason"] == "max_tool_calls_total"


def test_unavailable_source_family_blocks_second_pass_before_compiler() -> None:
    ledger = ToolCallLedger()
    report = reflection_report_from_coverage(
        _coverage_gap(),
        source_available=True,
        evidence_requirement_plan=_evidence_requirement_plan(),
        available_source_families={"market_snapshot"},
    )

    decision = should_execute_second_pass(report, ledger)

    assert report["source_available"] is False
    assert report["second_pass_requests"] == []
    assert report["needs_user_clarification"] is True
    assert decision["allowed"] is False
    assert decision["reason"] == "source_not_available"


def test_source_unavailable_does_not_trigger_tool_call_and_allows_bounded_answer() -> None:
    ledger = ToolCallLedger()
    report = normalize_reflection_report(
        {
            "sufficiency_level": "insufficient",
            "source_available": False,
            "second_pass_requests": [{"request_id": "r1"}],
        }
    )

    decision = should_execute_second_pass(report, ledger)

    assert decision["allowed"] is False
    assert decision["reason"] == "source_not_available"
    assert decision["bounded_answer_allowed"] is True
    assert ledger.bounded_answer_allowed is True


def test_second_pass_budget_exhaustion_blocks_more_retrieval() -> None:
    ledger = ToolCallLedger(budget=LoopBudget(max_second_pass_rounds=0))
    report = normalize_reflection_report(
        {
            "sufficiency_level": "partial",
            "source_available": True,
            "second_pass_requests": [{"request_id": "r1"}],
        }
    )

    decision = should_execute_second_pass(report, ledger)

    assert decision["allowed"] is False
    assert decision["reason"] == LOOP_BREAK_SECOND_PASS_BUDGET_EXHAUSTED


def test_second_pass_no_gain_sets_loop_break_and_bounded_answer() -> None:
    ledger = ToolCallLedger()

    outcome = record_second_pass_outcome(ledger, added_row_count=0, coverage_delta={"closed_gaps": 0})

    assert outcome["loop_break_reason"] == LOOP_BREAK_NO_INCREMENTAL_EVIDENCE
    assert outcome["bounded_answer_allowed"] is True
    assert ledger.loop_break_reason == LOOP_BREAK_NO_INCREMENTAL_EVIDENCE


def test_second_pass_with_coverage_delta_continues() -> None:
    ledger = ToolCallLedger()

    outcome = record_second_pass_outcome(ledger, added_row_count=0, coverage_delta={"closed_gaps": 1})

    assert outcome["loop_break_reason"] == ""
    assert outcome["bounded_answer_allowed"] is False


def test_quality_reflection_triggers_second_pass_for_missing_deep_research_claim_cards() -> None:
    report = quality_reflection_report_from_judgment(
        {
            "supported_claims": [
                {
                    "claim": "AMD capex has support.",
                    "ticker_scope": ["AMD"],
                    "evidence_refs": ["amd_ref"],
                    "source_families": ["primary_sec_filing"],
                }
            ]
        },
        state={
            "agent_activation_plan": {"execution_mode": "deep_research"},
            "specialist_outputs": [{"agent_id": "fundamental_analyst", "status": "pass"}],
            "runtime_ledger_rows": [{"evidence_ref": "amd_ref"}],
        },
        evidence_requirement_plan={
            **_evidence_requirement_plan(),
            "scope": {
                "focus_tickers": ["AMD", "NVDA"],
                "search_scope_tickers": ["AMD", "NVDA"],
                "years": [2026],
                "filing_types": ["10-Q"],
                "source_tiers": ["primary_sec_filing"],
                "metric_families": ["capex"],
            },
        },
    )
    decision = should_execute_second_pass(report, ToolCallLedger())

    assert report["trigger"] == "quality_second_pass"
    assert report["second_pass_requests"]
    assert report["quality_gaps"][0]["quality_gap_type"] == "missing_required_ticker_claim_card"
    assert report["second_pass_requests"][0]["tickers"] == ["NVDA"]
    assert decision["allowed"] is True
    assert decision["trigger"] == "quality_second_pass"


def test_quality_reflection_skips_stubbed_specialists() -> None:
    report = quality_reflection_report_from_judgment(
        {"supported_claims": []},
        state={
            "agent_activation_plan": {"execution_mode": "deep_research"},
            "specialist_outputs": [{"agent_id": "fundamental_analyst", "status": "stubbed"}],
        },
        evidence_requirement_plan=_evidence_requirement_plan(),
    )

    assert report["sufficiency_level"] == "sufficient"
    assert report["second_pass_requests"] == []


def test_quality_reflection_ignores_source_gaps_without_executable_routes() -> None:
    report = quality_reflection_report_from_judgment(
        {
            "supported_claims": [
                {
                    "claim": "Supported claim.",
                    "ticker_scope": ["AMD"],
                    "evidence_refs": ["ref_1"],
                    "source_families": ["primary_sec_filing"],
                }
            ]
        },
        state={
            "agent_activation_plan": {"execution_mode": "deep_research"},
            "specialist_outputs": [{"agent_id": "fundamental_analyst", "status": "pass"}],
            "runtime_ledger_rows": [{"evidence_ref": "ref_1"}],
        },
        evidence_requirement_plan=_evidence_requirement_plan(),
        source_gaps=[{"source_family": "external_private_feed", "reason": "diagnostic_gap"}],
    )

    assert report["sufficiency_level"] == "sufficient"
    assert report["second_pass_requests"] == []


def _coverage_gap() -> dict:
    return {
        "summary": {"coverage_complete": False, "primary_task_support_complete": False},
        "tasks": [
            {
                "task_id": "amd_capex",
                "question_zh": "Need AMD reported capex.",
                "priority": "primary",
                "support_level": "insufficient",
                "missing_tickers": ["AMD"],
                "missing_years": [2026],
                "missing_filing_types": ["10-Q"],
                "missing_source_tiers": ["primary_sec_filing"],
                "missing_metric_families": ["capex"],
            }
        ],
    }


def _evidence_requirement_plan() -> dict:
    return {
        "schema_version": "sec_agent_evidence_requirement_plan_v0.1",
        "case_id": "unit_second_pass",
        "scope": {
            "focus_tickers": ["AMD"],
            "search_scope_tickers": ["AMD"],
            "years": [2026],
            "filing_types": ["10-Q"],
            "source_tiers": ["primary_sec_filing"],
        },
        "requirements": [
            {
                "requirement_id": "req_amd_capex",
                "task_id": "amd_capex",
                "question": "Need AMD reported capex from filings.",
                "priority": "primary",
                "analysis_intent": "reported_financial_fact",
                "tickers": ["AMD"],
                "years": [2026],
                "filing_types": ["10-Q"],
                "source_tiers": ["primary_sec_filing"],
                "metric_families": ["capex"],
                "period_roles": ["QTD"],
                "evidence_routes": ["ledger_first", "filing_text"],
            }
        ],
    }


def _query_contract() -> dict:
    return {
        "focus_tickers": ["AMD"],
        "search_scope_tickers": ["AMD"],
        "years": [2026],
        "filing_types": ["10-Q"],
        "source_tiers": ["primary_sec_filing"],
        "metric_families": ["capex"],
    }
