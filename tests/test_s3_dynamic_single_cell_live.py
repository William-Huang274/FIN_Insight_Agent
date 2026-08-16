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


def test_dynamic_successor_validates_R1_inputs_from_historical_commit() -> None:
    authority_path = (
        ROOT
        / "configs/research/evals/"
        "fin_ia_0_1_3_s3_dell_dynamic_value_capture_chat_live_"
        "authority_v1_0.json"
    )
    authority = json.loads(authority_path.read_text(encoding="utf-8"))

    runner._validate_historical_authority_inputs(authority)

    drifted = deepcopy(authority)
    drifted["bound_inputs"]["runner_sha256"] = "0" * 64
    with pytest.raises(DynamicSingleCellLiveError) as exc:
        runner._validate_historical_authority_inputs(drifted)
    assert exc.value.code == (
        "dynamic_successor_historical_bound_input_drift:runner_ref"
    )


def test_dynamic_successor_bound_set_includes_current_runtime_policies() -> None:
    authority_path = (
        ROOT
        / "configs/research/evals/"
        "fin_ia_0_1_3_s3_dell_dynamic_counter_successor_chat_live_"
        "authority_v1_1.json"
    )
    authority = json.loads(authority_path.read_text(encoding="utf-8"))
    authority["bound_inputs"]["runner_sha256"] = runner._sha(
        ROOT / authority["bound_inputs"]["runner_ref"]
    )
    authority["bound_inputs"]["bounded_loop_sha256"] = runner._sha(
        ROOT / authority["bound_inputs"]["bounded_loop_ref"]
    )

    paths = runner._successor_bound_paths(authority)

    assert paths["loop_policy_ref"].name.endswith("loop_policy_v1_1.json")
    assert paths["dynamic_micro_policy_ref"].name.endswith(
        "dynamic_micro_judgment_policy_v1_0.json"
    )


def test_dynamic_temporal_repair_replays_rejected_fragment_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    surface_input = {"research_input_digest": "dynamic-input"}
    prefix = {
        "submit_research_thesis": {"fragment": "thesis"},
        "submit_research_mechanism": {"fragment": "mechanism"},
    }
    rejected = {
        "cell_id": "CELL::value_capture",
        "counterargument_atom": "同期关系未绑定",
    }
    observed: dict[str, object] = {}

    def compile_repair(**kwargs):
        observed.update(kwargs)
        return {
            "repair_messages_digest": "repair-messages",
            "repair_feedback": {"rejected_at": "fragment_validation"},
            "maximum_repair_turns": 1,
        }

    monkeypatch.setattr(
        runner,
        "compile_finance_micro_fragment_validation_repair_successor",
        compile_repair,
    )
    replay = runner._compile_temporal_repair_replay_state(
        predecessor_full={
            "predecessor_accepted_fragments": prefix,
            "validated_fragment": rejected,
        },
        base_predecessor_full={
            "surface_projection": {
                "claim_surface_research_input": surface_input
            }
        },
    )

    assert replay["surface_input"] == surface_input
    assert replay["accepted_fragments"] == prefix
    assert replay["rejected_fragment"] == rejected
    assert observed["terminal_failure_code"] == (
        "finance_loop_micro_temporal_relation_unbound"
    )
    assert observed["rejected_fragment"] == rejected
    assert observed["accepted_prefix_fragments"] == prefix

    with pytest.raises(DynamicSingleCellLiveError) as exc:
        runner._compile_temporal_repair_replay_state(
            predecessor_full={
                "predecessor_accepted_fragments": {
                    "submit_research_thesis": {"fragment": "thesis"}
                },
                "validated_fragment": rejected,
            },
            base_predecessor_full={
                "surface_projection": {
                    "claim_surface_research_input": surface_input
                }
            },
        )
    assert exc.value.code == (
        "dynamic_temporal_repair_predecessor_state_invalid"
    )


def test_dynamic_temporal_repair_runner_uses_one_submission_only(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    authority_path = tmp_path / "authority.json"
    authority_path.write_text("{}", encoding="utf-8")
    predecessor_path = tmp_path / "predecessor.json"
    base_path = tmp_path / "base.json"
    public_predecessor_path = tmp_path / "predecessor_public.json"
    profile_path = tmp_path / "profile.json"
    loop_path = tmp_path / "loop.json"
    micro_path = tmp_path / "micro.json"
    output_path = tmp_path / "result.json"
    private_root = tmp_path / "private"
    capture_root = tmp_path / "captures"
    authority = {
        "implementation_commit": "a" * 40,
        "known_boundary": "one repair only",
        "output_contract": {
            "capture_root_ref": "captures",
            "private_output_root_ref": "private",
            "public_result_ref": "result.json",
            "run_id": "repair-run",
            "submission_attempt_id": "repair-submission",
            "product_publication": "forbidden",
        },
    }
    predecessor_full = {
        "full_result_digest": "predecessor-full",
    }
    base_full = {"full_result_digest": "base-full"}
    predecessor_public = {"result_digest": "predecessor-public"}
    values = {
        authority_path: authority,
        predecessor_path: predecessor_full,
        base_path: base_full,
        public_predecessor_path: predecessor_public,
        profile_path: {},
        loop_path: {},
        micro_path: {},
    }
    monkeypatch.setattr(runner, "_json", lambda path: values[path])
    monkeypatch.setattr(
        runner,
        "validate_temporal_repair_authority",
        lambda *_args, **_kwargs: {
            "predecessor_private_result_ref": predecessor_path,
            "base_predecessor_private_result_ref": base_path,
            "predecessor_public_result_ref": public_predecessor_path,
            "submission_profile_ref": profile_path,
            "loop_policy_ref": loop_path,
            "dynamic_micro_policy_ref": micro_path,
        },
    )
    resolved = {
        "captures": capture_root,
        "private": private_root,
        "result.json": output_path,
    }
    monkeypatch.setattr(runner, "_resolve", lambda ref: resolved[ref])
    monkeypatch.setattr(runner, "_relative", lambda path: Path(path).as_posix())
    surface_input = {
        "cells": [{"cell_id": "CELL::value_capture"}],
    }
    counter = {
        "cell_id": "CELL::value_capture",
        "counterargument_atom": "不同报告期不能写成同期。",
    }
    monkeypatch.setattr(
        runner,
        "_compile_temporal_repair_replay_state",
        lambda **_: {
            "surface_input": surface_input,
            "accepted_fragments": {
                "submit_research_thesis": {"fragment": "thesis"},
                "submit_research_mechanism": {"fragment": "mechanism"},
            },
            "rejected_fragment": {"fragment": "rejected"},
            "repair": {
                "repair_messages": [{"role": "user", "content": "repair"}],
                "repair_messages_digest": "repair-messages",
                "repair_feedback": {"rejected_at": "fragment_validation"},
                "repair_feedback_digest": "repair-feedback",
                "fragment_context": {"schema_version": "context-v1"},
                "fragment_context_digest": "context-digest",
            },
        },
    )
    monkeypatch.setattr(runner, "load_chat_completion_profile", lambda _: object())
    monkeypatch.setattr(runner, "_runtime_contracts", lambda: (object(), object(), object()))
    monkeypatch.setattr(runner, "load_dynamic_micro_judgment_policy", lambda _: object())
    monkeypatch.setattr(runner, "load_bounded_finance_loop_policy", lambda _: object())
    monkeypatch.setattr(runner, "scope_bounded_finance_micro_judgment_policy", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(
        runner,
        "compile_finance_micro_judgment_tools",
        lambda **_: [
            {
                "type": "function",
                "function": {
                    "name": "submit_research_counterargument_and_wwc"
                },
            }
        ],
    )
    monkeypatch.setattr(
        runner,
        "validate_finance_micro_judgment_fragment",
        lambda **kwargs: kwargs["arguments"],
    )
    terminal = {
        "judgment_status": "insufficient_evidence",
        "inference_authority": "not_inferable",
        "causal_bridge_authority": "bridge_unavailable",
    }
    monkeypatch.setattr(
        runner,
        "compile_finance_micro_judgment_fragments",
        lambda *_args, **_kwargs: terminal,
    )
    monkeypatch.setattr(
        runner,
        "compile_current_research_deliverable",
        lambda **_: {"deliverable_digest": "deliverable"},
    )
    calls: list[dict[str, object]] = []

    def submit(**kwargs):
        calls.append(kwargs)
        return _step(
            tool_name="submit_research_counterargument_and_wwc",
            arguments=counter,
        )

    result = runner.run_temporal_repair(
        authority_path,
        submission_executor=submit,
    )

    assert len(calls) == 1
    assert result["status"].startswith("completed_")
    assert result["execution"]["fresh_model_calls_attempted"] == 1
    assert result["execution"]["planner_calls_rerun"] == 0
    assert result["execution"]["current_S1_S2_rerun"] == 0
    assert result["execution"]["new_evidence"] == 0
    assert output_path.is_file()
    assert (private_root / "full_result.json").is_file()
