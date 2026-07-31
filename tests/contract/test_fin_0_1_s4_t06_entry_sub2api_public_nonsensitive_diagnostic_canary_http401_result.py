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
    "fin_ia_0_1_s4_t06_entry_sub2api_public_nonsensitive_"
    "diagnostic_canary_exact_once_execution_result_v1_0.json"
)
EXPECTED_SHA256 = (
    "aaba2e0396c264d5a071cc3532572ff87d9b2ea4a8415284574f38012e82d301"
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


def test_result_is_exact_once_http401_before_generation() -> None:
    assert hashlib.sha256(RESULT.read_bytes()).hexdigest() == EXPECTED_SHA256
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    assert result["status"] == "terminal_failed_no_retry"
    assert result["failure_class"] == "model_or_endpoint_access_rejected"
    assert result["http_status"] == 401
    assert result["transport_status"] == "http_error"
    assert result["response_status"] == ""
    assert result["usage"] == {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
    }
    assert result["transport_attempt_count"] == 1
    assert result["observed_counts"]["semantic_model_calls"] == 1
    assert result["observed_counts"]["provider_calls"] == 1
    assert result["observed_counts"]["network_calls"] == 1
    assert result["retry_count"] == 0
    assert result["provider_hopping_count"] == 0
    assert result["automatic_repair_count"] == 0
    assert not result["strict_schema_parse_pass"]
    assert not result["local_exact_value_validation_pass"]


def test_result_is_sanitized_diagnostic_only() -> None:
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    text = RESULT.read_text(encoding="utf-8")
    assert result["result_is_diagnostic_only"]
    assert not result["result_closes_RC_P36_074"]
    assert not result["result_admits_T06_or_full_chain"]
    assert not result["raw_provider_response_persisted"]
    assert not result["provider_output_text_persisted"]
    assert not result["request_or_response_headers_persisted"]
    assert not result["static_client_marker_value_persisted"]
    assert not result["private_reasoning_persisted"]
    assert not result["credential_persisted"]
    assert not result["stack_trace_persisted"]
    assert "local-image-extension" not in text
    assert "Authorization" not in text


def test_backlogs_and_latest_issues_stop_at_post_result_disposition() -> None:
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
    assert program["next_action"]["item_id"] in {
        CURRENT,
        DEEPSEEK_MAINLINE,
        "S4-T06-MU-ACTION-PLANNING-TEMPORAL-AUTHORITY-AND-CAPTURE-V2-"
        "TERMINAL-RESULT-MATERIALIZATION-MINIMUM-ZERO-CALL-IMPLEMENTATION",
    }
    assert s4["current_next_action"] == program["next_action"]["item_id"]
    for state in (program["next_action"], s4["T06_entry_program_scope_replace"]):
        assert state["Sub2API_public_nonsensitive_diagnostic_completed"]
        assert state["Sub2API_public_nonsensitive_diagnostic_consumed"]
        assert state["Sub2API_public_nonsensitive_diagnostic_http_status"] == 401
        assert state["Sub2API_public_nonsensitive_diagnostic_result_sha256"] == (
            EXPECTED_SHA256
        )
        assert not state[
            "Sub2API_public_nonsensitive_diagnostic_exact_execution_authorized"
        ]
        assert not state["Sub2API_mainline_T06_acceptance_transport_admissible"]

    expected_scope = [
        "S4_T06_entry_Sub2API_public_non_sensitive_diagnostic_canary_"
        "post_result_program_disposition",
        "repository_and_git_hygiene",
    ]
    if program["next_action"]["item_id"] == DEEPSEEK_MAINLINE:
        expected_scope = [
            "S4_T06_MU_DeepSeek_fresh_exact_admission_preparation_and_"
            "zero_call_proof",
            "repository_and_git_hygiene",
        ]
    for issue_id in (
        "RC-P36-070-s4-t06-strict-schema-unsupported-uniqueItems",
        "RC-P36-073-s4-t06-provider-route-authority-mismatch-sub2api-unbound",
        "RC-P36-074-s4-t06-sub2api-plain-http-authenticated-"
        "transport-security-boundary",
        "RC-P36-075-s4-t06-sub2api-public-diagnostic-http401-"
        "client-access-contract-unproven",
    ):
        issue = _latest_issue(issue_id)
        if program["next_action"]["item_id"].startswith(
            "S4-T06-MU-ACTION-PLANNING-TEMPORAL-AUTHORITY"
        ):
            assert issue["allowed_run_scopes"] == [
                "S4_T06_MU_DeepSeek_fresh_exact_admission_preparation_and_"
                "zero_call_proof",
                "repository_and_git_hygiene",
            ]
        else:
            assert issue["allowed_run_scopes"] == expected_scope
