from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

from sec_agent.p35_ai_infra_supervisor_dogfood import (  # noqa: E402
    build_ai_infra_decision_surface_framework,
    build_current_system_gap_audit,
)


DEFAULT_FRAMEWORK_JSON = (
    REPO_ROOT / "docs/project_os/p35_ai_infra_decision_surface_framework_v0_1.json"
)
DEFAULT_GAP_AUDIT_JSON = (
    REPO_ROOT / "docs/project_os/p35_ai_infra_current_system_gap_audit_v0_1.json"
)
DEFAULT_FRAMEWORK_MD = (
    REPO_ROOT / "docs/internal/vnext_20260610/p35_ai_infra_supervisor_dogfood_framework.zh-CN.md"
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build the P35 AI infrastructure decision-surface framework and current-system gap audit. "
            "This is deterministic and does not call an LLM or run full-chain."
        )
    )
    parser.add_argument("--framework-json", type=Path, default=DEFAULT_FRAMEWORK_JSON)
    parser.add_argument("--gap-audit-json", type=Path, default=DEFAULT_GAP_AUDIT_JSON)
    parser.add_argument("--framework-md", type=Path, default=DEFAULT_FRAMEWORK_MD)
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    framework = build_ai_infra_decision_surface_framework()
    gap_audit = build_current_system_gap_audit(framework=framework)

    for path in (args.framework_json, args.gap_audit_json, args.framework_md):
        path.parent.mkdir(parents=True, exist_ok=True)
    args.framework_json.write_text(json.dumps(framework, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.gap_audit_json.write_text(json.dumps(gap_audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.framework_md.write_text(_framework_md(framework, gap_audit), encoding="utf-8")

    summary = {
        "status": gap_audit["status"],
        "framework_json": str(args.framework_json.resolve()),
        "gap_audit_json": str(args.gap_audit_json.resolve()),
        "framework_md": str(args.framework_md.resolve()),
        "segment_count": len(framework["chain_segments"]),
        "dimension_count": len(framework["decision_dimensions"]),
        "decision_surface_cell_count": len(framework["decision_surface_cells"]),
        "missing_cell_count": len(gap_audit["missing_decision_surface_cells"]),
        "workbuddy_samples_read": gap_audit["scope"]["workbuddy_samples_read"],
        "paid_llm_run": False,
        "full_chain_run": False,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if args.strict and summary["workbuddy_samples_read"] == 0:
        return 1
    return 0


def _framework_md(framework: Mapping[str, Any], gap_audit: Mapping[str, Any]) -> str:
    lines = [
        "# P35 AI Infra Supervisor Dogfood Framework",
        "",
        "本文件是 no-paid deterministic dogfood 产物：先把用户题面需要的研究框架固化，再对照当前 P34 runtime rows 和 WorkBuddy 样本检查缺口。不调用 LLM，不跑 full-chain。",
        "",
        "## 最终输出预期",
        "",
        "- 开头必须是 TL;DR 判断和五链条决策面，不是数据 lineage 或边界声明。",
        "- 决策面覆盖 Accelerator、Server OEM、Foundry/Packaging、HBM、Semicap。",
        "- 每个链条都要回答 demand proof、capture mechanism、revenue evidence、profit quality、bottleneck monetization、margin dilution、capex digestion、export control、price-in、counter-thesis、source grade、numeric sanity。",
        "- 官方披露、parser row、二级估算、推断和 attempt-backed gap 必须分层标注。",
        "- 如果当前库不够，supervisor 必须补源或写清楚 source-hunter attempt，而不是直接把报告写成边界声明。",
        "",
        "## 决策面规模",
        "",
        f"- 产业链环节：`{len(framework['chain_segments'])}`。",
        f"- 判断维度：`{len(framework['decision_dimensions'])}`。",
        f"- 决策单元格：`{len(framework['decision_surface_cells'])}`。",
        "",
        "## 当前系统审计摘要",
        "",
    ]
    coverage = gap_audit["current_p34_coverage"]
    lines.extend(
        [
            f"- P34 accepted runtime rows：`{coverage.get('accepted_row_count')}`。",
            f"- P34 typed gaps：`{coverage.get('typed_gap_count')}`。",
            f"- P34 quality audit：`{coverage.get('quality_audit_status')}`；full-chain allowed：`{coverage.get('full_chain_allowed')}`。",
            f"- WorkBuddy HTML samples read：`{gap_audit['scope']['workbuddy_samples_read']}`。",
            f"- Missing decision-surface cells：`{len(gap_audit['missing_decision_surface_cells'])}`。",
            "",
            "## 关键缺口",
            "",
        ]
    )
    for row in gap_audit["root_causes"]:
        lines.extend(
            [
                f"### {row['root_cause_id']}",
                "",
                f"- 层级：`{row['layer']}`。",
                f"- 发现：{row['finding']}",
                f"- 影响：{row['why_it_matters']}",
                f"- 修复方向：{row['repair_direction']}",
                "",
            ]
        )
    lines.extend(
        [
            "## 本轮未运行",
            "",
            *[f"- `{item}`" for item in gap_audit["not_run"]],
            "",
        ]
    )
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
