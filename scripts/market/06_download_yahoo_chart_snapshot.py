from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROVIDER = "yahoo_finance_chart_unofficial"
DEFAULT_RANGE = "3mo"
DEFAULT_INTERVAL = "1d"
DEFAULT_OUTPUT_DIR = Path("data/raw_private/market/provider_snapshots")
CSV_FIELDS = (
    "ticker",
    "date",
    "open",
    "high",
    "low",
    "close",
    "adjusted_close",
    "volume",
    "currency",
    "provider",
    "source_url",
    "market_cap",
    "enterprise_value",
    "pe_ttm",
    "ev_sales_ttm",
    "ev_ebitda_ttm",
)


def _split_csv(value: str | None) -> list[str]:
    out = []
    seen = set()
    for item in (value or "").split(","):
        ticker = item.strip().upper()
        if ticker and ticker not in seen:
            out.append(ticker)
            seen.add(ticker)
    return out


def _tickers_from_config(path: str | None) -> list[str]:
    if not path:
        return []
    text = Path(path).read_text(encoding="utf-8")
    return _split_csv(",".join(re.findall(r"^\s*-\s*ticker:\s*([A-Za-z0-9.\-]+)\s*$", text, flags=re.MULTILINE)))


def _chart_url(ticker: str, period_range: str, interval: str) -> str:
    return (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        f"?range={period_range}&interval={interval}&events=div%2Csplits"
    )


def _read_yahoo_chart(ticker: str, period_range: str, interval: str, timeout: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    url = _chart_url(ticker, period_range, interval)
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 FIN_Insight_Agent market snapshot smoke",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Yahoo chart HTTP {exc.code} for {ticker}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Yahoo chart URL error for {ticker}: {exc.reason}") from exc

    chart = payload.get("chart") or {}
    error = chart.get("error")
    if error:
        raise RuntimeError(f"Yahoo chart error for {ticker}: {json.dumps(error, sort_keys=True)}")
    results = chart.get("result") or []
    if not results:
        raise RuntimeError(f"Yahoo chart returned no result for {ticker}")

    result = results[0]
    meta = result.get("meta") or {}
    timestamps = result.get("timestamp") or []
    indicators = result.get("indicators") or {}
    quote = (indicators.get("quote") or [{}])[0] or {}
    adjusted = (indicators.get("adjclose") or [{}])[0].get("adjclose") or []
    currency = str(meta.get("currency") or "USD")

    rows: list[dict[str, Any]] = []
    for idx, ts_value in enumerate(timestamps):
        close = _list_get(quote.get("close"), idx)
        adjusted_close = _list_get(adjusted, idx)
        if close is None and adjusted_close is None:
            continue
        date = datetime.fromtimestamp(int(ts_value), timezone.utc).date().isoformat()
        rows.append(
            {
                "ticker": ticker,
                "date": date,
                "open": _list_get(quote.get("open"), idx),
                "high": _list_get(quote.get("high"), idx),
                "low": _list_get(quote.get("low"), idx),
                "close": close if close is not None else adjusted_close,
                "adjusted_close": adjusted_close if adjusted_close is not None else close,
                "volume": _list_get(quote.get("volume"), idx),
                "currency": currency,
                "provider": PROVIDER,
                "source_url": url,
                "market_cap": None,
                "enterprise_value": None,
                "pe_ttm": None,
                "ev_sales_ttm": None,
                "ev_ebitda_ttm": None,
            }
        )
    if not rows:
        raise RuntimeError(f"Yahoo chart returned no usable bars for {ticker}")
    return rows, meta


def _list_get(values: Any, idx: int) -> Any:
    if not isinstance(values, list) or idx >= len(values):
        return None
    value = values[idx]
    if value == "null":
        return None
    return value


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: "" if row.get(field) is None else row.get(field) for field in CSV_FIELDS})


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _default_snapshot_id(tickers: list[str], period_range: str) -> str:
    today = datetime.now(timezone.utc).date().isoformat().replace("-", "")
    scope = "full30" if len(tickers) >= 30 else f"{len(tickers)}tickers"
    return f"{today}_market_yahoo_chart_{scope}_{period_range}_v1"


def main() -> int:
    parser = argparse.ArgumentParser(description="Download a real offline Yahoo chart market snapshot CSV.")
    parser.add_argument("--tickers", default="", help="Comma-separated target tickers.")
    parser.add_argument("--benchmark-tickers", default="SPY,QQQ", help="Comma-separated benchmark tickers.")
    parser.add_argument("--tickers-config", default="", help="Optional YAML config with '- ticker: XYZ' entries.")
    parser.add_argument("--range", default=DEFAULT_RANGE, help="Yahoo range, e.g. 3mo, 6mo, 1y.")
    parser.add_argument("--interval", default=DEFAULT_INTERVAL, help="Yahoo interval, e.g. 1d.")
    parser.add_argument("--snapshot-id", default="", help="Stable snapshot id for output filenames.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--timeout", type=int, default=25)
    parser.add_argument("--sleep", type=float, default=0.05, help="Delay between provider requests.")
    parser.add_argument("--fail-on-missing", action="store_true", help="Fail if any ticker cannot be downloaded.")
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    target_tickers = _tickers_from_config(args.tickers_config) + _split_csv(args.tickers)
    target_tickers = _split_csv(",".join(target_tickers))
    benchmark_tickers = _split_csv(args.benchmark_tickers)
    all_tickers = _split_csv(",".join(target_tickers + benchmark_tickers))
    if not target_tickers:
        parser.error("Provide --tickers or --tickers-config.")

    snapshot_id = args.snapshot_id or _default_snapshot_id(target_tickers, args.range)
    output_dir = Path(args.output_dir)
    csv_path = output_dir / f"{snapshot_id}_daily_bars.csv"
    metadata_path = output_dir / f"{snapshot_id}_provider_probe.json"

    rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    meta_by_ticker: dict[str, dict[str, Any]] = {}
    for ticker in all_tickers:
        try:
            ticker_rows, meta = _read_yahoo_chart(ticker, args.range, args.interval, args.timeout)
            rows.extend(ticker_rows)
            meta_by_ticker[ticker] = {
                "long_name": meta.get("longName") or meta.get("shortName"),
                "exchange": meta.get("fullExchangeName") or meta.get("exchangeName"),
                "currency": meta.get("currency"),
                "regular_market_price": meta.get("regularMarketPrice"),
                "regular_market_time": meta.get("regularMarketTime"),
                "bar_count": len(ticker_rows),
                "first_date": ticker_rows[0]["date"],
                "last_date": ticker_rows[-1]["date"],
            }
        except Exception as exc:
            failures.append({"ticker": ticker, "error": str(exc)})
        if args.sleep > 0:
            time.sleep(args.sleep)

    if failures and args.fail_on_missing:
        raise SystemExit(json.dumps({"failures": failures}, ensure_ascii=False, indent=2))
    if not rows:
        raise SystemExit("No market rows downloaded.")

    rows.sort(key=lambda item: (str(item["ticker"]), str(item["date"])))
    target_latest = {
        ticker: meta_by_ticker[ticker]["last_date"]
        for ticker in target_tickers
        if ticker in meta_by_ticker
    }
    benchmark_latest = {
        ticker: meta_by_ticker[ticker]["last_date"]
        for ticker in benchmark_tickers
        if ticker in meta_by_ticker
    }
    common_as_of_date = min(target_latest.values()) if target_latest else ""

    _write_csv(csv_path, rows)
    metadata = {
        "snapshot_id": snapshot_id,
        "provider": PROVIDER,
        "provider_status": "usable_for_price_volume_snapshot",
        "provider_boundary": (
            "Yahoo chart returned OHLCV and adjusted close without an API key in this probe. "
            "Quote/fundamental endpoints were not used; valuation fields are intentionally empty."
        ),
        "range": args.range,
        "interval": args.interval,
        "target_tickers": target_tickers,
        "benchmark_tickers": benchmark_tickers,
        "row_count": len(rows),
        "ticker_count": len(meta_by_ticker),
        "failed_tickers": failures,
        "common_as_of_date": common_as_of_date,
        "latest_date_by_target_ticker": target_latest,
        "latest_date_by_benchmark_ticker": benchmark_latest,
        "metadata_by_ticker": meta_by_ticker,
        "output_csv": str(csv_path),
        "valuation_fields_status": {
            "market_cap": "missing_not_provided",
            "enterprise_value": "missing_not_provided",
            "pe_ttm": "missing_not_provided",
            "ev_sales_ttm": "missing_not_provided",
            "ev_ebitda_ttm": "missing_not_provided",
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_json(metadata_path, metadata)
    metadata["metadata_path"] = str(metadata_path)
    print(json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
