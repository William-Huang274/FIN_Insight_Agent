"""Stdlib-only v2.6 parent supervisor with an exact child argv contract."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CHILD = ROOT / "scripts/engineering/run_point01_m2_a1_actual_audit_clean_child_v2_6.py"
_EXECUTE_FLAGS = ("--admission", "--receipt-id", "--scenario-id")


def normalize_child_argv(argv: list[str]) -> list[str]:
    values = list(argv)
    if values.count("--") > 1:
        raise ValueError("m2_a1_parent_duplicate_separator")
    if "--" in values:
        if values[0] != "--":
            raise ValueError("m2_a1_parent_separator_must_precede_child_argv")
        values = values[1:]
    if not values:
        raise ValueError("m2_a1_parent_child_argv_required")
    if values in (["--help"], ["--transport-isolation-probe"]):
        return values
    if values[0] != "--execute-admitted" or len(values) != 7:
        raise ValueError("m2_a1_parent_child_command_invalid")
    pairs = values[1:]
    if any(pairs[index] != expected for index, expected in zip(range(0, 6, 2), _EXECUTE_FLAGS, strict=True)) or any(not pairs[index] or pairs[index].startswith("-") for index in range(1, 6, 2)):
        raise ValueError("m2_a1_parent_execute_argument_invalid")
    return values


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    if raw == ["--help"]:
        argparse.ArgumentParser(description="M2-A1 v2.6 frozen-JIT parent supervisor.").print_help()
        return 0
    try:
        child_argv = normalize_child_argv(raw)
    except ValueError as exc:
        print(json.dumps({"status": str(exc), "child_started": False, "authority_or_runtime_created": 0}, sort_keys=True))
        return 2
    return subprocess.run([sys.executable, "-I", str(CHILD), *child_argv], cwd=ROOT, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
