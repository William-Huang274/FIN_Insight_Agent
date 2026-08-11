from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.s1_candidate_bundle_retrieval_evaluation import (  # noqa: E402
    load_candidate_bundle_retrieval_evaluation_policy,
    materialize_candidate_bundle_retrieval_implementation_proof,
)


POLICY_PATH = ROOT / (
    "configs/runtime/"
    "fin_ia_0_1_3_s1_candidate_bundle_retrieval_evaluation_policy_v1_0.json"
)
OUTPUT_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s1_candidate_bundle_retrieval_evaluation_implementation_proof_v1_0.json"
)


def main() -> int:
    if OUTPUT_PATH.exists():
        raise RuntimeError("candidate_bundle_retrieval_implementation_proof_exists")
    policy = load_candidate_bundle_retrieval_evaluation_policy(
        POLICY_PATH, repo_root=ROOT
    )
    proof = materialize_candidate_bundle_retrieval_implementation_proof(
        policy=policy,
        repo_root=ROOT,
    )
    temporary = OUTPUT_PATH.with_name(OUTPUT_PATH.name + ".tmp")
    temporary.write_text(
        json.dumps(proof, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(OUTPUT_PATH)
    print(
        json.dumps(
            {
                "status": proof["status"],
                "proof_digest": proof["proof_digest"],
                "business_ceiling": proof["business_ceiling"],
                "owner_target_ceiling": proof["owner_target_ceiling"],
                "output": str(OUTPUT_PATH.relative_to(ROOT)),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
