from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.data_quality_release_eval_gate import (  # noqa: E402
    build_data_quality_release_eval_gate,
    build_data_quality_release_eval_summary,
    render_data_quality_release_eval_report,
    write_data_quality_release_eval_sqlite,
    write_json,
    write_jsonl,
)


DEFAULT_OUTPUT_ROWS = REPO_ROOT / "data" / "manifests" / "data_quality_release_eval_gate_rows_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY = REPO_ROOT / "data" / "manifests" / "data_quality_release_eval_gate_summary_v0_1.json"
DEFAULT_OUTPUT_SQLITE = REPO_ROOT / "data" / "workbench_private" / "research_data" / "data_quality_release_eval_gate_v0_1.sqlite"
DEFAULT_OUTPUT_REPORT = REPO_ROOT / "docs" / "internal" / "vnext_20260610" / "rd7_data_quality_release_eval_gate.zh-CN.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build RD7 data-quality / release-eval gate artifacts.")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--output-rows", type=Path, default=DEFAULT_OUTPUT_ROWS)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--output-sqlite", type=Path, default=DEFAULT_OUTPUT_SQLITE)
    parser.add_argument("--output-report", type=Path, default=DEFAULT_OUTPUT_REPORT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_data_quality_release_eval_gate(args.repo_root.resolve())
    sqlite_counts = write_data_quality_release_eval_sqlite(args.output_sqlite, gate_rows=result["gate_rows"])
    summary = build_data_quality_release_eval_summary(
        gate_rows=result["gate_rows"],
        generated_at=result["summary"]["generated_at"],
    )
    summary = {
        **summary,
        "upstream_summary_statuses": result["summary"].get("upstream_summary_statuses", {}),
        "policy": result["summary"].get("policy", ""),
        "sqlite_path": str(args.output_sqlite),
        "sqlite_gate_row_count": sqlite_counts["gate_row_count"],
    }
    output_paths = {
        "gate_rows": str(args.output_rows),
        "sqlite": str(args.output_sqlite),
        "summary": str(args.output_summary),
        "report": str(args.output_report),
    }
    write_jsonl(args.output_rows, result["gate_rows"])
    write_json(args.output_summary, {**summary, "outputs": output_paths})
    args.output_report.parent.mkdir(parents=True, exist_ok=True)
    args.output_report.write_text(
        render_data_quality_release_eval_report({**summary, "outputs": output_paths}, output_paths=output_paths),
        encoding="utf-8",
    )
    print(json.dumps({**summary, "outputs": output_paths}, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if summary.get("status") == "action_required" else 0


if __name__ == "__main__":
    raise SystemExit(main())
