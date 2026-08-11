from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from scripts.releases.run_fin_ia_0_1_3_s1_08_tencent_wsa_query_only_replacement_diagnostic import (  # noqa: E402
    _write_json_atomic,
)
from sec_agent.s1_08_firecrawl_semantic_control import load_plan  # noqa: E402
from sec_agent.s1_08_tencent_relationship_aware_semantic_comparator import (  # noqa: E402
    evaluate_comparator,
    load_scoring_contract,
)


DEFAULT_RESULT = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_tencent_relationship_aware_semantic_comparator_result_v1_0.json"
DEFAULT_CONTROL_PLAN = ROOT / "configs/runtime/fin_ia_0_1_3_s1_08_firecrawl_relationship_aware_semantic_control_plan_v1_0.json"
DEFAULT_SCORING = ROOT / "configs/eval/fin_ia_0_1_3_s1_08_tencent_relationship_aware_semantic_comparator_scoring_v1_0.json"
DEFAULT_VISIBLE = ROOT / "eval_sets/fin_0_1_3_same_evidence_v1/model_visible/shared_benchmark_evidence_pack_v1.json"
DEFAULT_FIRECRAWL_ASSESSMENT = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_firecrawl_relationship_aware_semantic_control_assessment_v1_0.json"
DEFAULT_OUTPUT = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_tencent_relationship_aware_semantic_comparator_assessment_v1_0.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--control-plan", type=Path, default=DEFAULT_CONTROL_PLAN)
    parser.add_argument("--scoring", type=Path, default=DEFAULT_SCORING)
    parser.add_argument("--visible-pack", type=Path, default=DEFAULT_VISIBLE)
    parser.add_argument(
        "--firecrawl-assessment", type=Path, default=DEFAULT_FIRECRAWL_ASSESSMENT
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    assessment = evaluate_comparator(
        result=_load(args.result),
        control_plan=load_plan(args.control_plan),
        scoring_contract=load_scoring_contract(args.scoring),
        visible_pack=_load(args.visible_pack),
        firecrawl_assessment=_load(args.firecrawl_assessment),
    )
    _write_json_atomic(args.output, assessment)
    print(
        json.dumps(
            {
                "status": assessment["status"],
                "aggregate": assessment["aggregate"],
                "hard_gate_results": assessment["hard_gate_results"],
                "decision": assessment["decision"],
                "assessment_digest": assessment["assessment_digest"],
            },
            ensure_ascii=True,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
