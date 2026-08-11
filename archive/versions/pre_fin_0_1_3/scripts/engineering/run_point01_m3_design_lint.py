from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "configs/engineering_handoff/point01_m3_design_freeze_manifest_v1_0.json"
DEFAULT_OUTPUT = ROOT / "data/manifests/point01_m3_design_lint_result_v1_0.json"
POINT_IDS = tuple(f"M3.{index}" for index in range(1, 9))
REQUIRED_BOUNDARIES = {
    "no_m4_authority_cutover",
    "no_paid_model_or_full_chain",
    "no_evidence_or_writer_runtime",
    "legacy_task_run_remains_authoritative",
    "decision_surface_remains_shadow_only",
    "workbuddy_prompt_required_structure_is_not_independent_discovery",
    "review_actions_do_not_grant_cutover_authority",
}
ALLOWED_REVIEW_STATUSES = {
    "pending_cross_owner_review",
    "codex_structured_design_review_completed_pending_user_confirmation",
    "user_confirmed_calibration_accepted",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _has_cycle(dependencies: Mapping[str, tuple[str, ...]]) -> bool:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(point_id: str) -> bool:
        if point_id in visiting:
            return True
        if point_id in visited:
            return False
        visiting.add(point_id)
        for dependency in dependencies[point_id]:
            if dependency in dependencies and visit(dependency):
                return True
        visiting.remove(point_id)
        visited.add(point_id)
        return False

    return any(visit(point_id) for point_id in dependencies)


def validate_manifest(manifest: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if manifest.get("manifest_version") != "finsight_point01_m3_design_freeze_v1_0":
        errors.append("manifest_version_invalid")
    if manifest.get("scope") != "Point01_M3_0_design_freeze_only":
        errors.append("scope_invalid")
    if manifest.get("authority_boundary") != {"legacy_task_run": "authoritative", "canonical_lane": "shadow_only", "cutover": "forbidden"}:
        errors.append("authority_boundary_invalid")
    errors.extend(f"required_boundary_missing:{value}" for value in sorted(REQUIRED_BOUNDARIES - set(manifest.get("enforced_boundaries") or ())))
    review = manifest.get("design_review") or {}
    if not isinstance(review, Mapping) or review.get("status") not in ALLOWED_REVIEW_STATUSES or review.get("required_for_m3_0_calibration") is not True:
        errors.append("design_review_contract_invalid")
    elif review.get("status") != "pending_cross_owner_review":
        evidence_path = ROOT / str(review.get("evidence_path") or "")
        try:
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            errors.append("design_review_evidence_unreadable")
        else:
            if evidence.get("review_method") != "codex_single_agent_structured_role_separation" or evidence.get("independent_human_or_multi_person_signoff") is not False:
                errors.append("design_review_evidence_boundary_invalid")
            if len(evidence.get("reviewer_lenses") or ()) != 5 or len(evidence.get("findings") or ()) < 5:
                errors.append("design_review_evidence_incomplete")
            if evidence.get("status") not in {"completed_pending_user_confirmation", "accepted_by_current_thread_user"}:
                errors.append("design_review_evidence_status_invalid")
    children = manifest.get("child_contracts")
    if not isinstance(children, list):
        return errors + ["child_contracts_not_list"]
    ids = [str(row.get("point_id") or "") for row in children if isinstance(row, Mapping)]
    errors.extend(f"missing_point_id:{point_id}" for point_id in POINT_IDS if point_id not in ids)
    errors.extend(f"unexpected_point_id:{point_id}" for point_id in ids if point_id not in POINT_IDS)
    if len(set(ids)) != len(ids):
        errors.append("duplicate_point_id")
    owners: set[str] = set()
    object_owners: dict[str, str] = {}
    dependencies: dict[str, tuple[str, ...]] = {}
    for row in children:
        if not isinstance(row, Mapping):
            errors.append("child_contract_not_mapping")
            continue
        point_id = str(row.get("point_id") or "unknown")
        for field in ("point_id", "owner", "owned_objects", "input_contracts", "output_contracts", "dependencies", "acceptance_boundary"):
            if field not in row or (not row[field] and not (field == "dependencies" and row[field] == [])):
                errors.append(f"{point_id}:required_field_missing:{field}")
        owner = str(row.get("owner") or "")
        if owner in owners:
            errors.append(f"duplicate_owner:{owner}")
        owners.add(owner)
        for object_name in row.get("owned_objects") or ():
            previous = object_owners.get(str(object_name))
            if previous and previous != point_id:
                errors.append(f"object_has_multiple_owners:{object_name}")
            object_owners[str(object_name)] = point_id
        dependencies[point_id] = tuple(str(value) for value in row.get("dependencies") or ())
        for dependency in dependencies[point_id]:
            if dependency not in POINT_IDS or dependency == point_id:
                errors.append(f"invalid_dependency:{point_id}:{dependency}")
    if set(dependencies) == set(POINT_IDS) and _has_cycle(dependencies):
        errors.append("dependency_cycle_detected")
    closeout = next((row for row in children if isinstance(row, Mapping) and row.get("point_id") == "M3.8"), None)
    if not closeout or set(closeout.get("dependencies") or ()) != set(POINT_IDS[:-1]):
        errors.append("m3_8_dependencies_must_cover_m3_1_to_m3_7")
    return sorted(set(errors))


def build_result(manifest: Mapping[str, Any], *, manifest_path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    errors = validate_manifest(manifest)
    review_path = ROOT / str((manifest.get("design_review") or {}).get("evidence_path") or "")
    hashes = {
        str(manifest_path.relative_to(ROOT)).replace("\\", "/"): _sha256(manifest_path),
        "scripts/engineering/run_point01_m3_design_lint.py": _sha256(Path(__file__).resolve()),
        "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md": _sha256(ROOT / "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md"),
    }
    if review_path.is_file():
        hashes[str(review_path.relative_to(ROOT)).replace("\\", "/")] = _sha256(review_path)
    return {
        "result_version": "finsight_point01_m3_design_lint_result_v1_0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": manifest.get("scope"),
        "status": "pass" if not errors else "fail_closed",
        "errors": errors,
        "child_contract_count": len(manifest.get("child_contracts") or ()),
        "authority_boundary": manifest.get("authority_boundary"),
        "design_review_status": (manifest.get("design_review") or {}).get("status"),
        "model_call_count": 0,
        "external_call_count": 0,
        "fixed_input_sha256": hashes,
        "boundary": "This lint freezes M3 contracts. It neither accepts human reviewer approval nor changes legacy authority, cutover, evidence, writer, provider, or full-chain admission.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Lint the Point 01 M3 design-freeze manifest.")
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
