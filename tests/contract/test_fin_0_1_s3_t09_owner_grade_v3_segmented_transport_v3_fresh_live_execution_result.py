from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_s3_t09_owner_grade_v3_segmented_"
    "transport_v3_fresh_live_execution_result_v1_0.json"
)
BACKLOG = ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
RUNTIME_RESULT = ROOT / (
    ".codex_runtime/fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1/"
    "transport_v3_r1_live_execution_result.json"
)


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_runtime_digest_and_terminal_truth_are_exact() -> None:
    result = _load(RESULT)
    runtime = _load(RUNTIME_RESULT)
    digest = hashlib.sha256(RUNTIME_RESULT.read_bytes()).hexdigest()
    assert digest == result["runtime_result_sha256"]
    assert digest == "934152c91f2e85c30051946a661c3f6fd8657c9c7cab2b0165214d63cc38cbe5"
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


def test_five_calls_stop_at_second_specialist_epistemic_gate() -> None:
    result = _load(RESULT)
    provider = result["provider_execution"]
    terminal = result["canonical_terminal_truth"]
    assert provider["failed_stage"] == (
        "domain_specialist:value_and_profit_capture:owner_grade_claim_cards"
    )
    assert provider["finish_reasons"] == ["stop"] * 5
    assert [
        provider["model_calls"],
        provider["provider_calls"],
        provider["network_calls"],
    ] == [5, 5, 5]
    assert [
        provider["input_tokens"],
        provider["output_tokens"],
        provider["total_tokens"],
    ] == [18167, 1863, 20030]
    assert provider["estimated_cost_usd"] == 0.00941302
    assert [
        provider["retry_count"],
        provider["fallback_count"],
        provider["rerun_count"],
    ] == [0, 0, 0]
    assert terminal["failure_code"].endswith(
        "s3_owner_grade_epistemic_status_statement_conflict"
    )


def test_failure_is_not_misclassified_as_repeated_context_authority_subtype() -> None:
    disposition = _load(RESULT)["failure_disposition"]
    assert disposition["provider_HTTP_failure"] is False
    assert disposition["provider_JSON_syntax_failure"] is False
    assert disposition["context_authority_membership_failure"] is False
    assert disposition["epistemic_status_statement_conflict"] is True
    assert disposition["same_context_authority_subtype_as_transport_v2"] is False
    assert disposition["root_cause_or_provider_route_decision_performed"] is False
    assert "the_provider_response_body" in disposition[
        "not_reconstructable_from_safe_persisted_evidence"
    ]


def test_canonical_and_execution_boundaries_are_closed() -> None:
    boundary = _load(RESULT)["boundary_observation"]
    assert boundary["canonical_counts_after"] == [7, 7, 7, 13]
    assert boundary["canonical_database_sha256_after"] == (
        "7eba5df705d2b8ff66bd6ef3d1c92cf346a72dc0a02d0631dcf4875c47de307a"
    )
    assert boundary["canonical_object_tree_sha256_after"] == (
        "00ac740b53c91c032b221453cf9269c5748a7fbcf5802bbc239a8e34ae21ea75"
    )
    assert boundary["object_tree_unchanged"] is True
    assert boundary["gateway_event_lines_before_and_after_execution"] == [28, 38]
    assert boundary["post_terminal_inspect_additional_model_provider_network_calls"] == [
        0,
        0,
        0,
    ]


def test_result_points_to_zero_call_root_cause_decision_without_rerun() -> None:
    result = _load(RESULT)
    next_action = _load(BACKLOG)["next_action"]
    historical_expected = (
        "S3-T09-OWNER-GRADE-V3-SEGMENTED-TRANSPORT-V3-EPISTEMIC-STATUS-"
        "STATEMENT-CONFLICT-RESULT-AND-ROOT-CAUSE-DECISION"
    )
    current_expected = (
        "S3-T09-OWNER-GRADE-V3-SEGMENTED-TRANSPORT-V5-RESEARCH-LEAD-OUTPUT-TRUNCATION-RESULT-AND-ROOT-CAUSE-DECISION"
    )
    assert result["next_action"] == historical_expected
    assert next_action["item_id"] == current_expected
    assert next_action["transport_v3_fresh_exact_admission_consumed"] is True
    assert next_action["transport_v3_fresh_live_execution_authorized"] is True
    assert next_action["transport_v3_fresh_artifact_count"] == 0
    assert next_action["agent_rerun_authorized"] is False
    assert next_action["replacement_admission_or_execution_authorized"] is False
    assert next_action["owner_review_or_T10_authorized"] is False


def test_result_contract_contains_no_plaintext_credential() -> None:
    rendered = RESULT.read_text(encoding="utf-8").lower()
    assert "sk-" not in rendered
    assert "fixture-secret" not in rendered
