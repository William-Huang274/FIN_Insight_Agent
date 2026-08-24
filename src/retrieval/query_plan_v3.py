from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Any, Iterable, Mapping

from .contracts import EvidenceRequest, FinancialResearchKernel
from .financial_intent_v3 import (
    concept_aliases,
    validate_financial_intent_ontology,
)
from .query_plan import (
    OwnerQuery,
    QueryFacetPlan,
    QueryLane as QueryLaneV1,
    canonical_digest,
    compile_query_facet_plan as compile_query_facet_plan_v1,
    compile_query_facet_plan_for_request as compile_query_facet_plan_for_request_v1,
)
from .text import tokenize


QUERY_PLAN_V3_SCHEMA_VERSION = "fin_ia_typed_query_facet_plan_v1_2"
QUERY_PLAN_V3_GROUPED_RECALL_SCHEMA_VERSION = (
    "fin_ia_typed_query_facet_plan_v1_3"
)


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    output: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = str(raw).strip()
        key = value.casefold()
        if value and key not in seen:
            output.append(value)
            seen.add(key)
    return tuple(output)


@dataclass(frozen=True)
class TypedLexicalSubquery:
    query_id: str
    query_kind: str
    concept_id: str | None
    lexical_query: str
    lexical_tokens: tuple[str, ...]
    candidate_only: bool = True

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class QueryLane(QueryLaneV1):
    lexical_subqueries: tuple[TypedLexicalSubquery, ...]


def _concept_surface(
    intent: str,
    *,
    family: str,
    ontology: Mapping[str, Any],
) -> tuple[
    str,
    tuple[str, ...],
    tuple[str, ...],
    tuple[tuple[str, tuple[str, ...]], ...],
]:
    concepts = ontology.get(family) or {}
    if intent in concepts:
        concept_id = str(intent)
        raw = concepts[concept_id]
        aliases = _unique(raw.get("aliases") or ())
    else:
        concept_id, aliases = concept_aliases(
            intent,
            family=family,
            ontology=ontology,
        )
        raw = concepts.get(concept_id) or {}
    supporting = (
        _unique(raw.get("supporting_terms") or ())
        if family == "product_concepts"
        else ()
    )
    recall_groups = (
        tuple(
            (str(group_id), _unique(terms or ()))
            for group_id, terms in (
                raw.get("recall_surface_groups") or {}
            ).items()
        )
        if family == "product_concepts"
        else ()
    )
    return concept_id, aliases, supporting, recall_groups


def _subquery(
    *,
    query_id: str,
    query_kind: str,
    concept_id: str | None,
    terms: Iterable[str],
) -> TypedLexicalSubquery | None:
    values = _unique(terms)
    tokens = _unique(token for term in values for token in tokenize(term))
    if not tokens:
        return None
    return TypedLexicalSubquery(
        query_id=query_id,
        query_kind=query_kind,
        concept_id=concept_id,
        lexical_query=" ".join(values),
        lexical_tokens=tokens,
    )


def compile_query_facet_plan(
    kernel: FinancialResearchKernel,
    case_key: str,
) -> QueryFacetPlan:
    """Keep the frozen broad case plan unchanged for historical replay."""

    return compile_query_facet_plan_v1(kernel, case_key)


def compile_query_facet_plan_for_request(
    kernel: FinancialResearchKernel,
    request: EvidenceRequest,
    *,
    ontology: Mapping[str, Any] | None = None,
    grouped_surface_recall_enabled: bool = False,
) -> QueryFacetPlan:
    """Compile a request into balanced, typed lexical recall surfaces.

    Identity, source, period, relationship and facet constraints remain owned
    by the frozen v1 compiler.  This successor stops one broad bag of words
    from crowding out a material business concept: the raw request, metric
    aliases and every product concept receive separate candidate-only lexical
    subqueries.  No result IDs, URLs, qrels, case branches or Evidence
    authority enter the compiler.
    """

    base = compile_query_facet_plan_for_request_v1(kernel, request)
    request_terms = _unique((*request.metric_intents, *request.product_intents))
    if ontology is not None:
        validate_financial_intent_ontology(ontology)

    metric_surfaces: list[str] = []
    product_groups: list[
        tuple[
            str,
            tuple[str, ...],
            tuple[tuple[str, tuple[str, ...]], ...],
        ]
    ] = []
    if ontology is not None:
        for intent in request.metric_intents:
            _, aliases, _, _ = _concept_surface(
                intent,
                family="metric_concepts",
                ontology=ontology,
            )
            metric_surfaces.extend(aliases)
        for intent in request.product_intents:
            concept_id, aliases, supporting, recall_groups = _concept_surface(
                intent,
                family="product_concepts",
                ontology=ontology,
            )
            product_groups.append(
                (
                    concept_id,
                    _unique((*aliases, *supporting)),
                    recall_groups,
                )
            )
    else:
        metric_surfaces.extend(request.metric_intents)
        product_groups.extend(
            (f"unmapped::{intent.casefold()}", (intent,), ())
            for intent in request.product_intents
        )

    product_primary_surfaces = [
        surfaces[0] for _, surfaces, _ in product_groups if surfaces
    ]
    query_rows: list[TypedLexicalSubquery] = []
    for row in (
        _subquery(
            query_id="request_core",
            query_kind="request_core",
            concept_id=None,
            terms=request_terms,
        ),
        _subquery(
            query_id="metric_core",
            query_kind="metric_aliases_with_product_anchors",
            concept_id=None,
            terms=(*metric_surfaces, *product_primary_surfaces),
        ),
    ):
        if row is not None:
            query_rows.append(row)
    for index, (concept_id, surfaces, recall_groups) in enumerate(
        product_groups,
        start=1,
    ):
        row = _subquery(
            query_id=f"product_{index:02d}",
            query_kind="product_aliases_and_disclosure_surfaces",
            concept_id=concept_id,
            terms=(*surfaces, *metric_surfaces),
        )
        if row is not None:
            query_rows.append(row)
        if grouped_surface_recall_enabled:
            for group_index, (group_id, group_terms) in enumerate(
                recall_groups,
                start=1,
            ):
                group_row = _subquery(
                    query_id=(
                        f"product_{index:02d}_surface_{group_index:02d}"
                    ),
                    query_kind="product_grouped_disclosure_surface",
                    concept_id=f"{concept_id}::{group_id}",
                    terms=group_terms,
                )
                if group_row is not None:
                    query_rows.append(group_row)
    if not query_rows:
        for lane in base.lanes:
            row = _subquery(
                query_id="facet_fallback",
                query_kind="frozen_facet_fallback",
                concept_id=None,
                terms=(lane.lexical_query,),
            )
            if row is not None:
                query_rows.append(row)

    deduplicated_subqueries: list[TypedLexicalSubquery] = []
    seen_queries: set[str] = set()
    for row in query_rows:
        key = row.lexical_query.casefold()
        if key not in seen_queries:
            deduplicated_subqueries.append(row)
            seen_queries.add(key)

    focused_terms = request_terms or tuple(
        term
        for lane in base.lanes
        for term in lane.lexical_query.split()
    )
    focused_tokens = _unique(
        token for term in focused_terms for token in tokenize(term)
    )
    semantic_surfaces = _unique(
        (
            *metric_surfaces,
            *(term for _, rows, _ in product_groups for term in rows),
            *(
                term
                for _, _, groups in product_groups
                for _, group_terms in groups
                for term in group_terms
            ),
        )
    )
    lanes: list[QueryLane] = []
    for lane in base.lanes:
        owner_queries = tuple(
            replace(
                owner_query,
                lexical_query=" ".join(focused_terms),
                lexical_tokens=focused_tokens,
                anchor_token_groups=tuple(
                    tuple(tokenize(term))
                    for term in focused_terms
                    if tokenize(term)
                ),
            )
            for owner_query in lane.owner_queries
        )
        semantic_query = lane.semantic_query
        if semantic_surfaces:
            semantic_query += (
                " 可用于候选召回、但不授予证据权威的财报表面包括："
                f"{'、'.join(semantic_surfaces)}。"
            )
        lanes.append(
            QueryLane(
                **{
                    **lane.as_dict(),
                    "lexical_query": " ".join(focused_terms),
                    "lexical_tokens": focused_tokens,
                    "owner_queries": owner_queries,
                    "semantic_query": semantic_query,
                    "lexical_subqueries": tuple(deduplicated_subqueries),
                }
            )
        )

    unsigned = {
        "schema_version": (
            QUERY_PLAN_V3_GROUPED_RECALL_SCHEMA_VERSION
            if grouped_surface_recall_enabled
            else QUERY_PLAN_V3_SCHEMA_VERSION
        ),
        "case_key": base.case_key,
        "subject_ticker": base.subject_ticker,
        "subject_legal_name": base.subject_legal_name,
        "research_as_of": base.research_as_of,
        "industry_pack_id": base.industry_pack_id,
        "lanes": [lane.as_dict() for lane in lanes],
    }
    return QueryFacetPlan(
        schema_version=(
            QUERY_PLAN_V3_GROUPED_RECALL_SCHEMA_VERSION
            if grouped_surface_recall_enabled
            else QUERY_PLAN_V3_SCHEMA_VERSION
        ),
        case_key=base.case_key,
        subject_ticker=base.subject_ticker,
        subject_legal_name=base.subject_legal_name,
        research_as_of=base.research_as_of,
        industry_pack_id=base.industry_pack_id,
        lanes=tuple(lanes),
        plan_digest=canonical_digest(unsigned),
    )


__all__ = [
    "OwnerQuery",
    "QUERY_PLAN_V3_SCHEMA_VERSION",
    "QUERY_PLAN_V3_GROUPED_RECALL_SCHEMA_VERSION",
    "QueryFacetPlan",
    "QueryLane",
    "TypedLexicalSubquery",
    "canonical_digest",
    "compile_query_facet_plan",
    "compile_query_facet_plan_for_request",
]
