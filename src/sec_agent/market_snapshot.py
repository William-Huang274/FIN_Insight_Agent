from __future__ import annotations

import csv
import json
import math
import re
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = "sec_agent_market_snapshot_v0.1"
SOURCE_TIER = "market_snapshot"
DEFAULT_CURRENCY = "USD"
TRADING_DAY_WINDOWS = {
    "1d": 1,
    "5d": 5,
    "1m": 21,
    "3m": 63,
}
EVENT_WINDOW_DAYS = (1, 3, 5, 10)
SNAPSHOT_NUMERIC_FIELDS = (
    "close_price",
    "market_cap",
    "enterprise_value",
    "pe_ttm",
    "ev_sales_ttm",
    "ev_ebitda_ttm",
)


def normalize_market_snapshot_fixture(
    *,
    input_path: str | Path,
    output_root: str | Path,
    snapshot_id: str,
    as_of_date: str,
    provider: str = "manual_fixture",
    tickers: Iterable[str] | None = None,
    benchmark_tickers: Iterable[str] | None = None,
    currency: str = DEFAULT_CURRENCY,
) -> dict[str, Any]:
    """Normalize an offline market fixture into private JSONL/parquet artifacts."""
    output_root = Path(output_root)
    as_of = _parse_date(as_of_date)
    target_tickers = _upper_list(tickers)
    benchmark_set = set(_upper_list(benchmark_tickers))
    allowed_tickers = set(target_tickers) | benchmark_set if target_tickers or benchmark_set else set()

    source_rows = _read_rows(input_path)
    if not source_rows:
        raise ValueError(f"market snapshot fixture has no rows: {input_path}")

    bars = []
    row_errors = []
    seen_bar_keys = set()
    for row_idx, row in enumerate(source_rows, start=1):
        ticker = _ticker(row.get("ticker") or row.get("symbol"))
        if not ticker:
            row_errors.append({"row": row_idx, "type": "missing_ticker"})
            continue
        if allowed_tickers and ticker not in allowed_tickers:
            continue
        try:
            row_date = _parse_date(row.get("date"))
        except ValueError:
            row_errors.append({"row": row_idx, "type": "invalid_or_missing_date", "ticker": ticker})
            continue
        if row_date > as_of:
            continue
        close = _float_or_none(row.get("close"))
        adjusted_close = _float_or_none(row.get("adjusted_close") or row.get("adj_close")) or close
        if adjusted_close is None:
            row_errors.append({"row": row_idx, "type": "invalid_or_missing_price", "ticker": ticker, "date": row_date.isoformat()})
            continue
        bar_key = (ticker, row_date.isoformat())
        if bar_key in seen_bar_keys:
            row_errors.append({"row": row_idx, "type": "duplicate_ticker_date", "ticker": ticker, "date": row_date.isoformat()})
            continue
        seen_bar_keys.add(bar_key)
        close = close if close is not None else adjusted_close
        bar = {
            "schema_version": SCHEMA_VERSION,
            "snapshot_id": snapshot_id,
            "source_tier": SOURCE_TIER,
            "ticker": ticker,
            "date": row_date.isoformat(),
            "open": _float_or_none(row.get("open")),
            "high": _float_or_none(row.get("high")),
            "low": _float_or_none(row.get("low")),
            "close": close,
            "adjusted_close": adjusted_close,
            "volume": _int_or_none(row.get("volume")),
            "currency": str(row.get("currency") or currency or DEFAULT_CURRENCY),
            "provider": str(row.get("provider") or provider),
            "is_benchmark": ticker in benchmark_set,
            "source_url": str(row.get("source_url") or ""),
        }
        for field in ("market_cap", "enterprise_value", "pe_ttm", "ev_sales_ttm", "ev_ebitda_ttm"):
            bar[field] = _float_or_none(row.get(field))
        bars.append(bar)

    if row_errors:
        raise ValueError(
            "invalid market snapshot fixture rows: "
            + json.dumps(row_errors[:20], ensure_ascii=False, sort_keys=True)
        )
    if not bars:
        raise ValueError("market snapshot fixture has no usable rows after ticker/as_of filtering")

    bars.sort(key=lambda item: (item["ticker"], item["date"]))
    if not target_tickers:
        target_tickers = sorted({bar["ticker"] for bar in bars if not bar.get("is_benchmark")})
    if not target_tickers:
        raise ValueError("market snapshot fixture has no target tickers")

    latest_by_ticker: dict[str, dict[str, Any]] = {}
    for bar in bars:
        ticker = str(bar["ticker"])
        if ticker not in target_tickers:
            continue
        latest_by_ticker[ticker] = bar

    covered_tickers = {str(bar["ticker"]) for bar in bars}
    missing_targets = sorted(ticker for ticker in target_tickers if ticker not in latest_by_ticker)
    missing_benchmarks = sorted(ticker for ticker in benchmark_set if ticker not in covered_tickers)
    if missing_targets or missing_benchmarks:
        raise ValueError(
            "market snapshot fixture missing requested tickers: "
            + json.dumps(
                {
                    "missing_target_tickers": missing_targets,
                    "missing_benchmark_tickers": missing_benchmarks,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )

    snapshots = []
    for ticker in target_tickers:
        latest = latest_by_ticker.get(ticker)
        if not latest:
            continue
        field_status = {
            field: "provided" if latest.get(field) is not None else "missing_not_provided"
            for field in SNAPSHOT_NUMERIC_FIELDS
        }
        snapshots.append(
            {
                "schema_version": SCHEMA_VERSION,
                "snapshot_id": snapshot_id,
                "source_tier": SOURCE_TIER,
                "ticker": ticker,
                "as_of_date": as_of.isoformat(),
                "provider": str(latest.get("provider") or provider),
                "currency": str(latest.get("currency") or currency or DEFAULT_CURRENCY),
                "close_price": latest.get("adjusted_close"),
                "market_cap": latest.get("market_cap"),
                "enterprise_value": latest.get("enterprise_value"),
                "pe_ttm": latest.get("pe_ttm"),
                "ev_sales_ttm": latest.get("ev_sales_ttm"),
                "ev_ebitda_ttm": latest.get("ev_ebitda_ttm"),
                "field_status": field_status,
                "field_definitions": _default_field_definitions(),
                "source_boundary": f"market_snapshot; non-real-time; as_of_date={as_of.isoformat()}",
            }
        )

    paths = _market_paths(output_root, snapshot_id)
    _write_jsonl(paths["bars_jsonl"], bars)
    _write_jsonl(paths["snapshot_jsonl"], snapshots)
    _write_parquet_if_possible(paths["bars_jsonl"], paths["bars_parquet"])
    _write_parquet_if_possible(paths["snapshot_jsonl"], paths["snapshot_parquet"])
    metadata = {
        "schema_version": SCHEMA_VERSION,
        "snapshot_id": snapshot_id,
        "source_tier": SOURCE_TIER,
        "provider": provider,
        "as_of_date": as_of.isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "target_tickers": target_tickers,
        "benchmark_tickers": sorted(benchmark_set),
        "input_path": str(Path(input_path)),
        "bars_jsonl": str(paths["bars_jsonl"]),
        "snapshot_jsonl": str(paths["snapshot_jsonl"]),
        "bars_parquet": str(paths["bars_parquet"]),
        "snapshot_parquet": str(paths["snapshot_parquet"]),
        "bar_count": len(bars),
        "snapshot_count": len(snapshots),
        "license_note": "offline fixture; not for redistribution unless provider terms allow it",
    }
    _write_json(paths["metadata_json"], metadata)
    return metadata


def build_market_snapshot_catalog(
    *,
    output_root: str | Path,
    catalog_path: str | Path | None = None,
) -> dict[str, Any]:
    import duckdb

    output_root = Path(output_root)
    catalog_path = Path(catalog_path) if catalog_path else output_root / "catalog.duckdb"
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(catalog_path))
    _create_json_table(con, "market_daily_bars", output_root / "bars" / "*.jsonl")
    _create_json_table(con, "market_snapshots", output_root / "snapshots" / "*.jsonl")
    _create_json_table(con, "market_analytics", output_root / "analytics" / "*.jsonl")
    counts = {
        "market_daily_bars": _table_count(con, "market_daily_bars"),
        "market_snapshots": _table_count(con, "market_snapshots"),
        "market_analytics": _table_count(con, "market_analytics"),
    }
    con.close()
    return {
        "schema_version": SCHEMA_VERSION,
        "catalog_path": str(catalog_path),
        "table_counts": counts,
    }


def compute_market_analytics(
    *,
    bars_path: str | Path,
    snapshot_path: str | Path,
    output_path: str | Path,
    window: str = "3M",
    benchmark_ticker: str | None = None,
    tickers: Iterable[str] | None = None,
    events_path: str | Path | None = None,
) -> dict[str, Any]:
    bars = _read_jsonl(bars_path)
    snapshots = _read_jsonl(snapshot_path)
    selected = set(_upper_list(tickers)) if tickers else {
        str(row.get("ticker") or "").upper() for row in snapshots if row.get("ticker")
    }
    benchmark = _ticker(benchmark_ticker) if benchmark_ticker else ""
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for bar in bars:
        ticker = _ticker(bar.get("ticker"))
        if ticker:
            grouped[ticker].append(bar)
    for rows in grouped.values():
        rows.sort(key=lambda item: item["date"])

    snapshot_by_ticker = {_ticker(row.get("ticker")): row for row in snapshots}
    benchmark_returns = _return_bundle(grouped.get(benchmark, [])) if benchmark else {}
    valuation_rows = [row for row in snapshots if _ticker(row.get("ticker")) in selected]
    ev_sales_ranks = _peer_ranks(valuation_rows, "ev_sales_ttm")
    events_by_ticker = _read_market_events(events_path) if events_path else {}

    analytics = []
    for ticker in sorted(selected):
        rows = grouped.get(ticker, [])
        snapshot = snapshot_by_ticker.get(ticker, {})
        returns = _return_bundle(rows)
        max_drawdown = _max_drawdown(rows, TRADING_DAY_WINDOWS["3m"])
        volatility = _annualized_volatility(rows, TRADING_DAY_WINDOWS["3m"])
        relative_3m = None
        if benchmark_returns.get("return_3m") is not None and returns.get("return_3m") is not None:
            relative_3m = float(returns["return_3m"]) - float(benchmark_returns["return_3m"])
        rank_info = ev_sales_ranks.get(ticker, {})
        event_window, event_window_metadata, event_window_gaps = _event_window_returns(
            rows,
            events_by_ticker.get(ticker, []),
        )
        as_of_date = str(snapshot.get("as_of_date") or (rows[-1]["date"] if rows else ""))
        row = {
            "schema_version": SCHEMA_VERSION,
            "snapshot_id": str(snapshot.get("snapshot_id") or (rows[-1].get("snapshot_id") if rows else "")),
            "source_tier": SOURCE_TIER,
            "ticker": ticker,
            "as_of_date": as_of_date,
            "window": window.upper(),
            "provider": str(snapshot.get("provider") or (rows[-1].get("provider") if rows else "")),
            "market_reaction": {
                **returns,
                "relative_return_vs_benchmark_3m": relative_3m,
                "benchmark_ticker": benchmark or None,
                "max_drawdown_3m": max_drawdown,
                "volatility_3m": volatility,
            },
            "valuation_context": {
                "pe_ttm": snapshot.get("pe_ttm"),
                "ev_sales_ttm": snapshot.get("ev_sales_ttm"),
                "ev_ebitda_ttm": snapshot.get("ev_ebitda_ttm"),
                "peer_ev_sales_rank": rank_info.get("rank"),
                "peer_ev_sales_bucket": rank_info.get("bucket"),
            },
            "event_window": event_window,
            "event_window_metadata": event_window_metadata,
            "event_window_gaps": event_window_gaps,
            "derived_signals": _derived_signals(returns, relative_3m, max_drawdown, rank_info.get("bucket")),
            "source_boundary": f"market_snapshot; non-real-time; as_of_date={as_of_date}",
        }
        analytics.append(row)

    output_path = Path(output_path)
    _write_jsonl(output_path, analytics)
    _write_parquet_if_possible(output_path, output_path.with_suffix(".parquet"))
    return {
        "schema_version": SCHEMA_VERSION,
        "output_path": str(output_path),
        "analytics_count": len(analytics),
        "tickers": [row["ticker"] for row in analytics],
        "benchmark_ticker": benchmark or None,
        "events_path": str(events_path) if events_path else None,
    }


def build_market_evidence_pack(
    *,
    analytics_path: str | Path,
    snapshot_path: str | Path,
    output_path: str | Path,
    tickers: Iterable[str] | None = None,
    max_rows: int = 30,
) -> dict[str, Any]:
    analytics = _read_jsonl(analytics_path)
    snapshots = {_ticker(row.get("ticker")): row for row in _read_jsonl(snapshot_path)}
    selected = set(_upper_list(tickers)) if tickers else {_ticker(row.get("ticker")) for row in analytics}
    rows = []
    for item in analytics:
        ticker = _ticker(item.get("ticker"))
        if not ticker or ticker not in selected:
            continue
        snapshot = snapshots.get(ticker, {})
        field_refs = _market_field_refs(item, snapshot)
        text = _market_evidence_text(item, field_refs)
        object_id = f"MARKET_SNAPSHOT::{item.get('snapshot_id')}::{ticker}::{item.get('window')}::{item.get('as_of_date')}"
        rows.append(
            {
                "schema_version": "sec_agent_market_evidence_pack_v0.1",
                "object_id": object_id,
                "evidence_id": object_id,
                "source_type": SOURCE_TIER,
                "source_tier": SOURCE_TIER,
                "ticker": ticker,
                "as_of_date": item.get("as_of_date"),
                "snapshot_id": item.get("snapshot_id"),
                "provider": item.get("provider"),
                "window": item.get("window"),
                "text": text,
                "market_reaction": item.get("market_reaction") or {},
                "valuation_context": item.get("valuation_context") or {},
                "event_window": item.get("event_window") or {},
                "event_window_metadata": item.get("event_window_metadata") or [],
                "event_window_gaps": item.get("event_window_gaps") or [],
                "derived_signals": item.get("derived_signals") or [],
                "field_refs": field_refs,
                "source_boundary": item.get("source_boundary"),
            }
        )
        if len(rows) >= max_rows:
            break
    output_path = Path(output_path)
    _write_jsonl(output_path, rows)
    return {
        "schema_version": "sec_agent_market_evidence_pack_v0.1",
        "output_path": str(output_path),
        "row_count": len(rows),
        "tickers": [row["ticker"] for row in rows],
    }


def validate_market_snapshot(
    *,
    snapshot_path: str | Path,
    analytics_path: str | Path | None = None,
) -> dict[str, Any]:
    snapshots = _read_jsonl(snapshot_path)
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    seen = set()
    for idx, row in enumerate(snapshots, start=1):
        ticker = _ticker(row.get("ticker"))
        key = (row.get("snapshot_id"), ticker, row.get("as_of_date"))
        if key in seen:
            errors.append({"type": "duplicate_snapshot_row", "row": idx, "key": list(key)})
        seen.add(key)
        for field in ("snapshot_id", "ticker", "as_of_date", "provider", "source_tier"):
            if not row.get(field):
                errors.append({"type": "missing_required_field", "row": idx, "field": field})
        if row.get("source_tier") != SOURCE_TIER:
            errors.append({"type": "invalid_source_tier", "row": idx, "source_tier": row.get("source_tier")})
        for field in SNAPSHOT_NUMERIC_FIELDS:
            value = row.get(field)
            if value is not None and not isinstance(value, (int, float)):
                errors.append({"type": "non_numeric_snapshot_field", "row": idx, "field": field, "value": value})

    analytics_count = 0
    if analytics_path:
        analytics = _read_jsonl(analytics_path)
        analytics_count = len(analytics)
        for idx, row in enumerate(analytics, start=1):
            if not row.get("as_of_date"):
                errors.append({"type": "analytics_missing_as_of_date", "row": idx})
            if row.get("source_tier") != SOURCE_TIER:
                errors.append({"type": "analytics_invalid_source_tier", "row": idx})
            if not row.get("source_boundary"):
                warnings.append({"type": "analytics_missing_source_boundary", "row": idx})
            event_window = row.get("event_window") or {}
            if not isinstance(event_window, dict):
                errors.append({"type": "analytics_invalid_event_window", "row": idx})
            else:
                for field, value in event_window.items():
                    if value is not None and not isinstance(value, (int, float)):
                        errors.append({"type": "analytics_non_numeric_event_window", "row": idx, "field": field})

    return {
        "schema_version": SCHEMA_VERSION,
        "can_enter_market_snapshot_chain": not errors,
        "snapshot_count": len(snapshots),
        "analytics_count": analytics_count,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
    }


def _read_rows(path: str | Path) -> list[dict[str, Any]]:
    path = Path(path)
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as fh:
            return [dict(row) for row in csv.DictReader(fh)]
    if path.suffix.lower() == ".jsonl":
        return _read_jsonl(path)
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return [row for row in payload if isinstance(row, dict)]
        rows = payload.get("rows") if isinstance(payload, dict) else None
        return [row for row in rows or [] if isinstance(row, dict)]
    raise ValueError(f"unsupported fixture input: {path}")


def _read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    path = Path(path)
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _read_market_events(path: str | Path) -> dict[str, list[dict[str, Any]]]:
    path = Path(path)
    if not path.exists():
        raise ValueError(f"market event file not found: {path}")
    rows = _read_rows(path)
    if not rows:
        raise ValueError(f"market event file has no rows: {path}")
    errors = []
    seen_ticker_event_types = set()
    events: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for idx, row in enumerate(rows, start=1):
        ticker = _ticker(row.get("ticker") or row.get("symbol"))
        event_type = _event_type(row.get("event_type") or row.get("event_name") or row.get("type") or row.get("filing_type"))
        try:
            event_date = _parse_date(row.get("event_date") or row.get("date") or row.get("filed_date"))
        except ValueError:
            errors.append({"row": idx, "type": "invalid_or_missing_event_date", "ticker": ticker})
            continue
        if not ticker:
            errors.append({"row": idx, "type": "missing_event_ticker"})
            continue
        if not event_type:
            errors.append({"row": idx, "type": "missing_event_type", "ticker": ticker})
            continue
        key = (ticker, event_type)
        if key in seen_ticker_event_types:
            errors.append({"row": idx, "type": "duplicate_ticker_event_type", "ticker": ticker, "event_type": event_type})
            continue
        seen_ticker_event_types.add(key)
        events[ticker].append(
            {
                "event_type": event_type,
                "event_date": event_date.isoformat(),
                "source": str(row.get("source") or ""),
            }
        )
    if errors:
        raise ValueError(
            "invalid market event rows: "
            + json.dumps(errors[:20], ensure_ascii=False, sort_keys=True)
        )
    return events


def _write_jsonl(path: str | Path, rows: list[dict[str, Any]]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + ("\n" if rows else ""), encoding="utf-8")


def _write_json(path: str | Path, payload: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _write_parquet_if_possible(jsonl_path: Path, parquet_path: Path) -> None:
    if not jsonl_path.exists() or not jsonl_path.read_text(encoding="utf-8").strip():
        return
    try:
        import duckdb
    except Exception as exc:
        raise RuntimeError("duckdb is required to write market snapshot parquet artifacts") from exc
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    in_path = _sql_path(jsonl_path)
    out_path = _sql_path(parquet_path)
    con = duckdb.connect(":memory:")
    try:
        con.execute(f"COPY (SELECT * FROM read_json_auto('{in_path}')) TO '{out_path}' (FORMAT PARQUET)")
    finally:
        con.close()


def _create_json_table(con: Any, table_name: str, glob_path: Path) -> None:
    pattern = _sql_path(glob_path)
    if list(glob_path.parent.glob(glob_path.name)):
        con.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM read_json_auto('{pattern}')")
    else:
        con.execute(f"CREATE OR REPLACE TABLE {table_name} (empty_marker VARCHAR)")


def _table_count(con: Any, table_name: str) -> int:
    return int(con.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])


def _market_paths(output_root: Path, snapshot_id: str) -> dict[str, Path]:
    return {
        "bars_jsonl": output_root / "bars" / f"{snapshot_id}_daily_bars.jsonl",
        "bars_parquet": output_root / "bars" / f"{snapshot_id}_daily_bars.parquet",
        "snapshot_jsonl": output_root / "snapshots" / f"{snapshot_id}_snapshot.jsonl",
        "snapshot_parquet": output_root / "snapshots" / f"{snapshot_id}_snapshot.parquet",
        "metadata_json": output_root / "metadata" / f"{snapshot_id}_metadata.json",
    }


def _return_bundle(rows: list[dict[str, Any]]) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    for label, days in TRADING_DAY_WINDOWS.items():
        out[f"return_{label}"] = _trailing_return(rows, days)
    out["return_ytd"] = _ytd_return(rows)
    return out


def _trailing_return(rows: list[dict[str, Any]], days: int) -> float | None:
    if len(rows) <= days:
        return None
    end = _price(rows[-1])
    start = _price(rows[-1 - days])
    if start in (None, 0) or end is None:
        return None
    return (end / start) - 1.0


def _ytd_return(rows: list[dict[str, Any]]) -> float | None:
    if len(rows) < 2:
        return None
    end_date = _parse_date(rows[-1]["date"])
    same_year = [row for row in rows if _parse_date(row["date"]).year == end_date.year]
    if len(same_year) < 2:
        return None
    start = _price(same_year[0])
    end = _price(rows[-1])
    if start in (None, 0) or end is None:
        return None
    return (end / start) - 1.0


def _max_drawdown(rows: list[dict[str, Any]], days: int) -> float | None:
    window = rows[-days:] if len(rows) >= days else rows
    peak = None
    max_dd = 0.0
    for row in window:
        price = _price(row)
        if price is None:
            continue
        peak = price if peak is None else max(peak, price)
        if peak:
            max_dd = min(max_dd, (price / peak) - 1.0)
    return max_dd if peak is not None else None


def _annualized_volatility(rows: list[dict[str, Any]], days: int) -> float | None:
    window = rows[-days:] if len(rows) >= days else rows
    returns = []
    for prev, cur in zip(window, window[1:]):
        prev_price = _price(prev)
        cur_price = _price(cur)
        if prev_price in (None, 0) or cur_price is None:
            continue
        returns.append((cur_price / prev_price) - 1.0)
    if len(returns) < 2:
        return None
    mean = sum(returns) / len(returns)
    variance = sum((value - mean) ** 2 for value in returns) / (len(returns) - 1)
    return math.sqrt(variance) * math.sqrt(252)


def _event_window_returns(
    rows: list[dict[str, Any]],
    events: list[dict[str, Any]],
) -> tuple[dict[str, float], list[dict[str, Any]], list[dict[str, Any]]]:
    if not rows or not events:
        return {}, [], []
    dates = [_parse_date(row["date"]) for row in rows]
    returns: dict[str, float] = {}
    metadata = []
    gaps = []
    for event in sorted(events, key=lambda item: (item["event_type"], item["event_date"])):
        event_type = str(event["event_type"])
        event_date = _parse_date(event["event_date"])
        anchor_idx = next((idx for idx, row_date in enumerate(dates) if row_date >= event_date), None)
        if anchor_idx is None:
            gaps.append(
                {
                    "event_type": event_type,
                    "event_date": event_date.isoformat(),
                    "reason": "no_market_bar_on_or_after_event_date",
                }
            )
            continue
        anchor_price = _price(rows[anchor_idx])
        if anchor_price in (None, 0):
            gaps.append(
                {
                    "event_type": event_type,
                    "event_date": event_date.isoformat(),
                    "anchor_date": rows[anchor_idx]["date"],
                    "reason": "missing_anchor_price",
                }
            )
            continue
        metadata.append(
            {
                "event_type": event_type,
                "event_date": event_date.isoformat(),
                "anchor_date": rows[anchor_idx]["date"],
                "source": event.get("source") or "",
            }
        )
        for days in EVENT_WINDOW_DAYS:
            target_idx = anchor_idx + days
            field = f"{event_type}_return_{days}d"
            if target_idx >= len(rows):
                gaps.append(
                    {
                        "event_type": event_type,
                        "event_date": event_date.isoformat(),
                        "anchor_date": rows[anchor_idx]["date"],
                        "window": f"{days}d",
                        "reason": "insufficient_bars_after_event",
                    }
                )
                continue
            target_price = _price(rows[target_idx])
            if target_price is None:
                gaps.append(
                    {
                        "event_type": event_type,
                        "event_date": event_date.isoformat(),
                        "anchor_date": rows[anchor_idx]["date"],
                        "window": f"{days}d",
                        "reason": "missing_target_price",
                    }
                )
                continue
            returns[field] = (target_price / float(anchor_price)) - 1.0
    return returns, metadata, gaps


def _peer_ranks(rows: list[dict[str, Any]], field: str) -> dict[str, dict[str, Any]]:
    valued = [
        (_ticker(row.get("ticker")), _float_or_none(row.get(field)))
        for row in rows
    ]
    valued = [(ticker, value) for ticker, value in valued if ticker and value is not None]
    valued.sort(key=lambda item: item[1], reverse=True)
    total = len(valued)
    out = {}
    for index, (ticker, _) in enumerate(valued, start=1):
        percentile = index / total if total else 1.0
        if percentile <= 0.25:
            bucket = "top_quartile"
        elif percentile <= 0.5:
            bucket = "upper_middle"
        elif percentile <= 0.75:
            bucket = "lower_middle"
        else:
            bucket = "bottom_quartile"
        out[ticker] = {"rank": index, "bucket": bucket}
    return out


def _derived_signals(
    returns: dict[str, float | None],
    relative_3m: float | None,
    max_drawdown: float | None,
    valuation_bucket: str | None,
) -> list[str]:
    signals = []
    r3m = returns.get("return_3m")
    if r3m is not None:
        if r3m >= 0.05:
            signals.append("market_reaction_positive")
        elif r3m <= -0.05:
            signals.append("market_reaction_negative")
        else:
            signals.append("market_reaction_muted")
    if relative_3m is not None:
        signals.append("outperformed_benchmark_3m" if relative_3m > 0 else "underperformed_benchmark_3m")
    if max_drawdown is not None and max_drawdown <= -0.2:
        signals.append("drawdown_elevated")
    if valuation_bucket == "top_quartile":
        signals.append("valuation_premium_vs_peers")
    elif valuation_bucket == "bottom_quartile":
        signals.append("valuation_discount_vs_peers")
    return signals


def _market_field_refs(analytics: dict[str, Any], snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    refs = []
    snapshot_id = str(analytics.get("snapshot_id") or snapshot.get("snapshot_id") or "")
    ticker = str(analytics.get("ticker") or snapshot.get("ticker") or "")
    as_of_date = str(analytics.get("as_of_date") or snapshot.get("as_of_date") or "")
    for group_name in ("market_reaction", "valuation_context", "event_window"):
        group = analytics.get(group_name) or {}
        if not isinstance(group, dict):
            continue
        for field, value in group.items():
            if field == "benchmark_ticker" or value is None:
                continue
            refs.append(
                {
                    "field_ref": f"MARKET::{snapshot_id}::{ticker}::{field}::{as_of_date}",
                    "field_name": field,
                    "value": value,
                    "as_of_date": as_of_date,
                    "snapshot_id": snapshot_id,
                    "source": group_name,
                }
            )
    for field in ("close_price", "market_cap", "enterprise_value"):
        value = snapshot.get(field)
        if value is None:
            continue
        refs.append(
            {
                "field_ref": f"MARKET::{snapshot_id}::{ticker}::{field}::{as_of_date}",
                "field_name": field,
                "value": value,
                "as_of_date": as_of_date,
                "snapshot_id": snapshot_id,
                "source": "snapshot",
            }
        )
    return refs


def _market_evidence_text(analytics: dict[str, Any], field_refs: list[dict[str, Any]]) -> str:
    ticker = str(analytics.get("ticker") or "")
    as_of_date = str(analytics.get("as_of_date") or "")
    values = {ref["field_name"]: ref["value"] for ref in field_refs}
    fragments = [
        f"{ticker} market snapshot as of {as_of_date}",
    ]
    for field in ("return_3m", "relative_return_vs_benchmark_3m", "max_drawdown_3m", "volatility_3m", "pe_ttm", "ev_sales_ttm"):
        if field in values:
            fragments.append(f"{field}={_format_number(values[field])}")
    event_fields = sorted(field for field in values if field.endswith("_return_5d"))
    for field in event_fields[:2]:
        fragments.append(f"{field}={_format_number(values[field])}")
    signals = analytics.get("derived_signals") or []
    if signals:
        fragments.append("signals=" + ",".join(str(item) for item in signals[:4]))
    return "; ".join(fragments) + "."


def _default_field_definitions() -> dict[str, str]:
    return {
        "close_price": "adjusted close price at as_of_date",
        "market_cap": "provider supplied market capitalization at as_of_date",
        "enterprise_value": "provider supplied enterprise value at as_of_date",
        "pe_ttm": "provider supplied trailing twelve month price-to-earnings ratio",
        "ev_sales_ttm": "provider supplied trailing twelve month enterprise-value-to-sales ratio",
        "ev_ebitda_ttm": "provider supplied trailing twelve month enterprise-value-to-EBITDA ratio",
    }


def _price(row: dict[str, Any]) -> float | None:
    return _float_or_none(row.get("adjusted_close") or row.get("close"))


def _parse_date(value: Any) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    text = str(value or "").strip()
    if not text:
        raise ValueError("date value is required")
    return datetime.fromisoformat(text[:10]).date()


def _ticker(value: Any) -> str:
    return str(value or "").strip().upper()


def _event_type(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text[:64]


def _upper_list(values: Iterable[str] | None) -> list[str]:
    out = []
    seen = set()
    for value in values or []:
        ticker = _ticker(value)
        if ticker and ticker not in seen:
            out.append(ticker)
            seen.add(ticker)
    return out


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
    if math.isnan(result) or math.isinf(result):
        return None
    return result


def _int_or_none(value: Any) -> int | None:
    number = _float_or_none(value)
    return int(number) if number is not None else None


def _format_number(value: Any) -> str:
    number = _float_or_none(value)
    if number is None:
        return str(value)
    return f"{number:.6g}"


def _sql_path(path: Path) -> str:
    return str(path).replace("\\", "/").replace("'", "''")
