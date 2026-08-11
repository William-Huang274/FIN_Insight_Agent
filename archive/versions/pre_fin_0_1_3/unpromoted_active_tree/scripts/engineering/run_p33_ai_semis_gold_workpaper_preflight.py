from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
for path in (SRC_ROOT, REPO_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from sec_agent.p33_ai_semis_gold_workpaper_preflight import build_p33_ai_semis_gold_workpaper_preflight


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the P33-3 AI/Semis gold workpaper no-paid preflight.")
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="Repository root.")
    parser.add_argument("--no-write", action="store_true", help="Do not write manifest/report artifacts.")
    args = parser.parse_args()

    manifest = build_p33_ai_semis_gold_workpaper_preflight(args.root, write_outputs=not args.no_write)
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "deterministic_preflight_status": manifest["deterministic_preflight_status"],
                "paid_run_allowed": manifest["paid_run_allowed"],
                "release_decision": manifest["release_decision"],
                "closeout_level": manifest["closeout_level"],
                "gate_fail_count": manifest["gate_fail_count"],
                "case_id": manifest["case_id"],
                "open_full_chain_blocker_count": manifest["project_os_preflight"]["open_full_chain_blocker_count"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if manifest["deterministic_preflight_status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
