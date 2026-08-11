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
DECISION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_wwc_numeric_authority_surface_"
    "zero_call_root_cause_disposition_v1_0.json"
)
FAILURE = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_task_claim_link_policy_r3_"
    "exact_live_execution_failure_result_v1_0.json"
)
PROGRAM_BACKLOG = (
    ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
)
S4_BACKLOG = (
    ROOT / "configs/releases/fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
)
IMPLEMENTATION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_wwc_numeric_authority_surface_"
    "minimum_zero_call_implementation_v1_0.json"
)
PROOF = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_wwc_numeric_authority_surface_"
    "fresh_agent_proof_decision_v1_0.json"
)
ISSUANCE = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_wwc_numeric_authority_surface_"
    "fresh_exact_admission_issuance_v1_0.json"
)
AUTHORITY = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_wwc_numeric_authority_r4_"
    "exact_live_execution_and_paired_assessment_authority_decision_v1_0.json"
)
R4_FAILURE = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_wwc_numeric_authority_r4_"
    "exact_live_execution_failure_result_v1_0.json"
)
GAP_PROJECTION_DISPOSITION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_research_lead_remaining_"
    "gaps_cardinality_zero_call_root_cause_disposition_v1_0.json"
)
LATEST_RUNTIME_IMPLEMENTATION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_research_lead_gap_atom_"
    "deterministic_projection_minimum_zero_call_implementation_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_disposition_is_bound_to_the_immutable_R3_failure() -> None:
    decision = _load(DECISION)
    source = decision["source_failure"]
    failure = _load(FAILURE)

    assert source["result_sha256"] == _sha256(FAILURE)
    assert source["failure_code"] == "s3_owner_grade_WWC_task_incomplete"
    assert source["terminal_states"] == ["failed", "failed", "failed"]
    assert source["artifact_count"] == 0
    assert source["fact_support_numeric_ref_count"] == 6
    assert source["legacy_WWC_numeric_ref_count"] == 0
    assert source["model_or_provider_fault"] is False
    assert failure["root_cause_classification"]["new_issue_id"] == (
        "RC-P36-060-s4-WWC-numeric-authority-surface-drift"
    )


def test_disposition_selects_one_closed_field_local_membership_owner() -> None:
    selected = _load(DECISION)["selected_minimum_implementation_contract"]

    assert selected["contract_ref"] == (
        "fin01.s3.what_would_change_authority_policy:v1"
    )
    assert selected["single_machine_native_membership_owner"] == (
        "cell_input.authority_refs"
    )
    assert selected["allowed_refs_by_authority_class"] == {
        "Evidence": "accepted_evidence_refs",
        "Numeric": "numeric_refs",
        "Candidate": "candidate_refs_not_evidence",
        "Graph": "graph_context_refs_not_evidence",
    }
    assert selected["provider_request_must_expose_the_exact_closed_field_local_surface"]
    assert selected["local_validator_must_consume_the_same_policy_instance_or_canonical_projection"]
    assert selected["legacy_numeric_reconstruction_union_allowed"] is False
    assert selected["numeric_input_role_after_repair"].endswith(
        "not_membership_authority"
    )
    assert selected["L1_fail_closed_unchanged"] is True


def test_disposition_adds_only_blocker_specific_safe_telemetry() -> None:
    decision = _load(DECISION)
    failure = decision["selected_minimum_implementation_contract"][
        "blocker_specific_safe_failure"
    ]

    assert failure["failure_code"] == "s3_owner_grade_WWC_task_authority_invalid"
    assert set(failure["closed_subtypes"]) == {
        "authority_refs_not_nonempty_string_array",
        "authority_ref_outside_current_cell_closed_surface",
    }
    assert failure["content_free_telemetry_only"] is True
    assert failure["complete_WWC_failure_taxonomy_claimed"] is False
    assert "complete_typed_WWC_failure_taxonomy" in decision[
        "sequence_boundary"
    ]["deferred_to_S4_T10_to_S5"]


def test_disposition_is_zero_call_and_does_not_authorize_execution() -> None:
    decision = _load(DECISION)

    assert set(decision["observed_counts"].values()) == {0}
    assert decision["authority"]["runtime_patch_authorized"] is False
    assert decision["authority"]["fourth_DELL_execution_authorized"] is False
    assert decision["authority"]["paired_assessment_authorized"] is False
    assert decision["stage_acceptance"]["DELL_R2"] == "not_proven"
    assert decision["next_action"] == (
        "S4-T05-DELL-WWC-NUMERIC-AUTHORITY-SURFACE-MINIMUM-"
        "ZERO-CALL-IMPLEMENTATION"
    )


def test_backlogs_advance_only_to_the_separate_zero_call_implementation() -> None:
    decision = _load(DECISION)
    program = _load(PROGRAM_BACKLOG)
    detailed = _load(S4_BACKLOG)
    task = next(row for row in detailed["tasks"] if row["item_id"] == "S4-T05")

    current_next = (
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
        _load(LATEST_RUNTIME_IMPLEMENTATION)["next_action"]
        if LATEST_RUNTIME_IMPLEMENTATION.exists()
        else _load(GAP_PROJECTION_DISPOSITION)["next_action"]
        if GAP_PROJECTION_DISPOSITION.exists()
        else
        _load(R4_FAILURE)["next_action"]
        if R4_FAILURE.exists()
        else _load(AUTHORITY)["conditional_next_action"][
            "on_authority_decision_complete"
        ]
        if AUTHORITY.exists()
        else _load(ISSUANCE)["next_action"]
        if ISSUANCE.exists()
        else _load(PROOF)["next_action"]
        if PROOF.exists()
        else _load(IMPLEMENTATION)["next_action"]
        if IMPLEMENTATION.exists()
        else decision["next_action"]
    )
    assert program["next_action"]["item_id"] == current_next
    assert program["next_action"]["S4_T05_RC_P36_060_status"] == (
        "closed_R4_live_path_positive_evidence_before_new_failure"
        if R4_FAILURE.exists()
        else "R4_exact_live_authorized_execution_not_started"
        if AUTHORITY.exists()
        else "fresh_exact_admission_issued_unconsumed_execution_authority_pending"
        if ISSUANCE.exists()
        else "fresh_proof_contract_frozen_admission_issuance_pending"
        if PROOF.exists()
        else "implementation_fixture_proven_fresh_agent_proof_pending"
        if IMPLEMENTATION.exists()
        else "root_cause_disposed_minimum_shared_WWC_authority_policy_"
        "selected_implementation_pending"
    )
    assert detailed["current_next_action"] == current_next
    assert task["RC_P36_060_status"] == (
        "closed_R4_live_path_positive_evidence_before_new_failure"
        if R4_FAILURE.exists()
        else "R4_exact_live_authorized_execution_not_started"
        if AUTHORITY.exists()
        else "fresh_exact_admission_issued_unconsumed_execution_authority_pending"
        if ISSUANCE.exists()
        else "fresh_proof_contract_frozen_admission_issuance_pending"
        if PROOF.exists()
        else "implementation_fixture_proven_fresh_agent_proof_pending"
        if IMPLEMENTATION.exists()
        else "root_cause_disposed_minimum_shared_WWC_authority_policy_"
        "selected_implementation_pending"
    )
    assert task["fourth_execution_authorized"] is AUTHORITY.exists()
    if R4_FAILURE.exists():
        assert detailed["observed_counts"] == {
            "model_calls": 10,
            "provider_calls": 10,
            "network_calls": 10,
            "source_network_calls": 0,
            "external_tool_calls": 0,
            "new_research_runs": 1,
            "new_business_artifacts": 0,
            "human_reviews": 0,
        }
    else:
        assert set(detailed["observed_counts"].values()) == {0}


def test_decision_contains_no_plaintext_credential() -> None:
    rendered = DECISION.read_text(encoding="utf-8").lower()
    assert "sk-" not in rendered
    assert "fixture-secret" not in rendered
