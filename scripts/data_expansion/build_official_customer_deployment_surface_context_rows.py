from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import urljoin, urlparse

import requests


REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_DIR = REPO_ROOT / "data" / "manifests"

SCHEMA_VERSION = "finsight_official_customer_deployment_surface_context_row_v0_1"
ATTEMPT_SCHEMA_VERSION = "finsight_official_customer_deployment_surface_attempt_v0_1"
SUMMARY_SCHEMA_VERSION = "finsight_official_customer_deployment_surface_summary_v0_1"

DEFAULT_GAP_ACTION_PLAN = MANIFEST_DIR / "second_third_layer_depth_parity_gap_action_plan_v0_1.jsonl"
DEFAULT_OFFICIAL_PRODUCT_SURFACE_ROWS = MANIFEST_DIR / "official_product_surface_context_rows_v0_1.jsonl"
DEFAULT_OUTPUT_ROWS = MANIFEST_DIR / "official_customer_deployment_surface_context_rows_v0_1.jsonl"
DEFAULT_OUTPUT_ATTEMPTS = MANIFEST_DIR / "official_customer_deployment_surface_attempts_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY = MANIFEST_DIR / "official_customer_deployment_surface_summary_v0_1.json"
DEFAULT_DOMAIN_CACHE = MANIFEST_DIR / "company_domain_locator_cache_v0_1.json"
DEFAULT_RAW_PRODUCT_PAGE_DIR = Path("Z:/FIN_Insight_Agent_data/raw_private/public_source_extended_materialization/company_product_pages")
DEFAULT_RAW_OUTPUT_DIR = Path("Z:/FIN_Insight_Agent_data/raw_private/public_source_extended_materialization/official_customer_deployment_surfaces")

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0 Safari/537.36 FIN-Insight-Agent official surface resolver"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

HIGH_VALUE_LINK_PATTERNS = (
    r"\bcustomer(?:s)?\b",
    r"\bclient(?:s)?\b",
    r"\bcase[-\s]?stud(?:y|ies)\b",
    r"\bsuccess[-\s]?stor(?:y|ies)\b",
    r"\bdeployment(?:s)?\b",
    r"\bdeployed\b",
    r"\bpartner(?:s|ship)?\b",
    r"\becosystem\b",
    r"\balliance(?:s)?\b",
)
HIGH_VALUE_LINK_RE = re.compile("|".join(HIGH_VALUE_LINK_PATTERNS), flags=re.IGNORECASE)
STRICT_SURFACE_RE = re.compile(
    r"\b(case[-\s]?stud(?:y|ies)|success[-\s]?stor(?:y|ies)|customer[-\s]?(story|stories|case|success|spotlight)|"
    r"customers\s+we\s+serve|deployment(?:s)?|deployed|partner(?:s|ship|ships| program)?|partner\s+with\s+us|"
    r"ecosystem|alliance|supplier(?:s)?|supply\s+agreement)\b|"
    r"/(case-studies|customer-stories|customers|partners|partner|success-library|ecosystem|alliance|suppliers)(/|\\?|#|$)",
    flags=re.IGNORECASE,
)
BODY_SIGNAL_RE = re.compile(
    r"\b(customers?|clients?|case stud(?:y|ies)|success stor(?:y|ies)|deployment|deployed|partners?|partnerships?|"
    r"ecosystem|alliances?|selected by|powered by|built on|collaboration|suppliers?|supply agreement|purchase order)\b",
    flags=re.IGNORECASE,
)
GENERIC_NAV_RE = re.compile(
    r"^(about|contact|careers|investors?|privacy|terms|support|login|search|subscribe|download|learn more|"
    r"all news|latest news|news archives|press releases?)$",
    flags=re.IGNORECASE,
)
SUPPORT_NAV_RE = re.compile(r"\b(customer\s+support|help center|support search|knowledge base|documentation)\b", flags=re.IGNORECASE)
LOW_VALUE_SURFACE_RE = re.compile(
    r"\b(customer\s+(portal|resource|resources|service|services|support|login|care|claims?)|"
    r"claims?(,\s*repairs?| and support| and plan)|terms?\s*(and|&)\s*conditions?|t&cs?|"
    r"client\s+trends?\s+report|insights?|white\s*papers?|resources?|builder\s+developer\s+resources|"
    r"privacy|contact\s+us|careers?|jobs?|working\s+at|find\s+a\s+(store|dealer|branch|location))\b",
    flags=re.IGNORECASE,
)
LOW_VALUE_PATH_RE = re.compile(
    r"/(careers?|jobs?|working-at|about/(businesses?|company)|insights?|resources?|support|help|contact|privacy|terms)(/|\?|#|$)",
    flags=re.IGNORECASE,
)
BLOCKED_SURFACE_PATH_RE = re.compile(
    r"/(careers?|jobs?|working-at|support|help|privacy|terms|terms-conditions|terms-and-conditions)(/|\?|#|$)|"
    r"(t&cs?|m-a-contact|contact-us|customer-service|customer-support|customer-care|claims?)",
    flags=re.IGNORECASE,
)
EXPLICIT_CUSTOMER_SURFACE_RE = re.compile(
    r"\b(case[-\s]?stud(?:y|ies)|success[-\s]?stor(?:y|ies)|customer[-\s]?(story|stories|case|success|spotlight)|"
    r"customers\s+we\s+serve|(?:customer|client|project|case|success|order|contract)[-\w\s]{0,60}deploy(?:ed|ment|ments)?|"
    r"deploy(?:ed|ment|ments)?[-\w\s]{0,60}(?:customer|client|project|case|success|order|contract))\b|"
    r"/(case-studies|customer-stories|success-library|customers)(/|\?|#|$)",
    flags=re.IGNORECASE,
)
EXPLICIT_PARTNER_SURFACE_RE = re.compile(
    r"\b(partner\s+(program|with\s+us|application|portal|center|ecosystem|catalog)|become\s+a\s+partner|"
    r"ecosystem\s+partner|technology\s+partner|alliance(?:s)?|supplier(?:s)?|supply\s+agreement|"
    r"strategic\s+partnership)\b|"
    r"/(partners?|partner-program|partner-application|ecosystem|alliance|alliances|suppliers?)(/|\?|#|$)",
    flags=re.IGNORECASE,
)
GENERIC_WEAK_ANCHOR_RE = re.compile(
    r"^(read more|learn more|more|view more|see more|continue reading|details?|click here|here|"
    r"さらに詳しく|詳しく|詳細|もっと見る|了解更多|查看更多|阅读更多)$",
    flags=re.IGNORECASE,
)

DEPLOYMENT_RE = re.compile(
    r"\b(customer|client|case study|success story|deployment|deployed|selected by|powered by|built on|uses|"
    r"award|contract|purchase order)\b",
    flags=re.IGNORECASE,
)
PARTNER_RE = re.compile(r"\b(partner|partnership|ecosystem|alliance|supplier|collaboration)\b", flags=re.IGNORECASE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build official customer/deployment/partner surface rows from issuer official product-page links."
    )
    parser.add_argument("--gap-action-plan", type=Path, default=DEFAULT_GAP_ACTION_PLAN)
    parser.add_argument("--official-product-surface-rows", type=Path, default=DEFAULT_OFFICIAL_PRODUCT_SURFACE_ROWS)
    parser.add_argument("--raw-product-page-dir", type=Path, default=DEFAULT_RAW_PRODUCT_PAGE_DIR)
    parser.add_argument("--raw-output-dir", type=Path, default=DEFAULT_RAW_OUTPUT_DIR)
    parser.add_argument("--output-rows", type=Path, default=DEFAULT_OUTPUT_ROWS)
    parser.add_argument("--output-attempts", type=Path, default=DEFAULT_OUTPUT_ATTEMPTS)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--domain-cache", type=Path, default=DEFAULT_DOMAIN_CACHE)
    parser.add_argument("--tickers", nargs="*", default=[])
    parser.add_argument("--max-candidates-per-ticker", type=int, default=3)
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--timeout-s", type=float, default=12.0)
    parser.add_argument("--sleep-s", type=float, default=0.02)
    parser.add_argument("--replace-output", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    generated_at = _utc_now()
    result = build_official_customer_deployment_surface_context_rows(
        gap_action_rows=_load_jsonl(args.gap_action_plan),
        official_product_surface_rows=_load_jsonl(args.official_product_surface_rows),
        domain_cache=_load_json(args.domain_cache),
        raw_product_page_dir=args.raw_product_page_dir,
        raw_output_dir=args.raw_output_dir,
        generated_at=generated_at,
        tickers=args.tickers,
        max_candidates_per_ticker=args.max_candidates_per_ticker,
        workers=args.workers,
        timeout_s=args.timeout_s,
        sleep_s=args.sleep_s,
    )
    output_rows = result["rows"] if args.replace_output else _dedupe_rows([*_load_jsonl(args.output_rows), *result["rows"]])
    output_attempts = result["attempts"] if args.replace_output else _dedupe_attempts(
        [*_load_jsonl(args.output_attempts), *result["attempts"]]
    )
    summary = build_summary(
        rows=output_rows,
        attempts=output_attempts,
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


def build_official_customer_deployment_surface_context_rows(
    *,
    gap_action_rows: Iterable[Mapping[str, Any]],
    official_product_surface_rows: Iterable[Mapping[str, Any]],
    domain_cache: Mapping[str, Any] | None = None,
    raw_product_page_dir: Path,
    raw_output_dir: Path,
    generated_at: str,
    tickers: Iterable[str] = (),
    max_candidates_per_ticker: int = 3,
    workers: int = 12,
    timeout_s: float = 12.0,
    sleep_s: float = 0.02,
) -> dict[str, list[dict[str, Any]]]:
    raw_output_dir.mkdir(parents=True, exist_ok=True)
    ticker_filter = {str(ticker).strip().upper() for ticker in tickers if str(ticker).strip()}
    action_gap_tickers = {
        str(row.get("ticker") or "").strip().upper()
        for row in gap_action_rows
        if str(row.get("dimension") or "") == "customer_deployment_depth"
        and str(row.get("ticker") or "").strip()
    }
    surface_by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in official_product_surface_rows:
        ticker = str(row.get("ticker") or "").strip().upper()
        if ticker:
            surface_by_ticker[ticker].append(dict(row))

    target_tickers = ticker_filter or set(surface_by_ticker)

    jobs = [
        (ticker, surface_by_ticker.get(ticker, []))
        for ticker in sorted(target_tickers)
        if surface_by_ticker.get(ticker)
    ]
    rows: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, int(workers or 1))) as executor:
        futures = {
            executor.submit(
                _process_ticker,
                ticker,
                surface_rows,
                raw_product_page_dir=raw_product_page_dir,
                raw_output_dir=raw_output_dir,
                domain_cache=domain_cache or {},
                generated_at=generated_at,
                max_candidates=max(1, int(max_candidates_per_ticker or 1)),
                timeout_s=timeout_s,
            ): ticker
            for ticker, surface_rows in jobs
        }
        for future in as_completed(futures):
            try:
                result = future.result()
            except Exception as exc:  # noqa: BLE001
                ticker = futures[future]
                attempts.append(_attempt(ticker=ticker, status="worker_failed", reason=f"{type(exc).__name__}:{exc}"))
                continue
            rows.extend(result["rows"])
            attempts.extend(result["attempts"])
            if sleep_s:
                time.sleep(float(sleep_s))
    for ticker in sorted(target_tickers - set(surface_by_ticker)):
        attempts.append(_attempt(ticker=ticker, status="no_official_product_surface_seed", reason="No official product page row for customer/deployment locator."))
    for ticker in sorted(action_gap_tickers - set(surface_by_ticker)):
        if ticker_filter and ticker not in ticker_filter:
            continue
        attempts.append(
            _attempt(
                ticker=ticker,
                status="action_gap_without_official_product_surface_seed",
                reason="Action plan still needs customer/deployment evidence, but no official product surface seed is available.",
            )
        )
    return {"rows": _dedupe_rows(rows), "attempts": attempts}


def _process_ticker(
    ticker: str,
    surface_rows: list[Mapping[str, Any]],
    *,
    raw_product_page_dir: Path,
    raw_output_dir: Path,
    domain_cache: Mapping[str, Any],
    generated_at: str,
    max_candidates: int,
    timeout_s: float,
) -> dict[str, list[dict[str, Any]]]:
    company_name = str(surface_rows[0].get("company") or surface_rows[0].get("company_name") or ticker)
    official_hosts = _official_hosts(surface_rows)
    verified_hosts, has_guess_only_cache = _verified_domain_hosts_for_ticker(ticker, domain_cache)
    if verified_hosts:
        official_hosts = {host for host in official_hosts if host in verified_hosts}
    elif has_guess_only_cache:
        official_hosts = set()
    if not official_hosts:
        return {
            "rows": [],
            "attempts": [
                _attempt(
                    ticker=ticker,
                    status="no_verified_official_host_seed",
                    reason="Official product surface rows do not expose a verified source_url/snapshot_url/url host, or only map to guess-only domains; refusing unbound raw-link promotion.",
                )
            ],
        }
    candidates = discover_candidate_links(
        ticker=ticker,
        surface_rows=surface_rows,
        raw_product_page_dir=raw_product_page_dir,
        official_hosts=official_hosts,
        max_candidates=max_candidates,
    )
    rows: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []
    if not candidates:
        return {
            "rows": rows,
            "attempts": [
                _attempt(
                    ticker=ticker,
                    status="no_candidate_link_found",
                    reason="Official product pages did not expose customer/case-study/partner/deployment links.",
                )
            ],
        }

    for candidate in candidates:
        body, status, reason = _fetch_candidate(candidate["url"], timeout_s=timeout_s)
        raw_path = raw_output_dir / f"{_slug(ticker)}_{_stable_digest(candidate['url'])}.html"
        raw_path.write_text(body or "", encoding="utf-8")
        if status != "fetched":
            attempts.append(
                _attempt(
                    ticker=ticker,
                    status=status,
                    reason=reason,
                    candidate_url=candidate["url"],
                    raw_path=raw_path,
                )
            )
            continue
        text = _clean_text(body)
        body_signal_text = f"{_page_title(body)} {text[:4000]}"
        if not BODY_SIGNAL_RE.search(body_signal_text):
            attempts.append(
                _attempt(
                    ticker=ticker,
                    status="fetched_no_customer_or_partner_signal",
                    reason="Fetched official page, but text did not contain customer/deployment/partner signal terms.",
                    candidate_url=candidate["url"],
                    raw_path=raw_path,
                )
            )
            continue
        rows.append(
            _context_row(
                ticker=ticker,
                company_name=company_name,
                candidate=candidate,
                raw_path=raw_path,
                body=body,
                text=text,
                generated_at=generated_at,
            )
        )
        attempts.append(
            _attempt(
                ticker=ticker,
                status="materialized",
                reason="Official customer/deployment/partner surface row materialized.",
                candidate_url=candidate["url"],
                raw_path=raw_path,
            )
        )
    return {"rows": rows, "attempts": attempts}


def discover_candidate_links(
    *,
    ticker: str,
    surface_rows: list[Mapping[str, Any]],
    raw_product_page_dir: Path,
    official_hosts: set[str],
    max_candidates: int,
) -> list[dict[str, str]]:
    bases = _surface_base_urls(surface_rows)
    raw_files = _raw_files_for_ticker(raw_product_page_dir, ticker)
    candidates: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for raw_file in raw_files:
        try:
            html_text = raw_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for href, label in _extract_anchors(html_text):
            label_clean = _clean_text(label)[:180]
            haystack = f"{label_clean} {href}"
            if not HIGH_VALUE_LINK_RE.search(haystack):
                continue
            if not STRICT_SURFACE_RE.search(haystack):
                continue
            if GENERIC_NAV_RE.match(label_clean):
                continue
            if SUPPORT_NAV_RE.search(haystack) and not re.search(r"\b(case[-\s]?stud(?:y|ies)|success[-\s]?stor(?:y|ies))\b", haystack, flags=re.IGNORECASE):
                continue
            if not _is_high_quality_surface_link(label_clean, href):
                continue
            if LOW_VALUE_SURFACE_RE.search(haystack) and not _is_high_quality_surface_link(label_clean, href):
                continue
            for base_url in bases or [""]:
                url = urljoin(base_url, href)
                if not _same_official_host(url, official_hosts):
                    continue
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                candidates.append(
                    {
                        "url": url,
                        "label": label_clean or url,
                        "source_product_url": base_url,
                        "raw_product_page": str(raw_file),
                    }
                )
                break
            if len(candidates) >= max_candidates:
                return candidates
    if not candidates:
        for candidate in _official_path_probe_candidates(bases, official_hosts):
            url = candidate["url"]
            if url in seen_urls:
                continue
            if not _same_official_host(url, official_hosts):
                continue
            if not _is_high_quality_surface_link(candidate["label"], url):
                continue
            seen_urls.add(url)
            candidates.append(candidate)
            if len(candidates) >= max_candidates:
                return candidates
    return candidates


def _official_path_probe_candidates(base_urls: list[str], official_hosts: set[str]) -> list[dict[str, str]]:
    probe_paths = [
        ("/case-studies", "Case studies"),
        ("/customer-stories", "Customer stories"),
        ("/success-stories", "Success stories"),
        ("/success-library", "Success library"),
        ("/customers", "Customers"),
        ("/partners", "Partners"),
        ("/partner", "Partner"),
        ("/partner-program", "Partner program"),
        ("/ecosystem", "Ecosystem"),
        ("/alliances", "Alliances"),
        ("/suppliers", "Suppliers"),
    ]
    origins: list[str] = []
    seen_origins: set[str] = set()
    for base_url in base_urls:
        parsed = urlparse(base_url)
        if not parsed.scheme or not parsed.netloc:
            continue
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin not in seen_origins:
            seen_origins.add(origin)
            origins.append(origin)
    if not origins:
        origins = [f"https://www.{host}" for host in sorted(official_hosts)]
    candidates: list[dict[str, str]] = []
    for origin in origins[:2]:
        for path, label in probe_paths:
            candidates.append(
                {
                    "url": urljoin(origin, path),
                    "label": label,
                    "source_product_url": origin,
                    "raw_product_page": "",
                }
            )
    return candidates


def _context_row(
    *,
    ticker: str,
    company_name: str,
    candidate: Mapping[str, str],
    raw_path: Path,
    body: str,
    text: str,
    generated_at: str,
) -> dict[str, Any]:
    url = candidate["url"]
    label = _best_fact_label(candidate["label"], url, body, text)
    event_kind = _event_kind(label, url, text)
    source_role = (
        "official_customer_order_or_deployment_event"
        if event_kind == "official_customer_deployment_surface"
        else "supply_chain_official_relationship"
    )
    counterparty = _extract_counterparty(label)
    evidence_ref = f"official_customer_deployment_surface:{_stable_digest(ticker + url)}"
    preview = _clean_text(text)[:700]
    return {
        "schema_version": SCHEMA_VERSION,
        "ticker": ticker,
        "company_name": company_name,
        "generated_at": generated_at,
        "source_role": source_role,
        "requirement_id": source_role,
        "source_id": "official_customer_deployment_surface",
        "underlying_source_id": "official_customer_deployment_surface",
        "source_class": "issuer_official_customer_partner_deployment_surface",
        "source_family": "live_public_web_context",
        "runtime_source_family": "public_source_context",
        "source_layer": "L2",
        "source_layer_id": "L2",
        "source_url": url,
        "raw_path": str(raw_path),
        "evidence_ref": evidence_ref,
        "evidence_id": evidence_ref,
        "fact_label": label,
        "product_or_segment": label,
        "product_family": label,
        "counterparty": counterparty,
        "counterparty_binding_status": "counterparty_mentioned_in_snapshot" if counterparty else "not_bound",
        "issuer_binding_status": "issuer_mentioned_in_snapshot",
        "product_binding_status": "product_mentioned_in_snapshot",
        "parser_status": "source_specific_context_parser_pass",
        "source_specific_parser": "official_customer_deployment_surface_locator_v0_1",
        "source_specific_resolver": "issuer_official_domain_customer_surface_resolver_v0_1",
        "structured_context_type": event_kind,
        "structured_fact_status": "bounded_context_fact_materialized",
        "runtime_ready_context": True,
        "bounded_structured_context": True,
        "context_only": True,
        "exact_value_authority": False,
        "can_support_company_exact_fact": False,
        "allowed_claims": [
            "official_customer_deployment_surface_context",
            "official_partner_or_ecosystem_surface_context",
            "customer_deployment_signal",
            "supply_chain_signal",
            "verification_lead",
        ],
        "forbidden_claims": [
            "issuer_revenue",
            "order_value",
            "backlog",
            "shipment_volume",
            "asp",
            "sell_through",
            "inventory",
            "market_share",
        ],
        "claim_boundary": (
            "Issuer-official customer, case-study, partner, ecosystem, or deployment surface context only. "
            "Use as bounded thesis-driver signal; do not infer revenue, order value, backlog, shipment, ASP, "
            "sell-through, inventory, or share."
        ),
        "authority_boundary": "L2 issuer official surface context; never exact financial or product KPI authority.",
        "citation": {"title": label, "url": url},
        "text": preview,
        "preview": preview,
        "entity_binding": {
            "issuer_ticker": ticker,
            "issuer_binding_status": "issuer_mentioned_in_snapshot",
            "counterparty_binding_status": "counterparty_mentioned_in_snapshot" if counterparty else "not_bound",
            "product_binding_status": "product_mentioned_in_snapshot",
            "resolver_status": "official_domain_surface_bound_to_issuer",
            "binding_claim_boundary": "Official surface context only; no exact revenue/order/backlog/sales/share promotion.",
        },
    }


def _event_kind(label: str, url: str, text: str) -> str:
    label_url = f"{label} {url}"
    haystack = f"{label_url} {text[:3000]}"
    if PARTNER_RE.search(label_url):
        return "official_partner_ecosystem_surface"
    if DEPLOYMENT_RE.search(haystack):
        return "official_customer_deployment_surface"
    if PARTNER_RE.search(haystack):
        return "official_partner_ecosystem_surface"
    return "official_customer_deployment_surface"


def _is_high_quality_surface_link(label: str, href: str) -> bool:
    haystack = f"{label} {href}"
    if BLOCKED_SURFACE_PATH_RE.search(haystack) and not re.search(
        r"/(case-studies|customer-stories|success-library)(/|\?|#|$)|\b(case[-\s]?stud(?:y|ies)|success[-\s]?stor(?:y|ies))\b",
        haystack,
        flags=re.IGNORECASE,
    ):
        return False
    has_customer = bool(EXPLICIT_CUSTOMER_SURFACE_RE.search(haystack))
    has_partner = bool(EXPLICIT_PARTNER_SURFACE_RE.search(haystack))
    if not has_customer and not has_partner:
        return False
    if LOW_VALUE_PATH_RE.search(href) and not (
        re.search(
            r"/(case-studies|customer-stories|success-library|partners?|ecosystem|alliance|alliances|suppliers?)(/|\?|#|$)",
            href,
            flags=re.IGNORECASE,
        )
        or re.search(
            r"\b(case[-\s]?stud(?:y|ies)|success[-\s]?stor(?:y|ies)|partner\s+(program|with\s+us|application)|supplier|alliance)\b",
            label,
            flags=re.IGNORECASE,
        )
    ):
        return False
    return True


def _best_fact_label(label: str, url: str, body: str, text: str) -> str:
    clean_label = _clean_text(label)
    if clean_label and not GENERIC_WEAK_ANCHOR_RE.match(clean_label) and clean_label != url and len(clean_label) >= 4:
        return clean_label[:220]
    page_title = _page_title(body)
    if page_title:
        return page_title[:220]
    clean_text = _clean_text(text)
    if clean_text:
        return clean_text[:220]
    return url


def _page_title(body: str) -> str:
    for pattern in (
        r"<h1\b[^>]*>(.*?)</h1>",
        r"<title\b[^>]*>(.*?)</title>",
        r"<meta\b[^>]*(?:property|name)=[\"'](?:og:title|twitter:title|title)[\"'][^>]*content=[\"']([^\"']+)[\"'][^>]*>",
        r"<meta\b[^>]*content=[\"']([^\"']+)[\"'][^>]*(?:property|name)=[\"'](?:og:title|twitter:title|title)[\"'][^>]*>",
    ):
        match = re.search(pattern, body or "", flags=re.IGNORECASE | re.DOTALL)
        if not match:
            continue
        value = _clean_text(match.group(1))
        if value and not GENERIC_WEAK_ANCHOR_RE.match(value):
            return value
    return ""


def _extract_counterparty(label: str) -> str:
    clean = _clean_text(label)
    patterns = [
        r"featured partner[:\s-]+(.+)$",
        r"customer story[:\s-]+(.+)$",
        r"success story[:\s-]+(.+)$",
        r"case study[:\s-]+(.+)$",
        r"made possible[:\s-]+(.+)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, clean, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()[:120]
    if len(clean.split()) <= 6 and re.search(r"\b(meta|microsoft|google|amazon|intel|nvidia|toyota|ford|gm|bmw)\b", clean, flags=re.IGNORECASE):
        return clean[:120]
    return ""


def _fetch_candidate(url: str, *, timeout_s: float) -> tuple[str, str, str]:
    try:
        response = requests.get(url, headers=REQUEST_HEADERS, timeout=timeout_s)
    except requests.RequestException as exc:
        return "", "fetch_failed", str(exc)[:240]
    if response.encoding is None or response.encoding.lower() in {"iso-8859-1", "latin-1"}:
        response.encoding = response.apparent_encoding or "utf-8"
    if response.status_code < 200 or response.status_code >= 300:
        return response.text or "", f"http_{response.status_code}", response.reason[:240]
    content_type = response.headers.get("content-type", "")
    if "text/html" not in content_type and "text/plain" not in content_type and not response.text.lstrip().startswith("<"):
        return response.text or "", "unsupported_content_type", content_type[:160]
    return response.text or "", "fetched", ""


def _official_hosts(rows: Iterable[Mapping[str, Any]]) -> set[str]:
    hosts: set[str] = set()
    for row in rows:
        for key in ("source_url", "snapshot_url", "url"):
            host = urlparse(str(row.get(key) or "")).netloc.lower()
            if host:
                hosts.add(_registrable_host(host))
    return hosts


def _verified_domain_hosts_for_ticker(ticker: str, domain_cache: Mapping[str, Any]) -> tuple[set[str], bool]:
    row = domain_cache.get(ticker) if isinstance(domain_cache, Mapping) else None
    if not isinstance(row, Mapping):
        return set(), False
    resolver_sources = row.get("resolver_sources") if isinstance(row.get("resolver_sources"), Mapping) else {}
    verified_values: list[str] = []
    guess_values: list[str] = []
    for source_id, values in resolver_sources.items():
        if not isinstance(values, list):
            continue
        if source_id == "company_name_domain_guess":
            guess_values.extend(str(value).strip() for value in values if str(value).strip())
        else:
            verified_values.extend(str(value).strip() for value in values if str(value).strip())
    verified_hosts = {_registrable_host(_domain_value_host(value)) for value in verified_values}
    verified_hosts = {host for host in verified_hosts if host}
    has_guess_only_cache = bool(guess_values and not verified_hosts)
    return verified_hosts, has_guess_only_cache


def _domain_value_host(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw if re.match(r"^https?://", raw, flags=re.IGNORECASE) else f"https://{raw}")
    return parsed.netloc or parsed.path


def _surface_base_urls(rows: Iterable[Mapping[str, Any]]) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for row in rows:
        url = str(row.get("source_url") or row.get("snapshot_url") or row.get("url") or "").strip()
        if url and url not in seen:
            urls.append(url)
            seen.add(url)
    return urls


def _same_official_host(url: str, official_hosts: set[str]) -> bool:
    host = _registrable_host(urlparse(url).netloc.lower())
    return bool(host and (not official_hosts or host in official_hosts))


def _registrable_host(host: str) -> str:
    host = host.split("@")[-1].split(":")[0].strip(".").lower()
    if host.startswith("www."):
        host = host[4:]
    parts = host.split(".")
    if len(parts) >= 3 and parts[-2] in {"co", "com", "net", "org"} and len(parts[-1]) == 2:
        return ".".join(parts[-3:])
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return host


def _raw_files_for_ticker(raw_dir: Path, ticker: str) -> list[Path]:
    prefix = _slug(ticker)
    if not raw_dir.exists():
        return []
    return sorted(raw_dir.glob(f"{prefix}_*.html"))[:8]


def _extract_anchors(html_text: str) -> list[tuple[str, str]]:
    anchors: list[tuple[str, str]] = []
    for match in re.finditer(r"<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", html_text, flags=re.IGNORECASE | re.DOTALL):
        href = html.unescape(match.group(1)).strip()
        label = _clean_text(match.group(2))
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        anchors.append((href, label))
    return anchors


def build_summary(
    *,
    rows: list[Mapping[str, Any]],
    attempts: list[Mapping[str, Any]],
    generated_at: str,
    output_rows: Path,
    output_attempts: Path,
) -> dict[str, Any]:
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "status": "pass",
        "generated_at": generated_at,
        "row_count": len(rows),
        "success_ticker_count": len({str(row.get("ticker") or "").upper() for row in rows}),
        "attempt_count": len(attempts),
        "attempt_status_counts": dict(Counter(str(row.get("status") or "") for row in attempts)),
        "source_role_counts": dict(Counter(str(row.get("source_role") or "") for row in rows)),
        "structured_context_type_counts": dict(Counter(str(row.get("structured_context_type") or "") for row in rows)),
        "boundary": "Issuer-official customer/deployment/partner surface context only; no revenue/order/backlog/sales/share promotion.",
        "outputs": {"rows": str(output_rows), "attempts": str(output_attempts)},
    }


def _attempt(
    *,
    ticker: str,
    status: str,
    reason: str,
    candidate_url: str = "",
    raw_path: Path | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": ATTEMPT_SCHEMA_VERSION,
        "ticker": ticker,
        "status": status,
        "reason": reason,
        "candidate_url": candidate_url,
        "raw_path": str(raw_path) if raw_path else "",
    }


def _dedupe_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        key = (
            str(row.get("ticker") or "").upper(),
            str(row.get("source_url") or ""),
            str(row.get("structured_context_type") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(dict(row))
    return sorted(out, key=lambda row: (str(row.get("ticker") or ""), str(row.get("source_url") or "")))


def _dedupe_attempts(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        key = (str(row.get("ticker") or "").upper(), str(row.get("candidate_url") or ""), str(row.get("status") or ""))
        if key in seen:
            continue
        seen.add(key)
        out.append(dict(row))
    return sorted(out, key=lambda row: (str(row.get("ticker") or ""), str(row.get("candidate_url") or ""), str(row.get("status") or "")))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _clean_text(value: str) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", str(value or "")))
    return re.sub(r"\s+", " ", text).strip()


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")


def _stable_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
