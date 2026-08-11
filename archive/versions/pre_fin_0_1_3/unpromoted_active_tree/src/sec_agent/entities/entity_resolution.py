from __future__ import annotations

import re
from typing import Any, Mapping


ENTITY_RESOLUTION_SCHEMA_VERSION = "fin_agent_entity_resolution_v0.1"

LEGAL_SUFFIXES = {
    "ag",
    "corp",
    "corporation",
    "co",
    "company",
    "inc",
    "incorporated",
    "limited",
    "ltd",
    "llc",
    "lp",
    "plc",
    "sa",
    "se",
    "nv",
    "holdings",
    "holding",
    "group",
}


def normalize_entity_name(value: Any) -> str:
    """Normalize a company/entity name for exact alias matching."""
    text = str(value or "").strip().lower()
    if not text:
        return ""
    text = text.replace("&", " and ")
    text = re.sub(r"\b(the|class [a-z])\b", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    tokens = [token for token in text.split() if token and token not in LEGAL_SUFFIXES]
    return " ".join(tokens)


def build_entity_alias_registry(companies: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    registry: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in companies:
        ticker = str(row.get("ticker") or row.get("symbol") or "").upper().strip()
        cik = _normalize_cik(row.get("cik") or row.get("cik_str"))
        name = str(row.get("company_name") or row.get("name") or row.get("title") or row.get("company") or "").strip()
        if not ticker and not cik and not name:
            continue
        entity_id = str(row.get("entity_id") or (f"sec_cik:{cik}" if cik else f"ticker:{ticker}")).strip()
        if entity_id in seen:
            continue
        seen.add(entity_id)
        aliases = _unique_strings(
            [
                ticker,
                name,
                row.get("legal_name"),
                *(_string_list(row.get("aliases"))),
            ]
        )
        normalized_aliases = _unique_strings([normalize_entity_name(alias) for alias in aliases])
        registry.append(
            {
                "schema_version": ENTITY_RESOLUTION_SCHEMA_VERSION,
                "entity_id": entity_id,
                "ticker": ticker,
                "cik": cik,
                "canonical_name": name or ticker,
                "aliases": aliases,
                "normalized_aliases": normalized_aliases,
                "source": str(row.get("source") or row.get("source_set") or "universe_manifest").strip(),
            }
        )
    return registry


def resolve_entity_name(raw_name: Any, registry: list[Mapping[str, Any]]) -> dict[str, Any]:
    raw = str(raw_name or "").strip()
    normalized = normalize_entity_name(raw)
    ticker_like = raw.upper().strip()
    if not raw:
        return _unresolved(raw, normalized, reason="empty_raw_name")

    exact_by_alias: dict[str, Mapping[str, Any]] = {}
    exact_by_ticker: dict[str, Mapping[str, Any]] = {}
    for entity in registry:
        ticker = str(entity.get("ticker") or "").upper().strip()
        if ticker:
            exact_by_ticker[ticker] = entity
        for alias in entity.get("normalized_aliases") or []:
            alias_text = str(alias or "").strip()
            if alias_text:
                exact_by_alias.setdefault(alias_text, entity)

    if ticker_like and ticker_like in exact_by_ticker and ticker_like.isascii() and len(ticker_like) <= 8:
        return _resolved(exact_by_ticker[ticker_like], raw=raw, normalized=normalized, matched_alias=ticker_like, confidence="high")
    if normalized and normalized in exact_by_alias:
        return _resolved(exact_by_alias[normalized], raw=raw, normalized=normalized, matched_alias=normalized, confidence="high")

    # Conservative fuzzy step: only accept a containment match when the shorter
    # side is still specific enough to avoid mapping generic terms like "Bank".
    for alias, entity in exact_by_alias.items():
        if len(alias) < 8 or len(normalized) < 8:
            continue
        if alias in normalized or normalized in alias:
            return _resolved(entity, raw=raw, normalized=normalized, matched_alias=alias, confidence="medium")

    return _unresolved(raw, normalized, reason="no_alias_match")


def _resolved(
    entity: Mapping[str, Any],
    *,
    raw: str,
    normalized: str,
    matched_alias: str,
    confidence: str,
) -> dict[str, Any]:
    return {
        "schema_version": ENTITY_RESOLUTION_SCHEMA_VERSION,
        "status": "resolved",
        "confidence": confidence,
        "entity_id": str(entity.get("entity_id") or "").strip(),
        "ticker": str(entity.get("ticker") or "").upper().strip(),
        "cik": _normalize_cik(entity.get("cik")),
        "canonical_name": str(entity.get("canonical_name") or "").strip(),
        "raw_name": raw,
        "normalized_name": normalized,
        "matched_alias": matched_alias,
    }


def _unresolved(raw: str, normalized: str, *, reason: str) -> dict[str, Any]:
    return {
        "schema_version": ENTITY_RESOLUTION_SCHEMA_VERSION,
        "status": "unresolved",
        "confidence": "low",
        "entity_id": "",
        "ticker": "",
        "cik": "",
        "canonical_name": "",
        "raw_name": raw,
        "normalized_name": normalized,
        "matched_alias": "",
        "reason": reason,
    }


def _normalize_cik(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    digits = re.sub(r"\D", "", text)
    return digits.zfill(10) if digits else ""


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item or "").strip() for item in value if str(item or "").strip()]
    return [str(value).strip()]


def _unique_strings(values: list[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result
