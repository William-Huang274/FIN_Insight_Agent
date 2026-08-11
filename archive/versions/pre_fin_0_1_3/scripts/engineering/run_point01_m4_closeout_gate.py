from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.canonical_runtime.store import SQLiteCanonicalStore


DEFAULT_MANIFEST = ROOT / "configs/engineering_handoff/point01_m4_closeout_gate_manifest_v1_0.json"
DEFAULT_OUTPUT = ROOT / "data/manifests/point01_m4_closeout_gate_result_v1_0.json"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _pilot_approval_errors(approval: Mapping[str, Any]) -> list[str]:
    if approval.get("status") != "approved":
        return ["human_pilot_approval_pending"]
    required = (
        "approval_id",
        "approval_registry_ref",
        "approver_type",
        "approver_identity",
        "approved_at",
        "decision",
        "approved_case_scope",
        "approved_lane_id",
        "approved_store_identity",
        "approved_contract_version_id",
        "approved_contract_digest",
        "approved_artifact_version_id",
        "approved_artifact_digest",
        "approved_comparison_id",
        "approved_comparison_digest",
        "backup_snapshot_sha256",
        "rollback_window",
        "kill_switch_state",
        "impact_scope",
        "approval_revocation_registry_ref",
    )
    errors = [f"human_pilot_approval_missing:{field}" for field in required if not approval.get(field)]
    if approval.get("approver_type") != "human":
        errors.append("human_pilot_approval_type_invalid")
    if approval.get("decision") != "approve_case_scoped_planning_cutover_only":
        errors.append("human_pilot_approval_decision_invalid")
    if approval.get("authority_boundary_acknowledged") != {"legacy_task_run": "authoritative", "canonical_lane": "case_scoped_planning_only_after_approval", "cutover": "m4_case_scoped_only"}:
        errors.append("human_pilot_authority_boundary_not_acknowledged")
    if approval.get("rollback_acknowledged") is not True:
        errors.append("human_pilot_rollback_not_acknowledged")
    if approval.get("kill_switch_state") != "off_before_cutover":
        errors.append("human_pilot_kill_switch_state_invalid")
    if approval.get("impact_scope") != "case_scoped_planning_only":
        errors.append("human_pilot_impact_scope_invalid")
    return errors


def _pilot_execution_errors(evidence: Mapping[str, Any]) -> list[str]:
    if evidence.get("status") != "pass":
        return ["real_case_pilot_execution_pending"]
    required = (
        "tenant_id",
        "project_id",
        "case_id",
        "lane_id",
        "persistent_store_identity",
        "approval_id",
        "approval_registry_ref",
        "cutover_id",
        "request_digest",
        "cutover_decision_ref",
        "rollback_decision_ref",
        "contract_version_id",
        "contract_digest",
        "artifact_version_id",
        "artifact_digest",
        "comparison_id",
        "comparison_digest",
        "backup_snapshot_sha256",
        "backup_restore_mode",
        "rollback_window",
        "kill_switch_state",
        "impact_scope",
    )
    errors = [f"real_case_pilot_execution_missing:{field}" for field in required if not evidence.get(field)]
    if evidence.get("authority_before") != "legacy":
        errors.append("real_case_pilot_initial_authority_invalid")
    if evidence.get("authority_after_cutover") != "canonical_for_lane":
        errors.append("real_case_pilot_cutover_authority_invalid")
    if evidence.get("authority_after_rollback") != "legacy":
        errors.append("real_case_pilot_rollback_authority_invalid")
    if evidence.get("kill_switch_state") != "off_before_cutover":
        errors.append("real_case_pilot_kill_switch_state_invalid")
    if evidence.get("impact_scope") != "case_scoped_planning_only":
        errors.append("real_case_pilot_impact_scope_invalid")
    if evidence.get("backup_restore_mode") not in {"post_rollback_audit", "pre_mutation_baseline"}:
        errors.append("real_case_pilot_backup_restore_mode_invalid")
    event_types = set(evidence.get("authority_event_types") or ())
    required_events = {"PLANNING_CUTOVER_REQUESTED", "PLANNING_CUTOVER_DECIDED", "PLANNING_AUTHORITY_CHANGED", "PLANNING_ROLLBACK_EXECUTED"}
    errors.extend(f"real_case_pilot_event_missing:{event_type}" for event_type in sorted(required_events - event_types))
    return errors


def _approval_execution_alignment_errors(approval: Mapping[str, Any], evidence: Mapping[str, Any]) -> list[str]:
    if approval.get("status") != "approved" or evidence.get("status") != "pass":
        return []
    pairs = {
        "approval_id": "approval_id",
        "approval_registry_ref": "approval_registry_ref",
        "approved_case_scope": "case_id",
        "approved_lane_id": "lane_id",
        "approved_store_identity": "persistent_store_identity",
        "approved_contract_version_id": "contract_version_id",
        "approved_contract_digest": "contract_digest",
        "approved_artifact_version_id": "artifact_version_id",
        "approved_artifact_digest": "artifact_digest",
        "approved_comparison_id": "comparison_id",
        "approved_comparison_digest": "comparison_digest",
        "backup_snapshot_sha256": "backup_snapshot_sha256",
        "rollback_window": "rollback_window",
        "kill_switch_state": "kill_switch_state",
        "impact_scope": "impact_scope",
    }
    return [f"pilot_approval_execution_mismatch:{approval_field}" for approval_field, evidence_field in pairs.items() if approval.get(approval_field) != evidence.get(evidence_field)]


REQUIRED_AUTHORITY_EVENTS = (
    "PLANNING_CUTOVER_REQUESTED",
    "PLANNING_CUTOVER_DECIDED",
    "PLANNING_AUTHORITY_CHANGED",
    "PLANNING_ROLLBACK_EXECUTED",
)


def _event_sequence_errors(events: list[Mapping[str, Any]], *, cutover_id: str) -> list[str]:
    """Validate the durable, ordered transition trace for one cutover.

    This deliberately consumes event envelopes persisted in the store instead of
    the self-reported `authority_event_types` field from execution evidence.
    """
    selected = [event for event in events if (event.get("payload") or {}).get("cutover_id") == cutover_id]
    ordered = sorted(selected, key=lambda event: int(event.get("sequence_no") or -1))
    errors: list[str] = []
    if [event.get("event_type") for event in ordered] != list(REQUIRED_AUTHORITY_EVENTS):
        errors.append("store_backed_authority_event_sequence_invalid")
        return errors
    sequence_numbers = [int(event.get("sequence_no") or -1) for event in ordered]
    if sequence_numbers != list(range(sequence_numbers[0], sequence_numbers[0] + len(sequence_numbers))):
        errors.append("store_backed_authority_event_sequence_noncontiguous")
    expected_state_versions = ((0, 1), (1, 2), (1, 2), (2, 3))
    expected_subjects = ("lane_cutover_decision", "lane_cutover_decision", "case_control_summary", "case_control_summary")
    for event, expected_versions, expected_subject in zip(ordered, expected_state_versions, expected_subjects, strict=True):
        if (event.get("state_version_before"), event.get("state_version_after")) != expected_versions:
            errors.append(f"store_backed_authority_event_version_invalid:{event.get('event_type')}")
        payload = event.get("payload") or {}
        if payload.get("state_subject") != expected_subject:
            errors.append(f"store_backed_authority_event_subject_invalid:{event.get('event_type')}")
    return sorted(set(errors))


def _binding_errors(store: SQLiteCanonicalStore, evidence: Mapping[str, Any], *, prefix: str = "store_backed") -> list[str]:
    case_id = str(evidence.get("case_id") or "")
    contract_rows = [row for row in store.list_versions("canonical_decision_surface_contract_versions", case_id=case_id) if row.get("contract_version_id") == evidence.get("contract_version_id")]
    artifact_rows = [row for row in store.list_versions("canonical_artifact_versions", case_id=case_id) if row.get("artifact_version_id") == evidence.get("artifact_version_id")]
    comparison_rows = [row for row in store.list_versions("canonical_shadow_comparisons", case_id=case_id) if row.get("comparison_id") == evidence.get("comparison_id")]
    errors: list[str] = []
    if len(contract_rows) != 1:
        errors.append(f"{prefix}_contract_version_missing_or_ambiguous")
    elif canonical_digest(contract_rows[0]) != evidence.get("contract_digest"):
        errors.append(f"{prefix}_contract_digest_mismatch")
    if len(artifact_rows) != 1:
        errors.append(f"{prefix}_artifact_version_missing_or_ambiguous")
    elif artifact_rows[0].get("object_digest") != evidence.get("artifact_digest"):
        errors.append(f"{prefix}_artifact_digest_mismatch")
    if len(comparison_rows) != 1:
        errors.append(f"{prefix}_comparison_missing_or_ambiguous")
    elif canonical_digest(comparison_rows[0]) != evidence.get("comparison_digest"):
        errors.append(f"{prefix}_comparison_digest_mismatch")
    elif comparison_rows[0].get("canonical_contract_version_id") != evidence.get("contract_version_id"):
        errors.append(f"{prefix}_comparison_contract_mismatch")
    return errors


def _restore_backup(backup_path: Path, destination: Path) -> SQLiteCanonicalStore:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(backup_path) as source, sqlite3.connect(destination) as restored:
        source.backup(restored)
    return SQLiteCanonicalStore(destination)


def store_backed_pilot_verification(
    approval: Mapping[str, Any],
    evidence: Mapping[str, Any],
    *,
    persistent_store_path: Path | None,
    backup_snapshot_path: Path | None,
    restore_root: Path,
) -> tuple[list[str], dict[str, Any]]:
    """Recompute every M4.8 pilot claim from the durable source and its backup.

    The closeout gate invokes this only after the human approval and execution
    receipt are individually well formed.  It creates a fresh restore database
    below the gate work directory; a pre-existing JSON receipt cannot substitute
    for either the source store or this restore drill.
    """
    errors: list[str] = []
    proof: dict[str, Any] = {"status": "fail_closed", "verification_mode": "persistent_store_backed"}
    if persistent_store_path is None:
        return ["store_backed_persistent_store_path_required"], proof
    if backup_snapshot_path is None:
        return ["store_backed_backup_snapshot_path_required"], proof
    if not persistent_store_path.is_file():
        return ["store_backed_persistent_store_path_missing"], proof
    if not backup_snapshot_path.is_file():
        return ["store_backed_backup_snapshot_path_missing"], proof
    try:
        store = SQLiteCanonicalStore(persistent_store_path)
        source_recovery = store.recovery_check()
        source_fingerprint = store.content_fingerprint()
    except (OSError, sqlite3.Error, ValueError) as exc:
        return [f"store_backed_source_store_unreadable:{type(exc).__name__}"], proof
    backup_sha256 = _sha256(backup_snapshot_path)
    proof.update(
        {
            "source_store_identity": store.store_identity(),
            "source_content_fingerprint": source_fingerprint,
            "source_store_integrity_check": source_recovery,
            "backup_snapshot_sha256": backup_sha256,
        }
    )
    if source_recovery.get("status") != "pass":
        errors.append("store_backed_source_store_integrity_failed")
    if store.store_identity() != evidence.get("persistent_store_identity"):
        errors.append("store_backed_store_identity_mismatch")
    if store.store_identity() != approval.get("approved_store_identity"):
        errors.append("store_backed_approval_store_identity_mismatch")
    if backup_sha256 != evidence.get("backup_snapshot_sha256"):
        errors.append("store_backed_backup_sha256_mismatch")
    errors.extend(_binding_errors(store, evidence))
    case = store.get_latest("canonical_research_cases", str(evidence.get("case_id") or ""))
    if not case or case.get("tenant_id") != evidence.get("tenant_id") or case.get("project_id") != evidence.get("project_id"):
        errors.append("store_backed_case_scope_mismatch")
    else:
        control = store.get_latest("canonical_case_control_versions", str(case.get("case_control_summary_ref") or ""))
        if not control or control.get("planning_authority") != "legacy":
            errors.append("store_backed_final_legacy_authority_missing")
    cutover_id = str(evidence.get("cutover_id") or "")
    decisions = [row for row in store.list_versions("canonical_lane_cutover_decisions", case_id=str(evidence.get("case_id") or "")) if row.get("cutover_id") == cutover_id]
    expected_decisions = ((1, "requested"), (2, "executed"), (3, "rolled_back"))
    for decision_version, expected_status in expected_decisions:
        matches = [row for row in decisions if row.get("decision_version") == decision_version]
        if len(matches) != 1:
            errors.append(f"store_backed_decision_version_missing_or_ambiguous:{decision_version}")
            continue
        decision = matches[0]
        if decision.get("current_status") != expected_status:
            errors.append(f"store_backed_decision_status_invalid:{decision_version}")
        if decision.get("content_digest") != evidence.get("request_digest"):
            errors.append(f"store_backed_request_digest_mismatch:{decision_version}")
        for decision_field, evidence_field in (
            ("approval_id", "approval_id"),
            ("approval_registry_ref", "approval_registry_ref"),
            ("approved_contract_version_id", "contract_version_id"),
            ("approved_contract_digest", "contract_digest"),
            ("approved_artifact_version_id", "artifact_version_id"),
            ("approved_artifact_digest", "artifact_digest"),
            ("approved_comparison_id", "comparison_id"),
            ("approved_comparison_digest", "comparison_digest"),
        ):
            if decision.get(decision_field) != evidence.get(evidence_field):
                errors.append(f"store_backed_decision_binding_mismatch:{decision_field}")
    if evidence.get("cutover_decision_ref") != f"{cutover_id}:v2":
        errors.append("store_backed_cutover_decision_ref_mismatch")
    if evidence.get("rollback_decision_ref") != f"{cutover_id}:v3":
        errors.append("store_backed_rollback_decision_ref_mismatch")
    errors.extend(_event_sequence_errors(list(store.list_events()), cutover_id=cutover_id))
    try:
        restored_store = _restore_backup(backup_snapshot_path, restore_root / "store_backed_restored.sqlite")
        restored_recovery = restored_store.recovery_check()
        restored_fingerprint = restored_store.content_fingerprint()
        proof.update(
            {
                "restored_store_identity": restored_store.store_identity(),
                "restored_content_fingerprint": restored_fingerprint,
                "restored_store_integrity_check": restored_recovery,
                "restored_content_fingerprint_match": restored_fingerprint == source_fingerprint,
            }
        )
        if restored_recovery.get("status") != "pass":
            errors.append("store_backed_restored_store_integrity_failed")
        restore_mode = evidence.get("backup_restore_mode")
        if restore_mode == "post_rollback_audit":
            expected_restored_fingerprint = source_fingerprint
        elif restore_mode == "pre_mutation_baseline":
            expected_restored_fingerprint = evidence.get("backup_baseline_content_fingerprint")
            if not expected_restored_fingerprint:
                errors.append("store_backed_backup_baseline_fingerprint_missing")
            if evidence.get("post_rollback_content_fingerprint") != source_fingerprint:
                errors.append("store_backed_post_rollback_fingerprint_mismatch")
        else:
            expected_restored_fingerprint = None
            errors.append("store_backed_backup_restore_mode_invalid")
        proof["backup_restore_mode"] = restore_mode
        proof["restored_matches_expected_baseline"] = restored_fingerprint == expected_restored_fingerprint
        if restored_fingerprint != expected_restored_fingerprint:
            errors.append("store_backed_restore_content_fingerprint_mismatch")
        if restore_mode == "pre_mutation_baseline":
            restored_cutover_event_count = sum(
                1
                for event in restored_store.list_events()
                if (event.get("payload") or {}).get("cutover_id") == cutover_id
            )
            proof["restored_baseline_cutover_event_count"] = restored_cutover_event_count
            if evidence.get("backup_baseline_cutover_event_count") != restored_cutover_event_count:
                errors.append("store_backed_restored_baseline_event_count_mismatch")
        errors.extend(_binding_errors(restored_store, evidence, prefix="store_backed_restored"))
        restored_case = restored_store.get_latest("canonical_research_cases", str(evidence.get("case_id") or ""))
        restored_control = restored_store.get_latest("canonical_case_control_versions", str(restored_case.get("case_control_summary_ref") or "")) if restored_case else None
        if not restored_control or restored_control.get("planning_authority") != "legacy":
            errors.append("store_backed_restored_legacy_authority_missing")
    except (OSError, sqlite3.Error, ValueError) as exc:
        errors.append(f"store_backed_restore_failed:{type(exc).__name__}")
    proof["status"] = "pass" if not errors else "fail_closed"
    return sorted(set(errors)), proof


def _run_children(work_root: Path) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    design_path = work_root / "m4_design.json"
    fixture_dir = work_root / "fixtures"
    errors: list[str] = []
    for command in (
        [sys.executable, "scripts/engineering/run_point01_m4_design_lint.py", "--output", str(design_path)],
        [sys.executable, "scripts/engineering/run_point01_m4_cutover_fixtures.py", "--output-dir", str(fixture_dir), "--work-root", str(work_root / "runtime")],
    ):
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        if completed.returncode != 0:
            errors.append(f"child_runner_failed:{Path(command[1]).name}")
    try:
        design = _load(design_path)
    except (OSError, json.JSONDecodeError):
        design = {"status": "fail_closed"}
        errors.append("design_result_unreadable")
    try:
        fixtures = _load(fixture_dir / "point01_m4_cutover_fixture_result_v1_0.json")
    except (OSError, json.JSONDecodeError):
        fixtures = {"status": "fail_closed", "point_statuses": {}}
        errors.append("fixture_result_unreadable")
    return design, fixtures, errors


def build_result(
    manifest: Mapping[str, Any],
    *,
    work_root: Path | None = None,
    persistent_store_path: Path | None = None,
    backup_snapshot_path: Path | None = None,
) -> dict[str, Any]:
    root = work_root or Path(tempfile.mkdtemp(prefix="point01_m4_closeout_"))
    root.mkdir(parents=True, exist_ok=True)
    design, fixtures, errors = _run_children(root)
    if design.get("status") != "pass":
        errors.append("m4_0_design_lint_not_pass")
    statuses = dict(fixtures.get("point_statuses") or {})
    for point in manifest.get("required_points") or ():
        if point != "M4.0" and statuses.get(point) != "pass":
            errors.append(f"required_point_not_pass:{point}")
    event_types: set[str] = set()
    try:
        recovery = _load(root / "fixtures" / "point01_m4_6_fixture_result_v1_0.json")["payload"]["recovery"]
        event_types = set(recovery.get("event_types") or ())
        for event_type in manifest.get("required_authority_events") or ():
            if event_type not in event_types:
                errors.append(f"authority_event_missing:{event_type}")
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        errors.append("rollback_recovery_evidence_unreadable")
    approval_path = ROOT / str(manifest.get("human_pilot_approval_path") or "")
    try:
        approval = _load(approval_path)
        errors.extend(_pilot_approval_errors(approval))
    except (OSError, json.JSONDecodeError):
        approval = {"status": "unreadable"}
        errors.append("human_pilot_approval_unreadable")
    execution_path = ROOT / str(manifest.get("pilot_execution_evidence_path") or "")
    try:
        execution_evidence = _load(execution_path)
        errors.extend(_pilot_execution_errors(execution_evidence))
    except (OSError, json.JSONDecodeError):
        execution_evidence = {"status": "unreadable"}
        errors.append("real_case_pilot_execution_evidence_unreadable")
    errors.extend(_approval_execution_alignment_errors(approval, execution_evidence))
    if approval.get("status") == "approved" and execution_evidence.get("status") == "pass":
        store_errors, store_proof = store_backed_pilot_verification(
            approval,
            execution_evidence,
            persistent_store_path=persistent_store_path,
            backup_snapshot_path=backup_snapshot_path,
            restore_root=root,
        )
        errors.extend(store_errors)
    else:
        store_proof = {"status": "not_attempted", "verification_mode": "persistent_store_backed"}
        errors.append("store_backed_pilot_verification_pending")
    if design.get("design_review_status") != "user_confirmed_calibration_accepted":
        errors.append("m4_0_design_review_user_confirmation_pending")
    unmet = sorted(set(errors))
    return {
        "result_version": "finsight_point01_m4_closeout_gate_result_v1_0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": manifest.get("scope"),
        "status": "pass" if not unmet else "fail_closed",
        "milestone": "M4_complete" if not unmet else "M4_closeout_pending",
        "unmet_conditions": unmet,
        "required_point_statuses": {"M4.0": design.get("status"), **statuses},
        "human_pilot_approval_status": approval.get("status"),
        "pilot_execution_status": execution_evidence.get("status"),
        "store_backed_pilot_verification": store_proof,
        "design_review_status": design.get("design_review_status"),
        "authority_events": sorted(event_types),
        "authority_boundary": manifest.get("authority_boundary"),
        "forbidden_admissions": manifest.get("forbidden_admissions"),
        "model_call_count": 0,
        "external_call_count": 0,
        "fixed_input_sha256": {
            "configs/engineering_handoff/point01_m4_closeout_gate_manifest_v1_0.json": _sha256(DEFAULT_MANIFEST),
            "configs/engineering_handoff/point01_m4_human_pilot_approval_v1_0.json": _sha256(approval_path),
            "configs/engineering_handoff/point01_m4_pilot_execution_evidence_v1_0.json": _sha256(execution_path),
            "scripts/engineering/run_point01_m4_closeout_gate.py": _sha256(Path(__file__).resolve()),
            "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md": _sha256(ROOT / "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md"),
        },
        "boundary": "M4 closeout can authorize only an explicitly approved case-scoped planning pilot. It cannot change legacy TaskRun authority or admit sector/global cutover, Evidence/Writer, provider/model or full-chain runtime.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Point 01 M4 aggregate closeout gate.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--work-root", type=Path)
    parser.add_argument("--persistent-store-path", type=Path)
    parser.add_argument("--backup-snapshot-path", type=Path)
    args = parser.parse_args()
    manifest_path = args.manifest if args.manifest.is_absolute() else ROOT / args.manifest
    output_path = args.output if args.output.is_absolute() else ROOT / args.output
    work_root = args.work_root if args.work_root is None or args.work_root.is_absolute() else ROOT / args.work_root
    persistent_store_path = args.persistent_store_path if args.persistent_store_path is None or args.persistent_store_path.is_absolute() else ROOT / args.persistent_store_path
    backup_snapshot_path = args.backup_snapshot_path if args.backup_snapshot_path is None or args.backup_snapshot_path.is_absolute() else ROOT / args.backup_snapshot_path
    result = build_result(
        _load(manifest_path),
        work_root=work_root,
        persistent_store_path=persistent_store_path,
        backup_snapshot_path=backup_snapshot_path,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "milestone": result["milestone"], "unmet_conditions": result["unmet_conditions"]}, ensure_ascii=False))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
