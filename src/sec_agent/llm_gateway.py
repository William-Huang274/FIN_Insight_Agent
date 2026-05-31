from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from typing import Any


class LLMGatewayError(RuntimeError):
    """Raised when a model gateway call fails before usable content is returned."""


def chat_completion(
    *,
    llm_backend: str,
    base_url: str,
    chat_completions_path: str,
    model: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    tool_choice: str | dict[str, Any] | None = None,
    parallel_tool_calls: bool | None = None,
    response_format: dict[str, Any] | None = None,
    api_key_env: str = "",
    temperature: float = 0.0,
    max_tokens: int = 1024,
    timeout_s: int = 180,
    stream: bool = False,
    enable_thinking: bool = False,
    reasoning_effort: str = "",
    role: str = "",
    profile: str = "",
    trace_tags: dict[str, Any] | None = None,
) -> dict[str, Any]:
    started = time.time()
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": stream,
    }
    if tools is not None:
        payload["tools"] = tools
    if tool_choice is not None:
        payload["tool_choice"] = tool_choice
    if parallel_tool_calls is not None:
        payload["parallel_tool_calls"] = bool(parallel_tool_calls)
    if response_format is not None:
        payload["response_format"] = response_format
    headers = {"Content-Type": "application/json"}
    backend = str(llm_backend or "").strip()

    if backend == "qwen_vllm":
        payload["chat_template_kwargs"] = {"enable_thinking": False}
    else:
        api_key = os.environ.get(str(api_key_env or ""), "") if api_key_env else ""
        if not api_key:
            return _error_result(
                started=started,
                status="provider_error",
                backend=backend,
                model=model,
                role=role,
                profile=profile,
                trace_tags=trace_tags,
                failure_reason=f"{backend} backend requires API key env var: {api_key_env or '<unset>'}",
            )
        headers["Authorization"] = f"Bearer {api_key}"
        if backend == "deepseek":
            if enable_thinking and reasoning_effort:
                payload["reasoning_effort"] = reasoning_effort
            payload["thinking"] = {"type": "enabled" if enable_thinking else "disabled"}
        elif enable_thinking and reasoning_effort:
            payload["reasoning_effort"] = reasoning_effort

    request_body = json.dumps(_clean_json_value(payload), ensure_ascii=False).encode("utf-8")
    url = _chat_completions_url(base_url, chat_completions_path)
    transport_failures: list[dict[str, Any]] = []
    max_transport_retries = max(0, _int_env(os.environ.get("LLM_GATEWAY_TRANSPORT_RETRIES"), default=1))
    max_attempts = max_transport_retries + 1
    parsed: dict[str, Any] | None = None
    transport_attempt_count = 0
    for attempt_index in range(max_attempts):
        transport_attempt_count = attempt_index + 1
        try:
            req = urllib.request.Request(url, data=request_body, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                response_text = resp.read().decode("utf-8")
                parsed = json.loads(response_text)
            break
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            failure_reason = f"HTTP {exc.code}: {body[:1000]}"
            if _should_retry_http_status(exc.code) and attempt_index < max_attempts - 1:
                transport_failures.append(
                    {
                        "attempt": transport_attempt_count,
                        "status": "provider_error",
                        "reason": failure_reason[:500],
                    }
                )
                _sleep_before_retry(attempt_index)
                continue
            return _error_result(
                started=started,
                status="provider_error",
                backend=backend,
                model=model,
                role=role,
                profile=profile,
                trace_tags=trace_tags,
                failure_reason=failure_reason,
                transport_attempt_count=transport_attempt_count,
                transport_failures=transport_failures,
            )
        except Exception as exc:
            failure_reason = f"{type(exc).__name__}: {str(exc)[:1000]}"
            status = "timeout" if "timed out" in str(exc).lower() else "provider_error"
            if _should_retry_transport_exception(exc) and attempt_index < max_attempts - 1:
                transport_failures.append(
                    {
                        "attempt": transport_attempt_count,
                        "status": status,
                        "reason": failure_reason[:500],
                    }
                )
                _sleep_before_retry(attempt_index)
                continue
            return _error_result(
                started=started,
                status=status,
                backend=backend,
                model=model,
                role=role,
                profile=profile,
                trace_tags=trace_tags,
                failure_reason=failure_reason,
                transport_attempt_count=transport_attempt_count,
                transport_failures=transport_failures,
            )
    if parsed is None:
        return _error_result(
            started=started,
            status="provider_error",
            backend=backend,
            model=model,
            role=role,
            profile=profile,
            trace_tags=trace_tags,
            failure_reason="LLM transport returned no response.",
            transport_attempt_count=transport_attempt_count,
            transport_failures=transport_failures,
        )

    choices = parsed.get("choices") or []
    if not choices:
        return _error_result(
            started=started,
            status="schema_failed",
            backend=backend,
            model=model,
            role=role,
            profile=profile,
            trace_tags=trace_tags,
            failure_reason=f"LLM returned no choices: {json.dumps(parsed, ensure_ascii=False)[:1000]}",
            raw_response=parsed,
        )
    choice = choices[0]
    message = choice.get("message") or {}
    content = str(message.get("content") or "")
    tool_calls = message.get("tool_calls") or []
    return {
        "status": "ok",
        "provider": backend,
        "model": model,
        "role": role,
        "profile": profile,
        "content": content,
        "message": message,
        "tool_calls": tool_calls if isinstance(tool_calls, list) else [],
        "finish_reason": choice.get("finish_reason"),
        "latency_ms": int((time.time() - started) * 1000),
        "input_tokens": _usage_int(parsed, "prompt_tokens"),
        "output_tokens": _usage_int(parsed, "completion_tokens"),
        "total_tokens": _usage_int(parsed, "total_tokens"),
        "cost_estimate": None,
        "failure_reason": "",
        "trace_tags": trace_tags or {},
        "transport_attempt_count": transport_attempt_count,
        "transport_failures": transport_failures,
        "raw_response": parsed,
    }


def chat_completion_content(**kwargs: Any) -> tuple[str, dict[str, Any]]:
    result = chat_completion(**kwargs)
    if result.get("status") != "ok":
        raise LLMGatewayError(str(result.get("failure_reason") or result.get("status") or "llm_gateway_error"))
    return str(result.get("content") or ""), result


def _chat_completions_url(base_url: str, chat_completions_path: str) -> str:
    path = str(chat_completions_path or "").strip() or "/v1/chat/completions"
    if not path.startswith("/"):
        path = "/" + path
    return str(base_url or "").rstrip("/") + path


def _usage_int(parsed: dict[str, Any], key: str) -> int | None:
    usage = parsed.get("usage") if isinstance(parsed, dict) else None
    if not isinstance(usage, dict):
        return None
    try:
        return int(usage.get(key))
    except Exception:
        return None


def _error_result(
    *,
    started: float,
    status: str,
    backend: str,
    model: str,
    role: str,
    profile: str,
    trace_tags: dict[str, Any] | None,
    failure_reason: str,
    raw_response: dict[str, Any] | None = None,
    transport_attempt_count: int = 1,
    transport_failures: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "status": status,
        "provider": backend,
        "model": model,
        "role": role,
        "profile": profile,
        "content": "",
        "message": {},
        "tool_calls": [],
        "finish_reason": None,
        "latency_ms": int((time.time() - started) * 1000),
        "input_tokens": None,
        "output_tokens": None,
        "total_tokens": None,
        "cost_estimate": None,
        "failure_reason": failure_reason,
        "trace_tags": trace_tags or {},
        "transport_attempt_count": transport_attempt_count,
        "transport_failures": transport_failures or [],
        "raw_response": raw_response or {},
    }


def _clean_json_value(value: Any) -> Any:
    if isinstance(value, str):
        return re.sub("[\ud800-\udfff]", "", value)
    if isinstance(value, list):
        return [_clean_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _clean_json_value(item) for key, item in value.items()}
    return value


def _int_env(value: str | None, *, default: int) -> int:
    try:
        return int(value) if value not in {None, ""} else default
    except (TypeError, ValueError):
        return default


def _float_env(value: str | None, *, default: float) -> float:
    try:
        return float(value) if value not in {None, ""} else default
    except (TypeError, ValueError):
        return default


def _should_retry_http_status(status_code: int) -> bool:
    return int(status_code) in {408, 409, 425, 429, 500, 502, 503, 504}


def _should_retry_transport_exception(exc: Exception) -> bool:
    if isinstance(exc, ValueError) and "unknown url type" in str(exc).lower():
        return False
    return True


def _sleep_before_retry(attempt_index: int) -> None:
    base = max(0.0, _float_env(os.environ.get("LLM_GATEWAY_TRANSPORT_RETRY_BACKOFF_S"), default=2.0))
    cap = max(base, _float_env(os.environ.get("LLM_GATEWAY_TRANSPORT_RETRY_MAX_BACKOFF_S"), default=12.0))
    delay = min(cap, base * (2 ** max(0, attempt_index)))
    if delay > 0:
        time.sleep(delay)
