from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest


pytestmark = pytest.mark.fast_contract

ROOT = Path(__file__).resolve().parents[2]
RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_2_s2_t03_mu_flash_stable_vs_pro_preview_"
    "exact_six_call_execution_result_and_project_contract_gap_v1_0.json"
)
PROJECTION = ROOT / (
    "configs/runtime/fin_ia_0_1_2_current_program_projection_v2_13.json"
)
BACKLOG = ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_sanitized_result_records_exact_six_terminal_outcomes() -> None:
    result = _load(RESULT)
    summary = result["execution_summary"]

    assert summary["started_model_calls"] == 6
    assert summary["terminal_model_calls"] == 6
    assert summary["transport_attempts_each"] == 1
    assert summary["retry_fallback_provider_hopping_prompt_only_retry"] == [
        0,
        0,
        0,
        0,
    ]
    assert summary["replacement_pair_calls"] == 0
    assert summary["business_Run_or_Artifact_writes"] == 0
    assert [row["status"] for row in result["outcomes"]].count("pass") == 5
    invalid = [
        row for row in result["outcomes"] if row["status"] != "pass"
    ]
    assert len(invalid) == 1
    assert invalid[0]["candidate_id"] == "flash_stable"
    assert invalid[0]["family_id"] == "what_would_change_atoms"
    assert invalid[0]["code"] == "s4_compiled_wwc_unbound_date_alias_forbidden"
    assert result["first_credible_failure"]["owned_by_project"] is True
    assert result["first_credible_failure"][
        "model_or_provider_fault_established"
    ] is False
    assert result["stage_acceptance"]["S2_T04_blinded_assessment"] == (
        "not_entered"
    )


def test_execution_projection_stays_historical_and_backlog_retains_result() -> None:
    result = _load(RESULT)
    projection = _load(PROJECTION)
    backlog = _load(BACKLOG)
    result_ref = RESULT.relative_to(ROOT).as_posix()
    result_sha = hashlib.sha256(RESULT.read_bytes()).hexdigest()

    assert projection["result_binding"] == {
        "ref": result_ref,
        "sha256": result_sha,
        "binding_role": (
            "S2_T03_exact_six_call_terminal_materialization_and_project_contract_gap"
        ),
    }
    truth = projection["current_truth"]
    assert truth["S2_model_calls"] == 6
    assert truth["S2_terminal_results"] == 6
    assert truth["S2_restricted_captures"] == 6
    assert truth["model_selection"] == "not_permitted_from_current_measurement"
    assert truth["current_next_action"] == result["next_action"]
    authority = projection["execution_authority"]
    assert authority["replacement_pair_authorized"] is False
    assert authority["full_chain_authorized"] is False

    current = backlog["next_action"]
    assert current["item_id"] != result["next_action"]
    assert current["current_projection_ref"].startswith(
        "configs/runtime/fin_ia_0_1_2_current_program_projection_v2_"
    )
    assert current["current_projection_ref"] != PROJECTION.relative_to(
        ROOT
    ).as_posix()
    assert current["S2_T03_execution_result_ref"] == result_ref
    assert current["S2_T03_execution_result_sha256"] == result_sha
    assert current["S2_T03_terminal_capture_counts"] == [6, 6]
    assert current["S2_T03_T04_entered"] is True
    assert current["S2_T03_model_selected"] is False
    assert current["S2_T04_authority_status"].startswith("pass_")
    assert current["S2_T04_independent_assessment_started"] is False


def test_restricted_evidence_is_referenced_but_not_promoted() -> None:
    result = _load(RESULT)
    evidence = result["restricted_execution_evidence"]

    assert evidence["ref"].startswith(".codex_runtime/")
    assert evidence["tracked_or_business_promotable"] is False
    assert evidence["restricted_capture_count"] == 6
    assert evidence["terminal_result_count"] == 6
    assert evidence["raw_provider_response_persisted"] is False
    assert evidence["credential_value_persisted"] is False
