from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_contract_policies import (
    S3_RESEARCH_LEAD_CONFLICT_FACT_PRESENCE_LOCAL_MATERIALIZATION_POLICY,
)
from apps.workbench.backend.application.bounded_agent_executor import (
    S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V7_REF,
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF,
    S3ThreeCellBoundedAgentAdmission,
)
from scripts.releases.prepare_fin_ia_0_1_s4_t06_mu_research_lead_fact_presence_local_materialization_fresh_proof import (
    DECISION,
    IMPLEMENTATION,
    PROSPECTIVE_ADMISSION,
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
NEXT_ACTION = (
    "S4-T06-MU-RESEARCH-LEAD-CONFLICT-FACT-PRESENCE-LOCAL-"
    "MATERIALIZATION-FRESH-EXACT-ADMISSION-ISSUANCE-DECISION"
)
ISSUANCE = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t06_mu_research_lead_fact_presence_local_"
    "materialization_fresh_exact_admission_issuance_v1_0.json"
)
AUTHORITY = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_research_lead_fact_presence_"
    "local_materialization_r2_exact_live_execution_and_success_only_"
    "paired_assessment_authority_decision_v1_0.json"
)
CURRENT_RUNTIME_IMPLEMENTATION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_runtime_audit_evidence_v2_"
    "and_material_numeric_classifier_minimum_zero_call_"
    "implementation_v1_0.json"
)
CURRENT_IDENTITY_BOUNDARY_IMPLEMENTATION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_current_case_aware_"
    "delivery_identity_boundary_scope_replacement_minimum_zero_call_"
    "implementation_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _assert_historical_or_current(
    relative_path: str,
    historical_sha256: str,
) -> None:
    observed = _sha256(ROOT / relative_path)
    if observed == historical_sha256:
        return
    identity_boundary = _load(
        CURRENT_IDENTITY_BOUNDARY_IMPLEMENTATION
    )
    if (
        identity_boundary["exact_code_bindings"].get(relative_path)
        == observed
    ):
        return
    current = _load(CURRENT_RUNTIME_IMPLEMENTATION)
    current_digest = current["exact_code_bindings"].get(relative_path)
    if current_digest is not None:
        assert current_digest == observed
        return
    assert relative_path in current[
        "historical_exact_binding_supersession"
    ]["allowed_changed_paths"]


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


def test_fresh_r2_identity_is_nonreused_and_target_is_read_only() -> None:
    decision = _load(DECISION)
    identity = decision["fresh_identity"]
    freshness = decision["freshness_and_nonreuse"]
    audit = decision["target_read_only_audit"]

    assert identity["work_unit_id"] == (
        "wu_p02_5_43322e55457b647277d2297a"
    )
    assert identity["attempt_id"] == (
        "attempt_fin01_217f2f2aaaa051080a540f2a"
    )
    assert identity["research_run_id"] == (
        "research_run_fin01_1920b03b8205e9861dfb5676"
    )
    assert (
        freshness["work_unit_absent"],
        freshness["attempt_absent"],
        freshness["research_run_absent"],
        freshness["consumed_failed_R1_preserved"],
        freshness["consumed_failed_R1_reused"],
    ) == (True, True, True, True, False)
    assert audit["canonical_database_file_unchanged"] is True
    assert audit["canonical_object_tree_unchanged"] is True
    assert audit["logical_snapshot_unchanged"] is True


def test_v7_policy_and_implementation_bindings_are_reproved() -> None:
    decision = _load(DECISION)
    implementation = _load(IMPLEMENTATION)
    audit = decision["implementation_reaudit"]
    reproof = decision["materialization_policy_reproof"]
    policy = (
        S3_RESEARCH_LEAD_CONFLICT_FACT_PRESENCE_LOCAL_MATERIALIZATION_POLICY
    )

    assert audit["implementation_contract_sha256"] == _sha256(
        IMPLEMENTATION
    )
    assert audit["exact_code_bindings"] == implementation[
        "exact_code_bindings"
    ]
    for relative_path, expected_digest in audit[
        "exact_code_bindings"
    ].items():
        _assert_historical_or_current(
            relative_path, expected_digest
        )
    assert audit["research_lead_transport_ref"] == (
        S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V7_REF
    )
    assert reproof["policy_ref"] == policy.policy_ref
    assert reproof["truth_table"] == dict(policy.truth_table)
    assert reproof["provider_emits_fact_presence_summary"] is False
    assert reproof["canonical_output_requires_fact_presence_summary"] is True
    assert reproof["lead_v6_gap_atom_projection_inherited"] is False
    assert reproof["MU_case_or_provider_special_branch"] is False


def test_prospective_r2_admission_is_valid_fresh_and_unissued() -> None:
    decision = _load(DECISION)
    prospective = decision["prospective_admission"]
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(
        prospective["payload"]
    )

    admission.assert_profile_admissible()
    assert admission.company == "MU"
    assert admission.research_lead_transport_ref == (
        S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V7_REF
    )
    assert admission.transport_ref == (
        S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF
    )
    assert canonical_digest(admission.digest_payload()) == prospective[
        "digest"
    ]
    assert prospective["digest"] == (
        "55fb08cac25b3a03109b13ae645d858b90b2074873f5355e6ed47ac93c6cd65c"
    )
    assert prospective["prospective_admission_file_absent"] is True
    if PROSPECTIVE_ADMISSION.exists():
        assert _load(PROSPECTIVE_ADMISSION) == prospective["payload"]
    else:
        assert PROSPECTIVE_ADMISSION.exists() is False
    assert (
        prospective["issued"],
        prospective["consumed"],
        prospective["execution_started"],
    ) == (False, False, False)
    assert set(decision["hard_boundaries"].values()) == {0}


def test_R1_failure_is_immutable_and_future_success_gate_is_complete() -> None:
    decision = _load(DECISION)
    source_failure = _load(SOURCE_FAILURE)
    success = decision["future_success_contract"]

    assert source_failure["canonical_terminal_truth"]["research_run_state"] == (
        "failed"
    )
    assert source_failure["canonical_terminal_truth"]["artifact_count"] == 0
    assert decision["root_cause_disposition"][
        "historical_R1_terminal_failure_reclassified"
    ] is False
    assert (
        success["terminal_state"],
        success["logical_nodes"],
        success["provider_calls"],
        success["provider_output_captures"],
        success["logical_artifact_families"],
    ) == ("succeeded", 6, 12, 12, 9)
    assert success["research_lead_v7_consumed"] is True
    assert success["provider_wire_omits_fact_presence_summary"] is True
    assert success["canonical_conflict_summary_locally_materialized"] is True
    assert success["paired_assessment_only_after_coherent_success"] is True


def test_decision_advances_only_to_separate_admission_issuance() -> None:
    decision = _load(DECISION)
    program = _load(PROGRAM_BACKLOG)
    detailed = _load(DETAILED_BACKLOG)
    current_next = program["next_action"]["item_id"]

    assert decision["status"] == (
        "pass_zero_call_independent_fresh_proof_contract_frozen_"
        "admission_issuance_pending_separate_authority"
    )
    assert decision["next_action"] == NEXT_ACTION
    assert detailed["current_next_action"] == current_next
    assert decision["experiment_governance"][
        "admission_issuance_authorized"
    ] is False
    assert decision["experiment_governance"][
        "live_execution_authorized"
    ] is False
    assert decision["root_cause_disposition"]["MU_R2_proven"] is False
