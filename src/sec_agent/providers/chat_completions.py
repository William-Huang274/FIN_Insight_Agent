from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any, Mapping, Sequence
import urllib.error
import urllib.request
from urllib.parse import urlparse


CHAT_COMPLETION_PROFILE_SCHEMA_VERSION = (
    "fin_ia_chat_completion_provider_profile_v1_0"
)
CHAT_COMPLETION_CAPTURE_SCHEMA_VERSION = (
    "fin_ia_capture_first_chat_completion_v1_0"
)
CHAT_COMPLETION_TOOL_STEP_CAPTURE_SCHEMA_VERSION = (
    "fin_ia_capture_first_chat_completion_tool_step_v1_0"
)

_PRIVATE_REASONING_KEYS = frozenset(
    {"reasoning", "reasoning_content", "thinking", "thoughts"}
)
_SENSITIVE_KEYS = frozenset(
    {
        "authorization",
        "api_key",
        "apikey",
        "secret",
        "password",
        "cookie",
        "access_token",
        "refresh_token",
        "bearer_token",
    }
)
_REQUIRED_AUTHORITY = {
    "transport_attempt_ceiling": 1,
    "retry_count": 0,
    "capture_model_visible_request": True,
    "capture_assistant_output": True,
    "credential_capture_forbidden": True,
    "provider_private_reasoning_capture_forbidden": True,
    "provider_specific_profile_outside_core": True,
}


class ModelGatewayError(RuntimeError):
    """Typed failure for an exact-once provider call or its capture boundary."""

    def __init__(self, code: str, *, capture_ref: str = "") -> None:
        self.code = code
        self.capture_ref = capture_ref
        super().__init__(code)


def _require(condition: bool, code: str, *, capture_ref: str = "") -> None:
    if not condition:
        raise ModelGatewayError(code, capture_ref=capture_ref)


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _safe_identity(value: str, code: str) -> str:
    text = str(value or "").strip()
    _require(
        bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,159}", text)),
        code,
    )
    return text


def _path_slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")


def _contains_sensitive_key(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = str(key).casefold()
            if (
                normalized in _SENSITIVE_KEYS
                or normalized.endswith("_api_key")
                or normalized.endswith("_password")
                or normalized.endswith("_secret")
            ):
                return True
            if _contains_sensitive_key(item):
                return True
    elif isinstance(value, list):
        return any(_contains_sensitive_key(item) for item in value)
    return False


def _redact_private_reasoning(value: Any) -> tuple[Any, int]:
    if isinstance(value, Mapping):
        output: dict[str, Any] = {}
        redacted = 0
        for key, item in value.items():
            if str(key).casefold() in _PRIVATE_REASONING_KEYS:
                redacted += 1
                continue
            clean, count = _redact_private_reasoning(item)
            output[str(key)] = clean
            redacted += count
        return output, redacted
    if isinstance(value, list):
        output_list: list[Any] = []
        redacted = 0
        for item in value:
            clean, count = _redact_private_reasoning(item)
            output_list.append(clean)
            redacted += count
        return output_list, redacted
    return value, 0


def _write_new_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(
                value,
                handle,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            handle.write("\n")
    except FileExistsError as exc:
        raise ModelGatewayError(
            "model_gateway_exact_once_identity_consumed",
            capture_ref=path.as_posix(),
        ) from exc


@dataclass(frozen=True)
class ChatCompletionProfile:
    provider_id: str
    base_url: str
    endpoint: str
    model: str
    api_key_env: str
    timeout_seconds: int
    maximum_response_bytes: int
    request_defaults: Mapping[str, Any]
    authority: Mapping[str, Any]

    @property
    def url(self) -> str:
        return self.base_url.rstrip("/") + self.endpoint


@dataclass(frozen=True)
class ChatCompletionResult:
    status: str
    provider_id: str
    model: str
    content: str
    finish_reason: str
    usage: Mapping[str, Any]
    request_capture_ref: str
    response_capture_ref: str
    request_digest: str
    response_digest: str
    private_reasoning_fields_redacted: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "provider_id": self.provider_id,
            "model": self.model,
            "content": self.content,
            "finish_reason": self.finish_reason,
            "usage": dict(self.usage),
            "request_capture_ref": self.request_capture_ref,
            "response_capture_ref": self.response_capture_ref,
            "request_digest": self.request_digest,
            "response_digest": self.response_digest,
            "private_reasoning_fields_redacted": (
                self.private_reasoning_fields_redacted
            ),
        }


@dataclass(frozen=True)
class ChatCompletionToolStepResult:
    """One no-retry provider step in a bounded tool-use loop.

    ``reasoning_content`` is deliberately transient.  It is returned only so
    the caller can satisfy a provider's same-loop continuation protocol; it is
    excluded from ``as_dict`` and from every persisted capture.
    """

    status: str
    provider_id: str
    model: str
    content: str
    reasoning_content: str
    tool_calls: tuple[Mapping[str, Any], ...]
    finish_reason: str
    usage: Mapping[str, Any]
    request_capture_ref: str
    response_capture_ref: str
    request_digest: str
    response_digest: str
    private_reasoning_fields_redacted: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "provider_id": self.provider_id,
            "model": self.model,
            "content": self.content,
            "tool_calls": [dict(row) for row in self.tool_calls],
            "finish_reason": self.finish_reason,
            "usage": dict(self.usage),
            "request_capture_ref": self.request_capture_ref,
            "response_capture_ref": self.response_capture_ref,
            "request_digest": self.request_digest,
            "response_digest": self.response_digest,
            "private_reasoning_fields_redacted": (
                self.private_reasoning_fields_redacted
            ),
            "reasoning_content_persisted": False,
        }

    def continuation_assistant_message(self) -> dict[str, Any]:
        """Return the transient provider continuation message.

        The caller must keep this object in memory only.  It intentionally
        carries ``reasoning_content`` because DeepSeek thinking-mode tool
        loops reject a continuation that omits it.
        """

        message: dict[str, Any] = {
            "role": "assistant",
            "content": self.content,
        }
        if self.reasoning_content:
            message["reasoning_content"] = self.reasoning_content
        if self.tool_calls:
            message["tool_calls"] = [dict(row) for row in self.tool_calls]
        return message


def load_chat_completion_profile(
    payload: Mapping[str, Any],
) -> ChatCompletionProfile:
    expected_fields = {
        "schema_version",
        "status",
        "provider_id",
        "wire_api",
        "base_url",
        "endpoint",
        "model",
        "api_key_env",
        "timeout_seconds",
        "maximum_response_bytes",
        "request_defaults",
        "authority",
    }
    _require(set(payload) == expected_fields, "model_provider_profile_fields_invalid")
    _require(
        payload.get("schema_version") == CHAT_COMPLETION_PROFILE_SCHEMA_VERSION,
        "model_provider_profile_schema_invalid",
    )
    _require(
        payload.get("status")
        == "experimental_provider_profile_not_product_authority",
        "model_provider_profile_status_invalid",
    )
    _require(
        payload.get("wire_api") == "openai_compatible_chat_completions",
        "model_provider_profile_wire_api_invalid",
    )
    base_url = str(payload.get("base_url") or "").strip()
    parsed_url = urlparse(base_url)
    _require(
        parsed_url.scheme == "https" and bool(parsed_url.netloc),
        "model_provider_profile_https_required",
    )
    endpoint = str(payload.get("endpoint") or "").strip()
    _require(
        endpoint.startswith("/") and "?" not in endpoint,
        "model_provider_profile_endpoint_invalid",
    )
    defaults = payload.get("request_defaults")
    authority = payload.get("authority")
    _require(
        isinstance(defaults, Mapping)
        and not _contains_sensitive_key(defaults),
        "model_provider_profile_request_defaults_invalid",
    )
    _require(
        isinstance(authority, Mapping)
        and dict(authority) == _REQUIRED_AUTHORITY,
        "model_provider_profile_authority_invalid",
    )
    timeout_seconds = int(payload.get("timeout_seconds") or 0)
    maximum_response_bytes = int(payload.get("maximum_response_bytes") or 0)
    _require(
        1 <= timeout_seconds <= 600
        and 1024 <= maximum_response_bytes <= 10 * 1024 * 1024,
        "model_provider_profile_transport_budget_invalid",
    )
    provider_id = str(payload.get("provider_id") or "").strip()
    model = str(payload.get("model") or "").strip()
    api_key_env = str(payload.get("api_key_env") or "").strip()
    _require(
        bool(provider_id)
        and bool(model)
        and bool(re.fullmatch(r"[A-Z_][A-Z0-9_]*", api_key_env)),
        "model_provider_profile_identity_invalid",
    )
    return ChatCompletionProfile(
        provider_id=provider_id,
        base_url=base_url,
        endpoint=endpoint,
        model=model,
        api_key_env=api_key_env,
        timeout_seconds=timeout_seconds,
        maximum_response_bytes=maximum_response_bytes,
        request_defaults=dict(defaults),
        authority=dict(authority),
    )


def _normalize_tool_call(
    value: object,
    *,
    code: str,
    capture_ref: str = "",
) -> dict[str, Any]:
    _require(isinstance(value, Mapping), code, capture_ref=capture_ref)
    assert isinstance(value, Mapping)
    function = value.get("function")
    allowed_fields = {"id", "type", "function"}
    if "index" in value:
        index = value.get("index")
        _require(
            isinstance(index, int)
            and not isinstance(index, bool)
            and 0 <= index <= 1_000_000,
            "model_gateway_tool_call_index_invalid",
            capture_ref=capture_ref,
        )
        allowed_fields.add("index")
    _require(
        set(value) == allowed_fields
        and value.get("type") == "function"
        and isinstance(function, Mapping),
        code,
        capture_ref=capture_ref,
    )
    assert isinstance(function, Mapping)
    name = str(function.get("name") or "").strip()
    arguments = str(function.get("arguments") or "")
    _require(
        set(function) == {"name", "arguments"}
        and bool(name)
        and bool(arguments)
        and bool(str(value.get("id") or "").strip()),
        code,
        capture_ref=capture_ref,
    )
    return {
        "id": str(value["id"]),
        "type": "function",
        "function": {"name": name, "arguments": arguments},
    }


def normalize_chat_completion_tool_calls(
    value: object,
    *,
    code: str = "model_gateway_tool_calls_invalid",
    call_code: str = "model_gateway_tool_call_invalid",
    capture_ref: str = "",
) -> tuple[dict[str, Any], ...]:
    """Normalize one non-stream tool-call array into the provider-neutral form.

    OpenAI-compatible providers may attach a positional ``index`` to each
    tool call.  It is a wire-order field, not financial or tool authority, so
    this boundary validates a complete zero-based sequence and strips it.
    Unknown fields still fail closed.
    """

    _require(isinstance(value, list), code, capture_ref=capture_ref)
    assert isinstance(value, list)
    present = [
        isinstance(row, Mapping) and "index" in row for row in value
    ]
    _require(
        not any(present) or all(present),
        "model_gateway_tool_call_index_invalid",
        capture_ref=capture_ref,
    )
    if present and all(present):
        indexes = [
            row.get("index") if isinstance(row, Mapping) else None
            for row in value
        ]
        _require(
            indexes == list(range(len(value))),
            "model_gateway_tool_call_index_invalid",
            capture_ref=capture_ref,
        )
    return tuple(
        _normalize_tool_call(
            row,
            code=call_code,
            capture_ref=capture_ref,
        )
        for row in value
    )


def _normalize_tool_loop_messages(
    messages: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    _require(bool(messages), "model_gateway_messages_missing")
    normalized: list[dict[str, Any]] = []
    for raw in messages:
        _require(isinstance(raw, Mapping), "model_gateway_messages_invalid")
        role = str(raw.get("role") or "")
        if role in {"system", "user"}:
            content = str(raw.get("content") or "")
            _require(
                set(raw) == {"role", "content"} and bool(content),
                "model_gateway_messages_invalid",
            )
            normalized.append({"role": role, "content": content})
            continue
        if role == "assistant":
            _require(
                set(raw).issubset(
                    {"role", "content", "reasoning_content", "tool_calls"}
                ),
                "model_gateway_messages_invalid",
            )
            content = str(raw.get("content") or "")
            reasoning = str(raw.get("reasoning_content") or "")
            raw_calls = raw.get("tool_calls") or []
            _require(
                isinstance(raw_calls, list),
                "model_gateway_messages_invalid",
            )
            calls = list(
                normalize_chat_completion_tool_calls(
                    raw_calls,
                    code="model_gateway_messages_invalid",
                    call_code="model_gateway_message_tool_call_invalid",
                )
            )
            _require(
                bool(content or calls),
                "model_gateway_messages_invalid",
            )
            message: dict[str, Any] = {
                "role": "assistant",
                "content": content,
            }
            if reasoning:
                message["reasoning_content"] = reasoning
            if calls:
                message["tool_calls"] = calls
            normalized.append(message)
            continue
        if role == "tool":
            content = str(raw.get("content") or "")
            call_id = str(raw.get("tool_call_id") or "").strip()
            _require(
                set(raw) == {"role", "tool_call_id", "content"}
                and bool(call_id)
                and bool(content),
                "model_gateway_messages_invalid",
            )
            normalized.append(
                {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": content,
                }
            )
            continue
        raise ModelGatewayError("model_gateway_messages_invalid")
    return normalized


def _normalize_tool_definitions(
    tools: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    _require(
        bool(tools) and len(tools) <= 16,
        "model_gateway_tools_invalid",
    )
    normalized: list[dict[str, Any]] = []
    names: set[str] = set()
    for raw in tools:
        _require(
            isinstance(raw, Mapping)
            and set(raw) == {"type", "function"}
            and raw.get("type") == "function",
            "model_gateway_tool_invalid",
        )
        function = raw.get("function")
        _require(
            isinstance(function, Mapping),
            "model_gateway_tool_invalid",
        )
        assert isinstance(function, Mapping)
        _require(
            set(function).issubset(
                {"name", "description", "parameters", "strict"}
            )
            and {"name", "description", "parameters"}.issubset(function),
            "model_gateway_tool_invalid",
        )
        name = str(function.get("name") or "").strip()
        parameters = function.get("parameters")
        _require(
            bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", name))
            and name not in names
            and isinstance(parameters, Mapping)
            and not _contains_sensitive_key(function),
            "model_gateway_tool_invalid",
        )
        names.add(name)
        normalized.append(
            {
                "type": "function",
                "function": dict(function),
            }
        )
    return normalized


def _redact_transient_request_reasoning(
    request_body: Mapping[str, Any],
) -> tuple[dict[str, Any], int]:
    output = dict(request_body)
    messages = []
    redacted = 0
    for raw in request_body.get("messages") or ():
        row = dict(raw)
        if "reasoning_content" in row:
            row.pop("reasoning_content")
            redacted += 1
        messages.append(row)
    output["messages"] = messages
    return output, redacted


def _empty_completion_failure_code(
    *,
    response_body: Mapping[str, Any],
    choice: Mapping[str, Any],
    request_body: Mapping[str, Any],
    fallback_code: str,
) -> str:
    """Distinguish an empty answer from a consumed generation budget.

    DeepSeek thinking tokens share ``max_tokens`` with the visible answer.  A
    response can therefore be HTTP 200 yet contain no final content or tool
    call when reasoning consumes the entire allowance.  Preserve that as a
    typed capacity failure instead of misreporting it as generic empty output.
    """

    if str(choice.get("finish_reason") or "") != "length":
        return fallback_code
    usage = response_body.get("usage")
    maximum = request_body.get("max_tokens")
    if not isinstance(usage, Mapping) or not isinstance(maximum, int):
        return "model_gateway_generation_budget_exhausted"
    completion = usage.get("completion_tokens")
    details = usage.get("completion_tokens_details")
    reasoning = details.get("reasoning_tokens") if isinstance(details, Mapping) else 0
    if (
        isinstance(completion, int)
        and isinstance(reasoning, int)
        and completion >= maximum
        and reasoning >= maximum
    ):
        return "model_gateway_reasoning_budget_exhausted"
    return "model_gateway_generation_budget_exhausted"


def _execute_capture_first_request(
    *,
    profile: ChatCompletionProfile,
    request_body: Mapping[str, Any],
    persisted_request_body: Mapping[str, Any],
    capture_dir: Path,
    run_id: str,
    attempt_id: str,
    capture_schema_version: str,
    capture_type: str,
    transient_request_reasoning_fields_redacted: int,
) -> tuple[str, Path, Path, dict[str, Any], Any]:
    """Send one request after persisting its credential-free audit view."""

    api_key = os.environ.get(profile.api_key_env, "").strip()
    _require(bool(api_key), "model_gateway_credential_absent")
    _require(
        not _contains_sensitive_key(request_body)
        and not _contains_sensitive_key(persisted_request_body),
        "model_gateway_request_contains_sensitive_key",
    )
    request_digest = _digest(request_body)
    request_ref = capture_dir / "model_visible_request.json"
    response_ref = capture_dir / "provider_response.json"
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    _write_new_json(
        request_ref,
        {
            "schema_version": capture_schema_version,
            "capture_type": capture_type,
            "captured_at": now,
            "run_id": run_id,
            "attempt_id": attempt_id,
            "provider_id": profile.provider_id,
            "model": profile.model,
            "url": profile.url,
            "transport_attempt_ceiling": 1,
            "request_body": dict(persisted_request_body),
            "request_digest": request_digest,
            "transient_private_reasoning_fields_redacted": (
                transient_request_reasoning_fields_redacted
            ),
            "credential_or_authorization_captured": False,
        },
    )
    encoded = _canonical_bytes(request_body)
    request = urllib.request.Request(
        profile.url,
        data=encoded,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "FIN-Insight-Agent/0.1.3",
        },
    )
    try:
        with urllib.request.urlopen(
            request,
            timeout=profile.timeout_seconds,
        ) as response:
            status_code = int(getattr(response, "status", 200))
            raw = response.read(profile.maximum_response_bytes + 1)
            content_type = str(response.headers.get("Content-Type") or "")
            provider_request_id = str(
                response.headers.get("x-request-id")
                or response.headers.get("x-ds-request-id")
                or ""
            )
    except urllib.error.HTTPError as exc:
        raw = exc.read(profile.maximum_response_bytes + 1)
        _persist_response_capture(
            response_ref=response_ref,
            run_id=run_id,
            attempt_id=attempt_id,
            provider_id=profile.provider_id,
            model=profile.model,
            status_code=int(exc.code),
            content_type=str(exc.headers.get("Content-Type") or ""),
            provider_request_id=str(exc.headers.get("x-request-id") or ""),
            raw=raw,
            maximum_response_bytes=profile.maximum_response_bytes,
            transport_error="",
        )
        raise ModelGatewayError(
            f"model_gateway_http_error:{exc.code}",
            capture_ref=response_ref.as_posix(),
        ) from exc
    except Exception as exc:
        _persist_response_capture(
            response_ref=response_ref,
            run_id=run_id,
            attempt_id=attempt_id,
            provider_id=profile.provider_id,
            model=profile.model,
            status_code=0,
            content_type="",
            provider_request_id="",
            raw=b"",
            maximum_response_bytes=profile.maximum_response_bytes,
            transport_error=type(exc).__name__,
        )
        raise ModelGatewayError(
            "model_gateway_transport_error",
            capture_ref=response_ref.as_posix(),
        ) from exc
    try:
        transient_body: Any = (
            json.loads(raw[: profile.maximum_response_bytes].decode("utf-8"))
            if raw
            else {}
        )
    except (UnicodeDecodeError, json.JSONDecodeError):
        transient_body = raw[: profile.maximum_response_bytes].decode(
            "utf-8", errors="replace"
        )
    capture = _persist_response_capture(
        response_ref=response_ref,
        run_id=run_id,
        attempt_id=attempt_id,
        provider_id=profile.provider_id,
        model=profile.model,
        status_code=status_code,
        content_type=content_type,
        provider_request_id=provider_request_id,
        raw=raw,
        maximum_response_bytes=profile.maximum_response_bytes,
        transport_error="",
    )
    return (
        request_digest,
        request_ref,
        response_ref,
        capture,
        transient_body,
    )


def execute_chat_completion_exact_once(
    *,
    profile: ChatCompletionProfile,
    messages: Sequence[Mapping[str, str]],
    capture_root: str | Path,
    run_id: str,
    attempt_id: str,
) -> ChatCompletionResult:
    """Execute one no-retry call after persisting the model-visible request."""

    normalized_run_id = _safe_identity(run_id, "model_gateway_run_id_invalid")
    normalized_attempt_id = _safe_identity(
        attempt_id, "model_gateway_attempt_id_invalid"
    )
    _require(bool(messages), "model_gateway_messages_missing")
    normalized_messages = [
        {"role": str(row.get("role") or ""), "content": str(row.get("content") or "")}
        for row in messages
    ]
    _require(
        all(
            row["role"] in {"system", "user", "assistant"}
            and row["content"]
            for row in normalized_messages
        ),
        "model_gateway_messages_invalid",
    )
    api_key = os.environ.get(profile.api_key_env, "").strip()
    _require(bool(api_key), "model_gateway_credential_absent")
    request_body = {
        "model": profile.model,
        "messages": normalized_messages,
        **dict(profile.request_defaults),
    }
    _require(
        not _contains_sensitive_key(request_body),
        "model_gateway_request_contains_sensitive_key",
    )
    request_digest = _digest(request_body)
    capture_dir = (
        Path(capture_root).resolve()
        / _path_slug(normalized_run_id)
        / _path_slug(normalized_attempt_id)
    )
    request_ref = capture_dir / "model_visible_request.json"
    response_ref = capture_dir / "provider_response.json"
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    _write_new_json(
        request_ref,
        {
            "schema_version": CHAT_COMPLETION_CAPTURE_SCHEMA_VERSION,
            "capture_type": "model_visible_request_without_credentials",
            "captured_at": now,
            "run_id": normalized_run_id,
            "attempt_id": normalized_attempt_id,
            "provider_id": profile.provider_id,
            "model": profile.model,
            "url": profile.url,
            "transport_attempt_ceiling": 1,
            "request_body": request_body,
            "request_digest": request_digest,
            "credential_or_authorization_captured": False,
        },
    )
    encoded = _canonical_bytes(request_body)
    request = urllib.request.Request(
        profile.url,
        data=encoded,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "FIN-Insight-Agent/0.1.3",
        },
    )
    try:
        with urllib.request.urlopen(
            request,
            timeout=profile.timeout_seconds,
        ) as response:
            status_code = int(getattr(response, "status", 200))
            raw = response.read(profile.maximum_response_bytes + 1)
            content_type = str(response.headers.get("Content-Type") or "")
            provider_request_id = str(
                response.headers.get("x-request-id")
                or response.headers.get("x-ds-request-id")
                or ""
            )
    except urllib.error.HTTPError as exc:
        raw = exc.read(profile.maximum_response_bytes + 1)
        _persist_response_capture(
            response_ref=response_ref,
            run_id=normalized_run_id,
            attempt_id=normalized_attempt_id,
            provider_id=profile.provider_id,
            model=profile.model,
            status_code=int(exc.code),
            content_type=str(exc.headers.get("Content-Type") or ""),
            provider_request_id=str(exc.headers.get("x-request-id") or ""),
            raw=raw,
            maximum_response_bytes=profile.maximum_response_bytes,
            transport_error="",
        )
        raise ModelGatewayError(
            f"model_gateway_http_error:{exc.code}",
            capture_ref=response_ref.as_posix(),
        ) from exc
    except Exception as exc:
        _persist_response_capture(
            response_ref=response_ref,
            run_id=normalized_run_id,
            attempt_id=normalized_attempt_id,
            provider_id=profile.provider_id,
            model=profile.model,
            status_code=0,
            content_type="",
            provider_request_id="",
            raw=b"",
            maximum_response_bytes=profile.maximum_response_bytes,
            transport_error=type(exc).__name__,
        )
        raise ModelGatewayError(
            "model_gateway_transport_error",
            capture_ref=response_ref.as_posix(),
        ) from exc
    capture = _persist_response_capture(
        response_ref=response_ref,
        run_id=normalized_run_id,
        attempt_id=normalized_attempt_id,
        provider_id=profile.provider_id,
        model=profile.model,
        status_code=status_code,
        content_type=content_type,
        provider_request_id=provider_request_id,
        raw=raw,
        maximum_response_bytes=profile.maximum_response_bytes,
        transport_error="",
    )
    if capture["truncated"]:
        raise ModelGatewayError(
            "model_gateway_response_too_large",
            capture_ref=response_ref.as_posix(),
        )
    body = capture["response_body"]
    capture_ref = response_ref.as_posix()
    _require(
        isinstance(body, Mapping),
        "model_gateway_response_json_invalid",
        capture_ref=capture_ref,
    )
    choices = body.get("choices")
    _require(
        isinstance(choices, list) and len(choices) == 1,
        "model_gateway_choice_count_invalid",
        capture_ref=capture_ref,
    )
    choice = choices[0]
    _require(
        isinstance(choice, Mapping),
        "model_gateway_choice_invalid",
        capture_ref=capture_ref,
    )
    message = choice.get("message")
    _require(
        isinstance(message, Mapping),
        "model_gateway_message_invalid",
        capture_ref=capture_ref,
    )
    content = str(message.get("content") or "")
    if not content.strip():
        raise ModelGatewayError(
            _empty_completion_failure_code(
                response_body=body,
                choice=choice,
                request_body=request_body,
                fallback_code="model_gateway_content_empty",
            ),
            capture_ref=capture_ref,
        )
    usage = body.get("usage") if isinstance(body.get("usage"), Mapping) else {}
    return ChatCompletionResult(
        status="completed_exact_once",
        provider_id=profile.provider_id,
        model=profile.model,
        content=content,
        finish_reason=str(choice.get("finish_reason") or ""),
        usage=dict(usage),
        request_capture_ref=request_ref.as_posix(),
        response_capture_ref=response_ref.as_posix(),
        request_digest=request_digest,
        response_digest=str(capture["response_digest"]),
        private_reasoning_fields_redacted=int(
            capture["private_reasoning_fields_redacted"]
        ),
    )


def execute_chat_completion_tool_step_exact_once(
    *,
    profile: ChatCompletionProfile,
    messages: Sequence[Mapping[str, Any]],
    tools: Sequence[Mapping[str, Any]],
    capture_root: str | Path,
    run_id: str,
    attempt_id: str,
    tool_choice: object | None = None,
) -> ChatCompletionToolStepResult:
    """Execute one capture-first step of a caller-bounded tool loop.

    This function owns no loop, tool budget, or financial authority.  It only
    preserves the wire fields required for a provider continuation while
    keeping private reasoning out of persistent captures and result ledgers.
    """

    normalized_run_id = _safe_identity(run_id, "model_gateway_run_id_invalid")
    normalized_attempt_id = _safe_identity(
        attempt_id, "model_gateway_attempt_id_invalid"
    )
    normalized_messages = _normalize_tool_loop_messages(messages)
    normalized_tools = _normalize_tool_definitions(tools)
    defaults = dict(profile.request_defaults)
    _require(
        not set(defaults).intersection({"model", "messages", "tools"})
        and defaults.get("stream") is not True,
        "model_gateway_tool_step_defaults_invalid",
    )
    request_body: dict[str, Any] = {
        "model": profile.model,
        "messages": normalized_messages,
        "tools": normalized_tools,
        **defaults,
    }
    if tool_choice is not None:
        _require(
            isinstance(tool_choice, (str, Mapping)),
            "model_gateway_tool_choice_invalid",
        )
        request_body["tool_choice"] = (
            dict(tool_choice)
            if isinstance(tool_choice, Mapping)
            else str(tool_choice)
        )
    persisted_request, request_reasoning_redacted = (
        _redact_transient_request_reasoning(request_body)
    )
    capture_dir = (
        Path(capture_root).resolve()
        / _path_slug(normalized_run_id)
        / _path_slug(normalized_attempt_id)
    )
    (
        request_digest,
        request_ref,
        response_ref,
        capture,
        transient_body,
    ) = _execute_capture_first_request(
        profile=profile,
        request_body=request_body,
        persisted_request_body=persisted_request,
        capture_dir=capture_dir,
        run_id=normalized_run_id,
        attempt_id=normalized_attempt_id,
        capture_schema_version=(
            CHAT_COMPLETION_TOOL_STEP_CAPTURE_SCHEMA_VERSION
        ),
        capture_type=(
            "model_visible_tool_step_request_without_credentials_or_reasoning"
        ),
        transient_request_reasoning_fields_redacted=(
            request_reasoning_redacted
        ),
    )
    capture_ref = response_ref.as_posix()
    _require(
        not capture["truncated"],
        "model_gateway_response_too_large",
        capture_ref=capture_ref,
    )
    _require(
        isinstance(transient_body, Mapping),
        "model_gateway_response_json_invalid",
        capture_ref=capture_ref,
    )
    assert isinstance(transient_body, Mapping)
    choices = transient_body.get("choices")
    _require(
        isinstance(choices, list) and len(choices) == 1,
        "model_gateway_choice_count_invalid",
        capture_ref=capture_ref,
    )
    choice = choices[0]
    _require(
        isinstance(choice, Mapping),
        "model_gateway_choice_invalid",
        capture_ref=capture_ref,
    )
    assert isinstance(choice, Mapping)
    message = choice.get("message")
    _require(
        isinstance(message, Mapping),
        "model_gateway_message_invalid",
        capture_ref=capture_ref,
    )
    assert isinstance(message, Mapping)
    content = str(message.get("content") or "")
    reasoning_content = str(message.get("reasoning_content") or "")
    raw_calls = message.get("tool_calls") or []
    _require(
        isinstance(raw_calls, list),
        "model_gateway_tool_calls_invalid",
        capture_ref=capture_ref,
    )
    tool_calls = normalize_chat_completion_tool_calls(
        raw_calls,
        capture_ref=capture_ref,
    )
    if not content.strip() and not tool_calls:
        raise ModelGatewayError(
            _empty_completion_failure_code(
                response_body=transient_body,
                choice=choice,
                request_body=request_body,
                fallback_code="model_gateway_tool_step_empty",
            ),
            capture_ref=capture_ref,
        )
    usage = (
        transient_body.get("usage")
        if isinstance(transient_body.get("usage"), Mapping)
        else {}
    )
    return ChatCompletionToolStepResult(
        status="completed_exact_once_tool_step",
        provider_id=profile.provider_id,
        model=profile.model,
        content=content,
        reasoning_content=reasoning_content,
        tool_calls=tool_calls,
        finish_reason=str(choice.get("finish_reason") or ""),
        usage=dict(usage),
        request_capture_ref=request_ref.as_posix(),
        response_capture_ref=response_ref.as_posix(),
        request_digest=request_digest,
        response_digest=str(capture["response_digest"]),
        private_reasoning_fields_redacted=int(
            capture["private_reasoning_fields_redacted"]
        ),
    )


def _persist_response_capture(
    *,
    response_ref: Path,
    run_id: str,
    attempt_id: str,
    provider_id: str,
    model: str,
    status_code: int,
    content_type: str,
    provider_request_id: str,
    raw: bytes,
    maximum_response_bytes: int,
    transport_error: str,
) -> dict[str, Any]:
    truncated = len(raw) > maximum_response_bytes
    admitted_raw = raw[:maximum_response_bytes]
    try:
        parsed: Any = json.loads(admitted_raw.decode("utf-8")) if admitted_raw else {}
    except (UnicodeDecodeError, json.JSONDecodeError):
        parsed = admitted_raw.decode("utf-8", errors="replace")
    cleaned, redacted = _redact_private_reasoning(parsed)
    response_digest = _digest(cleaned)
    capture = {
        "schema_version": CHAT_COMPLETION_CAPTURE_SCHEMA_VERSION,
        "capture_type": "provider_response_private_reasoning_redacted",
        "captured_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "run_id": run_id,
        "attempt_id": attempt_id,
        "provider_id": provider_id,
        "model": model,
        "status_code": status_code,
        "content_type": content_type,
        "provider_request_id": provider_request_id,
        "response_body": cleaned,
        "response_digest": response_digest,
        "truncated": truncated,
        "transport_error": transport_error,
        "private_reasoning_fields_redacted": redacted,
        "credential_or_authorization_captured": False,
    }
    _write_new_json(response_ref, capture)
    return capture


__all__ = [
    "CHAT_COMPLETION_CAPTURE_SCHEMA_VERSION",
    "CHAT_COMPLETION_PROFILE_SCHEMA_VERSION",
    "CHAT_COMPLETION_TOOL_STEP_CAPTURE_SCHEMA_VERSION",
    "ChatCompletionProfile",
    "ChatCompletionResult",
    "ChatCompletionToolStepResult",
    "ModelGatewayError",
    "execute_chat_completion_exact_once",
    "execute_chat_completion_tool_step_exact_once",
    "load_chat_completion_profile",
    "normalize_chat_completion_tool_calls",
]
