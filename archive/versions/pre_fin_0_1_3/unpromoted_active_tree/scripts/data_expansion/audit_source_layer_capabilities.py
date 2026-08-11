from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sec_agent.source_layer_capability_audit import (
    build_source_layer_capability_audit,
    write_source_layer_capability_audit,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build source-layer capability audit for analyst-first research routing.")
    parser.add_argument("--coverage-config", default="configs/data_sources/public_source_coverage_v0_1.yaml")
    parser.add_argument("--availability-audit", default="data/manifests/public_source_full_availability_audit_v0_1.jsonl")
    parser.add_argument("--materialization-matrix", default="data/manifests/public_source_strength_materialization_matrix_v0_1.jsonl")
    parser.add_argument("--inventory-summary", default="data/manifests/public_source_inventory_adapter_summary_v0_1.json")
    parser.add_argument("--output-rows", default="data/manifests/source_layer_capability_audit_v0_1.jsonl")
    parser.add_argument("--output-summary", default="data/manifests/source_layer_capability_audit_summary_v0_1.json")
    parser.add_argument("--output-report", default="docs/internal/vnext_20260610/source_layer_capability_audit.zh-CN.md")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero if validation fails.")
    args = parser.parse_args()

    payload = build_source_layer_capability_audit(
        coverage_config_path=args.coverage_config,
        availability_audit_path=args.availability_audit,
        materialization_matrix_path=args.materialization_matrix,
        inventory_summary_path=args.inventory_summary,
    )
    outputs = write_source_layer_capability_audit(
        payload,
        output_rows_path=args.output_rows,
        output_summary_path=args.output_summary,
        output_report_path=args.output_report,
    )
    print(json.dumps({"status": payload["validation"]["status"], "summary": payload["summary"], "outputs": outputs}, ensure_ascii=False, indent=2))
    if args.strict and payload["validation"]["status"] != "pass":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
