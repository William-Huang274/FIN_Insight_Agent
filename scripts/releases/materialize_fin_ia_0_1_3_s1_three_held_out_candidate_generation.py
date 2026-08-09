from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sec_agent.financial_research_held_out_candidate_generation import (  # noqa: E402
    execute_held_out_candidate_generation,
    load_held_out_candidate_generation_policy,
)


POLICY_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s1_three_held_out_"
    "candidate_generation_policy_v1_0.json"
)
RESULT_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_3_s1_three_held_out_"
    "candidate_generation_result_v1_0.json"
)


def main() -> int:
    if RESULT_PATH.exists():
        raise RuntimeError("held_out_candidate_generation_output_exists")
    policy, selection, extended_contract = (
        load_held_out_candidate_generation_policy(
            POLICY_PATH,
            repo_root=ROOT,
        )
    )
    result = execute_held_out_candidate_generation(
        policy=policy,
        selection=selection,
        extended_contract=extended_contract,
        repo_root=ROOT,
    )
    if result["status"] != (
        "gold_blind_candidate_generation_complete_review_required"
    ):
        raise RuntimeError("held_out_candidate_generation_acceptance_failed")
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
                "cases": [
                    {
                        "case_key": row["case_key"],
                        "candidate_rows": row["observed_counts"][
                            "candidate_rows"
                        ],
                        "unique_candidate_refs": row["observed_counts"][
                            "unique_candidate_refs"
                        ],
                        "currentness": row["source_currentness_status"],
                        "zero_candidate_required_slots": row[
                            "zero_candidate_required_slots"
                        ],
                    }
                    for row in result["case_results"]
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
