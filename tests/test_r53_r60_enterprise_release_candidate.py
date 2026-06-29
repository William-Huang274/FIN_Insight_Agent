from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from sec_agent.r53_r60_enterprise_release_candidate import (
    INCIDENT_CATEGORIES,
    S10_TASK_ID,
    build_s10_gate,
    default_s10_paths,
    enterprise_release_schema_contract,
)
from sec_agent.r53_r60_research_to_quant_lab import build_s9_gate
from sec_agent.r53_r60_runtime_task_spine import json_loads
from test_r53_r60_research_to_quant_lab import seed_s9_fixture


def write_summary(path: Path, release_decision: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": path.stem,
                "status": "pass",
                "release_decision": release_decision,
                "closeout_level": "L4_scope_pass",
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def seed_s10_fixture(root: Path) -> None:
    manifest_dir = root / "data" / "manifests"
    for file_name, decision in [
        ("r53_r60_unified_backlog_summary_v0_1.json", "S0_L4_scope_pass"),
        ("r53_r60_s1_runtime_task_spine_summary_v0_1.json", "S1_L4_scope_pass"),
        ("r53_r60_s2_tool_sandbox_trace_summary_v0_1.json", "S2_L4_scope_pass"),
        ("r53_r60_s3_retrieval_evidence_spine_summary_v0_1.json", "S3_L4_scope_pass"),
        ("r53_r60_s4_context_graph_skill_registry_summary_v0_1.json", "S4_L4_scope_pass"),
        ("r53_r60_s5_workpaper_lead_review_workflow_summary_v0_1.json", "S5_L4_scope_pass"),
        ("r53_r60_s6_workbench_frontdoor_drilldown_summary_v0_1.json", "S6_L4_scope_pass"),
        ("r53_r60_s7_deliverable_studio_dashboard_summary_v0_1.json", "S7_L4_scope_pass"),
    ]:
        write_summary(manifest_dir / file_name, decision)
    seed_s9_fixture(root)
    assert build_s9_gate(root)["release_decision"] == "S9_L4_scope_pass"


def test_build_s10_gate_outputs_release_candidate_l4_scope_pass(tmp_path: Path) -> None:
    seed_s10_fixture(tmp_path)

    summary = build_s10_gate(tmp_path)

    assert summary["release_decision"] == "S10_L4_scope_pass_release_candidate_ready"
    assert summary["closeout_level"] == "L4_scope_pass"
    assert summary["full_product_release_status"] == "not_l4_production_pass"
    assert summary["counts"]["gate_count"] == 12
    assert summary["counts"]["gate_fail_count"] == 0
    assert summary["counts"]["demand_acceptance_count"] == 5
    assert summary["counts"]["load_observation_count"] == 20
    assert (tmp_path / summary["outputs"]["schema"]).exists()
    assert (tmp_path / summary["outputs"]["gate_rows"]).exists()
    assert (tmp_path / summary["outputs"]["summary"]).exists()
    assert (tmp_path / summary["outputs"]["closeout_report"]).exists()


def test_s10_schema_and_rbac_contract(tmp_path: Path) -> None:
    seed_s10_fixture(tmp_path)
    build_s10_gate(tmp_path)
    db_path = default_s10_paths(tmp_path).db_path

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        tables = {row["name"] for row in conn.execute("select name from sqlite_master where type='table'").fetchall()}
        allow_count = conn.execute("select count(*) from permission_checks_s10 where decision = 'allow'").fetchone()[0]
        deny_count = conn.execute("select count(*) from permission_checks_s10 where decision = 'deny'").fetchone()[0]
        cross_tenant_bad = conn.execute(
            "select count(*) from permission_checks_s10 where tenant_id != target_tenant_id and decision != 'deny'"
        ).fetchone()[0]
        demands = conn.execute("select * from demand_acceptance_records_s10").fetchall()

    assert set(enterprise_release_schema_contract()["tables"]).issubset(tables)
    assert allow_count >= 3
    assert deny_count >= 2
    assert cross_tenant_bad == 0
    assert len(demands) == 5
    assert all(row["status"] == "pass" for row in demands)


def test_s10_load_chaos_sla_incident_and_feedback_lifecycle(tmp_path: Path) -> None:
    seed_s10_fixture(tmp_path)
    build_s10_gate(tmp_path)
    db_path = default_s10_paths(tmp_path).db_path

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        load_count = conn.execute("select count(*) from load_task_observations_s10").fetchone()[0]
        token_sum = conn.execute("select sum(token_count) from load_task_observations_s10").fetchone()[0]
        cost_sum = conn.execute("select sum(cost_amount) from load_task_observations_s10").fetchone()[0]
        chaos_types = {row["chaos_type"] for row in conn.execute("select chaos_type from chaos_events_s10").fetchall()}
        bad_sla = conn.execute("select count(*) from sla_observations_s10 where status != 'pass'").fetchone()[0]
        visible_categories = {
            row["category"]
            for row in conn.execute("select category from incident_dashboard_projections_s10 where status = 'visible'").fetchall()
        }
        regression_count = conn.execute("select count(*) from regression_case_records_s10").fetchone()[0]
        gold_count = conn.execute("select count(*) from gold_promotion_records_s10").fetchone()[0]

    assert load_count == 20
    assert token_sum > 0
    assert cost_sum > 0
    assert chaos_types == {"worker_crash", "provider_timeout", "sse_disconnect", "artifact_write_retry"}
    assert bad_sla == 0
    assert set(INCIDENT_CATEGORIES).issubset(visible_categories)
    assert regression_count >= 2
    assert gold_count >= 1


def test_s10_release_report_boundary_artifacts_and_workpaper_event(tmp_path: Path) -> None:
    seed_s10_fixture(tmp_path)
    build_s10_gate(tmp_path)
    db_path = default_s10_paths(tmp_path).db_path

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        report = conn.execute("select * from release_readiness_reports_s10").fetchone()
        artifact_count = conn.execute(
            """
            select count(*) from artifact_refs
            where task_id = ? and artifact_type like 'enterprise_release_%'
            """,
            (S10_TASK_ID,),
        ).fetchone()[0]
        event_count = conn.execute(
            "select count(*) from workpaper_events where task_id = ? and event_type = 'enterprise_release_candidate_ready'",
            (S10_TASK_ID,),
        ).fetchone()[0]
        gate_count = conn.execute("select count(*) from release_gate_results_s10 where status = 'pass'").fetchone()[0]

    assert report["status"] == "release_candidate_ready"
    assert report["full_product_release_status"] == "not_l4_production_pass"
    assert json_loads(report["known_gaps_json"], [])
    assert json_loads(report["rollback_plan_json"], {})
    assert report["owner"] == "release_manager"
    assert report["user_feedback_entry"]
    assert artifact_count >= 4
    assert event_count == 1
    assert gate_count == 12


def test_s10_rerun_keeps_current_projection_stable_and_appends_workpaper_event(tmp_path: Path) -> None:
    seed_s10_fixture(tmp_path)
    first = build_s10_gate(tmp_path)
    second = build_s10_gate(tmp_path)
    db_path = default_s10_paths(tmp_path).db_path

    with sqlite3.connect(db_path) as conn:
        demand_count = conn.execute("select count(*) from demand_acceptance_records_s10").fetchone()[0]
        load_count = conn.execute("select count(*) from load_task_observations_s10").fetchone()[0]
        event_count = conn.execute(
            "select count(*) from workpaper_events where task_id = ? and event_type = 'enterprise_release_candidate_ready'",
            (S10_TASK_ID,),
        ).fetchone()[0]

    assert first["release_decision"] == "S10_L4_scope_pass_release_candidate_ready"
    assert second["release_decision"] == "S10_L4_scope_pass_release_candidate_ready"
    assert demand_count == 5
    assert load_count == 20
    assert event_count == 2
