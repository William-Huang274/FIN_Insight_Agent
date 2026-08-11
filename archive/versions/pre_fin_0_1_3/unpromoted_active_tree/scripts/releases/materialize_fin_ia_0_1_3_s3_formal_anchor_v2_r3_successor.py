from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
for value in (ROOT, ROOT / "src"):
    if str(value) not in sys.path:
        sys.path.insert(0, str(value))

from sec_agent.retrieval_evidence_usefulness_program import canonical_digest  # noqa: E402
from sec_agent.s3_claim_quality_program import (  # noqa: E402
    compile_s3_claim_quality_all_natural_successor,
    load_s3_claim_quality_policy,
)
from sec_agent.s3_cross_cell_synthesis_program import (  # noqa: E402
    compile_s3_cross_cell_synthesis_program,
    load_s3_cross_cell_policy,
)
from sec_agent.s3_final_delivery_binding import (  # noqa: E402
    compile_s3_final_delivery_binding,
)
from sec_agent.s3_research_quality_gate import (  # noqa: E402
    compile_s3_research_quality_gate_program,
    load_s3_research_quality_gate_policy,
)
from sec_agent.s3_paired_review_packet import (  # noqa: E402
    compile_s3_paired_review_packet,
)
from sec_agent.s3_workpaper_writer_content_program import (  # noqa: E402
    compile_s3_workpaper_writer_content_program,
    load_s3_workpaper_writer_content_policy,
)


def _load(ref: str | Path) -> dict[str, Any]:
    path = Path(ref)
    if not path.is_absolute():
        path = ROOT / path
    return json.loads(path.read_text(encoding="utf-8"))


def _decision(*, acceptance: dict[str, Any], program_key: str, program: dict[str, Any]) -> dict[str, Any]:
    body = {"acceptance": acceptance, program_key: program}
    return {**body, "record_digest": canonical_digest(body)}


def compile_successor(formal_result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    claim_program = compile_s3_claim_quality_all_natural_successor(
        policy=load_s3_claim_quality_policy(ROOT / "configs/runtime/fin_ia_0_1_3_repair_closeout_s3_claim_and_observable_wwc_policy_v1_0.json"),
        s1_decision=_load("configs/releases/fin_ia_0_1_3_repair_closeout_s1_05_retrieval_evidence_usefulness_and_s1_closeout_v1_0.json"),
        s2_decision=_load("configs/releases/fin_ia_0_1_3_repair_closeout_s2_01_research_question_method_contract_translation_v1_0.json"),
        representative_decision=_load("configs/releases/fin_ia_0_1_3_repair_closeout_s2_02_representative_node_context_precedence_and_canary_entry_v1_0.json"),
        s3_surface_decision=_load("configs/releases/fin_ia_0_1_3_repair_closeout_s3_01_dynamic_decision_surface_v1_0.json"),
        natural_s2_result=_load("configs/releases/fin_ia_0_1_3_repair_closeout_s2_02_three_family_natural_canary_result_v1_0.json"),
        natural_s2_03_result=_load("configs/releases/fin_ia_0_1_3_repair_closeout_s2_03_context_yield_natural_reproof_result_v1_0.json"),
        formal_anchor_result=formal_result,
    )
    claim = _decision(
        acceptance={"S3_02": "engineering_pass", "authority": "all_natural_exact_once"},
        program_key="claim_quality_program",
        program=claim_program,
    )
    synthesis_program = compile_s3_cross_cell_synthesis_program(
        policy=load_s3_cross_cell_policy(ROOT / "configs/runtime/fin_ia_0_1_3_repair_closeout_s3_cross_cell_synthesis_policy_v1_0.json"),
        claim_decision=claim,
    )
    synthesis = _decision(
        acceptance={"S3_03": "engineering_pass", "authority": "all_natural_candidate"},
        program_key="cross_cell_synthesis_program",
        program=synthesis_program,
    )
    writer_program = compile_s3_workpaper_writer_content_program(
        policy=load_s3_workpaper_writer_content_policy(ROOT / "configs/runtime/fin_ia_0_1_3_repair_closeout_s3_workpaper_writer_content_policy_v1_0.json"),
        claim_decision=claim,
        synthesis_decision=synthesis,
    )
    writer = _decision(
        acceptance={"S3_04": "engineering_pass", "authority": "all_natural_candidate"},
        program_key="workpaper_writer_content_program",
        program=writer_program,
    )
    quality_policy = load_s3_research_quality_gate_policy(
        ROOT / "configs/runtime/fin_ia_0_1_3_repair_closeout_s3_research_quality_gate_policy_v1_0.json"
    )
    quality_program = compile_s3_research_quality_gate_program(
        policy=quality_policy,
        writer_decision=writer,
        claim_decision=claim,
    )
    quality = _decision(
        acceptance={"S3_05": "engineering_pass_formal_binding_pending"},
        program_key="research_quality_gate_program",
        program=quality_program,
    )
    binding_program = compile_s3_final_delivery_binding(
        claim_decision=claim,
        writer_decision=writer,
        quality_decision=quality,
        s1_decision=_load("configs/releases/fin_ia_0_1_3_repair_closeout_s1_05_retrieval_evidence_usefulness_and_s1_closeout_v1_0.json"),
        formal_result=formal_result,
    )
    binding = _decision(
        acceptance={"S3_final_binding": "engineering_pass"},
        program_key="final_delivery_binding_program",
        program=binding_program,
    )
    paired_program = compile_s3_paired_review_packet(
        binding_decision=binding,
        claim_decision=claim,
        writer_decision=writer,
        quality_policy=quality_policy,
    )
    paired = _decision(
        acceptance={"S3_paired_review_packet": "prepared_unscored"},
        program_key="paired_review_packet_program",
        program=paired_program,
    )
    return {
        "claim": claim,
        "synthesis": synthesis,
        "writer": writer,
        "quality": quality,
        "binding": binding,
        "paired_review": paired,
    }


def _render_review_markdown(paired: dict[str, Any]) -> str:
    lines = [
        "# FIN 0.1.3 S3 R3 三案 paired review packet",
        "",
        "> 本材料尚未评分。baseline 与 Agent 使用同一批 R3 Claim/Evidence；baseline 仅逐 Claim 展示，Agent 增加跨 Cell 综合与 8-lens Workpaper。",
        "",
        "评分范围：每维 0–4；正式通过要求总分 >=24，Q1/Q2/Q3/Q8 >=3，Q1–Q7 >=2，且至少四维 >=3。",
        "",
    ]
    program = paired["paired_review_packet_program"]
    for packet in program["case_packets"]:
        lines.extend([f"## {packet['case_key']}", "", "### Claim-only baseline", ""])
        for claim in packet["baseline"]["delivery"]["claim_cards"]:
            lines.extend(
                [
                    f"- **{claim['program_cell_id']}**（`{claim['claim_card_id']}`）：{claim['mechanism_atom']}",
                    f"  - epistemic：`{claim['epistemic_state']}` / `{claim['answer_direction']}`",
                    f"  - evidence boundary：{'；'.join(claim['evidence_boundary']) or '无'}",
                ]
            )
            if claim["numeric_facts"]:
                lines.append("  - Numeric：")
                for fact in claim["numeric_facts"]:
                    lines.append(
                        "    - "
                        f"`{fact['candidate_id']}`：{fact['metric_family']}="
                        f"{fact['normalized_value']} {fact['unit']}，published_at={fact['published_at']}"
                    )
            else:
                lines.append("  - Numeric：无")
            if claim["typed_gaps"]:
                lines.append("  - typed gaps：")
                for gap in claim["typed_gaps"]:
                    lines.append(
                        f"    - `{gap['alias']}` / `{gap['gap_code']}`：{gap['cannot_infer']}"
                    )
            else:
                lines.append("  - typed gaps：无")
            if claim["what_would_change"]:
                lines.append("  - What-Would-Change：")
                for wwc in claim["what_would_change"]:
                    lines.append(
                        "    - "
                        f"`{wwc['alias']}`：{wwc['metric_or_event']} → {wwc['direction']}；"
                        f"窗口={wwc['time_window']}；阈值={wwc['threshold']}；"
                        f"下一路线={wwc['next_evidence_route']}"
                    )
            else:
                lines.append("  - What-Would-Change：无")
        lines.extend(["", "### Agent Workpaper", ""])
        for section in packet["agent"]["workpaper"]["sections"]:
            answers = section["answers"]
            lines.extend(
                [
                    f"#### {section['lens_id']}",
                    "",
                    f"- 结论：{answers['conclusion']}",
                    f"- 为什么：{answers['why']}",
                    f"- 最强反方：{answers['opposing_view']}",
                    f"- 缺失证据：{answers['missing_evidence']}",
                    f"- 什么会改变：{answers['what_would_change']}",
                    f"- Claim refs：{', '.join(f'`{value}`' for value in section['claim_card_ids'])}",
                    "",
                ]
            )
        lines.extend(["### 本案允许的评分理由引用", ""])
        allowed_refs = packet["agent"]["sealed_candidate_context"]["allowed_reason_refs"]
        for ref_type in ("claim", "evidence", "numeric", "section", "wwc"):
            lines.append(
                f"- {ref_type}："
                + (", ".join(f"`{value}`" for value in allowed_refs[ref_type]) or "无")
            )
        lines.extend(
            [
                "### 八维评分表（待 qualified reviewer 填写）",
                "",
                "| 维度 | Baseline 0–4 | Agent 0–4 | 实质增益？ | 理由与引用 |",
                "|---|---:|---:|---|---|",
            ]
        )
        for row in packet["dimension_review_rows"]:
            lines.append(f"| {row['dimension_id']} {row['name']} |  |  |  |  |")
        lines.extend(["", "已知质量 finding：" + "；".join(packet["known_quality_findings"]), ""])
    lines.extend(
        [
            "## Reviewer 决策区",
            "",
            "- [ ] 三案分别达到绝对阈值；",
            "- [ ] 每案至少三个维度存在 reviewer-confirmed material gain；",
            "- [ ] 接受内容 / 退回研究修复；",
            "- Reviewer identity / authenticated session digest / reason refs：待填写。",
            "",
            "Codex/自动化不得勾选或代签以上项目。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Materialize the zero-model successor of a successful FIN 0.1.3 S3 formal Anchor v2 run.")
    parser.add_argument("--formal-result", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    outputs = compile_successor(_load(args.formal_result))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, value in outputs.items():
        (args.output_dir / f"{name}.json").write_text(
            json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    (args.output_dir / "paired_review_packet.md").write_text(
        _render_review_markdown(outputs["paired_review"]), encoding="utf-8"
    )
    summary = {
        "status": "successor_materialized_zero_model",
        "claim_counts": outputs["claim"]["claim_quality_program"]["observed_counts"],
        "synthesis_counts": outputs["synthesis"]["cross_cell_synthesis_program"]["observed_counts"],
        "writer_counts": outputs["writer"]["workpaper_writer_content_program"]["observed_counts"],
        "quality_counts": outputs["quality"]["research_quality_gate_program"]["observed_counts"],
        "quality_dispositions": outputs["quality"]["research_quality_gate_program"]["current_case_dispositions"],
        "binding_counts": outputs["binding"]["final_delivery_binding_program"]["observed_counts"],
        "paired_review_counts": outputs["paired_review"]["paired_review_packet_program"]["observed_counts"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
