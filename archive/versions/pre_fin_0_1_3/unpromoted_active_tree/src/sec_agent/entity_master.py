from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Any, Mapping

from sec_agent.entities.entity_resolution import build_entity_alias_registry, normalize_entity_name, resolve_entity_name


ENTITY_SECURITY_MASTER_SCHEMA_VERSION = "sec_agent_entity_security_master_v0.1"
IDENTIFIER_FIELDS = ("cik", "lei", "figi", "isin", "cusip", "sedol", "issuer_id")
EXTENDED_ENTITY_FIELDS = (
    "exchange",
    "country",
    "company_domain",
    "ir_domain",
    "security_type",
    "ordinary_share_ticker",
    "adr_ticker",
    "parent_entity_id",
)


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
    for row in _capital_macro_company_entity_rows(state):
        ticker = str(row.get("ticker") or "").upper().strip()
        if ticker and ticker not in existing_tickers:
            entity_rows.append(_entity_from_row(row, source_ref="capital_macro_pack"))
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
    unresolved = [
        *_unresolved_query_entities(state, alias_registry),
        *_unresolved_capital_macro_entities(state, alias_registry),
    ]
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
            "brand_alias_count": sum(len(row.get("brands") or []) for row in entities),
            "subsidiary_alias_count": sum(len(row.get("subsidiaries") or []) for row in entities),
            "product_alias_count": sum(len(row.get("product_aliases") or []) for row in entities),
            "adr_or_common_share_link_count": len(
                [
                    row
                    for row in entities
                    if str(row.get("ordinary_share_ticker") or "").strip() or str(row.get("adr_ticker") or "").strip()
                ]
            ),
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
    brands = _string_list(row.get("brands") or row.get("brand_names"))
    subsidiaries = _string_list(row.get("subsidiaries") or row.get("subsidiary_names"))
    product_aliases = _string_list(row.get("product_aliases") or row.get("product_names"))
    aliases = _unique_strings([ticker, canonical_name, legal_name, *_string_list(row.get("aliases")), *brands, *subsidiaries, *product_aliases])
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
        "exchange": str(row.get("exchange") or row.get("exchange_code") or "").strip(),
        "country": str(row.get("country") or row.get("country_code") or "").strip(),
        "company_domain": str(row.get("company_domain") or row.get("domain") or "").strip(),
        "ir_domain": str(row.get("ir_domain") or "").strip(),
        "security_type": str(row.get("security_type") or row.get("share_class") or "").strip(),
        "ordinary_share_ticker": str(row.get("ordinary_share_ticker") or row.get("local_ticker") or "").upper().strip(),
        "adr_ticker": str(row.get("adr_ticker") or "").upper().strip(),
        "parent_entity_id": str(row.get("parent_entity_id") or row.get("parent_lei") or "").strip(),
        "brands": brands,
        "subsidiaries": subsidiaries,
        "product_aliases": product_aliases,
        "aliases": aliases,
        "normalized_aliases": _unique_strings([normalize_entity_name(alias) for alias in aliases]),
        "resolution_confidence": _resolution_confidence(ticker=ticker, cik=cik, canonical_name=canonical_name, row=row),
        "source_refs": _unique_strings([source_ref, *_string_list(row.get("source_refs"))]),
        "source_priority": _unique_strings(_string_list(row.get("source_priority")) or ["sec_submissions", "gleif", "openfigi", "company_ir", "wikidata_low_weight"]),
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
        for field in ("ticker", "issuer_name", "canonical_name", "legal_name", *IDENTIFIER_FIELDS, *EXTENDED_ENTITY_FIELDS):
            if not existing.get(field) and row.get(field):
                existing[field] = row[field]
        for list_field in ("aliases", "brands", "subsidiaries", "product_aliases", "source_refs", "source_priority"):
            existing[list_field] = _unique_strings([*(existing.get(list_field) or []), *(row.get(list_field) or [])])
        existing["aliases"] = _unique_strings(
            [
                *(existing.get("aliases") or []),
                *(existing.get("brands") or []),
                *(existing.get("subsidiaries") or []),
                *(existing.get("product_aliases") or []),
            ]
        )
        existing["normalized_aliases"] = _unique_strings(
            [*(existing.get("normalized_aliases") or []), *(row.get("normalized_aliases") or [])]
        )
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


def _capital_macro_company_entity_rows(state: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in _iter_capital_macro_rows(state):
        ticker = str(row.get("company_id") or row.get("ticker") or "").upper().strip()
        if not ticker:
            continue
        rows.append(
            {
                "ticker": ticker,
                "company_name": row.get("issuer_name") or row.get("company_name") or row.get("company") or ticker,
                "cusip": row.get("cusip") or "",
                "source_refs": ["capital_macro_pack"],
                "source_priority": ["sec_13f", "sec_fsd", "sec_debt_footnote", "public_source_context"],
            }
        )
    return rows


def _unresolved_capital_macro_entities(state: Mapping[str, Any], alias_registry: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    unresolved: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in _iter_capital_macro_rows(state):
        for role, field in (("investor", "investor_id"), ("insider", "insider_id")):
            raw_name = str(row.get(field) or "").strip()
            if not raw_name:
                continue
            key = f"{role}:{normalize_entity_name(raw_name)}"
            if key in seen:
                continue
            seen.add(key)
            resolved = resolve_entity_name(raw_name, alias_registry)
            if resolved.get("status") == "resolved":
                continue
            unresolved.append(
                {
                    **resolved,
                    "unresolved_reference_id": f"capital_macro_{role}:{_hash_text(raw_name)}",
                    "raw_name": raw_name,
                    "status": "unresolved_context_entity",
                    "source_ref": "capital_macro_pack",
                    "entity_role": role,
                    "treatment_action": "resolve_with_entity_history_or_keep_context_only",
                }
            )
    return unresolved


def _iter_capital_macro_rows(state: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows: list[Mapping[str, Any]] = []
    adapter = state.get("capital_macro_source_adapter") if isinstance(state.get("capital_macro_source_adapter"), Mapping) else {}
    pack = state.get("capital_macro_pack") if isinstance(state.get("capital_macro_pack"), Mapping) else {}
    for container, keys in (
        (
            adapter,
            (
                "capital_ownership_rows",
                "macro_driver_rows",
                "macro_exposure_rows",
                "vertical_official_object_rows",
            ),
        ),
        (
            pack,
            (
                "capital_structures",
                "debt_instruments",
                "credit_facilities",
                "equity_offerings",
                "ownership_positions",
                "insider_transactions",
                "macro_drivers",
                "company_exposure_edges",
                "vertical_official_objects",
            ),
        ),
    ):
        for key in keys:
            rows.extend(row for row in container.get(key) or [] if isinstance(row, Mapping))
    return rows


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
