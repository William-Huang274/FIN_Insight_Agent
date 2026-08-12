from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from ingestion.official_source_capture import capture_plan  # noqa: E402


DEFAULT_PLAN = (
    ROOT
    / "configs"
    / "retrieval"
    / "fin_ia_0_1_3_s1b_official_source_capture_plan_v1_0.json"
)
DEFAULT_OUTPUT_ROOT = (
    ROOT / "data" / "workbench_private" / "fin_0_1_3_s1b_official_source_capture"
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Capture the bounded FIN 0.1.3 S1-B official-source addendum."
    )
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--attempt-id", required=True)
    args = parser.parse_args()
    plan = json.loads(args.plan.resolve().read_text(encoding="utf-8"))
    result = capture_plan(
        plan,
        output_root=args.output_root,
        attempt_id=str(args.attempt_id),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "s1b_official_sources_captured" else 2


if __name__ == "__main__":
    raise SystemExit(main())
