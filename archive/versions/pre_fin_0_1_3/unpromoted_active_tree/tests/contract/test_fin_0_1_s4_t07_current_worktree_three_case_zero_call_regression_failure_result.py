from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
RESULT_PATH = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t07_current_worktree_three_case_zero_call_"
    "regression_failure_result_v1_0.json"
)
PROGRAM_BACKLOG = (
    ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
)
S4_BACKLOG = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
)


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load(path: Path) -> dict[str, Any]:
    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=_strict_object,
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_result_binds_consumed_scope_and_exact_counts() -> None:
    result = _load(RESULT_PATH)
    authority = result["authority"]
    decision_path = ROOT / authority["scope_decision_ref"]
    assert _sha256(decision_path) == authority["scope_decision_sha256"]
    assert authority["maximum_regression_packages"] == 1
    assert authority["regression_packages_executed"] == 1
    assert authority["automatic_follow_on_packages"] == 0
    assert result["execution"]["collected_tests"] == 97
    assert result["execution"]["passed"] == 93
    assert result["execution"]["failed"] == 4
    assert result["execution"]["exit_code"] == 1


def test_failures_are_typed_without_inflating_runtime_or_product_truth() -> None:
    result = _load(RESULT_PATH)
    assert len(result["failed_tests"]) == 4
    assert {
        row["classification"] for row in result["failed_tests"]
    } == {
        "legacy_S4_T03_fixture_admission_contract_stale",
        "historical_status_snapshot_allowlist_stale",
    }
    assert all(
        row["active_current_runtime_failure_established"] is False
        for row in result["failed_tests"]
    )
    disposition = result["root_cause_disposition"]
    assert disposition["new_financial_business_L1_established"] is False
    assert disposition["shared_runtime_repair_in_T07"] is False
    assert disposition["regression_rerun_in_T07"] is False


def test_t07_is_blocked_and_exact_live_was_not_run() -> None:
    result = _load(RESULT_PATH)
    stage = result["stage_disposition"]
    assert stage["S4_T07"] == (
        "terminal_honestly_blocked_entry_regression_package_failed_"
        "no_exact_live"
    )
    assert stage["NVDA_post_transfer_exact_live"] == "not_authorized_not_run"
    assert stage["NVDA_R3_review_candidate"] == "not_created"
    assert set(result["observed_counts"].values()) == {0}
    assert result["next_action"] == (
        "S4-T08-READ-ONLY-THREE-CASE-CALIBRATION-AND-WORKBENCH-"
        "PRODUCT-VALUE-SCOPE-DECISION"
    )


def test_backlogs_preserve_t07_honest_block_after_current_program_advances() -> None:
    result = _load(RESULT_PATH)
    program = _load(PROGRAM_BACKLOG)
    s4 = _load(S4_BACKLOG)
    s4_items = {
        item["item_id"]: item for item in s4["tasks"]
    }
    program_s4 = next(
        item for item in program["slices"] if item["slice_id"] == "S4"
    )
    program_items = {
        item["item_id"]: item for item in program_s4["items"]
    }
    assert "honestly_blocked" in s4_items["S4-T07"]["status"]
    assert "honestly_blocked" in program_items["S4-T07"]["status"]
    assert "read_only" in s4_items["S4-T08"]["status"]
    assert "read_only" in program_items["S4-T08"]["status"]
    assert program["next_action"]["item_id"] == s4["current_next_action"]
    assert program["next_action"]["item_id"] != result["next_action"]
