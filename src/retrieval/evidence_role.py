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
            r"accounted for|driven by|resulted in|recognized|versus)\b|"
            r"\b(up|down)\s+\d+(?:\.\d+)?%|"
            r"\byear over year\b|\brecord\s+(?:quarterly\s+)?(?:revenue|sales|income|cash flow)\b",
            text,
        )
    )


def _is_context_dependent_fragment(text: str) -> bool:
    surface = " ".join(str(text).casefold().split())
    return bool(
        re.match(
            r"^(?:[•\-]\s*)?(?:the\s+)?(?:year[- ]over[- ]year|sequential)\s+"
            r"(?:increase|decrease)\b|^(?:[•\-]\s*)?increases were as follows\b",
            surface,
        )
    )


def _is_transcript_question_without_management_answer(text: str) -> bool:
    """Reject questions and IR restatements as evidence of management facts.

    Transcript parsing can produce a claim-sized child that contains an analyst
    question or an investor-relations restatement but not the management answer.
    Topic similarity is useful for recall, yet the question itself has no fact
    authority.  Keep the test deliberately speaker based so that it generalizes
    across companies instead of memorizing a particular transcript.
    """

    surface = " ".join(str(text).casefold().split())
    management_titles = (
        "chief executive officer",
        "chief financial officer",
        "president and chief",
        "chairman and chief",
    )
    has_management_answer = _contains_any(surface, management_titles)
    analyst_question = " - analyst" in surface and (
        "?" in surface
        or _contains_any(
            surface,
            (
                "could i ask",
                "my question",
                "first question",
                "second question",
                "follow-up",
                "would like to understand",
                "are we worried",
            ),
        )
    )
    ir_restatement = (
        "director of investor relations" in surface
        and _contains_any(
            surface,
            (
                "question is",
                "question was",
                "first question is",
                "first question was",
                "wants to know",
                "is noting",
                "question's is",
            ),
        )
    )
    question_only_transcript_fragment = (
        "earnings call transcript" in surface and "?" in surface
    )
    return not has_management_answer and (
        analyst_question or ir_restatement or question_only_transcript_fragment
    )


def _role_surface(document: Mapping[str, Any]) -> tuple[str, str, str]:
    """Return only the surface that is allowed to imply an evidence role.

    A metric-row candidate may carry issuer and table-title metadata in its
    retrieval rendering.  Those fields are useful for identity filtering but
    must not make the row look like demand, supply or relationship evidence.
    For metric rows, classify the row/header payload while the object kind
    independently establishes its financial-statement role.
    """

    section = str(document.get("section") or "").casefold()
    subsection = str(document.get("subsection") or "").casefold()
    raw_text = str(document.get("document_text") or document.get("text") or "")
    if str(document.get("object_kind") or "") != "metric_row":
        return section, subsection, raw_text.casefold()

    projection = document.get("structured_projection") or {}
    if isinstance(projection, Mapping) and projection:
        values: list[str] = []
        for key in ("header_lines", "row_context_lines"):
            rows = projection.get(key) or []
            if isinstance(rows, list):
                values.extend(str(value) for value in rows if str(value).strip())
        for key in ("metric_row_label",):
            value = str(projection.get(key) or "").strip()
            if value:
                values.append(value)
        cells = projection.get("metric_row_cells") or []
        if isinstance(cells, list):
            values.extend(str(value) for value in cells if str(value).strip())
        if values:
            return "", "", " ".join(values).casefold()

    # Backward-compatible fallback for callers that have not yet supplied the
    # structured projection.  Exclude retrieval-only identity/source headers.
    allowed_prefixes = ("header:", "row context:", "row:")
    values = [
        line.split(":", 1)[1].strip()
        for line in raw_text.splitlines()
        if line.casefold().startswith(allowed_prefixes) and ":" in line
    ]
    return "", "", " ".join(values).casefold()


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
    section, subsection, role_surface = _role_surface(document)
    text = " ".join(
        (
            section,
            subsection,
            role_surface,
        )
    )
    owner = str(
        evidence_owner_ticker or document.get("ticker") or subject_ticker
    ).upper()
    subject = str(subject_ticker).upper()
    labels: set[str] = set()
    reasons: list[str] = []

    transcript_question_only = _is_transcript_question_without_management_answer(
        text
    )

    if _contains_any(
        text,
        (
            "table of contents",
            "forward-looking statements",
            "certain statements in this press release",
            "statements as to:",
            "investor relations contact",
            "may be downloaded",
            "conference call information",
            "these protections may be limited",
        ),
    ):
        labels.add(ROLE_GENERIC)
        reasons.append("generic_or_boilerplate_surface")
    if _is_context_dependent_fragment(role_surface):
        labels.add(ROLE_GENERIC)
        reasons.append("context_dependent_fragment_requires_parent")
    if transcript_question_only:
        labels.add(ROLE_GENERIC)
        reasons.append("transcript_question_without_management_answer")

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
    if facet_id == "working_capital_risk":
        result_terms = result_terms or _contains_any(
            text,
            (
                "working capital",
                "inventory",
                "accounts receivable",
                "accounts payable",
                "operating cash flow",
                "cash provided by operating activities",
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
            "supply and demand",
        ),
    )
    risk_demand_exposure = risk_section and _contains_any(
        text,
        (
            "customer",
            "sales",
            "growth",
            "revenue",
            "orders",
            "demand",
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
    if demand_risk or (risk_section and demand_terms) or risk_demand_exposure:
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
            "production ramp",
            "component availability",
            "supply and demand",
            "managing our supply",
            "suppliers",
            "capacity commitments",
        ),
    )
    if facet_id == "upstream_capacity_context":
        supply_terms = supply_terms or _contains_any(
            text,
            (
                "packaging capacity",
                "packaging",
                "tester",
                "shortage",
                "bottleneck",
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
            "inventory provisions",
            "capacity commitments exceed demand",
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
            "customer agreements",
            "binding commitments",
            "contract terms",
            "specific volumes",
            "cash deposits",
        ),
    )
    if relationship_terms and (
        relationship_direction not in {None, "", "subject_self_disclosure"}
        or owner != subject
        or facet_id in {"subject_relationship_disclosure", "counterparty_direct_mention"}
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
    if facet_id == "working_capital_risk":
        working_capital_anchor = _contains_any(
            text,
            (
                "working capital",
                "inventory",
                "accounts receivable",
                "accounts payable",
                "operating cash flow",
                "cash provided by operating activities",
                "customer credit",
            ),
        )
        if not working_capital_anchor:
            labels.discard(ROLE_FINANCIAL_STATEMENT)
            reasons.append("working_capital_semantic_anchor_missing")
    if ROLE_GENERIC in labels:
        compatibility = "incompatible"
        reasons.append("generic_or_context_dependent_override")
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
