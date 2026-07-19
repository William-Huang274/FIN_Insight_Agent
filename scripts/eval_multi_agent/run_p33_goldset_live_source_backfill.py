from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

from sec_agent.humanmade_gold_set_runtime import build_goldset_live_source_backfill  # noqa: E402


DEFAULT_JSON_OUT = REPO_ROOT / "docs/project_os/p33_goldset_live_source_backfill_v0_1.json"
DEFAULT_MD_OUT = REPO_ROOT / "docs/internal/vnext_20260610/p33_goldset_live_source_backfill_v0_1.zh-CN.md"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build P33 gold-set live source backfill artifact.")
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD_OUT)
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_goldset_live_source_backfill()
    payload = {
        **payload,
        "created_at": _utc_now(),
        "artifact_refs": {
            "json_out": _rel(args.json_out),
            "md_out": _rel(args.md_out),
        },
    }
    _write_json(args.json_out, payload)
    args.md_out.parent.mkdir(parents=True, exist_ok=True)
    args.md_out.write_text(render_markdown(payload), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": payload["status"],
                "metrics": payload["metrics"],
                "json_out": str(args.json_out.resolve()),
                "md_out": str(args.md_out.resolve()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if args.strict and payload["metrics"]["row_count"] != 68:
        return 1
    return 0


def render_markdown(payload: Mapping[str, Any]) -> str:
    metrics = payload.get("metrics") if isinstance(payload.get("metrics"), Mapping) else {}
    source_summary = (
        payload.get("source_index_summary") if isinstance(payload.get("source_index_summary"), Mapping) else {}
    )
    lines: list[str] = []
    lines.append("# P33 Gold-set Live Source Backfill v0.1")
    lines.append("")
    lines.append(f"日期：{str(payload.get('created_at') or '')[:10]}")
    lines.append("")
    lines.append("## 1. 结论")
    lines.append("")
    lines.append(
        "本轮没有跑 paid LLM、full-chain、新爬虫或新 parser，而是把 gold-set matrix 的 68 条 row "
        "回填到现有已物化 source/runtime manifests，检查哪些已经有 parser-backed runtime row。"
    )
    lines.append("")
    lines.append(
        f"当前状态为 `{payload.get('status')}`。这表示一部分 slot 已能绑定到现有 runtime row，"
        "但仍有 row 需要 issuer 绑定、source route/parser 深挖，或保持 failure fixture。"
    )
    lines.append("")
    lines.append("## 2. Backfill Metrics")
    lines.append("")
    for key in (
        "case_count",
        "row_count",
        "live_runtime_ready_row_count",
        "route_candidate_only_parser_lineage_pending_count",
        "source_route_candidate_weak_not_bound_count",
        "source_route_not_bound_required_count",
        "case_binding_required_count",
        "failure_fixture_count",
        "remaining_action_required_row_count",
        "indexed_row_count",
        "indexed_ticker_count",
    ):
        lines.append(f"- `{key}`: `{metrics.get(key)}`")
    lines.append("")
    lines.append("## 3. Source Index")
    lines.append("")
    lines.append(f"- `rowset_count`: `{source_summary.get('rowset_count')}`")
    lines.append(f"- `indexed_row_count`: `{source_summary.get('indexed_row_count')}`")
    lines.append(f"- `indexed_ticker_count`: `{source_summary.get('indexed_ticker_count')}`")
    missing = source_summary.get("missing_rowsets") or []
    lines.append(f"- `missing_rowsets`: `{len(missing)}`")
    lines.append("")
    lines.append("## 4. Case Summary")
    lines.append("")
    lines.append("| Case | Type | Status | Rows | Live ready | Action required | Source rowsets |")
    lines.append("| --- | --- | --- | ---: | ---: | ---: | --- |")
    for row in payload.get("case_summaries") or []:
        if not isinstance(row, Mapping):
            continue
        source_rowsets = ", ".join(str(item) for item in row.get("source_rowset_paths") or []) or "-"
        lines.append(
            "| `{case}` | `{case_type}` | `{status}` | {rows} | {live} | {action} | {sources} |".format(
                case=row.get("case_id"),
                case_type=row.get("case_type"),
                status=row.get("status"),
                rows=row.get("row_count"),
                live=row.get("live_runtime_ready_row_count"),
                action=row.get("action_required_row_count"),
                sources=source_rowsets.replace("|", "/"),
            )
        )
    lines.append("")
    lines.append("## 5. 关键解释")
    lines.append("")
    lines.append("- `live_runtime_ready`：同 issuer、角色/产品/metric 语义匹配，且已有 source/parser/runtime lineage。")
    lines.append("- `source_route_candidate_weak_not_bound`：有候选但不足以安全绑定，不能提权。")
    lines.append("- `source_route_not_bound_required`：当前 manifests 找不到足够候选，下一步需要 locator/parser 或 typed gap attempt。")
    lines.append("- `case_binding_required_before_live_lookup`：rubric / basket slot 还没绑定到具体 issuer，不能直接查 live row。")
    lines.append("- `not_applicable_failure_fixture`：negative case 只用于失败检测，不进 evidence bundle。")
    lines.append("")
    lines.append("## 6. 下一步")
    lines.append("")
    lines.append(str(payload.get("next_step") or ""))
    lines.append("")
    lines.append("## 7. Artifact refs")
    lines.append("")
    for key, value in (payload.get("artifact_refs") or {}).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.append("")
    return "\n".join(lines)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
