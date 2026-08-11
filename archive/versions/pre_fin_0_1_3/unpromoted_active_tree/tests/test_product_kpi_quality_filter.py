from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "data_expansion" / "quality_filter_product_kpi_fact_layer.py"
SPEC = importlib.util.spec_from_file_location("quality_filter_product_kpi_fact_layer", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _fact(**overrides: object) -> dict:
    row = {
        "ticker": "TEST",
        "fact_id": "fact-1",
        "metric_family": "product_revenue",
        "metric_name": "revenue",
        "product_or_segment": "Cloud",
        "period": "FY2025",
        "unit": "USD",
        "unit_category": "currency",
        "value": 100.0,
        "row_label": "Cloud",
        "column_label": "2025",
        "citation_span": "Revenue by segment Cloud $100",
    }
    row.update(overrides)
    return row


def test_suppresses_non_positive_product_revenue() -> None:
    assert MODULE.suppression_reason(_fact(value=-10.0)) == "non_positive_product_revenue_level_invalid"


def test_suppresses_subscriber_metric_misclassified_as_revenue() -> None:
    assert (
        MODULE.suppression_reason(
            _fact(row_label="Total Streaming subscribers", citation_span="Subscriber information consisted of the following")
        )
        == "subscriber_metric_misclassified_as_product_revenue"
    )


def test_suppresses_ed_gas_delivered_rows_until_mdt_repair() -> None:
    assert (
        MODULE.suppression_reason(
            _fact(
                ticker="ED",
                metric_family="unit_sales_or_deliveries",
                unit="units",
                row_label="Total Gas Delivered to CECONY Customers",
                citation_span="Gas Delivered (MDt) Firm sales Full service | Total Gas Delivered to CECONY Customers",
                value=2_730.0,
            )
        )
        == "ed_gas_delivered_requires_mdt_source_specific_repair"
    )


def test_keeps_positive_revenue_and_operating_metrics() -> None:
    assert MODULE.suppression_reason(_fact(value=10.0)) == ""
    assert MODULE.suppression_reason(_fact(metric_family="subscribers_or_arpu", value=10.0, row_label="Total subscribers")) == ""
