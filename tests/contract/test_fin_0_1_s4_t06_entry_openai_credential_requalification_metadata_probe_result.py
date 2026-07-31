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
    "fin_ia_0_1_s4_t06_entry_openai_credential_requalification_"
    "exact_once_metadata_probe_result_v1_0.json"
)
AUTHORITY = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_s4_t06_entry_openai_credential_"
    "requalification_authority_decision_v1_0.json"
)
NEXT = (
    "S4-T06-ENTRY-OPENAI-CREDENTIAL-REQUALIFIED-"
    "FRESH-STRICT-SCHEMA-CANARY-AUTHORITY-DECISION"
)
PROGRESSED = (
    "S4-T06-ENTRY-OPENAI-CREDENTIAL-REQUALIFIED-FRESH-"
    "STRICT-SCHEMA-CANARY-EXACT-ONCE-EXECUTION"
)
HTTP_429_DISPOSITION = (
    "S4-T06-ENTRY-OPENAI-HTTP-429-RATE-OR-QUOTA-"
    "PROGRAM-DISPOSITION-DECISION"
)
SUB2API_REBASELINE = (
    "S4-T06-ENTRY-SUB2API-PROVIDER-ROUTE-AND-CAPABILITY-"
    "CONTRACT-REBASELINE-DECISION"
)
SUB2API_SECURE_TRANSPORT = (
    "S4-T06-ENTRY-SUB2API-SECURE-TRANSPORT-ENDPOINT-CONFIRMATION"
)
SUB2API_DIAGNOSTIC_AUTHORITY = (
    "S4-T06-ENTRY-SUB2API-PUBLIC-NON-SENSITIVE-"
    "DIAGNOSTIC-CANARY-AUTHORITY-DECISION"
)
SUB2API_DIAGNOSTIC_IMPLEMENTATION = (
    "S4-T06-ENTRY-SUB2API-PUBLIC-NON-SENSITIVE-DIAGNOSTIC-"
    "CANARY-MINIMUM-ZERO-CALL-IMPLEMENTATION-AND-PREFLIGHT"
)
SUB2API_DIAGNOSTIC_RESULT = (
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


def test_probe_succeeded_exactly_once_without_inference_or_secret_persistence() -> None:
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    sanitized = result["sanitized_result"]
    counts = result["observed_counts"]
    persistence = result["persistence_boundary"]

    assert result["authority_decision_sha256"] == hashlib.sha256(
        AUTHORITY.read_bytes()
    ).hexdigest()
    assert result["status"] == "terminal_succeeded_exact_once_no_retry"
    assert sanitized["http_status"] == 200
    assert sanitized["failure_class"] is None
    assert sanitized["response_json_object"]
    assert sanitized["exact_model_id_match"]
    assert sanitized["credential_authentication_accepted"]
    assert sanitized["model_visibility_established"]
    assert counts["network_calls"] == 1
    assert counts["transport_attempts"] == 1
    assert counts["retry_count"] == 0
    assert counts["model_inference_calls"] == 0
    assert counts["semantic_model_calls"] == 0
    assert counts["responses_calls"] == 0
    assert counts["chat_completions_calls"] == 0
    assert counts["total_tokens"] == 0
    assert counts["cost_usd"] == 0.0
    assert not any(persistence.values())
    assert "sk-" not in RESULT.read_text(encoding="utf-8")


def test_probe_proof_boundary_does_not_inflate_to_schema_or_t06() -> None:
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    proof = result["proof_boundary"]
    stage = result["stage_disposition"]

    assert proof["credential_authentication_proven"]
    assert proof["exact_model_visibility_proven"]
    assert not proof["responses_endpoint_acceptance_proven"]
    assert not proof["strict_schema_acceptance_proven"]
    assert not proof["strict_parse_proven"]
    assert not proof["local_semantic_validator_proven_live"]
    assert not proof["research_quality_proven"]
    assert not proof["T06_entry_proven"]
    assert stage["RC_P36_071"].endswith("_closed")
    assert stage["S4_T05"] == "blocked_not_passed_not_owner_accepted"
    assert stage["DELL_R2"] == "not_proven"
    assert stage["S4_T06"] == "not_entered"
    assert stage["S5"] == "blocked"
    assert result["next_action"] == NEXT
    assert not result["next_action_authorized"]


def test_backlogs_and_ledgers_expose_only_fresh_canary_authority_decision() -> None:
    result_sha256 = hashlib.sha256(RESULT.read_bytes()).hexdigest()
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
    rc_071 = _latest_issue(
        "RC-P36-071-s4-t06-openai-credential-authentication-rejected"
    )
    rc_070 = _latest_issue(
        "RC-P36-070-s4-t06-strict-schema-unsupported-uniqueItems"
    )

    assert program["next_action"]["item_id"] in {
        NEXT,
        PROGRESSED,
        HTTP_429_DISPOSITION,
        SUB2API_REBASELINE,
        SUB2API_SECURE_TRANSPORT,
        SUB2API_DIAGNOSTIC_AUTHORITY,
        SUB2API_DIAGNOSTIC_IMPLEMENTATION,
        SUB2API_DIAGNOSTIC_RESULT,
        DEEPSEEK_MAINLINE,
        "S4-T06-MU-ACTION-PLANNING-TEMPORAL-AUTHORITY-AND-CAPTURE-V2-"
        "TERMINAL-RESULT-MATERIALIZATION-MINIMUM-ZERO-CALL-IMPLEMENTATION",
    }
    assert s4["current_next_action"] == program["next_action"]["item_id"]
    for state in (
        program["next_action"],
        s4["T06_entry_program_scope_replace"],
    ):
        assert state["credential_authentication_accepted"]
        assert state["exact_model_visibility_established"]
        assert state["credential_requalification_probe_completed"]
        assert state["credential_requalification_probe_consumed"]
        assert (
            state["credential_requalification_probe_result_sha256"]
            == result_sha256
        )
        assert state["fresh_strict_schema_canary_authority_decision_admissible"]
        assert state["future_canary_authorized"] is (
            program["next_action"]["item_id"] == PROGRESSED
        )
    assert rc_071["status"].startswith("closed_")
    assert not rc_071["full_chain_blocker"]
    if program["next_action"]["item_id"] == NEXT:
        assert rc_070["allowed_run_scopes"] == [
            "S4_T06_entry_openai_credential_requalified_fresh_strict_"
            "schema_canary_authority_decision",
            "repository_and_git_hygiene",
        ]
    elif program["next_action"]["item_id"] == PROGRESSED:
        assert rc_070["allowed_run_scopes"] == [
            "S4_T06_entry_openai_credential_requalified_fresh_strict_"
            "schema_canary_exact_once_execution",
            "repository_and_git_hygiene",
        ]
    elif program["next_action"]["item_id"] == HTTP_429_DISPOSITION:
        assert rc_070["allowed_run_scopes"] == [
            "S4_T06_entry_openai_HTTP_429_rate_or_quota_program_"
            "disposition_decision",
            "repository_and_git_hygiene",
        ]
    elif program["next_action"]["item_id"] == SUB2API_REBASELINE:
        assert rc_070["allowed_run_scopes"] == [
            "S4_T06_entry_Sub2API_provider_route_and_capability_contract_"
            "rebaseline_decision",
            "repository_and_git_hygiene",
        ]
    elif program["next_action"]["item_id"] == SUB2API_SECURE_TRANSPORT:
        assert rc_070["allowed_run_scopes"] == [
            "S4_T06_entry_Sub2API_secure_transport_endpoint_confirmation",
            "repository_and_git_hygiene",
        ]
    elif (
        program["next_action"]["item_id"]
        == SUB2API_DIAGNOSTIC_AUTHORITY
    ):
        assert rc_070["allowed_run_scopes"] == [
            "S4_T06_entry_Sub2API_public_non_sensitive_diagnostic_canary_"
            "authority_decision",
            "repository_and_git_hygiene",
        ]
    elif (
        program["next_action"]["item_id"]
        == SUB2API_DIAGNOSTIC_IMPLEMENTATION
    ):
        assert rc_070["allowed_run_scopes"] == [
            "S4_T06_entry_Sub2API_public_non_sensitive_diagnostic_canary_"
            "minimum_zero_call_implementation_and_preflight",
            "repository_and_git_hygiene",
        ]
    elif program["next_action"]["item_id"] == SUB2API_DIAGNOSTIC_RESULT:
        assert rc_070["allowed_run_scopes"] == [
            "S4_T06_entry_Sub2API_public_non_sensitive_diagnostic_canary_"
            "post_result_program_disposition",
            "repository_and_git_hygiene",
        ]
    else:
        assert program["next_action"]["item_id"] in {
            DEEPSEEK_MAINLINE,
            "S4-T06-MU-ACTION-PLANNING-TEMPORAL-AUTHORITY-AND-CAPTURE-V2-"
            "TERMINAL-RESULT-MATERIALIZATION-MINIMUM-ZERO-CALL-IMPLEMENTATION",
        }
        assert rc_070["allowed_run_scopes"] == [
            "S4_T06_MU_DeepSeek_fresh_exact_admission_preparation_and_"
            "zero_call_proof",
            "repository_and_git_hygiene",
        ]
