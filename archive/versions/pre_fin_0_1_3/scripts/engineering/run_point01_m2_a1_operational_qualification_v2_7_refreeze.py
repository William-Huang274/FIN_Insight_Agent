"""Refreeze B0.4 approval-lineage repair without issuing any authority."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


OLD_PACKAGE = ROOT / "data/manifests/point01_m2_a1_execution_ready_audit_package_manifest_v2_6.json"
PACKAGE_REF = "point01-m2-a1-approval-lineage-preterminal-terminal-package-v2-7"
NAMESPACE_ID = "point01_m2_a1_exact_admitted_runs_v2_7"
NAMESPACE_PATH = "D:/temp/FIN_Insight_Agent/point01_m2_a1_exact_admitted_runs_v2_7"
POLICY = "configs/engineering_handoff/point01_m2_a1_approval_lineage_policy_v2_7.json"
OUTPUTS = {
    "package": ROOT / "data/manifests/point01_m2_a1_execution_ready_audit_package_manifest_v2_7.json",
    "package_gate": ROOT / "data/manifests/point01_m2_a1_execution_ready_audit_package_freeze_gate_result_v2_7.json",
    "plan": ROOT / "data/manifests/point01_m2_a1_receipt_execution_plan_v1_4_approval_lineage.json",
    "plan_gate": ROOT / "data/manifests/point01_m2_a1_receipt_execution_plan_v1_4_approval_lineage_gate.json",
    "blueprint": ROOT / "data/manifests/point01_m2_a1_baseline_authority_blueprint_v1_4_approval_lineage.json",
    "blueprint_gate": ROOT / "data/manifests/point01_m2_a1_baseline_authority_blueprint_v1_4_approval_lineage_gate.json",
}
NEW_INPUTS = {
    POLICY,
    "src/sec_agent/canonical_runtime/m2_a1_execution_receipt.py",
    "src/sec_agent/canonical_runtime/m2_a1_frozen_jit.py",
    "src/sec_agent/canonical_runtime/m2_a1_audit_harness.py",
    "src/sec_agent/canonical_runtime/m2_a1_audit_reviewer_gate.py",
    "scripts/engineering/run_point01_m2_a1_v2_7_frozen_jit_window.py",
    "scripts/engineering/run_point01_m2_a1_actual_audit_v2_7.py",
    "scripts/engineering/run_point01_m2_a1_actual_audit_clean_child_v2_7.py",
    "scripts/engineering/run_point01_m2_a1_receipt_registrar_v2_7.py",
    "scripts/engineering/run_point01_m2_a1_v2_7_synthetic_terminal_child.py",
    "scripts/engineering/run_point01_m2_a1_operational_qualification_v2_7_refreeze.py",
    "tests/contract/test_point01_m2_a1_v2_7_approval_lineage.py",
}
RETIRED_INPUTS = {
    "scripts/engineering/run_point01_m2_a1_v2_6_frozen_jit_window.py",
    "scripts/engineering/run_point01_m2_a1_actual_audit_v2_6.py",
    "scripts/engineering/run_point01_m2_a1_actual_audit_clean_child_v2_6.py",
    "scripts/engineering/run_point01_m2_a1_receipt_registrar_v2_6.py",
    "scripts/engineering/run_point01_m2_a1_operational_qualification_v2_6_refreeze.py",
    "tests/contract/test_point01_m2_a1_v2_6_frozen_jit.py",
}


def _index_bytes(relative_path: str) -> bytes:
    result = subprocess.run(["git", "show", f":{relative_path}"], cwd=ROOT, capture_output=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"v2_7_missing_staged_input:{relative_path}")
    return result.stdout


def _json_from_index(relative_path: str) -> Mapping[str, Any]:
    value = json.loads(_index_bytes(relative_path).decode("utf-8"))
    if not isinstance(value, Mapping):
        raise RuntimeError(f"v2_7_mapping_required:{relative_path}")
    return value


def _sha(relative_path: str) -> str:
    return hashlib.sha256(_index_bytes(relative_path)).hexdigest()


def _write(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _policy_digest() -> str:
    return canonical_digest(_json_from_index(POLICY))


def build_package() -> dict[str, Any]:
    old = _json_from_index("data/manifests/point01_m2_a1_execution_ready_audit_package_manifest_v2_6.json")
    paths = set(old["input_file_sha256"]).difference(RETIRED_INPUTS) | NEW_INPUTS
    hashes = {path: _sha(path) for path in sorted(paths)}
    payload = {key: value for key, value in old.items() if key not in {"schema_version", "package_ref", "package_digest", "input_file_sha256", "execution_preflight", "transport_isolation", "receipt_lifecycle", "jit_window_contract", "supersedes"}}
    payload.update({
        "schema_version": "finsight_point01_m2_a1_execution_ready_audit_package_manifest_v2_7",
        "package_ref": PACKAGE_REF,
        "input_file_sha256": hashes,
        "execution_preflight": {**old["execution_preflight"], "execution_staging_namespace_id": NAMESPACE_ID, "execution_staging_namespace_path": NAMESPACE_PATH},
        "transport_isolation": {**old["transport_isolation"], "runtime_hash_bindings": {
            "parent_runner": {"relative_path": "scripts/engineering/run_point01_m2_a1_actual_audit_v2_7.py", "sha256": hashes["scripts/engineering/run_point01_m2_a1_actual_audit_v2_7.py"]},
            "clean_child": {"relative_path": "scripts/engineering/run_point01_m2_a1_actual_audit_clean_child_v2_7.py", "sha256": hashes["scripts/engineering/run_point01_m2_a1_actual_audit_clean_child_v2_7.py"]},
            "canary": {"relative_path": "src/sec_agent/canonical_runtime/m2_a1_audit_canary.py", "sha256": hashes["src/sec_agent/canonical_runtime/m2_a1_audit_canary.py"]},
            "registrar": {"relative_path": "scripts/engineering/run_point01_m2_a1_receipt_registrar_v2_7.py", "sha256": hashes["scripts/engineering/run_point01_m2_a1_receipt_registrar_v2_7.py"]},
            "jit_orchestrator": {"relative_path": "scripts/engineering/run_point01_m2_a1_v2_7_frozen_jit_window.py", "sha256": hashes["scripts/engineering/run_point01_m2_a1_v2_7_frozen_jit_window.py"]},
        }},
        "receipt_lifecycle": {"registrar": "authority_only_register_exact_package_scenario_and_human_approval_digest", "executor": "open_existing_consume_reverify_verify_grant_before_runtime", "post_consume": "materialize_runtime_then_import_m2", "crash_recovery": "consumed_without_terminal_outcome_unknown", "execution_eligibility": "fresh_exact_admission_and_receipt_required", "terminal_order": "actual_oracle_reviewer_before_terminal"},
        "jit_window_contract": {"approval_schema_version": "finsight_point01_m2_a1_human_jit_window_approval_v1", "approval_required_before_issue": True, "orchestrator": {"relative_path": "scripts/engineering/run_point01_m2_a1_v2_7_frozen_jit_window.py", "sha256": hashes["scripts/engineering/run_point01_m2_a1_v2_7_frozen_jit_window.py"]}, "dry_run": "approval_validate_only_no_admission_receipt_namespace_or_write", "execute_sequence": ["verify_approval", "issue_admission", "verify", "register", "preflight", "consume", "reverify", "grant", "materialize", "parent_clean_child_execute", "immutable_actual_validated", "independent_oracle", "preterminal_reviewer", "terminal_append", "closeout"], "default_command": "do_not_invoke", "active_command": "execute_approved_window_only", "supersedes_v2_6_package_digest": "e85ceffb0922ceda99e105b519a7f2dac19d5e5bdcea357925ee451d066ad4ed"},
        "approval_lineage_contract": {"admission_schema_version": "finsight_point01_m2_a1_external_package_admission_v2_7", "receipt_schema_version": "finsight_point01_m2_a1_single_use_execution_receipt_v2_7", "human_approval_digest_required": True, "ledger_events": ["REGISTERED", "CONSUMED_BEFORE_RUN", "TERMINAL"], "terminal_sequence": ["immutable_actual_validated", "independent_oracle", "preterminal_reviewer", "terminal_append"], "post_consume_exception_terminal": "outcome_unknown_no_success", "supersedes_v2_6_package_digest": "e85ceffb0922ceda99e105b519a7f2dac19d5e5bdcea357925ee451d066ad4ed"},
        "supersedes": {"v2_6_package_digest": "e85ceffb0922ceda99e105b519a7f2dac19d5e5bdcea357925ee451d066ad4ed", "authority_disposition": "historical_only_expired_consumed_or_non_replayable"},
        "b0_4_policy_digest": _policy_digest(),
    })
    return {**payload, "package_digest": canonical_digest(payload)}


def verify_package(package: Mapping[str, Any]) -> dict[str, Any]:
    payload = {key: value for key, value in package.items() if key != "package_digest"}
    failures: list[str] = []
    if package.get("package_digest") != canonical_digest(payload): failures.append("package_digest_mismatch")
    if any(_sha(path) != digest for path, digest in package.get("input_file_sha256", {}).items()): failures.append("staged_input_hash_mismatch")
    try:
        from sec_agent.canonical_runtime.m2_a1_execution_receipt import M2A1ExecutionPreflightError, preflight_exact_execution
        preflight_exact_execution(package, None, repository_root=ROOT, receipt_id="v2-7-no-receipt", scenario_id="p01-baseline-separated-input")
    except M2A1ExecutionPreflightError as exc:
        if str(exc) != "package_admission_required": failures.append(f"production_validator:{exc}")
    else: failures.append("missing_admission_unexpected_pass")
    return {"status": "pass" if not failures else "fail_closed", "failures": failures, "calculated_package_digest": canonical_digest(payload), "input_hash_count": len(package.get("input_file_sha256", {})), "external_call_count": 0, "store_write_count": 0}


def build_plan(package: Mapping[str, Any], package_gate: Mapping[str, Any]) -> dict[str, Any]:
    ids = package["scenario_matrix_summary"]["scenario_ids"]
    payload = {"schema_version": "finsight_point01_m2_a1_receipt_execution_plan_v1_4_approval_lineage", "status": "B0_4_repaired_refrozen_pending_independent_review", "exact_package": {"package_ref": package["package_ref"], "package_digest": package["package_digest"], "package_gate_digest": package_gate["gate_digest"], "scope": package["scope"], "authority_boundary": package["authority_boundary"], "execution_staging_namespace_id": NAMESPACE_ID}, "approval_lineage_contract": package["approval_lineage_contract"], "baseline_first": "p01-baseline-separated-input", "scenario_execution_order": [{"sequence": index, "scenario_id": item, "future_authority": "independent_human_approval_admission_receipt_JIT_only", "on_failure": "fail_fast_no_retry_no_replay"} for index, item in enumerate(ids, 1)], "group_counts": {"P01": 4, "P02": 6, "P03": 6}, "execution_counts": {"approval": 0, "admission": 0, "receipt": 0, "ledger": 0, "namespace": 0, "actual": 0, "external": 0, "store_write": 0}}
    return {**payload, "plan_digest": canonical_digest(payload)}


def build_blueprint(package: Mapping[str, Any], package_gate: Mapping[str, Any], plan: Mapping[str, Any], plan_gate: Mapping[str, Any]) -> dict[str, Any]:
    unresolved = "unresolved_not_active"
    payload = {"schema_version": "finsight_point01_m2_a1_baseline_authority_blueprint_v1_4_approval_lineage", "status": "B0_4_repaired_refrozen_pending_independent_review", "exact_binding": {"package_ref": package["package_ref"], "package_digest": package["package_digest"], "package_gate_digest": package_gate["gate_digest"], "plan_digest": plan["plan_digest"], "plan_gate_digest": plan_gate["gate_digest"], "scenario_id": "p01-baseline-separated-input", "input_ref": "m2-a1-ai-semis-input", "mutation": "none", "authority_boundary": package["authority_boundary"], "execution_staging_namespace_id": NAMESPACE_ID, "approval_lineage_contract": package["approval_lineage_contract"]}, "templates": {"human_jit_window_approval": unresolved, "v2_7_admission": unresolved, "v2_7_receipt": unresolved}, "all_other_scenarios": {"count": 15, "authority_issue_forbidden": True}, "command_contracts": {"orchestrator": "do_not_invoke", "registrar": "do_not_invoke", "executor": "do_not_invoke"}, "execution_counts": {"approval": 0, "admission": 0, "receipt": 0, "ledger": 0, "namespace": 0, "actual": 0, "external": 0, "store_write": 0}}
    return {**payload, "blueprint_digest": canonical_digest(payload)}


def _gate(kind: str, target: Mapping[str, Any], verification: Mapping[str, Any], package: Mapping[str, Any]) -> dict[str, Any]:
    digest = target["package_digest" if kind == "package" else "plan_digest" if kind == "plan" else "blueprint_digest"]
    payload = {"result_version": f"finsight_point01_m2_a1_v2_7_{kind}_freeze_gate_v1", "status": verification["status"], "package_ref": package["package_ref"], "package_digest": package["package_digest"], "target_digest": digest, "verification": dict(verification), "execution_counts": {"approval": 0, "admission": 0, "receipt": 0, "ledger": 0, "namespace": 0, "actual": 0, "network": 0, "tool": 0, "model": 0, "provider": 0, "store_write": 0}, "next_step": "independent_review_required_no_active_authority"}
    return {**payload, "gate_digest": canonical_digest(payload)}


def build_artifacts() -> dict[str, dict[str, Any]]:
    package = build_package(); package_gate = _gate("package", package, verify_package(package), package)
    plan = build_plan(package, package_gate); plan_gate = _gate("plan", plan, {"status": "pass", "calculated_plan_digest": canonical_digest({k: v for k, v in plan.items() if k != "plan_digest"})}, package)
    blueprint = build_blueprint(package, package_gate, plan, plan_gate); blueprint_gate = _gate("blueprint", blueprint, {"status": "pass", "calculated_blueprint_digest": canonical_digest({k: v for k, v in blueprint.items() if k != "blueprint_digest"})}, package)
    return {"package": package, "package_gate": package_gate, "plan": plan, "plan_gate": plan_gate, "blueprint": blueprint, "blueprint_gate": blueprint_gate}


def main() -> int:
    artifacts = build_artifacts()
    for name, path in OUTPUTS.items(): _write(path, artifacts[name])
    digests = {
        "package_digest": artifacts["package"]["package_digest"],
        "package_gate_digest": artifacts["package_gate"]["gate_digest"],
        "plan_digest": artifacts["plan"]["plan_digest"],
        "plan_gate_digest": artifacts["plan_gate"]["gate_digest"],
        "blueprint_digest": artifacts["blueprint"]["blueprint_digest"],
        "blueprint_gate_digest": artifacts["blueprint_gate"]["gate_digest"],
    }
    print(json.dumps({"status": "B0_4_repaired_refrozen_pending_independent_review", **digests}, sort_keys=True))
    return 0 if all(artifacts[name]["status"] == "pass" for name in ("package_gate", "plan_gate", "blueprint_gate")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
