from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.s1_internal_dense_index_diagnostic import (  # noqa: E402
    build_dense_index_diagnostic,
)


OUTPUT_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_3_s1_internal_"
    "dense_index_diagnostic_v1_0.json"
)


def main() -> int:
    if OUTPUT_PATH.exists():
        raise RuntimeError("internal_dense_index_diagnostic_v1_0_already_exists")
    result = build_dense_index_diagnostic(
        repo_root=ROOT,
        r2_result_path=ROOT
        / "configs/releases/fin_ia_0_1_3_s1_internal_bge_fusion_evaluation_attempt_r2.json",
        qrels_path=ROOT
        / "configs/releases/fin_ia_0_1_3_s1_internal_qrels_review_packet_v1_3.json",
        r2_policy_path=ROOT
        / "configs/runtime/fin_ia_0_1_3_s1_internal_bge_fusion_evaluation_policy_v1_1.json",
    )
    encoded = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    temporary = OUTPUT_PATH.with_suffix(OUTPUT_PATH.suffix + ".tmp")
    temporary.write_text(encoded, encoding="utf-8")
    temporary.replace(OUTPUT_PATH)
    print(
        json.dumps(
            {
                "status": result["status"],
                "row_weighted_classification_counts": result[
                    "row_weighted_classification_counts"
                ],
                "unique_selected_target_count": result[
                    "unique_selected_target_count"
                ],
                "unique_selected_targets_present_in_milvus": result[
                    "unique_selected_targets_present_in_milvus"
                ],
                "disposition": result["disposition"],
                "diagnostic_digest": result["diagnostic_digest"],
                "output": OUTPUT_PATH.as_posix(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
