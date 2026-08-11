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
    SECOND_THIRD_LAYER_REAL_SOURCE_READINESS_COMPANY_SCHEMA_VERSION,
    build_second_third_layer_real_source_readiness_gate,
    load_jsonl,
)


DEFAULT_COMPANY_UNIVERSE = REPO_ROOT / "data/manifests/company_product_slots_v0_1.jsonl"
DEFAULT_SECOND_LAYER_ROW_PATHS = [
    REPO_ROOT / "data/manifests/sec_product_taxonomy_context_rows_v0_1.jsonl",
    REPO_ROOT / "data/manifests/official_product_surface_context_rows_v0_1.jsonl",
    REPO_ROOT / "data/manifests/official_product_catalog_context_rows_v0_1.jsonl",
    REPO_ROOT / "data/manifests/company_reported_product_operating_metric_runtime_rows_v0_1.jsonl",
    REPO_ROOT / "data/manifests/non_us_product_kpi_local_disclosure_runtime_rows_v0_1.jsonl",
    REPO_ROOT / "data/manifests/r16_product_kpi_deep_repair_runtime_rows_v0_1.jsonl",
    REPO_ROOT / "data/manifests/r17_product_family_evidence_runtime_rows_v0_1.jsonl",
    REPO_ROOT / "data/manifests/targeted_official_technology_document_context_rows_v0_1.jsonl",
]
DEFAULT_THIRD_LAYER_ROW_PATHS = [
    REPO_ROOT / "data/manifests/sec_financial_statement_metric_runtime_rows_v0_1.jsonl",
    REPO_ROOT / "data/manifests/non_us_l1_financial_statement_metric_runtime_rows_v0_1.jsonl",
    REPO_ROOT / "data/manifests/capital_funding_ownership_context_rows_v0_1.jsonl",
    REPO_ROOT / "data/manifests/sec_capital_market_event_context_rows_v0_1.jsonl",
]
DEFAULT_OUTPUT_SUMMARY = REPO_ROOT / "data/manifests/second_third_layer_real_source_readiness_gate_summary_v0_1.json"
DEFAULT_OUTPUT_COMPANY_ROWS = REPO_ROOT / "data/manifests/second_third_layer_real_source_readiness_company_rows_v0_1.jsonl"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build stricter per-company real-source readiness gate for second and third data layers."
    )
    parser.add_argument("--company-count", type=int, default=603)
    parser.add_argument("--company-universe", type=Path, default=DEFAULT_COMPANY_UNIVERSE)
    parser.add_argument(
        "--second-layer-row-path",
        dest="second_layer_row_paths",
        action="append",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--third-layer-row-path",
        dest="third_layer_row_paths",
        action="append",
        type=Path,
        default=None,
    )
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--output-company-rows", type=Path, default=DEFAULT_OUTPUT_COMPANY_ROWS)
    args = parser.parse_args()
    if args.second_layer_row_paths is None:
        args.second_layer_row_paths = DEFAULT_SECOND_LAYER_ROW_PATHS
    if args.third_layer_row_paths is None:
        args.third_layer_row_paths = DEFAULT_THIRD_LAYER_ROW_PATHS
    return args


def main() -> int:
    args = parse_args()
    second_rows = _load_rows_with_source_file(args.second_layer_row_paths)
    third_rows = _load_rows_with_source_file(args.third_layer_row_paths)
    payload = build_second_third_layer_real_source_readiness_gate(
        company_universe_rows=load_jsonl(args.company_universe),
        second_layer_rows=second_rows,
        third_layer_rows=third_rows,
        company_count=args.company_count,
    )
    company_rows = payload.pop("company_rows")
    args.output_summary.parent.mkdir(parents=True, exist_ok=True)
    args.output_company_rows.parent.mkdir(parents=True, exist_ok=True)
    args.output_summary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args.output_company_rows.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in company_rows),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": payload["status"],
                "metrics": payload["metrics"],
                "company_row_schema": SECOND_THIRD_LAYER_REAL_SOURCE_READINESS_COMPANY_SCHEMA_VERSION,
                "outputs": {"summary": str(args.output_summary), "company_rows": str(args.output_company_rows)},
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
