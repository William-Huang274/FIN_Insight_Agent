"""Provider-neutral, capture-first model transports for the current runtime."""

from .chat_completions import (
    ChatCompletionProfile,
    ChatCompletionResult,
    ChatCompletionToolStepResult,
    ModelGatewayError,
    execute_chat_completion_exact_once,
    execute_chat_completion_tool_step_exact_once,
    load_chat_completion_profile,
    normalize_chat_completion_tool_calls,
)
from .agent_protocol import (
    ANTHROPIC_MESSAGES_WIRE,
    CHAT_COMPLETIONS_WIRE,
    RESPONSES_WIRE,
    AgentProtocolError,
    AgentTransportProfile,
    AgentToolStepResult,
    canonicalize_tool_definitions,
    compile_agent_request_projection,
    load_agent_transport_profile,
    project_tool_definitions,
    validate_deepseek_ga_live_transport,
)
from .responses import (
    RESPONSES_TOOL_STEP_CAPTURE_SCHEMA_VERSION,
    ResponsesToolStepResult,
    execute_responses_tool_step_exact_once,
)
from .transport_dispatch import execute_agent_tool_step_exact_once
from .deepseek_strict import (
    DEEPSEEK_STRICT_UNSUPPORTED_SCHEMA_KEYWORDS,
    DeepSeekStrictProjectionError,
    project_deepseek_strict_tool,
    validate_deepseek_strict_submission_profile,
)

__all__ = [
    "ChatCompletionProfile",
    "ChatCompletionResult",
    "ChatCompletionToolStepResult",
    "ModelGatewayError",
    "execute_chat_completion_exact_once",
    "execute_chat_completion_tool_step_exact_once",
    "load_chat_completion_profile",
    "normalize_chat_completion_tool_calls",
    "ANTHROPIC_MESSAGES_WIRE",
    "CHAT_COMPLETIONS_WIRE",
    "RESPONSES_WIRE",
    "AgentProtocolError",
    "AgentTransportProfile",
    "AgentToolStepResult",
    "RESPONSES_TOOL_STEP_CAPTURE_SCHEMA_VERSION",
    "ResponsesToolStepResult",
    "canonicalize_tool_definitions",
    "compile_agent_request_projection",
    "execute_responses_tool_step_exact_once",
    "execute_agent_tool_step_exact_once",
    "load_agent_transport_profile",
    "project_tool_definitions",
    "validate_deepseek_ga_live_transport",
    "DEEPSEEK_STRICT_UNSUPPORTED_SCHEMA_KEYWORDS",
    "DeepSeekStrictProjectionError",
    "project_deepseek_strict_tool",
    "validate_deepseek_strict_submission_profile",
]
