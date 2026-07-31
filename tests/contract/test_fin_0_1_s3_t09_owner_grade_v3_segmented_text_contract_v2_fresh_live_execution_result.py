from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_s3_t09_owner_grade_v3_segmented_"
    "text_contract_v2_fresh_live_execution_result_v1_0.json"
)
BACKLOG = ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
RUNTIME_RESULT = ROOT / (
    ".codex_runtime/fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1/"
    "owner_grade_v3_segmented_text_contract_v2_r1_live_execution_result.json"
)


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_runtime_digest_and_terminal_truth_are_exact() -> None:
    result = _load(RESULT)
    runtime = _load(RUNTIME_RESULT)
    digest = hashlib.sha256(RUNTIME_RESULT.read_bytes()).hexdigest()
    assert digest == result["runtime_result_sha256"]
    assert digest == "d78858ff42f53e7556fe65ea293dc33bc22af9d4b8da72a281fdafd7079c1370"
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


def test_five_calls_stop_at_second_specialist_authority_gate() -> None:
    provider = _load(RESULT)["provider_execution"]
    assert provider["failed_stage"] == (
        "domain_specialist:value_and_profit_capture:owner_grade_claim_cards"
    )
    assert provider["finish_reasons"] == ["stop"] * 5
    assert [provider["model_calls"], provider["provider_calls"], provider["network_calls"]] == [5, 5, 5]
    assert provider["transport_attempt_count"] == 5
    assert [provider["input_tokens"], provider["output_tokens"], provider["total_tokens"]] == [17682, 2519, 20201]
    assert provider["estimated_cost_usd"] == 0.00883411
    assert [provider["retry_count"], provider["fallback_count"], provider["rerun_count"]] == [0, 0, 0]


def test_failure_disposition_is_bounded_by_safe_persisted_evidence() -> None:
    result = _load(RESULT)
    disposition = result["failure_disposition"]
    assert "at_least_one_claim_context_ref_was_not_a_member_of_the_frozen_candidate_or_graph_context_authority_surface" in disposition["proven"]
    assert "the_offending_context_ref_value" in disposition["not_reconstructable_from_safe_persisted_evidence"]
    assert disposition["provider_HTTP_failure"] is False
    assert disposition["provider_JSON_syntax_failure"] is False
    assert disposition["segment_top_level_shape_or_cell_binding_failure"] is False
    assert disposition["claim_card_shape_failure"] is False
    assert disposition["context_authority_membership_failure"] is True
    assert disposition["root_cause_or_repair_decision_performed"] is False


def test_canonical_and_authority_boundaries_are_closed() -> None:
    boundary = _load(RESULT)["boundary_observation"]
    assert boundary["canonical_counts_after"] == [6, 6, 6, 13]
    assert boundary["canonical_database_sha256_after"] == (
        "b19539cf749a03035eb9c70bc2613eab63e15fcb53b1f56c3087bb0319baceba"
    )
    assert boundary["canonical_object_tree_sha256_after"] == (
        "00ac740b53c91c032b221453cf9269c5748a7fbcf5802bbc239a8e34ae21ea75"
    )
    assert boundary["object_tree_unchanged"] is True
    assert boundary["consumed_identity_reuse_preflight_rejected"] is True
    assert boundary["reuse_guard_gateway_event_lines_before_after"] == [28, 28]
    assert boundary["post_terminal_inspect_additional_model_provider_network_calls"] == [0, 0, 0]


def test_result_points_to_zero_call_root_cause_decision_without_rerun() -> None:
    result = _load(RESULT)
    next_action = _load(BACKLOG)["next_action"]
    expected = (
        "S3-T09-OWNER-GRADE-V3-SEGMENTED-TRANSPORT-V2-CONTEXT-AUTHORITY-"
        "FAILURE-RESULT-AND-ROOT-CAUSE-DECISION"
    )
    assert result["next_action"] == expected
    assert next_action["item_id"] == (
        "S3-T09-OWNER-GRADE-V3-SEGMENTED-TRANSPORT-V5-RESEARCH-LEAD-OUTPUT-TRUNCATION-RESULT-AND-ROOT-CAUSE-DECISION"
    )
    assert next_action[
        "text_contract_v2_context_authority_failure_root_cause_decision_authorized"
    ] is True
    assert next_action["text_contract_v2_fresh_exact_admission_consumed"] is True
    assert next_action["text_contract_v2_fresh_exact_live_execution_authorized"] is True
    assert next_action["text_contract_v2_fresh_artifact_count"] == 0
    assert next_action["agent_rerun_authorized"] is False
    assert next_action["replacement_admission_or_execution_authorized"] is False
    assert next_action["owner_review_or_T10_authorized"] is False


def test_result_contract_contains_no_plaintext_credential() -> None:
    rendered = RESULT.read_text(encoding="utf-8").lower()
    assert "sk-" not in rendered
    assert "fixture-secret" not in rendered
