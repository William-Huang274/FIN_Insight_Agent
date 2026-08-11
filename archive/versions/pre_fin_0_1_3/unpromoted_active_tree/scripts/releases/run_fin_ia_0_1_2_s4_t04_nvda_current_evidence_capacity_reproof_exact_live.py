from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT_PATH = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT_PATH), str(ROOT_PATH / "src")]

from scripts.releases.issue_fin_ia_0_1_2_s4_t04_nvda_current_evidence_capacity_reproof_exact_admission import (  # noqa: E402
    ADMISSION_REF,
    EXECUTION_IDENTITY,
    ISSUANCE_REF,
)
from scripts.releases.run_fin_ia_0_1_2_s4_t04_nvda_current_evidence_exact_live import (  # noqa: E402
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
    "fin012-s4-t04-nvda-current-evidence-capacity-reproof-exact-live-r3"
)
EXPECTED_ADMISSION_DIGEST = (
    "b2aa76f43bd3fc58ee2014b58c9ab11bd63aa882699a62bb992b6b0ed4eb32dd"
)
EXPECTED_ISSUANCE_DIGEST = (
    "4db9fb4a5787201fbc176fd157f2445c689fccbc3c2685d7669d14ed2acc9ec6"
)


def zero_call_preflight() -> dict[str, object]:
    result = zero_call_preflight_for(
        admission_path=ADMISSION,
        issuance_path=ISSUANCE,
        expected_admission_digest=EXPECTED_ADMISSION_DIGEST,
        expected_issuance_digest=EXPECTED_ISSUANCE_DIGEST,
        execution_identity=EXECUTION_IDENTITY,
    )
    issuance = _load(ISSUANCE)
    capacity = issuance["execution_envelope"].get("input_capacity_contract")
    if (
        not isinstance(capacity, dict)
        or capacity.get("maximum_input_tokens") != 108000
        or capacity.get("cost_derived_absolute_maximum_input_tokens") != 117931
        or issuance["execution_envelope"]["hard_budget"].get(
            "maximum_input_tokens"
        )
        != 108000
    ):
        raise ValueError("s4_t04_r3_compiled_capacity_binding_missing")
    return {
        **result,
        "compiled_capacity_contract_ref": capacity["contract_ref"],
        "maximum_input_tokens": capacity["maximum_input_tokens"],
        "cost_derived_absolute_maximum_input_tokens": capacity[
            "cost_derived_absolute_maximum_input_tokens"
        ],
    }


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
