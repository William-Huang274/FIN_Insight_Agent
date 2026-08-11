from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.r53_r60_workbench_frontdoor_drilldown import build_s6_projection


def main() -> None:
    parser = argparse.ArgumentParser(description="Build R53-R60 S6 Workbench frontdoor / drilldown projection artifacts.")
    parser.add_argument("--root", default=".", help="Repository root.")
    parser.add_argument("--task-id", default=None, help="Optional R53-R60 runtime task id to project.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    summary = build_s6_projection(root, task_id=args.task_id) if args.task_id else build_s6_projection(root)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
