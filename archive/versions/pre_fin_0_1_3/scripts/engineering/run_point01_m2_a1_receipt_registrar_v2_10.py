"""Authority-only registrar bound to the v2.10 execution-proof package."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PACKAGE_PATH = ROOT / "data/manifests/point01_m2_a1_execution_ready_audit_package_manifest_v2_10.json"
sys.path.insert(0, str(ROOT / "src"))


def main(argv: list[str] | None = None) -> int:
    from sec_agent.canonical_runtime.m2_a1_frozen_jit import registrar_main

    return registrar_main(root=ROOT, package_path=PACKAGE_PATH, argv=sys.argv[1:] if argv is None else argv)


if __name__ == "__main__":
    raise SystemExit(main())
