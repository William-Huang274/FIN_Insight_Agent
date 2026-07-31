from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_contract_policies import (
    S3_SPECIALIST_WWC_JUDGMENT_ATOM_POLICY_REF,
    S4_DELL_THREE_CELL_RESEARCH_PROFILE_V2_REF,
    research_profile_for_ref,
    specialist_transport_contract,
)
from apps.workbench.backend.application.bounded_agent_executor import (
    S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V6_REF,
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V8_REF,
    S3ThreeCellBoundedAgentAdmission,
)
from scripts.releases.issue_fin_ia_0_1_s4_t05_specialist_wwc_judgment_atom_fresh_exact_admission import (
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
EXECUTION_AUTHORITY = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_specialist_wwc_judgment_"
    "atom_r6_exact_live_execution_and_paired_assessment_authority_"
    "decision_v1_0.json"
)
EXECUTION_FAILURE_RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_specialist_wwc_judgment_"
    "atom_r6_exact_live_execution_pre_admission_failure_result_v1_0.json"
)
ROOT_CAUSE_DISPOSITION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_r6_research_profile_v2_"
    "case_runtime_binding_mismatch_zero_call_root_cause_disposition_v1_0.json"
)
R7_BINDING_IMPLEMENTATION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_r7_profile_v2_versioned_"
    "case_runtime_binding_and_create_app_preflight_minimum_zero_call_"
    "implementation_v1_0.json"
)
EXPECTED_DIGEST = (
    "ac44bff5dda2911465859dc48dfbce44aefaa22533b74321c96fedc816a4b265"
)
EXPECTED_PROOF_SHA256 = (
    "c63c5f4e2e59e9ee57986ca03f9eb5da5f01bbd493eb6393b9a3e4049115ee3e"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_issued_R6_admission_is_exact_frozen_payload() -> None:
    proof = _load(PROOF_DECISION)
    payload = _load(ADMISSION)
    issuance = _load(ISSUANCE)
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(payload)

    admission.assert_profile_admissible()
    assert payload == proof["prospective_admission"]["payload"]
    assert canonical_digest(admission.digest_payload()) == EXPECTED_DIGEST
    assert (
        admission.transport_ref
        == S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V8_REF
    )
    assert (
        admission.research_profile_ref
        == S4_DELL_THREE_CELL_RESEARCH_PROFILE_V2_REF
    )
    assert (
        admission.wwc_judgment_atom_policy_ref
        == S3_SPECIALIST_WWC_JUDGMENT_ATOM_POLICY_REF
    )
    assert (
        admission.research_lead_transport_ref
        == S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V6_REF
    )
    assert specialist_transport_contract(
        admission.transport_ref
    ).what_would_change_judgment_atom_assembly is True
    assert _sha256(PROOF_DECISION) == EXPECTED_PROOF_SHA256
    assert issuance["source_proof_decision_sha256"] == EXPECTED_PROOF_SHA256


def test_issuance_verifier_proves_unconsumed_zero_call_state() -> None:
    r7_failure = (
        ROOT
        / "configs/releases/fin_ia_0_1_s4_t05_dell_r7_profile_v2_binding_exact_live_execution_failure_result_v1_0.json"
    )
    if r7_failure.exists():
        result = _load(ISSUANCE)
        assert result["status"] == "issued_unconsumed_zero_call_preflight_pass"
        assert result["proof_reverification"]["freshness_and_nonreuse"] == {
            "work_unit_absent": True,
            "attempt_absent": True,
            "research_run_absent": True,
            "prior_failed_runs_preserved": True,
        }
        assert result["observed_counts"]["provider_calls"] == 0
        assert result["next_action"] == NEXT_ACTION
    else:
        result = verify_issued_admission()
        assert result["status"] == "issued_unconsumed_zero_call_preflight_pass"
        assert result["fresh_identity_absent"] is True
        assert result["prior_runs_preserved"] is True
        assert result["provider_calls"] == 0
        assert result["next_action"] == NEXT_ACTION


def test_runner_loads_exact_R6_admission_without_execution() -> None:
    target = load_execution_target(ISSUANCE)
    admission = _load_admission(ADMISSION, target)
    proof = _load(PROOF_DECISION)
    profile = research_profile_for_ref(admission.research_profile_ref)

    assert target.admission_digest == EXPECTED_DIGEST
    assert target.work_unit_id == proof["fresh_identity"]["work_unit_id"]
    assert target.attempt_id == proof["fresh_identity"]["attempt_id"]
    assert target.research_run_id == proof["fresh_identity"][
        "research_run_id"
    ]
    assert target.maximum_output_tokens == 18000
    assert admission.admission_id == target.admission_id
    assert profile.aggregate_output_tokens(expanded_lead=True) == 18000


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


def test_project_state_advances_only_to_R6_execution_authority() -> None:
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
        else _load(ROOT_CAUSE_DISPOSITION)["next_action"]
        if ROOT_CAUSE_DISPOSITION.exists()
        else _load(EXECUTION_FAILURE_RESULT)["next_action"]
        if EXECUTION_FAILURE_RESULT.exists()
        else _load(EXECUTION_AUTHORITY)["next_action"]
        if EXECUTION_AUTHORITY.exists()
        else NEXT_ACTION
    )
    assert program["next_action"]["item_id"] == current_next
    assert detailed["current_next_action"] == current_next
    assert program["next_action"][
        "current_S4_T05_WWC_judgment_atom_prospective_admission_digest"
    ] == EXPECTED_DIGEST
    assert program["next_action"][
        "current_S4_T05_WWC_judgment_atom_prospective_admission_issued"
    ] is True
    assert program["next_action"][
        "current_S4_T05_WWC_judgment_atom_prospective_admission_consumed"
    ] is False
    assert detailed_t05[
        "WWC_judgment_atom_prospective_admission_issued"
    ] is True
    assert detailed_t05[
        "WWC_judgment_atom_prospective_admission_consumed"
    ] is False
    assert detailed_t05["WWC_judgment_atom_execution_started"] is False
    assert detailed_t05["paired_assessment_performed"] is False
    assert issuance["root_cause_disposition"]["DELL_R2_proven"] is False
