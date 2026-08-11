from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_r9_specialist_validated_"
    "segment_union_capacity_exact_live_execution_failure_result_v1_0.json"
)
PROGRAM_BACKLOG = ROOT / (
    "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
)
DETAILED_BACKLOG = ROOT / (
    "configs/releases/fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
)
DISPOSITION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_r9_profile_result_"
    "validation_after_six_node_completion_zero_call_root_cause_"
    "disposition_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_R9_exact_live_result_binds_authority_admission_and_runtime() -> None:
    result = _load(RESULT)

    for group, ref_key, sha_key in (
        ("authority", "decision_ref", "decision_sha256"),
        ("admission", "ref", "file_sha256"),
        ("admission", "issuance_ref", "issuance_sha256"),
        ("supervision", "launch_receipt_ref", "launch_receipt_sha256"),
        ("supervision", "exit_receipt_ref", "exit_receipt_sha256"),
        ("runtime_evidence", "result_ref", "result_sha256"),
        (
            "runtime_evidence",
            "terminal_inspection_ref",
            "terminal_inspection_sha256",
        ),
    ):
        assert _sha256(ROOT / result[group][ref_key]) == result[group][sha_key]
    assert result["admission"]["issued"] is True
    assert result["admission"]["consumed"] is True
    assert result["admission"]["execution_completed"] is True


def test_R9_exact_live_terminal_truth_is_coherent_failed_zero_artifact() -> None:
    result = _load(RESULT)
    terminal = result["canonical_terminal_truth"]
    runtime = _load(ROOT / result["runtime_evidence"]["result_ref"])
    inspection = _load(
        ROOT / result["runtime_evidence"]["terminal_inspection_ref"]
    )

    assert (
        terminal["work_unit_state"],
        terminal["attempt_state"],
        terminal["research_run_state"],
    ) == ("failed", "failed", "failed")
    assert terminal["terminal_consistent"] is True
    assert terminal["orphaned_run"] is False
    assert terminal["artifact_count"] == 0
    assert runtime["status"] == "terminal_failed_admission_consumed_no_retry"
    assert runtime["canonical_terminal_truth"]["artifact_count"] == 0
    assert inspection["status"] == "inspected_no_provider_call"
    assert inspection["additional_model_provider_network_calls"] == [0, 0, 0]


def test_R9_exact_live_reached_all_nodes_and_preserved_typed_evidence() -> None:
    result = _load(RESULT)
    provider = result["provider_execution"]
    completed = result["completed_node_evidence"]
    failure = result["first_credible_failure"]
    envelope = result["typed_failure_envelope_result"]

    assert (
        provider["model_calls"],
        provider["provider_calls"],
        provider["network_calls"],
    ) == (12, 12, 12)
    assert provider["all_completed_status"] == "ok"
    assert provider["all_completed_finish_reason"] == "stop"
    assert provider["transport_attempt_count"] == 12
    assert provider["usage_receipt_count"] == 12
    assert provider["restricted_capture_count"] == 12
    assert provider["restricted_capture_readback_count"] == 12
    assert provider["retry_count"] == 0
    assert provider["fallback_count"] == 0
    assert provider["replay_count"] == 0
    assert provider["relaunch_count"] == 0
    assert provider["rerun_count"] == 0
    assert completed["completed_logical_node_receipt_count"] == 6
    assert completed[
        "all_three_specialist_nodes_completed_under_profile_v3_capacity"
    ] is True
    assert completed["research_lead_v6_completed"] is True
    assert completed["memo_writer_v3_completed"] is True
    assert completed["verifier_provider_call_completed_ok_stop"] is True
    assert failure["stage"] == "profile_result_validation"
    assert failure["failure_code"] == (
        "s3_bounded_profile_result_validation_failed"
    )
    assert failure["specific_profile_subtype_persisted"] is False
    assert failure["model_instruction_noncompliance_established"] is False
    assert envelope["usage_receipts_preserved"] == 12
    assert envelope["restricted_captures_preserved"] == 12
    assert envelope["completed_logical_node_receipts_preserved"] == 6


def test_R9_failure_blocks_pairing_and_routes_to_zero_call_disposition() -> None:
    result = _load(RESULT)
    program = _load(PROGRAM_BACKLOG)
    detailed = _load(DETAILED_BACKLOG)
    task = next(
        item for item in detailed["tasks"] if item["item_id"] == "S4-T05"
    )

    assert result["authority"]["paired_assessment_performed"] is False
    assert result["stage_acceptance"]["DELL_R2"] == "not_proven"
    assert result["stage_acceptance"]["S4_T06"] == "not_entered"
    assert result["root_cause_progress"]["RC_P36_065"].startswith(
        "closed_live_path_positive"
    )
    assert result["root_cause_progress"]["RC_P36_066"] == (
        "open_zero_call_root_cause_disposition_pending"
    )
    if DISPOSITION.exists():
        next_action = _load(DISPOSITION)["next_action"]
        assert program["next_action"]["item_id"] == next_action
        assert detailed["current_next_action"] == next_action
    else:
        assert program["next_action"]["item_id"] == result["next_action"]
        assert detailed["current_next_action"] == result["next_action"]
    assert task["R9_admission_consumed"] is True
    assert task["R9_execution_completed"] is True
    assert task["R9_artifact_count"] == 0
    assert task["R9_paired_assessment_performed"] is False
