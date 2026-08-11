from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from apps.workbench.backend.app import create_app
from apps.workbench.backend.application.case_service import CaseService
from sec_agent.canonical_runtime.models import canonical_digest


PROFILE_PATH = (
    REPO_ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_vt4_p36_candidate_profile_v1_0.json"
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


def _headers() -> dict[str, str]:
    return {
        "X-Fin-Case-Tenant": TENANT_ID,
        "X-Fin-Case-Project": PROJECT_ID,
        "X-Fin-Case-Actor": ACTOR_ID,
        "X-Fin-Case-Permissions": PERMISSIONS,
        "X-Trace-Id": "trace-vt4-p36-ten-cell",
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


def test_ten_cell_profile_runs_case_to_trace_and_restores_exactly(tmp_path: Path) -> None:
    profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    profile_digest = canonical_digest(profile)
    fixture_root = tmp_path / "canonical-runtime"
    workbench_path = tmp_path / "workbench.sqlite"
    service = CaseService.for_fixture_root(fixture_root, repo_root=REPO_ROOT)
    app = create_app(workbench_path, p02_case_service=service)

    with TestClient(app) as client:
        case = _post(
            client,
            "/api/v1/cases",
            {
                "query": "Assess the P36 AI infrastructure candidate profile",
                "as_of": "2026-07-18T00:00:00Z",
                "language": "en",
                "source_policy_ref": "fixture:internal-only",
                "idempotency_key": "vt4-case",
            },
        )
        plan = _post(
            client,
            f"/api/v1/cases/{case['case_id']}/planning/compile",
            {
                "expected_case_version": case["case_version"],
                "expected_summary_version": case["summary_version"],
                "compiler_policy_ref": profile["planning_profile"]["compiler_policy_ref"],
                "pack_selection_ref": profile["planning_profile"]["pack_selection_ref"],
                "actor_ref": ACTOR_ID,
                "idempotency_key": "vt4-plan",
            },
        )
        assert len(plan["cells"]) == 10
        assert {cell["decision_question"] for cell in plan["cells"]} == {
            row["decision_question"] for row in profile["planning_profile"]["cells"]
        }
        assert {
            slot["evidence_role"]
            for cell in plan["cells"]
            for slot in cell["evidence_slots"]
        } == set(profile["planning_profile"]["active_cell_roles"])
        accepted = _post(
            client,
            f"/api/v1/cases/{case['case_id']}/planning/checkpoint",
            {
                "decision": "accept",
                "expected_case_version": case["case_version"],
                "expected_decision_surface_contract_version": plan["contract_version"],
                "expected_checkpoint_version": plan["checkpoint_version"],
                "actor_ref": ACTOR_ID,
                "idempotency_key": "vt4-accept",
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
                "idempotency_key": "vt4-work-unit",
            },
        )
        evidence = _post(
            client,
            f"/api/v1/cases/{case['case_id']}/evidence/compile",
            {
                "expected_workspace_version": 0,
                "actor_ref": ACTOR_ID,
                "idempotency_key": "vt4-evidence",
            },
        )
        assert evidence["counts"]["slot_count"] == 10
        assert {slot["evidence_role"] for slot in evidence["slots"]} == set(
            profile["planning_profile"]["active_cell_roles"]
        )
        stored_evidence = service._facade.store.list_latest(
            "canonical_evidence_workbench_projection_versions", case_id=case["case_id"]
        )
        assert stored_evidence[0]["fixture_contract_digest"] == profile_digest

        counter_slot = next(
            slot
            for slot in evidence["slots"]
            if slot["evidence_role"] == "thesis_counterevidence"
        )
        requested = _post(
            client,
            f"/api/v1/cases/{case['case_id']}/evidence/slots/{counter_slot['evidence_slot_id']}/request-repair",
            {
                "expected_workspace_version": evidence["workspace_version"],
                "reason": "Resolve the bounded counterevidence fixture gap.",
                "actor_ref": ACTOR_ID,
                "idempotency_key": "vt4-repair-request",
            },
        )
        repaired = _post(
            client,
            f"/api/v1/cases/{case['case_id']}/evidence/slots/{counter_slot['evidence_slot_id']}/execute-repair",
            {
                "expected_workspace_version": requested["workspace_version"],
                "actor_ref": ACTOR_ID,
                "idempotency_key": "vt4-repair-execute",
            },
        )
        numeric = _post(
            client,
            f"/api/v1/cases/{case['case_id']}/integrity/numeric/compile",
            {
                "expected_evidence_workspace_version": repaired["workspace_version"],
                "actor_ref": ACTOR_ID,
                "idempotency_key": "vt4-numeric",
            },
        )
        assert len(numeric["facts"]) == 1
        workpaper = _post(
            client,
            f"/api/v1/cases/{case['case_id']}/workpaper/compile",
            {
                "expected_numeric_workspace_version": numeric["numeric_workspace_version"],
                "actor_ref": ACTOR_ID,
                "idempotency_key": "vt4-workpaper",
            },
        )
        assert len(workpaper["judgments"]) == 10
        assert all(len(judgment["remaining_gaps"]) == 1 for judgment in workpaper["judgments"])
        assert all(
            judgment["remaining_gaps"][0].startswith("Explicit gap:")
            for judgment in workpaper["judgments"]
        )
        stored_workpaper = service._facade.store.list_latest(
            "canonical_workpaper_projection_versions", case_id=case["case_id"]
        )[0]
        assert stored_workpaper["policy_config_refs"][-1] == f"contract:{profile_digest}"
        admitted = _post(
            client,
            f"/api/v1/cases/{case['case_id']}/workpaper/lead-review",
            {
                "expected_workpaper_version": workpaper["workpaper_version"],
                "expected_content_digest": workpaper["content_digest"],
                "decision": "admit_fixture_writer_preview",
                "reason": "Admit the fixture-only deterministic preview.",
                "actor_ref": ACTOR_ID,
                "idempotency_key": "vt4-lead-review",
            },
        )
        stored_lead_review = service._facade.store.list_latest(
            "canonical_lead_review_decision_versions", case_id=case["case_id"]
        )[0]
        assert stored_lead_review["policy_config_refs"][-1] == (
            f"contract:{profile_digest}"
        )
        preview = _post(
            client,
            f"/api/v1/cases/{case['case_id']}/deliverables",
            {
                "expected_workpaper_version": admitted["workpaper_version"],
                "expected_workpaper_content_digest": admitted["content_digest"],
                "writer_admission_id": admitted["writer_admission"]["writer_admission_id"],
                "actor_ref": ACTOR_ID,
                "idempotency_key": "vt4-deliverable",
            },
        )
        assert len(preview["material_claims"]) == 10
        assert all(len(claim["gap_refs"]) == 1 for claim in preview["material_claims"])
        assert all("Explicit gap:" in claim["gap_refs"][0] for claim in preview["material_claims"])
        stored_deliverable = service._facade.store.list_latest(
            "canonical_deliverable_projection_versions", case_id=case["case_id"]
        )[0]
        assert stored_deliverable["policy_config_refs"][-1] == f"contract:{profile_digest}"
        review = _post(
            client,
            f"/api/v1/artifacts/{preview['deliverable_id']}/versions/{preview['artifact_version']}/review-actions",
            {
                "expected_artifact_version": preview["artifact_version"],
                "expected_content_digest": preview["content_digest"],
                "expected_canonical_presentation_digest": preview[
                    "canonical_presentation_digest"
                ],
                "action_type": "accept_fixture_preview",
                "reason": "Accept the fixture preview for internal dogfood only.",
                "actor_ref": ACTOR_ID,
                "idempotency_key": "vt4-deliverable-review",
            },
        )
        stored_review = service._facade.store.list_latest(
            "canonical_deliverable_review_action_versions", case_id=case["case_id"]
        )[0]
        assert stored_review["policy_config_refs"][-1] == (
            f"contract:{profile_digest}"
        )
        trace = client.get(
            f"/api/v1/cases/{case['case_id']}/trace", headers=_headers()
        ).json()
        assert len(trace["claim_to_source"]) == 10
        assert all(trace["source_to_claim"][source_id] for source_id in trace["source_to_claim"])
        assert service._facade.store.list_latest(
            "canonical_attempts", case_id=case["case_id"]
        ) == []
        assert service._facade.store.list_latest(
            "canonical_artifact_versions", case_id=case["case_id"]
        ) == []

    reconstructed = CaseService.for_fixture_root(fixture_root, repo_root=REPO_ROOT)
    restored_app = create_app(workbench_path, p02_case_service=reconstructed)
    with TestClient(restored_app) as client:
        restored = client.get(
            f"/api/v1/cases/{case['case_id']}/deliverables", headers=_headers()
        )
        restored_trace = client.get(
            f"/api/v1/cases/{case['case_id']}/trace", headers=_headers()
        )
    assert restored.status_code == restored_trace.status_code == 200
    assert restored.json() == review
    assert restored_trace.json() == trace
