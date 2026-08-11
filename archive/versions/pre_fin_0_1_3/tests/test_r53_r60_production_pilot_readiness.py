from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from sec_agent.r53_r60_enterprise_release_candidate import build_s10_gate
from sec_agent.r53_r60_production_pilot_readiness import (
    P11_TASK_ID,
    PILOT_CASE_IDS,
    REVIEWER_ROLES,
    SLA_TARGETS,
    build_p11_gate,
    default_p11_paths,
    production_pilot_readiness_schema_contract,
)
from sec_agent.r53_r60_runtime_task_spine import json_loads
from test_r53_r60_enterprise_release_candidate import seed_s10_fixture


def seed_p11_fixture(root: Path) -> None:
    seed_s10_fixture(root)
    assert build_s10_gate(root)["release_decision"] == "S10_L4_scope_pass_release_candidate_ready"
    post_s10_path = root / "data" / "manifests" / "r53_r60_post_s10_completion_gap_register_v0_1.json"
    post_s10_path.parent.mkdir(parents=True, exist_ok=True)
    post_s10_path.write_text(
        json.dumps(
            {
                "schema_version": "r53_r60_post_s10_completion_gap_register_v0_1",
                "status": "pass",
                "decision": "R53-R60 reached controlled internal release-candidate scope pass; not claim full production.",
                "production_gaps": [
                    {"gap_id": "P-S10-001"},
                    {"gap_id": "P-PRD-001"},
                ],
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def test_build_p11_gate_outputs_pilot_readiness_l4_scope_pass(tmp_path: Path) -> None:
    seed_p11_fixture(tmp_path)

    summary = build_p11_gate(tmp_path)

    assert summary["release_decision"] == "P11_L4_scope_pass_pilot_ready_execution_pending"
    assert summary["closeout_level"] == "L4_scope_pass"
    assert summary["pilot_readiness_status"] == "ready_for_controlled_internal_pilot"
    assert summary["pilot_execution_status"] == "not_started_requires_real_internal_pilot"
    assert summary["full_product_release_status"] == "not_l4_production_pass"
    assert summary["counts"]["gate_count"] == 10
    assert summary["counts"]["gate_fail_count"] == 0
    assert summary["counts"]["case_catalog_count"] == len(PILOT_CASE_IDS)
    assert (tmp_path / summary["outputs"]["schema"]).exists()
    assert (tmp_path / summary["outputs"]["gate_rows"]).exists()
    assert (tmp_path / summary["outputs"]["summary"]).exists()
    assert (tmp_path / summary["outputs"]["closeout_report"]).exists()


def test_p11_schema_case_catalog_and_reviewer_protocols(tmp_path: Path) -> None:
    seed_p11_fixture(tmp_path)
    build_p11_gate(tmp_path)
    db_path = default_p11_paths(tmp_path).db_path

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        tables = {row["name"] for row in conn.execute("select name from sqlite_master where type='table'").fetchall()}
        cases = conn.execute("select * from pilot_case_catalog_p11").fetchall()
        roles = {row["role"] for row in conn.execute("select * from pilot_reviewer_protocols_p11").fetchall()}
        assignments = conn.execute("select count(*) from pilot_reviewer_assignments_p11").fetchone()[0]

    assert set(production_pilot_readiness_schema_contract()["tables"]).issubset(tables)
    assert len(cases) == len(PILOT_CASE_IDS)
    assert all(json_loads(row["expected_surfaces_json"], []) for row in cases)
    assert all(json_loads(row["required_pack_refs_json"], []) for row in cases)
    assert set(REVIEWER_ROLES).issubset(roles)
    assert assignments >= len(PILOT_CASE_IDS) * 2


def test_p11_sla_feedback_defect_rollback_and_cost_contracts(tmp_path: Path) -> None:
    seed_p11_fixture(tmp_path)
    build_p11_gate(tmp_path)
    db_path = default_p11_paths(tmp_path).db_path

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        sla_targets = {row["metric_name"] for row in conn.execute("select metric_name from pilot_sla_targets_p11").fetchall()}
        baseline_count = conn.execute("select count(*) from pilot_baseline_observations_p11").fetchone()[0]
        feedback_count = conn.execute("select count(*) from pilot_dogfood_feedback_records_p11").fetchone()[0]
        defect_count = conn.execute("select count(*) from pilot_defect_lifecycle_records_p11").fetchone()[0]
        rollback_count = conn.execute("select count(*) from pilot_rollback_rehearsals_p11").fetchone()[0]
        cost_count = conn.execute("select count(*) from pilot_cost_roi_records_p11").fetchone()[0]

    assert set(SLA_TARGETS).issubset(sla_targets)
    assert baseline_count >= 6
    assert feedback_count >= 4
    assert defect_count >= 6
    assert rollback_count >= 3
    assert cost_count >= 3


def test_p11_readiness_report_boundary_artifacts_and_workpaper_event(tmp_path: Path) -> None:
    seed_p11_fixture(tmp_path)
    build_p11_gate(tmp_path)
    db_path = default_p11_paths(tmp_path).db_path

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        report = conn.execute("select * from pilot_readiness_reports_p11").fetchone()
        artifact_count = conn.execute(
            """
            select count(*) from artifact_refs
            where task_id = ? and artifact_type like 'production_pilot_readiness_%'
            """,
            (P11_TASK_ID,),
        ).fetchone()[0]
        event_count = conn.execute(
            "select count(*) from workpaper_events where task_id = ? and event_type = 'production_pilot_readiness_ready'",
            (P11_TASK_ID,),
        ).fetchone()[0]
        gate_count = conn.execute("select count(*) from pilot_gate_results_p11 where status = 'pass'").fetchone()[0]

    assert report["readiness_status"] == "ready_for_controlled_internal_pilot"
    assert report["pilot_execution_status"] == "not_started_requires_real_internal_pilot"
    assert report["full_product_release_status"] == "not_l4_production_pass"
    assert json_loads(report["known_gaps_json"], [])
    assert json_loads(report["next_actions_json"], [])
    assert artifact_count >= 4
    assert event_count == 1
    assert gate_count == 10


def test_p11_rerun_keeps_projection_stable_and_appends_event(tmp_path: Path) -> None:
    seed_p11_fixture(tmp_path)
    first = build_p11_gate(tmp_path)
    second = build_p11_gate(tmp_path)
    db_path = default_p11_paths(tmp_path).db_path

    with sqlite3.connect(db_path) as conn:
        case_count = conn.execute("select count(*) from pilot_case_catalog_p11").fetchone()[0]
        event_count = conn.execute(
            "select count(*) from workpaper_events where task_id = ? and event_type = 'production_pilot_readiness_ready'",
            (P11_TASK_ID,),
        ).fetchone()[0]

    assert first["release_decision"] == "P11_L4_scope_pass_pilot_ready_execution_pending"
    assert second["release_decision"] == "P11_L4_scope_pass_pilot_ready_execution_pending"
    assert case_count == len(PILOT_CASE_IDS)
    assert event_count == 2
