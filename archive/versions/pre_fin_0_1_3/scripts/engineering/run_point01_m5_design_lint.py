from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "configs/engineering_handoff/point01_m5_design_freeze_manifest_v1_0.json"
DEFAULT_CROSS_OWNER_REVIEW = ROOT / "configs/engineering_handoff/point01_m5_cross_owner_design_review_v1_0.json"
DEFAULT_HUMAN_REVIEW = ROOT / "configs/engineering_handoff/point01_m5_human_ops_security_review_v1_0.json"
DEFAULT_OUTPUT = ROOT / "data/manifests/point01_m5_design_lint_result_v1_0.json"
POINT_IDS = tuple(f"M5.{number}" for number in range(1, 10))
REQUIRED_FORBIDDEN_ADMISSIONS = {
    "business_case_mutation",
    "legacy_taskrun_authority_change",
    "provider_execution",
    "evidence_runtime",
    "writer_runtime",
    "full_chain",
    "sector_tenant_global_cutover",
}
REQUIRED_EXTERNAL_PATTERNS = {
    "temporal_durable_workflow",
    "langgraph_checkpoint_interrupt_resume",
    "p32_durable_hil_task_event_contract",
    "mcp_tool_gateway",
    "opentelemetry_langfuse_phoenix_eval_trace",
}
REQUIRED_ACCEPTANCE = {
    "M5.1": {"duplicate worker is fenced", "expired lease is reclaimable", "cancel reaches active and queued work", "worker loss is observable"},
    "M5.2": {"poison work cannot retry", "retry budget terminates", "resume uses exact checkpoint", "dead letter is inspectable"},
    "M5.3": {"checkpoint is atomic with event", "stale write fails", "supersession retains prior version", "restart can recover exact snapshot"},
    "M5.4": {"unknown capability denied", "tenant cross-read denied", "network/path/tool scope denied", "grant expiry revokes execution"},
    "M5.5": {"budget is reserved before admission", "terminal stop prevents retry", "refund is traceable", "no overrun by fallback"},
    "M5.6": {"expired/revoked approval fails closed", "pause survives restart", "resume requires exact scope digest", "review action is append-only"},
    "M5.7": {"irrelevant delta does not cancel", "relevant delta invalidates dependent branch", "shared mutable context is rejected", "causality is retained"},
    "M5.8": {"reconnect does not duplicate", "events retain ordering", "redaction is enforced", "incident replay is inspectable"},
    "M5.9": {"all child points pass", "crash/security/cost/HITL suites pass", "human ops/security acceptance recorded", "no forbidden runtime admission"},
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


def _read_json(path: Path, errors: list[str], error: str) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        errors.append(error)
        return {}
    if not isinstance(value, Mapping):
        errors.append(error)
        return {}
    return value


def validate_manifest(
    manifest: Mapping[str, Any],
    *,
    cross_owner_review: Mapping[str, Any] | None = None,
    human_review: Mapping[str, Any] | None = None,
) -> list[str]:
    errors: list[str] = []
    if manifest.get("manifest_version") != "finsight_point01_m5_design_freeze_v1_0":
        errors.append("manifest_version_invalid")
    if manifest.get("scope") != "Point01_M5_durable_harness" or manifest.get("point_id") != "M5.0":
        errors.append("manifest_scope_invalid")
    if manifest.get("status") not in {"frozen_structured_review_complete_human_ops_security_pending", "frozen_human_ops_security_approved"}:
        errors.append("manifest_status_invalid")
    if manifest.get("prerequisites") != {
        "m1_status": "M1_complete",
        "m4_status": "M4_complete_nonproduction_synthetic_pilot",
        "legacy_task_run_authority": "authoritative",
    }:
        errors.append("prerequisites_invalid")
    if manifest.get("authority_boundary") != {
        "legacy_task_run": "authoritative_execution_history_owner",
        "canonical_runtime": "durable_harness_control_plane_only",
        "decision_surface": "case_scoped_planning_pilot_proven_only",
        "model_execution": "not_admitted",
        "evidence_writer_full_chain": "not_admitted",
    }:
        errors.append("authority_boundary_invalid")
    errors.extend(f"missing_forbidden_admission:{item}" for item in sorted(REQUIRED_FORBIDDEN_ADMISSIONS - set(manifest.get("forbidden_admissions") or ())))
    errors.extend(f"missing_external_pattern:{item}" for item in sorted(REQUIRED_EXTERNAL_PATTERNS - set(manifest.get("external_pattern_adoptions") or ())))

    children = manifest.get("children")
    if not isinstance(children, list):
        return sorted(set(errors + ["children_not_list"]))
    ids = [str(row.get("point_id") or "") for row in children if isinstance(row, Mapping)]
    errors.extend(f"missing_point_id:{point_id}" for point_id in POINT_IDS if point_id not in ids)
    errors.extend(f"unexpected_point_id:{point_id}" for point_id in ids if point_id not in POINT_IDS)
    if len(set(ids)) != len(ids):
        errors.append("duplicate_point_id")
    owners: set[str] = set()
    dependencies: dict[str, tuple[str, ...]] = {}
    for row in children:
        if not isinstance(row, Mapping):
            errors.append("child_not_mapping")
            continue
        point_id = str(row.get("point_id") or "unknown")
        for field in ("point_id", "owner", "responsibility", "inputs", "outputs", "dependencies", "external_dependencies", "acceptance", "non_goals"):
            if field not in row or (not row[field] and not (field == "dependencies" and row[field] == [])):
                errors.append(f"{point_id}:required_field_missing:{field}")
        owner = str(row.get("owner") or "")
        if owner in owners:
            errors.append(f"duplicate_owner:{owner}")
        owners.add(owner)
        deps = tuple(str(item) for item in row.get("dependencies") or ())
        dependencies[point_id] = deps
        for dependency in deps:
            if dependency not in POINT_IDS or dependency == point_id:
                errors.append(f"invalid_dependency:{point_id}:{dependency}")
        required_acceptance = REQUIRED_ACCEPTANCE.get(point_id, set())
        missing_acceptance = required_acceptance - set(row.get("acceptance") or ())
        errors.extend(f"{point_id}:missing_acceptance:{item}" for item in sorted(missing_acceptance))
    if set(dependencies) == set(POINT_IDS) and _has_cycle(dependencies):
        errors.append("dependency_cycle_detected")
    closeout = next((row for row in children if isinstance(row, Mapping) and row.get("point_id") == "M5.9"), None)
    if not closeout or set(closeout.get("dependencies") or ()) != set(POINT_IDS[:-1]):
        errors.append("m5_9_dependencies_must_cover_m5_1_to_m5_8")

    requirement = manifest.get("human_review_requirement") or {}
    if requirement != {
        "status": "pending_human_ops_security_review",
        "required_decision": "approve_m5_durable_harness_design_freeze_only",
        "scope": "M5 design only; it cannot authorize M5.1 worker execution or later runtime admission",
    }:
        errors.append("human_review_requirement_invalid")
    if cross_owner_review is not None:
        if cross_owner_review.get("review_version") != "finsight_point01_m5_cross_owner_design_review_v1_0" or cross_owner_review.get("status") != "structured_internal_review_complete_human_ops_security_pending":
            errors.append("cross_owner_review_invalid")
        expected_lenses = {"state_machine", "security", "reliability", "operations", "concurrency", "governance"}
        lenses = {str(item.get("lens")) for item in cross_owner_review.get("review_lenses") or () if isinstance(item, Mapping)}
        errors.extend(f"cross_owner_lens_missing:{lens}" for lens in sorted(expected_lenses - lenses))
        remaining_human_review = " ".join(str(item) for item in cross_owner_review.get("remaining_human_review") or ()).lower()
        if "human approval" not in remaining_human_review and "human ops/security acceptance" not in remaining_human_review:
            errors.append("cross_owner_human_review_boundary_missing")
    if human_review is not None:
        status = human_review.get("status")
        exact_decision = "approve_m5_durable_harness_design_freeze_only"
        if human_review.get("review_version") != "finsight_point01_m5_human_ops_security_review_v1_0" or human_review.get("required_decision") != exact_decision:
            errors.append("human_review_identity_invalid")
        if status == "pending_human_ops_security_review":
            if any(human_review.get(key) is not None for key in ("reviewer_identity", "reviewed_at", "decision")):
                errors.append("pending_human_review_must_not_claim_decision")
        elif status == "approved_m5_design_freeze_only":
            if not all(human_review.get(key) for key in ("reviewer_identity", "reviewed_at")) or human_review.get("decision") != exact_decision:
                errors.append("approved_human_review_receipt_invalid")
        else:
            errors.append("human_review_status_invalid")
        notes = str(human_review.get("notes") or "")
        if "cannot authorize" not in notes or "worker" not in notes or "full-chain" not in notes:
            errors.append("human_review_runtime_boundary_missing")
    return sorted(set(errors))


def build_result(
    manifest: Mapping[str, Any],
    *,
    manifest_path: Path = DEFAULT_MANIFEST,
    cross_owner_review_path: Path = DEFAULT_CROSS_OWNER_REVIEW,
    human_review_path: Path = DEFAULT_HUMAN_REVIEW,
) -> dict[str, Any]:
    errors: list[str] = []
    cross_owner_review = _read_json(cross_owner_review_path, errors, "cross_owner_review_unreadable")
    human_review = _read_json(human_review_path, errors, "human_review_unreadable")
    errors.extend(validate_manifest(manifest, cross_owner_review=cross_owner_review, human_review=human_review))
    hashes = {
        str(manifest_path.relative_to(ROOT)).replace("\\", "/"): _sha256(manifest_path),
        str(cross_owner_review_path.relative_to(ROOT)).replace("\\", "/"): _sha256(cross_owner_review_path),
        str(human_review_path.relative_to(ROOT)).replace("\\", "/"): _sha256(human_review_path),
        "scripts/engineering/run_point01_m5_design_lint.py": _sha256(Path(__file__).resolve()),
        "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md": _sha256(ROOT / "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md"),
    }
    return {
        "result_version": "finsight_point01_m5_design_lint_result_v1_0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": manifest.get("scope"),
        "status": "pass" if not errors else "fail_closed",
        "errors": sorted(set(errors)),
        "child_contract_count": len(manifest.get("children") or ()),
        "manifest_status": manifest.get("status"),
        "human_ops_security_review_status": human_review.get("status"),
        "authority_boundary": manifest.get("authority_boundary"),
        "model_call_count": 0,
        "external_call_count": 0,
        "fixed_input_sha256": hashes,
        "boundary": "This is an M5.0 design-freeze lint only. A pass does not approve M5.1 execution or admit a worker, queue service, external tool, provider, Evidence/Writer, full-chain, business Case mutation, legacy authority change, or global cutover.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Lint Point 01 M5 durable-harness design freeze.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--cross-owner-review", type=Path, default=DEFAULT_CROSS_OWNER_REVIEW)
    parser.add_argument("--human-review", type=Path, default=DEFAULT_HUMAN_REVIEW)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    manifest_path = args.manifest if args.manifest.is_absolute() else ROOT / args.manifest
    cross_owner_path = args.cross_owner_review if args.cross_owner_review.is_absolute() else ROOT / args.cross_owner_review
    human_review_path = args.human_review if args.human_review.is_absolute() else ROOT / args.human_review
    output_path = args.output if args.output.is_absolute() else ROOT / args.output
    manifest = _read_json(manifest_path, [], "manifest_unreadable")
    result = build_result(manifest, manifest_path=manifest_path, cross_owner_review_path=cross_owner_path, human_review_path=human_review_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "output": str(output_path), "errors": result["errors"]}, ensure_ascii=False))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
