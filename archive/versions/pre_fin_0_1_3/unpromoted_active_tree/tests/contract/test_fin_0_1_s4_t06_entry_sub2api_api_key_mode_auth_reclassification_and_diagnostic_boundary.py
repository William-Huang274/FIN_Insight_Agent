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
    "fin_ia_0_1_s4_t06_entry_sub2api_api_key_mode_auth_"
    "reclassification_and_diagnostic_boundary_v1_0.json"
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


def test_api_key_mode_disables_openai_bearer_without_persisting_header_value() -> None:
    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    observed = decision["observed_API_Key_Mode_contract"]
    auth = decision["auth_reclassification"]

    assert observed["base_url"] == "http://43.135.174.27:8080"
    assert observed["wire_api"] == "responses"
    assert observed["model_alias"] == "gpt-5.5"
    assert not observed["requires_openai_auth"]
    assert observed["custom_actor_authorization_header_present"]
    assert not observed["custom_header_value_persisted"]
    assert not auth["official_OPENAI_API_KEY_should_be_sent"]
    assert not auth["Sub2API_API_key_should_be_sent_as_OpenAI_Bearer"]
    assert not auth["OpenAI_Authorization_header_enabled_by_snippet"]
    assert not auth["credential_exposure_over_HTTP_established"]


def test_plain_http_is_diagnostic_only_and_never_mainline_acceptance() -> None:
    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    boundary = decision["remaining_plain_HTTP_boundary"]
    diagnostic = decision["diagnostic_candidate"]

    assert not boundary["prompt_and_response_confidentiality_established"]
    assert not boundary["server_identity_authenticated_by_TLS"]
    assert not boundary["response_integrity_protected_by_TLS"]
    assert boundary[
        "public_or_synthetic_payload_diagnostic_admissible_after_separate_authority"
    ]
    assert not boundary["private_financial_data_or_credentials_admissible"]
    assert not boundary["mainline_T06_acceptance_evidence_admissible"]
    assert diagnostic["maximum_provider_requests"] == 1
    assert diagnostic["retry_budget"] == 0
    assert diagnostic["credential_reads_or_writes"] == 0
    assert diagnostic["business_Run_or_Artifact_writes"] == 0
    assert diagnostic["result_classification"] == (
        "diagnostic_only_never_T06_acceptance"
    )


def test_backlogs_and_latest_issues_advance_after_diagnostic_authority() -> None:
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
        assert state["Sub2API_API_Key_Mode_auth_reclassification_sha256"] == (
            decision_sha256
        )
        assert state["Sub2API_API_Key_Mode_auth_reclassification_completed"]
        assert not state["Sub2API_requires_openai_auth"]
        assert not state["Sub2API_OpenAI_Bearer_enabled"]
        assert state["Sub2API_static_client_marker_observed"]
        assert not state["Sub2API_static_client_marker_value_persisted"]
        assert state["Sub2API_public_nonsensitive_diagnostic_admissible"]
        assert state["Sub2API_public_nonsensitive_diagnostic_authorized"]
        assert state["Sub2API_public_nonsensitive_diagnostic_started"]
        assert state["Sub2API_public_nonsensitive_diagnostic_completed"]
        assert state["Sub2API_public_nonsensitive_diagnostic_consumed"]
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


def test_decision_is_zero_call_and_contains_no_secret_material() -> None:
    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    accounting = decision["zero_call_execution_accounting"]
    text = DECISION.read_text(encoding="utf-8")

    assert accounting["model_calls"] == 0
    assert accounting["provider_calls"] == 0
    assert accounting["network_calls"] == 0
    assert accounting["credential_reads"] == 0
    assert accounting["credential_writes"] == 0
    assert not accounting["diagnostic_canary_authorized"]
    assert not accounting["diagnostic_canary_started"]
    assert decision["next_action"] == (
        "S4-T06-ENTRY-SUB2API-PUBLIC-NON-SENSITIVE-"
        "DIAGNOSTIC-CANARY-AUTHORITY-DECISION"
    )
    assert not decision["next_action_authorized"]
    assert "sk-" not in text
    assert "Bearer sk-" not in text
