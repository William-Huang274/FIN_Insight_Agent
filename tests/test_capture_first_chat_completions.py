from __future__ import annotations

import json
from pathlib import Path
import urllib.error
import urllib.request

import pytest

from sec_agent.providers.chat_completions import (
    ModelGatewayError,
    execute_chat_completion_exact_once,
    execute_chat_completion_tool_step_exact_once,
    load_chat_completion_profile,
)


def _profile(**overrides: object):
    value: dict[str, object] = {
        "schema_version": "fin_ia_chat_completion_provider_profile_v1_0",
        "status": "experimental_provider_profile_not_product_authority",
        "provider_id": "fixture_provider",
        "wire_api": "openai_compatible_chat_completions",
        "base_url": "https://provider.example/v1",
        "endpoint": "/chat/completions",
        "model": "fixture-model",
        "api_key_env": "FIXTURE_PROVIDER_KEY",
        "timeout_seconds": 30,
        "maximum_response_bytes": 1048576,
        "request_defaults": {
            "temperature": 0,
            "max_tokens": 500,
            "stream": False,
            "response_format": {"type": "json_object"},
        },
        "authority": {
            "transport_attempt_ceiling": 1,
            "retry_count": 0,
            "capture_model_visible_request": True,
            "capture_assistant_output": True,
            "credential_capture_forbidden": True,
            "provider_private_reasoning_capture_forbidden": True,
            "provider_specific_profile_outside_core": True,
        },
    }
    value.update(overrides)
    return load_chat_completion_profile(value)


class _Response:
    status = 200

    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.headers = {
            "Content-Type": "application/json",
            "x-request-id": "provider-request-1",
        }

    def __enter__(self):
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self, size: int = -1) -> bytes:
        return json.dumps(self.payload).encode("utf-8")[:size]


def test_exact_once_gateway_captures_request_and_output_without_secret_or_reasoning(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    observed: dict[str, object] = {}

    def fake_urlopen(request: urllib.request.Request, timeout: int):
        observed["authorization_present"] = bool(
            request.headers.get("Authorization")
        )
        observed["payload"] = json.loads(bytes(request.data or b"").decode())
        observed["timeout"] = timeout
        return _Response(
            {
                "id": "fixture-response",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": '{"ok":true}',
                            "reasoning_content": "private chain",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 11,
                    "completion_tokens": 4,
                    "total_tokens": 15,
                },
            }
        )

    monkeypatch.setenv("FIXTURE_PROVIDER_KEY", "secret-never-capture")
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    result = execute_chat_completion_exact_once(
        profile=_profile(),
        messages=(
            {"role": "system", "content": "Return JSON."},
            {"role": "user", "content": "Bounded input."},
        ),
        capture_root=tmp_path,
        run_id="RUN::PLANNER-1",
        attempt_id="ATTEMPT::1",
    )

    assert result.content == '{"ok":true}'
    assert result.private_reasoning_fields_redacted == 1
    assert observed["authorization_present"] is True
    assert observed["timeout"] == 30
    request_capture = Path(result.request_capture_ref).read_text(encoding="utf-8")
    response_capture = Path(result.response_capture_ref).read_text(encoding="utf-8")
    assert "secret-never-capture" not in request_capture + response_capture
    assert "Authorization" not in request_capture + response_capture
    assert "private chain" not in response_capture
    assert '"content": "{\\"ok\\":true}"' in response_capture

    with pytest.raises(ModelGatewayError, match="identity_consumed"):
        execute_chat_completion_exact_once(
            profile=_profile(),
            messages=({"role": "user", "content": "Bounded input."},),
            capture_root=tmp_path,
            run_id="RUN::PLANNER-1",
            attempt_id="ATTEMPT::1",
        )


def test_gateway_preserves_http_failure_capture_without_retry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls = 0

    def fail(request: urllib.request.Request, timeout: int):
        nonlocal calls
        calls += 1
        raise urllib.error.HTTPError(
            request.full_url,
            429,
            "rate limited",
            {"Content-Type": "application/json", "x-request-id": "failed-1"},
            _ResponseFile(b'{"error":{"message":"quota"}}'),
        )

    monkeypatch.setenv("FIXTURE_PROVIDER_KEY", "fixture")
    monkeypatch.setattr(urllib.request, "urlopen", fail)
    with pytest.raises(ModelGatewayError, match="http_error:429") as failure:
        execute_chat_completion_exact_once(
            profile=_profile(),
            messages=({"role": "user", "content": "Bounded input."},),
            capture_root=tmp_path,
            run_id="RUN::HTTP-FAIL",
            attempt_id="ATTEMPT::1",
        )
    assert calls == 1
    capture = json.loads(
        Path(failure.value.capture_ref).read_text(encoding="utf-8")
    )
    assert capture["status_code"] == 429
    assert capture["response_body"]["error"]["message"] == "quota"


def test_gateway_invalid_provider_shape_preserves_response_capture_ref(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("FIXTURE_PROVIDER_KEY", "fixture")
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: _Response({"unexpected": True}),
    )

    with pytest.raises(ModelGatewayError) as failure:
        execute_chat_completion_exact_once(
            profile=_profile(),
            messages=({"role": "user", "content": "Bounded input."},),
            capture_root=tmp_path,
            run_id="RUN::INVALID-SHAPE",
            attempt_id="ATTEMPT::1",
        )

    assert failure.value.code == "model_gateway_choice_count_invalid"
    assert failure.value.capture_ref.endswith("provider_response.json")
    assert Path(failure.value.capture_ref).is_file()


def test_gateway_classifies_reasoning_budget_exhaustion(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("FIXTURE_PROVIDER_KEY", "fixture")
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: _Response(
            {
                "choices": [
                    {
                        "message": {"role": "assistant", "content": ""},
                        "finish_reason": "length",
                    }
                ],
                "usage": {
                    "completion_tokens": 500,
                    "completion_tokens_details": {"reasoning_tokens": 500},
                    "total_tokens": 511,
                },
            }
        ),
    )

    with pytest.raises(
        ModelGatewayError, match="reasoning_budget_exhausted"
    ) as failure:
        execute_chat_completion_exact_once(
            profile=_profile(),
            messages=({"role": "user", "content": "Bounded input."},),
            capture_root=tmp_path,
            run_id="RUN::REASONING-BUDGET",
            attempt_id="ATTEMPT::1",
        )

    assert Path(failure.value.capture_ref).is_file()


class _ResponseFile:
    def __init__(self, value: bytes) -> None:
        self.value = value

    def read(self, size: int = -1) -> bytes:
        return self.value[:size]


def test_provider_profile_rejects_plain_http_and_sensitive_request_defaults() -> None:
    with pytest.raises(ModelGatewayError, match="https_required"):
        _profile(base_url="http://provider.example")
    with pytest.raises(ModelGatewayError, match="request_defaults_invalid"):
        _profile(request_defaults={"api_key": "must-not-be-here"})


def test_tool_step_preserves_reasoning_only_for_transient_continuation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    observed: dict[str, object] = {}

    def fake_urlopen(request: urllib.request.Request, timeout: int):
        observed["body"] = json.loads(bytes(request.data or b"").decode())
        return _Response(
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "",
                            "reasoning_content": "transient private chain",
                            "tool_calls": [
                                {
                                    "id": "call-1",
                                    "type": "function",
                                    "function": {
                                        "name": "read_reviewed_evidence_for_cell",
                                        "arguments": '{"cell_id":"CELL::demand_quality"}',
                                    },
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
                "usage": {"total_tokens": 10},
            }
        )

    profile = _profile(
        request_defaults={
            "max_tokens": 500,
            "stream": False,
            "thinking": {"type": "enabled"},
            "reasoning_effort": "max",
        }
    )
    monkeypatch.setenv("FIXTURE_PROVIDER_KEY", "secret")
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    result = execute_chat_completion_tool_step_exact_once(
        profile=profile,
        messages=(
            {"role": "system", "content": "Use tools."},
            {"role": "user", "content": "Research one cell."},
            {
                "role": "assistant",
                "content": "",
                "reasoning_content": "prior transient chain",
                "tool_calls": [
                    {
                        "id": "prior-call",
                        "type": "function",
                        "function": {
                            "name": "read_reviewed_evidence_for_cell",
                            "arguments": '{"cell_id":"CELL::demand_quality"}',
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "prior-call",
                "content": '{"status":"ok"}',
            },
        ),
        tools=(
            {
                "type": "function",
                "function": {
                    "name": "read_reviewed_evidence_for_cell",
                    "description": "Read evidence.",
                    "parameters": {
                        "type": "object",
                        "properties": {"cell_id": {"type": "string"}},
                        "required": ["cell_id"],
                        "additionalProperties": False,
                    },
                },
            },
        ),
        capture_root=tmp_path,
        run_id="RUN::TOOL-STEP",
        attempt_id="STEP::1",
    )

    assert observed["body"]["messages"][2]["reasoning_content"] == (
        "prior transient chain"
    )
    assert result.reasoning_content == "transient private chain"
    assert result.continuation_assistant_message()["reasoning_content"] == (
        "transient private chain"
    )
    assert "reasoning_content" not in result.as_dict()
    request_capture = Path(result.request_capture_ref).read_text(encoding="utf-8")
    response_capture = Path(result.response_capture_ref).read_text(encoding="utf-8")
    assert "prior transient chain" not in request_capture
    assert "transient private chain" not in response_capture
    assert json.loads(request_capture)[
        "transient_private_reasoning_fields_redacted"
    ] == 1


def test_tool_step_classifies_reasoning_budget_exhaustion(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("FIXTURE_PROVIDER_KEY", "fixture")
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: _Response(
            {
                "choices": [
                    {
                        "message": {"role": "assistant", "content": ""},
                        "finish_reason": "length",
                    }
                ],
                "usage": {
                    "completion_tokens": 500,
                    "completion_tokens_details": {"reasoning_tokens": 500},
                    "total_tokens": 511,
                },
            }
        ),
    )

    with pytest.raises(
        ModelGatewayError, match="reasoning_budget_exhausted"
    ) as failure:
        execute_chat_completion_tool_step_exact_once(
            profile=_profile(
                request_defaults={
                    "max_tokens": 500,
                    "stream": False,
                    "thinking": {"type": "enabled"},
                    "reasoning_effort": "max",
                }
            ),
            messages=({"role": "user", "content": "Research one cell."},),
            tools=(
                {
                    "type": "function",
                    "function": {
                        "name": "submit_research_judgment",
                        "description": "Submit one judgment.",
                        "parameters": {
                            "type": "object",
                            "properties": {"cell_id": {"type": "string"}},
                            "required": ["cell_id"],
                            "additionalProperties": False,
                        },
                    },
                },
            ),
            capture_root=tmp_path,
            run_id="RUN::TOOL-REASONING-BUDGET",
            attempt_id="ATTEMPT::1",
        )

    assert Path(failure.value.capture_ref).is_file()
