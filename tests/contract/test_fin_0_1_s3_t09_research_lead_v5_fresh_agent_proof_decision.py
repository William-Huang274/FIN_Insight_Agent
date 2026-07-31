from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DECISION = (
    ROOT
    / "configs/releases/fin_ia_0_1_s3_t09_research_lead_v5_"
    "fresh_agent_proof_decision_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_decision_binds_v5_profile_v2_output_v4_and_scoped_identity() -> None:
    from apps.workbench.backend.application.bounded_agent_contract_policies import (
        S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V2_REF,
    )
    from apps.workbench.backend.application.bounded_agent_executor import (
        S3_OWNER_GRADE_MEMO_WRITER_TRANSPORT_V3_REF,
        S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V5_REF,
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
        S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V5_REF
    )
    assert payload["memo_writer_transport_ref"] == (
        S3_OWNER_GRADE_MEMO_WRITER_TRANSPORT_V3_REF
    )
    assert payload["scoped_identity_contract_ref"] == (
        S3_CELL_SCOPED_RESEARCH_IDENTITY_CONTRACT_REF
    )
    assert payload["research_profile_ref"] == (
        S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V2_REF
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


def test_decision_freezes_freshness_budget_capacity_capture_and_stop() -> None:
    decision = _load(DECISION)
    budget = decision["budget_and_stop_contract"]
    capacity = decision["capacity_contract"]
    governance = decision["experiment_governance"]

    assert decision["double_prepare"]["independent_disposable_clone_invocations"] == 2
    assert decision["double_prepare"]["independent_invocation_equal"] is True
    assert decision["freshness_and_nonreuse"][
        "distinct_from_all_prior_agent_and_baseline_runs"
    ]
    assert budget["semantic_model_calls"] == 12
    assert budget["provider_calls"] == 12
    assert budget["network_calls"] == 12
    assert budget["aggregate_max_output_tokens"] == 16800
    assert budget["lead_max_output_tokens"] == 1800
    assert budget["retry_budget"] == 0
    assert budget["automatic_repair_fallback_or_rerun"] is False
    assert capacity["provider_raw_wire_utf8_byte_maximum"] == 8192
    assert capacity["canonical_alias_segment_utf8_byte_maximum"] == 6000
    assert capacity["local_expanded_hard_utf8_byte_maximum"] == 32768
    assert capacity["token_or_cost_increase_selected"] is False
    assert governance["admission_issuance_authorized"] is False
    assert governance["live_execution_authorized"] is False
    assert set(decision["observed_counts"].values()) == {0}


def test_decision_requires_complete_product_and_no_alias_residue() -> None:
    decision = _load(DECISION)
    acceptance = decision["artifact_acceptance_contract"]
    architecture = decision["architecture_contract"]

    assert acceptance["success_requires_terminal_state"] == "succeeded"
    assert acceptance["success_requires_logical_nodes"] == 6
    assert acceptance["success_requires_provider_calls"] == 12
    assert acceptance["success_requires_artifact_families"] == 9
    assert acceptance["transport_or_lead_only_green_is_success"] is False
    assert acceptance["failure_requires_typed_terminal_closeout"] is True
    assert acceptance["failure_preserves_completed_assistant_outputs_and_usage"]
    assert acceptance["complete_product_semantic_review_required_after_live_success"]
    assert architecture["provider_alias_is_authoritative_or_persisted"] is False
    assert architecture["provider_alias_expands_before_output_v4_validation"]
    assert architecture["writer_verifier_and_artifact_alias_residue_allowed"] is False


def test_decision_is_a_zero_call_preissuance_gate() -> None:
    decision = _load(DECISION)

    assert decision["status"] == (
        "pass_zero_call_research_lead_v5_fresh_exact_proof_contract_"
        "frozen_admission_issuance_pending_separate_authority"
    )
    assert decision["next_action"] == (
        "S3-T09-OWNER-GRADE-RESEARCH-LEAD-V5-FRESH-EXACT-"
        "ADMISSION-ISSUANCE"
    )
    assert decision["prospective_admission"]["admission_issued"] is False
    assert decision["prospective_admission"]["admission_consumed"] is False
    assert decision["prospective_admission"]["execution_started"] is False
    assert decision["comparison_boundary"]["paired_comparison_performed"] is False
    assert decision["comparison_boundary"]["owner_acceptance_performed"] is False
