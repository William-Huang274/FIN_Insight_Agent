from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
from typing import Any, Callable, Mapping

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
    S3_OWNER_GRADE_SEGMENTED_AGGREGATE_OUTPUT_TOKEN_BUDGET,
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_REF,
    S3_OWNER_GRADE_SEGMENTED_STAGE_OUTPUT_TOKEN_BUDGETS,
    S3_OWNER_GRADE_SPECIALIST_SEGMENT_IDS,
    S3_OWNER_GRADE_SPECIALIST_SEGMENT_TOKEN_BUDGETS,
    S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF,
    S3ThreeCellBoundedAgentAdmission,
    build_s3_three_cell_bounded_agent_executor_for_admission,
)
from test_fin_0_1_s3_t09_owner_grade_semantic_actionability_zero_call_repair import (
    _input_pack,
    _lead_output,
    _specialist_output,
    _verifier_output,
    _writer_output,
    _cell_input,
)


Mutation = Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]


def test_failure_telemetry_families_are_mutually_exclusive() -> None:
    with pytest.raises(
        ValueError, match="bounded_agent_failure_telemetry_family_ambiguous"
    ):
        BoundedAgentExecutionError(
            "domain_specialist:demand_authenticity_and_sustainability",
            usage_receipts=[],
            estimated_cost_usd=0.0,
            strict_tool_parse_subtype="json_decode_error",
            segmented_specialist_shape={
                "parser_contract": "closed_segment_top_level_shape:v1",
                "segment_id": "facts_explanation_and_terminal",
                "shape_subtype": "top_level_keys_unexpected",
                "missing_key_count": 0,
                "unexpected_key_count": 1,
                "raw_output_persisted": False,
                "arbitrary_key_names_persisted": False,
            },
        )


def _surfaces() -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    cells = [
        _cell_input(cell_id, index)
        for index, cell_id in enumerate(
            (
                "demand_authenticity_and_sustainability",
                "value_and_profit_capture",
                "bottleneck_counterevidence_and_what_would_change",
            ),
            1,
        )
    ]
    specialists = {
        str(cell["program_cell_id"]): _specialist_output(cell, index)
        for index, cell in enumerate(cells, 1)
    }
    return cells, specialists


def _admission(
    input_pack: Any,
    *,
    transport_ref: str = S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_REF,
) -> S3ThreeCellBoundedAgentAdmission:
    return S3ThreeCellBoundedAgentAdmission(
        admission_id="fixture-s3-t09-segmented-owner-grade-v3",
        output_contract_ref=S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF,
        execution_enabled=True,
        execution_mode="fixture_only_segmented_owner_grade_v3",
        case_id=input_pack.case_id,
        case_version=input_pack.case_version,
        as_of=input_pack.as_of,
        input_digest=input_pack.input_digest,
        provider="deepseek",
        model="deepseek-v4-pro",
        model_ref="deepseek:deepseek-v4-pro",
        api_key_env="DEEPSEEK_API_KEY",
        base_url=BOUNDED_DEEPSEEK_BETA_BASE_URL,
        transport_ref=transport_ref,
        max_semantic_model_calls=12,
        max_provider_calls=12,
        max_network_calls=12,
        max_total_cost_usd=0.10,
        specialist_max_output_tokens=4200,
        lead_max_output_tokens=1200,
        writer_max_output_tokens=1400,
        verifier_max_output_tokens=1000,
    )


class _SegmentedOwnerGradeFakeProvider:
    def __init__(
        self,
        specialists: Mapping[str, dict[str, Any]],
        *,
        mutation: Mutation | None = None,
    ) -> None:
        self.specialists = specialists
        self.mutation = mutation
        self.calls: list[dict[str, Any]] = []

    def __call__(self, **kwargs: Any) -> Mapping[str, Any]:
        request = json.loads(kwargs["messages"][1]["content"])
        self.calls.append({"kwargs": dict(kwargs), "request": request})
        node_id = str(request["node_id"])
        if node_id.startswith("domain_specialist:"):
            cell_id = node_id.split(":", 1)[1]
            specialist = self.specialists[cell_id]
            segment_id = request["segment_id"]
            if segment_id == "facts_explanation_and_terminal":
                output = {
                    key: deepcopy(specialist[key])
                    for key in (
                        "program_cell_id",
                        "fact_layer",
                        "explanation_layer",
                        "remaining_gaps",
                        "terminal_class",
                    )
                }
            elif segment_id == "owner_grade_claim_cards":
                output = {
                    "program_cell_id": specialist["program_cell_id"],
                    "judgment_layer": deepcopy(specialist["judgment_layer"]),
                }
            else:
                output = {
                    "program_cell_id": specialist["program_cell_id"],
                    "what_would_change": deepcopy(
                        specialist["what_would_change"]
                    ),
                }
        elif node_id == "research_lead":
            output = _lead_output(list(request["analysis_input"]["specialist_outputs"]))
        elif node_id == "memo_writer":
            analysis = request["analysis_input"]
            output = _writer_output(
                list(analysis["specialist_heads"]), analysis["cross_cell_lead"]
            )
        elif node_id == "verifier":
            analysis = request["analysis_input"]
            output = _verifier_output(
                analysis["cross_cell_lead"], analysis["writer_output"]
            )
            required_finding = request["required_output_schema"]["findings"][0]
            if any(
                set(finding) != set(required_finding)
                for finding in output["findings"]
            ):
                raise AssertionError(
                    "fixture_verifier_output_does_not_follow_required_output_schema"
                )
        else:
            raise AssertionError(node_id)
        if self.mutation is not None:
            output = self.mutation(request, output)
        content = json.dumps(output, ensure_ascii=False, sort_keys=True)
        return {
            "status": "ok",
            "finish_reason": "stop",
            "content": content,
            "input_tokens": 10,
            "output_tokens": 100,
            "total_tokens": 110,
            "call_id": f"fixture-segmented-{len(self.calls)}",
            "provider": "deepseek",
            "model": "deepseek-v4-pro",
            "latency_ms": 1,
            "transport_attempt_count": 1,
            "raw_response": {
                "usage": {
                    "prompt_cache_hit_tokens": 0,
                    "prompt_cache_miss_tokens": 10,
                }
            },
        }


def _run(
    monkeypatch: pytest.MonkeyPatch,
    *,
    mutation: Mutation | None = None,
    transport_ref: str = S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_REF,
) -> tuple[Any, _SegmentedOwnerGradeFakeProvider]:
    cells, specialists = _surfaces()
    input_pack = _input_pack(cells)
    admission = _admission(input_pack, transport_ref=transport_ref)
    fake = _SegmentedOwnerGradeFakeProvider(specialists, mutation=mutation)
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture-not-a-real-secret")
    monkeypatch.setattr(
        DeepSeekS3ThreeCellNodeExecutor,
        "_specialist_model_view",
        classmethod(
            lambda cls, payload: {
                "program_cell_id": payload["cell_input"]["program_cell_id"],
                "authority_refs": payload["cell_input"]["authority_refs"],
            }
        ),
    )
    executor = build_s3_three_cell_bounded_agent_executor_for_admission(
        admission, chat_completion_fn=fake
    )
    result = executor.execute(
        input_pack,
        admission,
        run_identity={
            "research_run_id": "fixture-run-segmented-owner-grade-v3",
            "attempt_id": "fixture-attempt-segmented-owner-grade-v3",
        },
    )
    return result, fake


def test_segmented_transport_is_admission_bound_to_exact_v3_twelve_call_budget() -> None:
    cells, _ = _surfaces()
    input_pack = _input_pack(cells)
    admission = _admission(input_pack)
    admission.assert_profile_admissible()
    assert S3_OWNER_GRADE_SEGMENTED_STAGE_OUTPUT_TOKEN_BUDGETS == {
        "specialist": 4200,
        "lead": 1200,
        "writer": 1400,
        "verifier": 1000,
    }
    assert S3_OWNER_GRADE_SPECIALIST_SEGMENT_TOKEN_BUDGETS == {
        "facts_explanation_and_terminal": 1600,
        "owner_grade_claim_cards": 1200,
        "actionable_what_would_change_tasks": 1400,
    }
    assert S3_OWNER_GRADE_SEGMENTED_AGGREGATE_OUTPUT_TOKEN_BUDGET == 16200
    with pytest.raises(ValueError, match="s3_bounded_admission_exact_call_budget_required"):
        admission.model_copy(update={"max_provider_calls": 11}).assert_profile_admissible()


def test_segmented_transport_positive_fixture_preserves_six_nodes_and_nine_artifacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, fake = _run(monkeypatch)
    assert tuple(row.artifact_type for row in result.artifacts) == BOUNDED_AGENT_ARTIFACT_TYPES
    manifest = result.artifacts[0].payload
    assert len(manifest["node_topology"]) == 6
    assert manifest["observed_counts"]["model_calls"] == 12
    assert manifest["observed_counts"]["provider_calls"] == 12
    assert manifest["observed_counts"]["network_calls"] == 12
    assert len(fake.calls) == 12
    specialist_calls = [
        row for row in fake.calls if row["request"]["node_id"].startswith("domain_specialist:")
    ]
    assert [row["request"]["segment_id"] for row in specialist_calls] == list(
        S3_OWNER_GRADE_SPECIALIST_SEGMENT_IDS
    ) * 3
    for row in specialist_calls:
        request = row["request"]
        assert set(request["required_output_schema"]) == set(
            request["required_top_level_keys"]
        )
        assert not set(request["output_constraints"]) & set(
            request["required_output_schema"]
        )
        assert request["additional_properties_allowed"] is False


def _first_segment_mutation(
    mutator: Callable[[dict[str, Any]], None]
) -> Mutation:
    def mutate(request: dict[str, Any], output: dict[str, Any]) -> dict[str, Any]:
        if (
            request.get("node_id")
            == "domain_specialist:demand_authenticity_and_sustainability"
            and request.get("segment_id") == "facts_explanation_and_terminal"
        ):
            mutator(output)
        return output

    return mutate


@pytest.mark.parametrize(
    ("mutation", "expected_calls", "expected_fragment", "shape_subtype"),
    [
        (
            _first_segment_mutation(
                lambda output: output.update({"unexpected_provider_field": "do-not-persist"})
            ),
            1,
            "segmented_specialist_shape_invalid",
            "top_level_keys_unexpected",
        ),
        (
            _first_segment_mutation(
                lambda output: output.update({"program_cell_id": "wrong-cell"})
            ),
            1,
            "segmented_specialist_shape_invalid",
            "program_cell_id_mismatch",
        ),
        (
            _first_segment_mutation(
                lambda output: output["fact_layer"][0].update(
                    {"support_refs": ["candidate:1"]}
                )
            ),
            1,
            "fact_authority_invalid",
            None,
        ),
        (
            _first_segment_mutation(
                lambda output: output["fact_layer"].append(
                    deepcopy(output["fact_layer"][0])
                )
            ),
            1,
            "fact_or_ref_duplicate_invalid",
            None,
        ),
        (
            lambda request, output: (
                {
                    **output,
                    "judgment_layer": [
                        {
                            **output["judgment_layer"][0],
                            "support_fact_ids": ["fact:unknown"],
                        }
                    ],
                }
                if request.get("node_id")
                == "domain_specialist:demand_authenticity_and_sustainability"
                and request.get("segment_id") == "owner_grade_claim_cards"
                else output
            ),
            2,
            "claim_support_fact_unknown",
            None,
        ),
        (
            lambda request, output: (
                {
                    **output,
                    "what_would_change": [
                        {
                            **output["what_would_change"][0],
                            "authority_refs": ["candidate:unknown"],
                        }
                    ],
                }
                if request.get("node_id")
                == "domain_specialist:demand_authenticity_and_sustainability"
                and request.get("segment_id")
                == "actionable_what_would_change_tasks"
                else output
            ),
            3,
            "wwc_task_incomplete",
            None,
        ),
    ],
)
def test_segmented_transport_stops_at_earliest_invalid_segment_without_later_calls(
    monkeypatch: pytest.MonkeyPatch,
    mutation: Mutation,
    expected_calls: int,
    expected_fragment: str,
    shape_subtype: str | None,
) -> None:
    with pytest.raises(BoundedAgentExecutionError) as captured:
        _run(monkeypatch, mutation=mutation)
    observation = captured.value.failure_observation
    assert len(observation["usage_receipts"]) == expected_calls
    assert observation["observed_counts"]["model_calls"] == expected_calls
    assert expected_fragment in observation["failure_codes"][0]
    assert all(
        not receipt["stage"].startswith("research_lead")
        for receipt in observation["usage_receipts"]
    )
    if shape_subtype is not None:
        telemetry = observation["failure_telemetry"]["segmented_specialist_shape"]
        assert telemetry["shape_subtype"] == shape_subtype
        assert set(telemetry) == {
            "parser_contract",
            "segment_id",
            "shape_subtype",
            "missing_key_count",
            "unexpected_key_count",
            "raw_output_persisted",
            "arbitrary_key_names_persisted",
        }
        assert "do-not-persist" not in json.dumps(observation)
    else:
        assert "failure_telemetry" not in observation


def test_segmented_transport_result_and_next_authority_are_frozen() -> None:
    result = json.loads(
        (
            ROOT
            / "configs/releases/fin_ia_0_1_s3_t09_owner_grade_v3_segmented_specialist_transport_implementation_v1_0.json"
        ).read_text(encoding="utf-8")
    )
    assert result["status"] == (
        "pass_zero_call_segmented_specialist_transport_fixture_proven_"
        "fresh_exact_admission_decision_pending"
    )
    assert result["implementation"]["transport_ref"] == (
        S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_REF
    )
    assert result["implementation"]["maximum_semantic_provider_network_calls"] == [
        12,
        12,
        12,
    ]
    assert result["deterministic_proof"]["negative_fixture_count"] == 6
    assert set(result["observed_counts"].values()) == {0}
    assert result["next_action"] == (
        "S3-T09-OWNER-GRADE-V3-SEGMENTED-SPECIALIST-FRESH-EXACT-"
        "ADMISSION-DECISION"
    )
    # Historical result contracts freeze their own next action. The mutable
    # program backlog is intentionally allowed to advance independently.
