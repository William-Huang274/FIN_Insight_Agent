from __future__ import annotations

import json
from pathlib import Path

from sec_agent.layer_acceptance_gates import build_second_third_layer_depth_parity_matrix
from sec_agent.market_snapshot import build_market_liquidity_driver_context_rows


def test_market_evidence_pack_projects_to_market_liquidity_runtime_rows(tmp_path: Path) -> None:
    evidence_path = tmp_path / "market_evidence.jsonl"
    output_path = tmp_path / "market_liquidity_driver_context_rows.jsonl"
    summary_path = tmp_path / "market_liquidity_driver_context_summary.json"
    evidence_path.write_text(
        json.dumps(
            {
                "schema_version": "sec_agent_market_evidence_pack_v0.1",
                "evidence_id": "MARKET_SNAPSHOT::unit::NVDA::3M::2026-06-24",
                "ticker": "NVDA",
                "as_of_date": "2026-06-24",
                "snapshot_id": "unit",
                "provider": "yahoo_finance_chart_unofficial",
                "window": "3M",
                "market_reaction": {
                    "return_3m": 0.12,
                    "relative_return_vs_benchmark_3m": 0.03,
                    "max_drawdown_3m": -0.08,
                    "volatility_3m": 0.32,
                },
                "valuation_context": {"ev_sales_ttm": 18.0},
                "derived_signals": ["outperformed_benchmark_3m"],
                "field_refs": [
                    {
                        "field_ref": "MARKET::unit::NVDA::return_3m::2026-06-24",
                        "field_name": "return_3m",
                        "value": 0.12,
                    }
                ],
                "source_boundary": "market_snapshot; non-real-time; as_of_date=2026-06-24",
                "text": "NVDA market snapshot as of 2026-06-24.",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    summary = build_market_liquidity_driver_context_rows(
        market_evidence_path=evidence_path,
        output_path=output_path,
        summary_path=summary_path,
    )
    rows = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]

    assert summary["status"] == "pass"
    assert summary["ticker_count"] == 1
    assert rows[0]["source_role"] == "market_liquidity_driver"
    assert rows[0]["parser_status"] == "market_evidence_pack_projector_pass"
    assert rows[0]["source_specific_parser"]
    assert rows[0]["claim_boundary"]
    assert rows[0]["source_url"].startswith("https://query1.finance.yahoo.com/v8/finance/chart/NVDA")

    depth = build_second_third_layer_depth_parity_matrix(
        company_universe_rows=[{"ticker": "NVDA"}],
        product_kpi_closeout_rows=[{"ticker": "NVDA", "status": "product_kpi_exact_gap"}],
        product_kpi_rows=[],
        product_spec_rows=[],
        customer_deployment_rows=[],
        capital_market_rows=[],
        market_liquidity_rows=[{**rows[0], "_source_file": "market_liquidity_driver_context_rows_v0_1.jsonl"}],
        company_count=1,
    )
    assert depth["company_rows"][0]["dimensions"]["market_liquidity_depth"]["target_depth_met"] is True
