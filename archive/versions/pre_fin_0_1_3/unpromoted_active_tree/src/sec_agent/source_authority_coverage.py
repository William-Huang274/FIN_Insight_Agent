from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


SOURCE_AUTHORITY_COVERAGE_SCHEMA_VERSION = "finsight_source_authority_coverage_v0_1"

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SIGNAL_AUTHORITY_MATRIX_PATH = (
    REPO_ROOT / "data" / "manifests" / "r18_signal_authority_coverage_matrix_v0_2.jsonl"
)


DIMENSION_SUPPORT_SURFACES: dict[str, set[str]] = {
    "fundamentals": {"fundamental_company_disclosure"},
    "product_and_production": {
        "product_and_technology",
        "channel_offer_availability_proxy",
        "developer_ecosystem_proxy",
        "regulated_product_context",
        "regulated_product_identity",
        "technology_research_ip",
        "supply_chain_relationship",
        "public_order_supply_chain_proxy",
    },
    "capital_and_financing": {
        "capital_funding_ownership_market_liquidity",
        "macro_industry_driver",
        "financial_regulatory_context",
    },
    "competition_and_market_position": {
        "industry_competition_market_context",
        "supply_chain_relationship",
        "public_order_supply_chain_proxy",
        "channel_offer_availability_proxy",
        "developer_ecosystem_proxy",
        "technology_research_ip",
        "product_and_technology",
        "app_marketplace_review_proxy",
        "macro_industry_driver",
    },
    "industry_and_supply_chain": {
        "industry_competition_market_context",
        "supply_chain_relationship",
        "public_order_supply_chain_proxy",
        "macro_industry_driver",
        "energy_utility_context",
    },
    "risk_and_counterevidence": {
        "fundamental_company_disclosure",
        "industry_competition_market_context",
        "supply_chain_relationship",
        "public_order_supply_chain_proxy",
        "macro_industry_driver",
        "technology_research_ip",
        "regulated_product_context",
        "capital_funding_ownership_market_liquidity",
        "financial_regulatory_context",
        "energy_utility_context",
    },
}


DIMENSION_SOURCE_ROLES: dict[str, set[str]] = {
    "fundamentals": {"primary_company_disclosure"},
    "product_and_production": {
        "official_product_surface",
        "primary_company_disclosure",
        "channel_offer_proxy",
        "developer_ecosystem_proxy",
        "regulated_product_context",
        "auto_product_identity_context",
        "technology_research_proxy",
        "supply_chain_official_relationship",
        "public_order_proxy",
    },
    "capital_and_financing": {
        "primary_company_disclosure",
        "financial_regulatory_context",
        "macro_official_context",
        "energy_utility_context",
    },
    "competition_and_market_position": {
        "trusted_external_context",
        "supply_chain_official_relationship",
        "public_order_proxy",
        "channel_offer_proxy",
        "developer_ecosystem_proxy",
        "technology_research_proxy",
        "official_product_surface",
        "app_rank_store_proxy",
        "platform_review_proxy",
        "macro_official_context",
    },
    "industry_and_supply_chain": {
        "trusted_external_context",
        "supply_chain_official_relationship",
        "public_order_proxy",
        "macro_official_context",
        "energy_utility_context",
    },
    "risk_and_counterevidence": set(),
}


def load_source_authority_coverage(
    *,
    path: str | Path | None = None,
    focus_tickers: Iterable[str] | None = None,
    search_scope_tickers: Iterable[str] | None = None,
    max_rows_per_ticker: int = 24,
) -> dict[str, Any]:
    rows_path = _repo_path(path or DEFAULT_SIGNAL_AUTHORITY_MATRIX_PATH)
    if not rows_path.exists():
        return {
            "schema_version": SOURCE_AUTHORITY_COVERAGE_SCHEMA_VERSION,
            "status": "not_loaded",
            "rows_path": str(rows_path),
            "rows": [],
            "summary": {"row_count": 0, "reason": "signal_authority_matrix_not_found"},
        }
    rows = _load_jsonl(rows_path)
    payload = build_source_authority_coverage(
        rows,
        focus_tickers=focus_tickers,
        search_scope_tickers=search_scope_tickers,
        max_rows_per_ticker=max_rows_per_ticker,
    )
    payload["rows_path"] = str(rows_path)
    return payload


def build_source_authority_coverage(
    rows: Sequence[Mapping[str, Any]],
    *,
    focus_tickers: Iterable[str] | None = None,
    search_scope_tickers: Iterable[str] | None = None,
    max_rows_per_ticker: int = 24,
) -> dict[str, Any]:
    focus = set(_unique_upper(focus_tickers or []))
    scope = _unique_upper([*(focus_tickers or []), *(search_scope_tickers or [])])
    scope_set = set(scope)
    compact_rows = [_compact_row(row) for row in rows if isinstance(row, Mapping)]
    if scope_set:
        compact_rows = [row for row in compact_rows if str(row.get("ticker") or "").upper() in scope_set]
    selected = _select_rows(compact_rows, focus_tickers=focus, max_rows_per_ticker=max(1, int(max_rows_per_ticker)))
    return {
        "schema_version": SOURCE_AUTHORITY_COVERAGE_SCHEMA_VERSION,
        "status": "loaded",
        "scope_tickers": scope,
        "focus_tickers": sorted(focus),
        "row_count": len(compact_rows),
        "selected_row_count": len(selected),
        "rows": selected,
        "summary": _summary(compact_rows),
        "dimension_coverage": {
            dimension: summarize_dimension_authority(selected, dimension)
            for dimension in sorted(_all_dimensions())
        },
        "policy": "research_lead_reads_source_route_registry_v2_signal_authority_before_targeted_repair_v0_1",
    }


def dimension_source_authority_candidates(
    source_authority_coverage: Mapping[str, Any],
    dimension: str,
    *,
    limit: int = 16,
) -> list[dict[str, Any]]:
    rows = [row for row in source_authority_coverage.get("rows") or [] if isinstance(row, Mapping)]
    matched = [dict(row) for row in rows if _row_matches_dimension(row, dimension)]
    matched.sort(key=_row_rank)
    return matched[: max(1, int(limit))]


def summarize_dimension_authority(
    rows_or_coverage: Sequence[Mapping[str, Any]] | Mapping[str, Any],
    dimension: str,
) -> dict[str, Any]:
    if isinstance(rows_or_coverage, Mapping):
        candidates = dimension_source_authority_candidates(rows_or_coverage, dimension, limit=200)
    else:
        candidates = [dict(row) for row in rows_or_coverage if isinstance(row, Mapping) and _row_matches_dimension(row, dimension)]
    evidence_allowed = [row for row in candidates if row.get("can_enter_evidence_bundle")]
    exact_rows = [row for row in evidence_allowed if row.get("exact_company_fact_authority")]
    thesis_rows = [row for row in evidence_allowed if row.get("thesis_driver_authority")]
    route_debt = [
        row
        for row in candidates
        if str(row.get("admission_decision") or row.get("availability_status") or "") == "route_or_parser_debt"
    ]
    attempt_boundary = [
        row
        for row in candidates
        if str(row.get("admission_decision") or row.get("availability_status") or "") == "attempt_backed_public_boundary"
    ]
    if evidence_allowed:
        gap_classification = "evidence_available_not_yet_claimed"
    elif route_debt:
        gap_classification = "route_or_parser_debt"
    elif attempt_boundary:
        gap_classification = "signal_boundary_or_commercial_gap"
    else:
        gap_classification = "no_registered_source_candidate"
    return {
        "dimension": dimension,
        "candidate_count": len(candidates),
        "evidence_bundle_allowed_count": len(evidence_allowed),
        "exact_company_fact_authority_count": len(exact_rows),
        "thesis_driver_authority_count": len(thesis_rows),
        "route_or_parser_debt_count": len(route_debt),
        "attempt_backed_public_boundary_count": len(attempt_boundary),
        "by_source_role": dict(Counter(str(row.get("source_role") or "") for row in candidates)),
        "by_signal_authority_type": dict(Counter(str(row.get("signal_authority_type") or "") for row in candidates)),
        "by_authority_mode": dict(Counter(str(row.get("authority_mode") or "") for row in candidates)),
        "primary_source_roles": _unique_strings([row.get("source_role") for row in candidates])[:8],
        "primary_source_ids": _unique_strings([row.get("source_id") for row in candidates])[:8],
        "primary_signal_authority_types": _unique_strings([row.get("signal_authority_type") for row in candidates])[:8],
        "gap_classification": gap_classification,
        "has_evidence_bundle_allowed_candidate": bool(evidence_allowed),
        "has_thesis_driver_authority": bool(thesis_rows),
        "has_exact_company_fact_authority": bool(exact_rows),
        "has_route_or_parser_debt": bool(route_debt),
        "sample_candidates": candidates[:6],
    }


def source_authority_repairability(candidates: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    evidence_allowed = [row for row in candidates if row.get("can_enter_evidence_bundle")]
    route_debt = [
        row
        for row in candidates
        if str(row.get("admission_decision") or row.get("availability_status") or "") == "route_or_parser_debt"
    ]
    boundaries = [
        row
        for row in candidates
        if str(row.get("admission_decision") or row.get("availability_status") or "") == "attempt_backed_public_boundary"
    ]
    return {
        "evidence_bundle_allowed_count": len(evidence_allowed),
        "route_or_parser_debt_count": len(route_debt),
        "attempt_backed_public_boundary_count": len(boundaries),
        "repairable_candidate_count": len(evidence_allowed) + len(route_debt),
        "primary_repair_source_roles": _unique_strings([row.get("source_role") for row in [*evidence_allowed, *route_debt]])[:8],
        "primary_repair_source_ids": _unique_strings([row.get("source_id") for row in [*evidence_allowed, *route_debt]])[:8],
        "boundary_source_roles": _unique_strings([row.get("source_role") for row in boundaries])[:8],
        "policy": "Use parser-backed source authority rows for targeted repair; attempt-backed boundaries cannot be promoted.",
    }


def _compact_row(row: Mapping[str, Any]) -> dict[str, Any]:
    authority = row.get("authority") if isinstance(row.get("authority"), Mapping) else {}
    return {
        "ledger_id": str(row.get("ledger_id") or ""),
        "ticker": str(row.get("ticker") or "").upper(),
        "company_name": str(row.get("company_name") or ""),
        "primary_lane_id": str(row.get("primary_lane_id") or ""),
        "source_role": str(row.get("source_role") or authority.get("source_role") or ""),
        "source_id": str(row.get("source_id") or authority.get("source_id") or ""),
        "source_layer": str(row.get("source_layer") or ""),
        "support_surface": str(row.get("support_surface") or authority.get("support_surface") or ""),
        "authority_mode": str(authority.get("authority_mode") or ""),
        "signal_authority_type": str(authority.get("signal_authority_type") or ""),
        "exact_company_fact_authority": bool(authority.get("exact_company_fact_authority")),
        "thesis_driver_authority": bool(authority.get("thesis_driver_authority")),
        "can_enter_evidence_bundle": bool(row.get("can_enter_evidence_bundle") and authority.get("can_enter_evidence_bundle", True)),
        "admission_decision": str(authority.get("admission_decision") or ""),
        "availability_status": str(row.get("availability_status") or authority.get("availability_status") or ""),
        "adapter_parser_status": str(row.get("adapter_parser_status") or authority.get("adapter_parser_status") or ""),
        "claim_scope": str(authority.get("claim_scope") or ""),
        "claim_boundary": str(row.get("claim_boundary") or ""),
        "forbidden_claim_types": [str(item) for item in authority.get("forbidden_claim_types") or [] if str(item).strip()],
        "sample_urls": [str(item) for item in row.get("sample_urls") or [] if str(item).strip()][:3],
        "sample_evidence_refs": [str(item) for item in row.get("sample_evidence_refs") or [] if str(item).strip()][:6],
    }


def _select_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    focus_tickers: set[str],
    max_rows_per_ticker: int,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        ticker = str(row.get("ticker") or "")
        if not ticker:
            continue
        grouped[ticker].append(dict(row))
    selected: list[dict[str, Any]] = []
    for ticker in sorted(grouped):
        selected.extend(sorted(grouped[ticker], key=lambda row: _row_rank(row, focus_tickers=focus_tickers))[:max_rows_per_ticker])
    return selected


def _summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    evidence_allowed = [row for row in rows if row.get("can_enter_evidence_bundle")]
    return {
        "row_count": len(rows),
        "ticker_count": len({str(row.get("ticker") or "") for row in rows if str(row.get("ticker") or "")}),
        "evidence_bundle_allowed_count": len(evidence_allowed),
        "planning_or_gap_only_count": len(rows) - len(evidence_allowed),
        "exact_company_fact_authority_count": len([row for row in evidence_allowed if row.get("exact_company_fact_authority")]),
        "thesis_driver_authority_count": len([row for row in evidence_allowed if row.get("thesis_driver_authority")]),
        "by_source_role": dict(Counter(str(row.get("source_role") or "") for row in rows)),
        "by_source_id": dict(Counter(str(row.get("source_id") or "") for row in rows)),
        "by_support_surface": dict(Counter(str(row.get("support_surface") or "") for row in rows)),
        "by_signal_authority_type": dict(Counter(str(row.get("signal_authority_type") or "") for row in rows)),
        "by_authority_mode": dict(Counter(str(row.get("authority_mode") or "") for row in rows)),
        "by_admission_decision": dict(Counter(str(row.get("admission_decision") or row.get("availability_status") or "") for row in rows)),
    }


def _row_matches_dimension(row: Mapping[str, Any], dimension: str) -> bool:
    key = _dimension_key(dimension)
    if key == "risk_and_counterevidence":
        return bool(row.get("source_role") or row.get("support_surface"))
    surfaces = DIMENSION_SUPPORT_SURFACES.get(key, set())
    roles = DIMENSION_SOURCE_ROLES.get(key, set())
    return str(row.get("support_surface") or "") in surfaces or str(row.get("source_role") or "") in roles


def _dimension_key(dimension: str) -> str:
    value = str(dimension or "")
    if value.startswith("fundamental"):
        return "fundamentals"
    if value.startswith("product"):
        return "product_and_production"
    if value.startswith("capital"):
        return "capital_and_financing"
    if value.startswith("competition"):
        return "competition_and_market_position"
    if value.startswith("industry"):
        return "industry_and_supply_chain"
    if value.startswith("risk"):
        return "risk_and_counterevidence"
    return value


def _all_dimensions() -> set[str]:
    return set(DIMENSION_SUPPORT_SURFACES) | set(DIMENSION_SOURCE_ROLES)


def _row_rank(row: Mapping[str, Any], *, focus_tickers: set[str] | None = None) -> tuple[int, int, int, str, str]:
    focus_tickers = focus_tickers or set()
    authority_rank = 0
    if row.get("exact_company_fact_authority"):
        authority_rank = -40
    elif row.get("thesis_driver_authority"):
        authority_rank = -30
    elif row.get("can_enter_evidence_bundle"):
        authority_rank = -20
    elif str(row.get("admission_decision") or row.get("availability_status") or "") == "route_or_parser_debt":
        authority_rank = -5
    focus_rank = 0 if str(row.get("ticker") or "") in focus_tickers else 1
    layer_rank = {"L1": 0, "L2": 1, "L3": 2, "L4": 3}.get(str(row.get("source_layer") or ""), 4)
    return (focus_rank, authority_rank, layer_rank, str(row.get("ticker") or ""), str(row.get("source_role") or ""))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _repo_path(path: str | Path) -> Path:
    value = Path(path)
    if value.is_absolute():
        return value
    return REPO_ROOT / value


def _unique_upper(values: Iterable[Any]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip().upper()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _unique_strings(values: Iterable[Any]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out
