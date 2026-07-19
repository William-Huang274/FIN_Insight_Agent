from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "configs/engineering_handoff/point01_m4_design_freeze_manifest_v1_0.json"
DEFAULT_OUTPUT = ROOT / "data/manifests/point01_m4_design_lint_result_v1_0.json"
POINT_IDS = tuple(f"M4.{number}" for number in range(1, 9))
REQUIRED_BOUNDARIES = {"no_global_or_sector_cutover", "no_legacy_taskrun_authority_change", "no_dual_authoritative_write", "legacy_projection_read_only_only", "no_evidence_writer_provider_or_full_chain_admission", "approval_must_bind_schema_policy_artifact_comparison_hash", "kill_switch_allows_only_rollback_control_transaction"}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_manifest(manifest: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if manifest.get("manifest_version") != "finsight_point01_m4_design_freeze_v1_0" or manifest.get("scope") != "Point01_M4_0_design_freeze_only":
        errors.append("manifest_identity_invalid")
    if manifest.get("authority_boundary") != {"legacy_task_run": "authoritative", "canonical_lane": "case_scoped_planning_only_after_approval", "cutover": "m4_case_scoped_only"}:
        errors.append("authority_boundary_invalid")
    errors.extend(f"required_boundary_missing:{value}" for value in sorted(REQUIRED_BOUNDARIES - set(manifest.get("enforced_boundaries") or ())))
    review = manifest.get("design_review") or {}
    path = ROOT / str(review.get("evidence_path") or "")
    try:
        evidence = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        evidence = {}
        errors.append("design_review_evidence_unreadable")
    if review.get("required_for_m4_0_calibration") is not True or review.get("status") not in {"codex_structured_design_review_completed_pending_user_confirmation", "user_confirmed_calibration_accepted"}:
        errors.append("design_review_contract_invalid")
    if evidence.get("review_method") != "codex_single_agent_structured_role_separation" or evidence.get("independent_human_or_multi_person_signoff") is not False or len(evidence.get("reviewer_lenses") or ()) != 5 or len(evidence.get("findings") or ()) < 5:
        errors.append("design_review_evidence_invalid")
    children = manifest.get("child_contracts")
    if not isinstance(children, list):
        return errors + ["child_contracts_not_list"]
    ids = [str(row.get("point_id") or "") for row in children if isinstance(row, Mapping)]
    errors.extend(f"missing_point:{point}" for point in POINT_IDS if point not in ids)
    if len(set(ids)) != len(ids):
        errors.append("duplicate_point_id")
    owners: set[str] = set()
    dependencies: dict[str, tuple[str, ...]] = {}
    for row in children:
        if not isinstance(row, Mapping):
            errors.append("child_not_mapping")
            continue
        point = str(row.get("point_id") or "unknown")
        for field in ("owner", "owned_objects", "input_contracts", "output_contracts", "dependencies", "acceptance_boundary"):
            if field not in row or (not row[field] and not (field == "dependencies" and row[field] == [])):
                errors.append(f"{point}:missing:{field}")
        if str(row.get("owner") or "") in owners:
            errors.append(f"duplicate_owner:{row.get('owner')}")
        owners.add(str(row.get("owner") or ""))
        dependencies[point] = tuple(str(value) for value in row.get("dependencies") or ())
    closeout = next((row for row in children if isinstance(row, Mapping) and row.get("point_id") == "M4.8"), None)
    if not closeout or set(closeout.get("dependencies") or ()) != set(POINT_IDS[:-1]):
        errors.append("m4_8_dependencies_incomplete")
    for point, deps in dependencies.items():
        for dep in deps:
            if dep not in POINT_IDS or dep == point:
                errors.append(f"invalid_dependency:{point}:{dep}")
    return sorted(set(errors))


def build_result(manifest: Mapping[str, Any], *, manifest_path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    errors = validate_manifest(manifest)
    review_path = ROOT / str((manifest.get("design_review") or {}).get("evidence_path") or "")
    hashes = {str(manifest_path.relative_to(ROOT)).replace("\\", "/"): _sha256(manifest_path), "scripts/engineering/run_point01_m4_design_lint.py": _sha256(Path(__file__).resolve()), "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md": _sha256(ROOT / "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md")}
    if review_path.is_file():
        hashes[str(review_path.relative_to(ROOT)).replace("\\", "/")] = _sha256(review_path)
    return {"result_version": "finsight_point01_m4_design_lint_result_v1_0", "generated_at": datetime.now(timezone.utc).isoformat(), "status": "pass" if not errors else "fail_closed", "errors": errors, "child_contract_count": len(manifest.get("child_contracts") or ()), "authority_boundary": manifest.get("authority_boundary"), "design_review_status": (manifest.get("design_review") or {}).get("status"), "model_call_count": 0, "external_call_count": 0, "fixed_input_sha256": hashes, "boundary": "M4 design lint freezes case-scoped cutover contracts only. It does not execute a pilot cutover, change legacy TaskRun authority, or admit downstream/model/full-chain runtime."}


def main() -> int:
    parser = argparse.ArgumentParser(description="Lint Point 01 M4 cutover design freeze.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    manifest_path = args.manifest if args.manifest.is_absolute() else ROOT / args.manifest
    output_path = args.output if args.output.is_absolute() else ROOT / args.output
    result = build_result(json.loads(manifest_path.read_text(encoding="utf-8")), manifest_path=manifest_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "output": str(output_path), "errors": result["errors"]}, ensure_ascii=False))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
