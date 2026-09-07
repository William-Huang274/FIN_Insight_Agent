from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import math
from typing import Any, Mapping, Sequence

import numpy as np

from .object_retrieval_comparison import (
    CandidateScore,
    bm25_rank,
    dense_rank,
    sparse_rank,
)
from .retrieval_need import RetrievalNeed


_METRIC_ROW_SOURCE_PRIORITY = {
    "10-K": 5,
    "10-Q": 5,
    "20-F": 5,
    "40-F": 5,
    "8-K": 4,
    "6-K": 4,
}


class CandidateRankingError(ValueError):
    """A multi-need candidate ranking violated the shared S1 boundary."""


@dataclass(frozen=True)
class NeedRouteRanking:
    route_id: str
    need_id: str
    rows: tuple[CandidateScore, ...]


def exact_phrase_rank(
    objects: Sequence[Mapping[str, Any]],
    eligible_indices: np.ndarray,
    phrases: Sequence[str],
    *,
    limit: int,
) -> list[CandidateScore]:
    normalized = tuple(value.casefold().strip() for value in phrases if value.strip())
    if eligible_indices.size == 0 or not normalized:
        return []
    rows: list[CandidateScore] = []
    for raw_index in eligible_indices:
        row = objects[int(raw_index)]
        text = " ".join(str(row["model_text"]).casefold().split())
        matches = sum(phrase in text for phrase in normalized)
        if not matches:
            continue
        rows.append(
            CandidateScore(
                compiled_object_id=str(row["compiled_object_id"]),
                score=float(matches) + 1.0 / max(len(text), 1),
            )
        )
    rows.sort(key=lambda value: (-value.score, value.compiled_object_id))
    return rows[:limit]


def rank_need_lexical_routes(
    *,
    objects: Sequence[Mapping[str, Any]],
    eligible_indices: np.ndarray,
    needs: Sequence[RetrievalNeed],
    per_need_limit: int,
) -> tuple[NeedRouteRanking, ...]:
    _validate_budget(per_need_limit)
    rankings: list[NeedRouteRanking] = []
    for need in needs:
        rankings.append(
            NeedRouteRanking(
                route_id="bm25_need_lexical",
                need_id=need.need_id,
                rows=tuple(
                    bm25_rank(
                        objects,
                        eligible_indices,
                        need.lexical_query,
                        limit=per_need_limit,
                    )
                ),
            )
        )
        if need.exact_phrases:
            rankings.append(
                NeedRouteRanking(
                    route_id="typed_exact_phrase",
                    need_id=need.need_id,
                    rows=tuple(
                        exact_phrase_rank(
                            objects,
                            eligible_indices,
                            need.exact_phrases,
                            limit=per_need_limit,
                        )
                    ),
                )
            )
    return tuple(rankings)


def rank_need_intent_alias_routes(
    *,
    objects: Sequence[Mapping[str, Any]],
    eligible_indices: np.ndarray,
    needs: Sequence[RetrievalNeed],
    per_need_limit: int,
) -> tuple[NeedRouteRanking, ...]:
    """Require one bounded alias hit from every typed intent group.

    This route is ontology-driven and label-blind. A metric-product request can
    therefore retrieve a claim such as ``AI server revenue`` without allowing
    a generic ``revenue`` table or an unrelated use of ``server`` to satisfy
    the same need.
    """

    _validate_budget(per_need_limit)
    rankings: list[NeedRouteRanking] = []
    for need in needs:
        groups = tuple(
            tuple(_normalized_surface(alias) for alias in group if alias.strip())
            for group in need.intent_alias_groups
            if group
        )
        if not groups:
            continue
        rows: list[CandidateScore] = []
        for raw_index in eligible_indices:
            row = objects[int(raw_index)]
            text = _normalized_surface(str(row.get("model_text") or ""))
            group_hits = [
                tuple(alias for alias in group if _contains_alias(text, alias))
                for group in groups
            ]
            if not all(group_hits):
                continue
            matched = sum(len(values) for values in group_hits)
            rows.append(
                CandidateScore(
                    compiled_object_id=str(row["compiled_object_id"]),
                    score=float(len(groups) * 1_000 + matched * 10)
                    + 1.0 / max(len(text), 1),
                )
            )
        rows.sort(key=lambda value: (-value.score, value.compiled_object_id))
        rankings.append(
            NeedRouteRanking(
                route_id="typed_intent_alias_groups",
                need_id=need.need_id,
                rows=tuple(rows[:per_need_limit]),
            )
        )
    return tuple(rankings)


def rank_authority_indices(
    objects: Sequence[Mapping[str, Any]],
    eligible_indices: np.ndarray,
    *,
    allowed_object_kinds: Sequence[str],
) -> tuple[np.ndarray, dict[str, int]]:
    """Keep context objects available for projection without letting them rank.

    Hard eligibility answers whether an object belongs to the request boundary.
    Rank authority is narrower: parent context can be attached to a selected
    claim/table row, but it must not displace those evidence-bearing children.
    """

    allowed = {str(value).strip() for value in allowed_object_kinds if str(value).strip()}
    if not allowed:
        raise CandidateRankingError("rank_authority_object_kinds_empty")
    selected: list[int] = []
    excluded: dict[str, int] = {}
    for raw_index in eligible_indices:
        index = int(raw_index)
        kind = str(objects[index].get("object_kind") or "")
        if kind in allowed:
            selected.append(index)
        else:
            reason = f"post_selection_projection_only:{kind or 'missing'}"
            excluded[reason] = excluded.get(reason, 0) + 1
    return np.asarray(selected, dtype=np.int64), dict(sorted(excluded.items()))


def rank_need_metric_row_routes(
    *,
    objects: Sequence[Mapping[str, Any]],
    eligible_indices: np.ndarray,
    needs: Sequence[RetrievalNeed],
    per_need_limit: int,
) -> tuple[NeedRouteRanking, ...]:
    """Rank typed metric rows from request metric intent, never from qrels.

    A matching metric label is stronger than a mention somewhere in table
    context.  Within the same match class, the newest already-eligible official
    publication wins.  This remains candidate retrieval and has no NumericFact
    authority.
    """

    _validate_budget(per_need_limit)
    rankings: list[NeedRouteRanking] = []
    for need in needs:
        if need.need_kind not in {"metric", "metric_product"} or not need.intent_terms:
            continue
        metric_aliases = (
            tuple(
                _normalized_surface(value)
                for value in need.intent_alias_groups[0]
                if value.strip()
            )
            if need.intent_alias_groups
            else (_normalized_surface(need.intent_terms[0]),)
        )
        metric_aliases = tuple(value for value in metric_aliases if value)
        if not metric_aliases:
            continue
        rows: list[tuple[int, int, int, int, str]] = []
        for raw_index in eligible_indices:
            row = objects[int(raw_index)]
            if str(row.get("object_kind") or "") != "metric_row":
                continue
            projection = row.get("structured_projection") or {}
            label = _normalized_surface(str(projection.get("metric_row_label") or ""))
            text = _normalized_surface(str(row.get("model_text") or ""))
            match_class = 0
            if label in metric_aliases:
                match_class = 3
            elif label and any(
                alias in label or label in alias for alias in metric_aliases
            ):
                match_class = 2
            elif any(_contains_alias(text, alias) for alias in metric_aliases):
                match_class = 1
            if not match_class:
                continue
            base = row.get("base_object_view") or {}
            publication = str(base.get("publication_date") or "")
            try:
                publication_ordinal = date.fromisoformat(publication).toordinal()
            except ValueError:
                publication_ordinal = 0
            source_type = str(base.get("source_type") or "").upper()
            source_priority = _METRIC_ROW_SOURCE_PRIORITY.get(source_type, 0)
            section = _normalized_surface(
                str(projection.get("parent_section") or base.get("section") or "")
            )
            if "financial statements" in section:
                section_priority = 3
            elif "management s discussion and analysis" in section:
                section_priority = 2
            elif "earnings release" in section:
                section_priority = 1
            else:
                section_priority = 0
            rows.append(
                (
                    match_class,
                    publication_ordinal,
                    source_priority,
                    section_priority,
                    str(row["compiled_object_id"]),
                )
            )
        rows.sort(
            key=lambda value: (
                -value[0],
                -value[1],
                -value[2],
                -value[3],
                value[4],
            )
        )
        rankings.append(
            NeedRouteRanking(
                route_id="typed_metric_row_exact",
                need_id=need.need_id,
                rows=tuple(
                    CandidateScore(
                        compiled_object_id=object_id,
                        score=float(
                            match_class * 1_000_000_000_000
                            + publication_ordinal * 1_000_000
                            + source_priority * 1_000
                            + section_priority
                        ),
                    )
                    for (
                        match_class,
                        publication_ordinal,
                        source_priority,
                        section_priority,
                        object_id,
                    ) in rows[:per_need_limit]
                ),
            )
        )
    return tuple(rankings)


def rank_need_dense_routes(
    *,
    route_id: str,
    objects: Sequence[Mapping[str, Any]],
    eligible_indices: np.ndarray,
    needs: Sequence[RetrievalNeed],
    document_embeddings: np.ndarray,
    query_embeddings: np.ndarray,
    per_need_limit: int,
) -> tuple[NeedRouteRanking, ...]:
    _validate_budget(per_need_limit)
    if query_embeddings.shape[0] != len(needs):
        raise CandidateRankingError("need_dense_query_count_mismatch")
    return tuple(
        NeedRouteRanking(
            route_id=route_id,
            need_id=need.need_id,
            rows=tuple(
                dense_rank(
                    objects,
                    eligible_indices,
                    document_embeddings,
                    query_embeddings[index],
                    limit=per_need_limit,
                )
            ),
        )
        for index, need in enumerate(needs)
    )


def rank_need_sparse_routes(
    *,
    route_id: str,
    objects: Sequence[Mapping[str, Any]],
    eligible_indices: np.ndarray,
    needs: Sequence[RetrievalNeed],
    document_sparse: Any,
    query_sparse: Any,
    per_need_limit: int,
) -> tuple[NeedRouteRanking, ...]:
    _validate_budget(per_need_limit)
    if int(query_sparse.shape[0]) != len(needs):
        raise CandidateRankingError("need_sparse_query_count_mismatch")
    return tuple(
        NeedRouteRanking(
            route_id=route_id,
            need_id=need.need_id,
            rows=tuple(
                sparse_rank(
                    objects,
                    eligible_indices,
                    document_sparse,
                    query_sparse[index],
                    limit=per_need_limit,
                )
            ),
        )
        for index, need in enumerate(needs)
    )


def fuse_need_rankings(
    rankings: Sequence[NeedRouteRanking],
    *,
    maximum: int,
    reciprocal_rank_constant: int = 60,
) -> tuple[CandidateScore, ...]:
    """Fuse bounded needs without allowing query order to affect the result."""

    _validate_budget(maximum)
    if reciprocal_rank_constant <= 0:
        raise CandidateRankingError("reciprocal_rank_constant_invalid")
    scores: dict[str, float] = {}
    best_rank: dict[str, int] = {}
    coverage: dict[str, set[tuple[str, str]]] = {}
    for ranking in rankings:
        for rank, row in enumerate(ranking.rows, start=1):
            object_id = row.compiled_object_id
            scores[object_id] = scores.get(object_id, 0.0) + 1.0 / (
                reciprocal_rank_constant + rank
            )
            best_rank[object_id] = min(best_rank.get(object_id, rank), rank)
            coverage.setdefault(object_id, set()).add(
                (ranking.route_id, ranking.need_id)
            )
    ordered = sorted(
        scores,
        key=lambda object_id: (
            -scores[object_id],
            -len(coverage[object_id]),
            best_rank[object_id],
            object_id,
        ),
    )
    return tuple(
        CandidateScore(compiled_object_id=object_id, score=scores[object_id])
        for object_id in ordered[:maximum]
    )


def fuse_need_rankings_with_route_floors(
    rankings: Sequence[NeedRouteRanking],
    *,
    maximum: int,
    route_minimum_per_need: Mapping[str, int],
    reciprocal_rank_constant: int = 60,
) -> tuple[CandidateScore, ...]:
    """Preserve bounded high-precision lanes before filling by RRF.

    RRF rewards candidates repeated across many routes.  In a multi-facet
    financial request that can crowd a top typed metric/product candidate out
    of the finite candidate pool merely because it appears in one precise
    lane.  A route floor protects the first N rows of each need-specific typed
    lane without consulting labels or granting Evidence authority.
    """

    _validate_budget(maximum)
    floors: dict[str, int] = {}
    for route_id, raw_value in route_minimum_per_need.items():
        value = int(raw_value)
        if value < 0:
            raise CandidateRankingError("candidate_route_floor_invalid")
        if value:
            floors[str(route_id)] = value
    full = fuse_need_rankings(
        rankings,
        maximum=max(
            maximum,
            len(
                {
                    row.compiled_object_id
                    for ranking in rankings
                    for row in ranking.rows
                }
            ),
        ),
        reciprocal_rank_constant=reciprocal_rank_constant,
    )
    protected: set[str] = set()
    for ranking in sorted(
        rankings, key=lambda value: (value.route_id, value.need_id)
    ):
        floor = floors.get(ranking.route_id, 0)
        protected.update(
            row.compiled_object_id for row in ranking.rows[:floor]
        )
    if len(protected) > maximum:
        raise CandidateRankingError("candidate_route_floor_exceeds_union_budget")
    protected_rows = [
        row for row in full if row.compiled_object_id in protected
    ]
    remaining_rows = [
        row for row in full if row.compiled_object_id not in protected
    ]
    return tuple((protected_rows + remaining_rows)[:maximum])


def fuse_lane_rankings_with_balanced_review_prefix(
    rankings: Sequence[NeedRouteRanking],
    *,
    maximum: int,
    review_k: int,
    reciprocal_rank_constant: int = 60,
) -> tuple[CandidateScore, ...]:
    """Give every requested facet an equal chance inside the review window.

    Repetition across several lanes is still useful after the review prefix,
    but it must not consume the finite human/Agent review window before a
    proposition's other approved facets are represented. The prefix is a
    deterministic round-robin over lane-local financial rankings and consults
    neither qrels nor business labels.
    """

    _validate_budget(maximum)
    _validate_budget(review_k)
    if review_k > maximum:
        raise CandidateRankingError("candidate_review_budget_exceeds_maximum")
    if not rankings:
        return ()
    full = fuse_need_rankings(
        rankings,
        maximum=max(
            maximum,
            len(
                {
                    row.compiled_object_id
                    for ranking in rankings
                    for row in ranking.rows
                }
            ),
        ),
        reciprocal_rank_constant=reciprocal_rank_constant,
    )
    score_by_id = {row.compiled_object_id: row.score for row in full}
    lanes = tuple(sorted(rankings, key=lambda value: (value.need_id, value.route_id)))
    offsets = [0] * len(lanes)
    prefix_ids: list[str] = []
    selected: set[str] = set()
    while len(prefix_ids) < review_k:
        progressed = False
        for index, ranking in enumerate(lanes):
            while offsets[index] < len(ranking.rows):
                object_id = ranking.rows[offsets[index]].compiled_object_id
                offsets[index] += 1
                if object_id in selected or object_id not in score_by_id:
                    continue
                prefix_ids.append(object_id)
                selected.add(object_id)
                progressed = True
                break
            if len(prefix_ids) >= review_k:
                break
        if not progressed:
            break
    prefix_ids.extend(
        row.compiled_object_id
        for row in full
        if row.compiled_object_id not in selected
    )
    return tuple(
        CandidateScore(compiled_object_id=object_id, score=score_by_id[object_id])
        for object_id in prefix_ids[:maximum]
    )


def route_membership(
    rankings: Sequence[NeedRouteRanking],
    candidate_ids: Sequence[str],
) -> dict[str, list[dict[str, Any]]]:
    allowed = set(candidate_ids)
    output: dict[str, list[dict[str, Any]]] = {object_id: [] for object_id in candidate_ids}
    for ranking in rankings:
        for rank, row in enumerate(ranking.rows, start=1):
            if row.compiled_object_id not in allowed:
                continue
            output[row.compiled_object_id].append(
                {
                    "route_id": ranking.route_id,
                    "need_id": ranking.need_id,
                    "rank": rank,
                    "score": _finite(row.score),
                }
            )
    for rows in output.values():
        rows.sort(key=lambda value: (value["route_id"], value["need_id"], value["rank"]))
    return output


def evaluate_ranking(
    rows: Sequence[CandidateScore],
    *,
    positive_ids: Sequence[str],
    hard_negative_ids: Sequence[str],
    top_k: int,
) -> dict[str, Any]:
    _validate_budget(top_k)
    rank_by_id = {
        row.compiled_object_id: rank for rank, row in enumerate(rows, start=1)
    }
    positives = [value for value in positive_ids if value in rank_by_id]
    negatives = [value for value in hard_negative_ids if value in rank_by_id]
    comparisons = [(positive, negative) for positive in positives for negative in negatives]
    wins = sum(rank_by_id[positive] < rank_by_id[negative] for positive, negative in comparisons)
    best_positive = min((rank_by_id[value] for value in positives), default=None)
    return {
        "positive_target_available": bool(positive_ids),
        "positive_target_in_ranking": bool(positives),
        "positive_target_rank": best_positive,
        "positive_target_in_top_k": best_positive is not None and best_positive <= top_k,
        "positive_ids_in_ranking": sorted(positives),
        "hard_negative_in_ranking_count": len(negatives),
        "hard_negative_ids_in_ranking": sorted(negatives),
        "pairwise_wins": wins,
        "pairwise_comparisons": len(comparisons),
        "pairwise_accuracy": round(wins / len(comparisons), 6) if comparisons else None,
        "reciprocal_rank": round(1.0 / best_positive, 6) if best_positive else 0.0,
        "top_ids": [row.compiled_object_id for row in rows[:top_k]],
    }


def rank_scores(
    candidate_ids: Sequence[str], scores: Sequence[float]
) -> tuple[CandidateScore, ...]:
    if len(candidate_ids) != len(scores):
        raise CandidateRankingError("candidate_score_count_mismatch")
    rows = [
        CandidateScore(compiled_object_id=object_id, score=_finite(score))
        for object_id, score in zip(candidate_ids, scores)
    ]
    rows.sort(key=lambda value: (-value.score, value.compiled_object_id))
    return tuple(rows)


def role_guarded_primary_ranking(
    *,
    candidate_ids: Sequence[str],
    primary_rows: Sequence[CandidateScore],
    shadow_rows: Sequence[CandidateScore],
    compatibility_by_id: Mapping[str, str],
) -> tuple[CandidateScore, ...]:
    """Apply role strata without averaging away the selected reranker's order.

    Evidence Role is a financial eligibility/advisory layer, not a second
    semantic relevance model. It may separate compatible, abstain and
    incompatible candidates, but within a stratum the provisional winner is
    authoritative. A weaker shadow reranker is retained only as a stable
    sub-tie signal and cannot demote a primary top result.
    """

    candidate_set = set(candidate_ids)
    primary_rank = {
        row.compiled_object_id: rank
        for rank, row in enumerate(primary_rows, start=1)
    }
    shadow_rank = {
        row.compiled_object_id: rank
        for rank, row in enumerate(shadow_rows, start=1)
    }
    if (
        set(primary_rank) != candidate_set
        or set(shadow_rank) != candidate_set
        or set(compatibility_by_id) != candidate_set
    ):
        raise CandidateRankingError("role_guarded_candidate_identity_mismatch")
    penalty = {"compatible": 0.0, "abstain": -1.0, "incompatible": -2.0}
    if any(value not in penalty for value in compatibility_by_id.values()):
        raise CandidateRankingError("role_guarded_compatibility_invalid")
    return rank_scores(
        candidate_ids,
        tuple(
            penalty[compatibility_by_id[object_id]]
            + 1.0 / (1 + primary_rank[object_id])
            + 1e-6 / (1 + shadow_rank[object_id])
            for object_id in candidate_ids
        ),
    )


def aggregate_all_need_pair_scores(
    *,
    candidate_ids: Sequence[str],
    need_ids: Sequence[str],
    pair_scores: Sequence[float],
) -> tuple[tuple[CandidateScore, ...], dict[str, str]]:
    """Take each candidate's best independently scored RetrievalNeed.

    Inputs are candidate-major and need-minor.  Unlike a selector chosen by a
    different model, this lets each reranker decide which bounded need the
    candidate can answer.  Need IDs break exact score ties deterministically.
    """

    candidates = tuple(str(value) for value in candidate_ids)
    needs = tuple(str(value) for value in need_ids)
    if (
        not candidates
        or len(candidates) != len(set(candidates))
        or not needs
        or len(needs) != len(set(needs))
    ):
        raise CandidateRankingError("candidate_need_score_identity_invalid")
    if len(pair_scores) != len(candidates) * len(needs):
        raise CandidateRankingError("candidate_need_score_count_mismatch")
    selected_scores: list[float] = []
    selected_needs: dict[str, str] = {}
    offset = 0
    for candidate_id in candidates:
        rows = [
            (need_id, _finite(pair_scores[offset + index]))
            for index, need_id in enumerate(needs)
        ]
        offset += len(needs)
        best_need, best_score = min(rows, key=lambda row: (-row[1], row[0]))
        selected_scores.append(best_score)
        selected_needs[candidate_id] = best_need
    return rank_scores(candidates, selected_scores), selected_needs


def ranking_candidate_order_stable(
    *, candidate_ids: Sequence[str], rows: Sequence[CandidateScore]
) -> bool:
    """Prove that a completed ranking does not depend on candidate input order.

    The all-need reranker emits one score per candidate *after* aggregating a
    candidate-by-need matrix.  Reversing that raw matrix is not a valid
    permutation because it also changes which score belongs to which need.
    This check therefore rebinds the already aggregated score by object ID and
    reranks a reversed candidate sequence.
    """

    candidates = tuple(str(value) for value in candidate_ids)
    score_by_id = {row.compiled_object_id: row.score for row in rows}
    if (
        len(candidates) != len(set(candidates))
        or len(rows) != len(candidates)
        or set(score_by_id) != set(candidates)
    ):
        raise CandidateRankingError("candidate_ranking_identity_mismatch")
    reversed_ids = tuple(reversed(candidates))
    reranked = rank_scores(
        reversed_ids,
        tuple(score_by_id[object_id] for object_id in reversed_ids),
    )
    return [row.compiled_object_id for row in reranked] == [
        row.compiled_object_id for row in rows
    ]


def _finite(value: float) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise CandidateRankingError("candidate_score_not_finite")
    return number


def _validate_budget(value: int) -> None:
    if not isinstance(value, int) or value <= 0:
        raise CandidateRankingError("candidate_budget_invalid")


def _normalized_surface(value: str) -> str:
    return " ".join(
        "".join(character if character.isalnum() else " " for character in value.casefold())
        .replace("_", " ")
        .split()
    )


def _contains_alias(text: str, alias: str) -> bool:
    return f" {alias} " in f" {text} "


__all__ = [
    "CandidateRankingError",
    "NeedRouteRanking",
    "aggregate_all_need_pair_scores",
    "evaluate_ranking",
    "exact_phrase_rank",
    "fuse_need_rankings",
    "fuse_need_rankings_with_route_floors",
    "fuse_lane_rankings_with_balanced_review_prefix",
    "rank_need_dense_routes",
    "rank_need_intent_alias_routes",
    "rank_need_lexical_routes",
    "rank_need_metric_row_routes",
    "rank_need_sparse_routes",
    "rank_authority_indices",
    "ranking_candidate_order_stable",
    "rank_scores",
    "role_guarded_primary_ranking",
    "route_membership",
]
