from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from retrieval.candidate_ceiling_provenance import (
    CandidateCeilingProvenanceError,
    build_candidate_ceiling_provenance,
    validate_candidate_ceiling_provenance,
)
from retrieval.current_runtime_binding import (
    project_request_route_execution_truth,
    validate_current_s1_runtime_binding_receipt,
)
from retrieval.query_plan import canonical_digest


ROOT = Path(__file__).resolve().parents[1]
POLICY = json.loads(
    (
        ROOT
        / "configs"
        / "retrieval"
        / "fin_ia_0_1_3_s1_current_product_runtime_binding_policy_v1_1.json"
    ).read_text(encoding="utf-8")
)
RECEIPT = validate_current_s1_runtime_binding_receipt(
    json.loads(
        (
            ROOT
            / "configs"
            / "runtime"
            / "fin_ia_0_1_3_current_s1_runtime_binding_receipt_v1_1.json"
        ).read_text(encoding="utf-8")
    ),
    POLICY,
)
CANDIDATE_CONTRACT = {
    "first_stage_limit": 64,
    "candidate_union_limit": 96,
    "output_limit": 16,
    "max_candidates_per_source_record": 2,
}
REQUEST = {
    "request_id": "REQ::candidate-ceiling-test",
    "case_key": "DELL",
}
STATIC_SUMMARY = {"unique_candidates": 6}
STATIC_LANES = [
    {
        "candidates": [{"source_record_id": "SRC-1"}],
        "missing_required_source_roles": [],
    }
]
EXECUTION_PLAN = {
    "narrative_requests": [
        {
            "route_request_id": "NRR::one",
            "query_family_id": "issuer_results",
            "candidate_routes": [
                "bm25_lexical",
                "dense_embedding",
                "typed_relationship_graph",
            ],
        }
    ],
    "typed_fact_requests": [],
}


def _hybrid_result() -> dict:
    return {
        "request_id": REQUEST["request_id"],
        "candidate_state": "candidate_not_evidence",
        "result_digest": "a" * 64,
        "summary": {
            "eligible_object_count": 200,
            "bm25_first_stage_count": 64,
            "qwen_first_stage_count": 64,
            "union_count_before_source_quota": 96,
            "selected_count": 1,
            "hard_filter_exclusions": {"outside_evidence_owner_scope": 10},
            "material_reservation_active": True,
        },
        "candidates": [{"compiled_object_id": "COBJ::kept"}],
        "material_evidence": {
            "requirement_plan": {
                "requirement_groups": [
                    {
                        "requirement_id": "MER::complete",
                        "facet_id": "reported_results",
                        "role": "direct",
                        "coverage_mode": "single_binding",
                    },
                    {
                        "requirement_id": "MER::incomplete",
                        "facet_id": "orders_and_backlog",
                        "role": "counter",
                        "coverage_mode": "collective_axes",
                    },
                ]
            },
            "selection": {
                "requirement_receipts": [
                    {
                        "requirement_id": "MER::complete",
                        "complete": True,
                        "selected_candidate_ids": ["COBJ::kept"],
                    },
                    {
                        "requirement_id": "MER::incomplete",
                        "complete": False,
                        "selected_candidate_ids": [],
                    },
                ]
            },
        },
    }


def test_direct_snapshot_receipt_refuses_to_claim_hybrid_or_public_gap() -> None:
    route_truth = project_request_route_execution_truth(
        execution_plan=EXECUTION_PLAN,
        binding_receipt=RECEIPT,
    )
    result = build_candidate_ceiling_provenance(
        request=REQUEST,
        request_digest=canonical_digest(REQUEST),
        static_summary=STATIC_SUMMARY,
        static_lanes=STATIC_LANES,
        route_execution_truth=route_truth,
        runtime_binding_receipt=RECEIPT,
        candidate_contract=CANDIDATE_CONTRACT,
    )

    assert result["earliest_observed_limitation"] == (
        "hybrid_candidate_runtime_not_executed"
    )
    assert result["hybrid_candidate_ceiling"]["execution_state"] == (
        "not_executed_by_direct_snapshot_endpoint"
    )
    assert result["gap_eligibility"]["public_information_gap_eligible"] is False


def test_executed_candidate_receipt_separates_preserved_and_union_incomplete() -> None:
    hybrid = _hybrid_result()
    route_truth = project_request_route_execution_truth(
        execution_plan=EXECUTION_PLAN,
        binding_receipt=RECEIPT,
        hybrid_result=hybrid,
    )
    result = build_candidate_ceiling_provenance(
        request=REQUEST,
        request_digest=canonical_digest(REQUEST),
        static_summary=STATIC_SUMMARY,
        static_lanes=STATIC_LANES,
        route_execution_truth=route_truth,
        runtime_binding_receipt=RECEIPT,
        candidate_contract=CANDIDATE_CONTRACT,
        hybrid_result=hybrid,
    )

    rows = {row["requirement_id"]: row for row in result["material_requirements"]}
    assert rows["MER::complete"]["observed_loss_stage"] == (
        "none_observed_through_candidate_review"
    )
    assert rows["MER::incomplete"]["observed_loss_stage"] == (
        "at_or_before_bounded_candidate_union_ceiling"
    )
    assert result["hybrid_candidate_ceiling"]["union_ceiling_reached"] is True
    assert result["earliest_observed_limitation"] == "at_or_before_candidate_union"
    assert "one_or_more_material_requirements_incomplete" in result[
        "gap_eligibility"
    ]["blockers"]


def test_complete_union_candidate_cut_from_final_review_is_explicit() -> None:
    hybrid = _hybrid_result()
    hybrid["material_evidence"]["selection"]["requirement_receipts"][0][
        "selected_candidate_ids"
    ] = ["COBJ::cut"]
    route_truth = project_request_route_execution_truth(
        execution_plan=EXECUTION_PLAN,
        binding_receipt=RECEIPT,
        hybrid_result=hybrid,
    )
    result = build_candidate_ceiling_provenance(
        request=REQUEST,
        request_digest=canonical_digest(REQUEST),
        static_summary=STATIC_SUMMARY,
        static_lanes=STATIC_LANES,
        route_execution_truth=route_truth,
        runtime_binding_receipt=RECEIPT,
        candidate_contract=CANDIDATE_CONTRACT,
        hybrid_result=hybrid,
    )

    assert result["material_requirements"][0]["observed_loss_stage"] == (
        "post_union_source_quota_or_review_cut"
    )
    assert result["earliest_observed_limitation"] == (
        "post_union_source_quota_or_review_cut"
    )


def test_candidate_provenance_fails_closed_if_gap_authority_is_added() -> None:
    route_truth = project_request_route_execution_truth(
        execution_plan=EXECUTION_PLAN,
        binding_receipt=RECEIPT,
    )
    result = build_candidate_ceiling_provenance(
        request=REQUEST,
        request_digest=canonical_digest(REQUEST),
        static_summary=STATIC_SUMMARY,
        static_lanes=STATIC_LANES,
        route_execution_truth=route_truth,
        runtime_binding_receipt=RECEIPT,
        candidate_contract=CANDIDATE_CONTRACT,
    )
    mutated = deepcopy(result)
    mutated["gap_eligibility"]["public_information_gap_eligible"] = True

    with pytest.raises(CandidateCeilingProvenanceError):
        validate_candidate_ceiling_provenance(mutated)
