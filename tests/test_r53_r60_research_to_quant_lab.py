from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from sec_agent.r53_r60_research_to_quant_lab import (
    S9_TASK_ID,
    build_s9_gate,
    default_s9_paths,
    research_to_quant_schema_contract,
)
from sec_agent.r53_r60_secondary_market_capital_feedback import build_s8_gate
from test_r53_r60_secondary_market_capital_feedback import seed_s8_fixture


def seed_s9_fixture(root: Path) -> None:
    seed_s8_fixture(root)
    assert build_s8_gate(root)["release_decision"] == "S8_L4_scope_pass"


def test_build_s9_gate_outputs_l4_scope_pass(tmp_path: Path) -> None:
    seed_s9_fixture(tmp_path)

    summary = build_s9_gate(tmp_path)

    assert summary["release_decision"] == "S9_L4_scope_pass"
    assert summary["closeout_level"] == "L4_scope_pass"
    assert summary["next_slice_unlocked"] == "S10"
    assert summary["counts"]["gate_count"] == 12
    assert summary["counts"]["gate_fail_count"] == 0
    assert summary["counts"]["approved_factor_count"] == 2
    assert summary["counts"]["blocked_factor_count"] == 1
    assert summary["counts"]["backtest_result_count"] == 2
    assert (tmp_path / summary["outputs"]["schema"]).exists()
    assert (tmp_path / summary["outputs"]["gate_rows"]).exists()
    assert (tmp_path / summary["outputs"]["summary"]).exists()
    assert (tmp_path / summary["outputs"]["closeout_report"]).exists()


def test_s9_schema_hypothesis_traceability_and_approval_contract(tmp_path: Path) -> None:
    seed_s9_fixture(tmp_path)
    build_s9_gate(tmp_path)
    db_path = default_s9_paths(tmp_path).db_path
    contract = research_to_quant_schema_contract()

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        tables = {row["name"] for row in conn.execute("select name from sqlite_master where type='table'").fetchall()}
        hypotheses = conn.execute("select * from factor_hypotheses_s9 where task_id = ?", (S9_TASK_ID,)).fetchall()
        trace_bad = conn.execute(
            """
            select count(*) from factor_hypotheses_s9
            where task_id = ? and (thesis_driver_id = '' or source_refs_json in ('', '[]'))
            """,
            (S9_TASK_ID,),
        ).fetchone()[0]
        approved_plan_bad = conn.execute(
            """
            select count(*) from dataset_build_plans_s9 p
            left join human_approval_decisions_s9 a on p.approval_id = a.approval_id
            where p.task_id = ?
              and p.status != 'blocked_no_human_approval'
              and (a.decision != 'approved' or a.approval_scope != 'dataset_build')
            """,
            (S9_TASK_ID,),
        ).fetchone()[0]
        denied_plan = conn.execute(
            "select * from dataset_build_plans_s9 where task_id = ? and status = 'blocked_no_human_approval'",
            (S9_TASK_ID,),
        ).fetchone()
        denied_rows = conn.execute(
            "select count(*) from pit_dataset_rows_s9 where task_id = ? and dataset_build_plan_id = ?",
            (S9_TASK_ID, denied_plan["dataset_build_plan_id"]),
        ).fetchone()[0]

    assert set(contract["tables"]).issubset(tables)
    assert len(hypotheses) == 3
    assert trace_bad == 0
    assert approved_plan_bad == 0
    assert denied_plan is not None
    assert denied_rows == 0


def test_s9_pit_rows_leakage_guard_and_backtest_are_fail_closed(tmp_path: Path) -> None:
    seed_s9_fixture(tmp_path)
    build_s9_gate(tmp_path)
    db_path = default_s9_paths(tmp_path).db_path

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        pit_bad = conn.execute(
            """
            select count(*) from pit_dataset_rows_s9
            where task_id = ?
              and (source_refs_json in ('', '[]')
                   or feature_available_time > tradable_after
                   or tradable_after > label_window_start)
            """,
            (S9_TASK_ID,),
        ).fetchone()[0]
        leakage_statuses = {
            row["status"]
            for row in conn.execute("select status from leakage_guard_results_s9 where task_id = ?", (S9_TASK_ID,)).fetchall()
        }
        backtests = conn.execute("select * from backtest_results_s9 where task_id = ?", (S9_TASK_ID,)).fetchall()
        denied_backtest_count = conn.execute(
            """
            select count(*) from backtest_results_s9
            where task_id = ?
              and factor_hypothesis_id in (
                select factor_hypothesis_id from factor_hypotheses_s9
                where task_id = ? and status = 'blocked_no_human_approval'
              )
            """,
            (S9_TASK_ID, S9_TASK_ID),
        ).fetchone()[0]

    assert pit_bad == 0
    assert "pass" in leakage_statuses
    assert "blocked_no_human_approval" in leakage_statuses
    assert len(backtests) == 2
    assert all(row["no_investment_advice"] == 1 and row["status"] == "pass" for row in backtests)
    assert denied_backtest_count == 0


def test_s9_factorcards_risk_memory_and_paper_trading_boundary(tmp_path: Path) -> None:
    seed_s9_fixture(tmp_path)
    build_s9_gate(tmp_path)
    db_path = default_s9_paths(tmp_path).db_path

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        factor_cards = conn.execute("select * from factor_cards_s9 where task_id = ?", (S9_TASK_ID,)).fetchall()
        bad_cards = [
            row
            for row in factor_cards
            if row["no_investment_advice"] != 1
            or "live_trading" not in row["forbidden_actions_json"]
            or not json.loads(row["failure_scenarios_json"])
        ]
        paper_started = conn.execute(
            "select count(*) from paper_trading_controls_s9 where task_id = ? and status not like 'not_started%'",
            (S9_TASK_ID,),
        ).fetchone()[0]
        experience_rows = conn.execute("select * from research_experience_records_s9 where task_id = ?", (S9_TASK_ID,)).fetchall()
        risk_count = conn.execute("select count(*) from risk_attributions_s9 where task_id = ?", (S9_TASK_ID,)).fetchone()[0]
        event_count = conn.execute(
            "select count(*) from workpaper_events where task_id = ? and event_type = 'research_to_quant_lab_ready'",
            (S9_TASK_ID,),
        ).fetchone()[0]

    assert len(factor_cards) == 3
    assert bad_cards == []
    assert paper_started == 0
    assert len(experience_rows) == 3
    assert risk_count == 2
    assert event_count == 1


def test_s9_rerun_keeps_current_projection_stable_and_appends_workpaper_event(tmp_path: Path) -> None:
    seed_s9_fixture(tmp_path)
    first = build_s9_gate(tmp_path)
    second = build_s9_gate(tmp_path)
    db_path = default_s9_paths(tmp_path).db_path

    with sqlite3.connect(db_path) as conn:
        factor_count = conn.execute("select count(*) from factor_hypotheses_s9 where task_id = ?", (S9_TASK_ID,)).fetchone()[0]
        backtest_count = conn.execute("select count(*) from backtest_results_s9 where task_id = ?", (S9_TASK_ID,)).fetchone()[0]
        event_count = conn.execute(
            "select count(*) from workpaper_events where task_id = ? and event_type = 'research_to_quant_lab_ready'",
            (S9_TASK_ID,),
        ).fetchone()[0]

    assert first["release_decision"] == "S9_L4_scope_pass"
    assert second["release_decision"] == "S9_L4_scope_pass"
    assert factor_count == 3
    assert backtest_count == 2
    assert event_count == 2
