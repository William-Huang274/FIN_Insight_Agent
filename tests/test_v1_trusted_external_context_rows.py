from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "data_expansion" / "build_v1_trusted_external_context_rows.py"
SPEC = importlib.util.spec_from_file_location("build_v1_trusted_external_context_rows", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_v1_trusted_external_rows_are_lane_context_not_issuer_claim(tmp_path: Path) -> None:
    body = """
    <html>
      <head>
        <title>Global Semiconductor Sales Increase 11% Month-to-Month in April</title>
        <meta name="description" content="Worldwide chip sales in April up 93.9% year-to-year.">
      </head>
      <body>
        <p>The Semiconductor Industry Association announced global semiconductor sales increased as AI infrastructure demand remained a market driver.</p>
      </body>
    </html>
    """

    result = MODULE.build_v1_trusted_external_context_rows(
        probes=[
            {
                "provider": "SIA",
                "url": "https://example.org/sia",
                "title": "SIA sales",
                "routing_tickers": ["NVDA", "AMD"],
                "topic_terms": ["semiconductor sales", "AI infrastructure"],
            }
        ],
        generated_at="2026-06-17T00:00:00Z",
        raw_dir=tmp_path,
        timeout_s=2,
        fetch=lambda url, timeout_s: (200, "text/html", body),
    )

    rows = result["rows"]
    assert len(rows) >= 2
    assert {row["ticker"] for row in rows} == {"AMD", "NVDA"}
    row = rows[0]
    assert row["source_id"] == MODULE.SOURCE_ID
    assert row["source_layer_id"] == "L2"
    assert row["structured_context_type"] == "trusted_industry_association_context"
    assert row["context_scope"] == "v1_lane_context_routed_to_representative_ticker"
    assert row["issuer_binding_status"] == "lane_context_not_issuer_bound"
    assert row["routing_ticker_binding_status"] == "lane_context_routing_not_issuer_claim"
    assert row["exact_value_authority"] is False
    assert "issuer_revenue" in row["forbidden_claims"]


def test_v1_trusted_external_coverage_gate_passes_with_parser_rows(tmp_path: Path) -> None:
    body = """
    <html><head><title>Industry report</title></head>
    <body><p>Industry association report says semiconductor equipment billings and market cycle indicators changed.</p></body></html>
    """
    result = MODULE.build_v1_trusted_external_context_rows(
        probes=[
            {
                "provider": "SEMI",
                "url": "https://example.org/semi",
                "title": "SEMI billings",
                "routing_tickers": ["ASML"],
                "topic_terms": ["equipment billings"],
            }
        ],
        generated_at="2026-06-17T00:00:00Z",
        raw_dir=tmp_path,
        fetch=lambda url, timeout_s: (200, "text/html", body),
    )
    source_rows = [
        {
            "source_id": MODULE.SOURCE_ID,
            "layer_id": "L2",
            "evidence_graph_status": "runtime_ready_context",
            "can_crawl_or_download": True,
            "can_structure": True,
            "runtime_ready_context": True,
            "exact_value_authority_ready": False,
            "can_support_company_exact_fact": False,
        }
    ]

    coverage = MODULE.build_v1_trusted_external_coverage_gate(
        context_rows=result["rows"],
        source_layer_rows=source_rows,
        generated_at="2026-06-17T00:00:00Z",
    )
    req = coverage["requirements"][0]
    assert req["requirement_id"] == "trusted_external_context"
    assert req["status"] == "pass"
    assert req["parser_row_count"] >= 1
