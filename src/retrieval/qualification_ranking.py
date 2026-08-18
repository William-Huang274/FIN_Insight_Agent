from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .object_retrieval_comparison import CandidateScore
from .retrieval_need import RetrievalNeed


_ROUTE_PRIORITY = {
    "typed_metric_row_exact": 0,
    "typed_intent_alias_groups": 1,
    "typed_exact_phrase": 2,
    "bm25_need_lexical": 3,
    "bge_m3_multi_vector": 4,
    "bge_m3_learned_sparse": 5,
    "bge_m3_dense": 6,
    "qwen3_embedding_0_6b_dense": 6,
}


class QualificationRankingError(ValueError):
    """A label-blind qualification ranking step lost its bounded contract."""


@dataclass(frozen=True)
class RerankerPairBinding:
    candidate_id: str
    need_id: str


def select_candidate_relevant_need_ids(
    route_rows: Sequence[Mapping[str, Any]],
    *,
    allowed_need_ids: set[str],
    maximum: int,
) -> tuple[str, ...]:
    """Select only needs that actually recalled a candidate.

    This avoids both failure modes seen in the development runner: one BGE
    preselected need cannot control every reranker, while the Cartesian product
    of every candidate and every proposition need is needlessly broad.
    """

    if maximum < 1:
        raise QualificationRankingError("qualification_relevant_need_budget_invalid")
    best: dict[str, tuple[int, int, str]] = {}
    for row in route_rows:
        need_id = str(row.get("need_id") or "")
        route_id = str(row.get("route_id") or "")
        rank = int(row.get("rank") or 0)
        if not need_id or need_id not in allowed_need_ids or rank < 1:
            continue
        key = (_ROUTE_PRIORITY.get(route_id, 99), rank, need_id)
        if need_id not in best or key < best[need_id]:
            best[need_id] = key
    return tuple(
        need_id
        for need_id, _ in sorted(best.items(), key=lambda item: item[1])[:maximum]
    )


def build_relevant_pair_manifest(
    *,
    candidate_ids: Sequence[str],
    route_membership_by_id: Mapping[str, Sequence[Mapping[str, Any]]],
    needs_by_id: Mapping[str, RetrievalNeed],
    objects_by_id: Mapping[str, Mapping[str, Any]],
    maximum_needs_per_candidate: int,
) -> tuple[list[tuple[str, str]], list[RerankerPairBinding]]:
    pairs: list[tuple[str, str]] = []
    bindings: list[RerankerPairBinding] = []
    allowed = set(needs_by_id)
    for candidate_id in candidate_ids:
        if candidate_id not in objects_by_id:
            raise QualificationRankingError(
                f"qualification_pair_candidate_missing:{candidate_id}"
            )
        need_ids = select_candidate_relevant_need_ids(
            route_membership_by_id.get(candidate_id, ()),
            allowed_need_ids=allowed,
            maximum=maximum_needs_per_candidate,
        )
        if not need_ids:
            raise QualificationRankingError(
                f"qualification_pair_relevant_need_missing:{candidate_id}"
            )
        document = str(objects_by_id[candidate_id].get("model_text") or "")
        if not document.strip():
            raise QualificationRankingError(
                f"qualification_pair_document_missing:{candidate_id}"
            )
        for need_id in need_ids:
            pairs.append((needs_by_id[need_id].semantic_query, document))
            bindings.append(RerankerPairBinding(candidate_id, need_id))
    return pairs, bindings


def aggregate_relevant_pair_scores(
    *,
    candidate_ids: Sequence[str],
    bindings: Sequence[RerankerPairBinding],
    scores: Sequence[float],
) -> tuple[tuple[CandidateScore, ...], dict[str, str]]:
    if len(bindings) != len(scores):
        raise QualificationRankingError("qualification_pair_score_count_mismatch")
    allowed = set(candidate_ids)
    best: dict[str, tuple[float, str]] = {}
    for binding, raw_score in zip(bindings, scores):
        if binding.candidate_id not in allowed:
            raise QualificationRankingError("qualification_pair_candidate_scope_drift")
        score = float(raw_score)
        value = (score, binding.need_id)
        previous = best.get(binding.candidate_id)
        if previous is None or score > previous[0] or (
            score == previous[0] and binding.need_id < previous[1]
        ):
            best[binding.candidate_id] = value
    if set(best) != allowed:
        raise QualificationRankingError("qualification_pair_candidate_score_missing")
    ranked = sorted(best, key=lambda key: (-best[key][0], key))
    return (
        tuple(CandidateScore(candidate_id, best[candidate_id][0]) for candidate_id in ranked),
        {candidate_id: best[candidate_id][1] for candidate_id in candidate_ids},
    )


__all__ = [
    "QualificationRankingError",
    "RerankerPairBinding",
    "aggregate_relevant_pair_scores",
    "build_relevant_pair_manifest",
    "select_candidate_relevant_need_ids",
]
