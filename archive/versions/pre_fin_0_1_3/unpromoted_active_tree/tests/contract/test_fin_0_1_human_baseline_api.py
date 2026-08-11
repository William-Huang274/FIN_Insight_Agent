from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from apps.workbench.backend.api.v1.human_baseline import build_human_baseline_router
from apps.workbench.backend.application.human_baseline_service import HumanBaselineService


class _CaseService:
    def get_case(self, case_id, principal):
        return {"case_id": case_id, "case_version": 7}


class _ResearchService:
    preview_digest = "preview-001"
    analysis_digest = "analysis-001"

    def preview(self, case_id, principal):
        return {"case_id": case_id, "preview_digest": self.preview_digest}

    def analysis_preview(self, case_id, principal):
        return {
            "case_id": case_id,
            "analysis_digest": self.analysis_digest,
            "workpaper": {"content_digest": "workpaper-001"},
            "writer": {"content_digest": "writer-001"},
        }


def _client(tmp_path):
    research = _ResearchService()
    service = HumanBaselineService(tmp_path / "human-baseline.sqlite3", _CaseService(), research)
    app = FastAPI()
    app.include_router(build_human_baseline_router(service), prefix="/api/v1")
    return TestClient(app), research, service


def _headers(*permissions: str) -> dict[str, str]:
    return {
        "X-Fin-Case-Tenant": "fixture_internal",
        "X-Fin-Case-Project": "workbench_internal",
        "X-Fin-Case-Actor": "human_tester",
        "X-Fin-Case-Permissions": ",".join(permissions),
    }


def _analyst_payload() -> dict[str, object]:
    return {
        "strongest_source": "Source A",
        "material_limitation": "Does not establish durability.",
        "numeric_verification": "Recalculated and matched.",
        "weakest_judgment": "Judgment 4",
        "required_modification": "Downgrade confidence.",
        "writer_usefulness_score": 4,
        "writer_usefulness_reason": "Useful as a bounded starting point.",
        "time_to_find_source_seconds": 30,
        "time_to_verify_numeric_seconds": 45,
        "time_to_identify_weakest_judgment_seconds": 60,
        "time_to_review_writer_seconds": 40,
        "repeated_work_count": 0,
        "blocking_ui_issue": "",
        "idempotency_key": "analyst-001",
    }


def _senior_payload() -> dict[str, object]:
    return {
        "reviewer_ref": "senior-001",
        "reviewer_role": "senior_analyst",
        "decision": "conditional_approve",
        "research_quality_score": 4,
        "evidence_quality_score": 4,
        "senior_reviewability_score": 4,
        "numeric_reproducibility_confirmed": True,
        "gap_boundaries_preserved": True,
        "exact_digest_confirmed": True,
        "review_comment": "Usable with the stated boundary.",
        "bounded_follow_up": ["Confirm demand durability."],
        "idempotency_key": "senior-001",
    }


def test_exact_human_baseline_records_bound_analyst_and_senior_evidence(tmp_path) -> None:
    client, _, service = _client(tmp_path)
    path = "/api/v1/cases/case-p36/human-baseline/sessions"

    started = client.post(
        path,
        headers=_headers("baseline:read", "baseline:write", "baseline:review"),
        json={"participant_ref": "analyst-001", "idempotency_key": "start-001"},
    )
    assert started.status_code == 201
    session = started.json()
    assert session["status"] == "in_progress"
    assert session["artifact_binding"]["case_version"] == 7
    assert session["execution_counts"]["case_mutations"] == 0

    session_id = session["session_id"]
    analyst = client.post(
        f"{path}/{session_id}/analyst-submission",
        headers=_headers("baseline:write"),
        json=_analyst_payload(),
    )
    assert analyst.status_code == 200
    assert analyst.json()["status"] == "analyst_submitted"

    senior = client.post(
        f"{path}/{session_id}/senior-review",
        headers=_headers("baseline:review"),
        json=_senior_payload(),
    )
    assert senior.status_code == 200
    completed = senior.json()
    assert completed["status"] == "exact_human_senior_review_recorded"
    assert completed["final_review_digest"]
    assert [event["event_type"] for event in completed["events"]] == [
        "baseline_started",
        "analyst_baseline_submitted",
        "exact_human_senior_review_recorded",
    ]

    with sqlite3.connect(service._store_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM human_baseline_events").fetchone()[0] == 3


def test_baseline_rejects_missing_permission_and_exact_candidate_drift(tmp_path) -> None:
    client, research, _ = _client(tmp_path)
    path = "/api/v1/cases/case-p36/human-baseline/sessions"
    denied = client.post(path, headers=_headers("baseline:read"), json={"participant_ref": "a", "idempotency_key": "s0"})
    assert denied.status_code == 403
    assert denied.json()["detail"]["reason"] == "permission_denied"

    started = client.post(
        path,
        headers=_headers("baseline:write"),
        json={"participant_ref": "analyst-001", "idempotency_key": "start-drift"},
    ).json()
    research.analysis_digest = "analysis-002"
    drifted = client.post(
        f"{path}/{started['session_id']}/analyst-submission",
        headers=_headers("baseline:write"),
        json=_analyst_payload(),
    )
    assert drifted.status_code == 409
    assert drifted.json()["detail"]["reason"] == "exact_candidate_drift"
