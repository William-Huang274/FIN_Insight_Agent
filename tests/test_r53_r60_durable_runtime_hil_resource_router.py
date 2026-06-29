from __future__ import annotations

import sqlite3
from pathlib import Path

from sec_agent.r53_r60_durable_runtime_hil_resource_router import (
    GRAPH_NODE_NAMES,
    P12_RUNTIME_DRILL_TASK_ID,
    P12_TASK_ID,
    ROUTE_CLASSES,
    TRACE_EXPORT_TARGETS,
    build_p12_gate,
    default_p12_paths,
    durable_runtime_schema_contract,
)
from sec_agent.r53_r60_production_pilot_readiness import build_p11_gate
from sec_agent.r53_r60_runtime_task_spine import json_loads
from test_r53_r60_production_pilot_readiness import seed_p11_fixture


def seed_p12_fixture(root: Path) -> None:
    seed_p11_fixture(root)
    assert build_p11_gate(root)["release_decision"] == "P11_L4_scope_pass_pilot_ready_execution_pending"


def test_build_p12_gate_outputs_runtime_l4_scope_pass(tmp_path: Path) -> None:
    seed_p12_fixture(tmp_path)

    summary = build_p12_gate(tmp_path)

    assert summary["release_decision"] == "P12_L4_scope_pass_runtime_drill_ready"
    assert summary["closeout_level"] == "L4_scope_pass"
    assert summary["status"] == "pass"
    assert summary["runtime_status"] == "durable_runtime_drill_pass"
    assert summary["hil_status"] == "human_interrupt_resume_pass"
    assert summary["resource_router_status"] == "resource_router_ledger_pass"
    assert summary["replay_status"] == "replayable"
    assert summary["full_runtime_migration_status"] == "partial_migration_runtime_drill_only"
    assert summary["counts"]["gate_count"] == 12
    assert summary["counts"]["gate_fail_count"] == 0
    assert summary["counts"]["checkpoint_bridge_count"] >= 2
    assert summary["counts"]["human_interrupt_count"] >= 1
    assert summary["counts"]["human_approval_count"] >= 1
    assert summary["counts"]["route_policy_count"] == len(ROUTE_CLASSES)
    assert summary["counts"]["trace_export_count"] == len(TRACE_EXPORT_TARGETS)
    assert summary["counts"]["drill_resume_count"] >= 1
    assert (tmp_path / summary["outputs"]["schema"]).exists()
    assert (tmp_path / summary["outputs"]["gate_rows"]).exists()
    assert (tmp_path / summary["outputs"]["summary"]).exists()
    assert (tmp_path / summary["outputs"]["closeout_report"]).exists()


def test_p12_schema_node_bindings_and_routes(tmp_path: Path) -> None:
    seed_p12_fixture(tmp_path)
    build_p12_gate(tmp_path)
    db_path = default_p12_paths(tmp_path).db_path

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        tables = {row["name"] for row in conn.execute("select name from sqlite_master where type='table'").fetchall()}
        node_rows = conn.execute("select * from graph_node_runtime_bindings_p12").fetchall()
        route_rows = conn.execute("select * from resource_model_route_policies_p12").fetchall()
        route_classes = {row["route_class"] for row in route_rows}

    assert set(durable_runtime_schema_contract()["tables"]).issubset(tables)
    assert len(node_rows) == len(GRAPH_NODE_NAMES)
    assert {row["node_name"] for row in node_rows} == set(GRAPH_NODE_NAMES)
    assert route_classes == set(ROUTE_CLASSES)
    assert all(row["checkpoint_policy"] for row in node_rows)
    assert all(row["tool_permission_scope"] for row in node_rows)


def test_p12_checkpoint_hil_resume_and_budget(tmp_path: Path) -> None:
    seed_p12_fixture(tmp_path)
    build_p12_gate(tmp_path)
    db_path = default_p12_paths(tmp_path).db_path

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        drill_task = conn.execute("select * from research_tasks where task_id = ?", (P12_RUNTIME_DRILL_TASK_ID,)).fetchone()
        checkpoint_count = conn.execute("select count(*) from checkpoint_bridge_records_p12").fetchone()[0]
        interrupt = conn.execute("select * from human_interrupt_records_p12").fetchone()
        approval = conn.execute("select * from human_approval_decisions_p12").fetchone()
        budgets = conn.execute("select * from model_budget_ledger_p12").fetchall()
        queue_count = conn.execute("select count(*) from resource_queue_events_p12").fetchone()[0]

    assert drill_task["status"] == "succeeded"
    assert int(drill_task["resume_count"]) >= 1
    assert checkpoint_count >= 2
    assert interrupt["status"] == "approved_after_review"
    assert approval["decision"] == "approved"
    assert json_loads(approval["approved_scope_json"], {})["forbidden_actions"] == ["unbounded_web_search"]
    assert queue_count >= len(GRAPH_NODE_NAMES)
    assert budgets
    assert all(row["status"] == "within_budget" for row in budgets)


def test_p12_replay_trace_export_and_boundary(tmp_path: Path) -> None:
    seed_p12_fixture(tmp_path)
    build_p12_gate(tmp_path)
    db_path = default_p12_paths(tmp_path).db_path

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        replay = conn.execute("select * from runtime_replay_attempts_p12").fetchone()
        trace_rows = conn.execute("select * from trace_export_records_p12").fetchall()
        report = conn.execute("select * from runtime_readiness_reports_p12").fetchone()
        gates = conn.execute("select * from runtime_gate_results_p12").fetchall()

    assert replay["replay_status"] == "replayable"
    assert int(replay["checkpoint_count"]) >= 2
    assert int(replay["node_count"]) >= len(GRAPH_NODE_NAMES)
    assert {row["target"] for row in trace_rows} == set(TRACE_EXPORT_TARGETS)
    assert {row["source_of_truth"] for row in trace_rows} == {"sql_runtime_ledger"}
    assert report["full_runtime_migration_status"] == "partial_migration_runtime_drill_only"
    assert report["release_decision"] == "P12_L4_scope_pass_runtime_drill_ready"
    assert json_loads(report["known_gaps_json"], [])
    assert len(gates) == 12
    assert all(row["status"] == "pass" for row in gates)


def test_p12_rerun_keeps_projection_stable_and_appends_event(tmp_path: Path) -> None:
    seed_p12_fixture(tmp_path)
    first = build_p12_gate(tmp_path)
    second = build_p12_gate(tmp_path)
    db_path = default_p12_paths(tmp_path).db_path

    with sqlite3.connect(db_path) as conn:
        route_count = conn.execute("select count(*) from resource_model_route_policies_p12").fetchone()[0]
        event_count = conn.execute(
            "select count(*) from workpaper_events where task_id = ? and event_type = 'durable_runtime_hil_resource_router_ready'",
            (P12_TASK_ID,),
        ).fetchone()[0]
        drill_resume_count = conn.execute(
            "select resume_count from research_tasks where task_id = ?",
            (P12_RUNTIME_DRILL_TASK_ID,),
        ).fetchone()[0]

    assert first["release_decision"] == "P12_L4_scope_pass_runtime_drill_ready"
    assert second["release_decision"] == "P12_L4_scope_pass_runtime_drill_ready"
    assert route_count == len(ROUTE_CLASSES)
    assert event_count == 2
    assert int(drill_resume_count) >= 2
