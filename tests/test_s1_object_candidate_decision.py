from __future__ import annotations

from copy import deepcopy

from retrieval.candidate_decision import (
    compile_object_candidate_decision_ledger,
    compile_object_coverage_state,
    compile_object_pack_readiness,
    compile_object_workbench_projection,
)
from retrieval.product_pack_readiness import compile_product_candidate_decision_ledger
from retrieval.query_plan import OwnerQuery, QueryLane


def _lane() -> QueryLane:
    return QueryLane(
        lane_id="LANE-1",
        slot_id="operating_performance",
        facet_id="reported_results",
        business_question_zh="当期业绩如何？",
        execution_mode="local",
        subject_ticker="DELL",
        evidence_owner_tickers=("DELL",),
        relationship_constraints=("subject_self_disclosure",),
        publication_date_lte="2026-08-06",
        source_types=("10-Q",),
        required_source_roles=("issuer_disclosure",),
        exact_queries=(),
        lexical_query="reported results",
        lexical_tokens=("reported", "results"),
        owner_queries=(
            OwnerQuery(
                evidence_owner_ticker="DELL",
                relationship_direction="subject_self_disclosure",
                lexical_query="reported results",
                lexical_tokens=("reported", "results"),
                anchor_token_groups=(),
            ),
        ),
        semantic_query="reported results",
        graph_constraints=(),
        forbidden_expansions=(),
        candidate_budget=10,
    )


def _request() -> dict[str, object]:
    return {
        "request_id": "REQ-1",
        "case_key": "DELL",
        "subject_ticker": "DELL",
        "research_as_of": "2026-08-06",
        "period": {"start_date": "2026-01-01", "end_date": "2026-08-06"},
        "metric_intents": ["revenue"],
        "product_intents": [],
        "stop_condition": "return evidence or a typed gap",
    }


def _object(object_id: str, source_id: str, *, publication_date: str = "2026-05-28") -> dict[str, object]:
    return {
        "compiled_object_id": object_id,
        "candidate_not_evidence": True,
        "evidence_promoted": False,
        "numeric_authority": False,
        "object_kind": "claim",
        "lineage_source_record_ids": [source_id],
        "base_object_view": {
            "source_record_id": source_id,
            "ticker": "DELL",
            "source_type": "10-Q",
            "publication_date": publication_date,
        },
    }


def _pack() -> dict[str, object]:
    return {
        "case_key": "DELL",
        "pack_payload_digest": "a" * 64,
        "source_materials": [
            {
                "material_ref": "MAT-1",
                "evidence_owner_ticker": "DELL",
                "source_type": "10-Q",
                "period_end": "2026-05-01",
            }
        ],
        "evidence_items": [
            {
                "case_key": "DELL",
                "writer_citable": True,
                "evidence_item_digest": "b" * 64,
                "source_record_id": "SRC-1",
                "source_material_ref": "MAT-1",
                "publication_date": "2026-05-28",
                "source_reporting_period_end": "2026-05-01",
                "relationship_directions": ["subject_self_disclosure"],
                "slot_bindings": [{"slot_id": "operating_performance"}],
            }
        ],
        "residual_gaps": [
            {
                "gap_id": "GAP-1",
                "gap_code": "missing_bridge",
                "slot_id": "operating_performance",
                "business_reason_zh": "尚缺产品到利润桥。",
            }
        ],
    }


def _product_request_result() -> dict[str, object]:
    request = _request()
    return {
        "request": request,
        "request_digest": "d" * 64,
        "lanes": [
            {
                "lane": {
                    "slot_id": "operating_performance",
                    "facet_id": "reported_results",
                    "evidence_owner_tickers": ["DELL"],
                    "source_types": ["10-Q"],
                    "owner_queries": [
                        {
                            "evidence_owner_ticker": "DELL",
                            "relationship_direction": "subject_self_disclosure",
                        }
                    ],
                }
            }
        ],
        "hybrid_object_retrieval": {
            "result_digest": "e" * 64,
            "summary": {"union_count_before_source_quota": 4},
            "candidate_decision_seed": [
                _product_seed("OBJ-1", "SRC-1", "selected_for_material_review", 1),
                _product_seed("OBJ-SIBLING", "SRC-1", "selected_for_material_review", 2),
                _product_seed(
                    "OBJ-EXCLUDED",
                    "SRC-3",
                    "excluded_by_material_requirement_alignment",
                    3,
                ),
                _product_seed("OBJ-4", "SRC-4", "eligible_not_selected", 4),
            ],
        },
    }


def _product_seed(
    object_id: str, source_id: str, alignment: str, rank: int
) -> dict[str, object]:
    return {
        "compiled_object_id": object_id,
        "source_record_id": source_id,
        "lineage_source_record_ids": [source_id],
        "ticker": "DELL",
        "source_type": "10-Q",
        "source_tier": "primary_sec_filing",
        "publication_date": "2026-05-28",
        "period_end": "2026-05-01",
        "object_kind": "claim",
        "rank_trace": {
            "raw_union_rank": rank,
            "financial_rank": rank,
            "review_priority_rank": rank,
            "final_output_rank": rank if rank < 4 else None,
        },
        "route_membership": ["bm25_lexical"],
        "material_alignment_state": alignment,
        "material_reserved_for_requirement": rank == 1,
        "selected_requirement_ids": ["MER-1"] if rank == 1 else [],
        "evidence_role": {"compatibility": "compatible", "advisory_only": True},
        "candidate_not_evidence": True,
        "candidate_text_included": False,
        "evidence_promoted": False,
        "numeric_authority": False,
    }


def _product_pack() -> dict[str, object]:
    pack = deepcopy(_pack())
    item = pack["evidence_items"][0]
    item["compiled_object_id"] = "OBJ-1"
    item["disposition"] = "accepted_direct_evidence"
    item["slot_bindings"] = [
        {"slot_id": "operating_performance", "facet_ids": ["reported_results"]}
    ]
    return pack


def test_reviewed_source_without_exact_object_relation_needs_review() -> None:
    objects = {"OBJ-1": _object("OBJ-1", "SRC-1")}
    ledger = compile_object_candidate_decision_ledger(
        request=_request(),
        lane=_lane(),
        ranked_object_ids=("OBJ-1",),
        objects_by_id=objects,
        reviewed_relations={},
        evidence_pack=_pack(),
        recorded_at="2026-08-17",
    )

    assert ledger["decision_counts"] == {
        "accepted": 0,
        "rejected": 0,
        "unjudged": 0,
        "needs_review": 1,
    }
    assert ledger["decisions"][0]["reason_codes"] == [
        "reviewed_source_lineage_without_object_relation"
    ]
    assert ledger["accepted_evidence_item_digests"] == []


def test_positive_object_and_reviewed_pack_binding_can_reuse_evidence_only() -> None:
    objects = {"OBJ-1": _object("OBJ-1", "SRC-1")}
    ledger = compile_object_candidate_decision_ledger(
        request=_request(),
        lane=_lane(),
        ranked_object_ids=("OBJ-1",),
        objects_by_id=objects,
        reviewed_relations={"OBJ-1": {"judgement": "positive"}},
        evidence_pack=_pack(),
        recorded_at="2026-08-17",
    )

    assert ledger["decision_counts"]["accepted"] == 1
    assert ledger["accepted_compiled_object_ids"] == ["OBJ-1"]
    assert ledger["accepted_evidence_item_digests"] == ["b" * 64]
    assert ledger["decisions"][0]["candidate_text_promoted"] is False
    assert ledger["decisions"][0]["runtime_evidence_promotion"] is False

    coverage = compile_object_coverage_state(
        request=_request(),
        lane=_lane(),
        decision_ledger=ledger,
        evidence_pack=_pack(),
        recorded_at="2026-08-17",
    )
    readiness = compile_object_pack_readiness(
        coverage=coverage,
        decision_ledger=ledger,
        evidence_pack=_pack(),
        pack_artifact_digest="c" * 64,
        recorded_at="2026-08-17",
    )
    workbench = compile_object_workbench_projection(
        decision_ledger=ledger,
        coverage=coverage,
        readiness=readiness,
        recorded_at="2026-08-17",
    )

    assert readiness["readiness_state"] == (
        "ready_for_development_replay_not_runtime_promotion"
    )
    assert readiness["checks"]["runtime_evidence_promotion_authorized"] is False
    assert workbench["decision_rows"][0]["compiled_object_id"] == "OBJ-1"
    assert workbench["coverage_summary"]["unresolved_gap_count"] == 1


def test_hard_negative_stays_rejected_even_when_source_is_reviewed() -> None:
    objects = {"OBJ-1": _object("OBJ-1", "SRC-1")}
    ledger = compile_object_candidate_decision_ledger(
        request=_request(),
        lane=_lane(),
        ranked_object_ids=("OBJ-1",),
        objects_by_id=objects,
        reviewed_relations={"OBJ-1": {"judgement": "hard_negative"}},
        evidence_pack=_pack(),
        recorded_at="2026-08-17",
    )

    assert ledger["decision_counts"]["rejected"] == 1
    assert ledger["accepted_evidence_item_digests"] == []
    assert ledger["decisions"][0]["reason_codes"] == [
        "exact_object_reviewed_hard_negative"
    ]


def test_exact_compiled_object_binding_cannot_authorize_sibling_claim() -> None:
    objects = {"OBJ-SIBLING": _object("OBJ-SIBLING", "SRC-1")}
    pack = _pack()
    pack["evidence_items"][0]["compiled_object_id"] = "OBJ-ORIGINAL"

    ledger = compile_object_candidate_decision_ledger(
        request=_request(),
        lane=_lane(),
        ranked_object_ids=("OBJ-SIBLING",),
        objects_by_id=objects,
        reviewed_relations={"OBJ-SIBLING": {"judgement": "positive"}},
        evidence_pack=pack,
        recorded_at="2026-08-18",
    )

    assert ledger["decision_counts"]["accepted"] == 0
    assert ledger["decision_counts"]["needs_review"] == 1
    assert ledger["decisions"][0]["reason_codes"] == [
        "positive_development_object_not_bound_to_current_reviewed_pack"
    ]


def test_product_decision_materializes_full_union_without_new_promotion() -> None:
    ledger = compile_product_candidate_decision_ledger(
        request_result=_product_request_result(),
        evidence_pack=_product_pack(),
        recorded_at="2026-08-18",
    )

    assert ledger["candidate_count"] == 4
    assert ledger["decision_counts"] == {
        "accepted": 1,
        "rejected": 1,
        "unjudged": 1,
        "needs_human_review": 1,
    }
    assert ledger["accepted_compiled_object_ids"] == ["OBJ-1"]
    assert ledger["accepted_evidence_item_digests"] == ["b" * 64]
    accepted = next(
        row for row in ledger["decisions"] if row["compiled_object_id"] == "OBJ-1"
    )
    assert accepted["decision_authority"] == "current_reviewed_pack_exact_object_reuse"
    assert accepted["candidate_text_promoted"] is False
    assert accepted["new_evidence_created"] is False
    assert all(row["numeric_authority"] is False for row in ledger["decisions"])


def test_product_decision_facet_mismatch_fails_closed() -> None:
    pack = _product_pack()
    pack["evidence_items"][0]["slot_bindings"][0]["facet_ids"] = [
        "unrelated_facet"
    ]

    ledger = compile_product_candidate_decision_ledger(
        request_result=_product_request_result(),
        evidence_pack=pack,
        recorded_at="2026-08-18",
    )

    assert ledger["decision_counts"]["accepted"] == 0
    original = next(
        row for row in ledger["decisions"] if row["compiled_object_id"] == "OBJ-1"
    )
    assert original["decision_state"] == "needs_human_review"
    assert "reviewed_item_facet_not_bound_to_current_request" in original[
        "reason_codes"
    ]
