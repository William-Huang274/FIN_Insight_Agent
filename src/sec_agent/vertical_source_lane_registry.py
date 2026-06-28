from __future__ import annotations

import csv
import hashlib
import json
import re
from collections.abc import Iterable
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from sec_agent.source_coverage_gate import build_source_coverage_gate


VERTICAL_SOURCE_LANE_REGISTRY_SCHEMA_VERSION = "finsight_vertical_source_lane_registry_v0_1"


@dataclass(frozen=True)
class LaneDefinition:
    lane_id: str
    lane_name: str
    industry_schema: str
    subvertical: str
    company_archetype: str
    representative_tickers: tuple[str, ...]
    product_taxonomy_scope: tuple[str, ...]
    key_products_or_services: tuple[str, ...]
    l1_required_facts: tuple[str, ...]
    l1_financial_statement_focus: tuple[str, ...]
    l1_company_disclosed_kpi_focus: tuple[str, ...]
    l2_trusted_context_sources: tuple[str, ...]
    l2_regulatory_or_official_sources: tuple[str, ...]
    l2_official_product_surface_sources: tuple[str, ...]
    l3_proxy_sources: tuple[str, ...]
    l4_discovery_sources: tuple[str, ...]
    public_data_ceiling: tuple[str, ...]
    expected_commercial_gaps: tuple[str, ...]


LANE_DEFINITIONS: tuple[LaneDefinition, ...] = (
    LaneDefinition(
        lane_id="V1",
        lane_name="Semiconductors / AI Infrastructure",
        industry_schema="semiconductors_hardware",
        subvertical="semiconductors_ai_infrastructure",
        company_archetype="chips_semicap_ai_servers_networking_and_datacenter_infrastructure",
        representative_tickers=("NVDA", "AMD", "INTC", "QCOM", "AVGO", "ASML", "TSM", "AMAT", "LRCX", "KLAC", "DELL", "SMCI", "HPE", "ANET", "MRVL"),
        product_taxonomy_scope=("GPU/accelerator", "CPU", "ASIC", "NIC/networking", "wafer fab/foundry", "advanced packaging", "lithography", "deposition/etch/metrology", "AI server/rack"),
        key_products_or_services=("AI accelerators", "datacenter GPUs", "foundry capacity", "semicap tools", "AI servers", "datacenter networking"),
        l1_required_facts=("segment/product revenue", "inventory", "purchase commitments", "capex", "gross margin", "customer concentration", "backlog/order commentary", "20-F/6-K/local filings for non-US issuers"),
        l1_financial_statement_focus=("revenue by segment", "gross margin", "inventory", "capex", "purchase obligations", "deferred revenue/backlog where disclosed", "cash conversion"),
        l1_company_disclosed_kpi_focus=("product revenue", "unit deliveries if disclosed", "backlog/orders", "capacity/throughput", "customer concentration"),
        l2_trusted_context_sources=("mainstream_financial_news", "supplier_customer_official_news", "industry_association_reports"),
        l2_regulatory_or_official_sources=("export_control_regulators", "patentsview_api", "openalex_api", "official_trade_statistics"),
        l2_official_product_surface_sources=("company_product_pages", "company_ir_reports", "official_product_specs"),
        l3_proxy_sources=("channel_pricing_quotations", "public_tenders_contracts_orders", "job_postings_hiring_signals", "developer_ecosystem_github_npm_pypi_huggingface"),
        l4_discovery_sources=("common_crawl_index", "unverified_self_media_forums", "yahoo_chart"),
        public_data_ceiling=("public sources cannot prove vendor share, sell-through, allocation, channel inventory, or tracker forecasts without company disclosure",),
        expected_commercial_gaps=("IDC/Counterpoint/Omdia/Gartner shipments/share/forecast", "supply allocation", "hyperscaler exact purchase orders", "channel inventory"),
    ),
    LaneDefinition(
        lane_id="V2",
        lane_name="Consumer Electronics / Hardware Devices",
        industry_schema="consumer_electronics",
        subvertical="consumer_hardware_devices",
        company_archetype="devices_pcs_wearables_gaming_and_smart_hardware",
        representative_tickers=("AAPL", "MSFT", "GOOGL", "DELL", "HPQ", "LNVGY", "SONY", "SSNLF"),
        product_taxonomy_scope=("phones", "tablets", "PCs", "wearables", "gaming hardware", "smart devices", "device services ecosystem"),
        key_products_or_services=("iPhone/Mac/iPad", "Surface/Xbox", "PCs", "wearables", "consumer hardware services"),
        l1_required_facts=("segment revenue", "unit commentary if disclosed", "warranty", "inventory", "channel comments", "services attach where disclosed"),
        l1_financial_statement_focus=("product revenue mix", "gross margin", "inventory", "warranty", "deferred revenue/services", "sales and marketing"),
        l1_company_disclosed_kpi_focus=("device revenue", "unit sales/deliveries if disclosed", "installed base/subscribers if disclosed"),
        l2_trusted_context_sources=("mainstream_financial_news", "supplier_customer_official_news"),
        l2_regulatory_or_official_sources=("regulatory_certification_where_available",),
        l2_official_product_surface_sources=("company_product_pages", "official_product_specs", "company_ir_reports"),
        l3_proxy_sources=("ecommerce_major_platforms", "channel_pricing_quotations", "app_store_rankings", "platform_reviews_rankings_downloads"),
        l4_discovery_sources=("common_crawl_index", "unverified_self_media_forums", "search_snippet"),
        public_data_ceiling=("public channels can show price/configuration/availability but not ASP, sell-through, shipment share, or channel inventory",),
        expected_commercial_gaps=("IDC/Canalys/Counterpoint device shipments/share", "retailer POS/sell-through", "channel inventory", "ASP tracker"),
    ),
    LaneDefinition(
        lane_id="V3",
        lane_name="SaaS / Cloud / Developer Products",
        industry_schema="software_saas",
        subvertical="software_cloud_developer_products",
        company_archetype="subscription_software_cloud_platform_security_data_and_developer_ecosystem",
        representative_tickers=("MSFT", "AMZN", "GOOGL", "CRM", "NOW", "ADBE", "SNOW", "DDOG", "NET", "PLTR", "MDB", "TEAM"),
        product_taxonomy_scope=("cloud infrastructure", "AI services", "observability", "data platform", "security", "workflow", "developer tools", "marketplace apps"),
        key_products_or_services=("cloud platform", "SaaS subscription", "AI APIs", "data/observability/security products", "developer ecosystem"),
        l1_required_facts=("segment revenue", "RPO/cRPO/billings", "deferred revenue", "sales efficiency", "capex/leases if infra-heavy"),
        l1_financial_statement_focus=("subscription revenue", "remaining performance obligations", "deferred revenue", "operating margin", "sales and marketing", "capex/lease commitments"),
        l1_company_disclosed_kpi_focus=("ARR/RPO/billings if disclosed", "customer count", "net retention if disclosed", "cloud segment revenue"),
        l2_trusted_context_sources=("mainstream_financial_news", "supplier_customer_official_news"),
        l2_regulatory_or_official_sources=("status_pages", "official_release_notes", "official_docs"),
        l2_official_product_surface_sources=("company_product_pages", "pricing_pages", "documentation", "company_ir_reports"),
        l3_proxy_sources=("developer_ecosystem_github_npm_pypi_huggingface", "job_postings_hiring_signals", "public_tenders_contracts_orders", "app_store_rankings"),
        l4_discovery_sources=("developer_forums_as_discovery_only", "common_crawl_index", "search_snippet"),
        public_data_ceiling=("developer activity and public contracts are adoption/context proxies, not revenue, retention, or share proof",),
        expected_commercial_gaps=("net retention benchmarks", "third-party web traffic/commercial intent", "private cloud usage", "consensus revision"),
    ),
    LaneDefinition(
        lane_id="V4",
        lane_name="Pharma / Biotech / Medtech",
        industry_schema="healthcare_pharma_medtech",
        subvertical="pharma_biotech_medtech",
        company_archetype="drug_device_trial_regulatory_and_procedure_businesses",
        representative_tickers=("LLY", "NVO", "PFE", "AMGN", "MRK", "JNJ", "ISRG", "BSX", "SYK", "ZTS"),
        product_taxonomy_scope=("approved drugs", "pipeline indications", "medical devices", "procedures", "clinical trials"),
        key_products_or_services=("approved products", "pipeline programs", "devices", "procedures", "animal health products"),
        l1_required_facts=("product sales if disclosed", "pipeline table", "R&D", "acquired IPR&D", "milestone obligations"),
        l1_financial_statement_focus=("product revenue", "R&D", "gross margin", "SG&A", "acquired IPR&D", "cash runway for biotech"),
        l1_company_disclosed_kpi_focus=("product sales", "procedure/device volumes if disclosed", "pipeline milestones"),
        l2_trusted_context_sources=("mainstream_financial_news", "official_press_releases", "medical_guidelines_where_public"),
        l2_regulatory_or_official_sources=("clinicaltrials_api", "openfda_api", "cms_public_data", "labels", "advisory_committee_materials"),
        l2_official_product_surface_sources=("company_product_pages", "company_ir_reports", "official_label_or_device_pages"),
        l3_proxy_sources=("public_tenders_contracts_orders", "job_postings_hiring_signals", "procedure_public_leads_where_available"),
        l4_discovery_sources=("patient_community_discussion_as_discovery_only", "common_crawl_index"),
        public_data_ceiling=("ClinicalTrials/openFDA/CMS support R&D/regulatory/use context, not prescriptions, utilization share, or sales unless company/official source states it",),
        expected_commercial_gaps=("IQVIA/Symphony scripts", "prescription share", "procedure volumes", "hospital channel sell-through"),
    ),
    LaneDefinition(
        lane_id="V5",
        lane_name="Auto / Mobility / Transport Platforms",
        industry_schema="auto_mobility",
        subvertical="auto_mobility_transport",
        company_archetype="vehicle_oem_battery_charging_autonomy_and_mobility_marketplace",
        representative_tickers=("TSLA", "GM", "F", "RIVN", "LCID", "TM", "MBG.DE", "UBER", "LYFT"),
        product_taxonomy_scope=("vehicle model", "platform", "battery/charging", "autonomy", "mobility marketplace"),
        key_products_or_services=("vehicle models", "EV platform", "charging network", "autonomy stack", "rideshare/delivery marketplace"),
        l1_required_facts=("deliveries", "ASP commentary if disclosed", "inventory", "warranty", "capex", "deferred revenue", "credits"),
        l1_financial_statement_focus=("deliveries/unit economics", "automotive gross margin", "inventory", "warranty", "capex", "regulatory credits", "platform take rate if disclosed"),
        l1_company_disclosed_kpi_focus=("deliveries", "production", "active users/trips if disclosed", "take rate if disclosed"),
        l2_trusted_context_sources=("mainstream_financial_news", "supplier_customer_official_news"),
        l2_regulatory_or_official_sources=("nhtsa_vpic_api", "recalls", "complaints", "regulatory_filings", "charging_network_official_data"),
        l2_official_product_surface_sources=("company_product_pages", "official_model_pages", "company_ir_reports"),
        l3_proxy_sources=("used_new_listing_proxy", "app_store_rankings", "job_postings_hiring_signals", "public_tenders_contracts_orders"),
        l4_discovery_sources=("owner_forums_as_recall_or_service_bulletin_lead_only", "common_crawl_index"),
        public_data_ceiling=("listings/app ranks/owner forums are proxy or discovery only, not sales, ASP, reliability rate, or profitability proof",),
        expected_commercial_gaps=("registration/VIO", "model share", "true used inventory", "owner demographics", "ride-level marketplace data"),
    ),
    LaneDefinition(
        lane_id="V6",
        lane_name="Banks / Financials / Capital Markets",
        industry_schema="financials_banks",
        subvertical="banks_financials_capital_markets",
        company_archetype="bank_broker_asset_manager_exchange_and_financial_platform",
        representative_tickers=("JPM", "BAC", "WFC", "C", "GS", "MS", "BLK", "SCHW", "CBOE"),
        product_taxonomy_scope=("net interest income", "deposits", "loans", "trading", "wealth/AUM", "capital markets", "exchange volumes"),
        key_products_or_services=("banking", "trading", "wealth management", "asset management", "exchange data/transactions"),
        l1_required_facts=("deposits", "loans", "NII", "charge-offs", "capital ratios", "AUM", "trading/capital markets revenue"),
        l1_financial_statement_focus=("net interest income", "deposit beta", "loan growth", "credit costs", "capital ratios", "AUM", "trading revenue"),
        l1_company_disclosed_kpi_focus=("deposits", "loans", "AUM/AUA", "trading metrics", "exchange volumes if disclosed"),
        l2_trusted_context_sources=("mainstream_financial_news", "regulatory_releases"),
        l2_regulatory_or_official_sources=("fdic_bankfind_api", "fred_api", "call_reports", "official_exchange_statistics"),
        l2_official_product_surface_sources=("company_ir_reports", "company_product_pages"),
        l3_proxy_sources=("app_store_rankings", "market_reaction_context"),
        l4_discovery_sources=("social_or_news_chatter_as_regulatory_event_discovery_only", "common_crawl_index"),
        public_data_ceiling=("FDIC/FRED and market data explain macro/regulatory context, not company revenue or real-time flows unless issuer/official statistics disclose it",),
        expected_commercial_gaps=("real-time flows", "private deposit migration", "advisor-channel detail", "consensus revision"),
    ),
    LaneDefinition(
        lane_id="V7",
        lane_name="Energy / Utilities / Industrials",
        industry_schema="energy_utilities",
        subvertical="energy_utilities_industrials_materials",
        company_archetype="asset_heavy_energy_utility_industrial_equipment_materials_and_power_infrastructure",
        representative_tickers=("XOM", "CVX", "COP", "SLB", "NEE", "DUK", "SO", "XEL", "ED", "GE", "CAT", "DE"),
        product_taxonomy_scope=("upstream/downstream", "oilfield services", "generation assets", "regulated utility territories", "industrial equipment", "power/datacenter infrastructure"),
        key_products_or_services=("oil/gas production", "utility rate base", "industrial equipment", "power equipment", "services/backlog"),
        l1_required_facts=("production", "reserves", "capex", "regulated rate base", "fuel costs", "backlog/order book if disclosed"),
        l1_financial_statement_focus=("capex", "asset base", "debt/liquidity", "working capital", "regulated returns", "backlog/orders", "commodity sensitivity"),
        l1_company_disclosed_kpi_focus=("production", "rate base", "backlog/orders", "equipment deliveries", "capacity/utilization if disclosed"),
        l2_trusted_context_sources=("mainstream_financial_news", "supplier_customer_official_news", "industry_association_reports"),
        l2_regulatory_or_official_sources=("eia_open_data", "ferc_state_utility_filings", "environmental_regulatory_data", "fred_api"),
        l2_official_product_surface_sources=("company_product_pages", "official_project_pages", "company_ir_reports"),
        l3_proxy_sources=("public_tenders_contracts_orders", "job_postings_hiring_signals", "dealer_channel_listings"),
        l4_discovery_sources=("local_chatter_as_project_or_regulatory_filing_lead_only", "common_crawl_index"),
        public_data_ceiling=("EIA/FRED/regulatory data are context/exposure bridges, not single-company revenue/margin proof unless the issuer discloses it",),
        expected_commercial_gaps=("asset-level utilization where not disclosed", "dealer sell-through", "private project economics", "equipment order pipeline"),
    ),
    LaneDefinition(
        lane_id="V8",
        lane_name="Retail / CPG / Restaurants / Travel",
        industry_schema="retail_cpg",
        subvertical="retail_cpg_restaurants_travel",
        company_archetype="store_channel_category_menu_traffic_membership_and_travel_marketplace",
        representative_tickers=("WMT", "COST", "TGT", "HD", "LOW", "PG", "KO", "PEP", "NKE", "SBUX", "MCD", "BKNG", "ABNB"),
        product_taxonomy_scope=("store/channel", "category mix", "menu/SKU", "pricing/promotion", "traffic", "membership/loyalty", "travel inventory"),
        key_products_or_services=("retail categories", "CPG brands", "restaurant menu", "travel marketplace", "membership/loyalty"),
        l1_required_facts=("same-store sales", "transactions", "ticket", "inventory", "gross margin", "advertising/promotional spend when disclosed"),
        l1_financial_statement_focus=("comparable sales", "gross margin", "inventory", "traffic/ticket", "advertising/promotion", "working capital", "loyalty/membership"),
        l1_company_disclosed_kpi_focus=("same-store sales", "transactions/ticket", "store count", "membership", "bookings/room nights if disclosed"),
        l2_trusted_context_sources=("mainstream_financial_news", "company_official_news", "census_retail_sales", "bls_cpi"),
        l2_regulatory_or_official_sources=("census_data_api", "bls_public_api", "fred_api"),
        l2_official_product_surface_sources=("company_product_pages", "official_menu_store_pages", "company_ir_reports"),
        l3_proxy_sources=("ecommerce_major_platforms", "app_store_rankings", "platform_reviews_rankings_downloads", "job_postings_hiring_signals"),
        l4_discovery_sources=("consumer_chatter_as_discovery_only", "common_crawl_index"),
        public_data_ceiling=("public listings/reviews/app ranks can support price/menu/attention context, not POS sell-through, product share, traffic, or channel inventory",),
        expected_commercial_gaps=("Circana/NielsenIQ POS", "scanner/panel data", "traffic trackers", "private booking conversion", "promotion/channel inventory"),
    ),
)

LANE_BY_ID = {lane.lane_id: lane for lane in LANE_DEFINITIONS}

PRIMARY_LANE_OVERRIDES = {
    "1211.HK": "V5",
    "AAPL": "V2",
    "ADP": "V3",
    "ADSK": "V3",
    "AMZN": "V3",
    "AZO": "V8",
    "GOOGL": "V3",
    "MSFT": "V3",
    "DELL": "V1",
    "HPE": "V1",
    "HPQ": "V2",
    "ABNB": "V8",
    "ORLY": "V8",
    "ROK": "V7",
    "UBER": "V5",
    "LYFT": "V5",
    "LI": "V5",
    "NIO": "V5",
    "XPEV": "V5",
}


def build_vertical_source_lane_registry(
    *,
    universe_rows: Iterable[Mapping[str, Any]],
    product_nodes: Iterable[Mapping[str, Any]] | None = None,
    product_gaps: Iterable[Mapping[str, Any]] | None = None,
    product_metric_rows: Iterable[Mapping[str, Any]] | None = None,
    official_product_rows: Iterable[Mapping[str, Any]] | None = None,
    source_capability_rows: Iterable[Mapping[str, Any]] | Mapping[str, Any] | None = None,
    generated_at: str | None = None,
    input_paths: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or _utc_now()
    companies = _normalize_universe_rows(universe_rows)
    product_summary = _build_product_summary(
        product_nodes=product_nodes or (),
        product_gaps=product_gaps or (),
        product_metric_rows=product_metric_rows or (),
        official_product_rows=official_product_rows or (),
    )
    assignments = [
        _assign_company(company, product_summary=product_summary)
        for company in companies
    ]
    lanes = [
        _lane_payload(
            lane,
            assignments=[item for item in assignments if item["primary_lane_id"] == lane.lane_id or lane.lane_id in item.get("secondary_lane_ids", [])],
            primary_assignments=[item for item in assignments if item["primary_lane_id"] == lane.lane_id],
            product_summary=product_summary,
            source_capability_rows=source_capability_rows,
            generated_at=generated_at,
        )
        for lane in LANE_DEFINITIONS
    ]
    validation = validate_vertical_source_lane_registry(assignments=assignments, lanes=lanes, company_count=len(companies))
    payload = {
        "schema_version": VERTICAL_SOURCE_LANE_REGISTRY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "policy": "lane_first_l1_l3_expansion_with_l4_discovery_only_boundary_v0_1",
        "input_paths": dict(input_paths or {}),
        "company_count": len(companies),
        "lane_count": len(lanes),
        "summary": _registry_summary(assignments, lanes),
        "lane_definitions": [_lane_definition_dict(lane) for lane in LANE_DEFINITIONS],
        "lanes": lanes,
        "company_assignments": assignments,
        "validation": validation,
        "registry_digest": _digest({"lanes": lanes, "company_assignments": assignments}),
    }
    return payload


def validate_vertical_source_lane_registry(
    *,
    assignments: Sequence[Mapping[str, Any]],
    lanes: Sequence[Mapping[str, Any]],
    company_count: int,
) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    if len(assignments) != company_count:
        errors.append({"type": "assignment_count_mismatch", "assignment_count": len(assignments), "company_count": company_count})
    lane_ids = {lane.lane_id for lane in LANE_DEFINITIONS}
    seen: set[str] = set()
    for item in assignments:
        ticker = str(item.get("ticker") or "")
        if not ticker:
            errors.append({"type": "assignment_missing_ticker", "row": dict(item)})
            continue
        if ticker in seen:
            errors.append({"type": "duplicate_ticker_assignment", "ticker": ticker})
        seen.add(ticker)
        primary = str(item.get("primary_lane_id") or "")
        if primary not in lane_ids:
            errors.append({"type": "invalid_primary_lane", "ticker": ticker, "primary_lane_id": primary})
        for secondary in item.get("secondary_lane_ids") or []:
            if secondary not in lane_ids:
                errors.append({"type": "invalid_secondary_lane", "ticker": ticker, "secondary_lane_id": secondary})
        if not item.get("lane_source_requirements"):
            errors.append({"type": "assignment_missing_lane_source_requirements", "ticker": ticker})
    for lane in lanes:
        if str(lane.get("lane_id") or "") not in lane_ids:
            errors.append({"type": "invalid_lane_payload", "lane_id": lane.get("lane_id")})
        if not lane.get("completion_gates"):
            errors.append({"type": "lane_missing_completion_gates", "lane_id": lane.get("lane_id")})
        if not lane.get("public_data_ceiling"):
            errors.append({"type": "lane_missing_public_data_ceiling", "lane_id": lane.get("lane_id")})
    return {
        "schema_version": "finsight_vertical_source_lane_registry_validation_v0_1",
        "status": "fail" if errors else "pass",
        "errors": errors,
    }


def write_vertical_source_lane_registry(
    payload: Mapping[str, Any],
    *,
    output_json_path: str | Path = "data/manifests/vertical_source_lane_registry_v0_1.json",
    output_jsonl_path: str | Path = "data/manifests/vertical_source_lane_company_assignments_v0_1.jsonl",
    output_report_path: str | Path = "docs/internal/vnext_20260610/vertical_source_lane_registry.zh-CN.md",
) -> dict[str, str]:
    json_path = Path(output_json_path)
    jsonl_path = Path(output_jsonl_path)
    report_path = Path(output_report_path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    assignments = [row for row in payload.get("company_assignments") or [] if isinstance(row, Mapping)]
    jsonl_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in assignments),
        encoding="utf-8",
    )
    report_path.write_text(render_vertical_source_lane_registry_report(payload), encoding="utf-8")
    return {"registry": str(json_path), "assignments": str(jsonl_path), "report": str(report_path)}


def render_vertical_source_lane_registry_report(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Vertical Source Lane Registry",
        "",
        f"- schema_version: `{payload.get('schema_version')}`",
        f"- generated_at: `{payload.get('generated_at')}`",
        f"- status: `{(payload.get('validation') or {}).get('status')}`",
        f"- company_count: `{payload.get('company_count')}`",
        f"- registry_digest: `{payload.get('registry_digest')}`",
        "",
        "## Lane Summary",
        "",
        "| lane | primary tickers | all tickers | product KPI ready | official surface ready | commercial gaps | coverage gate |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for lane in payload.get("lanes") or []:
        if not isinstance(lane, Mapping):
            continue
        coverage = lane.get("lane_source_coverage_gate") if isinstance(lane.get("lane_source_coverage_gate"), Mapping) else {}
        product = lane.get("product_coverage_summary") if isinstance(lane.get("product_coverage_summary"), Mapping) else {}
        gaps = lane.get("gap_summary") if isinstance(lane.get("gap_summary"), Mapping) else {}
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{lane.get('lane_id')}` {lane.get('lane_name')}",
                    str(lane.get("primary_ticker_count") or 0),
                    str(lane.get("ticker_count") or 0),
                    str(product.get("product_kpi_ready_ticker_count") or 0),
                    str(product.get("official_product_surface_ticker_count") or 0),
                    str(gaps.get("commercial_gap_count") or 0),
                    str(coverage.get("status") or "not_run"),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Lane Details", ""])
    for lane in payload.get("lanes") or []:
        if not isinstance(lane, Mapping):
            continue
        lines.extend(
            [
                f"### {lane.get('lane_id')} {lane.get('lane_name')}",
                "",
                f"- industry_schema: `{lane.get('industry_schema')}`",
                f"- primary_ticker_count: `{lane.get('primary_ticker_count')}`",
                f"- secondary_inclusive_ticker_count: `{lane.get('ticker_count')}`",
                f"- representative_tickers: `{', '.join(lane.get('representative_tickers') or [])}`",
                f"- product_taxonomy_scope: `{', '.join(lane.get('product_taxonomy_scope') or [])}`",
                f"- public_data_ceiling: `{'; '.join(lane.get('public_data_ceiling') or [])}`",
                f"- expected_commercial_gaps: `{'; '.join(lane.get('expected_commercial_gaps') or [])}`",
                "",
            ]
        )
        coverage = lane.get("lane_source_coverage_gate") if isinstance(lane.get("lane_source_coverage_gate"), Mapping) else {}
        if coverage:
            summary = coverage.get("summary") if isinstance(coverage.get("summary"), Mapping) else {}
            lines.append(
                f"- coverage_gate: `{coverage.get('status')}`; requirements=`{summary.get('requirement_count')}`; gaps=`{summary.get('gap_requirement_count')}`; fail=`{summary.get('fail_requirement_count')}`"
            )
        for key in ("l1_required_facts", "l2_trusted_context_sources", "l3_proxy_sources", "l4_discovery_sources"):
            lines.append(f"- {key}: `{', '.join(lane.get(key) or [])}`")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def load_csv_rows(path: str | Path) -> list[dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        return []
    with p.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def load_jsonl_rows(path: str | Path) -> list[dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        return []
    rows: list[dict[str, Any]] = []
    with p.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            value = json.loads(line)
            if isinstance(value, dict):
                rows.append(value)
    return rows


def _normalize_universe_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    companies: dict[str, dict[str, Any]] = {}
    for row in rows:
        ticker = _ticker(row.get("ticker") or row.get("symbol") or row.get("provider_symbol"))
        if not ticker:
            continue
        company = companies.setdefault(
            ticker,
            {
                "ticker": ticker,
                "provider_symbol": str(row.get("provider_symbol") or ticker).strip(),
                "company_name": str(row.get("company_name") or row.get("company") or row.get("name") or "").strip(),
                "sector": str(row.get("sector") or "").strip(),
                "category": str(row.get("category") or "").strip(),
                "universe_tier": str(row.get("universe_tier") or "").strip(),
                "country": str(row.get("country") or "").strip(),
                "listing_exchange": str(row.get("listing_exchange") or "").strip(),
                "reporting_currency": str(row.get("reporting_currency") or "").strip(),
                "market_region": str(row.get("market_region") or "").strip(),
                "sec_download_eligible": _bool(row.get("sec_download_eligible")),
                "global_public_download_eligible": _bool(row.get("global_public_download_eligible")),
                "source_sets": _split_tokens(row.get("source_sets")),
                "source_policy": str(row.get("source_policy") or "").strip(),
            },
        )
        for key in ("company_name", "sector", "category", "universe_tier", "country", "listing_exchange", "reporting_currency", "market_region", "source_policy"):
            if not company.get(key) and row.get(key):
                company[key] = str(row.get(key) or "").strip()
        company["sec_download_eligible"] = bool(company.get("sec_download_eligible") or _bool(row.get("sec_download_eligible")))
        company["global_public_download_eligible"] = bool(company.get("global_public_download_eligible") or _bool(row.get("global_public_download_eligible")))
        company["source_sets"] = sorted(set(company.get("source_sets") or []) | set(_split_tokens(row.get("source_sets"))))
    return [companies[ticker] for ticker in sorted(companies)]


def _build_product_summary(
    *,
    product_nodes: Iterable[Mapping[str, Any]],
    product_gaps: Iterable[Mapping[str, Any]],
    product_metric_rows: Iterable[Mapping[str, Any]],
    official_product_rows: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    by_ticker: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "product_node_count": 0,
        "product_sources": Counter(),
        "product_industry_schemas": Counter(),
        "node_layers": Counter(),
        "promotion_statuses": Counter(),
        "product_kpi_ready": False,
        "official_surface_ready": False,
        "commercial_gap_count": 0,
        "gap_types": Counter(),
        "missing_metrics": Counter(),
        "commercial_sources": Counter(),
    })
    for row in product_nodes:
        ticker = _ticker(row.get("ticker"))
        if not ticker:
            continue
        item = by_ticker[ticker]
        item["product_node_count"] += 1
        _counter_add(item["product_sources"], row.get("source_id"))
        _counter_add(item["product_industry_schemas"], row.get("industry_schema"))
        _counter_add(item["node_layers"], row.get("evidence_layer"))
        status = str(row.get("promotion_status") or "")
        _counter_add(item["promotion_statuses"], status)
        if status == "runtime_fact_allowed" or str(row.get("evidence_layer") or "") == "company_disclosed_verified_product_kpi":
            item["product_kpi_ready"] = True
        if str(row.get("evidence_layer") or "") == "official_company_product_surface" or str(row.get("source_id") or "") == "company_product_pages":
            item["official_surface_ready"] = True
    for row in product_metric_rows:
        ticker = _ticker(row.get("ticker") or row.get("issuer_ticker"))
        if ticker:
            by_ticker[ticker]["product_kpi_ready"] = True
            _counter_add(by_ticker[ticker]["node_layers"], "runtime_product_kpi_row")
    for row in official_product_rows:
        ticker = _ticker(row.get("ticker") or row.get("issuer_ticker"))
        if ticker:
            by_ticker[ticker]["official_surface_ready"] = True
            _counter_add(by_ticker[ticker]["node_layers"], "runtime_official_product_surface_row")
            _counter_add(by_ticker[ticker]["product_sources"], row.get("source_id") or "company_product_pages")
    for row in product_gaps:
        ticker = _ticker(row.get("ticker"))
        if not ticker:
            continue
        item = by_ticker[ticker]
        gap_type = str(row.get("gap_type") or "unknown")
        item["gap_types"][gap_type] += 1
        if "commercial" in gap_type:
            item["commercial_gap_count"] += 1
        _counter_add(item["missing_metrics"], row.get("missing_metric"))
        for source in _list(row.get("commercial_sources_that_would_fill")):
            _counter_add(item["commercial_sources"], source)
    return {
        ticker: {
            "product_node_count": int(item["product_node_count"]),
            "product_sources": dict(sorted(item["product_sources"].items())),
            "product_industry_schemas": dict(sorted(item["product_industry_schemas"].items())),
            "node_layers": dict(sorted(item["node_layers"].items())),
            "promotion_statuses": dict(sorted(item["promotion_statuses"].items())),
            "product_kpi_ready": bool(item["product_kpi_ready"]),
            "official_surface_ready": bool(item["official_surface_ready"]),
            "commercial_gap_count": int(item["commercial_gap_count"]),
            "gap_types": dict(sorted(item["gap_types"].items())),
            "missing_metrics": dict(sorted(item["missing_metrics"].items())),
            "commercial_sources": dict(sorted(item["commercial_sources"].items())),
        }
        for ticker, item in by_ticker.items()
    }


def _assign_company(company: Mapping[str, Any], *, product_summary: Mapping[str, Any]) -> dict[str, Any]:
    ticker = _ticker(company.get("ticker"))
    primary, reason = _primary_lane_for_company(company)
    secondary = _secondary_lanes_for_company(company, primary_lane=primary)
    lane = LANE_BY_ID[primary]
    product = dict(product_summary.get(ticker) or {})
    product_status = "product_kpi_ready" if product.get("product_kpi_ready") else (
        "official_surface_context_ready" if product.get("official_surface_ready") else (
            "taxonomy_or_context_nodes_ready" if product.get("product_node_count") else "product_context_gap"
        )
    )
    return {
        "schema_version": "finsight_vertical_source_lane_assignment_v0_1",
        "ticker": ticker,
        "provider_symbol": str(company.get("provider_symbol") or ticker),
        "company_name": str(company.get("company_name") or ""),
        "sector": str(company.get("sector") or ""),
        "category": str(company.get("category") or ""),
        "country": str(company.get("country") or ""),
        "market_region": str(company.get("market_region") or ""),
        "universe_tier": str(company.get("universe_tier") or ""),
        "sec_download_eligible": bool(company.get("sec_download_eligible")),
        "global_public_download_eligible": bool(company.get("global_public_download_eligible")),
        "primary_lane_id": primary,
        "primary_lane_name": lane.lane_name,
        "secondary_lane_ids": secondary,
        "lane_assignment_reason": reason,
        "product_taxonomy_status": product_status,
        "product_coverage": product,
        "lane_source_requirements": {
            "L1_required_facts": list(lane.l1_required_facts),
            "L2_sources": sorted(set(lane.l2_trusted_context_sources + lane.l2_regulatory_or_official_sources + lane.l2_official_product_surface_sources)),
            "L3_sources": list(lane.l3_proxy_sources),
            "L4_sources": list(lane.l4_discovery_sources),
        },
        "public_data_ceiling": list(lane.public_data_ceiling),
        "expected_commercial_gaps": list(lane.expected_commercial_gaps),
    }


def _primary_lane_for_company(company: Mapping[str, Any]) -> tuple[str, str]:
    ticker = _ticker(company.get("ticker"))
    text = " ".join(
        str(company.get(key) or "").lower()
        for key in ("ticker", "provider_symbol", "company_name", "sector", "category", "country", "market_region", "source_sets")
    )
    if ticker in PRIMARY_LANE_OVERRIDES:
        return PRIMARY_LANE_OVERRIDES[ticker], "primary_lane_manual_override_for_cross_lane_representative"
    representative_matches = [lane.lane_id for lane in LANE_DEFINITIONS if ticker in lane.representative_tickers]
    if len(representative_matches) == 1:
        return representative_matches[0], "representative_ticker_override"
    if _has_any(text, "semiconductor", "semi", "memory", "foundry", "server_odm", "ai server", "networking", "semicap", "chip", "electronics_manufacturing_services"):
        return "V1", "category_keyword_semiconductor_or_ai_infrastructure"
    if _has_any(text, "software", "saas", "cloud", "cyber", "data platform", "internet", "interactive media", "communication services"):
        return "V3", "category_keyword_software_cloud_or_internet"
    if _has_any(text, "consumer electronics", "pc", "hardware", "device", "gaming"):
        return "V2", "category_keyword_consumer_hardware"
    if _has_any(text, "health care", "healthcare", "pharma", "biotech", "medtech", "medical", "life sciences"):
        return "V4", "sector_or_category_healthcare"
    if _has_auto_lane_signal(text):
        return "V5", "category_keyword_auto_mobility"
    if _has_any(text, "financial", "bank", "capital markets", "insurance", "asset management", "broker", "exchange"):
        return "V6", "sector_or_category_financials"
    if _has_any(text, "energy", "utility", "utilities", "industrial", "industrials", "materials", "power", "thermal", "machinery", "aerospace", "construction"):
        return "V7", "sector_or_category_energy_utilities_industrials"
    if _has_any(text, "retail", "cpg", "consumer staples", "restaurant", "travel", "hotel", "apparel", "food", "beverage", "home improvement", "consumer discretionary"):
        return "V8", "sector_or_category_retail_cpg_travel"
    if _has_any(text, "information technology"):
        return "V3", "sector_fallback_information_technology"
    if _has_any(text, "consumer"):
        return "V8", "sector_fallback_consumer"
    return "V7", "generic_asset_or_industrial_fallback"


def _secondary_lanes_for_company(company: Mapping[str, Any], *, primary_lane: str) -> list[str]:
    ticker = _ticker(company.get("ticker"))
    text = " ".join(
        str(company.get(key) or "").lower()
        for key in ("ticker", "provider_symbol", "company_name", "sector", "category")
    )
    secondary: set[str] = set()
    if ticker in {"MSFT", "AMZN", "GOOGL", "META", "ORCL"}:
        secondary.add("V1")
    if ticker in {"AAPL", "MSFT", "GOOGL", "DELL", "HPQ", "SONY", "SSNLF"}:
        secondary.add("V2")
    if ticker in {"AAPL", "AMZN", "GOOGL", "META", "NFLX", "BKNG", "ABNB"}:
        secondary.add("V3")
    if ticker in {"ABNB", "BKNG", "UBER", "LYFT"}:
        secondary.add("V8")
    if _has_any(text, "battery", "power", "thermal", "datacenter", "data center"):
        secondary.add("V1")
        secondary.add("V7")
    secondary.discard(primary_lane)
    return sorted(secondary)


def _lane_payload(
    lane: LaneDefinition,
    *,
    assignments: Sequence[Mapping[str, Any]],
    primary_assignments: Sequence[Mapping[str, Any]],
    product_summary: Mapping[str, Any],
    source_capability_rows: Iterable[Mapping[str, Any]] | Mapping[str, Any] | None,
    generated_at: str,
) -> dict[str, Any]:
    tickers = sorted({str(item.get("ticker") or "") for item in assignments if item.get("ticker")})
    primary_tickers = sorted({str(item.get("ticker") or "") for item in primary_assignments if item.get("ticker")})
    coverage_gate = build_source_coverage_gate(
        industry_schema=lane.industry_schema,
        phase="registry",
        source_layer_capability=source_capability_rows,
        generated_at=generated_at,
    )
    product_coverage = _lane_product_coverage(primary_tickers, product_summary)
    gap_summary = _lane_gap_summary(primary_tickers, product_summary)
    return {
        "schema_version": "finsight_vertical_source_lane_v0_1",
        "lane_id": lane.lane_id,
        "lane_name": lane.lane_name,
        "industry_schema": lane.industry_schema,
        "subvertical": lane.subvertical,
        "company_archetype": lane.company_archetype,
        "ticker_count": len(tickers),
        "primary_ticker_count": len(primary_tickers),
        "ticker_universe": tickers,
        "primary_ticker_universe": primary_tickers,
        "representative_tickers": [ticker for ticker in lane.representative_tickers if ticker in set(tickers) or ticker in set(primary_tickers)] or list(lane.representative_tickers),
        "product_taxonomy_scope": list(lane.product_taxonomy_scope),
        "key_products_or_services": list(lane.key_products_or_services),
        "l1_required_facts": list(lane.l1_required_facts),
        "l1_financial_statement_focus": list(lane.l1_financial_statement_focus),
        "l1_company_disclosed_kpi_focus": list(lane.l1_company_disclosed_kpi_focus),
        "l2_trusted_context_sources": list(lane.l2_trusted_context_sources),
        "l2_regulatory_or_official_sources": list(lane.l2_regulatory_or_official_sources),
        "l2_official_product_surface_sources": list(lane.l2_official_product_surface_sources),
        "l3_proxy_sources": list(lane.l3_proxy_sources),
        "l4_discovery_sources": list(lane.l4_discovery_sources),
        "public_data_ceiling": list(lane.public_data_ceiling),
        "expected_commercial_gaps": list(lane.expected_commercial_gaps),
        "analyst_playbook_path": f"docs/internal/vnext_20260610/vertical_lanes/{lane.lane_id.lower()}_analyst_playbook.zh-CN.md",
        "source_playbook_path": f"docs/internal/vnext_20260610/vertical_lanes/{lane.lane_id.lower()}_source_playbook.zh-CN.md",
        "product_coverage_summary": product_coverage,
        "gap_summary": gap_summary,
        "lane_source_coverage_gate": coverage_gate,
        "completion_gates": [
            "primary_ticker_universe_frozen",
            "l1_filing_financial_and_company_kpi_status_by_ticker_recorded",
            "product_taxonomy_or_official_surface_status_by_ticker_recorded",
            "lane_required_l2_routes_ready_or_gap_classified",
            "lane_required_l3_routes_ready_or_gap_classified",
            "l4_only_lead_exclusion_or_repair_attempt",
            "source_coverage_gate_auditable",
            "2_to_3_representative_cases_pass_dimension_judgment_gate",
        ],
    }


def _lane_product_coverage(primary_tickers: Sequence[str], product_summary: Mapping[str, Any]) -> dict[str, Any]:
    ready = [ticker for ticker in primary_tickers if (product_summary.get(ticker) or {}).get("product_kpi_ready")]
    official = [ticker for ticker in primary_tickers if (product_summary.get(ticker) or {}).get("official_surface_ready")]
    any_nodes = [ticker for ticker in primary_tickers if (product_summary.get(ticker) or {}).get("product_node_count")]
    return {
        "primary_ticker_count": len(primary_tickers),
        "product_kpi_ready_ticker_count": len(ready),
        "official_product_surface_ticker_count": len(official),
        "product_context_node_ticker_count": len(any_nodes),
        "product_context_gap_ticker_count": max(0, len(primary_tickers) - len(any_nodes)),
        "sample_product_kpi_ready_tickers": ready[:20],
        "sample_official_product_surface_tickers": official[:20],
    }


def _lane_gap_summary(primary_tickers: Sequence[str], product_summary: Mapping[str, Any]) -> dict[str, Any]:
    gap_types: Counter[str] = Counter()
    missing_metrics: Counter[str] = Counter()
    commercial_sources: Counter[str] = Counter()
    commercial_count = 0
    for ticker in primary_tickers:
        item = product_summary.get(ticker) or {}
        commercial_count += int(item.get("commercial_gap_count") or 0)
        gap_types.update(dict(item.get("gap_types") or {}))
        missing_metrics.update(dict(item.get("missing_metrics") or {}))
        commercial_sources.update(dict(item.get("commercial_sources") or {}))
    return {
        "commercial_gap_count": commercial_count,
        "gap_types": dict(sorted(gap_types.items())),
        "missing_metrics_top": dict(missing_metrics.most_common(12)),
        "commercial_sources_top": dict(commercial_sources.most_common(12)),
    }


def _registry_summary(assignments: Sequence[Mapping[str, Any]], lanes: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    by_primary = Counter(str(item.get("primary_lane_id") or "") for item in assignments)
    by_sector = Counter(str(item.get("sector") or "") for item in assignments)
    non_us = [item for item in assignments if str(item.get("market_region") or "").lower().startswith("non_us") or bool(item.get("global_public_download_eligible"))]
    return {
        "by_primary_lane": dict(sorted(by_primary.items())),
        "by_sector": dict(sorted(by_sector.items())),
        "non_us_or_global_public_company_count": len(non_us),
        "source_coverage_gate_status_by_lane": {
            str(lane.get("lane_id")): ((lane.get("lane_source_coverage_gate") or {}).get("status") if isinstance(lane.get("lane_source_coverage_gate"), Mapping) else "not_run")
            for lane in lanes
        },
    }


def _lane_definition_dict(lane: LaneDefinition) -> dict[str, Any]:
    return {
        "lane_id": lane.lane_id,
        "lane_name": lane.lane_name,
        "industry_schema": lane.industry_schema,
        "subvertical": lane.subvertical,
        "company_archetype": lane.company_archetype,
        "representative_tickers": list(lane.representative_tickers),
        "product_taxonomy_scope": list(lane.product_taxonomy_scope),
        "key_products_or_services": list(lane.key_products_or_services),
    }


def _counter_add(counter: Counter[str], value: Any) -> None:
    text = str(value or "").strip()
    if text:
        counter[text] += 1


def _ticker(value: Any) -> str:
    return str(value or "").upper().strip()


def _split_tokens(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in re.split(r"[|,;]", value) if part.strip()]
    if isinstance(value, Iterable) and not isinstance(value, (bytes, Mapping)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Iterable) and not isinstance(value, (bytes, Mapping)):
        return [str(item) for item in value if str(item).strip()]
    return [str(value)]


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _has_any(text: str, *terms: str) -> bool:
    return any(term in text for term in terms)


def _has_auto_lane_signal(text: str) -> bool:
    if _has_any(text, "transport platform", "electric vehicle", "ev maker", "vehicle oem"):
        return True
    return bool(
        re.search(
            r"\b(automotive|mobility|vehicles?|cars?|trucks?|motors?|battery|batteries)\b",
            text,
        )
    )


def _digest(value: Any) -> str:
    data = json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha1(data).hexdigest()[:16]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
