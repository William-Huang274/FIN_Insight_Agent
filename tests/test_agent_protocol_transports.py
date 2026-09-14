from __future__ import annotations

import json
from pathlib import Path
import urllib.request

import pytest


ROOT = Path(__file__).resolve().parents[1]

from sec_agent.providers.agent_protocol import (  # noqa: E402
    ANTHROPIC_MESSAGES_WIRE,
    CHAT_COMPLETIONS_WIRE,
    RESPONSES_WIRE,
    AgentProtocolError,
    canonicalize_tool_definitions,
    compile_agent_request_projection,
    load_agent_transport_profile,
    project_tool_definitions,
)
from sec_agent.providers.responses import (  # noqa: E402
    execute_responses_tool_step_exact_once,
)
from sec_agent.providers.chat_completions import ModelGatewayError  # noqa: E402
from sec_agent.providers.transport_dispatch import (  # noqa: E402
    execute_agent_tool_step_exact_once,
)


PROFILE_ROOT = ROOT / "configs/providers"


def _json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _chat_tools() -> list[dict[str, object]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "read_reviewed_evidence_for_cell",
                "description": "Read reviewed evidence.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "cell_id": {"type": "string", "enum": ["CELL::value_capture"]}
                    },
                    "required": ["cell_id"],
                    "additionalProperties": False,
                },
            },
        }
    ]


def _messages() -> list[dict[str, object]]:
    return [
        {"role": "system", "content": "Use only reviewed financial evidence."},
        {"role": "user", "content": "Assess value capture."},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "read_reviewed_evidence_for_cell",
                        "arguments": '{"cell_id":"CELL::value_capture"}',
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call_1",
            "content": '{"status":"reviewed_evidence_read"}',
        },
    ]


def test_same_canonical_transcript_projects_to_three_wire_shapes() -> None:
    canonical = canonicalize_tool_definitions(
        _chat_tools(), wire_api=CHAT_COMPLETIONS_WIRE
    )
    chat = compile_agent_request_projection(
        messages=_messages(),
        canonical_tools=canonical,
        wire_api=CHAT_COMPLETIONS_WIRE,
    )
    responses = compile_agent_request_projection(
        messages=_messages(),
        canonical_tools=canonical,
        wire_api=RESPONSES_WIRE,
    )
    anthropic = compile_agent_request_projection(
        messages=_messages(),
        canonical_tools=canonical,
        wire_api=ANTHROPIC_MESSAGES_WIRE,
    )

    assert chat["messages"][2]["tool_calls"][0]["id"] == "call_1"
    assert responses["instructions"] == "Use only reviewed financial evidence."
    assert [row["type"] for row in responses["input"] if "type" in row] == [
        "function_call",
        "function_call_output",
    ]
    assert anthropic["messages"][1]["content"][0]["type"] == "tool_use"
    assert anthropic["messages"][2]["content"][0]["type"] == "tool_result"
    assert "previous_response_id" not in responses
    assert "max_tool_calls" not in responses


class _FakeResponse:
    status = 200

    def __init__(self, payload: dict[str, object]) -> None:
        self._raw = json.dumps(payload).encode("utf-8")
        self.headers = {"Content-Type": "application/json", "x-request-id": "req"}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, _maximum: int) -> bytes:
        return self._raw
