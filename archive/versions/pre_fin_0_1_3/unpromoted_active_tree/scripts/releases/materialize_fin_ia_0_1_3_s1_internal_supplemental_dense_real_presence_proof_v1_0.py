from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.s1_internal_supplemental_dense_execution import (  # noqa: E402
    build_real_presence_proof,
    load_supplemental_dense_execution_policy,
    validate_real_presence_proof,
)


POLICY_PATH = ROOT / "configs/runtime/fin_ia_0_1_3_s1_internal_supplemental_dense_execution_policy_v1_0.json"


def main() -> int:
    policy, build_policy, _ = load_supplemental_dense_execution_policy(
        POLICY_PATH, repo_root=ROOT
    )
    public = dict(policy["public_outputs"])
    output = ROOT / str(public["presence_result_ref"])
    if output.exists():
        raise RuntimeError("supplemental_dense_real_presence_proof_already_exists")
    terminal = json.loads((ROOT / str(public["terminal_result_ref"])).read_text(encoding="utf-8"))
    result = build_real_presence_proof(
        repo_root=ROOT,
        policy=policy,
        build_policy=build_policy,
        terminal_result=terminal,
    )
    validate_real_presence_proof(result)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output)
    print(json.dumps({"status": result["status"], "unique_selected_targets_present": result["unique_selected_targets_present"], "row_weighted_satisfied_count": result["row_weighted_satisfied_count"], "observed_calls": result["observed_calls"], "presence_digest": result["presence_digest"], "output": output.as_posix()}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
