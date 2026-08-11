from __future__ import annotations

import importlib.util
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest


pytestmark = pytest.mark.fast_contract
ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("point01_m4_closeout_gate", ROOT / "scripts/engineering/run_point01_m4_closeout_gate.py")
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
FIXTURE_SPEC = importlib.util.spec_from_file_location("point01_m4_cutover_fixtures", ROOT / "scripts/engineering/run_point01_m4_cutover_fixtures.py")
assert FIXTURE_SPEC and FIXTURE_SPEC.loader
FIXTURES = importlib.util.module_from_spec(FIXTURE_SPEC)
FIXTURE_SPEC.loader.exec_module(FIXTURES)


def _snapshot(store_path: Path, destination: Path) -> None:
    with sqlite3.connect(store_path) as source, sqlite3.connect(destination) as backup:
        source.backup(backup)


def _store_backed_records(tmp_path: Path) -> tuple[dict, dict, Path, Path]:
    store, _, service = FIXTURES._runtime(tmp_path / "pilot-store")
    request = FIXTURES._request(store, datetime.now(timezone.utc))
    eligibility = service.evaluate_eligibility(request.scope, consumer_inventory_complete=True, legacy_projection_ready=True)
    service.request_cutover(request, eligibility, actor_snapshot_ref="pilot-actor", permission_snapshot_ref="pilot-permission", correlation_id="pilot-correlation")
    service.execute_cutover(request, actor_snapshot_ref="pilot-actor", permission_snapshot_ref="pilot-permission", correlation_id="pilot-correlation")
    service.rollback_cutover(request, reason="deterministic_closeout_fixture", actor_snapshot_ref="pilot-actor", permission_snapshot_ref="pilot-permission", correlation_id="pilot-correlation")
    backup_path = tmp_path / "pilot-backup.sqlite"
    _snapshot(store.db_path, backup_path)
    backup_sha256 = MODULE._sha256(backup_path)
    approval = {
        "status": "approved",
        "approval_id": request.approval.approval_id,
        "approval_registry_ref": request.approval.approval_registry_ref,
        "approver_type": "human",
        "approver_identity": "deterministic-reviewer",
        "approved_at": "2026-07-12T00:00:00+00:00",
        "decision": "approve_case_scoped_planning_cutover_only",
        "approved_case_scope": request.scope.case_id,
        "approved_lane_id": request.scope.lane_id,
        "approved_store_identity": store.store_identity(),
        "approved_contract_version_id": request.contract_version_id,
        "approved_contract_digest": request.contract_digest,
        "approved_artifact_version_id": request.artifact_version_id,
        "approved_artifact_digest": request.artifact_digest,
        "approved_comparison_id": request.comparison_id,
        "approved_comparison_digest": request.comparison_digest,
        "backup_snapshot_sha256": backup_sha256,
        "rollback_window": "15m",
        "kill_switch_state": "off_before_cutover",
        "impact_scope": "case_scoped_planning_only",
        "approval_revocation_registry_ref": request.approval.approval_registry_ref,
        "authority_boundary_acknowledged": {"legacy_task_run": "authoritative", "canonical_lane": "case_scoped_planning_only_after_approval", "cutover": "m4_case_scoped_only"},
        "rollback_acknowledged": True,
    }
    evidence = {
        "status": "pass",
        "tenant_id": request.scope.tenant_id,
        "project_id": request.scope.project_id,
        "case_id": request.scope.case_id,
        "lane_id": request.scope.lane_id,
        "persistent_store_identity": store.store_identity(),
        "approval_id": request.approval.approval_id,
        "approval_registry_ref": request.approval.approval_registry_ref,
        "cutover_id": request.cutover_id,
        "request_digest": request.request_digest,
        "cutover_decision_ref": f"{request.cutover_id}:v2",
        "rollback_decision_ref": f"{request.cutover_id}:v3",
        "contract_version_id": request.contract_version_id,
        "contract_digest": request.contract_digest,
        "artifact_version_id": request.artifact_version_id,
        "artifact_digest": request.artifact_digest,
        "comparison_id": request.comparison_id,
        "comparison_digest": request.comparison_digest,
        "backup_snapshot_sha256": backup_sha256,
        "backup_restore_mode": "post_rollback_audit",
        "rollback_window": "15m",
        "kill_switch_state": "off_before_cutover",
        "impact_scope": "case_scoped_planning_only",
        "authority_before": "legacy",
        "authority_after_cutover": "canonical_for_lane",
        "authority_after_rollback": "legacy",
        "authority_event_types": list(MODULE.REQUIRED_AUTHORITY_EVENTS),
    }
    return approval, evidence, store.db_path, backup_path


def test_m4_closeout_fails_closed_until_case_pilot_approval_after_design_confirmation(tmp_path: Path) -> None:
    manifest = json.loads((ROOT / "configs/engineering_handoff/point01_m4_closeout_gate_manifest_v1_0.json").read_text(encoding="utf-8"))
    result = MODULE.build_result(manifest, work_root=tmp_path)
    assert result["status"] == "fail_closed"
    assert "human_pilot_approval_pending" in result["unmet_conditions"]
    assert "real_case_pilot_execution_pending" in result["unmet_conditions"]
    assert "store_backed_pilot_verification_pending" in result["unmet_conditions"]
    assert "m4_0_design_review_user_confirmation_pending" not in result["unmet_conditions"]
    assert all(result["required_point_statuses"][f"M4.{number}"] == "pass" for number in range(1, 8))


def test_m4_pilot_approval_contract_requires_human_case_scope_and_rollback_acknowledgment() -> None:
    pending = json.loads((ROOT / "configs/engineering_handoff/point01_m4_human_pilot_approval_v1_0.json").read_text(encoding="utf-8"))
    assert MODULE._pilot_approval_errors(pending) == ["human_pilot_approval_pending"]
    approved = {**pending, "status": "approved", "approval_id": "approval-x", "approval_registry_ref": "hil-approval-x", "approver_type": "human", "approver_identity": "reviewer", "approved_at": "2026-07-12T22:00:00+08:00", "decision": "approve_case_scoped_planning_cutover_only", "approved_case_scope": "case-x", "approved_lane_id": "planning", "approved_store_identity": "store-sha256:example", "approved_contract_version_id": "contract-x:v1", "approved_contract_digest": "contract-sha256:example", "approved_artifact_version_id": "artifact-x:v1", "approved_artifact_digest": "artifact-sha256:example", "approved_comparison_id": "comparison-x", "approved_comparison_digest": "comparison-sha256:example", "backup_snapshot_sha256": "backup-sha256:example", "rollback_window": "15m", "kill_switch_state": "off_before_cutover", "impact_scope": "case_scoped_planning_only", "approval_revocation_registry_ref": "hil-approval-x"}
    assert MODULE._pilot_approval_errors(approved) == []


def test_m4_pilot_execution_contract_requires_persistent_cutover_and_rollback_evidence() -> None:
    pending = json.loads((ROOT / "configs/engineering_handoff/point01_m4_pilot_execution_evidence_v1_0.json").read_text(encoding="utf-8"))
    assert MODULE._pilot_execution_errors(pending) == ["real_case_pilot_execution_pending"]
    passed = {
        **pending,
        "status": "pass",
        "tenant_id": "tenant-x",
        "project_id": "project-x",
        "case_id": "case-x",
        "lane_id": "planning",
        "persistent_store_identity": "store-sha256:example",
        "approval_id": "approval-x",
        "approval_registry_ref": "hil-approval-x",
        "cutover_id": "cutover-x",
        "request_digest": "request-sha256:example",
        "contract_version_id": "contract-x:v1",
        "contract_digest": "contract-sha256:example",
        "artifact_version_id": "artifact-x:v1",
        "artifact_digest": "artifact-sha256:example",
        "comparison_id": "comparison-x",
        "comparison_digest": "comparison-sha256:example",
        "backup_snapshot_sha256": "backup-sha256:example",
        "backup_restore_mode": "post_rollback_audit",
        "rollback_window": "15m",
        "kill_switch_state": "off_before_cutover",
        "impact_scope": "case_scoped_planning_only",
        "cutover_decision_ref": "cutover-x:v2",
        "rollback_decision_ref": "cutover-x:v3",
        "authority_before": "legacy",
        "authority_after_cutover": "canonical_for_lane",
        "authority_after_rollback": "legacy",
        "authority_event_types": ["PLANNING_CUTOVER_REQUESTED", "PLANNING_CUTOVER_DECIDED", "PLANNING_AUTHORITY_CHANGED", "PLANNING_ROLLBACK_EXECUTED"],
    }
    assert MODULE._pilot_execution_errors(passed) == []
    approved = {
        "status": "approved",
        "approval_id": "approval-x",
        "approval_registry_ref": "hil-approval-x",
        "approved_case_scope": "case-x",
        "approved_lane_id": "planning",
        "approved_store_identity": "store-sha256:example",
        "approved_contract_version_id": "contract-x:v1",
        "approved_contract_digest": "contract-sha256:example",
        "approved_artifact_version_id": "artifact-x:v1",
        "approved_artifact_digest": "artifact-sha256:example",
        "approved_comparison_id": "comparison-x",
        "approved_comparison_digest": "comparison-sha256:example",
        "backup_snapshot_sha256": "backup-sha256:example",
        "rollback_window": "15m",
        "kill_switch_state": "off_before_cutover",
        "impact_scope": "case_scoped_planning_only",
    }
    assert MODULE._approval_execution_alignment_errors(approved, passed) == []
    assert MODULE._approval_execution_alignment_errors({**approved, "approved_contract_digest": "stale"}, passed) == ["pilot_approval_execution_mismatch:approved_contract_digest"]


def test_m4_store_backed_closeout_recomputes_persistent_source_and_backup_restore(tmp_path: Path) -> None:
    approval, evidence, store_path, backup_path = _store_backed_records(tmp_path)
    assert MODULE._pilot_approval_errors(approval) == []
    assert MODULE._pilot_execution_errors(evidence) == []
    assert MODULE._approval_execution_alignment_errors(approval, evidence) == []
    errors, proof = MODULE.store_backed_pilot_verification(
        approval,
        evidence,
        persistent_store_path=store_path,
        backup_snapshot_path=backup_path,
        restore_root=tmp_path / "closeout-restore",
    )
    assert errors == []
    assert proof["status"] == "pass"
    assert proof["source_content_fingerprint"] == proof["restored_content_fingerprint"]
    assert proof["source_store_identity"] != proof["restored_store_identity"]

    hand_filled_errors, _ = MODULE.store_backed_pilot_verification(
        approval,
        evidence,
        persistent_store_path=None,
        backup_snapshot_path=None,
        restore_root=tmp_path / "missing-source",
    )
    assert hand_filled_errors == ["store_backed_persistent_store_path_required"]

    tampered_errors, _ = MODULE.store_backed_pilot_verification(
        approval,
        {**evidence, "contract_digest": "hand-filled-wrong-digest"},
        persistent_store_path=store_path,
        backup_snapshot_path=backup_path,
        restore_root=tmp_path / "tampered",
    )
    assert "store_backed_contract_digest_mismatch" in tampered_errors
    assert "store_backed_decision_binding_mismatch:approved_contract_digest" in tampered_errors

    wrong_store_path = tmp_path / "wrong-store.sqlite"
    MODULE.SQLiteCanonicalStore(wrong_store_path)
    wrong_store_errors, _ = MODULE.store_backed_pilot_verification(
        approval,
        evidence,
        persistent_store_path=wrong_store_path,
        backup_snapshot_path=backup_path,
        restore_root=tmp_path / "wrong-store-restore",
    )
    assert "store_backed_store_identity_mismatch" in wrong_store_errors
    assert "store_backed_case_scope_mismatch" in wrong_store_errors

    wrong_backup_errors, _ = MODULE.store_backed_pilot_verification(
        approval,
        {**evidence, "backup_snapshot_sha256": "0" * 64},
        persistent_store_path=store_path,
        backup_snapshot_path=backup_path,
        restore_root=tmp_path / "wrong-backup",
    )
    assert "store_backed_backup_sha256_mismatch" in wrong_backup_errors


def test_m4_store_backed_event_verifier_fails_closed_for_missing_disordered_and_wrong_versions(tmp_path: Path) -> None:
    _, evidence, store_path, _ = _store_backed_records(tmp_path)
    store = MODULE.SQLiteCanonicalStore(store_path)
    events = [event for event in store.list_events() if (event.get("payload") or {}).get("cutover_id") == evidence["cutover_id"]]
    assert MODULE._event_sequence_errors(events, cutover_id=evidence["cutover_id"]) == []
    assert "store_backed_authority_event_sequence_invalid" in MODULE._event_sequence_errors(events[:-1], cutover_id=evidence["cutover_id"])
    disordered = json.loads(json.dumps(events))
    disordered[1]["event_type"], disordered[2]["event_type"] = disordered[2]["event_type"], disordered[1]["event_type"]
    assert "store_backed_authority_event_sequence_invalid" in MODULE._event_sequence_errors(disordered, cutover_id=evidence["cutover_id"])
    wrong_version = json.loads(json.dumps(events))
    wrong_version[3]["state_version_after"] = 99
    assert "store_backed_authority_event_version_invalid:PLANNING_ROLLBACK_EXECUTED" in MODULE._event_sequence_errors(wrong_version, cutover_id=evidence["cutover_id"])
