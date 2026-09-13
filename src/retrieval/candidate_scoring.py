"""Production candidate scoring and request eligibility, independent of eval runners.

Algorithms extracted unchanged from the FIN 0.1.3 frozen implementations.
No qrels, labeled evaluation loader or shadow execution is part of serving.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable, Mapping, Sequence
import numpy as np
from rank_bm25 import BM25Okapi
from .text import tokenize
from .query_plan import QueryLane
from .route_compiler import QueryObjectFactRoutePolicy

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
                "fin_ia_compiled_financial_object_view_v1_2",
                "fin_ia_compiled_financial_object_view_v1_3",
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


class QueryAtomShadowError(ValueError):
    """Raised when a runtime-query shadow would weaken a hard boundary."""


def eligible_request_indices(
    objects: Sequence[Mapping[str, Any]],
    *,
    request: Any,
    lane: QueryLane,
    route_policy: QueryObjectFactRoutePolicy,
) -> tuple[np.ndarray, dict[str, int]]:
    """Apply the same hard boundary to a product request with one or more owners."""

    family = route_policy.family_by_facet().get(lane.facet_id)
    if family is None:
        raise QueryAtomShadowError("query_atom_facet_unrouted")
    object_kinds = {
        "bounded_parent_context" if form == "bounded_parent_context" else form
        for form in family.allowed_object_forms
    }
    fiscal_years = {int(value) for value in request.period.fiscal_years}
    as_of = date.fromisoformat(lane.publication_date_lte)
    owners = {value.upper() for value in lane.evidence_owner_tickers}
    if not owners:
        raise QueryAtomShadowError("query_request_evidence_owner_missing")
    eligible: list[int] = []
    exclusions: dict[str, int] = {}
    for index, row in enumerate(objects):
        reason = _request_object_exclusion_reason(
            row,
            owners=owners,
            as_of=as_of,
            source_types=lane.source_types,
            object_kinds=object_kinds,
            fiscal_years=fiscal_years,
            period_start=request.period.start_date,
            period_end=request.period.end_date,
        )
        if reason is None:
            eligible.append(index)
        else:
            exclusions[reason] = exclusions.get(reason, 0) + 1
    return np.asarray(eligible, dtype=np.int64), dict(sorted(exclusions.items()))


def _request_object_exclusion_reason(
    row: Mapping[str, Any],
    *,
    owners: set[str],
    as_of: date,
    source_types: Sequence[str],
    object_kinds: set[str],
    fiscal_years: set[int],
    period_start: date | None = None,
    period_end: date | None = None,
) -> str | None:
    base = row["base_object_view"]
    if str(base.get("ticker") or "").upper() not in owners:
        return "outside_evidence_owner_scope"
    try:
        published = date.fromisoformat(str(base.get("publication_date") or ""))
    except ValueError:
        return "publication_date_invalid"
    if published > as_of:
        return "after_research_as_of"
    if str(base.get("source_type") or "").upper() not in {
        value.upper() for value in source_types
    }:
        return "source_type_not_allowed"
    if str(row.get("object_kind") or "") not in object_kinds:
        return "object_form_not_allowed"
    raw_fiscal_year = base.get("fiscal_year")
    publication_outside_period = bool(
        (period_start is not None and published < period_start)
        or (period_end is not None and published > period_end)
    )
    if fiscal_years:
        if raw_fiscal_year is None:
            # Non-periodic official materials (for example issuer IR pages and
            # press releases) often have no fiscal-year field.  Bind those
            # rows to the request's explicit publication window instead of
            # discarding every otherwise-current source before retrieval.
            if period_start is None or period_end is None or publication_outside_period:
                return "reporting_period_outside_request"
        else:
            try:
                fiscal_year = int(raw_fiscal_year)
            except (TypeError, ValueError):
                return "reporting_period_outside_request"
            if fiscal_year not in fiscal_years:
                return "reporting_period_outside_request"
    elif publication_outside_period:
        return "reporting_period_outside_request"
    return None
