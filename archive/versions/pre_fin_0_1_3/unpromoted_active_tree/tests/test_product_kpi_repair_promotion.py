from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "data_expansion" / "promote_product_kpi_repair_candidates.py"
SPEC = importlib.util.spec_from_file_location("promote_product_kpi_repair_candidates", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _fact(
    *,
    ticker: str = "TEST",
    product_node_id: str = "PRODUCTNODE::TEST::segment::cloud",
    product_or_segment: str = "Cloud",
    period: str = "FY2025",
    value: float = 100.0,
    source_id: str = "company_product_kpi_facts_structured_metric_parser",
    row_label: str = "Cloud",
    column_label: str = "Year Ended December 31, 2025",
    citation: str = "Revenue by segment (in millions): [TABLE_START] Cloud | $ | 100",
    raw_value_text: str = "$100",
) -> dict:
    return {
        "ticker": ticker,
        "company": "Test Co",
        "fact_id": f"fact-{ticker}-{product_or_segment}-{period}-{value}",
        "metric_family": "product_revenue",
        "product_node_id": product_node_id,
        "product_or_segment": product_or_segment,
        "product_node_type": "segment",
        "product_link_method": "structured_row_label_alias_exact",
        "period": period,
        "fiscal_year": int(period.replace("FY", "")),
        "unit": "USD",
        "unit_category": "currency",
        "value": value,
        "raw_value_text": raw_value_text,
        "row_label": row_label,
        "column_label": column_label,
        "source_id": source_id,
        "source_document_id": f"{ticker}_{period}_DOC",
        "source_url": "https://example.test/filing",
        "citation_span": citation,
    }


def test_promotes_monotonic_row_bound_currency_revenue() -> None:
    repair_rows = [
        _fact(
            ticker="AMT",
            product_node_id="PRODUCTNODE::AMT::segment::data_center",
            product_or_segment="Data Center",
            row_label="Data Centers",
            value=924.8,
            citation="Revenue by product category [TABLE_START] Data Centers | $ | 924.8",
        )
    ]

    combined, promoted, rejected, summary = MODULE.promote_repair_candidates(
        baseline_rows=[],
        repair_rows=repair_rows,
        generated_at="2026-06-11T00:00:00+00:00",
    )

    assert len(combined) == 1
    assert len(promoted) == 1
    assert not rejected
    assert promoted[0]["repair_claim_scope"] == "company_disclosed_product_category_revenue"
    assert promoted[0]["repair_promotion_status"] == "monotonic_repair_promoted"
    assert promoted[0]["product_node_type"] == "category_or_brand_family"
    assert summary["promoted_fact_count"] == 1


def test_rejects_geographic_revenue_without_region_dimension() -> None:
    repair_rows = [
        _fact(
            ticker="ABNB",
            product_node_id="PRODUCTNODE::ABNB::segment::north_america",
            product_or_segment="North America",
            row_label="North America",
            value=5006.0,
            citation="Revenue Disaggregated by Geographic Region [TABLE_START] North America | $ | 5,006",
        )
    ]

    _, promoted, rejected, summary = MODULE.promote_repair_candidates(
        baseline_rows=[],
        repair_rows=repair_rows,
        generated_at="2026-06-11T00:00:00+00:00",
    )

    assert not promoted
    assert {row["rejection_reason"] for row in rejected} == {"geographic_segment_requires_region_dimension"}
    assert summary["promoted_claim_scope_counts"] == {}


def test_rejects_sentence_candidates_baseline_claims_and_conflicts() -> None:
    baseline = [
        _fact(
            ticker="BASE",
            product_node_id="PRODUCTNODE::BASE::segment::cloud",
            product_or_segment="Cloud",
            value=100.0,
        )
    ]
    repair_rows = [
        _fact(
            ticker="BASE",
            product_node_id="PRODUCTNODE::BASE::segment::cloud",
            product_or_segment="Cloud",
            value=110.0,
        ),
        _fact(
            ticker="SENT",
            source_id="company_product_kpi_facts_structured_sentence_metric_parser",
            value=50.0,
        ),
        _fact(
            ticker="CONFLICT",
            product_node_id="PRODUCTNODE::CONFLICT::segment::cloud",
            value=200.0,
            citation="Revenue by product category [TABLE_START] Cloud | $ | 200",
        ),
        _fact(
            ticker="CONFLICT",
            product_node_id="PRODUCTNODE::CONFLICT::segment::cloud",
            value=201.0,
            citation="Revenue by product category [TABLE_START] Cloud | $ | 201",
        ),
    ]

    _, promoted, rejected, summary = MODULE.promote_repair_candidates(
        baseline_rows=baseline,
        repair_rows=repair_rows,
        generated_at="2026-06-11T00:00:00+00:00",
    )

    reasons = {row["rejection_reason"] for row in rejected}
    assert not promoted
    assert "claim_already_covered_by_baseline" in reasons
    assert "not_structured_table_metric" in reasons
    assert "conflicting_values_for_same_claim" in reasons
    assert summary["combined_fact_count"] == 1


def test_promotes_sales_value_from_total_sales_percent_mix_table() -> None:
    repair_rows = [
        _fact(
            ticker="LOW",
            product_node_id="PRODUCTNODE::LOW::category::kitchens_bath",
            product_or_segment="Kitchens and Bath",
            row_label="Kitchens & Bath",
            column_label="February 3, 2023",
            value=7_100_000.0,
            raw_value_text="7.1",
            citation="(In millions, except percentage data) | Total Sales | % | Total Sales | % Kitchens & Bath | $ | 6,178 | 7.1 | %",
        ),
        _fact(
            ticker="LOW",
            product_node_id="PRODUCTNODE::LOW::category::kitchens_bath",
            product_or_segment="Kitchens and Bath",
            row_label="Kitchens & Bath",
            column_label="February 3, 2023",
            value=6_178_000_000.0,
            raw_value_text="6,178",
            citation="(In millions, except percentage data) | Total Sales | % | Total Sales | % Kitchens & Bath | $ | 6,178 | 7.1 | %",
        ),
    ]

    _, promoted, rejected, summary = MODULE.promote_repair_candidates(
        baseline_rows=[],
        repair_rows=repair_rows,
        generated_at="2026-06-11T00:00:00+00:00",
    )

    assert len(promoted) == 1
    assert promoted[0]["value"] == 6_178_000_000.0
    assert {row["rejection_reason"] for row in rejected} == {"non_sales_percentage_value_in_mixed_table"}
    assert summary["promoted_fact_count"] == 1


def test_rejects_total_sales_percent_mix_when_multiple_large_sales_values_conflict() -> None:
    repair_rows = [
        _fact(
            ticker="LOW",
            product_node_id="PRODUCTNODE::LOW::category::appliances",
            product_or_segment="Appliances",
            row_label="Appliances",
            column_label="February 2, 2024",
            value=12_344_000_000.0,
            raw_value_text="12,344",
            citation="(In millions, except percentage data) | Total Sales | % | Total Sales | % Appliances | $ | 12,344 | 14.4 | %",
        ),
        _fact(
            ticker="LOW",
            product_node_id="PRODUCTNODE::LOW::category::appliances",
            product_or_segment="Appliances",
            row_label="Appliances",
            column_label="February 2, 2024",
            value=12_514_000_000.0,
            raw_value_text="12,514",
            citation="(In millions, except percentage data) | Total Sales | % | Total Sales | % Appliances | $ | 12,514 | 14.3 | %",
        ),
        _fact(
            ticker="LOW",
            product_node_id="PRODUCTNODE::LOW::category::appliances",
            product_or_segment="Appliances",
            row_label="Appliances",
            column_label="February 2, 2024",
            value=14.4,
            raw_value_text="14.4 %",
            citation="(In millions, except percentage data) | Total Sales | % | Total Sales | % Appliances | $ | 12,344 | 14.4 | %",
        ),
    ]

    _, promoted, rejected, _ = MODULE.promote_repair_candidates(
        baseline_rows=[],
        repair_rows=repair_rows,
        generated_at="2026-06-11T00:00:00+00:00",
    )

    assert not promoted
    assert {row["rejection_reason"] for row in rejected} == {"conflicting_values_for_same_claim"}


def test_promotes_sales_of_principal_products_table_without_generic_revenue_context() -> None:
    repair_rows = [
        _fact(
            ticker="KMB",
            product_node_id="PRODUCTNODE::KMB::category::consumer_tissue",
            product_or_segment="Consumer Tissue",
            row_label="Consumer tissue products",
            column_label="2023",
            value=6_200_000_000.0,
            raw_value_text="6.2",
            citation="Sales of Principal Products [TABLE_START] (Billions of dollars) | 2023 | 2022 Consumer tissue products | $ | 6.2 | $ | 6.0",
        )
    ]

    _, promoted, rejected, summary = MODULE.promote_repair_candidates(
        baseline_rows=[],
        repair_rows=repair_rows,
        generated_at="2026-06-11T00:00:00+00:00",
    )

    assert len(promoted) == 1
    assert not rejected
    assert promoted[0]["repair_claim_scope"] == "company_disclosed_product_category_revenue"
    assert summary["promotion_gate"] == "structured_table_currency_revenue_row_bound_v0_5"


def test_promotes_low_merchandising_continuation_span_when_header_is_truncated() -> None:
    repair_rows = [
        _fact(
            ticker="LOW",
            product_node_id="PRODUCTNODE::LOW::category::millwork",
            product_or_segment="Millwork",
            row_label="Millwork",
            column_label="February 3, 2023",
            value=6_000_000.0,
            raw_value_text="6.0",
            citation=(
                "Seasonal & Outdoor Living | 7,370 | 8.8 | Lumber | 6,747 | 8.1 | "
                "Lawn & Garden | 6,526 | 7.8 Kitchens & Bath | 5,869 | 7.0 | "
                "Hardware | 5,821 | 7.0 | Building Materials | 5,419 | 6.5 | Millwork | 5,180 | 6.0 |"
            ),
        ),
        _fact(
            ticker="LOW",
            product_node_id="PRODUCTNODE::LOW::category::millwork",
            product_or_segment="Millwork",
            row_label="Millwork",
            column_label="February 3, 2023",
            value=5_180_000_000.0,
            raw_value_text="5,180",
            citation=(
                "Seasonal & Outdoor Living | 7,370 | 8.8 | Lumber | 6,747 | 8.1 | "
                "Lawn & Garden | 6,526 | 7.8 Kitchens & Bath | 5,869 | 7.0 | "
                "Hardware | 5,821 | 7.0 | Building Materials | 5,419 | 6.5 | Millwork | 5,180 | 6.0 |"
            ),
        ),
    ]

    _, promoted, rejected, _ = MODULE.promote_repair_candidates(
        baseline_rows=[],
        repair_rows=repair_rows,
        generated_at="2026-06-11T00:00:00+00:00",
    )

    assert len(promoted) == 1
    assert promoted[0]["value"] == 5_180_000_000.0
    assert {row["rejection_reason"] for row in rejected} == {"non_sales_percentage_value_in_mixed_table"}


def test_promotes_tsn_sales_block_and_rejects_operating_income_block() -> None:
    citation = (
        "The following table is a summary of segment sales and operating income (loss) "
        "for fiscal years ended 2024, 2023 and 2022: [TABLE_START] in millions "
        "Sales | Operating Income (Loss) 2024 | 2023 | 2022 | 2024 | 2023 | 2022 "
        "Beef (a) | $ | 20,479 | $ | 19,325 | $ | 19,854 | $ | 381 | $ | 91 | $ | 2,502"
    )
    repair_rows = [
        _fact(
            ticker="TSN",
            product_node_id="PRODUCTNODE::TSN::segment::beef",
            product_or_segment="Beef",
            row_label="Beef (a)",
            column_label="2022",
            value=19_854_000_000.0,
            raw_value_text="$ 19,854",
            citation=citation,
        ),
        _fact(
            ticker="TSN",
            product_node_id="PRODUCTNODE::TSN::segment::beef",
            product_or_segment="Beef",
            row_label="Beef (a)",
            column_label="2022",
            value=2_502_000_000.0,
            raw_value_text="$ 2,502",
            citation=citation,
        ),
    ]

    _, promoted, rejected, _ = MODULE.promote_repair_candidates(
        baseline_rows=[],
        repair_rows=repair_rows,
        generated_at="2026-06-11T00:00:00+00:00",
    )

    assert len(promoted) == 1
    assert promoted[0]["value"] == 19_854_000_000.0
    assert {row["rejection_reason"] for row in rejected} == {"non_sales_operating_income_value_in_mixed_table"}


def test_promotes_tsn_sales_block_from_truncated_segment_table_context() -> None:
    citation = (
        "table_context=rating income (loss) for fiscal years ended 2024, 2023 and 2022, "
        "which is how we measure segment income (loss): [TABLE_START] in millions "
        "Sales | Operating Income (Loss) 2024 | 2023 | 2022 | 2024 | 2023 | 2022 "
        "Chicken (c) | $ | 16,425 | $ | 17,060 | $ | 16,961 | $ | 988 | $ | 91 | $ | 955"
    )
    repair_rows = [
        _fact(
            ticker="TSN",
            product_node_id="PRODUCTNODE::TSN::segment::chicken",
            product_or_segment="Chicken",
            row_label="Chicken (c)",
            column_label="2024",
            value=16_425_000_000.0,
            raw_value_text="$ 16,425",
            citation=citation,
        ),
        _fact(
            ticker="TSN",
            product_node_id="PRODUCTNODE::TSN::segment::chicken",
            product_or_segment="Chicken",
            row_label="Chicken (c)",
            column_label="2024",
            value=988_000_000.0,
            raw_value_text="$ 988",
            citation=citation,
        ),
    ]

    _, promoted, rejected, _ = MODULE.promote_repair_candidates(
        baseline_rows=[],
        repair_rows=repair_rows,
        generated_at="2026-06-11T00:00:00+00:00",
    )

    assert len(promoted) == 1
    assert promoted[0]["value"] == 16_425_000_000.0
    assert {row["rejection_reason"] for row in rejected} == {"non_sales_operating_income_value_in_mixed_table"}


def test_promotes_dri_restaurant_sales_block_only() -> None:
    citation = (
        "Sales | Average Annual Sales per Restaurant (2) Fiscal Year Ended | Percent Change | "
        "Fiscal Year Ended (in millions) | May 28, 2023 | May 29, 2022 | SRS (1) | "
        "May 28, 2023 | May 29, 2022 LongHorn Steakhouse | $ | 2,612.3 | $ | 2,374.3 | "
        "10.0 | % | $ | 4.7 | $ | 4.4"
    )
    repair_rows = [
        _fact(
            ticker="DRI",
            product_node_id="PRODUCTNODE::DRI::segment::longhorn_steakhouse",
            product_or_segment="LongHorn Steakhouse",
            row_label="LongHorn Steakhouse",
            column_label="(in millions)",
            value=2_612_300_000.0,
            raw_value_text="$ 2,612.3",
            citation=citation,
        ),
        _fact(
            ticker="DRI",
            product_node_id="PRODUCTNODE::DRI::segment::longhorn_steakhouse",
            product_or_segment="LongHorn Steakhouse",
            row_label="LongHorn Steakhouse",
            column_label="May 28, 2023",
            value=4_700_000.0,
            raw_value_text="$ 4.7",
            citation=citation,
        ),
    ]

    _, promoted, rejected, _ = MODULE.promote_repair_candidates(
        baseline_rows=[],
        repair_rows=repair_rows,
        generated_at="2026-06-11T00:00:00+00:00",
    )

    assert len(promoted) == 1
    assert promoted[0]["value"] == 2_612_300_000.0
    assert {row["rejection_reason"] for row in rejected} == {
        "missing_product_category_or_source_specific_revenue_table_context"
    }


def test_promotes_hubb_net_sales_segment_table() -> None:
    repair = _fact(
        ticker="HUBB",
        product_node_id="PRODUCTNODE::HUBB::segment::electrical_solutions",
        product_or_segment="Electrical Solutions",
        row_label="Total Electrical Solutions",
        column_label="2024",
        value=2_027_800_000.0,
        raw_value_text="$ 2,027.8",
        citation=(
            "December 31, in millions | 2024 | 2023 | 2022 Net sales Grid Infrastructure | $ | 2,531.3 "
            "Grid Automation | 1,069.4 Total Utility Solutions | $ | 3,600.7 Electrical Products | $ | 931.8 "
            "Industrial | 1,074.8 Retail and Builder | 21.2 Total Electrical Solutions | $ | 2,027.8"
        ),
    )

    _, promoted, rejected, _ = MODULE.promote_repair_candidates(
        baseline_rows=[],
        repair_rows=[repair],
        generated_at="2026-06-11T00:00:00+00:00",
    )

    assert len(promoted) == 1
    assert not rejected
    assert promoted[0]["repair_claim_scope"] == "company_disclosed_product_or_segment_revenue"


def test_promotes_es_customer_contract_revenue_table() -> None:
    repair_rows = [
        _fact(
            ticker="ES",
            product_node_id="PRODUCTNODE::ES::service::transmission",
            product_or_segment="Transmission",
            row_label="Wholesale Transmission Revenues",
            column_label="2021",
            value=290_800_000.0,
            raw_value_text="290.8",
            citation=(
                "ues from Contracts with Customers Retail Tariff Sales Residential | "
                "Total Retail Tariff Sales Revenues | Wholesale Transmission Revenues | 290.8"
            ),
        ),
        _fact(
            ticker="ES",
            product_node_id="PRODUCTNODE::ES::service::transmission",
            product_or_segment="Transmission",
            row_label="Wholesale Transmission Revenues",
            column_label="2021",
            value=290_800_000.0,
            raw_value_text="290.8",
            citation=(
                "ues from Contracts with Customers Retail Tariff Sales Residential | "
                "Total Retail Tariff Sales Revenues | Wholesale Transmission Revenues | 290.8"
            ),
        ),
    ]

    _, promoted, rejected, _ = MODULE.promote_repair_candidates(
        baseline_rows=[],
        repair_rows=repair_rows,
        generated_at="2026-06-11T00:00:00+00:00",
    )

    assert len(promoted) == 1
    assert {row["rejection_reason"] for row in rejected} == {"duplicate_promoted_semantic_fact"}
