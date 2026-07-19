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


TENANT_ID = "fixture_internal"
PROJECT_ID = "workbench_internal"
ACTOR_ID = "analyst_internal"
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
        "evidence:repair",
        "numeric:read",
        "numeric:write",
        "workpaper:read",
        "workpaper:write",
        "lead_review:decide",
    )
)


@pytest.fixture()
def runtime(tmp_path: Path) -> SimpleNamespace:
    fixture_root = tmp_path / "canonical-runtime"
    case_service = CaseService.for_fixture_root(fixture_root, repo_root=REPO_ROOT)
    app = create_app(tmp_path / "workbench.sqlite", p02_case_service=case_service)
    with TestClient(app) as client:
        yield SimpleNamespace(
            client=client,
            facade=case_service._facade,
            fixture_root=fixture_root,
            workbench_path=tmp_path / "workbench.sqlite",
        )


def _headers(*, permissions: str = PERMISSIONS) -> dict[str, str]:
    return {
        "X-Fin-Case-Tenant": TENANT_ID,
        "X-Fin-Case-Project": PROJECT_ID,
        "X-Fin-Case-Actor": ACTOR_ID,
        "X-Fin-Case-Permissions": permissions,
        "X-Trace-Id": "trace-vt2-integrity",
    }


def _post(client: TestClient, path: str, payload: dict[str, Any], expected: int = 202) -> dict[str, Any]:
    response = client.post(path, headers=_headers(), json=payload)
    assert response.status_code == expected, response.text
    return response.json()


def _ready_evidence(client: TestClient, key: str) -> tuple[dict[str, Any], dict[str, Any]]:
    case = _post(
        client,
        "/api/v1/cases",
        {
            "query": "Assess the P36 AI infrastructure fixture",
            "as_of": "2026-07-18T00:00:00Z",
            "language": "en",
            "source_policy_ref": "fixture:internal-only",
            "idempotency_key": f"{key}-case",
        },
    )
    plan = _post(
        client,
        f"/api/v1/cases/{case['case_id']}/planning/compile",
        {
            "expected_case_version": case["case_version"],
            "expected_summary_version": case["summary_version"],
            "compiler_policy_ref": "fixture:p36-three-cell-v1",
            "pack_selection_ref": "fixture:p36-ai-infrastructure-v1",
            "actor_ref": ACTOR_ID,
            "idempotency_key": f"{key}-plan",
        },
    )
    accepted = _post(
        client,
        f"/api/v1/cases/{case['case_id']}/planning/checkpoint",
        {
            "decision": "accept",
            "expected_case_version": case["case_version"],
            "expected_decision_surface_contract_version": plan["contract_version"],
            "expected_checkpoint_version": plan["checkpoint_version"],
            "actor_ref": ACTOR_ID,
            "idempotency_key": f"{key}-accept",
        },
    )
    _post(
        client,
        f"/api/v1/cases/{case['case_id']}/work-units",
        {
            "work_unit_type": "p36_evidence_fixture_entry",
            "expected_case_version": case["case_version"],
            "input_head_digest": canonical_digest((accepted["contract_version_id"],)),
            "actor_ref": ACTOR_ID,
            "idempotency_key": f"{key}-work-unit",
        },
    )
    evidence = _post(
        client,
        f"/api/v1/cases/{case['case_id']}/evidence/compile",
        {
            "expected_workspace_version": 0,
            "actor_ref": ACTOR_ID,
            "idempotency_key": f"{key}-evidence",
        },
    )
    return case, evidence


def _request_repair(client: TestClient, case_id: str, evidence: dict[str, Any], key: str) -> tuple[str, dict[str, Any]]:
    slot_id = next(
        slot["evidence_slot_id"]
        for slot in evidence["slots"]
        if slot["evidence_role"] == "thesis_counterevidence"
    )
    requested = _post(
        client,
        f"/api/v1/cases/{case_id}/evidence/slots/{slot_id}/request-repair",
        {
            "expected_workspace_version": evidence["workspace_version"],
            "reason": "Resolve the bounded counterevidence gap.",
            "actor_ref": ACTOR_ID,
            "idempotency_key": f"{key}-request-repair",
        },
    )
    return slot_id, requested


def _execute_repair(client: TestClient, case_id: str, slot_id: str, requested: dict[str, Any], key: str) -> dict[str, Any]:
    return _post(
        client,
        f"/api/v1/cases/{case_id}/evidence/slots/{slot_id}/execute-repair",
        {
            "expected_workspace_version": requested["workspace_version"],
            "actor_ref": ACTOR_ID,
            "idempotency_key": f"{key}-execute-repair",
        },
    )


def test_vt2_happy_path_is_a_single_auditable_three_cell_product_chain(runtime: SimpleNamespace) -> None:
    case, evidence = _ready_evidence(runtime.client, "happy")
    slot_id, requested = _request_repair(runtime.client, case["case_id"], evidence, "happy")
    repaired = _execute_repair(runtime.client, case["case_id"], slot_id, requested, "happy")

    assert repaired["workspace_version"] == requested["workspace_version"] + 1
    assert repaired["counts"]["repair_completed_count"] == 1
    assert repaired["counts"]["typed_gap_count"] == 0
    assert repaired["repair_outcomes"][0]["attempt_state"] == "completed_fixture_no_retry"
    repaired_slot = next(row for row in repaired["slots"] if row["evidence_slot_id"] == slot_id)
    assert repaired_slot["display_state"] == "candidate"
    assert repaired_slot["typed_gap_codes"] == []

    numeric_payload = {
        "expected_evidence_workspace_version": repaired["workspace_version"],
        "actor_ref": ACTOR_ID,
        "idempotency_key": "happy-numeric",
    }
    numeric_path = f"/api/v1/cases/{case['case_id']}/integrity/numeric/compile"
    numeric = _post(runtime.client, numeric_path, numeric_payload)
    replayed_numeric = _post(runtime.client, numeric_path, numeric_payload)
    assert numeric == replayed_numeric
    assert numeric["status"] == "compiled_fixture"
    assert numeric["counts"] == {
        "fact_count": 1,
        "promoted_for_internal_fixture_count": 1,
    }
    fact = numeric["facts"][0]
    assert fact["normalized_value"] == "120000"
    assert fact["source_coordinate"] == "advanced_packaging_capacity_table:row:capacity_units"
    assert fact["promotion_status"] == "accepted_for_internal_fixture_judgment"
    assert fact["writer_citable"] is False

    workpaper_payload = {
        "expected_numeric_workspace_version": numeric["numeric_workspace_version"],
        "actor_ref": ACTOR_ID,
        "idempotency_key": "happy-workpaper",
    }
    workpaper_path = f"/api/v1/cases/{case['case_id']}/workpaper/compile"
    workpaper = _post(runtime.client, workpaper_path, workpaper_payload)
    assert _post(runtime.client, workpaper_path, workpaper_payload) == workpaper
    assert workpaper["status"] == "awaiting_lead_review"
    assert len(workpaper["judgments"]) == 3
    assert {row["evidence_role"] for row in workpaper["judgments"]} == {
        "demand_signal",
        "revenue_capture",
        "thesis_counterevidence",
    }
    counterevidence = next(
        row for row in workpaper["judgments"] if row["evidence_role"] == "thesis_counterevidence"
    )
    assert len(counterevidence["repair_outcome_refs"]) == 1

    review_payload = {
        "expected_workpaper_version": workpaper["workpaper_version"],
        "expected_content_digest": workpaper["content_digest"],
        "decision": "admit_fixture_writer_preview",
        "reason": "The exact fixture Workpaper is ready for a no-execution Writer preview.",
        "actor_ref": ACTOR_ID,
        "idempotency_key": "happy-lead-review",
    }
    review_path = f"/api/v1/cases/{case['case_id']}/workpaper/lead-review"
    reviewed = _post(runtime.client, review_path, review_payload)
    assert _post(runtime.client, review_path, review_payload) == reviewed
    assert reviewed["lead_review"]["content_digest"] == workpaper["content_digest"]
    assert reviewed["writer_admission"]["fixture_only"] is True
    assert reviewed["writer_admission"]["writer_execution_authorized"] is False

    for view in (numeric, workpaper, reviewed):
        for boundary in (
            "network_calls",
            "tool_invocations",
            "model_calls",
            "provider_calls",
            "writer_execution",
            "runtime_promotion",
            "release_evidence",
        ):
            assert view["hard_boundaries"][boundary] == 0
    assert runtime.facade.store.list_latest("canonical_attempts", case_id=case["case_id"]) == []
    assert runtime.facade.store.list_latest("canonical_artifact_versions", case_id=case["case_id"]) == []


def test_vt2_rejects_stale_versions_and_missing_permissions_without_side_effects(
    runtime: SimpleNamespace,
) -> None:
    case, evidence = _ready_evidence(runtime.client, "negative")
    slot_id, requested = _request_repair(runtime.client, case["case_id"], evidence, "negative")
    path = f"/api/v1/cases/{case['case_id']}/evidence/slots/{slot_id}/execute-repair"
    payload = {
        "expected_workspace_version": evidence["workspace_version"],
        "actor_ref": ACTOR_ID,
        "idempotency_key": "negative-stale-repair",
    }
    stale = runtime.client.post(path, headers=_headers(), json=payload)
    assert stale.status_code == 409
    assert stale.json()["detail"]["reason"] == "version_conflict"
    assert runtime.facade.store.list_latest(
        "canonical_evidence_repair_outcome_versions", case_id=case["case_id"]
    ) == []

    denied = runtime.client.post(
        path,
        headers=_headers(permissions=PERMISSIONS.replace(",evidence:repair", "")),
        json={
            "expected_workspace_version": requested["workspace_version"],
            "actor_ref": ACTOR_ID,
            "idempotency_key": "negative-denied-repair",
        },
    )
    assert denied.status_code == 403
    assert denied.json()["detail"]["reason"] == "permission_denied"


def test_vt2_state_restores_after_backend_reconstruction(runtime: SimpleNamespace) -> None:
    case, evidence = _ready_evidence(runtime.client, "restore")
    slot_id, requested = _request_repair(runtime.client, case["case_id"], evidence, "restore")
    repaired = _execute_repair(runtime.client, case["case_id"], slot_id, requested, "restore")
    numeric = _post(
        runtime.client,
        f"/api/v1/cases/{case['case_id']}/integrity/numeric/compile",
        {
            "expected_evidence_workspace_version": repaired["workspace_version"],
            "actor_ref": ACTOR_ID,
            "idempotency_key": "restore-numeric",
        },
    )
    workpaper = _post(
        runtime.client,
        f"/api/v1/cases/{case['case_id']}/workpaper/compile",
        {
            "expected_numeric_workspace_version": numeric["numeric_workspace_version"],
            "actor_ref": ACTOR_ID,
            "idempotency_key": "restore-workpaper",
        },
    )

    reconstructed = CaseService.for_fixture_root(runtime.fixture_root, repo_root=REPO_ROOT)
    app = create_app(runtime.workbench_path, p02_case_service=reconstructed)
    with TestClient(app) as client:
        evidence_read = client.get(
            f"/api/v1/cases/{case['case_id']}/evidence", headers=_headers()
        )
        numeric_read = client.get(
            f"/api/v1/cases/{case['case_id']}/integrity/numeric", headers=_headers()
        )
        workpaper_read = client.get(
            f"/api/v1/cases/{case['case_id']}/workpaper", headers=_headers()
        )
    assert evidence_read.status_code == numeric_read.status_code == workpaper_read.status_code == 200
    assert evidence_read.json()["workspace_version"] == repaired["workspace_version"]
    assert numeric_read.json() == numeric
    assert workpaper_read.json() == workpaper
