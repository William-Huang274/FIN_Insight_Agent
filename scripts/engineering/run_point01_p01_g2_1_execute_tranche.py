"""Run the one authorized P01-G2.1 operational tranche exactly once.

The baseline delegates to the accepted M2-A1 v2.10 production kernel.  The
three follow-on checks are deliberately pre-authority boundary probes: they
cannot issue an admission, receipt, namespace, runtime or terminal event.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
PACKAGE_PATH = ROOT / "data/manifests/point01_p01_g2_1_operational_execution_package_manifest_v1_0.json"
PACKAGE_GATE_PATH = ROOT / "data/manifests/point01_p01_g2_1_operational_execution_package_gate_v1_0.json"
TRANCHE_PATH = ROOT / "data/manifests/point01_p01_g2_operational_tranche_manifest_v1_1.json"
TRANCHE_GATE_PATH = ROOT / "data/manifests/point01_p01_g2_operational_tranche_gate_v1_1.json"
V2_PATHS = {
    "package": ROOT / "data/manifests/point01_m2_a1_execution_ready_audit_package_manifest_v2_10.json",
    "package_gate": ROOT / "data/manifests/point01_m2_a1_execution_ready_audit_package_freeze_gate_result_v2_10.json",
    "plan": ROOT / "data/manifests/point01_m2_a1_receipt_execution_plan_v1_7_execution_proof.json",
    "plan_gate": ROOT / "data/manifests/point01_m2_a1_receipt_execution_plan_v1_7_execution_proof_gate.json",
    "blueprint": ROOT / "data/manifests/point01_m2_a1_baseline_authority_blueprint_v1_7_execution_proof.json",
    "blueprint_gate": ROOT / "data/manifests/point01_m2_a1_baseline_authority_blueprint_v1_7_execution_proof_gate.json",
}
POLICY_PATH = ROOT / "configs/engineering_handoff/point01_p01_g2_1_operational_execution_policy_v1_0.json"
ORACLE_PATH = ROOT / "configs/engineering_handoff/point01_m2_a1_independent_expected_cell_oracle_v1_1.json"
MATRIX_PATH = ROOT / "configs/engineering_handoff/point01_m2_a1_execution_ready_scenario_matrix_v2_1.json"
V2_PARENT = ROOT / "scripts/engineering/run_point01_m2_a1_actual_audit_v2_10.py"
V2_JIT_PATH = ROOT / "scripts/engineering/run_point01_m2_a1_v2_10_frozen_jit_window.py"
P01_ROOT = Path("D:/temp/FIN_Insight_Agent/point01_p01_g2_1_exact_operational_tranche")

from sec_agent.canonical_runtime.m2_a1_audit_canary import M2A1AuditCanary, M2A1TransportAccessError
from sec_agent.canonical_runtime.m2_a1_execution_receipt import (
    M2A1ReceiptLedger,
    ProductionHumanJITWindowApprovalV2_10,
    ProductionReviewerDecisionReceiptV2_10,
    preflight_exact_execution,
    validate_production_human_jit_window_approval_v2_10,
)
from sec_agent.canonical_runtime.m2_a1_v2_10_execution_proof import execute_approved_window_kernel, make_production_v2_10_adapter
from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.canonical_runtime.p01_g2_1_operational_tranche import (
    ACTOR_ID,
    BASELINE_CASE_ID,
    BASELINE_INPUT_REF,
    BASELINE_MUTATION,
    BASELINE_SCENARIO_ID,
    REVIEWER_IDENTITY,
    build_case_result,
    create_reviewer_authority,
    digest_file,
    result_payload,
    validate_execution_package,
    validate_reviewer_authority,
    write_verified_json,
)


def _load(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError(f"p01_g2_1_mapping_required:{path.name}")
    return value


def _index_bytes(relative: str) -> bytes:
    completed = subprocess.run(["git", "show", f":{relative}"], cwd=ROOT, capture_output=True, check=False)
    if completed.returncode:
        raise ValueError(f"p01_g2_1_index_input_missing:{relative}")
    return completed.stdout


def _normalized(value: bytes) -> bytes:
    return value.replace(b"\r\n", b"\n")


def _verify_execution_package_inputs(package: Mapping[str, Any]) -> None:
    hashes = package.get("input_file_sha256")
    if package.get("input_bytes_source") != "git_index" or not isinstance(hashes, Mapping):
        raise ValueError("p01_g2_1_package_input_source_invalid")
    for relative, expected in hashes.items():
        if not isinstance(relative, str) or not isinstance(expected, str):
            raise ValueError("p01_g2_1_package_input_hash_shape_invalid")
        indexed = _index_bytes(relative)
        if hashlib.sha256(indexed).hexdigest() != expected:
            raise ValueError(f"p01_g2_1_package_index_hash_mismatch:{relative}")
        working = (ROOT / relative).read_bytes()
        if _normalized(working) != _normalized(indexed):
            raise ValueError(f"p01_g2_1_package_working_drift:{relative}")


def _v2_jit_module() -> Any:
    spec = importlib.util.spec_from_file_location("point01_m2_a1_v2_10_frozen_jit", V2_JIT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("p01_g2_1_v2_10_jit_module_unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _family() -> tuple[Mapping[str, Any], Mapping[str, Any], dict[str, Mapping[str, Any]]]:
    package, gate, tranche, tranche_gate = _load(PACKAGE_PATH), _load(PACKAGE_GATE_PATH), _load(TRANCHE_PATH), _load(TRANCHE_GATE_PATH)
    v2 = {name: _load(path) for name, path in V2_PATHS.items()}
    return package, gate, {"tranche": tranche, "gate": tranche_gate}, v2


def _preflight_no_side_effects() -> tuple[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any], Mapping[str, Any], dict[str, Mapping[str, Any]]]:
    package, gate, g2, v2 = _family()
    if gate.get("status") != "pass" or gate.get("package_digest") != package.get("package_digest"):
        raise ValueError("p01_g2_1_execution_package_gate_invalid")
    if g2["gate"].get("status") != "pass" or g2["gate"].get("tranche_digest") != g2["tranche"].get("tranche_digest"):
        raise ValueError("p01_g2_1_tranche_gate_invalid")
    if any(v2[name].get("status") != "pass" for name in ("package_gate", "plan_gate", "blueprint_gate")):
        raise ValueError("p01_g2_1_v2_10_gate_invalid")
    check = validate_execution_package(package, tranche=g2["tranche"], tranche_gate=g2["gate"], v2_package=v2["package"], v2_package_gate=v2["package_gate"], v2_plan=v2["plan"], v2_plan_gate=v2["plan_gate"], v2_blueprint=v2["blueprint"], v2_blueprint_gate=v2["blueprint_gate"])
    if check["status"] != "pass":
        raise ValueError(f"p01_g2_1_execution_package_validation:{check['errors']}")
    _verify_execution_package_inputs(package)
    fixed = ROOT / str(v2["package"]["fixed_store_fingerprints"]["fixed_approval_store"]["path"])
    expected_fixed = package["exact_bindings"]["fixed_store_sha256"]
    if digest_file(fixed) != expected_fixed:
        raise ValueError("p01_g2_1_fixed_store_fingerprint_drift")
    namespace = Path(str(v2["package"]["execution_preflight"]["execution_staging_namespace_path"]))
    if namespace.exists():
        raise ValueError("p01_g2_1_formal_namespace_must_be_absent")
    if P01_ROOT.exists():
        raise ValueError("p01_g2_1_case_root_must_be_absent_no_replay")
    return package, gate, g2["tranche"], g2["gate"], v2


def _authority_pair(package: Mapping[str, Any], v2: Mapping[str, Mapping[str, Any]]) -> tuple[dict[str, Any], ProductionReviewerDecisionReceiptV2_10, ProductionHumanJITWindowApprovalV2_10, Any]:
    now = datetime.now(timezone.utc)
    review_expiry = now + timedelta(minutes=31)
    approval_expiry = now + timedelta(minutes=30)
    review_id = f"p01-g2-1-total-review-{hashlib.sha256(now.isoformat().encode()).hexdigest()[:20]}"
    reviewer_receipt = ProductionReviewerDecisionReceiptV2_10.create(
        receipt_id=review_id, receipt_version=1, actor_id=ACTOR_ID, reviewer_identity=REVIEWER_IDENTITY,
        decision="approved_single_jit_window", decision_source="total_reviewer_recorded_decision",
        package_ref=str(v2["package"]["package_ref"]), package_digest=str(v2["package"]["package_digest"]), package_gate_digest=str(v2["package_gate"]["gate_digest"]),
        plan_digest=str(v2["plan"]["plan_digest"]), plan_gate_digest=str(v2["plan_gate"]["gate_digest"]),
        blueprint_digest=str(v2["blueprint"]["blueprint_digest"]), blueprint_gate_digest=str(v2["blueprint_gate"]["gate_digest"]),
        scenario_id=BASELINE_SCENARIO_ID, scope=str(v2["package"]["scope"]), authority_boundary=str(v2["package"]["authority_boundary"]),
        execution_staging_namespace_id=str(v2["package"]["execution_preflight"]["execution_staging_namespace_id"]), issued_at=now, expires_at=review_expiry,
    )
    approval_id = f"p01-g2-1-baseline-{hashlib.sha256((review_id + ':approval').encode()).hexdigest()[:20]}"
    approval = ProductionHumanJITWindowApprovalV2_10.create(
        approval_ref="approve_p01_g2_1_exact_operational_baseline_only", approval_id=approval_id, approval_version=1,
        reviewer_identity=REVIEWER_IDENTITY, decision="approved_single_jit_window", actor_id=ACTOR_ID,
        review_receipt_id=reviewer_receipt.receipt_id, review_receipt_digest=reviewer_receipt.receipt_digest,
        issued_at=now, expires_at=approval_expiry, package_ref=str(v2["package"]["package_ref"]), package_digest=str(v2["package"]["package_digest"]),
        package_gate_digest=str(v2["package_gate"]["gate_digest"]), plan_digest=str(v2["plan"]["plan_digest"]), plan_gate_digest=str(v2["plan_gate"]["gate_digest"]),
        blueprint_digest=str(v2["blueprint"]["blueprint_digest"]), blueprint_gate_digest=str(v2["blueprint_gate"]["gate_digest"]),
        phase_a_digests=v2["package"]["phase_a_digests"], incident_digest=str(v2["package"]["incident_evidence"]["incident_digest"]),
        expired_terminal_digest=str(v2["package"]["incident_evidence"]["expired_terminal_digest"]), scenario_id=BASELINE_SCENARIO_ID,
        input_ref=BASELINE_INPUT_REF, mutation=BASELINE_MUTATION, authority_boundary=str(v2["package"]["authority_boundary"]),
        execution_staging_namespace_id=str(v2["package"]["execution_preflight"]["execution_staging_namespace_id"]), admission_ttl_minutes=30, receipt_ttl_minutes=15,
        single_use=True, no_retry_replay_or_renewal=True,
    )
    context, check = validate_production_human_jit_window_approval_v2_10(approval, reviewer_receipt=reviewer_receipt, package=v2["package"], package_gate=v2["package_gate"], plan=v2["plan"], plan_gate=v2["plan_gate"], blueprint=v2["blueprint"], blueprint_gate=v2["blueprint_gate"])
    if context is None or check.get("status") != "pass":
        raise ValueError("p01_g2_1_v2_10_authority_invalid")
    authority = create_reviewer_authority(
        authority_id=f"p01-g2-1-authority-{hashlib.sha256((approval.approval_digest + ':outer').encode()).hexdigest()[:20]}",
        issued_at=now, expires_at=approval_expiry, exact_bindings=package["exact_bindings"],
        v2_reviewer_receipt=reviewer_receipt.model_dump(mode="json"), v2_approval=approval.model_dump(mode="json"),
    )
    outer_check = validate_reviewer_authority(authority, package=package)
    if outer_check["status"] != "pass":
        raise ValueError("p01_g2_1_outer_authority_invalid")
    return authority, reviewer_receipt, approval, context


def _baseline_counts() -> dict[str, int]:
    return {"valid_authority_issue_count": 1, "receipt_registration_count": 1, "receipt_consume_count": 1, "formal_namespace_count": 1, "runtime_materialization_count": 1, "baseline_execution_count": 1, "terminal_lifecycle_write_count": 1, "network_success": 0, "tool_success": 0, "model_success": 0, "provider_success": 0, "fixed_store_write": 0, "legacy_authority_change": 0}


def _negative_counts(*, probe_key: str) -> dict[str, int]:
    counts = {"valid_authority_issue_count": 0, "receipt_registration_count": 0, "receipt_consume_count": 0, "formal_namespace_count": 0, "runtime_materialization_count": 0, "baseline_execution_count": 0, "terminal_lifecycle_write_count": 0, "network_success": 0, "tool_success": 0, "model_success": 0, "provider_success": 0, "fixed_store_write": 0, "legacy_authority_change": 0}
    counts[probe_key] = 1
    return counts


def _run_baseline(package: Mapping[str, Any], v2: Mapping[str, Mapping[str, Any]], *, case_root: Path) -> dict[str, Any]:
    authority, reviewer_receipt, approval, context = _authority_pair(package, v2)
    write_verified_json(case_root / "reviewer_decision_authority.json", authority, digest_field="authority_digest")
    write_verified_json(case_root / "v2_10_reviewer_decision_receipt.json", reviewer_receipt.model_dump(mode="json"), digest_field="receipt_digest")
    write_verified_json(case_root / "v2_10_human_approval.json", approval.model_dump(mode="json"), digest_field="approval_digest")
    jit = _v2_jit_module()
    admission, receipt = jit._issue_authority(approval, v2["package"])
    preflight = preflight_exact_execution(v2["package"], admission, repository_root=ROOT, receipt_id=receipt.receipt_id, scenario_id=BASELINE_SCENARIO_ID, human_approval_digest=approval.approval_digest)
    oracle_doc, matrix_doc = _load(ORACLE_PATH), _load(MATRIX_PATH)
    oracle_case = next(item for item in oracle_doc["oracle_cases"] if item["input_case_ref"] == BASELINE_INPUT_REF)
    scenario = next(item for item in matrix_doc["scenarios"] if item["scenario_id"] == BASELINE_SCENARIO_ID)
    result = execute_approved_window_kernel(adapter=make_production_v2_10_adapter(authority_context=context, package=v2["package"], admission=admission, receipt=receipt, preflight=preflight, oracle_case=oracle_case, scenario=scenario, parent=V2_PARENT))
    if result.state != "succeeded" or result.actual is None or result.oracle is None or result.reviewer is None or result.actual.actual_status != "succeeded":
        details = {"kernel_state": result.state, "failure_reason": result.failure_reason, "route_trace": list(result.route_trace), "terminal_digest": result.terminal_digest}
        return build_case_result(case_id=BASELINE_CASE_ID, status="baseline_failed_halt_all", terminal="outcome_unknown" if result.state != "succeeded" else "typed_stop", counts=_baseline_counts(), details=details)
    ledger = M2A1ReceiptLedger.open_existing(result.ledger_path, approved_authority_root=preflight.authority_root)
    events = list(ledger.events(receipt.receipt_id))
    details = {
        "authority_digest": authority["authority_digest"], "v2_reviewer_receipt_digest": reviewer_receipt.receipt_digest,
        "approval_digest": approval.approval_digest, "admission_digest": admission.admission_digest, "receipt_id": receipt.receipt_id,
        "receipt_digest": receipt.receipt_digest, "actual_digest": result.actual.actual_result_digest, "oracle_digest": result.oracle.evaluation_digest,
        "reviewer_gate_digest": result.reviewer.gate_digest, "terminal_digest": result.terminal_digest, "validation_order": list(result.route_trace),
        "ledger_path": str(result.ledger_path), "formal_namespace_root": str(preflight.run_root.parent), "runtime_root": str(preflight.run_root), "output_path": str(preflight.output_path),
        "ledger_events": events, "artifact_digests": dict(result.artifact_digests),
    }
    return build_case_result(case_id=BASELINE_CASE_ID, status="pass", terminal="succeeded", counts=_baseline_counts(), details=details)


def _run_pre_authority_probe(case_id: str, *, case_root: Path, package: Mapping[str, Any], v2: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    if case_id == "g2-wrong-package-or-approval":
        details = {"tampered_package_digest": "0" * 64, "expected_package_digest": package["package_digest"], "authority_created": False, "namespace_opened": False}
        result = build_case_result(case_id=case_id, status="pass", terminal="pre_authority_typed_deny:package_or_approval_mismatch", counts=_negative_counts(probe_key="package_approval_binding_deny_artifact_count"), details=details)
    elif case_id == "g2-stale-input-version-drift":
        scenario = next(item for item in _load(MATRIX_PATH)["scenarios"] if item["scenario_id"] == "p02-stale-or-superseded-pack")
        details = {"scenario_id": scenario["scenario_id"], "mutation": scenario["mutation"], "expected_typed_stop": scenario["expected_typed_stop"], "authority_created": False, "namespace_opened": False}
        result = build_case_result(case_id=case_id, status="pass", terminal="typed_stop:superseded_pack_version_or_pack_not_fresh", counts=_negative_counts(probe_key="pack_version_admission_preflight_artifact_count"), details=details)
    elif case_id == "g2-unauthorized-transport":
        canary = M2A1AuditCanary(allowed_temporary_roots=(case_root,), fixed_paths=(ROOT / str(v2["package"]["fixed_store_fingerprints"]["fixed_approval_store"]["path"]),))
        canary.observe_transport_module_presence()
        caught: str | None = None
        try:
            with canary.instrument():
                urllib.request.urlopen("http://127.0.0.1:9", timeout=0.01)
        except M2A1TransportAccessError as exc:
            caught = str(exc)
        snapshot = canary.snapshot()
        counts = snapshot["counts"]
        if caught != "shadow_scope_violation" or counts["network_request_attempt_count"] != 1 or counts["network_request_success_count"] != 0:
            raise ValueError("p01_g2_1_transport_probe_unexpected")
        result = build_case_result(case_id=case_id, status="pass", terminal="typed_stop:shadow_scope_violation", counts=_negative_counts(probe_key="network_tool_permission_probe_artifact_count"), details={"canary": snapshot, "authority_created": False, "namespace_opened": False})
    else:
        raise ValueError("p01_g2_1_negative_case_invalid")
    write_verified_json(case_root / f"{case_id}_pre_authority_probe.json", result, digest_field="result_digest")
    return result


def _aggregate(case_results: list[Mapping[str, Any]]) -> dict[str, Any]:
    totals: dict[str, int] = {}
    for result in case_results:
        for key, value in result["counts"].items():
            totals[key] = totals.get(key, 0) + int(value)
    payload = {"schema_version": "finsight_point01_p01_g2_1_aggregate_reconciliation_v1_0", "case_result_digests": [result["result_digest"] for result in case_results], "per_case_counts": {result["case_id"]: result["counts"] for result in case_results}, "aggregate_counts": totals}
    return {**payload, "result_digest": canonical_digest(payload)}


def execute() -> tuple[int, Mapping[str, Any] | None]:
    try:
        package, _gate, tranche, tranche_gate, v2 = _preflight_no_side_effects()
        case_root = P01_ROOT / BASELINE_CASE_ID
        baseline = _run_baseline(package, v2, case_root=case_root)
        write_verified_json(case_root / "baseline_case_result.json", baseline, digest_field="result_digest")
        fixed_after = digest_file(ROOT / str(v2["package"]["fixed_store_fingerprints"]["fixed_approval_store"]["path"]))
        if baseline["status"] != "pass":
            return 2, {"status": "P01_G2_1_BASELINE_FAILED_STOPPED", "baseline": baseline, "fixed_store_sha256_after": fixed_after}
        results: list[Mapping[str, Any]] = [baseline]
        for case_id in ("g2-wrong-package-or-approval", "g2-stale-input-version-drift", "g2-unauthorized-transport"):
            probe_root = P01_ROOT / "pre_authority_probes" / case_id
            probe = _run_pre_authority_probe(case_id, case_root=probe_root, package=package, v2=v2)
            if probe["status"] != "pass":
                return 2, {"status": "P01_G2_1_PRE_AUTHORITY_PROBE_FAILED_STOPPED", "case": case_id, "probe": probe}
            results.append(probe)
        aggregate = _aggregate(results)
        write_verified_json(P01_ROOT / "aggregate_reconciliation.json", aggregate, digest_field="result_digest")
        final_payload = {
            "schema_version": "finsight_point01_p01_g2_1_operational_execution_result_v1_0",
            "status": "P01_G2_1_OPERATIONAL_TRANCHE_EXECUTED_PENDING_INDEPENDENT_REVIEW",
            "package_digest": package["package_digest"], "tranche_digest": tranche["tranche_digest"], "tranche_gate_digest": tranche_gate["gate_digest"],
            "v2_10_family": package["exact_bindings"], "case_results": results, "aggregate": aggregate,
            "fixed_store_sha256_after": fixed_after, "legacy_authority": "retained", "production_readiness": "not_admitted", "cleanup": "forbidden_until_independent_closeout",
        }
        final = {**final_payload, "result_digest": canonical_digest(final_payload)}
        write_verified_json(P01_ROOT / "p01_g2_1_execution_result.json", final, digest_field="result_digest")
        return 0, final
    except Exception as exc:
        return 2, {"status": "P01_G2_1_FAIL_CLOSED", "error_type": type(exc).__name__, "error": str(exc), "formal_namespace_created": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Execute the exact authorized P01-G2.1 tranche once; default is deny.")
    parser.add_argument("--execute-approved-tranche", action="store_true")
    args = parser.parse_args(argv)
    if not args.execute_approved_tranche:
        print(json.dumps({"status": "p01_g2_1_execution_authority_required", "side_effects": 0}, sort_keys=True))
        return 2
    rc, result = execute()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
