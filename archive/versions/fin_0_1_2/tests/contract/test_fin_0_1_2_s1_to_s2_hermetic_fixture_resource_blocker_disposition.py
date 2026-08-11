from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DECISION = ROOT / (
    "configs/releases/fin_ia_0_1_2_s1_to_s2_hermetic_fixture_"
    "resource_blocker_disposition_v1_0.json"
)
IMPLEMENTATION = ROOT / (
    "configs/releases/fin_ia_0_1_2_pre_s2_hermetic_fixture_resource_"
    "rebaseline_minimum_zero_call_implementation_v1_0.json"
)
CAPABILITY_LEDGER = ROOT / "docs/project_os/capability_status_ledger.jsonl"
ROOT_CAUSE_LEDGER = ROOT / "docs/project_os/root_cause_issue_ledger.jsonl"
PATTERN_LEDGER = ROOT / "docs/project_os/external_pattern_registry.jsonl"


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


def _ledger(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line, object_pairs_hook=_strict_object)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_disposition_is_duplicate_safe_and_binds_terminal_S1_evidence() -> None:
    decision = _load(DECISION)
    assert decision["status"] == (
        "pass_pre_S2_rebaseline_selected_implementation_pending_"
        "S2_entry_blocked"
    )
    for binding in decision["immutable_parent_evidence"]:
        if binding["ref"].startswith("configs/"):
            path = ROOT / binding["ref"]
            assert path.is_file()
            assert _sha256(path) == binding["sha256"]
        else:
            assert binding["ref"].startswith("D:/FIN_Insight_Agent_recovery/")
            assert len(binding["sha256"]) == 64


def test_disposition_selects_one_bounded_pre_S2_stage_without_reopening_S1() -> None:
    decision = _load(DECISION)
    selected = [row["option"] for row in decision["decision_options"] if row["selected"]]
    assert selected == ["A"]
    assert decision["selected_stage"] == {
        "stage_id": "FIN-0.1.2-PRE-S2-HERMETIC-FIXTURE-RESOURCE-REBASELINE-R1",
        "stage_kind": "bounded_zero_call_dependency_closure_and_replacement_proof",
        "is_S1_continuation": False,
        "is_S1_T05_or_R_number": False,
        "is_S2": False,
        "mission": decision["selected_stage"]["mission"],
    }
    tasks = decision["fixed_task_and_package_budget"]
    assert [row["task_id"] for row in tasks] == [
        "PRE-S2-RB-T01",
        "PRE-S2-RB-T02",
        "PRE-S2-RB-T03",
    ]
    assert tasks[0]["status"] == "pass_current_decision"
    assert tasks[1]["maximum_implementation_bundles"] == 1
    assert tasks[2]["maximum_hermetic_proof_packages"] == 1
    assert decision["pass_and_stop_rules"]["automatic_second_implementation_bundle"] is False
    assert decision["pass_and_stop_rules"]["automatic_second_replacement_proof_package"] is False
    assert decision["authority"]["S1_reopen_or_S1_T05_authorized"] is False
    assert decision["authority"]["S2_entry_authorized"] is False


def test_disposition_assigns_all_three_earliest_repository_owners() -> None:
    owners = _load(DECISION)["earliest_owner_audit"]
    assert set(owners) == {
        "MU_realistic_fixture",
        "runtime_nonpython_resources",
        "semantic_parity_projection",
    }

    fixture = owners["MU_realistic_fixture"]
    assert fixture["source_object_sha256"] == (
        "290e82aec53d6d3078eb0c8bac94e022bde7cc17a77b72d2315af118ced4958e"
    )
    assert fixture["source_object_bytes"] == 196647
    assert fixture["input_digest"] == (
        "7887b5bb447fc6a844c410751f2038a04a1c0b04dbbe7e5bde41b040135a12e1"
    )
    assert fixture["future_owner"] == (
        "tests/fixtures/fin_0_1_2/mu_realistic_three_cell_exact_input_v1.json"
    )
    assert fixture["active_proof_import_of_historical_S4_fixture_helper_after_migration"] is False

    resources = owners["runtime_nonpython_resources"]
    assert resources["inventory_source_of_truth"] == "research_skills.SKILL_FILES"
    assert resources["observed_registered_resource_count"] == 16
    assert resources["observed_registered_resource_bytes"] == 53382
    assert resources["observed_registered_resource_canonical_digest"] == (
        "2b704b4c20dafad05097f59bb35740fc2f8a0479a2f55b6bb7d1a1bae15d1e9a"
    )

    parity = owners["semantic_parity_projection"]
    assert parity["raw_capture_retention_required"] is True
    assert parity["raw_detail_stdout_stderr_hashes_rewritten"] is False
    assert parity["normalization_allowlist"] == [
        "exact_disposable_repository_root",
        "exact_disposable_package_root",
        "exact_hermetic_temporary_parent",
    ]
    assert parity["normalization_of_business_values_nodeids_failure_codes_or_relative_paths"] is False
    assert parity["unknown_absolute_path_behavior"] == "fail_closed_and_keep_parity_false"


def test_historical_disposition_points_to_replacement_proof_without_inflation() -> None:
    decision = _load(DECISION)
    implementation = _load(IMPLEMENTATION)
    assert decision["next_action"] == (
        "FIN-0.1.2-PRE-S2-HERMETIC-FIXTURE-RESOURCE-REBASELINE-"
        "MINIMUM-ZERO-CALL-IMPLEMENTATION"
    )
    assert implementation["next_action"] == (
        "FIN-0.1.2-PRE-S2-RB-T03-INDEPENDENT-TWO-DISPOSABLE-"
        "REPLACEMENT-HERMETIC-PROOF"
    )
    assert set(decision["observed_counts"].values()) == {0}
    assert implementation["authority"]["implementation_bundles_consumed"] == 1
    assert implementation["authority"]["replacement_proof_packages_consumed"] == 0
    assert decision["product_truth"]["S2_entry"] is False
    assert implementation["product_truth"]["S2_entry"] is False


def test_project_OS_records_T02_pass_and_T03_pending_proof() -> None:
    capability = next(
        row
        for row in _ledger(CAPABILITY_LEDGER)
        if row["capability_id"]
        == "fin_0_1_2_pre_s2_hermetic_fixture_resource_rebaseline_T02"
    )
    assert capability["stage_acceptance"]["PRE_S2_RB_T02"] == "pass"
    assert capability["stage_acceptance"]["PRE_S2_RB_T03"] == "ready_not_started"
    root_cause = next(
        row
        for row in _ledger(ROOT_CAUSE_LEDGER)
        if row["issue_id"].startswith("RC-P36-085-")
        and row["status"]
        == "pre_S2_T02_fixture_resource_semantic_parity_implementation_"
        "pass_T03_replacement_proof_pending"
    )
    assert root_cause["issue_id"].startswith("RC-P36-085-")
    assert root_cause["full_chain_blocker"] is True
    assert root_cause["model_or_provider_fault_established"] is False
    pattern = next(
        row
        for row in _ledger(PATTERN_LEDGER)
        if row["pattern_id"]
        == "content_addressed_runtime_dependency_closure_with_raw_evidence_"
        "and_normalized_semantic_parity"
        and row["status"]
        == "runtime_implemented_fixture_and_host_matrix_proven_"
        "independent_hermetic_proof_pending"
    )
    assert pattern["status"] == (
        "runtime_implemented_fixture_and_host_matrix_proven_"
        "independent_hermetic_proof_pending"
    )
