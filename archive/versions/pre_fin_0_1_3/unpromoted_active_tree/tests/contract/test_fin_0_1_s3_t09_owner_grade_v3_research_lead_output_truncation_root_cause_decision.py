from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DECISION = (
    ROOT
    / "configs/releases/fin_ia_0_1_s3_t09_owner_grade_v3_"
    "research_lead_output_truncation_root_cause_decision_v1_0.json"
)
BACKLOG = ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_restricted_capture_audit_distinguishes_length_cutoff_from_json_conformance() -> None:
    decision = _read(DECISION)
    evidence = decision["source_evidence"]
    audit = decision["restricted_capture_structural_audit"]
    root_cause = decision["root_cause"]

    assert evidence["lead_output_tokens"] == evidence["lead_output_token_cap"] == 1200
    assert evidence["finish_reason"] == "length"
    assert evidence["restricted_assistant_output_characters"] == 4278
    assert audit["starts_with_json_object"] is True
    assert audit["ends_with_json_object"] is False
    assert audit["json_error"]["subtype"] == "unterminated_string_after_length_cutoff"
    assert audit["all_required_top_level_keys_started"] == [
        "cell_heads",
        "cross_cell_dependencies",
        "conflict_adjudications",
        "variant_view",
        "remaining_gaps",
    ]
    assert audit["unexpected_schema_member_names_observed"] == []
    assert root_cause["deepseek_json_conformance_is_primary_root_cause"] is False
    assert root_cause["lead_input_volume_is_primary_root_cause"] is False
    assert evidence["raw_assistant_output_copied_into_tracked_artifacts"] is False
    assert "assistant_output_text" not in DECISION.read_text(encoding="utf-8")


def test_selected_repair_closes_output_without_lossy_input_or_cap_only_patch() -> None:
    decision = _read(DECISION)
    repair = decision["selected_repair_contract"]

    assert repair["specialist_transport_ref_unchanged"].endswith(":v5")
    assert repair["canonical_output_contract_ref_unchanged"].endswith(":v3")
    assert repair["cell_heads"]["provider_must_emit"] is False
    assert repair["cell_heads"][
        "local_runtime_derives_exactly_three_from_validated_specialist_outputs_and_digests"
    ] is True
    assert repair["analysis_input"]["retain_full_validated_specialist_semantic_bodies"] is True
    assert repair["provider_visible_cardinality"] == {
        "cross_cell_dependencies_min_max": [1, 3],
        "conflict_adjudications_min_max": [0, 3],
        "remaining_gaps_min_max": [1, 4],
        "variant_view_exactly_one_object": True,
    }
    assert repair["provider_visible_text_and_size"][
        "maximum_unicode_characters_per_narrative_field"
    ] == 320
    assert repair["provider_visible_text_and_size"][
        "maximum_provider_segment_serialized_utf8_bytes"
    ] == 6000
    assert repair["provider_visible_text_and_size"][
        "maximum_locally_assembled_lead_utf8_bytes"
    ] == 8192
    assert repair["token_and_cost_limits"] == {
        "lead_max_output_tokens": 1800,
        "prior_lead_max_output_tokens": 1200,
        "aggregate_max_output_tokens": 16800,
        "prior_aggregate_max_output_tokens": 16200,
        "maximum_incremental_output_only_cost_usd": 0.000522,
        "max_total_cost_usd": 0.1,
        "max_total_cost_change_allowed": False,
        "retry_fallback_and_rerun_budget": 0,
    }


def test_decision_is_zero_call_and_only_authorizes_future_implementation() -> None:
    decision = _read(DECISION)
    counts = decision["observed_counts"]

    assert set(counts.values()) == {0}
    assert decision["authority"]["code_prompt_budget_or_admission_change_authorized"] is False
    assert decision["stage_decision"]["S3_T09"].startswith("blocked_")
    assert decision["next_action"].endswith("ZERO-CALL-IMPLEMENTATION")


def test_program_backlog_preserves_decision_and_advances_after_implementation() -> None:
    next_action = _read(BACKLOG)["next_action"]

    assert next_action["item_id"] == (
        "S3-T09-OWNER-GRADE-V3-RESEARCH-LEAD-V3-CONFLICT-LOCAL-"
        "DIRECT-SUPPORT-ZERO-CALL-IMPLEMENTATION"
    )
    assert next_action["research_lead_truncation_root_cause_decision_authorized"] is True
    assert next_action["research_lead_truncation_root_cause_decision_status"].startswith(
        "pass_project_owned_open_lead_output_contract"
    )
    assert next_action["research_lead_zero_call_implementation_authorized"] is True
    assert next_action["research_lead_zero_call_implementation_status"].startswith(
        "pass_closed_four_member_output"
    )
    assert next_action[
        "research_lead_v2_conflict_fact_presence_scope_root_cause_decision_authorized"
    ] is True
    assert next_action[
        "research_lead_v3_conflict_local_direct_support_implementation_authorized"
    ] is False
    assert next_action["replacement_admission_or_execution_authorized"] is False
