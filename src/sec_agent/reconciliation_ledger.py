from __future__ import annotations

import hashlib
import re
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from sec_agent.metric_product_ontology import (
    METRIC_PRODUCT_ONTOLOGY_SCHEMA_VERSION,
    build_metric_product_ontology_snapshot,
    normalize_metric_alias,
    resolve_metric_for_row,
)


RECONCILIATION_LEDGER_SCHEMA_VERSION = "sec_agent_reconciliation_ledger_v0.1"

SOURCE_PRIORITY_RANK = {
    "primary_sec_filing": 100,
    "sec_financial_statement_data_sets": 98,
    "sec_companyfacts_api": 96,
    "company_authored_unaudited_sec_filing": 82,
    "company_product_evidence_graph": 78,
    "company_ir_reports": 76,
    "public_source_context": 20,
    "live_public_web_context": 20,
    "market_snapshot": 10,
    "industry_snapshot": 10,
    "relationship_graph": 10,
    "milvus_semantic": 5,
    "run_artifact": 0,
}

CONTEXT_ONLY_SOURCE_FAMILIES = {
    "public_source_context",
    "live_public_web_context",
    "market_snapshot",
    "industry_snapshot",
    "relationship_graph",
    "milvus_semantic",
    "run_artifact",
}


def build_metric_ontology_and_reconciliation_layers(state: Mapping[str, Any]) -> dict[str, Any]:
    ontology = (
        state.get("metric_product_ontology_snapshot")
        if isinstance(state.get("metric_product_ontology_snapshot"), Mapping)
        else build_metric_product_ontology_snapshot(state)
    )
    ledger = build_reconciliation_ledger({**state, "metric_product_ontology_snapshot": ontology})
    return {
        "metric_product_ontology_snapshot": ontology,
        "reconciliation_ledger": ledger,
    }


def build_reconciliation_ledger(state: Mapping[str, Any]) -> dict[str, Any]:
    ontology = (
        state.get("metric_product_ontology_snapshot")
        if isinstance(state.get("metric_product_ontology_snapshot"), Mapping)
        else build_metric_product_ontology_snapshot(state)
    )
    vintage_index = _vintage_index(state.get("asof_vintage_layer") if isinstance(state.get("asof_vintage_layer"), Mapping) else {})
    candidates: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for channel, row in _iter_candidate_rows(state):
        candidate = _candidate_from_row(row, channel=channel, state=state, ontology=ontology, vintage_index=vintage_index)
        if candidate.get("candidate_status") == "eligible":
            candidates.append(candidate)
        else:
            excluded.append(candidate)

    groups = [_reconcile_group(group_key, rows) for group_key, rows in _group_candidates(candidates).items()]
    groups = sorted(groups, key=lambda row: str(row.get("group_id") or ""))
    conflict_gaps = [_conflict_gap(row) for row in groups if row.get("resolution_status") == "unresolved_conflict"]
    conflict_type_counts = Counter(
        conflict_type
        for group in groups
        for conflict_type in group.get("conflict_types") or []
    )
    payload = {
        "schema_version": RECONCILIATION_LEDGER_SCHEMA_VERSION,
        "policy": "deterministic_reconciliation_no_average_no_proxy_fallback_v0_1",
        "run_id": str(state.get("run_id") or ""),
        "ontology_schema_version": str(ontology.get("schema_version") or ""),
        "candidate_count": len(candidates),
        "excluded_candidate_count": len(excluded),
        "group_count": len(groups),
        "conflict_gap_count": len(conflict_gaps),
        "candidates": candidates,
        "excluded_candidates": excluded,
        "reconciliation_groups": groups,
        "conflict_gaps": conflict_gaps,
        "summary": {
            "by_resolution_status": dict(sorted(Counter(row.get("resolution_status") or "unknown" for row in groups).items())),
            "by_conflict_type": dict(sorted(conflict_type_counts.items())),
            "resolved_group_count": len([row for row in groups if str(row.get("resolution_status") or "").startswith("resolved")]),
            "unresolved_conflict_count": len([row for row in groups if row.get("resolution_status") == "unresolved_conflict"]),
            "preferred_candidate_count": len([row for row in groups if row.get("preferred_value")]),
            "unit_conflict_count": conflict_type_counts.get("unit_conflict", 0),
            "period_conflict_count": conflict_type_counts.get("period_conflict", 0),
            "taxonomy_conflict_count": conflict_type_counts.get("taxonomy_conflict", 0),
            "source_priority_conflict_count": conflict_type_counts.get("source_priority_conflict", 0),
            "rounding_conflict_count": conflict_type_counts.get("rounding_conflict", 0),
        },
    }
    payload["validation"] = validate_reconciliation_ledger(payload)
    return _jsonable(payload)


def validate_reconciliation_ledger(payload: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    candidates_by_id = {
        str(row.get("candidate_id") or ""): row
        for row in payload.get("candidates") or []
        if isinstance(row, Mapping) and str(row.get("candidate_id") or "").strip()
    }
    seen_groups: set[str] = set()
    for index, group in enumerate([row for row in payload.get("reconciliation_groups") or [] if isinstance(row, Mapping)]):
        group_id = str(group.get("group_id") or "").strip()
        status = str(group.get("resolution_status") or "").strip()
        preferred = group.get("preferred_value") if isinstance(group.get("preferred_value"), Mapping) else {}
        candidate_ids = _string_list(group.get("candidate_ids"))
        if not group_id:
            errors.append({"type": "group_id_required", "index": index})
        elif group_id in seen_groups:
            errors.append({"type": "duplicate_reconciliation_group_id", "group_id": group_id})
        seen_groups.add(group_id)
        if not candidate_ids:
            errors.append({"type": "reconciliation_group_without_candidates", "group_id": group_id})
        if status not in {"resolved_single_candidate", "resolved_consensus", "resolved_by_rule", "unresolved_conflict"}:
            errors.append({"type": "invalid_resolution_status", "group_id": group_id, "status": status})
        if status.startswith("resolved"):
            if not preferred:
                errors.append({"type": "resolved_group_without_preferred_value", "group_id": group_id})
            if not str(preferred.get("resolution_rule") or "").strip():
                errors.append({"type": "preferred_value_missing_resolution_rule", "group_id": group_id})
            if not str(preferred.get("confidence") or "").strip():
                errors.append({"type": "preferred_value_missing_confidence", "group_id": group_id})
            preferred_candidate = str(preferred.get("candidate_id") or "")
            if preferred_candidate and preferred_candidate not in candidate_ids:
                errors.append({"type": "preferred_candidate_not_in_group", "group_id": group_id, "candidate_id": preferred_candidate})
        else:
            if preferred:
                errors.append({"type": "unresolved_group_has_preferred_value", "group_id": group_id})
            if not str(group.get("conflict_gap_id") or "").strip():
                errors.append({"type": "unresolved_group_missing_conflict_gap", "group_id": group_id})
        for candidate_id in candidate_ids:
            if candidate_id not in candidates_by_id:
                warnings.append({"type": "group_candidate_missing_from_candidate_table", "group_id": group_id, "candidate_id": candidate_id})
        if "unit_conflict" in (group.get("conflict_types") or []) and status.startswith("resolved"):
            errors.append({"type": "unit_conflict_resolved_without_unit_conversion_policy", "group_id": group_id})
        if "period_conflict" in (group.get("conflict_types") or []) and status.startswith("resolved"):
            errors.append({"type": "period_conflict_resolved_without_period_policy", "group_id": group_id})
        if "taxonomy_conflict" in (group.get("conflict_types") or []) and status.startswith("resolved"):
            errors.append({"type": "taxonomy_conflict_resolved_without_manual_mapping", "group_id": group_id})
    if str(payload.get("ontology_schema_version") or "") != METRIC_PRODUCT_ONTOLOGY_SCHEMA_VERSION:
        warnings.append({"type": "unexpected_ontology_schema_version", "schema_version": payload.get("ontology_schema_version")})
    return {
        "schema_version": "sec_agent_reconciliation_ledger_validation_v0.1",
        "status": "fail" if errors else "pass",
        "errors": errors,
        "warnings": warnings,
    }


def _candidate_from_row(
    row: Mapping[str, Any],
    *,
    channel: str,
    state: Mapping[str, Any],
    ontology: Mapping[str, Any],
    vintage_index: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    evidence_ref = _first_text(row, "evidence_ref", "evidence_id", "metric_id", "fact_id", "object_id")
    source_id = _first_text(row, "source_id") or _stable_id("source", channel, evidence_ref, _first_text(row, "document_id", "accession_number"))
    vintage = _lookup_vintage(vintage_index, source_id=source_id, evidence_ref=evidence_ref)
    metric = resolve_metric_for_row(row, ontology)
    raw_value = _first_text(row, "value", "numeric_value", "raw_value", "raw_value_text")
    numeric_value = _decimal_value(raw_value)
    source_family = _source_family(row, channel=channel)
    exact_authority = _exact_value_authority(row, source_family=source_family)
    has_value = raw_value != ""
    unit = _first_text(row, "unit", "unit_name", "unit_label")
    unit_family = _unit_family(unit=unit, metric=metric)
    unit_gate_reason = _metric_unit_gate_reason(metric, unit_family=unit_family, unit=unit)
    semantic_gate_reason = _metric_semantic_gate_reason(row, metric)
    eligible = (
        has_value
        and exact_authority
        and source_family not in CONTEXT_ONLY_SOURCE_FAMILIES
        and not unit_gate_reason
        and not semantic_gate_reason
    )
    fiscal_year = _first_text(row, "fiscal_year", "year") or _first_text(vintage, "fiscal_year")
    fiscal_period = _first_text(row, "fiscal_period", "period") or _first_text(vintage, "fiscal_period")
    fiscal_period_end = _first_text(row, "fiscal_period_end", "period_end", "source_period_end") or _first_text(vintage, "fiscal_period_end")
    market_as_of = _first_text(row, "market_as_of_date", "as_of_date") or _first_text(vintage, "market_as_of_date")
    macro_vintage = _first_text(row, "macro_vintage_date", "vintage_date") or _first_text(vintage, "macro_vintage_date")
    period_role = _first_text(row, "period_role", "time_basis")
    period_key = _period_key(
        fiscal_year=fiscal_year,
        fiscal_period=fiscal_period,
        fiscal_period_end=fiscal_period_end,
        market_as_of=market_as_of,
        macro_vintage=macro_vintage,
        period_role=period_role,
    )
    product_or_segment = _product_or_segment_from_row(row, metric=metric)
    candidate_id = _first_text(row, "candidate_id") or _stable_id("reconciliation_candidate", channel, evidence_ref, source_id, raw_value)
    status = (
        "eligible"
        if eligible
        else _candidate_exclusion_reason(
            has_value=has_value,
            exact_authority=exact_authority,
            source_family=source_family,
            unit_gate_reason=unit_gate_reason,
            semantic_gate_reason=semantic_gate_reason,
        )
    )
    return {
        "candidate_id": candidate_id,
        "candidate_status": status,
        "run_id": str(state.get("run_id") or ""),
        "channel": channel,
        "source_id": source_id,
        "evidence_ref": evidence_ref,
        "ticker": _first_text(row, "ticker", "symbol", "focus_ticker").upper(),
        "canonical_metric_id": metric.get("canonical_metric_id") or "",
        "metric_type": metric.get("metric_type") or "unknown",
        "metric_match_status": metric.get("match_status") or "unknown",
        "raw_metric_text": metric.get("raw_metric_text") or "",
        "product_or_segment": product_or_segment,
        "product_key": _product_key(product_or_segment),
        "period_key": period_key,
        "fiscal_year": fiscal_year,
        "fiscal_period": fiscal_period,
        "fiscal_period_end": fiscal_period_end,
        "filing_date": _first_text(row, "filing_date") or _first_text(vintage, "filing_date"),
        "accepted_date": _first_text(row, "accepted_date", "accepted_at") or _first_text(vintage, "accepted_date"),
        "market_as_of_date": market_as_of,
        "macro_vintage_date": macro_vintage,
        "time_basis": period_role or _first_text(vintage, "time_basis"),
        "value": raw_value,
        "numeric_value": str(numeric_value) if numeric_value is not None else "",
        "unit": unit,
        "unit_family": unit_family,
        "unit_gate_reason": unit_gate_reason,
        "semantic_gate_reason": semantic_gate_reason,
        "source_family": source_family,
        "source_priority_rank": SOURCE_PRIORITY_RANK.get(source_family, 50),
        "exact_value_authority": exact_authority,
        "form_type": _first_text(row, "form_type"),
        "document_id": _first_text(row, "document_id", "accession_number", "accession", "adsh"),
        "amendment_flag": _amendment_flag(row),
        "parser_version": _first_text(row, "parser_version"),
    }


def _reconcile_group(group_key: tuple[str, str, str, str], rows: list[dict[str, Any]]) -> dict[str, Any]:
    sorted_rows = sorted(rows, key=lambda row: (-int(row.get("source_priority_rank") or 0), str(row.get("accepted_date") or ""), str(row.get("candidate_id") or "")))
    conflict_types = _conflict_types(sorted_rows)
    candidate_ids = [str(row.get("candidate_id") or "") for row in sorted_rows]
    group_id = _stable_id("reconciliation_group", *group_key)
    base = {
        "group_id": group_id,
        "group_key": {
            "ticker": group_key[0],
            "canonical_metric_id": group_key[1],
            "product_key": group_key[2],
            "period_key": group_key[3],
        },
        "ticker": group_key[0],
        "canonical_metric_id": group_key[1],
        "product_or_segment": _display_product(sorted_rows),
        "period_key": group_key[3],
        "candidate_count": len(sorted_rows),
        "candidate_ids": candidate_ids,
        "conflict_types": conflict_types,
    }
    blocking = set(conflict_types) & {"unit_conflict", "period_conflict", "taxonomy_conflict", "segment_conflict"}
    if len(sorted_rows) == 1 and not blocking:
        return {
            **base,
            "resolution_status": "resolved_single_candidate",
            "preferred_value": _preferred_value(sorted_rows[0], resolution_rule="single_exact_authority_candidate", confidence="high"),
            "resolution_notes": [],
            "conflict_gap_id": "",
        }
    if blocking:
        gap_id = _stable_id("conflict_gap", group_id, ",".join(conflict_types))
        return {
            **base,
            "resolution_status": "unresolved_conflict",
            "preferred_value": {},
            "resolution_notes": _resolution_notes(conflict_types),
            "conflict_gap_id": gap_id,
        }
    numeric_values = [_decimal_value(row.get("numeric_value") or row.get("value")) for row in sorted_rows]
    numeric_values = [value for value in numeric_values if value is not None]
    top = sorted_rows[0]
    if not numeric_values or _all_equal(numeric_values):
        return {
            **base,
            "resolution_status": "resolved_consensus",
            "preferred_value": _preferred_value(top, resolution_rule="same_value_highest_source_priority", confidence="high"),
            "resolution_notes": [],
            "conflict_gap_id": "",
        }
    if _rounding_equivalent(numeric_values):
        return {
            **base,
            "conflict_types": _unique_strings([*conflict_types, "rounding_conflict"]),
            "resolution_status": "resolved_by_rule",
            "preferred_value": _preferred_value(top, resolution_rule="rounding_tolerance_highest_source_priority", confidence="medium"),
            "resolution_notes": ["numeric values differ only within rounding tolerance"],
            "conflict_gap_id": "",
        }
    amended = _preferred_amended_candidate(sorted_rows)
    if amended:
        return {
            **base,
            "conflict_types": _unique_strings([*conflict_types, "amendment_conflict"]),
            "resolution_status": "resolved_by_rule",
            "preferred_value": _preferred_value(amended, resolution_rule="amendment_latest_filing_wins", confidence="high"),
            "resolution_notes": ["amended filing candidate supersedes earlier candidate"],
            "conflict_gap_id": "",
        }
    top_rank = int(top.get("source_priority_rank") or 0)
    same_rank = [row for row in sorted_rows if int(row.get("source_priority_rank") or 0) == top_rank]
    if len(same_rank) == 1:
        return {
            **base,
            "conflict_types": _unique_strings([*conflict_types, "source_priority_conflict"]),
            "resolution_status": "resolved_by_rule",
            "preferred_value": _preferred_value(top, resolution_rule="source_priority_highest_authority_wins", confidence="medium"),
            "resolution_notes": ["candidate values differ; selected highest source priority"],
            "conflict_gap_id": "",
        }
    conflict_types = _unique_strings([*conflict_types, "source_priority_conflict"])
    gap_id = _stable_id("conflict_gap", group_id, ",".join(conflict_types))
    return {
        **base,
        "conflict_types": conflict_types,
        "resolution_status": "unresolved_conflict",
        "preferred_value": {},
        "resolution_notes": ["same source priority candidates disagree"],
        "conflict_gap_id": gap_id,
    }


def _conflict_types(rows: list[Mapping[str, Any]]) -> list[str]:
    conflicts: list[str] = []
    if any(str(row.get("metric_match_status") or "") != "mapped" for row in rows):
        conflicts.append("taxonomy_conflict")
    unit_families = {str(row.get("unit_family") or "").strip() for row in rows if str(row.get("unit_family") or "").strip()}
    units = {str(row.get("unit") or "").strip().lower() for row in rows if str(row.get("unit") or "").strip()}
    if len(unit_families) > 1 or (len(units) > 1 and len(unit_families) == 1 and next(iter(unit_families), "") == "unknown"):
        conflicts.append("unit_conflict")
    fiscal_period_ends = {str(row.get("fiscal_period_end") or "").strip() for row in rows if str(row.get("fiscal_period_end") or "").strip()}
    time_bases = {str(row.get("time_basis") or "").strip() for row in rows if str(row.get("time_basis") or "").strip()}
    if len(fiscal_period_ends) > 1 or len(time_bases - {""}) > 1:
        conflicts.append("period_conflict")
    product_keys = {str(row.get("product_key") or "__company_total__") for row in rows}
    if len(product_keys) > 1:
        conflicts.append("segment_conflict")
    return _unique_strings(conflicts)


def _conflict_gap(group: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "gap_id": str(group.get("conflict_gap_id") or _stable_id("conflict_gap", group.get("group_id"))),
        "gap_type": "conflict_gap",
        "ticker": str(group.get("ticker") or ""),
        "metric": str(group.get("canonical_metric_id") or ""),
        "product_or_segment": str(group.get("product_or_segment") or ""),
        "period_key": str(group.get("period_key") or ""),
        "conflict_types": list(group.get("conflict_types") or []),
        "candidate_ids": list(group.get("candidate_ids") or []),
        "reason": "reconciliation could not produce a preferred value under deterministic public-evidence rules",
        "treatment_action": "exclude_from_memo_fact_layer_until_resolved",
    }


def _group_candidates(candidates: list[dict[str, Any]]) -> dict[tuple[str, str, str, str], list[dict[str, Any]]]:
    groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        key = (
            str(candidate.get("ticker") or "").upper(),
            str(candidate.get("canonical_metric_id") or ""),
            str(candidate.get("product_key") or "__company_total__"),
            str(candidate.get("period_key") or "__period_unknown__"),
        )
        groups[key].append(candidate)
    return groups


def _iter_candidate_rows(state: Mapping[str, Any]) -> list[tuple[str, Mapping[str, Any]]]:
    rows: list[tuple[str, Mapping[str, Any]]] = []
    for channel in ("runtime_ledger_rows", "product_evidence_rows", "context_rows", "public_source_context_rows"):
        for row in state.get(channel) or []:
            if isinstance(row, Mapping):
                rows.append((channel, row))
    return rows


def _vintage_index(layer: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    index: dict[str, Mapping[str, Any]] = {}
    for row in layer.get("records") or []:
        if not isinstance(row, Mapping):
            continue
        for key in (_first_text(row, "source_id"), _first_text(row, "evidence_ref")):
            if key:
                index[key] = row
    return index


def _lookup_vintage(index: Mapping[str, Mapping[str, Any]], *, source_id: str, evidence_ref: str) -> Mapping[str, Any]:
    return index.get(evidence_ref) or index.get(source_id) or {}


def _exact_value_authority(row: Mapping[str, Any], *, source_family: str) -> bool:
    if row.get("exact_value_authority") is True:
        return True
    if row.get("context_only") is True:
        return False
    if source_family in {"primary_sec_filing", "sec_companyfacts_api", "sec_financial_statement_data_sets"}:
        return True
    if source_family == "company_authored_unaudited_sec_filing":
        return True
    if source_family == "company_product_evidence_graph":
        status = str(row.get("promotion_status") or row.get("repair_promotion_status") or "").strip()
        return status in {
            "runtime_fact_allowed",
            "parser_verified_fact",
            "monotonic_repair_promoted",
            "operating_metric_repair_promoted",
            "source_specific_repair_promoted",
        }
    return False


def _source_family(row: Mapping[str, Any], *, channel: str) -> str:
    family = _first_text(row, "source_family", "runtime_source_family", "source_tier")
    if family:
        return family
    if channel == "product_evidence_rows":
        return "company_product_evidence_graph"
    if channel == "runtime_ledger_rows":
        return "primary_sec_filing"
    return "unknown"


def _candidate_exclusion_reason(
    *,
    has_value: bool,
    exact_authority: bool,
    source_family: str,
    unit_gate_reason: str = "",
    semantic_gate_reason: str = "",
) -> str:
    if not has_value:
        return "excluded_missing_value"
    if source_family in CONTEXT_ONLY_SOURCE_FAMILIES:
        return "excluded_context_only_source"
    if not exact_authority:
        return "excluded_without_exact_value_authority"
    if unit_gate_reason:
        return unit_gate_reason
    if semantic_gate_reason:
        return semantic_gate_reason
    return "excluded_unknown"


def _unit_family(*, unit: str, metric: Mapping[str, Any]) -> str:
    explicit = str(metric.get("unit_family") or "").strip()
    raw = str(unit or "").strip().lower()
    if raw in {
        "usd",
        "$",
        "dollars",
        "usd_millions",
        "usd millions",
        "usd_billions",
        "usd billions",
        "usd_thousands",
        "usd thousands",
        "currency",
    }:
        return "currency"
    if raw in {"%", "percent", "percentage"}:
        return "percent"
    if raw in {"shares", "share"}:
        return "shares"
    if raw in {"users", "subscribers", "accounts"}:
        return raw
    if raw in {"units", "vehicles", "devices", "systems"}:
        return "units"
    if raw and "per share" in raw:
        return "currency_per_share"
    return explicit or ("unknown" if raw else "")


def _metric_unit_gate_reason(metric: Mapping[str, Any], *, unit_family: str, unit: str) -> str:
    canonical = str(metric.get("canonical_metric_id") or "")
    if not canonical or canonical.startswith("unmapped:"):
        return ""
    actual = str(unit_family or "").strip()
    raw_unit = str(unit or "").strip().lower()
    if canonical in {
        "financial_metric:revenue",
        "financial_metric:gross_profit",
        "financial_metric:cost_of_revenue",
        "financial_metric:operating_income",
        "financial_metric:operating_cash_flow",
        "financial_metric:fcf",
        "financial_metric:capex",
        "financial_metric:debt",
        "financial_metric:cash",
        "financial_metric:inventory",
    } and actual != "currency":
        return "excluded_metric_unit_mismatch"
    if canonical == "financial_metric:gross_margin" and actual != "percent":
        return "excluded_metric_unit_mismatch"
    if canonical == "product_kpi:backlog" and (actual == "percent" or raw_unit in {"%", "percent", "percentage"}):
        return "excluded_metric_unit_mismatch"
    return ""


def _metric_semantic_gate_reason(row: Mapping[str, Any], metric: Mapping[str, Any]) -> str:
    canonical = str(metric.get("canonical_metric_id") or "")
    if canonical != "product_kpi:backlog":
        return ""
    text = " ".join(
        _first_text(row, key)
        for key in (
            "metric_name",
            "row_label",
            "line_item",
            "label",
            "table_title",
            "record_title",
            "source_text",
            "context",
        )
    ).lower()
    if not any(term in text for term in ("remaining performance obligation", "rpo", "backlog", "bookings", "order backlog")):
        return "excluded_metric_semantic_mismatch"
    if any(
        term in text
        for term in (
            "corporate debt securities",
            "corporate notes",
            "corporate and other assets",
            "corporate expense",
            "corporate expenses",
            "other corporate",
            "corporate",
            "long-term debt",
            "long term debt",
            "debt securities",
            "unamortized discount",
            "issuance costs",
            "bonds",
        )
    ):
        return "excluded_metric_semantic_mismatch"
    return ""


def _period_key(
    *,
    fiscal_year: str,
    fiscal_period: str,
    fiscal_period_end: str,
    market_as_of: str,
    macro_vintage: str,
    period_role: str = "",
) -> str:
    role = normalize_metric_alias(period_role)
    if fiscal_year and fiscal_period:
        return f"fiscal:{fiscal_year}:{fiscal_period}:{role}" if role else f"fiscal:{fiscal_year}:{fiscal_period}"
    if fiscal_period_end:
        return f"period_end:{fiscal_period_end}:{role}" if role else f"period_end:{fiscal_period_end}"
    if market_as_of:
        return f"market_as_of:{market_as_of}"
    if macro_vintage:
        return f"macro_vintage:{macro_vintage}"
    return "__period_unknown__"


def _product_or_segment_from_row(row: Mapping[str, Any], *, metric: Mapping[str, Any]) -> str:
    explicit = _first_text(row, "product_or_segment", "product", "segment", "business_line")
    if explicit:
        return explicit
    canonical = str(metric.get("canonical_metric_id") or "")
    if canonical not in {
        "financial_metric:revenue",
        "financial_metric:gross_profit",
        "financial_metric:gross_margin",
        "financial_metric:cost_of_revenue",
        "product_kpi:product_revenue",
    }:
        return ""
    label = _first_text(row, "metric_name", "line_item", "label")
    normalized = normalize_metric_alias(label)
    if not normalized:
        return ""
    if canonical == "product_kpi:product_revenue":
        cleaned = _product_label_from_metric_label(label)
        if cleaned:
            return cleaned
    company_total_labels = {
        "revenue",
        "revenues",
        "net_sales",
        "total_revenue",
        "total_revenues",
        "total_net_sales",
        "sales",
        "gross_margin",
        "gross_margin_percentage",
        "total_gross_margin",
        "total_gross_margin_percentage",
        "gross_profit",
        "cost_of_revenue",
        "cost_of_sales",
        "total_cost_of_sales",
    }
    if normalized in company_total_labels:
        return ""
    return label


def _product_label_from_metric_label(label: str) -> str:
    text = str(label or "").strip()
    cleaned = re.sub(r"^(?:net\s+revenue|revenue|product\s+revenue|net\s+sales)\s+[-:–—]?\s*", "", text, flags=re.I).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    if not cleaned or normalize_metric_alias(cleaned) in {"total", "total_revenue", "total_net_revenue", "total_net_sales"}:
        return ""
    return cleaned


def _product_key(value: str) -> str:
    normalized = normalize_metric_alias(value)
    return normalized or "__company_total__"


def _display_product(rows: list[Mapping[str, Any]]) -> str:
    for row in rows:
        value = str(row.get("product_or_segment") or "").strip()
        if value:
            return value
    return ""


def _preferred_value(row: Mapping[str, Any], *, resolution_rule: str, confidence: str) -> dict[str, Any]:
    return {
        "candidate_id": str(row.get("candidate_id") or ""),
        "value": str(row.get("value") or ""),
        "numeric_value": str(row.get("numeric_value") or ""),
        "unit": str(row.get("unit") or ""),
        "unit_family": str(row.get("unit_family") or ""),
        "source_id": str(row.get("source_id") or ""),
        "evidence_ref": str(row.get("evidence_ref") or ""),
        "source_family": str(row.get("source_family") or ""),
        "resolution_rule": resolution_rule,
        "confidence": confidence,
    }


def _resolution_notes(conflict_types: list[str]) -> list[str]:
    notes = []
    if "unit_conflict" in conflict_types:
        notes.append("unit conflict requires explicit conversion policy")
    if "period_conflict" in conflict_types:
        notes.append("period conflict requires period alignment or amended-source rule")
    if "taxonomy_conflict" in conflict_types:
        notes.append("taxonomy conflict requires D7 ontology repair")
    if "segment_conflict" in conflict_types:
        notes.append("segment conflict requires product/segment binding repair")
    return notes


def _preferred_amended_candidate(rows: list[Mapping[str, Any]]) -> Mapping[str, Any]:
    amended = [row for row in rows if row.get("amendment_flag")]
    if not amended:
        return {}
    return sorted(amended, key=lambda row: (-int(row.get("source_priority_rank") or 0), str(row.get("accepted_date") or "")))[0]


def _amendment_flag(row: Mapping[str, Any]) -> bool:
    if row.get("amendment_flag") is True or row.get("amended") is True:
        return True
    form = _first_text(row, "form_type", "form")
    document_id = _first_text(row, "document_id", "accession_number", "accession")
    return "/A" in form.upper() or "-A" in form.upper() or document_id.upper().endswith("/A")


def _all_equal(values: list[Decimal]) -> bool:
    if not values:
        return True
    first = values[0]
    return all(value == first for value in values)


def _rounding_equivalent(values: list[Decimal]) -> bool:
    if len(values) < 2:
        return False
    low = min(values)
    high = max(values)
    spread = abs(high - low)
    basis = max(abs(high), abs(low), Decimal("1"))
    return spread <= basis * Decimal("0.005")


def _decimal_value(value: Any) -> Decimal | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    text = text.replace(",", "").replace("$", "").replace("%", "")
    negative = text.startswith("(") and text.endswith(")")
    text = text.strip("()")
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        parsed = Decimal(match.group(0))
    except InvalidOperation:
        return None
    return -parsed if negative else parsed


def _first_text(row: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        if isinstance(value, (list, tuple, set)):
            value = next((item for item in value if str(item or "").strip()), "")
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item or "").strip() for item in value if str(item or "").strip()]
    return [str(value).strip()]


def _unique_strings(values: list[Any]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        for item in _string_list(value):
            if item and item not in seen:
                seen.add(item)
                out.append(item)
    return out


def _stable_id(prefix: str, *values: Any) -> str:
    raw = "|".join(str(value or "") for value in values)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}:{digest}"


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(child) for key, child in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    if isinstance(value, Decimal):
        return str(value)
    return value
