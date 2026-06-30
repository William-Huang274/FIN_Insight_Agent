from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.r53_r60_source_doc_status_reconciliation import build_p22_source_doc_status_reconciliation


def main() -> int:
    parser = argparse.ArgumentParser(description="Build R53-R60 P22 source-doc status reconciliation artifacts.")
    parser.add_argument("--root", default=".", help="Repository root. Defaults to current directory.")
    args = parser.parse_args()
    summary = build_p22_source_doc_status_reconciliation(Path(args.root))
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
