"""Freeze a non-active authority blueprint for the first M2-A1 scenario.

This is deliberately a design artifact, not an issuer, registrar, or executor.
It consumes the already-staged v2.3 package, receipt execution plan, and
scenario matrix; it never creates a nonce, timestamp, admission, receipt,
ledger, run root, or runtime output.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = "data/manifests/point01_m2_a1_execution_ready_audit_package_manifest_v2_3.json"
PACKAGE_GATE = "data/manifests/point01_m2_a1_execution_ready_audit_package_freeze_gate_result_v2_3.json"
PLAN = "data/manifests/point01_m2_a1_receipt_execution_plan_v1_0.json"
PLAN_GATE = "data/manifests/point01_m2_a1_receipt_execution_plan_freeze_gate_v1_0.json"
MATRIX = "configs/engineering_handoff/point01_m2_a1_execution_ready_scenario_matrix_v2_1.json"
OLD_ADMISSION = "data/manifests/point01_m2_a1_external_package_admission_v2_3.json"
OLD_AUTHORITY = "data/manifests/point01_m2_a1_external_package_admission_authority_v2_3.json"
OLD_VERIFICATION = "data/manifests/point01_m2_a1_external_package_admission_verification_v2_3.json"
OUTPUT_BLUEPRINT = ROOT / "data/manifests/point01_m2_a1_baseline_authority_blueprint_v1_0.json"
OUTPUT_GATE = ROOT / "data/manifests/point01_m2_a1_baseline_authority_blueprint_freeze_gate_v1_0.json"

PACKAGE_DIGEST = "ff5476b9a8c4d9a82a11b163039e118922b09c945a0d53ff9df031b7c268b318"
PACKAGE_GATE_DIGEST = "904d1030c7110281acc4963ec0a615da3db0b0ce9e4a68b0d6aaf80971549243"
PLAN_DIGEST = "9a0e16878bb899b853e2d91d84a5771d69b4b7d49cd37a490cc20d2de7ca4f5a"
PLAN_GATE_DIGEST = "7e6ab5fc460678a506e7f5cd7cf71d7ff1f5c826b5abc1e6589a4c38e1878fa1"
PACKAGE_REF = "point01-m2-a1-receipt-invariants-adversarial-audit-package-v2-3"
SCOPE = "M2_A1_exact_admission_gated_future_actual_only"
AUTHORITY_BOUNDARY = "no_actual_a0_m2_probe_without_exact_external_admission_and_single_use_receipt_no_model_network_tool_provider_fixed_production_business_or_legacy_mutation"
NAMESPACE_ID = "point01_m2_a1_exact_admitted_runs_v2_3"
OLD_ADMISSION_DIGEST = "3b15556e5d71f7ad69725af4794703578115c9ed376b2ab0e010a1e57943fdef"
OLD_AUTHORITY_DIGEST = "ff483ea47a72a5738bd60227ca360cca7d372efa0c274087bc142e127a4a8fec"
OLD_VERIFICATION_DIGEST = "4e09d56e47cfc6ea73929ac120dabb186f0701eae3be8f2cfd575e550633e468"
BASELINE = "p01-baseline-separated-input"
REVIEWER = "william/003/total_reviewer"
SHA256 = re.compile(r"^[0-9a-f]{64}$")
UTC_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _staged_json(relative_path: str) -> dict[str, Any]:
    completed = subprocess.run(["git", "show", f":{relative_path}"], cwd=ROOT, capture_output=True, check=False)
    if completed.returncode:
        raise RuntimeError(f"m2_a1_baseline_blueprint_input_not_staged:{relative_path}")
    loaded = json.loads(completed.stdout.decode("utf-8"))
    if not isinstance(loaded, dict):
        raise RuntimeError(f"m2_a1_baseline_blueprint_mapping_required:{relative_path}")
    return loaded


def _digest_exact(payload: Mapping[str, Any], field: str) -> bool:
    return payload.get(field) == canonical_digest({key: value for key, value in payload.items() if key != field})


def _unresolved(value: Any) -> bool:
    return isinstance(value, str) and value.startswith("<unresolved_") and value.endswith("_not_active>")


def _template_dynamic_values(blueprint: Mapping[str, Any]) -> tuple[Any, ...]:
    templates = blueprint.get("runtime_compatible_templates")
    if not isinstance(templates, Mapping):
        return ()
    admission = templates.get("external_admission")
    authority = templates.get("authority_wrapper")
    receipt = templates.get("execution_receipt")
    if not all(isinstance(value, Mapping) for value in (admission, authority, receipt)):
        return ()
    return (
        admission.get("admission_id"),
        admission.get("admission_version"),
        admission.get("decision"),
        admission.get("expires_at"),
        admission.get("admission_digest"),
        authority.get("issued_at"),
        authority.get("expires_at"),
        authority.get("runtime_admission_digest"),
        authority.get("nonce_sha256"),
        authority.get("authority_artifact_digest"),
        receipt.get("receipt_id"),
        receipt.get("receipt_version"),
        receipt.get("approval_id"),
        receipt.get("admission_digest"),
        receipt.get("nonce_sha256"),
        receipt.get("expires_at"),
        receipt.get("state"),
        receipt.get("receipt_digest"),
    )


def verify_inputs() -> dict[str, Any]:
    package, package_gate, plan, plan_gate, matrix, old_admission, old_authority, old_verification = (
        _staged_json(path)
        for path in (PACKAGE, PACKAGE_GATE, PLAN, PLAN_GATE, MATRIX, OLD_ADMISSION, OLD_AUTHORITY, OLD_VERIFICATION)
    )
    failures: list[str] = []
    exact = (
        (package, "package_digest", PACKAGE_DIGEST),
        (package_gate, "gate_digest", PACKAGE_GATE_DIGEST),
        (plan, "plan_digest", PLAN_DIGEST),
        (plan_gate, "gate_digest", PLAN_GATE_DIGEST),
        (old_admission, "admission_digest", OLD_ADMISSION_DIGEST),
        (old_authority, "authority_artifact_digest", OLD_AUTHORITY_DIGEST),
        (old_verification, "verification_digest", OLD_VERIFICATION_DIGEST),
    )
    for payload, field, expected in exact:
        if not _digest_exact(payload, field) or payload.get(field) != expected:
            failures.append(f"{field}_mismatch")
    if package.get("package_ref") != PACKAGE_REF:
        failures.append("package_ref_mismatch")
    if package_gate.get("package_digest") != PACKAGE_DIGEST:
        failures.append("package_gate_binding_mismatch")
    if plan_gate.get("plan_digest") != PLAN_DIGEST or plan_gate.get("status") != "pass":
        failures.append("plan_gate_binding_mismatch")
    if plan.get("status") != "receipt_execution_plan_design_frozen_pending_baseline_authority_approval":
        failures.append("plan_status_mismatch")
    scenarios = matrix.get("scenarios")
    if not isinstance(scenarios, list) or len(scenarios) != 16:
        failures.append("scenario_matrix_not_sixteen")
        baseline: Mapping[str, Any] = {}
    else:
        baseline = scenarios[0] if isinstance(scenarios[0], Mapping) else {}
        if baseline.get("scenario_id") != BASELINE or baseline.get("input_ref") != "m2-a1-ai-semis-input" or baseline.get("mutation") != "none":
            failures.append("baseline_scenario_binding_mismatch")
    plan_scenarios = plan.get("scenario_execution_order")
    if not isinstance(plan_scenarios, list) or len(plan_scenarios) != 16 or not isinstance(plan_scenarios[0], Mapping):
        failures.append("plan_scenario_order_missing")
    elif plan_scenarios[0].get("scenario_id") != BASELINE or plan_scenarios[0].get("input_ref") != baseline.get("input_ref"):
        failures.append("plan_matrix_baseline_mismatch")
    if old_admission.get("expires_at") != "2026-07-13T23:45:32.089653Z":
        failures.append("old_admission_expiry_evidence_mismatch")
    if old_authority.get("execution_receipt_status") != "not_created_not_registered_not_consumed":
        failures.append("old_admission_receipt_state_mismatch")
    return {
        "status": "pass" if not failures else "fail_closed",
        "failures": sorted(set(failures)),
        "package": package,
        "package_gate": package_gate,
        "plan": plan,
        "plan_gate": plan_gate,
        "baseline": dict(baseline),
    }


def build_blueprint() -> dict[str, Any]:
    inputs = verify_inputs()
    if inputs["status"] != "pass":
        raise RuntimeError(f"m2_a1_baseline_blueprint_input_fail_closed:{','.join(inputs['failures'])}")
    package = inputs["package"]
    baseline = inputs["baseline"]
    exact_binding = {
        "package_ref": package["package_ref"],
        "package_digest": PACKAGE_DIGEST,
        "package_gate_digest": PACKAGE_GATE_DIGEST,
        "receipt_execution_plan_digest": PLAN_DIGEST,
        "receipt_execution_plan_gate_digest": PLAN_GATE_DIGEST,
        "scenario_id": BASELINE,
        "input_ref": baseline["input_ref"],
        "mutation": baseline["mutation"],
        "reviewer_identity": REVIEWER,
        "scope": package["scope"],
        "authority_boundary": package["authority_boundary"],
        "execution_staging_namespace_id": package["execution_preflight"]["execution_staging_namespace_id"],
    }
    payload = {
        "schema_version": "finsight_point01_m2_a1_baseline_authority_blueprint_v1_0",
        "status": "baseline_authority_blueprint_design_frozen_pending_independent_review",
        "authority_mode": "blueprint_only_not_active_not_issuable_not_registerable_not_executable",
        "target": {"scenario_id": BASELINE, "input_ref": baseline["input_ref"], "mutation": baseline["mutation"], "sequence": 1, "group_id": "P01"},
        "all_other_scenarios": {"count": 15, "status": "blocked_pending_baseline_actual_oracle_reviewer_checkpoint", "authority_issue_forbidden": True},
        "exact_binding": exact_binding,
        "old_admission_artifacts": {
            "runtime_admission_digest": OLD_ADMISSION_DIGEST,
            "authority_artifact_digest": OLD_AUTHORITY_DIGEST,
            "verification_digest": OLD_VERIFICATION_DIGEST,
            "status": "expired_execution_unused",
            "receipt_registration_forbidden": True,
            "expiry_or_digest_amendment_forbidden": True,
        },
        "runtime_compatible_templates": {
            "template_mode": "schema_field_compatible_but_unresolved_not_active",
            "external_admission": {
                "schema_version": "finsight_point01_m2_a1_external_package_admission_v2_3",
                "admission_ref": "<unresolved_total_reviewer_admission_ref_not_active>",
                "admission_id": "<unresolved_unique_admission_id_not_active>",
                "admission_version": "<unresolved_admission_version_not_active>",
                "reviewer_identity": REVIEWER,
                "decision": "<unresolved_admitted_decision_not_active>",
                "package_ref": package["package_ref"],
                "executable_package_digest": PACKAGE_DIGEST,
                "scope": package["scope"],
                "authority_boundary": package["authority_boundary"],
                "execution_staging_namespace_id": package["execution_preflight"]["execution_staging_namespace_id"],
                "execution_mode": "external_admission_gated",
                "expires_at": "<unresolved_admission_expiry_utc_not_active>",
                "admission_digest": "<unresolved_admission_digest_not_active>",
            },
            "authority_wrapper": {
                "schema_version": "finsight_point01_m2_a1_external_package_admission_authority_v2_3",
                "artifact_kind": "<unresolved_authority_artifact_kind_not_active>",
                "reviewer_identity": REVIEWER,
                "decision": "<unresolved_admitted_decision_not_active>",
                "issued_at": "<unresolved_issued_at_utc_not_active>",
                "expires_at": "<unresolved_admission_expiry_utc_not_active>",
                "package_ref": package["package_ref"],
                "package_digest": PACKAGE_DIGEST,
                "package_gate_digest": PACKAGE_GATE_DIGEST,
                "scope": package["scope"],
                "authority_boundary": package["authority_boundary"],
                "execution_staging_namespace_id": package["execution_preflight"]["execution_staging_namespace_id"],
                "runtime_admission_digest": "<unresolved_admission_digest_not_active>",
                "nonce_sha256": "<unresolved_nonce_sha256_not_active>",
                "execution_receipt_status": "<unresolved_not_created_not_registered_not_consumed_not_active>",
                "authority_artifact_digest": "<unresolved_authority_artifact_digest_not_active>",
                "raw_nonce_persisted": False,
                "user_agent_persisted": False,
            },
            "execution_receipt": {
                "schema_version": "finsight_point01_m2_a1_single_use_execution_receipt_v2_3",
                "receipt_id": "<unresolved_unique_receipt_id_not_active>",
                "receipt_version": "<unresolved_receipt_version_not_active>",
                "approval_id": "<unresolved_approval_id_not_active>",
                "package_ref": package["package_ref"],
                "executable_package_digest": PACKAGE_DIGEST,
                "scope": package["scope"],
                "admission_digest": "<unresolved_admission_digest_not_active>",
                "nonce_sha256": "<unresolved_nonce_sha256_not_active>",
                "expires_at": "<unresolved_receipt_expiry_utc_not_active>",
                "reviewer_identity": REVIEWER,
                "execution_staging_namespace_id": package["execution_preflight"]["execution_staging_namespace_id"],
                "scenario_id": BASELINE,
                "state": "<unresolved_active_unconsumed_state_not_active>",
                "single_use": True,
                "receipt_digest": "<unresolved_receipt_digest_not_active>",
            },
        },
        "command_contracts": {
            "registrar": {
                "entrypoint": "scripts/engineering/run_point01_m2_a1_receipt_registrar.py",
                "argv_template": ["python", "scripts/engineering/run_point01_m2_a1_receipt_registrar.py", "--register-exact-receipt", "--admission", "<unresolved_admission_json_path_not_active>", "--receipt", "<unresolved_receipt_json_path_not_active>", "--scenario-id", BASELINE],
                "blueprint_mode": "do_not_invoke",
                "invocation_permitted": False,
                "allowed_effect_when_future_approved": "authority_root_and_receipt_ledger_only",
            },
            "executor": {
                "entrypoint": "scripts/engineering/run_point01_m2_a1_actual_audit.py",
                "argv_template": ["python", "scripts/engineering/run_point01_m2_a1_actual_audit.py", "--execute-admitted", "--admission", "<unresolved_admission_json_path_not_active>", "--receipt-id", "<unresolved_receipt_id_not_active>", "--scenario-id", BASELINE],
                "blueprint_mode": "do_not_invoke",
                "invocation_permitted": False,
                "required_future_order": ["existing_ledger_no_create_open", "atomic_consume", "staged_tree_reverify", "grant_verify", "runtime_output_materialize", "M2_import", "execute"],
            },
        },
        "just_in_time_issuance_contract": {
            "admission_ttl_minutes": 30,
            "receipt_ttl_minutes": 15,
            "receipt_expiry_must_not_exceed_admission_expiry": True,
            "no_pair_pre_generation_while_waiting_for_human_or_heartbeat": True,
            "future_order": ["issue", "verify", "register", "preflight", "consume", "reverify", "grant_verify", "materialize", "execute"],
            "next_authority_after_baseline": "independent_review_required_not_automatic",
        },
        "baseline_post_run_pipeline": {
            "actual_runner": "terminalize_immutable_actual_before_oracle",
            "oracle_evaluator": "reads_oracle_only_after_actual_terminalization",
            "reviewer_gate": "requires_actual_oracle_and_boundary_evidence",
            "before_after_evidence": ["fixed_fingerprint_before_after", "staged_bytes_and_working_index_drift", "receipt_events", "authority_runtime_output_paths", "counter_snapshot"],
            "exception_semantics": "outcome_unknown_or_fail_fast_no_retry_no_replay",
        },
        "isolation": {
            "authority_issuer_forbidden_from": ["actual_runner_import", "compiler_or_shadow_execution", "oracle_evaluator_input"],
            "actual_runner_forbidden_from": ["blueprint_reviewer_expectations", "reviewer_oracle", "expected_typed_stop"],
            "oracle_evaluator_starts_after": "immutable_actual_terminalization",
            "reviewer_gate_input": ["actual_digest", "oracle_digest", "receipt_events", "before_after_fingerprints", "counter_snapshot"],
        },
        "execution_counts": {"active_admissions_created": 0, "active_receipts_created": 0, "receipt_registrations": 0, "receipt_consumptions": 0, "ledgers_created": 0, "runtime_namespaces_created": 0, "actual_probes": 0, "compiler_shadow_runs": 0, "network": 0, "model": 0, "tool": 0, "provider": 0, "fixed_or_production_store_open": 0, "store_writes": 0, "business_case_mutations": 0, "legacy_authority_mutations": 0},
    }
    return {**payload, "blueprint_digest": canonical_digest(payload)}


def validate_blueprint(blueprint: Mapping[str, Any]) -> dict[str, bool]:
    payload = {key: value for key, value in blueprint.items() if key != "blueprint_digest"}
    binding = blueprint.get("exact_binding")
    templates = blueprint.get("runtime_compatible_templates")
    lifecycle = blueprint.get("just_in_time_issuance_contract")
    commands = blueprint.get("command_contracts")
    counts = blueprint.get("execution_counts")
    dynamic = _template_dynamic_values(blueprint)
    command_values = tuple(value for contract in commands.values() if isinstance(commands, Mapping) and isinstance(contract, Mapping) for value in (contract.get("blueprint_mode"), contract.get("invocation_permitted"))) if isinstance(commands, Mapping) else ()
    admission_template = templates.get("external_admission") if isinstance(templates, Mapping) else None
    authority_template = templates.get("authority_wrapper") if isinstance(templates, Mapping) else None
    receipt_template = templates.get("execution_receipt") if isinstance(templates, Mapping) else None
    required_admission_fields = {
        "schema_version", "admission_ref", "admission_id", "admission_version", "reviewer_identity", "decision", "package_ref", "executable_package_digest", "scope", "authority_boundary", "execution_staging_namespace_id", "execution_mode", "expires_at", "admission_digest",
    }
    required_receipt_fields = {
        "schema_version", "receipt_id", "receipt_version", "approval_id", "package_ref", "executable_package_digest", "scope", "admission_digest", "nonce_sha256", "expires_at", "reviewer_identity", "execution_staging_namespace_id", "scenario_id", "state", "single_use", "receipt_digest",
    }
    return {
        "blueprint_digest_exact": blueprint.get("blueprint_digest") == canonical_digest(payload),
        "baseline_only": isinstance(blueprint.get("target"), Mapping) and blueprint["target"].get("scenario_id") == BASELINE and isinstance(blueprint.get("all_other_scenarios"), Mapping) and blueprint["all_other_scenarios"].get("count") == 15 and blueprint["all_other_scenarios"].get("authority_issue_forbidden") is True,
        "exact_binding": isinstance(binding, Mapping) and binding == {
            "package_ref": PACKAGE_REF,
            "package_digest": PACKAGE_DIGEST,
            "package_gate_digest": PACKAGE_GATE_DIGEST,
            "receipt_execution_plan_digest": PLAN_DIGEST,
            "receipt_execution_plan_gate_digest": PLAN_GATE_DIGEST,
            "scenario_id": BASELINE,
            "input_ref": "m2-a1-ai-semis-input",
            "mutation": "none",
            "reviewer_identity": REVIEWER,
            "scope": SCOPE,
            "authority_boundary": AUTHORITY_BOUNDARY,
            "execution_staging_namespace_id": NAMESPACE_ID,
        },
        "old_admission_expired_unused": isinstance(blueprint.get("old_admission_artifacts"), Mapping) and blueprint["old_admission_artifacts"].get("status") == "expired_execution_unused" and blueprint["old_admission_artifacts"].get("receipt_registration_forbidden") is True,
        "templates_runtime_field_compatible": isinstance(admission_template, Mapping) and required_admission_fields == set(admission_template) and isinstance(authority_template, Mapping) and authority_template.get("schema_version") == "finsight_point01_m2_a1_external_package_admission_authority_v2_3" and isinstance(receipt_template, Mapping) and required_receipt_fields == set(receipt_template),
        "templates_unresolved_not_active": isinstance(templates, Mapping) and templates.get("template_mode") == "schema_field_compatible_but_unresolved_not_active" and len(dynamic) == 18 and all(_unresolved(value) for value in dynamic) and not any(SHA256.fullmatch(value) or UTC_TIMESTAMP.fullmatch(value) for value in dynamic if isinstance(value, str)),
        "receipt_ttl_bounded": isinstance(lifecycle, Mapping) and lifecycle.get("admission_ttl_minutes") == 30 and lifecycle.get("receipt_ttl_minutes") == 15 and lifecycle.get("receipt_expiry_must_not_exceed_admission_expiry") is True,
        "jit_order_and_commands_noninvocable": isinstance(lifecycle, Mapping) and lifecycle.get("future_order") == ["issue", "verify", "register", "preflight", "consume", "reverify", "grant_verify", "materialize", "execute"] and command_values == ("do_not_invoke", False, "do_not_invoke", False),
        "zero_execution_counts": isinstance(counts, Mapping) and all(value == 0 for value in counts.values()),
    }


def build_gate(blueprint: Mapping[str, Any]) -> dict[str, Any]:
    checks = validate_blueprint(blueprint)
    inputs = verify_inputs()
    checks["staged_inputs_exact"] = inputs["status"] == "pass"
    payload = {
        "result_version": "finsight_point01_m2_a1_baseline_authority_blueprint_freeze_gate_v1_0",
        "status": "pass" if all(checks.values()) else "fail_closed",
        "blueprint_digest": blueprint.get("blueprint_digest"),
        "checks": checks,
        "execution_counts": blueprint.get("execution_counts"),
        "next_step": "Stop. An independent reviewer must approve one just-in-time baseline admission/receipt issue-register-execute window; this blueprint itself cannot issue authority.",
    }
    return {**payload, "gate_digest": canonical_digest(payload)}


def _write(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    blueprint = build_blueprint()
    gate = build_gate(blueprint)
    _write(OUTPUT_BLUEPRINT, blueprint)
    _write(OUTPUT_GATE, gate)
    print(json.dumps({"status": gate["status"], "blueprint_digest": blueprint["blueprint_digest"], "gate_digest": gate["gate_digest"], "active_authority_created": 0}, ensure_ascii=False))
    return 0 if gate["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
