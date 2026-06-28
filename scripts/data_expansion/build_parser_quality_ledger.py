from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.parser_quality_ledger import (  # noqa: E402
    build_parser_quality_ledger,
    render_parser_quality_report,
    write_json,
    write_jsonl,
)


DEFAULT_OUTPUT_RUNS = REPO_ROOT / "data" / "manifests" / "parser_run_ledger_v0_1.jsonl"
DEFAULT_OUTPUT_ARTIFACTS = REPO_ROOT / "data" / "manifests" / "parser_output_artifact_ledger_v0_1.jsonl"
DEFAULT_OUTPUT_REJECTIONS = REPO_ROOT / "data" / "manifests" / "parser_rejection_taxonomy_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY = REPO_ROOT / "data" / "manifests" / "parser_quality_summary_v0_1.json"
DEFAULT_OUTPUT_REPORT = REPO_ROOT / "docs" / "internal" / "vnext_20260610" / "rd2_parser_chunk_table_metric_ledger.zh-CN.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build RD2 parser/chunk/table/metric quality ledger artifacts.")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--max-line-count-bytes", type=int, default=64 * 1024 * 1024)
    parser.add_argument("--output-runs", type=Path, default=DEFAULT_OUTPUT_RUNS)
    parser.add_argument("--output-artifacts", type=Path, default=DEFAULT_OUTPUT_ARTIFACTS)
    parser.add_argument("--output-rejections", type=Path, default=DEFAULT_OUTPUT_REJECTIONS)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--output-report", type=Path, default=DEFAULT_OUTPUT_REPORT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    result = build_parser_quality_ledger(repo_root, max_line_count_bytes=args.max_line_count_bytes)
    output_paths = {
        "parser_run_ledger": str(args.output_runs),
        "parser_output_artifact_ledger": str(args.output_artifacts),
        "parser_rejection_taxonomy": str(args.output_rejections),
        "summary": str(args.output_summary),
        "report": str(args.output_report),
    }
    write_jsonl(args.output_runs, result["parser_runs"])
    write_jsonl(args.output_artifacts, result["artifact_rows"])
    write_jsonl(args.output_rejections, result["rejection_rows"])
    summary = {**result["summary"], "outputs": output_paths}
    write_json(args.output_summary, summary)
    args.output_report.parent.mkdir(parents=True, exist_ok=True)
    args.output_report.write_text(render_parser_quality_report(summary, output_paths=output_paths), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if str(summary.get("status") or "").startswith("pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
