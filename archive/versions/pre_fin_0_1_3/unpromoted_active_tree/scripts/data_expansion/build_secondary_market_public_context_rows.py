from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


SCHEMA_VERSION = "finsight_secondary_market_public_context_row_v0_1"
SUMMARY_SCHEMA_VERSION = "finsight_secondary_market_public_context_summary_v0_1"
DEFAULT_MARKET_ROWS = REPO_ROOT / "data" / "manifests" / "market_liquidity_driver_context_rows_v0_1.jsonl"
DEFAULT_MARKET_SNAPSHOT_ROWS = (
    REPO_ROOT
    / "data"
    / "processed_private"
    / "market"
    / "snapshots"
    / "20260624_market_yahoo_chart_603_3m_v1_snapshot.jsonl"
)
DEFAULT_MARKET_BARS_ROWS = (
    REPO_ROOT
    / "data"
    / "processed_private"
    / "market"
    / "bars"
    / "20260624_market_yahoo_chart_603_3m_v1_daily_bars.jsonl"
)
DEFAULT_SEC_FS_ROWS = REPO_ROOT / "data" / "manifests" / "sec_financial_statement_metric_runtime_rows_v0_1.jsonl"
DEFAULT_UNIVERSE_ENTITIES = (
    REPO_ROOT
    / "data"
    / "processed_private"
    / "public_sources"
    / "public_source_mapping_endpoint_gate_v0_1"
    / "universe_entities.jsonl"
)
DEFAULT_SEC_COMPANYFACTS_CACHE_DIR = REPO_ROOT / "data" / "raw_private" / "sec_companyfacts_valuation_cache"
DEFAULT_OUTPUT_ROWS = REPO_ROOT / "data" / "manifests" / "secondary_market_public_context_rows_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY = REPO_ROOT / "data" / "manifests" / "secondary_market_public_context_summary_v0_1.json"
FRED_API_URL = "https://api.stlouisfed.org/fred/series/observations"
FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
YAHOO_TIMESERIES_URL = "https://query1.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/{symbol}"
FRED_SERIES = {
    "VIXCLS": {
        "label": "CBOE Volatility Index: VIX",
        "source_id": "fred_vix_market_volatility_regime",
        "pack_role": "derivatives_market_signal",
        "signal_type": "fred_vix_market_volatility_regime",
        "unit": "index_level",
    },
    "BAMLC0A0CM": {
        "label": "ICE BofA US Corporate Index Option-Adjusted Spread",
        "source_id": "fred_credit_spread_regime",
        "pack_role": "credit_funding",
        "signal_type": "fred_credit_spread_regime_context",
        "unit": "percent",
    },
    "BAMLH0A0HYM2": {
        "label": "ICE BofA US High Yield Index Option-Adjusted Spread",
        "source_id": "fred_credit_spread_regime",
        "pack_role": "credit_funding",
        "signal_type": "fred_credit_spread_regime_context",
        "unit": "percent",
    },
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build public secondary-market valuation, credit-spread and volatility context rows.")
    parser.add_argument("--market-rows", type=Path, default=DEFAULT_MARKET_ROWS)
    parser.add_argument("--market-snapshot-rows", type=Path, default=DEFAULT_MARKET_SNAPSHOT_ROWS)
    parser.add_argument("--market-bars", type=Path, default=DEFAULT_MARKET_BARS_ROWS)
    parser.add_argument("--sec-financial-rows", type=Path, default=DEFAULT_SEC_FS_ROWS)
    parser.add_argument("--universe-entities", type=Path, default=DEFAULT_UNIVERSE_ENTITIES)
    parser.add_argument("--sec-companyfacts-cache-dir", type=Path, default=DEFAULT_SEC_COMPANYFACTS_CACHE_DIR)
    parser.add_argument("--no-sec-companyfacts-fetch", action="store_true")
    parser.add_argument("--output-rows", type=Path, default=DEFAULT_OUTPUT_ROWS)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--fred-api-key-env", default="FRED_API_KEY")
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at = _utc_now()
    market_rows = list(_load_jsonl(args.market_rows))
    market_snapshot_rows = list(_load_jsonl(args.market_snapshot_rows))
    market_bar_rows = list(_load_jsonl(args.market_bars))
    effective_market_rows = [*market_rows, *market_snapshot_rows, *market_bar_rows]
    sec_rows = list(_load_jsonl(args.sec_financial_rows))
    fred_latest, fred_failures = fetch_fred_latest(timeout=args.timeout, api_key_env=args.fred_api_key_env)
    supplemental_valuation_facts = (
        {}
        if args.no_sec_companyfacts_fetch
        else fetch_sec_companyfacts_valuation_facts(
            market_rows=effective_market_rows,
            sec_financial_rows=sec_rows,
            universe_entities_path=args.universe_entities,
            cache_dir=args.sec_companyfacts_cache_dir,
            timeout=args.timeout,
        )
    )
    supplemental_valuation_facts = {
        **supplemental_valuation_facts,
        **fetch_yahoo_market_cap_facts(
            market_rows=effective_market_rows,
            sec_financial_rows=sec_rows,
            supplemental_valuation_facts=supplemental_valuation_facts,
            timeout=args.timeout,
        ),
    }
    rows = build_secondary_market_public_context_rows(
        market_rows=effective_market_rows,
        sec_financial_rows=sec_rows,
        fred_latest=fred_latest,
        supplemental_valuation_facts=supplemental_valuation_facts,
        generated_at=generated_at,
    )
    summary = build_summary(
        rows=rows,
        market_rows=effective_market_rows,
        market_snapshot_rows=market_snapshot_rows,
        market_bar_rows=market_bar_rows,
        sec_financial_rows=sec_rows,
        fred_latest=fred_latest,
        fred_failures=fred_failures,
        supplemental_valuation_facts=supplemental_valuation_facts,
        generated_at=generated_at,
        output_rows=args.output_rows,
    )
    _write_jsonl(args.output_rows, rows)
    _write_json(args.output_summary, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if args.strict and (summary["row_count"] == 0 or summary["fred_failure_count"]):
        return 1
    return 0


def build_secondary_market_public_context_rows(
    *,
    market_rows: Iterable[Mapping[str, Any]],
    sec_financial_rows: Iterable[Mapping[str, Any]],
    fred_latest: Mapping[str, Mapping[str, Any]],
    supplemental_valuation_facts: Mapping[str, Mapping[str, Any]] | None = None,
    generated_at: str,
) -> list[dict[str, Any]]:
    latest_market = latest_market_rows(market_rows)
    latest_shares = latest_shares_rows(sec_financial_rows)
    supplemental_valuation_facts = supplemental_valuation_facts or {}
    out: list[dict[str, Any]] = []
    for ticker, market in sorted(latest_market.items()):
        price = _market_price(market)
        shares = latest_shares.get(ticker)
        if price is not None and shares:
            share_value = _number(shares.get("value"))
            if share_value is not None and share_value > 0:
                out.append(_valuation_row(ticker, market, shares, price, share_value, generated_at))
        elif price is not None and ticker in supplemental_valuation_facts:
            fact = supplemental_valuation_facts[ticker]
            fact_type = str(fact.get("fact_type") or "")
            if fact_type == "shares_outstanding":
                share_value = _number(fact.get("value"))
                if share_value is not None and share_value > 0:
                    out.append(_valuation_row(ticker, market, fact, price, share_value, generated_at))
            elif fact_type == "public_float":
                out.append(_public_float_row(ticker, fact, generated_at))
            elif fact_type == "market_cap":
                out.append(_market_cap_row(ticker, fact, generated_at))
        if "VIXCLS" in fred_latest:
            out.append(_fred_derivatives_row(ticker, fred_latest["VIXCLS"], generated_at))
        if "BAMLC0A0CM" in fred_latest or "BAMLH0A0HYM2" in fred_latest:
            out.append(_fred_credit_row(ticker, fred_latest, generated_at))
    out.sort(key=lambda row: (str(row.get("ticker")), str(row.get("pack_role")), str(row.get("evidence_ref"))))
    return out


def fetch_sec_companyfacts_valuation_facts(
    *,
    market_rows: Iterable[Mapping[str, Any]],
    sec_financial_rows: Iterable[Mapping[str, Any]],
    universe_entities_path: Path,
    cache_dir: Path,
    timeout: int,
) -> dict[str, dict[str, Any]]:
    latest_market = latest_market_rows(market_rows)
    latest_shares = latest_shares_rows(sec_financial_rows)
    cik_by_ticker = load_cik_map(universe_entities_path)
    missing = sorted(ticker for ticker in latest_market if ticker not in latest_shares and ticker in cik_by_ticker)
    out: dict[str, dict[str, Any]] = {}
    for ticker in missing:
        cik = cik_by_ticker[ticker]
        companyfacts = load_sec_companyfacts(cik, cache_dir=cache_dir, timeout=timeout)
        if not companyfacts:
            continue
        fact = extract_sec_companyfacts_valuation_fact(ticker=ticker, cik=cik, companyfacts=companyfacts)
        if fact:
            out[ticker] = fact
    return out


def fetch_yahoo_market_cap_facts(
    *,
    market_rows: Iterable[Mapping[str, Any]],
    sec_financial_rows: Iterable[Mapping[str, Any]],
    supplemental_valuation_facts: Mapping[str, Mapping[str, Any]],
    timeout: int,
) -> dict[str, dict[str, Any]]:
    latest_market = latest_market_rows(market_rows)
    latest_shares = latest_shares_rows(sec_financial_rows)
    missing = sorted(
        ticker
        for ticker in latest_market
        if ticker not in latest_shares and ticker not in supplemental_valuation_facts
    )
    out: dict[str, dict[str, Any]] = {}
    for ticker in missing:
        fact = fetch_yahoo_market_cap_fact(ticker, timeout=timeout)
        if fact:
            out[ticker] = fact
    return out


def fetch_yahoo_market_cap_fact(ticker: str, *, timeout: int) -> dict[str, Any] | None:
    encoded = urllib.parse.quote(ticker, safe="")
    query = urllib.parse.urlencode(
        {
            "type": "trailingMarketCap,quarterlyMarketCap,annualMarketCap",
            "period1": "1704067200",
            "period2": "1798761600",
        }
    )
    url = f"{YAHOO_TIMESERIES_URL.format(symbol=encoded)}?{query}"
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 FIN_Insight_Agent valuation context"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return None
    candidates: list[dict[str, Any]] = []
    for block in payload.get("timeseries", {}).get("result", []) or []:
        if not isinstance(block, Mapping):
            continue
        for key in ("trailingMarketCap", "quarterlyMarketCap", "annualMarketCap"):
            for item in block.get(key, []) or []:
                if not isinstance(item, Mapping):
                    continue
                reported = item.get("reportedValue") if isinstance(item.get("reportedValue"), Mapping) else {}
                value = _number(reported.get("raw"))
                if value is None or value <= 0:
                    continue
                candidates.append(
                    {
                        "ticker": ticker,
                        "fact_type": "market_cap",
                        "source_id": "yahoo_fundamentals_timeseries_market_cap",
                        "evidence_ref": _stable_ref("s8_yahoo_market_cap", [ticker, key, item.get("asOfDate"), value]),
                        "metric_name": key,
                        "value": value,
                        "unit": item.get("currencyCode") or "",
                        "period": item.get("asOfDate") or "",
                        "period_end": item.get("asOfDate") or "",
                        "source_url": url,
                    }
                )
    if not candidates:
        return None
    return max(candidates, key=lambda fact: str(fact.get("period") or ""))


def load_cik_map(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for row in _load_jsonl(path):
        ticker = _ticker(row.get("ticker"))
        cik = str(row.get("cik") or "").strip()
        if ticker and cik:
            out[ticker] = cik.zfill(10)
    return out


def load_sec_companyfacts(cik: str, *, cache_dir: Path, timeout: int) -> dict[str, Any] | None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"CIK{cik}.json"
    if cache_path.exists():
        try:
            return json.loads(cache_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            cache_path.unlink(missing_ok=True)
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "FIN_Insight_Agent valuation context hht13@example.com"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        cache_path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        return payload
    except Exception:
        return None


def extract_sec_companyfacts_valuation_fact(*, ticker: str, cik: str, companyfacts: Mapping[str, Any]) -> dict[str, Any] | None:
    facts = companyfacts.get("facts") if isinstance(companyfacts.get("facts"), Mapping) else {}
    share_fact = _latest_sec_fact(
        facts,
        concepts=[
            ("dei", "EntityCommonStockSharesOutstanding"),
            ("us-gaap", "CommonStockSharesOutstanding"),
        ],
        unit_candidates=["shares"],
    )
    if share_fact:
        return _sec_valuation_fact_row(
            ticker=ticker,
            cik=cik,
            fact=share_fact,
            fact_type="shares_outstanding",
            source_id="sec_companyfacts_common_stock_shares_outstanding",
            metric_name="sec_companyfacts_common_stock_shares_outstanding",
            unit="shares",
        )
    public_float = _latest_sec_fact(facts, concepts=[("dei", "EntityPublicFloat")], unit_candidates=["USD", "usd"])
    if public_float:
        return _sec_valuation_fact_row(
            ticker=ticker,
            cik=cik,
            fact=public_float,
            fact_type="public_float",
            source_id="sec_entity_public_float",
            metric_name="sec_entity_public_float",
            unit="USD",
        )
    return None


def _latest_sec_fact(
    facts: Mapping[str, Any],
    *,
    concepts: list[tuple[str, str]],
    unit_candidates: list[str],
) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []
    for taxonomy, concept in concepts:
        concept_payload = facts.get(taxonomy, {}).get(concept) if isinstance(facts.get(taxonomy), Mapping) else None
        if not isinstance(concept_payload, Mapping):
            continue
        units = concept_payload.get("units") if isinstance(concept_payload.get("units"), Mapping) else {}
        for unit in unit_candidates:
            for fact in units.get(unit, []) or []:
                value = _number(fact.get("val"))
                if value is None or value <= 0:
                    continue
                candidates.append(
                    {
                        **dict(fact),
                        "taxonomy": taxonomy,
                        "concept": concept,
                        "label": concept_payload.get("label") or concept,
                        "unit": unit,
                        "value": value,
                    }
                )
    if not candidates:
        return None
    return max(candidates, key=lambda fact: str(fact.get("filed") or fact.get("end") or ""))


def _sec_valuation_fact_row(
    *,
    ticker: str,
    cik: str,
    fact: Mapping[str, Any],
    fact_type: str,
    source_id: str,
    metric_name: str,
    unit: str,
) -> dict[str, Any]:
    period = str(fact.get("end") or fact.get("filed") or "")
    evidence_ref = _stable_ref("s8_sec_valuation_fact", [ticker, source_id, fact.get("accn"), period, fact.get("value")])
    source_url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    return {
        "ticker": ticker,
        "cik": cik,
        "fact_type": fact_type,
        "canonical_metric_id": "financial_metric:shares_outstanding" if fact_type == "shares_outstanding" else "financial_metric:entity_public_float",
        "source_id": source_id,
        "evidence_ref": evidence_ref,
        "fact_id": evidence_ref,
        "evidence_id": evidence_ref,
        "metric_name": metric_name,
        "concept": fact.get("concept"),
        "taxonomy": fact.get("taxonomy"),
        "value": fact.get("value"),
        "unit": unit,
        "period": period,
        "period_end": fact.get("end") or "",
        "filing_date": fact.get("filed") or "",
        "source_url": source_url,
        "citation": {"url": source_url, "title": f"{ticker} SEC CompanyFacts {fact.get('concept')}", "span": f"value={fact.get('value')} {unit}; period={period}; filed={fact.get('filed')}"},
    }


def latest_market_rows(rows: Iterable[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    latest: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if row.get("is_benchmark") is True:
            continue
        ticker = _ticker(row.get("ticker"))
        if not ticker:
            continue
        if _market_price(row) is None:
            continue
        if ticker not in latest or _market_row_date(row) >= _market_row_date(latest[ticker]):
            latest[ticker] = row
    return latest


def latest_shares_rows(rows: Iterable[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    latest: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        ticker = _ticker(row.get("ticker"))
        if not ticker:
            continue
        canonical = str(row.get("canonical_metric_id") or "")
        metric = str(row.get("metric_family") or row.get("metric_name") or "").lower()
        if canonical != "financial_metric:shares_outstanding" and "shares_outstanding" not in metric:
            continue
        value = _number(row.get("value"))
        if value is None or value <= 0:
            continue
        row_date = str(row.get("period_end") or row.get("period") or row.get("filing_date") or "")
        old_date = str(latest.get(ticker, {}).get("period_end") or latest.get(ticker, {}).get("period") or latest.get(ticker, {}).get("filing_date") or "")
        if ticker not in latest or row_date >= old_date:
            latest[ticker] = row
    return latest


def fetch_fred_latest(*, timeout: int, api_key_env: str = "FRED_API_KEY") -> tuple[dict[str, dict[str, Any]], list[dict[str, str]]]:
    latest: dict[str, dict[str, Any]] = {}
    failures: list[dict[str, str]] = []
    api_key = _load_env_value(api_key_env)
    for series_id, meta in FRED_SERIES.items():
        api_result = None
        api_error = ""
        if api_key:
            api_result, api_error = _fetch_fred_latest_from_api(series_id, meta, api_key=api_key, timeout=timeout)
        if api_result:
            latest[series_id] = api_result
            continue
        url = FRED_CSV_URL.format(series_id=series_id)
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "FIN_Insight_Agent secondary market public context"})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                text = response.read().decode("utf-8-sig")
            rows = list(csv.DictReader(text.splitlines()))
            for row in reversed(rows):
                value = _number(row.get(series_id))
                if value is None:
                    continue
                latest[series_id] = {
                    "series_id": series_id,
                    "label": meta["label"],
                    "date": row.get("observation_date") or row.get("DATE") or row.get("date") or "",
                    "value": value,
                    "unit": meta["unit"],
                    "source_url": url,
                    "fetch_route": "fred_graph_csv",
                }
                break
            if series_id not in latest:
                failures.append({"series_id": series_id, "error": _join_errors(api_error, "csv_no_numeric_observation")})
        except Exception as exc:
            failures.append({"series_id": series_id, "error": _join_errors(api_error, f"csv_{type(exc).__name__}: {exc}")})
    return latest, failures


def _fetch_fred_latest_from_api(
    series_id: str,
    meta: Mapping[str, Any],
    *,
    api_key: str,
    timeout: int,
) -> tuple[dict[str, Any] | None, str]:
    query = urllib.parse.urlencode(
        {
            "series_id": series_id,
            "api_key": api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": "5",
        }
    )
    request_url = f"{FRED_API_URL}?{query}"
    public_url = f"{FRED_API_URL}?series_id={series_id}&file_type=json&sort_order=desc&limit=5"
    try:
        request = urllib.request.Request(request_url, headers={"User-Agent": "FIN_Insight_Agent secondary market public context"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        for observation in payload.get("observations") or []:
            value = _number(observation.get("value"))
            if value is None:
                continue
            return (
                {
                    "series_id": series_id,
                    "label": meta["label"],
                    "date": observation.get("date") or "",
                    "value": value,
                    "unit": meta["unit"],
                    "source_url": public_url,
                    "fetch_route": "fred_api",
                },
                "",
            )
        return None, "api_no_numeric_observation"
    except Exception as exc:
        return None, f"api_{type(exc).__name__}: {exc}"


def _valuation_row(
    ticker: str,
    market: Mapping[str, Any],
    shares: Mapping[str, Any],
    price: float,
    share_value: float,
    generated_at: str,
) -> dict[str, Any]:
    market_cap = price * share_value
    period = _market_row_date(market)
    shares_period = str(shares.get("period_end") or shares.get("period") or shares.get("filing_date") or "")
    evidence_ref = _stable_ref("s8_public_valuation", [ticker, period, shares_period, price, share_value])
    return {
        "schema_version": SCHEMA_VERSION,
        "evidence_ref": evidence_ref,
        "evidence_id": evidence_ref,
        "fact_id": evidence_ref,
        "ticker": ticker,
        "source_id": "public_price_x_sec_shares_market_cap",
        "source_role": "valuation_price_in",
        "source_family": "secondary_market_public_context",
        "runtime_source_family": "secondary_market_public_context",
        "pack_role": "valuation_price_in",
        "authority_class": "valuation_price_in_signal",
        "signal_type": "public_price_filed_shares_market_cap_context",
        "metric_name": "market_cap_from_delayed_price_and_reported_shares",
        "value": market_cap,
        "unit": "market_cap_in_price_currency",
        "period": period,
        "as_of_date": period,
        "source_url": str(market.get("source_url") or ""),
        "citation": {
            "url": str(market.get("source_url") or ""),
            "title": f"{ticker} delayed price x issuer-filed shares market-cap context",
            "span": f"price={price}; shares_outstanding={share_value}; shares_period={shares_period}; market_period={period}",
        },
        "valuation_context": {
            "close_price": price,
            "shares_outstanding": share_value,
            "shares_period": shares_period,
            "computed_market_cap": market_cap,
            "price_source_ref": market.get("evidence_ref") or market.get("evidence_id"),
            "shares_source_ref": shares.get("evidence_ref") or shares.get("fact_id"),
        },
        "allowed_claims": ["valuation_price_in_context", "market_cap_context_from_public_price_and_filed_shares"],
        "forbidden_claims": ["fair_value_truth", "consensus_ntm_without_commercial_source", "investment_recommendation"],
        "claim_boundary": "Computed market-cap context from delayed public price and issuer-filed shares; not a fair-value, target-price, or consensus estimate.",
        "parser_status": "public_price_and_filed_shares_join_pass",
        "structured_context_type": "valuation_price_in_context",
        "generated_at": generated_at,
    }


def _public_float_row(ticker: str, fact: Mapping[str, Any], generated_at: str) -> dict[str, Any]:
    period = str(fact.get("period_end") or fact.get("period") or fact.get("filing_date") or "")
    value = _number(fact.get("value"))
    evidence_ref = _stable_ref("s8_sec_public_float", [ticker, fact.get("evidence_ref"), period, value])
    source_url = str(fact.get("source_url") or "")
    return {
        "schema_version": SCHEMA_VERSION,
        "evidence_ref": evidence_ref,
        "evidence_id": evidence_ref,
        "fact_id": evidence_ref,
        "ticker": ticker,
        "source_id": "sec_entity_public_float",
        "source_role": "valuation_price_in",
        "source_family": "secondary_market_public_context",
        "runtime_source_family": "secondary_market_public_context",
        "pack_role": "valuation_price_in",
        "authority_class": "valuation_price_in_signal",
        "signal_type": "sec_entity_public_float_context",
        "metric_name": "sec_entity_public_float",
        "value": value,
        "unit": str(fact.get("unit") or "USD"),
        "period": period,
        "as_of_date": period,
        "source_url": source_url,
        "citation": {
            "url": source_url,
            "title": f"{ticker} SEC CompanyFacts EntityPublicFloat valuation context",
            "span": f"public_float={value}; period={period}; filed={fact.get('filing_date')}",
        },
        "valuation_context": {
            "entity_public_float": value,
            "fact_period": period,
            "fact_source_ref": fact.get("evidence_ref") or fact.get("fact_id"),
            "concept": fact.get("concept"),
        },
        "allowed_claims": ["valuation_price_in_context", "public_float_context_from_sec_companyfacts"],
        "forbidden_claims": ["full_market_cap_without_share_count", "fair_value_truth", "consensus_ntm_without_commercial_source", "investment_recommendation"],
        "claim_boundary": "SEC EntityPublicFloat is company-reported public float context at the filing date; it is not complete market capitalization, target price, or consensus valuation.",
        "parser_status": "sec_companyfacts_entity_public_float_pass",
        "structured_context_type": "valuation_price_in_context",
        "generated_at": generated_at,
    }


def _market_cap_row(ticker: str, fact: Mapping[str, Any], generated_at: str) -> dict[str, Any]:
    period = str(fact.get("period_end") or fact.get("period") or "")
    value = _number(fact.get("value"))
    evidence_ref = str(fact.get("evidence_ref") or _stable_ref("s8_yahoo_market_cap", [ticker, period, value]))
    source_url = str(fact.get("source_url") or "")
    return {
        "schema_version": SCHEMA_VERSION,
        "evidence_ref": evidence_ref,
        "evidence_id": evidence_ref,
        "fact_id": evidence_ref,
        "ticker": ticker,
        "source_id": "yahoo_fundamentals_timeseries_market_cap",
        "source_role": "valuation_price_in",
        "source_family": "secondary_market_public_context",
        "runtime_source_family": "secondary_market_public_context",
        "pack_role": "valuation_price_in",
        "authority_class": "valuation_price_in_signal",
        "signal_type": "yahoo_fundamentals_market_cap_context",
        "metric_name": str(fact.get("metric_name") or "market_cap"),
        "value": value,
        "unit": str(fact.get("unit") or "market_cap_currency"),
        "period": period,
        "as_of_date": period,
        "source_url": source_url,
        "citation": {
            "url": source_url,
            "title": f"{ticker} Yahoo fundamentals-timeseries market-cap context",
            "span": f"market_cap={value}; period={period}; unit={fact.get('unit')}",
        },
        "valuation_context": {
            "market_cap": value,
            "fact_period": period,
            "provider": "yahoo_fundamentals_timeseries_unofficial_public_endpoint",
        },
        "allowed_claims": ["valuation_price_in_context", "market_cap_context_from_public_timeseries"],
        "forbidden_claims": ["fair_value_truth", "consensus_ntm_without_commercial_source", "investment_recommendation", "realtime_fund_flow"],
        "claim_boundary": "Yahoo fundamentals-timeseries market cap is delayed public market valuation context; it is not a target price, consensus estimate, fair-value truth, or real-time flow.",
        "parser_status": "yahoo_fundamentals_timeseries_market_cap_pass",
        "structured_context_type": "valuation_price_in_context",
        "generated_at": generated_at,
    }


def _fred_derivatives_row(ticker: str, fred: Mapping[str, Any], generated_at: str) -> dict[str, Any]:
    evidence_ref = _stable_ref("s8_fred_vix", [ticker, fred.get("date"), fred.get("value")])
    return {
        "schema_version": SCHEMA_VERSION,
        "evidence_ref": evidence_ref,
        "evidence_id": evidence_ref,
        "fact_id": evidence_ref,
        "ticker": ticker,
        "source_id": "fred_vix_market_volatility_regime",
        "source_role": "derivatives_market_signal",
        "source_family": "secondary_market_public_context",
        "runtime_source_family": "secondary_market_public_context",
        "pack_role": "derivatives_market_signal",
        "authority_class": "market_expectation_proxy",
        "signal_type": "fred_vix_market_volatility_regime",
        "metric_name": "vix_market_volatility_regime",
        "value": fred.get("value"),
        "unit": fred.get("unit") or "index_level",
        "period": fred.get("date") or "",
        "as_of_date": fred.get("date") or "",
        "source_url": fred.get("source_url") or FRED_CSV_URL.format(series_id="VIXCLS"),
        "citation": {"url": fred.get("source_url") or "", "title": str(fred.get("label") or "VIXCLS"), "span": f"value={fred.get('value')}; date={fred.get('date')}"},
        "derivatives_context": {"series_id": "VIXCLS", "series_label": fred.get("label"), "value": fred.get("value"), "date": fred.get("date")},
        "allowed_claims": ["market_wide_volatility_regime_context", "derivatives_market_regime_context"],
        "forbidden_claims": ["single_stock_option_positioning_without_option_chain", "realtime_gamma_without_licensed_source", "investment_recommendation"],
        "claim_boundary": "FRED VIXCLS is broad market volatility context only; it does not prove single-stock option OI, IV surface, gamma, or dealer positioning.",
        "parser_status": "fred_graph_csv_latest_observation_pass",
        "structured_context_type": "derivatives_market_regime_context",
        "generated_at": generated_at,
    }


def _fred_credit_row(ticker: str, fred_latest: Mapping[str, Mapping[str, Any]], generated_at: str) -> dict[str, Any]:
    ig = fred_latest.get("BAMLC0A0CM", {})
    hy = fred_latest.get("BAMLH0A0HYM2", {})
    date = str(ig.get("date") or hy.get("date") or "")
    evidence_ref = _stable_ref("s8_fred_credit", [ticker, date, ig.get("value"), hy.get("value")])
    context = {
        "investment_grade_oas": ig.get("value"),
        "investment_grade_oas_date": ig.get("date"),
        "high_yield_oas": hy.get("value"),
        "high_yield_oas_date": hy.get("date"),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "evidence_ref": evidence_ref,
        "evidence_id": evidence_ref,
        "fact_id": evidence_ref,
        "ticker": ticker,
        "source_id": "fred_credit_spread_regime",
        "source_role": "credit_funding",
        "source_family": "secondary_market_public_context",
        "runtime_source_family": "secondary_market_public_context",
        "pack_role": "credit_funding",
        "authority_class": "capital_feedback_signal",
        "signal_type": "fred_credit_spread_regime_context",
        "metric_name": "public_credit_spread_regime",
        "value": context,
        "unit": "percent_oas",
        "period": date,
        "as_of_date": date,
        "source_url": FRED_CSV_URL.format(series_id="BAMLC0A0CM"),
        "citation": {"url": FRED_CSV_URL.format(series_id="BAMLC0A0CM"), "title": "FRED ICE BofA credit spread regime", "span": json.dumps(context, sort_keys=True)},
        "credit_spread_context": context,
        "allowed_claims": ["credit_market_regime_context", "market_credit_spread_context"],
        "forbidden_claims": ["issuer_credit_spread_without_issuer_bond_source", "cds_claim_without_source", "investment_recommendation"],
        "claim_boundary": "FRED credit spreads are market-regime context only; they do not prove issuer-specific bond yield, CDS, rating action, or refinancing access.",
        "parser_status": "fred_graph_csv_latest_observation_pass",
        "structured_context_type": "credit_market_regime_context",
        "generated_at": generated_at,
    }


def build_summary(
    *,
    rows: list[dict[str, Any]],
    market_rows: list[Mapping[str, Any]],
    market_snapshot_rows: list[Mapping[str, Any]],
    market_bar_rows: list[Mapping[str, Any]],
    sec_financial_rows: list[Mapping[str, Any]],
    fred_latest: Mapping[str, Mapping[str, Any]],
    fred_failures: list[dict[str, str]],
    supplemental_valuation_facts: Mapping[str, Mapping[str, Any]],
    generated_at: str,
    output_rows: Path,
) -> dict[str, Any]:
    role_counts = Counter(str(row.get("pack_role") or "") for row in rows)
    source_counts = Counter(str(row.get("source_id") or "") for row in rows)
    ticker_counts = Counter(str(row.get("ticker") or "") for row in rows)
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "pass" if rows and not fred_failures else "pass_with_source_failures" if rows else "fail_no_rows",
        "row_count": len(rows),
        "ticker_count": len(ticker_counts),
        "role_counts": dict(sorted(role_counts.items())),
        "source_counts": dict(sorted(source_counts.items())),
        "market_input_count": len(market_rows),
        "market_snapshot_input_count": len(market_snapshot_rows),
        "market_bar_input_count": len(market_bar_rows),
        "sec_financial_input_count": len(sec_financial_rows),
        "fred_series_count": len(fred_latest),
        "fred_failure_count": len(fred_failures),
        "fred_failures": fred_failures,
        "supplemental_valuation_fact_count": len(supplemental_valuation_facts),
        "supplemental_valuation_fact_type_counts": dict(
            sorted(Counter(str(row.get("fact_type") or "") for row in supplemental_valuation_facts.values()).items())
        ),
        "output_rows": str(output_rows.relative_to(REPO_ROOT)) if output_rows.is_absolute() and output_rows.is_relative_to(REPO_ROOT) else str(output_rows),
        "claim_boundary": "Rows support bounded secondary-market/capital-feedback context only; they do not provide investment recommendations, issuer CDS, OPRA option feeds, borrow cost, or consensus valuation.",
    }


def _load_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + ("\n" if rows else ""), encoding="utf-8")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _number(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if value != value or value in (float("inf"), float("-inf")):
            return None
        return float(value)
    text = str(value).strip().replace(",", "")
    if not text or text == ".":
        return None
    try:
        result = float(text)
    except ValueError:
        return None
    if result != result or result in (float("inf"), float("-inf")):
        return None
    return result


def _market_price(row: Mapping[str, Any]) -> float | None:
    for key in ("close_price", "adjusted_close", "close", "value"):
        price = _number(row.get(key))
        if price is not None:
            return price
    reaction = row.get("market_reaction") if isinstance(row.get("market_reaction"), Mapping) else {}
    return _number(reaction.get("close_price"))


def _market_row_date(row: Mapping[str, Any]) -> str:
    return str(row.get("as_of_date") or row.get("date") or row.get("period") or "")


def _load_env_value(name: str) -> str:
    value = os.environ.get(name)
    if value:
        return value.strip().strip('"').strip("'")
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return ""
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith(f"{name}="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def _join_errors(*errors: str) -> str:
    return " | ".join(error for error in errors if error)


def _ticker(value: Any) -> str:
    return str(value or "").strip().upper()


def _stable_ref(prefix: str, parts: Iterable[Any]) -> str:
    digest = hashlib.sha1("|".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}:{digest}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
