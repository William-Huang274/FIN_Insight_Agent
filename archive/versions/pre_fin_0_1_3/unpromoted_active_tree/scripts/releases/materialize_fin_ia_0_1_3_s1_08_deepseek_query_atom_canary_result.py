from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sec_agent.s1_08_query_atom_canary_assessment import (  # noqa: E402
    assess_failed_query_atom_canary,
)
from sec_agent.shared_admission_ledger import (  # noqa: E402
    SharedAdmissionConsumptionLedger,
)


AUTHORITY = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_deepseek_query_atom_canary_authority_decision_v1_0.json"
ZERO_CALL_EVALUATION = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_query_facet_three_way_zero_call_proof_v1_0.json"
OUTPUT = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_deepseek_query_atom_canary_result_v1_0.json"
DEFAULT_LEDGER = ROOT / ".codex_runtime/fin013_s1_08/query_atom_canary_v1/shared/admission_ledger.sqlite"


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("query_atom_result_json_object_required")
    return value


def _write(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--admission", type=Path, required=True)
    parser.add_argument("--terminal", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    args = parser.parse_args()
    admission = _load(args.admission.resolve())
    terminal = _load(args.terminal.resolve())
    capture = _load(args.terminal.resolve().parent / str(terminal["capture_ref"]))
    receipt = SharedAdmissionConsumptionLedger(args.ledger).read(
        str(admission["admission_digest"])
    ).as_dict()
    result = assess_failed_query_atom_canary(
        admission=admission,
        terminal=terminal,
        capture=capture,
        receipt=receipt,
        authority=_load(AUTHORITY),
        zero_call_evaluation=_load(ZERO_CALL_EVALUATION),
    )
    _write(OUTPUT, result)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
