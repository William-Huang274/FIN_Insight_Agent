from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sec_agent.hermetic_test_runner import run_hermetic_active_suite


DEFAULT_MANIFEST = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_2_s0_current_active_test_suite_manifest_v2_1.json"
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the manifest-selected current S0 qualification in two "
            "disposable runtimes without model or provider credentials."
        )
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    result = run_hermetic_active_suite(
        repository_root=ROOT,
        manifest_path=args.manifest.resolve(),
        output_root=args.output_root.resolve(),
    )
    print(result["status"])
    print(result["output_root"])
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
