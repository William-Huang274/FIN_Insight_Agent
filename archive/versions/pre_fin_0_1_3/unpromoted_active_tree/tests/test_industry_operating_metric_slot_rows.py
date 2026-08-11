from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "data_expansion"
    / "build_industry_operating_metric_slot_rows.py"
)
SPEC = importlib.util.spec_from_file_location("build_industry_operating_metric_slot_rows", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "verifier_id": "verifier:1",
        "ticker": "TEST",
        "company": "Test Co",
        "source_id": "company_product_kpi_facts_structured_metric_parser",
        "verifier_class": "business_segment_metric",
        "verifier_reason": "company_disclosed_business_segment_revenue_candidate",
        "metric_family": "product_revenue",
        "metric_name": "net sales",
        "product_or_segment": "Cloud Services",
        "period": "FY2025",
        "unit": "USD",
        "unit_category": "currency",
        "value": 1200000000.0,
        "row_label": "Cloud Services",
        "column_label": "2025",
        "citation_sample": "Revenue by segment [TABLE_START] Cloud Services | $ | 1,200",
        "source_url": "https://example.test/10k",
        "source_document_id": "TEST_10K",
    }
    row.update(overrides)
    return row


def test_promotes_business_segment_revenue_as_industry_slot_not_product_kpi() -> None:
    rows, rejects = MODULE.build_industry_operating_metric_slot_rows(
        verifier_rows=[_row()],
        docket_context={"TEST": {"primary_lane_id": "V3", "company_name": "Test Co"}},
        generated_at="2026-06-19T00:00:00Z",
    )

    assert not rejects
    assert len(rows) == 1
    assert rows[0]["slot_id"] == "business_segment_revenue"
    assert rows[0]["source_id"] == "industry_operating_metric_exact_slot"
    assert "product_revenue" in rows[0]["forbidden_claims"]


def test_rejects_region_and_generic_rows() -> None:
    candidates = [
        _row(verifier_id="verifier:region", product_or_segment="North America", row_label="North America"),
        _row(verifier_id="verifier:total", product_or_segment="Total", row_label="Total revenue"),
    ]
    rows, rejects = MODULE.build_industry_operating_metric_slot_rows(
        verifier_rows=candidates,
        docket_context={"TEST": {"primary_lane_id": "V8"}},
        generated_at="2026-06-19T00:00:00Z",
    )

    assert rows == []
    assert [row["rejection_reason"] for row in rejects] == [
        "region_only_not_industry_operating_slot",
        "business_segment_metric_not_currency_revenue_or_generic_row",
    ]


def test_promotes_slot_specific_operating_metrics_only_when_context_matches() -> None:
    candidates = [
        _row(
            verifier_id="verifier:orders",
            verifier_class="operating_metric_defer_step2",
            metric_family="backlog_or_orders",
            product_or_segment="Equipment",
            row_label="Backlog",
            column_label="2025",
            value=900000000.0,
            citation_sample="Backlog by segment [TABLE_START] Equipment | $ | 900",
        ),
        _row(
            verifier_id="verifier:false-production",
            verifier_class="operating_metric_defer_step2",
            metric_family="production_or_throughput",
            product_or_segment="Production Solutions",
            row_label="Production Solutions",
            column_label="Total Revenue",
            value=3806.0,
            unit="units",
            unit_category="units",
            citation_sample="Revenue by segment [TABLE_START] Production Solutions | Total Revenue | 3,806",
        ),
        _row(
            verifier_id="verifier:same-store",
            verifier_class="operating_metric_defer_step2",
            metric_family="same_store_sales",
            product_or_segment="Comparable stores",
            row_label="Same-store sales",
            column_label="2025",
            value=-3.2,
            unit="percent_change",
            unit_category="ratio",
            raw_value_text="(3.2) %",
            citation_sample="Same-store sales growth [TABLE_START] Same-store sales | (3.2) %",
        ),
    ]
    rows, rejects = MODULE.build_industry_operating_metric_slot_rows(
        verifier_rows=candidates,
        docket_context={"TEST": {"primary_lane_id": "V8"}},
        generated_at="2026-06-19T00:00:00Z",
    )

    assert [row["slot_id"] for row in rows] == ["backlog_or_orders", "same_store_sales_growth"]
    assert len(rejects) == 1
    assert rejects[0]["rejection_reason"] == "production_metric_without_capacity_or_throughput_context"


def test_promotes_segment_orders_as_bounded_backlog_or_order_slot() -> None:
    rows, rejects = MODULE.build_industry_operating_metric_slot_rows(
        verifier_rows=[
            _row(
                verifier_id="verifier:segment-orders",
                verifier_class="operating_metric_defer_step2",
                metric_family="backlog_or_orders",
                metric_name="orders",
                product_or_segment="Segment Orders",
                row_label="Segment Orders",
                column_label="2025",
                value=5706600000.0,
                citation_sample=(
                    "row=Segment Orders | column=2025 | value=$ 5,706.6 | "
                    "subsection=Segment Results | table_context=Segment Results for Years Ended December 31"
                ),
            )
        ],
        docket_context={"TEST": {"primary_lane_id": "V7"}},
        generated_at="2026-06-19T00:00:00Z",
    )

    assert not rejects
    assert len(rows) == 1
    assert rows[0]["slot_id"] == "backlog_or_orders"
    assert "product revenue" in rows[0]["claim_boundary"]


def test_rejects_expense_table_mislabeled_as_business_segment_metric() -> None:
    rows, rejects = MODULE.build_industry_operating_metric_slot_rows(
        verifier_rows=[
            _row(
                verifier_id="verifier:cme-expense-licensing",
                product_or_segment="Licensing and other fee agreements",
                row_label="Licensing and other fee agreements",
                column_label="2025",
                value=371000000.0,
                citation_sample=(
                    "Expenses [TABLE_START] Compensation and benefits | Technology support services | "
                    "Licensing and other fee agreements | 371.0"
                ),
            )
        ],
        docket_context={"TEST": {"primary_lane_id": "V6"}},
        generated_at="2026-06-25T00:00:00Z",
    )

    assert rows == []
    assert [row["rejection_reason"] for row in rejects] == ["expense_table_not_industry_operating_slot"]


def test_rejects_investing_cash_flow_sales_rows() -> None:
    rows, rejects = MODULE.build_industry_operating_metric_slot_rows(
        verifier_rows=[
            _row(
                verifier_id="verifier:aig-security-sales",
                product_or_segment="Sales of fixed maturity securities",
                row_label="Sales of fixed maturity securities",
                column_label="2025",
                value=2500000000.0,
                citation_sample=(
                    "Cash flows from investing activities [TABLE_START] "
                    "Sales of fixed maturity securities | $2,500"
                ),
            )
        ],
        docket_context={"TEST": {"primary_lane_id": "V6"}},
        generated_at="2026-06-25T00:00:00Z",
    )

    assert rows == []
    assert [row["rejection_reason"] for row in rejects] == ["cash_flow_table_not_industry_operating_slot"]


def test_rejects_production_payment_obligation_as_production_volume() -> None:
    rows, rejects = MODULE.build_industry_operating_metric_slot_rows(
        verifier_rows=[
            _row(
                verifier_id="verifier:lac-production-payment",
                verifier_class="operating_metric_defer_step2",
                metric_family="production_or_throughput",
                product_or_segment="Production payment obligation",
                row_label="Production payment obligation",
                column_label="2025",
                unit="USD",
                value=100000000.0,
                citation_sample="Production payment obligation [TABLE_START] Production payment obligation | $100",
            )
        ],
        docket_context={"TEST": {"primary_lane_id": "V7"}},
        generated_at="2026-06-25T00:00:00Z",
    )

    assert rows == []
    assert [row["rejection_reason"] for row in rejects] == ["production_payment_obligation_not_production_volume"]


def test_promotes_marketplace_gov_as_industry_operating_metric() -> None:
    rows, rejects = MODULE.build_industry_operating_metric_slot_rows(
        verifier_rows=[
            _row(
                verifier_id="verifier:marketplace-gov",
                verifier_class="operating_metric_defer_step2",
                metric_family="backlog_or_orders",
                metric_name="Marketplace GOV",
                product_or_segment="Marketplace GOV",
                row_label="Marketplace GOV",
                column_label="Year Ended December 31, 2025",
                period="FY2025",
                unit="USD",
                value=102018000000.0,
                raw_value_text="$ 102,018",
                citation_sample="Overview [TABLE_START] Marketplace GOV | Year Ended December 31, 2025 | $102,018",
            )
        ],
        docket_context={"TEST": {"primary_lane_id": "V3"}},
        generated_at="2026-06-25T00:00:00Z",
    )

    assert not rejects
    assert len(rows) == 1
    assert rows[0]["slot_id"] == "marketplace_gross_order_value"
    assert "not product revenue" in rows[0]["claim_boundary"]


def test_does_not_promote_neighbor_rows_from_marketplace_gov_table() -> None:
    rows, rejects = MODULE.build_industry_operating_metric_slot_rows(
        verifier_rows=[
            _row(
                verifier_id="verifier:adjusted-ebitda-neighbor",
                verifier_class="operating_metric_defer_step2",
                metric_family="backlog_or_orders",
                metric_name="Adjusted EBITDA",
                product_or_segment="Adjusted EBITDA (1)",
                row_label="Adjusted EBITDA (1)",
                column_label="Year Ended December 31, 2025",
                period="FY2025",
                unit="USD",
                value=2779000000.0,
                raw_value_text="$ 2,779",
                citation_sample="Overview [TABLE_START] Marketplace GOV | Adjusted EBITDA (1) | $2,779",
            )
        ],
        docket_context={"TEST": {"primary_lane_id": "V3"}},
        generated_at="2026-06-25T00:00:00Z",
    )

    assert rows == []
    assert [row["rejection_reason"] for row in rejects] == ["backlog_metric_without_backlog_or_order_context"]


def test_customer_type_other_sales_disaggregation_is_business_mix_not_generic_other() -> None:
    rows, rejects = MODULE.build_industry_operating_metric_slot_rows(
        verifier_rows=[
            _row(
                verifier_id="verifier:customer-type-other",
                product_or_segment="Other Sales, Sales Adjustments, and Sales From Acquired Stores",
                row_label="Other sales, sales adjustments, and sales from acquired stores",
                column_label="2024",
                period="FY2024",
                value=452909000.0,
                citation_sample=(
                    "evenues disaggregated by major customer type for the years ended December 31 "
                    "[TABLE_START] Sales to do-it-yourself customers | Sales to professional service providers | "
                    "Other sales, sales adjustments, and sales from acquired stores"
                ),
            )
        ],
        docket_context={"TEST": {"primary_lane_id": "V8"}},
        generated_at="2026-06-19T00:00:00Z",
    )

    assert not rejects
    assert len(rows) == 1
    assert rows[0]["slot_id"] == "business_segment_revenue"
    assert "not product-family revenue" in rows[0]["claim_boundary"]


def test_repairs_mislabeled_product_revenue_units_sold_into_unit_sales_slot() -> None:
    rows, rejects = MODULE.build_industry_operating_metric_slot_rows(
        verifier_rows=[
            _row(
                verifier_id="verifier:retail-units-sold",
                verifier_class="business_segment_mixed_table_needs_column_group",
                verifier_reason="segment_table_contains_mixed_financial_columns",
                metric_family="product_revenue",
                metric_name="product revenue",
                product_or_segment="Retail Units Sold",
                row_label="Retail units sold",
                column_label="2024",
                unit="USD",
                unit_category="currency",
                raw_value_text="416,348",
                value=416348000.0,
                citation_sample=(
                    "key operating metrics demonstrate our ability to translate these drivers into retail sales "
                    "[TABLE_START] Retail units sold | 416,348"
                ),
            )
        ],
        docket_context={"TEST": {"primary_lane_id": "V8"}},
        generated_at="2026-06-19T00:00:00Z",
    )

    assert not rejects
    assert len(rows) == 1
    row = rows[0]
    assert row["slot_id"] == "unit_sales_or_deliveries"
    assert row["value"] == 416348.0
    assert row["unit"] == "units"
    assert row["source_value"] == 416348000.0
    assert row["source_unit"] == "USD"
    assert "mislabeled" in row["claim_boundary"]


def test_repairs_mislabeled_product_revenue_identical_sales_into_same_store_growth_slot() -> None:
    rows, rejects = MODULE.build_industry_operating_metric_slot_rows(
        verifier_rows=[
            _row(
                verifier_id="verifier:identical-sales",
                verifier_class="percentage_or_change",
                verifier_reason="not_currency_revenue_or_raw_percent",
                metric_family="product_revenue",
                metric_name="sales",
                product_or_segment="Identical Sales Excluding Fuel (1)",
                row_label="Identical sales excluding fuel (1)",
                column_label="2023 2023",
                unit="percent_of_revenue",
                unit_category="percent_of_revenue",
                raw_value_text="0.9 %",
                value=0.9,
                citation_sample="The following table provides highlights [TABLE_START] Identical sales excluding fuel (1) | 0.9 %",
            )
        ],
        docket_context={"TEST": {"primary_lane_id": "V8"}},
        generated_at="2026-06-19T00:00:00Z",
    )

    assert not rejects
    assert len(rows) == 1
    row = rows[0]
    assert row["slot_id"] == "same_store_sales_growth"
    assert row["unit"] == "percent_change"
    assert "mislabeled" in row["claim_boundary"]
    assert "product_revenue" in row["forbidden_claims"]


def test_repairs_same_store_residential_revenue_component_without_promoting_revenue() -> None:
    rows, rejects = MODULE.build_industry_operating_metric_slot_rows(
        verifier_rows=[
            _row(
                verifier_id="verifier:lease-rate-component",
                verifier_class="percentage_or_change",
                verifier_reason="not_currency_revenue_or_raw_percent",
                metric_family="product_revenue",
                metric_name="product revenue",
                product_or_segment="Lease Rates",
                row_label="Lease rates",
                column_label="2024",
                unit="percent_of_revenue",
                unit_category="percent_of_revenue",
                raw_value_text="2.2 %",
                value=2.2,
                citation_sample=(
                    "The following table details the increase in Same Store Residential revenue by component "
                    "for the year ended December 31, 2024 [TABLE_START] Lease rates | 2.2 %"
                ),
            )
        ],
        docket_context={"TEST": {"primary_lane_id": "V7"}},
        generated_at="2026-06-19T00:00:00Z",
    )

    assert not rejects
    assert len(rows) == 1
    row = rows[0]
    assert row["slot_id"] == "same_store_revenue_growth_component"
    assert row["unit"] == "percent_change_component"
    assert "not product revenue" in row["claim_boundary"]


def test_repairs_segment_revenue_growth_percentage_without_promoting_revenue_level() -> None:
    rows, rejects = MODULE.build_industry_operating_metric_slot_rows(
        verifier_rows=[
            _row(
                verifier_id="verifier:segment-growth",
                verifier_class="sentence_relation_insufficient",
                verifier_reason="needs_local_relation_verification",
                metric_family="product_revenue",
                metric_name="product revenue",
                product_or_segment="Total Application Software",
                row_label="Total Revenue Growth",
                column_label="2025",
                period="FY2025",
                unit="percent_of_revenue",
                unit_category="percent_of_revenue",
                raw_value_text="15.9 %",
                value=15.9,
                citation_sample="Technology enabled products [TABLE_START] Total Application Software | Total Revenue Growth | 15.9 %",
            ),
            _row(
                verifier_id="verifier:tax-false-positive",
                verifier_class="percentage_or_change",
                verifier_reason="not_currency_revenue_or_raw_percent",
                metric_family="product_revenue",
                metric_name="product revenue",
                product_or_segment="Global Industrial",
                row_label="Global Industrial",
                column_label="2024",
                period="FY2024",
                unit="percent_of_revenue",
                unit_category="percent_of_revenue",
                raw_value_text="7 %",
                value=7.0,
                citation_sample="Provision for income taxes [TABLE_START] Global Industrial | 7 %",
            ),
        ],
        docket_context={"TEST": {"primary_lane_id": "V3"}},
        generated_at="2026-06-19T00:00:00Z",
    )

    assert len(rows) == 1
    assert rows[0]["slot_id"] == "segment_revenue_growth"
    assert rows[0]["unit"] == "percent_change"
    assert "revenue level" in rows[0]["claim_boundary"]
    assert rejects == []


def test_repairs_travel_units_mislabeled_as_usd_revenue() -> None:
    rows, rejects = MODULE.build_industry_operating_metric_slot_rows(
        verifier_rows=[
            _row(
                verifier_id="verifier:room-nights",
                verifier_class="business_segment_metric",
                verifier_reason="business_segment_candidate_without_source_specific_segment_table_context",
                metric_family="product_revenue",
                metric_name="product revenue",
                product_or_segment="Room Nights",
                row_label="Room nights",
                column_label="2023",
                period="FY2023",
                unit="USD",
                unit_category="currency",
                raw_value_text="896",
                value=896000000.0,
                citation_sample="room nights, rental car days, and airline tickets [TABLE_START] Room nights | 896",
            ),
            _row(
                verifier_id="verifier:room-nights-header",
                verifier_class="business_segment_metric",
                verifier_reason="business_segment_candidate_without_source_specific_segment_table_context",
                metric_family="product_revenue",
                metric_name="product revenue",
                product_or_segment="Room Nights",
                row_label="Room nights",
                column_label="(in millions)",
                period="FY2023",
                unit="USD",
                unit_category="currency",
                raw_value_text="1,049",
                value=1049000000.0,
                citation_sample="room nights, rental car days, and airline tickets [TABLE_START] Room nights | 1,049",
            ),
        ],
        docket_context={"TEST": {"primary_lane_id": "V8"}},
        generated_at="2026-06-19T00:00:00Z",
    )

    assert len(rows) == 1
    assert len(rejects) == 1
    row = rows[0]
    assert row["slot_id"] == "room_nights"
    assert row["value"] == 896.0
    assert row["unit"] == "million_room_nights"
    assert rejects[0]["rejection_reason"] == "mislabeled_operating_metric_without_exact_period_column_binding"


def test_repairs_real_estate_revenue_per_occupied_square_foot_mislabeled_as_revenue() -> None:
    rows, rejects = MODULE.build_industry_operating_metric_slot_rows(
        verifier_rows=[
            _row(
                verifier_id="verifier:revenue-per-foot",
                verifier_class="percentage_or_change",
                verifier_reason="mixed_percent_table_or_percent_like_cell",
                metric_family="product_revenue",
                metric_name="revenue",
                product_or_segment="Average Annual Total Revenues Per Occupied Square Foot (5)",
                row_label="Average annual total revenues per occupied square foot (5)",
                column_label="2022",
                period="FY2022",
                unit="USD",
                unit_category="currency",
                raw_value_text="$ 69",
                value=69000.0,
                citation_sample="same store table [TABLE_START] Average annual total revenues per occupied square foot | $ 69",
            )
        ],
        docket_context={"TEST": {"primary_lane_id": "V7"}},
        generated_at="2026-06-19T00:00:00Z",
    )

    assert not rejects
    assert len(rows) == 1
    row = rows[0]
    assert row["slot_id"] == "revenue_per_occupied_square_foot"
    assert row["value"] == 69.0
    assert row["unit"] == "USD_per_occupied_square_foot"


def test_conflicting_values_for_same_industry_slot_are_rejected() -> None:
    candidates = [
        _row(verifier_id="verifier:one", value=100.0),
        _row(verifier_id="verifier:two", value=200.0),
    ]
    rows, rejects = MODULE.build_industry_operating_metric_slot_rows(
        verifier_rows=candidates,
        docket_context={"TEST": {"primary_lane_id": "V3"}},
        generated_at="2026-06-19T00:00:00Z",
    )

    assert rows == []
    assert [row["rejection_reason"] for row in rejects] == [
        "conflicting_values_for_industry_operating_claim",
        "conflicting_values_for_industry_operating_claim",
    ]


def test_resolves_column_group_conflict_when_total_matches_sibling_sum() -> None:
    candidates = [
            _row(
                verifier_id="verifier:us",
                period="FY2024",
                value=1800.0,
            row_label="Pediatric Nutritionals",
            column_label="U.S. 2024",
            citation_sample="Nutritionals [TABLE_START] Total | U.S. | Int'l | Pediatric Nutritionals | 1800",
        ),
            _row(
                verifier_id="verifier:intl",
                period="FY2024",
                value=2200.0,
            row_label="Pediatric Nutritionals",
            column_label="International 2024",
            citation_sample="Nutritionals [TABLE_START] Total | U.S. | Int'l | Pediatric Nutritionals | 2200",
        ),
            _row(
                verifier_id="verifier:total",
                period="FY2024",
                value=4000.0,
            row_label="Pediatric Nutritionals",
            column_label="Total 2024",
            citation_sample="Nutritionals [TABLE_START] Total | U.S. | Int'l | Pediatric Nutritionals | 4000",
        ),
    ]
    rows, rejects = MODULE.build_industry_operating_metric_slot_rows(
        verifier_rows=candidates,
        docket_context={"TEST": {"primary_lane_id": "V4"}},
        generated_at="2026-06-19T00:00:00Z",
    )

    assert len(rows) == 1
    assert rows[0]["value"] == 4000.0
    assert rows[0]["conflict_resolution_status"] == "aggregate_total_selected_from_column_group_conflict"
    assert [row["rejection_reason"] for row in rejects] == [
        "conflict_resolved_non_aggregate_sibling",
        "conflict_resolved_non_aggregate_sibling",
    ]


def test_financial_operating_slots_do_not_fall_into_business_segment_revenue() -> None:
    candidates = [
        _row(
            verifier_id="verifier:aum",
            product_or_segment="Equity",
            row_label="Equity",
            column_label="Average AUM",
            value=544000000000.0,
            citation_sample="ASSETS UNDER MANAGEMENT AUM by asset class [TABLE_START] Equity | $544.0",
        ),
        _row(
            verifier_id="verifier:payment-frequency",
            product_or_segment="Number of Payment Transactions Per Active Account",
            row_label="Number of payment transactions per active account",
            column_label="Year Ended December 31, 2024",
            period="FY2024",
            raw_value_text="60.6",
            value=60600000.0,
            citation_sample="Selected payment metrics [TABLE_START] Number of payment transactions per active account | 60.6",
        ),
        _row(
            verifier_id="verifier:cross-border-tpv",
            verifier_class="percentage_or_change",
            verifier_reason="not_currency_revenue_or_raw_percent",
            metric_family="product_revenue",
            product_or_segment="Percent of Cross-border TPV (1)",
            row_label="Percent of cross-border TPV (1)",
            column_label="Year Ended December 31, 2024",
            period="FY2024",
            unit="percent_of_revenue",
            unit_category="percent_of_revenue",
            raw_value_text="12 %",
            value=12.0,
            citation_sample="Selected payment metrics [TABLE_START] Percent of cross-border TPV (1) | 12 %",
        ),
        _row(
            verifier_id="verifier:aum-flow",
            product_or_segment="Long-term Inflows",
            row_label="Long-term inflows",
            column_label="2024",
            value=419000000000.0,
            citation_sample="Assets under management rollforward [TABLE_START] Long-term inflows | $419.0",
        ),
        _row(
            verifier_id="verifier:deposit-service-charge",
            product_or_segment="Service Charges On Deposit Accounts",
            row_label="Service charges on deposit accounts",
            column_label="2024",
            value=193000000.0,
            citation_sample="Noninterest revenue [TABLE_START] Service charges on deposit accounts | $193",
        ),
    ]
    rows, rejects = MODULE.build_industry_operating_metric_slot_rows(
        verifier_rows=candidates,
        docket_context={"TEST": {"primary_lane_id": "V6"}},
        generated_at="2026-06-19T00:00:00Z",
    )

    assert [row["slot_id"] for row in rows] == ["aum", "payment_transactions_per_active_account", "tpv_mix_percent"]
    assert rows[1]["value"] == 60.6
    assert rows[1]["unit"] == "transactions_per_active_account"
    assert rows[2]["unit"] == "percent_of_tpv"
    assert [row["rejection_reason"] for row in rejects] == [
        "business_segment_metric_not_currency_revenue_or_generic_row",
        "business_segment_metric_not_currency_revenue_or_generic_row",
    ]


def test_summary_requires_no_unclassified_rejections() -> None:
    rows, rejects = MODULE.build_industry_operating_metric_slot_rows(
        verifier_rows=[_row()],
        docket_context={"TEST": {"primary_lane_id": "V3"}},
        generated_at="2026-06-19T00:00:00Z",
    )
    summary = MODULE.build_summary(
        runtime_rows=rows,
        rejection_rows=rejects,
        generated_at="2026-06-19T00:00:00Z",
        output_rows=Path("rows.jsonl"),
        output_rejections=Path("rejects.jsonl"),
        output_report=Path("report.md"),
    )

    assert summary["status"] == "pass"
    assert summary["runtime_row_count"] == 1
    assert summary["unclassified_rejection_count"] == 0
