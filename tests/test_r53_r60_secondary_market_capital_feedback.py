from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from sec_agent.r53_r60_secondary_market_capital_feedback import (
    PACK_ROLES,
    S8_TASK_ID,
    build_s8_gate,
    default_s8_paths,
    secondary_market_schema_contract,
)
from sec_agent.r53_r60_runtime_task_spine import json_loads


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n", encoding="utf-8")


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
    write_jsonl(paths.market_rows_path, market_rows)
    write_jsonl(paths.capital_rows_path, capital_rows)
    write_jsonl(paths.sec_event_rows_path, sec_rows)


def test_build_s8_gate_outputs_l4_scope_pass(tmp_path: Path) -> None:
    seed_s8_fixture(tmp_path)

    summary = build_s8_gate(tmp_path)

    assert summary["release_decision"] == "S8_L4_scope_pass"
    assert summary["closeout_level"] == "L4_scope_pass"
    assert summary["counts"]["gate_count"] == 10
    assert summary["counts"]["gate_fail_count"] == 0
    assert summary["counts"]["pack_count"] == 2
    assert summary["role_gap_counts"]["derivatives_market_signal"] == 2
    assert (tmp_path / summary["outputs"]["schema"]).exists()
    assert (tmp_path / summary["outputs"]["gate_rows"]).exists()
    assert (tmp_path / summary["outputs"]["summary"]).exists()
    assert (tmp_path / summary["outputs"]["closeout_report"]).exists()


def test_s8_source_registry_and_pack_boundaries(tmp_path: Path) -> None:
    seed_s8_fixture(tmp_path)
    build_s8_gate(tmp_path)
    db_path = default_s8_paths(tmp_path).db_path

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        tables = {row["name"] for row in conn.execute("select name from sqlite_master where type='table'").fetchall()}
        registry = {
            row["source_id"]: dict(row)
            for row in conn.execute("select * from secondary_market_source_registry_s8").fetchall()
        }
        packs = conn.execute("select * from capital_feedback_packs_s8 order by ticker").fetchall()

    assert set(secondary_market_schema_contract()["tables"]).issubset(tables)
    assert set(PACK_ROLES).issubset({row["pack_role"] for row in registry.values()})
    assert registry["sec_ownership_and_13f"]["authority_class"] == "lagged_positioning_context"
    assert "realtime_flow" in json_loads(registry["sec_ownership_and_13f"]["forbidden_claims_json"], [])
    assert registry["derivatives_public_sources_planned"]["lifecycle_status"] == "public_boundary"
    assert len(packs) == 2
    for pack in packs:
        role_counts = json_loads(pack["role_counts_json"], {})
        assert role_counts["secondary_market_capital_flow"] >= 1
        assert role_counts["liquidity_and_positioning"] >= 1
        assert json_loads(pack["gap_refs_json"], {})["derivatives_market_signal"]


def test_s8_signals_gaps_edges_and_workpaper_event_are_bounded(tmp_path: Path) -> None:
    seed_s8_fixture(tmp_path)
    build_s8_gate(tmp_path)
    db_path = default_s8_paths(tmp_path).db_path

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        signals = conn.execute("select * from capital_feedback_signals_s8").fetchall()
        lagged = conn.execute(
            "select * from capital_feedback_signals_s8 where authority_class = 'lagged_positioning_context'"
        ).fetchall()
        derivative_signals = conn.execute(
            "select count(*) from capital_feedback_signals_s8 where pack_role = 'derivatives_market_signal'"
        ).fetchone()[0]
        derivative_gaps = conn.execute(
            "select count(*) from capital_feedback_gap_items_s8 where pack_role = 'derivatives_market_signal'"
        ).fetchone()[0]
        graph_bad = conn.execute(
            "select count(*) from capital_feedback_graph_edges_s8 where evidence_refs_json = '[]' and gap_refs_json = '[]'"
        ).fetchone()[0]
        event_count = conn.execute(
            """
            select count(*) from workpaper_events
            where task_id = ? and event_type = 'secondary_market_capital_feedback_pack_ready'
            """,
            (S8_TASK_ID,),
        ).fetchone()[0]

    assert signals
    assert all(row["claim_boundary"] and json_loads(row["forbidden_claims_json"], []) for row in signals)
    assert lagged
    assert all("realtime" in row["forbidden_claims_json"] for row in lagged)
    assert derivative_signals == 0
    assert derivative_gaps == 2
    assert graph_bad == 0
    assert event_count == 1


def test_s8_rerun_is_idempotent_for_current_projection(tmp_path: Path) -> None:
    seed_s8_fixture(tmp_path)
    first = build_s8_gate(tmp_path)
    second = build_s8_gate(tmp_path)
    db_path = default_s8_paths(tmp_path).db_path

    with sqlite3.connect(db_path) as conn:
        pack_count = conn.execute("select count(*) from capital_feedback_packs_s8 where task_id = ?", (S8_TASK_ID,)).fetchone()[0]
        event_count = conn.execute(
            "select count(*) from workpaper_events where task_id = ? and event_type = 'secondary_market_capital_feedback_pack_ready'",
            (S8_TASK_ID,),
        ).fetchone()[0]

    assert first["release_decision"] == "S8_L4_scope_pass"
    assert second["release_decision"] == "S8_L4_scope_pass"
    assert pack_count == 2
    assert event_count == 2
