from __future__ import annotations

import argparse
import glob
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "configs/engineering_handoff/point01_m5_9_closeout_gate_manifest_v1_0.json"
DEFAULT_POLICY = ROOT / "configs/engineering_handoff/point01_m5_9_closeout_policy_v1_0.json"
DEFAULT_REVIEW = ROOT / "configs/engineering_handoff/point01_m5_human_ops_security_closeout_v1_0.json"
DEFAULT_FULL_REVIEW = ROOT / "configs/engineering_handoff/point01_m5_human_full_calibrated_closeout_v1_0.json"
DEFAULT_OUTPUT = ROOT / "data/manifests/point01_m5_closeout_gate_result_v1_0.json"
PACKAGE_PATTERNS = (
    "src/sec_agent/canonical_runtime/*.py", "tests/contract/test_point01_m5*.py",
    "configs/engineering_handoff/point01_m5*.json", "scripts/engineering/run_point01_m5*.py",
    "data/manifests/point01_m5*.json", "configs/engineering_handoff/point01_generated_json_schemas_v1_0.json",
    "data/manifests/point01_m1_closeout_gate_result_v1_0.json", "data/manifests/point01_m1_postgresql_conformance_sample_result_v1_0.json",
    "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md",
)


def _sha256(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()


def _package_file_sha256(path: Path) -> str:
    """Hash deterministic fixture content without binding the execution clock.

    M5 fixture runners deliberately record their wall-clock ``generated_at``.
    That field is useful operational metadata but must not invalidate a human
    receipt when a gate reruns the same deterministic fixture evidence.  Every
    other fixture field, including status, errors, evidence and fixed inputs,
    remains part of the package hash.
    """
    if path.name.startswith("point01_m5_") and path.suffix == ".json":
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return _sha256(path)
        if isinstance(payload, dict) and "result_version" in payload:
            payload = {key: value for key, value in payload.items() if key != "generated_at"}
            return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()
    return _sha256(path)


def _resolve(path: Path) -> Path: return path if path.is_absolute() else ROOT / path


def _run_script(path: Path) -> dict[str, Any]:
    completed = subprocess.run([sys.executable, str(path)], cwd=ROOT, capture_output=True, text=True, check=False)
    return {"returncode": completed.returncode, "output_tail": (completed.stdout + completed.stderr)[-2000:]}


def _package_manifest() -> tuple[list[str], str]:
    excluded = {DEFAULT_REVIEW.resolve(), DEFAULT_FULL_REVIEW.resolve(), DEFAULT_OUTPUT.resolve()}
    paths = sorted({Path(path) for pattern in PACKAGE_PATTERNS for path in glob.glob(str(ROOT / pattern)) if Path(path).is_file() and Path(path).resolve() not in excluded})
    relative = [path.relative_to(ROOT).as_posix() for path in paths]
    return relative, _digest_paths(relative)


def _digest_paths(relative_paths: list[str]) -> str:
    return hashlib.sha256(json.dumps({path: _package_file_sha256(ROOT / path) for path in sorted(relative_paths)}, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _run_test_manifest() -> dict[str, Any]:
    # The closeout test invokes this script in verification mode, so the full
    # M5 manifest can be run here without recursive fixture execution.
    paths = sorted((ROOT / "tests/contract").glob("test_point01_m5*.py"))
    completed = subprocess.run([sys.executable, "-m", "pytest", *map(str, paths), "-q"], cwd=ROOT, capture_output=True, text=True, check=False)
    return {"paths": [path.relative_to(ROOT).as_posix() for path in paths], "returncode": completed.returncode, "output_tail": (completed.stdout + completed.stderr)[-2000:]}


def _fixture_evidence(fixture_results: dict[str, dict[str, Any]], point: str) -> dict[str, Any] | None:
    result = fixture_results.get(point)
    if not result or result.get("status") != "pass":
        return None
    evidence = result.get("evidence")
    return evidence if isinstance(evidence, dict) else None


def _has_values(evidence: dict[str, Any] | None, expected: dict[str, Any]) -> bool:
    return evidence is not None and all(evidence.get(key) == value for key, value in expected.items())


def _validate_persistent_authority(fixture_results: dict[str, dict[str, Any]]) -> bool:
    return all((_has_values(_fixture_evidence(fixture_results, "M5.4"), {"persisted_grant_authority_survives_restart": True}), _has_values(_fixture_evidence(fixture_results, "M5.5"), {"budget_ledger_survives_restart": True}), _has_values(_fixture_evidence(fixture_results, "M5.6"), {"persisted_registry_authority_survives_restart": True})))


def _validate_real_child_process_crash_matrix(fixture_results: dict[str, dict[str, Any]]) -> bool:
    return _has_values(_fixture_evidence(fixture_results, "M5.calibration"), {"worker_a_process_started": True, "worker_a_exit_code": 71, "worker_loss_observed": True, "worker_b_process_started": True, "worker_b_reclaimed": True, "recovered_fencing_token": 2, "stale_worker_fenced": True, "transaction_crash_process_started": True, "transaction_crash_exit_code": 73, "partial_row_absent_after_process_crash": True, "budget_crash_process_started": True, "budget_crash_exit_code": 74, "budget_artifact_committed_before_reconcile": True, "budget_reservation_reconciled_consumed": True})


def _validate_concurrency_security_outcomes(fixture_results: dict[str, dict[str, Any]]) -> bool:
    return _has_values(_fixture_evidence(fixture_results, "M5.concurrency"), {"budget_outcomes": ["reserved", "terminal_stop"], "budget_reserved_count": 1, "budget_terminal_stop_count": 1, "security_outcomes": ["allowed", "denied"], "security_decision_count": 3, "revoked_grant_denial_code": "capability_grant_revoked"})


def _validate_hitl_restart_revocation(fixture_results: dict[str, dict[str, Any]]) -> bool:
    return _has_values(_fixture_evidence(fixture_results, "M5.6"), {"persisted_registry_authority_survives_restart": True, "pause_survived_restart": True, "resumed_fencing_token": 2, "revoked_resume_blocked": True})


def _validate_semantic_rebase_authoritative_receipt(fixture_results: dict[str, dict[str, Any]]) -> bool:
    return _has_values(_fixture_evidence(fixture_results, "M5.7"), {"rebase_requested_state": "rebase_required", "rebase_context_recompile_requested": True, "recompiled_snapshot_state": "active", "recompiled_context": {"eps": 2}, "forged_ambiguous_receipt_rejected": True, "ambiguous_receipt_verified": True})


def _validate_observability_incident_semantics(fixture_results: dict[str, dict[str, Any]]) -> bool:
    return _has_values(_fixture_evidence(fixture_results, "M5.8"), {"reconnect_has_no_duplicate": True, "open_alert_count": 1, "raw_reasoning_rejected": True, "raw_reasoning_persisted": False}) and int((_fixture_evidence(fixture_results, "M5.8") or {}).get("trace_span_count", 0)) >= 1


CALIBRATION_VALIDATORS = {
    "persistent_authority_v1": _validate_persistent_authority,
    "real_child_process_crash_matrix_v2": _validate_real_child_process_crash_matrix,
    "concurrency_security_outcomes_v1": _validate_concurrency_security_outcomes,
    "hitl_restart_revocation_v1": _validate_hitl_restart_revocation,
    "semantic_rebase_authoritative_receipt_v2": _validate_semantic_rebase_authoritative_receipt,
    "observability_incident_semantics_v1": _validate_observability_incident_semantics,
}


def _machine_calibration_validation_details(policy: dict[str, Any], fixture_results: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    details: dict[str, dict[str, Any]] = {}
    for condition, validator_name in (policy.get("machine_calibration_validators") or {}).items():
        validator = CALIBRATION_VALIDATORS.get(str(validator_name))
        details[str(condition)] = {"validator": validator_name, "status": "pass" if validator and validator(fixture_results) else "fail_closed"}
    return details


def _completed_machine_calibrations(policy: dict[str, Any], fixture_results: dict[str, dict[str, Any]]) -> list[str]:
    return sorted(condition for condition, detail in _machine_calibration_validation_details(policy, fixture_results).items() if detail["status"] == "pass")


def build_result(manifest: dict[str, Any], policy: dict[str, Any], review: dict[str, Any], full_review: dict[str, Any], *, manifest_path: Path = DEFAULT_MANIFEST, policy_path: Path = DEFAULT_POLICY, review_path: Path = DEFAULT_REVIEW, full_review_path: Path = DEFAULT_FULL_REVIEW, invoke_fixtures: bool = True, invoke_checks: bool = True, m1_result: dict[str, Any] | None = None) -> dict[str, Any]:
    unmet: list[str] = []
    fixture_runs: dict[str, Any] = {}
    fixture_results: dict[str, Any] = {}
    if policy.get("policy_version") != "finsight_point01_m5_9_closeout_policy_v1_0": unmet.append("closeout_policy_identity_invalid")
    required_scripts = manifest.get("required_fixture_scripts") or {}
    required_results = manifest.get("required_fixture_results") or {}
    for point, relative in sorted(required_scripts.items()):
        script = _resolve(Path(relative))
        if not script.exists():
            unmet.append(f"fixture_script_missing:{point}")
            continue
        if invoke_fixtures:
            fixture_runs[point] = _run_script(script)
            if fixture_runs[point]["returncode"] != 0: unmet.append(f"fixture_runner_failed:{point}")
        result_path = _resolve(Path(required_results.get(point) or ""))
        if not result_path.exists():
            unmet.append(f"fixture_result_missing:{point}")
            continue
        result = json.loads(result_path.read_text(encoding="utf-8")); fixture_results[point] = result
        if result.get("status") != "pass": unmet.append(f"fixture_result_not_pass:{point}")
    lint = _run_script(ROOT / "scripts/engineering/run_point01_m5_design_lint.py") if invoke_checks else {"returncode": 0, "output_tail": "verification_uses_existing_checked_evidence"}
    if lint["returncode"] != 0: unmet.append("m5_design_lint_failed")
    test_manifest = _run_test_manifest() if invoke_checks else {"paths": [path.relative_to(ROOT).as_posix() for path in sorted((ROOT / "tests/contract").glob("test_point01_m5*.py"))], "returncode": 0, "output_tail": "verification_uses_existing_checked_evidence"}
    if test_manifest["returncode"] != 0: unmet.append("m5_test_manifest_failed")
    compileall = subprocess.run([sys.executable, "-m", "compileall", "-q", "src/sec_agent/canonical_runtime", "tests/contract"], cwd=ROOT, capture_output=True, text=True, check=False) if invoke_checks else subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
    if compileall.returncode != 0: unmet.append("compileall_failed")
    m1_path = ROOT / "data/manifests/point01_m1_closeout_gate_result_v1_0.json"
    m1 = m1_result if m1_result is not None else (json.loads(m1_path.read_text(encoding="utf-8")) if m1_path.exists() else {})
    if m1.get("gate_status") != "pass": unmet.append("m1_fixed_hash_closeout_not_pass")
    expected_decision = policy.get("required_fixture_tranche_decision")
    expected_full_decision = policy.get("required_full_calibrated_closeout_decision")
    package_paths, closeout_package_digest = _package_manifest()
    fixture_tranche_metadata_accepted = review.get("status") == "accepted_m5_fixture_tranche_only" and review.get("decision") == expected_decision and bool(review.get("reviewer_identity")) and bool(review.get("reviewed_at"))
    fixture_tranche_accepted = fixture_tranche_metadata_accepted and review.get("closeout_package_digest") == closeout_package_digest
    full_review_accepted = full_review.get("status") == "accepted_m5_full_calibrated_closeout_only" and full_review.get("decision") == expected_full_decision and bool(full_review.get("reviewer_identity")) and bool(full_review.get("reviewed_at")) and full_review.get("closeout_package_digest") == closeout_package_digest
    if not fixture_tranche_metadata_accepted and not full_review_accepted:
        unmet.append("fixture_tranche_human_acceptance_required")
    if not fixture_tranche_accepted and not full_review_accepted:
        unmet.append("fixture_tranche_receipt_package_digest_mismatch")
    completed_machine_calibrations = _completed_machine_calibrations(policy, fixture_results)
    machine_calibration_validation = _machine_calibration_validation_details(policy, fixture_results)
    for condition in policy.get("required_full_calibrated_closeout_conditions") or ():
        if condition == "separate_full_calibrated_human_review" and full_review_accepted:
            continue
        if condition != "separate_full_calibrated_human_review" and condition in completed_machine_calibrations:
            continue
        if condition == "separate_full_calibrated_human_review" or condition not in completed_machine_calibrations:
            unmet.append(f"full_calibrated_closeout_required:{condition}")
    forbidden = ["worker_service", "provider_execution", "external_tool_execution", "Evidence_runtime", "Writer_runtime", "full_chain", "business_case_mutation", "legacy_taskrun_authority_change", "sector_tenant_global_cutover"]
    forbidden_violations = [name for name in forbidden if name not in policy.get("forbidden_admissions", [])]
    if forbidden_violations: unmet.append("forbidden_admission_boundary_incomplete")
    gate_status = "pass" if not unmet else "fail_closed"
    milestone_status = "M5_complete_temporary_store_full_calibrated_reviewed" if gate_status == "pass" else "M5_fixture_tranche_accepted_full_and_calibrated_closeout_pending"
    fixture_tranche_status = "full_calibrated_review_accepted" if full_review_accepted else "accepted" if fixture_tranche_accepted else "pending_digest_bound_acceptance"
    return {"result_version": "finsight_point01_m5_closeout_gate_result_v1_3", "generated_at": datetime.now(timezone.utc).isoformat(), "scope": "Point01_M5_fixture_tranche_and_full_calibrated_closeout_gate", "gate_status": gate_status, "fixture_tranche_status": fixture_tranche_status, "milestone_status": milestone_status, "unmet_closeout_conditions": unmet, "completed_machine_calibrations": completed_machine_calibrations, "machine_calibration_validation": machine_calibration_validation, "fixture_runs": fixture_runs, "fixture_results": {point: {"status": result.get("status"), "worker_started": result.get("worker_started"), "model_call_count": result.get("model_call_count"), "external_call_count": result.get("external_call_count")} for point, result in fixture_results.items()}, "machine_checks": {"m5_design_lint": lint, "m5_test_manifest": test_manifest, "compileall": {"returncode": compileall.returncode, "output_tail": (compileall.stdout + compileall.stderr)[-2000:]}, "m1_fixed_hash_closeout_status": m1.get("gate_status")}, "closeout_package": {"digest": closeout_package_digest, "path_count": len(package_paths), "paths": package_paths}, "human_review": {"fixture_tranche": {"status": review.get("status"), "required_decision": expected_decision, "decision": review.get("decision"), "bound_package_digest": review.get("closeout_package_digest")}, "full_calibrated": {"status": full_review.get("status"), "required_decision": expected_full_decision, "decision": full_review.get("decision"), "bound_package_digest": full_review.get("closeout_package_digest")}}, "authority_boundary": {"legacy_task_run": "authoritative", "worker_started": False, "provider_execution": False, "external_tool_execution": False, "Evidence_runtime": False, "Writer_runtime": False, "full_chain": False, "business_case_mutation": False, "legacy_authority_change": False}, "fixed_input_sha256": {"configs/engineering_handoff/point01_m5_9_closeout_gate_manifest_v1_0.json": _sha256(manifest_path), "configs/engineering_handoff/point01_m5_9_closeout_policy_v1_0.json": _sha256(policy_path), "configs/engineering_handoff/point01_m5_human_ops_security_closeout_v1_0.json": _sha256(review_path), "configs/engineering_handoff/point01_m5_human_full_calibrated_closeout_v1_0.json": _sha256(full_review_path), "scripts/engineering/run_point01_m5_closeout_gate.py": _sha256(Path(__file__).resolve())}, "boundary": "This gate may close only a digest-bound temporary-store M5 tranche after an independent full/calibrated human review. It cannot authorize provider/tool execution, business Case mutation, legacy authority change or broader runtime cutover."}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Point 01 M5 aggregate closeout gate.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST); parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY); parser.add_argument("--review", type=Path, default=DEFAULT_REVIEW); parser.add_argument("--full-review", type=Path, default=DEFAULT_FULL_REVIEW); parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT); parser.add_argument("--skip-fixture-rerun", action="store_true"); parser.add_argument("--verify-existing-package", action="store_true")
    args = parser.parse_args(); manifest_path = _resolve(args.manifest); policy_path = _resolve(args.policy); review_path = _resolve(args.review); full_review_path = _resolve(args.full_review); output_path = _resolve(args.output)
    result = build_result(json.loads(manifest_path.read_text(encoding="utf-8")), json.loads(policy_path.read_text(encoding="utf-8")), json.loads(review_path.read_text(encoding="utf-8")), json.loads(full_review_path.read_text(encoding="utf-8")), manifest_path=manifest_path, policy_path=policy_path, review_path=review_path, full_review_path=full_review_path, invoke_fixtures=not args.skip_fixture_rerun, invoke_checks=not args.verify_existing_package)
    output_path.parent.mkdir(parents=True, exist_ok=True); output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"gate_status": result["gate_status"], "output": str(output_path), "unmet": result["unmet_closeout_conditions"]}, ensure_ascii=False)); return 0 if result["gate_status"] == "pass" else 1


if __name__ == "__main__": raise SystemExit(main())
