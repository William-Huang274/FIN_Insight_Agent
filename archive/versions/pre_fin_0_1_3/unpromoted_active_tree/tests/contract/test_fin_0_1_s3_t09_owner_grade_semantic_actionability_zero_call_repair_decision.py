from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

RELEASES = ROOT / "configs" / "releases"
DECISION = (
    RELEASES
    / "fin_ia_0_1_s3_t09_owner_grade_semantic_actionability_zero_call_repair_decision_v1_0.json"
)
BACKLOG = RELEASES / "fin_ia_0_1_program_release_backlog_v2_0.json"
ROOT_CAUSES = ROOT / "docs" / "project_os" / "root_cause_issue_ledger.jsonl"


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _latest_issue(issue_id: str) -> dict[str, object]:
    latest: dict[str, dict[str, object]] = {}
    for line in ROOT_CAUSES.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            latest[str(row["issue_id"])] = row
    return latest[issue_id]


def test_decision_selects_upstream_typed_repair_without_authorizing_execution() -> None:
    decision = _load(DECISION)
    assert decision["status"] == (
        "pass_selected_upstream_to_verifier_typed_repair_implementation_pending"
    )
    authority = decision["authority"]
    assert authority["zero_call_repair_decision_authorized"] is True
    assert authority["repair_implementation_authorized"] is False
    assert authority["baseline_materialization_authorized"] is False
    assert authority["new_agent_proof_authorized"] is False
    assert set(decision["observed_counts"].values()) == {0}
    root = decision["root_cause_binding"]
    assert root["earliest_faulty_surface"] == (
        "specialist_outputs[value_and_profit_capture].judgment_layer"
    )
    assert root["classification"] == (
        "project_owned_output_contract_context_and_validator_gap_not_provider_json_failure"
    )


def test_decision_snapshot_records_why_verifier_only_repair_was_insufficient() -> None:
    decision = _load(DECISION)
    proof = decision["current_contract_gap_proof"]
    assert "fact_layer" in proof["specialist"]
    assert "judgment_layer" in proof["specialist"]
    assert "consumed claim refs" in proof["writer"]
    assert "not Specialist/Lead bodies" in proof["verifier_input"]
    assert "does not fail accept_for_internal_review" in proof["verifier_output"]
    assert proof["observed_false_negative_count"] == 4


def test_selected_contract_closes_claim_scope_fact_state_WWC_writer_and_verifier_gaps() -> None:
    decision = _load(DECISION)
    versions = decision["selected_contract_versions"]
    assert versions["three_cell_output_contract_ref"] == (
        "fin01.s3.bounded_agent_three_cell_output:v3"
    )
    claim = decision["specialist_claim_card_contract"]
    assert {
        "epistemic_status",
        "support_fact_ids",
        "context_refs",
        "scope",
        "qualification",
        "cannot_support",
    }.issubset(claim["required_fields"])
    assert "segment" in claim["business_scope_kind_enum"]
    assert "company_total" in claim["attribution_level_enum"]
    wwc = decision["actionable_what_would_change_contract"]
    assert {
        "source_target",
        "metric_or_observation",
        "decision_rule",
        "time_window",
    }.issubset(wwc["required_fields"])
    lead = decision["lead_contract"]
    assert "numeric_fact_count" in lead["cell_head_required_fields"]
    assert "fact_presence_summary" in lead["conflict_adjudication_required_fields"]
    writer = decision["writer_contract"]
    assert writer["writer_may_create_new_research_claims"] is False
    verifier = decision["verifier_contract"]
    assert "authority_surface_by_cell" in verifier["required_full_input_bodies"]
    assert "specialist_claim_cards" in verifier["required_full_input_bodies"]
    assert verifier["no_additional_model_call"] is True


def test_negative_fixture_matrix_covers_all_four_live_findings_and_false_green() -> None:
    decision = _load(DECISION)
    rows = decision["negative_fixture_matrix"]
    assert len(rows) == decision["implementation_acceptance_gate"]["negative_fixture_count"] == 10
    observed = {row["fixture_id"]: row for row in rows}
    assert {
        "unsupported_segment_revenue_from_company_total_numeric",
        "lead_non_fact_wording_with_numeric_fact_count_one",
        "writer_graph_context_mistranslated_as_chart",
        "WWC_missing_source_metric_rule_or_time",
        "verifier_accepts_with_local_semantic_issue",
    }.issubset(observed)
    assert all(row["earliest_rejector"] and row["expected_failure_code"] for row in rows)


def test_decision_historical_next_action_and_current_backlog_progress_are_consistent() -> None:
    decision = _load(DECISION)
    backlog = _load(BACKLOG)
    assert decision["next_action"] == (
        "S3-T09-OWNER-GRADE-SEMANTIC-ACTIONABILITY-ZERO-CALL-REPAIR-IMPLEMENTATION"
    )
    assert backlog["next_action"]["item_id"] == (
        "S3-T09-OWNER-GRADE-V3-SEGMENTED-TRANSPORT-V5-RESEARCH-LEAD-OUTPUT-TRUNCATION-RESULT-AND-ROOT-CAUSE-DECISION"
    )
    assert backlog["next_action"][
        "S3_T09_owner_grade_semantic_actionability_zero_call_repair_decision_authorized"
    ] is True
    assert backlog["next_action"][
        "S3_T09_owner_grade_semantic_actionability_zero_call_repair_implementation_authorized"
    ] is True
    assert backlog["next_action"]["deterministic_baseline_materialization_authorized"] is True
    assert backlog["next_action"]["fresh_v3_agent_proof_decision_authorized"] is True
    assert backlog["next_action"]["fresh_v3_exact_admission_issuance_authorized"] is True
    assert backlog["next_action"]["fresh_v3_exact_admission_issued"] is True
    assert backlog["next_action"]["fresh_v3_exact_live_execution_authorized"] is True
    assert backlog["next_action"]["agent_rerun_authorized"] is False
    issue = _latest_issue(
        "RC-P36-037-s3-owner-grade-semantic-actionability-and-verifier-false-negative-gap"
    )
    assert issue["status"] == (
            "semantic_repair_and_transport_v5_assembly_live_proven_lead_truncation_"
            "no_complete_artifact_proof"
    )


def test_implementation_gate_preserves_runtime_budget_and_historical_truth() -> None:
    decision = _load(DECISION)
    gate = decision["implementation_acceptance_gate"]
    assert gate["historical_v1_v2_admissions_digests_and_artifacts_unchanged"] is True
    assert gate["existing_profile_transport_runtime_registry_writer_and_store_families_reused"] is True
    assert gate["stage_output_token_budgets"] == {
        "specialist": 2200,
        "lead": 1200,
        "writer": 1400,
        "verifier": 1000,
        "aggregate": 10200,
    }
    assert gate["model_provider_network_source_tool_calls"] == 0
    assert gate["new_admission_or_live_run"] == 0
    assert gate["baseline_materialization"] == 0
    assert gate["human_review"] == 0
