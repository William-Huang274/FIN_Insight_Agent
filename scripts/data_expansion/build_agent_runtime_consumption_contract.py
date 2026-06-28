from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.agent_runtime_consumption_contract import (  # noqa: E402
    build_agent_runtime_consumption_contract,
    build_agent_runtime_consumption_summary,
    render_agent_runtime_consumption_report,
    write_agent_runtime_consumption_sqlite,
    write_json,
    write_jsonl,
)


DEFAULT_OUTPUT_BRIEFS = REPO_ROOT / "data" / "manifests" / "agent_runtime_data_brief_v0_1.jsonl"
DEFAULT_OUTPUT_PACKS = REPO_ROOT / "data" / "manifests" / "role_specific_evidence_pack_registry_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY = REPO_ROOT / "data" / "manifests" / "agent_runtime_consumption_contract_summary_v0_1.json"
DEFAULT_OUTPUT_SQLITE = REPO_ROOT / "data" / "workbench_private" / "research_data" / "agent_runtime_consumption_contract_v0_1.sqlite"
DEFAULT_OUTPUT_REPORT = REPO_ROOT / "docs" / "internal" / "vnext_20260610" / "rd6_agent_runtime_consumption_contract.zh-CN.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build RD6 agent runtime data briefs and role evidence pack registry.")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--max-refs-per-pack", type=int, default=24)
    parser.add_argument("--output-briefs", type=Path, default=DEFAULT_OUTPUT_BRIEFS)
    parser.add_argument("--output-packs", type=Path, default=DEFAULT_OUTPUT_PACKS)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--output-sqlite", type=Path, default=DEFAULT_OUTPUT_SQLITE)
    parser.add_argument("--output-report", type=Path, default=DEFAULT_OUTPUT_REPORT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    result = build_agent_runtime_consumption_contract(repo_root, max_refs_per_pack=args.max_refs_per_pack)
    sqlite_counts = write_agent_runtime_consumption_sqlite(
        args.output_sqlite,
        briefs=result["briefs"],
        packs=result["packs"],
    )
    summary = build_agent_runtime_consumption_summary(
        briefs=result["briefs"],
        packs=result["packs"],
        generated_at=result["summary"]["generated_at"],
    )
    summary = {
        **summary,
        "sqlite_path": str(args.output_sqlite),
        "sqlite_brief_count": sqlite_counts["brief_count"],
        "sqlite_pack_count": sqlite_counts["pack_count"],
    }
    output_paths = {
        "agent_runtime_data_briefs": str(args.output_briefs),
        "role_specific_evidence_pack_registry": str(args.output_packs),
        "sqlite": str(args.output_sqlite),
        "summary": str(args.output_summary),
        "report": str(args.output_report),
    }
    write_jsonl(args.output_briefs, result["briefs"])
    write_jsonl(args.output_packs, result["packs"])
    write_json(args.output_summary, {**summary, "outputs": output_paths})
    args.output_report.parent.mkdir(parents=True, exist_ok=True)
    args.output_report.write_text(
        render_agent_runtime_consumption_report({**summary, "outputs": output_paths}, output_paths=output_paths),
        encoding="utf-8",
    )
    print(json.dumps({**summary, "outputs": output_paths}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
