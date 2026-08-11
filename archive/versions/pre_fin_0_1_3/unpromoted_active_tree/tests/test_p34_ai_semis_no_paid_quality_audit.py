from __future__ import annotations

from sec_agent.p34_lane_quality_runtime import (
    build_ai_semis_no_paid_quality_audit,
    build_ai_semis_source_route_plan,
)


def test_p34_no_paid_quality_audit_blocks_paid_writer_until_live_route_and_quality_closeout() -> None:
    audit = build_ai_semis_no_paid_quality_audit()

    assert audit["schema_version"] == "fin_insight_p34_ai_semis_no_paid_quality_audit_v0_1"
    assert audit["status"] == "blocked_live_route_attempt_and_quality_gaps_pending"
    assert audit["metrics"]["allow_paid_memo_writer"] is False
    assert audit["metrics"]["allow_full_chain"] is False
    assert audit["metrics"]["paid_llm_run"] is False


def test_p34_no_paid_quality_audit_identifies_missing_quality_lanes() -> None:
    audit = build_ai_semis_no_paid_quality_audit()
    chains = {row["chain_id"]: row for row in audit["chain_results"]}

    assert chains["jc_ai_capex_demand_pool"]["fixture_answerability_status"] == "fail_no_hyperscaler_capex_fixture_supported_slots"
    assert chains["jc_market_price_in_capital_feedback"]["fixture_answerability_status"] == "fail_no_fixture_supported_slots"
    assert chains["jc_counter_thesis_what_would_change"]["fixture_answerability_status"] == "fail_no_counter_thesis_fixture_supported_slots"
    assert chains["jc_dell_ai_server_financial_quality"]["fixture_answerability_status"].startswith("partial_")


def test_p34_no_paid_quality_audit_preserves_positive_fixture_value_without_overpromotion() -> None:
    audit = build_ai_semis_no_paid_quality_audit()
    chains = {row["chain_id"]: row for row in audit["chain_results"]}

    assert chains["jc_accelerator_architecture_competition"]["fixture_supported_slot_count"] >= 3
    assert chains["jc_foundry_semicap_readthrough"]["fixture_supported_slot_count"] >= 3
    assert all(
        not row["fixture_answerability_status"].startswith("pass")
        for row in audit["chain_results"]
    )


def test_p34_no_paid_quality_audit_allows_scoped_writer_after_attempt_backed_boundaries() -> None:
    route_plan = build_ai_semis_source_route_plan()
    slot_ids = [slot["evidence_row_id"] for slot in route_plan["slots"]]
    live_report = {
        "status": "live_route_attempts_recorded_with_remaining_typed_gaps",
        "metrics": {
            "attempt_count": len(slot_ids),
            "accepted_runtime_row_count": len(slot_ids),
            "typed_gap_count": 2,
            "unattempted_slot_count": 0,
            "perform_network": True,
        },
        "accepted_runtime_rows": [{"evidence_row_id": slot_id} for slot_id in slot_ids],
        "typed_gaps": [
            {
                "evidence_row_id": "dell_ai_server_margin_bridge_quality_gap",
                "judgment_chain_ids": ["jc_dell_ai_server_financial_quality"],
                "attempt_backed": True,
            },
            {
                "evidence_row_id": "market_price_in_exact_positioning_gap",
                "judgment_chain_ids": ["jc_market_price_in_capital_feedback"],
                "attempt_backed": True,
            },
        ],
    }

    audit = build_ai_semis_no_paid_quality_audit(
        source_route_plan=route_plan,
        live_route_attempt_report=live_report,
    )

    assert audit["status"] == "bounded_quality_audit_pass_scoped_writer_allowed_full_chain_blocked"
    assert audit["metrics"]["chain_fail_count"] == 0
    assert audit["metrics"]["allow_scoped_paid_memo_writer"] is True
    assert audit["metrics"]["allow_paid_memo_writer"] is True
    assert audit["metrics"]["allow_full_chain"] is False
