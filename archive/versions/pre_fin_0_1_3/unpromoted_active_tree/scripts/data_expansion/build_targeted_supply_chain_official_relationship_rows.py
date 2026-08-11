from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


SCHEMA_VERSION = "finsight_targeted_supply_chain_official_relationship_context_row_v0_1"
ATTEMPT_SCHEMA_VERSION = "finsight_targeted_supply_chain_official_relationship_attempt_v0_1"
SUMMARY_SCHEMA_VERSION = "finsight_targeted_supply_chain_official_relationship_summary_v0_1"

DEFAULT_COMPANY_SOURCE_MATRIX = REPO_ROOT / "data" / "manifests" / "company_public_source_coverage_matrix_v0_1.jsonl"
DEFAULT_OUTPUT_ROWS = REPO_ROOT / "data" / "manifests" / "targeted_supply_chain_official_relationship_context_rows_v0_1.jsonl"
DEFAULT_OUTPUT_ATTEMPTS = REPO_ROOT / "data" / "manifests" / "targeted_supply_chain_official_relationship_attempts_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY = REPO_ROOT / "data" / "manifests" / "targeted_supply_chain_official_relationship_summary_v0_1.json"
DEFAULT_REPORT = REPO_ROOT / "docs" / "internal" / "vnext_20260610" / "vertical_lanes" / "targeted_supply_chain_official_relationship.zh-CN.md"
DEFAULT_RAW_DIR = Path("Z:/FIN_Insight_Agent_data/raw_private/public_source_extended_materialization/targeted_supply_chain_official_relationship")

USER_AGENT = "FIN-Insight-Agent public official relationship resolver"

TARGETED_RELATIONSHIP_SEEDS = {
    "AEHR": [
        {
            "source_url": "https://www.aehr.com/2026/04/aehr-receives-record-41-million-production-order-from-lead-hyperscale-ai-customer-second-half-bookings-exceed-92-million/",
            "issuer_aliases": ["Aehr", "Aehr Test Systems"],
            "counterparty": "Lead hyperscale AI customer",
            "counterparty_aliases": ["lead hyperscale AI customer", "hyperscale AI customer"],
            "relationship_label": "Aehr official production-order relationship with lead hyperscale AI customer",
            "product_or_segment": "FOX-XP / FOX-NP wafer-level test and burn-in systems for AI and semiconductor devices",
        }
    ],
    "1211.HK": [
        {
            "source_url": "https://en.byd.com/news/byd-wins-the-largest-pure-electric-bus-order-in-the-americas/",
            "issuer_aliases": ["BYD"],
            "counterparty": "Bogota public transport operators",
            "counterparty_aliases": ["Bogota", "capital of Colombia", "public transport"],
            "relationship_label": "BYD official electric-bus order relationship in Bogota",
            "product_or_segment": "pure-electric buses / commercial vehicles",
        }
    ],
    "AMKR": [
        {
            "source_url": "https://amkor.com/company-news/lightmatter-and-amkor-partner-to-build-worlds-largest-3d-photonics-package/",
            "issuer_aliases": ["Amkor", "Amkor Technology"],
            "counterparty": "Lightmatter",
            "counterparty_aliases": ["Lightmatter"],
            "relationship_label": "Lightmatter and Amkor official 3D photonics package partnership",
            "product_or_segment": "advanced packaging and photonics supply-chain relationship",
        }
    ],
    "BILL": [
        {
            "source_url": "https://www.bill.com/case-study/customer-success-story-goodie-nation",
            "issuer_aliases": ["BILL"],
            "counterparty": "Goodie Nation",
            "counterparty_aliases": ["Goodie Nation"],
            "relationship_label": "BILL official customer-story relationship with Goodie Nation",
            "product_or_segment": "BILL financial automation / payments platform",
        }
    ],
    "ASML": [
        {
            "source_url": "https://www.asml.com/news/press-releases/2022/intel-and-asml-strengthen-their-collaboration-to-drive-high-na-into-manufacturing-in-2025",
            "issuer_aliases": ["ASML"],
            "counterparty": "Intel",
            "counterparty_aliases": ["Intel"],
            "relationship_label": "Intel and ASML official High-NA EUV collaboration and purchase-order context",
            "product_or_segment": "High-NA EUV lithography systems",
        }
    ],
    "CAMT": [
        {
            "source_url": "https://www.camtek.com/news-and-events/camtek-earns-intels-2025-epic-supplier-award/",
            "issuer_aliases": ["Camtek"],
            "counterparty": "Intel",
            "counterparty_aliases": ["Intel"],
            "relationship_label": "Camtek official Intel EPIC Supplier Award relationship",
            "product_or_segment": "semiconductor inspection and metrology supplier relationship",
        }
    ],
    "CCJ": [
        {
            "source_url": "https://www.cameco.com/media/news/cameco-signs-long-term-uranium-supply-agreement-with-india",
            "issuer_aliases": ["Cameco"],
            "counterparty": "Government of India's Department of Atomic Energy",
            "counterparty_aliases": ["India", "Department of Atomic Energy"],
            "relationship_label": "Cameco official long-term uranium supply agreement with India",
            "product_or_segment": "uranium ore concentrate supply",
        }
    ],
    "CRDO": [
        {
            "source_url": "https://credosemi.com/news/credo-extends-lp-switch-aec-family-to-200g-4x56g-adding-pam4-support-for-hyperscale-data-center-and-telecom-service-providers/",
            "issuer_aliases": ["Credo"],
            "counterparty": "Microsoft",
            "counterparty_aliases": ["Microsoft", "SONIC"],
            "relationship_label": "Credo official SWITCH AEC / Microsoft SONiC solution relationship",
            "product_or_segment": "HiWire SWITCH AEC connectivity for hyperscale data centers",
        }
    ],
    "CSIQ": [
        {
            "source_url": "https://recurrentenergy.com/recurrent-energy-closes-160-million-in-project-financing-secures-microsoft-as-customer-for-127-mw-solar-project-in-louisiana/",
            "issuer_aliases": ["Canadian Solar", "Recurrent Energy"],
            "counterparty": "Microsoft",
            "counterparty_aliases": ["Microsoft"],
            "relationship_label": "Canadian Solar / Recurrent Energy official Microsoft customer relationship for Bayou Galion Solar",
            "product_or_segment": "solar project power purchase / renewable energy credits",
        }
    ],
    "DQ": [
        {
            "source_url": "https://www.dqsolar.com/2021-03-16-Daqo-New-Energy-Announces-Three-Year-High-Purity-Polysilicon-Supply-Agreement-with-Gaojing-Solar",
            "issuer_aliases": ["Daqo New Energy", "Daqo"],
            "counterparty": "Gaojing Solar",
            "counterparty_aliases": ["Gaojing"],
            "relationship_label": "Daqo New Energy official high-purity polysilicon supply agreement with Gaojing Solar",
            "product_or_segment": "high-purity mono-grade polysilicon supply",
        }
    ],
    "DNN": [
        {
            "source_url": "https://denisonmines.com/news/denison-reports-financial-and-operational-results-122847/",
            "issuer_aliases": ["Denison"],
            "counterparty": "North American nuclear power utility customers",
            "counterparty_aliases": ["customers", "North American nuclear power utilities", "contracted sales commitments"],
            "relationship_label": "Denison official sales book / utility customer commitment context",
            "product_or_segment": "uranium sales commitments / physical uranium sales book",
        }
    ],
    "ENLT": [
        {
            "source_url": "https://enlightenergy.com/news-api/nta-and-enlight-sign-a-22m-power-purchase-agreement/",
            "issuer_aliases": ["Enlight"],
            "counterparty": "NTA Metropolitan Mass Transit System",
            "counterparty_aliases": ["NTA", "Metropolitan Mass Transit"],
            "relationship_label": "Enlight official power purchase agreement with NTA",
            "product_or_segment": "renewable electricity power purchase agreement",
        }
    ],
    "ENPH": [
        {
            "source_url": "https://www.nasdaq.com/press-release/enphase-energy-announces-strategic-supply-agreement-with-sunrun-2019-11-18",
            "issuer_aliases": ["Enphase"],
            "counterparty": "Sunrun",
            "counterparty_aliases": ["Sunrun"],
            "relationship_label": "Enphase official strategic supply agreement with Sunrun",
            "product_or_segment": "IQ microinverters / residential solar supply relationship",
        }
    ],
    "FORM": [
        {
            "source_url": "https://www.formfactor.com/blog/2026/formfactor-named-a-2026-intel-epic-supplier-award-winner/",
            "issuer_aliases": ["FormFactor"],
            "counterparty": "Intel",
            "counterparty_aliases": ["Intel"],
            "relationship_label": "FormFactor official Intel EPIC Supplier Award relationship",
            "product_or_segment": "semiconductor test and measurement supplier relationship",
        }
    ],
    "JKS": [
        {
            "source_url": "https://www.jinkosolar.com/en/site/newsdetail/2919",
            "issuer_aliases": ["JinkoSolar", "Jinko Solar"],
            "counterparty": "customer in Bulgaria",
            "counterparty_aliases": ["customer in Bulgaria", "Bulgaria"],
            "relationship_label": "JinkoSolar official Tiger Neo module order relationship in Bulgaria",
            "product_or_segment": "Tiger Neo 3.0 solar modules",
        }
    ],
    "NXT": [
        {
            "source_url": "https://investors.nextracker.com/news/news-details/2022/Silicon-Ranch-and-Nextracker-expand-strategic-partnership-with-master-supply-agreement-for-1-5-GW-of-solar-trackers-05-24-2022/default.aspx",
            "issuer_aliases": ["Nextracker"],
            "counterparty": "Silicon Ranch",
            "counterparty_aliases": ["Silicon Ranch"],
            "relationship_label": "Nextracker official master supply agreement with Silicon Ranch",
            "product_or_segment": "solar trackers / utility-scale solar infrastructure",
        }
    ],
    "OKLO": [
        {
            "source_url": "https://oklo.com/newsroom/news-details/2026/Oklo-Meta-Announce-Agreement-in-Support-of-1-2-GW-Nuclear-Energy-Development-in-Southern-Ohio/default.aspx",
            "issuer_aliases": ["Oklo"],
            "counterparty": "Meta",
            "counterparty_aliases": ["Meta"],
            "relationship_label": "Oklo official nuclear energy development agreement with Meta",
            "product_or_segment": "advanced nuclear power for data center energy demand",
        }
    ],
    "PCAR": [
        {
            "source_url": "https://investors.paccar.com/financial-news/news-details/2023/PACCAR-and-Toyota-Expand-Hydrogen-Fuel-Cell-Truck-Collaboration-to-Include-Commercialization-05-02-2023/default.aspx",
            "issuer_aliases": ["PACCAR"],
            "counterparty": "Toyota",
            "counterparty_aliases": ["Toyota"],
            "relationship_label": "PACCAR official hydrogen fuel-cell truck commercialization collaboration with Toyota",
            "product_or_segment": "Kenworth / Peterbilt hydrogen fuel-cell trucks",
        }
    ],
    "RUN": [
        {
            "source_url": "https://investors.sunrun.com/news-events/press-releases/detail/303/sunrun-and-lowes-partner-to-bring-solar-and-storage-to",
            "issuer_aliases": ["Sunrun"],
            "counterparty": "Lowe's",
            "counterparty_aliases": ["Lowe", "Lowes"],
            "relationship_label": "Sunrun official partnership relationship with Lowe's",
            "product_or_segment": "residential solar and storage channel partnership",
        }
    ],
    "SEDG": [
        {
            "source_url": "https://investors.solaredge.com/news-releases/news-release-details/solaredge-and-summit-ridge-collaborate-deploy-solaredges?mobile=1",
            "issuer_aliases": ["SolarEdge"],
            "counterparty": "Summit Ridge Energy",
            "counterparty_aliases": ["Summit Ridge"],
            "relationship_label": "SolarEdge official collaboration with Summit Ridge Energy",
            "product_or_segment": "SolarEdge Power Optimizers / community solar deployments",
        }
    ],
    "SHOP": [
        {
            "source_url": "https://www.shopify.com/case-studies/allbirds",
            "issuer_aliases": ["Shopify"],
            "counterparty": "Allbirds",
            "counterparty_aliases": ["Allbirds"],
            "relationship_label": "Shopify official customer-story relationship with Allbirds",
            "product_or_segment": "Shopify POS / unified commerce platform",
        }
    ],
    "SMR": [
        {
            "source_url": "https://www.nuscalepower.com/press-releases/2025/nuscale-proudly-supports-tva-and-entra1-energy-announcement-of-landmark-6-gigawatt-small-module-reactor-smr-deployment-program",
            "issuer_aliases": ["NuScale"],
            "counterparty": "TVA and ENTRA1 Energy",
            "counterparty_aliases": ["TVA", "ENTRA1"],
            "relationship_label": "NuScale official support for TVA / ENTRA1 SMR deployment program",
            "product_or_segment": "NuScale SMR technology deployment program",
        }
    ],
    "2317.TW": [
        {
            "source_url": "https://nvidianews.nvidia.com/news/foxconn-builds-ai-factory-in-partnership-with-taiwan-and-nvidia",
            "issuer_aliases": ["Foxconn", "Hon Hai", "Hon Hai Technology Group"],
            "counterparty": "NVIDIA",
            "counterparty_aliases": ["NVIDIA"],
            "relationship_label": "NVIDIA and Foxconn / Hon Hai AI factory partnership",
            "product_or_segment": "AI factory / AI server manufacturing relationship",
        }
    ],
    "2382.TW": [
        {
            "source_url": "https://www.nvidia.com/en-us/data-center/products/certified-systems/",
            "issuer_aliases": ["Quanta", "Quanta Computer", "Quanta Cloud Technology", "QCT"],
            "counterparty": "NVIDIA",
            "counterparty_aliases": ["NVIDIA"],
            "relationship_label": "NVIDIA-Certified Systems page identifies QCT and Quanta Computer parent relationship",
            "product_or_segment": "NVIDIA-certified systems / QCT data center systems",
        }
    ],
    "3231.TW": [
        {
            "source_url": "https://blogs.nvidia.com/blog/nvidia-manufacture-american-made-ai-supercomputers-us/",
            "issuer_aliases": ["Wistron"],
            "counterparty": "NVIDIA",
            "counterparty_aliases": ["NVIDIA"],
            "relationship_label": "NVIDIA official blog names Wistron in US AI supercomputer manufacturing plan",
            "product_or_segment": "AI supercomputer manufacturing relationship",
        }
    ],
    "8035.T": [
        {
            "source_url": "https://www.tel.com/news/topics/2025/20250409_001.html",
            "issuer_aliases": ["Tokyo Electron", "TEL"],
            "counterparty": "Intel",
            "counterparty_aliases": ["Intel"],
            "relationship_label": "Tokyo Electron official Intel EPIC Supplier Award relationship",
            "product_or_segment": "semiconductor equipment supplier relationship",
        }
    ],
    "SMCI": [
        {
            "source_url": "https://nvidianews.nvidia.com/news/computer-industry-ai-factories-data-centers",
            "issuer_aliases": ["Supermicro", "Super Micro"],
            "counterparty": "NVIDIA",
            "counterparty_aliases": ["NVIDIA"],
            "relationship_label": "NVIDIA official AI factory systems relationship naming Supermicro",
            "product_or_segment": "AI systems using NVIDIA GPUs and networking",
        }
    ],
    "UROY": [
        {
            "source_url": "https://www.uraniumroyalty.com/news/uranium-royalty-corp-enters-into-strategic-supply-stream-with-cgn-global",
            "issuer_aliases": ["Uranium Royalty"],
            "counterparty": "CGN Global Uranium",
            "counterparty_aliases": ["CGN Global"],
            "relationship_label": "Uranium Royalty official supply stream agreement with CGN Global",
            "product_or_segment": "uranium supply stream / physical uranium exposure",
        }
    ],
    "6752.T": [
        {
            "source_url": "https://news.panasonic.com/global/press/en251125-2",
            "issuer_aliases": ["Panasonic"],
            "counterparty": "Zoox",
            "counterparty_aliases": ["Zoox"],
            "relationship_label": "Panasonic Energy official lithium-ion battery supply agreement with Zoox",
            "product_or_segment": "cylindrical lithium-ion batteries for robotaxi fleets",
        }
    ],
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build targeted official supply-chain relationship context rows.")
    parser.add_argument("--company-source-matrix", type=Path, default=DEFAULT_COMPANY_SOURCE_MATRIX)
    parser.add_argument("--output-rows", type=Path, default=DEFAULT_OUTPUT_ROWS)
    parser.add_argument("--output-attempts", type=Path, default=DEFAULT_OUTPUT_ATTEMPTS)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--output-report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--tickers", nargs="*", default=[])
    parser.add_argument("--timeout-s", type=float, default=15.0)
    parser.add_argument("--sleep-s", type=float, default=0.1)
    parser.add_argument("--replace-output", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at = _utc_now()
    matrix_rows = _load_jsonl(args.company_source_matrix)
    result = build_targeted_supply_chain_official_relationship_rows(
        matrix_rows=matrix_rows,
        generated_at=generated_at,
        tickers=args.tickers,
        raw_dir=args.raw_dir,
        timeout_s=args.timeout_s,
        sleep_s=args.sleep_s,
    )
    output_rows = result["rows"] if args.replace_output else _dedupe_rows([*result["rows"], *_load_jsonl(args.output_rows)])
    output_attempts = result["attempts"] if args.replace_output else _dedupe_attempts(
        [*_load_jsonl(args.output_attempts), *result["attempts"]]
    )
    summary = build_summary(
        rows=output_rows,
        attempts=output_attempts,
        matrix_rows=matrix_rows,
        generated_at=generated_at,
        output_rows=args.output_rows,
        output_attempts=args.output_attempts,
        output_report=args.output_report,
    )
    _write_jsonl(args.output_rows, output_rows)
    _write_jsonl(args.output_attempts, output_attempts)
    _write_json(args.output_summary, summary)
    args.output_report.parent.mkdir(parents=True, exist_ok=True)
    args.output_report.write_text(render_report(summary), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if args.strict and result["targeted_gap_ticker_count"] and not result["rows"]:
        return 1
    return 0


def build_targeted_supply_chain_official_relationship_rows(
    *,
    matrix_rows: Iterable[Mapping[str, Any]],
    generated_at: str,
    raw_dir: Path,
    tickers: Iterable[str] = (),
    timeout_s: float = 15.0,
    sleep_s: float = 0.1,
) -> dict[str, Any]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    ticker_filter = {str(ticker).strip().upper() for ticker in tickers if str(ticker).strip()}
    relationship_gap_tickers = _official_relationship_gap_tickers(matrix_rows)
    target_tickers = sorted((relationship_gap_tickers & set(TARGETED_RELATIONSHIP_SEEDS)) | ticker_filter)
    rows: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []
    for ticker in target_tickers:
        for seed in TARGETED_RELATIONSHIP_SEEDS.get(ticker, []):
            result = _process_seed(ticker, seed, generated_at=generated_at, raw_dir=raw_dir, timeout_s=timeout_s)
            rows.extend(result["rows"])
            attempts.extend(result["attempts"])
            if sleep_s:
                time.sleep(sleep_s)
    return {
        "rows": _dedupe_rows(rows),
        "attempts": _dedupe_attempts(attempts),
        "targeted_gap_ticker_count": len(target_tickers),
    }


def _process_seed(
    ticker: str,
    seed: Mapping[str, Any],
    *,
    generated_at: str,
    raw_dir: Path,
    timeout_s: float,
) -> dict[str, list[dict[str, Any]]]:
    source_url = str(seed.get("source_url") or "").strip()
    status, body, reason = _fetch_text(source_url, timeout_s=timeout_s)
    raw_path = raw_dir / f"{_slug(ticker)}_{_stable_digest(source_url)}.html"
    raw_path.write_text(body or "", encoding="utf-8", errors="ignore")
    if status != "ok":
        return {
            "rows": [],
            "attempts": [_attempt(ticker, source_url, status=status, raw_path=raw_path, reason=reason)],
        }
    text = _html_to_text(body)
    issuer_ok = _any_alias_in_text(text, seed.get("issuer_aliases") or [])
    counterparty_ok = _any_alias_in_text(text, seed.get("counterparty_aliases") or [])
    if not issuer_ok or not counterparty_ok:
        return {
            "rows": [],
            "attempts": [
                _attempt(
                    ticker,
                    source_url,
                    status="official_page_missing_required_aliases",
                    raw_path=raw_path,
                    reason=f"issuer_ok={issuer_ok}; counterparty_ok={counterparty_ok}",
                )
            ],
        }
    return {
        "rows": [_relationship_row(ticker, seed, generated_at=generated_at, source_text=text)],
        "attempts": [_attempt(ticker, source_url, status="materialized", raw_path=raw_path, reason="")],
    }


def _relationship_row(
    ticker: str,
    seed: Mapping[str, Any],
    *,
    generated_at: str,
    source_text: str,
) -> dict[str, Any]:
    source_url = str(seed.get("source_url") or "").strip()
    counterparty = str(seed.get("counterparty") or "").strip()
    product_or_segment = str(seed.get("product_or_segment") or "official supply-chain relationship").strip()
    fact_label = str(seed.get("relationship_label") or f"{ticker} official relationship with {counterparty}").strip()
    evidence_ref = _stable_ref("targeted_supply_chain_official_relationship", [ticker, source_url, fact_label])
    preview = _snippet(source_text, seed.get("issuer_aliases") or [], seed.get("counterparty_aliases") or [])
    event_type = _event_type(f"{fact_label} {product_or_segment}")
    event_date = _event_date(source_url, preview)
    event_scale_text = _event_scale_text(f"{fact_label} {product_or_segment} {preview}")
    return {
        "schema_version": SCHEMA_VERSION,
        "evidence_ref": evidence_ref,
        "evidence_id": evidence_ref,
        "source_id": "supplier_customer_official_news",
        "underlying_source_id": "supplier_customer_official_news",
        "source_class": "supplier_customer_official_news",
        "source_family": "public_source_context",
        "runtime_source_family": "public_source_context",
        "source_layer_id": "L2",
        "source_layer": "L2",
        "layer_id": "L2",
        "source_specific_parser": "targeted_official_supply_chain_relationship_page_parser_v0_1",
        "source_specific_resolver": "targeted_official_relationship_alias_resolver_v0_1",
        "parser_status": "source_specific_context_parser_pass",
        "structured_fact_status": "bounded_context_fact_materialized",
        "runtime_ready_context": True,
        "bounded_structured_context": True,
        "structured_context_type": "official_supply_chain_relationship_context",
        "requirement_id": "supply_chain_official_relationship",
        "source_role": "official_customer_order_or_deployment_event" if event_type else "supply_chain_official_relationship",
        "ticker": ticker,
        "source_url": source_url,
        "citation": {"url": source_url, "record_id": evidence_ref, "title": fact_label},
        "counterparty": counterparty,
        "fact_label": fact_label,
        "relationship_label": fact_label,
        "event_type": event_type,
        "event_date": event_date,
        "event_scale_text": event_scale_text,
        "product_or_segment": product_or_segment,
        "product_family": product_or_segment,
        "period": event_date or generated_at[:10],
        "as_of_datetime": generated_at,
        "issuer_binding_status": "issuer_mentioned_in_snapshot",
        "product_binding_status": "product_mentioned_in_snapshot",
        "counterparty_binding_status": "counterparty_mentioned_in_snapshot",
        "entity_binding": {
            "issuer_ticker": ticker,
            "issuer_binding_status": "issuer_mentioned_in_snapshot",
            "product_binding_status": "product_mentioned_in_snapshot",
            "counterparty_binding_status": "counterparty_mentioned_in_snapshot",
            "counterparty_matched_terms": [counterparty],
            "resolver_status": "issuer_counterparty_official_relationship_bound",
            "binding_claim_boundary": "Official relationship/order/deployment event context only; no revenue, backlog, shipment, ASP, sell-through, or market-share inference.",
        },
        "resolver_status": "issuer_counterparty_official_relationship_bound",
        "context_only": True,
        "exact_value_authority": False,
        "can_support_company_exact_fact": False,
        "allowed_claims": [
            "official_supply_chain_relationship_context",
            "official_customer_order_or_deployment_event",
            "customer_deployment_signal",
            "demand_proxy_context",
            "verification_lead",
        ],
        "forbidden_claims": ["total_orders", "backlog", "revenue", "shipment_volume", "market_share", "asp", "sell_through"],
        "claim_boundary": (
            "Official supplier/customer/partner relationship or customer order/deployment event context only. "
            "Event fields can support bounded thesis-driver analysis when issuer/counterparty/product/date/scale are cited, "
            "but cannot be promoted to revenue, backlog, shipments, ASP, sell-through, or share."
        ),
        "text": preview,
        "preview": preview,
    }


def _event_type(text: str) -> str:
    normalized = _normalize(text)
    event_rules = [
        ("customer_order", ("order", "purchase order", "production order")),
        ("customer_agreement", ("agreement", "contract", "supply agreement", "master supply agreement")),
        ("customer_deployment", ("deployment", "deploy", "deployed")),
        ("project_or_program", ("project", "program", "power purchase", "ppa")),
        ("customer_story", ("case study", "customer story")),
        ("production_or_manufacturing_plan", ("manufacturing", "factory", "production")),
        ("partnership_or_collaboration", ("partnership", "collaboration", "partner")),
        ("supplier_award", ("supplier award", "supplier relationship")),
    ]
    for event_type, tokens in event_rules:
        if any(token in normalized for token in tokens):
            return event_type
    return ""


def _event_date(url: str, text: str) -> str:
    for value in (url, text):
        match = re.search(r"\b(20\d{2})[-/](0?[1-9]|1[0-2])[-/](0?[1-9]|[12]\d|3[01])\b", value or "")
        if match:
            return f"{match.group(1)}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
        match = re.search(r"\b(20\d{2})[-/](0?[1-9]|1[0-2])\b", value or "")
        if match:
            return f"{match.group(1)}-{int(match.group(2)):02d}"
        match = re.search(
            r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+"
            r"([0-3]?\d),\s*(20\d{2})\b",
            value or "",
            flags=re.IGNORECASE,
        )
        if match:
            month_names = {
                "january": 1,
                "february": 2,
                "march": 3,
                "april": 4,
                "may": 5,
                "june": 6,
                "july": 7,
                "august": 8,
                "september": 9,
                "october": 10,
                "november": 11,
                "december": 12,
            }
            return f"{match.group(3)}-{month_names[match.group(1).lower()]:02d}-{int(match.group(2)):02d}"
    return ""


def _event_scale_text(text: str) -> str:
    patterns = [
        r"\$?\b\d+(?:\.\d+)?\s*(?:million|billion|m|bn)\b",
        r"\b\d+(?:\.\d+)?\s*(?:GW|MW|kW|GWh|MWh)\b",
        r"\b\d+(?:,\d{3})*\s*(?:GPUs?|systems?|servers?|buses?|modules?|trackers?|vehicles?|square feet)\b",
        r"\b\d+(?:\.\d+)?\s*(?:gigawatt|megawatt)s?\b",
    ]
    matches: list[str] = []
    for pattern in patterns:
        matches.extend(match.group(0).strip() for match in re.finditer(pattern, text or "", flags=re.IGNORECASE))
    deduped = []
    seen = set()
    for item in matches:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return "; ".join(deduped[:5])


def build_summary(
    *,
    rows: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
    matrix_rows: list[dict[str, Any]],
    generated_at: str,
    output_rows: Path,
    output_attempts: Path,
    output_report: Path,
) -> dict[str, Any]:
    relationship_gap_tickers = _official_relationship_gap_tickers(matrix_rows)
    success_tickers = {str(row.get("ticker") or "").upper() for row in rows if row.get("ticker")}
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "pass" if rows else "gap",
        "targeted_gap_ticker_count": len(relationship_gap_tickers & set(TARGETED_RELATIONSHIP_SEEDS)),
        "row_count": len(rows),
        "attempt_count": len(attempts),
        "success_ticker_count": len(success_tickers),
        "remaining_targeted_gap_tickers": sorted((relationship_gap_tickers & set(TARGETED_RELATIONSHIP_SEEDS)) - success_tickers),
        "row_tickers": sorted(success_tickers),
        "attempt_status_counts": dict(sorted(Counter(str(row.get("status") or "") for row in attempts).items())),
        "outputs": {"rows": str(output_rows), "attempts": str(output_attempts), "report": str(output_report)},
        "boundary": "Targeted official relationship rows are L2/L3 supply-chain context only and cannot prove shipment, allocation, order volume, revenue, or share.",
    }


def render_report(summary: Mapping[str, Any]) -> str:
    return "\n".join(
        [
            "# Targeted Supply Chain Official Relationship Rows",
            "",
            f"- generated_at: `{summary.get('generated_at')}`",
            f"- status: `{summary.get('status')}`",
            f"- targeted_gap_ticker_count: `{summary.get('targeted_gap_ticker_count')}`",
            f"- row_count: `{summary.get('row_count')}`",
            f"- success_ticker_count: `{summary.get('success_ticker_count')}`",
            f"- remaining_targeted_gap_tickers: `{', '.join(summary.get('remaining_targeted_gap_tickers') or [])}`",
            "",
            "## Boundary",
            "",
            str(summary.get("boundary") or ""),
            "",
        ]
    )


def _official_relationship_gap_tickers(matrix_rows: Iterable[Mapping[str, Any]]) -> set[str]:
    out: set[str] = set()
    target_requirements = {"supply_chain_official_relationship", "public_order_proxy"}
    for row in matrix_rows:
        ticker = str(row.get("ticker") or "").upper()
        for req in row.get("source_role_matrix") or []:
            if (
                isinstance(req, Mapping)
                and req.get("requirement_id") in target_requirements
                and req.get("status") != "pass"
            ):
                out.add(ticker)
    return out


def _supply_chain_gap_tickers(matrix_rows: Iterable[Mapping[str, Any]]) -> set[str]:
    return _official_relationship_gap_tickers(matrix_rows)


def _fetch_text(url: str, *, timeout_s: float) -> tuple[str, str, str]:
    try:
        request = Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36 "
                    f"{USER_AGENT}"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Connection": "close",
            },
        )
        with urlopen(request, timeout=timeout_s) as response:
            body = response.read().decode("utf-8", errors="ignore")
            if response.status >= 400:
                return f"http_{response.status}", body, f"http_{response.status}"
            return "ok", body, ""
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore") if exc.fp else ""
        return f"http_{exc.code or 0}", body, f"HTTPError:{exc.code}"
    except (URLError, TimeoutError) as exc:
        return "fetch_failed", "", f"{type(exc).__name__}:{str(exc)[:220]}"
    except Exception as exc:  # noqa: BLE001
        return "fetch_failed", "", f"{type(exc).__name__}:{str(exc)[:220]}"


def _attempt(ticker: str, source_url: str, *, status: str, raw_path: Path, reason: str) -> dict[str, Any]:
    return {
        "schema_version": ATTEMPT_SCHEMA_VERSION,
        "generated_at": _utc_now(),
        "attempt_id": _stable_ref("targeted_supply_chain_official_relationship_attempt", [ticker, source_url, status, reason]),
        "ticker": ticker,
        "source_id": "supplier_customer_official_news",
        "source_url": source_url,
        "status": status,
        "raw_path": str(raw_path),
        "reason": reason,
    }


def _html_to_text(value: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", value or "")
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _any_alias_in_text(text: str, aliases: Iterable[str]) -> bool:
    norm = _normalize(text)
    return any(_normalize(alias) in norm for alias in aliases if _normalize(alias))


def _snippet(text: str, issuer_aliases: Iterable[str], counterparty_aliases: Iterable[str]) -> str:
    terms = [*issuer_aliases, *counterparty_aliases]
    lower = text.lower()
    positions = [lower.find(str(term).lower()) for term in terms if str(term).strip() and lower.find(str(term).lower()) >= 0]
    start = max(0, min(positions) - 220) if positions else 0
    return text[start : start + 700].strip()


def _normalize(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", " ", str(value or "").lower())
    return re.sub(r"\s+", " ", text).strip()


def _stable_ref(prefix: str, parts: Iterable[Any]) -> str:
    digest = _stable_digest("::".join(str(part) for part in parts))
    return f"{prefix}:{digest}"


def _stable_digest(value: str) -> str:
    return hashlib.sha1(str(value).encode("utf-8", errors="ignore")).hexdigest()[:16]


def _slug(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "_", str(value or "").strip()).strip("_").lower()
    return text[:80] or "empty"


def _dedupe_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        key = str(row.get("evidence_ref") or row.get("evidence_id") or json.dumps(dict(row), sort_keys=True))
        if key in seen:
            continue
        seen.add(key)
        out.append(dict(row))
    return out


def _dedupe_attempts(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        key = str(row.get("attempt_id") or json.dumps(dict(row), sort_keys=True))
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
            if text:
                rows.append(json.loads(text))
    return rows


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
