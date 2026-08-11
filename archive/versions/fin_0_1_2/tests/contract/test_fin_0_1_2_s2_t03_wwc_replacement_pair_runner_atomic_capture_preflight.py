from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
from typing import Any, Mapping

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.fin_0_1_2_s2_paired_model_canary import (
    Fin012S2PairedCanaryError,
)
from apps.workbench.backend.application.fin_0_1_2_s2_wwc_replacement_pair_runner import (
    Fin012S2WWCReplacementPairRunnerError,
    T03_WWC_REPLACEMENT_CAPTURE_NAMESPACE,
    T03_WWC_REPLACEMENT_RUNTIME_RESOURCE_REGISTRY_REF,
    _assert_exact_call_plan,
    build_bound_replacement_pair,
    execute_exact_replacement_pair,
    run_zero_call_preflight,
)
from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore
from sec_agent.runtime_resource_registry import load_runtime_resource_registry


pytestmark = pytest.mark.fast_contract


def _fake_completion(
    mutation: Any | None = None,
) -> tuple[list[str], Any]:
    compiler, _, _ = build_bound_replacement_pair(ROOT)
    calls: list[str] = []

    def complete(call: Any) -> Mapping[str, Any]:
        calls.append(call.call_id)
        response = deepcopy(compiler.fake_provider_response(call))
        if mutation is not None:
            response = dict(mutation(call, response))
        return response

    return calls, complete


def test_preflight_rederives_only_exact_wwc_pair_without_credentials_or_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "must-never-be-read-or-returned")
    monkeypatch.setattr(
        "sec_agent.llm_gateway.chat_completion",
        lambda **_: pytest.fail("preflight_must_not_call_gateway"),
    )

    result = run_zero_call_preflight(ROOT)

    assert result["status"].startswith("pass_zero_call")
    assert result["exact_call_count"] == 2
    assert {row["family_id"] for row in result["exact_calls"]} == {
        "what_would_change_atoms"
    }
    assert {row["candidate_id"] for row in result["exact_calls"]} == {
        "flash_stable",
        "pro_preview",
    }
    assert result["fake_execution_proofs"] == {
        "happy_pair_statuses": ["pass", "pass"],
        "semantic_failure_continues_pair": True,
        "transport_failure_stops_pair": True,
        "execution_identity_reuse_fails_closed": True,
        "Fact_or_Claim_calls": 0,
    }
    assert result["credential_checked"] is False
    assert result["credential_reads"] == 0
    assert result["model_calls"] == result["provider_calls"] == 0
    assert "must-never-be-read-or-returned" not in json.dumps(result)
    assert result["budget"]["projected_worst_case_cost_usd"] < 0.015


def test_bound_pair_matches_authority_v12_and_fact_claim_are_absent() -> None:
    compiler, calls, authority = build_bound_replacement_pair(ROOT)
    expected = authority["replacement_pair_conditional_authority"]["call_plan"]

    assert compiler.binding.binding_ref.endswith(":v1.2")
    assert compiler.binding.compiled_contract_ref.endswith(":v1.2.0")
    assert [call.call_id for call in calls] == [row["call_id"] for row in expected]
    assert [call.model_visible_request_digest for call in calls] == [
        row["model_visible_request_digest"] for row in expected
    ]
    assert [call.request_equivalence_digest for call in calls] == [
        row["request_equivalence_digest"] for row in expected
    ]
    assert {call.family_id for call in calls} == {"what_would_change_atoms"}
    assert authority["replacement_pair_conditional_authority"][
        "Fact_or_Claim_rerun"
    ] is False


def test_family_pair_compiler_preserves_primary_history_and_rejects_bad_ids() -> None:
    compiler, calls, _ = build_bound_replacement_pair(ROOT)
    primary = compiler.compile_primary_calls()

    assert len(primary) == 6
    assert all("replacement" not in call.call_id for call in primary)
    assert all("replacement" in call.call_id for call in calls)
    with pytest.raises(
        Fin012S2PairedCanaryError,
        match="family_pair_call_identity_invalid",
    ):
        compiler.compile_family_pair(
            "what_would_change_atoms",
            call_ids_by_candidate={"flash_stable": "duplicate"},
        )


def test_resource_registry_binds_authority_and_mu_fixture() -> None:
    registry = load_runtime_resource_registry(
        ROOT,
        T03_WWC_REPLACEMENT_RUNTIME_RESOURCE_REGISTRY_REF,
    )

    assert len(registry.resources) == 2
    assert [row.resource_id for row in registry.resources] == sorted(
        row.resource_id for row in registry.resources
    )
    assert all((ROOT / row.repo_relative_path).is_file() for row in registry.resources)


def test_fake_pair_persists_capture_before_validation_and_terminal(
    tmp_path: Path,
) -> None:
    events: list[str] = []

    def observe(event: str, call: Any) -> None:
        events.append(f"{event}:{call.call_id}")

    calls, complete = _fake_completion()
    result = execute_exact_replacement_pair(
        runtime_root=tmp_path / "run",
        repository_root=ROOT,
        completion=complete,
        event_observer=observe,
    )

    assert result["status"] == "completed_two_terminal_results"
    assert calls == [row["call_id"] for row in result["outcomes"]]
    assert [row["status"] for row in result["outcomes"]] == ["pass", "pass"]
    assert result["observed_counts"]["Fact_or_Claim_calls"] == 0
    for index, call_id in enumerate(calls):
        assert events[index * 3 : index * 3 + 3] == [
            f"capture_persisted:{call_id}",
            f"local_validation_started:{call_id}",
            f"terminal_persisted:{call_id}",
        ]
    assert all(row["capture_object"] for row in result["outcomes"])
    assert all(row["terminal_object"] for row in result["outcomes"])


def test_semantic_failure_is_terminalized_and_second_candidate_continues(
    tmp_path: Path,
) -> None:
    seen = 0

    def mutation(call: Any, response: Mapping[str, Any]) -> Mapping[str, Any]:
        nonlocal seen
        seen += 1
        return {**response, "content": "{}"} if seen == 1 else response

    calls, complete = _fake_completion(mutation)
    result = execute_exact_replacement_pair(
        runtime_root=tmp_path / "run",
        repository_root=ROOT,
        completion=complete,
    )

    assert len(calls) == 2
    assert result["status"] == "completed_two_terminal_results"
    assert [row["status"] for row in result["outcomes"]] == ["failed", "pass"]
    assert result["outcomes"][0]["capture_object"]
    assert result["outcomes"][0]["terminal_object"]


def test_transport_failure_is_captured_then_stops_second_candidate(
    tmp_path: Path,
) -> None:
    def mutation(call: Any, response: Mapping[str, Any]) -> Mapping[str, Any]:
        return {**response, "status": "provider_error", "finish_reason": None}

    calls, complete = _fake_completion(mutation)
    result = execute_exact_replacement_pair(
        runtime_root=tmp_path / "run",
        repository_root=ROOT,
        completion=complete,
    )

    assert len(calls) == 1
    assert result["status"].startswith("stopped_fail_closed")
    assert [row["status"] for row in result["outcomes"]] == [
        "failed",
        "not_started",
    ]
    assert result["outcomes"][0]["capture_object"]


def test_capture_failure_stops_and_sanitized_result_excludes_exception_text(
    tmp_path: Path,
) -> None:
    marker = "provider-output-must-not-enter-sanitized-result"

    class FailingStore(FileCanonicalObjectStore):
        def put_json(self, payload: Any, *, namespace: str, artifact_type: str):
            if namespace == T03_WWC_REPLACEMENT_CAPTURE_NAMESPACE:
                raise OSError(marker)
            return super().put_json(
                payload, namespace=namespace, artifact_type=artifact_type
            )

    calls, complete = _fake_completion()
    result = execute_exact_replacement_pair(
        runtime_root=tmp_path / "run",
        repository_root=ROOT,
        completion=complete,
        object_store_factory=FailingStore,
    )

    assert len(calls) == 1
    assert [row["status"] for row in result["outcomes"]] == [
        "runner_failed",
        "not_started",
    ]
    assert result["outcomes"][0]["code"] == "OSError"
    assert marker not in json.dumps(result)


def test_budget_failure_preserves_capture_and_stops_second_candidate(
    tmp_path: Path,
) -> None:
    def mutation(call: Any, response: Mapping[str, Any]) -> Mapping[str, Any]:
        return {
            **response,
            "usage": {
                "input_tokens": 10001,
                "output_tokens": 1,
                "total_tokens": 10002,
            },
        }

    calls, complete = _fake_completion(mutation)
    result = execute_exact_replacement_pair(
        runtime_root=tmp_path / "run",
        repository_root=ROOT,
        completion=complete,
    )

    assert len(calls) == 1
    assert result["outcomes"][0]["status"] == "runner_failed"
    assert result["outcomes"][0]["code"] == (
        "s2_t03_wwc_replacement_runtime_budget_exceeded"
    )
    assert result["outcomes"][0]["capture_object"]
    assert [row["status"] for row in result["outcomes"][1:]] == ["not_started"]


def test_raw_provider_envelope_and_secret_are_not_persisted(tmp_path: Path) -> None:
    marker = "raw-provider-secret-marker"

    def mutation(call: Any, response: Mapping[str, Any]) -> Mapping[str, Any]:
        return {**response, "raw_response": {"authorization": marker}}

    _, complete = _fake_completion(mutation)
    result = execute_exact_replacement_pair(
        runtime_root=tmp_path / "run",
        repository_root=ROOT,
        completion=complete,
    )

    serialized = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (tmp_path / "run").rglob("*.json")
    )
    assert marker not in serialized
    assert "Authorization" not in serialized
    assert result["raw_provider_response_persisted"] is False


def test_execution_identity_cannot_be_reused(tmp_path: Path) -> None:
    _, complete = _fake_completion()
    runtime = tmp_path / "run"
    execute_exact_replacement_pair(
        runtime_root=runtime,
        repository_root=ROOT,
        completion=complete,
    )

    with pytest.raises(
        Fin012S2WWCReplacementPairRunnerError,
        match="execution_identity_already_claimed",
    ):
        execute_exact_replacement_pair(
            runtime_root=runtime,
            repository_root=ROOT,
            completion=complete,
        )


def test_live_gateway_path_requires_explicit_execution_flag(tmp_path: Path) -> None:
    with pytest.raises(
        Fin012S2WWCReplacementPairRunnerError,
        match="live_execution_not_authorized",
    ):
        execute_exact_replacement_pair(
            runtime_root=tmp_path / "run",
            repository_root=ROOT,
        )
    assert not (tmp_path / "run").exists()


def test_authority_budget_or_call_plan_drift_fails_closed() -> None:
    compiler, calls, authority = build_bound_replacement_pair(ROOT)
    changed = deepcopy(authority)
    changed["replacement_pair_conditional_authority"]["hard_budget"][
        "retry_budget"
    ] = 1

    with pytest.raises(
        Fin012S2WWCReplacementPairRunnerError,
        match="exact_call_plan_drift",
    ):
        _assert_exact_call_plan(compiler, calls, changed)
