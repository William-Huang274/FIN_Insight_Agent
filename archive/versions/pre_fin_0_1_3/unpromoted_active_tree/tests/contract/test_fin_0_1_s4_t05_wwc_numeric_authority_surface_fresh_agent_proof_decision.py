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
GAP_PROJECTION_AUTHORITY = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_research_lead_gap_atom_"
    "projection_r5_exact_live_execution_and_paired_assessment_"
    "authority_decision_v1_0.json"
)
GAP_PROJECTION_R5_FAILURE_RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_research_lead_gap_atom_"
    "projection_r5_exact_live_execution_failure_result_v1_0.json"
)
GAP_PROJECTION_ISSUANCE = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_research_lead_gap_atom_"
    "deterministic_projection_fresh_exact_admission_issuance_v1_0.json"
)
GAP_PROJECTION_FRESH_PROOF = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_research_lead_gap_atom_"
    "deterministic_projection_fresh_agent_proof_decision_v1_0.json"
)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_contract_policies import (
    S3_WHAT_WOULD_CHANGE_AUTHORITY_POLICY_REF,
)
from apps.workbench.backend.application.bounded_agent_executor import (
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF,
    S3ThreeCellBoundedAgentAdmission,
)
from scripts.releases.prepare_fin_ia_0_1_s4_t05_wwc_numeric_authority_surface_fresh_proof import (
    DECISION,
    IMPLEMENTATION,
    PROSPECTIVE_ADMISSION,
    build_decision,
)
from sec_agent.canonical_runtime.models import canonical_digest


PROGRAM_BACKLOG = (
    ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
)
DETAILED_BACKLOG = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
)
NEXT_ACTION = (
    "S4-T05-DELL-WWC-NUMERIC-AUTHORITY-SURFACE-"
    "FRESH-EXACT-ADMISSION-ISSUANCE-DECISION"
)
ISSUANCE = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_wwc_numeric_authority_surface_"
    "fresh_exact_admission_issuance_v1_0.json"
)
AUTHORITY = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_dell_wwc_numeric_authority_r4_exact_live_"
    "execution_and_paired_assessment_authority_decision_v1_0.json"
)
R4_FAILURE_RESULT = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_dell_wwc_numeric_authority_r4_"
    "exact_live_execution_failure_result_v1_0.json"
)
GAP_PROJECTION_DISPOSITION = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_dell_research_lead_remaining_gaps_cardinality_"
    "zero_call_root_cause_disposition_v1_0.json"
)
LATEST_RUNTIME_IMPLEMENTATION = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_specialist_wwc_judgment_atom_deterministic_"
    "task_assembly_minimum_zero_call_implementation_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_two_independent_disposable_proofs_equal_frozen_decision() -> None:
    decision = _load(DECISION)
    if PROSPECTIVE_ADMISSION.exists():
        assert _load(PROSPECTIVE_ADMISSION) == decision[
            "prospective_admission"
        ]["payload"]
        assert _load(ISSUANCE)["source_proof_decision_sha256"] == _sha256(
            DECISION
        )
        return
    regenerated = build_decision()

    assert regenerated == decision
    assert decision["proof_generator"]["independent_invocations"] == 2
    assert decision["proof_generator"]["independent_outputs_equal"] is True
    assert decision["proof_generator"]["sha256"] == _sha256(
        ROOT / decision["proof_generator"]["ref"]
    )


def test_fresh_identity_is_nonreused_and_target_is_read_only() -> None:
    decision = _load(DECISION)
    identity = decision["fresh_identity"]
    freshness = decision["freshness_and_nonreuse"]
    audit = decision["target_read_only_audit"]

    assert identity["work_unit_id"] == "wu_p02_5_d85b3ee8e94cd729074fc272"
    assert identity["attempt_id"] == (
        "attempt_fin01_3c963494980cb5a28a467832"
    )
    assert identity["research_run_id"] == (
        "research_run_fin01_9f2cc1412a2fd495db65b8b4"
    )
    assert (
        freshness["work_unit_absent"],
        freshness["attempt_absent"],
        freshness["research_run_absent"],
        freshness["prior_failed_run_reused"],
    ) == (True, True, True, False)
    assert set(freshness["prior_failed_run_ids_preserved"]) == {
        "research_run_fin01_9756044e7d7f23b3ff9fb395",
        "research_run_fin01_8905466e65d6259e54d42f6c",
    }
    assert audit["canonical_database_file_unchanged"] is True
    assert audit["canonical_object_tree_unchanged"] is True
    assert audit["logical_snapshot_unchanged"] is True


def test_WWC_authority_contract_is_reproved_from_current_DELL_input() -> None:
    decision = _load(DECISION)
    reproof = decision["WWC_authority_reproof"]
    implementation = _load(IMPLEMENTATION)
    audit = decision["implementation_reaudit"]
    latest = _load(R7_BINDING_IMPLEMENTATION)

    assert reproof["contract_ref"] == (
        S3_WHAT_WOULD_CHANGE_AUTHORITY_POLICY_REF
    )
    assert reproof["single_membership_owner"] == "cell_input.authority_refs"
    assert reproof["allowed_authority_classes"] == [
        "Evidence",
        "Numeric",
        "Candidate",
        "Graph",
    ]
    assert reproof["DELL_demand_numeric_ref_count"] == 6
    assert reproof[
        "provider_prompt_and_local_validator_surface_equal"
    ] is True
    assert reproof["legacy_numeric_input_membership_owner"] is False
    assert audit["implementation_contract_sha256"] == _sha256(
        IMPLEMENTATION
    )
    assert audit["exact_code_bindings"] == implementation[
        "exact_code_bindings"
    ]
    for relative_path, expected_sha256 in audit[
        "exact_code_bindings"
    ].items():
        current_sha256 = _sha256(ROOT / relative_path)
        if current_sha256 != expected_sha256:
            assert relative_path in latest[
                "historical_exact_binding_supersession"
            ]["allowed_changed_paths"]
            assert latest["exact_code_bindings"][
                relative_path
            ] == current_sha256


def test_prospective_admission_is_valid_fresh_and_still_unissued() -> None:
    decision = _load(DECISION)
    prospective = decision["prospective_admission"]
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(
        prospective["payload"]
    )

    admission.assert_profile_admissible()
    assert admission.transport_ref == (
        S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF
    )
    assert canonical_digest(admission.digest_payload()) == prospective[
        "digest"
    ]
    assert prospective["digest"] == (
        "45eef7b1150ee54b3680e69d98b0d8ba3db577dc1b4464649ff561a4e8354b8b"
    )
    assert prospective["source_consumed_admission_digest"] == (
        "4be4fa99479da78547bfc9266c708478aa524d459db97c7341799b2724a7f29d"
    )
    assert prospective["prospective_admission_file_absent"] is True
    assert PROSPECTIVE_ADMISSION.exists() is ISSUANCE.exists()
    assert (
        prospective["issued"],
        prospective["consumed"],
        prospective["execution_started"],
    ) == (False, False, False)
    assert set(decision["hard_boundaries"].values()) == {0}


def test_decision_advances_only_to_separate_admission_issuance() -> None:
    decision = _load(DECISION)
    program = _load(PROGRAM_BACKLOG)
    detailed = _load(DETAILED_BACKLOG)

    assert decision["status"] == (
        "pass_zero_call_independent_fresh_proof_contract_frozen_"
        "admission_issuance_pending_separate_authority"
    )
    assert decision["next_action"] == NEXT_ACTION
    current_next = (
        _load(ROOT / "configs/releases/fin_ia_0_1_s4_t05_dell_r7_profile_v2_binding_exact_live_execution_failure_result_v1_0.json")["next_action"]
        if R7_BINDING_IMPLEMENTATION.exists()
        else _load(WWC_ATOM_ISSUANCE)["next_action"]
        if WWC_ATOM_ISSUANCE.exists()
        else _load(WWC_TRUNCATION_DISPOSITION)["next_action"]
        if WWC_TRUNCATION_DISPOSITION.exists()
        else
        _load(GAP_PROJECTION_R5_FAILURE_RESULT)["next_action"]
        if GAP_PROJECTION_R5_FAILURE_RESULT.exists()
        else _load(GAP_PROJECTION_AUTHORITY)["conditional_next_action"][
            "on_authority_decision_complete"
        ]
        if GAP_PROJECTION_AUTHORITY.exists()
        else _load(GAP_PROJECTION_ISSUANCE)["next_action"]
        if GAP_PROJECTION_ISSUANCE.exists()
        else _load(GAP_PROJECTION_FRESH_PROOF)["next_action"]
        if GAP_PROJECTION_FRESH_PROOF.exists()
        else
        _load(LATEST_RUNTIME_IMPLEMENTATION)["next_action"]
        if LATEST_RUNTIME_IMPLEMENTATION.exists()
        else _load(GAP_PROJECTION_DISPOSITION)["next_action"]
        if GAP_PROJECTION_DISPOSITION.exists()
        else
        _load(R4_FAILURE_RESULT)["next_action"]
        if R4_FAILURE_RESULT.exists()
        else _load(AUTHORITY)["conditional_next_action"][
            "on_authority_decision_complete"
        ]
        if AUTHORITY.exists()
        else _load(ISSUANCE)["next_action"]
        if ISSUANCE.exists()
        else NEXT_ACTION
    )
    assert program["next_action"]["item_id"] == current_next
    assert detailed["current_next_action"] == current_next
    assert decision["experiment_governance"][
        "admission_issuance_authorized"
    ] is False
    assert decision["experiment_governance"][
        "live_execution_authorized"
    ] is False
    assert decision["root_cause_disposition"]["DELL_R2_proven"] is False
