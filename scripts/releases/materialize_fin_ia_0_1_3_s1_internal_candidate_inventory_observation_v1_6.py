from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402
from sec_agent.project_os_preflight import run_project_os_preflight  # noqa: E402
from sec_agent.s1_internal_candidate_ceiling import (  # noqa: E402
    canonical_observation_digest,
)
from sec_agent.s1_internal_supplemental_assets import (  # noqa: E402
    RUN_SCOPE,
    load_internal_supplemental_candidate_refresh_policy,
)
from sec_agent.s1_internal_supplemental_candidate_refresh import (  # noqa: E402
    execute_internal_supplemental_candidate_refresh,
)


POLICY_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s1_internal_"
    "supplemental_candidate_refresh_policy_v1_2.json"
)
OUTPUT_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_3_s1_internal_candidate_"
    "inventory_observation_v1_6_attempt_r7.json"
)
ATTEMPT_ID = "S1-INTERNAL-MU-10Q-THREE-ASSET-CANDIDATE-GATE-R7"
SUPERSEDES = (
    "configs/releases/fin_ia_0_1_3_s1_internal_candidate_"
    "inventory_observation_v1_5_attempt_r6.json"
)


def main() -> int:
    if OUTPUT_PATH.exists():
        raise RuntimeError("internal_supplemental_candidate_r7_already_exists")
    preflight = run_project_os_preflight(ROOT, run_scope=RUN_SCOPE)
    if preflight.get("status") != "pass":
        raise RuntimeError("internal_supplemental_candidate_r7_preflight_blocked")
    policy = load_internal_supplemental_candidate_refresh_policy(
        POLICY_PATH, repo_root=ROOT
    )
    result = execute_internal_supplemental_candidate_refresh(
        policy=policy, repo_root=ROOT
    )
    body = dict(result)
    body.pop("result_digest", None)
    body.update(
        {
            "attempt_id": ATTEMPT_ID,
            "policy_digest": canonical_digest(policy),
            "supersedes_observation": SUPERSEDES,
            "project_os_preflight": {
                "status": str(preflight["status"]),
                "run_scope": str(preflight["run_scope"]),
                "open_full_chain_blocker_count": int(
                    preflight.get("open_full_chain_blocker_count") or 0
                ),
            },
            "implementation": {
                "module_ref": (
                    "src/sec_agent/s1_internal_supplemental_candidate_refresh.py"
                ),
                "materializer_ref": (
                    "scripts/releases/materialize_fin_ia_0_1_3_s1_internal_"
                    "candidate_inventory_observation_v1_6.py"
                ),
                "policy_ref": POLICY_PATH.relative_to(ROOT).as_posix(),
            },
        }
    )
    output = {**body, "result_digest": canonical_observation_digest(body)}
    OUTPUT_PATH.write_text(
        json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": output["status"],
                "attempt_id": output["attempt_id"],
                "candidate_counts_by_route": output["observed_counts"][
                    "candidate_counts_by_route"
                ],
                "typed_gap_counts": output["observed_counts"][
                    "typed_gap_counts"
                ],
                "result_digest": output["result_digest"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
