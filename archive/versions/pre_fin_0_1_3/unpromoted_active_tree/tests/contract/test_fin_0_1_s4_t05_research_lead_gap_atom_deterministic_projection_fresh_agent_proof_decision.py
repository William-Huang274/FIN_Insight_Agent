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
)
from apps.workbench.backend.application.bounded_agent_executor import (
    S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V6_REF,
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF,
    S3ThreeCellBoundedAgentAdmission,
)
from scripts.releases.prepare_fin_ia_0_1_s4_t05_research_lead_gap_atom_projection_fresh_proof import (
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
    "S4-T05-DELL-RESEARCH-LEAD-GAP-ATOM-DETERMINISTIC-PROJECTION-"
    "FRESH-EXACT-ADMISSION-ISSUANCE-DECISION"
)
ISSUANCE = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_research_lead_gap_atom_"
    "deterministic_projection_fresh_exact_admission_issuance_v1_0.json"
)
EXECUTION_AUTHORITY_NEXT_ACTION = (
    "S4-T05-DELL-RESEARCH-LEAD-GAP-ATOM-DETERMINISTIC-PROJECTION-R5-"
    "EXACT-LIVE-EXECUTION-AND-SUCCESS-ONLY-PAIRED-ASSESSMENT-"
    "AUTHORITY-DECISION"
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


def test_two_independent_disposable_proofs_equal_frozen_decision() -> None:
    decision = _load(DECISION)
    if PROSPECTIVE_ADMISSION.exists():
        assert _load(PROSPECTIVE_ADMISSION) == decision[
            "prospective_admission"
        ]["payload"]
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

    assert identity["work_unit_id"] == "wu_p02_5_b63a5202479c6be6fcedbe94"
    assert identity["attempt_id"] == (
        "attempt_fin01_ba8728e601ea22f6592189e2"
    )
    assert identity["research_run_id"] == (
        "research_run_fin01_3ce365aa075bacbc2cc31346"
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
        "research_run_fin01_9f2cc1412a2fd495db65b8b4",
    }
    assert audit["canonical_database_file_unchanged"] is True
    assert audit["canonical_object_tree_unchanged"] is True
    assert audit["logical_snapshot_unchanged"] is True


def test_current_v6_projection_policy_is_reproved_without_case_branch() -> None:
    decision = _load(DECISION)
    reproof = decision["projection_policy_reproof"]
    implementation = _load(IMPLEMENTATION)
    audit = decision["implementation_reaudit"]
    policy = S3_RESEARCH_LEAD_GAP_ATOM_PROJECTION_POLICY

    assert audit["research_lead_transport_ref"] == (
        S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V6_REF
    )
    assert audit["implementation_contract_sha256"] == _sha256(
        IMPLEMENTATION
    )
    assert audit["exact_code_bindings"] == implementation[
        "exact_code_bindings"
    ]
    latest = _load(R7_BINDING_IMPLEMENTATION)
    for relative_path, expected_sha256 in audit[
        "exact_code_bindings"
    ].items():
        current_sha256 = _sha256(ROOT / relative_path)
        if current_sha256 != expected_sha256:
            assert latest["exact_code_bindings"][
                relative_path
            ] == current_sha256

    assert reproof["policy_ref"] == policy.policy_ref
    assert reproof["provider_field_id"] == "remaining_gap_atoms"
    assert reproof["canonical_field_id"] == "remaining_gaps"
    assert reproof["canonical_maximum"] == 4
    assert reproof["provider_atom_fields"] == list(policy.atom_fields)
    assert reproof["ranking_fields"] == list(policy.ranking_fields)
    assert reproof["all_candidates_validated_before_projection"] is True
    assert reproof["invalid_candidate_may_be_dropped"] is False
    assert reproof["DELL_case_or_provider_special_branch"] is False
    assert reproof[
        "v5_historical_hard_cardinality_behavior_preserved"
    ] is True


def test_prospective_r5_admission_is_valid_fresh_and_still_unissued() -> None:
    decision = _load(DECISION)
    prospective = decision["prospective_admission"]
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(
        prospective["payload"]
    )

    admission.assert_profile_admissible()
    assert admission.research_lead_transport_ref == (
        S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V6_REF
    )
    assert admission.transport_ref == (
        S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF
    )
    assert canonical_digest(admission.digest_payload()) == prospective[
        "digest"
    ]
    assert prospective["digest"] == (
        "378731667e55e56740b5fd2fcc81fc152e3b2da91e15230cc7db33a6034ca5db"
    )
    assert prospective["source_consumed_R4_admission_digest"] == (
        "45eef7b1150ee54b3680e69d98b0d8ba3db577dc1b4464649ff561a4e8354b8b"
    )
    assert prospective["prospective_admission_file_absent"] is True
    if ISSUANCE.exists():
        issuance = _load(ISSUANCE)
        assert _load(PROSPECTIVE_ADMISSION) == prospective["payload"]
        assert issuance["issued_admission"]["consumed"] is False
        assert issuance["issued_admission"]["execution_started"] is False
    else:
        assert PROSPECTIVE_ADMISSION.exists() is False
    assert (
        prospective["issued"],
        prospective["consumed"],
        prospective["execution_started"],
    ) == (False, False, False)
    assert set(decision["hard_boundaries"].values()) == {0}


def test_future_success_is_complete_product_gate_not_fixture_pass() -> None:
    decision = _load(DECISION)
    success = decision["future_success_contract"]

    assert (
        success["terminal_state"],
        success["logical_nodes"],
        success["provider_calls"],
        success["logical_artifact_families"],
    ) == ("succeeded", 6, 12, 9)
    assert success["research_lead_v6_consumed"] is True
    assert success[
        "all_gap_atom_candidates_validated_before_projection"
    ] is True
    assert success[
        "valid_overflow_records_nonterminal_L2_finding"
    ] is True
    assert success[
        "manifest_and_judgment_finding_parity_required"
    ] is True
    assert success["invalid_overflow_candidate_remains_hard_failure"] is True
    assert success["paired_assessment_only_after_coherent_success"] is True


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
        _load(R5_FAILURE_RESULT)["next_action"]
        if R5_FAILURE_RESULT.exists()
        else _load(R5_AUTHORITY_DECISION)["conditional_next_action"][
            "on_authority_decision_complete"
        ]
        if R5_AUTHORITY_DECISION.exists()
        else EXECUTION_AUTHORITY_NEXT_ACTION
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
