from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.providers.chat_completions import (  # noqa: E402
    ChatCompletionResult,
    ChatCompletionToolStepResult,
    ModelGatewayError,
)
from sec_agent.research.bounded_finance_loop import (  # noqa: E402
    MICRO_JUDGMENT_TOOL_NAMES,
    READ_NUMERIC_FACTS_TOOL,
    READ_REVIEWED_EVIDENCE_TOOL,
    SUBMIT_RESEARCH_JUDGMENT_TOOL,
)
from sec_agent.research.paired_submission import (  # noqa: E402
    PairedResearchSubmission,
    PairedSubmissionError,
    run_paired_research_submission,
    shared_provider_failure,
)


SCRIPT = ROOT / "scripts/research/run_s3_current_research_consumer_canary.py"
LOOP_POLICY = ROOT / (
    "configs/research/fin_ia_0_1_3_s3_bounded_finance_agent_loop_policy_v1_1.json"
)
CONSUMER_POLICY = ROOT / (
    "configs/research/fin_ia_0_1_3_s3_current_research_consumer_policy_v1_2.json"
)
OBJECTIVE = ROOT / (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_minimal_planner_canary_objective_v1_0.json"
)
ATOMS = ROOT / (
    "tests/fixtures/research/"
    "fin_ia_0_1_3_s3_dell_planner_r1_atoms_v1_0.json"
)
FAKE = ROOT / (
    "tests/fixtures/research/"
    "fin_ia_0_1_3_s3_dell_current_research_consumer_fake_payload_v1_2.json"
)
STANDARD_PROFILE = ROOT / (
    "configs/providers/"
    "fin_ia_0_1_3_deepseek_v4_pro_ga_agent_profile_v1_1.json"
)
CLEAN_LOOP_PROOF = ROOT / (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_bounded_finance_loop_zero_call_result_v1_0.json"
)
CLAIM_AUTHORITY_POLICY = ROOT / (
    "configs/research/"
    "fin_ia_0_1_3_s3_dell_value_capture_fixed_pack_claim_authority_v1_0.json"
)
CLAIM_SURFACE_AUTHORITY_POLICY = ROOT / (
    "configs/research/"
    "fin_ia_0_1_3_s3_dell_value_capture_fixed_pack_"
    "claim_surface_authority_v1_0.json"
)
CLAIM_SURFACE_FAKE = ROOT / (
    "tests/fixtures/research/"
    "fin_ia_0_1_3_s3_dell_value_capture_fixed_pack_"
    "claim_surface_authority_fake_payload_v1_0.json"
)
CLAIM_RELATION_ALIAS_POLICY = ROOT / (
    "configs/research/"
    "fin_ia_0_1_3_s3_dell_value_capture_fixed_pack_"
    "claim_surface_authority_v1_1.json"
)
CLAIM_RELATION_ALIAS_FAKE = ROOT / (
    "tests/fixtures/research/"
    "fin_ia_0_1_3_s3_dell_value_capture_fixed_pack_"
    "claim_surface_authority_alias_fake_payload_v1_0.json"
)
MICRO_POLICY = ROOT / (
    "configs/research/"
    "fin_ia_0_1_3_s3_fixed_pack_micro_judgment_policy_v1_0.json"
)
MICRO_READ_PROFILE = ROOT / (
    "configs/providers/"
    "fin_ia_0_1_3_deepseek_v4_pro_ga_micro_read_profile_v1_0.json"
)
MICRO_JUDGMENT_PROFILE = ROOT / (
    "configs/providers/"
    "fin_ia_0_1_3_deepseek_v4_pro_ga_micro_judgment_profile_v1_0.json"
)
MICRO_PROOF_AUTHORITY = ROOT / (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_value_capture_fixed_pack_"
    "micro_judgment_zero_call_authority_v1_0.json"
)
MICRO_PROOF_RESULT = ROOT / (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_value_capture_fixed_pack_"
    "micro_judgment_zero_call_result_v1_0.json"
)
PRIOR_ALIAS_LIVE_RESULT = ROOT / (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_value_capture_fixed_pack_"
    "claim_relation_alias_chat_live_result_v1_0.json"
)
PRIOR_ALIAS_CAPACITY = ROOT / (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_value_capture_fixed_pack_"
    "claim_relation_alias_chat_live_capacity_assessment_v1_0.json"
)
MICRO_LIVE_DECISION = ROOT / (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_value_capture_fixed_pack_"
    "micro_judgment_live_scope_decision_v1_0.json"
)
FRAGMENT_ZERO_CALL_RESULT = ROOT / (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_value_capture_fixed_pack_"
    "fragment_analysis_submission_zero_call_result_v1_0.json"
)
FRAGMENT_DISPOSITION = ROOT / (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_value_capture_fixed_pack_"
    "fragment_analysis_submission_disposition_v1_0.json"
)
MICRO_R3_RESULT = ROOT / (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_value_capture_fixed_pack_"
    "micro_judgment_chat_live_result_v1_0.json"
)
MICRO_R3_CAPACITY = ROOT / (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_value_capture_fixed_pack_"
    "micro_judgment_chat_live_capacity_assessment_v1_0.json"
)


def _runner():
    spec = importlib.util.spec_from_file_location(
        "s3_current_research_consumer_canary_runner",
        SCRIPT,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _tool_loop_authority(tmp_path: Path) -> tuple[Path, dict[str, object]]:
    authority = {
        "schema_version": "fin_ia_s3_bounded_finance_loop_live_authority_v1_0",
        "status": "signed_exact_once_standard_API_bounded_finance_loop_live",
        "implementation_commit": "a" * 40,
        "case_key": "DELL",
        "required_cell_ids": ["CELL::value_capture"],
        "execution_budget": {
            "maximum_model_calls": 6,
            "maximum_transport_attempts": 6,
            "maximum_evidence_requests": 3,
            "retries": 0,
            "fallbacks": 0,
            "planner_calls": 0,
            "external_retrieval_calls": 0,
            "embedding_calls": 0,
            "current_product_pointer_mutations": 0,
        },
        "output_contract": {
            "capture_root_ref": "capture",
            "private_output_root_ref": "private",
            "public_result_ref": "public.json",
            "run_id": "TEST-LOOP-R1",
            "step_attempt_prefix": "STEP",
            "product_publication": "forbidden",
        },
        "known_boundary": "unit test only",
    }
    path = tmp_path / "authority.json"
    path.write_text(json.dumps(authority), encoding="utf-8")
    return path, authority


def _tool_loop_bound_paths() -> dict[str, Path]:
    return {
        "consumer_policy_ref": CONSUMER_POLICY,
        "objective_ref": OBJECTIVE,
        "planner_atoms_ref": ATOMS,
        "clean_zero_call_result_ref": CLEAN_LOOP_PROOF,
        "loop_policy_ref": LOOP_POLICY,
        "provider_profile_ref": STANDARD_PROFILE,
        "prior_scope_decision_ref": ROOT
        / (
            "configs/research/evals/"
            "fin_ia_0_1_3_s3_dell_ga_value_capture_json_r2_node_assessment_v1_0.json"
        ),
    }


def _tool_step(
    index: int,
    name: str,
    arguments: dict[str, object],
    capture_root: Path,
) -> ChatCompletionToolStepResult:
    return ChatCompletionToolStepResult(
        status="completed_exact_once_tool_step",
        provider_id="fixture-provider",
        model="fixture-model",
        content="",
        reasoning_content=f"transient-private-{index}",
        tool_calls=(
            {
                "id": f"call-{index}",
                "type": "function",
                "function": {
                    "name": name,
                    "arguments": json.dumps(arguments, ensure_ascii=False),
                },
            },
        ),
        finish_reason="tool_calls",
        usage={"prompt_tokens": index, "completion_tokens": index + 1},
        request_capture_ref=str(capture_root / f"request-{index}.json"),
        response_capture_ref=str(capture_root / f"response-{index}.json"),
        request_digest=str(index) * 64,
        response_digest=str(index + 1) * 64,
        private_reasoning_fields_redacted=1,
    )


def _parallel_tool_step(
    index: int,
    cell_id: str,
    capture_root: Path,
) -> ChatCompletionToolStepResult:
    return ChatCompletionToolStepResult(
        status="completed_exact_once_tool_step",
        provider_id="fixture-provider",
        model="fixture-model",
        content="",
        reasoning_content=f"transient-private-{index}",
        tool_calls=tuple(
            {
                "id": f"call-{index}-{offset}",
                "type": "function",
                "function": {
                    "name": name,
                    "arguments": json.dumps(
                        {"cell_id": cell_id}, ensure_ascii=False
                    ),
                },
            }
            for offset, name in enumerate(
                (READ_REVIEWED_EVIDENCE_TOOL, READ_NUMERIC_FACTS_TOOL)
            )
        ),
        finish_reason="tool_calls",
        usage={"prompt_tokens": index, "completion_tokens": index + 1},
        request_capture_ref=str(capture_root / f"request-{index}.json"),
        response_capture_ref=str(capture_root / f"response-{index}.json"),
        request_digest=str(index) * 64,
        response_digest=str(index + 1) * 64,
        private_reasoning_fields_redacted=1,
    )


def _micro_alias_fragments() -> dict[str, dict[str, object]]:
    row = json.loads(CLAIM_RELATION_ALIAS_FAKE.read_text(encoding="utf-8"))[
        "cells"
    ][0]
    relation_by_atom = {
        item["atom_field"]: item["claim_relation_ref"]
        for item in row["claim_relations"]
    }
    common_refs = {
        "numeric_refs": list(row["numeric_refs"]),
        "method_step_refs": list(row["method_step_refs"]),
        "graph_edge_refs": list(row["graph_edge_refs"]),
    }
    return {
        MICRO_JUDGMENT_TOOL_NAMES[0]: {
            "cell_id": row["cell_id"],
            "claim_relation_ref": relation_by_atom["thesis_atom"],
            "evidence_uses": row["evidence_uses"][:2],
            **common_refs,
            "numeric_relation_refs": [],
            "qualitative_fact_refs": list(row["qualitative_fact_refs"]),
            "judgment_status": row["judgment_status"],
            "confidence_basis": row["confidence_basis"],
            "inference_authority": row["inference_authority"],
            "claim_scope": row["claim_scope"],
            "financial_scope": row["financial_scope"],
            "causal_bridge_authority": row["causal_bridge_authority"],
            "thesis_atom": row["thesis_atom"],
        },
        MICRO_JUDGMENT_TOOL_NAMES[1]: {
            "cell_id": row["cell_id"],
            "claim_relation_ref": relation_by_atom["mechanism_atom"],
            "evidence_uses": row["evidence_uses"][2:3],
            "numeric_refs": [],
            "numeric_relation_refs": [],
            "qualitative_fact_refs": [],
            "method_step_refs": [],
            "graph_edge_refs": [],
            "mechanism_atom": row["mechanism_atom"],
        },
        MICRO_JUDGMENT_TOOL_NAMES[2]: {
            "cell_id": row["cell_id"],
            "claim_relation_ref": relation_by_atom["counterargument_atom"],
            "evidence_uses": row["evidence_uses"][3:],
            "numeric_refs": [],
            "numeric_relation_refs": list(row["numeric_relation_refs"]),
            "qualitative_fact_refs": [],
            "method_step_refs": [],
            "graph_edge_refs": [],
            "counterargument_atom": row["counterargument_atom"],
            "what_would_change": {
                **row["what_would_change"],
                "threshold_numeric_ref": "",
            },
        },
    }


def _micro_tool_loop_paths() -> dict[str, Path]:
    paths = _tool_loop_bound_paths()
    paths.pop("provider_profile_ref")
    paths.update(
        {
            "claim_authority_policy_ref": CLAIM_AUTHORITY_POLICY,
            "claim_surface_authority_policy_ref": CLAIM_RELATION_ALIAS_POLICY,
            "clean_zero_call_result_ref": MICRO_PROOF_RESULT,
            "micro_zero_call_authority_ref": MICRO_PROOF_AUTHORITY,
            "micro_policy_ref": MICRO_POLICY,
            "micro_read_profile_ref": MICRO_READ_PROFILE,
            "micro_judgment_profile_ref": MICRO_JUDGMENT_PROFILE,
            "prior_live_result_ref": PRIOR_ALIAS_LIVE_RESULT,
            "prior_capacity_assessment_ref": PRIOR_ALIAS_CAPACITY,
            "prior_scope_decision_ref": MICRO_LIVE_DECISION,
        }
    )
    return paths


def _micro_validation_paths() -> dict[str, Path]:
    paths = _micro_tool_loop_paths()
    paths.update(
        {
            "current_evidence_pack_result_ref": ROOT
            / "configs/runtime/fin_ia_current_research_evidence_pack_result_v1_1.json",
            "runtime_registry_ref": ROOT
            / "configs/runtime/fin_ia_0_1_3_clean_baseline_runtime_resource_registry_v1_0.json",
            "runner_ref": SCRIPT,
            "loop_implementation_ref": ROOT
            / "src/sec_agent/research/bounded_finance_loop.py",
            "provider_transport_ref": ROOT
            / "src/sec_agent/providers/chat_completions.py",
        }
    )
    return paths


def _fragment_validation_paths() -> dict[str, Path]:
    return {
        "consumer_policy_ref": CONSUMER_POLICY,
        "objective_ref": OBJECTIVE,
        "planner_atoms_ref": ATOMS,
        "current_evidence_pack_result_ref": ROOT
        / "configs/runtime/fin_ia_current_research_evidence_pack_result_v1_1.json",
        "runtime_registry_ref": ROOT
        / "configs/runtime/fin_ia_0_1_3_clean_baseline_runtime_resource_registry_v1_0.json",
        "claim_authority_policy_ref": CLAIM_AUTHORITY_POLICY,
        "claim_surface_authority_policy_ref": CLAIM_RELATION_ALIAS_POLICY,
        "loop_policy_ref": LOOP_POLICY,
        "micro_policy_ref": MICRO_POLICY,
        "analysis_profile_ref": MICRO_JUDGMENT_PROFILE,
        "submission_profile_ref": MICRO_READ_PROFILE,
        "runner_ref": SCRIPT,
        "loop_implementation_ref": ROOT
        / "src/sec_agent/research/bounded_finance_loop.py",
        "provider_transport_ref": ROOT
        / "src/sec_agent/providers/chat_completions.py",
        "zero_call_result_ref": FRAGMENT_ZERO_CALL_RESULT,
        "prior_live_result_ref": MICRO_R3_RESULT,
        "prior_capacity_assessment_ref": MICRO_R3_CAPACITY,
        "disposition_decision_ref": FRAGMENT_DISPOSITION,
    }


def _prepare_micro_tool_loop_test(
    runner,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> tuple[Path, dict[str, object], dict[str, Path]]:
    authority_path, authority = _tool_loop_authority(tmp_path)
    authority.update(
        {
            "schema_version": runner.MICRO_TOOL_LOOP_AUTHORITY_SCHEMA,
            "status": runner.MICRO_TOOL_LOOP_AUTHORITY_STATUS,
            "execution_budget": {
                "maximum_model_calls": 4,
                "maximum_transport_attempts": 4,
                "maximum_tool_calls": 5,
                "maximum_evidence_requests": 0,
                "retries": 0,
                "fallbacks": 0,
                "planner_calls": 0,
                "external_retrieval_calls": 0,
                "embedding_calls": 0,
                "current_product_pointer_mutations": 0,
            },
        }
    )
    paths = _micro_tool_loop_paths()
    _, research_input, _ = runner._compile_runtime_input(
        paths,
        case_key="DELL",
        required_cell_ids=["CELL::value_capture"],
    )
    kernel, route, _ = runner._tool_loop_contracts(paths)
    base_policy = runner.load_bounded_finance_loop_policy(
        json.loads(LOOP_POLICY.read_text(encoding="utf-8"))
    )
    scoped_policy = runner.scope_bounded_finance_micro_judgment_policy(
        base_policy,
        micro_policy=runner.load_fixed_pack_micro_judgment_policy(
            json.loads(MICRO_POLICY.read_text(encoding="utf-8"))
        ),
        cell_count=1,
        maximum_evidence_requests=0,
    )
    messages = runner.compile_finance_loop_messages(
        research_input=research_input,
        required_cell_ids=["CELL::value_capture"],
        execution_budget={
            "maximum_steps": 4,
            "maximum_evidence_requests": 0,
            "maximum_reads_per_cell": 1,
            "maximum_parallel_read_tools": 2,
            "maximum_judgments_per_cell": 1,
            "retry_count": 0,
        },
        micro_judgment_mode=True,
    )
    tools = runner.compile_finance_micro_judgment_tools(
        research_input=research_input,
        required_cell_ids=["CELL::value_capture"],
        kernel=kernel,
        route_policy=route,
        policy=scoped_policy,
        strict=False,
    )
    authority["bound_inputs"] = {
        "research_input_digest": research_input["research_input_digest"],
        "finance_loop_messages_digest": runner.canonical_digest(
            list(messages)
        ),
        "micro_tool_schema_digest": runner.canonical_digest(list(tools)),
    }
    authority_path.write_text(json.dumps(authority), encoding="utf-8")
    monkeypatch.setattr(
        runner,
        "validate_tool_loop_authority",
        lambda _payload, authority_path: paths,
    )
    destinations = {
        "capture": tmp_path / "capture",
        "private": tmp_path / "private",
        "public.json": tmp_path / "public.json",
    }
    monkeypatch.setattr(runner, "_resolve", lambda ref: destinations[str(ref)])
    monkeypatch.setattr(runner, "_relative", lambda path: Path(path).name)
    return authority_path, authority, paths


def _prepare_tool_loop_test(
    runner,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> tuple[Path, dict[str, object], dict[str, Path]]:
    authority_path, authority = _tool_loop_authority(tmp_path)
    paths = _tool_loop_bound_paths()
    clean_proof_path = tmp_path / "clean-proof.json"
    clean_proof_path.write_text(
        json.dumps(
            {
                "status": "zero_call_engineering_and_fresh_process_proof_pass",
                "result_digest": "c" * 64,
                "normalized_proof": {
                    "research_input_digest": "pending",
                    "single_cell_maximum_steps": 6,
                    "safe_parallel_read_pair_pass": True,
                    "wire_tool_call_index_stripped": True,
                    "standard_profile_max_tokens": 16000,
                    "mutation_failure_codes": [
                        "finance_loop_parallel_tool_set_invalid",
                        "finance_loop_required_cell_reads_incomplete"
                    ],
                },
            }
        ),
        encoding="utf-8",
    )
    paths["clean_zero_call_result_ref"] = clean_proof_path
    _, research_input, _ = runner._compile_runtime_input(
        paths,
        case_key="DELL",
        required_cell_ids=["CELL::value_capture"],
    )
    kernel, route, _ = runner._tool_loop_contracts(paths)
    messages = runner.compile_finance_loop_messages(
        research_input=research_input,
        required_cell_ids=["CELL::value_capture"],
        execution_budget={
            "maximum_steps": 6,
            "maximum_evidence_requests": 3,
            "maximum_reads_per_cell": 1,
            "maximum_parallel_read_tools": 2,
            "maximum_judgments_per_cell": 1,
            "retry_count": 0,
        },
    )
    tools = runner.compile_finance_loop_tools(
        research_input=research_input,
        required_cell_ids=["CELL::value_capture"],
        kernel=kernel,
        route_policy=route,
        policy=runner.load_bounded_finance_loop_policy(
            json.loads(LOOP_POLICY.read_text(encoding="utf-8"))
        ),
        strict=False,
    )
    authority["bound_inputs"] = {
        "research_input_digest": research_input["research_input_digest"],
        "finance_loop_messages_digest": runner.canonical_digest(list(messages)),
        "standard_tool_schema_digest": runner.canonical_digest(list(tools)),
    }
    proof = json.loads(clean_proof_path.read_text(encoding="utf-8"))
    proof["normalized_proof"]["research_input_digest"] = research_input[
        "research_input_digest"
    ]
    clean_proof_path.write_text(json.dumps(proof), encoding="utf-8")
    authority_path.write_text(json.dumps(authority), encoding="utf-8")
    monkeypatch.setattr(
        runner,
        "validate_tool_loop_authority",
        lambda _payload, authority_path: paths,
    )
    destinations = {
        "capture": tmp_path / "capture",
        "private": tmp_path / "private",
        "public.json": tmp_path / "public.json",
    }
    monkeypatch.setattr(
        runner,
        "_resolve",
        lambda ref: destinations[str(ref)],
    )
    monkeypatch.setattr(runner, "_relative", lambda path: Path(path).name)
    return authority_path, authority, paths


def test_standard_tool_loop_success_materializes_three_steps(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runner = _runner()
    authority_path, _, _ = _prepare_tool_loop_test(
        runner, monkeypatch, tmp_path
    )
    fake = json.loads(FAKE.read_text(encoding="utf-8"))
    judgment = next(
        row
        for row in fake["cells"]
        if row["cell_id"] == "CELL::value_capture"
    )
    sequence = [
        (READ_REVIEWED_EVIDENCE_TOOL, {"cell_id": "CELL::value_capture"}),
        (READ_NUMERIC_FACTS_TOOL, {"cell_id": "CELL::value_capture"}),
        (SUBMIT_RESEARCH_JUDGMENT_TOOL, judgment),
    ]

    def executor(**kwargs):
        index = int(str(kwargs["attempt_id"]).split("-")[-3])
        if index == 1:
            first_user_message = kwargs["messages"][1]["content"]
            assert '"maximum_steps":6' in first_user_message
            assert '"retry_count":0' in first_user_message
        name, arguments = sequence[index - 1]
        return _tool_step(index, name, arguments, tmp_path / "capture")

    result = runner.run_tool_loop(authority_path, step_executor=executor)

    assert result["status"] == "completed_contract_valid_content_assessment_pending"
    assert result["execution"]["model_calls_attempted"] == 3
    assert result["accepted_receipt_count"] == 3
    assert result["tool_counts"] == {
        READ_REVIEWED_EVIDENCE_TOOL: 1,
        READ_NUMERIC_FACTS_TOOL: 1,
        SUBMIT_RESEARCH_JUDGMENT_TOOL: 1,
    }
    assert result["acceptance"][
        "standard_tool_transport_and_local_contract_pass"
    ] is True
    assert result["acceptance"]["five_cell_live_authorized"] is False
    full = (tmp_path / "private" / "full_result.json").read_text(
        encoding="utf-8"
    )
    assert "transient-private" not in full
    assert (tmp_path / "public.json").is_file()


def test_standard_tool_loop_parallel_reads_materialize_distinct_receipts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runner = _runner()
    authority_path, _, _ = _prepare_tool_loop_test(
        runner, monkeypatch, tmp_path
    )
    fake = json.loads(FAKE.read_text(encoding="utf-8"))
    judgment = next(
        row
        for row in fake["cells"]
        if row["cell_id"] == "CELL::value_capture"
    )

    def executor(**kwargs):
        index = int(str(kwargs["attempt_id"]).split("-")[-3])
        if index == 1:
            return _parallel_tool_step(
                index, "CELL::value_capture", tmp_path / "capture"
            )
        return _tool_step(
            index,
            SUBMIT_RESEARCH_JUDGMENT_TOOL,
            judgment,
            tmp_path / "capture",
        )

    result = runner.run_tool_loop(authority_path, step_executor=executor)

    assert result["status"] == "completed_contract_valid_content_assessment_pending"
    assert result["execution"]["model_calls_attempted"] == 2
    assert result["accepted_receipt_count"] == 3
    assert result["provider_steps"][0]["tool_names"] == [
        READ_REVIEWED_EVIDENCE_TOOL,
        READ_NUMERIC_FACTS_TOOL,
    ]
    receipts = sorted((tmp_path / "private").glob("receipt-*.json"))
    assert [path.name for path in receipts] == [
        "receipt-01-step-01.json",
        "receipt-02-step-01.json",
        "receipt-03-step-02.json",
    ]


def test_micro_tool_loop_uses_node_profiles_and_materializes_four_steps(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runner = _runner()
    authority_path, _, _ = _prepare_micro_tool_loop_test(
        runner, monkeypatch, tmp_path
    )
    fragments = _micro_alias_fragments()
    observed: list[dict[str, object]] = []

    def executor(**kwargs):
        index = len(observed) + 1
        names = [row["function"]["name"] for row in kwargs["tools"]]
        observed.append(
            {
                "names": names,
                "reasoning_effort": kwargs[
                    "profile"
                ].request_defaults["reasoning_effort"],
                "max_tokens": kwargs["profile"].request_defaults[
                    "max_tokens"
                ],
            }
        )
        if index == 1:
            return _parallel_tool_step(
                index, "CELL::value_capture", tmp_path
            )
        name = names[0]
        return _tool_step(index, name, fragments[name], tmp_path)

    result = runner.run_tool_loop(authority_path, step_executor=executor)

    assert result["status"] == "completed_contract_valid_content_assessment_pending"
    assert result["execution"]["model_calls_attempted"] == 4
    assert result["accepted_receipt_count"] == 5
    assert result["tool_counts"] == {
        READ_REVIEWED_EVIDENCE_TOOL: 1,
        READ_NUMERIC_FACTS_TOOL: 1,
        MICRO_JUDGMENT_TOOL_NAMES[0]: 1,
        MICRO_JUDGMENT_TOOL_NAMES[1]: 1,
        MICRO_JUDGMENT_TOOL_NAMES[2]: 1,
    }
    assert observed[0] == {
        "names": [READ_REVIEWED_EVIDENCE_TOOL, READ_NUMERIC_FACTS_TOOL],
        "reasoning_effort": "low",
        "max_tokens": 2000,
    }
    assert [row["reasoning_effort"] for row in observed[1:]] == [
        "high",
        "high",
        "high",
    ]
    assert [row["max_tokens"] for row in observed[1:]] == [8000, 8000, 8000]
    assert [row["node_class"] for row in result["node_profile_selections"]] == [
        "tool_routing",
        "bounded_financial_judgment",
        "bounded_financial_judgment",
        "bounded_financial_judgment",
    ]


def test_micro_node_profile_rejects_wrong_active_tools_before_provider() -> None:
    runner = _runner()
    read_profile = runner.load_chat_completion_profile(
        json.loads(MICRO_READ_PROFILE.read_text(encoding="utf-8"))
    )
    judgment_profile = runner.load_chat_completion_profile(
        json.loads(MICRO_JUDGMENT_PROFILE.read_text(encoding="utf-8"))
    )
    with pytest.raises(runner.CurrentResearchConsumerCanaryError) as exc:
        runner._select_micro_node_profile(
            [
                {
                    "type": "function",
                    "function": {"name": READ_REVIEWED_EVIDENCE_TOOL},
                }
            ],
            read_profile=read_profile,
            judgment_profile=judgment_profile,
        )
    assert exc.value.code == "research_consumer_micro_active_tool_set_invalid"


def test_micro_scope_decision_rejects_predecessor_drift() -> None:
    runner = _runner()
    decision = json.loads(MICRO_LIVE_DECISION.read_text(encoding="utf-8"))
    clean = json.loads(MICRO_PROOF_RESULT.read_text(encoding="utf-8"))
    clean_authority = json.loads(
        MICRO_PROOF_AUTHORITY.read_text(encoding="utf-8")
    )
    predecessor = json.loads(
        PRIOR_ALIAS_LIVE_RESULT.read_text(encoding="utf-8")
    )
    capacity = json.loads(PRIOR_ALIAS_CAPACITY.read_text(encoding="utf-8"))
    assert runner._fixed_pack_micro_judgment_scope_authorized(
        decision,
        cell_ids=["CELL::value_capture"],
        clean_zero_call_result=clean,
        clean_zero_call_authority=clean_authority,
        prior_live_result=predecessor,
        prior_capacity_assessment=capacity,
    )
    predecessor["failure_code"] = "different_failure"
    with pytest.raises(runner.CurrentResearchConsumerCanaryError) as exc:
        runner._fixed_pack_micro_judgment_scope_authorized(
            decision,
            cell_ids=["CELL::value_capture"],
            clean_zero_call_result=clean,
            clean_zero_call_authority=clean_authority,
            prior_live_result=predecessor,
            prior_capacity_assessment=capacity,
        )
    assert exc.value.code == "research_consumer_micro_judgment_disposition_invalid"


def test_micro_authority_binds_profiles_budget_digest_and_unused_identity(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runner = _runner()
    authority_path, authority = _tool_loop_authority(tmp_path)
    authority.update(
        {
            "schema_version": runner.MICRO_TOOL_LOOP_AUTHORITY_SCHEMA,
            "status": runner.MICRO_TOOL_LOOP_AUTHORITY_STATUS,
            "execution_budget": {
                "maximum_model_calls": 4,
                "maximum_transport_attempts": 4,
                "maximum_tool_calls": 5,
                "maximum_evidence_requests": 0,
                "retries": 0,
                "fallbacks": 0,
                "planner_calls": 0,
                "external_retrieval_calls": 0,
                "embedding_calls": 0,
                "current_product_pointer_mutations": 0,
            },
        }
    )
    paths = _micro_validation_paths()
    bound: dict[str, object] = {
        "research_input_digest": "1" * 64,
        "finance_loop_messages_digest": "2" * 64,
        "micro_tool_schema_digest": "3" * 64,
    }
    for key, path in paths.items():
        bound[key] = path.relative_to(ROOT).as_posix()
        bound[key[:-4] + "_sha256"] = runner._sha(path)
    authority["bound_inputs"] = bound
    authority_path.write_text(json.dumps(authority), encoding="utf-8")
    commit = authority["implementation_commit"]

    def fake_git(*args):
        if args[0] == "rev-parse":
            return commit
        if args[0] == "status":
            return "?? authority.json"
        raise AssertionError(args)

    output_paths = {
        "capture": tmp_path / "capture",
        "private": tmp_path / "private",
        "public.json": tmp_path / "public.json",
    }
    original_resolve = runner._resolve
    monkeypatch.setattr(runner, "_git", fake_git)
    monkeypatch.setattr(runner, "_relative", lambda path: Path(path).name)
    monkeypatch.setattr(
        runner,
        "_resolve",
        lambda ref: output_paths.get(str(ref), original_resolve(ref)),
    )

    validated = runner.validate_tool_loop_authority(
        authority, authority_path=authority_path
    )
    assert validated["micro_read_profile_ref"] == MICRO_READ_PROFILE
    assert validated["micro_judgment_profile_ref"] == MICRO_JUDGMENT_PROFILE
    assert validated["clean_zero_call_result_ref"] == MICRO_PROOF_RESULT

    digest_drift = json.loads(json.dumps(authority))
    digest_drift["bound_inputs"]["micro_policy_sha256"] = "0" * 64
    with pytest.raises(runner.CurrentResearchConsumerCanaryError) as exc:
        runner.validate_tool_loop_authority(
            digest_drift, authority_path=authority_path
        )
    assert exc.value.code.startswith(
        "research_consumer_tool_loop_bound_input_drift:micro_policy_ref"
    )

    output_paths["public.json"].write_text("{}", encoding="utf-8")
    with pytest.raises(runner.CurrentResearchConsumerCanaryError) as exc:
        runner.validate_tool_loop_authority(
            authority, authority_path=authority_path
        )
    assert exc.value.code == "research_consumer_tool_loop_identity_consumed"


def test_fragment_analysis_submission_runner_keeps_analysis_and_submission_separate(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runner = _runner()
    paths = _micro_tool_loop_paths()
    paths.update(
        {
            "analysis_profile_ref": MICRO_JUDGMENT_PROFILE,
            "submission_profile_ref": MICRO_READ_PROFILE,
        }
    )
    authority_path = tmp_path / "authority.json"
    authority = {
        "schema_version": runner.FRAGMENT_ANALYSIS_SUBMISSION_AUTHORITY_SCHEMA,
        "status": runner.FRAGMENT_ANALYSIS_SUBMISSION_AUTHORITY_STATUS,
        "implementation_commit": "a" * 40,
        "case_key": "DELL",
        "cell_id": "CELL::value_capture",
        "fragment_tool": MICRO_JUDGMENT_TOOL_NAMES[0],
        "execution_budget": {},
        "bound_inputs": {},
        "output_contract": {
            "capture_root_ref": "capture",
            "private_output_root_ref": "private",
            "public_result_ref": "public.json",
            "run_id": "fragment-run",
            "analysis_attempt_id": "analysis-attempt",
            "submission_attempt_id": "submission-attempt",
            "product_publication": "forbidden",
        },
        "known_boundary": "single fragment fixed-Pack unit test only",
    }
    authority_path.write_text(json.dumps(authority), encoding="utf-8")
    destinations = {
        "capture": tmp_path / "capture",
        "private": tmp_path / "private",
        "public.json": tmp_path / "public.json",
    }
    monkeypatch.setattr(
        runner,
        "validate_fragment_analysis_submission_authority",
        lambda _payload, authority_path: paths,
    )
    original_resolve = runner._resolve
    monkeypatch.setattr(
        runner,
        "_resolve",
        lambda ref: destinations.get(str(ref), original_resolve(ref)),
    )
    monkeypatch.setattr(runner, "_relative", lambda path: Path(path).name)

    def analyze(**_kwargs):
        return ChatCompletionResult(
            status="completed_exact_once",
            provider_id="deepseek",
            model="deepseek-v4-pro",
            content="受控分析草案",
            finish_reason="stop",
            usage={"prompt_tokens": 10, "completion_tokens": 5},
            request_capture_ref=str(tmp_path / "analysis-request.json"),
            response_capture_ref=str(tmp_path / "analysis-response.json"),
            request_digest="1" * 64,
            response_digest="2" * 64,
            private_reasoning_fields_redacted=1,
        )

    fragment = _micro_alias_fragments()[MICRO_JUDGMENT_TOOL_NAMES[0]]

    def submit(**_kwargs):
        return ChatCompletionToolStepResult(
            status="completed_exact_once",
            provider_id="deepseek",
            model="deepseek-v4-pro",
            content="",
            reasoning_content="transient",
            tool_calls=(
                {
                    "id": "call-thesis",
                    "type": "function",
                    "function": {
                        "name": MICRO_JUDGMENT_TOOL_NAMES[0],
                        "arguments": json.dumps(fragment, ensure_ascii=False),
                    },
                },
            ),
            finish_reason="tool_calls",
            usage={"prompt_tokens": 20, "completion_tokens": 8},
            request_capture_ref=str(tmp_path / "submit-request.json"),
            response_capture_ref=str(tmp_path / "submit-response.json"),
            request_digest="3" * 64,
            response_digest="4" * 64,
            private_reasoning_fields_redacted=1,
        )

    monkeypatch.setattr(runner, "execute_chat_completion_exact_once", analyze)
    monkeypatch.setattr(
        runner,
        "execute_chat_completion_tool_step_exact_once",
        submit,
    )
    result = runner.run_fragment_analysis_submission(authority_path)
    assert (
        result["status"]
        == "completed_fragment_contract_valid_content_assessment_pending"
    )
    assert result["analysis"]["visible_chars"] == len("受控分析草案")
    assert result["submission"]["tool_call_count"] == 1
    assert result["acceptance"]["submission_tool_contract_pass"] is True
    full = json.loads(
        (tmp_path / "private/full_result.json").read_text(encoding="utf-8")
    )
    assert full["authorship"]["analysis_draft_model_owned"] is True
    assert full["authorship"]["harness_generated_research_judgment"] is False
    assert full["analysis_step"]["content"] == "受控分析草案"


def test_fragment_analysis_submission_authority_binds_clean_runtime_and_scope(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runner = _runner()
    paths = _fragment_validation_paths()
    research_input, context, messages, thesis_tool = (
        runner._fragment_analysis_submission_artifacts(paths)
    )
    commit = "a" * 40
    authority_path = tmp_path / "authority.json"
    bound: dict[str, object] = {
        "research_input_digest": research_input["research_input_digest"],
        "fragment_context_digest": context["projection_digest"],
        "analysis_messages_digest": runner.canonical_digest(list(messages)),
        "submission_tool_schema_digest": runner.canonical_digest(thesis_tool),
    }
    for key, path in paths.items():
        bound[key] = path.relative_to(ROOT).as_posix()
        bound[key[:-4] + "_sha256"] = runner._sha(path)
    authority = {
        "schema_version": runner.FRAGMENT_ANALYSIS_SUBMISSION_AUTHORITY_SCHEMA,
        "status": runner.FRAGMENT_ANALYSIS_SUBMISSION_AUTHORITY_STATUS,
        "implementation_commit": commit,
        "case_key": "DELL",
        "cell_id": "CELL::value_capture",
        "fragment_tool": MICRO_JUDGMENT_TOOL_NAMES[0],
        "execution_budget": {
            "maximum_model_calls": 2,
            "maximum_transport_attempts": 2,
            "maximum_tool_calls": 1,
            "maximum_evidence_requests": 0,
            "retries": 0,
            "fallbacks": 0,
            "planner_calls": 0,
            "external_retrieval_calls": 0,
            "embedding_calls": 0,
            "protocol_switches": 0,
            "current_product_pointer_mutations": 0,
        },
        "bound_inputs": bound,
        "output_contract": {
            "capture_root_ref": "capture",
            "private_output_root_ref": "private",
            "public_result_ref": "public.json",
            "run_id": "fragment-run",
            "analysis_attempt_id": "analysis-attempt",
            "submission_attempt_id": "submission-attempt",
            "product_publication": "forbidden",
        },
        "known_boundary": "single thesis only",
    }
    authority_path.write_text(json.dumps(authority), encoding="utf-8")

    def fake_git(*args):
        if args[0] == "rev-parse":
            return commit
        if args[0] == "status":
            return "?? authority.json"
        raise AssertionError(args)

    output_paths = {
        "capture": tmp_path / "capture",
        "private": tmp_path / "private",
        "public.json": tmp_path / "public.json",
    }
    original_resolve = runner._resolve
    monkeypatch.setattr(runner, "_git", fake_git)
    monkeypatch.setattr(runner, "_relative", lambda path: Path(path).name)
    monkeypatch.setattr(
        runner,
        "_resolve",
        lambda ref: output_paths.get(str(ref), original_resolve(ref)),
    )
    validated = runner.validate_fragment_analysis_submission_authority(
        authority,
        authority_path=authority_path,
    )
    assert validated["analysis_profile_ref"] == MICRO_JUDGMENT_PROFILE
    assert validated["submission_profile_ref"] == MICRO_READ_PROFILE

    drifted = json.loads(json.dumps(authority))
    drifted["bound_inputs"]["fragment_context_digest"] = "0" * 64
    with pytest.raises(runner.CurrentResearchConsumerCanaryError) as exc:
        runner.validate_fragment_analysis_submission_authority(
            drifted,
            authority_path=authority_path,
        )
    assert exc.value.code == "research_consumer_fragment_runtime_digest_drift"


def test_fixed_pack_claim_surface_live_path_uses_surface_contract(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runner = _runner()
    authority_path, authority, paths = _prepare_tool_loop_test(
        runner, monkeypatch, tmp_path
    )
    paths["claim_authority_policy_ref"] = CLAIM_AUTHORITY_POLICY
    paths["claim_surface_authority_policy_ref"] = (
        CLAIM_SURFACE_AUTHORITY_POLICY
    )
    _, research_input, _ = runner._compile_runtime_input(
        paths,
        case_key="DELL",
        required_cell_ids=["CELL::value_capture"],
    )
    assert "claim_surface_authority_contract" in research_input
    value_capture = next(
        row
        for row in research_input["cells"]
        if row["cell_id"] == "CELL::value_capture"
    )
    assert value_capture["allowed_qualitative_fact_refs"] == [
        "QF::DELL::AI_SERVER_OPERATING_INCOME_RATE_TARGET::FY2027Q1"
    ]

    kernel, route, _ = runner._tool_loop_contracts(paths)
    base_policy = runner.load_bounded_finance_loop_policy(
        json.loads(LOOP_POLICY.read_text(encoding="utf-8"))
    )
    scoped_policy = runner.scope_bounded_finance_loop_policy(
        base_policy,
        cell_count=1,
        maximum_evidence_requests=0,
    )
    visible_budget = {
        "maximum_steps": scoped_policy.maximum_steps,
        "maximum_evidence_requests": 0,
        "maximum_reads_per_cell": 1,
        "maximum_parallel_read_tools": 2,
        "maximum_judgments_per_cell": 1,
        "retry_count": 0,
    }
    messages = runner.compile_finance_loop_messages(
        research_input=research_input,
        required_cell_ids=["CELL::value_capture"],
        execution_budget=visible_budget,
    )
    tools = runner.compile_finance_loop_tools(
        research_input=research_input,
        required_cell_ids=["CELL::value_capture"],
        kernel=kernel,
        route_policy=route,
        policy=scoped_policy,
        strict=False,
    )
    proof_path = paths["clean_zero_call_result_ref"]
    proof_path.write_text(
        json.dumps(
            {
                "status": "engineering_pass_zero_call_claim_surface_authority",
                "result_digest": "d" * 64,
                "normalized_proof": {
                    "claim_surface_input_digest": research_input[
                        "research_input_digest"
                    ],
                    "finance_loop_messages_digest": runner.canonical_digest(
                        list(messages)
                    ),
                    "standard_tool_schema_digest": runner.canonical_digest(
                        list(tools)
                    ),
                    "structured_claim_relations_per_atom": 3,
                    "qualitative_band_converted_to_point_estimate": False,
                    "fake_loop_steps": 2,
                    "fake_loop_tool_calls": 3,
                    "fake_loop_evidence_requests": 0,
                    "agentic_research_claimed": False,
                    "model_calls": 0,
                    "network_calls": 0,
                    "retries": 0,
                },
            }
        ),
        encoding="utf-8",
    )
    predecessor_path = tmp_path / "predecessor.json"
    predecessor_path.write_text(
        json.dumps(
            {
                "status": "terminal_failed_no_retry",
                "failure_code": (
                    "finance_loop_judgment_invalid:"
                    "research_consumer_thesis_atom_invalid"
                ),
                "result_digest": "e" * 64,
                "execution": {"retries": 0, "fallbacks": 0},
            }
        ),
        encoding="utf-8",
    )
    decision_path = tmp_path / "claim-surface-decision.json"
    decision_path.write_text(
        json.dumps(
            {
                "status": (
                    "fixed_pack_claim_surface_authority_zero_call_pass_"
                    "one_chat_replacement_authorized"
                ),
                "case_key": "DELL",
                "cell_id": "CELL::value_capture",
                "next_authorized_scope": (
                    "one_DELL_value_capture_fixed_pack_claim_surface_"
                    "Chat_replacement"
                ),
                "clean_zero_call_result_digest": "d" * 64,
                "immutable_predecessor_result_ref": "predecessor.json",
                "immutable_predecessor_result_sha256": runner._sha(
                    predecessor_path
                ),
                "immutable_predecessor_result_digest": "e" * 64,
                "replacement_is_new_attempt_not_retry": True,
                "historical_failure_promoted": False,
                "maximum_evidence_requests": 0,
                "chat_live_authorized": True,
                "responses_live_authorized": False,
                "anthropic_live_authorized": False,
                "dynamic_layer_two_authorized": False,
                "five_cell_live_authorized": False,
                "product_publication_authorized": False,
                "retries": 0,
                "fallbacks": 0,
            }
        ),
        encoding="utf-8",
    )
    paths["prior_scope_decision_ref"] = decision_path
    authority["execution_budget"].update(
        {
            "maximum_model_calls": scoped_policy.maximum_steps,
            "maximum_transport_attempts": scoped_policy.maximum_steps,
            "maximum_evidence_requests": 0,
        }
    )
    authority["bound_inputs"] = {
        "research_input_digest": research_input["research_input_digest"],
        "finance_loop_messages_digest": runner.canonical_digest(list(messages)),
        "standard_tool_schema_digest": runner.canonical_digest(list(tools)),
    }
    authority_path.write_text(json.dumps(authority), encoding="utf-8")
    destinations = {
        "capture": tmp_path / "capture",
        "private": tmp_path / "private",
        "public.json": tmp_path / "public.json",
        "predecessor.json": predecessor_path,
    }
    monkeypatch.setattr(
        runner,
        "_resolve",
        lambda ref: destinations[str(ref)],
    )
    fake = json.loads(CLAIM_SURFACE_FAKE.read_text(encoding="utf-8"))
    judgment = fake["cells"][0]

    def executor(**kwargs):
        index = int(str(kwargs["attempt_id"]).split("-")[-3])
        if index == 1:
            return _parallel_tool_step(
                index, "CELL::value_capture", tmp_path / "capture"
            )
        return _tool_step(
            index,
            SUBMIT_RESEARCH_JUDGMENT_TOOL,
            judgment,
            tmp_path / "capture",
        )

    result = runner.run_tool_loop(authority_path, step_executor=executor)

    assert result["status"] == "completed_contract_valid_content_assessment_pending"
    assert result["execution"]["model_calls_attempted"] == 2
    assert result["tool_counts"] == {
        READ_REVIEWED_EVIDENCE_TOOL: 1,
        READ_NUMERIC_FACTS_TOOL: 1,
        SUBMIT_RESEARCH_JUDGMENT_TOOL: 1,
    }
    full = json.loads(
        (tmp_path / "private" / "full_result.json").read_text(
            encoding="utf-8"
        )
    )
    receipt = full["loop_result"]["structured_deliverable"]["cells"][0][
        "claim_surface_authority_receipt"
    ]
    assert receipt["qualitative_fact_refs"] == [
        "QF::DELL::AI_SERVER_OPERATING_INCOME_RATE_TARGET::FY2027Q1"
    ]


def test_claim_relation_alias_successor_requires_bound_capacity_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runner = _runner()
    predecessor = tmp_path / "capacity-r1.json"
    predecessor.write_text(
        json.dumps(
            {
                "status": "terminal_failed_no_retry",
                "failure_code": "model_gateway_reasoning_budget_exhausted",
                "result_digest": "a" * 64,
                "execution": {"retries": 0, "fallbacks": 0},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        runner,
        "_resolve",
        lambda ref: predecessor if ref == "capacity-r1.json" else Path(ref),
    )
    decision = {
        "status": (
            "fixed_pack_claim_relation_alias_capacity_zero_call_pass_"
            "one_chat_successor_authorized"
        ),
        "case_key": "DELL",
        "cell_id": "CELL::value_capture",
        "next_authorized_scope": (
            "one_DELL_value_capture_fixed_pack_claim_relation_alias_"
            "Chat_successor"
        ),
        "clean_zero_call_result_digest": "b" * 64,
        "immutable_predecessor_result_ref": "capacity-r1.json",
        "immutable_predecessor_result_sha256": runner._sha(predecessor),
        "immutable_predecessor_result_digest": "a" * 64,
        "maximum_evidence_requests": 0,
        "chat_live_authorized": True,
        "responses_live_authorized": False,
        "anthropic_live_authorized": False,
        "dynamic_layer_two_authorized": False,
        "five_cell_live_authorized": False,
        "product_publication_authorized": False,
        "same_evidence_pack_and_provider_profile": True,
        "reasoning_or_token_limit_increase": False,
        "retries": 0,
        "fallbacks": 0,
        "replacement_is_new_attempt_not_retry": True,
        "historical_failure_promoted": False,
    }
    assert runner._fixed_pack_claim_relation_alias_replacement_scope_authorized(
        decision,
        cell_ids=["CELL::value_capture"],
        clean_zero_call_result={"result_digest": "b" * 64},
    ) is True

    contaminated = dict(decision)
    contaminated["same_evidence_pack_and_provider_profile"] = False
    with pytest.raises(runner.CurrentResearchConsumerCanaryError) as exc:
        runner._fixed_pack_claim_relation_alias_replacement_scope_authorized(
            contaminated,
            cell_ids=["CELL::value_capture"],
            clean_zero_call_result={"result_digest": "b" * 64},
        )
    assert exc.value.args[0] == (
        "research_consumer_claim_relation_alias_replacement_disposition_invalid"
    )


def test_standard_tool_loop_accepts_digest_bound_research_context_decision(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runner = _runner()
    authority_path, _, paths = _prepare_tool_loop_test(
        runner, monkeypatch, tmp_path
    )
    decision_path = tmp_path / "research-context-decision.json"
    decision_path.write_text(
        json.dumps(
            {
                "status": (
                    "research_context_closure_zero_call_pass_"
                    "one_chat_revalidation_authorized"
                ),
                "case_key": "DELL",
                "cell_id": "CELL::value_capture",
                "next_authorized_scope": (
                    "one_Chat_DELL_value_capture_revalidation_after_"
                    "research_context_closure"
                ),
                "clean_zero_call_result_digest": "c" * 64,
                "chat_live_authorized": True,
                "responses_live_authorized": False,
                "five_cell_live_authorized": False,
                "other_role_method_pack_migration_authorized": False,
            }
        ),
        encoding="utf-8",
    )
    paths["prior_scope_decision_ref"] = decision_path
    fake = json.loads(FAKE.read_text(encoding="utf-8"))
    judgment = next(
        row
        for row in fake["cells"]
        if row["cell_id"] == "CELL::value_capture"
    )

    def executor(**kwargs):
        index = int(str(kwargs["attempt_id"]).split("-")[-3])
        if index == 1:
            return _parallel_tool_step(
                index, "CELL::value_capture", tmp_path / "capture"
            )
        return _tool_step(
            index,
            SUBMIT_RESEARCH_JUDGMENT_TOOL,
            judgment,
            tmp_path / "capture",
        )

    result = runner.run_tool_loop(authority_path, step_executor=executor)

    assert result["status"] == "completed_contract_valid_content_assessment_pending"
    assert result["acceptance"]["five_cell_live_authorized"] is False


def test_standard_tool_loop_accepts_bound_incomplete_read_replacement_decision(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runner = _runner()
    authority_path, _, paths = _prepare_tool_loop_test(
        runner, monkeypatch, tmp_path
    )
    proof_path = tmp_path / "transport-proof.json"
    proof_path.write_text(
        json.dumps(
            {
                "status": "zero_call_incomplete_read_capture_replay_pass",
                "result_digest": "d" * 64,
                "normalized_proof": {
                    "provider_neutral_shared_terminal_capture_path": True,
                    "ordinary_chat_and_tool_calls_both_covered": True,
                    "model_calls": 0,
                    "network_calls": 0,
                    "provider_calls": 0,
                    "retries": 0,
                    "valid_json_partial_mutation": {
                        "transport_attempts": 1,
                        "eligible_for_contract_parse": False,
                        "eligible_for_business_promotion": False,
                    },
                    "malformed_partial_mutation": {
                        "transport_attempts": 1,
                        "partial_plaintext_persisted": False,
                        "private_reasoning_leaked": False,
                        "eligible_for_contract_parse": False,
                        "eligible_for_business_promotion": False,
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    r1_result_path = tmp_path / "immutable-r1-result.json"
    r1_authority_ref = "immutable-r1-authority.json"
    r1_result_path.write_text(
        json.dumps(
            {
                "status": "terminal_failed_no_retry",
                "failure_code": "model_gateway_transport_error",
                "authority_ref": r1_authority_ref,
                "execution": {"retries": 0, "fallbacks": 0},
            }
        ),
        encoding="utf-8",
    )
    decision_path = tmp_path / "replacement-decision.json"
    decision_path.write_text(
        json.dumps(
            {
                "status": (
                    "incomplete_read_capture_replay_pass_"
                    "one_chat_replacement_authorized"
                ),
                "case_key": "DELL",
                "cell_id": "CELL::value_capture",
                "next_authorized_scope": (
                    "one_Chat_DELL_value_capture_replacement_after_"
                    "incomplete_read_capture_replay"
                ),
                "research_context_zero_call_result_digest": "c" * 64,
                "chat_live_authorized": True,
                "responses_live_authorized": False,
                "anthropic_live_authorized": False,
                "five_cell_live_authorized": False,
                "other_role_method_pack_migration_authorized": False,
                "external_retrieval_authorized": False,
                "product_publication_authorized": False,
                "retries": 0,
                "fallbacks": 0,
                "replacement_boundary": {
                    "transport_capture_proof_ref": "transport-proof",
                    "transport_capture_proof_sha256": runner._sha(proof_path),
                    "transport_capture_proof_result_digest": "d" * 64,
                    "immutable_r1_result_ref": "immutable-r1-result",
                    "immutable_r1_result_sha256": runner._sha(r1_result_path),
                    "immutable_r1_authority_ref": r1_authority_ref,
                    "replacement_is_new_attempt_not_retry": True,
                    "historical_partial_recovery_claimed": False,
                },
            }
        ),
        encoding="utf-8",
    )
    paths["prior_scope_decision_ref"] = decision_path
    destinations = {
        "capture": tmp_path / "capture",
        "private": tmp_path / "private",
        "public.json": tmp_path / "public.json",
        "transport-proof": proof_path,
        "immutable-r1-result": r1_result_path,
    }
    monkeypatch.setattr(
        runner,
        "_resolve",
        lambda ref: destinations[str(ref)],
    )
    fake = json.loads(FAKE.read_text(encoding="utf-8"))
    judgment = next(
        row
        for row in fake["cells"]
        if row["cell_id"] == "CELL::value_capture"
    )

    def executor(**kwargs):
        index = int(str(kwargs["attempt_id"]).split("-")[-3])
        if index == 1:
            return _parallel_tool_step(
                index, "CELL::value_capture", tmp_path / "capture"
            )
        return _tool_step(
            index,
            SUBMIT_RESEARCH_JUDGMENT_TOOL,
            judgment,
            tmp_path / "capture",
        )

    result = runner.run_tool_loop(authority_path, step_executor=executor)

    assert result["status"] == "completed_contract_valid_content_assessment_pending"
    assert result["execution"]["retries"] == 0
    assert result["acceptance"]["five_cell_live_authorized"] is False


def test_standard_tool_loop_failure_preserves_successful_prefix_without_retry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runner = _runner()
    authority_path, _, _ = _prepare_tool_loop_test(
        runner, monkeypatch, tmp_path
    )

    def executor(**kwargs):
        index = int(str(kwargs["attempt_id"]).split("-")[-3])
        if index == 2:
            raise ModelGatewayError(
                "model_gateway_transport_error",
                capture_ref=str(tmp_path / "capture" / "failed-response.json"),
            )
        return _tool_step(
            index,
            READ_REVIEWED_EVIDENCE_TOOL,
            {"cell_id": "CELL::value_capture"},
            tmp_path / "capture",
        )

    result = runner.run_tool_loop(authority_path, step_executor=executor)

    assert result["status"] == "terminal_failed_no_retry"
    assert result["failure_phase"] == "provider_transport_or_response"
    assert result["failure_code"] == "model_gateway_transport_error"
    assert result["execution"]["model_calls_attempted"] == 2
    assert result["execution"]["retries"] == 0
    assert result["accepted_receipt_count"] == 1
    assert len(result["provider_steps"]) == 1
    assert result["failure_capture_ref"] == "failed-response.json"


def test_live_runner_is_case_bound_and_has_exact_once_budget() -> None:
    runner = _runner()
    source = SCRIPT.read_text(encoding="utf-8")

    assert 'case_key = str(authority["case_key"])' in source
    assert 'evidence_service.get_case(\n        case_key,' in source
    assert 'retrieval_service.execute_controlled_plan(\n        case_key,' in source
    assert '"model_calls": 1' in source
    assert '"transport_attempts": 1' in source
    assert '"retries": 0' in source
    assert '"fallbacks": 0' in source
    assert '"external_retrieval_calls": 0' in source
    assert '"planner_calls": 0' in source
    assert '"current_product_pointer_mutations": 0' in source
    assert runner.AUTHORITY_SCHEMA.endswith("_v1_1")


def test_terminal_summary_preserves_success_usage_and_no_product_claim(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runner = _runner()
    monkeypatch.setattr(runner, "_relative", lambda path: Path(path).name)
    authority_path = tmp_path / "authority.json"
    authority_path.write_text("{}", encoding="utf-8")
    request = ROOT / ".codex_runtime/model_runs/test/request.json"
    response = ROOT / ".codex_runtime/model_runs/test/response.json"
    provider = ChatCompletionResult(
        status="completed_exact_once",
        provider_id="fixture",
        model="fixture-model",
        content="{}",
        finish_reason="stop",
        usage={"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
        request_capture_ref=str(request),
        response_capture_ref=str(response),
        request_digest="a" * 64,
        response_digest="b" * 64,
        private_reasoning_fields_redacted=1,
    )
    research_input = {
        "case_identity": {"case_key": "DELL", "research_as_of": "2026-08-06"},
        "research_input_digest": "c" * 64,
        "evidence_pack_binding": {
            "artifact_digest": "d" * 64,
            "pack_payload_digest": "e" * 64,
        },
    }
    summary = runner._terminal_summary(
        authority={
            "implementation_commit": "f" * 40,
            "output_contract": {"result_id": "RESULT-1"},
            "known_boundary": "not product acceptance",
        },
        authority_path=authority_path,
        research_input=research_input,
        provider_result=provider,
        status="completed_contract_valid",
        failure_phase="",
        failure_code="",
        model_call_attempted=True,
        transport_attempted=True,
    )

    assert summary["terminal"]["model_calls"] == 1
    assert summary["terminal"]["retries"] == 0
    assert summary["terminal"]["product_publication"] is False
    assert summary["provider"]["usage"]["total_tokens"] == 5
    assert summary["acceptance"]["natural_research_quality_proven"] is False
    assert summary["acceptance"]["s3_product_acceptance"] is False


def test_gateway_failure_capture_is_terminalized_without_retry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runner = _runner()
    monkeypatch.setattr(runner, "_relative", lambda path: Path(path).name)
    authority_path = tmp_path / "authority.json"
    result_path = tmp_path / "result.json"
    authority = {
        "output_contract": {
            "capture_root_ref": ".codex_runtime/model_runs/fixture",
            "private_output_root_ref": "data/workbench_private/fixture",
            "public_result_ref": result_path.relative_to(tmp_path).as_posix(),
            "result_id": "RESULT-FAIL",
            "run_id": "RUN-FAIL",
            "attempt_id": "ATTEMPT-01",
            "product_publication": "forbidden",
        },
        "implementation_commit": "a" * 40,
        "case_key": "DELL",
        "known_boundary": "fixture",
        "bound_inputs": {"model_visible_messages_sha256": "b" * 64},
    }
    authority_path.write_text(json.dumps(authority), encoding="utf-8")
    research_input = {
        "case_identity": {"case_key": "DELL", "research_as_of": "2026-08-06"},
        "research_input_digest": "c" * 64,
        "evidence_pack_binding": {
            "artifact_digest": "d" * 64,
            "pack_payload_digest": "e" * 64,
        },
    }

    monkeypatch.setattr(runner, "_json", lambda path: authority if path == authority_path else {})
    monkeypatch.setattr(runner, "validate_authority", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        runner,
        "_compile_runtime_input",
        lambda *_args, **_kwargs: ({}, research_input, ({"role": "user", "content": "x"},)),
    )

    # The detailed gateway behavior is covered in test_capture_first_chat_completions;
    # this runner-level test protects the no-retry terminal accounting helper.
    response_ref = ROOT / ".codex_runtime/model_runs/fixture/provider_response.json"
    error = ModelGatewayError(
        "model_gateway_transport_error",
        capture_ref=str(response_ref),
    )
    assert error.code == "model_gateway_transport_error"
    summary = runner._terminal_summary(
        authority=authority,
        authority_path=authority_path,
        research_input=research_input,
        provider_result=None,
        status="terminal_failed_no_retry",
        failure_phase="provider_transport_or_response",
        failure_code=error.code,
        model_call_attempted=True,
        transport_attempted=True,
        provider_identity={"provider_id": "fixture", "model": "fixture-model"},
        response_capture_ref=runner._relative(response_ref),
    )
    assert summary["status"] == "terminal_failed_no_retry"
    assert summary["terminal"]["transport_attempts"] == 1
    assert summary["terminal"]["retries"] == 0
    assert summary["provider"]["response_capture_ref"].endswith(
        "provider_response.json"
    )


def _paired_fixture():
    runner = _runner()
    paths = {
        "objective_ref": ROOT
        / "configs/research/evals/"
        "fin_ia_0_1_3_s3_dell_minimal_planner_canary_objective_v1_0.json",
        "planner_atoms_ref": ROOT
        / "tests/fixtures/research/"
        "fin_ia_0_1_3_s3_dell_planner_r1_atoms_v1_0.json",
        "consumer_policy_ref": ROOT
        / "configs/research/"
        "fin_ia_0_1_3_s3_current_research_consumer_policy_v1_2.json",
    }
    paired = runner._compile_paired_inputs(
        paths,
        case_key="DELL",
        cell_id="CELL::value_capture",
    )
    research_input, json_messages, strict_messages, strict_tool, digest = paired
    fake = json.loads(
        (
            ROOT
            / "tests/fixtures/research/"
            "fin_ia_0_1_3_s3_dell_current_research_consumer_fake_payload_v1_2.json"
        ).read_text(encoding="utf-8")
    )
    judgment = next(
        row for row in fake["cells"] if row["cell_id"] == "CELL::value_capture"
    )
    return (
        runner,
        research_input,
        json_messages,
        strict_messages,
        strict_tool,
        digest,
        judgment,
    )


def test_paired_runner_uses_same_payload_and_validates_both_lanes(
    tmp_path: Path,
) -> None:
    (
        runner,
        research_input,
        json_messages,
        strict_messages,
        strict_tool,
        digest,
        judgment,
    ) = _paired_fixture()

    def json_executor(**_kwargs):
        return ChatCompletionResult(
            status="completed_exact_once",
            provider_id="deepseek",
            model="deepseek-v4-pro",
            content=json.dumps({"cells": [judgment]}, ensure_ascii=False),
            finish_reason="stop",
            usage={"total_tokens": 10},
            request_capture_ref=str(ROOT / ".codex_runtime/test/json-request.json"),
            response_capture_ref=str(ROOT / ".codex_runtime/test/json-response.json"),
            request_digest="json-request",
            response_digest="json-response",
            private_reasoning_fields_redacted=1,
        )

    def strict_executor(**kwargs):
        assert kwargs["tool_choice"] is None
        strict_args = json.loads(json.dumps(judgment, ensure_ascii=False))
        if strict_args["what_would_change"]["threshold_numeric_ref"] is None:
            strict_args["what_would_change"]["threshold_numeric_ref"] = ""
        return ChatCompletionToolStepResult(
            status="completed_exact_once_tool_step",
            provider_id="deepseek",
            model="deepseek-v4-pro",
            content="",
            reasoning_content="private-transient",
            tool_calls=(
                {
                    "id": "call-1",
                    "type": "function",
                    "function": {
                        "name": SUBMIT_RESEARCH_JUDGMENT_TOOL,
                        "arguments": json.dumps(strict_args, ensure_ascii=False),
                    },
                },
            ),
            finish_reason="tool_calls",
            usage={"total_tokens": 11},
            request_capture_ref=str(ROOT / ".codex_runtime/test/strict-request.json"),
            response_capture_ref=str(ROOT / ".codex_runtime/test/strict-response.json"),
            request_digest="strict-request",
            response_digest="strict-response",
            private_reasoning_fields_redacted=1,
        )

    recorded: list[str] = []
    full = run_paired_research_submission(
        research_input=research_input,
        submission=PairedResearchSubmission(
            json_messages=json_messages,
            strict_messages=strict_messages,
            strict_tool=strict_tool,
            business_payload_digest=digest,
        ),
        json_profile=object(),
        strict_profile=object(),
        capture_root=tmp_path / "captures",
        run_id="TEST-RUN",
        json_attempt_id="JSON-01",
        strict_attempt_id="STRICT-01",
        cell_id="CELL::value_capture",
        capture_ref_formatter=lambda value: value,
        lane_recorder=lambda lane, _value: recorded.append(lane),
        json_executor=json_executor,
        strict_executor=strict_executor,
    )

    assert full["json_lane"]["status"] == "contract_valid"
    assert full["strict_lane"]["status"] == "contract_valid"
    assert full["tool_choice_sent"] is False
    assert "private-transient" not in json.dumps(full, ensure_ascii=False)
    assert recorded == ["json_lane", "strict_lane"]


def test_paired_json_transport_failure_skips_strict_lane(tmp_path: Path) -> None:
    (
        runner,
        research_input,
        json_messages,
        strict_messages,
        strict_tool,
        digest,
        _,
    ) = _paired_fixture()
    calls = 0

    def json_executor(**_kwargs):
        raise ModelGatewayError("model_gateway_transport_error")

    def strict_executor(**_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("strict lane must not run")

    full = run_paired_research_submission(
        research_input=research_input,
        submission=PairedResearchSubmission(
            json_messages=json_messages,
            strict_messages=strict_messages,
            strict_tool=strict_tool,
            business_payload_digest=digest,
        ),
        json_profile=object(),
        strict_profile=object(),
        capture_root=tmp_path / "captures",
        run_id="TEST-FAIL",
        json_attempt_id="JSON-01",
        strict_attempt_id="STRICT-01",
        cell_id="CELL::value_capture",
        capture_ref_formatter=lambda value: value,
        json_executor=json_executor,
        strict_executor=strict_executor,
    )

    assert calls == 0
    assert full["strict_skipped"] is True
    assert full["strict_lane"]["failure_code"] == "paired_submission_strict_skipped"


def test_paired_http_400_does_not_hide_strict_qualification() -> None:
    assert shared_provider_failure("model_gateway_http_error:400") is False
    assert shared_provider_failure("model_gateway_http_error:401") is True
    assert shared_provider_failure("model_gateway_http_error:429") is True
    assert shared_provider_failure("model_gateway_transport_error") is True


def test_paired_submission_rejects_business_digest_drift(tmp_path: Path) -> None:
    (
        _,
        research_input,
        json_messages,
        strict_messages,
        strict_tool,
        _,
        _,
    ) = _paired_fixture()

    with pytest.raises(PairedSubmissionError, match="business_digest_drift"):
        run_paired_research_submission(
            research_input=research_input,
            submission=PairedResearchSubmission(
                json_messages=json_messages,
                strict_messages=strict_messages,
                strict_tool=strict_tool,
                business_payload_digest="0" * 64,
            ),
            json_profile=object(),
            strict_profile=object(),
            capture_root=tmp_path / "captures",
            run_id="TEST-DRIFT",
            json_attempt_id="JSON-01",
            strict_attempt_id="STRICT-01",
            cell_id="CELL::value_capture",
            capture_ref_formatter=lambda value: value,
            json_executor=lambda **_kwargs: (_ for _ in ()).throw(
                AssertionError("provider must not run")
            ),
            strict_executor=lambda **_kwargs: (_ for _ in ()).throw(
                AssertionError("provider must not run")
            ),
        )
