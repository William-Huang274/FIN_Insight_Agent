from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESULT = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_dell_research_lead_gap_atom_projection_r5_"
    "exact_live_execution_failure_result_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_r5_terminalized_and_stopped_without_pairing_or_retry() -> None:
    result = _load(RESULT)
    terminal = result["terminal_result"]
    stop = result["stop_contract_observation"]

    assert result["status"] == (
        "terminal_failed_specialist_v7_WWC_segment_truncated_"
        "admission_consumed_no_retry"
    )
    assert [
        terminal["work_unit_state"],
        terminal["attempt_state"],
        terminal["research_run_state"],
    ] == ["failed", "failed", "failed"]
    assert terminal["artifact_count"] == 0
    assert terminal["orphaned_run"] is False
    assert terminal["runner_exit_code"] == 0
    assert stop["paired_assessment_performed"] is False
    assert stop["DELL_R2_proven"] is False
    assert [
        stop["automatic_retry_count"],
        stop["fallback_count"],
        stop["replay_count"],
        stop["relaunch_count"],
        stop["rerun_count"],
    ] == [0, 0, 0, 0, 0]


def test_r5_receipts_and_runtime_results_are_digest_bound() -> None:
    result = _load(RESULT)
    assert _sha256(ROOT / result["authority_decision_ref"]) == (
        result["authority_decision_sha256"]
    )
    assert _sha256(ROOT / result["admission"]["admission_ref"]) == (
        result["admission"]["admission_file_sha256"]
    )
    for key in (
        "preflight",
        "runtime_result",
        "terminal_inspection",
        "launch_receipt",
        "exit_receipt",
    ):
        assert _sha256(ROOT / result["runtime_evidence"][f"{key}_ref"]) == (
            result["runtime_evidence"][f"{key}_sha256"]
        )


def test_first_failure_is_exact_cap_specialist_wwc_truncation() -> None:
    result = _load(RESULT)
    failure = result["first_credible_failure"]
    provider = result["provider_execution"]
    runtime = _load(ROOT / result["runtime_evidence"]["runtime_result_ref"])

    assert failure["failure_code"] == "s3_bounded_node_output_truncated"
    assert failure["segment_id"] == "actionable_what_would_change_tasks"
    assert failure["provider_finish_reason"] == "length"
    assert failure["provider_output_tokens"] == 1400
    assert failure["configured_segment_output_token_cap"] == 1400
    assert runtime["failure_observation"]["failure_codes"] == [
        "s3_bounded_node_output_truncated"
    ]
    assert provider["finish_reason_stop_count"] == 2
    assert provider["finish_reason_length_count"] == 1


def test_r5_projection_was_not_reached_and_rc_p36_061_is_not_closed() -> None:
    result = _load(RESULT)
    live = result["R5_live_observation"]
    classification = result["root_cause_classification"]

    assert live["demand_facts_segment_completed_ok_stop"] is True
    assert live["demand_claim_cards_segment_completed_ok_stop"] is True
    assert live["demand_WWC_segment_completed"] is False
    assert live["research_lead_called"] is False
    assert live["gap_atom_projection_live_observed"] is False
    assert live["RC_P36_061_repaired_path_reached"] is False
    assert classification["research_lead_v6_or_gap_projection_failure"] is False
    assert classification["new_issue_id"] == (
        "RC-P36-062-s4-specialist-v7-WWC-segment-output-truncation-recurrence"
    )
    assert classification["repair_not_authorized"] is True


def test_r5_provider_and_secret_safe_boundary_counts_are_closed() -> None:
    result = _load(RESULT)
    provider = result["provider_execution"]

    assert [
        provider["model_calls"],
        provider["provider_calls"],
        provider["execution_network_calls"],
    ] == [3, 3, 3]
    assert [
        provider["source_network_calls"],
        provider["external_tool_calls"],
    ] == [0, 0]
    assert provider["provider_output_capture_count"] == 3
    assert provider["restricted_readback_count"] == 3
    assert provider["raw_provider_body_in_result"] is False
    assert provider["assistant_output_text_in_result"] is False
    assert provider["private_reasoning_persisted"] is False
    assert provider["credential_value_persisted"] is False
