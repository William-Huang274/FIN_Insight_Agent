from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.r53_r60_product_evidence_depth_p26_gate import build_p26_product_evidence_depth_gate


def main() -> int:
    parser = argparse.ArgumentParser(description="Build R53-R60 P26 ProductEvidence all-universe depth gate artifacts.")
    parser.add_argument("--root", default=".", help="Repository root. Defaults to current directory.")
    args = parser.parse_args()
    summary = build_p26_product_evidence_depth_gate(Path(args.root))
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary.get("status") in {"pass", "pass_with_product_pack_blocker_registered"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
