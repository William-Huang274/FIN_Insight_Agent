from __future__ import annotations

import hashlib
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCOPE_PATH = (
    PROJECT_ROOT
    / "configs/releases/fin_ia_0_1_repository_recovery_s0_to_s4_audit_and_0_1_1_0_1_2_version_lineage_scope_decision_v1_0.json"
)
PROGRAM_BACKLOG_PATH = PROJECT_ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
S4_BACKLOG_PATH = PROJECT_ROOT / "configs/releases/fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
TECH_RETRO_PATH = (
    PROJECT_ROOT
    / "docs/architecture/repository/FIN_0_1_S0_TO_S4_DUAL_THREAD_ENGINEERING_RETROSPECTIVE_AND_REFINED_S_SERIES_20260731.zh-CN.md"
)
VERSION_DECISION_PATH = (
    PROJECT_ROOT
    / "docs/product/FIN_0_1_1_0_1_2_VERSION_LINEAGE_AND_RELEASE_CADENCE_DECISION_20260731.zh-CN.md"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_all_source_bindings_exist_and_match() -> None:
    scope = _load(SCOPE_PATH)
    assert len(scope["source_bindings"]) == 11
    for binding in scope["source_bindings"]:
        source = PROJECT_ROOT / binding["ref"]
        assert source.is_file()
        assert _sha256(source) == binding["sha256"]


def test_dual_task_history_and_repository_inventory_are_explicit() -> None:
    scope = _load(SCOPE_PATH)
    tasks = scope["Codex_task_history_audit"]
    assert tasks["current_task"]["thread_id"] == "019f91b7-662a-7f31-b71d-eb90d2ec32c2"
    assert tasks["adjacent_task"]["thread_id"] == "019f54fe-4b90-74c0-b5e7-6325c47b77ce"
    assert tasks["current_task"]["turns"] == 199
    assert tasks["adjacent_task"]["turns"] == 135
    assert tasks["current_task"]["file_change_events_not_unique_files"] == 2055
    assert tasks["adjacent_task"]["file_change_events_not_unique_files"] == 1246

    repo = scope["repository_snapshot"]
    assert repo["status_rows"] == 1118
    assert repo["staged_unstaged_untracked_rows"] == [799, 28, 317]
    assert repo["S4_T05_release_test_worklog_files"] == [74, 53, 39]
    assert repo["S4_T06_release_test_worklog_files"] == [92, 68, 66]
    assert repo["cleanup_ready"] is False


def test_release_truth_remains_honestly_blocked_without_inflation() -> None:
    scope = _load(SCOPE_PATH)
    truth = scope["audit_verdict"]
    assert truth["S4_truth"] == "honestly_blocked"
    assert truth["NVDA_historical_S3_R2"] is True
    for key in (
        "DELL_R2",
        "MU_R2",
        "NVDA_post_transfer_exact_product",
        "NVDA_qualified_senior_R3",
        "T07_all_green",
        "FIN_0_1_release_qualified",
    ):
        assert truth[key] is False
    assert truth["release_requirements_weakened"] is False


def test_version_lineage_preserves_fin_0_2_earnings_definition() -> None:
    scope = _load(SCOPE_PATH)
    lineage = scope["version_lineage"]
    assert lineage["broad_product_release_cadence_changed"] is False
    assert lineage["FIN_0_1_1"]["release_qualified"] is False
    assert lineage["FIN_0_1_2"]["name"] == "FIN_0_1_stabilization_and_transfer_qualification"
    assert lineage["FIN_0_2"]["name"] == "Earnings Review Alpha"
    assert lineage["FIN_0_2"]["original_definition_preserved"] is True
    assert lineage["FIN_0_2"]["entry"] == "FIN_0_1_runtime_and_exact_artifact_mainline_stable"

    supersession = scope["supersession"]
    assert supersession["historical_T10_scope_bytes_rewritten"] is False
    assert supersession["T10_honest_block_truth_preserved"] is True
    assert supersession["T05_T06_T07_reopened"] is False
    assert supersession["current_carry_forward"].startswith("FIN_0_1_2_owns_")


def test_refined_s_series_has_fixed_gates_and_non_bypass_budget() -> None:
    scope = _load(SCOPE_PATH)
    refined = scope["refined_S_series"]
    assert [item[0] for item in refined["macro_stages"]] == [
        "S0",
        "S1",
        "S2",
        "S3",
        "S4",
        "S5",
    ]
    assert [item[0] for item in refined["fixed_internal_gates"]] == [
        "G0",
        "G1",
        "G2",
        "G3",
        "G4",
        "G5",
        "G6",
    ]
    budgets = scope["artifact_and_run_budgets"]
    assert budgets["separate_zero_call_scope_authority_admission_proof_result_disposition_families"] == 0
    assert budgets["natural_canary_batches_per_changed_contract_family"] == 1
    assert budgets["formal_exact_live_per_product_target"] == 1
    assert budgets["automatic_R_number_or_replacement_family"] == 0
    assert "honest_block" in budgets["new_shared_runtime_L1_during_S4"]


def test_deepseek_is_not_a_financial_truth_owner() -> None:
    scope = _load(SCOPE_PATH)
    envelope = scope["DeepSeek_capability_envelope"]
    assert "request_local_alias_or_enum_selection" in envelope["allowed_outputs"]
    assert "material_number_period_unit_scale_sign_formula_inputs" in envelope["locally_owned_outputs"]
    assert "canonical_ID_ticker_entity_identity_authority_ref_lineage" in envelope["locally_owned_outputs"]
    assert "soft hints" in envelope["transport_rule"]


def test_current_action_is_inventory_only_and_all_mutation_budgets_are_zero() -> None:
    scope = _load(SCOPE_PATH)
    expected = "FIN-0.1-REPOSITORY-EVIDENCE-FREEZE-AND-SAFE-CLASSIFICATION-EXECUTION"
    assert scope["next_action"] == expected
    assert scope["next_action_scope"]["item_id"] == expected
    assert set(scope["hard_budgets"].values()) == {0}
    prohibited = set(scope["next_action_scope"]["not_allowed"])
    assert "delete_move_clean_unstage_reset_checkout" in prohibited
    assert "commit_push_tag_or_release" in prohibited
    assert "model_provider_network_source_or_live" in prohibited


def test_product_and_engineering_docs_make_the_same_decision() -> None:
    technical = TECH_RETRO_PATH.read_text(encoding="utf-8")
    product = VERSION_DECISION_PATH.read_text(encoding="utf-8")
    for text in (technical, product):
        assert "FIN 0.1.1" in text
        assert "FIN 0.1.2" in text
        assert "Earnings Review Alpha" in text
        assert "FIN-0.1-REPOSITORY-EVIDENCE-FREEZE-AND-SAFE-CLASSIFICATION-EXECUTION" in text


def test_historical_inventory_scope_is_preserved_without_binding_mutable_current_pointer() -> None:
    scope = _load(SCOPE_PATH)
    program = _load(PROGRAM_BACKLOG_PATH)
    s4 = _load(S4_BACKLOG_PATH)
    historical_next = scope["next_action"]
    current_next = (
        "FIN-0.1-REPOSITORY-CLASSIFICATION-OWNER-REVIEW-AND-"
        "COHERENT-COMMIT-SLICE-AUTHORITY-DECISION"
    )
    expected_sha = _sha256(SCOPE_PATH)
    assert historical_next == (
        "FIN-0.1-REPOSITORY-EVIDENCE-FREEZE-AND-SAFE-CLASSIFICATION-EXECUTION"
    )
    assert program["next_action"]["item_id"] == current_next
    assert program["next_action"]["repository_recovery_scope_decision_sha256"] == expected_sha
    assert s4["current_next_action"] == current_next
    assert s4["repository_recovery_and_version_lineage_scope"]["scope_decision_sha256"] == expected_sha
    assert program["next_action"]["S4_closeout_executed"] is False
    assert program["next_action"]["S5_entered"] is False
    assert s4["repository_recovery_and_version_lineage_scope"]["cleanup_executed"] is False
