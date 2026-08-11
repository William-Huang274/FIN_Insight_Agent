"""P01-G2.1 exact operational-tranche bindings.

This module intentionally does not define a second admission, receipt, ledger,
or execution lifecycle.  It verifies the P01 envelope and delegates the sole
authority lifecycle to the accepted M2-A1 v2.10 production kernel.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping

from .models import canonical_digest


P01_G2_1_PACKAGE_SCHEMA = "finsight_point01_p01_g2_1_operational_execution_package_v1_0"
P01_G2_1_GATE_SCHEMA = "finsight_point01_p01_g2_1_operational_execution_package_gate_v1_0"
P01_G2_1_AUTHORITY_SCHEMA = "finsight_point01_p01_g2_1_package_external_reviewer_decision_v1_0"
P01_G2_1_FINAL_BASELINE_CANDIDATE_MANIFEST_SCHEMA = "finsight_point01_p01_g2_1_final_baseline_candidate_manifest_v1_0"
P01_G2_1_FINAL_BASELINE_CANDIDATE_SCHEMA = "finsight_point01_p01_g2_1_final_baseline_candidate_package_v1_0"
P01_G2_1_FINAL_BASELINE_CANDIDATE_GATE_SCHEMA = "finsight_point01_p01_g2_1_final_baseline_candidate_gate_v1_0"
P01_G2_1_FINAL_BASELINE_CANDIDATE_PREFLIGHT_SCHEMA = "finsight_point01_p01_g2_1_final_baseline_candidate_preflight_v1_0"
BASELINE_CASE_ID = "g2-baseline"
BASELINE_SCENARIO_ID = "p01-baseline-separated-input"
BASELINE_INPUT_REF = "m2-a1-ai-semis-input"
BASELINE_MUTATION = "none"
REVIEWER_IDENTITY = "william/003/total_reviewer"
ACTOR_ID = "003"
AI_SEMIS_CASE_INSTANCE_PACK_REF = "pack-case-m2-a1-ai-semis-no-override:v1"
AI_SEMIS_CASE_INSTANCE_PACK_PAYLOAD_DIGEST = "71d9a25e7973db55ec0a99295e90d51d9acb2ed87c988b548d4e8089d00d28b9"


def digest_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def utc_json(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value):
        raise ValueError("p01_g2_1_utc_required")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def package_payload(value: Mapping[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if key != "package_digest"}


def candidate_manifest_payload(value: Mapping[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if key != "manifest_digest"}


def candidate_package_payload(value: Mapping[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if key != "candidate_digest"}


def candidate_gate_payload(value: Mapping[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if key != "gate_digest"}


def candidate_preflight_payload(value: Mapping[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if key != "preflight_digest"}


def authority_payload(value: Mapping[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if key != "authority_digest"}


def result_payload(value: Mapping[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if key != "result_digest"}


def write_verified_json(path: Path, value: Mapping[str, Any], *, digest_field: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    loaded = json.loads(path.read_text(encoding="utf-8"))
    expected = str(value[digest_field])
    if loaded.get(digest_field) != expected:
        raise OSError(f"p01_g2_1_artifact_readback_failed:{path.name}")
    return digest_file(path)


def validate_execution_package(
    package: Mapping[str, Any],
    *,
    tranche: Mapping[str, Any],
    tranche_gate: Mapping[str, Any],
    v2_package: Mapping[str, Any],
    v2_package_gate: Mapping[str, Any],
    v2_plan: Mapping[str, Any],
    v2_plan_gate: Mapping[str, Any],
    v2_blueprint: Mapping[str, Any],
    v2_blueprint_gate: Mapping[str, Any],
) -> dict[str, Any]:
    errors: list[str] = []
    if package.get("schema_version") != P01_G2_1_PACKAGE_SCHEMA:
        errors.append("execution_package_schema_invalid")
    if package.get("package_digest") != canonical_digest(package_payload(package)):
        errors.append("execution_package_digest_invalid")
    expected = {
        "tranche_digest": tranche.get("tranche_digest"),
        "tranche_gate_digest": tranche_gate.get("gate_digest"),
        "v2_package_digest": v2_package.get("package_digest"),
        "v2_package_gate_digest": v2_package_gate.get("gate_digest"),
        "v2_plan_digest": v2_plan.get("plan_digest"),
        "v2_plan_gate_digest": v2_plan_gate.get("gate_digest"),
        "v2_blueprint_digest": v2_blueprint.get("blueprint_digest"),
        "v2_blueprint_gate_digest": v2_blueprint_gate.get("gate_digest"),
        "trigger_ddl_digest": v2_package.get("trigger_ddl_contract", {}).get("normalized_ddl_digest"),
        "fixed_store_sha256": v2_package.get("fixed_store_fingerprints", {}).get("fixed_approval_store", {}).get("sha256"),
    }
    bindings = package.get("exact_bindings")
    if not isinstance(bindings, Mapping) or any(bindings.get(key) != value for key, value in expected.items()):
        errors.append("execution_package_exact_binding_invalid")
    baseline = package.get("baseline_contract")
    expected_baseline = {
        "case_id": BASELINE_CASE_ID,
        "scenario_id": BASELINE_SCENARIO_ID,
        "input_ref": BASELINE_INPUT_REF,
        "mutation": BASELINE_MUTATION,
        "reviewer_identity": REVIEWER_IDENTITY,
        "actor_id": ACTOR_ID,
        "admission_ttl_minutes": 30,
        "receipt_ttl_minutes": 15,
        "single_use": True,
        "no_retry_replay_or_renewal": True,
    }
    if not isinstance(baseline, Mapping) or any(baseline.get(key) != value for key, value in expected_baseline.items()):
        errors.append("execution_package_baseline_contract_invalid")
    cases = package.get("cases")
    expected_cases = {
        BASELINE_CASE_ID: {"mode": "single_authorized_v2_10_production_lifecycle", "expected_terminal": "succeeded", "authority": 1, "formal_namespace": 1, "runtime": 1, "terminal_lifecycle": 1},
        "g2-wrong-package-or-approval": {"mode": "pre_authority_boundary_probe", "expected_terminal": "pre_authority_typed_deny:package_or_approval_mismatch", "authority": 0, "formal_namespace": 0, "runtime": 0, "terminal_lifecycle": 0},
        "g2-stale-input-version-drift": {"mode": "pre_authority_pack_admission_probe", "expected_terminal": "typed_stop:superseded_pack_version_or_pack_not_fresh", "authority": 0, "formal_namespace": 0, "runtime": 0, "terminal_lifecycle": 0},
        "g2-unauthorized-transport": {"mode": "pre_authority_permission_canary_probe", "expected_terminal": "typed_stop:shadow_scope_violation", "authority": 0, "formal_namespace": 0, "runtime": 0, "terminal_lifecycle": 0},
    }
    if not isinstance(cases, list) or [item.get("case_id") for item in cases if isinstance(item, Mapping)] != [
        BASELINE_CASE_ID,
        "g2-wrong-package-or-approval",
        "g2-stale-input-version-drift",
        "g2-unauthorized-transport",
    ]:
        errors.append("execution_package_case_order_invalid")
    else:
        for case in cases:
            expected_case = expected_cases[str(case["case_id"])]
            if any(case.get(field) != value for field, value in expected_case.items()):
                errors.append("execution_package_case_authority_or_terminal_invalid")
                break
    return {"status": "pass" if not errors else "fail_closed", "errors": tuple(sorted(errors)), "package_digest": package.get("package_digest")}


def gate_payload(*, package: Mapping[str, Any], verification: Mapping[str, Any]) -> dict[str, Any]:
    payload = {
        "schema_version": P01_G2_1_GATE_SCHEMA,
        "status": "pass" if verification.get("status") == "pass" else "fail_closed",
        "package_ref": package.get("package_ref"),
        "package_digest": package.get("package_digest"),
        "verification": dict(verification),
        "execution_counts": {"active_authority": 0, "admission": 0, "receipt": 0, "formal_namespace": 0, "runtime": 0, "baseline": 0, "negative_probe": 0, "network_success": 0, "tool_success": 0, "model_success": 0, "provider_success": 0, "fixed_store_write": 0},
        "next_step": "execute_exact_g2_1_once_after_total_reviewer_authority_only",
    }
    return {**payload, "gate_digest": canonical_digest(payload)}


def validate_final_baseline_candidate(
    candidate: Mapping[str, Any],
    *,
    manifest: Mapping[str, Any],
    historical_execution_package: Mapping[str, Any],
    historical_execution_gate: Mapping[str, Any],
    tranche: Mapping[str, Any],
    tranche_gate: Mapping[str, Any],
    v2_package: Mapping[str, Any],
    v2_package_gate: Mapping[str, Any],
    v2_plan: Mapping[str, Any],
    v2_plan_gate: Mapping[str, Any],
    v2_blueprint: Mapping[str, Any],
    v2_blueprint_gate: Mapping[str, Any],
    stable_contract_digests: Mapping[str, str],
    fixed_store_sha256: str,
) -> dict[str, Any]:
    """Validate a no-authority replacement candidate within the P01-G2.1 family.

    This contract deliberately cannot be passed to the historical execution
    runner.  It freezes the current staged execution inputs after a bounded
    product repair and awaits a separately issued exact-digest authority.
    """

    errors: list[str] = []
    if manifest.get("schema_version") != P01_G2_1_FINAL_BASELINE_CANDIDATE_MANIFEST_SCHEMA:
        errors.append("candidate_manifest_schema_invalid")
    if manifest.get("manifest_digest") != canonical_digest(candidate_manifest_payload(manifest)):
        errors.append("candidate_manifest_digest_invalid")
    hashes = manifest.get("input_file_sha256")
    if not isinstance(hashes, Mapping) or not hashes or any(
        not isinstance(path, str) or not isinstance(digest, str) or len(digest) != 64
        for path, digest in hashes.items()
    ):
        errors.append("candidate_manifest_input_inventory_invalid")
    elif manifest.get("input_hash_count") != len(hashes) or manifest.get("input_hashes_digest") != canonical_digest(dict(hashes)):
        errors.append("candidate_manifest_input_digest_invalid")
    if candidate.get("schema_version") != P01_G2_1_FINAL_BASELINE_CANDIDATE_SCHEMA:
        errors.append("candidate_schema_invalid")
    if candidate.get("candidate_digest") != canonical_digest(candidate_package_payload(candidate)):
        errors.append("candidate_digest_invalid")
    if candidate.get("status") != "P01_G2_FINAL_BASELINE_CANDIDATE_FREEZE_PENDING_EXACT_DIGEST_APPROVAL":
        errors.append("candidate_status_invalid")
    if candidate.get("future_scope") != "single_ai_semis_operational_baseline_only":
        errors.append("candidate_scope_invalid")
    if candidate.get("manifest_digest") != manifest.get("manifest_digest"):
        errors.append("candidate_manifest_binding_invalid")
    expected_case_pack = {
        "pack_version_id": AI_SEMIS_CASE_INSTANCE_PACK_REF,
        "payload_digest": AI_SEMIS_CASE_INSTANCE_PACK_PAYLOAD_DIGEST,
        "case_id": BASELINE_INPUT_REF,
        "override_mode": "no_override",
    }
    if candidate.get("case_instance_pack") != expected_case_pack:
        errors.append("candidate_case_instance_pack_invalid")
    expected_baseline = {
        "case_id": BASELINE_CASE_ID,
        "scenario_id": BASELINE_SCENARIO_ID,
        "input_ref": BASELINE_INPUT_REF,
        "mutation": BASELINE_MUTATION,
        "single_use": True,
        "no_retry_replay_or_renewal": True,
    }
    if candidate.get("baseline_contract") != expected_baseline:
        errors.append("candidate_baseline_contract_invalid")
    expected_bindings = {
        "historical_execution_package_digest": historical_execution_package.get("package_digest"),
        "historical_execution_gate_digest": historical_execution_gate.get("gate_digest"),
        "tranche_digest": tranche.get("tranche_digest"),
        "tranche_gate_digest": tranche_gate.get("gate_digest"),
        "v2_package_digest": v2_package.get("package_digest"),
        "v2_package_gate_digest": v2_package_gate.get("gate_digest"),
        "v2_plan_digest": v2_plan.get("plan_digest"),
        "v2_plan_gate_digest": v2_plan_gate.get("gate_digest"),
        "v2_blueprint_digest": v2_blueprint.get("blueprint_digest"),
        "v2_blueprint_gate_digest": v2_blueprint_gate.get("gate_digest"),
        "trigger_ddl_digest": v2_package.get("trigger_ddl_contract", {}).get("normalized_ddl_digest"),
        "fixed_store_sha256": fixed_store_sha256,
        "case_instance_pack_ref": AI_SEMIS_CASE_INSTANCE_PACK_REF,
        "case_instance_pack_payload_digest": AI_SEMIS_CASE_INSTANCE_PACK_PAYLOAD_DIGEST,
        "stable_contract_digests": dict(stable_contract_digests),
    }
    if candidate.get("exact_bindings") != expected_bindings:
        errors.append("candidate_exact_binding_invalid")
    expected_counts = {
        "human_approval": 0,
        "admission": 0,
        "receipt": 0,
        "baseline": 0,
        "negative_case": 0,
        "formal_namespace": 0,
        "runtime": 0,
        "network_success": 0,
        "tool_success": 0,
        "model_success": 0,
        "provider_success": 0,
        "fixed_business_store_write": 0,
    }
    if candidate.get("execution_counts") != expected_counts:
        errors.append("candidate_zero_execution_counts_invalid")
    boundary = candidate.get("authority_boundary")
    if not isinstance(boundary, Mapping) or boundary != {
        "exact_digest_approval_required": True,
        "historical_consumed_receipts_non_replayable": True,
        "no_authority_artifact_created": True,
        "no_network_tool_model_provider_execution": True,
        "no_fixed_or_business_store_write": True,
        "legacy_authority": "retained",
        "production_readiness": "not_admitted",
    }:
        errors.append("candidate_authority_boundary_invalid")
    return {
        "status": "pass" if not errors else "fail_closed",
        "errors": tuple(sorted(errors)),
        "candidate_digest": candidate.get("candidate_digest"),
        "manifest_digest": manifest.get("manifest_digest"),
    }


def create_reviewer_authority(
    *,
    authority_id: str,
    issued_at: datetime,
    expires_at: datetime,
    exact_bindings: Mapping[str, str],
    v2_reviewer_receipt: Mapping[str, Any],
    v2_approval: Mapping[str, Any],
) -> dict[str, Any]:
    """Create an outer audit envelope; v2.10 remains the only lifecycle authority."""

    payload = {
        "schema_version": P01_G2_1_AUTHORITY_SCHEMA,
        "authority_id": authority_id,
        "authority_version": 1,
        "reviewer_identity": REVIEWER_IDENTITY,
        "actor_id": ACTOR_ID,
        "decision": "approved_single_operational_baseline_only",
        "decision_source": "p01_g2_1_independent_total_reviewer_disposition",
        "issued_at": utc_json(issued_at),
        "expires_at": utc_json(expires_at),
        "exact_bindings": dict(exact_bindings),
        "baseline": {"case_id": BASELINE_CASE_ID, "scenario_id": BASELINE_SCENARIO_ID, "input_ref": BASELINE_INPUT_REF, "mutation": BASELINE_MUTATION},
        "single_use": True,
        "no_retry_replay_or_renewal": True,
        "v2_10_reviewer_decision_receipt": dict(v2_reviewer_receipt),
        "v2_10_human_approval": dict(v2_approval),
    }
    return {**payload, "authority_digest": canonical_digest(payload)}


def validate_reviewer_authority(authority: Mapping[str, Any], *, package: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if authority.get("schema_version") != P01_G2_1_AUTHORITY_SCHEMA:
        errors.append("authority_schema_invalid")
    if authority.get("authority_digest") != canonical_digest(authority_payload(authority)):
        errors.append("authority_digest_invalid")
    if authority.get("reviewer_identity") != REVIEWER_IDENTITY or authority.get("actor_id") != ACTOR_ID:
        errors.append("authority_reviewer_invalid")
    if authority.get("decision") != "approved_single_operational_baseline_only" or authority.get("decision_source") != "p01_g2_1_independent_total_reviewer_disposition":
        errors.append("authority_decision_invalid")
    if authority.get("single_use") is not True or authority.get("no_retry_replay_or_renewal") is not True:
        errors.append("authority_single_use_invalid")
    baseline = authority.get("baseline")
    if not isinstance(baseline, Mapping) or baseline != {"case_id": BASELINE_CASE_ID, "scenario_id": BASELINE_SCENARIO_ID, "input_ref": BASELINE_INPUT_REF, "mutation": BASELINE_MUTATION}:
        errors.append("authority_baseline_binding_invalid")
    if authority.get("exact_bindings") != package.get("exact_bindings"):
        errors.append("authority_package_binding_invalid")
    try:
        issued = datetime.fromisoformat(str(authority.get("issued_at")).replace("Z", "+00:00"))
        expires = datetime.fromisoformat(str(authority.get("expires_at")).replace("Z", "+00:00"))
        if issued.tzinfo is None or expires.tzinfo is None or expires <= datetime.now(timezone.utc) or issued >= expires:
            errors.append("authority_expiry_invalid")
    except (TypeError, ValueError):
        errors.append("authority_expiry_invalid")
    return {"status": "pass" if not errors else "fail_closed", "errors": tuple(sorted(errors)), "authority_digest": authority.get("authority_digest")}


def pre_authority_terminal(*, case_id: str) -> str:
    terminals = {
        "g2-wrong-package-or-approval": "pre_authority_typed_deny:package_or_approval_mismatch",
        "g2-stale-input-version-drift": "typed_stop:superseded_pack_version_or_pack_not_fresh",
        "g2-unauthorized-transport": "typed_stop:shadow_scope_violation",
    }
    try:
        return terminals[case_id]
    except KeyError as exc:
        raise ValueError("p01_g2_1_pre_authority_case_invalid") from exc


def build_case_result(*, case_id: str, status: str, terminal: str, counts: Mapping[str, int], details: Mapping[str, Any]) -> dict[str, Any]:
    payload = {"schema_version": "finsight_point01_p01_g2_1_case_result_v1_0", "case_id": case_id, "status": status, "terminal": terminal, "counts": dict(counts), "details": dict(details)}
    return {**payload, "result_digest": canonical_digest(payload)}
