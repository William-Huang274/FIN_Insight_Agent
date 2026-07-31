from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_s3_t09_research_lead_v5_profile_v3_"
    "final_exact_live_execution_result_v1_0.json"
)


def _result() -> dict:
    return json.loads(RESULT.read_text(encoding="utf-8"))


def test_final_exact_live_is_terminal_replayable_and_not_retried() -> None:
    result = _result()

    assert result["canonical_terminal_truth"]["work_unit_state"] == "failed"
    assert result["canonical_terminal_truth"]["attempt_state"] == "failed"
    assert result["canonical_terminal_truth"]["research_run_state"] == "failed"
    assert result["canonical_terminal_truth"]["orphaned_run"] is False
    assert result["canonical_terminal_truth"]["artifact_count"] == 0
    assert result["provider_execution"]["model_provider_network_calls"] == [5, 5, 5]
    assert result["provider_execution"]["retry_fallback_rerun_counts"] == [0, 0, 0]
    assert result["provider_execution"][
        "provider_output_capture_and_restricted_readback_counts"
    ] == [5, 5]


def test_failure_is_fact_link_identity_layer_not_profile_v3_length() -> None:
    result = _result()
    failure = result["failure"]
    root_cause = result["independent_root_cause_assessment"]

    assert failure["claim_support_fact_id_item_count"] == 6
    assert failure["items_matching_validated_local_fact_ids"] == 0
    assert failure["items_matching_underlying_numeric_support_refs"] == 6
    assert failure["validator_correctly_failed_closed"] is True
    assert root_cause["provider_model_semantic_mapping_failure_confirmed"] is True
    assert root_cause["same_as_research_lead_narrative_quality_failure"] is False
    assert root_cause["profile_v3_live_reached"] is False


def test_hard_failure_stops_before_comparison_T10_or_manifest() -> None:
    result = _result()
    stage = result["stage_decision"]

    assert stage["S3_T09"].startswith("blocked_")
    assert stage["S3_T10"] == "not_entered"
    assert stage["paired_comparison"].startswith("not_performed_")
    assert stage["cross_slice_manifest"].startswith("not_due_")
    assert result["authority"]["automatic_retry_fallback_patch_or_second_live_executed"] is False
    assert result["next_action"] == "S3-T09-FINAL-HARD-FAILURE-DISPOSITION-DECISION"
