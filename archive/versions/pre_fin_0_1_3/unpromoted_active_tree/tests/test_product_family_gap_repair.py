from __future__ import annotations

from sec_agent.product_family_gap_repair import build_product_family_gap_repair_ledger


def test_gap_repair_ledger_does_not_final_closeout_when_ladder_is_missing() -> None:
    result = build_product_family_gap_repair_ledger(
        closeout_rows=[
            {
                "ticker": "2317.TW",
                "company_name": "Hon Hai Precision Industry Co., Ltd.",
                "family_id": "electronics_manufacturing_services",
                "family_name": "Electronics Manufacturing / ODM",
                "slot_status": "seed_needs_locator",
                "closeout_class": "bounded_public_gap",
                "closeout_reason": "official_site_access_blocked_or_timeout",
            }
        ],
        before_slots=[
            {
                "ticker": "2317.TW",
                "family_id": "electronics_manufacturing_services",
                "slot_status": "seed_needs_locator",
            }
        ],
        after_slots=[
            {
                "ticker": "2317.TW",
                "family_id": "electronics_manufacturing_services",
                "slot_status": "seed_needs_locator",
            }
        ],
        materialization_attempts=[
            {"ticker": "2317.TW", "url": "https://www.foxconn.com/products", "status": "unusable_response"}
        ],
        context_rows=[],
        generated_at="2026-06-18T00:00:00Z",
    )

    row = result["rows"][0]
    assert row["repair_state"] == "adapter_needed_not_final_gap"
    assert row["final_gap_allowed"] is False
    assert "local_exchange_or_regulator_path_checked" in row["missing_ladder_steps"]
    assert result["summary"]["final_gap_allowed_count"] == 0


def test_gap_repair_ledger_marks_fixed_when_after_slot_is_runtime_ready() -> None:
    result = build_product_family_gap_repair_ledger(
        closeout_rows=[
            {
                "ticker": "MPWR",
                "company_name": "Monolithic Power Systems",
                "family_id": "power_semiconductor_components",
                "family_name": "Power Semiconductor Components",
                "slot_status": "seed_needs_locator",
                "closeout_class": "bounded_public_gap",
                "closeout_reason": "official_site_client_challenge",
            }
        ],
        before_slots=[
            {"ticker": "MPWR", "family_id": "power_semiconductor_components", "slot_status": "seed_needs_locator"}
        ],
        after_slots=[
            {"ticker": "MPWR", "family_id": "power_semiconductor_components", "slot_status": "official_surface_slot"}
        ],
        materialization_attempts=[
            {"ticker": "MPWR", "url": "https://www.monolithicpower.com/en/products.html", "status": "materialized"}
        ],
        context_rows=[
            {
                "ticker": "MPWR",
                "source_id": "company_product_pages",
                "structured_context_type": "product_spec_context",
            }
        ],
        generated_at="2026-06-18T00:00:00Z",
    )

    row = result["rows"][0]
    assert row["repair_state"] == "fixed_to_runtime_row"
    assert row["allowed_runtime_use"] == "product_specialist_bounded_context"
    assert result["summary"]["repair_state_counts"] == {"fixed_to_runtime_row": 1}
