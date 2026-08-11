from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]

SCHEMA_VERSION = "finsight_company_gap_docket_v0_1"
CLUSTER_SCHEMA_VERSION = "finsight_company_gap_adapter_cluster_v0_1"
SUMMARY_SCHEMA_VERSION = "finsight_company_gap_docket_summary_v0_1"

DEFAULT_SOURCE_CLOSEOUT = REPO_ROOT / "data" / "manifests" / "exact_slot_gap_closeout_v0_1.jsonl"
DEFAULT_PRODUCT_KPI_DIAGNOSTIC = REPO_ROOT / "data" / "manifests" / "product_kpi_deep_gap_diagnostic_v0_1.jsonl"
DEFAULT_PRODUCT_KPI_VERIFIER_TICKER_SUMMARY = (
    REPO_ROOT / "data" / "manifests" / "product_kpi_source_specific_verifier_ticker_summary_v0_1.jsonl"
)
DEFAULT_COVERAGE_MATRIX = REPO_ROOT / "data" / "manifests" / "exact_slot_coverage_matrix_v0_1.jsonl"
DEFAULT_FAMILY_ASSIGNMENTS = REPO_ROOT / "data" / "manifests" / "company_product_family_assignments_v0_1.jsonl"
DEFAULT_FAMILY_ROUTE_PLAN = REPO_ROOT / "data" / "manifests" / "family_source_route_plan_v0_1.jsonl"
DEFAULT_OUTPUT_DOCKET = REPO_ROOT / "data" / "manifests" / "company_gap_docket_v0_1.jsonl"
DEFAULT_OUTPUT_CLUSTERS = REPO_ROOT / "data" / "manifests" / "company_gap_adapter_cluster_queue_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY = REPO_ROOT / "data" / "manifests" / "company_gap_docket_summary_v0_1.json"
DEFAULT_OUTPUT_REPORT = (
    REPO_ROOT / "docs" / "internal" / "vnext_20260610" / "vertical_lanes" / "company_gap_docket.zh-CN.md"
)

NON_US_TICKER_SUFFIXES = (".HK", ".KS", ".TW", ".T", ".DE", ".L", ".PA", ".AS", ".SW", ".TO", ".SZ")

SOURCE_ROLE_RULES: dict[str, dict[str, Any]] = {
    "channel_offer_proxy": {
        "cluster_id": "channel_offer_distributor_marketplace_adapter",
        "adapter_family": "family_scoped_channel_offer_adapter",
        "source_ladder": ["official_store", "amazon", "jd", "digikey", "mouser", "arrow", "cdw"],
        "completion_state": "needs_adapter_batch",
        "priority": "high",
        "pass_condition": "issuer/product/SKU-bound public offer row with price/configuration/availability snapshot; no ASP, inventory, sell-through, or share promotion",
    },
    "hiring_capacity_proxy": {
        "cluster_id": "hiring_capacity_site_specific_public_jobs_adapter",
        "adapter_family": "public_ats_and_official_careers_site_specific_adapter",
        "source_ladder": ["greenhouse", "lever", "ashby", "smartrecruiters", "workday", "jibe", "phenom", "successfactors", "official_careers_html"],
        "completion_state": "needs_site_specific_parser_or_boundary_audit",
        "priority": "medium",
        "pass_condition": "issuer-bound public job row with title/location/category/date or explicit no-public-job-row attempt ledger",
    },
    "developer_ecosystem_proxy": {
        "cluster_id": "developer_ecosystem_official_seed_locator",
        "adapter_family": "official_docs_repo_package_seed_locator",
        "source_ladder": ["company_docs", "official_github_org", "npm_verified_scope", "pypi_verified_project", "huggingface_verified_org", "marketplace_verified_publisher"],
        "completion_state": "needs_verified_seed_locator",
        "priority": "high",
        "pass_condition": "official docs/package/repo seed verifies issuer/product binding before GitHub/npm/PyPI/HuggingFace API rows are accepted",
    },
    "technology_research_proxy": {
        "cluster_id": "technology_research_patents_assignee_resolver",
        "adapter_family": "patentsview_openalex_assignee_topic_resolver",
        "source_ladder": ["patentsview_assignee", "openalex_institution_topic", "official_technical_publications"],
        "completion_state": "needs_adapter_batch",
        "priority": "medium",
        "pass_condition": "issuer/assignee/topic-bound patent or research proxy row; remains L3 technology proxy only",
    },
    "public_order_proxy": {
        "cluster_id": "public_order_local_tender_and_recipient_adapter",
        "adapter_family": "public_procurement_recipient_tender_adapter",
        "source_ladder": ["usaspending", "sam_gov", "eu_ted", "uk_contracts_finder", "canada_buyandsell", "japan_geps", "hong_kong_tender", "taiwan_government_procurement"],
        "completion_state": "needs_jurisdiction_adapter_or_recipient_boundary_audit",
        "priority": "high",
        "pass_condition": "recipient-bound award/tender/order row with issuer/legal-entity binding; no backlog/revenue/order-volume promotion",
    },
    "supply_chain_official_relationship": {
        "cluster_id": "supply_chain_official_relationship_resolver",
        "adapter_family": "official_counterparty_relationship_adapter",
        "source_ladder": ["company_official_news", "customer_supplier_official_news", "public_contract_awards", "regulatory_contract_disclosures"],
        "completion_state": "needs_official_relationship_adapter_or_boundary_audit",
        "priority": "high",
        "pass_condition": "issuer/counterparty/product or contract relationship row from official or regulated source; no volume/share inference",
    },
    "regulated_product_context": {
        "cluster_id": "regulated_product_context_regulatory_api_adapter",
        "adapter_family": "clinical_fda_ema_veterinary_device_regulatory_adapter",
        "source_ladder": ["clinicaltrials", "openfda_drug", "openfda_device", "fda_510k_pma", "ema_medicines", "animal_veterinary_regulatory_sources"],
        "completion_state": "needs_regulatory_route_extension_or_public_boundary_audit",
        "priority": "high",
        "pass_condition": "sponsor/applicant/manufacturer-bound product/trial/device/regulatory row; supports R&D/approval/risk context only",
    },
    "app_rank_store_proxy": {
        "cluster_id": "app_marketplace_seller_alias_adapter",
        "adapter_family": "app_store_google_play_verified_publisher_adapter",
        "source_ladder": ["apple_itunes_search", "apple_lookup", "google_play_listing", "official_app_page"],
        "completion_state": "needs_marketplace_alias_adapter_or_boundary_audit",
        "priority": "medium",
        "pass_condition": "seller/publisher-bound app listing/review/ranking proxy row; no app revenue/download/share promotion",
    },
    "platform_review_proxy": {
        "cluster_id": "platform_review_seller_alias_adapter",
        "adapter_family": "app_store_google_play_review_adapter",
        "source_ladder": ["apple_itunes_search", "apple_lookup", "google_play_listing", "official_app_page"],
        "completion_state": "needs_marketplace_alias_adapter_or_boundary_audit",
        "priority": "medium",
        "pass_condition": "seller/publisher-bound platform review/listing proxy row; no revenue/download/share promotion",
    },
    "auto_product_identity_context": {
        "cluster_id": "auto_product_identity_regulatory_boundary_audit",
        "adapter_family": "nhtsa_vpic_make_model_adapter",
        "source_ladder": ["nhtsa_vpic", "nhtsa_recalls", "company_vehicle_pages"],
        "completion_state": "attempt_backed_public_boundary_or_make_alias_repair",
        "priority": "low",
        "pass_condition": "make/model/recall row bound to issuer or explicit non-applicable vehicle route closeout",
    },
}

PRODUCT_KPI_RULES: dict[str, dict[str, Any]] = {
    "parser_candidate_found_but_not_runtime_promotable": {
        "cluster_id": "product_kpi_source_specific_table_verifier",
        "adapter_family": "product_kpi_table_period_product_binding_verifier",
        "source_ladder": ["sec_xbrl_table", "10k_10q_product_table", "20f_6k_product_table", "ir_deck_table", "annual_report_pdf_table"],
        "completion_state": "needs_parser_verifier_batch",
        "priority": "high",
        "pass_condition": "candidate row must verify value/unit/period/product/citation and reject geography/customer/channel/percentage/change cells",
    },
    "non_us_local_or_ir_parser_required": {
        "cluster_id": "product_kpi_non_us_ir_local_exchange_parser",
        "adapter_family": "non_us_annual_report_ir_table_parser",
        "source_ladder": ["local_exchange_filing", "company_ir_annual_report", "20f_6k", "annual_report_pdf_table", "ir_deck_table"],
        "completion_state": "needs_non_us_disclosure_adapter",
        "priority": "high",
        "pass_condition": "non-US official filing/IR table row verifies value/unit/period/product/citation",
    },
    "product_surface_or_taxonomy_available_no_company_kpi_candidate": {
        "cluster_id": "product_kpi_ir_deck_annual_report_locator",
        "adapter_family": "company_ir_product_kpi_locator",
        "source_ladder": ["company_ir_presentation", "annual_report_pdf_table", "filing_segment_note", "earnings_deck_product_table"],
        "completion_state": "needs_locator_before_final_gap",
        "priority": "medium",
        "pass_condition": "IR/report locator either finds company-disclosed product KPI table or writes attempt-backed company-undisclosed gap",
    },
    "no_product_kpi_candidate_in_current_public_scan": {
        "cluster_id": "product_kpi_company_undisclosed_boundary_audit",
        "adapter_family": "company_ir_and_public_disclosure_exhaustion_audit",
        "source_ladder": ["sec_filings", "company_ir_annual_report", "local_exchange_filing", "earnings_deck", "commercial_tracker_gap"],
        "completion_state": "needs_public_disclosure_exhaustion_audit",
        "priority": "medium",
        "pass_condition": "all applicable company disclosure routes attempted before final company-undisclosed/commercial tracker gap",
    },
    "geographic_or_non_product_only": {
        "cluster_id": "product_kpi_region_dimension_or_rejection_gate",
        "adapter_family": "region_schema_or_non_product_rejection_gate",
        "source_ladder": ["segment_note_region_schema", "product_table_parser"],
        "completion_state": "needs_region_dimension_schema_or_remain_rejected",
        "priority": "low",
        "pass_condition": "only promoted if region dimension is explicitly supported; otherwise remains non-product rejected evidence",
    },
    "verifier_business_segment_only_candidates": {
        "cluster_id": "product_kpi_business_segment_boundary",
        "adapter_family": "business_segment_metric_router",
        "source_ladder": ["segment_note_table", "10k_10q_segment_table", "20f_6k_segment_table"],
        "completion_state": "route_to_business_mix_or_remain_product_kpi_gap",
        "priority": "medium",
        "pass_condition": "business/segment metrics may support fundamental analysis but cannot fill product KPI exact slot without product-family binding",
    },
    "verifier_business_segment_column_group_required": {
        "cluster_id": "product_kpi_column_group_schema_verifier",
        "adapter_family": "segment_table_column_group_parser",
        "source_ladder": ["segment_note_table", "10k_10q_product_table", "ir_deck_table", "annual_report_pdf_table"],
        "completion_state": "needs_column_group_schema",
        "priority": "high",
        "pass_condition": "only revenue/level columns with verified period and product/segment binding can be promoted; margins/costs/operating income remain rejected",
    },
    "verifier_region_or_geography_only_candidates": {
        "cluster_id": "product_kpi_region_dimension_or_rejection_gate",
        "adapter_family": "region_schema_or_product_binding_filter",
        "source_ladder": ["geographic_revenue_table", "product_table_parser"],
        "completion_state": "region_exposure_only_or_needs_product_table",
        "priority": "low",
        "pass_condition": "geographic rows require explicit region dimension; they never fill product KPI exact slots without product binding",
    },
    "verifier_percentage_or_change_only_candidates": {
        "cluster_id": "product_kpi_percentage_change_rejection_gate",
        "adapter_family": "percentage_change_level_value_filter",
        "source_ladder": ["product_table_parser", "local_table_coordinate_verifier"],
        "completion_state": "reject_or_pair_with_currency_level_value",
        "priority": "medium",
        "pass_condition": "percentage/change cells can only support directionality; product KPI exact requires a company-disclosed currency or operating level value",
    },
    "verifier_operating_metric_requires_industry_slot": {
        "cluster_id": "product_kpi_industry_operating_metric_slot_router",
        "adapter_family": "industry_operating_metric_schema_mapper",
        "source_ladder": ["industry_operating_metric_table", "business_metric_table", "company_disclosed_kpi_table"],
        "completion_state": "needs_industry_operating_metric_slot_mapping",
        "priority": "medium",
        "pass_condition": "non-revenue metrics enter only typed industry operating slots with metric/unit/product/period/citation gates",
    },
    "verifier_sentence_relation_insufficient": {
        "cluster_id": "product_kpi_sentence_relation_verifier",
        "adapter_family": "local_sentence_table_neighborhood_verifier",
        "source_ladder": ["filing_sentence_window", "local_table_neighborhood", "ir_deck_sentence_window"],
        "completion_state": "needs_local_relation_verifier",
        "priority": "high",
        "pass_condition": "unstructured numeric mentions require local product-value-period relation verification before any promotion",
    },
    "verifier_period_or_version_conflict": {
        "cluster_id": "product_kpi_period_version_schema_verifier",
        "adapter_family": "period_column_version_reconciler",
        "source_ladder": ["versioned_filing_table", "prior_year_column_group", "restatement_note"],
        "completion_state": "needs_period_version_reconciliation",
        "priority": "high",
        "pass_condition": "current/prior-year or restatement conflicts must be reconciled before exact-slot use",
    },
    "verifier_non_product_or_total_candidates": {
        "cluster_id": "product_kpi_non_product_total_rejection_gate",
        "adapter_family": "non_product_total_filter",
        "source_ladder": ["product_table_parser", "segment_note_table"],
        "completion_state": "reject_or_find_product_family_table",
        "priority": "low",
        "pass_condition": "generic totals, corporate, eliminations, costs, and non-product rows remain rejected unless a separate product-family table is found",
    },
    "verifier_product_table_context_insufficient": {
        "cluster_id": "product_kpi_product_table_context_verifier",
        "adapter_family": "product_table_caption_header_verifier",
        "source_ladder": ["10k_10q_product_table", "20f_6k_product_table", "ir_deck_table", "annual_report_pdf_table"],
        "completion_state": "needs_product_table_context_verification",
        "priority": "high",
        "pass_condition": "product alias must be backed by local table title/header/caption proving product/category/product-line revenue context",
    },
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build company-level source-role and Product-KPI gap dockets.")
    parser.add_argument("--source-closeout", type=Path, default=DEFAULT_SOURCE_CLOSEOUT)
    parser.add_argument("--product-kpi-diagnostic", type=Path, default=DEFAULT_PRODUCT_KPI_DIAGNOSTIC)
    parser.add_argument("--product-kpi-verifier-ticker-summary", type=Path, default=DEFAULT_PRODUCT_KPI_VERIFIER_TICKER_SUMMARY)
    parser.add_argument("--coverage-matrix", type=Path, default=DEFAULT_COVERAGE_MATRIX)
    parser.add_argument("--family-assignments", type=Path, default=DEFAULT_FAMILY_ASSIGNMENTS)
    parser.add_argument("--family-route-plan", type=Path, default=DEFAULT_FAMILY_ROUTE_PLAN)
    parser.add_argument("--output-docket", type=Path, default=DEFAULT_OUTPUT_DOCKET)
    parser.add_argument("--output-clusters", type=Path, default=DEFAULT_OUTPUT_CLUSTERS)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--output-report", type=Path, default=DEFAULT_OUTPUT_REPORT)
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at = _utc_now()
    docket_rows = build_company_gap_docket_rows(
        source_closeout_rows=_load_jsonl(args.source_closeout),
        product_kpi_diagnostic_rows=_load_jsonl(args.product_kpi_diagnostic),
        product_kpi_verifier_ticker_rows=_load_jsonl(args.product_kpi_verifier_ticker_summary),
        coverage_rows=_load_jsonl(args.coverage_matrix),
        family_assignment_rows=_load_jsonl(args.family_assignments),
        family_route_plan_rows=_load_jsonl(args.family_route_plan),
        generated_at=generated_at,
    )
    cluster_rows = build_adapter_cluster_queue(docket_rows=docket_rows, generated_at=generated_at)
    summary = build_summary(
        docket_rows=docket_rows,
        cluster_rows=cluster_rows,
        generated_at=generated_at,
        output_docket=args.output_docket,
        output_clusters=args.output_clusters,
        output_report=args.output_report,
    )
    _write_jsonl(args.output_docket, docket_rows)
    _write_jsonl(args.output_clusters, cluster_rows)
    _write_json(args.output_summary, summary)
    args.output_report.parent.mkdir(parents=True, exist_ok=True)
    args.output_report.write_text(render_report(summary, cluster_rows=cluster_rows), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if args.strict and summary["unclassified_docket_count"]:
        return 1
    return 0


def build_company_gap_docket_rows(
    *,
    source_closeout_rows: Iterable[Mapping[str, Any]],
    product_kpi_diagnostic_rows: Iterable[Mapping[str, Any]],
    coverage_rows: Iterable[Mapping[str, Any]],
    family_assignment_rows: Iterable[Mapping[str, Any]],
    family_route_plan_rows: Iterable[Mapping[str, Any]],
    generated_at: str,
    product_kpi_verifier_ticker_rows: Iterable[Mapping[str, Any]] = (),
) -> list[dict[str, Any]]:
    company_context = _company_context_by_ticker(coverage_rows)
    family_context = _family_context_by_ticker(family_assignment_rows)
    family_routes = _family_routes_by_ticker_route(family_route_plan_rows)
    product_kpi_verifier_context = _company_context_by_ticker(product_kpi_verifier_ticker_rows)
    rows: list[dict[str, Any]] = []
    for closeout in source_closeout_rows:
        ticker = _ticker(closeout)
        requirement_id = str(closeout.get("requirement_id") or "")
        rule = _source_role_rule(requirement_id, closeout)
        rows.append(
            _base_row(
                ticker=ticker,
                company_name=str(closeout.get("company_name") or ""),
                primary_lane_id=str(closeout.get("primary_lane_id") or ""),
                docket_type="source_role",
                requirement_id=requirement_id,
                generated_at=generated_at,
                company_context=company_context.get(ticker, {}),
                family_context=family_context.get(ticker, []),
                rule=rule,
                status=str(closeout.get("closeout_class") or ""),
                reason=str(closeout.get("closeout_reason") or ""),
                closeout_row=closeout,
                related_family_routes=family_routes.get((ticker, requirement_id), []),
                product_kpi_verifier_context={},
            )
        )
    for diagnostic in product_kpi_diagnostic_rows:
        if str(diagnostic.get("product_kpi_status") or "") != "product_kpi_exact_gap":
            continue
        ticker = _ticker(diagnostic)
        rule = _product_kpi_rule(str(diagnostic.get("diagnostic_class") or ""), diagnostic)
        rows.append(
            _base_row(
                ticker=ticker,
                company_name=str(diagnostic.get("company_name") or ""),
                primary_lane_id=str(diagnostic.get("primary_lane_id") or ""),
                docket_type="product_kpi",
                requirement_id="product_kpi_exact_slot",
                generated_at=generated_at,
                company_context=company_context.get(ticker, {}),
                family_context=family_context.get(ticker, []),
                rule=rule,
                status=str(diagnostic.get("product_kpi_status") or ""),
                reason=str(diagnostic.get("diagnostic_reason") or diagnostic.get("gap_reason") or ""),
                closeout_row=diagnostic,
                related_family_routes=[],
                product_kpi_verifier_context=product_kpi_verifier_context.get(ticker, {}),
            )
        )
    return sorted(rows, key=lambda row: (_priority_rank(row["priority"]), row["docket_type"], row["cluster_id"], row["ticker"]))


def build_adapter_cluster_queue(*, docket_rows: Iterable[Mapping[str, Any]], generated_at: str) -> list[dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in docket_rows:
        grouped[str(row.get("cluster_id") or "unclassified")].append(row)
    out: list[dict[str, Any]] = []
    for cluster_id, rows in grouped.items():
        first = rows[0]
        source_ladder = list(first.get("source_ladder") or [])
        out.append(
            {
                "schema_version": CLUSTER_SCHEMA_VERSION,
                "generated_at": generated_at,
                "cluster_id": cluster_id,
                "adapter_family": first.get("adapter_family") or "",
                "priority": first.get("priority") or "medium",
                "completion_state": first.get("completion_state") or "",
                "docket_count": len(rows),
                "company_count": len({str(row.get("ticker") or "") for row in rows}),
                "docket_type_counts": dict(sorted(Counter(str(row.get("docket_type") or "") for row in rows).items())),
                "requirement_counts": dict(sorted(Counter(str(row.get("requirement_id") or "") for row in rows).items())),
                "lane_counts": dict(sorted(Counter(str(row.get("primary_lane_id") or "") for row in rows).items())),
                "family_counts": dict(Counter(family for row in rows for family in row.get("family_ids") or []).most_common(12)),
                "source_ladder": source_ladder,
                "sample_tickers": sorted({str(row.get("ticker") or "") for row in rows})[:20],
                "sample_docket_ids": [str(row.get("docket_id") or "") for row in rows[:10]],
                "pass_condition": first.get("pass_condition") or "",
                "next_batch_action": _cluster_next_batch_action(cluster_id, source_ladder),
            }
        )
    return sorted(out, key=lambda row: (_priority_rank(row["priority"]), -int(row["docket_count"]), row["cluster_id"]))


def build_summary(
    *,
    docket_rows: list[dict[str, Any]],
    cluster_rows: list[dict[str, Any]],
    generated_at: str,
    output_docket: Path,
    output_clusters: Path,
    output_report: Path,
) -> dict[str, Any]:
    unclassified = [row for row in docket_rows if row.get("cluster_id") == "unclassified"]
    source_rows = [row for row in docket_rows if row.get("docket_type") == "source_role"]
    product_rows = [row for row in docket_rows if row.get("docket_type") == "product_kpi"]
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "pass" if docket_rows and not unclassified else "gap",
        "docket_count": len(docket_rows),
        "source_role_gap_docket_count": len(source_rows),
        "product_kpi_gap_docket_count": len(product_rows),
        "unique_gap_company_count": len({row["ticker"] for row in docket_rows}),
        "cluster_count": len(cluster_rows),
        "unclassified_docket_count": len(unclassified),
        "by_docket_type": dict(sorted(Counter(row["docket_type"] for row in docket_rows).items())),
        "by_requirement": dict(sorted(Counter(row["requirement_id"] for row in docket_rows).items())),
        "by_cluster": {
            row["cluster_id"]: {
                "docket_count": row["docket_count"],
                "company_count": row["company_count"],
                "priority": row["priority"],
                "completion_state": row["completion_state"],
            }
            for row in cluster_rows
        },
        "by_completion_state": dict(sorted(Counter(row["completion_state"] for row in docket_rows).items())),
        "by_priority": dict(sorted(Counter(row["priority"] for row in docket_rows).items())),
        "top_lanes": dict(Counter(row["primary_lane_id"] for row in docket_rows).most_common(12)),
        "outputs": {
            "docket": str(output_docket),
            "clusters": str(output_clusters),
            "report": str(output_report),
        },
        "boundary": (
            "The docket operationalizes remaining company gaps. It does not promote evidence. "
            "A gap can become final only after its listed source ladder and pass condition are exhausted in an attempt ledger."
        ),
    }


def _base_row(
    *,
    ticker: str,
    company_name: str,
    primary_lane_id: str,
    docket_type: str,
    requirement_id: str,
    generated_at: str,
    company_context: Mapping[str, Any],
    family_context: list[Mapping[str, Any]],
    rule: Mapping[str, Any],
    status: str,
    reason: str,
    closeout_row: Mapping[str, Any],
    related_family_routes: list[Mapping[str, Any]],
    product_kpi_verifier_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    family_ids = sorted({str(row.get("family_id") or "") for row in family_context if row.get("family_id")})
    family_names = sorted({str(row.get("family_name") or "") for row in family_context if row.get("family_name")})
    source_ladder = list(rule.get("source_ladder") or [])
    docket_id = _stable_id("company_gap_docket", [docket_type, ticker, requirement_id, rule.get("cluster_id"), reason])
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "docket_id": docket_id,
        "docket_type": docket_type,
        "ticker": ticker,
        "company_name": company_name or str(company_context.get("company_name") or ""),
        "primary_lane_id": primary_lane_id or str(company_context.get("primary_lane_id") or ""),
        "requirement_id": requirement_id,
        "status": status,
        "gap_reason": reason,
        "cluster_id": rule.get("cluster_id") or "unclassified",
        "adapter_family": rule.get("adapter_family") or "",
        "completion_state": rule.get("completion_state") or "needs_manual_review",
        "priority": rule.get("priority") or "medium",
        "source_ladder": source_ladder,
        "pass_condition": rule.get("pass_condition") or "",
        "family_ids": family_ids,
        "family_names": family_names,
        "sample_family_routes": [_route_sample(row) for row in related_family_routes[:5]],
        "company_coverage_status": company_context.get("coverage_status") or "",
        "company_exact_gap_requirement_count": company_context.get("exact_gap_requirement_count") or 0,
        "attempt_count": closeout_row.get("attempt_count") or closeout_row.get("strict_candidate_count") or 0,
        "sample_attempts_or_candidates": _sample_attempts_or_candidates(closeout_row),
        "public_data_ceiling": closeout_row.get("public_data_ceiling")
        or closeout_row.get("public_boundary_assessment")
        or "",
        "next_action": closeout_row.get("next_action") or _cluster_next_batch_action(str(rule.get("cluster_id") or ""), source_ladder),
        "final_gap_allowed_only_after": _final_gap_allowed_after(rule, docket_type=docket_type),
        "claim_boundary": closeout_row.get("claim_boundary") or "",
        "source_specific_verifier_summary": _source_specific_verifier_summary(product_kpi_verifier_context or {}),
    }


def _source_role_rule(requirement_id: str, closeout: Mapping[str, Any]) -> dict[str, Any]:
    base = dict(SOURCE_ROLE_RULES.get(requirement_id) or {})
    if not base:
        return {
            "cluster_id": "unclassified",
            "adapter_family": "manual_source_route_review",
            "source_ladder": [],
            "completion_state": "needs_manual_review",
            "priority": "high",
            "pass_condition": "Add an explicit source-role rule before final closeout.",
        }
    ticker = _ticker(closeout)
    if requirement_id == "public_order_proxy" and _is_non_us_ticker(ticker):
        base["cluster_id"] = "public_order_non_us_local_tender_adapter"
        if "local_tender_no_supplier_bound_award_or_no_structured_award_endpoint" in str(closeout.get("closeout_reason") or ""):
            base["completion_state"] = "attempt_backed_public_boundary_after_local_tender_attempt"
        else:
            base["completion_state"] = "needs_local_tender_adapter"
        base["priority"] = "high"
    if requirement_id == "regulated_product_context" and ticker in {"ZTS", "IDXX"}:
        base["cluster_id"] = "regulated_product_animal_health_veterinary_adapter"
        base["completion_state"] = "needs_veterinary_regulatory_route"
        base["priority"] = "high"
    return base


def _product_kpi_rule(diagnostic_class: str, diagnostic: Mapping[str, Any]) -> dict[str, Any]:
    base = dict(PRODUCT_KPI_RULES.get(diagnostic_class) or {})
    if base:
        return base
    if str(diagnostic.get("coverage_bucket") or "") == "surface_or_taxonomy_only_no_kpi_candidate":
        return dict(PRODUCT_KPI_RULES["product_surface_or_taxonomy_available_no_company_kpi_candidate"])
    return {
        "cluster_id": "unclassified",
        "adapter_family": "manual_product_kpi_gap_review",
        "source_ladder": [],
        "completion_state": "needs_manual_review",
        "priority": "high",
        "pass_condition": "Add an explicit Product-KPI diagnostic rule before final closeout.",
    }


def _cluster_next_batch_action(cluster_id: str, source_ladder: list[str]) -> str:
    if not source_ladder:
        return "Review manually and add a typed adapter rule before closing."
    return (
        f"Run `{cluster_id}` batch through source ladder "
        f"{' -> '.join(source_ladder)}; write ready rows or attempt-backed final gap, never unattempted fallback."
    )


def _final_gap_allowed_after(rule: Mapping[str, Any], *, docket_type: str) -> str:
    if docket_type == "product_kpi":
        return "all applicable company disclosure, IR, local exchange, and annual-report table routes have attempt rows or the company explicitly does not disclose the KPI"
    return "all source_ladder routes applicable to the company/product family have attempt rows and failed issuer/product/counterparty binding or source availability gates"


def _company_context_by_ticker(rows: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        ticker = _ticker(row)
        if ticker:
            out[ticker] = dict(row)
    return out


def _family_context_by_ticker(rows: Iterable[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        ticker = _ticker(row)
        if ticker:
            out[ticker].append(dict(row))
    return out


def _family_routes_by_ticker_route(rows: Iterable[Mapping[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    out: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        ticker = _ticker(row)
        route_id = str(row.get("route_id") or "")
        if ticker and route_id:
            out[(ticker, route_id)].append(dict(row))
    return out


def render_report(summary: Mapping[str, Any], *, cluster_rows: Iterable[Mapping[str, Any]]) -> str:
    lines = [
        "# Company Gap Docket",
        "",
        f"- schema_version: `{summary.get('schema_version')}`",
        f"- generated_at: `{summary.get('generated_at')}`",
        f"- status: `{summary.get('status')}`",
        f"- docket_count: `{summary.get('docket_count')}`",
        f"- source_role_gap_docket_count: `{summary.get('source_role_gap_docket_count')}`",
        f"- product_kpi_gap_docket_count: `{summary.get('product_kpi_gap_docket_count')}`",
        f"- unique_gap_company_count: `{summary.get('unique_gap_company_count')}`",
        f"- unclassified_docket_count: `{summary.get('unclassified_docket_count')}`",
        "",
        "## Adapter Cluster Queue",
        "",
        "| cluster | priority | dockets | companies | state | ladder |",
        "| --- | --- | ---: | ---: | --- | --- |",
    ]
    for row in cluster_rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row.get("cluster_id") or ""),
                    str(row.get("priority") or ""),
                    str(row.get("docket_count") or 0),
                    str(row.get("company_count") or 0),
                    str(row.get("completion_state") or ""),
                    " -> ".join(str(item) for item in row.get("source_ladder") or []),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Requirement Counts",
            "",
            "| requirement | dockets |",
            "| --- | ---: |",
        ]
    )
    for req, count in sorted((summary.get("by_requirement") or {}).items()):
        lines.append(f"| `{req}` | {count} |")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            str(summary.get("boundary") or ""),
            "",
        ]
    )
    return "\n".join(lines)


def _sample_attempts_or_candidates(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    samples: list[Any] = []
    for key in ("sample_attempts", "sample_strict_candidates", "sample_runtime_rows", "sample_final_closeouts"):
        values = row.get(key)
        if isinstance(values, list):
            samples.extend(values)
    out: list[dict[str, Any]] = []
    for sample in samples[:5]:
        if isinstance(sample, Mapping):
            out.append({str(k): v for k, v in list(sample.items())[:8]})
    return out


def _route_sample(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "route_plan_id": row.get("route_plan_id") or "",
        "family_id": row.get("family_id") or "",
        "route_id": row.get("route_id") or "",
        "route_status": row.get("route_status") or "",
        "source_ids": list(row.get("source_ids") or [])[:6],
        "sample_urls": list(row.get("sample_urls") or [])[:3],
    }


def _source_specific_verifier_summary(row: Mapping[str, Any]) -> dict[str, Any]:
    if not row:
        return {}
    return {
        "candidate_count": row.get("candidate_count") or 0,
        "verifier_class_counts": dict(row.get("verifier_class_counts") or {}),
        "verifier_decision_counts": dict(row.get("verifier_decision_counts") or {}),
        "promotable_product_metric_count": row.get("promotable_product_metric_count") or 0,
        "business_segment_metric_count": row.get("business_segment_metric_count") or 0,
        "region_only_count": row.get("region_only_count") or 0,
        "percentage_or_change_count": row.get("percentage_or_change_count") or 0,
        "sentence_relation_insufficient_count": row.get("sentence_relation_insufficient_count") or 0,
        "operating_metric_defer_step2_count": row.get("operating_metric_defer_step2_count") or 0,
        "top_verifier_reasons": dict(row.get("top_verifier_reasons") or {}),
    }


def _priority_rank(value: Any) -> int:
    return {"high": 0, "medium": 1, "low": 2}.get(str(value or "").lower(), 3)


def _is_non_us_ticker(ticker: str) -> bool:
    return ticker.upper().endswith(NON_US_TICKER_SUFFIXES)


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
