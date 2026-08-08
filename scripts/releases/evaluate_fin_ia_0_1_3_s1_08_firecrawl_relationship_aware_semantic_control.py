from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from scripts.releases.run_fin_ia_0_1_3_s1_08_firecrawl_relationship_aware_semantic_control import (  # noqa: E402
    _atomic_write_json,
)
from sec_agent.s1_08_firecrawl_semantic_control import (  # noqa: E402
    evaluate_semantic_control,
    load_plan,
    load_scoring_contract,
)


DEFAULT_RESULT = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_firecrawl_relationship_aware_semantic_control_result_v1_0.json"
DEFAULT_PLAN = ROOT / "configs/runtime/fin_ia_0_1_3_s1_08_firecrawl_relationship_aware_semantic_control_plan_v1_0.json"
DEFAULT_SCORING = ROOT / "configs/eval/fin_ia_0_1_3_s1_08_firecrawl_relationship_aware_semantic_control_scoring_v1_0.json"
DEFAULT_VISIBLE = ROOT / "eval_sets/fin_0_1_3_same_evidence_v1/model_visible/shared_benchmark_evidence_pack_v1.json"
DEFAULT_OUTPUT = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_firecrawl_relationship_aware_semantic_control_assessment_v1_0.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--scoring", type=Path, default=DEFAULT_SCORING)
    parser.add_argument("--visible-pack", type=Path, default=DEFAULT_VISIBLE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    # Terminal truth is validated before any target/source registry is loaded.
    result = json.loads(args.result.read_text(encoding="utf-8"))
    if int((result.get("observed_counts") or {}).get("terminalized_queries") or 0) != 24:
        raise RuntimeError("firecrawl_semantic_gold_load_before_terminal_forbidden")
    plan = load_plan(args.plan)

    # Evaluator-only inputs are intentionally loaded only after terminalization.
    scoring = load_scoring_contract(args.scoring)
    visible = json.loads(args.visible_pack.read_text(encoding="utf-8"))
    assessment = evaluate_semantic_control(
        result=result,
        plan=plan,
        scoring_contract=scoring,
        visible_pack=visible,
    )
    _atomic_write_json(args.output, assessment)
    print(
        json.dumps(
            {
                "status": assessment["status"],
                "semantic_control_lane_qualified": assessment[
                    "semantic_control_lane_qualified"
                ],
                "target_in_pool": assessment["aggregate"][
                    "case_slot_target_in_pool"
                ],
                "topical_useful": [
                    assessment["aggregate"]["topical_useful_count"],
                    assessment["aggregate"]["topical_useful_denominator"],
                ],
                "credits_used": assessment["aggregate"]["credits_used"],
                "latency_ms": assessment["aggregate"]["latency_ms"],
            },
            ensure_ascii=True,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
