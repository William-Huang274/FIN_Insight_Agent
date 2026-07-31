from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DECISION_PATH = (
    ROOT
    / "configs"
    / "releases"
    / (
        "fin_ia_0_1_s4_t06_mu_changed_contract_family_single_node_"
        "natural_output_canaries_post_result_disposition_decision_v1_0.json"
    )
)


def _decision() -> dict:
    return json.loads(DECISION_PATH.read_text(encoding="utf-8"))


def test_disposition_locates_hidden_conditional_semantic_rule() -> None:
    decision = _decision()
    reproduction = decision["zero_call_reproduction"]
    audit = decision["cross_layer_contract_audit"]
    root = decision["root_cause_disposition"]

    assert reproduction["selected_alias_membership"] == (
        "exact_current_request_alias"
    )
    assert reproduction["unknown_alias_count"] == 0
    assert reproduction["cross_case_alias_count"] == 0
    assert reproduction["mixed_scope_field_count"] == 0
    assert reproduction["cross_alias_scope_conflict_count"] == 0
    assert reproduction["provider_claim_kind"] == "insufficient_evidence"
    assert reproduction["provider_support_alias_count"] == 1
    assert reproduction["first_rejecting_rule"] == (
        "insufficient_evidence_requires_exactly_empty_support_fact_aliases"
    )
    assert audit["selector_contains_conditional_claim_kind_support_rule"] is True
    assert (
        audit[
            "model_visible_contract_contains_conditional_claim_kind_support_rule"
        ]
        is False
    )
    assert (
        audit["wire_schema_contains_conditional_claim_kind_support_rule"]
        is False
    )
    assert root["model_or_provider_fault_established"] is False
    assert root["RC_P36_083"] == (
        "reopened_live_semantic_parity_recurrence"
    )


def test_both_current_canonical_epistemic_routes_are_zero_call_viable() -> None:
    decision = _decision()
    variants = {
        row["variant_id"]: row
        for row in decision["zero_call_counterfactuals"]
    }

    bounded = variants["boundary_backed_evidence_direction"]
    assert bounded["downstream_strict_validation"] == "pass"
    assert bounded["canonical_epistemic_status"] == "bounded_inference"
    assert bounded["canonical_support_fact_id_count"] == 1
    assert bounded["canonical_cannot_support_count"] == 1

    cannot_infer = variants["supportless_insufficient_evidence"]
    assert cannot_infer["downstream_strict_validation"] == "pass"
    assert cannot_infer["canonical_epistemic_status"] == "cannot_infer"
    assert cannot_infer["canonical_support_fact_id_count"] == 0
    assert cannot_infer["canonical_cannot_support_count"] == 1


def test_selected_v2_repair_is_bounded_and_does_not_expand_live_budget() -> None:
    decision = _decision()
    selected = decision["selected_bounded_repair"]
    proof = decision["required_zero_call_proof"]
    stage = decision["stage_disposition"]

    assert selected["contract_ref"].endswith(":v2")
    assert selected["maximum_zero_call_implementation_bundles"] == 1
    assert selected["automatic_follow_on_implementation_bundles"] == 0
    assert selected["canonical_claim_schema_change_allowed"] is False
    assert selected["silent_claim_kind_rewrite_allowed"] is False
    assert selected["silent_support_alias_drop_allowed"] is False
    assert selected["validator_weakening_allowed"] is False
    assert proof["new_single_node_canary_after_implementation"] is False
    assert proof["maximum_remaining_formal_MU_exact_lives"] == 1
    assert stage["WWC_family"] == "not_called_and_not_makeup_run_eligible"
    assert stage["R7"] == "not_created_not_authorized"
    assert decision["observed_counts_this_disposition"]["model_calls"] == 0
    assert decision["next_action_authorized"] is False


def test_public_disposition_does_not_copy_restricted_raw_content() -> None:
    decision = _decision()
    serialized = json.dumps(decision, ensure_ascii=False)

    assert (
        decision["source_evidence"][
            "claim_restricted_raw_content_copied_to_public_decision"
        ]
        is False
    )
    assert "strategic customer agreements" not in serialized
    assert "cannot be attributed to HBM" not in serialized
    assert "assistant_output_text" not in serialized
    assert "model_visible_request" not in serialized
