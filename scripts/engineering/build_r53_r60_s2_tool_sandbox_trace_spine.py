"""Build S2 tool / sandbox / trace spine L4-scope gate artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root. Defaults to current working directory.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    sys.path.insert(0, str(root / "src"))
    from sec_agent.r53_r60_tool_sandbox_spine import build_s2_gate

    summary = build_s2_gate(root)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary.get("release_decision") == "S2_L4_scope_pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
