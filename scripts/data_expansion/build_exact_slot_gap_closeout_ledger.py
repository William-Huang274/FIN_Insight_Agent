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


CLOSEOUT_SCHEMA_VERSION = "finsight_exact_slot_gap_closeout_v0_1"
PRODUCT_KPI_SCHEMA_VERSION = "finsight_product_kpi_exact_slot_closeout_v0_1"
SUMMARY_SCHEMA_VERSION = "finsight_exact_slot_gap_closeout_summary_v0_1"

DEFAULT_EXACT_COVERAGE = REPO_ROOT / "data" / "manifests" / "exact_slot_coverage_matrix_v0_1.jsonl"
DEFAULT_EXACT_GAPS = REPO_ROOT / "data" / "manifests" / "exact_slot_gap_ledger_v0_1.jsonl"
DEFAULT_PRODUCT_SLOTS = REPO_ROOT / "data" / "manifests" / "company_product_slots_v0_1.jsonl"
DEFAULT_PRODUCT_KPI_RUNTIME_ROW_PATHS = [
    REPO_ROOT / "data" / "manifests" / "company_disclosed_product_business_mix_runtime_rows_v0_1.jsonl",
    REPO_ROOT / "data" / "manifests" / "company_reported_product_operating_metric_runtime_rows_v0_1.jsonl",
    REPO_ROOT / "data" / "manifests" / "industry_operating_metric_slot_rows_v0_1.jsonl",
    REPO_ROOT / "data" / "manifests" / "non_us_product_kpi_local_disclosure_runtime_rows_v0_1.jsonl",
    REPO_ROOT / "data" / "manifests" / "r16_product_kpi_deep_repair_runtime_rows_v0_1.jsonl",
    REPO_ROOT / "data" / "manifests" / "r17_known_public_product_kpi_repair_runtime_rows_v0_1.jsonl",
]
DEFAULT_ATTEMPT_PATHS = [
    REPO_ROOT / "data" / "manifests" / "broad_hiring_capacity_attempts_v0_1.jsonl",
    REPO_ROOT / "data" / "manifests" / "broad_official_careers_attempts_v0_1.jsonl",
    REPO_ROOT / "data" / "manifests" / "broad_channel_offer_attempts_v0_1.jsonl",
    REPO_ROOT / "data" / "manifests" / "family_channel_distributor_attempts_v0_1.jsonl",
    REPO_ROOT / "data" / "manifests" / "broad_public_contract_award_attempts_v0_1.jsonl",
    REPO_ROOT / "data" / "manifests" / "local_public_tender_attempts_v0_1.jsonl",
    REPO_ROOT / "data" / "manifests" / "targeted_supply_chain_official_relationship_attempts_v0_1.jsonl",
    REPO_ROOT / "data" / "manifests" / "broad_app_store_platform_attempts_v0_1.jsonl",
    REPO_ROOT / "data" / "manifests" / "targeted_regulated_auto_official_api_attempts_v0_1.jsonl",
    REPO_ROOT / "data" / "manifests" / "v1_openalex_technology_research_attempts_v0_1.jsonl",
    REPO_ROOT / "data" / "manifests" / "v1_patentsview_technology_research_attempts_v0_1.jsonl",
    REPO_ROOT / "data" / "manifests" / "developer_ecosystem_attempts_v0_1.jsonl",
    REPO_ROOT / "data" / "manifests" / "r15_manual_public_source_attempts_v0_1.jsonl",
]
DEFAULT_SEC_FINANCIAL_SUMMARY = REPO_ROOT / "data" / "manifests" / "sec_financial_statement_metric_runtime_summary_v0_1.json"
DEFAULT_PRODUCT_KPI_SUMMARY = REPO_ROOT / "data" / "manifests" / "company_reported_product_operating_metric_runtime_summary_v0_1.json"
DEFAULT_OUTPUT_CLOSEOUT = REPO_ROOT / "data" / "manifests" / "exact_slot_gap_closeout_v0_1.jsonl"
DEFAULT_OUTPUT_PRODUCT_KPI = REPO_ROOT / "data" / "manifests" / "product_kpi_exact_slot_closeout_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY = REPO_ROOT / "data" / "manifests" / "exact_slot_gap_closeout_summary_v0_1.json"
DEFAULT_OUTPUT_REPORT = REPO_ROOT / "docs" / "internal" / "vnext_20260610" / "vertical_lanes" / "exact_slot_gap_closeout.zh-CN.md"

ATTEMPT_RELATED_REQUIREMENTS = {
    "hiring_capacity_proxy": {"job_postings_hiring_signals"},
    "channel_offer_proxy": {"channel_pricing_quotations", "ecommerce_major_platforms", "channel_distributor_locator"},
    "public_order_proxy": {"public_tenders_contracts_orders"},
    "supply_chain_official_relationship": {"public_tenders_contracts_orders", "supplier_customer_official_news"},
    "app_rank_store_proxy": {"itunes_search_api", "app_store_rankings"},
    "platform_review_proxy": {"itunes_search_api", "platform_reviews_rankings_downloads"},
    "regulated_product_context": {"clinicaltrials_api", "openfda_api", "cms_public_data", "fda_animal_drugs_api"},
    "auto_product_identity_context": {"nhtsa_vpic_api"},
    "technology_research_proxy": {"openalex_api", "patentsview_api"},
    "developer_ecosystem_proxy": {"developer_ecosystem_github_npm_pypi_huggingface"},
}

ATTEMPT_PROVIDER_SOURCE_ID_ALIASES = {
    "cdw": "channel_pricing_quotations",
    "cdw_product": "channel_pricing_quotations",
    "cdw_search": "channel_pricing_quotations",
    "official_channel_distributor_locator": "channel_distributor_locator",
    "greenhouse": "job_postings_hiring_signals",
    "lever": "job_postings_hiring_signals",
    "ashby": "job_postings_hiring_signals",
    "smartrecruiters": "job_postings_hiring_signals",
    "usaspending": "public_tenders_contracts_orders",
    "supplier_customer_official_news": "supplier_customer_official_news",
    "itunes_search": "itunes_search_api",
    "itunes_lookup": "itunes_search_api",
    "clinicaltrials": "clinicaltrials_api",
    "openfda": "openfda_api",
    "fda_animal_drugs": "fda_animal_drugs_api",
    "fda_animal_drugs_api": "fda_animal_drugs_api",
    "nhtsa_vpic": "nhtsa_vpic_api",
    "openalex": "openalex_api",
    "openalex_api": "openalex_api",
    "patentsview": "patentsview_api",
    "patentsview_api": "patentsview_api",
    "github": "developer_ecosystem_github_npm_pypi_huggingface",
    "npm": "developer_ecosystem_github_npm_pypi_huggingface",
    "pypi": "developer_ecosystem_github_npm_pypi_huggingface",
    "huggingface": "developer_ecosystem_github_npm_pypi_huggingface",
}

NON_US_PUBLIC_ORDER_TICKERS = {
    "ASML",
    "CCJ",
    "CSIQ",
    "DNN",
    "DQ",
    "ENLT",
    "HMC",
    "JKS",
    "NXE",
    "TM",
    "UROY",
}

NON_US_COMPANY_NAME_MARKERS = (
    " holding nv",
    " motor co ltd",
    " corp/",
    " limited",
    " ltd",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build auditable closeout rows for remaining exact-slot gaps.")
    parser.add_argument("--exact-coverage", type=Path, default=DEFAULT_EXACT_COVERAGE)
    parser.add_argument("--exact-gaps", type=Path, default=DEFAULT_EXACT_GAPS)
    parser.add_argument("--product-slots", type=Path, default=DEFAULT_PRODUCT_SLOTS)
    parser.add_argument(
        "--product-kpi-runtime-rows",
        dest="product_kpi_runtime_row_paths",
        type=Path,
        action="append",
        default=None,
        help="Product/business KPI runtime JSONL path. Can be repeated.",
    )
    parser.add_argument("--attempt-path", dest="attempt_paths", type=Path, action="append", default=None)
    parser.add_argument("--sec-financial-summary", type=Path, default=DEFAULT_SEC_FINANCIAL_SUMMARY)
    parser.add_argument("--product-kpi-summary", type=Path, default=DEFAULT_PRODUCT_KPI_SUMMARY)
    parser.add_argument("--output-closeout", type=Path, default=DEFAULT_OUTPUT_CLOSEOUT)
    parser.add_argument("--output-product-kpi", type=Path, default=DEFAULT_OUTPUT_PRODUCT_KPI)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--output-report", type=Path, default=DEFAULT_OUTPUT_REPORT)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    if args.attempt_paths is None:
        args.attempt_paths = DEFAULT_ATTEMPT_PATHS
    if args.product_kpi_runtime_row_paths is None:
        args.product_kpi_runtime_row_paths = DEFAULT_PRODUCT_KPI_RUNTIME_ROW_PATHS
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at = _utc_now()
    coverage_rows = _load_jsonl(args.exact_coverage)
    gap_rows = _load_jsonl(args.exact_gaps)
    product_slots = _load_jsonl(args.product_slots)
    attempts = [row for path in args.attempt_paths for row in _load_jsonl(path)]
    closeout_rows = build_gap_closeout_rows(
        gap_rows=gap_rows,
        attempts=attempts,
        sec_financial_summary=_load_json(args.sec_financial_summary),
        generated_at=generated_at,
    )
    product_kpi_rows = build_product_kpi_closeout_rows(
        coverage_rows=coverage_rows,
        product_slots=product_slots,
        product_kpi_runtime_rows=[row for path in args.product_kpi_runtime_row_paths for row in _load_jsonl(path)],
        product_kpi_summary=_load_json(args.product_kpi_summary),
        generated_at=generated_at,
    )
    summary = build_summary(
        coverage_rows=coverage_rows,
        gap_rows=gap_rows,
        closeout_rows=closeout_rows,
        product_kpi_rows=product_kpi_rows,
        generated_at=generated_at,
        output_closeout=args.output_closeout,
        output_product_kpi=args.output_product_kpi,
        output_report=args.output_report,
    )
    _write_jsonl(args.output_closeout, closeout_rows)
    _write_jsonl(args.output_product_kpi, product_kpi_rows)
    _write_json(args.output_summary, summary)
    args.output_report.parent.mkdir(parents=True, exist_ok=True)
    args.output_report.write_text(render_report(summary), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if args.strict and summary["unclassified_closeout_count"]:
        return 1
    return 0


def build_gap_closeout_rows(
    *,
    gap_rows: Iterable[Mapping[str, Any]],
    attempts: Iterable[Mapping[str, Any]],
    sec_financial_summary: Mapping[str, Any],
    generated_at: str,
) -> list[dict[str, Any]]:
    attempts_by_ticker_req = _attempts_by_ticker_requirement(attempts)
    sec_uncovered = {str(ticker).upper() for ticker in sec_financial_summary.get("uncovered_tickers") or []}
    out: list[dict[str, Any]] = []
    for gap in gap_rows:
        ticker = str(gap.get("ticker") or "").upper()
        requirement_id = str(gap.get("requirement_id") or "")
        related_attempts = attempts_by_ticker_req.get((ticker, requirement_id), [])
        closeout = _classify_gap(gap, related_attempts=related_attempts, sec_uncovered=sec_uncovered)
        out.append(
            {
                "schema_version": CLOSEOUT_SCHEMA_VERSION,
                "generated_at": generated_at,
                "closeout_id": f"{gap.get('gap_id')}:closeout",
                "gap_id": gap.get("gap_id"),
                "ticker": ticker,
                "company_name": gap.get("company_name") or "",
                "primary_lane_id": gap.get("primary_lane_id") or "",
                "requirement_id": requirement_id,
                "dimension": gap.get("dimension") or "",
                "gap_class": gap.get("gap_class") or "",
                "source_gate_gap_type": gap.get("source_gate_gap_type") or "",
                "closeout_class": closeout["closeout_class"],
                "closeout_reason": closeout["closeout_reason"],
                "attempt_count": len(related_attempts),
                "attempt_status_counts": dict(sorted(Counter(str(row.get("status") or "") for row in related_attempts).items())),
                "attempt_provider_counts": dict(sorted(Counter(str(row.get("provider") or row.get("source_id") or "") for row in related_attempts).items())),
                "sample_attempts": [
                    {
                        "source_id": row.get("source_id") or "",
                        "provider": row.get("provider") or "",
                        "status": row.get("status") or "",
                        "source_url": row.get("source_url") or row.get("api_url") or "",
                        "reason": row.get("reason") or "",
                    }
                    for row in related_attempts[:5]
                ],
                "public_data_ceiling": closeout["public_data_ceiling"],
                "next_action": closeout["next_action"],
                "claim_boundary": gap.get("claim_boundary") or "",
            }
        )
    return out


def build_product_kpi_closeout_rows(
    *,
    coverage_rows: Iterable[Mapping[str, Any]],
    product_slots: Iterable[Mapping[str, Any]],
    product_kpi_runtime_rows: Iterable[Mapping[str, Any]] = (),
    product_kpi_summary: Mapping[str, Any],
    generated_at: str,
) -> list[dict[str, Any]]:
    slots_by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for slot in product_slots:
        ticker = str(slot.get("ticker") or "").upper()
        if ticker:
            slots_by_ticker[ticker].append(dict(slot))
    runtime_by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in product_kpi_runtime_rows:
        ticker = str(row.get("ticker") or "").upper()
        if ticker:
            runtime_by_ticker[ticker].append(dict(row))
    coverage_by_ticker = {str(row.get("ticker") or "").upper(): dict(row) for row in coverage_rows if row.get("ticker")}
    out: list[dict[str, Any]] = []
    for ticker, coverage in sorted(coverage_by_ticker.items()):
        slots = slots_by_ticker.get(ticker, [])
        runtime_rows = runtime_by_ticker.get(ticker, [])
        classified = _classify_product_kpi_runtime_rows(runtime_rows)
        kpi_slots = [slot for slot in slots if slot.get("slot_status") == "product_kpi_exact_slot"]
        official_slots = [slot for slot in slots if slot.get("slot_status") == "official_surface_slot"]
        taxonomy_slots = [slot for slot in slots if slot.get("slot_status") == "filings_taxonomy_slot"]
        product_rows = classified["product_kpi_exact_rows"]
        segment_rows = classified["business_segment_metric_rows"]
        non_product_rows = classified["geographic_or_non_product_rows"]
        if product_rows:
            status = "product_kpi_exact_ready"
            reason = "company_disclosed_product_kpi_runtime_row_available"
        elif segment_rows:
            status = "business_segment_metric_ready"
            reason = "company_disclosed_business_segment_metric_available_but_not_product_family_kpi"
        elif non_product_rows:
            status = "geographic_or_non_product_metric_only"
            reason = "company_disclosed_metric_available_but_geographic_or_non_product_only"
        else:
            status = "product_kpi_exact_gap"
            reason = _product_kpi_gap_reason(slots, coverage)
        out.append(
            {
                "schema_version": PRODUCT_KPI_SCHEMA_VERSION,
                "generated_at": generated_at,
                "ticker": ticker,
                "company_name": coverage.get("company_name") or "",
                "primary_lane_id": coverage.get("primary_lane_id") or "",
                "status": status,
                "closeout_reason": reason,
                "product_slot_count": len(slots),
                "product_kpi_exact_slot_count": len(kpi_slots),
                "runtime_product_kpi_row_count": len(runtime_rows),
                "runtime_product_kpi_exact_row_count": len(product_rows),
                "runtime_business_segment_metric_row_count": len(segment_rows),
                "runtime_geographic_or_non_product_metric_row_count": len(non_product_rows),
                "official_surface_slot_count": len(official_slots),
                "filings_taxonomy_slot_count": len(taxonomy_slots),
                "sample_product_kpi_slots": [_slot_sample(slot) for slot in kpi_slots[:5]],
                "sample_runtime_product_kpi_rows": [_runtime_kpi_sample(row) for row in product_rows[:5]],
                "sample_runtime_business_segment_rows": [_runtime_kpi_sample(row) for row in segment_rows[:5]],
                "sample_runtime_non_product_rows": [_runtime_kpi_sample(row) for row in non_product_rows[:5]],
                "sample_non_kpi_slots": [_slot_sample(slot) for slot in (official_slots or taxonomy_slots or slots)[:5]],
                "runtime_product_kpi_summary_status": product_kpi_summary.get("status") or "",
                "claim_boundary": (
                    "Product KPI exact slots require company-disclosed product/product-line operating metric rows. "
                    "Business-segment metrics can support fundamental/business mix analysis but are not SKU/product-family proof. "
                    "Geographic or generic non-product rows cannot fill product KPI exact slots. Official product pages, filings taxonomy, "
                    "hiring, channel, macro, app, developer, or award proxies cannot fill product KPI exact slots."
                ),
                "next_action": (
                    _product_kpi_next_action(status)
                ),
            }
        )
    return out


def build_summary(
    *,
    coverage_rows: list[dict[str, Any]],
    gap_rows: list[dict[str, Any]],
    closeout_rows: list[dict[str, Any]],
    product_kpi_rows: list[dict[str, Any]],
    generated_at: str,
    output_closeout: Path,
    output_product_kpi: Path,
    output_report: Path,
) -> dict[str, Any]:
    product_status_counts = Counter(str(row.get("status") or "") for row in product_kpi_rows)
    runtime_product_ticker_count = sum(1 for row in product_kpi_rows if int(row.get("runtime_product_kpi_row_count") or 0) > 0)
    product_exact_ticker_count = sum(1 for row in product_kpi_rows if row.get("status") == "product_kpi_exact_ready")
    segment_metric_ticker_count = sum(1 for row in product_kpi_rows if row.get("status") == "business_segment_metric_ready")
    non_product_metric_ticker_count = sum(1 for row in product_kpi_rows if row.get("status") == "geographic_or_non_product_metric_only")
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "pass" if closeout_rows and not [row for row in closeout_rows if row.get("closeout_class") == "unclassified_gap"] else "gap",
        "company_count": len(coverage_rows),
        "exact_gap_count": len(gap_rows),
        "closeout_row_count": len(closeout_rows),
        "closeout_class_counts": dict(sorted(Counter(str(row.get("closeout_class") or "") for row in closeout_rows).items())),
        "closeout_reason_counts": dict(sorted(Counter(str(row.get("closeout_reason") or "") for row in closeout_rows).items())),
        "closeout_by_requirement": dict(sorted(Counter(str(row.get("requirement_id") or "") for row in closeout_rows).items())),
        "unclassified_closeout_count": sum(1 for row in closeout_rows if row.get("closeout_class") == "unclassified_gap"),
        "product_kpi_company_count": len(product_kpi_rows),
        "product_kpi_status_counts": dict(sorted(product_status_counts.items())),
        "product_kpi_gap_count": product_status_counts.get("product_kpi_exact_gap", 0),
        "runtime_product_kpi_ticker_count": runtime_product_ticker_count,
        "product_kpi_exact_ready_ticker_count": product_exact_ticker_count,
        "business_segment_metric_ready_ticker_count": segment_metric_ticker_count,
        "product_or_business_kpi_ready_ticker_count": product_exact_ticker_count + segment_metric_ticker_count,
        "geographic_or_non_product_metric_only_ticker_count": non_product_metric_ticker_count,
        "outputs": {
            "closeout": str(output_closeout),
            "product_kpi": str(output_product_kpi),
            "report": str(output_report),
        },
        "policy": (
            "Every remaining L1/L2/L3 exact-slot gap is classified with attempts or source-boundary reason. "
            "Closeout rows are not evidence rows and must not be promoted by Research Lead, specialists, Memo Writer, or Verifier."
        ),
    }


def render_report(summary: Mapping[str, Any]) -> str:
    lines = [
        "# Exact Slot Gap Closeout",
        "",
        f"- schema_version: `{summary.get('schema_version')}`",
        f"- generated_at: `{summary.get('generated_at')}`",
        f"- status: `{summary.get('status')}`",
        f"- company_count: `{summary.get('company_count')}`",
        f"- exact_gap_count: `{summary.get('exact_gap_count')}`",
        f"- closeout_row_count: `{summary.get('closeout_row_count')}`",
        f"- product_kpi_gap_count: `{summary.get('product_kpi_gap_count')}`",
        "",
        "## Closeout By Requirement",
        "",
        "| requirement | count |",
        "| --- | ---: |",
    ]
    for req, count in sorted((summary.get("closeout_by_requirement") or {}).items()):
        lines.append(f"| {req} | {count} |")
    lines.extend(["", "## Closeout Classes", "", "| class | count |", "| --- | ---: |"])
    for klass, count in sorted((summary.get("closeout_class_counts") or {}).items()):
        lines.append(f"| {klass} | {count} |")
    lines.extend(["", "## Closeout Reasons", "", "| reason | count |", "| --- | ---: |"])
    for reason, count in sorted((summary.get("closeout_reason_counts") or {}).items()):
        lines.append(f"| {reason} | {count} |")
    lines.extend(["", "## Policy", "", str(summary.get("policy") or ""), ""])
    return "\n".join(lines)


def _classify_gap(
    gap: Mapping[str, Any],
    *,
    related_attempts: list[dict[str, Any]],
    sec_uncovered: set[str],
) -> dict[str, str]:
    requirement_id = str(gap.get("requirement_id") or "")
    ticker = str(gap.get("ticker") or "").upper()
    gap_class = str(gap.get("gap_class") or "")
    attempt_statuses = {str(row.get("status") or "") for row in related_attempts}
    rejected_statuses = gap.get("rejected_statuses") if isinstance(gap.get("rejected_statuses"), Mapping) else {}

    if requirement_id == "primary_company_disclosure":
        if ticker in sec_uncovered:
            return _closeout(
                "parser_or_source_profile_gap",
                "non_us_or_uncovered_sec_companyfacts_requires_local_exchange_or_ir_table_parser",
                "Official filing exists or may exist, but no parser-verified statement metric is available in SEC CompanyFacts runtime rows.",
                "Finish local exchange/company IR table parser for non-US reports; do not substitute product pages or proxy rows.",
            )
    if requirement_id == "hiring_capacity_proxy":
        if "entity_binding_gap" in rejected_statuses or "materialized" in attempt_statuses:
            return _closeout(
                "resolver_gap",
                "public_ats_endpoint_materialized_but_issuer_binding_not_verified",
                "Public ATS endpoint returned jobs, but board-token/company binding was not strong enough for exact-slot promotion.",
                "Add official careers-page/ATS token resolver before promotion; keep unverified rows out of ClaimCards.",
            )
        if related_attempts:
            return _closeout(
                "public_source_exhausted_gap",
                "public_ats_and_official_careers_no_bound_job_rows",
                "Greenhouse, Lever, Ashby, SmartRecruiters, Workday, Jibe, Phenom, SuccessFactors, and official careers pages were attempted where locatable; no issuer-bound exact job rows were found.",
                "Add further site-specific careers locators only when official site exposes stable public job rows or API routes.",
            )
    if requirement_id == "channel_offer_proxy":
        if related_attempts:
            attempt_source_ids = {source_id for row in related_attempts for source_id in _attempt_source_ids(row)}
            if "channel_distributor_locator" in attempt_source_ids:
                return _closeout(
                    "public_source_exhausted_gap",
                    "official_channel_distributor_locator_no_bound_channel_row",
                    (
                        "Official-domain channel/distributor/store locator routes were attempted after CDW; remaining pages were blocked, "
                        "missing locator links, or lacked issuer/product-family bound channel rows."
                    ),
                    "Only continue with source-specific Playwright or official marketplace adapters where public pages expose stable issuer-bound channel rows; do not infer ASP, inventory, sell-through, sales, revenue, or share.",
                )
            return _closeout(
                "public_source_exhausted_gap",
                "cdw_channel_search_no_verified_sku_price_availability_match",
                "CDW public search/product pages were crawled; returned products either did not bind to issuer/product or lacked exact offer fields.",
                "Add distributor-specific adapters such as Digi-Key/Mouser/Arrow/Amazon/JD only by product family; do not infer channel inventory/ASP.",
            )
        return _closeout(
            "adapter_or_locator_deep_repair_needed",
            "channel_offer_route_applicable_but_no_company_family_channel_attempt",
            "The product-family route requires public channel offer evidence, but no source-specific channel adapter attempt is recorded for this issuer/family.",
            "Run family-scoped CDW/Digi-Key/Mouser/Arrow/Amazon/JD/official-store locator and promote only SKU/price/availability snapshots.",
        )
    if requirement_id == "supply_chain_official_relationship":
        if related_attempts:
            attempt_source_ids = {source_id for row in related_attempts for source_id in _attempt_source_ids(row)}
            if "supplier_customer_official_news" in attempt_source_ids:
                return _closeout(
                    "public_source_exhausted_gap",
                    "official_supply_chain_relationship_page_no_issuer_counterparty_bound_row",
                    "Official supplier/customer/partner pages were attempted, but no issuer-and-counterparty-bound relationship row was available.",
                    "Continue only with official issuer/customer/supplier/news/contract disclosures; do not infer customer concentration, orders, shipments, revenue, or share.",
                )
            return _closeout(
                "public_source_exhausted_gap",
                "usaspending_no_recipient_bound_supply_chain_award_proxy",
                "USAspending public-award API was attempted as a weak supply-chain/order proxy; no recipient-bound exact slot was available.",
                "Prefer official customer/supplier/news/contract disclosures before procurement proxy; do not infer total orders/backlog.",
            )
        return _closeout(
            "adapter_or_locator_deep_repair_needed",
            "supply_chain_route_applicable_but_no_official_relationship_attempt",
            "The product-family route requires official supplier/customer relationship evidence, but no official relationship locator attempt is recorded for this issuer/family.",
            "Run official issuer/customer/supplier/news/contract locators before declaring supply-chain relationship gap final.",
        )
    if requirement_id == "public_order_proxy":
        jurisdiction = _public_order_jurisdiction(ticker, str(gap.get("company_name") or ""))
        if jurisdiction != "us":
            if _has_local_public_tender_attempt(related_attempts):
                return _closeout(
                    "public_source_exhausted_gap",
                    f"{jurisdiction}_local_tender_no_supplier_bound_award_or_no_structured_award_endpoint",
                    (
                        "Jurisdiction-specific public tender / award source was attempted, but no supplier-bound award row with "
                        "award id, amount, award date, and agency was available for this issuer."
                    ),
                    "Keep this as a public-order gap unless a stable local exchange, regulator, procurement API, or official company contract disclosure exposes supplier-bound award rows.",
                )
            return _closeout(
                "adapter_or_locator_deep_repair_needed",
                f"{jurisdiction}_public_order_local_tender_adapter_required",
                (
                    "The public-order route is jurisdiction-bound and USAspending is not the authoritative primary endpoint for this issuer. "
                    "No local tender/exchange/regulator/company-contract parser is recorded."
                ),
                "Run jurisdiction-specific local tender, regulator award, exchange filing, or company official contract-disclosure adapters; do not infer orders/backlog from generic web results.",
            )
        if related_attempts:
            return _closeout(
                "public_source_exhausted_gap",
                "usaspending_no_recipient_bound_award_or_api_fetch_gap",
                "USAspending public-award API was attempted; no recipient-bound award exact slot was available for this issuer/role.",
                "Add SAM/state/local/official customer-news adapters only where public endpoints expose recipient-bound rows; do not infer total orders/backlog.",
            )
        return _closeout(
            "adapter_or_locator_deep_repair_needed",
            "us_public_order_route_applicable_but_no_usaspending_attempt",
            "The product-family route requires public order evidence for a US issuer, but no USAspending/SAM/source-specific attempt is recorded.",
            "Run USAspending/SAM/state/local tender and official customer-news locators before declaring public-order gap final.",
        )
    if requirement_id in {"app_rank_store_proxy", "platform_review_proxy"}:
        if related_attempts:
            return _closeout(
                "public_source_exhausted_gap",
                "itunes_search_no_seller_bound_app_or_platform_listing",
                "iTunes public search/lookup was attempted with company and configured brand/subsidiary aliases; no seller-bound app/listing exact slot was available.",
                "Add Google Play/G2/Capterra/vendor marketplace adapters where source terms allow and product binding is verifiable.",
            )
        return _closeout(
            "adapter_or_locator_deep_repair_needed",
            "app_or_platform_route_applicable_but_no_seller_bound_attempt",
            "The product-family route requires app or platform review evidence, but no seller/product-bound marketplace attempt is recorded for this issuer/family.",
            "Run iTunes/Google Play/G2/Capterra/vendor marketplace locators with seller/product binding before declaring the proxy unavailable.",
        )
    if requirement_id == "regulated_product_context":
        if related_attempts:
            return _closeout(
                "public_source_exhausted_gap",
                "clinicaltrials_openfda_no_sponsor_collaborator_or_applicant_bound_record",
                "ClinicalTrials/openFDA public APIs were attempted; no sponsor/collaborator/applicant-bound exact regulatory row was found.",
                "For providers/labs/distributors, mark source not applicable; for pharma/medtech, add product/indication alias resolver.",
            )
    if requirement_id == "auto_product_identity_context":
        if related_attempts:
            return _closeout(
                "not_applicable_or_source_gap",
                "nhtsa_make_model_not_applicable_or_no_make_bound_record",
                "NHTSA vPIC was attempted or source matrix required auto identity for non-OEM companies; no exact make/model row is available.",
                "Restrict NHTSA requirement to vehicle OEMs and add make aliases only for actual manufacturers.",
            )
        return _closeout(
            "adapter_or_locator_deep_repair_needed",
            "auto_identity_route_applicable_but_no_make_model_attempt",
            "The route requires NHTSA/make-model identity context, but no make/model resolver attempt is recorded for this issuer/family.",
            "Run NHTSA vPIC make/model resolver with OEM aliases before declaring auto identity context unavailable.",
        )
    if requirement_id == "developer_ecosystem_proxy":
        if related_attempts:
            if "materialized" in attempt_statuses:
                return _closeout(
                    "parser_gap",
                    "developer_ecosystem_materialized_row_failed_exact_slot_contract",
                    "A GitHub/npm/PyPI/HuggingFace row was materialized for this issuer, but the exact-slot contract did not accept it for developer ecosystem proxy.",
                    "Inspect fact_label/activity fields and issuer/product binding before promotion; keep unverified rows out of ClaimCards.",
                )
            return _closeout(
                "public_source_exhausted_gap",
                "developer_ecosystem_official_seed_fetch_or_binding_failed",
                "Official developer seed URLs were attempted, but no issuer/product-bound GitHub/npm/PyPI/HuggingFace exact proxy row was materialized.",
                "Add official docs-to-repo/package locator only when company site, official docs, or package metadata verifies issuer/product binding.",
            )
        return _closeout(
            "resolver_gap",
            "no_verified_project_to_issuer_product_resolver_for_broad_developer_artifacts",
            "No issuer/product-bound GitHub/npm/PyPI/HuggingFace artifact seed exists for broad promotion; blind project search would create false bindings.",
            "Build official docs/package/repo locator by product family before broad API materialization; use token-authenticated API for scale.",
        )
    if requirement_id == "official_product_surface":
        return _closeout(
            "adapter_or_locator_deep_repair_needed",
            "official_product_surface_seed_available_but_not_materialized_to_family_exact_slot",
            "A company/product-family official surface route is applicable, but the seed has not been materialized into an issuer/product-bound official product slot.",
            "Run official product sitemap/catalog/IR product page locator and source-specific parser; do not use unrelated homepage text as product evidence.",
        )
    if requirement_id == "technology_research_proxy":
        if related_attempts:
            attempt_source_ids = {source_id for row in related_attempts for source_id in _attempt_source_ids(row)}
            patentsview_attempted = "patentsview_api" in attempt_source_ids
            openalex_attempted = "openalex_api" in attempt_source_ids
            patentsview_statuses = {
                str(row.get("status") or "")
                for row in related_attempts
                if "patentsview_api" in _attempt_source_ids(row)
            }
            if "materialized" in attempt_statuses:
                return _closeout(
                    "parser_gap",
                    "openalex_patentsview_materialized_proxy_row_failed_exact_slot_contract",
                    "OpenAlex or PatentsView returned issuer/product-bound technology proxy rows, but the exact-slot contract did not accept them for this requirement.",
                    "Inspect parser_status/source_id/entity binding contract before promotion; keep rows as L3 technology proxy only.",
                )
            if patentsview_statuses.intersection({"missing_patentsview_api_key"}):
                return _closeout(
                    "adapter_or_locator_deep_repair_needed",
                    "patentsview_api_key_missing_or_patentsearch_unavailable",
                    (
                        "OpenAlex/PatentsView technology route is applicable, but the PatentsView PatentSearch API could not be used "
                        "without an API key in the current runtime; no assignee/topic-bound IP proxy row can be promoted from URL existence."
                    ),
                    "Provide PATENTSVIEW_API_KEY/USPTO_PATENTSVIEW_API_KEY or use USPTO ODP bulk downloads with assignee resolver; keep technology proxy bounded.",
                )
            if attempt_statuses.intersection({"fetch_failed", "unusable_response"}):
                reason = "patentsview_public_api_fetch_or_payload_gap" if patentsview_attempted else "openalex_public_api_fetch_or_payload_gap"
                provider = "PatentsView/OpenAlex" if patentsview_attempted and openalex_attempted else ("PatentsView" if patentsview_attempted else "OpenAlex")
                return _closeout(
                    "adapter_or_locator_deep_repair_needed",
                    reason,
                    f"{provider} API was attempted, but the public response could not be parsed or fetched reliably for this issuer/product-family route.",
                    "Retry with narrower product aliases, lower per-page, explicit rate-limit handling, PatentsView key, or USPTO ODP bulk downloads where applicable.",
                )
            if patentsview_attempted:
                return _closeout(
                    "public_source_exhausted_gap",
                    "openalex_patentsview_no_issuer_topic_or_assignee_bound_research_proxy",
                    "OpenAlex and/or PatentsView was attempted with company/product-family aliases; no issuer/topic or assignee/topic-bound research/IP proxy row was found.",
                    "Treat technology research proxy as unavailable from current free public route; add official technical publications only when issuer/product aliases are verifiable.",
                )
            return _closeout(
                "public_source_exhausted_gap",
                "openalex_no_issuer_topic_bound_research_proxy",
                "OpenAlex public API was attempted with company/product-family aliases; no issuer/topic-bound research proxy row was found.",
                "Treat technology research proxy as unavailable from current free public route; add PatentsView or official technical publications only when issuer/product aliases are verifiable.",
            )
        reason = (
            "openalex_patentsview_seed_available_but_not_materialized_to_issuer_product_proxy"
            if str(gap.get("gap_class") or "") == "seed_available_not_materialized_to_exact_slot"
            else "openalex_patentsview_route_applicable_but_no_issuer_product_bound_attempt"
        )
        return _closeout(
            "adapter_or_locator_deep_repair_needed",
            reason,
            "Technology/research proxy is applicable for this product family, but no issuer/product-bound OpenAlex or PatentsView proxy exact row is available yet.",
            "Run family-scoped OpenAlex/PatentsView resolver using company/product aliases; keep outputs as technology proxy only.",
        )
    if gap_class == "parser_or_structured_field_gap":
        return _closeout(
            "parser_gap",
            "source_row_observed_but_required_exact_fields_missing",
            "A source row exists but lacks required exact-slot fields.",
            "Repair source-specific parser and rerun exact-slot contract gate.",
        )
    return _closeout(
        "unclassified_gap",
        "gap_requires_manual_source_route_review",
        "No closeout rule matched this gap.",
        "Inspect source route and add source-specific attempt or applicability rule.",
    )


def _closeout(closeout_class: str, reason: str, ceiling: str, next_action: str) -> dict[str, str]:
    return {
        "closeout_class": closeout_class,
        "closeout_reason": reason,
        "public_data_ceiling": ceiling,
        "next_action": next_action,
    }


def _product_kpi_gap_reason(slots: list[Mapping[str, Any]], coverage: Mapping[str, Any]) -> str:
    if any(slot.get("slot_status") == "official_surface_slot" for slot in slots):
        return "official_product_surface_available_but_company_disclosed_product_kpi_absent"
    if any(slot.get("slot_status") == "filings_taxonomy_slot" for slot in slots):
        return "filings_taxonomy_available_but_value_unit_period_product_kpi_absent"
    if slots:
        return "product_context_available_but_no_company_disclosed_product_kpi_exact_slot"
    if coverage.get("exact_ready_requirement_count"):
        return "company_has_other_exact_slots_but_no_product_family_kpi_slot"
    return "no_product_slot_available"


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

GEOGRAPHIC_OR_NON_PRODUCT_RE = (
    "north america|latin america|emea|apac|asia|europe|africa|international|domestic|"
    "united states|u\\.s\\.|us |canada|mexico|china|japan|korea|india|brazil|"
    "other countries|rest of world|geographic|region|regional|country"
)

GENERIC_NON_PRODUCT_RE = (
    "products and services|total products|total services|corporate|other|all other|"
    "eliminations|reconciliation|unallocated|intercompany|total company|consolidated"
)


def _classify_product_kpi_runtime_rows(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    product_rows: list[dict[str, Any]] = []
    segment_rows: list[dict[str, Any]] = []
    non_product_rows: list[dict[str, Any]] = []
    for row in rows:
        bucket = _runtime_product_kpi_bucket(row)
        if bucket == "product_kpi_exact":
            product_rows.append(row)
        elif bucket == "business_segment_metric":
            segment_rows.append(row)
        else:
            non_product_rows.append(row)
    return {
        "product_kpi_exact_rows": product_rows,
        "business_segment_metric_rows": segment_rows,
        "geographic_or_non_product_rows": non_product_rows,
    }


def _runtime_product_kpi_bucket(row: Mapping[str, Any]) -> str:
    label = " ".join(
        str(row.get(key) or "")
        for key in ("product_or_segment", "matched_product_alias", "row_label", "metric_name")
    ).lower()
    node_type = str(row.get("product_node_type") or "").strip()
    if re.search(GEOGRAPHIC_OR_NON_PRODUCT_RE, label, flags=re.IGNORECASE):
        return "geographic_or_non_product_metric"
    if re.search(GENERIC_NON_PRODUCT_RE, label, flags=re.IGNORECASE):
        return "business_segment_metric" if node_type in BUSINESS_SEGMENT_NODE_TYPES else "geographic_or_non_product_metric"
    if node_type in PRODUCT_EXACT_NODE_TYPES:
        return "product_kpi_exact"
    if node_type in BUSINESS_SEGMENT_NODE_TYPES:
        return "business_segment_metric"
    if node_type == "asset_or_product_family":
        return "business_segment_metric"
    return "geographic_or_non_product_metric"


def _runtime_kpi_sample(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "evidence_ref": row.get("evidence_ref") or row.get("evidence_id") or "",
        "product_or_segment": row.get("product_or_segment") or "",
        "metric_name": row.get("metric_name") or "",
        "value": row.get("value"),
        "unit": row.get("unit") or "",
        "period": row.get("period") or "",
        "product_node_type": row.get("product_node_type") or "",
        "source_url": row.get("source_url") or "",
    }


def _product_kpi_next_action(status: str) -> str:
    if status == "product_kpi_exact_ready":
        return "Use company-disclosed product/product-line KPI rows as strong product evidence within their cited metric/product/period boundary."
    if status == "business_segment_metric_ready":
        return "Use disclosed business segment metrics for fundamental/business mix analysis, and continue product-family parser/IR deck/local filing search if product-level KPI is needed."
    if status == "geographic_or_non_product_metric_only":
        return "Do not promote geography/generic rows as product KPI; seek product-family disclosures or expose product-KPI gap."
    return "Use company filing/IR table parser for disclosed product KPIs; if company does not disclose the product metric, expose commercial tracker or company-undisclosed gap rather than substituting proxy evidence."


def _slot_sample(slot: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "product_slot_id": slot.get("product_slot_id") or "",
        "product_slot_name": slot.get("product_slot_name") or "",
        "family_id": slot.get("family_id") or "",
        "slot_status": slot.get("slot_status") or "",
        "sample_urls": list(slot.get("sample_urls") or [])[:2],
    }


def _public_order_jurisdiction(ticker: str, company_name: str) -> str:
    ticker_upper = str(ticker or "").upper()
    company_lower = f" {str(company_name or '').lower()} "
    if ticker_upper.endswith(".HK"):
        return "hk"
    if ticker_upper.endswith(".TW"):
        return "tw"
    if ticker_upper.endswith(".T"):
        return "jp"
    if ticker_upper.endswith(".DE"):
        return "eu_de"
    if ticker_upper.endswith(".SZ") or ticker_upper.endswith(".SS"):
        return "cn"
    if ticker_upper in NON_US_PUBLIC_ORDER_TICKERS:
        return "non_us_fpi_or_adr"
    if ticker_upper and "." in ticker_upper:
        return "non_us_local"
    if any(marker in company_lower for marker in NON_US_COMPANY_NAME_MARKERS) and ticker_upper not in {"BILL", "IOT", "PATH", "SHOP"}:
        return "non_us_possible"
    return "us"


def _attempts_by_ticker_requirement(attempts: Iterable[Mapping[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    out: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for attempt in attempts:
        ticker = str(attempt.get("ticker") or "").upper()
        attempt_source_ids = _attempt_source_ids(attempt)
        for req_id, related_source_ids in ATTEMPT_RELATED_REQUIREMENTS.items():
            if related_source_ids.intersection(attempt_source_ids):
                out[(ticker, req_id)].append(dict(attempt))
    return out


def _attempt_source_ids(attempt: Mapping[str, Any]) -> set[str]:
    values = {
        str(attempt.get("source_id") or "").strip().lower(),
        str(attempt.get("underlying_source_id") or "").strip().lower(),
    }
    provider = str(attempt.get("provider") or "").strip().lower()
    if provider:
        values.add(provider)
        if provider in ATTEMPT_PROVIDER_SOURCE_ID_ALIASES:
            values.add(ATTEMPT_PROVIDER_SOURCE_ID_ALIASES[provider])
    return {value for value in values if value}


def _has_local_public_tender_attempt(attempts: Iterable[Mapping[str, Any]]) -> bool:
    local_providers = {
        "hk_open_data_contract_awards",
        "tw_pcc_eprocurement",
        "jp_jetro_procurement",
        "local_public_tender",
    }
    for attempt in attempts:
        provider = str(attempt.get("provider") or "").strip().lower()
        if provider in local_providers:
            return True
    return False


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


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return dict(value) if isinstance(value, Mapping) else {}


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
