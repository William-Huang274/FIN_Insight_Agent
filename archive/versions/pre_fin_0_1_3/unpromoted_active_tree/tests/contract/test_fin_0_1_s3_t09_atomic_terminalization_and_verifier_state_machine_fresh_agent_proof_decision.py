from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_executor import (
    S3_OWNER_GRADE_VERIFIER_STATE_MACHINE_REF,
    S3ThreeCellBoundedAgentAdmission,
)
from scripts.releases.prepare_fin_ia_0_1_s3_t09_atomic_terminalization_and_verifier_state_machine_fresh_exact_proof import (
    DECISION_STATUS,
    MINIMUM_LIFECYCLE_BUDGET_SECONDS,
    NEXT_ACTION,
)
from scripts.releases.supervise_fin_ia_0_1_s3_t09_exact_live_execution import (
    SUPERVISION_CONTRACT_REF,
)
from sec_agent.canonical_runtime.models import canonical_digest


PROOF = ROOT / (
    "configs/releases/fin_ia_0_1_s3_t09_atomic_terminalization_and_"
    "typed_verifier_state_machine_fresh_agent_proof_decision_v1_0.json"
)
PROSPECTIVE_ADMISSION = ROOT / (
    "configs/releases/fin_ia_0_1_s3_t09_three_cell_deepseek_"
    "atomic_terminalization_verifier_state_machine_supervised_"
    "exact_admission_r1.json"
)


def _load() -> dict:
    return json.loads(PROOF.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_fresh_proof_freezes_new_identity_and_zero_call_boundary() -> None:
    proof = _load()
    identity = proof["identity"]

    assert proof["status"] == DECISION_STATUS
    assert proof["double_prepare"]["equal"] is True
    assert proof["target_read_only_audit"][
        "expected_prior_research_run_count"
    ] == 20
    assert proof["freshness_and_nonreuse"]["work_unit_absent"] is True
    assert proof["freshness_and_nonreuse"]["attempt_absent"] is True
    assert proof["freshness_and_nonreuse"]["research_run_absent"] is True
    assert identity["research_run_id"] not in proof["freshness_and_nonreuse"][
        "prior_research_run_ids"
    ]
    assert set(proof["observed_counts"].values()) == {0}


def test_prospective_admission_was_valid_frozen_and_unconsumed_at_decision() -> None:
    proof = _load()
    prospective = proof["prospective_admission"]
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(
        prospective["payload"]
    )

    admission.assert_profile_admissible()
    assert canonical_digest(admission.digest_payload()) == prospective["digest"]
    assert prospective["admission_issued"] is False
    assert prospective["admission_consumed"] is False
    assert prospective["execution_started"] is False
    assert prospective["prospective_admission_file_absent"] is True
    assert PROSPECTIVE_ADMISSION.exists()
    assert admission.timeout_seconds * admission.max_provider_calls + max(
        120, admission.timeout_seconds
    ) == MINIMUM_LIFECYCLE_BUDGET_SECONDS


def test_exact_code_bindings_preserve_the_historical_v1_proof_surface() -> None:
    proof = _load()
    bindings = proof["exact_code_bindings"]

    assert set(bindings) == {
        "apps/workbench/backend/application/research_runtime.py",
        "apps/workbench/backend/application/bounded_agent_executor.py",
        "src/sec_agent/canonical_runtime/facade.py",
        "scripts/releases/supervise_fin_ia_0_1_s3_t09_exact_live_execution.py",
        "scripts/releases/run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution.py",
    }
    superseded = {
        "apps/workbench/backend/application/bounded_agent_executor.py",
        "scripts/releases/supervise_fin_ia_0_1_s3_t09_exact_live_execution.py",
        "scripts/releases/run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution.py",
    }
    for relative, digest in bindings.items():
        if relative in superseded:
            assert _sha256(ROOT / relative) != digest
        else:
            assert _sha256(ROOT / relative) == digest


def test_atomic_failure_contract_forbids_split_capture_terminalization() -> None:
    contract = _load()["atomic_failure_terminalization_acceptance_contract"]

    assert contract["runtime_exception_path_command_count"] == 1
    assert contract["failure_command"] == "FAIL_RESEARCH_RUN"
    assert contract["failure_command_carries_restricted_capture_refs"] is True
    assert contract["separate_preterminal_capture_event_allowed"] is False
    assert contract["inside_transaction_fault_requires_full_rollback"] is True
    assert contract["after_transaction_failure_requires_failed_failed_failed"] is True
    assert contract[
        "restricted_capture_replay_or_business_artifact_promotion_allowed"
    ] is False


def test_typed_verifier_state_machine_is_explicit_and_fail_closed() -> None:
    contract = _load()["typed_verifier_state_machine_acceptance_contract"]

    assert contract["contract_ref"] == (
        "fin01.s3.owner_grade_verifier_output_state_machine:v1"
    )
    assert contract["provider_request_and_local_validator_share_rules"] is True
    assert contract["positive_state_fixture_count"] == 3
    assert contract["closed_negative_subtype_count"] == 7
    assert contract["all_pass_maps_to_accept"] is True
    assert contract["review_without_fail_maps_to_repair"] is True
    assert contract["any_fail_maps_to_reject"] is True
    assert contract[
        "raw_issue_ref_owner_output_or_private_reasoning_persisted"
    ] is False
    assert contract["normalization_coercion_or_silent_rewrite_allowed"] is False


def test_supervision_and_next_authority_are_frozen_without_launch() -> None:
    proof = _load()
    supervision = proof["supervision_acceptance_contract"]
    governance = proof["experiment_governance"]

    assert supervision["contract_ref"] == "fin01.s3.exact_run_supervision:v1"
    assert supervision["launch_path"] == "detached_supervisor_only"
    assert supervision["direct_execute_cli_allowed"] is False
    assert supervision["minimum_lifecycle_budget_seconds"] == 1_560
    assert supervision["parent_enforced_timeout_seconds"] is None
    assert supervision["parent_may_terminate_child"] is False
    assert supervision["monitoring_contract"] == "read_only_no_signal_no_retry"
    assert governance["admission_issuance_authorized"] is False
    assert governance["admission_consumption_authorized"] is False
    assert governance["live_execution_authorized"] is False
    assert governance["paired_comparison_or_owner_acceptance_authorized"] is False
    assert proof["next_action"] == NEXT_ACTION


def test_issuance_records_generator_reproduction_before_materialization() -> None:
    frozen = _load()
    issuance = json.loads(
        (
            ROOT
            / "configs/releases/fin_ia_0_1_s3_t09_atomic_terminalization_and_"
            "typed_verifier_state_machine_fresh_exact_admission_issuance_v1_0.json"
        ).read_text(encoding="utf-8")
    )
    reverification = issuance["proof_reverification"]

    assert reverification["generator_rerun_before_materialization"] is True
    assert reverification[
        "frozen_and_regenerated_critical_sections_equal"
    ] is True
    assert reverification["prepared_payload_digest"] == frozen[
        "double_prepare"
    ]["prepared_payload_digest"]
    assert reverification["exact_code_bindings"] == frozen[
        "exact_code_bindings"
    ]


def test_program_backlog_preserves_proof_after_live_failure_gate() -> None:
    backlog = json.loads(
        (
            ROOT
            / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
        ).read_text(encoding="utf-8")
    )
    next_action = backlog["next_action"]

    assert next_action[
        "S3_T09_atomic_terminalization_and_typed_verifier_state_machine_"
        "fresh_agent_proof_decision_ref"
    ] == (
        "configs/releases/fin_ia_0_1_s3_t09_atomic_terminalization_and_"
        "typed_verifier_state_machine_fresh_agent_proof_decision_v1_0.json"
    )
    assert next_action["fresh_exact_live_execution_result_ref"] == (
        "configs/releases/fin_ia_0_1_s3_t09_atomic_terminalization_and_"
        "typed_verifier_state_machine_fresh_exact_live_execution_result_v1_0.json"
    )
    assert next_action["atomic_terminalization_fresh_exact_admission_consumed"] is True
    assert next_action["atomic_terminalization_fresh_exact_live_artifact_count"] == 0
    assert next_action["repair_implementation_complete"] is True
    assert next_action["second_live_execution_authorized"] is False
    assert next_action["agent_execution_authorized"] is False
