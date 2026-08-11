from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_contract_policies import (
    S3_CLAIM_FACT_LINK_POLICY_REF,
    S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V3_REF,
)
from apps.workbench.backend.application.bounded_agent_executor import (
    S3_OWNER_GRADE_MEMO_WRITER_TRANSPORT_V3_REF,
    S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V5_REF,
    S3_OWNER_GRADE_RESEARCH_LEAD_V2_AGGREGATE_OUTPUT_TOKEN_BUDGET,
    S3_OWNER_GRADE_RESEARCH_LEAD_V2_STAGE_OUTPUT_TOKEN_BUDGETS,
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF,
    S3_PROVIDER_OUTPUT_CAPTURE_POLICY_REF,
    S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF,
    S3ThreeCellBoundedAgentAdmission,
    build_s3_three_cell_bounded_agent_executor_for_admission,
)
from apps.workbench.backend.application.bounded_agent_identity_policies import (
    S3_CELL_SCOPED_RESEARCH_IDENTITY_CONTRACT_REF,
)
from scripts.releases.prepare_fin_ia_0_1_s3_t09_owner_grade_v3_segmented_exact_admission_decision import (
    prepare as _prepare,
)
from scripts.releases.prepare_fin_ia_0_1_s3_t09_research_lead_v5_fresh_exact_proof import (
    _prior_failed_results,
)
from sec_agent.canonical_runtime.models import canonical_digest


RELEASES = ROOT / "configs" / "releases"
IMPLEMENTATION_STATUS = (
    "pass_zero_call_shared_claim_fact_link_policy_closed_alias_local_"
    "expansion_fixture_proven"
)
FINAL_FAILURE_STATUS = (
    "terminal_failed_hard_specialist_claim_fact_identity_layer_violation_"
    "no_second_execution_authorized"
)
EXECUTION_IDENTITY = (
    "fin01-s3-t09-three-cell-deepseek-claim-fact-link-policy-"
    "live-validation-r1"
)
PROSPECTIVE_ADMISSION_ID = (
    "fin01-s3-t09-three-cell-deepseek-claim-fact-link-policy-"
    "exact-admission-r1"
)
PROSPECTIVE_ADMISSION_FILE = (
    "configs/releases/fin_ia_0_1_s3_t09_three_cell_deepseek_"
    "claim_fact_link_policy_exact_admission_r1.json"
)
DECISION_STATUS = (
    "pass_zero_call_claim_fact_link_policy_fresh_exact_proof_contract_"
    "frozen_admission_issuance_pending_separate_authority"
)
NEXT_ACTION = (
    "S3-T09-GENERALIZED-CLAIM-FACT-LINK-POLICY-"
    "FRESH-EXACT-ADMISSION-ISSUANCE"
)


class ClaimFactLinkFreshProofDecisionError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ClaimFactLinkFreshProofDecisionError(code)


def _additional_prior_failed_results() -> tuple[Path, ...]:
    return (
        *_prior_failed_results(RELEASES),
        RELEASES
        / "fin_ia_0_1_s3_t09_research_lead_v5_fresh_live_execution_"
        "result_v1_0.json",
        RELEASES
        / "fin_ia_0_1_s3_t09_research_lead_v5_profile_v3_final_"
        "exact_live_execution_result_v1_0.json",
    )


def _prepare_base(
    *,
    runtime_root: Path,
    implementation_result_path: Path,
    execution_identity: str = EXECUTION_IDENTITY,
    prospective_admission_id: str = PROSPECTIVE_ADMISSION_ID,
    prospective_admission_file: str = PROSPECTIVE_ADMISSION_FILE,
    execution_mode: str = (
        "exact_live_three_cell_deepseek_claim_fact_link_policy_r1"
    ),
    required_implementation_status: str = IMPLEMENTATION_STATUS,
    decision_status: str = DECISION_STATUS,
    decision_contract_ref: str = (
        "fin01.s3.claim_fact_link_policy_fresh_exact_proof_decision:v1"
    ),
    additional_source_failed_result_paths: tuple[Path, ...] = (),
    research_profile_ref: str = S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V3_REF,
) -> dict[str, Any]:
    return _prepare(
        runtime_root=runtime_root,
        baseline_result_path=RELEASES
        / "fin_ia_0_1_s3_t09_paired_deterministic_baseline_"
        "materialization_v1_0.json",
        paired_decision_path=RELEASES
        / "fin_ia_0_1_s3_t09_replacement_live_artifact_paired_"
        "baseline_decision_v1_0.json",
        monolithic_v3_result_path=RELEASES
        / "fin_ia_0_1_s3_t09_owner_grade_v3_fresh_live_execution_"
        "result_v1_0.json",
        transport_implementation_result_path=implementation_result_path,
        additional_prior_failed_result_paths=(
            *_additional_prior_failed_results(),
            *additional_source_failed_result_paths,
        ),
        execution_identity=execution_identity,
        prospective_admission_id=prospective_admission_id,
        prospective_admission_file=prospective_admission_file,
        execution_mode=execution_mode,
        transport_ref=S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF,
        required_transport_result_status=required_implementation_status,
        decision_status=decision_status,
        decision_contract_ref=decision_contract_ref,
        transport_result_binding_path=("selected_contract_ref",),
        required_transport_result_binding_value=(
            S3_CLAIM_FACT_LINK_POLICY_REF
        ),
        provider_output_capture_policy_ref=(
            S3_PROVIDER_OUTPUT_CAPTURE_POLICY_REF
        ),
        research_lead_transport_ref=(
            S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V5_REF
        ),
        memo_writer_transport_ref=(
            S3_OWNER_GRADE_MEMO_WRITER_TRANSPORT_V3_REF
        ),
        research_profile_ref=research_profile_ref,
        output_contract_ref=(
            S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF
        ),
        scoped_identity_contract_ref=(
            S3_CELL_SCOPED_RESEARCH_IDENTITY_CONTRACT_REF
        ),
        stage_output_token_budgets=(
            S3_OWNER_GRADE_RESEARCH_LEAD_V2_STAGE_OUTPUT_TOKEN_BUDGETS
        ),
        aggregate_output_token_budget=(
            S3_OWNER_GRADE_RESEARCH_LEAD_V2_AGGREGATE_OUTPUT_TOKEN_BUDGET
        ),
    )


def prepare(
    *,
    runtime_root: Path,
    implementation_result_path: Path,
    final_failure_result_path: Path,
    execution_identity: str = EXECUTION_IDENTITY,
    prospective_admission_id: str = PROSPECTIVE_ADMISSION_ID,
    prospective_admission_file: str = PROSPECTIVE_ADMISSION_FILE,
    execution_mode: str = (
        "exact_live_three_cell_deepseek_claim_fact_link_policy_r1"
    ),
    decision_status: str = DECISION_STATUS,
    decision_contract_ref: str = (
        "fin01.s3.claim_fact_link_policy_fresh_exact_proof_decision:v1"
    ),
    additional_source_failed_result_paths: tuple[Path, ...] = (),
    research_profile_ref: str = S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V3_REF,
) -> dict[str, Any]:
    implementation = json.loads(
        implementation_result_path.read_text(encoding="utf-8")
    )
    final_failure = json.loads(
        final_failure_result_path.read_text(encoding="utf-8")
    )
    _require(
        implementation.get("status") == IMPLEMENTATION_STATUS,
        "claim_fact_link_policy_implementation_not_fixture_proven",
    )
    _require(
        implementation.get("selected_contract_ref")
        == S3_CLAIM_FACT_LINK_POLICY_REF,
        "claim_fact_link_policy_implementation_binding_mismatch",
    )
    implemented = implementation.get("implementation")
    _require(
        isinstance(implemented, dict)
        and implemented.get("activation_binding")
        == "S3ThreeCellBoundedAgentAdmission.claim_fact_link_policy_ref"
        and implemented.get("activation_is_explicit") is True
        and implemented.get(
            "historical_admission_digest_field_absence_preserved"
        )
        is True,
        "claim_fact_link_policy_activation_contract_mismatch",
    )
    observed = implementation.get("observed_counts")
    _require(
        isinstance(observed, dict) and set(observed.values()) == {0},
        "claim_fact_link_policy_implementation_must_be_zero_call",
    )
    _require(
        final_failure.get("status") == FINAL_FAILURE_STATUS
        and final_failure.get("canonical_terminal_truth", {}).get(
            "research_run_state"
        )
        == "failed"
        and final_failure.get("canonical_terminal_truth", {}).get(
            "artifact_count"
        )
        == 0,
        "claim_fact_link_policy_source_failure_truth_mismatch",
    )

    result = _prepare_base(
        runtime_root=runtime_root,
        implementation_result_path=implementation_result_path,
        execution_identity=execution_identity,
        prospective_admission_id=prospective_admission_id,
        prospective_admission_file=prospective_admission_file,
        execution_mode=execution_mode,
        decision_status=decision_status,
        decision_contract_ref=decision_contract_ref,
        additional_source_failed_result_paths=(
            additional_source_failed_result_paths
        ),
        research_profile_ref=research_profile_ref,
    )
    payload = dict(result["prospective_admission"]["payload"])
    payload["claim_fact_link_policy_ref"] = S3_CLAIM_FACT_LINK_POLICY_REF
    admission = S3ThreeCellBoundedAgentAdmission(**payload)
    admission.assert_profile_admissible()
    provider_callback_calls = 0

    def _must_not_call_provider(**_: Any) -> dict[str, Any]:
        nonlocal provider_callback_calls
        provider_callback_calls += 1
        raise AssertionError("provider_callback_forbidden_in_proof_decision")

    build_s3_three_cell_bounded_agent_executor_for_admission(
        admission,
        chat_completion_fn=_must_not_call_provider,
    )
    _require(
        provider_callback_calls == 0,
        "provider_callback_called_during_claim_fact_link_proof_decision",
    )
    admission_payload = admission.digest_payload()
    result["prospective_admission"]["payload"] = admission_payload
    result["prospective_admission"]["digest"] = canonical_digest(
        admission_payload
    )
    result["source_refs"]["claim_fact_link_policy_implementation"] = (
        implementation_result_path.resolve().relative_to(ROOT).as_posix()
    )
    result["source_refs"]["final_claim_fact_identity_failure"] = (
        final_failure_result_path.resolve().relative_to(ROOT).as_posix()
    )
    result["architecture_contract"] = {
        "output_contract_ref": (
            S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF
        ),
        "specialist_transport_ref": (
            S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF
        ),
        "research_lead_transport_ref": (
            S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V5_REF
        ),
        "memo_writer_transport_ref": (
            S3_OWNER_GRADE_MEMO_WRITER_TRANSPORT_V3_REF
        ),
        "research_profile_ref": (
            research_profile_ref
        ),
        "scoped_identity_contract_ref": (
            S3_CELL_SCOPED_RESEARCH_IDENTITY_CONTRACT_REF
        ),
        "claim_fact_link_policy_ref": S3_CLAIM_FACT_LINK_POLICY_REF,
        "provider_output_capture_policy_ref": (
            S3_PROVIDER_OUTPUT_CAPTURE_POLICY_REF
        ),
        "claim_fact_link_policy_activation_is_explicit": True,
        "historical_transport_version_behavior_unchanged": True,
    }
    result["claim_fact_link_live_acceptance_contract"] = {
        "all_three_claim_segments_receive_policy_binding": True,
        "provider_response_support_field": "support_fact_aliases",
        "provider_support_fact_ids_when_policy_active_allowed": False,
        "provider_visible_raw_fact_source_object_or_routing_refs_allowed": False,
        "local_expansion_must_precede_scope_epistemic_and_canonical_validation": (
            True
        ),
        "fact_supported_or_bounded_inference_support_must_be_nonempty": True,
        "expanded_support_must_resolve_to_validated_same_Cell_Facts": True,
        "persisted_alias_residue_required": 0,
        "persisted_source_ref_as_claim_support_required": 0,
        "safe_failure_code": "s3_owner_grade_claim_fact_link_invalid",
        "failure_telemetry_content_free": True,
    }
    result["artifact_acceptance_contract"] = {
        "success_requires_terminal_state": "succeeded",
        "success_requires_logical_nodes": 6,
        "success_requires_provider_calls": 12,
        "success_requires_artifact_families": 9,
        "required_artifact_types": [
            "SpecialistAnalysis",
            "ResearchLeadSynthesis",
            "MemoDraft",
            "VerifierResult",
            "FactSet",
            "EvidenceSet",
            "NumericSet",
            "JudgmentSet",
            "Report",
        ],
        "claim_fact_link_live_acceptance_must_pass": True,
        "transport_or_specialist_only_green_is_success": False,
        "failure_requires_typed_terminal_closeout": True,
        "failure_preserves_completed_assistant_outputs_and_usage": True,
        "paired_comparison_requires_separate_read_only_authority": True,
        "owner_acceptance_requires_user_confirmation": True,
    }
    result["audit_contract"] = {
        "target_service_initialization_allowed": False,
        "target_SQLite_access": "direct_mode_ro_or_digest_only",
        "service_backed_preparation": "disposable_clone_only",
        "target_database_or_object_write_allowed": False,
        "credential_value_read_output_or_persisted": False,
        "historical_failed_provider_answer_read_or_rewritten": False,
    }
    result["experiment_governance"] = {
        "hypothesis": (
            "The explicit shared ClaimFactLinkPolicy prevents Provider selection "
            "of source-object identities and allows exact same-Cell Claim-to-Fact "
            "lineage through the complete six-node product path."
        ),
        "decision_target": (
            "One separately issued and separately authorized exact proof must "
            "reach terminal succeeded with six nodes, twelve calls, nine Artifact "
            "families, valid same-Cell Fact support, and zero alias/source-ref "
            "Claim-support residue."
        ),
        "stop_condition": (
            "The first credible parse, schema, ClaimFactLink, scope, epistemic, "
            "canonical, identity, length, budget, terminalization, or capture "
            "failure must terminally stop without retry, fallback, patch, or rerun."
        ),
        "decision_label": "proceed_to_separate_exact_admission_issuance_gate",
        "admission_issuance_authorized": False,
        "admission_consumption_authorized": False,
        "live_execution_authorized": False,
        "automatic_retry_fallback_patch_or_rerun_authorized": False,
        "paired_comparison_or_owner_acceptance_authorized": False,
        "T10_S4_release_or_production_authorized": False,
    }
    result["observed_counts"]["provider_calls"] = provider_callback_calls
    result["next_action"] = NEXT_ACTION
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--runtime-root",
        type=Path,
        default=ROOT
        / ".codex_runtime"
        / "fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
    )
    args = parser.parse_args()
    result = prepare(
        runtime_root=args.runtime_root,
        implementation_result_path=RELEASES
        / "fin_ia_0_1_s3_t09_claim_fact_link_policy_closed_alias_"
        "zero_call_implementation_v1_0.json",
        final_failure_result_path=RELEASES
        / "fin_ia_0_1_s3_t09_research_lead_v5_profile_v3_final_"
        "exact_live_execution_result_v1_0.json",
    )
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output is not None:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
