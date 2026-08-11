"""Freeze M2-A1 v2.3 receipt-invariant code without running actual scenarios.

This is a standard-library-only, Git-index verifier.  It does not import the
actual runner or M2 runtime, create an admission/receipt, open a canonical
store, or execute P01/P02/P03.
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
MATRIX = "configs/engineering_handoff/point01_m2_a1_execution_ready_scenario_matrix_v2_1.json"
POLICY = "configs/engineering_handoff/point01_m2_a1_receipt_invariants_policy_v2_3.json"
A0_DESIGN = "configs/engineering_handoff/point01_m1_m5_adversarial_retro_audit_design_freeze_v1_0.json"
DESIGN_PACKAGE = "data/manifests/point01_m2_a1_adversarial_audit_package_manifest_v1_1.json"
OUTPUT_PACKAGE = ROOT / "data/manifests/point01_m2_a1_execution_ready_audit_package_manifest_v2_3.json"
OUTPUT_GATE = ROOT / "data/manifests/point01_m2_a1_execution_ready_audit_package_freeze_gate_result_v2_3.json"

SCHEMA_VERSION = "finsight_point01_m2_a1_execution_ready_audit_package_manifest_v2_3"
PACKAGE_REF = "point01-m2-a1-receipt-invariants-adversarial-audit-package-v2-3"
SCOPE = "M2_A1_exact_admission_gated_future_actual_only"
AUTHORITY_BOUNDARY = "no_actual_a0_m2_probe_without_exact_external_admission_and_single_use_receipt_no_model_network_tool_provider_fixed_production_business_or_legacy_mutation"
EXECUTION_MODE = "external_admission_gated"
EXPECTED_A0_DESIGN_DIGEST = "75a76e24a3a730b82942b9861b9d203a5ec0e735a936dbc229d1c68681ff250d"
EXPECTED_DESIGN_PACKAGE_DIGEST = "34a6877a084bc85aa28d160082661db7d1fc9ca04f44d576afe6bb5d5acc5d89"
REJECTED_V2_PACKAGE_DIGEST = "19d70b9fd0c89bd3e7945454a5d7bcc70ff4b2fb26b6d4118ef84543096973f0"
FIXED_APPROVAL_PATH = ".runtime_control/point01_m6_3_5_nvda_sec_document_parser_repaired_global_approval/canonical.sqlite"
FIXED_APPROVAL_SHA256 = "ae48eea1eec25ae96143a49266c991365fe9974d1c282d3d5579ccd56ab561f4"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

PACKAGE_INPUTS = (
    A0_DESIGN,
    DESIGN_PACKAGE,
    CORPUS,
    ORACLE,
    MATRIX,
    POLICY,
    "configs/engineering_handoff/point01_m2_1_compiler_input_validation_policy_v1_0.json",
    "configs/engineering_handoff/point01_m2_2_full_serializer_policy_v1_0.json",
    "configs/engineering_handoff/point01_m2_3_pack_registry_policy_v1_0.json",
    "configs/engineering_handoff/point01_m2_4_pack_selection_policy_v1_0.json",
    "configs/engineering_handoff/point01_m2_8_model_admission_policy_v1_0.json",
    "configs/runtime/point01_feature_flags_v1_0.json",
    "src/sec_agent/canonical_runtime/models.py",
    "src/sec_agent/canonical_runtime/store.py",
    "src/sec_agent/canonical_runtime/object_store.py",
    "src/sec_agent/canonical_runtime/facade.py",
    "src/sec_agent/canonical_runtime/planning_service.py",
    "src/sec_agent/canonical_runtime/legacy_objective_adapter.py",
    "src/sec_agent/canonical_runtime/pack_registry.py",
    "src/sec_agent/canonical_runtime/pack_selection.py",
    "src/sec_agent/canonical_runtime/cell_composition.py",
    "src/sec_agent/canonical_runtime/evidence_policy.py",
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
    "scripts/engineering/run_point01_m2_a1_receipt_registrar.py",
    "scripts/engineering/run_point01_m2_a1_execution_ready_package_freeze.py",
    "tests/contract/test_point01_m2_a1_execution_ready_boundaries.py",
    "tests/contract/test_point01_m2_a1_execution_ready_package_static.py",
    "tests/contract/test_point01_m2_a1_receipt_lifecycle.py",
    "tests/contract/test_point01_m2_a1_assembly_harness.py",
    "tests/contract/test_point01_m2_a1_harness_boundaries.py",
)

PAYLOAD_FIELDS = (
    "schema_version", "scope", "package_ref", "authority_boundary", "input_bytes_source", "a0_design_digest", "design_package_digest", "supersedes_rejected_package_digest", "input_file_sha256", "fixed_store_fingerprints", "corpus_digest", "oracle_digest", "scenario_matrix_digest", "execution_ready_policy_digest", "execution_preflight", "receipt_lifecycle", "execution_mode", "external_package_admission_ref", "external_package_admission_required", "single_use_execution_receipt_required", "receipt_authority_ledger_required", "actual_execution_authorized_by_package", "compiler_shadow_execution_authorized_by_package",
)
PACKAGE_FIELDS = frozenset((*PAYLOAD_FIELDS, "package_digest"))


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _staged_bytes(relative_path: str) -> bytes:
    completed = subprocess.run(["git", "show", f":{relative_path}"], cwd=ROOT, capture_output=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"m2_a1_execution_ready_package_input_not_staged:{relative_path}")
    return completed.stdout


def _staged_json(relative_path: str) -> dict[str, Any]:
    return json.loads(_staged_bytes(relative_path).decode("utf-8"))


def _sha(value: Any) -> bool:
    return isinstance(value, str) and bool(SHA256_RE.fullmatch(value))


def _fixed_fingerprints() -> dict[str, Any]:
    return {
        "fixed_approval_store": {"path": FIXED_APPROVAL_PATH, "sha256": FIXED_APPROVAL_SHA256, "access": "instrumentation_rejects_open_read_or_write"},
        "canonical_or_business_store_absence_manifest": {"status": "explicit_absence_no_M2_A1_fixed_canonical_or_business_store_registered", "registered_paths": [], "enforcement": "instrumentation_rejects_every_nonallowlisted_store_path_or_ambient_resolution"},
    }


def _execution_preflight_contract(*, corpus: dict[str, Any], matrix: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    """Immutable input/location contract used before a future admitted write."""

    return {
        "execution_staging_namespace_id": "point01_m2_a1_exact_admitted_runs_v2_3",
        "execution_staging_namespace_path": "D:/temp/FIN_Insight_Agent/point01_m2_a1_exact_admitted_runs_v2_3",
        "runtime_inputs": {
            "corpus": {"relative_path": CORPUS, "canonical_digest": canonical_digest(corpus)},
            "scenario_matrix": {"relative_path": MATRIX, "canonical_digest": canonical_digest(matrix)},
            "execution_policy": {"relative_path": POLICY, "canonical_digest": canonical_digest(policy)},
        },
        "working_tree_equivalence": "git_index_bytes_with_crlf_normalisation_only",
        "path_derivation": "sha256(package_digest:admission_digest:receipt_id)",
        "caller_path_override": "forbidden",
        "prewrite_order": ["package_validate", "input_verify", "admission_validate", "fixed_fingerprint", "bound_json_verify", "derive_paths", "registrar_authority_only_mkdir_or_sqlite", "executor_no_create_open_and_atomic_consume", "reverify_staged_execution_tree", "verify_ledger_backed_consumption_grant", "then_and_only_then_runtime_output_mkdir_or_M2_import"],
    }


def _receipt_lifecycle_contract() -> dict[str, str]:
    return {
        "registrar": "authority_only_register_exact_package_and_scenario",
        "executor": "open_existing_consume_reverify_verify_grant_before_runtime",
        "post_consume": "materialize_runtime_then_import_m2",
        "crash_recovery": "consumed_without_terminal_outcome_unknown",
    }


def _payload(package: dict[str, Any]) -> dict[str, Any]:
    return {field: package[field] for field in PAYLOAD_FIELDS}


def package_payload_digest(package: dict[str, Any]) -> str:
    return canonical_digest(_payload(package))


def build_package() -> dict[str, Any]:
    corpus, oracle, matrix, policy, a0, design = (_staged_json(path) for path in (CORPUS, ORACLE, MATRIX, POLICY, A0_DESIGN, DESIGN_PACKAGE))
    payload = {
        "schema_version": SCHEMA_VERSION,
        "scope": SCOPE,
        "package_ref": PACKAGE_REF,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "input_bytes_source": "git_index",
        "a0_design_digest": str(a0.get("design_digest") or ""),
        "design_package_digest": str(design.get("package_digest") or ""),
        "supersedes_rejected_package_digest": REJECTED_V2_PACKAGE_DIGEST,
        "input_file_sha256": {path: hashlib.sha256(_staged_bytes(path)).hexdigest() for path in PACKAGE_INPUTS},
        "fixed_store_fingerprints": _fixed_fingerprints(),
        "corpus_digest": canonical_digest(corpus),
        "oracle_digest": canonical_digest(oracle),
        "scenario_matrix_digest": canonical_digest(matrix),
        "execution_ready_policy_digest": canonical_digest(policy),
        "execution_preflight": _execution_preflight_contract(corpus=corpus, matrix=matrix, policy=policy),
        "receipt_lifecycle": _receipt_lifecycle_contract(),
        "execution_mode": EXECUTION_MODE,
        "external_package_admission_ref": "point01-m2-a1-total-reviewer-execution-ready-package-admission:v1",
        "external_package_admission_required": True,
        "single_use_execution_receipt_required": True,
        "receipt_authority_ledger_required": True,
        "actual_execution_authorized_by_package": False,
        "compiler_shadow_execution_authorized_by_package": False,
    }
    return {**payload, "package_digest": canonical_digest(payload)}


def validate_execution_ready_policy(policy: dict[str, Any]) -> dict[str, bool]:
    runner = policy.get("actual_runner") if isinstance(policy, dict) else None
    instrumentation = policy.get("instrumentation") if isinstance(policy, dict) else None
    receipt = policy.get("receipt_authority") if isinstance(policy, dict) else None
    projection = policy.get("actual_projection") if isinstance(policy, dict) else None
    gate = policy.get("reviewer_gate") if isinstance(policy, dict) else None
    preflight = policy.get("execution_preflight") if isinstance(policy, dict) else None
    runtime = tuple(policy.get("real_runtime_path") or ()) if isinstance(policy, dict) else ()
    lifecycle = policy.get("receipt_lifecycle") if isinstance(policy, dict) else None
    return {
        "policy_schema": policy.get("schema_version") == "finsight_point01_m2_a1_receipt_invariants_policy_v2_3",
        "external_admission_mode": policy.get("execution_mode") == EXECUTION_MODE and isinstance(runner, dict) and runner.get("actual_probe_execution_currently_authorized") is False,
        "prewrite_execution_preflight": isinstance(preflight, dict) and preflight.get("execution_staging_namespace_id") == "point01_m2_a1_exact_admitted_runs_v2_3" and preflight.get("caller_path_override") == "forbidden" and {"authority_root_mkdir_for_registrar_only", "existing_ledger_open_for_executor_only", "atomic_consume", "staged_byte_reverify", "ledger_backed_consumption_grant_verify", "runtime_output_mkdir_after_atomic_consume_only", "M2_runtime_import_after_atomic_consume_only"}.issubset(set(preflight.get("before") or ())),
        "real_runtime_path_complete": {"adapt_legacy_research_objective", "PlanningPackRegistry", "PackSelectionEngine", "DecisionSurfacePlanningService", "DeterministicShadowCompiler", "DecisionSurfaceBundleAssembler", "ShadowCompilerOrchestrator"}.issubset(set(runtime)),
        "instrumentation_is_concrete": isinstance(instrumentation, dict) and instrumentation.get("mode") == "context_manager_patch_constructors_and_accessors" and {"sqlite3.connect", "socket.socket.connect", "http.client.HTTPConnection.connect", "preloaded_transport_provider_module_load_gate"}.issubset(set(instrumentation.get("intercepts") or ())),
        "authoritative_receipt_required": isinstance(receipt, dict) and receipt.get("ledger") == "M2A1ReceiptLedger" and receipt.get("register_before_executor") is True and receipt.get("consume_before_runtime_import") is True and receipt.get("terminal_event_required") is True and "preflight_digest" in (receipt.get("required_binding") or ()) and "run_root" in (receipt.get("required_binding") or ()),
        "lifecycle_contract_exact": isinstance(lifecycle, dict) and all(lifecycle.get(field) == value for field, value in _receipt_lifecycle_contract().items()),
    }


def validate_execution_ready_matrix(matrix: dict[str, Any]) -> dict[str, bool]:
    scenarios = matrix.get("scenarios") if isinstance(matrix, dict) else None
    if not isinstance(scenarios, list):
        return {
            "execution_matrix_schema": False,
            "execution_matrix_exact_sixteen_scenarios": False,
            "execution_matrix_runtime_oracle_separation": False,
        }
    ids = [str(item.get("scenario_id") or "") for item in scenarios if isinstance(item, dict)]
    runtime_fields_only = all(
        isinstance(item, dict)
        and {"scenario_id", "input_ref", "mutation", "expected_typed_stop", "owner", "actual_assertions", "oracle_assertions"}.issubset(item)
        for item in scenarios
    )
    return {
        "execution_matrix_schema": matrix.get("schema_version") == "finsight_point01_m2_a1_execution_ready_scenario_matrix_v2_1",
        "execution_matrix_exact_sixteen_scenarios": len(scenarios) == 16 and len(set(ids)) == 16 and all(ids),
        "execution_matrix_runtime_oracle_separation": runtime_fields_only and "expected_typed_stop" in str(matrix.get("actual_runner_input_rule") or "") and "must never enter the runner" in str(matrix.get("actual_runner_input_rule") or "") and "package preflight" in str(matrix.get("actual_runner_input_rule") or ""),
    }


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
    exact = {
        "schema_version": SCHEMA_VERSION,
        "scope": SCOPE,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "input_bytes_source": "git_index",
        "execution_mode": EXECUTION_MODE,
        "external_package_admission_ref": "point01-m2-a1-total-reviewer-execution-ready-package-admission:v1",
        "supersedes_rejected_package_digest": REJECTED_V2_PACKAGE_DIGEST,
    }
    errors.extend(f"{field}_invalid" for field, value in exact.items() if package.get(field) != value)
    if not isinstance(package.get("package_ref"), str) or not package["package_ref"].strip():
        errors.append("package_ref_invalid")
    for field in ("a0_design_digest", "design_package_digest", "supersedes_rejected_package_digest", "corpus_digest", "oracle_digest", "scenario_matrix_digest", "execution_ready_policy_digest", "package_digest"):
        if not _sha(package.get(field)):
            errors.append(f"{field}_must_be_sha256")
    if package.get("a0_design_digest") != EXPECTED_A0_DESIGN_DIGEST:
        errors.append("a0_design_digest_invalid")
    if package.get("design_package_digest") != EXPECTED_DESIGN_PACKAGE_DIGEST:
        errors.append("design_package_digest_invalid")
    for field, expected in (("external_package_admission_required", True), ("single_use_execution_receipt_required", True), ("receipt_authority_ledger_required", True), ("actual_execution_authorized_by_package", False), ("compiler_shadow_execution_authorized_by_package", False)):
        if package.get(field) is not expected:
            errors.append(f"{field}_invalid")
    hashes = package.get("input_file_sha256")
    if not isinstance(hashes, dict) or set(hashes) != set(PACKAGE_INPUTS) or any(not _sha(value) for value in hashes.values()):
        errors.append("input_file_sha256_invalid")
    if package.get("fixed_store_fingerprints") != _fixed_fingerprints():
        errors.append("fixed_store_fingerprints_invalid")
    try:
        expected_preflight = _execution_preflight_contract(
            corpus=_staged_json(CORPUS), matrix=_staged_json(MATRIX), policy=_staged_json(POLICY)
        )
    except (RuntimeError, json.JSONDecodeError):
        errors.append("execution_preflight_inputs_unavailable")
    else:
        if package.get("execution_preflight") != expected_preflight:
            errors.append("execution_preflight_contract_invalid")
    if package.get("receipt_lifecycle") != _receipt_lifecycle_contract():
        errors.append("receipt_lifecycle_contract_invalid")
    return errors


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
    for path, expected in sorted(package["input_file_sha256"].items()):
        if hashlib.sha256(_staged_bytes(path)).hexdigest() != expected:
            mismatches.append(path)
    for path, field in ((CORPUS, "corpus_digest"), (ORACLE, "oracle_digest"), (MATRIX, "scenario_matrix_digest"), (POLICY, "execution_ready_policy_digest")):
        if canonical_digest(_staged_json(path)) != package[field]:
            mismatches.append(f"{path}:{field}")
    if _staged_json(A0_DESIGN).get("design_digest") != package["a0_design_digest"]:
        mismatches.append("a0_design_digest")
    if _staged_json(DESIGN_PACKAGE).get("package_digest") != package["design_package_digest"]:
        mismatches.append("design_package_digest")
    if package.get("execution_preflight") != _execution_preflight_contract(
        corpus=_staged_json(CORPUS), matrix=_staged_json(MATRIX), policy=_staged_json(POLICY)
    ):
        mismatches.append("execution_preflight")
    checks = {
        **validate_execution_ready_policy(_staged_json(POLICY)),
        **validate_execution_ready_matrix(_staged_json(MATRIX)),
    }
    if not all(checks.values()):
        mismatches.append("execution_ready_policy_contract_invalid")
    return {"status": "pass" if not mismatches else "package_input_digest_mismatch", "schema_errors": [], "mismatches": mismatches, "calculated_package_digest": calculated, "policy_checks": checks}


def verify_external_admission(package: dict[str, Any], admission: dict[str, Any] | None) -> dict[str, Any]:
    if admission is None:
        return {"status": "package_admission_required"}
    required = {"schema_version", "admission_ref", "admission_id", "admission_version", "reviewer_identity", "decision", "package_ref", "executable_package_digest", "scope", "authority_boundary", "execution_staging_namespace_id", "execution_mode", "expires_at", "admission_digest"}
    if set(admission) != required:
        return {"status": "package_admission_schema_invalid"}
    expected = {
        "schema_version": "finsight_point01_m2_a1_external_package_admission_v2_3",
        "admission_ref": package["external_package_admission_ref"],
        "reviewer_identity": "william/003/total_reviewer",
        "decision": "admitted",
        "package_ref": package["package_ref"],
        "executable_package_digest": package["package_digest"],
        "scope": package["scope"],
        "authority_boundary": package["authority_boundary"],
        "execution_staging_namespace_id": package["execution_preflight"]["execution_staging_namespace_id"],
        "execution_mode": EXECUTION_MODE,
    }
    errors = sorted(field for field, value in expected.items() if admission.get(field) != value)
    if not _sha(admission.get("admission_digest")):
        errors.append("admission_digest")
    return {"status": "pass" if not errors else "package_admission_binding_mismatch", "mismatch_fields": errors}


def build_gate(package: dict[str, Any]) -> dict[str, Any]:
    verification = verify_package(package)
    checks = verification.get("policy_checks", {})
    failures = [name for name, passed in checks.items() if not passed]
    if verification["status"] != "pass":
        failures.append("package_verification_failed")
    payload = {
        "result_version": "finsight_point01_m2_a1_execution_ready_audit_package_freeze_gate_result_v2_3",
        "scope": SCOPE,
        "status": "receipt_invariants_repaired_package_frozen_pending_exact_admission" if not failures else "fail_closed",
        "package_ref": package["package_ref"],
        "package_digest": package["package_digest"],
        "package_verify": verification,
        "policy_checks": checks,
        "actual_admission_status": verify_external_admission(package, None)["status"],
        "failures": sorted(failures),
        "execution_counts": {"a0_m2_actual_probes": 0, "compiler_or_shadow_fixture_runs": 0, "model_calls": 0, "network_requests": 0, "external_tool_calls": 0, "provider_calls": 0, "fixed_or_production_store_opens": 0, "store_writes": 0, "business_case_mutations": 0, "legacy_authority_mutations": 0, "receipt_registrations": 0, "receipt_consumptions": 0},
        "next_step_requires_total_reviewer": "Independent review of this exact v2.3 receipt-invariants package only. No admission, receipt registration or actual scenario is created by this freeze.",
        "boundary": "Static refreeze only. It packages ledger-backed consumption grants, post-consume staged-byte verification and future actual code but does not execute compiler/shadow, external/model/tool/provider, store or mutation paths.",
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
    return 0 if gate["status"] == "receipt_invariants_repaired_package_frozen_pending_exact_admission" else 1


if __name__ == "__main__":
    raise SystemExit(main())
