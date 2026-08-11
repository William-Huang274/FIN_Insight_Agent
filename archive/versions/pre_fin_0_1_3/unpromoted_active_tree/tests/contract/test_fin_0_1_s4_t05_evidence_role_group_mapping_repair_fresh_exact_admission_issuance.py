from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
R7_BINDING_IMPLEMENTATION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_r7_profile_v2_versioned_"
    "case_runtime_binding_and_create_app_preflight_minimum_zero_call_"
    "implementation_v1_0.json"
)
R7_EXACT_FAILURE_RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_r7_profile_v2_binding_"
    "exact_live_execution_failure_result_v1_0.json"
)
WWC_TRUNCATION_DISPOSITION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_specialist_wwc_judgment_atom_"
    "deterministic_assembly_fresh_agent_proof_decision_v1_0.json"
)
WWC_ATOM_ISSUANCE = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_r6_research_profile_v2_"
    "case_runtime_binding_mismatch_zero_call_root_cause_disposition_v1_0.json"
)
GAP_PROJECTION_R5_FAILURE_RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_research_lead_gap_atom_"
    "projection_r5_exact_live_execution_failure_result_v1_0.json"
)
GAP_PROJECTION_AUTHORITY = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_research_lead_gap_atom_"
    "projection_r5_exact_live_execution_and_paired_assessment_"
    "authority_decision_v1_0.json"
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

from apps.workbench.backend.application.bounded_agent_executor import (
    S3ThreeCellBoundedAgentAdmission,
)
from scripts.releases.run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution import (
    _load_admission,
    load_execution_target,
    preflight,
)
from sec_agent.canonical_runtime.models import canonical_digest


RUNTIME_ROOT = (
    ROOT
    / ".codex_runtime/"
    "fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1"
)
ADMISSION = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_dell_evidence_role_group_mapping_repair_"
    "fresh_exact_admission_r2.json"
)
ISSUANCE = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_evidence_role_group_mapping_repair_"
    "fresh_exact_admission_issuance_v1_0.json"
)
PROOF = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_evidence_role_group_mapping_repair_"
    "fresh_agent_proof_decision_v1_0.json"
)
TASK_CLAIM_IMPLEMENTATION = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_task_claim_link_policy_minimum_"
    "zero_call_implementation_v1_0.json"
)
TASK_CLAIM_PROOF = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_task_claim_link_policy_"
    "fresh_agent_proof_decision_v1_0.json"
)
TASK_CLAIM_ISSUANCE = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_task_claim_link_policy_"
    "fresh_exact_admission_issuance_v1_0.json"
)
TASK_CLAIM_AUTHORITY = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_dell_task_claim_link_policy_r3_"
    "exact_live_execution_and_paired_assessment_"
    "authority_decision_v1_0.json"
)
R3_FAILURE_RESULT = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_dell_task_claim_link_policy_r3_"
    "exact_live_execution_failure_result_v1_0.json"
)
NUMERIC_AUTHORITY_DISPOSITION = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_dell_wwc_numeric_authority_surface_"
    "zero_call_root_cause_disposition_v1_0.json"
)
NUMERIC_AUTHORITY_IMPLEMENTATION = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_specialist_wwc_judgment_atom_deterministic_"
    "task_assembly_minimum_zero_call_implementation_v1_0.json"
)
NUMERIC_AUTHORITY_PROOF = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_wwc_numeric_authority_surface_fresh_agent_"
    "proof_decision_v1_0.json"
)
NUMERIC_AUTHORITY_ISSUANCE = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_wwc_numeric_authority_surface_fresh_exact_"
    "admission_issuance_v1_0.json"
)
NUMERIC_AUTHORITY_DECISION = (
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
DRIFT_AUDIT = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_replacement_admission_pre_issuance_"
    "physical_digest_drift_audit_v1_0.json"
)
PROGRAM_BACKLOG = (
    ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
)
DETAILED_BACKLOG = (
    ROOT / "configs/releases/fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
)
EXPECTED_DIGEST = (
    "058c579211eb1f4573959d86f0b904b64e2535e749631ab7ee208571ef601af3"
)
NEXT_ACTION = (
    "S4-T05-DELL-REPLACEMENT-EXACT-R2-EXECUTION-AND-"
    "PAIRED-ASSESSMENT-AUTHORITY-DECISION"
)
POST_FAILURE_NEXT_ACTION = (
    "S4-T05-DELL-WWC-TASK-TO-CLAIM-CLOSED-IDENTITY-"
    "ZERO-CALL-ROOT-CAUSE-DISPOSITION-DECISION"
)
POST_IMPLEMENTATION_NEXT_ACTION = (
    "S4-T05-DELL-WWC-TASK-TO-CLAIM-CLOSED-IDENTITY-"
    "FRESH-AGENT-PROOF-DECISION"
)
POST_PROOF_NEXT_ACTION = (
    "S4-T05-DELL-WWC-TASK-TO-CLAIM-CLOSED-IDENTITY-"
    "FRESH-EXACT-ADMISSION-ISSUANCE-DECISION"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_replacement_admission_is_issued_unconsumed_and_digest_bound() -> None:
    issuance = _load(ISSUANCE)
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(
        _load(ADMISSION)
    )

    admission.assert_profile_admissible()
    assert issuance["status"] == "issued_unconsumed_zero_call_preflight_pass"
    assert canonical_digest(admission.digest_payload()) == EXPECTED_DIGEST
    assert issuance["issued_admission"]["admission_digest"] == EXPECTED_DIGEST
    assert issuance["issued_admission"]["consumed"] is False
    assert issuance["issued_admission"]["execution_started"] is False


def test_issuance_rebinds_fresh_identity_and_three_dispatch_digests() -> None:
    issuance = _load(ISSUANCE)
    proof = _load(PROOF)
    binding = issuance["exact_binding"]
    fresh = proof["fresh_identity"]

    assert binding["predicted_work_unit_id"] == fresh["work_unit_id"]
    assert binding["predicted_attempt_id"] == fresh["attempt_id"]
    assert binding["predicted_research_run_id"] == fresh["research_run_id"]
    assert binding["input_digest"] == fresh["input_digest"]
    assert binding["preparation_digest"] == fresh["preparation_digest"]
    assert binding["role_group_mapping_digest"] == (
        fresh["role_group_mapping_digest"]
    )
    assert binding["evidence_alignment_digest"] == (
        fresh["evidence_alignment_digest"]
    )
    assert binding["evidence_dispatch_digest"] == (
        fresh["evidence_dispatch_digest"]
    )
    assert issuance["proof_reverification"][
        "mapping_alignment_dispatch_digests_equal"
    ] is True
    assert all(
        issuance["proof_reverification"]["freshness_and_nonreuse"].values()
    )


def test_pre_issuance_physical_drift_is_benign_and_bound() -> None:
    issuance = _load(ISSUANCE)
    audit = _load(DRIFT_AUDIT)
    classification = audit["classification"]

    assert audit["status"] == (
        "pass_benign_sqlite_physical_digest_drift_"
        "logical_identity_and_object_tree_unchanged"
    )
    assert classification["prior_canonical_database_sha256"] != (
        classification["current_canonical_database_sha256"]
    )
    assert classification["canonical_object_tree_sha256_unchanged"] is True
    assert classification["logical_snapshot_digest_unchanged"] is True
    assert classification["research_or_execution_logical_state_drift_observed"] is False
    assert issuance["physical_digest_drift_audit_sha256"] == (
        _sha256(DRIFT_AUDIT)
    )
    assert issuance["proof_reverification"]["target_database_sha256"] == (
        classification["current_canonical_database_sha256"]
    )


def test_issuance_binds_current_code_and_source_contracts() -> None:
    issuance = _load(ISSUANCE)
    bindings = issuance["proof_reverification"]["exact_code_bindings"]
    task_claim_implementation = _load(TASK_CLAIM_IMPLEMENTATION)
    latest_implementation = _load(R7_BINDING_IMPLEMENTATION)
    allowed_changed_paths = set(
        latest_implementation["historical_exact_binding_supersession"][
            "allowed_changed_paths"
        ]
    ) | set(
        task_claim_implementation["historical_exact_binding_supersession"][
            "allowed_changed_paths"
        ]
    )

    assert issuance["source_proof_decision_sha256"] == _sha256(PROOF)
    assert issuance["proof_reverification"]["exact_code_binding_count"] == 9
    for relative_path, expected_sha256 in bindings.items():
        current_sha256 = _sha256(ROOT / relative_path)
        if current_sha256 != expected_sha256:
            assert relative_path in allowed_changed_paths
    for relative_path, expected_sha256 in task_claim_implementation[
        "exact_code_bindings"
    ].items():
        current_sha256 = _sha256(ROOT / relative_path)
        if current_sha256 != expected_sha256:
            assert latest_implementation["exact_code_bindings"][
                relative_path
            ] == current_sha256


def test_consumed_replacement_identity_cannot_pass_preflight_again(
    tmp_path: Path,
    monkeypatch,
) -> None:
    target = load_execution_target(ISSUANCE)
    admission = _load_admission(ADMISSION, target)
    clone_runtime = tmp_path / RUNTIME_ROOT.name
    shutil.copytree(RUNTIME_ROOT, clone_runtime)
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv(str(admission.api_key_env), "fixture-not-a-real-key")

    with pytest.raises(
        RuntimeError,
        match="s3_t09_exact_execution_identity_already_consumed",
    ):
        preflight(
            clone_runtime,
            ADMISSION,
            target,
            output_prefix="s4_t05_replacement_issuance_fixture",
        )

    failure = _load(
        ROOT
        / "configs/releases/"
        "fin_ia_0_1_s4_t05_dell_replacement_exact_r2_"
        "execution_failure_result_v1_0.json"
    )
    assert failure["admission"]["admission_digest"] == EXPECTED_DIGEST
    assert failure["admission"]["consumed"] is True
    assert failure["identity"]["research_run_id"] == target.research_run_id
    assert failure["stop_contract_observation"]["rerun_count"] == 0


def test_historical_issuance_boundary_is_preserved_after_exact_live() -> None:
    issuance = _load(ISSUANCE)
    authority = issuance["authority"]
    boundary = issuance["issuance_boundary"]
    program = _load(PROGRAM_BACKLOG)
    detailed = _load(DETAILED_BACKLOG)

    assert authority["replacement_exact_admission_issuance_authorized"] is True
    assert authority[
        "admission_consumption_or_exact_live_execution_authorized"
    ] is False
    assert authority["paired_assessment_or_Human_review_authorized"] is False
    assert boundary["admission_issued"] is True
    assert boundary["admission_consumed"] is False
    assert boundary["execution_started"] is False
    assert issuance["next_action"] == NEXT_ACTION
    expected_current_next = (
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
        _load(NUMERIC_AUTHORITY_IMPLEMENTATION)["next_action"]
        if NUMERIC_AUTHORITY_IMPLEMENTATION.exists()
        else _load(GAP_PROJECTION_DISPOSITION)["next_action"]
        if GAP_PROJECTION_DISPOSITION.exists()
        else
        _load(R4_FAILURE_RESULT)["next_action"]
        if R4_FAILURE_RESULT.exists()
        else _load(NUMERIC_AUTHORITY_DECISION)["conditional_next_action"][
            "on_authority_decision_complete"
        ]
        if NUMERIC_AUTHORITY_DECISION.exists()
        else _load(NUMERIC_AUTHORITY_ISSUANCE)["next_action"]
        if NUMERIC_AUTHORITY_ISSUANCE.exists()
        else _load(NUMERIC_AUTHORITY_PROOF)["next_action"]
        if NUMERIC_AUTHORITY_PROOF.exists()
        else _load(NUMERIC_AUTHORITY_IMPLEMENTATION)["next_action"]
        if NUMERIC_AUTHORITY_IMPLEMENTATION.exists()
        else
        _load(NUMERIC_AUTHORITY_DISPOSITION)["next_action"]
        if NUMERIC_AUTHORITY_DISPOSITION.exists()
        else
        _load(R3_FAILURE_RESULT)["next_action"]
        if R3_FAILURE_RESULT.exists()
        else
        _load(TASK_CLAIM_AUTHORITY)["conditional_next_action"][
            "on_authority_decision_complete"
        ]
        if TASK_CLAIM_AUTHORITY.exists()
        else
        _load(TASK_CLAIM_ISSUANCE)["next_action"]
        if TASK_CLAIM_ISSUANCE.exists()
        else
        POST_PROOF_NEXT_ACTION
        if TASK_CLAIM_PROOF.exists()
        else POST_IMPLEMENTATION_NEXT_ACTION
        if TASK_CLAIM_IMPLEMENTATION.exists()
        else POST_FAILURE_NEXT_ACTION
    )
    assert program["next_action"]["item_id"] == expected_current_next
    assert detailed["current_next_action"] == expected_current_next
    expected_current_status = (
        "R7_terminal_failed_post_verifier_RC_P36_064_"
        "zero_call_disposition_pending"
        if R7_EXACT_FAILURE_RESULT.exists()
        else
        "RC_P36_063_profile_overlay_create_app_preflight_"
        "fixture_proven_fresh_agent_proof_pending"
        if R7_BINDING_IMPLEMENTATION.exists()
        else
        "RC_P36_063_profile_overlay_create_app_preflight_"
        "implementation_pending"
        if WWC_ATOM_ISSUANCE.exists()
        else
        "RC_P36_062_WWC_judgment_atom_fresh_proof_contract_frozen_"
        "admission_issuance_pending"
        if WWC_TRUNCATION_DISPOSITION.exists()
        else
        "RC_P36_062_specialist_v7_WWC_segment_truncation_"
        "disposition_pending"
        if GAP_PROJECTION_R5_FAILURE_RESULT.exists()
        else
        "RC_P36_061_gap_atom_projection_R5_exact_live_authorized_"
        "execution_not_started"
        if GAP_PROJECTION_AUTHORITY.exists()
        else
        "RC_P36_061_gap_atom_projection_R5_admission_issued_unconsumed_"
        "execution_authority_pending"
        if GAP_PROJECTION_ISSUANCE.exists()
        else
        "RC_P36_061_gap_atom_projection_fresh_proof_pass_"
        "admission_issuance_pending"
        if GAP_PROJECTION_FRESH_PROOF.exists()
        else
        "RC_P36_061_gap_atom_projection_implementation_fixture_proven_"
        "fresh_proof_pending"
        if NUMERIC_AUTHORITY_IMPLEMENTATION.exists()
        else
        "RC_P36_061_gap_atom_deterministic_projection_selected_"
        "implementation_pending"
        if GAP_PROJECTION_DISPOSITION.exists()
        else
        "RC_P36_061_research_lead_remaining_gaps_cardinality_"
        "disposition_pending"
        if R4_FAILURE_RESULT.exists()
        else "RC_P36_060_WWC_authority_R4_exact_live_authorized_"
        "execution_not_started"
        if NUMERIC_AUTHORITY_DECISION.exists()
        else
        "RC_P36_060_WWC_authority_R4_admission_issued_unconsumed_"
        "execution_authority_pending"
        if NUMERIC_AUTHORITY_ISSUANCE.exists()
        else "RC_P36_060_WWC_authority_fresh_proof_contract_frozen_"
        "admission_issuance_pending"
        if NUMERIC_AUTHORITY_PROOF.exists()
        else "RC_P36_060_shared_WWC_authority_runtime_injected_"
        "fixture_proven_fresh_agent_proof_pending"
        if NUMERIC_AUTHORITY_IMPLEMENTATION.exists()
        else
        "RC_P36_060_root_cause_disposed_minimum_shared_WWC_authority_"
        "policy_selected_implementation_pending"
        if NUMERIC_AUTHORITY_DISPOSITION.exists()
        else
        "RC_P36_060_open_zero_call_root_cause_disposition_pending"
        if R3_FAILURE_RESULT.exists()
        else
        "RC_P36_059_task_claim_R3_exact_live_authorized_not_started"
        if TASK_CLAIM_AUTHORITY.exists()
        else
        "RC_P36_059_task_claim_R3_admission_issued_unconsumed_"
        "execution_authority_pending"
        if TASK_CLAIM_ISSUANCE.exists()
        else
        "RC_P36_059_task_claim_fresh_proof_contract_frozen_"
        "admission_issuance_pending"
        if TASK_CLAIM_PROOF.exists()
        else "RC_P36_059_minimum_shared_policy_runtime_injected_"
        "fixture_proven_fresh_agent_proof_pending"
        if TASK_CLAIM_IMPLEMENTATION.exists()
        else "replacement_exact_terminal_failed_WWC_unknown_claim_link_"
        "root_cause_disposition_pending"
    )
    assert program["next_action"]["status"] == expected_current_status
