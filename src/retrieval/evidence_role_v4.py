from __future__ import annotations

from dataclasses import replace
import re
from typing import Any, Mapping, Sequence

from .evidence_role import (
    ROLE_DEMAND_RISK,
    ROLE_DIRECT_DEMAND,
    ROLE_DIRECT_SUPPLY,
    ROLE_GENERIC,
    ROLE_GUIDANCE,
    ROLE_OBSERVED_RESULT,
    ROLE_REGULATORY,
    ROLE_RELATIONSHIP,
    ROLE_SUPPLY_RISK,
    EvidenceRoleEvaluation,
)
from .evidence_role_v3 import (
    EVIDENCE_ROLES_V3,
    LEGACY_EVIDENCE_SLOT_MAP,
    ROLE_MECHANISM_CONTEXT,
    evaluate_evidence_role as evaluate_evidence_role_v3,
)


EVIDENCE_ROLE_V4_SCHEMA_VERSION = "fin_ia_evidence_role_evaluation_v1_3"
EVIDENCE_ROLES_V4 = EVIDENCE_ROLES_V3

# The frozen v1-v3 files are qualification-bound assets. Public-context
# successor facets therefore live here instead of mutating their historical
# semantics. Each successor facet is first classified through the closest
# provider-neutral v3 surface, then checked against its own explicit role set.
_PUBLIC_FACET_ALIASES = {
    "industry_demand_context": "downstream_demand_context",
    "industry_pricing_mix_context": "pricing_and_mix",
    "channel_configuration_context": "counterparty_direct_mention",
    "trusted_value_pool_context": "upstream_or_demand_counterevidence",
    "industry_supply_context": "upstream_capacity_context",
    "industry_relationship_context": "counterparty_direct_mention",
    "trusted_or_industry_counterevidence": (
        "upstream_or_demand_counterevidence"
    ),
}

_PUBLIC_COMPATIBLE_ROLES = {
    "industry_demand_context": frozenset(
        {
            ROLE_DIRECT_DEMAND,
            ROLE_DEMAND_RISK,
            ROLE_OBSERVED_RESULT,
            ROLE_GUIDANCE,
            ROLE_RELATIONSHIP,
        }
    ),
    "industry_pricing_mix_context": frozenset(
        {
            ROLE_OBSERVED_RESULT,
            ROLE_GUIDANCE,
            ROLE_DIRECT_DEMAND,
            ROLE_DEMAND_RISK,
            ROLE_RELATIONSHIP,
        }
    ),
    "channel_configuration_context": frozenset(
        {ROLE_OBSERVED_RESULT, ROLE_RELATIONSHIP}
    ),
    "trusted_value_pool_context": frozenset(
        {
            ROLE_OBSERVED_RESULT,
            ROLE_GUIDANCE,
            ROLE_DEMAND_RISK,
            ROLE_SUPPLY_RISK,
            ROLE_RELATIONSHIP,
        }
    ),
    "industry_supply_context": frozenset(
        {
            ROLE_DIRECT_SUPPLY,
            ROLE_SUPPLY_RISK,
            ROLE_OBSERVED_RESULT,
            ROLE_GUIDANCE,
            ROLE_RELATIONSHIP,
        }
    ),
    "industry_relationship_context": frozenset(
        {ROLE_RELATIONSHIP, ROLE_DIRECT_SUPPLY, ROLE_DIRECT_DEMAND}
    ),
    "trusted_or_industry_counterevidence": frozenset(
        {
            ROLE_DEMAND_RISK,
            ROLE_SUPPLY_RISK,
            ROLE_REGULATORY,
            ROLE_OBSERVED_RESULT,
            ROLE_RELATIONSHIP,
        }
    ),
}


def _observed_supply_state(text: str) -> tuple[bool, bool]:
    """Recognize an observed capacity state without granting Evidence status."""

    surface = " ".join(str(text).casefold().split())
    observed = bool(
        re.search(
            r"\b(?:production(?:\s+of\s+[a-z0-9-]+)?\s+is\s+)?ramping\s+at\s+full\s+speed\b|"
            r"\bproduction\s+(?:is\s+)?ramping\b|"
            r"\b(?:gpu|gpus|accelerator|accelerators|capacity|supply)\s+(?:is|are|remains?)\s+sold\s+out\b|"
            r"\bsold\s+out\b|"
            r"\b(?:supply|capacity)\s+(?:is|remains?)\s+(?:tight|constrained)\b|"
            r"\bshort\s+supply\b",
            surface,
        )
    )
    constrained = bool(
        re.search(
            r"\bsold\s+out\b|\bshort\s+supply\b|"
            r"\b(?:supply|capacity)\s+(?:is|remains?)\s+(?:tight|constrained)\b",
            surface,
        )
    )
    return observed, constrained


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
    alias = _PUBLIC_FACET_ALIASES.get(str(facet_id or ""))
    base = evaluate_evidence_role_v3(
        row,
        slot_id=slot_id,
        subject_ticker=subject_ticker,
        facet_id=(alias if alias is not None else facet_id),
        evidence_owner_ticker=evidence_owner_ticker,
        relationship_direction=relationship_direction,
        request_intent_terms=request_intent_terms,
    )
    observed_supply, constrained_supply = _observed_supply_state(
        str(row.get("document_text") or row.get("model_text") or "")
    )
    supply_state_facets = {
        "upstream_capacity_context",
        "upstream_or_demand_counterevidence",
        "industry_supply_context",
        "trusted_or_industry_counterevidence",
    }
    if observed_supply and str(facet_id or "") in supply_state_facets:
        labels = set(base.labels)
        reasons = set(base.reason_codes)
        labels.add(ROLE_DIRECT_SUPPLY)
        reasons.add("observed_supply_state_surface_candidate_only")
        if constrained_supply:
            labels.add(ROLE_SUPPLY_RISK)
            reasons.add("observed_supply_constraint_surface_candidate_only")
        reasons.discard("no_qualified_financial_role_detected")
        return replace(
            base,
            schema_version=EVIDENCE_ROLE_V4_SCHEMA_VERSION,
            labels=tuple(sorted(labels)),
            compatibility="compatible",
            reason_codes=tuple(sorted(reasons)),
            decision_basis=(
                "deterministic_public_supply_state_successor_role_rules_v4"
            ),
        )
    if alias is None:
        return base

    # Public-context facets retain their explicit compatible-role projection.
    labels = set(base.labels)
    reasons = set(base.reason_codes)
    compatible_roles = _PUBLIC_COMPATIBLE_ROLES[str(facet_id)]
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
    reasons.add("public_context_successor_facet_mapped_to_frozen_v3_classifier")
    return replace(
        base,
        schema_version=EVIDENCE_ROLE_V4_SCHEMA_VERSION,
        compatibility=compatibility,
        reason_codes=tuple(sorted(reasons)),
        decision_basis="deterministic_public_context_successor_role_rules_v4",
    )


__all__ = [
    "EVIDENCE_ROLES_V4",
    "EVIDENCE_ROLE_V4_SCHEMA_VERSION",
    "EvidenceRoleEvaluation",
    "LEGACY_EVIDENCE_SLOT_MAP",
    "ROLE_MECHANISM_CONTEXT",
    "evaluate_evidence_role",
]
