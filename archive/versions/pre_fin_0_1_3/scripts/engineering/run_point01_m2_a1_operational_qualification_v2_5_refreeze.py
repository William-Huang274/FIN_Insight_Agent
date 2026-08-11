"""Refreeze B0.2 after the v2.4 pre-consume dispatch incident.

This script reads Git-index bytes only and emits reviewed manifests.  It cannot
issue authority, create a receipt ledger, create an execution namespace, or
run an M2 scenario.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
OLD_PACKAGE_PATH = "data/manifests/point01_m2_a1_execution_ready_audit_package_manifest_v2_4.json"
INCIDENT_PATH = "data/manifests/point01_m2_a1_v2_4_baseline_jit_dispatch_incident.json"
EXPIRED_PATH = "data/manifests/point01_m2_a1_v2_4_baseline_jit_expired_unconsumed_terminal.json"
OLD_PACKAGE_DIGEST = "615a73da64eff69a56a13b42d6c59c892820f15c4de7dc3a2be3c425d2aee68e"
OLD_BLUEPRINT_DIGEST = "09ee9176a8090f1c42885fb2fab33c118a2d7b41cab2b66d694e478ff0b873a8"
INCIDENT_DIGEST = "a59076a127c0b76902dc362aee94980427660fbc695b47e9c94fd73228cb9a18"
FIXED_PATH = ".runtime_control/point01_m6_3_5_nvda_sec_document_parser_repaired_global_approval/canonical.sqlite"
FIXED_SHA256 = "ae48eea1eec25ae96143a49266c991365fe9974d1c282d3d5579ccd56ab561f4"
PACKAGE_REF = "point01-m2-a1-operational-qualification-adversarial-audit-package-v2-5-dispatch-repair"
NAMESPACE_ID = "point01_m2_a1_exact_admitted_runs_v2_5"
NAMESPACE_PATH = "D:/temp/FIN_Insight_Agent/point01_m2_a1_exact_admitted_runs_v2_5"
BASELINE = "p01-baseline-separated-input"
OUTPUTS = {
    "package": ROOT / "data/manifests/point01_m2_a1_execution_ready_audit_package_manifest_v2_5.json",
    "package_gate": ROOT / "data/manifests/point01_m2_a1_execution_ready_audit_package_freeze_gate_result_v2_5.json",
    "plan": ROOT / "data/manifests/point01_m2_a1_receipt_execution_plan_v1_2_dispatch_repair.json",
    "plan_gate": ROOT / "data/manifests/point01_m2_a1_receipt_execution_plan_v1_2_dispatch_repair_gate.json",
    "blueprint": ROOT / "data/manifests/point01_m2_a1_baseline_authority_blueprint_v1_2_dispatch_repair.json",
    "blueprint_gate": ROOT / "data/manifests/point01_m2_a1_baseline_authority_blueprint_v1_2_dispatch_repair_gate.json",
}
REPLACED_PATHS = {
    "scripts/engineering/run_point01_m2_a1_actual_audit_v2_4.py": "scripts/engineering/run_point01_m2_a1_actual_audit_v2_5.py",
    "scripts/engineering/run_point01_m2_a1_actual_audit_clean_child_v2_4.py": "scripts/engineering/run_point01_m2_a1_actual_audit_clean_child_v2_5.py",
    "scripts/engineering/run_point01_m2_a1_receipt_registrar_v2_4.py": "scripts/engineering/run_point01_m2_a1_receipt_registrar_v2_5.py",
    "scripts/engineering/run_point01_m2_a1_operational_qualification_v2_4_refreeze.py": "scripts/engineering/run_point01_m2_a1_operational_qualification_v2_5_refreeze.py",
}
NEW_INPUTS = {
    "scripts/engineering/run_point01_m2_a1_v2_5_baseline_jit_window.py",
    "scripts/engineering/run_point01_m2_a1_expire_v2_4_baseline_unconsumed_receipt.py",
    "tests/contract/test_point01_m2_a1_v2_5_dispatch_and_expiry.py",
    INCIDENT_PATH,
    EXPIRED_PATH,
}


def _canonical(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _index_bytes(relative_path: str) -> bytes:
    completed = subprocess.run(["git", "show", f":{relative_path}"], cwd=ROOT, capture_output=True, check=False)
    if completed.returncode:
        raise RuntimeError(f"v2_5_refreeze_git_index_input_missing:{relative_path}")
    return completed.stdout


def _index_json(relative_path: str) -> dict[str, Any]:
    loaded = json.loads(_index_bytes(relative_path).decode("utf-8"))
    if not isinstance(loaded, dict):
        raise RuntimeError(f"v2_5_refreeze_index_mapping_required:{relative_path}")
    return loaded


def _sha(relative_path: str) -> str:
    return hashlib.sha256(_index_bytes(relative_path)).hexdigest()


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _runtime_templates() -> dict[str, Any]:
    unresolved = "unresolved_not_active"
    return {
        "external_admission": {"schema_version": "finsight_point01_m2_a1_external_package_admission_v2_5", "fields": {key: unresolved for key in ("admission_ref", "admission_id", "admission_version", "reviewer_identity", "decision", "package_ref", "executable_package_digest", "scope", "authority_boundary", "execution_staging_namespace_id", "execution_mode", "expires_at", "admission_digest")}},
        "authority_wrapper": {"schema_version": "finsight_point01_m2_a1_external_admission_authority_wrapper_v2_5", "fields": {key: unresolved for key in ("authority_ref", "reviewer_identity", "decision", "issued_at", "expires_at", "package_ref", "package_digest", "package_gate_digest", "plan_digest", "plan_gate_digest", "scope", "authority_boundary", "execution_staging_namespace_id", "runtime_admission_digest", "nonce_sha256", "fixed_store_fingerprint", "authority_artifact_digest")}},
        "single_use_execution_receipt": {"schema_version": "finsight_point01_m2_a1_single_use_execution_receipt_v2_5", "fields": {key: unresolved for key in ("receipt_id", "receipt_version", "approval_id", "package_ref", "executable_package_digest", "scope", "admission_digest", "nonce_sha256", "expires_at", "reviewer_identity", "execution_staging_namespace_id", "scenario_id", "state", "single_use", "receipt_digest")}},
    }


def build_package() -> dict[str, Any]:
    old = _index_json(OLD_PACKAGE_PATH)
    incident = _index_json(INCIDENT_PATH)
    expired = _index_json(EXPIRED_PATH)
    if old.get("package_digest") != OLD_PACKAGE_DIGEST or incident.get("incident_digest") != INCIDENT_DIGEST:
        raise RuntimeError("v2_5_refreeze_historical_incident_binding_invalid")
    if expired.get("status") not in {"expired_unconsumed", "already_expired_unconsumed_exact"} or not isinstance(expired.get("expired_terminal_digest"), str):
        raise RuntimeError("v2_5_refreeze_expired_terminal_invalid")
    input_paths = set(old["input_file_sha256"])
    input_paths.difference_update(REPLACED_PATHS)
    input_paths.update(REPLACED_PATHS.values())
    input_paths.update(NEW_INPUTS)
    input_hashes = {path: _sha(path) for path in sorted(input_paths)}
    phase_a = old["phase_a_digests"]
    payload: dict[str, Any] = {
        **{key: value for key, value in old.items() if key not in {"package_digest", "schema_version", "package_ref", "input_file_sha256", "execution_preflight", "receipt_lifecycle", "transport_isolation", "supersedes", "incident_evidence"}},
        "schema_version": "finsight_point01_m2_a1_execution_ready_audit_package_manifest_v2_5",
        "package_ref": PACKAGE_REF,
        "input_file_sha256": input_hashes,
        "execution_preflight": {**old["execution_preflight"], "execution_staging_namespace_id": NAMESPACE_ID, "execution_staging_namespace_path": NAMESPACE_PATH},
        "receipt_lifecycle": {**old["receipt_lifecycle"], "expiry_terminal": "exact_expired_unconsumed_append_only_no_payload_overwrite"},
        "transport_isolation": {**{key: value for key, value in old["transport_isolation"].items() if key != "runtime_hash_bindings"}, "runtime_hash_bindings": {
            "parent_runner": {"relative_path": REPLACED_PATHS["scripts/engineering/run_point01_m2_a1_actual_audit_v2_4.py"], "sha256": input_hashes[REPLACED_PATHS["scripts/engineering/run_point01_m2_a1_actual_audit_v2_4.py"]]},
            "clean_child": {"relative_path": REPLACED_PATHS["scripts/engineering/run_point01_m2_a1_actual_audit_clean_child_v2_4.py"], "sha256": input_hashes[REPLACED_PATHS["scripts/engineering/run_point01_m2_a1_actual_audit_clean_child_v2_4.py"]]},
            "canary": {"relative_path": "src/sec_agent/canonical_runtime/m2_a1_audit_canary.py", "sha256": input_hashes["src/sec_agent/canonical_runtime/m2_a1_audit_canary.py"]},
            "registrar": {"relative_path": REPLACED_PATHS["scripts/engineering/run_point01_m2_a1_receipt_registrar_v2_4.py"], "sha256": input_hashes[REPLACED_PATHS["scripts/engineering/run_point01_m2_a1_receipt_registrar_v2_4.py"]]},
            "jit_orchestrator": {"relative_path": "scripts/engineering/run_point01_m2_a1_v2_5_baseline_jit_window.py", "sha256": input_hashes["scripts/engineering/run_point01_m2_a1_v2_5_baseline_jit_window.py"]},
        }},
        "supersedes": {"v2_4_package_digest": OLD_PACKAGE_DIGEST, "v2_4_blueprint_digest": OLD_BLUEPRINT_DIGEST, "prior_failed_actual_digest": "934fb16b76f1e1b19371603f0d69c2e3e25c9357c8427c84e1e626b1247795d7", "authority_disposition": "historical_only_expired_consumed_or_non_replayable"},
        "incident_evidence": {"relative_path": INCIDENT_PATH, "incident_digest": INCIDENT_DIGEST, "expired_terminal_relative_path": EXPIRED_PATH, "expired_terminal_digest": expired["expired_terminal_digest"]},
    }
    return {**payload, "package_digest": _canonical(payload)}


def verify_package(package: Mapping[str, Any]) -> dict[str, Any]:
    payload = {key: value for key, value in package.items() if key != "package_digest"}
    failures: list[str] = []
    if package.get("package_digest") != _canonical(payload):
        failures.append("package_digest_mismatch")
    if package.get("schema_version") != "finsight_point01_m2_a1_execution_ready_audit_package_manifest_v2_5" or package.get("package_ref") != PACKAGE_REF:
        failures.append("package_identity_invalid")
    hashes = package.get("input_file_sha256")
    if not isinstance(hashes, Mapping) or any(_sha(path) != digest for path, digest in hashes.items()):
        failures.append("git_index_input_hash_mismatch")
    if package.get("fixed_store_fingerprints", {}).get("fixed_approval_store", {}).get("sha256") != FIXED_SHA256:
        failures.append("fixed_fingerprint_invalid")
    import sys
    sys.path.insert(0, str(ROOT / "src"))
    from sec_agent.canonical_runtime.m2_a1_execution_receipt import M2A1ExecutionPreflightError, preflight_exact_execution
    try:
        preflight_exact_execution(package, None, repository_root=ROOT, receipt_id="v2-5-schema-preflight-no-receipt", scenario_id=BASELINE)
    except M2A1ExecutionPreflightError as exc:
        preflight_status = str(exc)
        if preflight_status != "package_admission_required":
            failures.append(f"production_preflight_{preflight_status}")
    else:
        preflight_status = "unexpected_pass"
        failures.append("production_preflight_missing_admission_did_not_fail_closed")
    return {"status": "pass" if not failures else "fail_closed", "failures": sorted(set(failures)), "calculated_package_digest": _canonical(payload), "production_preflight": preflight_status, "input_hash_count": len(package["input_file_sha256"])}


def build_plan(package: Mapping[str, Any], gate: Mapping[str, Any]) -> dict[str, Any]:
    summary = package["scenario_matrix_summary"]
    entries = []
    for index, scenario_id in enumerate(summary["scenario_ids"], start=1):
        entries.append({"sequence": index, "group": "P01" if index <= 4 else "P02" if index <= 10 else "P03", "scenario_id": scenario_id, "future_authority": "independent_admission_plus_single_use_receipt_JIT_only", "on_failure": "fail_fast_no_retry_no_replay_no_next_authority"})
    payload = {"schema_version": "finsight_point01_m2_a1_receipt_execution_plan_v1_2_dispatch_repair", "status": "compatibility_assessed_dispatch_repair_refrozen_pending_independent_review_no_authority", "exact_package": {"package_ref": package["package_ref"], "package_digest": package["package_digest"], "package_gate_digest": gate["gate_digest"], "scope": package["scope"], "authority_boundary": package["authority_boundary"], "execution_staging_namespace_id": NAMESPACE_ID}, "phase_a_digests": package["phase_a_digests"], "incident_binding": package["incident_evidence"], "baseline_first": BASELINE, "scenario_execution_order": entries, "group_counts": {"P01": 4, "P02": 6, "P03": 6}, "all_other_scenarios_blocked_until_prior_checkpoint": True, "execution_counts": {"admission": 0, "receipt": 0, "ledger": 0, "namespace": 0, "actual": 0, "external": 0, "store_write": 0}}
    return {**payload, "plan_digest": _canonical(payload)}


def verify_plan(plan: Mapping[str, Any], package: Mapping[str, Any], gate: Mapping[str, Any]) -> dict[str, Any]:
    payload = {key: value for key, value in plan.items() if key != "plan_digest"}
    failures = []
    if plan.get("plan_digest") != _canonical(payload): failures.append("plan_digest_mismatch")
    if plan.get("exact_package", {}).get("package_digest") != package.get("package_digest") or plan.get("exact_package", {}).get("package_gate_digest") != gate.get("gate_digest"): failures.append("plan_package_gate_binding_invalid")
    if plan.get("incident_binding") != package.get("incident_evidence"): failures.append("plan_incident_binding_invalid")
    if plan.get("group_counts") != {"P01": 4, "P02": 6, "P03": 6} or len(plan.get("scenario_execution_order", [])) != 16 or plan.get("scenario_execution_order", [{}])[0].get("scenario_id") != BASELINE: failures.append("plan_matrix_invalid")
    return {"status": "pass" if not failures else "fail_closed", "failures": failures, "calculated_plan_digest": _canonical(payload)}


def build_blueprint(package: Mapping[str, Any], package_gate: Mapping[str, Any], plan: Mapping[str, Any], plan_gate: Mapping[str, Any]) -> dict[str, Any]:
    payload = {"schema_version": "finsight_point01_m2_a1_baseline_authority_blueprint_v1_2_dispatch_repair", "status": "baseline_blueprint_dispatch_repair_refrozen_pending_independent_review_no_authority", "exact_binding": {"package_ref": package["package_ref"], "package_digest": package["package_digest"], "package_gate_digest": package_gate["gate_digest"], "plan_digest": plan["plan_digest"], "plan_gate_digest": plan_gate["gate_digest"], "phase_a_digests": package["phase_a_digests"], "incident_evidence": package["incident_evidence"], "scenario_id": BASELINE, "input_ref": "m2-a1-ai-semis-input", "mutation": "none", "reviewer_identity": "william/003/total_reviewer", "authority_boundary": package["authority_boundary"], "execution_staging_namespace_id": NAMESPACE_ID}, "all_other_scenarios": {"count": 15, "authority_issue_forbidden": True}, "templates": _runtime_templates(), "command_contracts": {"registrar": "do_not_invoke", "executor": "do_not_invoke", "baseline_rerun": "do_not_invoke", "jit_orchestrator": "do_not_invoke"}, "execution_counts": {"admission": 0, "receipt": 0, "ledger": 0, "namespace": 0, "actual": 0, "external": 0, "store_write": 0}}
    return {**payload, "blueprint_digest": _canonical(payload)}


def verify_blueprint(blueprint: Mapping[str, Any], package: Mapping[str, Any], package_gate: Mapping[str, Any], plan: Mapping[str, Any], plan_gate: Mapping[str, Any]) -> dict[str, Any]:
    payload = {key: value for key, value in blueprint.items() if key != "blueprint_digest"}
    binding = blueprint.get("exact_binding", {})
    failures = []
    if blueprint.get("blueprint_digest") != _canonical(payload): failures.append("blueprint_digest_mismatch")
    if binding.get("package_digest") != package.get("package_digest") or binding.get("package_gate_digest") != package_gate.get("gate_digest") or binding.get("plan_digest") != plan.get("plan_digest") or binding.get("plan_gate_digest") != plan_gate.get("gate_digest") or binding.get("incident_evidence") != package.get("incident_evidence"): failures.append("blueprint_cross_gate_binding_invalid")
    if blueprint.get("all_other_scenarios") != {"count": 15, "authority_issue_forbidden": True}: failures.append("blueprint_other_scenarios_invalid")
    if any(value != "do_not_invoke" for value in blueprint.get("command_contracts", {}).values()): failures.append("blueprint_command_contract_invalid")
    return {"status": "pass" if not failures else "fail_closed", "failures": failures, "calculated_blueprint_digest": _canonical(payload)}


def _gate(kind: str, target: Mapping[str, Any], verification: Mapping[str, Any], package: Mapping[str, Any]) -> dict[str, Any]:
    key = {"package": "package_digest", "plan": "plan_digest", "blueprint": "blueprint_digest"}[kind]
    payload = {"result_version": f"finsight_point01_m2_a1_v2_5_{kind}_freeze_gate_v1", "status": "pass" if verification.get("status") == "pass" else "fail_closed", "package_ref": package["package_ref"], "package_digest": package["package_digest"], "target_digest": target[key], "verification": dict(verification), "fixed_store_sha256": FIXED_SHA256, "execution_counts": {"new_admission": 0, "new_receipt": 0, "receipt_registration": 0, "receipt_consumption": 0, "actual": 0, "network": 0, "tool": 0, "model": 0, "provider": 0, "store_write": 0}, "next_step": "independent_review_required_no_authority_or_baseline"}
    return {**payload, "gate_digest": _canonical(payload)}


def build_artifacts() -> dict[str, dict[str, Any]]:
    package = build_package(); package_gate = _gate("package", package, verify_package(package), package)
    plan = build_plan(package, package_gate); plan_gate = _gate("plan", plan, verify_plan(plan, package, package_gate), package)
    blueprint = build_blueprint(package, package_gate, plan, plan_gate); blueprint_gate = _gate("blueprint", blueprint, verify_blueprint(blueprint, package, package_gate, plan, plan_gate), package)
    return {"package": package, "package_gate": package_gate, "plan": plan, "plan_gate": plan_gate, "blueprint": blueprint, "blueprint_gate": blueprint_gate}


def main() -> int:
    artifacts = build_artifacts()
    for name, path in OUTPUTS.items(): _write(path, artifacts[name])
    statuses = [artifacts[name]["status"] for name in ("package_gate", "plan_gate", "blueprint_gate")]
    print(json.dumps({"status": "phase_b0_2_dispatch_repair_refrozen_pending_independent_review" if statuses == ["pass"] * 3 else "fail_closed", "package_digest": artifacts["package"]["package_digest"], "package_gate_digest": artifacts["package_gate"]["gate_digest"], "plan_digest": artifacts["plan"]["plan_digest"], "plan_gate_digest": artifacts["plan_gate"]["gate_digest"], "blueprint_digest": artifacts["blueprint"]["blueprint_digest"], "blueprint_gate_digest": artifacts["blueprint_gate"]["gate_digest"]}, sort_keys=True))
    return 0 if statuses == ["pass"] * 3 else 1


if __name__ == "__main__":
    raise SystemExit(main())
