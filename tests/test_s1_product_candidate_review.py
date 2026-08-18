from __future__ import annotations

from copy import deepcopy

import pytest

from retrieval.product_candidate_review import (
    ProductCandidateReviewError,
    compile_product_candidate_review_packet,
)
from retrieval.product_pack_readiness import (
    compile_product_candidate_decision_ledger,
)


def _request_result(*, scope_ready: bool = True) -> dict[str, object]:
    seed = {
        "compiled_object_id": "OBJ-1",
        "source_record_id": "SRC-1",
        "lineage_source_record_ids": ["SRC-1"],
        "ticker": "MU",
        "source_type": "8-K",
        "source_tier": "company_authored_unaudited_sec_filing",
        "publication_date": "2026-06-24",
        "period_end": "2026-06-24",
        "object_kind": "claim",
        "rank_trace": {
            "raw_union_rank": 3,
            "financial_rank": 2,
            "review_priority_rank": 1,
            "final_output_rank": 1,
        },
        "route_membership": ["bm25_lexical", "qwen3_embedding_0_6b_dense"],
        "material_alignment_state": "selected_for_material_review",
        "material_reserved_for_requirement": True,
        "selected_requirement_ids": ["MER-1"],
        "evidence_role": {
            "compatibility": "compatible",
            "labels": ["direct_demand_signal"],
            "reason_codes": ["request_bound_observed_demand_surface"],
            "advisory_only": True,
        },
        "candidate_not_evidence": True,
        "candidate_text_included": False,
        "evidence_promoted": False,
        "numeric_authority": False,
    }
    return {
        "request": {
            "request_id": "REQ-1",
            "case_key": "MU",
            "subject_ticker": "MU",
            "research_as_of": "2026-08-06",
            "period": {"start_date": "2025-01-01", "end_date": "2026-08-06"},
        },
        "request_digest": "a" * 64,
        "lanes": [
            {
                "lane": {
                    "slot_id": "demand_volume_quality",
                    "facet_id": "orders_and_backlog",
                    "business_question_zh": "HBM 需求是否已有可验证承诺？",
                    "evidence_owner_tickers": ["MU"],
                    "source_types": ["8-K"],
                    "owner_queries": [
                        {
                            "evidence_owner_ticker": "MU",
                            "relationship_direction": "subject_self_disclosure",
                        }
                    ],
                }
            }
        ],
        "hybrid_object_retrieval": {
            "result_digest": "b" * 64,
            "summary": {"union_count_before_source_quota": 1},
            "candidate_decision_seed": [seed],
            "material_evidence": {
                "runtime_scope_ready": scope_ready,
                "requirement_plan": {
                    "requirement_groups": [
                        {
                            "requirement_id": "MER-1",
                            "facet_id": "orders_and_backlog",
                            "role": "direct",
                            "product_ids": ["HBM4 shipment and capacity"],
                            "metric_ids": ["shipments"],
                            "target_entities": ["MU"],
                        }
                    ]
                },
                "selection": {
                    "selected_candidate_ids": ["OBJ-1"],
                    "requirement_receipts": [
                        {
                            "requirement_id": "MER-1",
                            "complete": True,
                            "selected_candidate_ids": ["OBJ-1"],
                            "missing_required_product_ids": [],
                            "missing_required_metric_ids": [],
                        }
                    ],
                },
            },
        },
    }


def _pack(*, exact_object: bool = False) -> dict[str, object]:
    return {
        "case_key": "MU",
        "pack_payload_digest": "c" * 64,
        "source_materials": [
            {
                "material_ref": "MAT-1",
                "evidence_owner_ticker": "MU",
                "source_type": "8-K",
                "period_end": "2026-06-24",
            }
        ],
        "evidence_items": [
            {
                "case_key": "MU",
                "compiled_object_id": "OBJ-1" if exact_object else "OBJ-OLD",
                "disposition": "accepted_direct_evidence",
                "writer_citable": True,
                "evidence_item_digest": "d" * 64,
                "source_record_id": "SRC-1",
                "source_material_ref": "MAT-1",
                "publication_date": "2026-06-24",
                "source_reporting_period_end": "2026-06-24",
                "relationship_directions": ["subject_self_disclosure"],
                "slot_bindings": [
                    {
                        "slot_id": "demand_volume_quality",
                        "facet_ids": ["orders_and_backlog"],
                    }
                ],
            }
        ],
        "residual_gaps": [],
    }


def _objects() -> dict[str, dict[str, object]]:
    return {
        "OBJ-1": {
            "compiled_object_id": "OBJ-1",
            "candidate_not_evidence": True,
            "evidence_promoted": False,
            "numeric_authority": False,
            "object_kind": "claim",
            "lineage_source_record_ids": ["SRC-1"],
            "model_text": (
                "HBM4 is in high-volume shipments for our lead customer's "
                "platform, and samples shipped to multiple end-customers."
            ),
            "base_object_view": {
                "source_record_id": "SRC-1",
                "source_record_digest": "e" * 64,
                "surface_digest": "f" * 64,
            },
        }
    }


def _sources() -> dict[str, dict[str, object]]:
    return {
        "SRC-1": {
            "evidence_id": "SRC-1",
            "company": "Micron Technology, Inc.",
            "ticker": "MU",
            "source_type": "8-K",
            "source_tier": "company_authored_unaudited_sec_filing",
            "publication_date": "2026-06-24",
            "period_end": "2026-06-24",
            "section": "Product highlights",
            "subsection": "HBM4",
            "source_url": "https://www.sec.gov/example",
            "license_scope": "public_official_source_research_use",
            "redistributable": False,
        }
    }


def _compile(*, exact_object: bool = False, scope_ready: bool = True) -> dict[str, object]:
    request_result = _request_result(scope_ready=scope_ready)
    ledger = compile_product_candidate_decision_ledger(
        request_result=request_result,
        evidence_pack=_pack(exact_object=exact_object),
        recorded_at="2026-08-19",
    )
    return compile_product_candidate_review_packet(
        product_projection={
            "case_key": "MU",
            "request_results": [request_result],
        },
        candidate_decision_ledgers=[ledger],
        compiled_objects_by_id=_objects(),
        source_records_by_id=_sources(),
        recorded_at="2026-08-19",
        excerpt_char_limit=120,
    )


def test_new_official_candidate_is_reviewable_but_never_promoted() -> None:
    result = _compile()

    assert result["review_item_count"] == 1
    assert result["human_review_required_count"] == 1
    item = result["requests"][0]["review_items"][0]
    assert item["issue_classes"] == ["reviewed_pack_exact_object_binding"]
    assert item["next_legal_action"] == "review_exact_object_and_pack_binding"
    assert item["source"]["bounded_excerpt"].startswith("HBM4 is in high-volume")
    assert item["source"]["redistributable"] is False
    assert item["candidate_is_not_evidence"] is True
    assert item["candidate_text_promoted"] is False
    assert item["new_evidence_created"] is False
    assert result["authority"]["S1_qualification_claimed"] is False


def test_exact_reviewed_object_is_visible_as_reuse_not_new_evidence() -> None:
    result = _compile(exact_object=True)

    item = result["requests"][0]["review_items"][0]
    assert item["decision_state"] == "accepted"
    assert item["issue_classes"] == ["existing_reviewed_evidence_reuse"]
    assert item["human_review_required"] is False
    assert item["new_evidence_created"] is False


def test_scope_pending_case_does_not_surface_candidate_excerpts() -> None:
    result = _compile(scope_ready=False)

    assert result["review_item_count"] == 0
    assert result["requests"][0]["review_items"] == []


def test_non_http_source_url_fails_closed() -> None:
    request_result = _request_result()
    ledger = compile_product_candidate_decision_ledger(
        request_result=request_result,
        evidence_pack=_pack(),
        recorded_at="2026-08-19",
    )
    sources = deepcopy(_sources())
    sources["SRC-1"]["source_url"] = "file:///private/capture.json"

    with pytest.raises(
        ProductCandidateReviewError,
        match="product_candidate_review_source_url_invalid",
    ):
        compile_product_candidate_review_packet(
            product_projection={
                "case_key": "MU",
                "request_results": [request_result],
            },
            candidate_decision_ledgers=[ledger],
            compiled_objects_by_id=_objects(),
            source_records_by_id=sources,
            recorded_at="2026-08-19",
        )
