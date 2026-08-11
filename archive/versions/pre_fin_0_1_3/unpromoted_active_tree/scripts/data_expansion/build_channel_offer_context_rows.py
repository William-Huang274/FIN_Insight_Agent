from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sec_agent.public_web_context_parser import parse_public_web_context_rows  # noqa: E402
from sec_agent.source_coverage_gate import build_source_coverage_gate  # noqa: E402


SCHEMA_VERSION = "fin_agent_channel_offer_context_row_v0_1"
SUMMARY_SCHEMA_VERSION = "fin_agent_channel_offer_context_summary_v0_1"

CHANNEL_SOURCE_ID = "channel_pricing_quotations"
REVIEW_SOURCE_ID = "platform_reviews_rankings_downloads"
DEFAULT_SOURCE_LAYER_ROWS = REPO_ROOT / "data" / "manifests" / "source_layer_capability_audit_v0_1.jsonl"
DEFAULT_OUTPUT_ROWS = REPO_ROOT / "data" / "manifests" / "channel_offer_context_rows_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY = REPO_ROOT / "data" / "manifests" / "channel_offer_context_summary_v0_1.json"
DEFAULT_OUTPUT_COVERAGE = REPO_ROOT / "data" / "manifests" / "channel_offer_runtime_coverage_gate_v0_1.json"
DEFAULT_RAW_DIR = Path("Z:/FIN_Insight_Agent_data/raw_private/public_source_extended_materialization/channel_offers")

FetchFunc = Callable[[str, float], tuple[int, str, str]]


DEFAULT_CHANNEL_OFFER_PROBES: tuple[dict[str, Any], ...] = (
    {
        "ticker": "AAPL",
        "company_name": "Apple",
        "company_names": ["Apple"],
        "product_terms": ["MacBook Pro", "MacBook", "M4 Pro", "M5 Pro"],
        "search_query": "apple macbook pro m4 cdw",
    },
    {
        "ticker": "MSFT",
        "company_name": "Microsoft",
        "company_names": ["Microsoft"],
        "product_terms": ["Surface Laptop", "Surface", "Copilot PC"],
        "search_query": "microsoft surface laptop 7 cdw",
    },
    {
        "ticker": "NVDA",
        "company_name": "NVIDIA",
        "company_names": ["NVIDIA", "Nvidia Corp"],
        "product_terms": ["RTX", "RTX 4000 Ada", "graphics card"],
        "search_query": "nvidia rtx 4000 ada cdw",
    },
    {
        "ticker": "HPQ",
        "company_name": "HP Inc",
        "company_names": ["HP", "HP Inc"],
        "product_terms": ["EliteBook", "Copilot PC", "Notebook"],
        "search_query": "hp elitebook cdw",
    },
    {
        "ticker": "DELL",
        "company_name": "Dell Technologies",
        "company_names": ["Dell", "Dell Technologies"],
        "product_terms": ["PowerEdge", "server", "rack-mountable"],
        "search_query": "dell poweredge server cdw",
    },
    {
        "ticker": "LNVGY",
        "company_name": "Lenovo",
        "company_names": ["Lenovo"],
        "product_terms": ["ThinkPad", "AI PC", "Notebook"],
        "search_query": "lenovo thinkpad cdw",
    },
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build bounded L3 channel offer and review context rows from public reseller pages.")
    parser.add_argument("--tickers", nargs="*", default=[], help="Optional ticker allowlist.")
    parser.add_argument("--source-layer-rows", type=Path, default=DEFAULT_SOURCE_LAYER_ROWS)
    parser.add_argument("--output-rows", type=Path, default=DEFAULT_OUTPUT_ROWS)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--output-coverage-gate", type=Path, default=DEFAULT_OUTPUT_COVERAGE)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--timeout-s", type=float, default=15.0)
    parser.add_argument("--fetch-retries", type=int, default=2)
    parser.add_argument("--max-products-per-probe", type=int, default=2)
    parser.add_argument("--max-search-links", type=int, default=8)
    parser.add_argument("--strict", action="store_true", help="Exit non-zero if no channel offer rows are produced.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    result = build_channel_offer_context_rows(
        probes=DEFAULT_CHANNEL_OFFER_PROBES,
        generated_at=generated_at,
        raw_dir=args.raw_dir,
        tickers=args.tickers,
        timeout_s=args.timeout_s,
        fetch_retries=args.fetch_retries,
        max_products_per_probe=args.max_products_per_probe,
        max_search_links=args.max_search_links,
    )
    source_layer_rows = _load_jsonl(args.source_layer_rows)
    coverage_gate = build_channel_offer_coverage_gate(
        context_rows=result["rows"],
        source_layer_rows=source_layer_rows,
        generated_at=generated_at,
    )
    summary = build_summary(
        rows=result["rows"],
        attempts=result["attempts"],
        coverage_gate=coverage_gate,
        generated_at=generated_at,
        output_rows=args.output_rows,
        output_coverage=args.output_coverage_gate,
    )
    _write_jsonl(args.output_rows, result["rows"])
    _write_json(args.output_summary, summary)
    _write_json(args.output_coverage_gate, coverage_gate)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if args.strict and summary["channel_offer_row_count"] <= 0:
        return 1
    return 0


def build_channel_offer_context_rows(
    *,
    probes: Iterable[Mapping[str, Any]],
    generated_at: str,
    raw_dir: Path,
    tickers: Iterable[str] = (),
    timeout_s: float = 15.0,
    fetch_retries: int = 2,
    max_products_per_probe: int = 2,
    max_search_links: int = 8,
    fetch: FetchFunc | None = None,
) -> dict[str, Any]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    ticker_filter = {str(ticker).strip().upper() for ticker in tickers if str(ticker).strip()}
    fetcher = fetch or _fetch_url
    rows: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []

    for probe in probes:
        ticker = str(probe.get("ticker") or "").strip().upper()
        if ticker_filter and ticker not in ticker_filter:
            continue
        product_urls = _unique_strings(probe.get("urls") or [])
        search_query = str(probe.get("search_query") or "").strip()
        if search_query:
            search_url = cdw_search_url(search_query)
            try:
                status_code, content_type, body = _fetch_with_retries(fetcher, search_url, timeout_s, fetch_retries)
            except Exception as exc:  # noqa: BLE001
                attempts.append(_attempt(ticker, "cdw_search", search_url, "fetch_failed", reason=f"{type(exc).__name__}: {str(exc)[:220]}"))
            else:
                raw_search_path = raw_dir / f"{ticker.lower()}_cdw_search_{_slug(search_query)}.html"
                raw_search_path.write_text(body, encoding="utf-8")
                if status_code >= 400 or not body.strip():
                    attempts.append(_attempt(ticker, "cdw_search", search_url, "unusable_response", reason=f"http_{status_code}" if status_code else "empty_body", raw_path=str(raw_search_path)))
                else:
                    discovered = extract_cdw_product_links(body, base_url=search_url, max_links=max_search_links)
                    product_urls = _unique_strings([*product_urls, *discovered])
                    attempts.append(
                        _attempt(
                            ticker,
                            "cdw_search",
                            search_url,
                            "discovered",
                            content_type=content_type,
                            raw_path=str(raw_search_path),
                            discovered_count=len(discovered),
                        )
                    )

        selected_count = 0
        for product_url in product_urls:
            if selected_count >= max(1, int(max_products_per_probe or 1)):
                break
            try:
                status_code, content_type, body = _fetch_with_retries(fetcher, product_url, timeout_s, fetch_retries)
            except Exception as exc:  # noqa: BLE001
                attempts.append(_attempt(ticker, "cdw_product", product_url, "fetch_failed", reason=f"{type(exc).__name__}: {str(exc)[:220]}"))
                continue
            raw_path = raw_dir / f"{ticker.lower()}_cdw_product_{_stable_digest(product_url)}.html"
            raw_path.write_text(body, encoding="utf-8")
            if status_code >= 400 or not body.strip():
                attempts.append(_attempt(ticker, "cdw_product", product_url, "unusable_response", reason=f"http_{status_code}" if status_code else "empty_body", raw_path=str(raw_path)))
                continue
            tag_data = cdw_tag_management_data(body)
            if not cdw_product_matches_probe(body=body, tag_data=tag_data, probe=probe):
                attempts.append(
                    _attempt(
                        ticker,
                        "cdw_product",
                        product_url,
                        "skipped_product_mismatch",
                        raw_path=str(raw_path),
                        product_name=str(tag_data.get("product_name") or ""),
                        product_root_brand_name=str(tag_data.get("product_root_brand_name") or ""),
                    )
                )
                continue

            selected_count += 1
            product_name = str(tag_data.get("product_name") or "").strip()
            repair = _repair_payload(probe=probe, ticker=ticker, product_name=product_name)
            parent_ref = _stable_ref("channel_offer", [ticker, product_url, generated_at[:10]])
            channel_rows = parse_public_web_context_rows(
                ticker=ticker,
                parent_evidence_ref=parent_ref,
                url=product_url,
                source_class="channel_pricing_snapshot",
                repair_type="market_proxy",
                analysis_dimension="product_and_production",
                title=f"{repair['company_name']} channel offer: {product_name or product_url}",
                body=body,
                content_type=content_type or "text/html",
                as_of_datetime=generated_at,
                citation={"url": product_url, "title": product_name or product_url, "provider": "CDW"},
                source_layer_meta=_source_layer_meta(CHANNEL_SOURCE_ID, parser_status="cdw_offer_microdata_parser_pass"),
                claim_boundary=(
                    "Public reseller/channel offer context only; supports listed product, configuration, quoted price, "
                    "and availability/lead-time proxy, not ASP, channel inventory, sell-through, sales, revenue, demand, or market share."
                ),
                authority_boundary="L3 public channel quotation proxy; never exact company metric authority.",
                repair=repair,
                max_rows=4,
            )
            review_rows = parse_public_web_context_rows(
                ticker=ticker,
                parent_evidence_ref=parent_ref,
                url=product_url,
                source_class="platform_review_or_ranking_snapshot",
                repair_type="market_proxy",
                analysis_dimension="product_and_production",
                title=f"{repair['company_name']} platform review: {product_name or product_url}",
                body=body,
                content_type=content_type or "text/html",
                as_of_datetime=generated_at,
                citation={"url": product_url, "title": product_name or product_url, "provider": "CDW"},
                source_layer_meta=_source_layer_meta(REVIEW_SOURCE_ID, parser_status="cdw_review_microdata_parser_pass"),
                claim_boundary=(
                    "Public platform review/rating context only; supports directional customer attention/satisfaction proxy, "
                    "not sales, revenue, retention, TAM, demand, or market share."
                ),
                authority_boundary="L3 platform review proxy; never exact company metric authority.",
                repair=repair,
                max_rows=4,
            )
            parsed_rows = [
                *[row for row in channel_rows if row.get("structured_context_type") == "channel_offer_context"],
                *[row for row in review_rows if row.get("structured_context_type") == "platform_review_ranking_context"],
            ]
            for row in parsed_rows:
                source_id = REVIEW_SOURCE_ID if row.get("structured_context_type") == "platform_review_ranking_context" else CHANNEL_SOURCE_ID
                row["schema_version"] = SCHEMA_VERSION
                row["runtime_source_family"] = "public_source_context"
                row["source_family"] = "live_public_web_context"
                row["source_id"] = source_id
                row["underlying_source_id"] = source_id
                row["provider"] = "cdw"
                row["source_url"] = product_url
                row["raw_path"] = str(raw_path)
                row["context_only"] = True
                row["exact_value_authority"] = False
                row["can_support_company_exact_fact"] = False
                row["allowed_claims"] = _allowed_claims(row)
                row["forbidden_claims"] = [
                    "asp",
                    "channel_inventory",
                    "sell_through",
                    "sales_volume",
                    "revenue",
                    "market_share",
                    "demand_proof",
                ]
                row["channel_provider"] = "CDW"
                row["channel_product_id"] = str(tag_data.get("product_id") or "")
                row["channel_product_name"] = product_name
                row["channel_product_category"] = str(tag_data.get("product_category") or tag_data.get("webclasscode_level1name") or "")
                row["channel_brand_name"] = str(tag_data.get("product_root_brand_name") or tag_data.get("product_brand_name") or "")
            rows.extend(parsed_rows)
            attempts.append(
                _attempt(
                    ticker,
                    "cdw_product",
                    product_url,
                    "materialized" if parsed_rows else "parser_no_rows",
                    raw_path=str(raw_path),
                    product_name=product_name,
                    product_price=str(tag_data.get("product_price") or ""),
                    product_stock_status=str(tag_data.get("product_stock_status") or ""),
                    parsed_row_count=len(parsed_rows),
                    channel_offer_rows=len([row for row in parsed_rows if row.get("structured_context_type") == "channel_offer_context"]),
                    review_rows=len([row for row in parsed_rows if row.get("structured_context_type") == "platform_review_ranking_context"]),
                )
            )

    return {"rows": _dedupe_rows(rows), "attempts": attempts}


def build_channel_offer_coverage_gate(
    *,
    context_rows: list[dict[str, Any]],
    source_layer_rows: list[dict[str, Any]],
    generated_at: str,
) -> dict[str, Any]:
    visible = {
        "product_technology_analyst": context_rows,
        "market_valuation_analyst": context_rows,
        "risk_counterevidence_analyst": [row for row in context_rows if row.get("structured_context_type") == "platform_review_ranking_context"],
    }
    return build_source_coverage_gate(
        industry_schema="consumer_electronics",
        phase="runtime_case",
        case_id="channel_offer_context_backfill_smoke",
        source_layer_capability={"rows": source_layer_rows},
        observed_rows=context_rows,
        specialist_visible_rows=visible,
        required_dimensions=["channel_offer_proxy", "platform_review_proxy"],
        generated_at=generated_at,
    )


def build_summary(
    *,
    rows: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
    coverage_gate: Mapping[str, Any],
    generated_at: str,
    output_rows: Path,
    output_coverage: Path,
) -> dict[str, Any]:
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "pass" if any(row.get("structured_context_type") == "channel_offer_context" for row in rows) else "gap",
        "attempted_count": len(attempts),
        "materialized_count": len([row for row in attempts if row.get("status") == "materialized"]),
        "failed_count": len([row for row in attempts if row.get("status") in {"fetch_failed", "unusable_response"}]),
        "context_row_count": len(rows),
        "parser_backed_row_count": len([row for row in rows if row.get("bounded_structured_context") or row.get("structured_context_type")]),
        "channel_offer_row_count": len([row for row in rows if row.get("structured_context_type") == "channel_offer_context"]),
        "platform_review_row_count": len([row for row in rows if row.get("structured_context_type") == "platform_review_ranking_context"]),
        "ticker_count": len({str(row.get("ticker") or "") for row in rows if str(row.get("ticker") or "")}),
        "tickers": sorted({str(row.get("ticker") or "") for row in rows if str(row.get("ticker") or "")}),
        "source_id_counts": dict(sorted(Counter(str(row.get("source_id") or "") for row in rows).items())),
        "structured_context_type_counts": dict(sorted(Counter(str(row.get("structured_context_type") or "") for row in rows).items())),
        "issuer_binding_status_counts": dict(sorted(Counter(str(row.get("issuer_binding_status") or "") for row in rows).items())),
        "product_binding_status_counts": dict(sorted(Counter(str(row.get("product_binding_status") or "") for row in rows).items())),
        "coverage_gate_status": str(coverage_gate.get("status") or ""),
        "channel_offer_proxy_requirement": _requirement_summary(coverage_gate, "channel_offer_proxy"),
        "platform_review_proxy_requirement": _requirement_summary(coverage_gate, "platform_review_proxy"),
        "outputs": {"rows": str(output_rows), "coverage_gate": str(output_coverage)},
        "boundary": (
            "L3 public channel/review rows support product listing, configuration, price, availability, and review proxy only; "
            "they cannot prove ASP, sell-through, sales, channel inventory, revenue, share, or demand."
        ),
        "major_ecommerce_gap": (
            "Major consumer ecommerce platforms such as Amazon/BestBuy/Walmart commonly returned robot or blocking pages in smoke probes; "
            "CDW public reseller pages are materialized here, while blocked platforms remain source gaps until compliant access is available."
        ),
        "attempts": attempts,
    }


def cdw_search_url(query: str) -> str:
    return f"https://www.cdw.com/search/?key={quote(str(query or '').strip())}"


def extract_cdw_product_links(body: str, *, base_url: str, max_links: int = 8) -> list[str]:
    links = re.findall(r"href=['\"](/product/[^'\"#?]+/\d+)['\"]", body)
    return _unique_strings(urljoin(base_url, link) for link in links)[: max(0, int(max_links or 0))]


def cdw_tag_management_data(body: str) -> dict[str, Any]:
    match = re.search(r"(?is)window\.cdwTagManagementData\s*=\s*(\{.*?\});\s*</script>", body)
    if not match:
        return {}
    try:
        value = ast.literal_eval(match.group(1))
    except (SyntaxError, ValueError):
        return {}
    return dict(value) if isinstance(value, Mapping) else {}


def cdw_product_matches_probe(*, body: str, tag_data: Mapping[str, Any], probe: Mapping[str, Any]) -> bool:
    name_text = str(tag_data.get("product_name") or "").lower()
    brand_text = " ".join(
        [
            str(tag_data.get("product_brand_name") or ""),
            str(tag_data.get("product_root_brand_name") or ""),
        ]
    ).lower()
    identity_parts = [
        name_text,
        brand_text,
        str(tag_data.get("product_category") or ""),
    ]
    identity_text = " ".join(identity_parts).lower()
    fallback_text = " ".join(
        [
            _html_title(body),
            body[:6000],
        ]
    ).lower()
    product_text = name_text or fallback_text
    company_terms = [str(term).strip().lower() for term in [probe.get("company_name"), *(probe.get("company_names") or [])] if str(term).strip()]
    product_terms = [str(term).strip().lower() for term in probe.get("product_terms") or [] if str(term).strip()]
    company_match = any(term in (brand_text or fallback_text) for term in company_terms)
    product_match = not product_terms or any(term in product_text for term in product_terms)
    if company_match and product_match:
        return True
    if company_match and bool(probe.get("allow_brand_only_match")) and not _is_cdw_low_value_accessory_or_protection(name_text):
        return True
    return False


def _is_cdw_low_value_accessory_or_protection(product_name: str) -> bool:
    return bool(
        re.search(
            r"product protection|warranty|service plan|support renewal|memory upgrade|compatible|"
            r"replacement battery|power adapter|cable|mounting kit|license renewal",
            product_name,
            re.IGNORECASE,
        )
    )


def _html_title(body: str) -> str:
    match = re.search(r"(?is)<title[^>]*>(.*?)</title>", body)
    if not match:
        return ""
    return re.sub(r"\s+", " ", re.sub(r"(?is)<[^>]+>", " ", match.group(1))).strip()


def _repair_payload(*, probe: Mapping[str, Any], ticker: str, product_name: str) -> dict[str, Any]:
    company_name = str(probe.get("company_name") or ticker).strip()
    return {
        "repair_id": f"channel_offer_backfill:{ticker.lower()}:{_slug(product_name or probe.get('search_query') or ticker)}",
        "repair_type": "market_proxy",
        "ticker": ticker,
        "company_name": company_name,
        "company_names": _unique_strings([company_name, *(probe.get("company_names") or [])]),
        "product_terms": _unique_strings([*(probe.get("product_terms") or []), product_name]),
        "product_names": _unique_strings([*(probe.get("product_terms") or []), product_name]),
        "metric_leads": ["channel price", "availability", "sku", "configuration", "rating", "review count"],
    }


def _source_layer_meta(source_id: str, *, parser_status: str) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "underlying_source_id": source_id,
        "source_layer_id": "L3",
        "source_layer": "L3",
        "layer_id": "L3",
        "parser_status": parser_status,
        "structured_fact_status": "bounded_context_fact_materialized",
        "evidence_graph_status": "runtime_ready_context",
        "runtime_ready_context": True,
        "can_support_company_exact_fact": False,
    }


def _allowed_claims(row: Mapping[str, Any]) -> list[str]:
    if row.get("structured_context_type") == "platform_review_ranking_context":
        return ["platform_review_ranking_context", "market_proxy_context", "verification_lead"]
    return ["channel_offer_context", "market_proxy_context", "verification_lead"]


def _fetch_url(url: str, timeout_s: float) -> tuple[int, str, str]:
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) FIN-Insight-Agent/0.1 channel-offer-source-backfill",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    try:
        with urlopen(request, timeout=float(timeout_s or 15.0)) as response:  # noqa: S310
            body = response.read().decode("utf-8", errors="replace")
            return int(getattr(response, "status", 200) or 200), str(response.headers.get("Content-Type") or ""), body
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        return int(exc.code or 0), str(exc.headers.get("Content-Type") if exc.headers else ""), body
    except URLError:
        raise


def _fetch_with_retries(fetcher: FetchFunc, url: str, timeout_s: float, retries: int) -> tuple[int, str, str]:
    max_attempts = max(1, int(retries or 0) + 1)
    last_exc: Exception | None = None
    for attempt_index in range(max_attempts):
        try:
            return fetcher(url, timeout_s)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt_index + 1 >= max_attempts:
                break
            time.sleep(min(1.5, 0.25 * (2**attempt_index)))
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("fetch_failed_without_exception")


def _requirement_summary(payload: Mapping[str, Any], requirement_id: str) -> dict[str, Any]:
    for row in payload.get("requirements") or []:
        if isinstance(row, Mapping) and str(row.get("requirement_id") or "") == requirement_id:
            return {
                "status": str(row.get("status") or ""),
                "observed_row_count": int(row.get("observed_row_count") or 0),
                "parser_row_count": int(row.get("parser_row_count") or 0),
                "entity_bound_row_count": int(row.get("entity_bound_row_count") or 0),
                "specialist_visible_row_count": int(row.get("specialist_visible_row_count") or 0),
                "gaps": list(row.get("gaps") or []),
            }
    return {}


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            value = json.loads(line)
            if isinstance(value, Mapping):
                rows.append(dict(value))
    return rows


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _unique_strings(values: Iterable[Any]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def _dedupe_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        key = str(row.get("evidence_ref") or row.get("evidence_id") or "")
        if not key:
            key = hashlib.sha1(json.dumps(row, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def _stable_ref(prefix: str, parts: Iterable[Any]) -> str:
    digest = hashlib.sha1("|".join(str(part or "") for part in parts).encode("utf-8", errors="ignore")).hexdigest()[:16]
    return f"{prefix}:{digest}"


def _stable_digest(text: str) -> str:
    return hashlib.sha1(str(text or "").encode("utf-8", errors="ignore")).hexdigest()[:16]


def _slug(text: Any) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "_", str(text or "").strip()).strip("_").lower()
    return value[:90] or "unknown"


def _attempt(ticker: str, provider: str, url: str, status: str, **extra: Any) -> dict[str, Any]:
    row = {"ticker": ticker, "provider": provider, "url": url, "status": status}
    row.update(extra)
    return row


if __name__ == "__main__":
    raise SystemExit(main())
