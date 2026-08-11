from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.r53_r60_quality_engineering_online_eval import build_p16_gate


def main() -> int:
    parser = argparse.ArgumentParser(description="Build R53-R60 P16 quality engineering / online eval gate artifacts.")
    parser.add_argument("--root", default=".", help="Repository root. Defaults to current directory.")
    parser.add_argument("--task-id", default=None, help="Optional P16 task id.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    summary = build_p16_gate(root, task_id=args.task_id) if args.task_id else build_p16_gate(root)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
