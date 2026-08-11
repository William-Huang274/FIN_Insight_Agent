from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402
from sec_agent.financial_research_source_object_vertical import (  # noqa: E402
    RUN_SCOPE,
    execute_financial_source_object_vertical,
    load_financial_source_object_vertical_policy,
)
from sec_agent.project_os_preflight import run_project_os_preflight  # noqa: E402


POLICY_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s1_dell_"
    "financial_source_object_vertical_policy_v1_0.json"
)
OUTPUT_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_3_s1_dell_"
    "financial_source_object_vertical_result_v1_0.json"
)
ATTEMPT_ID = "S1-DELL-FINANCIAL-SOURCE-OBJECT-VERTICAL-R1"


def main() -> int:
    if OUTPUT_PATH.exists():
        raise RuntimeError("dell_financial_source_object_vertical_result_exists")
    preflight = run_project_os_preflight(ROOT, run_scope=RUN_SCOPE)
    if preflight.get("status") != "pass":
        raise RuntimeError("dell_financial_source_object_vertical_preflight_blocked")
    policy, _, compiled = load_financial_source_object_vertical_policy(
        POLICY_PATH,
        repo_root=ROOT,
    )
    result = execute_financial_source_object_vertical(
        policy=policy,
        compiled=compiled,
        repo_root=ROOT,
    )
    body = dict(result)
    body.pop("result_digest", None)
    body.update(
        {
            "attempt_id": ATTEMPT_ID,
            "policy_digest": canonical_digest(policy),
            "project_os_preflight": {
                "status": str(preflight["status"]),
                "run_scope": str(preflight["run_scope"]),
                "open_full_chain_blocker_count": int(
                    preflight.get("open_full_chain_blocker_count") or 0
                ),
            },
            "implementation": {
                "module_ref": (
                    "src/sec_agent/financial_research_source_object_vertical.py"
                ),
                "materializer_ref": (
                    "scripts/releases/materialize_fin_ia_0_1_3_s1_dell_"
                    "financial_source_object_vertical.py"
                ),
                "policy_ref": POLICY_PATH.relative_to(ROOT).as_posix(),
            },
        }
    )
    output = {**body, "result_digest": canonical_digest(body)}
    OUTPUT_PATH.write_text(
        json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": output["status"],
                "attempt_id": output["attempt_id"],
                "observed_counts": output["observed_counts"],
                "pack_status": output["candidate_pack_evaluation"]["status"],
                "result_digest": output["result_digest"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
