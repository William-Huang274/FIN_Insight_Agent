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
    BOUNDED_DEEPSEEK_BETA_BASE_URL,
    BoundedAgentExecutionError,
    DeepSeekS3ThreeCellNodeExecutor,
    S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V2_REF,
    S3_OWNER_GRADE_RESEARCH_LEAD_V2_AGGREGATE_OUTPUT_TOKEN_BUDGET,
    S3_OWNER_GRADE_RESEARCH_LEAD_V2_MAX_ASSEMBLED_UTF8_BYTES,
    S3_OWNER_GRADE_RESEARCH_LEAD_V2_MAX_PROVIDER_UTF8_BYTES,
    S3_OWNER_GRADE_RESEARCH_LEAD_V2_STAGE_OUTPUT_TOKEN_BUDGETS,
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V5_REF,
    S3_PROVIDER_OUTPUT_CAPTURE_POLICY_REF,
    S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF,
    S3ResearchLeadContractError,
    S3ThreeCellBoundedAgentAdmission,
    build_s3_three_cell_bounded_agent_executor_for_admission,
)
from sec_agent.canonical_runtime.models import canonical_digest
from test_fin_0_1_s3_t09_owner_grade_semantic_actionability_zero_call_repair import (
    _input_pack,
    _lead_output,
)
from test_fin_0_1_s3_t09_owner_grade_v3_segmented_specialist_transport import (
    _SegmentedOwnerGradeFakeProvider,
)
from test_fin_0_1_s3_t09_owner_grade_v3_segmented_transport_v3_closed_context_authority_repair import (
    _production_surfaces,
)


def _admission(input_pack: Any) -> S3ThreeCellBoundedAgentAdmission:
    return S3ThreeCellBoundedAgentAdmission(
        admission_id="fixture-s3-t09-research-lead-v2",
        output_contract_ref=S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF,
        execution_enabled=True,
        execution_mode="fixture_only_research_lead_v2",
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
        research_lead_transport_ref=S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V2_REF,
        provider_output_capture_policy_ref=S3_PROVIDER_OUTPUT_CAPTURE_POLICY_REF,
        max_semantic_model_calls=12,
        max_provider_calls=12,
        max_network_calls=12,
        max_total_cost_usd=0.10,
        specialist_max_output_tokens=4200,
        lead_max_output_tokens=1800,
        writer_max_output_tokens=1400,
        verifier_max_output_tokens=1000,
    )


def _provider_lead_segment(
    specialists: list[Mapping[str, Any]],
) -> dict[str, Any]:
    output = _lead_output(specialists)
    output.pop("cell_heads")
    return output


def _run(monkeypatch: pytest.MonkeyPatch, mutation=None):
    cells, specialists = _production_surfaces()
    input_pack = _input_pack(cells)
    admission = _admission(input_pack)

    def remove_heads(request: dict[str, Any], output: dict[str, Any]) -> dict[str, Any]:
        if request.get("node_id") == "research_lead":
            output.pop("cell_heads")
        if mutation is not None:
            return mutation(request, output)
        return output

    fake = _SegmentedOwnerGradeFakeProvider(
        specialists,
        mutation=remove_heads,
    )
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture-not-a-real-secret")
    executor = build_s3_three_cell_bounded_agent_executor_for_admission(
        admission,
        chat_completion_fn=fake,
    )
    result = executor.execute(
        input_pack,
        admission,
        run_identity={
            "research_run_id": "fixture-run-research-lead-v2",
            "attempt_id": "fixture-attempt-research-lead-v2",
        },
    )
    return result, fake, specialists


def test_research_lead_v2_budget_is_explicit_and_historical_default_is_immutable() -> None:
    cells, _ = _production_surfaces()
    input_pack = _input_pack(cells)
    admission = _admission(input_pack)
    admission.assert_profile_admissible()
    assert S3_OWNER_GRADE_RESEARCH_LEAD_V2_STAGE_OUTPUT_TOKEN_BUDGETS == {
        "specialist": 4200,
        "lead": 1800,
        "writer": 1400,
        "verifier": 1000,
    }
    assert S3_OWNER_GRADE_RESEARCH_LEAD_V2_AGGREGATE_OUTPUT_TOKEN_BUDGET == 16800
    assert admission.max_total_cost_usd == 0.10
    assert admission.retry_budget == 0
    assert admission.max_transport_attempts_per_call == 1
    historical = admission.model_copy(
        update={
            "research_lead_transport_ref": (
                "fin01.s3.bounded_agent.research_lead_owner_grade:v1"
            ),
            "lead_max_output_tokens": 1200,
        }
    )
    historical.assert_profile_admissible()
    historical_unset = S3ThreeCellBoundedAgentAdmission.model_validate(
        {
            key: value
            for key, value in historical.model_dump(mode="json").items()
            if key != "research_lead_transport_ref"
        }
    )
    assert "research_lead_transport_ref" not in historical_unset.digest_payload()


def test_research_lead_v2_request_retains_full_specialists_without_heads_or_digest_map(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, fake, specialists = _run(monkeypatch)
    lead_call = next(
        row for row in fake.calls if row["request"]["node_id"] == "research_lead"
    )
    request = lead_call["request"]
    assert set(request["required_top_level_keys"]) == {
        "cross_cell_dependencies",
        "conflict_adjudications",
        "variant_view",
        "remaining_gaps",
    }
    assert "cell_heads" not in request["required_output_schema"]
    assert "specialist_output_digests" not in request["analysis_input"]
    assert request["analysis_input"]["specialist_outputs"] == list(
        specialists.values()
    )
    assert request["output_constraints"] == {
        "cross_cell_dependencies_cardinality": "1..3",
        "conflict_adjudications_cardinality": "0..3",
        "variant_view_cardinality": "exactly_one_object",
        "remaining_gaps_cardinality": "1..4",
        "maximum_narrative_field_unicode_characters": 320,
        "maximum_provider_segment_serialized_utf8_bytes": 6000,
        "maximum_locally_assembled_lead_utf8_bytes": 8192,
        "cell_heads_emitted_by_provider": False,
    }
    assert lead_call["kwargs"]["max_tokens"] == 1800
    judgment = next(
        row
        for row in result.artifacts
        if row.artifact_type == "bounded_agent_judgment"
    ).payload
    lead = judgment["cross_cell_lead"]
    assert len(lead["cell_heads"]) == 3
    for head, specialist in zip(
        lead["cell_heads"], specialists.values(), strict=True
    ):
        assert head["program_cell_id"] == specialist["program_cell_id"]
        assert head["specialist_output_digest"] == canonical_digest(specialist)
    assert len(fake.calls) == 12


def test_research_lead_v2_minimum_and_maximum_closed_shapes_fit_both_envelopes() -> None:
    _, specialists_by_cell = _production_surfaces()
    specialists = list(specialists_by_cell.values())
    minimum = _provider_lead_segment(specialists)
    minimum["conflict_adjudications"] = []
    DeepSeekS3ThreeCellNodeExecutor._validate_research_lead_v2_segment(
        minimum, specialists
    )
    maximum = deepcopy(minimum)
    maximum["cross_cell_dependencies"] = [
        {**deepcopy(minimum["cross_cell_dependencies"][0]), "dependency_id": f"d:{i}"}
        for i in range(3)
    ]
    maximum["conflict_adjudications"] = [
        {
            **deepcopy(_provider_lead_segment(specialists)["conflict_adjudications"][0]),
            "adjudication_id": f"a:{i}",
        }
        for i in range(3)
    ]
    maximum["remaining_gaps"] = [
        {**deepcopy(minimum["remaining_gaps"][0]), "gap_id": f"g:{i}"}
        for i in range(4)
    ]
    DeepSeekS3ThreeCellNodeExecutor._validate_research_lead_v2_segment(
        maximum, specialists
    )
    provider_bytes = len(
        json.dumps(
            maximum, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    )
    heads = DeepSeekS3ThreeCellNodeExecutor._derive_research_lead_cell_heads(
        specialists,
        {
            str(row["program_cell_id"]): canonical_digest(row)
            for row in specialists
        },
    )
    assembled_bytes = len(
        json.dumps(
            {"cell_heads": heads, **maximum},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    assert provider_bytes <= S3_OWNER_GRADE_RESEARCH_LEAD_V2_MAX_PROVIDER_UTF8_BYTES
    assert assembled_bytes <= S3_OWNER_GRADE_RESEARCH_LEAD_V2_MAX_ASSEMBLED_UTF8_BYTES


@pytest.mark.parametrize(
    ("mutate", "family", "subtype", "field_id"),
    [
        (
            lambda row: row.pop("remaining_gaps"),
            "shape",
            "top_level_keys_missing",
            "top_level",
        ),
        (
            lambda row: row.update({"unexpected": []}),
            "shape",
            "top_level_keys_unexpected",
            "top_level",
        ),
        (
            lambda row: row.update({"cross_cell_dependencies": []}),
            "cardinality",
            "below_minimum",
            "cross_cell_dependencies",
        ),
        (
            lambda row: row.update(
                {
                    "remaining_gaps": [
                        *row["remaining_gaps"],
                        *[deepcopy(row["remaining_gaps"][0]) for _ in range(4)],
                    ]
                }
            ),
            "cardinality",
            "above_maximum",
            "remaining_gaps",
        ),
        (
            lambda row: row["variant_view"].update({"statement": "x" * 321}),
            "text",
            "item_over_max_unicode_characters",
            "variant_view",
        ),
        (
            lambda row: row["variant_view"].update(
                {"claim_ids": ["unauthorized-claim"]}
            ),
            "authority",
            "claim_ref_invalid",
            "variant_view",
        ),
    ],
)
def test_research_lead_v2_rejects_closed_contract_boundaries(
    mutate, family: str, subtype: str, field_id: str
) -> None:
    _, specialists_by_cell = _production_surfaces()
    specialists = list(specialists_by_cell.values())
    output = _provider_lead_segment(specialists)
    mutate(output)
    with pytest.raises(S3ResearchLeadContractError) as captured:
        DeepSeekS3ThreeCellNodeExecutor._validate_research_lead_v2_segment(
            output, specialists
        )
    assert captured.value.telemetry["failure_family"] == family
    assert captured.value.telemetry["failure_subtype"] == subtype
    assert captured.value.telemetry["field_id"] == field_id
    assert all(
        captured.value.telemetry[key] is False
        for key in (
            "raw_text_persisted",
            "ref_or_digest_persisted",
            "item_index_persisted",
            "arbitrary_key_names_persisted",
            "private_reasoning_persisted",
        )
    )


def test_research_lead_v2_earliest_stop_exposes_only_closed_content_free_telemetry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def over_cardinality(request: dict[str, Any], output: dict[str, Any]):
        if request.get("node_id") == "research_lead":
            output["remaining_gaps"] = [
                *output["remaining_gaps"],
                *[deepcopy(output["remaining_gaps"][0]) for _ in range(4)],
            ]
        return output

    with pytest.raises(BoundedAgentExecutionError) as captured:
        _run(monkeypatch, mutation=over_cardinality)
    observation = captured.value.failure_observation
    assert observation["observed_counts"]["model_calls"] == 10
    assert observation["failure_telemetry"] == {
        "research_lead_contract": {
            "validator_contract": "closed_research_lead_output:v2",
            "failure_family": "cardinality",
            "failure_subtype": "above_maximum",
            "field_id": "remaining_gaps",
            "failing_item_count": 1,
            "raw_text_persisted": False,
            "ref_or_digest_persisted": False,
            "item_index_persisted": False,
            "arbitrary_key_names_persisted": False,
            "private_reasoning_persisted": False,
        }
    }


@pytest.mark.parametrize(
    ("content", "finish_reason", "family", "subtype"),
    [
        (
            '{"cross_cell_dependencies":[',
            "stop",
            "parse",
            "json_decode_failed",
        ),
        (
            "{}",
            "length",
            "capacity",
            "provider_length_stop",
        ),
        (
            json.dumps({"oversize": "x" * 6100}),
            "stop",
            "capacity",
            "provider_segment_over_max_utf8_bytes",
        ),
    ],
)
def test_research_lead_v2_parse_and_capacity_stop_before_semantic_validation(
    content: str,
    finish_reason: str,
    family: str,
    subtype: str,
) -> None:
    cells, _ = _production_surfaces()
    admission = _admission(_input_pack(cells))

    def provider(**kwargs: Any) -> Mapping[str, Any]:
        return {
            "status": "ok",
            "finish_reason": finish_reason,
            "content": content,
            "input_tokens": 10,
            "output_tokens": 100,
            "total_tokens": 110,
            "call_id": "fixture-lead-v2-stop",
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

    node = DeepSeekS3ThreeCellNodeExecutor(chat_completion_fn=provider)
    state = {
        "spent_usd": 0.0,
        "usage_receipts": [],
        "provider_output_captures": [],
        "failed": False,
    }
    with pytest.raises(BoundedAgentExecutionError) as captured:
        node._call_json_object(
            state=state,
            logical_node_id="research_lead",
            receipt_stage="research_lead",
            system="fixture",
            request={"fixture": True},
            max_tokens=1800,
            admission=admission,
            input_digest=admission.input_digest or "",
            research_run_id="fixture-research-run",
            enforce_specialist_byte_limit=False,
            research_lead_v2_telemetry=True,
            output_byte_limit=6000,
        )
    telemetry = captured.value.failure_observation["failure_telemetry"][
        "research_lead_contract"
    ]
    assert telemetry["failure_family"] == family
    assert telemetry["failure_subtype"] == subtype
    assert captured.value.failure_observation["observed_counts"]["model_calls"] == 1


def test_research_lead_v2_zero_call_result_and_next_authority_are_frozen() -> None:
    result = json.loads(
        (
            ROOT
            / "configs/releases/fin_ia_0_1_s3_t09_owner_grade_v3_research_lead_closed_output_local_head_assembly_and_bounded_headroom_zero_call_implementation_v1_0.json"
        ).read_text(encoding="utf-8")
    )
    assert result["status"].startswith("pass_zero_call_research_lead_v2")
    assert result["implementation"]["lead_max_output_tokens"] == 1800
    assert result["implementation"]["aggregate_max_output_tokens"] == 16800
    assert set(result["observed_counts"].values()) == {0}
    assert result["next_action"] == (
        "S3-T09-OWNER-GRADE-V3-RESEARCH-LEAD-V2-FRESH-AGENT-PROOF-DECISION"
    )
