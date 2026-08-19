from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping

from sec_agent.providers import AgentTransportProfile
from sec_agent.research.multi_agent_preview_runtime import (
    compile_cross_role_feedback_receipt,
    execute_validated_preview_node,
    start_preview_agent_session,
)


@dataclass(frozen=True)
class _FakeStep:
    tool_calls: tuple[Mapping[str, Any], ...]
    provider_id: str = "deepseek"
    model: str = "deepseek-v4-pro"

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": "completed",
            "provider_id": self.provider_id,
            "model": self.model,
            "tool_calls": [dict(row) for row in self.tool_calls],
            "finish_reason": "tool_calls",
            "usage": {"input_tokens": 10, "output_tokens": 10},
            "request_capture_ref": "capture://request",
            "response_capture_ref": "capture://response",
            "request_digest": "1" * 64,
            "response_digest": "2" * 64,
            "private_reasoning_fields_redacted": 1,
        }

    def continuation_assistant_message(self) -> dict[str, Any]:
        return {"role": "assistant", "content": "", "tool_calls": list(self.tool_calls)}


def _profile() -> AgentTransportProfile:
    return AgentTransportProfile(
        provider_id="deepseek",
        wire_api="openai_compatible_chat_completions",
        base_url="https://api.deepseek.com",
        endpoint="/chat/completions",
        model="deepseek-v4-pro",
        api_key_env="DEEPSEEK_API_KEY",
        timeout_seconds=300,
        maximum_response_bytes=2_097_152,
        request_defaults={
            "max_tokens": 4000,
            "stream": False,
            "thinking": {"type": "enabled"},
            "reasoning_effort": "max",
        },
        authority={},
    )


def _tool() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "submit_preview",
            "description": "submit",
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "required": ["value"],
                "properties": {"value": {"type": "string"}},
            },
        },
    }


def test_contract_failure_is_visible_then_one_successor_can_repair(tmp_path: Path) -> None:
    state = start_preview_agent_session(
        agent_id="AGENT::DEMAND_QUALITY",
        run_id="PREVIEW-R1",
        objective_ref="objective://dell",
        active_plan_ref="plan://dell",
    )
    calls = 0

    def transport(**_kwargs: Any) -> _FakeStep:
        nonlocal calls
        calls += 1
        value = "bad" if calls == 1 else "accepted"
        return _FakeStep(
            tool_calls=(
                {
                    "id": f"call_{calls}",
                    "type": "function",
                    "function": {
                        "name": "submit_preview",
                        "arguments": json.dumps({"value": value}),
                    },
                },
            )
        )

    def validate(payload: Mapping[str, Any]) -> Mapping[str, Any]:
        if payload.get("value") != "accepted":
            raise ValueError("preview_value_invalid")
        return dict(payload)

    execution = execute_validated_preview_node(
        profile=_profile(),
        session_state=state,
        messages=(
            {"role": "system", "content": "Submit a preview."},
            {"role": "user", "content": "Use only current authority."},
        ),
        tool=_tool(),
        validator=validate,
        capture_root=tmp_path,
        run_id="PREVIEW-R1",
        node_id="DEMAND-PLAN",
        purpose="形成一个受合同约束的独立需求研究计划意见并保留失败反馈。",
        input_reference_count=1,
        required_outputs=("value",),
        schema_burden="one small strict tool contract",
        materiality_quality_risk="invalid contract must not enter later research",
        comparable_run_evidence=("DELL fixed workflow R7",),
        output_token_ceiling=1024,
        transport=transport,
    )
    assert execution.validated_payload["value"] == "accepted"
    assert execution.successor_attempt_count == 1
    assert calls == 2
    assert [row["event_type"] for row in state.events].count(
        "provider_attempt_completed"
    ) == 2
    assert any(row["event_type"] == "feedback_issued" for row in state.events)


def test_cross_role_challenge_becomes_typed_agent_feedback() -> None:
    receipt = compile_cross_role_feedback_receipt(
        target_session_id="SESSION::DELL::VALUE",
        challenge={
            "challenge_id": "CHALLENGE::ONE",
            "source_agent_id": "AGENT::COUNTEREVIDENCE",
            "target_agent_id": "AGENT::VALUE_CAPTURE",
            "challenge": "重新检查公司利润变化是否被过度归因于 AI 服务器。",
            "material_reason": "当前资料没有产品到公司利润的直接财务桥。",
            "requested_action": "recheck_judgment",
            "source_workpaper_digest": "a" * 64,
        },
        created_at="2026-08-19T12:00:00+00:00",
    )
    assert receipt["owning_plane"] == "agent_work_mode_plane"
    assert receipt["owning_stage"] == "S3"
    assert receipt["target_node_id"] == "AGENT::VALUE_CAPTURE"
    assert receipt["feedback_digest"]
