from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any, Iterable, Mapping, Sequence


FINANCIAL_INTENT_ONTOLOGY_SCHEMA_VERSION = (
    "fin_ia_financial_intent_ontology_v1_0"
)
FINANCIAL_INTENT_ONTOLOGY_SUCCESSOR_SCHEMA_VERSION = (
    "fin_ia_financial_intent_ontology_v1_1"
)
FINANCIAL_INTENT_ONTOLOGY_CURRENT_SCHEMA_VERSION = (
    "fin_ia_financial_intent_ontology_v1_2"
)
FINANCIAL_INTENT_ONTOLOGY_SCHEMA_VERSIONS = frozenset(
    {
        FINANCIAL_INTENT_ONTOLOGY_SCHEMA_VERSION,
        FINANCIAL_INTENT_ONTOLOGY_SUCCESSOR_SCHEMA_VERSION,
        FINANCIAL_INTENT_ONTOLOGY_CURRENT_SCHEMA_VERSION,
    }
)
FINANCIAL_INTENT_EVALUATION_SCHEMA_VERSION = (
    "fin_ia_financial_intent_evaluation_v1_0"
)
FINANCIAL_INTENT_EVALUATION_SUCCESSOR_SCHEMA_VERSION = (
    "fin_ia_financial_intent_evaluation_v1_1"
)
FINANCIAL_INTENT_EVALUATION_CURRENT_SCHEMA_VERSION = (
    "fin_ia_financial_intent_evaluation_v1_2"
)


class FinancialIntentError(ValueError):
    """A typed financial intent or ontology entry is ambiguous."""


def combine_financial_evidence_compatibility(
    *,
    role_compatibility: str,
    intent_compatibility: str,
    has_typed_intent: bool,
) -> str:
    """Combine independent role and intent decisions without score averaging."""

    states = {"compatible", "abstain", "incompatible"}
    if role_compatibility not in states or intent_compatibility not in states:
        raise FinancialIntentError("financial_evidence_compatibility_state_invalid")
    if "incompatible" in {role_compatibility, intent_compatibility}:
        return "incompatible"
    if role_compatibility == "compatible" and (
        not has_typed_intent or intent_compatibility == "compatible"
    ):
        return "compatible"
    return "abstain"


@dataclass(frozen=True)
class FinancialIntentEvaluation:
    schema_version: str
    compatibility: str
    metric_compatibility: str
    product_compatibility: str
    requested_metric_concepts: tuple[str, ...]
    requested_product_concepts: tuple[str, ...]
    observed_metric_concept: str | None
    matched_metric_aliases: tuple[str, ...]
    matched_product_aliases: tuple[str, ...]
    matched_product_supporting_terms: tuple[str, ...]
    matched_product_proxy_terms: tuple[str, ...]
    matched_product_exclusion_terms: tuple[str, ...]
    reason_codes: tuple[str, ...]
    candidate_not_evidence: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_financial_intent_ontology(
    ontology: Mapping[str, Any],
) -> None:
    if ontology.get("schema_version") not in FINANCIAL_INTENT_ONTOLOGY_SCHEMA_VERSIONS:
        raise FinancialIntentError("financial_intent_ontology_schema_invalid")
    for family in ("metric_concepts", "product_concepts"):
        concepts = ontology.get(family)
        if not isinstance(concepts, Mapping) or not concepts:
            raise FinancialIntentError(
                f"financial_intent_ontology_{family}_invalid"
            )
        for concept_id, raw in concepts.items():
            if not str(concept_id).strip() or not isinstance(raw, Mapping):
                raise FinancialIntentError(
                    f"financial_intent_ontology_{family}_entry_invalid"
                )
            aliases = _strings(raw.get("aliases") or ())
            if not aliases:
                raise FinancialIntentError(
                    f"financial_intent_ontology_{family}_aliases_missing"
                )


def concept_aliases(
    intent: str,
    *,
    family: str,
    ontology: Mapping[str, Any],
) -> tuple[str, tuple[str, ...]]:
    validate_financial_intent_ontology(ontology)
    concepts = ontology.get(family)
    if not isinstance(concepts, Mapping):
        raise FinancialIntentError("financial_intent_family_invalid")
    normalized = _normalize(intent)
    matches: list[tuple[str, tuple[str, ...]]] = []
    for concept_id, raw in concepts.items():
        aliases = _strings((raw or {}).get("aliases") or ())
        if normalized in {_normalize(value) for value in aliases}:
            matches.append((str(concept_id), aliases))
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise FinancialIntentError(
            f"financial_intent_request_alias_ambiguous:{intent}"
        )
    # Unknown intents remain usable lexical surfaces. They are abstentions in
    # the evaluator, never silently coerced into a nearby known concept.
    return f"unmapped::{normalized}", (str(intent).strip(),)


def intent_alias_groups(
    *,
    metric_intents: Sequence[str],
    product_intents: Sequence[str],
    ontology: Mapping[str, Any],
) -> tuple[tuple[str, ...], ...]:
    groups: list[tuple[str, ...]] = []
    for value in metric_intents:
        _, aliases = concept_aliases(
            value, family="metric_concepts", ontology=ontology
        )
        groups.append(aliases)
    for value in product_intents:
        concept_id, aliases = concept_aliases(
            value, family="product_concepts", ontology=ontology
        )
        raw = (ontology.get("product_concepts") or {}).get(concept_id) or {}
        groups.append(_strings((*aliases, *(raw.get("supporting_terms") or ()))))
    return tuple(groups)


def evaluate_financial_intent(
    row: Mapping[str, Any],
    *,
    metric_intents: Sequence[str],
    product_intents: Sequence[str],
    acceptable_proxy: bool,
    ontology: Mapping[str, Any],
) -> FinancialIntentEvaluation:
    validate_financial_intent_ontology(ontology)
    text = _normalize(str(row.get("model_text") or ""))
    projection = row.get("structured_projection") or {}
    metric_label = _normalize(str(projection.get("metric_row_label") or ""))
    object_kind = str(row.get("object_kind") or "")

    metric_concepts = tuple(
        concept_aliases(
            value, family="metric_concepts", ontology=ontology
        )[0]
        for value in metric_intents
    )
    product_concepts = tuple(
        concept_aliases(
            value, family="product_concepts", ontology=ontology
        )[0]
        for value in product_intents
    )
    matched_metric_aliases: list[str] = []
    observed_metric = _surface_concept(
        metric_label,
        concepts=ontology["metric_concepts"],
    ) if metric_label else _claim_surface_concept(
        text,
        concepts=ontology["metric_concepts"],
    )
    for value in metric_intents:
        _, aliases = concept_aliases(
            value, family="metric_concepts", ontology=ontology
        )
        matched_metric_aliases.extend(
            alias for alias in aliases if _contains_surface(text, alias)
        )

    reasons: list[str] = []
    if not metric_intents:
        metric_state = "not_requested"
    elif observed_metric in metric_concepts:
        metric_state = "compatible"
        reasons.append("typed_metric_concept_exact")
    elif observed_metric is not None:
        metric_state = "abstain" if acceptable_proxy else "incompatible"
        reasons.append(
            "typed_metric_proxy_requires_review"
            if acceptable_proxy
            else "typed_metric_concept_mismatch_proxy_forbidden"
        )
    elif matched_metric_aliases:
        metric_state = "compatible"
        reasons.append("requested_metric_alias_in_claim")
    else:
        metric_state = "abstain"
        reasons.append("requested_metric_not_observed")

    product_aliases: list[str] = []
    supporting: list[str] = []
    proxies: list[str] = []
    exclusions: list[str] = []
    for concept_id in product_concepts:
        if concept_id.startswith("unmapped::"):
            continue
        raw = ontology["product_concepts"][concept_id]
        product_aliases.extend(
            alias
            for alias in _strings(raw.get("aliases") or ())
            if _contains_surface(text, alias)
        )
        supporting.extend(
            term
            for term in _strings(raw.get("supporting_terms") or ())
            if _contains_surface(text, term)
        )
        proxies.extend(
            term
            for term in _strings(raw.get("proxy_terms") or ())
            if _contains_surface(text, term)
        )
        exclusions.extend(
            term
            for term in _strings(raw.get("excluded_terms") or ())
            if _contains_surface(text, term)
        )
    if not product_intents:
        product_state = "not_requested"
    elif exclusions:
        product_state = "incompatible"
        reasons.append("product_domain_exclusion_matched")
    elif product_aliases:
        product_state = "compatible"
        reasons.append("product_concept_alias_matched")
    elif supporting:
        product_state = "compatible"
        reasons.append("product_concept_supporting_surface_matched")
    elif proxies:
        product_state = "abstain"
        reasons.append("product_proxy_surface_requires_review")
    else:
        product_state = "abstain"
        reasons.append("product_concept_not_observed")

    requested_states = [
        value
        for value in (metric_state, product_state)
        if value != "not_requested"
    ]
    if "incompatible" in requested_states:
        compatibility = "incompatible"
    elif requested_states and all(value == "compatible" for value in requested_states):
        compatibility = "compatible"
    else:
        compatibility = "abstain"
    return FinancialIntentEvaluation(
        schema_version={
            FINANCIAL_INTENT_ONTOLOGY_SCHEMA_VERSION:
                FINANCIAL_INTENT_EVALUATION_SCHEMA_VERSION,
            FINANCIAL_INTENT_ONTOLOGY_SUCCESSOR_SCHEMA_VERSION:
                FINANCIAL_INTENT_EVALUATION_SUCCESSOR_SCHEMA_VERSION,
            FINANCIAL_INTENT_ONTOLOGY_CURRENT_SCHEMA_VERSION:
                FINANCIAL_INTENT_EVALUATION_CURRENT_SCHEMA_VERSION,
        }[str(ontology.get("schema_version"))],
        compatibility=compatibility,
        metric_compatibility=metric_state,
        product_compatibility=product_state,
        requested_metric_concepts=metric_concepts,
        requested_product_concepts=product_concepts,
        observed_metric_concept=observed_metric,
        matched_metric_aliases=tuple(_unique(matched_metric_aliases)),
        matched_product_aliases=tuple(_unique(product_aliases)),
        matched_product_supporting_terms=tuple(_unique(supporting)),
        matched_product_proxy_terms=tuple(_unique(proxies)),
        matched_product_exclusion_terms=tuple(_unique(exclusions)),
        reason_codes=tuple(_unique(reasons)),
        candidate_not_evidence=True,
    )


def _surface_concept(
    value: str, *, concepts: Mapping[str, Any]
) -> str | None:
    normalized = _normalize(value)
    for concept_id, raw in concepts.items():
        aliases = _strings((raw or {}).get("aliases") or ())
        if normalized in {_normalize(alias) for alias in aliases}:
            return str(concept_id)
    return None


def _claim_surface_concept(
    text: str, *, concepts: Mapping[str, Any]
) -> str | None:
    """Return the earliest explicit metric surface in a narrative claim."""

    matches: list[tuple[int, int, str]] = []
    for concept_id, raw in concepts.items():
        for alias in _strings((raw or {}).get("aliases") or ()):
            needle = _normalize(alias)
            if not needle:
                continue
            match = re.search(
                rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])",
                text,
            )
            if match is not None:
                matches.append((match.start(), -len(needle), str(concept_id)))
    if not matches:
        return None
    return min(matches)[2]


def _contains_surface(text: str, phrase: str) -> bool:
    needle = _normalize(phrase)
    if not needle:
        return False
    return bool(re.search(rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])", text))


def _normalize(value: str) -> str:
    return " ".join(
        re.sub(r"[^a-z0-9]+", " ", str(value).casefold()).split()
    )


def _strings(values: Iterable[object]) -> tuple[str, ...]:
    return tuple(_unique(str(value).strip() for value in values if str(value).strip()))


def _unique(values: Iterable[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = str(value).casefold()
        if value and key not in seen:
            seen.add(key)
            output.append(value)
    return output


__all__ = [
    "FINANCIAL_INTENT_EVALUATION_CURRENT_SCHEMA_VERSION",
    "FINANCIAL_INTENT_EVALUATION_SCHEMA_VERSION",
    "FINANCIAL_INTENT_EVALUATION_SUCCESSOR_SCHEMA_VERSION",
    "FINANCIAL_INTENT_ONTOLOGY_CURRENT_SCHEMA_VERSION",
    "FINANCIAL_INTENT_ONTOLOGY_SCHEMA_VERSION",
    "FINANCIAL_INTENT_ONTOLOGY_SCHEMA_VERSIONS",
    "FINANCIAL_INTENT_ONTOLOGY_SUCCESSOR_SCHEMA_VERSION",
    "FinancialIntentError",
    "FinancialIntentEvaluation",
    "combine_financial_evidence_compatibility",
    "concept_aliases",
    "evaluate_financial_intent",
    "intent_alias_groups",
    "validate_financial_intent_ontology",
]
