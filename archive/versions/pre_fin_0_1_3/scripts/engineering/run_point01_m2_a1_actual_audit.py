"""Start an admitted M2-A1 audit only in a fresh isolated child process.

The supervisor intentionally imports no ``sec_agent`` code.  Its sole job is
to hand the exact admission/receipt identifiers to the clean child so a host
pytest process or workbench process cannot pre-load transport aliases before
the M2 canary is installed.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CLEAN_CHILD = ROOT / "scripts/engineering/run_point01_m2_a1_actual_audit_clean_child.py"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Launch one already-registered M2-A1 receipt in an isolated Python child.")
    parser.add_argument("--execute-admitted", action="store_true")
    parser.add_argument("--admission", type=Path)
    parser.add_argument("--receipt-id")
    parser.add_argument("--scenario-id")
    args = parser.parse_args(argv)
    if not args.execute_admitted:
        print(json.dumps({"status": "m2_a1_actual_probes_not_authorized", "compiler_or_shadow_fixture_runs": 0, "model_calls": 0, "network_requests": 0, "store_writes": 0}, ensure_ascii=False))
        return 1
    if args.admission is None or not args.receipt_id or not args.scenario_id:
        print(json.dumps({"status": "m2_a1_exact_admitted_cli_arguments_required"}, ensure_ascii=False))
        return 2

    completed = subprocess.run(
        [
            sys.executable,
            "-I",
            str(CLEAN_CHILD),
            "--execute-admitted",
            "--admission",
            str(args.admission.resolve()),
            "--receipt-id",
            args.receipt_id,
            "--scenario-id",
            args.scenario_id,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.stdout:
        sys.stdout.write(completed.stdout)
    if completed.stderr:
        sys.stderr.write(completed.stderr)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
