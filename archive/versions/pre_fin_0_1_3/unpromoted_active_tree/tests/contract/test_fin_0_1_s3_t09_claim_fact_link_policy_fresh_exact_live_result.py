from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_executor import (
    DeepSeekS3ThreeCellNodeExecutor,
    S3ThreeCellBoundedAgentAdmission,
)


RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_s3_t09_claim_fact_link_policy_"
    "fresh_exact_live_execution_result_v1_0.json"
)
ADMISSION = ROOT / (
    "configs/releases/fin_ia_0_1_s3_t09_three_cell_deepseek_"
    "claim_fact_link_policy_exact_admission_r1.json"
)
BACKLOG = ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_exact_live_is_terminal_replayable_and_not_retried() -> None:
    result = _load(RESULT)

    assert result["canonical_terminal_truth"]["work_unit_state"] == "failed"
    assert result["canonical_terminal_truth"]["attempt_state"] == "failed"
    assert result["canonical_terminal_truth"]["research_run_state"] == "failed"
    assert result["canonical_terminal_truth"]["orphaned_run"] is False
    assert result["canonical_terminal_truth"]["artifact_count"] == 0
    assert result["provider_execution"]["model_provider_network_calls"] == [12, 12, 12]
    assert result["provider_execution"]["retry_fallback_rerun_counts"] == [0, 0, 0]
    assert result["provider_execution"][
        "provider_output_capture_and_restricted_readback_counts"
    ] == [12, 12]


def test_claim_fact_link_policy_reaches_and_passes_all_claim_segments() -> None:
    observed = _load(RESULT)["claim_fact_link_live_observation"]

    assert observed["claim_segments_completed"] == 3
    assert observed["fact_supported_alias_selections"] == [["F001"], ["F002"]]
    assert observed["cannot_infer_alias_selections"] == [[], [], []]
    assert observed["provider_support_fact_ids_field_count"] == 0
    assert observed["all_fact_supported_claims_selected_nonempty_closed_aliases"] is True
    assert observed["local_exact_expansion_and_same_cell_validation_passed_before_downstream"] is True
    assert observed["research_lead_writer_verifier_reached"] == [True, True, True]
    assert observed["downstream_capture_alias_token_count"] == 0
    assert observed["RC_P36_048_live_repair_observed"] is True


def test_output_v4_verifier_failure_preserves_historical_schema_drift_truth() -> None:
    root = _load(RESULT)["independent_root_cause_assessment"]
    failure = _load(RESULT)["failure"]

    assert failure["provider_observed_finding_keys"] == [
        "issues",
        "layer",
        "status",
    ]
    assert failure["output_v4_validator_required_finding_keys"] == [
        "artifact_or_claim_refs",
        "issue_codes",
        "layer",
        "repair_owner",
        "status",
    ]
    assert root["project_owned_prompt_validator_schema_drift_confirmed"] is True
    assert root["provider_model_noncompliance_confirmed"] is False


def test_hard_failure_blocks_comparison_T10_and_second_execution() -> None:
    result = _load(RESULT)
    stage = result["stage_decision"]

    assert stage["S3_T09"].startswith("blocked_")
    assert stage["S3_T10"] == "not_entered"
    assert stage["paired_comparison"].startswith("not_performed_")
    assert stage["cross_slice_manifest"].startswith("not_due_")
    assert result["authority"][
        "automatic_retry_fallback_patch_or_second_live_executed"
    ] is False
    assert result["next_action"] == (
        "S3-T09-OUTPUT-V4-VERIFIER-PROMPT-VALIDATOR-SCHEMA-DRIFT-"
        "ZERO-CALL-ROOT-CAUSE-DECISION"
    )


def test_backlog_preserves_historical_result_and_routes_to_latest_blocker() -> None:
    backlog = _load(BACKLOG)

    assert backlog["next_action"]["item_id"]
    assert backlog["next_action"]["claim_fact_link_exact_admission_consumed"] is True
    assert backlog["next_action"]["claim_fact_link_second_execution_authorized"] is False
    assert (
        backlog["next_action"]["output_v4_verifier_schema_repair_artifact_count"]
        == 0
    )
