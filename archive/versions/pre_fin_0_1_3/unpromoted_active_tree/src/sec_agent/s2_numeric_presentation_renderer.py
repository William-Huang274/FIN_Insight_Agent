from __future__ import annotations

from decimal import Decimal, InvalidOperation
import re
from typing import Any, Mapping, Sequence

from sec_agent.canonical_runtime.models import canonical_digest


RENDERER_SCHEMA = (
    "fin_ia_0_1_3_s2_provider_neutral_numeric_presentation_renderer_v1_0"
)


class NumericPresentationRendererError(RuntimeError):
    """Typed failure from the protected numeric presentation boundary."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


_NUMBER_RE = re.compile(
    r"(?<![A-Za-z0-9_])-?\d[\d,]*(?:\.\d+)?(?![A-Za-z0-9_])"
)
_SENTENCE_RE = re.compile(
    r".+?(?:[!?。](?=\s|$)|\.(?!\d)(?=\s+[A-Z]|$)|\n|$)",
    re.MULTILINE,
)
_NEGATION_RE = re.compile(
    r"\b(?:not|never|no|cannot|can't|did\s+not|does\s+not|do\s+not|"
    r"has\s+not|have\s+not|had\s+not|without)\b|(?:未|不|没有|并未)",
    re.IGNORECASE,
)
_RELATIONS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "less_than_or_equal",
        re.compile(
            r"\b(?:at\s+most|no\s+more\s+than|not\s+above)\b|"
            r"(?:不超过|至多|最高)",
            re.I,
        ),
    ),
    (
        "less_than",
        re.compile(
            r"\b(?:less\s+than|fewer\s+than|below|under)\b|"
            r"(?:低于|少于|不足)",
            re.I,
        ),
    ),
    (
        "greater_than_or_equal",
        re.compile(
            r"\b(?:at\s+least|no\s+fewer\s+than|not\s+below)\b|"
            r"(?:不少于|至少|不低于)",
            re.I,
        ),
    ),
    (
        "greater_than",
        re.compile(
            r"\b(?:surpass(?:es|ed|ing)?|exceed(?:s|ed|ing)?|"
            r"more\s+than|over|above)\b|(?:超过|超出|高于|多于)",
            re.I,
        ),
    ),
    (
        "approximate",
        re.compile(
            r"\b(?:about|around|approximately|roughly|nearly)\b|"
            r"(?:约|大约|近|接近)",
            re.I,
        ),
    ),
    (
        "equal",
        re.compile(
            r"\b(?:exactly|equal(?:s|ed|ing)?\s+to)\b|(?:恰好|等于)",
            re.I,
        ),
    ),
)
_PERIOD_RE = (
    re.compile(r"\bQ(?P<q>[1-4])\s*FY(?P<y>20\d{2}|\d{2})\b", re.I),
    re.compile(r"\bFY(?P<y>20\d{2}|\d{2})\s*Q(?P<q>[1-4])\b", re.I),
)
_RELATION_BY_QUALIFIER = {
    "surpassed": "greater_than",
    "exceeded": "greater_than",
    "more than": "greater_than",
    "over": "greater_than",
    "at least": "greater_than_or_equal",
    "approximately": "approximate",
    "about": "approximate",
    "nearly": "approximate",
    "exact": "equal",
}


def _fail(code: str) -> None:
    raise NumericPresentationRendererError(code)


def _decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, ValueError) as exc:
        raise NumericPresentationRendererError(
            "numeric_presentation_renderer_value_invalid"
        ) from exc


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def _is_count(fact: Mapping[str, Any]) -> bool:
    value = dict(fact.get("authoritative_value") or {})
    return (
        _norm(fact.get("value_kind")) == "count_scalar"
        or _norm(fact.get("canonical_unit")) == "count"
        or bool(value.get("count_noun"))
    )


def _presentations(fact: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = fact.get("presentation_receipts") or fact.get("allowed_presentations") or ()
    return [
        dict(row)
        for row in rows
        if row.get("equivalence_relation") != "non_equivalent_conflicting_surface"
        and str(row.get("rendered") or "").strip()
    ]


def _count_aliases(fact: Mapping[str, Any]) -> tuple[str, ...]:
    value = dict(fact.get("authoritative_value") or {})
    aliases = {
        _norm(value.get("count_noun")),
        _norm(str(fact.get("semantic_metric_key") or "").replace("_", " ")),
    }
    for alias in tuple(aliases):
        if alias.endswith(" count"):
            aliases.add(alias[: -len(" count")].strip() + "s")
    return tuple(sorted((alias for alias in aliases if alias), key=len, reverse=True))


def _preferred(fact: Mapping[str, Any]) -> str:
    unit = _norm(fact.get("canonical_unit"))

    def score(row: Mapping[str, Any]) -> tuple[int, int, str]:
        text = str(row["rendered"])
        points = 0
        if _is_count(fact):
            points += 20 if any(alias in _norm(text) for alias in _count_aliases(fact)) else 0
            points += 10 if any(pattern.search(text) for _, pattern in _RELATIONS) else 0
        if unit in {"usd", "eur"}:
            points += 10 if re.search(r"(?:US\$|USD|EUR|\$|€)", text, re.I) else 0
            points += 8 if re.search(r"\b(?:billion|million|thousand|bn|mn)\b", text, re.I) else 0
        points += 2 if row.get("equivalence_relation") == "exact_equivalent" else 1
        return points, -len(text), text

    rows = _presentations(fact)
    if not rows:
        _fail("numeric_presentation_renderer_no_allowed_presentation")
    return max(rows, key=score)["rendered"]


def _exact_matches(text: str, fact: Mapping[str, Any]) -> list[tuple[int, int, str]]:
    found: dict[tuple[int, int], str] = {}
    for row in _presentations(fact):
        for match in re.finditer(re.escape(str(row["rendered"])), text, re.I):
            found[(match.start(), match.end())] = match.group(0)
    return [(start, end, found[(start, end)]) for start, end in sorted(found)]


def _entity_aliases(
    case_key: str, evidence: Sequence[Mapping[str, Any]]
) -> tuple[set[str], set[str]]:
    current = {_norm(case_key)}
    foreign: set[str] = set()
    relation_markers = {
        "competitor",
        "supplier",
        "customer",
        "counterparty",
        "ecosystem",
    }
    for row in evidence:
        parts = str(row.get("target_id") or "").split("::")
        for index, part in enumerate(parts[:-1]):
            if part.casefold() in relation_markers:
                alias = _norm(parts[index + 1])
                if alias and alias not in current:
                    foreign.add(alias)
    return current, foreign


def _has_alias(text: str, alias: str) -> bool:
    return bool(
        re.search(
            rf"(?<![A-Za-z0-9]){re.escape(alias)}(?![A-Za-z0-9])",
            text,
            re.I,
        )
    )


def _period(value: Any) -> tuple[int, int] | None:
    match = re.fullmatch(r"FY(?P<y>20\d{2})_Q(?P<q>[1-4])", str(value or ""), re.I)
    return (int(match.group("y")), int(match.group("q"))) if match else None


def _observed_periods(text: str) -> set[tuple[int, int]]:
    found: set[tuple[int, int]] = set()
    for pattern in _PERIOD_RE:
        for match in pattern.finditer(text):
            year = match.group("y")
            found.add((int(year) if len(year) == 4 else 2000 + int(year), int(match.group("q"))))
    return found


def _count_claim(
    text: str,
    fact: Mapping[str, Any],
    current_aliases: set[str],
    foreign_aliases: set[str],
) -> dict[str, Any]:
    value = dict(fact.get("authoritative_value") or {})
    expected_value = _decimal(value.get("value"))
    expected_relation = _RELATION_BY_QUALIFIER.get(_norm(value.get("qualifier") or "exact"))
    if not expected_relation:
        _fail("numeric_presentation_renderer_fact_qualifier_unsupported")
    candidates: list[dict[str, Any]] = []
    for sentence_match in _SENTENCE_RE.finditer(text):
        sentence = sentence_match.group(0)
        numbers = [m for m in _NUMBER_RE.finditer(sentence) if _decimal(m.group(0)) == expected_value]
        nouns = [
            match
            for alias in _count_aliases(fact)
            for match in re.finditer(re.escape(alias), sentence, re.I)
        ]
        relations = [
            (name, match)
            for name, pattern in _RELATIONS
            for match in pattern.finditer(sentence)
        ]
        for number in numbers:
            for noun in nouns:
                nearby = [
                    row
                    for row in relations
                    if max(number.end(), noun.end(), row[1].end())
                    - min(number.start(), noun.start(), row[1].start())
                    <= 96
                ]
                if not nearby:
                    continue
                relation, relation_match = min(
                    nearby,
                    key=lambda row: abs(row[1].start() - number.start())
                    + abs(row[1].start() - noun.start()),
                )
                if _NEGATION_RE.search(sentence[max(0, relation_match.start() - 28) : relation_match.start()]):
                    _fail("numeric_presentation_renderer_negated_relation")
                if relation != expected_relation:
                    _fail("numeric_presentation_renderer_relation_direction_mismatch")
                normalized_sentence = _norm(sentence)
                has_current = any(_has_alias(normalized_sentence, alias) for alias in current_aliases)
                has_foreign = any(_has_alias(normalized_sentence, alias) for alias in foreign_aliases)
                if has_foreign and not has_current:
                    _fail("numeric_presentation_renderer_foreign_entity_mismatch")
                if has_foreign and has_current:
                    _fail("numeric_presentation_renderer_entity_scope_ambiguous")
                expected_period = _period(fact.get("period_or_as_of"))
                periods = _observed_periods(sentence)
                if expected_period and periods and periods != {expected_period}:
                    _fail("numeric_presentation_renderer_period_mismatch")
                start = sentence_match.start() + min(noun.start(), relation_match.start(), number.start())
                end = sentence_match.start() + max(noun.end(), relation_match.end(), number.end())
                candidates.append(
                    {
                        "start": start,
                        "end": end,
                        "observed_surface": text[start:end],
                        "relation": relation,
                    }
                )
    if not candidates:
        _fail("numeric_presentation_renderer_required_count_claim_missing")
    spans = {(row["start"], row["end"]) for row in candidates}
    if len(spans) != 1:
        _fail("numeric_presentation_renderer_count_claim_ambiguous")
    return candidates[0]


def render_protected_numeric_presentations(
    *,
    atom_text: str,
    numeric_refs: Sequence[str],
    numeric_facts: Sequence[Mapping[str, Any]],
    case_key: str,
    evidence: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Render only bound numeric spans; analytical prose remains model-owned."""

    facts = {str(row.get("numeric_ref") or ""): dict(row) for row in numeric_facts}
    requested = [str(ref) for ref in numeric_refs]
    if len(requested) != len(set(requested)) or not set(requested) <= set(facts):
        _fail("numeric_presentation_renderer_unknown_or_duplicate_ref")
    current_aliases, foreign_aliases = _entity_aliases(case_key, evidence)
    replacements: list[dict[str, Any]] = []
    for numeric_ref in requested:
        fact = facts[numeric_ref]
        canonical = _preferred(fact)
        exact = _exact_matches(atom_text, fact)
        if _is_count(fact):
            match = _count_claim(atom_text, fact, current_aliases, foreign_aliases)
            exact_spans = {(start, end) for start, end, _ in exact}
            replacements.append(
                {
                    "numeric_ref": numeric_ref,
                    **match,
                    "canonical_surface": canonical,
                    "equivalence_basis": (
                        "approved_presentation_receipt"
                        if (match["start"], match["end"]) in exact_spans
                        else "bounded_relation_equivalence"
                    ),
                }
            )
        elif exact:
            start, end, observed = exact[0]
            replacements.append(
                {
                    "numeric_ref": numeric_ref,
                    "start": start,
                    "end": end,
                    "observed_surface": observed,
                    "canonical_surface": canonical,
                    "equivalence_basis": "approved_presentation_receipt",
                    "relation": "source_numeric_equivalence",
                }
            )
        else:
            _fail("numeric_presentation_renderer_required_numeric_surface_missing")
    occupied: list[tuple[int, int]] = []
    for row in sorted(replacements, key=lambda item: (item["start"], item["end"])):
        span = int(row["start"]), int(row["end"])
        if any(span[0] < other[1] and other[0] < span[1] for other in occupied):
            _fail("numeric_presentation_renderer_overlapping_claims")
        occupied.append(span)
    rendered = atom_text
    for row in sorted(replacements, key=lambda item: int(item["start"]), reverse=True):
        rendered = rendered[: int(row["start"])] + str(row["canonical_surface"]) + rendered[int(row["end"]) :]
    receipts = [
        {
            key: row[key]
            for key in (
                "numeric_ref",
                "observed_surface",
                "canonical_surface",
                "equivalence_basis",
                "relation",
            )
        }
        for row in sorted(replacements, key=lambda item: str(item["numeric_ref"]))
    ]
    body = {
        "schema_version": RENDERER_SCHEMA,
        "case_key": str(case_key),
        "input_text_digest": canonical_digest({"text": atom_text}),
        "rendered_text_digest": canonical_digest({"text": rendered}),
        "used_numeric_refs": sorted(requested),
        "protected_span_count": len(receipts),
        "receipts": receipts,
        "free_prose_changed": False,
        "non_protected_prose_changed": False,
        "provider_specific_rule_used": False,
    }
    return {**body, "rendered_text": rendered, "renderer_receipt_digest": canonical_digest(body)}


__all__ = [
    "NumericPresentationRendererError",
    "RENDERER_SCHEMA",
    "render_protected_numeric_presentations",
]
