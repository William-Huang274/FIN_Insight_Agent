from __future__ import annotations

import hashlib
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCOPE_PATH = (
    PROJECT_ROOT
    / "configs/releases/fin_ia_0_1_s4_t10_s4_pass_or_honest_block_closeout_scope_decision_v1_0.json"
)
PROGRAM_BACKLOG_PATH = PROJECT_ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
S4_BACKLOG_PATH = PROJECT_ROOT / "configs/releases/fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_source_bindings_are_current_and_content_addressed() -> None:
    scope = _load(SCOPE_PATH)
    assert len(scope["source_bindings"]) == 8
    for binding in scope["source_bindings"]:
        bound_path = PROJECT_ROOT / binding["ref"]
        assert bound_path.is_file()
        assert _sha256(bound_path) == binding["sha256"]


def test_pass_gate_truth_forces_honest_block_without_weakening_release() -> None:
    scope = _load(SCOPE_PATH)
    gates = scope["S4_pass_gate_truth_matrix"]
    assert gates["NVDA_historical_S3_R2_owner_accepted"] is True
    assert gates["T09_owner_evidence_disposition_complete"] is True
    for field in (
        "DELL_R2",
        "MU_R2",
        "NVDA_post_transfer_exact_product_present",
        "NVDA_qualified_senior_R3",
        "T07_current_worktree_regression_all_green",
        "three_case_R2_requirement_satisfied",
        "owner_and_qualified_senior_value_evidence_requirement_satisfied",
        "S4_pass",
        "FIN_0_1_release_qualified",
    ):
        assert gates[field] is False
    selected = scope["selected_closeout_branch"]
    assert selected["branch"] == "S4_honestly_blocked_FIN_0_1_not_qualified"
    assert selected["selection_is_mandatory_from_current_evidence"] is True
    assert selected["owner_option_A_is_bound"] is True
    assert selected["release_requirements_weakened"] is False


def test_scope_does_not_execute_closeout_or_enter_s5() -> None:
    scope = _load(SCOPE_PATH)
    authority = scope["authority"]
    progression = scope["progression_rule"]
    assert authority["S4_closeout_executed_or_inferred_now"] is False
    assert authority["S5_entry_executed_or_inferred_now"] is False
    assert authority["release_candidate_release_or_production_authorized_or_inferred"] is False
    assert progression["this_scope_decision_is_S4_closeout"] is False
    assert progression["this_scope_decision_enters_S5"] is False
    assert progression["future_closeout_requires_separate_execution_step"] is True


def test_carry_forward_keeps_s5_and_fin_0_2_ownership_separate() -> None:
    scope = _load(SCOPE_PATH)
    carry = scope["carry_forward_boundary"]
    assert carry["S5_entry_mode_after_future_T10_closeout"] == "decision_only_honest_block"
    assert carry["S5_release_candidate_execution_allowed"] is False
    assert carry["S5_paid_three_case_rerun_allowed"] is False
    assert "Git_commit_manifest_rollback_slice_and_secret_safe_release_evidence" in carry["S5_scope"]
    assert "DELL_and_MU_R2_formal_reproof" in carry["FIN_0_2_scope"]
    assert "complete_single_source_contract_compiler" in carry["FIN_0_2_scope"]


def test_all_mutating_and_external_budgets_are_zero() -> None:
    scope = _load(SCOPE_PATH)
    assert set(scope["hard_budgets"].values()) == {0}
    prohibited = set(scope["prohibited_during_scope_and_future_closeout"])
    assert "T05_T06_T07_repair_reopen_or_paid_live" in prohibited
    assert "release_candidate_creation_or_RG_execution" in prohibited
    assert "release_gate_weakening_or_historical_evidence_rewrite" in prohibited


def test_historical_scope_preserves_its_next_step_without_binding_mutable_current_pointer() -> None:
    scope = _load(SCOPE_PATH)
    expected = "S4-T10-S4-HONEST-BLOCK-CLOSEOUT-AND-S5-DECISION-ONLY-HANDOFF"
    assert scope["next_action"] == expected
    assert scope["authority"]["S4_closeout_executed_or_inferred_now"] is False
    assert scope["authority"]["S5_entry_executed_or_inferred_now"] is False
    assert scope["progression_rule"]["future_closeout_requires_separate_execution_step"] is True


def test_backlogs_preserve_non_inflation_after_t10_progression() -> None:
    program = _load(PROGRAM_BACKLOG_PATH)
    s4 = _load(S4_BACKLOG_PATH)
    program_t10 = next(
        item
        for stage in program["slices"]
        if stage["slice_id"] == "S4"
        for item in stage["items"]
        if item["item_id"] == "S4-T10"
    )
    s4_t10 = next(item for item in s4["tasks"] if item["item_id"] == "S4-T10")
    assert program_t10["status"] == "closed_terminal_honest_block_FIN_0_1_not_qualified"
    assert s4_t10["status"] == "closed_terminal_honest_block_FIN_0_1_not_qualified"
    assert s4["non_inflation"]["DELL_R2"] is False
    assert s4["non_inflation"]["MU_R2"] is False
    assert s4["non_inflation"]["NVDA_R3"] is False
    assert s4["non_inflation"]["S4_passed"] is False
    assert s4["non_inflation"]["S5_entry_ready"] is True
    assert s4["non_inflation"]["Alpha_release_or_production"] is False
