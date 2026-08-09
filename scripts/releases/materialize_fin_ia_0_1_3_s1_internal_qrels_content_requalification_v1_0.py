from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.s1_internal_qrels_content_requalification import (  # noqa: E402
    load_qrels_content_requalification_policy,
    materialize_qrels_content_requalification_packet,
    validate_qrels_content_requalification_packet,
)


POLICY_PATH = ROOT / (
    "configs/runtime/"
    "fin_ia_0_1_3_s1_internal_qrels_content_requalification_policy_v1_0.json"
)
OUTPUT_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s1_internal_qrels_content_requalification_packet_v1_0.json"
)


def main() -> int:
    if OUTPUT_PATH.exists():
        raise RuntimeError("qrels_content_requalification_packet_already_exists")
    policy = load_qrels_content_requalification_policy(POLICY_PATH, repo_root=ROOT)
    result = materialize_qrels_content_requalification_packet(
        policy, repo_root=ROOT
    )
    validate_qrels_content_requalification_packet(result)
    temporary = OUTPUT_PATH.with_suffix(OUTPUT_PATH.suffix + ".tmp")
    temporary.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(OUTPUT_PATH)
    print(
        json.dumps(
            {
                "status": result["status"],
                "summary": result["content_requalification_summary"],
                "successor_gate": result["successor_gate"],
                "review_digest": result["review_digest"],
                "output": OUTPUT_PATH.as_posix(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
