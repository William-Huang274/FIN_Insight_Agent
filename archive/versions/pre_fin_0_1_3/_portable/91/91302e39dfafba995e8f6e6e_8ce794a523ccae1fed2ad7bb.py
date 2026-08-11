from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "contract"))

from apps.workbench.backend.application.bounded_agent_contract_policies import (
    LEGACY_S3_ARTIFACT_LINEAGE_KEYS,
    PROFILE_AWARE_ARTIFACT_LINEAGE_VALIDATION_CONTRACT_REF,
    ProfileAwareArtifactLineageError,
    compile_profile_aware_artifact_lineage_contract,
)
from apps.workbench.backend.application.bounded_agent_executor import (
    BOUNDED_AGENT_ARTIFACT_TYPES,
    BOUNDED_AGENT_MANIFEST_ARTIFACT_TYPE,
    S3_THREE_CELL_BOUNDED_AGENT_PROFILE_REF,
    S3_THREE_CELL_BOUNDED_AGENT_WORKER_REF,
    build_s3_three_cell_bounded_agent_executor_for_admission,
    build_s4_source_grounded_bounded_agent_input,
    resolve_s4_case_runtime_binding_for_admission,
)
from apps.workbench.backend.application.execution_service import (
    BOUNDED_AGENT_INTERNAL_WORK_UNIT_TYPE,
)
from apps.workbench.backend.application.research_runtime import (
    ExecutionProfileVersion,
    Fin01ResearchRuntime,
    _S3ThreeCellBoundedAgentAdapter,
)
from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.s4_case_runtime import (
    load_s4_case_runtime_binding,
    load_s4_source_grounded_input_pack,
)
from test_fin_0_1_s4_t05_dell_r8_specialist_validated_segment_union_capacity_zero_call_implementation import (
    _v3_full_fake,
)


IMPLEMENTATION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_r9_profile_aware_"
    "artifact_lineage_validation_and_typed_subtype_minimum_zero_call_"
    "implementation_v1_0.json"
)


def _legacy_lineage() -> dict[str, dict[str, str]]:
    return {
        key: {
            "version_ref": f"fixture:{key}:v1",
            "digest": canonical_digest({"fixture": key}),
        }
        for key in LEGACY_S3_ARTIFACT_LINEAGE_KEYS
    }


def _real_s4_full_fake(monkeypatch: pytest.MonkeyPatch):
    stripped, admission, _, fake = _v3_full_fake(monkeypatch)
    binding, overlay = resolve_s4_case_runtime_binding_for_admission(
        ROOT, admission
    )
    assert overlay is not None
    source_pack = load_s4_source_grounded_input_pack(ROOT, "DELL")
    input_pack = build_s4_source_grounded_bounded_agent_input(
        binding,
        source_pack,
        case_id=stripped.case_id,
        case_version=stripped.case_version,
        decision_surface_contract_ref=(
            stripped.decision_surface_contract_ref
        ),
        query=stripped.query,
        research_profile_overlay=overlay,
    )
    admission = admission.model_copy(
        update={"input_digest": input_pack.input_digest}
    )
    executor = build_s3_three_cell_bounded_agent_executor_for_admission(
        admission,
        chat_completion_fn=fake,
    )
    profile = ExecutionProfileVersion(
        execution_profile_id="fixture-three-cell-profile-aware-lineage",
        execution_profile_version=1,
        execution_profile_version_ref=(
            S3_THREE_CELL_BOUNDED_AGENT_PROFILE_REF
        ),
        work_unit_type=BOUNDED_AGENT_INTERNAL_WORK_UNIT_TYPE,
        execution_mode="zero_call_fake_provider",
        worker_ref=S3_THREE_CELL_BOUNDED_AGENT_WORKER_REF,
        artifact_type=BOUNDED_AGENT_MANIFEST_ARTIFACT_TYPE,
        model_calls_allowed=True,
        network_calls_allowed=True,
        external_tool_calls_allowed=False,
        direct_canonical_writes_allowed=False,
    )
    role_group_digest = "a" * 64
    context = SimpleNamespace(
        case_id=input_pack.case_id,
        case_query=input_pack.query,
        work_unit_id="fixture-profile-aware-lineage-work-unit",
        attempt_id="fixture-profile-aware-lineage-attempt",
        research_run_id="fixture-profile-aware-lineage-run",
        causation_event_id="fixture-profile-aware-lineage-causation",
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
    adapter = _S3ThreeCellBoundedAgentAdapter(
        object(),
        profile,
        admission,
        executor,
        binding,
        source_pack,
        overlay,
    )
    result = adapter.execute(context, object())
    runtime = object.__new__(Fin01ResearchRuntime)
    bound = runtime._bind_profile_artifact_refs(
        result,
        research_run_id=context.research_run_id,
    )
    return input_pack, profile, runtime, bound, fake


def test_contract_dispatches_legacy_s3_s4_base_and_overlay_families() -> None:
    legacy = compile_profile_aware_artifact_lineage_contract(
        _legacy_lineage(),
        s4_case_runtime=None,
    )
    assert legacy.lineage_family == "legacy_s3"
    assert legacy.contract_ref == (
        PROFILE_AWARE_ARTIFACT_LINEAGE_VALIDATION_CONTRACT_REF
    )

    base = load_s4_case_runtime_binding(ROOT, "DELL")
    source = load_s4_source_grounded_input_pack(ROOT, "DELL")
    base_input = build_s4_source_grounded_bounded_agent_input(
        base,
        source,
        case_id="fixture-profile-aware-lineage-base",
        case_version=1,
        decision_surface_contract_ref="fixture:surface:base:v1",
        query="Validate S4 base lineage.",
    )
    base_contract = compile_profile_aware_artifact_lineage_contract(
        base_input.lineage,
        s4_case_runtime=base_input.s4_case_runtime,
    )
    assert base_contract.lineage_family == "s4_base"
    assert len(base_input.lineage) == 4

    admission = json.loads(
        (
            ROOT
            / "configs/releases/fin_ia_0_1_s4_t05_dell_r9_"
            "specialist_validated_segment_union_capacity_fresh_exact_"
            "admission_r9.json"
        ).read_text(encoding="utf-8")
    )
    from apps.workbench.backend.application.bounded_agent_executor import (
        S3ThreeCellBoundedAgentAdmission,
    )

    parsed = S3ThreeCellBoundedAgentAdmission.model_validate(admission)
    for profile_ref in (
        "fin01.s4.research_profile.dell_oem_three_cell:v2",
        "fin01.s4.research_profile.dell_oem_three_cell:v3",
    ):
        binding, overlay = resolve_s4_case_runtime_binding_for_admission(
            ROOT,
            parsed.model_copy(
                update={"research_profile_ref": profile_ref}
            ),
        )
        assert overlay is not None
        built = build_s4_source_grounded_bounded_agent_input(
            binding,
            source,
            case_id=f"fixture-{profile_ref.rsplit(':', 1)[-1]}",
            case_version=1,
            decision_surface_contract_ref="fixture:surface:overlay:v1",
            query="Validate S4 overlay lineage.",
            research_profile_overlay=overlay,
        )
        contract = compile_profile_aware_artifact_lineage_contract(
            built.lineage,
            s4_case_runtime=built.s4_case_runtime,
        )
        assert contract.lineage_family == (
            "s4_research_profile_overlay"
        )
        assert len(built.lineage) == 5


@pytest.mark.parametrize(
    ("mutation", "subtype"),
    (
        (
            lambda pack: pack["lineage"].pop(
                "S4_T04_source_grounded_input"
            ),
            "bounded_agent_profile_lineage_contract_mismatch",
        ),
        (
            lambda pack: pack["lineage"].update(
                {
                    "unexpected": {
                        "version_ref": "fixture:unexpected:v1",
                        "digest": "0" * 64,
                    }
                }
            ),
            "bounded_agent_profile_lineage_contract_mismatch",
        ),
        (
            lambda pack: pack["lineage"]["S4_T03_runtime_binding"].update(
                {"digest": "0" * 64}
            ),
            "bounded_agent_profile_lineage_digest_mismatch",
        ),
        (
            lambda pack: pack["runtime"][
                "research_profile_overlay"
            ].update({"overlay_digest": "0" * 64}),
            "bounded_agent_profile_lineage_overlay_mismatch",
        ),
    ),
)
def test_wrong_shape_digest_and_overlay_fail_with_safe_typed_subtype(
    mutation: Any,
    subtype: str,
) -> None:
    admission_path = ROOT / (
        "configs/releases/fin_ia_0_1_s4_t05_dell_r9_"
        "specialist_validated_segment_union_capacity_fresh_exact_"
        "admission_r9.json"
    )
    from apps.workbench.backend.application.bounded_agent_executor import (
        S3ThreeCellBoundedAgentAdmission,
    )

    admission = S3ThreeCellBoundedAgentAdmission.model_validate(
        json.loads(admission_path.read_text(encoding="utf-8"))
    )
    binding, overlay = resolve_s4_case_runtime_binding_for_admission(
        ROOT, admission
    )
    built = build_s4_source_grounded_bounded_agent_input(
        binding,
        load_s4_source_grounded_input_pack(ROOT, "DELL"),
        case_id="fixture-negative-profile-aware-lineage",
        case_version=1,
        decision_surface_contract_ref="fixture:surface:negative:v1",
        query="Validate negative lineage paths.",
        research_profile_overlay=overlay,
    )
    candidate = {
        "lineage": deepcopy(built.lineage),
        "runtime": deepcopy(built.s4_case_runtime),
    }
    mutation(candidate)
    with pytest.raises(ProfileAwareArtifactLineageError) as captured:
        compile_profile_aware_artifact_lineage_contract(
            candidate["lineage"],
            s4_case_runtime=candidate["runtime"],
        )
    assert captured.value.telemetry["validation_subtype"] == subtype
    serialized = json.dumps(
        captured.value.telemetry, ensure_ascii=False
    )
    assert set(captured.value.telemetry) == {
        "validation_contract_ref",
        "validation_subtype",
        "artifact_type",
        "lineage_family",
        "raw_output_persisted",
        "private_reasoning_persisted",
        "credential_persisted",
        "stack_persisted",
    }
    assert "provider" not in serialized.lower()
    assert "traceback" not in serialized.lower()


def test_full_fake_s4_chain_reaches_adapter_binding_validation_and_9_artifacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_pack, profile, runtime, result, fake = _real_s4_full_fake(
        monkeypatch
    )
    runtime._validate_profile_result(
        profile,
        result,
        case_id=input_pack.case_id,
    )
    assert len(fake.calls) == 12
    assert len(result.provider_output_captures) == 12
    assert len(result.execution_observation["usage_receipts"]) == 12
    assert len(
        result.execution_observation["completed_node_receipts"]
    ) == 6
    assert len((result.payload, *result.artifacts)) == 9
    assert result.payload["lineage_contract_ref"] == (
        PROFILE_AWARE_ARTIFACT_LINEAGE_VALIDATION_CONTRACT_REF
    )
    assert result.payload["lineage_family"] == (
        "s4_research_profile_overlay"
    )


def test_post_verifier_lineage_fault_keeps_12_receipts_captures_and_safe_subtype(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_pack, profile, runtime, result, fake = _real_s4_full_fake(
        monkeypatch
    )
    artifacts = list(result.artifacts)
    trace_index = next(
        index
        for index, row in enumerate(artifacts)
        if row.artifact_type == "bounded_agent_trace"
    )
    tampered_trace = artifacts[trace_index].model_copy(
        update={
            "payload": {
                **artifacts[trace_index].payload,
                "lineage": {
                    **artifacts[trace_index].payload["lineage"],
                    "S4_T03_runtime_binding": {
                        **artifacts[trace_index].payload["lineage"][
                            "S4_T03_runtime_binding"
                        ],
                        "digest": "0" * 64,
                    },
                },
            }
        }
    )
    artifacts[trace_index] = tampered_trace
    tampered = result.model_copy(update={"artifacts": tuple(artifacts)})
    with pytest.raises(ProfileAwareArtifactLineageError) as captured:
        runtime._validate_profile_result(
            profile,
            tampered,
            case_id=input_pack.case_id,
        )
    error = runtime._typed_s3_post_provider_failure(
        captured.value,
        lifecycle_phase="profile_result_validation",
        failure_code="s3_bounded_profile_result_validation_failed",
        profile_result=tampered,
    )
    observation = error.failure_observation
    telemetry = observation["failure_telemetry"][
        "profile_artifact_lineage"
    ]
    assert telemetry["validation_subtype"] == (
        "bounded_agent_profile_lineage_digest_mismatch"
    )
    assert len(fake.calls) == 12
    assert len(observation["usage_receipts"]) == 12
    assert len(error.provider_output_captures) == 12
    assert len(observation["completed_node_receipts"]) == 6
    assert len(tampered.artifacts) == 8
    serialized = json.dumps(observation, ensure_ascii=False)
    assert "fixture-not-a-real-secret" not in serialized
    assert "Traceback" not in serialized


def test_implementation_record_closes_only_zero_call_scope() -> None:
    record = json.loads(IMPLEMENTATION.read_text(encoding="utf-8"))
    assert record["contract_ref"] == (
        PROFILE_AWARE_ARTIFACT_LINEAGE_VALIDATION_CONTRACT_REF
    )
    assert record["observed_counts"] == {
        "model_calls": 0,
        "provider_calls": 0,
        "execution_network_calls": 0,
        "source_network_calls": 0,
        "external_tool_calls": 0,
        "canonical_business_writes": 0,
    }
    assert record["stage_acceptance"]["DELL_R2"] == "not_proven"
    assert record["stage_acceptance"]["S4_T06"] == "not_entered"
