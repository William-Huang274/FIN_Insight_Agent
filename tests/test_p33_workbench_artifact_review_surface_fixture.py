from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sec_agent.p33_workbench_artifact_review_surface_fixture import (
    CONTRACT_ID,
    RELEASE_DECISION_PASS,
    build_p33_workbench_artifact_review_surface_fixture,
    default_p33_workbench_artifact_review_surface_fixture_paths,
)
from sec_agent.r53_r60_workbench_frontdoor_drilldown import DEFAULT_TASK_ID, default_s6_paths
from test_r53_r60_workbench_frontdoor_drilldown import seed_s6_fixture


def test_p33_workbench_fixture_outputs_l4_scope_pass(tmp_path: Path) -> None:
    seed_s6_fixture(tmp_path)

    manifest = build_p33_workbench_artifact_review_surface_fixture(tmp_path)
    paths = default_p33_workbench_artifact_review_surface_fixture_paths(tmp_path)

    assert manifest["status"] == "pass"
    assert manifest["contract_id"] == CONTRACT_ID
    assert manifest["release_decision"] == RELEASE_DECISION_PASS
    assert manifest["closeout_level"] == "L4_scope_pass"
    assert manifest["promotion_recommendation"] == "active_registry_ready_runtime_alignment_only"
    assert manifest["gate_fail_count"] == 0
    assert paths.manifest_path.exists()
    assert paths.report_path.exists()


def test_p33_fixture_review_actions_are_targeted_append_only_and_idempotent(tmp_path: Path) -> None:
    seed_s6_fixture(tmp_path)

    first = build_p33_workbench_artifact_review_surface_fixture(tmp_path)
    second = build_p33_workbench_artifact_review_surface_fixture(tmp_path)
    audit = second["review_action_audit"]

    assert first["release_decision"] == RELEASE_DECISION_PASS
    assert second["release_decision"] == RELEASE_DECISION_PASS
    assert audit["fixture_action_count"] == 3
    assert audit["all_required_actions_present"] is True
    assert audit["rows_with_workpaper_event_count"] == 3
    assert audit["rows_with_target_count"] == 3

    with sqlite3.connect(default_s6_paths(tmp_path).db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            select action, payload_json, workpaper_event_id
            from workbench_review_actions_s6
            where reviewer_role = 'p33_fixture_reviewer'
            order by action
            """
        ).fetchall()
        event_count = conn.execute(
            """
            select count(*)
            from workpaper_events
            where task_id = ? and event_type in (
                'human_review_accept',
                'human_review_reject',
                'human_review_supersede'
            )
            """,
            (DEFAULT_TASK_ID,),
        ).fetchone()[0]

    assert {row["action"] for row in rows} == {"accept", "reject", "supersede"}
    assert event_count == 3


def test_p33_traceability_covers_claim_gap_gate_artifact_deliverable_dashboard(tmp_path: Path) -> None:
    seed_s6_fixture(tmp_path)

    manifest = build_p33_workbench_artifact_review_surface_fixture(tmp_path)
    trace = manifest["traceability_audit"]

    assert trace["claim_with_selected_evidence_count"] >= 1
    assert trace["typed_gap_count"] >= 1
    assert trace["gate_count"] >= 1
    assert trace["artifact_count"] >= 1
    assert trace["judgment_claim_refs_covered"] is True
    assert trace["judgment_gap_refs_covered"] is True
    assert trace["deliverable_artifact_refs_covered"] is True
    assert trace["dashboard_artifact_refs_covered"] is True


def test_p33_fixture_reuse_existing_outputs_without_rebuild(tmp_path: Path) -> None:
    seed_s6_fixture(tmp_path)
    first = build_p33_workbench_artifact_review_surface_fixture(tmp_path, rebuild_dependencies=True)

    second = build_p33_workbench_artifact_review_surface_fixture(tmp_path, rebuild_dependencies=False)

    assert first["release_decision"] == RELEASE_DECISION_PASS
    assert second["release_decision"] == RELEASE_DECISION_PASS


def test_workbench_backend_accepts_p33_review_action_semantics(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    import apps.workbench.backend.app as workbench_app

    seed_s6_fixture(tmp_path)
    build_p33_workbench_artifact_review_surface_fixture(tmp_path)
    monkeypatch.setattr(workbench_app, "REPO_ROOT", tmp_path)
    client = TestClient(workbench_app.create_app(store_path=tmp_path / "workbench_api.sqlite"))

    for action in ["accept", "reject", "supersede"]:
        response = client.post(
            f"/api/r53-r60/tasks/{DEFAULT_TASK_ID}/review-actions",
            json={"action": action, "comment": f"API {action}", "reviewer_role": "lead_analyst"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "ledgered"
