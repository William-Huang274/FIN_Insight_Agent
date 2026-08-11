from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]

SEC_COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_SUBMISSION_FILE_URL = "https://data.sec.gov/submissions/{file_name}"
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"

EARNINGS_TERMS = (
    "earnings",
    "financial results",
    "quarterly results",
    "annual results",
    "results of operations",
    "reports results",
    "announces results",
    "press release",
)


@dataclass(frozen=True)
class CompanyRequirement:
    ticker: str
    source_sets: tuple[str, ...]
    packs: tuple[str, ...]
    priority: str | None = None
    target_forms: tuple[str, ...] = ()
    cik: str | None = None


class SecMetadataClient:
    def __init__(
        self,
        *,
        cache_dir: Path,
        user_agent: str,
        rate_limit: float,
        timeout: int,
        max_historical_files: int,
    ) -> None:
        self.cache_dir = cache_dir
        self.user_agent = user_agent
        self.timeout = timeout
        self.max_historical_files = max_historical_files
        self.min_interval = 1.0 / rate_limit if rate_limit > 0 else 0.0
        self._last_request_ts = 0.0
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": user_agent,
                "Accept": "application/json,text/csv,*/*",
                "Accept-Encoding": "gzip, deflate",
            }
        )

    def get_ticker_map(self) -> dict[str, str]:
        path = self.cache_dir / "_reference" / "company_tickers.json"
        data = self._get_json(SEC_COMPANY_TICKERS_URL, path)
        ticker_map: dict[str, str] = {}
        for row in data.values():
            ticker = str(row.get("ticker") or "").upper().strip()
            cik = row.get("cik_str")
            if ticker and cik is not None:
                ticker_map[ticker] = f"{int(cik):010d}"
        return ticker_map

    def get_submission_rows(self, cik: str) -> list[dict[str, Any]]:
        submissions = self.get_company_submissions(cik)
        rows = self._rows_from_block(submissions.get("filings", {}).get("recent", {}), source="recent")
        for index, file_info in enumerate(submissions.get("filings", {}).get("files", []) or []):
            if index >= self.max_historical_files:
                break
            file_name = file_info.get("name")
            if not file_name:
                continue
            block = self.get_company_submission_file(str(file_name))
            rows.extend(self._rows_from_block(block, source=str(file_name)))
        rows.sort(key=lambda row: str(row.get("filing_date") or ""), reverse=True)
        return rows

    def get_company_submissions(self, cik: str) -> dict[str, Any]:
        normalized = f"{int(cik):010d}"
        path = self.cache_dir / "_reference" / "submissions" / f"CIK{normalized}.json"
        return self._get_json(SEC_SUBMISSIONS_URL.format(cik=normalized), path)

    def get_company_submission_file(self, file_name: str) -> dict[str, Any]:
        path = self.cache_dir / "_reference" / "submissions" / file_name
        return self._get_json(SEC_SUBMISSION_FILE_URL.format(file_name=file_name), path)

    def _get_json(self, url: str, cache_path: Path) -> dict[str, Any]:
        if cache_path.exists():
            return json.loads(cache_path.read_text(encoding="utf-8"))
        self._rate_limit()
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return data

    def _rate_limit(self) -> None:
        if self.min_interval <= 0:
            return
        elapsed = time.time() - self._last_request_ts
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_request_ts = time.time()

    @staticmethod
    def _rows_from_block(block: dict[str, Any], *, source: str) -> list[dict[str, Any]]:
        forms = block.get("form", []) or []
        rows: list[dict[str, Any]] = []
        for index, form in enumerate(forms):
            rows.append(
                {
                    "form": str(form or "").upper().strip(),
                    "filing_date": _value_at(block, "filingDate", index),
                    "report_date": _value_at(block, "reportDate", index),
                    "accession_number": _value_at(block, "accessionNumber", index),
                    "primary_document": _value_at(block, "primaryDocument", index),
                    "primary_doc_description": _value_at(block, "primaryDocDescription", index),
                    "items": _value_at(block, "items", index),
                    "source_block": source,
                }
            )
        return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe SEC, market, and industry-source availability for sector-depth research coverage."
    )
    parser.add_argument("--sector-config", default="configs/sector_depth_packs_v0_2.yaml")
    parser.add_argument("--foreign-config", default="configs/foreign_issuer_source_family_canary_v0_2.yaml")
    parser.add_argument("--industry-config", default="configs/industry_data_source_families_v0_2.yaml")
    parser.add_argument("--full128-additions-config", default="configs/sec_investment_coverage_full128_us_additions_v0_2.yaml")
    parser.add_argument(
        "--8k-additions-config",
        dest="eight_k_additions_config",
        default="configs/sec_investment_coverage_8k_earnings_full128_us_additions_v0_2.yaml",
    )
    parser.add_argument("--cache-dir", default=os.getenv("SEC_CACHE_DIR", "data/raw_private/sec"))
    parser.add_argument("--user-agent", default=os.getenv("SEC_USER_AGENT") or "FinSight-Agent/0.2 availability-probe contact@example.com")
    parser.add_argument("--rate-limit", type=float, default=8.0)
    parser.add_argument("--timeout-s", type=int, default=20)
    parser.add_argument("--max-historical-files", type=int, default=30)
    parser.add_argument("--tickers", help="Optional comma-separated ticker filter for SEC and market probes.")
    parser.add_argument("--sec-limit", type=int, help="Optional max companies for SEC probe smoke.")
    parser.add_argument("--skip-sec", action="store_true")
    parser.add_argument("--skip-market-live", action="store_true")
    parser.add_argument("--skip-industry-live", action="store_true")
    parser.add_argument("--output-json", default=_default_report_path("json"))
    parser.add_argument("--output-md", default=_default_report_path("md"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ticker_filter = _parse_ticker_filter(args.tickers)
    loaded = load_inputs(args)
    requirements = build_company_requirements(loaded, ticker_filter=ticker_filter)
    now = datetime.now(timezone.utc).isoformat()

    report: dict[str, Any] = {
        "schema_version": "sector_depth_source_availability_v0.2",
        "generated_at": now,
        "inputs": {
            "sector_config": args.sector_config,
            "foreign_config": args.foreign_config,
            "industry_config": args.industry_config,
            "full128_additions_config": args.full128_additions_config,
            "8k_additions_config": args.eight_k_additions_config,
            "sec_limit": args.sec_limit,
            "tickers": sorted(ticker_filter) if ticker_filter else None,
            "max_historical_files": args.max_historical_files,
            "market_live_probe": not args.skip_market_live,
            "industry_live_probe": not args.skip_industry_live,
        },
        "company_requirement_count": len(requirements),
        "sector_packs": summarize_sector_pack_requirements(loaded["sector_config"]),
        "source_family_contract": summarize_source_family_contract(loaded),
        "sec_probe": None,
        "market_probe": None,
        "industry_probe": None,
        "source_gaps": [],
        "recommendations": [],
    }

    if args.skip_sec:
        report["sec_probe"] = {"status": "skipped"}
    else:
        sec_requirements = requirements[: args.sec_limit] if args.sec_limit else requirements
        report["sec_probe"] = probe_sec_availability(sec_requirements, args)
        report["source_gaps"].extend(report["sec_probe"].get("source_gaps", []))

    market_tickers = [requirement.ticker for requirement in requirements]
    report["market_probe"] = probe_market_availability(
        market_tickers,
        skip_live=args.skip_market_live,
        timeout=args.timeout_s,
    )
    report["source_gaps"].extend(report["market_probe"].get("source_gaps", []))

    report["industry_probe"] = probe_industry_sources(
        loaded["industry_config"],
        skip_live=args.skip_industry_live,
        timeout=args.timeout_s,
    )
    report["source_gaps"].extend(report["industry_probe"].get("source_gaps", []))

    report["sector_pack_availability"] = build_sector_pack_availability(report)
    report["recommendations"] = build_recommendations(report)

    output_json = REPO_ROOT / args.output_json
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    output_md = REPO_ROOT / args.output_md
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(render_markdown_report(report), encoding="utf-8")

    print(json.dumps({"json": str(output_json), "markdown": str(output_md)}, ensure_ascii=False))


def load_inputs(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "sector_config": _load_yaml(REPO_ROOT / args.sector_config),
        "foreign_config": _load_yaml(REPO_ROOT / args.foreign_config),
        "industry_config": _load_yaml(REPO_ROOT / args.industry_config),
        "full128_additions_config": _load_yaml(REPO_ROOT / args.full128_additions_config),
        "8k_additions_config": _load_yaml(REPO_ROOT / args.eight_k_additions_config),
    }


def build_company_requirements(
    loaded: dict[str, Any],
    *,
    ticker_filter: set[str] | None,
) -> list[CompanyRequirement]:
    merged: dict[str, dict[str, Any]] = {}

    cik_overrides = {
        str(key).upper(): str(value)
        for key, value in (
            (loaded["sector_config"].get("selection_policy", {}) or {}).get("cik_overrides", {}) or {}
        ).items()
    }

    def add(
        ticker: str,
        source_set: str,
        pack: str | None = None,
        priority: str | None = None,
        forms: list[str] | None = None,
        cik: str | None = None,
    ) -> None:
        ticker_upper = str(ticker or "").upper().strip()
        if not ticker_upper:
            return
        if ticker_filter and ticker_upper not in ticker_filter:
            return
        entry = merged.setdefault(
            ticker_upper,
            {"source_sets": set(), "packs": set(), "priorities": set(), "forms": set()},
        )
        if cik or cik_overrides.get(ticker_upper):
            entry["cik"] = str(cik or cik_overrides.get(ticker_upper) or "").strip()
        entry["source_sets"].add(source_set)
        if pack:
            entry["packs"].add(pack)
        if priority:
            entry["priorities"].add(priority)
        for form in forms or []:
            entry["forms"].add(str(form).upper().strip())

    for company in loaded["full128_additions_config"].get("companies", []) or []:
        add(company.get("ticker"), "full128_us_addition", forms=["10-K", "10-Q", "8-K"], cik=company.get("cik"))

    for pack in loaded["sector_config"].get("packs", []) or []:
        pack_id = str(pack.get("pack_id") or "")
        candidates = pack.get("candidate_tickers", {}) or {}
        for priority in ("p0", "p1"):
            for ticker in candidates.get(priority, []) or []:
                add(ticker, "sector_depth_pack", pack=pack_id, priority=priority, forms=["10-K", "10-Q", "8-K"])

    for company in loaded["foreign_config"].get("canary_companies", []) or []:
        forms = [str(value).upper().strip() for value in company.get("target_forms", []) or []]
        add(company.get("ticker"), "foreign_issuer_canary", pack="foreign_source_family_canary", priority="canary", forms=forms, cik=company.get("cik"))

    requirements: list[CompanyRequirement] = []
    for ticker, entry in sorted(merged.items()):
        priorities = sorted(entry["priorities"])
        requirements.append(
            CompanyRequirement(
                ticker=ticker,
                source_sets=tuple(sorted(entry["source_sets"])),
                packs=tuple(sorted(entry["packs"])),
                priority=priorities[0] if priorities else None,
                target_forms=tuple(sorted(entry["forms"])),
                cik=entry.get("cik"),
            )
        )
    return requirements


def summarize_sector_pack_requirements(config: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for pack in config.get("packs", []) or []:
        candidates = pack.get("candidate_tickers", {}) or {}
        p0 = [str(value).upper() for value in candidates.get("p0", []) or []]
        p1 = [str(value).upper() for value in candidates.get("p1", []) or []]
        rows.append(
            {
                "pack_id": pack.get("pack_id"),
                "industry_group": pack.get("industry_group"),
                "p0_tickers": p0,
                "p1_tickers": p1,
                "p0_count": len(p0),
                "p1_count": len(p1),
                "candidate_count": len(set(p0 + p1)),
                "required_source_families": pack.get("required_source_families", []),
                "primary_metric_families": pack.get("primary_metric_families", []),
            }
        )
    return rows


def summarize_source_family_contract(loaded: dict[str, Any]) -> dict[str, Any]:
    industry_defined = {
        str(row.get("source_family"))
        for row in loaded["industry_config"].get("source_families", []) or []
        if row.get("source_family")
    }
    sector_required = {
        str(source_family)
        for pack in loaded["sector_config"].get("packs", []) or []
        for source_family in pack.get("required_source_families", []) or []
    }
    missing_industry_definitions = sorted(
        source_family
        for source_family in sector_required
        if source_family.startswith("industry_") and source_family not in industry_defined
    )
    return {
        "industry_source_families_defined": sorted(industry_defined),
        "sector_required_source_families": sorted(sector_required),
        "missing_industry_source_family_definitions": missing_industry_definitions,
        "foreign_source_families": loaded["foreign_config"].get("source_families", []),
    }


def probe_sec_availability(requirements: list[CompanyRequirement], args: argparse.Namespace) -> dict[str, Any]:
    client = SecMetadataClient(
        cache_dir=REPO_ROOT / args.cache_dir,
        user_agent=args.user_agent,
        rate_limit=args.rate_limit,
        timeout=args.timeout_s,
        max_historical_files=args.max_historical_files,
    )
    results: list[dict[str, Any]] = []
    source_gaps: list[dict[str, Any]] = []
    ticker_map = client.get_ticker_map()
    for index, requirement in enumerate(requirements, start=1):
        ticker = requirement.ticker
        row: dict[str, Any] = {
            "ticker": ticker,
            "source_sets": list(requirement.source_sets),
            "packs": list(requirement.packs),
            "priority": requirement.priority,
            "target_forms": list(requirement.target_forms),
            "status": "unknown",
        }
        cik = requirement.cik or ticker_map.get(ticker)
        if not cik:
            row.update({"status": "missing", "reason": "ticker_not_found_in_sec_company_tickers"})
            source_gaps.append(_gap(ticker, "sec", "ticker_not_found_in_sec_company_tickers", row))
            results.append(row)
            continue
        row["cik"] = cik
        try:
            filings = client.get_submission_rows(cik)
        except Exception as exc:  # noqa: BLE001
            row.update({"status": "error", "reason": "sec_submissions_request_failed", "error": str(exc)})
            source_gaps.append(_gap(ticker, "sec", "sec_submissions_request_failed", row))
            results.append(row)
            continue

        row.update(_summarize_sec_forms(requirement, filings))
        row["status"] = "available" if not row.get("missing_required_forms") else "partial"
        for missing in row.get("missing_required_forms", []):
            source_gaps.append(_gap(ticker, "sec", str(missing), row))
        results.append(row)
        if index % 25 == 0:
            print(f"[sec] probed {index}/{len(requirements)} companies", file=sys.stderr)

    return {
        "status": "completed",
        "company_count": len(results),
        "available_count": sum(1 for row in results if row.get("status") == "available"),
        "partial_count": sum(1 for row in results if row.get("status") == "partial"),
        "missing_or_error_count": sum(1 for row in results if row.get("status") in {"missing", "error"}),
        "results": results,
        "source_gaps": source_gaps,
        "note": "8-K earnings availability is metadata-level: Item 2.02 or earnings terms in SEC submissions, not exhibit-download validation.",
    }


def _summarize_sec_forms(requirement: CompanyRequirement, filings: list[dict[str, Any]]) -> dict[str, Any]:
    forms = set(requirement.target_forms)
    missing: list[str] = []
    summary: dict[str, Any] = {
        "filing_rows_seen": len(filings),
    }
    if {"10-K", "10-Q", "8-K"} & forms:
        annual = annual_10k_coverage(filings, years=(2023, 2024, 2025))
        latest_q = latest_form(filings, "10-Q")
        earnings = earnings_8k_coverage(filings, filing_years=(2026, 2027))
        summary.update(
            {
                "annual_10k": annual,
                "latest_10q": latest_q,
                "earnings_8k": earnings,
            }
        )
        for year, value in annual.items():
            if not value:
                missing.append(f"missing_10k_fy{year}")
        if not latest_q:
            missing.append("missing_latest_10q")
        if not earnings.get("2026") and not earnings.get("2027"):
            missing.append("missing_2026_or_2027_earnings_8k_metadata_candidate")

    foreign_forms = [form for form in forms if form in {"20-F", "6-K", "40-F"}]
    if foreign_forms:
        foreign = {form: latest_form(filings, form) for form in foreign_forms}
        summary["foreign_forms"] = foreign
        for form, value in foreign.items():
            if not value:
                missing.append(f"missing_{form.lower().replace('-', '_')}")

    summary["missing_required_forms"] = missing
    return summary


def annual_10k_coverage(filings: list[dict[str, Any]], *, years: tuple[int, ...]) -> dict[str, dict[str, Any] | None]:
    rows = [row for row in filings if row.get("form") == "10-K"]
    coverage: dict[str, dict[str, Any] | None] = {}
    for year in years:
        match = None
        for row in rows:
            fiscal_year = _date_year(row.get("report_date")) or _date_year(row.get("filing_date"))
            if fiscal_year == year:
                match = compact_filing_row(row)
                break
        coverage[str(year)] = match
    return coverage


def latest_form(filings: list[dict[str, Any]], form: str) -> dict[str, Any] | None:
    rows = [row for row in filings if row.get("form") == form]
    rows.sort(key=lambda row: str(row.get("filing_date") or ""), reverse=True)
    return compact_filing_row(rows[0]) if rows else None


def earnings_8k_coverage(filings: list[dict[str, Any]], *, filing_years: tuple[int, ...]) -> dict[str, dict[str, Any] | None]:
    coverage: dict[str, dict[str, Any] | None] = {}
    rows = [row for row in filings if row.get("form") == "8-K"]
    for year in filing_years:
        match = None
        for row in rows:
            filing_date = str(row.get("filing_date") or "")
            if not filing_date.startswith(str(year)):
                continue
            if _looks_like_earnings_8k(row):
                match = compact_filing_row(row)
                break
        coverage[str(year)] = match
    return coverage


def compact_filing_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "form": row.get("form"),
        "filing_date": row.get("filing_date"),
        "report_date": row.get("report_date"),
        "accession_number": row.get("accession_number"),
        "primary_doc_description": row.get("primary_doc_description"),
        "items": row.get("items"),
    }


def _looks_like_earnings_8k(row: dict[str, Any]) -> bool:
    items = str(row.get("items") or "")
    description = f"{row.get('primary_doc_description') or ''} {row.get('primary_document') or ''}".lower()
    return "2.02" in items or any(term in description for term in EARNINGS_TERMS)


def probe_market_availability(
    tickers: list[str],
    *,
    skip_live: bool,
    timeout: int,
) -> dict[str, Any]:
    tickers_unique = sorted(set(tickers))
    local = load_local_market_ticker_index()
    results: list[dict[str, Any]] = []
    source_gaps: list[dict[str, Any]] = []
    for index, ticker in enumerate(tickers_unique, start=1):
        local_info = local.get(ticker, {})
        row: dict[str, Any] = {
            "ticker": ticker,
            "local_market_rows": int(local_info.get("rows") or 0),
            "local_artifacts": sorted(local_info.get("artifacts") or []),
            "live_yahoo_chart": None,
        }
        if skip_live:
            row["status"] = "available_local" if row["local_market_rows"] else "not_checked_live"
        else:
            row["live_yahoo_chart"] = probe_yahoo_chart(ticker, timeout=timeout)
            if row["live_yahoo_chart"].get("status") == "available":
                row["status"] = "available_live"
            elif row["local_market_rows"]:
                row["status"] = "available_local"
            else:
                row["status"] = "missing"
                source_gaps.append(_gap(ticker, "market_snapshot", "market_snapshot_not_available", row))
        results.append(row)
        if not skip_live and index % 25 == 0:
            print(f"[market] probed {index}/{len(tickers_unique)} tickers", file=sys.stderr)
    return {
        "status": "completed",
        "ticker_count": len(results),
        "available_count": sum(1 for row in results if str(row.get("status")).startswith("available")),
        "missing_count": sum(1 for row in results if row.get("status") == "missing"),
        "results": results,
        "source_gaps": source_gaps,
    }


def load_local_market_ticker_index() -> dict[str, dict[str, Any]]:
    roots = [
        REPO_ROOT / "data" / "processed_private" / "market" / "evidence_packs",
        REPO_ROOT / "data" / "processed_private" / "market" / "snapshots",
        REPO_ROOT / "data" / "processed_private" / "market" / "analytics",
    ]
    index: dict[str, dict[str, Any]] = defaultdict(lambda: {"rows": 0, "artifacts": set()})
    for root in roots:
        if not root.exists():
            continue
        for path in root.glob("*.jsonl"):
            for row in _iter_jsonl(path, limit=20000):
                ticker = str(row.get("ticker") or row.get("symbol") or "").upper().strip()
                if not ticker:
                    continue
                index[ticker]["rows"] += 1
                index[ticker]["artifacts"].add(str(path.relative_to(REPO_ROOT)))
    return index


def probe_yahoo_chart(ticker: str, *, timeout: int) -> dict[str, Any]:
    try:
        response = requests.get(
            YAHOO_CHART_URL.format(ticker=ticker),
            params={"range": "6mo", "interval": "1d"},
            timeout=timeout,
            headers={"User-Agent": "Mozilla/5.0 FinSight-Agent availability probe"},
        )
        if response.status_code >= 400:
            return {"status": "error", "http_status": response.status_code}
        data = response.json()
        result = ((data.get("chart") or {}).get("result") or [None])[0] or {}
        timestamps = result.get("timestamp") or []
        return {
            "status": "available" if timestamps else "empty",
            "bar_count": len(timestamps),
            "currency": (result.get("meta") or {}).get("currency"),
            "exchange": (result.get("meta") or {}).get("exchangeName"),
        }
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error": str(exc)}


def probe_industry_sources(config: dict[str, Any], *, skip_live: bool, timeout: int) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    source_gaps: list[dict[str, Any]] = []
    for family in config.get("source_families", []) or []:
        source_family = str(family.get("source_family") or "")
        family_row = {
            "source_family": source_family,
            "providers": [],
            "status": "unknown",
        }
        provider_statuses: list[str] = []
        for provider in family.get("providers", []) or []:
            provider_row = probe_industry_provider(provider, skip_live=skip_live, timeout=timeout)
            family_row["providers"].append(provider_row)
            provider_statuses.append(str(provider_row.get("status")))
        if any(status == "available" for status in provider_statuses):
            family_row["status"] = "available"
        elif any(status in {"dataset_mapping_required", "api_key_or_dataset_mapping_required"} for status in provider_statuses):
            family_row["status"] = "needs_mapping"
            source_gaps.append(_gap(source_family, "industry_data", "industry_dataset_mapping_required", family_row))
        elif skip_live:
            family_row["status"] = "not_checked_live"
        else:
            family_row["status"] = "missing_or_error"
            source_gaps.append(_gap(source_family, "industry_data", "industry_source_not_available", family_row))
        rows.append(family_row)
    return {
        "status": "completed",
        "source_family_count": len(rows),
        "available_count": sum(1 for row in rows if row.get("status") == "available"),
        "needs_mapping_count": sum(1 for row in rows if row.get("status") == "needs_mapping"),
        "provider_mapping_required_count": sum(
            1
            for family in rows
            for provider in family.get("providers", [])
            if provider.get("status") in {"dataset_mapping_required", "api_key_or_dataset_mapping_required"}
        ),
        "results": rows,
        "source_gaps": source_gaps,
    }


def probe_industry_provider(provider: dict[str, Any], *, skip_live: bool, timeout: int) -> dict[str, Any]:
    provider_name = str(provider.get("provider") or "")
    row: dict[str, Any] = {
        "provider": provider_name,
        "access_mode": provider.get("access_mode"),
        "candidate_series": provider.get("candidate_series", []),
        "candidate_datasets": provider.get("candidate_datasets", []),
        "series_results": [],
        "dataset_results": [],
    }
    if skip_live:
        row["status"] = "not_checked_live"
        return row
    if provider_name.upper() == "FRED":
        for series_id in provider.get("candidate_series", []) or []:
            row["series_results"].append(probe_fred_series(str(series_id), timeout=timeout))
        row["status"] = "available" if any(r.get("status") == "available" for r in row["series_results"]) else "missing_or_error"
        return row
    if provider_name.upper() == "FDA":
        row["dataset_results"].append(probe_simple_json_endpoint("drug_approvals", "https://api.fda.gov/drug/drugsfda.json?limit=1", timeout=timeout))
        row["status"] = "available" if any(r.get("status") == "available" for r in row["dataset_results"]) else "missing_or_error"
        return row
    if provider_name.upper() == "CMS":
        row["dataset_results"].append(probe_simple_json_endpoint("cms_data_catalog", "https://data.cms.gov/data.json", timeout=timeout))
        row["status"] = "available" if any(r.get("status") == "available" for r in row["dataset_results"]) else "missing_or_error"
        return row
    if provider_name.upper() == "EIA":
        row["status"] = "api_key_or_dataset_mapping_required"
        row["note"] = "Config lists semantic datasets but not concrete EIA route/frequency/facet series; map datasets before normalization."
        return row
    row["status"] = "dataset_mapping_required"
    return row


def probe_fred_series(series_id: str, *, timeout: int) -> dict[str, Any]:
    try:
        response = requests.get(FRED_CSV_URL.format(series_id=series_id), timeout=timeout)
        if response.status_code >= 400:
            return {"series_id": series_id, "status": "error", "http_status": response.status_code}
        text = response.text
        sample = list(csv.DictReader(text.splitlines()))
        values = [row for row in sample if row.get(series_id) not in {None, "", "."}]
        return {
            "series_id": series_id,
            "status": "available" if values else "empty",
            "row_count": len(sample),
            "latest_observation_date": sample[-1].get("observation_date") if sample else None,
        }
    except Exception as exc:  # noqa: BLE001
        return {"series_id": series_id, "status": "error", "error": str(exc)}


def probe_simple_json_endpoint(dataset_id: str, url: str, *, timeout: int) -> dict[str, Any]:
    try:
        response = requests.get(url, timeout=timeout)
        if response.status_code >= 400:
            return {"dataset_id": dataset_id, "status": "error", "http_status": response.status_code}
        data = response.json()
        return {"dataset_id": dataset_id, "status": "available", "top_level_type": type(data).__name__}
    except Exception as exc:  # noqa: BLE001
        return {"dataset_id": dataset_id, "status": "error", "error": str(exc)}


def build_sector_pack_availability(report: dict[str, Any]) -> list[dict[str, Any]]:
    sec_by_ticker = {
        row.get("ticker"): row
        for row in ((report.get("sec_probe") or {}).get("results") or [])
        if row.get("ticker")
    }
    market_by_ticker = {
        row.get("ticker"): row
        for row in ((report.get("market_probe") or {}).get("results") or [])
        if row.get("ticker")
    }
    rows = []
    for pack in report.get("sector_packs", []) or []:
        pack_id = pack.get("pack_id")
        pack_sec = [row for row in sec_by_ticker.values() if pack_id in (row.get("packs") or [])]
        pack_market = [row for row in market_by_ticker.values() if row.get("ticker") in {sec.get("ticker") for sec in pack_sec}]
        rows.append(
            {
                "pack_id": pack_id,
                "company_count": len(pack_sec),
                "sec_available": sum(1 for row in pack_sec if row.get("status") == "available"),
                "sec_partial": sum(1 for row in pack_sec if row.get("status") == "partial"),
                "market_available": sum(1 for row in pack_market if str(row.get("status")).startswith("available")),
                "required_industry_sources": [
                    source for source in pack.get("required_source_families", []) if str(source).startswith("industry_")
                ],
            }
        )
    return rows


def build_recommendations(report: dict[str, Any]) -> list[str]:
    recommendations: list[str] = []
    missing_industry = (report.get("source_family_contract") or {}).get("missing_industry_source_family_definitions") or []
    if missing_industry:
        recommendations.append(
            "Normalize sector pack source-family names before building industry-data snapshots: "
            + ", ".join(missing_industry)
        )
    sec_probe = report.get("sec_probe") or {}
    if sec_probe.get("partial_count"):
        recommendations.append("Review SEC source gaps before accepting any sector-depth pack into the main universe.")
    industry_probe = report.get("industry_probe") or {}
    if industry_probe.get("needs_mapping_count"):
        recommendations.append("Create concrete dataset/series mappings for industry source families marked needs_mapping.")
    if industry_probe.get("provider_mapping_required_count"):
        recommendations.append("Map EIA and other semantic provider datasets to concrete endpoint/frequency/facet contracts before normalization.")
    recommendations.append("Treat 20-F/6-K/40-F canary companies as parser validation only until source-family gates pass.")
    return recommendations


def render_markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# Sector Depth Source Availability v0.2",
        "",
        f"Generated at: `{report.get('generated_at')}`",
        "",
        "## Summary",
        "",
        f"- Company requirements: `{report.get('company_requirement_count')}`",
    ]
    sec = report.get("sec_probe") or {}
    if sec.get("status") == "completed":
        lines.extend(
            [
                f"- SEC metadata probe: `{sec.get('available_count')}` available, `{sec.get('partial_count')}` partial, `{sec.get('missing_or_error_count')}` missing/error.",
                f"- SEC note: {sec.get('note')}",
            ]
        )
    market = report.get("market_probe") or {}
    if market.get("status") == "completed":
        lines.append(
            f"- Market probe: `{market.get('available_count')}` available, `{market.get('missing_count')}` missing."
        )
    industry = report.get("industry_probe") or {}
    if industry.get("status") == "completed":
        lines.append(
            f"- Industry source families: `{industry.get('available_count')}` available, `{industry.get('needs_mapping_count')}` need source-family mapping, `{industry.get('provider_mapping_required_count')}` provider mappings still need concrete datasets or keys."
        )
    lines.extend(["", "## Sector Packs", ""])
    lines.append("| Pack | P0 | P1 | SEC available | SEC partial | Market available | Industry sources |")
    lines.append("| --- | --- | --- | ---: | ---: | ---: | --- |")
    for row in report.get("sector_pack_availability", []) or []:
        pack_req = next(
            (pack for pack in report.get("sector_packs", []) if pack.get("pack_id") == row.get("pack_id")),
            {},
        )
        lines.append(
            "| {pack_id} | {p0} | {p1} | {sec_available} | {sec_partial} | {market_available} | {sources} |".format(
                pack_id=row.get("pack_id"),
                p0=", ".join(pack_req.get("p0_tickers") or []),
                p1=", ".join(pack_req.get("p1_tickers") or []),
                sec_available=row.get("sec_available"),
                sec_partial=row.get("sec_partial"),
                market_available=row.get("market_available"),
                sources=", ".join(row.get("required_industry_sources") or []),
            )
        )
    lines.extend(["", "## Source-Family Contract Issues", ""])
    missing = (report.get("source_family_contract") or {}).get("missing_industry_source_family_definitions") or []
    if missing:
        lines.append("- Missing industry source-family definitions: `" + "`, `".join(missing) + "`")
    else:
        lines.append("- No missing industry source-family definitions detected.")
    lines.extend(["", "## Recommendations", ""])
    for item in report.get("recommendations", []) or []:
        lines.append(f"- {item}")
    lines.extend(["", "## Gap Count", ""])
    lines.append(f"- Total source gaps emitted: `{len(report.get('source_gaps') or [])}`")
    return "\n".join(lines) + "\n"


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _default_report_path(suffix: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d")
    return f"reports/quality/{stamp}_sector_depth_source_availability_v0_2.{suffix}"


def _parse_ticker_filter(raw: str | None) -> set[str] | None:
    if not raw:
        return None
    return {value.strip().upper() for value in raw.split(",") if value.strip()}


def _value_at(block: dict[str, Any], key: str, index: int) -> Any:
    values = block.get(key, []) or []
    if index >= len(values):
        return None
    return values[index]


def _date_year(value: Any) -> int | None:
    match = re.match(r"(\d{4})", str(value or ""))
    return int(match.group(1)) if match else None


def _gap(subject: str, source_family: str, reason: str, evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "subject": subject,
        "source_family": source_family,
        "reason": reason,
        "evidence": evidence,
    }


def _iter_jsonl(path: Path, *, limit: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for index, line in enumerate(handle):
                if index >= limit:
                    break
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    rows.append(json.loads(stripped))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return rows


if __name__ == "__main__":
    main()
