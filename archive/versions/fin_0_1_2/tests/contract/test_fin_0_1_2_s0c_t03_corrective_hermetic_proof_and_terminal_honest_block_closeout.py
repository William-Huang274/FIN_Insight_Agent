from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CLOSEOUT = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_2_s0c_t03_corrective_hermetic_proof_and_"
    "terminal_honest_block_closeout_v1_0.json"
)
EXPECTED_CLOSEOUT_SHA256 = (
    "c790aa649babdf4dcb4201456fcd969b77289e0323e939d056b248522d25655e"
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


def test_S0C_T03_closeout_freezes_the_unique_terminal_package() -> None:
    closeout = _load(CLOSEOUT)
    assert _sha256(CLOSEOUT) == EXPECTED_CLOSEOUT_SHA256
    assert closeout["status"] == (
        "terminal_failed_unique_S0C_T03_package_consumed_no_T04_"
        "S2_entry_false"
    )
    authority = closeout["authority"]
    assert authority["implementation_bundles_consumed"] == 1
    assert authority["corrective_proof_packages_consumed"] == 1
    assert authority["maximum_corrective_proof_packages"] == 1
    assert authority["automatic_second_proof_package"] is False
    assert authority["automatic_T04_or_R_number"] is False
    assert authority["patch_then_rerun_in_this_stage_authorized"] is False

    execution = closeout["frozen_execution"]
    assert execution["disposable_runtime_count"] == 2
    assert execution["collection_errors_each"] == [1, 1]
    assert execution["pytest_exit_code_each"] == [2, 2]
    assert execution["test_counts_each"] == {}
    assert execution["repository_unchanged_during_run"] is True
    assert execution[
        "complete_per_test_stdout_stderr_content_addressed"
    ] is True


def test_package_construction_has_positive_no_recurrence_evidence_without_false_closure() -> None:
    closeout = _load(CLOSEOUT)
    package = closeout["package_construction_result"]
    assert package["tracked_paths"] == 746
    assert package["explicit_allowlist_paths"] == 0
    assert package["git_metadata_paths"] == 0
    assert package["codex_runtime_paths"] == 0
    assert package["RC_P36_090_positive_no_recurrence_evidence"] is True
    assert package["RC_P36_091_positive_no_recurrence_evidence"] is True
    assert package["RC_P36_090_or_091_formally_closed"] is False


def test_collection_failure_identifies_static_resource_and_semantic_path_owners() -> None:
    closeout = _load(CLOSEOUT)
    failure = closeout["first_blocking_failure"]
    assert failure["phase"] == "pytest_collection"
    assert failure["identical_failure_class_in_both_disposables"] is True
    assert failure["host_resource_git_tracked"] is True
    assert failure["packaged_resource_count"] == 0
    assert failure["packaged_consumer_count"] == 1
    assert failure["financial_runtime_tests_executed"] is False
    assert failure["new_financial_runtime_L1_established"] is False
    assert failure["DeepSeek_or_provider_failure"] is False

    semantic = closeout["secondary_semantic_parity_failure"]
    assert semantic["normalization_valid_each"] == [False, False]
    assert semantic["semantic_parity"] is False
    assert semantic["unknown_absolute_path_count_each"] == [1, 1]


def test_terminal_event_blocks_S2_and_model_canary_without_product_inflation() -> None:
    closeout = _load(CLOSEOUT)
    stop = closeout["stop_decision"]
    assert stop["S0C_T03_result"] == "terminal_failed"
    assert stop["S0C_result"] == "closed_terminal_honest_block"
    assert stop["second_T03_package"] is False
    assert stop["S0C_T04"] is False
    assert stop["S2_stage_plan_created"] is False
    assert stop["Flash_stable_canary_calls"] == 0
    assert stop["Pro_preview_canary_calls"] == 0

    assert closeout["observed_counts"]["model_calls"] == 0
    assert closeout["observed_counts"]["provider_calls"] == 0
    assert closeout["observed_counts"]["business_artifacts"] == 0
    assert closeout["product_truth"]["S2_entry"] is False
    assert closeout["product_truth"]["DELL_R2"] is False
    assert closeout["product_truth"]["MU_R2"] is False
    assert closeout["product_truth"]["NVDA_R3"] is False
    assert closeout["product_truth"]["FIN_0_1_release_qualified"] is False
    assert closeout["next_action"] == (
        "FIN-0.1.2-S0C-TERMINAL-HONEST-BLOCK-AND-REPAIR-OWNER-"
        "VERSION-DISPOSITION-DECISION"
    )
