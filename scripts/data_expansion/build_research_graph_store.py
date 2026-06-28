from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.research_graph_store import (  # noqa: E402
    build_research_graph_store,
    build_research_graph_summary,
    render_research_graph_report,
    write_json,
    write_jsonl,
    write_research_graph_sqlite,
)


DEFAULT_OUTPUT_NODES = REPO_ROOT / "data" / "manifests" / "research_graph_nodes_v0_1.jsonl"
DEFAULT_OUTPUT_EDGES = REPO_ROOT / "data" / "manifests" / "research_graph_edges_v0_1.jsonl"
DEFAULT_OUTPUT_SUPPORT = REPO_ROOT / "data" / "manifests" / "research_graph_evidence_support_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY = REPO_ROOT / "data" / "manifests" / "research_graph_summary_v0_1.json"
DEFAULT_OUTPUT_SQLITE = REPO_ROOT / "data" / "workbench_private" / "research_data" / "research_graph_store_v0_1.sqlite"
DEFAULT_OUTPUT_REPORT = REPO_ROOT / "docs" / "internal" / "vnext_20260610" / "rd4_research_graph_store.zh-CN.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build RD4 Research Graph Store JSONL and SQLite artifacts.")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--output-nodes", type=Path, default=DEFAULT_OUTPUT_NODES)
    parser.add_argument("--output-edges", type=Path, default=DEFAULT_OUTPUT_EDGES)
    parser.add_argument("--output-support", type=Path, default=DEFAULT_OUTPUT_SUPPORT)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--output-sqlite", type=Path, default=DEFAULT_OUTPUT_SQLITE)
    parser.add_argument("--output-report", type=Path, default=DEFAULT_OUTPUT_REPORT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    result = build_research_graph_store(repo_root)
    sqlite_counts = write_research_graph_sqlite(
        args.output_sqlite,
        nodes=result["nodes"],
        edges=result["edges"],
        support_rows=result["support_rows"],
    )
    summary = build_research_graph_summary(
        nodes=result["nodes"],
        edges=result["edges"],
        support_rows=result["support_rows"],
        generated_at=result["summary"]["generated_at"],
        sqlite_path=str(args.output_sqlite),
        sqlite_node_count=sqlite_counts["node_count"],
        sqlite_edge_count=sqlite_counts["edge_count"],
        sqlite_support_count=sqlite_counts["support_count"],
    )
    output_paths = {
        "nodes": str(args.output_nodes),
        "edges": str(args.output_edges),
        "evidence_support": str(args.output_support),
        "sqlite": str(args.output_sqlite),
        "summary": str(args.output_summary),
        "report": str(args.output_report),
    }
    write_jsonl(args.output_nodes, result["nodes"])
    write_jsonl(args.output_edges, result["edges"])
    write_jsonl(args.output_support, result["support_rows"])
    write_json(args.output_summary, {**summary, "outputs": output_paths})
    args.output_report.parent.mkdir(parents=True, exist_ok=True)
    args.output_report.write_text(
        render_research_graph_report({**summary, "outputs": output_paths}, output_paths=output_paths),
        encoding="utf-8",
    )
    print(json.dumps({**summary, "outputs": output_paths}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
