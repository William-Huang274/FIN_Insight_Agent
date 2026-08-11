from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "configs/engineering_handoff/point01_m2_design_freeze_manifest_v1_0.json"
DEFAULT_OUTPUT = ROOT / "data/manifests/point01_m2_design_lint_result_v1_0.json"
POINT_IDS = tuple(f"M2.{index}" for index in range(1, 11))
REQUIRED_CHILD_FIELDS = ("point_id", "owner", "owned_objects", "input_contracts", "output_contracts", "dependencies", "acceptance_boundary")
REQUIRED_BOUNDARIES = {
    "no_m3_shadow_comparison_or_reviewer_decision",
    "no_m4_authority_cutover",
    "no_paid_model_or_full_chain",
    "no_evidence_or_writer_runtime",
    "legacy_task_run_remains_authoritative",
    "decision_surface_remains_shadow_only",
}
ALLOWED_REVIEW_STATUSES = {
    "pending_cross_owner_review",
    "codex_multi_perspective_review_completed_pending_user_confirmation",
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


def _dependency_closure(point_id: str, dependencies: Mapping[str, tuple[str, ...]]) -> set[str]:
    closure: set[str] = set()
    frontier = list(dependencies.get(point_id, ()))
    while frontier:
        dependency = frontier.pop()
        if dependency in closure:
            continue
        closure.add(dependency)
        frontier.extend(dependencies.get(dependency, ()))
    return closure


def _validate_review_contract(review: Mapping[str, Any]) -> list[str]:
    status = review.get("status")
    if status not in ALLOWED_REVIEW_STATUSES or review.get("required_for_m2_0_calibration") is not True:
        return ["cross_owner_design_review_contract_invalid"]
    if status == "pending_cross_owner_review":
        return []
    evidence_path_value = str(review.get("evidence_path") or "")
    if not evidence_path_value:
        return ["cross_owner_design_review_evidence_missing"]
    evidence_path = ROOT / evidence_path_value
    try:
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ["cross_owner_design_review_evidence_unreadable"]
    expected_evidence_status = (
        "accepted_by_current_thread_user"
        if status == "user_confirmed_calibration_accepted"
        else "completed_pending_user_confirmation"
    )
    if evidence.get("status") != expected_evidence_status:
        return ["cross_owner_design_review_evidence_status_invalid"]
    if evidence.get("review_method") != "codex_single_agent_structured_role_separation":
        return ["cross_owner_design_review_method_invalid"]
    if evidence.get("independent_human_or_multi_person_signoff") is not False:
        return ["cross_owner_design_review_signoff_boundary_invalid"]
    if len(evidence.get("reviewer_lenses") or ()) != 5 or not evidence.get("findings"):
        return ["cross_owner_design_review_content_incomplete"]
    expected_overall_result = (
        "pass_with_resolved_design_findings_user_confirmed"
        if status == "user_confirmed_calibration_accepted"
        else "pass_with_resolved_design_findings_pending_user_confirmation"
    )
    if evidence.get("overall_result") != expected_overall_result:
        return ["cross_owner_design_review_result_invalid"]
    if status == "user_confirmed_calibration_accepted":
        confirmation = evidence.get("user_confirmation") or {}
        if not isinstance(confirmation, Mapping) or confirmation.get("status") != "accepted" or confirmation.get("approver_type") != "human":
            return ["cross_owner_design_review_user_confirmation_invalid"]
    return []


def validate_manifest(manifest: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if manifest.get("manifest_version") != "finsight_point01_m2_design_freeze_v1_0":
        errors.append("manifest_version_invalid")
    if manifest.get("scope") != "Point01_M2_0_design_freeze_only":
        errors.append("scope_invalid")
    if manifest.get("authority_boundary") != {"legacy_task_run": "authoritative", "canonical_lane": "shadow_only", "cutover": "forbidden"}:
        errors.append("authority_boundary_invalid")
    boundaries = set(manifest.get("enforced_boundaries") or ())
    missing_boundaries = sorted(REQUIRED_BOUNDARIES - boundaries)
    errors.extend(f"required_boundary_missing:{boundary}" for boundary in missing_boundaries)
    review = manifest.get("design_review") or {}
    if not isinstance(review, Mapping):
        errors.append("cross_owner_design_review_contract_invalid")
    else:
        errors.extend(_validate_review_contract(review))
    external_contracts = manifest.get("external_contracts")
    if not isinstance(external_contracts, Mapping):
        errors.append("external_contracts_not_mapping")
        external_contracts = {}
    for contract_name, declaration in external_contracts.items():
        if not isinstance(declaration, Mapping) or not declaration.get("provider") or not declaration.get("authority_boundary"):
            errors.append(f"external_contract_invalid:{contract_name}")

    children = manifest.get("child_contracts")
    if not isinstance(children, list):
        return errors + ["child_contracts_not_list"]
    point_ids = [str(child.get("point_id") or "") for child in children if isinstance(child, Mapping)]
    duplicate_points = sorted({point_id for point_id in point_ids if point_ids.count(point_id) > 1})
    errors.extend(f"duplicate_point_id:{point_id}" for point_id in duplicate_points)
    errors.extend(f"missing_point_id:{point_id}" for point_id in POINT_IDS if point_id not in point_ids)
    errors.extend(f"unexpected_point_id:{point_id}" for point_id in point_ids if point_id not in POINT_IDS)

    owners: set[str] = set()
    object_owners: dict[str, str] = {}
    output_producers: dict[str, str] = {}
    input_contracts_by_point: dict[str, tuple[str, ...]] = {}
    dependencies: dict[str, tuple[str, ...]] = {}
    for child in children:
        if not isinstance(child, Mapping):
            errors.append("child_contract_not_mapping")
            continue
        point_id = str(child.get("point_id") or "unknown")
        for field in REQUIRED_CHILD_FIELDS:
            value = child.get(field)
            is_empty_allowed = field == "dependencies" and value == []
            if field not in child or (not value and not is_empty_allowed):
                errors.append(f"{point_id}:required_field_missing:{field}")
        owner = str(child.get("owner") or "")
        if owner and owner in owners:
            errors.append(f"duplicate_child_owner:{owner}")
        owners.add(owner)
        for object_name in child.get("owned_objects") or ():
            object_key = str(object_name)
            prior_owner = object_owners.get(object_key)
            if prior_owner and prior_owner != point_id:
                errors.append(f"object_has_multiple_owners:{object_key}")
            object_owners[object_key] = point_id
        for contract_name in child.get("output_contracts") or ():
            contract_key = str(contract_name)
            prior_producer = output_producers.get(contract_key)
            if prior_producer and prior_producer != point_id:
                errors.append(f"output_contract_has_multiple_producers:{contract_key}")
            output_producers[contract_key] = point_id
        input_contracts_by_point[point_id] = tuple(str(value) for value in child.get("input_contracts") or ())
        deps = tuple(str(value) for value in child.get("dependencies") or ())
        dependencies[point_id] = deps
        for dependency in deps:
            if dependency == point_id:
                errors.append(f"self_dependency:{point_id}")
            elif dependency not in POINT_IDS:
                errors.append(f"unknown_dependency:{point_id}:{dependency}")

    if set(dependencies) == set(POINT_IDS) and _has_cycle(dependencies):
        errors.append("dependency_cycle_detected")
    if set(dependencies) == set(POINT_IDS):
        for point_id, input_contracts in input_contracts_by_point.items():
            reachable_producers = _dependency_closure(point_id, dependencies)
            for contract_name in input_contracts:
                producer = output_producers.get(contract_name)
                if producer is None:
                    if contract_name not in external_contracts:
                        errors.append(f"input_contract_without_producer_or_external_declaration:{point_id}:{contract_name}")
                elif producer != point_id and producer not in reachable_producers:
                    errors.append(f"input_contract_dependency_missing:{point_id}:{contract_name}:{producer}")
    expected_closeout_dependencies = set(POINT_IDS[:-1])
    closeout = next((child for child in children if isinstance(child, Mapping) and child.get("point_id") == "M2.10"), None)
    if not closeout or set(closeout.get("dependencies") or ()) != expected_closeout_dependencies:
        errors.append("m2_10_dependencies_must_cover_m2_1_to_m2_9")
    model = next((child for child in children if isinstance(child, Mapping) and child.get("point_id") == "M2.8"), None)
    model_policy = model.get("model_run_admission") if model else None
    if not isinstance(model_policy, Mapping) or model_policy.get("model_execution_permitted") is not False or not all(
        model_policy.get(field) is True
        for field in ("requires_explicit_approved_scoped_node", "requires_feature_flag", "requires_provider_preflight", "requires_budget_preflight")
    ):
        errors.append("m2_8_model_admission_must_fail_closed")
    return sorted(set(errors))


def build_result(manifest: Mapping[str, Any], *, manifest_path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    errors = validate_manifest(manifest)
    children = manifest.get("child_contracts") or []
    dependencies = [dependency for child in children if isinstance(child, Mapping) for dependency in child.get("dependencies") or ()]
    review = manifest.get("design_review") or {}
    review_evidence_path = ROOT / str(review.get("evidence_path") or "")
    fixed_inputs = {
        str(manifest_path.relative_to(ROOT)).replace("\\", "/"): _sha256(manifest_path),
        "scripts/engineering/run_point01_m2_design_lint.py": _sha256(Path(__file__).resolve()),
        "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md": _sha256(ROOT / "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md"),
    }
    if review.get("evidence_path") and review_evidence_path.is_file():
        fixed_inputs[str(review_evidence_path.relative_to(ROOT)).replace("\\", "/")] = _sha256(review_evidence_path)
    return {
        "result_version": "finsight_point01_m2_design_lint_result_v1_0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": manifest.get("scope"),
        "status": "pass" if not errors else "fail_closed",
        "errors": errors,
        "child_contract_count": len(children),
        "owner_count": len({str(child.get("owner")) for child in children if isinstance(child, Mapping)}),
        "dependency_edge_count": len(dependencies),
        "authority_boundary": manifest.get("authority_boundary"),
        "cross_owner_design_review_status": review.get("status"),
        "model_execution_permitted": False,
        "external_call_count": 0,
        "fixed_input_sha256": fixed_inputs,
        "boundary": "This lint freezes M2 child contracts only. It does not implement any child, admit a model, run a compiler, alter legacy authority, or advance to M3/M4.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Lint the Point 01 M2 child design-freeze manifest.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    manifest_path = args.manifest if args.manifest.is_absolute() else ROOT / args.manifest
    output_path = args.output if args.output.is_absolute() else ROOT / args.output
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    result = build_result(manifest, manifest_path=manifest_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "output": str(output_path), "errors": result["errors"]}, ensure_ascii=False))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
