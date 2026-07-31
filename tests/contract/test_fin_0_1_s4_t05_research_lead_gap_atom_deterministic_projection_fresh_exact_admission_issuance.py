from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
R7_BINDING_IMPLEMENTATION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_r7_profile_v2_versioned_"
    "case_runtime_binding_and_create_app_preflight_minimum_zero_call_"
    "implementation_v1_0.json"
)
WWC_TRUNCATION_DISPOSITION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_specialist_wwc_judgment_atom_"
    "deterministic_assembly_fresh_agent_proof_decision_v1_0.json"
)
WWC_ATOM_ISSUANCE = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_r6_research_profile_v2_"
    "case_runtime_binding_mismatch_zero_call_root_cause_disposition_v1_0.json"
)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_contract_policies import (
    S3_RESEARCH_LEAD_GAP_ATOM_PROJECTION_POLICY,
    research_lead_transport_contract,
)
from apps.workbench.backend.application.bounded_agent_executor import (
    S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V6_REF,
    S3ThreeCellBoundedAgentAdmission,
)
from scripts.releases.issue_fin_ia_0_1_s4_t05_research_lead_gap_atom_projection_fresh_exact_admission import (
    ADMISSION,
    ISSUANCE,
    NEXT_ACTION,
    PROOF_DECISION,
    verify_issued_admission,
)
from scripts.releases.run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution import (
    _load_admission,
    load_execution_target,
)
from sec_agent.canonical_runtime.models import canonical_digest


PROGRAM_BACKLOG = (
    ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
)
DETAILED_BACKLOG = ROOT / (
    "configs/releases/fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
)
EXPECTED_DIGEST = (
    "378731667e55e56740b5fd2fcc81fc152e3b2da91e15230cc7db33a6034ca5db"
)
EXPECTED_PROOF_SHA256 = (
    "11e14945d570eba841772dcb25861c75ec62d3cc2de5fda2624a6e03ccdf4aa9"
)
R5_AUTHORITY_DECISION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_research_lead_gap_atom_"
    "projection_r5_exact_live_execution_and_paired_assessment_"
    "authority_decision_v1_0.json"
)
R5_FAILURE_RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_research_lead_gap_atom_"
    "projection_r5_exact_live_execution_failure_result_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_issued_R5_admission_is_exact_frozen_payload() -> None:
    proof = _load(PROOF_DECISION)
    payload = _load(ADMISSION)
    issuance = _load(ISSUANCE)
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(payload)

    admission.assert_profile_admissible()
    assert payload == proof["prospective_admission"]["payload"]
    assert canonical_digest(admission.digest_payload()) == EXPECTED_DIGEST
    assert (
        admission.research_lead_transport_ref
        == S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V6_REF
    )
    assert research_lead_transport_contract(
        admission.research_lead_transport_ref
    ).gap_atom_deterministic_projection is True
    assert issuance["exact_binding"][
        "research_lead_gap_atom_projection_policy_ref"
    ] == S3_RESEARCH_LEAD_GAP_ATOM_PROJECTION_POLICY.policy_ref
    assert _sha256(PROOF_DECISION) == EXPECTED_PROOF_SHA256
    assert issuance["source_proof_decision_sha256"] == EXPECTED_PROOF_SHA256


def test_issuance_verifier_proves_unconsumed_zero_call_state() -> None:
    if R5_FAILURE_RESULT.exists():
        failure = _load(R5_FAILURE_RESULT)
        proof = _load(PROOF_DECISION)
        assert failure["admission"]["consumed"] is True
        assert failure["admission"]["admission_digest"] == EXPECTED_DIGEST
        assert (
            failure["identity"]["work_unit_id"]
            == proof["fresh_identity"]["work_unit_id"]
        )
        return

    result = verify_issued_admission()

    assert result["status"] == "issued_unconsumed_zero_call_preflight_pass"
    assert result["fresh_identity_absent"] is True
    assert result["prior_runs_preserved"] is True
    assert result["provider_calls"] == 0
    assert result["next_action"] == NEXT_ACTION


def test_runner_loads_exact_R5_admission_without_execution() -> None:
    target = load_execution_target(ISSUANCE)
    admission = _load_admission(ADMISSION, target)
    proof = _load(PROOF_DECISION)

    assert target.admission_digest == EXPECTED_DIGEST
    assert target.work_unit_id == proof["fresh_identity"]["work_unit_id"]
    assert target.attempt_id == proof["fresh_identity"]["attempt_id"]
    assert target.research_run_id == proof["fresh_identity"][
        "research_run_id"
    ]
    assert target.maximum_output_tokens == 16800
    assert admission.admission_id == target.admission_id


def test_issuance_boundary_excludes_execution_and_deferred_work() -> None:
    issuance = _load(ISSUANCE)
    authority = issuance["authority"]
    boundary = issuance["issuance_boundary"]
    counts = issuance["observed_counts"]

    assert authority["fresh_exact_admission_issuance_authorized"] is True
    assert authority[
        "admission_consumption_or_exact_live_execution_authorized"
    ] is False
    assert authority[
        "paired_assessment_or_Human_review_authorized"
    ] is False
    assert authority["S4_T06_or_later_authorized"] is False
    assert boundary["admission_issued"] is True
    assert boundary["admission_consumed"] is False
    assert boundary["execution_started"] is False
    assert boundary["deferred_sequence_work_reentered"] is False
    assert counts["new_admissions"] == 1
    assert set(
        value for key, value in counts.items() if key != "new_admissions"
    ) == {0}


def test_project_state_advances_only_to_R5_execution_authority() -> None:
    issuance = _load(ISSUANCE)
    program = _load(PROGRAM_BACKLOG)
    detailed = _load(DETAILED_BACKLOG)
    detailed_t05 = next(
        item for item in detailed["tasks"] if item["item_id"] == "S4-T05"
    )

    assert issuance["next_action"] == NEXT_ACTION
    current_next = (
        _load(ROOT / "configs/releases/fin_ia_0_1_s4_t05_dell_r7_profile_v2_binding_exact_live_execution_failure_result_v1_0.json")["next_action"]
        if R7_BINDING_IMPLEMENTATION.exists()
        else _load(WWC_ATOM_ISSUANCE)["next_action"]
        if WWC_ATOM_ISSUANCE.exists()
        else _load(WWC_TRUNCATION_DISPOSITION)["next_action"]
        if WWC_TRUNCATION_DISPOSITION.exists()
        else
        _load(R5_FAILURE_RESULT)["next_action"]
        if R5_FAILURE_RESULT.exists()
        else _load(R5_AUTHORITY_DECISION)["conditional_next_action"][
            "on_authority_decision_complete"
        ]
        if R5_AUTHORITY_DECISION.exists()
        else NEXT_ACTION
    )
    assert program["next_action"]["item_id"] == current_next
    assert detailed["current_next_action"] == current_next
    assert program["next_action"][
        "S4_T05_gap_projection_admission_digest"
    ] == EXPECTED_DIGEST
    assert program["next_action"][
        "S4_T05_gap_projection_prospective_admission_issued"
    ] is True
    assert program["next_action"][
        "S4_T05_gap_projection_prospective_admission_consumed"
    ] is R5_FAILURE_RESULT.exists()
    assert program["next_action"][
        "S4_T05_gap_projection_execution_started"
    ] is R5_FAILURE_RESULT.exists()
    assert detailed_t05[
        "gap_projection_prospective_admission_issued"
    ] is True
    assert detailed_t05[
        "gap_projection_prospective_admission_consumed"
    ] is R5_FAILURE_RESULT.exists()
    assert (
        detailed_t05["gap_projection_execution_started"]
        is R5_FAILURE_RESULT.exists()
    )
    assert detailed_t05["paired_assessment_performed"] is False
    assert issuance["root_cause_disposition"]["DELL_R2_proven"] is False
