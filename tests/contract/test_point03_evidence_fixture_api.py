from __future__ import annotations

from pathlib import Path
import sys
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from apps.workbench.backend.app import create_app
from apps.workbench.backend.application.case_service import CaseService
from sec_agent.canonical_runtime.models import canonical_digest


TENANT_ID = "tenant-point03"
PROJECT_ID = "project-point03"
ACTOR_ID = "analyst-point03"
PERMISSIONS = ",".join(
    (
        "case:create",
        "case:read",
        "planning:write",
        "planning:review",
        "planning:read",
        "execution:write",
        "execution:read",
        "evidence:read",
        "evidence:write",
        "evidence:review",
    )
)
UPSTREAM_TABLES = (
    "canonical_research_cases",
    "canonical_case_control_versions",
    "canonical_decision_surface_contract_versions",
    "canonical_decision_surface_cell_versions",
    "canonical_evidence_slot_versions",
    "canonical_planning_checkpoint_versions",
    "canonical_work_units",
    "canonical_attempts",
    "canonical_artifact_versions",
)


@pytest.fixture()
def runtime(tmp_path: Path) -> SimpleNamespace:
    fixture_root = tmp_path / "canonical-runtime"
    case_service = CaseService.for_fixture_root(fixture_root, repo_root=REPO_ROOT)
    app = create_app(tmp_path / "workbench.sqlite", p02_case_service=case_service)
    with TestClient(app) as client:
        yield SimpleNamespace(client=client, facade=case_service._facade)


def _headers(*, permissions: str = PERMISSIONS, project_id: str = PROJECT_ID) -> dict[str, str]:
    return {
        "X-Fin-Case-Tenant": TENANT_ID,
        "X-Fin-Case-Project": project_id,
        "X-Fin-Case-Actor": ACTOR_ID,
        "X-Fin-Case-Permissions": permissions,
        "X-Trace-Id": "trace-point03-evidence",
    }


def _create_case(client: TestClient, key: str) -> dict[str, Any]:
    response = client.post(
        "/api/v1/cases",
        headers=_headers(),
        json={
            "query": "Assess the P36 AI infrastructure fixture",
            "as_of": "2026-07-18T00:00:00Z",
            "language": "en",
            "source_policy_ref": "fixture:internal-only",
            "idempotency_key": f"{key}-case",
        },
    )
    assert response.status_code == 202, response.text
    return response.json()


def _compile_plan(client: TestClient, case: dict[str, Any], key: str) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/cases/{case['case_id']}/planning/compile",
        headers=_headers(),
        json={
            "expected_case_version": case["case_version"],
            "expected_summary_version": case["summary_version"],
            "compiler_policy_ref": "fixture:p36-three-cell-v1",
            "pack_selection_ref": "fixture:p36-ai-infrastructure-v1",
            "actor_ref": ACTOR_ID,
            "idempotency_key": f"{key}-plan",
        },
    )
    assert response.status_code == 202, response.text
    return response.json()


def _accept_plan(client: TestClient, case: dict[str, Any], plan: dict[str, Any], key: str) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/cases/{case['case_id']}/planning/checkpoint",
        headers=_headers(),
        json={
            "decision": "accept",
            "expected_case_version": case["case_version"],
            "expected_decision_surface_contract_version": plan["contract_version"],
            "expected_checkpoint_version": plan["checkpoint_version"],
            "actor_ref": ACTOR_ID,
            "idempotency_key": f"{key}-accept",
        },
    )
    assert response.status_code == 202, response.text
    return response.json()


def _create_work_unit(client: TestClient, case: dict[str, Any], plan: dict[str, Any], key: str) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/cases/{case['case_id']}/work-units",
        headers=_headers(),
        json={
            "work_unit_type": "p36_evidence_fixture_entry",
            "expected_case_version": case["case_version"],
            "input_head_digest": canonical_digest((plan["contract_version_id"],)),
            "actor_ref": ACTOR_ID,
            "idempotency_key": f"{key}-work-unit",
        },
    )
    assert response.status_code == 202, response.text
    return response.json()["work_units"][0]


def _ready_case(client: TestClient, key: str) -> tuple[dict[str, Any], dict[str, Any]]:
    case = _create_case(client, key)
    plan = _compile_plan(client, case, key)
    accepted = _accept_plan(client, case, plan, key)
    _create_work_unit(client, case, accepted, key)
    return case, accepted


def _compile_evidence(client: TestClient, case_id: str, key: str = "evidence-compile") -> Any:
    return client.post(
        f"/api/v1/cases/{case_id}/evidence/compile",
        headers=_headers(),
        json={
            "expected_workspace_version": 0,
            "actor_ref": ACTOR_ID,
            "idempotency_key": key,
        },
    )


def _snapshot(facade: Any) -> dict[str, list[dict[str, Any]]]:
    return {table: list(facade.store.list_versions(table)) for table in UPSTREAM_TABLES}


def test_compile_requires_accepted_plan_and_exactly_one_pending_work_unit(runtime: SimpleNamespace) -> None:
    case = _create_case(runtime.client, "entry")
    no_plan = _compile_evidence(runtime.client, case["case_id"], "entry-no-plan")
    assert no_plan.status_code == 409

    plan = _compile_plan(runtime.client, case, "entry")
    not_accepted = _compile_evidence(runtime.client, case["case_id"], "entry-not-accepted")
    assert not_accepted.status_code == 409

    accepted = _accept_plan(runtime.client, case, plan, "entry")
    no_work_unit = _compile_evidence(runtime.client, case["case_id"], "entry-no-work-unit")
    assert no_work_unit.status_code == 409
    assert no_work_unit.json()["detail"]["reason"] == (
        "exactly_one_pending_evidence_fixture_work_unit_required"
    )

    _create_work_unit(runtime.client, case, accepted, "entry")
    compiled = _compile_evidence(runtime.client, case["case_id"], "entry-compile")
    assert compiled.status_code == 202, compiled.text


def test_compile_persists_ui_ready_immutable_fixture_without_execution_or_case_mutation(
    runtime: SimpleNamespace,
) -> None:
    case, _ = _ready_case(runtime.client, "compile")
    before = _snapshot(runtime.facade)
    command_key = "compile-evidence-idempotent"

    first = _compile_evidence(runtime.client, case["case_id"], command_key)
    second = _compile_evidence(runtime.client, case["case_id"], command_key)
    read = runtime.client.get(f"/api/v1/cases/{case['case_id']}/evidence", headers=_headers())

    assert first.status_code == second.status_code == 202
    assert read.status_code == 200
    assert first.json() == second.json() == read.json()
    view = first.json()
    assert view["workspace_version"] == 1
    assert view["fixture_mode"] == "fixture_shadow_internal_only"
    assert view["available_actions"] == [
        "reject_candidate",
        "request_repair",
        "execute_repair",
    ]
    assert view["counts"] == {
        "slot_count": 3,
        "total_candidate_count": 4,
        "candidate_count": 2,
        "context_only_count": 2,
        "rejected_count": 0,
        "typed_gap_count": 1,
        "repair_requested_count": 0,
        "repair_completed_count": 0,
        "review_action_count": 0,
    }
    by_role = {slot["evidence_role"]: slot for slot in view["slots"]}
    assert set(by_role) == {"demand_signal", "revenue_capture", "thesis_counterevidence"}
    assert by_role["thesis_counterevidence"]["display_state"] == "typed_gap"
    assert by_role["thesis_counterevidence"]["typed_gap_codes"] == ["candidate_metadata_absent"]
    candidate = by_role["demand_signal"]["candidates"][0]
    assert candidate["source_authority"] == "official_filing_fixture"
    assert candidate["citation"]
    assert candidate["excerpt"]
    assert candidate["applicability_boundary"]
    assert candidate["promotion_boundary"] == "not_in_Point03_VT1"
    for key in (
        "retrieval_execution",
        "tool_invocation",
        "network_calls",
        "model_calls",
        "provider_calls",
        "attempts",
        "artifacts",
    ):
        assert view["hard_boundaries"][key] == 0

    assert _snapshot(runtime.facade) == before
    assert len(runtime.facade.store.list_versions("canonical_evidence_workbench_projection_versions")) == 1
    assert runtime.facade.store.list_versions("canonical_evidence_review_action_versions") == []
    assert runtime.facade.store.list_latest("canonical_attempts", case_id=case["case_id"]) == []
    assert runtime.facade.store.list_latest("canonical_artifact_versions", case_id=case["case_id"]) == []
    events = [
        event
        for event in runtime.facade.store.list_events()
        if event["event_type"].startswith("EVIDENCE_")
    ]
    assert [event["event_type"] for event in events] == ["EVIDENCE_FIXTURE_COMPILED"]


def test_reject_and_repair_are_append_only_idempotent_and_exact_versioned(runtime: SimpleNamespace) -> None:
    case, _ = _ready_case(runtime.client, "review")
    compiled = _compile_evidence(runtime.client, case["case_id"], "review-compile").json()
    candidate_id = compiled["slots"][0]["candidates"][0]["candidate_id"]
    gap_slot_id = next(
        slot["evidence_slot_id"] for slot in compiled["slots"] if slot["display_state"] == "typed_gap"
    )
    reject_payload = {
        "expected_workspace_version": 1,
        "reason": "Candidate is too indirect for this slot.",
        "actor_ref": ACTOR_ID,
        "idempotency_key": "review-reject",
    }
    reject_url = f"/api/v1/cases/{case['case_id']}/evidence/candidates/{candidate_id}/reject"

    rejected = runtime.client.post(reject_url, headers=_headers(), json=reject_payload)
    replayed = runtime.client.post(reject_url, headers=_headers(), json=reject_payload)
    assert rejected.status_code == replayed.status_code == 202
    assert rejected.json() == replayed.json()
    assert rejected.json()["workspace_version"] == 2
    assert rejected.json()["counts"]["rejected_count"] == 1

    stale = runtime.client.post(
        f"/api/v1/cases/{case['case_id']}/evidence/slots/{gap_slot_id}/request-repair",
        headers=_headers(),
        json={
            "expected_workspace_version": 1,
            "reason": "Stale request",
            "actor_ref": ACTOR_ID,
            "idempotency_key": "review-stale-repair",
        },
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["reason"] == "version_conflict"

    repaired = runtime.client.post(
        f"/api/v1/cases/{case['case_id']}/evidence/slots/{gap_slot_id}/request-repair",
        headers=_headers(),
        json={
            "expected_workspace_version": 2,
            "reason": "Add an official policy counterevidence fixture.",
            "actor_ref": ACTOR_ID,
            "idempotency_key": "review-repair",
        },
    )
    assert repaired.status_code == 202, repaired.text
    view = repaired.json()
    assert view["workspace_version"] == 3
    assert view["counts"]["repair_requested_count"] == 1
    assert view["counts"]["review_action_count"] == 2
    assert next(slot for slot in view["slots"] if slot["evidence_slot_id"] == gap_slot_id)[
        "display_state"
    ] == "repair_requested"
    assert len(runtime.facade.store.list_versions("canonical_evidence_workbench_projection_versions")) == 1
    assert len(runtime.facade.store.list_versions("canonical_evidence_review_action_versions")) == 2
    event_types = [
        event["event_type"]
        for event in runtime.facade.store.list_events()
        if event["event_type"].startswith("EVIDENCE_")
    ]
    assert event_types == [
        "EVIDENCE_FIXTURE_COMPILED",
        "EVIDENCE_CANDIDATE_REJECTED",
        "EVIDENCE_REPAIR_REQUESTED",
    ]
    replay = runtime.facade.replay_projection()
    workspace = replay["evidence_workspaces"][view["workspace_id"]]
    assert workspace["workspace_version"] == 3
    assert len(workspace["review_action_ids"]) == 2
    assert replay["external_call_count"] == 0


def test_permissions_scope_and_openapi_expose_no_accept_or_promotion(runtime: SimpleNamespace) -> None:
    case, _ = _ready_case(runtime.client, "permissions")
    denied = _compile_evidence(runtime.client, case["case_id"], "permissions-denied")
    assert denied.status_code == 202
    candidate_id = denied.json()["slots"][0]["candidates"][0]["candidate_id"]
    action_count = len(runtime.facade.store.list_versions("canonical_evidence_review_action_versions"))

    assert runtime.client.get(
        f"/api/v1/cases/{case['case_id']}/evidence",
        headers=_headers(permissions="evidence:write"),
    ).status_code == 403
    assert runtime.client.post(
        f"/api/v1/cases/{case['case_id']}/evidence/candidates/{candidate_id}/reject",
        headers=_headers(permissions="evidence:read"),
        json={
            "expected_workspace_version": 1,
            "reason": "Denied",
            "actor_ref": ACTOR_ID,
            "idempotency_key": "permissions-review-denied",
        },
    ).status_code == 403
    assert runtime.client.get(
        f"/api/v1/cases/{case['case_id']}/evidence",
        headers=_headers(project_id="other-project"),
    ).status_code == 404
    assert len(runtime.facade.store.list_versions("canonical_evidence_review_action_versions")) == action_count

    paths = runtime.client.get("/openapi.json").json()["paths"]
    assert paths[f"/api/v1/cases/{{case_id}}/evidence"]["get"]["operationId"] == "getEvidenceWorkbench"
    assert paths[f"/api/v1/cases/{{case_id}}/evidence/compile"]["post"]["operationId"] == "compileEvidenceFixture"
    assert paths[f"/api/v1/cases/{{case_id}}/evidence/candidates/{{candidate_id}}/reject"]["post"][
        "operationId"
    ] == "rejectEvidenceCandidate"
    assert paths[f"/api/v1/cases/{{case_id}}/evidence/slots/{{evidence_slot_id}}/request-repair"][
        "post"
    ]["operationId"] == "requestEvidenceRepair"
    assert all("accept" not in path and "promot" not in path for path in paths if "/api/v1/cases/" in path)
