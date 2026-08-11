"""Refreeze Phase-B0 M2-A1 operational-qualification artifacts without authority.

This standard-library-only script consumes Git-index bytes.  It creates only
reviewable manifests: no admission, receipt, namespace, ledger, compiler,
network, provider, tool, or canonical-store operation is possible here.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
SHA256 = re.compile(r"^[0-9a-f]{64}$")
FIXED_PATH = ".runtime_control/point01_m6_3_5_nvda_sec_document_parser_repaired_global_approval/canonical.sqlite"
FIXED_SHA256 = "ae48eea1eec25ae96143a49266c991365fe9974d1c282d3d5579ccd56ab561f4"
PHASE_A = {
    "classification": ("data/manifests/point01_m2_a1_rc_p38_024_root_cause_classification_v1_0.json", "classification_digest", "537801860ceb455c1ce035621776128c3d8647e2d3af00e66b02d27e8b1e0b71"),
    "repair_package": ("data/manifests/point01_m2_a1_transport_isolation_repair_package_v1_0.json", "package_digest", "11f4cd9267e56e9c6c33eaeb32119194731d76dbe0040e34b441e6daf66bd7cd"),
    "repair_gate": ("data/manifests/point01_m2_a1_transport_isolation_repair_gate_v1_0.json", "gate_digest", "52cd13eda74affc99352a14a3ffff322e96b992b252c40d9dd6335d9f9e181fe"),
}
CORPUS = "configs/engineering_handoff/point01_m2_a1_adversarial_input_corpus_v1_1.json"
ORACLE = "configs/engineering_handoff/point01_m2_a1_independent_expected_cell_oracle_v1_1.json"
MATRIX = "configs/engineering_handoff/point01_m2_a1_execution_ready_scenario_matrix_v2_1.json"
POLICY = "configs/engineering_handoff/point01_m2_a1_operational_qualification_policy_v2_4.json"
A0 = "configs/engineering_handoff/point01_m1_m5_adversarial_retro_audit_design_freeze_v1_0.json"
DESIGN = "data/manifests/point01_m2_a1_adversarial_audit_package_manifest_v1_1.json"
OLD_PACKAGE_DIGEST = "ff5476b9a8c4d9a82a11b163039e118922b09c945a0d53ff9df031b7c268b318"
OLD_BLUEPRINT_DIGEST = "683f3df509735466c33394e3771dded3c0c1bb129ab1c53462902f7b6b5e485f"
OLD_FAILED_ACTUAL_DIGEST = "934fb16b76f1e1b19371603f0d69c2e3e25c9357c8427c84e1e626b1247795d7"
SCOPE = "M2_A1_exact_admission_gated_future_actual_only"
AUTHORITY_BOUNDARY = "no_actual_a0_m2_probe_without_fresh_exact_external_admission_and_single_use_receipt_no_model_network_tool_provider_fixed_production_business_or_legacy_mutation"
PACKAGE_REF = "point01-m2-a1-operational-qualification-adversarial-audit-package-v2-4"
NAMESPACE_ID = "point01_m2_a1_exact_admitted_runs_v2_4"
NAMESPACE_PATH = "D:/temp/FIN_Insight_Agent/point01_m2_a1_exact_admitted_runs_v2_4"
BASELINE = "p01-baseline-separated-input"

OUTPUTS = {
    "package": ROOT / "data/manifests/point01_m2_a1_execution_ready_audit_package_manifest_v2_4.json",
    "package_gate": ROOT / "data/manifests/point01_m2_a1_execution_ready_audit_package_freeze_gate_result_v2_4.json",
    "plan": ROOT / "data/manifests/point01_m2_a1_receipt_execution_plan_v1_1_operational_qualification.json",
    "plan_gate": ROOT / "data/manifests/point01_m2_a1_receipt_execution_plan_v1_1_operational_qualification_gate.json",
    "blueprint": ROOT / "data/manifests/point01_m2_a1_baseline_authority_blueprint_v1_1_operational_qualification.json",
    "blueprint_gate": ROOT / "data/manifests/point01_m2_a1_baseline_authority_blueprint_v1_1_operational_qualification_gate.json",
}

PACKAGE_INPUTS = (
    A0, DESIGN, CORPUS, ORACLE, MATRIX, POLICY,
    *(item[0] for item in PHASE_A.values()),
    "configs/engineering_handoff/point01_m2_1_compiler_input_validation_policy_v1_0.json",
    "configs/engineering_handoff/point01_m2_2_full_serializer_policy_v1_0.json",
    "configs/engineering_handoff/point01_m2_3_pack_registry_policy_v1_0.json",
    "configs/engineering_handoff/point01_m2_4_pack_selection_policy_v1_0.json",
    "configs/engineering_handoff/point01_m2_8_model_admission_policy_v1_0.json",
    "configs/runtime/point01_feature_flags_v1_0.json",
    "src/sec_agent/canonical_runtime/__init__.py",
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
    "scripts/engineering/run_point01_m2_a1_actual_audit_clean_child.py",
    "scripts/engineering/run_point01_m2_a1_receipt_registrar.py",
    "scripts/engineering/run_point01_m2_a1_execution_ready_package_freeze.py",
    "scripts/engineering/run_point01_m2_a1_transport_isolation_bisect.py",
    "scripts/engineering/run_point01_m2_a1_transport_isolation_repair_freeze.py",
    "scripts/engineering/run_point01_m2_a1_actual_audit_v2_4.py",
    "scripts/engineering/run_point01_m2_a1_actual_audit_clean_child_v2_4.py",
    "scripts/engineering/run_point01_m2_a1_receipt_registrar_v2_4.py",
    "scripts/engineering/run_point01_m2_a1_operational_qualification_v2_4_refreeze.py",
    "tests/contract/test_point01_m2_a1_assembly_harness.py",
    "tests/contract/test_point01_m2_a1_execution_ready_boundaries.py",
    "tests/contract/test_point01_m2_a1_execution_ready_package_static.py",
    "tests/contract/test_point01_m2_a1_receipt_lifecycle.py",
    "tests/contract/test_point01_m2_a1_harness_boundaries.py",
    "tests/contract/test_point01_m2_a1_receipt_execution_plan.py",
    "tests/contract/test_point01_m2_a1_external_admission_artifact.py",
    "tests/contract/test_point01_m2_a1_baseline_authority_blueprint.py",
    "tests/contract/test_point01_m2_a1_design_package_static.py",
    "tests/contract/test_point01_m2_a1_executable_package_static.py",
    "tests/contract/test_point01_m2_a1_transport_isolation_repair.py",
    "tests/contract/test_point01_m2_a1_operational_qualification_v2_4.py",
    "tests/contract/test_point01_m2_a1_operational_qualification_v2_4_production_preflight.py",
)


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


@lru_cache(maxsize=None)
def _staged_bytes(path: str) -> bytes:
    completed = subprocess.run(["git", "show", f":{path}"], cwd=ROOT, capture_output=True, check=False)
    if completed.returncode:
        raise RuntimeError(f"phase_b0_input_not_staged:{path}")
    return completed.stdout


def _staged_json(path: str) -> dict[str, Any]:
    payload = json.loads(_staged_bytes(path).decode("utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"phase_b0_mapping_required:{path}")
    return payload


def _is_digest(value: Any) -> bool:
    return isinstance(value, str) and bool(SHA256.fullmatch(value))


def _phase_a_digests() -> dict[str, str]:
    result: dict[str, str] = {}
    for name, (path, field, expected) in PHASE_A.items():
        value = _staged_json(path).get(field)
        if value != expected:
            raise RuntimeError(f"phase_b0_phase_a_digest_mismatch:{name}")
        result[name] = expected
    return result


def _phase_a_artifacts(phase_a: Mapping[str, str]) -> dict[str, dict[str, str]]:
    return {
        name: {
            "relative_path": path,
            "digest_field": field,
            "digest": str(phase_a[name]),
        }
        for name, (path, field, _expected) in PHASE_A.items()
    }


def _fixed_fingerprints() -> dict[str, Any]:
    return {
        "fixed_approval_store": {"path": FIXED_PATH, "sha256": FIXED_SHA256, "access": "fingerprint_only_no_open_or_mutation"},
        "canonical_or_business_store_absence_manifest": {"status": "explicit_absence_no_M2_A1_fixed_canonical_or_business_store_registered", "registered_paths": [], "enforcement": "clean_child_canary_rejects_open_read_write_or_ambient_resolution"},
    }


def _matrix_summary(matrix: Mapping[str, Any]) -> dict[str, Any]:
    scenarios = matrix.get("scenarios")
    if not isinstance(scenarios, list) or len(scenarios) != 16:
        raise RuntimeError("phase_b0_matrix_requires_exact_sixteen_scenarios")
    ids = [str(item.get("scenario_id") or "") for item in scenarios if isinstance(item, Mapping)]
    if len(ids) != 16 or len(set(ids)) != 16 or ids[0] != BASELINE:
        raise RuntimeError("phase_b0_matrix_order_or_identity_invalid")
    groups = {"P01": ids[:4], "P02": ids[4:10], "P03": ids[10:]}
    if {key: len(value) for key, value in groups.items()} != {"P01": 4, "P02": 6, "P03": 6}:
        raise RuntimeError("phase_b0_matrix_group_count_invalid")
    return {"scenario_ids": ids, "groups": groups, "matrix_digest": canonical_digest(matrix)}


def build_package() -> dict[str, Any]:
    policy = _staged_json(POLICY)
    matrix = _staged_json(MATRIX)
    phase_a = _phase_a_digests()
    matrix_summary = _matrix_summary(matrix)
    if policy.get("execution_staging_namespace_id") != NAMESPACE_ID or policy.get("actual_probe_execution_currently_authorized") is not False:
        raise RuntimeError("phase_b0_policy_not_non_authoritative")
    input_hashes = {path: hashlib.sha256(_staged_bytes(path)).hexdigest() for path in PACKAGE_INPUTS}
    runtime_hash_paths = {
        "parent_runner": "scripts/engineering/run_point01_m2_a1_actual_audit_v2_4.py",
        "clean_child": "scripts/engineering/run_point01_m2_a1_actual_audit_clean_child_v2_4.py",
        "canary": "src/sec_agent/canonical_runtime/m2_a1_audit_canary.py",
        "registrar": "scripts/engineering/run_point01_m2_a1_receipt_registrar_v2_4.py",
    }
    payload = {
        "schema_version": "finsight_point01_m2_a1_execution_ready_audit_package_manifest_v2_4",
        "package_ref": PACKAGE_REF,
        "scope": SCOPE,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "input_bytes_source": "git_index",
        "input_file_sha256": input_hashes,
        "phase_a_digests": phase_a,
        "phase_a_artifacts": _phase_a_artifacts(phase_a),
        "fixed_store_fingerprints": _fixed_fingerprints(),
        "corpus_digest": canonical_digest(_staged_json(CORPUS)),
        "oracle_digest": canonical_digest(_staged_json(ORACLE)),
        "scenario_matrix_digest": matrix_summary["matrix_digest"],
        "execution_policy_digest": canonical_digest(policy),
        "scenario_matrix_summary": matrix_summary,
        "execution_preflight": {
            "execution_staging_namespace_id": NAMESPACE_ID,
            "execution_staging_namespace_path": NAMESPACE_PATH,
            "caller_path_override": "forbidden",
            "clean_child_required": True,
            "prewrite_order": ["package_and_staged_input_validate", "exact_external_admission_validate", "existing_ledger_open_no_create", "atomic_receipt_consume", "staged_tree_reverify", "ledger_backed_grant_verify", "runtime_output_materialize", "canary_before_harness_import"],
            "runtime_inputs": {
                "corpus": {"relative_path": CORPUS, "canonical_digest": canonical_digest(_staged_json(CORPUS))},
                "scenario_matrix": {"relative_path": MATRIX, "canonical_digest": canonical_digest(matrix)},
                "execution_policy": {"relative_path": POLICY, "canonical_digest": canonical_digest(policy)},
            },
        },
        "receipt_lifecycle": {
            "registrar": "authority_only_register_exact_package_and_scenario",
            "executor": "open_existing_consume_reverify_verify_grant_before_runtime",
            "post_consume": "materialize_runtime_then_import_m2",
            "crash_recovery": "consumed_without_terminal_outcome_unknown",
            "execution_eligibility": "fresh_exact_admission_and_receipt_required",
        },
        "transport_isolation": {
            "public_exports": "lazy",
            "parent": "stdlib_clean_child_supervisor",
            "module_presence": "context_only",
            "constructor_connect_request": "hard_fail",
            "parent_preload": "cannot_contaminate_python_I_child",
            "runtime_hash_bindings": {
                name: {"relative_path": path, "sha256": input_hashes[path]}
                for name, path in runtime_hash_paths.items()
            },
        },
        "execution_mode": "external_admission_gated",
        "actual_execution_authorized_by_package": False,
        "execution_eligibility": "fresh_exact_admission_and_receipt_required",
        "fresh_external_admission_required": True,
        "single_use_execution_receipt_required": True,
        "cross_gate_contract": {
            "phase_a_exact_digests_required": True,
            "plan_must_bind_package_gate_digest": True,
            "blueprint_must_bind_package_and_plan_gate_digests": True,
        },
        "supersedes": {
            "v2_3_package_digest": OLD_PACKAGE_DIGEST,
            "v2_3_blueprint_digest": OLD_BLUEPRINT_DIGEST,
            "prior_failed_actual_digest": OLD_FAILED_ACTUAL_DIGEST,
            "authority_disposition": "historical_only_expired_consumed_or_non_replayable",
        },
        "zero_execution_counts": {"new_admission": 0, "new_receipt": 0, "receipt_registration": 0, "receipt_consumption": 0, "runtime_namespace": 0, "actual_probe": 0, "compiler_or_shadow": 0, "network_success": 0, "tool": 0, "provider": 0, "model": 0, "fixed_or_business_store_open": 0, "store_write": 0, "business_case_mutation": 0, "legacy_authority_mutation": 0},
    }
    return {**payload, "package_digest": canonical_digest(payload)}


def verify_package(package: Mapping[str, Any]) -> dict[str, Any]:
    payload = {key: value for key, value in package.items() if key != "package_digest"}
    failures: list[str] = []
    if package.get("package_digest") != canonical_digest(payload):
        failures.append("package_digest_mismatch")
    exact = {"schema_version": "finsight_point01_m2_a1_execution_ready_audit_package_manifest_v2_4", "package_ref": PACKAGE_REF, "scope": SCOPE, "authority_boundary": AUTHORITY_BOUNDARY, "input_bytes_source": "git_index", "execution_mode": "external_admission_gated", "actual_execution_authorized_by_package": False, "execution_eligibility": "fresh_exact_admission_and_receipt_required"}
    failures.extend(f"{key}_invalid" for key, value in exact.items() if package.get(key) != value)
    hashes = package.get("input_file_sha256")
    if not isinstance(hashes, Mapping) or set(hashes) != set(PACKAGE_INPUTS):
        failures.append("input_hash_schema_invalid")
    else:
        for path, expected in hashes.items():
            if not _is_digest(expected) or hashlib.sha256(_staged_bytes(str(path))).hexdigest() != expected:
                failures.append(f"input_hash_mismatch:{path}")
    try:
        phase_a = _phase_a_digests()
        matrix_summary = _matrix_summary(_staged_json(MATRIX))
    except RuntimeError as exc:
        failures.append(str(exc))
    else:
        if package.get("phase_a_digests") != phase_a:
            failures.append("phase_a_binding_mismatch")
        if package.get("scenario_matrix_summary") != matrix_summary:
            failures.append("scenario_matrix_summary_mismatch")
        if package.get("scenario_matrix_digest") != matrix_summary["matrix_digest"]:
            failures.append("scenario_matrix_digest_mismatch")
    if package.get("fixed_store_fingerprints") != _fixed_fingerprints():
        failures.append("fixed_store_fingerprint_mismatch")
    if package.get("supersedes") != {"v2_3_package_digest": OLD_PACKAGE_DIGEST, "v2_3_blueprint_digest": OLD_BLUEPRINT_DIGEST, "prior_failed_actual_digest": OLD_FAILED_ACTUAL_DIGEST, "authority_disposition": "historical_only_expired_consumed_or_non_replayable"}:
        failures.append("legacy_nonreplay_binding_mismatch")
    # The freeze script must exercise the same production schema/preflight
    # path the future registrar/executor will use.  A missing admission is the
    # only accepted terminal here; it proves schema acceptance without any
    # ledger, namespace, authority, receipt or runtime materialization.
    production_preflight = {"status": "not_run"}
    if not failures:
        import sys

        sys.path.insert(0, str(ROOT / "src"))
        from sec_agent.canonical_runtime.m2_a1_execution_receipt import M2A1ExecutionPreflightError, preflight_exact_execution

        try:
            preflight_exact_execution(package, None, repository_root=ROOT, receipt_id="preflight-schema-only-no-receipt", scenario_id=BASELINE)
        except M2A1ExecutionPreflightError as exc:
            production_preflight = {"status": str(exc), "side_effects": {"authority": 0, "receipt": 0, "namespace": 0, "runtime": 0}}
            if str(exc) != "package_admission_required":
                failures.append("production_preflight_schema_or_identity_invalid")
        else:
            failures.append("production_preflight_missing_admission_did_not_fail_closed")
    return {"status": "pass" if not failures else "fail_closed", "failures": sorted(set(failures)), "calculated_package_digest": canonical_digest(payload), "production_preflight": production_preflight}


def build_plan(package: Mapping[str, Any], package_gate: Mapping[str, Any]) -> dict[str, Any]:
    summary = package["scenario_matrix_summary"]
    planned = []
    for sequence, scenario_id in enumerate(summary["scenario_ids"], start=1):
        group = "P01" if sequence <= 4 else "P02" if sequence <= 10 else "P03"
        planned.append({"sequence": sequence, "group": group, "scenario_id": scenario_id, "future_authority": "independent_admission_plus_single_use_receipt_JIT_only", "on_failure": "fail_fast_no_retry_no_replay_no_next_authority"})
    payload = {
        "schema_version": "finsight_point01_m2_a1_receipt_execution_plan_v1_1_operational_qualification",
        "status": "compatibility_assessed_pending_independent_review_no_authority",
        "scope": "M2_A1_receipt_execution_plan_compatibility_only_no_admission_receipt_ledger_namespace_or_actual",
        "exact_package": {"package_ref": package["package_ref"], "package_digest": package["package_digest"], "package_gate_digest": package_gate["gate_digest"], "scope": package["scope"], "authority_boundary": package["authority_boundary"], "execution_staging_namespace_id": NAMESPACE_ID},
        "phase_a_digests": package["phase_a_digests"],
        "supersedes": {"prior_plan_digest": "9a0e16878bb899b853e2d91d84a5771d69b4b7d49cd37a490cc20d2de7ca4f5a", "status": "prior_plan_not_valid_for_v2_4_execution"},
        "compatibility": {"matrix_digest": package["scenario_matrix_digest"], "scenario_count": 16, "group_counts": {key: len(value) for key, value in summary["groups"].items()}, "semantic_change": "p03_transport_assertions_now_distinguish_module_context_from_constructor_connect_request", "new_plan_required": True},
        "baseline_first": BASELINE,
        "scenario_execution_order": planned,
        "group_checkpoints": [{"group": key, "after_sequence": max(item["sequence"] for item in planned if item["group"] == key), "action": "independent_oracle_and_reviewer_checkpoint_required"} for key in ("P01", "P02", "P03")],
        "authority_rules": {"independent_pair_per_scenario": True, "JIT_only": True, "no_batch_pre_generation": True, "admission_and_receipt_expiry": "discard_and_seek_new_review_never_mutate_old_timestamps_or_digests", "all_other_scenarios_blocked_until_prior_checkpoint": True},
        "runner_isolation": {"actual_runner_never_reads": ["oracle", "reviewer_expectation", "expected_typed_stop"], "oracle_reads_only_after_immutable_actual_terminalization": True, "reviewer_reads_actual_oracle_receipt_counter_and_fingerprint": True},
        "execution_counts": {"admission": 0, "receipt": 0, "ledger": 0, "namespace": 0, "actual": 0, "external": 0, "store_write": 0},
    }
    return {**payload, "plan_digest": canonical_digest(payload)}


def verify_plan(plan: Mapping[str, Any], package: Mapping[str, Any], package_gate: Mapping[str, Any]) -> dict[str, Any]:
    payload = {key: value for key, value in plan.items() if key != "plan_digest"}
    failures: list[str] = []
    if plan.get("plan_digest") != canonical_digest(payload): failures.append("plan_digest_mismatch")
    if plan.get("status") != "compatibility_assessed_pending_independent_review_no_authority": failures.append("plan_status_invalid")
    if plan.get("exact_package", {}).get("package_digest") != package.get("package_digest") or plan.get("exact_package", {}).get("package_gate_digest") != package_gate.get("gate_digest"): failures.append("plan_package_or_gate_binding_mismatch")
    compatibility = plan.get("compatibility", {})
    if compatibility.get("scenario_count") != 16 or compatibility.get("group_counts") != {"P01": 4, "P02": 6, "P03": 6}: failures.append("plan_matrix_coverage_invalid")
    entries = plan.get("scenario_execution_order")
    if not isinstance(entries, list) or len(entries) != 16 or entries[0].get("scenario_id") != BASELINE or any(item.get("future_authority") != "independent_admission_plus_single_use_receipt_JIT_only" for item in entries if isinstance(item, Mapping)): failures.append("plan_JIT_or_baseline_invalid")
    if plan.get("execution_counts") != {"admission": 0, "receipt": 0, "ledger": 0, "namespace": 0, "actual": 0, "external": 0, "store_write": 0}: failures.append("plan_zero_counts_invalid")
    return {"status": "pass" if not failures else "fail_closed", "failures": sorted(set(failures)), "calculated_plan_digest": canonical_digest(payload)}


def _unresolved_templates() -> dict[str, Any]:
    unresolved = "unresolved_not_active"
    return {
        "external_admission": {
            "schema_version": "finsight_point01_m2_a1_external_package_admission_v2_4",
            "fields": {key: unresolved for key in ("admission_ref", "admission_id", "admission_version", "reviewer_identity", "decision", "package_ref", "executable_package_digest", "scope", "authority_boundary", "execution_staging_namespace_id", "execution_mode", "expires_at", "admission_digest")},
        },
        "authority_wrapper": {
            "schema_version": "finsight_point01_m2_a1_external_admission_authority_wrapper_v2_4",
            "fields": {key: unresolved for key in ("authority_ref", "reviewer_identity", "decision", "issued_at", "expires_at", "package_ref", "package_digest", "package_gate_digest", "plan_digest", "plan_gate_digest", "scope", "authority_boundary", "execution_staging_namespace_id", "runtime_admission_digest", "nonce_sha256", "fixed_store_fingerprint", "authority_artifact_digest")},
        },
        "single_use_execution_receipt": {
            "schema_version": "finsight_point01_m2_a1_single_use_execution_receipt_v2_4",
            "fields": {key: unresolved for key in ("receipt_id", "receipt_version", "approval_id", "package_ref", "executable_package_digest", "scope", "admission_digest", "nonce_sha256", "expires_at", "reviewer_identity", "execution_staging_namespace_id", "scenario_id", "state", "single_use", "receipt_digest")},
        },
    }


def build_blueprint(package: Mapping[str, Any], package_gate: Mapping[str, Any], plan: Mapping[str, Any], plan_gate: Mapping[str, Any]) -> dict[str, Any]:
    payload = {
        "schema_version": "finsight_point01_m2_a1_baseline_authority_blueprint_v1_1_operational_qualification",
        "status": "baseline_blueprint_refrozen_pending_independent_review_no_authority",
        "scope": "M2_A1_baseline_authority_blueprint_only_no_admission_receipt_ledger_namespace_or_actual",
        "exact_binding": {"package_ref": package["package_ref"], "package_digest": package["package_digest"], "package_gate_digest": package_gate["gate_digest"], "plan_digest": plan["plan_digest"], "plan_gate_digest": plan_gate["gate_digest"], "phase_a_digests": package["phase_a_digests"], "scenario_id": BASELINE, "input_ref": "m2-a1-ai-semis-input", "mutation": "none", "reviewer_identity": "william/003/total_reviewer", "authority_boundary": package["authority_boundary"], "execution_staging_namespace_id": NAMESPACE_ID},
        "supersedes": {"prior_blueprint_digest": OLD_BLUEPRINT_DIGEST, "status": "historical_only_not_executable_for_v2_4"},
        "all_other_scenarios": {"count": 15, "authority_issue_forbidden": True},
        "templates": _unresolved_templates(),
        "command_contracts": {"registrar": "do_not_invoke", "executor": "do_not_invoke", "baseline_rerun": "do_not_invoke"},
        "JIT_contract": {"future_admission_TTL_minutes": 30, "future_receipt_TTL_minutes": 15, "receipt_not_later_than_admission": True, "issue_register_preflight_consume_reverify_grant_materialize_execute": "future_separately_approved_only"},
        "post_run_pipeline": ["immutable_actual_terminalize", "independent_oracle_after_actual", "reviewer_gate", "fail_fast_no_retry_or_replay"],
        "execution_counts": {"admission": 0, "receipt": 0, "ledger": 0, "namespace": 0, "actual": 0, "external": 0, "store_write": 0},
    }
    return {**payload, "blueprint_digest": canonical_digest(payload)}


def verify_blueprint(blueprint: Mapping[str, Any], package: Mapping[str, Any], package_gate: Mapping[str, Any], plan: Mapping[str, Any], plan_gate: Mapping[str, Any]) -> dict[str, Any]:
    payload = {key: value for key, value in blueprint.items() if key != "blueprint_digest"}
    failures: list[str] = []
    if blueprint.get("blueprint_digest") != canonical_digest(payload): failures.append("blueprint_digest_mismatch")
    binding = blueprint.get("exact_binding", {})
    if binding.get("package_digest") != package.get("package_digest") or binding.get("package_gate_digest") != package_gate.get("gate_digest") or binding.get("plan_digest") != plan.get("plan_digest") or binding.get("plan_gate_digest") != plan_gate.get("gate_digest") or binding.get("phase_a_digests") != package.get("phase_a_digests") or binding.get("scenario_id") != BASELINE: failures.append("blueprint_exact_binding_invalid")
    if blueprint.get("all_other_scenarios") != {"count": 15, "authority_issue_forbidden": True}: failures.append("blueprint_other_scenarios_invalid")
    if blueprint.get("templates") != _unresolved_templates(): failures.append("blueprint_runtime_template_contract_invalid")
    if any(value != "do_not_invoke" for value in blueprint.get("command_contracts", {}).values()): failures.append("blueprint_command_contract_invalid")
    if blueprint.get("execution_counts") != {"admission": 0, "receipt": 0, "ledger": 0, "namespace": 0, "actual": 0, "external": 0, "store_write": 0}: failures.append("blueprint_zero_counts_invalid")
    return {"status": "pass" if not failures else "fail_closed", "failures": sorted(set(failures)), "calculated_blueprint_digest": canonical_digest(payload)}


def _gate(kind: str, target: Mapping[str, Any], verify: Mapping[str, Any], package: Mapping[str, Any]) -> dict[str, Any]:
    target_key = {"execution_ready_package": "package_digest", "receipt_execution_plan": "plan_digest", "baseline_authority_blueprint": "blueprint_digest"}[kind]
    payload = {"result_version": f"finsight_point01_m2_a1_{kind}_gate_v1_1", "status": "pass" if verify.get("status") == "pass" else "fail_closed", "package_ref": package["package_ref"], "package_digest": package["package_digest"], "target_digest": target[target_key], "verification": dict(verify), "fixed_store_fingerprint": _fixed_fingerprints()["fixed_approval_store"], "execution_counts": {"admission": 0, "receipt": 0, "ledger": 0, "namespace": 0, "actual": 0, "network": 0, "tool": 0, "model": 0, "provider": 0, "store_write": 0}, "next_step": "independent_review_required_no_authority_issued"}
    return {**payload, "gate_digest": canonical_digest(payload)}


def build_artifacts() -> dict[str, dict[str, Any]]:
    package = build_package()
    package_verify = verify_package(package)
    package_gate = _gate("execution_ready_package", package, package_verify, package)
    plan = build_plan(package, package_gate)
    plan_verify = verify_plan(plan, package, package_gate)
    plan_gate = _gate("receipt_execution_plan", plan, plan_verify, package)
    blueprint = build_blueprint(package, package_gate, plan, plan_gate)
    blueprint_verify = verify_blueprint(blueprint, package, package_gate, plan, plan_gate)
    blueprint_gate = _gate("baseline_authority_blueprint", blueprint, blueprint_verify, package)
    return {"package": package, "package_gate": package_gate, "plan": plan, "plan_gate": plan_gate, "blueprint": blueprint, "blueprint_gate": blueprint_gate}


def validate_new_execution_identity(*, package_digest: str, blueprint_digest: str, admission_or_receipt_digest: str) -> str:
    """Static future-admission guard; old authority identities never activate v2.4."""
    if package_digest == OLD_PACKAGE_DIGEST or blueprint_digest == OLD_BLUEPRINT_DIGEST or admission_or_receipt_digest == OLD_FAILED_ACTUAL_DIGEST:
        return "historical_authority_non_replayable"
    return "fresh_exact_external_admission_and_receipt_required"


def _write(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    artifacts = build_artifacts()
    for name, path in OUTPUTS.items(): _write(path, artifacts[name])
    statuses = [artifacts["package_gate"]["status"], artifacts["plan_gate"]["status"], artifacts["blueprint_gate"]["status"]]
    print(json.dumps({"status": "phase_b0_refrozen_pending_independent_review" if statuses == ["pass", "pass", "pass"] else "fail_closed", "package_digest": artifacts["package"]["package_digest"], "package_gate_digest": artifacts["package_gate"]["gate_digest"], "plan_digest": artifacts["plan"]["plan_digest"], "plan_gate_digest": artifacts["plan_gate"]["gate_digest"], "blueprint_digest": artifacts["blueprint"]["blueprint_digest"], "blueprint_gate_digest": artifacts["blueprint_gate"]["gate_digest"]}, ensure_ascii=False, sort_keys=True))
    return 0 if statuses == ["pass", "pass", "pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
