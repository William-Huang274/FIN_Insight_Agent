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
    "fin_ia_0_1_s4_t06_entry_sub2api_provider_route_and_"
    "capability_contract_rebaseline_decision_v1_0.json"
)
NEXT = "S4-T06-ENTRY-SUB2API-SECURE-TRANSPORT-ENDPOINT-CONFIRMATION"
PROGRESSED = (
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


def test_user_supplied_route_is_bound_without_inventing_v1_or_model_alias() -> None:
    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    observed = decision["observed_connection_contract"]
    route = decision["derived_project_route_contract"]

    assert observed["base_url"] == "http://43.135.174.27:8080"
    assert not observed["base_url_includes_v1_path"]
    assert observed["wire_api"] == "responses"
    assert observed["requires_openai_auth"]
    assert observed["advertised_model_alias"] == "gpt-5.5"
    assert route["endpoint_path"] == "/responses"
    assert route["candidate_request_url"] == (
        "http://43.135.174.27:8080/responses"
    )
    assert not route["append_v1_to_base_url"]
    assert route["candidate_model_alias"] == "gpt-5.5"
    assert not route["prior_official_model_alias_gpt_5_6_sol_applies"]


def test_plain_http_authenticated_public_route_is_not_request_admissible() -> None:
    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    gate = decision["transport_security_gate"]
    accounting = decision["zero_call_execution_accounting"]

    assert gate["scheme"] == "http"
    assert not gate["remote_host_is_loopback"]
    assert gate["authentication_required"]
    assert not gate["credential_confidentiality_in_transit_established"]
    assert not gate["credentialed_request_admissible"]
    assert not gate["plain_http_public_ip_override_authorized"]
    assert accounting["model_calls"] == 0
    assert accounting["provider_calls"] == 0
    assert accounting["network_calls"] == 0
    assert accounting["credential_reads"] == 0
    assert accounting["credential_writes"] == 0
    assert not accounting["probe_or_canary_issued"]


def test_capabilities_remain_advertised_or_unknown_not_live_proven() -> None:
    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    capability = decision["capability_classification"]
    route = decision["derived_project_route_contract"]

    assert capability["responses_wire_advertised_by_operator_configuration"]
    assert capability["responses_endpoint_live_reachable"] == "not_evaluated"
    assert capability["authentication_accepted"] == "not_evaluated"
    assert capability["gpt_5_5_alias_resolves_to_upstream_model"] == (
        "not_evaluated"
    )
    assert capability["strict_json_schema_supported"] == (
        "not_advertised_not_evaluated"
    )
    assert route["project_credential_env_name"] == "SUB2API_API_KEY"
    assert not route["reuse_official_OPENAI_API_KEY_for_Sub2API"]


def test_backlogs_and_latest_issues_stop_at_secure_endpoint_confirmation() -> None:
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
        PROGRESSED,
        DEEPSEEK_MAINLINE,
        "S4-T06-MU-ACTION-PLANNING-TEMPORAL-AUTHORITY-AND-CAPTURE-V2-"
        "TERMINAL-RESULT-MATERIALIZATION-MINIMUM-ZERO-CALL-IMPLEMENTATION",
    }
    assert s4["current_next_action"] == program["next_action"]["item_id"]
    for state in (program["next_action"], s4["T06_entry_program_scope_replace"]):
        assert state["Sub2API_route_rebaseline_decision_sha256"] == (
            decision_sha256
        )
        assert state["Sub2API_route_rebaseline_completed"]
        assert state["Sub2API_candidate_model_alias"] == "gpt-5.5"
        assert state["Sub2API_candidate_endpoint_path"] == "/responses"
        assert not state["Sub2API_secure_transport_confirmed"]
        assert not state["Sub2API_credentialed_request_admissible"]
        assert not state["Sub2API_probe_or_canary_authorized"]

        expected_scope = [
            "S4_T06_entry_Sub2API_public_non_sensitive_diagnostic_canary_"
            "post_result_program_disposition",
            "repository_and_git_hygiene",
        ]
        if program["next_action"]["item_id"] in {
            DEEPSEEK_MAINLINE,
            "S4-T06-MU-ACTION-PLANNING-TEMPORAL-AUTHORITY-AND-CAPTURE-V2-"
            "TERMINAL-RESULT-MATERIALIZATION-MINIMUM-ZERO-CALL-"
            "IMPLEMENTATION",
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


def test_decision_contains_no_secret_and_authorizes_no_request() -> None:
    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    text = DECISION.read_text(encoding="utf-8")

    assert decision["next_action"] == NEXT
    assert not decision["next_action_authorized"]
    assert not decision["program_disposition"]["credential_binding_authorized"]
    assert not decision["program_disposition"]["metadata_probe_authorized"]
    assert not decision["program_disposition"]["strict_schema_canary_authorized"]
    assert "sk-" not in text
    assert "Bearer " not in text
