from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_s3_t09_atomic_terminalization_and_typed_"
    "verifier_state_machine_fresh_exact_live_execution_result_v1_0.json"
)
BACKLOG = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_program_release_backlog_v2_0.json"
)
NEXT_ACTION = (
    "S3-T09-VERIFIER-REPAIR-OWNER-SENTINEL-AND-WINDOWS-SUPERVISOR-"
    "EXIT-RECEIPT-LOSS-ZERO-CALL-ROOT-CAUSE-DISPOSITION"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_live_result_records_exact_once_terminal_failure_and_budget() -> None:
    result = _load(RESULT)
    provider = result["provider_execution"]
    observed = result["observed_counts"]

    assert result["status"] == (
        "terminal_failed_verifier_repair_owner_null_vs_string_sentinel_"
        "and_supervisor_exit_receipt_loss_no_retry_relaunch_or_rerun"
    )
    assert result["identity"]["admission_consumed"] is True
    assert provider["observed_counts"] == {
        "external_tool_calls": 0,
        "model_calls": 12,
        "network_calls": 12,
        "provider_calls": 12,
        "source_network_calls": 0,
    }
    assert provider["usage"] == {
        "input_tokens": 53346,
        "output_tokens": 5527,
        "total_tokens": 58873,
        "estimated_cost_usd": 0.02481146,
        "transport_attempt_count": 12,
    }
    assert provider["all_status_ok"] is True
    assert provider["all_finish_reason_stop"] is True
    assert observed["automatic_retries"] == 0
    assert observed["relaunches"] == 0
    assert observed["reruns"] == 0


def test_verifier_semantics_pass_but_none_representation_is_ambiguous() -> None:
    result = _load(RESULT)
    verifier = result["verifier_safe_structure"]
    root_cause = result["root_cause_classification"]

    assert verifier["statuses"] == ["pass", "pass", "pass", "pass"]
    assert verifier["issue_code_counts"] == [0, 0, 0, 0]
    assert verifier["artifact_or_claim_ref_counts"] == [0, 0, 0, 0]
    assert verifier["repair_owner_types"] == ["NoneType"] * 4
    assert verifier["decision"] == "accept_for_internal_review"
    assert verifier["state_machine_semantics_satisfied"] is True
    assert verifier["required_string_shape_satisfied"] is False
    assert verifier["local_failure_code"] == (
        "s3_bounded_verifier_finding_schema_invalid"
    )
    assert root_cause["provider_state_machine_semantics_followed"] is True
    assert root_cause["model_only_failure"] is False


def test_atomic_capture_failure_terminalization_is_live_proven() -> None:
    result = _load(RESULT)
    canonical = result["canonical_terminal_truth"]
    acceptance = result["acceptance"]

    assert [
        canonical["work_unit_state"],
        canonical["attempt_state"],
        canonical["research_run_state"],
    ] == ["failed", "failed", "failed"]
    assert canonical["orphaned_run"] is False
    assert canonical["artifact_count"] == 0
    assert canonical["terminal_failure_event_capture_ref_count"] == 12
    assert canonical["separate_preterminal_capture_event_present"] is False
    assert canonical[
        "atomic_capture_bearing_failure_transaction_live_proven"
    ] is True
    assert acceptance[
        "RC_P38_050_atomic_failure_terminalization_live_proven"
    ] is True


def test_supervision_receipt_loss_is_separate_non_model_failure() -> None:
    result = _load(RESULT)
    supervision = result["supervision_observation"]
    root_cause = result["root_cause_classification"]

    assert supervision["launch_receipt_present"] is True
    assert supervision["wrapper_pid_alive_when_observed_after_launch"] is False
    assert supervision["runner_alive_after_wrapper_loss_when_observed"] is True
    assert supervision["runner_naturally_exited_without_signal"] is True
    assert supervision["runtime_result_present"] is True
    assert supervision["exit_receipt_present"] is False
    assert supervision["monitor_signals_sent"] == 0
    assert supervision["automatic_retry_count"] == 0
    assert supervision["relaunch_count"] == 0
    assert root_cause["supervision_model_related"] is False
    assert result["acceptance"]["supervision_contract_complete"] is False


def test_backlog_preserves_live_result_after_root_cause_disposition() -> None:
    result = _load(RESULT)
    next_action = _load(BACKLOG)["next_action"]

    assert result["next_action"] == NEXT_ACTION
    assert next_action["item_id"] == (
        "S3-T09-NULLABLE-REPAIR-OWNER-AND-WINDOWS-DIRECT-RUNNER-"
        "SUPERVISION-V2-FRESH-AGENT-PROOF-DECISION"
    )
    assert next_action["fresh_exact_admission_consumed"] is False
    assert next_action["fresh_exact_execution_authorized"] is False
    assert next_action["second_live_execution_authorized"] is False
    assert next_action["root_cause_disposition_authorized"] is True
    assert next_action["repair_implementation_authorized"] is True
    assert next_action["repair_implementation_complete"] is True
    assert next_action["agent_execution_authorized"] is False
    assert next_action["paired_comparison_authorized"] is False
    assert next_action["owner_acceptance_authorized"] is False
