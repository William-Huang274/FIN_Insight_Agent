from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.raw_source_provenance_store import (  # noqa: E402
    build_raw_source_provenance_store,
    render_raw_source_provenance_report,
    write_json,
    write_jsonl,
)


DEFAULT_OUTPUT_DOCUMENTS = REPO_ROOT / "data" / "manifests" / "raw_source_documents_v0_1.jsonl"
DEFAULT_OUTPUT_ATTEMPTS = REPO_ROOT / "data" / "manifests" / "raw_fetch_attempts_v0_1.jsonl"
DEFAULT_OUTPUT_SNAPSHOTS = REPO_ROOT / "data" / "manifests" / "source_snapshots_v0_1.jsonl"
DEFAULT_OUTPUT_LINEAGE = REPO_ROOT / "data" / "manifests" / "runtime_row_source_lineage_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY = REPO_ROOT / "data" / "manifests" / "raw_source_provenance_summary_v0_1.json"
DEFAULT_OUTPUT_REPORT = REPO_ROOT / "docs" / "internal" / "vnext_20260610" / "rd1_raw_source_provenance_store.zh-CN.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build RD1 Bronze raw source provenance store artifacts.")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--max-hash-bytes", type=int, default=64 * 1024 * 1024)
    parser.add_argument("--output-documents", type=Path, default=DEFAULT_OUTPUT_DOCUMENTS)
    parser.add_argument("--output-attempts", type=Path, default=DEFAULT_OUTPUT_ATTEMPTS)
    parser.add_argument("--output-snapshots", type=Path, default=DEFAULT_OUTPUT_SNAPSHOTS)
    parser.add_argument("--output-lineage", type=Path, default=DEFAULT_OUTPUT_LINEAGE)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--output-report", type=Path, default=DEFAULT_OUTPUT_REPORT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    result = build_raw_source_provenance_store(repo_root, max_hash_bytes=args.max_hash_bytes)
    output_paths = {
        "raw_source_documents": str(args.output_documents),
        "raw_fetch_attempts": str(args.output_attempts),
        "source_snapshots": str(args.output_snapshots),
        "runtime_row_source_lineage": str(args.output_lineage),
        "summary": str(args.output_summary),
        "report": str(args.output_report),
    }
    write_jsonl(args.output_documents, result["source_documents"])
    write_jsonl(args.output_attempts, result["fetch_attempts"])
    write_jsonl(args.output_snapshots, result["source_snapshots"])
    write_jsonl(args.output_lineage, result["runtime_lineage_rows"])
    summary = {**result["summary"], "outputs": output_paths}
    write_json(args.output_summary, summary)
    args.output_report.parent.mkdir(parents=True, exist_ok=True)
    args.output_report.write_text(
        render_raw_source_provenance_report(summary, output_paths=output_paths),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
