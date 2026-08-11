from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
from typing import Any, Callable

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "contract"))

from apps.workbench.backend.application.bounded_agent_executor import (
    BOUNDED_AGENT_ARTIFACT_TYPES,
    BoundedAgentExecutionError,
    DeepSeekS3ThreeCellNodeExecutor,
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_REF,
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V2_REF,
)
from test_fin_0_1_s3_t09_owner_grade_semantic_actionability_zero_call_repair import (
    _cell_input,
    _input_pack,
)
from test_fin_0_1_s3_t09_owner_grade_v3_segmented_specialist_transport import (
    Mutation,
    _admission,
    _first_segment_mutation,
    _run,
    _surfaces,
)


def test_transport_v2_adds_field_local_limits_without_rewriting_v1(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "input_contract_ref": "fixture:input:v1",
        "input_digest": "a" * 64,
        "cell_input": _cell_input(
            "demand_authenticity_and_sustainability", 1
        ),
        "required_output_layers": [],
    }
    monkeypatch.setattr(
        DeepSeekS3ThreeCellNodeExecutor,
        "_specialist_model_view",
        classmethod(lambda cls, value: value["cell_input"]),
    )
    v1_system, v1_request, _ = (
        DeepSeekS3ThreeCellNodeExecutor._specialist_segment_request(
            node_id="domain_specialist:demand_authenticity_and_sustainability",
            segment_id="facts_explanation_and_terminal",
            payload=payload,
            validated_segments={},
            transport_ref=S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_REF,
        )
    )
    v2_system, v2_request, _ = (
        DeepSeekS3ThreeCellNodeExecutor._specialist_segment_request(
            node_id="domain_specialist:demand_authenticity_and_sustainability",
            segment_id="facts_explanation_and_terminal",
            payload=payload,
            validated_segments={},
            transport_ref=S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V2_REF,
        )
    )
    assert v1_request["required_output_schema"]["explanation_layer"] == [
        "string"
    ]
    assert "check every narrative field item by item" not in v1_system
    assert v2_request["required_output_schema"]["explanation_layer"] == [
        "non-empty string, maximum 320 Unicode characters"
    ]
    assert v2_request["required_output_schema"]["fact_layer"][0][
        "statement"
    ] == "non-empty string, maximum 320 Unicode characters"
    assert "check every narrative field item by item" in v2_system
    assert "Never truncate, coerce, drop, join, or split" in v2_system


def test_transport_v2_positive_fake_provider_fixture_preserves_topology_and_artifacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, fake = _run(
        monkeypatch,
        transport_ref=S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V2_REF,
    )
    assert tuple(row.artifact_type for row in result.artifacts) == (
        BOUNDED_AGENT_ARTIFACT_TYPES
    )
    manifest = result.artifacts[0].payload
    assert len(manifest["node_topology"]) == 6
    assert manifest["observed_counts"]["model_calls"] == 12
    assert len(fake.calls) == 12
    assert all(
        row["request"]["output_constraints"][
            "maximum_narrative_item_unicode_characters"
        ]
        == 320
        for row in fake.calls[:3]
    )


def _claim_segment_mutation(mutator: Callable[[dict[str, Any]], None]) -> Mutation:
    def mutate(request: dict[str, Any], output: dict[str, Any]) -> dict[str, Any]:
        if (
            request.get("node_id")
            == "domain_specialist:demand_authenticity_and_sustainability"
            and request.get("segment_id") == "owner_grade_claim_cards"
        ):
            mutator(output)
        return output

    return mutate


def _task_segment_mutation(mutator: Callable[[dict[str, Any]], None]) -> Mutation:
    def mutate(request: dict[str, Any], output: dict[str, Any]) -> dict[str, Any]:
        if (
            request.get("node_id")
            == "domain_specialist:demand_authenticity_and_sustainability"
            and request.get("segment_id")
            == "actionable_what_would_change_tasks"
        ):
            mutator(output)
        return output

    return mutate


@pytest.mark.parametrize(
    (
        "mutation",
        "expected_calls",
        "expected_field",
        "expected_subtype",
    ),
    [
        (
            _first_segment_mutation(
                lambda output: output["fact_layer"][0].update(
                    {"statement": {"secret_raw_text": "must-not-persist"}}
                )
            ),
            1,
            "fact_layer.statement_or_boundary",
            "item_not_string",
        ),
        (
            _first_segment_mutation(
                lambda output: output.update({"explanation_layer": ["  "]})
            ),
            1,
            "explanation_layer",
            "item_blank",
        ),
        (
            _first_segment_mutation(
                lambda output: output.update({"remaining_gaps": ["x" * 321]})
            ),
            1,
            "remaining_gaps",
            "item_over_max_unicode_characters",
        ),
        (
            _claim_segment_mutation(
                lambda output: output["judgment_layer"][0].update(
                    {"statement": 17}
                )
            ),
            2,
            "judgment_layer",
            "item_not_string",
        ),
        (
            _task_segment_mutation(
                lambda output: output["what_would_change"][0].update(
                    {"fallback_stop_condition": "y" * 321}
                )
            ),
            3,
            "what_would_change",
            "item_over_max_unicode_characters",
        ),
    ],
)
def test_transport_v2_stops_at_exact_text_subtype_without_content_or_later_calls(
    monkeypatch: pytest.MonkeyPatch,
    mutation: Mutation,
    expected_calls: int,
    expected_field: str,
    expected_subtype: str,
) -> None:
    with pytest.raises(BoundedAgentExecutionError) as captured:
        _run(
            monkeypatch,
            mutation=mutation,
            transport_ref=S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V2_REF,
        )
    observation = captured.value.failure_observation
    assert observation["observed_counts"]["model_calls"] == expected_calls
    assert len(observation["usage_receipts"]) == expected_calls
    telemetry = observation["failure_telemetry"][
        "segmented_specialist_text"
    ]
    assert telemetry == {
        "validator_contract": "closed_segment_narrative_text:v1",
        "segment_id": (
            "facts_explanation_and_terminal"
            if expected_calls == 1
            else (
                "owner_grade_claim_cards"
                if expected_calls == 2
                else "actionable_what_would_change_tasks"
            )
        ),
        "field_id": expected_field,
        "text_subtype": expected_subtype,
        "failing_item_count": 1,
        "raw_text_persisted": False,
        "item_index_persisted": False,
        "arbitrary_key_names_persisted": False,
        "private_reasoning_persisted": False,
    }
    serialized = json.dumps(observation, ensure_ascii=False)
    assert "must-not-persist" not in serialized
    assert "secret_raw_text" not in serialized
    assert "x" * 321 not in serialized
    assert "y" * 321 not in serialized


@pytest.mark.parametrize(
    ("mutation", "expected_calls"),
    [
        (
            _claim_segment_mutation(
                lambda output: output["judgment_layer"][0].pop("qualification")
            ),
            2,
        ),
        (
            _task_segment_mutation(
                lambda output: output["what_would_change"][0][
                    "source_target"
                ].update({"unexpected_field": 17})
            ),
            3,
        ),
    ],
)
def test_transport_v2_leaves_missing_or_extra_members_to_structure_validator(
    monkeypatch: pytest.MonkeyPatch,
    mutation: Mutation,
    expected_calls: int,
) -> None:
    with pytest.raises(BoundedAgentExecutionError) as captured:
        _run(
            monkeypatch,
            mutation=mutation,
            transport_ref=S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V2_REF,
        )
    observation = captured.value.failure_observation
    assert observation["observed_counts"]["model_calls"] == expected_calls
    assert "failure_telemetry" not in observation
    assert "segmented_specialist_contract_invalid" in observation["failure_codes"][0]


def test_transport_v2_admission_is_distinct_and_v1_remains_admissible() -> None:
    cells, _ = _surfaces()
    input_pack = _input_pack(deepcopy(cells))
    _admission(input_pack).assert_profile_admissible()
    v2 = _admission(
        input_pack,
        transport_ref=S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V2_REF,
    )
    v2.assert_profile_admissible()
    assert v2.transport_ref != S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_REF


def test_transport_v2_repair_result_and_next_authority_are_frozen() -> None:
    result = json.loads(
        (
            ROOT
            / "configs/releases/fin_ia_0_1_s3_t09_owner_grade_v3_segmented_field_local_text_contract_and_safe_subtype_telemetry_repair_v1_0.json"
        ).read_text(encoding="utf-8")
    )
    backlog = json.loads(
        (
            ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
        ).read_text(encoding="utf-8")
    )
    assert result["status"] == (
        "pass_zero_call_transport_v2_field_local_text_contract_and_safe_subtype_"
        "telemetry_fixture_proven_fresh_proof_decision_pending"
    )
    assert result["implementation"]["transport_ref"] == (
        S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V2_REF
    )
    assert result["deterministic_proof"]["text_failure_field_fixture_count"] == 5
    assert set(result["observed_counts"].values()) == {0}
    assert result["next_action"] == (
        "S3-T09-OWNER-GRADE-V3-SEGMENTED-TEXT-CONTRACT-V2-FRESH-AGENT-"
        "PROOF-DECISION"
    )
    assert backlog["next_action"]["item_id"] == (
        "S3-T09-OWNER-GRADE-V3-SEGMENTED-TRANSPORT-V5-RESEARCH-LEAD-OUTPUT-TRUNCATION-RESULT-AND-ROOT-CAUSE-DECISION"
    )
    assert backlog["next_action"][
        "text_contract_zero_call_repair_implementation_authorized"
    ] is True
    assert backlog["next_action"][
        "text_contract_v2_fresh_agent_proof_decision_authorized"
    ] is True
    assert backlog["next_action"]["agent_rerun_authorized"] is False
    assert backlog["next_action"][
        "transport_v3_context_authority_zero_call_implementation_authorized"
    ] is True
