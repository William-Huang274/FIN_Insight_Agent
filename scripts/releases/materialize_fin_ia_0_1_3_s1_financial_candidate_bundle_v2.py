from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sec_agent.financial_research_candidate_bundle_v2 import (  # noqa: E402
    execute_candidate_bundle_v2_reproof,
    load_candidate_bundle_v2_policy,
    validate_candidate_bundle_v2_result,
)


POLICY_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s1_financial_"
    "candidate_bundle_v2_policy_v1_0.json"
)
RESULT_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_3_s1_financial_"
    "candidate_bundle_v2_result_v1_0.json"
)


def main() -> int:
    if RESULT_PATH.exists():
        raise RuntimeError("financial_candidate_bundle_v2_output_exists")
    policy = load_candidate_bundle_v2_policy(POLICY_PATH, repo_root=ROOT)
    result = execute_candidate_bundle_v2_reproof(policy=policy, repo_root=ROOT)
    if result["status"] != (
        "bundle_v2_engineering_pass_fail_closed_current_sources_pending"
    ):
        raise RuntimeError("financial_candidate_bundle_v2_status_unexpected")
    validate_candidate_bundle_v2_result(result)
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "result_digest": result["result_digest"],
                "case_summaries": [
                    {
                        "case_key": row["case_key"],
                        "source_currentness_status": row[
                            "source_currentness_status"
                        ],
                        "observed_counts": row["observed_counts"],
                        "finding_counts": row["finding_counts"],
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
