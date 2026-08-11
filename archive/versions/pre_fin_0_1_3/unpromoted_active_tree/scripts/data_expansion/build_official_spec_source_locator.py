from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import urljoin, urlparse, urlunparse


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


SCHEMA_VERSION = "finsight_official_spec_source_locator_candidates_v0_1"
SUMMARY_SCHEMA_VERSION = "finsight_official_spec_source_locator_summary_v0_1"

DEFAULT_MATERIALIZED_PRODUCT_PAGES = Path(
    "Z:/FIN_Insight_Agent_data/processed_private/public_source_extended_materialization/"
    "company_product_pages/company_product_pages.materialized.jsonl"
)
DEFAULT_ROUTE_PLAN = REPO_ROOT / "data" / "manifests" / "family_source_route_plan_v0_1.jsonl"
DEFAULT_OUTPUT_CANDIDATES = REPO_ROOT / "data" / "manifests" / "official_spec_source_locator_candidates_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY = REPO_ROOT / "data" / "manifests" / "official_spec_source_locator_summary_v0_1.json"

LOCATOR_ROUTE_IDS = {"technical_product_spec", "business_asset_profile_spec"}

TECHNICAL_HINTS = {
    "architecture",
    "benchmark",
    "brochure",
    "catalog",
    "configuration",
    "data sheet",
    "datasheet",
    "developer",
    "documentation",
    "features",
    "guide",
    "manual",
    "model",
    "performance",
    "platform",
    "product brief",
    "product guide",
    "reference",
    "resources",
    "spec",
    "specification",
    "technical",
    "white paper",
    "whitepaper",
}

ASSET_PROFILE_HINTS = {
    "asset",
    "assets",
    "capacity",
    "facility",
    "facilities",
    "fleet",
    "generation",
    "generating",
    "grid",
    "infrastructure",
    "locations",
    "plant",
    "plants",
    "portfolio",
    "power",
    "project",
    "projects",
    "renewable",
    "site",
    "sites",
}

BLOCKED_HINTS = {
    "about",
    "account",
    "cart",
    "careers",
    "checkout",
    "contact",
    "cookie",
    "events",
    "governance",
    "investor",
    "legal",
    "login",
    "news",
    "privacy",
    "search",
    "signin",
    "support",
    "terms",
}

BLOCKED_EXTENSIONS = {
    ".css",
    ".gif",
    ".ico",
    ".jpg",
    ".jpeg",
    ".js",
    ".json",
    ".png",
    ".svg",
    ".webp",
    ".zip",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Locate issuer-domain official product spec and business/asset profile detail pages "
            "from already-materialized official product pages."
        )
    )
    parser.add_argument("--materialized-product-pages", type=Path, default=DEFAULT_MATERIALIZED_PRODUCT_PAGES)
    parser.add_argument("--route-plan", type=Path, default=DEFAULT_ROUTE_PLAN)
    parser.add_argument("--output-candidates", type=Path, default=DEFAULT_OUTPUT_CANDIDATES)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--max-candidates-per-ticker-route", type=int, default=6)
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at = _utc_now()
    product_pages = _load_jsonl(args.materialized_product_pages)
    route_plan = _load_jsonl(args.route_plan)
    rows, diagnostics = build_official_spec_source_locator_candidates(
        product_pages=product_pages,
        route_plan_rows=route_plan,
        generated_at=generated_at,
        max_candidates_per_ticker_route=args.max_candidates_per_ticker_route,
    )
    summary = build_summary(
        product_pages=product_pages,
        route_plan_rows=route_plan,
        candidates=rows,
        diagnostics=diagnostics,
        generated_at=generated_at,
        output_candidates=args.output_candidates,
    )
    _write_jsonl(args.output_candidates, rows)
    _write_json(args.output_summary, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if args.strict and not rows:
        return 1
    return 0


def build_official_spec_source_locator_candidates(
    *,
    product_pages: Iterable[Mapping[str, Any]],
    route_plan_rows: Iterable[Mapping[str, Any]],
    generated_at: str,
    max_candidates_per_ticker_route: int = 6,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    route_targets = [
        dict(row)
        for row in route_plan_rows
        if str(row.get("route_id") or "") in LOCATOR_ROUTE_IDS
        and str(row.get("route_status") or "") != "runtime_family_row_available"
    ]
    targets_by_ticker: dict[str, list[dict[str, Any]]] = {}
    for row in route_targets:
        ticker = str(row.get("ticker") or "").upper().strip()
        if ticker:
            targets_by_ticker.setdefault(ticker, []).append(row)

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    per_ticker_route = Counter()
    diagnostics = {
        "product_page_count": 0,
        "route_target_count": len(route_targets),
        "link_count": 0,
        "candidate_count_before_cap": 0,
        "rejected_link_count": 0,
        "rejection_reasons": Counter(),
    }

    for page in product_pages:
        ticker = str(page.get("ticker") or "").upper().strip()
        if not ticker or ticker not in targets_by_ticker:
            continue
        source_url = str(page.get("source_url") or page.get("url") or "").strip()
        raw_path = Path(str(page.get("raw_path") or "")) if str(page.get("raw_path") or "").strip() else None
        body = ""
        if raw_path and raw_path.exists():
            body = raw_path.read_text(encoding="utf-8", errors="ignore")
        else:
            body = str(page.get("body") or page.get("html") or "")
        if not source_url or not body.strip():
            continue
        diagnostics["product_page_count"] += 1
        links = extract_links(body=body, base_url=source_url)
        diagnostics["link_count"] += len(links)
        for route in targets_by_ticker[ticker]:
            route_id = str(route.get("route_id") or "")
            per_key = (ticker, route_id)
            if per_ticker_route[per_key] >= max(1, int(max_candidates_per_ticker_route or 1)):
                continue
            for link in links:
                if per_ticker_route[per_key] >= max(1, int(max_candidates_per_ticker_route or 1)):
                    break
                reason = _reject_link(link=link, source_url=source_url)
                if reason:
                    diagnostics["rejected_link_count"] += 1
                    diagnostics["rejection_reasons"][reason] += 1
                    continue
                score, patterns = _score_link(link=link, route=route, route_id=route_id)
                if score < 4:
                    diagnostics["rejected_link_count"] += 1
                    diagnostics["rejection_reasons"]["below_locator_score_threshold"] += 1
                    continue
                diagnostics["candidate_count_before_cap"] += 1
                row = _candidate_row(
                    page=page,
                    route=route,
                    link=link,
                    score=score,
                    patterns=patterns,
                    generated_at=generated_at,
                )
                key = str(row["candidate_id"])
                if key in seen:
                    continue
                seen.add(key)
                rows.append(row)
                per_ticker_route[per_key] += 1

    diagnostics["rejection_reasons"] = dict(sorted(diagnostics["rejection_reasons"].items()))
    return sorted(
        rows,
        key=lambda row: (
            str(row.get("ticker") or ""),
            str(row.get("route_id") or ""),
            -int(row.get("locator_score") or 0),
            str(row.get("candidate_url") or ""),
        ),
    ), diagnostics


def extract_links(*, body: str, base_url: str) -> list[dict[str, str]]:
    parser = _LinkExtractor()
    parser.feed(body)
    parser.close()
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in parser.links:
        href = html.unescape(str(item.get("href") or "")).strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        url = _canonical_url(urljoin(base_url, href))
        if not url or url in seen:
            continue
        seen.add(url)
        out.append({"url": url, "link_text": _clean_text(item.get("text") or ""), "title": _clean_text(item.get("title") or "")})
    return out


def build_summary(
    *,
    product_pages: list[Mapping[str, Any]],
    route_plan_rows: list[Mapping[str, Any]],
    candidates: list[Mapping[str, Any]],
    diagnostics: Mapping[str, Any],
    generated_at: str,
    output_candidates: Path,
) -> dict[str, Any]:
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "pass" if candidates else "gap",
        "input_product_page_count": len(product_pages),
        "input_route_plan_count": len(route_plan_rows),
        "candidate_count": len(candidates),
        "ticker_count": len({row.get("ticker") for row in candidates}),
        "route_counts": _counts(candidates, "route_id"),
        "source_role_counts": _counts(candidates, "source_role"),
        "candidate_status_counts": _counts(candidates, "materialization_status"),
        "diagnostics": dict(diagnostics),
        "outputs": {"candidates": str(output_candidates)},
        "authority_boundary": (
            "Locator rows are issuer-domain source candidates only. They are not evidence rows and cannot support "
            "product specs, product KPIs, revenue, orders, utilization, share, ASP, or demand claims until fetched "
            "and parsed into runtime rows."
        ),
    }


def _candidate_row(
    *,
    page: Mapping[str, Any],
    route: Mapping[str, Any],
    link: Mapping[str, str],
    score: int,
    patterns: list[str],
    generated_at: str,
) -> dict[str, Any]:
    ticker = str(page.get("ticker") or "").upper().strip()
    route_id = str(route.get("route_id") or "")
    candidate_url = str(link.get("url") or "")
    source_role = "technical_product_spec" if route_id == "technical_product_spec" else "business_asset_profile_spec"
    source_id = "official_product_spec_pages" if route_id == "technical_product_spec" else "official_project_pages"
    candidate_id = _stable_id("official_spec_source_candidate", [ticker, route_id, str(route.get("family_id") or ""), candidate_url])
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "candidate_id": candidate_id,
        "ticker": ticker,
        "company": page.get("company") or page.get("company_name") or route.get("company_name") or "",
        "company_name": page.get("company") or page.get("company_name") or route.get("company_name") or "",
        "route_id": route_id,
        "source_role": source_role,
        "source_id": source_id,
        "family_id": route.get("family_id") or "",
        "family_name": route.get("family_name") or page.get("product") or "",
        "product": route.get("family_name") or page.get("product") or "",
        "candidate_url": candidate_url,
        "source_url": candidate_url,
        "referring_source_url": page.get("source_url") or page.get("url") or "",
        "referring_raw_path": page.get("raw_path") or "",
        "link_text": link.get("link_text") or "",
        "link_title": link.get("title") or "",
        "locator_score": score,
        "matched_patterns": patterns,
        "materialization_status": "candidate_not_fetched",
        "candidate_boundary": "Issuer-domain locator candidate only; fetch and parser gates are required before runtime use.",
        "claim_boundary": (
            "Candidate URL is not a runtime evidence row. It can only be used to drive source fetching and parsing."
        ),
        "allowed_next_actions": ["fetch_official_detail_page", "parse_into_runtime_context_row"],
        "forbidden_claims": [
            "product_revenue",
            "unit_sales",
            "ASP",
            "market_share",
            "inventory",
            "sell_through",
            "backlog",
            "customer_order_value",
            "demand_proof",
        ],
    }


def _score_link(*, link: Mapping[str, str], route: Mapping[str, Any], route_id: str) -> tuple[int, list[str]]:
    text = _link_haystack(link)
    query_terms = [str(term).lower() for term in route.get("query_terms") or [] if str(term).strip()]
    family_terms = [str(route.get("family_name") or "").lower(), str(route.get("family_id") or "").replace("_", " ").lower()]
    hints = TECHNICAL_HINTS if route_id == "technical_product_spec" else ASSET_PROFILE_HINTS
    score = 0
    patterns: list[str] = []
    for hint in hints:
        if hint in text:
            score += 3
            patterns.append(hint)
    for term in [*query_terms, *family_terms]:
        term = term.strip()
        if len(term) >= 3 and term in text:
            score += 2
            patterns.append(f"family:{term}")
    if text.endswith(".pdf") or ".pdf?" in text:
        score += 1
        patterns.append("pdf")
    if route_id == "technical_product_spec" and re.search(r"\b(h100|h200|b200|gb200|blackwell|cuda|gpu|cpu|tpu|accelerator|wafer|node|battery|camera|server|instance)\b", text):
        score += 3
        patterns.append("technical-product-token")
    if route_id == "business_asset_profile_spec" and re.search(r"\b(mw|megawatt|kw|kilowatt|plant|facility|project|fleet|asset|capacity)\b", text):
        score += 3
        patterns.append("asset-profile-token")
    if any(blocked in text for blocked in BLOCKED_HINTS):
        score -= 3
        patterns.append("blocked-hint-penalty")
    return score, _unique_strings(patterns)


def _reject_link(*, link: Mapping[str, str], source_url: str) -> str:
    candidate = str(link.get("url") or "").strip()
    if not candidate:
        return "empty_url"
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"}:
        return "unsupported_scheme"
    source_domain = _domain(source_url)
    candidate_domain = _domain(candidate)
    if not source_domain or not candidate_domain:
        return "missing_domain"
    if not (candidate_domain == source_domain or candidate_domain.endswith("." + source_domain) or source_domain.endswith("." + candidate_domain)):
        return "off_domain"
    path = parsed.path.lower()
    if any(path.endswith(ext) for ext in BLOCKED_EXTENSIONS):
        return "blocked_static_extension"
    text = _link_haystack(link)
    if any(token in text for token in ("#", "javascript:", "mailto:", "tel:")):
        return "non_page_link"
    if len(text) > 500:
        return "link_text_too_long"
    return ""


def _link_haystack(link: Mapping[str, str]) -> str:
    return " ".join([str(link.get("url") or ""), str(link.get("link_text") or ""), str(link.get("title") or "")]).lower()


def _canonical_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    query = parsed.query
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), path, "", query, ""))


def _domain(url: str) -> str:
    return urlparse(url).netloc.lower().split(":")[0].lstrip("www.")


class _LinkExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[dict[str, str]] = []
        self._current: dict[str, str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        attr = {key.lower(): value or "" for key, value in attrs}
        self._current = {"href": attr.get("href", ""), "title": attr.get("title", ""), "text": ""}

    def handle_data(self, data: str) -> None:
        if self._current is not None and data.strip():
            self._current["text"] = (self._current.get("text") or "") + " " + data.strip()

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._current is not None:
            self.links.append(self._current)
            self._current = None


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(str(value or ""))).strip()


def _counts(rows: Iterable[Mapping[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(key) or "") for row in rows).items()))


def _stable_id(prefix: str, parts: Iterable[str]) -> str:
    raw = "|".join(str(part) for part in parts)
    return f"{prefix}:{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:16]}"


def _unique_strings(values: Iterable[Any]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


if __name__ == "__main__":
    raise SystemExit(main())
