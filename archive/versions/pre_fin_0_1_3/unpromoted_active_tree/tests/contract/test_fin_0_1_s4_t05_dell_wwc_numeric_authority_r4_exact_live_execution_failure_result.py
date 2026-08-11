from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESULT = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_dell_wwc_numeric_authority_r4_"
    "exact_live_execution_failure_result_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_r4_terminalized_and_stopped_without_pairing_or_retry() -> None:
    result = _load(RESULT)
    terminal = result["terminal_result"]
    stop = result["stop_contract_observation"]

    assert result["status"] == (
        "terminal_failed_research_lead_remaining_gaps_cardinality_"
        "nonconformance_admission_consumed_no_retry"
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


def test_r4_receipts_and_runtime_results_are_digest_bound() -> None:
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


def test_r4_crossed_all_specialists_and_did_not_recur_rc_p36_060() -> None:
    result = _load(RESULT)
    live = result["repaired_policy_live_observation"]

    assert live["RC_P36_060_recurred"] is False
    assert live["specialist_cells_completed"] == 3
    assert live["specialist_segments_completed"] == 9
    assert live["specialist_responses_ok_stop"] == 9
    assert live["all_three_WWC_segments_passed_local_validation"] is True
    assert live["research_lead_called"] is True
    assert live["memo_writer_called"] is False
    assert live["verifier_called"] is False


def test_first_failure_is_request_aligned_direct_output_nonconformance() -> None:
    result = _load(RESULT)
    failure = result["first_credible_failure"]
    classification = result["root_cause_classification"]
    runtime = _load(ROOT / result["runtime_evidence"]["runtime_result_ref"])
    telemetry = runtime["failure_observation"]["failure_telemetry"][
        "research_lead_contract"
    ]

    assert failure["failure_code"] == (
        "s3_bounded_research_lead_v3_cardinality_above_maximum"
    )
    assert failure["field_id"] == "remaining_gaps"
    assert failure["contract_maximum"] == 4
    assert failure["excess_item_count"] == 4
    assert failure["inferred_observed_item_count"] == 8
    assert failure["request_visible_cardinality"] == "1..4"
    assert telemetry["validator_contract"] == "closed_research_lead_output:v3"
    assert telemetry["failure_family"] == "cardinality"
    assert telemetry["failure_subtype"] == "above_maximum"
    assert telemetry["field_id"] == "remaining_gaps"
    assert telemetry["failing_item_count"] == 4
    assert telemetry["raw_text_persisted"] is False
    assert classification["request_validator_schema_drift"] is False
    assert classification["direct_model_output_contract_nonconformance"] is True


def test_r4_provider_and_boundary_counts_are_closed() -> None:
    result = _load(RESULT)
    provider = result["provider_execution"]

    assert [
        provider["model_calls"],
        provider["provider_calls"],
        provider["execution_network_calls"],
    ] == [10, 10, 10]
    assert [
        provider["source_network_calls"],
        provider["external_tool_calls"],
    ] == [0, 0]
    assert provider["finish_reason_stop_count"] == 10
    assert provider["provider_output_capture_count"] == 10
    assert provider["restricted_readback_count"] == 10
    assert provider["raw_provider_body_in_result"] is False
    assert provider["assistant_output_text_in_result"] is False
    assert provider["private_reasoning_persisted"] is False
    assert provider["credential_value_persisted"] is False
