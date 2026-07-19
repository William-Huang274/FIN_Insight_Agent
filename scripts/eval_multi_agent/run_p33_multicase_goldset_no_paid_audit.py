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
    build_multicase_goldset_evidence_depth_packs,
    build_ai_semis_fresh_all_specialist_gold_pass,
    compile_negative_gold_failure_fixtures,
    run_multicase_goldset_no_paid_audit,
)


DEFAULT_JSON_OUT = REPO_ROOT / "docs/project_os/p33_multicase_goldset_no_paid_audit_v0_1.json"
DEFAULT_MD_OUT = REPO_ROOT / "docs/internal/vnext_20260610/p33_multicase_goldset_no_paid_audit_v0_1.zh-CN.md"
DEFAULT_EVIDENCE_DEPTH_OUT = REPO_ROOT / "docs/project_os/p33_multicase_goldset_evidence_depth_packs_v0_1.json"
DEFAULT_FRESH_SPECIALIST_OUT = REPO_ROOT / "docs/project_os/p33_ai_semis_fresh_all_specialist_gold_pass_v0_1.json"
DEFAULT_NEGATIVE_FIXTURES_OUT = REPO_ROOT / "docs/project_os/p33_negative_gold_failure_fixtures_v0_1.json"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run P33 no-paid multi-case gold-set artifact-depth audit.")
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD_OUT)
    parser.add_argument("--evidence-depth-out", type=Path, default=DEFAULT_EVIDENCE_DEPTH_OUT)
    parser.add_argument("--fresh-specialist-out", type=Path, default=DEFAULT_FRESH_SPECIALIST_OUT)
    parser.add_argument("--negative-fixtures-out", type=Path, default=DEFAULT_NEGATIVE_FIXTURES_OUT)
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    evidence_depth = build_multicase_goldset_evidence_depth_packs()
    fresh_specialist = build_ai_semis_fresh_all_specialist_gold_pass()
    negative_fixtures = compile_negative_gold_failure_fixtures()
    audit = run_multicase_goldset_no_paid_audit()
    audit = {
        **audit,
        "created_at": _utc_now(),
        "artifact_refs": {
            "json_out": _rel(args.json_out),
            "md_out": _rel(args.md_out),
            "evidence_depth_out": _rel(args.evidence_depth_out),
            "fresh_specialist_out": _rel(args.fresh_specialist_out),
            "negative_fixtures_out": _rel(args.negative_fixtures_out),
        },
    }
    _write_json(args.json_out, audit)
    _write_json(args.evidence_depth_out, evidence_depth)
    _write_json(args.fresh_specialist_out, fresh_specialist)
    _write_json(args.negative_fixtures_out, negative_fixtures)
    args.md_out.parent.mkdir(parents=True, exist_ok=True)
    args.md_out.write_text(render_markdown(audit), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": audit["status"],
                "metrics": audit["metrics"],
                "json_out": str(args.json_out.resolve()),
                "md_out": str(args.md_out.resolve()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if args.strict and audit["status"] != "pass":
        return 1
    return 0


def render_markdown(audit: Mapping[str, Any]) -> str:
    metrics = audit.get("metrics") if isinstance(audit.get("metrics"), Mapping) else {}
    compiled = audit.get("compiled_artifacts") if isinstance(audit.get("compiled_artifacts"), Mapping) else {}
    evidence_depth = (
        compiled.get("evidence_depth_packs") if isinstance(compiled.get("evidence_depth_packs"), Mapping) else {}
    )
    fresh = (
        compiled.get("ai_semis_fresh_all_specialist_gold_pass")
        if isinstance(compiled.get("ai_semis_fresh_all_specialist_gold_pass"), Mapping)
        else {}
    )
    negative = (
        compiled.get("negative_failure_fixtures")
        if isinstance(compiled.get("negative_failure_fixtures"), Mapping)
        else {}
    )
    lines: list[str] = []
    lines.append("# P33 Multi-case Gold Set No-paid Audit v0.1")
    lines.append("")
    lines.append(f"日期：{str(audit.get('created_at') or '')[:10]}")
    lines.append("")
    lines.append("## 1. 结论")
    lines.append("")
    if audit.get("status") == "pass":
        lines.append(
            "本轮完成的是 multi-case gold-set 的 no-paid artifact closeout：15 个 case 都已有可运行的 "
            "evidence-depth pack，AI/Semis deep case 有 fresh all-specialist gold pass，6 个 negative cases "
            "都有 aggregate / writer payload / final memo 的 deterministic failure fixture。"
        )
    else:
        lines.append("本轮 no-paid multi-case audit 未通过，仍不能进入 paid full-chain、模型对比或 release eval。")
    lines.append("")
    lines.append("这不是 live retrieval/parser 全覆盖，也不是 paid writer 或 human dogfood；它只关闭当前请求的 1-4 项 artifact-depth / fresh-specialist / negative-fixture / no-paid matrix audit 范围。")
    lines.append("")
    lines.append("## 2. 指标")
    lines.append("")
    for key in (
        "case_count",
        "artifact_ready_count",
        "fresh_all_specialist_pass_count",
        "negative_fixture_pass_count",
        "runtime_contract_ready_count",
        "blocking_case_count",
    ):
        lines.append(f"- `{key}`: `{metrics.get(key)}`")
    lines.append("")
    lines.append("## 3. Case Results")
    lines.append("")
    lines.append("| Case | Type | Evidence-depth | Fresh specialist | Negative fixture | Blocking |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for row in audit.get("case_results") or []:
        if not isinstance(row, Mapping):
            continue
        lines.append(
            "| `{case}` | `{case_type}` | `{evidence}` | `{fresh}` | `{negative}` | {blocking} |".format(
                case=row.get("case_id"),
                case_type=row.get("case_type"),
                evidence=row.get("evidence_depth_status"),
                fresh=row.get("fresh_all_specialist_status", ""),
                negative=row.get("negative_failure_fixture_status", ""),
                blocking=", ".join(row.get("blocking_reasons") or []) or "none",
            )
        )
    lines.append("")
    lines.append("## 4. Artifact 摘要")
    lines.append("")
    lines.append(f"- Evidence-depth packs：`{evidence_depth.get('artifact_ready_count')}/{evidence_depth.get('case_count')}` ready。")
    lines.append(f"- AI/Semis fresh all-specialist：`{fresh.get('status')}`，roles `{fresh.get('role_pass_count')}/{fresh.get('role_count')}` pass。")
    lines.append(f"- Negative failure fixtures：`{negative.get('status')}`，fixtures `{negative.get('fixture_count')}`。")
    lines.append("")
    lines.append("## 5. 边界")
    lines.append("")
    lines.append("- 未运行 paid LLM、paid specialist、paid Memo Writer、full-chain、模型对比、新检索、爬虫或 parser。")
    lines.append("- Rubric / negative case 的 evidence-depth pack 是 gold-exemplar-backed 可运行工件，不代表已经完成真实行业 source ingestion。")
    lines.append("- 下一步如果要进入真实行业 runtime，应逐 case 把这些 packs 接到 source route / parser / specialist 节点，而不是直接扩 full-chain。")
    lines.append("")
    lines.append("## 6. Artifact refs")
    lines.append("")
    for key, value in (audit.get("artifact_refs") or {}).items():
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
