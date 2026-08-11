from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESULT = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_dell_replacement_exact_r2_"
    "execution_failure_result_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _capture_path(digest: str) -> Path:
    root = (
        ROOT
        / ".codex_runtime/"
        "fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1/"
        "canonical-runtime/objects/fin01/provider-output-captures"
    )
    matches = list(root.rglob(f"{digest}.json"))
    assert len(matches) == 1
    return matches[0]


def test_replacement_run_terminalized_and_stopped_without_pairing() -> None:
    result = _load(RESULT)
    terminal = result["terminal_result"]
    stop = result["stop_contract_observation"]

    assert result["status"] == (
        "terminal_failed_specialist_WWC_unknown_claim_link_"
        "admission_consumed_no_retry"
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


def test_replacement_run_receipts_and_runtime_result_are_digest_bound() -> None:
    result = _load(RESULT)
    assert _sha256(ROOT / result["authority_decision_ref"]) == (
        result["authority_decision_sha256"]
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


def test_live_role_group_repair_passed_before_the_new_failure() -> None:
    result = _load(RESULT)
    provider = result["provider_execution"]
    repair = result["live_repair_observation"]

    assert provider["model_calls"] == 9
    assert provider["provider_calls"] == 9
    assert provider["execution_network_calls"] == 9
    assert provider["provider_output_capture_count"] == 9
    assert provider["restricted_readback_count"] == 9
    assert provider["total_tokens"] == 43849
    assert provider["estimated_cost_usd"] == 0.02050905
    assert repair["RC_P36_058_recurred"] is False
    assert repair["role_group_mapping_live_path_reached"] is True
    assert repair["all_three_specialist_cells_called"] is True
    assert repair["research_lead_called"] is False


def test_restricted_structural_replay_proves_one_unknown_claim_link() -> None:
    result = _load(RESULT)
    evidence = result["runtime_evidence"]
    claim_capture = _load(
        _capture_path(evidence["failed_claim_capture_object_digest"])
    )
    task_capture = _load(
        _capture_path(evidence["failed_WWC_capture_object_digest"])
    )
    claims = json.loads(claim_capture["assistant_output_text"])
    tasks = json.loads(task_capture["assistant_output_text"])

    claim_ids = [
        row["claim_id"] for row in claims["judgment_layer"]
    ]
    task_claim_ids = [
        row["claim_id"] for row in tasks["what_would_change"]
    ]
    unknown = sorted(set(task_claim_ids) - set(claim_ids))

    assert claim_ids == result["first_credible_failure"]["validated_claim_ids"]
    assert task_claim_ids == (
        result["first_credible_failure"]["returned_task_claim_ids"]
    )
    assert unknown == ["C3"]
    assert len(tasks["what_would_change"]) == 3
    assert result["first_credible_failure"]["shape_complete_task_count"] == 3
    assert result["root_cause_classification"][
        "not_safely_downgradable_to_L2_or_L3"
    ] is True
