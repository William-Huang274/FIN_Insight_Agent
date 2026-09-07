from __future__ import annotations

import pytest

from retrieval.qualification_ranking import (
    QualificationRankingError,
    aggregate_relevant_pair_scores,
    build_relevant_pair_manifest,
    select_candidate_relevant_need_ids,
)
from retrieval.retrieval_need import RetrievalNeed


def _need(need_id: str) -> RetrievalNeed:
    return RetrievalNeed(
        need_id=need_id,
        need_kind="product",
        facet_id="reported_results",
        evidence_owner_ticker="COST",
        relationship_direction="subject_self_disclosure",
        intent_terms=(need_id,),
        role_cues=("result",),
        exact_phrases=(),
        lexical_query=need_id,
        semantic_query=f"semantic {need_id}",
        constraint_digest="x" * 64,
    )


def test_relevant_need_selection_prefers_typed_routes_and_is_bounded() -> None:
    rows = [
        {"route_id": "qwen3_embedding_0_6b_dense", "need_id": "N1", "rank": 1},
        {"route_id": "typed_metric_row_exact", "need_id": "N2", "rank": 8},
        {"route_id": "bm25_need_lexical", "need_id": "N3", "rank": 2},
        {"route_id": "typed_exact_phrase", "need_id": "N4", "rank": 1},
        {"route_id": "bm25_need_lexical", "need_id": "N3", "rank": 1},
    ]
    assert select_candidate_relevant_need_ids(
        rows, allowed_need_ids={"N1", "N2", "N3", "N4"}, maximum=3
    ) == ("N2", "N4", "N3")


def test_pair_manifest_has_no_candidate_all_need_cartesian_product() -> None:
    needs = {key: _need(key) for key in ("N1", "N2", "N3", "N4")}
    pairs, bindings = build_relevant_pair_manifest(
        candidate_ids=("C1", "C2"),
        route_membership_by_id={
            "C1": [
                {"route_id": "bm25_need_lexical", "need_id": "N1", "rank": 1},
                {"route_id": "bge_m3_dense", "need_id": "N2", "rank": 1},
                {"route_id": "bge_m3_dense", "need_id": "N3", "rank": 2},
            ],
            "C2": [
                {"route_id": "typed_exact_phrase", "need_id": "N4", "rank": 1}
            ],
        },
        needs_by_id=needs,
        objects_by_id={"C1": {"model_text": "doc one"}, "C2": {"model_text": "doc two"}},
        maximum_needs_per_candidate=2,
    )
    assert len(pairs) == 3
    assert [(row.candidate_id, row.need_id) for row in bindings] == [
        ("C1", "N1"),
        ("C1", "N2"),
        ("C2", "N4"),
    ]


def test_each_reranker_can_choose_its_own_best_relevant_need() -> None:
    needs = {key: _need(key) for key in ("N1", "N2")}
    _, bindings = build_relevant_pair_manifest(
        candidate_ids=("C1",),
        route_membership_by_id={
            "C1": [
                {"route_id": "bm25_need_lexical", "need_id": "N1", "rank": 1},
                {"route_id": "bge_m3_dense", "need_id": "N2", "rank": 1},
            ]
        },
        needs_by_id=needs,
        objects_by_id={"C1": {"model_text": "doc"}},
        maximum_needs_per_candidate=2,
    )
    bge, bge_best = aggregate_relevant_pair_scores(
        candidate_ids=("C1",), bindings=bindings, scores=(0.9, 0.1)
    )
    qwen, qwen_best = aggregate_relevant_pair_scores(
        candidate_ids=("C1",), bindings=bindings, scores=(0.2, 0.8)
    )
    assert bge[0].score == pytest.approx(0.9)
    assert qwen[0].score == pytest.approx(0.8)
    assert bge_best == {"C1": "N1"}
    assert qwen_best == {"C1": "N2"}


def test_pair_manifest_fails_when_candidate_has_no_recalled_need() -> None:
    with pytest.raises(
        QualificationRankingError, match="qualification_pair_relevant_need_missing"
    ):
        build_relevant_pair_manifest(
            candidate_ids=("C1",),
            route_membership_by_id={"C1": []},
            needs_by_id={"N1": _need("N1")},
            objects_by_id={"C1": {"model_text": "doc"}},
            maximum_needs_per_candidate=3,
        )
