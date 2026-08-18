from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import numpy as np
from rank_bm25 import BM25Okapi

from .object_retrieval_comparison import CandidateScore, union_candidate_ids
from .query_plan_v3 import TypedLexicalSubquery
from .text import tokenize


class BalancedLexicalRecallError(ValueError):
    """A typed lexical recall plan cannot be executed deterministically."""


@dataclass(frozen=True)
class BalancedLexicalRecall:
    candidates: tuple[CandidateScore, ...]
    trace: Mapping[str, Any]


def balanced_bm25_rank(
    objects: Sequence[Mapping[str, Any]],
    eligible_indices: np.ndarray,
    subqueries: Sequence[TypedLexicalSubquery],
    *,
    limit: int,
) -> BalancedLexicalRecall:
    """Give every typed business concept a bounded first-stage opportunity.

    Each query searches the same hard-filtered object population.  Candidate
    routes are fused deterministically and truncated only after query-level
    recall.  This prevents a long generic bag of terms from consuming the
    entire BM25 prefix before a narrower material disclosure surface is seen.
    Scores remain candidate diagnostics and never confer Evidence authority.
    """

    if limit <= 0:
        raise BalancedLexicalRecallError("balanced_lexical_limit_invalid")
    if eligible_indices.size == 0:
        return BalancedLexicalRecall(
            candidates=(),
            trace={
                "mode": "typed_subquery_balanced_bm25_v1",
                "subquery_count": 0,
                "eligible_object_count": 0,
                "candidate_count": 0,
                "candidate_not_evidence": True,
            },
        )
    usable = [row for row in subqueries if row.lexical_tokens]
    if not usable:
        raise BalancedLexicalRecallError("balanced_lexical_subqueries_missing")

    tokenized = [
        tokenize(str(objects[int(index)]["model_text"]))
        for index in eligible_indices
    ]
    index = BM25Okapi(tokenized)
    routes: list[list[CandidateScore]] = []
    summaries: list[dict[str, Any]] = []
    for row in usable:
        scores = np.asarray(index.get_scores(list(row.lexical_tokens)), dtype=np.float64)
        candidates = [
            CandidateScore(
                compiled_object_id=str(objects[int(object_index)]["compiled_object_id"]),
                score=float(score),
            )
            for object_index, score in zip(eligible_indices, scores)
        ]
        candidates.sort(key=lambda item: (-item.score, item.compiled_object_id))
        candidates = candidates[:limit]
        routes.append(candidates)
        summaries.append(
            {
                "query_id": row.query_id,
                "query_kind": row.query_kind,
                "concept_id": row.concept_id,
                "lexical_query": row.lexical_query,
                "candidate_count": len(candidates),
            }
        )

    ordered_ids = union_candidate_ids(routes, maximum=limit)
    ranks_by_route = [
        {candidate.compiled_object_id: rank for rank, candidate in enumerate(route, 1)}
        for route in routes
    ]
    candidates = tuple(
        CandidateScore(
            compiled_object_id=object_id,
            score=sum(
                1.0 / (60.0 + ranks[object_id])
                for ranks in ranks_by_route
                if object_id in ranks
            ),
        )
        for object_id in ordered_ids
    )
    return BalancedLexicalRecall(
        candidates=candidates,
        trace={
            "mode": "typed_subquery_balanced_bm25_v1",
            "subquery_count": len(usable),
            "subqueries": summaries,
            "eligible_object_count": int(eligible_indices.size),
            "candidate_count": len(candidates),
            "candidate_limit": limit,
            "fusion": "minimum_rank_then_cross_query_rank_sum",
            "candidate_not_evidence": True,
            "numeric_authority": False,
        },
    )


__all__ = [
    "BalancedLexicalRecall",
    "BalancedLexicalRecallError",
    "balanced_bm25_rank",
]
