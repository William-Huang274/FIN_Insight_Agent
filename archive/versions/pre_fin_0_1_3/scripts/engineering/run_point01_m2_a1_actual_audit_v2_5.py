"""Stdlib-only v2.5 parent supervisor with an exact child argv contract.

The parent owns neither planning nor transport capability.  It accepts one
optional separator solely for shell ergonomics and forwards the normalised
child argument vector exactly once to the isolated child.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CHILD = ROOT / "scripts/engineering/run_point01_m2_a1_actual_audit_clean_child_v2_5.py"
_EXECUTE_FLAGS = ("--admission", "--receipt-id", "--scenario-id")


class ParentArgvError(ValueError):
    """The parent rejected argv before creating a child or authority resource."""


def normalize_child_argv(argv: list[str]) -> list[str]:
    """Return the one exact argv that may be passed to the clean child."""

    values = list(argv)
    separator_count = values.count("--")
    if separator_count > 1:
        raise ParentArgvError("m2_a1_parent_duplicate_separator")
    if separator_count == 1:
        if values[0] != "--":
            raise ParentArgvError("m2_a1_parent_separator_must_precede_child_argv")
        values = values[1:]
    if not values:
        raise ParentArgvError("m2_a1_parent_child_argv_required")
    if values == ["--help"]:
        return values
    if values == ["--transport-isolation-probe"]:
        return values
    if not values or values[0] != "--execute-admitted":
        raise ParentArgvError("m2_a1_parent_child_command_invalid")
    if len(values) != 7:
        raise ParentArgvError("m2_a1_parent_execute_argument_count_invalid")
    pairs = values[1:]
    if any(pairs[index] != expected for index, expected in zip(range(0, 6, 2), _EXECUTE_FLAGS, strict=True)):
        raise ParentArgvError("m2_a1_parent_execute_argument_order_invalid")
    if any(not pairs[index] or pairs[index].startswith("-") for index in range(1, 6, 2)):
        raise ParentArgvError("m2_a1_parent_execute_argument_value_invalid")
    return values


def _parent_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        description="M2-A1 v2.5 parent supervisor; use `-- <child argv>` to invoke the clean child.",
        add_help=True,
    )


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    if raw == ["--help"]:
        _parent_parser().print_help()
        return 0
    try:
        child_argv = normalize_child_argv(raw)
    except ParentArgvError as exc:
        print(json.dumps({"status": str(exc), "child_started": False, "authority_or_runtime_created": 0}, sort_keys=True))
        return 2
    completed = subprocess.run([sys.executable, "-I", str(CHILD), *child_argv], cwd=ROOT, check=False)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
