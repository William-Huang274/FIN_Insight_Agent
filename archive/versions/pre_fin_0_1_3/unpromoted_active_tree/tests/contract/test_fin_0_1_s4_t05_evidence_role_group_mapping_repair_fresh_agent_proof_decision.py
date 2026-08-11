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

DECISION = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_evidence_role_group_mapping_repair_"
    "fresh_agent_proof_decision_v1_0.json"
)
IMPLEMENTATION = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_evidence_role_group_mapping_actual_dispatch_"
    "preflight_zero_call_implementation_v1_0.json"
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
PROOF_SCRIPT = (
    ROOT
    / "scripts/releases/"
    "prepare_fin_ia_0_1_s4_t05_evidence_role_group_mapping_"
    "repair_fresh_proof.py"
)
BACKLOG = (
    ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
)
DETAILED_BACKLOG = (
    ROOT / "configs/releases/fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
)
ISSUANCE = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_evidence_role_group_mapping_repair_"
    "fresh_exact_admission_issuance_v1_0.json"
)
FAILURE_RESULT = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_dell_replacement_exact_r2_"
    "execution_failure_result_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_fresh_proof_binds_fixture_proven_implementation_and_current_code() -> None:
    decision = _load(DECISION)
    implementation = _load(IMPLEMENTATION)
    task_claim_implementation = _load(TASK_CLAIM_IMPLEMENTATION)
    latest_implementation = _load(R7_BINDING_IMPLEMENTATION)

    assert implementation["status"] == (
        "pass_zero_call_implementation_fixture_proven_"
        "fresh_agent_proof_pending"
    )
    assert decision["source_refs"]["implementation"] == (
        IMPLEMENTATION.relative_to(ROOT).as_posix()
    )
    audit = decision["implementation_reaudit"]
    assert audit["implementation_contract_sha256"] == _sha256(IMPLEMENTATION)
    assert audit["exact_code_bindings"] == implementation[
        "exact_code_bindings"
    ]
    allowed_changed_paths = set(
        latest_implementation["historical_exact_binding_supersession"][
            "allowed_changed_paths"
        ]
    ) | set(
        task_claim_implementation["historical_exact_binding_supersession"][
            "allowed_changed_paths"
        ]
    )
    for relative_path, expected_sha256 in audit[
        "exact_code_bindings"
    ].items():
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
    assert decision["proof_generator"]["sha256"] == _sha256(PROOF_SCRIPT)


def test_fresh_proof_freezes_exact_role_alignment_and_shared_dispatch() -> None:
    decision = _load(DECISION)
    audit = decision["implementation_reaudit"]
    identity = decision["fresh_identity"]

    assert audit["program_cell_axis"] == "program_cell_id"
    assert audit["role_group_counts"] == [4, 5, 5]
    assert audit["exact_role_count"] == 14
    assert audit["shared_dispatcher"] == "compile_profile_evidence_dispatch"
    assert audit["dispatcher_definition_and_call_site_count"] >= 3
    assert audit["S4_fixture_candidate_fallback_absent"] is True
    assert audit["S4_ticker_specific_mapping_branch_absent"] is True
    assert identity["role_group_mapping_digest"] == (
        audit["role_group_mapping_digest"]
    )
    assert identity["evidence_alignment_digest"]
    assert identity["evidence_dispatch_digest"]


def test_fresh_proof_is_deterministic_nonreused_and_target_read_only() -> None:
    decision = _load(DECISION)

    assert decision["proof_generator"]["independent_invocations"] == 2
    assert decision["proof_generator"]["independent_outputs_equal"] is True
    assert decision["double_prepare"]["equal"] is True
    assert decision["double_prepare"]["clone_execution_counts_before"] == (
        decision["double_prepare"]["clone_execution_counts_after"]
    )
    assert decision["freshness_and_nonreuse"]["work_unit_absent"] is True
    assert decision["freshness_and_nonreuse"]["attempt_absent"] is True
    assert decision["freshness_and_nonreuse"]["research_run_absent"] is True
    assert decision["freshness_and_nonreuse"]["failed_run_reused"] is False
    assert decision["target_read_only_audit"][
        "canonical_database_file_unchanged"
    ]
    assert decision["target_read_only_audit"][
        "canonical_object_tree_unchanged"
    ]
    assert decision["target_read_only_audit"]["logical_snapshot_unchanged"]
    assert set(decision["hard_boundaries"].values()) == {0}


def test_prospective_replacement_admission_is_valid_but_not_issued() -> None:
    from apps.workbench.backend.application.bounded_agent_executor import (
        S3ThreeCellBoundedAgentAdmission,
        build_s3_three_cell_bounded_agent_executor_for_admission,
    )
    from sec_agent.canonical_runtime.models import canonical_digest

    prospective = _load(DECISION)["prospective_admission"]
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(
        prospective["payload"]
    )
    admission.assert_profile_admissible()
    assert canonical_digest(admission.digest_payload()) == prospective["digest"]
    assert prospective["prospective_admission_file_absent"] is True
    prospective_path = ROOT / prospective["prospective_admission_file"]
    if ISSUANCE.exists():
        issuance = _load(ISSUANCE)
        assert prospective_path.exists()
        assert issuance["issued_admission"]["admission_digest"] == (
            prospective["digest"]
        )
        assert issuance["issued_admission"]["admission_ref"] == (
            prospective["prospective_admission_file"]
        )
        assert issuance["issued_admission"]["consumed"] is False
    else:
        assert not prospective_path.exists()
    assert prospective["issued"] is False
    assert prospective["consumed"] is False
    assert prospective["execution_started"] is False

    callback_calls = 0

    def _must_not_call_provider(**_: object) -> dict:
        nonlocal callback_calls
        callback_calls += 1
        raise AssertionError("provider_callback_forbidden")

    build_s3_three_cell_bounded_agent_executor_for_admission(
        admission,
        chat_completion_fn=_must_not_call_provider,
    )
    assert callback_calls == 0


def test_fresh_proof_closes_engineering_blocker_without_inflating_dell_r2() -> None:
    decision = _load(DECISION)
    disposition = decision["root_cause_disposition"]
    governance = decision["experiment_governance"]

    assert decision["status"] == (
        "pass_zero_call_independent_fresh_proof_contract_frozen_"
        "replacement_admission_issuance_pending_separate_authority"
    )
    assert disposition["full_chain_engineering_blocker_closed"] is True
    assert disposition["model_or_provider_issue"] is False
    assert disposition["DELL_R2_proven"] is False
    assert governance["admission_issuance_authorized"] is False
    assert governance["admission_consumption_authorized"] is False
    assert governance["live_execution_authorized"] is False
    assert governance["paired_assessment_authorized"] is False


def test_project_backlogs_trace_proof_through_later_issuance_gate() -> None:
    decision = _load(DECISION)
    backlog = _load(BACKLOG)
    detailed = _load(DETAILED_BACKLOG)
    expected = (
        "S4-T05-DELL-EVIDENCE-ROLE-GROUP-MAPPING-REPAIR-"
        "FRESH-EXACT-ADMISSION-ISSUANCE-DECISION"
    )

    assert decision["next_action"] == expected
    if R7_BINDING_IMPLEMENTATION.exists():
        current_expected = _load(
            ROOT / "configs/releases/fin_ia_0_1_s4_t05_dell_r7_profile_v2_binding_exact_live_execution_failure_result_v1_0.json"
        )["next_action"]
    elif WWC_ATOM_ISSUANCE.exists():
        current_expected = _load(WWC_ATOM_ISSUANCE)["next_action"]
    elif WWC_TRUNCATION_DISPOSITION.exists():
        current_expected = _load(WWC_TRUNCATION_DISPOSITION)["next_action"]
    elif GAP_PROJECTION_R5_FAILURE_RESULT.exists():
        current_expected = _load(GAP_PROJECTION_R5_FAILURE_RESULT)["next_action"]
    elif GAP_PROJECTION_AUTHORITY.exists():
        current_expected = _load(GAP_PROJECTION_AUTHORITY)[
            "conditional_next_action"
        ]["on_authority_decision_complete"]
    elif GAP_PROJECTION_ISSUANCE.exists():
        current_expected = _load(GAP_PROJECTION_ISSUANCE)["next_action"]
    elif GAP_PROJECTION_FRESH_PROOF.exists():
        current_expected = _load(GAP_PROJECTION_FRESH_PROOF)["next_action"]
    elif NUMERIC_AUTHORITY_IMPLEMENTATION.exists():
        current_expected = _load(NUMERIC_AUTHORITY_IMPLEMENTATION)[
            "next_action"
        ]
    elif GAP_PROJECTION_DISPOSITION.exists():
        current_expected = _load(GAP_PROJECTION_DISPOSITION)["next_action"]
    elif R4_FAILURE_RESULT.exists():
        current_expected = _load(R4_FAILURE_RESULT)["next_action"]
    elif NUMERIC_AUTHORITY_DECISION.exists():
        current_expected = _load(NUMERIC_AUTHORITY_DECISION)[
            "conditional_next_action"
        ]["on_authority_decision_complete"]
    elif NUMERIC_AUTHORITY_ISSUANCE.exists():
        current_expected = _load(NUMERIC_AUTHORITY_ISSUANCE)["next_action"]
    elif NUMERIC_AUTHORITY_PROOF.exists():
        current_expected = _load(NUMERIC_AUTHORITY_PROOF)["next_action"]
    elif NUMERIC_AUTHORITY_IMPLEMENTATION.exists():
        current_expected = _load(NUMERIC_AUTHORITY_IMPLEMENTATION)[
            "next_action"
        ]
    elif NUMERIC_AUTHORITY_DISPOSITION.exists():
        current_expected = _load(NUMERIC_AUTHORITY_DISPOSITION)[
            "next_action"
        ]
    elif R3_FAILURE_RESULT.exists():
        current_expected = _load(R3_FAILURE_RESULT)["next_action"]
    elif TASK_CLAIM_AUTHORITY.exists():
        current_expected = _load(TASK_CLAIM_AUTHORITY)[
            "conditional_next_action"
        ]["on_authority_decision_complete"]
    elif TASK_CLAIM_ISSUANCE.exists():
        current_expected = _load(TASK_CLAIM_ISSUANCE)["next_action"]
    elif TASK_CLAIM_PROOF.exists():
        current_expected = (
            "S4-T05-DELL-WWC-TASK-TO-CLAIM-CLOSED-IDENTITY-"
            "FRESH-EXACT-ADMISSION-ISSUANCE-DECISION"
        )
    elif TASK_CLAIM_IMPLEMENTATION.exists():
        current_expected = (
            "S4-T05-DELL-WWC-TASK-TO-CLAIM-CLOSED-IDENTITY-"
            "FRESH-AGENT-PROOF-DECISION"
        )
    elif FAILURE_RESULT.exists():
        current_expected = (
            "S4-T05-DELL-WWC-TASK-TO-CLAIM-CLOSED-IDENTITY-"
            "ZERO-CALL-ROOT-CAUSE-DISPOSITION-DECISION"
        )
    elif ISSUANCE.exists():
        current_expected = (
            "S4-T05-DELL-REPLACEMENT-EXACT-R2-EXECUTION-AND-"
            "PAIRED-ASSESSMENT-AUTHORITY-DECISION"
        )
    else:
        current_expected = expected
    assert backlog["next_action"]["item_id"] == current_expected
    assert detailed["current_next_action"] == current_expected
    assert backlog["next_action"][
        "S4_T05_role_mapping_fresh_proof_ref"
    ] == DECISION.relative_to(ROOT).as_posix()
    assert backlog["next_action"][
        "S4_T05_role_mapping_fresh_proof_sha256"
    ] == _sha256(DECISION)
    assert backlog["next_action"][
        "current_S4_T05_fresh_agent_proof_authorized"
    ] is True
    assert backlog["next_action"][
        "current_S4_T05_fresh_agent_proof_completed"
    ] is True
    assert backlog["next_action"][
        "current_S4_T05_replacement_admission_issued"
    ] is ISSUANCE.exists()
    assert backlog["next_action"][
        "current_S4_T05_second_execution_authorized"
    ] is FAILURE_RESULT.exists()
