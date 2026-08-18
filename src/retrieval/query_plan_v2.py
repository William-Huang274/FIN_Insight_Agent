from __future__ import annotations

from dataclasses import replace
import re
from typing import Iterable

from .contracts import EvidenceRequest, FinancialResearchKernel
from .query_plan import (
    OwnerQuery,
    QueryFacetPlan,
    QueryLane,
    canonical_digest,
    compile_query_facet_plan as compile_query_facet_plan_v1,
    compile_query_facet_plan_for_request as compile_query_facet_plan_for_request_v1,
)
from .text import tokenize


QUERY_PLAN_V2_SCHEMA_VERSION = "fin_ia_typed_query_facet_plan_v1_1"


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


def compile_query_facet_plan(
    kernel: FinancialResearchKernel,
    case_key: str,
) -> QueryFacetPlan:
    """Keep the frozen broad case plan unchanged."""

    return compile_query_facet_plan_v1(kernel, case_key)


def compile_query_facet_plan_for_request(
    kernel: FinancialResearchKernel,
    request: EvidenceRequest,
) -> QueryFacetPlan:
    """Compile a typed request without polluting every lane with broad pack terms.

    The frozen v1 compiler remains the authority for identity, source, relation,
    facet and semantic boundaries.  V2 only narrows lexical/exact surfaces to
    terms explicitly present in the EvidenceRequest.  It does not consult
    qrels, result IDs, URLs, scores or a ticker-specific branch.
    """

    base = compile_query_facet_plan_for_request_v1(kernel, request)
    request_terms = _unique((*request.metric_intents, *request.product_intents))
    if not request_terms:
        return base

    lexical_tokens = _unique(
        token for term in request_terms for token in tokenize(term)
    )
    anchors = tuple(
        tokens
        for term in request_terms
        if 1 <= len(tokens := tuple(tokenize(term))) <= 8
    )
    lanes: list[QueryLane] = []
    for lane in base.lanes:
        aliases = _unique(
            match.group(1)
            for query in lane.exact_queries
            if (match := re.match(r'^"([^"]+)"', query)) is not None
        )
        exact_queries = _unique(
            f'"{alias}" "{term}"'
            for alias in aliases
            for term in request_terms
        )
        owner_queries = tuple(
            replace(
                owner_query,
                lexical_query=" ".join(request_terms),
                lexical_tokens=lexical_tokens,
                anchor_token_groups=anchors,
            )
            for owner_query in lane.owner_queries
        )
        lanes.append(
            replace(
                lane,
                exact_queries=exact_queries,
                lexical_query=" ".join(request_terms),
                lexical_tokens=lexical_tokens,
                owner_queries=owner_queries,
            )
        )

    unsigned = {
        "schema_version": QUERY_PLAN_V2_SCHEMA_VERSION,
        "case_key": base.case_key,
        "subject_ticker": base.subject_ticker,
        "subject_legal_name": base.subject_legal_name,
        "research_as_of": base.research_as_of,
        "industry_pack_id": base.industry_pack_id,
        "lanes": [lane.as_dict() for lane in lanes],
    }
    return QueryFacetPlan(
        schema_version=QUERY_PLAN_V2_SCHEMA_VERSION,
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
    "QUERY_PLAN_V2_SCHEMA_VERSION",
    "QueryFacetPlan",
    "QueryLane",
    "canonical_digest",
    "compile_query_facet_plan",
    "compile_query_facet_plan_for_request",
]
