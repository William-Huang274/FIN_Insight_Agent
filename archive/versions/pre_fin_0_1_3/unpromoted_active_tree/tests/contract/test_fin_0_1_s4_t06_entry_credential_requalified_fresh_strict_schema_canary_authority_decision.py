from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEEPSEEK_MAINLINE = (
    "S4-T06-MU-RUNTIME-AUDIT-EVIDENCE-V2-AND-MATERIAL-NUMERIC-"
    "CLASSIFIER-R5-EXACT-LIVE-EXECUTION-AND-SUCCESS-ONLY-PAIRED-ASSESSMENT"
)
AUTHORITY = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_s4_t06_entry_openai_credential_requalified_"
    "fresh_strict_schema_canary_authority_decision_v1_0.json"
)
RUNNER = ROOT / (
    "scripts/releases/"
    "run_fin_ia_0_1_s4_t06_entry_credential_requalified_"
    "strict_schema_canary.py"
)
NEXT = (
    "S4-T06-ENTRY-OPENAI-CREDENTIAL-REQUALIFIED-FRESH-"
    "STRICT-SCHEMA-CANARY-EXACT-ONCE-EXECUTION"
)
PROGRESSED = (
    "S4-T06-ENTRY-OPENAI-HTTP-429-RATE-OR-QUOTA-"
    "PROGRAM-DISPOSITION-DECISION"
)
RECLASSIFIED = (
    "S4-T06-ENTRY-SUB2API-PROVIDER-ROUTE-AND-CAPABILITY-"
    "CONTRACT-REBASELINE-DECISION"
)
SECURE_TRANSPORT = (
    "S4-T06-ENTRY-SUB2API-SECURE-TRANSPORT-ENDPOINT-CONFIRMATION"
)
DIAGNOSTIC_AUTHORITY = (
    "S4-T06-ENTRY-SUB2API-PUBLIC-NON-SENSITIVE-"
    "DIAGNOSTIC-CANARY-AUTHORITY-DECISION"
)
DIAGNOSTIC_IMPLEMENTATION = (
    "S4-T06-ENTRY-SUB2API-PUBLIC-NON-SENSITIVE-DIAGNOSTIC-"
    "CANARY-MINIMUM-ZERO-CALL-IMPLEMENTATION-AND-PREFLIGHT"
)
DIAGNOSTIC_RESULT = (
    "S4-T06-ENTRY-SUB2API-PUBLIC-NON-SENSITIVE-DIAGNOSTIC-"
    "CANARY-POST-RESULT-PROGRAM-DISPOSITION"
)


def _load_runner():
    spec = importlib.util.spec_from_file_location(
        "fresh_strict_schema_canary_runner_test",
        RUNNER,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _latest_issue(issue_id: str) -> dict:
    rows = [
        json.loads(line)
        for line in (
            ROOT / "docs/project_os/root_cause_issue_ledger.jsonl"
        ).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return [row for row in rows if row["issue_id"] == issue_id][-1]


def test_authority_uses_fresh_identity_and_exact_old_request_without_replay() -> None:
    authority = json.loads(AUTHORITY.read_text(encoding="utf-8"))
    exact = authority["exact_canary"]
    historical = authority["historical_canary_boundary"]
    budget = authority["hard_budget"]

    assert authority["decision_label"] == (
        "authorize_one_fresh_strict_schema_canary_after_"
        "credential_requalification"
    )
    assert exact["canary_id"] != historical["old_canary_id"]
    assert exact["result_ref"] != historical["old_result_ref"]
    assert historical["old_canary_consumed"]
    assert not historical["old_canary_replayable"]
    assert exact["exact_request_template_sha256"] == (
        "b92911d0bb9755c3e46fc0d4cac87cb0d07486d8fba8177ca69f2785ee443d7e"
    )
    assert exact["server_schema_sha256"] == (
        "24cdd015fd3c6b393c1d1013ffa065eb0a2a266c691720e981c01e6db9004938"
    )
    assert budget["maximum_semantic_model_calls"] == 1
    assert budget["maximum_provider_calls"] == 1
    assert budget["maximum_network_calls"] == 1
    assert budget["maximum_transport_attempts"] == 1
    assert budget["retry_budget"] == 0
    assert budget["maximum_output_tokens"] == 512
    assert budget["maximum_total_cost_usd"] == 0.05
    assert authority["next_action"] == NEXT
    assert authority["next_action_authorized"]


def test_authority_does_not_inflate_to_t06_or_business_execution() -> None:
    authority = json.loads(AUTHORITY.read_text(encoding="utf-8"))
    allowed = authority["authority"]
    observed = authority["current_turn_observed_counts"]
    stage = authority["stage_disposition"]

    assert allowed["future_exact_once_canary_execution_authorized"]
    assert not allowed["current_turn_model_or_provider_execution_authorized"]
    assert not allowed["old_canary_replay_authorized"]
    assert not allowed["full_chain_execution_authorized"]
    assert not allowed["admission_issuance_authorized"]
    assert not allowed["MU_T06_execution_authorized"]
    assert not allowed["DELL_R12_authorized"]
    assert observed["actual_model_calls"] == 0
    assert observed["actual_provider_calls"] == 0
    assert observed["execution_network_calls"] == 0
    assert observed["canary_executions"] == 0
    assert observed["business_artifacts_created"] == 0
    assert stage["S4_T05"] == "blocked_not_passed_not_owner_accepted"
    assert stage["DELL_R2"] == "not_proven"
    assert stage["S4_T06"] == "not_entered"
    assert stage["S5"] == "blocked"


def test_bound_runner_zero_call_preflight_matches_authority(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = _load_runner()
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    runner = module._load_bound_runner()
    result = runner.preflight(
        result_path=tmp_path / "fresh-result.json",
        require_credential=False,
    )

    assert result["status"] == "pass_zero_call_exact_execution_preflight"
    assert result["canary_id"] == module.CANARY_ID
    assert result["authority_decision_digest"] == hashlib.sha256(
        AUTHORITY.read_bytes()
    ).hexdigest()
    assert result["exact_request_digests"][
        "exact_request_template_sha256"
    ] == json.loads(AUTHORITY.read_text(encoding="utf-8"))["exact_canary"][
        "exact_request_template_sha256"
    ]
    assert result["fake_provider_strict_wire_and_local_validator_pass"]
    assert result["model_calls"] == 0
    assert result["provider_calls"] == 0
    assert result["network_calls"] == 0
    assert not (tmp_path / "fresh-result.json").exists()
    assert os.environ["LLM_GATEWAY_TRANSPORT_RETRIES"] == "0"


def test_backlogs_and_rc_ledger_preserve_authority_after_execution() -> None:
    authority_sha256 = hashlib.sha256(AUTHORITY.read_bytes()).hexdigest()
    runner_sha256 = hashlib.sha256(RUNNER.read_bytes()).hexdigest()
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

    assert program["next_action"]["item_id"] in {
        NEXT,
        PROGRESSED,
        RECLASSIFIED,
        SECURE_TRANSPORT,
        DIAGNOSTIC_AUTHORITY,
        DIAGNOSTIC_IMPLEMENTATION,
        DIAGNOSTIC_RESULT,
        DEEPSEEK_MAINLINE,
        "S4-T06-MU-ACTION-PLANNING-TEMPORAL-AUTHORITY-AND-CAPTURE-V2-"
        "TERMINAL-RESULT-MATERIALIZATION-MINIMUM-ZERO-CALL-IMPLEMENTATION",
    }
    assert s4["current_next_action"] == program["next_action"]["item_id"]
    for state in (
        program["next_action"],
        s4["T06_entry_program_scope_replace"],
    ):
        assert (
            state["fresh_strict_schema_canary_authority_decision_sha256"]
            == authority_sha256
        )
        assert state["fresh_strict_schema_canary_runner_sha256"] == (
            runner_sha256
        )
        assert state["fresh_strict_schema_canary_zero_call_preflight"] == (
            "pass"
        )
        if program["next_action"]["item_id"] == NEXT:
            assert state["future_canary_authorized"]
            assert not state["fresh_strict_schema_canary_execution_started"]
            assert not state["fresh_strict_schema_canary_consumed"]
        else:
            assert not state["future_canary_authorized"]
            assert state["fresh_strict_schema_canary_execution_started"]
            assert state["fresh_strict_schema_canary_execution_completed"]
            assert state["fresh_strict_schema_canary_consumed"]
    if program["next_action"]["item_id"] == NEXT:
        assert rc_070["allowed_run_scopes"] == [
            "S4_T06_entry_openai_credential_requalified_fresh_strict_"
            "schema_canary_exact_once_execution",
            "repository_and_git_hygiene",
        ]
    elif program["next_action"]["item_id"] == PROGRESSED:
        assert rc_070["allowed_run_scopes"] == [
            "S4_T06_entry_openai_HTTP_429_rate_or_quota_program_"
            "disposition_decision",
            "repository_and_git_hygiene",
        ]
    elif program["next_action"]["item_id"] == RECLASSIFIED:
        assert rc_070["allowed_run_scopes"] == [
            "S4_T06_entry_Sub2API_provider_route_and_capability_contract_"
            "rebaseline_decision",
            "repository_and_git_hygiene",
        ]
    elif program["next_action"]["item_id"] == SECURE_TRANSPORT:
        assert rc_070["allowed_run_scopes"] == [
            "S4_T06_entry_Sub2API_secure_transport_endpoint_confirmation",
            "repository_and_git_hygiene",
        ]
    elif program["next_action"]["item_id"] == DIAGNOSTIC_AUTHORITY:
        assert rc_070["allowed_run_scopes"] == [
            "S4_T06_entry_Sub2API_public_non_sensitive_diagnostic_canary_"
            "authority_decision",
            "repository_and_git_hygiene",
        ]
    elif program["next_action"]["item_id"] == DIAGNOSTIC_IMPLEMENTATION:
        assert rc_070["allowed_run_scopes"] == [
            "S4_T06_entry_Sub2API_public_non_sensitive_diagnostic_canary_"
            "minimum_zero_call_implementation_and_preflight",
            "repository_and_git_hygiene",
        ]
    elif program["next_action"]["item_id"] == DIAGNOSTIC_RESULT:
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
