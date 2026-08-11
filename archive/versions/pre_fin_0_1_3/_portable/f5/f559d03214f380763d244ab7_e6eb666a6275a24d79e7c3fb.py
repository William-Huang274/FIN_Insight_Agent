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
from scripts.releases.issue_fin_ia_0_1_s4_t05_task_claim_link_policy_fresh_exact_admission import (
    verify_issued_admission,
)
from scripts.releases.run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution import (
    _load_admission,
    load_execution_target,
)
from scripts.releases.supervise_fin_ia_0_1_s3_t09_exact_live_execution import (
    _validate_host_capability_receipt,
)
from sec_agent.canonical_runtime.models import canonical_digest


DECISION = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_dell_task_claim_link_policy_r3_"
    "exact_live_execution_and_paired_assessment_"
    "authority_decision_v1_0.json"
)
PROGRAM_BACKLOG = (
    ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
)
DETAILED_BACKLOG = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
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
NEXT_ACTION = (
    "S4-T05-DELL-TASK-CLAIM-LINK-POLICY-R3-EXACT-LIVE-EXECUTION"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_R3_authority_is_exact_once_and_success_conditional() -> None:
    decision = _load(DECISION)
    authority = decision["authority"]
    stop = decision["stop_contract"]
    boundary = decision["decision_boundary"]

    assert decision["status"] == (
        "authorized_R3_exact_once_and_"
        "conditional_read_only_paired_assessment"
    )
    assert authority["R3_admission_exact_once_consumption_authorized"] is True
    assert authority["DELL_R3_exact_live_execution_authorized"] is True
    assert authority[
        "paired_assessment_authorized_only_after_coherent_terminal_success"
    ] is True
    assert authority[
        "automatic_retry_fallback_replay_relaunch_patch_or_rerun_authorized"
    ] is False
    assert authority["Human_review_or_owner_acceptance_authorized"] is False
    assert authority["S4_T06_or_later_authorized"] is False
    assert authority[
        "deferred_task_identity_taxonomy_or_cross_stage_redesign_authorized"
    ] is False
    assert stop["paired_assessment_after_failure_allowed"] is False
    assert stop["automatic_second_execution_allowed"] is False
    assert boundary["admission_consumed"] is False
    assert boundary["execution_started"] is False
    assert boundary["supervisor_launched"] is False


def test_R3_authority_binds_issued_admission_preflight_and_host() -> None:
    decision = _load(DECISION)
    source = decision["source_authority"]
    admission_path = ROOT / source["admission_ref"]
    issuance_path = ROOT / source["issuance_ref"]
    preflight_path = ROOT / source["preflight_ref"]
    host_path = ROOT / source["host_capability_receipt_ref"]
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(
        _load(admission_path)
    )
    target = load_execution_target(issuance_path)
    _, host_digest = _validate_host_capability_receipt(host_path)

    assert _sha256(admission_path) == source["admission_file_sha256"]
    assert _sha256(issuance_path) == source["issuance_file_sha256"]
    assert _sha256(preflight_path) == source["preflight_file_sha256"]
    assert _sha256(host_path) == source["host_capability_receipt_sha256"]
    assert host_digest == source["host_capability_receipt_sha256"]
    assert canonical_digest(admission.digest_payload()) == (
        source["admission_digest"]
    )
    assert _load_admission(admission_path, target) == admission
    if R3_FAILURE_RESULT.exists():
        failure = _load(R3_FAILURE_RESULT)
        assert failure["admission"]["consumed"] is True
        assert failure["identity"]["work_unit_id"] == target.work_unit_id
    else:
        assert verify_issued_admission()["fresh_identity_absent"] is True


def test_R3_execution_target_preflight_and_success_contract_are_closed() -> None:
    decision = _load(DECISION)
    target = decision["exact_execution_target"]
    verification = decision["pre_execution_verification"]
    success = decision["success_contract"]
    preflight = _load(ROOT / decision["source_authority"]["preflight_ref"])

    assert target["task_claim_link_policy_ref"] == (
        "fin01.s3.task_claim_link_policy:v1"
    )
    assert target["maximum_semantic_model_calls"] == 12
    assert target["maximum_provider_calls"] == 12
    assert target["maximum_network_calls"] == 12
    assert target["maximum_output_tokens"] == 16800
    assert target["maximum_total_cost_usd"] == 0.1
    assert target["transport_retry_count"] == 0
    assert target["source_network_calls_allowed"] is False
    assert target["external_tool_calls_allowed"] is False
    assert target["live_business_case_head_writes_allowed"] is False
    assert verification["project_os_full_chain_preflight"] == "pass"
    assert verification["open_full_chain_blocker_count"] == 0
    assert verification["exact_runner_zero_call_preflight"] == (
        "pass_exact_zero_call_execution_preflight"
    )
    assert verification["credential_present"] is True
    assert verification["credential_value_read_output_or_persisted"] is False
    assert verification["exact_code_binding_count"] == 7
    latest = _load(R7_BINDING_IMPLEMENTATION)
    for relative_path, expected_sha256 in verification[
        "exact_code_bindings"
    ].items():
        current_sha256 = _sha256(ROOT / relative_path)
        if current_sha256 != expected_sha256:
            assert latest["exact_code_bindings"][
                relative_path
            ] == current_sha256
    assert verification["target_work_unit_attempt_run_absent"] is True
    assert preflight["execution_state_counts_before"] == (
        preflight["execution_state_counts_after"]
    )
    assert set(preflight["observed_counts"].values()) == {0}
    assert success["artifact_count"] == 9
    assert success["semantic_model_call_count"] == 12
    assert success[
        "all_three_WWC_segments_consume_task_claim_link_policy"
    ] is True
    assert success["persisted_request_alias_residue"] == 0
    assert success["unknown_or_cross_Cell_task_claim_link_count"] == 0


def test_project_state_advances_only_to_exact_live_execution() -> None:
    decision = _load(DECISION)
    program = _load(PROGRAM_BACKLOG)
    detailed = _load(DETAILED_BACKLOG)
    detailed_t05 = next(
        row for row in detailed["tasks"] if row["item_id"] == "S4-T05"
    )

    assert decision["conditional_next_action"][
        "on_authority_decision_complete"
    ] == NEXT_ACTION
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
        else _load(R3_FAILURE_RESULT)["next_action"]
        if R3_FAILURE_RESULT.exists()
        else NEXT_ACTION
    )
    assert program["next_action"]["item_id"] == current_next
    assert detailed["current_next_action"] == current_next
    assert program["next_action"][
        "S4_T05_task_claim_R3_execution_authority_decision_ref"
    ] == DECISION.relative_to(ROOT).as_posix()
    assert detailed_t05["task_claim_R3_execution_authorized"] is True
    assert detailed_t05["task_claim_R3_execution_started"] is (
        R3_FAILURE_RESULT.exists()
    )
    assert detailed_t05["paired_assessment_performed"] is False
    assert detailed["non_inflation"]["DELL_R2"] is False
