from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESULT = (
    ROOT
    / "configs/releases/fin_ia_0_1_s3_t09_owner_grade_v3_segmented_fresh_live_execution_result_v1_0.json"
)
BACKLOG = ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
RUNTIME_RESULT = (
    ROOT
    / ".codex_runtime/fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1"
    / "owner_grade_v3_segmented_live_live_execution_result.json"
)


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_runtime_receipt_digest_and_terminal_truth_are_exact() -> None:
    result = _load(RESULT)
    runtime = _load(RUNTIME_RESULT)
    digest = hashlib.sha256(RUNTIME_RESULT.read_bytes()).hexdigest()
    assert digest == result["runtime_result_sha256"]
    assert digest == "32b2696eb0cf764b0e0e28f2e42f90386a57ffbaf4cc2e96e9f4834be9fc88ed"
    terminal = result["canonical_terminal_truth"]
    assert result["status"] == "terminal_failed_admission_consumed_no_retry"
    assert [
        terminal["work_unit_state"],
        terminal["attempt_state"],
        terminal["research_run_state"],
    ] == ["failed", "failed", "failed"]
    assert terminal["artifact_count"] == 0
    assert terminal["event_count"] == 7
    assert terminal["orphaned_run"] is False
    assert runtime["status"] == result["status"]


def test_one_provider_call_stopped_at_first_segment_without_retry() -> None:
    result = _load(RESULT)
    provider = result["provider_execution"]
    assert provider["failed_stage"] == (
        "domain_specialist:demand_authenticity_and_sustainability:"
        "facts_explanation_and_terminal"
    )
    assert provider["finish_reason"] == "stop"
    assert [provider["model_calls"], provider["provider_calls"], provider["network_calls"]] == [1, 1, 1]
    assert provider["transport_attempt_count"] == 1
    assert [provider["input_tokens"], provider["output_tokens"], provider["total_tokens"]] == [2582, 294, 2876]
    assert provider["estimated_cost_usd"] == 0.00137895
    assert [provider["retry_count"], provider["fallback_count"], provider["rerun_count"]] == [0, 0, 0]


def test_failure_disposition_does_not_invent_unpersisted_length_subtype() -> None:
    result = _load(RESULT)
    disposition = result["failure_disposition"]
    assert "native_JSON_object_parse_passed" in disposition["proven"]
    assert (
        "at_least_one_explanation_item_failed_nonblank_string_and_maximum_320_unicode_character_contract"
        in disposition["proven"]
    )
    assert "whether_the_item_was_non_string_blank_or_over_320_unicode_characters" in (
        disposition["not_reconstructable_from_safe_persisted_evidence"]
    )
    assert disposition["provider_HTTP_failure"] is False
    assert disposition["provider_JSON_syntax_failure"] is False
    assert result["boundary_observation"]["raw_provider_response_persisted"] is False


def test_canonical_and_authority_boundaries_are_closed() -> None:
    result = _load(RESULT)
    boundary = result["boundary_observation"]
    assert boundary["canonical_counts_after"] == [5, 5, 5, 13]
    assert boundary["canonical_database_sha256_after"] == (
        "57b78491eba2ece91db4f9d2268b87d742be86a10574dd75eb46a88bd6093751"
    )
    assert boundary["canonical_object_tree_sha256_after"] == (
        "00ac740b53c91c032b221453cf9269c5748a7fbcf5802bbc239a8e34ae21ea75"
    )
    assert boundary["object_tree_unchanged"] is True
    assert boundary["consumed_identity_reuse_preflight_rejected"] is True
    assert boundary["reuse_guard_gateway_event_lines_before_after"] == [18, 18]
    assert [
        boundary["source_network_calls"],
        boundary["external_tool_calls"],
        boundary["live_business_case_head_writes"],
    ] == [0, 0, 0]


def test_historical_live_result_stays_frozen_as_current_program_advances() -> None:
    result = _load(RESULT)
    next_action = _load(BACKLOG)["next_action"]
    historical_expected = (
        "S3-T09-OWNER-GRADE-V3-SEGMENTED-FIRST-SEGMENT-TEXT-LENGTH-"
        "FAILURE-RESULT-AND-ROOT-CAUSE-DECISION"
    )
    current_expected = (
        "S3-T09-OWNER-GRADE-V3-SEGMENTED-TRANSPORT-V5-RESEARCH-LEAD-OUTPUT-TRUNCATION-RESULT-AND-ROOT-CAUSE-DECISION"
    )
    assert result["next_action"] == historical_expected
    assert next_action["item_id"] == current_expected
    assert next_action["fresh_segmented_exact_admission_consumed"] is True
    assert next_action["fresh_segmented_exact_live_execution_authorized"] is True
    assert next_action["fresh_segmented_exact_live_execution_status"] == (
        "terminal_failed_first_segment_explanation_layer_text_length_contract"
    )
    assert next_action["text_contract_zero_call_repair_implementation_authorized"] is True
    assert next_action["text_contract_v2_fresh_agent_proof_decision_authorized"] is True
    assert next_action["agent_rerun_authorized"] is False
    assert next_action["owner_review_or_T10_authorized"] is False
    assert next_action["replacement_admission_or_execution_authorized"] is False


def test_result_contract_contains_no_plaintext_credential() -> None:
    rendered = RESULT.read_text(encoding="utf-8").lower()
    assert "sk-" not in rendered
    assert "fixture-secret" not in rendered
