from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.raw_disclosure_data_inventory import (  # noqa: E402
    build_inventory_summary,
    build_rag_index_inventory,
    build_raw_disclosure_data_inventory,
    build_runtime_database_inventory,
    render_inventory_report,
    write_json,
    write_jsonl,
)


DEFAULT_OUTPUT_RAW = REPO_ROOT / "data" / "manifests" / "raw_disclosure_data_inventory_v0_1.jsonl"
DEFAULT_OUTPUT_RAG = REPO_ROOT / "data" / "manifests" / "rag_index_inventory_v0_1.jsonl"
DEFAULT_OUTPUT_DATABASE = REPO_ROOT / "data" / "manifests" / "runtime_database_inventory_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY = REPO_ROOT / "data" / "manifests" / "raw_disclosure_rag_database_inventory_summary_v0_1.json"
DEFAULT_OUTPUT_REPORT = REPO_ROOT / "docs" / "internal" / "vnext_20260610" / "rd0_raw_disclosure_rag_database_inventory.zh-CN.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build RD0 raw disclosure / RAG / runtime database inventory artifacts."
    )
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--milvus-config-path", type=Path, default=None)
    parser.add_argument("--output-raw", type=Path, default=DEFAULT_OUTPUT_RAW)
    parser.add_argument("--output-rag", type=Path, default=DEFAULT_OUTPUT_RAG)
    parser.add_argument("--output-database", type=Path, default=DEFAULT_OUTPUT_DATABASE)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--output-report", type=Path, default=DEFAULT_OUTPUT_REPORT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    raw_rows = build_raw_disclosure_data_inventory(repo_root)
    rag_rows = build_rag_index_inventory(repo_root, milvus_config_path=args.milvus_config_path)
    database_rows = build_runtime_database_inventory(repo_root)
    summary = build_inventory_summary(raw_rows=raw_rows, rag_rows=rag_rows, database_rows=database_rows)
    output_paths = {
        "raw_disclosure_data_inventory": str(args.output_raw),
        "rag_index_inventory": str(args.output_rag),
        "runtime_database_inventory": str(args.output_database),
        "summary": str(args.output_summary),
        "report": str(args.output_report),
    }
    write_jsonl(args.output_raw, raw_rows)
    write_jsonl(args.output_rag, rag_rows)
    write_jsonl(args.output_database, database_rows)
    write_json(args.output_summary, {**summary, "outputs": output_paths})
    args.output_report.parent.mkdir(parents=True, exist_ok=True)
    args.output_report.write_text(
        render_inventory_report({**summary, "outputs": output_paths}, output_paths=output_paths),
        encoding="utf-8",
    )
    print(json.dumps({**summary, "outputs": output_paths}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
