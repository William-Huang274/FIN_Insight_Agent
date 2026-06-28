from __future__ import annotations

import argparse
import html
import json
import re
import ssl
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin, urlparse
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parents[2]

SOURCE_ID = "developer_ecosystem_github_npm_pypi_huggingface"
SCHEMA_VERSION = "finsight_developer_official_seed_locator_v0_1"
SUMMARY_SCHEMA_VERSION = "finsight_developer_official_seed_locator_summary_v0_1"

DEFAULT_DOCKET_PATH = REPO_ROOT / "data" / "manifests" / "company_gap_docket_v0_1.jsonl"
DEFAULT_COMPANY_SOURCE_MATRIX = REPO_ROOT / "data" / "manifests" / "company_public_source_coverage_matrix_v0_1.jsonl"
DEFAULT_DOMAIN_CACHE = REPO_ROOT / "data" / "manifests" / "company_domain_locator_cache_v0_1.json"
DEFAULT_FAMILY_ASSIGNMENTS = REPO_ROOT / "data" / "manifests" / "company_product_family_assignments_v0_1.jsonl"
DEFAULT_OFFICIAL_SURFACE_ROWS = REPO_ROOT / "data" / "manifests" / "official_product_surface_context_rows_v0_1.jsonl"
DEFAULT_EXISTING_SEEDS = REPO_ROOT / "data" / "manifests" / "developer_ecosystem_official_seed_registry_v0_1.jsonl"
DEFAULT_OUTPUT_SEEDS = REPO_ROOT / "data" / "manifests" / "developer_ecosystem_official_seed_locator_v0_1.jsonl"
DEFAULT_OUTPUT_ATTEMPTS = REPO_ROOT / "data" / "manifests" / "developer_ecosystem_official_seed_locator_attempts_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY = REPO_ROOT / "data" / "manifests" / "developer_ecosystem_official_seed_locator_summary_v0_1.json"
DEFAULT_OUTPUT_REPORT = REPO_ROOT / "docs" / "internal" / "vnext_20260610" / "vertical_lanes" / "developer_official_seed_locator.zh-CN.md"
DEFAULT_RAW_DIR = Path("Z:/FIN_Insight_Agent_data/raw_private/public_source_extended_materialization/developer_official_seed_locator")

REQUIREMENT_ID = "developer_ecosystem_proxy"

FetchFunc = Callable[[str, float], tuple[int, str, str]]

COMMON_DEV_PATHS = (
    "",
    "/developers",
    "/developer",
    "/docs",
    "/documentation",
    "/support/developer",
    "/support/documentation",
    "/open-source",
    "/opensource",
    "/software",
    "/resources/developer",
    "/api",
    "/apis",
    "/sdk",
    "/github",
)
COMMON_DEV_SUBDOMAINS = ("developer", "developers", "docs")

NOISE_GITHUB_OWNERS = {
    "afarkas",
    "ampproject",
    "bootstrap",
    "cloudflare",
    "facebook",
    "fontawesome",
    "google",
    "jquery",
    "newrelic",
    "nrwl",
    "twbs",
    "vercel",
    "webpack",
}
GITHUB_NON_REPO_OWNERS = {
    "about",
    "apps",
    "collections",
    "customer-stories",
    "enterprise",
    "events",
    "features",
    "marketplace",
    "orgs",
    "pricing",
    "readme",
    "search",
    "security",
    "settings",
    "solutions",
    "sponsors",
    "topics",
}
NOISE_REPO_NAMES = {
    "lazysizes",
    "newrelic-browser-agent",
}

MANUAL_ALIASES: dict[str, tuple[str, ...]] = {
    "6723.T": ("renesas",),
    "CDNS": ("cadence",),
    "CRDO": ("credo", "credosemi"),
    "DIOD": ("diodes", "diodesinc"),
    "FICO": ("fico", "fairisaac"),
    "FTNT": ("fortinet",),
    "GEN": ("gendigital", "nortonlifelock", "norton"),
    "KEYS": ("keysight",),
    "MTSI": ("macom",),
    "ON": ("onsemi",),
    "PTC": ("ptc", "thingworx"),
    "RMBS": ("rambus",),
    "S": ("sentinelone", "sentinel-one"),
    "TOST": ("toast", "toasttab"),
    "VRSN": ("verisign",),
    "WOLF": ("wolfspeed",),
}

MANUAL_GITHUB_ORG_CANDIDATES: dict[str, tuple[str, ...]] = {
    "6723.T": ("renesas",),
    "CDNS": ("cadence", "CadenceDesignSystems"),
    "CRDO": ("credosemi",),
    "FICO": ("fico", "fico-xpress"),
    "FTNT": ("fortinet", "fortinet-solutions-cse"),
    "GEN": ("GenDigital", "NortonLifeLock"),
    "KEYS": ("Keysight", "keysight"),
    "MSI": ("motorolasolutions", "MotorolaSolutions"),
    "ON": ("onsemi",),
    "PTC": ("ptc-iot-sharing", "PTCInc"),
    "RMBS": ("rambus", "Rambus"),
    "S": ("Sentinel-One", "sentinelone"),
    "TOST": ("toasttab", "ToastInc"),
    "VRSN": ("verisign",),
    "WOLF": ("wolfspeed",),
}

EXTRA_ALLOWED_PROFILE_DOMAINS: dict[str, tuple[str, ...]] = {
    "FICO": ("fico.com",),
    "GEN": ("nortonlifelock.com", "norton.com", "avast.com", "avg.com"),
    "TOST": ("toasttab.com",),
}

REPO_NAME_HINTS = (
    "sdk",
    "api",
    "apis",
    "driver",
    "python",
    "java",
    "javascript",
    "js",
    "cli",
    "samples",
    "examples",
    "tool",
    "tools",
    "plugin",
    "plugins",
    "client",
    "library",
    "libraries",
    "open",
    "oss",
    "software",
    "dev",
    "docs",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Locate official developer repo/package/model seeds from issuer-bound sources.")
    parser.add_argument("--tickers", nargs="*", default=[])
    parser.add_argument("--docket-path", type=Path, default=DEFAULT_DOCKET_PATH)
    parser.add_argument("--company-source-matrix", type=Path, default=DEFAULT_COMPANY_SOURCE_MATRIX)
    parser.add_argument("--domain-cache", type=Path, default=DEFAULT_DOMAIN_CACHE)
    parser.add_argument("--family-assignments", type=Path, default=DEFAULT_FAMILY_ASSIGNMENTS)
    parser.add_argument("--official-surface-rows", type=Path, default=DEFAULT_OFFICIAL_SURFACE_ROWS)
    parser.add_argument("--existing-seeds", type=Path, default=DEFAULT_EXISTING_SEEDS)
    parser.add_argument("--output-seeds", type=Path, default=DEFAULT_OUTPUT_SEEDS)
    parser.add_argument("--output-attempts", type=Path, default=DEFAULT_OUTPUT_ATTEMPTS)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--output-report", type=Path, default=DEFAULT_OUTPUT_REPORT)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--timeout-s", type=float, default=7.0)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--max-source-pages-per-ticker", type=int, default=20)
    parser.add_argument("--max-seeds-per-ticker", type=int, default=3)
    parser.add_argument("--max-repos-per-org", type=int, default=12)
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at = _utc_now()
    targets = build_targets(
        docket_rows=_load_jsonl(args.docket_path),
        company_source_matrix_rows=_load_jsonl(args.company_source_matrix),
        domain_cache=_load_json(args.domain_cache),
        family_assignment_rows=_load_jsonl(args.family_assignments),
        existing_seed_rows=_load_jsonl(args.existing_seeds),
        tickers=args.tickers,
    )
    seeds, attempts = locate_developer_official_seeds(
        targets=targets,
        official_surface_rows=_load_jsonl(args.official_surface_rows),
        raw_dir=args.raw_dir,
        generated_at=generated_at,
        timeout_s=args.timeout_s,
        workers=args.workers,
        max_source_pages_per_ticker=args.max_source_pages_per_ticker,
        max_seeds_per_ticker=args.max_seeds_per_ticker,
        max_repos_per_org=args.max_repos_per_org,
    )
    summary = build_summary(
        targets=targets,
        seeds=seeds,
        attempts=attempts,
        generated_at=generated_at,
        output_seeds=args.output_seeds,
        output_attempts=args.output_attempts,
        output_report=args.output_report,
    )
    _write_jsonl(args.output_seeds, seeds)
    _write_jsonl(args.output_attempts, attempts)
    _write_json(args.output_summary, summary)
    args.output_report.parent.mkdir(parents=True, exist_ok=True)
    args.output_report.write_text(render_report(summary), encoding="utf-8", newline="\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if args.strict and summary["unclassified_target_count"] > 0:
        return 1
    return 0


def build_targets(
    *,
    docket_rows: Iterable[Mapping[str, Any]],
    company_source_matrix_rows: Iterable[Mapping[str, Any]],
    domain_cache: Mapping[str, Any],
    family_assignment_rows: Iterable[Mapping[str, Any]],
    existing_seed_rows: Iterable[Mapping[str, Any]],
    tickers: Iterable[str] = (),
) -> list[dict[str, Any]]:
    ticker_filter = {str(ticker).strip().upper() for ticker in tickers if str(ticker).strip()}
    family_by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in family_assignment_rows:
        ticker = str(row.get("ticker") or "").strip().upper()
        if ticker:
            family_by_ticker[ticker].append(dict(row))
    existing_seed_tickers = {str(row.get("ticker") or "").strip().upper() for row in existing_seed_rows if row.get("ticker")}

    targets: dict[str, dict[str, Any]] = {}
    for row in docket_rows:
        if str(row.get("requirement_id") or "") != REQUIREMENT_ID:
            continue
        ticker = str(row.get("ticker") or "").strip().upper()
        if not ticker or (ticker_filter and ticker not in ticker_filter):
            continue
        targets[ticker] = _target_from_row(row, domain_cache=domain_cache, family_rows=family_by_ticker.get(ticker) or [], existing_seed_tickers=existing_seed_tickers)

    for company in company_source_matrix_rows:
        ticker = str(company.get("ticker") or "").strip().upper()
        if not ticker or ticker in targets or (ticker_filter and ticker not in ticker_filter):
            continue
        requirements = {
            str(req.get("requirement_id") or "")
            for req in company.get("source_role_matrix") or []
            if isinstance(req, Mapping) and str(req.get("status") or "") == "gap"
        }
        if REQUIREMENT_ID not in requirements:
            continue
        targets[ticker] = _target_from_row(company, domain_cache=domain_cache, family_rows=family_by_ticker.get(ticker) or [], existing_seed_tickers=existing_seed_tickers)

    return sorted(targets.values(), key=lambda row: row["ticker"])


def _target_from_row(
    row: Mapping[str, Any],
    *,
    domain_cache: Mapping[str, Any],
    family_rows: list[Mapping[str, Any]],
    existing_seed_tickers: set[str],
) -> dict[str, Any]:
    ticker = str(row.get("ticker") or "").strip().upper()
    cached = domain_cache.get(ticker) if isinstance(domain_cache, Mapping) else {}
    domains = _unique_strings([*(cached.get("domains") or []), *(EXTRA_ALLOWED_PROFILE_DOMAINS.get(ticker) or [])])
    company_name = str(row.get("company_name") or (cached.get("company_name") if isinstance(cached, Mapping) else "") or ticker).strip()
    family_names = _unique_strings(row.get("family_names") or [family.get("family_name") for family in family_rows])
    aliases = _company_aliases(ticker=ticker, company_name=company_name, domains=domains, family_names=family_names)
    return {
        "ticker": ticker,
        "company_name": company_name,
        "company_names": _unique_strings([company_name, *aliases]),
        "domains": domains,
        "family_names": family_names,
        "family_ids": _unique_strings(row.get("family_ids") or [family.get("family_id") for family in family_rows]),
        "aliases": aliases,
        "has_existing_seed": ticker in existing_seed_tickers,
    }


def locate_developer_official_seeds(
    *,
    targets: list[Mapping[str, Any]],
    official_surface_rows: Iterable[Mapping[str, Any]],
    raw_dir: Path,
    generated_at: str,
    timeout_s: float = 7.0,
    workers: int = 16,
    max_source_pages_per_ticker: int = 20,
    max_seeds_per_ticker: int = 3,
    max_repos_per_org: int = 12,
    fetch: FetchFunc | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    fetcher = fetch or _fetch_url
    surface_urls_by_ticker: dict[str, list[str]] = defaultdict(list)
    for row in official_surface_rows:
        ticker = str(row.get("ticker") or "").strip().upper()
        url = str(row.get("source_url") or row.get("url") or "").strip()
        if ticker and url:
            surface_urls_by_ticker[ticker].append(url)

    seeds_by_ticker: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    attempts: list[dict[str, Any]] = []

    page_jobs: list[tuple[Mapping[str, Any], str]] = []
    for target in targets:
        ticker = str(target.get("ticker") or "").upper()
        for url in build_source_page_urls(target, surface_urls=surface_urls_by_ticker.get(ticker) or [], max_pages=max_source_pages_per_ticker):
            page_jobs.append((target, url))

    with ThreadPoolExecutor(max_workers=max(1, int(workers or 1))) as executor:
        future_map = {executor.submit(fetcher, url, timeout_s): (target, url) for target, url in page_jobs}
        for future in as_completed(future_map):
            target, url = future_map[future]
            ticker = str(target.get("ticker") or "").upper()
            try:
                status_code, content_type, body = future.result()
            except Exception as exc:  # noqa: BLE001
                attempts.append(_attempt(ticker, "official_page_probe", url, "fetch_failed", reason=f"{type(exc).__name__}: {str(exc)[:180]}"))
                continue
            raw_path = ""
            if body and 200 <= status_code < 400 and _looks_html(content_type, body):
                raw_path = str(_write_raw(raw_dir, ticker, "official_page", url, body))
                for seed_url in extract_seed_urls_from_official_page(target=target, source_url=url, body=body):
                    seed = _seed_record(
                        target,
                        urls=[seed_url],
                        source_urls=[url],
                        seed_discovery_method="official_domain_page_link",
                        generated_at=generated_at,
                    )
                    seeds_by_ticker[ticker][_seed_key(seed)] = seed
            attempts.append(
                _attempt(
                    ticker,
                    "official_page_probe",
                    url,
                    "source_page_scanned" if raw_path else "source_page_unusable",
                    status_code=status_code,
                    content_type=content_type,
                    raw_path=raw_path,
                )
            )

    for target in targets:
        ticker = str(target.get("ticker") or "").upper()
        if len(seeds_by_ticker[ticker]) >= max_seeds_per_ticker:
            continue
        for org in github_org_candidates(target):
            profile = fetch_github_profile(org, target=target, fetch=fetcher, timeout_s=timeout_s)
            attempts.append(profile["attempt"])
            if not profile.get("verified"):
                continue
            repo_result = fetch_github_repo_urls(
                org,
                target=target,
                fetch=fetcher,
                timeout_s=timeout_s,
                max_repos=max_repos_per_org,
            )
            attempts.extend(repo_result["attempts"])
            urls = repo_result["urls"][: max(0, max_seeds_per_ticker - len(seeds_by_ticker[ticker]))]
            if not urls:
                continue
            seed = _seed_record(
                target,
                urls=urls,
                source_urls=[profile.get("profile_url") or f"https://github.com/{org}"],
                seed_discovery_method="github_org_profile_verified_official_domain",
                generated_at=generated_at,
                github_org=org,
                issuer_binding_evidence=profile.get("issuer_binding_evidence") or "",
            )
            seeds_by_ticker[ticker][_seed_key(seed)] = seed
            if len(seeds_by_ticker[ticker]) >= max_seeds_per_ticker:
                break
        if not seeds_by_ticker[ticker]:
            attempts.append(
                _attempt(
                    ticker,
                    "developer_official_seed_locator",
                    "",
                    "no_verified_official_seed",
                    reason="official_pages_and_verified_github_org_profiles_found_no_supported_repo_package_model_seed",
                )
            )

    seeds = []
    for ticker in sorted(seeds_by_ticker):
        ticker_seeds = list(seeds_by_ticker[ticker].values())
        if not ticker_seeds:
            continue
        merged_urls = _unique_strings(url for seed in ticker_seeds for url in seed.get("urls") or [])
        merged_source_urls = _unique_strings(url for seed in ticker_seeds for url in seed.get("source_urls") or [])
        first = dict(ticker_seeds[0])
        first["urls"] = merged_urls[:max_seeds_per_ticker]
        first["source_urls"] = merged_source_urls
        first["seed_discovery_methods"] = _unique_strings(seed.get("seed_discovery_method") for seed in ticker_seeds)
        first["product_terms"] = _unique_strings([*(first.get("product_terms") or []), *[_seed_product_term(url) for url in first["urls"]]])
        seeds.append(first)
    return seeds, attempts


def build_source_page_urls(target: Mapping[str, Any], *, surface_urls: list[str], max_pages: int) -> list[str]:
    urls: list[str] = [*surface_urls]
    for domain in target.get("domains") or []:
        clean = str(domain or "").strip().strip("/")
        if not clean:
            continue
        base = f"https://{clean}"
        urls.extend([base + path for path in COMMON_DEV_PATHS])
        urls.extend([f"https://{sub}.{clean}/" for sub in COMMON_DEV_SUBDOMAINS])
    return _unique_strings(urls)[:max_pages]


def extract_seed_urls_from_official_page(*, target: Mapping[str, Any], source_url: str, body: str) -> list[str]:
    if not _source_url_is_official(source_url, target.get("domains") or []):
        return []
    aliases = set(_normal_terms(target.get("aliases") or []))
    family_terms = set(_normal_terms(target.get("family_names") or []))
    candidates: list[str] = []
    for raw_url, context in _extract_supported_links_with_context(body, base_url=source_url):
        seed_url = normalize_supported_seed_url(raw_url)
        if not seed_url:
            continue
        if _seed_is_noise(seed_url):
            continue
        norm_seed = _normalize_text(seed_url)
        norm_context = _normalize_text(context)
        if aliases and any(alias in norm_seed or alias in norm_context for alias in aliases):
            candidates.append(seed_url)
            continue
        if any(term in norm_context for term in family_terms) and _developer_context_present(norm_context):
            candidates.append(seed_url)
            continue
        if _developer_context_present(norm_context) and not _third_party_frontend_noise(seed_url, norm_context):
            candidates.append(seed_url)
    return _unique_strings(candidates)


def github_org_candidates(target: Mapping[str, Any]) -> list[str]:
    ticker = str(target.get("ticker") or "").upper()
    candidates: list[str] = [*(MANUAL_GITHUB_ORG_CANDIDATES.get(ticker) or [])]
    for alias in target.get("aliases") or []:
        compact = re.sub(r"[^A-Za-z0-9-]", "", str(alias))
        if len(compact) >= 3:
            candidates.append(compact)
    for domain in target.get("domains") or []:
        stem = str(domain).split(".")[0]
        if len(stem) >= 3:
            candidates.append(stem)
    return _unique_strings(candidates)[:8]


def fetch_github_profile(
    org: str,
    *,
    target: Mapping[str, Any],
    fetch: FetchFunc,
    timeout_s: float,
) -> dict[str, Any]:
    profile_url = f"https://github.com/{quote(org, safe='')}"
    api_url = f"https://api.github.com/users/{quote(org, safe='')}"
    status_code = 0
    body = ""
    content_type = ""
    try:
        status_code, content_type, body = fetch(api_url, timeout_s)
    except Exception as exc:  # noqa: BLE001
        return {
            "verified": False,
            "profile_url": profile_url,
            "attempt": _attempt(str(target.get("ticker") or ""), "github_org_profile", api_url, "fetch_failed", reason=f"{type(exc).__name__}: {str(exc)[:180]}"),
        }
    profile: dict[str, Any] = {}
    if status_code < 400:
        try:
            profile = json.loads(body) if body.strip() else {}
        except json.JSONDecodeError:
            profile = {}
    verified, evidence = _verify_github_profile(profile, target=target, html_body="")
    status = "verified_github_profile" if verified else "github_profile_not_verified"
    reason = evidence or (f"http_{status_code}" if status_code >= 400 else "profile_lacks_official_domain_or_alias")
    if not verified:
        try:
            html_status, html_type, html_body = fetch(profile_url, timeout_s)
        except Exception:  # noqa: BLE001
            html_status, html_type, html_body = 0, "", ""
        if html_status < 400 and html_body:
            verified, evidence = _verify_github_profile({}, target=target, html_body=html_body)
            status = "verified_github_profile_html" if verified else "github_profile_html_not_verified"
            reason = evidence or f"api_http_{status_code}; html_http_{html_status}"
            status_code = html_status
            content_type = html_type
    return {
        "verified": verified,
        "profile_url": profile_url,
        "issuer_binding_evidence": evidence,
        "attempt": _attempt(
            str(target.get("ticker") or ""),
            "github_org_profile",
            profile_url,
            status,
            api_url=api_url,
            status_code=status_code,
            content_type=content_type,
            reason=reason,
            github_org=org,
        ),
    }


def fetch_github_repo_urls(
    org: str,
    *,
    target: Mapping[str, Any],
    fetch: FetchFunc,
    timeout_s: float,
    max_repos: int,
) -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    urls: list[str] = []
    api_url = f"https://api.github.com/users/{quote(org, safe='')}/repos?per_page={max(1, min(50, max_repos))}&sort=updated"
    try:
        status_code, content_type, body = fetch(api_url, timeout_s)
    except Exception as exc:  # noqa: BLE001
        attempts.append(_attempt(str(target.get("ticker") or ""), "github_repo_list", api_url, "fetch_failed", reason=f"{type(exc).__name__}: {str(exc)[:180]}", github_org=org))
        status_code, content_type, body = 0, "", ""
    if status_code < 400 and body.strip():
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = []
        if isinstance(payload, list):
            for repo in payload:
                if not isinstance(repo, Mapping):
                    continue
                html_url = str(repo.get("html_url") or "").strip()
                if html_url and _repo_candidate_allowed(html_url, repo.get("name"), target):
                    urls.append(normalize_supported_seed_url(html_url))
    attempts.append(
        _attempt(
            str(target.get("ticker") or ""),
            "github_repo_list",
            api_url,
            "repo_urls_materialized" if urls else "repo_list_no_allowed_rows",
            status_code=status_code,
            content_type=content_type,
            github_org=org,
            parsed_seed_count=len(urls),
        )
    )
    if not urls:
        html_url = f"https://github.com/{quote(org, safe='')}?tab=repositories"
        try:
            html_status, html_type, html_body = fetch(html_url, timeout_s)
        except Exception as exc:  # noqa: BLE001
            attempts.append(_attempt(str(target.get("ticker") or ""), "github_repo_list_html", html_url, "fetch_failed", reason=f"{type(exc).__name__}: {str(exc)[:180]}", github_org=org))
        else:
            if html_status < 400:
                for url, _context in _extract_supported_links_with_context(html_body, base_url=html_url):
                    seed_url = normalize_supported_seed_url(url)
                    if seed_url and _repo_candidate_allowed(seed_url, "", target):
                        urls.append(seed_url)
            attempts.append(
                _attempt(
                    str(target.get("ticker") or ""),
                    "github_repo_list_html",
                    html_url,
                    "repo_urls_materialized" if urls else "repo_list_no_allowed_rows",
                    status_code=html_status,
                    content_type=html_type,
                    github_org=org,
                    parsed_seed_count=len(urls),
                )
            )
    return {"urls": _unique_strings(urls)[:max_repos], "attempts": attempts}


def normalize_supported_seed_url(url: str) -> str:
    text = html.unescape(str(url or "").strip()).strip('"\'<>).,;')
    if not text:
        return ""
    parsed = urlparse(text)
    netloc = parsed.netloc.lower()
    path_parts = [part for part in parsed.path.strip("/").split("/") if part]
    if netloc == "github.com" and len(path_parts) >= 2:
        if path_parts[0].lower() in GITHUB_NON_REPO_OWNERS:
            return ""
        if path_parts[2:3] and path_parts[2].lower() in {"blob", "tree", "issues", "pull", "pulls", "releases", "actions", "wiki", "stargazers", "forks"}:
            return ""
        return f"https://github.com/{path_parts[0]}/{path_parts[1].removesuffix('.git')}"
    if netloc == "www.npmjs.com" and len(path_parts) >= 2 and path_parts[0] == "package":
        package = "/".join(path_parts[1:3]) if path_parts[1].startswith("@") and len(path_parts) >= 3 else path_parts[1]
        return f"https://www.npmjs.com/package/{package}"
    if netloc == "pypi.org" and len(path_parts) >= 2 and path_parts[0] == "project":
        return f"https://pypi.org/project/{path_parts[1]}/"
    if netloc == "huggingface.co" and len(path_parts) >= 2:
        return f"https://huggingface.co/{path_parts[0]}/{path_parts[1]}"
    return ""


def build_summary(
    *,
    targets: list[Mapping[str, Any]],
    seeds: list[Mapping[str, Any]],
    attempts: list[Mapping[str, Any]],
    generated_at: str,
    output_seeds: Path,
    output_attempts: Path,
    output_report: Path,
) -> dict[str, Any]:
    seeded_tickers = {str(seed.get("ticker") or "") for seed in seeds if seed.get("ticker")}
    target_tickers = {str(target.get("ticker") or "") for target in targets if target.get("ticker")}
    unseeded = sorted(target_tickers - seeded_tickers)
    terminal_statuses = {"no_verified_official_seed"}
    terminal_unseeded = {
        str(attempt.get("ticker") or "")
        for attempt in attempts
        if attempt.get("status") in terminal_statuses and attempt.get("ticker")
    }
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "pass" if len(terminal_unseeded | seeded_tickers) >= len(target_tickers) else "gap",
        "target_ticker_count": len(target_tickers),
        "seeded_ticker_count": len(seeded_tickers),
        "seed_row_count": len(seeds),
        "seed_url_count": sum(len(seed.get("urls") or []) for seed in seeds),
        "unseeded_ticker_count": len(unseeded),
        "unseeded_tickers": unseeded,
        "attempt_count": len(attempts),
        "attempt_status_counts": dict(sorted(Counter(str(attempt.get("status") or "") for attempt in attempts).items())),
        "seed_discovery_method_counts": dict(sorted(Counter(method for seed in seeds for method in (seed.get("seed_discovery_methods") or [seed.get("seed_discovery_method") or ""])).items())),
        "unclassified_target_count": len(target_tickers - seeded_tickers - terminal_unseeded),
        "unclassified_tickers": sorted(target_tickers - seeded_tickers - terminal_unseeded),
        "outputs": {"seeds": str(output_seeds), "attempts": str(output_attempts), "report": str(output_report)},
        "boundary": (
            "Located seeds are issuer-bound developer repository/package/model entry points discovered from official-domain pages "
            "or GitHub organization profiles that expose an official company domain. They are not evidence rows until the developer "
            "ecosystem parser materializes bounded L3 context rows."
        ),
    }


def render_report(summary: Mapping[str, Any]) -> str:
    lines = [
        "# Developer Official Seed Locator",
        "",
        f"- generated_at: `{summary.get('generated_at')}`",
        f"- status: `{summary.get('status')}`",
        f"- target_ticker_count: `{summary.get('target_ticker_count')}`",
        f"- seeded_ticker_count: `{summary.get('seeded_ticker_count')}`",
        f"- seed_url_count: `{summary.get('seed_url_count')}`",
        f"- unseeded_ticker_count: `{summary.get('unseeded_ticker_count')}`",
        "",
        "## Boundary",
        "",
        str(summary.get("boundary") or ""),
        "",
        "## Attempt Status",
        "",
        "| status | count |",
        "| --- | ---: |",
    ]
    for status, count in (summary.get("attempt_status_counts") or {}).items():
        lines.append(f"| `{status}` | {count} |")
    lines.extend(["", "## Unseeded Tickers", ""])
    lines.append(", ".join(f"`{ticker}`" for ticker in summary.get("unseeded_tickers") or []) or "None")
    lines.append("")
    return "\n".join(lines)


def _verify_github_profile(profile: Mapping[str, Any], *, target: Mapping[str, Any], html_body: str) -> tuple[bool, str]:
    domains = _official_domains(target)
    aliases = set(_normal_terms(target.get("aliases") or []))
    if profile:
        profile_text = _normalize_text(" ".join(str(profile.get(key) or "") for key in ("login", "name", "company", "blog", "html_url", "description", "bio")))
        blog = str(profile.get("blog") or "")
        if _url_matches_domains(blog, domains):
            return True, f"github_profile_blog_matches_official_domain:{blog}"
    if html_body:
        text = _normalize_text(html.unescape(re.sub(r"<[^>]+>", " ", html_body)))
        if any(domain in html_body.lower() for domain in domains) and any(alias in text for alias in aliases):
            return True, "github_profile_html_links_official_domain_and_alias"
    return False, ""


def _repo_candidate_allowed(url: str, name: Any, target: Mapping[str, Any]) -> bool:
    seed_url = normalize_supported_seed_url(url)
    if not seed_url or _seed_is_noise(seed_url):
        return False
    parsed = urlparse(seed_url)
    parts = [part for part in parsed.path.strip("/").split("/") if part]
    repo_name = str(name or (parts[1] if len(parts) > 1 else "")).lower()
    if repo_name in {".github", "github", "docs.github.io"}:
        return False
    aliases = set(_normal_terms(target.get("aliases") or []))
    norm = _normalize_text(seed_url + " " + repo_name)
    if any(alias in norm for alias in aliases):
        return True
    if any(hint in repo_name for hint in REPO_NAME_HINTS):
        return True
    return False


def _seed_record(
    target: Mapping[str, Any],
    *,
    urls: list[str],
    source_urls: list[str],
    seed_discovery_method: str,
    generated_at: str,
    github_org: str = "",
    issuer_binding_evidence: str = "",
) -> dict[str, Any]:
    ticker = str(target.get("ticker") or "").upper()
    product_terms = _unique_strings([
        *(target.get("family_names") or []),
        *[_seed_product_term(url) for url in urls],
    ])
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "ticker": ticker,
        "company_name": target.get("company_name") or ticker,
        "company_names": _unique_strings(target.get("company_names") or [target.get("company_name") or ticker]),
        "product_terms": product_terms,
        "urls": _unique_strings(urls),
        "source_urls": _unique_strings(source_urls),
        "seed_discovery_method": seed_discovery_method,
        "github_org": github_org,
        "issuer_binding_evidence": issuer_binding_evidence,
        "source_id": SOURCE_ID,
        "source_layer_id": "L3",
        "official_seed_verified": True,
        "claim_boundary": "Official developer seed only; parser output remains L3 directional proxy and cannot prove revenue, sales, share, customer adoption, or moat.",
    }


def _seed_key(seed: Mapping[str, Any]) -> str:
    return "|".join([str(seed.get("ticker") or ""), ",".join(seed.get("urls") or [])])


def _seed_product_term(url: str) -> str:
    parsed = urlparse(url)
    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if parsed.netloc.lower() == "github.com" and len(parts) >= 2:
        return f"{parts[0]}/{parts[1]}"
    if parsed.netloc.lower() == "www.npmjs.com" and len(parts) >= 2:
        return parts[-1] if not parts[1].startswith("@") else "/".join(parts[1:3])
    if parsed.netloc.lower() == "pypi.org" and len(parts) >= 2:
        return parts[1]
    if parsed.netloc.lower() == "huggingface.co" and len(parts) >= 2:
        return f"{parts[0]}/{parts[1]}"
    return url


def _extract_supported_links_with_context(body: str, *, base_url: str) -> list[tuple[str, str]]:
    links: list[tuple[str, str]] = []
    href_re = re.compile(r"(?is)<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>")
    for match in href_re.finditer(body):
        href = html.unescape(match.group(1)).strip()
        text = html.unescape(re.sub(r"(?is)<[^>]+>", " ", match.group(2)))
        absolute = urljoin(base_url, href)
        if _supported_url_like(absolute):
            start = max(0, match.start() - 240)
            end = min(len(body), match.end() + 240)
            links.append((absolute, text + " " + html.unescape(re.sub(r"(?is)<[^>]+>", " ", body[start:end]))))
    raw_re = re.compile(r"https?://(?:github\.com/[^\s\"'<>]+|www\.npmjs\.com/package/[^\s\"'<>]+|pypi\.org/project/[^\s\"'<>]+|huggingface\.co/[^\s\"'<>]+)")
    for match in raw_re.finditer(body):
        start = max(0, match.start() - 180)
        end = min(len(body), match.end() + 180)
        links.append((match.group(0), html.unescape(re.sub(r"(?is)<[^>]+>", " ", body[start:end]))))
    return links


def _supported_url_like(url: str) -> bool:
    parsed = urlparse(str(url or ""))
    netloc = parsed.netloc.lower()
    return netloc == "github.com" or netloc == "www.npmjs.com" or netloc == "pypi.org" or netloc == "huggingface.co"


def _source_url_is_official(url: str, domains: Iterable[str]) -> bool:
    return _url_matches_domains(url, _clean_domains(domains))


def _url_matches_domains(url: str, domains: Iterable[str]) -> bool:
    host = urlparse(str(url or "")).netloc.lower().removeprefix("www.")
    if not host:
        return False
    for domain in _clean_domains(domains):
        if host == domain or host.endswith("." + domain):
            return True
    return False


def _official_domains(target: Mapping[str, Any]) -> list[str]:
    return _clean_domains(target.get("domains") or [])


def _clean_domains(domains: Iterable[str]) -> list[str]:
    cleaned = []
    for domain in domains:
        text = str(domain or "").strip().lower().removeprefix("www.").strip("/")
        if text:
            cleaned.append(text)
    return _unique_strings(cleaned)


def _seed_is_noise(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.netloc.lower() != "github.com":
        return False
    parts = [part.lower() for part in parsed.path.strip("/").split("/") if part]
    if len(parts) < 2:
        return True
    return parts[0] in NOISE_GITHUB_OWNERS or parts[1] in NOISE_REPO_NAMES


def _third_party_frontend_noise(seed_url: str, context: str) -> bool:
    parsed = urlparse(seed_url)
    if parsed.netloc.lower() != "github.com":
        return False
    parts = [part.lower() for part in parsed.path.strip("/").split("/") if part]
    if len(parts) >= 2 and (parts[0] in NOISE_GITHUB_OWNERS or parts[1] in NOISE_REPO_NAMES):
        return True
    return "warning-codes" in seed_url.lower() or "lazysizes" in context


def _developer_context_present(text: str) -> bool:
    return any(term in text for term in ("developer", "developers", "github", "sdk", "api", "apis", "open source", "software", "docs", "documentation", "package"))


def _looks_html(content_type: str, body: str) -> bool:
    lower = str(content_type or "").lower()
    if "html" in lower:
        return True
    prefix = body[:512].lower()
    return "<html" in prefix or "<!doctype html" in prefix


def _company_aliases(*, ticker: str, company_name: str, domains: list[str], family_names: list[str]) -> list[str]:
    values = [ticker, company_name, *(MANUAL_ALIASES.get(ticker) or [])]
    values.extend(domain.split(".")[0] for domain in domains)
    for token in re.split(r"[^A-Za-z0-9]+", company_name):
        if len(token) >= 3:
            values.append(token)
    values.extend(family_names)
    return _unique_strings(_normal_terms(values))


def _normal_terms(values: Iterable[Any]) -> list[str]:
    terms: list[str] = []
    for value in values:
        text = _normalize_text(str(value or ""))
        if len(text) >= 3:
            terms.append(text)
    return _unique_strings(terms)


def _normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _fetch_url(url: str, timeout_s: float) -> tuple[int, str, str]:
    request = Request(
        url,
        headers={
            "User-Agent": "FIN-Insight-Agent/0.1 developer-official-seed-locator",
            "Accept": "text/html,application/json;q=0.9,*/*;q=0.5",
        },
    )
    context = ssl.create_default_context()
    try:
        with urlopen(request, timeout=float(timeout_s or 7.0), context=context) as response:  # noqa: S310
            body = response.read(1_000_000).decode("utf-8", errors="replace")
            return int(getattr(response, "status", 200) or 200), str(response.headers.get("Content-Type") or ""), body
    except HTTPError as exc:
        body = exc.read(500_000).decode("utf-8", errors="replace") if exc.fp else ""
        return int(exc.code or 0), str(exc.headers.get("Content-Type") if exc.headers else ""), body
    except URLError:
        raise


def _write_raw(raw_dir: Path, ticker: str, kind: str, url: str, body: str) -> Path:
    path = raw_dir / f"{ticker.lower()}_{kind}_{_slug(url)}.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8", newline="\n")
    return path


def _attempt(ticker: str, source_type: str, url: str, status: str, **extra: Any) -> dict[str, Any]:
    return {
        "ticker": str(ticker or "").upper(),
        "source_type": source_type,
        "url": url,
        "status": status,
        "source_id": SOURCE_ID,
        "underlying_source_id": SOURCE_ID,
        **{key: value for key, value in extra.items() if value not in (None, "")},
    }


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8", newline="\n")


def _unique_strings(values: Iterable[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _slug(value: str, *, limit: int = 90) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "_", str(value or "").lower()).strip("_")
    return (text[:limit] or "item").strip("_")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
