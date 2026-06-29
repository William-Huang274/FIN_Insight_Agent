from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from fastapi.testclient import TestClient

import apps.workbench.backend.app as workbench_app
from sec_agent.r53_r60_workbench_frontdoor_drilldown import (
    DEFAULT_TASK_ID,
    append_review_action,
    build_s6_projection,
    default_s6_paths,
    get_ops_projection,
    get_review_queue,
    get_task_detail,
    get_task_drilldown,
    list_tasks,
    workbench_frontdoor_schema_contract,
)
from sec_agent.r53_r60_workpaper_lead_review_workflow import build_s5_gate
from test_r53_r60_workpaper_lead_review_workflow import seed_s5_fixture


def seed_s6_fixture(root: Path) -> None:
    seed_s5_fixture(root)
    assert build_s5_gate(root)["release_decision"] == "S5_L4_scope_pass"


def test_build_s6_projection_outputs_l4_scope_pass(tmp_path: Path) -> None:
    seed_s6_fixture(tmp_path)

    summary = build_s6_projection(tmp_path)

    assert summary["release_decision"] == "S6_L4_scope_pass"
    assert summary["closeout_level"] == "L4_scope_pass"
    assert summary["counts"]["gate_count"] == 8
    assert summary["counts"]["gate_fail_count"] == 0
    assert summary["counts"]["workbench_api_contracts_s6"] == len(workbench_frontdoor_schema_contract()["endpoints"])
    assert summary["projection"]["task_id"] == DEFAULT_TASK_ID
    assert summary["projection"]["claim_count"] >= 1
    assert summary["projection"]["gap_count"] >= 1
    assert summary["projection"]["event_count"] >= 1
    assert (tmp_path / summary["outputs"]["schema"]).exists()
    assert (tmp_path / summary["outputs"]["gate_rows"]).exists()
    assert (tmp_path / summary["outputs"]["summary"]).exists()
    assert (tmp_path / summary["outputs"]["closeout_report"]).exists()


def test_s6_gate_rows_ignore_later_slice_artifacts(tmp_path: Path) -> None:
    seed_s6_fixture(tmp_path)
    build_s6_projection(tmp_path)
    baseline_summary = build_s6_projection(tmp_path)
    baseline_projection_gate_count = baseline_summary["projection"]["gate_count"]
    s7_gate_rows = tmp_path / "data" / "manifests" / "r53_r60_s7_deliverable_studio_dashboard_gate_rows_v0_1.jsonl"
    s7_gate_rows.parent.mkdir(parents=True, exist_ok=True)
    s7_gate_rows.write_text(
        json.dumps(
            {
                "schema_version": "r53_r60_s7_deliverable_studio_dashboard_v0_1",
                "slice_id": "S7",
                "gate_id": "future_slice_gate_should_not_pollute_s6",
                "status": "pass",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    second_summary = build_s6_projection(tmp_path)

    assert second_summary["projection"]["gate_count"] == baseline_projection_gate_count


def test_s6_task_center_drilldown_review_and_ops_are_sql_final(tmp_path: Path) -> None:
    seed_s6_fixture(tmp_path)
    build_s6_projection(tmp_path)

    tasks = list_tasks(tmp_path)["tasks"]
    detail = get_task_detail(tmp_path, task_id=DEFAULT_TASK_ID)
    drilldown = get_task_drilldown(tmp_path, task_id=DEFAULT_TASK_ID)["drilldown"]
    queue = get_review_queue(tmp_path, task_id=DEFAULT_TASK_ID)
    ops = get_ops_projection(tmp_path, task_id=DEFAULT_TASK_ID)["ops"]

    assert tasks and tasks[0]["task_id"] == DEFAULT_TASK_ID
    assert detail["task"]["lead_review_status"] == "review_ready_with_visible_gaps"
    assert detail["task"]["judgment_status"] == "ready_for_writer"
    assert drilldown["sections"]
    assert drilldown["claims"]
    assert drilldown["gaps"]
    assert drilldown["gates"]
    assert drilldown["artifacts"]
    assert drilldown["events"]
    assert drilldown["context"]["injection_plans"] or drilldown["context"]["consumed_pack_refs"]
    assert queue["review_queue"]
    assert ops["trace_span_count"] >= 1
    assert ops["queue_status"] == "terminal"
    assert ops["rollback_ref"]
    assert "cost_amount" in ops


def test_s6_review_action_appends_workpaper_event_and_review_ledger(tmp_path: Path) -> None:
    seed_s6_fixture(tmp_path)
    build_s6_projection(tmp_path)
    db_path = default_s6_paths(tmp_path).db_path

    result = append_review_action(
        tmp_path,
        task_id=DEFAULT_TASK_ID,
        action="comment",
        comment="S6 deterministic reviewer note",
        reviewer_role="senior_analyst",
    )
    queue = get_review_queue(tmp_path, task_id=DEFAULT_TASK_ID)

    with sqlite3.connect(db_path) as conn:
        action_count = conn.execute(
            "select count(*) from workbench_review_actions_s6 where task_id = ?",
            (DEFAULT_TASK_ID,),
        ).fetchone()[0]
        workpaper_event_count = conn.execute(
            "select count(*) from workpaper_events where task_id = ? and event_type = ?",
            (DEFAULT_TASK_ID, "human_review_comment"),
        ).fetchone()[0]

    assert result["status"] == "ledgered"
    assert result["workpaper_event_id"]
    assert action_count == 1
    assert workpaper_event_count == 1
    assert queue["review_actions"][0]["comment"] == "S6 deterministic reviewer note"


def test_s6_backend_api_exposes_task_drilldown_and_review_actions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seed_s6_fixture(tmp_path)
    build_s6_projection(tmp_path)
    monkeypatch.setattr(workbench_app, "REPO_ROOT", tmp_path)
    client = TestClient(workbench_app.create_app(store_path=tmp_path / "workbench_api.sqlite"))

    task_center = client.get("/api/r53-r60/tasks")
    assert task_center.status_code == 200
    assert task_center.json()["tasks"][0]["task_id"] == DEFAULT_TASK_ID

    drilldown = client.get(f"/api/r53-r60/tasks/{DEFAULT_TASK_ID}/drilldown")
    assert drilldown.status_code == 200
    assert drilldown.json()["drilldown"]["claims"]

    ops = client.get(f"/api/r53-r60/tasks/{DEFAULT_TASK_ID}/ops")
    assert ops.status_code == 200
    assert ops.json()["ops"]["trace_span_count"] >= 1

    review = client.post(
        f"/api/r53-r60/tasks/{DEFAULT_TASK_ID}/review-actions",
        json={"action": "request_repair", "comment": "API ledgered repair request", "reviewer_role": "lead_analyst"},
    )
    assert review.status_code == 200
    assert review.json()["status"] == "ledgered"

    queue = client.get(f"/api/r53-r60/tasks/{DEFAULT_TASK_ID}/review-queue")
    assert queue.status_code == 200
    assert queue.json()["review_actions"][0]["comment"] == "API ledgered repair request"

    cancel = client.post(f"/api/r53-r60/tasks/{DEFAULT_TASK_ID}/cancel", json={"reason": "should fail closed"})
    assert cancel.status_code == 409
