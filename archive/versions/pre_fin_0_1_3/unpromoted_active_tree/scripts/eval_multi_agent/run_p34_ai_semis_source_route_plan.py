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

from sec_agent.p34_lane_quality_runtime import build_ai_semis_source_route_plan  # noqa: E402


DEFAULT_JSON_OUT = REPO_ROOT / "docs/project_os/p34_ai_semis_source_route_plan_v0_1.json"
DEFAULT_MD_OUT = REPO_ROOT / "docs/internal/vnext_20260610/p34_ai_semis_source_route_plan_v0_1.zh-CN.md"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build P34 AI/Semis source route plan.")
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD_OUT)
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_ai_semis_source_route_plan()
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
    if args.strict and (
        payload["metrics"]["slot_count"] != 20
        or payload["metrics"]["slot_with_primary_route_count"] != 20
        or payload["metrics"]["slot_with_fallback_route_count"] != 20
        or payload["metrics"]["route_gap_count"] != 0
    ):
        return 1
    return 0


def render_markdown(payload: Mapping[str, Any]) -> str:
    metrics = payload.get("metrics") if isinstance(payload.get("metrics"), Mapping) else {}
    lines: list[str] = []
    lines.append("# P34 AI/Semis Source Route Plan v0.1")
    lines.append("")
    lines.append(f"日期：{str(payload.get('created_at') or '')[:10]}")
    lines.append("")
    lines.append("## 1. 结论")
    lines.append("")
    lines.append(
        "本轮把 P34 的 20 个 AI/Semis evidence slots 转成 source route plan。"
        "它只是 route/parser 执行前的机器可读计划，不代表已经完成 live source、爬虫、parser 或 runtime row 提权。"
    )
    lines.append("")
    lines.append(f"当前状态：`{payload.get('status')}`。")
    lines.append("")
    lines.append("## 2. Metrics")
    lines.append("")
    for key in (
        "slot_count",
        "route_count",
        "primary_route_count",
        "fallback_route_count",
        "slot_with_primary_route_count",
        "slot_with_fallback_route_count",
        "route_gap_count",
        "adapter_family_count",
    ):
        lines.append(f"- `{key}`: `{metrics.get(key)}`")
    lines.append("")
    lines.append("## 3. Adapter Family Counts")
    lines.append("")
    for family, count in sorted((payload.get("adapter_family_counts") or {}).items()):
        lines.append(f"- `{family}`: `{count}`")
    lines.append("")
    lines.append("## 4. Slots")
    lines.append("")
    lines.append("| Slot | Status | Primary route | Fallback routes |")
    lines.append("| --- | --- | --- | --- |")
    for slot in payload.get("slots") or []:
        if not isinstance(slot, Mapping):
            continue
        fallback = ", ".join(str(item) for item in slot.get("fallback_route_ids") or [])
        lines.append(
            "| `{slot}` | `{status}` | `{primary}` | {fallback} |".format(
                slot=slot.get("evidence_row_id"),
                status=slot.get("route_plan_status"),
                primary=slot.get("primary_route_id"),
                fallback=fallback or "-",
            )
        )
    lines.append("")
    lines.append("## 5. 当前边界")
    lines.append("")
    lines.append("- 没有运行 paid LLM。")
    lines.append("- 没有运行 full-chain。")
    lines.append("- 没有运行新爬虫或 parser。")
    lines.append("- `route_plan_ready` 不等于 `live_runtime_ready`。")
    lines.append("- weak candidate 仍不能进入正式 evidence bundle。")
    lines.append("")
    lines.append("## 6. 下一步")
    lines.append("")
    lines.append(str(payload.get("next_step") or ""))
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
