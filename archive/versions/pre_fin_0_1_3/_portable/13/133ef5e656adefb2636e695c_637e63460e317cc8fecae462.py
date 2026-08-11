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
R5_FAILURE_RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_research_lead_gap_atom_"
    "projection_r5_exact_live_execution_failure_result_v1_0.json"
)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_contract_policies import (
    S3_RESEARCH_LEAD_GAP_ATOM_PROJECTION_POLICY,
    S3_TASK_CLAIM_LINK_POLICY_REF,
    S3_WHAT_WOULD_CHANGE_AUTHORITY_POLICY_REF,
    research_lead_transport_contract,
)
from apps.workbench.backend.application.bounded_agent_executor import (
    S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V6_REF,
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF,
    S3ThreeCellBoundedAgentAdmission,
)
from scripts.releases.issue_fin_ia_0_1_s4_t05_research_lead_gap_atom_projection_fresh_exact_admission import (
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


DECISION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_research_lead_gap_atom_"
    "projection_r5_exact_live_execution_and_paired_assessment_"
    "authority_decision_v1_0.json"
)
PROGRAM_BACKLOG = (
    ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
)
DETAILED_BACKLOG = ROOT / (
    "configs/releases/fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
)
NEXT_ACTION = (
    "S4-T05-DELL-RESEARCH-LEAD-GAP-ATOM-DETERMINISTIC-PROJECTION-R5-"
    "EXACT-LIVE-EXECUTION"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_R5_authority_is_exact_once_and_success_conditional() -> None:
    decision = _load(DECISION)
    authority = decision["authority"]
    stop = decision["stop_contract"]
    boundary = decision["decision_boundary"]

    assert decision["status"] == (
        "authorized_R5_exact_once_and_"
        "conditional_read_only_paired_assessment"
    )
    assert authority["R5_admission_exact_once_consumption_authorized"] is True
    assert authority["DELL_R5_exact_live_execution_authorized"] is True
    assert authority[
        "paired_assessment_authorized_only_after_coherent_terminal_success"
    ] is True
    assert authority[
        "automatic_retry_fallback_replay_relaunch_patch_or_rerun_authorized"
    ] is False
    assert authority["Human_review_or_owner_acceptance_authorized"] is False
    assert authority["S4_T06_or_later_authorized"] is False
    assert authority[
        "dependency_conflict_or_all_node_atomization_authorized"
    ] is False
    assert stop["paired_assessment_after_failure_allowed"] is False
    assert stop["automatic_second_execution_allowed"] is False
    assert set(boundary.values()) == {False}


def test_R5_authority_binds_issued_admission_preflights_and_host() -> None:
    decision = _load(DECISION)
    source = decision["source_authority"]
    admission_path = ROOT / source["admission_ref"]
    issuance_path = ROOT / source["issuance_ref"]
    project_preflight_path = ROOT / source["project_os_preflight_ref"]
    runner_preflight_path = ROOT / source["preflight_ref"]
    host_path = ROOT / source["host_capability_receipt_ref"]
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(
        _load(admission_path)
    )
    target = load_execution_target(issuance_path)
    _, host_digest = _validate_host_capability_receipt(host_path)

    assert _sha256(admission_path) == source["admission_file_sha256"]
    assert _sha256(issuance_path) == source["issuance_file_sha256"]
    assert _sha256(project_preflight_path) == (
        source["project_os_preflight_sha256"]
    )
    assert _sha256(runner_preflight_path) == source["preflight_file_sha256"]
    assert _sha256(host_path) == source["host_capability_receipt_sha256"]
    assert host_digest == source["host_capability_receipt_sha256"]
    assert canonical_digest(admission.digest_payload()) == (
        source["admission_digest"]
    )
    assert _load_admission(admission_path, target) == admission
    if R5_FAILURE_RESULT.exists():
        failure = _load(R5_FAILURE_RESULT)
        assert failure["admission"]["consumed"] is True
        assert failure["identity"]["work_unit_id"] == target.work_unit_id
    else:
        issuance_result = verify_issued_admission()
        assert issuance_result["fresh_identity_absent"] is True
        assert issuance_result["provider_calls"] == 0


def test_R5_preflight_and_success_contract_are_closed() -> None:
    decision = _load(DECISION)
    target = decision["exact_execution_target"]
    verification = decision["pre_execution_verification"]
    success = decision["success_contract"]
    project_preflight = _load(
        ROOT / decision["source_authority"]["project_os_preflight_ref"]
    )
    runner_preflight = _load(
        ROOT / decision["source_authority"]["preflight_ref"]
    )

    assert target["task_claim_link_policy_ref"] == (
        S3_TASK_CLAIM_LINK_POLICY_REF
    )
    assert target["what_would_change_authority_policy_ref"] == (
        S3_WHAT_WOULD_CHANGE_AUTHORITY_POLICY_REF
    )
    assert target["research_lead_gap_atom_projection_policy_ref"] == (
        S3_RESEARCH_LEAD_GAP_ATOM_PROJECTION_POLICY.policy_ref
    )
    assert target["research_lead_transport_ref"] == (
        S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V6_REF
    )
    assert research_lead_transport_contract(
        target["research_lead_transport_ref"]
    ).gap_atom_deterministic_projection is True
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
    assert project_preflight["status"] == "pass"
    assert project_preflight["open_full_chain_blockers"] == []
    assert verification["exact_runner_zero_call_preflight"] == (
        "pass_exact_zero_call_execution_preflight"
    )
    assert verification["credential_present"] is True
    assert verification["credential_value_read_output_or_persisted"] is False
    assert verification["provider_health_probe_performed"] is False
    assert verification["transport_retry_environment_zero_during_preflight"]
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
    assert verification["fresh_supervision_root_absent"] is True
    assert verification["target_work_unit_attempt_run_absent"] is True
    assert runner_preflight["execution_state_counts_before"] == (
        runner_preflight["execution_state_counts_after"]
    )
    assert set(runner_preflight["observed_counts"].values()) == {0}
    assert (
        success["logical_node_count"],
        success["semantic_model_call_count"],
        success["artifact_count"],
    ) == (6, 12, 9)
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


def test_project_state_advances_only_to_R5_exact_live_execution() -> None:
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
        _load(R5_FAILURE_RESULT)["next_action"]
        if R5_FAILURE_RESULT.exists()
        else NEXT_ACTION
    )
    assert program["next_action"]["item_id"] == current_next
    assert detailed["current_next_action"] == current_next
    assert program["next_action"][
        "S4_T05_gap_projection_R5_execution_authority_decision_ref"
    ] == DECISION.relative_to(ROOT).as_posix()
    assert program["next_action"][
        "S4_T05_gap_projection_R5_execution_authorized"
    ] is True
    assert program["next_action"][
        "S4_T05_gap_projection_R5_paired_assessment_success_only_authorized"
    ] is True
    assert detailed_t05["gap_projection_R5_execution_authorized"] is True
    assert (
        detailed_t05["gap_projection_execution_started"]
        is R5_FAILURE_RESULT.exists()
    )
    assert detailed_t05["fifth_execution_authorized"] is True
    assert detailed_t05["paired_assessment_performed"] is False
    assert detailed["non_inflation"]["DELL_R2"] is False
