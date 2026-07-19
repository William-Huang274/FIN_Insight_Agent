"""Frozen v2.8 JIT entry boundary.

B0.5 intentionally does not issue active human authority or run a baseline.
This package-bound entry therefore remains default-deny.  Its post-preflight
lifecycle implementation is the separately hash-bound
``m2_a1_v2_8_operational_proof.execute_v2_8_frozen_lifecycle_core``; only the
explicit synthetic non-human test adapter is reachable during this repair.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="M2-A1 v2.8 frozen JIT: no active authority in B0.5.")
    parser.add_argument("--dry-run-approved-window", action="store_true")
    parser.add_argument("--execute-approved-window", action="store_true")
    parser.add_argument("--run-synthetic-nonhuman-operational-proof", action="store_true")
    parser.add_argument("--synthetic-nonhuman-fixture", action="store_true")
    parser.add_argument("--temporary-root", type=Path)
    parser.add_argument("--approval", type=Path)
    args = parser.parse_args(argv)
    if args.run_synthetic_nonhuman_operational_proof:
        if not args.synthetic_nonhuman_fixture or args.temporary_root is None:
            print(json.dumps({"status": "m2_a1_v2_8_synthetic_fixture_required", "admission": 0, "receipt": 0, "namespace": 0, "actual": 0}, sort_keys=True))
            return 2
        from sec_agent.canonical_runtime.m2_a1_v2_8_operational_proof import execute_v2_8_frozen_lifecycle_core

        proof = execute_v2_8_frozen_lifecycle_core(
            synthetic_nonhuman_fixture=True,
            temporary_root=args.temporary_root,
            child=ROOT / "scripts/engineering/run_point01_m2_a1_v2_8_synthetic_operational_child.py",
            package_digest="f" * 64,
        )
        print(json.dumps({"status": proof.state, "receipt_id": proof.receipt_id, "terminal_digest": proof.terminal_digest, "synthetic_nonhuman_fixture": True}, sort_keys=True))
        return 0 if proof.state == "succeeded" else 1
    if args.execute_approved_window:
        print(json.dumps({"status": "m2_a1_v2_8_active_human_authority_not_issued_B0_5", "admission": 0, "receipt": 0, "namespace": 0, "actual": 0}, sort_keys=True))
        return 2
    print(json.dumps({"status": "m2_a1_v2_8_dry_run_no_active_authority_B0_5", "admission": 0, "receipt": 0, "namespace": 0, "actual": 0}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
