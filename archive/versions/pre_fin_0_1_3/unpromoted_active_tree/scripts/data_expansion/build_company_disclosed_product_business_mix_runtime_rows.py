from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_DIR = REPO_ROOT / "data" / "manifests"

SCHEMA_VERSION = "finsight_company_disclosed_product_business_mix_runtime_row_v0_1"
REJECTION_SCHEMA_VERSION = "finsight_company_disclosed_product_business_mix_rejection_v0_1"
SUMMARY_SCHEMA_VERSION = "finsight_company_disclosed_product_business_mix_summary_v0_1"

DEFAULT_VERIFIER_ROWS = MANIFEST_DIR / "product_kpi_source_specific_verifier_v0_1.jsonl"
DEFAULT_OUTPUT_ROWS = MANIFEST_DIR / "company_disclosed_product_business_mix_runtime_rows_v0_1.jsonl"
DEFAULT_OUTPUT_REJECTIONS = MANIFEST_DIR / "company_disclosed_product_business_mix_rejections_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY = MANIFEST_DIR / "company_disclosed_product_business_mix_summary_v0_1.json"

PRODUCT_OR_SEGMENT_NODE_TYPES = {
    "product_family",
    "product_or_therapy_family",
    "model_or_product_family",
    "category_or_brand_family",
    "financial_product_or_service",
    "segment",
    "business_line",
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
TOTAL_OR_NON_PRODUCT_RE = re.compile(
    r"^(total|total revenue|total revenues|revenue|revenues|net sales|sales|"
    r"other|corporate|eliminations?|intersegment|unallocated|not allocated|"
    r"reconciling items?|all other|miscellaneous)$",
    re.IGNORECASE,
)
NON_PRODUCT_CONTEXT_RE = re.compile(
    r"gross margin|operating margin|operating income|operating profit|income before|"
    r"cost of|expenses?|price realization|currency|acquisition|divestiture|"
    r"deferred revenue|contract liability|lease|rent|same store|comparable store",
    re.IGNORECASE,
)
CHANNEL_OR_CUSTOMER_RE = re.compile(
    r"distributors?|direct customers?|customers?|dealers?|resellers?|retailers?|"
    r"channel|wholesale|franchise|licensees?|partners?",
    re.IGNORECASE,
)
CHANGE_OR_GROWTH_RE = re.compile(r"change|increase|decrease|variance|growth|\bover\b|\bvs\b|year over year|yoy", re.IGNORECASE)
REVENUE_MIX_CONTEXT_RE = re.compile(
    r"% of (?:total )?revenue|percent of (?:fiscal )?(?:20\d{2} )?revenue|"
    r"percentage of (?:total )?revenue|revenue mix|sales mix|% of (?:total )?net sales|"
    r"percent of (?:total )?net sales",
    re.IGNORECASE,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Project company-disclosed product/business revenue-mix percentages into bounded exact runtime rows."
    )
    parser.add_argument("--verifier-rows", type=Path, default=DEFAULT_VERIFIER_ROWS)
    parser.add_argument("--output-rows", type=Path, default=DEFAULT_OUTPUT_ROWS)
    parser.add_argument("--output-rejections", type=Path, default=DEFAULT_OUTPUT_REJECTIONS)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at = _utc_now()
    verifier_rows = _load_jsonl(args.verifier_rows)
    runtime_rows, rejection_rows = build_company_disclosed_product_business_mix_runtime_rows(
        verifier_rows,
        generated_at=generated_at,
    )
    summary = build_summary(
        verifier_rows=verifier_rows,
        runtime_rows=runtime_rows,
        rejection_rows=rejection_rows,
        generated_at=generated_at,
        output_rows=args.output_rows,
        output_rejections=args.output_rejections,
    )
    _write_jsonl(args.output_rows, runtime_rows)
    _write_jsonl(args.output_rejections, rejection_rows)
    _write_json(args.output_summary, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if args.strict and summary["status"] != "pass":
        return 1
    return 0


def build_company_disclosed_product_business_mix_runtime_rows(
    verifier_rows: Iterable[Mapping[str, Any]],
    *,
    generated_at: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    rejections: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in verifier_rows:
        source = dict(raw)
        verdict = _mix_rejection_reason(source)
        if verdict:
            rejections.append(_rejection_row(source, verdict, generated_at))
            continue
        ref = _stable_id(
            "company_disclosed_product_business_mix",
            [
                source.get("verifier_id"),
                source.get("fact_id"),
                source.get("ticker"),
                source.get("product_or_segment"),
                source.get("period"),
                source.get("value"),
            ],
        )
        if ref in seen:
            rejections.append(_rejection_row(source, "duplicate_mix_metric_row", generated_at))
            continue
        seen.add(ref)
        rows.append(_runtime_row(source, evidence_ref=ref, generated_at=generated_at))
    return rows, rejections


def build_summary(
    *,
    verifier_rows: list[dict[str, Any]],
    runtime_rows: list[dict[str, Any]],
    rejection_rows: list[dict[str, Any]],
    generated_at: str,
    output_rows: Path,
    output_rejections: Path,
) -> dict[str, Any]:
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "pass" if runtime_rows else "gap",
        "input_verifier_row_count": len(verifier_rows),
        "runtime_row_count": len(runtime_rows),
        "runtime_ticker_count": len({row["ticker"] for row in runtime_rows}),
        "runtime_contract_counts": dict(sorted(Counter(str(row.get("structured_context_type") or "") for row in runtime_rows).items())),
        "source_role_counts": dict(sorted(Counter(str(row.get("source_role") or "") for row in runtime_rows).items())),
        "rejection_count": len(rejection_rows),
        "rejection_reason_counts": dict(sorted(Counter(str(row.get("rejection_reason") or "") for row in rejection_rows).items())),
        "outputs": {
            "rows": str(output_rows),
            "rejections": str(output_rejections),
        },
        "authority_boundary": (
            "Rows support company-disclosed product/business revenue-mix percentages or verifier-approved "
            "product/business-line revenue amounts only. They do not prove ASP, shipment volume, market share, "
            "sell-through, backlog, order value, or commercial tracker estimates."
        ),
    }


def _mix_rejection_reason(row: Mapping[str, Any]) -> str:
    if str(row.get("source_id") or "") != "company_product_kpi_facts_structured_metric_parser":
        return "not_structured_metric_parser_row"
    if str(row.get("metric_family") or "") != "product_revenue":
        return "not_product_revenue_metric_family"
    if str(row.get("product_link_method") or "") != "structured_row_label_alias_exact":
        return "missing_exact_product_or_segment_row_binding"
    if str(row.get("product_node_type") or "") not in PRODUCT_OR_SEGMENT_NODE_TYPES:
        return "unsupported_product_node_type_for_mix_metric"
    product = str(row.get("product_or_segment") or "").strip()
    row_label = str(row.get("row_label") or "").strip()
    column_label = str(row.get("column_label") or "").strip()
    citation = str(row.get("citation_sample") or row.get("citation_span") or "").strip()
    if not product or not row_label or not column_label:
        return "missing_product_row_or_column_label"
    if GEOGRAPHIC_RE.match(product) or GEOGRAPHIC_RE.match(row_label):
        return "region_or_geography_mix_not_product_business_mix"
    if TOTAL_OR_NON_PRODUCT_RE.match(product) or TOTAL_OR_NON_PRODUCT_RE.match(row_label):
        return "total_or_non_product_mix_row"
    if CHANNEL_OR_CUSTOMER_RE.search(product) or CHANNEL_OR_CUSTOMER_RE.search(row_label):
        return "channel_or_customer_mix_not_product_business_mix"
    if _is_promotable_absolute_product_or_business_revenue(row):
        return ""
    if CHANGE_OR_GROWTH_RE.search(row_label) or CHANGE_OR_GROWTH_RE.search(column_label) or CHANGE_OR_GROWTH_RE.search(citation):
        return "change_or_growth_percentage_not_revenue_mix_level"
    if NON_PRODUCT_CONTEXT_RE.search(citation) or NON_PRODUCT_CONTEXT_RE.search(column_label):
        return "non_product_or_margin_percent_context"
    unit = str(row.get("unit") or "").lower()
    unit_category = str(row.get("unit_category") or "").lower()
    raw_value = str(row.get("raw_value_text") or "")
    context = " ".join([unit, unit_category, raw_value, column_label, citation])
    if "percent_of_revenue" not in unit and "percent_of_revenue" not in unit_category and not REVENUE_MIX_CONTEXT_RE.search(context):
        return "not_revenue_mix_percent_context"
    try:
        value = float(row.get("value"))
    except (TypeError, ValueError):
        return "value_not_numeric"
    if value <= 0 or value > 100:
        return "percent_value_out_of_bounds"
    if not str(row.get("source_url") or "").strip():
        return "missing_source_url"
    return ""


def _is_promotable_absolute_product_or_business_revenue(row: Mapping[str, Any]) -> bool:
    if str(row.get("verifier_class") or "") != "promotable_product_category_or_product_line_metric":
        return False
    if str(row.get("unit") or "").upper() != "USD":
        return False
    if str(row.get("unit_category") or "").lower() != "currency":
        return False
    if not str(row.get("source_url") or "").strip():
        return False
    try:
        value = float(row.get("value"))
    except (TypeError, ValueError):
        return False
    return value > 0


def _runtime_row(source: Mapping[str, Any], *, evidence_ref: str, generated_at: str) -> dict[str, Any]:
    ticker = str(source.get("ticker") or "").strip().upper()
    product = str(source.get("product_or_segment") or "").strip()
    period = str(source.get("period") or source.get("fiscal_year") or "").strip()
    value = float(source.get("value"))
    source_url = str(source.get("source_url") or "").strip()
    is_absolute_revenue = _is_promotable_absolute_product_or_business_revenue(source)
    if is_absolute_revenue:
        boundary = (
            "Company-disclosed product/business-line revenue amount for the cited line item, value, unit, and period only; "
            "do not use it as ASP, shipment volume, market share, sell-through, backlog, order value, or commercial tracker proof."
        )
        text = f"{ticker} disclosed {product} revenue of {value:,.0f} USD for {period}."
        source_id = "company_disclosed_product_business_revenue_metrics"
        source_class = "company_disclosed_product_business_revenue_metric"
        parser_status = "company_disclosed_product_business_revenue_parser_pass"
        source_specific_parser = str(source.get("source_specific_parser") or "company_disclosed_product_business_revenue_amount_v0_1")
        structured_context_type = "company_disclosed_product_business_revenue_amount_fact"
        metric_family = "product_revenue"
        metric_name = str(source.get("metric_name") or "product/business-line revenue")
        canonical_metric_id = "product_kpi:product_revenue"
        unit = str(source.get("unit") or "USD")
        unit_category = str(source.get("unit_category") or "currency")
        claim_types = [
            "company_disclosed_product_kpi",
            "company_disclosed_product_revenue_metric",
            "company_disclosed_product_business_revenue_amount",
        ]
        allowed_claims = [
            "company_disclosed_product_kpi",
            "company_disclosed_product_revenue",
            "product_business_revenue_amount",
        ]
        forbidden_claims = [
            "asp",
            "shipment_volume",
            "market_share",
            "sell_through",
            "inventory",
            "backlog",
            "customer_order_value",
            "commercial_tracker_estimate",
        ]
    else:
        boundary = (
            "Company-disclosed product/business revenue-mix percentage for the cited product or business line only; "
            "do not convert to absolute revenue, ASP, volume, market share, sell-through, backlog, or order value."
        )
        text = f"{ticker} disclosed {product} revenue mix of {value:g}% for {period}."
        source_id = "company_disclosed_product_business_mix_metrics"
        source_class = "company_disclosed_product_business_mix_metric"
        parser_status = "company_disclosed_product_business_mix_parser_pass"
        source_specific_parser = "company_disclosed_product_business_mix_percent_v0_1"
        structured_context_type = "company_disclosed_product_business_mix_percent_fact"
        metric_family = "product_business_revenue_mix_percent"
        metric_name = "revenue mix percent"
        canonical_metric_id = "product_kpi:product_business_revenue_mix_percent"
        unit = "percent_of_revenue"
        unit_category = "percent_of_revenue"
        claim_types = [
            "company_disclosed_product_kpi",
            "company_disclosed_business_mix_metric",
            "company_disclosed_product_business_revenue_mix_percent",
        ]
        allowed_claims = [
            "company_disclosed_product_kpi",
            "company_disclosed_business_mix_metric",
            "product_business_revenue_mix_percent",
        ]
        forbidden_claims = [
            "absolute_product_revenue",
            "asp",
            "shipment_volume",
            "market_share",
            "sell_through",
            "inventory",
            "backlog",
            "customer_order_value",
            "commercial_tracker_estimate",
        ]
    return {
        "schema_version": SCHEMA_VERSION,
        "evidence_ref": evidence_ref,
        "evidence_id": evidence_ref,
        "snapshot_id": evidence_ref,
        "source_id": source_id,
        "underlying_source_id": str(source.get("source_id") or ""),
        "source_role": "company_disclosed_product_kpi",
        "source_class": source_class,
        "source_family": "company_product_evidence_graph",
        "runtime_source_family": "company_product_evidence_graph",
        "source_layer_id": "L1",
        "source_layer": "L1",
        "layer_id": "L1",
        "evidence_graph_status": "exact_authority_ready",
        "runtime_ready_context": True,
        "exact_value_authority": True,
        "can_support_company_exact_fact": True,
        "promotion_status": "runtime_fact_allowed",
        "parser_status": parser_status,
        "source_specific_parser": source_specific_parser,
        "structured_fact_status": "exact_fact_materialized",
        "bounded_structured_context": True,
        "structured_context_type": structured_context_type,
        "claim_types": claim_types,
        "allowed_claims": allowed_claims,
        "forbidden_claims": forbidden_claims,
        "authority_boundary": boundary,
        "claim_boundary": boundary,
        "runtime_use_boundary": boundary,
        "ticker": ticker,
        "company": source.get("company"),
        "product_or_segment": product,
        "product_family": product,
        "product_node_id": source.get("product_node_id"),
        "product_node_type": source.get("product_node_type"),
        "matched_product_alias": source.get("matched_product_alias"),
        "product_link_method": source.get("product_link_method"),
        "metric_family": metric_family,
        "metric_name": metric_name,
        "canonical_metric_id": canonical_metric_id,
        "value": value,
        "unit": unit,
        "unit_category": unit_category,
        "raw_value_text": source.get("raw_value_text"),
        "period": period,
        "fiscal_year": source.get("fiscal_year"),
        "row_label": source.get("row_label"),
        "column_label": source.get("column_label"),
        "citation_span": source.get("citation_sample") or source.get("citation_span"),
        "citation": {"url": source_url, "span": source.get("citation_sample") or source.get("citation_span")},
        "source_url": source_url,
        "snapshot_url": source_url,
        "source_document_id": source.get("source_document_id"),
        "source_candidate_id": source.get("fact_id"),
        "source_verifier_id": source.get("verifier_id"),
        "issuer_binding_status": "issuer_mentioned_in_snapshot",
        "product_binding_status": "product_mentioned_in_snapshot",
        "counterparty_binding_status": "not_bound",
        "entity_binding": {
            "schema_version": "finsight_public_web_entity_binding_v0_1",
            "issuer_ticker": ticker,
            "issuer_binding_status": "issuer_mentioned_in_snapshot",
            "product_binding_status": "product_mentioned_in_snapshot",
            "counterparty_binding_status": "not_bound",
            "product_matched_terms": [product],
            "source_entity_role": "company_disclosed_product_business_mix_metric",
            "binding_claim_boundary": boundary,
        },
        "text": text,
        "preview": text,
        "as_of_datetime": generated_at,
    }


def _rejection_row(source: Mapping[str, Any], reason: str, generated_at: str) -> dict[str, Any]:
    return {
        "schema_version": REJECTION_SCHEMA_VERSION,
        "generated_at": generated_at,
        "rejection_reason": reason,
        "ticker": source.get("ticker"),
        "company": source.get("company"),
        "fact_id": source.get("fact_id"),
        "verifier_id": source.get("verifier_id"),
        "product_or_segment": source.get("product_or_segment"),
        "metric_family": source.get("metric_family"),
        "unit": source.get("unit"),
        "unit_category": source.get("unit_category"),
        "raw_value_text": source.get("raw_value_text"),
        "row_label": source.get("row_label"),
        "column_label": source.get("column_label"),
        "source_url": source.get("source_url"),
    }


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
            if isinstance(value, dict):
                rows.append(value)
    return rows


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _stable_id(prefix: str, parts: Iterable[Any]) -> str:
    digest = hashlib.sha1("||".join(str(part or "") for part in parts).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}:{digest}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
