"""Freeze an M2-A1 receipt execution plan without creating any authority.

The plan is a static governance artifact.  It consumes only staged manifests
and the frozen scenario matrix; it never imports M2 runtime, opens a receipt
ledger, creates a namespace, or generates an admission/receipt/nonce.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = "data/manifests/point01_m2_a1_execution_ready_audit_package_manifest_v2_3.json"
PACKAGE_GATE = "data/manifests/point01_m2_a1_execution_ready_audit_package_freeze_gate_result_v2_3.json"
ADMISSION = "data/manifests/point01_m2_a1_external_package_admission_v2_3.json"
AUTHORITY_ARTIFACT = "data/manifests/point01_m2_a1_external_package_admission_authority_v2_3.json"
ADMISSION_VERIFICATION = "data/manifests/point01_m2_a1_external_package_admission_verification_v2_3.json"
MATRIX = "configs/engineering_handoff/point01_m2_a1_execution_ready_scenario_matrix_v2_1.json"
OUTPUT_PLAN = ROOT / "data/manifests/point01_m2_a1_receipt_execution_plan_v1_0.json"
OUTPUT_GATE = ROOT / "data/manifests/point01_m2_a1_receipt_execution_plan_freeze_gate_v1_0.json"

PACKAGE_DIGEST = "ff5476b9a8c4d9a82a11b163039e118922b09c945a0d53ff9df031b7c268b318"
PACKAGE_GATE_DIGEST = "904d1030c7110281acc4963ec0a615da3db0b0ce9e4a68b0d6aaf80971549243"
ADMISSION_DIGEST = "3b15556e5d71f7ad69725af4794703578115c9ed376b2ab0e010a1e57943fdef"
AUTHORITY_ARTIFACT_DIGEST = "ff483ea47a72a5738bd60227ca360cca7d372efa0c274087bc142e127a4a8fec"
VERIFICATION_DIGEST = "4e09d56e47cfc6ea73929ac120dabb186f0701eae3be8f2cfd575e550633e468"
NAMESPACE_PATH = Path("D:/temp/FIN_Insight_Agent/point01_m2_a1_exact_admitted_runs_v2_3")

GROUPS = (
    ("P01", 1, 4, "independent_oracle_reviewer_checkpoint"),
    ("P02", 5, 10, "lineage_replay_independent_oracle_reviewer_checkpoint"),
    ("P03", 11, 16, "isolation_counter_fingerprint_independent_oracle_reviewer_checkpoint"),
)
BASELINE_SCENARIO_ID = "p01-baseline-separated-input"


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _staged_bytes(relative_path: str) -> bytes:
    completed = subprocess.run(["git", "show", f":{relative_path}"], cwd=ROOT, capture_output=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"m2_a1_receipt_plan_input_not_staged:{relative_path}")
    return completed.stdout


def _staged_json(relative_path: str) -> dict[str, Any]:
    loaded = json.loads(_staged_bytes(relative_path).decode("utf-8"))
    if not isinstance(loaded, dict):
        raise RuntimeError(f"m2_a1_receipt_plan_mapping_required:{relative_path}")
    return loaded


def _digest_valid(payload: Mapping[str, Any], digest_field: str) -> bool:
    return payload.get(digest_field) == canonical_digest({key: value for key, value in payload.items() if key != digest_field})


def _planned_scenarios(matrix: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    source = matrix.get("scenarios")
    if not isinstance(source, list) or len(source) != 16:
        raise ValueError("m2_a1_receipt_plan_matrix_must_have_sixteen_scenarios")
    planned: list[dict[str, Any]] = []
    for sequence, scenario in enumerate(source, start=1):
        if not isinstance(scenario, Mapping):
            raise ValueError("m2_a1_receipt_plan_scenario_mapping_required")
        group = next((item for item in GROUPS if item[1] <= sequence <= item[2]), None)
        if group is None:
            raise ValueError("m2_a1_receipt_plan_group_assignment_invalid")
        planned.append(
            {
                "sequence": sequence,
                "group_id": group[0],
                "scenario_id": scenario["scenario_id"],
                "input_ref": scenario["input_ref"],
                "mutation": scenario["mutation"],
                "expected_typed_stop": scenario["expected_typed_stop"],
                "owner": scenario["owner"],
                "future_authority_pair": {
                    "strategy": "independent_future_admission_and_single_use_receipt_pair",
                    "admission_id_template": f"point01-m2-a1-v2-3-{scenario['scenario_id']}-admission:future_exact_review",
                    "receipt_id_template": f"point01-m2-a1-v2-3-{scenario['scenario_id']}-receipt:future_single_use",
                    "unique_admission_digest": "required_at_just_in_time_issue",
                    "unique_receipt_nonce_sha256": "required_at_just_in_time_issue",
                    "admission_ttl_minutes": 30,
                    "receipt_ttl_minutes": 15,
                    "bind_exact": [
                        "package_ref",
                        "package_digest",
                        "package_gate_digest",
                        "scenario_id",
                        "reviewer_identity",
                        "scope",
                        "authority_boundary",
                        "execution_staging_namespace_id",
                        "admission_id_and_digest",
                        "receipt_id_and_nonce_sha256",
                        "expiry",
                        "receipt_register_consume_terminal_state",
                    ],
                    "pre_generated": False,
                },
                "before_evidence": [
                    "staged_package_bytes_and_working_index_drift",
                    "fixed_approval_db_fingerprint",
                    "namespace_and_derived_run_root_absent",
                    "exact_admission_and_receipt_active_unconsumed",
                ],
                "after_evidence": [
                    "receipt_event_sequence",
                    "runtime_and_output_path_inventory",
                    "immutable_actual_digest",
                    "independent_oracle_digest",
                    "reviewer_gate_result",
                    "network_model_tool_provider_store_counters",
                ],
            }
        )
    return tuple(planned)


def verify_inputs() -> dict[str, Any]:
    package, package_gate, admission, authority, verification, matrix = (
        _staged_json(path) for path in (PACKAGE, PACKAGE_GATE, ADMISSION, AUTHORITY_ARTIFACT, ADMISSION_VERIFICATION, MATRIX)
    )
    failures: list[str] = []
    if not _digest_valid(package, "package_digest") or package.get("package_digest") != PACKAGE_DIGEST:
        failures.append("package_digest_mismatch")
    if not _digest_valid(package_gate, "gate_digest") or package_gate.get("gate_digest") != PACKAGE_GATE_DIGEST:
        failures.append("package_gate_digest_mismatch")
    if not _digest_valid(admission, "admission_digest") or admission.get("admission_digest") != ADMISSION_DIGEST:
        failures.append("admission_digest_mismatch")
    if not _digest_valid(authority, "authority_artifact_digest") or authority.get("authority_artifact_digest") != AUTHORITY_ARTIFACT_DIGEST:
        failures.append("authority_artifact_digest_mismatch")
    if not _digest_valid(verification, "verification_digest") or verification.get("verification_digest") != VERIFICATION_DIGEST:
        failures.append("verification_digest_mismatch")
    if verification.get("status") != "pass" or authority.get("execution_receipt_status") != "not_created_not_registered_not_consumed":
        failures.append("current_admission_artifact_not_execution_unused")
    if admission.get("executable_package_digest") != PACKAGE_DIGEST or authority.get("runtime_admission_digest") != ADMISSION_DIGEST or verification.get("runtime_admission_digest") != ADMISSION_DIGEST:
        failures.append("admission_package_binding_mismatch")
    if package_gate.get("package_digest") != PACKAGE_DIGEST or verification.get("package_gate_digest") != PACKAGE_GATE_DIGEST:
        failures.append("package_gate_binding_mismatch")
    if matrix.get("schema_version") != "finsight_point01_m2_a1_execution_ready_scenario_matrix_v2_1":
        failures.append("scenario_matrix_schema_mismatch")
    try:
        planned = _planned_scenarios(matrix)
    except (KeyError, TypeError, ValueError) as exc:
        failures.append(str(exc))
        planned = ()
    if planned and planned[0]["scenario_id"] != BASELINE_SCENARIO_ID:
        failures.append("baseline_first_scenario_mismatch")
    if NAMESPACE_PATH.exists():
        failures.append("runtime_namespace_must_be_absent_for_plan_freeze")
    return {
        "status": "pass" if not failures else "fail_closed",
        "failures": sorted(set(failures)),
        "package": package,
        "package_gate": package_gate,
        "admission": admission,
        "authority": authority,
        "verification": verification,
        "matrix": matrix,
        "planned_scenarios": planned,
    }


def build_plan() -> dict[str, Any]:
    inputs = verify_inputs()
    if inputs["status"] != "pass":
        raise RuntimeError(f"m2_a1_receipt_plan_input_fail_closed:{','.join(inputs['failures'])}")
    package = inputs["package"]
    payload = {
        "schema_version": "finsight_point01_m2_a1_receipt_execution_plan_v1_0",
        "status": "receipt_execution_plan_design_frozen_pending_baseline_authority_approval",
        "scope": "M2_A1_receipt_plan_design_only_no_admission_receipt_ledger_namespace_or_actual",
        "exact_package": {
            "package_ref": package["package_ref"],
            "package_digest": package["package_digest"],
            "package_gate_digest": PACKAGE_GATE_DIGEST,
            "scope": package["scope"],
            "authority_boundary": package["authority_boundary"],
            "reviewer_identity": "william/003/total_reviewer",
            "execution_staging_namespace_id": package["execution_preflight"]["execution_staging_namespace_id"],
        },
        "current_admission_artifact_disposition": {
            "runtime_admission_digest": ADMISSION_DIGEST,
            "authority_artifact_digest": AUTHORITY_ARTIFACT_DIGEST,
            "verification_digest": VERIFICATION_DIGEST,
            "status": "artifact_integrity_accepted_execution_unused_expiry_pending_or_expired",
            "execution_receipt_forbidden": True,
            "expiry_policy": "never_extend_or_reuse_old_expiry_nonce_or_digest; after expiry mark expired_for_execution and seek a new exact external admission artifact",
        },
        "ledger_constraint": {
            "known_constraint": "point01_m2_a1_execution_receipts.admission_digest_is_unique",
            "consequence": "one_admission_can_register_only_one_receipt_and_one_scenario",
            "chosen_strategy": "independent_future_admission_and_single_use_receipt_pair_per_scenario",
            "forbidden_strategy": "one_admission_plus_sixteen_receipts",
            "schema_migration": "not_authorized_by_this_plan",
        },
        "just_in_time_authority": {
            "only_current_scenario_pair_may_be_issued_or_registered": True,
            "no_batch_pre_generation_of_active_admissions_or_receipts": True,
            "baseline_first": BASELINE_SCENARIO_ID,
            "authorization_renewal": "new_external_review_and_new_digests_only; never mutate_expiry_or_reuse_old_digest",
        },
        "scenario_execution_order": list(inputs["planned_scenarios"]),
        "group_checkpoints": [
            {
                "group_id": group_id,
                "sequences": [start, end],
                "after_scenario_id": inputs["planned_scenarios"][end - 1]["scenario_id"],
                "required_gate": checkpoint,
                "failure_action": "stop_this_group_and_all_later_groups_no_retry_or_replay",
            }
            for group_id, start, end, checkpoint in GROUPS
        ],
        "baseline_gate": {
            "scenario_id": BASELINE_SCENARIO_ID,
            "required_before_next_authority": [
                "actual_terminal_and_immutable_digest",
                "independent_oracle_pass",
                "reviewer_gate_pass",
                "fixed_fingerprint_unchanged",
                "all_counters_within_authorized_zero_or_expected_typed_stop_contract",
            ],
            "failure_action": "stop_all_remaining_scenarios_and_do_not_issue_next_authority",
        },
        "runner_isolation": {
            "actual_runner_input": ["exact_package", "preflight_bound_corpus_case", "scenario_id", "input_ref", "mutation", "current_exact_admission_and_receipt"],
            "actual_runner_forbidden_input": ["reviewer_oracle", "reviewer_expected_values", "ambient_store", "fixed_store", "provider_or_network_client"],
            "oracle_evaluator_input": ["immutable_actual_result_after_terminalization", "reviewer_oracle", "scenario_oracle_assertions"],
            "reviewer_gate_input": ["actual_digest", "oracle_digest", "receipt_event_sequence", "counter_snapshot", "fixed_fingerprint_before_after"],
        },
        "fail_fast": {
            "on_actual_or_oracle_or_reviewer_or_lineage_or_counter_or_fingerprint_failure": "terminal_stop_no_retry_no_replay_no_next_authority",
            "on_admission_or_receipt_expiry": "discard_for_execution_and_seek_new_exact_review",
        },
        "retention_and_cleanup": {
            "authority_runtime_output": "immutable_retained_until_independent_closeout_policy",
            "cleanup_before_closeout": "forbidden",
            "cleanup_after_closeout": "separate_policy_and_audit_required",
        },
        "execution_counts": {
            "future_admissions_created": 0,
            "future_receipts_created": 0,
            "receipt_registrations": 0,
            "receipt_consumptions": 0,
            "runtime_namespaces_created": 0,
            "a0_m2_actual_probes": 0,
            "compiler_or_shadow_fixture_runs": 0,
            "network_requests": 0,
            "model_calls": 0,
            "external_tool_calls": 0,
            "provider_calls": 0,
            "fixed_or_production_store_opens": 0,
            "store_writes": 0,
            "business_case_mutations": 0,
            "legacy_authority_mutations": 0,
        },
    }
    return {**payload, "plan_digest": canonical_digest(payload)}


def validate_plan(plan: Mapping[str, Any]) -> dict[str, bool]:
    payload = {key: value for key, value in plan.items() if key != "plan_digest"}
    scenarios = plan.get("scenario_execution_order")
    ids = [item.get("scenario_id") for item in scenarios] if isinstance(scenarios, list) else []
    all_zero = isinstance(plan.get("execution_counts"), Mapping) and all(value == 0 for value in plan["execution_counts"].values())
    return {
        "plan_digest_exact": plan.get("plan_digest") == canonical_digest(payload),
        "plan_status_and_scope": plan.get("status") == "receipt_execution_plan_design_frozen_pending_baseline_authority_approval" and plan.get("scope") == "M2_A1_receipt_plan_design_only_no_admission_receipt_ledger_namespace_or_actual",
        "current_artifact_execution_unused": isinstance(plan.get("current_admission_artifact_disposition"), Mapping) and plan["current_admission_artifact_disposition"].get("status") == "artifact_integrity_accepted_execution_unused_expiry_pending_or_expired" and plan["current_admission_artifact_disposition"].get("execution_receipt_forbidden") is True,
        "unique_pair_strategy": isinstance(plan.get("ledger_constraint"), Mapping) and plan["ledger_constraint"].get("chosen_strategy") == "independent_future_admission_and_single_use_receipt_pair_per_scenario" and plan["ledger_constraint"].get("forbidden_strategy") == "one_admission_plus_sixteen_receipts",
        "sixteen_fixed_scenarios": len(ids) == 16 and len(set(ids)) == 16 and ids[0] == BASELINE_SCENARIO_ID,
        "group_coverage_4_6_6": isinstance(plan.get("group_checkpoints"), list) and [item.get("sequences") for item in plan["group_checkpoints"]] == [[1, 4], [5, 10], [11, 16]],
        "baseline_first_checkpoint": isinstance(plan.get("baseline_gate"), Mapping) and plan["baseline_gate"].get("scenario_id") == BASELINE_SCENARIO_ID,
        "just_in_time_only": isinstance(plan.get("just_in_time_authority"), Mapping) and plan["just_in_time_authority"].get("only_current_scenario_pair_may_be_issued_or_registered") is True and plan["just_in_time_authority"].get("no_batch_pre_generation_of_active_admissions_or_receipts") is True,
        "execution_counts_zero": all_zero,
        "runtime_namespace_absent": not NAMESPACE_PATH.exists(),
    }


def build_gate(plan: Mapping[str, Any]) -> dict[str, Any]:
    checks = validate_plan(plan)
    input_check = verify_inputs()
    if input_check["status"] != "pass":
        checks["inputs_exact"] = False
    else:
        checks["inputs_exact"] = True
    payload = {
        "result_version": "finsight_point01_m2_a1_receipt_execution_plan_freeze_gate_v1_0",
        "status": "pass" if all(checks.values()) else "fail_closed",
        "plan_digest": plan.get("plan_digest"),
        "checks": checks,
        "scenario_group_coverage": {"P01": 4, "P02": 6, "P03": 6},
        "execution_counts": plan.get("execution_counts"),
        "next_step": "Stop. Only approve a just-in-time baseline scenario authority pair after independent review of this plan.",
    }
    return {**payload, "gate_digest": canonical_digest(payload)}


def _write(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    plan = build_plan()
    gate = build_gate(plan)
    _write(OUTPUT_PLAN, plan)
    _write(OUTPUT_GATE, gate)
    print(json.dumps({"status": gate["status"], "plan_digest": plan["plan_digest"], "gate_digest": gate["gate_digest"], "future_receipts_created": 0}, ensure_ascii=False))
    return 0 if gate["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
