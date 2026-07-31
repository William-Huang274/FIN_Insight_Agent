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
    _validate_host_capability_receipt,
)


RELEASES = ROOT / "configs" / "releases"
RUNTIME_ROOT = (
    ROOT
    / ".codex_runtime"
    / "fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1"
)
IMPLEMENTATION_RESULT = RELEASES / (
    "fin_ia_0_1_s3_t09_nullable_repair_owner_and_windows_direct_runner_"
    "supervision_v2_zero_call_implementation_v1_0.json"
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
ATOMIC_LIVE_FAILURE_RESULT = RELEASES / (
    "fin_ia_0_1_s3_t09_atomic_terminalization_and_typed_verifier_"
    "state_machine_fresh_exact_live_execution_result_v1_0.json"
)
HOST_CAPABILITY_RECEIPT = (
    ROOT
    / ".codex_runtime"
    / "fin01-s3-t09-supervision-v2-final-host-capability-r1"
    / "host_capability_receipt.json"
)
EXECUTION_IDENTITY = (
    "fin01-s3-t09-three-cell-deepseek-nullable-owner-supervision-v2-"
    "final-live-validation-r1"
)
PROSPECTIVE_ADMISSION_ID = (
    "fin01-s3-t09-three-cell-deepseek-nullable-owner-supervision-v2-"
    "final-exact-admission-r1"
)
PROSPECTIVE_ADMISSION_FILE = (
    "configs/releases/fin_ia_0_1_s3_t09_three_cell_deepseek_"
    "nullable_owner_supervision_v2_final_exact_admission_r1.json"
)
DECISION_STATUS = (
    "pass_zero_call_nullable_owner_and_direct_runner_supervision_v2_"
    "final_fresh_proof_contract_frozen_admission_issuance_authorized"
)
DECISION_CONTRACT_REF = (
    "fin01.s3.nullable_owner_direct_runner_supervision_v2_"
    "final_fresh_proof_decision:v1"
)
NEXT_ACTION = (
    "S3-T09-NULLABLE-OWNER-AND-DIRECT-RUNNER-SUPERVISION-V2-"
    "FINAL-EXACT-ADMISSION-ISSUANCE"
)
IMPLEMENTATION_STATUS = (
    "pass_zero_call_nullable_repair_owner_and_windows_direct_runner_"
    "self_finalizing_supervision_v2_implemented_and_host_smoke_proven"
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


class NullableOwnerSupervisionV2FreshProofError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise NullableOwnerSupervisionV2FreshProofError(code)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def prepare(
    *,
    runtime_root: Path = RUNTIME_ROOT,
    implementation_result_path: Path = IMPLEMENTATION_RESULT,
    host_capability_receipt_path: Path = HOST_CAPABILITY_RECEIPT,
) -> dict[str, Any]:
    implementation = json.loads(
        implementation_result_path.read_text(encoding="utf-8")
    )
    _require(
        implementation.get("status") == IMPLEMENTATION_STATUS,
        "nullable_supervision_v2_implementation_status_invalid",
    )
    _require(
        set((implementation.get("observed_counts") or {}).values()) == {0},
        "nullable_supervision_v2_implementation_not_zero_call",
    )

    nullable = implementation.get(
        "nullable_repair_owner_state_machine_v2"
    ) or {}
    supervision = implementation.get(
        "windows_direct_runner_supervision_v2"
    ) or {}
    deterministic = implementation.get("deterministic_verification") or {}
    _require(
        nullable.get("contract_ref")
        == S3_OWNER_GRADE_VERIFIER_STATE_MACHINE_REF
        and nullable.get("pass_repair_owner") is None
        and nullable.get("literal_JSON_examples_present") is True
        and nullable.get("literal_string_none_allowed") is False
        and nullable.get("normalization_or_silent_rewrite_allowed") is False
        and nullable.get("captured_answer_rewrite_performed") is False,
        "nullable_owner_state_machine_v2_contract_incomplete",
    )
    _require(
        supervision.get("contract_ref") == SUPERVISION_CONTRACT_REF
        and supervision.get("launch_receipt_binds_actual_runner_pid") is True
        and supervision.get("launch_and_exit_bind_creation_identity") is True
        and supervision.get(
            "actual_runner_top_level_finally_writes_atomic_exit_receipt"
        )
        is True
        and supervision.get("windows_os_kill_pid_zero_used") is False
        and supervision.get("pid_reuse_guard") is True
        and supervision.get(
            "exact_launch_requires_valid_host_capability_receipt_before_issuance_or_admission_read"
        )
        is True
        and supervision.get("automatic_retry_fallback_replay_relaunch")
        == [0, 0, 0, 0],
        "direct_runner_supervision_v2_contract_incomplete",
    )
    _require(
        deterministic.get("success_self_finalization") is True
        and deterministic.get("typed_nonzero_self_finalization") is True
        and deterministic.get("running_exited_and_pid_reuse_status_covered")
        is True
        and deterministic.get(
            "missing_host_capability_fails_before_issuance_read"
        )
        is True
        and deterministic.get("request_derived_fake_provider_nullable_output")
        is True,
        "nullable_supervision_v2_deterministic_matrix_incomplete",
    )

    digest_bindings = implementation.get("source_digests") or {}
    expected_current_digests = {
        "verifier_request_and_validator_sha256": _sha256(
            ROOT / "apps/workbench/backend/application/bounded_agent_executor.py"
        ),
        "direct_runner_supervisor_sha256": _sha256(
            ROOT
            / "scripts/releases/"
            "supervise_fin_ia_0_1_s3_t09_exact_live_execution.py"
        ),
        "exact_runner_self_finalizer_sha256": _sha256(
            ROOT
            / "scripts/releases/"
            "run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution.py"
        ),
    }
    _require(
        all(
            digest_bindings.get(key) == value
            for key, value in expected_current_digests.items()
        ),
        "nullable_supervision_v2_source_digest_drift",
    )

    capability, capability_digest = _validate_host_capability_receipt(
        host_capability_receipt_path
    )
    _require(
        capability.get("durable_process_strategy")
        == "windows_CREATE_BREAKAWAY_FROM_JOB_direct_runner"
        and capability.get(
            "separate_launcher_and_status_command_invocations"
        )
        is True
        and capability.get("self_finalized_exit_receipt") is True,
        "final_windows_host_capability_not_proven",
    )

    result = prepare_claim_fact_proof(
        runtime_root=runtime_root,
        implementation_result_path=CLAIM_FACT_IMPLEMENTATION_RESULT,
        final_failure_result_path=PROFILE_V3_FINAL_FAILURE_RESULT,
        execution_identity=EXECUTION_IDENTITY,
        prospective_admission_id=PROSPECTIVE_ADMISSION_ID,
        prospective_admission_file=PROSPECTIVE_ADMISSION_FILE,
        execution_mode=(
            "exact_live_three_cell_deepseek_nullable_owner_"
            "direct_runner_supervision_v2_final_r1"
        ),
        decision_status=DECISION_STATUS,
        decision_contract_ref=DECISION_CONTRACT_REF,
        additional_source_failed_result_paths=(
            CLAIM_FACT_LIVE_FAILURE_RESULT,
            OUTPUT_V4_ORPHAN_CLOSEOUT_RESULT,
            ATOMIC_LIVE_FAILURE_RESULT,
        ),
    )
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(
        result["prospective_admission"]["payload"]
    )
    _require(
        admission.timeout_seconds * admission.max_provider_calls
        + max(120, admission.timeout_seconds)
        == MINIMUM_LIFECYCLE_BUDGET_SECONDS,
        "final_supervised_lifecycle_budget_mismatch",
    )

    result["source_refs"]["nullable_owner_and_supervision_v2_implementation"] = (
        _relative(implementation_result_path)
    )
    result["source_refs"]["atomic_terminalization_fresh_live_failure"] = (
        _relative(ATOMIC_LIVE_FAILURE_RESULT)
    )
    result["exact_code_bindings"] = {
        path.as_posix(): _sha256(ROOT / path) for path in CODE_BINDING_PATHS
    }
    result["nullable_owner_state_machine_v2_acceptance_contract"] = {
        "contract_ref": S3_OWNER_GRADE_VERIFIER_STATE_MACHINE_REF,
        "pass_repair_owner": "JSON_null",
        "review_or_fail_repair_owner": (
            "nonblank_real_owner_string_not_literal_none"
        ),
        "structural_gate_domain": "JSON_null_or_nonblank_string",
        "semantic_gate_owns_status_relation": True,
        "literal_string_none_allowed": False,
        "normalization_or_captured_answer_rewrite_allowed": False,
        "positive_state_fixture_count": 3,
        "closed_negative_fixture_count_at_least": 10,
        "request_derived_fake_provider_required": True,
    }
    result["supervision_v2_acceptance_contract"] = {
        "contract_ref": SUPERVISION_CONTRACT_REF,
        "launch_path": "direct_actual_runner_no_intermediate_wrapper",
        "fresh_supervision_root_required": True,
        "minimum_lifecycle_budget_seconds": (
            MINIMUM_LIFECYCLE_BUDGET_SECONDS
        ),
        "actual_runner_pid_and_creation_identity_required": True,
        "actual_runner_self_finalized_atomic_exit_receipt_required": True,
        "windows_native_status_and_pid_reuse_guard_required": True,
        "parent_enforced_timeout_seconds": None,
        "parent_may_terminate_child": False,
        "monitoring_contract": "read_only_no_signal_no_retry_no_relaunch",
        "host_capability_receipt_ref": _relative(
            host_capability_receipt_path
        ),
        "host_capability_receipt_sha256": capability_digest,
        "host_durable_process_strategy": capability[
            "durable_process_strategy"
        ],
        "child_exit_code_zero_required_for_success": True,
        "consistent_terminal_canonical_truth_required": True,
        "automatic_retry_fallback_replay_or_second_launch_allowed": False,
    }
    result["artifact_acceptance_contract"].update(
        {
            "nullable_owner_state_machine_v2_must_pass": True,
            "supervision_v2_contract_must_pass": True,
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
        "nullable_owner_positive_and_negative_regressions_must_pass": True,
        "direct_runner_success_failure_pid_reuse_regressions_must_pass": True,
        "host_capability_receipt_digest_must_match": True,
        "project_os_scoped_preflight_must_pass_without_override": True,
        "admission_payload_must_equal_frozen_payload": True,
    }
    result["experiment_governance"] = {
        "hypothesis": (
            "The nullable-owner Verifier state machine and direct actual-runner "
            "self-finalizing Windows supervision remove the final known "
            "project-owned exact-live blockers without weakening product quality."
        ),
        "decision_target": (
            "One fresh exact run must exit through supervision-v2 with code zero, "
            "canonical succeeded/succeeded/succeeded, twelve successful calls, "
            "nine reconstructable Artifact families, valid Claim-to-Fact lineage "
            "and an all-pass four-layer Verifier."
        ),
        "ceiling": (
            "twelve semantic/provider/network calls, 16800 aggregate output "
            "tokens, USD 0.10, one transport attempt per call and a 1560-second "
            "minimum direct-runner lifecycle budget"
        ),
        "stop_condition": (
            "The first credible parse, schema, semantic, authority, identity, "
            "state-machine, supervision, budget, terminalization, capture or "
            "Artifact failure terminally stops without retry, fallback, patch, "
            "replay, relaunch or second run."
        ),
        "decision_label": "proceed_to_final_exact_admission_issuance",
        "current_user_authorizes_ordered_issuance_execution_and_acceptance": True,
        "automatic_retry_fallback_patch_replay_relaunch_or_rerun_authorized": (
            False
        ),
        "paired_comparison_requires_successful_nine_artifact_run": True,
        "T10_S4_release_or_production_authorized": False,
    }
    result["observed_counts"].update(
        {
            "host_capability_smoke_model_calls": 0,
            "supervisor_launches_for_exact_run": 0,
            "live_executions": 0,
            "new_business_artifacts": 0,
        }
    )
    result["next_action"] = NEXT_ACTION
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", type=Path, default=RUNTIME_ROOT)
    parser.add_argument(
        "--host-capability-receipt",
        type=Path,
        default=HOST_CAPABILITY_RECEIPT,
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = prepare(
        runtime_root=args.runtime_root,
        implementation_result_path=IMPLEMENTATION_RESULT,
        host_capability_receipt_path=args.host_capability_receipt,
    )
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output is None:
        print(rendered)
    else:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
