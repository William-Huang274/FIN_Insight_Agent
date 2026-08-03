from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_2_s2_t03_mu_wwc_v12_flash_stable_vs_"
    "pro_preview_replacement_pair_exact_execution_result_v1_0.json"
)
PROJECTION = ROOT / (
    "configs/runtime/fin_ia_0_1_2_current_program_projection_v2_18.json"
)
BACKLOG = ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
CAPABILITY_LEDGER = ROOT / "docs/project_os/capability_status_ledger.jsonl"
ROOT_CAUSE_LEDGER = ROOT / "docs/project_os/root_cause_issue_ledger.jsonl"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _latest_jsonl(path: Path, key: str, value: str) -> dict:
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return [row for row in rows if row.get(key) == value][-1]


def test_exact_pair_result_is_sanitized_complete_and_within_authority() -> None:
    result = _load(RESULT)

    assert result["status"].startswith("completed_two_terminal_results")
    assert result["execution_summary"] == {
        "case": "MU",
        "program_cell_id": "demand_authenticity_and_sustainability",
        "family": "what_would_change_atoms",
        "started_model_calls": 2,
        "terminal_model_calls": 2,
        "hard_integrity_passes": 2,
        "transport_attempts_each": 1,
        "Fact_or_Claim_calls": 0,
        "retry_fallback_provider_hopping_prompt_only_retry": [0, 0, 0, 0],
        "business_Run_or_Artifact_writes": 0,
        "input_tokens": 3690,
        "output_tokens": 779,
        "estimated_cost_usd": 0.00228288,
        "billing_truth": "provider_external",
    }
    assert len(result["outcomes"]) == 2
    assert [row["status"] for row in result["outcomes"]] == ["pass", "pass"]
    assert [row["transport_attempt_count"] for row in result["outcomes"]] == [1, 1]
    assert [row["assembled_unique_claim_ids"] for row in result["outcomes"]] == [2, 2]
    assert result["restricted_execution_evidence"]["raw_provider_response_persisted"] is False
    assert result["restricted_execution_evidence"]["credential_value_persisted"] is False


def test_exact_pair_closes_project_defects_but_does_not_select_model() -> None:
    result = _load(RESULT)

    assert result["fair_measurement_reconstruction"]["effective_hard_integrity_passes"] == 6
    assert result["project_defect_disposition"]["new_project_owned_comparator_failure"] is False
    assert result["project_defect_disposition"]["RC_P36_102"].startswith("closed_")
    assert result["project_defect_disposition"]["RC_P36_103"].startswith("closed_")
    assert result["unscored_product_observations_for_T04"]["formal_blinded_assessment_performed"] is False
    assert result["unscored_product_observations_for_T04"]["model_selected"] is False
    assert result["stage_acceptance"]["S2_T04"].startswith("not_entered")


def test_projection_backlog_and_ledgers_point_to_T04_authority_only() -> None:
    result = _load(RESULT)
    projection = _load(PROJECTION)
    backlog = _load(BACKLOG)
    result_ref = RESULT.relative_to(ROOT).as_posix()
    result_sha = hashlib.sha256(RESULT.read_bytes()).hexdigest()
    projection_ref = PROJECTION.relative_to(ROOT).as_posix()
    projection_sha = hashlib.sha256(PROJECTION.read_bytes()).hexdigest()

    assert projection["implementation_binding"] == {
        "ref": result_ref,
        "sha256": result_sha,
        "binding_role": "S2_T03_fair_WWC_replacement_pair_exact_execution_and_six_outcome_hard_integrity_completion",
    }
    assert projection["current_truth"]["current_next_action"] == result["next_action"]
    assert projection["execution_authority"]["replacement_pair_execution_completed"] is True
    assert projection["execution_authority"]["T04_or_model_selection_executed"] is False
    current = backlog["next_action"]
    assert current["item_id"] == result["next_action"]
    assert current["current_projection_ref"] == projection_ref
    assert current["current_projection_sha256"] == projection_sha
    assert current["S2_T03_replacement_pair_result_ref"] == result_ref
    assert current["S2_T03_replacement_pair_result_sha256"] == result_sha
    assert current["S2_T03_T04_entered"] is False
    assert current["S2_T03_model_selected"] is False

    capability = _latest_jsonl(
        CAPABILITY_LEDGER,
        "capability_id",
        "fin_0_1_2_S2_T03_WWC_v1_2_replacement_pair_exact_execution",
    )
    assert capability["status"].endswith("T04_not_entered")
    assert capability["verification"]["hard_integrity_passes"] == 2

    for issue_id in (
        "RC-P36-102-fin-0-1-2-s2-t03-wwc-review-cadence-date-alias-model-visible-contract-parity-gap",
        "RC-P36-103-fin-0-1-2-s2-t03-wwc-selected-task-claim-binding-loop-state-leak",
    ):
        issue = _latest_jsonl(ROOT_CAUSE_LEDGER, "issue_id", issue_id)
        assert issue["status"] == "closed"
        assert issue["verification"]["replacement_pair_hard_integrity_passes"] == 2
