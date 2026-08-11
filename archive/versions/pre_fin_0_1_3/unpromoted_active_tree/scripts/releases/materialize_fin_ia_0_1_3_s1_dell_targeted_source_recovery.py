from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.s1_dell_targeted_source_recovery import (  # noqa: E402
    compile_recovery_result,
    load_recovery_policy,
)


POLICY_PATH = ROOT / (
    "configs/runtime/"
    "fin_ia_0_1_3_s1_dell_targeted_source_recovery_policy_v1_0.json"
)
RESULT_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s1_dell_targeted_source_recovery_result_v1_0.json"
)


def main() -> int:
    policy = load_recovery_policy(POLICY_PATH, repo_root=ROOT)
    result = compile_recovery_result(
        policy=policy,
        repo_root=ROOT,
        recorded_at="2026-08-10T15:45:00Z",
    )
    RESULT_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "result_digest": result["result_digest"],
                "authority_decision": result["authority_decision"],
                "observed_counts": result["observed_counts"],
                "result_path": str(RESULT_PATH.relative_to(ROOT)).replace("\\", "/"),
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
