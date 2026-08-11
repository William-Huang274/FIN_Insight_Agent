from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEEPSEEK_MAINLINE = (
    "S4-T06-MU-RUNTIME-AUDIT-EVIDENCE-V2-AND-MATERIAL-NUMERIC-"
    "CLASSIFIER-R5-EXACT-LIVE-EXECUTION-AND-SUCCESS-ONLY-PAIRED-ASSESSMENT"
)
DECISION = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_s4_t06_entry_sub2api_public_nonsensitive_"
    "diagnostic_canary_authority_decision_v1_0.json"
)
RESULT = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_s4_t06_entry_sub2api_public_nonsensitive_"
    "diagnostic_canary_exact_once_execution_result_v1_0.json"
)
NEXT = (
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


def test_authority_binds_exact_no_credential_plain_http_route() -> None:
    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    authority = decision["authority"]
    provider = decision["provider_contract"]

    assert authority["future_exact_once_diagnostic_execution_authorized"]
    assert authority["minimum_zero_call_runner_implementation_and_preflight_authorized"]
    assert not authority["current_turn_model_provider_or_network_execution_authorized"]
    assert not authority["credential_read_write_or_presence_probe_authorized"]
    assert provider["base_url"] == "http://43.135.174.27:8080"
    assert provider["endpoint_path"] == "/responses"
    assert provider["full_request_url"] == "http://43.135.174.27:8080/responses"
    assert not provider["base_url_includes_v1_path"]
    assert provider["wire_api"] == "responses"
    assert provider["model"] == "gpt-5.5"
    assert not provider["requires_openai_auth"]
    assert not provider["OpenAI_Authorization_or_Bearer_header_enabled"]
    assert provider["credential_environment_variable"] is None
    marker = provider["static_client_marker"]
    assert marker["header_name"] == "x-openai-actor-authorization"
    assert marker["header_value"] == "local-image-extension"
    assert not marker["raw_header_logging_or_result_persistence"]


def test_request_is_fully_synthetic_strict_and_tiny() -> None:
    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    canary = decision["exact_diagnostic_canary"]
    request = decision["exact_request_contract"]
    schema = request["text_format"]["schema"]
    budget = decision["hard_budget"]

    assert canary["input_class"] == (
        "fully_synthetic_public_non_sensitive_no_company_no_financial_data"
    )
    assert not canary["input_contains_real_company_or_financial_data"]
    assert not canary["input_contains_credentials_or_private_data"]
    assert request["text_format"]["type"] == "json_schema"
    assert request["text_format"]["strict"]
    assert schema["type"] == "object"
    assert not schema["additionalProperties"]
    assert schema["required"] == ["selected_alias", "judgment", "note_code"]
    assert request["expected_exact_values"] == {
        "selected_alias": "N001",
        "judgment": "confirmed",
        "note_code": "synthetic_ok",
    }
    assert budget["maximum_semantic_model_calls"] == 1
    assert budget["maximum_provider_calls"] == 1
    assert budget["maximum_network_calls"] == 1
    assert budget["maximum_transport_attempts"] == 1
    assert budget["maximum_output_tokens"] == 128
    assert budget["retry_budget"] == 0
    assert budget["credential_reads"] == 0
    assert budget["credential_writes"] == 0
    assert budget["canonical_work_unit_attempt_run_writes"] == 0
    assert budget["business_artifact_writes"] == 0


def test_authority_was_zero_call_before_the_later_consumed_result() -> None:
    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    counts = decision["current_turn_observed_counts"]

    assert RESULT.exists()
    assert counts["actual_model_calls"] == 0
    assert counts["actual_provider_calls"] == 0
    assert counts["execution_network_calls"] == 0
    assert counts["credential_reads"] == 0
    assert counts["credential_writes"] == 0
    assert counts["diagnostic_executions"] == 0
    assert counts["runner_or_runtime_changes"] == 0
    assert decision["next_action"] == (
        "S4-T06-ENTRY-SUB2API-PUBLIC-NON-SENSITIVE-DIAGNOSTIC-"
        "CANARY-MINIMUM-ZERO-CALL-IMPLEMENTATION-AND-PREFLIGHT"
    )
    assert decision["next_action_authorized"]


def test_result_is_diagnostic_only_and_persistence_is_sanitized() -> None:
    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    success = decision["success_contract"]
    failure = decision["failure_contract"]
    persistence = decision["result_persistence_contract"]

    assert success["result_is_diagnostic_only"]
    assert not success["result_closes_RC_P36_074"]
    assert not success["result_admits_T06_or_full_chain"]
    assert failure["first_credible_failure"] == "terminal_stop"
    assert failure["retry"] == 0
    assert not failure["provider_hopping"]
    assert not failure["automatic_repair"]
    assert "raw_provider_response" in persistence["forbidden"]
    assert "request_or_response_headers" in persistence["forbidden"]
    assert "static_client_marker_value" in persistence["forbidden"]


def test_backlogs_and_latest_issues_point_to_zero_call_implementation() -> None:
    decision_sha256 = hashlib.sha256(DECISION.read_bytes()).hexdigest()
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
        NEXT,
        DEEPSEEK_MAINLINE,
        "S4-T06-MU-ACTION-PLANNING-TEMPORAL-AUTHORITY-AND-CAPTURE-V2-"
        "TERMINAL-RESULT-MATERIALIZATION-MINIMUM-ZERO-CALL-IMPLEMENTATION",
    }
    assert s4["current_next_action"] == program["next_action"]["item_id"]
    for state in (program["next_action"], s4["T06_entry_program_scope_replace"]):
        assert state["Sub2API_public_nonsensitive_diagnostic_authority_ref"] == (
            str(DECISION.relative_to(ROOT)).replace("\\", "/")
        )
        assert state["Sub2API_public_nonsensitive_diagnostic_authority_sha256"] == (
            decision_sha256
        )
        assert state["Sub2API_public_nonsensitive_diagnostic_authorized"]
        assert state["Sub2API_public_nonsensitive_diagnostic_started"]
        assert state["Sub2API_public_nonsensitive_diagnostic_completed"]
        assert state["Sub2API_public_nonsensitive_diagnostic_consumed"]
        assert state["Sub2API_public_nonsensitive_diagnostic_request_ceiling"] == 1
        assert not state["Sub2API_mainline_T06_acceptance_transport_admissible"]

    expected_scope = [
        "S4_T06_entry_Sub2API_public_non_sensitive_diagnostic_canary_"
        "post_result_program_disposition",
        "repository_and_git_hygiene",
    ]
    if program["next_action"]["item_id"] in {
        DEEPSEEK_MAINLINE,
        "S4-T06-MU-ACTION-PLANNING-TEMPORAL-AUTHORITY-AND-CAPTURE-V2-"
        "TERMINAL-RESULT-MATERIALIZATION-MINIMUM-ZERO-CALL-IMPLEMENTATION",
    }:
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
    ):
        issue = _latest_issue(issue_id)
        assert issue["full_chain_blocker"] is False
        assert issue["allowed_run_scopes"] == expected_scope
