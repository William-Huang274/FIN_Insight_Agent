from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import urljoin, urlparse


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sec_agent.product_family_source_routes import load_jsonl_rows  # noqa: E402


SCHEMA_VERSION = "fin_agent_official_product_catalog_context_rows_v0_1"
SUMMARY_SCHEMA_VERSION = "fin_agent_official_product_catalog_context_summary_v0_1"

DEFAULT_INPUT = Path(
    "Z:/FIN_Insight_Agent_data/processed_private/public_source_extended_materialization/company_product_pages/company_product_pages.materialized.jsonl"
)
DEFAULT_ASSIGNMENTS = REPO_ROOT / "data/manifests/company_product_family_assignments_v0_1.jsonl"
DEFAULT_OUTPUT_ROWS = REPO_ROOT / "data/manifests/official_product_catalog_context_rows_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY = REPO_ROOT / "data/manifests/official_product_catalog_context_summary_v0_1.json"

GENERIC_LABELS = {
    "about",
    "about us",
    "all",
    "account",
    "careers",
    "cart",
    "categories",
    "charter members",
    "company",
    "company information",
    "compare",
    "contact",
    "corporate members",
    "corporate partners",
    "customers",
    "customer service",
    "download",
    "explore",
    "featured",
    "features",
    "find a warehouse",
    "get in touch",
    "home",
    "holiday schedule",
    "international members",
    "investors",
    "latest insights",
    "latest sia news",
    "learn",
    "learn more",
    "login",
    "menu",
    "news",
    "overview",
    "our",
    "partners",
    "policy priorities",
    "popular resources",
    "privacy",
    "products",
    "r&d",
    "resources",
    "search",
    "select country/region",
    "semiconductor industry association",
    "services",
    "shop",
    "sifma",
    "skip to main content",
    "social media",
    "solutions",
    "support",
    "terms",
    "who we are",
}

GENERIC_PATTERNS = (
    "accessibility",
    "annual report",
    "career",
    "cookie",
    "copyright",
    "event",
    "governance",
    "investor",
    "language",
    "leadership",
    "member",
    "membership",
    "privacy",
    "press release",
    "scroll",
    "sign in",
    "submit feedback",
    "terms of",
)

COUNTRY_OR_REGION_LABELS = {
    "argentina",
    "australia",
    "austria",
    "belgium",
    "brazil",
    "bulgaria",
    "canada",
    "china",
    "france",
    "germany",
    "india",
    "italy",
    "japan",
    "mexico",
    "netherlands",
    "poland",
    "spain",
    "uk",
    "united kingdom",
    "united states",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract official product catalog rows from materialized company product pages.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--family-assignments", type=Path, default=DEFAULT_ASSIGNMENTS)
    parser.add_argument("--output-rows", type=Path, default=DEFAULT_OUTPUT_ROWS)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--max-items-per-page", type=int, default=24)
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    page_rows = load_jsonl_rows(args.input)
    assignments = load_jsonl_rows(args.family_assignments)
    rows = build_official_product_catalog_context_rows(
        page_rows=page_rows,
        family_assignments=assignments,
        generated_at=generated_at,
        max_items_per_page=args.max_items_per_page,
    )
    summary = build_summary(page_rows=page_rows, rows=rows, generated_at=generated_at)
    _write_jsonl(args.output_rows, rows)
    args.output_summary.parent.mkdir(parents=True, exist_ok=True)
    args.output_summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if args.strict and not rows:
        return 1
    return 0


def build_official_product_catalog_context_rows(
    *,
    page_rows: Iterable[Mapping[str, Any]],
    family_assignments: Iterable[Mapping[str, Any]],
    generated_at: str,
    max_items_per_page: int = 24,
) -> list[dict[str, Any]]:
    assignments_by_ticker: dict[str, list[dict[str, Any]]] = {}
    for row in family_assignments:
        ticker = str(row.get("ticker") or "").strip().upper()
        if ticker:
            assignments_by_ticker.setdefault(ticker, []).append(dict(row))

    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for page in page_rows:
        ticker = str(page.get("ticker") or "").strip().upper()
        url = str(page.get("source_url") or page.get("url") or "").strip()
        if not ticker or not url:
            continue
        body = _page_body(page)
        if not body.strip():
            continue
        candidates = _catalog_candidates(page=page, body=body, max_items=max_items_per_page)
        if not candidates:
            continue
        assignments = assignments_by_ticker.get(ticker, [])
        for candidate in candidates:
            matched_assignments = _matched_assignments(candidate=candidate, assignments=assignments)
            for assignment, matched_terms, match_status in matched_assignments:
                row = _catalog_row(
                    page=page,
                    candidate=candidate,
                    assignment=assignment,
                    matched_terms=matched_terms,
                    family_match_status=match_status,
                    generated_at=generated_at,
                )
                key = str(row["evidence_ref"])
                if key not in seen:
                    out.append(row)
                    seen.add(key)
    return sorted(out, key=lambda row: (row["ticker"], row["family_id"], row["product_or_segment"], row["catalog_candidate_url"]))


def build_summary(*, page_rows: list[Mapping[str, Any]], rows: list[Mapping[str, Any]], generated_at: str) -> dict[str, Any]:
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "pass" if rows else "gap",
        "input_page_count": len(page_rows),
        "catalog_row_count": len(rows),
        "ticker_count": len({str(row.get("ticker") or "") for row in rows}),
        "family_count": len({str(row.get("family_id") or "") for row in rows}),
        "product_candidate_count": len({str(row.get("ticker") or "") + "::" + str(row.get("product_or_segment") or "") for row in rows}),
        "rows_by_ticker_top20": _top_counts(rows, "ticker", limit=20),
        "rows_by_family_top20": _top_counts(rows, "family_id", limit=20),
        "boundary": "Official catalog rows identify product taxonomy/spec/navigation candidates only; they do not support sales, share, ASP, inventory, sell-through, or product KPI claims.",
    }


def _catalog_candidates(*, page: Mapping[str, Any], body: str, max_items: int) -> list[dict[str, Any]]:
    url = str(page.get("source_url") or page.get("url") or "")
    candidates: list[dict[str, Any]] = []
    product = str(page.get("product") or "").strip()
    if _valid_label(product):
        candidates.append({"label": product, "candidate_url": url, "candidate_source": "materialized_page_product", "score": 5})
    title = str(page.get("title") or "").strip()
    title_label = re.sub(r"\s*[-|].*$", "", title).strip()
    if _valid_label(title_label):
        candidates.append({"label": title_label, "candidate_url": url, "candidate_source": "page_title", "score": 3})

    for tag, text in _heading_texts(body):
        if _valid_label(text) and (tag in {"h1", "h2"} or _label_has_product_signal(text)):
            candidates.append({"label": text, "candidate_url": url, "candidate_source": tag, "score": 4})
    for label, href in _anchor_candidates(body, base_url=url):
        if _valid_label(label) and _productish_url(href):
            score = 2 + (2 if _productish_url(href) else 0)
            candidates.append({"label": label, "candidate_url": href or url, "candidate_source": "anchor", "score": score})
    for label in _json_ld_names(body):
        if _valid_label(label):
            candidates.append({"label": label, "candidate_url": url, "candidate_source": "json_ld", "score": 4})

    by_label: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        normalized = _normalize_label(str(candidate.get("label") or ""))
        if not normalized:
            continue
        candidate["label"] = normalized
        key = normalized.lower()
        existing = by_label.get(key)
        if not existing or int(candidate.get("score") or 0) > int(existing.get("score") or 0):
            by_label[key] = candidate
    return sorted(by_label.values(), key=lambda item: (-int(item.get("score") or 0), str(item.get("label") or "")))[: max(1, int(max_items or 1))]


def _matched_assignments(*, candidate: Mapping[str, Any], assignments: list[Mapping[str, Any]]) -> list[tuple[Mapping[str, Any], list[str], str]]:
    if not assignments:
        return []
    text = " ".join(str(candidate.get(key) or "") for key in ("label", "candidate_url", "candidate_source")).lower()
    matches: list[tuple[Mapping[str, Any], list[str], str]] = []
    for assignment in assignments:
        terms = _family_terms(assignment)
        matched = [term for term in terms if _term_matches(text, term)]
        if matched:
            matches.append((assignment, matched[:8], "family_term_match"))
    if matches:
        return matches[:3]
    if len(assignments) == 1:
        return [(assignments[0], [], "single_family_default")]
    return []


def _catalog_row(
    *,
    page: Mapping[str, Any],
    candidate: Mapping[str, Any],
    assignment: Mapping[str, Any],
    matched_terms: list[str],
    family_match_status: str,
    generated_at: str,
) -> dict[str, Any]:
    ticker = str(page.get("ticker") or assignment.get("ticker") or "").strip().upper()
    label = str(candidate.get("label") or "").strip()
    page_url = str(page.get("source_url") or page.get("url") or "").strip()
    candidate_url = str(candidate.get("candidate_url") or page_url).strip()
    title = str(page.get("title") or label).strip()
    company = str(page.get("company") or assignment.get("company_name") or "").strip()
    family_id = str(assignment.get("family_id") or "").strip()
    family_name = str(assignment.get("family_name") or family_id).strip()
    evidence_ref = _stable_ref("official_product_catalog", [ticker, family_id, label, candidate_url])
    summary = (
        f"Official company product/catalog surface lists {label}"
        f" under {family_name if family_name else 'assigned product family'}; "
        "this is taxonomy/spec/navigation context only, not sales, share, ASP, inventory, or sell-through authority."
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "evidence_ref": evidence_ref,
        "evidence_id": evidence_ref,
        "parent_evidence_ref": _stable_ref("official_product_surface", [ticker, page_url, str(page.get("product") or "")]),
        "source_id": "company_product_pages",
        "underlying_source_id": "company_product_pages",
        "source_family": "live_public_web_context",
        "runtime_source_family": "public_source_context",
        "source_class": "company_product_page",
        "source_specific_parser": "official_product_catalog_parser_v0_1",
        "source_layer_id": "L2",
        "source_layer": "L2",
        "layer_id": "L2",
        "parser_status": "official_product_catalog_parser_pass",
        "structured_fact_status": "bounded_context_fact_materialized",
        "evidence_graph_status": "runtime_ready_context",
        "bounded_structured_context": True,
        "retrieval_route": "live_public_web_context",
        "repair_type": "product_surface",
        "analysis_dimension": "product_and_production",
        "claim_types": ["official_product_surface", "product_taxonomy_context", "product_spec_context", "verification_lead"],
        "ticker": ticker,
        "company": company,
        "company_name": company,
        "family_id": family_id,
        "product_family": family_name,
        "product_or_segment": label,
        "topic": label,
        "fact_type": "official_product_taxonomy_context",
        "structured_context_type": "official_product_taxonomy_context",
        "fact_label": label,
        "fact_value": candidate_url,
        "structured_context_summary": summary,
        "text": " ".join([label, family_name, " ".join(matched_terms), summary]),
        "preview": summary,
        "metric_leads": ["product taxonomy", "product specification", "product availability context"],
        "matched_family_terms": matched_terms,
        "family_match_status": family_match_status,
        "catalog_candidate_source": candidate.get("candidate_source") or "",
        "catalog_candidate_url": candidate_url,
        "url": page_url,
        "source_url": page_url,
        "snapshot_url": page_url,
        "domain": _domain(page_url),
        "citation": {"url": page_url, "title": title, "candidate_url": candidate_url},
        "source_title": title,
        "as_of_datetime": generated_at,
        "context_only": True,
        "lead_only": False,
        "exact_value_authority": False,
        "source_claim_strength": "bounded_official_context",
        "promotion_status": "bounded_context_fact_available",
        "issuer_binding_status": "company_domain_bound",
        "product_binding_status": "product_mentioned_in_snapshot",
        "counterparty_binding_status": "not_bound",
        "entity_binding": {
            "schema_version": "finsight_public_web_entity_binding_v0_1",
            "issuer_ticker": ticker,
            "issuer_binding_status": "company_domain_bound",
            "issuer_matched_terms": [ticker, company] if company else [ticker],
            "product_binding_status": "product_mentioned_in_snapshot",
            "product_matched_terms": [label],
            "counterparty_binding_status": "not_bound",
            "counterparty_matched_terms": [],
            "source_entity_role": "product_or_platform_context",
            "binding_claim_boundary": "Catalog binding routes official product context to specialists; it does not promote product KPI, sales, shipment, or market-share authority.",
        },
        "allowed_claims": ["official_product_surface", "product_taxonomy_context", "product_spec_context"],
        "forbidden_claims": ["company_sales", "market_share", "product_revenue", "ASP", "inventory", "sell_through"],
        "claim_boundary": "official product catalog context only; no sales, share, ASP, inventory, or product KPI authority",
        "authority_boundary": "company official product surface; context only until exact product KPI parser/citation gate passes",
    }


def _page_body(page: Mapping[str, Any]) -> str:
    for key in ("raw_path", "clean_text_path"):
        raw_value = str(page.get(key) or "").strip()
        if not raw_value:
            continue
        path = Path(raw_value)
        if path.is_file():
            return path.read_text(encoding="utf-8", errors="replace")
    return str(page.get("body") or "")


def _heading_texts(body: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for tag, raw in re.findall(r"(?is)<(h[1-4])\b[^>]*>(.*?)</\1>", body)[:80]:
        text = _clean_html_text(raw)
        if text:
            out.append((tag.lower(), text))
    return out


def _anchor_candidates(body: str, *, base_url: str) -> list[tuple[str, str]]:
    base_domain = _domain(base_url)
    out: list[tuple[str, str]] = []
    for attrs, raw in re.findall(r"(?is)<a\b([^>]*)>(.*?)</a>", body)[:600]:
        label = _clean_html_text(raw)
        href_match = re.search(r"""(?is)\bhref\s*=\s*['"]([^'"]+)['"]""", attrs)
        href = urljoin(base_url, unescape(href_match.group(1))) if href_match else ""
        if href and base_domain and _domain(href) != base_domain:
            continue
        if label:
            out.append((label, href))
    return out


def _json_ld_names(body: str) -> list[str]:
    names: list[str] = []
    for raw in re.findall(r"(?is)<script[^>]+application/ld\+json[^>]*>(.*?)</script>", body)[:16]:
        try:
            payload = json.loads(unescape(raw).strip())
        except json.JSONDecodeError:
            continue
        for item in _json_items(payload):
            type_text = " ".join(_ensure_list(item.get("@type") or item.get("type"))).lower()
            if "product" in type_text or "service" in type_text:
                names.append(str(item.get("name") or "").strip())
    return [name for name in names if name]


def _json_items(value: Any) -> list[Mapping[str, Any]]:
    if isinstance(value, list):
        out: list[Mapping[str, Any]] = []
        for item in value:
            out.extend(_json_items(item))
        return out
    if not isinstance(value, Mapping):
        return []
    rows: list[Mapping[str, Any]] = [value]
    graph = value.get("@graph")
    if isinstance(graph, list):
        rows.extend(item for item in graph if isinstance(item, Mapping))
    return rows


def _valid_label(value: str) -> bool:
    text = _normalize_label(value)
    if not text:
        return False
    lower = text.lower()
    if lower in GENERIC_LABELS or lower in COUNTRY_OR_REGION_LABELS or any(pattern in lower for pattern in GENERIC_PATTERNS):
        return False
    if len(text) < 3 or len(text) > 90:
        return False
    if text.endswith(".") and not _label_has_product_signal(text):
        return False
    if text.count(".") >= 2 or text.count("?"):
        return False
    if re.search(r"\b(about|account|buy|cart|compare|contact|customer|delivery|environment|get|learn|locations|login|membership|policy|supplier|vendor)\b", lower):
        return False
    if re.search(r"\b(benefit|browse|continue|designed|everyday|everything|explore|homepage|pushing|reassurance|resilience|trusted names)\b", lower):
        return False
    if re.search(r"[\u4e00-\u9fff]?\s*图片\s*\d+", lower):
        return False
    if len(text.split()) > 9:
        return False
    if not re.search(r"[A-Za-z0-9]", text):
        return False
    return True


def _normalize_label(value: str) -> str:
    text = _clean_html_text(value)
    text = re.sub(r"\s+", " ", text).strip(" -:|•")
    text = re.sub(r"\s+(learn more|overview|products|services)$", "", text, flags=re.I).strip()
    return text


def _clean_html_text(value: str) -> str:
    text = re.sub(r"(?is)<script\b.*?</script>|<style\b.*?</style>|<noscript\b.*?</noscript>", " ", str(value or ""))
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", unescape(text)).strip()


def _productish_url(url: str) -> bool:
    path = urlparse(str(url or "")).path.lower()
    blocked = (
        "/about",
        "/career",
        "/contact",
        "/investor",
        "/legal",
        "/privacy",
        "/sustainability",
        "/we-are",
    )
    if any(token in path for token in blocked):
        return False
    return any(
        token in path
        for token in (
            "/product",
            "/products",
            "/products-services",
            "/markets-we-serve",
            "/solution",
            "/service",
            "/cloud",
            "/watch",
            "/iphone",
            "/ipad",
            "/mac",
            "/airpods",
            "/ingredient",
            "/nutrition",
            "/server",
            "/switch",
            "/data-center",
            "/technologies",
        )
    )


def _label_has_product_signal(value: str) -> bool:
    lower = str(value or "").lower()
    return bool(
        re.search(
            r"\b("
            r"airpods|apple watch|blackwell|cuda|dgx|duv|euv|exe|gb[0-9]+|h[0-9]{3}|hgx|iphone|ipad|"
            r"lithography|mac|nvl[0-9]+|nxe|nvlink|poweredge|proliant|rtx|switch|watch"
            r")\b",
            lower,
        )
    )


def _matched_text(candidate: Mapping[str, Any]) -> str:
    return " ".join(str(candidate.get(key) or "") for key in ("label", "candidate_url", "candidate_source")).lower()


def _family_terms(assignment: Mapping[str, Any]) -> list[str]:
    return _unique_strings(
        [
            assignment.get("family_id"),
            assignment.get("family_name"),
            *(assignment.get("query_terms") or []),
            *(assignment.get("family_aliases") or []),
            *(assignment.get("matched_terms") or []),
        ]
    )


def _term_matches(text: str, term: str) -> bool:
    term_l = str(term or "").lower().replace("_", " ").strip()
    if not term_l:
        return False
    if len(term_l) <= 3:
        return bool(re.search(rf"\b{re.escape(term_l)}\b", text))
    return term_l in text


def _domain(url: str) -> str:
    return urlparse(str(url or "")).netloc.lower().removeprefix("www.")


def _stable_ref(prefix: str, parts: Iterable[str]) -> str:
    digest = hashlib.sha1("|".join(str(part or "") for part in parts).encode("utf-8", errors="ignore")).hexdigest()[:14]
    return f"{prefix}:{digest}"


def _top_counts(rows: Iterable[Mapping[str, Any]], key: str, *, limit: int) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "")
        if value:
            counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit])


def _ensure_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if value is None:
        return []
    return [str(value)]


def _unique_strings(values: Iterable[Any]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if text and text not in seen:
            out.append(text)
            seen.add(text)
    return out


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
