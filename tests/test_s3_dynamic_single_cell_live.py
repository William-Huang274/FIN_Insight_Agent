from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from scripts.research.run_s3_dynamic_single_cell_live import (
    DynamicSingleCellLiveError,
    _public_provider_step,
    _require_controlled_plan_binding,
    _tool_arguments,
)
import scripts.research.run_s3_dynamic_single_cell_live as runner
from sec_agent.research.reviewed_evidence_pack import canonical_digest
from sec_agent.providers.chat_completions import ChatCompletionToolStepResult


def _step(*, tool_name: str, arguments: object, finish_reason: str = "tool_calls"):
    return ChatCompletionToolStepResult(
        status="completed_exact_once",
        provider_id="deepseek",
        model="deepseek-v4-pro",
        content="",
        reasoning_content="private reasoning must not persist",
        tool_calls=(
            {
                "id": "call-1",
                "type": "function",
                "function": {
                    "name": tool_name,
                    "arguments": json.dumps(arguments, ensure_ascii=False),
                },
            },
        ),
        finish_reason=finish_reason,
        usage={"prompt_tokens": 10, "completion_tokens": 5},
        request_capture_ref=(
            ROOT / "data/captures/provider_calls/run/attempt/request.json"
        ).as_posix(),
        response_capture_ref=(
            ROOT / "data/captures/provider_calls/run/attempt/response.json"
        ).as_posix(),
        request_digest="a" * 64,
        response_digest="b" * 64,
        private_reasoning_fields_redacted=1,
    )


def test_dynamic_live_tool_arguments_require_exact_single_expected_tool() -> None:
    result = _step(
        tool_name="submit_research_thesis",
        arguments={"claim_relation_ref": "CR::1"},
    )
    assert _tool_arguments(
        result, expected_tool="submit_research_thesis"
    ) == {"claim_relation_ref": "CR::1"}

    with pytest.raises(DynamicSingleCellLiveError) as exc:
        _tool_arguments(result, expected_tool="submit_research_mechanism")
    assert exc.value.code == "dynamic_live_submission_tool_invalid"


def test_dynamic_live_public_step_excludes_content_tools_and_reasoning() -> None:
    private = _step(
        tool_name="submit_research_thesis",
        arguments={"secret_model_atom": "must remain private"},
    ).as_dict()
    public = _public_provider_step(private)
    assert set(public) == {
        "finish_reason",
        "usage",
        "request_digest",
        "response_digest",
        "request_capture_ref",
        "response_capture_ref",
    }
    rendered = json.dumps(public, ensure_ascii=False)
    assert "secret_model_atom" not in rendered
    assert "private reasoning" not in rendered
    assert '"tool_calls":' not in rendered


def test_dynamic_live_requires_service_to_execute_the_exact_compiled_plan() -> None:
    _require_controlled_plan_binding(
        {"compiled_plan": {"plan_digest": "expected"}},
        expected_plan_digest="expected",
    )

    for drifted in (
        {},
        {"compiled_plan": {}},
        {"compiled_plan": {"plan_digest": "different"}},
    ):
        with pytest.raises(DynamicSingleCellLiveError) as exc:
            _require_controlled_plan_binding(
                drifted, expected_plan_digest="expected"
            )
        assert exc.value.code == "dynamic_live_plan_digest_drift"


def test_dynamic_successor_replays_only_the_failed_counter_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = {"projection_digest": "counter-context"}
    messages = ({"role": "user", "content": "counter analysis"},)
    monkeypatch.setattr(
        runner,
        "compile_finance_micro_fragment_context",
        lambda **_: context,
    )
    monkeypatch.setattr(
        runner,
        "compile_finance_micro_fragment_analysis_messages",
        lambda _: messages,
    )
    predecessor = {
        "surface_projection": {
            "claim_surface_research_input": {"research_input_digest": "input"}
        },
        "accepted_fragments": {
            "submit_research_thesis": {"fragment": "thesis"},
            "submit_research_mechanism": {"fragment": "mechanism"},
        },
        "fragment_steps": [
            {
                "fragment_tool": "submit_research_counterargument_and_wwc",
                "fragment_context": context,
                "analysis_messages_digest": canonical_digest(list(messages)),
                "analysis_step": {},
                "submission_step": {},
                "validated_fragment": {},
            }
        ],
    }

    replay = runner._compile_successor_replay_state(predecessor)
    assert set(replay["accepted_fragments"]) == {
        "submit_research_thesis",
        "submit_research_mechanism",
    }
    assert replay["predecessor_fragment_context_digest"] == "counter-context"
    assert replay["analysis_messages_digest"] == canonical_digest(
        list(messages)
    )

    predecessor["fragment_steps"][0]["analysis_messages_digest"] = "drift"
    with pytest.raises(DynamicSingleCellLiveError) as exc:
        runner._compile_successor_replay_state(predecessor)
    assert exc.value.code == "dynamic_successor_failed_fragment_replay_drift"

    missing_prefix = deepcopy(predecessor)
    missing_prefix["fragment_steps"][0]["analysis_messages_digest"] = (
        canonical_digest(list(messages))
    )
    del missing_prefix["accepted_fragments"]["submit_research_mechanism"]
    with pytest.raises(DynamicSingleCellLiveError) as exc:
        runner._compile_successor_replay_state(missing_prefix)
    assert exc.value.code == "dynamic_successor_predecessor_prefix_invalid"

    extra_fragment = deepcopy(predecessor)
    extra_fragment["fragment_steps"][0]["analysis_messages_digest"] = (
        canonical_digest(list(messages))
    )
    extra_fragment["accepted_fragments"][
        "submit_research_counterargument_and_wwc"
    ] = {"fragment": "must not already exist"}
    with pytest.raises(DynamicSingleCellLiveError) as exc:
        runner._compile_successor_replay_state(extra_fragment)
    assert exc.value.code == "dynamic_successor_predecessor_prefix_invalid"
