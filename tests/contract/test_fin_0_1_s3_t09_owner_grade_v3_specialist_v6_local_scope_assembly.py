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
    DeepSeekS3ThreeCellNodeExecutor,
    S3_OWNER_GRADE_MEMO_WRITER_TRANSPORT_V2_REF,
    S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V3_REF,
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V5_REF,
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V6_REF,
    S3_PROVIDER_OUTPUT_CAPTURE_POLICY_REF,
    S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF,
    S3ThreeCellBoundedAgentAdmission,
    build_s3_three_cell_bounded_agent_executor_for_admission,
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


def _first_segment(specialist: dict[str, Any]) -> dict[str, Any]:
    return {
        key: deepcopy(specialist[key])
        for key in (
            "program_cell_id",
            "fact_layer",
            "explanation_layer",
            "remaining_gaps",
            "terminal_class",
        )
    }


def _provider_claim_segment(specialist: dict[str, Any]) -> dict[str, Any]:
    claims = deepcopy(specialist["judgment_layer"])
    for claim in claims:
        claim["scope"] = {
            "metric_or_mechanism": claim["scope"]["metric_or_mechanism"]
        }
    return {
        "program_cell_id": specialist["program_cell_id"],
        "judgment_layer": claims,
    }


def _v6_admission(input_pack: Any) -> S3ThreeCellBoundedAgentAdmission:
    return S3ThreeCellBoundedAgentAdmission(
        admission_id="fixture-s3-t09-specialist-v6-local-scope-assembly",
        output_contract_ref=S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF,
        execution_enabled=True,
        execution_mode="fixture_only_specialist_v6_local_scope_assembly",
        case_id=input_pack.case_id,
        case_version=input_pack.case_version,
        as_of=input_pack.as_of,
        input_digest=input_pack.input_digest,
        provider="deepseek",
        model="deepseek-v4-pro",
        model_ref="deepseek:deepseek-v4-pro",
        api_key_env="DEEPSEEK_API_KEY",
        base_url=BOUNDED_DEEPSEEK_BETA_BASE_URL,
        transport_ref=S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V6_REF,
        research_lead_transport_ref=S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V3_REF,
        memo_writer_transport_ref=S3_OWNER_GRADE_MEMO_WRITER_TRANSPORT_V2_REF,
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


def test_v6_is_explicit_and_preserves_v5_contract_identity() -> None:
    assert S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V6_REF != (
        S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V5_REF
    )
    cells, _ = _production_surfaces()
    admission = _v6_admission(_input_pack(cells))
    admission.assert_profile_admissible()
    assert admission.digest_payload()["transport_ref"] == (
        S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V6_REF
    )


def test_v6_request_removes_provider_owned_canonical_scope_tokens() -> None:
    cells, specialists = _production_surfaces()
    cell = cells[0]
    specialist = specialists[str(cell["program_cell_id"])]
    _, request, _ = DeepSeekS3ThreeCellNodeExecutor._specialist_segment_request(
        node_id=f"domain_specialist:{cell['program_cell_id']}",
        segment_id="owner_grade_claim_cards",
        payload={
            "input_contract_ref": "fixture:input:v1",
            "input_digest": "fixture-input-digest",
            "cell_input": cell,
            "required_output_layers": [],
        },
        validated_segments={
            "facts_explanation_and_terminal": _first_segment(specialist)
        },
        transport_ref=S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V6_REF,
    )

    scope_schema = request["required_output_schema"]["judgment_layer"][0]["scope"]
    assert scope_schema == {
        "metric_or_mechanism": (
            "non-empty string, maximum 320 Unicode characters"
        )
    }
    contract = request["local_scope_assembly_contract"]
    assert contract["provider_emitted_scope_fields"] == ["metric_or_mechanism"]
    assert set(contract["locally_assembled_scope_fields"]) == {
        "entity_ref",
        "business_scope_kind",
        "business_scope_ref",
        "period",
        "attribution_level",
    }
    assert contract["normalization_or_token_copy_by_provider_allowed"] is False


def test_v6_locally_assembles_exact_period_and_rejects_provider_period_copy() -> None:
    cells, specialists = _production_surfaces()
    cell = cells[0]
    specialist = specialists[str(cell["program_cell_id"])]
    provider_output = _provider_claim_segment(specialist)

    assembled = (
        DeepSeekS3ThreeCellNodeExecutor._assemble_specialist_claim_scopes_v6(
            output=provider_output,
            cell_input=cell,
            validated_segments={
                "facts_explanation_and_terminal": _first_segment(specialist)
            },
        )
    )
    scope = assembled["judgment_layer"][0]["scope"]
    assert scope == specialist["judgment_layer"][0]["scope"]
    assert scope["period"] == "FY2025-FY"

    invalid = deepcopy(provider_output)
    invalid["judgment_layer"][0]["scope"]["period"] = "FY2025"
    with pytest.raises(
        ValueError,
        match="s3_bounded_specialist_scope_assembly_provider_shape_invalid",
    ):
        DeepSeekS3ThreeCellNodeExecutor._assemble_specialist_claim_scopes_v6(
            output=invalid,
            cell_input=cell,
            validated_segments={
                "facts_explanation_and_terminal": _first_segment(specialist)
            },
        )


def test_v6_fake_provider_node_reaches_exact_locally_assembled_claim_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cells, specialists = _production_surfaces()
    cell = cells[0]
    cell_id = str(cell["program_cell_id"])
    input_pack = _input_pack(cells)
    admission = _v6_admission(input_pack)

    def emit_v6_scope(
        request: dict[str, Any], output: dict[str, Any]
    ) -> dict[str, Any]:
        if request.get("segment_id") == "owner_grade_claim_cards":
            for claim in output["judgment_layer"]:
                claim["scope"] = {
                    "metric_or_mechanism": claim["scope"][
                        "metric_or_mechanism"
                    ]
                }
        return output

    fake = _SegmentedOwnerGradeFakeProvider(
        specialists,
        mutation=emit_v6_scope,
    )
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture-not-a-real-secret")
    executor = DeepSeekS3ThreeCellNodeExecutor(chat_completion_fn=fake)
    result = executor.execute_node(
        f"domain_specialist:{cell_id}",
        {
            "input_contract_ref": input_pack.input_contract_ref,
            "input_digest": input_pack.input_digest,
            "cell_input": cell,
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
            "research_run_id": "fixture-run-specialist-v6",
            "attempt_id": "fixture-attempt-specialist-v6",
        },
    )

    assert len(fake.calls) == 3
    assert len(result["provider_output_captures"]) == 3
    assert result["output"]["judgment_layer"][0]["scope"]["period"] == "FY2025-FY"
    assert result["version_bindings"]["specialist_transport_ref"] == (
        S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V6_REF
    )


class _V6FullFakeProvider(_SegmentedOwnerGradeFakeProvider):
    def __call__(self, **kwargs: Any) -> dict[str, Any]:
        request = json.loads(kwargs["messages"][1]["content"])
        if request.get("node_id") != "memo_writer":
            return dict(super().__call__(**kwargs))
        self.calls.append({"kwargs": dict(kwargs), "request": request})
        output = {
            "claim_renderings": [
                {
                    "claim_id": claim["claim_id"],
                    "analysis_text_zh_cn": "该判断严格保留上游事实和范围边界。",
                }
                for claim in request["analysis_input"]["claims"]
            ]
        }
        return {
            "status": "ok",
            "finish_reason": "stop",
            "content": json.dumps(output, ensure_ascii=False, sort_keys=True),
            "input_tokens": 10,
            "output_tokens": 100,
            "total_tokens": 110,
            "call_id": f"fixture-v6-{len(self.calls)}",
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


def test_v6_full_fake_provider_reaches_six_nodes_and_nine_artifacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cells, specialists = _production_surfaces()
    input_pack = _input_pack(cells)
    admission = _v6_admission(input_pack)

    def emit_versioned_semantic_only_outputs(
        request: dict[str, Any], output: dict[str, Any]
    ) -> dict[str, Any]:
        if request.get("segment_id") == "owner_grade_claim_cards":
            for claim in output["judgment_layer"]:
                claim["scope"] = {
                    "metric_or_mechanism": claim["scope"][
                        "metric_or_mechanism"
                    ]
                }
        elif request.get("node_id") == "research_lead":
            output.pop("cell_heads")
        return output

    fake = _V6FullFakeProvider(
        specialists,
        mutation=emit_versioned_semantic_only_outputs,
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
            "research_run_id": "fixture-run-specialist-v6-full",
            "attempt_id": "fixture-attempt-specialist-v6-full",
        },
    )

    assert (
        result.terminal_reason
        == "s3_bounded_agent_three_cell_execution_succeeded"
    )
    assert len(fake.calls) == 12
    assert len(result.provider_output_captures) == 12
    assert len(result.artifacts) == 9
