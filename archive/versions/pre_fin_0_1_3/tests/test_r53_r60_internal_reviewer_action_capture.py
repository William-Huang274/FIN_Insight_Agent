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
from sec_agent.r53_r60_internal_reviewer_action_capture import (
    append_live_reviewer_action,
    build_p19_gate,
    default_p19_paths,
    get_pilot_action_ledger,
    get_pilot_case_action_ledger,
    internal_reviewer_action_capture_schema_contract,
)
from sec_agent.r53_r60_internal_reviewer_dogfood_window import build_p18_gate
from sec_agent.r53_r60_production_pilot_readiness import PILOT_CASE_IDS
from test_r53_r60_internal_reviewer_dogfood_window import seed_p18_fixture


def seed_p19_fixture(root: Path) -> None:
    seed_p18_fixture(root)
    assert build_p18_gate(root)["release_decision"] == "P18_L4_scope_pass_internal_reviewer_dogfood_window_ready"


def test_build_p19_gate_outputs_l4_scope_pass_and_p16_promotions(tmp_path: Path) -> None:
    seed_p19_fixture(tmp_path)
    summary = build_p19_gate(tmp_path)

    assert summary["release_decision"] == "P19_L4_scope_pass_internal_reviewer_action_capture_ready"
    assert summary["closeout_level"] == "L4_scope_pass"
    assert summary["status"] == "pass"
    assert summary["real_multi_day_human_adoption_status"] == "pending_multi_day_human_dogfood"
    assert summary["full_product_release_status"] == "not_l4_production_pass"
    assert summary["counts"]["gate_count"] == 11
    assert summary["counts"]["gate_fail_count"] == 0
    assert summary["counts"]["live_action_count"] == len(PILOT_CASE_IDS)
    assert summary["counts"]["regression_promotion_count"] >= 1
    assert summary["counts"]["p16_live_regression_count"] == summary["counts"]["regression_promotion_count"]
    assert (tmp_path / summary["outputs"]["schema"]).exists()
    assert (tmp_path / summary["outputs"]["summary"]).exists()


def test_p19_schema_action_feedback_case_status_and_p16_rows_present(tmp_path: Path) -> None:
    seed_p19_fixture(tmp_path)
    build_p19_gate(tmp_path)
    db_path = default_p19_paths(tmp_path).db_path

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        tables = {row["name"] for row in conn.execute("select name from sqlite_master where type='table'").fetchall()}
        action_count = conn.execute("select count(*) from live_reviewer_actions_p19 where action_status = 'ledgered'").fetchone()[0]
        feedback_count = conn.execute("select count(*) from live_reviewer_feedback_records_p19 where feedback_status = 'ledgered'").fetchone()[0]
        case_status_count = conn.execute("select count(*) from live_pilot_case_status_p19").fetchone()[0]
        p16_failure_count = conn.execute("select count(*) from failure_events_p16 where source_ref like 'p19_live_action:%'").fetchone()[0]
        p16_regression_count = conn.execute("select count(*) from regression_case_records_p16 where source_failure_event_id like 'p19_failure_%'").fetchone()[0]

    assert set(internal_reviewer_action_capture_schema_contract()["tables"]).issubset(tables)
    assert action_count == len(PILOT_CASE_IDS)
    assert feedback_count == action_count
    assert case_status_count == len(PILOT_CASE_IDS)
    assert p16_failure_count >= 1
    assert p16_regression_count == p16_failure_count


def test_p19_append_live_reviewer_action_updates_ledger_and_regression(tmp_path: Path) -> None:
    seed_p19_fixture(tmp_path)
    build_p19_gate(tmp_path)

    result = append_live_reviewer_action(
        tmp_path,
        case_id=PILOT_CASE_IDS[0],
        action="request_repair",
        comment="Manual deterministic API smoke repair request",
        reviewer_role="lead_analyst",
    )
    ledger = get_pilot_case_action_ledger(tmp_path, case_id=PILOT_CASE_IDS[0])

    assert result["status"] == "ledgered"
    assert result["p16_regression_case_id"]
    assert any(row["live_action_id"] == result["live_action_id"] for row in ledger["live_reviewer_actions"])
    assert any(row["live_action_id"] == result["live_action_id"] for row in ledger["regression_promotions"])
    assert ledger["case_status"][0]["p16_regression_count"] >= 1


def test_p19_backend_api_exposes_action_ledger_and_post_action(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seed_p19_fixture(tmp_path)
    build_p19_gate(tmp_path)
    monkeypatch.setattr(workbench_app, "REPO_ROOT", tmp_path)
    client = TestClient(workbench_app.create_app(store_path=tmp_path / "workbench_api.sqlite"))

    ledger = client.get("/api/r53-r60/pilot/actions")
    assert ledger.status_code == 200
    assert ledger.json()["counts"]["live_action_count"] == len(PILOT_CASE_IDS)

    response = client.post(
        f"/api/r53-r60/pilot/cases/{PILOT_CASE_IDS[0]}/review-actions",
        json={"action": "request_repair", "comment": "API repair request", "reviewer_role": "lead_analyst"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ledgered"
    assert payload["p16_regression_case_id"]

    detail = client.get(f"/api/r53-r60/pilot/cases/{PILOT_CASE_IDS[0]}/actions")
    assert detail.status_code == 200
    assert any(row["live_action_id"] == payload["live_action_id"] for row in detail.json()["live_reviewer_actions"])

    bad_action = client.post(
        f"/api/r53-r60/pilot/cases/{PILOT_CASE_IDS[0]}/review-actions",
        json={"action": "bad", "comment": "bad", "reviewer_role": "lead_analyst"},
    )
    assert bad_action.status_code == 422

    missing = client.post(
        "/api/r53-r60/pilot/cases/not_a_case/review-actions",
        json={"action": "comment", "comment": "missing", "reviewer_role": "lead_analyst"},
    )
    assert missing.status_code == 404


def test_p19_dashboard_projection_boundary_preserved(tmp_path: Path) -> None:
    seed_p19_fixture(tmp_path)
    build_p19_gate(tmp_path)
    ledger = get_pilot_action_ledger(tmp_path)

    assert ledger["window"]["real_multi_day_human_adoption_status"] == "pending_multi_day_human_dogfood"
    assert ledger["report"]["full_product_release_status"] == "not_l4_production_pass"
    assert ledger["counts"]["regression_promotion_count"] >= 1
    assert all(row["status"] == "pass" for row in ledger["gates"])
