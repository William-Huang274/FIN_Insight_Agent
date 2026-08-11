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
DEFAULT_MANIFEST = ROOT / "configs/engineering_handoff/point01_m3_closeout_gate_manifest_v1_0.json"
DEFAULT_OUTPUT = ROOT / "data/manifests/point01_m3_closeout_gate_result_v1_0.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _approval_errors(approval: Mapping[str, Any]) -> list[str]:
    if approval.get("status") != "approved":
        return ["human_reviewer_approval_pending"]
    required = ("approver_type", "approver_identity", "approved_at", "decision")
    errors = [f"human_reviewer_approval_missing:{field}" for field in required if not approval.get(field)]
    if approval.get("approver_type") != "human":
        errors.append("human_reviewer_approval_type_invalid")
    if approval.get("decision") != "approve_m3_shadow_calibration_only":
        errors.append("human_reviewer_approval_decision_invalid")
    if approval.get("authority_boundary_acknowledged") != {"legacy_task_run": "authoritative", "canonical_lane": "shadow_only", "cutover": "forbidden"}:
        errors.append("human_reviewer_authority_boundary_not_acknowledged")
    return errors


def _run_children(work_root: Path) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    design_output = work_root / "m3_design_lint.json"
    calibration_output_dir = work_root / "calibration"
    commands = (
        [sys.executable, "scripts/engineering/run_point01_m3_design_lint.py", "--output", str(design_output)],
        [sys.executable, "scripts/engineering/run_point01_m3_calibration_fixtures.py", "--output-dir", str(calibration_output_dir)],
    )
    errors: list[str] = []
    for command in commands:
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        if result.returncode != 0:
            errors.append(f"child_runner_failed:{Path(command[1]).name}")
    try:
        design = _load_json(design_output)
    except (OSError, json.JSONDecodeError):
        design = {"status": "fail_closed", "errors": ["design_result_unreadable"]}
        errors.append("design_result_unreadable")
    try:
        calibration = _load_json(calibration_output_dir / "point01_m3_calibration_fixture_result_v1_0.json")
    except (OSError, json.JSONDecodeError):
        calibration = {"status": "fail_closed", "point_statuses": {}}
        errors.append("calibration_result_unreadable")
    return design, calibration, errors


def build_result(manifest: Mapping[str, Any], *, work_root: Path | None = None) -> dict[str, Any]:
    root = work_root or Path(tempfile.mkdtemp(prefix="point01_m3_closeout_"))
    root.mkdir(parents=True, exist_ok=True)
    design, calibration, errors = _run_children(root)
    required_points = tuple(str(point) for point in manifest.get("required_points") or ())
    if design.get("status") != "pass":
        errors.append("m3_0_design_lint_not_pass")
    point_statuses = dict(calibration.get("point_statuses") or {})
    for point_id in required_points:
        if point_id == "M3.0":
            continue
        if point_statuses.get(point_id) != "pass":
            errors.append(f"required_point_not_pass:{point_id}")
    calibration_path = root / "calibration" / "point01_m3_4_fixture_result_v1_0.json"
    negative_path = root / "calibration" / "point01_m3_5_fixture_result_v1_0.json"
    try:
        matrix_payload = _load_json(calibration_path)["payload"]
        present_sectors = {row["sector"] for row in matrix_payload.get("findings") or () if row.get("status") == "pass"}
        for sector in manifest.get("required_positive_sectors") or ():
            if sector not in present_sectors:
                errors.append(f"positive_sector_not_pass:{sector}")
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        errors.append("multi_sector_evidence_unreadable")
    try:
        negative_payload = _load_json(negative_path)["payload"]
        control_ids = " ".join(row.get("control_id", "") for row in negative_payload.get("findings") or ())
        if negative_payload.get("material_escape_count") != 0:
            errors.append("negative_control_material_escape_detected")
        for family in manifest.get("required_negative_families") or ():
            if family not in control_ids:
                errors.append(f"negative_family_not_observed:{family}")
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        errors.append("negative_control_evidence_unreadable")
    approval_path = ROOT / str(manifest.get("human_approval_path") or "")
    try:
        approval = _load_json(approval_path)
        errors.extend(_approval_errors(approval))
    except (OSError, json.JSONDecodeError):
        approval = {"status": "unreadable"}
        errors.append("human_reviewer_approval_unreadable")
    design_review_status = design.get("design_review_status")
    if design_review_status != "user_confirmed_calibration_accepted":
        errors.append("m3_0_design_review_user_confirmation_pending")
    hashes = {
        "configs/engineering_handoff/point01_m3_closeout_gate_manifest_v1_0.json": _sha256(DEFAULT_MANIFEST),
        "scripts/engineering/run_point01_m3_closeout_gate.py": _sha256(Path(__file__).resolve()),
        "configs/engineering_handoff/point01_m3_human_reviewer_approval_v1_0.json": _sha256(approval_path),
        "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md": _sha256(ROOT / "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md"),
    }
    unique_errors = sorted(set(errors))
    return {
        "result_version": "finsight_point01_m3_closeout_gate_result_v1_0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": manifest.get("scope"),
        "status": "pass" if not unique_errors else "fail_closed",
        "milestone": "M3_complete" if not unique_errors else "M3_closeout_pending",
        "unmet_conditions": unique_errors,
        "required_point_statuses": {"M3.0": design.get("status"), **point_statuses},
        "human_reviewer_approval_status": approval.get("status"),
        "design_review_status": design_review_status,
        "authority_boundary": manifest.get("authority_boundary"),
        "forbidden_admissions": manifest.get("forbidden_admissions"),
        "model_call_count": 0,
        "external_call_count": 0,
        "fixed_input_sha256": hashes,
        "boundary": "M3 closeout can only validate deterministic shadow comparison. It does not authorize M4 cutover, provider/model execution, Evidence/Writer runtime, or full-chain.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Point 01 M3 aggregate closeout gate.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--work-root", type=Path)
    args = parser.parse_args()
    manifest_path = args.manifest if args.manifest.is_absolute() else ROOT / args.manifest
    output_path = args.output if args.output.is_absolute() else ROOT / args.output
    work_root = args.work_root if args.work_root is None or args.work_root.is_absolute() else ROOT / args.work_root
    result = build_result(_load_json(manifest_path), work_root=work_root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "milestone": result["milestone"], "unmet_conditions": result["unmet_conditions"]}, ensure_ascii=False))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
