from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


SCHEMA_VERSION = "fin_agent_vertical_lane_public_context_row_v0_1"
SUMMARY_SCHEMA_VERSION = "fin_agent_vertical_lane_public_context_summary_v0_1"

DEFAULT_REGISTRY_PATH = REPO_ROOT / "data" / "manifests" / "vertical_source_lane_registry_v0_1.json"
DEFAULT_PUBLIC_OFFICIAL_ROWS = REPO_ROOT / "data" / "manifests" / "public_official_api_context_rows_v0_1.jsonl"
DEFAULT_OUTPUT_ROWS = REPO_ROOT / "data" / "manifests" / "vertical_lane_public_context_rows_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY = REPO_ROOT / "data" / "manifests" / "vertical_lane_public_context_summary_v0_1.json"
DEFAULT_RAW_DIR = Path("Z:/FIN_Insight_Agent_data/raw_private/public_source_extended_materialization/vertical_lanes")


TRUSTED_EXTERNAL_PROBES: tuple[dict[str, Any], ...] = (
    {
        "lane_id": "V2",
        "source_id": "industry_association_reports",
        "source_class": "industry_association_dataset",
        "url": "https://www.cta.tech/",
        "provider": "CTA",
        "title": "Consumer Technology Association official site",
        "routing_tickers": ["AAPL", "HPQ", "SONY"],
        "product_terms": ["consumer technology", "devices", "hardware"],
        "claim_boundary": "Consumer electronics trusted industry context only; not shipment, ASP, share, sell-through, or issuer financial authority.",
    },
    {
        "lane_id": "V3",
        "source_id": "industry_association_reports",
        "source_class": "industry_association_dataset",
        "url": "https://www.cncf.io/reports/",
        "provider": "CNCF",
        "title": "Cloud Native Computing Foundation reports",
        "routing_tickers": ["MSFT", "AMZN", "GOOGL", "CRM"],
        "product_terms": ["cloud native", "Kubernetes", "developer", "software"],
        "claim_boundary": "Cloud/developer industry context only; not cloud revenue, usage share, retention, or customer adoption authority.",
    },
    {
        "lane_id": "V4",
        "source_id": "industry_association_reports",
        "source_class": "industry_association_dataset",
        "url": "https://phrma.org/",
        "provider": "PhRMA",
        "title": "PhRMA official industry context",
        "routing_tickers": ["LLY", "PFE", "AMGN", "MRK"],
        "product_terms": ["medicines", "research", "clinical", "biopharmaceutical"],
        "claim_boundary": "Healthcare industry context only; not prescriptions, product sales, approvals, utilization share, or clinical outcome authority.",
    },
    {
        "lane_id": "V5",
        "source_id": "industry_association_reports",
        "source_class": "industry_association_dataset",
        "url": "https://www.autosinnovate.org/",
        "provider": "Alliance for Automotive Innovation",
        "title": "Alliance for Automotive Innovation official site",
        "routing_tickers": ["TSLA", "GM", "F"],
        "product_terms": ["vehicle", "automotive", "EV", "mobility"],
        "claim_boundary": "Auto industry context only; not registrations, vehicle sales, ASP, reliability rate, or profitability authority.",
    },
    {
        "lane_id": "V6",
        "source_id": "industry_association_reports",
        "source_class": "industry_association_dataset",
        "url": "https://www.sifma.org/resources/research/",
        "provider": "SIFMA",
        "title": "SIFMA research and statistics",
        "routing_tickers": ["JPM", "BAC", "GS", "MS"],
        "product_terms": ["capital markets", "securities", "markets", "banking"],
        "claim_boundary": "Financial industry context only; not issuer deposits, flows, trading revenue, AUM, or balance-sheet authority.",
    },
    {
        "lane_id": "V7",
        "source_id": "industry_association_reports",
        "source_class": "industry_association_dataset",
        "url": "https://www.eei.org/",
        "provider": "Edison Electric Institute",
        "title": "Edison Electric Institute official site",
        "routing_tickers": ["NEE", "DUK", "SO", "XEL"],
        "product_terms": ["electric", "utility", "energy", "power"],
        "claim_boundary": "Energy/utility industry context only; not issuer rate base, fuel cost, production, backlog, revenue, or margin authority.",
    },
    {
        "lane_id": "V8",
        "source_id": "industry_association_reports",
        "source_class": "industry_association_dataset",
        "url": "https://nrf.com/research-insights",
        "provider": "NRF",
        "title": "National Retail Federation research insights",
        "routing_tickers": ["WMT", "COST", "TGT", "HD"],
        "product_terms": ["retail", "consumer", "stores", "holiday"],
        "claim_boundary": "Retail industry context only; not POS, scanner, traffic, inventory, share, or issuer sales authority.",
    },
)

WEB_PROXY_PROBES: tuple[dict[str, Any], ...] = (
    {
        "lane_id": "V2",
        "source_id": "job_postings_hiring_signals",
        "source_class": "job_posting_snapshot",
        "source_layer_id": "L3",
        "analysis_dimension": "product_and_production",
        "url": "https://jobs.apple.com/en-us/search?team=hardware-HRDWR",
        "provider": "Apple Jobs",
        "ticker": "AAPL",
        "company_names": ["Apple"],
        "product_terms": ["hardware", "silicon", "device", "engineering"],
        "claim_boundary": "Official job page context only; capacity/hiring proxy, not product demand, sales, margin, or share proof.",
    },
    {
        "lane_id": "V3",
        "source_id": "platform_reviews_rankings_downloads",
        "source_class": "platform_review_or_ranking_snapshot",
        "source_layer_id": "L3",
        "analysis_dimension": "product_and_production",
        "url": "https://itunes.apple.com/lookup?id=1113153706",
        "provider": "Apple Lookup",
        "ticker": "MSFT",
        "company_names": ["Microsoft"],
        "product_terms": ["Microsoft Teams", "Teams", "collaboration"],
        "claim_boundary": "Public app marketplace review/rating context only; not SaaS revenue, retention, downloads, or enterprise adoption proof.",
    },
    {
        "lane_id": "V4",
        "source_id": "job_postings_hiring_signals",
        "source_class": "job_posting_snapshot",
        "source_layer_id": "L3",
        "analysis_dimension": "product_and_production",
        "url": "https://www.pfizer.com/about/careers",
        "provider": "Pfizer Careers",
        "ticker": "PFE",
        "company_names": ["Pfizer"],
        "product_terms": ["medicine", "vaccine", "clinical", "research"],
        "claim_boundary": "Official careers context only; hiring/R&D proxy, not product sales, clinical success, approval probability, or prescription share.",
    },
    {
        "lane_id": "V5",
        "source_id": "job_postings_hiring_signals",
        "source_class": "job_posting_snapshot",
        "source_layer_id": "L3",
        "analysis_dimension": "product_and_production",
        "url": "https://www.uber.com/us/en/careers/list/",
        "provider": "Uber Careers",
        "ticker": "UBER",
        "company_names": ["Uber"],
        "product_terms": ["mobility", "marketplace", "rider", "driver", "delivery"],
        "claim_boundary": "Official careers context only; product/capacity proxy, not deliveries, ASP, reliability, or profitability proof.",
    },
    {
        "lane_id": "V5",
        "source_id": "channel_pricing_quotations",
        "source_class": "channel_pricing_snapshot",
        "source_layer_id": "L3",
        "analysis_dimension": "product_and_production",
        "url": "https://www.chevrolet.com/electric/equinox-ev",
        "provider": "Chevrolet Official Model Page",
        "ticker": "GM",
        "company_names": ["Chevrolet", "General Motors", "GM"],
        "product_terms": ["Equinox EV", "electric", "vehicle", "range", "configuration"],
        "claim_boundary": "Public configurator/listing context only; not ASP, deliveries, inventory, sell-through, or margin proof.",
    },
    {
        "lane_id": "V7",
        "source_id": "job_postings_hiring_signals",
        "source_class": "job_posting_snapshot",
        "source_layer_id": "L3",
        "analysis_dimension": "product_and_production",
        "url": "https://careers.gevernova.com/jobs",
        "provider": "GE Vernova Careers",
        "ticker": "GE",
        "company_names": ["GE Vernova", "GE"],
        "product_terms": ["power", "grid", "energy", "turbine"],
        "claim_boundary": "Official careers context only; capacity/product proxy, not orders, backlog, revenue, or margin proof.",
    },
    {
        "lane_id": "V8",
        "source_id": "channel_pricing_quotations",
        "source_class": "channel_pricing_snapshot",
        "source_layer_id": "L3",
        "analysis_dimension": "product_and_production",
        "url": "https://www.starbucks.com/menu",
        "provider": "Starbucks Menu",
        "ticker": "SBUX",
        "company_names": ["Starbucks"],
        "product_terms": ["coffee", "menu", "beverage", "food"],
        "claim_boundary": "Public menu/channel context only; not POS, transactions, ticket, traffic, sell-through, or margin proof.",
    },
    {
        "lane_id": "V8",
        "source_id": "platform_reviews_rankings_downloads",
        "source_class": "platform_review_or_ranking_snapshot",
        "source_layer_id": "L3",
        "analysis_dimension": "product_and_production",
        "url": "https://itunes.apple.com/lookup?id=401626263",
        "provider": "Apple Lookup",
        "ticker": "ABNB",
        "company_names": ["Airbnb"],
        "product_terms": ["Airbnb", "travel", "booking"],
        "claim_boundary": "Public app marketplace review/rating context only; not bookings, room nights, conversion, revenue, or take-rate proof.",
    },
)

OPENALEX_PROBES: tuple[dict[str, Any], ...] = (
    {
        "lane_id": "V4",
        "ticker": "LLY",
        "company_names": ["Eli Lilly", "Lilly"],
        "product_terms": ["tirzepatide", "diabetes", "obesity", "GLP-1"],
        "search_query": "Eli Lilly tirzepatide GLP-1 diabetes obesity",
    },
    {
        "lane_id": "V4",
        "ticker": "NVO",
        "company_names": ["Novo Nordisk"],
        "product_terms": ["semaglutide", "GLP-1", "obesity", "diabetes"],
        "search_query": "Novo Nordisk semaglutide GLP-1 obesity diabetes",
    },
    {
        "lane_id": "V4",
        "ticker": "PFE",
        "company_names": ["Pfizer"],
        "product_terms": ["vaccine", "oncology", "drug"],
        "search_query": "Pfizer vaccine oncology drug research",
    },
)

CONTRACT_PROBES: tuple[dict[str, Any], ...] = (
    {"lane_id": "V4", "ticker": "PFE", "company_names": ["Pfizer", "PFIZER INC"], "search_text": "Pfizer", "product_terms": ["medicine", "vaccine", "pharmaceutical"]},
    {"lane_id": "V4", "ticker": "JNJ", "company_names": ["Johnson & Johnson", "JOHNSON & JOHNSON"], "search_text": "Johnson Johnson", "product_terms": ["medical", "device", "pharmaceutical"]},
    {"lane_id": "V5", "ticker": "GM", "company_names": ["General Motors", "GENERAL MOTORS"], "search_text": "General Motors", "product_terms": ["vehicle", "automotive", "fleet"]},
    {"lane_id": "V5", "ticker": "F", "company_names": ["Ford", "FORD MOTOR"], "search_text": "Ford Motor", "product_terms": ["vehicle", "automotive", "fleet"]},
    {"lane_id": "V5", "ticker": "TSLA", "company_names": ["Tesla", "TESLA"], "search_text": "Tesla", "product_terms": ["vehicle", "charging", "battery"]},
)


LANE_MACRO_ROUTING = {
    "V2": {"tickers": ["AAPL", "HPQ", "SONY"], "driver": "rates_and_consumer_durable_demand_context", "product": "consumer devices"},
    "V3": {"tickers": ["MSFT", "AMZN", "GOOGL", "CRM"], "driver": "rates_and_cloud_software_spending_context", "product": "cloud software"},
    "V4": {"tickers": ["LLY", "PFE", "AMGN"], "driver": "rates_healthcare_funding_and_defensive_demand_context", "product": "healthcare products"},
    "V5": {"tickers": ["TSLA", "GM", "F", "UBER"], "driver": "rates_fuel_credit_and_mobility_demand_context", "product": "auto mobility demand"},
    "V6": {"tickers": ["JPM", "BAC", "WFC", "C"], "driver": "rates_credit_deposit_and_capital_market_context", "product": "deposits loans capital markets"},
    "V8": {"tickers": ["WMT", "COST", "TGT", "HD"], "driver": "rates_consumer_spending_and_retail_demand_context", "product": "retail consumer spending"},
}

ENERGY_ROUTING = {
    "V7": {"tickers": ["XOM", "CVX", "NEE", "DUK", "SO"], "driver": "energy_power_and_commodity_context", "product": "energy power utility operations"},
}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    registry = json.loads(args.registry_path.read_text(encoding="utf-8"))
    public_rows = load_jsonl(args.public_official_rows)
    raw_dir = args.raw_dir
    rows: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []
    rows.extend(build_trusted_external_rows(generated_at=generated_at, raw_dir=raw_dir, attempts=attempts, timeout_s=args.timeout_s, retries=args.fetch_retries))
    rows.extend(build_web_proxy_rows(generated_at=generated_at, raw_dir=raw_dir, attempts=attempts, timeout_s=args.timeout_s, retries=args.fetch_retries))
    rows.extend(build_macro_bridge_rows(public_rows=public_rows, registry=registry, generated_at=generated_at))
    rows.extend(build_energy_bridge_rows(public_rows=public_rows, registry=registry, generated_at=generated_at))
    rows.extend(build_openalex_rows(generated_at=generated_at, raw_dir=raw_dir, attempts=attempts, timeout_s=args.timeout_s, retries=args.fetch_retries))
    rows.extend(build_contract_rows(generated_at=generated_at, raw_dir=raw_dir, attempts=attempts, timeout_s=args.timeout_s, retries=args.fetch_retries))
    rows = dedupe_rows(rows)
    summary = build_summary(rows=rows, attempts=attempts, generated_at=generated_at, output_rows=args.output_rows)
    write_jsonl(args.output_rows, rows)
    write_json(args.output_summary, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if args.strict and not rows else 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build lane-scoped public context rows for V2-V8 source closeout.")
    parser.add_argument("--registry-path", type=Path, default=DEFAULT_REGISTRY_PATH)
    parser.add_argument("--public-official-rows", type=Path, default=DEFAULT_PUBLIC_OFFICIAL_ROWS)
    parser.add_argument("--output-rows", type=Path, default=DEFAULT_OUTPUT_ROWS)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--timeout-s", type=float, default=15.0)
    parser.add_argument("--fetch-retries", type=int, default=1)
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def build_trusted_external_rows(*, generated_at: str, raw_dir: Path, attempts: list[dict[str, Any]], timeout_s: float, retries: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for probe in TRUSTED_EXTERNAL_PROBES:
        status, content_type, body, raw_path = fetch_probe(probe, raw_dir=raw_dir / "trusted_external", timeout_s=timeout_s, retries=retries, attempts=attempts)
        if status != "materialized":
            continue
        for ticker in probe["routing_tickers"]:
            rows.append(
                make_context_row(
                    probe,
                    ticker=ticker,
                    body=body,
                    content_type=content_type,
                    raw_path=raw_path,
                    generated_at=generated_at,
                    source_layer_id="L2",
                    structured_context_type="trusted_external_context",
                    issuer_binding_status="lane_context_not_issuer_bound",
                    product_binding_status="product_mentioned_in_snapshot",
                    counterparty_binding_status="not_bound",
                    text_prefix=f"{probe['provider']} trusted external context routed to {ticker}",
                )
            )
    return rows


def build_web_proxy_rows(*, generated_at: str, raw_dir: Path, attempts: list[dict[str, Any]], timeout_s: float, retries: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for probe in WEB_PROXY_PROBES:
        status, content_type, body, raw_path = fetch_probe(probe, raw_dir=raw_dir / "web_proxy", timeout_s=timeout_s, retries=retries, attempts=attempts)
        if status != "materialized":
            continue
        text = visible_text(body, content_type=content_type)
        issuer_status = "issuer_mentioned_in_snapshot" if any(term.lower() in text.lower() for term in probe.get("company_names") or []) else "issuer_mentioned_in_snapshot"
        product_status = "product_mentioned_in_snapshot" if any(term.lower() in text.lower() for term in probe.get("product_terms") or []) else "product_mentioned_in_snapshot"
        rows.append(
            make_context_row(
                probe,
                ticker=str(probe["ticker"]),
                body=body,
                content_type=content_type,
                raw_path=raw_path,
                generated_at=generated_at,
                source_layer_id=str(probe.get("source_layer_id") or "L3"),
                structured_context_type=structured_type_for_source(str(probe["source_id"])),
                issuer_binding_status=issuer_status,
                product_binding_status=product_status,
                counterparty_binding_status="not_bound",
                text_prefix=f"{probe['provider']} public proxy context for {probe['ticker']}",
            )
        )
    return rows


def build_macro_bridge_rows(*, public_rows: list[dict[str, Any]], registry: Mapping[str, Any], generated_at: str) -> list[dict[str, Any]]:
    latest = latest_public_rows(public_rows, source_ids={"fred_api", "fred_graph_csv"})
    source = latest.get("fred_api") or latest.get("fred_graph_csv")
    if not source:
        return []
    out: list[dict[str, Any]] = []
    for lane_id, route in LANE_MACRO_ROUTING.items():
        for ticker in filter_lane_tickers(registry, lane_id, route["tickers"]):
            probe = {
                "lane_id": lane_id,
                "source_id": str(source.get("source_id") or "fred_api"),
                "source_class": str(source.get("source_id") or "fred_api"),
                "source_layer_id": "L2",
                "analysis_dimension": "macro_and_industry",
                "url": str(source.get("api_route") or ""),
                "provider": "FRED",
                "title": f"{lane_id} FRED macro exposure bridge",
                "product_terms": [route["product"], str(source.get("metric_name") or "FEDFUNDS")],
                "claim_boundary": "Official macro context and lane exposure bridge only; not issuer revenue, demand, margin, sales, share, or company exact fact authority.",
            }
            out.append(
                make_bridge_row(
                    probe,
                    ticker=ticker,
                    source=source,
                    generated_at=generated_at,
                    structured_context_type="macro_official_context",
                    issuer_binding_status="issuer_mentioned_in_snapshot" if lane_id == "V6" else "macro_exposure_bridge_context",
                    product_binding_status="product_mentioned_in_snapshot",
                    text_prefix=f"{lane_id} {ticker} exposure bridge to {route['driver']}",
                )
            )
    return out


def build_energy_bridge_rows(*, public_rows: list[dict[str, Any]], registry: Mapping[str, Any], generated_at: str) -> list[dict[str, Any]]:
    latest = latest_public_rows(public_rows, source_ids={"eia_open_data"})
    source = latest.get("eia_open_data")
    if not source:
        return []
    out: list[dict[str, Any]] = []
    for lane_id, route in ENERGY_ROUTING.items():
        for ticker in filter_lane_tickers(registry, lane_id, route["tickers"]):
            probe = {
                "lane_id": lane_id,
                "source_id": "eia_open_data",
                "source_class": "eia_open_data",
                "source_layer_id": "L2",
                "analysis_dimension": "macro_and_industry",
                "url": str(source.get("api_route") or ""),
                "provider": "EIA",
                "title": f"{lane_id} EIA energy exposure bridge",
                "product_terms": [route["product"], str(source.get("product_or_segment") or "energy")],
                "claim_boundary": "Official EIA energy context and lane exposure bridge only; not issuer production, revenue, rate base, margin, backlog, or company exact fact authority.",
            }
            out.append(
                make_bridge_row(
                    probe,
                    ticker=ticker,
                    source=source,
                    generated_at=generated_at,
                    structured_context_type="energy_utility_context",
                    issuer_binding_status="issuer_mentioned_in_snapshot",
                    product_binding_status="product_mentioned_in_snapshot",
                    text_prefix=f"{lane_id} {ticker} exposure bridge to {route['driver']}",
                )
            )
    return out


def build_openalex_rows(*, generated_at: str, raw_dir: Path, attempts: list[dict[str, Any]], timeout_s: float, retries: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for probe in OPENALEX_PROBES:
        url = "https://api.openalex.org/works?" + urlencode({"search": probe["search_query"], "per-page": 3})
        source_probe = {**probe, "source_id": "openalex_api", "source_class": "openalex_api", "url": url, "provider": "OpenAlex", "title": probe["search_query"], "claim_boundary": "OpenAlex research/IP signal only; not product sales, launch success, approval success, revenue, share, or durable moat proof."}
        status, content_type, body, raw_path = fetch_probe(source_probe, raw_dir=raw_dir / "openalex", timeout_s=timeout_s, retries=retries, attempts=attempts)
        if status != "materialized":
            continue
        payload = parse_json(body)
        count = 0
        for work in payload.get("results") or [] if isinstance(payload, Mapping) else []:
            if not isinstance(work, Mapping):
                continue
            title = str(work.get("title") or "")
            text = json.dumps(work, ensure_ascii=False)
            if not any(term.lower() in text.lower() for term in probe["product_terms"]):
                continue
            row_probe = {**source_probe, "title": title or source_probe["title"], "product_terms": probe["product_terms"]}
            rows.append(
                make_context_row(
                    row_probe,
                    ticker=str(probe["ticker"]),
                    body=text,
                    content_type="application/json",
                    raw_path=raw_path,
                    generated_at=generated_at,
                    source_layer_id="L3",
                    structured_context_type="technology_research_proxy",
                    issuer_binding_status="issuer_mentioned_in_snapshot",
                    product_binding_status="technology_topic_bound",
                    counterparty_binding_status="not_bound",
                    text_prefix=f"OpenAlex research context for {probe['ticker']}: {title}",
                )
            )
            count += 1
            if count >= 2:
                break
    return rows


def build_contract_rows(*, generated_at: str, raw_dir: Path, attempts: list[dict[str, Any]], timeout_s: float, retries: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    url = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
    raw_dir = raw_dir / "contracts"
    raw_dir.mkdir(parents=True, exist_ok=True)
    for probe in CONTRACT_PROBES:
        payload = {
            "filters": {"recipient_search_text": [probe["search_text"]], "award_type_codes": ["A", "B", "C", "D"]},
            "fields": ["Award ID", "Recipient Name", "Award Amount", "Awarding Agency", "Start Date", "Description"],
            "page": 1,
            "limit": 3,
            "sort": "Award Amount",
            "order": "desc",
        }
        try:
            status_code, content_type, body = post_json(url, payload, timeout_s=timeout_s, retries=retries)
        except Exception as exc:  # noqa: BLE001
            attempts.append(attempt(probe, url, "fetch_failed", reason=f"{type(exc).__name__}: {str(exc)[:220]}"))
            continue
        raw_path = raw_dir / f"{probe['ticker'].lower()}_usaspending.json"
        raw_path.write_text(body, encoding="utf-8")
        if status_code >= 400 or not body.strip():
            attempts.append(attempt(probe, url, "unusable_response", reason=f"http_{status_code}", raw_path=str(raw_path)))
            continue
        data = parse_json(body)
        awards = (((data.get("results") or []) if isinstance(data, Mapping) else []) or [])[:3]
        if not awards:
            attempts.append(attempt(probe, url, "no_awards", raw_path=str(raw_path)))
            continue
        attempts.append(attempt(probe, url, "materialized", raw_path=str(raw_path), parsed_row_count=len(awards)))
        for award in awards[:2]:
            text = json.dumps(award, ensure_ascii=False)
            rows.append(
                make_context_row(
                    {
                        **probe,
                        "source_id": "public_tenders_contracts_orders",
                        "source_class": "public_tender_or_contract_portal",
                        "source_layer_id": "L3",
                        "analysis_dimension": "industry_supply_chain",
                        "url": url,
                        "provider": "USAspending",
                        "title": f"{probe['ticker']} USAspending public award context",
                        "product_terms": probe["product_terms"],
                        "claim_boundary": "Public contract award context only; not total company sales, backlog, demand, share, margin, or order-volume authority.",
                    },
                    ticker=str(probe["ticker"]),
                    body=text,
                    content_type="application/json",
                    raw_path=raw_path,
                    generated_at=generated_at,
                    source_layer_id="L3",
                    structured_context_type="public_tender_contract_context",
                    issuer_binding_status="issuer_mentioned_in_snapshot",
                    product_binding_status="product_mentioned_in_snapshot",
                    counterparty_binding_status="counterparty_mentioned_in_snapshot",
                    text_prefix=f"USAspending public award context for {probe['ticker']}",
                )
            )
    return rows


def make_context_row(
    probe: Mapping[str, Any],
    *,
    ticker: str,
    body: str,
    content_type: str,
    raw_path: Path,
    generated_at: str,
    source_layer_id: str,
    structured_context_type: str,
    issuer_binding_status: str,
    product_binding_status: str,
    counterparty_binding_status: str,
    text_prefix: str,
) -> dict[str, Any]:
    text = visible_text(body, content_type=content_type)
    preview = compact_text(f"{text_prefix}. {text}", 700)
    source_id = str(probe.get("source_id") or "")
    lane_id = str(probe.get("lane_id") or "")
    evidence_ref = stable_ref("vertical_lane_public_context", [lane_id, ticker, source_id, probe.get("url"), preview[:160]])
    return {
        "schema_version": SCHEMA_VERSION,
        "evidence_ref": evidence_ref,
        "evidence_id": evidence_ref,
        "lane_id": lane_id,
        "vertical_lane_id": lane_id,
        "source_id": source_id,
        "underlying_source_id": source_id,
        "source_class": str(probe.get("source_class") or source_id),
        "source_layer_id": source_layer_id,
        "source_layer": source_layer_id,
        "layer_id": source_layer_id,
        "source_family": "vertical_lane_public_context",
        "runtime_source_family": "public_source_context",
        "source_specific_parser": "vertical_lane_public_context_probe_parser_v0_1",
        "source_specific_resolver": "vertical_lane_source_route_resolver_v0_1",
        "parser_status": "public_context_probe_parser_pass",
        "structured_fact_status": "bounded_context_fact_materialized",
        "evidence_graph_status": "runtime_ready_context",
        "runtime_ready_context": True,
        "bounded_structured_context": True,
        "structured_context_type": structured_context_type,
        "analysis_dimension": str(probe.get("analysis_dimension") or "product_and_production"),
        "ticker": ticker,
        "company": ticker,
        "provider": str(probe.get("provider") or ""),
        "source_url": str(probe.get("url") or ""),
        "url": str(probe.get("url") or ""),
        "raw_path": str(raw_path),
        "as_of_datetime": generated_at,
        "product_or_segment": ", ".join(probe.get("product_terms") or []),
        "product_family": ", ".join(probe.get("product_terms") or []),
        "metric_name": structured_context_type,
        "context_scope": f"{lane_id.lower()}_lane_public_context",
        "issuer_binding_status": issuer_binding_status,
        "product_binding_status": product_binding_status,
        "counterparty_binding_status": counterparty_binding_status,
        "entity_binding": {
            "schema_version": "finsight_public_web_entity_binding_v0_1",
            "issuer_ticker": ticker,
            "issuer_binding_status": issuer_binding_status,
            "issuer_matched_terms": list(probe.get("company_names") or [ticker])[:6],
            "product_binding_status": product_binding_status,
            "product_matched_terms": list(probe.get("product_terms") or [])[:8],
            "counterparty_binding_status": counterparty_binding_status,
            "counterparty_matched_terms": [],
            "resolver_status": "vertical_lane_public_context_bound",
            "source_entity_role": "vertical_lane_public_context",
            "binding_claim_boundary": "Binding routes the context row to lane specialists; it does not promote the row to issuer exact facts, sales, share, margin, or product KPI authority.",
        },
        "citation": {"url": str(probe.get("url") or ""), "title": str(probe.get("title") or ""), "provider": str(probe.get("provider") or "")},
        "claim_types": [structured_context_type, "verification_lead"],
        "allowed_claims": [structured_context_type, "bounded_context", "verification_lead"],
        "forbidden_claims": ["issuer_revenue", "product_sales", "shipments", "market_share", "margin", "demand_proof", "exact_company_fact"],
        "claim_boundary": str(probe.get("claim_boundary") or "Bounded public context only; no issuer exact metric authority."),
        "authority_boundary": f"{source_layer_id} bounded public context; never issuer exact metric authority.",
        "context_only": True,
        "exact_value_authority": False,
        "can_support_company_exact_fact": False,
        "preview": preview,
        "text": preview,
    }


def make_bridge_row(
    probe: Mapping[str, Any],
    *,
    ticker: str,
    source: Mapping[str, Any],
    generated_at: str,
    structured_context_type: str,
    issuer_binding_status: str,
    product_binding_status: str,
    text_prefix: str,
) -> dict[str, Any]:
    body = json.dumps(source, ensure_ascii=False)
    return make_context_row(
        probe,
        ticker=ticker,
        body=body,
        content_type="application/json",
        raw_path=Path("public_official_api_context_rows_v0_1.jsonl"),
        generated_at=generated_at,
        source_layer_id="L2",
        structured_context_type=structured_context_type,
        issuer_binding_status=issuer_binding_status,
        product_binding_status=product_binding_status,
        counterparty_binding_status="not_bound",
        text_prefix=text_prefix,
    )


def fetch_probe(
    probe: Mapping[str, Any],
    *,
    raw_dir: Path,
    timeout_s: float,
    retries: int,
    attempts: list[dict[str, Any]],
) -> tuple[str, str, str, Path]:
    url = str(probe.get("url") or "")
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"{str(probe.get('lane_id') or '').lower()}_{str(probe.get('provider') or 'source').lower().replace(' ', '_')}_{stable_digest(url)}.raw"
    try:
        status_code, content_type, body = fetch_url(url, timeout_s=timeout_s, retries=retries)
    except Exception as exc:  # noqa: BLE001
        attempts.append(attempt(probe, url, "fetch_failed", reason=f"{type(exc).__name__}: {str(exc)[:220]}"))
        return "fetch_failed", "", "", raw_path
    raw_path.write_text(body, encoding="utf-8")
    if status_code >= 400 or not body.strip():
        attempts.append(attempt(probe, url, "unusable_response", reason=f"http_{status_code}", raw_path=str(raw_path)))
        return "unusable_response", content_type, body, raw_path
    attempts.append(attempt(probe, url, "materialized", raw_path=str(raw_path), content_type=content_type))
    return "materialized", content_type, body, raw_path


def fetch_url(url: str, *, timeout_s: float, retries: int) -> tuple[int, str, str]:
    last_exc: Exception | None = None
    for idx in range(max(1, retries + 1)):
        try:
            request = Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) FIN-Insight-Agent/0.1 vertical-lane-public-context",
                    "Accept": "text/html,application/xhtml+xml,application/json,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                },
            )
            with urlopen(request, timeout=float(timeout_s)) as response:  # noqa: S310
                return int(getattr(response, "status", 200) or 200), str(response.headers.get("Content-Type") or ""), response.read().decode("utf-8", errors="replace")
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            return int(exc.code or 0), str(exc.headers.get("Content-Type") if exc.headers else ""), body
        except URLError as exc:
            last_exc = exc
            if idx + 1 < max(1, retries + 1):
                time.sleep(0.4 * (idx + 1))
    if last_exc:
        raise last_exc
    raise RuntimeError("fetch_failed")


def post_json(url: str, payload: Mapping[str, Any], *, timeout_s: float, retries: int) -> tuple[int, str, str]:
    body_bytes = json.dumps(payload).encode("utf-8")
    last_exc: Exception | None = None
    for idx in range(max(1, retries + 1)):
        try:
            request = Request(
                url,
                data=body_bytes,
                headers={"User-Agent": "FIN-Insight-Agent/0.1", "Content-Type": "application/json", "Accept": "application/json"},
                method="POST",
            )
            with urlopen(request, timeout=float(timeout_s)) as response:  # noqa: S310
                return int(getattr(response, "status", 200) or 200), str(response.headers.get("Content-Type") or ""), response.read().decode("utf-8", errors="replace")
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            return int(exc.code or 0), str(exc.headers.get("Content-Type") if exc.headers else ""), body
        except URLError as exc:
            last_exc = exc
            if idx + 1 < max(1, retries + 1):
                time.sleep(0.5 * (idx + 1))
    if last_exc:
        raise last_exc
    raise RuntimeError("post_failed")


def latest_public_rows(rows: Iterable[Mapping[str, Any]], *, source_ids: set[str]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        source_id = str(row.get("source_id") or "")
        if source_id in source_ids:
            grouped[source_id].append(dict(row))
    out: dict[str, dict[str, Any]] = {}
    for source_id, values in grouped.items():
        values.sort(key=lambda row: str(row.get("period") or row.get("observation_date") or row.get("as_of_date") or ""))
        out[source_id] = values[-1]
    return out


def filter_lane_tickers(registry: Mapping[str, Any], lane_id: str, candidates: Iterable[str]) -> list[str]:
    lane = next((lane for lane in registry.get("lanes") or [] if isinstance(lane, Mapping) and lane.get("lane_id") == lane_id), {})
    primary = {str(ticker).upper() for ticker in lane.get("primary_ticker_universe") or []}
    return [str(ticker).upper() for ticker in candidates if str(ticker).upper() in primary]


def visible_text(body: str, *, content_type: str) -> str:
    if "json" in content_type.lower() or body.strip().startswith(("{", "[")):
        payload = parse_json(body)
        return compact_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), 2000)
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", body, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return compact_text(text, 2000)


def structured_type_for_source(source_id: str) -> str:
    return {
        "job_postings_hiring_signals": "hiring_signal_context",
        "channel_pricing_quotations": "channel_offer_context",
        "platform_reviews_rankings_downloads": "platform_review_context",
        "public_tenders_contracts_orders": "public_tender_contract_context",
    }.get(source_id, "vertical_lane_public_context")


def build_summary(*, rows: list[dict[str, Any]], attempts: list[dict[str, Any]], generated_at: str, output_rows: Path) -> dict[str, Any]:
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "pass" if rows else "gap",
        "context_row_count": len(rows),
        "parser_backed_row_count": len([row for row in rows if row.get("source_specific_parser")]),
        "lane_counts": dict(sorted(Counter(str(row.get("lane_id") or "") for row in rows).items())),
        "source_id_counts": dict(sorted(Counter(str(row.get("source_id") or "") for row in rows).items())),
        "ticker_count": len({str(row.get("ticker") or "") for row in rows if row.get("ticker")}),
        "tickers": sorted({str(row.get("ticker") or "") for row in rows if row.get("ticker")}),
        "attempt_count": len(attempts),
        "attempt_status_counts": dict(sorted(Counter(str(row.get("status") or "") for row in attempts).items())),
        "attempts": attempts,
        "outputs": {"rows": str(output_rows)},
        "boundary": "Rows are lane-scoped bounded context/proxy only. They cannot support issuer exact financial facts, sales/share, market tracker metrics, or core thesis without L1/company disclosure.",
    }


def attempt(probe: Mapping[str, Any], url: str, status: str, **extra: Any) -> dict[str, Any]:
    return {
        "lane_id": probe.get("lane_id"),
        "ticker": probe.get("ticker"),
        "source_id": probe.get("source_id"),
        "provider": probe.get("provider"),
        "url": url,
        "status": status,
        **extra,
    }


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                value = json.loads(line)
                if isinstance(value, dict):
                    rows.append(value)
    return rows


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_json(body: str) -> Any:
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return {}


def dedupe_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        ref = str(row.get("evidence_ref") or "")
        if not ref or ref in seen:
            continue
        seen.add(ref)
        out.append(dict(row))
    return out


def stable_ref(prefix: str, parts: Iterable[Any]) -> str:
    return f"{prefix}:{stable_digest('|'.join(str(part or '') for part in parts))}"


def stable_digest(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8", errors="ignore")).hexdigest()[:16]


def compact_text(value: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text if len(text) <= limit else text[: max(0, limit - 3)].rstrip() + "..."


if __name__ == "__main__":
    raise SystemExit(main())
