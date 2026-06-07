from __future__ import annotations

import argparse
import csv
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "external_reference"
SCHEMA_VERSION = "fin_agent_sp500_constituents_v0.1"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download current S&P 500 constituents into a small public reference CSV.")
    parser.add_argument("--source-url", default=DEFAULT_SOURCE_URL)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--output-csv", default="sp500_constituents.csv")
    parser.add_argument("--summary-output", default="sp500_constituents_summary_v0_1.json")
    parser.add_argument("--timeout-sec", type=int, default=30)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    downloaded_at_utc = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    html = _download_html(args.source_url, timeout_sec=args.timeout_sec)
    rows = parse_sp500_constituents_html(html, source_url=args.source_url, downloaded_at_utc=downloaded_at_utc)
    if len(rows) < 490:
        raise RuntimeError(f"Parsed too few S&P 500 constituent rows: {len(rows)}")

    output_dir = _resolve(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / args.output_csv
    summary_path = output_dir / args.summary_output
    _write_csv(csv_path, rows)
    summary = summarize_sp500_rows(rows, source_url=args.source_url, downloaded_at_utc=downloaded_at_utc)
    summary["outputs"] = {"csv": str(csv_path), "summary": str(summary_path)}
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def parse_sp500_constituents_html(html: str, *, source_url: str, downloaded_at_utc: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table", {"id": "constituents"})
    if table is None:
        tables = soup.find_all("table", class_="wikitable")
        table = tables[0] if tables else None
    if table is None:
        raise ValueError("Could not find S&P 500 constituents table.")

    headers = [_normalize_header(cell.get_text(" ", strip=True)) for cell in table.find_all("th")]
    rows: list[dict[str, Any]] = []
    for tr in table.find_all("tr")[1:]:
        cells = [cell.get_text(" ", strip=True) for cell in tr.find_all(["td", "th"])]
        if len(cells) < 2:
            continue
        payload = {headers[index] if index < len(headers) else f"col_{index}": value for index, value in enumerate(cells)}
        symbol = str(payload.get("symbol") or payload.get("ticker") or "").strip()
        company_name = str(payload.get("security") or payload.get("company") or "").strip()
        if not symbol or not company_name:
            continue
        ticker = normalize_sp500_symbol(symbol)
        cik = _normalize_cik(payload.get("cik"))
        rows.append(
            {
                "schema_version": SCHEMA_VERSION,
                "ticker": ticker,
                "raw_symbol": symbol,
                "company_name": company_name,
                "sector": str(payload.get("gics_sector") or payload.get("sector") or "").strip(),
                "sub_industry": str(payload.get("gics_sub_industry") or payload.get("sub_industry") or "").strip(),
                "headquarters": str(payload.get("headquarters_location") or payload.get("headquarters") or "").strip(),
                "date_added": str(payload.get("date_added") or "").strip(),
                "cik": cik,
                "founded": str(payload.get("founded") or "").strip(),
                "source_url": source_url,
                "downloaded_at_utc": downloaded_at_utc,
            }
        )
    return rows


def summarize_sp500_rows(rows: list[dict[str, Any]], *, source_url: str, downloaded_at_utc: str) -> dict[str, Any]:
    tickers = [row["ticker"] for row in rows]
    ciks = [row["cik"] for row in rows if row.get("cik")]
    duplicate_tickers = sorted({ticker for ticker in tickers if tickers.count(ticker) > 1})
    duplicate_ciks = sorted({cik for cik in ciks if ciks.count(cik) > 1})
    return {
        "schema_version": "fin_agent_sp500_constituents_download_summary_v0.1",
        "status": "completed",
        "source_url": source_url,
        "downloaded_at_utc": downloaded_at_utc,
        "row_count": len(rows),
        "unique_ticker_count": len(set(tickers)),
        "unique_cik_count": len(set(ciks)),
        "missing_cik_count": sum(1 for row in rows if not row.get("cik")),
        "duplicate_tickers": duplicate_tickers,
        "duplicate_ciks": duplicate_ciks,
        "dedupe_note": "S&P 500 can contain multiple share-class symbols for the same company; downstream universe builder deduplicates by CIK.",
    }


def normalize_sp500_symbol(value: Any) -> str:
    text = str(value or "").upper().strip()
    return text.replace(".", "-")


def _download_html(source_url: str, *, timeout_sec: int) -> str:
    headers = {
        "User-Agent": "FIN_Insight_Agent data-expansion diagnostic (contact: local development)",
    }
    response = requests.get(source_url, headers=headers, timeout=timeout_sec)
    response.raise_for_status()
    time.sleep(0.2)
    return response.text


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "schema_version",
        "ticker",
        "raw_symbol",
        "company_name",
        "sector",
        "sub_industry",
        "headquarters",
        "date_added",
        "cik",
        "founded",
        "source_url",
        "downloaded_at_utc",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _normalize_header(value: str) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("&", "and")
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text


def _normalize_cik(value: Any) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    return digits.zfill(10) if digits else ""


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


if __name__ == "__main__":
    raise SystemExit(main())
