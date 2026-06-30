from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fastapi.testclient import TestClient

import apps.workbench.backend.app as workbench_app
from sec_agent.r53_r60_controlled_internal_pilot_execution import build_p17_gate
from sec_agent.r53_r60_internal_reviewer_dogfood_window import (
    P18_WINDOW_ID,
    build_p18_gate,
    default_p18_paths,
    get_pilot_case_detail,
    get_pilot_dashboard_projection,
    internal_reviewer_dogfood_window_schema_contract,
)
from sec_agent.r53_r60_production_pilot_readiness import PILOT_CASE_IDS
from test_r53_r60_controlled_internal_pilot_execution import seed_p17_fixture


def seed_p18_fixture(root: Path) -> None:
    seed_p17_fixture(root)
    assert build_p17_gate(root)["release_decision"] == "P17_L4_scope_pass_controlled_internal_pilot_execution_ready"


def test_build_p18_gate_outputs_l4_scope_pass(tmp_path: Path) -> None:
    seed_p18_fixture(tmp_path)
    summary = build_p18_gate(tmp_path)

    assert summary["release_decision"] == "P18_L4_scope_pass_internal_reviewer_dogfood_window_ready"
    assert summary["closeout_level"] == "L4_scope_pass"
    assert summary["status"] == "pass"
    assert summary["dogfood_status"] == "ready_for_real_internal_reviewer_use"
    assert summary["real_human_adoption_status"] == "pending_actual_reviewer_actions"
    assert summary["full_product_release_status"] == "not_l4_production_pass"
    assert summary["counts"]["gate_count"] == 11
    assert summary["counts"]["gate_fail_count"] == 0
    assert summary["counts"]["assignment_count"] == len(PILOT_CASE_IDS)
    assert (tmp_path / summary["outputs"]["schema"]).exists()
    assert (tmp_path / summary["outputs"]["gate_rows"]).exists()
    assert (tmp_path / summary["outputs"]["summary"]).exists()
    assert (tmp_path / summary["outputs"]["closeout_report"]).exists()


def test_p18_schema_assignments_sessions_and_promotions_present(tmp_path: Path) -> None:
    seed_p18_fixture(tmp_path)
    build_p18_gate(tmp_path)
    db_path = default_p18_paths(tmp_path).db_path

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        tables = {row["name"] for row in conn.execute("select name from sqlite_master where type='table'").fetchall()}
        window = conn.execute("select * from dogfood_windows_p18").fetchone()
        assignment_count = conn.execute("select count(*) from dogfood_case_assignments_p18 where assignment_status = 'review_ready'").fetchone()[0]
        session_count = conn.execute("select count(*) from reviewer_session_records_p18 where session_status = 'ready_for_real_human_replay'").fetchone()[0]
        action_count = conn.execute("select count(*) from reviewer_action_events_p18").fetchone()[0]
        promotion_count = conn.execute("select count(*) from pilot_defect_promotions_p18 where promotion_status = 'queued_for_p16_regression_lifecycle'").fetchone()[0]
        api_count = conn.execute("select count(*) from pilot_workbench_api_contracts_p18 where status = 'implemented'").fetchone()[0]

    assert set(internal_reviewer_dogfood_window_schema_contract()["tables"]).issubset(tables)
    assert window["window_id"] == P18_WINDOW_ID
    assert window["real_human_adoption_status"] == "pending_actual_reviewer_actions"
    assert assignment_count == len(PILOT_CASE_IDS)
    assert session_count == len(PILOT_CASE_IDS)
    assert action_count >= len(PILOT_CASE_IDS) * 3
    assert promotion_count == len(PILOT_CASE_IDS)
    assert api_count == 3


def test_p18_dashboard_projection_and_case_detail_decode_json(tmp_path: Path) -> None:
    seed_p18_fixture(tmp_path)
    build_p18_gate(tmp_path)

    dashboard = get_pilot_dashboard_projection(tmp_path)
    case_detail = get_pilot_case_detail(tmp_path, case_id=PILOT_CASE_IDS[0])

    assert dashboard["schema_version"].endswith("v0_1")
    assert dashboard["window"]["window_status"] == "ready_for_real_internal_reviewer_use"
    assert dashboard["counts"]["case_assignment_count"] == len(PILOT_CASE_IDS)
    assert len(dashboard["tiles"]) >= 6
    assert len(dashboard["gates"]) == 11
    assert dashboard["readiness_report"]["full_product_release_status"] == "not_l4_production_pass"
    assert case_detail["case"]["case_id"] == PILOT_CASE_IDS[0]
    assert case_detail["sessions"]
    assert case_detail["reviewer_action_events"]
    assert case_detail["defect_promotions"]
    assert isinstance(case_detail["case"]["required_actions"], list)


def test_p18_gates_preserve_real_human_boundary(tmp_path: Path) -> None:
    seed_p18_fixture(tmp_path)
    build_p18_gate(tmp_path)
    db_path = default_p18_paths(tmp_path).db_path

    with sqlite3.connect(db_path) as conn:
        fake_adoption = conn.execute(
            "select count(*) from dogfood_windows_p18 where real_human_adoption_status != 'pending_actual_reviewer_actions'"
        ).fetchone()[0]
        gate_fail = conn.execute("select count(*) from pilot_dogfood_gate_results_p18 where status != 'pass'").fetchone()[0]
        report_bad = conn.execute(
            "select count(*) from pilot_dogfood_readiness_reports_p18 where full_product_release_status != 'not_l4_production_pass'"
        ).fetchone()[0]

    assert fake_adoption == 0
    assert gate_fail == 0
    assert report_bad == 0


def test_p18_backend_api_exposes_pilot_dashboard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seed_p18_fixture(tmp_path)
    build_p18_gate(tmp_path)
    monkeypatch.setattr(workbench_app, "REPO_ROOT", tmp_path)
    client = TestClient(workbench_app.create_app(store_path=tmp_path / "workbench_api.sqlite"))

    dashboard = client.get("/api/r53-r60/pilot/dashboard")
    assert dashboard.status_code == 200
    payload = dashboard.json()
    assert payload["counts"]["case_assignment_count"] == len(PILOT_CASE_IDS)
    assert payload["readiness_report"]["full_product_release_status"] == "not_l4_production_pass"

    cases = client.get("/api/r53-r60/pilot/cases")
    assert cases.status_code == 200
    assert len(cases.json()["cases"]) == len(PILOT_CASE_IDS)

    detail = client.get(f"/api/r53-r60/pilot/cases/{PILOT_CASE_IDS[0]}")
    assert detail.status_code == 200
    assert detail.json()["case"]["case_id"] == PILOT_CASE_IDS[0]

    missing = client.get("/api/r53-r60/pilot/cases/not_a_case")
    assert missing.status_code == 404
