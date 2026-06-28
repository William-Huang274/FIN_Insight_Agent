from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sec_agent.company_public_source_coverage_matrix import (
    build_company_public_source_coverage_matrix,
    load_jsonl_rows,
    write_company_public_source_coverage_matrix,
)


DEFAULT_COMPANY_ASSIGNMENTS_PATH = Path("data/manifests/vertical_source_lane_company_assignments_v0_1.jsonl")
DEFAULT_SOURCE_CAPABILITY_ROWS_PATH = Path("data/manifests/source_layer_capability_audit_v0_1.jsonl")
DEFAULT_REPAIR_SEED_ROWS_PATH = Path("Z:/FIN_Insight_Agent/data/manifests/product_evidence_graph_v0_1/company_product_evidence_nodes_v0_1.jsonl")
DEFAULT_FAMILY_SOURCE_ROUTE_PLAN_PATH = Path("data/manifests/family_source_route_plan_v0_1.jsonl")
DEFAULT_OBSERVED_ROW_PATHS = [
    Path("data/manifests/sec_financial_statement_metric_runtime_rows_v0_1.jsonl"),
    Path("data/manifests/non_us_l1_financial_statement_metric_runtime_rows_v0_1.jsonl"),
    Path("data/manifests/company_reported_product_operating_metric_runtime_rows_v0_1.jsonl"),
    Path("data/manifests/non_us_product_kpi_local_disclosure_runtime_rows_v0_1.jsonl"),
    Path("data/manifests/r16_product_kpi_deep_repair_runtime_rows_v0_1.jsonl"),
    Path("data/manifests/sec_product_taxonomy_context_rows_v0_1.jsonl"),
    Path("data/manifests/official_product_surface_context_rows_v0_1.jsonl"),
    Path("data/manifests/official_product_catalog_context_rows_v0_1.jsonl"),
    Path("data/manifests/public_official_api_context_rows_v0_1.jsonl"),
    Path("data/manifests/official_api_exposure_bridge_context_rows_v0_1.jsonl"),
    Path("data/manifests/targeted_regulated_auto_official_api_context_rows_v0_1.jsonl"),
    Path("data/manifests/trusted_external_family_context_rows_v0_1.jsonl"),
    Path("data/manifests/developer_ecosystem_context_rows_v0_1.jsonl"),
    Path("data/manifests/broad_app_store_platform_context_rows_v0_1.jsonl"),
    Path("data/manifests/app_marketplace_context_rows_v0_1.jsonl"),
    Path("data/manifests/hiring_capacity_context_rows_v0_1.jsonl"),
    Path("data/manifests/broad_official_careers_context_rows_v0_1.jsonl"),
    Path("data/manifests/broad_hiring_capacity_context_rows_v0_1.jsonl"),
    Path("data/manifests/public_contract_award_context_rows_v0_1.jsonl"),
    Path("data/manifests/broad_public_contract_award_context_rows_v0_1.jsonl"),
    Path("data/manifests/local_public_tender_context_rows_v0_1.jsonl"),
    Path("data/manifests/targeted_supply_chain_official_relationship_context_rows_v0_1.jsonl"),
    Path("data/manifests/r17_product_family_evidence_runtime_rows_v0_1.jsonl"),
    Path("data/manifests/channel_offer_context_rows_v0_1.jsonl"),
    Path("data/manifests/broad_channel_offer_context_rows_v0_1.jsonl"),
    Path("data/manifests/family_channel_distributor_context_rows_v0_1.jsonl"),
    Path("data/manifests/v1_trusted_external_context_rows_v0_1.jsonl"),
    Path("data/manifests/v1_openalex_technology_research_context_rows_v0_1.jsonl"),
    Path("data/manifests/v1_patentsview_technology_research_context_rows_v0_1.jsonl"),
    Path("data/manifests/targeted_official_technology_document_context_rows_v0_1.jsonl"),
    Path("data/manifests/v1_macro_official_exposure_context_rows_v0_1.jsonl"),
    Path("data/manifests/capital_funding_ownership_context_rows_v0_1.jsonl"),
    Path("data/manifests/sec_capital_market_event_context_rows_v0_1.jsonl"),
    Path("data/manifests/vertical_lane_public_context_rows_v0_1.jsonl"),
]
DEFAULT_OUTPUT_JSON_PATH = Path("data/manifests/company_public_source_coverage_matrix_v0_1.json")
DEFAULT_OUTPUT_JSONL_PATH = Path("data/manifests/company_public_source_coverage_matrix_v0_1.jsonl")
DEFAULT_OUTPUT_REPAIR_QUEUE_PATH = Path("data/manifests/company_public_source_repair_queue_v0_1.jsonl")
DEFAULT_OUTPUT_REPORT_PATH = Path("docs/internal/vnext_20260610/vertical_lanes/company_public_source_coverage_matrix.zh-CN.md")


def main() -> int:
    args = parse_args()
    assignments = load_jsonl_rows(args.company_assignments_path)
    source_capability_rows = load_jsonl_rows(args.source_capability_rows_path)
    repair_seed_rows = load_jsonl_rows(args.repair_seed_rows_path)
    family_source_route_plan_rows = load_jsonl_rows(args.family_source_route_plan_path)
    observed_rows: list[dict[str, Any]] = []
    existing_observed_paths: list[str] = []
    missing_observed_paths: list[str] = []
    for path in args.observed_row_paths:
        if path.exists():
            existing_observed_paths.append(str(path))
            observed_rows.extend(load_jsonl_rows(path))
        else:
            missing_observed_paths.append(str(path))

    input_paths = {
        "company_assignments": str(args.company_assignments_path),
        "source_capability_rows": str(args.source_capability_rows_path),
        "repair_seed_rows": str(args.repair_seed_rows_path),
        "family_source_route_plan": str(args.family_source_route_plan_path),
        "observed_rows": existing_observed_paths,
        "missing_observed_rows": missing_observed_paths,
    }
    payload = build_company_public_source_coverage_matrix(
        company_assignments=assignments,
        observed_rows=observed_rows,
        source_capability_rows=source_capability_rows,
        repair_seed_rows=repair_seed_rows,
        family_source_route_plan_rows=family_source_route_plan_rows,
        input_paths=input_paths,
    )
    outputs = write_company_public_source_coverage_matrix(
        payload,
        output_json_path=args.output_json_path,
        output_jsonl_path=args.output_jsonl_path,
        output_repair_queue_path=args.output_repair_queue_path,
        output_report_path=args.output_report_path,
    )
    summary = {
        "status": payload.get("status"),
        "company_count": payload.get("company_count"),
        "summary": payload.get("summary"),
        "outputs": outputs,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if (payload.get("validation") or {}).get("status") == "pass" else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build issuer-level public source coverage matrix and repair queue.")
    parser.add_argument("--company-assignments-path", type=Path, default=DEFAULT_COMPANY_ASSIGNMENTS_PATH)
    parser.add_argument("--source-capability-rows-path", type=Path, default=DEFAULT_SOURCE_CAPABILITY_ROWS_PATH)
    parser.add_argument("--repair-seed-rows-path", type=Path, default=DEFAULT_REPAIR_SEED_ROWS_PATH)
    parser.add_argument("--family-source-route-plan-path", type=Path, default=DEFAULT_FAMILY_SOURCE_ROUTE_PLAN_PATH)
    parser.add_argument(
        "--observed-row-path",
        dest="observed_row_paths",
        action="append",
        type=Path,
        default=None,
        help="Runtime source context JSONL path. Can be repeated. Defaults to all known generated L1-L3 context manifests.",
    )
    parser.add_argument("--output-json-path", type=Path, default=DEFAULT_OUTPUT_JSON_PATH)
    parser.add_argument("--output-jsonl-path", type=Path, default=DEFAULT_OUTPUT_JSONL_PATH)
    parser.add_argument("--output-repair-queue-path", type=Path, default=DEFAULT_OUTPUT_REPAIR_QUEUE_PATH)
    parser.add_argument("--output-report-path", type=Path, default=DEFAULT_OUTPUT_REPORT_PATH)
    args = parser.parse_args()
    if args.observed_row_paths is None:
        args.observed_row_paths = DEFAULT_OBSERVED_ROW_PATHS
    return args


if __name__ == "__main__":
    raise SystemExit(main())
