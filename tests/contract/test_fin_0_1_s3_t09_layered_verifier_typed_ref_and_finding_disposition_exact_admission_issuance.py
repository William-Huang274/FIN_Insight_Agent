from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_executor import (
    S3ThreeCellBoundedAgentAdmission,
)
from scripts.releases.issue_fin_ia_0_1_s3_t09_layered_verifier_typed_ref_and_finding_disposition_exact_admission import (
    ADMISSION,
    EXPECTED_ADMISSION_DIGEST,
    ISSUANCE,
    NEXT_ACTION,
)
from scripts.releases.run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution import (
    _load_admission,
    load_execution_target,
)
from sec_agent.canonical_runtime.models import canonical_digest


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_admission_is_issued_unconsumed_and_exactly_bound() -> None:
    issuance = _load(ISSUANCE)
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(
        _load(ADMISSION)
    )

    admission.assert_profile_admissible()
    assert issuance["status"] == "issued_unconsumed_zero_call_preflight_pass"
    assert canonical_digest(admission.digest_payload()) == (
        EXPECTED_ADMISSION_DIGEST
    )
    assert issuance["issued_admission"]["admission_digest"] == (
        EXPECTED_ADMISSION_DIGEST
    )
    assert issuance["issued_admission"]["consumed"] is False
    assert issuance["issued_admission"]["execution_started"] is False


def test_issuance_reproduced_proof_and_preserved_layered_contracts() -> None:
    issuance = _load(ISSUANCE)
    proof = issuance["proof_reverification"]
    typed_ref = issuance["verifier_typed_scoped_ref_acceptance_contract"]
    findings = issuance["finding_disposition_acceptance_contract"]
    supervision = issuance["supervision_v2_acceptance_contract"]

    assert proof["generator_rerun_before_materialization"] is True
    assert proof["frozen_and_regenerated_critical_sections_equal"] is True
    assert proof["double_prepare_equal"] is True
    assert proof["exact_code_binding_count"] == 7
    assert typed_ref["exact_membership_required"] is True
    assert typed_ref[
        "identity_guessing_normalization_or_silent_rewrite_allowed"
    ] is False
    assert findings["hard_integrity_requires_canonical_evidence"] is True
    assert findings["quality_findings_may_coexist_with_success_after_L1_pass"] is True
    assert supervision["contract_ref"] == "fin01.s3.exact_run_supervision:v2"
    assert supervision["host_capability_receipt_sha256"]


def test_issuance_loads_through_exact_runner_without_calls() -> None:
    issuance = _load(ISSUANCE)
    target = load_execution_target(ISSUANCE)
    admission = _load_admission(ADMISSION, target)

    assert target.work_unit_id == issuance["exact_binding"][
        "predicted_work_unit_id"
    ]
    assert target.attempt_id == issuance["exact_binding"][
        "predicted_attempt_id"
    ]
    assert target.research_run_id == issuance["exact_binding"][
        "predicted_research_run_id"
    ]
    assert admission.retry_budget == 0
    assert admission.max_transport_attempts_per_call == 1
    assert admission.max_provider_calls == 12
    assert admission.max_total_cost_usd == 0.10


def test_authority_allows_one_live_and_read_only_final_assessment() -> None:
    issuance = _load(ISSUANCE)
    authority = issuance["authority"]
    boundary = issuance["issuance_boundary"]

    assert authority[
        "admission_consumption_or_exact_live_execution_authorized"
    ] is True
    assert authority[
        "automatic_retry_fallback_patch_or_rerun_authorized"
    ] is False
    assert authority["paired_comparison_read_only_authorized_after_success"] is True
    assert authority["layered_T09_final_assessment_authorized_after_live"] is True
    assert authority["owner_acceptance_write_authorized"] is False
    assert boundary["admission_issued"] is True
    assert boundary["admission_consumed"] is False
    assert boundary["supervisor_launched"] is False
    assert issuance["next_action"] == NEXT_ACTION
