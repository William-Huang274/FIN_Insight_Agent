from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESULT = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s3_t09_owner_grade_specialist_v7_fresh_live_execution_result_v1_0.json"
)
BACKLOG = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_program_release_backlog_v2_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_v7_live_result_preserves_gateway_truth_and_terminal_truth() -> None:
    result = _load(RESULT)

    assert result["canonical_terminal_truth"]["work_unit_state"] == "failed"
    assert result["canonical_terminal_truth"]["attempt_state"] == "failed"
    assert result["canonical_terminal_truth"]["research_run_state"] == "failed"
    assert result["canonical_terminal_truth"]["artifact_count"] == 0
    assert result["canonical_terminal_truth"]["orphaned_run"] is False

    gateway = result["provider_execution_gateway_truth"]
    assert [gateway["model_calls"], gateway["provider_calls"], gateway["network_calls"]] == [
        3,
        3,
        3,
    ]
    assert gateway["total_tokens"] == 12201
    assert gateway["retry_count"] == 0
    assert gateway["fallback_count"] == 0
    assert gateway["rerun_count"] == 0


def test_v7_live_result_does_not_hide_capture_loss_or_blame_provider() -> None:
    result = _load(RESULT)
    discrepancy = result["telemetry_discrepancy"]
    failure = result["earliest_project_owned_failure"]

    assert discrepancy["runtime_result_reported_model_provider_network_calls"] == [0, 0, 0]
    assert discrepancy["gateway_event_model_provider_network_calls"] == [3, 3, 3]
    assert discrepancy["provider_output_capture_count"] == 0
    assert discrepancy["assistant_final_output_text_replayable"] is False
    assert failure["inner_profile_max_serialized_utf8_bytes"] == 8192
    assert failure["outer_effective_max_serialized_utf8_bytes"] == 6000
    assert failure["assembled_first_cell_serialized_utf8_bytes_proven_range"] == [6001, 8192]
    assert failure["provider_fault_confirmed"] is False


def test_v7_result_and_backlog_freeze_zero_call_next_action() -> None:
    result = _load(RESULT)
    backlog = _load(BACKLOG)["next_action"]
    expected = (
        "S3-T09-OWNER-GRADE-SPECIALIST-V7-OUTER-ASSEMBLY-CAPABILITY-"
        "AND-CAPTURE-ZERO-CALL-ROOT-CAUSE-DECISION"
    )

    assert result["next_action"] == expected
    assert backlog["item_id"] == expected
    assert backlog["specialist_v7_exact_admission_consumed"] is True
    assert backlog["specialist_v7_live_execution_authorized"] is True
    assert backlog["specialist_v7_fresh_artifact_count"] == 0
    assert backlog["agent_rerun_authorized"] is False
