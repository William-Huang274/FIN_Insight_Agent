from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


SCHEMA_VERSION = "finsight_family_channel_distributor_context_row_v0_1"
ATTEMPT_SCHEMA_VERSION = "finsight_family_channel_distributor_attempt_v0_1"
SUMMARY_SCHEMA_VERSION = "finsight_family_channel_distributor_summary_v0_1"

DEFAULT_DOCKET_PATH = REPO_ROOT / "data" / "manifests" / "company_gap_docket_v0_1.jsonl"
DEFAULT_COMPANY_SOURCE_MATRIX = REPO_ROOT / "data" / "manifests" / "company_public_source_coverage_matrix_v0_1.jsonl"
DEFAULT_OFFICIAL_SURFACE_ROWS = REPO_ROOT / "data" / "manifests" / "official_product_surface_context_rows_v0_1.jsonl"
DEFAULT_DOMAIN_CACHE = REPO_ROOT / "data" / "manifests" / "company_domain_locator_cache_v0_1.json"
DEFAULT_FAMILY_ASSIGNMENTS = REPO_ROOT / "data" / "manifests" / "company_product_family_assignments_v0_1.jsonl"
DEFAULT_OUTPUT_ROWS = REPO_ROOT / "data" / "manifests" / "family_channel_distributor_context_rows_v0_1.jsonl"
DEFAULT_OUTPUT_ATTEMPTS = REPO_ROOT / "data" / "manifests" / "family_channel_distributor_attempts_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY = REPO_ROOT / "data" / "manifests" / "family_channel_distributor_context_summary_v0_1.json"
DEFAULT_OUTPUT_REPORT = (
    REPO_ROOT / "docs" / "internal" / "vnext_20260610" / "vertical_lanes" / "family_channel_distributor_context.zh-CN.md"
)
DEFAULT_RAW_DIR = Path("Z:/FIN_Insight_Agent_data/raw_private/public_source_extended_materialization/family_channel_distributors")

SOURCE_ID = "channel_distributor_locator"
REQUIREMENT_ID = "channel_offer_proxy"
FetchFunc = Callable[[str, float], tuple[int, str, str]]

LOCATOR_LINK_RE = re.compile(
    r"where\s+to\s+buy|find\s+(?:a\s+)?(?:dealer|distributor|store|retailer)|dealer\s+locator|"
    r"partner\s+locator|distributor(?:s|\s+locator)?|store\s+locator|authorized\s+distributor|sales\s+office|"
    r"contact\s+sales|sales\s+inquir(?:y|ies)|sales@|retail\s+(?:center|centres?|spaces?)|"
    r"service\s+centers?|dealer\s+recruitment|spaces|buy\s+online|shop\s+now|buy\s+now|official\s+distributor",
    re.IGNORECASE,
)
LOCATOR_PATH_RE = re.compile(
    r"where[-_/]?to[-_/]?buy|dealer[-_/]?locator|find[-_/]?(?:a[-_/]?)?(?:dealer|store|distributor)|"
    r"partner[-_/]?locator|distributors?|store[-_/]?locator|locations?|stores?|retail[-_/]?centers?|service[-_/]?centers?|spaces?|buy[-_/]?online|shop|"
    r"contact[-_/]?sales|sales[-_/]?contact|sales[-_/]?offices?|sales[-_/]?support|sales[-_/]?inquir(?:y|ies)",
    re.IGNORECASE,
)
NOISE_LINK_RE = re.compile(r"privacy|cookie|terms|login|sign[-_]?in|careers|investor|newsletter|warranty|support[-_]?center", re.I)

DIRECT_PATHS = (
    "/where-to-buy",
    "/where-to-buy/",
    "/contact-us/where-to-buy",
    "/contact-us/where-to-buy/",
    "/distributors",
    "/distributors/",
    "/dealer-locator",
    "/dealer-locator/",
    "/find-a-dealer",
    "/find-a-dealer/",
    "/store-locator",
    "/store-locator/",
    "/stores",
    "/stores/",
    "/locations",
    "/locations/",
    "/shop",
    "/shop/",
    "/contact-sales",
    "/contact-sales/",
    "/contact/sales",
    "/contact/sales/",
    "/sales",
    "/sales/",
    "/sales-support",
    "/sales-support/",
)

DOMAIN_OVERRIDES: dict[str, tuple[str, ...]] = {
    "1211.HK": ("byd.com", "bydbatterybox.com", "bydglobal.com", "en.byd.com", "bydautoindia.com"),
    "AMD": ("amd.com",),
    "AZO": ("autozone.com", "autozone.com.mx"),
    "BBY": ("bestbuy.com",),
    "CASY": ("caseys.com",),
    "CAT": ("cat.com", "caterpillar.com"),
    "CHD": ("churchdwight.com", "armandhammer.com", "oxiclean.com"),
    "CMI": ("cummins.com",),
    "CRDO": ("credosemi.com",),
    "DECK": ("deckers.com", "hoka.com", "ugg.com", "teva.com"),
    "DG": ("dollargeneral.com",),
    "DOV": ("dovercorporation.com",),
    "FTV": ("fortive.com", "fluke.com", "tek.com"),
    "GPC": ("genpt.com", "genuine-parts.com", "napaonline.com"),
    "HD": ("homedepot.com", "corporate.homedepot.com"),
    "IEX": ("idexcorp.com",),
    "ITW": ("itw.com", "itwconnect.com", "millerwelds.com"),
    "KMB": ("kimberly-clark.com", "huggies.com", "kleenex.com"),
    "KVUE": ("kenvue.com", "tylenol.com", "listerine.com", "neutrogena.com"),
    "LCID": ("lucidmotors.com",),
    "LI": ("lixiang.com", "liauto.com"),
    "LOW": ("lowes.com",),
    "LULU": ("shop.lululemon.com", "lululemon.com"),
    "MDLZ": ("mondelezinternational.com", "mondelezawayfromhome.com", "oreo.com"),
    "MNST": ("monsterbeverage.com", "monsterenergy.com"),
    "MRVL": ("marvell.com",),
    "NIO": ("nio.com",),
    "PH": ("parker.com",),
    "PPG": ("ppg.com", "ppgpaints.com"),
    "QCOM": ("qualcomm.com",),
    "RIVN": ("rivian.com",),
    "ROK": ("rockwellautomation.com",),
    "SJM": ("jmsmucker.com", "smuckers.com"),
    "SNA": ("snapon.com",),
    "SWK": ("stanleyblackanddecker.com", "stanleytools.com", "dewalt.com", "craftsman.com"),
    "TPR": ("tapestry.com", "coach.com", "katespade.com"),
    "TSCO": ("tractorsupply.com", "corporate.tractorsupply.com"),
    "WAB": ("wabteccorp.com",),
    "XOM": ("exxonmobil.com", "exxon.com"),
}

MANUAL_CHANNEL_SEEDS: dict[str, tuple[str, ...]] = {
    "1211.HK": ("https://www.byd.com/eu/find-store", "https://www.byd.com/uk/find-store", "https://bydautoindia.com/find-dealer"),
    "AMD": ("https://www.amd.com/en/where-to-buy.html",),
    "AZO": ("https://www.autozone.com/locations/",),
    "BBY": ("https://stores.bestbuy.com/",),
    "CASY": ("https://www.caseys.com/store-finder",),
    "CAT": ("https://www.cat.com/en_US/support/dealer-locator.html",),
    "CHD": ("https://www.armandhammer.com/en", "https://www.oxiclean.com/en"),
    "CMI": ("https://www.cummins.com/locations",),
    "COST": ("https://www.costco.com/warehouse-locations",),
    "CRDO": ("https://www.credosemi.com/contact", "https://www.credosemi.com/contact-us"),
    "DECK": ("https://www.hoka.com/en/us/store-locator/", "https://www.ugg.com/stores/"),
    "DG": ("https://www.dollargeneral.com/store-locator.html",),
    "DIOD": ("https://www.diodes.com/sales-support/distributors/",),
    "DOV": ("https://www.dovercorporation.com/segments/worldwide-locations/dover-locations",),
    "GPC": ("https://www.napaonline.com/en/auto-parts-stores-near-me",),
    "FTV": ("https://www.fluke.com/en-us/where-to-buy",),
    "HD": ("https://www.homedepot.com/l/storeDirectory",),
    "IEX": ("https://idexcorp.com/business-directory/",),
    "ITW": ("https://www.millerwelds.com/where-to-buy", "https://www.itw.com/"),
    "KMB": ("https://www.huggies.com/en-us/where-to-buy",),
    "KR": ("https://www.kroger.com/stores/search",),
    "KVUE": ("https://www.tylenol.com/where-to-buy", "https://www.neutrogena.com/where-to-buy",),
    "LI": ("https://www.liauto.com/support/aftersale", "https://www.lixiang.com/en/retail"),
    "LCID": ("https://lucidmotors.com/locations",),
    "LOW": ("https://www.lowes.com/store/",),
    "LULU": ("https://shop.lululemon.com/stores",),
    "MDLZ": (
        "https://www.mondelezawayfromhome.com/where-to-buy/",
        "https://www.mondelezawayfromhome.com/Find-Distributor/",
        "https://www.oreo.com/",
    ),
    "MRVL": ("https://www.marvell.com/company/sales.html", "https://www.marvell.com/company/contact-us.html"),
    "MNST": ("https://www.monsterenergy.com/en-us/where-to-buy/",),
    "NIO": ("https://www.nio.com/locations",),
    "ORLY": ("https://locations.oreillyauto.com/",),
    "PH": ("https://ph.parker.com/us/en/wtb/where-to-buy", "https://www.parker.com/us/en/distribution-network.html"),
    "PPG": ("https://www.ppgpaints.com/store-locator",),
    "QCOM": ("https://www.qualcomm.com/contact/sales",),
    "RIVN": ("https://rivian.com/spaces",),
    "ROK": ("https://www.rockwellautomation.com/en-us/sales/partner-locator.html",),
    "SJM": ("https://www.smuckers.com/where-to-buy", "https://www.jmsmucker.com/smucker-store"),
    "SNA": ("https://shop.snapon.com/webapp/wcs/stores/servlet/StoreLocator",),
    "SWK": ("https://www.stanleytools.com/support/where-to-buy",),
    "TPR": ("https://www.katespade.com/stores", "https://www.coach.com/stores"),
    "TSCO": ("https://www.tractorsupply.com/tsc/store-locator",),
    "WAB": (
        "https://www.wabteccorp.com/marine-solutions/marine-diesel-engines/parts-and-service",
        "https://www.wabteccorp.com/stationary-power-diesel-engines/parts-and-service",
    ),
    "XOM": ("https://www.exxon.com/en/find-station",),
}

READER_PROXY_CHANNEL_SEEDS: dict[str, tuple[str, ...]] = {
    "AZO": ("https://www.autozone.com/locations/ca.html",),
    "CASY": ("https://www.caseys.com/general-store/ia-ankeny/2150", "https://www.caseys.com/locations"),
    "DG": ("https://stores.dollargeneral.com/",),
    "GPC": ("https://www.genpt.com/our-companies", "https://www.napaonline.com/en/store-locator", "https://www.napaonline.com/en/ca/san-diego/store/27415"),
    "HD": ("https://corporate.homedepot.com/page/about-us", "https://www.homedepot.com/l/Long-Island-City/NY/Long-Island-City/11101/1255"),
    "MNST": ("https://www.monsterenergy.com/en-us/where-to-buy/",),
}

TRUSTED_DISTRIBUTOR_SEEDS: dict[str, tuple[str, ...]] = {
    "DIOD": ("https://www.arrow.com/en/manufacturers/d/diodes-incorporated.html",),
    "MPWR": ("https://www.arrow.com/en/manufacturers/m/monolithic-power-systems.html",),
}

TRUSTED_DISTRIBUTOR_DOMAINS = {"arrow.com"}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build family-scoped official channel/distributor locator context rows.")
    parser.add_argument("--docket-path", type=Path, default=DEFAULT_DOCKET_PATH)
    parser.add_argument("--company-source-matrix", type=Path, default=DEFAULT_COMPANY_SOURCE_MATRIX)
    parser.add_argument("--official-surface-rows", type=Path, default=DEFAULT_OFFICIAL_SURFACE_ROWS)
    parser.add_argument("--domain-cache", type=Path, default=DEFAULT_DOMAIN_CACHE)
    parser.add_argument("--family-assignments", type=Path, default=DEFAULT_FAMILY_ASSIGNMENTS)
    parser.add_argument("--output-rows", type=Path, default=DEFAULT_OUTPUT_ROWS)
    parser.add_argument("--output-attempts", type=Path, default=DEFAULT_OUTPUT_ATTEMPTS)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--output-report", type=Path, default=DEFAULT_OUTPUT_REPORT)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--tickers", nargs="*", default=[])
    parser.add_argument("--timeout-s", type=float, default=12.0)
    parser.add_argument("--max-seeds-per-ticker", type=int, default=8)
    parser.add_argument("--max-links-per-seed", type=int, default=6)
    parser.add_argument("--max-rows-per-ticker", type=int, default=2)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--browser-fallback", action="store_true")
    parser.add_argument("--replace-output", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at = _utc_now()
    targets = build_targets(
        docket_rows=_load_jsonl(args.docket_path),
        company_source_matrix_rows=_load_jsonl(args.company_source_matrix),
        family_assignment_rows=_load_jsonl(args.family_assignments),
        tickers=args.tickers,
    )
    rows, attempts = build_family_channel_distributor_context_rows(
        targets=targets,
        official_surface_rows=_load_jsonl(args.official_surface_rows),
        domain_cache=_load_json(args.domain_cache),
        raw_dir=args.raw_dir,
        generated_at=generated_at,
        timeout_s=args.timeout_s,
        max_seeds_per_ticker=args.max_seeds_per_ticker,
        max_links_per_seed=args.max_links_per_seed,
        max_rows_per_ticker=args.max_rows_per_ticker,
        workers=args.workers,
        browser_fallback=args.browser_fallback,
    )
    existing_rows = _load_jsonl(args.output_rows)
    output_rows = rows if args.replace_output else _dedupe_rows([*filter(_output_row_usable, existing_rows), *rows])
    output_attempts = attempts if args.replace_output else _dedupe_attempts([*_load_jsonl(args.output_attempts), *attempts])
    summary = build_summary(
        targets=targets,
        rows=output_rows,
        attempts=output_attempts,
        generated_at=generated_at,
        output_rows=args.output_rows,
        output_attempts=args.output_attempts,
        output_report=args.output_report,
    )
    _write_jsonl(args.output_rows, output_rows)
    _write_jsonl(args.output_attempts, output_attempts)
    _write_json(args.output_summary, summary)
    args.output_report.parent.mkdir(parents=True, exist_ok=True)
    args.output_report.write_text(render_report(summary), encoding="utf-8", newline="\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if args.strict and summary["new_or_existing_success_ticker_count"] <= 0:
        return 1
    return 0


def build_targets(
    *,
    docket_rows: Iterable[Mapping[str, Any]],
    family_assignment_rows: Iterable[Mapping[str, Any]],
    company_source_matrix_rows: Iterable[Mapping[str, Any]] = (),
    tickers: Iterable[str] = (),
) -> list[dict[str, Any]]:
    ticker_filter = {str(ticker).strip().upper() for ticker in tickers if str(ticker).strip()}
    family_by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in family_assignment_rows:
        ticker = str(row.get("ticker") or "").strip().upper()
        if ticker:
            family_by_ticker[ticker].append(dict(row))
    company_by_ticker: dict[str, dict[str, Any]] = {}
    for company in company_source_matrix_rows:
        ticker = str(company.get("ticker") or "").strip().upper()
        if ticker:
            company_by_ticker[ticker] = dict(company)
    targets: dict[str, dict[str, Any]] = {}
    for row in docket_rows:
        if str(row.get("requirement_id") or "") != REQUIREMENT_ID:
            continue
        ticker = str(row.get("ticker") or "").strip().upper()
        if not ticker or (ticker_filter and ticker not in ticker_filter):
            continue
        families = family_by_ticker.get(ticker) or []
        if not families and row.get("family_ids"):
            families = [
                {"family_id": fid, "family_name": name}
                for fid, name in zip(row.get("family_ids") or [], row.get("family_names") or [], strict=False)
            ]
        targets[ticker] = {
            "ticker": ticker,
            "company_name": row.get("company_name") or ticker,
            "primary_lane_id": row.get("primary_lane_id") or "",
            "family_ids": _unique_strings([family.get("family_id") for family in families] or row.get("family_ids") or []),
            "family_names": _unique_strings([family.get("family_name") for family in families] or row.get("family_names") or []),
            "query_terms": _unique_strings(term for family in families for term in (family.get("query_terms") or [])),
            "docket_id": row.get("docket_id") or "",
        }
    for company in company_source_matrix_rows:
        ticker = str(company.get("ticker") or "").strip().upper()
        if not ticker or ticker in targets or (ticker_filter and ticker not in ticker_filter):
            continue
        requirements = {
            str(req.get("requirement_id") or "")
            for req in company.get("source_role_matrix") or []
            if isinstance(req, Mapping)
        }
        if REQUIREMENT_ID not in requirements:
            continue
        families = family_by_ticker.get(ticker) or []
        targets[ticker] = {
            "ticker": ticker,
            "company_name": company.get("company_name") or ticker,
            "primary_lane_id": company.get("primary_lane_id") or "",
            "family_ids": _unique_strings([family.get("family_id") for family in families]),
            "family_names": _unique_strings([family.get("family_name") for family in families]),
            "query_terms": _unique_strings(term for family in families for term in (family.get("query_terms") or [])),
            "docket_id": "",
        }
    for ticker in sorted(ticker_filter):
        if ticker in targets:
            continue
        company = company_by_ticker.get(ticker, {})
        families = family_by_ticker.get(ticker) or []
        targets[ticker] = {
            "ticker": ticker,
            "company_name": company.get("company_name") or ticker,
            "primary_lane_id": company.get("primary_lane_id") or "",
            "family_ids": _unique_strings([family.get("family_id") for family in families]),
            "family_names": _unique_strings([family.get("family_name") for family in families]),
            "query_terms": _unique_strings(term for family in families for term in (family.get("query_terms") or [])),
            "docket_id": "explicit_ticker_channel_probe",
        }
    return sorted(targets.values(), key=lambda row: row["ticker"])


def build_family_channel_distributor_context_rows(
    *,
    targets: list[Mapping[str, Any]],
    official_surface_rows: Iterable[Mapping[str, Any]],
    domain_cache: Mapping[str, Any],
    raw_dir: Path,
    generated_at: str,
    timeout_s: float = 12.0,
    max_seeds_per_ticker: int = 8,
    max_links_per_seed: int = 6,
    max_rows_per_ticker: int = 2,
    workers: int = 8,
    fetch: FetchFunc | None = None,
    browser_fallback: bool = False,
    browser_fetch: FetchFunc | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    fetcher = fetch or _fetch_url
    targets_by_ticker = {str(target.get("ticker") or "").upper(): dict(target) for target in targets}
    seeds_by_ticker = build_seed_urls(
        targets=targets,
        official_surface_rows=official_surface_rows,
        domain_cache=domain_cache,
        max_seeds_per_ticker=max_seeds_per_ticker,
    )
    jobs = [
        (ticker, target, seed)
        for ticker, target in targets_by_ticker.items()
        for seed in seeds_by_ticker.get(ticker, [])
    ]
    attempts: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []

    if not jobs:
        return [], [
            _attempt(
                target.get("ticker") or "",
                "",
                "no_official_seed_url",
                "No official-domain seed URL was available for this channel/distributor target.",
                generated_at=generated_at,
            )
            for target in targets
        ]

    max_workers = max(1, int(workers or 1))
    if max_workers == 1:
        results = [
            _process_seed(
                ticker=ticker,
                target=target,
                seed=seed,
                raw_dir=raw_dir,
                generated_at=generated_at,
                timeout_s=timeout_s,
                max_links_per_seed=max_links_per_seed,
                fetch=fetcher,
                browser_fallback=browser_fallback,
                browser_fetch=browser_fetch,
            )
            for ticker, target, seed in jobs
        ]
    else:
        results = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(
                    _process_seed,
                    ticker=ticker,
                    target=target,
                    seed=seed,
                    raw_dir=raw_dir,
                    generated_at=generated_at,
                    timeout_s=timeout_s,
                    max_links_per_seed=max_links_per_seed,
                    fetch=fetcher,
                    browser_fallback=browser_fallback,
                    browser_fetch=browser_fetch,
                )
                for ticker, target, seed in jobs
            ]
            for future in as_completed(futures):
                results.append(future.result())

    for result in results:
        attempts.extend(result["attempts"])
        rows.extend(result["rows"])

    for ticker, target in targets_by_ticker.items():
        if not seeds_by_ticker.get(ticker):
            attempts.append(
                _attempt(
                    ticker,
                    "",
                    "no_official_seed_url",
                    "No official-domain product/store seed passed domain binding.",
                    generated_at=generated_at,
                    company_name=target.get("company_name") or ticker,
                )
            )

    deduped = _dedupe_rows(rows)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in deduped:
        grouped[str(row.get("ticker") or "").upper()].append(row)
    selected: list[dict[str, Any]] = []
    for ticker, ticker_rows in sorted(grouped.items()):
        selected.extend(sorted(ticker_rows, key=_row_rank, reverse=True)[: max(1, int(max_rows_per_ticker or 1))])
    return selected, _dedupe_attempts(attempts)


def build_seed_urls(
    *,
    targets: list[Mapping[str, Any]],
    official_surface_rows: Iterable[Mapping[str, Any]],
    domain_cache: Mapping[str, Any],
    max_seeds_per_ticker: int,
) -> dict[str, list[dict[str, Any]]]:
    official_by_ticker: dict[str, list[str]] = defaultdict(list)
    for row in official_surface_rows:
        ticker = str(row.get("ticker") or "").strip().upper()
        url = _row_url(row)
        if ticker and url:
            official_by_ticker[ticker].append(url)

    out: dict[str, list[dict[str, Any]]] = {}
    for target in targets:
        ticker = str(target.get("ticker") or "").strip().upper()
        domains = _official_domains(domain_cache, ticker)
        urls: list[tuple[str, str]] = []
        for url in MANUAL_CHANNEL_SEEDS.get(ticker, ()):
            if _url_matches_domains(url, domains):
                urls.append((url, "manual_verified_channel_seed"))
        for url in READER_PROXY_CHANNEL_SEEDS.get(ticker, ()):
            if _url_matches_domains(url, domains):
                urls.append((url, "reader_proxy_official_channel_seed"))
        for url in TRUSTED_DISTRIBUTOR_SEEDS.get(ticker, ()):
            if _url_matches_trusted_distributor(url):
                urls.append((url, "manual_trusted_distributor_seed"))
        for url in official_by_ticker.get(ticker, []):
            if _url_matches_domains(url, domains):
                urls.append((url, "official_product_surface_seed"))
        for domain in domains:
            base = f"https://www.{domain}" if not domain.startswith("www.") else f"https://{domain}"
            urls.append((base + "/", "official_domain_home_seed"))
        for domain in domains:
            base = f"https://www.{domain}" if not domain.startswith("www.") else f"https://{domain}"
            for path in DIRECT_PATHS:
                urls.append((base.rstrip("/") + path, "direct_locator_path_probe"))
        deduped: list[dict[str, Any]] = []
        seen: set[str] = set()
        for url, seed_type in urls:
            normalized = _normalize_url(url)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            seed = {"url": normalized, "seed_type": seed_type, "official_domains": domains}
            if seed_type == "reader_proxy_official_channel_seed":
                seed["fetch_url"] = _reader_proxy_url(normalized)
                seed["fetch_transport"] = "jina_reader_proxy"
            deduped.append(seed)
            if len(deduped) >= max(1, int(max_seeds_per_ticker or 1)):
                break
        out[ticker] = deduped
    return out


def _process_seed(
    *,
    ticker: str,
    target: Mapping[str, Any],
    seed: Mapping[str, Any],
    raw_dir: Path,
    generated_at: str,
    timeout_s: float,
    max_links_per_seed: int,
    fetch: FetchFunc,
    browser_fallback: bool = False,
    browser_fetch: FetchFunc | None = None,
) -> dict[str, list[dict[str, Any]]]:
    url = str(seed.get("url") or "")
    fetch_url = str(seed.get("fetch_url") or url)
    seed_type = str(seed.get("seed_type") or "")
    manual_verified_seed = seed_type in {"manual_verified_channel_seed", "reader_proxy_official_channel_seed"}
    rows: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []
    raw_path = raw_dir / f"{ticker.lower()}_{_stable_digest(fetch_url)}.html"
    cache_used = False
    response_source = "live_fetch"
    try:
        status_code, content_type, body = fetch(fetch_url, timeout_s)
    except Exception as exc:  # noqa: BLE001
        cached_body = _usable_cached_body(raw_path)
        if cached_body:
            status_code, content_type, body = 200, "text/html; cached=1", cached_body
            cache_used = True
        else:
            return {
                "rows": [],
                "attempts": [
                    _attempt(
                        ticker,
                        url,
                        "fetch_failed",
                        f"{type(exc).__name__}: {str(exc)[:220]}",
                        generated_at=generated_at,
                        seed_type=seed.get("seed_type") or "",
                        fetch_transport=seed.get("fetch_transport") or "direct",
                        fetch_transport_url=fetch_url if fetch_url != url else "",
                    )
                ],
            }
    unusable = status_code >= 400 or not str(body or "").strip() or _looks_blocked(body)
    if unusable:
        cached_body = _usable_cached_body(raw_path)
        if cached_body:
            status_code, content_type, body = 200, "text/html; cached=1", cached_body
            cache_used = True
            response_source = "cached_raw"
            unusable = False
    if unusable and browser_fallback and manual_verified_seed:
        try:
            browser_status, _, browser_body = (browser_fetch or _fetch_url_with_browser)(fetch_url, timeout_s)
        except Exception as exc:  # noqa: BLE001
            attempts.append(
                _attempt(
                    ticker,
                    url,
                    "browser_fetch_failed",
                    f"{type(exc).__name__}: {str(exc)[:220]}",
                    generated_at=generated_at,
                    seed_type=seed_type,
                    raw_path=str(raw_path),
                    fetch_transport=seed.get("fetch_transport") or "direct",
                    fetch_transport_url=fetch_url if fetch_url != url else "",
                )
            )
        else:
            if browser_status < 400 and str(browser_body or "").strip() and not _looks_blocked(browser_body):
                status_code, content_type, body = browser_status, "text/html; rendered=playwright", browser_body
                response_source = "live_browser_fetch"
                unusable = False
    if not unusable:
        raw_path.write_text(body or "", encoding="utf-8")
    else:
        return {
            "rows": [],
            "attempts": [
                _attempt(
                    ticker,
                    url,
                    "unusable_response",
                    f"http_{status_code}" if status_code >= 400 else "empty_or_blocked_body",
                    generated_at=generated_at,
                    seed_type=seed_type,
                    raw_path=str(raw_path),
                    fetch_transport=seed.get("fetch_transport") or "direct",
                    fetch_transport_url=fetch_url if fetch_url != url else "",
                )
            ],
        }

    trusted_distributor_seed = seed_type == "manual_trusted_distributor_seed"
    rows, links, page_title, trusted_binding_gap = _parse_seed_body(
        ticker=ticker,
        target=target,
        url=url,
        body=body,
        seed_type=seed_type,
        max_links_per_seed=max_links_per_seed,
        generated_at=generated_at,
        raw_path=raw_path,
    )
    if trusted_binding_gap:
        return {
            "rows": [],
            "attempts": [
                _attempt(
                    ticker,
                    url,
                    "trusted_distributor_seed_binding_gap",
                    "Trusted distributor page did not bind to issuer and channel/distributor context.",
                    generated_at=generated_at,
                    seed_type=seed_type,
                    raw_path=str(raw_path),
                )
            ],
        }
    if not rows and browser_fallback and manual_verified_seed and not cache_used and response_source != "live_browser_fetch":
        try:
            browser_status, _, browser_body = (browser_fetch or _fetch_url_with_browser)(fetch_url, timeout_s)
        except Exception as exc:  # noqa: BLE001
            attempts.append(
                _attempt(
                    ticker,
                    url,
                    "browser_fetch_failed",
                    f"{type(exc).__name__}: {str(exc)[:220]}",
                    generated_at=generated_at,
                    seed_type=seed.get("seed_type") or "",
                    raw_path=str(raw_path),
                    fetch_transport=seed.get("fetch_transport") or "direct",
                    fetch_transport_url=fetch_url if fetch_url != url else "",
                )
            )
        else:
            if browser_status < 400 and str(browser_body or "").strip() and not _looks_blocked(browser_body):
                browser_rows, browser_links, browser_title, browser_trusted_binding_gap = _parse_seed_body(
                    ticker=ticker,
                    target=target,
                    url=url,
                    body=browser_body,
                    seed_type=seed_type,
                    max_links_per_seed=max_links_per_seed,
                    generated_at=generated_at,
                    raw_path=raw_path,
                )
                if browser_rows and not browser_trusted_binding_gap:
                    body = browser_body
                    rows = browser_rows
                    links = browser_links
                    page_title = browser_title
                    raw_path.write_text(browser_body or "", encoding="utf-8")
                    response_source = "live_browser_fetch"
    for row in rows:
        row["fetch_transport"] = seed.get("fetch_transport") or "direct"
        if fetch_url != url:
            row["fetch_transport_url"] = fetch_url
        row["raw_response_source"] = response_source
    attempts.append(
        _attempt(
            ticker,
            url,
            "materialized_from_cached_official_body" if rows and cache_used else "materialized" if rows else "no_locator_link_found",
            "",
            generated_at=generated_at,
            seed_type=seed.get("seed_type") or "",
            raw_path=str(raw_path),
            response_source=response_source,
            fetch_transport=seed.get("fetch_transport") or "direct",
            fetch_transport_url=fetch_url if fetch_url != url else "",
            discovered_count=len(links),
            parsed_row_count=len(rows),
        )
    )
    return {"rows": rows, "attempts": attempts}


def _parse_seed_body(
    *,
    ticker: str,
    target: Mapping[str, Any],
    url: str,
    body: str,
    seed_type: str,
    max_links_per_seed: int,
    generated_at: str,
    raw_path: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, str]], str, bool]:
    rows: list[dict[str, Any]] = []
    page_title = _html_title(body)
    manual_verified_seed = seed_type in {"manual_verified_channel_seed", "reader_proxy_official_channel_seed"}
    trusted_distributor_seed = seed_type == "manual_trusted_distributor_seed"
    clean_limit = 500000 if trusted_distributor_seed or manual_verified_seed else 80000
    clean_body = _clean_html(str(body or "")[:clean_limit]) if manual_verified_seed or trusted_distributor_seed else ""
    if trusted_distributor_seed and (
        not _trusted_distributor_seed_binds_target(target, url=url, page_title=page_title, clean_body=clean_body)
        or not _trusted_distributor_seed_has_channel_context(clean_body)
    ):
        return [], [], page_title, True
    direct_kind = "distributor_locator" if trusted_distributor_seed else _locator_kind_from_text(
        f"{url} {page_title} {clean_body[:200000]}"
    )
    if direct_kind and (_body_has_locator_context(body) or manual_verified_seed or trusted_distributor_seed):
        rows.append(
            _row(
                ticker=ticker,
                target=target,
                source_url=url,
                seed_url=url,
                link_text=page_title or direct_kind.replace("_", " "),
                locator_kind=direct_kind,
                generated_at=generated_at,
                raw_path=raw_path,
            )
        )

    links = extract_locator_links(body, base_url=url, max_links=max_links_per_seed)
    for link in links:
        rows.append(
            _row(
                ticker=ticker,
                target=target,
                source_url=link["url"],
                seed_url=url,
                link_text=link["text"],
                locator_kind=link["locator_kind"],
                generated_at=generated_at,
                raw_path=raw_path,
            )
        )
    return rows, links, page_title, False


def extract_locator_links(body: str, *, base_url: str, max_links: int = 6) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for match in re.finditer(r"(?is)<a\b([^>]*?)href=['\"]([^'\"]+)['\"]([^>]*)>(.*?)</a>", body or ""):
        href = html.unescape(match.group(2) or "").strip()
        text = _clean_html(match.group(4))
        haystack = f"{text} {href}"
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        if NOISE_LINK_RE.search(haystack):
            continue
        if not LOCATOR_LINK_RE.search(haystack):
            continue
        url = _normalize_url(urljoin(base_url, href))
        if not url or url in seen:
            continue
        seen.add(url)
        out.append({"url": url, "text": text or url, "locator_kind": _locator_kind_from_text(haystack) or "official_channel_link"})
        if len(out) >= max(0, int(max_links or 0)):
            break
    return out


def _row(
    *,
    ticker: str,
    target: Mapping[str, Any],
    source_url: str,
    seed_url: str,
    link_text: str,
    locator_kind: str,
    generated_at: str,
    raw_path: Path,
) -> dict[str, Any]:
    family_names = _unique_strings(target.get("family_names") or [])
    product_or_segment = family_names[0] if family_names else str(target.get("primary_lane_id") or "channel/distributor context")
    channel_name = _channel_name(locator_kind)
    fact_label = f"{target.get('company_name') or ticker} {channel_name}: {link_text or source_url}"
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "ticker": ticker,
        "company_name": target.get("company_name") or ticker,
        "primary_lane_id": target.get("primary_lane_id") or "",
        "family_ids": list(target.get("family_ids") or []),
        "family_names": family_names,
        "source_id": SOURCE_ID,
        "underlying_source_id": SOURCE_ID,
        "runtime_source_family": "public_source_context",
        "source_family": "live_public_web_context",
        "source_layer_id": "L3",
        "source_layer": "L3",
        "layer_id": "L3",
        "source_url": source_url,
        "seed_url": seed_url,
        "citation": {"url": source_url, "title": link_text or fact_label, "provider": channel_name},
        "fact_label": fact_label[:260],
        "product_or_segment": product_or_segment,
        "channel_name": channel_name,
        "channel_locator_type": locator_kind,
        "channel_link_text": link_text,
        "raw_path": str(raw_path),
        "parser_status": "source_specific_context_parser_pass",
        "structured_fact_status": "bounded_context_fact_materialized",
        "evidence_graph_status": "runtime_ready_context",
        "runtime_ready_context": True,
        "bounded_structured_context": True,
        "structured_context_type": "channel_distributor_locator_context",
        "context_only": True,
        "exact_value_authority": False,
        "can_support_company_exact_fact": False,
        "issuer_binding_status": "issuer_mentioned_in_snapshot",
        "product_binding_status": "product_mentioned_in_snapshot" if product_or_segment else "not_bound",
        "counterparty_binding_status": "not_bound",
        "allowed_claims": ["channel_distributor_locator_context", "channel_offer_context", "market_proxy_context", "verification_lead"],
        "forbidden_claims": ["asp", "price", "channel_inventory", "sell_through", "sales_volume", "revenue", "market_share"],
        "claim_boundary": (
            "Official or issuer-linked channel/distributor/store locator context only; supports public channel presence, "
            "not price, ASP, channel inventory, sell-through, sales, revenue, demand, or market share."
        ),
        "authority_boundary": "L3 public channel/distributor locator proxy; never exact company metric authority.",
        "evidence_ref": f"channel_distributor:{_stable_digest('|'.join([ticker, source_url, product_or_segment]))}",
    }


def build_summary(
    *,
    targets: list[Mapping[str, Any]],
    rows: list[Mapping[str, Any]],
    attempts: list[Mapping[str, Any]],
    generated_at: str,
    output_rows: Path,
    output_attempts: Path,
    output_report: Path,
) -> dict[str, Any]:
    required = {str(target.get("ticker") or "").upper() for target in targets}
    success = {str(row.get("ticker") or "").upper() for row in rows if row.get("ticker")}
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "pass" if success else "gap",
        "target_ticker_count": len(required),
        "new_or_existing_success_ticker_count": len(success),
        "unmaterialized_ticker_count": len(required - success),
        "row_count": len(rows),
        "attempt_count": len(attempts),
        "row_source_counts": dict(sorted(Counter(str(row.get("source_id") or "") for row in rows).items())),
        "locator_type_counts": dict(sorted(Counter(str(row.get("channel_locator_type") or "") for row in rows).items())),
        "lane_success_counts": dict(sorted(Counter(str(row.get("primary_lane_id") or "") for row in rows).items())),
        "attempt_status_counts": dict(sorted(Counter(str(row.get("status") or "") for row in attempts).items())),
        "unmaterialized_tickers": sorted(required - success),
        "outputs": {"rows": str(output_rows), "attempts": str(output_attempts), "report": str(output_report)},
        "boundary": (
            "Rows are official or issuer-linked public channel/distributor/store locator context only. They cannot prove "
            "price, ASP, inventory, sell-through, revenue, sales volume, demand, or market share."
        ),
    }


def render_report(summary: Mapping[str, Any]) -> str:
    return "\n".join(
        [
            "# Family Channel / Distributor Context Rows",
            "",
            f"- Generated at: `{summary.get('generated_at')}`",
            f"- Status: `{summary.get('status')}`",
            f"- Target tickers: `{summary.get('target_ticker_count')}`",
            f"- Success tickers: `{summary.get('new_or_existing_success_ticker_count')}`",
            f"- Rows: `{summary.get('row_count')}`",
            f"- Locator types: `{json.dumps(summary.get('locator_type_counts'), ensure_ascii=False, sort_keys=True)}`",
            f"- Attempt statuses: `{json.dumps(summary.get('attempt_status_counts'), ensure_ascii=False, sort_keys=True)}`",
            f"- Unmaterialized tickers: `{json.dumps(summary.get('unmaterialized_tickers'), ensure_ascii=False)}`",
            "",
            "## Boundary",
            "",
            str(summary.get("boundary") or ""),
            "",
        ]
    )


def _fetch_url(url: str, timeout_s: float) -> tuple[int, str, str]:
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) FIN-Insight-Agent/0.1 channel-distributor-source-backfill",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "close",
        },
    )
    try:
        with urlopen(request, timeout=float(timeout_s or 12.0)) as response:  # noqa: S310
            body = response.read().decode("utf-8", errors="replace")
            return int(getattr(response, "status", 200) or 200), str(response.headers.get("Content-Type") or ""), body
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        return int(exc.code or 0), str(exc.headers.get("Content-Type") if exc.headers else ""), body
    except URLError:
        raise


def _fetch_url_with_browser(url: str, timeout_s: float) -> tuple[int, str, str]:
    import asyncio

    return asyncio.run(_fetch_url_with_browser_async(url, timeout_s))


async def _fetch_url_with_browser_async(url: str, timeout_s: float) -> tuple[int, str, str]:
    from playwright.async_api import async_playwright

    executable_path = _browser_executable_path()
    timeout_ms = int(max(5.0, float(timeout_s or 12.0)) * 1000)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True, executable_path=executable_path or None)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
            ),
            locale="en-US",
        )
        page = await context.new_page()
        try:
            response = await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            await page.wait_for_timeout(min(3000, max(1000, timeout_ms // 5)))
            body = await page.content()
            return int(response.status if response else 0), "text/html; rendered=playwright", body
        finally:
            await context.close()
            await browser.close()


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


def _attempt(ticker: str, url: str, status: str, reason: str, *, generated_at: str, **extra: Any) -> dict[str, Any]:
    row = {
        "schema_version": ATTEMPT_SCHEMA_VERSION,
        "generated_at": generated_at,
        "attempt_id": f"channel_distributor_attempt:{_stable_digest('|'.join([ticker, url, status, reason]))}",
        "ticker": ticker,
        "source_id": SOURCE_ID,
        "underlying_source_id": SOURCE_ID,
        "provider": "official_channel_distributor_locator",
        "url": url,
        "status": status,
        "reason": reason,
    }
    row.update(extra)
    return row


def _row_url(row: Mapping[str, Any]) -> str:
    return str(row.get("source_url") or row.get("url") or _first_present(row, ("citation", "url")) or "").strip()


def _official_domains(domain_cache: Mapping[str, Any], ticker: str) -> list[str]:
    if ticker in DOMAIN_OVERRIDES:
        return _unique_strings(DOMAIN_OVERRIDES[ticker])
    payload = domain_cache.get(ticker) if isinstance(domain_cache, Mapping) else {}
    domains = payload.get("domains") if isinstance(payload, Mapping) else []
    return _unique_strings(_hostish(domain) for domain in domains)


def _url_matches_domains(url: str, domains: list[str]) -> bool:
    host = _hostish(urlparse(url).netloc)
    return bool(host and any(host == domain or host.endswith(f".{domain}") for domain in domains))


def _url_matches_trusted_distributor(url: str) -> bool:
    host = _hostish(urlparse(url).netloc)
    return bool(host and any(host == domain or host.endswith(f".{domain}") for domain in TRUSTED_DISTRIBUTOR_DOMAINS))


def _trusted_distributor_seed_binds_target(target: Mapping[str, Any], *, url: str, page_title: str, clean_body: str) -> bool:
    company_name = str(target.get("company_name") or target.get("ticker") or "")
    haystack = f"{page_title} {clean_body[:20000]}".lower()
    aliases = _issuer_aliases(company_name, str(target.get("ticker") or ""))
    return any(alias in haystack for alias in aliases)


def _trusted_distributor_seed_has_channel_context(clean_body: str) -> bool:
    return bool(re.search(r"authorized\s+distributor|distributor|stock(?:ing|s)?|product\s+categories|manufacturer", clean_body, re.I))


def _issuer_aliases(company_name: str, ticker: str) -> list[str]:
    base = _unique_strings(
        [
            company_name,
            re.sub(r"\b(incorporated|inc|corp|corporation|company|co|ltd|limited|plc|holdings?|/del/)\b", " ", company_name, flags=re.I),
            ticker,
        ]
    )
    aliases: list[str] = []
    for value in base:
        normalized = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
        if len(normalized) >= 3:
            aliases.append(normalized)
            aliases.append(normalized.replace(" ", "-"))
    return _unique_strings(aliases)


def _normalize_url(url: str) -> str:
    text = html.unescape(str(url or "").strip())
    if not text:
        return ""
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return text.split("#", 1)[0]


def _hostish(value: str) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"^https?://", "", text).split("/", 1)[0]
    return text[4:] if text.startswith("www.") else text


def _locator_kind_from_text(value: str) -> str:
    text = str(value or "").lower()
    if re.search(r"dealer", text):
        return "dealer_locator"
    if re.search(r"partner", text):
        return "partner_locator"
    if re.search(r"sales\s+office|contact\s+sales|sales\s+inquir(?:y|ies)|sales@", text):
        return "sales_office_locator"
    if re.search(r"distributor|where\s+to\s+buy|authorized", text):
        return "distributor_locator"
    if re.search(r"store|locations?|spaces?|retail\s+centers?|service\s+centers?", text):
        return "store_locator"
    if re.search(r"shop|buy\s+online|buy\s+now", text):
        return "official_store_or_shop"
    if LOCATOR_PATH_RE.search(text):
        return "official_channel_link"
    return ""


def _channel_name(locator_kind: str) -> str:
    return {
        "dealer_locator": "official dealer locator",
        "distributor_locator": "official distributor locator",
        "partner_locator": "official partner locator",
        "store_locator": "official store locator",
        "official_store_or_shop": "official store/shop",
        "sales_office_locator": "official sales office locator",
        "official_channel_link": "official channel locator",
    }.get(locator_kind, "official channel locator")


def _looks_blocked(body: str) -> bool:
    text = re.sub(r"\s+", " ", str(body or "")[:4000]).lower()
    return any(
        token in text
        for token in (
            "access denied",
            "robot check",
            "verify you are human",
            "just a moment",
            "temporarily blocked",
            "client challenge",
            "our apologies",
            "page not found",
            "404 error",
            "requiring captcha",
            "requires captcha",
            "please make sure you are authorized",
            "308 permanent redirect",
            "permanent redirect",
        )
    )


def _reader_proxy_url(url: str) -> str:
    return f"https://r.jina.ai/http://r.jina.ai/http://{url}"


def _body_has_locator_context(body: str) -> bool:
    clean = _clean_html(str(body or "")[:200000])
    return bool(LOCATOR_LINK_RE.search(clean) or LOCATOR_PATH_RE.search(clean))


def _usable_cached_body(raw_path: Path) -> str:
    if not raw_path.exists():
        return ""
    try:
        body = raw_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    if not str(body or "").strip() or _looks_blocked(body) or not _body_has_locator_context(body):
        return ""
    return body


def _html_title(body: str) -> str:
    match = re.search(r"(?is)<title[^>]*>(.*?)</title>", body or "")
    return _clean_html(match.group(1)) if match else ""


def _clean_html(value: str) -> str:
    text = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", value or "")
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _row_rank(row: Mapping[str, Any]) -> tuple[int, int, str]:
    kind = str(row.get("channel_locator_type") or "")
    priority = {
        "distributor_locator": 5,
        "dealer_locator": 5,
        "partner_locator": 5,
        "official_store_or_shop": 4,
        "store_locator": 3,
        "sales_office_locator": 2,
        "official_channel_link": 1,
    }.get(kind, 0)
    return (priority, -len(str(row.get("source_url") or "")), str(row.get("source_url") or ""))


def _dedupe_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        key = str(row.get("evidence_ref") or "")
        if not key:
            key = "|".join(str(row.get(field) or "") for field in ("ticker", "source_url", "channel_locator_type"))
        if key in seen:
            continue
        seen.add(key)
        out.append(dict(row))
    return out


def _output_row_usable(row: Mapping[str, Any]) -> bool:
    text = " ".join(
        str(row.get(key) or "")
        for key in ("source_url", "fact_label", "channel_link_text", "citation")
    ).lower()
    return "404 error" not in text and "access denied" not in text


def _dedupe_attempts(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        key = str(row.get("attempt_id") or "")
        if not key:
            key = "|".join(str(row.get(field) or "") for field in ("ticker", "url", "status", "reason"))
        if key in seen:
            continue
        seen.add(key)
        out.append(dict(row))
    return out


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


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return dict(value) if isinstance(value, Mapping) else {}


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _unique_strings(values: Iterable[Any]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        text = str(value or "").strip()
        key = text.lower()
        if not text or key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def _first_present(row: Mapping[str, Any], *keys: Any) -> Any:
    for key in keys:
        if isinstance(key, tuple):
            current: Any = row
            for part in key:
                if not isinstance(current, Mapping) or part not in current:
                    current = None
                    break
                current = current.get(part)
            if current not in (None, ""):
                return current
        elif row.get(key) not in (None, ""):
            return row.get(key)
    return None


def _stable_digest(text: str) -> str:
    return hashlib.sha1(str(text or "").encode("utf-8", errors="ignore")).hexdigest()[:16]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
