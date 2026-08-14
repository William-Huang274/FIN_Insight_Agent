from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .agent_protocol import (
    CHAT_COMPLETIONS_WIRE,
    RESPONSES_WIRE,
    AgentTransportProfile,
    canonicalize_tool_definitions,
    compile_agent_request_projection,
)
from .chat_completions import (
    ModelGatewayError,
    _execute_capture_first_request,
    _path_slug,
    _safe_identity,
)


RESPONSES_TOOL_STEP_CAPTURE_SCHEMA_VERSION = (
    "fin_ia_capture_first_responses_tool_step_v1_0"
)


def _require(condition: bool, code: str, *, capture_ref: str = "") -> None:
    if not condition:
        raise ModelGatewayError(code, capture_ref=capture_ref)


def _redact_transient_responses_input(
    request_body: Mapping[str, Any],
) -> tuple[dict[str, Any], int]:
    output = deepcopy(dict(request_body))
    redacted = 0
    clean_items: list[Any] = []
    for raw in output.get("input") or ():
        if isinstance(raw, Mapping) and raw.get("type") == "reasoning":
            clean_items.append(
                {"type": "reasoning", "private_reasoning_redacted": True}
            )
            redacted += 1
        else:
            clean_items.append(raw)
    output["input"] = clean_items
    return output, redacted


def _normalize_responses_output(
    body: Mapping[str, Any],
    *,
    capture_ref: str,
) -> tuple[str, tuple[dict[str, Any], ...], tuple[dict[str, Any], ...]]:
    raw_output = body.get("output")
    _require(
        isinstance(raw_output, list),
        "responses_gateway_output_invalid",
        capture_ref=capture_ref,
    )
    text_parts: list[str] = []
    calls: list[dict[str, Any]] = []
    continuation: list[dict[str, Any]] = []
    for raw in raw_output:
        _require(
            isinstance(raw, Mapping),
            "responses_gateway_output_item_invalid",
            capture_ref=capture_ref,
        )
        assert isinstance(raw, Mapping)
        item = deepcopy(dict(raw))
        item_type = str(item.get("type") or "")
        if item_type == "message":
            content = item.get("content")
            if isinstance(content, str):
                if content:
                    text_parts.append(content)
            else:
                _require(
                    isinstance(content, list),
                    "responses_gateway_message_content_invalid",
                    capture_ref=capture_ref,
                )
                for part in content:
                    _require(
                        isinstance(part, Mapping),
                        "responses_gateway_message_content_invalid",
                        capture_ref=capture_ref,
                    )
                    part_type = str(part.get("type") or "")
                    if part_type in {"output_text", "text"}:
                        text = str(part.get("text") or "")
                        if text:
                            text_parts.append(text)
                    elif part_type not in {"refusal"}:
                        raise ModelGatewayError(
                            "responses_gateway_message_content_type_unsupported",
                            capture_ref=capture_ref,
                        )
            continuation.append(item)
            continue
        if item_type == "function_call":
            call_id = str(item.get("call_id") or item.get("id") or "").strip()
            name = str(item.get("name") or "").strip()
            arguments = str(item.get("arguments") or "")
            _require(
                bool(call_id and name and arguments),
                "responses_gateway_function_call_invalid",
                capture_ref=capture_ref,
            )
            calls.append(
                {
                    "id": call_id,
                    "type": "function",
                    "function": {"name": name, "arguments": arguments},
                }
            )
            continuation.append(item)
            continue
        if item_type == "reasoning":
            continuation.append(item)
            continue
        raise ModelGatewayError(
            "responses_gateway_unexpected_server_side_tool_or_output",
            capture_ref=capture_ref,
        )
    return "\n".join(text_parts), tuple(calls), tuple(continuation)


@dataclass(frozen=True)
class ResponsesToolStepResult:
    status: str
    provider_id: str
    model: str
    content: str
    tool_calls: tuple[Mapping[str, Any], ...]
    finish_reason: str
    usage: Mapping[str, Any]
    request_capture_ref: str
    response_capture_ref: str
    request_digest: str
    response_digest: str
    private_reasoning_fields_redacted: int
    _transient_output_items: tuple[Mapping[str, Any], ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "provider_id": self.provider_id,
            "wire_api": RESPONSES_WIRE,
            "model": self.model,
            "content": self.content,
            "tool_calls": [deepcopy(dict(row)) for row in self.tool_calls],
            "finish_reason": self.finish_reason,
            "usage": deepcopy(dict(self.usage)),
            "request_capture_ref": self.request_capture_ref,
            "response_capture_ref": self.response_capture_ref,
            "request_digest": self.request_digest,
            "response_digest": self.response_digest,
            "private_reasoning_fields_redacted": (
                self.private_reasoning_fields_redacted
            ),
            "reasoning_content_persisted": False,
            "transient_output_items_persisted": False,
        }

    def continuation_assistant_message(self) -> dict[str, Any]:
        message: dict[str, Any] = {
            "role": "assistant",
            "content": self.content,
            "_provider_continuation": {
                "wire_api": RESPONSES_WIRE,
                "output_items": [
                    deepcopy(dict(row)) for row in self._transient_output_items
                ],
            },
        }
        if self.tool_calls:
            message["tool_calls"] = [deepcopy(dict(row)) for row in self.tool_calls]
        return message


def _responses_tool_choice(value: object | None) -> object | None:
    if value is None:
        return None
    if isinstance(value, str):
        _require(
            value in {"none", "auto", "required"},
            "responses_gateway_tool_choice_invalid",
        )
        return value
    _require(isinstance(value, Mapping), "responses_gateway_tool_choice_invalid")
    assert isinstance(value, Mapping)
    if value.get("type") == "function" and "name" in value:
        return {"type": "function", "name": str(value["name"])}
    function = value.get("function")
    _require(
        value.get("type") == "function"
        and isinstance(function, Mapping)
        and bool(function.get("name")),
        "responses_gateway_tool_choice_invalid",
    )
    return {"type": "function", "name": str(function["name"])}


def execute_responses_tool_step_exact_once(
    *,
    profile: AgentTransportProfile,
    messages: Sequence[Mapping[str, Any]],
    tools: Sequence[Mapping[str, Any]],
    capture_root: str | Path,
    run_id: str,
    attempt_id: str,
    tool_choice: object | None = None,
) -> ResponsesToolStepResult:
    _require(
        profile.wire_api == RESPONSES_WIRE,
        "responses_gateway_profile_wire_invalid",
    )
    normalized_run_id = _safe_identity(run_id, "model_gateway_run_id_invalid")
    normalized_attempt_id = _safe_identity(
        attempt_id, "model_gateway_attempt_id_invalid"
    )
    canonical_tools = canonicalize_tool_definitions(
        tools,
        wire_api=CHAT_COMPLETIONS_WIRE,
    )
    projection = compile_agent_request_projection(
        messages=messages,
        canonical_tools=canonical_tools,
        wire_api=RESPONSES_WIRE,
    )
    defaults = deepcopy(dict(profile.request_defaults))
    _require(
        not set(defaults).intersection(
            {"model", "input", "instructions", "tools", "tool_choice"}
        )
        and defaults.get("stream") is False,
        "responses_gateway_defaults_invalid",
    )
    request_body = {"model": profile.model, **projection, **defaults}
    projected_choice = _responses_tool_choice(tool_choice)
    if projected_choice is not None:
        request_body["tool_choice"] = projected_choice
    persisted_request, request_reasoning_redacted = (
        _redact_transient_responses_input(request_body)
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
        profile=profile,  # type: ignore[arg-type]
        request_body=request_body,
        persisted_request_body=persisted_request,
        capture_dir=capture_dir,
        run_id=normalized_run_id,
        attempt_id=normalized_attempt_id,
        capture_schema_version=RESPONSES_TOOL_STEP_CAPTURE_SCHEMA_VERSION,
        capture_type=(
            "model_visible_responses_tool_step_request_without_credentials_or_reasoning"
        ),
        transient_request_reasoning_fields_redacted=request_reasoning_redacted,
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
    status = str(transient_body.get("status") or "")
    _require(
        status in {"completed", "incomplete"},
        "responses_gateway_status_invalid",
        capture_ref=capture_ref,
    )
    content, calls, continuation = _normalize_responses_output(
        transient_body,
        capture_ref=capture_ref,
    )
    _require(
        bool(content.strip() or calls),
        "responses_gateway_tool_step_empty",
        capture_ref=capture_ref,
    )
    usage = (
        transient_body.get("usage")
        if isinstance(transient_body.get("usage"), Mapping)
        else {}
    )
    finish_reason = "tool_calls" if calls else (
        "length" if status == "incomplete" else "stop"
    )
    return ResponsesToolStepResult(
        status="completed_exact_once_tool_step",
        provider_id=profile.provider_id,
        model=profile.model,
        content=content,
        tool_calls=calls,
        finish_reason=finish_reason,
        usage=deepcopy(dict(usage)),
        request_capture_ref=request_ref.as_posix(),
        response_capture_ref=response_ref.as_posix(),
        request_digest=request_digest,
        response_digest=str(capture["response_digest"]),
        private_reasoning_fields_redacted=int(
            capture["private_reasoning_fields_redacted"]
        ),
        _transient_output_items=continuation,
    )


__all__ = [
    "RESPONSES_TOOL_STEP_CAPTURE_SCHEMA_VERSION",
    "ResponsesToolStepResult",
    "execute_responses_tool_step_exact_once",
]
