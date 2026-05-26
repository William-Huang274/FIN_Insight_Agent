from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any, Iterable, Literal

from evidence.structured_text import structured_object_preview, structured_object_search_text


VerificationLabel = Literal["direct", "partial", "false"]


STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "based",
    "be",
    "by",
    "do",
    "does",
    "for",
    "from",
    "have",
    "in",
    "into",
    "is",
    "it",
    "of",
    "on",
    "or",
    "our",
    "over",
    "per",
    "the",
    "their",
    "to",
    "was",
    "were",
    "what",
    "with",
}


def load_structured_object_map(
    structured_dir: str | Path,
    prefix: str = "sec_tech_10k",
) -> dict[str, dict[str, Any]]:
    root = Path(structured_dir)
    objects: dict[str, dict[str, Any]] = {}
    for suffix in ("tables", "metrics", "claims"):
        path = root / f"{prefix}_{suffix}.jsonl"
        for row in read_jsonl(path):
            objects[str(row["object_id"])] = row
    return objects


def verify_object_against_need(
    obj: dict[str, Any],
    need: dict[str, Any],
) -> dict[str, Any]:
    must_find = [str(item) for item in need.get("must_find", []) if str(item).strip()]
    if not must_find and need.get("facet"):
        must_find = [str(need["facet"])]

    text = structured_object_search_text(obj)
    norm_text = normalize_text(text)
    object_tokens = set(tokens(norm_text))
    phrase_results = [
        _score_phrase(phrase, norm_text, object_tokens, obj)
        for phrase in must_find
    ]

    direct_phrases = [
        item["phrase"]
        for item in phrase_results
        if item["match_level"] == "direct"
    ]
    partial_phrases = [
        item["phrase"]
        for item in phrase_results
        if item["match_level"] == "partial"
    ]
    missing_phrases = [
        item["phrase"]
        for item in phrase_results
        if item["match_level"] == "missing"
    ]
    matched_numbers = list(
        dict.fromkeys(
            number
            for item in phrase_results
            for number in item.get("matched_numbers", [])
        )
    )
    score = round(sum(item["score"] for item in phrase_results), 4)
    matched_phrase_count = len(direct_phrases) + len(partial_phrases)
    has_numeric_direct = any(
        item["match_level"] == "direct" and item.get("numbers")
        for item in phrase_results
    )

    if direct_phrases and (len(must_find) == 1 or matched_phrase_count >= 2 or has_numeric_direct):
        label: VerificationLabel = "direct"
    elif direct_phrases or partial_phrases:
        label = "partial"
    else:
        label = "false"

    all_important = [
        term
        for item in phrase_results
        for term in item.get("important_terms", [])
    ]
    matched_important = {
        term
        for item in phrase_results
        for term in item.get("matched_terms", [])
    }
    important_coverage = (
        round(len(matched_important) / len(set(all_important)), 4)
        if all_important
        else 0.0
    )

    confidence = _confidence(label, score, len(must_find), matched_phrase_count)
    return {
        "object_id": obj.get("object_id"),
        "object_type": obj.get("object_type"),
        "source_evidence_id": obj.get("source_evidence_id"),
        "label": label,
        "confidence": confidence,
        "score": score,
        "matched_must_find": direct_phrases,
        "partial_must_find": partial_phrases,
        "missing_must_find": missing_phrases,
        "matched_numbers": matched_numbers,
        "important_token_coverage": important_coverage,
        "phrase_results": phrase_results,
        "preview": structured_object_preview(obj),
    }


def normalize_text(value: str) -> str:
    cleaned = (
        value.lower()
        .replace(",", "")
        .replace("’", "'")
        .replace("“", '"')
        .replace("”", '"')
    )
    cleaned = _expand_verifier_aliases(cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _expand_verifier_aliases(value: str) -> str:
    additions = []
    alias_groups = {
        "operating income": ("income from operations", "total income from operations", "operating profit"),
        "cost of revenue": ("cost of revenues", "cost of sales"),
        "headcount": ("employees", "employee headcount", "number of employees"),
        "capital expenditures": ("capex", "purchases of property and equipment"),
        "operating cash flow": ("net cash provided by operating activities", "cash provided by operating activities"),
        "advertising revenues": ("advertising revenue", "google advertising", "family of apps advertising"),
    }
    for canonical, aliases in alias_groups.items():
        if canonical in value or any(alias in value for alias in aliases):
            additions.append(canonical)
            additions.extend(aliases)
    if additions:
        value = f"{value} {' '.join(dict.fromkeys(additions))}"
    return value


def tokens(value: str) -> list[str]:
    return re.findall(r"[a-z]+(?:'[a-z]+)?|[0-9]+(?:\.[0-9]+)?", value)


def important_terms(value: str) -> list[str]:
    return [
        token
        for token in tokens(value)
        if token not in STOPWORDS and (len(token) > 1 or any(char.isdigit() for char in token))
    ]


def read_jsonl(path: str | Path) -> Iterable[dict[str, Any]]:
    input_path = Path(path)
    with input_path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                yield json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {input_path}:{line_number}") from exc


def _score_phrase(
    phrase: str,
    norm_text: str,
    object_tokens: set[str],
    obj: dict[str, Any],
) -> dict[str, Any]:
    norm_phrase = normalize_text(phrase)
    phrase_terms = important_terms(norm_phrase)
    number_terms = [term for term in phrase_terms if _is_number(term)]
    non_numeric_terms = [term for term in phrase_terms if not _is_number(term)]
    matched_terms = [term for term in phrase_terms if term in object_tokens]
    matched_numbers = [
        number
        for number in number_terms
        if _number_matches_object(number, object_tokens, obj)
    ]
    exact_match = bool(norm_phrase and norm_phrase in norm_text)
    coverage = len(matched_terms) / len(phrase_terms) if phrase_terms else 0.0
    non_numeric_coverage = (
        len([term for term in non_numeric_terms if term in object_tokens]) / len(non_numeric_terms)
        if non_numeric_terms
        else 0.0
    )
    numeric_complete = bool(number_terms) and len(matched_numbers) == len(number_terms)

    score = 0.0
    if exact_match:
        score += 5.0
    if numeric_complete:
        score += 3.0
    elif matched_numbers:
        score += 1.5 * len(matched_numbers)
    score += coverage * 3.0
    if len(non_numeric_terms) == 1 and not number_terms:
        score *= 0.55

    if numeric_complete and non_numeric_coverage >= 0.35:
        match_level: Literal["direct", "partial", "missing"] = "direct"
    elif exact_match and (len(non_numeric_terms) >= 2 or number_terms):
        match_level = "direct"
    elif matched_numbers or coverage >= 0.35:
        match_level = "partial"
    else:
        match_level = "missing"

    return {
        "phrase": phrase,
        "match_level": match_level,
        "score": round(score, 4),
        "exact_match": exact_match,
        "coverage": round(coverage, 4),
        "important_terms": phrase_terms,
        "matched_terms": matched_terms,
        "numbers": number_terms,
        "matched_numbers": matched_numbers,
    }


def _number_matches_object(
    number: str,
    object_tokens: set[str],
    obj: dict[str, Any],
) -> bool:
    if number in object_tokens:
        return True
    value = obj.get("value")
    if value is None:
        return False
    try:
        target = float(number)
        object_value = float(value)
    except (TypeError, ValueError):
        return False
    if target == 0:
        return object_value == 0
    if math.isclose(target, object_value, rel_tol=0.01, abs_tol=0.01):
        return True
    # Handle phrase values stated in billions while table metrics are stored in millions.
    return math.isclose(target * 1000.0, object_value, rel_tol=0.03, abs_tol=2.0)


def _is_number(value: str) -> bool:
    return bool(re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", value))


def _confidence(
    label: VerificationLabel,
    score: float,
    phrase_count: int,
    matched_phrase_count: int,
) -> float:
    if label == "false":
        return round(min(0.95, 0.45 + max(0, phrase_count - matched_phrase_count) * 0.08), 4)
    base = 0.55 if label == "partial" else 0.68
    return round(min(0.98, base + min(score, 12.0) / 40.0), 4)
