from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_executor import (
    S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V3_REF,
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V5_REF,
    S3ThreeCellBoundedAgentAdmission,
    build_s3_three_cell_bounded_agent_executor_for_admission,
)
from sec_agent.canonical_runtime.models import canonical_digest


RELEASES = ROOT / "configs" / "releases"
DECISION = RELEASES / (
    "fin_ia_0_1_s3_t09_owner_grade_v3_research_lead_v3_"
    "fresh_agent_proof_decision_v1_0.json"
)
BACKLOG = RELEASES / "fin_ia_0_1_program_release_backlog_v2_0.json"
PROSPECTIVE_ADMISSION = RELEASES / (
    "fin_ia_0_1_s3_t09_three_cell_deepseek_owner_grade_v3_"
    "specialist_v5_research_lead_v3_exact_admission_v1_0.json"
)


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_decision_freezes_fresh_identity_without_issuance_or_execution() -> None:
    decision = _load(DECISION)
    assert decision["status"] == (
        "pass_fresh_specialist_v5_research_lead_v3_exact_proof_contract_"
        "decided_admission_issuance_pending_separate_authority"
    )
    authority = decision["authority"]
    assert authority["fresh_agent_proof_decision_authorized"] is True
    assert authority["exact_admission_issuance_authorized"] is False
    assert authority["admission_consumption_or_live_execution_authorized"] is False
    assert authority["model_provider_network_source_or_tool_execution_authorized"] is False
    assert authority["canonical_run_or_artifact_write_authorized"] is False
    identity = decision["fresh_identity"]
    assert identity["work_unit_id"] == "wu_p02_5_faa27f97931244939f6daf3f"
    assert identity["attempt_id"] == "attempt_fin01_1de0ba5e8037f6d2953d1733"
    assert identity["research_run_id"] == (
        "research_run_fin01_e418d7086d4a1d253e9b2c9b"
    )
    assert identity["input_digest"] == (
        "4574a5ce43ec24a8563d8ca2108de0880deb6659c4ffde7162f0d801a0dda9fb"
    )
    assert set(decision["observed_counts"].values()) == {0}


def test_double_prepare_and_target_read_only_audit_were_reproducible() -> None:
    verification = _load(DECISION)["preflight_verification"]
    assert verification["independent_prepare_invocation_count"] == 2
    assert verification["disposable_clone_double_prepare_equal"] is True
    assert verification["clone_execution_counts_before_and_after"] == [10, 10, 10, 13]
    assert verification["independent_prepared_payload_digest_equal"] is True
    assert verification["independent_admission_digest_equal"] is True
    assert verification["logical_snapshot_unchanged"] is True
    assert verification["canonical_database_file_unchanged"] is True
    assert verification["canonical_object_tree_unchanged"] is True
    assert verification["canonical_database_sha256"] == (
        "3a4390adca6f656e1f653636cd657da7cf8939aadf3c96c131444967013b2458"
    )
    assert verification["canonical_object_tree_sha256"] == (
        "42c30c3cc369e513bee5dd37a21c7fcdb7d5bdf4f9326e54215bdf89d6ee4784"
    )
    assert verification["provider_callback_invoked"] is False
    incident = verification["physical_checkpoint_incident"]
    assert incident["root_cause_id"].startswith("RC-P36-038")
    assert incident["prospective_execution_objects_created"] == 0
    assert incident["test_repaired_to_disposable_clone_only"] is True
    assert incident[
        "corrected_target_database_object_and_logical_snapshot_unchanged"
    ] is True


def test_prospective_admission_binds_v5_lead_v3_and_exact_budgets() -> None:
    prospective = _load(DECISION)["prospective_admission"]
    assert prospective["prospective_admission_file_absent_at_decision"] is True
    assert prospective["admission_issued_at_decision"] is False
    assert prospective["admission_consumed_at_decision"] is False
    assert prospective["execution_started_at_decision"] is False
    assert PROSPECTIVE_ADMISSION.exists()
    assert _load(PROSPECTIVE_ADMISSION) == prospective["payload"]

    admission = S3ThreeCellBoundedAgentAdmission.model_validate(
        prospective["payload"]
    )
    admission.assert_profile_admissible()
    assert admission.transport_ref == (
        S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V5_REF
    )
    assert admission.research_lead_transport_ref == (
        S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V3_REF
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


def test_nonreuse_truth_table_stop_and_product_target_are_closed() -> None:
    decision = _load(DECISION)
    freshness = decision["freshness_and_nonreuse"]
    assert freshness["prior_research_run_count"] == 10
    assert freshness["distinct_from_all_prior_agent_and_baseline_runs"] is True
    assert freshness["prior_admission_payload_or_digest_reusable"] is False
    assert freshness["baseline_output_body_exposed_to_agent"] is False

    contract = decision["research_lead_v3_contract_review"]
    assert contract["fact_presence_scope"] == (
        "each conflict involved Claim direct support_fact_ids"
    )
    assert set(contract["fact_presence_truth_table"].values()) == {
        "facts_present",
        "no_facts_present",
        "mixed_fact_presence",
    }
    assert contract["restricted_live_replay_mismatch_count"] == 1
    assert contract["historical_research_lead_v2_contract_and_runs_immutable"] is True

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


def test_project_os_preserves_decision_and_advances_to_exact_execution() -> None:
    decision = _load(DECISION)
    backlog = _load(BACKLOG)
    decision_next = (
        "S3-T09-OWNER-GRADE-V3-RESEARCH-LEAD-V3-FRESH-EXACT-"
        "ADMISSION-ISSUANCE"
    )
    assert decision["next_action"] == decision_next
    assert backlog["next_action"]["item_id"] == (
        "S3-T09-OWNER-GRADE-V3-RESEARCH-LEAD-V3-FRESH-EXACT-LIVE-EXECUTION"
    )
    next_action = backlog["next_action"]
    assert next_action["research_lead_v3_fresh_agent_proof_decision_authorized"] is True
    assert next_action["research_lead_v3_fresh_agent_proof_decision_status"] == (
        "pass_exact_identity_input_v5_lead_v3_budget_capture_nonreuse_and_"
        "first_failure_stop_contract_frozen"
    )
    assert next_action[
        "research_lead_v3_fresh_exact_admission_issuance_authorized"
    ] is True
    assert next_action["research_lead_v3_fresh_exact_admission_issued"] is True
    assert next_action["research_lead_v3_fresh_exact_admission_consumed"] is False
    assert next_action[
        "research_lead_v3_fresh_exact_live_execution_authorized"
    ] is False
    assert next_action["agent_execution_authorized"] is False
    assert next_action["agent_rerun_authorized"] is False
    assert next_action["owner_review_or_T10_authorized"] is False


def test_decision_does_not_persist_plaintext_credentials() -> None:
    text = DECISION.read_text(encoding="utf-8")
    assert "DEEPSEEK_API_KEY" in text
    assert "sk-" not in text.lower()
