from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from typing import Any, Mapping

import pytest
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "contract"))

import apps.workbench.backend.application.bounded_agent_executor as executor_module
from apps.workbench.backend.app import create_app
from apps.workbench.backend.application.bounded_agent_executor import (
    BOUNDED_AGENT_ARTIFACT_TYPES,
    BoundedAgentAdmission,
    BoundedAgentExecutionError,
    BOUNDED_AGENT_MANIFEST_ARTIFACT_TYPE,
    S3_THREE_CELL_BOUNDED_AGENT_PROFILE_REF,
    S3_THREE_CELL_BOUNDED_AGENT_WORKER_REF,
    S3_POST_PROVIDER_FAILURE_ENVELOPE_CONTRACT_REF,
    build_s3_post_provider_failure_error,
    build_s3_three_cell_bounded_agent_executor_for_admission,
)
from apps.workbench.backend.application.case_service import CaseService
from apps.workbench.backend.application.execution_service import (
    BOUNDED_AGENT_INTERNAL_WORK_UNIT_TYPE,
)
from apps.workbench.backend.application.research_runtime import (
    ExecutionProfileVersion,
    Fin01ResearchRuntime,
    ProfileArtifactResult,
    ProfileExecutionContext,
    ProfileExecutionResult,
    _S3ThreeCellBoundedAgentAdapter,
)
from sec_agent.s4_case_runtime import (
    load_s4_case_runtime_binding,
    load_s4_source_grounded_input_pack,
)
from test_fin_0_1_s3_t09_claim_fact_link_policy_zero_call_implementation import (
    _emit_claim_fact_aliases,
)
from test_fin_0_1_s4_t05_research_lead_gap_atom_deterministic_projection_zero_call_implementation import (
    _GapAtomV6FullFakeProvider,
)
from test_fin_0_1_s4_t05_specialist_wwc_judgment_atom_deterministic_assembly_zero_call_implementation import (
    _claims_by_cell,
    _dell_input,
    _policy_by_cell,
    _v8_admission,
)
from test_fin_0_1_s3_t09_provider_output_capture_persistence import (
    _accepted_case,
    _admission,
    _capture,
    _create_work_unit,
)


RUN_IDENTITY = {
    "research_run_id": "fixture-s4-t05-typed-post-provider-envelope",
    "attempt_id": "fixture-s4-t05-typed-post-provider-envelope",
}


def _full_fake_executor(monkeypatch: pytest.MonkeyPatch):
    input_pack = _dell_input()
    _, specialists = _claims_by_cell()
    policies = _policy_by_cell(input_pack, specialists)
    admission = _v8_admission(input_pack)

    def mutation(
        request: dict[str, Any],
        output: dict[str, Any],
    ) -> dict[str, Any]:
        output = _emit_claim_fact_aliases(request, output)
        segment_id = request.get("segment_id")
        if segment_id == "facts_explanation_and_terminal":
            allowed = request["fact_support_authority_contract"][
                "allowed_refs_by_support_type"
            ]["Evidence"]
            for fact in output["fact_layer"]:
                fact["support_type"] = "Evidence"
                fact["support_refs"] = [allowed[0]]
        elif segment_id == "actionable_what_would_change_tasks":
            cell_id = str(request["node_id"]).split(":", 1)[1]
            return policies[cell_id].fake_provider_output(
                atom_count=3,
                narrative_characters=32,
            )
        return output

    fake = _GapAtomV6FullFakeProvider(
        specialists,
        mutation=mutation,
    )
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture-not-a-real-secret")
    executor = build_s3_three_cell_bounded_agent_executor_for_admission(
        admission,
        chat_completion_fn=fake,
    )
    return input_pack, admission, executor, fake


def _assert_twelve_call_typed_failure(
    error: BoundedAgentExecutionError,
    *,
    phase: str,
    code: str,
) -> None:
    observation = error.failure_observation
    assert observation["contract_ref"] == (
        S3_POST_PROVIDER_FAILURE_ENVELOPE_CONTRACT_REF
    )
    assert observation["lifecycle_phase"] == phase
    assert observation["failure_code"] == code
    assert observation["failure_codes"] == [code]
    assert len(observation["usage_receipts"]) == 12
    assert observation["observed_counts"]["model_calls"] == 12
    assert observation["observed_counts"]["provider_calls"] == 12
    assert observation["observed_counts"]["network_calls"] == 12
    assert len(observation["completed_node_receipts"]) == 6
    assert len(error.provider_output_captures) == 12
    serialized = json.dumps(observation, ensure_ascii=False)
    assert "fixture-not-a-real-secret" not in serialized
    assert "Traceback" not in serialized
    assert "assistant_output_text" not in serialized
    assert observation["private_reasoning_persisted"] is False
    assert observation["raw_provider_response_persisted"] is False


class _VerifierAccountingFault:
    def __init__(self, inner: Any) -> None:
        self._inner = inner

    def execute_node(
        self,
        node_id: str,
        payload: Mapping[str, Any],
        admission: Any,
        *,
        run_identity: Mapping[str, str],
    ) -> Mapping[str, Any]:
        raw = self._inner.execute_node(
            node_id,
            payload,
            admission,
            run_identity=run_identity,
        )
        if node_id != "verifier":
            return raw
        mutated = deepcopy(raw)
        for key in ("model_calls", "provider_calls", "network_calls"):
            mutated["observed_counts"][key] = 0
        return mutated


def test_post_verifier_accounting_fault_keeps_all_receipts_and_captures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_pack, admission, executor, fake = _full_fake_executor(monkeypatch)
    executor._node_executor = _VerifierAccountingFault(
        executor._node_executor
    )

    with pytest.raises(BoundedAgentExecutionError) as captured:
        executor.execute(
            input_pack,
            admission,
            run_identity=RUN_IDENTITY,
        )

    assert len(fake.calls) == 12
    _assert_twelve_call_typed_failure(
        captured.value,
        phase="post_verifier_call_accounting",
        code="s3_bounded_post_verifier_call_accounting_failed",
    )


def test_artifact_assembly_fault_keeps_all_receipts_and_captures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_pack, admission, executor, fake = _full_fake_executor(monkeypatch)

    def injected_artifact_failure(*_: Any, **__: Any) -> None:
        raise ValueError("injected_artifact_assembly_failure")

    monkeypatch.setattr(
        executor_module,
        "BoundedAgentArtifact",
        injected_artifact_failure,
    )
    with pytest.raises(BoundedAgentExecutionError) as captured:
        executor.execute(
            input_pack,
            admission,
            run_identity=RUN_IDENTITY,
        )

    assert len(fake.calls) == 12
    _assert_twelve_call_typed_failure(
        captured.value,
        phase="execution_artifact_assembly",
        code="s3_bounded_execution_artifact_assembly_failed",
    )


def test_adapter_conversion_fault_uses_successful_executor_observation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_pack, admission, executor, fake = _full_fake_executor(monkeypatch)
    successful_output = executor.execute(
        input_pack,
        admission,
        run_identity=RUN_IDENTITY,
    )

    class _MalformedArtifactSetExecutor:
        def execute(self, *_: Any, **__: Any):
            return successful_output.model_copy(
                update={"artifacts": successful_output.artifacts[:-1]}
            )

    binding = load_s4_case_runtime_binding(ROOT, "DELL")
    source_pack = load_s4_source_grounded_input_pack(ROOT, "DELL")
    role_group_digest = "a" * 64
    context = ProfileExecutionContext.model_construct(
        case_id=input_pack.case_id,
        case_query=input_pack.query,
        work_unit_id="fixture-work-unit",
        attempt_id="fixture-attempt",
        research_run_id="fixture-run",
        causation_event_id="fixture-causation",
        execution_profile_version_ref=(
            S3_THREE_CELL_BOUNDED_AGENT_PROFILE_REF
        ),
        s3_runtime_plan=SimpleNamespace(
            decision_surface_contract_ref=(
                input_pack.decision_surface_contract_ref
            ),
            s4_evidence_role_group_mapping_digest=role_group_digest,
        ),
        s3_evidence_route_plan=None,
        s4_evidence_slot_alignment=SimpleNamespace(
            case_id=input_pack.case_id,
            decision_surface_contract_ref=(
                input_pack.decision_surface_contract_ref
            ),
            runtime_binding_digest=binding.runtime_binding_digest,
            role_group_mapping_digest=role_group_digest,
        ),
        evidence_dispatch_digest="b" * 64,
    )
    profile = ExecutionProfileVersion(
        execution_profile_id="fixture-three-cell",
        execution_profile_version=1,
        execution_profile_version_ref=(
            S3_THREE_CELL_BOUNDED_AGENT_PROFILE_REF
        ),
        work_unit_type=BOUNDED_AGENT_INTERNAL_WORK_UNIT_TYPE,
        execution_mode="fixture",
        worker_ref=S3_THREE_CELL_BOUNDED_AGENT_WORKER_REF,
        artifact_type=BOUNDED_AGENT_MANIFEST_ARTIFACT_TYPE,
        model_calls_allowed=True,
        network_calls_allowed=True,
        external_tool_calls_allowed=False,
        direct_canonical_writes_allowed=False,
    )
    adapter = _S3ThreeCellBoundedAgentAdapter(
        object(),
        profile,
        admission,
        _MalformedArtifactSetExecutor(),
        binding,
        source_pack,
    )

    with pytest.raises(BoundedAgentExecutionError) as captured:
        adapter.execute(context, object())

    assert len(fake.calls) == 12
    _assert_twelve_call_typed_failure(
        captured.value,
        phase="adapter_output_conversion",
        code="s3_bounded_adapter_output_conversion_failed",
    )


def test_success_and_remaining_post_provider_phase_envelopes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_pack, admission, executor, fake = _full_fake_executor(monkeypatch)
    result = executor.execute(
        input_pack,
        admission,
        run_identity=RUN_IDENTITY,
    )

    assert len(fake.calls) == 12
    assert len(result.provider_output_captures) == 12
    assert len(result.artifacts) == 9
    assert {row.artifact_type for row in result.artifacts} == set(
        BOUNDED_AGENT_ARTIFACT_TYPES
    )
    assert len(
        result.execution_observation["completed_node_receipts"]
    ) == 6
    assert len(result.execution_observation["usage_receipts"]) == 12

    profile_result = ProfileExecutionResult(
        execution_profile_version_ref=(
            S3_THREE_CELL_BOUNDED_AGENT_PROFILE_REF
        ),
        case_id=input_pack.case_id,
        artifact_type=result.artifacts[0].artifact_type,
        payload=dict(result.artifacts[0].payload),
        artifacts=tuple(
            ProfileArtifactResult(
                artifact_type=row.artifact_type,
                payload=dict(row.payload),
            )
            for row in result.artifacts[1:]
        ),
        trace_events=result.trace_events,
        provider_output_captures=result.provider_output_captures,
        execution_observation=result.execution_observation,
        terminal_reason=result.terminal_reason,
    )
    phases = {
        "profile_artifact_ref_binding": (
            "s3_bounded_profile_artifact_ref_binding_failed"
        ),
        "profile_result_validation": (
            "s3_bounded_profile_result_validation_failed"
        ),
        "profile_trace_recording": (
            "s3_bounded_profile_trace_recording_failed"
        ),
    }
    for phase, code in phases.items():
        injected = ValueError(f"injected_{phase}_failure")
        error = Fin01ResearchRuntime._typed_s3_post_provider_failure(
            injected,
            lifecycle_phase=phase,
            failure_code=code,
            profile_result=profile_result,
        )
        _assert_twelve_call_typed_failure(
            error,
            phase=phase,
            code=code,
        )


class _CanonicalTypedFailureProbe:
    def execute(
        self,
        input_pack: Any,
        admission: BoundedAgentAdmission,
        *,
        run_identity: Mapping[str, str],
    ) -> Any:
        usage_receipts = [
            {
                "stage": f"fixture-stage-{index}",
                "call_id": f"fixture-call-{index}",
                "provider": "deepseek",
                "model": "deepseek-v4-pro",
                "status": "ok",
                "finish_reason": "stop",
                "input_tokens": 10,
                "input_cache_hit_tokens": 0,
                "input_cache_miss_tokens": 10,
                "output_tokens": 5,
                "total_tokens": 15,
                "estimated_cost_usd": 0.00001,
                "latency_ms": 1,
                "transport_attempt_count": 1,
            }
            for index in range(1, 13)
        ]
        captures = []
        for index in range(1, 13):
            row = _capture()
            row.update(
                {
                    "capture_sequence": index,
                    "stage": f"fixture-stage-{index}",
                    "call_id": f"fixture-call-{index}",
                }
            )
            captures.append(row)
        raise BoundedAgentExecutionError(
            "profile_result_validation",
            usage_receipts=usage_receipts,
            estimated_cost_usd=0.00012,
            failure_codes=(
                "s3_bounded_profile_result_validation_failed",
            ),
            provider_output_captures=captures,
            observed_counts={
                "model_calls": 12,
                "provider_calls": 12,
                "network_calls": 12,
                "source_network_calls": 0,
                "external_tool_calls": 0,
            },
            completed_node_receipts=[
                {
                    "node_id": f"fixture-node-{index}",
                    "input_digest": f"{index:064x}",
                    "output_digest": f"{index + 10:064x}",
                    "observed_counts": {
                        "model_calls": 2,
                        "provider_calls": 2,
                        "network_calls": 2,
                    },
                    "version_bindings": {
                        "agent_definition_version_ref": "fixture:agent:v1",
                        "skill_pack_version_ref": "fixture:skill:v1",
                    },
                }
                for index in range(1, 7)
            ],
            failure_contract_ref=(
                S3_POST_PROVIDER_FAILURE_ENVELOPE_CONTRACT_REF
            ),
            lifecycle_phase="profile_result_validation",
        )


def test_canonical_failure_persists_typed_envelope_with_zero_artifact_and_retry(
    tmp_path: Path,
) -> None:
    case_service = CaseService.for_fixture_root(
        tmp_path / "typed-envelope-runtime",
        repo_root=ROOT,
    )
    app = create_app(
        tmp_path / "typed-envelope.sqlite",
        p02_case_service=case_service,
        bounded_agent_admission=_admission(),
        bounded_agent_executor=_CanonicalTypedFailureProbe(),
    )
    with TestClient(app) as client:
        case, plan = _accepted_case(
            client,
            key="typed-envelope",
        )
        response = _create_work_unit(
            client,
            case,
            plan,
            key="typed-envelope-bounded",
        )
    assert response.status_code == 202, response.text

    events = case_service._facade.store.list_events()
    failed_event = next(
        row
        for row in events
        if row.get("event_type") == "RESEARCH_RUN_FAILED"
    )
    observation = failed_event["payload"]["failure_observation"]
    assert observation["contract_ref"] == (
        S3_POST_PROVIDER_FAILURE_ENVELOPE_CONTRACT_REF
    )
    assert observation["lifecycle_phase"] == (
        "profile_result_validation"
    )
    assert len(observation["usage_receipts"]) == 12
    assert len(observation["completed_node_receipts"]) == 6
    assert len(
        failed_event["payload"]["provider_output_capture_refs"]
    ) == 12
    assert not any(
        row.get("event_type") == "RESEARCH_RUN_COMPLETED"
        for row in events
    )
    assert (
        case_service._facade.store.list_latest(
            "canonical_artifact_versions",
            case_id=case["case_id"],
        )
        == []
    )
    attempts = case_service._facade.store.list_latest(
        "canonical_attempts",
        case_id=case["case_id"],
    )
    assert len(attempts) == 1
    assert attempts[0]["state"] == "failed"
