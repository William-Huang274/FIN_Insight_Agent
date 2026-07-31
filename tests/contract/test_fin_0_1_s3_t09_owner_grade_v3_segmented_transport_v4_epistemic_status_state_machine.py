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
sys.path.insert(0, str(ROOT / "tests" / "contract"))

from apps.workbench.backend.application.bounded_agent_executor import (
    BOUNDED_AGENT_ARTIFACT_TYPES,
    BOUNDED_DEEPSEEK_BETA_BASE_URL,
    BoundedAgentExecutionError,
    DeepSeekS3ThreeCellNodeExecutor,
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V3_REF,
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V4_REF,
    S3_PROVIDER_OUTPUT_CAPTURE_POLICY_REF,
    S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF,
    S3ThreeCellBoundedAgentAdmission,
    build_s3_three_cell_bounded_agent_executor_for_admission,
)
from test_fin_0_1_s3_t09_owner_grade_semantic_actionability_zero_call_repair import (
    _input_pack,
)
from test_fin_0_1_s3_t09_owner_grade_v3_segmented_specialist_transport import (
    Mutation,
    _SegmentedOwnerGradeFakeProvider,
)
from test_fin_0_1_s3_t09_owner_grade_v3_segmented_transport_v3_closed_context_authority_repair import (
    _production_surfaces,
)


def _admission(input_pack: Any) -> S3ThreeCellBoundedAgentAdmission:
    return S3ThreeCellBoundedAgentAdmission(
        admission_id="fixture-s3-t09-segmented-owner-grade-transport-v4",
        output_contract_ref=S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF,
        execution_enabled=True,
        execution_mode="fixture_only_segmented_owner_grade_transport_v4",
        case_id=input_pack.case_id,
        case_version=input_pack.case_version,
        as_of=input_pack.as_of,
        input_digest=input_pack.input_digest,
        provider="deepseek",
        model="deepseek-v4-pro",
        model_ref="deepseek:deepseek-v4-pro",
        api_key_env="DEEPSEEK_API_KEY",
        base_url=BOUNDED_DEEPSEEK_BETA_BASE_URL,
        transport_ref=S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V4_REF,
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


def test_v4_execution_admission_requires_explicit_output_capture_policy_binding() -> None:
    cells, _ = _production_surfaces()
    input_pack = _input_pack(cells)
    payload = _admission(input_pack).model_dump(mode="python")
    payload.pop("provider_output_capture_policy_ref")
    implicit_default = S3ThreeCellBoundedAgentAdmission.model_validate(payload)
    with pytest.raises(
        ValueError,
        match="s3_bounded_admission_v4_output_capture_policy_explicit_binding_required",
    ):
        implicit_default.assert_profile_admissible()


def _run(
    monkeypatch: pytest.MonkeyPatch,
    *,
    mutation: Mutation | None = None,
) -> tuple[Any, _SegmentedOwnerGradeFakeProvider]:
    cells, specialists = _production_surfaces()
    input_pack = _input_pack(cells)
    admission = _admission(input_pack)
    fake = _SegmentedOwnerGradeFakeProvider(specialists, mutation=mutation)
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture-not-a-real-secret")
    executor = build_s3_three_cell_bounded_agent_executor_for_admission(
        admission, chat_completion_fn=fake
    )
    result = executor.execute(
        input_pack,
        admission,
        run_identity={
            "research_run_id": "fixture-run-segmented-owner-grade-transport-v4",
            "attempt_id": "fixture-attempt-segmented-owner-grade-transport-v4",
        },
    )
    return result, fake


def test_v4_full_production_view_exposes_closed_epistemic_status_matrix() -> None:
    cells, _ = _production_surfaces()
    cell = cells[0]
    payload = {
        "input_contract_ref": "fixture:input:v1",
        "input_digest": "fixture-input-digest",
        "cell_input": cell,
        "required_output_layers": [],
    }
    _, request, _ = DeepSeekS3ThreeCellNodeExecutor._specialist_segment_request(
        node_id=f"domain_specialist:{cell['program_cell_id']}",
        segment_id="owner_grade_claim_cards",
        payload=payload,
        validated_segments={
            "facts_explanation_and_terminal": {
                "program_cell_id": cell["program_cell_id"],
                "fact_layer": [],
                "explanation_layer": ["fixture"],
                "remaining_gaps": ["fixture"],
                "terminal_class": "fixture",
            }
        },
        transport_ref=S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V4_REF,
    )
    assert set(request["analysis_input"]["cell_input"]) == {
        "program_cell_id",
        "decision_contract",
        "specialist_authority",
        "evidence_view",
        "numeric_view",
        "graph_view",
        "authority_refs",
    }
    contract = request["epistemic_status_contract"]
    assert set(contract["status_rules"]) == {
        "fact_supported",
        "bounded_inference",
        "hypothesis",
        "cannot_infer",
    }
    assert contract["status_rules"]["cannot_infer"] == {
        "support_fact_ids": "exactly_empty_array",
        "qualification": "string_may_be_empty",
        "cannot_support": "one_or_more_nonblank_boundaries",
    }
    assert contract["forbidden_repairs"] == [
        "silently_change_epistemic_status",
        "silently_drop_support_fact_ids",
        "silently_add_cannot_support_boundary",
        "coerce_or_rewrite_field_values",
    ]


@pytest.mark.parametrize(
    ("status", "support_fact_ids", "qualification", "cannot_support"),
    [
        ("fact_supported", ["fact:1"], "", []),
        ("bounded_inference", ["fact:1"], "", []),
        ("hypothesis", [], "A bounded hypothesis.", []),
        ("cannot_infer", [], "", ["The available record cannot establish this."]),
    ],
)
def test_v4_all_four_epistemic_status_states_pass_strict_local_validation(
    status: str,
    support_fact_ids: list[str],
    qualification: str,
    cannot_support: list[str],
) -> None:
    cells, specialists = _production_surfaces()
    cell = cells[0]
    specialist = specialists[str(cell["program_cell_id"])]
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
    claim = deepcopy(specialist["judgment_layer"][0])
    claim["epistemic_status"] = status
    claim["support_fact_ids"] = support_fact_ids
    claim["qualification"] = qualification
    claim["cannot_support"] = cannot_support
    DeepSeekS3ThreeCellNodeExecutor._validate_specialist_segment(
        segment_id="owner_grade_claim_cards",
        output={
            "program_cell_id": cell["program_cell_id"],
            "judgment_layer": [claim],
        },
        cell_input=cell,
        validated_segments={"facts_explanation_and_terminal": first},
        transport_ref=S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V4_REF,
    )


def test_v4_positive_fixture_preserves_six_nodes_nine_artifacts_and_twelve_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, fake = _run(monkeypatch)
    assert result.trace_events[-1]["event_payload"]["node_count"] == 6
    assert tuple(row.artifact_type for row in result.artifacts) == (
        BOUNDED_AGENT_ARTIFACT_TYPES
    )
    assert len(result.artifacts) == 9
    assert len(fake.calls) == 12
    assert len(result.provider_output_captures) == 12


def _cannot_infer_conflict_mutation(
    *, has_support: bool, missing_boundary: bool
) -> Mutation:
    def mutate(request: dict[str, Any], output: dict[str, Any]) -> dict[str, Any]:
        if (
            request.get("node_id")
            == "domain_specialist:demand_authenticity_and_sustainability"
            and request.get("segment_id") == "owner_grade_claim_cards"
        ):
            claim = output["judgment_layer"][0]
            claim["statement"] = "provider-private-claim-text"
            claim["epistemic_status"] = "cannot_infer"
            claim["support_fact_ids"] = ["fact:1"] if has_support else []
            claim["cannot_support"] = (
                [] if missing_boundary else ["provider-private-boundary-text"]
            )
        return output

    return mutate


@pytest.mark.parametrize(
    ("has_support", "missing_boundary", "expected_subtype"),
    [
        (True, False, "cannot_infer_has_support_fact_ids"),
        (False, True, "cannot_infer_missing_cannot_support"),
        (True, True, "cannot_infer_has_support_and_missing_boundary"),
    ],
)
def test_v4_cannot_infer_conflicts_stop_at_claim_segment_with_closed_telemetry(
    monkeypatch: pytest.MonkeyPatch,
    has_support: bool,
    missing_boundary: bool,
    expected_subtype: str,
) -> None:
    with pytest.raises(BoundedAgentExecutionError) as captured:
        _run(
            monkeypatch,
            mutation=_cannot_infer_conflict_mutation(
                has_support=has_support,
                missing_boundary=missing_boundary,
            ),
        )
    observation = captured.value.failure_observation
    assert observation["observed_counts"]["model_calls"] == 2
    assert len(observation["usage_receipts"]) == 2
    assert len(captured.value.provider_output_captures) == 2
    assert observation["failure_telemetry"] == {
        "segmented_specialist_epistemic_status": {
            "validator_contract": "closed_claim_card_epistemic_status_state:v1",
            "segment_id": "owner_grade_claim_cards",
            "field_id": (
                "judgment_layer.epistemic_status_support_fact_ids_"
                "qualification_cannot_support"
            ),
            "status_subtype": expected_subtype,
            "failing_item_count": 1,
            "raw_claim_persisted": False,
            "support_fact_ids_persisted": False,
            "cannot_support_text_persisted": False,
            "item_index_persisted": False,
            "arbitrary_key_names_persisted": False,
            "private_reasoning_persisted": False,
        }
    }
    assert "provider-private-claim-text" not in json.dumps(observation)
    assert "provider-private-boundary-text" not in json.dumps(observation)
    captured_output = json.loads(
        captured.value.provider_output_captures[-1]["assistant_output_text"]
    )
    assert captured_output["judgment_layer"][0]["statement"] == (
        "provider-private-claim-text"
    )


def test_v3_request_remains_immutable_without_epistemic_status_contract() -> None:
    cells, specialists = _production_surfaces()
    cell = cells[0]
    first = {
        key: deepcopy(specialists[str(cell["program_cell_id"])][key])
        for key in (
            "program_cell_id",
            "fact_layer",
            "explanation_layer",
            "remaining_gaps",
            "terminal_class",
        )
    }
    _, request, _ = DeepSeekS3ThreeCellNodeExecutor._specialist_segment_request(
        node_id=f"domain_specialist:{cell['program_cell_id']}",
        segment_id="owner_grade_claim_cards",
        payload={
            "input_contract_ref": "fixture:input:v1",
            "input_digest": "fixture-input-digest",
            "cell_input": cell,
            "required_output_layers": [],
        },
        validated_segments={"facts_explanation_and_terminal": first},
        transport_ref=S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V3_REF,
    )
    assert "field_authority_contract" in request
    assert "epistemic_status_contract" not in request


def test_v4_zero_call_result_and_next_authority_are_frozen() -> None:
    result = json.loads(
        (
            ROOT
            / "configs/releases/fin_ia_0_1_s3_t09_owner_grade_v3_segmented_transport_v4_epistemic_status_state_machine_repair_v1_0.json"
        ).read_text(encoding="utf-8")
    )
    backlog = json.loads(
        (ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json").read_text(
            encoding="utf-8"
        )
    )
    assert result["status"] == (
        "pass_zero_call_transport_v4_epistemic_status_state_machine_fixture_proven"
    )
    assert result["implementation"]["transport_ref"] == (
        S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V4_REF
    )
    assert result["observed_counts"]["real_model_calls"] == 0
    assert result["observed_counts"]["new_Artifacts"] == 0
    assert result["next_action"] == (
        "S3-T09-OWNER-GRADE-V3-SEGMENTED-TRANSPORT-V4-FRESH-AGENT-PROOF-DECISION"
    )
    assert backlog["next_action"]["item_id"] == (
        "S3-T09-OWNER-GRADE-V3-SEGMENTED-TRANSPORT-V5-RESEARCH-LEAD-OUTPUT-TRUNCATION-RESULT-AND-ROOT-CAUSE-DECISION"
    )
    assert backlog["next_action"][
        "S3_T09_owner_grade_v3_segmented_transport_v4_fresh_agent_proof_decision_ref"
    ].endswith("transport_v4_fresh_agent_proof_decision_v1_0.json")
    assert backlog["next_action"][
        "transport_v4_epistemic_status_zero_call_implementation_authorized"
    ] is True
    assert backlog["next_action"]["agent_proof_decision_authorized"] is True
    assert backlog["next_action"]["admission_issuance_authorized"] is True
    assert backlog["next_action"]["agent_execution_authorized"] is False
    assert backlog["next_action"][
        "transport_v5_fresh_exact_live_execution_authorized"
    ] is True
    assert backlog["next_action"]["transport_v4_fresh_exact_admission_issued"] is True
    assert backlog["next_action"]["transport_v4_fresh_exact_admission_consumed"] is True
