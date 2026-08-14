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


def test_transport_profiles_and_tool_contract_round_trip() -> None:
    profiles = [
        load_agent_transport_profile(
            _json(
                PROFILE_ROOT
                / "fin_ia_0_1_3_deepseek_v4_pro_ga_chat_control_transport_profile_v1_0.json"
            )
        ),
        load_agent_transport_profile(
            _json(
                PROFILE_ROOT
                / "fin_ia_0_1_3_deepseek_v4_pro_ga_responses_candidate_transport_profile_v1_0.json"
            )
        ),
        load_agent_transport_profile(
            _json(
                PROFILE_ROOT
                / "fin_ia_0_1_3_deepseek_v4_pro_ga_anthropic_shadow_transport_profile_v1_0.json"
            )
        ),
    ]
    assert [row.wire_api for row in profiles] == [
        CHAT_COMPLETIONS_WIRE,
        RESPONSES_WIRE,
        ANTHROPIC_MESSAGES_WIRE,
    ]
    assert profiles[1].url == "https://api.deepseek.com/responses"
    assert profiles[2].url == "https://api.deepseek.com/anthropic/v1/messages"

    canonical = canonicalize_tool_definitions(
        _chat_tools(), wire_api=CHAT_COMPLETIONS_WIRE
    )
    for wire_api in (
        CHAT_COMPLETIONS_WIRE,
        RESPONSES_WIRE,
        ANTHROPIC_MESSAGES_WIRE,
    ):
        projected = project_tool_definitions(canonical, wire_api=wire_api)
        assert canonicalize_tool_definitions(
            projected, wire_api=wire_api
        ) == canonical

    invalid = _json(
        PROFILE_ROOT
        / "fin_ia_0_1_3_deepseek_v4_pro_ga_responses_candidate_transport_profile_v1_0.json"
    )
    invalid["request_defaults"]["max_tool_calls"] = 4
    with pytest.raises(
        AgentProtocolError,
        match="agent_transport_responses_defaults_invalid",
    ):
        load_agent_transport_profile(invalid)


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


def test_anthropic_shadow_cannot_enter_live_dispatch() -> None:
    profile = load_agent_transport_profile(
        _json(
            PROFILE_ROOT
            / "fin_ia_0_1_3_deepseek_v4_pro_ga_anthropic_shadow_transport_profile_v1_0.json"
        )
    )
    with pytest.raises(ModelGatewayError) as caught:
        execute_agent_tool_step_exact_once(
            profile=profile,
            messages=_messages()[:2],
            tools=_chat_tools(),
            capture_root="unused",
            run_id="SHADOW-RUN",
            attempt_id="ATTEMPT-01",
        )
    assert caught.value.code == "anthropic_messages_shadow_live_not_qualified"


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


def test_responses_exact_once_preserves_private_continuation_only_in_memory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    profile = load_agent_transport_profile(
        _json(
            PROFILE_ROOT
            / "fin_ia_0_1_3_deepseek_v4_pro_ga_responses_candidate_transport_profile_v1_0.json"
        )
    )
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-only-secret")
    bodies = [
        {
            "id": "resp_1",
            "object": "response",
            "status": "completed",
            "output": [
                {
                    "id": "reason_1",
                    "type": "reasoning",
                    "content": [
                        {"type": "reasoning_text", "text": "private-hidden-chain"}
                    ],
                    "summary": [],
                },
                {
                    "id": "fc_1",
                    "type": "function_call",
                    "call_id": "call_1",
                    "name": "read_reviewed_evidence_for_cell",
                    "arguments": '{"cell_id":"CELL::value_capture"}',
                    "status": "completed",
                },
            ],
            "usage": {"input_tokens": 10, "output_tokens": 20},
        },
        {
            "id": "resp_2",
            "object": "response",
            "status": "completed",
            "output": [
                {
                    "id": "msg_2",
                    "type": "message",
                    "role": "assistant",
                    "content": [
                        {"type": "output_text", "text": "bounded conclusion"}
                    ],
                    "status": "completed",
                }
            ],
            "usage": {"input_tokens": 30, "output_tokens": 5},
        },
    ]
    sent_bodies: list[dict[str, object]] = []

    def fake_urlopen(request, timeout):
        assert timeout == 300
        sent_bodies.append(json.loads(request.data.decode("utf-8")))
        return _FakeResponse(bodies.pop(0))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    first = execute_responses_tool_step_exact_once(
        profile=profile,
        messages=_messages()[:2],
        tools=_chat_tools(),
        capture_root=tmp_path,
        run_id="responses-test",
        attempt_id="step-01",
    )
    assert first.tool_calls[0]["id"] == "call_1"
    assert "private-hidden-chain" not in json.dumps(first.as_dict())
    continuation = first.continuation_assistant_message()
    assert "private-hidden-chain" in json.dumps(continuation)

    second_messages = [
        *_messages()[:2],
        continuation,
        {
            "role": "tool",
            "tool_call_id": "call_1",
            "content": '{"status":"reviewed_evidence_read"}',
        },
    ]
    second = execute_responses_tool_step_exact_once(
        profile=profile,
        messages=second_messages,
        tools=_chat_tools(),
        capture_root=tmp_path,
        run_id="responses-test",
        attempt_id="step-02",
    )
    assert second.content == "bounded conclusion"
    assert "private-hidden-chain" in json.dumps(sent_bodies[1])

    persisted_request = json.loads(
        Path(second.request_capture_ref).read_text(encoding="utf-8")
    )
    persisted_response = json.loads(
        Path(first.response_capture_ref).read_text(encoding="utf-8")
    )
    assert "private-hidden-chain" not in json.dumps(persisted_request)
    assert "private-hidden-chain" not in json.dumps(persisted_response)
    assert persisted_request["transient_private_reasoning_fields_redacted"] == 1
    assert persisted_response["private_reasoning_fields_redacted"] == 1
    assert "test-only-secret" not in json.dumps(persisted_request)
