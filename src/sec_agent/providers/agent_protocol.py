from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
import re
from typing import Any, Mapping, Protocol, Sequence, runtime_checkable
from urllib.parse import urlparse


CHAT_COMPLETIONS_WIRE = "openai_compatible_chat_completions"
RESPONSES_WIRE = "openai_responses"
ANTHROPIC_MESSAGES_WIRE = "anthropic_messages"
SUPPORTED_AGENT_WIRES = frozenset(
    {CHAT_COMPLETIONS_WIRE, RESPONSES_WIRE, ANTHROPIC_MESSAGES_WIRE}
)
_TRANSIENT_CONTINUATION_KEY = "_provider_continuation"
AGENT_TRANSPORT_PROFILE_SCHEMA_VERSION = "fin_ia_agent_transport_profile_v1_0"
AGENT_TRANSPORT_PROFILE_SCHEMA_VERSION_V1_1 = (
    "fin_ia_agent_transport_profile_v1_1"
)
_REQUIRED_PROFILE_AUTHORITY = {
    "transport_attempt_ceiling": 1,
    "retry_count": 0,
    "capture_model_visible_request": True,
    "capture_assistant_output": True,
    "credential_capture_forbidden": True,
    "provider_private_reasoning_capture_forbidden": True,
    "provider_specific_profile_outside_core": True,
    "local_tool_budget_is_authoritative": True,
    "silently_ignored_provider_parameters_forbidden": True,
}
_REQUIRED_THINKING_TOOL_CAPABILITIES = {
    "thinking_tool_choice_supported": False,
    "thinking_tool_continuation_requires_reasoning_content": True,
    "thinking_tool_continuation_requires_assistant_content": True,
}


class AgentProtocolError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class AgentTransportProfile:
    provider_id: str
    wire_api: str
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


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise AgentProtocolError(code)


def _contains_sensitive_key(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = str(key).casefold()
            if (
                normalized
                in {
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


def load_agent_transport_profile(
    payload: Mapping[str, Any],
) -> AgentTransportProfile:
    expected = {
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
    _require(set(payload) == expected, "agent_transport_profile_fields_invalid")
    schema_version = str(payload.get("schema_version") or "")
    _require(
        schema_version
        in {
            AGENT_TRANSPORT_PROFILE_SCHEMA_VERSION,
            AGENT_TRANSPORT_PROFILE_SCHEMA_VERSION_V1_1,
        },
        "agent_transport_profile_schema_invalid",
    )
    _require(
        payload.get("status")
        == "experimental_transport_profile_not_product_authority",
        "agent_transport_profile_status_invalid",
    )
    wire_api = str(payload.get("wire_api") or "")
    _require(wire_api in SUPPORTED_AGENT_WIRES, "agent_transport_profile_wire_invalid")
    base_url = str(payload.get("base_url") or "").strip()
    parsed = urlparse(base_url)
    endpoint = str(payload.get("endpoint") or "").strip()
    _require(
        parsed.scheme == "https"
        and bool(parsed.netloc)
        and endpoint.startswith("/")
        and "?" not in endpoint,
        "agent_transport_profile_url_invalid",
    )
    defaults = payload.get("request_defaults")
    authority = payload.get("authority")
    _require(
        isinstance(defaults, Mapping) and not _contains_sensitive_key(defaults),
        "agent_transport_profile_defaults_invalid",
    )
    expected_authority = dict(_REQUIRED_PROFILE_AUTHORITY)
    if schema_version == AGENT_TRANSPORT_PROFILE_SCHEMA_VERSION_V1_1:
        expected_authority.update(_REQUIRED_THINKING_TOOL_CAPABILITIES)
    _require(
        isinstance(authority, Mapping)
        and dict(authority) == expected_authority,
        "agent_transport_profile_authority_invalid",
    )
    unsupported_responses = {
        "previous_response_id",
        "conversation",
        "store",
        "background",
        "metadata",
        "include",
        "prompt",
        "truncation",
        "service_tier",
        "max_tool_calls",
        "parallel_tool_calls",
        "temperature",
        "top_p",
    }
    if wire_api == RESPONSES_WIRE:
        _require(
            endpoint == "/responses"
            and not set(defaults).intersection(unsupported_responses)
            and defaults.get("stream") is False
            and defaults.get("reasoning") == {"effort": "max"}
            and isinstance(defaults.get("max_output_tokens"), int)
            and 1 <= int(defaults["max_output_tokens"]) <= 384_000,
            "agent_transport_responses_defaults_invalid",
        )
    elif wire_api == ANTHROPIC_MESSAGES_WIRE:
        _require(
            endpoint == "/v1/messages"
            and defaults.get("stream") is False
            and defaults.get("thinking") == {"type": "enabled"}
            and defaults.get("output_config") == {"effort": "max"}
            and isinstance(defaults.get("max_tokens"), int)
            and 1 <= int(defaults["max_tokens"]) <= 384_000,
            "agent_transport_anthropic_defaults_invalid",
        )
    else:
        _require(
            endpoint == "/chat/completions"
            and defaults.get("stream") is False
            and defaults.get("thinking") == {"type": "enabled"}
            and defaults.get("reasoning_effort") == "max"
            and isinstance(defaults.get("max_tokens"), int)
            and 1 <= int(defaults["max_tokens"]) <= 384_000,
            "agent_transport_chat_defaults_invalid",
        )
    timeout = int(payload.get("timeout_seconds") or 0)
    maximum_bytes = int(payload.get("maximum_response_bytes") or 0)
    provider_id = str(payload.get("provider_id") or "").strip()
    model = str(payload.get("model") or "").strip()
    api_key_env = str(payload.get("api_key_env") or "").strip()
    _require(
        1 <= timeout <= 600
        and 1024 <= maximum_bytes <= 10 * 1024 * 1024
        and bool(provider_id)
        and bool(model)
        and bool(re.fullmatch(r"[A-Z_][A-Z0-9_]*", api_key_env)),
        "agent_transport_profile_identity_or_budget_invalid",
    )
    return AgentTransportProfile(
        provider_id=provider_id,
        wire_api=wire_api,
        base_url=base_url,
        endpoint=endpoint,
        model=model,
        api_key_env=api_key_env,
        timeout_seconds=timeout,
        maximum_response_bytes=maximum_bytes,
        request_defaults=deepcopy(dict(defaults)),
        authority=deepcopy(dict(authority)),
    )


def validate_deepseek_ga_live_transport(
    profile: AgentTransportProfile,
) -> None:
    """Qualify only the two DeepSeek GA wires allowed in paid canaries."""

    _require(
        profile.provider_id == "deepseek"
        and profile.model == "deepseek-v4-pro"
        and profile.api_key_env == "DEEPSEEK_API_KEY",
        "deepseek_ga_transport_identity_invalid",
    )
    if profile.wire_api == CHAT_COMPLETIONS_WIRE:
        _require(
            profile.base_url.rstrip("/") == "https://api.deepseek.com"
            and profile.endpoint == "/chat/completions",
            "deepseek_ga_transport_endpoint_invalid",
        )
        return
    if profile.wire_api == RESPONSES_WIRE:
        _require(
            profile.base_url.rstrip("/") == "https://api.deepseek.com"
            and profile.endpoint == "/responses",
            "deepseek_ga_transport_endpoint_invalid",
        )
        return
    raise AgentProtocolError("deepseek_ga_transport_live_wire_not_qualified")


@runtime_checkable
class AgentToolStepResult(Protocol):
    provider_id: str
    model: str
    tool_calls: tuple[Mapping[str, Any], ...]

    def as_dict(self) -> dict[str, Any]: ...

    def continuation_assistant_message(self) -> dict[str, Any]: ...


def _canonical_tool_call(value: object) -> dict[str, Any]:
    _require(isinstance(value, Mapping), "agent_protocol_tool_call_invalid")
    assert isinstance(value, Mapping)
    function = value.get("function")
    _require(
        set(value).issubset({"id", "type", "function", "index"})
        and value.get("type") == "function"
        and isinstance(function, Mapping),
        "agent_protocol_tool_call_invalid",
    )
    assert isinstance(function, Mapping)
    call_id = str(value.get("id") or "").strip()
    name = str(function.get("name") or "").strip()
    arguments = str(function.get("arguments") or "")
    _require(
        bool(call_id)
        and bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", name))
        and bool(arguments),
        "agent_protocol_tool_call_invalid",
    )
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": arguments},
    }


def normalize_canonical_agent_messages(
    messages: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], ...]:
    _require(bool(messages), "agent_protocol_messages_missing")
    output: list[dict[str, Any]] = []
    for raw in messages:
        _require(isinstance(raw, Mapping), "agent_protocol_message_invalid")
        role = str(raw.get("role") or "")
        if role in {"system", "user"}:
            content = str(raw.get("content") or "")
            _require(
                set(raw) == {"role", "content"} and bool(content),
                "agent_protocol_message_invalid",
            )
            output.append({"role": role, "content": content})
            continue
        if role == "assistant":
            _require(
                set(raw).issubset(
                    {
                        "role",
                        "content",
                        "reasoning_content",
                        "tool_calls",
                        _TRANSIENT_CONTINUATION_KEY,
                    }
                ),
                "agent_protocol_message_invalid",
            )
            content = str(raw.get("content") or "")
            reasoning = str(raw.get("reasoning_content") or "")
            calls = tuple(
                _canonical_tool_call(row) for row in (raw.get("tool_calls") or [])
            )
            continuation = raw.get(_TRANSIENT_CONTINUATION_KEY)
            _require(
                continuation is None or isinstance(continuation, Mapping),
                "agent_protocol_continuation_invalid",
            )
            _require(
                bool(content or calls or continuation),
                "agent_protocol_message_invalid",
            )
            row: dict[str, Any] = {"role": "assistant", "content": content}
            if reasoning:
                row["reasoning_content"] = reasoning
            if calls:
                row["tool_calls"] = [deepcopy(call) for call in calls]
            if continuation is not None:
                row[_TRANSIENT_CONTINUATION_KEY] = deepcopy(dict(continuation))
            output.append(row)
            continue
        if role == "tool":
            content = str(raw.get("content") or "")
            call_id = str(raw.get("tool_call_id") or "").strip()
            _require(
                set(raw) == {"role", "tool_call_id", "content"}
                and bool(call_id)
                and bool(content),
                "agent_protocol_message_invalid",
            )
            output.append(
                {"role": "tool", "tool_call_id": call_id, "content": content}
            )
            continue
        raise AgentProtocolError("agent_protocol_message_role_invalid")
    return tuple(output)


def canonicalize_tool_definitions(
    tools: Sequence[Mapping[str, Any]],
    *,
    wire_api: str,
) -> tuple[dict[str, Any], ...]:
    _require(wire_api in SUPPORTED_AGENT_WIRES, "agent_protocol_wire_invalid")
    _require(bool(tools) and len(tools) <= 16, "agent_protocol_tools_invalid")
    output: list[dict[str, Any]] = []
    names: set[str] = set()
    for raw in tools:
        _require(isinstance(raw, Mapping), "agent_protocol_tool_invalid")
        if wire_api == CHAT_COMPLETIONS_WIRE:
            _require(
                set(raw) == {"type", "function"}
                and raw.get("type") == "function"
                and isinstance(raw.get("function"), Mapping),
                "agent_protocol_tool_invalid",
            )
            source = dict(raw["function"])
            schema_key = "parameters"
        elif wire_api == RESPONSES_WIRE:
            _require(
                raw.get("type") == "function",
                "agent_protocol_tool_invalid",
            )
            source = dict(raw)
            source.pop("type", None)
            schema_key = "parameters"
        else:
            source = dict(raw)
            schema_key = "input_schema"
        _require(
            set(source).issubset(
                {"name", "description", schema_key, "strict"}
            )
            and {"name", "description", schema_key}.issubset(source),
            "agent_protocol_tool_invalid",
        )
        name = str(source.get("name") or "").strip()
        description = str(source.get("description") or "").strip()
        schema = source.get(schema_key)
        _require(
            bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", name))
            and name not in names
            and bool(description)
            and isinstance(schema, Mapping),
            "agent_protocol_tool_invalid",
        )
        names.add(name)
        output.append(
            {
                "name": name,
                "description": description,
                "input_schema": deepcopy(dict(schema)),
                "strict": source.get("strict") is True,
            }
        )
    return tuple(output)


def project_tool_definitions(
    canonical_tools: Sequence[Mapping[str, Any]],
    *,
    wire_api: str,
) -> tuple[dict[str, Any], ...]:
    _require(wire_api in SUPPORTED_AGENT_WIRES, "agent_protocol_wire_invalid")
    output: list[dict[str, Any]] = []
    for raw in canonical_tools:
        _require(
            isinstance(raw, Mapping)
            and set(raw) == {"name", "description", "input_schema", "strict"}
            and isinstance(raw.get("input_schema"), Mapping),
            "agent_protocol_canonical_tool_invalid",
        )
        name = str(raw["name"])
        description = str(raw["description"])
        schema = deepcopy(raw["input_schema"])
        strict = raw["strict"] is True
        if wire_api == CHAT_COMPLETIONS_WIRE:
            function = {
                "name": name,
                "description": description,
                "parameters": schema,
            }
            if strict:
                function["strict"] = True
            output.append({"type": "function", "function": function})
        elif wire_api == RESPONSES_WIRE:
            tool = {
                "type": "function",
                "name": name,
                "description": description,
                "parameters": schema,
            }
            if strict:
                tool["strict"] = True
            output.append(tool)
        else:
            output.append(
                {
                    "name": name,
                    "description": description,
                    "input_schema": schema,
                }
            )
    return tuple(output)


def _responses_input(messages: Sequence[Mapping[str, Any]]) -> tuple[str, list[Any]]:
    instructions = "\n\n".join(
        str(row["content"]) for row in messages if row["role"] == "system"
    )
    items: list[Any] = []
    for row in messages:
        role = str(row["role"])
        if role == "system":
            continue
        if role == "user":
            items.append({"role": "user", "content": str(row["content"])})
            continue
        if role == "assistant":
            continuation = row.get(_TRANSIENT_CONTINUATION_KEY)
            if (
                isinstance(continuation, Mapping)
                and continuation.get("wire_api") == RESPONSES_WIRE
                and isinstance(continuation.get("output_items"), list)
            ):
                items.extend(deepcopy(continuation["output_items"]))
                continue
            if str(row.get("content") or ""):
                items.append(
                    {"role": "assistant", "content": str(row["content"])}
                )
            for call in row.get("tool_calls") or ():
                items.append(
                    {
                        "type": "function_call",
                        "call_id": str(call["id"]),
                        "name": str(call["function"]["name"]),
                        "arguments": str(call["function"]["arguments"]),
                    }
                )
            continue
        items.append(
            {
                "type": "function_call_output",
                "call_id": str(row["tool_call_id"]),
                "output": str(row["content"]),
            }
        )
    return instructions, items


def _anthropic_messages(
    messages: Sequence[Mapping[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    system = "\n\n".join(
        str(row["content"]) for row in messages if row["role"] == "system"
    )
    output: list[dict[str, Any]] = []
    for row in messages:
        role = str(row["role"])
        if role == "system":
            continue
        if role == "user":
            output.append(
                {
                    "role": "user",
                    "content": [{"type": "text", "text": str(row["content"])}],
                }
            )
            continue
        if role == "assistant":
            continuation = row.get(_TRANSIENT_CONTINUATION_KEY)
            if (
                isinstance(continuation, Mapping)
                and continuation.get("wire_api") == ANTHROPIC_MESSAGES_WIRE
                and isinstance(continuation.get("content_blocks"), list)
            ):
                blocks = deepcopy(continuation["content_blocks"])
            else:
                blocks = []
                if str(row.get("content") or ""):
                    blocks.append({"type": "text", "text": str(row["content"])})
                for call in row.get("tool_calls") or ():
                    try:
                        arguments = json.loads(str(call["function"]["arguments"]))
                    except json.JSONDecodeError as exc:
                        raise AgentProtocolError(
                            "agent_protocol_tool_arguments_invalid_json"
                        ) from exc
                    _require(
                        isinstance(arguments, dict),
                        "agent_protocol_tool_arguments_invalid_json",
                    )
                    blocks.append(
                        {
                            "type": "tool_use",
                            "id": str(call["id"]),
                            "name": str(call["function"]["name"]),
                            "input": arguments,
                        }
                    )
            output.append({"role": "assistant", "content": blocks})
            continue
        tool_result = {
            "type": "tool_result",
            "tool_use_id": str(row["tool_call_id"]),
            "content": str(row["content"]),
        }
        if output and output[-1]["role"] == "user" and all(
            block.get("type") == "tool_result"
            for block in output[-1]["content"]
        ):
            output[-1]["content"].append(tool_result)
        else:
            output.append({"role": "user", "content": [tool_result]})
    return system, output


def compile_agent_request_projection(
    *,
    messages: Sequence[Mapping[str, Any]],
    canonical_tools: Sequence[Mapping[str, Any]],
    wire_api: str,
) -> dict[str, Any]:
    normalized = normalize_canonical_agent_messages(messages)
    tools = project_tool_definitions(canonical_tools, wire_api=wire_api)
    if wire_api == CHAT_COMPLETIONS_WIRE:
        clean_messages = []
        for row in normalized:
            projected = {
                key: deepcopy(value)
                for key, value in row.items()
                if key != _TRANSIENT_CONTINUATION_KEY
            }
            clean_messages.append(projected)
        return {"messages": clean_messages, "tools": list(tools)}
    if wire_api == RESPONSES_WIRE:
        instructions, items = _responses_input(normalized)
        return {
            "instructions": instructions,
            "input": items,
            "tools": list(tools),
        }
    if wire_api == ANTHROPIC_MESSAGES_WIRE:
        system, projected_messages = _anthropic_messages(normalized)
        return {
            "system": system,
            "messages": projected_messages,
            "tools": list(tools),
        }
    raise AgentProtocolError("agent_protocol_wire_invalid")


__all__ = [
    "AGENT_TRANSPORT_PROFILE_SCHEMA_VERSION_V1_1",
    "AGENT_TRANSPORT_PROFILE_SCHEMA_VERSION",
    "ANTHROPIC_MESSAGES_WIRE",
    "CHAT_COMPLETIONS_WIRE",
    "RESPONSES_WIRE",
    "AgentProtocolError",
    "AgentTransportProfile",
    "AgentToolStepResult",
    "canonicalize_tool_definitions",
    "compile_agent_request_projection",
    "load_agent_transport_profile",
    "validate_deepseek_ga_live_transport",
    "normalize_canonical_agent_messages",
    "project_tool_definitions",
]
