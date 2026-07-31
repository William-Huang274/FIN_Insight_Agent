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
PROGRAM = ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
S4_BACKLOG = ROOT / (
    "configs/releases/fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
)
CONTEXT = ROOT / "docs/project_os/current_context_pack.zh-CN.md"
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


def test_current_projection_points_to_implementation_without_product_inflation() -> None:
    decision = _load(DECISION)
    program = _load(PROGRAM)
    s4 = _load(S4_BACKLOG)
    decision_sha = _sha256(DECISION)
    assert program["active_slice"] == "FIN_0_1_2_PRE_S2_REBASELINE"
    assert program["next_action"]["item_id"] == decision["next_action"]
    assert program["next_action"]["FIN_0_1_2_pre_S2_disposition_sha256"] == decision_sha
    assert s4["current_next_action"] == decision["next_action"]
    assert s4["FIN_0_1_2_S1_stage_plan"]["pre_S2_disposition_sha256"] == decision_sha
    assert program["current_truth"]["FIN_0_1_2_S1_closed_honest_block"] is True
    assert program["current_truth"]["FIN_0_1_2_S2_entry_authorized"] is False
    assert program["current_truth"]["FIN_0_1_release_qualified"] is False
    assert set(decision["observed_counts"].values()) == {0}
    context = CONTEXT.read_text(encoding="utf-8")
    assert f"current next=`{decision['next_action']}`" in context


def test_project_OS_records_decision_as_pending_implementation_not_proof() -> None:
    capability = _ledger(CAPABILITY_LEDGER)[-1]
    root_cause = _ledger(ROOT_CAUSE_LEDGER)[-1]
    pattern = _ledger(PATTERN_LEDGER)[-1]
    assert capability["capability_id"] == (
        "fin_0_1_2_s1_to_s2_hermetic_fixture_resource_blocker_disposition"
    )
    assert capability["stage_acceptance"]["PRE_S2_RB_T02"] == "authorized_not_started"
    assert root_cause["issue_id"].startswith("RC-P36-085-")
    assert root_cause["full_chain_blocker"] is True
    assert root_cause["model_or_provider_fault_established"] is False
    assert pattern["pattern_id"] == (
        "content_addressed_runtime_dependency_closure_with_raw_evidence_"
        "and_normalized_semantic_parity"
    )
    assert pattern["status"] == "contract_selected_pre_S2_implementation_pending"
