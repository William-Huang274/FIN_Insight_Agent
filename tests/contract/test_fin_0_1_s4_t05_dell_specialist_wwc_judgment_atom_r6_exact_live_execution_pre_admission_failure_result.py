from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
R7_BINDING_IMPLEMENTATION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_r7_profile_v2_versioned_"
    "case_runtime_binding_and_create_app_preflight_minimum_zero_call_"
    "implementation_v1_0.json"
)
RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_specialist_wwc_judgment_"
    "atom_r6_exact_live_execution_pre_admission_failure_result_v1_0.json"
)
PROGRAM_BACKLOG = ROOT / (
    "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
)
DETAILED_BACKLOG = ROOT / (
    "configs/releases/fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
)
ROOT_CAUSE_DISPOSITION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_r6_research_profile_v2_"
    "case_runtime_binding_mismatch_zero_call_root_cause_disposition_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_R6_launch_failed_before_admission_consumption_or_calls() -> None:
    result = _load(RESULT)
    admission = result["admission"]
    terminal = result["terminal_result"]
    provider = result["provider_execution"]
    stop = result["stop_contract_observation"]

    assert result["status"] == (
        "runner_exited_pre_admission_on_S4_research_profile_"
        "binding_mismatch_no_calls_no_retry"
    )
    assert admission["issued"] is True
    assert admission["consumed"] is False
    assert admission["supervised_launch_attempted"] is True
    assert admission["canonical_execution_started"] is False
    assert [
        terminal["work_unit_state"],
        terminal["attempt_state"],
        terminal["research_run_state"],
    ] == [None, None, None]
    assert terminal["runtime_result_materialized"] is False
    assert terminal["runner_exit_code"] == 1
    assert terminal["typed_unhandled_failure_code"] == "unhandled_ValueError"
    assert [
        provider["model_calls"],
        provider["provider_calls"],
        provider["execution_network_calls"],
        provider["source_network_calls"],
        provider["external_tool_calls"],
    ] == [0, 0, 0, 0, 0]
    assert stop["paired_assessment_performed"] is False
    assert stop["DELL_R2_proven"] is False


def test_R6_failure_is_owned_profile_binding_drift_not_model_quality() -> None:
    result = _load(RESULT)
    failure = result["first_credible_failure"]
    coverage = result["preflight_coverage_gap"]
    classification = result["root_cause_classification"]

    assert failure["failure_code"] == (
        "s4_admission_research_profile_binding_mismatch"
    )
    assert failure["case_runtime_binding_research_profile_ref"].endswith(
        ":v1"
    )
    assert failure["exact_admission_research_profile_ref"].endswith(":v2")
    assert failure["model_or_provider_fault"] is False
    assert coverage[
        "Fin01ResearchRuntime_or_create_app_instantiated_during_preflight"
    ] is False
    assert coverage[
        "S4_case_runtime_binding_to_admission_profile_equality_checked_during_preflight"
    ] is False
    assert classification["owned_by_project"] is True
    assert classification["external_boundary"] is False
    assert classification["repair_or_relaunch_authorized"] is False
    assert classification["new_issue_id"] == (
        "RC-P36-063-s4-R6-research-profile-v2-case-runtime-binding-drift"
    )


def test_R6_supervision_and_zero_call_evidence_are_digest_bound() -> None:
    result = _load(RESULT)
    evidence = result["runtime_evidence"]

    assert _sha256(ROOT / result["authority_decision_ref"]) == (
        result["authority_decision_sha256"]
    )
    assert _sha256(ROOT / result["admission"]["admission_ref"]) == (
        result["admission"]["admission_file_sha256"]
    )
    for key in (
        "preflight",
        "post_failure_preflight",
        "runner_command",
        "launch_receipt",
        "exit_receipt",
        "runner_stdout",
        "runner_stderr",
    ):
        assert _sha256(ROOT / evidence[f"{key}_ref"]) == (
            evidence[f"{key}_sha256"]
        )
    assert not (ROOT / evidence["runtime_result_ref"]).exists()
    stderr_text = (ROOT / evidence["runner_stderr_ref"]).read_text(
        encoding="utf-8"
    )
    assert "s4_admission_research_profile_binding_mismatch" in stderr_text
    assert evidence["raw_provider_body_in_evidence"] is False
    assert evidence["credential_value_in_evidence"] is False


def test_R6_post_failure_state_is_unchanged_and_project_advances_after_disposition() -> None:
    result = _load(RESULT)
    post = result["post_failure_zero_call_verification"]
    program = _load(PROGRAM_BACKLOG)
    detailed = _load(DETAILED_BACKLOG)
    detailed_t05 = next(
        row for row in detailed["tasks"] if row["item_id"] == "S4-T05"
    )

    assert post["canonical_total_work_unit_attempt_run_artifact_counts"] == [
        5,
        5,
        5,
        0,
    ]
    assert post["target_work_unit_attempt_run_absent"] is True
    assert post["admission_consumed"] is False
    assert post["model_provider_network_source_tool_calls"] == [0, 0, 0, 0, 0]
    current_next = (
        _load(ROOT / "configs/releases/fin_ia_0_1_s4_t05_dell_r7_profile_v2_binding_exact_live_execution_failure_result_v1_0.json")["next_action"]
        if R7_BINDING_IMPLEMENTATION.exists()
        else _load(ROOT_CAUSE_DISPOSITION)["next_action"]
        if ROOT_CAUSE_DISPOSITION.exists()
        else result["next_action"]
    )
    assert program["next_action"]["item_id"] == current_next
    assert detailed["current_next_action"] == current_next
    assert program["next_action"][
        "current_S4_T05_RC_P36_063_issue_id"
    ] == "RC-P36-063-s4-R6-research-profile-v2-case-runtime-binding-drift"
    assert detailed_t05["RC_P36_063_status"] == (
        "R7_profile_binding_path_reached_not_terminal_failure"
    )
    assert detailed_t05["sixth_execution_completed"] is True
    assert detailed_t05["paired_assessment_performed"] is False
    assert detailed["non_inflation"]["DELL_R2"] is False
