from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DECISION = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_s4_t06_mu_r3_current_case_identity_token_policy_"
    "overconstraint_program_scope_replace_or_block_decision_v1_0.json"
)
R3_FAILURE = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_s4_t06_mu_mandatory_material_truth_identity_safety_"
    "closure_r3_exact_live_execution_failure_result_v1_0.json"
)
SAFETY_IMPLEMENTATION = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_s4_t06_mu_case_runtime_mandatory_material_truth_"
    "identity_safety_closure_minimum_zero_call_implementation_v1_0.json"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_decision_is_grounded_in_r3_and_grants_no_execution() -> None:
    decision = _load(DECISION)
    failure = _load(R3_FAILURE)
    evidence = decision["source_evidence"]
    assert evidence["R3_failure_result"]["sha256"] == _sha256(
        R3_FAILURE
    )
    assert evidence["safety_closure_implementation"][
        "sha256"
    ] == _sha256(SAFETY_IMPLEMENTATION)
    assert failure["first_credible_failure"]["failure_code"] == (
        "s4_case_delivery_identity_provider_narrative_invalid"
    )
    assert failure["restricted_content_free_reaudit"] == {
        "current_case_ticker_occurrences": 4,
        "nonlocal_known_ticker_occurrences": {
            "DELL": 0,
            "NVDA": 0,
        },
        "provider_response_finish_reason_stop": True,
        "numeric_failure_observed": False,
        "cross_case_identity_pollution_observed": False,
        "conclusion": (
            "The output used the correct local MU identity only; the "
            "runtime rejected it because provider_narrative_has_entity_token "
            "forbids every known ticker including the current case ticker."
        ),
    }
    assert decision["decision_label"] == "scope_replace"
    authority = decision["authority_boundary"]
    assert authority[
        "program_scope_replace_or_block_decision_authorized"
    ]
    for key, value in authority.items():
        if key not in {
            "program_scope_replace_or_block_decision_authorized",
            "replacement_contract_design_authorized",
        }:
            assert value is False
    assert set(decision["observed_counts"].values()) == {0}


def test_replacement_preserves_local_authority_and_nonlocal_l1() -> None:
    decision = _load(DECISION)
    contract = decision["replacement_contract"]
    identity = contract["identity_classification"]
    delivery = contract["delivery_authority"]
    assert identity["current_case_ticker_in_provider_narrative"] == (
        "allowed_as_non_authoritative_narrative_context"
    )
    assert identity[
        "registered_nonlocal_case_ticker_in_provider_narrative"
    ] == "L1_hard_failure"
    assert identity["mixed_current_and_nonlocal_case_tokens"] == (
        "L1_hard_failure"
    )
    assert identity[
        "hardcoded_DELL_MU_NVDA_tuple_as_policy_owner_forbidden"
    ]
    assert delivery["provider_may_author_title_or_delivery_identity_fields"] is False
    assert delivery["final_nine_artifact_identity_recomputation_required"]
    assert delivery["model_verifier_cannot_substitute_for_independent_L1"]
    assert decision["replacement_contract"]["historical_immutability"] == {
        "existing_v1_admissions_and_consumed_runs_reinterpreted": False,
        "R3_failure_reclassified_as_success": False,
        "new_admission_must_explicitly_bind_v2": True,
    }


def test_fixture_contract_closes_the_live_path_blind_spot() -> None:
    decision = _load(DECISION)
    acceptance = decision["replacement_bundle_acceptance"]
    assert acceptance["cases"] == ["DELL", "MU", "NVDA"]
    assert acceptance["fixture_live_parity"] == {
        "positive_fake_may_sanitize_current_case_identity_tokens": False,
        "fake_provider_must_generate_request_conformant_natural_current_case_mentions": True,
        "provider_request_policy_validator_fake_and_mutation_rubric_share_one_versioned_contract_owner": True,
    }
    assert (
        "mixed_current_and_nonlocal_case_tokens_fail_closed"
        in acceptance["negative_fixtures"]
    )
    assert (
        "numeric_projection_and_canonical_numeric_fact_mutations_remain_rejected"
        in acceptance["negative_fixtures"]
    )
    assert set(
        acceptance["actual_allowed_counts_for_the_bundle"].values()
    ) == {0}


def test_scope_replacement_has_a_hard_anti_loop_ceiling() -> None:
    decision = _load(DECISION)
    ceiling = decision["anti_loop_ceiling"]
    assert ceiling["replacement_zero_call_implementation_bundles_maximum"] == 1
    assert ceiling["replacement_bundle_requires_separate_authority"]
    assert ceiling["automatic_follow_on_repair_bundles"] == 0
    assert (
        ceiling[
            "field_by_field_prompt_regex_or_token_allowlist_patch_iterations"
        ]
        == 0
    )
    assert ceiling[
        "replacement_bundle_failure_disposition"
    ] == (
        "block_the_affected_agent_delivery_scope_keep_S4_T06_blocked_"
        "no_second_replacement_bundle"
    )
    assert ceiling["R4_exact_live_execution_maximum_after_fresh_proof_and_admission"] == 1
    assert ceiling["R4_requires_separate_authority"]
    assert ceiling["R4_first_new_L1_failure_disposition"] == (
        "stop_and_return_to_program_level_block_no_R5"
    )
    assert decision["next_action"] == (
        "S4-T06-MU-CURRENT-CASE-AWARE-DELIVERY-IDENTITY-BOUNDARY-"
        "SCOPE-REPLACEMENT-MINIMUM-ZERO-CALL-IMPLEMENTATION"
    )
    assert decision["next_action_authorized"] is False
