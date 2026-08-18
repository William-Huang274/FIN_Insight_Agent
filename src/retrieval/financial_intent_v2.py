from __future__ import annotations

from dataclasses import replace
import re
from typing import Any, Mapping, Sequence

from .financial_intent import (
    FinancialIntentEvaluation,
    combine_financial_evidence_compatibility,
    concept_aliases,
    evaluate_financial_intent as evaluate_financial_intent_v1,
    intent_alias_groups,
)


FINANCIAL_INTENT_V2_SCHEMA_VERSION = "fin_ia_financial_intent_evaluation_v1_3"


def _normalize(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.casefold()).split())


def _contains_surface(text: str, phrase: str) -> bool:
    needle = _normalize(phrase)
    return bool(
        needle
        and re.search(
            rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])",
            text,
        )
    )


def evaluate_financial_intent(
    row: Mapping[str, Any],
    *,
    metric_intents: Sequence[str],
    product_intents: Sequence[str],
    acceptable_proxy: bool,
    ontology: Mapping[str, Any],
) -> FinancialIntentEvaluation:
    """Allow a new request term to match verbatim without granting synonyms.

    The frozen ontology remains the only expansion/proxy authority.  V2 merely
    avoids treating the ontology as a closed-world vocabulary when the exact
    product phrase requested by the caller is present in the candidate.
    """

    base = evaluate_financial_intent_v1(
        row,
        metric_intents=metric_intents,
        product_intents=product_intents,
        acceptable_proxy=acceptable_proxy,
        ontology=ontology,
    )
    text = _normalize(str(row.get("model_text") or ""))
    exact_unmapped = tuple(
        intent
        for intent, concept in zip(
            product_intents, base.requested_product_concepts
        )
        if concept.startswith("unmapped::") and _contains_surface(text, intent)
    )
    if not exact_unmapped or base.product_compatibility != "abstain":
        return base

    requested_states = tuple(
        value
        for value in (base.metric_compatibility, "compatible")
        if value != "not_requested"
    )
    if "incompatible" in requested_states:
        compatibility = "incompatible"
    elif requested_states and all(value == "compatible" for value in requested_states):
        compatibility = "compatible"
    else:
        compatibility = "abstain"
    reasons = tuple(
        sorted(
            {
                *(
                    value
                    for value in base.reason_codes
                    if value != "product_concept_not_observed"
                ),
                "product_request_exact_surface_matched",
            }
        )
    )
    aliases = tuple(dict.fromkeys((*base.matched_product_aliases, *exact_unmapped)))
    return replace(
        base,
        schema_version=FINANCIAL_INTENT_V2_SCHEMA_VERSION,
        compatibility=compatibility,
        product_compatibility="compatible",
        matched_product_aliases=aliases,
        reason_codes=reasons,
    )


__all__ = [
    "FINANCIAL_INTENT_V2_SCHEMA_VERSION",
    "FinancialIntentEvaluation",
    "combine_financial_evidence_compatibility",
    "concept_aliases",
    "evaluate_financial_intent",
    "intent_alias_groups",
]
