from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping

import pytest

from sec_agent.providers import AgentTransportProfile, ChatCompletionProfile
from sec_agent.research.multi_agent_preview import (
    compile_analysis_completion_checkpoint,
    compile_analysis_fragment_checkpoint,
    compile_token_budget_basis,
    merge_analysis_draft_fragments,
)
from sec_agent.research.multi_agent_preview_runtime import (
    compile_cross_role_feedback_receipt,
    compile_lead_checkpoint_successor_zero_call_projection,
    execute_analyzed_preview_node,
    execute_checkpointed_preview_submission,
    execute_validated_preview_node,
    start_preview_agent_session,
)


ROOT = Path(__file__).resolve().parents[1]


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


@dataclass(frozen=True)
class _FakeAnalysis:
    content: str
    finish_reason: str = "stop"

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": "completed_exact_once",
            "provider_id": "deepseek",
            "model": "deepseek-v4-pro",
            "content": self.content,
            "finish_reason": self.finish_reason,
            "usage": {"prompt_tokens": 100, "completion_tokens": 200},
            "request_capture_ref": "capture://analysis-request",
            "response_capture_ref": "capture://analysis-response",
            "request_digest": "3" * 64,
            "response_digest": "4" * 64,
            "private_reasoning_fields_redacted": 1,
        }


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


def _chat_profile(*, thinking: bool) -> ChatCompletionProfile:
    return ChatCompletionProfile(
        provider_id="deepseek",
        base_url="https://api.deepseek.com",
        endpoint="/chat/completions",
        model="deepseek-v4-pro",
        api_key_env="DEEPSEEK_API_KEY",
        timeout_seconds=300,
        maximum_response_bytes=2_097_152,
        request_defaults={
            "max_tokens": 8000 if thinking else 2000,
            "stream": False,
            "thinking": {"type": "enabled" if thinking else "disabled"},
            **({"reasoning_effort": "max"} if thinking else {}),
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


def _analysis_checkpoint(partial_draft: str) -> dict[str, Any]:
    return compile_analysis_fragment_checkpoint(
        case_key="DELL",
        run_id="PREVIEW-R4-LENGTH",
        node_id="RESEARCH-LEAD-PLAN",
        source_authority_ref="authority.json",
        source_authority_sha256="a" * 64,
        source_public_result_ref="result.json",
        source_public_result_sha256="b" * 64,
        source_public_result_digest="c" * 64,
        request_capture_ref="capture/request.json",
        request_capture_sha256="d" * 64,
        request_digest="e" * 64,
        response_capture_ref="capture/response.json",
        response_capture_sha256="f" * 64,
        response_digest="1" * 64,
        partial_draft=partial_draft,
        required_outputs=("value",),
        completed_required_outputs=(),
        partial_required_outputs=("value",),
        missing_required_outputs=(),
        usage={"prompt_tokens": 100, "completion_tokens": 200},
        recorded_at="2026-08-20T12:00:00+00:00",
    )


def _analysis_completion_checkpoint(
    partial_draft: str,
    continuation_draft: str,
) -> tuple[dict[str, Any], str]:
    fragment = _analysis_checkpoint(partial_draft)
    merged = merge_analysis_draft_fragments(
        checkpoint=fragment,
        partial_draft=partial_draft,
        continuation_draft=continuation_draft,
    )
    basis = compile_token_budget_basis(
        node_id="RESEARCH-LEAD-PLAN::ANALYSIS_CONTINUATION",
        purpose=(
            "Continue the preserved analysis fragment without redoing any "
            "completed research content."
        ),
        input_characters=1000,
        input_reference_count=1,
        required_outputs=("visible_analysis_continuation", "value"),
        schema_burden="analysis-only",
        materiality_quality_risk="partial analysis cannot become a Lead plan",
        comparable_run_evidence=("R4 visible length failure",),
        reasoning_profile="deepseek-v4-pro thinking=low",
        output_token_ceiling=4000,
        stop_truncation_behavior="one continuation; finish_reason stop",
    )
    checkpoint = compile_analysis_completion_checkpoint(
        fragment_checkpoint=fragment,
        fragment_checkpoint_ref="checkpoint/r4.json",
        fragment_checkpoint_sha256="2" * 64,
        partial_draft=partial_draft,
        source_continuation_run_id="PREVIEW-R5-CONTINUE",
        source_continuation_authority_ref="authority/r5.json",
        source_continuation_authority_sha256="3" * 64,
        source_continuation_result_ref="result/r5.json",
        source_continuation_result_sha256="4" * 64,
        source_continuation_result_digest="5" * 64,
        continuation_request_capture_ref="capture/r5/request.json",
        continuation_request_capture_sha256="6" * 64,
        continuation_request_digest="7" * 64,
        continuation_response_capture_ref="capture/r5/response.json",
        continuation_response_capture_sha256="8" * 64,
        continuation_response_digest="9" * 64,
        continuation_messages_digest="0" * 64,
        continuation_draft=continuation_draft,
        finish_reason="stop",
        usage={"prompt_tokens": 100, "completion_tokens": 200},
        source_analysis_token_budget_basis=basis,
        recorded_at="2026-08-20T13:00:00+00:00",
    )
    return checkpoint, merged


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


def test_analysis_and_submission_are_separate_and_submission_can_repair(
    tmp_path: Path,
) -> None:
    state = start_preview_agent_session(
        agent_id="AGENT::RESEARCH_LEAD",
        run_id="PREVIEW-R4",
        objective_ref="objective://dell",
        active_plan_ref="plan://pending",
    )
    analysis_calls = 0
    submission_calls = 0
    submission_messages: list[list[Mapping[str, Any]]] = []

    def analyze(**_kwargs: Any) -> _FakeAnalysis:
        nonlocal analysis_calls
        analysis_calls += 1
        return _FakeAnalysis(
            "Complete draft: value=accepted. Preserve exact role and stop condition."
        )

    def submit(**kwargs: Any) -> _FakeStep:
        nonlocal submission_calls
        submission_calls += 1
        submission_messages.append(list(kwargs["messages"]))
        value = "bad" if submission_calls == 1 else "accepted"
        return _FakeStep(
            tool_calls=(
                {
                    "id": f"call_{submission_calls}",
                    "type": "function",
                    "function": {
                        "name": "submit_preview",
                        "arguments": json.dumps({"value": value}),
                    },
                },
            )
        )

    execution = execute_analyzed_preview_node(
        analysis_profile=_chat_profile(thinking=True),
        submission_profile=_chat_profile(thinking=False),
        session_state=state,
        messages=(
            {
                "role": "system",
                "content": "Research the role and submit exactly one tool call.",
            },
            {
                "role": "user",
                "content": "ORIGINAL_PRIVATE_TASK_CONTEXT",
            },
        ),
        tool=_tool(),
        validator=lambda payload: (
            dict(payload)
            if payload.get("value") == "accepted"
            else (_ for _ in ()).throw(ValueError("preview_value_invalid"))
        ),
        capture_root=tmp_path,
        run_id="PREVIEW-R4",
        node_id="RESEARCH-LEAD-PLAN",
        purpose="形成研究负责人共同计划并严格保持六角色边界与停止条件。",
        input_reference_count=1,
        required_outputs=("value",),
        schema_burden="one strict preview tool",
        materiality_quality_risk="invalid Lead plan would corrupt all downstream workpapers",
        comparable_run_evidence=("R3 Lead capacity failure",),
        analysis_output_token_ceiling=8000,
        submission_output_token_ceiling=2000,
        analysis_transport=analyze,
        submission_transport=submit,
    )
    assert execution.validated_payload == {"value": "accepted"}
    assert analysis_calls == 1
    assert submission_calls == 2
    assert execution.successor_attempt_count == 1
    assert [row["phase"] for row in execution.attempts] == [
        "analysis",
        "submission",
        "submission",
    ]
    assert set(execution.token_budget_basis) == {"analysis", "submission"}
    assert execution.token_budget_basis["analysis"]["output_token_ceiling"] == 8000
    assert execution.token_budget_basis["submission"]["output_token_ceiling"] == 2000
    assert "ORIGINAL_PRIVATE_TASK_CONTEXT" not in json.dumps(
        submission_messages[0], ensure_ascii=False
    )
    assert "Complete draft" in json.dumps(
        submission_messages[0], ensure_ascii=False
    )
    repair_prompt = json.dumps(submission_messages[1], ensure_ascii=False)
    assert "ACTIONABLE_CONTRACT_FEEDBACK" in repair_prompt
    assert "preview_value_invalid" in repair_prompt


def test_analysis_length_finish_fails_before_submission(tmp_path: Path) -> None:
    state = start_preview_agent_session(
        agent_id="AGENT::RESEARCH_LEAD",
        run_id="PREVIEW-R4-LENGTH",
        objective_ref="objective://dell",
        active_plan_ref="plan://pending",
    )
    submission_calls = 0

    def analyze(**_kwargs: Any) -> _FakeAnalysis:
        return _FakeAnalysis("partial but non-empty draft", finish_reason="length")

    def submit(**_kwargs: Any) -> _FakeStep:
        nonlocal submission_calls
        submission_calls += 1
        return _FakeStep(tool_calls=())

    try:
        execute_analyzed_preview_node(
            analysis_profile=_chat_profile(thinking=True),
            submission_profile=_chat_profile(thinking=False),
            session_state=state,
            messages=(
                {"role": "system", "content": "Analyze and submit."},
                {"role": "user", "content": "Current task authority."},
            ),
            tool=_tool(),
            validator=dict,
            capture_root=tmp_path,
            run_id="PREVIEW-R4-LENGTH",
            node_id="RESEARCH-LEAD-PLAN",
            purpose="形成研究负责人共同计划并检查截断是否严格失败关闭。",
            input_reference_count=0,
            required_outputs=("value",),
            schema_burden="one strict preview tool",
            materiality_quality_risk="partial analysis cannot become a Lead plan",
            comparable_run_evidence=("R3 Lead capacity failure",),
            analysis_output_token_ceiling=8000,
            submission_output_token_ceiling=2000,
            analysis_transport=analyze,
            submission_transport=submit,
        )
    except Exception as exc:
        assert "analysis_finish_reason_invalid:length" in str(exc)
    else:
        raise AssertionError("length-truncated analysis must fail closed")
    assert submission_calls == 0


def test_analysis_checkpoint_continues_once_then_submits_merged_draft(
    tmp_path: Path,
) -> None:
    partial = "Preserved partial Lead draft with already reviewed business context."
    checkpoint = _analysis_checkpoint(partial)
    state = start_preview_agent_session(
        agent_id="AGENT::RESEARCH_LEAD",
        run_id="PREVIEW-R5-CONTINUE",
        objective_ref="objective://dell",
        active_plan_ref="plan://pending",
    )
    analysis_calls = 0
    continuation_messages: list[Mapping[str, Any]] = []
    submission_messages: list[Mapping[str, Any]] = []

    def continue_analysis(**kwargs: Any) -> _FakeAnalysis:
        nonlocal analysis_calls
        analysis_calls += 1
        continuation_messages.extend(kwargs["messages"])
        assert kwargs["profile"].request_defaults["reasoning_effort"] == "low"
        return _FakeAnalysis(
            "accepted\nCOMPLETED_OUTPUTS::value"
        )

    def submit(**kwargs: Any) -> _FakeStep:
        submission_messages.extend(kwargs["messages"])
        return _FakeStep(
            tool_calls=(
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "submit_preview",
                        "arguments": json.dumps({"value": "accepted"}),
                    },
                },
            )
        )

    execution = execute_analyzed_preview_node(
        analysis_profile=_chat_profile(thinking=True),
        submission_profile=_chat_profile(thinking=False),
        analysis_continuation_profile=ChatCompletionProfile(
            **{
                **_chat_profile(thinking=True).__dict__,
                "request_defaults": {
                    **_chat_profile(thinking=True).request_defaults,
                    "reasoning_effort": "low",
                },
            }
        ),
        session_state=state,
        messages=(
            {"role": "system", "content": "ORIGINAL_SYSTEM_CONTEXT_DO_NOT_RESEND"},
            {"role": "user", "content": "ORIGINAL_USER_CONTEXT_DO_NOT_RESEND"},
        ),
        tool=_tool(),
        validator=dict,
        capture_root=tmp_path,
        run_id="PREVIEW-R5-CONTINUE",
        node_id="RESEARCH-LEAD-PLAN",
        purpose="只完成先前截断的 Lead 分析，然后映射既有合同。",
        input_reference_count=99,
        required_outputs=("value",),
        schema_burden="one strict preview tool",
        materiality_quality_risk="partial analysis cannot become a Lead plan",
        comparable_run_evidence=("R4 visible length failure",),
        analysis_output_token_ceiling=2000,
        submission_output_token_ceiling=1000,
        maximum_submission_successor_attempts=0,
        analysis_checkpoint=checkpoint,
        analysis_checkpoint_draft=partial,
        analysis_transport=continue_analysis,
        submission_transport=submit,
    )
    assert analysis_calls == 1
    assert [row["phase"] for row in execution.attempts] == [
        "analysis_continuation",
        "submission",
    ]
    continuation_text = json.dumps(continuation_messages, ensure_ascii=False)
    assert partial in continuation_text
    assert "ORIGINAL_SYSTEM_CONTEXT_DO_NOT_RESEND" not in continuation_text
    assert "ORIGINAL_USER_CONTEXT_DO_NOT_RESEND" not in continuation_text
    submission_text = json.dumps(submission_messages, ensure_ascii=False)
    assert partial in submission_text
    assert "COMPLETED_OUTPUTS::value" in submission_text
    assert len(state.feedback_receipts) == 1
    assert state.feedback_receipts[0]["target_node_id"] == "RESEARCH-LEAD-PLAN"
    assert {row["event_type"] for row in state.events} >= {
        "checkpoint_created",
        "feedback_issued",
        "session_resumed",
    }


@pytest.mark.parametrize(
    ("content", "finish_reason", "expected_code"),
    [
        (
            "accepted",
            "stop",
            "analysis_continuation_semantically_incomplete",
        ),
        (
            "accepted\nCOMPLETED_OUTPUTS::value",
            "length",
            "analysis_continuation_finish_reason_invalid:length",
        ),
    ],
)
def test_analysis_checkpoint_failure_never_recontinues_or_submits(
    tmp_path: Path,
    content: str,
    finish_reason: str,
    expected_code: str,
) -> None:
    partial = "Preserved partial Lead draft with already reviewed business context."
    checkpoint = _analysis_checkpoint(partial)
    state = start_preview_agent_session(
        agent_id="AGENT::RESEARCH_LEAD",
        run_id="PREVIEW-R5-FAIL",
        objective_ref="objective://dell",
        active_plan_ref="plan://pending",
    )
    analysis_calls = 0
    submission_calls = 0

    def continue_analysis(**_kwargs: Any) -> _FakeAnalysis:
        nonlocal analysis_calls
        analysis_calls += 1
        return _FakeAnalysis(content, finish_reason=finish_reason)

    def submit(**_kwargs: Any) -> _FakeStep:
        nonlocal submission_calls
        submission_calls += 1
        return _FakeStep(tool_calls=())

    with pytest.raises(Exception, match=expected_code):
        execute_analyzed_preview_node(
            analysis_profile=_chat_profile(thinking=True),
            submission_profile=_chat_profile(thinking=False),
            analysis_continuation_profile=ChatCompletionProfile(
                **{
                    **_chat_profile(thinking=True).__dict__,
                    "request_defaults": {
                        **_chat_profile(thinking=True).request_defaults,
                        "reasoning_effort": "low",
                    },
                }
            ),
            session_state=state,
            messages=(
                {"role": "system", "content": "Do not resend this."},
                {"role": "user", "content": "Do not resend this either."},
            ),
            tool=_tool(),
            validator=dict,
            capture_root=tmp_path,
            run_id="PREVIEW-R5-FAIL",
            node_id="RESEARCH-LEAD-PLAN",
            purpose="只完成先前截断的 Lead 分析。",
            input_reference_count=99,
            required_outputs=("value",),
            schema_burden="one strict preview tool",
            materiality_quality_risk="partial analysis cannot become a Lead plan",
            comparable_run_evidence=("R4 visible length failure",),
            analysis_output_token_ceiling=2000,
            submission_output_token_ceiling=1000,
            maximum_submission_successor_attempts=0,
            analysis_checkpoint=checkpoint,
            analysis_checkpoint_draft=partial,
            analysis_transport=continue_analysis,
            submission_transport=submit,
        )
    assert analysis_calls == 1
    assert submission_calls == 0


def test_completed_analysis_checkpoint_resumes_at_submission_only(
    tmp_path: Path,
) -> None:
    partial = "Preserved partial Lead draft with already reviewed business context."
    continuation = " accepted\nCOMPLETED_OUTPUTS::value"
    checkpoint, merged = _analysis_completion_checkpoint(partial, continuation)
    state = start_preview_agent_session(
        agent_id="AGENT::RESEARCH_LEAD",
        run_id="PREVIEW-R6-SUBMISSION",
        objective_ref="objective://dell",
        active_plan_ref="plan://pending",
    )
    submission_calls = 0
    submission_messages: list[Mapping[str, Any]] = []

    def submit(**kwargs: Any) -> _FakeStep:
        nonlocal submission_calls
        submission_calls += 1
        submission_messages.extend(kwargs["messages"])
        return _FakeStep(
            tool_calls=(
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "submit_preview",
                        "arguments": json.dumps({"value": "accepted"}),
                    },
                },
            )
        )

    execution = execute_checkpointed_preview_submission(
        submission_profile=_chat_profile(thinking=False),
        session_state=state,
        completed_analysis_checkpoint=checkpoint,
        merged_analysis_draft=merged,
        tool=_tool(),
        validator=dict,
        capture_root=tmp_path,
        run_id="PREVIEW-R6-SUBMISSION",
        node_id="RESEARCH-LEAD-PLAN",
        purpose=(
            "Reuse the completed and bound Lead analysis, then perform only "
            "the strict contract submission."
        ),
        required_outputs=("value",),
        schema_burden="one strict preview tool",
        materiality_quality_risk="checkpoint drift cannot become a Lead plan",
        comparable_run_evidence=("R5 continuation capture",),
        submission_output_token_ceiling=1000,
        maximum_submission_successor_attempts=0,
        submission_transport=submit,
    )
    assert submission_calls == 1
    assert [row["phase"] for row in execution.attempts] == [
        "analysis_checkpoint_reuse",
        "submission",
    ]
    assert execution.attempts[0]["provider_call"] is False
    assert set(execution.token_budget_basis) == {"source_analysis", "submission"}
    submission_payload = json.loads(submission_messages[1]["content"])
    assert submission_payload["analysis_draft"] == merged
    assert {row["event_type"] for row in state.events} >= {
        "checkpoint_created",
        "session_resumed",
    }

    with pytest.raises(
        Exception,
        match="completed_analysis_checkpoint_scope_invalid",
    ):
        execute_checkpointed_preview_submission(
            submission_profile=_chat_profile(thinking=False),
            session_state=state,
            completed_analysis_checkpoint=checkpoint,
            merged_analysis_draft=merged + " drift",
            tool=_tool(),
            validator=dict,
            capture_root=tmp_path,
            run_id="PREVIEW-R6-DRIFT",
            node_id="RESEARCH-LEAD-PLAN",
            purpose="不得接受漂移草稿。",
            required_outputs=("value",),
            schema_burden="one strict preview tool",
            materiality_quality_risk="checkpoint drift cannot become a Lead plan",
            comparable_run_evidence=("R5 continuation capture",),
            submission_output_token_ceiling=1000,
            maximum_submission_successor_attempts=0,
            submission_transport=submit,
        )
    assert submission_calls == 1


def test_lead_checkpoint_successor_projection_skips_completed_lead_node() -> None:
    topology = json.loads(
        (
            ROOT
            / "configs/research/fin_ia_0_1_3_multi_agent_role_topology_v1_0.json"
        ).read_text(encoding="utf-8")
    )
    objective = json.loads(
        (
            ROOT
            / "configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_preview_objective_v1_0.json"
        ).read_text(encoding="utf-8")
    )
    specialist_checkpoint = json.loads(
        (
            ROOT
            / "configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_preview_R3_specialist_plan_checkpoint_v1_0.json"
        ).read_text(encoding="utf-8")
    )
    lead_checkpoint = json.loads(
        (
            ROOT
            / "configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_preview_R6_lead_plan_checkpoint_v1_0.json"
        ).read_text(encoding="utf-8")
    )

    result = compile_lead_checkpoint_successor_zero_call_projection(
        repo_root=ROOT,
        topology=topology,
        objective_payload=objective,
        specialist_plan_checkpoint=specialist_checkpoint,
        lead_plan_checkpoint=lead_checkpoint,
    )

    assert result["status"].endswith("downstream_successor_zero_call_pass")
    assert result["maximum_new_model_nodes"] == 15
    assert result["downstream_node_budget_basis"] == {
        "specialist_workpaper_nodes": 6,
        "lead_coordination_nodes": 1,
        "maximum_counter_challenge_repairs": 3,
        "maximum_evaluation_rounds": 2,
        "maximum_evaluator_repairs": 2,
        "conditional_writer_nodes": 1,
    }
    assert result["claims"]["new_lead_analysis_calls"] == 0
    assert result["claims"]["new_lead_submission_calls"] == 0
    assert result["materialization_readiness"]["blocking_empty_role_ids"] == []
