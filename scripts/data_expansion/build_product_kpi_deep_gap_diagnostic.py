from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


SCHEMA_VERSION = "finsight_product_kpi_deep_gap_diagnostic_v0_1"
SUMMARY_SCHEMA_VERSION = "finsight_product_kpi_deep_gap_diagnostic_summary_v0_1"

DEFAULT_PRODUCT_KPI_CLOSEOUT = REPO_ROOT / "data" / "manifests" / "product_kpi_exact_slot_closeout_v0_1.jsonl"
DEFAULT_RUNTIME_ROW_PATHS = [
    REPO_ROOT / "data" / "manifests" / "company_reported_product_operating_metric_runtime_rows_v0_1.jsonl",
    REPO_ROOT / "data" / "manifests" / "non_us_product_kpi_local_disclosure_runtime_rows_v0_1.jsonl",
    REPO_ROOT / "data" / "manifests" / "r16_product_kpi_deep_repair_runtime_rows_v0_1.jsonl",
    REPO_ROOT / "data" / "manifests" / "r17_known_public_product_kpi_repair_runtime_rows_v0_1.jsonl",
]
DEFAULT_STRICT_CANDIDATES = Path(
    "Z:/FIN_Insight_Agent/data/manifests/product_evidence_v0_1/company_product_kpi_facts_parser_verified_targeted_repair_strict_v0_1.jsonl"
)
DEFAULT_FINAL_CLOSEOUT = Path(
    "Z:/FIN_Insight_Agent/data/manifests/product_evidence_v0_1/company_product_kpi_repair_final_closeout_v0_1.jsonl"
)
DEFAULT_SOURCE_SPECIFIC_VERIFIER_TICKER_SUMMARY = (
    REPO_ROOT / "data" / "manifests" / "product_kpi_source_specific_verifier_ticker_summary_v0_1.jsonl"
)
DEFAULT_OUTPUT_ROWS = REPO_ROOT / "data" / "manifests" / "product_kpi_deep_gap_diagnostic_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY = REPO_ROOT / "data" / "manifests" / "product_kpi_deep_gap_diagnostic_summary_v0_1.json"
DEFAULT_OUTPUT_REPORT = REPO_ROOT / "docs" / "internal" / "vnext_20260610" / "vertical_lanes" / "product_kpi_deep_gap_diagnostic.zh-CN.md"

PRODUCT_EXACT_NODE_TYPES = {
    "product_family",
    "product_or_therapy_family",
    "model_or_product_family",
    "category_or_brand_family",
    "financial_product_or_service",
}
BUSINESS_SEGMENT_NODE_TYPES = {"segment", "business_line", "banner_or_channel", "therapeutic_area_or_business_line"}
GEOGRAPHIC_RE = re.compile(
    r"north america|latin america|emea|apac|asia|europe|africa|international|domestic|"
    r"united states|u\.s\.|canada|mexico|china|japan|korea|india|brazil|"
    r"other countries|rest of world|geographic|region|regional|country|americas",
    re.IGNORECASE,
)
GENERIC_RE = re.compile(
    r"products and services|total products|total services|corporate|other|all other|"
    r"eliminations|reconciliation|unallocated|intercompany|total company|consolidated",
    re.IGNORECASE,
)
NON_US_TICKER_RE = re.compile(r"\.(HK|KS|SZ|TW|T|DE|L|PA|AS|SW|TO)$", re.IGNORECASE)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build company-level product KPI deep gap diagnostics.")
    parser.add_argument("--product-kpi-closeout", type=Path, default=DEFAULT_PRODUCT_KPI_CLOSEOUT)
    parser.add_argument(
        "--runtime-row",
        "--runtime-rows",
        dest="runtime_row_paths",
        action="append",
        type=Path,
        default=None,
        help=(
            "Product/business KPI runtime JSONL path. Can be repeated. Defaults to SEC/company-reported rows "
            "plus non-US local disclosure rows."
        ),
    )
    parser.add_argument("--strict-candidates", type=Path, default=DEFAULT_STRICT_CANDIDATES)
    parser.add_argument("--final-closeout", type=Path, default=DEFAULT_FINAL_CLOSEOUT)
    parser.add_argument(
        "--source-specific-verifier-ticker-summary",
        type=Path,
        default=DEFAULT_SOURCE_SPECIFIC_VERIFIER_TICKER_SUMMARY,
    )
    parser.add_argument("--output-rows", type=Path, default=DEFAULT_OUTPUT_ROWS)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--output-report", type=Path, default=DEFAULT_OUTPUT_REPORT)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    if args.runtime_row_paths is None:
        args.runtime_row_paths = DEFAULT_RUNTIME_ROW_PATHS
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at = _utc_now()
    rows = build_product_kpi_deep_gap_diagnostic_rows(
        closeout_rows=_load_jsonl(args.product_kpi_closeout),
        runtime_rows=[row for path in args.runtime_row_paths for row in _load_jsonl(path)],
        strict_candidate_rows=_load_jsonl(args.strict_candidates),
        final_closeout_rows=_load_jsonl(args.final_closeout),
        verifier_ticker_summary_rows=_load_jsonl(args.source_specific_verifier_ticker_summary),
        generated_at=generated_at,
    )
    summary = build_summary(rows=rows, generated_at=generated_at, output_rows=args.output_rows, output_report=args.output_report)
    _write_jsonl(args.output_rows, rows)
    _write_json(args.output_summary, summary)
    args.output_report.parent.mkdir(parents=True, exist_ok=True)
    args.output_report.write_text(render_report(summary), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if args.strict and summary["unclassified_count"]:
        return 1
    return 0


def build_product_kpi_deep_gap_diagnostic_rows(
    *,
    closeout_rows: Iterable[Mapping[str, Any]],
    runtime_rows: Iterable[Mapping[str, Any]],
    strict_candidate_rows: Iterable[Mapping[str, Any]],
    final_closeout_rows: Iterable[Mapping[str, Any]],
    generated_at: str,
    verifier_ticker_summary_rows: Iterable[Mapping[str, Any]] = (),
) -> list[dict[str, Any]]:
    runtime_by_ticker = _by_ticker(runtime_rows)
    strict_by_ticker = _by_ticker(strict_candidate_rows)
    final_closeout_by_ticker = _by_ticker(final_closeout_rows)
    verifier_summary_by_ticker = _single_by_ticker(verifier_ticker_summary_rows)
    out: list[dict[str, Any]] = []
    for closeout in sorted((dict(row) for row in closeout_rows), key=lambda row: str(row.get("ticker") or "")):
        ticker = str(closeout.get("ticker") or "").upper()
        runtime = runtime_by_ticker.get(ticker, [])
        strict_candidates = strict_by_ticker.get(ticker, [])
        final_closeouts = final_closeout_by_ticker.get(ticker, [])
        verifier_summary = verifier_summary_by_ticker.get(ticker, {})
        runtime_bucket_counts = Counter(_bucket(row) for row in runtime)
        strict_bucket_counts = Counter(_bucket(row) for row in strict_candidates)
        final_reason_counts = Counter(str(row.get("closeout_reason") or row.get("rejection_reason") or "") for row in final_closeouts)
        diagnostic = _diagnose(
            closeout,
            runtime_bucket_counts,
            strict_candidates,
            strict_bucket_counts,
            final_reason_counts,
            verifier_summary,
        )
        out.append(
            {
                "schema_version": SCHEMA_VERSION,
                "generated_at": generated_at,
                "ticker": ticker,
                "company_name": closeout.get("company_name") or "",
                "primary_lane_id": closeout.get("primary_lane_id") or "",
                "product_kpi_status": diagnostic["effective_product_kpi_status"],
                "source_product_kpi_closeout_status": closeout.get("status") or "",
                "product_kpi_closeout_reason": closeout.get("closeout_reason") or "",
                "diagnostic_class": diagnostic["diagnostic_class"],
                "diagnostic_reason": diagnostic["diagnostic_reason"],
                "gap_reason": diagnostic["diagnostic_reason"],
                "coverage_bucket": diagnostic["coverage_bucket"],
                "public_boundary_assessment": diagnostic["public_boundary_assessment"],
                "next_action": diagnostic["next_action"],
                "runtime_row_count": len(runtime),
                "runtime_bucket_counts": dict(sorted(runtime_bucket_counts.items())),
                "strict_candidate_count": len(strict_candidates),
                "strict_candidate_bucket_counts": dict(sorted(strict_bucket_counts.items())),
                "source_specific_verifier_candidate_count": int(verifier_summary.get("candidate_count") or 0),
                "source_specific_verifier_class_counts": _dict_field(verifier_summary, "verifier_class_counts"),
                "source_specific_verifier_decision_counts": _dict_field(verifier_summary, "verifier_decision_counts"),
                "source_specific_verifier_top_reasons": _dict_field(verifier_summary, "top_verifier_reasons"),
                "dominant_verifier_class": diagnostic.get("dominant_verifier_class", ""),
                "dominant_verifier_reason": diagnostic.get("dominant_verifier_reason", ""),
                "final_repair_closeout_count": len(final_closeouts),
                "final_repair_closeout_reason_counts": dict(final_reason_counts.most_common(8)),
                "official_surface_slot_count": closeout.get("official_surface_slot_count") or 0,
                "filings_taxonomy_slot_count": closeout.get("filings_taxonomy_slot_count") or 0,
                "sample_runtime_rows": [_sample_fact(row) for row in runtime[:3]],
                "sample_strict_candidates": [_sample_fact(row) for row in strict_candidates[:3]],
                "sample_final_closeouts": [_sample_final_closeout(row) for row in final_closeouts[:3]],
                "claim_boundary": (
                    "Diagnostic rows are not runtime evidence. Only rows that pass company-disclosed value/unit/period/product/citation gates "
                    "may enter product KPI exact slots; proxies and rejected candidates remain gap/debug context."
                ),
            }
        )
    return out


def build_summary(*, rows: list[dict[str, Any]], generated_at: str, output_rows: Path, output_report: Path) -> dict[str, Any]:
    gap_rows = [row for row in rows if row.get("product_kpi_status") == "product_kpi_exact_gap"]
    class_counts = Counter(str(row.get("diagnostic_class") or "") for row in rows)
    coverage_bucket_counts = Counter(str(row.get("coverage_bucket") or "") for row in rows)
    product_family_ready = class_counts.get("ready_product_kpi_exact", 0)
    business_segment_ready = class_counts.get("ready_business_segment_metric_only", 0)
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "pass" if rows and not any(row.get("diagnostic_class") == "unclassified" for row in rows) else "gap",
        "company_count": len(rows),
        "product_kpi_status_counts": dict(sorted(Counter(str(row.get("product_kpi_status") or "") for row in rows).items())),
        "diagnostic_class_counts": dict(sorted(class_counts.items())),
        "coverage_bucket_counts": dict(sorted(coverage_bucket_counts.items())),
        "product_family_exact_ready_ticker_count": product_family_ready,
        "business_or_segment_exact_ready_ticker_count": business_segment_ready,
        "product_or_business_kpi_ready_ticker_count": product_family_ready + business_segment_ready,
        "geographic_or_non_product_only_ticker_count": class_counts.get("geographic_or_non_product_only", 0),
        "gap_diagnostic_class_counts": dict(sorted(Counter(str(row.get("diagnostic_class") or "") for row in gap_rows).items())),
        "top_gap_reasons": dict(Counter(str(row.get("diagnostic_reason") or "") for row in gap_rows).most_common(15)),
        "gap_dominant_verifier_class_counts": dict(
            sorted(Counter(str(row.get("dominant_verifier_class") or "") for row in gap_rows if row.get("dominant_verifier_class")).items())
        ),
        "strict_candidate_gap_ticker_count": len({row["ticker"] for row in gap_rows if row.get("strict_candidate_count")}),
        "no_candidate_gap_ticker_count": len({row["ticker"] for row in gap_rows if not row.get("strict_candidate_count")}),
        "unclassified_count": len([row for row in rows if row.get("diagnostic_class") == "unclassified"]),
        "outputs": {"rows": str(output_rows), "report": str(output_report)},
        "boundary": "This diagnostic separates company-disclosed product KPI coverage, rejected parser candidates, and public/commercial gaps. It does not promote any row by itself.",
    }


def _diagnose(
    closeout: Mapping[str, Any],
    runtime_bucket_counts: Counter[str],
    strict_candidates: list[dict[str, Any]],
    strict_bucket_counts: Counter[str],
    final_reason_counts: Counter[str],
    verifier_summary: Mapping[str, Any] | None = None,
) -> dict[str, str]:
    status = str(closeout.get("status") or "")
    ticker = str(closeout.get("ticker") or "").upper()
    if runtime_bucket_counts.get("product_kpi_exact"):
        return {
            "effective_product_kpi_status": "product_kpi_exact_ready",
            "diagnostic_class": "ready_product_kpi_exact",
            "diagnostic_reason": "runtime_product_or_product_line_kpi_row_available_after_repair",
            "coverage_bucket": "product_family_or_product_line_exact_ready",
            "public_boundary_assessment": "ready",
            "next_action": "Use within exact metric/product/period/citation boundary.",
        }
    if runtime_bucket_counts.get("business_segment_metric") or runtime_bucket_counts.get("business_segment_or_asset_metric"):
        return {
            "effective_product_kpi_status": "business_segment_metric_ready",
            "diagnostic_class": "ready_business_segment_metric_only",
            "diagnostic_reason": "runtime_business_segment_metric_available_after_repair",
            "coverage_bucket": "business_or_segment_exact_ready",
            "public_boundary_assessment": "usable_for_fundamental_business_mix_not_product_exact",
            "next_action": "Use for fundamental/business mix; keep SKU/product-family KPI as gap unless company discloses it.",
        }
    if status == "product_kpi_exact_ready":
        return {
            "effective_product_kpi_status": status,
            "diagnostic_class": "ready_product_kpi_exact",
            "diagnostic_reason": "company_disclosed_product_or_product_line_kpi_runtime_row_available",
            "coverage_bucket": "product_family_or_product_line_exact_ready",
            "public_boundary_assessment": "ready",
            "next_action": "Use within exact metric/product/period/citation boundary.",
        }
    if status == "business_segment_metric_ready":
        return {
            "effective_product_kpi_status": status,
            "diagnostic_class": "ready_business_segment_metric_only",
            "diagnostic_reason": "company_disclosed_business_segment_metric_available_not_sku_or_product_family_kpi",
            "coverage_bucket": "business_or_segment_exact_ready",
            "public_boundary_assessment": "usable_for_fundamental_business_mix_not_product_exact",
            "next_action": "Use for fundamental/business mix; keep product-family KPI as gap unless company discloses it.",
        }
    if status == "geographic_or_non_product_metric_only":
        return {
            "effective_product_kpi_status": status,
            "diagnostic_class": "geographic_or_non_product_only",
            "diagnostic_reason": "company_disclosed_metric_is_geography_generic_or_non_product",
            "coverage_bucket": "geographic_or_non_product_metric_not_product_kpi",
            "public_boundary_assessment": "not_product_kpi",
            "next_action": "Do not promote as product KPI; seek product-family disclosure or expose gap.",
        }
    if strict_candidates:
        verifier_diagnostic = _diagnose_from_source_specific_verifier(verifier_summary or {}, final_reason_counts)
        if verifier_diagnostic:
            return verifier_diagnostic
        reason = _primary_candidate_reason(strict_bucket_counts, final_reason_counts)
        return {
            "effective_product_kpi_status": status,
            "diagnostic_class": "parser_candidate_found_but_not_runtime_promotable",
            "diagnostic_reason": reason,
            "coverage_bucket": "candidate_exists_but_not_promotable",
            "public_boundary_assessment": "adapter_or_parser_deep_repair_possible_if_source_specific_gate_can_verify",
            "next_action": "Inspect candidate rows by closeout reason; add source-specific table/period/region/product-binding parser only where local citation proves value/unit/period/product.",
        }
    if int(closeout.get("official_surface_slot_count") or 0) or int(closeout.get("filings_taxonomy_slot_count") or 0):
        cls = "non_us_local_or_ir_parser_required" if NON_US_TICKER_RE.search(ticker) else "product_surface_or_taxonomy_available_no_company_kpi_candidate"
        return {
            "effective_product_kpi_status": status,
            "diagnostic_class": cls,
            "diagnostic_reason": "product_taxonomy_or_official_surface_exists_but_current_disclosure_scan_found_no_product_kpi_candidate",
            "coverage_bucket": "surface_or_taxonomy_only_no_kpi_candidate",
            "public_boundary_assessment": "may_require_ir_deck_annual_report_table_local_exchange_or_company_does_not_disclose",
            "next_action": "Run IR deck/local exchange/annual report table locator before declaring company-undisclosed commercial gap.",
        }
    return {
        "effective_product_kpi_status": status,
        "diagnostic_class": "no_product_kpi_candidate_in_current_public_scan",
        "diagnostic_reason": "no_company_disclosed_product_kpi_candidate_in_current_sec_or_public_disclosure_scan",
        "coverage_bucket": "no_candidate_in_current_public_scan",
        "public_boundary_assessment": "likely_company_undisclosed_or_locator_scope_gap",
        "next_action": "Check company IR/local regulator/annual report tables; if still empty, expose company-undisclosed or commercial-tracker gap.",
    }


def _primary_candidate_reason(strict_bucket_counts: Counter[str], final_reason_counts: Counter[str]) -> str:
    if final_reason_counts:
        reason, _ = final_reason_counts.most_common(1)[0]
        if reason:
            return f"final_quality_gate_rejected_candidate:{reason}"
    if strict_bucket_counts.get("geographic_or_non_product_metric"):
        return "strict_candidates_mostly_geographic_or_non_product"
    if strict_bucket_counts.get("business_segment_metric"):
        return "strict_candidates_are_business_segment_metrics_requiring_segment_schema_or_not_product_exact"
    if strict_bucket_counts.get("product_kpi_exact"):
        return "strict_product_candidates_need_local_citation_or_period_table_verifier"
    return "strict_candidates_exist_but_bucket_unclassified"


VERIFIER_CLASS_DIAGNOSTICS = {
    "business_segment_metric": {
        "diagnostic_class": "verifier_business_segment_only_candidates",
        "coverage_bucket": "business_segment_candidates_not_product_family_kpi",
        "public_boundary_assessment": "usable_for_fundamental_business_mix_not_product_exact",
        "next_action": "Route to business/segment metric slots for fundamental analysis; do not fill product-family KPI unless the company table binds product/category revenue directly.",
    },
    "business_segment_mixed_table_needs_column_group": {
        "diagnostic_class": "verifier_business_segment_column_group_required",
        "coverage_bucket": "mixed_segment_table_requires_column_group_schema",
        "public_boundary_assessment": "source_specific_parser_repair_possible_only_with_column_group_validation",
        "next_action": "Add source-specific column-group/period parser; promote only the revenue/level column, reject operating income, margin, cost, and mix columns.",
    },
    "region_only": {
        "diagnostic_class": "verifier_region_or_geography_only_candidates",
        "coverage_bucket": "region_geography_candidates_not_product_kpi",
        "public_boundary_assessment": "not_product_kpi_without_region_dimension_and_product_binding",
        "next_action": "Do not promote as product KPI; only use as geographic exposure if a region dimension is explicitly supported.",
    },
    "percentage_or_change": {
        "diagnostic_class": "verifier_percentage_or_change_only_candidates",
        "coverage_bucket": "percentage_or_change_cells_not_level_revenue",
        "public_boundary_assessment": "not_level_product_kpi",
        "next_action": "Reject as product KPI unless paired local table coordinates prove a currency level value for the same product/period.",
    },
    "operating_metric_defer_step2": {
        "diagnostic_class": "verifier_operating_metric_requires_industry_slot",
        "coverage_bucket": "operating_metric_candidates_require_industry_slot",
        "public_boundary_assessment": "usable_only_after_industry_metric_schema_maps_metric_unit_product_period",
        "next_action": "Route to industry operating metric slots such as AUM, deposits, MW, capacity, deliveries, ARR, subscribers, backlog, or patient volume.",
    },
    "sentence_relation_insufficient": {
        "diagnostic_class": "verifier_sentence_relation_insufficient",
        "coverage_bucket": "sentence_or_unstructured_candidate_needs_local_relation_verifier",
        "public_boundary_assessment": "parser_deep_repair_possible_only_with_local_product_value_relation",
        "next_action": "Run local sentence/table-neighborhood relation verifier; do not promote detached numeric mentions.",
    },
    "period_or_version_conflict": {
        "diagnostic_class": "verifier_period_or_version_conflict",
        "coverage_bucket": "period_or_restatement_conflict_requires_versioned_schema",
        "public_boundary_assessment": "requires_period_version_reconciliation_before_use",
        "next_action": "Add versioned period/column schema; keep conflicting current/prior-year or restatement rows out of product KPI until reconciled.",
    },
    "non_product_or_total": {
        "diagnostic_class": "verifier_non_product_or_total_candidates",
        "coverage_bucket": "generic_total_or_non_product_rows_not_product_kpi",
        "public_boundary_assessment": "not_product_kpi",
        "next_action": "Reject generic totals, operating profit, costs, corporate, eliminations, and non-product rows; seek product-family disclosure or expose gap.",
    },
    "product_table_context_insufficient": {
        "diagnostic_class": "verifier_product_table_context_insufficient",
        "coverage_bucket": "product_node_candidate_lacks_verified_product_revenue_table_context",
        "public_boundary_assessment": "source_specific_table_context_repair_possible",
        "next_action": "Verify the table title/header/caption locally before promotion; product alias alone is insufficient.",
    },
}


def _diagnose_from_source_specific_verifier(
    verifier_summary: Mapping[str, Any], final_reason_counts: Counter[str]
) -> dict[str, str] | None:
    class_counts = _counter_field(verifier_summary, "verifier_class_counts")
    if not class_counts:
        return None
    dominant_class, dominant_count = _dominant_verifier_class(class_counts)
    if not dominant_class:
        return None
    template = VERIFIER_CLASS_DIAGNOSTICS.get(dominant_class)
    if not template:
        return None
    top_reasons = _counter_field(verifier_summary, "top_verifier_reasons")
    dominant_reason = ""
    if top_reasons:
        dominant_reason, _ = top_reasons.most_common(1)[0]
    if final_reason_counts:
        final_reason, _ = final_reason_counts.most_common(1)[0]
        reason = f"source_specific_verifier_{dominant_class}:{dominant_reason or 'no_top_reason'};final_quality_gate:{final_reason}"
    else:
        reason = f"source_specific_verifier_{dominant_class}:{dominant_reason or 'no_top_reason'}"
    return {
        "effective_product_kpi_status": "product_kpi_exact_gap",
        "diagnostic_class": str(template["diagnostic_class"]),
        "diagnostic_reason": reason,
        "coverage_bucket": str(template["coverage_bucket"]),
        "public_boundary_assessment": str(template["public_boundary_assessment"]),
        "next_action": str(template["next_action"]),
        "dominant_verifier_class": dominant_class,
        "dominant_verifier_reason": dominant_reason,
    }


def _dominant_verifier_class(class_counts: Counter[str]) -> tuple[str, int]:
    priority = {
        "product_table_context_insufficient": 0,
        "business_segment_mixed_table_needs_column_group": 1,
        "sentence_relation_insufficient": 2,
        "period_or_version_conflict": 3,
        "operating_metric_defer_step2": 4,
        "business_segment_metric": 5,
        "region_only": 6,
        "percentage_or_change": 7,
        "non_product_or_total": 8,
    }
    return max(class_counts.items(), key=lambda item: (item[1], -priority.get(item[0], 99)))


def _bucket(row: Mapping[str, Any]) -> str:
    label = " ".join(
        str(row.get(key) or "")
        for key in ("product_or_segment", "matched_product_alias", "row_label", "metric_name")
    )
    node_type = str(row.get("product_node_type") or "")
    if GEOGRAPHIC_RE.search(label):
        return "geographic_or_non_product_metric"
    if GENERIC_RE.search(label):
        return "business_segment_metric" if node_type in BUSINESS_SEGMENT_NODE_TYPES else "geographic_or_non_product_metric"
    if node_type in PRODUCT_EXACT_NODE_TYPES:
        return "product_kpi_exact"
    if node_type in BUSINESS_SEGMENT_NODE_TYPES:
        return "business_segment_metric"
    if node_type == "asset_or_product_family":
        return "business_segment_or_asset_metric"
    return "geographic_or_non_product_metric"


def render_report(summary: Mapping[str, Any]) -> str:
    return "\n".join(
        [
            "# Product-KPI Deep Gap Diagnostic",
            "",
            f"- Generated at: `{summary.get('generated_at')}`",
            f"- Companies: `{summary.get('company_count')}`",
            f"- Product KPI statuses: `{json.dumps(summary.get('product_kpi_status_counts'), ensure_ascii=False, sort_keys=True)}`",
            f"- Coverage buckets: `{json.dumps(summary.get('coverage_bucket_counts'), ensure_ascii=False, sort_keys=True)}`",
            f"- Product family exact ready tickers: `{summary.get('product_family_exact_ready_ticker_count')}`",
            f"- Business/segment exact ready tickers: `{summary.get('business_or_segment_exact_ready_ticker_count')}`",
            f"- Product or business KPI ready tickers: `{summary.get('product_or_business_kpi_ready_ticker_count')}`",
            f"- Gap diagnostic classes: `{json.dumps(summary.get('gap_diagnostic_class_counts'), ensure_ascii=False, sort_keys=True)}`",
            f"- Strict-candidate gap tickers: `{summary.get('strict_candidate_gap_ticker_count')}`",
            f"- No-candidate gap tickers: `{summary.get('no_candidate_gap_ticker_count')}`",
            "",
            "## Boundary",
            "",
            str(summary.get("boundary") or ""),
            "",
        ]
    )


def _by_ticker(rows: Iterable[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        ticker = str(row.get("ticker") or "").upper()
        if ticker:
            out[ticker].append(dict(row))
    return out


def _single_by_ticker(rows: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        ticker = str(row.get("ticker") or "").upper()
        if ticker:
            out[ticker] = dict(row)
    return out


def _counter_field(row: Mapping[str, Any], key: str) -> Counter[str]:
    value = row.get(key)
    if not isinstance(value, Mapping):
        return Counter()
    return Counter({str(k): int(v or 0) for k, v in value.items() if str(k)})


def _dict_field(row: Mapping[str, Any], key: str) -> dict[str, int]:
    return dict(sorted(_counter_field(row, key).items()))


def _sample_fact(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "fact_id": row.get("fact_id") or row.get("evidence_ref") or "",
        "product_or_segment": row.get("product_or_segment") or "",
        "product_node_type": row.get("product_node_type") or "",
        "metric_family": row.get("metric_family") or "",
        "value": row.get("value"),
        "unit": row.get("unit") or "",
        "period": row.get("period") or "",
        "row_label": row.get("row_label") or "",
        "column_label": row.get("column_label") or "",
        "source_url": row.get("source_url") or "",
    }


def _sample_final_closeout(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "closeout_reason": row.get("closeout_reason") or row.get("rejection_reason") or "",
        "action_class": row.get("action_class") or "",
        "target_phase": row.get("target_phase") or "",
        "product_or_segment": row.get("product_or_segment") or "",
        "metric_family": row.get("metric_family") or "",
        "value": row.get("value"),
        "unit": row.get("unit") or "",
        "period": row.get("period") or "",
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
