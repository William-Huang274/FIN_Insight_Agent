from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

import scripts.research.run_s3_dynamic_five_cell_live as runner
from sec_agent.providers.chat_completions import (
    ChatCompletionResult,
    ChatCompletionToolStepResult,
)


def _analysis_step(tmp_path: Path, index: int) -> ChatCompletionResult:
    return ChatCompletionResult(
        status="completed_exact_once",
        provider_id="fixture",
        model="fixture-model",
        content=f"这是第{index}个单元的模型分析草案，只用于验证五单元编排和失败隔离。",
        finish_reason="stop",
        usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        request_capture_ref=str(tmp_path / f"analysis-request-{index}.json"),
        response_capture_ref=str(tmp_path / f"analysis-response-{index}.json"),
        request_digest=f"{index:x}" * 64,
        response_digest=f"{index + 1:x}" * 64,
        private_reasoning_fields_redacted=1,
    )


def _submission_step(
    tmp_path: Path,
    index: int,
    *,
    tool_name: str,
    arguments: object,
) -> ChatCompletionToolStepResult:
    return ChatCompletionToolStepResult(
        status="completed_exact_once_tool_step",
        provider_id="fixture",
        model="fixture-model",
        content="",
        reasoning_content="transient private reasoning",
        tool_calls=(
            {
                "id": f"call-{index}",
                "type": "function",
                "function": {
                    "name": tool_name,
                    "arguments": json.dumps(arguments, ensure_ascii=False),
                },
            },
        ),
        finish_reason="tool_calls",
        usage={"prompt_tokens": 8, "completion_tokens": 4, "total_tokens": 12},
        request_capture_ref=str(tmp_path / f"submit-request-{index}.json"),
        response_capture_ref=str(tmp_path / f"submit-response-{index}.json"),
        request_digest=f"{index + 2:x}" * 64,
        response_digest=f"{index + 3:x}" * 64,
        private_reasoning_fields_redacted=1,
    )


def _prepare_runner(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    successor_mode: bool = False,
) -> tuple[Path, Path, Path, dict[str, int]]:
    authority_path = tmp_path / "authority.json"
    private_root = tmp_path / "private"
    public_path = tmp_path / "public.json"
    capture_root = tmp_path / "captures"
    output = {
        "capture_root_ref": "captures",
        "private_output_root_ref": "private",
        "public_result_ref": "public.json",
        "run_id": "FIN013-S3-DELL-DYNAMIC-FIVE-CELL-TEST-R1",
        "planner_attempt_id": "planner-01",
        "cell_attempt_ids": {
            cell_id: {
                "analysis_attempt_id": f"analysis-{index:02d}",
                "submission_attempt_id": f"submission-{index:02d}",
            }
            for index, cell_id in enumerate(runner.REQUIRED_CELL_IDS, start=1)
        },
        "synthesis_attempt_ids": {
            "analysis_attempt_id": "synthesis-analysis-01",
            "submission_attempt_id": "synthesis-submission-01",
        },
        "product_publication": "forbidden",
    }
    if successor_mode:
        output.pop("planner_attempt_id")
    authority = {
        "schema_version": (
            runner.SUCCESSOR_AUTHORITY_SCHEMA if successor_mode else "fixture"
        ),
        "implementation_commit": "a" * 40,
        "known_boundary": "fixture orchestration proof; not product acceptance",
        "output_contract": output,
    }
    if successor_mode:
        authority["bound_inputs"] = {
            "predecessor_plan_digest": "plan-digest",
            "expected_evidence_pack_artifact_digest": "artifact",
            "expected_evidence_pack_payload_digest": "payload",
            "expected_research_input_digest": "research-input",
        }
    authority_path.write_text(json.dumps(authority), encoding="utf-8")
    profile_path = tmp_path / "profile.json"
    objective_path = tmp_path / "objective.json"
    for path in (profile_path, objective_path):
        path.write_text("{}", encoding="utf-8")
    paths = {
        "planner_profile_ref": profile_path,
        "analysis_profile_ref": profile_path,
        "submission_profile_ref": profile_path,
        "objective_ref": objective_path,
        "truth_spine_policy_ref": profile_path,
        "consumer_policy_ref": profile_path,
    }
    values = {authority_path: authority, profile_path: {}, objective_path: {}}
    if successor_mode:
        predecessor_path = tmp_path / "predecessor.json"
        predecessor_authority_path = tmp_path / "predecessor-authority.json"
        predecessor_public_path = tmp_path / "predecessor-public.json"
        predecessor_path.write_text("{}", encoding="utf-8")
        predecessor_authority_path.write_text("{}", encoding="utf-8")
        predecessor_public_path.write_text("{}", encoding="utf-8")
        paths["predecessor_private_result_ref"] = predecessor_path
        paths["predecessor_authority_ref"] = predecessor_authority_path
        paths["predecessor_public_result_ref"] = predecessor_public_path
        values[predecessor_path] = {
            "planner_step": {"finish_reason": "stop"},
            "planner_output": {"atoms": []},
            "compiled_plan": {
                "plan_digest": "plan-digest",
                "proposed_atoms": [{"atom_id": "A1"}],
                "planner_atoms": [{"atom_id": "A1"}],
                "deferred_atoms": [],
            },
            "controlled_plan": {
                "compiled_plan": {"plan_digest": "plan-digest"}
            },
        }
        values[predecessor_authority_path] = {}
        values[predecessor_public_path] = {}
    monkeypatch.setattr(runner, "_json", lambda path: values[path])
    monkeypatch.setattr(
        runner,
        "validate_authority",
        lambda *_args, **_kwargs: paths,
    )
    destinations = {
        "captures": capture_root,
        "private": private_root,
        "public.json": public_path,
    }
    monkeypatch.setattr(runner, "_resolve", lambda ref: destinations[str(ref)])
    monkeypatch.setattr(runner, "_relative", lambda path: Path(path).as_posix())
    monkeypatch.setattr(runner, "_sha", lambda _path: "f" * 64)
    monkeypatch.setattr(runner, "load_chat_completion_profile", lambda _: object())
    objective = SimpleNamespace(
        objective_id="OBJECTIVE::DELL::FIVE-CELL",
        as_dict=lambda: {"objective_id": "OBJECTIVE::DELL::FIVE-CELL"},
    )
    monkeypatch.setattr(
        runner,
        "_compile_planner_contract",
        lambda _paths: (
            object(),
            object(),
            object(),
            objective,
            ({"role": "user", "content": "plan"},),
        ),
    )
    plan = SimpleNamespace(
        plan_digest="plan-digest",
        as_dict=lambda: {
            "plan_digest": "plan-digest",
            "proposed_atoms": [{"atom_id": "A1"}],
            "planner_atoms": [{"atom_id": "A1"}],
            "deferred_atoms": [],
        },
    )
    monkeypatch.setattr(runner, "parse_research_planner_output", lambda _: {"atoms": []})
    monkeypatch.setattr(runner, "compile_research_plan", lambda *_a, **_k: plan)

    class Retrieval:
        def execute_controlled_plan(self, *_args, **_kwargs):
            return {"compiled_plan": {"plan_digest": "plan-digest"}}

    class Evidence:
        def get_case(self, *_args, **_kwargs):
            return {"artifact_digest": "artifact", "pack_payload_digest": "payload"}

    monkeypatch.setattr(runner, "_services", lambda: (Evidence(), Retrieval()))
    research_input = {
        "cells": [{"cell_id": cell_id} for cell_id in runner.REQUIRED_CELL_IDS],
        "research_input_digest": "research-input",
    }
    monkeypatch.setattr(
        runner,
        "compile_dynamic_research_input_projection",
        lambda **_: {
            "dynamic_research_input": research_input,
            "evidence_responses": {
                "summary": {"response_count": 5},
                "evidence_response_set_digest": "response-set",
            },
            "candidate_promotions": 0,
        },
    )
    monkeypatch.setattr(
        runner,
        "compile_five_cell_analysis_messages",
        lambda **kwargs: (
            {"role": "user", "content": f"analyze:{kwargs['cell_id']}"},
        ),
    )
    monkeypatch.setattr(
        runner,
        "compile_five_cell_submission",
        lambda **kwargs: (
            ({"role": "user", "content": f"submit:{kwargs['cell_id']}"},),
            {
                "type": "function",
                "function": {
                    "name": runner.SUBMIT_RESEARCH_JUDGMENT_TOOL,
                    "description": kwargs["cell_id"],
                },
            },
        ),
    )

    def validate_cells(payload, *, required_cell_ids, **_kwargs):
        cells = [dict(row) for row in payload["cells"]]
        assert {row["cell_id"] for row in cells} == set(required_cell_ids)
        result = {"cells": cells}
        if len(cells) == 5:
            result["judgment_output_digest"] = "judgment-output"
        return result

    monkeypatch.setattr(runner, "validate_current_research_output", validate_cells)
    monkeypatch.setattr(
        runner,
        "compile_current_research_deliverable",
        lambda **kwargs: {
            "cells": [dict(row) for row in kwargs["judgment_output"]["cells"]],
            "deliverable_digest": "cell-workpaper",
        },
    )
    monkeypatch.setattr(
        runner,
        "compile_five_cell_synthesis_analysis_messages",
        lambda **_: ({"role": "user", "content": "synthesize"},),
    )
    monkeypatch.setattr(
        runner,
        "compile_five_cell_synthesis_submission",
        lambda **_: (
            ({"role": "user", "content": "submit synthesis"},),
            {"type": "function", "function": {"name": "submit_five_cell_synthesis"}},
        ),
    )
    monkeypatch.setattr(
        runner,
        "validate_five_cell_synthesis",
        lambda payload, **_: {**dict(payload), "synthesis_digest": "synthesis"},
    )
    monkeypatch.setattr(
        runner,
        "compile_five_cell_report",
        lambda **_: {"report_digest": "report"},
    )
    counters = {"analysis": 0, "submission": 0}
    return authority_path, private_root, public_path, counters


def _planner(tmp_path: Path) -> ChatCompletionResult:
    return ChatCompletionResult(
        status="completed_exact_once",
        provider_id="fixture",
        model="fixture-model",
        content="{}",
        finish_reason="stop",
        usage={"total_tokens": 10},
        request_capture_ref=str(tmp_path / "planner-request.json"),
        response_capture_ref=str(tmp_path / "planner-response.json"),
        request_digest="a" * 64,
        response_digest="b" * 64,
        private_reasoning_fields_redacted=1,
    )


def test_five_cell_live_runs_all_cells_then_synthesis_and_redacts_public_result(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    authority_path, private_root, public_path, counters = _prepare_runner(
        monkeypatch, tmp_path
    )

    def analyze(**_kwargs):
        counters["analysis"] += 1
        return _analysis_step(tmp_path, counters["analysis"])

    def submit(**kwargs):
        counters["submission"] += 1
        tool = kwargs["tools"][0]["function"]
        if tool["name"] == "submit_five_cell_synthesis":
            arguments = {"executive_thesis": "all cells synthesized"}
        else:
            arguments = {"cell_id": tool["description"]}
        return _submission_step(
            tmp_path,
            counters["submission"],
            tool_name=tool["name"],
            arguments=arguments,
        )

    result = runner.run(
        authority_path,
        planner_executor=lambda **_: _planner(tmp_path),
        analysis_executor=analyze,
        submission_executor=submit,
    )

    assert result["status"].startswith("completed_")
    assert result["execution"]["model_calls_attempted"] == 13
    assert result["execution"]["cell_judgments_accepted"] == 5
    assert result["acceptance"]["cross_cell_synthesis_contract_valid"] is True
    assert result["acceptance"]["five_cell_report_compiled"] is True
    assert counters == {"analysis": 6, "submission": 6}
    assert public_path.is_file()
    assert (private_root / "full_result.json").is_file()
    rendered_public = public_path.read_text(encoding="utf-8")
    assert "transient private reasoning" not in rendered_public
    assert "分析草案" not in rendered_public
    assert '"tool_calls":' not in rendered_public


def test_five_cell_successor_reuses_prefix_and_attempts_only_twelve_nodes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    authority_path, private_root, public_path, counters = _prepare_runner(
        monkeypatch, tmp_path, successor_mode=True
    )

    def planner_must_not_run(**_kwargs):
        raise AssertionError("successor must not rerun planner")

    def analyze(**_kwargs):
        counters["analysis"] += 1
        return _analysis_step(tmp_path, counters["analysis"])

    def submit(**kwargs):
        counters["submission"] += 1
        tool = kwargs["tools"][0]["function"]
        arguments = (
            {"executive_thesis": "all cells synthesized"}
            if tool["name"] == "submit_five_cell_synthesis"
            else {"cell_id": tool["description"]}
        )
        return _submission_step(
            tmp_path,
            counters["submission"],
            tool_name=tool["name"],
            arguments=arguments,
        )

    result = runner.run(
        authority_path,
        planner_executor=planner_must_not_run,
        analysis_executor=analyze,
        submission_executor=submit,
    )

    assert result["schema_version"] == runner.SUCCESSOR_RESULT_SCHEMA
    assert result["status"].startswith("completed_")
    assert result["planner"]["reused_from_predecessor"] is True
    assert result["execution"]["model_calls_attempted"] == 12
    assert result["execution"]["maximum_model_calls"] == 12
    assert result["execution"]["planner_calls_completed"] == 0
    assert result["execution"]["planner_calls_reused"] == 1
    assert result["execution"]["current_S1_S2_executed"] is False
    assert result["execution"]["current_S1_S2_reused"] is True
    assert result["acceptance"]["natural_planner_reused_not_rerun"] is True
    assert result["acceptance"]["current_S1_S2_reused_not_rerun"] is True
    assert counters == {"analysis": 6, "submission": 6}
    assert public_path.is_file()
    assert (private_root / "full_result.json").is_file()


def test_five_cell_live_continues_after_one_cell_failure_and_skips_synthesis(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    authority_path, private_root, public_path, counters = _prepare_runner(
        monkeypatch, tmp_path
    )

    def analyze(**_kwargs):
        counters["analysis"] += 1
        return _analysis_step(tmp_path, counters["analysis"])

    def submit(**kwargs):
        counters["submission"] += 1
        tool = kwargs["tools"][0]["function"]
        name = tool["name"]
        if counters["submission"] == 2:
            name = "wrong_tool"
        return _submission_step(
            tmp_path,
            counters["submission"],
            tool_name=name,
            arguments={"cell_id": tool["description"]},
        )

    result = runner.run(
        authority_path,
        planner_executor=lambda **_: _planner(tmp_path),
        analysis_executor=analyze,
        submission_executor=submit,
    )

    assert result["status"] == "terminal_failed_or_partial_no_retry"
    assert result["execution"]["model_calls_attempted"] == 11
    assert result["execution"]["cell_judgments_accepted"] == 4
    assert counters == {"analysis": 5, "submission": 5}
    assert result["cells"][1]["failure_code"] == (
        "five_cell_live_submission_tool_invalid"
    )
    assert result["synthesis"]["failure_code"] == (
        "five_cell_synthesis_requires_all_cells"
    )
    assert result["acceptance"]["five_cell_report_compiled"] is False
    assert public_path.is_file()
    assert (private_root / "full_result.json").is_file()
