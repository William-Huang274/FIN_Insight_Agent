from __future__ import annotations

import sqlite3
from pathlib import Path

from sec_agent.r53_r60_data_ingestion_retrieval_control_plane import build_p14_gate
from sec_agent.r53_r60_deliverable_studio_dashboard import build_s7_gate
from sec_agent.r53_r60_enterprise_workbench_product_surface import (
    P15_DRILL_TASK_ID,
    P15_TASK_ID,
    REQUIRED_API_SURFACES,
    REQUIRED_JOURNEYS,
    REQUIRED_SURFACES,
    build_p15_gate,
    default_p15_paths,
    enterprise_workbench_product_surface_schema_contract,
)
from sec_agent.r53_r60_graph_skill_memory_lifecycle import build_p13_gate
from sec_agent.r53_r60_runtime_task_spine import json_loads
from sec_agent.r53_r60_workbench_frontdoor_drilldown import DEFAULT_TASK_ID, build_s6_projection
from sec_agent.r53_r60_workpaper_lead_review_workflow import build_s5_gate
from test_r53_r60_data_ingestion_retrieval_control_plane import seed_p14_fixture
from test_r53_r60_workpaper_lead_review_workflow import seed_s5_fixture


def seed_p15_fixture(root: Path) -> None:
    seed_s5_fixture(root)
    assert build_s5_gate(root)["release_decision"] == "S5_L4_scope_pass"
    assert build_s6_projection(root)["release_decision"] == "S6_L4_scope_pass"
    assert build_s7_gate(root)["release_decision"] == "S7_L4_scope_pass"
    seed_p14_fixture(root)
    assert build_p13_gate(root)["release_decision"] == "P13_L4_scope_pass_graph_skill_memory_lifecycle_ready"
    assert build_p14_gate(root)["release_decision"] == "P14_L4_scope_pass_data_ingestion_retrieval_control_plane_ready"


def test_build_p15_gate_outputs_l4_scope_pass(tmp_path: Path) -> None:
    seed_p15_fixture(tmp_path)

    summary = build_p15_gate(tmp_path)

    assert summary["release_decision"] == "P15_L4_scope_pass_enterprise_workbench_product_surface_ready"
    assert summary["closeout_level"] == "L4_scope_pass"
    assert summary["status"] == "pass"
    assert summary["surface_registry_status"] == "surface_registry_ready"
    assert summary["api_contract_status"] == "api_contracts_ready"
    assert summary["workflow_surface_status"] == "workflow_surfaces_ready"
    assert summary["rbac_status"] == "rbac_positive_negative_ready"
    assert summary["e2e_status"] == "deterministic_e2e_journeys_ready"
    assert summary["counts"]["gate_count"] == 12
    assert summary["counts"]["gate_fail_count"] == 0
    assert summary["counts"]["surface_count"] >= len(REQUIRED_SURFACES)
    assert summary["counts"]["api_contract_count"] >= len(REQUIRED_API_SURFACES)
    assert summary["counts"]["journey_count"] >= len(REQUIRED_JOURNEYS)
    assert (tmp_path / summary["outputs"]["schema"]).exists()
    assert (tmp_path / summary["outputs"]["gate_rows"]).exists()
    assert (tmp_path / summary["outputs"]["summary"]).exists()
    assert (tmp_path / summary["outputs"]["closeout_report"]).exists()


def test_p15_schema_surfaces_and_api_contracts_present(tmp_path: Path) -> None:
    seed_p15_fixture(tmp_path)
    build_p15_gate(tmp_path)
    db_path = default_p15_paths(tmp_path).db_path

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        tables = {row["name"] for row in conn.execute("select name from sqlite_master where type='table'").fetchall()}
        surfaces = {row[0] for row in conn.execute("select surface_id from workbench_product_surface_registry_p15").fetchall()}
        api_bad = conn.execute(
            """
            select count(*) from enterprise_api_surface_contracts_p15
            where trace_required != 1 or rbac_required != 1 or sql_audit_required != 1 or status != 'api_contract_ready'
            """
        ).fetchone()[0]
        ia_count = conn.execute("select count(*) from frontend_information_architecture_p15").fetchone()[0]

    contract = enterprise_workbench_product_surface_schema_contract()
    assert set(contract["tables"]).issubset(tables)
    assert set(REQUIRED_SURFACES).issubset(surfaces)
    assert api_bad == 0
    assert ia_count >= len(REQUIRED_SURFACES)


def test_p15_workflow_panels_link_existing_runtime_rows(tmp_path: Path) -> None:
    seed_p15_fixture(tmp_path)
    build_p15_gate(tmp_path)
    db_path = default_p15_paths(tmp_path).db_path

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        task_center = conn.execute("select * from task_center_workflow_records_p15 where task_id = ?", (DEFAULT_TASK_ID,)).fetchone()
        evidence = conn.execute("select * from evidence_workbench_panel_records_p15 where task_id = ?", (DEFAULT_TASK_ID,)).fetchone()
        workpaper = conn.execute("select * from workpaper_builder_panel_records_p15 where task_id = ?", (DEFAULT_TASK_ID,)).fetchone()
        review = conn.execute("select * from review_queue_panel_records_p15 where task_id = ?", (DEFAULT_TASK_ID,)).fetchone()

    assert task_center["status"] == "workflow_surface_ready"
    assert int(task_center["resume_supported"]) == 1
    assert int(evidence["claim_count"]) > 0
    assert int(evidence["gap_count"]) > 0
    assert int(evidence["source_lineage_visible"]) == 1
    assert int(workpaper["section_count"]) > 0
    assert int(workpaper["claim_card_count"]) > 0
    assert "evidence_refs" in json_loads(workpaper["locked_fields_json"], [])
    assert int(review["review_item_count"]) > 0
    assert int(review["approval_supported"]) == 1


def test_p15_artifact_deliverable_data_room_and_ops_surfaces(tmp_path: Path) -> None:
    seed_p15_fixture(tmp_path)
    build_p15_gate(tmp_path)
    db_path = default_p15_paths(tmp_path).db_path

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        artifacts = conn.execute("select * from artifact_browser_records_p15 where task_id = ?", (DEFAULT_TASK_ID,)).fetchone()
        deliverable = conn.execute("select * from deliverable_studio_panel_records_p15 where task_id = ?", (DEFAULT_TASK_ID,)).fetchone()
        upload = conn.execute("select * from data_room_upload_contracts_p15").fetchone()
        ops = conn.execute("select * from admin_ops_console_panel_records_p15 where task_id = ?", (DEFAULT_TASK_ID,)).fetchone()

    assert int(artifacts["artifact_ref_count"]) > 0
    assert int(artifacts["source_trace_links"]) > 0
    assert int(artifacts["lineage_drilldown_supported"]) == 1
    assert int(deliverable["render_job_count"]) >= 3
    assert int(deliverable["publish_requires_approval"]) == 1
    assert int(upload["parser_required"]) == 1
    assert int(upload["provenance_required"]) == 1
    assert upload["user_provided_evidence_pack_status"] == "user_provided_evidence_pack_pending_parser_gate"
    assert int(ops["cost_latency_visible"]) == 1
    assert int(ops["rollback_supported"]) == 1


def test_p15_rbac_negative_cases_action_ledger_and_journeys(tmp_path: Path) -> None:
    seed_p15_fixture(tmp_path)
    build_p15_gate(tmp_path)
    db_path = default_p15_paths(tmp_path).db_path

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rbac_bad = conn.execute("select count(*) from rbac_product_permission_checks_p15 where expected_decision != actual_decision or status != 'pass'").fetchone()[0]
        deny_count = conn.execute("select count(*) from rbac_product_permission_checks_p15 where expected_decision = 'deny'").fetchone()[0]
        denied_actions = conn.execute("select count(*) from product_action_ledger_p15 where permission_decision = 'deny' and status = 'permission_denied_recorded'").fetchone()[0]
        journeys = {row[0] for row in conn.execute("select journey_name from frontend_e2e_journey_records_p15 where status = 'pass'").fetchall()}

    assert rbac_bad == 0
    assert deny_count >= 2
    assert denied_actions >= 1
    assert set(REQUIRED_JOURNEYS).issubset(journeys)


def test_p15_rerun_stable_and_appends_workpaper_event(tmp_path: Path) -> None:
    seed_p15_fixture(tmp_path)
    first = build_p15_gate(tmp_path)
    second = build_p15_gate(tmp_path)
    db_path = default_p15_paths(tmp_path).db_path

    with sqlite3.connect(db_path) as conn:
        surface_count = conn.execute("select count(*) from workbench_product_surface_registry_p15").fetchone()[0]
        gate_count = conn.execute("select count(*) from workbench_product_gate_results_p15").fetchone()[0]
        event_count = conn.execute(
            "select count(*) from workpaper_events where task_id = ? and event_type = 'enterprise_workbench_product_surface_ready'",
            (P15_TASK_ID,),
        ).fetchone()[0]
        drill_resume_count = conn.execute(
            "select resume_count from research_tasks where task_id = ?",
            (P15_DRILL_TASK_ID,),
        ).fetchone()[0]

    assert first["release_decision"] == "P15_L4_scope_pass_enterprise_workbench_product_surface_ready"
    assert second["release_decision"] == "P15_L4_scope_pass_enterprise_workbench_product_surface_ready"
    assert surface_count >= len(REQUIRED_SURFACES)
    assert gate_count == 12
    assert event_count == 2
    assert int(drill_resume_count) >= 1
