from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from scripts.releases.issue_fin_ia_0_1_2_s4_t04_nvda_current_evidence_fresh_exact_admission import (
    render_issuance_for,
)


ADMISSION_REF = (
    "configs/releases/"
    "fin_ia_0_1_2_s4_t04_nvda_current_evidence_replacement_fresh_exact_"
    "admission_r2.json"
)
ISSUANCE_REF = (
    "configs/releases/"
    "fin_ia_0_1_2_s4_t04_nvda_current_evidence_replacement_fresh_exact_"
    "admission_issuance_v1_0.json"
)
EXECUTION_IDENTITY = (
    "fin012-s4-t04-nvda-current-evidence-replacement-exact-live-r2"
)


def render_replacement_issuance() -> tuple[dict[str, object], dict[str, object]]:
    return render_issuance_for(
        admission_ref=ADMISSION_REF,
        execution_identity=EXECUTION_IDENTITY,
        admission_id=(
            "fin012-s4-t04-nvda-current-evidence-replacement-exact-"
            "admission-r2"
        ),
        execution_mode=(
            "exact_live_fin_0_1_2_s4_t04_current_evidence_replacement_r2"
        ),
        issuance_schema_version=(
            "fin_ia_0_1_2_s4_t04_current_evidence_replacement_fresh_exact_"
            "admission_issuance_v1_0"
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", choices=("admission", "issuance"), required=True)
    args = parser.parse_args()
    admission, issuance = render_replacement_issuance()
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
