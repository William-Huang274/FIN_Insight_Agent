from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "contract"))

import apps.workbench.backend.application.bounded_agent_executor as executor_module
from apps.workbench.backend.application.bounded_agent_contract_policies import (
    S3_SPECIALIST_LOCAL_ASSEMBLY_CAPACITY_CONTRACT_REF,
    S4_DELL_THREE_CELL_RESEARCH_PROFILE_V2,
    S4_DELL_THREE_CELL_RESEARCH_PROFILE_V3,
    S4_DELL_THREE_CELL_RESEARCH_PROFILE_V3_REF,
    SpecialistWWCJudgmentAtomPolicy,
    bounded_research_profile_contract_payload,
    research_profile_for_ref,
    specialist_local_assembly_capacity,
)
from apps.workbench.backend.application.bounded_agent_executor import (
    BOUNDED_AGENT_ARTIFACT_TYPES,
    BoundedAgentExecutionError,
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V8_REF,
    S3SpecialistLocalAssemblyCapacityError,
    assert_specialist_validated_segment_union_capacity,
    build_s3_three_cell_bounded_agent_executor_for_admission,
    resolve_s4_case_runtime_binding_for_admission,
)
from sec_agent.s4_case_runtime import (
    assert_s4_case_runtime_research_profile_overlay,
    load_s4_case_runtime_binding,
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
    _v8_admission,
)


RUN_IDENTITY = {
    "research_run_id": "fixture-s4-t05-dell-v3-union-capacity",
    "attempt_id": "fixture-s4-t05-dell-v3-union-capacity",
}


def _canonical_size(value: Any) -> int:
    return len(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )


def _maximum_cardinality_specialists(input_pack: Any) -> dict[str, dict[str, Any]]:
    cells = {
        str(cell["program_cell_id"]): cell
        for cell in input_pack.cell_inputs
    }
    _, source_specialists = _claims_by_cell()
    specialists: dict[str, dict[str, Any]] = {}
    for cell_id, source in source_specialists.items():
        specialist = deepcopy(source)
        fact_template = deepcopy(specialist["fact_layer"][0])
        facts = []
        for ordinal in range(1, 4):
            fact = deepcopy(fact_template)
            fact.update(
                {
                    "fact_id": f"fact-{ordinal:03d}",
                    "statement": "x" * 320,
                    "boundary": "x" * 320,
                }
            )
            facts.append(fact)
        claim_template = deepcopy(specialist["judgment_layer"][0])
        claims = []
        for ordinal in range(1, 3):
            claim = deepcopy(claim_template)
            claim.update(
                {
                    "claim_id": f"claim-{ordinal:03d}",
                    "statement": "x" * 320,
                    "support_fact_ids": [f"fact-{ordinal:03d}"],
                    "qualification": "x" * 320,
                }
            )
            claim["scope"].update(
                {
                    "entity_ref": "DELL",
                    "business_scope_kind": "unknown",
                    "business_scope_ref": "unknown",
                    "period": input_pack.as_of,
                    "metric_or_mechanism": "x" * 320,
                    "attribution_level": "none",
                }
            )
            claims.append(claim)
        specialist.update(
            {
                "fact_layer": facts,
                "explanation_layer": ["x" * 320] * 3,
                "remaining_gaps": ["x" * 320] * 4,
                "judgment_layer": claims,
            }
        )
        assert str(cells[cell_id]["program_cell_id"]) == cell_id
        specialists[cell_id] = specialist
    return specialists


def _v3_full_fake(monkeypatch: pytest.MonkeyPatch):
    input_pack = _dell_input()
    specialists = _maximum_cardinality_specialists(input_pack)
    cells = {
        str(cell["program_cell_id"]): cell
        for cell in input_pack.cell_inputs
    }
    policies = {
        cell_id: SpecialistWWCJudgmentAtomPolicy.from_cell_input(
            cell_input=cells[cell_id],
            claims=specialist["judgment_layer"],
            as_of=input_pack.as_of,
        )
        for cell_id, specialist in specialists.items()
    }
    admission = _v8_admission(input_pack).model_copy(
        update={
            "admission_id": "fixture-s4-t05-dell-v3-union-capacity",
            "execution_mode": "zero_call_fake_provider_s4_dell_v3_capacity",
            "research_profile_ref": (
                S4_DELL_THREE_CELL_RESEARCH_PROFILE_V3_REF
            ),
        }
    )

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
                narrative_characters=160,
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


def test_dell_v3_resolves_closed_three_level_capacity_without_v2_drift() -> None:
    assert research_profile_for_ref(
        S4_DELL_THREE_CELL_RESEARCH_PROFILE_V3_REF
    ) == S4_DELL_THREE_CELL_RESEARCH_PROFILE_V3
    assert (
        bounded_research_profile_contract_payload(
            S4_DELL_THREE_CELL_RESEARCH_PROFILE_V2
        )["profile_ref"]
        != S4_DELL_THREE_CELL_RESEARCH_PROFILE_V3_REF
    )
    capacity = specialist_local_assembly_capacity(
        transport_ref=S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V8_REF,
        research_profile=S4_DELL_THREE_CELL_RESEARCH_PROFILE_V3,
    )
    assert capacity.contract_ref == (
        S3_SPECIALIST_LOCAL_ASSEMBLY_CAPACITY_CONTRACT_REF
    )
    assert (
        capacity.provider_raw_segment_limit_utf8_bytes,
        capacity.post_local_expansion_segment_limit_utf8_bytes,
        capacity.validated_segment_count,
        capacity.whole_union_limit_utf8_bytes,
    ) == (6000, 8192, 3, 24576)
    assert S4_DELL_THREE_CELL_RESEARCH_PROFILE_V3.segment_token_budgets == (
        S4_DELL_THREE_CELL_RESEARCH_PROFILE_V2.segment_token_budgets
    )
    assert (
        S4_DELL_THREE_CELL_RESEARCH_PROFILE_V3
        .owner_grade_lead_v2_aggregate_output_tokens
        == 18000
    )


def test_v3_admission_generates_a_deterministic_case_runtime_overlay() -> None:
    input_pack = _dell_input()
    admission = _v8_admission(input_pack).model_copy(
        update={
            "research_profile_ref": (
                S4_DELL_THREE_CELL_RESEARCH_PROFILE_V3_REF
            )
        }
    )
    base = load_s4_case_runtime_binding(ROOT, "DELL")
    effective, overlay = resolve_s4_case_runtime_binding_for_admission(
        ROOT,
        admission,
    )
    assert base.research_profile_ref.endswith(":v1")
    assert effective.research_profile_ref == (
        S4_DELL_THREE_CELL_RESEARCH_PROFILE_V3_REF
    )
    assert overlay is not None
    assert_s4_case_runtime_research_profile_overlay(
        effective,
        overlay.model_dump(mode="json"),
    )


def test_one_byte_over_union_limit_is_typed_content_free_hard_failure() -> None:
    capacity = specialist_local_assembly_capacity(
        transport_ref=S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V8_REF,
        research_profile=S4_DELL_THREE_CELL_RESEARCH_PROFILE_V3,
    )
    with pytest.raises(
        S3SpecialistLocalAssemblyCapacityError
    ) as captured:
        assert_specialist_validated_segment_union_capacity(
            capacity=capacity,
            observed_validated_segment_utf8_bytes=[8192, 8192, 8192],
            observed_whole_union_utf8_bytes=24577,
        )
    telemetry = captured.value.telemetry
    assert telemetry == {
        "contract_ref": S3_SPECIALIST_LOCAL_ASSEMBLY_CAPACITY_CONTRACT_REF,
        "segment_count": 3,
        "provider_raw_segment_limit_utf8_bytes": 6000,
        "post_local_expansion_segment_limit_utf8_bytes": 8192,
        "whole_union_limit_utf8_bytes": 24576,
        "observed_validated_segment_utf8_bytes": [8192, 8192, 8192],
        "observed_whole_union_utf8_bytes": 24577,
        "failure_phase": "validated_segment_union_assembly",
        "raw_text_persisted": False,
        "private_reasoning_persisted": False,
        "credentials_persisted": False,
        "stack_persisted": False,
        "exception_message_persisted": False,
    }


def test_maximum_cardinality_high_density_full_fake_reaches_12_calls_9_artifacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_pack, admission, executor, fake = _v3_full_fake(monkeypatch)
    result = executor.execute(
        input_pack,
        admission,
        run_identity=RUN_IDENTITY,
    )
    assert result.terminal_reason == (
        "s3_bounded_agent_three_cell_execution_succeeded"
    )
    assert len(fake.calls) == 12
    assert len(result.provider_output_captures) == 12
    assert len(result.artifacts) == 9
    assert {row.artifact_type for row in result.artifacts} == set(
        BOUNDED_AGENT_ARTIFACT_TYPES
    )
    specialist_payloads = [
        row.payload
        for row in result.artifacts
        if row.artifact_type == "ResearchArtifact"
    ]
    if specialist_payloads:
        assert min(_canonical_size(row) for row in specialist_payloads) > 8192


def test_injected_one_byte_over_failure_keeps_all_9_receipts_and_captures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_pack, admission, executor, fake = _v3_full_fake(monkeypatch)
    original = (
        executor_module.assert_specialist_validated_segment_union_capacity
    )
    calls = 0

    def inject_third_specialist_failure(
        *,
        capacity: Any,
        observed_validated_segment_utf8_bytes: Any,
        observed_whole_union_utf8_bytes: int,
    ) -> None:
        nonlocal calls
        calls += 1
        if calls == 3:
            original(
                capacity=capacity,
                observed_validated_segment_utf8_bytes=[8192, 8192, 8192],
                observed_whole_union_utf8_bytes=24577,
            )
        original(
            capacity=capacity,
            observed_validated_segment_utf8_bytes=(
                observed_validated_segment_utf8_bytes
            ),
            observed_whole_union_utf8_bytes=(
                observed_whole_union_utf8_bytes
            ),
        )

    monkeypatch.setattr(
        executor_module,
        "assert_specialist_validated_segment_union_capacity",
        inject_third_specialist_failure,
    )
    with pytest.raises(BoundedAgentExecutionError) as captured:
        executor.execute(
            input_pack,
            admission,
            run_identity=RUN_IDENTITY,
        )
    assert len(fake.calls) == 9
    observation = captured.value.failure_observation
    assert len(observation["usage_receipts"]) == 9
    assert len(captured.value.provider_output_captures) == 9
    telemetry = observation["failure_telemetry"][
        "specialist_local_assembly_capacity"
    ]
    assert telemetry["observed_whole_union_utf8_bytes"] == 24577
    assert telemetry["whole_union_limit_utf8_bytes"] == 24576
    serialized = json.dumps(observation, ensure_ascii=False)
    assert "assistant_output_text" not in serialized
    assert "fixture-not-a-real-secret" not in serialized
