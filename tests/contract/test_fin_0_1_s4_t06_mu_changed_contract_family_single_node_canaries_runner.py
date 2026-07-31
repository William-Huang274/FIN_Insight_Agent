from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
from typing import Any, Mapping

import pytest


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / (
    "scripts/releases/"
    "run_fin_ia_0_1_s4_t06_mu_changed_contract_family_"
    "single_node_natural_output_canaries.py"
)


def _load_runner():
    spec = importlib.util.spec_from_file_location(
        "fin01_s4_t06_mu_changed_family_canary_runner",
        RUNNER,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _fake_provider(
    *,
    fail_family: str | None = None,
):
    calls: list[str] = []

    def completion(**kwargs: Any) -> Mapping[str, Any]:
        request = json.loads(kwargs["messages"][1]["content"])
        contract = request["compiled_judgment_atom_contract"]
        family = contract["family_id"]
        calls.append(family)
        if family == fail_family:
            output = {
                "program_cell_id": contract["program_cell_id"],
                "unexpected": [],
            }
        elif family == "specialist_fact_atoms":
            output = {
                "program_cell_id": contract["program_cell_id"],
                "fact_atoms": [
                    {
                        "support_alias": contract["allowed_supports"][0][
                            "support_alias"
                        ],
                        "causal_relation": "supports",
                        "materiality": "high",
                        "confidence": "high",
                        "priority": "high",
                    }
                ],
                "terminal_class": "supported",
            }
        elif family == "claim_candidate_atoms":
            output = {
                "program_cell_id": contract["program_cell_id"],
                "claim_candidate_atoms": [
                    {
                        "support_fact_aliases": [
                            contract["allowed_facts"][0]["fact_alias"]
                        ],
                        "claim_kind": "economic_mechanism",
                        "direction": "supports",
                        "materiality": "high",
                        "confidence": "high",
                        "priority": "high",
                    }
                ],
            }
        else:
            claim = contract["allowed_claims"][0]["claim_alias"]
            authority = contract["allowed_authorities"][0][
                "authority_alias"
            ]
            output = {
                "program_cell_id": contract["program_cell_id"],
                "what_would_change_atoms": [
                    {
                        "claim_alias": claim,
                        "primary_authority_alias": authority,
                        "authority_aliases": [authority],
                        "trigger_code": "authority_confirmation",
                        "direction": "supports",
                        "review_cadence": "next_authority_event",
                        "start_date_alias": "NONE",
                        "review_date_alias": "NONE",
                        "expected_claim_transition": "strengthen",
                    }
                ],
            }
        return {
            "status": "ok",
            "finish_reason": "stop",
            "content": json.dumps(
                output,
                ensure_ascii=False,
                sort_keys=True,
            ),
            "input_tokens": 100,
            "output_tokens": 50,
            "total_tokens": 150,
            "call_id": f"fixture-{family}",
            "provider": "deepseek",
            "model": "deepseek-v4-pro",
            "latency_ms": 1,
            "transport_attempt_count": 1,
            "raw_response": {
                "usage": {
                    "prompt_cache_hit_tokens": 0,
                    "prompt_cache_miss_tokens": 100,
                }
            },
        }

    return calls, completion


def test_zero_call_preflight_recomputes_exact_templates(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runner = _load_runner()
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture-not-a-secret")
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    result = runner.preflight(
        result_path=tmp_path / "result.json",
        state_path=tmp_path / "state.json",
        capture_root=tmp_path / "captures",
    )
    assert result["status"] == "pass_exact_zero_call_execution_preflight"
    assert result["execution_order"] == [
        "specialist_fact_atoms",
        "claim_candidate_atoms",
        "what_would_change_atoms",
    ]
    assert result["projected_worst_case_cost_usd"] < 0.03


def test_fake_three_family_execution_is_isolated_and_capture_first(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runner = _load_runner()
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture-not-a-secret")
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    calls, completion = _fake_provider()
    monkeypatch.setattr(runner, "_provider_chat_completion", completion)
    result = runner.execute(
        result_path=tmp_path / "result.json",
        state_path=tmp_path / "state.json",
        capture_root=tmp_path / "captures",
    )
    assert result["status"] == "terminal_succeeded_exact_once"
    assert calls == result["execution_order"]
    assert result["totals"]["model_calls"] == 3
    assert len(list((tmp_path / "captures").glob("*.json"))) == 3
    assert all(
        row["capture_persisted_before_local_validation"]
        and row["capture_policy_ref"]
        == "fin01.runtime.provider_interaction_audit_capture:v2"
        and row["validation"]["compiled_wire_pass"]
        and row["validation"]["local_deterministic_assembly_pass"]
        for row in result["family_results"]
    )
    assert result["canonical_work_unit_attempt_run_or_artifact_writes"] == 0


def test_first_failure_stops_remaining_families_without_retry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runner = _load_runner()
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture-not-a-secret")
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    calls, completion = _fake_provider(
        fail_family="claim_candidate_atoms"
    )
    monkeypatch.setattr(runner, "_provider_chat_completion", completion)
    result = runner.execute(
        result_path=tmp_path / "result.json",
        state_path=tmp_path / "state.json",
        capture_root=tmp_path / "captures",
    )
    assert result["status"] == "terminal_failed_no_retry"
    assert calls == [
        "specialist_fact_atoms",
        "claim_candidate_atoms",
    ]
    assert result["skipped_after_first_failure"] == [
        "what_would_change_atoms"
    ]
    assert result["totals"]["model_calls"] == 2
    assert len(list((tmp_path / "captures").glob("*.json"))) == 2
    assert result["budget"][
        "retry_fallback_replay_provider_hopping"
    ] == [0, 0, 0, 0]
