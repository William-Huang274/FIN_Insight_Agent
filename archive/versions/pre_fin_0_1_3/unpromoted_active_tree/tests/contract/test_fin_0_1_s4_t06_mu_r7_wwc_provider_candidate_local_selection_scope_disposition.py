from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DECISION_PATH = (
    ROOT
    / "configs"
    / "releases"
    / (
        "fin_ia_0_1_s4_t06_mu_r7_wwc_provider_candidate_"
        "local_selection_scope_disposition_v1_0.json"
    )
)
RESULT_PATH = (
    ROOT
    / "configs"
    / "releases"
    / (
        "fin_ia_0_1_s4_t06_mu_claim_support_role_v2_r7_"
        "exact_live_execution_failure_result_v1_0.json"
    )
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_decision_binds_immutable_R7_and_zero_call_scope() -> None:
    decision = _load(DECISION_PATH)
    source = decision["source_failure"]
    authority = decision["authority"]
    counts = decision["observed_counts_this_disposition"]

    assert source["result_sha256"] == _sha256(RESULT_PATH)
    assert source["R7_consumed_and_immutable"] is True
    assert source["failure_code"] == "s4_compiled_wwc_atom_shape_invalid"
    assert source["provider_returned_candidate_count"] == 6
    assert source["model_visible_provider_candidate_maximum"] == 6
    assert source["executed_local_input_maximum"] == 3
    assert source["local_selection_ran_before_rejection"] is False
    assert source["model_instruction_noncompliance_established"] is False
    assert source["project_owned_contract_drift_established"] is True
    assert authority["runtime_implementation_authorized_in_this_turn"] is False
    assert authority["R8_or_replacement_exact_live_authorized"] is False
    assert all(value == 0 for value in counts.values())


def test_code_audit_isolates_WWC_parity_from_fact_and_claim_paths() -> None:
    audit = _load(DECISION_PATH)["zero_call_code_audit"]

    assert audit["provider_candidate_maximum"] == 6
    assert audit["fact_final_selected_maximum"] == 3
    assert audit["claim_final_selected_maximum"] == 2
    assert audit["WWC_final_selected_maximum"] == 3
    assert audit["fact_path_accepts_candidate_maximum_before_local_selection"]
    assert audit["claim_path_accepts_candidate_maximum_before_local_selection"]
    assert not audit["WWC_path_accepts_candidate_maximum_before_local_selection"]
    assert audit["WWC_path_current_rejecting_constant"] == (
        "fact_selected_maximum"
    )
    assert audit["WWC_candidate_atoms_are_alias_and_finite_enum_only"] is True
    assert audit["WWC_provider_free_material_narrative_allowed"] is False


def test_disposition_selects_bounded_local_selection_not_surface_block() -> None:
    decision = _load(DECISION_PATH)
    options = {row["option_id"]: row for row in decision["option_disposition"]}
    contract = decision["selected_minimum_implementation_contract"]

    assert options["block_provider_authored_WWC_surface"]["decision"] == (
        "rejected_for_current_scope"
    )
    assert options[
        "validate_up_to_six_then_deterministically_select_up_to_three"
    ]["decision"] == "selected"
    assert options["raise_final_WWC_maximum_to_six"]["decision"] == "rejected"
    assert options[
        "silently_take_first_three_or_drop_invalid_candidates"
    ]["decision"] == "rejected"
    assert contract["maximum_zero_call_implementation_bundles"] == 1
    assert contract["automatic_follow_on_implementation_bundles"] == 0
    assert contract["provider_candidate_contract"]["maximum_candidate_count"] == 6
    assert contract["deterministic_selection"]["final_selected_maximum"] == 3
    assert contract["deterministic_selection"][
        "model_generated_score_or_free_form_rank_used"
    ] is False


def test_validation_precedes_selection_and_preserves_hard_gates() -> None:
    decision = _load(DECISION_PATH)
    contract = decision["selected_minimum_implementation_contract"]
    validation = contract["pre_selection_validation"]
    acceptance = decision["minimum_implementation_acceptance"]

    assert validation["validate_every_candidate_before_selection"] is True
    assert validation["invalid_candidate_can_be_silently_dropped"] is False
    assert validation["unknown_cross_case_or_wrong_kind_alias"].startswith(
        "L1_hard_integrity"
    )
    assert validation["unbound_or_conflicting_date_alias"].startswith(
        "L1_hard_temporal"
    )
    assert acceptance["boundary_candidate_counts"] == {
        "zero": "typed failure",
        "one": "one selected task",
        "three": "three selected tasks",
        "six": "three deterministically selected tasks",
        "seven": "typed candidate cardinality failure",
    }
    assert acceptance["one_invalid_candidate_among_six_fails_before_selection"]
    assert acceptance["permutation_stability_for_same_valid_candidate_set"]
    assert acceptance["DELL_MU_NVDA_full_fake_required"] is True
    assert acceptance["per_case_required_nodes_callbacks_captures_artifacts"] == [
        6,
        12,
        12,
        9,
    ]


def test_decision_does_not_authorize_new_live_or_expand_T06() -> None:
    decision = _load(DECISION_PATH)
    sequence = decision["sequence_boundary"]
    stage = decision["stage_disposition"]

    assert sequence["implementation_in_this_decision"] is False
    assert stage["R7"] == "immutable_terminal_failed_consumed_no_retry"
    assert stage["R8_or_replacement_exact_live"] == "not_authorized"
    assert stage["paired_assessment"] == "not_eligible"
    assert stage["owner_acceptance"] == "not_eligible"
    assert stage["S4_T07"] == "not_entered"
    assert decision["minimum_implementation_acceptance"][
        "remaining_formal_MU_exact_live_ceiling"
    ] == 0
    assert decision["next_action"] == (
        "S4-T06-MU-WWC-PROVIDER-CANDIDATE-VALIDATION-AND-"
        "DETERMINISTIC-FINAL-SELECTION-MINIMUM-ZERO-CALL-IMPLEMENTATION"
    )
    assert decision["next_action_authorized"] is False
