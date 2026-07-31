from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CLOSEOUT = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_2_pre_s2_t03_replacement_hermetic_proof_"
    "and_honest_block_closeout_v1_0.json"
)
PROGRAM_BACKLOG = ROOT / (
    "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
)
S4_BACKLOG = ROOT / (
    "configs/releases/fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
)
CONTEXT = ROOT / "docs/project_os/current_context_pack.zh-CN.md"
EXPECTED_CLOSEOUT_SHA256 = (
    "244442ddc01110cf6fbdb4c5d3580c26b418955cd8da2ed92f94fb4eccafc7ae"
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


def test_T03_closeout_preserves_unique_failed_package_and_stop_rule() -> None:
    closeout = _load(CLOSEOUT)
    assert _sha256(CLOSEOUT) == EXPECTED_CLOSEOUT_SHA256
    assert closeout["status"] == (
        "terminal_failed_unique_T03_package_consumed_pre_S2_"
        "honest_block_S2_entry_false"
    )
    authority = closeout["authority"]
    assert authority["implementation_bundles_consumed"] == 1
    assert authority["replacement_proof_packages_consumed"] == 1
    assert authority["maximum_replacement_proof_packages"] == 1
    assert authority["automatic_second_proof_package"] is False
    assert authority["patch_then_rerun_in_this_stage_authorized"] is False

    execution = closeout["frozen_execution"]
    assert execution["disposable_runtime_count"] == 2
    assert execution["test_counts_each"] == {
        "passed": 56,
        "failed": 1,
        "collection_errors": 0,
    }
    assert execution["pytest_exit_code_each"] == [1, 1]
    assert execution["repository_unchanged_during_run"] is True
    assert execution[
        "complete_per_test_stdout_stderr_content_addressed"
    ] is True
    assert execution["process_stdout_stderr_content_addressed"] is True


def test_T03_closeout_separates_positive_owner_proof_from_blocking_harness_failure() -> None:
    closeout = _load(CLOSEOUT)
    owners = closeout["T02_owner_results"]
    assert owners["tracked_MU_fixture"]["packaged_exactly_once"] is True
    assert owners["tracked_MU_fixture"][
        "active_three_case_proof_read_host_local_MU_object"
    ] is False
    resources = owners["runtime_nonpython_resources"]
    assert resources["registered_resource_count"] == 16
    assert resources["inventory_registry_and_resource_paths_packaged"] == 18
    assert resources["missing_paths"] == 0
    assert resources["digest_mismatches"] == 0
    assert owners["semantic_parity"]["semantic_parity"] is True
    assert owners["semantic_parity"]["raw_parity"] is False
    assert owners["current_runtime"][
        "three_case_full_fake_and_final_artifact_mutations_passed"
    ] is True

    failure = closeout["first_blocking_failure"]
    assert failure["failure_code"] == "hermetic_git_inventory_failed"
    assert failure["identical_gating_nodeid_in_both_disposables"] is True
    assert failure["missing_MU_fixture"] is False
    assert failure["missing_registered_runtime_resource"] is False
    assert failure["semantic_parity_failure"] is False
    assert failure["financial_runtime_failure"] is False
    assert failure["DeepSeek_or_provider_failure"] is False


def test_T03_closeout_quarantines_ignored_runtime_package_overreach() -> None:
    closeout = _load(CLOSEOUT)
    finding = closeout["independent_package_boundary_finding"]
    assert finding["ignored_host_runtime_files_packaged"] == 164
    assert finding["ignored_host_runtime_bytes_packaged"] == 6427052
    assert finding["source_paths_git_tracked"] == 0
    assert finding["source_paths_git_ignored"] is True
    assert finding["participated_in_active_three_case_runtime_proof"] is False
    assert finding["caused_first_blocking_test_failure"] is False
    assert finding["package_access"] == (
        "restricted_quarantine_do_not_share_or_promote"
    )
    assert finding["credential_content_absence_independently_proven"] is False
    assert finding["package_deletion_authorized_or_performed"] is False


def test_current_projection_closes_pre_S2_without_product_inflation() -> None:
    closeout = _load(CLOSEOUT)
    program = _load(PROGRAM_BACKLOG)
    s4 = _load(S4_BACKLOG)
    next_action = closeout["next_action"]

    assert program["next_action"]["item_id"] == next_action
    assert program["next_action"][
        "FIN_0_1_2_pre_S2_T03_closeout_sha256"
    ] == EXPECTED_CLOSEOUT_SHA256
    assert program["next_action"][
        "FIN_0_1_2_pre_S2_observed_implementation_and_proof_packages"
    ] == [1, 1]
    assert program["next_action"]["FIN_0_1_2_S2_entry_authorized"] is False
    assert s4["current_next_action"] == next_action
    assert s4["FIN_0_1_2_S1_stage_plan"][
        "pre_S2_observed_implementation_and_proof_packages"
    ] == [1, 1]
    assert s4["FIN_0_1_2_S1_stage_plan"]["S2_entry_authorized"] is False

    assert closeout["observed_counts"] == {
        "implementation_bundles_consumed": 1,
        "replacement_proof_packages_consumed": 1,
        "credential_reads_or_probes": 0,
        "model_calls": 0,
        "provider_calls": 0,
        "business_network_source_or_external_tool_calls": 0,
        "new_admissions": 0,
        "business_runs": 0,
        "business_artifacts": 0,
        "paid_reproofs": 0,
    }
    assert closeout["product_truth"]["S2_entry"] is False
    assert closeout["product_truth"]["DELL_R2"] is False
    assert closeout["product_truth"]["MU_R2"] is False
    assert closeout["product_truth"]["NVDA_R3"] is False
    assert closeout["product_truth"]["FIN_0_1_release_qualified"] is False
    assert f"current next=`{next_action}`" in CONTEXT.read_text(encoding="utf-8")
