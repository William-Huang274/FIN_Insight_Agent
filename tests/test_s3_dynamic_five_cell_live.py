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
from sec_agent.research.reviewed_evidence_pack import canonical_digest


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
    partial_successor_mode: bool = False,
    node_successor_mode: bool = False,
    claim_surface_successor_mode: bool = False,
    value_repair_successor_mode: bool = False,
) -> tuple[Path, Path, Path, dict[str, int]]:
    assert sum(
        (
            successor_mode,
            partial_successor_mode,
            node_successor_mode,
            claim_surface_successor_mode,
            value_repair_successor_mode,
        )
    ) <= 1
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
    if (
        successor_mode
        or partial_successor_mode
        or node_successor_mode
        or claim_surface_successor_mode
        or value_repair_successor_mode
    ):
        output.pop("planner_attempt_id")
    if partial_successor_mode:
        output["cell_attempt_ids"] = {
            cell_id: output["cell_attempt_ids"][cell_id]
            for cell_id in runner.PARTIAL_SUCCESSOR_REMAINING_CELL_IDS
        }
    if node_successor_mode:
        output["cell_attempt_ids"] = {
            cell_id: {
                "submission_attempt_id": output["cell_attempt_ids"][cell_id][
                    "submission_attempt_id"
                ]
            }
            for cell_id in runner.NODE_SUCCESSOR_RESUBMISSION_CELL_IDS
        }
    if value_repair_successor_mode:
        output["cell_attempt_ids"] = {
            cell_id: {
                "submission_attempt_id": output["cell_attempt_ids"][cell_id][
                    "submission_attempt_id"
                ]
            }
            for cell_id in runner.VALUE_REPAIR_SUCCESSOR_RESUBMISSION_CELL_IDS
        }
    authority = {
        "schema_version": (
            runner.VALUE_REPAIR_SUCCESSOR_AUTHORITY_SCHEMA
            if value_repair_successor_mode
            else (
                runner.CLAIM_SURFACE_SUCCESSOR_AUTHORITY_SCHEMA
                if claim_surface_successor_mode
                else (
                    runner.NODE_SUCCESSOR_AUTHORITY_SCHEMA
                    if node_successor_mode
                    else (
                        runner.PARTIAL_SUCCESSOR_AUTHORITY_SCHEMA
                        if partial_successor_mode
                        else (
                            runner.SUCCESSOR_AUTHORITY_SCHEMA
                            if successor_mode
                            else "fixture"
                        )
                    )
                )
            )
        ),
        "implementation_commit": "a" * 40,
        "known_boundary": "fixture orchestration proof; not product acceptance",
        "output_contract": output,
    }
    if (
        successor_mode
        or partial_successor_mode
        or node_successor_mode
        or claim_surface_successor_mode
        or value_repair_successor_mode
    ):
        authority["bound_inputs"] = {
            "predecessor_plan_digest": "plan-digest",
            "expected_evidence_pack_artifact_digest": "artifact",
            "expected_evidence_pack_payload_digest": "payload",
            **(
                {
                    "expected_base_research_input_digest": "research-input",
                    "expected_claim_surface_research_input_digest": (
                        "claim-surface-input"
                    ),
                }
                if claim_surface_successor_mode or value_repair_successor_mode
                else {"expected_research_input_digest": "research-input"}
            ),
        }
    if partial_successor_mode:
        authority["reused_cell_ids"] = list(
            runner.PARTIAL_SUCCESSOR_REUSED_CELL_IDS
        )
        authority["remaining_cell_ids"] = list(
            runner.PARTIAL_SUCCESSOR_REMAINING_CELL_IDS
        )
    if node_successor_mode:
        authority["reused_cell_ids"] = list(runner.NODE_SUCCESSOR_REUSED_CELL_IDS)
        authority["resubmission_cell_ids"] = list(
            runner.NODE_SUCCESSOR_RESUBMISSION_CELL_IDS
        )
    if value_repair_successor_mode:
        authority["reused_cell_ids"] = list(
            runner.VALUE_REPAIR_SUCCESSOR_REUSED_CELL_IDS
        )
        authority["resubmission_cell_ids"] = list(
            runner.VALUE_REPAIR_SUCCESSOR_RESUBMISSION_CELL_IDS
        )
    if claim_surface_successor_mode:
        authority["rerun_cell_ids"] = list(runner.REQUIRED_CELL_IDS)
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
    if claim_surface_successor_mode or value_repair_successor_mode:
        paths["claim_authority_template_ref"] = profile_path
        paths["claim_surface_template_ref"] = profile_path
    values = {authority_path: authority, profile_path: {}, objective_path: {}}
    if (
        successor_mode
        or partial_successor_mode
        or node_successor_mode
        or claim_surface_successor_mode
        or value_repair_successor_mode
    ):
        predecessor_path = tmp_path / "predecessor.json"
        predecessor_authority_path = tmp_path / "predecessor-authority.json"
        predecessor_public_path = tmp_path / "predecessor-public.json"
        predecessor_path.write_text("{}", encoding="utf-8")
        predecessor_authority_path.write_text("{}", encoding="utf-8")
        predecessor_public_path.write_text("{}", encoding="utf-8")
        paths["predecessor_private_result_ref"] = predecessor_path
        paths["predecessor_authority_ref"] = predecessor_authority_path
        paths["predecessor_public_result_ref"] = predecessor_public_path
        predecessor = {
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
        if (
            partial_successor_mode
            or node_successor_mode
            or value_repair_successor_mode
        ):
            valid_ids = (
                set(runner.VALUE_REPAIR_SUCCESSOR_REUSED_CELL_IDS)
                if value_repair_successor_mode
                else set(runner.PARTIAL_SUCCESSOR_REUSED_CELL_IDS)
                if partial_successor_mode
                else set(runner.NODE_SUCCESSOR_REUSED_CELL_IDS)
            )
            predecessor["cell_steps"] = [
                {
                    "analysis_messages_digest": f"analysis-{index}",
                    "analysis_step": _analysis_step(tmp_path, index).as_dict(),
                    "cell_id": cell_id,
                    "failure_capture_ref": "",
                    "failure_code": (
                        "" if cell_id in valid_ids else "saved_failure"
                    ),
                    "failure_phase": (
                        "" if cell_id in valid_ids else "saved_phase"
                    ),
                    "raw_model_arguments": {"cell_id": cell_id},
                    "submission_messages_digest": f"submission-{index}",
                    "submission_step": (
                        {"finish_reason": "tool_calls"}
                        if cell_id in valid_ids
                        else {}
                    ),
                    "tool_schema_digest": f"tool-{index}",
                    "validated_cell": (
                        {"cell_id": cell_id} if cell_id in valid_ids else {}
                    ),
                }
                for index, cell_id in enumerate(
                    runner.REQUIRED_CELL_IDS, start=1
                )
            ]
            if node_successor_mode:
                authority["bound_inputs"]["expected_reused_analysis_digests"] = {
                    row["cell_id"]: runner._reused_analysis_digest(row)
                    for row in predecessor["cell_steps"]
                    if row["cell_id"]
                    in runner.NODE_SUCCESSOR_RESUBMISSION_CELL_IDS
                }
            if value_repair_successor_mode:
                value_row = next(
                    row
                    for row in predecessor["cell_steps"]
                    if row["cell_id"] == "CELL::value_capture"
                )
                authority["bound_inputs"][
                    "expected_value_analysis_reuse_digest"
                ] = runner._reused_analysis_digest(value_row)
                authority["bound_inputs"][
                    "expected_rejected_arguments_digest"
                ] = canonical_digest(value_row["raw_model_arguments"])
        values[predecessor_path] = predecessor
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
    monkeypatch.setattr(
        runner,
        "_validate_reused_analysis_capture",
        lambda row: {
            "analysis_reuse_digest": runner._reused_analysis_digest(row),
            "content_digest": "capture-content",
        },
    )
    monkeypatch.setattr(
        runner,
        "project_deepseek_strict_tool",
        lambda tool: (
            tool,
            {
                "projection_digest": "strict-projection",
                "finance_contract_weakened": False,
            },
        ),
    )
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
        "compile_dynamic_claim_surface_projection",
        lambda **_: {
            "claim_surface_research_input": {
                **research_input,
                "research_input_digest": "claim-surface-input",
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
    monkeypatch.setattr(
        runner,
        "compile_five_cell_submission_repair",
        lambda **kwargs: (
            (
                {
                    "role": "user",
                    "content": f"repair:{kwargs['cell_id']}",
                },
            ),
            {
                "type": "function",
                "function": {
                    "name": runner.SUBMIT_RESEARCH_JUDGMENT_TOOL,
                    "description": kwargs["cell_id"],
                },
            },
            {
                "schema_version": "fixture-repair-receipt",
                "rejected_submission_promoted": False,
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


def _captured_analysis_row(tmp_path: Path) -> tuple[dict, Path, Path]:
    messages = [{"role": "user", "content": "analyze bounded evidence"}]
    request_body = {"model": "fixture", "messages": messages}
    response_body = {
        "choices": [
            {
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": "bounded draft"},
            }
        ]
    }
    request_path = tmp_path / "captured-request.json"
    response_path = tmp_path / "captured-response.json"
    request = {
        "run_id": "R3",
        "attempt_id": "VALUE-ANALYSIS",
        "request_body": request_body,
        "request_digest": canonical_digest(request_body),
    }
    response = {
        "run_id": "R3",
        "attempt_id": "VALUE-ANALYSIS",
        "response_body": response_body,
        "response_digest": canonical_digest(response_body),
        "response_body_complete": True,
        "response_body_persisted": True,
        "eligible_for_contract_parse": True,
        "partial_response_received": False,
        "truncated": False,
        "transport_error": "",
    }
    request_path.write_text(json.dumps(request), encoding="utf-8")
    response_path.write_text(json.dumps(response), encoding="utf-8")
    row = {
        "cell_id": "CELL::value_capture",
        "analysis_messages_digest": canonical_digest(messages),
        "analysis_step": {
            "finish_reason": "stop",
            "content": "bounded draft",
            "request_capture_ref": str(request_path),
            "response_capture_ref": str(response_path),
            "request_digest": request["request_digest"],
            "response_digest": response["response_digest"],
        },
    }
    return row, request_path, response_path


def test_reused_analysis_capture_is_content_and_transport_bound(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    row, request_path, response_path = _captured_analysis_row(tmp_path)
    monkeypatch.setattr(runner, "_resolve_capture_ref", lambda ref: Path(ref))
    monkeypatch.setattr(runner, "_relative", lambda path: Path(path).as_posix())

    receipt = runner._validate_reused_analysis_capture(row)

    assert receipt["analysis_reuse_digest"] == runner._reused_analysis_digest(row)
    assert receipt["request_capture_sha256"] == runner._sha(request_path)
    assert receipt["response_capture_sha256"] == runner._sha(response_path)


def test_reused_analysis_capture_mutation_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    row, _, response_path = _captured_analysis_row(tmp_path)
    monkeypatch.setattr(runner, "_resolve_capture_ref", lambda ref: Path(ref))
    mutated = json.loads(response_path.read_text(encoding="utf-8"))
    mutated["response_body"]["choices"][0]["message"]["content"] = "mutated"
    response_path.write_text(json.dumps(mutated), encoding="utf-8")

    with pytest.raises(
        runner.DynamicFiveCellLiveError,
        match="five_cell_node_successor_capture_integrity_invalid",
    ):
        runner._validate_reused_analysis_capture(row)


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


def test_claim_surface_successor_reuses_only_prefix_and_reruns_all_twelve_nodes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    authority_path, private_root, public_path, counters = _prepare_runner(
        monkeypatch, tmp_path, claim_surface_successor_mode=True
    )

    def planner_must_not_run(**_kwargs):
        raise AssertionError("claim-surface successor must not rerun planner")

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

    assert result["schema_version"] == runner.CLAIM_SURFACE_SUCCESSOR_RESULT_SCHEMA
    assert result["status"].startswith("completed_")
    assert result["dynamic_research_input_digest"] == "claim-surface-input"
    assert result["execution"]["model_calls_attempted"] == 12
    assert result["execution"]["maximum_model_calls"] == 12
    assert result["execution"]["planner_calls_completed"] == 0
    assert result["execution"]["planner_calls_reused"] == 1
    assert result["execution"]["cell_analysis_calls_attempted"] == 5
    assert result["execution"]["cell_analysis_drafts_reused"] == 0
    assert result["execution"]["cell_submission_calls_attempted"] == 5
    assert result["execution"]["cell_judgments_reused"] == 0
    assert result["execution"]["cell_judgments_accepted"] == 5
    full_result = json.loads(
        (private_root / "full_result.json").read_text(encoding="utf-8")
    )
    prefix = full_result["successor_prefix_reuse"]
    assert prefix["valid_cells_rerun"] is True
    assert prefix["cell_analysis_rerun"] is True
    assert prefix["claim_surface_successor"] is True
    projected = [
        row["tool_projection_receipt"] for row in result["cells"]
    ] + [result["synthesis"]["tool_projection_receipt"]]
    assert len(projected) == 6
    assert all(row["projection_digest"] == "strict-projection" for row in projected)
    assert counters == {"analysis": 6, "submission": 6}
    assert public_path.is_file()
    assert (private_root / "full_result.json").is_file()


def test_claim_surface_successor_materializes_unexpected_cell_exception(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    authority_path, private_root, public_path, counters = _prepare_runner(
        monkeypatch, tmp_path, claim_surface_successor_mode=True
    )

    def planner_must_not_run(**_kwargs):
        raise AssertionError("claim-surface successor must not rerun planner")

    def analyze(**_kwargs):
        counters["analysis"] += 1
        return _analysis_step(tmp_path, counters["analysis"])

    def submit(**kwargs):
        counters["submission"] += 1
        tool = kwargs["tools"][0]["function"]
        return _submission_step(
            tmp_path,
            counters["submission"],
            tool_name=tool["name"],
            arguments={"cell_id": tool["description"]},
        )

    def validate_with_one_project_exception(
        payload,
        *,
        required_cell_ids,
        **_kwargs,
    ):
        cell_id = required_cell_ids[0]
        if cell_id == "CELL::demand_quality":
            raise KeyError("allowed_qualitative_fact_refs")
        return {"cells": [dict(payload["cells"][0])]}

    monkeypatch.setattr(
        runner,
        "validate_current_research_output",
        validate_with_one_project_exception,
    )

    result = runner.run(
        authority_path,
        planner_executor=planner_must_not_run,
        analysis_executor=analyze,
        submission_executor=submit,
    )

    assert result["status"] == "terminal_failed_or_partial_no_retry"
    demand = result["cells"][0]
    assert demand["cell_id"] == "CELL::demand_quality"
    assert demand["failure_phase"] == "cell_unexpected_project_exception"
    assert demand["failure_code"] == (
        "five_cell_unexpected_project_exception_keyerror"
    )
    assert result["execution"]["model_calls_attempted"] == 10
    assert result["execution"]["cell_judgments_accepted"] == 4
    assert result["execution"]["retries"] == 0
    assert counters == {"analysis": 5, "submission": 5}
    assert public_path.is_file()
    assert (private_root / "full_result.json").is_file()


def test_five_cell_partial_successor_reuses_two_cells_and_runs_only_eight_nodes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    authority_path, private_root, public_path, counters = _prepare_runner(
        monkeypatch, tmp_path, partial_successor_mode=True
    )

    def planner_must_not_run(**_kwargs):
        raise AssertionError("partial successor must not rerun planner")

    def analyze(**_kwargs):
        counters["analysis"] += 1
        return _analysis_step(tmp_path, counters["analysis"] + 2)

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
            counters["submission"] + 2,
            tool_name=tool["name"],
            arguments=arguments,
        )

    result = runner.run(
        authority_path,
        planner_executor=planner_must_not_run,
        analysis_executor=analyze,
        submission_executor=submit,
    )

    assert result["schema_version"] == runner.PARTIAL_SUCCESSOR_RESULT_SCHEMA
    assert result["status"].startswith("completed_")
    assert result["execution"]["model_calls_attempted"] == 8
    assert result["execution"]["maximum_model_calls"] == 8
    assert result["execution"]["cell_analysis_calls_attempted"] == 3
    assert result["execution"]["cell_submission_calls_attempted"] == 3
    assert result["execution"]["cell_judgments_reused"] == 2
    assert result["execution"]["cell_judgments_accepted"] == 5
    assert result["acceptance"][
        "valid_cell_judgments_reused_not_rerun"
    ] is True
    assert result["acceptance"][
        "current_S1_S2_EvidenceResponse_executed"
    ] is False
    assert result["acceptance"][
        "current_S1_S2_EvidenceResponse_available"
    ] is True
    assert [row["reused_from_predecessor"] for row in result["cells"]] == [
        True,
        True,
        False,
        False,
        False,
    ]
    assert counters == {"analysis": 4, "submission": 4}
    assert public_path.is_file()
    assert (private_root / "full_result.json").is_file()


def test_five_cell_node_successor_reuses_three_judgments_and_two_analyses(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    authority_path, private_root, public_path, counters = _prepare_runner(
        monkeypatch, tmp_path, node_successor_mode=True
    )

    def planner_must_not_run(**_kwargs):
        raise AssertionError("node successor must not rerun planner")

    def analyze(**kwargs):
        counters["analysis"] += 1
        assert kwargs["attempt_id"] == "synthesis-analysis-01"
        return _analysis_step(tmp_path, 9)

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
            counters["submission"] + 10,
            tool_name=tool["name"],
            arguments=arguments,
        )

    result = runner.run(
        authority_path,
        planner_executor=planner_must_not_run,
        analysis_executor=analyze,
        submission_executor=submit,
    )

    assert result["schema_version"] == runner.NODE_SUCCESSOR_RESULT_SCHEMA
    assert result["status"].startswith("completed_")
    assert result["execution"]["model_calls_attempted"] == 4
    assert result["execution"]["maximum_model_calls"] == 4
    assert result["execution"]["cell_analysis_calls_attempted"] == 0
    assert result["execution"]["cell_analysis_drafts_reused"] == 2
    assert result["execution"]["cell_submission_calls_attempted"] == 2
    assert result["execution"]["cell_judgments_reused"] == 3
    assert result["execution"]["cell_judgments_accepted"] == 5
    assert result["acceptance"]["analysis_drafts_reused_not_rerun"] is True
    assert result["acceptance"][
        "valid_cell_judgments_reused_not_rerun"
    ] is True
    assert [row["reused_from_predecessor"] for row in result["cells"]] == [
        True,
        True,
        False,
        True,
        False,
    ]
    assert [
        row["analysis_reused_from_predecessor"] for row in result["cells"]
    ] == [True, True, True, True, True]
    projected = [
        row["tool_projection_receipt"]
        for row in result["cells"]
        if not row["reused_from_predecessor"]
    ] + [result["synthesis"]["tool_projection_receipt"]]
    assert len(projected) == 3
    assert all(row["projection_digest"] == "strict-projection" for row in projected)
    assert counters == {"analysis": 1, "submission": 3}
    assert public_path.is_file()
    assert (private_root / "full_result.json").is_file()


def test_five_cell_value_repair_successor_reuses_four_cells_and_one_analysis(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    authority_path, private_root, public_path, counters = _prepare_runner(
        monkeypatch, tmp_path, value_repair_successor_mode=True
    )

    def planner_must_not_run(**_kwargs):
        raise AssertionError("value repair successor must not rerun planner")

    def analyze(**kwargs):
        counters["analysis"] += 1
        assert kwargs["attempt_id"] == "synthesis-analysis-01"
        return _analysis_step(tmp_path, 19)

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
            counters["submission"] + 30,
            tool_name=tool["name"],
            arguments=arguments,
        )

    result = runner.run(
        authority_path,
        planner_executor=planner_must_not_run,
        analysis_executor=analyze,
        submission_executor=submit,
    )

    assert result["schema_version"] == runner.VALUE_REPAIR_SUCCESSOR_RESULT_SCHEMA
    assert result["status"].startswith("completed_"), (
        result["orchestration_failure"],
        [(row["cell_id"], row["failure_code"]) for row in result["cells"]],
        result["synthesis"],
    )
    assert result["execution"]["model_calls_attempted"] == 3
    assert result["execution"]["maximum_model_calls"] == 3
    assert result["execution"]["cell_analysis_calls_attempted"] == 0
    assert result["execution"]["cell_analysis_drafts_reused"] == 1
    assert result["execution"]["cell_submission_calls_attempted"] == 1
    assert result["execution"]["cell_judgments_reused"] == 4
    assert result["execution"]["cell_judgments_accepted"] == 5
    assert result["acceptance"]["analysis_drafts_reused_not_rerun"] is True
    assert result["acceptance"][
        "valid_cell_judgments_reused_not_rerun"
    ] is True
    assert result["acceptance"]["typed_value_submission_repair_executed"] is True
    value = next(
        row for row in result["cells"] if row["cell_id"] == "CELL::value_capture"
    )
    assert value["submission_repair_receipt"][
        "rejected_submission_promoted"
    ] is False
    assert [row["reused_from_predecessor"] for row in result["cells"]] == [
        True,
        True,
        False,
        True,
        True,
    ]
    assert counters == {"analysis": 1, "submission": 2}
    assert public_path.is_file()
    assert (private_root / "full_result.json").is_file()


def test_five_cell_node_successor_preserves_failed_resubmission_and_skips_synthesis(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    authority_path, private_root, public_path, counters = _prepare_runner(
        monkeypatch, tmp_path, node_successor_mode=True
    )

    def analysis_must_not_run(**_kwargs):
        raise AssertionError("synthesis must not run with four valid cells")

    def submit(**kwargs):
        counters["submission"] += 1
        tool = kwargs["tools"][0]["function"]
        name = tool["name"] if counters["submission"] == 1 else "wrong_tool"
        return _submission_step(
            tmp_path,
            counters["submission"] + 20,
            tool_name=name,
            arguments={"cell_id": tool["description"]},
        )

    result = runner.run(
        authority_path,
        planner_executor=lambda **_: (_ for _ in ()).throw(
            AssertionError("planner must not run")
        ),
        analysis_executor=analysis_must_not_run,
        submission_executor=submit,
    )

    assert result["status"] == "terminal_failed_or_partial_no_retry"
    assert result["execution"]["model_calls_attempted"] == 2
    assert result["execution"]["cell_judgments_accepted"] == 4
    assert result["synthesis"]["failure_code"] == (
        "five_cell_synthesis_requires_all_cells"
    )
    assert result["cells"][4]["failure_code"] == (
        "five_cell_live_submission_tool_invalid"
    )
    assert counters == {"analysis": 0, "submission": 2}
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
