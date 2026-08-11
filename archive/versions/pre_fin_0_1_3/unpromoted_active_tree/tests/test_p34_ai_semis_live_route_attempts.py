from __future__ import annotations

from sec_agent.p34_lane_quality_runtime import (
    build_ai_semis_live_route_attempt_report,
    build_ai_semis_no_paid_quality_audit,
)


def test_p34_live_route_attempt_report_uses_existing_live_rows_without_paid_or_full_chain() -> None:
    report = build_ai_semis_live_route_attempt_report(perform_network=False)

    assert report["schema_version"] == "fin_insight_p34_ai_semis_live_route_attempt_report_v0_1"
    assert report["metrics"]["paid_llm_run"] is False
    assert report["metrics"]["full_chain_run"] is False
    assert report["metrics"]["perform_network"] is False
    assert report["metrics"]["attempt_count"] >= 1
    assert report["metrics"]["accepted_runtime_row_count"] >= 4
    assert "nvda_gb200_nvl72_rack_architecture" in report["accepted_slot_ids"]
    assert all(row.get("parser_lineage") for row in report["accepted_runtime_rows"])


def test_p34_live_route_attempt_report_does_not_count_not_run_as_attempt_backed_gap() -> None:
    report = build_ai_semis_live_route_attempt_report(perform_network=False)

    not_run_gap_slots = {
        gap["evidence_row_id"]
        for gap in report["typed_gaps"]
        if gap.get("attempt_backed") is not True
    }
    assert not_run_gap_slots
    assert not not_run_gap_slots.intersection(report["attempt_backed_gap_slot_ids"])


def test_p34_no_paid_audit_consumes_live_attempt_report_but_stays_blocked() -> None:
    live_report = build_ai_semis_live_route_attempt_report(perform_network=False)
    audit = build_ai_semis_no_paid_quality_audit(live_route_attempt_report=live_report)
    chains = {row["chain_id"]: row for row in audit["chain_results"]}

    assert audit["status"] == "blocked_live_route_attempt_and_quality_gaps_pending"
    assert audit["metrics"]["allow_paid_memo_writer"] is False
    assert audit["metrics"]["accepted_live_runtime_row_count"] >= 4
    assert chains["jc_accelerator_architecture_competition"]["live_supported_slot_count"] >= 1
    assert chains["jc_market_price_in_capital_feedback"]["live_supported_slot_count"] == 1
    assert chains["jc_market_price_in_capital_feedback"]["attempt_backed_gap_slot_count"] == 1
