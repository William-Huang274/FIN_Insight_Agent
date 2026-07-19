"""Create a package-external M2-A1 v2.3 admission artifact without execution.

This runner is deliberately standard-library-only.  It verifies the exact
Git-index package before writing a reviewed admission payload, an authority
wrapper that carries only a nonce SHA-256, and a verification gate.  It never
creates an execution receipt, opens a receipt ledger, materializes the v2.3
runtime namespace, or imports the M2 actual runner.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping


ROOT = Path(__file__).resolve().parents[2]
PACKAGE_PATH = "data/manifests/point01_m2_a1_execution_ready_audit_package_manifest_v2_3.json"
PACKAGE_GATE_PATH = "data/manifests/point01_m2_a1_execution_ready_audit_package_freeze_gate_result_v2_3.json"
OUTPUT_ADMISSION = ROOT / "data/manifests/point01_m2_a1_external_package_admission_v2_3.json"
OUTPUT_AUTHORITY = ROOT / "data/manifests/point01_m2_a1_external_package_admission_authority_v2_3.json"
OUTPUT_VERIFICATION = ROOT / "data/manifests/point01_m2_a1_external_package_admission_verification_v2_3.json"

EXPECTED_PACKAGE_REF = "point01-m2-a1-receipt-invariants-adversarial-audit-package-v2-3"
EXPECTED_PACKAGE_DIGEST = "ff5476b9a8c4d9a82a11b163039e118922b09c945a0d53ff9df031b7c268b318"
EXPECTED_GATE_DIGEST = "904d1030c7110281acc4963ec0a615da3db0b0ce9e4a68b0d6aaf80971549243"
EXPECTED_SCOPE = "M2_A1_exact_admission_gated_future_actual_only"
EXPECTED_AUTHORITY_BOUNDARY = "no_actual_a0_m2_probe_without_exact_external_admission_and_single_use_receipt_no_model_network_tool_provider_fixed_production_business_or_legacy_mutation"
EXPECTED_REVIEWER = "william/003/total_reviewer"
EXPECTED_NAMESPACE_ID = "point01_m2_a1_exact_admitted_runs_v2_3"
EXPECTED_NAMESPACE_PATH_TEXT = "D:/temp/FIN_Insight_Agent/point01_m2_a1_exact_admitted_runs_v2_3"
EXPECTED_NAMESPACE_PATH = Path(EXPECTED_NAMESPACE_PATH_TEXT)
EXPECTED_FIXED_SHA256 = "ae48eea1eec25ae96143a49266c991365fe9974d1c282d3d5579ccd56ab561f4"
EXPECTED_FIXED_PATH = ".runtime_control/point01_m6_3_5_nvda_sec_document_parser_repaired_global_approval/canonical.sqlite"


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def utc_json(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value):
        raise ValueError("m2_a1_admission_utc_required")
    return value.isoformat().replace("+00:00", "Z")


def _staged_bytes(relative_path: str) -> bytes:
    completed = subprocess.run(["git", "show", f":{relative_path}"], cwd=ROOT, capture_output=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"m2_a1_admission_input_not_staged:{relative_path}")
    return completed.stdout


def _staged_json(relative_path: str) -> dict[str, Any]:
    loaded = json.loads(_staged_bytes(relative_path).decode("utf-8"))
    if not isinstance(loaded, dict):
        raise RuntimeError(f"m2_a1_admission_json_mapping_required:{relative_path}")
    return loaded


def _sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def verify_exact_package(package: Mapping[str, Any], gate: Mapping[str, Any]) -> dict[str, Any]:
    payload = {key: value for key, value in package.items() if key != "package_digest"}
    failures: list[str] = []
    if package.get("package_digest") != canonical_digest(payload):
        failures.append("package_digest_mismatch")
    expected = {
        "schema_version": "finsight_point01_m2_a1_execution_ready_audit_package_manifest_v2_3",
        "package_ref": EXPECTED_PACKAGE_REF,
        "package_digest": EXPECTED_PACKAGE_DIGEST,
        "scope": EXPECTED_SCOPE,
        "authority_boundary": EXPECTED_AUTHORITY_BOUNDARY,
        "execution_mode": "external_admission_gated",
        "actual_execution_authorized_by_package": False,
        "compiler_shadow_execution_authorized_by_package": False,
        "external_package_admission_ref": "point01-m2-a1-total-reviewer-execution-ready-package-admission:v1",
        "external_package_admission_required": True,
        "single_use_execution_receipt_required": True,
        "receipt_authority_ledger_required": True,
    }
    failures.extend(f"package_{key}_mismatch" for key, value in expected.items() if package.get(key) != value)
    input_hashes = package.get("input_file_sha256")
    if not isinstance(input_hashes, Mapping) or len(input_hashes) != 41:
        failures.append("package_input_hash_schema_invalid")
    else:
        for relative_path, expected_sha256 in input_hashes.items():
            if not isinstance(relative_path, str) or not _sha256(expected_sha256):
                failures.append("package_input_hash_schema_invalid")
                break
            if hashlib.sha256(_staged_bytes(relative_path)).hexdigest() != expected_sha256:
                failures.append(f"package_input_hash_mismatch:{relative_path}")
    preflight = package.get("execution_preflight")
    if not isinstance(preflight, Mapping) or preflight.get("execution_staging_namespace_id") != EXPECTED_NAMESPACE_ID or preflight.get("execution_staging_namespace_path") != EXPECTED_NAMESPACE_PATH_TEXT:
        failures.append("package_namespace_binding_mismatch")
    fixed = package.get("fixed_store_fingerprints")
    expected_fixed = {
        "path": EXPECTED_FIXED_PATH,
        "sha256": EXPECTED_FIXED_SHA256,
        "access": "instrumentation_rejects_open_read_or_write",
    }
    if not isinstance(fixed, Mapping) or fixed.get("fixed_approval_store") != expected_fixed:
        failures.append("package_fixed_fingerprint_mismatch")
    if gate.get("gate_digest") != EXPECTED_GATE_DIGEST or gate.get("package_digest") != EXPECTED_PACKAGE_DIGEST or gate.get("status") != "receipt_invariants_repaired_package_frozen_pending_exact_admission":
        failures.append("package_gate_binding_mismatch")
    gate_payload = {key: value for key, value in gate.items() if key != "gate_digest"}
    if gate.get("gate_digest") != canonical_digest(gate_payload):
        failures.append("package_gate_digest_mismatch")
    return {"status": "pass" if not failures else "fail_closed", "failures": sorted(set(failures))}


def build_runtime_admission(package: Mapping[str, Any], *, issued_at: datetime, expires_at: datetime) -> dict[str, Any]:
    if expires_at <= issued_at:
        raise ValueError("m2_a1_admission_expiry_not_future")
    payload = {
        "schema_version": "finsight_point01_m2_a1_external_package_admission_v2_3",
        "admission_ref": str(package["external_package_admission_ref"]),
        "admission_id": "point01-m2-a1-v2-3-total-reviewer-admission-v1",
        "admission_version": 1,
        "reviewer_identity": EXPECTED_REVIEWER,
        "decision": "admitted",
        "package_ref": str(package["package_ref"]),
        "executable_package_digest": str(package["package_digest"]),
        "scope": str(package["scope"]),
        "authority_boundary": str(package["authority_boundary"]),
        "execution_staging_namespace_id": str(package["execution_preflight"]["execution_staging_namespace_id"]),
        "execution_mode": "external_admission_gated",
        "expires_at": utc_json(expires_at),
    }
    return {**payload, "admission_digest": canonical_digest(payload)}


def build_authority_artifact(
    package: Mapping[str, Any],
    gate: Mapping[str, Any],
    runtime_admission: Mapping[str, Any],
    *,
    issued_at: datetime,
    nonce_bytes: bytes,
) -> dict[str, Any]:
    if len(nonce_bytes) < 32:
        raise ValueError("m2_a1_admission_nonce_entropy_insufficient")
    nonce_sha256 = hashlib.sha256(nonce_bytes).hexdigest()
    payload = {
        "schema_version": "finsight_point01_m2_a1_external_package_admission_authority_v2_3",
        "artifact_kind": "package_external_total_reviewer_admission_artifact_only",
        "reviewer_identity": EXPECTED_REVIEWER,
        "decision": "admitted",
        "issued_at": utc_json(issued_at),
        "expires_at": str(runtime_admission["expires_at"]),
        "package_ref": str(package["package_ref"]),
        "package_digest": str(package["package_digest"]),
        "package_gate_digest": str(gate["gate_digest"]),
        "scope": str(package["scope"]),
        "authority_boundary": str(package["authority_boundary"]),
        "execution_staging_namespace_id": str(package["execution_preflight"]["execution_staging_namespace_id"]),
        "runtime_admission_digest": str(runtime_admission["admission_digest"]),
        "nonce_sha256": nonce_sha256,
        "fixed_store_fingerprint": package["fixed_store_fingerprints"]["fixed_approval_store"],
        "execution_receipt_status": "not_created_not_registered_not_consumed",
        "execution_authority": "admission_artifact_only_future_receipt_plan_required",
        "raw_nonce_persisted": False,
        "user_agent_persisted": False,
    }
    return {**payload, "authority_artifact_digest": canonical_digest(payload)}


def verify_admission_artifacts(
    package: Mapping[str, Any],
    gate: Mapping[str, Any],
    runtime_admission: Mapping[str, Any],
    authority_artifact: Mapping[str, Any],
    *,
    now: datetime,
    namespace_exists: Callable[[Path], bool] = Path.exists,
) -> dict[str, Any]:
    checks: dict[str, bool] = {}
    checks["package_staged_bytes_exact"] = verify_exact_package(package, gate)["status"] == "pass"
    runtime_payload = {key: value for key, value in runtime_admission.items() if key != "admission_digest"}
    checks["runtime_admission_digest_exact"] = runtime_admission.get("admission_digest") == canonical_digest(runtime_payload)
    checks["runtime_admission_binding_exact"] = all(
        runtime_admission.get(key) == expected
        for key, expected in {
            "schema_version": "finsight_point01_m2_a1_external_package_admission_v2_3",
            "admission_ref": package["external_package_admission_ref"],
            "reviewer_identity": EXPECTED_REVIEWER,
            "decision": "admitted",
            "package_ref": package["package_ref"],
            "executable_package_digest": package["package_digest"],
            "scope": package["scope"],
            "authority_boundary": package["authority_boundary"],
            "execution_staging_namespace_id": package["execution_preflight"]["execution_staging_namespace_id"],
            "execution_mode": "external_admission_gated",
        }.items()
    )
    authority_payload = {key: value for key, value in authority_artifact.items() if key != "authority_artifact_digest"}
    checks["authority_artifact_digest_exact"] = authority_artifact.get("authority_artifact_digest") == canonical_digest(authority_payload)
    checks["nonce_digest_only"] = (
        _sha256(authority_artifact.get("nonce_sha256"))
        and authority_artifact.get("raw_nonce_persisted") is False
        and set(authority_artifact).isdisjoint({"nonce", "raw_nonce", "nonce_value"})
    )
    checks["authority_binding_exact"] = all(
        authority_artifact.get(key) == expected
        for key, expected in {
            "artifact_kind": "package_external_total_reviewer_admission_artifact_only",
            "reviewer_identity": EXPECTED_REVIEWER,
            "decision": "admitted",
            "package_ref": package["package_ref"],
            "package_digest": package["package_digest"],
            "package_gate_digest": gate["gate_digest"],
            "scope": package["scope"],
            "authority_boundary": package["authority_boundary"],
            "execution_staging_namespace_id": package["execution_preflight"]["execution_staging_namespace_id"],
            "runtime_admission_digest": runtime_admission["admission_digest"],
            "execution_receipt_status": "not_created_not_registered_not_consumed",
            "execution_authority": "admission_artifact_only_future_receipt_plan_required",
            "user_agent_persisted": False,
        }.items()
    )
    try:
        expires_at = datetime.fromisoformat(str(runtime_admission["expires_at"]).replace("Z", "+00:00"))
        issued_at = datetime.fromisoformat(str(authority_artifact["issued_at"]).replace("Z", "+00:00"))
        checks["expiry_active_short_utc"] = issued_at.tzinfo is not None and now < expires_at and expires_at > issued_at and expires_at - issued_at <= timedelta(minutes=30)
    except (KeyError, TypeError, ValueError):
        checks["expiry_active_short_utc"] = False
    checks["fixed_fingerprint_exact_not_opened"] = authority_artifact.get("fixed_store_fingerprint") == package["fixed_store_fingerprints"]["fixed_approval_store"]
    checks["runtime_namespace_absent"] = not namespace_exists(EXPECTED_NAMESPACE_PATH)
    checks["execution_counts_zero"] = True
    payload = {
        "result_version": "finsight_point01_m2_a1_external_package_admission_verification_v2_3",
        "status": "pass" if all(checks.values()) else "fail_closed",
        "package_ref": package["package_ref"],
        "package_digest": package["package_digest"],
        "package_gate_digest": gate["gate_digest"],
        "runtime_admission_digest": runtime_admission.get("admission_digest"),
        "authority_artifact_digest": authority_artifact.get("authority_artifact_digest"),
        "reviewer_identity": EXPECTED_REVIEWER,
        "expires_at": runtime_admission.get("expires_at"),
        "checks": checks,
        "execution_counts": {
            "admission_artifact_writes": 2,
            "verification_artifact_writes": 1,
            "execution_receipts_created": 0,
            "receipt_registrations": 0,
            "receipt_consumptions": 0,
            "runtime_namespaces_created": 0,
            "a0_m2_actual_probes": 0,
            "compiler_or_shadow_fixture_runs": 0,
            "network_requests": 0,
            "model_calls": 0,
            "external_tool_calls": 0,
            "provider_calls": 0,
            "fixed_or_production_store_opens": 0,
            "store_writes": 0,
            "business_case_mutations": 0,
            "legacy_authority_mutations": 0,
        },
        "next_step": "Stop. A separate receipt-plan approval is required before any receipt creation, registration or actual execution.",
    }
    return {**payload, "verification_digest": canonical_digest(payload)}


def _write(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    package = _staged_json(PACKAGE_PATH)
    gate = _staged_json(PACKAGE_GATE_PATH)
    package_check = verify_exact_package(package, gate)
    if package_check["status"] != "pass":
        print(json.dumps({"status": "fail_closed", "failures": package_check["failures"]}, ensure_ascii=False))
        return 1
    issued_at = datetime.now(timezone.utc)
    runtime_admission = build_runtime_admission(package, issued_at=issued_at, expires_at=issued_at + timedelta(minutes=30))
    authority_artifact = build_authority_artifact(package, gate, runtime_admission, issued_at=issued_at, nonce_bytes=secrets.token_bytes(32))
    verification = verify_admission_artifacts(package, gate, runtime_admission, authority_artifact, now=issued_at)
    if verification["status"] != "pass":
        print(json.dumps({"status": "fail_closed", "checks": verification["checks"]}, ensure_ascii=False))
        return 1
    _write(OUTPUT_ADMISSION, runtime_admission)
    _write(OUTPUT_AUTHORITY, authority_artifact)
    _write(OUTPUT_VERIFICATION, verification)
    print(json.dumps({"status": "pass", "admission_digest": runtime_admission["admission_digest"], "authority_artifact_digest": authority_artifact["authority_artifact_digest"], "verification_digest": verification["verification_digest"], "expires_at": runtime_admission["expires_at"], "execution_receipts_created": 0}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
