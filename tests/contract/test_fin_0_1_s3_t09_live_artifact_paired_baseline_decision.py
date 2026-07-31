from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RELEASES = ROOT / "configs" / "releases"
DECISION = RELEASES / "fin_ia_0_1_s3_t09_replacement_live_artifact_paired_baseline_decision_v1_0.json"
BACKLOG = RELEASES / "fin_ia_0_1_program_release_backlog_v2_0.json"


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_read_only_decision_accepts_integrity_without_accepting_research_quality() -> None:
    decision = _load(DECISION)
    assert decision["status"] == (
        "artifact_integrity_pass_owner_grade_repair_required_no_paired_baseline"
    )
    integrity = decision["artifact_integrity_validation"]
    assert integrity["status"] == "pass"
    assert integrity["canonical_terminal_states"] == ["succeeded"] * 3
    assert integrity["artifact_count"] == 9
    assert integrity["evidence_fact_row_count"] == 0
    assert integrity["numeric_fact_row_count"] == 1
    assert integrity["unsupported_numeric_precision_found"] is False
    quality = decision["owner_grade_quality_validation"]
    assert quality["machine_verifier_decision"] == "accept_for_internal_review"
    assert quality["machine_verifier_reported_issue_count"] == 0
    assert quality["independent_disposition"] == "repair_before_final_acceptance"
    assert quality["machine_verifier_false_negative_confirmed"] is True
    assert {row["finding_id"] for row in quality["findings"]} == {
        "unsupported_declarative_segment_revenue_claim",
        "lead_non_fact_state_wording_conflicts_with_numeric_fact_row",
        "graph_hypothesis_mistranslated_as_chart_hypothesis",
        "what_would_change_lacks_actionable_source_metric_threshold_time_contract",
    }


def test_baseline_search_proves_absence_at_the_minimum_gate() -> None:
    decision = _load(DECISION)
    search = decision["paired_baseline_search"]
    assert search["searched_canonical_database_count"] == 11
    assert search["query_error_count"] == 0
    assert search["same_case_and_input_head_run_count"] == 2
    assert {row["profile_ref"] for row in search["same_case_and_input_head_runs"]} == {
        "fin01.execution_profile.bounded_agent_internal_three_cell:v1"
    }
    assert search["minimum_gate_terminal_deterministic_candidate_count"] == 0
    assert search["qualifying_paired_baseline_exists"] is False
    assert search["T08_deterministic_run_reusable"] is False
    assert search["decision"] == (
        "no_qualifying_baseline_exists_materialization_decision_required"
    )


def test_read_only_boundary_and_stage_decision_remain_closed() -> None:
    decision = _load(DECISION)
    audit = decision["read_only_audit"]
    assert audit["all_searched_database_digests_unchanged"] is True
    assert audit["target_object_tree_digest_unchanged"] is True
    assert {
        audit[key]
        for key in (
            "model_calls",
            "provider_calls",
            "network_calls",
            "source_network_calls",
            "external_tool_calls",
            "canonical_writes",
            "human_review_writes",
        )
    } == {0}
    stage = decision["stage_decision"]
    assert stage["artifact_integrity_gate"] == "pass"
    assert stage["owner_grade_quality_gate"] == "repair_required"
    assert stage["paired_baseline_gate"] == "fail_absent"
    assert stage["T09_acceptance"] == (
        "blocked_missing_paired_baseline_and_owner_grade_semantic_repair"
    )
    assert stage["T10_unblocked"] is False
    assert stage["deterministic_baseline_materialized"] is False


def test_historical_decision_points_to_baseline_decision_and_current_backlog_advances() -> None:
    decision = _load(DECISION)
    backlog = _load(BACKLOG)
    assert decision["next_action"] == (
        "S3-T09-PAIRED-DETERMINISTIC-BASELINE-MATERIALIZATION-DECISION"
    )
    assert backlog["next_action"]["item_id"] == (
        "S3-T09-OWNER-GRADE-V3-SEGMENTED-TRANSPORT-V5-RESEARCH-LEAD-OUTPUT-TRUNCATION-RESULT-AND-ROOT-CAUSE-DECISION"
    )
    assert backlog["next_action"]["fresh_v3_agent_proof_decision_authorized"] is True
    assert backlog["next_action"]["fresh_v3_exact_admission_issuance_authorized"] is True
    assert backlog["next_action"]["fresh_v3_exact_admission_issued"] is True
    assert backlog["next_action"]["fresh_v3_exact_live_execution_authorized"] is True
    assert backlog["next_action"]["S3_T09_read_only_artifact_validation_authorized"] is True
    assert backlog["next_action"]["S3_T09_paired_baseline_minimum_gate_candidate_count"] == 1
    assert backlog["next_action"]["S3_T09_paired_baseline_materialization_decision_authorized"] is True
    assert backlog["next_action"]["deterministic_baseline_materialization_authorized"] is True
    assert backlog["next_action"]["owner_review_or_T10_authorized"] is False
    assert backlog["next_action"]["release_or_production_authorized"] is False
