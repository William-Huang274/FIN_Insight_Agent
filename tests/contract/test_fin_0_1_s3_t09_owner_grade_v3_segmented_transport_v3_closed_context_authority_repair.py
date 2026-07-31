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
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V2_REF,
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V3_REF,
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
    _run as _run_historical_transport,
    _surfaces,
)


def _production_surfaces() -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    cells, specialists = _surfaces()
    for index, cell in enumerate(cells, 1):
        candidate_ref = str(cell["authority_refs"]["candidate_refs_not_evidence"][0])
        graph_ref = str(
            cell["authority_refs"]["graph_context_refs_not_evidence"][0]
        )
        cell["authority_refs"]["accepted_evidence_refs"] = [f"evidence:{index}"]
        cell["role_contexts"] = [
            {
                "target_node": "domain_specialist",
                "authority": {
                    "candidate_context_refs": [candidate_ref],
                    "graph_context_refs": [graph_ref],
                    "fact_promotion_authorized": False,
                },
            }
        ]
        cell["evidence_input"] = {
            "route_outcome": "fixture_closed_context_only",
            "candidate_bundle": {
                "candidates": [
                    {
                        "candidate_id": candidate_ref,
                        "document_id": f"fixture-document-{index}",
                        "document_version": "v1",
                        "source_policy_ref": "fixture-local-only",
                        "route_id": f"fixture-route-{index}",
                        "source_role": "context_only",
                        "source_authority_rank": "candidate",
                        "entity_ref": "NVDA",
                        "period_ref": "FY2025-FY",
                        "section_or_table_ref": "fixture-section",
                        "content_ref": f"fixture-content-{index}",
                    }
                ]
            },
            "promotion_assessment": {
                "decision": "context_only",
                "candidate_refs": [candidate_ref],
                "context_refs": [candidate_ref, graph_ref],
                "rejected_refs": [],
                "typed_gap_codes": ["segment_revenue_not_supported"],
                "accepted_evidence_refs": [f"evidence:{index}"],
                "evidence_gate_owner_ref": "fixture:evidence-gate",
            },
        }
        cell["graph_context_input"] = {
            "product_industry_inputs": [
                {
                    "contract_ref": "fixture:graph-context:v1",
                    "status": "context_only",
                    "candidate_refs": [candidate_ref],
                    "typed_gaps": ["direct_evidence_absent"],
                    "direct_evidence_authorized": False,
                    "projection_input_ref": graph_ref,
                }
            ],
            "skill_contracts": [],
            "graph_edges": [],
            "market_price_in_contexts": [],
            "risk_contexts": [],
            "decision_cell": {"typed_gaps": ["direct_evidence_absent"]},
        }
    return cells, specialists


def _admission(input_pack: Any) -> S3ThreeCellBoundedAgentAdmission:
    return S3ThreeCellBoundedAgentAdmission(
        admission_id="fixture-s3-t09-segmented-owner-grade-v3-authority-v3",
        output_contract_ref=S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF,
        execution_enabled=True,
        execution_mode="fixture_only_segmented_owner_grade_v3_authority_v3",
        case_id=input_pack.case_id,
        case_version=input_pack.case_version,
        as_of=input_pack.as_of,
        input_digest=input_pack.input_digest,
        provider="deepseek",
        model="deepseek-v4-pro",
        model_ref="deepseek:deepseek-v4-pro",
        api_key_env="DEEPSEEK_API_KEY",
        base_url=BOUNDED_DEEPSEEK_BETA_BASE_URL,
        transport_ref=S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V3_REF,
        max_semantic_model_calls=12,
        max_provider_calls=12,
        max_network_calls=12,
        max_total_cost_usd=0.10,
        specialist_max_output_tokens=4200,
        lead_max_output_tokens=1200,
        writer_max_output_tokens=1400,
        verifier_max_output_tokens=1000,
    )


def _run(
    monkeypatch: pytest.MonkeyPatch,
    *,
    mutation: Mutation | None = None,
    use_empty_context_refs: bool = False,
) -> tuple[Any, _SegmentedOwnerGradeFakeProvider]:
    cells, specialists = _production_surfaces()
    input_pack = _input_pack(cells)
    admission = _admission(input_pack)

    def apply_field_contract(
        request: dict[str, Any], output: dict[str, Any]
    ) -> dict[str, Any]:
        if request.get("segment_id") == "owner_grade_claim_cards":
            allowed = request["field_authority_contract"]["allowed_context_refs"]
            output["judgment_layer"][0]["context_refs"] = (
                [] if use_empty_context_refs else list(allowed[:1])
            )
        return mutation(request, output) if mutation is not None else output

    fake = _SegmentedOwnerGradeFakeProvider(
        specialists, mutation=apply_field_contract
    )
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture-not-a-real-secret")
    executor = build_s3_three_cell_bounded_agent_executor_for_admission(
        admission, chat_completion_fn=fake
    )
    result = executor.execute(
        input_pack,
        admission,
        run_identity={
            "research_run_id": "fixture-run-segmented-owner-grade-v3-authority",
            "attempt_id": "fixture-attempt-segmented-owner-grade-v3-authority",
        },
    )
    return result, fake


@pytest.mark.parametrize("use_empty_context_refs", [False, True])
def test_v3_full_model_view_accepts_exact_subset_and_empty_array(
    monkeypatch: pytest.MonkeyPatch, use_empty_context_refs: bool
) -> None:
    result, fake = _run(
        monkeypatch, use_empty_context_refs=use_empty_context_refs
    )
    assert tuple(row.artifact_type for row in result.artifacts) == BOUNDED_AGENT_ARTIFACT_TYPES
    assert len(result.artifacts) == 9
    assert len(fake.calls) == 12
    assert len(result.provider_output_captures) == 12
    assert [row["capture_sequence"] for row in result.provider_output_captures] == list(
        range(1, 13)
    )
    assert all(
        row["assistant_output_present"] is True
        and row["raw_provider_response_included"] is False
        and row["private_reasoning_included"] is False
        and isinstance(json.loads(row["assistant_output_text"]), dict)
        for row in result.provider_output_captures
    )
    claim_requests = [
        row["request"]
        for row in fake.calls
        if row["request"].get("segment_id") == "owner_grade_claim_cards"
    ]
    assert len(claim_requests) == 3
    for index, request in enumerate(claim_requests, 1):
        assert request["field_authority_contract"] == {
            "field_id": "judgment_layer.context_refs",
            "allowed_context_refs": [f"candidate:{index}", f"graph:{index}"],
            "selection_rule": (
                "Each item must exactly equal one listed allowed_context_refs value; "
                "the output array must be a subset of that closed list."
            ),
            "empty_array_rule": "Use [] when the claim uses no context reference.",
            "forbidden_authority_classes": [
                "Evidence",
                "Numeric",
                "fact_id",
                "routing_ref",
                "free_text_or_derived_ref",
            ],
        }
        model_view = request["analysis_input"]["cell_input"]
        assert set(model_view) == {
            "program_cell_id",
            "decision_contract",
            "specialist_authority",
            "evidence_view",
            "numeric_view",
            "graph_view",
            "authority_refs",
        }
        assert model_view["evidence_view"]["candidates_not_evidence"]
        assert model_view["numeric_view"]["selected_financial_rows"]
        assert model_view["graph_view"]["product_industry"]


def _claim_context_mutation(value: Any) -> Mutation:
    def mutate(request: dict[str, Any], output: dict[str, Any]) -> dict[str, Any]:
        if (
            request.get("node_id")
            == "domain_specialist:demand_authenticity_and_sustainability"
            and request.get("segment_id") == "owner_grade_claim_cards"
        ):
            output["judgment_layer"][0]["context_refs"] = [deepcopy(value)]
        return output

    return mutate


@pytest.mark.parametrize(
    ("value", "expected_subtype"),
    [
        (7, "item_not_nonblank_string"),
        ("   ", "item_not_nonblank_string"),
        ("evidence:1", "evidence_or_numeric_ref_misclassified_as_context"),
        ("numeric:1", "evidence_or_numeric_ref_misclassified_as_context"),
        ("secret-outside-ref", "outside_current_cell_context_authority"),
    ],
)
def test_v3_invalid_context_ref_stops_at_claim_segment_with_content_free_subtype(
    monkeypatch: pytest.MonkeyPatch, value: Any, expected_subtype: str
) -> None:
    with pytest.raises(BoundedAgentExecutionError) as captured:
        _run(monkeypatch, mutation=_claim_context_mutation(value))
    observation = captured.value.failure_observation
    assert observation["observed_counts"]["model_calls"] == 2
    assert len(observation["usage_receipts"]) == 2
    assert len(captured.value.provider_output_captures) == 2
    assert captured.value.provider_output_captures[-1]["stage"].endswith(
        "owner_grade_claim_cards"
    )
    assert isinstance(
        json.loads(
            captured.value.provider_output_captures[-1]["assistant_output_text"]
        ),
        dict,
    )
    assert "s3_owner_grade_claim_context_authority_invalid" in observation[
        "failure_codes"
    ][0]
    assert observation["failure_telemetry"] == {
        "segmented_specialist_authority": {
            "validator_contract": "closed_segment_context_authority:v1",
            "segment_id": "owner_grade_claim_cards",
            "field_id": "judgment_layer.context_refs",
            "authority_subtype": expected_subtype,
            "failing_item_count": 1,
            "raw_ref_persisted": False,
            "ref_digest_persisted": False,
            "item_index_persisted": False,
            "arbitrary_key_names_persisted": False,
            "private_reasoning_persisted": False,
        }
    }
    assert "secret-outside-ref" not in json.dumps(observation)


def test_v2_request_contract_remains_without_v3_field_authority_member(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, fake = _run_historical_transport(
        monkeypatch,
        transport_ref=S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V2_REF,
    )
    claim_request = next(
        row["request"]
        for row in fake.calls
        if row["request"].get("segment_id") == "owner_grade_claim_cards"
    )
    assert "field_authority_contract" not in claim_request
    assert claim_request["required_output_schema"]["judgment_layer"][0][
        "context_refs"
    ] == ["exact Candidate or Graph context ref"]


def test_v3_zero_call_result_and_next_authority_are_frozen() -> None:
    result = json.loads(
        (
            ROOT
            / "configs/releases/fin_ia_0_1_s3_t09_owner_grade_v3_segmented_transport_v3_closed_context_authority_repair_v1_0.json"
        ).read_text(encoding="utf-8")
    )
    backlog = json.loads(
        (
            ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
        ).read_text(encoding="utf-8")
    )
    assert result["status"].startswith("pass_zero_call_transport_v3_")
    assert result["implementation"]["transport_ref"] == (
        S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V3_REF
    )
    assert result["observed_counts"] == {
        "real_model_calls": 0,
        "real_provider_calls": 0,
        "execution_network_calls": 0,
        "source_network_calls": 0,
        "external_tool_calls": 0,
        "new_admissions": 0,
        "new_WorkUnits": 0,
        "new_Attempts": 0,
        "new_ResearchRuns": 0,
        "new_Artifacts": 0,
        "paired_comparisons": 0,
        "Human_Reviews": 0,
    }
    assert result["next_action"] == (
        "S3-T09-OWNER-GRADE-V3-SEGMENTED-TRANSPORT-V3-FRESH-AGENT-"
        "PROOF-DECISION"
    )
    assert backlog["next_action"]["item_id"] == (
        "S3-T09-OWNER-GRADE-V3-SEGMENTED-TRANSPORT-V5-RESEARCH-LEAD-OUTPUT-TRUNCATION-RESULT-AND-ROOT-CAUSE-DECISION"
    )
    assert backlog["next_action"][
        "transport_v3_context_authority_zero_call_implementation_authorized"
    ] is True
    assert backlog["next_action"][
        "transport_v3_fresh_agent_proof_decision_authorized"
    ] is True
    assert backlog["next_action"][
        "transport_v3_fresh_exact_admission_issuance_authorized"
    ] is True
    assert backlog["next_action"]["agent_rerun_authorized"] is False
