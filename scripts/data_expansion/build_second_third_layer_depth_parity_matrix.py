from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.layer_acceptance_gates import (  # noqa: E402
    SECOND_THIRD_LAYER_DEPTH_PARITY_BACKFILL_SCHEMA_VERSION,
    SECOND_THIRD_LAYER_DEPTH_PARITY_COMPANY_SCHEMA_VERSION,
    build_second_third_layer_depth_parity_matrix,
    load_jsonl,
)


MANIFEST_DIR = REPO_ROOT / "data" / "manifests"
DEFAULT_COMPANY_UNIVERSE = MANIFEST_DIR / "company_product_slots_v0_1.jsonl"
DEFAULT_PRODUCT_KPI_CLOSEOUT = MANIFEST_DIR / "product_kpi_exact_slot_closeout_v0_1.jsonl"
DEFAULT_PRODUCT_KPI_ROW_PATHS = [
    MANIFEST_DIR / "company_disclosed_product_business_mix_runtime_rows_v0_1.jsonl",
    MANIFEST_DIR / "company_reported_product_operating_metric_runtime_rows_v0_1.jsonl",
    MANIFEST_DIR / "industry_operating_metric_slot_rows_v0_1.jsonl",
    MANIFEST_DIR / "non_us_product_kpi_local_disclosure_runtime_rows_v0_1.jsonl",
    MANIFEST_DIR / "r16_product_kpi_deep_repair_runtime_rows_v0_1.jsonl",
    MANIFEST_DIR / "r17_known_public_product_kpi_repair_runtime_rows_v0_1.jsonl",
]
DEFAULT_PRODUCT_SPEC_ROW_PATHS = [
    MANIFEST_DIR / "company_disclosed_product_profile_context_rows_v0_1.jsonl",
    MANIFEST_DIR / "official_product_surface_context_rows_v0_1.jsonl",
    MANIFEST_DIR / "official_product_catalog_context_rows_v0_1.jsonl",
    MANIFEST_DIR / "official_product_spec_context_rows_v0_1.jsonl",
    MANIFEST_DIR / "official_business_asset_profile_context_rows_v0_1.jsonl",
    MANIFEST_DIR / "r17_product_family_evidence_runtime_rows_v0_1.jsonl",
    MANIFEST_DIR / "targeted_official_technology_document_context_rows_v0_1.jsonl",
]
DEFAULT_CUSTOMER_DEPLOYMENT_ROW_PATHS = [
    MANIFEST_DIR / "targeted_supply_chain_official_relationship_context_rows_v0_1.jsonl",
    MANIFEST_DIR / "public_contract_award_context_rows_v0_1.jsonl",
    MANIFEST_DIR / "broad_public_contract_award_context_rows_v0_1.jsonl",
    MANIFEST_DIR / "local_public_tender_context_rows_v0_1.jsonl",
    MANIFEST_DIR / "r17_product_family_evidence_runtime_rows_v0_1.jsonl",
    MANIFEST_DIR / "family_channel_distributor_context_rows_v0_1.jsonl",
    MANIFEST_DIR / "channel_offer_context_rows_v0_1.jsonl",
    MANIFEST_DIR / "broad_channel_offer_context_rows_v0_1.jsonl",
    MANIFEST_DIR / "app_marketplace_context_rows_v0_1.jsonl",
    MANIFEST_DIR / "broad_app_store_platform_context_rows_v0_1.jsonl",
    MANIFEST_DIR / "official_customer_deployment_surface_context_rows_v0_1.jsonl",
    MANIFEST_DIR / "official_api_exposure_bridge_context_rows_v0_1.jsonl",
    MANIFEST_DIR / "public_official_api_context_rows_v0_1.jsonl",
    MANIFEST_DIR / "targeted_regulated_auto_official_api_context_rows_v0_1.jsonl",
    MANIFEST_DIR / "sec_financial_statement_metric_runtime_rows_v0_1.jsonl",
    MANIFEST_DIR / "industry_operating_metric_slot_rows_v0_1.jsonl",
    MANIFEST_DIR / "company_reported_product_operating_metric_runtime_rows_v0_1.jsonl",
    MANIFEST_DIR / "official_business_asset_profile_context_rows_v0_1.jsonl",
]
DEFAULT_CAPITAL_MARKET_ROW_PATHS = [
    MANIFEST_DIR / "capital_funding_ownership_context_rows_v0_1.jsonl",
    MANIFEST_DIR / "sec_capital_market_event_context_rows_v0_1.jsonl",
    MANIFEST_DIR / "non_us_l1_financial_statement_metric_runtime_rows_v0_1.jsonl",
]
DEFAULT_MARKET_LIQUIDITY_ROW_PATHS = [
    MANIFEST_DIR / "market_liquidity_driver_context_rows_v0_1.jsonl",
    MANIFEST_DIR / "market_liquidity_context_rows_v0_1.jsonl",
    MANIFEST_DIR / "market_price_volume_context_rows_v0_1.jsonl",
    MANIFEST_DIR / "short_interest_context_rows_v0_1.jsonl",
    MANIFEST_DIR / "options_liquidity_context_rows_v0_1.jsonl",
    MANIFEST_DIR / "etf_factor_flow_context_rows_v0_1.jsonl",
    MANIFEST_DIR / "credit_spread_context_rows_v0_1.jsonl",
]
DEFAULT_OUTPUT_SUMMARY = MANIFEST_DIR / "second_third_layer_depth_parity_summary_v0_1.json"
DEFAULT_OUTPUT_COMPANY_ROWS = MANIFEST_DIR / "second_third_layer_depth_parity_matrix_v0_1.jsonl"
DEFAULT_OUTPUT_BACKFILL_QUEUE = MANIFEST_DIR / "second_third_layer_depth_parity_backfill_queue_v0_1.jsonl"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build five-dimension second/third-layer depth parity matrix and backfill queue."
    )
    parser.add_argument("--company-count", type=int, default=603)
    parser.add_argument("--company-universe", type=Path, default=DEFAULT_COMPANY_UNIVERSE)
    parser.add_argument("--product-kpi-closeout", type=Path, default=DEFAULT_PRODUCT_KPI_CLOSEOUT)
    parser.add_argument("--product-kpi-row-path", dest="product_kpi_row_paths", action="append", type=Path)
    parser.add_argument("--product-spec-row-path", dest="product_spec_row_paths", action="append", type=Path)
    parser.add_argument(
        "--customer-deployment-row-path",
        dest="customer_deployment_row_paths",
        action="append",
        type=Path,
    )
    parser.add_argument("--capital-market-row-path", dest="capital_market_row_paths", action="append", type=Path)
    parser.add_argument("--market-liquidity-row-path", dest="market_liquidity_row_paths", action="append", type=Path)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--output-company-rows", type=Path, default=DEFAULT_OUTPUT_COMPANY_ROWS)
    parser.add_argument("--output-backfill-queue", type=Path, default=DEFAULT_OUTPUT_BACKFILL_QUEUE)
    args = parser.parse_args()
    args.product_kpi_row_paths = args.product_kpi_row_paths or DEFAULT_PRODUCT_KPI_ROW_PATHS
    args.product_spec_row_paths = args.product_spec_row_paths or DEFAULT_PRODUCT_SPEC_ROW_PATHS
    args.customer_deployment_row_paths = args.customer_deployment_row_paths or DEFAULT_CUSTOMER_DEPLOYMENT_ROW_PATHS
    args.capital_market_row_paths = args.capital_market_row_paths or DEFAULT_CAPITAL_MARKET_ROW_PATHS
    args.market_liquidity_row_paths = args.market_liquidity_row_paths or DEFAULT_MARKET_LIQUIDITY_ROW_PATHS
    return args


def main() -> int:
    args = parse_args()
    payload = build_second_third_layer_depth_parity_matrix(
        company_universe_rows=load_jsonl(args.company_universe),
        product_kpi_closeout_rows=load_jsonl(args.product_kpi_closeout),
        product_kpi_rows=_load_rows_with_source_file(args.product_kpi_row_paths),
        product_spec_rows=_load_rows_with_source_file(args.product_spec_row_paths),
        customer_deployment_rows=_load_rows_with_source_file(args.customer_deployment_row_paths),
        capital_market_rows=_load_rows_with_source_file(args.capital_market_row_paths),
        market_liquidity_rows=_load_rows_with_source_file(args.market_liquidity_row_paths),
        company_count=args.company_count,
    )
    company_rows = payload.pop("company_rows")
    backfill_queue = payload.pop("backfill_queue")
    args.output_summary.parent.mkdir(parents=True, exist_ok=True)
    args.output_summary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args.output_company_rows.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in company_rows),
        encoding="utf-8",
    )
    args.output_backfill_queue.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in backfill_queue),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": payload["status"],
                "parity_status": payload["parity_status"],
                "metrics": payload["metrics"],
                "company_row_schema": SECOND_THIRD_LAYER_DEPTH_PARITY_COMPANY_SCHEMA_VERSION,
                "backfill_schema": SECOND_THIRD_LAYER_DEPTH_PARITY_BACKFILL_SCHEMA_VERSION,
                "outputs": {
                    "summary": str(args.output_summary),
                    "company_rows": str(args.output_company_rows),
                    "backfill_queue": str(args.output_backfill_queue),
                },
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if payload.get("status") == "pass" else 1


def _load_rows_with_source_file(paths: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        if not path.exists():
            continue
        for row in load_jsonl(path):
            clean = dict(row)
            clean["_source_file"] = path.name
            rows.append(clean)
    return rows


if __name__ == "__main__":
    raise SystemExit(main())
