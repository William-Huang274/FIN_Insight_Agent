from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RELEASES = ROOT / "configs" / "releases"
DECISION = RELEASES / (
    "fin_ia_0_1_s3_t09_owner_grade_v3_research_lead_v2_"
    "conflict_fact_presence_scope_root_cause_decision_v1_0.json"
)
BACKLOG = RELEASES / "fin_ia_0_1_program_release_backlog_v2_0.json"


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_decision_selects_conflict_local_direct_claim_support_truth_table() -> None:
    decision = _load(DECISION)
    selected = decision["selected_semantics"]

    assert decision["status"].startswith(
        "pass_conflict_local_direct_claim_support_scope_selected"
    )
    assert selected["scope_owner"] == (
        "each_conflict_adjudication_involved_claim_ids"
    )
    assert selected["fact_presence_source"] == (
        "each_involved_claim_direct_support_fact_ids"
    )
    assert selected["unrelated_global_cell_or_claim_facts_affect_summary"] is False
    assert selected["unrelated_facts_in_the_same_cell_affect_summary"] is False
    assert selected["truth_table"] == [
        {
            "condition": (
                "every_involved_claim_has_at_least_one_direct_support_fact_id"
            ),
            "expected_summary": "facts_present",
        },
        {
            "condition": "no_involved_claim_has_any_direct_support_fact_id",
            "expected_summary": "no_facts_present",
        },
        {
            "condition": (
                "some_but_not_all_involved_claims_have_direct_support_fact_ids"
            ),
            "expected_summary": "mixed_fact_presence",
        },
    ]


def test_decision_does_not_relax_the_captured_live_answer_to_success() -> None:
    replay = _load(DECISION)["restricted_live_replay"]

    assert replay["observed_conflict_fact_presence_summaries"] == [
        "no_facts_present",
        "mixed_fact_presence",
        "no_facts_present",
    ]
    assert replay["selected_scope_expected_summaries"] == [
        "no_facts_present",
        "no_facts_present",
        "no_facts_present",
    ]
    assert replay["selected_scope_mismatch_flags"] == [False, True, False]
    assert replay["selected_scope_mismatch_count"] == 1
    assert replay["current_answer_would_pass_after_simple_relaxation"] is False
    assert replay["raw_answer_text_copied_to_tracked_files"] is False


def test_versioning_preserves_history_and_selects_research_lead_v3() -> None:
    versioning = _load(DECISION)["version_and_compatibility_decision"]

    assert versioning["selected_future_research_lead_transport_ref"] == (
        "fin01.s3.bounded_agent.research_lead_owner_grade:v3"
    )
    assert versioning["historical_research_lead_v2_transport_immutable"] is True
    assert versioning["specialist_transport_v5_unchanged"] is True
    assert versioning["canonical_output_contract_v3_retained"] is True
    assert versioning["consumed_admissions_and_terminal_runs_immutable"] is True
    assert versioning["provider_or_model_change_selected"] is False
    assert versioning["token_or_byte_cap_change_selected"] is False


def test_future_implementation_is_shared_fail_closed_and_content_free() -> None:
    decision = _load(DECISION)
    implementation = decision["future_zero_call_implementation_contract"]
    telemetry = decision["safe_telemetry_contract"]

    assert implementation["normalization_coercion_or_silent_repair_allowed"] is False
    assert implementation["historical_v2_branch_mutation_allowed"] is False
    assert "reuse_the_same_direct_support_helper" in implementation[
        "canonical_validator"
    ]
    assert telemetry["failure_family"] == "semantic"
    assert telemetry["allowed_subtypes"] == [
        "involved_claim_ref_duplicate",
        "fact_presence_summary_invalid",
        "fact_presence_summary_mismatch",
        "explicit_global_fact_presence_statement_conflict",
    ]
    assert telemetry["raw_text_persisted"] is False
    assert telemetry["claim_or_fact_ids_persisted"] is False
    assert telemetry["ref_or_digest_persisted"] is False
    assert telemetry["item_index_persisted"] is False
    assert telemetry["private_reasoning_persisted"] is False
    assert len(decision["required_deterministic_fixtures"]) == 16


def test_decision_is_zero_call_and_advances_only_to_separate_implementation() -> None:
    decision = _load(DECISION)
    authority = decision["authority"]

    assert authority["zero_call_root_cause_decision_authorized"] is True
    assert authority[
        "runtime_validator_prompt_or_transport_implementation_authorized"
    ] is False
    assert authority["admission_issuance_or_consumption_authorized"] is False
    assert authority[
        "model_provider_network_source_or_tool_execution_authorized"
    ] is False
    assert set(decision["observed_counts"].values()) == {0}
    assert decision["next_action"] == (
        "S3-T09-OWNER-GRADE-V3-RESEARCH-LEAD-V3-CONFLICT-LOCAL-"
        "DIRECT-SUPPORT-ZERO-CALL-IMPLEMENTATION"
    )


def test_program_backlog_preserves_repair_and_points_to_fresh_proof_decision() -> None:
    next_action = _load(BACKLOG)["next_action"]

    assert next_action["item_id"] == (
        "S3-T09-OWNER-GRADE-V3-RESEARCH-LEAD-V3-FRESH-EXACT-LIVE-EXECUTION"
    )
    assert next_action[
        "research_lead_v2_conflict_fact_presence_scope_root_cause_decision_authorized"
    ] is True
    assert next_action[
        "research_lead_v2_conflict_fact_presence_scope_root_cause_decision_status"
    ].startswith("pass_conflict_local_direct_claim_support")
    assert next_action["selected_future_research_lead_transport_ref"] == (
        "fin01.s3.bounded_agent.research_lead_owner_grade:v3"
    )
    assert next_action[
        "research_lead_v3_conflict_local_direct_support_implementation_authorized"
    ] is True
    assert next_action[
        "research_lead_v3_fresh_agent_proof_decision_authorized"
    ] is True
    assert next_action[
        "research_lead_v3_fresh_exact_admission_issuance_authorized"
    ] is True
    assert next_action["research_lead_v3_fresh_exact_admission_issued"] is True
    assert next_action["research_lead_v3_fresh_exact_admission_consumed"] is False
    assert next_action["agent_execution_authorized"] is False
    assert next_action["agent_rerun_authorized"] is False


def test_decision_does_not_persist_answer_body_or_credentials() -> None:
    rendered = DECISION.read_text(encoding="utf-8")

    assert '"assistant_output_text":' not in rendered
    assert "DEEPSEEK_API_KEY" not in rendered
    assert "sk-" not in rendered.lower()
