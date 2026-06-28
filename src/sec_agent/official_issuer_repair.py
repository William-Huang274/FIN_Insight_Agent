from __future__ import annotations

import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from sec_agent.public_web_context_parser import parse_public_web_context_rows


SCHEMA_VERSION = "finsight_public_web_gap_repair_execution_v0_2"

FetchFunc = Callable[[str], tuple[int, str, str]]

REPAIR_ROUTE_TYPES: dict[str, str] = {
    "official_issuer_disclosure_repair": "issuer_official",
    "official_product_surface_repair": "product_surface",
    "official_local_filing_repair": "local_filing",
    "public_market_proxy_repair": "market_proxy",
    "capital_ownership_repair": "capital_ownership",
    "official_supply_chain_repair": "supply_chain",
}
PUBLIC_WEB_REPAIR_SOURCE_CLASSES: dict[str, set[str]] = {
    "issuer_official": {
        "sec_fpi_filings",
        "company_ir",
        "company_ir_material",
        "local_exchange_filings",
        "regulator_filings",
        "government_dataset_endpoint",
    },
    "product_surface": {
        "company_product_page",
        "company_product_documentation",
        "company_ir_material",
        "company_support_documentation",
        "official_app_store_or_marketplace",
    },
    "local_filing": {
        "sec_fpi_filings",
        "company_ir",
        "company_ir_material",
        "local_exchange_filings",
        "regulator_filings",
        "government_dataset_endpoint",
    },
    "market_proxy": {
        "mainstream_financial_news_article",
        "official_statistics_dataset",
        "government_dataset_endpoint",
        "industry_association_dataset",
        "official_market_share_snapshot",
        "public_market_proxy_snapshot",
        "official_app_store_or_marketplace",
        "ecommerce_major_platform",
        "developer_ecosystem_snapshot",
        "public_tender_or_contract_portal",
        "job_posting_snapshot",
        "channel_pricing_snapshot",
        "platform_review_or_ranking_snapshot",
    },
    "capital_ownership": {
        "sec_ownership_filing",
        "sec_offering_filing",
        "sec_company_submissions",
        "company_ir_material",
        "regulator_filings",
    },
    "supply_chain": {
        "company_customer_page",
        "company_supplier_page",
        "supplier_customer_official_news",
        "company_ir_material",
        "official_partner_directory",
        "industry_association_dataset",
    },
}
DISALLOWED_WEB_DOMAINS = {
    "x.com",
    "twitter.com",
    "reddit.com",
    "facebook.com",
    "instagram.com",
    "tiktok.com",
    "medium.com",
    "substack.com",
}
DISALLOWED_DOMAIN_MARKERS = ("blog", "forum", "reddit", "x.com", "twitter", "facebook", "instagram", "tiktok")
TRUSTED_NEWS_DOMAINS = {
    "reuters.com",
    "www.reuters.com",
    "ft.com",
    "www.ft.com",
    "wsj.com",
    "www.wsj.com",
    "nytimes.com",
    "www.nytimes.com",
    "nikkei.com",
    "asia.nikkei.com",
    "apnews.com",
    "www.apnews.com",
    "cnbc.com",
    "www.cnbc.com",
    "marketwatch.com",
    "www.marketwatch.com",
    "caixin.com",
    "www.caixin.com",
    "xinhuanet.com",
    "www.xinhuanet.com",
}


ISSUER_PROFILES: dict[str, dict[str, Any]] = {
    "ASML": {
        "ticker": "ASML",
        "company_name": "ASML Holding N.V.",
        "cik": "0000937966",
        "company_domains": ["asml.com", "www.asml.com"],
        "company_ir_urls": [
            "https://www.asml.com/en/investors/financial-results",
            "https://www.asml.com/en/investors/annual-report",
        ],
        "official_product_urls": [
            "https://www.asml.com/en/products",
            "https://www.asml.com/en/products/euv-lithography-systems",
        ],
        "official_product_surfaces": [
            "EUV lithography systems",
            "DUV lithography systems",
            "Installed Base Management",
        ],
        "official_metric_leads": ["net bookings", "backlog", "systems revenue", "installed base management sales"],
    },
    "TSM": {
        "ticker": "TSM",
        "company_name": "Taiwan Semiconductor Manufacturing Company Limited",
        "cik": "0001046179",
        "company_domains": ["tsmc.com", "www.tsmc.com"],
        "company_ir_urls": ["https://investor.tsmc.com/english/quarterly-results"],
        "official_product_urls": ["https://www.tsmc.com/english/dedicatedFoundry/technology"],
        "official_product_surfaces": ["advanced logic process technologies", "specialty technologies", "advanced packaging"],
        "official_metric_leads": ["capital expenditures", "wafer revenue", "capacity", "technology platform revenue"],
    },
    "NVO": {
        "ticker": "NVO",
        "company_name": "Novo Nordisk A/S",
        "cik": "0000353278",
        "company_domains": ["novonordisk.com", "www.novonordisk.com"],
        "company_ir_urls": ["https://www.novonordisk.com/investors/financial-results.html"],
        "official_product_urls": ["https://www.novonordisk.com/our-products.html"],
        "official_product_surfaces": ["GLP-1 diabetes care", "obesity care", "rare disease medicines"],
        "official_metric_leads": ["sales growth", "volume growth", "pipeline progress"],
    },
    "MSFT": {
        "ticker": "MSFT",
        "company_name": "Microsoft Corporation",
        "cik": "0000789019",
        "company_domains": ["microsoft.com", "www.microsoft.com", "azure.microsoft.com"],
        "official_product_urls": [
            "https://azure.microsoft.com/en-us/products/",
            "https://www.microsoft.com/en-us/microsoft-365",
        ],
        "official_product_surfaces": ["Azure", "Microsoft 365", "Copilot", "Windows"],
        "official_metric_leads": ["cloud revenue", "commercial bookings", "remaining performance obligation"],
    },
    "AMZN": {
        "ticker": "AMZN",
        "company_name": "Amazon.com, Inc.",
        "cik": "0001018724",
        "company_domains": ["amazon.com", "www.amazon.com", "aws.amazon.com"],
        "official_product_urls": [
            "https://aws.amazon.com/products/",
            "https://aws.amazon.com/ec2/instance-types/",
        ],
        "official_product_surfaces": ["AWS", "EC2", "AI services", "retail marketplace"],
        "official_metric_leads": ["AWS revenue", "operating income", "capital expenditures"],
    },
    "GOOGL": {
        "ticker": "GOOGL",
        "company_name": "Alphabet Inc.",
        "cik": "0001652044",
        "company_domains": ["google.com", "www.google.com", "cloud.google.com", "abc.xyz"],
        "official_product_urls": [
            "https://cloud.google.com/products",
            "https://cloud.google.com/ai",
        ],
        "official_product_surfaces": ["Google Cloud", "Vertex AI", "Search", "YouTube"],
        "official_metric_leads": ["Google Cloud revenue", "capex", "traffic acquisition costs"],
    },
    "TSLA": {
        "ticker": "TSLA",
        "company_name": "Tesla, Inc.",
        "cik": "0001318605",
        "company_domains": ["tesla.com", "www.tesla.com"],
        "official_product_urls": [
            "https://www.tesla.com/models",
            "https://www.tesla.com/modely",
        ],
        "official_product_surfaces": ["Model S", "Model 3", "Model X", "Model Y", "Cybertruck"],
        "official_metric_leads": ["vehicle deliveries", "automotive revenue", "energy generation and storage"],
    },
    "LLY": {
        "ticker": "LLY",
        "company_name": "Eli Lilly and Company",
        "cik": "0000059478",
        "company_domains": ["lilly.com", "www.lilly.com"],
        "official_product_urls": ["https://www.lilly.com/our-medicines"],
        "official_product_surfaces": ["diabetes medicines", "obesity medicines", "oncology medicines", "immunology medicines"],
        "official_metric_leads": ["product revenue", "volume growth", "pipeline progress"],
    },
    "PFE": {
        "ticker": "PFE",
        "company_name": "Pfizer Inc.",
        "cik": "0000078003",
        "company_domains": ["pfizer.com", "www.pfizer.com"],
        "official_product_urls": ["https://www.pfizer.com/products"],
        "official_product_surfaces": ["vaccines", "oncology", "internal medicine", "rare disease"],
        "official_metric_leads": ["product revenue", "pipeline progress", "clinical milestones"],
    },
    "CRM": {
        "ticker": "CRM",
        "company_name": "Salesforce, Inc.",
        "cik": "0001108524",
        "company_domains": ["salesforce.com", "www.salesforce.com"],
        "official_product_urls": ["https://www.salesforce.com/products/"],
        "official_product_surfaces": ["Sales Cloud", "Service Cloud", "Data Cloud", "Agentforce"],
        "official_metric_leads": ["subscription and support revenue", "remaining performance obligation"],
    },
    "NOW": {
        "ticker": "NOW",
        "company_name": "ServiceNow, Inc.",
        "cik": "0001373715",
        "company_domains": ["servicenow.com", "www.servicenow.com"],
        "official_product_urls": ["https://www.servicenow.com/products-by-category.html"],
        "official_product_surfaces": ["IT Service Management", "Customer Service Management", "AI Platform"],
        "official_metric_leads": ["subscription revenue", "current remaining performance obligations"],
    },
    "AVGO": {
        "ticker": "AVGO",
        "company_name": "Broadcom Inc.",
        "cik": "0001730168",
        "company_domains": ["broadcom.com", "www.broadcom.com"],
        "official_product_urls": ["https://www.broadcom.com/products"],
        "official_product_surfaces": ["semiconductor solutions", "infrastructure software", "networking products"],
        "official_metric_leads": ["semiconductor solutions revenue", "infrastructure software revenue"],
    },
    "INTC": {
        "ticker": "INTC",
        "company_name": "Intel Corporation",
        "cik": "0000050863",
        "company_domains": ["intel.com", "www.intel.com"],
        "official_product_urls": ["https://www.intel.com/content/www/us/en/products/overview.html"],
        "official_product_surfaces": ["Intel Core processors", "Xeon processors", "foundry", "AI accelerators"],
        "official_metric_leads": ["client computing revenue", "data center revenue", "foundry revenue"],
    },
    "QCOM": {
        "ticker": "QCOM",
        "company_name": "QUALCOMM Incorporated",
        "cik": "0000804328",
        "company_domains": ["qualcomm.com", "www.qualcomm.com"],
        "official_product_urls": ["https://www.qualcomm.com/products"],
        "official_product_surfaces": ["Snapdragon", "automotive platforms", "modem-RF systems", "IoT platforms"],
        "official_metric_leads": ["handsets revenue", "automotive revenue", "IoT revenue"],
    },
}


def issuer_has_official_profile(ticker: str) -> bool:
    return str(ticker or "").strip().upper() in ISSUER_PROFILES


def known_official_issuer_profiles() -> dict[str, dict[str, Any]]:
    return {ticker: dict(profile) for ticker, profile in ISSUER_PROFILES.items()}


def _repair_type(repair: Mapping[str, Any]) -> str:
    explicit = str(repair.get("repair_type") or "").strip()
    if explicit in set(REPAIR_ROUTE_TYPES.values()):
        return explicit
    return REPAIR_ROUTE_TYPES.get(str(repair.get("route") or ""), "issuer_official")


def _repair_probes(profile: Mapping[str, Any], repair: Mapping[str, Any]) -> list[dict[str, Any]]:
    repair_type = _repair_type(repair)
    if repair_type == "product_surface":
        probes = _product_surface_probes(profile, repair)
    elif repair_type == "capital_ownership":
        probes = _capital_ownership_probes(profile, repair)
    elif repair_type == "market_proxy":
        probes = _market_proxy_probes(profile, repair)
    elif repair_type == "supply_chain":
        probes = _supply_chain_probes(profile, repair)
    elif repair_type == "local_filing":
        probes = [*_issuer_probes(profile, repair), *_explicit_url_probes(repair, source_class="local_exchange_filings")]
    else:
        probes = _issuer_probes(profile, repair)
    return [*probes, *_explicit_url_probes(repair)]


def _product_surface_probes(profile: Mapping[str, Any], repair: Mapping[str, Any]) -> list[dict[str, Any]]:
    ticker = str(profile.get("ticker") or repair.get("ticker") or "").strip().upper()
    urls = _unique_strings([*list(profile.get("official_product_urls") or []), *list(repair.get("official_product_urls") or [])])
    if not urls:
        urls = _unique_strings(profile.get("company_ir_urls") or repair.get("company_ir_urls") or [])
    return [
        {
            "probe_id": f"{ticker.lower()}_product_surface_{index}",
            "url": url,
            "source_class": "company_product_page" if "investor" not in url.lower() and "investors" not in url.lower() else "company_ir_material",
            "web_scope_policy_ids": ["official_product_surface_only"],
            "claim_types": ["official_product_surface", "product_taxonomy_context", "product_spec_context", "verification_lead"],
            "source_title": f"{ticker} official product surface",
            "company_domain_verified": True,
            "company_domains": [str(item) for item in profile.get("company_domains") or [] if str(item).strip()],
        }
        for index, url in enumerate(urls, start=1)
    ]


def _capital_ownership_probes(profile: Mapping[str, Any], repair: Mapping[str, Any]) -> list[dict[str, Any]]:
    ticker = str(profile.get("ticker") or repair.get("ticker") or "").strip().upper()
    probes: list[dict[str, Any]] = []
    cik = re.sub(r"\D", "", str(profile.get("cik") or repair.get("cik") or ""))
    if cik:
        probes.append(
            {
                "probe_id": f"{ticker.lower()}_sec_capital_ownership_submissions",
                "url": f"https://data.sec.gov/submissions/CIK{cik.zfill(10)}.json",
                "source_class": "sec_company_submissions",
                "web_scope_policy_ids": ["sec_company_ir_offering_ownership_only"],
                "claim_types": ["capital_ownership_context", "offering_or_ownership_parser_lead", "verification_lead"],
                "source_title": f"{ticker} SEC submissions for offering/ownership context",
            }
        )
    for index, url in enumerate(_unique_strings(repair.get("offering_urls") or repair.get("ownership_urls") or []), start=1):
        probes.append(
            {
                "probe_id": f"{ticker.lower()}_capital_ownership_{index}",
                "url": url,
                "source_class": "sec_offering_filing" if "sec.gov" in url.lower() else "company_ir_material",
                "web_scope_policy_ids": ["sec_company_ir_offering_ownership_only"],
                "claim_types": ["capital_ownership_context", "offering_or_ownership_parser_lead", "verification_lead"],
                "source_title": f"{ticker} capital/ownership source",
            }
        )
    return probes


def _market_proxy_probes(profile: Mapping[str, Any], repair: Mapping[str, Any]) -> list[dict[str, Any]]:
    urls = _unique_strings(repair.get("market_proxy_urls") or repair.get("official_market_urls") or repair.get("probe_urls") or [])
    ticker = str(profile.get("ticker") or repair.get("ticker") or "").strip().upper() or "market"
    source_class = str(repair.get("market_source_class") or repair.get("source_class") or "official_statistics_dataset")
    expanded_urls = _expanded_market_proxy_urls(urls, source_class=source_class)
    return [
        {
            "probe_id": f"{ticker.lower()}_market_proxy_{index}",
            "url": url,
            "source_class": source_class,
            "web_scope_policy_ids": ["official_statistics_or_industry_dataset_only"],
            "claim_types": ["market_proxy_context", "industry_cycle_context", "verification_lead"],
            "source_title": f"{ticker} official market proxy",
        }
        for index, url in enumerate(expanded_urls, start=1)
    ]


def _expanded_market_proxy_urls(urls: list[str], *, source_class: str) -> list[str]:
    expanded: list[str] = []
    for url in urls:
        derived = _source_specific_proxy_urls(url, source_class=source_class)
        expanded.extend(derived or [url])
    return _unique_strings(expanded)


def _source_specific_proxy_urls(url: str, *, source_class: str) -> list[str]:
    lower = str(url or "").strip().lower()
    if not lower:
        return []
    if source_class == "developer_ecosystem_snapshot":
        github = re.match(r"https?://github\.com/([^/\s]+)/([^/\s#?]+)", lower)
        if github:
            owner = github.group(1)
            repo = github.group(2).removesuffix(".git")
            return [f"https://api.github.com/repos/{owner}/{repo}", url]
        npm = re.match(r"https?://www\.npmjs\.com/package/(@?[^/\s#?]+(?:/[^/\s#?]+)?)", lower)
        if npm:
            package = npm.group(1)
            return [f"https://registry.npmjs.org/{package}", url]
        pypi = re.match(r"https?://pypi\.org/project/([^/\s#?]+)", lower)
        if pypi:
            package = pypi.group(1)
            return [f"https://pypi.org/pypi/{package}/json", url]
        huggingface = re.match(r"https?://huggingface\.co/([^/\s#?]+/[^/\s#?]+)", lower)
        if huggingface:
            model_id = huggingface.group(1)
            return [f"https://huggingface.co/api/models/{model_id}", url]
    if source_class == "official_app_store_or_marketplace":
        match = re.search(r"/id(\d+)", lower)
        if match:
            return [f"https://itunes.apple.com/lookup?id={match.group(1)}", url]
    return [url]


def _supply_chain_probes(profile: Mapping[str, Any], repair: Mapping[str, Any]) -> list[dict[str, Any]]:
    urls = _unique_strings(repair.get("supply_chain_urls") or repair.get("partner_urls") or repair.get("probe_urls") or [])
    ticker = str(profile.get("ticker") or repair.get("ticker") or "").strip().upper() or "issuer"
    return [
        {
            "probe_id": f"{ticker.lower()}_supply_chain_{index}",
            "url": url,
            "source_class": str(repair.get("supply_source_class") or "company_customer_page"),
            "web_scope_policy_ids": ["official_company_partner_supplier_customer_only"],
            "claim_types": ["supply_chain_context", "customer_supplier_relationship_context", "verification_lead"],
            "source_title": f"{ticker} official supply-chain source",
            "company_domain_verified": bool(profile.get("company_domains")),
            "company_domains": [str(item) for item in profile.get("company_domains") or [] if str(item).strip()],
        }
        for index, url in enumerate(urls, start=1)
    ]


def _explicit_url_probes(repair: Mapping[str, Any], *, source_class: str = "") -> list[dict[str, Any]]:
    urls = _unique_strings(repair.get("probe_urls") or repair.get("official_urls") or repair.get("source_urls") or [])
    if not urls:
        return []
    repair_type = _repair_type(repair)
    class_text = source_class or _default_source_class_for_repair_type(repair_type)
    return [
        {
            "probe_id": f"{repair_type}_explicit_{index}",
            "url": url,
            "source_class": class_text,
            "web_scope_policy_ids": [str(item) for item in repair.get("web_scope_policy_ids") or []],
            "claim_types": _claim_types_for_repair_type(repair_type),
            "source_title": str(repair.get("source_title") or f"{repair_type} source"),
        }
        for index, url in enumerate(urls, start=1)
    ]


def _allowed_repair_probes(probes: list[dict[str, Any]], *, repair: Mapping[str, Any], repair_type: str) -> list[dict[str, Any]]:
    allowed_classes = {str(item) for item in repair.get("allowed_source_classes") or [] if str(item).strip()}
    if not allowed_classes:
        allowed_classes = set(PUBLIC_WEB_REPAIR_SOURCE_CLASSES.get(repair_type, set()))
    allowed_policies = {str(item) for item in repair.get("web_scope_policy_ids") or [] if str(item).strip()}
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for probe in probes:
        url = str(probe.get("url") or "").strip()
        source_class = str(probe.get("source_class") or "").strip()
        if not url or not source_class:
            continue
        if source_class not in allowed_classes:
            continue
        policies = {str(item) for item in probe.get("web_scope_policy_ids") or [] if str(item).strip()}
        if allowed_policies and policies and not policies.intersection(allowed_policies):
            continue
        if not _url_allowed_for_repair(url, repair=repair, repair_type=repair_type, source_class=source_class):
            continue
        key = (url, source_class)
        if key in seen:
            continue
        seen.add(key)
        out.append(probe)
    return out


def _url_allowed_for_repair(url: str, *, repair: Mapping[str, Any], repair_type: str, source_class: str) -> bool:
    domain = _domain(url)
    if not domain or domain in DISALLOWED_WEB_DOMAINS or any(marker in domain for marker in DISALLOWED_DOMAIN_MARKERS):
        return False
    if source_class == "mainstream_financial_news_article":
        return any(domain == item or domain.endswith("." + item) for item in TRUSTED_NEWS_DOMAINS)
    if domain.endswith("sec.gov") or domain.endswith("data.sec.gov"):
        return source_class.startswith("sec_") or source_class in {"government_dataset_endpoint", "regulator_filings", "sec_fpi_filings"}
    if repair_type in {"issuer_official", "product_surface", "local_filing", "supply_chain"} and source_class.startswith("company"):
        allowed_domains = {str(item).lower().strip() for item in repair.get("company_domains") or [] if str(item).strip()}
        if not allowed_domains:
            allowed_domains = {str(item).lower().strip() for item in _issuer_profile(str(repair.get("ticker") or ""), repair).get("company_domains") or []}
        return not allowed_domains or any(domain == item or domain.endswith("." + item) for item in allowed_domains)
    return True


def _not_found_gap(
    *,
    repair: Mapping[str, Any],
    ticker: str,
    repair_type: str,
    probes: list[dict[str, Any]],
) -> dict[str, Any]:
    base = repair.get("not_found_gap") if isinstance(repair.get("not_found_gap"), Mapping) else {}
    return {
        "gap_id": str(base.get("gap_id") or f"lead_targeted_repair:{repair_type}:{(ticker or 'unknown').lower()}:not_found"),
        "gap_type": str(base.get("gap_type") or _not_found_gap_type(repair_type)),
        "ticker": ticker,
        "analysis_dimension": str(repair.get("dimension") or base.get("dimension") or _dimension_for_repair_type(repair_type)),
        "repair_type": repair_type,
        "reason_code": "scoped_public_web_repair_failed_or_unavailable",
        "reason": (
            "Scoped public web repair did not return a usable allowed-source snapshot in this run; "
            "do not fill the gap with generic web proxies or commercial tracker assumptions."
        ),
        "attempted_probe_count": len(probes),
        "attempted_source_classes": _unique_strings([str(probe.get("source_class") or "") for probe in probes]),
        "repairability": "bounded_gap",
        "source_family": "live_public_web_context",
        "claim_boundary": _claim_scope_boundary(repair_type),
    }


def execute_official_issuer_repair_plan(
    repair_plan: Mapping[str, Any],
    *,
    fetch: FetchFunc | None = None,
    max_probes_per_issuer: int = 2,
) -> dict[str, Any]:
    repairs = [
        dict(item)
        for item in repair_plan.get("repairs") or []
        if isinstance(item, Mapping) and str(item.get("route") or "") in REPAIR_ROUTE_TYPES
    ]
    if not repairs:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "not_required",
            "attempted_count": 0,
            "success_count": 0,
            "bounded_gap_count": 0,
            "context_rows": [],
            "source_gaps": [],
            "tool_observations": [],
            "artifact_refs": [],
            "official_context_summaries": [],
        }

    fetcher = fetch or _fetch_url
    context_rows: list[dict[str, Any]] = []
    source_gaps: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    artifact_refs: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    attempted = 0

    for repair in repairs:
        ticker = str(repair.get("ticker") or "").strip().upper()
        repair_type = _repair_type(repair)
        profile = _issuer_profile(ticker, repair)
        probes = _repair_probes(profile, repair)
        probes = _allowed_repair_probes(probes, repair=repair, repair_type=repair_type)[: max(1, int(max_probes_per_issuer or 1))]
        repair_success = 0
        for probe in probes:
            attempted += 1
            started = time.perf_counter()
            result = _execute_probe(ticker=ticker, probe=probe, repair=repair, repair_type=repair_type, fetch=fetcher)
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            row_count = len(result.get("context_rows") or [])
            gap_count = len(result.get("source_gaps") or [])
            observations.append(
                {
                    "route_id": result.get("route_id") or "",
                    "retrieval_route": "live_public_web_context",
                    "agent_id": "web_evidence_operator",
                    "tool_name": "web_evidence_snapshot",
                    "status": result.get("status") or "error",
                    "error": result.get("error") or "",
                    "arguments": result.get("arguments") or {},
                    "row_count": row_count,
                    "source_gap_count": gap_count,
                    "boundary": {
                        "status": "pass" if row_count else "fail",
                        "allowed_claim_scope": _claim_scope_boundary(repair_type),
                        "prohibited_claim_scope": _prohibited_claim_scope(repair_type),
                    },
                    "runtime_summary": {
                        "tool_name": "web_evidence_snapshot",
                        "context_row_count": row_count,
                        "repair_type": repair_type,
                        "source_class": probe.get("source_class") or "",
                        "snapshot_id": result.get("snapshot_id") or "",
                        "elapsed_ms": elapsed_ms,
                    },
                }
            )
            context_rows.extend(dict(item) for item in result.get("context_rows") or [] if isinstance(item, Mapping))
            source_gaps.extend(dict(item) for item in result.get("source_gaps") or [] if isinstance(item, Mapping))
            artifact_refs.extend(dict(item) for item in result.get("artifact_refs") or [] if isinstance(item, Mapping))
            summaries.extend(dict(item) for item in result.get("official_context_summaries") or [] if isinstance(item, Mapping))
            repair_success += row_count
        if repair_success == 0:
            source_gaps.append(_not_found_gap(repair=repair, ticker=ticker, repair_type=repair_type, probes=probes))

    deduped_rows = _dedupe_rows(context_rows)
    deduped_gaps = _dedupe_gaps(source_gaps)
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass" if deduped_rows else "bounded_gap",
        "attempted_count": attempted,
        "success_count": len(deduped_rows),
        "bounded_gap_count": len(deduped_gaps),
        "context_rows": deduped_rows,
        "source_gaps": deduped_gaps,
        "tool_observations": observations,
        "artifact_refs": artifact_refs,
        "official_context_summaries": summaries[:12],
        "policy": "lead_targeted_repair_scoped_public_web_context_rows_v0_2",
    }


def _issuer_profile(ticker: str, repair: Mapping[str, Any]) -> dict[str, Any]:
    profile = dict(ISSUER_PROFILES.get(ticker, {}))
    profile.setdefault("ticker", ticker)
    if repair.get("cik"):
        profile["cik"] = str(repair.get("cik") or "")
    if repair.get("company_domains"):
        profile["company_domains"] = [str(item) for item in repair.get("company_domains") or [] if str(item).strip()]
    if repair.get("company_ir_urls"):
        profile["company_ir_urls"] = [str(item) for item in repair.get("company_ir_urls") or [] if str(item).strip()]
    if repair.get("official_product_urls"):
        profile["official_product_urls"] = [str(item) for item in repair.get("official_product_urls") or [] if str(item).strip()]
    if repair.get("official_product_surfaces"):
        profile["official_product_surfaces"] = [str(item) for item in repair.get("official_product_surfaces") or [] if str(item).strip()]
    if repair.get("official_metric_leads"):
        profile["official_metric_leads"] = [str(item) for item in repair.get("official_metric_leads") or [] if str(item).strip()]
    return profile


def _issuer_probes(profile: Mapping[str, Any], repair: Mapping[str, Any]) -> list[dict[str, Any]]:
    ticker = str(profile.get("ticker") or repair.get("ticker") or "").strip().upper()
    probes: list[dict[str, Any]] = []
    cik = re.sub(r"\D", "", str(profile.get("cik") or ""))
    policy_ids = [str(item) for item in repair.get("web_scope_policy_ids") or [] if str(item).strip()] or [
        "company_ir_local_exchange_regulator_sec_fpi_only"
    ]
    if cik:
        probes.append(
            {
                "probe_id": f"{ticker.lower()}_sec_submissions",
                "url": f"https://data.sec.gov/submissions/CIK{cik.zfill(10)}.json",
                "source_class": "government_dataset_endpoint",
                "web_scope_policy_ids": policy_ids,
                "claim_types": ["issuer_filing_presence", "annual_report_context"],
                "source_title": f"{ticker} SEC submissions",
            }
        )
    for index, url in enumerate(profile.get("company_ir_urls") or [], start=1):
        probes.append(
            {
                "probe_id": f"{ticker.lower()}_company_ir_{index}",
                "url": str(url),
                "source_class": "company_ir_material",
                "web_scope_policy_ids": policy_ids,
                "claim_types": ["company_ir_context", "annual_report_context"],
                "source_title": f"{ticker} company IR",
                "company_domain_verified": True,
                "company_domains": [str(item) for item in profile.get("company_domains") or [] if str(item).strip()],
            }
        )
    return probes


def _execute_probe(
    *,
    ticker: str,
    probe: Mapping[str, Any],
    repair: Mapping[str, Any],
    repair_type: str,
    fetch: FetchFunc,
) -> dict[str, Any]:
    url = str(probe.get("url") or "")
    source_class = str(probe.get("source_class") or "")
    snapshot_id = "official_" + hashlib.sha1(f"{ticker}|{url}|{source_class}".encode("utf-8")).hexdigest()[:14]
    args = {
        "ticker": ticker,
        "url": url,
        "snapshot_url": url,
        "source_class": source_class,
        "repair_type": repair_type,
        "analysis_dimension": str(repair.get("dimension") or _dimension_for_repair_type(repair_type)),
        "web_scope_policy_ids": [str(item) for item in probe.get("web_scope_policy_ids") or []],
        "claim_types": [str(item) for item in probe.get("claim_types") or []],
        "source_title": str(probe.get("source_title") or ticker),
        "company_domain_verified": bool(probe.get("company_domain_verified")),
        "company_domains": [str(item) for item in probe.get("company_domains") or []],
        "repair_id": repair.get("repair_id") or "",
    }
    try:
        status_code, content_type, body = fetch(url)
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "error",
            "error": type(exc).__name__,
            "route_id": str(probe.get("probe_id") or snapshot_id),
            "arguments": args,
            "context_rows": [],
            "source_gaps": [
                {
                    "gap_id": f"official_issuer_probe:{ticker.lower()}:{snapshot_id}:fetch_failed",
                    "gap_type": "official_issuer_probe_fetch_failed",
                    "ticker": ticker,
                    "repair_type": repair_type,
                    "analysis_dimension": str(repair.get("dimension") or _dimension_for_repair_type(repair_type)),
                    "source_family": "live_public_web_context",
                    "url": url,
                    "reason_code": type(exc).__name__,
                    "reason": str(exc)[:300],
                    "repairability": "retrievable_gap",
                }
            ],
            "artifact_refs": [],
        }
    if status_code >= 400 or not body.strip():
        return {
            "status": "partial",
            "error": f"http_{status_code}" if status_code else "empty_body",
            "route_id": str(probe.get("probe_id") or snapshot_id),
            "arguments": args,
            "context_rows": [],
            "source_gaps": [
                {
                    "gap_id": f"official_issuer_probe:{ticker.lower()}:{snapshot_id}:http_{status_code}",
                    "gap_type": "official_issuer_probe_unusable_response",
                    "ticker": ticker,
                    "repair_type": repair_type,
                    "analysis_dimension": str(repair.get("dimension") or _dimension_for_repair_type(repair_type)),
                    "source_family": "live_public_web_context",
                    "url": url,
                    "reason_code": f"http_{status_code}" if status_code else "empty_body",
                    "repairability": "retrievable_gap",
                }
            ],
            "artifact_refs": [],
        }
    title, preview = _summarize_probe_body(body, content_type=content_type)
    as_of = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    source_layer_meta = _source_layer_metadata(repair_type=repair_type, source_class=source_class)
    row = {
        "evidence_ref": snapshot_id,
        "evidence_id": snapshot_id,
        "source_family": "live_public_web_context",
        **source_layer_meta,
        "retrieval_route": "live_public_web_context",
        "source_class": source_class,
        "repair_type": repair_type,
        "analysis_dimension": str(repair.get("dimension") or _dimension_for_repair_type(repair_type)),
        "web_scope_policy_ids": [str(item) for item in probe.get("web_scope_policy_ids") or []],
        "claim_types": [str(item) for item in probe.get("claim_types") or []],
        "ticker": ticker,
        "url": url,
        "domain": _domain(url),
        "snapshot_id": snapshot_id,
        "snapshot_url": url,
        "as_of_datetime": as_of,
        "citation": {"url": url, "title": title or str(probe.get("source_title") or ticker)},
        "source_title": title or str(probe.get("source_title") or ticker),
        "preview": preview,
        "text": preview,
        "context_only": True,
        "lead_only": True,
        "exact_value_authority": False,
        "authority_boundary": _authority_boundary(repair_type),
        "claim_boundary": _claim_scope_boundary(repair_type),
        "repair_id": repair.get("repair_id") or "",
    }
    lead_rows = _repair_lead_context_rows(
        ticker=ticker,
        snapshot_id=snapshot_id,
        url=url,
        source_class=source_class,
        title=row["source_title"],
        as_of=as_of,
        repair=repair,
        repair_type=repair_type,
        preview=preview,
    )
    structured_rows = parse_public_web_context_rows(
        ticker=ticker,
        parent_evidence_ref=snapshot_id,
        url=url,
        source_class=source_class,
        repair_type=repair_type,
        analysis_dimension=str(repair.get("dimension") or _dimension_for_repair_type(repair_type)),
        title=row["source_title"],
        body=body,
        content_type=content_type,
        as_of_datetime=as_of,
        citation=row["citation"],
        source_layer_meta=source_layer_meta,
        claim_boundary=_claim_scope_boundary(repair_type),
        authority_boundary=_authority_boundary(repair_type),
        repair=repair,
    )
    output_rows = [row, *lead_rows, *structured_rows]
    digest = hashlib.sha1(json.dumps(output_rows, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    return {
        "schema_version": "sec_agent_web_evidence_snapshot_v0.1",
        "status": "ok",
        "snapshot_id": snapshot_id,
        "snapshot_url": url,
        "as_of_datetime": as_of,
        "source_class": source_class,
        "web_scope_policy_ids": [str(item) for item in probe.get("web_scope_policy_ids") or []],
        "route_id": str(probe.get("probe_id") or snapshot_id),
        "arguments": args,
        "context_rows": output_rows,
        "source_gaps": [],
        "artifact_refs": [
            {
                "artifact_id": snapshot_id,
                "path": "",
                "digest": digest,
                "row_count": len(output_rows),
                "structured_context_row_count": len(structured_rows),
            }
        ],
        "official_context_summaries": [
            {
                "ticker": ticker,
                "repair_type": repair_type,
                "source_class": source_class,
                "title": row["source_title"],
                "url": url,
                "snapshot_id": snapshot_id,
                "claim_boundary": row["claim_boundary"],
                "product_surface_leads": [
                    str(item.get("product_family") or "")
                    for item in [*lead_rows, *structured_rows]
                    if str(item.get("product_family") or "")
                ][:6],
                "metric_leads": _issuer_profile(ticker, repair).get("official_metric_leads") or [],
                "structured_context_row_count": len(structured_rows),
                "structured_context_types": _unique_strings(
                    [str(item.get("structured_context_type") or item.get("fact_type") or "") for item in structured_rows]
                )[:8],
            }
        ],
    }


def _repair_lead_context_rows(
    *,
    ticker: str,
    snapshot_id: str,
    url: str,
    source_class: str,
    title: str,
    as_of: str,
    repair: Mapping[str, Any],
    repair_type: str,
    preview: str,
) -> list[dict[str, Any]]:
    profile = _issuer_profile(ticker, repair)
    product_surfaces = _product_surface_terms(profile, repair=repair)
    metric_leads = _metric_leads_for_repair_type(repair_type, profile=profile, repair=repair)
    if repair_type not in {"issuer_official", "product_surface", "local_filing"}:
        return [_non_product_lead_context_row(
            ticker=ticker,
            snapshot_id=snapshot_id,
            url=url,
            source_class=source_class,
            title=title,
            as_of=as_of,
            repair=repair,
            repair_type=repair_type,
            preview=preview,
            metric_leads=metric_leads,
        )]
    if not product_surfaces and not metric_leads:
        return []
    rows: list[dict[str, Any]] = []
    for index, product in enumerate(product_surfaces[:4], start=1):
        lead_ref = f"{snapshot_id}:product_surface:{_slug(product)}"
        rows.append(
            {
                "evidence_ref": lead_ref,
                "evidence_id": lead_ref,
                "parent_evidence_ref": snapshot_id,
                "source_family": "live_public_web_context",
                **_source_layer_metadata(repair_type=repair_type, source_class=source_class),
                "retrieval_route": "live_public_web_context",
                "source_class": source_class,
                "repair_type": repair_type,
                "analysis_dimension": str(repair.get("dimension") or _dimension_for_repair_type(repair_type)),
                "web_scope_policy_ids": [str(item) for item in repair.get("web_scope_policy_ids") or []] or ["official_product_surface_only"],
                "claim_types": ["official_product_surface", "product_taxonomy_context", "product_spec_context", "verification_lead"],
                "ticker": ticker,
                "product_family": product,
                "product_or_segment": product,
                "metric_leads": metric_leads[:6],
                "url": url,
                "domain": _domain(url),
                "snapshot_id": lead_ref,
                "snapshot_url": url,
                "as_of_datetime": as_of,
                "citation": {"url": url, "title": title},
                "source_title": title,
                "preview": _compact_text(
                    f"Official issuer source reached for {ticker}; product surface lead: {product}. "
                    f"Relevant parser targets include {', '.join(metric_leads[:4]) if metric_leads else 'company product and disclosure metrics'}. "
                    f"{preview}",
                    900,
                ),
                "text": _compact_text(
                    f"{ticker} official product-surface lead: {product}. "
                    "This supports product taxonomy/context and parser targeting only; it does not prove sales, orders, backlog, shipments, share, ASP, or inventory values.",
                    520,
                ),
                "context_only": True,
                "lead_only": True,
                "exact_value_authority": False,
                "promotion_status": "official_context_or_lead_available",
                "authority_boundary": _authority_boundary(repair_type),
                "claim_boundary": _product_context_claim_boundary(),
                "repair_id": repair.get("repair_id") or "",
            }
        )
    return rows


def _non_product_lead_context_row(
    *,
    ticker: str,
    snapshot_id: str,
    url: str,
    source_class: str,
    title: str,
    as_of: str,
    repair: Mapping[str, Any],
    repair_type: str,
    preview: str,
    metric_leads: list[str],
) -> dict[str, Any]:
    topic = _topic_for_repair_type(repair_type)
    lead_ref = f"{snapshot_id}:{repair_type}:{_slug(topic)}"
    return {
        "evidence_ref": lead_ref,
        "evidence_id": lead_ref,
        "parent_evidence_ref": snapshot_id,
        "source_family": "live_public_web_context",
        **_source_layer_metadata(repair_type=repair_type, source_class=source_class),
        "retrieval_route": "live_public_web_context",
        "source_class": source_class,
        "repair_type": repair_type,
        "analysis_dimension": str(repair.get("dimension") or _dimension_for_repair_type(repair_type)),
        "web_scope_policy_ids": [str(item) for item in repair.get("web_scope_policy_ids") or []],
        "claim_types": _claim_types_for_repair_type(repair_type),
        "ticker": ticker,
        "topic": topic,
        "metric_leads": metric_leads[:8],
        "url": url,
        "domain": _domain(url),
        "snapshot_id": lead_ref,
        "snapshot_url": url,
        "as_of_datetime": as_of,
        "citation": {"url": url, "title": title},
        "source_title": title,
        "preview": _compact_text(
            f"Scoped {repair_type} repair reached an allowed public source for {ticker or 'issuer/context'}. "
            f"Parser targets include {', '.join(metric_leads[:5]) if metric_leads else topic}. {preview}",
            900,
        ),
        "text": _compact_text(
            f"{ticker or 'Issuer/context'} scoped {repair_type} repair reached allowed source context for {topic}. "
            f"{_claim_scope_boundary(repair_type)}",
            520,
        ),
        "context_only": True,
        "lead_only": True,
        "exact_value_authority": False,
        "promotion_status": "scoped_public_context_or_parser_lead_available",
        "authority_boundary": _authority_boundary(repair_type),
        "claim_boundary": _claim_scope_boundary(repair_type),
        "repair_id": repair.get("repair_id") or "",
    }


def _source_layer_metadata(*, repair_type: str, source_class: str) -> dict[str, Any]:
    layer_id = _source_layer_id_for_repair(repair_type=repair_type, source_class=source_class)
    memo_usage = {
        "L1": "official source context; exact facts still require source parser gates",
        "L2": "trusted public/official context or parser lead with source boundary",
        "L3": "directional market/channel/developer proxy context only",
        "L4": "discovery or exclusion lead only",
    }.get(layer_id, "bounded public context")
    return {
        "source_layer_id": layer_id,
        "source_layer": layer_id,
        "parser_status": "snapshot_context_parser_pass",
        "structured_fact_status": "context_row_materialized",
        "evidence_graph_status": "runtime_ready_context",
        "context_or_proxy_allowed": layer_id in {"L1", "L2", "L3"},
        "can_support_company_exact_fact": False,
        "source_layer_claim_boundary": _claim_scope_boundary(repair_type),
        "source_layer_memo_usage": memo_usage,
    }


def _source_layer_id_for_repair(*, repair_type: str, source_class: str) -> str:
    class_text = str(source_class or "").strip()
    if class_text in {
        "official_app_store_or_marketplace",
        "official_market_share_snapshot",
        "public_market_proxy_snapshot",
        "ecommerce_major_platform",
        "developer_ecosystem_snapshot",
        "public_tender_or_contract_portal",
        "job_posting_snapshot",
        "channel_pricing_snapshot",
        "platform_review_or_ranking_snapshot",
    }:
        return "L3"
    if class_text in {"mainstream_financial_news_article", "supplier_customer_official_news"}:
        return "L2"
    if repair_type == "market_proxy":
        return "L3" if "market_proxy" in class_text else "L2"
    if class_text.startswith("sec_") or class_text in {"regulator_filings", "local_exchange_filings", "government_dataset_endpoint"}:
        return "L1"
    if repair_type in {"issuer_official", "product_surface", "local_filing", "capital_ownership", "supply_chain"}:
        return "L2"
    return "L2"


def _product_surface_terms(profile: Mapping[str, Any], *, repair: Mapping[str, Any]) -> list[str]:
    terms = _unique_strings(
        [
            *list(profile.get("official_product_surfaces") or []),
            *list(repair.get("official_product_surfaces") or []),
            *list(repair.get("product_surfaces") or []),
            *list(repair.get("target_products") or []),
        ]
    )
    return terms


def _metric_leads_for_repair_type(repair_type: str, *, profile: Mapping[str, Any], repair: Mapping[str, Any]) -> list[str]:
    explicit = _unique_strings(repair.get("official_metric_leads") or repair.get("metric_leads") or [])
    if explicit:
        return explicit
    if repair_type in {"issuer_official", "product_surface", "local_filing"}:
        return _unique_strings(profile.get("official_metric_leads") or ["revenue", "orders", "backlog", "shipments", "capacity"])
    if repair_type == "capital_ownership":
        return ["debt", "offering amount", "security type", "maturity", "interest rate", "holder", "ownership percentage"]
    if repair_type == "market_proxy":
        return ["market size", "vendor share", "shipments", "registrations", "install base", "industry demand proxy"]
    if repair_type == "supply_chain":
        return ["customer relationship", "supplier relationship", "order context", "capacity allocation", "contract duration"]
    return ["public context"]


def _default_source_class_for_repair_type(repair_type: str) -> str:
    return {
        "issuer_official": "company_ir_material",
        "product_surface": "company_product_page",
        "local_filing": "regulator_filings",
        "market_proxy": "official_statistics_dataset",
        "capital_ownership": "sec_company_submissions",
        "supply_chain": "company_customer_page",
    }.get(repair_type, "public_market_proxy_snapshot")


def _claim_types_for_repair_type(repair_type: str) -> list[str]:
    return {
        "issuer_official": ["official_issuer_context", "annual_report_context", "verification_lead"],
        "product_surface": ["official_product_surface", "product_taxonomy_context", "product_spec_context", "verification_lead"],
        "local_filing": ["local_filing_context", "issuer_filing_presence", "verification_lead"],
        "market_proxy": ["market_proxy_context", "industry_cycle_context", "verification_lead"],
        "capital_ownership": ["capital_ownership_context", "offering_or_ownership_parser_lead", "verification_lead"],
        "supply_chain": ["supply_chain_context", "customer_supplier_relationship_context", "verification_lead"],
    }.get(repair_type, ["public_context", "verification_lead"])


def _dimension_for_repair_type(repair_type: str) -> str:
    return {
        "issuer_official": "fundamentals",
        "product_surface": "product_and_production",
        "local_filing": "fundamentals",
        "market_proxy": "competition_and_market_position",
        "capital_ownership": "capital_and_financing",
        "supply_chain": "competition_and_market_position",
    }.get(repair_type, "fundamentals")


def _topic_for_repair_type(repair_type: str) -> str:
    return {
        "market_proxy": "industry or market proxy",
        "capital_ownership": "capital structure, offering, ownership, or insider context",
        "supply_chain": "official customer, supplier, partner, or channel relationship",
        "local_filing": "local exchange, regulator, SEC FPI, or company filing context",
        "issuer_official": "issuer official disclosure context",
        "product_surface": "product taxonomy, specification, or official product surface",
    }.get(repair_type, "public evidence context")


def _not_found_gap_type(repair_type: str) -> str:
    return {
        "issuer_official": "bounded_gap_after_official_issuer_source_probe",
        "product_surface": "bounded_gap_after_official_product_surface_probe",
        "local_filing": "bounded_gap_after_local_filing_probe",
        "market_proxy": "bounded_gap_after_public_market_proxy_probe",
        "capital_ownership": "bounded_gap_after_capital_ownership_probe",
        "supply_chain": "bounded_gap_after_supply_chain_probe",
    }.get(repair_type, "retrievable_gap_not_found_after_targeted_repair")


def _authority_boundary(repair_type: str) -> str:
    return {
        "product_surface": "official_product_surface_context_only_until_product_kpi_parser_gate_passes",
        "local_filing": "official_local_filing_context_only_until_parser_period_unit_citation_gate_passes",
        "market_proxy": "public_market_proxy_context_only_no_company_exact_metric_promotion",
        "capital_ownership": "capital_ownership_context_only_until_source_specific_parser_gate_passes",
        "supply_chain": "supply_chain_relationship_context_only_no_volume_or_order_promotion",
        "issuer_official": "official_issuer_web_context_only_until_parser_period_unit_citation_gate_passes",
    }.get(repair_type, "public_web_context_only_until_parser_gate_passes")


def _claim_scope_boundary(repair_type: str) -> str:
    return {
        "product_surface": "can support product taxonomy/spec/parser target context; cannot support sales, share, orders, backlog, ASP, inventory, or sell-through without exact parser authority",
        "local_filing": "can support official filing/source availability and parser targeting; cannot promote exact facts until period, unit, and citation gates pass",
        "market_proxy": "can support industry cycle or public market context; cannot prove issuer-specific sales, share, orders, inventory, or channel metrics",
        "capital_ownership": "can support ownership/offering/debt context; exact amount/security/holder claims require source-specific parser gates",
        "supply_chain": "can support official relationship or supply-chain context; cannot infer shipment, revenue, allocation, or order volume",
        "issuer_official": "can support issuer coverage and official-source existence; cannot support sales/share/orders without parser authority",
    }.get(repair_type, "context only until source-specific parser authority passes")


def _product_context_claim_boundary() -> str:
    return (
        "official product surface and metric parser lead only; no exact orders/backlog/sales/share authority; "
        "no shipments, ASP, inventory, sell-through, or product KPI promotion without parser gate"
    )


def _prohibited_claim_scope(repair_type: str) -> str:
    return {
        "product_surface": "commercial_tracker_sales_share_sell_through_orders_backlog_or_exact_values_without_parser_gate",
        "market_proxy": "issuer_specific_sales_share_or_order_claim_from_proxy_context",
        "capital_ownership": "exact_amount_security_holder_or_transaction_claim_without_source_parser_gate",
        "supply_chain": "shipment_revenue_order_volume_or_allocation_inference_from_relationship_context",
    }.get(repair_type, "commercial_tracker_or_exact_value_without_parser_gate")


def _fetch_url(url: str) -> tuple[int, str, str]:
    user_agent = os.environ.get("SEC_USER_AGENT") or os.environ.get("FINSIGHT_WEB_USER_AGENT") or "FINInsightAgent/0.1 research-contact@example.com"
    request = Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept": "application/json,text/html,text/plain;q=0.8,*/*;q=0.2",
        },
    )
    try:
        with urlopen(request, timeout=float(os.environ.get("FINSIGHT_OFFICIAL_REPAIR_TIMEOUT_S") or 6)) as response:  # noqa: S310
            raw = response.read(1_500_000)
            charset = response.headers.get_content_charset() or "utf-8"
            return int(response.status or 200), str(response.headers.get("Content-Type") or ""), raw.decode(charset, errors="replace")
    except HTTPError as exc:
        raw = exc.read(80_000) if hasattr(exc, "read") else b""
        return int(exc.code or 0), str(getattr(exc, "headers", {}).get("Content-Type", "") if getattr(exc, "headers", None) else ""), raw.decode("utf-8", errors="replace")
    except URLError as exc:
        raise RuntimeError(str(exc.reason or exc)) from exc


def _summarize_probe_body(body: str, *, content_type: str) -> tuple[str, str]:
    text = str(body or "")
    if "json" in str(content_type or "").lower() or text.lstrip().startswith("{"):
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = {}
        if isinstance(payload, Mapping):
            title = str(payload.get("name") or payload.get("entityName") or payload.get("companyName") or "official issuer disclosure")
            filings = _recent_fpi_filings(payload)
            if filings:
                return title, "Recent official filings: " + "; ".join(filings[:8])
            return title, _compact_text(json.dumps({key: payload.get(key) for key in list(payload.keys())[:8]}, ensure_ascii=False), 900)
    title_match = re.search(r"<title[^>]*>(.*?)</title>", text, flags=re.I | re.S)
    title = _compact_text(_strip_html(title_match.group(1) if title_match else ""), 160) or "official issuer disclosure"
    meta_match = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']', text, flags=re.I | re.S)
    preview_source = meta_match.group(1) if meta_match else text
    preview = _compact_text(_strip_html(preview_source), 900)
    return title, preview


def _recent_fpi_filings(payload: Mapping[str, Any]) -> list[str]:
    recent = payload.get("filings")
    if isinstance(recent, Mapping):
        recent = recent.get("recent")
    if not isinstance(recent, Mapping):
        return []
    forms = recent.get("form") if isinstance(recent.get("form"), list) else []
    dates = recent.get("filingDate") if isinstance(recent.get("filingDate"), list) else []
    accessions = recent.get("accessionNumber") if isinstance(recent.get("accessionNumber"), list) else []
    filings: list[str] = []
    for form, date, accession in zip(forms, dates, accessions):
        form_text = str(form or "")
        if form_text.upper() not in {"20-F", "6-K", "40-F"}:
            continue
        filings.append(f"{form_text} filed {date} accession {accession}")
        if len(filings) >= 12:
            break
    return filings


def _strip_html(value: str) -> str:
    text = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", str(value or ""))
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _compact_text(value: str, max_chars: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 1)].rstrip() + "…"


def _unique_strings(values: Any) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _slug(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "_", str(value or "").lower()).strip("_")
    return text or hashlib.sha1(str(value or "").encode("utf-8")).hexdigest()[:10]


def _domain(url: str) -> str:
    match = re.match(r"https?://([^/]+)", str(url or ""), flags=re.I)
    return (match.group(1).lower() if match else "").split(":")[0]


def _dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        key = str(row.get("snapshot_id") or row.get("evidence_ref") or row.get("url") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def _dedupe_gaps(gaps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for gap in gaps:
        key = str(gap.get("gap_id") or hashlib.sha1(json.dumps(gap, sort_keys=True, default=str).encode("utf-8")).hexdigest())
        if key in seen:
            continue
        seen.add(key)
        out.append(gap)
    return out
