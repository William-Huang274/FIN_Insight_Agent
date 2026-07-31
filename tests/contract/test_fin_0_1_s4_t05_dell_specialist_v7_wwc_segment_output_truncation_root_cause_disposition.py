from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DECISION_PATH = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s4_t05_dell_specialist_v7_wwc_segment_output_truncation_zero_call_root_cause_disposition_v1_0.json"
)
RESULT_PATH = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s4_t05_dell_research_lead_gap_atom_projection_r5_exact_live_execution_failure_result_v1_0.json"
)
RUNTIME_RESULT_PATH = (
    ROOT
    / ".codex_runtime"
    / "fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1"
    / "s4_t05_dell_research_lead_gap_atom_projection_r5_r1_live_execution_result.json"
)
LAYERED_STANDARD_PATH = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_layered_agent_acceptance_standard_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_decision_binds_immutable_r5_failure_and_zero_call_scope() -> None:
    decision = _load(DECISION_PATH)
    source = decision["source_failure"]
    authority = decision["authority"]

    assert source["result_sha256"] == _sha256(RESULT_PATH)
    assert source["runtime_result_sha256"] == _sha256(RUNTIME_RESULT_PATH)
    assert source["failure_code"] == "s3_bounded_node_output_truncated"
    assert source["provider_output_tokens_and_limit"] == [1400, 1400]
    assert source["terminal_states"] == ["failed"] * 3
    assert source["artifact_count"] == 0
    assert source["research_lead_called"] is False
    assert authority["zero_call_restricted_capture_request_contract_and_budget_audit_authorized"] is True
    assert authority["runtime_prompt_schema_validator_fake_provider_or_transport_implementation_authorized"] is False
    assert authority["retry_replay_relaunch_rerun_or_replacement_admission_authorized"] is False
    assert all(value == 0 for value in decision["observed_counts"].values())


def test_restricted_audit_proves_near_complete_three_task_attempt_not_broad_noncompliance() -> None:
    audit = _load(DECISION_PATH)["restricted_zero_call_audit"]

    assert audit["raw_assistant_text_printed_or_persisted_by_audit"] is False
    assert audit["capture_utf8_bytes"] == 5258
    assert audit["capture_starts_with_object"] is True
    assert audit["capture_ends_with_object"] is False
    assert audit["json_error"] == "unterminated_string_at_byte_position_5249"
    assert audit["markdown_fence_or_private_reasoning_marker_observed"] is False
    assert audit["raw_forbidden_claim_id_observed"] is False
    assert audit["observed_task_id_count"] == 3
    assert audit["observed_decision_rule_count"] == 3
    assert audit["observed_time_window_count"] == 3
    assert "not evidence of broad JSON" in audit["structural_inference"]


def test_capacity_audit_locates_project_owned_denormalized_wire_contract() -> None:
    decision = _load(DECISION_PATH)
    capacity = decision["request_and_capacity_audit"]
    disposition = decision["layered_acceptance_disposition"]

    assert capacity["current_provider_task_cardinality"] == [1, 3]
    assert capacity["narrative_fields_per_task"] == 13
    assert capacity["narrative_field_max_chars"] == 320
    assert capacity["segment_output_token_cap"] == 1400
    assert capacity["segment_serialized_byte_cap"] == 6000
    assert capacity["maximum_shape_bytes_for_three_tasks_at_field_maximum"] > 6000
    assert capacity["observed_output_bytes_at_token_cap"] < 6000
    assert capacity["token_and_byte_envelope_aligned_with_stable_headroom"] is False
    assert disposition["classification"] == "L1_hard_capacity_fail_closed"
    assert disposition["downgrade_to_L3_quality_finding_allowed"] is False
    assert disposition["provider_route_or_model_is_first_demonstrated_cause"] is False
    assert disposition["acceptance_standard_sha256"] == _sha256(LAYERED_STANDARD_PATH)


def test_r4_success_and_r5_truncation_prove_feasible_but_unstable_envelope() -> None:
    comparison = _load(DECISION_PATH)["historical_comparison"]

    assert comparison["R4"]["same_DELL_input_digest_and_current_segmented_path"] is True
    assert comparison["R4"]["WWC_valid_json"] is True
    assert comparison["R4"]["task_count"] == 3
    assert comparison["R4"]["output_tokens"] == 1050
    assert comparison["R5"]["attempted_task_count"] == 3
    assert comparison["R5"]["output_tokens"] == 1400
    assert comparison["R5"]["finish_reason"] == "length"
    assert "no stable generation headroom" in comparison["conclusion"]


def test_selected_contract_moves_canonical_task_structure_to_local_assembly() -> None:
    contract = _load(DECISION_PATH)["selected_minimum_implementation_contract"]
    provider = contract["provider_surface"]
    local = contract["local_deterministic_assembly"]
    headroom = contract["bounded_headroom"]

    assert contract["contract_ref"] == (
        "fin01.s3.specialist_WWC_judgment_atom_deterministic_assembly:v1"
    )
    assert contract["new_transport_ref"].endswith(":v8")
    assert provider["cardinality"] == [1, 3]
    assert provider["narrative_field_max_chars"] == 160
    assert provider["provider_emits_task_id"] is False
    assert provider["provider_emits_source_target"] is False
    assert provider["provider_emits_as_of"] is False
    assert provider["provider_emits_nested_canonical_decision_rule_or_time_window"] is False
    assert local["owns_task_id"] is True
    assert local["owns_authority_alias_expansion_and_kind_validation"] is True
    assert local["owns_source_target_from_primary_authority_metadata"] is True
    assert local["owns_time_window_as_of_from_exact_input"] is True
    assert local["silent_atom_drop_allowed"] is False
    assert headroom["WWC_segment_output_token_cap"] == 1800
    assert headroom["three_cell_full_chain_maximum_output_tokens"] == 18000
    assert headroom["blind_future_cap_increase_allowed"] is False


def test_decision_stays_within_t05_and_routes_only_to_zero_call_implementation() -> None:
    decision = _load(DECISION_PATH)
    sequence = decision["sequence_boundary"]
    acceptance = decision["minimum_implementation_acceptance"]
    stage = decision["stage_acceptance"]

    assert sequence["current_sequence"] == (
        "RC_P36_062_specialist_WWC_capacity_disposition_only"
    )
    assert sequence["implementation_in_this_decision"] is False
    assert sequence["RC_P36_061_status_unchanged"].endswith(
        "projection_live_observation_unproven"
    )
    assert "Writer_and_Verifier_atomization" in sequence["deferred_to_S4_T10_to_S5"]
    assert acceptance["versioned_v8_transport_preserves_v1_through_v7_historical_behavior"] is True
    assert acceptance["R3_R4_R5_results_and_restricted_captures_immutable"] is True
    assert stage["RC_P36_062"].endswith("implementation_pending")
    assert stage["DELL_R2"] == "not_proven"
    assert stage["S4_T06"] == "not_entered"
    assert decision["next_action"] == (
        "S4-T05-DELL-SPECIALIST-WWC-JUDGMENT-ATOM-AND-"
        "DETERMINISTIC-TASK-ASSEMBLY-MINIMUM-ZERO-CALL-IMPLEMENTATION"
    )
