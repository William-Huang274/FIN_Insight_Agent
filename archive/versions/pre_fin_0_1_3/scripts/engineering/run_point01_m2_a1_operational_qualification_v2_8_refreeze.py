"""Refreeze B0.5 operational proof without issuing execution authority."""

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


POLICY = "configs/engineering_handoff/point01_m2_a1_operational_proof_policy_v2_8.json"
OLD_PACKAGE = "data/manifests/point01_m2_a1_execution_ready_audit_package_manifest_v2_7.json"
PACKAGE_REF = "point01-m2-a1-b0-5-operational-proof-package-v2-8"
NAMESPACE_ID = "point01_m2_a1_exact_admitted_runs_v2_8"
NAMESPACE_PATH = "D:/temp/FIN_Insight_Agent/point01_m2_a1_exact_admitted_runs_v2_8"
OUTPUTS = {
    "package": ROOT / "data/manifests/point01_m2_a1_execution_ready_audit_package_manifest_v2_8.json",
    "package_gate": ROOT / "data/manifests/point01_m2_a1_execution_ready_audit_package_freeze_gate_result_v2_8.json",
    "plan": ROOT / "data/manifests/point01_m2_a1_receipt_execution_plan_v1_5_operational_proof.json",
    "plan_gate": ROOT / "data/manifests/point01_m2_a1_receipt_execution_plan_v1_5_operational_proof_gate.json",
    "blueprint": ROOT / "data/manifests/point01_m2_a1_baseline_authority_blueprint_v1_5_operational_proof.json",
    "blueprint_gate": ROOT / "data/manifests/point01_m2_a1_baseline_authority_blueprint_v1_5_operational_proof_gate.json",
}
NEW_INPUTS = {
    POLICY,
    "src/sec_agent/canonical_runtime/m2_a1_execution_receipt.py",
    "src/sec_agent/canonical_runtime/m2_a1_audit_reviewer_gate.py",
    "src/sec_agent/canonical_runtime/m2_a1_v2_8_operational_proof.py",
    "scripts/engineering/run_point01_m2_a1_v2_8_frozen_jit_window.py",
    "scripts/engineering/run_point01_m2_a1_v2_8_synthetic_operational_child.py",
    "scripts/engineering/run_point01_m2_a1_operational_qualification_v2_8_refreeze.py",
    "tests/contract/test_point01_m2_a1_v2_8_operational_proof.py",
}


def _index_bytes(relative_path: str) -> bytes:
    completed = subprocess.run(["git", "show", f":{relative_path}"], cwd=ROOT, capture_output=True, check=False)
    if completed.returncode:
        raise RuntimeError(f"v2_8_missing_staged_input:{relative_path}")
    return completed.stdout


def _from_index(relative_path: str) -> Mapping[str, Any]:
    payload = json.loads(_index_bytes(relative_path).decode("utf-8"))
    if not isinstance(payload, Mapping):
        raise RuntimeError(f"v2_8_mapping_required:{relative_path}")
    return payload


def _sha(relative_path: str) -> str:
    return hashlib.sha256(_index_bytes(relative_path)).hexdigest()


def _write(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _policy_digest() -> str:
    return canonical_digest(_from_index(POLICY))


def build_package() -> dict[str, Any]:
    old = _from_index(OLD_PACKAGE)
    retired = {
        "scripts/engineering/run_point01_m2_a1_v2_7_frozen_jit_window.py",
        "scripts/engineering/run_point01_m2_a1_v2_7_synthetic_terminal_child.py",
        "scripts/engineering/run_point01_m2_a1_operational_qualification_v2_7_refreeze.py",
        "tests/contract/test_point01_m2_a1_v2_7_approval_lineage.py",
    }
    paths = set(old["input_file_sha256"]).difference(retired) | NEW_INPUTS
    hashes = {path: _sha(path) for path in sorted(paths)}
    payload = {
        key: value
        for key, value in old.items()
        if key not in {"schema_version", "package_ref", "package_digest", "input_file_sha256", "execution_preflight", "jit_window_contract", "approval_lineage_contract", "supersedes", "b0_4_policy_digest"}
    }
    payload.update(
        {
            "schema_version": "finsight_point01_m2_a1_execution_ready_audit_package_manifest_v2_8",
            "package_ref": PACKAGE_REF,
            "input_file_sha256": hashes,
            "execution_preflight": {**old["execution_preflight"], "execution_staging_namespace_id": NAMESPACE_ID, "execution_staging_namespace_path": NAMESPACE_PATH},
            "jit_window_contract": {
                "approval_schema_version": "finsight_point01_m2_a1_human_jit_window_approval_v1",
                "approval_required_before_issue": True,
                "orchestrator": {"relative_path": "scripts/engineering/run_point01_m2_a1_v2_8_frozen_jit_window.py", "sha256": hashes["scripts/engineering/run_point01_m2_a1_v2_8_frozen_jit_window.py"]},
                "dry_run": "approval_validate_only_no_admission_receipt_namespace_or_write",
                "execute_sequence": ["verify_approval", "issue_admission", "register", "preflight", "consume", "reverify", "grant", "materialize", "clean_child", "immutable_actual_validated", "independent_oracle", "preterminal_reviewer", "terminal_append"],
                "default_command": "do_not_invoke",
                "active_command": "execute_approved_window_only",
                "supersedes_v2_5_package_digest": "a23dac3931164b4910a6182b97fa37e10d788e893991e4bc1d079e78439ebe6a",
            },
            "approval_lineage_contract": {
                "admission_schema_version": "finsight_point01_m2_a1_external_package_admission_v2_8",
                "receipt_schema_version": "finsight_point01_m2_a1_single_use_execution_receipt_v2_8",
                "human_approval_digest_required": True,
                "ledger_events": ["REGISTERED", "CONSUMED_BEFORE_RUN", "TERMINAL"],
                "terminal_sequence": ["immutable_actual_validated", "independent_oracle", "preterminal_reviewer", "terminal_append"],
                "post_consume_exception_terminal": "outcome_unknown_no_success",
                "supersedes_v2_7_package_digest": "0335e114950db227ac67d8dbb16e554626fec194d8acb8c84d0f29f90ccd1367",
            },
            "operational_proof_contract": {
                "admission_schema_version": "finsight_point01_m2_a1_external_package_admission_v2_8",
                "receipt_schema_version": "finsight_point01_m2_a1_single_use_execution_receipt_v2_8",
                "event_source_of_truth": "point01_m2_a1_execution_receipt_events_append_only_sqlite_triggers",
                "event_payload_digest_reverified_on_read": True,
                "integration_entry": "frozen_dependency_injected_v2_8_execute_core",
                "synthetic_fixture_authority": "synthetic_nonhuman_fixture_only",
                "required_integration_branches": ["happy_path", "corrupted_actual", "reviewer_failure", "post_consume_child_exit"],
                "supersedes_v2_7_package_digest": "0335e114950db227ac67d8dbb16e554626fec194d8acb8c84d0f29f90ccd1367",
            },
            "supersedes": {"v2_7_package_digest": "0335e114950db227ac67d8dbb16e554626fec194d8acb8c84d0f29f90ccd1367", "authority_disposition": "historical_rejected_proof_only_non_replayable"},
            "b0_4_policy_digest": old["b0_4_policy_digest"],
            "b0_5_policy_digest": _policy_digest(),
        }
    )
    return {**payload, "package_digest": canonical_digest(payload)}


def _package_verification(package: Mapping[str, Any]) -> dict[str, Any]:
    from sec_agent.canonical_runtime.m2_a1_execution_receipt import M2A1ExecutionPreflightError, preflight_exact_execution

    failures: list[str] = []
    payload = {key: value for key, value in package.items() if key != "package_digest"}
    if canonical_digest(payload) != package.get("package_digest"):
        failures.append("package_digest_mismatch")
    if any(_sha(path) != digest for path, digest in package["input_file_sha256"].items()):
        failures.append("staged_input_hash_mismatch")
    try:
        preflight_exact_execution(package, None, repository_root=ROOT, receipt_id="v2-8-no-receipt", scenario_id="p01-baseline-separated-input")
    except M2A1ExecutionPreflightError as exc:
        if str(exc) != "package_admission_required":
            failures.append(f"production_validator:{exc}")
    else:
        failures.append("missing_admission_unexpected_pass")
    return {"status": "pass" if not failures else "fail_closed", "package_current_verify": "pass" if not failures else "fail", "failures": failures, "calculated_package_digest": canonical_digest(payload), "input_hash_count": len(package["input_file_sha256"]), "external_call_count": 0, "store_write_count": 0}


def _gate(kind: str, target: Mapping[str, Any], verification: Mapping[str, Any], package: Mapping[str, Any]) -> dict[str, Any]:
    field = {"package": "package_digest", "plan": "plan_digest", "blueprint": "blueprint_digest"}[kind]
    payload = {"result_version": f"finsight_point01_m2_a1_v2_8_{kind}_freeze_gate_v1", "status": verification["status"], "package_ref": package["package_ref"], "package_digest": package["package_digest"], "target_digest": target[field], "verification": dict(verification), "execution_counts": {"approval": 0, "admission": 0, "receipt": 0, "ledger": 0, "namespace": 0, "actual": 0, "network": 0, "tool": 0, "model": 0, "provider": 0, "store_write": 0}, "next_step": "independent_review_required_no_active_authority"}
    return {**payload, "gate_digest": canonical_digest(payload)}


def build_artifacts() -> dict[str, dict[str, Any]]:
    package = build_package()
    package_gate = _gate("package", package, _package_verification(package), package)
    scenario_ids = package["scenario_matrix_summary"]["scenario_ids"]
    plan_payload = {"schema_version": "finsight_point01_m2_a1_receipt_execution_plan_v1_5_operational_proof", "status": "B0.5_repaired_refrozen_pending_independent_review", "exact_package": {"package_ref": PACKAGE_REF, "package_digest": package["package_digest"], "package_gate_digest": package_gate["gate_digest"], "scope": package["scope"], "authority_boundary": package["authority_boundary"], "execution_staging_namespace_id": NAMESPACE_ID}, "supersedes": {"v2_7_package_digest": "0335e114950db227ac67d8dbb16e554626fec194d8acb8c84d0f29f90ccd1367", "execution_authority": "none"}, "scenario_execution_order": [{"sequence": index, "scenario_id": value, "future_authority": "independent_human_approval_admission_receipt_JIT_only", "on_failure": "fail_fast_no_retry_no_replay"} for index, value in enumerate(scenario_ids, 1)], "group_counts": {"P01": 4, "P02": 6, "P03": 6}, "execution_counts": {"approval": 0, "admission": 0, "receipt": 0, "ledger": 0, "namespace": 0, "actual": 0, "external": 0, "store_write": 0}}
    plan = {**plan_payload, "plan_digest": canonical_digest(plan_payload)}
    plan_gate = _gate("plan", plan, {"status": "pass", "calculated_plan_digest": canonical_digest(plan_payload), "scenario_count": len(scenario_ids)}, package)
    blueprint_payload = {"schema_version": "finsight_point01_m2_a1_baseline_authority_blueprint_v1_5_operational_proof", "status": "B0.5_repaired_refrozen_pending_independent_review", "exact_binding": {"package_digest": package["package_digest"], "package_gate_digest": package_gate["gate_digest"], "plan_digest": plan["plan_digest"], "plan_gate_digest": plan_gate["gate_digest"], "b0_5_policy_digest": package["b0_5_policy_digest"], "scenario_id": "p01-baseline-separated-input", "authority_boundary": package["authority_boundary"], "execution_staging_namespace_id": NAMESPACE_ID}, "templates": {"human_jit_window_approval": "unresolved_not_active", "v2_8_admission": "unresolved_not_active", "v2_8_receipt": "unresolved_not_active"}, "all_other_scenarios": {"count": 15, "authority_issue_forbidden": True}, "command_contracts": {"orchestrator": "do_not_invoke", "registrar": "do_not_invoke", "executor": "do_not_invoke"}, "execution_counts": {"approval": 0, "admission": 0, "receipt": 0, "ledger": 0, "namespace": 0, "actual": 0, "external": 0, "store_write": 0}}
    blueprint = {**blueprint_payload, "blueprint_digest": canonical_digest(blueprint_payload)}
    blueprint_gate = _gate("blueprint", blueprint, {"status": "pass", "calculated_blueprint_digest": canonical_digest(blueprint_payload)}, package)
    return {"package": package, "package_gate": package_gate, "plan": plan, "plan_gate": plan_gate, "blueprint": blueprint, "blueprint_gate": blueprint_gate}


def main() -> int:
    artifacts = build_artifacts()
    for name, path in OUTPUTS.items():
        _write(path, artifacts[name])
    print(json.dumps({
        "status": "B0.5_repaired_refrozen_pending_independent_review",
        "package_digest": artifacts["package"]["package_digest"],
        "package_gate_digest": artifacts["package_gate"]["gate_digest"],
        "plan_digest": artifacts["plan"]["plan_digest"],
        "plan_gate_digest": artifacts["plan_gate"]["gate_digest"],
        "blueprint_digest": artifacts["blueprint"]["blueprint_digest"],
        "blueprint_gate_digest": artifacts["blueprint_gate"]["gate_digest"],
    }, sort_keys=True))
    return 0 if all(artifacts[name]["status"] == "pass" for name in ("package_gate", "plan_gate", "blueprint_gate")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
