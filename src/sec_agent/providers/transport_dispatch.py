from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence

from .agent_protocol import (
    ANTHROPIC_MESSAGES_WIRE,
    CHAT_COMPLETIONS_WIRE,
    RESPONSES_WIRE,
    AgentToolStepResult,
    AgentTransportProfile,
)
from .chat_completions import (
    ChatCompletionProfile,
    ModelGatewayError,
    execute_chat_completion_tool_step_exact_once,
)
from .responses import execute_responses_tool_step_exact_once


def _legacy_chat_profile(
    profile: AgentTransportProfile,
) -> ChatCompletionProfile:
    """Project a provider-neutral profile into the proven Chat executor."""

    return ChatCompletionProfile(
        provider_id=profile.provider_id,
        base_url=profile.base_url,
        endpoint=profile.endpoint,
        model=profile.model,
        api_key_env=profile.api_key_env,
        timeout_seconds=profile.timeout_seconds,
        maximum_response_bytes=profile.maximum_response_bytes,
        request_defaults=dict(profile.request_defaults),
        authority={
            key: value
            for key, value in profile.authority.items()
            if key
            not in {
                "local_tool_budget_is_authoritative",
                "silently_ignored_provider_parameters_forbidden",
            }
        },
    )


def execute_agent_tool_step_exact_once(
    *,
    profile: AgentTransportProfile,
    messages: Sequence[Mapping[str, object]],
    tools: Sequence[Mapping[str, object]],
    capture_root: str | Path,
    run_id: str,
    attempt_id: str,
    tool_choice: object | None = None,
) -> AgentToolStepResult:
    """Dispatch one exact-once step without leaking wire logic inward.

    Anthropic Messages remains a projection-only shadow until a separate
    qualification proves its continuation and capture semantics.
    """

    if profile.wire_api == CHAT_COMPLETIONS_WIRE:
        return execute_chat_completion_tool_step_exact_once(
            profile=_legacy_chat_profile(profile),
            messages=messages,
            tools=tools,
            capture_root=capture_root,
            run_id=run_id,
            attempt_id=attempt_id,
            tool_choice=tool_choice,
        )
    if profile.wire_api == RESPONSES_WIRE:
        return execute_responses_tool_step_exact_once(
            profile=profile,
            messages=messages,
            tools=tools,
            capture_root=capture_root,
            run_id=run_id,
            attempt_id=attempt_id,
            tool_choice=tool_choice,
        )
    if profile.wire_api == ANTHROPIC_MESSAGES_WIRE:
        raise ModelGatewayError("anthropic_messages_shadow_live_not_qualified")
    raise ModelGatewayError("agent_transport_wire_not_supported")


__all__ = ["execute_agent_tool_step_exact_once"]
