from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DECISION_PATH = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s4_t05_dell_research_lead_remaining_gaps_cardinality_zero_call_root_cause_disposition_v1_0.json"
)
RESULT_PATH = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s4_t05_dell_wwc_numeric_authority_r4_exact_live_execution_failure_result_v1_0.json"
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


def test_decision_binds_the_immutable_r4_failure_and_zero_call_scope() -> None:
    decision = _load(DECISION_PATH)
    source = decision["source_failure"]
    authority = decision["authority"]
    observed = decision["observed_counts"]

    assert source["result_sha256"] == _sha256(RESULT_PATH)
    assert source["failure_code"] == (
        "s3_bounded_research_lead_v3_cardinality_above_maximum"
    )
    assert source["request_and_validator_cardinality"] == [1, 4]
    assert source["excess_item_count"] == 4
    assert source["inferred_observed_item_count"] == 8
    assert source["request_validator_schema_drift"] is False
    assert source["direct_model_output_contract_nonconformance"] is True
    assert source["historical_terminal_states"] == ["failed"] * 3
    assert source["historical_artifact_count"] == 0

    assert authority["zero_call_root_cause_disposition_authorized"] is True
    assert (
        authority[
            "runtime_prompt_schema_validator_telemetry_or_fake_provider_implementation_authorized"
        ]
        is False
    )
    assert authority["replacement_admission_or_fifth_DELL_execution_authorized"] is False
    assert all(value == 0 for value in observed.values())


def test_decision_applies_layered_acceptance_without_calling_overflow_quality_only() -> None:
    decision = _load(DECISION_PATH)
    standard = _load(LAYERED_STANDARD_PATH)
    disposition = decision["layered_acceptance_disposition"]

    assert disposition["acceptance_standard_sha256"] == _sha256(
        LAYERED_STANDARD_PATH
    )
    l2 = next(
        layer
        for layer in standard["acceptance_layers"]
        if layer["layer_id"] == "L2_recoverable_protocol"
    )
    assert "schema shape and cardinality" in l2["gates"]
    assert disposition["classification"].startswith("L2_recoverable_protocol")
    assert disposition["not_classified_as_L3_quality_only"] is True
    assert disposition["historical_run_remains_terminal_failed"] is True
    assert disposition["historical_capture_remains_immutable"] is True


def test_historical_eight_items_are_not_retroactively_declared_valid_or_projected() -> None:
    decision = _load(DECISION_PATH)
    audit = decision["zero_call_code_audit"]
    boundary = decision["hard_and_recoverable_boundary"]

    assert audit["current_validation_order"].startswith(
        "list_type_then_cardinality"
    )
    assert (
        audit[
            "historical_eight_items_individually_shape_authority_or_semantic_validated"
        ]
        is False
    )
    assert audit["historical_output_safe_to_retroactively_project"] is False
    assert boundary["historical_failed_capture_repair"] == "forbidden"


def test_selected_contract_validates_all_atoms_then_projects_deterministic_top_four() -> None:
    decision = _load(DECISION_PATH)
    contract = decision["selected_minimum_implementation_contract"]
    provider = contract["provider_surface"]
    validation = contract["pre_projection_validation"]
    ranking = contract["deterministic_ranking"]
    projection = contract["local_canonical_projection"]
    telemetry = contract["recoverable_protocol_telemetry"]

    assert contract["contract_ref"] == (
        "fin01.s3.research_lead_gap_atom_deterministic_projection:v1"
    )
    assert provider["field_id"] == "remaining_gap_atoms"
    assert provider["minimum_candidate_count"] == 1
    assert provider["independent_semantic_maximum_candidate_count"] is None
    assert provider["provider_emits_gap_id"] is False
    assert validation["validate_every_candidate_before_selection"] is True
    assert validation["any_invalid_candidate_can_be_silently_dropped"] is False
    assert ranking["canonical_output_maximum"] == 4
    assert ranking["model_generated_priority_score_used"] is False
    assert ranking["ticker_case_or_provider_specific_branch_allowed"] is False
    assert projection["canonical_field_id"] == "remaining_gaps"
    assert projection["canonical_cardinality"] == [1, 4]
    assert projection["gap_id_owner"].startswith("local_deterministic")
    assert telemetry["layer"] == "L2_recoverable_protocol"
    assert telemetry["terminal"] is False
    assert telemetry["provider_nonconformance_hidden"] is False


def test_hard_boundary_and_future_acceptance_matrix_prevent_silent_drop() -> None:
    decision = _load(DECISION_PATH)
    boundary = decision["hard_and_recoverable_boundary"]
    acceptance = decision["minimum_implementation_acceptance"]

    assert boundary["overflow_only_after_all_candidate_validation"] == (
        "L2_recoverable_continue"
    )
    assert boundary["malformed_blank_or_non_string_candidate"].startswith(
        "fail_closed"
    )
    assert boundary["unknown_wrong_kind_cross_cell_or_out_of_surface_ref"].startswith(
        "L1_hard_integrity"
    )
    assert acceptance["fixture_valid_candidate_counts"] == [1, 4, 8]
    assert acceptance["eight_valid_candidate_expectation"] == {
        "canonical_gap_count": 4,
        "overflow_count": 4,
        "terminal": False,
        "L2_finding_persisted": True,
    }
    assert (
        acceptance[
            "malformed_or_unknown_ref_in_eight_candidate_fixture_fails_before_selection"
        ]
        is True
    )
    assert acceptance["historical_R4_result_capture_and_terminal_truth_are_immutable"] is True


def test_decision_stays_within_t05_and_routes_only_to_minimum_implementation() -> None:
    decision = _load(DECISION_PATH)
    sequence = decision["sequence_boundary"]
    stage = decision["stage_acceptance"]

    assert sequence["current_sequence"] == (
        "RC_P36_061_remaining_gap_overflow_disposition_only"
    )
    assert sequence["implementation_in_this_decision"] is False
    assert stage["RC_P36_061"].endswith("implementation_pending")
    assert stage["DELL_R2"] == "not_proven"
    assert stage["S4_T06"] == "not_entered"
    assert decision["next_action"] == (
        "S4-T05-DELL-RESEARCH-LEAD-REMAINING-GAP-ATOM-"
        "DETERMINISTIC-PROJECTION-MINIMUM-ZERO-CALL-IMPLEMENTATION"
    )
