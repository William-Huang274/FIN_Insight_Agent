from __future__ import annotations

from dataclasses import replace
import re
from typing import Any, Mapping, Sequence

from .evidence_role import ROLE_DIRECT_DEMAND, ROLE_GENERIC, EvidenceRoleEvaluation
from .evidence_role_v2 import (
    EVIDENCE_ROLES_V2,
    LEGACY_EVIDENCE_SLOT_MAP,
    ROLE_MECHANISM_CONTEXT,
    evaluate_evidence_role as evaluate_evidence_role_v2,
)


EVIDENCE_ROLE_V3_SCHEMA_VERSION = "fin_ia_evidence_role_evaluation_v1_2"
EVIDENCE_ROLES_V3 = EVIDENCE_ROLES_V2


def _has_executed_customer_commitment(text: str) -> bool:
    """Recognize an executed purchase structure, not a possible future one."""

    surface = " ".join(str(text).casefold().split())
    agreement = any(
        value in surface
        for value in (
            "customer agreement",
            "customer agreements",
            "strategic customer agreement",
            "strategic customer agreements",
            "take-or-pay agreement",
            "take-or-pay agreements",
        )
    )
    material_term = any(
        value in surface
        for value in (
            "binding commitment",
            "binding commitments",
            "specific volume",
            "specific volumes",
            "contractually enforceable volume",
            "contractually enforceable volumes",
            "customer deposit",
            "customer deposits",
            "cash deposit",
            "cash deposits",
            "take-or-pay",
        )
    )
    executed = bool(
        re.search(
            r"\b(?:we\s+)?(?:have\s+)?entered\s+into\b|"
            r"\b(?:these\s+)?(?:strategic\s+)?customer agreements?\s+"
            r"(?:include|includes|contain|contains|provide|provides|are structured)\b|"
            r"\b(?:have|has)\s+binding commitments?\b|"
            r"\b(?:received|have received|has received)\s+(?:customer|cash) deposits?\b",
            surface,
        )
    )
    hypothetical = bool(
        re.search(
            r"\b(?:may|might|could|would|plan to|plans to|intend to|intends to)\s+"
            r"(?:enter|include|contain|require|obtain|receive)\b",
            surface,
        )
    )
    return agreement and material_term and executed and not hypothetical


def _has_observed_demand_fulfillment(text: str) -> bool:
    """Recognize completed customer-facing shipment/qualification activity."""

    surface = " ".join(str(text).casefold().split())
    observed_shipment = bool(
        re.search(
            r"\b(?:began|commenced|started|completed)\s+(?:high-volume\s+)?shipments?\b|"
            r"\b(?:has|have|had)\s+shipped\b|"
            r"\bqualification samples?\s+(?:were\s+)?shipped\b|"
            r"\bhigh-volume shipments?\b",
            surface,
        )
    )
    customer_binding = any(
        value in surface
        for value in (
            "customer",
            "customer's platform",
            "customers' platforms",
            "lead platform",
            "qualification sample",
        )
    )
    hypothetical = bool(
        re.search(
            r"\b(?:may|might|could|would|expect to|expects to|plan to|plans to)\s+"
            r"(?:ship|begin shipments|commence shipments|start shipments)\b",
            surface,
        )
    )
    return observed_shipment and customer_binding and not hypothetical


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
    """Extend frozen v2 with observed commitments and customer fulfilment."""

    base = evaluate_evidence_role_v2(
        row,
        slot_id=slot_id,
        subject_ticker=subject_ticker,
        facet_id=facet_id,
        evidence_owner_ticker=evidence_owner_ticker,
        relationship_direction=relationship_direction,
        request_intent_terms=request_intent_terms,
    )
    text = str(row.get("document_text") or row.get("model_text") or "")
    labels = set(base.labels)
    reasons = set(base.reason_codes)
    added_direct_demand = False

    if _has_executed_customer_commitment(text):
        labels.add(ROLE_DIRECT_DEMAND)
        reasons.add("executed_customer_commitment_surface")
        added_direct_demand = True
    if (
        facet_id in {"orders_and_backlog", "conversion_and_durability"}
        and _has_observed_demand_fulfillment(text)
    ):
        labels.add(ROLE_DIRECT_DEMAND)
        reasons.add("observed_customer_fulfillment_surface")
        added_direct_demand = True

    compatibility = base.compatibility
    if added_direct_demand and ROLE_GENERIC not in labels and facet_id in {
        "orders_and_backlog",
        "conversion_and_durability",
        "downstream_demand_context",
    }:
        compatibility = "compatible"
        reasons.discard("no_qualified_financial_role_detected")
    return replace(
        base,
        schema_version=EVIDENCE_ROLE_V3_SCHEMA_VERSION,
        labels=tuple(sorted(labels)),
        compatibility=compatibility,
        reason_codes=tuple(sorted(reasons)),
        decision_basis="deterministic_request_bound_financial_role_rules_v3",
    )


__all__ = [
    "EVIDENCE_ROLES_V3",
    "EVIDENCE_ROLE_V3_SCHEMA_VERSION",
    "EvidenceRoleEvaluation",
    "LEGACY_EVIDENCE_SLOT_MAP",
    "ROLE_MECHANISM_CONTEXT",
    "evaluate_evidence_role",
]
