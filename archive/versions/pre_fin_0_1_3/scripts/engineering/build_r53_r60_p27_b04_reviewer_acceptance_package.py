from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the R53-R60 P27 B04 real-reviewer acceptance package.")
    parser.add_argument("--root", default=".", help="Repository root.")
    parser.add_argument("--workbench-url", default="http://127.0.0.1:18080", help="Workbench URL shown in the reviewer package.")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(root / "src"))

    from sec_agent.r53_r60_b04_reviewer_acceptance_package import build_b04_reviewer_acceptance_package

    package = build_b04_reviewer_acceptance_package(root, workbench_url=args.workbench_url)
    print(json.dumps(package, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
