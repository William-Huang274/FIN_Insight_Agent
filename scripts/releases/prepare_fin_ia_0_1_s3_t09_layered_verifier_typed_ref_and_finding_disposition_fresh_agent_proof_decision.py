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

from apps.workbench.backend.application.bounded_agent_contract_policies import (
    S3_CLAIM_FACT_LINK_POLICY_REF,
    S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V4_REF,
)
from apps.workbench.backend.application.bounded_agent_executor import (
    S3_OWNER_GRADE_MEMO_WRITER_TRANSPORT_V3_REF,
    S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V5_REF,
    S3_OWNER_GRADE_RESEARCH_LEAD_V2_AGGREGATE_OUTPUT_TOKEN_BUDGET,
    S3_OWNER_GRADE_RESEARCH_LEAD_V2_STAGE_OUTPUT_TOKEN_BUDGETS,
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF,
    S3_OWNER_GRADE_VERIFIER_STATE_MACHINE_REF,
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
from scripts.releases.supervise_fin_ia_0_1_s3_t09_exact_live_execution import (
    SUPERVISION_CONTRACT_REF,
)
from sec_agent.canonical_runtime.models import canonical_digest


RELEASES = ROOT / "configs" / "releases"
RUNTIME_ROOT = (
    ROOT
    / ".codex_runtime"
    / "fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1"
)
DISPOSITION = RELEASES / (
    "fin_ia_0_1_s3_t09_verifier_typed_scoped_ref_l2_recovery_and_"
    "l1_semantic_findings_disposition_v1_0.json"
)
LATEST_FAILED_LIVE = RELEASES / (
    "fin_ia_0_1_s3_t09_layered_acceptance_final_exact_live_"
    "execution_result_v1_0.json"
)
PREVIOUS_LAYERED_PROOF = RELEASES / (
    "fin_ia_0_1_s3_t09_layered_acceptance_final_fresh_agent_"
    "proof_decision_v1_0.json"
)
LAYERED_STANDARD = RELEASES / (
    "fin_ia_0_1_layered_agent_acceptance_standard_v1_0.json"
)
EXECUTION_IDENTITY = (
    "fin01-s3-t09-three-cell-deepseek-layered-verifier-typed-ref-"
    "finding-disposition-live-validation-r1"
)
PROSPECTIVE_ADMISSION_ID = (
    "fin01-s3-t09-three-cell-deepseek-layered-verifier-typed-ref-"
    "finding-disposition-exact-admission-r1"
)
PROSPECTIVE_ADMISSION_FILE = (
    "configs/releases/fin_ia_0_1_s3_t09_three_cell_deepseek_"
    "layered_verifier_typed_ref_finding_disposition_exact_admission_r1.json"
)
DECISION_STATUS = (
    "pass_zero_call_layered_verifier_typed_ref_and_finding_disposition_"
    "fresh_exact_proof_contract_frozen_admission_issuance_pending_"
    "separate_authority"
)
DECISION_CONTRACT_REF = (
    "fin01.s3.layered_verifier_typed_ref_and_finding_disposition_"
    "fresh_agent_proof_decision:v1"
)
NEXT_ACTION = (
    "S3-T09-LAYERED-VERIFIER-TYPED-REF-AND-FINDING-DISPOSITION-"
    "FRESH-EXACT-ADMISSION-ISSUANCE"
)
DISPOSITION_STATUS = (
    "pass_zero_call_typed_ref_contract_converged_L1_hard_integrity_not_"
    "confirmed_quality_findings_carried_forward_fresh_proof_decision_pending"
)
LATEST_FAILED_LIVE_STATUS = (
    "terminal_failed_verifier_typed_ref_representation_drift_and_"
    "semantic_repair_findings_zero_artifacts_no_rerun"
)
PREVIOUS_LAYERED_PROOF_STATUS = (
    "pass_zero_call_layered_acceptance_final_fresh_exact_proof_contract_"
    "frozen_admission_issuance_and_one_live_execution_authorized"
)
LAYERED_ACCEPTANCE_CONTRACT_REF = (
    "fin01.agent_acceptance.layered_hard_integrity_and_quality:v1"
)

CODE_BINDING_PATHS = (
    Path(
        "apps/workbench/backend/application/"
        "bounded_agent_contract_policies.py"
    ),
    Path(
        "apps/workbench/backend/application/"
        "bounded_agent_identity_policies.py"
    ),
    Path("apps/workbench/backend/application/bounded_agent_executor.py"),
    Path("apps/workbench/backend/application/research_runtime.py"),
    Path("src/sec_agent/canonical_runtime/facade.py"),
    Path(
        "scripts/releases/"
        "run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution.py"
    ),
    Path(
        "scripts/releases/"
        "supervise_fin_ia_0_1_s3_t09_exact_live_execution.py"
    ),
)


class LayeredVerifierFreshProofDecisionError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise LayeredVerifierFreshProofDecisionError(code)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(
    *,
    runtime_root: Path = RUNTIME_ROOT,
    disposition_path: Path = DISPOSITION,
    latest_failed_live_path: Path = LATEST_FAILED_LIVE,
    previous_layered_proof_path: Path = PREVIOUS_LAYERED_PROOF,
    layered_standard_path: Path = LAYERED_STANDARD,
) -> dict[str, Any]:
    disposition = _load(disposition_path)
    latest_failed_live = _load(latest_failed_live_path)
    previous_layered_proof = _load(previous_layered_proof_path)
    layered_standard = _load(layered_standard_path)

    _require(
        disposition.get("status") == DISPOSITION_STATUS,
        "typed_ref_and_finding_disposition_not_ready",
    )
    _require(
        set((disposition.get("observed_counts") or {}).values()) == {0},
        "typed_ref_and_finding_disposition_not_zero_call",
    )
    l2_recovery = disposition.get("L2_recovery") or {}
    l1_review = disposition.get("L1_review") or {}
    _require(
        l2_recovery.get("typed_ref_contract_converged") is True
        and l2_recovery.get("captured_refs_all_known") is True
        and l2_recovery.get(
            "identity_guessing_normalization_fuzzy_match_or_silent_rewrite"
        )
        is False,
        "typed_scoped_ref_recovery_contract_incomplete",
    )
    _require(
        l1_review.get("hard_integrity_violation_confirmed") is False
        and l1_review.get("scope_digest_mismatch", {}).get("disposition")
        == "not_substantiated_model_finding"
        and l1_review.get("unresolved_cross_cell_conflict", {}).get(
            "acceptance_layer"
        )
        == "L3_analytical_quality"
        and l1_review.get("unattributed_company_total_margins", {}).get(
            "acceptance_layer"
        )
        == "L3_analytical_quality",
        "layered_finding_disposition_incomplete",
    )
    _require(
        latest_failed_live.get("status") == LATEST_FAILED_LIVE_STATUS
        and latest_failed_live.get("canonical_terminal_truth", {}).get(
            "research_run_state"
        )
        == "failed"
        and latest_failed_live.get("canonical_terminal_truth", {}).get(
            "artifact_count"
        )
        == 0,
        "latest_failed_live_truth_mismatch",
    )
    _require(
        previous_layered_proof.get("status")
        == PREVIOUS_LAYERED_PROOF_STATUS,
        "previous_layered_proof_status_mismatch",
    )
    _require(
        previous_layered_proof.get(
            "claim_fact_link_live_acceptance_contract"
        )
        is not None,
        "previous_claim_fact_link_acceptance_contract_missing",
    )
    _require(
        layered_standard.get("contract_ref")
        == LAYERED_ACCEPTANCE_CONTRACT_REF,
        "layered_acceptance_standard_ref_mismatch",
    )

    prior_failed_refs = tuple(
        previous_layered_proof.get("source_refs", {}).get(
            "additional_prior_failed_results"
        )
        or ()
    )
    _require(
        len(prior_failed_refs) == 18,
        "previous_layered_failed_result_set_incomplete",
    )
    additional_prior_failed_paths = (
        *(ROOT / ref for ref in prior_failed_refs),
        latest_failed_live_path,
    )

    result = _prepare(
        runtime_root=runtime_root,
        baseline_result_path=ROOT
        / previous_layered_proof["source_refs"]["baseline_result"],
        paired_decision_path=ROOT
        / previous_layered_proof["source_refs"]["paired_decision"],
        monolithic_v3_result_path=ROOT
        / previous_layered_proof["source_refs"]["monolithic_v3_result"],
        transport_implementation_result_path=disposition_path,
        additional_prior_failed_result_paths=additional_prior_failed_paths,
        execution_identity=EXECUTION_IDENTITY,
        prospective_admission_id=PROSPECTIVE_ADMISSION_ID,
        prospective_admission_file=PROSPECTIVE_ADMISSION_FILE,
        execution_mode=(
            "exact_live_three_cell_deepseek_layered_verifier_typed_ref_"
            "finding_disposition_r1"
        ),
        transport_ref=S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF,
        required_transport_result_status=DISPOSITION_STATUS,
        decision_status=DECISION_STATUS,
        decision_contract_ref=DECISION_CONTRACT_REF,
        transport_result_binding_path=(
            "source_evidence",
            "scoped_identity_contract_ref",
        ),
        required_transport_result_binding_value=(
            S3_CELL_SCOPED_RESEARCH_IDENTITY_CONTRACT_REF
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
        research_profile_ref=S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V4_REF,
        output_contract_ref=S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF,
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

    payload = dict(result["prospective_admission"]["payload"])
    payload["claim_fact_link_policy_ref"] = S3_CLAIM_FACT_LINK_POLICY_REF
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(payload)
    admission.assert_profile_admissible()
    provider_callback_calls = 0

    def _must_not_call_provider(**_: Any) -> dict[str, Any]:
        nonlocal provider_callback_calls
        provider_callback_calls += 1
        raise AssertionError("provider_callback_forbidden_in_fresh_proof")

    build_s3_three_cell_bounded_agent_executor_for_admission(
        admission,
        chat_completion_fn=_must_not_call_provider,
    )
    _require(
        provider_callback_calls == 0,
        "provider_callback_called_during_fresh_proof",
    )
    admission_payload = admission.digest_payload()
    result["prospective_admission"]["payload"] = admission_payload
    result["prospective_admission"]["digest"] = canonical_digest(
        admission_payload
    )

    result["source_refs"].update(
        {
            "typed_ref_and_finding_disposition": _relative(
                disposition_path
            ),
            "latest_failed_layered_live": _relative(
                latest_failed_live_path
            ),
            "previous_layered_proof": _relative(
                previous_layered_proof_path
            ),
            "layered_acceptance_standard": _relative(
                layered_standard_path
            ),
        }
    )
    result["architecture_contract"] = {
        "layered_acceptance_contract_ref": (
            LAYERED_ACCEPTANCE_CONTRACT_REF
        ),
        "output_contract_ref": S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF,
        "specialist_transport_ref": (
            S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF
        ),
        "research_lead_transport_ref": (
            S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V5_REF
        ),
        "memo_writer_transport_ref": (
            S3_OWNER_GRADE_MEMO_WRITER_TRANSPORT_V3_REF
        ),
        "verifier_state_machine_ref": (
            S3_OWNER_GRADE_VERIFIER_STATE_MACHINE_REF
        ),
        "research_profile_ref": S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V4_REF,
        "scoped_identity_contract_ref": (
            S3_CELL_SCOPED_RESEARCH_IDENTITY_CONTRACT_REF
        ),
        "claim_fact_link_policy_ref": S3_CLAIM_FACT_LINK_POLICY_REF,
        "provider_output_capture_policy_ref": (
            S3_PROVIDER_OUTPUT_CAPTURE_POLICY_REF
        ),
    }
    result["exact_code_bindings"] = {
        path.as_posix(): _sha256(ROOT / path) for path in CODE_BINDING_PATHS
    }
    result["verifier_typed_scoped_ref_acceptance_contract"] = {
        "provider_request_representation": (
            "CellScopedResearchIdentityPolicy.wire_schema(claim)"
        ),
        "local_validator_uses_same_scoped_identity_surface": True,
        "current_supported_ref_kind": "Claim",
        "exact_membership_required": True,
        "raw_unknown_wrong_kind_wrong_cell_or_duplicate_ref": (
            "typed_fail_closed"
        ),
        "identity_guessing_normalization_or_silent_rewrite_allowed": False,
        "failure_code": "s3_bounded_verifier_finding_schema_invalid",
    }
    result["finding_disposition_acceptance_contract"] = {
        "deterministic_owned_checks": [
            "lead_and_writer_digest_binding",
            "claim_scope_digest_derivation",
            "typed_scoped_reference_membership",
        ],
        "scope_digest_mismatch_without_local_contradiction_is_L1": False,
        "disclosed_unresolved_conflict_is_L1": False,
        "explicit_company_total_metric_without_segment_attribution_is_L1": False,
        "hard_integrity_requires_canonical_evidence": True,
        "L3_findings_must_be_persisted": [
            "unresolved_cross_cell_conflict",
            "unattributed_company_total_margins",
        ],
        "quality_findings_may_coexist_with_success_after_L1_pass": True,
    }
    result["layered_runtime_acceptance_contract"] = {
        "L1_truth_provenance_numeric_scope_identity_permission_and_lineage": (
            "hard"
        ),
        "L2_recoverable_protocol_output_must_be_retained_when_safe": True,
        "L3_and_L4_findings_do_not_erase_valid_output": True,
        "ordinary_character_thresholds_are_quality_findings": True,
        "wire_alias_local_expanded_storage_and_security_capacity_remain_hard": (
            True
        ),
        "historical_terminal_truth_rewrite_allowed": False,
        "captured_output_promotion_or_synthesis_allowed": False,
    }
    result["claim_fact_link_live_acceptance_contract"] = (
        previous_layered_proof[
            "claim_fact_link_live_acceptance_contract"
        ]
    )
    result["artifact_acceptance_contract"] = {
        "success_requires_terminal_state": "succeeded",
        "success_requires_terminal_states": [
            "succeeded",
            "succeeded",
            "succeeded",
        ],
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
        "same_coherent_run_required": True,
        "L1_hard_integrity_pass_required": True,
        "L3_or_L4_quality_findings_may_coexist_with_success": True,
        "typed_scoped_ref_contract_must_pass": True,
        "claim_fact_link_live_acceptance_must_pass": True,
        "supervision_v2_contract_must_pass": True,
        "transport_or_node_only_green_is_success": False,
        "failure_requires_typed_atomic_terminal_closeout": True,
        "failure_preserves_completed_assistant_outputs_and_usage": True,
        "paired_comparison_requires_separate_read_only_authority": True,
        "owner_acceptance_requires_user_confirmation": True,
    }
    result["supervision_v2_acceptance_contract"] = {
        "contract_ref": SUPERVISION_CONTRACT_REF,
        "actual_runner_self_finalized_exit_receipt_required": True,
        "direct_actual_runner_no_parent_timeout": True,
        "process_identity_requires_pid_and_creation_time": True,
        "monitoring_is_read_only": True,
        "retry_fallback_replay_relaunch_or_rerun_allowed": False,
    }
    result["issuance_preconditions"] = {
        "generator_reproduction_must_match_frozen_critical_sections": True,
        "exact_code_bindings_must_match": True,
        "double_prepare_must_remain_equal": True,
        "fresh_identity_and_admission_file_must_remain_absent": True,
        "target_database_and_object_tree_digests_must_match": True,
        "typed_ref_positive_and_closed_negative_regressions_must_pass": True,
        "layered_finding_disposition_regressions_must_pass": True,
        "nullable_owner_state_machine_regressions_must_pass": True,
        "supervision_v2_regressions_and_host_capability_must_pass": True,
        "project_os_scoped_preflight_must_pass_without_override": True,
        "admission_payload_must_equal_frozen_payload": True,
    }
    result["audit_contract"] = {
        "target_service_initialization_allowed": False,
        "target_SQLite_access": "direct_mode_ro_or_digest_only",
        "service_backed_preparation": "disposable_clone_only",
        "target_database_or_object_write_allowed": False,
        "credential_value_read_output_or_persisted": False,
        "historical_failed_provider_answer_read_or_rewritten": False,
        "latest_restricted_capture_promoted_or_synthesized": False,
    }
    result["experiment_governance"] = {
        "hypothesis": (
            "The shared typed scoped Claim-ref contract and layered finding "
            "disposition remove the latest owned Verifier blocker while "
            "preserving hard integrity and the complete three-Cell product path."
        ),
        "decision_target": (
            "One separately issued and separately authorized exact proof must "
            "reach succeeded/succeeded/succeeded with six logical nodes, twelve "
            "calls, nine current Artifact families, exact typed Claim refs, L1 "
            "pass and persisted L3/L4 findings."
        ),
        "ceiling": (
            "twelve semantic/provider/network calls, 16800 aggregate output "
            "tokens, USD 0.10, one transport attempt per call and no rerun"
        ),
        "baseline_and_leakage_guard": (
            "same exact business input head; baseline output body remains hidden; "
            "all historical Run identities and admissions are nonreusable"
        ),
        "stop_condition": (
            "The first credible parse, schema, truth, provenance, numeric, scope, "
            "identity, ClaimFactLink, typed-ref, state-machine, atomicity, "
            "supervision, capacity, budget, terminalization, capture or Artifact "
            "failure terminally stops without retry, fallback, patch, replay, "
            "relaunch or second run."
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
            "provider_calls": provider_callback_calls,
            "supervisor_launches": 0,
            "live_executions": 0,
            "new_business_artifacts": 0,
            "captured_output_promotions": 0,
        }
    )
    result["next_action"] = NEXT_ACTION
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", type=Path, default=RUNTIME_ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = prepare(runtime_root=args.runtime_root)
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output is None:
        print(rendered)
    else:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
