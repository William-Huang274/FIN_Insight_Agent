"""Close M4 only for the human-accepted, non-production synthetic pilot."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_point01_m4_closeout_gate import _load, store_backed_pilot_verification


DEFAULT_ACCEPTANCE = ROOT / "configs/engineering_handoff/point01_m4_synthetic_pilot_human_acceptance_v1_0.json"
DEFAULT_APPROVAL = ROOT / "configs/engineering_handoff/point01_m4_synthetic_pilot_approval_v1_0.json"
DEFAULT_EVIDENCE = ROOT / "data/manifests/point01_m4_synthetic_pilot_execution_evidence_v1_0.json"
DEFAULT_PILOT_RESULT = ROOT / "data/manifests/point01_m4_synthetic_persistent_mutation_pilot_result_v1_0.json"
DEFAULT_STORE = ROOT / "data/staging/point01_m4_synthetic_pilot_v3/canonical.sqlite"
DEFAULT_BACKUP = ROOT / "data/staging/point01_m4_synthetic_pilot_v3/backups/pre_mutation_baseline.sqlite"
DEFAULT_OUTPUT = ROOT / "data/manifests/point01_m4_synthetic_closeout_gate_result_v1_0.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve_artifact_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def _acceptance_errors(acceptance: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if acceptance.get("status") != "accepted":
        errors.append("synthetic_human_acceptance_pending")
    if acceptance.get("decision") != "accept_m4_nonproduction_synthetic_persistent_pilot":
        errors.append("synthetic_human_acceptance_decision_invalid")
    for field in ("reviewer_identity", "reviewed_at"):
        if not acceptance.get(field):
            errors.append(f"synthetic_human_acceptance_missing:{field}")
    for artifact_name, artifact in dict(acceptance.get("reviewed_artifacts") or {}).items():
        path = _resolve_artifact_path(str(artifact.get("path") or ""))
        if not path.is_file():
            errors.append(f"synthetic_acceptance_artifact_missing:{artifact_name}")
        elif _sha256(path) != artifact.get("sha256"):
            errors.append(f"synthetic_acceptance_artifact_hash_mismatch:{artifact_name}")
    return errors


def _run_m4_children(work_root: Path) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    design_path = work_root / "m4_design.json"
    fixture_dir = work_root / "fixtures"
    errors: list[str] = []
    commands = (
        [sys.executable, "scripts/engineering/run_point01_m4_design_lint.py", "--output", str(design_path)],
        [sys.executable, "scripts/engineering/run_point01_m4_cutover_fixtures.py", "--output-dir", str(fixture_dir), "--work-root", str(work_root / "runtime")],
    )
    for command in commands:
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        if completed.returncode != 0:
            errors.append(f"m4_child_runner_failed:{Path(command[1]).name}")
    try:
        design = _load(design_path)
    except (OSError, json.JSONDecodeError):
        design = {"status": "fail_closed"}
        errors.append("m4_synthetic_design_result_unreadable")
    try:
        fixtures = _load(fixture_dir / "point01_m4_cutover_fixture_result_v1_0.json")
    except (OSError, json.JSONDecodeError):
        fixtures = {"status": "fail_closed", "point_statuses": {}}
        errors.append("m4_synthetic_fixture_result_unreadable")
    return design, fixtures, errors


def build_result(
    *,
    acceptance_path: Path = DEFAULT_ACCEPTANCE,
    approval_path: Path = DEFAULT_APPROVAL,
    evidence_path: Path = DEFAULT_EVIDENCE,
    pilot_result_path: Path = DEFAULT_PILOT_RESULT,
    persistent_store_path: Path = DEFAULT_STORE,
    backup_snapshot_path: Path = DEFAULT_BACKUP,
    work_root: Path | None = None,
) -> dict[str, Any]:
    root = work_root or Path(tempfile.mkdtemp(prefix="point01_m4_synthetic_closeout_"))
    root.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    try:
        acceptance = _load(acceptance_path)
        errors.extend(_acceptance_errors(acceptance))
    except (OSError, json.JSONDecodeError):
        acceptance = {"status": "unreadable"}
        errors.append("synthetic_human_acceptance_unreadable")
    try:
        approval = _load(approval_path)
        evidence = _load(evidence_path)
        pilot_result = _load(pilot_result_path)
    except (OSError, json.JSONDecodeError):
        approval, evidence, pilot_result = {}, {}, {}
        errors.append("synthetic_pilot_evidence_unreadable")
    if approval.get("status") != "approved":
        errors.append("synthetic_pilot_approval_not_approved")
    if evidence.get("status") != "pass" or pilot_result.get("status") != "pass":
        errors.append("synthetic_pilot_execution_not_pass")
    if pilot_result.get("business_case_mutation") is not False:
        errors.append("synthetic_pilot_business_case_boundary_breached")
    if evidence.get("downstream_consumer_count") != 0:
        errors.append("synthetic_pilot_downstream_consumers_present")
    design, fixtures, child_errors = _run_m4_children(root)
    errors.extend(child_errors)
    if design.get("status") != "pass" or design.get("design_review_status") != "user_confirmed_calibration_accepted":
        errors.append("m4_design_freeze_not_pass")
    point_statuses = dict(fixtures.get("point_statuses") or {})
    for point in (f"M4.{number}" for number in range(1, 8)):
        if point_statuses.get(point) != "pass":
            errors.append(f"m4_required_point_not_pass:{point}")
    store_errors, store_proof = store_backed_pilot_verification(
        approval,
        evidence,
        persistent_store_path=persistent_store_path,
        backup_snapshot_path=backup_snapshot_path,
        restore_root=root / "store_backed_restore",
    )
    errors.extend(store_errors)
    expected_events = [
        "PLANNING_CUTOVER_REQUESTED",
        "PLANNING_CUTOVER_DECIDED",
        "PLANNING_AUTHORITY_CHANGED",
        "PLANNING_ROLLBACK_EXECUTED",
    ]
    if evidence.get("authority_event_types") != expected_events:
        errors.append("synthetic_pilot_authority_event_sequence_invalid")
    if evidence.get("approved_read_contract_version_id") != evidence.get("contract_version_id") or evidence.get("pinned_read_contract_version_id") != evidence.get("contract_version_id"):
        errors.append("synthetic_pilot_approved_version_read_lock_invalid")
    if evidence.get("newer_contract_version_id") == evidence.get("contract_version_id"):
        errors.append("synthetic_pilot_newer_contract_not_created")
    unmet = sorted(set(errors))
    return {
        "result_version": "finsight_point01_m4_synthetic_closeout_gate_result_v1_0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "Point01_M4_nonproduction_synthetic_persistent_technical_pilot",
        "status": "pass" if not unmet else "fail_closed",
        "milestone": "M4_complete_nonproduction_synthetic_pilot" if not unmet else "M4_closeout_pending",
        "unmet_conditions": unmet,
        "human_acceptance_status": acceptance.get("status"),
        "required_point_statuses": {"M4.0": design.get("status"), **point_statuses},
        "store_backed_pilot_verification": store_proof,
        "pilot_execution_status": evidence.get("status"),
        "business_case_mutation": pilot_result.get("business_case_mutation"),
        "model_call_count": 0,
        "external_call_count": 0,
        "fixed_input_sha256": {
            _display_path(acceptance_path): _sha256(acceptance_path),
            _display_path(approval_path): _sha256(approval_path),
            _display_path(evidence_path): _sha256(evidence_path),
            _display_path(pilot_result_path): _sha256(pilot_result_path),
            "scripts/engineering/run_point01_m4_synthetic_closeout_gate.py": _sha256(Path(__file__).resolve()),
            "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md": _sha256(ROOT / "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md"),
        },
        "boundary": "This closes M4 only as a human-accepted non-production synthetic technical pilot. Business Case mutation, legacy TaskRun authority change, sector/tenant/global cutover, Evidence/Writer/provider/full-chain remain forbidden.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Point 01 M4 synthetic persistent pilot closeout gate.")
    parser.add_argument("--acceptance", type=Path, default=DEFAULT_ACCEPTANCE)
    parser.add_argument("--approval", type=Path, default=DEFAULT_APPROVAL)
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--pilot-result", type=Path, default=DEFAULT_PILOT_RESULT)
    parser.add_argument("--persistent-store-path", type=Path, default=DEFAULT_STORE)
    parser.add_argument("--backup-snapshot-path", type=Path, default=DEFAULT_BACKUP)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--work-root", type=Path)
    args = parser.parse_args()
    def resolve(path: Path) -> Path:
        return path if path.is_absolute() else ROOT / path
    result = build_result(
        acceptance_path=resolve(args.acceptance),
        approval_path=resolve(args.approval),
        evidence_path=resolve(args.evidence),
        pilot_result_path=resolve(args.pilot_result),
        persistent_store_path=resolve(args.persistent_store_path),
        backup_snapshot_path=resolve(args.backup_snapshot_path),
        work_root=resolve(args.work_root) if args.work_root else None,
    )
    output = resolve(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "milestone": result["milestone"], "unmet_conditions": result["unmet_conditions"]}, ensure_ascii=False))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
