from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "data_expansion" / "build_v1_macro_official_exposure_context_rows.py"
SPEC = importlib.util.spec_from_file_location("build_v1_macro_official_exposure_context_rows", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_macro_exposure_bridge_uses_latest_official_driver_row() -> None:
    official_rows = [
        {
            "evidence_ref": "fred_old",
            "source_id": "fred_api",
            "source_layer_id": "L2",
            "structured_context_type": "macro_official_context",
            "metric_name": "FEDFUNDS",
            "product_or_segment": "FEDFUNDS",
            "value": 3.6,
            "period": "2026-04-01",
            "api_route": "https://api.stlouisfed.org/fred/series/observations?series_id=FEDFUNDS",
        },
        {
            "evidence_ref": "fred_new",
            "source_id": "fred_api",
            "source_layer_id": "L2",
            "structured_context_type": "macro_official_context",
            "metric_name": "FEDFUNDS",
            "product_or_segment": "FEDFUNDS",
            "value": 3.63,
            "period": "2026-05-01",
            "api_route": "https://api.stlouisfed.org/fred/series/observations?series_id=FEDFUNDS",
        },
    ]

    rows = MODULE.build_v1_macro_official_exposure_context_rows(
        official_rows,
        generated_at="2026-06-17T00:00:00Z",
        tickers=["NVDA"],
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["ticker"] == "NVDA"
    assert row["parent_evidence_ref"] == "fred_new"
    assert row["source_id"] == "fred_api"
    assert row["structured_context_type"] == "macro_official_context"
    assert row["context_scope"] == "v1_company_exposure_to_macro_driver_bridge"
    assert row["issuer_binding_status"] == "macro_exposure_bridge_context"
    assert row["routing_ticker_binding_status"] == "macro_exposure_bridge_not_issuer_fact"
    assert row["exact_value_authority"] is False
    assert "issuer_revenue" in row["forbidden_claims"]


def test_macro_exposure_bridge_coverage_gate_passes() -> None:
    rows = MODULE.build_v1_macro_official_exposure_context_rows(
        [
            {
                "evidence_ref": "fred_new",
                "source_id": "fred_api",
                "metric_name": "FEDFUNDS",
                "product_or_segment": "FEDFUNDS",
                "value": 3.63,
                "period": "2026-05-01",
            }
        ],
        generated_at="2026-06-17T00:00:00Z",
        tickers=["AMD"],
    )
    source_rows = [
        {
            "source_id": "fred_api",
            "layer_id": "L2",
            "evidence_graph_status": "runtime_ready_context",
            "can_crawl_or_download": True,
            "can_structure": True,
            "runtime_ready_context": True,
            "exact_value_authority_ready": False,
            "can_support_company_exact_fact": False,
        }
    ]

    coverage = MODULE.build_v1_macro_official_exposure_coverage_gate(
        context_rows=rows,
        source_layer_rows=source_rows,
        generated_at="2026-06-17T00:00:00Z",
    )
    req = coverage["requirements"][0]
    assert req["requirement_id"] == "macro_official_context"
    assert req["status"] == "pass"
    assert req["parser_row_count"] == 1
