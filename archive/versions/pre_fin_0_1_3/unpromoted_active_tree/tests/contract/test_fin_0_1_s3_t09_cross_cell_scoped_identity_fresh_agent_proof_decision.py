from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DECISION = (
    ROOT
    / "configs/releases/fin_ia_0_1_s3_t09_cross_cell_scoped_identity_"
    "fresh_agent_proof_decision_v1_0.json"
)
BACKLOG = (
    ROOT
    / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_decision_binds_output_v4_and_exact_scoped_transports() -> None:
    from apps.workbench.backend.application.bounded_agent_contract_policies import (
        S3_NVDA_THREE_CELL_RESEARCH_PROFILE_REF,
    )
    from apps.workbench.backend.application.bounded_agent_executor import (
        S3_OWNER_GRADE_MEMO_WRITER_TRANSPORT_V3_REF,
        S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V4_REF,
        S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF,
        S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF,
        S3ThreeCellBoundedAgentAdmission,
    )
    from apps.workbench.backend.application.bounded_agent_identity_policies import (
        S3_CELL_SCOPED_RESEARCH_IDENTITY_CONTRACT_REF,
    )
    from sec_agent.canonical_runtime.models import canonical_digest

    prospective = _load(DECISION)["prospective_admission"]
    payload = prospective["payload"]
    admission = S3ThreeCellBoundedAgentAdmission(**payload)
    admission.assert_profile_admissible()

    assert canonical_digest(admission.digest_payload()) == prospective["digest"]
    assert payload["output_contract_ref"] == (
        S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF
    )
    assert payload["transport_ref"] == (
        S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF
    )
    assert payload["research_lead_transport_ref"] == (
        S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V4_REF
    )
    assert payload["memo_writer_transport_ref"] == (
        S3_OWNER_GRADE_MEMO_WRITER_TRANSPORT_V3_REF
    )
    assert payload["scoped_identity_contract_ref"] == (
        S3_CELL_SCOPED_RESEARCH_IDENTITY_CONTRACT_REF
    )
    assert payload["research_profile_ref"] == (
        S3_NVDA_THREE_CELL_RESEARCH_PROFILE_REF
    )


def test_decision_factory_construction_does_not_call_provider() -> None:
    from apps.workbench.backend.application.bounded_agent_executor import (
        S3ThreeCellBoundedAgentAdmission,
        build_s3_three_cell_bounded_agent_executor_for_admission,
    )

    payload = _load(DECISION)["prospective_admission"]["payload"]
    callback_calls = 0

    def _must_not_call_provider(**_: object) -> dict:
        nonlocal callback_calls
        callback_calls += 1
        raise AssertionError("provider_callback_forbidden_in_decision_test")

    build_s3_three_cell_bounded_agent_executor_for_admission(
        S3ThreeCellBoundedAgentAdmission(**payload),
        chat_completion_fn=_must_not_call_provider,
    )
    assert callback_calls == 0


def test_decision_freezes_freshness_budget_capture_and_stop() -> None:
    decision = _load(DECISION)
    budget = decision["budget_and_stop_contract"]
    audit = decision["audit_contract"]
    governance = decision["experiment_governance"]

    assert decision["double_prepare"]["independent_disposable_clone_invocations"] == 2
    assert decision["double_prepare"]["independent_invocation_equal"] is True
    assert decision["freshness_and_nonreuse"]["distinct_from_all_prior_agent_and_baseline_runs"]
    assert budget["semantic_model_calls"] == 12
    assert budget["provider_calls"] == 12
    assert budget["network_calls"] == 12
    assert budget["aggregate_max_output_tokens"] == 16800
    assert budget["retry_budget"] == 0
    assert budget["automatic_repair_fallback_or_rerun"] is False
    assert audit["target_service_initialization_allowed"] is False
    assert audit["service_backed_preparation"] == "disposable_clone_only"
    assert governance["admission_issuance_authorized"] is False
    assert governance["live_execution_authorized"] is False
    assert set(decision["observed_counts"].values()) == {0}


def test_decision_requires_complete_product_not_transport_only_green() -> None:
    acceptance = _load(DECISION)["artifact_acceptance_contract"]

    assert acceptance["success_requires_terminal_state"] == "succeeded"
    assert acceptance["success_requires_logical_nodes"] == 6
    assert acceptance["success_requires_provider_calls"] == 12
    assert acceptance["success_requires_artifact_families"] == 9
    assert acceptance["transport_only_green_is_success"] is False
    assert acceptance["failure_requires_typed_terminal_closeout"] is True
    assert acceptance["failure_preserves_completed_assistant_outputs_and_usage"] is True


def test_decision_remains_traced_after_separate_issuance_gate() -> None:
    decision = _load(DECISION)
    backlog = _load(BACKLOG)["next_action"]

    assert decision["next_action"] == (
        "S3-T09-OWNER-GRADE-CROSS-CELL-SCOPED-IDENTITY-"
        "FRESH-EXACT-ADMISSION-ISSUANCE"
    )
    assert backlog[
        "S3_T09_cross_cell_scoped_identity_fresh_agent_proof_decision_ref"
    ] == DECISION.relative_to(ROOT).as_posix()
    assert backlog[
        "cross_cell_scoped_identity_fresh_agent_proof_decision_authorized"
    ] is True
    assert backlog[
        "cross_cell_scoped_identity_fresh_exact_admission_issuance_authorized"
    ] is True
    assert backlog["cross_cell_scoped_identity_fresh_exact_admission_issued"] is True
    assert backlog[
        "cross_cell_scoped_identity_fresh_exact_admission_consumed"
    ] is True
    assert backlog["cross_cell_scoped_identity_fresh_live_execution_authorized"] is True
    assert backlog[
        "cross_cell_scoped_identity_research_lead_v4_capacity_recurrence_root_cause_decision_authorized"
    ] is True
    assert backlog["cross_cell_scoped_identity_agent_rerun_authorized"] is False
