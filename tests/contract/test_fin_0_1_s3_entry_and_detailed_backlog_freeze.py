from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RELEASES = ROOT / "configs" / "releases"
ENTRY = RELEASES / "fin_ia_0_1_s3_entry_and_detailed_backlog_freeze_v1_0.json"
BACKLOG = RELEASES / "fin_ia_0_1_program_release_backlog_v2_0.json"
ROOT_CAUSES = ROOT / "docs" / "project_os" / "root_cause_issue_ledger.jsonl"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_s3_entry_is_three_cell_zero_call_and_not_live_execution_authority() -> None:
    entry = _load(ENTRY)
    assert entry["status"] == "pass_S3_entry_T01_ready_pending_separate_authorization"
    assert entry["authority"] == {
        "user_instruction": "进入s3",
        "S3_entry_and_current_slice_backlog_freeze_authorized": True,
        "S3_T01_execution_authorized": False,
        "model_or_provider_execution_authorized": False,
        "source_network_or_external_tool_execution_authorized": False,
        "live_business_case_mutation_authorized": False,
        "release_or_production_authorized": False,
    }
    assert set(entry["entry_observed_counts"].values()) == {0}
    cells = entry["product_scope"]["active_cells"]
    assert [row["program_cell_id"] for row in cells] == [
        "demand_authenticity_and_sustainability",
        "value_and_profit_capture",
        "bottleneck_counterevidence_and_what_would_change",
    ]
    assert [row["evidence_role"] for row in cells] == [
        "demand_signal",
        "revenue_capture",
        "thesis_counterevidence",
    ]


def test_s3_entry_preserves_existing_assets_without_reusing_historical_admission() -> None:
    entry = _load(ENTRY)
    dispositions = {row["asset"]: row for row in entry["asset_disposition"]}
    historical = dispositions[
        "configs/releases/fin_ia_0_1_p36_three_cell_deepseek_vertical_contract_v1_1.json"
    ]
    assert historical["disposition"] == "historical_reference_only_not_reusable_S3_admission"
    assert dispositions["apps/workbench/backend/application/bounded_agent_executor.py"][
        "disposition"
    ].startswith("refactor_existing_one_cell_executor")
    assert entry["method_to_runtime_boundary"]["registry_status_alone_is_completion"] is False
    assert "consensus_valuation_scenario_catalyst_or_investment_alpha_contract" in (
        entry["product_scope"]["explicit_non_goals"]
    )


def test_s3_root_cause_constraints_reference_current_open_project_owned_gaps() -> None:
    entry = _load(ENTRY)
    latest: dict[str, dict] = {}
    for line in ROOT_CAUSES.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            latest[row["issue_id"]] = row
    refs = entry["root_cause_entry_constraints"]["must_address_before_exact_live_readiness"]
    assert len(refs) == 15
    assert all(ref in latest for ref in refs)
    assert all(not latest[ref]["status"].startswith("closed") for ref in refs)
    assert entry["root_cause_entry_constraints"]["deterministic_S3_implementation_allowed"] is True
    assert entry["root_cause_entry_constraints"]["paid_or_broad_three_cell_run_allowed_now"] is False


def test_program_backlog_preserves_entry_and_advances_through_t08_gate() -> None:
    backlog = _load(BACKLOG)
    assert backlog["active_slice"] in {"S3", "S4", "S5"}
    s3 = next(row for row in backlog["slices"] if row["slice_id"] == "S3")
    assert s3["status"] != "not_started"
    items = s3["items"]
    assert [row["item_id"] for row in items] == [f"S3-T{i:02d}" for i in range(1, 11)]
    positions = {row["item_id"]: index for index, row in enumerate(items)}
    for row in items:
        for dependency in row.get("depends_on", ()):
            if dependency.startswith("S3-T"):
                assert positions[dependency] < positions[row["item_id"]]
    assert items[0]["status"] == (
        "pass_zero_call_decision_surface_asset_owner_and_root_cause_freeze"
    )
    assert items[1]["status"] == (
        "pass_runtime_plan_branch_lineage_and_role_context_contract"
    )
    assert items[2]["status"].startswith("pass_cell_driven_evidence_route")
    assert items[3]["status"].startswith("pass_deterministic_financial_numeric")
    assert items[4]["status"].startswith("pass_bounded_graph_product_market")
    assert items[5]["status"] == "pass"
    assert items[6]["status"] == "pass_deterministic_presentation_and_review_target_T08_ready"
    assert items[7]["status"] == (
        "pass_readiness_gate_and_three_cell_adapter_repair_T09_ready_pending_separate_authority"
    )
    assert items[8]["status"] != "not_started"
    assert items[9]["status"].startswith("blocked_by_")
    mapped_root_causes = {
        ref for row in items for ref in row.get("root_cause_owners", ())
    }
    assert mapped_root_causes == set(
        _load(ENTRY)["root_cause_entry_constraints"][
            "must_address_before_exact_live_readiness"
        ]
    )
