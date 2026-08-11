from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESULT = (
    ROOT
    / "configs/releases/fin_ia_0_1_s3_t09_owner_grade_v3_fresh_live_execution_result_v1_0.json"
)
BACKLOG = ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_fresh_v3_execution_records_exact_terminal_failure_without_retry() -> None:
    result = _load(RESULT)
    terminal = result["canonical_terminal_truth"]
    provider = result["provider_execution"]
    assert result["status"] == "terminal_failed_admission_consumed_no_retry"
    assert [
        terminal["work_unit_state"],
        terminal["attempt_state"],
        terminal["research_run_state"],
    ] == ["failed", "failed", "failed"]
    assert terminal["artifact_count"] == 0
    assert terminal["orphaned_run"] is False
    assert [provider["model_calls"], provider["provider_calls"], provider["network_calls"]] == [1, 1, 1]
    assert [provider["retry_count"], provider["fallback_count"], provider["rerun_count"]] == [0, 0, 0]
    boundary = result["boundary_observation"]
    assert boundary["consumed_identity_reuse_preflight_rejected"] is True
    assert boundary["reuse_guard_gateway_event_lines_before_after"] == [16, 16]


def test_failure_disposition_is_precise_and_does_not_invent_raw_subtype() -> None:
    result = _load(RESULT)
    disposition = result["failure_disposition"]
    assert "native_JSON_object_parse_passed" in disposition["proven"]
    assert "unexpected_top_level_keys" in disposition["not_reconstructable_from_safe_persisted_evidence"]
    assert disposition["owner_grade_semantic_repair_live_proven"] is False
    assert result["boundary_observation"]["raw_provider_response_persisted"] is False


def test_program_stops_at_zero_call_root_cause_and_transport_decision() -> None:
    result = _load(RESULT)
    backlog = _load(BACKLOG)
    next_action = backlog["next_action"]
    assert result["next_action"] == (
        "S3-T09-OWNER-GRADE-V3-FIRST-SPECIALIST-SCHEMA-FAILURE-ROOT-CAUSE-AND-TRANSPORT-DECISION"
    )
    assert next_action["item_id"] == (
        "S3-T09-OWNER-GRADE-V3-SEGMENTED-TRANSPORT-V5-RESEARCH-LEAD-OUTPUT-TRUNCATION-RESULT-AND-ROOT-CAUSE-DECISION"
    )
    assert next_action["zero_call_root_cause_and_transport_decision_authorized"] is True
    assert next_action["segmented_specialist_transport_implementation_authorized"] is True
    assert next_action["fresh_segmented_exact_admission_decision_authorized"] is True
    assert next_action["fresh_segmented_exact_admission_issuance_authorized"] is True
    assert next_action["fresh_segmented_exact_admission_issued"] is True
    assert next_action["fresh_segmented_exact_admission_consumed"] is True
    assert next_action["fresh_v3_exact_admission_consumed"] is True
    assert next_action["fresh_v3_exact_live_execution_status"] == (
        "terminal_failed_first_specialist_output_schema_invalid"
    )
    assert next_action["agent_rerun_authorized"] is False
    assert next_action["owner_review_or_T10_authorized"] is False
