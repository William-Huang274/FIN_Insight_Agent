from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.s1_internal_supplemental_dense_index import (  # noqa: E402
    load_supplemental_dense_index_policy,
    materialize_supplemental_dense_index_zero_call_proof,
    validate_supplemental_dense_index_zero_call_proof,
)


POLICY_PATH = ROOT / (
    "configs/runtime/"
    "fin_ia_0_1_3_s1_internal_supplemental_dense_index_policy_v1_0.json"
)
OUTPUT_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s1_internal_supplemental_dense_index_"
    "zero_call_proof_v1_0.json"
)


def main() -> int:
    if OUTPUT_PATH.exists():
        raise RuntimeError("supplemental_dense_zero_call_proof_already_exists")
    policy = load_supplemental_dense_index_policy(POLICY_PATH, repo_root=ROOT)
    result = materialize_supplemental_dense_index_zero_call_proof(
        policy, repo_root=ROOT
    )
    validate_supplemental_dense_index_zero_call_proof(result)
    temporary = OUTPUT_PATH.with_suffix(OUTPUT_PATH.suffix + ".tmp")
    temporary.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(OUTPUT_PATH)
    print(
        json.dumps(
            {
                "status": result["status"],
                "source_inventory": result["source_inventory"],
                "federated_presence_gate": result["federated_presence_gate"],
                "fake_execution": result["fake_execution"],
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
