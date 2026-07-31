from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from scripts.releases.issue_fin_ia_0_1_s3_t09_claim_fact_link_policy_fresh_exact_admission import (
    render_issuance,
)


RELEASES = ROOT / "configs" / "releases"
DECISION = RELEASES / (
    "fin_ia_0_1_s3_t09_output_v4_verifier_schema_repair_"
    "fresh_exact_proof_decision_v1_0.json"
)
ADMISSION = RELEASES / (
    "fin_ia_0_1_s3_t09_three_cell_deepseek_"
    "output_v4_verifier_schema_repair_exact_admission_r1.json"
)
ISSUANCE = RELEASES / (
    "fin_ia_0_1_s3_t09_output_v4_verifier_schema_repair_"
    "fresh_exact_admission_issuance_v1_0.json"
)
EXPECTED_DECISION_STATUS = (
    "pass_zero_call_output_v4_verifier_schema_repair_fresh_exact_proof_"
    "contract_frozen_bundled_issuance_and_one_live_authorized"
)


def main() -> int:
    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    expected_digest = str(decision["prospective_admission"]["digest"])
    payload, issuance = render_issuance(
        decision_path=DECISION,
        admission_path=ADMISSION,
        issuance_path=ISSUANCE,
        expected_decision_status=EXPECTED_DECISION_STATUS,
        expected_admission_digest=expected_digest,
        schema_version=(
            "fin_ia_0_1_s3_t09_output_v4_verifier_schema_repair_"
            "fresh_exact_admission_issuance_v1_0"
        ),
        issuance_id=(
            "S3-T09-OUTPUT-V4-VERIFIER-SCHEMA-REPAIR-"
            "FRESH-EXACT-ADMISSION-ISSUANCE"
        ),
        user_instruction=(
            "按这个顺序先修exact-live然后做次t09整体验收"
        ),
        live_execution_authorized=True,
        next_action=(
            "S3-T09-OUTPUT-V4-VERIFIER-SCHEMA-REPAIR-"
            "FRESH-EXACT-LIVE-EXECUTION"
        ),
    )
    ADMISSION.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    ISSUANCE.write_text(
        json.dumps(issuance, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(issuance, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
