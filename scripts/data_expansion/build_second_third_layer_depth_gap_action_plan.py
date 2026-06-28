from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_DIR = REPO_ROOT / "data" / "manifests"

SCHEMA_VERSION = "finsight_second_third_layer_depth_gap_action_plan_v0_1"
SUMMARY_SCHEMA_VERSION = "finsight_second_third_layer_depth_gap_action_plan_summary_v0_1"

DEFAULT_MATRIX = MANIFEST_DIR / "second_third_layer_depth_parity_matrix_v0_1.jsonl"
DEFAULT_LANE_ASSIGNMENTS = MANIFEST_DIR / "vertical_source_lane_company_assignments_v0_1.jsonl"
DEFAULT_FAMILY_ASSIGNMENTS = MANIFEST_DIR / "company_product_family_assignments_v0_1.jsonl"
DEFAULT_PRODUCT_KPI_VERIFIER_ROWS = MANIFEST_DIR / "product_kpi_source_specific_verifier_v0_1.jsonl"
DEFAULT_OUTPUT_ROWS = MANIFEST_DIR / "second_third_layer_depth_parity_gap_action_plan_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY = MANIFEST_DIR / "second_third_layer_depth_parity_gap_action_plan_summary_v0_1.json"


LANE_ROUTE_LIBRARY = {
    "V1": {
        "product_spec_depth": [
            "official_product_specs_or_datasheets",
            "architecture_whitepaper_or_technology_brief",
            "oem_config_or_qualified_systems_page",
        ],
        "customer_deployment_depth": [
            "supplier_customer_official_news",
            "hyperscaler_or_oem_deployment_page",
            "public_contract_award_or_tender",
        ],
    },
    "V2": {
        "product_spec_depth": [
            "official_product_specs_or_model_compare",
            "retailer_sku_page_for_offer_context",
            "certification_or_regulatory_product_page",
        ],
        "customer_deployment_depth": [
            "official_customer_or_channel_partner_news",
            "retailer_or_official_store_offer_context",
            "public_contract_award_or_tender",
        ],
    },
    "V3": {
        "product_spec_depth": [
            "official_docs_api_reference_or_pricing_page",
            "developer_docs_package_or_marketplace_listing",
            "status_or_release_notes_page",
        ],
        "customer_deployment_depth": [
            "official_customer_case_study",
            "public_sector_contract_award",
            "marketplace_customer_deployment_context",
        ],
    },
    "V4": {
        "product_spec_depth": [
            "regulatory_label_or_device_product_page",
            "clinical_trials_or_openfda_product_context",
            "official_product_catalog_or_prescribing_info",
        ],
        "customer_deployment_depth": [
            "clinical_trial_site_or_sponsor_context",
            "hospital_or_provider_official_deployment_news",
            "cms_or_procurement_context_where_applicable",
        ],
    },
    "V5": {
        "product_spec_depth": [
            "official_model_specs_or_trim_page",
            "nhtsa_vpic_or_recall_model_context",
            "charging_battery_or_autonomy_technical_page",
        ],
        "customer_deployment_depth": [
            "fleet_customer_or_delivery_news",
            "public_tender_or_registration_context",
            "official_partnership_or_charging_network_deployment",
        ],
    },
    "V6": {
        "product_spec_depth": [
            "business_operating_profile_metric_slot",
            "regulatory_capital_or_deposit_product_context",
            "fund_or_platform_official_document",
        ],
        "customer_deployment_depth": [
            "public_sector_contract_or_mandate_context",
            "client_asset_or_platform_deployment_if_disclosed",
            "regulatory_relationship_context",
        ],
    },
    "V7": {
        "product_spec_depth": [
            "asset_capacity_or_project_spec_page",
            "equipment_datasheet_or_project_technical_page",
            "eia_ferc_or_local_regulatory_asset_context",
        ],
        "customer_deployment_depth": [
            "offtake_or_supply_agreement_official_news",
            "public_tender_contract_award",
            "customer_project_or_interconnection_context",
        ],
    },
    "V8": {
        "product_spec_depth": [
            "official_menu_product_catalog_or_property_inventory",
            "retailer_sku_or_channel_offer_context",
            "app_store_or_marketplace_listing_context",
        ],
        "customer_deployment_depth": [
            "franchise_or_store_opening_official_news",
            "public_contract_award_or_supplier_news",
            "channel_partner_or_distribution_context",
        ],
    },
}

DIMENSION_DEFAULT_ACTIONS = {
    "product_kpi_depth": {
        "filings_taxonomy_available_but_value_unit_period_product_kpi_absent": [
            "rerun_product_kpi_value_unit_period_parser_on_sec_or_local_filing_tables",
            "search_ir_deck_or_annual_report_tables_for_product_or_business_kpi",
        ],
        "official_product_surface_available_but_company_disclosed_product_kpi_absent": [
            "search_company_ir_reports_for_product_or_business_metric",
            "classify_as_public_boundary_if_no_company_disclosed_value_unit_period_exists",
        ],
        "product_kpi_slot_without_value_unit_period_runtime_row": [
            "repair_manifest_join_or_parser_output_for_exact_kpi_row",
        ],
    },
    "product_spec_depth": {
        "product_spec_parser_depth_gap": [
            "run_family_specific_spec_parser_on_existing_official_product_surface_or_catalog",
            "locate_datasheet_technical_brief_or_model_compare_page",
        ],
        "product_spec_source_or_parser_gap": [
            "locate_official_spec_or_business_profile_source",
            "materialize_source_then_run_source_specific_spec_or_profile_parser",
        ],
    },
    "customer_deployment_depth": {
        "customer_deployment_public_source_gap": [
            "search_official_customer_supplier_news_case_study_or_public_award",
            "materialize_event_with_issuer_counterparty_product_date_and_boundary",
        ],
    },
    "capital_market_detail_depth": {
        "capital_market_event_parser_or_coverage_gap": [
            "run_sec_or_local_exchange_offering_ownership_insider_proxy_event_parser",
            "classify_as_public_event_absent_if_no_relevant_event_exists",
        ],
        "capital_market_detail_source_gap": [
            "materialize_primary_disclosure_capital_debt_working_capital_rows",
            "materialize_capital_market_event_or_ownership_rows",
        ],
        "capital_primary_disclosure_parser_gap": [
            "run_debt_credit_facility_working_capital_primary_disclosure_parser",
        ],
    },
}

PRODUCT_KPI_HARD_BOUNDARY_REASON_RE = re.compile(
    r"geographic_or_region_only_row|generic_total_or_non_product_row_label|"
    r"non_positive_or_adjustment_value|not_currency_revenue_or_raw_percent|"
    r"mixed_percent_table_or_percent_like_cell|change_or_growth_row_or_column",
    re.IGNORECASE,
)
PRODUCT_KPI_FORBIDDEN_CONTEXT_RE = re.compile(
    r"geographic|region only|north america|latin america|emea|apac|asia pacific|"
    r"\bexpenses?\b|operating expenses|allocated overhead|inventory write-?off|"
    r"cash flows? from (?:investing|financing) activities|sales of (?:fixed maturity|available-for-sale|held-to-maturity) securities|"
    r"proceeds from sales of securities|principal payments received|"
    r"provision for income taxes|income taxes?|effective tax rate|tax rate|non-gaap financial measures?|"
    r"constant currency|foreign currency|fx impact|currency exchange|currency translation|"
    r"acquisitions?|divestitures?|without acquisitions|organic basis|"
    r"production payment obligation|"
    r"sales (?:increased|decreased)|(?:increase|decrease) in sales|amounts attributable to",
    re.IGNORECASE,
)
PRODUCT_KPI_GENERIC_TOTAL_OR_CONTRACT_REVENUE_RE = re.compile(
    r"^(?:total\b.*|revenues?|net sales|sales|total revenue|total revenues|"
    r"total revenue from contracts with customers|total noninterest income|"
    r"total reportable segment revenue|operating income|gross profit|other)$",
    re.IGNORECASE,
)
PRODUCT_KPI_REGION_CROSSTAB_RE = re.compile(
    r"\bu\.s\.\b|united states|international|emea|greater china|apec|europe|asia|americas?|region",
    re.IGNORECASE,
)
PRODUCT_KPI_REGION_LABEL_RE = re.compile(
    r"^(?:north america|latin america|emea|apac|asia(?:-pacific)?|europe|africa|"
    r"americas?|international|domestic|united states|u\.s\.|us|canada|mexico|"
    r"china|japan|korea|india|brazil|germany|u\.k\.|uk|other countries|rest of world)"
    r"(?:\s*\([^)]*\))?$",
    re.IGNORECASE,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build per-company action plan for second/third-layer depth gaps.")
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--lane-assignments", type=Path, default=DEFAULT_LANE_ASSIGNMENTS)
    parser.add_argument("--family-assignments", type=Path, default=DEFAULT_FAMILY_ASSIGNMENTS)
    parser.add_argument("--product-kpi-verifier-rows", type=Path, default=DEFAULT_PRODUCT_KPI_VERIFIER_ROWS)
    parser.add_argument("--output-rows", type=Path, default=DEFAULT_OUTPUT_ROWS)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = build_action_plan(
        matrix_rows=_load_jsonl(args.matrix),
        lane_rows=_load_jsonl(args.lane_assignments),
        family_rows=_load_jsonl(args.family_assignments),
        product_kpi_verifier_rows=_load_jsonl(args.product_kpi_verifier_rows),
    )
    summary = build_summary(rows)
    _write_jsonl(args.output_rows, rows)
    _write_json(args.output_summary, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def build_action_plan(
    *,
    matrix_rows: Iterable[Mapping[str, Any]],
    lane_rows: Iterable[Mapping[str, Any]],
    family_rows: Iterable[Mapping[str, Any]],
    product_kpi_verifier_rows: Iterable[Mapping[str, Any]] = (),
) -> list[dict[str, Any]]:
    lane_by_ticker = {str(row.get("ticker") or "").upper(): dict(row) for row in lane_rows}
    families_by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in family_rows:
        ticker = str(row.get("ticker") or "").upper()
        if ticker:
            families_by_ticker[ticker].append(dict(row))
    verifier_by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in product_kpi_verifier_rows:
        ticker = str(row.get("ticker") or "").upper()
        if ticker:
            verifier_by_ticker[ticker].append(dict(row))

    action_rows: list[dict[str, Any]] = []
    for row in matrix_rows:
        ticker = str(row.get("ticker") or "").upper()
        if not ticker:
            continue
        lane = lane_by_ticker.get(ticker, {})
        primary_lane_id = str(lane.get("primary_lane_id") or "unknown")
        dimensions = row.get("dimensions") or {}
        for dimension, payload in dimensions.items():
            if not isinstance(payload, Mapping) or payload.get("target_depth_met") is True:
                continue
            gap_class = str(payload.get("gap_class") or "unclassified_gap")
            verifier_rows = verifier_by_ticker.get(ticker, []) if dimension == "product_kpi_depth" else []
            action_rows.append(
                {
                    "schema_version": SCHEMA_VERSION,
                    "ticker": ticker,
                    "company_name": row.get("company_name") or lane.get("company_name") or "",
                    "primary_lane_id": primary_lane_id,
                    "primary_lane_name": lane.get("primary_lane_name") or "",
                    "dimension": dimension,
                    "status": payload.get("status") or "",
                    "gap_class": gap_class,
                    "reason": payload.get("reason") or "",
                    "next_action_from_depth_gate": payload.get("next_action") or "",
                    "recommended_source_routes": _recommended_routes(primary_lane_id, dimension, gap_class),
                    "family_scope": _family_scope(families_by_ticker.get(ticker, [])),
                    "source_gap_type": _source_gap_type(dimension, gap_class, verifier_rows=verifier_rows),
                    "product_kpi_verifier_candidate_count": len(verifier_rows) if dimension == "product_kpi_depth" else 0,
                    "product_kpi_verifier_top_reasons": _verifier_top_reasons(verifier_rows) if dimension == "product_kpi_depth" else {},
                    "attempt_policy": _attempt_policy(dimension, gap_class),
                    "claim_boundary": _claim_boundary(dimension),
                }
            )
    return sorted(action_rows, key=lambda item: (item["dimension"], item["gap_class"], item["primary_lane_id"], item["ticker"]))


def build_summary(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    dimension_counts = Counter(str(row.get("dimension") or "") for row in rows)
    gap_counts = Counter(f"{row.get('dimension')}::{row.get('gap_class')}" for row in rows)
    lane_counts = Counter(str(row.get("primary_lane_id") or "") for row in rows)
    source_gap_counts = Counter(str(row.get("source_gap_type") or "") for row in rows)
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "status": "pass",
        "action_row_count": len(rows),
        "affected_ticker_count": len({str(row.get("ticker") or "") for row in rows}),
        "dimension_counts": dict(sorted(dimension_counts.items())),
        "gap_counts": dict(sorted(gap_counts.items())),
        "lane_counts": dict(sorted(lane_counts.items())),
        "source_gap_type_counts": dict(sorted(source_gap_counts.items())),
        "outputs": {"rows": str(DEFAULT_OUTPUT_ROWS)},
    }


def _recommended_routes(primary_lane_id: str, dimension: str, gap_class: str) -> list[str]:
    lane_routes = LANE_ROUTE_LIBRARY.get(primary_lane_id, {}).get(dimension, [])
    default_routes = DIMENSION_DEFAULT_ACTIONS.get(dimension, {}).get(gap_class, [])
    return list(dict.fromkeys([*lane_routes, *default_routes]))


def _family_scope(rows: list[Mapping[str, Any]], *, limit: int = 8) -> list[dict[str, Any]]:
    scoped = []
    for row in rows[:limit]:
        scoped.append(
            {
                "family_id": row.get("family_id") or "",
                "family_name": row.get("family_name") or "",
                "query_terms": row.get("query_terms") or [],
                "route_ids": row.get("route_ids") or [],
            }
        )
    return scoped


def _source_gap_type(
    dimension: str,
    gap_class: str,
    *,
    verifier_rows: list[Mapping[str, Any]] | None = None,
) -> str:
    if dimension == "product_kpi_depth":
        if "runtime_row" in gap_class:
            return "parser_or_manifest_join_gap"
        if "value_unit_period" in gap_class:
            return _product_kpi_value_gap_source_type(verifier_rows or [])
        if "official_product_surface" in gap_class:
            return "classified_public_boundary_or_deep_adapter_gap"
        return "classified_product_kpi_boundary_or_deep_adapter_gap"
    if dimension == "capital_market_detail_depth" and "event" in gap_class:
        return "event_parser_or_public_event_absence_gap"
    if "source" in gap_class and "parser" not in gap_class:
        return "source_locator_or_materialization_gap"
    if "parser" in gap_class or "value_unit_period" in gap_class or "runtime_row" in gap_class:
        return "parser_or_join_gap"
    if dimension == "customer_deployment_depth":
        return "source_locator_or_event_binding_gap"
    return "classified_public_boundary_or_deep_adapter_gap"


def _product_kpi_value_gap_source_type(verifier_rows: list[Mapping[str, Any]]) -> str:
    if not verifier_rows:
        return "company_disclosure_value_candidate_absent_or_locator_gap"
    if all(_product_kpi_verifier_row_is_non_promotable(row) for row in verifier_rows):
        return "non_promotable_public_disclosure_boundary"
    return "source_specific_table_relation_parser_gap"


def _product_kpi_verifier_row_is_non_promotable(row: Mapping[str, Any]) -> bool:
    reason = str(row.get("verifier_reason") or "")
    row_label = str(row.get("row_label") or "").strip()
    product = str(row.get("product_or_segment") or "").strip()
    column = str(row.get("column_label") or "").strip()
    metric_name = str(row.get("metric_name") or "").strip()
    text = " ".join(
        [
            reason,
            row_label,
            product,
            column,
            metric_name,
            str(row.get("citation_sample") or ""),
        ]
    )
    direct = " ".join([row_label, product, column, metric_name])
    if re.search(r"\bsegment orders?\b", direct, re.IGNORECASE):
        return False
    if PRODUCT_KPI_REGION_LABEL_RE.match(row_label) or PRODUCT_KPI_REGION_LABEL_RE.match(product):
        return True
    if PRODUCT_KPI_FORBIDDEN_CONTEXT_RE.search(text):
        return True
    if PRODUCT_KPI_HARD_BOUNDARY_REASON_RE.search(reason):
        return True
    if PRODUCT_KPI_GENERIC_TOTAL_OR_CONTRACT_REVENUE_RE.match(row_label):
        return True
    if PRODUCT_KPI_GENERIC_TOTAL_OR_CONTRACT_REVENUE_RE.match(product):
        return True
    if (
        PRODUCT_KPI_REGION_CROSSTAB_RE.search(text)
        and re.search(r"total reportable segment revenue|net sales by geography|revenue by geography", text, re.IGNORECASE)
    ):
        return True
    return False


def _verifier_top_reasons(rows: list[Mapping[str, Any]], *, limit: int = 5) -> dict[str, int]:
    return dict(Counter(str(row.get("verifier_reason") or "") for row in rows).most_common(limit))


def _attempt_policy(dimension: str, gap_class: str) -> str:
    if dimension == "product_spec_depth":
        return "attempt official spec/datasheet/business-profile locator before exposing gap; do not promote generic product pages."
    if dimension == "customer_deployment_depth":
        return "attempt official customer/supplier/public-award routes before exposing gap; do not infer revenue/backlog."
    if dimension == "capital_market_detail_depth":
        return "attempt primary disclosure plus event/ownership parser; classify no-event cases separately."
    if dimension == "product_kpi_depth":
        return "attempt company-disclosed exact KPI/business metric parser; expose commercial/public boundary if undisclosed."
    return "attempt source-specific parser before closeout."


def _claim_boundary(dimension: str) -> str:
    if dimension == "product_spec_depth":
        return "May support product capability/spec/comparison or business profile context; no sales, ASP, share, backlog, or shipment proof."
    if dimension == "customer_deployment_depth":
        return "May support bounded customer/deployment/procurement signal; no company-wide order value, revenue, backlog, or demand proof."
    if dimension == "capital_market_detail_depth":
        return "May support capital structure, ownership, financing, or market-event context only at cited row/event scope."
    if dimension == "product_kpi_depth":
        return "May support company-disclosed product/business KPI only when value/unit/period/citation gates pass."
    return "Bounded context only."


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
