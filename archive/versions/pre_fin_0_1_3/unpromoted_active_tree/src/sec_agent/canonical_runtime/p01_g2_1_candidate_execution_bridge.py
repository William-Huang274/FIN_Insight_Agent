"""Candidate-bound P01-G2.1 baseline-only execution bridge.

The accepted final candidate is intentionally a freeze-only artifact and must
never be relaxed into a v2 execution package.  This module instead derives a
separate v2.10-compatible inner package and verifies a strict outer P01
baseline-only envelope.  It owns no authority, receipt lifecycle, or runtime
kernel; those remain in the existing v2.10 family.
"""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping

from .m2_a1_execution_receipt import M2A1ExecutionPreflightError, execution_package_contract, preflight_exact_execution
from .models import canonical_digest
from .p01_g2_1_operational_tranche import (
    ACTOR_ID,
    AI_SEMIS_CASE_INSTANCE_PACK_PAYLOAD_DIGEST,
    AI_SEMIS_CASE_INSTANCE_PACK_REF,
    BASELINE_CASE_ID,
    BASELINE_INPUT_REF,
    BASELINE_MUTATION,
    BASELINE_SCENARIO_ID,
    P01_G2_1_PACKAGE_SCHEMA,
    REVIEWER_IDENTITY,
    candidate_gate_payload,
    candidate_manifest_payload,
    candidate_package_payload,
    candidate_preflight_payload,
)


BRIDGE_MODE = "candidate_bound_baseline_only_v2_10"
BRIDGE_STATUS = "P01_G2_FINAL_BASELINE_EXECUTABLE_BRIDGE_REFREEZE_PENDING_INDEPENDENT_REVIEW"
BRIDGE_MANIFEST_SCHEMA = "finsight_point01_p01_g2_1_candidate_execution_bridge_manifest_v1_0"
BRIDGE_PREFLIGHT_SCHEMA = "finsight_point01_p01_g2_1_candidate_execution_bridge_preflight_v1_0"
BRIDGE_GATE_SCHEMA = "finsight_point01_p01_g2_1_candidate_execution_bridge_gate_v1_0"


def _without(value: Mapping[str, Any], digest_field: str) -> dict[str, Any]:
    return {key: item for key, item in value.items() if key != digest_field}


def bridge_manifest_payload(value: Mapping[str, Any]) -> dict[str, Any]:
    return _without(value, "bridge_manifest_digest")


def bridge_package_payload(value: Mapping[str, Any]) -> dict[str, Any]:
    return _without(value, "package_digest")


def bridge_preflight_payload(value: Mapping[str, Any]) -> dict[str, Any]:
    return _without(value, "preflight_digest")


def bridge_gate_payload(value: Mapping[str, Any]) -> dict[str, Any]:
    return _without(value, "gate_digest")


def file_digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _candidate_valid(candidate: Mapping[str, Any], manifest: Mapping[str, Any], preflight: Mapping[str, Any], gate: Mapping[str, Any]) -> bool:
    if manifest.get("manifest_digest") != canonical_digest(candidate_manifest_payload(manifest)):
        return False
    if candidate.get("candidate_digest") != canonical_digest(candidate_package_payload(candidate)):
        return False
    if preflight.get("preflight_digest") != canonical_digest(candidate_preflight_payload(preflight)):
        return False
    if gate.get("gate_digest") != canonical_digest(candidate_gate_payload(gate)):
        return False
    hashes = manifest.get("input_file_sha256")
    return (
        isinstance(hashes, Mapping)
        and manifest.get("input_hash_count") == len(hashes) == 100
        and candidate.get("manifest_digest") == manifest.get("manifest_digest")
        and preflight.get("candidate_digest") == candidate.get("candidate_digest")
        and gate.get("candidate_digest") == candidate.get("candidate_digest")
        and gate.get("preflight_digest") == preflight.get("preflight_digest")
    )


def validate_execution_package(
    package: Mapping[str, Any],
    *,
    manifest: Mapping[str, Any],
    candidate: Mapping[str, Any],
    candidate_preflight: Mapping[str, Any],
    candidate_gate: Mapping[str, Any],
    inner_package: Mapping[str, Any],
    inner_package_gate: Mapping[str, Any],
    plan: Mapping[str, Any],
    plan_gate: Mapping[str, Any],
    blueprint: Mapping[str, Any],
    blueprint_gate: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate only the candidate-bound baseline mode; legacy P01 stays untouched."""

    errors: list[str] = []
    if package.get("schema_version") != P01_G2_1_PACKAGE_SCHEMA:
        errors.append("execution_package_schema_invalid")
    if package.get("execution_mode") != BRIDGE_MODE or package.get("status") != BRIDGE_STATUS:
        errors.append("execution_package_mode_invalid")
    if package.get("package_digest") != canonical_digest(bridge_package_payload(package)):
        errors.append("execution_package_digest_invalid")
    if not _candidate_valid(candidate, manifest, candidate_preflight, candidate_gate):
        errors.append("candidate_artifact_contract_invalid")
    expected_candidate = {
        "manifest_digest": manifest.get("manifest_digest"),
        "candidate_digest": candidate.get("candidate_digest"),
        "candidate_preflight_digest": candidate_preflight.get("preflight_digest"),
        "candidate_gate_digest": candidate_gate.get("gate_digest"),
        "input_hash_count": manifest.get("input_hash_count"),
        "case_instance_pack_ref": AI_SEMIS_CASE_INSTANCE_PACK_REF,
        "case_instance_pack_payload_digest": AI_SEMIS_CASE_INSTANCE_PACK_PAYLOAD_DIGEST,
    }
    if package.get("candidate_bindings") != expected_candidate:
        errors.append("candidate_exact_binding_invalid")
    if candidate.get("case_instance_pack") != {
        "pack_version_id": AI_SEMIS_CASE_INSTANCE_PACK_REF,
        "payload_digest": AI_SEMIS_CASE_INSTANCE_PACK_PAYLOAD_DIGEST,
        "case_id": BASELINE_INPUT_REF,
        "override_mode": "no_override",
    }:
        errors.append("candidate_case_instance_pack_invalid")
    baseline = {
        "case_id": BASELINE_CASE_ID,
        "scenario_id": BASELINE_SCENARIO_ID,
        "input_ref": BASELINE_INPUT_REF,
        "mutation": BASELINE_MUTATION,
        "reviewer_identity": REVIEWER_IDENTITY,
        "actor_id": ACTOR_ID,
        "single_use": True,
        "no_retry_replay_or_renewal": True,
    }
    if package.get("baseline_contract") != baseline:
        errors.append("baseline_contract_invalid")
    if package.get("negative_cases") != {"enabled": False, "authorization": "not_authorized"}:
        errors.append("negative_cases_not_disabled")
    zero_counts = package.get("execution_counts")
    if not isinstance(zero_counts, Mapping) or any(value != 0 for value in zero_counts.values()):
        errors.append("bridge_execution_counts_not_zero")
    try:
        contract = execution_package_contract(inner_package)
        if contract.schema_version != "finsight_point01_m2_a1_execution_ready_audit_package_manifest_v2_10":
            errors.append("inner_v2_contract_not_v2_10")
    except M2A1ExecutionPreflightError as exc:
        errors.append(f"inner_v2_contract_invalid:{exc}")
    if inner_package.get("package_digest") != canonical_digest({key: value for key, value in inner_package.items() if key != "package_digest"}):
        errors.append("inner_v2_digest_invalid")
    if inner_package.get("input_file_sha256") != manifest.get("input_file_sha256"):
        errors.append("inner_v2_candidate_input_inventory_invalid")
    expected_inner = {
        "package_digest": inner_package.get("package_digest"),
        "package_gate_digest": inner_package_gate.get("gate_digest"),
        "plan_digest": plan.get("plan_digest"),
        "plan_gate_digest": plan_gate.get("gate_digest"),
        "blueprint_digest": blueprint.get("blueprint_digest"),
        "blueprint_gate_digest": blueprint_gate.get("gate_digest"),
    }
    if package.get("derived_v2_10") != expected_inner:
        errors.append("derived_v2_exact_binding_invalid")
    if inner_package_gate.get("package_digest") != inner_package.get("package_digest") or inner_package_gate.get("status") != "pass":
        errors.append("inner_v2_gate_invalid")
    if plan.get("plan_digest") != canonical_digest(_without(plan, "plan_digest")) or plan_gate.get("status") != "pass":
        errors.append("inner_v2_plan_invalid")
    if blueprint.get("blueprint_digest") != canonical_digest(_without(blueprint, "blueprint_digest")) or blueprint_gate.get("status") != "pass":
        errors.append("inner_v2_blueprint_invalid")
    return {"status": "pass" if not errors else "fail_closed", "errors": tuple(sorted(errors)), "package_digest": package.get("package_digest")}


def preflight_candidate_bound_execution(
    package: Mapping[str, Any],
    *,
    repository_root: Path,
    manifest: Mapping[str, Any],
    candidate: Mapping[str, Any],
    candidate_preflight: Mapping[str, Any],
    candidate_gate: Mapping[str, Any],
    inner_package: Mapping[str, Any],
    inner_package_gate: Mapping[str, Any],
    plan: Mapping[str, Any],
    plan_gate: Mapping[str, Any],
    blueprint: Mapping[str, Any],
    blueprint_gate: Mapping[str, Any],
    index_reader: Any,
) -> dict[str, Any]:
    """Read-only bridge preflight; its only allowed v2 result is no-admission deny."""

    verification = validate_execution_package(
        package,
        manifest=manifest,
        candidate=candidate,
        candidate_preflight=candidate_preflight,
        candidate_gate=candidate_gate,
        inner_package=inner_package,
        inner_package_gate=inner_package_gate,
        plan=plan,
        plan_gate=plan_gate,
        blueprint=blueprint,
        blueprint_gate=blueprint_gate,
    )
    errors = list(verification["errors"])
    index_matches = 0
    working_matches = 0
    for relative, expected in manifest["input_file_sha256"].items():
        indexed = index_reader(repository_root, str(relative))
        if sha256(indexed).hexdigest() != expected:
            errors.append(f"candidate_index_hash_mismatch:{relative}")
            continue
        index_matches += 1
        working = (repository_root / str(relative)).read_bytes()
        if working.replace(b"\r\n", b"\n") != indexed.replace(b"\r\n", b"\n"):
            errors.append(f"candidate_working_drift:{relative}")
            continue
        working_matches += 1
    try:
        preflight_exact_execution(
            inner_package,
            None,
            repository_root=repository_root,
            receipt_id="candidate-bridge-no-receipt",
            scenario_id=BASELINE_SCENARIO_ID,
            human_approval_digest="0" * 64,
            index_reader=index_reader,
        )
    except M2A1ExecutionPreflightError as exc:
        if str(exc) != "package_admission_required":
            errors.append(f"production_preflight:{exc}")
    else:
        errors.append("production_preflight_missing_admission_unexpected_pass")
    fixed_path = repository_root / str(inner_package["fixed_store_fingerprints"]["fixed_approval_store"]["path"])
    if file_digest(fixed_path) != candidate["exact_bindings"]["fixed_store_sha256"]:
        errors.append("fixed_store_fingerprint_drift")
    namespace = Path(str(inner_package["execution_preflight"]["execution_staging_namespace_path"]))
    if namespace.exists():
        errors.append("candidate_bound_namespace_must_be_absent")
    payload = {
        "schema_version": BRIDGE_PREFLIGHT_SCHEMA,
        "status": "pass" if not errors else "fail_closed",
        "package_digest": package.get("package_digest"),
        "candidate_digest": candidate.get("candidate_digest"),
        "candidate_manifest_digest": manifest.get("manifest_digest"),
        "candidate_input_hash_match_count": index_matches,
        "candidate_working_index_match_count": working_matches,
        "candidate_input_hash_count": len(manifest["input_file_sha256"]),
        "production_preflight_without_admission": "package_admission_required" if not any(error.startswith("production_preflight:") for error in errors) else "fail_closed",
        "fixed_store_sha256": file_digest(fixed_path),
        "formal_namespace_absent": not namespace.exists(),
        "execution_counts": dict(package["execution_counts"]),
        "verification": verification,
        "errors": tuple(sorted(errors)),
    }
    return {**payload, "preflight_digest": canonical_digest(payload)}
