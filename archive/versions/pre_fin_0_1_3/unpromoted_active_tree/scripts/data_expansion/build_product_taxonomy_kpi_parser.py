from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]

SUMMARY_SCHEMA_VERSION = "fin_agent_product_taxonomy_kpi_parser_summary_v0.1"
NORMALIZED_TAXONOMY_SCHEMA_VERSION = "fin_agent_company_product_taxonomy_normalized_v0.1"
TAXONOMY_ALIAS_SCHEMA_VERSION = "fin_agent_company_product_taxonomy_alias_v0.1"
TAXONOMY_REVIEW_SCHEMA_VERSION = "fin_agent_company_product_taxonomy_review_queue_v0.1"
KPI_FACT_SCHEMA_VERSION = "fin_agent_company_product_kpi_parser_verified_fact_v0.1"
KPI_REJECTION_SCHEMA_VERSION = "fin_agent_company_product_kpi_rejection_v0.1"

DEFAULT_RULES_CONFIG = REPO_ROOT / "configs" / "data_sources" / "product_taxonomy_normalization_rules_v0_1.yaml"
DEFAULT_TAXONOMY_CANDIDATES = REPO_ROOT / "data" / "manifests" / "company_product_taxonomy_candidates_v0_1.jsonl"
DEFAULT_METRIC_CANDIDATES = REPO_ROOT / "data" / "manifests" / "company_product_metric_candidates_balanced_v0_1.jsonl"
DEFAULT_UNIVERSE_MANIFEST = REPO_ROOT / "data" / "manifests" / "tier1_tier2_market_universe_v0_1.csv"
DEFAULT_SECTOR_DEPTH_CONFIG = REPO_ROOT / "configs" / "sector_depth_full238_us_v0_2_10k_fy2023_2025.yaml"
DEFAULT_METRIC_ONTOLOGY = REPO_ROOT / "configs" / "data_sources" / "company_product_operating_metric_ontology_v0_1.yaml"
DEFAULT_CHUNK_INPUTS = [
    REPO_ROOT / "data" / "staging" / "sec_tier1_sp500_annual" / "chunks" / "tier1_sp500_us_annual_10k_chunks_fy2023_2025_v0_1.jsonl",
    REPO_ROOT / "data" / "staging" / "sec_tier2_supply_chain_annual" / "chunks" / "tier2_supply_chain_sec_annual_chunks_fy2023_2025_v0_1.jsonl",
]
DEFAULT_STRUCTURED_OBJECT_SQLITES = [
    REPO_ROOT
    / "data"
    / "indexes"
    / "staging"
    / "sqlite_fts"
    / "tier1_sp500_us_annual_10k_objects_fy2023_2025_v0_1"
    / "records.sqlite",
    REPO_ROOT
    / "data"
    / "indexes"
    / "staging"
    / "sqlite_fts"
    / "tier2_supply_chain_sec_annual_objects_fy2023_2025_v0_1"
    / "records.sqlite",
]

DEFAULT_NORMALIZED_TAXONOMY_OUTPUT = REPO_ROOT / "data" / "manifests" / "company_product_taxonomy_normalized_v0_1.jsonl"
DEFAULT_TAXONOMY_ALIASES_OUTPUT = REPO_ROOT / "data" / "manifests" / "company_product_taxonomy_aliases_v0_1.jsonl"
DEFAULT_TAXONOMY_REVIEW_OUTPUT = REPO_ROOT / "data" / "manifests" / "company_product_taxonomy_review_queue_v0_1.jsonl"
DEFAULT_KPI_FACTS_OUTPUT = REPO_ROOT / "data" / "manifests" / "company_product_kpi_facts_parser_verified_v0_1.jsonl"
DEFAULT_KPI_REJECTIONS_OUTPUT = REPO_ROOT / "data" / "manifests" / "company_product_kpi_rejections_v0_1.jsonl"
DEFAULT_SUMMARY_OUTPUT = REPO_ROOT / "data" / "manifests" / "company_product_taxonomy_kpi_parser_summary_v0_1.json"
DEFAULT_REPORT_OUTPUT = REPO_ROOT / "docs" / "internal" / "vnext_20260610" / "product_taxonomy_kpi_parser_execution.zh-CN.md"

METRIC_KEYWORDS = {
    "product_revenue": [
        "product revenue",
        "net sales",
        "revenue",
        "sales",
        "segment revenue",
        "franchise revenue",
    ],
    "unit_sales_or_deliveries": ["deliveries", "delivered", "unit sales", "units sold", "vehicles delivered"],
    "shipments": ["shipments", "shipped", "shipped volume"],
    "backlog_or_orders": ["backlog", "orders", "bookings", "remaining performance obligations", "rpo"],
    "subscribers_or_arpu": ["subscribers", "paid subscribers", "arpu", "average revenue per user", "accounts"],
    "same_store_sales": ["same-store sales", "comparable sales", "comparable store sales", "comps"],
    "production_or_throughput": ["production", "throughput", "produced", "utilization"],
}

UNIT_CATEGORY_BY_OUTPUT_UNIT = {
    "USD": "currency",
    "percent_of_revenue": "percent_of_revenue",
    "percent": "percent",
    "percent_change": "percent",
    "vehicles": "vehicles",
    "units": "units",
    "devices": "devices",
    "systems": "systems",
    "subscribers": "subscribers",
    "accounts": "accounts",
    "barrels_per_day": "barrels_per_day",
    "barrels": "barrels",
    "tons": "tons",
    "metric_tons": "metric tons",
    "megawatt_hours": "megawatt_hours",
    "months": "months",
}

STRUCTURED_CURRENCY_UNIT_FACTORS = {
    "usd_thousands": ("thousand", 1_000.0),
    "usd_millions": ("million", 1_000_000.0),
    "usd_billions": ("billion", 1_000_000_000.0),
}

SCALE_FACTORS = {
    "thousand": 1_000.0,
    "thousands": 1_000.0,
    "million": 1_000_000.0,
    "millions": 1_000_000.0,
    "billion": 1_000_000_000.0,
    "billions": 1_000_000_000.0,
}

GENERIC_ALIAS_TERMS = {
    "business",
    "businesses",
    "product",
    "products",
    "service",
    "services",
    "solution",
    "solutions",
    "platform",
    "platforms",
    "market",
    "markets",
    "customer",
    "customers",
    "sales",
    "revenue",
    "net sales",
}

GENERIC_STRUCTURED_PRODUCT_LABELS = GENERIC_ALIAS_TERMS | {
    "total",
    "totals",
    "total revenues",
    "total revenue",
    "total net sales",
    "total sales",
    "revenue",
    "revenues",
    "net revenue",
    "net revenues",
    "net sales",
    "sales",
    "gross margin",
    "gross profit",
    "operating income",
    "operating profit",
    "operating expenses",
    "income before income taxes",
    "income tax expense",
    "net income",
    "total assets",
    "total liabilities",
    "cash flows",
    "cash and cash equivalents",
    "deferred revenue",
    "contract assets",
    "contract liabilities",
    "goodwill",
    "research and development",
    "acquisition termination cost",
    "income before",
    "other net",
    "operating margin",
    "margin",
    "cost",
    "costs",
    "loss from operations",
    "remaining performance obligations",
    "rpo",
    "rebates",
    "deferred",
    "thereafter",
    "non-current",
    "current",
    "revenue per",
    "as a percentage",
    "percentage of",
    "total change",
    "comparable sales",
}

STRUCTURED_REPAIR_FORBIDDEN_LABEL_TERMS = (
    "marketable securities",
    "cash equivalents",
    "proceeds from",
    "purchases of",
    "maturities of",
    "depreciation",
    "amortization",
    "income taxes",
    "tax expense",
    "tax benefit",
    "deferred tax",
    "interest expense",
    "interest income",
    "sales and marketing",
    "marketing expense",
    "payroll",
    "expense",
    "expenses",
    "charges to",
    "increase in",
    "decrease in",
    "primarily due",
    "investing activities",
    "operating activities",
    "financing activities",
    "property and equipment",
    "approximately",
    "totaled",
    "based on",
    "gross sales",
    "charged against",
    "metric",
    "was approximately",
    "were approximately",
    "of which",
    "accounts receivable",
    "accounts payable",
    "accrued expenses",
    "lease liabilities",
    "operating lease",
    "finance lease",
    "shareholders' equity",
    "stockholders' equity",
    "retained earnings",
    "treasury stock",
    "common stock",
    "comprehensive income",
    "unrealized gains",
    "unrealized losses",
)

STRUCTURED_REVENUE_CONTEXT_PATTERNS = (
    r"\brevenue(?:s)?\s+(?:by|from|of|for)\b",
    r"\bnet sales\s+(?:by|from|of|for)\b",
    r"\bsales\s+(?:by|from|of|for)\b",
    r"\bsegment sales\b",
    r"\bsegment revenue(?:s)?\b",
    r"\bsales and operating income\b",
    r"\brevenue disaggregated\b",
    r"\bdisaggregated revenue\b",
    r"\brevenue by (?:major )?(?:product|service|segment|category|geography|region)",
    r"\bnet sales by (?:product|service|segment|category|geography|region|merchandise)",
    r"\bsales by (?:product|service|segment|category|geography|region|brand|restaurant)",
)

STRUCTURED_NON_REVENUE_CONTEXT_PATTERNS = (
    r"\bbalance sheet\b",
    r"\bcash flow(?:s)?\b",
    r"\bderivative instruments?\b",
    r"\bfair value\b",
    r"\bgoodwill\b",
    r"\bimpairment\b",
    r"\bincome tax(?:es)?\b",
    r"\bdeferred tax(?:es)?\b",
    r"\bequity\b",
    r"\bcomprehensive income\b",
    r"\bcontract liabilities?\b",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize product taxonomy and parse parser-verified product KPI facts.")
    parser.add_argument("--rules-config", type=Path, default=DEFAULT_RULES_CONFIG)
    parser.add_argument("--taxonomy-candidates", type=Path, default=DEFAULT_TAXONOMY_CANDIDATES)
    parser.add_argument("--metric-candidates", type=Path, default=DEFAULT_METRIC_CANDIDATES)
    parser.add_argument("--universe-manifest", type=Path, default=DEFAULT_UNIVERSE_MANIFEST)
    parser.add_argument("--sector-depth-config", type=Path, default=DEFAULT_SECTOR_DEPTH_CONFIG)
    parser.add_argument("--metric-ontology", type=Path, default=DEFAULT_METRIC_ONTOLOGY)
    parser.add_argument("--chunk-input", type=Path, action="append", default=[])
    parser.add_argument("--enable-direct-chunk-kpi-scan", action="store_true")
    parser.add_argument("--max-direct-windows-per-chunk", type=int, default=3)
    parser.add_argument("--structured-object-sqlite", type=Path, action="append", default=[])
    parser.add_argument("--enable-structured-metric-kpi-scan", action="store_true")
    parser.add_argument("--structured-taxonomy-repair-reference-facts", type=Path, action="append", default=[])
    parser.add_argument("--enable-structured-table-taxonomy-repair", action="store_true")
    parser.add_argument("--normalized-taxonomy-output", type=Path, default=DEFAULT_NORMALIZED_TAXONOMY_OUTPUT)
    parser.add_argument("--taxonomy-aliases-output", type=Path, default=DEFAULT_TAXONOMY_ALIASES_OUTPUT)
    parser.add_argument("--taxonomy-review-output", type=Path, default=DEFAULT_TAXONOMY_REVIEW_OUTPUT)
    parser.add_argument("--kpi-facts-output", type=Path, default=DEFAULT_KPI_FACTS_OUTPUT)
    parser.add_argument("--kpi-rejections-output", type=Path, default=DEFAULT_KPI_REJECTIONS_OUTPUT)
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_SUMMARY_OUTPUT)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT_OUTPUT)
    parser.add_argument("--max-citation-chars", type=int, default=560)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at = datetime.now(timezone.utc).isoformat()
    rules_path = _resolve(args.rules_config)
    taxonomy_path = _resolve(args.taxonomy_candidates)
    metric_path = _resolve(args.metric_candidates)
    universe_path = _resolve(args.universe_manifest)
    sector_depth_path = _resolve(args.sector_depth_config)
    ontology_path = _resolve(args.metric_ontology)

    rules = _load_yaml(rules_path)
    universe_index = load_universe_index(universe_path, sector_depth_path)
    taxonomy_candidates = list(_iter_jsonl(taxonomy_path))
    normalized_rows, alias_rows, review_rows = normalize_taxonomy_candidates(
        taxonomy_candidates,
        rules=rules,
        universe_index=universe_index,
        generated_at=generated_at,
    )
    metric_candidates = list(_iter_jsonl(metric_path))
    ontology = _load_yaml(ontology_path)
    direct_metric_candidates: list[dict[str, Any]] = []
    chunk_inputs = [_resolve(path) for path in (args.chunk_input or DEFAULT_CHUNK_INPUTS)]
    structured_sqlite_inputs = [_resolve(path) for path in (args.structured_object_sqlite or DEFAULT_STRUCTURED_OBJECT_SQLITES)]
    structured_taxonomy_repair_reference_facts = [_resolve(path) for path in (args.structured_taxonomy_repair_reference_facts or [])]
    if args.enable_direct_chunk_kpi_scan:
        direct_metric_candidates = build_direct_metric_candidates_from_chunks(
            chunk_inputs,
            normalized_rows,
            generated_at=generated_at,
            max_windows_per_chunk=max(args.max_direct_windows_per_chunk, 1),
            max_citation_chars=max(args.max_citation_chars, 240),
        )
    kpi_facts, kpi_rejections = parse_metric_candidates_to_facts(
        [*metric_candidates, *direct_metric_candidates],
        normalized_rows,
        ontology=ontology,
        generated_at=generated_at,
        max_citation_chars=max(args.max_citation_chars, 240),
    )
    structured_kpi_facts: list[dict[str, Any]] = []
    structured_kpi_rejections: list[dict[str, Any]] = []
    structured_scan_summary: dict[str, Any] | None = None
    structured_taxonomy_repair_summary: dict[str, Any] | None = None
    if args.enable_structured_metric_kpi_scan:
        normalized_rows, structured_alias_rows, structured_taxonomy_repair_summary = augment_taxonomy_with_structured_metric_nodes(
            structured_sqlite_inputs,
            normalized_rows,
            rules=rules,
            universe_index=universe_index,
            chunk_inputs=chunk_inputs,
            reference_fact_paths=structured_taxonomy_repair_reference_facts,
            allow_table_taxonomy_repair=args.enable_structured_table_taxonomy_repair,
            generated_at=generated_at,
            max_citation_chars=max(args.max_citation_chars, 240),
        )
        alias_rows.extend(structured_alias_rows)
        structured_kpi_facts, structured_kpi_rejections, structured_scan_summary = parse_structured_sqlite_metrics_to_facts(
            structured_sqlite_inputs,
            normalized_rows,
            ontology=ontology,
            chunk_inputs=chunk_inputs,
            generated_at=generated_at,
            max_citation_chars=max(args.max_citation_chars, 240),
        )
        seen_fact_ids = {str(row.get("fact_id") or "") for row in kpi_facts}
        for fact in structured_kpi_facts:
            fact_id = str(fact.get("fact_id") or "")
            if fact_id in seen_fact_ids:
                structured_kpi_rejections.append(
                    _kpi_rejection_row(
                        fact,
                        generated_at,
                        "duplicate_fact",
                        fact.get("citation_span") or "",
                    )
                )
                continue
            seen_fact_ids.add(fact_id)
            kpi_facts.append(fact)
        kpi_rejections.extend(structured_kpi_rejections)

    normalized_output = _resolve(args.normalized_taxonomy_output)
    aliases_output = _resolve(args.taxonomy_aliases_output)
    review_output = _resolve(args.taxonomy_review_output)
    facts_output = _resolve(args.kpi_facts_output)
    rejections_output = _resolve(args.kpi_rejections_output)
    summary_output = _resolve(args.summary_output)
    report_output = _resolve(args.report_output)
    _write_jsonl(normalized_output, normalized_rows)
    _write_jsonl(aliases_output, alias_rows)
    _write_jsonl(review_output, review_rows)
    _write_jsonl(facts_output, kpi_facts)
    _write_jsonl(rejections_output, kpi_rejections)

    summary = build_summary(
        rules_path=rules_path,
        taxonomy_path=taxonomy_path,
        metric_path=metric_path,
        universe_path=universe_path,
        sector_depth_path=sector_depth_path,
        ontology_path=ontology_path,
        chunk_inputs=chunk_inputs if args.enable_direct_chunk_kpi_scan else [],
        normalized_output=normalized_output,
        aliases_output=aliases_output,
        review_output=review_output,
        facts_output=facts_output,
        rejections_output=rejections_output,
        summary_output=summary_output,
        report_output=report_output,
        taxonomy_candidates=taxonomy_candidates,
        metric_candidates=metric_candidates,
        direct_metric_candidates=direct_metric_candidates,
        structured_sqlite_inputs=structured_sqlite_inputs if args.enable_structured_metric_kpi_scan else [],
        structured_scan_summary=structured_scan_summary,
        structured_taxonomy_repair_summary=structured_taxonomy_repair_summary,
        normalized_rows=normalized_rows,
        alias_rows=alias_rows,
        review_rows=review_rows,
        kpi_facts=kpi_facts,
        kpi_rejections=kpi_rejections,
        generated_at=generated_at,
    )
    _write_json(summary_output, summary)
    report_output.parent.mkdir(parents=True, exist_ok=True)
    report_output.write_text(render_report(summary), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def load_universe_index(universe_manifest: Path, sector_depth_config: Path) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    if universe_manifest.exists():
        with universe_manifest.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                ticker = str(row.get("ticker") or "").strip()
                if not ticker:
                    continue
                entry = index.setdefault(ticker, {})
                entry.update(
                    {
                        "ticker": ticker,
                        "company_name": str(row.get("company_name") or "").strip(),
                        "sector": str(row.get("sector") or "").strip(),
                        "category": str(row.get("category") or "").strip(),
                        "universe_tier": str(row.get("universe_tier") or "").strip(),
                        "country": str(row.get("country") or "").strip(),
                    }
                )
    if sector_depth_config.exists():
        data = _load_yaml(sector_depth_config)
        for row in data.get("companies") or []:
            if not isinstance(row, dict):
                continue
            ticker = str(row.get("ticker") or "").strip()
            if not ticker:
                continue
            entry = index.setdefault(ticker, {"ticker": ticker})
            category = str(row.get("category") or "").strip()
            if category:
                entry["sector_depth_category"] = category
            groups = [str(item).strip() for item in row.get("industry_groups") or [] if str(item).strip()]
            if groups:
                entry["industry_groups"] = groups
    return index


def normalize_taxonomy_candidates(
    taxonomy_candidates: Iterable[dict[str, Any]],
    *,
    rules: dict[str, Any],
    universe_index: dict[str, dict[str, Any]],
    generated_at: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    node_state: dict[str, dict[str, Any]] = {}
    alias_rows: list[dict[str, Any]] = []
    review_rows: list[dict[str, Any]] = []

    for row in taxonomy_candidates:
        ticker = str(row.get("ticker") or "").strip()
        label = str(row.get("taxonomy_label") or "").strip()
        profile = universe_index.get(ticker, {})
        industry_schema, route_evidence = determine_industry_schema(row, profile, rules)
        quality_error = validate_taxonomy_label(label, rules)
        if industry_schema == "needs_industry_template_review":
            review_rows.append(_taxonomy_review_row(row, generated_at, "no_industry_template", route_evidence))
            continue
        if quality_error:
            review_rows.append(_taxonomy_review_row(row, generated_at, quality_error, route_evidence))
            continue

        canonical_name = canonicalize_taxonomy_label(label, rules)
        canonical_error = validate_taxonomy_label(canonical_name, rules)
        if canonical_error:
            review_rows.append(_taxonomy_review_row(row, generated_at, canonical_error, route_evidence))
            continue
        if is_issuer_name_label(canonical_name, str(row.get("company") or profile.get("company_name") or "")):
            review_rows.append(_taxonomy_review_row(row, generated_at, "issuer_name_not_product_taxonomy", route_evidence))
            continue

        node_type = node_type_for_taxonomy(row, industry_schema, rules)
        product_node_id = product_node_id_for(ticker, industry_schema, canonical_name)
        fiscal_year = _safe_int(row.get("fiscal_year"))
        node = node_state.setdefault(
            product_node_id,
            {
                "schema_version": NORMALIZED_TAXONOMY_SCHEMA_VERSION,
                "product_node_id": product_node_id,
                "ticker": ticker,
                "company": row.get("company") or profile.get("company_name"),
                "industry_schema": industry_schema,
                "industry_route_evidence": route_evidence,
                "canonical_name": canonical_name,
                "node_type": node_type,
                "aliases": [],
                "source_candidate_ids": [],
                "source_urls": [],
                "source_document_ids": [],
                "fiscal_years": [],
                "first_seen_fiscal_year": fiscal_year,
                "last_seen_fiscal_year": fiscal_year,
                "max_candidate_confidence": _safe_float(row.get("confidence_score")) or 0.0,
                "evidence_count": 0,
                "parent_node_id": None,
                "hierarchy_status": "parent_not_inferred_without_explicit_source_hierarchy",
                "signal_role": "company_disclosed",
                "signal_strength": "S5_primary_authority_taxonomy",
                "promotion_status": "taxonomy_normalized_auto_gate_passed",
                "runtime_use_boundary": "May support product taxonomy, retrieval planning, and product-KPI linking; cannot prove sales, demand, market share, or margin.",
                "generated_at": generated_at,
            },
        )
        _append_unique(node["aliases"], label)
        _append_unique(node["aliases"], canonical_name)
        _append_unique(node["source_candidate_ids"], str(row.get("candidate_id") or ""))
        _append_unique(node["source_urls"], str(row.get("source_url") or ""))
        _append_unique(node["source_document_ids"], str(row.get("chunk_id") or ""))
        if fiscal_year:
            _append_unique(node["fiscal_years"], fiscal_year)
            years = [int(item) for item in node["fiscal_years"] if item]
            node["first_seen_fiscal_year"] = min(years)
            node["last_seen_fiscal_year"] = max(years)
        node["max_candidate_confidence"] = max(float(node.get("max_candidate_confidence") or 0), _safe_float(row.get("confidence_score")) or 0.0)
        node["evidence_count"] = int(node.get("evidence_count") or 0) + 1
        alias_rows.append(_taxonomy_alias_row(row, product_node_id, canonical_name, industry_schema, node_type, generated_at))

    normalized_rows = sorted(node_state.values(), key=lambda item: (str(item.get("ticker")), str(item.get("industry_schema")), str(item.get("canonical_name"))))
    for node in normalized_rows:
        node["aliases"] = sorted({str(item) for item in node.get("aliases") or [] if str(item).strip()}, key=str.lower)
        node["source_candidate_ids"] = sorted({str(item) for item in node.get("source_candidate_ids") or [] if str(item).strip()})
        node["source_urls"] = sorted({str(item) for item in node.get("source_urls") or [] if str(item).strip()})
        node["source_document_ids"] = sorted({str(item) for item in node.get("source_document_ids") or [] if str(item).strip()})
        node["fiscal_years"] = sorted({int(item) for item in node.get("fiscal_years") or [] if item})
    return normalized_rows, alias_rows, review_rows


def determine_industry_schema(row: dict[str, Any], profile: dict[str, Any], rules: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    category_text = " ".join(
        [
            str(profile.get("sector") or ""),
            str(profile.get("category") or ""),
            str(profile.get("sector_depth_category") or ""),
            " ".join(str(item) for item in profile.get("industry_groups") or []),
        ]
    ).lower()
    label_text = " ".join([str(row.get("taxonomy_label") or ""), str(row.get("company") or "")]).lower()
    best_schema = ""
    best_score = 0
    best_hits: list[str] = []
    for schema_name, schema in (rules.get("industry_schemas") or {}).items():
        if not isinstance(schema, dict):
            continue
        priority = int(schema.get("priority") or 999)
        hits: list[str] = []
        score = 0
        for keyword in schema.get("category_keywords") or []:
            key = str(keyword).lower()
            if key and key in category_text:
                hits.append(f"category:{key}")
                score += 4
        for keyword in schema.get("label_keywords") or []:
            key = str(keyword).lower()
            if key and key in label_text:
                hits.append(f"label:{key}")
                score += 2
        if score <= 0:
            continue
        ranked_score = (score * 1000) - priority
        if ranked_score > best_score:
            best_score = ranked_score
            best_schema = str(schema_name)
            best_hits = hits
    if not best_schema:
        return (
            "needs_industry_template_review",
            {
                "sector": profile.get("sector") or "",
                "category": profile.get("category") or "",
                "sector_depth_category": profile.get("sector_depth_category") or "",
                "hits": [],
            },
        )
    return (
        best_schema,
        {
            "sector": profile.get("sector") or "",
            "category": profile.get("category") or "",
            "sector_depth_category": profile.get("sector_depth_category") or "",
            "hits": best_hits[:8],
        },
    )


def validate_taxonomy_label(label: str, rules: dict[str, Any]) -> str:
    gate = rules.get("label_quality_gate") or {}
    text = _clean_text(label)
    lower = text.lower().strip(":- ")
    if len(text) < int(gate.get("min_chars") or 3):
        return "label_too_short"
    if len(text) > int(gate.get("max_chars") or 120):
        return "label_too_long"
    if len(text.split()) > int(gate.get("max_words") or 12):
        return "label_too_many_words"
    if lower in {str(item).lower() for item in gate.get("reject_exact_lower") or []}:
        return "generic_or_metric_label"
    if any(str(item).lower() in lower for item in gate.get("reject_contains_lower") or []):
        return "boilerplate_or_reporting_context"
    for pattern in gate.get("reject_regex") or []:
        if re.search(str(pattern), lower, flags=re.IGNORECASE):
            return "boilerplate_or_numeric_label"
    if re.search(r"\b(?:increased|decreased|grew|declined|accounted for|represented)\b", lower):
        return "metric_sentence_not_taxonomy"
    return ""


def canonicalize_taxonomy_label(label: str, rules: dict[str, Any]) -> str:
    text = _clean_text(label)
    text = re.sub(r"\b(?:the company's|company's|our|the)\b\s+", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"\b(?:business|segment|group|division)\b$", "", text, flags=re.IGNORECASE).strip(" :-")
    for old, new in (rules.get("canonical_replacements") or {}).items():
        text = re.sub(re.escape(str(old)), str(new), text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip(" :-;,.")
    return _smart_title(text)


def node_type_for_taxonomy(row: dict[str, Any], industry_schema: str, rules: dict[str, Any]) -> str:
    taxonomy_type = str(row.get("taxonomy_type") or "")
    schema = ((rules.get("industry_schemas") or {}).get(industry_schema) or {})
    mapped = (schema.get("node_types") or {}).get(taxonomy_type)
    return str(mapped or taxonomy_type or "product_family")


def is_issuer_name_label(label: str, company: str) -> bool:
    label_key = _issuer_key(label)
    company_key = _issuer_key(company)
    if not label_key or not company_key:
        return False
    return label_key == company_key or label_key in company_key or company_key in label_key


def product_node_id_for(ticker: str, industry_schema: str, canonical_name: str) -> str:
    slug = _slug(canonical_name)
    digest = hashlib.sha1("||".join([ticker, industry_schema, canonical_name.lower()]).encode("utf-8")).hexdigest()[:8]
    return f"PRODUCTNODE::{ticker}::{industry_schema}::{slug[:64]}::{digest}"


def augment_taxonomy_with_structured_metric_nodes(
    sqlite_paths: Iterable[Path],
    normalized_rows: list[dict[str, Any]],
    *,
    rules: dict[str, Any],
    universe_index: dict[str, dict[str, Any]],
    chunk_inputs: Iterable[Path],
    generated_at: str,
    max_citation_chars: int,
    reference_fact_paths: Iterable[Path] = (),
    allow_table_taxonomy_repair: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    node_state = {str(row.get("product_node_id") or ""): dict(row) for row in normalized_rows}
    existing_names_by_ticker: dict[str, set[str]] = defaultdict(set)
    for row in normalized_rows:
        ticker = str(row.get("ticker") or "").strip()
        if not ticker:
            continue
        for alias in [row.get("canonical_name"), *(row.get("aliases") or [])]:
            key = canonical_product_label_key(alias)
            if key:
                existing_names_by_ticker[ticker].add(key)

    candidate_records: list[dict[str, Any]] = []
    stats: Counter[str] = Counter()
    seen_repair_candidate_keys: set[tuple[str, str]] = set()
    ticker_set = {str(ticker).strip().upper() for ticker in universe_index if str(ticker).strip()}
    if not ticker_set:
        ticker_set = {str(row.get("ticker") or "").strip().upper() for row in normalized_rows if row.get("ticker")}
    reference_fact_tickers = load_reference_fact_tickers(reference_fact_paths)
    if reference_fact_tickers:
        ticker_set = {ticker for ticker in ticker_set if ticker not in reference_fact_tickers}
        stats["reference_fact_tickers_excluded"] = len(reference_fact_tickers)

    for sqlite_path in sqlite_paths:
        path = _resolve(sqlite_path)
        if not path.exists():
            stats["missing_sqlite_inputs"] += 1
            continue
        for record in iter_structured_metric_records_from_sqlite(path, ticker_set):
            stats["sqlite_metric_rows_scanned"] += 1
            if structured_is_change_cell(record) or structured_is_non_period_or_decomposition_cell(record):
                stats["change_or_decomposition_rows_skipped"] += 1
                continue
            if structured_record_is_statement_noise_for_taxonomy_repair(record):
                stats["statement_noise_rows_skipped"] += 1
                continue
            if is_structured_table_metric_record(record) and not allow_table_taxonomy_repair:
                stats["table_taxonomy_repair_disabled_rows_skipped"] += 1
                continue
            if not structured_record_has_candidate_measurement(record):
                stats["rows_without_candidate_measurement"] += 1
                continue
            label_info = structured_taxonomy_label_candidate(record)
            if not label_info:
                stats["rows_without_repair_label"] += 1
                continue
            ticker = str(record.get("ticker") or "").strip()
            label = label_info["label"]
            canonical = canonicalize_taxonomy_label(label, rules)
            if canonical_product_label_key(canonical) in existing_names_by_ticker.get(ticker, set()):
                stats["already_known_labels"] += 1
                continue
            if validate_structured_taxonomy_repair_label(canonical, rules):
                stats["labels_failed_quality_gate"] += 1
                continue
            repair_key = (ticker, canonical_product_label_key(canonical))
            if repair_key in seen_repair_candidate_keys:
                stats["duplicate_repair_label_candidates"] += 1
                continue
            seen_repair_candidate_keys.add(repair_key)
            candidate = dict(record)
            candidate["_taxonomy_repair_label"] = label
            candidate["_taxonomy_repair_label_source"] = label_info["source"]
            candidate["_taxonomy_repair_canonical_name"] = canonical
            candidate_records.append(candidate)

    source_context_by_id = load_chunk_source_contexts(chunk_inputs, {str(row.get("source_evidence_id") or "") for row in candidate_records})
    stats["source_context_rows_loaded"] = len(source_context_by_id)
    alias_rows: list[dict[str, Any]] = []
    repaired_by_node: dict[str, dict[str, Any]] = {}
    rejected_reason_counts: Counter[str] = Counter()
    for record in candidate_records:
        source_context = source_context_by_id.get(str(record.get("source_evidence_id") or ""))
        if not source_context or not source_context.get("source_url"):
            rejected_reason_counts["missing_source_url"] += 1
            continue
        if not structured_metric_is_admissible_for_taxonomy_repair(record, source_context):
            rejected_reason_counts["not_admissible_product_metric_context"] += 1
            continue
        ticker = str(record.get("ticker") or "").strip()
        profile = universe_index.get(ticker, {"ticker": ticker})
        label = str(record.get("_taxonomy_repair_label") or "").strip()
        canonical = str(record.get("_taxonomy_repair_canonical_name") or "").strip()
        pseudo_row = {
            "candidate_id": structured_taxonomy_repair_candidate_id(record, canonical),
            "ticker": ticker,
            "company": source_context.get("company") or profile.get("company_name"),
            "taxonomy_label": label,
            "taxonomy_type": "reportable_segment" if record.get("_taxonomy_repair_label_source") in {"segment", "row_label"} else "product_or_service_family",
            "source_url": source_context.get("source_url"),
            "chunk_id": record.get("source_evidence_id"),
            "fiscal_year": record.get("fiscal_year"),
            "confidence_score": 0.82 if is_structured_table_metric_record(record) else 0.78,
        }
        industry_schema, route_evidence = determine_industry_schema(pseudo_row, profile, rules)
        if industry_schema == "needs_industry_template_review":
            rejected_reason_counts["no_industry_template"] += 1
            continue
        node_type = node_type_for_taxonomy(pseudo_row, industry_schema, rules)
        product_node_id = product_node_id_for(ticker, industry_schema, canonical)
        node = repaired_by_node.setdefault(
            product_node_id,
            {
                "schema_version": NORMALIZED_TAXONOMY_SCHEMA_VERSION,
                "product_node_id": product_node_id,
                "ticker": ticker,
                "company": pseudo_row.get("company"),
                "industry_schema": industry_schema,
                "industry_route_evidence": route_evidence,
                "canonical_name": canonical,
                "node_type": node_type,
                "aliases": [],
                "source_candidate_ids": [],
                "source_urls": [],
                "source_document_ids": [],
                "fiscal_years": [],
                "first_seen_fiscal_year": _safe_int(record.get("fiscal_year")),
                "last_seen_fiscal_year": _safe_int(record.get("fiscal_year")),
                "max_candidate_confidence": pseudo_row["confidence_score"],
                "evidence_count": 0,
                "parent_node_id": None,
                "hierarchy_status": "parent_not_inferred_without_explicit_source_hierarchy",
                "signal_role": "company_disclosed",
                "signal_strength": "S5_primary_authority_taxonomy",
                "promotion_status": "taxonomy_structured_metric_repair_gate_passed",
                "runtime_use_boundary": "May support product taxonomy and product-KPI linking because the label appears in a parser-readable company-disclosed metric object; cannot prove demand, sales, market share, or margin without a parser-verified KPI fact.",
                "generated_at": generated_at,
            },
        )
        _append_unique(node["aliases"], label)
        _append_unique(node["aliases"], canonical)
        _append_unique(node["source_candidate_ids"], pseudo_row["candidate_id"])
        _append_unique(node["source_urls"], str(source_context.get("source_url") or ""))
        _append_unique(node["source_document_ids"], str(record.get("source_evidence_id") or ""))
        fiscal_year = _safe_int(record.get("fiscal_year"))
        if fiscal_year:
            _append_unique(node["fiscal_years"], fiscal_year)
            years = [int(item) for item in node["fiscal_years"] if item]
            node["first_seen_fiscal_year"] = min(years)
            node["last_seen_fiscal_year"] = max(years)
        node["max_candidate_confidence"] = max(float(node.get("max_candidate_confidence") or 0), float(pseudo_row["confidence_score"]))
        node["evidence_count"] = int(node.get("evidence_count") or 0) + 1
        alias_rows.append(_taxonomy_alias_row(pseudo_row, product_node_id, canonical, industry_schema, node_type, generated_at))
        existing_names_by_ticker[ticker].add(canonical_product_label_key(canonical))

    for product_node_id, node in repaired_by_node.items():
        current = node_state.get(product_node_id)
        if current:
            for key in ("aliases", "source_candidate_ids", "source_urls", "source_document_ids", "fiscal_years"):
                for value in node.get(key) or []:
                    _append_unique(current.setdefault(key, []), value)
            current["evidence_count"] = int(current.get("evidence_count") or 0) + int(node.get("evidence_count") or 0)
            current["max_candidate_confidence"] = max(float(current.get("max_candidate_confidence") or 0), float(node.get("max_candidate_confidence") or 0))
        else:
            node_state[product_node_id] = node

    repaired_rows = sorted(node_state.values(), key=lambda item: (str(item.get("ticker")), str(item.get("industry_schema")), str(item.get("canonical_name"))))
    for node in repaired_rows:
        node["aliases"] = sorted({str(item) for item in node.get("aliases") or [] if str(item).strip()}, key=str.lower)
        node["source_candidate_ids"] = sorted({str(item) for item in node.get("source_candidate_ids") or [] if str(item).strip()})
        node["source_urls"] = sorted({str(item) for item in node.get("source_urls") or [] if str(item).strip()})
        node["source_document_ids"] = sorted({str(item) for item in node.get("source_document_ids") or [] if str(item).strip()})
        node["fiscal_years"] = sorted({int(item) for item in node.get("fiscal_years") or [] if item})

    repaired_nodes = [row for row in repaired_rows if str(row.get("promotion_status") or "") == "taxonomy_structured_metric_repair_gate_passed"]
    summary = {
        "schema_version": "fin_agent_structured_metric_taxonomy_repair_summary_v0.1",
        "status": "pass",
        "candidate_record_count": len(candidate_records),
        "repaired_node_count": len(repaired_nodes),
        "repaired_ticker_count": len({str(row.get("ticker") or "") for row in repaired_nodes if row.get("ticker")}),
        "repaired_node_type_counts": dict(sorted(Counter(str(row.get("node_type") or "") for row in repaired_nodes).items())),
        "rejected_reason_counts": dict(sorted(rejected_reason_counts.items())),
        "scan_counts": dict(sorted(stats.items())),
        "promotion_boundary": (
            "Adds taxonomy nodes only from structured metric objects with explicit product/segment labels, "
            "source URL hydration, non-generic labels, non-change numeric cells, and admissible product metric context. "
            "Table-row taxonomy repair is disabled unless explicitly requested."
        ),
        "allow_table_taxonomy_repair": allow_table_taxonomy_repair,
    }
    return repaired_rows, alias_rows, summary


def structured_taxonomy_repair_candidate_id(record: dict[str, Any], canonical_name: str) -> str:
    return _stable_id("PRODUCTTAXSTRUCTREPAIR", record.get("object_id"), record.get("source_evidence_id"), canonical_name)


def load_reference_fact_tickers(reference_fact_paths: Iterable[Path]) -> set[str]:
    tickers: set[str] = set()
    for path in reference_fact_paths:
        resolved = _resolve(path)
        if not resolved.exists():
            continue
        for row in _iter_jsonl(resolved):
            ticker = str(row.get("ticker") or "").strip().upper()
            if ticker:
                tickers.add(ticker)
    return tickers


def canonical_product_label_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", _clean_text(value).lower())


def structured_taxonomy_label_candidate(record: dict[str, Any]) -> dict[str, str] | None:
    fields = (
        (("segment", record.get("segment")),)
        if is_structured_sentence_metric_record(record)
        else (
            ("row_label", record.get("row_label")),
            ("segment", record.get("segment")),
            ("metric_name", record.get("metric_name")),
        )
    )
    for source, value in fields:
        label = _clean_text(value)
        if not label:
            continue
        if structured_label_is_generic_or_metric(label):
            continue
        return {"source": source, "label": label}
    return None


def structured_label_is_generic_or_metric(label: str) -> bool:
    lower = _clean_text(label).lower().strip(":- ")
    if not lower:
        return True
    if lower in GENERIC_STRUCTURED_PRODUCT_LABELS:
        return True
    if lower.startswith("total ") and any(term in lower for term in ("revenue", "sales", "assets", "liabilities", "income", "expense")):
        return True
    if any(term in lower for term in STRUCTURED_REPAIR_FORBIDDEN_LABEL_TERMS):
        return True
    if re.search(r"\b(?:revenue|revenues|net sales|sales|gross margin|operating income|operating profit|net income|total assets|cash flows?)\b", lower):
        if len(lower.split()) <= 4:
            return True
    if re.search(r"^[0-9.,%$()\- ]+$", lower):
        return True
    if "$" in label or re.search(r"\b20\d{2}\b", lower):
        return True
    return False


def structured_record_is_statement_noise_for_taxonomy_repair(record: dict[str, Any]) -> bool:
    text = _clean_text(
        " ".join(
            str(record.get(key) or "")
            for key in ("section", "subsection", "row_label", "metric_name", "column_label", "preview")
        )
    ).lower()
    if any(term in text for term in STRUCTURED_REPAIR_FORBIDDEN_LABEL_TERMS):
        return True
    if re.search(r"\b(?:cash flow hedges|cash flows?|balance sheets?|fair value|derivative instruments?|income taxes?|deferred taxes?|stockholders'? equity|shareholders'? equity)\b", text):
        return True
    return False


def validate_structured_taxonomy_repair_label(label: str, rules: dict[str, Any]) -> str:
    if structured_label_is_generic_or_metric(label):
        return "generic_or_metric_label"
    return validate_taxonomy_label(label, rules)


def structured_metric_is_admissible_for_taxonomy_repair(record: dict[str, Any], source_context: dict[str, Any]) -> bool:
    if is_structured_table_metric_record(record):
        return bool(infer_structured_metric_families(record, source_context))
    if is_structured_sentence_metric_record(record):
        unit = str(record.get("unit") or "").lower()
        raw = str(record.get("raw_value") or "")
        if unit == "percent" or "%" in raw:
            return False
        return bool(infer_structured_metric_families(record, source_context))
    return False


def parse_metric_candidates_to_facts(
    metric_candidates: Iterable[dict[str, Any]],
    normalized_taxonomy_rows: Iterable[dict[str, Any]],
    *,
    ontology: dict[str, Any],
    generated_at: str,
    max_citation_chars: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    nodes_by_ticker = build_product_node_lookup(normalized_taxonomy_rows)
    fact_rows: list[dict[str, Any]] = []
    rejection_rows: list[dict[str, Any]] = []
    seen_fact_ids: set[str] = set()
    for row in metric_candidates:
        fact, rejection = parse_one_metric_candidate(
            row,
            nodes_by_ticker=nodes_by_ticker,
            ontology=ontology,
            generated_at=generated_at,
            max_citation_chars=max_citation_chars,
        )
        if fact:
            fact_id = str(fact.get("fact_id") or "")
            if fact_id in seen_fact_ids:
                rejection_rows.append(_kpi_rejection_row(row, generated_at, "duplicate_fact", fact.get("citation_span") or row.get("snippet") or ""))
                continue
            seen_fact_ids.add(fact_id)
            fact_rows.append(fact)
        elif rejection:
            rejection_rows.append(rejection)
    return fact_rows, rejection_rows


def parse_structured_sqlite_metrics_to_facts(
    sqlite_paths: Iterable[Path],
    normalized_taxonomy_rows: Iterable[dict[str, Any]],
    *,
    ontology: dict[str, Any],
    chunk_inputs: Iterable[Path],
    generated_at: str,
    max_citation_chars: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    normalized_rows = list(normalized_taxonomy_rows)
    nodes_by_ticker = build_product_node_lookup(normalized_rows)
    preselected: list[dict[str, Any]] = []
    stats: Counter[str] = Counter()
    input_paths: list[str] = []
    for sqlite_path in sqlite_paths:
        path = _resolve(sqlite_path)
        input_paths.append(_repo_path(path))
        if not path.exists():
            stats["missing_sqlite_inputs"] += 1
            continue
        for record in iter_structured_metric_records_from_sqlite(path, nodes_by_ticker.keys()):
            stats["sqlite_metric_rows_scanned"] += 1
            if not is_structured_product_metric_record(record):
                stats["non_product_metric_rows_skipped"] += 1
                continue
            if structured_is_change_cell(record):
                stats["change_cells_skipped"] += 1
                continue
            product_match = match_structured_product_node(record, nodes_by_ticker.get(str(record.get("ticker") or ""), []))
            if not product_match:
                stats["table_metric_rows_without_product_match"] += 1
                continue
            if not structured_record_has_candidate_measurement(record):
                stats["table_product_rows_without_candidate_measurement"] += 1
                continue
            candidate = dict(record)
            candidate["_product_match"] = product_match
            preselected.append(candidate)
            stats["preselected_table_product_metric_rows"] += 1

    source_context_by_id = load_chunk_source_contexts(chunk_inputs, {str(row.get("source_evidence_id") or "") for row in preselected})
    stats["source_context_rows_loaded"] = len(source_context_by_id)
    fact_rows, rejection_rows = parse_structured_metric_records_to_facts(
        preselected,
        normalized_rows,
        ontology=ontology,
        source_context_by_id=source_context_by_id,
        generated_at=generated_at,
        max_citation_chars=max_citation_chars,
    )
    stats["parser_verified_fact_count"] = len(fact_rows)
    stats["rejection_count"] = len(rejection_rows)
    fact_tickers = {str(row.get("ticker") or "") for row in fact_rows if row.get("ticker")}
    candidate_tickers = {str(row.get("ticker") or "") for row in preselected if row.get("ticker")}
    summary = {
        "schema_version": "fin_agent_structured_metric_kpi_parser_summary_v0.1",
        "status": "pass",
        "inputs": {
            "structured_object_sqlites": input_paths,
            "chunk_inputs": [_repo_path(_resolve(path)) for path in chunk_inputs],
        },
        "scanned_ticker_count": len(nodes_by_ticker),
        "preselected_candidate_count": len(preselected),
        "preselected_candidate_ticker_count": len(candidate_tickers),
        "parser_verified_fact_count": len(fact_rows),
        "parser_verified_ticker_count": len(fact_tickers),
        "parser_verified_ticker_coverage_pct": _pct(len(fact_tickers), len(candidate_tickers)),
        "fact_metric_family_counts": dict(sorted(Counter(str(row.get("metric_family") or "") for row in fact_rows).items())),
        "rejection_reason_counts": dict(sorted(Counter(str(row.get("rejection_reason") or "") for row in rejection_rows).items())),
        "scan_counts": dict(sorted(stats.items())),
        "promotion_boundary": (
            "Structured MetricObject rows are promoted only when row/column period cells or strict sentence metric fields, "
            "product node match, value/unit, source URL, source document id, and chunk-level citation context all pass parser gates."
        ),
    }
    return fact_rows, rejection_rows, summary


def iter_structured_metric_records_from_sqlite(sqlite_path: Path, tickers: Iterable[str]) -> Iterable[dict[str, Any]]:
    uri = sqlite_path.as_posix()
    conn = sqlite3.connect(f"file:{uri}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA temp_store=MEMORY")
        ticker_set = {str(item or "").strip().upper() for item in tickers if str(item or "").strip()}
        has_fts = bool(
            conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='object_records_fts'"
            ).fetchone()
        )
        if has_fts:
            yield from iter_structured_metric_records_from_sqlite_fts(conn, sqlite_path, ticker_set)
        else:
            yield from iter_structured_metric_records_from_sqlite_full_scan(conn, sqlite_path, ticker_set)
    finally:
        conn.close()


def iter_structured_metric_records_from_sqlite_fts(
    conn: sqlite3.Connection,
    sqlite_path: Path,
    ticker_set: set[str],
) -> Iterable[dict[str, Any]]:
    seen_idx: set[int] = set()
    for query in structured_metric_fts_queries():
        cursor = conn.execute(
            """
            SELECT r.idx, r.object_id, r.source_evidence_id, r.ticker, r.fiscal_year,
                   r.form_type, r.source_type, r.source_tier, r.section, r.subsection,
                   r.period, r.period_end, r.period_type, r.duration_months,
                   r.fiscal_period, r.preview, r.metric_family, r.record_json
            FROM object_records_fts f
            JOIN object_records r ON r.idx = f.rowid
            WHERE object_records_fts MATCH ?
              AND r.object_type = 'metric'
            """,
            [query],
        )
        while True:
            rows = cursor.fetchmany(1000)
            if not rows:
                break
            for row in rows:
                idx = int(row["idx"])
                if idx in seen_idx:
                    continue
                seen_idx.add(idx)
                ticker = str(row["ticker"] or "").strip().upper()
                if ticker_set and ticker not in ticker_set:
                    continue
                record = sqlite_metric_record_from_row(row, sqlite_path)
                if record:
                    record["_fts_query"] = query
                    yield record


def iter_structured_metric_records_from_sqlite_full_scan(
    conn: sqlite3.Connection,
    sqlite_path: Path,
    ticker_set: set[str],
) -> Iterable[dict[str, Any]]:
    for ticker in sorted(ticker_set):
        cursor = conn.execute(
            """
            SELECT idx, object_id, source_evidence_id, ticker, fiscal_year, form_type,
                   source_type, source_tier, section, subsection, period, period_end,
                   period_type, duration_months, fiscal_period, preview, metric_family,
                   record_json
            FROM object_records INDEXED BY idx_object_records_ticker_year_form_object
            WHERE ticker = ? AND object_type = 'metric'
            """,
            [ticker],
        )
        while True:
            rows = cursor.fetchmany(1000)
            if not rows:
                break
            for row in rows:
                record = sqlite_metric_record_from_row(row, sqlite_path)
                if record:
                    yield record


def sqlite_metric_record_from_row(row: sqlite3.Row, sqlite_path: Path) -> dict[str, Any] | None:
    try:
        record = json.loads(row["record_json"])
    except json.JSONDecodeError:
        return None
    if not isinstance(record, dict):
        return None
    for key in (
        "object_id",
        "source_evidence_id",
        "ticker",
        "fiscal_year",
        "form_type",
        "source_type",
        "source_tier",
        "section",
        "subsection",
        "period",
        "period_end",
        "period_type",
        "duration_months",
        "fiscal_period",
        "preview",
        "metric_family",
    ):
        if record.get(key) in (None, "", [], {}):
            record[key] = row[key]
    record["_sqlite_idx"] = row["idx"]
    record["_sqlite_path"] = str(sqlite_path)
    record["_structured_record_mode"] = "compact_sqlite_record"
    return record


def structured_metric_fts_queries() -> list[str]:
    return [
        "revenue",
        "revenues",
        '"net sales"',
        '"sales and revenues"',
        '"segment revenue"',
        '"revenue by"',
        "backlog",
        "bookings",
        "orders",
        "rpo",
        '"remaining performance obligations"',
        "deliveries",
        "delivered",
        '"unit sales"',
        "shipments",
        "shipped",
        "production",
        "produced",
        "throughput",
        "subscribers",
        "arpu",
        '"comparable sales"',
        '"same-store sales"',
    ]


def parse_structured_metric_records_to_facts(
    metric_records: Iterable[dict[str, Any]],
    normalized_taxonomy_rows: Iterable[dict[str, Any]],
    *,
    ontology: dict[str, Any],
    source_context_by_id: dict[str, dict[str, Any]],
    generated_at: str,
    max_citation_chars: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    nodes_by_ticker = build_product_node_lookup(normalized_taxonomy_rows)
    fact_rows: list[dict[str, Any]] = []
    rejection_rows: list[dict[str, Any]] = []
    seen_fact_ids: set[str] = set()
    for record in metric_records:
        ticker = str(record.get("ticker") or "").strip()
        product_match = record.get("_product_match")
        if not isinstance(product_match, dict):
            product_match = match_structured_product_node(record, nodes_by_ticker.get(ticker, []))
        if not product_match:
            rejection_rows.append(_structured_kpi_rejection_row(record, generated_at, "no_product_node_match", structured_metric_citation(record, None, max_citation_chars=max_citation_chars)))
            continue
        source_context = source_context_by_id.get(str(record.get("source_evidence_id") or ""))
        if not source_context or not source_context.get("source_url"):
            rejection_rows.append(_structured_kpi_rejection_row(record, generated_at, "missing_source_url", structured_metric_citation(record, source_context, max_citation_chars=max_citation_chars)))
            continue
        metric_families = infer_structured_metric_families(record, source_context)
        if not metric_families:
            rejection_rows.append(_structured_kpi_rejection_row(record, generated_at, "no_valid_metric_context", structured_metric_citation(record, source_context, max_citation_chars=max_citation_chars)))
            continue
        for metric_family in metric_families:
            fact, rejection = parse_one_structured_metric_record(
                record,
                product_match=product_match,
                metric_family=metric_family,
                ontology=ontology,
                source_context=source_context,
                generated_at=generated_at,
                max_citation_chars=max_citation_chars,
            )
            if fact:
                fact_id = str(fact.get("fact_id") or "")
                if fact_id in seen_fact_ids:
                    rejection_rows.append(_structured_kpi_rejection_row(record, generated_at, "duplicate_fact", fact.get("citation_span") or ""))
                    continue
                seen_fact_ids.add(fact_id)
                fact_rows.append(fact)
            elif rejection:
                rejection_rows.append(rejection)
    return fact_rows, rejection_rows


def parse_one_structured_metric_record(
    record: dict[str, Any],
    *,
    product_match: dict[str, Any],
    metric_family: str,
    ontology: dict[str, Any],
    source_context: dict[str, Any],
    generated_at: str,
    max_citation_chars: int,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    citation = structured_metric_citation(record, source_context, max_citation_chars=max_citation_chars)
    if not citation:
        return None, _structured_kpi_rejection_row(record, generated_at, "empty_citation_span", "")
    if not is_structured_product_metric_record(record):
        return None, _structured_kpi_rejection_row(record, generated_at, "not_structured_product_metric_record", citation)
    if structured_is_change_cell(record):
        return None, _structured_kpi_rejection_row(record, generated_at, "change_cell_not_level_value", citation)
    if structured_is_non_period_or_decomposition_cell(record):
        return None, _structured_kpi_rejection_row(record, generated_at, "non_period_or_decomposition_column", citation)
    product_node = product_match["node"]
    product_type_error = validate_product_node_for_metric(metric_family, product_node)
    if product_type_error:
        return None, _structured_kpi_rejection_row(record, generated_at, product_type_error, citation)
    measurement_context = structured_metric_context_text(record, source_context, max_chars=max(max_citation_chars * 3, 1400))
    measurement, measurement_error = structured_measurement(record, metric_family, measurement_context)
    if measurement_error:
        return None, _structured_kpi_rejection_row(record, generated_at, measurement_error, citation)
    if not measurement:
        return None, _structured_kpi_rejection_row(record, generated_at, "no_value_unit_match", citation)
    allowed_error = validate_measurement_unit(metric_family, measurement, ontology)
    if allowed_error:
        return None, _structured_kpi_rejection_row(record, generated_at, allowed_error, citation)
    period = infer_structured_period(record)
    if not period.get("period"):
        return None, _structured_kpi_rejection_row(record, generated_at, "no_period", citation)
    source_document_id = str(record.get("source_evidence_id") or source_context.get("chunk_id") or "")
    source_url = str(source_context.get("source_url") or "")
    if not source_document_id:
        return None, _structured_kpi_rejection_row(record, generated_at, "missing_source_document_id", citation)
    if not source_url:
        return None, _structured_kpi_rejection_row(record, generated_at, "missing_source_url", citation)
    metric_name = infer_structured_metric_name(record, metric_family)
    ticker = str(record.get("ticker") or "").strip()
    table_object_id = structured_table_object_id(record)
    digest = hashlib.sha1(
        "||".join(
            [
                ticker,
                str(product_node.get("product_node_id") or ""),
                metric_family,
                metric_name,
                str(record.get("object_id") or ""),
                str(record.get("row_label") or ""),
                str(record.get("column_label") or ""),
                str(measurement.get("raw_value_text") or ""),
                str(period.get("period") or ""),
            ]
        ).encode("utf-8")
    ).hexdigest()[:14]
    fact_id = f"PRODUCTKPI::{ticker}::{metric_family}::STRUCTURED::{digest}"
    return (
        {
            "schema_version": KPI_FACT_SCHEMA_VERSION,
            "fact_id": fact_id,
            "source_candidate_id": structured_metric_candidate_id(record, metric_family),
            "source_id": "company_product_kpi_facts_structured_sentence_metric_parser"
            if is_structured_sentence_metric_record(record)
            else "company_product_kpi_facts_structured_metric_parser",
            "signal_role": "company_disclosed",
            "signal_strength": "S5_primary_authority_structured_sentence_metric_parser_verified"
            if is_structured_sentence_metric_record(record)
            else "S5_primary_authority_structured_metric_parser_verified",
            "fact_status": "parser_verified_fact",
            "ticker": ticker,
            "company": source_context.get("company") or record.get("company"),
            "fiscal_year": _safe_int(record.get("fiscal_year")),
            "period": period.get("period"),
            "period_type": period.get("period_type"),
            "period_end": period.get("period_end"),
            "period_role": period.get("period_role"),
            "product_node_id": product_node.get("product_node_id"),
            "product_or_segment": product_node.get("canonical_name"),
            "product_node_type": product_node.get("node_type"),
            "product_link_method": product_match.get("match_method"),
            "product_link_score": product_match.get("score"),
            "matched_product_alias": product_match.get("matched_alias"),
            "industry_schema": product_node.get("industry_schema"),
            "metric_family": metric_family,
            "metric_name": metric_name,
            "value": measurement.get("value"),
            "unit": measurement.get("unit"),
            "unit_category": measurement.get("unit_category"),
            "raw_value_text": measurement.get("raw_value_text"),
            "scale": measurement.get("scale"),
            "source_url": source_url,
            "source_document_id": source_document_id,
            "source_metric_object_id": record.get("object_id"),
            "source_table_object_id": table_object_id,
            "structured_record_mode": record.get("_structured_record_mode") or "metric_object",
            "row_label": record.get("row_label"),
            "column_label": record.get("column_label"),
            "cell_kind": structured_cell_kind(record),
            "citation_span": citation,
            "runtime_use_boundary": "May support company-disclosed product KPI facts from structured row/column cells; does not prove market share, channel inventory, or undisclosed product economics.",
            "generated_at": generated_at,
        },
        None,
    )


def build_product_node_lookup(normalized_taxonomy_rows: Iterable[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in normalized_taxonomy_rows:
        ticker = str(row.get("ticker") or "").strip()
        if ticker:
            by_ticker[ticker].append(row)
    for ticker, rows in by_ticker.items():
        rows.sort(key=lambda item: max((len(str(alias)) for alias in item.get("aliases") or [item.get("canonical_name") or ""]), default=0), reverse=True)
    return by_ticker


def build_direct_metric_candidates_from_chunks(
    chunk_inputs: Iterable[Path],
    normalized_taxonomy_rows: Iterable[dict[str, Any]],
    *,
    generated_at: str,
    max_windows_per_chunk: int,
    max_citation_chars: int,
) -> list[dict[str, Any]]:
    nodes_by_ticker = build_product_node_lookup(normalized_taxonomy_rows)
    rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for chunk in iter_chunk_rows(chunk_inputs):
        ticker = str(chunk.get("ticker") or "").strip()
        fiscal_year = _safe_int(chunk.get("fiscal_year"))
        if not ticker or not fiscal_year or ticker not in nodes_by_ticker:
            continue
        text = _clean_text(chunk.get("text") or "")
        if not text:
            continue
        lower = text.lower()
        emitted_for_chunk = 0
        for metric_family, keywords in METRIC_KEYWORDS.items():
            if emitted_for_chunk >= max_windows_per_chunk:
                break
            positions: list[int] = []
            for keyword in keywords:
                start = lower.find(keyword.lower())
                while start >= 0 and len(positions) < max_windows_per_chunk:
                    positions.append(start)
                    start = lower.find(keyword.lower(), start + len(keyword))
            for position in sorted(set(positions))[:max_windows_per_chunk]:
                if emitted_for_chunk >= max_windows_per_chunk:
                    break
                window = _window(text, position, position + 40, max_chars=max_citation_chars)
                if not has_numeric_value(window):
                    continue
                if not match_product_node(window, nodes_by_ticker[ticker]):
                    continue
                digest = hashlib.sha1(
                    "||".join(
                        [
                            ticker,
                            str(fiscal_year),
                            metric_family,
                            str(chunk.get("chunk_id") or ""),
                            window[:220],
                        ]
                    ).encode("utf-8")
                ).hexdigest()[:14]
                candidate_id = f"DIRECTPRODUCTKPI::{ticker}::{fiscal_year}::{digest}"
                if candidate_id in seen_ids:
                    continue
                seen_ids.add(candidate_id)
                rows.append(
                    {
                        "schema_version": "fin_agent_direct_product_kpi_candidate_from_chunk_v0.1",
                        "candidate_id": candidate_id,
                        "source_id": "direct_chunk_product_kpi_candidate",
                        "signal_role": "company_disclosed",
                        "signal_strength": "S5_primary_authority_candidate",
                        "generated_at": generated_at,
                        "metric_family": metric_family,
                        "match_pattern": "direct_chunk_metric_value_product_window",
                        "ticker": ticker,
                        "company": chunk.get("company"),
                        "fiscal_year": fiscal_year,
                        "form_type": chunk.get("form_type") or chunk.get("source_type"),
                        "period_end": chunk.get("period_end"),
                        "section": chunk.get("section"),
                        "chunk_id": chunk.get("chunk_id"),
                        "source_url": chunk.get("source_url"),
                        "candidate_status": "needs_value_unit_period_product_parser",
                        "runtime_use_boundary": "Direct chunk window candidate only; parser gate must pass before fact use.",
                        "snippet": window,
                    }
                )
                emitted_for_chunk += 1
    return rows


def parse_one_metric_candidate(
    row: dict[str, Any],
    *,
    nodes_by_ticker: dict[str, list[dict[str, Any]]],
    ontology: dict[str, Any],
    generated_at: str,
    max_citation_chars: int,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if row.get("signal_role") and row.get("signal_role") != "company_disclosed":
        return None, _kpi_rejection_row(row, generated_at, "source_boundary_not_company_disclosed", row.get("snippet") or "")
    ticker = str(row.get("ticker") or "").strip()
    metric_family = str(row.get("metric_family") or "").strip()
    if not ticker or not metric_family:
        return None, _kpi_rejection_row(row, generated_at, "malformed_candidate", row.get("snippet") or "")
    citation = select_metric_citation_span(str(row.get("snippet") or ""), metric_family, max_citation_chars=max_citation_chars)
    if not citation:
        return None, _kpi_rejection_row(row, generated_at, "empty_citation_span", row.get("snippet") or "")
    if table_layout_requires_table_parser(citation):
        return None, _kpi_rejection_row(row, generated_at, "table_layout_requires_table_parser", citation)
    if not has_valid_metric_context(citation, metric_family):
        return None, _kpi_rejection_row(row, generated_at, "no_valid_metric_context", citation)
    product_match = match_product_node(citation, nodes_by_ticker.get(ticker, []))
    if not product_match:
        return None, _kpi_rejection_row(row, generated_at, "no_product_node_match", citation)
    product_type_error = validate_product_node_for_metric(metric_family, product_match["node"])
    if product_type_error:
        return None, _kpi_rejection_row(row, generated_at, product_type_error, citation)
    measurement, measurement_error = extract_measurement(citation, metric_family)
    if measurement_error:
        return None, _kpi_rejection_row(row, generated_at, measurement_error, citation)
    if not measurement:
        return None, _kpi_rejection_row(row, generated_at, "no_value_unit_match", citation)
    measurement_context_error = validate_measurement_context(metric_family, measurement, citation)
    if measurement_context_error:
        return None, _kpi_rejection_row(row, generated_at, measurement_context_error, citation)
    allowed_error = validate_measurement_unit(metric_family, measurement, ontology)
    if allowed_error:
        return None, _kpi_rejection_row(row, generated_at, allowed_error, citation)
    relation_error = validate_product_measurement_relation(metric_family, product_match, measurement, citation)
    if relation_error:
        return None, _kpi_rejection_row(row, generated_at, relation_error, citation)
    period = infer_period(row, citation)
    if not period.get("period"):
        return None, _kpi_rejection_row(row, generated_at, "no_period", citation)

    metric_name = infer_metric_name(metric_family, citation)
    product_node = product_match["node"]
    digest = hashlib.sha1(
        "||".join(
            [
                ticker,
                str(product_node.get("product_node_id") or ""),
                metric_family,
                metric_name,
                str(measurement.get("raw_value_text") or ""),
                str(period.get("period") or ""),
                str(row.get("chunk_id") or ""),
            ]
        ).encode("utf-8")
    ).hexdigest()[:14]
    fact_id = f"PRODUCTKPI::{ticker}::{metric_family}::{digest}"
    return (
        {
            "schema_version": KPI_FACT_SCHEMA_VERSION,
            "fact_id": fact_id,
            "source_candidate_id": row.get("candidate_id"),
            "source_id": "company_product_kpi_facts_parser_verified",
            "signal_role": "company_disclosed",
            "signal_strength": "S5_primary_authority_parser_verified",
            "fact_status": "parser_verified_fact",
            "ticker": ticker,
            "company": row.get("company"),
            "fiscal_year": _safe_int(row.get("fiscal_year")),
            "period": period.get("period"),
            "period_type": period.get("period_type"),
            "period_end": period.get("period_end"),
            "product_node_id": product_node.get("product_node_id"),
            "product_or_segment": product_node.get("canonical_name"),
            "product_node_type": product_node.get("node_type"),
            "product_link_method": product_match.get("match_method"),
            "product_link_score": product_match.get("score"),
            "matched_product_alias": product_match.get("matched_alias"),
            "industry_schema": product_node.get("industry_schema"),
            "metric_family": metric_family,
            "metric_name": metric_name,
            "value": measurement.get("value"),
            "unit": measurement.get("unit"),
            "unit_category": measurement.get("unit_category"),
            "raw_value_text": measurement.get("raw_value_text"),
            "scale": measurement.get("scale"),
            "source_url": row.get("source_url"),
            "source_document_id": row.get("chunk_id"),
            "citation_span": citation,
            "runtime_use_boundary": "May support company-disclosed product KPI facts; does not prove market share, channel inventory, or undisclosed product economics.",
            "generated_at": generated_at,
        },
        None,
    )


def is_structured_table_metric_record(record: dict[str, Any]) -> bool:
    extraction_method = str(record.get("extraction_method") or "").strip().lower()
    if extraction_method == "table_row_heuristic":
        return bool(record.get("row_label") or record.get("metric_name"))
    metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
    if metadata.get("table_object_id") or record.get("table_object_id"):
        return bool(record.get("row_label") or record.get("column_label"))
    return bool(record.get("row_label") and record.get("column_label") and extraction_method.startswith("table"))


def is_structured_sentence_metric_record(record: dict[str, Any]) -> bool:
    if is_structured_table_metric_record(record):
        return False
    object_id = str(record.get("object_id") or "").upper()
    extraction_method = str(record.get("extraction_method") or "").strip().lower()
    has_sentence_shape = "_METRIC_SENT_" in object_id or "sentence" in extraction_method
    if not has_sentence_shape:
        return False
    if not _clean_text(record.get("segment")):
        return False
    if not _clean_text(record.get("metric_name")):
        return False
    if _safe_float(record.get("value")) is None:
        return False
    if not _clean_text(record.get("period")):
        return False
    return True


def is_structured_product_metric_record(record: dict[str, Any]) -> bool:
    return is_structured_table_metric_record(record) or is_structured_sentence_metric_record(record)


def structured_record_has_candidate_measurement(record: dict[str, Any]) -> bool:
    if _safe_float(record.get("value")) is None:
        return False
    if structured_cell_kind(record) == "change_value":
        return False
    raw = str(record.get("raw_value") or "")
    unit = str(record.get("unit") or "").lower()
    text = structured_metric_text(record)
    if unit in STRUCTURED_CURRENCY_UNIT_FACTORS or unit in {"usd", "percent"}:
        return True
    if "$" in raw or "%" in raw:
        return True
    if any(token in text for token in ("deliveries", "delivered", "units", "shipments", "production", "produced", "subscribers", "backlog", "orders")):
        return True
    return False


def structured_is_change_cell(record: dict[str, Any]) -> bool:
    return structured_cell_kind(record) == "change_value"


def structured_is_non_period_or_decomposition_cell(record: dict[str, Any]) -> bool:
    column = str(record.get("column_label") or "").lower()
    if not column:
        return False
    if re.fullmatch(r"\(?[a-z\s,]+ dollars\)?", column):
        return True
    disallowed_terms = (
        "sales volume",
        "price realization",
        "currency",
        "inter-segment",
        "intersegment",
        "other",
        "% contribution",
        "percentage contribution",
        "aro liability",
        "liability",
        "eliminations",
        "corporate",
    )
    return any(term in column for term in disallowed_terms)


def structured_cell_kind(record: dict[str, Any]) -> str:
    metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
    kind = str(record.get("cell_kind") or metadata.get("cell_kind") or "").strip().lower()
    if kind:
        return kind
    column = str(record.get("column_label") or "").lower()
    if not column:
        return "period_value"
    if " vs " in column or " vs." in column or "versus" in column or "change" in column or "variation" in column:
        return "change_value"
    if "%" in column and len(re.findall(r"(?:20\d{2}|19\d{2})", column)) > 1:
        return "change_value"
    return "period_value"


def structured_table_object_id(record: dict[str, Any]) -> str | None:
    metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
    value = record.get("table_object_id") or metadata.get("table_object_id")
    return str(value) if value not in (None, "", [], {}) else None


def structured_metric_candidate_id(record: dict[str, Any], metric_family: str) -> str:
    return _stable_id(
        "STRUCTUREDPRODUCTKPI",
        record.get("object_id"),
        metric_family,
        record.get("row_label"),
        record.get("column_label"),
        record.get("raw_value"),
    )


def structured_metric_text(record: dict[str, Any]) -> str:
    parts = [
        record.get("metric_name"),
        record.get("row_label"),
        record.get("column_label"),
        record.get("segment"),
        record.get("section"),
        record.get("subsection"),
        record.get("context"),
        record.get("preview"),
    ]
    return _clean_text(" ".join(str(part) for part in parts if part)).lower()


def match_structured_product_node(record: dict[str, Any], nodes: list[dict[str, Any]]) -> dict[str, Any] | None:
    best: dict[str, Any] | None = None
    fields = [
        ("row_label", record.get("row_label"), 20),
        ("metric_name", record.get("metric_name"), 18),
        ("segment", record.get("segment"), 16),
        ("preview", record.get("preview"), 8),
    ]
    for field_name, value, boost in fields:
        text = _clean_text(value)
        if not text:
            continue
        match = match_product_node(text, nodes)
        if not match:
            continue
        score = int(match.get("score") or 0) + boost
        candidate = {**match, "match_method": f"structured_{field_name}_alias_exact", "score": score}
        if best is None or score > int(best.get("score") or 0):
            best = candidate
    return best


def infer_structured_metric_families(record: dict[str, Any], source_context: dict[str, Any] | None) -> list[str]:
    citation = structured_metric_citation(record, source_context, max_citation_chars=900).lower()
    context_text = structured_metric_context_text(record, source_context, max_chars=1600).lower()
    focused_context = _clean_text(
        " ".join(
            str(record.get(key) or "")
            for key in ("metric_name", "row_label", "column_label", "segment", "subsection", "context", "preview")
        )
    ).lower()
    families: list[str] = []
    unit = str(record.get("unit") or "").lower()
    raw = str(record.get("raw_value") or "").lower()
    has_currency_value = unit in STRUCTURED_CURRENCY_UNIT_FACTORS or unit == "usd" or "$" in raw
    has_percent_value = unit == "percent" or "%" in raw
    if (has_currency_value or has_percent_value) and structured_has_product_revenue_context(record, citation, source_context):
        families.append("product_revenue")
    if re.search(r"\b(?:backlog|bookings|orders|remaining performance obligations|rpo)\b", focused_context):
        families.append("backlog_or_orders")
    if not (has_currency_value or has_percent_value) and re.search(r"\b(?:deliveries|delivered|unit sales|units sold|vehicles delivered)\b", focused_context):
        families.append("unit_sales_or_deliveries")
    if not (has_currency_value or has_percent_value) and re.search(r"\b(?:shipments|shipped|shipped volume)\b", focused_context):
        families.append("shipments")
    if not has_percent_value and re.search(r"\b(?:subscribers|paid subscribers|arpu|average revenue per user|accounts)\b", focused_context):
        families.append("subscribers_or_arpu")
    if re.search(r"\b(?:same-store sales|comparable sales|comparable store sales|comps)\b", focused_context):
        families.append("same_store_sales")
    if not (has_currency_value or has_percent_value) and re.search(r"\b(?:production|throughput|produced|utilization)\b", focused_context):
        families.append("production_or_throughput")
    return list(dict.fromkeys(families))


def structured_has_product_revenue_context(record: dict[str, Any], citation: str, source_context: dict[str, Any] | None = None) -> bool:
    focused = _clean_text(
        " ".join(
            str(record.get(key) or "")
            for key in ("metric_name", "row_label", "column_label", "subsection", "context", "preview")
        )
    ).lower()
    context_text = structured_metric_context_text(record, source_context, max_chars=1600).lower()
    if structured_context_is_non_revenue_financial_statement(context_text):
        return False
    if re.search(r"\b(?:revenue|revenues|net sales|sales and revenues|net sales from|sales of|sales from)\b", focused):
        return True
    if any(re.search(pattern, context_text, flags=re.I) for pattern in STRUCTURED_REVENUE_CONTEXT_PATTERNS):
        return True
    return False


def structured_measurement(record: dict[str, Any], metric_family: str, citation: str) -> tuple[dict[str, Any] | None, str]:
    value = _safe_float(record.get("value"))
    if value is None:
        return None, "no_numeric_value"
    raw_value_text = _clean_text(record.get("raw_value") or record.get("preview") or value)
    unit = str(record.get("unit") or "").strip().lower()
    if "$" in raw_value_text and unit == "percent":
        return None, "unit_value_conflict"
    if raw_value_has_non_atomic_text(raw_value_text):
        return None, "raw_value_not_atomic_numeric_cell"
    if metric_family in {"product_revenue", "backlog_or_orders"}:
        currency = structured_currency_measurement(value, unit, raw_value_text, citation)
        if currency:
            return currency, ""
        if metric_family == "product_revenue":
            percent = structured_percent_of_revenue_measurement(value, unit, raw_value_text, citation)
            if percent:
                return percent, ""
            if unit == "percent" or "%" in raw_value_text:
                return None, "percent_value_without_revenue_share_context"
        units = structured_count_measurement(value, unit, raw_value_text, citation, metric_family)
        if units and metric_family == "backlog_or_orders":
            return units, ""
        return None, "no_value_unit_match"
    if metric_family == "same_store_sales":
        if unit == "percent" or "%" in raw_value_text:
            return {
                "value": value,
                "unit": "percent_change",
                "unit_category": "percent",
                "raw_value_text": raw_value_text,
                "scale": "percent",
            }, ""
        return None, "no_value_unit_match"
    if metric_family == "subscribers_or_arpu":
        if re.search(r"\b(?:arpu|average revenue per user)\b", citation, flags=re.I):
            currency = structured_currency_measurement(value, unit, raw_value_text, citation, allow_unscaled=True)
            if currency:
                currency["unit_category"] = "currency_per_user"
                return currency, ""
        count = structured_count_measurement(value, unit, raw_value_text, citation, metric_family)
        if count:
            return count, ""
        return None, "no_value_unit_match"
    count = structured_count_measurement(value, unit, raw_value_text, citation, metric_family)
    if count:
        return count, ""
    return None, "no_value_unit_match"


def structured_currency_measurement(
    value: float,
    unit: str,
    raw_value_text: str,
    citation: str,
    *,
    allow_unscaled: bool = False,
) -> dict[str, Any] | None:
    if unit in STRUCTURED_CURRENCY_UNIT_FACTORS:
        scale, factor = STRUCTURED_CURRENCY_UNIT_FACTORS[unit]
        return {
            "value": value * factor,
            "unit": "USD",
            "unit_category": "currency",
            "raw_value_text": raw_value_text,
            "scale": scale,
        }
    raw_currency = _extract_currency(raw_value_text)
    if raw_currency and str(raw_currency.get("scale") or "") != "ones":
        return raw_currency
    lower = citation.lower()
    if unit == "usd" or "$" in raw_value_text:
        if re.search(r"\b(?:dollars|amounts|in)\s+in\s+billions\b|\bin\s+billions\b|\bbillions of dollars\b", lower):
            return {
                "value": value * 1_000_000_000.0,
                "unit": "USD",
                "unit_category": "currency",
                "raw_value_text": raw_value_text,
                "scale": "billion",
            }
        if re.search(r"\b(?:dollars|amounts|in)\s+in\s+millions\b|\bin\s+millions\b|\bmillions of dollars\b", lower):
            return {
                "value": value * 1_000_000.0,
                "unit": "USD",
                "unit_category": "currency",
                "raw_value_text": raw_value_text,
                "scale": "million",
            }
        if allow_unscaled:
            return {
                "value": value,
                "unit": "USD",
                "unit_category": "currency",
                "raw_value_text": raw_value_text,
                "scale": "ones",
            }
    return None


def structured_percent_of_revenue_measurement(value: float, unit: str, raw_value_text: str, citation: str) -> dict[str, Any] | None:
    if "%" not in raw_value_text:
        return None
    if not re.search(
        r"\b(?:of|as a percentage of|percentage of|represented|accounted for|comprised)\b.{0,120}\b(?:revenue|revenues|net sales|sales)\b|"
        r"\b(?:revenue|revenues|net sales|sales)\b.{0,120}\b(?:mix|percentage|represented|accounted for|comprised)\b",
        citation,
        flags=re.I,
    ):
        return None
    return {
        "value": value,
        "unit": "percent_of_revenue",
        "unit_category": "percent_of_revenue",
        "raw_value_text": raw_value_text,
        "scale": "percent",
    }


def structured_count_measurement(
    value: float,
    unit: str,
    raw_value_text: str,
    citation: str,
    metric_family: str,
) -> dict[str, Any] | None:
    lower = citation.lower()
    if unit in STRUCTURED_CURRENCY_UNIT_FACTORS or unit == "usd" or "$" in raw_value_text:
        return None
    if unit == "percent" or "%" in raw_value_text:
        return None
    scale = 1.0
    if re.search(r"\b(?:million|millions)\b", raw_value_text.lower()):
        scale = 1_000_000.0
    elif re.search(r"\b(?:thousand|thousands)\b", raw_value_text.lower()):
        scale = 1_000.0
    if metric_family == "unit_sales_or_deliveries" and re.search(r"\b(?:vehicle|vehicles|deliveries|delivered)\b", lower):
        out_unit = "vehicles" if re.search(r"\bvehicles?\b", lower) else "devices" if re.search(r"\bdevices?\b", lower) else "systems" if re.search(r"\bsystems?\b", lower) else "units"
        return {"value": value * scale, "unit": out_unit, "unit_category": UNIT_CATEGORY_BY_OUTPUT_UNIT.get(out_unit, out_unit), "raw_value_text": raw_value_text, "scale": "count"}
    if metric_family == "shipments" and re.search(r"\b(?:shipments|shipped|units|devices|systems|tons|barrels)\b", lower):
        out_unit = "metric_tons" if "metric ton" in lower else "tons" if re.search(r"\btons?\b", lower) else "barrels" if "barrel" in lower else "units"
        return {"value": value * scale, "unit": out_unit, "unit_category": UNIT_CATEGORY_BY_OUTPUT_UNIT.get(out_unit, out_unit), "raw_value_text": raw_value_text, "scale": "count"}
    if metric_family == "backlog_or_orders" and re.search(r"\b(?:units|systems|vehicles|months)\b", lower):
        out_unit = "months" if "months" in lower else "systems" if "systems" in lower else "vehicles" if "vehicles" in lower else "units"
        return {"value": value * scale, "unit": out_unit, "unit_category": UNIT_CATEGORY_BY_OUTPUT_UNIT.get(out_unit, out_unit), "raw_value_text": raw_value_text, "scale": "count"}
    if metric_family == "subscribers_or_arpu" and re.search(r"\b(?:subscribers|accounts|users|members)\b", lower):
        out_unit = "accounts" if "accounts" in lower else "subscribers"
        return {"value": value * scale, "unit": out_unit, "unit_category": out_unit, "raw_value_text": raw_value_text, "scale": "count"}
    if metric_family == "production_or_throughput" and re.search(r"\b(?:production|produced|throughput|barrels per day|bpd|mwh|megawatt hours|tons|units)\b", lower):
        if re.search(r"\bsales from\b.{0,80}\bproduction\b|\bproduction\b.{0,80}\bsales\b", lower):
            return None
        out_unit = "barrels_per_day" if "barrels per day" in lower or "bpd" in lower or "b/d" in lower else "megawatt_hours" if "mwh" in lower or "megawatt hours" in lower else "tons" if re.search(r"\btons?\b", lower) else "units"
        return {"value": value * scale, "unit": out_unit, "unit_category": UNIT_CATEGORY_BY_OUTPUT_UNIT.get(out_unit, out_unit), "raw_value_text": raw_value_text, "scale": "count"}
    return None


def raw_value_has_non_atomic_text(raw_value_text: str) -> bool:
    text = _clean_text(raw_value_text)
    if not re.search(r"[A-Za-z]", text):
        return False
    allowed = re.sub(
        r"\b(?:us|usd|dollars?|dollar|billion|billions|million|millions|thousand|thousands|units?|vehicles?|devices?|systems?|subscribers?|accounts?|barrels?|tons?|metric|mwh|megawatt|hours?|bpd|per|day)\b",
        " ",
        text,
        flags=re.I,
    )
    allowed = re.sub(r"[$,%().,\-\s0-9]", " ", allowed)
    return bool(re.search(r"[A-Za-z]", allowed))


def infer_structured_period(record: dict[str, Any]) -> dict[str, Any]:
    period_value = str(record.get("period") or record.get("column_label") or "").strip()
    year_match = re.search(r"(?:20\d{2}|19\d{2})", period_value)
    if year_match:
        year = int(year_match.group(0))
    else:
        year = None
    if not year:
        return {"period": None, "period_type": record.get("period_type"), "period_end": record.get("period_end"), "period_role": record.get("period_role")}
    return {
        "period": f"FY{year}",
        "period_type": record.get("period_type") or "annual",
        "period_end": record.get("period_end"),
        "period_role": record.get("period_role") or "annual",
    }


def infer_structured_metric_name(record: dict[str, Any], metric_family: str) -> str:
    name = _clean_text(record.get("metric_name") or record.get("row_label") or "")
    lower = name.lower()
    if metric_family == "product_revenue":
        if "net sales" in lower:
            return "net sales"
        if "sales and revenues" in lower:
            return "sales and revenues"
        if "revenue" in lower:
            return "revenue"
        if "sales" in lower:
            return "sales"
        return "product revenue"
    if metric_family == "backlog_or_orders":
        if "backlog" in lower:
            return "backlog"
        if "booking" in lower:
            return "bookings"
        if "order" in lower:
            return "orders"
        return "backlog/orders"
    if metric_family == "unit_sales_or_deliveries":
        return "deliveries" if "deliver" in lower else "unit sales"
    return infer_metric_name(metric_family, name)


def structured_metric_citation(
    record: dict[str, Any],
    source_context: dict[str, Any] | None,
    *,
    max_citation_chars: int,
) -> str:
    source_text = str((source_context or {}).get("text") or "")
    window = structured_source_window(record, source_text, max_chars=max_citation_chars)
    table_prefix = structured_source_table_prefix(record, source_text, max_chars=360)
    parts = [
        f"row={_clean_text(record.get('row_label') or record.get('metric_name') or '')}",
        f"column={_clean_text(record.get('column_label') or '')}",
        f"value={_clean_text(record.get('raw_value') or '')}",
        f"unit={_clean_text(record.get('unit') or '')}",
        f"section={_clean_text(record.get('section') or '')}",
        f"subsection={_clean_text(record.get('subsection') or '')}",
    ]
    context = " | ".join(part for part in parts if not part.endswith("="))
    if table_prefix:
        context = f"{context} | table_context={table_prefix}"
    if window:
        context = f"{context} | source_context={window}"
    return _clean_text(context)[:max_citation_chars]


def structured_source_window(record: dict[str, Any], source_text: str, *, max_chars: int) -> str:
    text = _clean_text(source_text)
    if not text:
        return ""
    needles = [
        _clean_text(record.get("row_label") or ""),
        _clean_text(record.get("metric_name") or ""),
        _clean_text(record.get("raw_value") or ""),
    ]
    lower = text.lower()
    positions = [lower.find(needle.lower()) for needle in needles if needle and lower.find(needle.lower()) >= 0]
    if not positions:
        return text[:max_chars]
    start = min(positions)
    return _window(text, start, start + max(len(item) for item in needles if item), max_chars=max_chars)


def structured_source_table_prefix(record: dict[str, Any], source_text: str, *, max_chars: int) -> str:
    text = _clean_text(source_text)
    if not text:
        return ""
    row_label = _clean_text(record.get("row_label") or record.get("metric_name") or "")
    lower = text.lower()
    row_pos = lower.find(row_label.lower()) if row_label else -1
    if row_pos < 0:
        return text[:max_chars]
    table_start = lower.rfind("[table_start", 0, row_pos)
    start = max(0, table_start - max_chars // 2) if table_start >= 0 else max(0, row_pos - max_chars)
    return text[start:row_pos].strip()[-max_chars:]


def structured_metric_context_text(record: dict[str, Any], source_context: dict[str, Any] | None, *, max_chars: int) -> str:
    source_text = str((source_context or {}).get("text") or "")
    parts = [
        record.get("metric_name"),
        record.get("row_label"),
        record.get("column_label"),
        record.get("segment"),
        record.get("section"),
        record.get("subsection"),
        record.get("context"),
        record.get("preview"),
        structured_source_table_prefix(record, source_text, max_chars=max_chars // 3),
        structured_source_window(record, source_text, max_chars=max_chars),
    ]
    return _clean_text(" ".join(str(part) for part in parts if part))


def structured_context_is_non_revenue_financial_statement(context_text: str) -> bool:
    lower = context_text.lower()
    if any(re.search(pattern, lower, flags=re.I) for pattern in STRUCTURED_NON_REVENUE_CONTEXT_PATTERNS):
        return not any(re.search(pattern, lower, flags=re.I) for pattern in STRUCTURED_REVENUE_CONTEXT_PATTERNS)
    return False


def load_chunk_source_contexts(chunk_inputs: Iterable[Path], source_ids: set[str]) -> dict[str, dict[str, Any]]:
    needed = {str(item or "").strip() for item in source_ids if str(item or "").strip()}
    contexts: dict[str, dict[str, Any]] = {}
    if not needed:
        return contexts
    for path in chunk_inputs:
        resolved = _resolve(path)
        if not resolved.exists():
            continue
        with resolved.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                row = json.loads(line)
                if not isinstance(row, dict):
                    continue
                chunk_id = str(row.get("chunk_id") or row.get("evidence_id") or "").strip()
                if chunk_id not in needed:
                    continue
                contexts[chunk_id] = {
                    "chunk_id": chunk_id,
                    "ticker": row.get("ticker"),
                    "company": row.get("company") or row.get("company_name"),
                    "fiscal_year": row.get("fiscal_year"),
                    "source_url": row.get("source_url"),
                    "local_path": row.get("local_path"),
                    "period_end": row.get("period_end"),
                    "form_type": row.get("form_type") or row.get("source_type"),
                    "section": row.get("section"),
                    "subsection": row.get("subsection"),
                    "text": row.get("text") or "",
                }
                if len(contexts) == len(needed):
                    return contexts
    return contexts


def select_metric_citation_span(snippet: str, metric_family: str, *, max_citation_chars: int) -> str:
    text = _clean_text(snippet)
    if not text:
        return ""
    keywords = METRIC_KEYWORDS.get(metric_family) or [metric_family.replace("_", " ")]
    lower = text.lower()
    positions = [lower.find(keyword.lower()) for keyword in keywords if lower.find(keyword.lower()) >= 0]
    if not positions:
        return text[:max_citation_chars]
    start = min(positions)
    return _window(text, start, start + 30, max_chars=max_citation_chars)


def match_product_node(citation: str, nodes: list[dict[str, Any]]) -> dict[str, Any] | None:
    lower = citation.lower()
    best: dict[str, Any] | None = None
    for node in nodes:
        aliases = list(node.get("aliases") or [])
        aliases.append(str(node.get("canonical_name") or ""))
        for alias in aliases:
            term = _clean_text(str(alias))
            if not is_usable_alias(term):
                continue
            if not _contains_term(lower, term.lower()):
                continue
            score = len(term) + int(node.get("evidence_count") or 0)
            if node.get("node_type") == "segment":
                score += 4
            if best is None or score > int(best.get("score") or 0):
                best = {
                    "node": node,
                    "matched_alias": term,
                    "match_method": "citation_alias_exact",
                    "score": score,
                }
    return best


def is_usable_alias(alias: str) -> bool:
    lower = alias.lower().strip()
    if lower in GENERIC_ALIAS_TERMS:
        return False
    if len(lower) < 3:
        return False
    if len(lower.split()) == 1 and lower in {"ai", "ev", "it"}:
        return False
    return True


def extract_measurement(citation: str, metric_family: str) -> tuple[dict[str, Any] | None, str]:
    if metric_family == "product_revenue":
        if _contains_change_rate_without_level(citation):
            return None, "change_rate_without_level_value"
        currency = _extract_currency(citation)
        if currency:
            return currency, ""
        percent = _extract_percent(citation)
        if percent and re.search(r"\b(?:of|as a percentage of|represented|accounted for)\b.{0,60}\b(?:revenue|net sales|sales)\b", citation, flags=re.I):
            percent["unit"] = "percent_of_revenue"
            percent["unit_category"] = "percent_of_revenue"
            return percent, ""
        return None, "no_value_unit_match"
    if metric_family == "same_store_sales":
        percent = _extract_percent(citation)
        if percent:
            percent["unit"] = "percent_change"
            percent["unit_category"] = "percent"
            return percent, ""
        return None, "no_value_unit_match"
    if metric_family == "subscribers_or_arpu":
        arpu = _extract_currency(citation)
        if arpu and re.search(r"\b(?:arpu|average revenue per user)\b", citation, flags=re.I):
            arpu["unit"] = "USD"
            arpu["unit_category"] = "currency_per_user"
            return arpu, ""
        subscribers = _extract_count_with_unit(citation, ("subscribers", "paid subscribers", "accounts"))
        if subscribers:
            return subscribers, ""
        return None, "no_value_unit_match"
    if metric_family == "backlog_or_orders":
        currency = _extract_currency(citation)
        if currency:
            return currency, ""
        units = _extract_count_with_unit(citation, ("units", "systems", "vehicles", "months"))
        if units:
            return units, ""
        return None, "no_value_unit_match"
    if metric_family == "unit_sales_or_deliveries":
        units = _extract_count_with_unit(citation, ("vehicles", "units", "devices", "systems"))
        if units:
            return units, ""
        return None, "no_value_unit_match"
    if metric_family == "shipments":
        units = _extract_count_with_unit(citation, ("shipments", "units", "devices", "systems", "metric tons", "tons", "barrels"))
        if units:
            if units["unit"] == "shipments":
                units["unit"] = "units"
                units["unit_category"] = "units"
            return units, ""
        return None, "no_value_unit_match"
    if metric_family == "production_or_throughput":
        units = _extract_count_with_unit(citation, ("barrels per day", "bpd", "barrels", "metric tons", "tons", "megawatt hours", "mwh", "units"))
        if units:
            return units, ""
        return None, "no_value_unit_match"
    return None, "unsupported_metric_family"


def validate_measurement_unit(metric_family: str, measurement: dict[str, Any], ontology: dict[str, Any]) -> str:
    family = ((ontology.get("metric_families") or {}).get(metric_family) or {})
    allowed = {str(item).lower() for item in family.get("allowed_units") or []}
    if not allowed:
        return ""
    unit_category = str(measurement.get("unit_category") or UNIT_CATEGORY_BY_OUTPUT_UNIT.get(str(measurement.get("unit") or ""), "")).lower()
    if unit_category in allowed:
        return ""
    if unit_category == "currency_per_user" and "currency_per_user" in allowed:
        return ""
    return "unit_not_allowed_for_metric_family"


def validate_measurement_context(metric_family: str, measurement: dict[str, Any], citation: str) -> str:
    lower = citation.lower()
    unit_category = str(measurement.get("unit_category") or "")
    if metric_family in {"product_revenue", "backlog_or_orders"} and unit_category == "currency":
        if str(measurement.get("scale") or "") == "ones":
            return "ambiguous_currency_scale"
    if metric_family == "product_revenue":
        if re.search(r"\b(?:increased|decreased|rose|declined|grew)\s+(?:by\s+)?(?:US\$|\$)", citation, flags=re.I):
            return "change_amount_without_level_value"
        if unit_category == "percent_of_revenue" and any(
            token in lower
            for token in (
                "customer accounted",
                "customers account",
                "largest retailer",
                "top ten customers",
                "distribution channels accounted",
                "direct distribution channels",
                "international operations",
                "sales through",
            )
        ):
            return "context_not_product_revenue"
        if any(
            token in lower
            for token in (
                "equity distribution sales agreement",
                "common stock",
                "atm program",
                "projected net sales would",
                "impairment",
            )
        ):
            return "context_not_product_revenue"
    if unit_category == "percent_of_revenue" and ambiguous_percent_allocation(citation):
        return "ambiguous_percent_allocation_requires_table_or_list_parser"
    return ""


def validate_product_node_for_metric(metric_family: str, product_node: dict[str, Any]) -> str:
    node_type = str(product_node.get("node_type") or "").lower()
    label = str(product_node.get("canonical_name") or "")
    if product_node_label_is_financial_or_metric_item(label):
        return "product_node_label_not_metric_bearing"
    non_metric_bearing = ("end_market", "customer_market", "use_case")
    if metric_family in {
        "product_revenue",
        "unit_sales_or_deliveries",
        "shipments",
        "backlog_or_orders",
        "subscribers_or_arpu",
        "production_or_throughput",
    } and any(token in node_type for token in non_metric_bearing):
        return "product_node_type_not_metric_bearing"
    return ""


def product_node_label_is_financial_or_metric_item(label: str) -> bool:
    lower = _clean_text(label).lower()
    if structured_label_is_generic_or_metric(lower):
        return True
    if any(term in lower for term in STRUCTURED_REPAIR_FORBIDDEN_LABEL_TERMS):
        return True
    if re.search(
        r"\b(?:income|loss|expense|expenses|cost|costs|margin|tax|assets?|liabilities|cash|investment|investments|maturities|proceeds|rebates|deferred|accrued|thereafter|non-current|current|rpo|remaining performance obligations|as a percentage|percentage of|change)\b",
        lower,
    ):
        return True
    return False


def validate_product_measurement_relation(
    metric_family: str,
    product_match: dict[str, Any],
    measurement: dict[str, Any],
    citation: str,
) -> str:
    alias = str(product_match.get("matched_alias") or "")
    raw_value = str(measurement.get("raw_value_text") or "")
    lower = citation.lower()
    alias_pos = lower.find(alias.lower())
    raw_pos = lower.find(raw_value.lower())
    if alias_pos < 0 or raw_pos < 0:
        return "no_product_value_relation"
    left = min(alias_pos, raw_pos)
    right = max(alias_pos + len(alias), raw_pos + len(raw_value))
    span = lower[left:right]
    distance = abs(raw_pos - alias_pos)
    if metric_family == "product_revenue":
        metric_pos = metric_position(lower, ("revenue", "net sales", "sales"))
        if metric_pos < 0:
            return "no_product_metric_relation"
        if distance > 180:
            return "no_product_value_relation"
        if sentence_boundary_between(lower, alias_pos, raw_pos):
            return "product_value_cross_sentence"
        if str(measurement.get("unit_category") or "") == "percent_of_revenue":
            if not (alias_pos < raw_pos and re.search(r"\b(?:represented|accounted for|comprised|was|were)\b", lower[alias_pos:raw_pos + len(raw_value)])):
                return "value_not_attributed_to_product"
            return ""
        if not (alias_pos <= metric_pos <= raw_pos):
            return "value_not_attributed_to_product"
        return ""
    if metric_family == "backlog_or_orders":
        if alias_pos > raw_pos or distance > 180:
            return "value_not_attributed_to_product"
        if sentence_boundary_between(lower, alias_pos, raw_pos):
            return "product_value_cross_sentence"
        if not re.search(r"\b(?:backlog|bookings|orders|remaining performance obligations|rpo)\b", span):
            return "no_product_metric_relation"
        return ""
    if metric_family == "subscribers_or_arpu":
        if str(measurement.get("unit_category") or "") == "currency_per_user":
            metric_pos = min((pos for pos in [lower.find("arpu"), lower.find("average revenue per user")] if pos >= 0), default=-1)
            if metric_pos < 0 or abs(raw_pos - metric_pos) > 60:
                return "value_not_attributed_to_arpu"
        if distance > 180:
            return "no_product_value_relation"
        return ""
    if metric_family in {"unit_sales_or_deliveries", "shipments", "production_or_throughput", "same_store_sales"}:
        if alias_pos > raw_pos or distance > 180:
            return "value_not_attributed_to_product"
        if sentence_boundary_between(lower, alias_pos, raw_pos):
            return "product_value_cross_sentence"
        if not has_valid_metric_context(span, metric_family):
            return "no_product_metric_relation"
        return ""
    return ""


def _extract_currency(text: str) -> dict[str, Any] | None:
    pattern = re.compile(
        r"(?P<raw>(?:US\$|\$)\s?\(?[0-9][0-9,]*(?:\.[0-9]+)?\)?\s*(?P<scale>billion|billions|million|millions|thousand|thousands)?)",
        flags=re.I,
    )
    match = pattern.search(text)
    if not match:
        match = re.search(
            r"(?P<raw>[0-9][0-9,]*(?:\.[0-9]+)?\s*(?P<scale>billion|billions|million|millions)\s+(?:of\s+)?(?:revenue|net sales|sales|backlog|orders|bookings))",
            text,
            flags=re.I,
        )
    if not match:
        return None
    raw = match.group("raw")
    number_match = re.search(r"[0-9][0-9,]*(?:\.[0-9]+)?", raw)
    if not number_match:
        return None
    number = float(number_match.group(0).replace(",", ""))
    scale = str(match.groupdict().get("scale") or "").lower()
    value = number * SCALE_FACTORS.get(scale, 1.0)
    return {
        "value": value,
        "unit": "USD",
        "unit_category": "currency",
        "raw_value_text": raw.strip(),
        "scale": scale or "ones",
    }


def _extract_percent(text: str) -> dict[str, Any] | None:
    match = re.search(r"(?P<raw>\(?[0-9][0-9,]*(?:\.[0-9]+)?\)?\s?%)", text)
    if not match:
        return None
    raw = match.group("raw")
    number = float(re.search(r"[0-9][0-9,]*(?:\.[0-9]+)?", raw).group(0).replace(",", ""))
    return {
        "value": number,
        "unit": "percent",
        "unit_category": "percent",
        "raw_value_text": raw.strip(),
        "scale": "percent",
    }


def _extract_count_with_unit(text: str, allowed_units: tuple[str, ...]) -> dict[str, Any] | None:
    unit_pattern = "|".join(re.escape(unit) for unit in sorted(allowed_units, key=len, reverse=True))
    pattern = re.compile(
        rf"(?P<raw>[0-9][0-9,]*(?:\.[0-9]+)?\s*(?P<scale>billion|billions|million|millions|thousand|thousands)?\s*(?P<unit>{unit_pattern}))\b",
        flags=re.I,
    )
    match = pattern.search(text)
    if not match:
        return None
    raw = match.group("raw")
    number = float(re.search(r"[0-9][0-9,]*(?:\.[0-9]+)?", raw).group(0).replace(",", ""))
    scale = str(match.groupdict().get("scale") or "").lower()
    output_unit = normalize_output_unit(str(match.group("unit") or ""))
    value = number * SCALE_FACTORS.get(scale, 1.0)
    return {
        "value": value,
        "unit": output_unit,
        "unit_category": UNIT_CATEGORY_BY_OUTPUT_UNIT.get(output_unit, output_unit),
        "raw_value_text": raw.strip(),
        "scale": scale or "ones",
    }


def normalize_output_unit(unit: str) -> str:
    lower = unit.lower().strip()
    return {
        "paid subscribers": "subscribers",
        "bpd": "barrels_per_day",
        "barrels per day": "barrels_per_day",
        "metric tons": "metric_tons",
        "megawatt hours": "megawatt_hours",
        "mwh": "megawatt_hours",
        "shipments": "shipments",
    }.get(lower, lower.replace(" ", "_"))


def _contains_change_rate_without_level(text: str) -> bool:
    has_change_word = re.search(r"\b(?:increased|decreased|grew|declined|growth|decrease|increase)\b", text, flags=re.I)
    has_percent = re.search(r"[0-9][0-9,]*(?:\.[0-9]+)?\s?%", text)
    has_currency = _extract_currency(text) is not None
    return bool(has_change_word and has_percent and not has_currency)


def infer_period(row: dict[str, Any], citation: str) -> dict[str, Any]:
    fiscal_year = _safe_int(row.get("fiscal_year"))
    period_end = row.get("period_end")
    period_type = "fiscal_year"
    if re.search(r"\b(?:three months|quarter|quarterly)\b", citation, flags=re.I):
        period_type = "interim_or_quarter"
    if re.search(r"\bas of\b", citation, flags=re.I):
        period_type = "point_in_time"
    return {
        "period": f"FY{fiscal_year}" if fiscal_year else "",
        "period_type": period_type,
        "period_end": period_end,
    }


def infer_metric_name(metric_family: str, citation: str) -> str:
    lower = citation.lower()
    for keyword in METRIC_KEYWORDS.get(metric_family) or []:
        if keyword.lower() in lower:
            return keyword
    return metric_family.replace("_", " ")


def table_layout_requires_table_parser(citation: str) -> bool:
    if "[TABLE_START" not in citation and "|" not in citation:
        return False
    numeric_count = len(re.findall(r"(?:\$|US\$)?\s?[0-9][0-9,]*(?:\.[0-9]+)?\s?(?:%|billion|million|thousand)?", citation, flags=re.I))
    return numeric_count > 1


def has_valid_metric_context(citation: str, metric_family: str) -> bool:
    lower = citation.lower()
    if metric_family == "backlog_or_orders":
        if any(token in lower for token in ("backlog", "bookings", "remaining performance obligations", "rpo")):
            return True
        order_context_patterns = (
            r"\bcustomer orders\b",
            r"\bnew orders\b",
            r"\bfirm orders\b",
            r"\borders received\b",
            r"\borders were\b",
            r"\borders totaled\b",
            r"\borders? for\b",
        )
        if any(re.search(pattern, lower) for pattern in order_context_patterns):
            return True
        for match in re.finditer(r"\borders\b", lower):
            left = lower[max(0, match.start() - 8) : match.start()]
            right = lower[match.end() : match.end() + 8]
            if "in " in left or right.startswith(" to"):
                continue
            return True
        return False
    return any(keyword.lower() in lower for keyword in METRIC_KEYWORDS.get(metric_family) or [metric_family.replace("_", " ")])


def metric_position(lower_citation: str, keywords: tuple[str, ...]) -> int:
    positions = [lower_citation.find(keyword) for keyword in keywords if lower_citation.find(keyword) >= 0]
    return min(positions) if positions else -1


def sentence_boundary_between(lower_citation: str, first_pos: int, second_pos: int) -> bool:
    left = min(first_pos, second_pos)
    right = max(first_pos, second_pos)
    between = lower_citation[left:right]
    return re.search(r"(?:\.\s+|;\s+|\?\s+|!\s+)", between) is not None


def ambiguous_percent_allocation(citation: str) -> bool:
    lower = citation.lower()
    percent_count = len(re.findall(r"[0-9][0-9,]*(?:\.[0-9]+)?\s?%", lower))
    if percent_count > 1:
        return True
    if "respectively" in lower:
        return True
    if re.search(r"\b(?:those|these)\s+(?:six|seven|eight|nine|ten|\d+)\s+brands\b", lower):
        return True
    if re.search(r"\b(?:brands|products|segments)\s+(?:are|were|include|included)\b", lower) and re.search(r"\brepresent(?:ed|s)?\b", lower):
        return True
    return False


def build_summary(
    *,
    rules_path: Path,
    taxonomy_path: Path,
    metric_path: Path,
    universe_path: Path,
    sector_depth_path: Path,
    ontology_path: Path,
    chunk_inputs: list[Path],
    normalized_output: Path,
    aliases_output: Path,
    review_output: Path,
    facts_output: Path,
    rejections_output: Path,
    summary_output: Path,
    report_output: Path,
    taxonomy_candidates: list[dict[str, Any]],
    metric_candidates: list[dict[str, Any]],
    direct_metric_candidates: list[dict[str, Any]],
    structured_sqlite_inputs: list[Path],
    structured_scan_summary: dict[str, Any] | None,
    structured_taxonomy_repair_summary: dict[str, Any] | None,
    normalized_rows: list[dict[str, Any]],
    alias_rows: list[dict[str, Any]],
    review_rows: list[dict[str, Any]],
    kpi_facts: list[dict[str, Any]],
    kpi_rejections: list[dict[str, Any]],
    generated_at: str,
) -> dict[str, Any]:
    taxonomy_tickers = {str(row.get("ticker")) for row in taxonomy_candidates if row.get("ticker")}
    normalized_tickers = {str(row.get("ticker")) for row in normalized_rows if row.get("ticker")}
    all_metric_candidates = [*metric_candidates, *direct_metric_candidates]
    metric_tickers = {str(row.get("ticker")) for row in all_metric_candidates if row.get("ticker")}
    fact_tickers = {str(row.get("ticker")) for row in kpi_facts if row.get("ticker")}
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "status": "pass",
        "generated_at": generated_at,
        "inputs": {
            "rules_config": _repo_path(rules_path),
            "taxonomy_candidates": _repo_path(taxonomy_path),
            "metric_candidates": _repo_path(metric_path),
            "universe_manifest": _repo_path(universe_path),
            "sector_depth_config": _repo_path(sector_depth_path),
            "metric_ontology": _repo_path(ontology_path),
            "direct_chunk_inputs": [_repo_path(path) for path in chunk_inputs],
            "structured_object_sqlites": [_repo_path(path) for path in structured_sqlite_inputs],
        },
        "outputs": {
            "normalized_taxonomy": _repo_path(normalized_output),
            "taxonomy_aliases": _repo_path(aliases_output),
            "taxonomy_review_queue": _repo_path(review_output),
            "parser_verified_kpi_facts": _repo_path(facts_output),
            "kpi_rejections": _repo_path(rejections_output),
            "summary": _repo_path(summary_output),
            "report": _repo_path(report_output),
        },
        "taxonomy": {
            "candidate_count": len(taxonomy_candidates),
            "candidate_ticker_count": len(taxonomy_tickers),
            "normalized_node_count": len(normalized_rows),
            "alias_row_count": len(alias_rows),
            "review_queue_count": len(review_rows),
            "normalized_ticker_count": len(normalized_tickers),
            "normalized_ticker_coverage_pct": _pct(len(normalized_tickers), len(taxonomy_tickers)),
            "industry_schema_counts": dict(sorted(Counter(str(row.get("industry_schema") or "") for row in normalized_rows).items())),
            "node_type_counts": dict(sorted(Counter(str(row.get("node_type") or "") for row in normalized_rows).items())),
            "review_reason_counts": dict(sorted(Counter(str(row.get("review_reason") or "") for row in review_rows).items())),
        },
        "kpi_parser": {
            "candidate_count": len(metric_candidates) + len(direct_metric_candidates),
            "balanced_candidate_count": len(metric_candidates),
            "direct_chunk_candidate_count": len(direct_metric_candidates),
            "candidate_ticker_count": len(metric_tickers),
            "parser_verified_fact_count": len(kpi_facts),
            "parser_verified_ticker_count": len(fact_tickers),
            "parser_verified_ticker_coverage_pct": _pct(len(fact_tickers), len(metric_tickers)),
            "fact_metric_family_counts": dict(sorted(Counter(str(row.get("metric_family") or "") for row in kpi_facts).items())),
            "fact_industry_schema_counts": dict(sorted(Counter(str(row.get("industry_schema") or "") for row in kpi_facts).items())),
            "rejection_count": len(kpi_rejections),
            "rejection_reason_counts": dict(sorted(Counter(str(row.get("rejection_reason") or "") for row in kpi_rejections).items())),
        },
        "structured_metric_kpi_parser": structured_scan_summary
        or {
            "status": "not_run",
            "parser_verified_fact_count": 0,
            "rejection_count": 0,
            "promotion_boundary": "Structured MetricObject scan was not enabled for this run.",
        },
        "structured_taxonomy_repair": structured_taxonomy_repair_summary
        or {
            "status": "not_run",
            "repaired_node_count": 0,
            "promotion_boundary": "Structured metric taxonomy repair was not enabled for this run.",
        },
        "promotion_policy": [
            "Raw product taxonomy candidates cannot enter runtime directly.",
            "Normalized taxonomy can support product structure and KPI linking only.",
            "Product KPI facts require parser_verified_fact status.",
            "Structured table metrics require row/column period cells and source URL hydration before promotion; structured sentence metrics require explicit metric, product/segment, value/unit, period, and citation fields.",
            "Rows in review_queue or kpi_rejections are context/debug only.",
        ],
    }


def render_report(summary: dict[str, Any]) -> str:
    taxonomy = summary["taxonomy"]
    kpi = summary["kpi_parser"]
    lines = [
        "# Product Taxonomy / KPI Parser 执行报告",
        "",
        f"- 生成时间：`{summary['generated_at']}`",
        f"- Taxonomy candidates：`{taxonomy['candidate_count']}`，normalized nodes：`{taxonomy['normalized_node_count']}`，review queue：`{taxonomy['review_queue_count']}`",
        f"- Normalized ticker coverage：`{taxonomy['normalized_ticker_count']}` / `{taxonomy['candidate_ticker_count']}` = `{taxonomy['normalized_ticker_coverage_pct']}%`",
        f"- KPI candidates：`{kpi['candidate_count']}`，parser-verified facts：`{kpi['parser_verified_fact_count']}`，rejections：`{kpi['rejection_count']}`",
        f"- KPI fact ticker coverage：`{kpi['parser_verified_ticker_count']}` / `{kpi['candidate_ticker_count']}` = `{kpi['parser_verified_ticker_coverage_pct']}%`",
        "",
        "## Boundary",
        "",
    ]
    lines.extend(f"- {item}" for item in summary["promotion_policy"])
    lines.extend(
        [
            "",
            "## Counts",
            "",
            f"- Industry schema counts：`{json.dumps(taxonomy['industry_schema_counts'], ensure_ascii=False, sort_keys=True)}`",
            f"- Node type counts：`{json.dumps(taxonomy['node_type_counts'], ensure_ascii=False, sort_keys=True)}`",
            f"- Taxonomy review reason counts：`{json.dumps(taxonomy['review_reason_counts'], ensure_ascii=False, sort_keys=True)}`",
            f"- KPI fact metric family counts：`{json.dumps(kpi['fact_metric_family_counts'], ensure_ascii=False, sort_keys=True)}`",
            f"- KPI rejection reason counts：`{json.dumps(kpi['rejection_reason_counts'], ensure_ascii=False, sort_keys=True)}`",
            f"- Structured MetricObject parser：`{json.dumps(summary['structured_metric_kpi_parser'], ensure_ascii=False, sort_keys=True)}`",
            f"- Structured taxonomy repair：`{json.dumps(summary['structured_taxonomy_repair'], ensure_ascii=False, sort_keys=True)}`",
            "",
        ]
    )
    return "\n".join(lines)


def _taxonomy_alias_row(
    row: dict[str, Any],
    product_node_id: str,
    canonical_name: str,
    industry_schema: str,
    node_type: str,
    generated_at: str,
) -> dict[str, Any]:
    return {
        "schema_version": TAXONOMY_ALIAS_SCHEMA_VERSION,
        "alias_id": _stable_id("PRODUCTALIAS", row.get("candidate_id"), product_node_id, row.get("taxonomy_label")),
        "product_node_id": product_node_id,
        "source_candidate_id": row.get("candidate_id"),
        "ticker": row.get("ticker"),
        "company": row.get("company"),
        "fiscal_year": row.get("fiscal_year"),
        "taxonomy_label": row.get("taxonomy_label"),
        "canonical_name": canonical_name,
        "industry_schema": industry_schema,
        "node_type": node_type,
        "source_url": row.get("source_url"),
        "source_document_id": row.get("chunk_id"),
        "signal_role": "company_disclosed",
        "promotion_status": "taxonomy_alias_to_normalized_node",
        "generated_at": generated_at,
    }


def _taxonomy_review_row(row: dict[str, Any], generated_at: str, reason: str, route_evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": TAXONOMY_REVIEW_SCHEMA_VERSION,
        "review_id": _stable_id("PRODUCTTAXREVIEW", row.get("candidate_id"), reason, row.get("taxonomy_label")),
        "source_candidate_id": row.get("candidate_id"),
        "ticker": row.get("ticker"),
        "company": row.get("company"),
        "fiscal_year": row.get("fiscal_year"),
        "taxonomy_label": row.get("taxonomy_label"),
        "taxonomy_type": row.get("taxonomy_type"),
        "review_reason": reason,
        "industry_route_evidence": route_evidence,
        "source_url": row.get("source_url"),
        "source_document_id": row.get("chunk_id"),
        "promotion_status": "taxonomy_candidate_rejected_or_needs_review",
        "runtime_use_boundary": "Cannot enter runtime taxonomy or KPI product linking until reviewed.",
        "generated_at": generated_at,
    }


def _kpi_rejection_row(row: dict[str, Any], generated_at: str, reason: str, citation: str) -> dict[str, Any]:
    return {
        "schema_version": KPI_REJECTION_SCHEMA_VERSION,
        "rejection_id": _stable_id("PRODUCTKPIREJECT", row.get("candidate_id"), reason, citation[:120]),
        "source_candidate_id": row.get("candidate_id"),
        "ticker": row.get("ticker"),
        "company": row.get("company"),
        "fiscal_year": row.get("fiscal_year"),
        "metric_family": row.get("metric_family"),
        "rejection_reason": reason,
        "source_url": row.get("source_url"),
        "source_document_id": row.get("chunk_id"),
        "citation_span": _clean_text(citation)[:700],
        "fact_status": "rejected_context_only",
        "runtime_use_boundary": "Cannot be used as a product KPI fact.",
        "generated_at": generated_at,
    }


def _structured_kpi_rejection_row(row: dict[str, Any], generated_at: str, reason: str, citation: str) -> dict[str, Any]:
    return {
        "schema_version": KPI_REJECTION_SCHEMA_VERSION,
        "rejection_id": _stable_id("PRODUCTKPISTRUCTREJECT", row.get("object_id"), row.get("row_label"), row.get("column_label"), reason, citation[:120]),
        "source_candidate_id": structured_metric_candidate_id(row, str(row.get("metric_family") or "structured_metric")),
        "ticker": row.get("ticker"),
        "company": row.get("company"),
        "fiscal_year": row.get("fiscal_year"),
        "metric_family": row.get("metric_family"),
        "rejection_reason": reason,
        "source_url": row.get("source_url"),
        "source_document_id": row.get("source_evidence_id") or row.get("chunk_id"),
        "source_metric_object_id": row.get("object_id"),
        "source_table_object_id": structured_table_object_id(row),
        "row_label": row.get("row_label"),
        "column_label": row.get("column_label"),
        "citation_span": _clean_text(citation)[:700],
        "fact_status": "rejected_context_only",
        "runtime_use_boundary": "Cannot be used as a product KPI fact.",
        "generated_at": generated_at,
    }


def _contains_term(haystack_lower: str, term_lower: str) -> bool:
    if " " in term_lower:
        return term_lower in haystack_lower
    return re.search(rf"(?<![A-Za-z0-9]){re.escape(term_lower)}(?![A-Za-z0-9])", haystack_lower) is not None


def _window(text: str, start: int, end: int, *, max_chars: int) -> str:
    padding = max((max_chars - (end - start)) // 2, 80)
    left = max(0, start - padding)
    right = min(len(text), end + padding)
    snippet = text[left:right].strip()
    if left > 0:
        snippet = "..." + snippet
    if right < len(text):
        snippet += "..."
    return snippet


def _smart_title(text: str) -> str:
    small = {"and", "or", "of", "the", "for", "to", "in", "as", "a", "an"}
    words: list[str] = []
    for index, word in enumerate(text.split()):
        stripped = word.strip()
        if not stripped:
            continue
        if stripped.isupper() or any(char.isdigit() for char in stripped):
            words.append(stripped)
        elif index > 0 and stripped.lower() in small:
            words.append(stripped.lower())
        else:
            words.append(stripped[:1].upper() + stripped[1:])
    return " ".join(words)


def _clean_text(value: Any) -> str:
    text = str(value or "")
    text = (
        text.replace("&amp;", "&")
        .replace("&nbsp;", " ")
        .replace("&#160;", " ")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )
    text = re.sub(r"\s+", " ", text).strip(" \t\n\r:-;,.")
    return text


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", value.lower()).strip("_")
    return slug or "unnamed"


def _issuer_key(value: str) -> str:
    text = _clean_text(value).lower()
    text = re.sub(r"\b(?:incorporated|inc|corp|corporation|company|co|ltd|limited|plc|llc|holdings|holding|group|the|de)\b", " ", text)
    text = re.sub(r"[^a-z0-9]+", "", text)
    return text


def _stable_id(prefix: str, *parts: Any) -> str:
    digest = hashlib.sha1("||".join(str(part or "") for part in parts).encode("utf-8")).hexdigest()[:14]
    return f"{prefix}::{digest}"


def _append_unique(items: list[Any], value: Any) -> None:
    if value in ("", None):
        return
    if value not in items:
        items.append(value)


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _pct(numerator: int, denominator: int) -> float:
    return round((numerator / denominator) * 100, 2) if denominator else 0.0


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return data if isinstance(data, dict) else {}


def _iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if isinstance(row, dict):
                yield row


def iter_chunk_rows(paths: Iterable[Path]) -> Iterable[dict[str, Any]]:
    for path in paths:
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                row = json.loads(line)
                if isinstance(row, dict):
                    yield row


def has_numeric_value(text: str) -> bool:
    return re.search(r"(?:US\$|\$)?\s?[0-9][0-9,]*(?:\.[0-9]+)?\s?(?:%|billion|million|thousand|vehicles|units|tons|barrels|subscribers|MWh|mwh)?", text) is not None


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def _repo_path(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


if __name__ == "__main__":
    raise SystemExit(main())
