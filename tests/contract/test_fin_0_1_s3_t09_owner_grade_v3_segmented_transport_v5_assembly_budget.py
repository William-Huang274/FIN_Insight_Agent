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

from apps.workbench.backend.application.bounded_agent_executor import (
    BOUNDED_DEEPSEEK_BETA_BASE_URL,
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V4_REF,
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V5_REF,
    S3_OWNER_GRADE_SEGMENTED_V5_MAX_ASSEMBLED_UTF8_BYTES,
    S3_PROVIDER_OUTPUT_CAPTURE_POLICY_REF,
    S3_SPECIALIST_V2_MAX_SERIALIZED_UTF8_BYTES,
    S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF,
    DeepSeekS3ThreeCellNodeExecutor,
    S3ThreeCellBoundedAgentAdmission,
    S3ThreeCellBoundedAgentExecutor,
)
from test_fin_0_1_s3_t09_owner_grade_semantic_actionability_zero_call_repair import (
    _input_pack,
)
from test_fin_0_1_s3_t09_owner_grade_v3_segmented_specialist_transport import (
    _SegmentedOwnerGradeFakeProvider,
)
from test_fin_0_1_s3_t09_owner_grade_v3_segmented_transport_v3_closed_context_authority_repair import (
    _production_surfaces,
)


def _canonical_size(value: dict[str, Any]) -> int:
    return len(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )


def _grow_valid_narrative_to_size(output: dict[str, Any], target: int) -> None:
    slots: list[tuple[Any, Any]] = []
    for fact in output["fact_layer"]:
        slots.extend((fact, key) for key in ("statement", "boundary"))
    slots.extend((output["explanation_layer"], index) for index in range(len(output["explanation_layer"])))
    slots.extend((output["remaining_gaps"], index) for index in range(len(output["remaining_gaps"])))
    for claim in output["judgment_layer"]:
        slots.extend((claim, key) for key in ("statement", "qualification"))
        slots.append((claim["scope"], "metric_or_mechanism"))
        slots.extend((claim["cannot_support"], index) for index in range(len(claim["cannot_support"])))
    for task in output["what_would_change"]:
        slots.extend((task["source_target"], key) for key in task["source_target"])
        slots.append((task, "metric_or_observation"))
        slots.extend((task["decision_rule"], key) for key in task["decision_rule"])
        slots.extend((task["time_window"], key) for key in task["time_window"])
        slots.extend(
            (task, key)
            for key in ("expected_claim_transition", "fallback_stop_condition")
        )

    remaining = target - _canonical_size(output)
    assert remaining > 0
    for container, key in slots:
        if remaining == 0:
            break
        value = str(container[key])
        growth = min(320 - len(value), remaining)
        container[key] = value + ("x" * growth)
        remaining -= growth
    assert remaining == 0
    assert _canonical_size(output) == target


def test_v5_is_a_distinct_bounded_assembly_contract() -> None:
    assert S3_SPECIALIST_V2_MAX_SERIALIZED_UTF8_BYTES == 6000
    assert S3_OWNER_GRADE_SEGMENTED_V5_MAX_ASSEMBLED_UTF8_BYTES == 8192
    assert S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V5_REF != (
        S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V4_REF
    )


def test_v4_rejects_exact_replay_size_while_v5_assembly_envelope_accepts_it() -> None:
    cells, specialist_outputs = _production_surfaces()
    cell = cells[0]
    output = deepcopy(specialist_outputs[str(cell["program_cell_id"])])
    _grow_valid_narrative_to_size(output, 6010)

    with pytest.raises(
        ValueError,
        match="s3_bounded_specialist_output_byte_budget_exceeded",
    ):
        S3ThreeCellBoundedAgentExecutor._validate_specialist_output(
            output,
            cell,
            output_contract_ref=S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF,
        )

    S3ThreeCellBoundedAgentExecutor._validate_specialist_output(
        output,
        cell,
        output_contract_ref=S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF,
        max_serialized_utf8_bytes=(
            S3_OWNER_GRADE_SEGMENTED_V5_MAX_ASSEMBLED_UTF8_BYTES
        ),
    )


def test_v5_inherits_v4_epistemic_and_authority_request_contracts() -> None:
    cells, specialist_outputs = _production_surfaces()
    cell = cells[0]
    specialist = specialist_outputs[str(cell["program_cell_id"])]
    first = {
        key: deepcopy(specialist[key])
        for key in (
            "program_cell_id",
            "fact_layer",
            "explanation_layer",
            "remaining_gaps",
            "terminal_class",
        )
    }
    payload = {
        "input_contract_ref": "fixture:input:v1",
        "input_digest": "fixture-input-digest",
        "cell_input": cell,
        "required_output_layers": [],
    }
    _, v4_request, _ = DeepSeekS3ThreeCellNodeExecutor._specialist_segment_request(
        node_id=f"domain_specialist:{cell['program_cell_id']}",
        segment_id="owner_grade_claim_cards",
        payload=payload,
        validated_segments={"facts_explanation_and_terminal": first},
        transport_ref=S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V4_REF,
    )
    _, v5_request, _ = DeepSeekS3ThreeCellNodeExecutor._specialist_segment_request(
        node_id=f"domain_specialist:{cell['program_cell_id']}",
        segment_id="owner_grade_claim_cards",
        payload=payload,
        validated_segments={"facts_explanation_and_terminal": first},
        transport_ref=S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V5_REF,
    )
    assert v5_request == v4_request
    assert "field_authority_contract" in v5_request
    assert "epistemic_status_contract" in v5_request


def test_v5_fake_provider_node_accepts_6010_byte_assembly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cells, specialist_outputs = _production_surfaces()
    first_cell_id = str(cells[0]["program_cell_id"])
    grown = deepcopy(specialist_outputs[first_cell_id])
    _grow_valid_narrative_to_size(grown, 6010)
    keys_by_segment = {
        "facts_explanation_and_terminal": (
            "program_cell_id",
            "fact_layer",
            "explanation_layer",
            "remaining_gaps",
            "terminal_class",
        ),
        "owner_grade_claim_cards": ("program_cell_id", "judgment_layer"),
        "actionable_what_would_change_tasks": (
            "program_cell_id",
            "what_would_change",
        ),
    }

    def replay_6010(request: dict[str, Any], output: dict[str, Any]) -> dict[str, Any]:
        if request.get("node_id") != f"domain_specialist:{first_cell_id}":
            return output
        segment_id = str(request["segment_id"])
        return {key: deepcopy(grown[key]) for key in keys_by_segment[segment_id]}

    input_pack = _input_pack(cells)
    admission = S3ThreeCellBoundedAgentAdmission(
        admission_id="fixture-s3-t09-segmented-owner-grade-transport-v5",
        output_contract_ref=S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF,
        execution_enabled=True,
        execution_mode="fixture_only_segmented_owner_grade_transport_v5",
        case_id=input_pack.case_id,
        case_version=input_pack.case_version,
        as_of=input_pack.as_of,
        input_digest=input_pack.input_digest,
        provider="deepseek",
        model="deepseek-v4-pro",
        model_ref="deepseek:deepseek-v4-pro",
        api_key_env="DEEPSEEK_API_KEY",
        base_url=BOUNDED_DEEPSEEK_BETA_BASE_URL,
        transport_ref=S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V5_REF,
        provider_output_capture_policy_ref=S3_PROVIDER_OUTPUT_CAPTURE_POLICY_REF,
        max_semantic_model_calls=12,
        max_provider_calls=12,
        max_network_calls=12,
        max_total_cost_usd=0.10,
        specialist_max_output_tokens=4200,
        lead_max_output_tokens=1200,
        writer_max_output_tokens=1400,
        verifier_max_output_tokens=1000,
    )
    fake = _SegmentedOwnerGradeFakeProvider(
        specialist_outputs,
        mutation=replay_6010,
    )
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture-not-a-real-secret")
    executor = DeepSeekS3ThreeCellNodeExecutor(chat_completion_fn=fake)
    result = executor.execute_node(
        f"domain_specialist:{first_cell_id}",
        {
            "input_contract_ref": input_pack.input_contract_ref,
            "input_digest": input_pack.input_digest,
            "cell_input": cells[0],
            "required_output_layers": [
                "fact_layer",
                "explanation_layer",
                "judgment_layer",
                "remaining_gaps",
                "what_would_change",
            ],
        },
        admission,
        run_identity={
            "research_run_id": "fixture-run-segmented-owner-grade-transport-v5",
            "attempt_id": "fixture-attempt-segmented-owner-grade-transport-v5",
        },
    )

    assert _canonical_size(dict(result["output"])) == 6010
    assert len(fake.calls) == 3
    assert len(result["provider_output_captures"]) == 3
