from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]

SCHEMA_VERSION = "finsight_industry_operating_metric_slot_row_v0_1"
REJECTION_SCHEMA_VERSION = "finsight_industry_operating_metric_slot_rejection_v0_1"
SUMMARY_SCHEMA_VERSION = "finsight_industry_operating_metric_slot_summary_v0_1"

DEFAULT_VERIFIER_ROWS = REPO_ROOT / "data" / "manifests" / "product_kpi_source_specific_verifier_v0_1.jsonl"
DEFAULT_DOCKET = REPO_ROOT / "data" / "manifests" / "company_gap_docket_v0_1.jsonl"
DEFAULT_OUTPUT_ROWS = REPO_ROOT / "data" / "manifests" / "industry_operating_metric_slot_rows_v0_1.jsonl"
DEFAULT_OUTPUT_REJECTIONS = REPO_ROOT / "data" / "manifests" / "industry_operating_metric_slot_rejections_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY = REPO_ROOT / "data" / "manifests" / "industry_operating_metric_slot_summary_v0_1.json"
DEFAULT_OUTPUT_REPORT = (
    REPO_ROOT / "docs" / "internal" / "vnext_20260610" / "vertical_lanes" / "industry_operating_metric_slot.zh-CN.md"
)

BUSINESS_SEGMENT_PROMOTABLE_CLASSES = {"business_segment_metric"}
OPERATING_PROMOTABLE_CLASS = "operating_metric_defer_step2"

GEOGRAPHIC_RE = re.compile(
    r"^(north america|latin america|emea|apac|asia(?:-pacific)?|europe|africa|"
    r"americas?|international|domestic|united states|u\.s\.|us|canada|mexico|"
    r"china|japan|korea|india|brazil|germany|u\.k\.|uk|ireland|luxembourg|western europe|other americas|"
    r"europe,\s*middle east.*africa|asia pacific|other countries|rest of world|"
    r"key emerging markets)(?:\s*\([^)]*\))?$",
    re.IGNORECASE,
)
TOTAL_OR_NON_OPERATING_RE = re.compile(
    r"^(total\b.*|total revenue|total revenues|revenue|revenues|net sales|sales|"
    r"operating income|operating profit|gross profit|income before|other|corporate|"
    r"eliminations?|total segment revenues?)$",
    re.IGNORECASE,
)
NON_SEGMENT_REVENUE_ROW_RE = re.compile(
    r"gains?\)|losses?|retained ownership interests?|products? (and services )?delivered "
    r"(at a point in time|over time)|revenue recognized|contract liabilit|deferred revenue|currency translation|"
    r"^other\b|corporate|all other|unguaranteed residual|net earnings|earnings per share|diluted|"
    r"payment transactions per active account|service charges?|deposit accounts?|"
    r"\b(net\s+)?(inflows?|outflows?|flows?)\b|available for sale securities|held to maturity securities|"
    r"proceeds from sales|interest revenue",
    re.IGNORECASE,
)
BACKLOG_ACTIVITY_ROW_RE = re.compile(
    r"balance at (beginning|end) of period|currency translation|revenue recognized|new revenue deferrals?|"
    r"deferred revenue|contract liabilit",
    re.IGNORECASE,
)
BACKLOG_RE = re.compile(
    r"backlog|bookings?|orders?|remaining performance obligations?|rpo|contract(ed)? backlog|contract value",
    re.IGNORECASE,
)
UNIT_SALES_RE = re.compile(r"sales in units|unit sales|units sold|vehicles delivered|engines?|turbines?", re.IGNORECASE)
SHIPMENT_RE = re.compile(r"shipments?|shipped|tonnes?|tons?|barrels|production volume", re.IGNORECASE)
CAPACITY_RE = re.compile(
    r"capacity|utili[sz]ation|megawatts?|mw\b|gigawatts?|gw\b|mwh|gwh|throughput|wafer starts|"
    r"production volume|produced|gas delivered|dekatherms?|barrels per day|boe|tonnes?",
    re.IGNORECASE,
)
SUBSCRIBER_RE = re.compile(r"subscribers?|users?|members?|accounts?", re.IGNORECASE)
ARPU_RE = re.compile(r"\barpu\b|average revenue per user|average revenue per account", re.IGNORECASE)
ARR_RPO_RE = re.compile(r"\barr\b|annual recurring revenue|remaining performance obligations?|\brpo\b", re.IGNORECASE)
SAME_STORE_RE = re.compile(r"same[- ]store|comparable store|comparable sales|comps?\b", re.IGNORECASE)
IDENTICAL_OR_COMPARABLE_SALES_RE = re.compile(
    r"identical sales|comparable sales|same[- ]store sales|same store sales|same[- ]store sales growth",
    re.IGNORECASE,
)
SAME_STORE_REVENUE_COMPONENT_RE = re.compile(
    r"same[- ]store residential (?:rental )?revenue by component|increase in same[- ]store residential",
    re.IGNORECASE,
)
TRAVEL_UNIT_RE = re.compile(r"room nights?|rental car days?|airline tickets?", re.IGNORECASE)
PAYMENT_ACTIVITY_RE = re.compile(
    r"payment transactions per active account|total payment volume|\btpv\b|payment volume|purchase volume|"
    r"processed transactions?|processed volume",
    re.IGNORECASE,
)
PAYMENT_MIX_PERCENT_RE = re.compile(
    r"percent of (?:cross-border )?tpv|percent of tpv generated outside|cross-border tpv",
    re.IGNORECASE,
)
MARKETPLACE_ACTIVITY_RE = re.compile(
    r"marketplace\s+gov|gross order value|\bgov\b|gross merchandise value|\bgmv\b",
    re.IGNORECASE,
)
SEGMENT_REVENUE_GROWTH_RE = re.compile(
    r"total revenue growth|revenue growth|net sales growth|sales growth",
    re.IGNORECASE,
)
SEGMENT_REVENUE_GROWTH_EXCLUSION_RE = re.compile(
    r"provision for income|income taxes?|tax rate|non-gaap financial measures?|currency|fx impact|"
    r"acquisitions?|divestitures?|without acquisitions|constant currency",
    re.IGNORECASE,
)
REAL_ESTATE_PER_OCCUPIED_AREA_RE = re.compile(
    r"average annual total revenues? per occupied square foot|revenues? per occupied square foot",
    re.IGNORECASE,
)
PATIENT_RE = re.compile(r"patient volume|admissions?|patient days|procedures?|visits?", re.IGNORECASE)
FINANCIAL_OPERATING_RE = re.compile(
    r"assets under management|\baum\b|\baua\b|deposits?|loan balances?|loans?|net interest income|"
    r"client assets|average assets|trading volume",
    re.IGNORECASE,
)
PERCENT_RE = re.compile(r"%|percent|percentage|basis points?|bps", re.IGNORECASE)
FORBIDDEN_OPERATING_CONTEXT_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"cash flows? from (?:investing|financing) activities|"
            r"sales of (?:fixed maturity|available-for-sale|held-to-maturity) securities|"
            r"proceeds from sales of securities|principal payments received",
            re.IGNORECASE,
        ),
        "cash_flow_table_not_industry_operating_slot",
    ),
    (
        re.compile(
            r"\bexpenses?\b\s*\[TABLE_START|operating expenses|compensation and benefits|"
            r"professional fees and outside services|depreciation and amortization|"
            r"amortization of purchased intangibles|allocated overhead|inventory write-?off",
            re.IGNORECASE,
        ),
        "expense_table_not_industry_operating_slot",
    ),
    (
        re.compile(
            r"provision for income taxes|income taxes?|effective tax rate|tax rate|"
            r"non-gaap financial measures?",
            re.IGNORECASE,
        ),
        "tax_or_non_gaap_bridge_not_industry_operating_slot",
    ),
    (
        re.compile(
            r"constant currency|foreign currency|fx impact|currency exchange|currency translation|"
            r"acquisitions?|divestitures?|without acquisitions|organic basis",
            re.IGNORECASE,
        ),
        "currency_or_acquisition_bridge_not_operating_slot",
    ),
    (
        re.compile(r"production payment obligation", re.IGNORECASE),
        "production_payment_obligation_not_production_volume",
    ),
)

LANE_REQUIRED_SLOT_HINTS: dict[str, tuple[str, ...]] = {
    "V3": ("arr_or_rpo", "subscriber_count", "arpu", "cloud_capacity_or_usage"),
    "V4": ("patient_volume", "procedure_volume", "regulated_product_volume"),
    "V6": ("aum", "aua", "deposits", "loan_balance", "client_assets", "trading_volume"),
    "V7": ("capacity", "utilization", "mw_or_generation", "backlog_or_orders", "production_volume"),
    "V8": ("same_store_sales_growth", "unit_sales_or_deliveries", "backlog_or_orders"),
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build industry operating metric exact-slot rows from classified candidates.")
    parser.add_argument("--verifier-rows", type=Path, default=DEFAULT_VERIFIER_ROWS)
    parser.add_argument("--docket", type=Path, default=DEFAULT_DOCKET)
    parser.add_argument("--output-rows", type=Path, default=DEFAULT_OUTPUT_ROWS)
    parser.add_argument("--output-rejections", type=Path, default=DEFAULT_OUTPUT_REJECTIONS)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--output-report", type=Path, default=DEFAULT_OUTPUT_REPORT)
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at = _utc_now()
    docket_context = _docket_context_by_ticker(_load_jsonl(args.docket))
    rows, rejections = build_industry_operating_metric_slot_rows(
        verifier_rows=_load_jsonl(args.verifier_rows),
        docket_context=docket_context,
        generated_at=generated_at,
    )
    summary = build_summary(
        runtime_rows=rows,
        rejection_rows=rejections,
        generated_at=generated_at,
        output_rows=args.output_rows,
        output_rejections=args.output_rejections,
        output_report=args.output_report,
    )
    _write_jsonl(args.output_rows, rows)
    _write_jsonl(args.output_rejections, rejections)
    _write_json(args.output_summary, summary)
    args.output_report.parent.mkdir(parents=True, exist_ok=True)
    args.output_report.write_text(render_report(summary), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if args.strict and (summary["unclassified_rejection_count"] or summary["runtime_row_count"] <= 0):
        return 1
    return 0


def build_industry_operating_metric_slot_rows(
    *,
    verifier_rows: Iterable[Mapping[str, Any]],
    docket_context: Mapping[str, Mapping[str, Any]],
    generated_at: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    runtime_rows: list[dict[str, Any]] = []
    rejection_rows: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    promoted_candidates: list[dict[str, Any]] = []
    for verifier_row in verifier_rows:
        row = dict(verifier_row)
        context = dict(docket_context.get(_ticker(row), {}))
        verdict = classify_industry_operating_slot(row, context)
        if verdict["decision"] == "promote":
            runtime_row = _runtime_row(row, context=context, verdict=verdict, generated_at=generated_at)
            key = _claim_key(runtime_row)
            if key in seen:
                rejection_rows.append(_rejection_row(row, context, verdict, "duplicate_industry_operating_claim", generated_at))
                continue
            seen.add(key)
            promoted_candidates.append(runtime_row)
        elif verdict["decision"] != "ignore":
            rejection_rows.append(_rejection_row(row, context, verdict, verdict["reason"], generated_at))
    conflict_resolution = _resolve_conflicting_claims(promoted_candidates)
    accepted_conflict_refs = {
        str(row.get("evidence_ref") or "") for row in conflict_resolution["resolved_rows"]
    }
    conflicting_groups = conflict_resolution["unresolved_conflicts"]
    for runtime_row in promoted_candidates:
        conflict_key = _claim_key_without_value(runtime_row)
        if conflict_key in conflicting_groups:
            rejection_rows.append(
                _runtime_conflict_rejection_row(
                    runtime_row,
                    conflict_values=conflicting_groups[conflict_key],
                    generated_at=generated_at,
                )
            )
            continue
        if conflict_key in conflict_resolution["resolved_conflicts"]:
            if str(runtime_row.get("evidence_ref") or "") not in accepted_conflict_refs:
                rejection_rows.append(
                    _runtime_conflict_resolution_rejection_row(
                        runtime_row,
                        chosen_refs=conflict_resolution["resolved_conflicts"][conflict_key]["chosen_refs"],
                        conflict_values=conflict_resolution["resolved_conflicts"][conflict_key]["conflict_values"],
                        generated_at=generated_at,
                    )
                )
                continue
            runtime_row = dict(runtime_row)
            runtime_row["conflict_resolution_status"] = "aggregate_total_selected_from_column_group_conflict"
            runtime_row["conflict_values"] = conflict_resolution["resolved_conflicts"][conflict_key]["conflict_values"]
            runtime_row["claim_boundary"] = (
                f"{runtime_row.get('claim_boundary') or ''} Conflict resolver kept this row because its value matches "
                "the sum of sibling column-group values; unresolved or non-aggregate siblings remain rejected."
            ).strip()
            runtime_row["runtime_use_boundary"] = runtime_row["claim_boundary"]
            runtime_row["authority_boundary"] = runtime_row["claim_boundary"]
        runtime_rows.append(runtime_row)
    return sorted(runtime_rows, key=lambda r: (r["ticker"], r["slot_id"], r["period"], str(r["value"]))), rejection_rows


def classify_industry_operating_slot(row: Mapping[str, Any], context: Mapping[str, Any]) -> dict[str, Any]:
    base = {
        "decision": "reject",
        "slot_id": "",
        "slot_metric_family": "",
        "reason": "unclassified",
        "claim_scope": "",
        "claim_boundary": "Do not promote without a slot-specific verifier decision.",
    }
    cls = str(row.get("verifier_class") or "")
    metric_family = str(row.get("metric_family") or "")
    row_label = str(row.get("row_label") or "").strip()
    product = str(row.get("product_or_segment") or "").strip()
    column = str(row.get("column_label") or "").strip()
    citation = str(row.get("citation_sample") or "")
    text = " ".join([row_label, product, column, citation])
    unit = str(row.get("unit") or "")
    value = _float_value(row.get("value"))

    mislabeled_operating = _mislabeled_product_revenue_operating_slot(row, text)
    if mislabeled_operating:
        return {
            **_slot(
                base,
                str(mislabeled_operating["slot_id"]),
                str(mislabeled_operating["claim_scope"]),
            ),
            "reason": str(mislabeled_operating["reason"]),
            "normalized_value": mislabeled_operating.get("value"),
            "normalized_unit": mislabeled_operating.get("unit"),
            "normalized_unit_category": mislabeled_operating.get("unit_category"),
            "normalized_metric_name": mislabeled_operating.get("metric_name"),
            "claim_boundary": str(mislabeled_operating["claim_boundary"]),
        }

    if cls not in BUSINESS_SEGMENT_PROMOTABLE_CLASSES and cls != OPERATING_PROMOTABLE_CLASS:
        return {**base, "decision": "ignore", "reason": "not_step2_industry_operating_candidate"}
    if GEOGRAPHIC_RE.match(row_label) or GEOGRAPHIC_RE.match(product):
        return {**base, "reason": "region_only_not_industry_operating_slot"}
    forbidden_reason = _forbidden_operating_metric_context(row, text)
    if forbidden_reason:
        return {**base, "reason": forbidden_reason}

    if cls in BUSINESS_SEGMENT_PROMOTABLE_CLASSES:
        if value <= 0:
            return {**base, "reason": "non_positive_value"}
        if _looks_like_mislabeled_operating_metric(row):
            return {**base, "reason": "mislabeled_operating_metric_without_exact_period_column_binding"}
        financial_slot = _financial_operating_slot(row, context)
        if financial_slot:
            return _slot(base, financial_slot, f"company_disclosed_{financial_slot}")
        if (
            metric_family == "product_revenue"
            and unit == "USD"
            and not TOTAL_OR_NON_OPERATING_RE.match(row_label)
            and (
                not NON_SEGMENT_REVENUE_ROW_RE.search(row_label)
                or _is_customer_type_revenue_disaggregation(row_label, text)
            )
        ):
            if not _column_matches_period(column, row.get("period")):
                return {**base, "reason": "business_segment_metric_without_exact_period_column_binding"}
            return {
                **base,
                "decision": "promote",
                "slot_id": "business_segment_revenue",
                "slot_metric_family": "business_segment_revenue",
                "reason": "company_disclosed_business_segment_revenue_verified",
                "claim_scope": "company_disclosed_business_segment_revenue",
                "claim_boundary": (
                    "May support company-disclosed business or segment revenue for this row label only; "
                    "not product-family revenue, unit volume, market share, ASP, sell-through, or channel inventory."
                ),
            }
        return {**base, "reason": "business_segment_metric_not_currency_revenue_or_generic_row"}

    if cls == OPERATING_PROMOTABLE_CLASS:
        if metric_family == "same_store_sales":
            if SAME_STORE_RE.search(text) and (PERCENT_RE.search(unit) or PERCENT_RE.search(str(row.get("raw_value_text") or ""))):
                return _slot(base, "same_store_sales_growth", "company_disclosed_same_store_sales_growth")
            return {**base, "reason": "same_store_metric_without_comparable_store_context"}
        if value <= 0:
            return {**base, "reason": "non_positive_value"}
        if metric_family == "backlog_or_orders":
            direct = " ".join([row_label, product, column])
            if MARKETPLACE_ACTIVITY_RE.search(direct):
                return _slot(base, "marketplace_gross_order_value", "company_disclosed_marketplace_gross_order_value")
            if _has_backlog_or_order_table_anchor(text, row_label, column):
                return _slot(base, "backlog_or_orders", "company_disclosed_backlog_or_order_metric")
            return {**base, "reason": "backlog_metric_without_backlog_or_order_context"}
        if metric_family == "unit_sales_or_deliveries":
            if _has_unit_sales_context(text, row_label, column, unit):
                return _slot(base, "unit_sales_or_deliveries", "company_disclosed_unit_sales_or_deliveries")
            return {**base, "reason": "unit_sales_metric_without_unit_delivery_context"}
        if metric_family == "shipments":
            if SHIPMENT_RE.search(text) or UNIT_SALES_RE.search(text):
                return _slot(base, "shipments", "company_disclosed_shipment_or_delivery_metric")
            return {**base, "reason": "shipment_metric_without_shipment_context"}
        if metric_family == "production_or_throughput":
            if CAPACITY_RE.search(text) and "production solutions" not in row_label.lower():
                slot = "capacity_utilization_or_production_volume"
                if re.search(r"megawatts?|mw\b|gigawatts?|gw\b", text, re.IGNORECASE):
                    slot = "mw_or_generation_capacity"
                return _slot(base, slot, "company_disclosed_capacity_utilization_or_production_metric")
            return {**base, "reason": "production_metric_without_capacity_or_throughput_context"}
        if metric_family == "subscribers_or_arpu":
            if ARR_RPO_RE.search(text):
                return _slot(base, "arr_or_rpo", "company_disclosed_arr_or_rpo")
            if SUBSCRIBER_RE.search(text) and unit.lower() in {"subscribers", "users", "accounts", "members", "units"}:
                return _slot(base, "subscriber_count", "company_disclosed_subscriber_or_user_count")
            if ARPU_RE.search(text):
                if unit == "USD" and value <= 10000:
                    return _slot(base, "arpu", "company_disclosed_arpu")
                return {**base, "reason": "arpu_unit_or_scale_ambiguous"}
            return {**base, "reason": "subscriber_metric_without_subscriber_arr_arpu_context"}
        if PATIENT_RE.search(text):
            return _slot(base, "patient_volume", "company_disclosed_patient_or_procedure_volume")
        if FINANCIAL_OPERATING_RE.search(text):
            return _slot(base, "financial_services_operating_metric", "company_disclosed_financial_services_operating_metric")
        return {**base, "reason": f"unsupported_operating_metric_family_{metric_family or 'missing'}"}

    return base


def build_summary(
    *,
    runtime_rows: list[dict[str, Any]],
    rejection_rows: list[dict[str, Any]],
    generated_at: str,
    output_rows: Path,
    output_rejections: Path,
    output_report: Path,
) -> dict[str, Any]:
    unclassified = [row for row in rejection_rows if row.get("rejection_reason") == "unclassified"]
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "pass" if runtime_rows and not unclassified else "gap",
        "runtime_row_count": len(runtime_rows),
        "runtime_ticker_count": len({row["ticker"] for row in runtime_rows}),
        "slot_counts": dict(sorted(Counter(row["slot_id"] for row in runtime_rows).items())),
        "lane_counts": dict(sorted(Counter(row.get("primary_lane_id") or "" for row in runtime_rows).items())),
        "source_verifier_class_counts": dict(sorted(Counter(row.get("source_verifier_class") or "" for row in runtime_rows).items())),
        "rejection_count": len(rejection_rows),
        "rejection_reason_counts": dict(sorted(Counter(row.get("rejection_reason") or "" for row in rejection_rows).items())),
        "unclassified_rejection_count": len(unclassified),
        "outputs": {
            "rows": str(output_rows),
            "rejections": str(output_rejections),
            "report": str(output_report),
        },
        "boundary": (
            "Industry operating metric exact slots are separate from Product-KPI exact. They may support "
            "business mix, capacity, backlog, deliveries, subscribers, ARPU/ARR/RPO, same-store growth, or "
            "financial-services operating metrics only when company-disclosed value/unit/period/citation are present."
        ),
    }


def render_report(summary: Mapping[str, Any]) -> str:
    lines = [
        "# Industry Operating Metric Slot",
        "",
        f"- schema_version: `{summary.get('schema_version')}`",
        f"- generated_at: `{summary.get('generated_at')}`",
        f"- status: `{summary.get('status')}`",
        f"- runtime_row_count: `{summary.get('runtime_row_count')}`",
        f"- runtime_ticker_count: `{summary.get('runtime_ticker_count')}`",
        f"- rejection_count: `{summary.get('rejection_count')}`",
        f"- unclassified_rejection_count: `{summary.get('unclassified_rejection_count')}`",
        "",
        "## Slot Counts",
        "",
        "| slot | rows |",
        "| --- | ---: |",
    ]
    for slot, count in sorted((summary.get("slot_counts") or {}).items()):
        lines.append(f"| `{slot}` | {count} |")
    lines.extend(["", "## Rejection Reasons", "", "| reason | rows |", "| --- | ---: |"])
    for reason, count in sorted((summary.get("rejection_reason_counts") or {}).items()):
        lines.append(f"| `{reason}` | {count} |")
    lines.extend(["", "## Boundary", "", str(summary.get("boundary") or ""), ""])
    return "\n".join(lines)


def _slot(base: Mapping[str, Any], slot_id: str, claim_scope: str) -> dict[str, Any]:
    return {
        **base,
        "decision": "promote",
        "slot_id": slot_id,
        "slot_metric_family": slot_id,
        "reason": f"{slot_id}_context_verified",
        "claim_scope": claim_scope,
        "claim_boundary": (
            f"May support {claim_scope} for the disclosed value/unit/period/entity only; "
            "not product revenue, market share, ASP, sell-through, or commercial tracker estimate."
        ),
    }


def _forbidden_operating_metric_context(row: Mapping[str, Any], text: str) -> str:
    direct = " ".join(
        str(row.get(key) or "")
        for key in ("product_or_segment", "row_label", "column_label", "metric_name", "citation_sample")
    )
    combined = " ".join([direct, text])
    for pattern, reason in FORBIDDEN_OPERATING_CONTEXT_PATTERNS:
        if pattern.search(combined):
            return reason
    return ""


def _has_backlog_or_order_table_anchor(text: str, row_label: str, column_label: str) -> bool:
    direct = " ".join([row_label, column_label])
    if BACKLOG_ACTIVITY_ROW_RE.search(direct):
        return False
    if re.search(r"percent increase|percent decrease|at actual currency|at constant currency", text, re.IGNORECASE):
        return False
    if re.search(r"\bsegment orders?\b", direct, re.IGNORECASE) and re.search(
        r"\bsegment results?\b|\border(?:s| value)?\b",
        text,
        re.IGNORECASE,
    ):
        return True
    if re.search(r"order backlog|backlog|new bookings?|remaining performance obligations?|\brpo\b", direct, re.IGNORECASE):
        return True
    if re.search(r"(new bookings?|remaining performance obligations?|contract(ed)? backlog)[^\[]*\[TABLE_START", text, re.IGNORECASE):
        return True
    if re.search(r"\[TABLE_START[^\]]*\][^\n]{0,220}(new bookings?|remaining performance obligations?|contract(ed)? backlog)", text, re.IGNORECASE):
        return True
    return False


def _is_customer_type_revenue_disaggregation(row_label: str, text: str) -> bool:
    return bool(
        re.search(r"\b(?:revenues?|evenues?) disaggregated by major customer type\b", text, re.IGNORECASE)
        and re.search(r"\bsales?\b", row_label, re.IGNORECASE)
        and not re.match(r"^other$", row_label.strip(), re.IGNORECASE)
    )


def _mislabeled_product_revenue_operating_slot(row: Mapping[str, Any], text: str) -> dict[str, Any]:
    if str(row.get("metric_family") or "") != "product_revenue":
        return {}
    same_store = _mislabeled_same_store_operating_slot(row, text)
    if same_store:
        return same_store
    travel_units = _mislabeled_travel_unit_operating_slot(row, text)
    if travel_units:
        return travel_units
    real_estate_per_area = _mislabeled_real_estate_per_area_slot(row, text)
    if real_estate_per_area:
        return real_estate_per_area
    payment_activity = _mislabeled_payment_activity_slot(row, text)
    if payment_activity:
        return payment_activity
    segment_revenue_growth = _mislabeled_segment_revenue_growth_slot(row, text)
    if segment_revenue_growth:
        return segment_revenue_growth
    cls = str(row.get("verifier_class") or "")
    if cls not in {"business_segment_mixed_table_needs_column_group", "sentence_relation_insufficient"}:
        return {}
    direct = " ".join(str(row.get(key) or "") for key in ("product_or_segment", "row_label", "column_label"))
    if not re.search(r"\bretail units sold\b|\bunits sold\b|\bvehicles sold\b", direct, re.IGNORECASE):
        return {}
    raw_value = _float_from_currency_or_numeric_text(row.get("raw_value_text"))
    if raw_value <= 0:
        return {}
    return {
        "slot_id": "unit_sales_or_deliveries",
        "claim_scope": "company_disclosed_unit_sales_or_deliveries",
        "reason": "mislabeled_product_revenue_unit_sales_context_verified",
        "metric_name": "retail units sold",
        "value": raw_value,
        "unit": "units",
        "unit_category": "units",
        "claim_boundary": (
            "May support company-disclosed retail units sold for this value/period/entity only; "
            "source parser mislabeled the row as USD product revenue, so do not use it as revenue, ASP, "
            "sell-through, market share, or channel inventory."
        ),
    }


def _mislabeled_payment_activity_slot(row: Mapping[str, Any], text: str) -> dict[str, Any]:
    cls = str(row.get("verifier_class") or "")
    direct = " ".join(str(row.get(key) or "") for key in ("product_or_segment", "row_label", "column_label"))
    if not (PAYMENT_ACTIVITY_RE.search(direct) or PAYMENT_ACTIVITY_RE.search(text)):
        return {}
    if GEOGRAPHIC_RE.match(str(row.get("row_label") or "")) or GEOGRAPHIC_RE.match(str(row.get("product_or_segment") or "")):
        return {}
    column = str(row.get("column_label") or "")
    if not _column_matches_period(column, row.get("period")):
        return {}
    if PAYMENT_MIX_PERCENT_RE.search(direct) and _row_is_percent_like(row):
        value = _float_value(row.get("value"))
        if value <= 0:
            return {}
        return {
            "slot_id": "tpv_mix_percent",
            "claim_scope": "company_disclosed_tpv_mix_percent",
            "reason": "mislabeled_product_revenue_tpv_mix_percent_context_verified",
            "metric_name": "TPV mix percent",
            "value": value,
            "unit": "percent_of_tpv",
            "unit_category": "percent",
            "claim_boundary": (
                "May support company-disclosed TPV mix percentage for this value/period only; source parser "
                "mislabeled the row as product revenue, so do not use it as revenue, absolute TPV, ASP, market "
                "share, sell-through, backlog, or customer order value."
            ),
        }
    if cls not in {"business_segment_metric", "business_segment_mixed_table_needs_column_group"}:
        return {}
    raw_value = _float_from_currency_or_numeric_text(row.get("raw_value_text"))
    if raw_value <= 0:
        return {}
    direct_lower = direct.lower()
    if "payment transactions per active account" in direct_lower:
        return {
            "slot_id": "payment_transactions_per_active_account",
            "claim_scope": "company_disclosed_payment_transactions_per_active_account",
            "reason": "mislabeled_product_revenue_payment_transactions_per_active_account_context_verified",
            "metric_name": "payment transactions per active account",
            "value": raw_value,
            "unit": "transactions_per_active_account",
            "unit_category": "activity_ratio",
            "claim_boundary": (
                "May support company-disclosed payment transactions per active account for this value/period only; "
                "source parser mislabeled the row as USD product revenue, so do not use it as revenue, TPV, ASP, "
                "market share, sell-through, backlog, or customer order value."
            ),
        }
    if re.search(r"total payment volume|\btpv\b|payment volume|purchase volume|processed volume", direct, re.IGNORECASE):
        return {
            "slot_id": "total_payment_volume",
            "claim_scope": "company_disclosed_total_payment_volume",
            "reason": "mislabeled_product_revenue_total_payment_volume_context_verified",
            "metric_name": "total payment volume",
            "value": raw_value,
            "unit": str(row.get("unit") or "USD"),
            "unit_category": "payment_volume",
            "claim_boundary": (
                "May support company-disclosed payment volume for this value/period only; source parser may have "
                "mislabeled the row as product revenue, so do not use it as revenue, take rate, ASP, market share, "
                "sell-through, backlog, or customer order value."
            ),
        }
    if re.search(r"processed transactions?", direct, re.IGNORECASE):
        return {
            "slot_id": "processed_transactions",
            "claim_scope": "company_disclosed_processed_transactions",
            "reason": "mislabeled_product_revenue_processed_transactions_context_verified",
            "metric_name": "processed transactions",
            "value": raw_value,
            "unit": "transactions",
            "unit_category": "activity_count",
            "claim_boundary": (
                "May support company-disclosed processed transaction count for this value/period only; source "
                "parser mislabeled the row as product revenue, so do not use it as revenue, TPV, ASP, market share, "
                "sell-through, backlog, or customer order value."
            ),
        }
    return {}


def _mislabeled_segment_revenue_growth_slot(row: Mapping[str, Any], text: str) -> dict[str, Any]:
    if str(row.get("verifier_class") or "") not in {"percentage_or_change", "sentence_relation_insufficient"}:
        return {}
    if not _row_is_percent_like(row):
        return {}
    product_or_segment = str(row.get("product_or_segment") or "")
    row_label = str(row.get("row_label") or "")
    column = str(row.get("column_label") or "")
    direct = " ".join([product_or_segment, row_label, column])
    if GEOGRAPHIC_RE.match(product_or_segment) or GEOGRAPHIC_RE.match(row_label):
        return {}
    if not (SEGMENT_REVENUE_GROWTH_RE.search(direct) or SEGMENT_REVENUE_GROWTH_RE.search(text)):
        return {}
    if SEGMENT_REVENUE_GROWTH_EXCLUSION_RE.search(direct) or SEGMENT_REVENUE_GROWTH_EXCLUSION_RE.search(text):
        return {}
    value = _float_value(row.get("value"))
    return {
        "slot_id": "segment_revenue_growth",
        "claim_scope": "company_disclosed_segment_revenue_growth",
        "reason": "mislabeled_product_revenue_segment_revenue_growth_context_verified",
        "metric_name": "segment revenue growth",
        "value": value,
        "unit": "percent_change",
        "unit_category": "percent",
        "claim_boundary": (
            "May support company-disclosed segment or product-line revenue growth percentage for this row/period only; "
            "source parser mislabeled the row as product revenue, so do not use it as revenue level, ASP, market share, "
            "sell-through, backlog, or customer order value."
        ),
    }


def _mislabeled_same_store_operating_slot(row: Mapping[str, Any], text: str) -> dict[str, Any]:
    cls = str(row.get("verifier_class") or "")
    if cls != "percentage_or_change":
        return {}
    if not _row_is_percent_like(row):
        return {}
    direct = " ".join(str(row.get(key) or "") for key in ("product_or_segment", "row_label", "column_label"))
    if GEOGRAPHIC_RE.match(str(row.get("row_label") or "")) or GEOGRAPHIC_RE.match(str(row.get("product_or_segment") or "")):
        return {}
    if re.search(r"^total\b|% of total|constant currency|foreign currency", direct, re.IGNORECASE):
        return {}
    value = _float_value(row.get("value"))
    if IDENTICAL_OR_COMPARABLE_SALES_RE.search(direct):
        return {
            "slot_id": "same_store_sales_growth",
            "claim_scope": "company_disclosed_same_store_sales_growth",
            "reason": "mislabeled_product_revenue_same_store_growth_context_verified",
            "metric_name": "same-store or identical sales growth",
            "value": value,
            "unit": "percent_change",
            "unit_category": "percent",
            "claim_boundary": (
                "May support company-disclosed same-store/comparable/identical sales growth for this value/period only; "
                "source parser mislabeled the row as product revenue, so do not use it as revenue, ASP, market share, "
                "sell-through, channel inventory, or company-wide demand proof."
            ),
        }
    if SAME_STORE_REVENUE_COMPONENT_RE.search(text):
        return {
            "slot_id": "same_store_revenue_growth_component",
            "claim_scope": "company_disclosed_same_store_revenue_growth_component",
            "reason": "mislabeled_product_revenue_same_store_component_context_verified",
            "metric_name": "same-store revenue growth component",
            "value": value,
            "unit": "percent_change_component",
            "unit_category": "percent",
            "claim_boundary": (
                "May support the disclosed component of same-store residential revenue change for this row/period only; "
                "it is not product revenue, rent level, occupancy, ASP, market share, sell-through, or customer deployment."
            ),
        }
    return {}


def _mislabeled_travel_unit_operating_slot(row: Mapping[str, Any], text: str) -> dict[str, Any]:
    cls = str(row.get("verifier_class") or "")
    if cls not in {"business_segment_metric", "business_segment_mixed_table_needs_column_group"}:
        return {}
    direct = " ".join(str(row.get(key) or "") for key in ("product_or_segment", "row_label"))
    if not TRAVEL_UNIT_RE.search(direct):
        return {}
    column = str(row.get("column_label") or "")
    if not _column_matches_period(column, row.get("period")):
        return {}
    raw_value = _float_from_currency_or_numeric_text(row.get("raw_value_text"))
    if raw_value <= 0:
        return {}
    label = direct.lower()
    if "room night" in label:
        slot_id = "room_nights"
        unit = "million_room_nights"
        metric_name = "room nights"
    elif "rental car" in label:
        slot_id = "rental_car_days"
        unit = "million_rental_car_days"
        metric_name = "rental car days"
    else:
        slot_id = "airline_tickets"
        unit = "million_airline_tickets"
        metric_name = "airline tickets"
    return {
        "slot_id": slot_id,
        "claim_scope": f"company_disclosed_{slot_id}",
        "reason": f"mislabeled_product_revenue_{slot_id}_context_verified",
        "metric_name": metric_name,
        "value": raw_value,
        "unit": unit,
        "unit_category": "count_in_millions",
        "claim_boundary": (
            f"May support company-disclosed {metric_name} for this value/period only; source parser mislabeled the row "
            "as USD product revenue, so do not use it as revenue, ASP, market share, sell-through, or customer deployment."
        ),
    }


def _mislabeled_real_estate_per_area_slot(row: Mapping[str, Any], text: str) -> dict[str, Any]:
    if str(row.get("verifier_class") or "") != "percentage_or_change":
        return {}
    direct = " ".join(str(row.get(key) or "") for key in ("product_or_segment", "row_label"))
    if not REAL_ESTATE_PER_OCCUPIED_AREA_RE.search(direct):
        return {}
    column = str(row.get("column_label") or "")
    if not _column_matches_period(column, row.get("period")):
        return {}
    raw_value = _float_from_currency_or_numeric_text(row.get("raw_value_text"))
    if raw_value <= 0:
        return {}
    return {
        "slot_id": "revenue_per_occupied_square_foot",
        "claim_scope": "company_disclosed_revenue_per_occupied_square_foot",
        "reason": "mislabeled_product_revenue_revenue_per_occupied_square_foot_context_verified",
        "metric_name": "average annual total revenues per occupied square foot",
        "value": raw_value,
        "unit": "USD_per_occupied_square_foot",
        "unit_category": "currency_per_area",
        "claim_boundary": (
            "May support company-disclosed average annual total revenues per occupied square foot for this value/period "
            "only; source parser mislabeled/scaled the row as product revenue, so do not use it as total revenue, ASP, "
            "market share, occupancy, or customer deployment."
        ),
    }


def _row_is_percent_like(row: Mapping[str, Any]) -> bool:
    return bool(
        PERCENT_RE.search(str(row.get("unit") or ""))
        or PERCENT_RE.search(str(row.get("unit_category") or ""))
        or PERCENT_RE.search(str(row.get("raw_value_text") or ""))
    )


def _looks_like_mislabeled_operating_metric(row: Mapping[str, Any]) -> bool:
    direct = " ".join(str(row.get(key) or "") for key in ("product_or_segment", "row_label"))
    return bool(
        TRAVEL_UNIT_RE.search(direct)
        or REAL_ESTATE_PER_OCCUPIED_AREA_RE.search(direct)
        or PAYMENT_ACTIVITY_RE.search(direct)
        or SEGMENT_REVENUE_GROWTH_RE.search(direct)
    )


def _column_matches_period(column_label: str, period: Any) -> bool:
    period_text = str(period or "")
    year_match = re.search(r"(20\d{2}|19\d{2})", period_text)
    if not year_match:
        return False
    year = year_match.group(1)
    column = str(column_label or "")
    if re.fullmatch(r"\(?\s*(?:in\s+)?(?:\$?\s*)?(?:millions?|thousands?|dollars in millions?|usd millions?)\s*\)?", column, re.IGNORECASE):
        return False
    return bool(re.search(rf"\b{re.escape(year)}\b", column))


def _float_from_raw_text(value: Any) -> float:
    text = str(value or "").strip()
    if not text or "$" in text or "%" in text:
        return 0.0
    match = re.search(r"-?\d[\d,]*(?:\.\d+)?", text)
    if not match:
        return 0.0
    try:
        return float(match.group(0).replace(",", ""))
    except ValueError:
        return 0.0


def _float_from_currency_or_numeric_text(value: Any) -> float:
    text = str(value or "").strip()
    if not text or "%" in text:
        return 0.0
    match = re.search(r"-?\d[\d,]*(?:\.\d+)?", text)
    if not match:
        return 0.0
    try:
        return float(match.group(0).replace(",", ""))
    except ValueError:
        return 0.0


def _has_unit_sales_context(text: str, row_label: str, column_label: str, unit: str) -> bool:
    direct = " ".join([row_label, column_label])
    if re.search(r"products? (and services )?delivered (at a point in time|over time)", direct, re.IGNORECASE):
        return False
    if str(unit).upper() == "USD":
        return False
    if re.search(r"sales in units|unit sales|units sold|vehicles delivered", text, re.IGNORECASE):
        return True
    if re.search(r"engines?|turbines?", direct, re.IGNORECASE) and re.search(r"\bunits?\b|sales in units", text, re.IGNORECASE):
        return True
    return False


def _financial_operating_slot(row: Mapping[str, Any], context: Mapping[str, Any]) -> str:
    if str(context.get("primary_lane_id") or "") != "V6":
        return ""
    direct = " ".join(
        str(row.get(key) or "")
        for key in ("product_or_segment", "row_label", "column_label")
    )
    text = direct + " " + str(row.get("citation_sample") or "")
    lowered = text.lower()
    direct_lower = direct.lower()
    if re.search(r"\b(net\s+)?(inflows?|outflows?|flows?)\b|redemptions?|sales|revenue|fees?|charges?", direct_lower):
        return ""
    if (
        "assets under management" in direct_lower
        or re.search(r"\b(average|ending|period-end|total)\s+aum\b|\baum\b", direct_lower)
        or ("assets under management" in lowered and re.search(r"\b(average|ending|period-end|total)\s+aum\b", direct_lower))
    ):
        return "aum"
    if "assets under administration" in direct_lower or re.search(r"\baua\b", direct_lower):
        return "aua"
    if "client assets" in direct_lower:
        return "client_assets"
    if re.search(r"\b(average|total|ending|period-end|customer|client)\s+deposits?\b|\bdeposits?\b|deposit balances?", direct_lower):
        if re.search(r"fees?|charges?|service charges?|revenue|receivable|sweep fees?", direct_lower):
            return ""
        return "deposits"
    if re.search(r"\b(average|total|ending|period-end)\s+loans?\b|\bloans?\b|loan balances?", direct_lower):
        if re.search(r"fees?|servicing|originated|sale|repayment|receivable|gains?|revenue", direct_lower):
            return ""
        return "loan_balance"
    if "trading volume" in lowered:
        return "trading_volume"
    return ""


def _conflicting_claim_groups(rows: Iterable[Mapping[str, Any]]) -> dict[tuple[Any, ...], list[float]]:
    grouped: dict[tuple[Any, ...], set[float]] = defaultdict(set)
    for row in rows:
        grouped[_claim_key_without_value(row)].add(_float_value(row.get("value")))
    return {key: sorted(values) for key, values in grouped.items() if len(values) > 1}


def _resolve_conflicting_claims(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[_claim_key_without_value(row)].append(dict(row))

    resolved_conflicts: dict[tuple[Any, ...], dict[str, Any]] = {}
    unresolved_conflicts: dict[tuple[Any, ...], list[float]] = {}
    resolved_rows: list[dict[str, Any]] = []
    for key, key_rows in grouped.items():
        values = sorted({_float_value(row.get("value")) for row in key_rows})
        if len(values) <= 1:
            continue
        chosen_rows = _choose_aggregate_conflict_rows(key_rows, values)
        if chosen_rows:
            chosen_refs = _unique_strings(row.get("evidence_ref") for row in chosen_rows)
            resolved_conflicts[key] = {"chosen_refs": chosen_refs, "conflict_values": values}
            resolved_rows.extend(chosen_rows)
            continue
        unresolved_conflicts[key] = values
    return {
        "resolved_conflicts": resolved_conflicts,
        "unresolved_conflicts": unresolved_conflicts,
        "resolved_rows": resolved_rows,
    }


def _choose_aggregate_conflict_rows(rows: Sequence[Mapping[str, Any]], values: Sequence[float]) -> list[dict[str, Any]]:
    slot_id = str(rows[0].get("slot_id") or "")
    if slot_id not in {
        "business_segment_revenue",
        "backlog_or_orders",
        "capacity_utilization_or_production_volume",
        "unit_sales_or_deliveries",
        "shipments",
    }:
        return []
    scored: list[tuple[int, float, dict[str, Any]]] = []
    for row in rows:
        value = _float_value(row.get("value"))
        if value <= 0 or not _value_matches_sum_of_sibling_values(value, values):
            continue
        score = 10
        text = _conflict_text(row)
        if re.search(r"\btotal\b|consolidated|worldwide", text, re.IGNORECASE):
            score += 3
        if re.search(r"\bu\.?s\.?\b|international|emea|apac|north america|europe|asia", text, re.IGNORECASE):
            score -= 1
        scored.append((score, value, dict(row)))
    if not scored:
        return []
    scored.sort(key=lambda item: (item[0], item[1], str(item[2].get("evidence_ref") or "")), reverse=True)
    best_score, best_value, _ = scored[0]
    best = [row for score, value, row in scored if score == best_score and value == best_value]
    if not best:
        return []
    # Keep one deterministic aggregate candidate per conflicting claim. Duplicate aggregate rows are still redundant.
    best.sort(key=lambda row: str(row.get("evidence_ref") or ""))
    return [best[0]]


def _value_matches_sum_of_sibling_values(value: float, values: Sequence[float]) -> bool:
    siblings = sorted({float(item) for item in values if float(item) > 0 and abs(float(item) - value) > 1e-6})
    if len(siblings) < 2:
        return False
    tolerance = max(1.0, abs(value) * 0.015)
    if abs(sum(siblings) - value) <= tolerance:
        return True
    for index, left in enumerate(siblings):
        for right in siblings[index + 1 :]:
            if abs(left + right - value) <= tolerance:
                return True
    return False


def _conflict_text(row: Mapping[str, Any]) -> str:
    return " ".join(
        str(row.get(key) or "")
        for key in ("product_or_segment", "row_label", "column_label", "citation_span", "text")
    )


def _claim_key_without_value(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        row.get("ticker"),
        row.get("slot_id"),
        row.get("product_or_segment"),
        row.get("period"),
        row.get("unit"),
    )


def _runtime_conflict_rejection_row(
    runtime_row: Mapping[str, Any],
    *,
    conflict_values: list[float],
    generated_at: str,
) -> dict[str, Any]:
    return {
        "schema_version": REJECTION_SCHEMA_VERSION,
        "generated_at": generated_at,
        "rejection_id": _stable_id("industry_operating_metric_slot_conflict", [runtime_row.get("evidence_ref"), conflict_values]),
        "ticker": runtime_row.get("ticker") or "",
        "primary_lane_id": runtime_row.get("primary_lane_id") or "",
        "rejection_reason": "conflicting_values_for_industry_operating_claim",
        "verifier_id": runtime_row.get("source_verifier_id") or "",
        "verifier_class": runtime_row.get("source_verifier_class") or "",
        "metric_family": runtime_row.get("source_metric_family") or "",
        "product_or_segment": runtime_row.get("product_or_segment") or "",
        "row_label": runtime_row.get("row_label") or "",
        "column_label": runtime_row.get("column_label") or "",
        "period": runtime_row.get("period") or "",
        "unit": runtime_row.get("unit") or "",
        "value": runtime_row.get("value"),
        "slot_decision": "reject",
        "candidate_slot_id": runtime_row.get("slot_id") or "",
        "conflict_values": conflict_values[:12],
        "citation_sample": runtime_row.get("citation_span") or "",
    }


def _runtime_conflict_resolution_rejection_row(
    runtime_row: Mapping[str, Any],
    *,
    chosen_refs: Sequence[str],
    conflict_values: list[float],
    generated_at: str,
) -> dict[str, Any]:
    return {
        "schema_version": REJECTION_SCHEMA_VERSION,
        "generated_at": generated_at,
        "rejection_id": _stable_id("industry_operating_metric_slot_conflict_sibling", [runtime_row.get("evidence_ref"), chosen_refs]),
        "ticker": runtime_row.get("ticker") or "",
        "primary_lane_id": runtime_row.get("primary_lane_id") or "",
        "rejection_reason": "conflict_resolved_non_aggregate_sibling",
        "verifier_id": runtime_row.get("source_verifier_id") or "",
        "verifier_class": runtime_row.get("source_verifier_class") or "",
        "metric_family": runtime_row.get("source_metric_family") or "",
        "product_or_segment": runtime_row.get("product_or_segment") or "",
        "row_label": runtime_row.get("row_label") or "",
        "column_label": runtime_row.get("column_label") or "",
        "period": runtime_row.get("period") or "",
        "unit": runtime_row.get("unit") or "",
        "value": runtime_row.get("value"),
        "slot_decision": "reject",
        "candidate_slot_id": runtime_row.get("slot_id") or "",
        "chosen_aggregate_evidence_refs": list(chosen_refs),
        "conflict_values": conflict_values[:12],
        "citation_sample": runtime_row.get("citation_span") or "",
    }


def _runtime_row(
    row: Mapping[str, Any],
    *,
    context: Mapping[str, Any],
    verdict: Mapping[str, Any],
    generated_at: str,
) -> dict[str, Any]:
    ticker = _ticker(row)
    slot_id = str(verdict.get("slot_id") or "")
    evidence_ref = _stable_id("industry_operating_metric_slot", [row.get("verifier_id"), ticker, slot_id])
    product_or_segment = str(row.get("product_or_segment") or row.get("row_label") or "")
    runtime_value = verdict.get("normalized_value", row.get("value"))
    runtime_unit = str(verdict.get("normalized_unit") or row.get("unit") or "")
    runtime_unit_category = str(verdict.get("normalized_unit_category") or row.get("unit_category") or "")
    metric_name = str(verdict.get("normalized_metric_name") or row.get("metric_name") or slot_id)
    text = (
        f"{ticker} disclosed {slot_id} for {product_or_segment}: "
        f"{runtime_value} {runtime_unit} for {row.get('period')}."
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "evidence_ref": evidence_ref,
        "evidence_id": evidence_ref,
        "snapshot_id": evidence_ref,
        "source_id": "industry_operating_metric_exact_slot",
        "underlying_source_id": row.get("source_id") or "",
        "source_family": "company_product_evidence_graph",
        "runtime_source_family": "company_product_evidence_graph",
        "source_layer_id": "L1",
        "source_layer": "L1",
        "layer_id": "L1",
        "source_class": "company_disclosed_industry_operating_metric",
        "evidence_graph_status": "exact_authority_ready",
        "runtime_ready_context": True,
        "exact_value_authority": True,
        "can_support_company_exact_fact": True,
        "promotion_status": "runtime_fact_allowed",
        "parser_status": "industry_operating_metric_slot_parser_pass",
        "source_specific_parser": "industry_operating_metric_slot_v0_1",
        "structured_fact_status": "exact_fact_materialized",
        "bounded_structured_context": True,
        "structured_context_type": "industry_operating_metric_exact_slot",
        "ticker": ticker,
        "company": row.get("company") or context.get("company_name") or "",
        "primary_lane_id": context.get("primary_lane_id") or "",
        "slot_id": slot_id,
        "slot_metric_family": verdict.get("slot_metric_family") or slot_id,
        "claim_types": ["company_disclosed_industry_operating_metric", str(verdict.get("claim_scope") or "")],
        "allowed_claims": ["company_disclosed_industry_operating_metric", slot_id],
        "forbidden_claims": [
            "product_revenue",
            "market_share",
            "asp",
            "sell_through",
            "channel_inventory",
            "commercial_tracker_estimate",
        ],
        "authority_boundary": verdict.get("claim_boundary") or "",
        "claim_boundary": verdict.get("claim_boundary") or "",
        "runtime_use_boundary": verdict.get("claim_boundary") or "",
        "product_or_segment": product_or_segment,
        "metric_family": slot_id,
        "source_metric_family": row.get("metric_family") or "",
        "metric_name": metric_name,
        "canonical_metric_id": f"industry_operating_metric:{slot_id}",
        "value": runtime_value,
        "unit": runtime_unit,
        "unit_category": runtime_unit_category,
        "source_value": row.get("value"),
        "source_unit": row.get("unit") or "",
        "source_unit_category": row.get("unit_category") or "",
        "raw_value_text": row.get("raw_value_text") or "",
        "period": row.get("period") or "",
        "fiscal_year": row.get("fiscal_year"),
        "row_label": row.get("row_label") or "",
        "column_label": row.get("column_label") or "",
        "citation_span": row.get("citation_sample") or "",
        "citation": {"url": row.get("source_url") or "", "span": row.get("citation_sample") or ""},
        "source_url": row.get("source_url") or "",
        "snapshot_url": row.get("source_url") or "",
        "source_document_id": row.get("source_document_id") or "",
        "source_verifier_id": row.get("verifier_id") or "",
        "source_verifier_class": row.get("verifier_class") or "",
        "source_verifier_reason": row.get("verifier_reason") or "",
        "industry_slot_reason": verdict.get("reason") or "",
        "issuer_binding_status": "issuer_mentioned_in_snapshot",
        "product_binding_status": "segment_or_metric_mentioned_in_snapshot",
        "counterparty_binding_status": "not_bound",
        "entity_binding": {
            "schema_version": "finsight_industry_operating_metric_entity_binding_v0_1",
            "issuer_ticker": ticker,
            "issuer_binding_status": "issuer_mentioned_in_snapshot",
            "product_binding_status": "segment_or_metric_mentioned_in_snapshot",
            "counterparty_binding_status": "not_bound",
            "source_entity_role": "company_disclosed_industry_operating_metric",
            "binding_claim_boundary": verdict.get("claim_boundary") or "",
        },
        "text": text,
        "preview": text,
        "as_of_datetime": generated_at,
    }


def _rejection_row(
    row: Mapping[str, Any],
    context: Mapping[str, Any],
    verdict: Mapping[str, Any],
    reason: str,
    generated_at: str,
) -> dict[str, Any]:
    return {
        "schema_version": REJECTION_SCHEMA_VERSION,
        "generated_at": generated_at,
        "rejection_id": _stable_id("industry_operating_metric_slot_rejection", [row.get("verifier_id"), reason]),
        "ticker": _ticker(row),
        "primary_lane_id": context.get("primary_lane_id") or "",
        "rejection_reason": reason,
        "verifier_id": row.get("verifier_id") or "",
        "verifier_class": row.get("verifier_class") or "",
        "metric_family": row.get("metric_family") or "",
        "product_or_segment": row.get("product_or_segment") or "",
        "row_label": row.get("row_label") or "",
        "column_label": row.get("column_label") or "",
        "period": row.get("period") or "",
        "unit": row.get("unit") or "",
        "value": row.get("value"),
        "slot_decision": verdict.get("decision") or "",
        "candidate_slot_id": verdict.get("slot_id") or "",
        "citation_sample": row.get("citation_sample") or "",
    }


def _docket_context_by_ticker(rows: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        ticker = _ticker(row)
        if ticker and ticker not in out:
            out[ticker] = {
                "ticker": ticker,
                "company_name": row.get("company_name") or "",
                "primary_lane_id": row.get("primary_lane_id") or "",
                "family_ids": list(row.get("family_ids") or []),
                "family_names": list(row.get("family_names") or []),
                "lane_required_slot_hints": LANE_REQUIRED_SLOT_HINTS.get(str(row.get("primary_lane_id") or ""), ()),
            }
    return out


def _claim_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        row.get("ticker"),
        row.get("slot_id"),
        row.get("product_or_segment"),
        row.get("period"),
        row.get("unit"),
        _float_value(row.get("value")),
    )


def _float_value(value: Any) -> float:
    try:
        return round(float(value), 6)
    except (TypeError, ValueError):
        return 0.0


def _ticker(row: Mapping[str, Any]) -> str:
    return str(row.get("ticker") or "").upper()


def _stable_id(prefix: str, parts: Iterable[Any]) -> str:
    raw = "\x1f".join(str(part) for part in parts)
    return f"{prefix}:{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:16]}"


def _unique_strings(values: Iterable[Any]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            value = json.loads(text)
            if isinstance(value, Mapping):
                rows.append(dict(value))
    return rows


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
