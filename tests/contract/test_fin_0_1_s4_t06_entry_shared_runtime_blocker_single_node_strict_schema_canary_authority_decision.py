from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping

import pytest


ROOT = Path(__file__).resolve().parents[2]
DEEPSEEK_MAINLINE = (
    "S4-T06-MU-RUNTIME-AUDIT-EVIDENCE-V2-AND-MATERIAL-NUMERIC-"
    "CLASSIFIER-R5-EXACT-LIVE-EXECUTION-AND-SUCCESS-ONLY-PAIRED-ASSESSMENT"
)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "contract"))

DECISION = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_s4_t06_entry_shared_runtime_blocker_"
    "single_node_strict_schema_canary_authority_decision_v1_0.json"
)

from apps.workbench.backend.application.bounded_agent_executor import (
    build_s3_three_cell_bounded_agent_executor_for_admission,
)
from test_fin_0_1_s3_t09_cross_cell_scoped_identity_zero_call_implementation import (
    _shared_local_id_specialists,
)
from test_fin_0_1_s4_t05_case_numeric_authority_and_delivery_identity_zero_call_implementation import (
    _NumericIdentitySafeFake,
)
from test_fin_0_1_s4_t06_entry_shared_runtime_blocker_minimum_zero_call_implementation import (
    _OpenAIChatFake,
    _StrictResponsesFake,
    _case_fixture_input_and_admission,
    _strict_admission,
)


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _capture_exact_first_strict_call(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Mapping[str, Any], Any, Any]:
    input_pack, source_admission = _case_fixture_input_and_admission(
        "DELL"
    )
    admission = _strict_admission(input_pack, source_admission)
    _, specialists = _shared_local_id_specialists()
    specialists = {
        cell_id: deepcopy(specialist)
        for cell_id, specialist in specialists.items()
    }
    chat = _OpenAIChatFake(
        _NumericIdentitySafeFake(input_pack, specialists)
    )
    strict_fake = _StrictResponsesFake()
    captured: list[Mapping[str, Any]] = []

    def responses(**kwargs: Any) -> Mapping[str, Any]:
        captured.append(deepcopy(kwargs))
        return strict_fake(**kwargs)

    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv(
        "OPENAI_API_KEY",
        "fixture-not-a-real-secret",
    )
    result = build_s3_three_cell_bounded_agent_executor_for_admission(
        admission,
        chat_completion_fn=chat,
        responses_completion_fn=responses,
    ).execute(
        input_pack,
        admission,
        run_identity={
            "research_run_id": "fixture-canary-authority",
            "attempt_id": "fixture-canary-authority",
        },
    )
    assert len(captured) == 3
    assert len(chat.calls) == 9
    assert len(result.provider_output_captures) == 12
    assert len(result.artifacts) == 9
    return captured[0], input_pack, admission


def test_exact_canary_template_is_recomputed_without_a_provider_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    exact = decision["exact_canary"]
    first, input_pack, admission = _capture_exact_first_strict_call(
        monkeypatch
    )
    request = json.loads(first["input"][1]["content"])
    schema = first["text"]["format"]["schema"]
    template = {
        "provider": "openai",
        "base_url": "https://api.openai.com/v1",
        "endpoint": "/responses",
        "model": "gpt-5.6-sol",
        "input": first["input"],
        "text": first["text"],
        "reasoning": {"effort": "none"},
        "max_output_tokens": 512,
        "timeout_s": 120,
        "stream": False,
        "role": first["role"],
        "profile": first["profile"],
    }

    assert input_pack.input_digest == exact["input_digest"]
    assert _canonical_sha256(request) == exact[
        "canonical_request_sha256"
    ]
    assert _canonical_sha256(schema) == exact[
        "server_schema_sha256"
    ]
    assert _canonical_sha256(first["text"]) == exact[
        "text_format_sha256"
    ]
    assert _text_sha256(first["input"][0]["content"]) == exact[
        "system_prompt_sha256"
    ]
    assert _text_sha256(first["input"][1]["content"]) == exact[
        "user_payload_sha256"
    ]
    assert _canonical_sha256(template) == exact[
        "exact_request_template_sha256"
    ]
    assert admission.reasoning_effort == "none"


def test_authority_is_exact_once_and_does_not_inflate_scope() -> None:
    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    authority = decision["authority"]
    budget = decision["hard_budget"]

    assert decision["decision_label"] == (
        "authorize_one_request_strict_schema_canary"
    )
    assert authority["future_exact_once_canary_execution_authorized"]
    assert not authority[
        "current_turn_model_or_provider_execution_authorized"
    ]
    assert not authority["full_chain_execution_authorized"]
    assert not authority["MU_T06_execution_authorized"]
    assert not authority["DELL_R12_authorized"]
    assert budget["maximum_semantic_model_calls"] == 1
    assert budget["maximum_provider_calls"] == 1
    assert budget["maximum_network_calls"] == 1
    assert budget["maximum_transport_attempts"] == 1
    assert budget["retry_budget"] == 0
    assert budget["chat_completions_calls"] == 0
    assert budget["canonical_work_unit_attempt_run_writes"] == 0
    assert budget["business_artifact_writes"] == 0
    assert decision["current_turn_observed_counts"][
        "actual_provider_calls"
    ] == 0


def test_failure_stops_without_retry_or_full_chain() -> None:
    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    failure = decision["failure_contract"]

    assert failure["first_credible_failure"] == "terminal_stop"
    assert failure["retry"] == 0
    assert not failure["provider_hopping"]
    assert not failure["full_chain_after_failure"]
    assert not failure["automatic_repair"]
    assert decision["stage_disposition"]["S4_T06"] == "not_entered"
    assert decision["next_action"] == (
        "S4-T06-ENTRY-SHARED-RUNTIME-BLOCKER-SINGLE-NODE-"
        "STRICT-SCHEMA-CANARY-EXACT-ONCE-EXECUTION"
    )
    assert decision["next_action_authorized"]


def test_backlogs_and_project_os_expose_only_exact_once_execution() -> None:
    expected = (
        "S4-T06-ENTRY-SHARED-RUNTIME-BLOCKER-SINGLE-NODE-"
        "STRICT-SCHEMA-CANARY-EXACT-ONCE-EXECUTION"
    )
    post_canary = (
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
    root_cause_rows = [
        json.loads(line)
        for line in (
            ROOT / "docs/project_os/root_cause_issue_ledger.jsonl"
        ).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    rc_070 = [
        row
        for row in root_cause_rows
        if row["issue_id"]
        == "RC-P36-070-s4-t06-strict-schema-unsupported-uniqueItems"
    ][-1]

    assert program["next_action"]["item_id"] in {
        expected,
        post_canary,
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
    assert program["next_action"]["single_node_canary_authorized"]
    assert s4["current_next_action"] == program["next_action"]["item_id"]
    assert s4["T06_entry_program_scope_replace"][
        "single_node_canary_authorized"
    ]
    if program["next_action"]["item_id"] == expected:
        assert not program["next_action"][
            "single_node_canary_execution_started"
        ]
        assert not s4["T06_entry_program_scope_replace"][
            "single_node_canary_execution_started"
        ]
        assert rc_070["allowed_run_scopes"] == [
            "S4_T06_entry_shared_runtime_blocker_single_node_strict_"
            "schema_canary_exact_once_execution",
            "repository_and_git_hygiene",
        ]
    else:
        assert program["next_action"][
            "single_node_canary_execution_started"
        ]
        assert program["next_action"]["single_node_canary_consumed"]
        assert s4["T06_entry_program_scope_replace"][
            "single_node_canary_execution_completed"
        ]
        if program["next_action"]["item_id"] == post_canary:
            assert rc_070["allowed_run_scopes"] == [
                "S4_T06_entry_openai_credential_requalification_authority_"
                "decision",
                "repository_and_git_hygiene",
            ]
        elif program["next_action"]["item_id"] == metadata_probe:
            assert rc_070["allowed_run_scopes"] == [
                "S4_T06_entry_openai_credential_requalification_exact_once_"
                "metadata_probe",
                "repository_and_git_hygiene",
            ]
        elif program["next_action"]["item_id"] == (
            requalified_canary_authority
        ):
            assert rc_070["allowed_run_scopes"] == [
                "S4_T06_entry_openai_credential_requalified_fresh_strict_"
                "schema_canary_authority_decision",
                "repository_and_git_hygiene",
            ]
        elif program["next_action"]["item_id"] == (
            requalified_canary_execution
        ):
            assert rc_070["allowed_run_scopes"] == [
                "S4_T06_entry_openai_credential_requalified_fresh_strict_"
                "schema_canary_exact_once_execution",
                "repository_and_git_hygiene",
            ]
        elif program["next_action"]["item_id"] == http_429_disposition:
            assert rc_070["allowed_run_scopes"] == [
                "S4_T06_entry_openai_HTTP_429_rate_or_quota_program_"
                "disposition_decision",
                "repository_and_git_hygiene",
            ]
        elif program["next_action"]["item_id"] == sub2api_rebaseline:
            assert rc_070["allowed_run_scopes"] == [
                "S4_T06_entry_Sub2API_provider_route_and_capability_contract_"
                "rebaseline_decision",
                "repository_and_git_hygiene",
            ]
        elif program["next_action"]["item_id"] == sub2api_secure_transport:
            assert rc_070["allowed_run_scopes"] == [
                "S4_T06_entry_Sub2API_secure_transport_endpoint_confirmation",
                "repository_and_git_hygiene",
            ]
        elif (
            program["next_action"]["item_id"]
            == sub2api_diagnostic_authority
        ):
            assert rc_070["allowed_run_scopes"] == [
                "S4_T06_entry_Sub2API_public_non_sensitive_diagnostic_canary_"
                "authority_decision",
                "repository_and_git_hygiene",
            ]
        elif (
            program["next_action"]["item_id"]
            == sub2api_diagnostic_implementation
        ):
            assert rc_070["allowed_run_scopes"] == [
                "S4_T06_entry_Sub2API_public_non_sensitive_diagnostic_canary_"
                "minimum_zero_call_implementation_and_preflight",
                "repository_and_git_hygiene",
            ]
        elif (
            program["next_action"]["item_id"]
            == sub2api_diagnostic_result
        ):
            assert rc_070["allowed_run_scopes"] == [
                "S4_T06_entry_Sub2API_public_non_sensitive_diagnostic_canary_"
                "post_result_program_disposition",
                "repository_and_git_hygiene",
            ]
        else:
            assert program["next_action"]["item_id"] in {
                DEEPSEEK_MAINLINE,
                "S4-T06-MU-ACTION-PLANNING-TEMPORAL-AUTHORITY-AND-CAPTURE-"
                "V2-TERMINAL-RESULT-MATERIALIZATION-MINIMUM-ZERO-CALL-"
                "IMPLEMENTATION",
            }
            assert rc_070["allowed_run_scopes"] == [
                "S4_T06_MU_DeepSeek_fresh_exact_admission_preparation_and_"
                "zero_call_proof",
                "repository_and_git_hygiene",
            ]
