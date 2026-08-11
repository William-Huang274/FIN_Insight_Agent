from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.s1_candidate_bundle_index_manifest import (  # noqa: E402
    load_candidate_bundle_index_policy,
    materialize_candidate_bundle_index_zero_call_proof,
    validate_candidate_bundle_index_zero_call_proof,
)


POLICY_PATH = ROOT / (
    "configs/runtime/"
    "fin_ia_0_1_3_s1_candidate_bundle_sparse_dense_manifest_policy_v1_0.json"
)
OUTPUT_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s1_candidate_bundle_sparse_dense_manifest_"
    "zero_call_proof_v1_0.json"
)
RUNTIME_ROOT = ROOT / (
    "data/workbench_private/"
    "fin_0_1_3_s1_candidate_bundle_sparse_dense_manifest/zero-call-r3"
)


def main() -> int:
    if OUTPUT_PATH.exists():
        raise RuntimeError("candidate_bundle_index_zero_call_proof_already_exists")
    policy = load_candidate_bundle_index_policy(POLICY_PATH, repo_root=ROOT)
    result = materialize_candidate_bundle_index_zero_call_proof(
        policy=policy,
        repo_root=ROOT,
        output_runtime_root=RUNTIME_ROOT,
    )
    validate_candidate_bundle_index_zero_call_proof(result)
    temporary = OUTPUT_PATH.with_suffix(OUTPUT_PATH.suffix + ".tmp")
    temporary.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(OUTPUT_PATH)
    print(
        json.dumps(
            {
                "status": result["status"],
                "selection_summary": result["selection_summary"],
                "private_manifest": result["private_manifest"],
                "fake_build": result["fake_build"],
                "mutation_proof": result["mutation_proof"],
                "execution_gate": result["execution_gate"],
                "proof_digest": result["proof_digest"],
                "output": OUTPUT_PATH.as_posix(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
