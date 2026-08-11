from __future__ import annotations

import sqlite3
from pathlib import Path

from sec_agent.r53_r60_controlled_internal_pilot_execution import (
    CASE_STAGES,
    P17_TASK_ID,
    build_p17_gate,
    controlled_internal_pilot_execution_schema_contract,
    default_p17_paths,
)
from sec_agent.r53_r60_production_pilot_readiness import build_p11_gate
from sec_agent.r53_r60_quality_engineering_online_eval import build_p16_gate
from sec_agent.r53_r60_production_pilot_readiness import PILOT_CASE_IDS
from sec_agent.r53_r60_runtime_task_spine import json_loads
from test_r53_r60_production_pilot_readiness import seed_p11_fixture
from test_r53_r60_quality_engineering_online_eval import seed_p16_fixture


def seed_p17_fixture(root: Path) -> None:
    seed_p11_fixture(root)
    assert build_p11_gate(root)["release_decision"] == "P11_L4_scope_pass_pilot_ready_execution_pending"
    seed_p16_fixture(root)
    assert build_p16_gate(root)["release_decision"] == "P16_L4_scope_pass_quality_engineering_online_eval_ready"


def test_build_p17_gate_outputs_l4_scope_pass(tmp_path: Path) -> None:
    seed_p17_fixture(tmp_path)
    summary = build_p17_gate(tmp_path)

    assert summary["release_decision"] == "P17_L4_scope_pass_controlled_internal_pilot_execution_ready"
    assert summary["closeout_level"] == "L4_scope_pass"
    assert summary["status"] == "pass"
    assert summary["pilot_execution_status"] == "controlled_internal_pilot_drill_executed"
    assert summary["full_product_release_status"] == "not_l4_production_pass"
    assert summary["counts"]["gate_count"] == 12
    assert summary["counts"]["gate_fail_count"] == 0
    assert summary["counts"]["case_execution_count"] == len(PILOT_CASE_IDS)
    assert (tmp_path / summary["outputs"]["schema"]).exists()
    assert (tmp_path / summary["outputs"]["gate_rows"]).exists()
    assert (tmp_path / summary["outputs"]["summary"]).exists()
    assert (tmp_path / summary["outputs"]["closeout_report"]).exists()


def test_p17_schema_cases_and_dependencies_present(tmp_path: Path) -> None:
    seed_p17_fixture(tmp_path)
    summary = build_p17_gate(tmp_path)
    db_path = default_p17_paths(tmp_path).db_path

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        tables = {row["name"] for row in conn.execute("select name from sqlite_master where type='table'").fetchall()}
        case_ids = {row[0] for row in conn.execute("select case_id from pilot_case_executions_p17").fetchall()}
        dependency_bad = [row for row in summary["dependency_status"] if row["status"] != "pass"]
        batch = conn.execute("select * from pilot_execution_batches_p17").fetchone()

    assert set(controlled_internal_pilot_execution_schema_contract()["tables"]).issubset(tables)
    assert set(PILOT_CASE_IDS).issubset(case_ids)
    assert not dependency_bad
    assert batch["batch_status"] == "controlled_internal_pilot_drill_complete"


def test_p17_runtime_stage_workpaper_and_artifacts(tmp_path: Path) -> None:
    seed_p17_fixture(tmp_path)
    build_p17_gate(tmp_path)
    db_path = default_p17_paths(tmp_path).db_path

    with sqlite3.connect(db_path) as conn:
        stage_count = conn.execute("select count(*) from pilot_case_stage_checkpoints_p17 where stage_status = 'pass'").fetchone()[0]
        runtime_success = conn.execute(
            """
            select count(*)
            from pilot_case_executions_p17 e
            join research_tasks t on e.runtime_task_id = t.task_id
            where t.status = 'succeeded'
            """
        ).fetchone()[0]
        workpaper_count = conn.execute("select count(*) from pilot_case_workpaper_outputs_p17 where memo_logic_plan_status = 'lead_reviewed'").fetchone()[0]
        artifact_count = conn.execute("select count(*) from pilot_case_artifact_links_p17 where resolvable = 1").fetchone()[0]
        p17_event_count = conn.execute(
            "select count(*) from workpaper_events where task_id = ? and event_type = 'controlled_internal_pilot_execution_ready'",
            (P17_TASK_ID,),
        ).fetchone()[0]

    assert stage_count == len(PILOT_CASE_IDS) * len(CASE_STAGES)
    assert runtime_success == len(PILOT_CASE_IDS)
    assert workpaper_count == len(PILOT_CASE_IDS)
    assert artifact_count == len(PILOT_CASE_IDS)
    assert p17_event_count == 1


def test_p17_review_eval_feedback_defect_and_cost_ledgers(tmp_path: Path) -> None:
    seed_p17_fixture(tmp_path)
    build_p17_gate(tmp_path)
    db_path = default_p17_paths(tmp_path).db_path

    with sqlite3.connect(db_path) as conn:
        review_count = conn.execute("select count(*) from pilot_case_reviewer_actions_p17 where action_status = 'complete'").fetchone()[0]
        eval_bad = conn.execute("select count(*) from pilot_case_eval_snapshots_p17 where gate_status != 'pass' or score < threshold").fetchone()[0]
        feedback_count = conn.execute("select count(*) from pilot_case_feedback_records_p17 where lifecycle_status = 'routed_to_defect_or_regression'").fetchone()[0]
        defect_count = conn.execute("select count(*) from pilot_case_defect_records_p17").fetchone()[0]
        over_budget = conn.execute("select count(*) from pilot_case_cost_latency_records_p17 where cost_usd > budget_usd").fetchone()[0]
        hidden_gap = conn.execute("select count(*) from pilot_case_defect_records_p17 where payload_json not like '%not_hidden_fallback%'").fetchone()[0]

    assert review_count >= len(PILOT_CASE_IDS) * 3
    assert eval_bad == 0
    assert feedback_count == len(PILOT_CASE_IDS)
    assert defect_count == len(PILOT_CASE_IDS)
    assert over_budget == 0
    assert hidden_gap == 0


def test_p17_release_report_preserves_production_boundary(tmp_path: Path) -> None:
    seed_p17_fixture(tmp_path)
    build_p17_gate(tmp_path)
    db_path = default_p17_paths(tmp_path).db_path

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        report = conn.execute("select * from pilot_execution_readiness_reports_p17").fetchone()
        decisions_bad = conn.execute(
            "select count(*) from pilot_case_release_decisions_p17 where production_boundary != 'not_l4_production_pass'"
        ).fetchone()[0]

    assert report["release_decision"] == "P17_L4_scope_pass_controlled_internal_pilot_execution_ready"
    assert report["full_product_release_status"] == "not_l4_production_pass"
    assert json_loads(report["known_gaps_json"], [])
    assert json_loads(report["next_actions_json"], [])
    assert decisions_bad == 0


def test_p17_rerun_stable_and_appends_p17_workpaper_event(tmp_path: Path) -> None:
    seed_p17_fixture(tmp_path)
    first = build_p17_gate(tmp_path)
    second = build_p17_gate(tmp_path)
    db_path = default_p17_paths(tmp_path).db_path

    with sqlite3.connect(db_path) as conn:
        gate_count = conn.execute("select count(*) from pilot_execution_gate_results_p17").fetchone()[0]
        case_count = conn.execute("select count(*) from pilot_case_executions_p17").fetchone()[0]
        event_count = conn.execute(
            "select count(*) from workpaper_events where task_id = ? and event_type = 'controlled_internal_pilot_execution_ready'",
            (P17_TASK_ID,),
        ).fetchone()[0]

    assert first["release_decision"] == "P17_L4_scope_pass_controlled_internal_pilot_execution_ready"
    assert second["release_decision"] == "P17_L4_scope_pass_controlled_internal_pilot_execution_ready"
    assert gate_count == 12
    assert case_count == len(PILOT_CASE_IDS)
    assert event_count == 2
