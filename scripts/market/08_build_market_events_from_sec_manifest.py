from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any


DEFAULT_OUTPUT_DIR = Path("data/raw_private/market/provider_snapshots")
EVENT_TYPE_BY_FORM = {
    "8-K": "8k_earnings_release",
    "10-Q": "latest_10q_filing",
    "10-K": "latest_10k_filing",
}
OUTPUT_FIELDS = (
    "ticker",
    "event_type",
    "event_date",
    "source",
    "form_type",
    "fiscal_year",
    "accession_number",
    "filing_url",
)


def _split_csv(value: str | None) -> list[str]:
    out = []
    seen = set()
    for item in (value or "").split(","):
        text = item.strip()
        if text and text.upper() not in seen:
            out.append(text)
            seen.add(text.upper())
    return out


def _tickers_from_config(path: str | None) -> list[str]:
    if not path:
        return []
    text = Path(path).read_text(encoding="utf-8")
    return [item.upper() for item in re.findall(r"^\s*-\s*ticker:\s*([A-Za-z0-9.\-]+)\s*$", text, flags=re.MULTILINE)]


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _row_value(row: dict[str, Any], field: str) -> Any:
    if row.get(field) is not None:
        return row.get(field)
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    return metadata.get(field)


def _date_text(value: Any) -> str:
    text = str(value or "").strip()
    return text[:10] if len(text) >= 10 else text


def _event_row(row: dict[str, Any], event_type: str) -> dict[str, Any] | None:
    ticker = str(_row_value(row, "ticker") or "").strip().upper()
    form_type = str(_row_value(row, "form_type") or "").strip().upper()
    event_date = _date_text(_row_value(row, "filing_date") or _row_value(row, "acceptance_datetime") or _row_value(row, "report_date"))
    if not ticker or not form_type or not event_date:
        return None
    return {
        "ticker": ticker,
        "event_type": event_type,
        "event_date": event_date,
        "source": "sec_manifest",
        "form_type": form_type,
        "fiscal_year": _row_value(row, "fiscal_year") or "",
        "accession_number": _row_value(row, "accession_number") or "",
        "filing_url": _row_value(row, "filing_url") or "",
    }


def build_events(
    *,
    manifest_paths: list[Path],
    tickers: list[str],
    years: list[int],
    form_types: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ticker_set = {ticker.upper() for ticker in tickers}
    year_set = set(years)
    form_set = {form.upper() for form in form_types}
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    skipped = []
    for path in manifest_paths:
        for row in _read_jsonl(path):
            ticker = str(_row_value(row, "ticker") or "").strip().upper()
            form_type = str(_row_value(row, "form_type") or "").strip().upper()
            fiscal_year_raw = _row_value(row, "fiscal_year")
            try:
                fiscal_year = int(fiscal_year_raw)
            except (TypeError, ValueError):
                fiscal_year = None
            if ticker_set and ticker not in ticker_set:
                continue
            if form_set and form_type not in form_set:
                continue
            if year_set and fiscal_year not in year_set:
                continue
            event_type = EVENT_TYPE_BY_FORM.get(form_type)
            if not event_type:
                skipped.append({"ticker": ticker, "form_type": form_type, "reason": "unsupported_form_type"})
                continue
            event = _event_row(row, event_type)
            if not event:
                skipped.append({"ticker": ticker, "form_type": form_type, "reason": "missing_event_fields"})
                continue
            key = (ticker, event_type)
            if key not in latest or str(event["event_date"]) > str(latest[key]["event_date"]):
                latest[key] = event
    return sorted(latest.values(), key=lambda item: (item["ticker"], item["event_type"])), skipped


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(OUTPUT_FIELDS))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build market event-window dates from SEC manifest filing dates.")
    parser.add_argument("--manifest-paths", required=True, help="Comma-separated JSONL manifest paths.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--tickers", default="")
    parser.add_argument("--tickers-config", default="")
    parser.add_argument("--years", default="")
    parser.add_argument("--form-types", default="10-Q,8-K")
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    manifest_paths = [Path(item) for item in _split_csv(args.manifest_paths)]
    missing = [str(path) for path in manifest_paths if not path.exists()]
    if missing:
        raise SystemExit("Missing manifest path(s): " + ", ".join(missing))
    tickers = [item.upper() for item in _split_csv(",".join(_tickers_from_config(args.tickers_config) + _split_csv(args.tickers)))]
    years = [int(item) for item in _split_csv(args.years)]
    form_types = [item.upper() for item in _split_csv(args.form_types)]
    rows, skipped = build_events(
        manifest_paths=manifest_paths,
        tickers=tickers,
        years=years,
        form_types=form_types,
    )
    output = Path(args.output)
    _write_csv(output, rows)
    summary = {
        "output": str(output),
        "manifest_paths": [str(path) for path in manifest_paths],
        "event_count": len(rows),
        "tickers": sorted({str(row["ticker"]) for row in rows}),
        "event_types": sorted({str(row["event_type"]) for row in rows}),
        "skipped_count": len(skipped),
        "skipped_sample": skipped[:20],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
