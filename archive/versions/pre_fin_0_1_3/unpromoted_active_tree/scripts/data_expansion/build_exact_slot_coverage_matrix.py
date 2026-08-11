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

from sec_agent.exact_slot_contracts import (
    build_exact_slot_contract_registry,
    build_exact_slot_coverage_matrix,
    build_exact_slot_rows,
    load_jsonl_rows,
    write_exact_slot_artifacts,
)


DEFAULT_COMPANY_SOURCE_MATRIX_PATH = Path("data/manifests/company_public_source_coverage_matrix_v0_1.jsonl")
DEFAULT_REPAIR_QUEUE_PATH = Path("data/manifests/company_public_source_repair_queue_v0_1.jsonl")
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
    Path("data/manifests/broad_hiring_capacity_context_rows_v0_1.jsonl"),
    Path("data/manifests/broad_official_careers_context_rows_v0_1.jsonl"),
    Path("data/manifests/public_contract_award_context_rows_v0_1.jsonl"),
    Path("data/manifests/broad_public_contract_award_context_rows_v0_1.jsonl"),
    Path("data/manifests/local_public_tender_context_rows_v0_1.jsonl"),
    Path("data/manifests/targeted_supply_chain_official_relationship_context_rows_v0_1.jsonl"),
    Path("data/manifests/channel_offer_context_rows_v0_1.jsonl"),
    Path("data/manifests/broad_channel_offer_context_rows_v0_1.jsonl"),
    Path("data/manifests/family_channel_distributor_context_rows_v0_1.jsonl"),
    Path("data/manifests/v1_trusted_external_context_rows_v0_1.jsonl"),
    Path("data/manifests/v1_openalex_technology_research_context_rows_v0_1.jsonl"),
    Path("data/manifests/v1_patentsview_technology_research_context_rows_v0_1.jsonl"),
    Path("data/manifests/targeted_official_technology_document_context_rows_v0_1.jsonl"),
    Path("data/manifests/v1_macro_official_exposure_context_rows_v0_1.jsonl"),
    Path("data/manifests/vertical_lane_public_context_rows_v0_1.jsonl"),
]

DEFAULT_OUTPUT_REGISTRY_PATH = Path("data/manifests/exact_slot_contract_registry_v0_1.json")
DEFAULT_OUTPUT_EXACT_ROWS_PATH = Path("data/manifests/exact_slot_rows_v0_1.jsonl")
DEFAULT_OUTPUT_REJECTED_ROWS_PATH = Path("data/manifests/exact_slot_rejected_attempts_v0_1.jsonl")
DEFAULT_OUTPUT_COVERAGE_JSON_PATH = Path("data/manifests/exact_slot_coverage_matrix_v0_1.json")
DEFAULT_OUTPUT_COVERAGE_JSONL_PATH = Path("data/manifests/exact_slot_coverage_matrix_v0_1.jsonl")
DEFAULT_OUTPUT_GAP_LEDGER_PATH = Path("data/manifests/exact_slot_gap_ledger_v0_1.jsonl")
DEFAULT_OUTPUT_REPORT_PATH = Path("docs/internal/vnext_20260610/vertical_lanes/exact_slot_coverage_matrix.zh-CN.md")


def main() -> int:
    args = parse_args()
    matrix_rows = load_jsonl_rows(args.company_source_matrix_path)
    repair_queue_rows = load_jsonl_rows(args.repair_queue_path)
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
        "company_source_matrix": str(args.company_source_matrix_path),
        "repair_queue": str(args.repair_queue_path),
        "observed_rows": existing_observed_paths,
        "missing_observed_rows": missing_observed_paths,
    }
    registry = build_exact_slot_contract_registry()
    exact_slot_payload = build_exact_slot_rows(observed_rows)
    coverage = build_exact_slot_coverage_matrix(
        company_source_matrix_rows=matrix_rows,
        exact_slot_rows=exact_slot_payload["exact_rows"],
        rejected_slot_rows=exact_slot_payload["rejected_rows"],
        repair_queue_rows=repair_queue_rows,
        input_paths=input_paths,
    )
    outputs = write_exact_slot_artifacts(
        registry=registry,
        exact_slot_payload=exact_slot_payload,
        coverage=coverage,
        output_registry_path=args.output_registry_path,
        output_exact_rows_path=args.output_exact_rows_path,
        output_rejected_rows_path=args.output_rejected_rows_path,
        output_coverage_json_path=args.output_coverage_json_path,
        output_coverage_jsonl_path=args.output_coverage_jsonl_path,
        output_gap_ledger_path=args.output_gap_ledger_path,
        output_report_path=args.output_report_path,
    )
    summary = {
        "registry": {
            "contract_count": registry.get("contract_count"),
        },
        "exact_slot_rows": exact_slot_payload.get("summary"),
        "coverage": coverage.get("summary"),
        "status": coverage.get("status"),
        "validation": coverage.get("validation"),
        "outputs": outputs,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if (coverage.get("validation") or {}).get("status") == "pass" else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build exact-slot row ledger and issuer-level exact-slot coverage matrix.")
    parser.add_argument("--company-source-matrix-path", type=Path, default=DEFAULT_COMPANY_SOURCE_MATRIX_PATH)
    parser.add_argument("--repair-queue-path", type=Path, default=DEFAULT_REPAIR_QUEUE_PATH)
    parser.add_argument(
        "--observed-row-path",
        dest="observed_row_paths",
        action="append",
        type=Path,
        default=None,
        help="Runtime/source context JSONL path. Can be repeated. Defaults to all known generated L1-L3 manifests.",
    )
    parser.add_argument("--output-registry-path", type=Path, default=DEFAULT_OUTPUT_REGISTRY_PATH)
    parser.add_argument("--output-exact-rows-path", type=Path, default=DEFAULT_OUTPUT_EXACT_ROWS_PATH)
    parser.add_argument("--output-rejected-rows-path", type=Path, default=DEFAULT_OUTPUT_REJECTED_ROWS_PATH)
    parser.add_argument("--output-coverage-json-path", type=Path, default=DEFAULT_OUTPUT_COVERAGE_JSON_PATH)
    parser.add_argument("--output-coverage-jsonl-path", type=Path, default=DEFAULT_OUTPUT_COVERAGE_JSONL_PATH)
    parser.add_argument("--output-gap-ledger-path", type=Path, default=DEFAULT_OUTPUT_GAP_LEDGER_PATH)
    parser.add_argument("--output-report-path", type=Path, default=DEFAULT_OUTPUT_REPORT_PATH)
    args = parser.parse_args()
    if args.observed_row_paths is None:
        args.observed_row_paths = DEFAULT_OBSERVED_ROW_PATHS
    return args


if __name__ == "__main__":
    raise SystemExit(main())
