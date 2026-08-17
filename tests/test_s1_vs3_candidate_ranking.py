from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

from retrieval.candidate_ranking import (
    NeedRouteRanking,
    aggregate_all_need_pair_scores,
    evaluate_ranking,
    fuse_need_rankings,
    fuse_need_rankings_with_route_floors,
    rank_authority_indices,
    rank_need_intent_alias_routes,
    rank_need_lexical_routes,
    rank_need_metric_row_routes,
    ranking_candidate_order_stable,
    role_guarded_primary_ranking,
    route_membership,
)
from retrieval.object_retrieval_comparison import CandidateScore
from retrieval.retrieval_need import RetrievalNeed


def _candidate_ranking_runner():
    path = (
        Path(__file__).resolve().parents[1]
        / "scripts/data_retrieval/run_s1_candidate_ranking.py"
    )
    spec = importlib.util.spec_from_file_location(
        "s1_candidate_ranking_cuda_contract_test", path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_learned_ranking_fails_closed_when_cuda_is_unavailable(monkeypatch) -> None:
    import torch

    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    with pytest.raises(RuntimeError, match="candidate_ranking_cuda_required"):
        _candidate_ranking_runner()._required_cuda_execution_receipt()


def _need(identity: str, query: str, phrase: str = "") -> RetrievalNeed:
    return RetrievalNeed(
        need_id=identity,
        need_kind="metric",
        facet_id="pricing_and_mix",
        evidence_owner_ticker="DELL",
        relationship_direction="subject_self_disclosure",
        intent_terms=(query,),
        role_cues=("pricing", "mix"),
        exact_phrases=(phrase,) if phrase else (),
        lexical_query=query,
        semantic_query=query,
        constraint_digest="constraint",
    )


def _object(identity: str, text: str) -> dict:
    return {"compiled_object_id": identity, "model_text": text}


def _typed_object(
    identity: str,
    text: str,
    *,
    kind: str,
    publication_date: str = "2026-01-01",
    metric_label: str = "",
    source_type: str = "10-Q",
    parent_section: str = "Item 1. Financial Statements",
) -> dict:
    return {
        "compiled_object_id": identity,
        "model_text": text,
        "object_kind": kind,
        "base_object_view": {
            "publication_date": publication_date,
            "source_type": source_type,
        },
        "structured_projection": {
            "metric_row_label": metric_label,
            "parent_section": parent_section,
        },
    }


def test_need_lexical_routes_keep_exact_and_bm25_separate() -> None:
    objects = [
        _object("a", "AI server profitability was in line with our target"),
        _object("b", "server mix and gross margin discussion"),
        _object("c", "generic company risk"),
    ]
    need = _need("need-1", "server profitability margin", "AI server profitability")
    routes = rank_need_lexical_routes(
        objects=objects,
        eligible_indices=np.asarray([0, 1, 2], dtype=np.int64),
        needs=(need,),
        per_need_limit=3,
    )
    assert [row.route_id for row in routes] == [
        "bm25_need_lexical",
        "typed_exact_phrase",
    ]
    assert routes[1].rows[0].compiled_object_id == "a"


def test_need_fusion_is_query_order_invariant() -> None:
    first = NeedRouteRanking(
        route_id="bm25",
        need_id="need-1",
        rows=(CandidateScore("a", 3.0), CandidateScore("b", 2.0)),
    )
    second = NeedRouteRanking(
        route_id="dense",
        need_id="need-2",
        rows=(CandidateScore("b", 0.9), CandidateScore("c", 0.8)),
    )
    forward = fuse_need_rankings((first, second), maximum=3)
    reverse = fuse_need_rankings((second, first), maximum=3)
    assert [row.compiled_object_id for row in forward] == [
        row.compiled_object_id for row in reverse
    ]
    assert forward[0].compiled_object_id == "b"


def test_typed_route_floor_survives_cross_route_rrf_crowding() -> None:
    typed = NeedRouteRanking(
        route_id="typed_intent_alias_groups",
        need_id="need-typed",
        rows=(CandidateScore("typed-target", 1.0),),
    )
    generic = tuple(
        NeedRouteRanking(
            route_id=f"generic-{index}",
            need_id=f"need-{index}",
            rows=(
                CandidateScore("popular-a", 3.0),
                CandidateScore("popular-b", 2.0),
            ),
        )
        for index in range(4)
    )

    result = fuse_need_rankings_with_route_floors(
        (*generic, typed),
        maximum=2,
        route_minimum_per_need={"typed_intent_alias_groups": 1},
    )

    assert result[0].compiled_object_id == "typed-target"
    assert len(result) == 2


def test_route_floor_is_ranking_input_order_invariant() -> None:
    typed = NeedRouteRanking(
        route_id="typed_metric_row_exact",
        need_id="metric",
        rows=(CandidateScore("metric-row", 1.0),),
    )
    lexical = NeedRouteRanking(
        route_id="bm25_need_lexical",
        need_id="lexical",
        rows=(CandidateScore("lexical", 2.0),),
    )
    kwargs = {
        "maximum": 2,
        "route_minimum_per_need": {"typed_metric_row_exact": 1},
    }

    forward = fuse_need_rankings_with_route_floors((typed, lexical), **kwargs)
    reverse = fuse_need_rankings_with_route_floors((lexical, typed), **kwargs)

    assert [row.compiled_object_id for row in forward] == [
        row.compiled_object_id for row in reverse
    ]


def test_route_membership_does_not_create_authority() -> None:
    ranking = NeedRouteRanking(
        route_id="bm25",
        need_id="need-1",
        rows=(CandidateScore("a", 1.0),),
    )
    membership = route_membership((ranking,), ("a",))
    assert membership["a"] == [
        {"route_id": "bm25", "need_id": "need-1", "rank": 1, "score": 1.0}
    ]


def test_ranking_evaluation_keeps_hard_negative_visible() -> None:
    rows = (CandidateScore("negative", 2.0), CandidateScore("positive", 1.0))
    result = evaluate_ranking(
        rows,
        positive_ids=("positive",),
        hard_negative_ids=("negative",),
        top_k=2,
    )
    assert result["positive_target_rank"] == 2
    assert result["pairwise_accuracy"] == 0.0
    assert result["hard_negative_ids_in_ranking"] == ["negative"]


def test_parent_context_is_projection_not_rank_authority() -> None:
    objects = [
        _typed_object("claim", "direct result", kind="claim"),
        _typed_object("table", "Revenue 10", kind="metric_row", metric_label="Revenue"),
        _typed_object("parent", "long parent context", kind="bounded_parent_context"),
    ]
    selected, excluded = rank_authority_indices(
        objects,
        np.asarray([0, 1, 2], dtype=np.int64),
        allowed_object_kinds=("claim", "metric_row"),
    )
    assert selected.tolist() == [0, 1]
    assert excluded == {"post_selection_projection_only:bounded_parent_context": 1}


def test_metric_row_route_prefers_exact_label_then_latest_publication() -> None:
    objects = [
        _typed_object(
            "old",
            "Revenue 10",
            kind="metric_row",
            publication_date="2025-05-01",
            metric_label="Revenue",
        ),
        _typed_object(
            "new",
            "Revenue 20",
            kind="metric_row",
            publication_date="2026-05-01",
            metric_label="Revenue",
        ),
        _typed_object(
            "mention",
            "Revenue appears in context",
            kind="metric_row",
            publication_date="2026-06-01",
            metric_label="Operating income",
        ),
        _typed_object("claim", "Revenue 30", kind="claim"),
    ]
    need = RetrievalNeed(
        need_id="metric-need",
        need_kind="metric",
        facet_id="reported_results",
        evidence_owner_ticker="NVDA",
        relationship_direction="subject_self_disclosure",
        intent_terms=("revenue",),
        role_cues=("reported results",),
        exact_phrases=(),
        lexical_query="revenue reported results",
        semantic_query="current reported revenue",
        constraint_digest="constraint",
    )
    routes = rank_need_metric_row_routes(
        objects=objects,
        eligible_indices=np.asarray([0, 1, 2, 3], dtype=np.int64),
        needs=(need,),
        per_need_limit=4,
    )
    assert [row.compiled_object_id for row in routes[0].rows] == [
        "new",
        "old",
        "mention",
    ]


def test_intent_alias_route_requires_every_metric_product_group() -> None:
    objects = [
        _object("direct", "We recognized $16.1 billion of AI server revenue."),
        _object("metric-only", "Revenue increased 20%."),
        _object("product-only", "AI server demand remains strong."),
    ]
    need = RetrievalNeed(
        need_id="metric-product",
        need_kind="metric_product",
        facet_id="reported_results",
        evidence_owner_ticker="DELL",
        relationship_direction="subject_self_disclosure",
        intent_terms=("revenue", "AI-optimized servers"),
        role_cues=("reported results",),
        exact_phrases=(),
        lexical_query="revenue AI-optimized servers",
        semantic_query="current AI server revenue",
        constraint_digest="constraint",
        intent_alias_groups=(("revenue", "net revenue"), ("AI server",)),
    )
    routes = rank_need_intent_alias_routes(
        objects=objects,
        eligible_indices=np.asarray([0, 1, 2], dtype=np.int64),
        needs=(need,),
        per_need_limit=3,
    )
    assert [row.compiled_object_id for row in routes[0].rows] == ["direct"]


def test_metric_row_route_uses_typed_metric_aliases() -> None:
    objects = [
        _typed_object(
            "target",
            "Net cash provided by operating activities 50,344",
            kind="metric_row",
            metric_label="Net cash provided by operating activities",
        ),
        _typed_object(
            "lease",
            "Operating cash flow used for operating leases 185",
            kind="metric_row",
            metric_label="Operating cash flow used for operating leases",
        ),
    ]
    need = RetrievalNeed(
        need_id="cash",
        need_kind="metric",
        facet_id="cash_generation",
        evidence_owner_ticker="NVDA",
        relationship_direction="subject_self_disclosure",
        intent_terms=("operating cash flow",),
        role_cues=("operating cash flow",),
        exact_phrases=(),
        lexical_query="operating cash flow",
        semantic_query="reported operating cash flow",
        constraint_digest="constraint",
        intent_alias_groups=(
            (
                "operating cash flow",
                "net cash provided by operating activities",
            ),
        ),
    )
    routes = rank_need_metric_row_routes(
        objects=objects,
        eligible_indices=np.asarray([0, 1], dtype=np.int64),
        needs=(need,),
        per_need_limit=2,
    )
    assert routes[0].rows[0].compiled_object_id == "target"


def test_metric_row_route_breaks_same_date_duplicates_by_financial_authority() -> None:
    objects = [
        _typed_object(
            "earnings-release",
            "Net cash provided by operating activities 50,344",
            kind="metric_row",
            metric_label="Net cash provided by operating activities",
            source_type="8-K",
            parent_section="Exhibit 99.1 Earnings Release",
        ),
        _typed_object(
            "mda-copy",
            "Net cash provided by operating activities 50,344",
            kind="metric_row",
            metric_label="Net cash provided by operating activities",
            source_type="10-Q",
            parent_section="Item 2. Management's Discussion and Analysis",
        ),
        _typed_object(
            "filing-statement",
            "Net cash provided by operating activities 50,344",
            kind="metric_row",
            metric_label="Net cash provided by operating activities",
            source_type="10-Q",
            parent_section="Item 1. Financial Statements",
        ),
    ]
    need = RetrievalNeed(
        need_id="cash-authority",
        need_kind="metric",
        facet_id="cash_generation",
        evidence_owner_ticker="NVDA",
        relationship_direction="subject_self_disclosure",
        intent_terms=("operating cash flow",),
        role_cues=("operating cash flow",),
        exact_phrases=(),
        lexical_query="operating cash flow",
        semantic_query="reported operating cash flow",
        constraint_digest="constraint",
        intent_alias_groups=(("net cash provided by operating activities",),),
    )
    routes = rank_need_metric_row_routes(
        objects=objects,
        eligible_indices=np.asarray([0, 1, 2], dtype=np.int64),
        needs=(need,),
        per_need_limit=3,
    )
    assert [row.compiled_object_id for row in routes[0].rows] == [
        "filing-statement",
        "mda-copy",
        "earnings-release",
    ]


def test_each_reranker_selects_its_own_best_need_per_candidate() -> None:
    ranking, selected = aggregate_all_need_pair_scores(
        candidate_ids=("a", "b"),
        need_ids=("need-2", "need-1"),
        pair_scores=(0.2, 0.8, 0.9, 0.1),
    )

    assert selected == {"a": "need-1", "b": "need-2"}
    assert [row.compiled_object_id for row in ranking] == ["b", "a"]


def test_all_need_pair_score_tie_uses_need_identity() -> None:
    ranking, selected = aggregate_all_need_pair_scores(
        candidate_ids=("a",),
        need_ids=("need-2", "need-1"),
        pair_scores=(0.5, 0.5),
    )

    assert selected == {"a": "need-1"}
    assert ranking[0].score == 0.5


def test_aggregated_ranking_stability_rebinds_scores_by_candidate() -> None:
    ranking, _ = aggregate_all_need_pair_scores(
        candidate_ids=("a", "b"),
        need_ids=("need-1", "need-2"),
        pair_scores=(0.9, 0.1, 0.2, 0.8),
    )

    assert ranking_candidate_order_stable(
        candidate_ids=("a", "b"),
        rows=ranking,
    )


def test_role_guard_preserves_primary_order_within_compatible_stratum() -> None:
    primary = (
        CandidateScore("target", 0.9),
        CandidateScore("other", 0.8),
        CandidateScore("noise", 0.7),
    )
    shadow = (
        CandidateScore("other", 0.9),
        CandidateScore("noise", 0.8),
        CandidateScore("target", 0.1),
    )

    result = role_guarded_primary_ranking(
        candidate_ids=("target", "other", "noise"),
        primary_rows=primary,
        shadow_rows=shadow,
        compatibility_by_id={
            "target": "compatible",
            "other": "compatible",
            "noise": "incompatible",
        },
    )

    assert [row.compiled_object_id for row in result] == [
        "target",
        "other",
        "noise",
    ]
