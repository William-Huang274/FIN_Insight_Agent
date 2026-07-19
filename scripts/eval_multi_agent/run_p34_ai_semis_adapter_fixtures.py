from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

from sec_agent.p34_lane_quality_runtime import build_ai_semis_adapter_fixture_report  # noqa: E402


DEFAULT_JSON_OUT = REPO_ROOT / "docs/project_os/p34_ai_semis_adapter_fixture_report_v0_1.json"
DEFAULT_MD_OUT = REPO_ROOT / "docs/internal/vnext_20260610/p34_ai_semis_adapter_fixture_report_v0_1.zh-CN.md"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build P34 AI/Semis adapter fixture report.")
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    parser.add_argument("--md-out", default=str(DEFAULT_MD_OUT))
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    report = build_ai_semis_adapter_fixture_report()
    json_out = Path(args.json_out)
    md_out = Path(args.md_out)
    json_out.parent.mkdir(parents=True, exist_ok=True)
    md_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_out.write_text(_render_markdown(report), encoding="utf-8")

    print(
        json.dumps(
            {
                "status": report["status"],
                "metrics": report["metrics"],
                "json_out": str(json_out),
                "md_out": str(md_out),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if args.strict and report["status"] != "adapter_fixture_parser_contract_pass_live_fetch_pending":
        raise SystemExit(1)


def _render_markdown(report: dict) -> str:
    metrics = report["metrics"]
    lines = [
        "# P34 AI/Semis Adapter Fixture Report v0.1",
        "",
        "日期：2026-07-07",
        "",
        f"状态：`{report['status']}`",
        "",
        "## 1. 目的",
        "",
        "本报告验证 P34-5 首批 adapter-family fixture 是否能把代表性输入解析成统一 runtime row。",
        "它不是 live fetch / crawler / parser 全量验收，也不是 paid LLM、full-chain 或模型对比。",
        "",
        "## 2. 指标",
        "",
        f"- adapter family：`{metrics['adapter_family_count']}`",
        f"- fixture：`{metrics['fixture_count']}`",
        f"- runtime rows：`{metrics['runtime_row_count']}`",
        f"- rejected candidates：`{metrics['rejected_candidate_count']}`",
        f"- typed gaps：`{metrics['typed_gap_count']}`",
        f"- rows with parser lineage：`{metrics['rows_with_parser_lineage_count']}`",
        f"- rows with authority scope：`{metrics['rows_with_authority_scope_count']}`",
        "",
        "## 3. Adapter Family 结果",
        "",
    ]
    for family in report["family_results"]:
        lines.extend(
            [
                f"### {family['adapter_family']}",
                "",
                f"- status：`{family['status']}`",
                f"- fixture_count：`{family['fixture_count']}`",
                f"- runtime_row_count：`{family['runtime_row_count']}`",
                f"- rejected_candidate_count：`{family['rejected_candidate_count']}`",
                f"- typed_gap_count：`{family['typed_gap_count']}`",
                f"- planned_in_source_route_plan：`{family['planned_in_source_route_plan']}`",
                "",
            ]
        )
    lines.extend(
        [
            "## 4. 边界",
            "",
            "- 本报告使用本地 artifact-backed fixture snippets，不做 live fetch。",
            "- `source_url` 使用 `source-ledger://p34/...`，表示 parser contract fixture，不表示真实 URL snapshot。",
            "- fixture rows 的 `promotion_status=fixture_parser_contract_pass_live_fetch_pending`，不能直接进入 live evidence bundle。",
            "- 下一步必须把这些 adapter 接到真实 source route attempts，或记录 attempt-backed typed gap。",
            "",
        ]
    )
    return "\n".join(lines)


if __name__ == "__main__":
    main()
