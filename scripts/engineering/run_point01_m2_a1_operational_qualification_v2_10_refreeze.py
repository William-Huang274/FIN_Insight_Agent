"""Freeze B0.7/v2.10 without issuing a human authority or running baseline."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from sec_agent.canonical_runtime.m2_a1_execution_receipt import event_append_only_trigger_ddl_digest  # noqa: E402
from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


POLICY = "configs/engineering_handoff/point01_m2_a1_execution_proof_policy_v2_10.json"
OLD_PACKAGE = "data/manifests/point01_m2_a1_execution_ready_audit_package_manifest_v2_9.json"
PACKAGE_REF = "point01-m2-a1-b0-7-classified-authority-execution-proof-package-v2-10"
NAMESPACE_ID = "point01_m2_a1_exact_admitted_runs_v2_10"
NAMESPACE_PATH = "D:/temp/FIN_Insight_Agent/point01_m2_a1_exact_admitted_runs_v2_10"
OUTPUTS = {
    "package": ROOT / "data/manifests/point01_m2_a1_execution_ready_audit_package_manifest_v2_10.json",
    "package_gate": ROOT / "data/manifests/point01_m2_a1_execution_ready_audit_package_freeze_gate_result_v2_10.json",
    "plan": ROOT / "data/manifests/point01_m2_a1_receipt_execution_plan_v1_7_execution_proof.json",
    "plan_gate": ROOT / "data/manifests/point01_m2_a1_receipt_execution_plan_v1_7_execution_proof_gate.json",
    "blueprint": ROOT / "data/manifests/point01_m2_a1_baseline_authority_blueprint_v1_7_execution_proof.json",
    "blueprint_gate": ROOT / "data/manifests/point01_m2_a1_baseline_authority_blueprint_v1_7_execution_proof_gate.json",
}
NEW_INPUTS = {
    POLICY,
    "src/sec_agent/canonical_runtime/m2_a1_execution_receipt.py",
    "src/sec_agent/canonical_runtime/m2_a1_v2_10_execution_proof.py",
    "scripts/engineering/run_point01_m2_a1_v2_10_frozen_jit_window.py",
    "scripts/engineering/run_point01_m2_a1_receipt_registrar_v2_10.py",
    "scripts/engineering/run_point01_m2_a1_actual_audit_v2_10.py",
    "scripts/engineering/run_point01_m2_a1_actual_audit_clean_child_v2_10.py",
    "scripts/engineering/run_point01_m2_a1_operational_qualification_v2_10_refreeze.py",
    "scripts/engineering/run_point01_m2_a1_v2_8_synthetic_operational_child.py",
    "tests/contract/test_point01_m2_a1_v2_10_execution_proof.py",
}


def _index_bytes(relative_path: str) -> bytes:
    completed = subprocess.run(["git", "show", f":{relative_path}"], cwd=ROOT, capture_output=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"v2_10_index_input_missing:{relative_path}")
    return completed.stdout


def _from_index(relative_path: str) -> Mapping[str, Any]:
    value = json.loads(_index_bytes(relative_path).decode("utf-8"))
    if not isinstance(value, Mapping):
        raise RuntimeError(f"v2_10_mapping_required:{relative_path}")
    return value


def _sha(relative_path: str) -> str:
    return hashlib.sha256(_index_bytes(relative_path)).hexdigest()


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _entry(path: str, hashes: Mapping[str, str]) -> dict[str, str]:
    return {"relative_path": path, "sha256": hashes[path]}


def build_package() -> dict[str, Any]:
    old = _from_index(OLD_PACKAGE)
    retired = {
        "scripts/engineering/run_point01_m2_a1_v2_9_frozen_jit_window.py",
        "scripts/engineering/run_point01_m2_a1_receipt_registrar_v2_9.py",
        "scripts/engineering/run_point01_m2_a1_actual_audit_v2_9.py",
        "scripts/engineering/run_point01_m2_a1_actual_audit_clean_child_v2_9.py",
        "scripts/engineering/run_point01_m2_a1_operational_qualification_v2_9_refreeze.py",
        "tests/contract/test_point01_m2_a1_v2_9_executable_authority.py",
    }
    paths = set(old["input_file_sha256"]).difference(retired) | NEW_INPUTS
    hashes = {path: _sha(path) for path in sorted(paths)}
    payload = {key: value for key, value in old.items() if key not in {"schema_version", "package_ref", "package_digest", "input_file_sha256", "execution_preflight", "jit_window_contract", "approval_lineage_contract", "operational_proof_contract", "executable_authority_contract", "transport_isolation", "supersedes", "b0_6_policy_digest"}}
    entries = {
        "orchestrator": _entry("scripts/engineering/run_point01_m2_a1_v2_10_frozen_jit_window.py", hashes),
        "registrar": _entry("scripts/engineering/run_point01_m2_a1_receipt_registrar_v2_10.py", hashes),
        "parent": _entry("scripts/engineering/run_point01_m2_a1_actual_audit_v2_10.py", hashes),
        "clean_child": _entry("scripts/engineering/run_point01_m2_a1_actual_audit_clean_child_v2_10.py", hashes),
        "lifecycle_kernel": _entry("src/sec_agent/canonical_runtime/m2_a1_v2_10_execution_proof.py", hashes),
    }
    payload.update(
        {
            "schema_version": "finsight_point01_m2_a1_execution_ready_audit_package_manifest_v2_10",
            "package_ref": PACKAGE_REF,
            "input_file_sha256": hashes,
            "execution_preflight": {**old["execution_preflight"], "execution_staging_namespace_id": NAMESPACE_ID, "execution_staging_namespace_path": NAMESPACE_PATH},
            "transport_isolation": {**old["transport_isolation"], "runtime_hash_bindings": {**entries, "canary": _entry("src/sec_agent/canonical_runtime/m2_a1_audit_canary.py", hashes)}},
            "jit_window_contract": {"approval_schema_version": "finsight_point01_m2_a1_production_human_jit_window_approval_v2_10", "approval_required_before_issue": True, "orchestrator": entries["orchestrator"], "dry_run": "production_authority_validate_only_no_admission_receipt_namespace_or_write", "execute_sequence": ["verify_production_authority", "issue_admission", "register", "preflight", "consume", "reverify", "grant", "materialize", "parent_clean_child_execute", "immutable_actual", "oracle_artifact", "reviewer_artifact", "terminal"], "default_command": "do_not_invoke", "active_command": "execute_approved_window_only", "supersedes_v2_5_package_digest": old["jit_window_contract"]["supersedes_v2_5_package_digest"]},
            "approval_lineage_contract": {"admission_schema_version": "finsight_point01_m2_a1_external_package_admission_v2_10", "receipt_schema_version": "finsight_point01_m2_a1_single_use_execution_receipt_v2_10", "human_approval_digest_required": True, "reviewer_decision_receipt_schema_version": "finsight_point01_m2_a1_production_reviewer_decision_receipt_v2_10", "reviewer_decision_receipt_resolution_required": True, "ledger_events": ["REGISTERED", "CONSUMED_BEFORE_RUN", "TERMINAL"], "terminal_sequence": ["immutable_actual_validated", "independent_oracle_artifact_verified", "preterminal_reviewer_artifact_verified", "terminal_append"], "post_consume_exception_terminal": "outcome_unknown_no_success", "supersedes_v2_9_package_digest": old["package_digest"]},
            "operational_proof_contract": {"admission_schema_version": "finsight_point01_m2_a1_external_package_admission_v2_10", "receipt_schema_version": "finsight_point01_m2_a1_single_use_execution_receipt_v2_10", "event_source_of_truth": "point01_m2_a1_execution_receipt_events_append_only_sqlite_triggers", "event_payload_digest_reverified_on_read": True, "integration_entry": "package_bound_v2_10_shared_lifecycle_kernel", "synthetic_fixture_authority": "separate_schema_nonhuman_fixture_only", "production_and_synthetic_differ_only_at": ["classified_authority", "isolated_root", "actual_leaf_fixture"], "required_integration_branches": ["happy_path", "corrupted_actual", "reviewer_failure", "post_consume_child_exit"], "supersedes_v2_9_package_digest": old["package_digest"]},
            "executable_authority_contract": {"approval_schema_version": "finsight_point01_m2_a1_production_human_jit_window_approval_v2_10", "reviewer_decision_receipt_schema_version": "finsight_point01_m2_a1_production_reviewer_decision_receipt_v2_10", "synthetic_authority_schema_version": "finsight_point01_m2_a1_synthetic_nonhuman_authority_v2_10", "admission_schema_version": "finsight_point01_m2_a1_external_package_admission_v2_10", "receipt_schema_version": "finsight_point01_m2_a1_single_use_execution_receipt_v2_10", "default_deny": True, "exact_approval_required": True, "shared_lifecycle_kernel_required": True, "entries": entries, "sequence": ["production_approval_preflight", "resolve_reviewer_decision_receipt", "issue_v2_10_admission_and_receipt", "register", "preflight", "consume", "reverify", "grant_verify", "materialize", "exact_bounded_actual_child", "immutable_actual_validation", "independent_oracle_artifact_verified", "preterminal_reviewer_artifact_verified", "terminal_append"], "supersedes_v2_9_package_digest": old["package_digest"]},
            "trigger_ddl_contract": {"normalized_ddl_digest": event_append_only_trigger_ddl_digest(), "enforcement_boundary": "application_controlled_sqlite_append_only_plus_payload_digest_not_malicious_admin_proof"},
            "supersedes": {"v2_9_package_digest": old["package_digest"], "authority_disposition": "v2_9_static_freeze_only_non_replayable"},
            "b0_6_policy_digest": old["b0_6_policy_digest"],
            "b0_7_policy_digest": canonical_digest(_from_index(POLICY)),
        }
    )
    return {**payload, "package_digest": canonical_digest(payload)}


def _verify_package(package: Mapping[str, Any]) -> dict[str, Any]:
    from sec_agent.canonical_runtime.m2_a1_execution_receipt import M2A1ExecutionPreflightError, preflight_exact_execution

    failures: list[str] = []
    if canonical_digest({key: value for key, value in package.items() if key != "package_digest"}) != package.get("package_digest"):
        failures.append("package_digest_mismatch")
    if any(_sha(path) != digest for path, digest in package["input_file_sha256"].items()):
        failures.append("staged_input_hash_mismatch")
    try:
        preflight_exact_execution(package, None, repository_root=ROOT, receipt_id="v2-10-no-receipt", scenario_id="p01-baseline-separated-input", human_approval_digest="0" * 64)
    except M2A1ExecutionPreflightError as exc:
        if str(exc) != "package_admission_required":
            failures.append(f"production_validator:{exc}")
    else:
        failures.append("missing_admission_unexpected_pass")
    return {"status": "pass" if not failures else "fail_closed", "package_current_verify": "pass" if not failures else "fail", "failures": failures, "input_hash_count": len(package["input_file_sha256"]), "trigger_ddl_digest": event_append_only_trigger_ddl_digest(), "external_call_count": 0, "store_write_count": 0}


def _gate(kind: str, target: Mapping[str, Any], verification: Mapping[str, Any], package: Mapping[str, Any]) -> dict[str, Any]:
    field = {"package": "package_digest", "plan": "plan_digest", "blueprint": "blueprint_digest"}[kind]
    payload = {"result_version": f"finsight_point01_m2_a1_v2_10_{kind}_freeze_gate_v1", "status": verification["status"], "package_ref": package["package_ref"], "package_digest": package["package_digest"], "target_digest": target[field], "verification": dict(verification), "execution_counts": {"approval": 0, "admission": 0, "receipt": 0, "ledger": 0, "namespace": 0, "actual": 0, "network": 0, "tool": 0, "model": 0, "provider": 0, "store_write": 0}, "next_step": "independent_review_required_no_active_authority"}
    return {**payload, "gate_digest": canonical_digest(payload)}


def build_artifacts() -> dict[str, dict[str, Any]]:
    package = build_package()
    package_gate = _gate("package", package, _verify_package(package), package)
    scenario_ids = package["scenario_matrix_summary"]["scenario_ids"]
    plan_payload = {"schema_version": "finsight_point01_m2_a1_receipt_execution_plan_v1_7_execution_proof", "status": "B0.7_repaired_refrozen_pending_independent_review", "exact_package": {"package_ref": package["package_ref"], "package_digest": package["package_digest"], "package_gate_digest": package_gate["gate_digest"], "scope": package["scope"], "authority_boundary": package["authority_boundary"], "execution_staging_namespace_id": NAMESPACE_ID, "trigger_ddl_digest": event_append_only_trigger_ddl_digest()}, "supersedes": {"v2_9_package_digest": "5a107d4b1b7f66a3028609f3d419106e6ba2c5664db9781f3b1e2243a391251b", "execution_authority": "none"}, "scenario_execution_order": [{"sequence": index, "scenario_id": value, "future_authority": "independent_production_human_approval_admission_receipt_JIT_only", "on_failure": "fail_fast_no_retry_no_replay"} for index, value in enumerate(scenario_ids, 1)], "group_counts": {"P01": 4, "P02": 6, "P03": 6}, "execution_counts": {"approval": 0, "admission": 0, "receipt": 0, "ledger": 0, "namespace": 0, "actual": 0, "external": 0, "store_write": 0}}
    plan = {**plan_payload, "plan_digest": canonical_digest(plan_payload)}
    plan_gate = _gate("plan", plan, {"status": "pass", "calculated_plan_digest": canonical_digest(plan_payload), "scenario_count": len(scenario_ids)}, package)
    blueprint_payload = {"schema_version": "finsight_point01_m2_a1_baseline_authority_blueprint_v1_7_execution_proof", "status": "B0.7_repaired_refrozen_pending_independent_review", "exact_binding": {"package_digest": package["package_digest"], "package_gate_digest": package_gate["gate_digest"], "plan_digest": plan["plan_digest"], "plan_gate_digest": plan_gate["gate_digest"], "b0_6_policy_digest": package["b0_6_policy_digest"], "b0_7_policy_digest": package["b0_7_policy_digest"], "trigger_ddl_digest": event_append_only_trigger_ddl_digest(), "scenario_id": "p01-baseline-separated-input", "input_ref": "m2-a1-ai-semis-input", "mutation": "none", "authority_boundary": package["authority_boundary"], "execution_staging_namespace_id": NAMESPACE_ID}, "templates": {"production_reviewer_decision_receipt_v2_10": {"schema_version": "finsight_point01_m2_a1_production_reviewer_decision_receipt_v2_10", "state": "unresolved_not_active", "package_external": True}, "production_human_jit_window_approval_v2_10": {"schema_version": "finsight_point01_m2_a1_production_human_jit_window_approval_v2_10", "authority_class": "production_human_total_reviewer", "state": "unresolved_not_active", "provenance": "requires_resolved_reviewer_decision_receipt"}, "synthetic_nonhuman_authority_v2_10": {"schema_version": "finsight_point01_m2_a1_synthetic_nonhuman_authority_v2_10", "authority_class": "synthetic_nonhuman_fixture", "production_cli_accepted": False}, "v2_10_admission": "unresolved_not_active", "v2_10_receipt": "unresolved_not_active"}, "all_other_scenarios": {"count": 15, "authority_issue_forbidden": True}, "command_contracts": {"orchestrator": "do_not_invoke", "registrar": "do_not_invoke", "executor": "do_not_invoke"}, "execution_counts": {"approval": 0, "admission": 0, "receipt": 0, "ledger": 0, "namespace": 0, "actual": 0, "external": 0, "store_write": 0}}
    blueprint = {**blueprint_payload, "blueprint_digest": canonical_digest(blueprint_payload)}
    blueprint_gate = _gate("blueprint", blueprint, {"status": "pass", "calculated_blueprint_digest": canonical_digest(blueprint_payload)}, package)
    return {"package": package, "package_gate": package_gate, "plan": plan, "plan_gate": plan_gate, "blueprint": blueprint, "blueprint_gate": blueprint_gate}


def main() -> int:
    artifacts = build_artifacts()
    for name, path in OUTPUTS.items():
        _write(path, artifacts[name])
    print(json.dumps({"status": "B0.7_repaired_refrozen_pending_independent_review", **{f"{name}_digest": artifacts[name][{"package": "package_digest", "package_gate": "gate_digest", "plan": "plan_digest", "plan_gate": "gate_digest", "blueprint": "blueprint_digest", "blueprint_gate": "gate_digest"}[name]] for name in OUTPUTS}}, sort_keys=True))
    return 0 if all(artifacts[name]["status"] == "pass" for name in ("package_gate", "plan_gate", "blueprint_gate")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
