from __future__ import annotations

import json
from pathlib import Path

from sec_agent.p33_capital_market_feedback_fixture import (
    CONTRACT_ID,
    RELEASE_DECISION_PASS,
    build_p33_capital_market_feedback_fixture,
    default_p33_capital_market_feedback_fixture_paths,
)
from sec_agent.r53_r60_secondary_market_capital_feedback import default_s8_paths


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )


def seed_s8_fixture(root: Path) -> None:
    paths = default_s8_paths(root)
    market_rows = [
        {
            "ticker": ticker,
            "source_id": "yahoo_chart_price_volume_snapshot",
            "source_role": "market_liquidity_driver",
            "evidence_ref": f"market:{ticker}",
            "period": "2026-06-23",
            "as_of_date": "2026-06-23",
            "source_url": f"https://example.test/chart/{ticker}",
            "value": "100.0",
            "unit": "price",
            "allowed_claims": ["market_liquidity_driver", "market_reaction_context"],
            "forbidden_claims": [
                "company_operating_performance",
                "current_fund_flow_without_flow_source",
                "investment_recommendation",
            ],
            "claim_boundary": "Delayed public market snapshot only; not operating performance or fund flow.",
            "market_reaction": {"return_1d": 0.01, "volatility_3m": 0.2},
            "valuation_context": {"pe_ttm": None, "ev_sales_ttm": None},
            "missing_fields": ["market_cap", "enterprise_value", "pe_ttm"],
        }
        for ticker in ["AAA", "BBB"]
    ]
    capital_rows = [
        {
            "ticker": "AAA",
            "source_id": "sec_annual_debt_footnote_chunk",
            "source_role": "capital_structure_disclosure",
            "object_type": "DebtInstrument",
            "metric_name": "debt_instrument_principal_coupon_maturity",
            "evidence_ref": "AAA_10K_DEBT_NOTE",
            "period": "2025-12-31",
            "filing_date": "2026-02-15",
            "value": "500",
            "unit": "USD millions",
            "coupon": "4.5%",
            "maturity_date": "2030-01-01",
            "allowed_claims": ["capital_structure_fact", "debt_context"],
            "forbidden_claims": ["market_implied_credit_spread_without_market_source", "investment_recommendation"],
            "claim_boundary": "Company-disclosed debt fact only.",
            "exact_value_authority": True,
        },
        {
            "ticker": "BBB",
            "source_id": "sec_ownership_and_13f",
            "source_role": "lagged_ownership_context",
            "object_type": "OwnershipPosition",
            "metric_name": "lagged_holder_position",
            "evidence_ref": "BBB_13F_ROW",
            "period": "2026Q1",
            "filing_date": "2026-05-15",
            "allowed_claims": ["lagged_ownership_context"],
            "forbidden_claims": ["realtime_flow", "current_buying_pressure", "investment_recommendation"],
            "claim_boundary": "Lagged 13F holder context only.",
            "exact_value_authority": False,
        },
        {
            "ticker": "AAA",
            "source_id": "sec_financial_statement_data_sets",
            "source_role": "working_capital_liquidity",
            "object_type": "WorkingCapitalLiquidityMetric",
            "metric_name": "cash_and_current_liabilities",
            "evidence_ref": "AAA_FSD_CASH",
            "period": "2025-12-31",
            "value": "1200",
            "unit": "USD millions",
            "allowed_claims": ["working_capital_liquidity"],
            "forbidden_claims": ["current_fund_flow_without_flow_source", "investment_recommendation"],
            "claim_boundary": "Financial statement liquidity row, not market liquidity.",
            "exact_value_authority": True,
        },
    ]
    sec_rows = [
        {
            "ticker": "AAA",
            "all_tickers": ["AAA"],
            "source_id": "sec_offering_filing_metadata",
            "source_role": "securities_offering_filing_event",
            "event_type": "securities_offering_filing_event",
            "form_type": "S-3ASR",
            "evidence_ref": "sec_event:AAA_S3",
            "filing_date": "2026-03-01",
            "source_url": "https://example.test/sec/AAA/S3",
            "allowed_claims": ["filing_event_existence", "capital_market_event_context"],
            "forbidden_claims": ["offering_amount_without_filing_text_or_xml", "investment_recommendation"],
            "claim_boundary": "SEC metadata proves offering filing event existence only.",
        },
        {
            "ticker": "BBB",
            "all_tickers": ["BBB"],
            "source_id": "sec_schedule_13d_13g_metadata",
            "source_role": "beneficial_ownership_filing_event",
            "event_type": "beneficial_ownership_filing_event",
            "form_type": "SC 13G",
            "evidence_ref": "sec_event:BBB_13G",
            "filing_date": "2026-04-01",
            "source_url": "https://example.test/sec/BBB/13G",
            "allowed_claims": ["filing_event_existence", "beneficial_ownership_context"],
            "forbidden_claims": ["beneficial_ownership_percentage_without_schedule_parser", "realtime_flow"],
            "claim_boundary": "SEC metadata proves 13G filing event existence only.",
        },
    ]
    _write_jsonl(paths.market_rows_path, market_rows)
    _write_jsonl(paths.capital_rows_path, capital_rows)
    _write_jsonl(paths.sec_event_rows_path, sec_rows)


def test_p33_capital_market_feedback_fixture_outputs_l4_scope_pass(tmp_path: Path) -> None:
    seed_s8_fixture(tmp_path)

    manifest = build_p33_capital_market_feedback_fixture(tmp_path)
    paths = default_p33_capital_market_feedback_fixture_paths(tmp_path)

    assert manifest["status"] == "pass"
    assert manifest["contract_id"] == CONTRACT_ID
    assert manifest["release_decision"] == RELEASE_DECISION_PASS
    assert manifest["closeout_level"] == "L4_scope_pass"
    assert manifest["promotion_recommendation"] == "active_registry_ready_runtime_alignment_only"
    assert manifest["gate_fail_count"] == 0
    assert paths.manifest_path.exists()
    assert paths.report_path.exists()
    assert Path(tmp_path / manifest["source_fixture_refs"]["runtime_db"]).exists()


def test_p33_market_proxy_and_lagged_holder_are_not_promoted(tmp_path: Path) -> None:
    seed_s8_fixture(tmp_path)

    manifest = build_p33_capital_market_feedback_fixture(tmp_path)
    signal_audit = manifest["signal_audit"]

    assert signal_audit["market_proxy_row_count"] > 0
    assert signal_audit["market_proxy_boundary_ok_count"] == signal_audit["market_proxy_row_count"]
    assert signal_audit["lagged_positioning_count"] > 0
    assert signal_audit["lagged_positioning_boundary_ok_count"] == signal_audit["lagged_positioning_count"]
    assert "market_proxy_as_fundamental_fact" in manifest["do_not_promote"]
    assert "real_time_flow_claim_from_delayed_public_data" in manifest["do_not_promote"]


def test_p33_typed_gaps_and_graph_edges_are_boundary_backed(tmp_path: Path) -> None:
    seed_s8_fixture(tmp_path)

    manifest = build_p33_capital_market_feedback_fixture(tmp_path)

    assert manifest["gap_audit"]["status"] == "pass"
    assert manifest["gap_audit"]["gap_count"] > 0
    assert manifest["gap_audit"]["complete_gap_count"] == manifest["gap_audit"]["gap_count"]
    assert manifest["graph_audit"]["status"] == "pass"
    assert manifest["graph_audit"]["edge_count"] > 0
    assert manifest["graph_audit"]["backed_edge_count"] == manifest["graph_audit"]["edge_count"]
    assert manifest["graph_audit"]["boundary_ready_edge_count"] == manifest["graph_audit"]["edge_count"]


def test_p33_judgment_material_is_writer_ready_and_bounded(tmp_path: Path) -> None:
    seed_s8_fixture(tmp_path)

    manifest = build_p33_capital_market_feedback_fixture(tmp_path)
    material = manifest["judgment_material"]

    assert material
    assert {row["judgment_role"] for row in material}
    for row in material:
        assert row["ticker"]
        assert row["thesis_driver_scope"]
        assert row["writer_instruction"]
        assert row["forbidden_claims"]
        assert row["evidence_refs"] or row["gap_refs"]
        assert row["promoted_to_fundamental_fact"] is False
        assert "investment_recommendation" in row["forbidden_claims"] or row["cannot_promote_to"]


def test_p33_fixture_can_reuse_existing_s8_outputs_without_rebuild(tmp_path: Path) -> None:
    seed_s8_fixture(tmp_path)
    first = build_p33_capital_market_feedback_fixture(tmp_path, rebuild_dependencies=True)
    db_path = default_s8_paths(tmp_path).db_path

    second = build_p33_capital_market_feedback_fixture(tmp_path, rebuild_dependencies=False)

    assert db_path.exists()
    assert first["release_decision"] == RELEASE_DECISION_PASS
    assert second["release_decision"] == RELEASE_DECISION_PASS
