from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_contract_policies import (
    S3_CLAIM_FACT_LINK_POLICY_REF,
    S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V4_REF,
)
from apps.workbench.backend.application.bounded_agent_executor import (
    S3_OWNER_GRADE_VERIFIER_STATE_MACHINE_REF,
    S3ThreeCellBoundedAgentAdmission,
)
from scripts.releases.prepare_fin_ia_0_1_s3_t09_layered_verifier_typed_ref_and_finding_disposition_fresh_agent_proof_decision import (
    DECISION_STATUS,
    NEXT_ACTION,
)
from scripts.releases.supervise_fin_ia_0_1_s3_t09_exact_live_execution import (
    SUPERVISION_CONTRACT_REF,
)
from sec_agent.canonical_runtime.models import canonical_digest


PROOF = ROOT / (
    "configs/releases/fin_ia_0_1_s3_t09_layered_verifier_typed_ref_and_"
    "finding_disposition_fresh_agent_proof_decision_v1_0.json"
)
PROSPECTIVE_ADMISSION = ROOT / (
    "configs/releases/fin_ia_0_1_s3_t09_three_cell_deepseek_layered_"
    "verifier_typed_ref_finding_disposition_exact_admission_r1.json"
)
S4_T03_DECISION = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_s4_t03_case_runtime_injection_and_leakage_preflight_v1_0.json"
)


def _load() -> dict:
    return json.loads(PROOF.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_fresh_proof_freezes_new_identity_and_zero_call_boundary() -> None:
    proof = _load()
    identity = proof["identity"]

    assert proof["status"] == DECISION_STATUS
    assert proof["double_prepare"]["equal"] is True
    assert proof["target_read_only_audit"][
        "expected_prior_research_run_count"
    ] == 23
    assert proof["freshness_and_nonreuse"]["work_unit_absent"] is True
    assert proof["freshness_and_nonreuse"]["attempt_absent"] is True
    assert proof["freshness_and_nonreuse"]["research_run_absent"] is True
    assert identity["research_run_id"] not in proof["freshness_and_nonreuse"][
        "prior_research_run_ids"
    ]
    assert set(proof["observed_counts"].values()) == {0}


def test_prospective_admission_is_valid_frozen_absent_and_unconsumed() -> None:
    prospective = _load()["prospective_admission"]
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(
        prospective["payload"]
    )

    admission.assert_profile_admissible()
    assert canonical_digest(admission.digest_payload()) == prospective["digest"]
    assert admission.research_profile_ref == (
        S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V4_REF
    )
    assert admission.claim_fact_link_policy_ref == S3_CLAIM_FACT_LINK_POLICY_REF
    assert prospective["admission_issued"] is False
    assert prospective["admission_consumed"] is False
    assert prospective["execution_started"] is False
    assert prospective["prospective_admission_file_absent"] is True
    assert PROSPECTIVE_ADMISSION.exists() is True


def test_exact_code_bindings_preserve_archived_S3_proof_and_bound_S4_extensions() -> None:
    bindings = _load()["exact_code_bindings"]
    s4_t03 = json.loads(S4_T03_DECISION.read_text(encoding="utf-8"))

    assert set(bindings) == {
        "apps/workbench/backend/application/bounded_agent_contract_policies.py",
        "apps/workbench/backend/application/bounded_agent_identity_policies.py",
        "apps/workbench/backend/application/bounded_agent_executor.py",
        "apps/workbench/backend/application/research_runtime.py",
        "src/sec_agent/canonical_runtime/facade.py",
        "scripts/releases/run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution.py",
        "scripts/releases/supervise_fin_ia_0_1_s3_t09_exact_live_execution.py",
    }
    later_extended = {
        "apps/workbench/backend/application/bounded_agent_contract_policies.py",
        "apps/workbench/backend/application/bounded_agent_executor.py",
        "apps/workbench/backend/application/research_runtime.py",
        "scripts/releases/run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution.py",
    }
    for relative, digest in bindings.items():
        if relative in later_extended:
            assert _sha256(ROOT / relative) != digest
        else:
            assert _sha256(ROOT / relative) == digest
    assert s4_t03["runtime_contract"]["same_existing_executor"].endswith(
        "S3ThreeCellBoundedAgentExecutor"
    )
    assert s4_t03["runtime_contract"][
        "parallel_case_specific_runtime_added"
    ] is False


def test_verifier_typed_ref_contract_is_exact_and_fail_closed() -> None:
    contract = _load()["verifier_typed_scoped_ref_acceptance_contract"]

    assert contract["provider_request_representation"] == (
        "CellScopedResearchIdentityPolicy.wire_schema(claim)"
    )
    assert contract["local_validator_uses_same_scoped_identity_surface"] is True
    assert contract["current_supported_ref_kind"] == "Claim"
    assert contract["exact_membership_required"] is True
    assert contract["raw_unknown_wrong_kind_wrong_cell_or_duplicate_ref"] == (
        "typed_fail_closed"
    )
    assert contract[
        "identity_guessing_normalization_or_silent_rewrite_allowed"
    ] is False


def test_layered_finding_disposition_preserves_hard_integrity_boundary() -> None:
    proof = _load()
    contract = proof["finding_disposition_acceptance_contract"]
    layered = proof["layered_runtime_acceptance_contract"]

    assert contract["scope_digest_mismatch_without_local_contradiction_is_L1"] is False
    assert contract["disclosed_unresolved_conflict_is_L1"] is False
    assert contract[
        "explicit_company_total_metric_without_segment_attribution_is_L1"
    ] is False
    assert contract["hard_integrity_requires_canonical_evidence"] is True
    assert contract["L3_findings_must_be_persisted"] == [
        "unresolved_cross_cell_conflict",
        "unattributed_company_total_margins",
    ]
    assert layered[
        "L1_truth_provenance_numeric_scope_identity_permission_and_lineage"
    ] == "hard"
    assert layered["historical_terminal_truth_rewrite_allowed"] is False
    assert layered["captured_output_promotion_or_synthesis_allowed"] is False


def test_product_target_and_supervision_v2_remain_complete() -> None:
    proof = _load()
    artifact = proof["artifact_acceptance_contract"]
    claim_fact = proof["claim_fact_link_live_acceptance_contract"]
    supervision = proof["supervision_v2_acceptance_contract"]

    assert artifact["success_requires_terminal_states"] == [
        "succeeded",
        "succeeded",
        "succeeded",
    ]
    assert artifact["success_requires_logical_nodes"] == 6
    assert artifact["success_requires_provider_calls"] == 12
    assert artifact["success_requires_artifact_families"] == 9
    assert artifact["same_coherent_run_required"] is True
    assert artifact["L1_hard_integrity_pass_required"] is True
    assert artifact["L3_or_L4_quality_findings_may_coexist_with_success"] is True
    assert claim_fact[
        "expanded_support_must_resolve_to_validated_same_Cell_Facts"
    ] is True
    assert claim_fact["persisted_alias_residue_required"] == 0
    assert claim_fact["persisted_source_ref_as_claim_support_required"] == 0
    assert supervision["contract_ref"] == SUPERVISION_CONTRACT_REF
    assert supervision["actual_runner_self_finalized_exit_receipt_required"] is True
    assert supervision["process_identity_requires_pid_and_creation_time"] is True
    assert supervision["monitoring_is_read_only"] is True


def test_governance_stops_at_separate_admission_issuance_gate() -> None:
    proof = _load()
    governance = proof["experiment_governance"]

    assert governance["decision_label"] == (
        "proceed_to_separate_exact_admission_issuance_gate"
    )
    assert governance["admission_issuance_authorized"] is False
    assert governance["admission_consumption_authorized"] is False
    assert governance["live_execution_authorized"] is False
    assert governance[
        "automatic_retry_fallback_patch_replay_relaunch_or_rerun_authorized"
    ] is False
    assert governance["paired_comparison_or_owner_acceptance_authorized"] is False
    assert governance["T10_S4_release_or_production_authorized"] is False
    assert proof["next_action"] == NEXT_ACTION


def test_program_backlog_preserves_proof_after_exact_live_completion() -> None:
    proof = _load()
    backlog = json.loads(
        (
            ROOT
            / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
        ).read_text(encoding="utf-8")
    )
    current = backlog["next_action"]

    assert current[
        "layered_verifier_typed_ref_finding_disposition_fresh_proof_ref"
    ] == (
        "configs/releases/fin_ia_0_1_s3_t09_layered_verifier_typed_ref_and_"
        "finding_disposition_fresh_agent_proof_decision_v1_0.json"
    )
    assert current["current_fresh_agent_proof_decision_authorized"] is True
    assert current["current_fresh_agent_proof_decision_complete"] is True
    assert current["current_fresh_exact_admission_issuance_authorized"] is True
    assert current["current_fresh_exact_admission_issued"] is True
    assert current["current_fresh_exact_admission_consumed"] is True
    assert current["current_fresh_exact_execution_authorized"] is False
    assert current["current_agent_execution_authorized"] is False
    assert current["current_T09_final_assessment_completed"] is True
    assert current["current_T09_decision"] == (
        "pass_owner_accepted_with_L4_quality_debt"
    )
    assert current["current_owner_acceptance_write_completed"] is True
    assert current["current_S3_T10_closeout_completed"] is True
    assert current["current_S4_T01_completed"] is True
    assert current["current_S4_T02_completed"] is True
    assert current["current_S4_T03_authorized"] is True
    assert current["current_S4_T03_completed"] is True
    assert current["current_S4_T04_authorized"] is True
    assert current["current_S4_T04_decision_completed"] is True
    assert current["current_S4_T04_completed"] is True
    assert current["current_S4_case_execution_started"] is True
    assert current["item_id"] == (
        "S4-T05-DELL-EVIDENCE-ROLE-GROUP-MAPPING-AND-ACTUAL-DISPATCH-"
        "PREFLIGHT-ZERO-CALL-IMPLEMENTATION"
    )
    assert current["current_prospective_admission_digest"] == proof[
        "prospective_admission"
    ]["digest"]
