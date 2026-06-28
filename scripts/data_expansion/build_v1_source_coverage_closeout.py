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

from sec_agent.vertical_source_lane_closeout import (  # noqa: E402
    build_v1_source_coverage_closeout,
    load_jsonl_rows,
    write_v1_source_coverage_closeout,
)


DEFAULT_COVERAGE_PATH = Path("data/manifests/v1_semiconductors_ai_infrastructure_lane_coverage_v0_1.json")
DEFAULT_SOURCE_CAPABILITY_PATH = Path("data/manifests/source_layer_capability_audit_v0_1.jsonl")
DEFAULT_OBSERVED_PATHS = (
    Path("data/manifests/company_reported_product_operating_metric_runtime_rows_v0_1.jsonl"),
    Path("data/manifests/official_product_surface_context_rows_v0_1.jsonl"),
    Path("data/manifests/public_official_api_context_rows_v0_1.jsonl"),
    Path("data/manifests/developer_ecosystem_context_rows_v0_1.jsonl"),
    Path("data/manifests/app_marketplace_context_rows_v0_1.jsonl"),
    Path("data/manifests/hiring_capacity_context_rows_v0_1.jsonl"),
    Path("data/manifests/public_contract_award_context_rows_v0_1.jsonl"),
    Path("data/manifests/channel_offer_context_rows_v0_1.jsonl"),
    Path("data/manifests/v1_trusted_external_context_rows_v0_1.jsonl"),
    Path("data/manifests/v1_openalex_technology_research_context_rows_v0_1.jsonl"),
    Path("data/manifests/v1_macro_official_exposure_context_rows_v0_1.jsonl"),
)
DEFAULT_OUTPUT_PATH = Path("data/manifests/v1_semiconductors_ai_infrastructure_source_closeout_v0_1.json")
DEFAULT_REPORT_PATH = Path("docs/internal/vnext_20260610/vertical_lanes/v1_source_coverage_closeout.zh-CN.md")


def main() -> int:
    args = parse_args()
    v1_coverage: dict[str, Any] = json.loads(args.coverage_path.read_text(encoding="utf-8"))
    source_rows = load_jsonl_rows(args.source_capability_path)
    observed_rows: list[dict[str, Any]] = []
    for path in args.observed_paths:
        observed_rows.extend(load_jsonl_rows(path))
    payload = build_v1_source_coverage_closeout(
        v1_coverage=v1_coverage,
        source_layer_capability_rows=source_rows,
        observed_rows=observed_rows,
    )
    outputs = write_v1_source_coverage_closeout(
        payload,
        output_path=args.output_path,
        report_path=args.report_path,
    )
    summary = {
        "status": payload["status"],
        "lane_id": payload["lane_id"],
        "requirement_count": payload["summary"]["requirement_count"],
        "pass_requirement_count": payload["summary"]["pass_requirement_count"],
        "source_gap_requirement_count": payload["summary"]["source_gap_requirement_count"],
        "commercial_gap_count": payload["summary"]["commercial_gap_count"],
        "observed_runtime_row_count": payload["summary"]["observed_runtime_row_count"],
        "outputs": outputs,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["validation"]["status"] == "pass" else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build V1 source coverage closeout from materialized runtime rows.")
    parser.add_argument("--coverage-path", type=Path, default=DEFAULT_COVERAGE_PATH)
    parser.add_argument("--source-capability-path", type=Path, default=DEFAULT_SOURCE_CAPABILITY_PATH)
    parser.add_argument("--observed-path", dest="observed_paths", action="append", type=Path)
    parser.add_argument("--output-path", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--report-path", type=Path, default=DEFAULT_REPORT_PATH)
    args = parser.parse_args()
    if not args.observed_paths:
        args.observed_paths = list(DEFAULT_OBSERVED_PATHS)
    return args


if __name__ == "__main__":
    raise SystemExit(main())
