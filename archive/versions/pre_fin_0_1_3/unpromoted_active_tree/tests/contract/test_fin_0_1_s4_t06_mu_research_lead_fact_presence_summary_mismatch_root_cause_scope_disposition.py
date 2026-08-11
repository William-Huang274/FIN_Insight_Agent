from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RELEASES = ROOT / "configs" / "releases"
DECISION = RELEASES / (
    "fin_ia_0_1_s4_t06_mu_research_lead_fact_presence_summary_"
    "mismatch_root_cause_scope_disposition_v1_0.json"
)
FAILURE = RELEASES / (
    "fin_ia_0_1_s4_t06_mu_fresh_exact_live_execution_"
    "failure_result_v1_0.json"
)
DETAIL = RELEASES / "fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
PROGRAM = RELEASES / "fin_ia_0_1_program_release_backlog_v2_0.json"
IMPLEMENTATION = RELEASES / (
    "fin_ia_0_1_s4_t06_mu_research_lead_fact_presence_local_"
    "materialization_minimum_zero_call_implementation_v1_0.json"
)


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_decision_confirms_dual_ownership_as_earliest_owned_fault() -> None:
    decision = _load(DECISION)
    fault = decision["confirmed_earliest_owned_fault"]
    failure = _load(FAILURE)

    assert decision["status"].startswith(
        "pass_project_owned_dual_ownership_confirmed"
    )
    assert failure["first_credible_failure"]["failure_code"] == (
        "s3_bounded_research_lead_v3_semantic_"
        "fact_presence_summary_mismatch"
    )
    assert fault["research_lead_v5_provider_schema_requires_fact_presence_summary"]
    assert fault["existing_local_helper_deterministically_derives_expected_summary"]
    assert fault["research_lead_v5_local_validator_recomputes_and_hard_compares_summary"]
    assert fault["canonical_output_validator_recomputes_and_hard_compares_summary"]
    assert fault["same_material_fact_has_provider_and_local_owners"]
    assert fault["failure_is_external_provider_only"] is False


def test_selected_contract_removes_only_the_deterministic_provider_field() -> None:
    selected = _load(DECISION)["selected_contract"]

    assert selected["policy_ref"] == (
        "fin01.s3.research_lead."
        "conflict_fact_presence_local_materialization:v1"
    )
    assert selected["selected_future_research_lead_transport_ref"] == (
        "fin01.s3.bounded_agent.research_lead_owner_grade:v7"
    )
    assert selected["provider_owned_fields"] == [
        "conflict_adjudications.involved_claim_ids",
        "conflict_adjudications.terminal_state_summary",
        "conflict_adjudications.resolution_status",
        "conflict_adjudications.statement",
    ]
    assert selected["locally_owned_field"] == (
        "conflict_adjudications.fact_presence_summary"
    )
    assert selected["provider_wire_requires_fact_presence_summary"] is False
    assert selected["provider_wire_allows_fact_presence_summary"] is False
    assert selected["canonical_output_requires_fact_presence_summary"] is True
    assert selected["provider_summary_normalization_overwrite_or_repair_allowed"] is False


def test_truth_table_is_exact_all_none_some() -> None:
    assert _load(DECISION)["selected_contract"]["truth_table"] == [
        {
            "condition": (
                "every_involved_claim_has_at_least_one_direct_support_fact_id"
            ),
            "canonical_value": "facts_present",
        },
        {
            "condition": "no_involved_claim_has_any_direct_support_fact_id",
            "canonical_value": "no_facts_present",
        },
        {
            "condition": (
                "some_but_not_all_involved_claims_have_direct_support_fact_ids"
            ),
            "canonical_value": "mixed_fact_presence",
        },
    ]


def test_disposition_rejects_prompt_patch_silent_repair_and_quality_downgrade() -> None:
    options = {
        row["option"]: row["decision"]
        for row in _load(DECISION)["disposition_options"]
    }

    assert options["prompt_emphasis_or_larger_token_budget"] == "reject"
    assert options["remove_ignore_or_quality_downgrade_the_summary"] == "reject"
    assert options["silent_repair_of_a_provider_emitted_summary"] == "reject"
    assert options[
        "local_deterministic_materialization_with_provider_field_removed"
    ] == "select"


def test_scope_is_one_zero_call_bundle_without_gap_atom_or_paid_expansion() -> None:
    decision = _load(DECISION)
    boundary = decision["version_and_scope_boundary"]
    implementation = decision["future_minimum_zero_call_implementation_contract"]

    assert boundary["MU_R1_consumed_admission_and_terminal_Run_immutable"]
    assert boundary["historical_research_lead_v1_through_v6_immutable"]
    assert boundary["research_lead_v6_gap_atom_projection_adopted_into_this_repair"] is False
    assert boundary["financial_evidence_graph_or_method_scope_changed"] is False
    assert boundary["strict_schema_transport_reactivated"] is False
    assert boundary["T05_reopened"] is False
    assert implementation["maximum_implementation_bundles"] == 1
    assert implementation["automatic_follow_on_repair_bundles"] == 0
    assert implementation["new_admission_or_paid_execution_after_implementation"].startswith(
        "not_automatic"
    )


def test_decision_is_zero_call_and_advances_only_to_implementation() -> None:
    decision = _load(DECISION)
    authority = decision["authority"]

    assert authority["zero_call_root_cause_or_scope_disposition_authorized"]
    assert authority["runtime_prompt_validator_or_transport_implementation_authorized"] is False
    assert authority["new_admission_issuance_or_consumption_authorized"] is False
    assert authority["model_provider_network_source_or_tool_execution_authorized"] is False
    assert authority["MU_R2_exact_live_or_paired_assessment_authorized"] is False
    assert set(decision["observed_counts"].values()) == {0}
    assert decision["next_action"] == (
        "S4-T06-MU-RESEARCH-LEAD-CONFLICT-FACT-PRESENCE-LOCAL-"
        "DETERMINISTIC-MATERIALIZATION-MINIMUM-ZERO-CALL-IMPLEMENTATION"
    )


def test_backlogs_advance_through_fresh_proof_to_admission_decision_only() -> None:
    detail = _load(DETAIL)
    program = _load(PROGRAM)
    implementation = _load(IMPLEMENTATION)
    t06 = next(row for row in detail["tasks"] if row["item_id"] == "S4-T06")
    next_action = program["next_action"]

    expected = (
        "S4-T06-RUNTIME-AUDIT-EVIDENCE-V2-AND-MATERIAL-NUMERIC-"
        "CLASSIFIER-MINIMUM-ZERO-CALL-IMPLEMENTATION"
    )
    current = (
        "S4-T06-MU-ACTION-PLANNING-TEMPORAL-AUTHORITY-AND-CAPTURE-V2-"
        "TERMINAL-RESULT-MATERIALIZATION-MINIMUM-ZERO-CALL-IMPLEMENTATION"
    )
    assert t06["required_in_scope_substep"] in {expected, current}
    assert t06["RC_P36_078_status"] == (
        "closed_exact_live_Lead_v7_local_materialization_proven"
    )
    assert next_action["action"].startswith(
        (
            "implement exactly one zero-call runtime bundle",
            "perform one independent zero-call fresh-agent proof decision",
            "perform a separate zero-call authority decision",
            "write only the exact frozen MU R5 admission payload",
            "perform one zero-call R5 execution authority decision",
            "consume the issued R5 admission exactly once",
            "if separately authorized implement one zero-call shared",
        )
    )
    assert next_action["required_in_scope_substep"] in {expected, current}
    assert next_action["MU_R2_authorized"] is True
    assert next_action[
        "fact_presence_materialization_fresh_R2_admission_issued"
    ] is True
    assert next_action[
        "fact_presence_materialization_fresh_R2_admission_consumed"
    ] is True
    assert implementation["authority"]["implementation_bundles_consumed"] == 1
    assert implementation["authority"][
        "automatic_follow_on_repair_bundles"
    ] == 0


def test_decision_persists_no_answer_body_or_credentials() -> None:
    rendered = DECISION.read_text(encoding="utf-8")

    assert '"assistant_output_text":' not in rendered
    assert "DEEPSEEK_API_KEY" not in rendered
    assert "sk-" not in rendered.lower()
