from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
from rank_bm25 import BM25Okapi

from .ranking_comparison import RankingQuery, load_ranking_queries
from .text import tokenize


class ObjectRetrievalComparisonError(ValueError):
    """Raised when the compiled-object comparison cannot fail closed."""


@dataclass(frozen=True)
class CandidateScore:
    compiled_object_id: str
    score: float


def load_compiled_objects(rows: Iterable[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    output: list[dict[str, Any]] = []
    identities: set[str] = set()
    for raw in rows:
        row = dict(raw)
        object_id = str(row.get("compiled_object_id") or "")
        base = row.get("base_object_view")
        if not (
            row.get("schema_version")
            in {
                "fin_ia_compiled_financial_object_view_v1_0",
                "fin_ia_compiled_financial_object_view_v1_1",
            }
            and object_id
            and object_id not in identities
            and isinstance(base, Mapping)
            and str(base.get("source_record_id") or "")
            and str(base.get("ticker") or "")
            and str(row.get("model_text") or "").strip()
            and row.get("candidate_not_evidence") is True
            and row.get("numeric_authority") is False
            and row.get("evidence_promoted") is False
        ):
            raise ObjectRetrievalComparisonError("compiled_object_contract_invalid")
        identities.add(object_id)
        output.append(row)
    if not output:
        raise ObjectRetrievalComparisonError("compiled_object_population_empty")
    return tuple(output)


def eligible_object_indices(
    objects: Sequence[Mapping[str, Any]],
    query: RankingQuery,
) -> tuple[np.ndarray, dict[str, int]]:
    as_of = date.fromisoformat(query.publication_date_lte)
    eligible: list[int] = []
    exclusions: dict[str, int] = {}
    for index, row in enumerate(objects):
        reason = _exclusion_reason(row, query, as_of)
        if reason is None:
            eligible.append(index)
        else:
            exclusions[reason] = exclusions.get(reason, 0) + 1
    return np.asarray(eligible, dtype=np.int64), dict(sorted(exclusions.items()))


def bm25_rank(
    objects: Sequence[Mapping[str, Any]],
    eligible_indices: np.ndarray,
    query_text: str,
    *,
    limit: int,
) -> list[CandidateScore]:
    query_tokens = tokenize(query_text)
    if eligible_indices.size == 0 or not query_tokens:
        return []
    tokenized = [
        tokenize(str(objects[int(index)]["model_text"])) for index in eligible_indices
    ]
    scores = BM25Okapi(tokenized).get_scores(query_tokens)
    return _top_scores(objects, eligible_indices, np.asarray(scores), limit=limit)


def dense_rank(
    objects: Sequence[Mapping[str, Any]],
    eligible_indices: np.ndarray,
    document_embeddings: np.ndarray,
    query_embedding: np.ndarray,
    *,
    limit: int,
) -> list[CandidateScore]:
    if document_embeddings.shape[0] != len(objects):
        raise ObjectRetrievalComparisonError("dense_object_count_mismatch")
    if eligible_indices.size == 0:
        return []
    query = np.asarray(query_embedding, dtype=np.float32).reshape(-1)
    matrix = np.asarray(document_embeddings[eligible_indices], dtype=np.float32)
    if matrix.shape[1] != query.shape[0]:
        raise ObjectRetrievalComparisonError("dense_dimension_mismatch")
    scores = matrix @ query
    return _top_scores(objects, eligible_indices, scores, limit=limit)


def sparse_rank(
    objects: Sequence[Mapping[str, Any]],
    eligible_indices: np.ndarray,
    document_sparse: Any,
    query_sparse: Any,
    *,
    limit: int,
) -> list[CandidateScore]:
    if int(document_sparse.shape[0]) != len(objects):
        raise ObjectRetrievalComparisonError("sparse_object_count_mismatch")
    if eligible_indices.size == 0:
        return []
    if int(document_sparse.shape[1]) != int(query_sparse.shape[1]):
        raise ObjectRetrievalComparisonError("sparse_dimension_mismatch")
    scores = document_sparse[eligible_indices].dot(query_sparse.T).toarray().reshape(-1)
    return _top_scores(objects, eligible_indices, scores, limit=limit)


def union_candidate_ids(
    routes: Sequence[Sequence[CandidateScore]],
    *,
    maximum: int,
) -> tuple[str, ...]:
    if maximum <= 0:
        raise ObjectRetrievalComparisonError("candidate_union_maximum_invalid")
    route_ranks = [
        {row.compiled_object_id: rank for rank, row in enumerate(route, start=1)}
        for route in routes
    ]
    identities = {identity for ranks in route_ranks for identity in ranks}
    ordered = sorted(
        identities,
        key=lambda identity: (
            min(ranks.get(identity, 10**9) for ranks in route_ranks),
            sum(ranks.get(identity, 10**6) for ranks in route_ranks),
            identity,
        ),
    )
    return tuple(ordered[:maximum])


def evaluate_route(
    rows: Sequence[CandidateScore],
    objects_by_id: Mapping[str, Mapping[str, Any]],
    *,
    target_source_record_ids: Sequence[str],
    reviewed_positive_object_ids: Sequence[str] = (),
    top_k: int,
) -> dict[str, Any]:
    target_sources = set(target_source_record_ids)
    target_objects = set(reviewed_positive_object_ids)
    source_rank = None
    object_rank = None
    candidates: list[dict[str, Any]] = []
    for rank, score in enumerate(rows, start=1):
        row = objects_by_id[score.compiled_object_id]
        lineage = set(str(value) for value in row.get("lineage_source_record_ids") or ())
        lineage.add(str(row["base_object_view"]["source_record_id"]))
        if source_rank is None and target_sources & lineage:
            source_rank = rank
        if object_rank is None and score.compiled_object_id in target_objects:
            object_rank = rank
        if rank <= top_k:
            base = row["base_object_view"]
            candidates.append(
                {
                    "rank": rank,
                    "compiled_object_id": score.compiled_object_id,
                    "source_record_id": str(base["source_record_id"]),
                    "lineage_source_record_ids": sorted(lineage),
                    "ticker": str(base["ticker"]),
                    "source_type": str(base["source_type"]),
                    "publication_date": str(base["publication_date"]),
                    "object_kind": str(row["object_kind"]),
                    "score": round(float(score.score), 8),
                    "excerpt": " ".join(str(row["model_text"]).split())[:500],
                    "candidate_not_evidence": True,
                    "numeric_authority": False,
                }
            )
    return {
        "source_record_target_rank": source_rank,
        "source_record_target_in_top_k": source_rank is not None and source_rank <= top_k,
        "reviewed_object_target_available": bool(target_objects),
        "reviewed_object_target_rank": object_rank,
        "reviewed_object_target_in_top_k": object_rank is not None and object_rank <= top_k,
        "candidates": candidates,
    }


def map_reviewed_objects_to_compiled_successors(
    compiled_objects: Sequence[Mapping[str, Any]],
    review_set: Mapping[str, Any],
) -> dict[str, Any]:
    by_source: dict[str, list[Mapping[str, Any]]] = {}
    for row in compiled_objects:
        source_id = str(row["base_object_view"]["source_record_id"])
        by_source.setdefault(source_id, []).append(row)
    review_views = {
        str(row["object_view_id"]): row for row in review_set.get("object_views") or ()
    }
    mappings: dict[str, dict[str, Any]] = {}
    unmapped: list[dict[str, Any]] = []
    for review_id, review in review_views.items():
        review_form = str(review.get("object_form") or "")
        if review_form not in {"claim", "parent_context"}:
            unmapped.append(
                {
                    "object_view_id": review_id,
                    "object_form": review_form,
                    "reason": "legacy_whole_object_form_not_projected_to_compiled_rows",
                }
            )
            continue
        surface = str(review.get("surface_text") or "")
        candidates: list[tuple[int, Mapping[str, Any], str]] = []
        for row in by_source.get(str(review.get("source_record_id") or ""), ()):
            kind = str(row.get("object_kind") or "")
            if review_form == "claim" and kind != "claim":
                continue
            if review_form == "parent_context" and kind != "bounded_parent_context":
                continue
            compiled_surface = str(row["base_object_view"].get("surface_text") or "")
            if compiled_surface == surface:
                candidates.append((0, row, "exact_surface"))
            elif surface and (surface in compiled_surface or compiled_surface in surface):
                candidates.append((1, row, "bounded_same_source_containment"))
        if not candidates:
            unmapped.append(
                {
                    "object_view_id": review_id,
                    "object_form": review_form,
                    "reason": "no_same_source_equivalent_compiled_surface",
                }
            )
            continue
        candidates.sort(
            key=lambda item: (item[0], len(str(item[1]["model_text"])), str(item[1]["compiled_object_id"]))
        )
        _, row, mapping_kind = candidates[0]
        mappings[review_id] = {
            "compiled_object_id": str(row["compiled_object_id"]),
            "mapping_kind": mapping_kind,
            "source_record_id": str(row["base_object_view"]["source_record_id"]),
            "label_authority": "successor_diagnostic_only_not_owner_accepted",
        }
    positives_by_query: dict[str, list[str]] = {}
    negatives_by_query: dict[str, list[str]] = {}
    for relation in review_set.get("query_relations") or ():
        mapped = mappings.get(str(relation.get("object_view_id") or ""))
        if mapped is None:
            continue
        destination = (
            positives_by_query
            if relation.get("relevance_judgement") == "positive"
            else negatives_by_query
            if relation.get("relevance_judgement") == "hard_negative"
            else None
        )
        if destination is not None:
            destination.setdefault(str(relation["qrel_id"]), []).append(
                str(mapped["compiled_object_id"])
            )
    return {
        "mapping_count": len(mappings),
        "unmapped_count": len(unmapped),
        "mappings": mappings,
        "unmapped": unmapped,
        "positive_compiled_object_ids_by_query": {
            key: sorted(set(values)) for key, values in sorted(positives_by_query.items())
        },
        "hard_negative_compiled_object_ids_by_query": {
            key: sorted(set(values)) for key, values in sorted(negatives_by_query.items())
        },
        "whole_table_projection_forbidden": True,
    }


def route_metrics(query_rows: Sequence[Mapping[str, Any]], route_id: str) -> dict[str, Any]:
    mapped = [row for row in query_rows if row["target_source_record_ids"]]
    source_hits = sum(
        bool(row["routes"][route_id]["source_record_target_in_top_k"])
        for row in mapped
    )
    object_judged = [
        row
        for row in query_rows
        if row["routes"][route_id]["reviewed_object_target_available"]
    ]
    object_hits = sum(
        bool(row["routes"][route_id]["reviewed_object_target_in_top_k"])
        for row in object_judged
    )
    reciprocal_ranks = [
        1.0 / int(row["routes"][route_id]["source_record_target_rank"])
        for row in mapped
        if row["routes"][route_id]["source_record_target_rank"] is not None
    ]
    return {
        "source_record_judged_query_count": len(mapped),
        "source_record_target_in_top_k_count": source_hits,
        "source_record_target_in_top_k_rate": _ratio(source_hits, len(mapped)),
        "source_record_mean_reciprocal_rank": round(
            sum(reciprocal_ranks) / len(mapped), 6
        ) if mapped else 0.0,
        "reviewed_object_judged_query_count": len(object_judged),
        "reviewed_object_target_in_top_k_count": object_hits,
        "reviewed_object_target_in_top_k_rate": _ratio(object_hits, len(object_judged)),
    }


def load_queries(payload: Mapping[str, Any]) -> tuple[RankingQuery, ...]:
    return load_ranking_queries(payload)


def _top_scores(
    objects: Sequence[Mapping[str, Any]],
    eligible_indices: np.ndarray,
    scores: np.ndarray,
    *,
    limit: int,
) -> list[CandidateScore]:
    if limit <= 0:
        raise ObjectRetrievalComparisonError("ranking_limit_invalid")
    pairs = [
        CandidateScore(
            compiled_object_id=str(objects[int(index)]["compiled_object_id"]),
            score=float(score),
        )
        for index, score in zip(eligible_indices, np.asarray(scores).reshape(-1))
    ]
    pairs.sort(key=lambda row: (-row.score, row.compiled_object_id))
    return pairs[:limit]


def _exclusion_reason(
    row: Mapping[str, Any],
    query: RankingQuery,
    as_of: date,
) -> str | None:
    base = row["base_object_view"]
    if str(base.get("ticker") or "").upper() != query.evidence_owner_ticker:
        return "outside_evidence_owner_scope"
    if str(base.get("source_type") or "").upper() not in set(query.form_types):
        return "source_type_not_allowed"
    if str(base.get("source_tier") or "") not in set(query.source_tiers):
        return "source_tier_not_allowed"
    try:
        publication = date.fromisoformat(str(base.get("publication_date") or ""))
    except ValueError:
        return "publication_date_missing_or_invalid"
    if publication > as_of:
        return "published_after_research_as_of"
    fiscal_year = base.get("fiscal_year")
    if (
        query.reporting_fiscal_years
        and fiscal_year not in {None, ""}
        and int(fiscal_year) not in set(query.reporting_fiscal_years)
    ):
        return "reporting_period_outside_query_scope"
    return None


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 6) if denominator else 0.0


__all__ = [
    "CandidateScore",
    "ObjectRetrievalComparisonError",
    "bm25_rank",
    "dense_rank",
    "eligible_object_indices",
    "evaluate_route",
    "load_compiled_objects",
    "load_queries",
    "map_reviewed_objects_to_compiled_successors",
    "route_metrics",
    "sparse_rank",
    "union_candidate_ids",
]
