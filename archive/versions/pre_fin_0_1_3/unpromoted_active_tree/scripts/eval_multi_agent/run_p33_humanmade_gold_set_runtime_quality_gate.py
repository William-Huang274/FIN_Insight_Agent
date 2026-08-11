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
    DEFAULT_ARTIFACT_AUDIT_PATH,
    DEFAULT_MATRIX_AUDIT_PATH,
    HUMANMADE_GOLD_SET_AUDIT_SCHEMA_VERSION,
    assimilate_ai_semis_gold_depth_content_pack,
    run_humanmade_gold_set_audit,
)


DEFAULT_AGGREGATE_NODE = (
    REPO_ROOT
    / "eval/sec_cases/outputs/p33_gold_case_runs"
    / "p33_stepwise_aggregate_judgment_plan_after_required_item_gate_hardening_20260705_r7"
    / "p33_3_ai_semis_accelerator_dell_gold_case_v0_1"
    / "aggregate_judgment_plan_node_result.json"
)
DEFAULT_WRITER_PAYLOAD = (
    REPO_ROOT
    / "eval/sec_cases/outputs/p33_gold_case_runs"
    / "p33_stepwise_memo_writer_payload_preflight_source_coverage_hardening_20260706_r1"
    / "p33_3_ai_semis_accelerator_dell_gold_case_v0_1"
    / "memo_writer_payload_preflight_summary.json"
)
DEFAULT_JSON_OUT = REPO_ROOT / "docs/project_os/humanmade_gold_set_runtime_quality_gate_v0_1.json"
DEFAULT_MD_OUT = REPO_ROOT / "docs/internal/vnext_20260610/p33_humanmade_gold_set_runtime_quality_gate_v0_1.zh-CN.md"
DEFAULT_SLOTS_OUT = REPO_ROOT / "docs/project_os/ai_semis_human_source_runtime_slots_v0_1.json"
DEFAULT_CONTENT_PACK_OUT = REPO_ROOT / "docs/project_os/ai_semis_gold_depth_content_pack_v0_1.json"
DEFAULT_ASSIMILATED_AGGREGATE_OUT = REPO_ROOT / "docs/project_os/ai_semis_gold_depth_assimilated_aggregate_v0_1.json"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run no-paid P33 HumanmadeGoldSetAudit / BriefingPackQualityGate against current artifacts."
    )
    parser.add_argument("--aggregate-node-result", type=Path, default=DEFAULT_AGGREGATE_NODE)
    parser.add_argument("--writer-payload", type=Path, default=DEFAULT_WRITER_PAYLOAD)
    parser.add_argument("--artifact-audit", type=Path, default=DEFAULT_ARTIFACT_AUDIT_PATH)
    parser.add_argument("--matrix-audit", type=Path, default=DEFAULT_MATRIX_AUDIT_PATH)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD_OUT)
    parser.add_argument("--slots-out", type=Path, default=DEFAULT_SLOTS_OUT)
    parser.add_argument("--content-pack-out", type=Path, default=DEFAULT_CONTENT_PACK_OUT)
    parser.add_argument("--assimilated-aggregate-out", type=Path, default=DEFAULT_ASSIMILATED_AGGREGATE_OUT)
    parser.add_argument(
        "--assimilate-gold-depth-content",
        action="store_true",
        help="Write and audit a repaired aggregate checkpoint that consumes the AI/Semis gold-depth content pack.",
    )
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    aggregate_state = _read_json(args.aggregate_node_result)
    writer_payload = _read_json(args.writer_payload) if args.writer_payload.exists() else {}
    artifact_audit = _read_json(args.artifact_audit)
    matrix_audit = _read_json(args.matrix_audit)
    if args.assimilate_gold_depth_content:
        aggregate_state = assimilate_ai_semis_gold_depth_content_pack(aggregate_state)
    audit = run_humanmade_gold_set_audit(
        aggregate_state=aggregate_state,
        writer_payload=writer_payload,
        artifact_audit=artifact_audit,
        matrix_audit=matrix_audit,
    )
    audit = {
        **audit,
        "created_at": _utc_now(),
        "artifact_refs": {
            "aggregate_node_result": _rel(args.aggregate_node_result),
            "writer_payload": _rel(args.writer_payload),
            "artifact_audit": _rel(args.artifact_audit),
            "matrix_audit": _rel(args.matrix_audit),
            "json_out": _rel(args.json_out),
            "md_out": _rel(args.md_out),
            "slots_out": _rel(args.slots_out),
            "content_pack_out": _rel(args.content_pack_out),
            "assimilated_aggregate_out": _rel(args.assimilated_aggregate_out)
            if args.assimilate_gold_depth_content
            else "",
        },
    }
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.md_out.parent.mkdir(parents=True, exist_ok=True)
    args.slots_out.parent.mkdir(parents=True, exist_ok=True)
    args.content_pack_out.parent.mkdir(parents=True, exist_ok=True)
    args.assimilated_aggregate_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.slots_out.write_text(
        json.dumps(audit["compiled_artifacts"]["source_runtime_slots"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    args.content_pack_out.write_text(
        json.dumps(audit["compiled_artifacts"]["ai_semis_gold_depth_content_pack"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if args.assimilate_gold_depth_content:
        args.assimilated_aggregate_out.write_text(
            json.dumps(aggregate_state, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    args.md_out.write_text(render_markdown(audit), encoding="utf-8")
    stdout = {
        "schema_version": HUMANMADE_GOLD_SET_AUDIT_SCHEMA_VERSION,
        "status": audit["status"],
        "allow_paid_memo_writer": audit["pre_writer_decision"]["allow_paid_memo_writer"],
        "briefing_pack_quality_gate": {
            "status": audit["briefing_pack_quality_gate"]["status"],
            "fail_count": audit["briefing_pack_quality_gate"]["fail_count"],
        },
        "negative_failure_gates": {
            "status": audit["negative_failure_gate_results"]["status"],
            "fail_count": audit["negative_failure_gate_results"]["fail_count"],
            "pending_final_memo_count": audit["negative_failure_gate_results"]["pending_final_memo_count"],
        },
        "json_out": str(args.json_out.resolve()),
        "md_out": str(args.md_out.resolve()),
        "content_pack_out": str(args.content_pack_out.resolve()),
        "assimilated_aggregate_out": str(args.assimilated_aggregate_out.resolve())
        if args.assimilate_gold_depth_content
        else "",
    }
    print(json.dumps(stdout, ensure_ascii=False, indent=2))
    if args.strict and audit["status"] != "pass":
        return 1
    return 0


def render_markdown(audit: Mapping[str, Any]) -> str:
    briefing = audit.get("briefing_pack_quality_gate") if isinstance(audit.get("briefing_pack_quality_gate"), Mapping) else {}
    negative = audit.get("negative_failure_gate_results") if isinstance(audit.get("negative_failure_gate_results"), Mapping) else {}
    compiled = audit.get("compiled_artifacts") if isinstance(audit.get("compiled_artifacts"), Mapping) else {}
    source_slots = compiled.get("source_runtime_slots") if isinstance(compiled.get("source_runtime_slots"), Mapping) else {}
    rubric_contracts = compiled.get("rubric_vertical_playbook_contracts") if isinstance(compiled.get("rubric_vertical_playbook_contracts"), Mapping) else {}
    negative_gates = compiled.get("negative_failure_gates") if isinstance(compiled.get("negative_failure_gates"), Mapping) else {}
    content_pack = compiled.get("ai_semis_gold_depth_content_pack") if isinstance(compiled.get("ai_semis_gold_depth_content_pack"), Mapping) else {}
    row_pack = content_pack.get("human_source_runtime_rows") if isinstance(content_pack.get("human_source_runtime_rows"), Mapping) else {}
    edge_pack = content_pack.get("product_intelligence_graph_projection") if isinstance(content_pack.get("product_intelligence_graph_projection"), Mapping) else {}
    material_pack = content_pack.get("specialist_judgment_materials") if isinstance(content_pack.get("specialist_judgment_materials"), Mapping) else {}
    lead_veto = audit.get("research_lead_gold_depth_veto") if isinstance(audit.get("research_lead_gold_depth_veto"), Mapping) else {}
    artifact_refs = audit.get("artifact_refs") if isinstance(audit.get("artifact_refs"), Mapping) else {}
    is_assimilated_checkpoint = bool(str(artifact_refs.get("assimilated_aggregate_out") or ""))
    lines: list[str] = []
    lines.append("# P33 Humanmade Gold Set Runtime Quality Gate v0.1")
    lines.append("")
    lines.append(f"日期：{str(audit.get('created_at') or '')[:10]}")
    lines.append("")
    lines.append("## 1. 结论")
    lines.append("")
    if audit.get("status") == "pass":
        if is_assimilated_checkpoint:
            lines.append(
                "`HumanmadeGoldSetAudit` 对 gold-depth runtime assimilation checkpoint 为 `pass`。"
                "这证明 human source ledger / ProductIntelligenceGraph / specialist judgment material / "
                "MemoLogicPlan 已被当前修复 checkpoint 消费；不等于原始 accepted r7 artifact 已通过，"
                "也不等于 full-chain、模型对比或扩 case 可以启动。"
            )
            lines.append("")
            lines.append(
                "下一步最多只能在用户批准后跑一个 scoped paid Memo Writer node，用这个 assimilated checkpoint "
                "验证 prose / renderer / verifier 质量；当前仍未跑 paid LLM。"
            )
        else:
            lines.append(
                "`HumanmadeGoldSetAudit` 对输入 artifact 为 `pass`；这只允许进入 scoped Memo Writer 节点级验证，"
                "不允许 broad full-chain、模型对比或 case expansion。"
            )
    else:
        lines.append("`HumanmadeGoldSetAudit` 当前为 `fail`，必须阻断 paid Memo Writer、full-chain、模型对比和扩 case。")
    lines.append("")
    lines.append(f"- AI/Semis human source runtime slots：`{source_slots.get('slot_count')}`。")
    lines.append(f"- AI/Semis gold-depth content rows：`{row_pack.get('row_count')}`。")
    lines.append(f"- ProductIntelligenceGraph investment edges：`{edge_pack.get('edge_count')}`。")
    lines.append(f"- Specialist judgment materials：`{material_pack.get('material_count')}`。")
    lines.append(f"- Rubric vertical playbook contracts：`{rubric_contracts.get('contract_count')}`。")
    lines.append(f"- Negative deterministic failure gates：`{negative_gates.get('gate_count')}`。")
    lines.append(f"- BriefingPackQualityGate：`{briefing.get('status')}`，fail count `{briefing.get('fail_count')}`。")
    lines.append(f"- ResearchLead gold-depth veto：`{lead_veto.get('status')}`，writer allowed `{lead_veto.get('writer_allowed')}`。")
    lines.append(f"- Negative gates：`{negative.get('status')}`，fail count `{negative.get('fail_count')}`，pending final memo `{negative.get('pending_final_memo_count')}`。")
    lines.append("")
    lines.append("## 2. BriefingPackQualityGate 明细")
    lines.append("")
    lines.append("| Lane | Status | Finding |")
    lines.append("| --- | --- | --- |")
    for row in briefing.get("checks") or []:
        if isinstance(row, Mapping):
            lines.append(f"| `{row.get('lane_id')}` | `{row.get('status')}` | {row.get('finding')} |")
    lines.append("")
    lines.append("## 3. Negative Failure Gates")
    lines.append("")
    lines.append("| Gate | Status | Finding |")
    lines.append("| --- | --- | --- |")
    for row in negative.get("results") or []:
        if isinstance(row, Mapping):
            lines.append(f"| `{row.get('case_id')}` | `{row.get('status')}` | {row.get('finding')} |")
    lines.append("")
    lines.append("## 4. Content Pack 摘要")
    lines.append("")
    lines.append("这些 rows / edges / materials 是 human source ledger 已经编译出的目标内容形态；只有当前 runtime artifact 真正消费它们，`BriefingPackQualityGate` 才能通过。")
    lines.append("")
    lines.append(f"- Row lane counts：`{json.dumps(row_pack.get('lane_counts') or {}, ensure_ascii=False)}`")
    lines.append(f"- Edge role counts：`{json.dumps(edge_pack.get('edge_role_counts') or {}, ensure_ascii=False)}`")
    lines.append(f"- Specialist memo slots：`{json.dumps(material_pack.get('memo_slot_counts') or {}, ensure_ascii=False)}`")
    if lead_veto.get("targeted_repairs"):
        lines.append("- ResearchLead veto repair actions:")
        for repair in lead_veto.get("targeted_repairs") or []:
            if isinstance(repair, Mapping):
                lines.append(f"  - `{repair.get('lane_id')}`: {repair.get('repair_action')}")
    lines.append("")
    lines.append("## 5. 当前允许/禁止")
    lines.append("")
    if audit.get("status") == "pass" and is_assimilated_checkpoint:
        lines.append("- 允许：继续 deterministic/node-level repair；在用户明确批准后，可用 `assimilated_aggregate_out` 跑一个 scoped paid Memo Writer node。")
        lines.append("- 禁止：broad full-chain、模型对比、case expansion、release eval；禁止把该 pass 记为 accepted gold workpaper。")
        lines.append("- 注意：原始 accepted r7 artifact 仍应保留 fail 基线；本报告证明的是修复 checkpoint 的 runtime consumption。")
    elif audit.get("status") == "pass":
        lines.append("- 允许：继续 deterministic/node-level repair；在用户明确批准后，可跑一个 scoped paid Memo Writer node。")
        lines.append("- 禁止：broad full-chain、模型对比、case expansion、release eval；禁止把该 pass 记为 accepted gold workpaper。")
    else:
        lines.append("- 允许：deterministic/node-level repair、source runtime ingestion fixture、PIG projection fixture、specialist contract fixture。")
        lines.append("- 禁止：paid Memo Writer、full-chain、模型对比、case expansion，直到 `BriefingPackQualityGate` 和 `HumanmadeGoldSetAudit` 真正 pass。")
    lines.append("")
    lines.append("## 6. Artifact refs")
    lines.append("")
    for key, value in (audit.get("artifact_refs") or {}).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.append("")
    return "\n".join(lines)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _rel(path: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
