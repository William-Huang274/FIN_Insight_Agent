from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DECISION = ROOT / (
    "configs/releases/fin_ia_0_1_s3_t09_research_lead_v4_"
    "capacity_recurrence_zero_call_root_cause_decision_v1_0.json"
)
BACKLOG = ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_decision_quantifies_typed_reference_structural_amplification() -> None:
    decision = _load(DECISION)
    audit = decision["independent_structural_amplification_audit"]
    control = decision["control_comparison"]
    root_cause = decision["root_cause"]

    assert audit["identity_kind_occurrences"] == 25
    assert audit["complete_typed_ref_objects"] == 24
    assert audit["complete_typed_ref_utf8_bytes"] == 4030
    assert audit["same_complete_refs_as_three_character_alias_strings_utf8_bytes"] == 120
    assert audit["selected_four_character_alias_projected_captured_prefix_utf8_bytes"] == 3291
    assert audit["selected_alias_projection_is_a_counterfactual_not_a_complete_output_proof"]
    assert control["control_lead_output_utf8_bytes"] == 3540
    assert control["output_v4_lead_input_token_increase"] == 1398
    assert root_cause["project_owned_contract_and_capacity_mismatch_confirmed"]
    assert root_cause["provider_model_fault_confirmed"] is False


def test_decision_rejects_token_only_and_preserves_canonical_typed_identity() -> None:
    decision = _load(DECISION)
    options = {row["option"]: row["decision"] for row in decision["option_comparison"]}
    repair = decision["selected_repair_contract"]

    assert options["increase_Research_Lead_output_tokens_only"] == "reject"
    assert options[
        "request_scoped_compact_alias_wire_local_typed_expansion_local_row_ids_and_dual_capacity_proof"
    ] == "select"
    assert repair["new_research_lead_transport_ref"].endswith(":v5")
    assert repair["historical_research_lead_v1_through_v4_immutable"] is True
    assert repair["canonical_output_contract_ref_unchanged"].endswith("output:v4")
    assert repair["canonical_scoped_identity_contract_ref_unchanged"].endswith(
        "identity:v1"
    )
    wire = repair["provider_wire_identity"]
    assert wire["alias_is_authoritative_identity"] is False
    assert wire["alias_is_persisted_as_canonical_identity"] is False
    assert wire[
        "local_runtime_expands_aliases_to_CellScopedResearchRef_before_existing_output_v4_validation_and_persistence"
    ] is True
    assert wire["raw_local_id_only_output_allowed"] is False


def test_dual_capacity_and_cardinality_contract_are_closed_without_budget_increase() -> None:
    repair = _load(DECISION)["selected_repair_contract"]
    capacity = repair["dual_capacity_contract"]
    refs = repair["closed_reference_cardinality"]
    governance = repair["capability_and_profile_governance"]

    assert capacity["aggregate_provider_narrative_unicode_character_maximum"] == 3200
    assert capacity["provider_raw_wire_utf8_byte_maximum"] == 8192
    assert capacity["provider_canonical_alias_segment_utf8_byte_maximum"] == 6000
    assert capacity["lead_max_output_tokens"] == 1800
    assert capacity["aggregate_max_output_tokens"] == 16800
    assert capacity["token_or_total_cost_increase_selected"] is False
    assert capacity[
        "admission_requires_exact_minimum_maximum_and_adversarial_capacity_fixture_digests"
    ] is True
    assert refs["every_reference_list_must_be_unique"] is True
    assert refs["hardcoded_NVDA_or_Cell_specific_ref_counts"] is False
    assert governance["Lead_transport_capability_registry_required"] is True
    assert governance["if_transport_equals_v5_branching_allowed"] is False
    assert governance["Provider_specific_contract_fork_required"] is False


def test_decision_is_zero_call_and_advances_only_to_zero_call_implementation() -> None:
    decision = _load(DECISION)
    authority = decision["authority"]

    assert set(decision["observed_counts"].values()) == {0}
    assert authority[
        "zero_call_restricted_capture_code_contract_and_capacity_audit_authorized"
    ] is True
    assert authority[
        "runtime_code_prompt_schema_validator_profile_or_budget_implementation_authorized"
    ] is False
    assert authority["admission_issuance_or_consumption_authorized"] is False
    assert authority[
        "model_provider_network_source_external_tool_retry_fallback_or_rerun_authorized"
    ] is False
    assert decision["next_action"].endswith("ZERO-CALL-IMPLEMENTATION")
    assert decision["stage_decision"]["S3_T09"].startswith("blocked_")


def test_program_backlog_records_decision_and_preserves_stop_line() -> None:
    backlog = _load(BACKLOG)["next_action"]

    assert backlog["item_id"] == (
        "S3-T09-OWNER-GRADE-RESEARCH-LEAD-V5-COMPACT-SCOPED-"
        "REFERENCE-WIRE-LOCAL-TYPED-EXPANSION-AND-DUAL-CAPACITY-"
        "ZERO-CALL-IMPLEMENTATION"
    )
    assert backlog[
        "cross_cell_scoped_identity_research_lead_v4_capacity_recurrence_root_cause_decision_authorized"
    ] is True
    assert backlog[
        "research_lead_v5_compact_scoped_reference_dual_capacity_zero_call_implementation_authorized"
    ] is False
    assert backlog["replacement_admission_or_execution_authorized"] is False
    assert backlog["agent_rerun_authorized"] is False
    assert backlog["owner_review_or_T10_authorized"] is False
