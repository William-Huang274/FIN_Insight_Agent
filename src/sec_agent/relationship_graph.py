from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping


RELATIONSHIP_GRAPH_SCHEMA_VERSION = "sec_agent_relationship_graph_lookup_v0.1"
RELATIONSHIP_EDGE_SCHEMA_VERSION = "sec_agent_relationship_edge_v0.3"
REPO_ROOT = Path(__file__).resolve().parents[2]


def query_relationship_graph(
    *,
    focus_tickers: list[str] | None = None,
    search_scope_tickers: list[str] | None = None,
    user_query: str = "",
    relationship_graph_path: str | Path | None = None,
    sector_depth_pack_path: str | Path | None = None,
    expected_pack_ids: list[str] | None = None,
    max_relationships: int = 24,
    max_expanded_tickers: int = 12,
    include_sector_depth: bool = True,
) -> dict[str, Any]:
    """Return bounded relationship rows for Universe planning.

    Relationship graph evidence is allowed to expand research scope and form
    hypotheses only. It never supports reported company financial facts.
    """
    focus = _unique_upper(focus_tickers)
    scope = _unique_upper(search_scope_tickers) or focus
    max_rels = _bounded_int(max_relationships, default=24, minimum=1, maximum=100)
    max_tickers = _bounded_int(max_expanded_tickers, default=12, minimum=1, maximum=50)

    graph_path = _resolve_optional_path(relationship_graph_path)
    sector_path = _resolve_optional_path(sector_depth_pack_path) or (REPO_ROOT / "configs" / "sector_depth_packs_v0_2.yaml")

    graph_relationships = _read_relationship_graph_rows(graph_path, focus=focus, scope=scope) if graph_path else []
    sector_relationships = (
        _relationships_from_sector_depth_pack(
            sector_path,
            focus=focus,
            scope=scope,
            user_query=user_query,
            expected_pack_ids=expected_pack_ids or [],
            max_relationships=max_rels,
        )
        if include_sector_depth and sector_path.exists()
        else []
    )
    relationships = _dedupe_relationships([*graph_relationships, *sector_relationships])[:max_rels]
    expanded = _expanded_tickers(focus, relationships)[:max_tickers]
    relationship_rows = [_relationship_row(item, index) for index, item in enumerate(relationships, start=1)]
    inference_counts = _count_by_key(relationships, "inference_level")
    confirmation_counts = _count_by_key(relationships, "confirmation_status")

    source_gaps: list[dict[str, Any]] = []
    if not graph_relationships and not sector_relationships:
        source_gaps.append(
            {
                "source_family": "relationship_graph",
                "reason_code": "no_relationship_rows_matched",
                "reason": "No bounded relationship graph or sector-depth metadata rows matched the requested scope.",
                "source_available": bool(graph_path or sector_path.exists()),
            }
        )

    return {
        "schema_version": RELATIONSHIP_GRAPH_SCHEMA_VERSION,
        "status": "ok" if relationships else "partial",
        "relationships": relationships,
        "relationship_rows": relationship_rows,
        "focus_tickers": focus,
        "expanded_tickers": expanded,
        "included_tickers": _unique_upper([*focus, *expanded]),
        "source_gaps": source_gaps,
        "summary": {
            "relationship_count": len(relationships),
            "relationship_graph_rows": len(graph_relationships),
            "sector_depth_rows": len(sector_relationships),
            "claim_scope": "scope_or_hypothesis_only",
            "financial_fact_policy": "relationship_graph_hypothesis_only",
            "edge_schema_version": RELATIONSHIP_EDGE_SCHEMA_VERSION,
            "inference_level_counts": inference_counts,
            "confirmation_status_counts": confirmation_counts,
            "direct_commercial_edge_source_available": bool(graph_path),
            "direct_commercial_edge_source_gap": "" if graph_path else "No explicit customer/supplier relationship graph artifact was configured; sector-depth rows are inference-only.",
        },
        "artifact_refs": _artifact_refs(graph_path=graph_path, sector_path=sector_path, row_count=len(relationships)),
    }


def relationship_plan_from_lookup(
    lookup: Mapping[str, Any],
    *,
    scope_mode: str,
    focus_tickers: list[str] | None = None,
    relationship_scope_rationale: str = "",
    max_expanded_tickers: int = 12,
    max_relationships: int = 24,
) -> dict[str, Any]:
    relationships = [dict(item) for item in lookup.get("relationships") or [] if isinstance(item, Mapping)]
    focus = _unique_upper(focus_tickers or lookup.get("focus_tickers"))
    expanded = _unique_upper(lookup.get("expanded_tickers") or _expanded_tickers(focus, relationships))[:max_expanded_tickers]
    included = _unique_upper(lookup.get("included_tickers") or [*focus, *expanded])
    return {
        "scope_mode": scope_mode,
        "focus_tickers": focus,
        "expanded_tickers": expanded,
        "included_tickers": included,
        "excluded_tickers": [],
        "relationship_scope_rationale": relationship_scope_rationale
        or "Relationship graph and sector-depth metadata are used only to define research scope and hypotheses.",
        "budget": {
            "max_expanded_tickers": max_expanded_tickers,
            "max_relationships": max_relationships,
            "max_evidence_requirements": max_relationships,
        },
        "relationships": relationships,
        "unsupported_relationships": [],
        "source_family": "relationship_graph",
        "metadata": {
            "lookup_status": lookup.get("status") or "",
            "lookup_schema_version": lookup.get("schema_version") or "",
            "relationship_source": "relationship_graph_lookup",
        },
    }


def _read_relationship_graph_rows(path: Path, *, focus: list[str], scope: list[str]) -> list[dict[str, Any]]:
    if not path.exists() or not path.is_file():
        return []
    allowed = set(scope or focus)
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, Mapping):
                continue
            relationship = _normalize_relationship_row(payload, source="relationship_graph")
            tickers = {relationship.get("ticker"), relationship.get("related_ticker")}
            if allowed and not ({str(item).upper() for item in tickers if item} & allowed):
                continue
            rows.append(relationship)
    return rows


def _relationships_from_sector_depth_pack(
    path: Path,
    *,
    focus: list[str],
    scope: list[str],
    user_query: str,
    expected_pack_ids: list[str],
    max_relationships: int,
) -> list[dict[str, Any]]:
    packs = _read_sector_depth_packs(path)
    if not packs:
        return []
    expected = {str(item).strip() for item in expected_pack_ids if str(item).strip()}
    if expected:
        packs = [pack for pack in packs if str(pack.get("pack_id") or "") in expected]
        if not packs:
            return []
    query_text = str(user_query or "").lower()
    scope_selected: list[dict[str, Any]] = []
    query_selected: list[dict[str, Any]] = []
    for pack in packs:
        reason = _pack_match_reason(pack, focus=focus, scope=scope, query_text=query_text)
        if reason == "scope":
            scope_selected.append(pack)
        elif reason == "query":
            query_selected.append(pack)
    selected = list(scope_selected)
    if not selected or _query_allows_cross_sector_depth(query_text):
        seen_pack_ids = {str(pack.get("pack_id") or "") for pack in selected}
        selected.extend(
            pack
            for pack in query_selected
            if str(pack.get("pack_id") or "") not in seen_pack_ids
        )
    if not selected:
        return []
    relationship_groups: list[list[dict[str, Any]]] = []
    for pack in selected:
        pack_relationships: list[dict[str, Any]] = []
        candidates = _unique_upper([*(pack.get("p0") or []), *(pack.get("p1") or [])])
        for ticker in focus or scope[:1]:
            for related in candidates:
                if related == ticker:
                    continue
                pack_relationships.append(
                    _normalize_relationship_row(
                        {
                            "ticker": ticker,
                            "related_ticker": related,
                            "relationship_type": "sector",
                            "direction": "sector_depth_peer",
                            "financial_link_type": str(pack.get("industry_group") or ""),
                            "metrics_to_check": pack.get("primary_metric_families") or [],
                            "evidence_source_needed": _normalize_required_source_families(pack.get("required_source_families") or []),
                            "evidence_refs": [f"sector_depth_pack:{pack.get('pack_id')}:{related}"],
                            "inclusion_rationale": (
                                f"{related} is included from sector-depth pack {pack.get('pack_id')} "
                                f"as a bounded research-scope hypothesis."
                            ),
                            "notes": "; ".join(pack.get("research_questions") or [])[:600],
                        },
                        source="sector_depth_pack",
                    )
                )
        if pack_relationships:
            relationship_groups.append(pack_relationships)
    return _round_robin_relationship_groups(relationship_groups, max_relationships)


def _read_sector_depth_packs(path: Path) -> list[dict[str, Any]]:
    current: dict[str, Any] | None = None
    list_field = ""
    packs: list[dict[str, Any]] = []
    in_candidates = False
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.rstrip()
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if re.match(r"^\s*-\s+pack_id:", line):
                if current:
                    packs.append(current)
                current = {
                    "pack_id": _quoted_value(stripped.split(":", 1)[1]),
                    "p0": [],
                    "p1": [],
                    "research_questions": [],
                    "primary_metric_families": [],
                    "required_source_families": [],
                }
                list_field = ""
                in_candidates = False
                continue
            if current is None:
                continue
            indent = len(line) - len(line.lstrip(" "))
            if indent <= 4 and not stripped.startswith("-"):
                list_field = ""
                in_candidates = False
            if stripped.startswith("industry_group:"):
                current["industry_group"] = _quoted_value(stripped.split(":", 1)[1])
            elif stripped.startswith("research_questions:"):
                list_field = "research_questions"
            elif stripped.startswith("primary_metric_families:"):
                list_field = "primary_metric_families"
            elif stripped.startswith("required_source_families:"):
                list_field = "required_source_families"
            elif stripped.startswith("candidate_tickers:"):
                in_candidates = True
            elif in_candidates and (stripped.startswith("p0:") or stripped.startswith("p1:")):
                key, value = stripped.split(":", 1)
                current[key] = _inline_yaml_list(value)
            elif list_field and stripped.startswith("-"):
                current.setdefault(list_field, []).append(_quoted_value(stripped[1:]))
    if current:
        packs.append(current)
    return packs


def _pack_matches_scope(pack: Mapping[str, Any], *, focus: list[str], scope: list[str], query_text: str) -> bool:
    return bool(_pack_match_reason(pack, focus=focus, scope=scope, query_text=query_text))


def _round_robin_relationship_groups(groups: list[list[dict[str, Any]]], max_relationships: int) -> list[dict[str, Any]]:
    if not groups:
        return []
    result: list[dict[str, Any]] = []
    max_group_len = max(len(group) for group in groups)
    for offset in range(max_group_len):
        for group in groups:
            if offset >= len(group):
                continue
            result.append(group[offset])
            if len(result) >= max_relationships:
                return result
    return result


def _pack_match_reason(pack: Mapping[str, Any], *, focus: list[str], scope: list[str], query_text: str) -> str:
    candidates = set(_unique_upper([*(pack.get("p0") or []), *(pack.get("p1") or [])]))
    if set(focus) & candidates or set(scope) & candidates:
        return "scope"
    text = " ".join(
        [
            str(pack.get("pack_id") or ""),
            str(pack.get("industry_group") or ""),
            " ".join(str(item) for item in pack.get("research_questions") or []),
        ]
    ).lower()
    if not query_text:
        return False
    query_terms = {
        "ai": ("ai", "gpu", "cloud", "data center", "数据中心", "云", "算力"),
        "power": ("power", "electricity", "utility", "能源", "电力"),
        "financial": ("bank", "credit", "rate", "金融", "利率", "信用"),
        "healthcare": ("health", "drug", "hospital", "医疗", "药"),
    }
    for aliases in query_terms.values():
        if any(_contains_alias(query_text, term) for term in aliases) and any(_contains_alias(text, term) for term in aliases):
            return "query"
    return ""


def _query_allows_cross_sector_depth(query_text: str) -> bool:
    text = str(query_text or "").lower()
    if not text:
        return False
    ai_terms = (
        "ai",
        "artificial intelligence",
        "ai infrastructure",
        "gpu",
        "cloud capex",
        "data center",
        "datacenter",
        "数据中心",
        "算力",
        "云",
    )
    power_terms = (
        "power",
        "electric",
        "electricity",
        "utility",
        "utilities",
        "load",
        "电力",
        "负荷",
        "公用事业",
    )
    transmission_terms = (
        "demand transmission",
        "readthrough",
        "supply chain",
        "产业链",
        "传导",
        "读通",
    )
    has_ai_signal = any(_contains_alias(text, term) for term in ai_terms)
    has_power_signal = any(_contains_alias(text, term) for term in power_terms)
    has_transmission_signal = any(_contains_alias(text, term) for term in transmission_terms)
    return has_ai_signal and has_power_signal and has_transmission_signal


def _contains_alias(text: str, alias: str) -> bool:
    term = str(alias or "").strip().lower()
    if not term:
        return False
    if re.fullmatch(r"[a-z0-9][a-z0-9 ._-]*", term):
        pattern = r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])"
        return re.search(pattern, text, flags=re.IGNORECASE) is not None
    return term in text


def _normalize_relationship_row(payload: Mapping[str, Any], *, source: str) -> dict[str, Any]:
    ticker = str(payload.get("ticker") or payload.get("source_ticker") or payload.get("company") or "").upper().strip()
    related = str(payload.get("related_ticker") or payload.get("counterparty") or payload.get("target_ticker") or "").upper().strip()
    refs = _string_list(payload.get("evidence_refs") or payload.get("refs") or payload.get("source_id"))
    if not refs and ticker and related:
        refs = [f"{source}:{ticker}:{related}"]
    relationship_type = str(payload.get("relationship_type") or payload.get("type") or "other").strip()
    direction = str(payload.get("direction") or "unknown").strip()
    metrics = _string_list(payload.get("metrics_to_check") or payload.get("required_metrics"))
    source_pack_id = str(payload.get("source_pack_id") or payload.get("pack_id") or _source_pack_id_from_refs(refs) or "").strip()
    edge_id = str(payload.get("edge_id") or _relationship_edge_id(source, ticker, related, relationship_type, direction, refs)).strip()
    mechanism = str(payload.get("mechanism") or payload.get("financial_link_type") or relationship_type or "").strip()
    inference_level = _normalize_inference_level(payload.get("inference_level"), source=source)
    confirmation_status = str(
        payload.get("confirmation_status")
        or ("no_confirmed_direct_edge" if inference_level in {"sector_inferred", "category_inferred"} else "input_edge_unverified")
    ).strip()
    missing_confirmations = _string_list(payload.get("missing_confirmations"))
    if inference_level in {"sector_inferred", "category_inferred"} and not missing_confirmations:
        missing_confirmations = [
            "direct customer/supplier filing confirmation",
            "contract/order/revenue exposure evidence",
        ]
    evidence_basis = _string_list(payload.get("evidence_basis"))
    if not evidence_basis:
        evidence_basis = ["sector_depth_pack_membership"] if source == "sector_depth_pack" else ["relationship_graph_input"]
    source_limitations = _string_list(payload.get("source_limitations"))
    if source == "sector_depth_pack" and not source_limitations:
        source_limitations = [
            "Sector-depth pack membership supports research-scope inference only.",
            "It does not prove a direct commercial customer/supplier edge.",
        ]
    return {
        "edge_schema_version": RELATIONSHIP_EDGE_SCHEMA_VERSION,
        "edge_id": edge_id,
        "ticker": ticker,
        "related_ticker": related,
        "from_ticker": str(payload.get("from_ticker") or ticker).upper().strip(),
        "to_ticker": str(payload.get("to_ticker") or related).upper().strip(),
        "relationship_type": relationship_type,
        "direction": direction,
        "edge_direction": direction,
        "financial_link_type": str(payload.get("financial_link_type") or "").strip(),
        "mechanism": mechanism,
        "metrics_to_check": metrics,
        "metric_links": metrics,
        "evidence_source_needed": _string_list(payload.get("evidence_source_needed") or payload.get("source_families_needed")),
        "evidence_refs": refs,
        "source_record_ref": refs[0] if refs else "",
        "source_pack_id": source_pack_id,
        "confidence": str(payload.get("confidence") or "medium").strip(),
        "inference_level": inference_level,
        "confirmation_status": confirmation_status,
        "evidence_basis": evidence_basis,
        "missing_confirmations": missing_confirmations,
        "source_limitations": source_limitations,
        "inclusion_rationale": str(payload.get("inclusion_rationale") or payload.get("rationale") or "").strip(),
        "claim_scope": "scope_or_hypothesis_only",
        "notes": str(payload.get("notes") or payload.get("summary") or "").strip(),
        "relationship_source": source,
        "source_family": "relationship_graph",
    }


def _relationship_row(relationship: Mapping[str, Any], index: int) -> dict[str, Any]:
    refs = _string_list(relationship.get("evidence_refs"))
    return {
        "evidence_ref": ",".join(refs) or f"relationship_ref_{index}",
        "edge_schema_version": relationship.get("edge_schema_version") or RELATIONSHIP_EDGE_SCHEMA_VERSION,
        "edge_id": relationship.get("edge_id") or f"relationship_edge_{index}",
        "source_family": "relationship_graph",
        "relationship_source": relationship.get("relationship_source") or "relationship_graph",
        "ticker": relationship.get("ticker") or "",
        "related_ticker": relationship.get("related_ticker") or "",
        "from_ticker": relationship.get("from_ticker") or relationship.get("ticker") or "",
        "to_ticker": relationship.get("to_ticker") or relationship.get("related_ticker") or "",
        "relationship_type": relationship.get("relationship_type") or "",
        "direction": relationship.get("direction") or relationship.get("edge_direction") or "",
        "mechanism": relationship.get("mechanism") or relationship.get("financial_link_type") or "",
        "metric_links": _string_list(relationship.get("metric_links") or relationship.get("metrics_to_check")),
        "source_pack_id": relationship.get("source_pack_id") or "",
        "source_record_ref": relationship.get("source_record_ref") or (refs[0] if refs else ""),
        "summary": relationship.get("inclusion_rationale") or relationship.get("notes") or "",
        "claim_scope": "scope_or_hypothesis_only",
        "inference_level": relationship.get("inference_level") or "unknown",
        "confirmation_status": relationship.get("confirmation_status") or "",
        "evidence_basis": _string_list(relationship.get("evidence_basis")),
        "missing_confirmations": _string_list(relationship.get("missing_confirmations")),
        "source_limitations": _string_list(relationship.get("source_limitations")),
    }


def _relationship_edge_id(
    source: str,
    ticker: str,
    related: str,
    relationship_type: str,
    direction: str,
    refs: list[str],
) -> str:
    payload = "|".join([source, ticker, related, relationship_type, direction, ",".join(refs)])
    return "rel_edge_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _source_pack_id_from_refs(refs: list[str]) -> str:
    for ref in refs:
        match = re.search(r"sector_depth_pack:([^:]+)", str(ref or ""))
        if match:
            return match.group(1)
    return ""


def _normalize_required_source_families(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text in {"us_primary_annual_10k", "us_primary_interim_10q"}:
            result.append("primary_sec_filing")
        elif text == "us_company_authored_8k_earnings":
            result.append("company_authored_unaudited_sec_filing")
        elif text == "market_snapshot":
            result.append("market_snapshot")
        elif text.startswith("industry_"):
            result.append("industry_snapshot")
    return _dedupe_strings(result) or ["primary_sec_filing"]


def _normalize_inference_level(value: Any, *, source: str) -> str:
    text = str(value or "").strip().lower()
    allowed = {
        "confirmed_direct",
        "disclosed_indirect",
        "curated_input_unverified",
        "sector_inferred",
        "category_inferred",
        "user_scope_unverified",
        "unknown",
    }
    if text in allowed:
        return text
    if source == "sector_depth_pack":
        return "sector_inferred"
    if source == "relationship_graph":
        return "curated_input_unverified"
    return "unknown"


def _count_by_key(rows: list[Mapping[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "unknown").strip() or "unknown"
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _expanded_tickers(focus: list[str], relationships: list[Mapping[str, Any]]) -> list[str]:
    focus_set = set(focus)
    tickers: list[str] = []
    for relationship in relationships:
        for key in ("ticker", "related_ticker"):
            ticker = str(relationship.get(key) or "").upper().strip()
            if ticker and ticker not in focus_set:
                tickers.append(ticker)
    return _unique_upper(tickers)


def _dedupe_relationships(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for row in rows:
        key = (
            str(row.get("ticker") or ""),
            str(row.get("related_ticker") or ""),
            str(row.get("relationship_type") or ""),
            str(row.get("direction") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(row)
    return result


def _artifact_refs(*, graph_path: Path | None, sector_path: Path | None, row_count: int) -> list[dict[str, Any]]:
    refs = []
    for artifact_id, path in (("relationship_graph", graph_path), ("sector_depth_pack_metadata", sector_path)):
        if path and path.exists() and path.is_file():
            refs.append(
                {
                    "artifact_id": artifact_id,
                    "path": str(path),
                    "digest": _file_digest(path),
                    "row_count": row_count,
                }
            )
    return refs


def _resolve_optional_path(value: str | Path | None) -> Path | None:
    text = str(value or "").strip()
    if not text:
        return None
    path = Path(text)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path


def _inline_yaml_list(value: str) -> list[str]:
    return re.findall(r'"([^"]+)"', value)


def _quoted_value(value: str) -> str:
    text = str(value or "").strip()
    if text.startswith('"') and text.endswith('"'):
        return text[1:-1]
    return text


def _file_digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return "sha256:" + hasher.hexdigest()[:16]


def _bounded_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(minimum, min(maximum, number))


def _string_list(value: Any) -> list[str]:
    if value is None:
        items: list[Any] = []
    elif isinstance(value, str):
        items = [part.strip() for part in value.split(",") if part.strip()]
    elif isinstance(value, (list, tuple, set)):
        items = list(value)
    else:
        items = [value]
    return _dedupe_strings([str(item or "").strip() for item in items if str(item or "").strip()])


def _unique_upper(value: Any) -> list[str]:
    return _dedupe_strings([item.upper() for item in _string_list(value)])


def _dedupe_strings(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result
