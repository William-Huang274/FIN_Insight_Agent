from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RELEASES = ROOT / "configs" / "releases"
RESULT = RELEASES / (
    "fin_ia_0_1_s3_t09_cross_cell_scoped_identity_"
    "fresh_live_execution_result_v1_0.json"
)
ADMISSION = RELEASES / (
    "fin_ia_0_1_s3_t09_three_cell_deepseek_cross_cell_"
    "scoped_identity_output_v4_exact_admission_r1.json"
)
BACKLOG = RELEASES / "fin_ia_0_1_program_release_backlog_v2_0.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_live_result_consumed_exact_admission_once_and_terminalized() -> None:
    from apps.workbench.backend.application.bounded_agent_executor import (
        S3ThreeCellBoundedAgentAdmission,
    )
    from sec_agent.canonical_runtime.models import canonical_digest

    result = _load(RESULT)
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(_load(ADMISSION))

    assert result["status"] == (
        "terminal_failed_research_lead_v4_provider_length_stop_"
        "admission_consumed_no_retry"
    )
    assert canonical_digest(admission.digest_payload()) == result["identity"][
        "admission_digest"
    ]
    assert result["canonical_terminal_truth"]["work_unit_state"] == "failed"
    assert result["canonical_terminal_truth"]["attempt_state"] == "failed"
    assert result["canonical_terminal_truth"]["research_run_state"] == "failed"
    assert result["canonical_terminal_truth"]["orphaned_run"] is False
    assert result["observed_counts"]["admissions_consumed"] == 1
    assert result["observed_counts"]["research_runs_created"] == 1


def test_live_result_records_exact_usage_capture_and_no_retry() -> None:
    result = _load(RESULT)
    provider = result["provider_execution"]
    capture = result["provider_output_capture"]

    assert provider["model_provider_network_calls"] == [10, 10, 10]
    assert provider["input_output_total_tokens"] == [42373, 6279, 48652]
    assert provider["estimated_cost_usd"] == 0.02284589
    assert provider["retry_fallback_rerun_counts"] == [0, 0, 0]
    assert provider["specialist_segments_completed"] == 9
    assert provider["research_lead_called"] is True
    assert provider["memo_writer_called"] is False
    assert provider["verifier_called"] is False
    assert provider["research_lead_output_tokens_and_cap"] == [1800, 1800]
    assert capture["capture_count"] == 10
    assert capture["restricted_readback_count"] == 10
    assert capture["assistant_output_present_count"] == 10


def test_live_result_proves_capacity_cut_not_scoped_identity_parse_conflict() -> None:
    result = _load(RESULT)
    audit = result["restricted_research_lead_capture_audit"]
    failure = result["failure_observation"]

    assert failure["stage"] == "research_lead"
    assert failure["failure_family"] == "capacity"
    assert failure["failure_subtype"] == "provider_length_stop"
    assert failure["first_credible_failure_stopped_execution"] is True
    assert audit["assistant_output_characters_and_utf8_bytes"] == [7177, 7177]
    assert audit["json_valid"] is False
    assert audit["truncated_inside_field"] == "program_cell_id"
    assert audit["identity_kind_occurrences"] == 25
    assert audit["all_three_program_cells_observed"] is True
    assert audit["complete_output_proven"] is False


def test_live_result_fails_complete_product_acceptance() -> None:
    result = _load(RESULT)
    acceptance = result["product_acceptance"]

    assert result["canonical_terminal_truth"]["artifact_count"] == 0
    assert acceptance["required_terminal_state"] == "succeeded"
    assert acceptance["required_provider_calls"] == 12
    assert acceptance["required_artifact_families"] == 9
    assert acceptance["observed_provider_calls"] == 10
    assert acceptance["observed_artifact_families"] == 0
    assert acceptance["fresh_agent_product_proof"] == "failed"
    assert acceptance["junior_analyst_deliverable"] is False
    assert acceptance["paired_comparison_authorized_or_performed"] is False


def test_live_result_remains_traced_after_zero_call_root_cause_decision() -> None:
    result = _load(RESULT)
    backlog = _load(BACKLOG)["next_action"]

    assert result["next_action"] == (
        "S3-T09-OWNER-GRADE-CROSS-CELL-SCOPED-IDENTITY-"
        "RESEARCH-LEAD-V4-CAPACITY-RECURRENCE-ZERO-CALL-"
        "ROOT-CAUSE-DECISION"
    )
    assert backlog[
        "S3_T09_cross_cell_scoped_identity_fresh_live_execution_result_ref"
    ] == RESULT.relative_to(ROOT).as_posix()
    assert backlog["cross_cell_scoped_identity_fresh_exact_admission_consumed"]
    assert backlog["cross_cell_scoped_identity_fresh_live_execution_authorized"]
    assert backlog[
        "cross_cell_scoped_identity_research_lead_v4_capacity_recurrence_root_cause_decision_authorized"
    ]
    assert backlog["cross_cell_scoped_identity_agent_rerun_authorized"] is False
