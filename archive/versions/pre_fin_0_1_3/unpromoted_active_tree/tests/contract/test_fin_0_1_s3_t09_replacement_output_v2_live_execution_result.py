from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RELEASES = ROOT / "configs" / "releases"
RESULT = RELEASES / "fin_ia_0_1_s3_t09_replacement_output_v2_live_execution_result_v1_0.json"
ADMISSION = RELEASES / "fin_ia_0_1_s3_t09_three_cell_deepseek_segmented_output_v2_exact_admission_v1_0.json"
ISSUANCE = RELEASES / "fin_ia_0_1_s3_t09_replacement_exact_admission_issuance_v1_0.json"
BACKLOG = RELEASES / "fin_ia_0_1_program_release_backlog_v2_0.json"


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_result_binds_consumed_admission_and_terminal_success() -> None:
    result = _load(RESULT)
    admission = _load(ADMISSION)
    issuance = _load(ISSUANCE)
    assert result["status"] == (
        "terminal_succeeded_artifacts_complete_T09_acceptance_pending_paired_baseline"
    )
    assert result["preflight"]["admission_id"] == admission["admission_id"]
    assert result["preflight"]["admission_digest"] == issuance["issued_admission"]["admission_digest"]
    terminal = result["canonical_terminal_truth"]
    assert {terminal[key] for key in ("work_unit_state", "attempt_state", "research_run_state")} == {"succeeded"}
    assert terminal["orphaned_run"] is False
    assert terminal["artifact_count"] == 9


def test_provider_usage_is_exact_six_call_no_retry_and_within_budget() -> None:
    result = _load(RESULT)
    provider = result["provider_execution"]
    assert [provider[key] for key in ("model_calls", "provider_calls", "network_calls")] == [6, 6, 6]
    assert [provider[key] for key in ("retry_count", "fallback_count", "rerun_count")] == [0, 0, 0]
    assert provider["total_tokens"] == 17683
    assert provider["estimated_cost_usd"] == 0.00893187
    assert provider["estimated_cost_usd"] < result["preflight"]["maximum_total_cost_usd"]
    assert len(provider["usage_receipts"]) == 6
    assert {row["finish_reason"] for row in provider["usage_receipts"]} == {"stop"}
    assert {row["transport_attempt_count"] for row in provider["usage_receipts"]} == {1}


def test_artifacts_model_views_and_boundaries_are_complete() -> None:
    result = _load(RESULT)
    artifacts = result["artifact_validation"]
    assert len(artifacts["artifact_types"]) == len(artifacts["artifact_refs"]) == 9
    assert artifacts["node_receipt_count"] == 6
    assert len(artifacts["specialist_model_view_bindings"]) == 3
    assert {row["model_view_contract_ref"] for row in artifacts["specialist_model_view_bindings"]} == {"fin01.s3.specialist_model_view:v1"}
    assert set(artifacts["machine_verifier_findings"].values()) == {"pass"}
    assert artifacts["machine_verifier_is_human_acceptance"] is False
    assert set(result["boundary_observation"].values()) == {0, False}


def test_live_execution_pass_does_not_prematurely_accept_t09() -> None:
    result = _load(RESULT)
    comparison = result["comparison_and_acceptance"]
    assert comparison["comparison_status"] == "pending_distinct_terminal_deterministic_run"
    assert comparison["owner_review_status"] == "not_performed"
    assert comparison["T09_acceptance"] == "pending_paired_baseline_and_read_only_artifact_acceptance"
    assert comparison["T10_unblocked"] is False
    assert result["research_quality_observation"]["investment_alpha_proven"] is False
    assert result["next_action"] == (
        "S3-T09-REPLACEMENT-LIVE-ARTIFACT-READ-ONLY-VALIDATION-AND-PAIRED-BASELINE-DECISION"
    )


def test_backlog_records_completed_validation_and_keeps_materialization_unauthorized() -> None:
    backlog = _load(BACKLOG)
    next_action = backlog["next_action"]
    assert next_action["item_id"] == (
        "S3-T09-OWNER-GRADE-V3-SEGMENTED-TRANSPORT-V5-RESEARCH-LEAD-OUTPUT-TRUNCATION-RESULT-AND-ROOT-CAUSE-DECISION"
    )
    assert next_action["fresh_v3_agent_proof_decision_authorized"] is True
    assert next_action["fresh_v3_exact_admission_issuance_authorized"] is True
    assert next_action["fresh_v3_exact_admission_issued"] is True
    assert next_action["fresh_v3_exact_live_execution_authorized"] is True
    assert next_action["S3_T09_replacement_exact_admission_consumed"] is True
    assert next_action["S3_T09_replacement_exact_live_execution_authorized"] is True
    assert next_action["S3_T09_replacement_live_execution_terminal_status"] == "succeeded"
    assert next_action["S3_T09_replacement_artifact_paired_baseline_validation_authorized"] is True
    assert next_action["S3_T09_paired_baseline_minimum_gate_candidate_count"] == 1
    assert next_action["deterministic_baseline_materialization_authorized"] is True
    assert next_action["release_or_production_authorized"] is False
