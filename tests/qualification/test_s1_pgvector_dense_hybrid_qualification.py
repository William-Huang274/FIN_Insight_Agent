from __future__ import annotations

import pytest

from scripts.qualification.run_s1_pgvector_candidate_plane import QualificationError
from scripts.qualification.run_s1_pgvector_dense_hybrid_qualification import (
    _candidate_rows_from_scores,
    _parity_receipt,
    _route_summary,
    _rrf_equal,
    _rrf_reference,
    _tokenize,
    reciprocal_rank_fusion,
)


def test_tokenizer_matches_frozen_retrieval_contract() -> None:
    assert _tokenize("AI/ML R&D isn't A&B -- 2027!") == [
        "ai/ml",
        "r&d",
        "isn't",
        "a&b",
        "2027",
    ]


def test_candidate_score_tie_breaks_by_compiled_identity() -> None:
    objects = [
        {"compiled_object_id": "COBJ::bbbbbbbbbbbbbbbbbbbbbbbb"},
        {"compiled_object_id": "COBJ::aaaaaaaaaaaaaaaaaaaaaaaa"},
    ]

    rows = _candidate_rows_from_scores(
        objects=objects,
        eligible_indices=[0, 1],
        scores=[0.5, 0.5],
        limit=2,
    )

    assert [row["compiled_object_id"] for row in rows] == [
        "COBJ::aaaaaaaaaaaaaaaaaaaaaaaa",
        "COBJ::bbbbbbbbbbbbbbbbbbbbbbbb",
    ]


def test_rrf_matches_independent_reference_and_respects_union_limit() -> None:
    left = [
        {"compiled_object_id": "A", "score": 4.0},
        {"compiled_object_id": "B", "score": 3.0},
        {"compiled_object_id": "C", "score": 2.0},
    ]
    right = [
        {"compiled_object_id": "C", "score": 9.0},
        {"compiled_object_id": "B", "score": 8.0},
        {"compiled_object_id": "D", "score": 7.0},
    ]

    observed = reciprocal_rank_fusion((left, right), limit=3)
    expected = _rrf_reference(left, right, limit=3)

    assert _rrf_equal(observed, expected)
    assert len(observed) == 3
    assert observed[0]["compiled_object_id"] == "C"
    assert len({row["compiled_object_id"] for row in observed}) == 3


def test_rrf_rejects_duplicate_identity_inside_one_route() -> None:
    route = [
        {"compiled_object_id": "A", "score": 2.0},
        {"compiled_object_id": "A", "score": 1.0},
    ]

    with pytest.raises(QualificationError, match="rrf_route_duplicate:A"):
        reciprocal_rank_fusion((route,), limit=2)


def test_parity_receipt_requires_order_and_score_tolerance() -> None:
    reference = [
        {"compiled_object_id": "A", "score": 0.5},
        {"compiled_object_id": "B", "score": 0.4},
    ]
    within = [
        {"compiled_object_id": "A", "score": 0.500001},
        {"compiled_object_id": "B", "score": 0.400001},
    ]
    reordered = list(reversed(within))

    assert _parity_receipt(reference, within)["ordered_ids_exact"] is True
    assert _parity_receipt(reference, within)["score_delta_within_1e_5"] is True
    assert _parity_receipt(reference, reordered)["ordered_ids_exact"] is False


def test_route_summary_keeps_eligible_misses_in_mrr_denominator() -> None:
    rows = [
        {"qrel_id": "q1", "eligible_target_count": 1, "target_rank_at_64": 2},
        {"qrel_id": "q2", "eligible_target_count": 2, "target_rank_at_64": None},
        {"qrel_id": "q3", "eligible_target_count": 0, "target_rank_at_64": None},
    ]

    summary = _route_summary(rows)

    assert summary["eligible_qrel_count"] == 2
    assert summary["target_in_top_64"] == 1
    assert summary["mean_reciprocal_rank_at_64"] == 0.25
    assert summary["zero_eligible_target_qrel_ids"] == ["q3"]
