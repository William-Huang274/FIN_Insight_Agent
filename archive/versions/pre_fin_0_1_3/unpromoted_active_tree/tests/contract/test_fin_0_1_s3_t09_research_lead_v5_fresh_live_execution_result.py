from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RELEASES = ROOT / "configs" / "releases"
RESULT = RELEASES / (
    "fin_ia_0_1_s3_t09_research_lead_v5_"
    "fresh_live_execution_result_v1_0.json"
)
ADMISSION = RELEASES / (
    "fin_ia_0_1_s3_t09_three_cell_deepseek_owner_grade_"
    "research_lead_v5_exact_admission_r1.json"
)
BACKLOG = RELEASES / "fin_ia_0_1_program_release_backlog_v2_0.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_live_result_consumed_exact_admission_once_and_terminalized() -> None:
    from apps.workbench.backend.application.bounded_agent_executor import (
        S3ThreeCellBoundedAgentAdmission,
    )
    from sec_agent.canonical_runtime.models import canonical_digest

    result = _load(RESULT)
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(_load(ADMISSION))

    assert result["status"] == (
        "terminal_failed_research_lead_v5_per_field_narrative_"
        "length_admission_consumed_no_retry"
    )
    assert canonical_digest(admission.digest_payload()) == result["identity"][
        "admission_digest"
    ]
    terminal = result["canonical_terminal_truth"]
    assert {
        terminal["work_unit_state"],
        terminal["attempt_state"],
        terminal["research_run_state"],
    } == {"failed"}
    assert terminal["orphaned_run"] is False
    assert result["observed_counts"]["admissions_consumed"] == 1
    assert result["observed_counts"]["research_runs_created"] == 1


def test_live_result_records_exact_usage_capture_and_no_retry() -> None:
    result = _load(RESULT)
    provider = result["provider_execution"]
    capture = result["provider_output_capture"]

    assert provider["model_provider_network_calls"] == [10, 10, 10]
    assert provider["input_output_total_tokens"] == [42040, 5860, 47900]
    assert provider["estimated_cost_usd"] == 0.0223365
    assert provider["retry_fallback_rerun_counts"] == [0, 0, 0]
    assert provider["specialist_segments_completed"] == 9
    assert provider["research_lead_called"] is True
    assert provider["memo_writer_called"] is False
    assert provider["verifier_called"] is False
    assert provider["finish_reasons"] == ["stop"] * 10
    assert provider["research_lead_output_tokens_and_cap"] == [1050, 1800]
    assert capture["capture_count"] == 10
    assert capture["restricted_readback_count"] == 10
    assert capture["assistant_output_present_count"] == 10


def test_restricted_audit_locates_exact_per_field_length_failures() -> None:
    result = _load(RESULT)
    audit = result["restricted_research_lead_capture_audit"]
    failure = result["failure_observation"]

    assert failure["stage"] == "research_lead"
    assert failure["failure_family"] == "text"
    assert failure["failure_subtype"] == "item_over_max_unicode_characters"
    assert failure["first_credible_failure_stopped_execution"] is True
    assert audit["json_valid"] is True
    assert audit["assistant_output_characters_and_utf8_bytes"] == [4628, 4628]
    assert audit["aggregate_narrative_characters"] == 3077
    assert audit["over_320_item_count"] == 3
    assert [
        (row["field_path"], row["unicode_characters"], row["over_by"])
        for row in audit["over_320_items"]
    ] == [
        ("cross_cell_dependencies[0].statement", 388, 68),
        ("cross_cell_dependencies[1].statement", 343, 23),
        ("variant_view.statement", 423, 103),
    ]
    assert failure["runtime_telemetry_failing_item_count"] == 1
    assert failure["restricted_audit_failing_item_count"] == 3


def test_live_result_proves_wire_capacity_but_fails_product_acceptance() -> None:
    result = _load(RESULT)
    provider = result["provider_execution"]
    acceptance = result["product_acceptance"]

    assert provider["research_lead_wire_utf8_bytes_and_cap"] == [4628, 8192]
    assert provider[
        "research_lead_aggregate_narrative_characters_and_cap"
    ] == [3077, 3200]
    assert result["canonical_terminal_truth"]["artifact_count"] == 0
    assert acceptance["observed_provider_calls"] == 10
    assert acceptance["observed_artifact_families"] == 0
    assert acceptance["fresh_agent_product_proof"] == "failed"
    assert acceptance["junior_analyst_deliverable"] is False
    assert acceptance["paired_comparison_authorized_or_performed"] is False


def test_live_result_is_durably_traced_without_rerun_authority() -> None:
    result = _load(RESULT)
    next_action = _load(BACKLOG)["next_action"]

    assert result["next_action"] == (
        "S3-T09-OWNER-GRADE-RESEARCH-LEAD-V5-PER-FIELD-"
        "NARRATIVE-LENGTH-FAILURE-ZERO-CALL-ROOT-CAUSE-DECISION"
    )
    assert next_action[
        "S3_T09_research_lead_v5_fresh_live_execution_result_ref"
    ] == RESULT.relative_to(ROOT).as_posix()
    assert next_action["research_lead_v5_fresh_exact_admission_consumed"]
    assert next_action["research_lead_v5_fresh_exact_live_execution_authorized"]
    assert next_action["agent_rerun_authorized"] is False
