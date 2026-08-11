"""Build S0 unified backlog artifacts for the R53-R60 program."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=repo_root_from_script(), help="Repository root.")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    sys.path.insert(0, str(root / "src"))

    from sec_agent.r53_r60_unified_backlog import build_s0_unified_backlog

    result = build_s0_unified_backlog(root)
    print(json.dumps(result.summary, ensure_ascii=False, indent=2))
    return 0 if result.summary["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
