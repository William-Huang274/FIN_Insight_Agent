from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESULT = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_dell_exact_r2_execution_failure_result_v1_0.json"
)


def _load() -> dict:
    return json.loads(RESULT.read_text(encoding="utf-8"))


def test_t05_failure_is_terminal_pre_provider_and_not_a_model_failure() -> None:
    result = _load()
    terminal = result["terminal_truth"]
    counts = result["observed_counts"]
    root_cause = result["root_cause"]

    assert result["status"] == (
        "terminal_failed_pre_provider_evidence_role_taxonomy_"
        "runtime_plan_mismatch"
    )
    assert [
        terminal["work_unit_state"],
        terminal["attempt_state"],
        terminal["research_run_state"],
    ] == ["failed", "failed", "failed"]
    assert terminal["artifact_count"] == 0
    assert terminal["orphaned_run"] is False
    assert terminal[
        "automatic_retry_fallback_replay_relaunch_rerun_counts"
    ] == [0, 0, 0, 0, 0]
    assert [
        counts["semantic_model_calls"],
        counts["provider_calls"],
        counts["execution_network_calls"],
        counts["source_network_calls"],
        counts["external_tool_calls"],
    ] == [0, 0, 0, 0, 0]
    assert root_cause["classification"] == (
        "project_owned_runtime_contract_gap_not_model_failure"
    )
    assert root_cause["external_boundary"] is False


def test_t05_failure_reproduction_exposes_the_exact_taxonomy_gap() -> None:
    reproduction = _load()["failure_reproduction"]

    assert reproduction["reproduced_exception_type"] == "EvidenceServiceError"
    assert reproduction["reproduced_failure_code"] == (
        "s3_required_evidence_role_slot_missing"
    )
    assert reproduction["model_or_provider_involved"] is False
    assert reproduction["required_runtime_evidence_roles"] == [
        "demand_signal",
        "revenue_capture",
        "thesis_counterevidence",
    ]
    assert len(reproduction["available_DELL_case_evidence_roles"]) == 14
    assert reproduction["required_role_match_count"] == 0


def test_t05_stops_before_paired_assessment_and_does_not_inflate_R2() -> None:
    result = _load()
    paired = result["paired_assessment"]
    stage = result["stage_decision"]

    assert paired["authorized_only_after_terminal_success"] is True
    assert paired["performed"] is False
    assert stage["S4_T05"] == (
        "honestly_blocked_project_owned_pre_provider_runtime_contract_gap"
    )
    assert stage["DELL_R2"] == "not_proven"
    assert stage["MU_R2"] == "not_started"
    assert stage["NVDA_R3"] == "not_started"
    assert stage["S4_pass"] is False
    assert result["next_action"] == (
        "S4-T05-DELL-EVIDENCE-ROLE-TAXONOMY-TO-RUNTIME-PLAN-"
        "ALIGNMENT-ZERO-CALL-ROOT-CAUSE-DISPOSITION-DECISION"
    )
