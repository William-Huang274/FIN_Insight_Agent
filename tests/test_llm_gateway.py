from __future__ import annotations

import json
import urllib.error
import urllib.request

from sec_agent.llm_gateway import chat_completion


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
