from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.p33_memo_projection_replay import (  # noqa: E402
    DEFAULT_MEMO_WRITER_NODE_RESULT,
    DEFAULT_MULTI_CASE_JSON,
    DEFAULT_MULTI_CASE_MD,
    DEFAULT_PROJECTION_JSON,
    DEFAULT_PROJECTION_MD,
    write_projection_replay_artifacts,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Replay P33 single-case renderer/final-verifier/Workbench projections "
            "from an accepted Memo Writer node artifact, then audit multi-case gold-set readiness."
        )
    )
    parser.add_argument("--memo-writer-node-result", default=str(DEFAULT_MEMO_WRITER_NODE_RESULT))
    parser.add_argument("--projection-json", default=str(DEFAULT_PROJECTION_JSON))
    parser.add_argument("--projection-md", default=str(DEFAULT_PROJECTION_MD))
    parser.add_argument("--multi-case-json", default=str(DEFAULT_MULTI_CASE_JSON))
    parser.add_argument("--multi-case-md", default=str(DEFAULT_MULTI_CASE_MD))
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero if the single-case projection fails. Multi-case readiness may remain blocked.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = write_projection_replay_artifacts(
        memo_writer_node_result=args.memo_writer_node_result,
        projection_json=args.projection_json,
        projection_md=args.projection_md,
        multi_case_json=args.multi_case_json,
        multi_case_md=args.multi_case_md,
    )
    single = result["single_case_projection"]
    multi = result["multi_case_readiness"]
    summary = {
        "single_case_projection_status": single.get("status"),
        "renderer_status": (single.get("renderer_projection") or {}).get("status"),
        "final_verifier_status": (single.get("final_verifier_projection") or {}).get("status"),
        "workbench_status": (single.get("workbench_projection") or {}).get("status"),
        "multi_case_readiness_status": multi.get("status"),
        "multi_case_count": multi.get("case_count"),
        "multi_case_artifact_ready_count": multi.get("artifact_ready_count"),
        "multi_case_fresh_specialist_pass_count": multi.get("fresh_specialist_pass_count"),
        "artifact_refs": result["artifact_refs"],
        "not_run": sorted(set((single.get("not_run") or []) + (multi.get("not_run") or []))),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.strict and single.get("status") != "pass":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
