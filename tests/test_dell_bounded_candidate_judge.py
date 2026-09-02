from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any

import pytest

import scripts.research.run_dell_bounded_candidate_judge as runner
from sec_agent.agent_runtime.bounded_candidate_judge import (
    BoundedCandidateJudgeError,
    build_candidate_judge_messages,
    find_banned_qrel_input_keys,
    validate_candidate_judge_input,
    validate_candidate_judge_output,
)
from sec_agent.providers.chat_completions import (
    ChatCompletionResult,
    load_chat_completion_profile,
)


def _candidate(query_index: int, rank: int) -> dict[str, Any]:
    issuer = "NVIDIA" if query_index == 1 else "MICRON"
    return {
        "node_id": f"NODE::{query_index}::{rank}",
        "retrieval_rank": rank,
        "node_kind": "table" if rank % 2 == 0 else "chunk",
        "issuer_id": issuer,
        "fiscal_period": "FY2027_Q2" if query_index == 1 else "FY2026_Q3",
        "route_id": "route_one" if query_index == 1 else "route_two",
        "source_role": "supplier_management_disclosure",
        "publication_date": "2026-08-26",
        "period_end": "2026-07-26",
        "section_path": ["Results"],
        "page_start": None,
        "page_end": None,
        "stable_url": f"https://example.test/{query_index}/{rank}",
        "content": f"Candidate {rank} bounded local content.",
        "candidate_is_not_evidence": True,
        "citation_eligible": False,
        "numeric_authority": False,
    }


def _input_value() -> dict[str, Any]:
    cases = []
    for query_index in (1, 2):
        requirement_ids = (
            ("metric", "sequential_growth", "year_over_year_growth")
            if query_index == 1
            else ("revenue", "gaap_gross_margin")
        )
        cases.append(
            {
                "query_id": f"Q{query_index}",
                "question_zh": f"问题 {query_index}",
                "retrieval_query_en": f"query {query_index}",
                "issuer_ids": ["NVIDIA" if query_index == 1 else "MICRON"],
                "fiscal_periods": [
                    "FY2027_Q2" if query_index == 1 else "FY2026_Q3"
                ],
                "source_roles": ["supplier_management_disclosure"],
                "route_ids": ["route_one" if query_index == 1 else "route_two"],
                "requirements": [
                    {
                        "requirement_id": requirement_id,
                        "description": requirement_id.replace("_", " "),
                    }
                    for requirement_id in requirement_ids
                ],
                "candidates": [
                    _candidate(query_index, rank) for rank in range(1, 7)
                ],
            }
        )
    return {
        "schema_version": "fin_ia_dell_bounded_candidate_judge_input_v1_0",
        "task": "select_minimal_sufficient_local_candidates",
        "candidate_authority": "candidate_only_not_evidence",
        "external_knowledge_allowed": False,
        "cases": cases,
    }


def _valid_output() -> dict[str, Any]:
    judgments = []
    for query_index, requirements in (
        (1, ("metric", "sequential_growth", "year_over_year_growth")),
        (2, ("revenue", "gaap_gross_margin")),
    ):
        selected = f"NODE::{query_index}::6"
        judgments.append(
            {
                "query_id": f"Q{query_index}",
                "decision": "select",
                "candidate_assessments": [
                    {
                        "node_id": f"NODE::{query_index}::{rank}",
                        "verdict": (
                            "full_support" if rank == 6 else "irrelevant"
                        ),
                        "covered_requirement_ids": (
                            list(requirements) if rank == 6 else []
                        ),
                    }
                    for rank in range(1, 7)
                ],
                "selected_node_ids": [selected],
                "requirement_coverage": [
                    {
                        "requirement_id": requirement_id,
                        "supporting_node_ids": [selected],
                    }
                    for requirement_id in requirements
                ],
                "confidence": "high",
                "rationale": "The selected candidate directly covers every field.",
            }
        )
    return {
        "schema_version": "fin_ia_dell_bounded_candidate_judge_output_v1_0",
        "judgments": judgments,
    }


def test_strict_candidate_judge_accepts_complete_candidate_only_selection() -> None:
    model_input = validate_candidate_judge_input(_input_value())
    parsed = validate_candidate_judge_output(
        _valid_output(), model_input=model_input
    )

    assert [row.query_id for row in parsed.judgments] == ["Q1", "Q2"]
    assert parsed.judgments[0].selected_node_ids == ("NODE::1::6",)
    messages = build_candidate_judge_messages(model_input)
    assert len(messages) == 2
    assert "JSON" in messages[0]["content"]
    assert not find_banned_qrel_input_keys(json.loads(messages[1]["content"]))


@pytest.mark.parametrize(
    "banned_key",
    [
        "gold_node_ids",
        "hard_negative_node_ids",
        "partial_node_ids",
        "derivable_node_ids",
    ],
)
def test_input_rejects_evaluation_only_qrel_labels(banned_key: str) -> None:
    value = _input_value()
    value["cases"][0][banned_key] = ["NODE::1::6"]

    with pytest.raises(
        BoundedCandidateJudgeError, match="candidate_judge_qrel_label_leakage"
    ):
        validate_candidate_judge_input(value)


def test_output_rejects_cross_query_candidate_and_incomplete_coverage() -> None:
    model_input = validate_candidate_judge_input(_input_value())
    cross_query = _valid_output()
    cross_query["judgments"][0]["selected_node_ids"] = ["NODE::2::6"]
    with pytest.raises(
        BoundedCandidateJudgeError,
        match="candidate_judge_selected_candidate_set_invalid",
    ):
        validate_candidate_judge_output(cross_query, model_input=model_input)

    incomplete = _valid_output()
    incomplete["judgments"][0]["requirement_coverage"].pop()
    with pytest.raises(
        BoundedCandidateJudgeError,
        match="candidate_judge_selected_requirement_coverage_incomplete",
    ):
        validate_candidate_judge_output(incomplete, model_input=model_input)


def test_repository_config_and_profile_are_bounded_and_answer_free() -> None:
    config = runner.load_candidate_judge_config(runner.DEFAULT_CONFIG)
    profile_payload = json.loads(runner.DEFAULT_PROFILE.read_text(encoding="utf-8"))
    profile = load_chat_completion_profile(profile_payload)

    assert not find_banned_qrel_input_keys(config)
    assert config["case_id"] == "DELL_AI_INFRA_REFERENCE_VERTICAL"
    assert config["authority"] == {
        "provider_attempt_ceiling": 1,
        "retry_count": 0,
        "fallback_model_allowed": False,
        "external_knowledge_allowed": False,
        "candidate_only": True,
        "evidence_promotion_authorized": False,
        "formal_qualification_claimed": False,
        "source_attempt_mutation_authorized": False,
    }
    assert profile.model == "deepseek-v4-pro"
    assert profile.request_defaults == {
        "max_tokens": 2000,
        "stream": False,
        "response_format": {"type": "json_object"},
        "thinking": {"type": "disabled"},
    }


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _prepared(tmp_path: Path) -> dict[str, Any]:
    tmp_path.mkdir(parents=True, exist_ok=False)
    source_paths = {}
    for name in ("manifest", "route_results", "retrieval_nodes"):
        path = tmp_path / f"{name}.json"
        path.write_text(f"{name}\n", encoding="utf-8")
        source_paths[name] = path
    model_input = validate_candidate_judge_input(_input_value())
    profile = load_chat_completion_profile(
        {
            "schema_version": "fin_ia_chat_completion_provider_profile_v1_0",
            "status": "experimental_provider_profile_not_product_authority",
            "provider_id": "deepseek",
            "wire_api": "openai_compatible_chat_completions",
            "base_url": "https://api.deepseek.com",
            "endpoint": "/chat/completions",
            "model": "deepseek-v4-pro",
            "api_key_env": "DEEPSEEK_API_KEY",
            "timeout_seconds": 120,
            "maximum_response_bytes": 1048576,
            "request_defaults": {
                "max_tokens": 2000,
                "stream": False,
                "response_format": {"type": "json_object"},
                "thinking": {"type": "disabled"},
            },
            "authority": {
                "transport_attempt_ceiling": 1,
                "retry_count": 0,
                "capture_model_visible_request": True,
                "capture_assistant_output": True,
                "credential_capture_forbidden": True,
                "provider_private_reasoning_capture_forbidden": True,
                "provider_specific_profile_outside_core": True,
            },
        }
    )
    return {
        "config": {
            "case_id": "TEST",
            "token_budget_basis": {"max_input_characters": 40000},
        },
        "profile": profile,
        "source_root": tmp_path,
        "source_paths": source_paths,
        "source_digests": {
            name: _sha(path) for name, path in source_paths.items()
        },
        "model_input": model_input,
        "model_input_value": model_input.model_dump(mode="json"),
        "messages": build_candidate_judge_messages(model_input),
        "input_characters": 5000,
        "scope_receipts": {},
        "config_sha256": "a" * 64,
        "profile_sha256": "b" * 64,
    }


def test_exact_once_runner_writes_candidate_only_success(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    prepared = _prepared(tmp_path / "source")
    monkeypatch.setattr(runner, "prepare_attempt", lambda **_: prepared)
    monkeypatch.setattr(
        runner,
        "_git_projection",
        lambda: {"branch": "test", "head": "c" * 40, "dirty": True},
    )
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-only-secret")
    calls = 0

    def fake_gateway(**_: Any) -> ChatCompletionResult:
        nonlocal calls
        calls += 1
        return ChatCompletionResult(
            status="completed_exact_once",
            provider_id="deepseek",
            model="deepseek-v4-pro",
            content=json.dumps(_valid_output()),
            finish_reason="stop",
            usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            request_capture_ref="request.json",
            response_capture_ref="response.json",
            request_digest="d" * 64,
            response_digest="e" * 64,
            private_reasoning_fields_redacted=0,
        )

    monkeypatch.setattr(runner, "execute_chat_completion_exact_once", fake_gateway)
    attempt_root = tmp_path / "success"
    result = runner.execute_attempt(
        config_path=tmp_path / "config.json",
        profile_path=tmp_path / "profile.json",
        attempt_root=attempt_root,
        run_id="TEST-RUN",
        attempt_id="TEST-ATTEMPT",
    )

    assert calls == 1
    assert result["status"] == "completed_exact_once_candidate_only"
    assert result["candidate_selection_promoted"] is False
    assert result["evidence_promotion_authorized"] is False
    assert (attempt_root / "result.json").is_file()
    assert not (attempt_root / "terminal_failure.json").exists()


def test_finish_reason_failure_is_immutable_and_never_retried(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    prepared = _prepared(tmp_path / "source")
    monkeypatch.setattr(runner, "prepare_attempt", lambda **_: prepared)
    monkeypatch.setattr(
        runner,
        "_git_projection",
        lambda: {"branch": "test", "head": "c" * 40, "dirty": True},
    )
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-only-secret")
    calls = 0

    def fake_gateway(**_: Any) -> ChatCompletionResult:
        nonlocal calls
        calls += 1
        return ChatCompletionResult(
            status="completed_exact_once",
            provider_id="deepseek",
            model="deepseek-v4-pro",
            content=json.dumps(_valid_output()),
            finish_reason="length",
            usage={"prompt_tokens": 100, "completion_tokens": 2000, "total_tokens": 2100},
            request_capture_ref="request.json",
            response_capture_ref="response.json",
            request_digest="d" * 64,
            response_digest="e" * 64,
            private_reasoning_fields_redacted=0,
        )

    monkeypatch.setattr(runner, "execute_chat_completion_exact_once", fake_gateway)
    attempt_root = tmp_path / "failure"
    with pytest.raises(SystemExit) as exc_info:
        runner.execute_attempt(
            config_path=tmp_path / "config.json",
            profile_path=tmp_path / "profile.json",
            attempt_root=attempt_root,
            run_id="TEST-RUN",
            attempt_id="TEST-ATTEMPT",
        )

    assert exc_info.value.code == 1
    assert calls == 1
    failure = json.loads(
        (attempt_root / "terminal_failure.json").read_text(encoding="utf-8")
    )
    assert failure["status"] == "terminal_failed_candidate_only_no_retry"
    assert failure["retry_count"] == 0
    assert failure["candidate_selection_promoted"] is False
    assert not (attempt_root / "result.json").exists()
