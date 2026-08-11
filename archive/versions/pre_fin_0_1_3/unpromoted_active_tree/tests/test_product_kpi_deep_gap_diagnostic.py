from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "data_expansion" / "build_product_kpi_deep_gap_diagnostic.py"
SPEC = importlib.util.spec_from_file_location("build_product_kpi_deep_gap_diagnostic", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_product_kpi_deep_gap_diagnostic_distinguishes_parser_candidates_from_no_candidates() -> None:
    rows = MODULE.build_product_kpi_deep_gap_diagnostic_rows(
        closeout_rows=[
            {"ticker": "AAPL", "company_name": "Apple", "status": "product_kpi_exact_ready"},
            {"ticker": "ABT", "company_name": "Abbott", "status": "product_kpi_exact_gap", "official_surface_slot_count": 1},
            {"ticker": "2330.TW", "company_name": "TSMC", "status": "product_kpi_exact_gap", "official_surface_slot_count": 1},
            {"ticker": "373220.KS", "company_name": "LG Energy Solution", "status": "product_kpi_exact_gap", "official_surface_slot_count": 1},
            {"ticker": "XYZ", "company_name": "No Candidate", "status": "product_kpi_exact_gap"},
        ],
        runtime_rows=[
            {"ticker": "AAPL", "product_node_type": "product_family", "product_or_segment": "iPhone"},
            {
                "ticker": "373220.KS",
                "product_node_type": "product_family",
                "product_or_segment": "ESS batteries",
                "metric_family": "backlog_or_orders",
                "value": 120,
                "unit": "GWH",
            },
        ],
        strict_candidate_rows=[
            {
                "ticker": "ABT",
                "product_or_segment": "Key Emerging Markets",
                "product_node_type": "segment",
                "metric_family": "product_revenue",
                "value": 10,
                "unit": "USD",
                "period": "FY2024",
            }
        ],
        final_closeout_rows=[
            {
                "ticker": "ABT",
                "closeout_reason": "geographic_revenue_context_requires_region_gate",
                "product_or_segment": "Key Emerging Markets",
            }
        ],
        generated_at="2026-06-19T00:00:00Z",
    )

    by_ticker = {row["ticker"]: row for row in rows}
    assert by_ticker["AAPL"]["diagnostic_class"] == "ready_product_kpi_exact"
    assert by_ticker["ABT"]["diagnostic_class"] == "parser_candidate_found_but_not_runtime_promotable"
    assert by_ticker["ABT"]["diagnostic_reason"].endswith("geographic_revenue_context_requires_region_gate")
    assert by_ticker["2330.TW"]["diagnostic_class"] == "non_us_local_or_ir_parser_required"
    assert by_ticker["373220.KS"]["product_kpi_status"] == "product_kpi_exact_ready"
    assert by_ticker["373220.KS"]["source_product_kpi_closeout_status"] == "product_kpi_exact_gap"
    assert by_ticker["373220.KS"]["diagnostic_class"] == "ready_product_kpi_exact"
    assert by_ticker["XYZ"]["diagnostic_class"] == "no_product_kpi_candidate_in_current_public_scan"


def test_product_kpi_deep_gap_diagnostic_runtime_product_row_ignores_citation_geography_terms() -> None:
    rows = MODULE.build_product_kpi_deep_gap_diagnostic_rows(
        closeout_rows=[
            {"ticker": "CF", "company_name": "CF Industries", "status": "product_kpi_exact_ready"},
        ],
        runtime_rows=[
            {
                "ticker": "CF",
                "product_node_type": "product_family",
                "product_or_segment": "Ammonia",
                "metric_family": "product_revenue",
                "metric_name": "product revenue",
                "value": 3546000000,
                "unit": "USD",
                "period": "FY2023",
                "citation_span": "Our Products table mentions United States production facilities and Ammonia revenue.",
            }
        ],
        strict_candidate_rows=[],
        final_closeout_rows=[],
        generated_at="2026-06-21T00:00:00Z",
    )

    assert rows[0]["product_kpi_status"] == "product_kpi_exact_ready"
    assert rows[0]["diagnostic_class"] == "ready_product_kpi_exact"


def test_product_kpi_deep_gap_diagnostic_uses_source_specific_verifier_class() -> None:
    rows = MODULE.build_product_kpi_deep_gap_diagnostic_rows(
        closeout_rows=[
            {"ticker": "REGN", "company_name": "Regeneron", "status": "product_kpi_exact_gap"},
            {"ticker": "AEP", "company_name": "AEP", "status": "product_kpi_exact_gap"},
        ],
        runtime_rows=[],
        strict_candidate_rows=[
            {"ticker": "REGN", "product_or_segment": "EYLEA", "product_node_type": "product_or_therapy_family"},
            {"ticker": "AEP", "product_or_segment": "Ohio", "product_node_type": "segment"},
        ],
        final_closeout_rows=[],
        verifier_ticker_summary_rows=[
            {
                "ticker": "REGN",
                "candidate_count": 4,
                "verifier_class_counts": {"percentage_or_change": 3, "sentence_relation_insufficient": 1},
                "verifier_decision_counts": {"reject": 3, "classify_only": 1},
                "top_verifier_reasons": {"not_currency_revenue_or_raw_percent": 3},
            },
            {
                "ticker": "AEP",
                "candidate_count": 5,
                "verifier_class_counts": {"business_segment_mixed_table_needs_column_group": 5},
                "verifier_decision_counts": {"classify_only": 5},
                "top_verifier_reasons": {"segment_table_contains_mixed_financial_columns": 5},
            },
        ],
        generated_at="2026-06-19T00:00:00Z",
    )

    by_ticker = {row["ticker"]: row for row in rows}
    assert by_ticker["REGN"]["diagnostic_class"] == "verifier_percentage_or_change_only_candidates"
    assert by_ticker["REGN"]["dominant_verifier_class"] == "percentage_or_change"
    assert by_ticker["AEP"]["diagnostic_class"] == "verifier_business_segment_column_group_required"
    assert by_ticker["AEP"]["source_specific_verifier_class_counts"] == {
        "business_segment_mixed_table_needs_column_group": 5
    }


def test_product_kpi_deep_gap_summary_counts_are_auditable() -> None:
    rows = [
        {"ticker": "A", "product_kpi_status": "product_kpi_exact_ready", "diagnostic_class": "ready_product_kpi_exact"},
        {
            "ticker": "B",
            "product_kpi_status": "product_kpi_exact_gap",
            "diagnostic_class": "parser_candidate_found_but_not_runtime_promotable",
            "strict_candidate_count": 2,
            "diagnostic_reason": "strict_product_candidates_need_local_citation_or_period_table_verifier",
        },
        {
            "ticker": "C",
            "product_kpi_status": "product_kpi_exact_gap",
            "diagnostic_class": "no_product_kpi_candidate_in_current_public_scan",
            "strict_candidate_count": 0,
            "diagnostic_reason": "no_company_disclosed_product_kpi_candidate_in_current_sec_or_public_disclosure_scan",
        },
    ]
    summary = MODULE.build_summary(
        rows=rows,
        generated_at="2026-06-19T00:00:00Z",
        output_rows=Path("rows.jsonl"),
        output_report=Path("report.md"),
    )

    assert summary["status"] == "pass"
    assert summary["strict_candidate_gap_ticker_count"] == 1
    assert summary["no_candidate_gap_ticker_count"] == 1
