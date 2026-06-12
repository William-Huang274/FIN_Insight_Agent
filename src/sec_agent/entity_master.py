from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Any, Mapping

from sec_agent.entities.entity_resolution import build_entity_alias_registry, normalize_entity_name, resolve_entity_name


ENTITY_SECURITY_MASTER_SCHEMA_VERSION = "sec_agent_entity_security_master_v0.1"
IDENTIFIER_FIELDS = ("cik", "lei", "figi", "isin", "cusip", "sedol", "issuer_id")


def build_entity_security_master(state: Mapping[str, Any]) -> dict[str, Any]:
    """Build a conservative per-run Entity / Security Master projection."""
    inventory = state.get("project_inventory") if isinstance(state.get("project_inventory"), Mapping) else {}
    entity_rows: list[dict[str, Any]] = []
    for row in inventory.get("companies") or []:
        if isinstance(row, Mapping):
            entity_rows.append(_entity_from_row(row, source_ref="project_inventory.companies"))

    existing_tickers = {str(row.get("ticker") or "").upper().strip() for row in entity_rows if row.get("ticker")}
    for ticker in _scope_tickers_from_state(state):
        if ticker not in existing_tickers:
            entity_rows.append(_entity_from_row({"ticker": ticker}, source_ref="query_scope"))
            existing_tickers.add(ticker)

    entities = _dedupe_entities(entity_rows)
    alias_registry = build_entity_alias_registry(
        [
            {
                "entity_id": row.get("entity_id"),
                "ticker": row.get("ticker"),
                "cik": row.get("cik"),
                "company_name": row.get("canonical_name") or row.get("issuer_name"),
                "aliases": row.get("aliases") or [],
                "source": "entity_security_master",
            }
            for row in entities
        ]
    )
    unresolved = _unresolved_query_entities(state, alias_registry)
    payload = {
        "schema_version": ENTITY_SECURITY_MASTER_SCHEMA_VERSION,
        "policy": "per_run_entity_security_master_projection_v0_1",
        "entity_count": len(entities),
        "entities": entities,
        "alias_registry": alias_registry,
        "unresolved_references": unresolved,
        "summary": {
            "by_resolution_confidence": dict(sorted(Counter(row.get("resolution_confidence") or "unknown" for row in entities).items())),
            "ticker_count": len([row for row in entities if row.get("ticker")]),
            "cik_count": len([row for row in entities if row.get("cik")]),
            "external_identifier_count": len([row for row in entities if _has_external_identifier(row)]),
            "unresolved_reference_count": len(unresolved),
        },
    }
    payload["validation"] = validate_entity_security_master(payload)
    payload["entity_master_digest"] = _json_digest(payload)
    return payload


def validate_entity_security_master(payload: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    seen_entity_ids: set[str] = set()
    ticker_to_entity: dict[str, str] = {}
    for index, row in enumerate([item for item in payload.get("entities") or [] if isinstance(item, Mapping)]):
        entity_id = str(row.get("entity_id") or "").strip()
        ticker = str(row.get("ticker") or "").upper().strip()
        cik = str(row.get("cik") or "").strip()
        name = str(row.get("canonical_name") or row.get("issuer_name") or "").strip()
        if not entity_id:
            errors.append({"type": "entity_id_required", "index": index})
        elif entity_id in seen_entity_ids:
            errors.append({"type": "duplicate_entity_id", "entity_id": entity_id})
        seen_entity_ids.add(entity_id)
        if not ticker and not cik and not name:
            errors.append({"type": "entity_identifier_required", "entity_id": entity_id})
        if ticker:
            previous = ticker_to_entity.get(ticker)
            if previous and previous != entity_id:
                errors.append({"type": "ticker_maps_to_multiple_entities", "ticker": ticker, "entity_ids": [previous, entity_id]})
            ticker_to_entity[ticker] = entity_id
        if str(row.get("resolution_confidence") or "") == "low":
            warnings.append({"type": "low_confidence_entity_resolution", "entity_id": entity_id, "ticker": ticker})
    return {
        "schema_version": "sec_agent_entity_security_master_validation_v0.1",
        "status": "fail" if errors else "pass",
        "errors": errors,
        "warnings": warnings,
    }


def resolve_entity_reference(raw_name: Any, entity_master: Mapping[str, Any]) -> dict[str, Any]:
    registry = [item for item in entity_master.get("alias_registry") or [] if isinstance(item, Mapping)]
    return resolve_entity_name(raw_name, registry)


def _entity_from_row(row: Mapping[str, Any], *, source_ref: str) -> dict[str, Any]:
    ticker = str(row.get("ticker") or row.get("symbol") or "").upper().strip()
    cik = _normalize_cik(row.get("cik") or row.get("cik_str"))
    issuer_id = str(row.get("issuer_id") or row.get("issuer") or "").strip()
    canonical_name = str(
        row.get("company_name")
        or row.get("company")
        or row.get("name")
        or row.get("title")
        or row.get("canonical_name")
        or ticker
        or issuer_id
    ).strip()
    legal_name = str(row.get("legal_name") or "").strip()
    entity_id = str(row.get("entity_id") or "").strip()
    if not entity_id:
        entity_id = f"sec_cik:{cik}" if cik else f"issuer:{issuer_id}" if issuer_id else f"ticker:{ticker or _hash_text(canonical_name)}"
    aliases = _unique_strings([ticker, canonical_name, legal_name, *_string_list(row.get("aliases"))])
    return {
        "entity_id": entity_id,
        "ticker": ticker,
        "issuer_name": canonical_name,
        "canonical_name": canonical_name,
        "legal_name": legal_name,
        "cik": cik,
        "lei": str(row.get("lei") or "").strip(),
        "figi": str(row.get("figi") or row.get("composite_figi") or "").strip(),
        "isin": str(row.get("isin") or "").strip(),
        "cusip": str(row.get("cusip") or "").strip(),
        "sedol": str(row.get("sedol") or "").strip(),
        "issuer_id": issuer_id,
        "aliases": aliases,
        "normalized_aliases": _unique_strings([normalize_entity_name(alias) for alias in aliases]),
        "resolution_confidence": _resolution_confidence(ticker=ticker, cik=cik, canonical_name=canonical_name, row=row),
        "source_refs": _unique_strings([source_ref, *_string_list(row.get("source_refs"))]),
    }


def _dedupe_entities(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row.get("entity_id") or row.get("ticker") or "").strip()
        if not key:
            continue
        if key not in by_key:
            by_key[key] = dict(row)
            continue
        existing = by_key[key]
        for field in ("ticker", "issuer_name", "canonical_name", "legal_name", *IDENTIFIER_FIELDS):
            if not existing.get(field) and row.get(field):
                existing[field] = row[field]
        existing["aliases"] = _unique_strings([*(existing.get("aliases") or []), *(row.get("aliases") or [])])
        existing["normalized_aliases"] = _unique_strings(
            [*(existing.get("normalized_aliases") or []), *(row.get("normalized_aliases") or [])]
        )
        existing["source_refs"] = _unique_strings([*(existing.get("source_refs") or []), *(row.get("source_refs") or [])])
        if _confidence_rank(row.get("resolution_confidence")) > _confidence_rank(existing.get("resolution_confidence")):
            existing["resolution_confidence"] = row.get("resolution_confidence")
    return sorted(by_key.values(), key=lambda item: (str(item.get("ticker") or ""), str(item.get("entity_id") or "")))


def _scope_tickers_from_state(state: Mapping[str, Any]) -> list[str]:
    contract = state.get("query_contract") if isinstance(state.get("query_contract"), Mapping) else {}
    scope = contract.get("scope") if isinstance(contract.get("scope"), Mapping) else {}
    values: list[Any] = []
    for key in ("focus_tickers", "search_scope_tickers", "selected_tickers"):
        values.extend(_string_list(contract.get(key)))
    for key in ("focus_tickers", "universe_tickers", "search_scope_tickers"):
        values.extend(_string_list(scope.get(key)))
    for raw in _string_list(contract.get("companies")):
        if _looks_like_explicit_ticker(raw):
            values.append(raw)
    values.extend(_string_list(state.get("focus_tickers")))
    values.extend(_string_list(state.get("search_scope_tickers")))
    values.extend(_string_list(state.get("selected_tickers")))
    return _unique_upper(values)


def _unresolved_query_entities(state: Mapping[str, Any], alias_registry: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    contract = state.get("query_contract") if isinstance(state.get("query_contract"), Mapping) else {}
    raw_values = _string_list(contract.get("companies") or contract.get("entities"))
    unresolved: list[dict[str, Any]] = []
    for raw in raw_values:
        resolved = resolve_entity_name(raw, alias_registry)
        if resolved.get("status") != "resolved":
            unresolved.append(resolved)
    return unresolved


def _resolution_confidence(*, ticker: str, cik: str, canonical_name: str, row: Mapping[str, Any]) -> str:
    if ticker and cik:
        return "high"
    if ticker and canonical_name and canonical_name != ticker:
        return "medium"
    if any(str(row.get(field) or "").strip() for field in ("lei", "figi", "isin", "cusip", "sedol", "issuer_id")):
        return "medium"
    return "low"


def _has_external_identifier(row: Mapping[str, Any]) -> bool:
    return any(str(row.get(field) or "").strip() for field in ("lei", "figi", "isin", "cusip", "sedol"))


def _normalize_cik(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    digits = "".join(ch for ch in text if ch.isdigit())
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


def _unique_upper(values: list[Any]) -> list[str]:
    return _unique_strings([str(value or "").upper().strip() for value in values if str(value or "").strip()])


def _confidence_rank(value: Any) -> int:
    return {"low": 1, "medium": 2, "high": 3}.get(str(value or "").strip(), 0)


def _looks_like_explicit_ticker(value: Any) -> bool:
    raw = str(value or "").strip()
    return bool(raw) and raw == raw.upper() and " " not in raw and len(raw) <= 16


def _hash_text(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:10]


def _json_digest(payload: Mapping[str, Any]) -> str:
    stable = dict(payload)
    stable.pop("entity_master_digest", None)
    encoded = json.dumps(stable, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha1(encoded).hexdigest()[:12]
