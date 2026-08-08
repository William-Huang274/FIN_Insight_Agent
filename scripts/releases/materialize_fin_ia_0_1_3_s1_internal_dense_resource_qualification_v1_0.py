from __future__ import annotations

import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from sec_agent.s1_internal_dense_resource_qualification import (  # noqa: E402
    load_dense_resource_qualification_policy,
    materialize_dense_resource_qualification,
    validate_dense_resource_qualification,
)


POLICY = REPO_ROOT / (
    "configs/runtime/"
    "fin_ia_0_1_3_s1_internal_dense_resource_qualification_policy_v1_0.json"
)
OUTPUT = REPO_ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s1_internal_dense_resource_qualification_observation_v1_0.json"
)


def main() -> int:
    policy = load_dense_resource_qualification_policy(POLICY, repo_root=REPO_ROOT)
    result = materialize_dense_resource_qualification(policy, repo_root=REPO_ROOT)
    validate_dense_resource_qualification(result)
    OUTPUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(OUTPUT.relative_to(REPO_ROOT)).replace("\\", "/"),
                "status": result["status"],
                "result_digest": result["result_digest"],
                "bge_status": result["resource_qualification"]["bge_m3"]["status"],
                "reranker_status": result["resource_qualification"]["reranker"]["status"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
