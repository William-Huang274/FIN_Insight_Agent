from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RELEASES = ROOT / "configs/releases"
SUCCESS = RELEASES / (
    "fin_ia_0_1_s4_t06_mu_research_lead_fact_presence_local_"
    "materialization_r2_exact_live_execution_success_result_v1_0.json"
)
BASELINE = RELEASES / (
    "fin_ia_0_1_s4_t06_mu_r2_source_grounded_deterministic_"
    "baseline_materialization_v1_0.json"
)
ASSESSMENT = RELEASES / (
    "fin_ia_0_1_s4_t06_mu_r2_success_only_paired_assessment_result_v1_0.json"
)
PROGRAM_BACKLOG = RELEASES / "fin_ia_0_1_program_release_backlog_v2_0.json"
DETAILED_BACKLOG = (
    RELEASES / "fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
)
ROOT_CAUSE_LEDGER = ROOT / "docs/project_os/root_cause_issue_ledger.jsonl"
NEXT_ACTION = (
    "S4-T06-MU-R2-L1-NUMERIC-AUTHORITY-AND-CASE-IDENTITY-"
    "LIVE-RECURRENCE-ROOT-CAUSE-OR-SCOPE-DISPOSITION-DECISION"
)
CURRENT_NEXT = (
    "S4-T06-MU-CASE-RUNTIME-MANDATORY-MATERIAL-TRUTH-AND-IDENTITY-"
    "SAFETY-CLOSURE-FRESH-AGENT-PROOF-DECISION"
)
RC_067 = "RC-P36-067-s4-R10-numeric-reference-value-correspondence-false-negative"
RC_068 = "RC-P36-068-s4-R10-case-identity-title-contract-hardcoded-NVDA"
RC_078 = (
    "RC-P36-078-s4-t06-mu-research-lead-deterministic-"
    "fact-presence-summary-model-ownership-recurrence"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _latest_issue(issue_id: str) -> dict:
    rows = [
        json.loads(line)
        for line in ROOT_CAUSE_LEDGER.read_text(encoding="utf-8").splitlines()
        if line.strip() and json.loads(line)["issue_id"] == issue_id
    ]
    return rows[-1]


def test_exact_live_success_is_exact_once_six_node_nine_artifact_truth() -> None:
    result = _load(SUCCESS)

    assert result["status"] == (
        "terminal_succeeded_exact_once_nine_artifacts_"
        "success_only_paired_assessment_eligible"
    )
    assert list(result["canonical_terminal_truth"].values())[:3] == [
        "succeeded",
        "succeeded",
        "succeeded",
    ]
    assert result["canonical_terminal_truth"]["logical_node_count"] == 6
    assert result["canonical_terminal_truth"]["artifact_count"] == 9
    provider = result["provider_execution"]
    assert provider["model_provider_network_calls"] == [12, 12, 12]
    assert provider["usage_receipts"] == 12
    assert provider["restricted_captures"] == 12
    assert provider["restricted_readbacks"] == 12
    assert provider["retry_fallback_replay_relaunch_rerun"] == [0, 0, 0, 0, 0]
    assert provider["input_output_total_tokens"] == [69484, 7734, 77218]
    assert provider["estimated_cost_usd"] == 0.0303834
    assert result["verification"]["decision"] == "accept_for_internal_review"
    assert result["stage_acceptance"]["RC_P36_078_runtime_recurrence"] is False

    evidence = result["evidence"]
    for ref_key, sha_key in (
        ("project_os_preflight_ref", "project_os_preflight_sha256"),
        ("runner_preflight_ref", "runner_preflight_sha256"),
        ("runtime_result_ref", "runtime_result_sha256"),
        ("terminal_inspection_ref", "terminal_inspection_sha256"),
        ("launch_receipt_ref", "launch_receipt_sha256"),
        ("exit_receipt_ref", "exit_receipt_sha256"),
    ):
        assert _sha256(ROOT / evidence[ref_key]) == evidence[sha_key]


def test_success_only_baseline_is_distinct_zero_call_and_exact_once() -> None:
    result = _load(BASELINE)

    assert result["status"] == (
        "pass_exact_once_source_grounded_deterministic_baseline_"
        "materialized_and_read_only_verified"
    )
    assert result["source_grounding"]["case_ticker"] == "MU"
    assert result["source_grounding"]["prospective_double_prepare_equal"]
    assert result["terminal_truth"]["exact_deterministic_run_cardinality"] == 1
    assert result["terminal_truth"]["artifact_count"] == 4
    assert result["terminal_truth"]["source_agent_artifact_count"] == 9
    assert result["identity"]["research_run_id"] != (
        result["identity"]["distinct_from_agent_research_run_id"]
    )
    assert set(result["observed_counts"].values()) == {0, 1}
    assert result["observed_counts"]["baseline_materializations"] == 1
    assert result["observed_counts"]["model_calls"] == 0
    assert result["observed_counts"]["provider_calls"] == 0
    assert result["observed_counts"]["network_calls"] == 0
    assert result["canonical_delta"]["source_agent_run_and_artifacts_unchanged"]
    assert result["read_only_verification"]["status"].startswith("pass_")


def test_independent_paired_assessment_blocks_false_green_verifier() -> None:
    result = _load(ASSESSMENT)
    layers = result["four_layer_assessment"]

    assert result["status"] == (
        "fail_L1_numeric_authority_and_case_identity_integrity_"
        "owner_acceptance_ineligible"
    )
    assert result["artifact_sets"]["agent"]["artifact_count"] == 9
    assert result["artifact_sets"]["deterministic_baseline"]["artifact_count"] == 4
    assert layers["L1_hard_integrity"]["status"] == "fail"
    assert layers["L1_hard_integrity"]["finding_count"] == 2
    assert layers["L1_hard_integrity"]["machine_verifier_false_negative_confirmed"]
    findings = {
        item["finding_id"]: item
        for item in layers["L1_hard_integrity"]["findings"]
    }
    numeric = findings[
        "agent_numeric_statements_do_not_equal_bound_MU_numeric_authority"
    ]
    assert numeric["mismatched_agent_numeric_fact_count"] == 5
    assert numeric["official_source_cross_check"]["status"] == (
        "source_pack_values_confirmed"
    )
    title = findings["MU_report_title_declares_NVDA"]
    assert title["observed"] == "NVDA 三单元内部研究备忘录"
    assert title["required_scope"] == "MU"
    assert title["model_owned_field"] is False
    assert layers["L2_recoverable_protocol"]["status"] == "pass"
    assert layers["L3_analytical_quality"]["status"].startswith(
        "material_gain_present"
    )
    assert layers["L4_user_fit_and_delivery"]["status"].startswith("fail_")
    assert result["stage_decision"]["MU_R2"] == "not_proven"
    assert result["stage_decision"]["owner_acceptance_written"] is False
    assert result["stage_decision"]["S4_T07_unblocked"] is False
    assert result["next_action"] == NEXT_ACTION

    for ref_key, sha_key in (
        ("agent_result_ref", "agent_result_sha256"),
        ("agent_runtime_result_ref", "agent_runtime_result_sha256"),
        ("baseline_result_ref", "baseline_result_sha256"),
        ("source_pack_ref", "source_pack_sha256"),
        ("acceptance_standard_ref", "acceptance_standard_sha256"),
    ):
        source = result["source_evidence"]
        assert _sha256(ROOT / source[ref_key]) == source[sha_key]


def test_ledgers_and_backlogs_stop_before_R3_and_T07() -> None:
    assessment = _load(ASSESSMENT)
    assert assessment["root_cause_updates"][RC_078]["status"].startswith("closed_")
    assert assessment["root_cause_updates"][RC_067]["status"].startswith("reopened_")
    assert assessment["root_cause_updates"][RC_068]["status"].startswith("reopened_")

    assert _latest_issue(RC_078)["status"] == (
        "closed_exact_live_Lead_v7_local_materialization_proven"
    )
    latest_067 = _latest_issue(RC_067)
    latest_068 = _latest_issue(RC_068)
    assert latest_067["status"] == "open"
    assert latest_068["status"] == "open"
    assert latest_067["disposition_status"] in {
        "final_numeric_rendering_live_reproof_pending_"
        "blocked_by_RC_P36_080_and_RC_P36_081",
        "classifier_v2_fixture_proven_final_numeric_rendering_"
        "exact_live_reproof_pending",
        "classifier_v2_fresh_proof_pass_final_numeric_rendering_"
        "R5_exact_live_reproof_pending",
        "R5_admission_issuance_authorized_not_issued_final_numeric_"
        "exact_live_reproof_pending",
        "R5_admission_issued_unconsumed_final_numeric_exact_live_"
        "authority_pending",
        "R5_exact_once_execution_authorized_not_started_final_numeric_"
        "live_reproof_pending",
        "R5_terminal_failed_before_final_Artifact_numeric_L1_no_R6",
    }
    assert latest_068["disposition_status"] in {
        "provider_identity_v2_live_positive_path_pass_writer_and_final_"
        "identity_reproof_blocked_by_RC_P36_080_and_RC_P36_081",
        "identity_v2_live_positive_path_pass_final_delivery_identity_"
        "exact_live_reproof_pending_after_fresh_proof",
        "identity_v2_preserved_in_fresh_R5_payload_final_delivery_"
        "identity_R5_exact_live_reproof_pending",
        "R5_admission_issuance_authorized_not_issued_final_delivery_"
        "identity_exact_live_reproof_pending",
        "R5_admission_issued_unconsumed_final_delivery_identity_exact_"
        "live_authority_pending",
        "R5_exact_once_execution_authorized_not_started_final_delivery_"
        "identity_live_reproof_pending",
        "R5_terminal_failed_before_final_delivery_identity_L1_no_R6",
    }

    program = _load(PROGRAM_BACKLOG)
    detailed = _load(DETAILED_BACKLOG)
    current_disposition = (
        "S4-T06-MU-CURRENT-CASE-AWARE-DELIVERY-IDENTITY-BOUNDARY-"
        "SCOPE-REPLACEMENT-MINIMUM-ZERO-CALL-IMPLEMENTATION"
    )
    current_fresh_proof = (
        "S4-T06-MU-CURRENT-CASE-AWARE-DELIVERY-IDENTITY-BOUNDARY-"
        "FRESH-AGENT-PROOF-DECISION"
    )
    current_post_R4 = (
        "S4-T06-RUNTIME-AUDIT-EVIDENCE-V2-AND-MATERIAL-NUMERIC-"
        "CLASSIFIER-MINIMUM-ZERO-CALL-IMPLEMENTATION"
    )
    current_after_v2 = (
        "S4-T06-MU-RUNTIME-AUDIT-EVIDENCE-V2-AND-MATERIAL-NUMERIC-"
        "CLASSIFIER-R5-EXACT-LIVE-EXECUTION-AND-SUCCESS-ONLY-PAIRED-ASSESSMENT"
    )
    current_after_R5 = (
        "S4-T06-MU-ACTION-PLANNING-TEMPORAL-AUTHORITY-AND-CAPTURE-V2-"
        "TERMINAL-RESULT-MATERIALIZATION-MINIMUM-ZERO-CALL-IMPLEMENTATION"
    )
    assert program["next_action"]["required_in_scope_substep"] in {
        CURRENT_NEXT,
        current_disposition,
        current_fresh_proof,
        current_post_R4,
        current_after_v2,
        current_after_R5,
    }
    assert program["next_action"]["MU_paired_assessment_performed"] is True
    assert program["next_action"]["MU_paired_assessment_passed"] is False
    assert program["next_action"]["MU_R2"] is False
    assert program["next_action"]["S4_T07_unblocked"] is False
    assert detailed["current_next_action"] in {
        CURRENT_NEXT,
        current_disposition,
        current_fresh_proof,
        current_post_R4,
        current_after_v2,
        current_after_R5,
    }
