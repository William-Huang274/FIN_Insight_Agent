from __future__ import annotations

import json
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


CONTRACT_PATH = (
    REPO_ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_vt3_deliverable_review_trace_contract_v1_0.json"
)
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
        "deliverable:read",
        "deliverable:write",
        "deliverable_review:decide",
        "trace:read",
    )
)


def _contract() -> dict[str, Any]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


@pytest.fixture()
def runtime(tmp_path: Path) -> SimpleNamespace:
    fixture_root = tmp_path / "canonical-runtime"
    case_service = CaseService.for_fixture_root(fixture_root, repo_root=REPO_ROOT)
    app = create_app(
        tmp_path / "workbench.sqlite",
        p02_case_service=case_service,
        workbench_runtime_mode="fixture",
    )
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
        "X-Trace-Id": "trace-vt3-deliverable",
    }


def _post(
    client: TestClient,
    path: str,
    payload: dict[str, Any],
    expected: int = 202,
) -> dict[str, Any]:
    response = client.post(path, headers=_headers(), json=payload)
    assert response.status_code == expected, response.text
    return response.json()


def _admitted_workpaper(client: TestClient, key: str) -> tuple[dict[str, Any], dict[str, Any]]:
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
    slot_id = next(
        slot["evidence_slot_id"]
        for slot in evidence["slots"]
        if slot["evidence_role"] == "thesis_counterevidence"
    )
    repair_request = _post(
        client,
        f"/api/v1/cases/{case['case_id']}/evidence/slots/{slot_id}/request-repair",
        {
            "expected_workspace_version": evidence["workspace_version"],
            "reason": "Resolve the bounded counterevidence gap.",
            "actor_ref": ACTOR_ID,
            "idempotency_key": f"{key}-request-repair",
        },
    )
    repaired = _post(
        client,
        f"/api/v1/cases/{case['case_id']}/evidence/slots/{slot_id}/execute-repair",
        {
            "expected_workspace_version": repair_request["workspace_version"],
            "actor_ref": ACTOR_ID,
            "idempotency_key": f"{key}-execute-repair",
        },
    )
    numeric = _post(
        client,
        f"/api/v1/cases/{case['case_id']}/integrity/numeric/compile",
        {
            "expected_evidence_workspace_version": repaired["workspace_version"],
            "actor_ref": ACTOR_ID,
            "idempotency_key": f"{key}-numeric",
        },
    )
    workpaper = _post(
        client,
        f"/api/v1/cases/{case['case_id']}/workpaper/compile",
        {
            "expected_numeric_workspace_version": numeric["numeric_workspace_version"],
            "actor_ref": ACTOR_ID,
            "idempotency_key": f"{key}-workpaper",
        },
    )
    admitted = _post(
        client,
        f"/api/v1/cases/{case['case_id']}/workpaper/lead-review",
        {
            "expected_workpaper_version": workpaper["workpaper_version"],
            "expected_content_digest": workpaper["content_digest"],
            "decision": "admit_fixture_writer_preview",
            "reason": "Admit only the fixture preview; Writer execution remains prohibited.",
            "actor_ref": ACTOR_ID,
            "idempotency_key": f"{key}-lead-review",
        },
    )
    return case, admitted


def _compile_preview(
    client: TestClient, case_id: str, workpaper: dict[str, Any], key: str
) -> dict[str, Any]:
    payload = {
        "expected_workpaper_version": workpaper["workpaper_version"],
        "expected_workpaper_content_digest": workpaper["content_digest"],
        "writer_admission_id": workpaper["writer_admission"]["writer_admission_id"],
        "actor_ref": ACTOR_ID,
        "idempotency_key": f"{key}-preview",
    }
    path = f"/api/v1/cases/{case_id}/deliverables"
    preview = _post(client, path, payload)
    assert _post(client, path, payload) == preview
    return preview


def _review_payload(preview: dict[str, Any], action_type: str, key: str) -> dict[str, Any]:
    return {
        "expected_artifact_version": preview["artifact_version"],
        "expected_content_digest": preview["content_digest"],
        "expected_canonical_presentation_digest": preview["canonical_presentation_digest"],
        "action_type": action_type,
        "reason": f"Fixture review action: {action_type}.",
        "actor_ref": ACTOR_ID,
        "idempotency_key": key,
    }


def test_vt3_openapi_uses_the_exact_contract_wire_fields(runtime: SimpleNamespace) -> None:
    contract = _contract()
    schema = runtime.client.get("/openapi.json").json()
    expected_routes = {
        (row["method"].lower(), row["path"].replace("/api/v1", "")): row["operation"]
        for row in contract["routes"]
    }
    for (method, path), operation in expected_routes.items():
        assert schema["paths"][f"/api/v1{path}"][method]["operationId"] == operation
    assert "/api/v1/cases/{case_id}/deliverables/latest" not in schema["paths"]
    assert "/api/v1/cases/{case_id}/deliverables/compile-preview" not in schema["paths"]
    assert (
        "/api/v1/cases/{case_id}/deliverables/{artifact_version_id}/review"
        not in schema["paths"]
    )
    assert "/api/v1/cases/{case_id}/deliverables/{artifact_version_id}/trace" not in schema[
        "paths"
    ]
    components = schema["components"]["schemas"]
    assert list(components["CompileDeliverablePreviewCommand"]["properties"]) == contract[
        "wire_contract"
    ]["compile_command_fields"]
    assert list(components["ReviewDeliverableCommand"]["properties"]) == contract[
        "wire_contract"
    ]["review_command_fields"]
    assert list(components["DeliverablePreviewView"]["properties"]) == contract[
        "wire_contract"
    ]["deliverable_view_fields"]
    assert list(components["DeliverableTraceView"]["properties"]) == contract[
        "wire_contract"
    ]["trace_view_fields"]


def test_vt3_compiles_exact_wire_preview_and_bidirectional_trace(
    runtime: SimpleNamespace,
) -> None:
    contract = _contract()
    case, workpaper = _admitted_workpaper(runtime.client, "happy")
    preview = _compile_preview(runtime.client, case["case_id"], workpaper, "happy")

    assert list(preview) == contract["wire_contract"]["deliverable_view_fields"]
    assert preview["status"] == "fixture_preview_compiled"
    assert [section["section_id"] for section in preview["sections"]] == contract[
        "composer_contract"
    ]["writer_brief_sections"]
    assert {claim["claim_kind"] for claim in preview["material_claims"]} == {
        "fixture_demand_signal_judgment",
        "fixture_revenue_capture_judgment",
        "fixture_thesis_counterevidence_judgment",
    }
    for claim in preview["material_claims"]:
        assert list(claim) == contract["presentation_contract"]["required_claim_fields"]
        assert any(
            claim[field]
            for field in (
                "evidence_refs",
                "numeric_refs",
                "repair_outcome_refs",
                "gap_refs",
            )
        )
    for rendering in preview["renderings"].values():
        assert rendering["canonical_presentation_digest"] == preview[
            "canonical_presentation_digest"
        ]
        assert rendering["content_digest"] == canonical_digest(rendering["content"])
    for key, value in contract["hard_boundaries"].items():
        assert preview["hard_boundaries"][key] == value
    for key, value in contract["composer_contract"]["call_counts"].items():
        assert preview["hard_boundaries"][f"{key}_calls"] == value

    trace_path = f"/api/v1/cases/{case['case_id']}/trace"
    trace_response = runtime.client.get(trace_path, headers=_headers())
    assert trace_response.status_code == 200, trace_response.text
    trace = trace_response.json()
    assert list(trace) == contract["wire_contract"]["trace_view_fields"]
    assert trace["artifact_content_digest"] == preview["content_digest"]
    assert trace["canonical_presentation_digest"] == preview["canonical_presentation_digest"]
    assert {node["node_type"] for node in trace["nodes"]}.issubset(
        set(contract["trace_contract"]["allowed_node_types"])
    )
    for claim_id, source_ids in trace["claim_to_source"].items():
        assert source_ids
        for source_id in source_ids:
            assert claim_id in trace["source_to_claim"][source_id]
    replayed_trace = runtime.facade.replay_projection()["trace_manifests"][
        trace["manifest_id"]
    ]
    assert replayed_trace == {
        "artifact_version_id": preview["artifact_version_id"],
        "claim_count": len(trace["claim_to_source"]),
        "source_count": len(trace["source_to_claim"]),
    }
    assert set(trace["redaction_summary"]) >= set(contract["trace_contract"]["required_redactions"])
    assert runtime.facade.store.list_latest("canonical_attempts", case_id=case["case_id"]) == []
    assert runtime.facade.store.list_latest(
        "canonical_artifact_versions", case_id=case["case_id"]
    ) == []
    assert len(
        runtime.facade.store.list_latest(
            "canonical_deliverable_projection_versions", case_id=case["case_id"]
        )
    ) == 1
    assert len(
        runtime.facade.store.list_latest(
            "canonical_artifact_provenance_manifest_versions", case_id=case["case_id"]
        )
    ) == 1


def test_vt3_review_actions_are_exact_versioned_idempotent_and_fail_closed(
    runtime: SimpleNamespace,
) -> None:
    case, workpaper = _admitted_workpaper(runtime.client, "review")
    preview = _compile_preview(runtime.client, case["case_id"], workpaper, "review")
    review_path = (
        f"/api/v1/artifacts/{preview['deliverable_id']}/versions/"
        f"{preview['artifact_version']}/review-actions"
    )

    stale = runtime.client.post(
        review_path,
        headers=_headers(),
        json={
            **_review_payload(preview, "comment", "review-stale"),
            "expected_content_digest": "stale-content-digest",
        },
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["reason"] == "artifact_content_digest_mismatch"
    assert runtime.facade.store.list_latest(
        "canonical_deliverable_review_action_versions", case_id=case["case_id"]
    ) == []

    comment_payload = _review_payload(preview, "comment", "review-comment")
    commented = _post(runtime.client, review_path, comment_payload)
    assert _post(runtime.client, review_path, comment_payload) == commented
    assert [row["action_type"] for row in commented["review_actions"]] == ["comment"]

    return_payload = _review_payload(preview, "return_for_repair", "review-return")
    returned = _post(runtime.client, review_path, return_payload)
    assert returned["status"] == "return_for_repair"
    assert [row["action_type"] for row in returned["review_actions"]] == [
        "comment",
        "return_for_repair",
    ]
    blocked = runtime.client.post(
        review_path,
        headers=_headers(),
        json=_review_payload(preview, "comment", "review-after-terminal"),
    )
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["reason"] == "deliverable_review_terminal_action_exists"


def test_vt3_permissions_and_restart_restore_preview_actions_and_trace(
    runtime: SimpleNamespace,
) -> None:
    case, workpaper = _admitted_workpaper(runtime.client, "restore")
    compile_path = f"/api/v1/cases/{case['case_id']}/deliverables"
    denied = runtime.client.post(
        compile_path,
        headers=_headers(permissions=PERMISSIONS.replace(",deliverable:write", "")),
        json={
            "expected_workpaper_version": workpaper["workpaper_version"],
            "expected_workpaper_content_digest": workpaper["content_digest"],
            "writer_admission_id": workpaper["writer_admission"]["writer_admission_id"],
            "actor_ref": ACTOR_ID,
            "idempotency_key": "restore-denied",
        },
    )
    assert denied.status_code == 403
    assert denied.json()["detail"]["reason"] == "permission_denied"
    assert runtime.facade.store.list_latest(
        "canonical_deliverable_projection_versions", case_id=case["case_id"]
    ) == []

    preview = _compile_preview(runtime.client, case["case_id"], workpaper, "restore")
    review_path = (
        f"/api/v1/artifacts/{preview['deliverable_id']}/versions/"
        f"{preview['artifact_version']}/review-actions"
    )
    commented = _post(
        runtime.client,
        review_path,
        _review_payload(preview, "comment", "restore-comment"),
    )
    accepted = _post(
        runtime.client,
        review_path,
        _review_payload(preview, "accept_fixture_preview", "restore-accept"),
    )
    assert accepted["status"] == "accept_fixture_preview"
    assert [row["action_type"] for row in accepted["review_actions"]] == [
        "comment",
        "accept_fixture_preview",
    ]
    trace_path = f"/api/v1/cases/{case['case_id']}/trace"
    trace = runtime.client.get(trace_path, headers=_headers()).json()

    reconstructed = CaseService.for_fixture_root(runtime.fixture_root, repo_root=REPO_ROOT)
    app = create_app(
        runtime.workbench_path,
        p02_case_service=reconstructed,
        workbench_runtime_mode="fixture",
    )
    with TestClient(app) as client:
        latest = client.get(
            f"/api/v1/cases/{case['case_id']}/deliverables", headers=_headers()
        )
        restored_trace = client.get(trace_path, headers=_headers())
        denied_trace = client.get(
            trace_path,
            headers=_headers(permissions=PERMISSIONS.replace(",trace:read", "")),
        )
    assert latest.status_code == restored_trace.status_code == 200
    assert latest.json() == accepted
    assert restored_trace.json() == trace
    assert denied_trace.status_code == 403
    assert denied_trace.json()["detail"]["reason"] == "permission_denied"
