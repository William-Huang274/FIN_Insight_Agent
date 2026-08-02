from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.fin_0_1_2_s2_paired_model_canary_runner import (
    T03_DEFAULT_RUNTIME_ROOT,
    execute_exact_six_call_canary,
    run_zero_call_preflight,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the FIN 0.1.2 S2 T03 paired canary preflight or exact execution."
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute the authority-bound six provider calls; default is zero-call preflight.",
    )
    parser.add_argument(
        "--runtime-root",
        type=Path,
        default=ROOT / T03_DEFAULT_RUNTIME_ROOT,
    )
    args = parser.parse_args()
    result = (
        execute_exact_six_call_canary(runtime_root=args.runtime_root)
        if args.execute
        else run_zero_call_preflight()
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
