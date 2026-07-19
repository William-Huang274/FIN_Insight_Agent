from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "data_expansion"
    / "build_filing_operating_footprint_context_rows.py"
)
SPEC = importlib.util.spec_from_file_location("build_filing_operating_footprint_context_rows", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_parse_lnt_utility_retail_customer_counts() -> None:
    result = MODULE.build_filing_operating_footprint_context_rows(
        documents=[
            {
                "ticker": "LNT",
                "company": "ALLIANT ENERGY CORP",
                "form_type": "10-K",
                "fiscal_year": 2025,
                "source_url": "https://www.sec.gov/Archives/example/lnt.htm",
                "raw_path": "lnt.htm",
                "html": (
                    "At December 31, 2025, IPL supplied electric and natural gas service to "
                    "approximately 505,000 and 230,000 retail customers, respectively, in Iowa. "
                    "At December 31, 2025, WPL supplied electric and natural gas service to "
                    "approximately 505,000 and 205,000 retail customers, respectively, in Wisconsin."
                ),
            }
        ],
        generated_at="2026-07-01T00:00:00Z",
    )

    rows = result["rows"]
    assert len(rows) == 4
    assert {row["metric_family"] for row in rows} == {"customer_count"}
    assert {row["value"] for row in rows} == {505000.0, 230000.0, 205000.0}
    assert all("not revenue" in row["claim_boundary"] for row in rows)


def test_parse_stld_production_and_shipment_rows() -> None:
    result = MODULE.build_filing_operating_footprint_context_rows(
        documents=[
            {
                "ticker": "STLD",
                "company": "STEEL DYNAMICS INC",
                "form_type": "10-K",
                "fiscal_year": 2025,
                "source_url": "https://www.sec.gov/Archives/example/stld.htm",
                "raw_path": "stld.htm",
                "html": (
                    "We produced 10.0 million tons of sheet steel at these facilities in 2025, "
                    "9.5 million tons in 2024, and 9.2 million tons in 2023. We shipped the following "
                    "volumes of sheet steel products (net tons): 2025 2024 2023 Butler, Columbus, "
                    "and Sinton 8,115,111 7,702,731 7,459,023 Flat Roll divisions Steel Processing "
                    "divisions 2,071,765 1,900,000 1,800,000"
                ),
            }
        ],
        generated_at="2026-07-01T00:00:00Z",
    )

    rows = result["rows"]
    assert len(rows) == 3
    by_metric = {row["metric_name"]: row for row in rows}
    assert by_metric["sheet steel produced"]["value"] == 10_000_000.0
    assert sum(row["value"] for row in rows if row["metric_family"] == "shipments") == 10_186_876.0
    assert all(row["unit"] in {"tons", "net tons"} for row in rows)


def test_parse_bhp_exact_production_table_rows() -> None:
    result = MODULE.build_filing_operating_footprint_context_rows(
        documents=[
            {
                "ticker": "BHP",
                "company": "BHP Group Ltd",
                "form_type": "20-F",
                "fiscal_year": 2025,
                "source_url": "https://www.sec.gov/Archives/example/bhp.htm",
                "raw_path": "bhp.htm",
                "html": (
                    "Year ended 30 June US$M 2025 2024 Revenue 22,530 18,566 "
                    "Total copper production (kt) 2,017 1,865 Average realised prices Copper. "
                    "Year ended 30 June US$M 2025 2024 Revenue 22,919 27,952 "
                    "Total iron ore production (Mt) 263 260 Average realised prices Iron ore."
                ),
            }
        ],
        generated_at="2026-07-01T00:00:00Z",
    )

    rows = result["rows"]
    assert len(rows) == 2
    assert {row["product_or_segment"] for row in rows} == {"copper", "iron ore"}
    assert {row["value"] for row in rows} == {2_017_000.0, 263_000_000.0}
    assert all(row["unit"] == "tonnes" for row in rows)


def test_does_not_materialize_revenue_only_filing_context() -> None:
    result = MODULE.build_filing_operating_footprint_context_rows(
        documents=[
            {
                "ticker": "BAD",
                "company": "Revenue Only Co",
                "form_type": "10-K",
                "fiscal_year": 2025,
                "source_url": "https://www.sec.gov/Archives/example/bad.htm",
                "raw_path": "bad.htm",
                "html": "Revenue was $10 billion and operating income was $2 billion.",
            }
        ],
        generated_at="2026-07-01T00:00:00Z",
    )

    assert result["rows"] == []
    assert result["rejections"][0]["rejection_reason"] == "no_strict_customer_or_operating_footprint_row_found"
