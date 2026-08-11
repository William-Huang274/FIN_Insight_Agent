from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]

SCHEMA_VERSION = "finsight_r16_product_kpi_deep_repair_runtime_row_v0_1"
ATTEMPT_SCHEMA_VERSION = "finsight_r16_product_kpi_deep_repair_attempt_v0_1"
SUMMARY_SCHEMA_VERSION = "finsight_r16_product_kpi_deep_repair_summary_v0_1"

DEFAULT_VERIFIER_ROWS = REPO_ROOT / "data" / "manifests" / "product_kpi_source_specific_verifier_v0_1.jsonl"
DEFAULT_NON_US_REJECTIONS = (
    REPO_ROOT / "data" / "manifests" / "non_us_product_kpi_local_disclosure_runtime_rejections_v0_1.jsonl"
)
DEFAULT_PATENTSVIEW_ATTEMPTS = REPO_ROOT / "data" / "manifests" / "v1_patentsview_technology_research_attempts_v0_1.jsonl"
DEFAULT_OUTPUT_ROWS = REPO_ROOT / "data" / "manifests" / "r16_product_kpi_deep_repair_runtime_rows_v0_1.jsonl"
DEFAULT_OUTPUT_ATTEMPTS = REPO_ROOT / "data" / "manifests" / "r16_product_kpi_deep_repair_attempts_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY = REPO_ROOT / "data" / "manifests" / "r16_product_kpi_deep_repair_summary_v0_1.json"
DEFAULT_OUTPUT_REPORT = (
    REPO_ROOT / "docs" / "internal" / "vnext_20260610" / "vertical_lanes" / "r16_product_kpi_deep_repair.zh-CN.md"
)

COLUMN_GROUP_TICKERS = {
    "AJG",
    "CF",
    "CRDO",
    "CVNA",
    "EL",
    "FANG",
    "IR",
    "JBHT",
    "MET",
    "NVDA",
    "PNW",
    "PTC",
    "RJF",
    "SNA",
    "SRE",
    "STLD",
    "SYF",
    "UPS",
}
SENTENCE_RELATION_TICKERS = {"CAG", "CFG", "DVA", "FTNT", "KR", "NWSA", "ROP", "SBUX", "XPEV"}
PERIOD_VERSION_TICKERS = {"AEP", "CRWD", "DLTR", "GSK", "LNG", "LUV", "OTIS"}
NON_US_PRODUCT_KPI_TICKERS = {"2308.TW", "2317.TW", "6723.T", "8035.T"}
PATENTSVIEW_TICKERS = {
    "1211.HK",
    "300750.SZ",
    "373220.KS",
    "ADI",
    "ALB",
    "CRM",
    "CSCO",
    "FLNC",
    "GOOGL",
    "MPWR",
    "PLTR",
    "SQM",
    "TDY",
    "TER",
    "TSLA",
    "TXN",
    "WDAY",
}

TARGET_CLASSES = {
    "column_group": ("business_segment_mixed_table_needs_column_group", COLUMN_GROUP_TICKERS),
    "sentence_relation": ("sentence_relation_insufficient", SENTENCE_RELATION_TICKERS),
    "period_version": ("period_or_version_conflict", PERIOD_VERSION_TICKERS),
}

PRODUCT_EXACT_NODE_TYPES = {
    "product_family",
    "product_or_therapy_family",
    "model_or_product_family",
    "category_or_brand_family",
    "financial_product_or_service",
}
BUSINESS_SEGMENT_NODE_TYPES = {"segment", "business_line", "banner_or_channel", "therapeutic_area_or_business_line"}

YEAR_RE = re.compile(r"(?:FY|20)(\d{2,4})")
GEOGRAPHIC_RE = re.compile(
    r"^(north america|latin america|emea|apac|asia(?:-pacific)?|europe|africa|"
    r"americas?|international|domestic|united states|u\.s\.|us|canada|mexico|"
    r"china|japan|korea|india|brazil|germany|other countries|rest of world|"
    r"geographic|region|regional|country)(?:\s|\(|$)",
    re.IGNORECASE,
)
TOTAL_OR_NON_PRODUCT_RE = re.compile(
    r"^(total|total revenue|total revenues|revenue|revenues|net sales|sales|"
    r"total net revenue|total net revenues|total consolidated|consolidated|"
    r"corporate|other|all other|eliminations?|reconciliation|unallocated|"
    r"segment operating earnings|operating income|operating profit|gross profit|gross margin|"
    r"income before|estimated annualized revenues acquired)",
    re.IGNORECASE,
)
CHANGE_RE = re.compile(r"change|increase|decrease|variance|growth|%|percent|percentage|margin|bps|\bvs\.?\b", re.IGNORECASE)
PRODUCT_TABLE_CONTEXT_RE = re.compile(
    r"our products|primary .*products|product sales|product engineering services|ip license|"
    r"revenue mix|revenue by line of business|net sales by product|revenue by product|"
    r"revenues by product|product line|product category|major product",
    re.IGNORECASE,
)
SEGMENT_TABLE_CONTEXT_RE = re.compile(
    r"business segments?|reporting segments?|reportable segments?|segment revenue|"
    r"revenue by reportable segments?|revenue by line of business|net sales|"
    r"premiums, fees and other revenues|noninterest income|vehicle sales|services and others",
    re.IGNORECASE,
)
FUTURE_OBLIGATION_RE = re.compile(
    r"remaining fixed performance obligations|remaining performance obligations|backlog|"
    r"contracted revenue|fixed performance obligations|revenue recognized from prior period deferral",
    re.IGNORECASE,
)
NON_OPERATING_RE = re.compile(
    r"realized gains|privately held equity securities|income tax|interest expense|debt|senior notes|"
    r"share-based|derivative|hedging transaction|operating earnings",
    re.IGNORECASE,
)
PRODUCT_LINE_LABEL_RE = re.compile(
    r"^(ammonia|granular urea|uan|an|product sales|product engineering services|ip license revenue|"
    r"license|support and cloud services|professional services|vehicle sales|services and others|"
    r"grocery\s*&?\s*snacks|refrigerated\s*&?\s*frozen|foodservice|consumable|discretionary|"
    r"variety|seasonal|home products|apparel and accessories|seasonal and electronics|"
    r"skin care|makeup|fragrance|hair care)(?:\s*\(\d+\))?$",
    re.IGNORECASE,
)
RELATED_VERIFIER_CLASSES = {
    "business_segment_metric",
    "business_segment_mixed_table_needs_column_group",
    "product_table_context_insufficient",
    "sentence_relation_insufficient",
    "period_or_version_conflict",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="R16 deep repair over Product-KPI verifier rejects and PatentsView credential-bound attempts."
    )
    parser.add_argument("--verifier-rows", type=Path, default=DEFAULT_VERIFIER_ROWS)
    parser.add_argument("--non-us-rejections", type=Path, default=DEFAULT_NON_US_REJECTIONS)
    parser.add_argument("--patentsview-attempts", type=Path, default=DEFAULT_PATENTSVIEW_ATTEMPTS)
    parser.add_argument("--output-rows", type=Path, default=DEFAULT_OUTPUT_ROWS)
    parser.add_argument("--output-attempts", type=Path, default=DEFAULT_OUTPUT_ATTEMPTS)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--output-report", type=Path, default=DEFAULT_OUTPUT_REPORT)
    parser.add_argument("--max-rows-per-ticker-bucket", type=int, default=12)
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at = _utc_now()
    verifier_rows = _load_jsonl(args.verifier_rows)
    non_us_rejections = _load_jsonl(args.non_us_rejections)
    patentsview_attempts = _load_jsonl(args.patentsview_attempts)
    result = build_r16_product_kpi_deep_repair(
        verifier_rows=verifier_rows,
        non_us_rejections=non_us_rejections,
        patentsview_attempts=patentsview_attempts,
        generated_at=generated_at,
        max_rows_per_ticker_bucket=args.max_rows_per_ticker_bucket,
    )
    summary = build_summary(
        runtime_rows=result["runtime_rows"],
        attempt_rows=result["attempt_rows"],
        generated_at=generated_at,
        output_rows=args.output_rows,
        output_attempts=args.output_attempts,
        output_report=args.output_report,
    )
    _write_jsonl(args.output_rows, result["runtime_rows"])
    _write_jsonl(args.output_attempts, result["attempt_rows"])
    _write_json(args.output_summary, summary)
    args.output_report.parent.mkdir(parents=True, exist_ok=True)
    args.output_report.write_text(render_report(summary), encoding="utf-8", newline="\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if args.strict and summary["unclassified_attempt_count"]:
        return 1
    return 0


def build_r16_product_kpi_deep_repair(
    *,
    verifier_rows: Iterable[Mapping[str, Any]],
    non_us_rejections: Iterable[Mapping[str, Any]],
    patentsview_attempts: Iterable[Mapping[str, Any]],
    generated_at: str,
    max_rows_per_ticker_bucket: int = 12,
) -> dict[str, list[dict[str, Any]]]:
    attempts: list[dict[str, Any]] = []
    promoted: list[dict[str, Any]] = []
    selected_by_ticker_bucket: Counter[tuple[str, str]] = Counter()

    for row in verifier_rows:
        row = dict(row)
        group = _target_group(row)
        if not group:
            continue
        decision = classify_verifier_row(row, group=group)
        attempts.append(_attempt_from_verifier(row, decision, group=group, generated_at=generated_at))
        if decision["runtime_action"] not in {"promote_product_kpi_exact", "reroute_business_segment_metric", "reroute_operating_metric"}:
            continue
        ticker_bucket = (_ticker(row), decision["runtime_action"])
        if selected_by_ticker_bucket[ticker_bucket] >= max(1, int(max_rows_per_ticker_bucket)):
            continue
        selected_by_ticker_bucket[ticker_bucket] += 1
        promoted.append(_runtime_row_from_verifier(row, decision, generated_at=generated_at))

    non_us_rows, non_us_attempts = classify_non_us_boundaries(non_us_rejections, generated_at=generated_at)
    patent_attempts = classify_patentsview_attempts(patentsview_attempts, generated_at=generated_at)
    attempts.extend(non_us_attempts)
    attempts.extend(patent_attempts)
    promoted.extend(non_us_rows)
    return {
        "runtime_rows": _dedupe_rows(promoted),
        "attempt_rows": _dedupe_rows(attempts, key_fields=("attempt_id",)),
    }


def classify_verifier_row(row: Mapping[str, Any], *, group: str) -> dict[str, str]:
    label = _label(row)
    citation = _citation(row)
    if not _has_minimum_exact_fields(row):
        return _decision("reject_boundary", "structured_field_gap", "missing_value_unit_period_product_or_citation")
    if _is_percent_or_change(row):
        return _decision("reject_boundary", "percentage_or_change", "percentage_change_or_margin_cell_not_level_fact")
    if _is_geographic(row):
        return _decision("reject_boundary", "geographic_only", "geographic_row_not_product_or_business_metric")
    if _is_total_or_non_product(row):
        return _decision("reject_boundary", "non_product_or_total", "total_non_product_or_non_operating_row")
    if group == "period_version":
        if _future_obligation_like(row):
            return _decision(
                "reroute_operating_metric",
                "future_obligation_or_backlog_metric",
                "future_period_column_is_operating_obligation_not_current_product_revenue",
                metric_family="contracted_performance_obligation",
                metric_name="contracted performance obligation",
                product_node_type="segment",
            )
        return _decision("reject_boundary", "period_version_boundary", "future_or_versioned_period_not_current_product_kpi")
    if _currency_mismatch(row):
        return _decision("reject_boundary", "currency_or_unit_mismatch", "citation_currency_conflicts_with_normalized_unit")
    if _product_line_like(row):
        return _decision(
            "promote_product_kpi_exact",
            "product_line_metric_promoted",
            "company_disclosed_product_or_product_line_value_unit_period_verified",
            product_node_type=_product_node_type(row, product=True),
        )
    if _business_segment_like(row):
        return _decision(
            "reroute_business_segment_metric",
            "business_segment_metric_rerouted",
            "company_disclosed_business_segment_or_service_line_value_unit_period_verified",
            product_node_type=_product_node_type(row, product=False),
        )
    if group == "sentence_relation":
        return _decision("reject_boundary", "sentence_relation_boundary", "local_product_value_relation_still_not_verified")
    return _decision("reject_boundary", "column_group_boundary", "mixed_table_column_group_not_safely_promotable")


def classify_non_us_boundaries(
    rejection_rows: Iterable[Mapping[str, Any]], *, generated_at: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    attempts: list[dict[str, Any]] = []
    runtime_rows: list[dict[str, Any]] = []
    by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rejection_rows:
        ticker = _ticker(row)
        if ticker in NON_US_PRODUCT_KPI_TICKERS:
            by_ticker[ticker].append(dict(row))
    for ticker in sorted(NON_US_PRODUCT_KPI_TICKERS):
        rows = by_ticker.get(ticker, [])
        reason_counts = Counter(str(row.get("rejection_reason") or "") for row in rows)
        status = "non_us_disclosure_parsed_no_promotable_exact_product_kpi" if rows else "non_us_disclosure_attempt_missing"
        attempts.append(
            {
                "schema_version": ATTEMPT_SCHEMA_VERSION,
                "generated_at": generated_at,
                "attempt_id": _stable_id("r16_non_us_product_kpi_attempt", [ticker, status, dict(reason_counts)]),
                "ticker": ticker,
                "repair_group": "non_us_product_kpi",
                "runtime_action": "boundary_only",
                "attempt_status": status,
                "boundary_class": "non_us_public_disclosure_boundary",
                "boundary_reason": _non_us_boundary_reason(reason_counts),
                "source_url": rows[0].get("source_url") if rows else "",
                "sample_rejection_reasons": dict(reason_counts.most_common(6)),
                "claim_boundary": (
                    "Current local exchange / IR annual-report parser found only geography, mix/percentage, stale, or no exact "
                    "product-value rows. Do not substitute product pages or percentage mix as product KPI exact evidence."
                ),
            }
        )
    return runtime_rows, attempts


def classify_patentsview_attempts(rows: Iterable[Mapping[str, Any]], *, generated_at: str) -> list[dict[str, Any]]:
    env_has_key = any(
        str(os.environ.get(name) or "").strip()
        for name in ("PATENTSVIEW_API_KEY", "USPTO_PATENTSVIEW_API_KEY", "PATENT_SEARCH_API_KEY")
    )
    by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        ticker = _ticker(row)
        if ticker in PATENTSVIEW_TICKERS:
            by_ticker[ticker].append(dict(row))
    out: list[dict[str, Any]] = []
    for ticker in sorted(PATENTSVIEW_TICKERS):
        attempts = by_ticker.get(ticker, [])
        statuses = Counter(str(row.get("status") or "") for row in attempts)
        if not env_has_key:
            status = "credential_bound_gap"
            reason = "patentsview_api_key_not_configured"
        elif statuses and all(status in {"missing_patentsview_api_key", "public_api_key_required_not_configured"} for status in statuses):
            status = "credential_bound_gap"
            reason = "existing_attempts_were_run_without_required_api_key"
        elif attempts:
            status = "attempted_no_runtime_row"
            reason = "patentsview_attempts_available_but_no_assignee_topic_runtime_row_materialized"
        else:
            status = "attempt_missing"
            reason = "no_patentsview_attempt_row_found_for_target_ticker"
        out.append(
            {
                "schema_version": ATTEMPT_SCHEMA_VERSION,
                "generated_at": generated_at,
                "attempt_id": _stable_id("r16_patentsview_attempt", [ticker, status, reason]),
                "ticker": ticker,
                "repair_group": "technology_research_patentsview",
                "runtime_action": "boundary_only",
                "attempt_status": status,
                "boundary_class": "credential_or_assignee_resolver_gap",
                "boundary_reason": reason,
                "source_id": "patentsview_api",
                "source_url": attempts[0].get("source_url") if attempts else "https://search.patentsview.org/api/v1/patent/",
                "attempt_status_counts": dict(sorted(statuses.items())),
                "claim_boundary": (
                    "PatentsView can only add L3/L2 technology research proxy rows after API credential and assignee/topic "
                    "resolver pass. It cannot support product revenue, orders, share, ASP, or sell-through claims."
                ),
            }
        )
    return out


def build_summary(
    *,
    runtime_rows: list[dict[str, Any]],
    attempt_rows: list[dict[str, Any]],
    generated_at: str,
    output_rows: Path,
    output_attempts: Path,
    output_report: Path,
) -> dict[str, Any]:
    action_counts = Counter(str(row.get("runtime_action") or "") for row in attempt_rows)
    runtime_action_counts = Counter(str(row.get("repair_runtime_action") or "") for row in runtime_rows)
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "pass" if not [row for row in attempt_rows if row.get("attempt_status") == "unclassified"] else "gap",
        "runtime_row_count": len(runtime_rows),
        "runtime_ticker_count": len({row.get("ticker") for row in runtime_rows if row.get("ticker")}),
        "runtime_action_counts": dict(sorted(runtime_action_counts.items())),
        "product_kpi_exact_repair_row_count": runtime_action_counts.get("promote_product_kpi_exact", 0),
        "business_segment_metric_repair_row_count": runtime_action_counts.get("reroute_business_segment_metric", 0),
        "operating_metric_repair_row_count": runtime_action_counts.get("reroute_operating_metric", 0),
        "attempt_row_count": len(attempt_rows),
        "attempt_group_counts": dict(sorted(Counter(str(row.get("repair_group") or "") for row in attempt_rows).items())),
        "attempt_action_counts": dict(sorted(action_counts.items())),
        "attempt_status_counts": dict(sorted(Counter(str(row.get("attempt_status") or "") for row in attempt_rows).items())),
        "boundary_reason_counts": dict(sorted(Counter(str(row.get("boundary_reason") or "") for row in attempt_rows).items())),
        "unclassified_attempt_count": len([row for row in attempt_rows if row.get("attempt_status") == "unclassified"]),
        "outputs": {"rows": str(output_rows), "attempts": str(output_attempts), "report": str(output_report)},
        "claim_boundary": (
            "R16 rows are parser-backed company-disclosed exact rows only when value/unit/period/product/citation relation is verified. "
            "Business segment and operating rows are routed as company-disclosed operating facts, not SKU/product-family proof. "
            "Boundary attempts are not evidence."
        ),
    }


def render_report(summary: Mapping[str, Any]) -> str:
    lines = [
        "# R16 Product-KPI / Source Adapter Deep Repair",
        "",
        f"- schema_version: `{summary.get('schema_version')}`",
        f"- generated_at: `{summary.get('generated_at')}`",
        f"- status: `{summary.get('status')}`",
        f"- runtime_row_count: `{summary.get('runtime_row_count')}`",
        f"- runtime_ticker_count: `{summary.get('runtime_ticker_count')}`",
        f"- product_kpi_exact_repair_row_count: `{summary.get('product_kpi_exact_repair_row_count')}`",
        f"- business_segment_metric_repair_row_count: `{summary.get('business_segment_metric_repair_row_count')}`",
        f"- operating_metric_repair_row_count: `{summary.get('operating_metric_repair_row_count')}`",
        f"- attempt_row_count: `{summary.get('attempt_row_count')}`",
        "",
        "## Runtime Actions",
        "",
        "| action | count |",
        "| --- | ---: |",
    ]
    for key, value in sorted((summary.get("runtime_action_counts") or {}).items()):
        lines.append(f"| `{key}` | {value} |")
    lines.extend(["", "## Attempt Status", "", "| status | count |", "| --- | ---: |"])
    for key, value in sorted((summary.get("attempt_status_counts") or {}).items()):
        lines.append(f"| `{key}` | {value} |")
    lines.extend(["", "## Boundary Reasons", "", "| reason | count |", "| --- | ---: |"])
    for key, value in sorted((summary.get("boundary_reason_counts") or {}).items()):
        lines.append(f"| `{key}` | {value} |")
    lines.extend(["", "## Boundary", "", str(summary.get("claim_boundary") or ""), ""])
    return "\n".join(lines)


def _target_group(row: Mapping[str, Any]) -> str:
    ticker = _ticker(row)
    cls = str(row.get("verifier_class") or "")
    for group, (target_cls, tickers) in TARGET_CLASSES.items():
        if ticker in tickers and cls == target_cls:
            return group
    for group, (_, tickers) in TARGET_CLASSES.items():
        if ticker in tickers and cls in RELATED_VERIFIER_CLASSES:
            return f"{group}_related_verified"
    return ""


def _decision(
    runtime_action: str,
    status: str,
    reason: str,
    *,
    metric_family: str = "",
    metric_name: str = "",
    product_node_type: str = "",
) -> dict[str, str]:
    return {
        "runtime_action": runtime_action,
        "attempt_status": status,
        "boundary_reason": reason,
        "metric_family_override": metric_family,
        "metric_name_override": metric_name,
        "product_node_type_override": product_node_type,
    }


def _attempt_from_verifier(row: Mapping[str, Any], decision: Mapping[str, str], *, group: str, generated_at: str) -> dict[str, Any]:
    return {
        "schema_version": ATTEMPT_SCHEMA_VERSION,
        "generated_at": generated_at,
        "attempt_id": _stable_id(
            "r16_product_kpi_deep_repair_attempt",
            [_ticker(row), group, row.get("fact_id"), row.get("period"), row.get("value"), decision.get("runtime_action")],
        ),
        "ticker": _ticker(row),
        "company": row.get("company") or "",
        "repair_group": group,
        "source_verifier_class": row.get("verifier_class") or "",
        "source_verifier_reason": row.get("verifier_reason") or "",
        "runtime_action": decision.get("runtime_action") or "",
        "attempt_status": decision.get("attempt_status") or "",
        "boundary_reason": decision.get("boundary_reason") or "",
        "product_or_segment": row.get("product_or_segment") or "",
        "metric_name": row.get("metric_name") or "",
        "value": row.get("value"),
        "unit": row.get("unit") or "",
        "period": row.get("period") or "",
        "fiscal_year": row.get("fiscal_year"),
        "row_label": row.get("row_label") or "",
        "column_label": row.get("column_label") or "",
        "source_url": row.get("source_url") or "",
        "citation_sample": _citation(row)[:900],
        "claim_boundary": _attempt_boundary(str(decision.get("runtime_action") or "")),
    }


def _runtime_row_from_verifier(row: Mapping[str, Any], decision: Mapping[str, str], *, generated_at: str) -> dict[str, Any]:
    runtime_action = str(decision.get("runtime_action") or "")
    product = str(row.get("product_or_segment") or row.get("row_label") or "").strip()
    metric_family = str(decision.get("metric_family_override") or row.get("metric_family") or "product_revenue")
    metric_name = str(decision.get("metric_name_override") or row.get("metric_name") or metric_family)
    node_type = str(decision.get("product_node_type_override") or row.get("product_node_type") or "")
    boundary = _runtime_boundary(runtime_action)
    evidence_ref = _stable_id(
        "R16PRODUCTKPI",
        [_ticker(row), runtime_action, row.get("fact_id"), product, metric_name, row.get("value"), row.get("period"), row.get("source_url")],
    )
    text = f"{_ticker(row)} disclosed {product} {metric_name} of {row.get('value')} {row.get('unit')} for {row.get('period')}."
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "as_of_datetime": generated_at,
        "evidence_ref": evidence_ref,
        "evidence_id": evidence_ref,
        "snapshot_id": evidence_ref,
        "source_id": "company_reported_product_operating_metrics",
        "underlying_source_id": str(row.get("source_id") or ""),
        "source_class": "company_reported_product_operating_metric",
        "source_family": "company_product_evidence_graph",
        "runtime_source_family": "company_product_evidence_graph",
        "source_layer_id": "L1",
        "source_layer": "L1",
        "layer_id": "L1",
        "runtime_ready_context": True,
        "exact_value_authority": True,
        "can_support_company_exact_fact": True,
        "promotion_status": "runtime_fact_allowed",
        "parser_status": "value_unit_period_product_citation_parser_pass",
        "source_specific_parser": "r16_product_kpi_deep_repair_relation_verifier_v0_1",
        "structured_fact_status": "exact_fact_materialized",
        "bounded_structured_context": True,
        "structured_context_type": "company_reported_product_or_business_metric_fact",
        "claim_types": _claim_types(runtime_action),
        "allowed_claims": _allowed_claims(runtime_action, metric_family),
        "forbidden_claims": ["market_share", "channel_inventory", "sell_through", "undisclosed_sku_economics", "commercial_tracker_estimate"],
        "authority_boundary": boundary,
        "claim_boundary": boundary,
        "runtime_use_boundary": boundary,
        "ticker": _ticker(row),
        "company": row.get("company") or row.get("company_name") or "",
        "product_or_segment": product,
        "product_family": product,
        "product_node_id": row.get("product_node_id") or "",
        "product_node_type": node_type,
        "matched_product_alias": row.get("matched_product_alias") or "",
        "metric_family": metric_family,
        "metric_name": metric_name,
        "canonical_metric_id": f"product_kpi:{metric_family}",
        "value": row.get("value"),
        "unit": row.get("unit") or "",
        "unit_category": row.get("unit_category") or "",
        "raw_value_text": row.get("raw_value_text") or "",
        "period": _period(row, runtime_action=runtime_action),
        "period_type": "annual_or_disclosed_period",
        "period_role": "reported_period",
        "fiscal_year": row.get("fiscal_year"),
        "citation_span": _citation(row),
        "citation": {"url": row.get("source_url") or "", "span": _citation(row)[:900]},
        "source_url": row.get("source_url") or "",
        "snapshot_url": row.get("source_url") or "",
        "source_document_id": row.get("source_document_id") or "",
        "source_candidate_id": row.get("fact_id") or row.get("verifier_id") or "",
        "row_label": row.get("row_label") or "",
        "column_label": row.get("column_label") or "",
        "repair_promotion_status": f"r16_{runtime_action}",
        "repair_promotion_gate": decision.get("attempt_status") or "",
        "repair_runtime_action": runtime_action,
        "runtime_action": runtime_action,
        "issuer_binding_status": "issuer_mentioned_in_snapshot",
        "product_binding_status": "product_mentioned_in_snapshot",
        "counterparty_binding_status": "not_bound",
        "entity_binding": {
            "schema_version": "finsight_public_web_entity_binding_v0_1",
            "issuer_ticker": _ticker(row),
            "issuer_binding_status": "issuer_mentioned_in_snapshot",
            "product_binding_status": "product_mentioned_in_snapshot",
            "counterparty_binding_status": "not_bound",
            "product_matched_terms": [product] if product else [],
            "source_entity_role": "company_disclosed_product_or_business_metric",
            "binding_claim_boundary": boundary,
        },
        "text": text,
        "preview": text,
    }


def _has_minimum_exact_fields(row: Mapping[str, Any]) -> bool:
    required = ("ticker", "source_url", "value", "unit", "period")
    if any(row.get(key) in (None, "") for key in required):
        return False
    if not (row.get("product_or_segment") or row.get("row_label")):
        return False
    if not _citation(row):
        return False
    try:
        return float(row.get("value")) > 0
    except (TypeError, ValueError):
        return False


def _is_percent_or_change(row: Mapping[str, Any]) -> bool:
    raw = " ".join(str(row.get(key) or "") for key in ("unit", "unit_category", "raw_value_text", "row_label", "column_label"))
    if str(row.get("unit") or "").lower().startswith("percent"):
        return True
    return bool(CHANGE_RE.search(raw))


def _is_geographic(row: Mapping[str, Any]) -> bool:
    label = _label(row)
    return bool(GEOGRAPHIC_RE.search(label))


def _is_total_or_non_product(row: Mapping[str, Any]) -> bool:
    labels = [
        str(row.get("row_label") or "").strip(),
        str(row.get("matched_product_alias") or "").strip(),
        str(row.get("product_or_segment") or "").strip(),
    ]
    citation = _citation(row)
    if any(label.lower() in {"external", "external non-united states"} for label in labels if label):
        return True
    if any(TOTAL_OR_NON_PRODUCT_RE.search(label) for label in labels if label):
        return True
    if any(re.search(r"\((louisiana|texas|arizona|california|new york|florida)\)", label, re.IGNORECASE) for label in labels):
        return True
    return bool(NON_OPERATING_RE.search(_label(row)) or NON_OPERATING_RE.search(citation[:500]))


def _future_obligation_like(row: Mapping[str, Any]) -> bool:
    if not _is_period_after_fiscal_year(row):
        return False
    if NON_OPERATING_RE.search(_label(row)):
        return False
    if not re.search(r"20\d{2}|after\s+20\d{2}", str(row.get("column_label") or ""), re.IGNORECASE):
        return False
    return bool(FUTURE_OBLIGATION_RE.search(_citation(row)))


def _currency_mismatch(row: Mapping[str, Any]) -> bool:
    citation = _citation(row)
    unit = str(row.get("unit") or "").upper()
    # Avoid promoting rows normalized as USD when the table explicitly says RMB and has no USD marker.
    return unit == "USD" and "RMB" in citation and "US$" not in citation and "USD" not in citation


def _product_line_like(row: Mapping[str, Any]) -> bool:
    node_type = str(row.get("product_node_type") or "")
    citation = _citation(row)
    if node_type in PRODUCT_EXACT_NODE_TYPES and PRODUCT_TABLE_CONTEXT_RE.search(citation):
        return True
    labels = [
        str(row.get("row_label") or "").strip(),
        str(row.get("matched_product_alias") or "").strip(),
        str(row.get("product_or_segment") or "").strip(),
    ]
    if any(PRODUCT_LINE_LABEL_RE.search(label) for label in labels if label) and _reported_revenue_metric(row):
        return True
    return False


def _business_segment_like(row: Mapping[str, Any]) -> bool:
    node_type = str(row.get("product_node_type") or "")
    citation = _citation(row)
    if node_type in BUSINESS_SEGMENT_NODE_TYPES and SEGMENT_TABLE_CONTEXT_RE.search(citation):
        return True
    if SEGMENT_TABLE_CONTEXT_RE.search(citation):
        return True
    return False


def _reported_revenue_metric(row: Mapping[str, Any]) -> bool:
    metric = str(row.get("metric_name") or "").lower()
    unit_category = str(row.get("unit_category") or "").lower()
    unit = str(row.get("unit") or "").lower()
    return bool(
        re.search(r"revenue|sales|net sales", metric)
        and (unit_category == "currency" or unit in {"usd", "eur", "jpy", "twd", "krw", "cny", "rmb"})
    )


def _is_period_after_fiscal_year(row: Mapping[str, Any]) -> bool:
    period_year = _period_year(str(row.get("period") or ""))
    try:
        fiscal_year = int(row.get("fiscal_year") or 0)
    except (TypeError, ValueError):
        fiscal_year = 0
    return bool(period_year and fiscal_year and period_year > fiscal_year)


def _period_year(text: str) -> int:
    match = YEAR_RE.search(text)
    if not match:
        return 0
    raw = match.group(1)
    if len(raw) == 2:
        return 2000 + int(raw)
    return int(raw)


def _product_node_type(row: Mapping[str, Any], *, product: bool) -> str:
    node_type = str(row.get("product_node_type") or "")
    if product:
        return node_type if node_type in PRODUCT_EXACT_NODE_TYPES else "product_family"
    return node_type if node_type in BUSINESS_SEGMENT_NODE_TYPES else "segment"


def _period(row: Mapping[str, Any], *, runtime_action: str) -> str:
    if runtime_action == "reroute_operating_metric":
        return str(row.get("column_label") or row.get("period") or "")
    return str(row.get("period") or "")


def _label(row: Mapping[str, Any]) -> str:
    return " ".join(
        str(row.get(key) or "")
        for key in ("product_or_segment", "matched_product_alias", "row_label", "column_label", "metric_name")
    ).strip()


def _citation(row: Mapping[str, Any]) -> str:
    return str(row.get("citation_span") or row.get("citation_sample") or "")


def _ticker(row: Mapping[str, Any]) -> str:
    return str(row.get("ticker") or "").upper()


def _runtime_boundary(runtime_action: str) -> str:
    if runtime_action == "promote_product_kpi_exact":
        return (
            "Company-disclosed product/product-line metric only for the cited product, metric, value, unit, and period. "
            "Does not prove market share, channel inventory, sell-through, ASP, or undisclosed SKU economics."
        )
    if runtime_action == "reroute_operating_metric":
        return (
            "Company-disclosed operating obligation/backlog-style metric for the cited segment and future/disclosed period. "
            "Use for operating/fundamental context, not current product revenue or market demand proof."
        )
    return (
        "Company-disclosed business/segment/service-line metric only for the cited metric, value, unit, and period. "
        "Use for fundamental/business-mix analysis, not product-family/SKU KPI proof."
    )


def _attempt_boundary(runtime_action: str) -> str:
    if runtime_action in {"promote_product_kpi_exact", "reroute_business_segment_metric", "reroute_operating_metric"}:
        return _runtime_boundary(runtime_action)
    return "Boundary/attempt row only. It must not become evidence or ClaimCard input."


def _claim_types(runtime_action: str) -> list[str]:
    if runtime_action == "promote_product_kpi_exact":
        return ["company_disclosed_product_kpi", "company_reported_product_operating_fact"]
    if runtime_action == "reroute_operating_metric":
        return ["company_disclosed_operating_metric", "company_reported_business_metric"]
    return ["company_disclosed_business_segment_metric", "company_reported_business_metric"]


def _allowed_claims(runtime_action: str, metric_family: str) -> list[str]:
    if runtime_action == "promote_product_kpi_exact":
        return ["company_disclosed_product_kpi", metric_family]
    if runtime_action == "reroute_operating_metric":
        return ["company_disclosed_operating_metric", metric_family]
    return ["company_disclosed_business_segment_metric", metric_family]


def _non_us_boundary_reason(reason_counts: Counter[str]) -> str:
    if not reason_counts:
        return "no_local_exchange_or_ir_attempt_rows_available"
    if reason_counts.get("percentage_or_mix_only_no_exact_product_value"):
        return "public_report_has_mix_or_percentage_but_no_exact_product_value"
    if reason_counts.get("geographic_or_region_only_no_product_kpi"):
        return "public_report_has_geographic_rows_but_no_product_kpi"
    if reason_counts.get("stale_document_year_mismatch"):
        return "public_report_locator_found_stale_document_not_current_exact_kpi"
    return "public_report_parser_found_no_promotable_product_kpi_exact_row"


def _dedupe_rows(rows: Iterable[Mapping[str, Any]], *, key_fields: tuple[str, ...] = ("evidence_ref",)) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        key = "\x1f".join(str(row.get(field) or "") for field in key_fields)
        if key in seen:
            continue
        seen.add(key)
        out.append(dict(row))
    return out


def _stable_id(prefix: str, parts: Iterable[Any]) -> str:
    raw = "\x1f".join(str(part) for part in parts)
    return f"{prefix}:{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:16]}"


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
