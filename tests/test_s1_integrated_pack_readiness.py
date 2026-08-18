from __future__ import annotations

from copy import deepcopy

import pytest

from retrieval.integrated_pack_readiness import (
    IntegratedPackReadinessError,
    compile_integrated_requirement_readiness,
)


def _inputs(*, typed_state: str = "resolved", review_state: str = "accepted"):
    requirement = {
        "requirement_id": "MER::ONE",
        "facet_id": "reported_results",
        "role": "direct",
        "target_entities": ["DELL"],
        "metric_ids": ["revenue"],
        "product_ids": ["AI server revenue contribution"],
    }
    fact_result = {
        "fact_request_id": "TFR::ONE",
        "metric_id": "revenue",
        "status": typed_state,
        "facts": (
            [
                {
                    "numeric_fact_id": "NUMFACT::ONE",
                    "numeric_fact_authority": True,
                }
            ]
            if typed_state == "resolved"
            else []
        ),
    }
    product = {
        "case_key": "DELL",
        "material_scope": {
            "research_plan_digest": "PLAN",
            "scope_compilation": {"compilation_digest": "SCOPE"},
        },
        "request_results": [
            {
                "request": {
                    "request_id": "REQ::ONE",
                    "case_key": "DELL",
                    "research_as_of": "2026-08-06",
                },
                "hybrid_object_retrieval": {
                    "material_evidence": {
                        "requirement_plan": {"requirement_groups": [requirement]}
                    }
                },
                "typed_fact_results": [fact_result],
                "typed_gaps": (
                    [
                        {
                            "fact_request_id": "TFR::ONE",
                            "metric_id": "revenue",
                            "gap_code": "metric_not_in_company_fact_mart",
                            "owning_stage": "S2",
                            "disposition": "return_typed_gap",
                        }
                    ]
                    if typed_state == "typed_gap"
                    else []
                ),
            }
        ],
    }
    evidence_pack = {
        "case_key": "DELL",
        "pack_payload_digest": "PACK",
        "evidence_items": [
            {
                "case_key": "DELL",
                "evidence_item_digest": "EVIDENCE",
                "source_record_id": "SOURCE",
                "target_id": "TARGET",
                "object_type": "claim",
                "publication_date": "2026-06-01",
                "writer_citable": True,
                "disposition": "accepted_direct_source_evidence",
                "slot_bindings": [
                    {
                        "slot_id": "operating_performance",
                        "facet_ids": ["reported_revenue"],
                    }
                ],
            }
        ],
    }
    supported = (
        ["AI server revenue contribution"]
        if review_state == "accepted"
        else []
    )
    unsupported = [] if review_state == "accepted" else [
        "AI server revenue contribution"
    ]
    review_plan = {
        "case_key": "DELL",
        "research_plan_digest": "PLAN",
        "scope_compilation_digest": "SCOPE",
        "evidence_pack_payload_digest": "PACK",
        "review_authority": {
            "candidate_text_may_be_promoted": False,
            "new_evidence_may_be_created": False,
            "numeric_authority_may_be_granted": False,
            "public_information_gap_may_be_declared": False,
            "owner_or_qualified_human_acceptance_claimed": False,
        },
        "requirement_reviews": [
            {
                "requirement_id": "MER::ONE",
                "request_id": "REQ::ONE",
                "facet_id": "reported_results",
                "role": "direct",
                "decision_state": review_state,
                "supported_product_ids": supported,
                "unsupported_product_ids": unsupported,
                "evidence_bindings": [
                    {
                        "evidence_item_digest": "EVIDENCE",
                        "required_slot_id": "operating_performance",
                        "required_facet_ids": ["reported_revenue"],
                        "require_exact_anchor": True,
                    }
                ],
                "decision_reason_zh": "已审证据绑定到本命题。",
                "claim_boundary_zh": (
                    "只能证明公司收入，不能证明产品归因。"
                    if review_state != "accepted"
                    else ""
                ),
                "review_authority": "provisional_project_audit",
            }
        ],
    }
    anchors = {
        "case_pack_bindings": {"DELL": {"pack_payload_digest": "PACK"}},
        "entries": [
            {
                "case_key": "DELL",
                "evidence_item_digest": "EVIDENCE",
                "review_status": "reviewed_exact_source_surface",
            }
        ]
    }
    return product, evidence_pack, review_plan, anchors


def _compile(*, typed_state: str = "resolved", review_state: str = "accepted"):
    product, pack, review, anchors = _inputs(
        typed_state=typed_state, review_state=review_state
    )
    return compile_integrated_requirement_readiness(
        product_projection=product,
        evidence_pack=pack,
        review_plan=review,
        anchor_catalog=anchors,
        recorded_at="2026-08-18T16:30:00+08:00",
    )


def test_reviewed_evidence_and_numeric_fact_are_ready_without_merging_authority() -> None:
    result = _compile()
    row = result["requirements"][0]
    assert row["integrated_state"] == "ready"
    assert row["fully_satisfied"] is True
    assert row["numeric_coverage"]["numeric_fact_authority"] is True
    assert row["evidence_bindings"][0]["numeric_authority"] is False
    assert result["authority"]["numeric_authority_merged_into_evidence"] is False


def test_s2_typed_gap_keeps_qualitative_research_consumable_but_not_complete() -> None:
    result = _compile(typed_state="typed_gap")
    row = result["requirements"][0]
    assert row["integrated_state"] == "qualitative_ready_s2_numeric_gap"
    assert row["research_consumable"] is True
    assert row["fully_satisfied"] is False
    assert row["numeric_coverage"]["metrics"][0]["owning_stage"] == "S2"


def test_bounded_evidence_is_consumable_with_claim_boundary() -> None:
    result = _compile(review_state="accepted_bounded")
    row = result["requirements"][0]
    assert row["integrated_state"] == "ready_with_claim_boundary"
    assert row["research_consumable"] is True
    assert row["fully_satisfied"] is False


def test_partial_evidence_does_not_become_pack_ready() -> None:
    result = _compile(review_state="partial")
    row = result["requirements"][0]
    assert row["integrated_state"] == "not_ready_s1_evidence"
    assert row["research_consumable"] is False
    assert result["requests"][0]["state"] == "not_ready"


def test_exact_anchor_requirement_fails_closed() -> None:
    product, pack, review, anchors = _inputs()
    anchors["entries"] = []
    with pytest.raises(
        IntegratedPackReadinessError,
        match="integrated_readiness_exact_anchor_missing",
    ):
        compile_integrated_requirement_readiness(
            product_projection=product,
            evidence_pack=pack,
            review_plan=review,
            anchor_catalog=anchors,
            recorded_at="2026-08-18T16:30:00+08:00",
        )


def test_future_or_wrong_facet_evidence_fails_closed() -> None:
    product, pack, review, anchors = _inputs()
    pack["evidence_items"][0]["publication_date"] = "2026-08-07"
    with pytest.raises(
        IntegratedPackReadinessError, match="integrated_readiness_future_evidence"
    ):
        compile_integrated_requirement_readiness(
            product_projection=product,
            evidence_pack=pack,
            review_plan=review,
            anchor_catalog=anchors,
            recorded_at="2026-08-18T16:30:00+08:00",
        )
    pack["evidence_items"][0]["publication_date"] = "2026-06-01"
    review["requirement_reviews"][0]["evidence_bindings"][0][
        "required_facet_ids"
    ] = ["reported_profitability"]
    with pytest.raises(
        IntegratedPackReadinessError,
        match="integrated_readiness_facet_binding_missing",
    ):
        compile_integrated_requirement_readiness(
            product_projection=product,
            evidence_pack=pack,
            review_plan=review,
            anchor_catalog=anchors,
            recorded_at="2026-08-18T16:30:00+08:00",
        )


def test_review_must_partition_every_natural_product_axis() -> None:
    product, pack, review, anchors = _inputs()
    review["requirement_reviews"][0]["supported_product_ids"] = []
    with pytest.raises(
        IntegratedPackReadinessError,
        match="integrated_readiness_product_partition_invalid",
    ):
        compile_integrated_requirement_readiness(
            product_projection=product,
            evidence_pack=pack,
            review_plan=review,
            anchor_catalog=anchors,
            recorded_at="2026-08-18T16:30:00+08:00",
        )


def test_candidate_like_evidence_digest_not_in_current_pack_cannot_be_promoted() -> None:
    product, pack, review, anchors = _inputs()
    review = deepcopy(review)
    review["requirement_reviews"][0]["evidence_bindings"][0][
        "evidence_item_digest"
    ] = "CANDIDATE"
    with pytest.raises(
        IntegratedPackReadinessError,
        match="integrated_readiness_evidence_not_in_pack",
    ):
        compile_integrated_requirement_readiness(
            product_projection=product,
            evidence_pack=pack,
            review_plan=review,
            anchor_catalog=anchors,
            recorded_at="2026-08-18T16:30:00+08:00",
        )


def test_review_authority_cannot_claim_runtime_promotion() -> None:
    product, pack, review, anchors = _inputs()
    review["review_authority"]["new_evidence_may_be_created"] = True
    with pytest.raises(
        IntegratedPackReadinessError,
        match="integrated_readiness_review_authority_invalid",
    ):
        compile_integrated_requirement_readiness(
            product_projection=product,
            evidence_pack=pack,
            review_plan=review,
            anchor_catalog=anchors,
            recorded_at="2026-08-18T16:30:00+08:00",
        )


def test_anchor_catalog_must_bind_the_same_pack() -> None:
    product, pack, review, anchors = _inputs()
    anchors["case_pack_bindings"]["DELL"]["pack_payload_digest"] = "OTHER"
    with pytest.raises(
        IntegratedPackReadinessError,
        match="integrated_readiness_anchor_pack_digest_mismatch",
    ):
        compile_integrated_requirement_readiness(
            product_projection=product,
            evidence_pack=pack,
            review_plan=review,
            anchor_catalog=anchors,
            recorded_at="2026-08-18T16:30:00+08:00",
        )
