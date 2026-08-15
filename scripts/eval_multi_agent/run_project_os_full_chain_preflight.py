from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sec_agent.project_os_preflight import build_preflight


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the current-baseline, decision-bound Project OS preflight. "
            "The historical multi-agent preflight implementation remains archived."
        )
    )
    parser.add_argument("--decision", required=True)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    try:
        result = build_preflight(root=ROOT, decision_ref=args.decision)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        result = {
            "schema_version": "fin_ia_current_decision_bound_project_os_preflight_v1_0",
            "status": "fail_closed",
            "decision_ref": args.decision,
            "failure_code": str(exc),
            "network_calls": 0,
            "model_calls": 0,
            "provider_calls": 0,
            "credential_value_persisted": False,
        }
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
        return 1
    print(
        json.dumps(
            result,
            ensure_ascii=False,
            sort_keys=True,
            indent=2 if args.pretty else None,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
