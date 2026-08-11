from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DECISION = ROOT / (
    "configs/releases/fin_ia_0_1_2_s0c_hermetic_test_topology_and_"
    "allowlisted_package_closure_scope_decision_v1_0.json"
)
CAPABILITY_LEDGER = ROOT / "docs/project_os/capability_status_ledger.jsonl"
ROOT_CAUSE_LEDGER = ROOT / "docs/project_os/root_cause_issue_ledger.jsonl"
PATTERN_LEDGER = ROOT / "docs/project_os/external_pattern_registry.jsonl"

NEXT = (
    "FIN-0.1.2-S0C-T02-HERMETIC-TEST-TOPOLOGY-AND-ALLOWLISTED-"
    "PACKAGE-CLOSURE-MINIMUM-ZERO-CALL-IMPLEMENTATION"
)
STAGE = (
    "FIN-0.1.2-S0C-HERMETIC-TEST-TOPOLOGY-AND-ALLOWLISTED-"
    "PACKAGE-CLOSURE-R1"
)
ISSUES = {
    "RC-P36-090-fin-0-1-2-pre-s2-t03-disposable-self-introspection-"
    "git-inventory-dependency",
    "RC-P36-091-fin-0-1-2-hermetic-package-recursive-json-ref-admits-"
    "ignored-runtime-state",
}


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_strict_object)


def _ledger(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line, object_pairs_hook=_strict_object)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_decision_binds_immutable_terminal_evidence_without_rewriting_it() -> None:
    decision = _load(DECISION)
    assert decision["status"] == (
        "pass_bounded_S0_corrective_stage_selected_T02_implementation_"
        "pending_S2_entry_blocked"
    )
    for binding in decision["immutable_parent_evidence"]:
        if binding["ref"].startswith("configs/"):
            source = ROOT / binding["ref"]
            assert source.is_file()
            assert _sha256(source) == binding["sha256"]
        else:
            assert binding["ref"].startswith("D:/FIN_Insight_Agent_recovery/")
            assert len(binding["sha256"]) == 64

    assert decision["product_truth"]["historical_S0"] == "closed_pass_not_rewritten"
    assert decision["product_truth"]["S1"] == "closed_honest_block_not_reopened"
    assert decision["product_truth"]["PRE_S2_RB_T03"] == (
        "terminal_failed_unique_package_consumed"
    )


def test_exactly_one_bounded_S0C_stage_and_budget_are_selected() -> None:
    decision = _load(DECISION)
    assert [row["option"] for row in decision["decision_options"] if row["selected"]] == ["A"]
    assert decision["selected_stage"]["stage_id"] == STAGE
    assert decision["selected_stage"]["owner_phase"] == (
        "FIN_0_1_2_S0_test_and_packaging_contract"
    )
    assert decision["selected_stage"]["is_historical_S0_rewrite"] is False
    assert decision["selected_stage"]["is_S1_continuation_or_S1_T05"] is False
    assert decision["selected_stage"]["is_second_PRE_S2_RB_T03"] is False
    assert decision["selected_stage"]["is_S2"] is False

    tasks = decision["fixed_task_and_package_budget"]
    assert [row["task_id"] for row in tasks] == ["S0C-T01", "S0C-T02", "S0C-T03"]
    assert tasks[0]["status"] == "pass_current_decision"
    assert tasks[1]["maximum_implementation_bundles"] == 1
    assert tasks[2]["maximum_corrective_proof_packages"] == 1
    stop = decision["pass_and_stop_rules"]
    assert stop["automatic_second_T02_implementation_bundle"] is False
    assert stop["automatic_second_T03_corrective_proof_package"] is False
    assert stop["automatic_S0C_T04_R_number_or_patch_then_rerun"] is False


def test_structural_owners_cover_topology_closure_projection_and_raw_evidence() -> None:
    decision = _load(DECISION)
    assert {row["issue_id"] for row in decision["observed_blockers"]} == ISSUES
    owners = decision["earliest_owner_audit"]
    assert set(owners) == {
        "host_vs_disposable_test_topology",
        "allowlisted_recursive_reference_closure",
        "immutable_event_vs_current_projection_topology",
        "raw_evidence_and_restricted_package_governance",
    }
    assert owners["host_vs_disposable_test_topology"]["disposable_git_command_requirement"] == 0
    assert owners["allowlisted_recursive_reference_closure"][
        "ignored_or_untracked_repository_reference_behavior"
    ] == "fail_closed_before_object_storage_or_disposable_execution"
    assert owners["immutable_event_vs_current_projection_topology"][
        "historical_evidence_or_assertion_relaxation"
    ] is False
    assert owners["raw_evidence_and_restricted_package_governance"][
        "raw_content_addressed_capture_rewrite_allowed"
    ] is False
    proof = decision["T03_proof_contract"]
    assert proof["historical_PRE_S2_RB_T03_patch_rerun_or_second_package"] is False
    assert proof["disposable_git_subprocess_calls_allowed"] == 0
    assert proof["ignored_or_untracked_runtime_paths_packaged_maximum"] == 0


def test_decision_event_points_only_to_S0C_T02_without_product_inflation() -> None:
    decision = _load(DECISION)
    assert decision["next_action"] == NEXT
    assert set(decision["observed_counts"].values()) == {0}
    assert decision["product_truth"]["S0C_T02"] == "ready_not_started"
    assert decision["product_truth"]["S0C_T03"] == "locked"
    assert decision["product_truth"]["S2_entry"] is False
    assert decision["product_truth"]["FIN_0_1_release_qualified"] is False


def test_project_OS_event_records_keep_both_blockers_open_and_scope_T02() -> None:
    capability = next(
        row
        for row in _ledger(CAPABILITY_LEDGER)
        if row["capability_id"]
        == "fin_0_1_2_S0C_test_packaging_contract_reopen_scope_decision"
    )
    roots = _ledger(ROOT_CAUSE_LEDGER)
    assert capability["stage_acceptance"]["S0C_T01"] == "pass"
    assert capability["stage_acceptance"]["S0C_T02"] == "ready_not_started"
    assert capability["current_next"] == NEXT

    for issue_id in ISSUES:
        issue = next(
            row
            for row in roots
            if row["issue_id"] == issue_id
            and NEXT in row.get("allowed_run_scopes", [])
        )
        assert issue["status"] == "open"
        assert issue["full_chain_blocker"] is True
        assert NEXT in issue["allowed_run_scopes"]
        assert issue["model_or_provider_fault_established"] is False

    pattern = next(
        row
        for row in _ledger(PATTERN_LEDGER)
        if row["pattern_id"]
        == "host_package_construction_must_not_self_execute_in_disposable_"
        "and_reference_closure_must_remain_allowlisted"
        and row["status"]
        == "bounded_S0C_selected_T02_zero_call_implementation_pending"
    )
    assert pattern["status"] == (
        "bounded_S0C_selected_T02_zero_call_implementation_pending"
    )
