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
    req = urllib.request.Request(
        _chat_completions_url(base_url, chat_completions_path),
        data=request_body,
        headers=headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            response_text = resp.read().decode("utf-8")
            parsed = json.loads(response_text)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return _error_result(
            started=started,
            status="provider_error",
            backend=backend,
            model=model,
            role=role,
            profile=profile,
            trace_tags=trace_tags,
            failure_reason=f"HTTP {exc.code}: {body[:1000]}",
        )
    except Exception as exc:
        return _error_result(
            started=started,
            status="timeout" if "timed out" in str(exc).lower() else "provider_error",
            backend=backend,
            model=model,
            role=role,
            profile=profile,
            trace_tags=trace_tags,
            failure_reason=f"{type(exc).__name__}: {str(exc)[:1000]}",
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
