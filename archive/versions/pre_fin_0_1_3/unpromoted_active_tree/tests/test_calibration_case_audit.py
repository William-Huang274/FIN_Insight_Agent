from __future__ import annotations

from pathlib import Path

from sec_agent.calibration_case_audit import (
    build_calibration_case_selection,
    build_historical_case_audit,
    build_sector_report_archetype_audit,
    load_json,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG_ROOT = ROOT / "configs" / "engineering_handoff"


def _audits():
    historical = build_historical_case_audit(
        ROOT, load_json(CONFIG_ROOT / "historical_case_audit_sources_v0_1.json")
    )
    archetype = build_sector_report_archetype_audit(
        load_json(CONFIG_ROOT / "sector_report_archetype_sources_v0_1.json")
    )
    return historical, archetype


def test_historical_case_audit_does_not_confuse_catalog_breadth_with_quality() -> None:
    historical, _ = _audits()

    assert historical["status"] == "pass"
    assert historical["source_membership_row_count"] >= 120
    assert historical["unique_case_count"] >= 100
    assert historical["artifact_backed_case_count"] == 15
    assert historical["exemplar_artifact_backed_case_count"] == 14
    assert historical["live_or_case_specific_artifact_case_count"] == 1
    assert historical["fresh_specialist_fixture_proven_case_count"] == 1
    assert historical["fresh_specialist_proven_case_count"] == 0
    assert historical["explicit_full_chain_proven_case_count"] == 0
    assert historical["explicit_human_accepted_case_count"] == 0
    assert historical["generalization_status"] == "not_proven"
    assert historical["legacy_benchmark_diagnostic_run_count"] == 2
    assert historical["current_multi_agent_or_manual_run_evidence_count"] == 4
    assert historical["current_runtime_cross_sector_generalization_status"] == "not_proven"
    assert all(row["worklog_present"] for row in historical["historical_run_evidence"])


def test_sector_report_archetype_audit_preserves_sector_specific_mechanisms() -> None:
    _, archetype = _audits()

    assert archetype["status"] == "pass"
    by_sector = {row["sector"]: row for row in archetype["sector_archetypes"]}
    assert "funding_mix_to_nim" in by_sector["banks_financials"]["decision_mechanisms"]
    assert "reimbursement_to_access" in by_sector["healthcare_pharma_medtech"]["decision_mechanisms"]
    assert "traffic_ticket_to_same_store_sales" in by_sector["retail_consumer"]["decision_mechanisms"]
    assert "capacity_bottleneck_to_rent_capture" in by_sector["semiconductors_ai_infrastructure"]["decision_mechanisms"]
    assert archetype["design_conclusions"]["report_type_is_orthogonal_to_sector"] is True


def test_calibration_selection_uses_anchor_shadows_and_negative_controls() -> None:
    historical, archetype = _audits()
    selection = build_calibration_case_selection(historical, archetype)

    assert selection["status"] == "pass"
    assert len(selection["positive_cases"]) == 4
    assert len(selection["negative_controls"]) == 3
    assert selection["positive_cases"][0]["historical_maturity"] == "fresh_specialist_fixture_proven"
    assert selection["execution_policy"]["full_chain_allowed"] is False
