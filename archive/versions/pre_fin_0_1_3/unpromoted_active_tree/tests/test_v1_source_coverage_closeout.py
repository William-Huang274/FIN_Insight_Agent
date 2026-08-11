from __future__ import annotations

from sec_agent.vertical_source_lane_closeout import build_v1_source_coverage_closeout


def test_v1_source_closeout_uses_runtime_rows_to_resolve_registry_product_surface_gap() -> None:
    payload = build_v1_source_coverage_closeout(
        v1_coverage=_coverage(),
        source_layer_capability_rows=[
            _source("sec_edgar_apis", "L1", "exact_authority_ready", exact=True),
            _source("company_reported_product_operating_metrics", "L1", "structured_not_promoted"),
            _source("company_product_pages", "L2", "structured_not_promoted", can_structure=True),
            _source("mainstream_financial_news", "L2", "runtime_ready_context"),
            _source("supplier_customer_official_news", "L2", "runtime_ready_context"),
            _source("public_tenders_contracts_orders", "L3", "runtime_ready_context"),
            _source("developer_ecosystem_github_npm_pypi_huggingface", "L3", "runtime_ready_context"),
            _source("channel_pricing_quotations", "L3", "runtime_ready_context"),
            _source("job_postings_hiring_signals", "L3", "runtime_ready_context"),
            _source("fred_api", "L2", "runtime_ready_context"),
            _source("openalex_api", "L3", "structured_not_promoted", can_structure=True),
            _source("patentsview_api", "L3", "structured_not_promoted", can_structure=True),
        ],
        observed_rows=[
            _row("company_reported_product_operating_metrics", "NVDA", "L1", issuer=True, product=True),
            _row("company_product_pages", "NVDA", "L2", source_class="company_product_page", issuer=True, product=True),
            _row("developer_ecosystem_github_npm_pypi_huggingface", "NVDA", "L3", issuer=True, product=True),
            _row("channel_pricing_quotations", "DELL", "L3", source_class="channel_pricing_snapshot", issuer=True, product=True),
        ],
        generated_at="2026-06-17T00:00:00Z",
    )

    by_req = {row["requirement_id"]: row for row in payload["requirement_closeouts"]}
    assert payload["status"] == "gap"
    assert payload["validation"]["status"] == "pass"
    assert by_req["official_product_surface"]["closeout_status"] == "pass"
    assert by_req["official_product_surface"]["registry_status"] == "gap"
    assert by_req["technology_research_proxy"]["closeout_status"] != "pass"
    assert any(gap["requirement_id"] == "technology_research_proxy" for gap in payload["source_gap_ledger"])
    assert payload["commercial_gap_ledger"]


def test_v1_source_closeout_fails_non_l1_exact_authority_rows() -> None:
    payload = build_v1_source_coverage_closeout(
        v1_coverage=_coverage(),
        source_layer_capability_rows=[
            _source("sec_edgar_apis", "L1", "exact_authority_ready", exact=True),
            _source("company_product_pages", "L2", "runtime_ready_context"),
            _source("mainstream_financial_news", "L2", "runtime_ready_context"),
            _source("fred_api", "L2", "runtime_ready_context"),
        ],
        observed_rows=[
            {
                **_row("company_product_pages", "NVDA", "L2", source_class="company_product_page", issuer=True, product=True),
                "exact_value_authority": True,
            }
        ],
        generated_at="2026-06-17T00:00:00Z",
    )

    assert payload["status"] == "fail"
    assert payload["validation"]["status"] == "fail"
    assert payload["validation"]["errors"][0]["type"] == "runtime_gate_exact_authority_violation"


def _coverage() -> dict[str, object]:
    return {
        "lane_id": "V1",
        "lane_name": "Semiconductors / AI Infrastructure",
        "primary_ticker_universe": ["NVDA", "DELL"],
        "ticker_universe": ["NVDA", "DELL", "MSFT"],
        "expected_commercial_gaps": ["shipments/share/forecast", "channel inventory"],
        "gap_summary": {"commercial_sources_top": {"IDC": 2}},
        "lane_source_coverage_gate": {
            "status": "gap",
            "requirements": [
                {"requirement_id": "official_product_surface", "status": "gap"},
                {"requirement_id": "technology_research_proxy", "status": "gap"},
            ],
        },
    }


def _source(source_id: str, layer_id: str, status: str, *, exact: bool = False, can_structure: bool = False) -> dict[str, object]:
    return {
        "source_id": source_id,
        "layer_id": layer_id,
        "evidence_graph_status": status,
        "runtime_ready_context": status in {"runtime_ready_context", "exact_authority_ready"},
        "exact_value_authority_ready": exact,
        "can_support_company_exact_fact": exact,
        "can_crawl_or_download": can_structure or status != "not_registered",
        "can_structure": can_structure or status in {"runtime_ready_context", "exact_authority_ready", "structured_not_promoted"},
    }


def _row(
    source_id: str,
    ticker: str,
    layer_id: str,
    *,
    source_class: str = "",
    issuer: bool = False,
    product: bool = False,
) -> dict[str, object]:
    return {
        "evidence_ref": f"ev:{ticker}:{source_id}",
        "ticker": ticker,
        "source_id": source_id,
        "source_class": source_class,
        "source_layer_id": layer_id,
        "bounded_structured_context": True,
        "source_specific_parser": "test_parser",
        "structured_context_type": "context_fact",
        "structured_fact_status": "exact_fact_materialized" if layer_id == "L1" else "bounded_context_fact_materialized",
        "issuer_binding_status": "issuer_mentioned_in_snapshot" if issuer else "not_bound",
        "product_binding_status": "product_mentioned_in_snapshot" if product else "not_bound",
        "counterparty_binding_status": "not_bound",
        "exact_value_authority": layer_id == "L1",
    }
