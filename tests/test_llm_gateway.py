from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

from sec_agent.llm_gateway import chat_completion, responses_completion


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


def test_chat_completion_retries_transient_transport_error(monkeypatch) -> None:
    calls: list[str] = []

    def fake_urlopen(req: urllib.request.Request, timeout: int) -> _FakeResponse:
        calls.append(req.full_url)
        if len(calls) == 1:
            raise urllib.error.URLError(FileNotFoundError(2, "No such file or directory"))
        return _FakeResponse(
            {
                "choices": [{"message": {"content": "{\"ok\": true}"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7},
            }
        )

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "1")
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRY_BACKOFF_S", "0")
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    result = chat_completion(
        llm_backend="deepseek",
        base_url="https://api.deepseek.com",
        chat_completions_path="/chat/completions",
        model="deepseek-v4-pro",
        messages=[{"role": "user", "content": "Return JSON."}],
        response_format={"type": "json_object"},
        api_key_env="DEEPSEEK_API_KEY",
    )

    assert result["status"] == "ok"
    assert result["transport_attempt_count"] == 2
    assert len(result["transport_failures"]) == 1
    assert calls == ["https://api.deepseek.com/chat/completions"] * 2


def test_chat_completion_does_not_retry_invalid_url(monkeypatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "2")
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRY_BACKOFF_S", "0")

    result = chat_completion(
        llm_backend="deepseek",
        base_url="",
        chat_completions_path="/chat/completions",
        model="deepseek-v4-pro",
        messages=[{"role": "user", "content": "Return JSON."}],
        response_format={"type": "json_object"},
        api_key_env="DEEPSEEK_API_KEY",
    )

    assert result["status"] == "provider_error"
    assert result["transport_attempt_count"] == 1
    assert "unknown url type" in result["failure_reason"]


def test_chat_completion_direct_proxy_mode_uses_explicit_no_proxy_opener(monkeypatch) -> None:
    captured_proxy_handlers: list[urllib.request.ProxyHandler] = []
    opened_urls: list[str] = []

    class _FakeOpener:
        def open(self, req: urllib.request.Request, timeout: int) -> _FakeResponse:
            opened_urls.append(req.full_url)
            return _FakeResponse(
                {
                    "choices": [{"message": {"content": "{\"ok\": true}"}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
                }
            )

    def fake_build_opener(*handlers: object) -> _FakeOpener:
        captured_proxy_handlers.extend(handler for handler in handlers if isinstance(handler, urllib.request.ProxyHandler))
        return _FakeOpener()

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("LLM_GATEWAY_PROXY_MODE", "direct")
    monkeypatch.setattr(urllib.request, "build_opener", fake_build_opener)

    result = chat_completion(
        llm_backend="deepseek",
        base_url="https://api.deepseek.com",
        chat_completions_path="/chat/completions",
        model="deepseek-v4-pro",
        messages=[{"role": "user", "content": "Return JSON."}],
        response_format={"type": "json_object"},
        api_key_env="DEEPSEEK_API_KEY",
    )

    assert result["status"] == "ok"
    assert result["proxy_mode"] == "direct"
    assert opened_urls == ["https://api.deepseek.com/chat/completions"]
    assert len(captured_proxy_handlers) == 1


def test_chat_completion_event_log_records_started_and_finished(monkeypatch, tmp_path: Path) -> None:
    event_log = tmp_path / "model_call_events.jsonl"

    def fake_urlopen(req: urllib.request.Request, timeout: int) -> _FakeResponse:
        return _FakeResponse(
            {
                "choices": [{"message": {"content": "{\"ok\": true}"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7},
            }
        )

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("LLM_GATEWAY_EVENT_LOG_PATH", str(event_log))
    monkeypatch.setenv("LLM_GATEWAY_PROXY_MODE", "system")
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    result = chat_completion(
        llm_backend="deepseek",
        base_url="https://api.deepseek.com",
        chat_completions_path="/chat/completions",
        model="deepseek-v4-pro",
        messages=[{"role": "user", "content": "Return JSON."}],
        response_format={"type": "json_object"},
        api_key_env="DEEPSEEK_API_KEY",
        role="memo_writer",
    )

    rows = [json.loads(line) for line in event_log.read_text(encoding="utf-8").splitlines()]
    assert result["status"] == "ok"
    assert [row["event_type"] for row in rows] == ["model_call_started", "model_call_finished"]
    assert rows[0]["call_id"] == rows[1]["call_id"] == result["call_id"]
    assert rows[0]["role"] == "memo_writer"
    assert rows[1]["total_tokens"] == 7
    assert "Authorization" not in json.dumps(rows, ensure_ascii=False)


def test_responses_completion_sends_native_json_schema_without_tools_and_logs_no_output(
    monkeypatch, tmp_path: Path
) -> None:
    event_log = tmp_path / "responses_events.jsonl"
    captured: dict[str, object] = {}
    generated_text = '{"secret-provider-output":"must-not-enter-event-log"}'

    def fake_urlopen(req: urllib.request.Request, timeout: int) -> _FakeResponse:
        captured["url"] = req.full_url
        captured["payload"] = json.loads(bytes(req.data or b"").decode("utf-8"))
        return _FakeResponse(
            {
                "id": "resp_fixture",
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": generated_text}],
                    }
                ],
                "usage": {
                    "input_tokens": 11,
                    "output_tokens": 7,
                    "total_tokens": 18,
                },
            }
        )

    text_format = {
        "format": {
            "type": "json_schema",
            "name": "fixture_schema",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {"result": {"type": "string"}},
                "required": ["result"],
                "additionalProperties": False,
            },
        }
    }
    monkeypatch.setenv("OPENAI_API_KEY", "test-secret-never-persist")
    monkeypatch.setenv("LLM_GATEWAY_EVENT_LOG_PATH", str(event_log))
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    result = responses_completion(
        llm_backend="openai",
        base_url="https://api.openai.com/v1",
        responses_path="/responses",
        model="fixture-structured-model",
        input=[{"role": "user", "content": "Return the bounded result."}],
        text=text_format,
        api_key_env="OPENAI_API_KEY",
        max_output_tokens=500,
        reasoning={"effort": "medium"},
        role="bounded_specialist_and_lead",
    )

    assert result["status"] == "ok"
    assert result["response_status"] == "completed"
    assert result["response_output"][0]["content"][0]["text"] == generated_text
    assert result["input_tokens"] == 11
    assert result["output_tokens"] == 7
    assert captured["url"] == "https://api.openai.com/v1/responses"
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["text"] == text_format
    assert payload["max_output_tokens"] == 500
    assert payload["reasoning"] == {"effort": "medium"}
    assert "tools" not in payload
    assert "tool_choice" not in payload
    assert "temperature" not in payload

    serialized_events = event_log.read_text(encoding="utf-8")
    assert generated_text not in serialized_events
    assert "test-secret-never-persist" not in serialized_events
    assert "Authorization" not in serialized_events
