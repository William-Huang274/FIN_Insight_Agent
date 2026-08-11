from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]

SUMMARY_SCHEMA_VERSION = "fin_agent_product_kpi_repair_promotion_summary_v0.5"
REJECTION_SCHEMA_VERSION = "fin_agent_product_kpi_repair_promotion_rejection_v0.5"

DEFAULT_BASELINE_FACTS = Path(
    "Z:/FIN_Insight_Agent/data/manifests/product_evidence_v0_1/company_product_kpi_facts_parser_verified_with_structured_v0_1.jsonl"
)
DEFAULT_REPAIR_FACTS = Path(
    "Z:/FIN_Insight_Agent/data/manifests/product_evidence_v0_1/company_product_kpi_facts_parser_verified_targeted_repair_strict_v0_1.jsonl"
)
DEFAULT_OUTPUT_DIR = Path("Z:/FIN_Insight_Agent/data/manifests/product_evidence_v0_1")
DEFAULT_COMBINED_FACTS_OUTPUT = DEFAULT_OUTPUT_DIR / "company_product_kpi_facts_parser_verified_with_monotonic_repair_v0_5.jsonl"
DEFAULT_PROMOTED_FACTS_OUTPUT = DEFAULT_OUTPUT_DIR / "company_product_kpi_facts_monotonic_repair_promoted_v0_5.jsonl"
DEFAULT_REJECTIONS_OUTPUT = DEFAULT_OUTPUT_DIR / "company_product_kpi_facts_monotonic_repair_rejections_v0_5.jsonl"
DEFAULT_SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "company_product_kpi_monotonic_repair_promotion_summary_v0_5.json"
DEFAULT_REPORT_OUTPUT = Path(
    "Z:/FIN_Insight_Agent/docs/internal/vnext_20260610/product_kpi_monotonic_repair_promotion_v0_5_execution.zh-CN.md"
)

REVENUE_TABLE_CONTEXT_RE = re.compile(
    r"("
    r"revenue disaggregated|disaggregated revenue|revenues? disaggregated by geographic|"
    r"revenues? by geographic|net sales by|revenues? by|sales by|segment revenue|"
    r"segment sales|sales and revenues|revenues? disaggregated|net revenue by segment|"
    r"net revenue by|net sales\s+by\s+category|products and services performance|"
    r"sales and revenues by"
    r")",
    re.IGNORECASE,
)

FORBIDDEN_FINANCIAL_CONTEXT_RE = re.compile(
    r"("
    r"operating income|operating profit|income before|tax|cash flow|balance sheet|"
    r"liquidity|credit facility|gross profit|gross margin|cost of|expenses?|"
    r"depreciation|amortization|assets|liabilities|debt|borrowings|lease|"
    r"price realization|sales volume|currency|acquisitions?|divestitures?|"
    r"consolidating adjustments|eliminations"
    r")",
    re.IGNORECASE,
)

GENERIC_OR_BAD_ROW_LABEL_RE = re.compile(
    r"^(total|total revenue|total revenues|revenue|revenues|net sales|sales|"
    r"operating income|operating profit|gross profit|gross margin|income before|"
    r"other|corporate|eliminations?|cash and cash equivalents|available under.*|"
    r"letters of credit)$",
    re.IGNORECASE,
)

GEOGRAPHIC_SEGMENT_RE = re.compile(
    r"^(north america|latin america|emea|apac|asia(?:-pacific)?|europe|africa|"
    r"americas?|international|domestic|united states|u\.s\.|us|canada|mexico|"
    r"china|japan|korea|india|brazil|germany|western europe|other americas|"
    r"other countries|rest of world|key emerging markets)(?:\s*\([^)]*\))?$",
    re.IGNORECASE,
)

CUSTOMER_CHANNEL_OR_NON_PRODUCT_ROW_LABEL_RE = re.compile(
    r"^(direct customers?|indirect customers?|distributors?|resellers?|"
    r"total healthcare insurers?|healthcare insurers?|capitated|"
    r"pricing|volume|price|currency exchange rates?|acquisitions?\s*/\s*divestitures?|"
    r"lease rates?|concessions? and other discounts?|uncollectible lease revenue.*|rent relief|"
    r"deliveries(?:\s*\([^)]*\))?|shipments?|gross profit|total gross profit|"
    r"operating income|operating profit|general and administrative|research and development|"
    r"sales and marketing)$",
    re.IGNORECASE,
)

PRODUCT_CATEGORY_REVENUE_CONTEXT_RE = re.compile(
    r"("
    r"(?:revenues?|net\s+sales|sales)\s+(?:by|from|disaggregated\s+by)\s+"
    r"(?:major\s+)?(?:product|products|product\s+categor(?:y|ies)|category|categories|"
    r"brand|brands|product\s+line|product\s+lines)|"
    r"(?:product|products|product\s+categor(?:y|ies)|product\s+line|product\s+lines|"
    r"revenue\s+categor(?:y|ies))\s+(?:revenue|revenues|sales|net\s+sales)|"
    r"disaggregates?\s+(?:the\s+company['’]s\s+)?(?:net\s+)?revenue\s+by\s+category|"
    r"revenue\s+categories\s+used\s+by\s+management|"
    r"sales\s+of\s+principal\s+products"
    r")",
    re.IGNORECASE,
)

PRODUCT_CATEGORY_FINANCIAL_CONTEXT_ALLOW_RE = re.compile(
    r"revenues?\s+by\s+product\s+categor|revenue\s+by\s+category|"
    r"net\s+revenue\s+by\s+category|sales\s+of\s+principal\s+products|"
    r"revenues?\s+by\s+product\s+line|net\s+sales\s+by\s+product",
    re.IGNORECASE,
)

CHANGE_TEXT_RE = re.compile(r"change|increase|decrease|variance|growth|percentage|\bover\b|\bvs\b", re.IGNORECASE)
ROW_CHANGE_TEXT_RE = re.compile(r"change|increase|decrease|variance|growth|percentage", re.IGNORECASE)

TOTAL_SALES_PERCENT_MIX_RE = re.compile(r"total\s+sales\s*\|\s*(?:%|percent)", re.IGNORECASE)
SALES_OF_PRINCIPAL_PRODUCTS_RE = re.compile(r"sales\s+of\s+principal\s+products", re.IGNORECASE)
TSN_SEGMENT_SALES_OP_INCOME_RE = re.compile(
    r"(?:summary\s+of\s+segment\s+sales\s+and\s+operating\s+income.*)?sales\s*\|\s*operating\s+income\s*\(loss\)",
    re.IGNORECASE | re.DOTALL,
)
DRI_SALES_AVERAGE_SALES_RE = re.compile(
    r"sales\s*\|\s*average\s+annual\s+sales\s+per\s+restaurant",
    re.IGNORECASE,
)
HUBB_NET_SALES_SEGMENT_RE = re.compile(r"net\s+sales.*total\s+utility\s+solutions", re.IGNORECASE | re.DOTALL)
ES_REVENUES_FROM_CONTRACTS_RE = re.compile(r"(?:revenues|ues)\s+from\s+contracts\s+with\s+customers", re.IGNORECASE)
LOW_MERCHANDISING_ROW_LABEL_RE = re.compile(
    r"^(appliances|seasonal\s*&\s*outdoor\s+living|lumber|lawn\s*&\s*garden|"
    r"kitchens?\s*&\s*bath|kitchens?\s+and\s+bath|hardware|building materials|"
    r"rough plumbing|paint|millwork|flooring)$",
    re.IGNORECASE,
)
LOW_MERCHANDISING_CONTEXT_TERMS = (
    "seasonal & outdoor living",
    "lumber",
    "lawn & garden",
    "kitchens & bath",
    "hardware",
    "building materials",
    "rough plumbing",
    "paint",
)
MIXED_TABLE_MIN_SALES_VALUE = 100_000_000

PRE_PROMOTION_REASONS = frozenset(
    {
        "pre_promote_product_or_segment",
        "pre_promote_geographic",
        "pre_promote_total_sales_percent_mix",
        "pre_promote_low_merchandising_sales_mix",
        "pre_promote_sales_of_principal_products",
        "pre_promote_segment_sales_operating_income_table",
        "pre_promote_restaurant_sales_table",
        "pre_promote_hubb_net_sales_segment_table",
        "pre_promote_es_customer_contract_revenue_table",
        "pre_promote_product_category_revenue_table",
    }
)
MIXED_SALES_TABLE_PRE_PROMOTION_REASONS = frozenset(
    {
        "pre_promote_total_sales_percent_mix",
        "pre_promote_low_merchandising_sales_mix",
    }
)
MAX_SALES_VALUE_PRE_PROMOTION_REASONS = frozenset(
    {
        "pre_promote_segment_sales_operating_income_table",
    }
)

PROMOTION_GATE_VERSION = "structured_table_currency_revenue_row_bound_v0_5"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Promote high-confidence product KPI repair candidates without replacing baseline facts.")
    parser.add_argument("--baseline-facts", type=Path, default=DEFAULT_BASELINE_FACTS)
    parser.add_argument("--repair-facts", type=Path, default=DEFAULT_REPAIR_FACTS)
    parser.add_argument("--combined-facts-output", type=Path, default=DEFAULT_COMBINED_FACTS_OUTPUT)
    parser.add_argument("--promoted-facts-output", type=Path, default=DEFAULT_PROMOTED_FACTS_OUTPUT)
    parser.add_argument("--rejections-output", type=Path, default=DEFAULT_REJECTIONS_OUTPUT)
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_SUMMARY_OUTPUT)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT_OUTPUT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at = datetime.now(timezone.utc).isoformat()
    baseline_rows = list(_iter_jsonl(_resolve(args.baseline_facts)))
    repair_rows = list(_iter_jsonl(_resolve(args.repair_facts)))
    combined_rows, promoted_rows, rejection_rows, summary = promote_repair_candidates(
        baseline_rows=baseline_rows,
        repair_rows=repair_rows,
        generated_at=generated_at,
        paths={
            "baseline_facts": _repo_path(_resolve(args.baseline_facts)),
            "repair_facts": _repo_path(_resolve(args.repair_facts)),
            "combined_facts": _repo_path(_resolve(args.combined_facts_output)),
            "promoted_facts": _repo_path(_resolve(args.promoted_facts_output)),
            "rejections": _repo_path(_resolve(args.rejections_output)),
            "summary": _repo_path(_resolve(args.summary_output)),
            "report": _repo_path(_resolve(args.report_output)),
        },
    )
    _write_jsonl(_resolve(args.combined_facts_output), combined_rows)
    _write_jsonl(_resolve(args.promoted_facts_output), promoted_rows)
    _write_jsonl(_resolve(args.rejections_output), rejection_rows)
    _write_json(_resolve(args.summary_output), summary)
    report_output = _resolve(args.report_output)
    report_output.parent.mkdir(parents=True, exist_ok=True)
    report_output.write_text(render_report(summary), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def promote_repair_candidates(
    *,
    baseline_rows: list[dict[str, Any]],
    repair_rows: list[dict[str, Any]],
    generated_at: str,
    paths: dict[str, str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    baseline_fact_keys = {fact_key(row) for row in baseline_rows}
    baseline_claim_keys = {claim_key(row) for row in baseline_rows}
    baseline_fact_ids = {str(row.get("fact_id") or "") for row in baseline_rows if row.get("fact_id")}

    candidates = [row for row in repair_rows if fact_key(row) not in baseline_fact_keys]
    pre_reasons = {id(row): pre_promotion_rejection_reason(row, baseline_claim_keys) for row in candidates}
    pre_promotable = [row for row in candidates if pre_reasons[id(row)] in PRE_PROMOTION_REASONS]
    selected_fact_keys_by_claim, claim_rejection_reasons = select_promotable_fact_keys(pre_promotable, pre_reasons)

    promoted_rows: list[dict[str, Any]] = []
    rejection_rows: list[dict[str, Any]] = []
    seen_fact_keys: set[tuple[Any, ...]] = set()
    for row in candidates:
        reason = final_promotion_rejection_reason(
            row,
            pre_reasons[id(row)],
            selected_fact_keys_by_claim,
            claim_rejection_reasons,
        )
        if reason == "promote":
            key = fact_key(row)
            if key in seen_fact_keys:
                rejection_rows.append(rejection_row(row, "duplicate_promoted_semantic_fact", generated_at))
                continue
            seen_fact_keys.add(key)
            promoted = dict(row)
            promoted["repair_promotion_status"] = "monotonic_repair_promoted"
            promoted["repair_promotion_gate"] = PROMOTION_GATE_VERSION
            promoted["repair_promotion_generated_at"] = generated_at
            promoted["repair_claim_scope"] = claim_scope(row)
            promoted["runtime_use_boundary"] = runtime_boundary_for_scope(promoted["repair_claim_scope"])
            if promoted["repair_claim_scope"] == "company_disclosed_product_category_revenue":
                promoted["product_node_type"] = "category_or_brand_family"
            if str(promoted.get("fact_id") or "") in baseline_fact_ids:
                promoted["fact_id"] = stable_id("PRODUCTKPIREPAIR", *fact_key(promoted))
            promoted_rows.append(promoted)
        else:
            rejection_rows.append(rejection_row(row, reason, generated_at))

    combined_rows = [*baseline_rows, *promoted_rows]
    summary = build_summary(
        baseline_rows=baseline_rows,
        repair_rows=repair_rows,
        candidates=candidates,
        promoted_rows=promoted_rows,
        rejection_rows=rejection_rows,
        generated_at=generated_at,
        paths=paths or {},
    )
    return combined_rows, promoted_rows, rejection_rows, summary


def pre_promotion_rejection_reason(row: dict[str, Any], baseline_claim_keys: set[tuple[Any, ...]]) -> str:
    if row.get("source_id") != "company_product_kpi_facts_structured_metric_parser":
        return "not_structured_table_metric"
    if row.get("metric_family") != "product_revenue":
        return "not_product_revenue"
    if row.get("unit") != "USD" or row.get("unit_category") != "currency":
        return "not_currency_revenue"
    if row.get("product_link_method") != "structured_row_label_alias_exact":
        return "not_bound_to_structured_row_label"
    if claim_key(row) in baseline_claim_keys:
        return "claim_already_covered_by_baseline"
    if not row.get("row_label") or not row.get("column_label"):
        return "missing_row_or_column_label"
    if normalized_value(row.get("value")) <= 0:
        return "non_positive_value"
    period_year = fiscal_year_from_period(row.get("period"))
    if period_year and row.get("fiscal_year") and period_year > int(row.get("fiscal_year") or 0):
        return "period_after_fiscal_year"
    row_label = str(row.get("row_label") or "").strip()
    column_label = str(row.get("column_label") or "").strip()
    citation = str(row.get("citation_span") or "")
    if ROW_CHANGE_TEXT_RE.search(row_label):
        return "change_or_growth_row"
    if CHANGE_TEXT_RE.search(column_label):
        return "change_or_growth_column"
    if GENERIC_OR_BAD_ROW_LABEL_RE.match(row_label):
        return "generic_or_bad_row_label"
    if CUSTOMER_CHANNEL_OR_NON_PRODUCT_ROW_LABEL_RE.match(row_label):
        return "customer_channel_or_non_product_row_label"
    is_geographic = is_geographic_segment(row)
    if is_geographic:
        return "geographic_segment_requires_region_dimension"
    source_specific_reason = source_specific_table_layout_promotion_reason(row)
    if source_specific_reason:
        return source_specific_reason
    if product_category_revenue_table_promotion_reason(row):
        return "pre_promote_product_category_revenue_table"
    if FORBIDDEN_FINANCIAL_CONTEXT_RE.search(citation):
        return "forbidden_financial_statement_context"
    return "missing_product_category_or_source_specific_revenue_table_context"


def select_promotable_fact_keys(
    rows: list[dict[str, Any]], pre_reasons: dict[int, str]
) -> tuple[dict[tuple[Any, ...], set[tuple[Any, ...]]], dict[tuple[Any, ...], str]]:
    rows_by_claim: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        rows_by_claim[claim_key(row)].append(row)

    selected_fact_keys_by_claim: dict[tuple[Any, ...], set[tuple[Any, ...]]] = {}
    claim_rejection_reasons: dict[tuple[Any, ...], str] = {}
    for key, claim_rows in rows_by_claim.items():
        if any(pre_reasons[id(row)] in MIXED_SALES_TABLE_PRE_PROMOTION_REASONS for row in claim_rows):
            high_sales_rows = [row for row in claim_rows if is_high_confidence_mixed_table_sales_value(row)]
            high_sales_values = {normalized_value(row.get("value")) for row in high_sales_rows}
            if not high_sales_values:
                claim_rejection_reasons[key] = "no_high_confidence_sales_value_in_mixed_table"
                continue
            if len(high_sales_values) > 1:
                claim_rejection_reasons[key] = "conflicting_values_for_same_claim"
                continue
            selected_value = next(iter(high_sales_values))
            selected_fact_keys_by_claim[key] = {
                fact_key(row) for row in high_sales_rows if normalized_value(row.get("value")) == selected_value
            }
            continue
        if any(pre_reasons[id(row)] in MAX_SALES_VALUE_PRE_PROMOTION_REASONS for row in claim_rows):
            high_sales_rows = [row for row in claim_rows if is_high_confidence_segment_sales_value(row)]
            high_sales_values = {normalized_value(row.get("value")) for row in high_sales_rows}
            if not high_sales_values:
                claim_rejection_reasons[key] = "no_high_confidence_sales_value_in_mixed_table"
                continue
            selected_value = max(high_sales_values)
            selected_fact_keys_by_claim[key] = {
                fact_key(row) for row in high_sales_rows if normalized_value(row.get("value")) == selected_value
            }
            continue

        distinct_values = {normalized_value(row.get("value")) for row in claim_rows}
        if len(distinct_values) > 1:
            claim_rejection_reasons[key] = "conflicting_values_for_same_claim"
            continue
        selected_fact_keys_by_claim[key] = {fact_key(row) for row in claim_rows}
    return selected_fact_keys_by_claim, claim_rejection_reasons


def final_promotion_rejection_reason(
    row: dict[str, Any],
    pre_reason: str,
    selected_fact_keys_by_claim: dict[tuple[Any, ...], set[tuple[Any, ...]]],
    claim_rejection_reasons: dict[tuple[Any, ...], str],
) -> str:
    if pre_reason not in PRE_PROMOTION_REASONS:
        return pre_reason
    key = claim_key(row)
    if fact_key(row) in selected_fact_keys_by_claim.get(key, set()):
        return "promote"
    if key in claim_rejection_reasons:
        return claim_rejection_reasons[key]
    if pre_reason in MIXED_SALES_TABLE_PRE_PROMOTION_REASONS:
        return "non_sales_percentage_value_in_mixed_table"
    if pre_reason in MAX_SALES_VALUE_PRE_PROMOTION_REASONS:
        return "non_sales_operating_income_value_in_mixed_table"
    return "conflicting_values_for_same_claim"


def rejection_row(row: dict[str, Any], reason: str, generated_at: str) -> dict[str, Any]:
    return {
        "schema_version": REJECTION_SCHEMA_VERSION,
        "rejection_id": stable_id("PRODUCTKPIREPAIRREJECT", row.get("fact_id"), reason),
        "generated_at": generated_at,
        "rejection_reason": reason,
        "ticker": row.get("ticker"),
        "company": row.get("company"),
        "fact_id": row.get("fact_id"),
        "metric_family": row.get("metric_family"),
        "product_or_segment": row.get("product_or_segment"),
        "product_node_id": row.get("product_node_id"),
        "period": row.get("period"),
        "unit": row.get("unit"),
        "value": row.get("value"),
        "row_label": row.get("row_label"),
        "column_label": row.get("column_label"),
        "source_id": row.get("source_id"),
        "source_document_id": row.get("source_document_id"),
        "source_url": row.get("source_url"),
    }


def build_summary(
    *,
    baseline_rows: list[dict[str, Any]],
    repair_rows: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    promoted_rows: list[dict[str, Any]],
    rejection_rows: list[dict[str, Any]],
    generated_at: str,
    paths: dict[str, str],
) -> dict[str, Any]:
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "status": "pass",
        "generated_at": generated_at,
        "promotion_gate": PROMOTION_GATE_VERSION,
        "baseline_fact_count": len(baseline_rows),
        "baseline_ticker_count": count_tickers(baseline_rows),
        "repair_fact_count": len(repair_rows),
        "semantic_repair_candidate_count": len(candidates),
        "semantic_repair_candidate_ticker_count": count_tickers(candidates),
        "promoted_fact_count": len(promoted_rows),
        "promoted_ticker_count": count_tickers(promoted_rows),
        "combined_fact_count": len(baseline_rows) + len(promoted_rows),
        "combined_ticker_count": count_tickers([*baseline_rows, *promoted_rows]),
        "promoted_claim_scope_counts": dict(sorted(Counter(str(row.get("repair_claim_scope") or "") for row in promoted_rows).items())),
        "promoted_ticker_counts": dict(sorted(Counter(str(row.get("ticker") or "") for row in promoted_rows).items())),
        "rejection_count": len(rejection_rows),
        "rejection_reason_counts": dict(sorted(Counter(str(row.get("rejection_reason") or "") for row in rejection_rows).items())),
        "outputs": paths,
        "promotion_boundary": [
            "Baseline parser-verified facts are preserved unchanged.",
            "Repair candidates are added only when they are semantic additions, table-derived, row-label-bound, currency revenue facts with strong revenue table context.",
            "Product/category/product-line revenue tables are promoted only when row label, value, unit, period, source table context, and issuer/product binding all pass.",
            "Source-specific table layouts are allowed only for audited principal-product sales tables, total-sales/percentage mix tables, LOW merchandising-table continuation spans, TSN segment sales/operating-income tables, DRI restaurant sales tables, HUBB net-sales segment tables, and ES customer-contract revenue tables; non-sales cells remain rejected.",
            "Sentence-derived repair candidates are not promoted in this pass.",
            "Geographic revenue candidates remain rejected until a region dimension/versioned schema is added; they cannot fill product KPI exact slots.",
            "If baseline already covers a ticker/product/metric/period/unit claim, the repair candidate is rejected for manual audit instead of replacing baseline.",
        ],
    }


def render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Product KPI Monotonic Repair Promotion 执行报告",
        "",
        f"- 生成时间：`{summary['generated_at']}`",
        f"- Promotion gate：`{summary['promotion_gate']}`",
        f"- Baseline facts：`{summary['baseline_fact_count']}` / tickers `({summary['baseline_ticker_count']})`",
        f"- Semantic repair candidates：`{summary['semantic_repair_candidate_count']}` / tickers `({summary['semantic_repair_candidate_ticker_count']})`",
        f"- Promoted facts：`{summary['promoted_fact_count']}` / tickers `({summary['promoted_ticker_count']})`",
        f"- Combined facts：`{summary['combined_fact_count']}` / tickers `({summary['combined_ticker_count']})`",
        "",
        "## Boundary",
        "",
    ]
    lines.extend(f"- {item}" for item in summary["promotion_boundary"])
    lines.extend(
        [
            "",
            "## Counts",
            "",
            f"- Promoted claim scopes：`{json.dumps(summary['promoted_claim_scope_counts'], ensure_ascii=False, sort_keys=True)}`",
            f"- Promoted tickers：`{json.dumps(summary['promoted_ticker_counts'], ensure_ascii=False, sort_keys=True)}`",
            f"- Rejection reasons：`{json.dumps(summary['rejection_reason_counts'], ensure_ascii=False, sort_keys=True)}`",
        ]
    )
    return "\n".join(lines) + "\n"


def is_geographic_segment(row: dict[str, Any]) -> bool:
    return bool(GEOGRAPHIC_SEGMENT_RE.match(str(row.get("product_or_segment") or "").strip()))


def source_specific_table_layout_promotion_reason(row: dict[str, Any]) -> str | None:
    citation = str(row.get("citation_span") or "")
    if is_tsn_segment_sales_operating_income_table(row):
        return "pre_promote_segment_sales_operating_income_table"
    if is_dri_restaurant_sales_table(row):
        return "pre_promote_restaurant_sales_table"
    if is_hubb_net_sales_segment_table(row):
        return "pre_promote_hubb_net_sales_segment_table"
    if is_es_customer_contract_revenue_table(row):
        return "pre_promote_es_customer_contract_revenue_table"
    if TOTAL_SALES_PERCENT_MIX_RE.search(citation):
        return "pre_promote_total_sales_percent_mix"
    if is_low_merchandising_sales_mix_table(row):
        return "pre_promote_low_merchandising_sales_mix"
    if SALES_OF_PRINCIPAL_PRODUCTS_RE.search(citation):
        return "pre_promote_sales_of_principal_products"
    return None


def product_category_revenue_table_promotion_reason(row: dict[str, Any]) -> str | None:
    citation = str(row.get("citation_span") or "")
    if not PRODUCT_CATEGORY_REVENUE_CONTEXT_RE.search(citation):
        return None
    if FORBIDDEN_FINANCIAL_CONTEXT_RE.search(citation) and not PRODUCT_CATEGORY_FINANCIAL_CONTEXT_ALLOW_RE.search(citation):
        return None
    return "pre_promote_product_category_revenue_table"


def is_tsn_segment_sales_operating_income_table(row: dict[str, Any]) -> bool:
    if row.get("ticker") != "TSN":
        return False
    citation = str(row.get("citation_span") or "")
    row_label = str(row.get("row_label") or "")
    if not TSN_SEGMENT_SALES_OP_INCOME_RE.search(citation):
        return False
    return bool(row_label and not GENERIC_OR_BAD_ROW_LABEL_RE.match(row_label))


def is_dri_restaurant_sales_table(row: dict[str, Any]) -> bool:
    if row.get("ticker") != "DRI":
        return False
    citation = str(row.get("citation_span") or "")
    if not DRI_SALES_AVERAGE_SALES_RE.search(citation):
        return False
    return str(row.get("column_label") or "").strip().lower() == "(in millions)"


def is_hubb_net_sales_segment_table(row: dict[str, Any]) -> bool:
    if row.get("ticker") != "HUBB":
        return False
    row_label = str(row.get("row_label") or "").strip().lower()
    citation = str(row.get("citation_span") or "")
    return row_label == "total electrical solutions" and HUBB_NET_SALES_SEGMENT_RE.search(citation) is not None


def is_es_customer_contract_revenue_table(row: dict[str, Any]) -> bool:
    if row.get("ticker") != "ES":
        return False
    row_label = str(row.get("row_label") or "").strip().lower()
    citation = str(row.get("citation_span") or "")
    return row_label == "wholesale transmission revenues" and ES_REVENUES_FROM_CONTRACTS_RE.search(citation) is not None


def is_low_merchandising_sales_mix_table(row: dict[str, Any]) -> bool:
    if row.get("ticker") != "LOW":
        return False
    row_label = str(row.get("row_label") or row.get("product_or_segment") or "").strip()
    if not LOW_MERCHANDISING_ROW_LABEL_RE.match(row_label):
        return False
    citation = str(row.get("citation_span") or "").lower()
    if "|" not in citation:
        return False
    if "%" not in citation and not has_low_merchandising_share_cells(citation):
        return False
    term_hits = sum(1 for term in LOW_MERCHANDISING_CONTEXT_TERMS if term in citation)
    return term_hits >= 4


def has_low_merchandising_share_cells(citation: str) -> bool:
    return len(re.findall(r"\|\s*\d{1,2}\.\d\s*(?=\|)", citation)) >= 4


def is_high_confidence_mixed_table_sales_value(row: dict[str, Any]) -> bool:
    raw_value_text = str(row.get("raw_value_text") or "")
    if "%" in raw_value_text:
        return False
    return normalized_value(row.get("value")) >= MIXED_TABLE_MIN_SALES_VALUE


def is_high_confidence_segment_sales_value(row: dict[str, Any]) -> bool:
    raw_value_text = str(row.get("raw_value_text") or "")
    if "%" in raw_value_text or "(" in raw_value_text:
        return False
    return normalized_value(row.get("value")) >= MIXED_TABLE_MIN_SALES_VALUE


def claim_scope(row: dict[str, Any]) -> str:
    if row.get("repair_promotion_gate") == PROMOTION_GATE_VERSION and row.get("repair_claim_scope"):
        return str(row.get("repair_claim_scope") or "")
    if product_category_revenue_table_promotion_reason(row):
        return "company_disclosed_product_category_revenue"
    if is_geographic_segment(row):
        return "company_disclosed_geographic_segment_revenue"
    return "company_disclosed_product_or_segment_revenue"


def runtime_boundary_for_scope(scope: str) -> str:
    if scope == "company_disclosed_geographic_segment_revenue":
        return (
            "May support company-disclosed geographic revenue disaggregation; "
            "must not be described as product demand, product market share, or SKU economics."
        )
    if scope == "company_disclosed_product_category_revenue":
        return (
            "May support company-disclosed product/category/product-line revenue for the cited row only; "
            "does not prove SKU demand, market share, channel inventory, sell-through, or undisclosed ASP."
        )
    return (
        "May support company-disclosed product or operating segment revenue; "
        "does not prove market share, channel inventory, or undisclosed product economics."
    )


def count_tickers(rows: Iterable[dict[str, Any]]) -> int:
    return len({str(row.get("ticker") or "") for row in rows if row.get("ticker")})


def fact_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row.get("ticker"),
        row.get("product_node_id"),
        row.get("metric_family"),
        row.get("period"),
        row.get("unit"),
        normalized_value(row.get("value")),
    )


def claim_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row.get("ticker"),
        row.get("product_node_id"),
        row.get("metric_family"),
        row.get("period"),
        row.get("unit"),
    )


def normalized_value(value: Any) -> float:
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return 0.0


def fiscal_year_from_period(period: Any) -> int | None:
    match = re.search(r"FY(\d{4})", str(period or ""))
    if not match:
        return None
    return int(match.group(1))


def stable_id(prefix: str, *parts: Any) -> str:
    digest = hashlib.sha1("||".join(str(part or "") for part in parts).encode("utf-8")).hexdigest()[:14]
    return f"{prefix}::{digest}"


def _resolve(path: Path) -> Path:
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def _repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
