"""Frozen v2.7 JIT entry with durable human-approval lineage.

This entry is default-deny.  It only performs execution after a package-external
human approval is supplied.  The v2.7 order deliberately validates the
immutable actual and independent adjudication before appending any success
terminal event.
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
sys.path.insert(0, str(ROOT / "src"))
PACKAGE_PATH = ROOT / "data/manifests/point01_m2_a1_execution_ready_audit_package_manifest_v2_7.json"
PACKAGE_GATE_PATH = ROOT / "data/manifests/point01_m2_a1_execution_ready_audit_package_freeze_gate_result_v2_7.json"
PLAN_PATH = ROOT / "data/manifests/point01_m2_a1_receipt_execution_plan_v1_4_approval_lineage.json"
PLAN_GATE_PATH = ROOT / "data/manifests/point01_m2_a1_receipt_execution_plan_v1_4_approval_lineage_gate.json"
BLUEPRINT_PATH = ROOT / "data/manifests/point01_m2_a1_baseline_authority_blueprint_v1_4_approval_lineage.json"
BLUEPRINT_GATE_PATH = ROOT / "data/manifests/point01_m2_a1_baseline_authority_blueprint_v1_4_approval_lineage_gate.json"
PARENT = ROOT / "scripts/engineering/run_point01_m2_a1_actual_audit_v2_7.py"
REGISTRAR = ROOT / "scripts/engineering/run_point01_m2_a1_receipt_registrar_v2_7.py"
ORACLE_PATH = ROOT / "configs/engineering_handoff/point01_m2_a1_independent_expected_cell_oracle_v1_1.json"
MATRIX_PATH = ROOT / "configs/engineering_handoff/point01_m2_a1_execution_ready_scenario_matrix_v2_1.json"


def _load(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError("m2_a1_v2_7_mapping_required")
    return value


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _artifacts() -> tuple[Mapping[str, Any], ...]:
    artifacts = tuple(_load(path) for path in (PACKAGE_PATH, PACKAGE_GATE_PATH, PLAN_PATH, PLAN_GATE_PATH, BLUEPRINT_PATH, BLUEPRINT_GATE_PATH))
    package, package_gate, plan, plan_gate, blueprint, blueprint_gate = artifacts
    if package_gate.get("status") != "pass" or plan_gate.get("status") != "pass" or blueprint_gate.get("status") != "pass":
        raise ValueError("m2_a1_v2_7_gate_not_pass")
    if package_gate.get("package_digest") != package.get("package_digest") or plan_gate.get("target_digest") != plan.get("plan_digest") or blueprint_gate.get("target_digest") != blueprint.get("blueprint_digest"):
        raise ValueError("m2_a1_v2_7_cross_gate_binding_invalid")
    return artifacts


def _approval_preflight(path: Path) -> tuple[Any, tuple[Mapping[str, Any], ...]]:
    from sec_agent.canonical_runtime.m2_a1_execution_receipt import HumanJITWindowApproval, M2A1ExecutionPreflightError, preflight_exact_execution, validate_human_jit_window_approval

    approval = HumanJITWindowApproval.model_validate(_load(path))
    artifacts = _artifacts()
    package, package_gate, plan, plan_gate, blueprint, blueprint_gate = artifacts
    check = validate_human_jit_window_approval(approval, package=package, package_gate=package_gate, plan=plan, plan_gate=plan_gate, blueprint=blueprint, blueprint_gate=blueprint_gate)
    if check["status"] != "pass":
        raise ValueError(str(check["status"]))
    try:
        preflight_exact_execution(package, None, repository_root=ROOT, receipt_id="v2-7-dry-run-no-receipt", scenario_id=approval.scenario_id, human_approval_digest=approval.approval_digest)
    except M2A1ExecutionPreflightError as exc:
        if str(exc) != "package_admission_required":
            raise ValueError(f"m2_a1_v2_7_package_preflight_invalid:{exc}") from exc
    else:
        raise ValueError("m2_a1_v2_7_missing_admission_unexpected_pass")
    return approval, artifacts


def dry_run(approval_path: Path) -> int:
    try:
        approval, artifacts = _approval_preflight(approval_path)
    except (ValueError, OSError, json.JSONDecodeError):
        print(json.dumps({"status": "m2_a1_v2_7_approval_preflight_fail_closed", "new_admission": 0, "new_receipt": 0, "namespace": 0, "runtime": 0, "actual": 0}, sort_keys=True))
        return 2
    package, package_gate, plan, plan_gate, blueprint, blueprint_gate = artifacts
    print(json.dumps({"status": "m2_a1_v2_7_approval_preflight_pass_no_side_effects", "approval_digest": approval.approval_digest, "package_digest": package["package_digest"], "package_gate_digest": package_gate["gate_digest"], "plan_digest": plan["plan_digest"], "plan_gate_digest": plan_gate["gate_digest"], "blueprint_digest": blueprint["blueprint_digest"], "blueprint_gate_digest": blueprint_gate["gate_digest"], "new_admission": 0, "new_receipt": 0, "namespace": 0, "runtime": 0, "actual": 0}, sort_keys=True))
    return 0


def _issue_authority(approval: Any, package: Mapping[str, Any]) -> tuple[Any, Any]:
    from sec_agent.canonical_runtime.m2_a1_execution_receipt import M2A1ExecutionReceipt, M2A1ExternalPackageAdmission, V2_7_ADMISSION_SCHEMA, V2_7_RECEIPT_SCHEMA

    current = datetime.now(timezone.utc)
    admission_expiry = min(approval.expires_at, current + timedelta(minutes=approval.admission_ttl_minutes))
    receipt_expiry = min(admission_expiry, current + timedelta(minutes=approval.receipt_ttl_minutes))
    if receipt_expiry <= current:
        raise ValueError("m2_a1_v2_7_expired_before_issue")
    admission = M2A1ExternalPackageAdmission.create(admission_ref=approval.approval_ref, admission_id=f"{approval.approval_id}:admission:v1", admission_version=1, reviewer_identity=approval.reviewer_identity, package_ref=approval.package_ref, executable_package_digest=approval.package_digest, scope=str(package["scope"]), authority_boundary=approval.authority_boundary, execution_staging_namespace_id=approval.execution_staging_namespace_id, expires_at=admission_expiry, schema_version=V2_7_ADMISSION_SCHEMA, human_approval_digest=approval.approval_digest)
    nonce_sha256 = hashlib.sha256(secrets.token_bytes(32)).hexdigest()
    receipt = M2A1ExecutionReceipt.create(receipt_id=f"{approval.approval_id}:receipt:{nonce_sha256[:20]}", receipt_version=1, approval_id=approval.approval_id, package_ref=approval.package_ref, executable_package_digest=approval.package_digest, scope=str(package["scope"]), admission_digest=admission.admission_digest, nonce_sha256=nonce_sha256, expires_at=receipt_expiry, reviewer_identity=approval.reviewer_identity, execution_staging_namespace_id=approval.execution_staging_namespace_id, scenario_id=approval.scenario_id, schema_version=V2_7_RECEIPT_SCHEMA, human_approval_digest=approval.approval_digest)
    return admission, receipt


def execute(approval_path: Path) -> int:
    from sec_agent.canonical_runtime.m2_a1_execution_receipt import M2A1ExecutionPreflightError, M2A1ReceiptAuthorityError, M2A1ReceiptLedger, preflight_exact_execution
    try:
        approval, artifacts = _approval_preflight(approval_path)
        package, _package_gate, _plan, _plan_gate, _blueprint, _blueprint_gate = artifacts
        admission, receipt = _issue_authority(approval, package)
        preflight = preflight_exact_execution(package, admission, repository_root=ROOT, receipt_id=receipt.receipt_id, scenario_id=approval.scenario_id, human_approval_digest=approval.approval_digest)
        preflight.materialize_authority_for_registration()
        admission_path, receipt_path = preflight.authority_root / "admission.json", preflight.authority_root / "receipt.json"
        _write(admission_path, admission.model_dump(mode="json")); _write(receipt_path, receipt.model_dump(mode="json"))
        registered = subprocess.run([sys.executable, str(REGISTRAR), "--register-exact-receipt", "--admission", str(admission_path), "--receipt", str(receipt_path), "--scenario-id", approval.scenario_id, "--human-approval-digest", approval.approval_digest], cwd=ROOT, capture_output=True, text=True, check=False)
        if registered.returncode != 0:
            raise ValueError("m2_a1_v2_7_registration_failed")
        executed = subprocess.run([sys.executable, str(PARENT), "--", "--execute-admitted", "--admission", str(admission_path), "--receipt-id", receipt.receipt_id, "--scenario-id", approval.scenario_id, "--human-approval-digest", approval.approval_digest], cwd=ROOT, capture_output=True, text=True, check=False)
        ledger = M2A1ReceiptLedger.open_existing(preflight.ledger_path, approved_authority_root=preflight.authority_root)
        state = ledger.state(receipt.receipt_id)
        if executed.returncode != 0 or state is None or state.get("state") != "consumed_before_run" or not preflight.output_path.is_file():
            ledger.recover_consumed_without_terminal(receipt.receipt_id)
            return 1
        from sec_agent.canonical_runtime.m2_a1_audit_oracle import evaluate_independent_oracle
        from sec_agent.canonical_runtime.m2_a1_audit_result import M2A1ImmutableActualResult
        from sec_agent.canonical_runtime.m2_a1_audit_reviewer_gate import review_future_actual
        actual = M2A1ImmutableActualResult.model_validate(_load(preflight.output_path))
        if not actual.verify_immutable_digest() or actual.executable_package_digest != package["package_digest"] or actual.scenario_id != approval.scenario_id or actual.admission_digest != admission.admission_digest or actual.consumed_receipt_digest != state.get("receipt_digest"):
            ledger.recover_consumed_without_terminal(receipt.receipt_id)
            return 1
        counts = actual.canary_snapshot.get("counts") if isinstance(actual.canary_snapshot, Mapping) else None
        if not isinstance(counts, Mapping) or any(int(counts.get(key, 0)) != 0 for key in ("network_request_success_count", "store_write_open_count", "model_constructor_success_count", "tool_transport_success_count")):
            ledger.recover_consumed_without_terminal(receipt.receipt_id)
            return 1
        consumed = ledger.receipt(receipt.receipt_id)
        if consumed is None:
            raise ValueError("m2_a1_v2_7_consumed_receipt_missing")
        oracle_doc, matrix_doc = _load(ORACLE_PATH), _load(MATRIX_PATH)
        oracle_case = next(item for item in oracle_doc["oracle_cases"] if item["input_case_ref"] == actual.case_id)
        scenario = next(item for item in matrix_doc["scenarios"] if item["scenario_id"] == approval.scenario_id)
        oracle = evaluate_independent_oracle(actual, oracle_case, scenario)
        reviewer = review_future_actual(package=package, actual_results=(actual,), oracle_evaluations=(oracle,), expected_scenario_ids=(approval.scenario_id,), admission=admission, consumed_receipt=consumed, receipt_ledger_state=state, receipt_terminal_event_digest=None, require_terminal_event=False)
        if reviewer.status != "pass":
            ledger.recover_consumed_without_terminal(receipt.receipt_id)
            return 1
        terminal = ledger.record_terminal_event(receipt.receipt_id, terminal_status="succeeded" if actual.actual_status == "succeeded" else "typed_stop", actual_result_digest=actual.actual_result_digest, oracle_evaluation_digest=oracle.evaluation_digest, reviewer_gate_digest=reviewer.gate_digest, expected_human_approval_digest=approval.approval_digest)
        _write(preflight.output_path.parent / "oracle_evaluation.json", oracle.model_dump(mode="json")); _write(preflight.output_path.parent / "reviewer_gate.json", reviewer.model_dump(mode="json"))
        closeout = {"status": "completed_pending_independent_review", "approval_digest": approval.approval_digest, "admission_digest": admission.admission_digest, "receipt_digest": receipt.receipt_digest, "actual_digest": actual.actual_result_digest, "oracle_digest": oracle.evaluation_digest, "reviewer_gate_digest": reviewer.gate_digest, "terminal_digest": terminal, "retry_permitted": False}
        closeout["closeout_digest"] = hashlib.sha256(json.dumps(closeout, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        _write(preflight.output_path.parent / "jit_closeout.json", closeout)
        print(json.dumps(closeout, sort_keys=True))
        return 0
    except (ValueError, OSError, M2A1ExecutionPreflightError, M2A1ReceiptAuthorityError):
        return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Frozen M2-A1 v2.7 JIT entry; approval lineage is mandatory.")
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--dry-run-approved-window", action="store_true")
    modes.add_argument("--execute-approved-window", action="store_true")
    parser.add_argument("--approval", type=Path, required=True)
    args = parser.parse_args(argv)
    return dry_run(args.approval) if args.dry_run_approved_window else execute(args.approval)


if __name__ == "__main__":
    raise SystemExit(main())
