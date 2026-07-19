"""Freeze the executable M2-A1 harness package without executing any probe.

Standard library only: this script reads Git-index bytes and validates static
contracts.  It never imports the M2 compiler/shadow runtime, opens a store,
or creates an admission/receipt.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CORPUS = "configs/engineering_handoff/point01_m2_a1_adversarial_input_corpus_v1_1.json"
ORACLE = "configs/engineering_handoff/point01_m2_a1_independent_expected_cell_oracle_v1_1.json"
MATRIX = "configs/engineering_handoff/point01_m2_a1_owner_authority_typed_stop_matrix_v1_1.json"
HARNESS_POLICY = "configs/engineering_handoff/point01_m2_a1_executable_audit_harness_policy_v1_0.json"
A0_DESIGN = "configs/engineering_handoff/point01_m1_m5_adversarial_retro_audit_design_freeze_v1_0.json"
DESIGN_PACKAGE = "data/manifests/point01_m2_a1_adversarial_audit_package_manifest_v1_1.json"
OUTPUT_PACKAGE = ROOT / "data/manifests/point01_m2_a1_executable_audit_package_manifest_v1_0.json"
OUTPUT_GATE = ROOT / "data/manifests/point01_m2_a1_executable_audit_package_freeze_gate_result_v1_0.json"

SCHEMA_VERSION = "finsight_point01_m2_a1_executable_audit_package_manifest_v1_0"
PACKAGE_REF = "point01-m2-a1-executable-audit-harness-package-v1"
SCOPE = "M2_A1_executable_harness_package_freeze_only"
AUTHORITY_BOUNDARY = "no_actual_a0_m2_probe_no_compiler_shadow_fixture_no_model_network_tool_provider_fixed_production_business_or_legacy_store_open_or_write"
EXPECTED_A0_DESIGN_DIGEST = "75a76e24a3a730b82942b9861b9d203a5ec0e735a936dbc229d1c68681ff250d"
EXPECTED_DESIGN_PACKAGE_DIGEST = "34a6877a084bc85aa28d160082661db7d1fc9ca04f44d576afe6bb5d5acc5d89"
FIXED_APPROVAL_PATH = ".runtime_control/point01_m6_3_5_nvda_sec_document_parser_repaired_global_approval/canonical.sqlite"
FIXED_APPROVAL_SHA256 = "ae48eea1eec25ae96143a49266c991365fe9974d1c282d3d5579ccd56ab561f4"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

PACKAGE_INPUTS = (
    A0_DESIGN,
    DESIGN_PACKAGE,
    CORPUS,
    ORACLE,
    MATRIX,
    HARNESS_POLICY,
    "configs/engineering_handoff/point01_m2_1_compiler_input_validation_policy_v1_0.json",
    "configs/engineering_handoff/point01_m2_3_pack_registry_policy_v1_0.json",
    "configs/engineering_handoff/point01_m2_8_model_admission_policy_v1_0.json",
    "configs/engineering_handoff/point01_m2_9_shadow_orchestration_policy_v1_0.json",
    "src/sec_agent/canonical_runtime/models.py",
    "src/sec_agent/canonical_runtime/planning_service.py",
    "src/sec_agent/canonical_runtime/legacy_objective_adapter.py",
    "src/sec_agent/canonical_runtime/pack_registry.py",
    "src/sec_agent/canonical_runtime/pack_selection.py",
    "src/sec_agent/canonical_runtime/full_serializer.py",
    "src/sec_agent/canonical_runtime/model_admission.py",
    "src/sec_agent/canonical_runtime/feature_flags.py",
    "src/sec_agent/canonical_runtime/shadow_compiler.py",
    "src/sec_agent/canonical_runtime/shadow_orchestration.py",
    "src/sec_agent/canonical_runtime/m2_a1_audit_harness.py",
    "src/sec_agent/canonical_runtime/m2_a1_audit_canary.py",
    "src/sec_agent/canonical_runtime/m2_a1_audit_result.py",
    "src/sec_agent/canonical_runtime/m2_a1_audit_oracle.py",
    "src/sec_agent/canonical_runtime/m2_a1_audit_reviewer_gate.py",
    "src/sec_agent/canonical_runtime/m2_a1_execution_receipt.py",
    "scripts/engineering/run_point01_m2_a1_actual_audit.py",
    "scripts/engineering/run_point01_m2_a1_executable_audit_package_freeze.py",
    "tests/contract/test_point01_m2_a1_assembly_harness.py",
    "tests/contract/test_point01_m2_a1_harness_boundaries.py",
    "tests/contract/test_point01_m2_a1_executable_package_static.py",
)

PAYLOAD_FIELDS = (
    "schema_version", "scope", "package_ref", "authority_boundary", "input_bytes_source", "a0_design_digest", "design_package_digest", "input_file_sha256", "fixed_store_fingerprints", "corpus_digest", "oracle_digest", "scenario_matrix_digest", "harness_policy_digest", "external_package_admission_ref", "external_package_admission_required", "single_use_execution_receipt_required", "actual_probes_currently_authorized", "compiler_shadow_execution_authorized", "receipt_wrapper_persistence_authorized",
)
PACKAGE_FIELDS = frozenset((*PAYLOAD_FIELDS, "package_digest"))


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _staged_bytes(relative_path: str) -> bytes:
    completed = subprocess.run(["git", "show", f":{relative_path}"], cwd=ROOT, capture_output=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"m2_a1_executable_package_input_not_staged:{relative_path}")
    return completed.stdout


def _staged_json(relative_path: str) -> dict[str, Any]:
    return json.loads(_staged_bytes(relative_path).decode("utf-8"))


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and bool(SHA256_RE.fullmatch(value))


def _fixed_store_fingerprints() -> dict[str, Any]:
    return {
        "fixed_approval_store": {"path": FIXED_APPROVAL_PATH, "sha256": FIXED_APPROVAL_SHA256, "access": "harness_canary_rejects_open_read_or_write"},
        "canonical_or_business_store_absence_manifest": {"status": "explicit_absence_no_M2_A1_fixed_canonical_or_business_store_registered", "registered_paths": [], "enforcement": "harness_canary_rejects_every_nonallowlisted_store_path_or_ambient_resolution"},
    }


def _payload(package: dict[str, Any]) -> dict[str, Any]:
    return {field: package[field] for field in PAYLOAD_FIELDS}


def package_payload_digest(package: dict[str, Any]) -> str:
    return canonical_digest(_payload(package))


def build_package() -> dict[str, Any]:
    corpus, oracle, matrix, harness_policy, a0, design = (_staged_json(path) for path in (CORPUS, ORACLE, MATRIX, HARNESS_POLICY, A0_DESIGN, DESIGN_PACKAGE))
    payload = {
        "schema_version": SCHEMA_VERSION,
        "scope": SCOPE,
        "package_ref": PACKAGE_REF,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "input_bytes_source": "git_index",
        "a0_design_digest": str(a0.get("design_digest") or ""),
        "design_package_digest": str(design.get("package_digest") or ""),
        "input_file_sha256": {path: hashlib.sha256(_staged_bytes(path)).hexdigest() for path in PACKAGE_INPUTS},
        "fixed_store_fingerprints": _fixed_store_fingerprints(),
        "corpus_digest": canonical_digest(corpus),
        "oracle_digest": canonical_digest(oracle),
        "scenario_matrix_digest": canonical_digest(matrix),
        "harness_policy_digest": canonical_digest(harness_policy),
        "external_package_admission_ref": "point01-m2-a1-total-reviewer-executable-package-admission:v1",
        "external_package_admission_required": True,
        "single_use_execution_receipt_required": True,
        "actual_probes_currently_authorized": False,
        "compiler_shadow_execution_authorized": False,
        "receipt_wrapper_persistence_authorized": False,
    }
    return {**payload, "package_digest": canonical_digest(payload)}


def _schema_errors(package: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = sorted(PACKAGE_FIELDS - set(package))
    unexpected = sorted(set(package) - PACKAGE_FIELDS)
    if missing:
        errors.append(f"missing_fields:{','.join(missing)}")
    if unexpected:
        errors.append(f"unexpected_fields:{','.join(unexpected)}")
    if missing:
        return errors
    expected = {"schema_version": SCHEMA_VERSION, "scope": SCOPE, "authority_boundary": AUTHORITY_BOUNDARY, "input_bytes_source": "git_index", "external_package_admission_ref": "point01-m2-a1-total-reviewer-executable-package-admission:v1"}
    for field, value in expected.items():
        if package.get(field) != value:
            errors.append(f"{field}_invalid")
    if not isinstance(package.get("package_ref"), str) or not package["package_ref"].strip():
        errors.append("package_ref_invalid")
    for field in ("a0_design_digest", "design_package_digest", "corpus_digest", "oracle_digest", "scenario_matrix_digest", "harness_policy_digest", "package_digest"):
        if not _is_sha256(package.get(field)):
            errors.append(f"{field}_must_be_sha256")
    if package.get("a0_design_digest") != EXPECTED_A0_DESIGN_DIGEST:
        errors.append("a0_design_digest_invalid")
    if package.get("design_package_digest") != EXPECTED_DESIGN_PACKAGE_DIGEST:
        errors.append("design_package_digest_invalid")
    for field, expected_bool in (("external_package_admission_required", True), ("single_use_execution_receipt_required", True), ("actual_probes_currently_authorized", False), ("compiler_shadow_execution_authorized", False), ("receipt_wrapper_persistence_authorized", False)):
        if package.get(field) is not expected_bool:
            errors.append(f"{field}_invalid")
    hashes = package.get("input_file_sha256")
    if not isinstance(hashes, dict) or set(hashes) != set(PACKAGE_INPUTS) or any(not _is_sha256(value) for value in hashes.values()):
        errors.append("input_file_sha256_invalid")
    if package.get("fixed_store_fingerprints") != _fixed_store_fingerprints():
        errors.append("fixed_store_fingerprints_invalid")
    return errors


def validate_harness_policy(policy: dict[str, Any]) -> dict[str, bool]:
    runner = policy.get("actual_runner") if isinstance(policy, dict) else None
    assembly = policy.get("assembly_contract") if isinstance(policy, dict) else None
    terminal = policy.get("terminalization_and_oracle") if isinstance(policy, dict) else None
    receipt = policy.get("receipt_wrapper") if isinstance(policy, dict) else None
    return {
        "policy_schema": policy.get("schema_version") == "finsight_point01_m2_a1_executable_audit_harness_policy_v1_0",
        "actual_runner_inputs_and_no_execution": isinstance(runner, dict) and runner.get("current_behavior") == "always_raises_m2_a1_actual_probes_not_authorized" and set(runner.get("forbidden_inputs") or ()) >= {"expected_cell_oracle", "oracle_digest", "reviewer_expected_values"},
        "explicit_adapter_seed_assembly": isinstance(assembly, dict) and assembly.get("adapter_output_pack_selection") == "must_be_empty_before_explicit_merge" and "pack_selection" in (assembly.get("required_exact_fields") or ()),
        "immutable_actual_before_oracle": isinstance(terminal, dict) and terminal.get("ordering") == ["actual_terminalize", "actual_result_digest", "independent_oracle_evaluate", "reviewer_gate"],
        "receipt_non_authoritative": isinstance(receipt, dict) and receipt.get("persistent_registration") == "forbidden_in_this_execution_point",
        "actual_probes_not_authorized": policy.get("status") == "executable_harness_implemented_actual_probes_not_authorized",
    }


def verify_package(package: dict[str, Any]) -> dict[str, Any]:
    try:
        calculated = package_payload_digest(package)
    except (KeyError, TypeError):
        return {"status": "package_schema_validation_failed", "schema_errors": _schema_errors(package), "mismatches": []}
    if package.get("package_digest") != calculated:
        return {"status": "package_digest_mismatch", "schema_errors": [], "mismatches": [], "calculated_package_digest": calculated}
    errors = _schema_errors(package)
    if errors:
        return {"status": "package_schema_validation_failed", "schema_errors": errors, "mismatches": [], "calculated_package_digest": calculated}
    mismatches: list[str] = []
    for relative_path, expected in sorted(package["input_file_sha256"].items()):
        if hashlib.sha256(_staged_bytes(relative_path)).hexdigest() != expected:
            mismatches.append(relative_path)
    refs = ((CORPUS, "corpus_digest"), (ORACLE, "oracle_digest"), (MATRIX, "scenario_matrix_digest"), (HARNESS_POLICY, "harness_policy_digest"))
    for path, field in refs:
        if canonical_digest(_staged_json(path)) != package[field]:
            mismatches.append(f"{path}:{field}")
    if _staged_json(A0_DESIGN).get("design_digest") != package["a0_design_digest"]:
        mismatches.append("a0_design_digest")
    if _staged_json(DESIGN_PACKAGE).get("package_digest") != package["design_package_digest"]:
        mismatches.append("design_package_digest")
    policy_checks = validate_harness_policy(_staged_json(HARNESS_POLICY))
    if not all(policy_checks.values()):
        mismatches.append("harness_policy_contract_invalid")
    return {"status": "pass" if not mismatches else "package_input_digest_mismatch", "schema_errors": [], "mismatches": mismatches, "calculated_package_digest": calculated, "harness_policy_checks": policy_checks}


def verify_external_admission(package: dict[str, Any], admission: dict[str, Any] | None) -> dict[str, Any]:
    if admission is None:
        return {"status": "package_admission_required"}
    required = {"admission_ref", "reviewer_identity", "decision", "package_ref", "package_digest", "scope", "authority_boundary"}
    if set(admission) != required:
        return {"status": "package_admission_schema_invalid"}
    expected = {"admission_ref": package["external_package_admission_ref"], "reviewer_identity": "william/003/total_reviewer", "decision": "admitted", "package_ref": package["package_ref"], "package_digest": package["package_digest"], "scope": package["scope"], "authority_boundary": package["authority_boundary"]}
    errors = sorted(field for field, value in expected.items() if admission.get(field) != value)
    return {"status": "pass" if not errors else "package_admission_binding_mismatch", "mismatch_fields": errors}


def build_gate(package: dict[str, Any]) -> dict[str, Any]:
    verification = verify_package(package)
    policy_checks = validation_checks = verification.get("harness_policy_checks", {})
    failures = [name for name, passed in policy_checks.items() if not passed]
    if verification["status"] != "pass":
        failures.append("package_verification_failed")
    payload = {
        "result_version": "finsight_point01_m2_a1_executable_audit_package_freeze_gate_result_v1_0",
        "scope": SCOPE,
        "status": "executable_package_frozen_pending_exact_admission" if not failures else "fail_closed",
        "package_ref": package["package_ref"],
        "package_digest": package["package_digest"],
        "package_verify": verification,
        "harness_policy_checks": validation_checks,
        "actual_admission_status": verify_external_admission(package, None)["status"],
        "failures": sorted(failures),
        "execution_counts": {"a0_m2_actual_probes": 0, "compiler_or_shadow_fixture_runs": 0, "model_calls": 0, "network_requests": 0, "external_tool_calls": 0, "provider_calls": 0, "fixed_or_production_store_opens": 0, "store_writes": 0, "business_case_mutations": 0, "legacy_authority_mutations": 0},
        "next_step_requires_total_reviewer": "Register an exact package-external admission only after reviewing this executable package. A separate single-use receipt is required before a future actual run; no receipt is created here.",
        "boundary": "Static package freeze only. The harness/unit tests may validate assembly/canary/oracle contracts but this gate does not execute A0-M2-P01/P02/P03 or compiler/shadow runtime.",
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
    print(json.dumps({"status": gate["status"], "package_digest": package["package_digest"], "gate_digest": gate["gate_digest"]}, ensure_ascii=False))
    return 0 if gate["status"] == "executable_package_frozen_pending_exact_admission" else 1


if __name__ == "__main__":
    raise SystemExit(main())
