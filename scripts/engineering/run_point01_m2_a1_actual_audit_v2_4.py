"""Stdlib-only v2.4 parent supervisor; it owns no compiler or transport capability."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CHILD = ROOT / "scripts/engineering/run_point01_m2_a1_actual_audit_clean_child_v2_4.py"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run an M2-A1 v2.4 clean-child boundary only.")
    parser.add_argument("--transport-isolation-probe", action="store_true")
    parser.add_argument("remaining", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    child_args = [sys.executable, "-I", str(CHILD)]
    if args.transport_isolation_probe:
        child_args.append("--transport-isolation-probe")
    child_args.extend(args.remaining)
    completed = subprocess.run(child_args, cwd=ROOT, check=False)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
