from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sec_agent.financial_research_held_out_business_review import (  # noqa: E402
    execute_held_out_business_review,
    load_held_out_business_review_policy,
)


POLICY_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s1_three_held_out_"
    "business_review_policy_v1_0.json"
)
RESULT_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_3_s1_three_held_out_"
    "business_review_result_v1_0.json"
)


def main() -> int:
    if RESULT_PATH.exists():
        raise RuntimeError("held_out_business_review_output_exists")
    policy, candidate_result = load_held_out_business_review_policy(
        POLICY_PATH,
        repo_root=ROOT,
    )
    result = execute_held_out_business_review(
        policy=policy,
        candidate_result=candidate_result,
        repo_root=ROOT,
    )
    if result["status"] != (
        "held_out_generalization_blocked_before_index_rebuild"
    ):
        raise RuntimeError("held_out_business_review_status_unexpected")
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "result_digest": result["result_digest"],
                "case_summaries": [
                    {
                        "case_key": row["case_key"],
                        "lane_verdict_counts": row["lane_verdict_counts"],
                        "useful_candidate_refs": row[
                            "reviewed_useful_candidate_ref_count"
                        ],
                        "mutation_outcome_counts": row[
                            "mutation_outcome_counts"
                        ],
                        "rebuild_admitted": row[
                            "sparse_dense_rebuild_admitted"
                        ],
                    }
                    for row in result["case_summaries"]
                ],
                "rebuild_blocker_codes": result["rebuild_blocker_codes"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
