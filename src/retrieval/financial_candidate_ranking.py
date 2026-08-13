from __future__ import annotations

from datetime import date
import re
from typing import Any, Mapping, Sequence

from .evidence_role import evaluate_evidence_role
from .query_plan import QueryLane
from .text import tokenize


FINANCIAL_CANDIDATE_RANKING_SCHEMA_VERSION = (
    "fin_ia_financial_candidate_ranking_v1_0"
)

_ROLE_TIER = {"incompatible": 0, "abstain": 1, "compatible": 2}
_OBJECT_TIER = {
    "claim": 3,
    "metric_row": 2,
    "bounded_parent_context": 1,
    "parent_context": 1,
}
_SOURCE_TIER = {
    "primary_sec_filing": 3,
    "primary_official_ir": 3,
    "primary_company_ir": 3,
    "official_market_data": 3,
    "primary_regulator": 3,
    "secondary_industry": 2,
    "secondary_reputable": 1,
}


class FinancialCandidateRankingError(ValueError):
    """Raised when financial candidate ordering loses a hard query boundary."""


def _surface_integrity(text: str, object_kind: str) -> tuple[int, tuple[str, ...]]:
    if object_kind == "metric_row":
        return 1, ()
    stripped = text.strip()
    reasons: list[str] = []
    if len(stripped) < 32:
        reasons.append("surface_too_short")
    if stripped.startswith(("-", "–", "—", ";", ",")):
        reasons.append("fragment_like_leading_punctuation")
    if re.match(r"^[a-z][a-z-]{0,24}\s", stripped):
        reasons.append("fragment_like_lowercase_start")
    lowered = stripped.casefold()
    if any(
        value in lowered
        for value in (
            "table of contents",
            "investor relations contact",
            "conference call information",
        )
    ):
        reasons.append("navigation_or_contact_surface")
    return (0 if reasons else 1), tuple(sorted(set(reasons)))


def _anchor_projection(
    lane: QueryLane,
    text: str,
) -> tuple[int, int, tuple[tuple[str, ...], ...]]:
    tokens = set(tokenize(text))
    owner = lane.evidence_owner_tickers[0]
    owner_query = next(
        (
            query
            for query in lane.owner_queries
            if query.evidence_owner_ticker == owner
        ),
        None,
    )
    if owner_query is None:
        raise FinancialCandidateRankingError(
            "financial_candidate_owner_query_missing"
        )
    matched = tuple(
        group
        for group in owner_query.anchor_token_groups
        if group and set(group).issubset(tokens)
    )
    return len(matched), len(owner_query.anchor_token_groups), matched


def _source_role_binding(lane: QueryLane) -> str:
    relationship = lane.relationship_constraints[0]
    owner = lane.evidence_owner_tickers[0]
    if relationship == "subject_self_disclosure" and owner == lane.subject_ticker:
        observed = "issuer_disclosure"
    elif relationship != "subject_self_disclosure" and owner != lane.subject_ticker:
        observed = "related_entity_context"
    else:
        return "incompatible"
    return "compatible" if observed in lane.required_source_roles else "abstain"


def candidate_financial_features(
    row: Mapping[str, Any],
    *,
    lane: QueryLane,
    route_ranks: Mapping[str, int | None],
) -> dict[str, Any]:
    base = row["base_object_view"]
    object_id = str(row["compiled_object_id"])
    text = str(row.get("model_text") or "")
    object_kind = str(row.get("object_kind") or "")
    integrity_tier, integrity_reasons = _surface_integrity(text, object_kind)
    anchor_hits, anchor_total, matched_groups = _anchor_projection(lane, text)
    owner = lane.evidence_owner_tickers[0]
    relationship = lane.relationship_constraints[0]
    role = evaluate_evidence_role(
        {
            "ticker": base.get("ticker"),
            "section": base.get("section"),
            "subsection": base.get("subsection"),
            "source_type": base.get("source_type"),
            "object_kind": object_kind,
            "document_text": text,
        },
        slot_id=lane.slot_id,
        facet_id=lane.facet_id,
        subject_ticker=lane.subject_ticker,
        evidence_owner_ticker=owner,
        relationship_direction=relationship,
    )
    lowered = text.casefold()
    forbidden_hits = tuple(
        value
        for value in lane.forbidden_expansions
        if str(value).casefold() in lowered
    )
    active_ranks = {
        route_id: int(rank)
        for route_id, rank in route_ranks.items()
        if rank is not None
    }
    reciprocal_rank = sum(1.0 / (60.0 + rank) for rank in active_ranks.values())
    try:
        publication_ordinal = date.fromisoformat(
            str(base.get("publication_date") or "")
        ).toordinal()
    except ValueError as exc:
        raise FinancialCandidateRankingError(
            f"financial_candidate_publication_date_invalid:{object_id}"
        ) from exc
    source_role_binding = _source_role_binding(lane)
    features = {
        "schema_version": FINANCIAL_CANDIDATE_RANKING_SCHEMA_VERSION,
        "compiled_object_id": object_id,
        "surface_integrity": {
            "tier": integrity_tier,
            "reason_codes": list(integrity_reasons),
        },
        "query_constraints": {
            "anchor_hit_count": anchor_hits,
            "anchor_group_count": anchor_total,
            "matched_anchor_token_groups": [list(group) for group in matched_groups],
            "source_role_binding": source_role_binding,
            "relationship_direction": relationship,
            "forbidden_expansion_hits": list(forbidden_hits),
        },
        "evidence_role": {
            **role.as_dict(),
            "ranking_only": True,
            "abstain_is_not_rejection": True,
        },
        "object_directness_tier": _OBJECT_TIER.get(object_kind, 0),
        "source_authority_tier": _SOURCE_TIER.get(
            str(base.get("source_tier") or ""), 0
        ),
        "publication_ordinal": publication_ordinal,
        "route_count": len(active_ranks),
        "route_reciprocal_rank": round(reciprocal_rank, 12),
        "route_ranks": active_ranks,
        "candidate_not_evidence": True,
        "numeric_authority": False,
    }
    return features


def _ranking_key(features: Mapping[str, Any]) -> tuple[Any, ...]:
    constraints = features["query_constraints"]
    role = features["evidence_role"]
    integrity = features["surface_integrity"]
    return (
        -int(integrity["tier"]),
        -int(constraints["anchor_hit_count"] > 0),
        -int(constraints["anchor_hit_count"]),
        -_ROLE_TIER[str(role["compatibility"])],
        -int(constraints["source_role_binding"] == "compatible"),
        int(bool(constraints["forbidden_expansion_hits"])),
        -int(features["object_directness_tier"]),
        -int(features["source_authority_tier"]),
        -int(features["publication_ordinal"]),
        -int(features["route_count"]),
        -float(features["route_reciprocal_rank"]),
        str(features["compiled_object_id"]),
    )


def rank_financial_candidate_union(
    *,
    union_object_ids: Sequence[str],
    objects_by_id: Mapping[str, Mapping[str, Any]],
    lane: QueryLane,
    route_ranks_by_id: Mapping[str, Mapping[str, int | None]],
) -> tuple[dict[str, Any], ...]:
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    for object_id in union_object_ids:
        if object_id in seen:
            raise FinancialCandidateRankingError(
                "financial_candidate_union_identity_duplicate"
            )
        row = objects_by_id.get(object_id)
        if row is None:
            raise FinancialCandidateRankingError(
                f"financial_candidate_object_missing:{object_id}"
            )
        seen.add(object_id)
        rows.append(
            candidate_financial_features(
                row,
                lane=lane,
                route_ranks=route_ranks_by_id.get(object_id, {}),
            )
        )
    return tuple(sorted(rows, key=_ranking_key))


__all__ = [
    "FINANCIAL_CANDIDATE_RANKING_SCHEMA_VERSION",
    "FinancialCandidateRankingError",
    "candidate_financial_features",
    "rank_financial_candidate_union",
]
