from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.providers.chat_completions import (  # noqa: E402
    ChatCompletionResult,
    ModelGatewayError,
)


SCRIPT = ROOT / "scripts/research/run_s3_current_research_consumer_canary.py"


def _runner():
    spec = importlib.util.spec_from_file_location(
        "s3_current_research_consumer_canary_runner",
        SCRIPT,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_live_runner_is_case_bound_and_has_exact_once_budget() -> None:
    runner = _runner()
    source = SCRIPT.read_text(encoding="utf-8")

    assert 'case_key = str(authority["case_key"])' in source
    assert 'evidence_service.get_case(\n        case_key,' in source
    assert 'retrieval_service.execute_controlled_plan(\n        case_key,' in source
    assert '"model_calls": 1' in source
    assert '"transport_attempts": 1' in source
    assert '"retries": 0' in source
    assert '"fallbacks": 0' in source
    assert '"external_retrieval_calls": 0' in source
    assert '"planner_calls": 0' in source
    assert '"current_product_pointer_mutations": 0' in source
    assert runner.AUTHORITY_SCHEMA.endswith("_v1_0")


def test_terminal_summary_preserves_success_usage_and_no_product_claim(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runner = _runner()
    monkeypatch.setattr(runner, "_relative", lambda path: Path(path).name)
    authority_path = tmp_path / "authority.json"
    authority_path.write_text("{}", encoding="utf-8")
    request = ROOT / ".codex_runtime/model_runs/test/request.json"
    response = ROOT / ".codex_runtime/model_runs/test/response.json"
    provider = ChatCompletionResult(
        status="completed_exact_once",
        provider_id="fixture",
        model="fixture-model",
        content="{}",
        finish_reason="stop",
        usage={"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
        request_capture_ref=str(request),
        response_capture_ref=str(response),
        request_digest="a" * 64,
        response_digest="b" * 64,
        private_reasoning_fields_redacted=1,
    )
    research_input = {
        "case_identity": {"case_key": "DELL", "research_as_of": "2026-08-06"},
        "research_input_digest": "c" * 64,
        "evidence_pack_binding": {
            "artifact_digest": "d" * 64,
            "pack_payload_digest": "e" * 64,
        },
    }
    summary = runner._terminal_summary(
        authority={
            "implementation_commit": "f" * 40,
            "output_contract": {"result_id": "RESULT-1"},
            "known_boundary": "not product acceptance",
        },
        authority_path=authority_path,
        research_input=research_input,
        provider_result=provider,
        status="completed_contract_valid",
        failure_phase="",
        failure_code="",
        model_call_attempted=True,
        transport_attempted=True,
    )

    assert summary["terminal"]["model_calls"] == 1
    assert summary["terminal"]["retries"] == 0
    assert summary["terminal"]["product_publication"] is False
    assert summary["provider"]["usage"]["total_tokens"] == 5
    assert summary["acceptance"]["natural_research_quality_proven"] is False
    assert summary["acceptance"]["s3_product_acceptance"] is False


def test_gateway_failure_capture_is_terminalized_without_retry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runner = _runner()
    monkeypatch.setattr(runner, "_relative", lambda path: Path(path).name)
    authority_path = tmp_path / "authority.json"
    result_path = tmp_path / "result.json"
    authority = {
        "output_contract": {
            "capture_root_ref": ".codex_runtime/model_runs/fixture",
            "private_output_root_ref": "data/workbench_private/fixture",
            "public_result_ref": result_path.relative_to(tmp_path).as_posix(),
            "result_id": "RESULT-FAIL",
            "run_id": "RUN-FAIL",
            "attempt_id": "ATTEMPT-01",
            "product_publication": "forbidden",
        },
        "implementation_commit": "a" * 40,
        "case_key": "DELL",
        "known_boundary": "fixture",
        "bound_inputs": {"model_visible_messages_sha256": "b" * 64},
    }
    authority_path.write_text(json.dumps(authority), encoding="utf-8")
    research_input = {
        "case_identity": {"case_key": "DELL", "research_as_of": "2026-08-06"},
        "research_input_digest": "c" * 64,
        "evidence_pack_binding": {
            "artifact_digest": "d" * 64,
            "pack_payload_digest": "e" * 64,
        },
    }

    monkeypatch.setattr(runner, "_json", lambda path: authority if path == authority_path else {})
    monkeypatch.setattr(runner, "validate_authority", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        runner,
        "_compile_runtime_input",
        lambda *_args, **_kwargs: ({}, research_input, ({"role": "user", "content": "x"},)),
    )

    # The detailed gateway behavior is covered in test_capture_first_chat_completions;
    # this runner-level test protects the no-retry terminal accounting helper.
    response_ref = ROOT / ".codex_runtime/model_runs/fixture/provider_response.json"
    error = ModelGatewayError(
        "model_gateway_transport_error",
        capture_ref=str(response_ref),
    )
    assert error.code == "model_gateway_transport_error"
    summary = runner._terminal_summary(
        authority=authority,
        authority_path=authority_path,
        research_input=research_input,
        provider_result=None,
        status="terminal_failed_no_retry",
        failure_phase="provider_transport_or_response",
        failure_code=error.code,
        model_call_attempted=True,
        transport_attempted=True,
        provider_identity={"provider_id": "fixture", "model": "fixture-model"},
        response_capture_ref=runner._relative(response_ref),
    )
    assert summary["status"] == "terminal_failed_no_retry"
    assert summary["terminal"]["transport_attempts"] == 1
    assert summary["terminal"]["retries"] == 0
    assert summary["provider"]["response_capture_ref"].endswith(
        "provider_response.json"
    )
