from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "releases"))

from run_fin_ia_0_1_s4_t06_entry_single_node_strict_schema_canary import (
    CANARY_ID,
    execute,
    preflight,
)


class _FakeCompletion:
    def __init__(self, result: Mapping[str, Any]) -> None:
        self.result = result
        self.calls: list[dict[str, Any]] = []

    def __call__(self, **kwargs: Any) -> Mapping[str, Any]:
        self.calls.append(kwargs)
        return self.result


def _valid_response() -> dict[str, Any]:
    return {
        "status": "ok",
        "call_id": "fixture-canary-call",
        "provider": "openai",
        "model": "gpt-5.6-sol",
        "response_status": "completed",
        "response_output": [
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": json.dumps(
                            {
                                "program_cell_id": (
                                    "demand_authenticity_and_sustainability"
                                ),
                                "fact_judgments": [
                                    {
                                        "numeric_alias": (
                                            "N44E454E88A001"
                                        ),
                                        "direction": "supports",
                                        "materiality": "high",
                                        "confidence": "high",
                                        "interpretation_code": (
                                            "directional_support"
                                        ),
                                        "counterevidence_aliases": [],
                                    }
                                ],
                                "terminal_class": "supported",
                            },
                            ensure_ascii=False,
                        ),
                    }
                ],
            }
        ],
        "input_tokens": 1000,
        "output_tokens": 100,
        "total_tokens": 1100,
        "latency_ms": 10,
        "transport_attempt_count": 1,
        "raw_response": {
            "usage": {
                "input_tokens": 1000,
                "output_tokens": 100,
                "total_tokens": 1100,
                "input_tokens_details": {"cached_tokens": 0},
            }
        },
    }


def test_preflight_recomputes_frozen_wire_without_provider_call(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv(
        "OPENAI_API_KEY",
        "sk-fixture-not-a-real-key-000000000000",
    )
    result = preflight(result_path=tmp_path / "result.json")
    assert result["status"] == "pass_zero_call_exact_execution_preflight"
    assert result["canary_id"] == CANARY_ID
    assert result["model_calls"] == 0
    assert result["provider_calls"] == 0
    assert result["network_calls"] == 0


def test_execute_calls_once_persists_only_sanitized_success(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv(
        "OPENAI_API_KEY",
        "sk-fixture-not-a-real-key-000000000000",
    )
    path = tmp_path / "result.json"
    fake = _FakeCompletion(_valid_response())
    result = execute(result_path=path, completion_fn=fake)
    assert len(fake.calls) == 1
    assert result["status"] == (
        "pass_exact_once_live_provider_capability_proven"
    )
    persisted = path.read_text(encoding="utf-8")
    assert "fixture-not-a-real-key" not in persisted
    assert "directional_support" not in persisted
    assert "N44E454E88A001" not in persisted
    assert "supported" not in persisted
    assert "raw_response" not in persisted
    assert result["strict_schema_parse_pass"]
    assert result["local_semantic_validation_and_rendering_pass"]


def test_execute_calls_once_and_terminalizes_http_failure(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv(
        "OPENAI_API_KEY",
        "sk-fixture-not-a-real-key-000000000000",
    )
    path = tmp_path / "result.json"
    fake = _FakeCompletion(
        {
            "status": "provider_error",
            "failure_reason": "HTTP 403",
            "transport_attempt_count": 1,
            "call_id": "fixture-denied",
        }
    )
    result = execute(result_path=path, completion_fn=fake)
    assert len(fake.calls) == 1
    assert result["status"] == "terminal_failed_no_retry"
    assert result["failure_class"] == "model_or_endpoint_access_rejected"
    assert result["next_action"] == (
        "return_to_program_level_blocked_decision"
    )
    try:
        execute(result_path=path, completion_fn=fake)
    except RuntimeError as exc:
        assert str(exc) == "canary_identity_already_consumed"
    else:
        raise AssertionError("consumed canary identity was reusable")
    assert len(fake.calls) == 1
