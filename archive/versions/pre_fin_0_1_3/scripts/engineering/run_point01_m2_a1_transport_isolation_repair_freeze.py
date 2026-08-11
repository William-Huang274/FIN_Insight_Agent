"""Freeze RC-P38-024 Phase-A transport-isolation repair evidence.

The freeze is standard-library-only and validates Git-index bytes.  It does
not create an admission or receipt, materialize an audit namespace, run a
baseline, import a provider, or open any fixed/canonical/business store.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CLASSIFICATION = "data/manifests/point01_m2_a1_rc_p38_024_root_cause_classification_v1_0.json"
POLICY = "configs/engineering_handoff/point01_m2_a1_transport_isolation_repair_policy_v1_0.json"
MATRIX = "configs/engineering_handoff/point01_m2_a1_execution_ready_scenario_matrix_v2_1.json"
OUTPUT_PACKAGE = ROOT / "data/manifests/point01_m2_a1_transport_isolation_repair_package_v1_0.json"
OUTPUT_GATE = ROOT / "data/manifests/point01_m2_a1_transport_isolation_repair_gate_v1_0.json"
SCHEMA_VERSION = "finsight_point01_m2_a1_transport_isolation_repair_package_v1_0"
PACKAGE_REF = "point01-m2-a1-rc-p38-024-transport-isolation-repair-package-v1"
SCOPE = "RC_P38_024_phase_a_root_cause_repair_and_package_freeze_only"
AUTHORITY_BOUNDARY = "no_admission_no_receipt_no_baseline_rerun_no_network_tool_model_provider_or_fixed_store_write"
FIXED_APPROVAL_SHA256 = "ae48eea1eec25ae96143a49266c991365fe9974d1c282d3d5579ccd56ab561f4"
FIXED_APPROVAL_PATH = ".runtime_control/point01_m6_3_5_nvda_sec_document_parser_repaired_global_approval/canonical.sqlite"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

PACKAGE_INPUTS = (
    CLASSIFICATION,
    POLICY,
    MATRIX,
    "src/sec_agent/canonical_runtime/__init__.py",
    "src/sec_agent/canonical_runtime/m2_a1_audit_canary.py",
    "src/sec_agent/canonical_runtime/m2_a1_audit_harness.py",
    "src/sec_agent/canonical_runtime/m2_a1_audit_oracle.py",
    "src/sec_agent/canonical_runtime/m2_a1_execution_receipt.py",
    "src/sec_agent/canonical_runtime/planning_service.py",
    "src/sec_agent/canonical_runtime/legacy_objective_adapter.py",
    "scripts/engineering/run_point01_m2_a1_actual_audit.py",
    "scripts/engineering/run_point01_m2_a1_actual_audit_clean_child.py",
    "scripts/engineering/run_point01_m2_a1_transport_isolation_bisect.py",
    "scripts/engineering/run_point01_m2_a1_transport_isolation_repair_freeze.py",
    "tests/contract/test_point01_m2_a1_execution_ready_boundaries.py",
    "tests/contract/test_point01_m2_a1_assembly_harness.py",
    "tests/contract/test_point01_m2_a1_execution_ready_package_static.py",
    "tests/contract/test_point01_m2_a1_receipt_lifecycle.py",
    "tests/contract/test_point01_m2_a1_transport_isolation_repair.py",
)
PAYLOAD_FIELDS = (
    "schema_version", "package_ref", "scope", "authority_boundary", "input_bytes_source", "input_file_sha256",
    "root_cause_id", "classification_digest", "classification_schema_version", "prior_fail_closed_actual_digest",
    "historical_before_repair", "before_after_behavior", "fixed_store_fingerprint", "operational_status", "authority_status", "zero_side_effect_counters",
)
PACKAGE_FIELDS = frozenset((*PAYLOAD_FIELDS, "package_digest"))


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _staged_bytes(relative_path: str) -> bytes:
    completed = subprocess.run(["git", "show", f":{relative_path}"], cwd=ROOT, capture_output=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"rc_p38_024_repair_input_not_staged:{relative_path}")
    return completed.stdout


def _staged_json(relative_path: str) -> dict[str, Any]:
    payload = json.loads(_staged_bytes(relative_path).decode("utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"rc_p38_024_repair_json_mapping_required:{relative_path}")
    return payload


def _sha(value: object) -> bool:
    return isinstance(value, str) and bool(SHA256_RE.fullmatch(value))


def _payload(package: dict[str, Any]) -> dict[str, Any]:
    return {field: package[field] for field in PAYLOAD_FIELDS}


def _fixed_fingerprint() -> dict[str, str]:
    return {"path": FIXED_APPROVAL_PATH, "sha256": FIXED_APPROVAL_SHA256, "access": "fingerprint_only_no_open_or_mutation"}


def _status() -> dict[str, str]:
    return {
        "m2_milestone_scope_status": "complete_deterministic_shadow",
        "m2_operational_qualification_status": "fail_closed_pending_transport_isolation_repair_review",
        "m3_operational_status": "scoped_closeout_retained_adversarial_operational_requalification_pending",
        "m4_operational_status": "scoped_closeout_retained_adversarial_operational_requalification_pending",
        "m5_operational_status": "scoped_closeout_retained_adversarial_operational_requalification_pending",
    }


def _zero_counts() -> dict[str, int]:
    return {
        "new_admission_count": 0,
        "new_receipt_count": 0,
        "receipt_consumption_count": 0,
        "baseline_rerun_count": 0,
        "network_request_success_count": 0,
        "external_tool_call_count": 0,
        "model_or_provider_call_count": 0,
        "fixed_canonical_or_business_store_open_count": 0,
        "fixed_canonical_or_business_store_write_count": 0,
    }


def build_package() -> dict[str, Any]:
    classification = _staged_json(CLASSIFICATION)
    policy = _staged_json(POLICY)
    before_after = classification.get("before_after_behavior")
    historical_before = classification.get("historical_before_repair")
    if not isinstance(before_after, dict):
        raise RuntimeError("rc_p38_024_before_after_behavior_missing")
    if not isinstance(historical_before, dict):
        raise RuntimeError("rc_p38_024_historical_before_repair_missing")
    payload = {
        "schema_version": SCHEMA_VERSION,
        "package_ref": PACKAGE_REF,
        "scope": SCOPE,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "input_bytes_source": "git_index",
        "input_file_sha256": {path: hashlib.sha256(_staged_bytes(path)).hexdigest() for path in PACKAGE_INPUTS},
        "root_cause_id": "RC-P38-024",
        "classification_digest": str(classification.get("classification_digest") or ""),
        "classification_schema_version": str(classification.get("schema_version") or ""),
        "prior_fail_closed_actual_digest": str(classification.get("prior_fail_closed_actual_digest") or ""),
        "historical_before_repair": historical_before,
        "before_after_behavior": before_after,
        "fixed_store_fingerprint": _fixed_fingerprint(),
        "operational_status": _status(),
        "authority_status": {
            "phase": "A",
            "admission_or_receipt_authorized": False,
            "baseline_rerun_authorized": False,
            "old_admission_or_receipt_replay": "permanently_forbidden",
            "next_step": "independent_review_then_phase_b_fresh_baseline_authority_decision_only",
        },
        "zero_side_effect_counters": _zero_counts(),
    }
    if policy.get("authority_boundary") != AUTHORITY_BOUNDARY or policy.get("actual_authorized") is not False:
        raise RuntimeError("rc_p38_024_policy_boundary_invalid")
    return {**payload, "package_digest": canonical_digest(payload)}


def _schema_errors(package: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = sorted(PACKAGE_FIELDS - set(package))
    extra = sorted(set(package) - PACKAGE_FIELDS)
    if missing:
        errors.append(f"missing_fields:{','.join(missing)}")
    if extra:
        errors.append(f"unexpected_fields:{','.join(extra)}")
    if missing:
        return errors
    exact = {
        "schema_version": SCHEMA_VERSION,
        "package_ref": PACKAGE_REF,
        "scope": SCOPE,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "input_bytes_source": "git_index",
        "root_cause_id": "RC-P38-024",
        "classification_schema_version": "finsight_point01_rc_p38_024_root_cause_classification_v1_0",
    }
    errors.extend(f"{field}_invalid" for field, value in exact.items() if package.get(field) != value)
    for field in ("classification_digest", "prior_fail_closed_actual_digest", "package_digest"):
        if not _sha(package.get(field)):
            errors.append(f"{field}_must_be_sha256")
    hashes = package.get("input_file_sha256")
    if not isinstance(hashes, dict) or set(hashes) != set(PACKAGE_INPUTS) or any(not _sha(value) for value in hashes.values()):
        errors.append("input_file_sha256_invalid")
    if package.get("fixed_store_fingerprint") != _fixed_fingerprint():
        errors.append("fixed_store_fingerprint_invalid")
    historical = package.get("historical_before_repair")
    if not isinstance(historical, dict) or historical.get("canonical_planning_transport_module_loaded_count") != 97 or historical.get("transport_constructor_attempt_count") != 0 or historical.get("network_request_success_count") != 0:
        errors.append("historical_before_repair_invalid")
    if package.get("operational_status") != _status():
        errors.append("operational_status_invalid")
    authority = package.get("authority_status")
    if not isinstance(authority, dict) or authority.get("admission_or_receipt_authorized") is not False or authority.get("baseline_rerun_authorized") is not False or authority.get("old_admission_or_receipt_replay") != "permanently_forbidden":
        errors.append("authority_status_invalid")
    if package.get("zero_side_effect_counters") != _zero_counts():
        errors.append("zero_side_effect_counters_invalid")
    return errors


def verify_package(package: dict[str, Any]) -> dict[str, Any]:
    try:
        calculated = canonical_digest(_payload(package))
    except (KeyError, TypeError):
        return {"status": "package_schema_validation_failed", "mismatches": ["package_payload_missing"]}
    if package.get("package_digest") != calculated:
        return {"status": "package_digest_mismatch", "calculated_package_digest": calculated, "mismatches": []}
    errors = _schema_errors(package)
    if errors:
        return {"status": "package_schema_validation_failed", "calculated_package_digest": calculated, "mismatches": errors}
    mismatches = [path for path, digest in sorted(package["input_file_sha256"].items()) if hashlib.sha256(_staged_bytes(path)).hexdigest() != digest]
    classification = _staged_json(CLASSIFICATION)
    if classification.get("classification_digest") != package["classification_digest"]:
        mismatches.append("classification_digest")
    policy = _staged_json(POLICY)
    if policy.get("authority_boundary") != AUTHORITY_BOUNDARY or policy.get("actual_authorized") is not False:
        mismatches.append("policy_authority_boundary")
    return {
        "status": "pass" if not mismatches else "package_input_digest_mismatch",
        "calculated_package_digest": calculated,
        "mismatches": mismatches,
        "package_current_verify": "pass" if not mismatches else "fail",
    }


def build_gate(package: dict[str, Any]) -> dict[str, Any]:
    verify = verify_package(package)
    classification = _staged_json(CLASSIFICATION)
    behavior = classification.get("before_after_behavior") if isinstance(classification, dict) else None
    historical = classification.get("historical_before_repair") if isinstance(classification, dict) else None
    negative = behavior.get("negative_control_counts") if isinstance(behavior, dict) else None
    checks = {
        "package_current_verify": verify["status"] == "pass",
        "historical_root_cause_recorded": isinstance(historical, dict) and historical.get("canonical_planning_transport_module_loaded_count") == 97 and historical.get("transport_constructor_attempt_count") == 0 and historical.get("network_request_success_count") == 0,
        "fresh_process_clean_baseline": isinstance(behavior, dict) and behavior.get("clean_baseline_transport_delta") == {},
        "pure_local_planning_transport_free": isinstance(behavior, dict) and behavior.get("planning_transport_delta_after_repair") == {},
        "concrete_negative_controls_blocked": isinstance(behavior, dict) and set(behavior.get("negative_controls_blocked") or ()) == {"requests_session_constructor", "socket_connect", "urlopen_request"},
        "constructor_connect_request_distinguished": isinstance(negative, dict) and int(negative.get("transport_constructor_attempt_count", 0)) == 1 and int(negative.get("socket_connect_attempt_count", 0)) == 1 and int(negative.get("network_request_attempt_count", 0)) == 2 and int(negative.get("network_request_success_count", -1)) == 0,
        "no_phase_a_authority_expansion": package["authority_status"]["admission_or_receipt_authorized"] is False and package["authority_status"]["baseline_rerun_authorized"] is False,
        "zero_side_effects": package["zero_side_effect_counters"] == _zero_counts(),
        "fixed_fingerprint_pinned": package["fixed_store_fingerprint"] == _fixed_fingerprint(),
    }
    payload = {
        "result_version": "finsight_point01_m2_a1_transport_isolation_repair_gate_v1_0",
        "scope": SCOPE,
        "status": "repair_package_frozen_pending_independent_review_phase_b_blocked" if all(checks.values()) else "fail_closed",
        "package_ref": package["package_ref"],
        "package_digest": package["package_digest"],
        "package_verify": verify,
        "checks": checks,
        "fixed_store_fingerprint": _fixed_fingerprint(),
        "execution_counts": _zero_counts(),
        "next_step": "independent_phase_a_review_required; fresh_baseline_authority_is_not_issued_by_this_gate",
    }
    return {**payload, "gate_digest": canonical_digest(payload)}


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    package = build_package()
    gate = build_gate(package)
    _write(OUTPUT_PACKAGE, package)
    _write(OUTPUT_GATE, gate)
    print(json.dumps({"status": gate["status"], "package_digest": package["package_digest"], "gate_digest": gate["gate_digest"], "execution_counts": gate["execution_counts"]}, ensure_ascii=False))
    return 0 if gate["status"] == "repair_package_frozen_pending_independent_review_phase_b_blocked" else 1


if __name__ == "__main__":
    raise SystemExit(main())
