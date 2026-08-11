from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
R7_BINDING_IMPLEMENTATION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_r7_profile_v2_versioned_"
    "case_runtime_binding_and_create_app_preflight_minimum_zero_call_"
    "implementation_v1_0.json"
)
WWC_TRUNCATION_DISPOSITION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_specialist_wwc_judgment_atom_"
    "deterministic_assembly_fresh_agent_proof_decision_v1_0.json"
)
WWC_ATOM_ISSUANCE = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_r6_research_profile_v2_"
    "case_runtime_binding_mismatch_zero_call_root_cause_disposition_v1_0.json"
)
GAP_PROJECTION_R5_FAILURE_RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_research_lead_gap_atom_"
    "projection_r5_exact_live_execution_failure_result_v1_0.json"
)
GAP_PROJECTION_AUTHORITY = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_research_lead_gap_atom_"
    "projection_r5_exact_live_execution_and_paired_assessment_"
    "authority_decision_v1_0.json"
)
GAP_PROJECTION_ISSUANCE = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_research_lead_gap_atom_"
    "deterministic_projection_fresh_exact_admission_issuance_v1_0.json"
)
GAP_PROJECTION_FRESH_PROOF = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_research_lead_gap_atom_"
    "deterministic_projection_fresh_agent_proof_decision_v1_0.json"
)
DECISION = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_dell_wwc_task_to_claim_closed_identity_"
    "zero_call_root_cause_disposition_v1_0.json"
)
FAILURE_RESULT = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_dell_replacement_exact_r2_"
    "execution_failure_result_v1_0.json"
)
TASK_CLAIM_IMPLEMENTATION = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_task_claim_link_policy_minimum_"
    "zero_call_implementation_v1_0.json"
)
TASK_CLAIM_PROOF = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_task_claim_link_policy_"
    "fresh_agent_proof_decision_v1_0.json"
)
TASK_CLAIM_ISSUANCE = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_task_claim_link_policy_"
    "fresh_exact_admission_issuance_v1_0.json"
)
TASK_CLAIM_AUTHORITY = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_dell_task_claim_link_policy_r3_"
    "exact_live_execution_and_paired_assessment_"
    "authority_decision_v1_0.json"
)
R3_FAILURE_RESULT = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_dell_task_claim_link_policy_r3_"
    "exact_live_execution_failure_result_v1_0.json"
)
NUMERIC_AUTHORITY_DISPOSITION = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_dell_wwc_numeric_authority_surface_"
    "zero_call_root_cause_disposition_v1_0.json"
)
NUMERIC_AUTHORITY_IMPLEMENTATION = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_specialist_wwc_judgment_atom_deterministic_"
    "task_assembly_minimum_zero_call_implementation_v1_0.json"
)
NUMERIC_AUTHORITY_PROOF = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_wwc_numeric_authority_surface_fresh_agent_"
    "proof_decision_v1_0.json"
)
NUMERIC_AUTHORITY_ISSUANCE = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_wwc_numeric_authority_surface_fresh_exact_"
    "admission_issuance_v1_0.json"
)
NUMERIC_AUTHORITY_DECISION = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_dell_wwc_numeric_authority_r4_exact_live_"
    "execution_and_paired_assessment_authority_decision_v1_0.json"
)
R4_FAILURE_RESULT = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_dell_wwc_numeric_authority_r4_"
    "exact_live_execution_failure_result_v1_0.json"
)
GAP_PROJECTION_DISPOSITION = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_dell_research_lead_remaining_gaps_cardinality_"
    "zero_call_root_cause_disposition_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_decision_binds_the_exact_immutable_failure() -> None:
    decision = _load(DECISION)
    failure = _load(FAILURE_RESULT)
    source = decision["source_failure"]
    observed = failure["first_credible_failure"]

    assert source["result_sha256"] == _sha256(FAILURE_RESULT)
    assert source["research_run_id"] == failure["identity"]["research_run_id"]
    assert source["failure_code"] == observed["failure_code"]
    assert source["validated_claim_ids"] == observed["validated_claim_ids"]
    assert source["returned_task_claim_ids"] == observed[
        "returned_task_claim_ids"
    ]
    assert source["unknown_task_claim_ids"] == ["C3"]
    assert source["shape_complete_task_count"] == 3
    assert source["current_L1_fail_closed_disposition_correct"] is True


def test_minimum_shared_closed_alias_contract_is_selected() -> None:
    decision = _load(DECISION)
    selected = decision["selected_minimum_contract"]

    assert selected["contract_ref"] == "fin01.s3.task_claim_link_policy:v1"
    assert selected["request_local_claim_alias_prefix"] == "Q"
    assert selected["alias_table_source"] == (
        "already_validated_current_Cell_owner_grade_claim_cards"
    )
    assert selected["provider_response_field"] == "claim_alias"
    assert selected["local_canonical_output_field"] == "claim_id"
    assert selected["minimum_new_failure_subtype"] == (
        "task_claim_alias_unknown"
    )
    assert selected["task_id_behavior_in_this_slice"] == (
        "retain_existing_provider_generated_nonblank_unique_within_Cell_validation"
    )
    assert selected[
        "fuzzy_match_trim_casefold_prefix_guess_nearest_claim_"
        "silent_relink_task_drop_or_answer_rewrite_allowed"
    ] is False
    assert selected["historical_failed_answer_or_consumed_Run_mutated"] is False


def test_single_sequence_scope_is_bounded_and_later_work_is_carried() -> None:
    decision = _load(DECISION)
    boundary = decision["current_sequence_implementation_boundary"]
    deferred = {
        row["item"]: row
        for row in decision["deferred_cross_sequence_items"]
    }

    assert boundary["implementation_authorized_in_this_decision"] is False
    assert boundary["fresh_proof_or_paid_execution_authorized_in_this_decision"] is False
    assert {
        "local generation or global redesign of task_id",
        "complete decomposition of every s3_owner_grade_WWC_task_incomplete predicate",
        "cross-stage task identity migration",
    }.issubset(set(boundary["explicit_non_goals"]))
    assert deferred["deterministic_locally_assembled_task_identity"][
        "target"
    ] == "S4-T10-to-S5-carry-forward"
    assert deferred["complete_typed_WWC_failure_taxonomy"][
        "blocks_current_T05"
    ] is False
    assert deferred["cross_stage_unified_claim_task_identity_redesign"][
        "target"
    ] == "S5-or-later-architecture-sequence"


def test_shortcuts_calls_and_progression_are_forbidden() -> None:
    decision = _load(DECISION)
    alternatives = {
        row["option"]: row["decision"]
        for row in decision["alternatives"]
    }
    acceptance = decision["future_zero_call_implementation_acceptance"]

    assert alternatives[
        "rewrite_C3_to_C1_or_C2_drop_the_third_task_or_relax_the_validator"
    ] == "rejected"
    assert alternatives[
        "add_DELL_or_third_Cell_specific_prompt_examples"
    ] == "rejected"
    assert alternatives[
        "redesign_all_task_ids_all_failure_subtypes_and_all_cross_stage_identity_now"
    ] == "deferred_to_later_sequence"
    assert set(decision["observed_counts"].values()) == {0}
    assert acceptance[
        "model_provider_network_source_external_tool_calls_allowed"
    ] == [0, 0, 0, 0, 0]
    assert acceptance["admission_Run_or_business_Artifact_creation_allowed"] is False
    assert acceptance["implementation_pass_does_not_prove_DELL_R2"] is True
    assert decision["stage_decision"]["S4_T06_or_later"] == "not_entered"
    assert decision["next_action"] == (
        "S4-T05-DELL-WWC-TASK-TO-CLAIM-CLOSED-IDENTITY-"
        "MINIMUM-ZERO-CALL-IMPLEMENTATION"
    )


def test_project_state_points_only_to_the_bounded_implementation() -> None:
    decision_sha = _sha256(DECISION)
    detailed = _load(
        ROOT
        / "configs/releases/"
        "fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
    )
    program = _load(
        ROOT
        / "configs/releases/"
        "fin_ia_0_1_program_release_backlog_v2_0.json"
    )
    next_action = program["next_action"]

    expected_next = (
        _load(ROOT / "configs/releases/fin_ia_0_1_s4_t05_dell_r7_profile_v2_binding_exact_live_execution_failure_result_v1_0.json")["next_action"]
        if R7_BINDING_IMPLEMENTATION.exists()
        else _load(WWC_ATOM_ISSUANCE)["next_action"]
        if WWC_ATOM_ISSUANCE.exists()
        else _load(WWC_TRUNCATION_DISPOSITION)["next_action"]
        if WWC_TRUNCATION_DISPOSITION.exists()
        else
        _load(GAP_PROJECTION_R5_FAILURE_RESULT)["next_action"]
        if GAP_PROJECTION_R5_FAILURE_RESULT.exists()
        else _load(GAP_PROJECTION_AUTHORITY)["conditional_next_action"][
            "on_authority_decision_complete"
        ]
        if GAP_PROJECTION_AUTHORITY.exists()
        else _load(GAP_PROJECTION_ISSUANCE)["next_action"]
        if GAP_PROJECTION_ISSUANCE.exists()
        else _load(GAP_PROJECTION_FRESH_PROOF)["next_action"]
        if GAP_PROJECTION_FRESH_PROOF.exists()
        else
        _load(NUMERIC_AUTHORITY_IMPLEMENTATION)["next_action"]
        if NUMERIC_AUTHORITY_IMPLEMENTATION.exists()
        else _load(GAP_PROJECTION_DISPOSITION)["next_action"]
        if GAP_PROJECTION_DISPOSITION.exists()
        else
        _load(R4_FAILURE_RESULT)["next_action"]
        if R4_FAILURE_RESULT.exists()
        else _load(NUMERIC_AUTHORITY_DECISION)["conditional_next_action"][
            "on_authority_decision_complete"
        ]
        if NUMERIC_AUTHORITY_DECISION.exists()
        else _load(NUMERIC_AUTHORITY_ISSUANCE)["next_action"]
        if NUMERIC_AUTHORITY_ISSUANCE.exists()
        else _load(NUMERIC_AUTHORITY_PROOF)["next_action"]
        if NUMERIC_AUTHORITY_PROOF.exists()
        else _load(NUMERIC_AUTHORITY_IMPLEMENTATION)["next_action"]
        if NUMERIC_AUTHORITY_IMPLEMENTATION.exists()
        else
        _load(NUMERIC_AUTHORITY_DISPOSITION)["next_action"]
        if NUMERIC_AUTHORITY_DISPOSITION.exists()
        else _load(R3_FAILURE_RESULT)["next_action"]
        if R3_FAILURE_RESULT.exists()
        else
        _load(TASK_CLAIM_AUTHORITY)["conditional_next_action"][
            "on_authority_decision_complete"
        ]
        if TASK_CLAIM_AUTHORITY.exists()
        else
        _load(TASK_CLAIM_ISSUANCE)["next_action"]
        if TASK_CLAIM_ISSUANCE.exists()
        else
        "S4-T05-DELL-WWC-TASK-TO-CLAIM-CLOSED-IDENTITY-"
        "FRESH-EXACT-ADMISSION-ISSUANCE-DECISION"
        if TASK_CLAIM_PROOF.exists()
        else "S4-T05-DELL-WWC-TASK-TO-CLAIM-CLOSED-IDENTITY-"
        "FRESH-AGENT-PROOF-DECISION"
        if TASK_CLAIM_IMPLEMENTATION.exists()
        else "S4-T05-DELL-WWC-TASK-TO-CLAIM-CLOSED-IDENTITY-"
        "MINIMUM-ZERO-CALL-IMPLEMENTATION"
    )
    assert detailed["current_next_action"] == expected_next
    assert next_action["item_id"] == detailed["current_next_action"]
    assert next_action["S4_T05_WWC_task_claim_disposition_sha256"] == (
        decision_sha
    )
    assert next_action["S4_T05_minimum_implementation_authorized"] is (
        TASK_CLAIM_IMPLEMENTATION.exists()
    )
    assert next_action["S4_T05_deferred_to_S4_T10_to_S5"] == [
        "deterministic_locally_assembled_task_identity",
        "complete_typed_WWC_failure_taxonomy",
    ]
    assert next_action["S4_T05_deferred_to_S5_or_later"] == [
        "cross_stage_unified_claim_task_identity_redesign"
    ]
    assert next_action["current_S4_T05_third_execution_authorized"] is (
        TASK_CLAIM_AUTHORITY.exists()
    )
