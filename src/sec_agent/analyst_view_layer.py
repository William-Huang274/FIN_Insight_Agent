from __future__ import annotations

import hashlib
from collections.abc import Iterable
from collections import Counter, defaultdict
from typing import Any, Mapping

from sec_agent.claim_evidence_ledger import build_evidence_governance_ledgers
from sec_agent.derived_metric_layer import build_derived_metric_layer


ANALYST_VIEW_LAYER_SCHEMA_VERSION = "sec_agent_analyst_view_research_memory_v0.1"

ALLOWED_VIEW_SOURCE_LAYERS = {"claim_evidence_ledger", "typed_gap_ledger", "derived_metric_layer"}
VIEW_TYPES = {
    "company_profile_view",
    "segment_model_view",
    "product_kpi_view",
    "earnings_change_view",
    "risk_factor_view",
    "bull_bear_debate_view",
    "thesis_tracker",
}
RAW_REF_FIELDS = {
    "evidence_refs",
    "supporting_evidence_ids",
    "input_evidence_refs",
    "input_source_ids",
    "source_ids",
    "raw_source_refs",
}


def build_analyst_view_research_memory_layer(state: Mapping[str, Any]) -> dict[str, Any]:
    ledgers = _governance_ledgers(state)
    claim_ledger = ledgers["claim_evidence_ledger"]
    gap_ledger = ledgers["typed_gap_ledger"]
    derived_layer = (
        state.get("derived_metric_layer")
        if isinstance(state.get("derived_metric_layer"), Mapping)
        else build_derived_metric_layer(state)
    )
    claims = [dict(row) for row in claim_ledger.get("claims") or [] if isinstance(row, Mapping)]
    gaps = [dict(row) for row in gap_ledger.get("gaps") or [] if isinstance(row, Mapping)]
    derived_metrics = [dict(row) for row in derived_layer.get("derived_metrics") or [] if isinstance(row, Mapping)]

    views: list[dict[str, Any]] = []
    views.extend(_company_profile_views(claims, gaps, derived_metrics))
    views.extend(_segment_model_views(claims, gaps, derived_metrics))
    views.extend(_product_kpi_views(claims, gaps, derived_metrics))
    views.extend(_earnings_change_views(claims, gaps, derived_metrics))
    views.extend(_risk_factor_views(claims, gaps))
    views.extend(_bull_bear_debate_views(claims, gaps, derived_metrics))
    views.extend(_thesis_tracker_views(claims, gaps, derived_metrics))
    views = _dedupe_views(views)
    memory_entries = [_memory_entry(view) for view in views]
    payload = {
        "schema_version": ANALYST_VIEW_LAYER_SCHEMA_VERSION,
        "policy": "analyst_views_are_not_sources_must_drill_down_to_ledgers_v0_1",
        "run_id": str(state.get("run_id") or ""),
        "view_count": len(views),
        "memory_entry_count": len(memory_entries),
        "analyst_views": views,
        "research_memory_entries": memory_entries,
        "summary": {
            "by_view_type": dict(sorted(Counter(row.get("view_type") or "unknown" for row in views).items())),
            "by_view_status": dict(sorted(Counter(row.get("view_status") or "unknown" for row in views).items())),
            "company_count": len({row.get("ticker") for row in views if row.get("ticker")}),
            "claim_ref_count": len({ref for row in views for ref in row.get("claim_ids") or []}),
            "gap_ref_count": len({ref for row in views for ref in row.get("gap_ids") or []}),
            "derived_metric_ref_count": len({ref for row in views for ref in row.get("derived_metric_ids") or []}),
            "not_source_policy": "views_must_not_support_claims_without_drilldown",
        },
    }
    payload["validation"] = validate_analyst_view_research_memory_layer(payload)
    return _jsonable(payload)


def validate_analyst_view_research_memory_layer(payload: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    views = [row for row in payload.get("analyst_views") or [] if isinstance(row, Mapping)]
    entries = [row for row in payload.get("research_memory_entries") or [] if isinstance(row, Mapping)]
    view_ids = {str(row.get("view_id") or "") for row in views if str(row.get("view_id") or "").strip()}
    seen_view_ids: set[str] = set()
    for index, view in enumerate(views):
        view_id = str(view.get("view_id") or "").strip()
        view_type = str(view.get("view_type") or "").strip()
        if not view_id:
            errors.append({"type": "view_id_required", "index": index})
        elif view_id in seen_view_ids:
            errors.append({"type": "duplicate_view_id", "view_id": view_id})
        seen_view_ids.add(view_id)
        if view_type not in VIEW_TYPES:
            errors.append({"type": "invalid_view_type", "view_id": view_id, "view_type": view_type})
        source_layers = set(_string_list(view.get("source_layers")))
        if not source_layers:
            errors.append({"type": "view_source_layers_required", "view_id": view_id})
        if source_layers - ALLOWED_VIEW_SOURCE_LAYERS:
            errors.append({"type": "view_uses_disallowed_source_layer", "view_id": view_id, "source_layers": sorted(source_layers)})
        if not _has_ledger_ref(view):
            warnings.append({"type": "view_without_ledger_refs", "view_id": view_id})
        if str(view.get("evidence_policy") or "") != "view_is_not_source_must_drill_down_to_ledgers":
            errors.append({"type": "view_evidence_policy_invalid", "view_id": view_id})
        for field in RAW_REF_FIELDS:
            if view.get(field):
                errors.append({"type": "view_contains_raw_source_reference", "view_id": view_id, "field": field})
    seen_entry_ids: set[str] = set()
    for index, entry in enumerate(entries):
        entry_id = str(entry.get("memory_entry_id") or "").strip()
        view_id = str(entry.get("view_id") or "").strip()
        if not entry_id:
            errors.append({"type": "memory_entry_id_required", "index": index})
        elif entry_id in seen_entry_ids:
            errors.append({"type": "duplicate_memory_entry_id", "memory_entry_id": entry_id})
        seen_entry_ids.add(entry_id)
        if view_id not in view_ids:
            errors.append({"type": "memory_entry_unknown_view_id", "memory_entry_id": entry_id, "view_id": view_id})
        if str(entry.get("memory_status") or "") != "run_scoped_candidate":
            errors.append({"type": "memory_entry_status_invalid", "memory_entry_id": entry_id})
        if str(entry.get("retrieval_policy") or "") != "retrieve_view_then_drill_down_to_claim_gap_derived_refs":
            errors.append({"type": "memory_entry_retrieval_policy_invalid", "memory_entry_id": entry_id})
        for field in RAW_REF_FIELDS:
            if entry.get(field):
                errors.append({"type": "memory_entry_contains_raw_source_reference", "memory_entry_id": entry_id, "field": field})
    return {
        "schema_version": "sec_agent_analyst_view_research_memory_validation_v0.1",
        "status": "fail" if errors else "pass",
        "errors": errors,
        "warnings": warnings,
    }


def _company_profile_views(claims: list[dict[str, Any]], gaps: list[dict[str, Any]], derived: list[dict[str, Any]]) -> list[dict[str, Any]]:
    views = []
    for ticker in _all_tickers(claims, gaps, derived):
        c = _claims_for_ticker(claims, ticker)
        g = _gaps_for_ticker(gaps, ticker)
        d = _derived_for_ticker(derived, ticker)
        views.append(
            _view(
                view_type="company_profile_view",
                ticker=ticker,
                product_or_segment="",
                title=f"{ticker} company profile view",
                claims=c,
                gaps=g,
                derived=d,
                focus_tags=["company_profile", "business_overview", "evidence_readiness"],
            )
        )
    return views


def _segment_model_views(claims: list[dict[str, Any]], gaps: list[dict[str, Any]], derived: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, list[dict[str, Any]]]] = defaultdict(lambda: {"claims": [], "gaps": [], "derived": []})
    for gap in gaps:
        product = str(gap.get("product_or_segment") or "").strip()
        if product:
            grouped[(str(gap.get("ticker") or "__run__").upper(), product)]["gaps"].append(gap)
    for metric in derived:
        product = str(metric.get("product_or_segment") or "").strip()
        if product:
            grouped[(str(metric.get("ticker") or "__run__").upper(), product)]["derived"].append(metric)
    for claim in claims:
        product = _claim_product_hint(claim)
        if product:
            grouped[(str(claim.get("ticker") or "__run__").upper(), product)]["claims"].append(claim)
    return [
        _view(
            view_type="segment_model_view",
            ticker=ticker,
            product_or_segment=product,
            title=f"{ticker} {product} segment model view",
            claims=rows["claims"],
            gaps=rows["gaps"],
            derived=rows["derived"],
            focus_tags=["segment", "product_or_business_line"],
        )
        for (ticker, product), rows in sorted(grouped.items())
    ]


def _product_kpi_views(claims: list[dict[str, Any]], gaps: list[dict[str, Any]], derived: list[dict[str, Any]]) -> list[dict[str, Any]]:
    product_metric_families = {"asp", "arpu", "take_rate", "yoy_growth", "qoq_growth"}
    grouped: dict[tuple[str, str], dict[str, list[dict[str, Any]]]] = defaultdict(lambda: {"claims": [], "gaps": [], "derived": []})
    for metric in derived:
        if str(metric.get("derived_metric_family") or "") in product_metric_families and str(metric.get("product_key") or "") != "__company_total__":
            product = str(metric.get("product_or_segment") or metric.get("product_key") or "").strip()
            grouped[(str(metric.get("ticker") or "__run__").upper(), product)]["derived"].append(metric)
    for gap in gaps:
        if gap.get("product_or_segment") or _is_product_metric(gap.get("metric")):
            product = str(gap.get("product_or_segment") or "__product_unknown__").strip()
            grouped[(str(gap.get("ticker") or "__run__").upper(), product)]["gaps"].append(gap)
    for claim in claims:
        if _claim_has_product_signal(claim):
            product = _claim_product_hint(claim) or "__product_unknown__"
            grouped[(str(claim.get("ticker") or "__run__").upper(), product)]["claims"].append(claim)
    return [
        _view(
            view_type="product_kpi_view",
            ticker=ticker,
            product_or_segment=product,
            title=f"{ticker} {product} product KPI view",
            claims=rows["claims"],
            gaps=rows["gaps"],
            derived=rows["derived"],
            focus_tags=["product_kpi", "company_disclosed_product_metric"],
        )
        for (ticker, product), rows in sorted(grouped.items())
    ]


def _earnings_change_views(claims: list[dict[str, Any]], gaps: list[dict[str, Any]], derived: list[dict[str, Any]]) -> list[dict[str, Any]]:
    earnings_families = {"yoy_growth", "qoq_growth", "gross_margin", "operating_margin", "free_cash_flow_margin"}
    views = []
    for ticker in _all_tickers(claims, gaps, derived):
        c = [row for row in _claims_for_ticker(claims, ticker) if _text_has_any(row, ["growth", "margin", "earnings", "revenue", "profit", "decline", "increase", "decrease"])]
        g = [row for row in _gaps_for_ticker(gaps, ticker) if _text_has_any(row, ["period", "unit", "conflict", "revenue", "margin", "growth"])]
        d = [row for row in _derived_for_ticker(derived, ticker) if str(row.get("derived_metric_family") or "") in earnings_families]
        if c or g or d:
            views.append(
                _view(
                    view_type="earnings_change_view",
                    ticker=ticker,
                    product_or_segment="",
                    title=f"{ticker} earnings change view",
                    claims=c,
                    gaps=g,
                    derived=d,
                    focus_tags=["earnings_change", "margin", "growth"],
                )
            )
    return views


def _risk_factor_views(claims: list[dict[str, Any]], gaps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    views = []
    for ticker in _all_tickers(claims, gaps, []):
        c = [row for row in _claims_for_ticker(claims, ticker) if _text_has_any(row, ["risk", "uncertain", "pressure", "headwind", "litigation", "regulatory", "competition"])]
        g = [row for row in _gaps_for_ticker(gaps, ticker) if str(row.get("gap_type") or "") in {"commercial_gap", "not_disclosed", "conflict_gap", "staleness_gap", "source_boundary_blocked"}]
        if c or g:
            views.append(
                _view(
                    view_type="risk_factor_view",
                    ticker=ticker,
                    product_or_segment="",
                    title=f"{ticker} risk factor view",
                    claims=c,
                    gaps=g,
                    derived=[],
                    focus_tags=["risk", "counterevidence", "gap_boundary"],
                )
            )
    return views


def _bull_bear_debate_views(claims: list[dict[str, Any]], gaps: list[dict[str, Any]], derived: list[dict[str, Any]]) -> list[dict[str, Any]]:
    views = []
    for ticker in _all_tickers(claims, gaps, derived):
        c = _claims_for_ticker(claims, ticker)
        g = _gaps_for_ticker(gaps, ticker)
        d = _derived_for_ticker(derived, ticker)
        if c or g:
            views.append(
                _view(
                    view_type="bull_bear_debate_view",
                    ticker=ticker,
                    product_or_segment="",
                    title=f"{ticker} bull bear debate view",
                    claims=c,
                    gaps=g,
                    derived=d[:8],
                    focus_tags=["bull_bear", "thesis_vs_counterthesis"],
                )
            )
    return views


def _thesis_tracker_views(claims: list[dict[str, Any]], gaps: list[dict[str, Any]], derived: list[dict[str, Any]]) -> list[dict[str, Any]]:
    views = []
    for ticker in _all_tickers(claims, gaps, derived):
        c = _claims_for_ticker(claims, ticker)
        g = _gaps_for_ticker(gaps, ticker)
        d = _derived_for_ticker(derived, ticker)
        if c or g or d:
            views.append(
                _view(
                    view_type="thesis_tracker",
                    ticker=ticker,
                    product_or_segment="",
                    title=f"{ticker} thesis tracker",
                    claims=c,
                    gaps=g,
                    derived=d,
                    focus_tags=["thesis_tracker", "claim_status", "open_gaps"],
                )
            )
    return views


def _view(
    *,
    view_type: str,
    ticker: str,
    product_or_segment: str,
    title: str,
    claims: list[Mapping[str, Any]],
    gaps: list[Mapping[str, Any]],
    derived: list[Mapping[str, Any]],
    focus_tags: list[str],
) -> dict[str, Any]:
    claim_ids = _unique_strings(row.get("claim_id") for row in claims)
    gap_ids = _unique_strings(row.get("gap_id") for row in gaps)
    derived_ids = _unique_strings(row.get("derived_metric_id") for row in derived)
    status_counts = Counter(str(row.get("claim_status") or "unknown") for row in claims)
    gap_counts = Counter(str(row.get("gap_type") or "unknown") for row in gaps)
    derived_counts = Counter(str(row.get("derived_metric_family") or "unknown") for row in derived)
    status = _view_status(status_counts=status_counts, gaps=gaps)
    view_id = _stable_id("analyst_view", view_type, ticker, product_or_segment, ",".join(claim_ids), ",".join(gap_ids), ",".join(derived_ids))
    return {
        "view_id": view_id,
        "view_type": view_type,
        "ticker": ticker,
        "product_or_segment": product_or_segment,
        "title": title,
        "view_status": status,
        "focus_tags": _unique_strings(focus_tags),
        "claim_ids": claim_ids,
        "gap_ids": gap_ids,
        "derived_metric_ids": derived_ids,
        "drilldown_refs": {
            "claim_evidence_ledger": claim_ids,
            "typed_gap_ledger": gap_ids,
            "derived_metric_layer": derived_ids,
        },
        "source_layers": sorted(layer for layer, refs in {
            "claim_evidence_ledger": claim_ids,
            "typed_gap_ledger": gap_ids,
            "derived_metric_layer": derived_ids,
        }.items() if refs),
        "summary_signals": {
            "claim_count": len(claim_ids),
            "gap_count": len(gap_ids),
            "derived_metric_count": len(derived_ids),
            "by_claim_status": dict(sorted(status_counts.items())),
            "by_gap_type": dict(sorted(gap_counts.items())),
            "by_derived_metric_family": dict(sorted(derived_counts.items())),
        },
        "evidence_policy": "view_is_not_source_must_drill_down_to_ledgers",
        "claim_boundary": "analyst_view_is_index_not_fact_source",
    }


def _memory_entry(view: Mapping[str, Any]) -> dict[str, Any]:
    view_id = str(view.get("view_id") or "")
    return {
        "memory_entry_id": _stable_id("research_memory", view_id),
        "view_id": view_id,
        "view_type": str(view.get("view_type") or ""),
        "ticker": str(view.get("ticker") or ""),
        "product_or_segment": str(view.get("product_or_segment") or ""),
        "memory_status": "run_scoped_candidate",
        "retrieval_policy": "retrieve_view_then_drill_down_to_claim_gap_derived_refs",
        "claim_ids": list(view.get("claim_ids") or []),
        "gap_ids": list(view.get("gap_ids") or []),
        "derived_metric_ids": list(view.get("derived_metric_ids") or []),
        "source_layers": list(view.get("source_layers") or []),
        "claim_boundary": "memory_entry_is_not_source_and_requires_ledger_drilldown",
    }


def _view_status(*, status_counts: Counter[str], gaps: list[Mapping[str, Any]]) -> str:
    if status_counts.get("contradicted") or any(str(row.get("gap_type") or "") in {"conflict_gap", "source_boundary_blocked"} for row in gaps):
        return "conflict_or_boundary_limited"
    if status_counts.get("gap_exposed") or gaps:
        return "partial_with_open_gaps"
    if status_counts.get("supported"):
        return "supported_claims_available"
    if status_counts.get("weakly_supported"):
        return "weak_support_only"
    return "index_only"


def _governance_ledgers(state: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    claim_ledger = state.get("claim_evidence_ledger") if isinstance(state.get("claim_evidence_ledger"), Mapping) else {}
    gap_ledger = state.get("typed_gap_ledger") if isinstance(state.get("typed_gap_ledger"), Mapping) else {}
    if claim_ledger and gap_ledger:
        return {"claim_evidence_ledger": claim_ledger, "typed_gap_ledger": gap_ledger}
    generated = build_evidence_governance_ledgers(state)
    return {
        "claim_evidence_ledger": claim_ledger or generated.get("claim_evidence_ledger") or {},
        "typed_gap_ledger": gap_ledger or generated.get("typed_gap_ledger") or {},
    }


def _all_tickers(claims: list[Mapping[str, Any]], gaps: list[Mapping[str, Any]], derived: list[Mapping[str, Any]]) -> list[str]:
    tickers = _unique_strings(
        [
            *[str(row.get("ticker") or "").upper() for row in claims],
            *[str(row.get("ticker") or "").upper() for row in gaps],
            *[str(row.get("ticker") or "").upper() for row in derived],
        ]
    )
    return sorted(tickers or ["__RUN__"])


def _claims_for_ticker(claims: list[Mapping[str, Any]], ticker: str) -> list[dict[str, Any]]:
    return [dict(row) for row in claims if _ticker_match(row, ticker)]


def _gaps_for_ticker(gaps: list[Mapping[str, Any]], ticker: str) -> list[dict[str, Any]]:
    return [dict(row) for row in gaps if _ticker_match(row, ticker)]


def _derived_for_ticker(derived: list[Mapping[str, Any]], ticker: str) -> list[dict[str, Any]]:
    return [dict(row) for row in derived if _ticker_match(row, ticker)]


def _ticker_match(row: Mapping[str, Any], ticker: str) -> bool:
    row_ticker = str(row.get("ticker") or "").upper().strip()
    return row_ticker == str(ticker or "").upper().strip() or (not row_ticker and ticker == "__RUN__")


def _claim_product_hint(claim: Mapping[str, Any]) -> str:
    for field in ("product_or_segment", "product", "segment", "business_line"):
        value = str(claim.get(field) or "").strip()
        if value:
            return value
    return ""


def _claim_has_product_signal(claim: Mapping[str, Any]) -> bool:
    return bool(_claim_product_hint(claim)) or _text_has_any(
        claim,
        ["product", "segment", "deliveries", "shipments", "subscribers", "arpu", "asp", "backlog", "orders"],
    )


def _is_product_metric(value: Any) -> bool:
    text = str(value or "").lower()
    return any(term in text for term in ["product", "segment", "deliver", "shipment", "subscriber", "arpu", "asp", "backlog", "order", "gmv"])


def _text_has_any(row: Mapping[str, Any], terms: list[str]) -> bool:
    text = " ".join(
        str(row.get(field) or "")
        for field in ("claim_text", "claim_type", "metric", "metric_scope", "materiality", "direction", "reason", "claim_boundary", "limitations")
    ).lower()
    return any(term.lower() in text for term in terms)


def _has_ledger_ref(row: Mapping[str, Any]) -> bool:
    return bool(row.get("claim_ids") or row.get("gap_ids") or row.get("derived_metric_ids"))


def _dedupe_views(views: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for row in views:
        view_id = str(row.get("view_id") or "")
        if view_id and view_id not in by_id and _has_ledger_ref(row):
            by_id[view_id] = row
    return sorted(by_id.values(), key=lambda row: (str(row.get("ticker") or ""), str(row.get("view_type") or ""), str(row.get("product_or_segment") or "")))


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, Mapping):
        return [str(value).strip()] if str(value).strip() else []
    if isinstance(value, Iterable):
        return [str(item or "").strip() for item in value if str(item or "").strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item or "").strip() for item in value if str(item or "").strip()]
    return [str(value).strip()] if str(value).strip() else []


def _unique_strings(values: Any) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in _string_list(values):
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _stable_id(prefix: str, *values: Any) -> str:
    raw = "|".join(str(value or "") for value in values)
    return f"{prefix}:{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:16]}"


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(child) for key, child in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    return value
