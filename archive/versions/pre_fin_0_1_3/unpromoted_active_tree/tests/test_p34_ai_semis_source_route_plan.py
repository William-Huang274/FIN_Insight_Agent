from __future__ import annotations

from sec_agent.p34_lane_quality_runtime import build_ai_semis_source_route_plan


def test_p34_source_route_plan_covers_all_ai_semis_slots() -> None:
    plan = build_ai_semis_source_route_plan()
    slot_ids = {slot["evidence_row_id"] for slot in plan["slots"]}

    assert plan["schema_version"] == "fin_insight_p34_ai_semis_source_route_plan_v0_1"
    assert plan["lane"] == "AI/Semis"
    assert plan["metrics"]["slot_count"] == 20
    assert len(slot_ids) == 20
    assert "dell_ai_server_orders_shipments_backlog" in slot_ids
    assert "counter_thesis_pack_ai_semis" in slot_ids


def test_p34_source_route_plan_has_primary_and_fallback_routes_for_every_slot() -> None:
    plan = build_ai_semis_source_route_plan()

    assert plan["metrics"]["slot_with_primary_route_count"] == 20
    assert plan["metrics"]["slot_with_fallback_route_count"] == 20
    assert plan["metrics"]["route_gap_count"] == 0
    assert plan["metrics"]["primary_route_count"] == 20
    assert plan["metrics"]["fallback_route_count"] >= 20


def test_p34_source_route_plan_keeps_parser_contract_and_gap_taxonomy() -> None:
    plan = build_ai_semis_source_route_plan()

    assert "parser_gap" in plan["typed_gap_taxonomy"]
    assert "source_absent_after_attempt" in plan["typed_gap_taxonomy"]
    for route in plan["routes"]:
        output_contract = route["parser_output_contract"]
        assert "source_url" in output_contract["normalized_runtime_row_fields"]
        assert "parser_lineage" in output_contract["must_preserve"]
        assert route["promotion_without_execution_allowed"] is False
        assert route["typed_gap_rules"]


def test_p34_source_route_plan_prioritizes_first_adapter_fixtures() -> None:
    plan = build_ai_semis_source_route_plan()
    adapter_counts = plan["adapter_family_counts"]

    assert adapter_counts["sec_8k_earnings_release_table_adapter"] >= 6
    assert adapter_counts["official_product_spec_page_adapter"] >= 6
    assert adapter_counts["semicap_bookings_backlog_adapter"] >= 3
    assert plan["pre_writer_decision"]["allow_paid_memo_writer"] is False
    assert plan["pre_writer_decision"]["allow_full_chain"] is False


def test_p34_source_route_plan_does_not_promote_weak_candidates() -> None:
    plan = build_ai_semis_source_route_plan()
    weak_slots = [
        slot
        for slot in plan["slots"]
        if slot["p33_backfill_status"] == "source_route_candidate_weak_not_bound"
    ]

    assert weak_slots
    assert all(
        slot["quality_gate"]["promotion_without_route_execution_allowed"] is False
        for slot in weak_slots
    )
    assert all(
        slot["route_plan_status"] == "route_plan_ready_adapter_fixture_required_before_promotion"
        for slot in weak_slots
    )
