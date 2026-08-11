from __future__ import annotations

import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from sec_agent.s1_internal_numeric_sql_qrels import (  # noqa: E402
    load_numeric_sql_qrels_policy,
    materialize_numeric_sql_qrels_observation,
    validate_numeric_sql_qrels_observation,
)


POLICY = (
    REPO_ROOT
    / "configs/runtime/fin_ia_0_1_3_s1_internal_numeric_sql_qrels_policy_v1_0.json"
)
OUTPUT = (
    REPO_ROOT
    / "configs/releases/fin_ia_0_1_3_s1_internal_numeric_sql_qrels_observation_v1_0.json"
)


def main() -> int:
    policy = load_numeric_sql_qrels_policy(POLICY, repo_root=REPO_ROOT)
    result = materialize_numeric_sql_qrels_observation(policy, repo_root=REPO_ROOT)
    validate_numeric_sql_qrels_observation(result)
    OUTPUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(OUTPUT.relative_to(REPO_ROOT)).replace("\\", "/"),
                "status": result["status"],
                "result_digest": result["result_digest"],
                "successor_strata": result["observations"][
                    "current_three_case_successor_mart"
                ]["strata"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
