from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402
from sec_agent.financial_research_held_out_profile_registry import (  # noqa: E402
    HELD_OUT_PROFILE_RUN_SCOPE,
    execute_held_out_profile_selection,
    load_held_out_profile_selection_policy,
)
from sec_agent.financial_research_source_object_vertical import (  # noqa: E402
    normalized_sha256,
)
from sec_agent.project_os_preflight import run_project_os_preflight  # noqa: E402


DEFAULT_POLICY = (
    "configs/runtime/"
    "fin_ia_0_1_3_s1_three_held_out_profile_selection_policy_v1_0.json"
)
DEFAULT_RESULT = (
    "configs/releases/"
    "fin_ia_0_1_3_s1_three_held_out_profile_selection_result_v1_0.json"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--policy", default=DEFAULT_POLICY)
    parser.add_argument("--result", default=DEFAULT_RESULT)
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    policy_path = root / args.policy
    result_path = root / args.result
    if result_path.exists():
        raise RuntimeError("held_out_profile_selection_result_already_exists")
    preflight = run_project_os_preflight(
        root,
        run_scope=HELD_OUT_PROFILE_RUN_SCOPE,
    )
    if preflight.get("status") != "pass":
        raise RuntimeError("held_out_profile_selection_preflight_blocked")
    policy, base_contract, extended_contract = (
        load_held_out_profile_selection_policy(policy_path, repo_root=root)
    )
    executed = execute_held_out_profile_selection(
        policy=policy,
        base_contract=base_contract,
        extended_contract=extended_contract,
        repo_root=root,
    )
    body = dict(executed)
    body.pop("result_digest", None)
    body.update(
        {
            "policy_ref": Path(args.policy).as_posix(),
            "policy_sha256": normalized_sha256(policy_path),
            "implementation": {
                "module_ref": (
                    "src/sec_agent/financial_research_held_out_profile_registry.py"
                ),
                "module_sha256": normalized_sha256(
                    root
                    / "src/sec_agent/financial_research_held_out_profile_registry.py"
                ),
                "materializer_ref": (
                    "scripts/releases/materialize_fin_ia_0_1_3_s1_"
                    "three_held_out_profile_selection.py"
                ),
            },
            "project_os_preflight": {
                "status": str(preflight["status"]),
                "run_scope": str(preflight["run_scope"]),
                "open_full_chain_blocker_count": int(
                    preflight.get("open_full_chain_blocker_count") or 0
                ),
            },
        }
    )
    result = {**body, "result_digest": canonical_digest(body)}
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
