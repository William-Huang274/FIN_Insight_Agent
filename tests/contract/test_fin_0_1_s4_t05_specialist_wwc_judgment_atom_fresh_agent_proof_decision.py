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
    SpecialistWWCJudgmentAtomPolicy,
    research_profile_for_ref,
    specialist_transport_contract,
)
from apps.workbench.backend.application.bounded_agent_executor import (
    S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V6_REF,
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF,
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V8_REF,
    S3ThreeCellBoundedAgentAdmission,
)
from scripts.releases.prepare_fin_ia_0_1_s4_t05_specialist_wwc_judgment_atom_fresh_proof import (
    DECISION,
    IMPLEMENTATION,
    PROSPECTIVE_ADMISSION,
    SOURCE_ADMISSION,
    SOURCE_FAILURE,
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
ISSUANCE = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_s4_t05_specialist_wwc_judgment_atom_deterministic_"
    "assembly_fresh_exact_admission_issuance_v1_0.json"
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
NEXT_ACTION = (
    "S4-T05-DELL-SPECIALIST-WWC-JUDGMENT-ATOM-AND-DETERMINISTIC-"
    "TASK-ASSEMBLY-FRESH-EXACT-ADMISSION-ISSUANCE-DECISION"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_two_independent_disposable_proofs_equal_frozen_decision() -> None:
    decision = _load(DECISION)

    if ISSUANCE.exists():
        issuance = _load(ISSUANCE)
        assert issuance["source_proof_decision_sha256"] == _sha256(DECISION)
    else:
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

    assert identity["work_unit_id"] == (
        "wu_p02_5_4fc6d8f6a641779d1c97861f"
    )
    assert identity["attempt_id"] == (
        "attempt_fin01_f34ce162a7e166702a3f5262"
    )
    assert identity["research_run_id"] == (
        "research_run_fin01_e187ada6b55d471d462e3242"
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
        "research_run_fin01_3ce365aa075bacbc2cc31346",
    }
    assert decision["double_prepare"]["clone_execution_counts_before"] == {
        "canonical_work_units": 5,
        "canonical_attempts": 5,
        "canonical_research_run_versions": 5,
        "canonical_artifact_versions": 0,
    }
    assert (
        decision["double_prepare"]["clone_execution_counts_before"]
        == decision["double_prepare"]["clone_execution_counts_after"]
    )
    assert audit["canonical_database_file_unchanged"] is True
    assert audit["canonical_object_tree_unchanged"] is True
    assert audit["logical_snapshot_unchanged"] is True


def test_current_v8_policy_profile_and_bindings_are_reproved() -> None:
    decision = _load(DECISION)
    implementation = _load(IMPLEMENTATION)
    reaudit = decision["implementation_reaudit"]
    reproof = decision["WWC_judgment_atom_reproof"]
    profile = research_profile_for_ref(
        S4_DELL_THREE_CELL_RESEARCH_PROFILE_V2_REF
    )

    assert reaudit["implementation_contract_sha256"] == _sha256(
        IMPLEMENTATION
    )
    assert reaudit["exact_code_bindings"] == implementation[
        "exact_code_bindings"
    ]
    for relative_path, expected_sha256 in reaudit[
        "exact_code_bindings"
    ].items():
        current_sha256 = _sha256(ROOT / relative_path)
        if current_sha256 != expected_sha256:
            r7_failure = (
                ROOT
                / "configs/releases/fin_ia_0_1_s4_t05_dell_r7_profile_v2_binding_exact_live_execution_failure_result_v1_0.json"
            )
            if r7_failure.exists():
                assert _load(r7_failure)["status"].startswith(
                    "terminal_failed_post_verifier"
                )
            else:
                latest = _load(
                    R7_BINDING_IMPLEMENTATION
                    if R7_BINDING_IMPLEMENTATION.exists()
                    else ROOT_CAUSE_DISPOSITION
                    if ROOT_CAUSE_DISPOSITION.exists()
                    else EXECUTION_FAILURE_RESULT
                    if EXECUTION_FAILURE_RESULT.exists()
                    else EXECUTION_AUTHORITY
                    if EXECUTION_AUTHORITY.exists()
                    else ISSUANCE
                )
                supersession = latest["historical_exact_binding_supersession"]
                assert relative_path in supersession["allowed_changed_paths"]
                assert latest["exact_code_bindings"][
                    relative_path
                ] == current_sha256
    assert reaudit["policy_ref"] == (
        S3_SPECIALIST_WWC_JUDGMENT_ATOM_POLICY_REF
    )
    assert reaudit["specialist_transport_ref"] == (
        S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V8_REF
    )
    assert (
        specialist_transport_contract(
            S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF
        ).what_would_change_judgment_atom_assembly
        is False
    )
    assert (
        specialist_transport_contract(
            S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V8_REF
        ).what_would_change_judgment_atom_assembly
        is True
    )
    assert SpecialistWWCJudgmentAtomPolicy.contract_ref == (
        S3_SPECIALIST_WWC_JUDGMENT_ATOM_POLICY_REF
    )
    assert reproof["provider_atom_cardinality"] == "1..3"
    assert reproof[
        "provider_atom_narrative_maximum_unicode_characters"
    ] == 160
    assert reproof["provider_output_maximum_utf8_bytes"] == 4800
    assert profile.segment_token_budgets[
        "actionable_what_would_change_tasks"
    ] == 1800
    assert profile.stage_token_budgets(expanded_lead=True)[
        "specialist"
    ] == 4600
    assert profile.aggregate_output_tokens(expanded_lead=True) == 18000
    assert reproof["DELL_case_or_provider_special_branch"] is False


def test_prospective_r6_admission_is_valid_fresh_and_unissued() -> None:
    decision = _load(DECISION)
    prospective = decision["prospective_admission"]
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(
        prospective["payload"]
    )

    admission.assert_profile_admissible()
    assert admission.transport_ref == (
        S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V8_REF
    )
    assert admission.research_profile_ref == (
        S4_DELL_THREE_CELL_RESEARCH_PROFILE_V2_REF
    )
    assert admission.wwc_judgment_atom_policy_ref == (
        S3_SPECIALIST_WWC_JUDGMENT_ATOM_POLICY_REF
    )
    assert admission.research_lead_transport_ref == (
        S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V6_REF
    )
    assert admission.specialist_max_output_tokens == 4600
    assert (
        3 * admission.specialist_max_output_tokens
        + admission.lead_max_output_tokens
        + admission.writer_max_output_tokens
        + admission.verifier_max_output_tokens
    ) == 18000
    assert canonical_digest(admission.digest_payload()) == prospective[
        "digest"
    ]
    assert prospective["digest"] == (
        "ac44bff5dda2911465859dc48dfbce44aefaa22533b74321c96fedc816a4b265"
    )
    assert prospective["source_consumed_R5_admission_digest"] == (
        "378731667e55e56740b5fd2fcc81fc152e3b2da91e15230cc7db33a6034ca5db"
    )
    assert PROSPECTIVE_ADMISSION.exists() is ISSUANCE.exists()
    if ISSUANCE.exists():
        issuance = _load(ISSUANCE)
        assert _load(PROSPECTIVE_ADMISSION) == prospective["payload"]
        assert issuance["issued_admission"]["consumed"] is False
        assert issuance["issued_admission"]["execution_started"] is False
    assert (
        prospective["issued"],
        prospective["consumed"],
        prospective["execution_started"],
    ) == (False, False, False)


def test_R5_failure_truth_is_immutable_and_not_reclassified() -> None:
    decision = _load(DECISION)
    source_admission = S3ThreeCellBoundedAgentAdmission.model_validate(
        _load(SOURCE_ADMISSION)
    )
    failure = _load(SOURCE_FAILURE)

    assert failure["admission"]["consumed"] is True
    assert failure["admission"]["admission_digest"] == canonical_digest(
        source_admission.digest_payload()
    )
    assert failure["terminal_result"]["artifact_count"] == 0
    assert failure["first_credible_failure"]["failure_code"] == (
        "s3_bounded_node_output_truncated"
    )
    disposition = decision["root_cause_disposition"]
    assert disposition["historical_R5_terminal_failure_reclassified"] is False
    assert disposition["RC_P36_061_status"] == (
        "R5_consumed_failed_upstream_projection_live_observation_unproven"
    )
    assert disposition["DELL_R2_proven"] is False


def test_future_success_contract_is_product_gate_not_proof_inflation() -> None:
    decision = _load(DECISION)
    success = decision["future_success_contract"]

    assert (
        success["terminal_state"],
        success["logical_nodes"],
        success["provider_calls"],
        success["logical_artifact_families"],
    ) == ("succeeded", 6, 12, 9)
    assert success[
        "all_three_specialist_WWC_segments_consume_v8_atom_policy"
    ] is True
    assert success["research_lead_v6_consumed"] is True
    assert success["gap_projection_live_observed"] is True
    assert success["canonical_atom_or_request_alias_residue"] == 0
    assert success["paired_assessment_only_after_coherent_success"] is True
    assert set(decision["hard_boundaries"].values()) == {0}


def test_decision_advances_only_to_separate_admission_issuance() -> None:
    decision = _load(DECISION)
    program = _load(PROGRAM_BACKLOG)
    detailed = _load(DETAILED_BACKLOG)
    task = next(
        row for row in detailed["tasks"] if row["item_id"] == "S4-T05"
    )

    assert decision["status"] == (
        "pass_zero_call_independent_fresh_proof_contract_frozen_"
        "admission_issuance_pending_separate_authority"
    )
    assert decision["next_action"] == NEXT_ACTION
    current_next = (
        _load(ROOT / "configs/releases/fin_ia_0_1_s4_t05_dell_r7_profile_v2_binding_exact_live_execution_failure_result_v1_0.json")["next_action"]
        if R7_BINDING_IMPLEMENTATION.exists()
        else _load(ROOT_CAUSE_DISPOSITION)["next_action"]
        if ROOT_CAUSE_DISPOSITION.exists()
        else _load(EXECUTION_FAILURE_RESULT)["next_action"]
        if EXECUTION_FAILURE_RESULT.exists()
        else _load(EXECUTION_AUTHORITY)["next_action"]
        if EXECUTION_AUTHORITY.exists()
        else _load(ISSUANCE)["next_action"]
        if ISSUANCE.exists()
        else NEXT_ACTION
    )
    assert program["next_action"]["item_id"] == current_next
    assert detailed["current_next_action"] == current_next
    assert task["WWC_judgment_atom_fresh_agent_proof_completed"] is True
    assert task["WWC_judgment_atom_fresh_agent_proof_ref"] == (
        DECISION.relative_to(ROOT).as_posix()
    )
    assert task["WWC_judgment_atom_fresh_agent_proof_sha256"] == _sha256(
        DECISION
    )
    governance = decision["experiment_governance"]
    assert governance["admission_issuance_authorized"] is False
    assert governance["admission_consumption_authorized"] is False
    assert governance["live_execution_authorized"] is False
    assert governance["S4_T06_or_later_authorized"] is False
