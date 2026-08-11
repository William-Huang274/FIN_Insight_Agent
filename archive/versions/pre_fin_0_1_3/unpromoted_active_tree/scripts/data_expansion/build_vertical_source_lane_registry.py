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

from sec_agent.vertical_source_lane_registry import (
    build_vertical_source_lane_registry,
    load_csv_rows,
    load_jsonl_rows,
    write_vertical_source_lane_registry,
)


DEFAULT_UNIVERSE_PATH = Path("data/manifests/tier1_tier2_market_universe_v0_1.csv")
DEFAULT_PRODUCT_NODES_PATH = Path("Z:/FIN_Insight_Agent/data/manifests/product_evidence_graph_v0_1/company_product_evidence_nodes_v0_1.jsonl")
DEFAULT_PRODUCT_GAPS_PATH = Path("Z:/FIN_Insight_Agent/data/manifests/product_evidence_graph_v0_1/company_product_evidence_gaps_v0_1.jsonl")
DEFAULT_PRODUCT_METRIC_ROWS_PATH = Path("data/manifests/company_reported_product_operating_metric_runtime_rows_v0_1.jsonl")
DEFAULT_OFFICIAL_PRODUCT_ROWS_PATH = Path("data/manifests/official_product_surface_context_rows_v0_1.jsonl")
DEFAULT_SOURCE_CAPABILITY_ROWS_PATH = Path("data/manifests/source_layer_capability_audit_v0_1.jsonl")
DEFAULT_OUTPUT_JSON_PATH = Path("data/manifests/vertical_source_lane_registry_v0_1.json")
DEFAULT_OUTPUT_JSONL_PATH = Path("data/manifests/vertical_source_lane_company_assignments_v0_1.jsonl")
DEFAULT_OUTPUT_REPORT_PATH = Path("docs/internal/vnext_20260610/vertical_source_lane_registry.zh-CN.md")


def main() -> int:
    args = parse_args()
    input_paths = {
        "universe": str(args.universe_path),
        "product_nodes": str(args.product_nodes_path),
        "product_gaps": str(args.product_gaps_path),
        "product_metric_rows": str(args.product_metric_rows_path),
        "official_product_rows": str(args.official_product_rows_path),
        "source_capability_rows": str(args.source_capability_rows_path),
    }
    universe_rows = load_csv_rows(args.universe_path)
    product_nodes = _load_optional_jsonl(args.product_nodes_path)
    product_gaps = _load_optional_jsonl(args.product_gaps_path)
    product_metric_rows = _load_optional_jsonl(args.product_metric_rows_path)
    official_product_rows = _load_optional_jsonl(args.official_product_rows_path)
    source_capability_rows = _load_optional_jsonl(args.source_capability_rows_path)

    payload = build_vertical_source_lane_registry(
        universe_rows=universe_rows,
        product_nodes=product_nodes,
        product_gaps=product_gaps,
        product_metric_rows=product_metric_rows,
        official_product_rows=official_product_rows,
        source_capability_rows=source_capability_rows,
        input_paths=input_paths,
    )
    outputs = write_vertical_source_lane_registry(
        payload,
        output_json_path=args.output_json_path,
        output_jsonl_path=args.output_jsonl_path,
        output_report_path=args.output_report_path,
    )
    summary = {
        "status": (payload.get("validation") or {}).get("status"),
        "company_count": payload.get("company_count"),
        "lane_count": payload.get("lane_count"),
        "by_primary_lane": (payload.get("summary") or {}).get("by_primary_lane"),
        "outputs": outputs,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["status"] == "pass" else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build 600+ company vertical source lane registry.")
    parser.add_argument("--universe-path", type=Path, default=DEFAULT_UNIVERSE_PATH)
    parser.add_argument("--product-nodes-path", type=Path, default=DEFAULT_PRODUCT_NODES_PATH)
    parser.add_argument("--product-gaps-path", type=Path, default=DEFAULT_PRODUCT_GAPS_PATH)
    parser.add_argument("--product-metric-rows-path", type=Path, default=DEFAULT_PRODUCT_METRIC_ROWS_PATH)
    parser.add_argument("--official-product-rows-path", type=Path, default=DEFAULT_OFFICIAL_PRODUCT_ROWS_PATH)
    parser.add_argument("--source-capability-rows-path", type=Path, default=DEFAULT_SOURCE_CAPABILITY_ROWS_PATH)
    parser.add_argument("--output-json-path", type=Path, default=DEFAULT_OUTPUT_JSON_PATH)
    parser.add_argument("--output-jsonl-path", type=Path, default=DEFAULT_OUTPUT_JSONL_PATH)
    parser.add_argument("--output-report-path", type=Path, default=DEFAULT_OUTPUT_REPORT_PATH)
    return parser.parse_args()


def _load_optional_jsonl(path: Path) -> list[dict[str, Any]]:
    return load_jsonl_rows(path) if path.exists() else []


if __name__ == "__main__":
    raise SystemExit(main())
