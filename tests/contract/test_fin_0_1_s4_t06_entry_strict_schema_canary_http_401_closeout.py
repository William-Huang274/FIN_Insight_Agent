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
    "fin_ia_0_1_s4_t06_entry_shared_runtime_blocker_"
    "single_node_strict_schema_canary_exact_once_execution_result_v1_0.json"
)
DISPOSITION = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_s4_t06_entry_shared_runtime_blocker_"
    "post_canary_program_disposition_decision_v1_0.json"
)


def test_exact_once_result_is_terminal_sanitized_and_unretriable() -> None:
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    assert result["status"] == "terminal_failed_no_retry"
    assert result["sanitized_failure_detail"] == "HTTP 401"
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


def test_program_disposition_does_not_overclaim_or_replay() -> None:
    result_sha256 = hashlib.sha256(RESULT.read_bytes()).hexdigest()
    disposition = json.loads(DISPOSITION.read_text(encoding="utf-8"))
    assert disposition["source_result"]["sha256"] == result_sha256
    classification = disposition["classification"]
    assert classification["first_credible_failure_phase"] == (
        "provider_authentication_before_generation"
    )
    assert not classification["model_inference_reached"]
    assert not classification["strict_schema_endpoint_acceptance_evaluated"]
    assert not classification["model_fault_established"]
    program = disposition["program_disposition"]
    assert not program["consumed_canary_may_be_replayed"]
    assert not program["automatic_retry_or_fresh_canary"]
    assert not program["automatic_key_creation_replacement_or_rotation"]
    assert program["S4_T06"] == "not_entered"
    assert disposition["next_action"] == (
        "S4-T06-ENTRY-OPENAI-CREDENTIAL-REQUALIFICATION-"
        "AUTHORITY-DECISION"
    )
    assert not disposition["next_action_authorized"]


def test_backlogs_expose_only_unapproved_credential_authority_decision() -> None:
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
    credential_authority = (
        "S4-T06-ENTRY-OPENAI-CREDENTIAL-REQUALIFICATION-"
        "AUTHORITY-DECISION"
    )
    metadata_probe = (
        "S4-T06-ENTRY-OPENAI-CREDENTIAL-REQUALIFICATION-"
        "EXACT-ONCE-METADATA-PROBE"
    )
    requalified_canary_authority = (
        "S4-T06-ENTRY-OPENAI-CREDENTIAL-REQUALIFIED-"
        "FRESH-STRICT-SCHEMA-CANARY-AUTHORITY-DECISION"
    )
    requalified_canary_execution = (
        "S4-T06-ENTRY-OPENAI-CREDENTIAL-REQUALIFIED-FRESH-"
        "STRICT-SCHEMA-CANARY-EXACT-ONCE-EXECUTION"
    )
    http_429_disposition = (
        "S4-T06-ENTRY-OPENAI-HTTP-429-RATE-OR-QUOTA-"
        "PROGRAM-DISPOSITION-DECISION"
    )
    sub2api_rebaseline = (
        "S4-T06-ENTRY-SUB2API-PROVIDER-ROUTE-AND-CAPABILITY-"
        "CONTRACT-REBASELINE-DECISION"
    )
    sub2api_secure_transport = (
        "S4-T06-ENTRY-SUB2API-SECURE-TRANSPORT-ENDPOINT-CONFIRMATION"
    )
    sub2api_diagnostic_authority = (
        "S4-T06-ENTRY-SUB2API-PUBLIC-NON-SENSITIVE-"
        "DIAGNOSTIC-CANARY-AUTHORITY-DECISION"
    )
    sub2api_diagnostic_implementation = (
        "S4-T06-ENTRY-SUB2API-PUBLIC-NON-SENSITIVE-DIAGNOSTIC-"
        "CANARY-MINIMUM-ZERO-CALL-IMPLEMENTATION-AND-PREFLIGHT"
    )
    sub2api_diagnostic_result = (
        "S4-T06-ENTRY-SUB2API-PUBLIC-NON-SENSITIVE-DIAGNOSTIC-"
        "CANARY-POST-RESULT-PROGRAM-DISPOSITION"
    )
    assert program["next_action"]["item_id"] in {
        credential_authority,
        metadata_probe,
        requalified_canary_authority,
        requalified_canary_execution,
        http_429_disposition,
        sub2api_rebaseline,
        sub2api_secure_transport,
        sub2api_diagnostic_authority,
        sub2api_diagnostic_implementation,
        sub2api_diagnostic_result,
        DEEPSEEK_MAINLINE,
        "S4-T06-MU-ACTION-PLANNING-TEMPORAL-AUTHORITY-AND-CAPTURE-V2-"
        "TERMINAL-RESULT-MATERIALIZATION-MINIMUM-ZERO-CALL-IMPLEMENTATION",
    }
    assert s4["current_next_action"] == program["next_action"]["item_id"]
    assert program["next_action"]["single_node_canary_consumed"]
    assert program["next_action"]["future_canary_authorized"] is (
        program["next_action"]["item_id"] == requalified_canary_execution
    )
    if program["next_action"]["item_id"] == credential_authority:
        assert not s4["T06_entry_program_scope_replace"][
            "future_credential_requalification_authority"
        ]
    else:
        assert s4["T06_entry_program_scope_replace"][
            "future_credential_requalification_authority"
        ]
        assert program["next_action"][
            "credential_requalification_probe_authorized"
        ]
