from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.s1_08_external_combined_assessment import (  # noqa: E402
    assess_external_combined_live,
)


DEFAULT_RESULT = (
    ROOT
    / "configs/releases/fin_ia_0_1_3_s1_08_external_combined_live_result_v1_0.json"
)
DEFAULT_RUNTIME = ROOT / ".codex_runtime/fin013_s1_08/external_combined/live-r1"
DEFAULT_OUTPUT = (
    ROOT
    / "configs/releases/fin_ia_0_1_3_s1_08_external_combined_live_assessment_v1_0.json"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--runtime-root", type=Path, default=DEFAULT_RUNTIME)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.output.exists():
        raise RuntimeError("external_combined_r1_assessment_already_exists")
    result = json.loads(args.result.read_text(encoding="utf-8"))
    assessment = assess_external_combined_live(
        result=result,
        runtime_root=args.runtime_root,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(assessment, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "status": assessment["status"],
                "assessment_digest": assessment["assessment_digest"],
                "official_failure_codes": assessment["official_lane"][
                    "failure_codes"
                ],
                "firecrawl_http_status_counts": assessment[
                    "firecrawl_shadow_lane"
                ]["http_status_counts"],
                "internal_retrieval_started": assessment["stage_disposition"][
                    "internal_retrieval_started"
                ],
            },
            ensure_ascii=True,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
