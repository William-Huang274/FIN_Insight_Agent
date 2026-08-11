from __future__ import annotations

import sqlite3
from pathlib import Path

from sec_agent.r53_r60_enterprise_release_candidate import build_s10_gate
from sec_agent.r53_r60_enterprise_workbench_product_surface import build_p15_gate
from sec_agent.r53_r60_quality_engineering_online_eval import (
    EVAL_LAYERS,
    P16_EVAL_RUN_ID,
    P16_TASK_ID,
    REFERENCE_ROWS,
    R60_DEMAND_IDS,
    build_p16_gate,
    default_p16_paths,
    quality_engineering_online_eval_schema_contract,
)
from sec_agent.r53_r60_runtime_task_spine import json_loads
from test_r53_r60_enterprise_release_candidate import seed_s10_fixture
from test_r53_r60_enterprise_workbench_product_surface import seed_p15_fixture


def seed_p16_fixture(root: Path) -> None:
    seed_p15_fixture(root)
    assert build_p15_gate(root)["release_decision"] == "P15_L4_scope_pass_enterprise_workbench_product_surface_ready"
    seed_s10_fixture(root)
    assert build_s10_gate(root)["release_decision"] == "S10_L4_scope_pass_release_candidate_ready"


def test_build_p16_gate_outputs_l4_scope_pass(tmp_path: Path) -> None:
    seed_p16_fixture(tmp_path)

    summary = build_p16_gate(tmp_path)

    assert summary["release_decision"] == "P16_L4_scope_pass_quality_engineering_online_eval_ready"
    assert summary["closeout_level"] == "L4_scope_pass"
    assert summary["counts"]["gate_count"] == 12
    assert summary["counts"]["gate_fail_count"] == 0
    assert summary["counts"]["eval_case_count"] >= 6
    assert summary["counts"]["node_eval_gate_count"] == len(EVAL_LAYERS)
    assert (tmp_path / summary["outputs"]["schema"]).exists()
    assert (tmp_path / summary["outputs"]["gate_rows"]).exists()
    assert (tmp_path / summary["outputs"]["summary"]).exists()
    assert (tmp_path / summary["outputs"]["closeout_report"]).exists()


def test_p16_schema_eval_registry_and_e0_e12_layers(tmp_path: Path) -> None:
    seed_p16_fixture(tmp_path)
    build_p16_gate(tmp_path)
    db_path = default_p16_paths(tmp_path).db_path

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        tables = {row["name"] for row in conn.execute("select name from sqlite_master where type='table'").fetchall()}
        dataset = conn.execute("select * from eval_datasets_p16").fetchone()
        eval_run = conn.execute("select * from eval_runs_p16 where eval_run_id = ?", (P16_EVAL_RUN_ID,)).fetchone()
        layers = {row["layer_id"] for row in conn.execute("select layer_id from node_eval_gate_records_p16 where gate_status = 'pass'").fetchall()}
        metric_bad = conn.execute("select count(*) from eval_metric_results_p16 where status != 'pass'").fetchone()[0]

    assert set(quality_engineering_online_eval_schema_contract()["tables"]).issubset(tables)
    assert dataset["status"] == "active"
    assert eval_run["pass_level"] == "L4_scope_pass"
    assert layers == {layer_id for layer_id, _, _ in EVAL_LAYERS}
    assert metric_bad == 0


def test_p16_trace_token_cost_parser_retrieval_tool_metrics(tmp_path: Path) -> None:
    seed_p16_fixture(tmp_path)
    build_p16_gate(tmp_path)
    db_path = default_p16_paths(tmp_path).db_path

    with sqlite3.connect(db_path) as conn:
        trace_count = conn.execute("select count(*) from trace_spans_p16").fetchone()[0]
        model_count = conn.execute("select count(*) from model_call_metrics_p16").fetchone()[0]
        cost_count = conn.execute("select count(*) from token_cost_ledger_p16").fetchone()[0]
        retrieval_count = conn.execute("select count(*) from retrieval_metrics_p16 where qrel_hit_count > 0").fetchone()[0]
        parser_count = conn.execute("select count(*) from parser_metrics_p16").fetchone()[0]
        tool_count = conn.execute("select count(*) from tool_metrics_p16").fetchone()[0]
        silent_overrun = conn.execute(
            """
            select count(*) from budget_exceeded_gates_p16
            where observed_cost > budget_limit
              and (human_approval_required != 1 or decision not like '%approval%')
            """
        ).fetchone()[0]

    assert trace_count >= 4
    assert model_count >= 5
    assert cost_count >= 5
    assert retrieval_count >= 3
    assert parser_count >= 3
    assert tool_count >= 3
    assert silent_overrun == 0


def test_p16_failure_gold_regression_qa_defect_and_demand_acceptance(tmp_path: Path) -> None:
    seed_p16_fixture(tmp_path)
    build_p16_gate(tmp_path)
    db_path = default_p16_paths(tmp_path).db_path

    with sqlite3.connect(db_path) as conn:
        failure_taxonomies = {row[0] for row in conn.execute("select failure_taxonomy from failure_events_p16").fetchall()}
        regression_count = conn.execute("select count(*) from regression_case_records_p16").fetchone()[0]
        gold_count = conn.execute("select count(*) from gold_promotion_records_p16").fetchone()[0]
        qa_plan_count = conn.execute("select count(*) from qa_execution_plans_p16 where status = 'pass'").fetchone()[0]
        defect_count = conn.execute("select count(*) from defect_records_p16").fetchone()[0]
        demand_count = conn.execute("select count(*) from demand_acceptance_records_p16 where status = 'pass'").fetchone()[0]

    assert {"parser_failure", "retrieval_recall_drop", "authority_misuse", "budget_exceeded"}.issubset(failure_taxonomies)
    assert regression_count >= 3
    assert gold_count >= 2
    assert qa_plan_count >= 3
    assert defect_count >= 4
    assert demand_count == len(R60_DEMAND_IDS)


def test_p16_sandbox_reference_dashboard_and_readiness_report(tmp_path: Path) -> None:
    seed_p16_fixture(tmp_path)
    build_p16_gate(tmp_path)
    db_path = default_p16_paths(tmp_path).db_path

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        sandbox_bad = conn.execute(
            "select count(*) from sandbox_regression_records_p16 where status != 'pass' or expected_decision != actual_decision"
        ).fetchone()[0]
        reference_count = conn.execute("select count(*) from reference_source_ledger_p16 where status = 'adopted'").fetchone()[0]
        reference_perf = conn.execute("select count(*) from reference_adoption_performance_p16 where keep_or_revise_decision = 'keep'").fetchone()[0]
        dashboards = conn.execute("select count(*) from eval_dashboard_projections_p16 where status = 'visible'").fetchone()[0]
        incidents = conn.execute("select count(*) from incident_records_p16 where status = 'visible'").fetchone()[0]
        report = conn.execute("select * from quality_readiness_reports_p16").fetchone()

    assert sandbox_bad == 0
    assert reference_count == len(REFERENCE_ROWS)
    assert reference_perf == len(REFERENCE_ROWS)
    assert dashboards >= 4
    assert incidents >= 6
    assert report["release_decision"] == "P16_L4_scope_pass_quality_engineering_online_eval_ready"
    assert json_loads(report["known_gaps_json"], [])


def test_p16_rerun_stable_and_appends_workpaper_event(tmp_path: Path) -> None:
    seed_p16_fixture(tmp_path)
    first = build_p16_gate(tmp_path)
    second = build_p16_gate(tmp_path)
    db_path = default_p16_paths(tmp_path).db_path

    with sqlite3.connect(db_path) as conn:
        eval_case_count = conn.execute("select count(*) from eval_cases_p16").fetchone()[0]
        demand_count = conn.execute("select count(*) from demand_acceptance_records_p16").fetchone()[0]
        event_count = conn.execute(
            "select count(*) from workpaper_events where task_id = ? and event_type = 'quality_engineering_online_eval_ready'",
            (P16_TASK_ID,),
        ).fetchone()[0]

    assert first["release_decision"] == "P16_L4_scope_pass_quality_engineering_online_eval_ready"
    assert second["release_decision"] == "P16_L4_scope_pass_quality_engineering_online_eval_ready"
    assert eval_case_count >= 6
    assert demand_count == len(R60_DEMAND_IDS)
    assert event_count == 2
