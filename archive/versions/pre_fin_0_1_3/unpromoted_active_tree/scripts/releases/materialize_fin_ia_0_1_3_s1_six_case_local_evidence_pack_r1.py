from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.s1_six_case_local_evidence_pack import (  # noqa: E402
    load_six_case_local_evidence_pack_policy,
    materialize_six_case_local_evidence_packs,
)


DEFAULT_POLICY = ROOT / (
    "configs/runtime/"
    "fin_ia_0_1_3_s1_six_case_local_evidence_pack_policy_v1_0.json"
)
DEFAULT_ARTIFACT_ROOT = ROOT / (
    "data/workbench_private/"
    "fin_0_1_3_s1_six_case_local_evidence_pack/zero-call-r1/objects"
)
DEFAULT_OUTPUT = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s1_six_case_local_evidence_pack_result_v1_0.json"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ARTIFACT_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    policy = load_six_case_local_evidence_pack_policy(
        args.policy,
        repo_root=repo_root,
    )
    result = materialize_six_case_local_evidence_packs(
        policy=policy,
        repo_root=repo_root,
        artifact_root=args.artifact_root,
        output_path=args.output,
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "attempt_id": result["attempt_id"],
                "result_digest": result["result_digest"],
                "observed_counts": result["observed_counts"],
                "case_summaries": result["case_summaries"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
