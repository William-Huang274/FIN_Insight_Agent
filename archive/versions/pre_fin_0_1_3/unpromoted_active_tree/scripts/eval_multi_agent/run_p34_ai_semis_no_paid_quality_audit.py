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

from sec_agent.p34_lane_quality_runtime import (  # noqa: E402
    DEFAULT_LIVE_ROUTE_ATTEMPT_REPORT_PATH,
    build_ai_semis_no_paid_quality_audit,
)


DEFAULT_JSON_OUT = REPO_ROOT / "docs/project_os/p34_ai_semis_no_paid_quality_audit_v0_1.json"
DEFAULT_MD_OUT = REPO_ROOT / "docs/internal/vnext_20260610/p34_ai_semis_no_paid_quality_audit_v0_1.zh-CN.md"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build P34 AI/Semis no-paid quality audit.")
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    parser.add_argument("--md-out", default=str(DEFAULT_MD_OUT))
    parser.add_argument("--live-route-report", default=str(DEFAULT_LIVE_ROUTE_ATTEMPT_REPORT_PATH))
    parser.add_argument("--skip-live-route-report", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    live_report = None
    live_report_path = Path(args.live_route_report)
    if not args.skip_live_route_report and live_report_path.exists():
        live_report = json.loads(live_report_path.read_text(encoding="utf-8"))

    report = build_ai_semis_no_paid_quality_audit(live_route_attempt_report=live_report)
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
    if args.strict and str(report["status"]).startswith("blocked"):
        raise SystemExit(1)


def _render_markdown(report: dict) -> str:
    metrics = report["metrics"]
    allow_scoped = bool(metrics.get("allow_scoped_paid_memo_writer") or metrics.get("allow_paid_memo_writer"))
    if allow_scoped:
        conclusion = [
            "P34 route plan、adapter fixture parser contract 和 live route attempts 已经形成 bounded no-paid quality pass。",
            "当前可以进入 scoped paid Memo Writer node，但必须把 DELL AI server margin bridge 和 market price-in exact positioning 写成 attempt-backed typed boundary；full-chain、模型对比、case expansion 和 release eval 仍禁止。",
        ]
    else:
        conclusion = [
            "P34 route plan 和 adapter fixture parser contract 已存在，但当前仍不能放行 paid Memo Writer 或 full-chain。",
            "原因不是工程没跑通，而是 live source attempts 和多个 judgment chain 的研究质量仍未闭合。",
        ]
    lines = [
        "# P34 AI/Semis No-paid Quality Audit v0.1",
        "",
        "日期：2026-07-07",
        "",
        f"状态：`{report['status']}`",
        "",
        "## 1. 结论",
        "",
        *conclusion,
        "",
        "## 2. 指标",
        "",
        f"- judgment_chain_count：`{metrics['judgment_chain_count']}`",
        f"- chain_pass_count：`{metrics['chain_pass_count']}`",
        f"- chain_partial_count：`{metrics['chain_partial_count']}`",
        f"- chain_fail_count：`{metrics['chain_fail_count']}`",
        f"- source_route_gap_count：`{metrics['source_route_gap_count']}`",
        f"- adapter_fixture_runtime_row_count：`{metrics['adapter_fixture_runtime_row_count']}`",
        f"- adapter_fixture_rejected_candidate_count：`{metrics['adapter_fixture_rejected_candidate_count']}`",
        f"- live_route_attempt_report_status：`{metrics['live_route_attempt_report_status']}`",
        f"- live_route_attempt_count：`{metrics['live_route_attempt_count']}`",
        f"- accepted_live_runtime_row_count：`{metrics['accepted_live_runtime_row_count']}`",
        f"- attempt_backed_typed_gap_count：`{metrics['attempt_backed_typed_gap_count']}`",
        f"- unattempted_slot_count：`{metrics.get('unattempted_slot_count', 0)}`",
        f"- all_live_gaps_attempt_backed：`{metrics.get('all_live_gaps_attempt_backed', False)}`",
        f"- allow_paid_memo_writer：`{metrics['allow_paid_memo_writer']}`",
        f"- allow_scoped_paid_memo_writer：`{metrics.get('allow_scoped_paid_memo_writer', metrics['allow_paid_memo_writer'])}`",
        f"- allow_full_chain：`{metrics['allow_full_chain']}`",
        "",
        "## 3. Judgment Chain 审计",
        "",
    ]
    for chain in report["chain_results"]:
        lines.extend(
            [
                f"### {chain['chain_id']}",
                "",
                f"- status：`{chain['fixture_answerability_status']}`",
                f"- fixture_supported_slots：`{chain['fixture_supported_slot_count']}/{chain['required_slot_count']}`",
                f"- live_supported_slots：`{chain.get('live_supported_slot_count', 0)}/{chain['required_slot_count']}`",
                f"- attempt_backed_gap_slots：`{chain.get('attempt_backed_gap_slot_count', 0)}`",
                f"- blocking_reason：{chain['blocking_reason']}",
                "",
            ]
        )
    lines.extend(
        [
            "## 4. 下一步",
            "",
            "1. 若继续，应只跑 scoped paid Memo Writer node，并强制 bounded answer：DELL 只能写收入能见度和 margin-quality 未证实，market 只能写公开 price-in context 与 commercial exact gap。",
            "2. 继续禁止 broad full-chain、模型对比、case expansion、release eval，直到 renderer / verifier / Workbench projection 与人工审稿通过。",
            "3. 后续可继续深挖 Dell AI server mix / GPU pass-through / AI server gross margin，以及 market exact positioning 的公开或商业数据边界。",
            "",
        ]
    )
    return "\n".join(lines)


if __name__ == "__main__":
    main()
