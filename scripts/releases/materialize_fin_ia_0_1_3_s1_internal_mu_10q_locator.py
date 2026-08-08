from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402
from sec_agent.project_os_preflight import run_project_os_preflight  # noqa: E402
from sec_agent.s1_internal_mu_10q_locator import (  # noqa: E402
    RUN_SCOPE,
    build_internal_mu_10q_locator_observation,
    load_internal_mu_10q_locator_policy,
)


POLICY_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s1_internal_mu_10q_locator_policy_v1_0.json"
)
OUTPUT_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_3_s1_internal_mu_10q_locator_observation_v1_0.json"
)


def main() -> int:
    if OUTPUT_PATH.exists():
        raise RuntimeError("internal_mu_10q_locator_output_already_exists")
    preflight = run_project_os_preflight(ROOT, run_scope=RUN_SCOPE)
    if preflight.get("status") != "pass":
        raise RuntimeError("internal_mu_10q_locator_preflight_blocked")
    policy = load_internal_mu_10q_locator_policy(POLICY_PATH, repo_root=ROOT)
    result = build_internal_mu_10q_locator_observation(
        policy=policy, repo_root=ROOT
    )
    body = dict(result)
    body.pop("locator_digest", None)
    body.update(
        {
            "policy_digest": canonical_digest(policy),
            "project_os_preflight": {
                "status": str(preflight["status"]),
                "run_scope": str(preflight["run_scope"]),
            },
            "implementation": {
                "module_ref": "src/sec_agent/s1_internal_mu_10q_locator.py",
                "materializer_ref": (
                    "scripts/releases/materialize_fin_ia_0_1_3_s1_internal_"
                    "mu_10q_locator.py"
                ),
                "policy_ref": POLICY_PATH.relative_to(ROOT).as_posix(),
            },
        }
    )
    output = {**body, "locator_digest": canonical_digest(body)}
    OUTPUT_PATH.write_text(
        json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": output["status"],
                "target": output["target"],
                "locator_digest": output["locator_digest"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
