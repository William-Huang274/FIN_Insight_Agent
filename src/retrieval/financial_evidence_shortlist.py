from __future__ import annotations

from datetime import date
import re
from typing import Any, Mapping, Sequence

from .evidence_role import evaluate_evidence_role
from .financial_intent import (
    combine_financial_evidence_compatibility,
    concept_aliases,
    evaluate_financial_intent,
)
from .query_plan import QueryLane


FINANCIAL_EVIDENCE_SHORTLIST_SCHEMA_VERSION = (
    "fin_ia_financial_evidence_shortlist_v1_2"
)

_COMPATIBILITY_TIER = {"incompatible": 0, "abstain": 1, "compatible": 2}
_NEED_SPECIFICITY = {
    "facet_role": 0,
    "exact_phrase": 1,
    "metric": 2,
    "product": 2,
    "metric_product": 3,
}
_SOURCE_TIER = {
    "primary_sec_filing": 3,
    "company_authored_unaudited_sec_filing": 3,
    "primary_official_ir": 3,
    "primary_company_ir": 3,
    "primary_company_disclosure": 3,
    "official_hosted_management_call_transcript": 3,
    "official_market_data": 3,
    "primary_regulator": 3,
    "secondary_industry": 2,
    "secondary_reputable": 1,
}

_FACET_ROLE_PRIORITY: Mapping[str, tuple[str, ...]] = {
    "reported_results": (
        "observed_operating_result",
        "financial_statement_or_reconciliation",
        "management_guidance",
    ),
    "cash_generation": (
        "financial_statement_or_reconciliation",
        "observed_operating_result",
    ),
    "pricing_and_mix": (
        "observed_operating_result",
        "financial_statement_or_reconciliation",
        "management_guidance",
    ),
    "margin_and_incremental_profit": (
        "observed_operating_result",
        "financial_statement_or_reconciliation",
    ),
    "downstream_demand_context": (
        "direct_demand_signal",
        "observed_operating_result",
        "demand_risk_or_counterevidence",
        "relationship_context",
        "supply_risk_or_counterevidence",
    ),
    "upstream_capacity_context": (
        "direct_supply_capacity_signal",
        "supply_risk_or_counterevidence",
        "relationship_context",
        "observed_operating_result",
    ),
    "subject_relationship_disclosure": (
        "relationship_context",
        "direct_demand_signal",
        "direct_supply_capacity_signal",
        "financial_statement_or_reconciliation",
    ),
    "counterparty_direct_mention": (
        "relationship_context",
        "direct_demand_signal",
        "direct_supply_capacity_signal",
    ),
    "issuer_counterevidence": (
        "demand_risk_or_counterevidence",
        "supply_risk_or_counterevidence",
        "regulatory_or_policy_exposure",
    ),
    "upstream_or_demand_counterevidence": (
        "demand_risk_or_counterevidence",
        "supply_risk_or_counterevidence",
        "regulatory_or_policy_exposure",
        "direct_supply_capacity_signal",
        "direct_demand_signal",
    ),
}


class FinancialEvidenceShortlistError(ValueError):
    """Raised when a bounded financial shortlist loses identity or lineage."""


def _role_priority(facet_id: str, labels: Sequence[str]) -> int:
    order = _FACET_ROLE_PRIORITY.get(facet_id, tuple(labels))
    width = len(order)
    return max(
        (width - index for index, role in enumerate(order) if role in labels),
        default=0,
    )


def _fact_specificity(
    *, text: str, object_kind: str, facet_id: str, labels: Sequence[str]
) -> int:
    lowered = text.casefold()
    if object_kind == "metric_row":
        return 4
    if facet_id in {"subject_relationship_disclosure", "counterparty_direct_mention"}:
        if any(
            phrase in lowered
            for phrase in (
                "binding commitment",
                "specific volumes",
                "customer agreement",
                "cash deposits",
                "contract terms",
            )
        ):
            return 4
    if "observed_operating_result" in labels and re.search(
        r"(?:\$|\b\d+(?:\.\d+)?%\b|\b(up|down)\s+\d+|\bversus\b)",
        lowered,
    ):
        return 4
    if any(
        role in labels
        for role in ("direct_demand_signal", "direct_supply_capacity_signal")
    ) and any(
        phrase in lowered
        for phrase in (
            "booked",
            "recognized",
            "shipments",
            "shipped",
            "deployed",
            "in production",
            "high-volume",
        )
    ):
        return 4
    if "risk factor" in lowered or any(
        role.endswith("risk_or_counterevidence") for role in labels
    ):
        return 3
    return 2 if labels else 0


def _route_projection(
    *, route_rows: Sequence[Mapping[str, Any]], object_kind: str, facet_id: str
) -> dict[str, Any]:
    ranks: dict[str, int] = {}
    for row in route_rows:
        route_id = str(row.get("route_id") or "")
        rank = int(row.get("rank") or 0)
        if route_id and rank > 0:
            ranks[route_id] = min(rank, ranks.get(route_id, rank))
    metric_facet = facet_id in {
        "reported_results",
        "cash_generation",
        "pricing_and_mix",
        "margin_and_incremental_profit",
    }
    exact_metric = ranks.get("typed_metric_row_exact") if object_kind == "metric_row" else None
    exact_phrase = ranks.get("typed_exact_phrase")
    bm25 = ranks.get("bm25_need_lexical")
    dense = min(
        (
            rank
            for route_id, rank in ranks.items()
            if route_id in {
                "qwen3_embedding_0_6b_dense",
                "bge_m3_dense",
                "bge_m3_learned_sparse",
            }
        ),
        default=None,
    )
    if metric_facet and exact_metric is not None:
        route_tier, best_rank = 4, exact_metric
    elif exact_phrase is not None:
        route_tier, best_rank = 3, exact_phrase
    elif bm25 is not None:
        route_tier, best_rank = 2, bm25
    elif dense is not None:
        route_tier, best_rank = 1, dense
    else:
        route_tier, best_rank = 0, 10**9
    return {
        "route_tier": route_tier,
        "best_qualified_route_rank": best_rank,
        "distinct_route_count": len(ranks),
        "best_rank_by_route": dict(sorted(ranks.items())),
    }


def _need_intents(
    need: Mapping[str, Any], *, ontology: Mapping[str, Any]
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return the one bounded intent combination represented by a need.

    A research request can ask for several distinct facts.  One candidate only
    has to satisfy one compiled retrieval need; requiring it to satisfy the
    entire request would suppress valid rows, footnotes and counterevidence.
    """

    kind = str(need.get("need_kind") or "")
    terms = tuple(str(value) for value in need.get("intent_terms") or ())
    if kind == "metric_product":
        return terms[:1], terms[1:2]
    if kind == "metric":
        return terms, ()
    if kind == "product":
        return (), terms
    if kind == "exact_phrase" and terms:
        metric_concept, _ = concept_aliases(
            terms[0], family="metric_concepts", ontology=ontology
        )
        if not metric_concept.startswith("unmapped::"):
            return terms[:1], ()
        product_concept, _ = concept_aliases(
            terms[0], family="product_concepts", ontology=ontology
        )
        if not product_concept.startswith("unmapped::"):
            return (), terms[:1]
    return (), ()


def _need_intent_selection(
    row: Mapping[str, Any],
    *,
    role_compatibility: str,
    route_rows: Sequence[Mapping[str, Any]],
    request: Mapping[str, Any],
    ontology: Mapping[str, Any],
    retrieval_needs: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    request_has_typed_intent = bool(
        request.get("metric_intents") or request.get("product_intents")
    )
    for need in retrieval_needs:
        need_id = str(need.get("need_id") or "")
        if not need_id:
            raise FinancialEvidenceShortlistError(
                "financial_shortlist_retrieval_need_id_missing"
            )
        metric_intents, product_intents = _need_intents(
            need, ontology=ontology
        )
        has_typed_intent = bool(metric_intents or product_intents)
        if has_typed_intent:
            intent = evaluate_financial_intent(
                row,
                metric_intents=metric_intents,
                product_intents=product_intents,
                acceptable_proxy=bool(request.get("acceptable_proxy")),
                ontology=ontology,
            ).as_dict()
        else:
            intent = {
                "schema_version": "fin_ia_financial_intent_evaluation_v1_1",
                "compatibility": "abstain",
                "metric_compatibility": "not_requested",
                "product_compatibility": "not_requested",
                "requested_metric_concepts": [],
                "requested_product_concepts": [],
                "observed_metric_concept": None,
                "matched_metric_aliases": [],
                "matched_product_aliases": [],
                "matched_product_supporting_terms": [],
                "matched_product_proxy_terms": [],
                "matched_product_exclusion_terms": [],
                "reason_codes": ["retrieval_need_has_no_typed_financial_intent"],
                "candidate_not_evidence": True,
            }
        composite = (
            "abstain"
            if request_has_typed_intent and not has_typed_intent
            else combine_financial_evidence_compatibility(
                role_compatibility=role_compatibility,
                intent_compatibility=str(intent["compatibility"]),
                has_typed_intent=has_typed_intent,
            )
        )
        need_route_rows = [
            value
            for value in route_rows
            if str(value.get("need_id") or "") == need_id
        ]
        route = _route_projection(
            route_rows=need_route_rows,
            object_kind=str(row.get("object_kind") or ""),
            facet_id=str(need.get("facet_id") or ""),
        )
        candidates.append(
            {
                "need_id": need_id,
                "need_kind": str(need.get("need_kind") or ""),
                "need_specificity": _NEED_SPECIFICITY.get(
                    str(need.get("need_kind") or ""), 0
                ),
                "intent_terms": list(need.get("intent_terms") or ()),
                "has_typed_intent": has_typed_intent,
                "financial_intent": intent,
                "composite_compatibility": composite,
                "route_projection": route,
            }
        )
    if not candidates:
        raise FinancialEvidenceShortlistError(
            "financial_shortlist_retrieval_needs_empty"
        )
    return min(
        candidates,
        key=lambda value: (
            -_COMPATIBILITY_TIER[str(value["composite_compatibility"])],
            -_COMPATIBILITY_TIER[
                str(value["financial_intent"]["compatibility"])
            ],
            -int(value["need_specificity"]),
            -int(value["route_projection"]["route_tier"]),
            int(value["route_projection"]["best_qualified_route_rank"]),
            str(value["need_id"]),
        ),
    )


def candidate_shortlist_features(
    row: Mapping[str, Any],
    *,
    lane: QueryLane,
    route_rows: Sequence[Mapping[str, Any]],
    union_rank: int,
    cross_encoder_ranks: Mapping[str, int | None],
    request: Mapping[str, Any] | None = None,
    intent_ontology: Mapping[str, Any] | None = None,
    retrieval_needs: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    base = row["base_object_view"]
    object_id = str(row["compiled_object_id"])
    object_kind = str(row.get("object_kind") or "")
    text = str(row.get("model_text") or "")
    role = evaluate_evidence_role(
        {
            "ticker": base.get("ticker"),
            "section": base.get("section"),
            "subsection": base.get("subsection"),
            "source_type": base.get("source_type"),
            "object_kind": object_kind,
            "document_text": text,
            "structured_projection": row.get("structured_projection"),
        },
        slot_id=lane.slot_id,
        facet_id=lane.facet_id,
        subject_ticker=lane.subject_ticker,
        evidence_owner_ticker=lane.evidence_owner_tickers[0],
        relationship_direction=lane.relationship_constraints[0],
    )
    try:
        publication_ordinal = date.fromisoformat(
            str(base.get("publication_date") or "")
        ).toordinal()
    except ValueError as exc:
        raise FinancialEvidenceShortlistError(
            f"financial_shortlist_publication_date_invalid:{object_id}"
        ) from exc
    finite_cross_ranks = [
        int(value) for value in cross_encoder_ranks.values() if value is not None
    ]
    if (request is None) != (intent_ontology is None):
        raise FinancialEvidenceShortlistError(
            "financial_shortlist_intent_inputs_incomplete"
        )
    if request is not None and intent_ontology is not None and retrieval_needs:
        need_selection = _need_intent_selection(
            row,
            role_compatibility=str(role.compatibility),
            route_rows=route_rows,
            request=request,
            ontology=intent_ontology,
            retrieval_needs=retrieval_needs,
        )
        financial_intent = need_selection["financial_intent"]
        composite_compatibility = need_selection["composite_compatibility"]
        route = need_selection["route_projection"]
        best_need = {
            key: need_selection[key]
            for key in (
                "need_id",
                "need_kind",
                "need_specificity",
                "intent_terms",
                "has_typed_intent",
            )
        }
    else:
        route = _route_projection(
            route_rows=route_rows,
            object_kind=object_kind,
            facet_id=lane.facet_id,
        )
        financial_intent = (
            evaluate_financial_intent(
                row,
                metric_intents=tuple(request.get("metric_intents") or ()),
                product_intents=tuple(request.get("product_intents") or ()),
                acceptable_proxy=bool(request.get("acceptable_proxy")),
                ontology=intent_ontology,
            ).as_dict()
            if request is not None and intent_ontology is not None
            else {
                "compatibility": "abstain",
                "reason_codes": ["financial_intent_not_supplied"],
                "candidate_not_evidence": True,
            }
        )
        has_typed_intent = bool(
            request is not None
            and (request.get("metric_intents") or request.get("product_intents"))
        )
        composite_compatibility = combine_financial_evidence_compatibility(
            role_compatibility=str(role.compatibility),
            intent_compatibility=str(financial_intent["compatibility"]),
            has_typed_intent=has_typed_intent,
        )
        best_need = None
    return {
        "schema_version": FINANCIAL_EVIDENCE_SHORTLIST_SCHEMA_VERSION,
        "compiled_object_id": object_id,
        "evidence_role": role.as_dict(),
        "financial_intent": financial_intent,
        "composite_compatibility": composite_compatibility,
        "best_retrieval_need": best_need,
        "role_priority": _role_priority(lane.facet_id, role.labels),
        "fact_specificity": _fact_specificity(
            text=text,
            object_kind=object_kind,
            facet_id=lane.facet_id,
            labels=role.labels,
        ),
        "route_projection": route,
        "source_authority_tier": _SOURCE_TIER.get(
            str(base.get("source_tier") or ""), 0
        ),
        "publication_ordinal": publication_ordinal,
        "union_rank": int(union_rank),
        "best_cross_encoder_rank": min(finite_cross_ranks, default=10**9),
        "cross_encoder_ranks": dict(cross_encoder_ranks),
        "candidate_not_evidence": True,
        "numeric_authority": False,
    }


def _ranking_key(features: Mapping[str, Any]) -> tuple[Any, ...]:
    intent = features["financial_intent"]
    role = features["evidence_role"]
    route = features["route_projection"]
    return (
        -_COMPATIBILITY_TIER[str(features["composite_compatibility"])],
        -_COMPATIBILITY_TIER[str(intent["compatibility"])],
        -_COMPATIBILITY_TIER[str(role["compatibility"])],
        -int((features.get("best_retrieval_need") or {}).get("need_specificity") or 0),
        -int(features["role_priority"]),
        -int(features["fact_specificity"]),
        -int(route["route_tier"]),
        int(route["best_qualified_route_rank"]),
        -int(features["source_authority_tier"]),
        -int(route["distinct_route_count"]),
        int(features["best_cross_encoder_rank"]),
        -int(features["publication_ordinal"]),
        int(features["union_rank"]),
        str(features["compiled_object_id"]),
    )


def rank_financial_evidence_shortlist(
    *,
    union_object_ids: Sequence[str],
    objects_by_id: Mapping[str, Mapping[str, Any]],
    lane: QueryLane,
    route_membership: Mapping[str, Sequence[Mapping[str, Any]]],
    cross_encoder_ranks_by_id: Mapping[str, Mapping[str, int | None]],
    request: Mapping[str, Any] | None = None,
    intent_ontology: Mapping[str, Any] | None = None,
    retrieval_needs: Sequence[Mapping[str, Any]] | None = None,
) -> tuple[dict[str, Any], ...]:
    if len(union_object_ids) != len(set(union_object_ids)):
        raise FinancialEvidenceShortlistError("financial_shortlist_candidate_duplicate")
    rows: list[dict[str, Any]] = []
    for union_rank, object_id in enumerate(union_object_ids, start=1):
        obj = objects_by_id.get(object_id)
        if obj is None:
            raise FinancialEvidenceShortlistError(
                f"financial_shortlist_object_missing:{object_id}"
            )
        rows.append(
            candidate_shortlist_features(
                obj,
                lane=lane,
                route_rows=route_membership.get(object_id, ()),
                union_rank=union_rank,
                cross_encoder_ranks=cross_encoder_ranks_by_id.get(object_id, {}),
                request=request,
                intent_ontology=intent_ontology,
                retrieval_needs=retrieval_needs,
            )
        )
    return tuple(sorted(rows, key=_ranking_key))


__all__ = [
    "FINANCIAL_EVIDENCE_SHORTLIST_SCHEMA_VERSION",
    "FinancialEvidenceShortlistError",
    "candidate_shortlist_features",
    "rank_financial_evidence_shortlist",
]
