"""Stdlib v2.10 parent that forwards one exact clean-child command."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CHILD = ROOT / "scripts/engineering/run_point01_m2_a1_actual_audit_clean_child_v2_10.py"
_FLAGS = ("--admission", "--receipt-id", "--scenario-id", "--human-approval-digest")
_LEAF_FLAGS = ("--leaf-kind", "--output", "--package-digest", "--admission-digest", "--receipt-digest", "--scenario-id", "--mode")
_PRODUCTION_LEAF_FLAGS = ("--leaf-kind", "--output", "--admission", "--grant", "--receipt-id", "--scenario-id", "--human-approval-digest")


def normalize_child_argv(argv: list[str]) -> list[str]:
    values = list(argv)
    if values.count("--") > 1:
        raise ValueError("m2_a1_v2_10_parent_duplicate_separator")
    if "--" in values:
        if values[0] != "--":
            raise ValueError("m2_a1_v2_10_parent_separator_must_precede_child_argv")
        values = values[1:]
    if not values:
        raise ValueError("m2_a1_v2_10_parent_child_argv_required")
    if values in (["--help"], ["--transport-isolation-probe"]):
        return values
    if values[0] == "--execute-admitted":
        if len(values) != 9:
            raise ValueError("m2_a1_v2_10_parent_child_command_invalid")
        pairs = values[1:]
        if any(pairs[index] != expected for index, expected in zip(range(0, 8, 2), _FLAGS, strict=True)) or any(not pairs[index] or pairs[index].startswith("-") for index in range(1, 8, 2)):
            raise ValueError("m2_a1_v2_10_parent_execute_argument_invalid")
        return values
    if values[0] == "--execute-kernel-leaf":
        if len(values) != 15:
            raise ValueError("m2_a1_v2_10_parent_leaf_command_invalid")
        pairs = values[1:]
        flag_shape = _LEAF_FLAGS if len(pairs) == 14 and pairs[1] == "synthetic_fixture" else _PRODUCTION_LEAF_FLAGS
        if any(pairs[index] != expected for index, expected in zip(range(0, 14, 2), flag_shape, strict=True)) or any(not pairs[index] or pairs[index].startswith("-") for index in range(1, 14, 2)):
            raise ValueError("m2_a1_v2_10_parent_leaf_argument_invalid")
        if pairs[1] == "synthetic_fixture" and pairs[13] not in {"happy", "corrupt", "reviewer_fail", "exit_after_consume"}:
            raise ValueError("m2_a1_v2_10_parent_leaf_kind_or_mode_invalid")
        if pairs[1] not in {"synthetic_fixture", "production_actual"}:
            raise ValueError("m2_a1_v2_10_parent_leaf_kind_or_mode_invalid")
        return values
    raise ValueError("m2_a1_v2_10_parent_child_command_invalid")


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    if raw == ["--help"]:
        argparse.ArgumentParser(description="M2-A1 v2.10 production parent supervisor.").print_help()
        return 0
    try:
        child_argv = normalize_child_argv(raw)
    except ValueError as exc:
        print(json.dumps({"status": str(exc), "child_started": False, "authority_or_runtime_created": 0}, sort_keys=True))
        return 2
    return subprocess.run([sys.executable, "-I", str(CHILD), *child_argv], cwd=ROOT, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
