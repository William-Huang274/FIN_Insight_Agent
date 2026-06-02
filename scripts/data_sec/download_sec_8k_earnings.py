from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from connectors import SecEdgarConnector, SecEdgarConnectorError  # noqa: E402


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def parse_csv_filter(raw: str | None) -> set[str] | None:
    if not raw:
        return None
    return {value.strip().upper() for value in raw.split(",") if value.strip()}


def parse_year_filter(raw: str | None) -> set[int] | None:
    if not raw:
        return None
    return {int(value.strip()) for value in raw.split(",") if value.strip()}


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download SEC 8-K earnings-release exhibits for a configured pilot universe."
    )
    parser.add_argument(
        "--config",
        default="configs/sec_tech_8k_earnings_pilot_2026_2027.yaml",
        help="Pilot universe YAML config.",
    )
    parser.add_argument(
        "--cache-dir",
        default=os.getenv("SEC_8K_EARNINGS_CACHE_DIR", "data/raw_private/sec_8k_earnings"),
        help="Private 8-K earnings-release cache directory.",
    )
    parser.add_argument(
        "--user-agent",
        default=os.getenv("SEC_USER_AGENT"),
        help="SEC User-Agent. Defaults to SEC_USER_AGENT.",
    )
    parser.add_argument("--tickers", help="Optional comma-separated ticker filter.")
    parser.add_argument("--years", help="Optional comma-separated filing-year filter.")
    parser.add_argument(
        "--after-date",
        help="Optional filing-date lower bound in YYYY-MM-DD; only later 8-K rows are selected.",
    )
    parser.add_argument("--limit", type=int, help="Optional max filings to process.")
    parser.add_argument("--dry-run", action="store_true", help="Print planned fetches only.")
    parser.add_argument(
        "--missing-output",
        default=os.getenv(
            "SEC_8K_EARNINGS_MISSING_OUTPUT",
            "data/processed_private/source_gaps/sec_tech_8k_earnings_pilot_missing_2026_2027.jsonl",
        ),
        help="Write structured missing-source records for planned 8-K earnings releases that cannot be selected.",
    )
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="Return success when some requested earnings-release 8-Ks are missing.",
    )
    parser.add_argument("--rate-limit", type=float, default=2.0)
    return parser.parse_args()


def main() -> None:
    load_env_file(REPO_ROOT / ".env")
    args = parse_args()
    config = load_config(REPO_ROOT / args.config)

    user_agent = args.user_agent or os.getenv("SEC_USER_AGENT") or "FinSight-Agent/0.1 contact@example.com"
    ticker_filter = parse_csv_filter(args.tickers)
    year_filter = parse_year_filter(args.years)
    years = [int(year) for year in config.get("years", [])]
    if year_filter is not None:
        years = [year for year in years if year in year_filter]
    companies = config.get("companies", [])
    if ticker_filter is not None:
        companies = [company for company in companies if str(company.get("ticker") or "").upper() in ticker_filter]

    connector = SecEdgarConnector(
        user_agent=user_agent,
        cache_dir=REPO_ROOT / args.cache_dir,
        log_path=REPO_ROOT / "data/logs/download_log.jsonl",
        rate_limit=args.rate_limit,
    )

    processed = 0
    failures: list[dict[str, Any]] = []
    for year in years:
        for company in companies:
            if args.limit is not None and processed >= args.limit:
                break
            ticker = str(company["ticker"]).upper()
            category = str(company.get("category") or "uncategorized")
            category_slug = str(company.get("category_slug") or category)
            planned = {
                "ticker": ticker,
                "year": year,
                "form_type": "8-K",
                "source_tier": "company_authored_unaudited_sec_filing",
                "category": category,
                "category_slug": category_slug,
            }
            if args.dry_run:
                print(json.dumps(planned, ensure_ascii=False))
                processed += 1
                continue
            try:
                cik = str(company.get("cik") or "").strip()
                if cik:
                    filing_meta = connector.find_earnings_release_8k(
                        cik=cik,
                        year=year,
                        after_date=args.after_date,
                    )
                    result = connector.download_earnings_release_8k(
                        filing_meta,
                        ticker=ticker,
                        category=category,
                        category_slug=category_slug,
                    )
                else:
                    result = connector.fetch_earnings_release_8k(
                        ticker=ticker,
                        year=year,
                        after_date=args.after_date,
                        category=category,
                        category_slug=category_slug,
                    )
                print(json.dumps(result, ensure_ascii=False))
            except SecEdgarConnectorError as exc:
                failure = build_missing_record(planned, exc, after_date=args.after_date)
                failures.append(failure)
                print(json.dumps(failure, ensure_ascii=False), file=sys.stderr)
            processed += 1
        if args.limit is not None and processed >= args.limit:
            break

    if failures and args.missing_output:
        write_jsonl(failures, REPO_ROOT / args.missing_output)

    if failures and not args.allow_missing:
        raise SystemExit(1)


def build_missing_record(
    planned: dict[str, Any],
    exc: SecEdgarConnectorError,
    *,
    after_date: str | None = None,
) -> dict[str, Any]:
    reason_code = getattr(exc, "reason_code", None) or classify_missing_reason(str(exc))
    diagnostics = getattr(exc, "diagnostics", {}) or {}
    return {
        "schema_version": "sec_8k_earnings_source_gap_v0.1",
        "source": "download_sec_8k_earnings",
        "status": "missing",
        **planned,
        "filing_year": planned.get("year"),
        "requested_item_codes": ["2.02"],
        "requested_exhibit_types": ["EX-99.1", "EX-99.01", "EX-99"],
        "after_date": after_date,
        "reason_code": reason_code,
        "reason": reason_code,
        "error": str(exc),
        "diagnostics": diagnostics,
    }


def classify_missing_reason(message: str) -> str:
    text = str(message or "").lower()
    if "ticker not found" in text:
        return "ticker_not_found_in_sec_reference"
    if "reason_code=" in text:
        return text.split("reason_code=", 1)[1].split(")", 1)[0].split(";", 1)[0].strip()
    if "no earnings-release 8-k" in text:
        return "earnings_release_8k_not_selected"
    return "sec_8k_earnings_download_error"


def write_jsonl(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False))
            f.write("\n")


if __name__ == "__main__":
    main()
