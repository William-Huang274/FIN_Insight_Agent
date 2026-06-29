from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.r53_r60_research_to_quant_lab import build_s9_gate


def main() -> int:
    parser = argparse.ArgumentParser(description="Build R53-R60 S9 Research-to-Quant Lab gate artifacts.")
    parser.add_argument("--root", default=".", help="Repository root. Defaults to current directory.")
    parser.add_argument("--task-id", default=None, help="Optional S9 runtime task id.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    summary = build_s9_gate(root, task_id=args.task_id) if args.task_id else build_s9_gate(root)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
