from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT_PATH = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT_PATH), str(ROOT_PATH / "src")]

from scripts.releases.issue_fin_ia_0_1_2_s4_t04_nvda_current_evidence_replacement_exact_admission import (
    ADMISSION_REF,
    EXECUTION_IDENTITY,
    ISSUANCE_REF,
)
from scripts.releases.run_fin_ia_0_1_2_s4_t04_nvda_current_evidence_exact_live import (
    ROOT,
    _default_completion,
    _load,
    execute_exact_once_for,
    zero_call_preflight_for,
)


ADMISSION = ROOT / ADMISSION_REF
ISSUANCE = ROOT / ISSUANCE_REF
DEFAULT_RUNTIME_ROOT = ROOT / (
    ".codex_runtime/"
    "fin012-s4-t04-nvda-current-evidence-replacement-exact-live-r2"
)

# Filled only after the immutable R2 admission and issuance are materialized.
EXPECTED_ADMISSION_DIGEST = (
    "b6d66b6821cbf5d6abe18239689a00a81db5ca76649cbaf9011e614445a2180e"
)
EXPECTED_ISSUANCE_DIGEST = (
    "b78ade3d7ce415c6ee10dadc3a867aa4c6e9a466a44d3a385c2abcefb89d977e"
)


def zero_call_preflight() -> dict[str, object]:
    return zero_call_preflight_for(
        admission_path=ADMISSION,
        issuance_path=ISSUANCE,
        expected_admission_digest=EXPECTED_ADMISSION_DIGEST,
        expected_issuance_digest=EXPECTED_ISSUANCE_DIGEST,
        execution_identity=EXECUTION_IDENTITY,
    )


def execute_exact_once(
    runtime_root: Path,
    *,
    completion=_default_completion,
) -> dict[str, object]:
    return execute_exact_once_for(
        runtime_root,
        admission_path=ADMISSION,
        issuance_path=ISSUANCE,
        expected_admission_digest=EXPECTED_ADMISSION_DIGEST,
        expected_issuance_digest=EXPECTED_ISSUANCE_DIGEST,
        execution_identity=EXECUTION_IDENTITY,
        completion=completion,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("preflight", "execute", "inspect"))
    parser.add_argument("--runtime-root", type=Path, default=DEFAULT_RUNTIME_ROOT)
    args = parser.parse_args()
    if args.mode == "preflight":
        result = zero_call_preflight()
    elif args.mode == "execute":
        result = execute_exact_once(args.runtime_root.resolve())
    else:
        result = _load(args.runtime_root.resolve() / "execution-result.json")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") in {
        "success",
        "pass_exact_input_admission_transport_wiring_zero_call",
    } else 2


if __name__ == "__main__":
    raise SystemExit(main())
