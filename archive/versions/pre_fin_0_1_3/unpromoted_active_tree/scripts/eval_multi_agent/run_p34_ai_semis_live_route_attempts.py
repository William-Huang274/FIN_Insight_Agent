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

from sec_agent.p34_lane_quality_runtime import build_ai_semis_live_route_attempt_report  # noqa: E402


DEFAULT_JSON_OUT = REPO_ROOT / "docs/project_os/p34_ai_semis_live_route_attempt_report_v0_1.json"
DEFAULT_MD_OUT = REPO_ROOT / "docs/internal/vnext_20260610/p34_ai_semis_live_route_attempt_report_v0_1.zh-CN.md"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build P34 AI/Semis live route attempt report.")
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    parser.add_argument("--md-out", default=str(DEFAULT_MD_OUT))
    parser.add_argument("--live-probe", action="store_true", help="Attempt lightweight HTTP GET probes for official routes.")
    parser.add_argument("--timeout-seconds", type=float, default=8.0)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    report = build_ai_semis_live_route_attempt_report(
        perform_network=args.live_probe,
        timeout_seconds=args.timeout_seconds,
    )
    report = {
        **report,
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "artifact_refs": {
            "json_out": _rel(Path(args.json_out)),
            "md_out": _rel(Path(args.md_out)),
        },
    }
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
    if args.strict and report["metrics"]["attempt_count"] == 0:
        raise SystemExit(1)


def _render_markdown(report: Mapping[str, Any]) -> str:
    metrics = report["metrics"]
    lines = [
        "# P34 AI/Semis Live Route Attempt Report v0.1",
        "",
        f"日期：{str(report.get('created_at') or '')[:10]}",
        "",
        f"状态：`{report['status']}`",
        "",
        "## 1. 结论",
        "",
        "本报告把 P34 的重点 evidence slots 接到真实 source route attempts 或 attempt-backed typed gaps。",
        "它不是 paid Memo Writer、full-chain 或模型对比；它只回答“哪些 source route 已尝试、哪些 row 可提权、哪些缺口有 attempt 依据”。",
        "",
        "## 2. Metrics",
        "",
        f"- attempt_count：`{metrics['attempt_count']}`",
        f"- attempted_slot_count：`{metrics['attempted_slot_count']}`",
        f"- accepted_runtime_row_count：`{metrics['accepted_runtime_row_count']}`",
        f"- accepted_slot_count：`{metrics['accepted_slot_count']}`",
        f"- typed_gap_count：`{metrics['typed_gap_count']}`",
        f"- attempt_backed_gap_slot_count：`{metrics['attempt_backed_gap_slot_count']}`",
        f"- unattempted_slot_count：`{metrics['unattempted_slot_count']}`",
        f"- network_attempt_count：`{metrics['network_attempt_count']}`",
        f"- network_ok_count：`{metrics['network_ok_count']}`",
        f"- perform_network：`{metrics['perform_network']}`",
        "",
        "## 3. Accepted Runtime Rows",
        "",
        "| Slot | Issuer | Metric | Authority |",
        "| --- | --- | --- | --- |",
    ]
    for row in report.get("accepted_runtime_rows") or []:
        lines.append(
            "| `{slot}` | `{issuer}` | `{metric}` | `{authority}` |".format(
                slot=row.get("evidence_row_id"),
                issuer=row.get("issuer"),
                metric=row.get("metric_or_attribute"),
                authority=row.get("authority_scope"),
            )
        )
    lines.extend(["", "## 4. Typed Gaps", "", "| Slot | Gap | Reason |", "| --- | --- | --- |"])
    for gap in report.get("typed_gaps") or []:
        lines.append(
            "| `{slot}` | `{gap}` | {reason} |".format(
                slot=gap.get("evidence_row_id"),
                gap=gap.get("gap_type"),
                reason=str(gap.get("reason") or "").replace("|", "/"),
            )
        )
    lines.extend(
        [
            "",
            "## 5. Boundary",
            "",
            "- Accepted rows can support P34 no-paid audit, but cannot exceed each row's `authority_scope` / `cannot_infer` boundary.",
            "- Typed gaps are useful only because they are attempt-backed; whether they block or allow a bounded scoped writer is decided by the P34 no-paid quality audit.",
            "- Market context and counter-thesis context are not fundamental facts and must not be used as revenue/margin evidence.",
            "",
        ]
    )
    return "\n".join(lines)


def _rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


if __name__ == "__main__":
    main()
