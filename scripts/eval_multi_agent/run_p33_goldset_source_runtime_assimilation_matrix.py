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

from sec_agent.humanmade_gold_set_runtime import (  # noqa: E402
    build_goldset_source_runtime_assimilation_matrix,
)


DEFAULT_JSON_OUT = REPO_ROOT / "docs/project_os/p33_goldset_source_runtime_assimilation_matrix_v0_1.json"
DEFAULT_MD_OUT = (
    REPO_ROOT / "docs/internal/vnext_20260610/p33_goldset_source_runtime_assimilation_matrix_v0_1.zh-CN.md"
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build P33 gold-set source-runtime assimilation matrix.")
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD_OUT)
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    matrix = build_goldset_source_runtime_assimilation_matrix()
    matrix = {
        **matrix,
        "created_at": _utc_now(),
        "artifact_refs": {
            "json_out": _rel(args.json_out),
            "md_out": _rel(args.md_out),
        },
    }
    _write_json(args.json_out, matrix)
    args.md_out.parent.mkdir(parents=True, exist_ok=True)
    args.md_out.write_text(render_markdown(matrix), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": matrix["status"],
                "matrix_integrity_status": matrix["matrix_integrity_status"],
                "metrics": matrix["metrics"],
                "json_out": str(args.json_out.resolve()),
                "md_out": str(args.md_out.resolve()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if args.strict and matrix["matrix_integrity_status"] != "pass":
        return 1
    return 0


def render_markdown(matrix: Mapping[str, Any]) -> str:
    metrics = matrix.get("metrics") if isinstance(matrix.get("metrics"), Mapping) else {}
    lines: list[str] = []
    lines.append("# P33 Gold-set Source Runtime Assimilation Matrix v0.1")
    lines.append("")
    lines.append(f"日期：{str(matrix.get('created_at') or '')[:10]}")
    lines.append("")
    lines.append("## 1. 结论")
    lines.append("")
    lines.append(
        "本矩阵把 15 个 Humanmade Gold Set packs 逐条映射为：case -> required evidence slot -> "
        "registered source role -> crawler/parser 状态 -> runtime row 状态 -> authority boundary。"
    )
    lines.append("")
    lines.append(
        "结果不是 live source 全通过，而是 `partial_artifact_scope_pass_live_runtime_pending`："
        "矩阵完整，但大多数 rubric case 仍是 gold exemplar / required slot，不能被当作真实 source row。"
    )
    lines.append("")
    lines.append("## 2. 指标")
    lines.append("")
    for key in (
        "case_count",
        "row_count",
        "live_runtime_ready_row_count",
        "source_route_unverified_runtime_artifact_row_count",
        "artifact_only_live_runtime_pending_row_count",
        "failure_fixture_row_count",
        "unknown_source_status_row_count",
        "live_runtime_pending_case_count",
        "registered_source_role_count",
    ):
        lines.append(f"- `{key}`: `{metrics.get(key)}`")
    lines.append("")
    lines.append("## 3. Case Summary")
    lines.append("")
    lines.append(
        "| Case | Type | Status | Rows | Live ready | Runtime artifact/source-route unverified | "
        "Artifact-only pending | Failure fixture | Next action |"
    )
    lines.append("| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |")
    for row in matrix.get("case_summaries") or []:
        if not isinstance(row, Mapping):
            continue
        lines.append(
            "| `{case}` | `{case_type}` | `{status}` | {rows} | {live} | {unverified} | {pending} | {fixture} | {next_action} |".format(
                case=row.get("case_id"),
                case_type=row.get("case_type"),
                status=row.get("status"),
                rows=row.get("evidence_row_count"),
                live=row.get("live_runtime_ready_row_count"),
                unverified=row.get("source_route_unverified_runtime_artifact_row_count"),
                pending=row.get("artifact_only_live_runtime_pending_row_count"),
                fixture=row.get("failure_fixture_row_count"),
                next_action=str(row.get("next_action") or "").replace("|", "/"),
            )
        )
    lines.append("")
    lines.append("## 4. 关键边界")
    lines.append("")
    lines.append("- AI/Semis deep case 的 20 条 rows 是 gold-depth runtime artifact rows，但还没有逐条证明 live source route / crawler / parser lineage。")
    lines.append("- 8 个 rubric cases 的 rows 是 required evidence slots，不是 live retrieval 或 parser-backed facts。")
    lines.append("- 6 个 negative cases 是 failure fixtures，只能进入 aggregate / writer / verifier / Workbench 的失败检测，不能进入 evidence bundle。")
    lines.append("- 本轮未运行 paid LLM、full-chain、新检索、爬虫或 parser。")
    lines.append("")
    lines.append("## 5. 下一步")
    lines.append("")
    lines.append(
        "按 case 和 required slot 补真实 source route / parser：先从 AI/Semis deep case 的 source-route lineage "
        "验证开始，再按 rubric case 分行业补 live rows；没有可得公开源时必须记录 attempt-backed typed gap。"
    )
    lines.append("")
    lines.append("## 6. Artifact refs")
    lines.append("")
    for key, value in (matrix.get("artifact_refs") or {}).items():
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
