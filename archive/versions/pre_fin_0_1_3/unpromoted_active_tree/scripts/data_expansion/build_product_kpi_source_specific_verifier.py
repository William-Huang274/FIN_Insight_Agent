from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]

SCHEMA_VERSION = "finsight_product_kpi_source_specific_verifier_v0_1"
TICKER_SCHEMA_VERSION = "finsight_product_kpi_source_specific_verifier_ticker_summary_v0_1"
SUMMARY_SCHEMA_VERSION = "finsight_product_kpi_source_specific_verifier_summary_v0_1"

DEFAULT_STRICT_CANDIDATES = Path(
    "Z:/FIN_Insight_Agent/data/manifests/product_evidence_v0_1/company_product_kpi_facts_parser_verified_targeted_repair_strict_v0_1.jsonl"
)
DEFAULT_DOCKET = REPO_ROOT / "data" / "manifests" / "company_gap_docket_v0_1.jsonl"
DEFAULT_OUTPUT_ROWS = REPO_ROOT / "data" / "manifests" / "product_kpi_source_specific_verifier_v0_1.jsonl"
DEFAULT_OUTPUT_TICKER_SUMMARY = (
    REPO_ROOT / "data" / "manifests" / "product_kpi_source_specific_verifier_ticker_summary_v0_1.jsonl"
)
DEFAULT_OUTPUT_PROMOTABLE = (
    REPO_ROOT / "data" / "manifests" / "product_kpi_source_specific_verifier_promotable_rows_v0_1.jsonl"
)
DEFAULT_OUTPUT_SUMMARY = REPO_ROOT / "data" / "manifests" / "product_kpi_source_specific_verifier_summary_v0_1.json"
DEFAULT_OUTPUT_REPORT = (
    REPO_ROOT / "docs" / "internal" / "vnext_20260610" / "vertical_lanes" / "product_kpi_source_specific_verifier.zh-CN.md"
)

PRODUCT_EXACT_NODE_TYPES = {
    "product_family",
    "product_or_therapy_family",
    "model_or_product_family",
    "category_or_brand_family",
    "financial_product_or_service",
}
BUSINESS_SEGMENT_NODE_TYPES = {
    "segment",
    "business_line",
    "banner_or_channel",
    "therapeutic_area_or_business_line",
}
GEOGRAPHIC_RE = re.compile(
    r"^(north america|latin america|emea|apac|asia(?:-pacific)?|europe|africa|"
    r"americas?|international|domestic|united states|u\.s\.|us|canada|mexico|"
    r"china|japan|korea|india|brazil|germany|western europe|other americas|"
    r"europe,\s*middle east.*africa|asia pacific|other countries|rest of world|"
    r"key emerging markets)(?:\s*\([^)]*\))?$",
    re.IGNORECASE,
)
BAD_TOTAL_ROW_RE = re.compile(
    r"^(total|total revenue|total revenues|revenue|revenues|net sales|sales|"
    r"total segment revenues|total casino revenues|total mall revenues|"
    r"total reportable segment revenue|total revenue from contracts with customers|"
    r"total net revenue|total net revenues|total consolidated revenues|"
    r"total consolidated revenue|total noninterest income|operating income|"
    r"operating profit|gross profit|gross margin|income before|other|corporate|"
    r"eliminations?)$",
    re.IGNORECASE,
)
NON_PRODUCT_ROW_RE = re.compile(
    r"general and administrative|research and development|sales and marketing|"
    r"gross profit|operating income|operating profit|cost of revenue|pricing|"
    r"volume|currency|impact of changes|lease|uncollectible|rent relief|"
    r"contract liability|deferred revenue|intersegment|corporate",
    re.IGNORECASE,
)
CHANGE_TEXT_RE = re.compile(r"change|increase|decrease|variance|growth|percentage|\bover\b|\bvs\b", re.IGNORECASE)
PRODUCT_REVENUE_CONTEXT_RE = re.compile(
    r"sales of principal products|revenue by product|revenues by product|"
    r"net sales by product|net revenue by category|revenue by category|"
    r"product line|product category|product categories|brand",
    re.IGNORECASE,
)
SEGMENT_REVENUE_CONTEXT_RE = re.compile(
    r"segment revenue|segment sales|revenues by segment|revenue by segment|"
    r"net revenue by segment|sales by segment|operating segments|reportable segment",
    re.IGNORECASE,
)
MIXED_OR_FORBIDDEN_TABLE_RE = re.compile(
    r"operating income|operating profit|income before|gross profit|gross margin|"
    r"cost of|expenses?|price realization|sales volume|currency|acquisition|"
    r"divestiture|eliminations|consolidating adjustments",
    re.IGNORECASE,
)
PERCENT_COLUMN_RE = re.compile(r"%|percent|percentage|margin|growth", re.IGNORECASE)

PROMOTABLE_CLASSES = {"promotable_product_category_or_product_line_metric"}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Classify strict Product-KPI repair candidates before promotion.")
    parser.add_argument("--strict-candidates", type=Path, default=DEFAULT_STRICT_CANDIDATES)
    parser.add_argument("--docket", type=Path, default=DEFAULT_DOCKET)
    parser.add_argument("--output-rows", type=Path, default=DEFAULT_OUTPUT_ROWS)
    parser.add_argument("--output-ticker-summary", type=Path, default=DEFAULT_OUTPUT_TICKER_SUMMARY)
    parser.add_argument("--output-promotable", type=Path, default=DEFAULT_OUTPUT_PROMOTABLE)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--output-report", type=Path, default=DEFAULT_OUTPUT_REPORT)
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at = _utc_now()
    target_tickers = _verifier_target_tickers(_load_jsonl(args.docket))
    candidate_rows = [
        row for row in _load_jsonl(args.strict_candidates) if _ticker(row) in target_tickers
    ]
    verifier_rows = build_verifier_rows(candidate_rows=candidate_rows, generated_at=generated_at)
    ticker_rows = build_ticker_summary_rows(verifier_rows=verifier_rows, generated_at=generated_at)
    promotable_rows = [
        _promotable_candidate_from_verifier(row, generated_at=generated_at)
        for row in verifier_rows
        if row.get("verifier_class") in PROMOTABLE_CLASSES
    ]
    summary = build_summary(
        verifier_rows=verifier_rows,
        ticker_rows=ticker_rows,
        promotable_rows=promotable_rows,
        target_tickers=target_tickers,
        generated_at=generated_at,
        output_rows=args.output_rows,
        output_ticker_summary=args.output_ticker_summary,
        output_promotable=args.output_promotable,
        output_report=args.output_report,
    )
    _write_jsonl(args.output_rows, verifier_rows)
    _write_jsonl(args.output_ticker_summary, ticker_rows)
    _write_jsonl(args.output_promotable, promotable_rows)
    _write_json(args.output_summary, summary)
    args.output_report.parent.mkdir(parents=True, exist_ok=True)
    args.output_report.write_text(render_report(summary, ticker_rows=ticker_rows), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if args.strict and summary["unclassified_candidate_count"]:
        return 1
    return 0


def build_verifier_rows(*, candidate_rows: Iterable[Mapping[str, Any]], generated_at: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    candidate_list = [dict(row) for row in candidate_rows]
    all_candidates = candidate_list + _source_specific_sec_backfill_candidates(candidate_list)
    for row in all_candidates:
        verdict = classify_candidate(row)
        out.append(
            {
                "schema_version": SCHEMA_VERSION,
                "generated_at": generated_at,
                "verifier_id": _stable_id(
                    "product_kpi_source_specific_verifier",
                    [row.get("fact_id"), _ticker(row), row.get("period"), row.get("value"), verdict["verifier_class"]],
                ),
                "ticker": _ticker(row),
                "company": row.get("company") or row.get("company_name") or "",
                "fact_id": row.get("fact_id") or "",
                "source_document_id": row.get("source_document_id") or "",
                "source_url": row.get("source_url") or "",
                "source_id": row.get("source_id") or "",
                "source_specific_parser": row.get("source_specific_parser") or "",
                "metric_family": row.get("metric_family") or "",
                "metric_name": row.get("metric_name") or "",
                "product_or_segment": row.get("product_or_segment") or "",
                "matched_product_alias": row.get("matched_product_alias") or "",
                "product_node_id": row.get("product_node_id") or "",
                "product_node_type": row.get("product_node_type") or "",
                "product_link_method": row.get("product_link_method") or "",
                "product_link_score": row.get("product_link_score"),
                "period": row.get("period") or "",
                "fiscal_year": row.get("fiscal_year"),
                "unit": row.get("unit") or "",
                "unit_category": row.get("unit_category") or "",
                "value": row.get("value"),
                "raw_value_text": row.get("raw_value_text") or "",
                "row_label": row.get("row_label") or "",
                "column_label": row.get("column_label") or "",
                "verifier_decision": verdict["verifier_decision"],
                "verifier_class": verdict["verifier_class"],
                "verifier_reason": verdict["verifier_reason"],
                "target_claim_scope": verdict["target_claim_scope"],
                "can_promote_product_kpi_exact": verdict["can_promote_product_kpi_exact"],
                "can_promote_business_segment_metric": verdict["can_promote_business_segment_metric"],
                "defer_to_step": verdict["defer_to_step"],
                "claim_boundary": verdict["claim_boundary"],
                "citation_sample": _citation_sample(row),
            }
        )
    return out


def build_ticker_summary_rows(*, verifier_rows: Iterable[Mapping[str, Any]], generated_at: str) -> list[dict[str, Any]]:
    by_ticker: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in verifier_rows:
        by_ticker[str(row.get("ticker") or "")].append(row)
    out: list[dict[str, Any]] = []
    for ticker, rows in sorted(by_ticker.items()):
        class_counts = Counter(str(row.get("verifier_class") or "") for row in rows)
        decision_counts = Counter(str(row.get("verifier_decision") or "") for row in rows)
        out.append(
            {
                "schema_version": TICKER_SCHEMA_VERSION,
                "generated_at": generated_at,
                "ticker": ticker,
                "candidate_count": len(rows),
                "verifier_class_counts": dict(sorted(class_counts.items())),
                "verifier_decision_counts": dict(sorted(decision_counts.items())),
                "promotable_product_metric_count": class_counts.get("promotable_product_category_or_product_line_metric", 0),
                "business_segment_metric_count": class_counts.get("business_segment_metric", 0),
                "region_only_count": class_counts.get("region_only", 0),
                "percentage_or_change_count": class_counts.get("percentage_or_change", 0),
                "sentence_relation_insufficient_count": class_counts.get("sentence_relation_insufficient", 0),
                "operating_metric_defer_step2_count": class_counts.get("operating_metric_defer_step2", 0),
                "top_verifier_reasons": dict(Counter(str(row.get("verifier_reason") or "") for row in rows).most_common(8)),
                "sample_candidate_refs": [str(row.get("fact_id") or row.get("verifier_id") or "") for row in rows[:5]],
            }
        )
    return out


def build_summary(
    *,
    verifier_rows: list[dict[str, Any]],
    ticker_rows: list[dict[str, Any]],
    promotable_rows: list[dict[str, Any]],
    target_tickers: set[str],
    generated_at: str,
    output_rows: Path,
    output_ticker_summary: Path,
    output_promotable: Path,
    output_report: Path,
) -> dict[str, Any]:
    class_counts = Counter(row["verifier_class"] for row in verifier_rows)
    decision_counts = Counter(row["verifier_decision"] for row in verifier_rows)
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "pass" if verifier_rows and not class_counts.get("unclassified") else "gap",
        "target_ticker_count": len(target_tickers),
        "candidate_count": len(verifier_rows),
        "candidate_ticker_count": len({row["ticker"] for row in verifier_rows}),
        "ticker_summary_count": len(ticker_rows),
        "verifier_class_counts": dict(sorted(class_counts.items())),
        "verifier_decision_counts": dict(sorted(decision_counts.items())),
        "promotable_product_metric_count": len(promotable_rows),
        "promotable_product_metric_ticker_count": len({row["ticker"] for row in promotable_rows}),
        "business_segment_metric_candidate_count": class_counts.get("business_segment_metric", 0),
        "region_only_candidate_count": class_counts.get("region_only", 0),
        "percentage_or_change_candidate_count": class_counts.get("percentage_or_change", 0),
        "sentence_relation_insufficient_candidate_count": class_counts.get("sentence_relation_insufficient", 0),
        "operating_metric_defer_step2_candidate_count": class_counts.get("operating_metric_defer_step2", 0),
        "unclassified_candidate_count": class_counts.get("unclassified", 0),
        "outputs": {
            "rows": str(output_rows),
            "ticker_summary": str(output_ticker_summary),
            "promotable_rows": str(output_promotable),
            "report": str(output_report),
        },
        "boundary": (
            "This verifier classifies strict Product-KPI repair candidates before promotion. "
            "Only product/category/product-line currency revenue rows with product-table context are promotable as Product-KPI exact. "
            "Business segment rows are classified for Step 2 and are not product-family KPI proof."
        ),
    }


def classify_candidate(row: Mapping[str, Any]) -> dict[str, Any]:
    base = {
        "verifier_decision": "reject",
        "verifier_class": "unclassified",
        "verifier_reason": "no_rule_matched",
        "target_claim_scope": "",
        "can_promote_product_kpi_exact": False,
        "can_promote_business_segment_metric": False,
        "defer_to_step": "",
        "claim_boundary": "Do not promote without an explicit source-specific verifier decision.",
    }
    source_id = str(row.get("source_id") or "")
    metric_family = str(row.get("metric_family") or "")
    unit = str(row.get("unit") or "")
    unit_category = str(row.get("unit_category") or "")
    row_label = str(row.get("row_label") or "").strip()
    column_label = str(row.get("column_label") or "").strip()
    product_label = str(row.get("product_or_segment") or "").strip()
    raw_value = str(row.get("raw_value_text") or "")
    citation = str(row.get("citation_span") or "")
    node_type = str(row.get("product_node_type") or "")
    source_specific_parser = str(row.get("source_specific_parser") or "")

    if source_id != "company_product_kpi_facts_structured_metric_parser":
        return _verdict(
            base,
            "classify_only",
            "sentence_relation_insufficient",
            "not_structured_table_metric",
            defer_to_step="sentence_local_relation_verifier",
        )
    if not row_label or not column_label or str(row.get("product_link_method") or "") != "structured_row_label_alias_exact":
        return _verdict(
            base,
            "classify_only",
            "sentence_relation_insufficient",
            "missing_table_coordinates_or_exact_row_binding",
            defer_to_step="sentence_local_relation_verifier",
        )
    if _is_period_after_fiscal_year(row):
        return _verdict(base, "reject", "period_or_version_conflict", "period_after_fiscal_year")
    if metric_family != "product_revenue":
        return _verdict(
            base,
            "classify_only",
            "operating_metric_defer_step2",
            f"metric_family_{metric_family or 'missing'}_requires_industry_operating_metric_slot",
            defer_to_step="step2_industry_operating_metric_slot",
        )
    if unit != "USD" or unit_category != "currency" or "%" in raw_value:
        return _verdict(base, "reject", "percentage_or_change", "not_currency_revenue_or_raw_percent")
    value = _float_value(row.get("value"))
    if value <= 0:
        return _verdict(base, "reject", "non_product_or_total", "non_positive_or_adjustment_value")
    if source_specific_parser == "sec_cash_markets_business_transaction_fee_table_v0_1":
        return _verdict(
            base,
            "promote",
            "promotable_product_category_or_product_line_metric",
            "sec_cash_markets_business_transaction_fee_table_verified",
            target_claim_scope="company_disclosed_product_or_business_line_transaction_fee_revenue",
            can_promote_product_kpi_exact=True,
            claim_boundary=(
                "Company-disclosed transaction-fee revenue by business/product line only for the cited SEC table, "
                "value, unit, period, and line item; not market share, ASP, sell-through, or commercial tracker proof."
            ),
        )
    if CHANGE_TEXT_RE.search(row_label) or CHANGE_TEXT_RE.search(column_label):
        return _verdict(base, "reject", "percentage_or_change", "change_or_growth_row_or_column")
    if _is_percent_like_cell(row, citation):
        return _verdict(base, "reject", "percentage_or_change", "mixed_percent_table_or_percent_like_cell")
    if GEOGRAPHIC_RE.match(row_label) or GEOGRAPHIC_RE.match(product_label):
        return _verdict(base, "classify_only", "region_only", "geographic_or_region_only_row")
    if BAD_TOTAL_ROW_RE.match(row_label) or NON_PRODUCT_ROW_RE.search(row_label):
        return _verdict(base, "reject", "non_product_or_total", "generic_total_or_non_product_row_label")

    if node_type in PRODUCT_EXACT_NODE_TYPES:
        if PRODUCT_REVENUE_CONTEXT_RE.search(citation) and not _has_mixed_or_forbidden_table_context(citation):
            return _verdict(
                base,
                "promote",
                "promotable_product_category_or_product_line_metric",
                "product_or_category_revenue_table_context_verified",
                target_claim_scope="company_disclosed_product_category_revenue",
                can_promote_product_kpi_exact=True,
                claim_boundary="Company-disclosed product/category/product-line metric only for the cited value/unit/period/product.",
            )
        return _verdict(
            base,
            "classify_only",
            "product_table_context_insufficient",
            "product_node_without_verified_product_revenue_table_context",
            defer_to_step="product_table_local_citation_verifier",
        )

    if node_type in BUSINESS_SEGMENT_NODE_TYPES:
        if _has_mixed_or_forbidden_table_context(citation):
            return _verdict(
                base,
                "classify_only",
                "business_segment_mixed_table_needs_column_group",
                "segment_table_contains_mixed_financial_columns",
                defer_to_step="step2_industry_operating_metric_slot",
            )
        if SEGMENT_REVENUE_CONTEXT_RE.search(citation):
            return _verdict(
                base,
                "classify_only",
                "business_segment_metric",
                "company_disclosed_business_segment_revenue_candidate",
                target_claim_scope="company_disclosed_business_segment_revenue",
                can_promote_business_segment_metric=True,
                defer_to_step="step2_industry_operating_metric_slot",
                claim_boundary="Business segment metric may support fundamental/business mix, not product-family KPI proof.",
            )
        return _verdict(
            base,
            "classify_only",
            "business_segment_metric",
            "business_segment_candidate_without_source_specific_segment_table_context",
            defer_to_step="step2_industry_operating_metric_slot",
        )

    return _verdict(base, "reject", "non_product_or_total", "unknown_or_non_product_node_type")


def _verdict(
    base: dict[str, Any],
    decision: str,
    cls: str,
    reason: str,
    *,
    target_claim_scope: str = "",
    can_promote_product_kpi_exact: bool = False,
    can_promote_business_segment_metric: bool = False,
    defer_to_step: str = "",
    claim_boundary: str | None = None,
) -> dict[str, Any]:
    out = dict(base)
    out.update(
        {
            "verifier_decision": decision,
            "verifier_class": cls,
            "verifier_reason": reason,
            "target_claim_scope": target_claim_scope,
            "can_promote_product_kpi_exact": can_promote_product_kpi_exact,
            "can_promote_business_segment_metric": can_promote_business_segment_metric,
            "defer_to_step": defer_to_step,
        }
    )
    if claim_boundary is not None:
        out["claim_boundary"] = claim_boundary
    return out


def _promotable_candidate_from_verifier(row: Mapping[str, Any], *, generated_at: str) -> dict[str, Any]:
    out = {key: row.get(key) for key in row.keys()}
    out["schema_version"] = "finsight_product_kpi_source_specific_verifier_promotable_row_v0_1"
    out["generated_at"] = generated_at
    out["repair_promotion_status"] = "source_specific_verifier_promotable"
    out["repair_claim_scope"] = row.get("target_claim_scope") or ""
    out["runtime_use_boundary"] = row.get("claim_boundary") or ""
    return dict(out)


def render_report(summary: Mapping[str, Any], *, ticker_rows: Iterable[Mapping[str, Any]]) -> str:
    lines = [
        "# Product-KPI Source-Specific Verifier",
        "",
        f"- schema_version: `{summary.get('schema_version')}`",
        f"- generated_at: `{summary.get('generated_at')}`",
        f"- status: `{summary.get('status')}`",
        f"- target_ticker_count: `{summary.get('target_ticker_count')}`",
        f"- candidate_count: `{summary.get('candidate_count')}`",
        f"- promotable_product_metric_count: `{summary.get('promotable_product_metric_count')}`",
        f"- business_segment_metric_candidate_count: `{summary.get('business_segment_metric_candidate_count')}`",
        f"- region_only_candidate_count: `{summary.get('region_only_candidate_count')}`",
        f"- percentage_or_change_candidate_count: `{summary.get('percentage_or_change_candidate_count')}`",
        f"- sentence_relation_insufficient_candidate_count: `{summary.get('sentence_relation_insufficient_candidate_count')}`",
        f"- operating_metric_defer_step2_candidate_count: `{summary.get('operating_metric_defer_step2_candidate_count')}`",
        f"- unclassified_candidate_count: `{summary.get('unclassified_candidate_count')}`",
        "",
        "## Class Counts",
        "",
        "| class | count |",
        "| --- | ---: |",
    ]
    for cls, count in sorted((summary.get("verifier_class_counts") or {}).items()):
        lines.append(f"| `{cls}` | {count} |")
    lines.extend(["", "## Ticker Summary Samples", "", "| ticker | candidates | top classes |", "| --- | ---: | --- |"])
    for row in list(ticker_rows)[:30]:
        lines.append(
            f"| `{row.get('ticker')}` | {row.get('candidate_count')} | "
            f"`{json.dumps(row.get('verifier_class_counts') or {}, ensure_ascii=False, sort_keys=True)}` |"
        )
    lines.extend(["", "## Boundary", "", str(summary.get("boundary") or ""), ""])
    return "\n".join(lines)


def _verifier_target_tickers(docket_rows: Iterable[Mapping[str, Any]]) -> set[str]:
    return {
        _ticker(row)
        for row in docket_rows
        if (
            row.get("cluster_id") == "product_kpi_source_specific_table_verifier"
            or str(row.get("gap_reason") or "").startswith("source_specific_verifier_")
        )
        and _ticker(row)
    }


def _citation_sample(row: Mapping[str, Any]) -> str:
    return str(row.get("citation_span") or "")[:700]


def _is_percent_like_cell(row: Mapping[str, Any], citation: str) -> bool:
    value = _float_value(row.get("value"))
    column_label = str(row.get("column_label") or "")
    raw_value = str(row.get("raw_value_text") or "")
    if PERCENT_COLUMN_RE.search(column_label):
        return True
    if "%" in raw_value:
        return True
    if value < 100_000_000 and "%" in citation:
        return True
    return False


def _source_specific_sec_backfill_candidates(candidate_rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in candidate_rows:
        source_url = str(row.get("source_url") or "")
        if "sec.gov/Archives/" not in source_url or not source_url.lower().endswith((".htm", ".html")):
            continue
        row_text = " ".join(
            str(row.get(key) or "")
            for key in ("row_label", "product_or_segment", "metric_name", "citation_span")
        )
        if not (
            re.search(r"\bsegment orders?\b|BrokerTec fixed income transaction fees|EBS foreign exchange transaction fees", row_text, re.IGNORECASE)
            or _ticker(row) == "CME"
        ):
            continue
        grouped[(_ticker(row), source_url)].append(row)

    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for (_ticker_value, source_url), rows in sorted(grouped.items()):
        html = _sec_html_for_source(source_url, rows)
        if not html:
            continue
        for candidate in _sec_segment_order_candidates(rows[0], source_url=source_url, html=html):
            key = str(candidate.get("fact_id") or "")
            if key and key not in seen:
                seen.add(key)
                out.append(candidate)
        for candidate in _sec_cash_markets_transaction_fee_candidates(rows[0], source_url=source_url, html=html):
            key = str(candidate.get("fact_id") or "")
            if key and key not in seen:
                seen.add(key)
                out.append(candidate)
    return out


def _sec_html_for_source(source_url: str, rows: list[Mapping[str, Any]]) -> str:
    for row in rows:
        html = str(row.get("_source_html") or "")
        if html:
            return html
    try:
        request = urllib.request.Request(
            source_url,
            headers={
                "User-Agent": "FINInsightAgent contact@example.com",
                "Accept-Encoding": "identity",
            },
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read().decode("utf-8", "ignore")
    except Exception:
        return ""


def _sec_segment_order_candidates(seed: Mapping[str, Any], *, source_url: str, html: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for table_info in _iter_sec_tables_with_context(html):
        table_text = table_info["text"]
        if not re.search(r"\bSegment Orders?\b", table_text, re.IGNORECASE):
            continue
        segment_title = _segment_title_from_heading(table_info["heading"])
        if not segment_title:
            continue
        years = _year_sequence(table_text)
        if not years:
            continue
        for cells in table_info["rows"]:
            if not cells or not re.search(r"\bSegment Orders?\b", cells[0], re.IGNORECASE):
                continue
            values = _first_numeric_values(cells[1:], limit=len(years))
            for year, value_millions in zip(years, values):
                if value_millions <= 0:
                    continue
                rows.append(
                    _source_specific_candidate(
                        seed,
                        source_url=source_url,
                        parser_id="sec_segment_results_segment_orders_table_v0_1",
                        metric_family="backlog_or_orders",
                        metric_name="orders",
                        product_or_segment=segment_title,
                        product_node_type="segment",
                        row_label="Segment Orders",
                        year=year,
                        value_millions=value_millions,
                        citation_span=(
                            f"{segment_title} Segment Results [TABLE_START] "
                            f"{' | '.join(cells[:12])}"
                        ),
                    )
                )
    return rows


def _sec_cash_markets_transaction_fee_candidates(seed: Mapping[str, Any], *, source_url: str, html: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for table_info in _iter_sec_tables_with_context(html):
        table_text = table_info["text"]
        if not re.search(r"BrokerTec fixed income transaction fees|EBS foreign exchange transaction fees", table_text, re.IGNORECASE):
            continue
        if "cash markets business" not in table_info["heading"].lower() and "cash markets business" not in table_text.lower():
            continue
        years = _year_sequence(table_text)
        if not years:
            continue
        for cells in table_info["rows"]:
            if not cells or not re.search(r"BrokerTec fixed income transaction fees|EBS foreign exchange transaction fees", cells[0], re.IGNORECASE):
                continue
            values = _first_numeric_values(cells[1:], limit=len(years))
            product_line = cells[0].strip()
            for year, value_millions in zip(years, values):
                if value_millions <= 0:
                    continue
                rows.append(
                    _source_specific_candidate(
                        seed,
                        source_url=source_url,
                        parser_id="sec_cash_markets_business_transaction_fee_table_v0_1",
                        metric_family="product_revenue",
                        metric_name="transaction fee revenue",
                        product_or_segment=product_line,
                        product_node_type="category_or_brand_family",
                        row_label=product_line,
                        year=year,
                        value_millions=value_millions,
                        citation_span=(
                            f"Cash Markets Business transaction fees [TABLE_START] "
                            f"{' | '.join(cells[:12])}"
                        ),
                    )
                )
    return rows


def _iter_sec_tables_with_context(html: str) -> list[dict[str, Any]]:
    try:
        import warnings

        from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
    except Exception:
        return []

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", XMLParsedAsHTMLWarning)
        soup = BeautifulSoup(html, "lxml")
    out: list[dict[str, Any]] = []
    for table in soup.find_all("table"):
        table_text = " ".join(table.get_text(" ", strip=True).split())
        if not table_text:
            continue
        heading = _previous_short_heading(table)
        parsed_rows: list[list[str]] = []
        for tr in table.find_all("tr"):
            cells = [" ".join(td.get_text(" ", strip=True).split()) for td in tr.find_all(["td", "th"])]
            cells = [cell for cell in cells if cell]
            if cells:
                parsed_rows.append(cells)
        out.append({"text": table_text, "heading": heading, "rows": parsed_rows})
    return out


def _previous_short_heading(table: Any) -> str:
    headings: list[str] = []
    previous = table.find_previous()
    steps = 0
    while previous is not None and steps < 50:
        text = " ".join(previous.get_text(" ", strip=True).split())
        if text and len(text) <= 220:
            headings.append(text)
        previous = previous.find_previous()
        steps += 1
    for text in headings:
        if re.search(r"Industrial Technologies and Services Segment Results|Precision and Science Technologies Segment Results|Cash Markets Business", text, re.IGNORECASE):
            return text
    return headings[0] if headings else ""


def _segment_title_from_heading(heading: str) -> str:
    text = re.sub(r"\s+", " ", heading).strip()
    match = re.match(r"(.+?)\s+Segment Results$", text, re.IGNORECASE)
    if not match:
        return ""
    segment = match.group(1).strip()
    if segment.lower() == "segment":
        return ""
    return segment


def _year_sequence(text: str) -> list[str]:
    years: list[str] = []
    for year in re.findall(r"\b(20\d{2}|19\d{2})\b", text):
        if year not in years:
            years.append(year)
        if len(years) >= 3:
            break
    return years


def _first_numeric_values(cells: Iterable[str], *, limit: int) -> list[float]:
    values: list[float] = []
    for cell in cells:
        if not cell or cell in {"$", "%"} or "bps" in cell.lower():
            continue
        if "%" in cell:
            continue
        value = _numeric_cell_value(cell)
        if value <= 0:
            continue
        values.append(value)
        if len(values) >= limit:
            break
    return values


def _numeric_cell_value(cell: str) -> float:
    text = str(cell or "").strip()
    if not text:
        return 0.0
    negative = text.startswith("(") and text.endswith(")")
    match = re.search(r"-?\d[\d,]*(?:\.\d+)?", text)
    if not match:
        return 0.0
    try:
        value = float(match.group(0).replace(",", ""))
    except ValueError:
        return 0.0
    return -value if negative else value


def _source_specific_candidate(
    seed: Mapping[str, Any],
    *,
    source_url: str,
    parser_id: str,
    metric_family: str,
    metric_name: str,
    product_or_segment: str,
    product_node_type: str,
    row_label: str,
    year: str,
    value_millions: float,
    citation_span: str,
) -> dict[str, Any]:
    fact_id = _stable_id("source_specific_product_kpi_candidate", [source_url, parser_id, product_or_segment, row_label, year, value_millions])
    return {
        "ticker": _ticker(seed),
        "company": seed.get("company") or seed.get("company_name") or "",
        "fact_id": fact_id,
        "source_id": "company_product_kpi_facts_structured_metric_parser",
        "source_specific_parser": parser_id,
        "metric_family": metric_family,
        "metric_name": metric_name,
        "product_or_segment": product_or_segment,
        "matched_product_alias": product_or_segment,
        "product_node_id": _stable_id("source_specific_product_node", [_ticker(seed), product_node_type, product_or_segment]),
        "product_node_type": product_node_type,
        "product_link_method": "structured_row_label_alias_exact",
        "product_link_score": 1.0,
        "period": f"FY{year}",
        "fiscal_year": int(year),
        "unit": "USD",
        "unit_category": "currency",
        "value": value_millions * 1_000_000,
        "raw_value_text": f"$ {value_millions:,.1f}",
        "row_label": row_label,
        "column_label": year,
        "source_url": source_url,
        "source_document_id": seed.get("source_document_id") or "",
        "citation_span": citation_span,
    }


def _has_mixed_or_forbidden_table_context(citation: str) -> bool:
    return bool(MIXED_OR_FORBIDDEN_TABLE_RE.search(citation))


def _is_period_after_fiscal_year(row: Mapping[str, Any]) -> bool:
    period = str(row.get("period") or "")
    match = re.search(r"FY(\d{4})", period)
    if not match:
        return False
    try:
        fiscal_year = int(row.get("fiscal_year") or 0)
    except (TypeError, ValueError):
        fiscal_year = 0
    return bool(fiscal_year and int(match.group(1)) > fiscal_year)


def _float_value(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _ticker(row: Mapping[str, Any]) -> str:
    return str(row.get("ticker") or "").upper()


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
