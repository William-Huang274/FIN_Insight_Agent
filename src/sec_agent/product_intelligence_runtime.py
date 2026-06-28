from __future__ import annotations

import hashlib
import json
import sqlite3
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Sequence


PRODUCT_INTELLIGENCE_RUNTIME_SCHEMA_VERSION = "finsight_product_intelligence_runtime_v0_1"

DEFAULT_PRODUCT_INTELLIGENCE_SQLITE = "data/workbench_private/research_data/product_intelligence_graph_v0_1.sqlite"
DEFAULT_PRODUCT_INTELLIGENCE_PACK_JSONL = "data/manifests/product_intelligence_company_pack_v0_1.jsonl"

EXACT_PRODUCT_KPI_BOUNDARY = (
    "Company-disclosed exact product or business-line row only; does not prove market share, channel inventory, "
    "undisclosed SKU economics, sell-through, ASP, backlog, or customer order value."
)
CONTEXT_BOUNDARY = (
    "Product intelligence context only; may support taxonomy, specs, deployment, channel, supply-chain, or comparable "
    "thesis drivers inside the cited boundary, but cannot become exact revenue, sales, ASP, share, sell-through, "
    "inventory, backlog, or order-value evidence."
)


def product_intelligence_packs_from_state(
    state: Mapping[str, Any],
    *,
    tickers: Sequence[str] | None = None,
    repo_root: str | Path | None = None,
    max_packs: int = 16,
    autoload: bool | None = None,
) -> list[dict[str, Any]]:
    packs = _explicit_packs_from_state(state)
    wanted = _ticker_set(tickers)
    if not wanted:
        wanted = _ticker_set(_state_tickers(state))
    if packs:
        filtered = [pack for pack in packs if not wanted or _ticker(pack) in wanted]
        return filtered[: max(0, int(max_packs or 0))]
    should_load = bool(state.get("product_intelligence_runtime_autoload", True)) if autoload is None else bool(autoload)
    if not should_load or not wanted:
        return []
    return load_product_intelligence_company_packs(
        repo_root or Path.cwd(),
        tickers=sorted(wanted),
        max_packs=max_packs,
    )


def product_intelligence_context_rows_for_state(
    state: Mapping[str, Any],
    *,
    tickers: Sequence[str] | None = None,
    repo_root: str | Path | None = None,
    max_rows: int = 96,
    autoload: bool | None = None,
) -> list[dict[str, Any]]:
    rows = [dict(row) for row in state.get("product_intelligence_context_rows") or [] if isinstance(row, Mapping)]
    packs = product_intelligence_packs_from_state(
        state,
        tickers=tickers,
        repo_root=repo_root,
        max_packs=max(16, len(_ticker_set(tickers)) or 1),
        autoload=autoload,
    )
    for pack in packs:
        rows.extend(product_intelligence_context_rows_from_pack(pack))
    return _dedupe_rows(rows)[: max(0, int(max_rows or 0))]


def compact_product_intelligence_pack_refs(
    state: Mapping[str, Any],
    *,
    tickers: Sequence[str] | None = None,
    repo_root: str | Path | None = None,
    max_packs: int = 8,
    autoload: bool | None = None,
) -> dict[str, Any]:
    packs = product_intelligence_packs_from_state(
        state,
        tickers=tickers,
        repo_root=repo_root,
        max_packs=max_packs,
        autoload=autoload,
    )
    return {
        "schema_version": PRODUCT_INTELLIGENCE_RUNTIME_SCHEMA_VERSION,
        "pack_count": len(packs),
        "packs": [_compact_pack(pack) for pack in packs],
        "policy": "research_lead_and_product_specialist_consume_pig_pack_not_raw_writer_surface_v0_1",
    }


def load_product_intelligence_company_packs(
    repo_root: str | Path,
    *,
    tickers: Sequence[str],
    sqlite_path: str = DEFAULT_PRODUCT_INTELLIGENCE_SQLITE,
    jsonl_path: str = DEFAULT_PRODUCT_INTELLIGENCE_PACK_JSONL,
    max_packs: int = 16,
) -> list[dict[str, Any]]:
    root = Path(repo_root).resolve()
    wanted = tuple(sorted(_ticker_set(tickers)))
    if not wanted:
        return []
    rows = _load_pack_rows_cached(str(root), wanted, sqlite_path, jsonl_path)
    return [normalize_product_intelligence_company_pack(row) for row in rows[: max(0, int(max_packs or 0))]]


def normalize_product_intelligence_company_pack(value: Mapping[str, Any]) -> dict[str, Any]:
    row = dict(value)
    payload = _json_object(row.get("pack_json"))
    for key in (
        "family_ids",
        "gap_ids",
        "memo_writer_boundary",
        "representative_deployment_rows",
        "representative_exact_kpis",
        "representative_operating_metrics",
        "representative_product_profile_or_specs",
        "representative_product_slots",
        "representative_relationship_edges",
    ):
        if key in row and key not in payload:
            payload[key] = row[key]
    pack = {
        "schema_version": str(row.get("schema_version") or "finsight_product_intelligence_company_pack_v0_1"),
        "ticker": _ticker(row) or _ticker(payload),
        "company_name": str(row.get("company_name") or payload.get("company_name") or ""),
        "status": str(row.get("status") or ""),
        "generated_at": str(row.get("generated_at") or ""),
        "counts": {
            "product_family_count": _int(row.get("product_family_count") or _mapping(payload.get("counts")).get("product_family_count")),
            "product_slot_count": _int(row.get("product_slot_count") or _mapping(payload.get("counts")).get("product_slot_count")),
            "product_profile_count": _int(row.get("product_profile_count") or _mapping(payload.get("counts")).get("product_profile_count")),
            "technical_spec_count": _int(row.get("technical_spec_count") or _mapping(payload.get("counts")).get("technical_spec_count")),
            "product_kpi_exact_count": _int(row.get("product_kpi_exact_count") or _mapping(payload.get("counts")).get("product_kpi_exact_count")),
            "industry_operating_metric_count": _int(row.get("industry_operating_metric_count") or _mapping(payload.get("counts")).get("industry_operating_metric_count")),
            "customer_deployment_signal_count": _int(row.get("customer_deployment_signal_count") or _mapping(payload.get("counts")).get("customer_deployment_signal_count")),
            "channel_signal_count": _int(row.get("channel_signal_count") or _mapping(payload.get("counts")).get("channel_signal_count")),
            "supply_chain_signal_count": _int(row.get("supply_chain_signal_count") or _mapping(payload.get("counts")).get("supply_chain_signal_count")),
            "competitive_edge_count": _int(row.get("competitive_edge_count") or _mapping(payload.get("counts")).get("competitive_edge_count")),
            "gap_count": _int(row.get("gap_count") or _mapping(payload.get("counts")).get("gap_count")),
        },
        **payload,
    }
    pack["pack_id"] = f"pig_company_pack:{pack['ticker']}"
    return pack


def product_intelligence_context_rows_from_pack(pack: Mapping[str, Any]) -> list[dict[str, Any]]:
    ticker = _ticker(pack)
    rows: list[dict[str, Any]] = []
    for item in _items(pack.get("representative_product_slots")):
        rows.append(_slot_row(item, ticker=ticker))
    for item in _items(pack.get("representative_exact_kpis")):
        rows.append(_gold_row(item, ticker=ticker, authority="exact_product_kpi"))
    for item in _items(pack.get("representative_operating_metrics")):
        rows.append(_gold_row(item, ticker=ticker, authority="industry_operating_metric"))
    for item in _items(pack.get("representative_product_profile_or_specs")):
        rows.append(_gold_row(item, ticker=ticker, authority="product_profile_or_spec"))
    for item in _items(pack.get("representative_deployment_rows")):
        rows.append(_deployment_row(item, ticker=ticker))
    for item in _items(pack.get("representative_relationship_edges")):
        row = _relationship_row(item, ticker=ticker)
        if row:
            rows.append(row)
    for gap_id in [str(item) for item in pack.get("gap_ids") or [] if str(item).strip()]:
        rows.append(_gap_row(gap_id, pack=pack))
    return _dedupe_rows(rows)


@lru_cache(maxsize=16)
def _load_pack_rows_cached(
    root: str,
    tickers: tuple[str, ...],
    sqlite_path: str,
    jsonl_path: str,
) -> tuple[dict[str, Any], ...]:
    wanted = set(tickers)
    sqlite_target = Path(root) / sqlite_path
    if sqlite_target.exists():
        rows = _load_pack_rows_from_sqlite(sqlite_target, wanted)
        if rows:
            return tuple(rows)
    jsonl_target = Path(root) / jsonl_path
    return tuple(_load_pack_rows_from_jsonl(jsonl_target, wanted))


def _load_pack_rows_from_sqlite(path: Path, tickers: set[str]) -> list[dict[str, Any]]:
    placeholders = ",".join("?" for _ in tickers)
    if not placeholders:
        return []
    query = f"SELECT * FROM product_intelligence_company_packs WHERE ticker IN ({placeholders})"
    with sqlite3.connect(str(path)) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute(query, sorted(tickers)).fetchall()]


def _load_pack_rows_from_jsonl(path: Path, tickers: set[str]) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            row = json.loads(line)
            if _ticker(row) in tickers:
                rows.append(row)
    return rows


def _slot_row(item: Mapping[str, Any], *, ticker: str) -> dict[str, Any]:
    ref = _first(item, "product_slot_id", "source_row_id", "source_id") or _stable_ref("pig_slot", ticker, item)
    return {
        "evidence_ref": ref,
        "source_family": "company_product_evidence_graph",
        "source_class": "product_intelligence_product_slot",
        "source_id": _first(item, "product_slot_id", "source_id") or ref,
        "promotion_status": "runtime_context_taxonomy_only",
        "exact_value_authority": False,
        "ticker": ticker,
        "product_family": _first(item, "family_name", "family_id"),
        "product_family_id": _first(item, "family_id"),
        "product_or_segment": _first(item, "product_slot_name", "family_name"),
        "model_name": _first(item, "product_slot_name"),
        "claim_scope": "product_taxonomy_context",
        "claim_boundary": _first(item, "claim_boundary") or CONTEXT_BOUNDARY,
        "summary": _summary_text("product slot", item),
        "citation_url": _first_url(item),
        "product_intelligence_row": True,
    }


def _gold_row(item: Mapping[str, Any], *, ticker: str, authority: str) -> dict[str, Any]:
    source_id = _first(item, "source_row_id", "gold_row_id", "source_id") or _stable_ref("pig_gold", ticker, item)
    fact_type = str(item.get("fact_type") or "")
    metric = _first(item, "metric_name", "metric_family", "fact_type")
    source_layer = _first(item, "source_layer")
    source_family = "company_product_evidence_graph" if source_layer == "L1" or authority in {"exact_product_kpi", "industry_operating_metric"} else "live_public_web_context"
    promotion = "runtime_fact_allowed" if authority in {"exact_product_kpi", "industry_operating_metric"} else "runtime_context_taxonomy_only"
    row = {
        "evidence_ref": source_id,
        "source_family": source_family,
        "source_class": "product_intelligence_" + authority,
        "source_id": source_id,
        "promotion_status": promotion,
        "exact_value_authority": authority in {"exact_product_kpi", "industry_operating_metric"},
        "ticker": ticker or _ticker(item),
        "company_name": _first(item, "company_name"),
        "product_family": _first(item, "product_family", "product_or_segment"),
        "product_or_segment": _first(item, "product_or_segment", "product_family"),
        "model_name": _first(item, "product_or_segment", "product_family", "metric_name"),
        "metric_family": _metric_family(fact_type, metric),
        "metric": metric,
        "value": _first(item, "value"),
        "unit": _first(item, "unit"),
        "period": _first(item, "period"),
        "effective_date": _first(item, "period") or _first(item, "source_date") or "not_disclosed",
        "citation_url": _first(item, "citation_url"),
        "claim_boundary": _first(item, "claim_boundary") or (EXACT_PRODUCT_KPI_BOUNDARY if authority != "product_profile_or_spec" else CONTEXT_BOUNDARY),
        "summary": _summary_text(authority, item),
        "product_intelligence_row": True,
    }
    if authority == "product_profile_or_spec" and row["value"] and row["unit"] and metric and metric != "product_or_service_profile":
        row.update(
            {
                "spec_name": metric,
                "spec_value": row["value"],
                "spec_unit": row["unit"],
                "claim_scope": "parser_verified_product_spec",
            }
        )
    return row


def _deployment_row(item: Mapping[str, Any], *, ticker: str) -> dict[str, Any]:
    source_id = _first(item, "source_row_id", "gold_row_id", "source_id") or _stable_ref("pig_deployment", ticker, item)
    return {
        "evidence_ref": source_id,
        "source_family": "public_source_context",
        "source_class": "official_customer_deployment_event",
        "source_id": source_id,
        "promotion_status": "context_or_lead_available",
        "exact_value_authority": False,
        "context_only": True,
        "ticker": ticker or _ticker(item),
        "company_name": _first(item, "company_name"),
        "product_family": _first(item, "product_family", "product_or_segment"),
        "product_or_segment": _first(item, "product_or_segment", "product_family"),
        "model_name": _first(item, "product_or_segment", "product_family", "metric_name"),
        "counterparty": _first(item, "counterparty", "customer", "recipient"),
        "deployment_signal": _first(item, "metric_name", "fact_type", "value"),
        "period": _first(item, "period"),
        "citation_url": _first(item, "citation_url"),
        "claim_scope": "official_customer_deployment_context_only",
        "claim_boundary": _first(item, "claim_boundary") or CONTEXT_BOUNDARY,
        "summary": _summary_text("customer deployment signal", item),
        "product_intelligence_row": True,
    }


def _relationship_row(item: Mapping[str, Any], *, ticker: str) -> dict[str, Any] | None:
    authority = str(item.get("authority_type") or "")
    edge_type = str(item.get("edge_type") or "")
    if authority == "template_context_edge" or not bool(item.get("can_enter_evidence_bundle")):
        return None
    source_id = _first(item, "edge_id") or _stable_ref("pig_edge", ticker, item)
    base = {
        "evidence_ref": source_id,
        "source_family": "company_product_evidence_graph",
        "source_class": "product_intelligence_relationship_edge",
        "source_id": source_id,
        "promotion_status": "context_or_lead_available",
        "exact_value_authority": False,
        "context_only": True,
        "ticker": ticker,
        "edge_type": edge_type,
        "authority_type": authority,
        "claim_boundary": _first(item, "claim_boundary") or CONTEXT_BOUNDARY,
        "summary": _summary_text(f"{edge_type} {authority}", item),
        "product_intelligence_row": True,
    }
    if authority == "competitive_context_candidate":
        base.update(
            {
                "object_type": "CompetitiveComparableEdge",
                "product_model_id": _first(item, "from_node_id"),
                "competitor_product_model_id": _first(item, "to_node_id"),
                "comparable_dimensions": [edge_type.lower() or "same_product_family"],
                "region": "global_or_not_disclosed",
            }
        )
    elif authority == "supply_chain_signal":
        base.update(
            {
                "object_type": "ProductSupplyChainSignal",
                "from_product_node_id": _first(item, "from_node_id"),
                "to_product_node_id": _first(item, "to_node_id"),
                "relationship_type": edge_type,
                "claim_scope": "supply_chain_context_only",
            }
        )
    elif authority in {"deployment_signal_authority", "channel_presence_signal"}:
        base.update({"object_type": "CustomerDeploymentSignal", "claim_scope": "official_customer_deployment_context_only"})
    return base


def _gap_row(gap_id: str, *, pack: Mapping[str, Any]) -> dict[str, Any]:
    ticker = _ticker(pack)
    return {
        "evidence_ref": gap_id,
        "source_family": "company_product_evidence_graph",
        "source_class": "product_intelligence_gap",
        "source_id": gap_id,
        "promotion_status": "gap_exposed_not_fallback",
        "exact_value_authority": False,
        "ticker": ticker,
        "missing_metric": "product_intelligence_gap",
        "gap_type": "product_intelligence_gap",
        "why_public_sources_do_not_fill": "ProductIntelligenceGraph gap ledger requires targeted repair or bounded-source classification.",
        "claim_scope": "bounded_gap_not_fallback",
        "summary": f"{ticker} ProductIntelligenceGraph gap {gap_id}.",
        "product_intelligence_row": True,
    }


def _compact_pack(pack: Mapping[str, Any]) -> dict[str, Any]:
    counts = pack.get("counts") if isinstance(pack.get("counts"), Mapping) else {}
    return {
        "pack_id": str(pack.get("pack_id") or ""),
        "ticker": _ticker(pack),
        "company_name": str(pack.get("company_name") or ""),
        "status": str(pack.get("status") or ""),
        "family_ids": [str(item) for item in pack.get("family_ids") or []][:12],
        "counts": dict(counts),
        "gap_ids": [str(item) for item in pack.get("gap_ids") or []][:12],
        "memo_writer_boundary": str(pack.get("memo_writer_boundary") or ""),
    }


def _explicit_packs_from_state(state: Mapping[str, Any]) -> list[dict[str, Any]]:
    candidates: list[Any] = []
    for key in ("product_intelligence_company_pack", "product_intelligence_pack"):
        value = state.get(key)
        if isinstance(value, Mapping):
            candidates.append(value)
    for key in ("product_intelligence_company_packs", "product_intelligence_packs", "product_intelligence_company_pack_rows"):
        value = state.get(key)
        if isinstance(value, Mapping):
            candidates.extend(value.values())
        elif isinstance(value, list):
            candidates.extend(value)
    return [normalize_product_intelligence_company_pack(row) for row in candidates if isinstance(row, Mapping)]


def _state_tickers(state: Mapping[str, Any]) -> list[str]:
    query_contract = state.get("query_contract") if isinstance(state.get("query_contract"), Mapping) else {}
    scope = query_contract.get("scope") if isinstance(query_contract.get("scope"), Mapping) else {}
    activation = state.get("agent_activation_plan") if isinstance(state.get("agent_activation_plan"), Mapping) else {}
    return [
        *_strings(state.get("focus_tickers")),
        *_strings(query_contract.get("focus_tickers")),
        *_strings(scope.get("focus_tickers")),
        *_strings(activation.get("focus_tickers")),
    ]


def _metric_family(fact_type: str, metric: str) -> str:
    text = f"{fact_type} {metric}".lower()
    if "product_revenue" in text or "segment_revenue" in text or "revenue" in text:
        return "product_revenue"
    if "shipment" in text or "volume" in text:
        return "shipments"
    if "capacity" in text:
        return "capacity"
    if "backlog" in text:
        return "backlog"
    return metric or fact_type


def _summary_text(kind: str, item: Mapping[str, Any]) -> str:
    product = _first(item, "product_or_segment", "product_family", "product_slot_name", "metric_name")
    value = _first(item, "value")
    unit = _first(item, "unit")
    period = _first(item, "period")
    boundary = _first(item, "claim_boundary")
    parts = [str(kind), product]
    if value:
        parts.append(f"value={value} {unit}".strip())
    if period:
        parts.append(f"period={period}")
    if boundary:
        parts.append(f"boundary={boundary}")
    return "; ".join(part for part in parts if part)


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return dict(parsed) if isinstance(parsed, Mapping) else {}


def _items(value: Any) -> list[dict[str, Any]]:
    return [dict(item) for item in value or [] if isinstance(item, Mapping)]


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _ticker(value: Mapping[str, Any]) -> str:
    return str(value.get("ticker") or value.get("company_ticker") or "").upper().strip()


def _ticker_set(values: Sequence[str] | None) -> set[str]:
    return {str(item or "").upper().strip() for item in values or [] if str(item or "").strip()}


def _strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if str(item or "").strip()]
    return [str(value)] if str(value or "").strip() else []


def _first(item: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = item.get(key)
        if value is None:
            continue
        if isinstance(value, (list, tuple, set)):
            for subvalue in value:
                text = str(subvalue or "").strip()
                if text:
                    return text
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _first_url(item: Mapping[str, Any]) -> str:
    for key in ("citation_url", "url", "source_url", "snapshot_url"):
        value = _first(item, key)
        if value.startswith(("http://", "https://")):
            return value
    for value in item.get("sample_urls") or []:
        text = str(value or "").strip()
        if text.startswith(("http://", "https://")):
            return text
    return ""


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _stable_ref(prefix: str, ticker: str, item: Mapping[str, Any]) -> str:
    payload = json.dumps({"ticker": ticker, "item": item}, ensure_ascii=True, sort_keys=True, default=str)
    return f"{prefix}:{hashlib.sha1(payload.encode('utf-8')).hexdigest()[:16]}"


def _dedupe_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        ref = _first(row, "evidence_ref", "source_id", "id") or _stable_ref("pig_row", _ticker(row), row)
        key = f"{ref}|{_first(row, 'source_class')}|{_first(row, 'object_type')}"
        if key in seen:
            continue
        seen.add(key)
        out.append(dict(row))
    return out
