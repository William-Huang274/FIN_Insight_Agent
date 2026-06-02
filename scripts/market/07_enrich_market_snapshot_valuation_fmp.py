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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROVIDER = "financial_modeling_prep_free_key"
DEFAULT_BASE_URL = "https://financialmodelingprep.com/stable"
DEFAULT_OUTPUT_DIR = Path("data/raw_private/market/provider_snapshots")
VALUATION_FIELDS = (
    "market_cap",
    "enterprise_value",
    "pe_ttm",
    "ev_sales_ttm",
    "ev_ebitda_ttm",
)
EXTRA_FIELDS = (
    "valuation_provider",
    "valuation_source_url",
    "valuation_as_of_date",
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


def _endpoint_set(value: str | None) -> set[str]:
    endpoints = {item.strip().lower().replace("-", "_") for item in (value or "").split(",") if item.strip()}
    aliases = {"key_metrics": "key_metrics_ttm", "metrics": "key_metrics_ttm", "ratios": "ratios_ttm"}
    normalized = {aliases.get(item, item) for item in endpoints}
    allowed = {"quote", "key_metrics_ttm", "ratios_ttm"}
    unknown = sorted(normalized - allowed)
    if unknown:
        raise ValueError(f"unknown valuation endpoints: {unknown}; allowed={sorted(allowed)}")
    if not normalized:
        raise ValueError("at least one valuation endpoint is required")
    return normalized


def _tickers_from_config(path: str | None) -> list[str]:
    if not path:
        return []
    text = Path(path).read_text(encoding="utf-8")
    return _split_csv(",".join(re.findall(r"^\s*-\s*ticker:\s*([A-Za-z0-9.\-]+)\s*$", text, flags=re.MULTILINE)))


def _read_rows(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        return [dict(row) for row in reader], list(reader.fieldnames or [])


def _write_rows(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _url(base_url: str, endpoint: str, *, apikey: str, **params: str) -> str:
    query = dict(params)
    query["apikey"] = apikey
    return f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}?{urllib.parse.urlencode(query)}"


def _redact_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    redacted = [(key, "REDACTED" if key.lower() == "apikey" else value) for key, value in query]
    return urllib.parse.urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            urllib.parse.urlencode(redacted),
            parsed.fragment,
        )
    )


def _read_json_url(url: str, timeout: int) -> Any:
    request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "FIN_Insight_Agent market snapshot valuation"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.load(response)
    _raise_provider_error(payload)
    return payload


def _raise_provider_error(payload: Any) -> None:
    if isinstance(payload, dict):
        for field in ("Error Message", "Information", "Note"):
            if payload.get(field):
                raise RuntimeError(str(payload[field]))


def _fetch_fmp_quotes(
    *,
    base_url: str,
    apikey: str,
    tickers: list[str],
    timeout: int,
    sleep: float,
) -> tuple[dict[str, dict[str, Any]], list[str], list[dict[str, str]]]:
    rows: dict[str, dict[str, Any]] = {}
    urls: list[str] = []
    failures: list[dict[str, str]] = []
    for ticker in tickers:
        url = _url(base_url, "quote", apikey=apikey, symbol=ticker)
        urls.append(url)
        try:
            payload = _read_json_url(url, timeout)
            quote_rows = payload if isinstance(payload, list) else []
            for row in quote_rows:
                if isinstance(row, dict) and str(row.get("symbol") or "").upper() == ticker:
                    rows[ticker] = row
                    break
        except Exception as exc:
            failures.append({"ticker": ticker, "stage": "quote", "error": str(exc)})
        if sleep > 0:
            time.sleep(sleep)
    return rows, urls, failures


def _fetch_fmp_key_metrics_ttm(*, base_url: str, apikey: str, ticker: str, timeout: int) -> tuple[dict[str, Any], str]:
    url = _url(base_url, "key-metrics-ttm", apikey=apikey, symbol=ticker)
    payload = _read_json_url(url, timeout)
    if isinstance(payload, list) and payload and isinstance(payload[0], dict):
        return payload[0], url
    if isinstance(payload, dict):
        return payload, url
    return {}, url


def _fetch_fmp_ratios_ttm(*, base_url: str, apikey: str, ticker: str, timeout: int) -> tuple[dict[str, Any], str]:
    url = _url(base_url, "ratios-ttm", apikey=apikey, symbol=ticker)
    payload = _read_json_url(url, timeout)
    if isinstance(payload, list) and payload and isinstance(payload[0], dict):
        return payload[0], url
    if isinstance(payload, dict):
        return payload, url
    return {}, url


def _extract_fmp_valuation(
    ticker: str,
    quote_row: dict[str, Any] | None,
    metrics_row: dict[str, Any] | None,
    ratios_row: dict[str, Any] | None = None,
) -> dict[str, Any]:
    quote = quote_row or {}
    metrics = metrics_row or {}
    ratios = ratios_row or {}
    values = {
        "ticker": ticker,
        "market_cap": _first_number(quote, metrics, ratios, names=("marketCap", "market_cap", "marketCapTTM")),
        "enterprise_value": _first_number(metrics, ratios, quote, names=("enterpriseValueTTM", "enterpriseValue", "enterprise_value")),
        "pe_ttm": _first_number(quote, ratios, metrics, names=("pe", "peRatio", "peRatioTTM", "priceEarningsRatioTTM", "priceToEarningsRatioTTM")),
        "ev_sales_ttm": _first_number(
            metrics,
            ratios,
            quote,
            names=("evToSalesTTM", "enterpriseValueOverRevenueTTM", "enterpriseValueToRevenueTTM", "evToSales", "enterpriseValueOverRevenue"),
        ),
        "ev_ebitda_ttm": _first_number(
            metrics,
            ratios,
            quote,
            names=("enterpriseValueOverEBITDATTM", "evToEBITDATTM", "evToEBITDA", "enterpriseValueOverEBITDA"),
        ),
        "source_fields": {
            "quote": sorted(k for k, v in quote.items() if v not in (None, "")),
            "key_metrics_ttm": sorted(k for k, v in metrics.items() if v not in (None, "")),
            "ratios_ttm": sorted(k for k, v in ratios.items() if v not in (None, "")),
        },
    }
    return values


def _first_number(*payloads: dict[str, Any], names: tuple[str, ...]) -> float | None:
    for name in names:
        for payload in payloads:
            if name not in payload:
                continue
            value = _float_or_none(payload.get(name))
            if value is not None:
                return value
    return None


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        result = float(text)
    except ValueError:
        return None
    if result != result or result in (float("inf"), float("-inf")):
        return None
    return result


def _latest_row_indexes_by_ticker(rows: list[dict[str, Any]], tickers: set[str], benchmark_tickers: set[str]) -> dict[str, int]:
    indexes: dict[str, int] = {}
    latest_dates: dict[str, str] = {}
    for idx, row in enumerate(rows):
        ticker = str(row.get("ticker") or row.get("symbol") or "").upper()
        if not ticker or ticker in benchmark_tickers:
            continue
        if tickers and ticker not in tickers:
            continue
        row_date = str(row.get("date") or "")
        if ticker not in latest_dates or row_date > latest_dates[ticker]:
            latest_dates[ticker] = row_date
            indexes[ticker] = idx
    return indexes


def _enrich_latest_rows(
    rows: list[dict[str, Any]],
    *,
    valuations: dict[str, dict[str, Any]],
    tickers: list[str],
    benchmark_tickers: list[str],
    valuation_source_url: str,
    valuation_as_of_date: str,
) -> dict[str, Any]:
    indexes = _latest_row_indexes_by_ticker(rows, set(tickers), set(benchmark_tickers))
    missing_tickers = []
    field_coverage = {field: 0 for field in VALUATION_FIELDS}
    for ticker in tickers:
        idx = indexes.get(ticker)
        valuation = valuations.get(ticker) or {}
        if idx is None or not valuation:
            missing_tickers.append(ticker)
            continue
        row = rows[idx]
        row["valuation_provider"] = PROVIDER
        row["valuation_source_url"] = valuation_source_url
        row["valuation_as_of_date"] = valuation_as_of_date
        for field in VALUATION_FIELDS:
            value = valuation.get(field)
            row[field] = "" if value is None else value
            if value is not None:
                field_coverage[field] += 1
    return {
        "enriched_ticker_count": sum(1 for ticker in tickers if ticker in indexes and valuations.get(ticker)),
        "missing_tickers": missing_tickers,
        "field_coverage": field_coverage,
    }


def _default_output(input_path: Path, snapshot_id: str) -> Path:
    suffix = input_path.suffix or ".csv"
    return DEFAULT_OUTPUT_DIR / f"{snapshot_id}_daily_bars_with_fmp_valuation{suffix}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Enrich a market daily-bars CSV with FMP free-key valuation fields.")
    parser.add_argument("--input", required=True, help="Daily bars CSV from the price/volume provider.")
    parser.add_argument("--output", default="")
    parser.add_argument("--snapshot-id", required=True)
    parser.add_argument("--tickers", default="")
    parser.add_argument("--tickers-config", default="")
    parser.add_argument("--benchmark-tickers", default="SPY,QQQ")
    parser.add_argument("--api-key-env", default="FMP_API_KEY")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument(
        "--valuation-endpoints",
        default="quote,key_metrics_ttm,ratios_ttm",
        help=(
            "Comma-separated FMP endpoints to call. Use key_metrics_ttm for large "
            "universes when free-key limits make quote/ratios too expensive."
        ),
    )
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--sleep", type=float, default=0.1)
    parser.add_argument("--fail-on-missing", action="store_true")
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    api_key = os.environ.get(args.api_key_env)
    if not api_key:
        raise SystemExit(f"Missing {args.api_key_env}; get a free FMP key and export it before running this enrichment.")

    input_path = Path(args.input)
    output_path = Path(args.output) if args.output else _default_output(input_path, args.snapshot_id)
    target_tickers = _split_csv(",".join(_tickers_from_config(args.tickers_config) + _split_csv(args.tickers)))
    benchmark_tickers = _split_csv(args.benchmark_tickers)
    endpoint_set = _endpoint_set(args.valuation_endpoints)
    if not target_tickers:
        parser.error("Provide --tickers or --tickers-config.")

    rows, fieldnames = _read_rows(input_path)
    for field in [*VALUATION_FIELDS, *EXTRA_FIELDS]:
        if field not in fieldnames:
            fieldnames.append(field)

    quote_rows: dict[str, dict[str, Any]] = {}
    quote_urls: list[str] = []
    quote_failures: list[dict[str, str]] = []
    if "quote" in endpoint_set:
        quote_rows, quote_urls, quote_failures = _fetch_fmp_quotes(
            base_url=args.base_url,
            apikey=api_key,
            tickers=target_tickers,
            timeout=args.timeout,
            sleep=args.sleep,
        )
    valuations: dict[str, dict[str, Any]] = {}
    failures = list(quote_failures)
    source_urls = [_redact_url(url) for url in quote_urls]
    for ticker in target_tickers:
        try:
            metrics: dict[str, Any] = {}
            ratios: dict[str, Any] = {}
            if "key_metrics_ttm" in endpoint_set:
                metrics, metrics_url = _fetch_fmp_key_metrics_ttm(
                    base_url=args.base_url,
                    apikey=api_key,
                    ticker=ticker,
                    timeout=args.timeout,
                )
                source_urls.append(_redact_url(metrics_url))
            if "ratios_ttm" in endpoint_set:
                ratios, ratios_url = _fetch_fmp_ratios_ttm(base_url=args.base_url, apikey=api_key, ticker=ticker, timeout=args.timeout)
                source_urls.append(_redact_url(ratios_url))
            valuations[ticker] = _extract_fmp_valuation(ticker, quote_rows.get(ticker), metrics, ratios)
        except Exception as exc:
            failures.append({"ticker": ticker, "error": str(exc)})
        if args.sleep > 0:
            time.sleep(args.sleep)

    valuation_as_of_date = datetime.now(timezone.utc).date().isoformat()
    enrichment = _enrich_latest_rows(
        rows,
        valuations=valuations,
        tickers=target_tickers,
        benchmark_tickers=benchmark_tickers,
        valuation_source_url=";".join(source_urls[:4]) + (";..." if len(source_urls) > 4 else ""),
        valuation_as_of_date=valuation_as_of_date,
    )
    _write_rows(output_path, rows, fieldnames)
    metadata = {
        "snapshot_id": args.snapshot_id,
        "provider": PROVIDER,
        "input": str(input_path),
        "output": str(output_path),
        "target_tickers": target_tickers,
        "benchmark_tickers": benchmark_tickers,
        "valuation_endpoints": sorted(endpoint_set),
        "valuation_as_of_date": valuation_as_of_date,
        "failed_tickers": failures,
        "enrichment": enrichment,
        "source_url_count": len(source_urls),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    metadata_path = output_path.with_suffix(".provider_probe.json")
    _write_json(metadata_path, metadata)
    metadata["metadata_path"] = str(metadata_path)
    print(json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True))
    if failures and args.fail_on_missing:
        return 2
    if args.fail_on_missing and enrichment["missing_tickers"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
