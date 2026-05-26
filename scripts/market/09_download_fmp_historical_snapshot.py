from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


PROVIDER = "financial_modeling_prep_stable_historical_eod"
DEFAULT_BASE_URL = "https://financialmodelingprep.com/stable"
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


def _url(base_url: str, endpoint: str, *, apikey: str, **params: str) -> str:
    query = dict(params)
    query["apikey"] = apikey
    return f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}?{urllib.parse.urlencode(query)}"


def _redact_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    redacted = [(key, "REDACTED" if key.lower() == "apikey" else value) for key, value in query]
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(redacted), parsed.fragment))


def _read_json_url(url: str, timeout: int) -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "FIN_Insight_Agent FMP market snapshot",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def _raise_provider_error(payload: Any, ticker: str) -> None:
    if isinstance(payload, dict):
        for field in ("Error Message", "Information", "Note"):
            if payload.get(field):
                raise RuntimeError(f"FMP historical error for {ticker}: {payload[field]}")


def _read_fmp_historical_eod(
    *,
    ticker: str,
    base_url: str,
    apikey: str,
    from_date: str,
    to_date: str,
    timeout: int,
) -> tuple[list[dict[str, Any]], str]:
    url = _url(
        base_url,
        "historical-price-eod/full",
        apikey=apikey,
        symbol=ticker,
        **{"from": from_date, "to": to_date},
    )
    payload = _read_json_url(url, timeout)
    _raise_provider_error(payload, ticker)
    if not isinstance(payload, list):
        raise RuntimeError(f"FMP historical returned {type(payload).__name__} for {ticker}, expected list")

    rows = [_normalize_fmp_bar(ticker, item, source_url=_redact_url(url)) for item in payload if isinstance(item, dict)]
    rows = [row for row in rows if row["date"] and (row["close"] is not None or row["adjusted_close"] is not None)]
    rows.sort(key=lambda item: str(item["date"]))
    if not rows:
        raise RuntimeError(f"FMP historical returned no usable bars for {ticker}")
    return rows, _redact_url(url)


def _normalize_fmp_bar(ticker: str, row: dict[str, Any], *, source_url: str) -> dict[str, Any]:
    close = _first_number(row, "close", "price")
    adjusted_close = _first_number(row, "adjClose", "adjustedClose", "adjusted_close") or close
    return {
        "ticker": ticker,
        "date": str(row.get("date") or ""),
        "open": _first_number(row, "open"),
        "high": _first_number(row, "high"),
        "low": _first_number(row, "low"),
        "close": close if close is not None else adjusted_close,
        "adjusted_close": adjusted_close,
        "volume": _first_number(row, "volume"),
        "currency": "USD",
        "provider": PROVIDER,
        "source_url": source_url,
        "market_cap": None,
        "enterprise_value": None,
        "pe_ttm": None,
        "ev_sales_ttm": None,
        "ev_ebitda_ttm": None,
    }


def _first_number(row: dict[str, Any], *names: str) -> float | None:
    for name in names:
        if name not in row:
            continue
        value = row.get(name)
        if value is None:
            continue
        text = str(value).strip().replace(",", "")
        if not text:
            continue
        try:
            result = float(text)
        except ValueError:
            continue
        if result != result or result in (float("inf"), float("-inf")):
            continue
        return result
    return None


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


def _default_dates(days: int) -> tuple[str, str]:
    today = datetime.now(timezone.utc).date()
    to_date = today - timedelta(days=1)
    from_date = to_date - timedelta(days=days)
    return from_date.isoformat(), to_date.isoformat()


def _default_snapshot_id(tickers: list[str], from_date: str, to_date: str) -> str:
    generated = datetime.now(timezone.utc).date().isoformat().replace("-", "")
    scope = "full30" if len(tickers) >= 30 else f"{len(tickers)}tickers"
    return f"{generated}_market_fmp_historical_{scope}_{from_date}_{to_date}_v1"


def main() -> int:
    parser = argparse.ArgumentParser(description="Download FMP stable historical EOD daily bars for offline market snapshots.")
    parser.add_argument("--tickers", default="", help="Comma-separated target tickers.")
    parser.add_argument("--benchmark-tickers", default="SPY,QQQ", help="Comma-separated benchmark tickers.")
    parser.add_argument("--tickers-config", default="", help="Optional YAML config with '- ticker: XYZ' entries.")
    parser.add_argument("--from-date", default="", help="Inclusive YYYY-MM-DD start date.")
    parser.add_argument("--to-date", default="", help="Inclusive YYYY-MM-DD end date.")
    parser.add_argument("--lookback-days", type=int, default=90, help="Used only when from/to dates are not provided.")
    parser.add_argument("--snapshot-id", default="", help="Stable snapshot id for output filenames.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--api-key-env", default="FMP_API_KEY")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--timeout", type=int, default=25)
    parser.add_argument("--sleep", type=float, default=0.1)
    parser.add_argument("--fail-on-missing", action="store_true", help="Fail if any ticker cannot be downloaded.")
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    apikey = os.environ.get(args.api_key_env, "").strip()
    if not apikey:
        raise SystemExit(f"{args.api_key_env} is not set.")

    target_tickers = _tickers_from_config(args.tickers_config) + _split_csv(args.tickers)
    target_tickers = _split_csv(",".join(target_tickers))
    benchmark_tickers = _split_csv(args.benchmark_tickers)
    all_tickers = _split_csv(",".join(target_tickers + benchmark_tickers))
    if not target_tickers:
        parser.error("Provide --tickers or --tickers-config.")

    from_date, to_date = (args.from_date, args.to_date)
    if not from_date or not to_date:
        from_date, to_date = _default_dates(args.lookback_days)

    snapshot_id = args.snapshot_id or _default_snapshot_id(target_tickers, from_date, to_date)
    output_dir = Path(args.output_dir)
    csv_path = output_dir / f"{snapshot_id}_daily_bars.csv"
    metadata_path = output_dir / f"{snapshot_id}_provider_probe.json"

    rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    meta_by_ticker: dict[str, dict[str, Any]] = {}
    for ticker in all_tickers:
        try:
            ticker_rows, source_url = _read_fmp_historical_eod(
                ticker=ticker,
                base_url=args.base_url,
                apikey=apikey,
                from_date=from_date,
                to_date=to_date,
                timeout=args.timeout,
            )
            rows.extend(ticker_rows)
            meta_by_ticker[ticker] = {
                "bar_count": len(ticker_rows),
                "first_date": ticker_rows[0]["date"],
                "last_date": ticker_rows[-1]["date"],
                "source_url": source_url,
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
    target_latest = {ticker: meta_by_ticker[ticker]["last_date"] for ticker in target_tickers if ticker in meta_by_ticker}
    benchmark_latest = {ticker: meta_by_ticker[ticker]["last_date"] for ticker in benchmark_tickers if ticker in meta_by_ticker}
    common_as_of_date = min(target_latest.values()) if target_latest else ""

    _write_csv(csv_path, rows)
    metadata = {
        "snapshot_id": snapshot_id,
        "provider": PROVIDER,
        "provider_status": "usable_for_price_volume_snapshot",
        "provider_boundary": (
            "FMP stable historical-price-eod/full returned OHLCV data with an environment API key. "
            "Valuation fields are intentionally empty in this raw bars export and should be added by the FMP valuation enrichment step."
        ),
        "from_date": from_date,
        "to_date": to_date,
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
            "market_cap": "missing_before_enrichment",
            "enterprise_value": "missing_before_enrichment",
            "pe_ttm": "missing_before_enrichment",
            "ev_sales_ttm": "missing_before_enrichment",
            "ev_ebitda_ttm": "missing_before_enrichment",
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_json(metadata_path, metadata)
    metadata["metadata_path"] = str(metadata_path)
    print(json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
