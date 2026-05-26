from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

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


def parse_csv_list(raw: str | None) -> list[str] | None:
    if not raw:
        return None
    return [value.strip().upper() for value in raw.split(",") if value.strip()]


def config_form_types(config: dict[str, Any], override: str | None = None) -> list[str]:
    values = parse_csv_list(override)
    if values:
        return values
    configured = config.get("form_types")
    if isinstance(configured, list):
        values = [str(value).strip().upper() for value in configured if str(value).strip()]
        if values:
            return values
    form_type = str(config.get("form_type") or "10-K").strip().upper()
    return [form_type]


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download SEC filing HTML files for a configured universe."
    )
    parser.add_argument(
        "--config",
        default="configs/sec_tech_universe.yaml",
        help="Universe YAML config.",
    )
    parser.add_argument(
        "--cache-dir",
        default=os.getenv("SEC_CACHE_DIR", "data/raw_private/sec"),
        help="Private SEC cache directory.",
    )
    parser.add_argument(
        "--user-agent",
        default=os.getenv("SEC_USER_AGENT"),
        help="SEC User-Agent. Defaults to SEC_USER_AGENT.",
    )
    parser.add_argument("--tickers", help="Optional comma-separated ticker filter.")
    parser.add_argument("--years", help="Optional comma-separated fiscal year filter.")
    parser.add_argument(
        "--form-types",
        help="Optional comma-separated SEC form type filter. Defaults to config form_types/form_type.",
    )
    parser.add_argument("--limit", type=int, help="Optional max filings to process.")
    parser.add_argument("--dry-run", action="store_true", help="Print planned downloads only.")
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="Return success when some requested filings are missing; missing filings are printed to stderr as coverage gaps.",
    )
    parser.add_argument("--rate-limit", type=float, default=2.0)
    return parser.parse_args()


def main() -> None:
    load_env_file(REPO_ROOT / ".env")
    args = parse_args()
    config = load_config(REPO_ROOT / args.config)

    user_agent = args.user_agent or os.getenv("SEC_USER_AGENT")
    if not user_agent:
        user_agent = "FinSight-Agent/0.1 contact@example.com"

    ticker_filter = parse_csv_filter(args.tickers)
    year_filter = {int(value) for value in args.years.split(",")} if args.years else None
    form_types = config_form_types(config, args.form_types)
    years = [int(year) for year in config["years"]]
    if year_filter is not None:
        years = [year for year in years if year in year_filter]

    companies = config["companies"]
    if ticker_filter is not None:
        companies = [
            company
            for company in companies
            if company["ticker"].upper() in ticker_filter
        ]

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
            ticker = company["ticker"].upper()
            category = company["category"]
            category_slug = company["category_slug"]
            for form_type in form_types:
                if args.limit is not None and processed >= args.limit:
                    break
                planned_path = (
                    REPO_ROOT
                    / args.cache_dir
                    / str(year)
                    / category_slug
                    / ticker
                    / f"{form_type}.html"
                )
                if args.dry_run:
                    print(
                        json.dumps(
                            {
                                "ticker": ticker,
                                "year": year,
                                "form_type": form_type,
                                "category": category,
                                "planned_path": str(planned_path),
                            },
                            ensure_ascii=False,
                        )
                    )
                    processed += 1
                    continue

                try:
                    result = connector.fetch_filing(
                        ticker=ticker,
                        form_type=form_type,
                        year=year,
                        category=category,
                        category_slug=category_slug,
                    )
                    print(json.dumps(result, ensure_ascii=False))
                except SecEdgarConnectorError as exc:
                    failure = {
                        "ticker": ticker,
                        "year": year,
                        "form_type": form_type,
                        "category": category,
                        "error": str(exc),
                    }
                    failures.append(failure)
                    print(json.dumps(failure, ensure_ascii=False), file=sys.stderr)
                processed += 1
        if args.limit is not None and processed >= args.limit:
            break

    if failures and not args.allow_missing:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
