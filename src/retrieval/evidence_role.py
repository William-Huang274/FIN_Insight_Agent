from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any, Mapping


EVIDENCE_ROLE_SCHEMA_VERSION = "fin_ia_evidence_role_evaluation_v1_0"

ROLE_OBSERVED_RESULT = "observed_operating_result"
ROLE_GUIDANCE = "management_guidance"
ROLE_DIRECT_DEMAND = "direct_demand_signal"
ROLE_DEMAND_RISK = "demand_risk_or_counterevidence"
ROLE_DIRECT_SUPPLY = "direct_supply_capacity_signal"
ROLE_SUPPLY_RISK = "supply_risk_or_counterevidence"
ROLE_FINANCIAL_STATEMENT = "financial_statement_or_reconciliation"
ROLE_REGULATORY = "regulatory_or_policy_exposure"
ROLE_RELATIONSHIP = "relationship_context"
ROLE_CAPITAL_VALUATION = "capital_allocation_or_valuation"
ROLE_GENERIC = "generic_or_boilerplate"

EVIDENCE_ROLES = frozenset(
    {
        ROLE_OBSERVED_RESULT,
        ROLE_GUIDANCE,
        ROLE_DIRECT_DEMAND,
        ROLE_DEMAND_RISK,
        ROLE_DIRECT_SUPPLY,
        ROLE_SUPPLY_RISK,
        ROLE_FINANCIAL_STATEMENT,
        ROLE_REGULATORY,
        ROLE_RELATIONSHIP,
        ROLE_CAPITAL_VALUATION,
        ROLE_GENERIC,
    }
)

SLOT_COMPATIBLE_ROLES: Mapping[str, frozenset[str]] = {
    "demand_volume_quality": frozenset({ROLE_DIRECT_DEMAND, ROLE_DEMAND_RISK}),
    "operating_performance": frozenset(
        {ROLE_OBSERVED_RESULT, ROLE_GUIDANCE, ROLE_FINANCIAL_STATEMENT}
    ),
    "pricing_mix_value_capture": frozenset(
        {ROLE_OBSERVED_RESULT, ROLE_FINANCIAL_STATEMENT}
    ),
    "cash_conversion_balance_sheet": frozenset({ROLE_FINANCIAL_STATEMENT}),
    "capacity_inputs_execution": frozenset(
        {ROLE_DIRECT_SUPPLY, ROLE_SUPPLY_RISK}
    ),
    "relationship_attribution": frozenset({ROLE_RELATIONSHIP}),
    "counterevidence_and_what_would_change": frozenset(
        {ROLE_DEMAND_RISK, ROLE_SUPPLY_RISK, ROLE_REGULATORY}
    ),
    "regulatory_policy_exposure": frozenset({ROLE_REGULATORY}),
    "capital_allocation_and_valuation": frozenset(
        {ROLE_CAPITAL_VALUATION, ROLE_FINANCIAL_STATEMENT}
    ),
    # Frozen S1-C qrels pre-date the decomposed kernel and retain this broad
    # legacy slot. Use the honest role union in shadow evaluation. Mapping each
    # labelled row to its target role would leak qrel answers into the gate;
    # mapping the whole slot to cash conversion would reject valid risk text.
    "regulatory_risk_and_financial_reconciliation": frozenset(
        {
            ROLE_DEMAND_RISK,
            ROLE_SUPPLY_RISK,
            ROLE_FINANCIAL_STATEMENT,
            ROLE_REGULATORY,
        }
    ),
}

# Product requests are facet-specific even when several facets share one broad
# Evidence Slot. Use the slot map for legacy qrels, but prefer this map for the
# current Runtime so that, for example, a working-capital risk claim is not
# rejected merely because cash statements share its parent slot.
FACET_COMPATIBLE_ROLES: Mapping[str, frozenset[str]] = {
    "orders_and_backlog": frozenset({ROLE_DIRECT_DEMAND, ROLE_DEMAND_RISK}),
    "conversion_and_durability": frozenset(
        {ROLE_DIRECT_DEMAND, ROLE_DEMAND_RISK}
    ),
    "downstream_demand_context": frozenset(
        {ROLE_DIRECT_DEMAND, ROLE_DEMAND_RISK, ROLE_OBSERVED_RESULT, ROLE_RELATIONSHIP}
    ),
    "reported_results": frozenset(
        {ROLE_OBSERVED_RESULT, ROLE_FINANCIAL_STATEMENT}
    ),
    "guidance_and_outlook": frozenset({ROLE_GUIDANCE}),
    "pricing_and_mix": frozenset(
        {ROLE_OBSERVED_RESULT, ROLE_GUIDANCE, ROLE_FINANCIAL_STATEMENT}
    ),
    "margin_and_incremental_profit": frozenset(
        {ROLE_OBSERVED_RESULT, ROLE_FINANCIAL_STATEMENT}
    ),
    "cash_generation": frozenset(
        {ROLE_FINANCIAL_STATEMENT, ROLE_OBSERVED_RESULT}
    ),
    "working_capital_risk": frozenset(
        {
            ROLE_FINANCIAL_STATEMENT,
            ROLE_OBSERVED_RESULT,
            ROLE_DEMAND_RISK,
            ROLE_SUPPLY_RISK,
        }
    ),
    "subject_execution": frozenset(
        {ROLE_DIRECT_SUPPLY, ROLE_SUPPLY_RISK, ROLE_OBSERVED_RESULT}
    ),
    "upstream_capacity_context": frozenset(
        {ROLE_DIRECT_SUPPLY, ROLE_SUPPLY_RISK, ROLE_RELATIONSHIP}
    ),
    "subject_relationship_disclosure": frozenset({ROLE_RELATIONSHIP}),
    "counterparty_direct_mention": frozenset({ROLE_RELATIONSHIP}),
    "issuer_counterevidence": frozenset(
        {ROLE_DEMAND_RISK, ROLE_SUPPLY_RISK, ROLE_REGULATORY}
    ),
    "upstream_or_demand_counterevidence": frozenset(
        {
            ROLE_DIRECT_DEMAND,
            ROLE_DEMAND_RISK,
            ROLE_DIRECT_SUPPLY,
            ROLE_SUPPLY_RISK,
            ROLE_REGULATORY,
            ROLE_RELATIONSHIP,
        }
    ),
    "issuer_policy_exposure": frozenset({ROLE_REGULATORY}),
    "capital_allocation": frozenset(
        {ROLE_CAPITAL_VALUATION, ROLE_FINANCIAL_STATEMENT}
    ),
    "point_in_time_valuation": frozenset(
        {ROLE_CAPITAL_VALUATION, ROLE_FINANCIAL_STATEMENT}
    ),
}

LEGACY_EVIDENCE_SLOT_MAP: Mapping[str, str] = {
    "customer_demand_and_deployment_validation": "demand_volume_quality",
    "issuer_results_and_management_commentary": "operating_performance",
    "regulatory_risk_and_financial_reconciliation": (
        "regulatory_risk_and_financial_reconciliation"
    ),
    "supply_chain_capacity_and_counterevidence": "capacity_inputs_execution",
}


@dataclass(frozen=True)
class EvidenceRoleEvaluation:
    schema_version: str
    slot_id: str
    labels: tuple[str, ...]
    compatibility: str
    reason_codes: tuple[str, ...]
    decision_basis: str
    evidence_promoted: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _contains_any(text: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in text for phrase in phrases)


def _has_observed_change(text: str) -> bool:
    return bool(
        re.search(
            r"\b(was|were|grew|increased|decreased|rose|declined|generated|reported|"
            r"accounted for|driven by|resulted in|recognized)\b",
            text,
        )
    )


def evaluate_evidence_role(
    document: Mapping[str, Any],
    *,
    slot_id: str,
    subject_ticker: str,
    facet_id: str | None = None,
    evidence_owner_ticker: str | None = None,
    relationship_direction: str | None = None,
) -> EvidenceRoleEvaluation:
    """Classify what a candidate can prove; abstain when rules are insufficient."""

    if slot_id not in SLOT_COMPATIBLE_ROLES:
        raise ValueError(f"evidence_role_slot_unknown:{slot_id}")
    if facet_id is not None and facet_id not in FACET_COMPATIBLE_ROLES:
        raise ValueError(f"evidence_role_facet_unknown:{facet_id}")
    section = str(document.get("section") or "").casefold()
    subsection = str(document.get("subsection") or "").casefold()
    text = " ".join(
        (
            section,
            subsection,
            str(document.get("document_text") or document.get("text") or "").casefold(),
        )
    )
    owner = str(
        evidence_owner_ticker or document.get("ticker") or subject_ticker
    ).upper()
    subject = str(subject_ticker).upper()
    labels: set[str] = set()
    reasons: list[str] = []

    if _contains_any(
        text,
        (
            "table of contents",
            "forward-looking statements",
            "investor relations contact",
            "may be downloaded",
            "conference call information",
            "these protections may be limited",
        ),
    ):
        labels.add(ROLE_GENERIC)
        reasons.append("generic_or_boilerplate_surface")

    risk_section = "risk factor" in section or "risk factor" in subsection
    financial_statement = (
        "financial statement" in section
        or "statements of cash flows" in text
        or "cash flows from operating activities" in text
        or "net cash provided by operating activities" in text
        or "reconciliation" in text
        or "balance sheets" in text
        or "structured_metric" in str(document.get("source_type") or "")
        or str(document.get("object_kind") or "") == "metric_row"
    )
    if financial_statement:
        labels.add(ROLE_FINANCIAL_STATEMENT)
        reasons.append("financial_statement_or_reconciliation_surface")

    if _contains_any(
        text,
        ("guidance", "outlook", "expected revenue", "we expect", "we anticipate"),
    ):
        labels.add(ROLE_GUIDANCE)
        reasons.append("forward_management_guidance_surface")

    result_terms = _contains_any(
        text,
        (
            "revenue",
            "operating income",
            "gross margin",
            "net income",
            "segment results",
            "system shipments",
        ),
    )
    if result_terms and _has_observed_change(text) and not risk_section:
        labels.add(ROLE_OBSERVED_RESULT)
        reasons.append("observed_period_result_surface")

    demand_terms = _contains_any(
        text,
        (
            "orders",
            "backlog",
            "bookings",
            "customer readiness",
            "customer demand",
            "deployments",
            "adoption",
        ),
    )
    demand_risk = _contains_any(
        text,
        (
            "cancel or defer orders",
            "cancellations",
            "overestimate demand",
            "pull-forward",
            "digestion",
            "demand variability",
            "demand could",
        ),
    )
    if demand_terms and not risk_section:
        labels.add(ROLE_DIRECT_DEMAND)
        reasons.append("direct_demand_activity_surface")
    if demand_risk or (risk_section and demand_terms):
        labels.add(ROLE_DEMAND_RISK)
        reasons.append("demand_risk_or_counterevidence_surface")

    supply_terms = _contains_any(
        text,
        (
            "capacity",
            "supply chain",
            "industry supply",
            "supply is",
            "supply growth",
            "supply constraints",
            "advanced packaging",
            "cowos",
            "hbm",
            "yield",
            "lead time",
            "manufacturing",
            "production ramp",
            "component availability",
        ),
    )
    supply_risk = _contains_any(
        text,
        (
            "supply demand mismatch",
            "quality issues",
            "production delays",
            "capacity agreement",
            "purchase commitments",
            "non-cancellable",
            "inventory write-down",
        ),
    )
    if supply_terms and not risk_section:
        labels.add(ROLE_DIRECT_SUPPLY)
        reasons.append("direct_supply_or_capacity_surface")
    if supply_risk or (risk_section and supply_terms):
        labels.add(ROLE_SUPPLY_RISK)
        reasons.append("supply_risk_or_counterevidence_surface")

    if _contains_any(
        text,
        (
            "export controls",
            "license requirements",
            "government restrictions",
            "regulation",
            "regulatory",
            "tariffs",
        ),
    ):
        labels.add(ROLE_REGULATORY)
        reasons.append("regulatory_or_policy_surface")

    if _contains_any(
        text,
        (
            "share repurchases",
            "dividends",
            "capital return",
            "market price",
            "valuation",
            "shares outstanding",
            "net debt",
        ),
    ):
        labels.add(ROLE_CAPITAL_VALUATION)
        reasons.append("capital_allocation_or_valuation_surface")

    relationship_terms = _contains_any(
        text,
        (
            "customer",
            "supplier",
            "partnership",
            "purchase commitments",
            "concentration",
        ),
    )
    if relationship_terms and (
        relationship_direction not in {None, "", "subject_self_disclosure"}
        or owner != subject
    ):
        labels.add(ROLE_RELATIONSHIP)
        reasons.append("related_entity_relationship_context_surface")

    if (
        not labels
        and "item 1. business" in section
        and _contains_any(text, ("we provide", "we offer", "portfolio", "solutions"))
    ):
        labels.add(ROLE_GENERIC)
        reasons.append("generic_company_description_surface")

    compatible_roles = (
        FACET_COMPATIBLE_ROLES[facet_id]
        if facet_id is not None
        else SLOT_COMPATIBLE_ROLES[slot_id]
    )
    if ROLE_GENERIC in labels and not (labels - {ROLE_GENERIC}):
        compatibility = "incompatible"
    elif labels.intersection(compatible_roles):
        compatibility = "compatible"
    elif labels:
        compatibility = "incompatible"
    else:
        compatibility = "abstain"
        reasons.append("no_qualified_financial_role_detected")
    return EvidenceRoleEvaluation(
        schema_version=EVIDENCE_ROLE_SCHEMA_VERSION,
        slot_id=slot_id,
        labels=tuple(sorted(labels)),
        compatibility=compatibility,
        reason_codes=tuple(sorted(set(reasons))),
        decision_basis=(
            "deterministic_facet_aware_metadata_and_phrase_rules_v1"
            if facet_id is not None
            else "deterministic_metadata_and_phrase_rules_v1"
        ),
        evidence_promoted=False,
    )


__all__ = [
    "EVIDENCE_ROLES",
    "FACET_COMPATIBLE_ROLES",
    "EVIDENCE_ROLE_SCHEMA_VERSION",
    "EvidenceRoleEvaluation",
    "LEGACY_EVIDENCE_SLOT_MAP",
    "SLOT_COMPATIBLE_ROLES",
    "evaluate_evidence_role",
]
