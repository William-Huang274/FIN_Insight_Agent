"""v2.10 default-deny production JIT entry.

The entry validates a package-external reviewer receipt and then delegates to
the one package-bound lifecycle kernel.  It deliberately contains no callback
or alternate production lifecycle.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
PACKAGE_PATH = ROOT / "data/manifests/point01_m2_a1_execution_ready_audit_package_manifest_v2_10.json"
PACKAGE_GATE_PATH = ROOT / "data/manifests/point01_m2_a1_execution_ready_audit_package_freeze_gate_result_v2_10.json"
PLAN_PATH = ROOT / "data/manifests/point01_m2_a1_receipt_execution_plan_v1_7_execution_proof.json"
PLAN_GATE_PATH = ROOT / "data/manifests/point01_m2_a1_receipt_execution_plan_v1_7_execution_proof_gate.json"
BLUEPRINT_PATH = ROOT / "data/manifests/point01_m2_a1_baseline_authority_blueprint_v1_7_execution_proof.json"
BLUEPRINT_GATE_PATH = ROOT / "data/manifests/point01_m2_a1_baseline_authority_blueprint_v1_7_execution_proof_gate.json"
PARENT = ROOT / "scripts/engineering/run_point01_m2_a1_actual_audit_v2_10.py"
ORACLE_PATH = ROOT / "configs/engineering_handoff/point01_m2_a1_independent_expected_cell_oracle_v1_1.json"
MATRIX_PATH = ROOT / "configs/engineering_handoff/point01_m2_a1_execution_ready_scenario_matrix_v2_1.json"


def _load(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError("m2_a1_v2_10_mapping_required")
    return value


def _write_verified(path: Path, value: Mapping[str, Any], *, digest_field: str, digest: str) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if _load(path).get(digest_field) != digest:
        raise OSError(f"m2_a1_v2_10_artifact_readback_failed:{path.name}")


def _artifacts() -> tuple[Mapping[str, Any], ...]:
    package, package_gate, plan, plan_gate, blueprint, blueprint_gate = tuple(_load(path) for path in (PACKAGE_PATH, PACKAGE_GATE_PATH, PLAN_PATH, PLAN_GATE_PATH, BLUEPRINT_PATH, BLUEPRINT_GATE_PATH))
    if package_gate.get("status") != "pass" or plan_gate.get("status") != "pass" or blueprint_gate.get("status") != "pass":
        raise ValueError("m2_a1_v2_10_gate_not_pass")
    if package_gate.get("package_digest") != package.get("package_digest") or plan_gate.get("target_digest") != plan.get("plan_digest") or blueprint_gate.get("target_digest") != blueprint.get("blueprint_digest"):
        raise ValueError("m2_a1_v2_10_cross_gate_binding_invalid")
    return package, package_gate, plan, plan_gate, blueprint, blueprint_gate


def _approval_preflight(path: Path, reviewer_receipt_path: Path) -> tuple[Any, Any, tuple[Mapping[str, Any], ...]]:
    from sec_agent.canonical_runtime.m2_a1_execution_receipt import (
        M2A1ExecutionPreflightError,
        ProductionHumanJITWindowApprovalV2_10,
        ProductionReviewerDecisionReceiptV2_10,
        preflight_exact_execution,
        validate_production_human_jit_window_approval_v2_10,
    )

    raw = _load(path)
    if raw.get("schema_version") != "finsight_point01_m2_a1_production_human_jit_window_approval_v2_10" or raw.get("authority_class") != "production_human_total_reviewer":
        raise ValueError("m2_a1_v2_10_nonproduction_authority_rejected")
    approval = ProductionHumanJITWindowApprovalV2_10.model_validate(raw)
    reviewer_receipt = ProductionReviewerDecisionReceiptV2_10.model_validate(_load(reviewer_receipt_path))
    artifacts = _artifacts()
    package, package_gate, plan, plan_gate, blueprint, blueprint_gate = artifacts
    context, check = validate_production_human_jit_window_approval_v2_10(approval, reviewer_receipt=reviewer_receipt, package=package, package_gate=package_gate, plan=plan, plan_gate=plan_gate, blueprint=blueprint, blueprint_gate=blueprint_gate)
    if context is None or check["status"] != "pass":
        raise ValueError(str(check["status"]))
    try:
        preflight_exact_execution(package, None, repository_root=ROOT, receipt_id="v2-10-dry-run-no-receipt", scenario_id=approval.scenario_id, human_approval_digest=approval.approval_digest)
    except M2A1ExecutionPreflightError as exc:
        if str(exc) != "package_admission_required":
            raise ValueError(f"m2_a1_v2_10_package_preflight_invalid:{exc}") from exc
    else:
        raise ValueError("m2_a1_v2_10_missing_admission_unexpected_pass")
    return approval, context, artifacts


def dry_run(approval_path: Path, reviewer_receipt_path: Path) -> int:
    try:
        approval, _context, artifacts = _approval_preflight(approval_path, reviewer_receipt_path)
    except (ValueError, OSError, json.JSONDecodeError):
        print(json.dumps({"status": "m2_a1_v2_10_approval_preflight_fail_closed", "new_admission": 0, "new_receipt": 0, "namespace": 0, "runtime": 0, "actual": 0}, sort_keys=True))
        return 2
    package, package_gate, plan, plan_gate, blueprint, blueprint_gate = artifacts
    print(json.dumps({"status": "m2_a1_v2_10_production_human_approval_preflight_pass_no_side_effects", "approval_digest": approval.approval_digest, "package_digest": package["package_digest"], "package_gate_digest": package_gate["gate_digest"], "plan_digest": plan["plan_digest"], "plan_gate_digest": plan_gate["gate_digest"], "blueprint_digest": blueprint["blueprint_digest"], "blueprint_gate_digest": blueprint_gate["gate_digest"], "new_admission": 0, "new_receipt": 0, "namespace": 0, "runtime": 0, "actual": 0}, sort_keys=True))
    return 0


def _issue_authority(approval: Any, package: Mapping[str, Any]) -> tuple[Any, Any]:
    from sec_agent.canonical_runtime.m2_a1_execution_receipt import M2A1ExecutionReceipt, M2A1ExternalPackageAdmission, V2_10_ADMISSION_SCHEMA, V2_10_RECEIPT_SCHEMA

    current = datetime.now(timezone.utc)
    admission_expiry = min(approval.expires_at, current + timedelta(minutes=approval.admission_ttl_minutes))
    receipt_expiry = min(admission_expiry, current + timedelta(minutes=approval.receipt_ttl_minutes))
    if receipt_expiry <= current:
        raise ValueError("m2_a1_v2_10_expired_before_issue")
    admission = M2A1ExternalPackageAdmission.create(admission_ref=approval.approval_ref, admission_id=f"{approval.approval_id}:admission:v1", admission_version=1, reviewer_identity=approval.reviewer_identity, package_ref=approval.package_ref, executable_package_digest=approval.package_digest, scope=str(package["scope"]), authority_boundary=approval.authority_boundary, execution_staging_namespace_id=approval.execution_staging_namespace_id, expires_at=admission_expiry, schema_version=V2_10_ADMISSION_SCHEMA, human_approval_digest=approval.approval_digest)
    nonce_sha256 = hashlib.sha256(secrets.token_bytes(32)).hexdigest()
    receipt = M2A1ExecutionReceipt.create(receipt_id=f"{approval.approval_id}:receipt:{nonce_sha256[:20]}", receipt_version=1, approval_id=approval.approval_id, package_ref=approval.package_ref, executable_package_digest=approval.package_digest, scope=str(package["scope"]), admission_digest=admission.admission_digest, nonce_sha256=nonce_sha256, expires_at=receipt_expiry, reviewer_identity=approval.reviewer_identity, execution_staging_namespace_id=approval.execution_staging_namespace_id, scenario_id=approval.scenario_id, schema_version=V2_10_RECEIPT_SCHEMA, human_approval_digest=approval.approval_digest)
    return admission, receipt


def execute(approval_path: Path, reviewer_receipt_path: Path) -> int:
    try:
        approval, context, artifacts = _approval_preflight(approval_path, reviewer_receipt_path)
        from sec_agent.canonical_runtime.m2_a1_execution_receipt import preflight_exact_execution
        from sec_agent.canonical_runtime.m2_a1_v2_10_execution_proof import execute_approved_window_kernel, make_production_v2_10_adapter

        package, _package_gate, _plan, _plan_gate, _blueprint, _blueprint_gate = artifacts
        admission, receipt = _issue_authority(approval, package)
        preflight = preflight_exact_execution(package, admission, repository_root=ROOT, receipt_id=receipt.receipt_id, scenario_id=approval.scenario_id, human_approval_digest=approval.approval_digest)
        oracle_doc, matrix_doc = _load(ORACLE_PATH), _load(MATRIX_PATH)
        oracle_case = next(item for item in oracle_doc["oracle_cases"] if item["input_case_ref"] == approval.input_ref)
        scenario = next(item for item in matrix_doc["scenarios"] if item["scenario_id"] == approval.scenario_id)
        result = execute_approved_window_kernel(adapter=make_production_v2_10_adapter(authority_context=context, package=package, admission=admission, receipt=receipt, preflight=preflight, oracle_case=oracle_case, scenario=scenario, parent=PARENT))
        if result.state != "succeeded":
            return 2
        closeout = {"status": "completed_pending_independent_review", "approval_digest": approval.approval_digest, "admission_digest": result.admission.admission_digest, "receipt_digest": result.receipt.receipt_digest, "actual_digest": result.actual.actual_result_digest if result.actual else None, "oracle_digest": result.oracle.evaluation_digest if result.oracle else None, "reviewer_gate_digest": result.reviewer.gate_digest if result.reviewer else None, "terminal_digest": result.terminal_digest, "retry_permitted": False}
        closeout["closeout_digest"] = hashlib.sha256(json.dumps(closeout, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        _write_verified(preflight.output_path.parent / "jit_closeout.json", closeout, digest_field="closeout_digest", digest=closeout["closeout_digest"])
        print(json.dumps(closeout, sort_keys=True))
        return 0
    except (ValueError, OSError, json.JSONDecodeError):
        return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Frozen M2-A1 v2.10 JIT entry; exact provenance-bound human approval is mandatory.")
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--dry-run-approved-window", action="store_true")
    modes.add_argument("--execute-approved-window", action="store_true")
    parser.add_argument("--approval", type=Path, required=True)
    parser.add_argument("--reviewer-decision-receipt", type=Path, required=True)
    args = parser.parse_args(argv)
    return dry_run(args.approval, args.reviewer_decision_receipt) if args.dry_run_approved_window else execute(args.approval, args.reviewer_decision_receipt)


if __name__ == "__main__":
    raise SystemExit(main())
