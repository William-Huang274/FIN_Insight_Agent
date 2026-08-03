from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.fin_0_1_2_s2_paired_model_canary import (
    Fin012S2PairedModelCanaryCompiler,
)
from apps.workbench.backend.application.fin_0_1_2_s2_paired_model_canary_runner import (
    Fin012S2PairedCanaryRunnerError,
    T03_CAPTURE_NAMESPACE,
    build_bound_compiler,
    execute_exact_six_call_canary,
    run_zero_call_preflight,
)
from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore


pytestmark = pytest.mark.fast_contract

T03_RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_2_s2_t03_paired_canary_bound_runner_"
    "atomic_capture_and_zero_call_preflight_minimum_implementation_v1_0.json"
)
CURRENT_PROJECTION = ROOT / (
    "configs/runtime/fin_ia_0_1_2_current_program_projection_v2_12.json"
)
PROGRAM_BACKLOG = ROOT / (
    "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
)


def _fake_completion(
    mutation: Any | None = None,
) -> tuple[list[str], Any]:
    compiler, _ = build_bound_compiler(ROOT)
    calls: list[str] = []

    def complete(call: Any) -> Mapping[str, Any]:
        calls.append(call.call_id)
        response = deepcopy(compiler.fake_provider_response(call))
        if mutation is not None:
            response = dict(mutation(call, response))
        return response

    return calls, complete


def _mutate_json_content(
    response: Mapping[str, Any], mutation: Any
) -> dict[str, Any]:
    changed = deepcopy(dict(response))
    content = json.loads(changed["content"])
    mutation(content)
    changed["content"] = json.dumps(
        content,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return changed


def test_preflight_rederives_exact_authority_without_credentials_or_calls(
    monkeypatch,
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "must-never-be-read-or-returned")
    monkeypatch.setattr(
        "sec_agent.llm_gateway.chat_completion",
        lambda **_: pytest.fail("preflight_must_not_call_gateway"),
    )

    result = run_zero_call_preflight(ROOT)

    assert result["status"].startswith("pass_zero_call")
    assert result["exact_call_count"] == 6
    assert result["credential_checked"] is False
    assert result["credential_reads"] == 0
    assert result["model_calls"] == result["provider_calls"] == 0
    assert "must-never-be-read-or-returned" not in json.dumps(result)
    assert result["budget"]["projected_worst_case_primary_cost_usd"] < 0.06


def test_bound_compiler_uses_production_fixture_and_matches_all_six_digests() -> None:
    compiler, authority = build_bound_compiler(ROOT)
    calls = compiler.compile_primary_calls()
    expected = authority["exact_canary"]["call_plan"]

    assert compiler.program_cell_id == "demand_authenticity_and_sustainability"
    assert [call.call_id for call in calls] == [row["call_id"] for row in expected]
    assert [call.model_visible_request_digest for call in calls] == [
        row["model_visible_request_digest"] for row in expected
    ]
    assert [call.request_equivalence_digest for call in calls] == [
        row["request_equivalence_digest"] for row in expected
    ]


def test_fake_six_call_execution_persists_capture_before_validation(
    tmp_path: Path, monkeypatch
) -> None:
    events: list[str] = []
    original = Fin012S2PairedModelCanaryCompiler.materialize_response

    class RecordingStore(FileCanonicalObjectStore):
        def put_json(self, payload: Any, *, namespace: str, artifact_type: str):
            if namespace == T03_CAPTURE_NAMESPACE:
                events.append(f"capture:{payload['call_id']}")
            return super().put_json(
                payload, namespace=namespace, artifact_type=artifact_type
            )

    def wrapped_materialize(self: Any, call: Any, response: Any):
        events.append(f"validate:{call.call_id}")
        return original(self, call, response)

    monkeypatch.setattr(
        Fin012S2PairedModelCanaryCompiler,
        "materialize_response",
        wrapped_materialize,
    )
    calls, complete = _fake_completion()
    result = execute_exact_six_call_canary(
        runtime_root=tmp_path / "run",
        repository_root=ROOT,
        completion=complete,
        object_store_factory=RecordingStore,
    )

    assert result["status"] == "completed_six_terminal_results"
    assert calls == [row["call_id"] for row in result["outcomes"]]
    assert [row["status"] for row in result["outcomes"]] == ["pass"] * 6
    assert len(events) == 12
    for index, call_id in enumerate(calls):
        assert events[index * 2 : index * 2 + 2] == [
            f"capture:{call_id}",
            f"validate:{call_id}",
        ]
    assert all(row["capture_object"] for row in result["outcomes"])
    assert all(row["terminal_object"] for row in result["outcomes"])


def test_semantic_failure_is_recorded_and_remaining_five_calls_continue(
    tmp_path: Path,
) -> None:
    def mutation(call: Any, response: dict[str, Any]) -> Mapping[str, Any]:
        if call.call_id.endswith("specialist_fact_atoms-flash_stable-r1"):
            return _mutate_json_content(
                response,
                lambda output: output["fact_atoms"][0].update(
                    support_alias="UNKNOWN-ALIAS"
                ),
            )
        return response

    calls, complete = _fake_completion(mutation)
    result = execute_exact_six_call_canary(
        runtime_root=tmp_path / "run",
        repository_root=ROOT,
        completion=complete,
    )

    assert len(calls) == 6
    assert result["status"] == "completed_six_terminal_results"
    assert result["outcomes"][0]["status"] == "failed"
    assert "fact_atom_alias_unknown_or_duplicate" in result["outcomes"][0][
        "code"
    ]
    assert [row["status"] for row in result["outcomes"][1:]] == ["pass"] * 5


def test_transport_failure_is_captured_then_stops_remaining_five_calls(
    tmp_path: Path,
) -> None:
    def mutation(call: Any, response: dict[str, Any]) -> Mapping[str, Any]:
        if call.call_id.endswith("specialist_fact_atoms-flash_stable-r1"):
            return {**response, "status": "provider_error", "finish_reason": None}
        return response

    calls, complete = _fake_completion(mutation)
    result = execute_exact_six_call_canary(
        runtime_root=tmp_path / "run",
        repository_root=ROOT,
        completion=complete,
    )

    assert len(calls) == 1
    assert result["status"].startswith("stopped_fail_closed")
    assert result["outcomes"][0]["status"] == "failed"
    assert result["outcomes"][0]["capture_object"]
    assert [row["status"] for row in result["outcomes"][1:]] == [
        "not_started"
    ] * 5


def test_capture_failure_stops_and_sanitized_result_contains_no_output(
    tmp_path: Path,
) -> None:
    secret_output = "provider-output-must-not-enter-sanitized-result"

    class FailingStore(FileCanonicalObjectStore):
        def put_json(self, payload: Any, *, namespace: str, artifact_type: str):
            raise OSError(secret_output)

    calls, complete = _fake_completion()
    result = execute_exact_six_call_canary(
        runtime_root=tmp_path / "run",
        repository_root=ROOT,
        completion=complete,
        object_store_factory=FailingStore,
    )

    assert len(calls) == 1
    assert result["outcomes"][0]["status"] == "runner_failed"
    assert result["outcomes"][0]["code"] == "OSError"
    assert [row["status"] for row in result["outcomes"][1:]] == [
        "not_started"
    ] * 5
    assert secret_output not in json.dumps(result)


def test_raw_provider_envelope_and_secret_are_never_persisted(tmp_path: Path) -> None:
    marker = "raw-provider-secret-marker"

    def mutation(call: Any, response: dict[str, Any]) -> Mapping[str, Any]:
        return {**response, "raw_response": {"secret": marker}}

    _, complete = _fake_completion(mutation)
    result = execute_exact_six_call_canary(
        runtime_root=tmp_path / "run",
        repository_root=ROOT,
        completion=complete,
    )

    serialized = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (tmp_path / "run").rglob("*.json")
    )
    assert marker not in serialized
    assert result["raw_provider_response_persisted"] is False
    assert "Authorization" not in serialized


def test_output_budget_failure_stops_after_capture_without_terminal_promotion(
    tmp_path: Path,
) -> None:
    def mutation(call: Any, response: dict[str, Any]) -> Mapping[str, Any]:
        return {
            **response,
            "usage": {
                "input_tokens": 10,
                "output_tokens": 1401,
                "total_tokens": 1411,
            },
        }

    calls, complete = _fake_completion(mutation)
    result = execute_exact_six_call_canary(
        runtime_root=tmp_path / "run",
        repository_root=ROOT,
        completion=complete,
    )

    assert len(calls) == 1
    assert result["outcomes"][0]["status"] == "runner_failed"
    assert result["outcomes"][0]["code"] == "s2_t03_runtime_budget_exceeded"
    assert result["outcomes"][0]["capture_object"]
    assert result["outcomes"][0]["terminal_object"]
    assert [row["status"] for row in result["outcomes"][1:]] == [
        "not_started"
    ] * 5


def test_execution_identity_cannot_be_reused(tmp_path: Path) -> None:
    calls, complete = _fake_completion()
    runtime = tmp_path / "run"
    execute_exact_six_call_canary(
        runtime_root=runtime,
        repository_root=ROOT,
        completion=complete,
    )

    with pytest.raises(
        Fin012S2PairedCanaryRunnerError,
        match="execution_identity_already_claimed",
    ):
        execute_exact_six_call_canary(
            runtime_root=runtime,
            repository_root=ROOT,
            completion=complete,
        )


def test_T03_result_binds_implementation_and_preserves_zero_calls() -> None:
    result = json.loads(T03_RESULT.read_text(encoding="utf-8"))

    assert result["status"].startswith("pass_engineering_and_zero_call")
    for row in result["implementation_bindings"]:
        path = ROOT / row["ref"]
        assert path.stat().st_size == row["bytes"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"]
    assert result["verification"]["focused_runner_gateway_object_store_tests"][
        "failed"
    ] == 0
    assert result["zero_call_preflight"]["credential_reads"] == 0
    assert result["zero_call_preflight"]["model_calls"] == 0
    assert result["stage_acceptance"]["S2_T03_execution"] == (
        "authorized_not_started"
    )


def test_preflight_projection_remains_historical_after_exact_execution() -> None:
    result = json.loads(T03_RESULT.read_text(encoding="utf-8"))
    projection = json.loads(CURRENT_PROJECTION.read_text(encoding="utf-8"))
    backlog = json.loads(PROGRAM_BACKLOG.read_text(encoding="utf-8"))

    result_ref = T03_RESULT.relative_to(ROOT).as_posix()
    result_sha = hashlib.sha256(T03_RESULT.read_bytes()).hexdigest()
    assert projection["implementation_binding"] == {
        "ref": result_ref,
        "sha256": result_sha,
        "binding_role": (
            "S2_T03_bound_runner_atomic_capture_and_zero_call_preflight_pass"
        ),
    }
    assert projection["current_truth"]["current_next_action"] == result[
        "next_action"
    ]
    assert projection["execution_authority"]["exact_execution_started"] is False
    assert projection["execution_authority"][
        "automatic_retry_fallback_provider_hopping_or_replacement_authorized"
    ] is False
    current = backlog["next_action"]
    assert current["item_id"] != result["next_action"]
    assert current["current_projection_ref"].endswith("v2_13.json")
    assert current["S2_T03_preflight_implementation_ref"] == result_ref
    assert current["S2_T03_preflight_implementation_sha256"] == result_sha
    assert current["S2_T03_execution_started"] is True
    assert current["S2_T03_current_model_provider_network_calls"] == [6, 6, 6]
