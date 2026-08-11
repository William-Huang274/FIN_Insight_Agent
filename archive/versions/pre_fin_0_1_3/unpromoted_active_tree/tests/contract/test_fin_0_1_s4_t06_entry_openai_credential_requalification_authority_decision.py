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
    "fin_ia_0_1_s4_t06_entry_openai_credential_"
    "requalification_authority_decision_v1_0.json"
)
SOURCE = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_s4_t06_entry_shared_runtime_blocker_"
    "post_canary_program_disposition_decision_v1_0.json"
)


def test_authority_is_metadata_only_zero_call_and_exact_once() -> None:
    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    authority = decision["authority"]
    probe = decision["exact_probe"]
    budget = decision["hard_budget"]
    observed = decision["current_turn_observed_counts"]

    assert decision["decision_label"] == (
        "authorize_one_read_only_credential_and_model_visibility_probe"
    )
    assert authority["future_exact_once_metadata_probe_authorized"]
    assert not authority["current_turn_provider_network_call_authorized"]
    assert not authority["model_inference_or_generation_authorized"]
    assert not authority["responses_or_chat_completions_authorized"]
    assert not authority["new_strict_schema_canary_authorized"]
    assert not authority["consumed_canary_replay_authorized"]
    assert probe["method"] == "GET"
    assert probe["endpoint"] == "/models/gpt-5.6-sol"
    assert budget["maximum_network_calls"] == 1
    assert budget["maximum_transport_attempts"] == 1
    assert budget["retry_budget"] == 0
    assert budget["model_inference_calls"] == 0
    assert budget["responses_calls"] == 0
    assert budget["chat_completions_calls"] == 0
    assert budget["maximum_total_cost_usd"] == 0.0
    assert set(observed.values()) == {0, 0.0}


def test_decision_binds_source_and_preserves_secret_boundary() -> None:
    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    source_sha256 = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    assert decision["source_disposition"]["sha256"] == source_sha256
    materialization = decision["credential_materialization_evidence"]
    assert materialization["usable_shape_present"]
    assert not materialization["env_file_git_tracked"]
    assert materialization["env_file_git_ignored"]
    assert not materialization[
        "credential_value_read_output_or_persisted"
    ]
    assert materialization["temporary_key_material_removed"]
    assert materialization["authentication_accepted"] == (
        "not_yet_evaluated"
    )
    text = DECISION.read_text(encoding="utf-8")
    assert "sk-" not in text
    assert "Authorization" not in text
    assert "org-" not in text
    assert "proj_" not in text


def test_success_boundary_does_not_inflate_to_schema_or_t06() -> None:
    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    success = decision["success_contract"]
    stage = decision["stage_disposition"]
    assert success["success_proves_only_authentication_and_model_visibility"]
    assert success["success_does_not_prove_responses_schema_or_semantics"]
    assert stage["S4_T05"] == "blocked_not_passed_not_owner_accepted"
    assert stage["DELL_R2"] == "not_proven"
    assert stage["S4_T06"] == "not_entered"
    assert stage["S5"] == "blocked"
    assert decision["next_action"] == (
        "S4-T06-ENTRY-OPENAI-CREDENTIAL-REQUALIFICATION-"
        "EXACT-ONCE-METADATA-PROBE"
    )
    assert decision["next_action_authorized"]


def test_backlogs_and_rc_ledger_expose_only_metadata_probe() -> None:
    decision_sha256 = hashlib.sha256(DECISION.read_bytes()).hexdigest()
    expected = (
        "S4-T06-ENTRY-OPENAI-CREDENTIAL-REQUALIFICATION-"
        "EXACT-ONCE-METADATA-PROBE"
    )
    progressed = (
        "S4-T06-ENTRY-OPENAI-CREDENTIAL-REQUALIFIED-"
        "FRESH-STRICT-SCHEMA-CANARY-AUTHORITY-DECISION"
    )
    execution = (
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
    rows = [
        json.loads(line)
        for line in (
            ROOT / "docs/project_os/root_cause_issue_ledger.jsonl"
        ).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    rc_071 = [
        row
        for row in rows
        if row["issue_id"]
        == "RC-P36-071-s4-t06-openai-credential-authentication-rejected"
    ][-1]
    assert program["next_action"]["item_id"] in {
        expected,
        progressed,
        execution,
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
    assert program["next_action"][
        "credential_requalification_authority_decision_sha256"
    ] == decision_sha256
    assert s4["T06_entry_program_scope_replace"][
        "credential_requalification_authority_decision_sha256"
    ] == decision_sha256
    if program["next_action"]["item_id"] == expected:
        assert rc_071["allowed_run_scopes"] == [
            "S4_T06_entry_openai_credential_requalification_exact_once_"
            "metadata_probe",
            "repository_and_git_hygiene",
        ]
    else:
        assert rc_071["status"].startswith("closed_")
        assert rc_071["allowed_run_scopes"] == [
            "repository_and_git_hygiene"
        ]
