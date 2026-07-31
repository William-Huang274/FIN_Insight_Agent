from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_executor import (
    S3_OWNER_GRADE_VERIFIER_STATE_MACHINE_REF,
    S3ThreeCellBoundedAgentAdmission,
)
from scripts.releases.prepare_fin_ia_0_1_s3_t09_claim_fact_link_policy_fresh_exact_proof import (
    prepare as prepare_claim_fact_proof,
)
from scripts.releases.supervise_fin_ia_0_1_s3_t09_exact_live_execution import (
    SUPERVISION_CONTRACT_REF,
)


RELEASES = ROOT / "configs" / "releases"
RUNTIME_ROOT = (
    ROOT
    / ".codex_runtime"
    / "fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1"
)
IMPLEMENTATION_RESULT = RELEASES / (
    "fin_ia_0_1_s3_t09_atomic_terminalization_and_typed_"
    "verifier_state_machine_zero_call_implementation_v1_0.json"
)
CLAIM_FACT_IMPLEMENTATION_RESULT = RELEASES / (
    "fin_ia_0_1_s3_t09_claim_fact_link_policy_closed_alias_"
    "zero_call_implementation_v1_0.json"
)
PROFILE_V3_FINAL_FAILURE_RESULT = RELEASES / (
    "fin_ia_0_1_s3_t09_research_lead_v5_profile_v3_final_"
    "exact_live_execution_result_v1_0.json"
)
CLAIM_FACT_LIVE_FAILURE_RESULT = RELEASES / (
    "fin_ia_0_1_s3_t09_claim_fact_link_policy_fresh_exact_"
    "live_execution_result_v1_0.json"
)
OUTPUT_V4_ORPHAN_CLOSEOUT_RESULT = RELEASES / (
    "fin_ia_0_1_s3_t09_output_v4_verifier_schema_repair_"
    "orphan_typed_closeout_result_v1_0.json"
)
EXECUTION_IDENTITY = (
    "fin01-s3-t09-three-cell-deepseek-atomic-terminalization-"
    "verifier-state-machine-supervised-live-validation-r1"
)
PROSPECTIVE_ADMISSION_ID = (
    "fin01-s3-t09-three-cell-deepseek-atomic-terminalization-"
    "verifier-state-machine-supervised-exact-admission-r1"
)
PROSPECTIVE_ADMISSION_FILE = (
    "configs/releases/fin_ia_0_1_s3_t09_three_cell_deepseek_"
    "atomic_terminalization_verifier_state_machine_supervised_"
    "exact_admission_r1.json"
)
DECISION_STATUS = (
    "pass_zero_call_atomic_terminalization_typed_verifier_state_machine_"
    "supervised_fresh_exact_proof_contract_frozen_admission_issuance_"
    "pending_separate_authority"
)
DECISION_CONTRACT_REF = (
    "fin01.s3.atomic_terminalization_typed_verifier_state_machine_"
    "supervised_fresh_exact_proof_decision:v1"
)
NEXT_ACTION = (
    "S3-T09-ATOMIC-CAPTURE-FAILURE-TERMINALIZATION-AND-TYPED-"
    "VERIFIER-STATE-MACHINE-FRESH-EXACT-ADMISSION-ISSUANCE"
)
IMPLEMENTATION_STATUS = (
    "pass_zero_call_atomic_failure_terminalization_typed_verifier_"
    "state_machine_safe_telemetry_and_supervised_runner_fixture_proven"
)
MINIMUM_LIFECYCLE_BUDGET_SECONDS = 1_560

CODE_BINDING_PATHS = (
    Path("apps/workbench/backend/application/research_runtime.py"),
    Path("apps/workbench/backend/application/bounded_agent_executor.py"),
    Path("src/sec_agent/canonical_runtime/facade.py"),
    Path(
        "scripts/releases/"
        "supervise_fin_ia_0_1_s3_t09_exact_live_execution.py"
    ),
    Path(
        "scripts/releases/"
        "run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution.py"
    ),
)


class AtomicTerminalizationFreshProofDecisionError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise AtomicTerminalizationFreshProofDecisionError(code)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def prepare(
    *,
    runtime_root: Path = RUNTIME_ROOT,
    implementation_result_path: Path = IMPLEMENTATION_RESULT,
) -> dict[str, Any]:
    implementation = json.loads(
        implementation_result_path.read_text(encoding="utf-8")
    )
    _require(
        implementation.get("status") == IMPLEMENTATION_STATUS,
        "atomic_terminalization_implementation_not_fixture_proven",
    )
    _require(
        set((implementation.get("observed_counts") or {}).values()) == {0},
        "atomic_terminalization_implementation_not_zero_call",
    )

    implemented = implementation.get("implementation") or {}
    atomic = implemented.get("atomic_failure_terminalization") or {}
    state_machine = implemented.get("typed_verifier_state_machine") or {}
    telemetry = implemented.get("safe_failure_telemetry") or {}
    supervision = implemented.get("supervised_exact_runner") or {}
    deterministic = implementation.get("deterministic_acceptance") or {}
    _require(
        atomic.get("runtime_exception_path_command_count") == 1
        and atomic.get("command_type") == "FAIL_RESEARCH_RUN"
        and atomic.get("command_carries_provider_output_captures") is True
        and atomic.get("separate_preterminal_capture_command_used") is False
        and atomic.get("capture_refs_bound_to_terminal_event") is True,
        "atomic_failure_terminalization_contract_incomplete",
    )
    _require(
        state_machine.get("contract_ref")
        == S3_OWNER_GRADE_VERIFIER_STATE_MACHINE_REF
        and state_machine.get("provider_request_exposes_state_machine") is True
        and state_machine.get("local_validator_consumes_same_rules") is True
        and state_machine.get("normalization_or_silent_rewrite") is False
        and state_machine.get("local_validator_fail_closed") is True,
        "typed_verifier_state_machine_contract_incomplete",
    )
    _require(
        telemetry.get("failure_code")
        == "s3_bounded_verifier_state_machine_invalid"
        and telemetry.get("closed_subtype_count") == 7
        and telemetry.get(
            "raw_issue_codes_refs_repair_owner_or_output_persisted"
        )
        is False
        and telemetry.get("private_reasoning_persisted") is False,
        "typed_verifier_safe_telemetry_contract_incomplete",
    )
    _require(
        supervision.get("supervision_contract_ref")
        == SUPERVISION_CONTRACT_REF
        and supervision.get("direct_execute_cli_requires_supervision_receipt")
        is True
        and supervision.get("detached_process_has_no_parent_timeout") is True
        and supervision.get("monitor_is_read_only") is True
        and supervision.get("monitor_sends_signals") is False
        and supervision.get("automatic_retry_fallback_or_replay") is False,
        "supervised_exact_runner_contract_incomplete",
    )
    _require(
        len(deterministic.get("failure_injection") or {}) == 3
        and len(deterministic.get("verifier_positive_states") or []) == 3
        and len(deterministic.get("verifier_negative_subtypes") or []) == 7
        and deterministic.get(
            "fake_provider_derives_output_from_request_state_machine"
        )
        is True,
        "deterministic_repair_matrix_incomplete",
    )

    closeout = json.loads(
        OUTPUT_V4_ORPHAN_CLOSEOUT_RESULT.read_text(encoding="utf-8")
    )
    _require(
        closeout.get("status") == "typed_orphan_closeout_succeeded_zero_call"
        and closeout.get("canonical_terminal_truth", {}).get(
            "research_run_state"
        )
        == "failed"
        and closeout.get("canonical_terminal_truth", {}).get("artifact_count")
        == 0,
        "source_orphan_closeout_truth_mismatch",
    )

    result = prepare_claim_fact_proof(
        runtime_root=runtime_root,
        implementation_result_path=CLAIM_FACT_IMPLEMENTATION_RESULT,
        final_failure_result_path=PROFILE_V3_FINAL_FAILURE_RESULT,
        execution_identity=EXECUTION_IDENTITY,
        prospective_admission_id=PROSPECTIVE_ADMISSION_ID,
        prospective_admission_file=PROSPECTIVE_ADMISSION_FILE,
        execution_mode=(
            "exact_live_three_cell_deepseek_atomic_terminalization_"
            "typed_verifier_state_machine_supervised_r1"
        ),
        decision_status=DECISION_STATUS,
        decision_contract_ref=DECISION_CONTRACT_REF,
        additional_source_failed_result_paths=(
            CLAIM_FACT_LIVE_FAILURE_RESULT,
            OUTPUT_V4_ORPHAN_CLOSEOUT_RESULT,
        ),
    )
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(
        result["prospective_admission"]["payload"]
    )
    _require(
        admission.timeout_seconds * admission.max_provider_calls
        + max(120, admission.timeout_seconds)
        == MINIMUM_LIFECYCLE_BUDGET_SECONDS,
        "supervised_lifecycle_budget_mismatch",
    )

    result["source_refs"][
        "atomic_terminalization_and_typed_verifier_state_machine_implementation"
    ] = _relative(implementation_result_path)
    result["source_refs"]["output_v4_orphan_closeout"] = _relative(
        OUTPUT_V4_ORPHAN_CLOSEOUT_RESULT
    )
    result["exact_code_bindings"] = {
        path.as_posix(): _sha256(ROOT / path) for path in CODE_BINDING_PATHS
    }
    result["atomic_failure_terminalization_acceptance_contract"] = {
        "runtime_exception_path_command_count": 1,
        "failure_command": "FAIL_RESEARCH_RUN",
        "failure_command_carries_restricted_capture_refs": True,
        "single_transaction_requires": [
            "restricted_capture_refs",
            "failed_research_run",
            "failed_attempt",
            "failed_work_unit",
            "RESEARCH_RUN_FAILED",
            "ATTEMPT_FAILED",
            "WORK_UNIT_FAILED",
            "idempotency_result",
        ],
        "separate_preterminal_capture_event_allowed": False,
        "before_transaction_rejection_requires_zero_partial_state": True,
        "inside_transaction_fault_requires_full_rollback": True,
        "after_transaction_failure_requires_failed_failed_failed": True,
        "capture_refs_must_bind_to_terminal_event": True,
        "restricted_capture_replay_or_business_artifact_promotion_allowed": False,
    }
    result["typed_verifier_state_machine_acceptance_contract"] = {
        "contract_ref": S3_OWNER_GRADE_VERIFIER_STATE_MACHINE_REF,
        "provider_request_and_local_validator_share_rules": True,
        "pass_requires_empty_issues_empty_refs_and_none_owner": True,
        "review_or_fail_requires_nonempty_typed_details_and_real_owner": True,
        "all_pass_maps_to_accept": True,
        "review_without_fail_maps_to_repair": True,
        "any_fail_maps_to_reject": True,
        "positive_state_fixture_count": 3,
        "closed_negative_subtype_count": 7,
        "failure_code": "s3_bounded_verifier_state_machine_invalid",
        "raw_issue_ref_owner_output_or_private_reasoning_persisted": False,
        "normalization_coercion_or_silent_rewrite_allowed": False,
    }
    result["supervision_acceptance_contract"] = {
        "contract_ref": SUPERVISION_CONTRACT_REF,
        "launch_path": "detached_supervisor_only",
        "direct_execute_cli_allowed": False,
        "fresh_supervision_root_required": True,
        "minimum_lifecycle_budget_seconds": (
            MINIMUM_LIFECYCLE_BUDGET_SECONDS
        ),
        "parent_enforced_timeout_seconds": None,
        "parent_may_terminate_child": False,
        "durable_launch_pid_stdout_stderr_and_exit_receipts_required": True,
        "monitoring_contract": "read_only_no_signal_no_retry",
        "child_exit_code_zero_required_for_success": True,
        "consistent_terminal_canonical_truth_required": True,
        "automatic_retry_fallback_replay_or_second_launch_allowed": False,
    }
    result["artifact_acceptance_contract"].update(
        {
            "atomic_terminalization_contract_must_pass": True,
            "typed_verifier_state_machine_contract_must_pass": True,
            "supervision_contract_must_pass": True,
            "supervisor_exit_code_required": 0,
            "success_requires_terminal_states": [
                "succeeded",
                "succeeded",
                "succeeded",
            ],
        }
    )
    result["issuance_preconditions"] = {
        "exact_code_bindings_must_match": True,
        "double_prepare_must_remain_equal": True,
        "fresh_identity_and_admission_file_must_remain_absent": True,
        "target_database_and_object_tree_digests_must_match": True,
        "atomic_before_inside_after_regressions_must_pass": True,
        "three_positive_and_seven_negative_verifier_regressions_must_pass": True,
        "detached_slow_child_and_direct_execute_guard_regressions_must_pass": True,
        "project_os_scoped_preflight_must_pass_without_override": True,
        "admission_payload_must_equal_frozen_payload": True,
    }
    result["experiment_governance"] = {
        "hypothesis": (
            "The atomic capture-bearing failure transaction, explicit typed "
            "Verifier state machine and detached supervised lifecycle remove "
            "the two known project-owned blockers while preserving the complete "
            "three-Cell product path."
        ),
        "decision_target": (
            "One separately issued and separately authorized exact proof must "
            "exit through the supervisor with code zero and canonical "
            "succeeded/succeeded/succeeded, six logical nodes, twelve calls, "
            "nine Artifact families, valid Claim-to-Fact lineage and a "
            "state-machine-valid four-layer Verifier."
        ),
        "ceiling": (
            "twelve semantic/provider/network calls, 16800 aggregate output "
            "tokens, USD 0.10, one transport attempt per call and a 1560-second "
            "minimum detached lifecycle budget"
        ),
        "baseline_and_leakage_guard": (
            "same exact business input head; baseline output body remains "
            "hidden; all historical Run identities and admissions are nonreusable"
        ),
        "stop_condition": (
            "The first credible parse, schema, semantic, authority, identity, "
            "state-machine, atomicity, supervision, budget, terminalization, "
            "capture or Artifact failure terminally stops without retry, "
            "fallback, patch, replay, relaunch or second run."
        ),
        "decision_label": "proceed_to_separate_exact_admission_issuance_gate",
        "admission_issuance_authorized": False,
        "admission_consumption_authorized": False,
        "live_execution_authorized": False,
        "automatic_retry_fallback_patch_replay_relaunch_or_rerun_authorized": (
            False
        ),
        "paired_comparison_or_owner_acceptance_authorized": False,
        "T10_S4_release_or_production_authorized": False,
    }
    result["observed_counts"].update(
        {
            "supervisor_launches": 0,
            "live_executions": 0,
            "new_business_artifacts": 0,
        }
    )
    result["next_action"] = NEXT_ACTION
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", type=Path, default=RUNTIME_ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = prepare(
        runtime_root=args.runtime_root,
        implementation_result_path=IMPLEMENTATION_RESULT,
    )
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output is None:
        print(rendered)
    else:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
