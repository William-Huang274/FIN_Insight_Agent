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
from apps.workbench.backend.application.execution_service import (
    ExecutionService,
    VT1_CANCEL_REASON,
    VT1_FENCING_TOKEN,
    VT1_WORK_UNIT_TYPE,
)
from sec_agent.canonical_runtime.models import canonical_digest


TENANT_ID = "tenant-vt1"
PROJECT_ID = "project-vt1"
ACTOR_ID = "analyst-vt1"
ALL_PERMISSIONS = ",".join(
    (
        "case:create",
        "case:read",
        "planning:write",
        "planning:review",
        "planning:read",
        "execution:write",
        "execution:read",
        "activity:read",
    )
)
BUSINESS_TABLES = (
    "canonical_research_cases",
    "canonical_case_control_versions",
    "canonical_decision_surface_contract_versions",
    "canonical_decision_surface_cell_versions",
    "canonical_evidence_slot_versions",
    "canonical_compile_gap_versions",
    "canonical_planning_checkpoint_versions",
)


@pytest.fixture()
def runtime(tmp_path: Path) -> SimpleNamespace:
    fixture_root = tmp_path / "canonical-runtime"
    case_service = CaseService.for_fixture_root(fixture_root, repo_root=REPO_ROOT)
    execution_service = ExecutionService.from_case_service(case_service)
    app = create_app(
        tmp_path / "workbench.sqlite",
        p02_case_service=case_service,
        p02_execution_service=execution_service,
    )
    with TestClient(app) as client:
        yield SimpleNamespace(
            client=client,
            fixture_root=fixture_root,
            case_service=case_service,
            facade=case_service._facade,
        )


def _headers(
    *,
    tenant_id: str = TENANT_ID,
    project_id: str = PROJECT_ID,
    actor_id: str = ACTOR_ID,
    permissions: str = ALL_PERMISSIONS,
) -> dict[str, str]:
    return {
        "X-Fin-Case-Tenant": tenant_id,
        "X-Fin-Case-Project": project_id,
        "X-Fin-Case-Actor": actor_id,
        "X-Fin-Case-Permissions": permissions,
    }


def _create_case(client: TestClient, *, key: str) -> dict[str, Any]:
    response = client.post(
        "/api/v1/cases",
        headers=_headers(),
        json={
            "query": "Assess the P36 AI infrastructure fixture",
            "as_of": "2026-07-18T00:00:00Z",
            "language": "en",
            "source_policy_ref": "fixture:internal-only",
            "idempotency_key": key,
        },
    )
    assert response.status_code == 202, response.text
    return response.json()


def _compile_plan(client: TestClient, case: dict[str, Any], *, key: str) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/cases/{case['case_id']}/planning/compile",
        headers=_headers(),
        json={
            "expected_case_version": case["case_version"],
            "expected_summary_version": case["summary_version"],
            "compiler_policy_ref": "fixture:p36-three-cell-v1",
            "pack_selection_ref": "fixture:p36-ai-infrastructure-v1",
            "actor_ref": ACTOR_ID,
            "idempotency_key": key,
        },
    )
    assert response.status_code == 202, response.text
    return response.json()


def _accept_plan(client: TestClient, case: dict[str, Any], plan: dict[str, Any], *, key: str) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/cases/{case['case_id']}/planning/checkpoint",
        headers=_headers(),
        json={
            "decision": "accept",
            "expected_case_version": case["case_version"],
            "expected_decision_surface_contract_version": plan["contract_version"],
            "expected_checkpoint_version": plan["checkpoint_version"],
            "actor_ref": ACTOR_ID,
            "idempotency_key": key,
        },
    )
    assert response.status_code == 202, response.text
    projection = response.json()
    assert projection["review_status"] == "accepted"
    return projection


def _accepted_case(client: TestClient, *, key: str) -> tuple[dict[str, Any], dict[str, Any]]:
    case = _create_case(client, key=f"{key}-case")
    plan = _compile_plan(client, case, key=f"{key}-compile")
    return case, _accept_plan(client, case, plan, key=f"{key}-accept")


def _create_command(case: dict[str, Any], plan: dict[str, Any], *, key: str) -> dict[str, Any]:
    return {
        "work_unit_type": VT1_WORK_UNIT_TYPE,
        "expected_case_version": case["case_version"],
        "input_head_digest": canonical_digest((plan["contract_version_id"],)),
        "actor_ref": ACTOR_ID,
        "idempotency_key": key,
    }


def _cancel_command(item: dict[str, Any], *, key: str) -> dict[str, Any]:
    return {
        "expected_work_unit_version": item["work_unit_version"],
        "expected_state_version": item["state_version"],
        "fencing_token": VT1_FENCING_TOKEN,
        "actor_ref": ACTOR_ID,
        "idempotency_key": key,
    }


def _business_snapshot(facade: Any) -> dict[str, list[dict[str, Any]]]:
    return {table: list(facade.store.list_versions(table)) for table in BUSINESS_TABLES}


def _object_files(root: Path) -> set[str]:
    objects = root / "objects"
    return {str(path.relative_to(objects)) for path in objects.rglob("*") if path.is_file()} if objects.exists() else set()


def test_create_requires_accepted_latest_plan_and_exact_digest(runtime: SimpleNamespace) -> None:
    case = _create_case(runtime.client, key="precondition-case")
    no_plan = runtime.client.post(
        f"/api/v1/cases/{case['case_id']}/work-units",
        headers=_headers(),
        json={
            "work_unit_type": VT1_WORK_UNIT_TYPE,
            "expected_case_version": case["case_version"],
            "input_head_digest": "0" * 64,
            "actor_ref": ACTOR_ID,
            "idempotency_key": "precondition-no-plan",
        },
    )
    assert no_plan.status_code == 409
    assert no_plan.json()["detail"]["reason"] == "accepted_planning_checkpoint_required"

    plan = _compile_plan(runtime.client, case, key="precondition-compile")
    command = _create_command(case, plan, key="precondition-create")

    rejected = runtime.client.post(
        f"/api/v1/cases/{case['case_id']}/work-units",
        headers=_headers(),
        json=command,
    )
    assert rejected.status_code == 409
    assert rejected.json()["detail"]["reason"] == "accepted_planning_checkpoint_required"
    assert runtime.facade.store.list_latest("canonical_work_units", case_id=case["case_id"]) == []

    accepted = _accept_plan(runtime.client, case, plan, key="precondition-accept")
    command = _create_command(case, accepted, key="precondition-create")
    wrong_digest = runtime.client.post(
        f"/api/v1/cases/{case['case_id']}/work-units",
        headers=_headers(),
        json={**command, "input_head_digest": "0" * 64},
    )
    assert wrong_digest.status_code == 409
    assert wrong_digest.json()["detail"]["reason"] == "input_head_digest_mismatch"

    created = runtime.client.post(
        f"/api/v1/cases/{case['case_id']}/work-units",
        headers=_headers(),
        json=command,
    )
    assert created.status_code == 202, created.text
    item = created.json()["work_units"][0]
    row = runtime.facade.store.get_latest("canonical_work_units", item["work_unit_id"])
    assert tuple(row["input_version_refs"]) == (accepted["contract_version_id"],)
    assert row["input_head_digest"] == canonical_digest((accepted["contract_version_id"],))


def test_enqueue_list_idempotency_and_no_attempt_artifact_external_or_business_write(
    runtime: SimpleNamespace,
) -> None:
    case, plan = _accepted_case(runtime.client, key="enqueue")
    command = _create_command(case, plan, key="enqueue-create")
    business_before = _business_snapshot(runtime.facade)
    objects_before = _object_files(runtime.fixture_root)

    first = runtime.client.post(
        f"/api/v1/cases/{case['case_id']}/work-units",
        headers=_headers(),
        json=command,
    )
    second = runtime.client.post(
        f"/api/v1/cases/{case['case_id']}/work-units",
        headers=_headers(),
        json=command,
    )
    different_key = runtime.client.post(
        f"/api/v1/cases/{case['case_id']}/work-units",
        headers=_headers(),
        json={**command, "idempotency_key": "enqueue-create-second-key"},
    )
    listed = runtime.client.get(
        f"/api/v1/cases/{case['case_id']}/work-units",
        headers=_headers(),
    )

    assert first.status_code == second.status_code == 202
    assert different_key.status_code == 409
    assert different_key.json()["detail"]["reason"] == "vt1_work_unit_already_exists"
    assert first.json() == second.json() == listed.json()
    assert set(listed.json()) == {"case_id", "work_units"}
    assert len(listed.json()["work_units"]) == 1
    item = listed.json()["work_units"][0]
    assert set(item) == {
        "work_unit_id",
        "work_unit_version",
        "state_version",
        "state",
        "input_head_digest",
    }
    assert item["state"] == "pending"
    assert item["work_unit_id"] == "wu_p02_5_" + canonical_digest(
        {
            "tenant_id": TENANT_ID,
            "project_id": PROJECT_ID,
            "case_id": case["case_id"],
            "contract_version_id": plan["contract_version_id"],
        }
    )[:24]
    events = [
        event
        for event in runtime.facade.store.list_events()
        if event.get("work_unit_id") == item["work_unit_id"]
    ]
    assert [event["event_type"] for event in events] == ["WORK_UNIT_CREATED"]
    assert runtime.facade.store.list_latest("canonical_attempts", case_id=case["case_id"]) == []
    assert runtime.facade.store.list_latest("canonical_artifact_versions", case_id=case["case_id"]) == []
    assert runtime.facade.replay_projection()["external_call_count"] == 0
    assert _business_snapshot(runtime.facade) == business_before
    assert _object_files(runtime.fixture_root) == objects_before


def test_cancel_typed_stop_is_idempotent_and_restores_with_recreated_service(
    runtime: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case, plan = _accepted_case(runtime.client, key="cancel")
    created = runtime.client.post(
        f"/api/v1/cases/{case['case_id']}/work-units",
        headers=_headers(),
        json=_create_command(case, plan, key="cancel-create"),
    )
    assert created.status_code == 202, created.text
    item = created.json()["work_units"][0]
    cancel_command = _cancel_command(item, key="cancel-command")
    cancel_envelopes = []
    runtime_cancel = runtime.facade.cancel_work_unit

    def record_cancel(command: Any) -> Any:
        cancel_envelopes.append(command)
        return runtime_cancel(command)

    monkeypatch.setattr(runtime.facade, "cancel_work_unit", record_cancel)

    first = runtime.client.post(
        f"/api/v1/cases/{case['case_id']}/work-units/{item['work_unit_id']}/cancel",
        headers=_headers(),
        json=cancel_command,
    )
    second = runtime.client.post(
        f"/api/v1/cases/{case['case_id']}/work-units/{item['work_unit_id']}/cancel",
        headers=_headers(),
        json=cancel_command,
    )
    assert first.status_code == second.status_code == 202
    assert first.json() == second.json()
    assert first.json()["work_units"][0]["state"] == "cancelled"
    assert len(cancel_envelopes) == 2
    assert all(
        envelope.payload["terminal_reason"] == VT1_CANCEL_REASON
        for envelope in cancel_envelopes
    )

    activity = runtime.client.get(
        f"/api/v1/cases/{case['case_id']}/activity",
        headers=_headers(),
    )
    assert activity.status_code == 200
    assert set(activity.json()) == {"case_id", "case_version", "events"}
    assert [event["event_type"] for event in activity.json()["events"]] == [
        "WORK_UNIT_CREATED",
        "WORK_UNIT_CANCELLED",
    ]
    assert activity.json()["events"][0]["typed_stop"] is None
    assert activity.json()["events"][1]["typed_stop"] == VT1_CANCEL_REASON

    restored_case_service = CaseService.for_fixture_root(runtime.fixture_root, repo_root=REPO_ROOT)
    restored_app = create_app(
        runtime.fixture_root / "restored-workbench.sqlite",
        p02_case_service=restored_case_service,
        p02_execution_service=ExecutionService.from_case_service(restored_case_service),
    )
    with TestClient(restored_app) as restored_client:
        restored_list = restored_client.get(
            f"/api/v1/cases/{case['case_id']}/work-units",
            headers=_headers(),
        )
        restored_activity = restored_client.get(
            f"/api/v1/cases/{case['case_id']}/activity",
            headers=_headers(),
        )
    assert restored_list.json() == first.json()
    assert restored_activity.json() == activity.json()
    assert runtime.facade.store.list_latest("canonical_attempts", case_id=case["case_id"]) == []
    assert runtime.facade.store.list_latest("canonical_artifact_versions", case_id=case["case_id"]) == []
    cancelled_events = [
        event
        for event in runtime.facade.store.list_events()
        if event.get("work_unit_id") == item["work_unit_id"] and event["event_type"] == "WORK_UNIT_CANCELLED"
    ]
    assert len(cancelled_events) == 1


def test_stale_permission_actor_scope_and_fencing_negatives(runtime: SimpleNamespace) -> None:
    case, plan = _accepted_case(runtime.client, key="negative")
    create_url = f"/api/v1/cases/{case['case_id']}/work-units"
    create_command = _create_command(case, plan, key="negative-create")

    stale_case = runtime.client.post(
        create_url,
        headers=_headers(),
        json={**create_command, "expected_case_version": case["case_version"] + 1},
    )
    denied_create = runtime.client.post(
        create_url,
        headers=_headers(permissions="execution:read"),
        json=create_command,
    )
    actor_mismatch = runtime.client.post(
        create_url,
        headers=_headers(),
        json={**create_command, "actor_ref": "other-analyst"},
    )
    cross_scope_create = runtime.client.post(
        create_url,
        headers=_headers(project_id="other-project"),
        json=create_command,
    )
    assert stale_case.status_code == 409
    assert denied_create.status_code == actor_mismatch.status_code == 403
    assert cross_scope_create.status_code == 404
    assert runtime.facade.store.list_latest("canonical_work_units", case_id=case["case_id"]) == []

    created = runtime.client.post(create_url, headers=_headers(), json=create_command)
    assert created.status_code == 202, created.text
    item = created.json()["work_units"][0]
    cancel_url = f"{create_url}/{item['work_unit_id']}/cancel"
    cancel_command = _cancel_command(item, key="negative-cancel")

    assert runtime.client.get(create_url, headers=_headers(permissions="execution:write")).status_code == 403
    assert runtime.client.get(create_url, headers=_headers(tenant_id="other-tenant")).status_code == 404
    assert runtime.client.post(
        cancel_url,
        headers=_headers(),
        json={**cancel_command, "expected_work_unit_version": item["work_unit_version"] + 1},
    ).status_code == 409
    assert runtime.client.post(
        cancel_url,
        headers=_headers(),
        json={**cancel_command, "expected_state_version": item["state_version"] + 1},
    ).status_code == 409
    assert runtime.client.post(
        cancel_url,
        headers=_headers(permissions="execution:read"),
        json=cancel_command,
    ).status_code == 403
    assert runtime.client.post(
        cancel_url,
        headers=_headers(),
        json={**cancel_command, "actor_ref": "other-analyst"},
    ).status_code == 403
    assert runtime.client.post(
        cancel_url,
        headers=_headers(project_id="other-project"),
        json=cancel_command,
    ).status_code == 404
    assert runtime.client.post(
        cancel_url,
        headers=_headers(),
        json={**cancel_command, "fencing_token": "not-a-lease"},
    ).status_code == 422
    assert runtime.client.get(
        f"/api/v1/cases/{case['case_id']}/activity",
        headers=_headers(permissions="execution:read"),
    ).status_code == 403
    assert runtime.client.get(
        f"/api/v1/cases/{case['case_id']}/activity",
        headers=_headers(project_id="other-project"),
    ).status_code == 404

    row = runtime.facade.store.get_latest("canonical_work_units", item["work_unit_id"])
    assert row["state"] == "pending"
    assert runtime.facade.store.list_latest("canonical_attempts", case_id=case["case_id"]) == []
    assert runtime.facade.store.list_latest("canonical_artifact_versions", case_id=case["case_id"]) == []
