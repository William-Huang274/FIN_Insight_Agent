from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.retrieval_index_registry import (  # noqa: E402
    build_retrieval_index_registry,
    build_retrieval_index_registry_summary,
    render_retrieval_index_registry_report,
    write_json,
    write_jsonl,
    write_retrieval_index_registry_sqlite,
)


DEFAULT_OUTPUT_SNAPSHOTS = REPO_ROOT / "data" / "manifests" / "retrieval_index_snapshot_registry_v0_1.jsonl"
DEFAULT_OUTPUT_LINEAGE = REPO_ROOT / "data" / "manifests" / "retrieval_index_source_lineage_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY = REPO_ROOT / "data" / "manifests" / "retrieval_index_registry_summary_v0_1.json"
DEFAULT_OUTPUT_SQLITE = REPO_ROOT / "data" / "workbench_private" / "research_data" / "retrieval_index_registry_v0_1.sqlite"
DEFAULT_OUTPUT_REPORT = REPO_ROOT / "docs" / "internal" / "vnext_20260610" / "rd5_retrieval_index_registry.zh-CN.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build RD5 RAG index snapshot registry and source lineage artifacts.")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--output-snapshots", type=Path, default=DEFAULT_OUTPUT_SNAPSHOTS)
    parser.add_argument("--output-lineage", type=Path, default=DEFAULT_OUTPUT_LINEAGE)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--output-sqlite", type=Path, default=DEFAULT_OUTPUT_SQLITE)
    parser.add_argument("--output-report", type=Path, default=DEFAULT_OUTPUT_REPORT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    result = build_retrieval_index_registry(repo_root)
    sqlite_counts = write_retrieval_index_registry_sqlite(
        args.output_sqlite,
        snapshots=result["snapshots"],
        lineages=result["lineages"],
    )
    summary = build_retrieval_index_registry_summary(
        snapshots=result["snapshots"],
        lineages=result["lineages"],
        generated_at=result["summary"]["generated_at"],
    )
    summary = {
        **summary,
        "sqlite_path": str(args.output_sqlite),
        "sqlite_snapshot_count": sqlite_counts["snapshot_count"],
        "sqlite_lineage_count": sqlite_counts["lineage_count"],
    }
    output_paths = {
        "retrieval_index_snapshots": str(args.output_snapshots),
        "retrieval_index_source_lineage": str(args.output_lineage),
        "sqlite": str(args.output_sqlite),
        "summary": str(args.output_summary),
        "report": str(args.output_report),
    }
    write_jsonl(args.output_snapshots, result["snapshots"])
    write_jsonl(args.output_lineage, result["lineages"])
    write_json(args.output_summary, {**summary, "outputs": output_paths})
    args.output_report.parent.mkdir(parents=True, exist_ok=True)
    args.output_report.write_text(
        render_retrieval_index_registry_report({**summary, "outputs": output_paths}, output_paths=output_paths),
        encoding="utf-8",
    )
    print(json.dumps({**summary, "outputs": output_paths}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
