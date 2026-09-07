from __future__ import annotations

import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

import scripts.engineering.verify_active_baseline as active_baseline
from sec_agent.canonical_runtime.session import (
    append_session_event,
    create_agent_session,
)
from scripts.research.run_s3_current_dynamic_single_unit_live import (
    AUTHORITY_SCHEMA,
    AUTHORITY_STATUS,
    CurrentDynamicSingleUnitLiveError,
    _execute_workpaper_submission_attempt,
    _bind_round_feedback,
    _feedback_for_round,
    _force_tool,
    _public_provider_step,
    _tool_arguments,
    run,
    validate_authority,
)
from sec_agent.providers import execute_agent_tool_step_exact_once
from sec_agent.providers.chat_completions import ChatCompletionToolStepResult


def _step(
    *, name: str, arguments: object, finish_reason: str = "tool_calls"
) -> ChatCompletionToolStepResult:
    return ChatCompletionToolStepResult(
        status="completed_exact_once_tool_step",
        provider_id="fixture",
        model="fixture-model",
        content="",
        reasoning_content="transient and never persisted",
        tool_calls=(
            {
                "id": "call-fixture-1",
                "type": "function",
                "function": {
                    "name": name,
                    "arguments": json.dumps(arguments, ensure_ascii=False),
                },
            },
        ),
        finish_reason=finish_reason,
        usage={"prompt_tokens": 10, "completion_tokens": 5},
        request_capture_ref=str(ROOT / "data/captures/request.json"),
        response_capture_ref=str(ROOT / "data/captures/response.json"),
        request_digest="a" * 64,
        response_digest="b" * 64,
        private_reasoning_fields_redacted=1,
    )


def test_current_dynamic_live_parses_exact_expected_tool_only() -> None:
    step = _step(
        name="request_research_evidence",
        arguments={"request_ids": ["REQ::DELL::PVM_BRIDGE::V1"]},
    )
    payload, call_id = _tool_arguments(
        step, expected_name="request_research_evidence"
    )
    assert payload["request_ids"] == ["REQ::DELL::PVM_BRIDGE::V1"]
    assert call_id == "call-fixture-1"

    with pytest.raises(CurrentDynamicSingleUnitLiveError) as exc:
        _tool_arguments(step, expected_name="submit_research_reflection")
    assert exc.value.code == "current_dynamic_live_unexpected_tool_call"

    truncated = _step(
        name="submit_specialist_workpaper",
        arguments={"partial": True},
        finish_reason="length",
    )
    with pytest.raises(CurrentDynamicSingleUnitLiveError) as exc:
        _tool_arguments(
            truncated,
            expected_name="submit_specialist_workpaper",
        )
    assert exc.value.code == "current_dynamic_live_tool_arguments_truncated"


def test_current_dynamic_live_forces_one_named_function() -> None:
    assert _force_tool("submit_research_reflection") == {
        "type": "function",
        "function": {"name": "submit_research_reflection"},
    }


def test_current_dynamic_live_public_step_excludes_model_payload() -> None:
    private = _step(
        name="submit_research_reflection",
        arguments={"secret_model_atom": "private"},
    ).as_dict()
    public = _public_provider_step(private)
    rendered = json.dumps(public, ensure_ascii=False)
    assert "secret_model_atom" not in rendered
    assert "transient and never persisted" not in rendered
    assert '"tool_calls":' not in rendered
    assert public["reasoning_content_persisted"] is False


def test_current_dynamic_live_authority_rejects_budget_drift_first(
    tmp_path: Path,
) -> None:
    authority = {
        "schema_version": AUTHORITY_SCHEMA,
        "status": AUTHORITY_STATUS,
        "signed_at": "2026-08-23T00:00:00Z",
        "implementation_commit": "0" * 40,
        "case_key": "DELL",
        "cell_id": "CELL::value_capture",
        "execution_budget": {"maximum_model_calls": 99},
        "bound_inputs": {},
        "output_contract": {},
        "known_boundary": "x" * 100,
    }
    path = tmp_path / "authority.json"
    path.write_text(json.dumps(authority), encoding="utf-8")
    with pytest.raises(CurrentDynamicSingleUnitLiveError) as exc:
        validate_authority(authority, authority_path=path.resolve())
    assert exc.value.code == "current_dynamic_live_authority_budget_invalid"


def test_current_dynamic_runner_replaces_legacy_single_cell_active_entry() -> None:
    assert (
        "scripts/research/run_s3_current_dynamic_single_unit_zero_call.py"
        in active_baseline.PYTHON_ENTRYPOINTS
    )
    assert (
        "scripts/research/run_s3_current_dynamic_single_unit_live.py"
        in active_baseline.PYTHON_ENTRYPOINTS
    )
    assert (
        "scripts/research/run_s3_dynamic_single_cell_live.py"
        not in active_baseline.PYTHON_ENTRYPOINTS
    )


def test_current_dynamic_live_uses_provider_neutral_transport_dispatch() -> None:
    assert run.__kwdefaults__["executor"] is execute_agent_tool_step_exact_once


def test_current_dynamic_live_binds_feedback_by_runtime_round_not_receipt_field() -> None:
    feedback_by_round: dict[int, list[dict]] = {}
    receipt = {
        "feedback_id": "FEEDBACK::REAL",
        "model_visible_summary": "The runtime contract intentionally has no round_id field.",
    }
    _bind_round_feedback(
        feedback_by_round,
        round_index=1,
        feedback_receipts=[receipt],
    )
    assert _feedback_for_round(feedback_by_round, round_index=1) == [receipt]

    with pytest.raises(CurrentDynamicSingleUnitLiveError) as exc:
        _feedback_for_round(feedback_by_round, round_index=2)
    assert exc.value.code == "current_dynamic_live_feedback_round_missing"


def test_workpaper_successor_uses_canonical_provider_attempt_events() -> None:
    session = create_agent_session(
        session_id="SESSION::WORKPAPER-SUCCESSOR-TEST",
        run_id="RUN::WORKPAPER-SUCCESSOR-TEST",
        case_id="CASE::DELL",
        case_version="DELL::CURRENT::2026-08-06",
        as_of_date="2026-08-06",
        objective_ref="objective://dell/value-capture",
        active_plan_ref="plan://dell/value-capture/r3",
        created_at="2026-08-23T00:00:00Z",
    )
    events: list[dict] = []
    requested = append_session_event(
        events,
        session_id=session["session_id"],
        event_type="provider_attempt_requested",
        actor_id="S3.DynamicSingleUnitHarness",
        occurred_at="2026-08-23T00:00:01Z",
        attempt_id="DELL-WORKPAPER-R5",
        input_refs=("checkpoint://r3",),
    )
    events.append(requested)
    completed = append_session_event(
        events,
        session_id=session["session_id"],
        event_type="provider_attempt_completed",
        actor_id="PROVIDER::DEEPSEEK",
        occurred_at="2026-08-23T00:00:02Z",
        attempt_id="DELL-WORKPAPER-R5",
        output_refs=("capture://response",),
    )
    assert completed["event_type"] == "provider_attempt_completed"


def test_workpaper_successor_fake_runs_real_event_transport_contract_seam(
    tmp_path: Path,
) -> None:
    session = create_agent_session(
        session_id="SESSION::WORKPAPER-FULL-SEAM",
        run_id="RUN::WORKPAPER-FULL-SEAM",
        case_id="CASE::DELL",
        case_version="DELL::CURRENT::2026-08-06",
        as_of_date="2026-08-06",
        objective_ref="objective://dell/value-capture",
        active_plan_ref="plan://dell/value-capture/r3",
        created_at="2026-08-23T00:00:00Z",
    )
    context = {
        "context_digest": "context-digest",
        "cell_analysis_view": {
            "evidence_fact_catalog": [],
            "numeric_fact_catalog": [],
            "numeric_relation_catalog": [],
            "cell": {
                "cell_evidence_views": [{"evidence_ref": "EV::ONE"}],
                "allowed_numeric_refs": ["NUM::ONE"],
                "allowed_numeric_relation_refs": ["REL::ONE"],
                "residual_gap_cards": [{"gap_ref": "GAP::ONE"}],
            },
        },
        "agent": {"agent_id": "AGENT::VALUE_CAPTURE"},
    }
    payload = {
        "schema_version": "fin_ia_specialist_workpaper_v1_0",
        "agent_id": "AGENT::VALUE_CAPTURE",
        "thesis": "现有证据支持形成有限的价值获取判断，但尚不足以把公司层利润变化全部归因于单一产品。",
        "confidence": "medium",
        "sourced_claims": [
            {
                "claim": "现有公司披露可以支持公司层经营变化这一有限事实判断。",
                "authority": "sourced_fact",
                "evidence_refs": ["EV::ONE"],
                "numeric_refs": ["NUM::ONE"],
                "numeric_relation_refs": ["REL::ONE"],
            }
        ],
        "mechanism": "经营结果可能同时受到规模、组合、成本和费用杠杆影响，因此需要保留多因素解释并避免单因果归因。",
        "alternative_explanations": ["其他业务组合变化也可能解释公司层结果。"],
        "strongest_counterarguments": ["产品到公司利润的直接桥接仍然缺失。"],
        "remaining_gap_refs": ["GAP::ONE"],
        "what_would_change": ["若取得同期间产品收入和利润桥，应重新裁决。"],
        "cross_role_challenges": [],
        "stop_reason": "当前证据足以形成有限判断，剩余问题已绑定为明确缺口。",
    }
    calls: list[dict] = []

    def fake_executor(**kwargs: object) -> ChatCompletionToolStepResult:
        calls.append(dict(kwargs))
        return _step(name="submit_specialist_workpaper", arguments=payload)

    events: list[dict] = []
    provider_steps: list[dict] = []
    workpaper = _execute_workpaper_submission_attempt(
        events=events,
        session_id=session["session_id"],
        checkpoint_digest="checkpoint-digest",
        workpaper_context=context,
        submission_view=context,
        profile=SimpleNamespace(provider_id="deepseek"),
        capture_root=tmp_path / "captures",
        run_id=session["run_id"],
        attempt_id="DELL-WORKPAPER-R5",
        occurred_at="2026-08-23T00:00:01Z",
        submission_executor=fake_executor,
        provider_steps=provider_steps,
    )
    assert len(calls) == 1
    assert calls[0]["tool_choice"] is None
    assert [row["event_type"] for row in events] == [
        "provider_attempt_requested",
        "provider_attempt_completed",
    ]
    assert len(provider_steps) == 1
    assert workpaper["agent_id"] == "AGENT::VALUE_CAPTURE"
    assert len(workpaper["workpaper_digest"]) == 64
