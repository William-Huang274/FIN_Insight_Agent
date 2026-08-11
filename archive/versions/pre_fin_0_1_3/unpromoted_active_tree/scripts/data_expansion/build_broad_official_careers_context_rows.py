from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


SCHEMA_VERSION = "finsight_broad_official_careers_context_row_v0_1"
ATTEMPT_SCHEMA_VERSION = "finsight_broad_official_careers_attempt_v0_1"
SUMMARY_SCHEMA_VERSION = "finsight_broad_official_careers_context_summary_v0_1"

DEFAULT_COMPANY_SOURCE_MATRIX = REPO_ROOT / "data" / "manifests" / "company_public_source_coverage_matrix_v0_1.jsonl"
DEFAULT_LOW_COVERAGE = REPO_ROOT / "data" / "manifests" / "l3_minimum_coverage_low_companies_v0_1.jsonl"
DEFAULT_DOMAIN_CACHE = REPO_ROOT / "data" / "manifests" / "company_domain_locator_cache_v0_1.json"
DEFAULT_OUTPUT_ROWS = REPO_ROOT / "data" / "manifests" / "broad_official_careers_context_rows_v0_1.jsonl"
DEFAULT_OUTPUT_ATTEMPTS = REPO_ROOT / "data" / "manifests" / "broad_official_careers_attempts_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY = REPO_ROOT / "data" / "manifests" / "broad_official_careers_context_summary_v0_1.json"
DEFAULT_RAW_DIR = Path("Z:/FIN_Insight_Agent_data/raw_private/public_source_extended_materialization/broad_official_careers")

USER_AGENT = "Mozilla/5.0 FIN-Insight-Agent official public careers parser"
LOCALE_SEGMENTS = {"en", "en-us", "en_us", "en-gb", "en_gb", "zh", "ja", "ko"}
DOMAIN_OVERRIDES = {
    "AMZN": ("amazon.jobs",),
    "CRM": ("salesforce.com",),
    "EME": ("emcorgroup.com",),
    "FFIV": ("f5.com",),
    "GOOGL": ("google.com", "abc.xyz"),
    "SBUX": ("starbucks.com",),
    "SHOP": ("shopify.com",),
}

DIRECT_CAREER_URLS = {
    "AMZN": (
        "https://www.amazon.jobs/en/search.json?offset=0&result_limit=10&sort=relevant",
    ),
    "CSCO": (
        "https://careers.cisco.com/global/en/search-results?from=0&s=1",
    ),
    "CMG": (
        "https://jobs.chipotle.com/search-jobs",
    ),
    "CHTR": (
        "https://jobs.spectrum.com/search-jobs",
    ),
    "EBAY": (
        "https://jobs.ebayinc.com/us/en/search-results?from=0&s=1",
    ),
    "GOOGL": (
        "https://www.google.com/about/careers/applications/jobs/results/?q=&page=1",
    ),
    "INTU": (
        "https://jobs.intuit.com/search-jobs?from=0&s=1",
    ),
    "IBM": (
        "https://www.ibm.com/careers/search",
    ),
    "ADP": (
        "https://jobs.adp.com/en/jobs/",
    ),
    "CTSH": (
        "https://careers.cognizant.com/global-en/jobs/?from=0&s=1",
    ),
    "DRI": (
        "https://dardenrscjobs.recruiting.com/",
    ),
    "EME": (
        "https://careers-emcorgroup.icims.com/jobs/search?ss=1&searchKeyword=%23efs&in_iframe=1",
    ),
    "LII": (
        "https://ushourly-lennox.icims.com/jobs/search?ss=1&in_iframe=1",
    ),
    "MSFT": (
        "https://apply.careers.microsoft.com/api/pcsx/search?domain=microsoft.com&query=&location=&start=0",
    ),
    "PCOR": (
        "https://careers.procore.com/jobs/search",
    ),
    "PWR": (
        "https://careers-quanta.icims.com/jobs/search?ss=1&in_iframe=1",
    ),
    "SHOP": (
        "https://www.shopify.com/careers",
    ),
    "SBUX": (
        "https://apply.starbucks.com/api/pcsx/search?domain=starbucks.com&query=&location=&start=0",
    ),
    "SE": (
        "https://career.sea.com/jobs",
    ),
    "T": (
        "https://www.att.jobs/search-jobs?from=0&s=1",
    ),
    "TEAM": (
        "https://www.atlassian.com/endpoint/careers/listings",
    ),
    "ETN": (
        "https://eaton.eightfold.ai/api/pcsx/search?domain=eaton.com&query=&location=&start=0&filter_include_remote=1",
    ),
    "MELI": (
        "https://mercadolibre.eightfold.ai/api/pcsx/search?domain=mercadolibre.com&query=&location=&start=0&",
    ),
    "ROP": (
        "https://careers.deltek.com/",
    ),
    "TT": (
        "https://careers.tranetechnologies.com/global/en/search-results?from=0&s=1",
    ),
    "VZ": (
        "https://mycareer.verizon.com/jobs/",
    ),
}

DIRECT_ATS_URLS = {
    "ADSK": ("https://autodesk.wd1.myworkdayjobs.com/Ext",),
    "AKAM": ("https://fa-extu-saasfaprod1.fa.ocs.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1/jobs",),
    "CRWD": ("https://crowdstrike.wd5.myworkdayjobs.com/crowdstrikecareers",),
    "CRM": ("https://salesforce.wd12.myworkdayjobs.com/External_Career_Site",),
    "FFIV": ("https://ffive.wd5.myworkdayjobs.com/f5jobs",),
    "FTNT": ("https://edel.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_2001/jobs",),
    "FIX": ("https://comfortsystemsusa.wd1.myworkdayjobs.com/Corpcareers",),
    "HON": ("https://ibqbjb.fa.ocs.oraclecloud.com/hcmUI/CandidateExperience/en/sites/Honeywell/jobs",),
    "MSI": ("https://motorolasolutions.wd5.myworkdayjobs.com/Careers",),
    "ORCL": ("https://eeho.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1/jobs",),
    "OTIS": ("https://otis.wd5.myworkdayjobs.com/REC_Ext_Gateway",),
    "TMUS": ("https://tmobile.wd1.myworkdayjobs.com/External",),
    "VRT": ("https://egup.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX/jobs",),
    "YUM": ("https://eczd.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1/jobs",),
}

ATS_TOKEN_OVERRIDES = {
    "BILL": ("billcom",),
    "ESTC": ("elastic",),
    "S": ("sentinellabs",),
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build official careers/ATS hiring rows for low-L3 companies.")
    parser.add_argument("--company-source-matrix", type=Path, default=DEFAULT_COMPANY_SOURCE_MATRIX)
    parser.add_argument("--low-coverage", type=Path, default=DEFAULT_LOW_COVERAGE)
    parser.add_argument("--domain-cache", type=Path, default=DEFAULT_DOMAIN_CACHE)
    parser.add_argument("--output-rows", type=Path, default=DEFAULT_OUTPUT_ROWS)
    parser.add_argument("--output-attempts", type=Path, default=DEFAULT_OUTPUT_ATTEMPTS)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--tickers", nargs="*", default=[])
    parser.add_argument("--only-low-coverage", action="store_true")
    parser.add_argument("--timeout-s", type=float, default=8.0)
    parser.add_argument("--workers", type=int, default=24)
    parser.add_argument("--max-jobs-per-company", type=int, default=2)
    parser.add_argument("--max-career-pages", type=int, default=12)
    parser.add_argument("--replace-output", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at = _utc_now()
    matrix_rows = _load_jsonl(args.company_source_matrix)
    low_tickers = _low_coverage_tickers(args.low_coverage) if args.only_low_coverage else set()
    result = build_broad_official_careers_context_rows(
        matrix_rows=matrix_rows,
        domain_cache=_load_domain_cache(args.domain_cache),
        low_coverage_tickers=low_tickers,
        generated_at=generated_at,
        tickers=args.tickers,
        raw_dir=args.raw_dir,
        timeout_s=args.timeout_s,
        workers=args.workers,
        max_jobs_per_company=args.max_jobs_per_company,
        max_career_pages=args.max_career_pages,
    )
    output_rows = result["rows"] if args.replace_output else _dedupe_rows(_load_jsonl(args.output_rows) + result["rows"])
    output_attempts = result["attempts"] if args.replace_output else _dedupe_attempts(_load_jsonl(args.output_attempts) + result["attempts"])
    summary = build_summary(
        rows=output_rows,
        attempts=output_attempts,
        matrix_rows=matrix_rows,
        low_coverage_tickers=low_tickers,
        generated_at=generated_at,
        output_rows=args.output_rows,
        output_attempts=args.output_attempts,
    )
    _write_jsonl(args.output_rows, output_rows)
    _write_jsonl(args.output_attempts, output_attempts)
    _write_json(args.output_summary, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if args.strict and not result["rows"]:
        return 1
    return 0


def build_broad_official_careers_context_rows(
    *,
    matrix_rows: Iterable[Mapping[str, Any]],
    domain_cache: Mapping[str, Any],
    low_coverage_tickers: set[str],
    generated_at: str,
    raw_dir: Path,
    tickers: Iterable[str] = (),
    timeout_s: float = 8.0,
    workers: int = 24,
    max_jobs_per_company: int = 2,
    max_career_pages: int = 12,
) -> dict[str, list[dict[str, Any]]]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    ticker_filter = {str(ticker).strip().upper() for ticker in tickers if str(ticker).strip()}
    companies: list[dict[str, Any]] = []
    for company in matrix_rows:
        ticker = str(company.get("ticker") or "").strip().upper()
        if not ticker or (ticker_filter and ticker not in ticker_filter) or (low_coverage_tickers and ticker not in low_coverage_tickers):
            continue
        requirements = {str(req.get("requirement_id") or "") for req in company.get("source_role_matrix") or [] if isinstance(req, Mapping)}
        if "hiring_capacity_proxy" in requirements:
            companies.append(dict(company))
    rows: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, int(workers or 1))) as executor:
        futures = {
            executor.submit(
                _process_company,
                company,
                domain_cache=domain_cache,
                generated_at=generated_at,
                raw_dir=raw_dir,
                timeout_s=timeout_s,
                max_jobs=max_jobs_per_company,
                max_career_pages=max_career_pages,
            ): str(company.get("ticker") or "").strip().upper()
            for company in companies
        }
        for future in as_completed(futures):
            try:
                result = future.result()
            except Exception as exc:  # noqa: BLE001
                ticker = futures[future]
                attempts.append(_attempt(ticker, "worker", "", "worker_failed", reason=f"{type(exc).__name__}:{str(exc)[:200]}", raw_path=""))
                continue
            rows.extend(result["rows"])
            attempts.extend(result["attempts"])
    return {"rows": _dedupe_rows(rows), "attempts": attempts}


def _process_company(
    company: Mapping[str, Any],
    *,
    domain_cache: Mapping[str, Any],
    generated_at: str,
    raw_dir: Path,
    timeout_s: float,
    max_jobs: int,
    max_career_pages: int,
) -> dict[str, list[dict[str, Any]]]:
    ticker = str(company.get("ticker") or "").strip().upper()
    domains = _domains_for_company(ticker, company, domain_cache)
    rows: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []
    if not domains:
        return {"rows": rows, "attempts": [_attempt(ticker, "domain_cache", "", "no_domain_candidates", reason="", raw_path="")]}
    candidate_urls = _unique([*DIRECT_CAREER_URLS.get(ticker, ()), *_career_candidate_urls(domains)])
    discovered_ats: list[str] = []
    for url in candidate_urls[: max(1, int(max_career_pages or 1))]:
        status, body, reason = _fetch_text(url, timeout_s=timeout_s)
        raw_path = raw_dir / _slug(ticker) / f"{_stable_digest(url)}.html"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(body or "", encoding="utf-8")
        if status != "ok":
            attempts.append(_attempt(ticker, "official_career_page", url, status, reason=reason, raw_path=str(raw_path)))
            if ticker == "VZ" and "mycareer.verizon.com" in urlparse(url).netloc.lower():
                browser_result = _fetch_verizon_browser_jobs(
                    company,
                    url,
                    generated_at=generated_at,
                    raw_dir=raw_dir,
                    timeout_s=timeout_s,
                    max_jobs=max_jobs - len(rows),
                )
                rows.extend(browser_result["rows"])
                attempts.extend(browser_result["attempts"])
                if len(rows) >= max_jobs:
                    return {"rows": rows[:max_jobs], "attempts": attempts}
            continue
        platform_result = _parse_platform_jobs(company, url, body, generated_at=generated_at, raw_dir=raw_dir, timeout_s=timeout_s, max_jobs=max_jobs - len(rows))
        rows.extend(platform_result["rows"])
        attempts.extend(platform_result["attempts"])
        if len(rows) >= max_jobs:
            return {"rows": rows[:max_jobs], "attempts": attempts}
        links = _extract_links(body, base_url=url)
        discovered_ats.extend([href for href in links if _is_supported_ats_url(href)])
        jsonld_rows = _parse_jsonld_jobs(company, body, source_url=url, generated_at=generated_at, max_jobs=max_jobs - len(rows))
        rows.extend(jsonld_rows)
        page_rows = platform_result["rows"] + jsonld_rows
        if not page_rows and ticker == "VZ" and "mycareer.verizon.com" in urlparse(url).netloc.lower():
            browser_result = _fetch_verizon_browser_jobs(
                company,
                url,
                generated_at=generated_at,
                raw_dir=raw_dir,
                timeout_s=timeout_s,
                max_jobs=max_jobs - len(rows),
            )
            rows.extend(browser_result["rows"])
            attempts.extend(browser_result["attempts"])
            page_rows = browser_result["rows"]
        attempts.append(_attempt(ticker, "official_career_page", url, "materialized" if page_rows else "careers_page_no_jobposting_rows", reason="" if page_rows else "No parser-backed job rows on official careers page", raw_path=str(raw_path)))
        if len(rows) >= max_jobs:
            return {"rows": rows[:max_jobs], "attempts": attempts}
        if discovered_ats:
            break

    for ats_url in _unique(discovered_ats + _direct_ats_candidates(ticker, company)):
        ats_result = _fetch_supported_ats_jobs(company, ats_url, generated_at=generated_at, raw_dir=raw_dir, timeout_s=timeout_s, max_jobs=max_jobs - len(rows))
        rows.extend(ats_result["rows"])
        attempts.extend(ats_result["attempts"])
        if len(rows) >= max_jobs:
            break
    return {"rows": rows[:max_jobs], "attempts": attempts}


def _fetch_supported_ats_jobs(
    company: Mapping[str, Any],
    ats_url: str,
    *,
    generated_at: str,
    raw_dir: Path,
    timeout_s: float,
    max_jobs: int,
) -> dict[str, list[dict[str, Any]]]:
    ticker = str(company.get("ticker") or "").strip().upper()
    if max_jobs <= 0:
        return {"rows": [], "attempts": []}
    parsed = urlparse(ats_url)
    host = parsed.netloc.lower()
    if "myworkdayjobs.com" in host:
        return _fetch_workday_jobs(company, ats_url, generated_at=generated_at, raw_dir=raw_dir, timeout_s=timeout_s, max_jobs=max_jobs)
    if "greenhouse.io" in host:
        token = _greenhouse_token(ats_url)
        if token:
            url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"
            return _fetch_greenhouse_jobs(company, url, token=token, generated_at=generated_at, raw_dir=raw_dir, timeout_s=timeout_s, max_jobs=max_jobs)
    if "lever.co" in host:
        token = _lever_token(ats_url)
        if token:
            url = f"https://api.lever.co/v0/postings/{token}?mode=json"
            return _fetch_lever_jobs(company, url, token=token, generated_at=generated_at, raw_dir=raw_dir, timeout_s=timeout_s, max_jobs=max_jobs)
    if "ashbyhq.com" in host:
        token = _ashby_token(ats_url)
        if token:
            url = f"https://api.ashbyhq.com/posting-api/job-board/{token}"
            return _fetch_ashby_jobs(company, url, token=token, generated_at=generated_at, raw_dir=raw_dir, timeout_s=timeout_s, max_jobs=max_jobs)
    if "oraclecloud.com" in host and "/candidateexperience/" in parsed.path.lower():
        site_number = _oracle_hcm_site_number(ats_url)
        if site_number:
            return _fetch_oracle_hcm_jobs(company, ats_url, site_number=site_number, generated_at=generated_at, raw_dir=raw_dir, timeout_s=timeout_s, max_jobs=max_jobs)
    return {"rows": [], "attempts": [_attempt(ticker, "ats", ats_url, "unsupported_ats_url", reason="", raw_path="")]}


def _parse_platform_jobs(
    company: Mapping[str, Any],
    page_url: str,
    body: str,
    *,
    generated_at: str,
    raw_dir: Path,
    timeout_s: float,
    max_jobs: int,
) -> dict[str, list[dict[str, Any]]]:
    if max_jobs <= 0:
        return {"rows": [], "attempts": []}
    parsed = urlparse(page_url)
    host = parsed.netloc.lower()
    lowered = body.lower()
    if host.endswith("amazon.jobs") and parsed.path.endswith("/search.json"):
        rows = _parse_amazon_jobs_payload(company, body, source_url=page_url, generated_at=generated_at, max_jobs=max_jobs)
        return {
            "rows": rows,
            "attempts": [
                _attempt(
                    str(company.get("ticker") or "").upper(),
                    "amazon_jobs_api",
                    page_url,
                    "materialized" if rows else "no_job_rows",
                    reason="" if rows else "Amazon Jobs API returned no parseable title/location rows",
                    raw_path="",
                )
            ],
        }
    if host.endswith("atlassian.com") and parsed.path.endswith("/endpoint/careers/listings"):
        rows = _parse_atlassian_careers_payload(company, body, source_url=page_url, generated_at=generated_at, max_jobs=max_jobs)
        return {
            "rows": rows,
            "attempts": [
                _attempt(
                    str(company.get("ticker") or "").upper(),
                    "atlassian_careers_api",
                    page_url,
                    "materialized" if rows else "no_job_rows",
                    reason="" if rows else "Atlassian careers API returned no parseable title/location rows",
                    raw_path="",
                )
            ],
        }
    if parsed.path.endswith("/api/pcsx/search"):
        rows = _parse_pcsx_search_payload(company, body, source_url=page_url, generated_at=generated_at, max_jobs=max_jobs)
        return {
            "rows": rows,
            "attempts": [
                _attempt(
                    str(company.get("ticker") or "").upper(),
                    "pcsx_careers_api",
                    page_url,
                    "materialized" if rows else "no_job_rows",
                    reason="" if rows else "PCSX careers API returned no parseable name/location rows",
                    raw_path="",
                )
            ],
        }
    if host.endswith("shopify.com") and parsed.path.rstrip("/") == "/careers" and "jobPostingsWithJobs" in body:
        rows = _parse_shopify_singlefetch_jobs(company, body, source_url=page_url, generated_at=generated_at, max_jobs=max_jobs)
        return {
            "rows": rows,
            "attempts": [
                _attempt(
                    str(company.get("ticker") or "").upper(),
                    "shopify_singlefetch_ashby_jobs",
                    page_url,
                    "materialized" if rows else "no_job_rows",
                    reason="" if rows else "Shopify careers SingleFetch payload returned no parseable listed title/location rows",
                    raw_path="",
                )
            ],
        }
    if host == "career.sea.com" and parsed.path.rstrip("/") == "/jobs":
        return _fetch_sea_careers_jobs(company, body, source_url=page_url, generated_at=generated_at, timeout_s=timeout_s, max_jobs=max_jobs)
    if host.endswith("careers.deltek.com") and "widget_joblist_row" in lowered:
        rows = _parse_deltek_findly_widget_jobs(company, body, source_url=page_url, generated_at=generated_at, max_jobs=max_jobs)
        return {"rows": rows, "attempts": [_attempt(str(company.get("ticker") or "").upper(), "deltek_findly_widget_jobs", page_url, "materialized" if rows else "no_job_rows", reason="" if rows else "No Deltek Findly widget job title/location rows", raw_path="")]}
    if host.endswith("ibm.com") and parsed.path.rstrip("/") == "/careers/search":
        return _fetch_ibm_careers_search_jobs(company, page_url, generated_at=generated_at, raw_dir=raw_dir, timeout_s=timeout_s, max_jobs=max_jobs)
    if "window.__preload_state__" in lowered and '"jobsearch"' in lowered:
        rows = _parse_paradox_preload_jobs(company, body, source_url=page_url, generated_at=generated_at, max_jobs=max_jobs)
        return {"rows": rows, "attempts": [_attempt(str(company.get("ticker") or "").upper(), "paradox_preload_jobs", page_url, "materialized" if rows else "no_job_rows", reason="" if rows else "No Paradox preload job title/location rows", raw_path="")]}
    if "icims_jobcarditem" in lowered and "icims_anchor" in lowered:
        rows = _parse_icims_iframe_job_cards(company, body, source_url=page_url, generated_at=generated_at, max_jobs=max_jobs)
        return {"rows": rows, "attempts": [_attempt(str(company.get("ticker") or "").upper(), "icims_iframe_job_cards", page_url, "materialized" if rows else "no_job_rows", reason="" if rows else "No iCIMS iframe job title/location rows", raw_path="")]}
    if "window._jibe" in body or "app.jibecdn.com" in lowered:
        return _fetch_jibe_jobs(company, page_url, generated_at=generated_at, raw_dir=raw_dir, timeout_s=timeout_s, max_jobs=max_jobs)
    if "phenompeople.com" in lowered or "var phapp" in lowered:
        rows = _parse_phenom_embedded_jobs(company, body, source_url=page_url, generated_at=generated_at, max_jobs=max_jobs)
        return {"rows": rows, "attempts": [_attempt(str(company.get("ticker") or "").upper(), "phenom_embedded", page_url, "materialized" if rows else "no_job_rows", reason="" if rows else "No embedded Phenom job title/location rows", raw_path="")]}
    if "search-results-list" in lowered and "/job/" in lowered:
        rows = _parse_talentbrew_search_jobs(company, body, source_url=page_url, generated_at=generated_at, max_jobs=max_jobs)
        return {"rows": rows, "attempts": [_attempt(str(company.get("ticker") or "").upper(), "talentbrew_html", page_url, "materialized" if rows else "no_job_rows", reason="" if rows else "No TalentBrew search list title/location rows", raw_path="")]}
    if "google.com/about/careers" in page_url and "qjpwve" in lowered:
        rows = _parse_google_careers_html_jobs(company, body, source_url=page_url, generated_at=generated_at, max_jobs=max_jobs)
        return {"rows": rows, "attempts": [_attempt(str(company.get("ticker") or "").upper(), "google_careers_html", page_url, "materialized" if rows else "no_job_rows", reason="" if rows else "No Google careers title/location rows", raw_path="")]}
    if "successfactors.com" in lowered or "searchresults" in lowered and "/job/" in lowered and "jobtitle" in lowered:
        rows = _parse_successfactors_search_jobs(company, body, source_url=page_url, generated_at=generated_at, max_jobs=max_jobs)
        return {"rows": rows, "attempts": [_attempt(str(company.get("ticker") or "").upper(), "successfactors_html", page_url, "materialized" if rows else "no_job_rows", reason="" if rows else "No SuccessFactors search table job rows", raw_path="")]}
    if "job-search-results-title" in lowered and "job-search-results-location" in lowered:
        rows = _parse_generic_job_search_table_jobs(company, body, source_url=page_url, generated_at=generated_at, max_jobs=max_jobs)
        return {"rows": rows, "attempts": [_attempt(str(company.get("ticker") or "").upper(), "generic_job_search_table_html", page_url, "materialized" if rows else "no_job_rows", reason="" if rows else "No generic careers search table title/location rows", raw_path="")]}
    if "card card-job" in lowered and "job-meta" in lowered:
        rows = _parse_card_job_html_jobs(company, body, source_url=page_url, generated_at=generated_at, max_jobs=max_jobs, provider="adp_card_job_html" if host.endswith("adp.com") else "cognizant_card_job_html", token=host)
        return {"rows": rows, "attempts": [_attempt(str(company.get("ticker") or "").upper(), "card_job_html", page_url, "materialized" if rows else "no_job_rows", reason="" if rows else "No card job title/location rows", raw_path="")]}
    if host.startswith("jobs.") and "/search" in parsed.path:
        rows = _parse_successfactors_search_jobs(company, body, source_url=page_url, generated_at=generated_at, max_jobs=max_jobs)
        if rows:
            return {"rows": rows, "attempts": [_attempt(str(company.get("ticker") or "").upper(), "successfactors_html", page_url, "materialized", reason="", raw_path="")]}
    return {"rows": [], "attempts": []}


def _fetch_jibe_jobs(
    company: Mapping[str, Any],
    page_url: str,
    *,
    generated_at: str,
    raw_dir: Path,
    timeout_s: float,
    max_jobs: int,
) -> dict[str, list[dict[str, Any]]]:
    ticker = str(company.get("ticker") or "").strip().upper()
    parsed = urlparse(page_url)
    api_url = f"{parsed.scheme}://{parsed.netloc}/api/jobs?limit={max(1, max_jobs)}"
    status, body, reason = _fetch_text(api_url, timeout_s=timeout_s, accept="application/json,*/*")
    raw_path = raw_dir / _slug(ticker) / f"jibe_{_stable_digest(api_url)}.json"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(body or "", encoding="utf-8")
    if status != "ok":
        return {"rows": [], "attempts": [_attempt(ticker, "jibe_api", api_url, status, reason=reason, raw_path=str(raw_path))]}
    data = _parse_json(body)
    rows: list[dict[str, Any]] = []
    for job in data.get("jobs", []) if isinstance(data, Mapping) else []:
        payload = job.get("data") if isinstance(job, Mapping) and isinstance(job.get("data"), Mapping) else job
        if not isinstance(payload, Mapping):
            continue
        title = str(payload.get("title") or "").strip()
        location = _jibe_location(payload)
        posted_at = str(payload.get("posted_date") or payload.get("create_date") or payload.get("update_date") or "").strip()
        department = _first_named(payload.get("categories") or payload.get("category"))
        source_url = str(payload.get("apply_url") or "")
        if not source_url:
            slug = str(payload.get("slug") or "").strip()
            source_url = urljoin(f"{parsed.scheme}://{parsed.netloc}", f"/jobs/{slug}") if slug else api_url
        if title and location:
            rows.append(_job_row(company, source_url=source_url, title=title, location=location, department=department, posted_at=posted_at, provider="jibe_api", token=parsed.netloc, generated_at=generated_at))
        if len(rows) >= max_jobs:
            break
    return {"rows": rows, "attempts": [_attempt(ticker, "jibe_api", api_url, "materialized" if rows else "no_job_rows", reason="" if rows else "Jibe API returned no parseable title/location rows", raw_path=str(raw_path))]}


def _fetch_ibm_careers_search_jobs(
    company: Mapping[str, Any],
    page_url: str,
    *,
    generated_at: str,
    raw_dir: Path,
    timeout_s: float,
    max_jobs: int,
) -> dict[str, list[dict[str, Any]]]:
    ticker = str(company.get("ticker") or "").strip().upper()
    api_url = "https://www-api.ibm.com/search/api/v2"
    payload = json.dumps(
        {
            "appId": "careers",
            "scopes": ["careers2"],
            "query": {"bool": {"must": []}},
            "sort": [{"_score": "desc"}, {"pageviews": "desc"}],
            "size": max(1, int(max_jobs or 1)),
            "lang": "en",
            "cc": "us",
            "from": 0,
            "localeSelector": {},
            "p": 1,
            "_source": ["title", "url", "field_keyword_18", "field_keyword_19", "field_keyword_03", "field_keyword_08"],
        },
        separators=(",", ":"),
    ).encode("utf-8")
    status, body, reason = _post_json(api_url, payload, timeout_s=timeout_s, referer=page_url)
    raw_path = raw_dir / _slug(ticker) / f"ibm_search_{_stable_digest(api_url)}.json"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(body or "", encoding="utf-8")
    if status != "ok":
        return {"rows": [], "attempts": [_attempt(ticker, "ibm_search_api", api_url, status, reason=reason, raw_path=str(raw_path))]}
    rows = _parse_ibm_careers_search_payload(company, body, source_url=api_url, generated_at=generated_at, max_jobs=max_jobs)
    return {
        "rows": rows,
        "attempts": [
            _attempt(
                ticker,
                "ibm_search_api",
                api_url,
                "materialized" if rows else "no_job_rows",
                reason="" if rows else "IBM careers search API returned no parseable title/location rows",
                raw_path=str(raw_path),
            )
        ],
    }


def _parse_ibm_careers_search_payload(
    company: Mapping[str, Any],
    body: str,
    *,
    source_url: str,
    generated_at: str,
    max_jobs: int,
) -> list[dict[str, Any]]:
    data = _parse_json(body)
    hits = ((data.get("hits") or {}).get("hits") or []) if isinstance(data, Mapping) else []
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for hit in hits if isinstance(hits, list) else []:
        if not isinstance(hit, Mapping):
            continue
        payload = hit.get("_source") if isinstance(hit.get("_source"), Mapping) else hit
        if not isinstance(payload, Mapping):
            continue
        title = str(payload.get("title") or "").strip()
        location = str(payload.get("field_keyword_19") or payload.get("field_keyword_05") or "").strip()
        department = str(payload.get("field_keyword_08") or payload.get("field_keyword_03") or "").strip()
        source = str(payload.get("url") or source_url).strip()
        key = (title, location)
        if not title or not location or key in seen:
            continue
        seen.add(key)
        rows.append(
            _job_row(
                company,
                source_url=source,
                title=title,
                location=location,
                department=department,
                posted_at=generated_at[:10],
                provider="ibm_search_api",
                token="careers2",
                generated_at=generated_at,
            )
        )
        if len(rows) >= max_jobs:
            break
    return rows


def _fetch_workday_jobs(
    company: Mapping[str, Any],
    page_url: str,
    *,
    generated_at: str,
    raw_dir: Path,
    timeout_s: float,
    max_jobs: int,
) -> dict[str, list[dict[str, Any]]]:
    ticker = str(company.get("ticker") or "").strip().upper()
    parsed = urlparse(page_url)
    tenant = parsed.netloc.split(".", 1)[0]
    parts = [part for part in parsed.path.split("/") if part and part.lower() not in LOCALE_SEGMENTS]
    site = parts[0] if parts else "External"
    api_url = f"{parsed.scheme}://{parsed.netloc}/wday/cxs/{tenant}/{site}/jobs"
    payload = json.dumps({"appliedFacets": {}, "limit": max(1, max_jobs), "offset": 0, "searchText": ""}).encode("utf-8")
    status, body, reason = _post_json(api_url, payload, timeout_s=timeout_s)
    raw_path = raw_dir / _slug(ticker) / f"workday_{_stable_digest(api_url)}.json"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(body or "", encoding="utf-8")
    if status != "ok":
        return {"rows": [], "attempts": [_attempt(ticker, "workday", api_url, status, reason=reason, raw_path=str(raw_path))]}
    data = _parse_json(body)
    jobs = data.get("jobPostings") if isinstance(data, Mapping) else []
    rows = []
    for job in jobs if isinstance(jobs, list) else []:
        if not isinstance(job, Mapping):
            continue
        title = str(job.get("title") or "").strip()
        location = str(job.get("locationsText") or job.get("location") or "").strip()
        external_path = str(job.get("externalPath") or "").strip()
        posted_at = str(job.get("postedOn") or "").strip()
        if title and location:
            job_url = urljoin(f"{parsed.scheme}://{parsed.netloc}", external_path) if external_path else page_url
            rows.append(_job_row(company, source_url=job_url, title=title, location=location, department="", posted_at=posted_at, provider="workday", token=site, generated_at=generated_at))
        if len(rows) >= max_jobs:
            break
    return {"rows": rows, "attempts": [_attempt(ticker, "workday", api_url, "materialized" if rows else "no_job_rows", reason="" if rows else "Workday API returned no parseable title/location rows", raw_path=str(raw_path))]}


def _fetch_oracle_hcm_jobs(
    company: Mapping[str, Any],
    page_url: str,
    *,
    site_number: str,
    generated_at: str,
    raw_dir: Path,
    timeout_s: float,
    max_jobs: int,
) -> dict[str, list[dict[str, Any]]]:
    ticker = str(company.get("ticker") or "").strip().upper()
    parsed = urlparse(page_url)
    api_url = (
        f"{parsed.scheme}://{parsed.netloc}/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
        f"?finder=findReqs;siteNumber={site_number},limit={max(1, max_jobs)}&onlyData=true&expand=requisitionList"
    )
    status, body, reason = _fetch_text(api_url, timeout_s=timeout_s, accept="application/json,*/*")
    raw_path = raw_dir / _slug(ticker) / f"oracle_hcm_{_stable_digest(api_url)}.json"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(body or "", encoding="utf-8")
    if status != "ok":
        return {"rows": [], "attempts": [_attempt(ticker, "oracle_hcm_ce", api_url, status, reason=reason, raw_path=str(raw_path))]}
    data = _parse_json(body)
    search_items = data.get("items") if isinstance(data, Mapping) else []
    requisitions: list[Mapping[str, Any]] = []
    for item in search_items if isinstance(search_items, list) else []:
        if not isinstance(item, Mapping):
            continue
        values = item.get("requisitionList")
        if isinstance(values, list):
            requisitions.extend(job for job in values if isinstance(job, Mapping))
    rows: list[dict[str, Any]] = []
    base_site = page_url.split("/jobs", 1)[0].split("/requisitions", 1)[0].rstrip("/")
    for job in requisitions[: max(1, max_jobs * 3)]:
        title = str(job.get("Title") or "").strip()
        location = str(job.get("PrimaryLocation") or job.get("PrimaryLocationCountry") or "").strip()
        posted_at = str(job.get("PostedDate") or "").strip()
        department = str(job.get("JobFamily") or job.get("JobFunction") or job.get("Organization") or "").strip()
        job_id = str(job.get("Id") or "").strip()
        source_url = f"{base_site}/job/{job_id}" if job_id else api_url
        if title and location:
            rows.append(
                _job_row(
                    company,
                    source_url=source_url,
                    title=title,
                    location=location,
                    department=department,
                    posted_at=posted_at,
                    provider="oracle_hcm_ce",
                    token=site_number,
                    generated_at=generated_at,
                )
            )
        if len(rows) >= max_jobs:
            break
    return {"rows": rows, "attempts": [_attempt(ticker, "oracle_hcm_ce", api_url, "materialized" if rows else "no_job_rows", reason="" if rows else "Oracle HCM CE endpoint returned no parseable title/location rows", raw_path=str(raw_path))]}


def _fetch_greenhouse_jobs(
    company: Mapping[str, Any],
    url: str,
    *,
    token: str,
    generated_at: str,
    raw_dir: Path,
    timeout_s: float,
    max_jobs: int,
) -> dict[str, list[dict[str, Any]]]:
    ticker = str(company.get("ticker") or "").strip().upper()
    status, body, reason = _fetch_text(url, timeout_s=timeout_s, accept="application/json")
    raw_path = raw_dir / _slug(ticker) / f"greenhouse_{_stable_digest(url)}.json"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(body or "", encoding="utf-8")
    if status != "ok":
        return {"rows": [], "attempts": [_attempt(ticker, "greenhouse", url, status, reason=reason, raw_path=str(raw_path))]}
    data = _parse_json(body)
    rows = []
    for job in data.get("jobs", []) if isinstance(data, Mapping) else []:
        if not isinstance(job, Mapping):
            continue
        title = str(job.get("title") or "").strip()
        location = str((job.get("location") or {}).get("name") if isinstance(job.get("location"), Mapping) else "").strip()
        if title and location:
            rows.append(_job_row(company, source_url=str(job.get("absolute_url") or url), title=title, location=location, department="", posted_at=str(job.get("updated_at") or ""), provider="greenhouse", token=token, generated_at=generated_at))
        if len(rows) >= max_jobs:
            break
    return {"rows": rows, "attempts": [_attempt(ticker, "greenhouse", url, "materialized" if rows else "no_job_rows", reason="" if rows else "Greenhouse returned no parseable title/location rows", raw_path=str(raw_path))]}


def _fetch_lever_jobs(
    company: Mapping[str, Any],
    url: str,
    *,
    token: str,
    generated_at: str,
    raw_dir: Path,
    timeout_s: float,
    max_jobs: int,
) -> dict[str, list[dict[str, Any]]]:
    ticker = str(company.get("ticker") or "").strip().upper()
    status, body, reason = _fetch_text(url, timeout_s=timeout_s, accept="application/json")
    raw_path = raw_dir / _slug(ticker) / f"lever_{_stable_digest(url)}.json"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(body or "", encoding="utf-8")
    if status != "ok":
        return {"rows": [], "attempts": [_attempt(ticker, "lever", url, status, reason=reason, raw_path=str(raw_path))]}
    data = _parse_json(body)
    rows = []
    for job in data if isinstance(data, list) else []:
        if not isinstance(job, Mapping):
            continue
        title = str(job.get("text") or "").strip()
        categories = job.get("categories") if isinstance(job.get("categories"), Mapping) else {}
        location = str(categories.get("location") or "").strip()
        if title and location:
            rows.append(_job_row(company, source_url=str(job.get("hostedUrl") or job.get("applyUrl") or url), title=title, location=location, department=str(categories.get("team") or ""), posted_at=str(job.get("createdAt") or ""), provider="lever", token=token, generated_at=generated_at))
        if len(rows) >= max_jobs:
            break
    return {"rows": rows, "attempts": [_attempt(ticker, "lever", url, "materialized" if rows else "no_job_rows", reason="" if rows else "Lever returned no parseable title/location rows", raw_path=str(raw_path))]}


def _fetch_ashby_jobs(
    company: Mapping[str, Any],
    url: str,
    *,
    token: str,
    generated_at: str,
    raw_dir: Path,
    timeout_s: float,
    max_jobs: int,
) -> dict[str, list[dict[str, Any]]]:
    ticker = str(company.get("ticker") or "").strip().upper()
    status, body, reason = _fetch_text(url, timeout_s=timeout_s, accept="application/json")
    raw_path = raw_dir / _slug(ticker) / f"ashby_{_stable_digest(url)}.json"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(body or "", encoding="utf-8")
    if status != "ok":
        return {"rows": [], "attempts": [_attempt(ticker, "ashby", url, status, reason=reason, raw_path=str(raw_path))]}
    data = _parse_json(body)
    rows = []
    jobs = data.get("jobs") if isinstance(data, Mapping) else []
    for job in jobs if isinstance(jobs, list) else []:
        if not isinstance(job, Mapping):
            continue
        title = str(job.get("title") or "").strip()
        location = str(job.get("location") or "").strip()
        if not location:
            location = _ashby_postal_location(job)
        department = str(job.get("department") or job.get("team") or "").strip()
        posted_at = str(job.get("publishedAt") or "").strip()
        source_url = str(job.get("jobUrl") or job.get("applyUrl") or url).strip()
        if title and location:
            rows.append(_job_row(company, source_url=source_url, title=title, location=location, department=department, posted_at=posted_at, provider="ashby", token=token, generated_at=generated_at))
        if len(rows) >= max_jobs:
            break
    return {"rows": rows, "attempts": [_attempt(ticker, "ashby", url, "materialized" if rows else "no_job_rows", reason="" if rows else "Ashby returned no parseable title/location rows", raw_path=str(raw_path))]}


def _ashby_postal_location(job: Mapping[str, Any]) -> str:
    address = job.get("address")
    postal = address.get("postalAddress") if isinstance(address, Mapping) and isinstance(address.get("postalAddress"), Mapping) else {}
    if not isinstance(postal, Mapping):
        return ""
    parts = [str(postal.get(key) or "").strip() for key in ("addressLocality", "addressRegion", "addressCountry")]
    return ", ".join(part for part in parts if part)


def _parse_phenom_embedded_jobs(
    company: Mapping[str, Any],
    body: str,
    *,
    source_url: str,
    generated_at: str,
    max_jobs: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for match in re.finditer(r'"title"\s*:\s*"([^"]{5,180})"', body or "", flags=re.I):
        title = html.unescape(match.group(1)).strip()
        window = body[max(0, match.start() - 1800) : min(len(body), match.end() + 2200)]
        if "jobSeqNo" not in window and "jobId" not in window and "applyUrl" not in window:
            continue
        if title.lower() in {"shareinfotext", "search results", "find jobs"}:
            continue
        location = _regex_json_value(window, "location") or _regex_json_value(window, "cityStateCountry") or _regex_json_value(window, "cityState")
        if not location:
            continue
        apply_url = _regex_json_value(window, "applyUrl") or source_url
        posted_at = _regex_json_value(window, "postedDate") or _regex_json_value(window, "dateCreated")
        department = _regex_json_value(window, "category")
        key = (title, location)
        if key in seen:
            continue
        seen.add(key)
        rows.append(_job_row(company, source_url=apply_url, title=title, location=location, department=department, posted_at=posted_at, provider="phenom_embedded", token=urlparse(source_url).netloc, generated_at=generated_at))
        if len(rows) >= max_jobs:
            break
    return rows


def _parse_successfactors_search_jobs(
    company: Mapping[str, Any],
    body: str,
    *,
    source_url: str,
    generated_at: str,
    max_jobs: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row_match in re.finditer(r"<tr\b[^>]*>(.*?)</tr>", body or "", flags=re.I | re.S):
        row_html = row_match.group(1)
        title_match = re.search(r'<a[^>]+class=["\'][^"\']*jobTitle-link[^"\']*["\'][^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', row_html, flags=re.I | re.S)
        if not title_match:
            continue
        title = _strip_tags(title_match.group(2))
        location_match = re.search(r'<span[^>]+class=["\'][^"\']*jobLocation[^"\']*["\'][^>]*>(.*?)</span>', row_html, flags=re.I | re.S)
        if not location_match:
            location_match = re.search(r'<td[^>]+class=["\'][^"\']*location[^"\']*["\'][^>]*>(.*?)</td>', row_html, flags=re.I | re.S)
        location = _strip_tags(location_match.group(1)) if location_match else ""
        if not title or not location or title.lower() == "job title":
            continue
        url = urljoin(source_url, html.unescape(title_match.group(1)))
        key = (title, location)
        if key in seen:
            continue
        seen.add(key)
        rows.append(_job_row(company, source_url=url, title=title, location=location, department="", posted_at="", provider="successfactors_html", token=urlparse(source_url).netloc, generated_at=generated_at))
        if len(rows) >= max_jobs:
            break
    return rows


def _parse_generic_job_search_table_jobs(
    company: Mapping[str, Any],
    body: str,
    *,
    source_url: str,
    generated_at: str,
    max_jobs: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row_match in re.finditer(r"(?is)<tr\b[^>]*data-job-url=[\"'](?P<url>[^\"']+)[\"'][^>]*>(?P<html>.*?)</tr>", body or ""):
        row_html = row_match.group("html")
        title_match = re.search(r"(?is)<td\b[^>]*class=[\"'][^\"']*job-search-results-title[^\"']*[\"'][^>]*>(?P<title>.*?)</td>", row_html)
        location_match = re.search(r"(?is)<td\b[^>]*class=[\"'][^\"']*job-search-results-location[^\"']*[\"'][^>]*>(?P<location>.*?)</td>", row_html)
        if not title_match or not location_match:
            continue
        title = _strip_tags(title_match.group("title"))
        location = _strip_tags(location_match.group("location"))
        key = (title, location)
        if not title or not location or key in seen:
            continue
        seen.add(key)
        rows.append(
            _job_row(
                company,
                source_url=urljoin(source_url, html.unescape(row_match.group("url"))),
                title=title,
                location=location,
                department="",
                posted_at=generated_at[:10],
                provider="generic_job_search_table_html",
                token=urlparse(source_url).netloc,
                generated_at=generated_at,
            )
        )
        if len(rows) >= max_jobs:
            break
    return rows


def _parse_talentbrew_search_jobs(
    company: Mapping[str, Any],
    body: str,
    *,
    source_url: str,
    generated_at: str,
    max_jobs: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item_match in re.finditer(r"<li\b[^>]*>(?P<html>.*?)(?=<li\b|</ul>|</section>)", body or "", flags=re.I | re.S):
        item_html = item_match.group("html")
        link_match = re.search(r'<a\b[^>]+href=["\'](?P<href>[^"\']*/job/[^"\']+)["\'][^>]*>(?P<label>.*?)</a>', item_html, flags=re.I | re.S)
        if not link_match:
            continue
        title = _strip_tags(link_match.group("label"))
        if not title:
            data_title_match = re.search(r'\bdata-title=["\'](?P<title>[^"\']+)["\']', item_html, flags=re.I)
            title = html.unescape(data_title_match.group("title")).strip() if data_title_match else ""
        location_match = re.search(r'<span\b[^>]+class=["\'][^"\']*job-location[^"\']*["\'][^>]*>(?P<location>.*?)</span>', item_html, flags=re.I | re.S)
        location = _strip_tags(location_match.group("location")) if location_match else ""
        if not title or not location:
            continue
        url = urljoin(source_url, html.unescape(link_match.group("href")))
        key = (title, location)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            _job_row(
                company,
                source_url=url,
                title=title,
                location=location,
                department="",
                posted_at="",
                provider="talentbrew_html",
                token=urlparse(source_url).netloc,
                generated_at=generated_at,
            )
        )
        if len(rows) >= max_jobs:
            break
    return rows


def _parse_google_careers_html_jobs(
    company: Mapping[str, Any],
    body: str,
    *,
    source_url: str,
    generated_at: str,
    max_jobs: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for match in re.finditer(r'<h3\b[^>]*class=["\'][^"\']*QJPWVe[^"\']*["\'][^>]*>(?P<title>.*?)</h3>', body or "", flags=re.I | re.S):
        title = _strip_tags(match.group("title"))
        window = body[match.end() : min(len(body), match.end() + 2200)]
        location_match = re.search(r'<span\b[^>]*class=["\'][^"\']*r0wTof[^"\']*["\'][^>]*>(?P<location>.*?)</span>', window, flags=re.I | re.S)
        if not location_match:
            location_match = re.search(r'<i\b[^>]*>\s*place\s*</i>\s*<span[^>]*>(?P<location>.*?)</span>', window, flags=re.I | re.S)
        location = _strip_tags(location_match.group("location")) if location_match else ""
        if not title or not location:
            continue
        key = (title, location)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            _job_row(
                company,
                source_url=source_url,
                title=title,
                location=location,
                department="",
                posted_at="",
                provider="google_careers_html",
                token="google_careers",
                generated_at=generated_at,
            )
        )
        if len(rows) >= max_jobs:
            break
    return rows


def _parse_amazon_jobs_payload(
    company: Mapping[str, Any],
    body: str,
    *,
    source_url: str,
    generated_at: str,
    max_jobs: int,
) -> list[dict[str, Any]]:
    data = _parse_json(body)
    jobs = data.get("jobs") if isinstance(data, Mapping) else []
    rows: list[dict[str, Any]] = []
    for job in jobs if isinstance(jobs, list) else []:
        if not isinstance(job, Mapping):
            continue
        title = str(job.get("title") or "").strip()
        location = str(job.get("normalized_location") or job.get("location") or "").strip()
        posted_at = str(job.get("posted_date") or job.get("posted_date_iso") or job.get("updated_time") or "").strip()
        job_path = str(job.get("job_path") or job.get("url_next_step") or "").strip()
        job_url = urljoin("https://www.amazon.jobs", job_path) if job_path else source_url
        if title and location:
            rows.append(
                _job_row(
                    company,
                    source_url=job_url,
                    title=title,
                    location=location,
                    department="",
                    posted_at=posted_at,
                    provider="amazon_jobs_api",
                    token="amazon.jobs",
                    generated_at=generated_at,
                )
            )
        if len(rows) >= max_jobs:
            break
    return rows


def _parse_shopify_singlefetch_jobs(
    company: Mapping[str, Any],
    body: str,
    *,
    source_url: str,
    generated_at: str,
    max_jobs: int,
) -> list[dict[str, Any]]:
    payload = _parse_react_router_singlefetch_payload(body)
    if not isinstance(payload, list):
        return []
    resolver = _DevalueResolver(payload)
    page_payload: Any = None
    for idx, value in enumerate(payload):
        if not isinstance(value, Mapping):
            continue
        for key_ref in value:
            key_idx = _devalue_ref_index(key_ref)
            if key_idx is not None and key_idx < len(payload) and payload[key_idx] == "jobPostingsWithJobs":
                page_payload = resolver.resolve(idx)
                break
        if isinstance(page_payload, Mapping):
            break
    if not isinstance(page_payload, Mapping):
        return []

    location_by_id: dict[str, str] = {}
    for location in page_payload.get("atsLocations") or []:
        if not isinstance(location, Mapping):
            continue
        location_id = str(location.get("id") or "").strip()
        location_name = str(location.get("externalName") or location.get("name") or "").strip()
        if not location_name:
            address = location.get("address")
            postal = address.get("postalAddress") if isinstance(address, Mapping) and isinstance(address.get("postalAddress"), Mapping) else {}
            location_name = ", ".join(str(postal.get(key) or "").strip() for key in ("addressLocality", "addressRegion", "addressCountry") if str(postal.get(key) or "").strip())
        if location_id and location_name:
            location_by_id[location_id] = location_name

    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in page_payload.get("jobPostingsWithJobs") or []:
        if not isinstance(item, Mapping):
            continue
        posting = item.get("jobPosting") if isinstance(item.get("jobPosting"), Mapping) else {}
        job = item.get("job") if isinstance(item.get("job"), Mapping) else {}
        if posting.get("isListed") is False:
            continue
        title = str(posting.get("title") or job.get("title") or "").strip()
        location = str(posting.get("locationExternalName") or posting.get("locationName") or "").strip()
        location_ids = posting.get("locationIds") if isinstance(posting.get("locationIds"), Mapping) else {}
        primary_location_id = str(location_ids.get("primaryLocationId") or job.get("locationId") or "").strip()
        if not location and primary_location_id:
            location = location_by_id.get(primary_location_id, "")
        workplace_type = str(posting.get("workplaceType") or job.get("workplaceType") or "").strip()
        if workplace_type and workplace_type.lower() not in location.lower():
            location = f"{location} ({workplace_type})" if location else workplace_type
        department = str(posting.get("teamName") or posting.get("departmentName") or "").strip()
        posted_at = str(posting.get("publishedDate") or posting.get("updatedAt") or "").strip()
        job_url = str(posting.get("externalLink") or posting.get("applyLink") or source_url).strip()
        if not title or not location:
            continue
        key = (title, location)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            _job_row(
                company,
                source_url=job_url,
                title=title,
                location=location,
                department=department,
                posted_at=posted_at,
                provider="shopify_singlefetch_ashby_jobs",
                token="shopify_careers_singlefetch",
                generated_at=generated_at,
            )
        )
        if len(rows) >= max_jobs:
            break
    return rows


def _parse_react_router_singlefetch_payload(body: str) -> Any:
    marker = "window.__reactRouterContext.streamController.enqueue("
    start = (body or "").find(marker)
    if start < 0:
        return {}
    arg_start = start + len(marker)
    arg_end = (body or "").find(");</script>", arg_start)
    if arg_end < 0:
        return {}
    try:
        decoded = json.loads(body[arg_start:arg_end])
        return json.loads(decoded)
    except Exception:  # noqa: BLE001
        return {}


class _DevalueResolver:
    def __init__(self, values: list[Any]) -> None:
        self.values = values
        self.cache: dict[int, Any] = {}

    def resolve(self, index: int) -> Any:
        if index < 0 or index >= len(self.values):
            return None
        if index in self.cache:
            return self.cache[index]
        value = self.values[index]
        if isinstance(value, Mapping):
            out: dict[str, Any] = {}
            self.cache[index] = out
            for key_ref, value_ref in value.items():
                key_idx = _devalue_ref_index(key_ref)
                key = self.resolve(key_idx) if key_idx is not None else key_ref
                out[str(key)] = self.resolve(value_ref) if isinstance(value_ref, int) else value_ref
            return out
        if isinstance(value, list):
            out_list: list[Any] = []
            self.cache[index] = out_list
            out_list.extend(self.resolve(item) if isinstance(item, int) else item for item in value)
            return out_list
        return value


def _devalue_ref_index(value: Any) -> int | None:
    text = str(value or "")
    if text.startswith("_"):
        text = text[1:]
    try:
        return int(text)
    except ValueError:
        return None


def _parse_cognizant_card_jobs(
    company: Mapping[str, Any],
    body: str,
    *,
    source_url: str,
    generated_at: str,
    max_jobs: int,
) -> list[dict[str, Any]]:
    return _parse_card_job_html_jobs(company, body, source_url=source_url, generated_at=generated_at, max_jobs=max_jobs, provider="cognizant_card_job_html", token="careers.cognizant.com")


def _parse_card_job_html_jobs(
    company: Mapping[str, Any],
    body: str,
    *,
    source_url: str,
    generated_at: str,
    max_jobs: int,
    provider: str,
    token: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    pattern = re.compile(r'<div\b[^>]*class=["\'][^"\']*card-job[^"\']*["\'][^>]*>(?P<card>.*?</div>\s*</div>)', flags=re.I | re.S)
    for match in pattern.finditer(body or ""):
        card = match.group("card")
        link_match = re.search(r'<h[23]\b[^>]*class=["\'][^"\']*card-title[^"\']*["\'][^>]*>\s*<a\b[^>]*href=["\'](?P<href>[^"\']+)["\'][^>]*>(?P<title>.*?)</a>', card, flags=re.I | re.S)
        if not link_match:
            continue
        title = _strip_tags(link_match.group("title"))
        posted_match = re.search(r'<time\b[^>]*datetime=["\'](?P<date>[^"\']+)["\']', card, flags=re.I)
        posted_at = html.unescape(posted_match.group("date")).strip() if posted_match else ""
        meta_match = re.search(r'<ul\b[^>]*class=["\'][^"\']*job-meta[^"\']*["\'][^>]*>(?P<meta>.*?)</ul>', card, flags=re.I | re.S)
        meta_items = re.findall(r'<li\b[^>]*>(?P<item>.*?)</li>', meta_match.group("meta") if meta_match else "", flags=re.I | re.S)
        location = _strip_tags(meta_items[0]) if meta_items else ""
        department = _strip_tags(meta_items[1]) if len(meta_items) > 1 else ""
        location_match = re.search(r'<span\b[^>]*class=["\'][^"\']*job-meta-location[^"\']*["\'][^>]*>(?P<location>.*?)</span>', card, flags=re.I | re.S)
        if location_match:
            location = _strip_tags(location_match.group("location"))
        if not department:
            meta_values = [_strip_tags(item) for item in re.findall(r'<div\b[^>]*class=["\'][^"\']*job-meta[^"\']*["\'][^>]*>(?P<meta>.*?)</div>', card, flags=re.I | re.S) for item in re.findall(r'<p\b[^>]*>(?P<item>.*?)</p>', item, flags=re.I | re.S)]
            clean_values = [value for value in meta_values if value and value != location and not re.fullmatch(r"\d+", value) and not re.fullmatch(r"\d{2}/\d{2}/\d{4}", value)]
            department = clean_values[0] if clean_values else ""
        if not title or not location:
            continue
        key = (title, location)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            _job_row(
                company,
                source_url=urljoin(source_url, html.unescape(link_match.group("href"))),
                title=title,
                location=location,
                department=department,
                posted_at=posted_at,
                provider=provider,
                token=token,
                generated_at=generated_at,
            )
        )
        if len(rows) >= max_jobs:
            break
    return rows


def _parse_paradox_preload_jobs(
    company: Mapping[str, Any],
    body: str,
    *,
    source_url: str,
    generated_at: str,
    max_jobs: int,
) -> list[dict[str, Any]]:
    data = _parse_window_json_assignment(body, "window.__PRELOAD_STATE__")
    job_search = data.get("jobSearch") if isinstance(data, Mapping) and isinstance(data.get("jobSearch"), Mapping) else {}
    jobs = job_search.get("jobs") if isinstance(job_search, Mapping) else []
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for job in jobs if isinstance(jobs, list) else []:
        if not isinstance(job, Mapping):
            continue
        title = str(job.get("title") or "").strip()
        locations = job.get("locations")
        first_location = locations[0] if isinstance(locations, list) and locations and isinstance(locations[0], Mapping) else {}
        location = str(first_location.get("locationParsedText") or first_location.get("locationText") or first_location.get("cityStateAbbr") or first_location.get("cityState") or "").strip()
        department = ""
        for field in job.get("customFields") or []:
            if isinstance(field, Mapping) and str(field.get("cfKey") or "") in {"cf_functional_area", "cf_brand"}:
                department = str(field.get("value") or "").strip()
                if department:
                    break
        job_url = str(job.get("applyURL") or job.get("originalURL") or source_url).strip()
        if not title or not location:
            continue
        key = (title, location)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            _job_row(
                company,
                source_url=job_url,
                title=title,
                location=location,
                department=department,
                posted_at="",
                provider="paradox_preload_jobs",
                token=urlparse(source_url).netloc.lower(),
                generated_at=generated_at,
            )
        )
        if len(rows) >= max_jobs:
            break
    return rows


def _fetch_sea_careers_jobs(
    company: Mapping[str, Any],
    page_body: str,
    *,
    source_url: str,
    generated_at: str,
    timeout_s: float,
    max_jobs: int,
) -> dict[str, list[dict[str, Any]]]:
    ticker = str(company.get("ticker") or "").strip().upper()
    api_url = "https://career.sea.com/api/user/job/list?externalEntityId=3&limit=10&offset=0&postType=1"
    status, body, reason = _fetch_text(api_url, timeout_s=timeout_s, accept="application/json,*/*")
    if status != "ok":
        return {"rows": [], "attempts": [_attempt(ticker, "sea_careers_api", api_url, status, reason=reason, raw_path="")]}
    rows = _parse_sea_careers_api_jobs(company, page_body, body, source_url=api_url, generated_at=generated_at, max_jobs=max_jobs)
    return {
        "rows": rows,
        "attempts": [
            _attempt(
                ticker,
                "sea_careers_api",
                api_url,
                "materialized" if rows else "no_job_rows",
                reason="" if rows else "Sea careers API returned no parseable job_name/city rows",
                raw_path="",
            )
        ],
    }


def _parse_sea_careers_api_jobs(
    company: Mapping[str, Any],
    page_body: str,
    api_body: str,
    *,
    source_url: str,
    generated_at: str,
    max_jobs: int,
) -> list[dict[str, Any]]:
    data = _parse_json(api_body)
    payload = data.get("data") if isinstance(data, Mapping) and isinstance(data.get("data"), Mapping) else {}
    jobs = payload.get("job_list") or payload.get("jobList") if isinstance(payload, Mapping) else []
    city_by_id = {city_id: name for city_id, name in re.findall(r'\\"cityId\\":(\d+),\\"cityName\\":\\"([^\\"]+)\\"', page_body or "")}
    dept_by_id = {dept_id: name for dept_id, name in re.findall(r'\\"deptId\\":(\d+),\\"deptName\\":\\"([^\\"]+)\\"', page_body or "")}
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for job in jobs if isinstance(jobs, list) else []:
        if not isinstance(job, Mapping):
            continue
        title = str(job.get("job_name") or job.get("jobName") or "").strip()
        city_id = str(job.get("city_id") or job.get("cityId") or "").strip()
        department_id = str(job.get("department_id") or job.get("departmentId") or "").strip()
        location = city_by_id.get(city_id, "")
        department = dept_by_id.get(department_id, "")
        job_id = str(job.get("job_id") or job.get("jobId") or job.get("id") or "").strip()
        job_url = f"https://career.sea.com/position/{job_id}" if job_id else source_url
        if not title or not location:
            continue
        key = (title, location)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            _job_row(
                company,
                source_url=job_url,
                title=title,
                location=location,
                department=department,
                posted_at="",
                provider="sea_careers_api",
                token="career.sea.com",
                generated_at=generated_at,
            )
        )
        if len(rows) >= max_jobs:
            break
    return rows


def _parse_icims_iframe_job_cards(
    company: Mapping[str, Any],
    body: str,
    *,
    source_url: str,
    generated_at: str,
    max_jobs: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for match in re.finditer(r'<li\b[^>]*class=["\'][^"\']*iCIMS_JobCardItem[^"\']*["\'][^>]*>(?P<card>.*?)(?=<li\b[^>]*class=["\'][^"\']*iCIMS_JobCardItem|</ul>)', body or "", flags=re.I | re.S):
        card = match.group("card")
        link_match = re.search(r'<a\b[^>]*href=["\'](?P<href>[^"\']+)["\'][^>]*class=["\'][^"\']*iCIMS_Anchor[^"\']*["\'][^>]*>.*?<h3\b[^>]*>(?P<title>.*?)</h3>', card, flags=re.I | re.S)
        if not link_match:
            continue
        title = _strip_tags(link_match.group("title"))
        location = _icims_card_field(card, ("Location", "Job Locations"))
        department = _icims_card_field(card, ("Category", "Company"))
        if not title or not location:
            continue
        key = (title, location)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            _job_row(
                company,
                source_url=urljoin(source_url, html.unescape(link_match.group("href"))),
                title=title,
                location=location,
                department=department,
                posted_at="",
                provider="icims_iframe_job_cards",
                token=urlparse(source_url).netloc.lower(),
                generated_at=generated_at,
            )
        )
        if len(rows) >= max_jobs:
            break
    return rows


def _icims_card_field(card: str, labels: tuple[str, ...]) -> str:
    for label in labels:
        pattern = re.compile(
            rf'<(?:dt|span)\b[^>]*>\s*(?:<[^>]+>\s*)*{re.escape(label)}(?:\s*</[^>]+>)*\s*</(?:dt|span)>.*?<(?:dd|span)\b[^>]*>\s*(?P<value>.*?)</(?:dd|span)>',
            flags=re.I | re.S,
        )
        match = pattern.search(card)
        if match:
            value = _strip_tags(match.group("value"))
            if value:
                return value
    return ""


def _parse_window_json_assignment(body: str, assignment_name: str) -> Any:
    marker = f"{assignment_name} = "
    start = (body or "").find(marker)
    if start < 0:
        return {}
    start += len(marker)
    end = (body or "").find("</script>", start)
    if end < 0:
        end = len(body or "")
    text = body[start:end]
    terminator = text.find(";\n")
    if terminator >= 0:
        text = text[:terminator]
    else:
        text = text.rstrip().removesuffix(";")
    return _parse_json(text.strip())


def _parse_atlassian_careers_payload(
    company: Mapping[str, Any],
    body: str,
    *,
    source_url: str,
    generated_at: str,
    max_jobs: int,
) -> list[dict[str, Any]]:
    data = _parse_json(body)
    jobs = data if isinstance(data, list) else []
    rows: list[dict[str, Any]] = []
    for job in jobs:
        if not isinstance(job, Mapping):
            continue
        title = str(job.get("title") or "").strip()
        locations = job.get("locations")
        if isinstance(locations, list):
            location = "; ".join(str(item).strip() for item in locations if str(item).strip())
        else:
            location = str(locations or "").strip()
        department = str(job.get("category") or "").strip()
        portal = job.get("portalJobPost") if isinstance(job.get("portalJobPost"), Mapping) else {}
        posted_at = str(portal.get("updatedDate") or job.get("updatedDate") or "").strip()
        job_url = str(portal.get("portalUrl") or source_url).strip()
        if title and location:
            rows.append(
                _job_row(
                    company,
                    source_url=job_url,
                    title=title,
                    location=location,
                    department=department,
                    posted_at=posted_at,
                    provider="atlassian_careers_api",
                    token="atlassian",
                    generated_at=generated_at,
                )
            )
        if len(rows) >= max_jobs:
            break
    return rows


def _parse_pcsx_search_payload(
    company: Mapping[str, Any],
    body: str,
    *,
    source_url: str,
    generated_at: str,
    max_jobs: int,
) -> list[dict[str, Any]]:
    data = _parse_json(body)
    payload = data.get("data") if isinstance(data, Mapping) and isinstance(data.get("data"), Mapping) else {}
    positions = payload.get("positions") if isinstance(payload, Mapping) else []
    rows: list[dict[str, Any]] = []
    parsed_source = urlparse(source_url)
    base_url = f"{parsed_source.scheme}://{parsed_source.netloc}"
    for position in positions if isinstance(positions, list) else []:
        if not isinstance(position, Mapping):
            continue
        title = str(position.get("name") or "").strip()
        locations = position.get("locations")
        if isinstance(locations, list):
            location = "; ".join(str(item).strip() for item in locations if str(item).strip())
        else:
            location = str(locations or "").strip()
        department = str(position.get("department") or position.get("profession") or "").strip()
        posted_at = _timestamp_to_date(position.get("postedTs") or position.get("posted_ts") or position.get("creationTs"))
        job_path = str(position.get("positionUrl") or "").strip()
        job_url = urljoin(base_url, job_path) if job_path else source_url
        if title and location:
            rows.append(
                _job_row(
                    company,
                    source_url=job_url,
                    title=title,
                    location=location,
                    department=department,
                    posted_at=posted_at,
                    provider="pcsx_careers_api",
                    token=parsed_source.netloc.lower(),
                    generated_at=generated_at,
                )
            )
        if len(rows) >= max_jobs:
            break
    return rows


def _fetch_verizon_browser_jobs(
    company: Mapping[str, Any],
    page_url: str,
    *,
    generated_at: str,
    raw_dir: Path,
    timeout_s: float,
    max_jobs: int,
) -> dict[str, list[dict[str, Any]]]:
    ticker = str(company.get("ticker") or "").strip().upper()
    if max_jobs <= 0:
        return {"rows": [], "attempts": []}
    raw_path = raw_dir / _slug(ticker) / f"verizon_browser_jobs_{_stable_digest(page_url)}.json"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    api_path = f"/api/jobs/search/?page=1&pagesize={max(1, int(max_jobs or 1))}"
    try:
        from playwright.sync_api import sync_playwright

        executable_path = _browser_executable_path()
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, executable_path=executable_path or None)
            try:
                page = browser.new_page(user_agent=USER_AGENT)
                page.goto(page_url, wait_until="domcontentloaded", timeout=max(10_000, int(timeout_s * 1000)))
                page.wait_for_timeout(1500)
                payload = page.evaluate(
                    """async ({apiPath}) => {
                        const response = await fetch(apiPath, {headers: {accept: 'application/json'}});
                        const text = await response.text();
                        return {status: response.status, ok: response.ok, url: new URL(apiPath, location.href).toString(), text};
                    }""",
                    {"apiPath": api_path},
                )
            finally:
                browser.close()
    except Exception as exc:  # noqa: BLE001
        raw_path.write_text("", encoding="utf-8")
        return {
            "rows": [],
            "attempts": [
                _attempt(
                    ticker,
                    "verizon_next_jobs_browser_api",
                    page_url,
                    "browser_fetch_failed",
                    reason=f"{type(exc).__name__}: {str(exc)[:220]}",
                    raw_path=str(raw_path),
                )
            ],
        }

    status_code = int(payload.get("status") or 0) if isinstance(payload, Mapping) else 0
    body = str(payload.get("text") or "") if isinstance(payload, Mapping) else ""
    api_url = str(payload.get("url") or urljoin(page_url, api_path)) if isinstance(payload, Mapping) else urljoin(page_url, api_path)
    raw_path.write_text(body or "", encoding="utf-8")
    if status_code >= 400 or not body:
        return {
            "rows": [],
            "attempts": [
                _attempt(
                    ticker,
                    "verizon_next_jobs_browser_api",
                    api_url,
                    f"http_{status_code}" if status_code else "empty_response",
                    reason="Verizon careers API did not return parser-ready JSON in browser context.",
                    raw_path=str(raw_path),
                )
            ],
        }
    rows = _parse_verizon_next_jobs_payload(company, body, source_url=api_url, generated_at=generated_at, max_jobs=max_jobs)
    return {
        "rows": rows,
        "attempts": [
            _attempt(
                ticker,
                "verizon_next_jobs_browser_api",
                api_url,
                "materialized" if rows else "no_job_rows",
                reason="" if rows else "Verizon Next jobs API returned no parseable title/location rows",
                raw_path=str(raw_path),
            )
        ],
    }


def _parse_verizon_next_jobs_payload(
    company: Mapping[str, Any],
    body: str,
    *,
    source_url: str,
    generated_at: str,
    max_jobs: int,
) -> list[dict[str, Any]]:
    data = _parse_json(body)
    jobs = data.get("jobs") if isinstance(data, Mapping) else []
    parsed_source = urlparse(source_url)
    base_url = f"{parsed_source.scheme}://{parsed_source.netloc}"
    rows: list[dict[str, Any]] = []
    for job in jobs if isinstance(jobs, list) else []:
        if not isinstance(job, Mapping):
            continue
        title = str(job.get("Title") or job.get("title") or "").strip()
        teams = job.get("Teams") or job.get("teams") or []
        department = "; ".join(str(item).strip() for item in teams if str(item).strip()) if isinstance(teams, list) else str(teams or "").strip()
        locations = job.get("Locations") or job.get("locations") or []
        location_parts: list[str] = []
        for location in locations if isinstance(locations, list) else []:
            if isinstance(location, Mapping):
                text = str(location.get("Identifier") or "").strip()
                if not text:
                    text = ", ".join(
                        str(location.get(key) or "").strip()
                        for key in ("City", "Region", "Country")
                        if str(location.get(key) or "").strip()
                    )
                if text:
                    location_parts.append(text)
            elif str(location or "").strip():
                location_parts.append(str(location).strip())
        location_text = "; ".join(_unique(location_parts))
        urls = job.get("Urls") or job.get("urls") or []
        job_path = ""
        for url_item in urls if isinstance(urls, list) else []:
            if isinstance(url_item, Mapping) and (url_item.get("IsDefault") is True or not job_path):
                job_path = str(url_item.get("Url") or url_item.get("url") or "").strip()
        job_url = urljoin(base_url, job_path) if job_path else source_url
        if title and location_text:
            rows.append(
                _job_row(
                    company,
                    source_url=job_url,
                    title=title,
                    location=location_text,
                    department=department,
                    posted_at=generated_at[:10],
                    provider="verizon_next_jobs_browser_api",
                    token="mycareer.verizon.com",
                    generated_at=generated_at,
                )
            )
        if len(rows) >= max_jobs:
            break
    return rows


def _parse_deltek_findly_widget_jobs(
    company: Mapping[str, Any],
    body: str,
    *,
    source_url: str,
    generated_at: str,
    max_jobs: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    pattern = re.compile(r'<li[^>]+class=["\'][^"\']*widget_joblist_row[^"\']*["\'][^>]*>(.*?)</li>', flags=re.I | re.S)
    for match in pattern.finditer(body or ""):
        block = match.group(1)
        href_match = re.search(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', block, flags=re.I | re.S)
        if not href_match:
            continue
        href = html.unescape(href_match.group(1)).strip()
        title = _strip_tags(href_match.group(2))
        category_match = re.search(r'<div[^>]+class=["\'][^"\']*widget_joblist_category[^"\']*["\'][^>]*>(.*?)</div>', block, flags=re.I | re.S)
        location_match = re.search(r'<div[^>]+class=["\'][^"\']*widget_joblist_loc[^"\']*["\'][^>]*>(.*?)</div>', block, flags=re.I | re.S)
        department = _strip_tags(category_match.group(1)) if category_match else ""
        location = _strip_tags(location_match.group(1)) if location_match else ""
        source = urljoin(source_url, href)
        key = (title, location)
        if not title or not location or key in seen:
            continue
        seen.add(key)
        row = _job_row(
            company,
            source_url=source,
            title=title,
            location=location,
            department=department,
            posted_at=generated_at[:10],
            provider="deltek_findly_widget_jobs",
            token="careers.deltek.com",
            generated_at=generated_at,
        )
        row["subsidiary_binding"] = {
            "subsidiary_name": "Deltek",
            "parent_issuer_ticker": str(company.get("ticker") or "").strip().upper(),
            "binding_boundary": "Deltek official careers rows are used as a Roper subsidiary hiring signal only.",
        }
        row["issuer_binding_status"] = "issuer_subsidiary_official_domain_bound"
        if isinstance(row.get("entity_binding"), dict):
            row["entity_binding"]["issuer_binding_status"] = "issuer_subsidiary_official_domain_bound"
            row["entity_binding"]["resolver_status"] = "official_subsidiary_careers_bound_to_parent_issuer"
        row["resolver_status"] = "official_subsidiary_careers_bound_to_parent_issuer"
        row["claim_boundary"] = "Official subsidiary careers snapshot supports subsidiary role/geography/focus signal only."
        rows.append(row)
        if len(rows) >= max_jobs:
            break
    return rows


def _timestamp_to_date(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value or "").strip()
    if number > 10_000_000_000:
        number = number / 1000
    try:
        return datetime.fromtimestamp(number, tz=timezone.utc).date().isoformat()
    except (OverflowError, OSError, ValueError):
        return str(value or "").strip()


def _jibe_location(payload: Mapping[str, Any]) -> str:
    for key in ("full_location", "short_location", "location_name", "location"):
        value = str(payload.get(key) or "").strip()
        if value:
            return value
    parts = [str(payload.get(key) or "").strip() for key in ("city", "state", "country")]
    return ", ".join(part for part in parts if part)


def _first_named(value: Any) -> str:
    if isinstance(value, list):
        if not value:
            return ""
        first = value[0]
        if isinstance(first, Mapping):
            return str(first.get("name") or first.get("category") or "").strip()
        return str(first or "").strip()
    if isinstance(value, Mapping):
        return str(value.get("name") or value.get("category") or "").strip()
    return str(value or "").strip()


def _regex_json_value(text: str, key: str) -> str:
    match = re.search(rf'"{re.escape(key)}"\s*:\s*"([^"]+)"', text or "", flags=re.I)
    return html.unescape(match.group(1)).strip() if match else ""


def _strip_tags(text: str) -> str:
    value = re.sub(r"<[^>]+>", " ", text or "")
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def _job_row(
    company: Mapping[str, Any],
    *,
    source_url: str,
    title: str,
    location: str,
    department: str,
    posted_at: str,
    provider: str,
    token: str,
    generated_at: str,
) -> dict[str, Any]:
    ticker = str(company.get("ticker") or "").strip().upper()
    evidence_ref = _stable_ref("broad_official_careers", [ticker, provider, source_url, title, location])
    text = f"{ticker} official careers snapshot: {title}; location={location}; department={department}; provider={provider}; posted_at={posted_at}."
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "evidence_ref": evidence_ref,
        "evidence_id": evidence_ref,
        "source_id": "job_postings_hiring_signals",
        "underlying_source_id": provider,
        "source_class": "job_posting_snapshot",
        "source_family": "public_source_context",
        "runtime_source_family": "public_source_context",
        "source_layer_id": "L3",
        "source_layer": "L3",
        "layer_id": "L3",
        "source_specific_parser": "official_careers_ats_job_parser_v0_1",
        "source_specific_resolver": "official_domain_or_ats_to_issuer_resolver_v0_1",
        "parser_status": "source_specific_context_parser_pass",
        "structured_fact_status": "bounded_context_fact_materialized",
        "runtime_ready_context": True,
        "bounded_structured_context": True,
        "structured_context_type": "hiring_capacity_context",
        "requirement_id": "hiring_capacity_proxy",
        "ticker": ticker,
        "company": company.get("company_name") or "",
        "company_name": company.get("company_name") or "",
        "source_url": source_url,
        "citation": {"url": source_url, "source_url": source_url, "title": title},
        "fact_label": title,
        "job_title": title,
        "job_location": location,
        "job_department": department,
        "posted_at": posted_at,
        "date": posted_at or generated_at[:10],
        "period": posted_at or generated_at[:10],
        "product_or_segment": department or title,
        "product_family": department or title,
        "issuer_binding_status": "company_domain_bound",
        "product_binding_status": "product_mentioned_in_snapshot",
        "counterparty_binding_status": "not_bound",
        "entity_binding": {
            "issuer_ticker": ticker,
            "issuer_binding_status": "company_domain_bound",
            "product_binding_status": "product_mentioned_in_snapshot",
            "counterparty_binding_status": "not_bound",
            "resolver_status": "official_careers_or_ats_bound_to_issuer",
            "binding_claim_boundary": "Official careers/ATS job snapshot only; no headcount, demand, revenue, orders, or capacity proof.",
        },
        "resolver_status": "official_careers_or_ats_bound_to_issuer",
        "context_only": True,
        "exact_value_authority": False,
        "can_support_company_exact_fact": False,
        "allowed_claims": ["hiring_signal_context", "market_proxy_context", "verification_lead"],
        "forbidden_claims": ["headcount", "revenue", "order_volume", "production_capacity_fact", "demand_proof"],
        "claim_boundary": "Official careers/ATS job snapshot supports role/geography/focus signal only.",
        "text": text,
        "preview": text,
        "provider": provider,
        "provider_token": token,
    }


def _domains_for_company(ticker: str, company: Mapping[str, Any], domain_cache: Mapping[str, Any]) -> list[str]:
    row = domain_cache.get(ticker) if isinstance(domain_cache, Mapping) else {}
    values = []
    values.extend(DOMAIN_OVERRIDES.get(ticker, ()))
    if isinstance(row, Mapping):
        values.extend(str(domain).strip().lower() for domain in row.get("domains") or [] if str(domain).strip())
    company_name = str(company.get("company_name") or ticker).lower()
    if "." not in ticker and len(ticker) > 1:
        values.append(f"{_slug(company_name).replace('_', '')}.com")
    return [domain for domain in _unique(values) if "." in domain and not domain.endswith(".pdf")]


def _career_candidate_urls(domains: Iterable[str]) -> list[str]:
    urls: list[str] = []
    for domain in domains:
        bare = domain[4:] if domain.startswith("www.") else domain
        for base in (f"https://jobs.{bare}", f"https://careers.{bare}", f"https://{bare}", f"https://www.{bare}"):
            for path in (
                "/jobs",
                "/search",
                "/search/",
                "/search-jobs",
                "/search-jobs?from=0&s=1",
                "/search-results",
                "/search-results?from=0&s=1",
                "/global/en/search-results",
                "/global/en/search-results?from=0&s=1",
                "/us/en/search-results",
                "/us/en/search-results?from=0&s=1",
                "/careers-home",
                "/careers-home/",
                "/careers",
                "/career",
                "",
                "/en/careers",
                "/en-us/careers",
                "/about/careers",
                "/company/careers",
                "/careers/jobs",
            ):
                urls.append(base.rstrip("/") + path)
    return _unique(urls)


def _direct_ats_candidates(ticker: str, company: Mapping[str, Any]) -> list[str]:
    ticker_key = str(ticker or "").upper()
    names = _unique([*ATS_TOKEN_OVERRIDES.get(ticker_key, ()), *_token_candidates(company.get("company_name") or ticker, ticker)])
    urls: list[str] = []
    urls.extend(DIRECT_ATS_URLS.get(ticker_key, ()))
    for token in names:
        urls.append(f"https://boards.greenhouse.io/{token}")
        urls.append(f"https://jobs.lever.co/{token}")
        urls.append(f"https://{token}.wd1.myworkdayjobs.com/External")
        urls.append(f"https://{token}.wd5.myworkdayjobs.com/jobs")
    return urls[:24]


def _token_candidates(company_name: Any, ticker: str) -> list[str]:
    base = _slug(_simplify_company_name(str(company_name or ticker))).replace("_", "")
    ticker_slug = _slug(ticker)
    return _unique([base, _slug(_simplify_company_name(str(company_name or ticker))), ticker_slug])


def _extract_links(body: str, *, base_url: str) -> list[str]:
    parser = _LinkParser(base_url)
    parser.feed(body or "")
    return parser.links


class _LinkParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        values = {key.lower(): value for key, value in attrs}
        href = values.get("href") or ""
        if href:
            self.links.append(urljoin(self.base_url, html.unescape(href)))


def _parse_jsonld_jobs(company: Mapping[str, Any], body: str, *, source_url: str, generated_at: str, max_jobs: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for match in re.finditer(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', body or "", flags=re.I | re.S):
        payload = html.unescape(match.group(1).strip())
        data = _parse_json(payload)
        for item in _walk_json(data):
            if not isinstance(item, Mapping):
                continue
            if str(item.get("@type") or "").lower() != "jobposting":
                continue
            title = str(item.get("title") or "").strip()
            location = _jsonld_location(item)
            posted_at = str(item.get("datePosted") or "").strip()
            if title and location:
                rows.append(_job_row(company, source_url=source_url, title=title, location=location, department="", posted_at=posted_at, provider="jsonld_jobposting", token="", generated_at=generated_at))
            if len(rows) >= max_jobs:
                return rows
    return rows


def _jsonld_location(item: Mapping[str, Any]) -> str:
    location = item.get("jobLocation")
    if isinstance(location, list):
        location = location[0] if location else {}
    if isinstance(location, Mapping):
        address = location.get("address")
        if isinstance(address, Mapping):
            return ", ".join(str(address.get(key) or "").strip() for key in ("addressLocality", "addressRegion", "addressCountry") if str(address.get(key) or "").strip())
    return str(location or "").strip()


def _walk_json(value: Any) -> Iterable[Any]:
    if isinstance(value, Mapping):
        yield value
        for child in value.values():
            yield from _walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_json(child)


def _is_supported_ats_url(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return any(marker in host for marker in ("myworkdayjobs.com", "greenhouse.io", "lever.co", "ashbyhq.com", "oraclecloud.com"))


def _greenhouse_token(url: str) -> str:
    parsed = urlparse(url)
    parts = [part for part in parsed.path.split("/") if part]
    if not parts:
        return ""
    if parts[0] in {"jobs", "job_board"} and len(parts) > 1:
        return parts[1]
    return parts[0]


def _lever_token(url: str) -> str:
    parsed = urlparse(url)
    parts = [part for part in parsed.path.split("/") if part]
    return parts[0] if parts else ""


def _ashby_token(url: str) -> str:
    parsed = urlparse(url)
    parts = [part for part in parsed.path.split("/") if part]
    if "api.ashbyhq.com" in parsed.netloc.lower() and len(parts) >= 3 and parts[:2] == ["posting-api", "job-board"]:
        return parts[2]
    return parts[0] if parts else ""


def _oracle_hcm_site_number(url: str) -> str:
    parsed = urlparse(url)
    parts = [part for part in parsed.path.split("/") if part]
    lowered = [part.lower() for part in parts]
    try:
        idx = lowered.index("sites")
    except ValueError:
        return ""
    if idx + 1 >= len(parts):
        return ""
    site = parts[idx + 1]
    return site.strip()


def _browser_executable_path() -> str:
    for candidate in (
        Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
        Path("C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"),
        Path("C:/Program Files/Microsoft/Edge/Application/msedge.exe"),
        Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"),
    ):
        if candidate.exists():
            return str(candidate)
    return ""


def _fetch_text(url: str, *, timeout_s: float, accept: str = "text/html,application/xhtml+xml,application/json,*/*") -> tuple[str, str, str]:
    try:
        request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
        with urlopen(request, timeout=timeout_s) as response:
            return "ok", response.read().decode("utf-8", errors="ignore"), ""
    except Exception as exc:  # noqa: BLE001
        return _error_status(exc), "", str(exc)[:220]


def _post_json(url: str, payload: bytes, *, timeout_s: float, referer: str = "") -> tuple[str, str, str]:
    try:
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json", "Content-Type": "application/json"}
        if referer:
            headers["Referer"] = referer
        request = Request(url, data=payload, headers=headers)
        with urlopen(request, timeout=timeout_s) as response:
            return "ok", response.read().decode("utf-8", errors="ignore"), ""
    except Exception as exc:  # noqa: BLE001
        return _error_status(exc), "", str(exc)[:220]


def _error_status(exc: BaseException) -> str:
    code = getattr(exc, "code", None)
    return f"http_{code}" if code else "fetch_failed"


def build_summary(
    *,
    rows: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
    matrix_rows: list[dict[str, Any]],
    low_coverage_tickers: set[str],
    generated_at: str,
    output_rows: Path,
    output_attempts: Path,
) -> dict[str, Any]:
    required = {
        str(row.get("ticker") or "").upper()
        for row in matrix_rows
        if (not low_coverage_tickers or str(row.get("ticker") or "").upper() in low_coverage_tickers)
        for req in row.get("source_role_matrix") or []
        if isinstance(req, Mapping) and str(req.get("requirement_id") or "") == "hiring_capacity_proxy"
    }
    success = {str(row.get("ticker") or "").upper() for row in rows if row.get("ticker")}
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "pass" if rows else "gap",
        "required_ticker_count": len(required),
        "success_ticker_count": len(success),
        "unmaterialized_ticker_count": len(required - success),
        "row_count": len(rows),
        "attempt_count": len(attempts),
        "attempt_status_counts": dict(sorted(Counter(str(row.get("status") or "") for row in attempts).items())),
        "provider_counts": dict(sorted(Counter(str(row.get("provider") or "") for row in rows).items())),
        "unmaterialized_tickers": sorted(required - success),
        "outputs": {"rows": str(output_rows), "attempts": str(output_attempts)},
        "boundary": "Only official careers/ATS job rows with title and location are promoted; no careers landing-page fallback.",
    }


def _attempt(ticker: str, provider: str, source_url: str, status: str, *, reason: str, raw_path: str) -> dict[str, Any]:
    return {
        "schema_version": ATTEMPT_SCHEMA_VERSION,
        "attempt_id": _stable_ref("broad_official_careers_attempt", [ticker, provider, source_url, status]),
        "ticker": ticker,
        "provider": provider,
        "source_id": "job_postings_hiring_signals",
        "source_url": source_url,
        "status": status,
        "reason": reason,
        "raw_path": raw_path,
    }


def _parse_json(value: str) -> Any:
    try:
        return json.loads(value)
    except Exception:  # noqa: BLE001
        return {}


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            value = json.loads(text)
            if isinstance(value, Mapping):
                rows.append(dict(value))
    return rows


def _load_domain_cache(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _low_coverage_tickers(path: Path) -> set[str]:
    return {str(row.get("ticker") or "").upper() for row in _load_jsonl(path) if int(row.get("l3_exact_slot_count") or 0) == 0}


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _dedupe_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row.get("evidence_ref") or row.get("evidence_id") or "")
        if key:
            out[key] = dict(row)
    return list(out.values())


def _dedupe_attempts(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row.get("attempt_id") or "")
        if key:
            out[key] = dict(row)
    return list(out.values())


def _unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        text = str(value or "").strip()
        key = text.lower()
        if text and key not in seen:
            seen.add(key)
            out.append(text)
    return out


def _simplify_company_name(value: str) -> str:
    text = value.lower()
    text = re.sub(r"\b(incorporated|inc|corp|corporation|company|co|ltd|limited|plc|ag|sa|group|holdings|holding|the)\b", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split()) or value


def _slug(value: Any) -> str:
    text = str(value or "").lower()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text or "unknown"


def _stable_ref(prefix: str, parts: Iterable[Any]) -> str:
    return f"{prefix}:{_stable_digest('||'.join(str(part or '') for part in parts))}"


def _stable_digest(value: Any) -> str:
    return hashlib.sha1(str(value or "").encode("utf-8", errors="ignore")).hexdigest()[:16]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
