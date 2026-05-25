from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import date, timedelta
from pathlib import Path
from typing import Any


DEFAULT_TICKERS = ("MSFT", "NVDA", "JPM", "CVX", "PG", "LLY", "WMT")
DEFAULT_BENCHMARK = "SPY"

TICKER_PROFILES: dict[str, dict[str, float]] = {
    "MSFT": {"base": 405.0, "daily": 0.0012, "wave": 0.006, "market_cap": 3_050_000_000_000, "pe": 34.0, "ev_sales": 12.2, "ev_ebitda": 23.5},
    "NVDA": {"base": 890.0, "daily": 0.0028, "wave": 0.014, "market_cap": 2_200_000_000_000, "pe": 48.0, "ev_sales": 22.6, "ev_ebitda": 36.0},
    "AMZN": {"base": 185.0, "daily": 0.0011, "wave": 0.007, "market_cap": 1_940_000_000_000, "pe": 39.0, "ev_sales": 3.4, "ev_ebitda": 18.0},
    "GOOGL": {"base": 165.0, "daily": 0.0009, "wave": 0.006, "market_cap": 2_080_000_000_000, "pe": 26.0, "ev_sales": 6.5, "ev_ebitda": 17.0},
    "JPM": {"base": 190.0, "daily": 0.0004, "wave": 0.004, "market_cap": 560_000_000_000, "pe": 12.5, "ev_sales": 3.8, "ev_ebitda": 8.5},
    "CVX": {"base": 152.0, "daily": -0.0001, "wave": 0.007, "market_cap": 290_000_000_000, "pe": 14.1, "ev_sales": 1.4, "ev_ebitda": 6.2},
    "PG": {"base": 164.0, "daily": 0.0003, "wave": 0.003, "market_cap": 390_000_000_000, "pe": 24.8, "ev_sales": 4.7, "ev_ebitda": 16.0},
    "LLY": {"base": 760.0, "daily": 0.0015, "wave": 0.010, "market_cap": 720_000_000_000, "pe": 55.0, "ev_sales": 18.5, "ev_ebitda": 39.0},
    "WMT": {"base": 68.0, "daily": 0.0006, "wave": 0.003, "market_cap": 545_000_000_000, "pe": 29.0, "ev_sales": 0.9, "ev_ebitda": 14.2},
    "SPY": {"base": 525.0, "daily": 0.0007, "wave": 0.004, "market_cap": 0.0, "pe": 0.0, "ev_sales": 0.0, "ev_ebitda": 0.0},
}


def _split_csv(value: str | None) -> list[str]:
    return [item.strip().upper() for item in (value or "").split(",") if item.strip()]


def _date(value: str) -> date:
    return date.fromisoformat(str(value))


def _price(profile: dict[str, float], offset: int) -> float:
    trend = 1.0 + profile["daily"] * offset
    wave = 1.0 + profile["wave"] * math.sin(offset / 6.0)
    return max(1.0, profile["base"] * trend * wave)


def _profile_for(ticker: str) -> dict[str, float]:
    if ticker not in TICKER_PROFILES:
        raise ValueError(f"Unsupported synthetic fixture ticker: {ticker}")
    return TICKER_PROFILES[ticker]


def _write_fixture(
    *,
    output: Path,
    snapshot_id: str,
    as_of_date: date,
    tickers: list[str],
    benchmark_ticker: str,
    start_date: date,
    days: int,
    provider: str,
) -> int:
    output.parent.mkdir(parents=True, exist_ok=True)
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
        "source_url",
    ]
    row_count = 0
    all_tickers = [*tickers, benchmark_ticker]
    with output.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for offset in range(days):
            row_date = start_date + timedelta(days=offset)
            if row_date > as_of_date:
                break
            for ticker in all_tickers:
                profile = _profile_for(ticker)
                close = _price(profile, offset)
                is_benchmark = ticker == benchmark_ticker
                market_cap = "" if is_benchmark else profile["market_cap"] * (close / profile["base"])
                enterprise_value = "" if is_benchmark else market_cap * 1.08
                writer.writerow(
                    {
                        "ticker": ticker,
                        "date": row_date.isoformat(),
                        "open": round(close * 0.996, 6),
                        "high": round(close * 1.006, 6),
                        "low": round(close * 0.991, 6),
                        "close": round(close, 6),
                        "adjusted_close": round(close, 6),
                        "volume": int(1_000_000 + offset * 1200 + (sum(ord(ch) for ch in ticker) * 97)),
                        "market_cap": round(market_cap, 2) if market_cap != "" else "",
                        "enterprise_value": round(enterprise_value, 2) if enterprise_value != "" else "",
                        "pe_ttm": profile["pe"] if not is_benchmark else "",
                        "ev_sales_ttm": profile["ev_sales"] if not is_benchmark else "",
                        "ev_ebitda_ttm": profile["ev_ebitda"] if not is_benchmark else "",
                        "currency": "USD",
                        "provider": provider,
                        "source_url": f"synthetic://{snapshot_id}/{ticker}",
                    }
                )
                row_count += 1
    return row_count


def _write_events(*, output: Path, tickers: list[str]) -> int:
    output.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for ticker in tickers:
        rows.append({"ticker": ticker, "event_type": "8k_earnings_release", "event_date": "2026-05-10", "source": "synthetic_fixture"})
        rows.append({"ticker": ticker, "event_type": "latest_10q_filing", "event_date": "2026-05-12", "source": "synthetic_fixture"})
    with output.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["ticker", "event_type", "event_date", "source"])
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def _default_output(snapshot_id: str) -> Path:
    return Path("data/raw_private/market/fixtures") / f"{snapshot_id}_daily_fixture.csv"


def _default_events(snapshot_id: str) -> Path:
    return Path("data/raw_private/market/fixtures") / f"{snapshot_id}_events.csv"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a deterministic 7-company offline market snapshot fixture.")
    parser.add_argument("--snapshot-id", default="market_pilot_2026-05-25_7co_v1")
    parser.add_argument("--as-of-date", default="2026-05-25")
    parser.add_argument("--tickers", default=",".join(DEFAULT_TICKERS))
    parser.add_argument("--benchmark-ticker", default=DEFAULT_BENCHMARK)
    parser.add_argument("--start-date", default="2026-02-20")
    parser.add_argument("--days", type=int, default=96)
    parser.add_argument("--provider", default="synthetic_local_fixture")
    parser.add_argument("--output", default="")
    parser.add_argument("--events-output", default="")
    args = parser.parse_args()

    tickers = _split_csv(args.tickers)
    benchmark_ticker = str(args.benchmark_ticker or DEFAULT_BENCHMARK).strip().upper()
    for ticker in [*tickers, benchmark_ticker]:
        _profile_for(ticker)
    snapshot_id = str(args.snapshot_id)
    output = Path(args.output) if args.output else _default_output(snapshot_id)
    events_output = Path(args.events_output) if args.events_output else _default_events(snapshot_id)
    as_of_date = _date(args.as_of_date)
    row_count = _write_fixture(
        output=output,
        snapshot_id=snapshot_id,
        as_of_date=as_of_date,
        tickers=tickers,
        benchmark_ticker=benchmark_ticker,
        start_date=_date(args.start_date),
        days=int(args.days),
        provider=str(args.provider),
    )
    event_count = _write_events(output=events_output, tickers=tickers)
    print(
        json.dumps(
            {
                "snapshot_id": snapshot_id,
                "as_of_date": as_of_date.isoformat(),
                "tickers": tickers,
                "benchmark_ticker": benchmark_ticker,
                "output": str(output),
                "events_output": str(events_output),
                "row_count": row_count,
                "event_count": event_count,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
