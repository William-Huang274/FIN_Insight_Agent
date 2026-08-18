from __future__ import annotations

from dataclasses import replace
import re
from typing import Any, Mapping, Sequence

from .evidence_role import (
    EVIDENCE_ROLES,
    FACET_COMPATIBLE_ROLES,
    LEGACY_EVIDENCE_SLOT_MAP,
    ROLE_DIRECT_DEMAND,
    ROLE_GENERIC,
    ROLE_OBSERVED_RESULT,
    SLOT_COMPATIBLE_ROLES,
    EvidenceRoleEvaluation,
    evaluate_evidence_role as evaluate_evidence_role_v1,
)


EVIDENCE_ROLE_V2_SCHEMA_VERSION = "fin_ia_evidence_role_evaluation_v1_1"
ROLE_MECHANISM_CONTEXT = "mechanism_or_definition_context"
EVIDENCE_ROLES_V2 = frozenset({*EVIDENCE_ROLES, ROLE_MECHANISM_CONTEXT})

_MECHANISM_COMPATIBLE_FACETS = frozenset(
    {
        "orders_and_backlog",
        "conversion_and_durability",
        "downstream_demand_context",
        "reported_results",
        "pricing_and_mix",
        "margin_and_incremental_profit",
    }
)
_MECHANISM_COMPATIBLE_SLOTS = frozenset(
    {"demand_volume_quality", "operating_performance", "pricing_mix_value_capture"}
)
_DEMAND_FACETS = frozenset(
    {"orders_and_backlog", "conversion_and_durability", "downstream_demand_context"}
)


def _normalized_surface(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.casefold()).split())


def _contains_request_surface(text: str, terms: Sequence[str]) -> bool:
    normalized_text = _normalized_surface(text)
    return any(
        normalized
        and re.search(
            rf"(?<![a-z0-9]){re.escape(normalized)}(?![a-z0-9])",
            normalized_text,
        )
        for normalized in (_normalized_surface(str(value)) for value in terms)
    )


def _strict_observed_change(text: str) -> bool:
    return bool(
        re.search(
            r"\b(was|were|grew|increased|decreased|rose|declined|generated|reported|"
            r"accounted for|driven by|resulted in|versus)\b|"
            r"\b(up|down)\s+\d+(?:\.\d+)?%|"
            r"\byear over year\b|"
            r"\brecord\s+(?:quarterly\s+)?(?:revenue|sales|income|cash flow)\b",
            text,
        )
    )


def _mechanism_or_definition(text: str) -> bool:
    return any(
        value in text
        for value in (
            "defined as",
            "is achieved through",
            "was primarily attributable to",
            "were primarily attributable to",
            "positively impacted by",
            "negatively impacted by",
            "driven by",
            "consists of",
            "primarily from",
        )
    )


def evaluate_evidence_role(
    row: Mapping[str, Any],
    *,
    slot_id: str,
    subject_ticker: str,
    facet_id: str | None = None,
    evidence_owner_ticker: str | None = None,
    relationship_direction: str | None = None,
    request_intent_terms: Sequence[str] = (),
) -> EvidenceRoleEvaluation:
    """Add request-bound financial role evidence without industry branches."""

    base = evaluate_evidence_role_v1(
        row,
        slot_id=slot_id,
        subject_ticker=subject_ticker,
        facet_id=facet_id,
        evidence_owner_ticker=evidence_owner_ticker,
        relationship_direction=relationship_direction,
    )
    text = str(row.get("document_text") or row.get("model_text") or "").casefold()
    section = " ".join(
        str(row.get(value) or "").casefold()
        for value in ("section", "subsection")
    )
    request_match = _contains_request_surface(text, request_intent_terms)
    strict_observed = _strict_observed_change(text)
    risk_section = "risk factor" in section or "item 1a" in section
    labels = set(base.labels)
    reasons = set(base.reason_codes)

    if ROLE_OBSERVED_RESULT in labels and not strict_observed:
        labels.remove(ROLE_OBSERVED_RESULT)
        reasons.add("recognized_without_observed_change_not_result")
    if request_match and _mechanism_or_definition(text) and not risk_section:
        labels.add(ROLE_MECHANISM_CONTEXT)
        reasons.add("request_bound_mechanism_or_definition_surface")
    if request_match and strict_observed and not risk_section:
        if facet_id in _DEMAND_FACETS:
            labels.add(ROLE_DIRECT_DEMAND)
            reasons.add("request_bound_observed_demand_surface")
        elif facet_id in {
            "reported_results",
            "pricing_and_mix",
            "margin_and_incremental_profit",
        }:
            labels.add(ROLE_OBSERVED_RESULT)
            reasons.add("request_bound_observed_result_surface")

    compatible_roles = set(
        FACET_COMPATIBLE_ROLES[facet_id]
        if facet_id is not None
        else SLOT_COMPATIBLE_ROLES[slot_id]
    )
    if (
        facet_id in _MECHANISM_COMPATIBLE_FACETS
        or (facet_id is None and slot_id in _MECHANISM_COMPATIBLE_SLOTS)
    ):
        compatible_roles.add(ROLE_MECHANISM_CONTEXT)
    if ROLE_GENERIC in labels:
        compatibility = "incompatible"
    elif labels.intersection(compatible_roles):
        compatibility = "compatible"
        reasons.discard("no_qualified_financial_role_detected")
    elif labels:
        compatibility = "incompatible"
    else:
        compatibility = "abstain"
        reasons.add("no_qualified_financial_role_detected")
    return replace(
        base,
        schema_version=EVIDENCE_ROLE_V2_SCHEMA_VERSION,
        labels=tuple(sorted(labels)),
        compatibility=compatibility,
        reason_codes=tuple(sorted(reasons)),
        decision_basis="deterministic_request_bound_financial_role_rules_v2",
    )


__all__ = [
    "EVIDENCE_ROLES_V2",
    "EVIDENCE_ROLE_V2_SCHEMA_VERSION",
    "EvidenceRoleEvaluation",
    "LEGACY_EVIDENCE_SLOT_MAP",
    "ROLE_MECHANISM_CONTEXT",
    "evaluate_evidence_role",
]
