from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "releases"))

from run_fin_ia_0_1_s4_t06_entry_sub2api_public_nonsensitive_diagnostic_canary import (  # noqa: E501
    CANARY_ID,
    execute,
    preflight,
)


class _FakeTransport:
    def __init__(self, result: Mapping[str, Any]) -> None:
        self.result = result
        self.calls: list[dict[str, Any]] = []

    def __call__(self, **kwargs: Any) -> Mapping[str, Any]:
        self.calls.append(kwargs)
        return self.result


def _valid_transport() -> dict[str, Any]:
    return {
        "transport_status": "ok",
        "http_status": 200,
        "latency_ms": 10,
        "transport_attempt_count": 1,
        "call_id_digest": "digest-only",
        "raw": {
            "id": "fixture-raw-id-must-not-persist",
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": json.dumps(
                                {
                                    "selected_alias": "N001",
                                    "judgment": "confirmed",
                                    "note_code": "synthetic_ok",
                                }
                            ),
                        }
                    ],
                }
            ],
            "usage": {
                "input_tokens": 25,
                "output_tokens": 12,
                "total_tokens": 37,
            },
        },
    }


def test_preflight_is_zero_call_no_credential_and_exact_wire(
    tmp_path: Path,
) -> None:
    result = preflight(result_path=tmp_path / "result.json")
    assert result["status"] == "pass_zero_call_exact_diagnostic_preflight"
    assert result["canary_id"] == CANARY_ID
    assert result["exact_request_url"] == (
        "http://43.135.174.27:8080/responses"
    )
    assert result["model"] == "gpt-5.5"
    assert result["credential_reads"] == 0
    assert result["credential_writes"] == 0
    assert not result["authorization_or_bearer_header_present"]
    assert result["fixed_client_marker_header_present"]
    assert result["fake_transport_exact_wire_parse_and_value_validation_pass"]
    assert result["model_calls"] == 0
    assert result["provider_calls"] == 0
    assert result["network_calls"] == 0
    assert result["transport_attempts"] == 0


def test_execute_calls_once_and_persists_only_sanitized_success(
    tmp_path: Path,
) -> None:
    path = tmp_path / "result.json"
    fake = _FakeTransport(_valid_transport())
    result = execute(result_path=path, transport_fn=fake)
    assert len(fake.calls) == 1
    call = fake.calls[0]
    assert call["url"] == "http://43.135.174.27:8080/responses"
    assert "Authorization" not in call["headers"]
    assert call["headers"]["x-openai-actor-authorization"] == (
        "local-image-extension"
    )
    assert call["body"]["model"] == "gpt-5.5"
    assert call["body"]["max_output_tokens"] == 128
    assert call["body"]["store"] is False
    assert call["body"]["stream"] is False
    assert result["status"] == (
        "pass_exact_once_public_diagnostic_route_wire_"
        "strict_schema_compatible"
    )
    persisted = path.read_text(encoding="utf-8")
    assert "fixture-raw-id-must-not-persist" not in persisted
    assert "local-image-extension" not in persisted
    assert "synthetic_ok" not in persisted
    assert "confirmed" not in persisted
    assert '"raw"' not in persisted
    assert result["strict_schema_parse_pass"]
    assert result["local_exact_value_validation_pass"]
    assert result["result_is_diagnostic_only"]
    assert not result["result_closes_RC_P36_074"]
    assert not result["result_admits_T06_or_full_chain"]


def test_execute_terminalizes_first_failure_without_retry(
    tmp_path: Path,
) -> None:
    path = tmp_path / "result.json"
    fake = _FakeTransport(
        {
            "transport_status": "http_error",
            "http_status": 422,
            "latency_ms": 5,
            "transport_attempt_count": 1,
        }
    )
    result = execute(result_path=path, transport_fn=fake)
    assert len(fake.calls) == 1
    assert result["status"] == "terminal_failed_no_retry"
    assert result["failure_class"] == (
        "strict_schema_request_rejected_or_unsupported"
    )
    assert result["retry_count"] == 0
    assert result["provider_hopping_count"] == 0
    assert result["automatic_repair_count"] == 0
    try:
        execute(result_path=path, transport_fn=fake)
    except RuntimeError as exc:
        assert str(exc) == "diagnostic_canary_identity_already_consumed"
    else:
        raise AssertionError("consumed diagnostic identity was reusable")
    assert len(fake.calls) == 1


def test_runner_source_has_no_credential_or_dotenv_access() -> None:
    source = (
        ROOT
        / "scripts/releases/"
        "run_fin_ia_0_1_s4_t06_entry_sub2api_public_"
        "nonsensitive_diagnostic_canary.py"
    ).read_text(encoding="utf-8")
    assert "OPENAI_API_KEY" not in source
    assert "SUB2API_API_KEY" not in source
    assert "dotenv" not in source.lower()
    assert "os.environ" not in source
    assert "ProxyHandler({})" in source
    assert "_NoRedirect" in source
