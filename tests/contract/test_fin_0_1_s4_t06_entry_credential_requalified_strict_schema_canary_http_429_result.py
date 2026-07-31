from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEEPSEEK_MAINLINE = (
    "S4-T06-MU-RUNTIME-AUDIT-EVIDENCE-V2-AND-MATERIAL-NUMERIC-"
    "CLASSIFIER-R5-EXACT-LIVE-EXECUTION-AND-SUCCESS-ONLY-PAIRED-ASSESSMENT"
)
RESULT = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_s4_t06_entry_openai_credential_requalified_"
    "fresh_strict_schema_canary_exact_once_execution_result_v1_0.json"
)
DISPOSITION = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_s4_t06_entry_openai_credential_requalified_"
    "strict_schema_canary_http_429_program_disposition_v1_0.json"
)
NEXT = (
    "S4-T06-ENTRY-OPENAI-HTTP-429-RATE-OR-QUOTA-"
    "PROGRAM-DISPOSITION-DECISION"
)
CURRENT = (
    "S4-T06-ENTRY-SUB2API-PUBLIC-NON-SENSITIVE-DIAGNOSTIC-"
    "CANARY-POST-RESULT-PROGRAM-DISPOSITION"
)


def _latest_issue(issue_id: str) -> dict:
    rows = [
        json.loads(line)
        for line in (
            ROOT / "docs/project_os/root_cause_issue_ledger.jsonl"
        ).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return [row for row in rows if row["issue_id"] == issue_id][-1]


def test_fresh_canary_is_terminal_exact_once_sanitized_and_zero_token() -> None:
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    assert result["status"] == "terminal_failed_no_retry"
    assert result["sanitized_failure_detail"] == "HTTP 429"
    assert result["provider_status"] == "provider_error"
    assert result["response_status"] == ""
    assert result["observed_counts"] == {
        "business_artifact_writes": 0,
        "canonical_work_unit_attempt_run_writes": 0,
        "chat_completions_calls": 0,
        "external_tool_calls": 0,
        "network_calls": 1,
        "provider_calls": 1,
        "semantic_model_calls": 1,
        "source_network_calls": 0,
        "transport_attempts": 1,
    }
    assert result["usage"]["total_tokens"] == 0
    assert result["usage"]["estimated_cost_usd"] == 0.0
    assert not result["strict_schema_parse_pass"]
    assert not result["local_semantic_validation_and_rendering_pass"]
    for field in (
        "raw_provider_response_persisted",
        "provider_output_text_persisted",
        "private_reasoning_persisted",
        "credential_persisted",
        "headers_persisted",
        "stack_trace_persisted",
    ):
        assert result[field] is False
    text = RESULT.read_text(encoding="utf-8")
    assert "sk-" not in text
    assert "Authorization" not in text
    assert '"response_output":' not in text


def test_disposition_classifies_429_without_schema_or_model_overclaim() -> None:
    disposition = json.loads(DISPOSITION.read_text(encoding="utf-8"))
    assert disposition["source_result"]["sha256"] == hashlib.sha256(
        RESULT.read_bytes()
    ).hexdigest()
    classification = disposition["classification"]
    assert classification["first_credible_failure_phase"] == (
        "provider_rate_or_quota_rejection_before_generation"
    )
    assert classification["credential_authentication_and_model_visibility_previously_proven"]
    assert classification["openai_api_response_reached"]
    assert not classification["model_inference_reached"]
    assert not classification["strict_schema_endpoint_acceptance_evaluated"]
    assert not classification["strict_schema_request_rejected"]
    assert not classification["model_fault_established"]
    assert classification["http_429_subtype"] == (
        "unknown_due_to_sanitized_result"
    )
    assert not classification[
        "ordinary_rate_limit_vs_insufficient_quota_or_spend_limit_distinguishable"
    ]
    program = disposition["program_disposition"]
    assert program["fresh_canary_consumed"]
    assert not program["fresh_canary_may_be_replayed"]
    assert not program["automatic_retry_or_third_canary"]
    assert not program["automatic_credit_or_limit_change"]
    assert program["S4_T06"] == "not_entered"
    assert disposition["next_action"] == NEXT
    assert not disposition["next_action_authorized"]


def test_backlogs_and_rc_ledger_expose_only_unapproved_zero_call_disposition() -> None:
    result_sha256 = hashlib.sha256(RESULT.read_bytes()).hexdigest()
    disposition_sha256 = hashlib.sha256(DISPOSITION.read_bytes()).hexdigest()
    program = json.loads(
        (
            ROOT
            / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
        ).read_text(encoding="utf-8")
    )
    s4 = json.loads(
        (
            ROOT
            / "configs/releases/fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
        ).read_text(encoding="utf-8")
    )
    rc_070 = _latest_issue(
        "RC-P36-070-s4-t06-strict-schema-unsupported-uniqueItems"
    )
    rc_072 = _latest_issue(
        "RC-P36-072-s4-t06-openai-http-429-rate-or-quota-subtype-unknown"
    )

    assert program["next_action"]["item_id"] in {
        CURRENT,
        DEEPSEEK_MAINLINE,
        "S4-T06-MU-ACTION-PLANNING-TEMPORAL-AUTHORITY-AND-CAPTURE-V2-"
        "TERMINAL-RESULT-MATERIALIZATION-MINIMUM-ZERO-CALL-IMPLEMENTATION",
    }
    assert s4["current_next_action"] == program["next_action"]["item_id"]
    for state in (
        program["next_action"],
        s4["T06_entry_program_scope_replace"],
    ):
        assert state["fresh_strict_schema_canary_execution_started"]
        assert state["fresh_strict_schema_canary_execution_completed"]
        assert state["fresh_strict_schema_canary_consumed"]
        assert state["fresh_strict_schema_canary_result_sha256"] == (
            result_sha256
        )
        assert state["HTTP_429_program_disposition_sha256"] == (
            disposition_sha256
        )
        assert not state["future_canary_authorized"]
        assert not state["HTTP_429_program_disposition_authorized"]
        expected_scope = (
            "S4_T06_MU_DeepSeek_fresh_exact_admission_preparation_and_"
            "zero_call_proof"
            if program["next_action"]["item_id"] in {
                DEEPSEEK_MAINLINE,
                "S4-T06-MU-ACTION-PLANNING-TEMPORAL-AUTHORITY-AND-CAPTURE-"
                "V2-TERMINAL-RESULT-MATERIALIZATION-MINIMUM-ZERO-CALL-"
                "IMPLEMENTATION",
            }
            else "S4_T06_entry_Sub2API_public_non_sensitive_diagnostic_"
            "canary_post_result_program_disposition"
        )
        assert rc_070["allowed_run_scopes"] == [
            expected_scope,
            "repository_and_git_hygiene",
        ]
    assert not rc_072["full_chain_blocker"]
    assert not rc_072["owned_by_project"]
    assert rc_072["allowed_run_scopes"] == ["repository_and_git_hygiene"]
