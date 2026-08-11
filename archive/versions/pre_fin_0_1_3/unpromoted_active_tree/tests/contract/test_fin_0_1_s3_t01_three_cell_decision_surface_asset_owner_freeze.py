from __future__ import annotations

import json
from pathlib import Path

from sec_agent.canonical_runtime.planning_service import P02_4_FIXED_CELL_SEEDS


ROOT = Path(__file__).resolve().parents[2]
RELEASES = ROOT / "configs" / "releases"
CONTRACT = (
    RELEASES
    / "fin_ia_0_1_s3_t01_three_cell_decision_surface_asset_owner_freeze_v1_0.json"
)
ENTRY = RELEASES / "fin_ia_0_1_s3_entry_and_detailed_backlog_freeze_v1_0.json"
BACKLOG = RELEASES / "fin_ia_0_1_program_release_backlog_v2_0.json"
ROOT_CAUSES = ROOT / "docs" / "project_os" / "root_cause_issue_ledger.jsonl"
METHODS = ROOT / "docs" / "project_os" / "financial_research_method_registry.jsonl"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _latest_jsonl(path: Path, key: str) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            rows[row[key]] = row
    return rows


def _jsonl_status_history(path: Path, key: str) -> dict[str, set[str]]:
    rows: dict[str, set[str]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            rows.setdefault(row[key], set()).add(row["status"])
    return rows


def _asset_path(ref: str) -> Path:
    return ROOT / ref.split(":", 1)[0]


def test_t01_freezes_exact_three_cells_aliases_questions_roles_stop_and_wwc() -> None:
    contract = _load(CONTRACT)
    entry = _load(ENTRY)
    cells = contract["decision_surface"]["cells"]
    entry_cells = entry["product_scope"]["active_cells"]

    assert contract["decision_surface"]["active_cell_cardinality"] == 3
    assert [cell["program_cell_id"] for cell in cells] == [
        "demand_authenticity_and_sustainability",
        "value_and_profit_capture",
        "bottleneck_counterevidence_and_what_would_change",
    ]
    assert [cell["legacy_cell_key"] for cell in cells] == [
        "demand_reality",
        "value_profit_capture",
        "bottleneck_counterevidence",
    ]
    assert [cell["evidence_role"] for cell in cells] == [
        "demand_signal",
        "revenue_capture",
        "thesis_counterevidence",
    ]
    assert [cell["unique_owner_role"] for cell in cells] == [
        "industry_analyst",
        "financial_analyst",
        "risk_reviewer",
    ]
    assert [cell["decision_question"] for cell in cells] == [
        cell["decision_question"] for cell in entry_cells
    ]
    seeds = {cell.cell_key: cell for cell in P02_4_FIXED_CELL_SEEDS}
    for cell in cells:
        seed = seeds[cell["legacy_cell_key"]]
        assert cell["stop_rule"] == seed.stop_rule
        assert cell["what_would_change"] == seed.what_would_change
        assert cell["legacy_evidence_roles"] == [
            slot.evidence_role for slot in seed.evidence_slots
        ]
    assert all("cannot_infer" in " ".join(cell["typed_terminal_states"]) for cell in cells)


def test_t01_has_one_existing_runtime_family_and_atomic_file_owners() -> None:
    contract = _load(CONTRACT)
    lineage = contract["single_runtime_lineage"]
    assert lineage["runtime_cardinality"] == 1
    assert lineage["research_run_cardinality_per_exact_execution"] == 1
    assert lineage["parallel_runtime_registry_writer_store_or_business_truth_family_allowed"] is False
    assert lineage["ordered_object_path"][3:5] == [
        "Fin01ResearchRuntime",
        "ResearchRunVersion",
    ]
    for row in contract["object_owner_freeze"]:
        assert isinstance(row["unique_owner"], str)
        assert "," not in row["unique_owner"]
        assert " and " not in row["unique_owner"]
        assert _asset_path(row["unique_owner"]).is_file()


def test_t01_asset_dispositions_exist_and_old_admission_is_reference_only() -> None:
    contract = _load(CONTRACT)
    dispositions = {row["asset"]: row for row in contract["asset_disposition"]}
    assert all(_asset_path(ref).is_file() for ref in dispositions)
    historical = dispositions[
        "configs/releases/fin_ia_0_1_p36_three_cell_deepseek_vertical_contract_v1_1.json"
    ]
    assert historical["disposition"] == (
        "historical_reference_only_never_reuse_as_S3_admission"
    )
    assert dispositions["configs/releases/fin_ia_0_1_vt4_p36_candidate_profile_v1_0.json"][
        "disposition"
    ] == "ten_cell_fixture_reference_only_no_release_activation"


def test_all_fifteen_current_root_causes_are_mapped_once_without_imputed_closure() -> None:
    contract = _load(CONTRACT)
    entry = _load(ENTRY)
    history = _jsonl_status_history(ROOT_CAUSES, "issue_id")
    mapping = contract["root_cause_reconcile_map"]
    refs = [row["issue_id"] for row in mapping]

    assert len(refs) == len(set(refs)) == 15
    assert set(refs) == set(
        entry["root_cause_entry_constraints"][
            "must_address_before_exact_live_readiness"
        ]
    )
    assert all(
        row["ledger_status_at_freeze"] in history[row["issue_id"]] for row in mapping
    )
    assert all("not_closed" in row["T01_disposition"] or "gap_remains_open" in row["T01_disposition"] for row in mapping)
    assert all(row["blocks_exact_live_readiness_now"] is True for row in mapping)
    assert all(row["earliest_owner_task"] in {f"S3-T{i:02d}" for i in range(2, 8)} for row in mapping)
    assert all(_asset_path(row["unique_owner"]).is_file() for row in mapping)


def test_method_registry_labels_do_not_become_runtime_capability() -> None:
    contract = _load(CONTRACT)
    latest = _latest_jsonl(METHODS, "method_id")
    mappings = contract["method_to_runtime_freeze"]
    assert {row["method_id"] for row in mappings} == {
        "product_to_financial_bridge",
        "customer_supplier_readthrough",
        "bounded_leading_signal_promotion",
        "p32_product_architecture_competitive_bridge",
        "p32_semis_cycle_value_chain_playbook",
    }
    for row in mappings:
        assert row["registry_recorded_status"] == latest[row["method_id"]]["status"]
        assert row["S3_normalized_state"] in {
            "registry_only_not_runtime_capability",
            "fixture_proven_but_not_runtime_injected_for_S3",
        }
        assert "node_level_consumed" in row["completion_proof"]


def test_t01_remains_zero_call_after_separately_authorized_t02_and_t03_advance() -> None:
    contract = _load(CONTRACT)
    backlog = _load(BACKLOG)
    s3 = next(row for row in backlog["slices"] if row["slice_id"] == "S3")
    tasks = {row["item_id"]: row for row in s3["items"]}

    assert set(contract["observed_counts"].values()) == {0}
    assert contract["authority"]["S3_T02_execution_authorized"] is False
    assert tasks["S3-T01"]["status"].startswith("pass_zero_call")
    assert tasks["S3-T01"]["root_causes_mapped"] == 15
    assert tasks["S3-T01"]["root_causes_closed_by_T01"] == 0
    assert tasks["S3-T02"]["status"].startswith("pass_runtime_plan")
    assert tasks["S3-T03"]["status"].startswith("pass_cell_driven_evidence_route")
    assert tasks["S3-T04"]["status"].startswith("pass_deterministic_financial_numeric")
    assert tasks["S3-T05"]["status"].startswith("pass_bounded_graph_product_market")
    assert tasks["S3-T06"]["status"] == "pass"
    assert tasks["S3-T07"]["status"] == (
        "pass_deterministic_presentation_and_review_target_T08_ready"
    )
    assert tasks["S3-T08"]["status"] == (
        "pass_readiness_gate_and_three_cell_adapter_repair_T09_ready_pending_separate_authority"
    )
    assert tasks["S3-T09"]["status"] == (
        "artifact_integrity_pass_owner_grade_repair_required_no_paired_baseline"
    )
    assert tasks["S3-T10"]["status"].startswith("blocked_by_")
    assert backlog["next_action"]["item_id"] == (
        "S3-T09-OWNER-GRADE-SEMANTIC-ACTIONABILITY-ZERO-CALL-REPAIR-IMPLEMENTATION"
    )
    assert backlog["next_action"]["S3_T08_repair_execution_authorized"] is True
    assert backlog["next_action"]["S3_T09_execution_authorized"] is True
    assert backlog["next_action"]["S3_T09_admission_consumed"] is True
    assert backlog["next_action"][
        "S3_T09_specialist_model_view_and_output_budget_repair_execution_authorized"
    ] is True
    assert backlog["next_action"][
        "S3_T09_replacement_exact_admission_issuance_authorized"
    ] is True
    assert backlog["next_action"][
        "S3_T09_replacement_exact_live_execution_authorized"
    ] is True
    assert backlog["next_action"][
        "S3_T09_replacement_artifact_paired_baseline_validation_authorized"
    ] is True
    assert backlog["next_action"]["deterministic_baseline_materialization_authorized"] is False
    assert backlog["next_action"]["replacement_admission_or_execution_authorized"] is False
