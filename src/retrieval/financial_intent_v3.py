from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import re
from typing import Any, Iterable, Mapping, Sequence

from .financial_intent import (
    FINANCIAL_INTENT_ONTOLOGY_CURRENT_SCHEMA_VERSION,
    FinancialIntentError,
    FinancialIntentEvaluation,
    combine_financial_evidence_compatibility,
    concept_aliases as concept_aliases_v1,
    intent_alias_groups as intent_alias_groups_v1,
    validate_financial_intent_ontology as validate_financial_intent_ontology_v1,
)
from .financial_intent_v2 import (
    evaluate_financial_intent as evaluate_financial_intent_v2,
)


FINANCIAL_INTENT_ONTOLOGY_GROUPED_RECALL_SCHEMA_VERSION = (
    "fin_ia_financial_intent_ontology_v1_3"
)
FINANCIAL_INTENT_EVALUATION_GROUPED_RECALL_SCHEMA_VERSION = (
    "fin_ia_financial_intent_evaluation_v1_4"
)


def _unique(values: Iterable[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = str(raw).strip()
        key = value.casefold()
        if value and key not in seen:
            seen.add(key)
            output.append(value)
    return output


def _normalize(value: str) -> str:
    return " ".join(
        re.sub(r"[^a-z0-9]+", " ", str(value).casefold()).split()
    )


def _contains_surface(text: str, phrase: str) -> bool:
    needle = _normalize(phrase)
    return bool(
        needle
        and re.search(
            rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])",
            text,
        )
    )


def validate_financial_intent_ontology(
    ontology: Mapping[str, Any],
) -> None:
    if (
        ontology.get("schema_version")
        != FINANCIAL_INTENT_ONTOLOGY_GROUPED_RECALL_SCHEMA_VERSION
    ):
        validate_financial_intent_ontology_v1(ontology)
        return
    products = ontology.get("product_concepts")
    if not isinstance(products, Mapping):
        raise FinancialIntentError(
            "financial_intent_ontology_product_concepts_invalid"
        )
    for raw in products.values():
        groups = (raw or {}).get("recall_surface_groups")
        if groups is None:
            continue
        if not isinstance(groups, Mapping) or not groups:
            raise FinancialIntentError(
                "financial_intent_recall_surface_groups_invalid"
            )
        for group_id, terms in groups.items():
            if (
                not str(group_id).strip()
                or not isinstance(terms, Sequence)
                or isinstance(terms, (str, bytes))
                or not _unique(str(value) for value in terms)
            ):
                raise FinancialIntentError(
                    "financial_intent_recall_surface_group_invalid"
                )
    projected = project_grouped_recall_ontology_to_current(
        ontology,
        validate=False,
    )
    validate_financial_intent_ontology_v1(projected)


def project_grouped_recall_ontology_to_current(
    ontology: Mapping[str, Any],
    *,
    validate: bool = True,
) -> dict[str, Any]:
    """Project grouped recall terms onto the frozen v1.2 evaluation contract.

    The projection lets immutable v1/v2 consumers score a candidate selected
    by the successor query planner.  It merges candidate-only grouped surfaces
    into ``supporting_terms`` and never changes aliases, proxy terms or
    Evidence authority.
    """

    if (
        ontology.get("schema_version")
        != FINANCIAL_INTENT_ONTOLOGY_GROUPED_RECALL_SCHEMA_VERSION
    ):
        if validate:
            validate_financial_intent_ontology_v1(ontology)
        return deepcopy(dict(ontology))
    if validate:
        validate_financial_intent_ontology(ontology)
    projected = deepcopy(dict(ontology))
    projected["schema_version"] = FINANCIAL_INTENT_ONTOLOGY_CURRENT_SCHEMA_VERSION
    products = projected.get("product_concepts")
    if not isinstance(products, Mapping):
        raise FinancialIntentError(
            "financial_intent_ontology_product_concepts_invalid"
        )
    for raw in products.values():
        if not isinstance(raw, dict):
            raise FinancialIntentError(
                "financial_intent_ontology_product_concepts_entry_invalid"
            )
        groups = raw.pop("recall_surface_groups", None)
        grouped_terms = (
            (
                str(term)
                for terms in groups.values()
                for term in terms
            )
            if isinstance(groups, Mapping)
            else ()
        )
        raw["supporting_terms"] = _unique(
            (
                *(str(value) for value in raw.get("supporting_terms") or ()),
                *grouped_terms,
            )
        )
    if validate:
        validate_financial_intent_ontology_v1(projected)
    return projected


def concept_aliases(
    intent: str,
    *,
    family: str,
    ontology: Mapping[str, Any],
) -> tuple[str, tuple[str, ...]]:
    validate_financial_intent_ontology(ontology)
    return concept_aliases_v1(
        intent,
        family=family,
        ontology=project_grouped_recall_ontology_to_current(
            ontology,
            validate=False,
        ),
    )


def intent_alias_groups(
    *,
    metric_intents: Sequence[str],
    product_intents: Sequence[str],
    ontology: Mapping[str, Any],
) -> tuple[tuple[str, ...], ...]:
    validate_financial_intent_ontology(ontology)
    return intent_alias_groups_v1(
        metric_intents=metric_intents,
        product_intents=product_intents,
        ontology=project_grouped_recall_ontology_to_current(
            ontology,
            validate=False,
        ),
    )


def evaluate_financial_intent(
    row: Mapping[str, Any],
    *,
    metric_intents: Sequence[str],
    product_intents: Sequence[str],
    acceptable_proxy: bool,
    ontology: Mapping[str, Any],
) -> FinancialIntentEvaluation:
    if (
        ontology.get("schema_version")
        != FINANCIAL_INTENT_ONTOLOGY_GROUPED_RECALL_SCHEMA_VERSION
    ):
        return evaluate_financial_intent_v2(
            row,
            metric_intents=metric_intents,
            product_intents=product_intents,
            acceptable_proxy=acceptable_proxy,
            ontology=ontology,
        )
    validate_financial_intent_ontology(ontology)
    projected = project_grouped_recall_ontology_to_current(
        ontology,
        validate=False,
    )
    base = evaluate_financial_intent_v2(
        row,
        metric_intents=metric_intents,
        product_intents=product_intents,
        acceptable_proxy=acceptable_proxy,
        ontology=projected,
    )
    text = _normalize(str(row.get("model_text") or ""))
    grouped_matches: list[str] = []
    for intent in product_intents:
        concept_id, _ = concept_aliases(
            intent,
            family="product_concepts",
            ontology=ontology,
        )
        raw = (ontology.get("product_concepts") or {}).get(concept_id) or {}
        for terms in (raw.get("recall_surface_groups") or {}).values():
            grouped_matches.extend(
                str(term)
                for term in terms
                if _contains_surface(text, str(term))
            )
    reasons = list(base.reason_codes)
    if grouped_matches:
        reasons = [
            value
            for value in reasons
            if value != "product_concept_supporting_surface_matched"
        ]
        reasons.append("product_grouped_recall_surface_matched_candidate_only")
    return replace(
        base,
        schema_version=FINANCIAL_INTENT_EVALUATION_GROUPED_RECALL_SCHEMA_VERSION,
        reason_codes=tuple(_unique(reasons)),
    )


__all__ = [
    "FINANCIAL_INTENT_EVALUATION_GROUPED_RECALL_SCHEMA_VERSION",
    "FINANCIAL_INTENT_ONTOLOGY_GROUPED_RECALL_SCHEMA_VERSION",
    "FinancialIntentError",
    "FinancialIntentEvaluation",
    "combine_financial_evidence_compatibility",
    "concept_aliases",
    "evaluate_financial_intent",
    "intent_alias_groups",
    "project_grouped_recall_ontology_to_current",
    "validate_financial_intent_ontology",
]
