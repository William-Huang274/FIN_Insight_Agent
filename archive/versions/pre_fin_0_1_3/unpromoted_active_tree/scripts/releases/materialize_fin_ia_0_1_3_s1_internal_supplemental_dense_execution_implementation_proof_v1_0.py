from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.s1_internal_supplemental_dense_execution import (  # noqa: E402
    load_supplemental_dense_execution_policy,
    materialize_execution_implementation_proof,
    validate_execution_implementation_proof,
)


POLICY_PATH = ROOT / "configs/runtime/fin_ia_0_1_3_s1_internal_supplemental_dense_execution_policy_v1_0.json"
OUTPUT_PATH = ROOT / "configs/releases/fin_ia_0_1_3_s1_internal_supplemental_dense_execution_implementation_proof_v1_0.json"


def main() -> int:
    if OUTPUT_PATH.exists():
        raise RuntimeError("supplemental_dense_execution_implementation_proof_exists")
    policy, build_policy, _ = load_supplemental_dense_execution_policy(
        POLICY_PATH, repo_root=ROOT
    )
    result = materialize_execution_implementation_proof(
        policy, build_policy, repo_root=ROOT
    )
    validate_execution_implementation_proof(result)
    temporary = OUTPUT_PATH.with_suffix(OUTPUT_PATH.suffix + ".tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(OUTPUT_PATH)
    print(json.dumps({"status": result["status"], "fake_execution": result["fake_execution"], "proof_digest": result["proof_digest"], "output": OUTPUT_PATH.as_posix()}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
