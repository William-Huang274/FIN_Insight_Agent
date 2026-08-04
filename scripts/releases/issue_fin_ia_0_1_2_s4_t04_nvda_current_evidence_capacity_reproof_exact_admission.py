from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from apps.workbench.backend.application.bounded_agent_executor import (  # noqa: E402
    S4_T04_CURRENT_EVIDENCE_VERIFIER_MODEL_VIEW_CONTRACT_REF,
)
from apps.workbench.backend.application.fin_0_1_2_s4_t04_current_evidence_research import (  # noqa: E402
    T04_MAXIMUM_INPUT_TOKENS,
)
from scripts.releases.issue_fin_ia_0_1_2_s4_t04_nvda_current_evidence_fresh_exact_admission import (  # noqa: E402
    render_issuance_for,
)


ADMISSION_REF = (
    "configs/releases/"
    "fin_ia_0_1_2_s4_t04_nvda_current_evidence_capacity_reproof_fresh_exact_"
    "admission_r3.json"
)
ISSUANCE_REF = (
    "configs/releases/"
    "fin_ia_0_1_2_s4_t04_nvda_current_evidence_capacity_reproof_fresh_exact_"
    "admission_issuance_v1_0.json"
)
EXECUTION_IDENTITY = (
    "fin012-s4-t04-nvda-current-evidence-capacity-reproof-exact-live-r3"
)


def render_capacity_reproof_issuance() -> tuple[
    dict[str, object], dict[str, object]
]:
    return render_issuance_for(
        admission_ref=ADMISSION_REF,
        execution_identity=EXECUTION_IDENTITY,
        admission_id=(
            "fin012-s4-t04-nvda-current-evidence-capacity-reproof-exact-"
            "admission-r3"
        ),
        execution_mode=(
            "exact_live_fin_0_1_2_s4_t04_current_evidence_capacity_reproof_r3"
        ),
        issuance_schema_version=(
            "fin_ia_0_1_2_s4_t04_current_evidence_capacity_reproof_fresh_exact_"
            "admission_issuance_v1_0"
        ),
        verifier_input_contract_ref=(
            S4_T04_CURRENT_EVIDENCE_VERIFIER_MODEL_VIEW_CONTRACT_REF
        ),
        maximum_input_tokens=T04_MAXIMUM_INPUT_TOKENS,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", choices=("admission", "issuance"), required=True)
    args = parser.parse_args()
    admission, issuance = render_capacity_reproof_issuance()
    print(
        json.dumps(
            admission if args.kind == "admission" else issuance,
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
