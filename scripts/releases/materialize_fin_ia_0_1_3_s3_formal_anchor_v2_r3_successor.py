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
from sec_agent.s3_research_quality_gate import (  # noqa: E402
    compile_s3_research_quality_gate_program,
    load_s3_research_quality_gate_policy,
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
    quality_program = compile_s3_research_quality_gate_program(
        policy=load_s3_research_quality_gate_policy(ROOT / "configs/runtime/fin_ia_0_1_3_repair_closeout_s3_research_quality_gate_policy_v1_0.json"),
        writer_decision=writer,
        claim_decision=claim,
    )
    quality = _decision(
        acceptance={"S3_05": "engineering_pass_formal_binding_pending"},
        program_key="research_quality_gate_program",
        program=quality_program,
    )
    return {"claim": claim, "synthesis": synthesis, "writer": writer, "quality": quality}


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
    summary = {
        "status": "successor_materialized_zero_model",
        "claim_counts": outputs["claim"]["claim_quality_program"]["observed_counts"],
        "synthesis_counts": outputs["synthesis"]["cross_cell_synthesis_program"]["observed_counts"],
        "writer_counts": outputs["writer"]["workpaper_writer_content_program"]["observed_counts"],
        "quality_counts": outputs["quality"]["research_quality_gate_program"]["observed_counts"],
        "quality_dispositions": outputs["quality"]["research_quality_gate_program"]["current_case_dispositions"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
