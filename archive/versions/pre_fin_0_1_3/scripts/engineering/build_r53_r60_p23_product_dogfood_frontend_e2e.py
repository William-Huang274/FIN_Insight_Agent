from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.r53_r60_product_dogfood_frontend_e2e import build_p23_product_dogfood_frontend_e2e


def main() -> int:
    parser = argparse.ArgumentParser(description="Build R53-R60 P23 product dogfood / frontend E2E readiness artifacts.")
    parser.add_argument("--root", default=".", help="Repository root. Defaults to current directory.")
    parser.add_argument(
        "--no-write-probe",
        action="store_true",
        help="Do not POST automation-marked review actions while checking API routes.",
    )
    args = parser.parse_args()
    summary = build_p23_product_dogfood_frontend_e2e(Path(args.root), write_probe=not args.no_write_probe)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary.get("status") == "pass_with_human_acceptance_blocked" and summary.get("counts", {}).get("gate_fail_count") == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
