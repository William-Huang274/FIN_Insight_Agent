from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.s1_residual_gap_external_supplement import (  # noqa: E402
    compile_residual_gap_external_priority_plan,
    load_bound_local_evidence_packs,
    load_residual_gap_external_supplement_policy,
)


DEFAULT_POLICY = ROOT / (
    "configs/runtime/"
    "fin_ia_0_1_3_s1_residual_gap_external_supplement_policy_v1_0.json"
)
DEFAULT_OUTPUT = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s1_residual_gap_external_priority_plan_v1_0.json"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    policy = load_residual_gap_external_supplement_policy(
        args.policy,
        repo_root=repo_root,
    )
    local_result, packs = load_bound_local_evidence_packs(
        policy=policy,
        repo_root=repo_root,
    )
    plan = compile_residual_gap_external_priority_plan(
        policy=policy,
        local_result=local_result,
        packs=packs,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(plan, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": plan["status"],
                "plan_digest": plan["plan_digest"],
                "raw_gap_count": plan["raw_gap_count"],
                "selected_gap_count": plan["selected_gap_count"],
                "deferred_gap_count": plan["deferred_gap_count"],
                "selected_intent_count": len(plan["selected_intents"]),
                "network_authority_issued": plan["stage_acceptance"][
                    "network_authority_issued"
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
