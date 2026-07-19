"""Frozen, approval-driven one-shot JIT entry for the v2.6 package.

Without the explicit external HumanJITWindowApproval this entry can only
perform a read-only dry run.  It never manufactures approval, admission,
receipt, or namespace state merely because a package exists.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
PACKAGE_PATH = ROOT / "data/manifests/point01_m2_a1_execution_ready_audit_package_manifest_v2_6.json"
PACKAGE_GATE_PATH = ROOT / "data/manifests/point01_m2_a1_execution_ready_audit_package_freeze_gate_result_v2_6.json"
PLAN_PATH = ROOT / "data/manifests/point01_m2_a1_receipt_execution_plan_v1_3_frozen_jit.json"
PLAN_GATE_PATH = ROOT / "data/manifests/point01_m2_a1_receipt_execution_plan_v1_3_frozen_jit_gate.json"
BLUEPRINT_PATH = ROOT / "data/manifests/point01_m2_a1_baseline_authority_blueprint_v1_3_frozen_jit.json"
BLUEPRINT_GATE_PATH = ROOT / "data/manifests/point01_m2_a1_baseline_authority_blueprint_v1_3_frozen_jit_gate.json"
PARENT = ROOT / "scripts/engineering/run_point01_m2_a1_actual_audit_v2_6.py"
REGISTRAR = ROOT / "scripts/engineering/run_point01_m2_a1_receipt_registrar_v2_6.py"
ORACLE_PATH = ROOT / "configs/engineering_handoff/point01_m2_a1_independent_expected_cell_oracle_v1_1.json"
MATRIX_PATH = ROOT / "configs/engineering_handoff/point01_m2_a1_execution_ready_scenario_matrix_v2_1.json"


def _load(path: Path) -> Mapping[str, Any]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, Mapping):
        raise ValueError("m2_a1_frozen_jit_mapping_required")
    return loaded


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _artifacts() -> tuple[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any], Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]]:
    package, package_gate, plan, plan_gate, blueprint, blueprint_gate = (_load(path) for path in (PACKAGE_PATH, PACKAGE_GATE_PATH, PLAN_PATH, PLAN_GATE_PATH, BLUEPRINT_PATH, BLUEPRINT_GATE_PATH))
    pairs = ((package_gate, "package_digest", package.get("package_digest")), (plan_gate, "target_digest", plan.get("plan_digest")), (blueprint_gate, "target_digest", blueprint.get("blueprint_digest")))
    if any(item.get("status") != "pass" for item, _, _ in pairs) or package_gate.get("package_digest") != package.get("package_digest") or any(item.get(field) != expected for item, field, expected in pairs[1:]):
        raise ValueError("m2_a1_frozen_jit_gate_binding_invalid")
    return package, package_gate, plan, plan_gate, blueprint, blueprint_gate


def _approval_preflight(path: Path) -> tuple[Any, tuple[Mapping[str, Any], ...], Mapping[str, Any]]:
    from sec_agent.canonical_runtime.m2_a1_execution_receipt import HumanJITWindowApproval, M2A1ExecutionPreflightError, preflight_exact_execution, validate_human_jit_window_approval

    approval = HumanJITWindowApproval.model_validate(_load(path))
    artifacts = _artifacts()
    package, package_gate, plan, plan_gate, blueprint, blueprint_gate = artifacts
    check = validate_human_jit_window_approval(approval, package=package, package_gate=package_gate, plan=plan, plan_gate=plan_gate, blueprint=blueprint, blueprint_gate=blueprint_gate)
    if check["status"] != "pass":
        raise ValueError(str(check["status"]))
    # This proves the exact frozen package still rejects before any admission,
    # ledger, directory, or runtime import.  A real execution constructs the
    # admission only after this no-write validation succeeds.
    try:
        preflight_exact_execution(package, None, repository_root=ROOT, receipt_id="jit-dry-run-no-receipt", scenario_id=approval.scenario_id)
    except M2A1ExecutionPreflightError as exc:
        if str(exc) != "package_admission_required":
            raise ValueError(f"m2_a1_frozen_jit_package_preflight_invalid:{exc}") from exc
    else:
        raise ValueError("m2_a1_frozen_jit_missing_admission_unexpected_pass")
    return approval, artifacts, check


def dry_run(approval_path: Path) -> int:
    try:
        approval, artifacts, check = _approval_preflight(approval_path)
    except FileNotFoundError:
        print(json.dumps({"status": "m2_a1_frozen_jit_json_input_unreadable", "new_admission": 0, "new_receipt": 0, "namespace": 0, "runtime": 0, "actual": 0}, sort_keys=True))
        return 2
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": str(exc), "new_admission": 0, "new_receipt": 0, "namespace": 0, "runtime": 0, "actual": 0}, sort_keys=True))
        return 2
    package, package_gate, plan, plan_gate, blueprint, blueprint_gate = artifacts
    print(json.dumps({"status": "human_jit_window_approval_preflight_pass_no_side_effects", "approval_digest": approval.approval_digest, "package_digest": package["package_digest"], "package_gate_digest": package_gate["gate_digest"], "plan_digest": plan["plan_digest"], "plan_gate_digest": plan_gate["gate_digest"], "blueprint_digest": blueprint["blueprint_digest"], "blueprint_gate_digest": blueprint_gate["gate_digest"], "approval_check": check["status"], "new_admission": 0, "new_receipt": 0, "namespace": 0, "runtime": 0, "actual": 0}, sort_keys=True))
    return 0


def _issue_authority(approval: Any, package: Mapping[str, Any]) -> tuple[Any, Any]:
    from sec_agent.canonical_runtime.m2_a1_execution_receipt import M2A1ExecutionReceipt, M2A1ExternalPackageAdmission, V2_6_ADMISSION_SCHEMA, V2_6_RECEIPT_SCHEMA

    current = datetime.now(timezone.utc)
    admission_expiry = min(approval.expires_at, current + timedelta(minutes=approval.admission_ttl_minutes))
    receipt_expiry = min(admission_expiry, current + timedelta(minutes=approval.receipt_ttl_minutes))
    if receipt_expiry <= current:
        raise ValueError("m2_a1_frozen_jit_window_expired_before_issue")
    admission = M2A1ExternalPackageAdmission.create(admission_ref=approval.approval_ref, admission_id=f"{approval.approval_id}:admission:v1", admission_version=1, reviewer_identity=approval.reviewer_identity, package_ref=approval.package_ref, executable_package_digest=approval.package_digest, scope=str(package["scope"]), authority_boundary=approval.authority_boundary, execution_staging_namespace_id=approval.execution_staging_namespace_id, expires_at=admission_expiry, schema_version=V2_6_ADMISSION_SCHEMA)
    nonce_sha256 = hashlib.sha256(secrets.token_bytes(32)).hexdigest()
    receipt_id = f"{approval.approval_id}:receipt:{nonce_sha256[:20]}"
    receipt = M2A1ExecutionReceipt.create(receipt_id=receipt_id, receipt_version=1, approval_id=approval.approval_id, package_ref=approval.package_ref, executable_package_digest=approval.package_digest, scope=str(package["scope"]), admission_digest=admission.admission_digest, nonce_sha256=nonce_sha256, expires_at=receipt_expiry, reviewer_identity=approval.reviewer_identity, execution_staging_namespace_id=approval.execution_staging_namespace_id, scenario_id=approval.scenario_id, schema_version=V2_6_RECEIPT_SCHEMA)
    return admission, receipt


def execute(approval_path: Path) -> int:
    """Future active path; B0.3 tests never call this function."""

    from sec_agent.canonical_runtime.m2_a1_execution_receipt import M2A1ExecutionPreflightError, M2A1ReceiptAuthorityError, M2A1ReceiptLedger, preflight_exact_execution

    try:
        approval, artifacts, _ = _approval_preflight(approval_path)
        package, _package_gate, _plan, _plan_gate, _blueprint, _blueprint_gate = artifacts
        admission, receipt = _issue_authority(approval, package)
        preflight = preflight_exact_execution(package, admission, repository_root=ROOT, receipt_id=receipt.receipt_id, scenario_id=approval.scenario_id)
        preflight.materialize_authority_for_registration()
        admission_path = preflight.authority_root / "admission.json"
        receipt_path = preflight.authority_root / "receipt.json"
        _write(admission_path, admission.model_dump(mode="json")); _write(receipt_path, receipt.model_dump(mode="json"))
        registered = subprocess.run([sys.executable, str(REGISTRAR), "--register-exact-receipt", "--admission", str(admission_path), "--receipt", str(receipt_path), "--scenario-id", approval.scenario_id], cwd=ROOT, capture_output=True, text=True, check=False)
        if registered.returncode != 0:
            raise ValueError("m2_a1_frozen_jit_registration_failed")
        executed = subprocess.run([sys.executable, str(PARENT), "--", "--execute-admitted", "--admission", str(admission_path), "--receipt-id", receipt.receipt_id, "--scenario-id", approval.scenario_id], cwd=ROOT, capture_output=True, text=True, check=False)
        ledger = M2A1ReceiptLedger.open_existing(preflight.ledger_path, approved_authority_root=preflight.authority_root)
        state = ledger.state(receipt.receipt_id)
        if executed.returncode != 0 or state is None or state.get("state") != "consumed_before_run" or not preflight.output_path.is_file():
            ledger.recover_consumed_without_terminal(receipt.receipt_id)
            print(json.dumps({"status": "m2_a1_frozen_jit_outcome_unknown_fail_fast", "receipt_id": receipt.receipt_id, "retry_permitted": False}, sort_keys=True))
            return 1
        terminal_digest = ledger.record_terminal_event(receipt.receipt_id, terminal_status="succeeded", actual_result_digest=hashlib.sha256(preflight.output_path.read_bytes()).hexdigest())
        consumed_receipt = ledger.receipt(receipt.receipt_id)
        if consumed_receipt is None:
            raise ValueError("m2_a1_frozen_jit_consumed_receipt_missing")
        from sec_agent.canonical_runtime.m2_a1_audit_oracle import evaluate_independent_oracle
        from sec_agent.canonical_runtime.m2_a1_audit_result import M2A1ImmutableActualResult
        from sec_agent.canonical_runtime.m2_a1_audit_reviewer_gate import review_future_actual
        actual = M2A1ImmutableActualResult.model_validate(_load(preflight.output_path))
        oracle_doc, matrix_doc = _load(ORACLE_PATH), _load(MATRIX_PATH)
        oracle_case = next(item for item in oracle_doc["oracle_cases"] if item["input_case_ref"] == actual.case_id)
        scenario = next(item for item in matrix_doc["scenarios"] if item["scenario_id"] == approval.scenario_id)
        oracle = evaluate_independent_oracle(actual, oracle_case, scenario)
        reviewer = review_future_actual(package=package, actual_results=(actual,), oracle_evaluations=(oracle,), expected_scenario_ids=(approval.scenario_id,), admission=admission, consumed_receipt=consumed_receipt, receipt_ledger_state=state, receipt_terminal_event_digest=terminal_digest)
        _write(preflight.output_path.parent / "oracle_evaluation.json", oracle.model_dump(mode="json")); _write(preflight.output_path.parent / "reviewer_gate.json", reviewer.model_dump(mode="json"))
        closeout = {"status": "completed_pending_independent_review" if reviewer.status == "pass" else "reviewer_fail_closed_no_retry", "approval_digest": approval.approval_digest, "admission_digest": admission.admission_digest, "receipt_digest": receipt.receipt_digest, "actual_digest": actual.actual_result_digest, "oracle_digest": oracle.evaluation_digest, "reviewer_gate_digest": reviewer.gate_digest, "terminal_digest": terminal_digest, "retry_permitted": False}
        closeout["closeout_digest"] = hashlib.sha256(json.dumps(closeout, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        _write(preflight.output_path.parent / "jit_closeout.json", closeout)
        print(json.dumps(closeout, sort_keys=True))
        return 0 if reviewer.status == "pass" else 1
    except (ValueError, OSError, M2A1ExecutionPreflightError, M2A1ReceiptAuthorityError) as exc:
        print(json.dumps({"status": str(exc), "retry_permitted": False}, sort_keys=True))
        return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Frozen M2-A1 v2.6 JIT entry; an external human approval is mandatory.")
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--dry-run-approved-window", action="store_true")
    modes.add_argument("--execute-approved-window", action="store_true")
    parser.add_argument("--approval", type=Path, required=True)
    args = parser.parse_args(argv)
    return dry_run(args.approval) if args.dry_run_approved_window else execute(args.approval)


if __name__ == "__main__":
    raise SystemExit(main())
