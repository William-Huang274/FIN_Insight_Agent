from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

import scripts.engineering.verify_active_baseline as active_baseline
from scripts.research.run_s3_current_dynamic_single_unit_live import (
    AUTHORITY_SCHEMA,
    AUTHORITY_STATUS,
    CurrentDynamicSingleUnitLiveError,
    _force_tool,
    _public_provider_step,
    _tool_arguments,
    run,
    validate_authority,
)
from sec_agent.providers import execute_agent_tool_step_exact_once
from sec_agent.providers.chat_completions import ChatCompletionToolStepResult


def _step(*, name: str, arguments: object) -> ChatCompletionToolStepResult:
    return ChatCompletionToolStepResult(
        status="completed_exact_once_tool_step",
        provider_id="fixture",
        model="fixture-model",
        content="",
        reasoning_content="transient and never persisted",
        tool_calls=(
            {
                "id": "call-fixture-1",
                "type": "function",
                "function": {
                    "name": name,
                    "arguments": json.dumps(arguments, ensure_ascii=False),
                },
            },
        ),
        finish_reason="tool_calls",
        usage={"prompt_tokens": 10, "completion_tokens": 5},
        request_capture_ref=str(ROOT / "data/captures/request.json"),
        response_capture_ref=str(ROOT / "data/captures/response.json"),
        request_digest="a" * 64,
        response_digest="b" * 64,
        private_reasoning_fields_redacted=1,
    )


def test_current_dynamic_live_parses_exact_expected_tool_only() -> None:
    step = _step(
        name="request_research_evidence",
        arguments={"request_ids": ["REQ::DELL::PVM_BRIDGE::V1"]},
    )
    payload, call_id = _tool_arguments(
        step, expected_name="request_research_evidence"
    )
    assert payload["request_ids"] == ["REQ::DELL::PVM_BRIDGE::V1"]
    assert call_id == "call-fixture-1"

    with pytest.raises(CurrentDynamicSingleUnitLiveError) as exc:
        _tool_arguments(step, expected_name="submit_research_reflection")
    assert exc.value.code == "current_dynamic_live_unexpected_tool_call"


def test_current_dynamic_live_forces_one_named_function() -> None:
    assert _force_tool("submit_research_reflection") == {
        "type": "function",
        "function": {"name": "submit_research_reflection"},
    }


def test_current_dynamic_live_public_step_excludes_model_payload() -> None:
    private = _step(
        name="submit_research_reflection",
        arguments={"secret_model_atom": "private"},
    ).as_dict()
    public = _public_provider_step(private)
    rendered = json.dumps(public, ensure_ascii=False)
    assert "secret_model_atom" not in rendered
    assert "transient and never persisted" not in rendered
    assert '"tool_calls":' not in rendered
    assert public["reasoning_content_persisted"] is False


def test_current_dynamic_live_authority_rejects_budget_drift_first(
    tmp_path: Path,
) -> None:
    authority = {
        "schema_version": AUTHORITY_SCHEMA,
        "status": AUTHORITY_STATUS,
        "signed_at": "2026-08-23T00:00:00Z",
        "implementation_commit": "0" * 40,
        "case_key": "DELL",
        "cell_id": "CELL::value_capture",
        "execution_budget": {"maximum_model_calls": 99},
        "bound_inputs": {},
        "output_contract": {},
        "known_boundary": "x" * 100,
    }
    path = tmp_path / "authority.json"
    path.write_text(json.dumps(authority), encoding="utf-8")
    with pytest.raises(CurrentDynamicSingleUnitLiveError) as exc:
        validate_authority(authority, authority_path=path.resolve())
    assert exc.value.code == "current_dynamic_live_authority_budget_invalid"


def test_current_dynamic_runner_replaces_legacy_single_cell_active_entry() -> None:
    assert (
        "scripts/research/run_s3_current_dynamic_single_unit_zero_call.py"
        in active_baseline.PYTHON_ENTRYPOINTS
    )
    assert (
        "scripts/research/run_s3_current_dynamic_single_unit_live.py"
        in active_baseline.PYTHON_ENTRYPOINTS
    )
    assert (
        "scripts/research/run_s3_dynamic_single_cell_live.py"
        not in active_baseline.PYTHON_ENTRYPOINTS
    )


def test_current_dynamic_live_uses_provider_neutral_transport_dispatch() -> None:
    assert run.__kwdefaults__["executor"] is execute_agent_tool_step_exact_once
