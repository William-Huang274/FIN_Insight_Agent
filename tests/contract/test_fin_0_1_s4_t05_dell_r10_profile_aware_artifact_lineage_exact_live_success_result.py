from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_r10_profile_aware_"
    "artifact_lineage_exact_live_execution_success_result_v1_0.json"
)
RUNTIME_RESULT = ROOT / (
    ".codex_runtime/fin01-s3-t09-three-cell-deepseek-segmented-"
    "live-validation-r1/s4_t05_dell_r10_profile_aware_artifact_"
    "lineage_r10_r1_live_execution_result.json"
)
ADMISSION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_r10_profile_aware_"
    "artifact_lineage_fresh_exact_admission_r10.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_R10_exact_live_is_consistent_nine_artifact_success() -> None:
    result = _load(RESULT)
    runtime = _load(RUNTIME_RESULT)
    truth = runtime["canonical_terminal_truth"]

    assert result["status"] == (
        "terminal_succeeded_exact_once_nine_artifacts_no_pairing"
    )
    assert tuple(
        truth[key]
        for key in (
            "work_unit_state",
            "attempt_state",
            "research_run_state",
        )
    ) == ("succeeded", "succeeded", "succeeded")
    assert truth["artifact_count"] == 9
    assert truth["orphaned_run"] is False
    assert len(result["artifact_manifest"]) == 9
    assert set(result["artifact_manifest"]) == set(
        truth["artifact_types"]
    )
    assert result["evidence"]["runtime_result_sha256"] == _sha(
        RUNTIME_RESULT
    )
    assert result["admission"]["file_sha256"] == _sha(ADMISSION)


def test_R10_provider_and_lineage_boundaries_are_closed() -> None:
    result = _load(RESULT)
    provider = result["provider_execution"]

    assert provider["model_provider_network_calls"] == [12, 12, 12]
    assert provider["all_call_statuses"] == "ok"
    assert provider["all_finish_reasons"] == "stop"
    assert provider["retry_fallback_replay_relaunch_rerun"] == [
        0, 0, 0, 0, 0
    ]
    assert result["lineage_validation"]["contract_ref"] == (
        "fin01.bounded_agent."
        "profile_aware_artifact_lineage_validation:v1"
    )
    assert result["lineage_validation"]["lineage_family"] == (
        "s4_research_profile_overlay"
    )
    assert result["lineage_validation"][
        "historical_R9_profile_result_validation_failure_recurred"
    ] is False


def test_R10_stops_before_pairing_owner_acceptance_and_T06() -> None:
    result = _load(RESULT)
    acceptance = result["stage_acceptance"]

    assert acceptance["RC_P36_066"] == (
        "closed_exact_live_nine_artifact_success"
    )
    assert acceptance["DELL_R2"].startswith("not_yet_proven")
    assert acceptance["paired_assessment"].startswith("not_performed")
    assert acceptance["owner_acceptance"] == "not_performed"
    assert acceptance["S4_T06"] == "not_entered"
    assert result["verification"]["recoverable_protocol_finding"][
        "terminal"
    ] is False
