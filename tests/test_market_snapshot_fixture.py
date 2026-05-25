from __future__ import annotations

import csv
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.market_snapshot import (  # noqa: E402
    build_market_evidence_pack,
    build_market_snapshot_catalog,
    compute_market_analytics,
    normalize_market_snapshot_fixture,
    validate_market_snapshot,
)


def _write_fixture(path: Path) -> None:
    tickers = {
        "NVDA": {"base": 100.0, "daily": 0.0030, "ev_sales": 22.0, "pe": 48.0},
        "MSFT": {"base": 250.0, "daily": 0.0016, "ev_sales": 12.0, "pe": 34.0},
        "JPM": {"base": 180.0, "daily": -0.0003, "ev_sales": 4.0, "pe": 13.0},
        "SPY": {"base": 500.0, "daily": 0.0009, "ev_sales": None, "pe": None},
    }
    start = date(2026, 2, 25)
    fields = [
        "ticker",
        "date",
        "open",
        "high",
        "low",
        "close",
        "adjusted_close",
        "volume",
        "market_cap",
        "enterprise_value",
        "pe_ttm",
        "ev_sales_ttm",
        "ev_ebitda_ttm",
        "currency",
        "provider",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for offset in range(90):
            row_date = start + timedelta(days=offset)
            for ticker, cfg in tickers.items():
                close = cfg["base"] * (1.0 + cfg["daily"] * offset)
                market_cap = close * 1_000_000_000 if ticker != "SPY" else ""
                enterprise_value = close * 1_100_000_000 if ticker != "SPY" else ""
                writer.writerow(
                    {
                        "ticker": ticker,
                        "date": row_date.isoformat(),
                        "open": close * 0.995,
                        "high": close * 1.005,
                        "low": close * 0.990,
                        "close": close,
                        "adjusted_close": close,
                        "volume": 1_000_000 + offset,
                        "market_cap": market_cap,
                        "enterprise_value": enterprise_value,
                        "pe_ttm": cfg["pe"] or "",
                        "ev_sales_ttm": cfg["ev_sales"] or "",
                        "ev_ebitda_ttm": (cfg["ev_sales"] * 4.0) if cfg["ev_sales"] else "",
                        "currency": "USD",
                        "provider": "unit_fixture",
                    }
                )


def _jsonl_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_market_snapshot_fixture_duckdb_analytics_and_evidence(tmp_path: Path) -> None:
    fixture_path = tmp_path / "market_fixture.csv"
    output_root = tmp_path / "processed_market"
    snapshot_id = "market_pilot_2026-05-25_unit_v1"
    _write_fixture(fixture_path)

    normalize_summary = normalize_market_snapshot_fixture(
        input_path=fixture_path,
        output_root=output_root,
        snapshot_id=snapshot_id,
        as_of_date="2026-05-25",
        provider="unit_fixture",
        tickers=["NVDA", "MSFT", "JPM"],
        benchmark_tickers=["SPY"],
    )

    bars_path = output_root / "bars" / f"{snapshot_id}_daily_bars.jsonl"
    snapshot_path = output_root / "snapshots" / f"{snapshot_id}_snapshot.jsonl"
    assert normalize_summary["bar_count"] == 360
    assert normalize_summary["snapshot_count"] == 3
    assert bars_path.exists()
    assert bars_path.with_suffix(".parquet").exists()
    assert snapshot_path.exists()
    assert snapshot_path.with_suffix(".parquet").exists()

    analytics_path = output_root / "analytics" / f"{snapshot_id}_3m_analytics.jsonl"
    analytics_summary = compute_market_analytics(
        bars_path=bars_path,
        snapshot_path=snapshot_path,
        output_path=analytics_path,
        window="3M",
        benchmark_ticker="SPY",
        tickers=["NVDA", "MSFT", "JPM"],
    )
    analytics_rows = {row["ticker"]: row for row in _jsonl_rows(analytics_path)}
    assert analytics_summary["analytics_count"] == 3
    assert analytics_path.with_suffix(".parquet").exists()
    assert analytics_rows["NVDA"]["market_reaction"]["return_3m"] is not None
    assert analytics_rows["NVDA"]["market_reaction"]["relative_return_vs_benchmark_3m"] is not None
    assert analytics_rows["NVDA"]["valuation_context"]["peer_ev_sales_bucket"] == "upper_middle"
    assert "outperformed_benchmark_3m" in analytics_rows["NVDA"]["derived_signals"]

    catalog_summary = build_market_snapshot_catalog(
        output_root=output_root,
        catalog_path=output_root / "catalog.duckdb",
    )
    assert catalog_summary["table_counts"]["market_daily_bars"] == 360
    assert catalog_summary["table_counts"]["market_snapshots"] == 3
    assert catalog_summary["table_counts"]["market_analytics"] == 3

    evidence_path = output_root / "evidence_packs" / f"{snapshot_id}_3m_market_evidence.jsonl"
    evidence_summary = build_market_evidence_pack(
        analytics_path=analytics_path,
        snapshot_path=snapshot_path,
        output_path=evidence_path,
        tickers=["NVDA", "MSFT", "JPM"],
    )
    evidence_rows = _jsonl_rows(evidence_path)
    assert evidence_summary["row_count"] == 3
    assert evidence_rows[0]["source_tier"] == "market_snapshot"
    assert evidence_rows[0]["field_refs"]
    assert "as_of_date=2026-05-25" in evidence_rows[0]["source_boundary"]
    assert "daily_bars" not in evidence_rows[0]

    validation = validate_market_snapshot(
        snapshot_path=snapshot_path,
        analytics_path=analytics_path,
    )
    assert validation["can_enter_market_snapshot_chain"] is True
    assert validation["error_count"] == 0


def test_market_snapshot_fixture_rejects_duplicate_ticker_date(tmp_path: Path) -> None:
    fixture_path = tmp_path / "duplicate_fixture.csv"
    rows = [
        {
            "ticker": "NVDA",
            "date": "2026-05-25",
            "close": "100",
            "adjusted_close": "100",
            "volume": "1000",
        },
        {
            "ticker": "NVDA",
            "date": "2026-05-25",
            "close": "101",
            "adjusted_close": "101",
            "volume": "1001",
        },
    ]
    with fixture_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["ticker", "date", "close", "adjusted_close", "volume"])
        writer.writeheader()
        writer.writerows(rows)

    with pytest.raises(ValueError, match="duplicate_ticker_date"):
        normalize_market_snapshot_fixture(
            input_path=fixture_path,
            output_root=tmp_path / "processed_market",
            snapshot_id="market_pilot_duplicate_unit_v1",
            as_of_date="2026-05-25",
            tickers=["NVDA"],
        )
