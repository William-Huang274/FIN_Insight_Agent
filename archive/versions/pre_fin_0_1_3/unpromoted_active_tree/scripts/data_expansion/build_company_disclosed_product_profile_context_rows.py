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

SCHEMA_VERSION = "finsight_company_disclosed_product_profile_context_rows_v0_1"
SUMMARY_SCHEMA_VERSION = "finsight_company_disclosed_product_profile_context_summary_v0_1"

DEFAULT_PRODUCT_PROFILE_INPUTS = [
    MANIFEST_DIR / "sec_product_taxonomy_context_rows_v0_1.jsonl",
    MANIFEST_DIR / "company_product_taxonomy_candidates_v0_1.jsonl",
    MANIFEST_DIR / "official_product_surface_context_rows_v0_1.jsonl",
    MANIFEST_DIR / "official_product_catalog_context_rows_v0_1.jsonl",
    MANIFEST_DIR / "targeted_regulated_auto_official_api_context_rows_v0_1.jsonl",
]
DEFAULT_OPERATING_PROFILE_INPUTS = [
    MANIFEST_DIR / "industry_operating_metric_slot_rows_v0_1.jsonl",
    MANIFEST_DIR / "company_reported_product_operating_metric_runtime_rows_v0_1.jsonl",
    MANIFEST_DIR / "non_us_product_kpi_local_disclosure_runtime_rows_v0_1.jsonl",
]
DEFAULT_OUTPUT_ROWS = MANIFEST_DIR / "company_disclosed_product_profile_context_rows_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY = MANIFEST_DIR / "company_disclosed_product_profile_context_summary_v0_1.json"

PASSING_PARSER_TOKENS = (
    "parser_pass",
    "projector_pass",
    "runtime_fact_allowed",
    "exact_fact_materialized",
    "bounded_context_fact_materialized",
)
ISSUER_BOUND_STATUSES = {"company_domain_bound", "issuer_mentioned_in_snapshot"}
PROFILE_NAME_NOISE = re.compile(
    r"\b("
    r"home|homepage|main|overview|about|investor|relations?|"
    r"contact|support|news|careers?|privacy|terms|resources?|search|login|"
    r"cookie|copyright|download|learn more|read more|history|risk factors?|"
    r"operations?|marketing|rates? and regulation"
    r")\b|새창|官网|中国",
    flags=re.IGNORECASE,
)
GENERIC_PROFILE_PREFIXES = ("general ", "mixed ", "unknown ")
GENERIC_PROFILE_NAMES = {
    "product",
    "products",
    "solution",
    "solutions",
    "product solution",
    "products solutions",
    "product specification context",
    "official product surface",
    "definitions of abbreviations",
    "federal and state regulatory agencies",
    "measurements",
    "where to find more information",
    "strategy",
}
OPERATING_PROFILE_METRIC_FAMILIES = {
    "aum",
    "capacity_utilization_or_production_volume",
    "deposits",
    "loan_balance",
    "patient_volume",
    "production_or_throughput",
    "shipments",
    "subscribers_or_arpu",
    "unit_sales_or_deliveries",
}
REJECTED_OPERATING_METRIC_FAMILIES = {
    "backlog_or_orders",
    "same_store_sales_growth",
}
PRODUCT_PROFILE_FROM_METRIC_FAMILIES = {
    "business_segment_revenue",
    "product_revenue",
    "segment_revenue",
    "segment_sales",
}
REGION_OR_AGGREGATE_PROFILE_NAMES = {
    "americas",
    "apac",
    "asia",
    "central",
    "company",
    "domestic",
    "east",
    "emea",
    "europe",
    "international",
    "north america",
    "other",
    "total",
    "u s",
    "us",
    "west",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Project strict company-disclosed product/service/business profile rows from official catalog, "
            "official/regulatory API identity rows, and non-revenue operating metrics."
        )
    )
    parser.add_argument("--product-profile-input", action="append", type=Path, default=[])
    parser.add_argument("--operating-profile-input", action="append", type=Path, default=[])
    parser.add_argument("--output-rows", type=Path, default=DEFAULT_OUTPUT_ROWS)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--max-product-profile-rows-per-ticker", type=int, default=12)
    parser.add_argument("--max-operating-profile-rows-per-ticker", type=int, default=8)
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    generated_at = _utc_now()
    product_inputs = args.product_profile_input or DEFAULT_PRODUCT_PROFILE_INPUTS
    operating_inputs = args.operating_profile_input or DEFAULT_OPERATING_PROFILE_INPUTS
    rows, diagnostics = build_company_disclosed_product_profile_context_rows(
        product_profile_rows=_load_rows_with_source_file(product_inputs),
        operating_profile_rows=_load_rows_with_source_file(operating_inputs),
        generated_at=generated_at,
        max_product_profile_rows_per_ticker=args.max_product_profile_rows_per_ticker,
        max_operating_profile_rows_per_ticker=args.max_operating_profile_rows_per_ticker,
    )
    summary = build_summary(rows=rows, diagnostics=diagnostics, generated_at=generated_at)
    _write_jsonl(args.output_rows, rows)
    _write_json(args.output_summary, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if args.strict and not rows:
        return 1
    return 0


def build_company_disclosed_product_profile_context_rows(
    *,
    product_profile_rows: Iterable[Mapping[str, Any]],
    operating_profile_rows: Iterable[Mapping[str, Any]],
    generated_at: str,
    max_product_profile_rows_per_ticker: int = 12,
    max_operating_profile_rows_per_ticker: int = 8,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    product_per_ticker = Counter()
    operating_per_ticker = Counter()
    diagnostics: dict[str, Any] = {
        "product_profile_input_count": 0,
        "operating_profile_input_count": 0,
        "product_profile_candidate_count": 0,
        "operating_profile_candidate_count": 0,
        "rejected_candidate_count": 0,
        "rejection_reasons": Counter(),
    }

    for source_row in product_profile_rows:
        diagnostics["product_profile_input_count"] += 1
        ticker = _ticker(source_row)
        if not ticker or product_per_ticker[ticker] >= max_product_profile_rows_per_ticker:
            continue
        reason = _reject_product_profile_source_row(source_row)
        if reason:
            diagnostics["rejected_candidate_count"] += 1
            diagnostics["rejection_reasons"][reason] += 1
            continue
        diagnostics["product_profile_candidate_count"] += 1
        row = _product_profile_row(source_row=source_row, generated_at=generated_at)
        key = _dedupe_key(row)
        if key in seen:
            continue
        seen.add(key)
        output.append(row)
        product_per_ticker[ticker] += 1

    for source_row in operating_profile_rows:
        diagnostics["operating_profile_input_count"] += 1
        ticker = _ticker(source_row)
        if not ticker or operating_per_ticker[ticker] >= max_operating_profile_rows_per_ticker:
            continue
        product_metric_reason = _reject_product_metric_profile_source_row(source_row)
        if not product_metric_reason:
            diagnostics["operating_profile_candidate_count"] += 1
            row = _product_profile_from_company_metric_row(source_row=source_row, generated_at=generated_at)
            key = _dedupe_key(row)
            if key in seen:
                continue
            seen.add(key)
            output.append(row)
            operating_per_ticker[ticker] += 1
            continue
        reason = _reject_operating_profile_source_row(source_row)
        if reason:
            diagnostics["rejected_candidate_count"] += 1
            diagnostics["rejection_reasons"][
                product_metric_reason if _metric_family(source_row) in PRODUCT_PROFILE_FROM_METRIC_FAMILIES else reason
            ] += 1
            continue
        diagnostics["operating_profile_candidate_count"] += 1
        row = _business_profile_row(source_row=source_row, generated_at=generated_at)
        key = _dedupe_key(row)
        if key in seen:
            continue
        seen.add(key)
        output.append(row)
        operating_per_ticker[ticker] += 1

    diagnostics["rejection_reasons"] = dict(sorted(diagnostics["rejection_reasons"].items()))
    return (
        sorted(output, key=lambda row: (str(row["ticker"]), str(row["source_role"]), str(row["product_or_segment"]))),
        diagnostics,
    )


def build_summary(
    *,
    rows: list[Mapping[str, Any]],
    diagnostics: Mapping[str, Any],
    generated_at: str,
) -> dict[str, Any]:
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "pass" if rows else "gap",
        "row_count": len(rows),
        "ticker_count": len({_ticker(row) for row in rows if _ticker(row)}),
        "by_source_role": _counts(rows, "source_role"),
        "by_runtime_contract": _counts(rows, "runtime_contract"),
        "by_profile_type": _counts(rows, "profile_type"),
        "rows_by_ticker_top30": _counts(rows, "ticker", limit=30),
        "diagnostics": dict(diagnostics),
        "authority_boundary": (
            "Rows are bounded ProductProfileSlot or BusinessProfileSlot context. They support product/service/asset/"
            "operating-profile analysis, but do not prove revenue, ASP, market share, sell-through, inventory, "
            "backlog, customer order value, or commercial tracker exactness."
        ),
    }


def _reject_product_profile_source_row(row: Mapping[str, Any]) -> str:
    if _ticker(row) == "":
        return "missing_ticker"
    source_file = str(row.get("_source_file") or "")
    if (
        source_file != "company_product_taxonomy_candidates_v0_1.jsonl"
        and str(row.get("issuer_binding_status") or "") not in ISSUER_BOUND_STATUSES
    ):
        return "issuer_not_bound"
    if source_file != "company_product_taxonomy_candidates_v0_1.jsonl" and not _parser_passed(row):
        return "parser_not_passed"
    if not str(row.get("source_url") or row.get("url") or "").strip():
        return "missing_source_url"
    source_id = str(row.get("source_id") or row.get("underlying_source_id") or "")
    requirement_id = str(row.get("requirement_id") or row.get("source_role") or "")
    supported_source = (
        source_file == "sec_product_taxonomy_context_rows_v0_1.jsonl"
        or (
            source_file == "company_product_taxonomy_candidates_v0_1.jsonl"
            and _candidate_row_has_projectable_profile(row)
        )
        or source_file == "official_product_catalog_context_rows_v0_1.jsonl"
        or (
            source_file == "official_product_surface_context_rows_v0_1.jsonl"
            and _surface_row_has_product_family(row)
        )
        or requirement_id in {"regulated_product_context", "auto_product_identity_context"}
        or source_id in {"clinicaltrials_api", "openfda_api", "nhtsa_vpic_api", "fda_animal_drugs_api"}
    )
    if not supported_source:
        return "unsupported_product_profile_source"
    name = _profile_name(row)
    family = str(row.get("product_family") or "").strip()
    company = str(row.get("company") or row.get("company_name") or "").strip()
    allow_same_family = (
        requirement_id in {"regulated_product_context", "auto_product_identity_context"}
        or source_id in {"clinicaltrials_api", "openfda_api", "nhtsa_vpic_api", "fda_animal_drugs_api"}
        or source_file == "official_product_catalog_context_rows_v0_1.jsonl"
        or source_file == "official_product_surface_context_rows_v0_1.jsonl"
        or source_file == "sec_product_taxonomy_context_rows_v0_1.jsonl"
        or source_file == "company_product_taxonomy_candidates_v0_1.jsonl"
    )
    min_name_length = 2 if source_id == "nhtsa_vpic_api" or requirement_id == "auto_product_identity_context" else 3
    if _bad_profile_name(
        name,
        family=family,
        company=company,
        allow_same_family=allow_same_family,
        min_name_length=min_name_length,
    ):
        return "weak_or_navigation_product_profile_name"
    return ""


def _reject_operating_profile_source_row(row: Mapping[str, Any]) -> str:
    if _ticker(row) == "":
        return "missing_ticker"
    if not _parser_passed(row):
        return "parser_not_passed"
    if not str(row.get("source_url") or row.get("url") or row.get("snapshot_url") or "").strip():
        return "missing_source_url"
    if not str(row.get("period") or row.get("fiscal_year") or "").strip():
        return "missing_period"
    if not str(row.get("value") or "").strip():
        return "missing_value"
    if not str(row.get("unit") or "").strip():
        return "missing_unit"
    family = _metric_family(row)
    if family in REJECTED_OPERATING_METRIC_FAMILIES:
        return "metric_family_is_kpi_or_revenue_not_profile"
    if family in PRODUCT_PROFILE_FROM_METRIC_FAMILIES:
        return "metric_family_is_product_or_segment_identity_profile_not_operating_profile"
    if family not in OPERATING_PROFILE_METRIC_FAMILIES:
        return "metric_family_not_supported_for_profile"
    product = str(row.get("product_or_segment") or row.get("row_label") or "").strip()
    if _bad_profile_name(product, family="", company=str(row.get("company") or row.get("company_name") or "")):
        return "weak_or_navigation_operating_profile_name"
    return ""


def _reject_product_metric_profile_source_row(row: Mapping[str, Any]) -> str:
    if _ticker(row) == "":
        return "missing_ticker"
    if not _parser_passed(row):
        return "parser_not_passed"
    if not str(row.get("source_url") or row.get("url") or row.get("snapshot_url") or "").strip():
        return "missing_source_url"
    family = _metric_family(row)
    if family not in PRODUCT_PROFILE_FROM_METRIC_FAMILIES:
        return "metric_family_not_product_or_segment_identity_profile"
    product = str(row.get("product_or_segment") or row.get("row_label") or "").strip()
    if _bad_profile_name(
        product,
        family=str(row.get("product_family") or ""),
        company=str(row.get("company") or row.get("company_name") or ""),
        allow_same_family=True,
    ):
        return "weak_or_navigation_product_metric_profile_name"
    if _normalized_key(product) in REGION_OR_AGGREGATE_PROFILE_NAMES:
        return "region_or_aggregate_product_metric_profile_name"
    if re.search(r"\b(total|consolidated|eliminations?|adjustments?)\b", product, flags=re.IGNORECASE):
        return "region_or_aggregate_product_metric_profile_name"
    return ""


def _product_profile_row(*, source_row: Mapping[str, Any], generated_at: str) -> dict[str, Any]:
    ticker = _ticker(source_row)
    name = _profile_name(source_row)
    family = _profile_family(source_row, profile_name=name)
    source_url = str(source_row.get("source_url") or source_row.get("url") or source_row.get("snapshot_url") or "").strip()
    profile_type = _product_profile_type(source_row)
    evidence_ref = "company_product_profile:" + hashlib.sha1(
        f"{ticker}|{source_url}|{profile_type}|{name}|{family}".encode("utf-8")
    ).hexdigest()[:16]
    text = f"{ticker} official product/service profile: {name}"
    if family:
        text += f" ({family})"
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "ticker": ticker,
        "company": source_row.get("company") or source_row.get("company_name") or "",
        "company_name": source_row.get("company") or source_row.get("company_name") or "",
        "evidence_ref": evidence_ref,
        "evidence_id": evidence_ref,
        "source_role": "official_product_profile_spec",
        "runtime_contract": "ProductProfileSlot",
        "structured_context_type": "official_product_profile_spec",
        "structured_fact_status": "bounded_context_fact_materialized",
        "parser_status": "source_specific_context_parser_pass",
        "source_id": "official_product_profile_parser",
        "underlying_source_id": source_row.get("source_id") or source_row.get("underlying_source_id") or "",
        "source_family": source_row.get("source_family") or "public_source_context",
        "runtime_source_family": "public_source_context",
        "source_layer": source_row.get("source_layer") or source_row.get("source_layer_id") or "L2",
        "source_layer_id": source_row.get("source_layer_id") or source_row.get("source_layer") or "L2",
        "layer_id": source_row.get("layer_id") or "L2",
        "source_class": source_row.get("source_class") or "company_official_product_profile",
        "source_specific_parser": "company_disclosed_product_profile_projector_v0_1",
        "source_url": source_url,
        "url": source_url,
        "raw_path": source_row.get("raw_path") or "",
        "citation": source_row.get("citation") or {"title": source_row.get("source_title") or "", "url": source_url},
        "citation_span": source_row.get("citation_span") or source_row.get("preview") or text,
        "profile_type": profile_type,
        "metric_name": "product_or_service_profile",
        "product_or_segment": name,
        "product_family": family,
        "profile_value": name,
        "issuer_binding_status": source_row.get("issuer_binding_status") or "issuer_mentioned_in_snapshot",
        "product_binding_status": source_row.get("product_binding_status") or "product_mentioned_in_snapshot",
        "bounded_structured_context": True,
        "context_only": True,
        "exact_value_authority": False,
        "can_support_company_exact_fact": False,
        "allowed_claims": ["official_product_profile_context", "product_identity_context", "product_spec_context"],
        "claim_types": ["official_product_profile_context", "product_identity_context"],
        "forbidden_claims": [
            "product_revenue",
            "sku_revenue",
            "sales",
            "unit_sales",
            "shipments",
            "ASP",
            "market_share",
            "sell_through",
            "inventory",
            "backlog",
            "customer_order_value",
        ],
        "claim_boundary": (
            "Official product/service/profile identity context only; no revenue, sales, ASP, market-share, "
            "inventory, sell-through, backlog, customer order value, or shipment authority."
        ),
        "authority_boundary": (
            "Official product/service/profile identity context only; no revenue, sales, ASP, market-share, "
            "inventory, sell-through, backlog, customer order value, or shipment authority."
        ),
        "evidence_graph_status": "runtime_ready_context",
        "preview": text,
        "text": text,
        "parent_evidence_ref": source_row.get("evidence_ref") or source_row.get("evidence_id") or "",
    }


def _business_profile_row(*, source_row: Mapping[str, Any], generated_at: str) -> dict[str, Any]:
    ticker = _ticker(source_row)
    metric_family = _metric_family(source_row)
    metric_name = str(source_row.get("metric_name") or source_row.get("slot_id") or metric_family).strip()
    product = str(source_row.get("product_or_segment") or source_row.get("row_label") or metric_name).strip()
    source_url = str(source_row.get("source_url") or source_row.get("url") or source_row.get("snapshot_url") or "").strip()
    value = source_row.get("value")
    unit = source_row.get("unit")
    period = source_row.get("period") or source_row.get("fiscal_year") or ""
    evidence_ref = "company_business_profile:" + hashlib.sha1(
        f"{ticker}|{source_url}|{metric_family}|{metric_name}|{product}|{period}|{value}|{unit}".encode("utf-8")
    ).hexdigest()[:16]
    text = f"{ticker} company-disclosed business/service operating profile: {product} {metric_name}={value} {unit} for {period}."
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "ticker": ticker,
        "company": source_row.get("company") or source_row.get("company_name") or "",
        "company_name": source_row.get("company") or source_row.get("company_name") or "",
        "evidence_ref": evidence_ref,
        "evidence_id": evidence_ref,
        "source_role": "business_service_profile_spec",
        "runtime_contract": "BusinessProfileSlot",
        "structured_context_type": "business_service_profile_spec",
        "structured_fact_status": "bounded_context_fact_materialized",
        "parser_status": "source_specific_context_parser_pass",
        "source_id": "company_disclosed_business_service_profile_projector",
        "underlying_source_id": source_row.get("source_id") or source_row.get("underlying_source_id") or "",
        "source_family": source_row.get("source_family") or "company_product_evidence_graph",
        "runtime_source_family": "company_product_evidence_graph",
        "source_layer": source_row.get("source_layer") or source_row.get("source_layer_id") or "L1",
        "source_layer_id": source_row.get("source_layer_id") or source_row.get("source_layer") or "L1",
        "layer_id": source_row.get("layer_id") or "L1",
        "source_class": source_row.get("source_class") or "company_disclosed_operating_profile",
        "source_specific_parser": "company_disclosed_product_profile_projector_v0_1",
        "source_url": source_url,
        "url": source_url,
        "raw_path": source_row.get("raw_path") or "",
        "citation": source_row.get("citation") or {"span": source_row.get("citation_span") or "", "url": source_url},
        "citation_span": source_row.get("citation_span") or source_row.get("preview") or text,
        "profile_type": "company_disclosed_operating_profile",
        "metric_family": metric_family,
        "metric_name": metric_name,
        "value": value,
        "unit": unit,
        "period": period,
        "product_or_segment": product,
        "product_family": source_row.get("product_family") or product,
        "profile_value": f"{metric_name}: {value} {unit}",
        "issuer_binding_status": source_row.get("issuer_binding_status") or "issuer_mentioned_in_snapshot",
        "product_binding_status": source_row.get("product_binding_status") or "segment_or_metric_mentioned_in_snapshot",
        "bounded_structured_context": True,
        "context_only": True,
        "exact_value_authority": False,
        "can_support_company_exact_fact": False,
        "allowed_claims": ["business_service_profile_context", "operating_profile_context", "product_spec_context"],
        "claim_types": ["business_service_profile_context", "operating_profile_context"],
        "forbidden_claims": [
            "product_revenue",
            "sku_revenue",
            "ASP",
            "market_share",
            "sell_through",
            "inventory",
            "backlog",
            "customer_order_value",
            "commercial_tracker_estimate",
        ],
        "claim_boundary": (
            "Company-disclosed operating profile context only. It may describe scale, capacity, volume, or service "
            "profile for the cited row, but it does not authorize product revenue, ASP, market share, sell-through, "
            "inventory, backlog, or customer order value claims."
        ),
        "authority_boundary": (
            "Company-disclosed operating profile context only. It may describe scale, capacity, volume, or service "
            "profile for the cited row, but it does not authorize product revenue, ASP, market share, sell-through, "
            "inventory, backlog, or customer order value claims."
        ),
        "evidence_graph_status": "runtime_ready_context",
        "preview": text,
        "text": text,
        "parent_evidence_ref": source_row.get("evidence_ref") or source_row.get("evidence_id") or "",
    }


def _product_profile_from_company_metric_row(*, source_row: Mapping[str, Any], generated_at: str) -> dict[str, Any]:
    ticker = _ticker(source_row)
    metric_family = _metric_family(source_row)
    product = str(source_row.get("product_or_segment") or source_row.get("row_label") or "").strip()
    source_url = str(source_row.get("source_url") or source_row.get("url") or source_row.get("snapshot_url") or "").strip()
    period = source_row.get("period") or source_row.get("fiscal_year") or ""
    evidence_ref = "company_metric_product_profile:" + hashlib.sha1(
        f"{ticker}|{source_url}|{metric_family}|{product}|{period}".encode("utf-8")
    ).hexdigest()[:16]
    text = f"{ticker} company-disclosed product/business-line profile from metric row: {product}."
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "ticker": ticker,
        "company": source_row.get("company") or source_row.get("company_name") or "",
        "company_name": source_row.get("company") or source_row.get("company_name") or "",
        "evidence_ref": evidence_ref,
        "evidence_id": evidence_ref,
        "source_role": "official_product_profile_spec",
        "runtime_contract": "ProductProfileSlot",
        "structured_context_type": "official_product_profile_spec",
        "structured_fact_status": "bounded_context_fact_materialized",
        "parser_status": "source_specific_context_parser_pass",
        "source_id": "company_disclosed_product_metric_profile_projector",
        "underlying_source_id": source_row.get("source_id") or source_row.get("underlying_source_id") or "",
        "source_family": source_row.get("source_family") or "company_product_evidence_graph",
        "runtime_source_family": "company_product_evidence_graph",
        "source_layer": source_row.get("source_layer") or source_row.get("source_layer_id") or "L1",
        "source_layer_id": source_row.get("source_layer_id") or source_row.get("source_layer") or "L1",
        "layer_id": source_row.get("layer_id") or "L1",
        "source_class": source_row.get("source_class") or "company_disclosed_product_metric_profile",
        "source_specific_parser": "company_disclosed_product_profile_projector_v0_1",
        "source_url": source_url,
        "url": source_url,
        "raw_path": source_row.get("raw_path") or "",
        "citation": source_row.get("citation") or {"span": source_row.get("citation_span") or "", "url": source_url},
        "citation_span": source_row.get("citation_span") or source_row.get("preview") or text,
        "profile_type": "company_disclosed_product_or_segment_metric_profile",
        "metric_family": metric_family,
        "metric_name": "product_or_business_line_profile",
        "period": period,
        "product_or_segment": product,
        "product_family": source_row.get("product_family") or product,
        "profile_value": product,
        "issuer_binding_status": source_row.get("issuer_binding_status") or "issuer_mentioned_in_snapshot",
        "product_binding_status": source_row.get("product_binding_status") or "segment_or_metric_mentioned_in_snapshot",
        "bounded_structured_context": True,
        "context_only": True,
        "exact_value_authority": False,
        "can_support_company_exact_fact": False,
        "allowed_claims": ["official_product_profile_context", "company_disclosed_product_line_identity"],
        "claim_types": ["official_product_profile_context", "company_disclosed_product_line_identity"],
        "forbidden_claims": [
            "product_revenue",
            "sku_revenue",
            "sales",
            "unit_sales",
            "shipments",
            "ASP",
            "market_share",
            "sell_through",
            "inventory",
            "backlog",
            "customer_order_value",
            "commercial_tracker_estimate",
        ],
        "claim_boundary": (
            "Company-disclosed metric row is used only to identify the product, service, or business-line profile. "
            "This projected profile row does not carry the source value and must not be used for product revenue, "
            "sales, ASP, market share, inventory, sell-through, backlog, customer order value, or shipment claims."
        ),
        "authority_boundary": (
            "Company-disclosed metric row is used only to identify the product, service, or business-line profile. "
            "This projected profile row does not carry the source value and must not be used for product revenue, "
            "sales, ASP, market share, inventory, sell-through, backlog, customer order value, or shipment claims."
        ),
        "evidence_graph_status": "runtime_ready_context",
        "preview": text,
        "text": text,
        "parent_evidence_ref": source_row.get("evidence_ref") or source_row.get("evidence_id") or "",
    }


def _product_profile_type(row: Mapping[str, Any]) -> str:
    requirement_id = str(row.get("requirement_id") or row.get("source_role") or "")
    source_id = str(row.get("source_id") or row.get("underlying_source_id") or "")
    if requirement_id == "auto_product_identity_context" or source_id == "nhtsa_vpic_api":
        return "regulated_vehicle_model_profile"
    if requirement_id == "regulated_product_context" or source_id in {
        "clinicaltrials_api",
        "openfda_api",
        "fda_animal_drugs_api",
    }:
        return "regulated_product_or_trial_profile"
    if str(row.get("_source_file") or "") == "sec_product_taxonomy_context_rows_v0_1.jsonl":
        return "sec_filings_product_taxonomy_profile"
    if str(row.get("_source_file") or "") == "company_product_taxonomy_candidates_v0_1.jsonl":
        return "company_filing_taxonomy_candidate_profile"
    if str(row.get("_source_file") or "") == "official_product_surface_context_rows_v0_1.jsonl":
        return "official_product_surface_category_profile"
    return "official_product_catalog_profile"


def _profile_name(row: Mapping[str, Any]) -> str:
    if str(row.get("_source_file") or "") == "company_product_taxonomy_candidates_v0_1.jsonl":
        projected = _project_taxonomy_candidate_profile_name(row)
        if projected:
            return projected
    return str(
        row.get("product_or_segment")
        or row.get("fact_label")
        or row.get("model")
        or row.get("product_family")
        or row.get("topic")
        or ""
    ).strip()


def _profile_family(row: Mapping[str, Any], *, profile_name: str) -> str:
    family = str(row.get("product_family") or row.get("topic") or "").strip()
    if family:
        return family
    if str(row.get("_source_file") or "") == "company_product_taxonomy_candidates_v0_1.jsonl":
        text = f"{profile_name} {row.get('evidence_snippet') or ''}".lower()
        if "electric" in text and ("natural gas" in text or "gas" in text or "utility" in text):
            return "Regulated Utility / Power"
    return ""


def _bad_profile_name(
    name: str,
    *,
    family: str,
    company: str,
    allow_same_family: bool = False,
    min_name_length: int = 3,
) -> bool:
    clean = str(name or "").strip()
    if len(clean) < min_name_length or len(clean) > 180:
        return True
    if clean.lower().startswith(GENERIC_PROFILE_PREFIXES):
        return True
    if _normalized_key(clean) in GENERIC_PROFILE_NAMES:
        return True
    if "official product surface" in clean.lower() or "product specification context" in clean.lower():
        return True
    if PROFILE_NAME_NOISE.search(clean):
        return True
    if re.search(r"https?://|www\.|\.com\b|\.html?\b", clean, flags=re.IGNORECASE):
        return True
    normalized_name = _normalized_key(clean)
    normalized_family = _normalized_key(family)
    normalized_company = _normalized_key(company)
    if normalized_name and normalized_name == normalized_family and not allow_same_family:
        return True
    name_words = normalized_name.split()
    if (
        normalized_name
        and normalized_company
        and (normalized_name == normalized_company or (len(name_words) >= 2 and normalized_company.startswith(normalized_name)))
    ):
        return True
    return False


def _surface_row_has_product_family(row: Mapping[str, Any]) -> bool:
    family = str(row.get("product_family") or row.get("fact_label") or "").strip()
    if not family:
        return False
    if family.lower().startswith(GENERIC_PROFILE_PREFIXES):
        return False
    if PROFILE_NAME_NOISE.search(family):
        return False
    return True


def _candidate_row_has_projectable_profile(row: Mapping[str, Any]) -> bool:
    if str(row.get("source_id") or "") != "company_product_taxonomy_candidates":
        return False
    return bool(_project_taxonomy_candidate_profile_name(row))


def _project_taxonomy_candidate_profile_name(row: Mapping[str, Any]) -> str:
    label = str(row.get("taxonomy_label") or "").strip()
    snippet = str(row.get("evidence_snippet") or "")
    normalized_label = _normalized_key(label)
    if normalized_label in GENERIC_PROFILE_NAMES or PROFILE_NAME_NOISE.search(label):
        label = ""
    lower = snippet.lower()
    if (
        ("utility subsidiary overview" in lower or "utility subsidiaries" in lower)
        and "electric" in lower
        and ("gas" in lower or "natural gas" in lower)
    ):
        return "Electric & Gas utility service"
    if "electric generating capacity" in lower and "natural gas" in lower:
        return "Electric generation and natural gas utility network"
    return label


def _parser_passed(row: Mapping[str, Any]) -> bool:
    parser_status = str(row.get("parser_status") or row.get("structured_fact_status") or row.get("promotion_status") or "")
    return any(token in parser_status for token in PASSING_PARSER_TOKENS) or row.get("runtime_ready_context") is True


def _metric_family(row: Mapping[str, Any]) -> str:
    return str(row.get("metric_family") or row.get("slot_metric_family") or row.get("source_metric_family") or "").strip()


def _ticker(row: Mapping[str, Any]) -> str:
    return str(row.get("ticker") or row.get("symbol") or "").upper().strip()


def _dedupe_key(row: Mapping[str, Any]) -> str:
    return "::".join(
        [
            str(row.get("ticker") or ""),
            str(row.get("source_role") or ""),
            str(row.get("profile_type") or ""),
            str(row.get("product_or_segment") or ""),
            str(row.get("metric_name") or ""),
            str(row.get("period") or ""),
            str(row.get("value") or ""),
        ]
    ).lower()


def _normalized_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _counts(rows: Iterable[Mapping[str, Any]], key: str, *, limit: int = 50) -> dict[str, int]:
    counter = Counter(str(row.get(key) or "") for row in rows)
    return dict(counter.most_common(limit))


def _load_rows_with_source_file(paths: Iterable[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        if not path.exists():
            continue
        for row in _load_jsonl(path):
            clean = dict(row)
            clean["_source_file"] = path.name
            rows.append(clean)
    return rows


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
