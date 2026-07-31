from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
DECISION = (
    ROOT
    / "configs/releases/fin_ia_0_1_s3_t09_claim_fact_link_policy_"
    "fresh_agent_proof_decision_v1_0.json"
)
IMPLEMENTATION = (
    ROOT
    / "configs/releases/fin_ia_0_1_s3_t09_claim_fact_link_policy_closed_"
    "alias_zero_call_implementation_v1_0.json"
)
BACKLOG = (
    ROOT
    / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_decision_requires_fixture_proven_policy_and_failed_source_truth() -> None:
    decision = _load(DECISION)
    implementation = _load(IMPLEMENTATION)

    assert implementation["status"] == (
        "pass_zero_call_shared_claim_fact_link_policy_closed_alias_local_"
        "expansion_fixture_proven"
    )
    assert decision["source_refs"]["claim_fact_link_policy_implementation"] == (
        IMPLEMENTATION.relative_to(ROOT).as_posix()
    )
    assert decision["source_refs"]["final_claim_fact_identity_failure"].endswith(
        "profile_v3_final_exact_live_execution_result_v1_0.json"
    )


def test_decision_binds_exact_profile_policy_and_digest() -> None:
    from apps.workbench.backend.application.bounded_agent_contract_policies import (
        S3_CLAIM_FACT_LINK_POLICY_REF,
        S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V3_REF,
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
    assert payload["claim_fact_link_policy_ref"] == (
        S3_CLAIM_FACT_LINK_POLICY_REF
    )
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
    assert payload["research_profile_ref"] == (
        S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V3_REF
    )
    assert payload["scoped_identity_contract_ref"] == (
        S3_CELL_SCOPED_RESEARCH_IDENTITY_CONTRACT_REF
    )


def test_decision_factory_construction_is_zero_call() -> None:
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


def test_decision_freezes_freshness_budget_nonreuse_and_target_integrity() -> None:
    decision = _load(DECISION)
    budget = decision["budget_and_stop_contract"]
    prospective = decision["prospective_admission"]

    assert decision["freshness_and_nonreuse"][
        "distinct_from_all_prior_agent_and_baseline_runs"
    ]
    assert decision["freshness_and_nonreuse"][
        "additional_consumed_failed_identity_count"
    ] == 14
    assert decision["target_read_only_audit"]["expected_prior_research_run_count"] == 18
    assert decision["target_read_only_audit"]["canonical_database_file_unchanged"]
    assert decision["target_read_only_audit"]["canonical_object_tree_unchanged"]
    assert budget["semantic_model_calls"] == 12
    assert budget["provider_calls"] == 12
    assert budget["network_calls"] == 12
    assert budget["aggregate_max_output_tokens"] == 16800
    assert budget["max_total_cost_usd"] == 0.1
    assert budget["retry_budget"] == 0
    assert budget["automatic_repair_fallback_or_rerun"] is False
    assert prospective["admission_issued"] is False
    assert prospective["admission_consumed"] is False
    assert prospective["execution_started"] is False
    assert set(decision["observed_counts"].values()) == {0}


def test_decision_requires_live_claim_fact_lineage_and_complete_product() -> None:
    decision = _load(DECISION)
    link = decision["claim_fact_link_live_acceptance_contract"]
    product = decision["artifact_acceptance_contract"]

    assert link["all_three_claim_segments_receive_policy_binding"] is True
    assert link["provider_response_support_field"] == "support_fact_aliases"
    assert link["provider_support_fact_ids_when_policy_active_allowed"] is False
    assert link["expanded_support_must_resolve_to_validated_same_Cell_Facts"]
    assert link["persisted_alias_residue_required"] == 0
    assert link["persisted_source_ref_as_claim_support_required"] == 0
    assert product["success_requires_terminal_state"] == "succeeded"
    assert product["success_requires_logical_nodes"] == 6
    assert product["success_requires_provider_calls"] == 12
    assert product["success_requires_artifact_families"] == 9
    assert product["transport_or_specialist_only_green_is_success"] is False


def test_decision_remains_traced_after_issuance_and_exact_live_gate() -> None:
    decision = _load(DECISION)
    governance = decision["experiment_governance"]
    next_action = _load(BACKLOG)["next_action"]

    assert decision["next_action"] == (
        "S3-T09-GENERALIZED-CLAIM-FACT-LINK-POLICY-"
        "FRESH-EXACT-ADMISSION-ISSUANCE"
    )
    assert governance["decision_label"] == (
        "proceed_to_separate_exact_admission_issuance_gate"
    )
    assert governance["admission_issuance_authorized"] is False
    assert governance["admission_consumption_authorized"] is False
    assert governance["live_execution_authorized"] is False
    assert governance[
        "automatic_retry_fallback_patch_or_rerun_authorized"
    ] is False
    assert next_action[
        "S3_T09_claim_fact_link_policy_fresh_exact_admission_issuance_ref"
    ] == (
        "configs/releases/"
        "fin_ia_0_1_s3_t09_claim_fact_link_policy_"
        "fresh_exact_admission_issuance_v1_0.json"
    )
    assert next_action[
        "S3_T09_claim_fact_link_policy_fresh_agent_proof_decision_ref"
    ] == DECISION.relative_to(ROOT).as_posix()
    assert next_action["claim_fact_link_fresh_proof_authorized"] is True
    assert next_action["claim_fact_link_exact_admission_issued"] is True
    assert next_action["claim_fact_link_exact_admission_consumed"] is True
    assert next_action["claim_fact_link_second_execution_authorized"] is False
    assert next_action["agent_execution_authorized"] is False
