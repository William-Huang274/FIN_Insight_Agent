from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_contract_policies import (
    S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V4_REF,
)
from scripts.releases.issue_fin_ia_0_1_s3_t09_claim_fact_link_policy_fresh_exact_admission import (
    render_issuance,
)
from scripts.releases.prepare_fin_ia_0_1_s3_t09_layered_acceptance_final_fresh_exact_proof import (
    CODE_BINDING_PATHS,
    DECISION_STATUS,
    HOST_CAPABILITY_RECEIPT,
)
from scripts.releases.supervise_fin_ia_0_1_s3_t09_exact_live_execution import (
    _validate_host_capability_receipt,
)


RELEASES = ROOT / "configs" / "releases"
DECISION = RELEASES / (
    "fin_ia_0_1_s3_t09_layered_acceptance_final_"
    "fresh_agent_proof_decision_v1_0.json"
)
ADMISSION = RELEASES / (
    "fin_ia_0_1_s3_t09_three_cell_deepseek_"
    "layered_acceptance_final_exact_admission_r1.json"
)
ISSUANCE = RELEASES / (
    "fin_ia_0_1_s3_t09_layered_acceptance_final_"
    "fresh_exact_admission_issuance_v1_0.json"
)
EXPECTED_ADMISSION_DIGEST = (
    "424add2dd9105a9a775af36bb31af4c62e6f1654597fccee7b1ebbee86f66550"
)


class LayeredAcceptanceIssuanceError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise LayeredAcceptanceIssuanceError(code)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render_final_issuance() -> tuple[dict, dict]:
    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    _require(
        decision.get("status") == DECISION_STATUS,
        "layered_acceptance_decision_status_invalid",
    )
    _require(
        decision.get("prospective_admission", {}).get("digest")
        == EXPECTED_ADMISSION_DIGEST,
        "layered_acceptance_prospective_digest_mismatch",
    )
    _require(
        decision.get("exact_code_bindings")
        == {
            path.as_posix(): _sha256(ROOT / path)
            for path in CODE_BINDING_PATHS
        },
        "layered_acceptance_exact_code_binding_drift",
    )
    capability, capability_digest = _validate_host_capability_receipt(
        HOST_CAPABILITY_RECEIPT
    )
    _require(
        capability_digest
        == decision["supervision_v2_acceptance_contract"][
            "host_capability_receipt_sha256"
        ],
        "layered_acceptance_host_capability_digest_drift",
    )

    payload, issuance = render_issuance(
        decision_path=DECISION,
        admission_path=ADMISSION,
        issuance_path=ISSUANCE,
        expected_decision_status=DECISION_STATUS,
        expected_admission_digest=EXPECTED_ADMISSION_DIGEST,
        schema_version=(
            "fin_ia_0_1_s3_t09_layered_acceptance_final_"
            "fresh_exact_admission_issuance_v1_0"
        ),
        issuance_id=(
            "S3-T09-LAYERED-ACCEPTANCE-FINAL-EXACT-ADMISSION-ISSUANCE"
        ),
        user_instruction=(
            "生产 exact-live 9 Artifact 后报告结果"
        ),
        live_execution_authorized=True,
        next_action=(
            "S3-T09-LAYERED-ACCEPTANCE-FINAL-ONE-EXACT-LIVE-EXECUTION"
        ),
        expected_research_profile_ref=(
            S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V4_REF
        ),
    )
    issuance["layered_runtime_acceptance_contract"] = decision[
        "layered_runtime_acceptance_contract"
    ]
    issuance["supervision_v2_acceptance_contract"] = decision[
        "supervision_v2_acceptance_contract"
    ]
    issuance["zero_call_preflight"].update(
        {
            "exact_code_bindings_match": True,
            "host_capability_receipt_match": True,
            "research_profile_v4_bound": True,
        }
    )
    return payload, issuance


def main() -> int:
    payload, issuance = render_final_issuance()
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
