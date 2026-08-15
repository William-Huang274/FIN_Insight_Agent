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
