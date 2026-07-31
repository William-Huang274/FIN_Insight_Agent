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
    S3_TASK_CLAIM_LINK_POLICY_REF,
)
from apps.workbench.backend.application.bounded_agent_executor import (
    S3ThreeCellBoundedAgentAdmission,
)
from scripts.releases.prepare_fin_ia_0_1_s4_t05_task_claim_link_policy_fresh_proof import (
    PROSPECTIVE_ADMISSION,
    prepare,
)
from sec_agent.canonical_runtime.models import canonical_digest


DECISION = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_task_claim_link_policy_"
    "fresh_agent_proof_decision_v1_0.json"
)
IMPLEMENTATION = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_task_claim_link_policy_minimum_"
    "zero_call_implementation_v1_0.json"
)
PROOF_SCRIPT = (
    ROOT
    / "scripts/releases/"
    "prepare_fin_ia_0_1_s4_t05_task_claim_link_policy_fresh_proof.py"
)
SOURCE_ADMISSION = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_dell_evidence_role_group_mapping_repair_"
    "fresh_exact_admission_r2.json"
)
PROGRAM_BACKLOG = (
    ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
)
DETAILED_BACKLOG = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
)
ISSUANCE = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_task_claim_link_policy_"
    "fresh_exact_admission_issuance_v1_0.json"
)
AUTHORITY_DECISION = (
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


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_frozen_decision_replays_the_current_zero_call_generator() -> None:
    decision = _load(DECISION)
    if PROSPECTIVE_ADMISSION.exists():
        assert _load(PROSPECTIVE_ADMISSION) == decision[
            "prospective_admission"
        ]["payload"]
        assert _load(ISSUANCE)["source_proof_decision_sha256"] == _sha256(
            DECISION
        )
        return
    generated = prepare()

    assert decision["status"] == (
        "pass_zero_call_independent_fresh_proof_contract_frozen_"
        "admission_issuance_pending_separate_authority"
    )
    assert canonical_digest(generated) == decision["proof_generator"][
        "canonical_output_digest"
    ]
    for key, value in generated.items():
        if key == "source_refs":
            for source_key, source_value in value.items():
                assert decision[key][source_key] == source_value
        else:
            assert decision[key] == value


def test_proof_binds_current_implementation_generator_and_runtime_code() -> None:
    decision = _load(DECISION)
    audit = decision["implementation_reaudit"]
    latest_implementation = _load(R7_BINDING_IMPLEMENTATION)

    assert audit["implementation_contract_sha256"] == _sha256(
        IMPLEMENTATION
    )
    assert decision["proof_generator"]["sha256"] == _sha256(PROOF_SCRIPT)
    assert decision["proof_generator"]["independent_invocations"] == 2
    assert decision["proof_generator"]["independent_outputs_equal"] is True
    for relative_path, expected_sha256 in audit[
        "exact_code_bindings"
    ].items():
        current_sha256 = _sha256(ROOT / relative_path)
        if current_sha256 != expected_sha256:
            assert latest_implementation["exact_code_bindings"][
                relative_path
            ] == current_sha256


def test_fresh_identity_is_nonreused_and_target_remains_read_only() -> None:
    decision = _load(DECISION)
    identity = decision["fresh_identity"]
    freshness = decision["freshness_and_nonreuse"]
    read_only = decision["target_read_only_audit"]

    assert identity["research_run_id"] not in freshness[
        "prior_research_run_ids"
    ]
    assert freshness["prior_research_run_ids"] == [
        "research_run_fin01_2eced17671df87082b95db9a",
        "research_run_fin01_9756044e7d7f23b3ff9fb395",
    ]
    assert freshness["work_unit_absent"] is True
    assert freshness["attempt_absent"] is True
    assert freshness["research_run_absent"] is True
    assert decision["double_prepare"]["clone_execution_counts_before"] == (
        decision["double_prepare"]["clone_execution_counts_after"]
    )
    assert read_only["canonical_database_file_unchanged"] is True
    assert read_only["canonical_object_tree_unchanged"] is True
    assert read_only["logical_snapshot_unchanged"] is True


def test_prospective_admission_explicitly_binds_task_claim_policy_only() -> None:
    decision = _load(DECISION)
    prospective = decision["prospective_admission"]
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(
        prospective["payload"]
    )
    source = S3ThreeCellBoundedAgentAdmission.model_validate(
        _load(SOURCE_ADMISSION)
    )

    admission.assert_profile_admissible()
    assert admission.task_claim_link_policy_ref == (
        S3_TASK_CLAIM_LINK_POLICY_REF
    )
    assert source.task_claim_link_policy_ref is None
    assert prospective["digest"] == canonical_digest(
        admission.digest_payload()
    )
    assert prospective["source_consumed_admission_digest"] == (
        canonical_digest(source.digest_payload())
    )
    assert prospective["digest_advanced_from_source"] is True
    if PROSPECTIVE_ADMISSION.exists():
        issuance = _load(ISSUANCE)
        assert _load(PROSPECTIVE_ADMISSION) == prospective["payload"]
        assert issuance["issued_admission"]["admission_digest"] == (
            prospective["digest"]
        )
        assert issuance["issuance_boundary"]["admission_consumed"] is False
        assert issuance["issuance_boundary"]["execution_started"] is False
    else:
        assert PROSPECTIVE_ADMISSION.exists() is False
    assert prospective["issued"] is False
    assert prospective["consumed"] is False
    assert prospective["execution_started"] is False


def test_success_contract_and_authority_do_not_inflate_DELL_R2() -> None:
    decision = _load(DECISION)
    success = decision["future_success_contract"]
    authority = decision["authority"]
    boundary = decision["hard_boundaries"]

    assert success["terminal_state"] == "succeeded"
    assert [
        success["logical_nodes"],
        success["provider_calls"],
        success["logical_artifact_families"],
    ] == [6, 12, 9]
    assert success["all_three_WWC_segments_consume_task_claim_policy"] is True
    assert success["persisted_request_alias_residue"] == 0
    assert success["unknown_or_cross_Cell_task_claim_link_count"] == 0
    assert set(boundary.values()) == {0}
    assert authority["fresh_exact_admission_issuance_authorized"] is False
    assert authority[
        "admission_consumption_or_live_execution_authorized"
    ] is False
    assert authority[
        "deferred_task_identity_taxonomy_or_cross_stage_redesign_authorized"
    ] is False
    assert decision["root_cause_disposition"]["DELL_R2_proven"] is False


def test_project_state_advances_only_to_separate_admission_issuance() -> None:
    decision = _load(DECISION)
    implementation = _load(IMPLEMENTATION)
    program = _load(PROGRAM_BACKLOG)
    detailed = _load(DETAILED_BACKLOG)
    expected_next = decision["next_action"]

    assert expected_next == (
        "S4-T05-DELL-WWC-TASK-TO-CLAIM-CLOSED-IDENTITY-"
        "FRESH-EXACT-ADMISSION-ISSUANCE-DECISION"
    )
    current_expected_next = (
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
        _load(AUTHORITY_DECISION)["conditional_next_action"][
            "on_authority_decision_complete"
        ]
        if AUTHORITY_DECISION.exists()
        else _load(ISSUANCE)["next_action"]
        if ISSUANCE.exists()
        else expected_next
    )
    assert program["next_action"]["item_id"] == current_expected_next
    assert detailed["current_next_action"] == current_expected_next
    proof_sha256 = _sha256(DECISION)
    assert program["next_action"][
        "S4_T05_task_claim_fresh_proof_sha256"
    ] == proof_sha256
    detailed_t05 = next(
        row for row in detailed["tasks"] if row["item_id"] == "S4-T05"
    )
    assert detailed_t05["task_claim_fresh_proof_sha256"] == proof_sha256
    assert decision["experiment_governance"][
        "deferred_task_identity_or_taxonomy_work_reentered"
    ] is False
    assert implementation["deferred_cross_sequence_items"] == [
        {
            "item": "deterministic_locally_assembled_task_identity",
            "target": "S4-T10-to-S5-carry-forward",
            "blocks_current_T05": False,
        },
        {
            "item": "complete_typed_WWC_failure_taxonomy",
            "target": "S4-T10-to-S5-carry-forward",
            "blocks_current_T05": False,
        },
        {
            "item": "cross_stage_unified_claim_task_identity_redesign",
            "target": "S5-or-later-architecture-sequence",
            "blocks_current_T05": False,
        },
    ]
