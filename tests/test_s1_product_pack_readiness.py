from __future__ import annotations

from copy import deepcopy

from retrieval.product_pack_readiness import (
    compile_product_candidate_decision_ledger,
    compile_product_pack_readiness,
)


def _pack() -> dict[str, object]:
    return {
        "case_key": "DELL",
        "pack_payload_digest": "a" * 64,
        "retrieval_result_digest": "b" * 64,
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
                "compiled_object_id": "OBJ-1",
                "disposition": "accepted_direct_evidence",
                "writer_citable": True,
                "evidence_item_digest": "c" * 64,
                "source_record_id": "SRC-1",
                "source_material_ref": "MAT-1",
                "publication_date": "2026-05-28",
                "source_reporting_period_end": "2026-05-01",
                "relationship_directions": ["subject_self_disclosure"],
                "slot_bindings": [
                    {
                        "slot_id": "operating_performance",
                        "facet_ids": ["reported_results"],
                    }
                ],
            }
        ],
        "residual_gaps": [
            {
                "gap_id": "GAP-1",
                "gap_code": "missing_bridge",
                "slot_id": "operating_performance",
                "business_reason_zh": "尚缺产品到利润桥。",
                "attempted_lane_ids": ["LANE-1"],
            }
        ],
    }


def _request_result(*, requirement_complete: bool = True) -> dict[str, object]:
    request = {
        "request_id": "REQ-1",
        "case_key": "DELL",
        "subject_ticker": "DELL",
        "research_as_of": "2026-08-06",
        "period": {"start_date": "2026-01-01", "end_date": "2026-08-06"},
    }
    seed = {
        "compiled_object_id": "OBJ-1",
        "source_record_id": "SRC-1",
        "lineage_source_record_ids": ["SRC-1"],
        "ticker": "DELL",
        "source_type": "10-Q",
        "source_tier": "primary_sec_filing",
        "publication_date": "2026-05-28",
        "period_end": "2026-05-01",
        "object_kind": "claim",
        "rank_trace": {
            "raw_union_rank": 1,
            "financial_rank": 1,
            "review_priority_rank": 1,
            "final_output_rank": 1,
        },
        "route_membership": ["bm25_lexical"],
        "material_alignment_state": "selected_for_material_review",
        "material_reserved_for_requirement": requirement_complete,
        "selected_requirement_ids": ["MER-1"] if requirement_complete else [],
        "evidence_role": {"compatibility": "compatible", "advisory_only": True},
        "candidate_not_evidence": True,
        "candidate_text_included": False,
        "evidence_promoted": False,
        "numeric_authority": False,
    }
    return {
        "request": request,
        "request_digest": "d" * 64,
        "lanes": [
            {
                "lane": {
                    "slot_id": "operating_performance",
                    "facet_id": "reported_results",
                    "business_question_zh": "当期业绩如何？",
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
            "summary": {"union_count_before_source_quota": 1},
            "candidate_decision_seed": [seed],
            "material_evidence": {
                "runtime_scope_ready": True,
                "requirement_plan": {
                    "requirement_groups": [
                        {
                            "requirement_id": "MER-1",
                            "facet_id": "reported_results",
                            "role": "direct",
                        }
                    ]
                },
                "selection": {
                    "requirement_receipts": [
                        {
                            "requirement_id": "MER-1",
                            "complete": requirement_complete,
                            "selected_candidate_ids": (
                                ["OBJ-1"] if requirement_complete else []
                            ),
                        }
                    ]
                },
            },
        },
        "typed_fact_results": [
            {
                "fact_request_id": "TFR-1",
                "metric_id": "revenue",
                "status": "resolved",
                "facts": [
                    {
                        "numeric_fact_id": "NF-1",
                        "numeric_fact_authority": True,
                    }
                ],
            }
        ],
        "route_execution_truth": {
            "narrative_route_requests": [
                {
                    "routes": [
                        {
                            "declared_route": "bm25_lexical",
                            "execution_state": "executed",
                        },
                        {
                            "declared_route": "dense_embedding",
                            "execution_state": "executed",
                        },
                    ]
                }
            ]
        },
        "candidate_ceiling_provenance": {
            "source_object_index_state": {
                "all_source_records_lineage_bound": True,
                "compiled_object_count": 100,
            },
            "hybrid_candidate_ceiling": {
                "execution_state": "executed",
                "union_ceiling_reached": False,
            },
        },
    }


def _compile(request_result: dict[str, object], pack: dict[str, object]) -> dict[str, object]:
    ledger = compile_product_candidate_decision_ledger(
        request_result=request_result,
        evidence_pack=pack,
        recorded_at="2026-08-18",
    )
    return compile_product_pack_readiness(
        product_projection={
            "case_key": "DELL",
            "objective": {"research_as_of": "2026-08-06"},
            "request_results": [request_result],
        },
        evidence_pack=pack,
        candidate_decision_ledgers=[ledger],
        recorded_at="2026-08-18",
    )


def test_product_pack_ready_only_reuses_exact_reviewed_evidence() -> None:
    result = _compile(_request_result(), _pack())

    assert result["readiness_state"] == "ready_for_current_scope"
    assert result["accepted_reviewed_evidence_digests"] == ["c" * 64]
    assert result["candidate_count"] == 1
    assert result["requests"][0]["numeric_authority_state"]["state"] == "resolved"
    assert result["checks"]["candidate_text_promoted"] is False
    assert result["checks"]["S1_qualified_stable"] is False
    assert result["declared_pack_gap_receipts"][0][
        "eligible_as_true_public_information_gap"
    ] is False


def test_incomplete_candidate_requirement_is_not_public_information_gap() -> None:
    result = _compile(_request_result(requirement_complete=False), _pack())

    assert result["readiness_state"] == "blocked_by_candidate_coverage"
    receipt = result["gap_eligibility_receipts"][0]
    assert receipt["earliest_responsible_layer"] == (
        "S1_query_candidate_coverage_or_evidence_role_binding"
    )
    assert receipt["eligible_as_true_public_information_gap"] is False
    assert "official_or_external_supplement_route_not_exhausted" in receipt[
        "blockers"
    ]


def test_exact_source_with_wrong_facet_blocks_evidence_admission() -> None:
    pack = _pack()
    pack["evidence_items"][0]["slot_bindings"][0]["facet_ids"] = ["other"]
    result = _compile(_request_result(), pack)

    assert result["readiness_state"] == "blocked_by_evidence_admission"
    assert result["requests"][0]["candidate_decision_counts"][
        "needs_human_review"
    ] == 1
    assert result["gap_eligibility_receipts"][0][
        "earliest_responsible_layer"
    ] == "S1_evidence_admission"


def test_explicit_scope_pending_remains_candidate_audit_only() -> None:
    request_result = _request_result()
    request_result["hybrid_object_retrieval"]["material_evidence"][
        "runtime_scope_ready"
    ] = False
    result = _compile(request_result, _pack())

    assert result["readiness_state"] == (
        "candidate_audit_only_explicit_scope_pending"
    )
    assert result["gap_eligibility_receipts"][0][
        "earliest_responsible_layer"
    ] == "S3_research_scope"


def test_one_reviewed_item_cannot_satisfy_an_unbound_sibling_requirement() -> None:
    request_result = _request_result()
    seed = request_result["hybrid_object_retrieval"]["candidate_decision_seed"][0]
    seed["selected_requirement_ids"] = ["MER-1", "MER-2"]
    material = request_result["hybrid_object_retrieval"]["material_evidence"]
    material["requirement_plan"]["requirement_groups"].append(
        {"requirement_id": "MER-2", "facet_id": "reported_results", "role": "counter"}
    )
    material["selection"]["requirement_receipts"].append(
        {
            "requirement_id": "MER-2",
            "complete": True,
            "selected_candidate_ids": ["OBJ-1"],
        }
    )
    pack = _pack()
    pack["evidence_items"][0]["slot_bindings"][0]["requirement_ids"] = [
        "MER-1"
    ]

    ledger = compile_product_candidate_decision_ledger(
        request_result=request_result,
        evidence_pack=pack,
        recorded_at="2026-08-19",
    )
    result = compile_product_pack_readiness(
        product_projection={
            "case_key": "DELL",
            "objective": {"research_as_of": "2026-08-06"},
            "request_results": [request_result],
        },
        evidence_pack=pack,
        candidate_decision_ledgers=[ledger],
        recorded_at="2026-08-19",
    )

    decision = ledger["decisions"][0]
    assert decision["accepted_evidence_by_requirement"] == {
        "MER-1": ["c" * 64]
    }
    requirement_states = {
        row["requirement_id"]: row["readiness_state"]
        for row in result["requests"][0]["requirements"]
    }
    assert requirement_states == {
        "MER-1": "ready_for_current_scope",
        "MER-2": "blocked_by_evidence_admission",
    }
    assert result["readiness_state"] == "blocked_by_evidence_admission"


def test_multi_requirement_reuse_without_explicit_binding_fails_closed() -> None:
    request_result = _request_result()
    seed = request_result["hybrid_object_retrieval"]["candidate_decision_seed"][0]
    seed["selected_requirement_ids"] = ["MER-1", "MER-2"]

    ledger = compile_product_candidate_decision_ledger(
        request_result=request_result,
        evidence_pack=_pack(),
        recorded_at="2026-08-19",
    )

    assert ledger["decision_counts"]["accepted"] == 0
    assert ledger["decision_counts"]["needs_human_review"] == 1
    assert ledger["accepted_evidence_by_requirement"] == {}
    assert "reviewed_evidence_requirement_binding_missing_or_ambiguous" in ledger[
        "decisions"
    ][0]["reason_codes"]
