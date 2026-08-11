from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.product_family_source_routes import (
    build_company_product_family_assignments,
    build_family_source_fetch_audit,
    build_family_source_route_plan,
    build_product_family_lane_registry,
    load_jsonl_rows,
    write_product_family_route_artifacts,
)


DEFAULT_PRODUCT_NODES = Path(
    "Z:/FIN_Insight_Agent/data/manifests/product_evidence_graph_v0_1/company_product_evidence_nodes_v0_1.jsonl"
)
DEFAULT_MATERIALIZED_PRODUCT_PAGES = Path(
    "Z:/FIN_Insight_Agent_data/processed_private/public_source_extended_materialization/company_product_pages/company_product_pages.materialized.jsonl"
)

DEFAULT_PUBLIC_CONTEXT_ROW_FILES = [
    Path("Z:/FIN_Insight_Agent/data/manifests/product_evidence_v0_1/company_product_taxonomy_normalized_targeted_repair_strict_sentence_v0_1.jsonl"),
    REPO_ROOT / "data/manifests/official_product_surface_context_rows_v0_1.jsonl",
    REPO_ROOT / "data/manifests/company_disclosed_product_profile_context_rows_v0_1.jsonl",
    REPO_ROOT / "data/manifests/official_product_spec_context_rows_v0_1.jsonl",
    REPO_ROOT / "data/manifests/official_business_asset_profile_context_rows_v0_1.jsonl",
    REPO_ROOT / "data/manifests/public_official_api_context_rows_v0_1.jsonl",
    REPO_ROOT / "data/manifests/developer_ecosystem_context_rows_v0_1.jsonl",
    REPO_ROOT / "data/manifests/app_marketplace_context_rows_v0_1.jsonl",
    REPO_ROOT / "data/manifests/hiring_capacity_context_rows_v0_1.jsonl",
    REPO_ROOT / "data/manifests/public_contract_award_context_rows_v0_1.jsonl",
    REPO_ROOT / "data/manifests/targeted_supply_chain_official_relationship_context_rows_v0_1.jsonl",
    REPO_ROOT / "data/manifests/r17_product_family_evidence_runtime_rows_v0_1.jsonl",
    REPO_ROOT / "data/manifests/channel_offer_context_rows_v0_1.jsonl",
    REPO_ROOT / "data/manifests/v1_macro_official_exposure_context_rows_v0_1.jsonl",
    REPO_ROOT / "data/manifests/v1_openalex_technology_research_context_rows_v0_1.jsonl",
    REPO_ROOT / "data/manifests/v1_trusted_external_context_rows_v0_1.jsonl",
    REPO_ROOT / "data/manifests/vertical_lane_public_context_rows_v0_1.jsonl",
]


def _load_many(paths: Iterable[Path]) -> list[dict]:
    rows: list[dict] = []
    for path in paths:
        rows.extend(load_jsonl_rows(path))
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build product-family assignments and family-scoped source route plans for 600+ company coverage."
    )
    parser.add_argument(
        "--company-assignments",
        type=Path,
        default=REPO_ROOT / "data/manifests/vertical_source_lane_company_assignments_v0_1.jsonl",
    )
    parser.add_argument(
        "--product-nodes",
        type=Path,
        default=DEFAULT_PRODUCT_NODES,
    )
    parser.add_argument(
        "--product-runtime-rows",
        type=Path,
        default=REPO_ROOT / "data/manifests/company_reported_product_operating_metric_runtime_rows_v0_1.jsonl",
    )
    parser.add_argument(
        "--materialized-product-pages",
        type=Path,
        default=DEFAULT_MATERIALIZED_PRODUCT_PAGES,
    )
    parser.add_argument(
        "--repair-queue",
        type=Path,
        default=REPO_ROOT / "data/manifests/company_public_source_repair_queue_v0_1.jsonl",
    )
    parser.add_argument(
        "--public-context-row-file",
        action="append",
        type=Path,
        default=[],
        help="Additional context-row JSONL. Defaults are always included unless --no-default-public-context is set.",
    )
    parser.add_argument("--no-default-public-context", action="store_true")
    parser.add_argument(
        "--output-registry",
        type=Path,
        default=REPO_ROOT / "data/manifests/product_family_lane_registry_v0_1.json",
    )
    parser.add_argument(
        "--output-assignments",
        type=Path,
        default=REPO_ROOT / "data/manifests/company_product_family_assignments_v0_1.jsonl",
    )
    parser.add_argument(
        "--output-route-plan",
        type=Path,
        default=REPO_ROOT / "data/manifests/family_source_route_plan_v0_1.jsonl",
    )
    parser.add_argument(
        "--output-fetch-audit",
        type=Path,
        default=REPO_ROOT / "data/manifests/family_source_fetch_audit_v0_1.json",
    )
    parser.add_argument(
        "--output-report",
        type=Path,
        default=REPO_ROOT / "docs/internal/vnext_20260610/vertical_lanes/product_family_source_route_plan.zh-CN.md",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    company_assignments = load_jsonl_rows(args.company_assignments)
    product_nodes = load_jsonl_rows(args.product_nodes)
    product_runtime_rows = load_jsonl_rows(args.product_runtime_rows)
    public_context_paths = [] if args.no_default_public_context else list(DEFAULT_PUBLIC_CONTEXT_ROW_FILES)
    public_context_paths.extend(args.public_context_row_file)
    public_context_rows = _load_many(public_context_paths)
    materialized_product_pages = load_jsonl_rows(args.materialized_product_pages)
    repair_queue_rows = load_jsonl_rows(args.repair_queue)

    registry = build_product_family_lane_registry()
    family_assignments = build_company_product_family_assignments(
        company_assignments=company_assignments,
        product_nodes=product_nodes,
        product_runtime_rows=product_runtime_rows,
        public_context_rows=public_context_rows,
    )
    route_plan = build_family_source_route_plan(
        family_assignments=family_assignments,
        product_runtime_rows=product_runtime_rows,
        public_context_rows=public_context_rows,
        materialized_product_pages=materialized_product_pages,
        repair_queue_rows=repair_queue_rows,
    )
    fetch_audit = build_family_source_fetch_audit(route_plan_rows=route_plan)

    written = write_product_family_route_artifacts(
        registry=registry,
        assignments=family_assignments,
        route_plan=route_plan,
        fetch_audit=fetch_audit,
        output_registry_path=args.output_registry,
        output_assignments_path=args.output_assignments,
        output_route_plan_path=args.output_route_plan,
        output_fetch_audit_path=args.output_fetch_audit,
        output_report_path=args.output_report,
    )
    summary = {
        "registry_status": registry.get("validation", {}).get("status"),
        "fetch_audit_status": fetch_audit.get("status"),
        "company_count": len({row.get("ticker") for row in company_assignments}),
        "family_count": registry.get("family_count"),
        "assignment_count": len(family_assignments),
        "route_plan_count": len(route_plan),
        "route_status": fetch_audit.get("summary", {}).get("by_route_status"),
        "written": written,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if summary["registry_status"] != "pass" or fetch_audit.get("validation", {}).get("status") != "pass" else 0


if __name__ == "__main__":
    raise SystemExit(main())
