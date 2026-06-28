from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "data_expansion"
    / "build_product_kpi_source_specific_verifier.py"
)
SPEC = importlib.util.spec_from_file_location("build_product_kpi_source_specific_verifier", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _candidate(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "ticker": "TEST",
        "company": "Test Co",
        "fact_id": "fact-1",
        "source_id": "company_product_kpi_facts_structured_metric_parser",
        "metric_family": "product_revenue",
        "metric_name": "product revenue",
        "product_or_segment": "Widgets",
        "matched_product_alias": "Widgets",
        "product_node_id": "PRODUCTNODE::TEST::category::widgets",
        "product_node_type": "category_or_brand_family",
        "product_link_method": "structured_row_label_alias_exact",
        "period": "FY2024",
        "fiscal_year": 2024,
        "unit": "USD",
        "unit_category": "currency",
        "value": 1200000000.0,
        "raw_value_text": "$1,200",
        "row_label": "Widgets",
        "column_label": "2024",
        "citation_span": "Revenue by product category [TABLE_START] Widgets | $ | 1,200",
    }
    row.update(overrides)
    return row


def test_verifier_promotes_only_product_category_or_product_line_metrics() -> None:
    rows = MODULE.build_verifier_rows(candidate_rows=[_candidate()], generated_at="2026-06-19T00:00:00Z")

    assert rows[0]["verifier_decision"] == "promote"
    assert rows[0]["verifier_class"] == "promotable_product_category_or_product_line_metric"
    assert rows[0]["can_promote_product_kpi_exact"] is True
    assert rows[0]["product_link_method"] == "structured_row_label_alias_exact"


def test_verifier_classifies_business_segment_without_product_promotion() -> None:
    rows = MODULE.build_verifier_rows(
        candidate_rows=[
            _candidate(
                product_or_segment="Cloud Services",
                matched_product_alias="Cloud Services",
                product_node_type="segment",
                row_label="Cloud Services",
                citation_span="Revenue by segment [TABLE_START] Cloud Services | $ | 1,200",
            )
        ],
        generated_at="2026-06-19T00:00:00Z",
    )

    assert rows[0]["verifier_decision"] == "classify_only"
    assert rows[0]["verifier_class"] == "business_segment_metric"
    assert rows[0]["can_promote_product_kpi_exact"] is False
    assert rows[0]["defer_to_step"] == "step2_industry_operating_metric_slot"


def test_verifier_rejects_region_percentage_and_sentence_candidates() -> None:
    candidates = [
        _candidate(product_or_segment="North America", row_label="North America"),
        _candidate(unit="percent_of_revenue", unit_category="ratio", raw_value_text="14.4 %", value=14.4),
        _candidate(source_id="company_product_kpi_facts_structured_sentence_metric_parser"),
    ]
    rows = MODULE.build_verifier_rows(candidate_rows=candidates, generated_at="2026-06-19T00:00:00Z")

    assert [row["verifier_class"] for row in rows] == [
        "region_only",
        "percentage_or_change",
        "sentence_relation_insufficient",
    ]


def test_verifier_summary_has_no_unclassified_rows() -> None:
    verifier_rows = MODULE.build_verifier_rows(
        candidate_rows=[
            _candidate(),
            _candidate(product_or_segment="North America", row_label="North America"),
            _candidate(metric_family="backlog_or_orders"),
        ],
        generated_at="2026-06-19T00:00:00Z",
    )
    ticker_rows = MODULE.build_ticker_summary_rows(
        verifier_rows=verifier_rows,
        generated_at="2026-06-19T00:00:00Z",
    )
    promotable = [
        row for row in verifier_rows if row["verifier_class"] == "promotable_product_category_or_product_line_metric"
    ]
    summary = MODULE.build_summary(
        verifier_rows=verifier_rows,
        ticker_rows=ticker_rows,
        promotable_rows=promotable,
        target_tickers={"TEST"},
        generated_at="2026-06-19T00:00:00Z",
        output_rows=Path("rows.jsonl"),
        output_ticker_summary=Path("ticker.jsonl"),
        output_promotable=Path("promote.jsonl"),
        output_report=Path("report.md"),
    )

    assert summary["status"] == "pass"
    assert summary["unclassified_candidate_count"] == 0
    assert summary["promotable_product_metric_count"] == 1


def test_sec_segment_orders_backfill_preserves_segment_and_column_binding() -> None:
    html = """
    <html><body>
    <div>Industrial Technologies and Services Segment Results</div>
    <table>
      <tr><td></td><td>Years Ended December 31,</td><td></td><td>Percent Change</td></tr>
      <tr><td>(In millions, except percentages)</td><td>2025</td><td>2024</td><td>2025 vs. 2024</td></tr>
      <tr><td>Segment Orders</td><td>$</td><td>6,119.6</td><td>$</td><td>5,706.6</td><td>7.2</td><td>%</td></tr>
    </table>
    <div>Precision and Science Technologies Segment Results</div>
    <table>
      <tr><td></td><td>Years Ended December 31,</td><td></td><td>Percent Change</td></tr>
      <tr><td>(In millions, except percentages)</td><td>2025</td><td>2024</td><td>2025 vs. 2024</td></tr>
      <tr><td>Segment Orders</td><td>$</td><td>1,596.3</td><td>$</td><td>1,398.9</td><td>14.1</td><td>%</td></tr>
    </table>
    </body></html>
    """
    rows = MODULE.build_verifier_rows(
        candidate_rows=[
            _candidate(
                ticker="IR",
                company="Ingersoll Rand",
                source_url="https://www.sec.gov/Archives/edgar/data/1699150/000162828026008617/iri-20251231.htm",
                _source_html=html,
                fact_id="bad-segment-orders",
                metric_family="backlog_or_orders",
                metric_name="orders",
                product_or_segment="Segment Orders",
                product_node_type="segment",
                row_label="Segment Orders",
                column_label="2025",
                value=5706600000.0,
                citation_span="Segment Results constant currency Segment Orders",
            )
        ],
        generated_at="2026-06-25T00:00:00Z",
    )

    backfilled = [
        row for row in rows if row.get("source_specific_parser") == "sec_segment_results_segment_orders_table_v0_1"
    ]
    assert {(row["product_or_segment"], row["period"], row["value"]) for row in backfilled} >= {
        ("Industrial Technologies and Services", "FY2025", 6119600000.0),
        ("Precision and Science Technologies", "FY2025", 1596300000.0),
    }
    assert all(row["verifier_class"] == "operating_metric_defer_step2" for row in backfilled)


def test_sec_cash_markets_transaction_fee_backfill_promotes_correct_scaled_product_line_rows() -> None:
    html = """
    <html><body>
    <div>Cash Markets Business</div>
    <table>
      <tr><td></td><td></td><td>Year-over-Year Change</td></tr>
      <tr><td>(amounts in millions)</td><td>2025</td><td>2024</td><td>2025-2024</td></tr>
      <tr><td>BrokerTec fixed income transaction fees</td><td>$</td><td>151.1</td><td>$</td><td>145.1</td><td>4</td><td>%</td></tr>
      <tr><td>EBS foreign exchange transaction fees</td><td>132.6</td><td>131.6</td><td>1</td></tr>
    </table>
    </body></html>
    """
    rows = MODULE.build_verifier_rows(
        candidate_rows=[
            _candidate(
                ticker="CME",
                company="CME Group",
                source_url="https://www.sec.gov/Archives/edgar/data/1156375/000115637526000009/cme-20251231.htm",
                _source_html=html,
                fact_id="bad-cash-market-row",
                product_or_segment="EBS Foreign Exchange Transaction Fees",
                row_label="EBS foreign exchange transaction fees",
                column_label="2025",
                value=154100000000.0,
                citation_span="Cash Markets Business Year-over-Year Change",
            )
        ],
        generated_at="2026-06-25T00:00:00Z",
    )

    backfilled = [
        row for row in rows if row.get("source_specific_parser") == "sec_cash_markets_business_transaction_fee_table_v0_1"
    ]
    assert {(row["product_or_segment"], row["period"], row["value"], row["verifier_class"]) for row in backfilled} >= {
        ("BrokerTec fixed income transaction fees", "FY2025", 151100000.0, "promotable_product_category_or_product_line_metric"),
        ("EBS foreign exchange transaction fees", "FY2025", 132600000.0, "promotable_product_category_or_product_line_metric"),
    }
