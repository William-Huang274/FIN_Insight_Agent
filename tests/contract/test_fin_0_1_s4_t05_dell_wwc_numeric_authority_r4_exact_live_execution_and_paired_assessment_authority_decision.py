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

from apps.workbench.backend.application.bounded_agent_contract_policies import (
    S3_TASK_CLAIM_LINK_POLICY_REF,
    S3_WHAT_WOULD_CHANGE_AUTHORITY_POLICY_REF,
)
from apps.workbench.backend.application.bounded_agent_executor import (
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF,
    S3ThreeCellBoundedAgentAdmission,
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
    "fin_ia_0_1_s4_t05_dell_wwc_numeric_authority_r4_"
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
NEXT_ACTION = (
    "S4-T05-DELL-WWC-NUMERIC-AUTHORITY-SURFACE-R4-"
    "EXACT-LIVE-EXECUTION"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_R4_authority_is_exact_once_and_success_conditional() -> None:
    decision = _load(DECISION)
    authority = decision["authority"]
    stop = decision["stop_contract"]
    boundary = decision["decision_boundary"]

    assert decision["status"] == (
        "authorized_R4_exact_once_and_"
        "conditional_read_only_paired_assessment"
    )
    assert authority["R4_admission_exact_once_consumption_authorized"] is True
    assert authority["DELL_R4_exact_live_execution_authorized"] is True
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
    assert set(boundary.values()) == {False}


def test_R4_authority_binds_issued_admission_preflight_and_host() -> None:
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


def test_R4_execution_target_preflight_and_success_contract_are_closed() -> None:
    decision = _load(DECISION)
    target = decision["exact_execution_target"]
    verification = decision["pre_execution_verification"]
    success = decision["success_contract"]
    preflight = _load(ROOT / decision["source_authority"]["preflight_ref"])
    latest = _load(R7_BINDING_IMPLEMENTATION)

    assert target["task_claim_link_policy_ref"] == (
        S3_TASK_CLAIM_LINK_POLICY_REF
    )
    assert target["what_would_change_authority_policy_ref"] == (
        S3_WHAT_WOULD_CHANGE_AUTHORITY_POLICY_REF
    )
    assert target["specialist_transport_ref"] == (
        S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF
    )
    assert (
        target["maximum_semantic_model_calls"],
        target["maximum_provider_calls"],
        target["maximum_network_calls"],
        target["maximum_output_tokens"],
        target["maximum_total_cost_usd"],
        target["transport_retry_count"],
    ) == (12, 12, 12, 16800, 0.1, 0)
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
    for relative_path, expected_sha256 in verification[
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
    assert verification["fresh_supervision_root_absent"] is True
    assert verification["target_work_unit_attempt_run_absent"] is True
    assert preflight["execution_state_counts_before"] == (
        preflight["execution_state_counts_after"]
    )
    assert set(preflight["observed_counts"].values()) == {0}
    assert (
        success["logical_node_count"],
        success["semantic_model_call_count"],
        success["artifact_count"],
    ) == (6, 12, 9)
    assert success[
        "all_three_WWC_segments_consume_task_claim_link_policy"
    ] is True
    assert success[
        "all_three_WWC_segments_consume_what_would_change_authority_policy"
    ] is True
    assert success["persisted_request_alias_residue"] == 0
    assert success["unknown_or_cross_Cell_task_claim_link_count"] == 0
    assert success["outside_or_cross_Cell_WWC_authority_link_count"] == 0


def test_project_state_advances_only_to_R4_exact_live_execution() -> None:
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
        _load(LATEST_RUNTIME_IMPLEMENTATION)["next_action"]
        if LATEST_RUNTIME_IMPLEMENTATION.exists()
        else _load(GAP_PROJECTION_DISPOSITION)["next_action"]
        if GAP_PROJECTION_DISPOSITION.exists()
        else
        _load(R4_FAILURE_RESULT)["next_action"]
        if R4_FAILURE_RESULT.exists()
        else NEXT_ACTION
    )
    assert program["next_action"]["item_id"] == current_next
    assert detailed["current_next_action"] == current_next
    assert program["next_action"][
        "S4_T05_WWC_numeric_authority_R4_execution_authority_decision_ref"
    ] == DECISION.relative_to(ROOT).as_posix()
    assert program["next_action"][
        "S4_T05_WWC_numeric_authority_R4_execution_authorized"
    ] is True
    assert detailed_t05[
        "WWC_numeric_authority_R4_execution_authorized"
    ] is True
    assert detailed_t05["WWC_numeric_authority_execution_started"] is (
        R4_FAILURE_RESULT.exists()
    )
    assert detailed_t05["fourth_execution_authorized"] is True
    assert detailed_t05["paired_assessment_performed"] is False
    assert detailed["non_inflation"]["DELL_R2"] is False
