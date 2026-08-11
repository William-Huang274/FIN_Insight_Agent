from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.s1_internal_supplemental_dense_execution import (  # noqa: E402
    REQUIRED_IMPLEMENTATION_BINDING_REFS,
    build_clean_execution_authority,
    load_supplemental_dense_execution_policy,
    validate_clean_execution_authority,
    validate_execution_implementation_proof,
)


POLICY_REF = "configs/runtime/fin_ia_0_1_3_s1_internal_supplemental_dense_execution_policy_v1_0.json"
OUTPUT_REF = "configs/releases/fin_ia_0_1_3_s1_internal_supplemental_dense_build_authority_v1_0.json"
BINDING_REFS = list(REQUIRED_IMPLEMENTATION_BINDING_REFS)


def main() -> int:
    output = ROOT / OUTPUT_REF
    if output.exists():
        raise RuntimeError("supplemental_dense_build_authority_already_exists")
    policy, _, _ = load_supplemental_dense_execution_policy(ROOT / POLICY_REF, repo_root=ROOT)
    proof = validate_execution_implementation_proof(
        json.loads((ROOT / BINDING_REFS[1]).read_text(encoding="utf-8"))
    )
    authority = build_clean_execution_authority(
        policy=policy,
        implementation_proof=proof,
        repo_root=ROOT,
        binding_refs=BINDING_REFS,
    )
    validate_clean_execution_authority(
        authority, policy=policy, repo_root=ROOT, require_clean_synced=True
    )
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(authority, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output)
    print(json.dumps({"status": authority["status"], "attempt_id": authority["attempt_id"], "implementation_commit": authority["implementation"]["commit"], "authority_digest": authority["authority_digest"], "output": output.as_posix()}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
