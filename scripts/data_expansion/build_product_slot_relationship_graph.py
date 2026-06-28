from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.product_family_source_routes import load_jsonl_rows
from sec_agent.product_slot_relationship_graph import (
    build_company_product_slots,
    build_product_relationship_graph,
    write_product_relationship_artifacts,
)


DEFAULT_PUBLIC_CONTEXT_ROW_FILES = [
    Path("Z:/FIN_Insight_Agent/data/manifests/product_evidence_v0_1/company_product_taxonomy_normalized_targeted_repair_strict_sentence_v0_1.jsonl"),
    REPO_ROOT / "data/manifests/official_product_surface_context_rows_v0_1.jsonl",
    REPO_ROOT / "data/manifests/official_product_catalog_context_rows_v0_1.jsonl",
    REPO_ROOT / "data/manifests/public_official_api_context_rows_v0_1.jsonl",
    REPO_ROOT / "data/manifests/developer_ecosystem_context_rows_v0_1.jsonl",
    REPO_ROOT / "data/manifests/app_marketplace_context_rows_v0_1.jsonl",
    REPO_ROOT / "data/manifests/hiring_capacity_context_rows_v0_1.jsonl",
    REPO_ROOT / "data/manifests/public_contract_award_context_rows_v0_1.jsonl",
    REPO_ROOT / "data/manifests/broad_public_contract_award_context_rows_v0_1.jsonl",
    REPO_ROOT / "data/manifests/local_public_tender_context_rows_v0_1.jsonl",
    REPO_ROOT / "data/manifests/channel_offer_context_rows_v0_1.jsonl",
    REPO_ROOT / "data/manifests/family_channel_distributor_context_rows_v0_1.jsonl",
    REPO_ROOT / "data/manifests/targeted_supply_chain_official_relationship_context_rows_v0_1.jsonl",
    REPO_ROOT / "data/manifests/official_customer_deployment_surface_context_rows_v0_1.jsonl",
    REPO_ROOT / "data/manifests/v1_macro_official_exposure_context_rows_v0_1.jsonl",
    REPO_ROOT / "data/manifests/v1_openalex_technology_research_context_rows_v0_1.jsonl",
    REPO_ROOT / "data/manifests/v1_trusted_external_context_rows_v0_1.jsonl",
    REPO_ROOT / "data/manifests/vertical_lane_public_context_rows_v0_1.jsonl",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build company product slots and bounded product relationship graph.")
    parser.add_argument(
        "--family-assignments",
        type=Path,
        default=REPO_ROOT / "data/manifests/company_product_family_assignments_v0_1.jsonl",
    )
    parser.add_argument(
        "--family-route-plan",
        type=Path,
        default=REPO_ROOT / "data/manifests/family_source_route_plan_v0_1.jsonl",
    )
    parser.add_argument(
        "--product-runtime-rows",
        type=Path,
        default=REPO_ROOT / "data/manifests/company_reported_product_operating_metric_runtime_rows_v0_1.jsonl",
    )
    parser.add_argument("--public-context-row-file", action="append", type=Path, default=[])
    parser.add_argument("--no-default-public-context", action="store_true")
    parser.add_argument(
        "--output-slots",
        type=Path,
        default=REPO_ROOT / "data/manifests/company_product_slots_v0_1.jsonl",
    )
    parser.add_argument(
        "--output-nodes",
        type=Path,
        default=REPO_ROOT / "data/manifests/product_relationship_graph_nodes_v0_1.jsonl",
    )
    parser.add_argument(
        "--output-edges",
        type=Path,
        default=REPO_ROOT / "data/manifests/product_relationship_graph_edges_v0_1.jsonl",
    )
    parser.add_argument(
        "--output-summary",
        type=Path,
        default=REPO_ROOT / "data/manifests/product_relationship_graph_summary_v0_1.json",
    )
    parser.add_argument(
        "--output-report",
        type=Path,
        default=REPO_ROOT / "docs/internal/vnext_20260610/vertical_lanes/product_slot_relationship_graph.zh-CN.md",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    family_assignments = load_jsonl_rows(args.family_assignments)
    route_plan = load_jsonl_rows(args.family_route_plan)
    product_runtime_rows = load_jsonl_rows(args.product_runtime_rows)
    context_paths = [] if args.no_default_public_context else list(DEFAULT_PUBLIC_CONTEXT_ROW_FILES)
    context_paths.extend(args.public_context_row_file)
    public_context_rows = []
    for path in context_paths:
        public_context_rows.extend(load_jsonl_rows(path))

    slots = build_company_product_slots(
        family_assignments=family_assignments,
        route_plan_rows=route_plan,
        product_runtime_rows=product_runtime_rows,
        public_context_rows=public_context_rows,
    )
    graph = build_product_relationship_graph(
        product_slots=slots,
        route_plan_rows=route_plan,
        relationship_context_rows=public_context_rows,
    )
    written = write_product_relationship_artifacts(
        product_slots=graph["slots"],
        nodes=graph["nodes"],
        edges=graph["edges"],
        summary=graph["summary"],
        output_slots_path=args.output_slots,
        output_nodes_path=args.output_nodes,
        output_edges_path=args.output_edges,
        output_summary_path=args.output_summary,
        output_report_path=args.output_report,
    )
    result = {"summary": graph["summary"], "written": written}
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if graph["summary"].get("validation", {}).get("status") != "pass" else 0


if __name__ == "__main__":
    raise SystemExit(main())
