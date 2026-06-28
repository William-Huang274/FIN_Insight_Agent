from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.gold_fact_signal_mart import (  # noqa: E402
    build_gold_fact_signal_mart,
    build_gold_fact_signal_mart_summary,
    render_gold_fact_signal_mart_report,
    write_gold_fact_signal_mart_sqlite,
    write_json,
    write_jsonl,
)


DEFAULT_OUTPUT_ROWS = REPO_ROOT / "data" / "manifests" / "gold_fact_signal_mart_rows_v0_1.jsonl"
DEFAULT_OUTPUT_SOURCE_ROWSETS = REPO_ROOT / "data" / "manifests" / "gold_fact_signal_mart_source_rowsets_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY = REPO_ROOT / "data" / "manifests" / "gold_fact_signal_mart_summary_v0_1.json"
DEFAULT_OUTPUT_SQLITE = REPO_ROOT / "data" / "workbench_private" / "research_data" / "gold_fact_signal_mart_v0_1.sqlite"
DEFAULT_OUTPUT_REPORT = REPO_ROOT / "docs" / "internal" / "vnext_20260610" / "rd3_gold_fact_signal_mart.zh-CN.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build RD3 Gold Fact / Signal Mart JSONL and SQLite artifacts.")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--output-rows", type=Path, default=DEFAULT_OUTPUT_ROWS)
    parser.add_argument("--output-source-rowsets", type=Path, default=DEFAULT_OUTPUT_SOURCE_ROWSETS)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--output-sqlite", type=Path, default=DEFAULT_OUTPUT_SQLITE)
    parser.add_argument("--output-report", type=Path, default=DEFAULT_OUTPUT_REPORT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    result = build_gold_fact_signal_mart(repo_root)
    sqlite_row_count = write_gold_fact_signal_mart_sqlite(args.output_sqlite, result["rows"])
    summary = build_gold_fact_signal_mart_summary(
        rows=result["rows"],
        source_rowset_status=result["source_rowset_status"],
        generated_at=result["summary"]["generated_at"],
        sqlite_path=str(args.output_sqlite),
        sqlite_row_count=sqlite_row_count,
    )
    output_paths = {
        "gold_fact_signal_mart_rows": str(args.output_rows),
        "gold_fact_signal_mart_source_rowsets": str(args.output_source_rowsets),
        "sqlite": str(args.output_sqlite),
        "summary": str(args.output_summary),
        "report": str(args.output_report),
    }
    write_jsonl(args.output_rows, result["rows"])
    write_jsonl(args.output_source_rowsets, result["source_rowset_status"])
    write_json(args.output_summary, {**summary, "outputs": output_paths})
    args.output_report.parent.mkdir(parents=True, exist_ok=True)
    args.output_report.write_text(
        render_gold_fact_signal_mart_report({**summary, "outputs": output_paths}, output_paths=output_paths),
        encoding="utf-8",
    )
    print(json.dumps({**summary, "outputs": output_paths}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
