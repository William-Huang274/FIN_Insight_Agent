from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "data_expansion" / "promote_product_operating_metric_repair_candidates.py"
SPEC = importlib.util.spec_from_file_location("promote_product_operating_metric_repair_candidates", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _repair_fact(**overrides: object) -> dict:
    row = {
        "ticker": "WBD",
        "company": "Warner Bros. Discovery, Inc.",
        "fact_id": "repair-1",
        "metric_family": "subscribers_or_arpu",
        "metric_name": "subscribers",
        "product_node_id": "PRODUCTNODE::WBD::segment::streaming",
        "product_or_segment": "Streaming",
        "period": "FY2025",
        "unit": "USD",
        "unit_category": "currency_per_user",
        "value": 131_600_000.0,
        "row_label": "Total Streaming subscribers",
        "column_label": "December 31, 2025",
        "citation_span": "Subscriber information consisted of the following (in millions). Total Streaming subscribers | 131.6",
        "source_url": "https://example.test/wbd",
    }
    row.update(overrides)
    return row


def test_promotes_wbd_streaming_subscribers_with_unit_correction() -> None:
    repair = _repair_fact()
    combined, promoted, rejected, summary = MODULE.promote_operating_metric_candidates(
        base_rows=[],
        repair_rows=[repair],
        revenue_rejection_rows=[{"fact_id": "repair-1", "rejection_reason": "not_product_revenue"}],
        generated_at="2026-06-12T00:00:00+00:00",
    )

    assert len(combined) == 1
    assert len(promoted) == 1
    assert not rejected
    assert promoted[0]["unit"] == "subscribers"
    assert promoted[0]["unit_category"] == "subscribers"
    assert promoted[0]["repair_claim_scope"] == "company_disclosed_streaming_subscribers"
    assert summary["promoted_fact_count"] == 1


def test_promotes_ed_gas_delivered_mdt_with_unit_correction() -> None:
    repair = _repair_fact(
        ticker="ED",
        fact_id="ed-1",
        metric_family="unit_sales_or_deliveries",
        row_label="Total Gas Delivered to CECONY Customers",
        value=172_977.0,
        citation_span="Gas Delivered (MDt) Firm sales Full service | Total Gas Delivered to CECONY Customers",
    )
    combined, promoted, rejected, summary = MODULE.promote_operating_metric_candidates(
        base_rows=[],
        repair_rows=[repair],
        revenue_rejection_rows=[{"fact_id": "ed-1", "rejection_reason": "not_product_revenue"}],
        generated_at="2026-06-12T00:00:00+00:00",
    )

    assert len(combined) == 1
    assert len(promoted) == 1
    assert not rejected
    assert promoted[0]["metric_name"] == "gas_delivered"
    assert promoted[0]["unit"] == "MDt"
    assert promoted[0]["unit_category"] == "thousand_dekatherms"
    assert promoted[0]["repair_claim_scope"] == "company_disclosed_gas_delivered_mdt"
    assert summary["promoted_metric_family_counts"] == {"unit_sales_or_deliveries": 1}


def test_rejects_ed_gas_delivered_low_values_as_row_binding_failure() -> None:
    repair = _repair_fact(
        ticker="ED",
        fact_id="ed-low",
        metric_family="unit_sales_or_deliveries",
        row_label="Total Gas Delivered to CECONY Customers",
        value=2_730.0,
        citation_span="Gas Delivered (MDt) Firm sales Full service | Total Gas Delivered to CECONY Customers",
    )
    _, promoted, rejected, summary = MODULE.promote_operating_metric_candidates(
        base_rows=[],
        repair_rows=[repair],
        revenue_rejection_rows=[{"fact_id": "ed-low", "rejection_reason": "not_product_revenue"}],
        generated_at="2026-06-12T00:00:00+00:00",
    )

    assert not promoted
    assert rejected[0]["rejection_reason"] == "ed_gas_delivered_customer_count_or_subtotal_not_total_mdt"
    assert summary["rejection_reason_counts"] == {"ed_gas_delivered_customer_count_or_subtotal_not_total_mdt": 1}
