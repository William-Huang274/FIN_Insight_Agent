from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.s1_candidate_bundle_retrieval_evaluation import (  # noqa: E402
    inspect_candidate_bundle_retrieval_environment,
    load_candidate_bundle_retrieval_evaluation_policy,
    materialize_candidate_bundle_retrieval_terminal_result,
)


DEFAULT_POLICY = (
    "configs/runtime/"
    "fin_ia_0_1_3_s1_candidate_bundle_retrieval_evaluation_policy_v1_0.json"
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
    policy = load_candidate_bundle_retrieval_evaluation_policy(
        policy_path, repo_root=repo_root
    )
    if args.inspect_only:
        environment = inspect_candidate_bundle_retrieval_environment(
            policy, repo_root=repo_root
        )
        print(json.dumps(environment, ensure_ascii=False, sort_keys=True))
        return 0 if environment["qualified"] else 1
    if args.authority is None or args.output is None:
        raise SystemExit("--authority and --output are required")
    authority = json.loads(args.authority.read_text(encoding="utf-8"))
    result = materialize_candidate_bundle_retrieval_terminal_result(
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
                "candidate_ceiling": (result.get("evaluation") or {}).get(
                    "candidate_ceiling"
                ),
                "adoption": (result.get("evaluation") or {}).get("adoption"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result["status"].startswith("terminal_succeeded") else 1


if __name__ == "__main__":
    raise SystemExit(main())
