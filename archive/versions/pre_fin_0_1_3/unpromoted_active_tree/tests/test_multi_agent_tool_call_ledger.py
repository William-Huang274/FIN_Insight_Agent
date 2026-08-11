from __future__ import annotations

from sec_agent.tool_call_ledger import (
    LOOP_BREAK_AGENT_TOOL_BUDGET_EXHAUSTED,
    LOOP_BREAK_DUPLICATE_TOOL_CALL,
    LOOP_BREAK_GRAPH_STEP_BUDGET_EXHAUSTED,
    LOOP_BREAK_NO_INCREMENTAL_EVIDENCE,
    LOOP_BREAK_REPAIR_NO_PROGRESS,
    LOOP_BREAK_SECOND_PASS_BUDGET_EXHAUSTED,
    LOOP_BREAK_TOOL_BUDGET_EXHAUSTED,
    LoopBudget,
    ToolCallLedger,
    ToolCallRecord,
    normalize_tool_arguments,
    stable_tool_arguments_digest,
)


def test_stable_digest_ignores_volatile_fields_and_normalizes_tickers() -> None:
    digest_a = stable_tool_arguments_digest(
        "sec_search_filings",
        {
            "tickers": ["msft", "NVDA", "msft"],
            "years": ["2026", 2025],
            "output_dir": "eval/run_a",
            "run_id": "run_a",
            "query": "capex trend",
        },
    )
    digest_b = stable_tool_arguments_digest(
        "sec_search_filings",
        {
            "query": "capex trend",
            "years": [2025, 2026],
            "tickers": ["NVDA", "MSFT"],
            "output_dir": "eval/run_b",
            "timestamp": "2026-05-30T00:00:00Z",
        },
    )

    assert digest_a == digest_b
    assert digest_a.startswith("sha256:")
    assert normalize_tool_arguments({"tickers": ["msft", "NVDA"], "output_root": "tmp"}) == {
        "tickers": ["MSFT", "NVDA"]
    }


def test_same_tool_same_args_duplicate_is_blocked() -> None:
    ledger = ToolCallLedger(budget=LoopBudget(max_same_tool_same_args=1))
    args = {"tickers": ["MSFT"], "years": [2026], "query": "capex"}
    first = ledger.can_call_tool(turn_id="turn_1", agent_id="sec_operator", tool_name="sec_search_filings", arguments=args)
    assert first["allowed"] is True
    ledger.record_tool_call(
        turn_id="turn_1",
        agent_id="sec_operator",
        tool_name="sec_search_filings",
        arguments=args,
        row_count=3,
    )

    second = ledger.can_call_tool(turn_id="turn_1", agent_id="sec_operator", tool_name="sec_search_filings", arguments=args)

    assert second["allowed"] is False
    assert second["reason"] == LOOP_BREAK_DUPLICATE_TOOL_CALL
    assert ledger.loop_break_reason == LOOP_BREAK_DUPLICATE_TOOL_CALL


def test_same_tool_different_ticker_or_year_is_not_duplicate() -> None:
    ledger = ToolCallLedger(budget=LoopBudget(max_same_tool_same_args=1))
    ledger.record_tool_call(
        turn_id="turn_1",
        agent_id="sec_operator",
        tool_name="sec_search_filings",
        arguments={"tickers": ["MSFT"], "years": [2026], "query": "capex"},
    )

    different_ticker = ledger.can_call_tool(
        turn_id="turn_1",
        agent_id="sec_operator",
        tool_name="sec_search_filings",
        arguments={"tickers": ["NVDA"], "years": [2026], "query": "capex"},
    )
    different_year = ledger.can_call_tool(
        turn_id="turn_1",
        agent_id="sec_operator",
        tool_name="sec_search_filings",
        arguments={"tickers": ["MSFT"], "years": [2025], "query": "capex"},
    )

    assert different_ticker["allowed"] is True
    assert different_year["allowed"] is True


def test_total_and_per_agent_tool_budgets_are_enforced() -> None:
    total_ledger = ToolCallLedger(budget=LoopBudget(max_tool_calls_total=2, max_tool_calls_per_agent=4))
    total_ledger.record_tool_call(turn_id="t", agent_id="sec_operator", tool_name="sec_search_filings", arguments={"tickers": ["A"]})
    total_ledger.record_tool_call(turn_id="t", agent_id="market_operator", tool_name="market_get_snapshot", arguments={"tickers": ["B"]})

    total_decision = total_ledger.can_call_tool(
        turn_id="t",
        agent_id="industry_operator",
        tool_name="industry_get_snapshot",
        arguments={"source_families": ["energy"]},
    )
    assert total_decision["allowed"] is False
    assert total_decision["reason"] == LOOP_BREAK_TOOL_BUDGET_EXHAUSTED
    assert total_ledger.loop_break_reason == LOOP_BREAK_TOOL_BUDGET_EXHAUSTED

    agent_ledger = ToolCallLedger(budget=LoopBudget(max_tool_calls_total=10, max_tool_calls_per_agent=1))
    agent_ledger.record_tool_call(turn_id="t", agent_id="sec_operator", tool_name="sec_search_filings", arguments={"tickers": ["A"]})
    agent_decision = agent_ledger.can_call_tool(
        turn_id="t",
        agent_id="sec_operator",
        tool_name="sec_query_exact_value_ledger",
        arguments={"tickers": ["B"]},
    )
    assert agent_decision["allowed"] is False
    assert agent_decision["reason"] == LOOP_BREAK_AGENT_TOOL_BUDGET_EXHAUSTED
    assert agent_ledger.loop_break_reason == LOOP_BREAK_AGENT_TOOL_BUDGET_EXHAUSTED


def test_second_pass_budget_and_no_gain_break() -> None:
    ledger = ToolCallLedger(budget=LoopBudget(max_second_pass_rounds=1))

    result = ledger.record_second_pass_result(added_row_count=0, coverage_delta={"closed_gaps": 0})
    exhausted = ledger.can_start_second_pass()

    assert result["status"] == "recorded"
    assert result["loop_break_reason"] == LOOP_BREAK_NO_INCREMENTAL_EVIDENCE
    assert result["bounded_answer_allowed"] is True
    assert exhausted["allowed"] is False
    assert exhausted["reason"] == LOOP_BREAK_SECOND_PASS_BUDGET_EXHAUSTED


def test_second_pass_with_added_rows_or_closed_gaps_continues() -> None:
    ledger = ToolCallLedger(budget=LoopBudget(max_second_pass_rounds=2))

    rows_result = ledger.record_second_pass_result(added_row_count=2, coverage_delta={"closed_gaps": 0})
    gaps_result = ledger.record_second_pass_result(added_row_count=0, coverage_delta={"closed_gaps": 1})

    assert rows_result["loop_break_reason"] == ""
    assert gaps_result["loop_break_reason"] == ""
    assert ledger.bounded_answer_allowed is False


def test_repair_no_progress_sets_loop_break_reason() -> None:
    ledger = ToolCallLedger(budget=LoopBudget(max_repair_rounds=2))

    result = ledger.record_repair_result(previous_failure_count=3, new_failure_count=3)

    assert result["status"] == "recorded"
    assert result["loop_break_reason"] == LOOP_BREAK_REPAIR_NO_PROGRESS


def test_graph_step_budget_is_enforced() -> None:
    ledger = ToolCallLedger(budget=LoopBudget(max_graph_steps=1))

    assert ledger.record_graph_step()["status"] == "recorded"
    blocked = ledger.record_graph_step()

    assert blocked["allowed"] is False
    assert blocked["reason"] == LOOP_BREAK_GRAPH_STEP_BUDGET_EXHAUSTED


def test_ledger_round_trip_preserves_records_and_state() -> None:
    ledger = ToolCallLedger(budget=LoopBudget(max_tool_calls_total=3))
    record = ledger.record_tool_call(
        turn_id="turn_1",
        agent_id="sec_operator",
        tool_name="sec_search_filings",
        arguments={"tickers": ["MSFT"], "years": [2026]},
        input_artifact_digests=["sha256:input"],
        output_artifact_digest="sha256:output",
        row_count=7,
        source_gap_count=1,
        coverage_delta={"closed_gaps": 2},
        elapsed_ms=123,
        status="ok",
    )
    ledger.record_second_pass_result(added_row_count=0, coverage_delta={"closed_gaps": 0})

    restored = ToolCallLedger.from_dict(ledger.to_dict())
    restored_record = ToolCallRecord.from_dict(record.to_dict())

    assert restored.budget.max_tool_calls_total == 3
    assert restored.records[0].row_count == 7
    assert restored.records[0].coverage_delta["closed_gaps"] == 2
    assert restored.loop_break_reason == LOOP_BREAK_NO_INCREMENTAL_EVIDENCE
    assert restored_record.output_artifact_digest == "sha256:output"
