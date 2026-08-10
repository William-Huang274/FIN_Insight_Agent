from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.s1_candidate_bundle_physical_index import (  # noqa: E402
    inspect_bound_linux_environment,
    load_physical_index_policy,
    materialize_terminal_result,
)


DEFAULT_POLICY = (
    "configs/runtime/"
    "fin_ia_0_1_3_s1_candidate_bundle_physical_index_build_policy_v1_1.json"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--policy", type=Path)
    parser.add_argument("--inspect-only", action="store_true")
    parser.add_argument("--authority", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    policy_path = args.policy or repo_root / DEFAULT_POLICY
    policy = load_physical_index_policy(policy_path, repo_root=repo_root)
    if args.inspect_only:
        print(
            json.dumps(
                inspect_bound_linux_environment(policy),
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    if args.authority is None or args.output is None:
        raise SystemExit("--authority and --output are required")
    for key, value in policy["runtime_contract"]["offline_environment"].items():
        os.environ[str(key)] = str(value)
    authority = json.loads(args.authority.read_text(encoding="utf-8"))
    result = materialize_terminal_result(
        policy=policy,
        authority=authority,
        repo_root=repo_root,
        output_path=args.output,
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "attempt_id": result["attempt_id"],
                "result_digest": result["result_digest"],
                "failure": result.get("failure"),
                "stage_acceptance": result.get("stage_acceptance"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result["status"] == "terminal_succeeded_physical_sparse_dense_build" else 1


if __name__ == "__main__":
    raise SystemExit(main())
