from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from scripts.releases.run_fin_ia_0_1_3_s1_08_tencent_wsa_query_only_replacement_diagnostic import (
    _write_json_atomic,
)
from sec_agent.s1_08_tencent_wsa_bilingual_evidence_slot_comparator import (
    evaluate_comparator,
    load_query_plan,
    load_scoring_contract,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", required=True)
    parser.add_argument("--query-plan", required=True)
    parser.add_argument("--scoring-contract", required=True)
    parser.add_argument("--visible-pack", required=True)
    parser.add_argument("--hidden-scoring", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = json.loads(Path(args.result).read_text(encoding="utf-8"))
    query_plan = load_query_plan(args.query_plan)
    scoring_contract = load_scoring_contract(args.scoring_contract)
    visible_pack = json.loads(Path(args.visible_pack).read_text(encoding="utf-8"))
    hidden_scoring = json.loads(Path(args.hidden_scoring).read_text(encoding="utf-8"))
    assessment = evaluate_comparator(
        result=result,
        query_plan=query_plan,
        scoring_contract=scoring_contract,
        visible_pack=visible_pack,
        hidden_scoring=hidden_scoring,
    )
    _write_json_atomic(Path(args.output), assessment)
    print(
        json.dumps(
            {
                "status": assessment["status"],
                "sourcehunter_integration_eligible": assessment[
                    "sourcehunter_integration_eligible"
                ],
                "target_in_pool_rate": assessment["aggregate"][
                    "case_slot_target_in_pool_rate_across_language_union"
                ],
                "documented_total_cost_cny": assessment["aggregate"][
                    "documented_total_cost_cny"
                ],
                "latency_ms": assessment["aggregate"]["latency_ms"],
            },
            ensure_ascii=True,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
