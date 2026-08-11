from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_executor import (
    S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V2_REF,
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V5_REF,
    S3ThreeCellBoundedAgentAdmission,
    build_s3_three_cell_bounded_agent_executor_for_admission,
)
from sec_agent.canonical_runtime.models import canonical_digest


RELEASES = ROOT / "configs" / "releases"
DECISION = RELEASES / (
    "fin_ia_0_1_s3_t09_owner_grade_v3_research_lead_v2_"
    "fresh_agent_proof_decision_v1_0.json"
)
BACKLOG = RELEASES / "fin_ia_0_1_program_release_backlog_v2_0.json"
ADMISSION = RELEASES / (
    "fin_ia_0_1_s3_t09_three_cell_deepseek_owner_grade_v3_"
    "specialist_v5_research_lead_v2_exact_admission_v1_0.json"
)
DUMMY_PROSPECTIVE_ADMISSION = (
    "configs/releases/fin_ia_0_1_s3_t09_research_lead_v2_"
    "decision_replay_DO_NOT_CREATE.json"
)


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_decision_freezes_fresh_identity_without_issuance_or_execution() -> None:
    decision = _load(DECISION)
    assert decision["status"] == (
        "pass_fresh_specialist_v5_research_lead_v2_exact_proof_contract_"
        "decided_admission_issuance_pending_separate_authority"
    )
    assert decision["authority"]["fresh_agent_proof_decision_authorized"] is True
    assert decision["authority"]["exact_admission_issuance_authorized"] is False
    assert (
        decision["authority"]["admission_consumption_or_live_execution_authorized"]
        is False
    )
    assert decision["fresh_identity"]["work_unit_id"] == (
        "wu_p02_5_43be21c85a5aa7f48103fba2"
    )
    assert decision["fresh_identity"]["attempt_id"] == (
        "attempt_fin01_7a048403efd7098be7e552a0"
    )
    assert decision["fresh_identity"]["research_run_id"] == (
        "research_run_fin01_641650afe6bb1062f9ae135e"
    )
    assert decision["fresh_identity"]["input_digest"] == (
        "86ad143c69b3ef146e64048fcf981e33e751f1fa41a9190b91449b511da1b232"
    )
    assert set(decision["observed_counts"].values()) == {0}


def test_double_prepare_and_target_read_only_audit_were_reproducible() -> None:
    decision = _load(DECISION)
    verification = decision["preflight_verification"]
    assert verification["disposable_clone_double_prepare_equal"] is True
    assert verification["clone_execution_counts_before_and_after"] == [9, 9, 9, 13]
    assert verification["logical_snapshot_unchanged"] is True
    assert verification["canonical_database_file_unchanged"] is True
    assert verification["canonical_object_tree_unchanged"] is True
    assert verification["canonical_database_sha256"] == (
        "87bbb325aeede067a823c02ad1d5ab46b56580ca279f077a6bdb698a6f498215"
    )
    assert verification["canonical_object_tree_sha256"] == (
        "e49c2a7ff76a048dc75f0f5ddfd3d8df74e70cea754d36b154399874859cabdd"
    )


def test_prospective_admission_binds_v5_lead_v2_and_exact_budgets() -> None:
    decision = _load(DECISION)
    prospective = decision["prospective_admission"]
    assert prospective["payload"] == _load(ADMISSION)
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(
        prospective["payload"]
    )
    admission.assert_profile_admissible()
    assert admission.transport_ref == (
        S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V5_REF
    )
    assert admission.research_lead_transport_ref == (
        S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V2_REF
    )
    assert admission.lead_max_output_tokens == 1800
    assert (
        3 * admission.specialist_max_output_tokens
        + admission.lead_max_output_tokens
        + admission.writer_max_output_tokens
        + admission.verifier_max_output_tokens
        == 16800
    )
    assert canonical_digest(admission.digest_payload()) == prospective[
        "admission_digest"
    ]
    callback_calls = 0

    def _must_not_call_provider(**_: object) -> dict[str, object]:
        nonlocal callback_calls
        callback_calls += 1
        raise AssertionError("provider_callback_forbidden")

    build_s3_three_cell_bounded_agent_executor_for_admission(
        admission, chat_completion_fn=_must_not_call_provider
    )
    assert callback_calls == 0
    assert not (ROOT / DUMMY_PROSPECTIVE_ADMISSION).exists()


def test_budget_nonreuse_stop_and_product_target_are_closed() -> None:
    decision = _load(DECISION)
    assert decision["freshness_and_nonreuse"]["prior_research_run_count"] == 9
    assert decision["freshness_and_nonreuse"][
        "distinct_from_all_prior_agent_and_baseline_runs"
    ] is True
    assert decision["freshness_and_nonreuse"][
        "prior_admission_payload_or_digest_reusable"
    ] is False
    assert decision["freshness_and_nonreuse"][
        "baseline_output_body_exposed_to_agent"
    ] is False
    budget = decision["budget_and_stop_contract"]
    assert [
        budget["semantic_model_calls"],
        budget["provider_calls"],
        budget["network_calls"],
    ] == [12, 12, 12]
    assert budget["aggregate_max_output_tokens"] == 16800
    assert budget["max_total_cost_usd"] == 0.1
    assert budget["retry_budget"] == 0
    assert budget["automatic_repair_fallback_or_rerun"] is False
    assert decision["product_proof_target"]["required_logical_node_count"] == 6
    assert decision["product_proof_target"]["required_artifact_family_count"] == 9


def test_project_os_preserves_decision_and_advances_to_separate_execution_authority() -> None:
    decision = _load(DECISION)
    backlog = _load(BACKLOG)
    assert decision["next_action"] == (
        "S3-T09-OWNER-GRADE-V3-RESEARCH-LEAD-V2-FRESH-EXACT-"
        "ADMISSION-ISSUANCE"
    )
    assert backlog["next_action"]["item_id"] == (
        "S3-T09-OWNER-GRADE-V3-RESEARCH-LEAD-V3-CONFLICT-LOCAL-"
        "DIRECT-SUPPORT-ZERO-CALL-IMPLEMENTATION"
    )
    assert backlog["next_action"][
        "research_lead_v2_fresh_agent_proof_decision_authorized"
    ] is True
    assert backlog["next_action"][
        "research_lead_v2_fresh_exact_admission_issuance_authorized"
    ] is True
    assert backlog["next_action"][
        "research_lead_v2_fresh_exact_admission_issued"
    ] is True
    assert backlog["next_action"][
        "research_lead_v2_fresh_exact_admission_consumed"
    ] is True
    assert backlog["next_action"][
        "research_lead_v2_conflict_fact_presence_scope_root_cause_decision_authorized"
    ] is True
    assert backlog["next_action"][
        "research_lead_v3_conflict_local_direct_support_implementation_authorized"
    ] is False
    assert backlog["next_action"]["agent_execution_authorized"] is False


def test_decision_does_not_persist_plaintext_credentials() -> None:
    text = DECISION.read_text(encoding="utf-8")
    assert "DEEPSEEK_API_KEY" in text
    assert "sk-" not in text.lower()
