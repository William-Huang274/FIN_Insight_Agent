from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from sec_agent.source_coverage_gate import SOURCE_CLASS_TO_SOURCE_ID


PRODUCT_FAMILY_LANE_REGISTRY_SCHEMA_VERSION = "finsight_product_family_lane_registry_v0_1"
COMPANY_PRODUCT_FAMILY_ASSIGNMENT_SCHEMA_VERSION = "finsight_company_product_family_assignment_v0_1"
FAMILY_SOURCE_ROUTE_PLAN_SCHEMA_VERSION = "finsight_family_source_route_plan_v0_1"
FAMILY_SOURCE_FETCH_AUDIT_SCHEMA_VERSION = "finsight_family_source_fetch_audit_v0_1"


COMMON_FORBIDDEN_CLAIMS = [
    "market_share_without_tracker_or_company_disclosure",
    "shipments_without_company_or_official_registration_data",
    "sell_through_or_channel_inventory_from_public_proxy",
    "undisclosed_product_revenue",
    "commercial_tracker_estimate_from_public_proxy",
]


WEAK_FAMILY_MATCH_TERMS = {
    "arm",
    "automotive",
    "cloud",
    "component",
    "compute",
    "data",
    "device",
    "brand",
    "brands",
    "hardware",
    "ip",
    "node",
    "power",
    "production",
    "property",
    "rack",
    "regulator",
    "regulated",
    "retail",
    "server",
    "services",
    "store",
    "storage",
    "subscription",
    "surface",
    "mobility",
    "truck",
    "vehicle",
    "generation",
    "transmission",
    "media",
    "content",
    "advertising",
    "equipment",
    "engine",
    "construction",
    "grocery",
    "material",
    "materials",
    "chemical",
    "chemicals",
}

SHORT_STRONG_FAMILY_MATCH_TERMS = {
    "aum",
    "crm",
    "dr",
    "dram",
    "duv",
    "eda",
    "euv",
    "ev",
    "gpu",
    "hbm",
    "nic",
    "ssd",
    "ups",
}


FAMILY_ASSIGNMENT_SOURCE_IDS = {
    "company_ir_reports",
    "company_product_pages",
    "company_reported_product_operating_metrics",
    "sec_product_taxonomy_normalized",
    "sec_edgar_apis",
}


def _family(
    lane_id: str,
    family_id: str,
    family_name: str,
    *,
    aliases: Sequence[str],
    representative_tickers: Sequence[str],
    route_ids: Sequence[str],
    query_terms: Sequence[str],
    fallback: bool = False,
) -> dict[str, Any]:
    return {
        "family_id": family_id,
        "family_name": family_name,
        "lane_id": lane_id,
        "aliases": list(aliases),
        "representative_tickers": [str(ticker).upper() for ticker in representative_tickers],
        "route_ids": list(route_ids),
        "query_terms": list(query_terms),
        "fallback": fallback,
        "claim_boundary": "Family-scoped public source context; follow each route boundary before company claims.",
        "forbidden_claims": list(COMMON_FORBIDDEN_CLAIMS),
    }


FAMILY_DEFINITIONS: tuple[dict[str, Any], ...] = (
    # V1 Semiconductors / AI infrastructure.
    _family(
        "V1",
        "gpu_accelerator",
        "GPU / Accelerator",
        aliases=["gpu", "accelerator", "ai accelerator", "cuda", "blackwell", "h100", "gb200", "mi300", "instinct", "data center gpu"],
        representative_tickers=["NVDA", "AMD", "INTC"],
        route_ids=["primary_company_disclosure", "official_product_surface", "developer_ecosystem_proxy", "channel_offer_proxy", "public_order_proxy", "technology_research_proxy", "trusted_external_context"],
        query_terms=["GPU", "AI accelerator", "CUDA", "Blackwell", "H100", "MI300"],
    ),
    _family(
        "V1",
        "eda_ip",
        "EDA / IP",
        aliases=["eda", "design automation", "ip", "arm", "synopsys", "cadence", "verification", "emulation"],
        representative_tickers=["SNPS", "CDNS", "ARM"],
        route_ids=["primary_company_disclosure", "official_product_surface", "developer_ecosystem_proxy", "technology_research_proxy", "trusted_external_context"],
        query_terms=["EDA", "semiconductor IP", "verification", "emulation", "chip design software"],
    ),
    _family(
        "V1",
        "foundry",
        "Foundry / Wafer Fabrication",
        aliases=["foundry", "wafer", "fab", "process technology", "advanced logic", "advanced packaging", "nanometer", "node"],
        representative_tickers=["TSM", "INTC", "005930.KS"],
        route_ids=["primary_company_disclosure", "official_product_surface", "macro_official_context", "technology_research_proxy", "trusted_external_context"],
        query_terms=["foundry", "wafer", "process technology", "advanced packaging", "capacity"],
    ),
    _family(
        "V1",
        "semicap_equipment",
        "Semicap Equipment",
        aliases=["lithography", "euv", "duv", "etch", "deposition", "metrology", "inspection", "wafer fabrication equipment", "semicap"],
        representative_tickers=["ASML", "AMAT", "LRCX", "KLAC", "ACLS", "AEHR", "CAMT"],
        route_ids=["primary_company_disclosure", "official_product_surface", "supply_chain_official_relationship", "public_order_proxy", "technology_research_proxy", "trusted_external_context"],
        query_terms=["EUV", "lithography", "etch", "deposition", "metrology", "inspection", "semiconductor equipment"],
    ),
    _family(
        "V1",
        "memory",
        "Memory / Storage Semiconductors",
        aliases=["memory", "dram", "nand", "hbm", "ssd", "storage semiconductor"],
        representative_tickers=["MU", "000660.KS", "005930.KS", "WDC", "STX"],
        route_ids=["primary_company_disclosure", "official_product_surface", "macro_official_context", "trusted_external_context", "technology_research_proxy"],
        query_terms=["DRAM", "NAND", "HBM", "memory", "SSD"],
    ),
    _family(
        "V1",
        "networking",
        "Datacenter Networking / Connectivity",
        aliases=["networking", "ethernet", "switch", "router", "nic", "dpu", "infiniband", "connectx", "optical"],
        representative_tickers=["ANET", "AVGO", "MRVL", "NVDA", "CSCO"],
        route_ids=["primary_company_disclosure", "official_product_surface", "developer_ecosystem_proxy", "channel_offer_proxy", "public_order_proxy", "trusted_external_context"],
        query_terms=["datacenter networking", "Ethernet switch", "NIC", "DPU", "optical networking"],
    ),
    _family(
        "V1",
        "analog_embedded_semiconductors",
        "Analog / Embedded / Connectivity Semiconductors",
        aliases=["analog semiconductor", "embedded processing", "microcontroller", "mcu", "power management ic", "automotive semiconductor", "connectivity semiconductor", "rf semiconductor"],
        representative_tickers=["ADI", "TXN", "MCHP", "NXPI", "ON", "IFX.DE"],
        route_ids=["primary_company_disclosure", "official_product_surface", "developer_ecosystem_proxy", "technology_research_proxy", "trusted_external_context"],
        query_terms=["analog semiconductor", "embedded processing", "microcontroller", "automotive semiconductor"],
    ),
    _family(
        "V1",
        "server_oem",
        "AI Server / Rack OEM",
        aliases=["server", "rack", "ai server", "poweredge", "proliant", "supermicro", "infrastructure solutions"],
        representative_tickers=["DELL", "SMCI", "HPE", "LNVGY", "HPQ"],
        route_ids=["primary_company_disclosure", "official_product_surface", "channel_offer_proxy", "public_order_proxy", "supply_chain_official_relationship", "trusted_external_context"],
        query_terms=["AI server", "rack server", "GPU server", "PowerEdge", "ProLiant"],
    ),
    _family(
        "V1",
        "electronics_manufacturing_services",
        "Electronics Manufacturing / ODM",
        aliases=["electronics manufacturing", "ems", "odm", "contract manufacturing", "manufacturing services", "server manufacturing", "assembly"],
        representative_tickers=["2317.TW", "2382.TW", "3231.TW", "JBL"],
        route_ids=["primary_company_disclosure", "official_product_surface", "supply_chain_official_relationship", "public_order_proxy", "trusted_external_context"],
        query_terms=["electronics manufacturing", "ODM", "EMS", "contract manufacturing", "assembly"],
    ),
    _family(
        "V1",
        "power_cooling",
        "Datacenter Power / Cooling",
        aliases=["power", "cooling", "thermal", "ups", "electrical", "datacenter infrastructure", "liquid cooling"],
        representative_tickers=["VRT", "ETN", "PWR", "GE", "HUBB"],
        route_ids=["primary_company_disclosure", "official_product_surface", "public_order_proxy", "hiring_capacity_proxy", "macro_official_context", "trusted_external_context"],
        query_terms=["datacenter power", "cooling", "thermal management", "UPS", "liquid cooling"],
    ),
    _family(
        "V1",
        "v1_general_ai_infrastructure",
        "General AI Infrastructure Component",
        aliases=["semiconductor", "ai infrastructure", "hardware", "component"],
        representative_tickers=[],
        route_ids=["primary_company_disclosure", "official_product_surface", "trusted_external_context", "macro_official_context"],
        query_terms=["AI infrastructure", "semiconductor", "hardware component"],
        fallback=True,
    ),
    # V2 consumer hardware.
    _family("V2", "smartphones_tablets", "Smartphones / Tablets", aliases=["iphone", "smartphone", "phone", "tablet", "ipad", "mobile device"], representative_tickers=["AAPL", "SSNLF"], route_ids=["primary_company_disclosure", "official_product_surface", "channel_offer_proxy", "app_rank_store_proxy", "trusted_external_context"], query_terms=["smartphone", "iPhone", "tablet"]),
    _family("V2", "pcs_peripherals", "PCs / Peripherals", aliases=["pc", "mac", "surface", "notebook", "laptop", "printer", "peripheral"], representative_tickers=["AAPL", "MSFT", "DELL", "HPQ", "LNVGY"], route_ids=["primary_company_disclosure", "official_product_surface", "channel_offer_proxy", "platform_review_proxy", "trusted_external_context"], query_terms=["PC", "laptop", "notebook", "desktop", "printer"]),
    _family("V2", "gaming_devices", "Gaming Devices", aliases=["gaming", "xbox", "playstation", "console"], representative_tickers=["MSFT", "SONY"], route_ids=["primary_company_disclosure", "official_product_surface", "channel_offer_proxy", "app_rank_store_proxy", "platform_review_proxy"], query_terms=["gaming console", "Xbox", "PlayStation"]),
    _family("V2", "wearables_devices", "Wearables / Smart Devices", aliases=["wearable", "watch", "airpods", "smart home", "device"], representative_tickers=["AAPL", "GOOGL"], route_ids=["primary_company_disclosure", "official_product_surface", "channel_offer_proxy", "platform_review_proxy"], query_terms=["wearable", "smart device", "watch"]),
    _family("V2", "v2_general_consumer_hardware", "General Consumer Hardware", aliases=["consumer electronics", "hardware devices"], representative_tickers=[], route_ids=["primary_company_disclosure", "official_product_surface", "trusted_external_context"], query_terms=["consumer electronics", "hardware device"], fallback=True),
    # V3 software / cloud.
    _family("V3", "cloud_infrastructure", "Cloud Infrastructure", aliases=["cloud", "azure", "aws", "google cloud", "infrastructure", "compute", "ec2"], representative_tickers=["MSFT", "AMZN", "GOOGL"], route_ids=["primary_company_disclosure", "official_product_surface", "developer_ecosystem_proxy", "public_order_proxy", "hiring_capacity_proxy", "trusted_external_context"], query_terms=["cloud infrastructure", "compute", "storage", "AI cloud"]),
    _family("V3", "ai_platform", "AI Platform / APIs", aliases=["ai platform", "copilot", "gemini", "bedrock", "agentforce", "llm", "machine learning"], representative_tickers=["MSFT", "GOOGL", "AMZN", "CRM", "ADBE"], route_ids=["primary_company_disclosure", "official_product_surface", "developer_ecosystem_proxy", "public_order_proxy", "technology_research_proxy"], query_terms=["AI platform", "Copilot", "Gemini", "Bedrock", "LLM API"]),
    _family("V3", "saas_crm_workflow", "SaaS CRM / Workflow", aliases=["crm", "sales cloud", "service cloud", "workflow", "subscription", "agentforce"], representative_tickers=["CRM", "NOW", "TEAM"], route_ids=["primary_company_disclosure", "official_product_surface", "app_rank_store_proxy", "public_order_proxy", "hiring_capacity_proxy"], query_terms=["CRM", "workflow", "subscription software"]),
    _family("V3", "data_observability_security", "Data / Observability / Security", aliases=["data", "observability", "monitoring", "security", "snowflake", "datadog", "mongodb", "cloudflare"], representative_tickers=["SNOW", "DDOG", "NET", "MDB"], route_ids=["primary_company_disclosure", "official_product_surface", "developer_ecosystem_proxy", "hiring_capacity_proxy", "trusted_external_context"], query_terms=["data platform", "observability", "security software"]),
    _family("V3", "connectivity_semiconductor_components", "Connectivity Semiconductor Components", aliases=["connectivity", "wireless", "rf", "radio frequency", "analog", "skyworks", "front-end module"], representative_tickers=["SWKS", "QCOM"], route_ids=["primary_company_disclosure", "official_product_surface", "developer_ecosystem_proxy", "technology_research_proxy", "trusted_external_context"], query_terms=["connectivity semiconductor", "RF", "wireless components"]),
    _family("V3", "industrial_instrumentation_imaging", "Industrial Instrumentation / Imaging", aliases=["instrumentation", "imaging", "sensors", "aerospace and defense electronics", "digital imaging", "teledyne"], representative_tickers=["TDY"], route_ids=["primary_company_disclosure", "official_product_surface", "public_order_proxy", "technology_research_proxy", "trusted_external_context"], query_terms=["instrumentation", "imaging", "sensors"]),
    _family("V3", "telecom_connectivity_services", "Telecom / Connectivity Services", aliases=["telecom", "wireless", "mobile network", "5g", "broadband", "connectivity services"], representative_tickers=["TMUS", "VZ", "T"], route_ids=["primary_company_disclosure", "official_product_surface", "app_rank_store_proxy", "hiring_capacity_proxy", "trusted_external_context"], query_terms=["telecom", "wireless service", "5G", "mobile network"]),
    _family("V3", "digital_media_content", "Digital Media / Content", aliases=["media", "news", "broadcast", "streaming", "sports", "content", "advertising", "facebook", "instagram", "whatsapp", "paramount+", "paramount plus", "cbs", "nickelodeon", "mtv", "showtime"], representative_tickers=["NWSA", "PSKY", "META"], route_ids=["primary_company_disclosure", "official_product_surface", "app_rank_store_proxy", "platform_review_proxy", "trusted_external_context"], query_terms=["media", "streaming", "broadcast", "content", "social apps"]),
    _family("V3", "real_estate_data_marketplace", "Real Estate Data / Marketplace Platforms", aliases=["real estate data", "commercial real estate information", "marketplace", "costar", "loopnet", "apartments.com", "homes.com", "str"], representative_tickers=["CSGP"], route_ids=["primary_company_disclosure", "official_product_surface", "app_rank_store_proxy", "platform_review_proxy", "trusted_external_context"], query_terms=["real estate data", "commercial real estate marketplace", "CoStar", "LoopNet", "Apartments.com"]),
    _family("V3", "v3_general_software_cloud", "General Software / Cloud", aliases=["software", "saas", "developer products"], representative_tickers=[], route_ids=["primary_company_disclosure", "official_product_surface", "developer_ecosystem_proxy", "trusted_external_context"], query_terms=["software", "SaaS", "developer product"], fallback=True),
    # V4 healthcare.
    _family("V4", "glp1_metabolic", "GLP-1 / Metabolic", aliases=["glp-1", "obesity", "diabetes", "mounjaro", "zepbound", "ozempic", "wegovy"], representative_tickers=["LLY", "NVO"], route_ids=["primary_company_disclosure", "official_product_surface", "regulated_product_context", "technology_research_proxy", "trusted_external_context"], query_terms=["GLP-1", "obesity", "diabetes"]),
    _family("V4", "oncology_immunology", "Oncology / Immunology", aliases=["oncology", "cancer", "immunology", "autoimmune"], representative_tickers=["MRK", "PFE", "AMGN", "JNJ"], route_ids=["primary_company_disclosure", "official_product_surface", "regulated_product_context", "technology_research_proxy"], query_terms=["oncology", "immunology", "clinical trial"]),
    _family("V4", "vaccines_infectious", "Vaccines / Infectious Disease", aliases=["vaccine", "vaccines", "infectious"], representative_tickers=["PFE", "MRK"], route_ids=["primary_company_disclosure", "official_product_surface", "regulated_product_context", "public_order_proxy"], query_terms=["vaccine", "infectious disease"]),
    _family("V4", "medtech_devices", "Medtech Devices / Procedures", aliases=["device", "surgery", "procedure", "robotic", "implant", "diagnostic"], representative_tickers=["ISRG", "BSX", "SYK", "ABT"], route_ids=["primary_company_disclosure", "official_product_surface", "regulated_product_context", "public_order_proxy", "trusted_external_context"], query_terms=["medical device", "procedure", "robotic surgery"]),
    _family("V4", "rna_rare_disease_therapeutics", "RNA / Rare Disease Therapeutics", aliases=["rna", "sirna", "rare disease", "givosiran", "lumasiran", "vutrisiran", "onpattro", "amvuttra", "ttr franchise"], representative_tickers=["ALNY"], route_ids=["primary_company_disclosure", "official_product_surface", "regulated_product_context", "technology_research_proxy", "trusted_external_context"], query_terms=["RNA therapeutics", "siRNA", "rare disease", "ONPATTRO", "AMVUTTRA"]),
    _family("V4", "life_science_tools_diagnostics", "Life Science Tools / Diagnostics", aliases=["life science", "diagnostics", "reagents", "proteins", "antibodies", "assays", "bio-techne"], representative_tickers=["TECH", "A"], route_ids=["primary_company_disclosure", "official_product_surface", "regulated_product_context", "technology_research_proxy", "trusted_external_context"], query_terms=["life science tools", "diagnostics", "reagents", "assays"]),
    _family("V4", "healthcare_distribution_services", "Healthcare Distribution / Pharmacy Services", aliases=["distribution", "pharmaceutical distribution", "medical products", "healthcare services", "pharmacy", "specialty"], representative_tickers=["CAH", "MCK", "COR"], route_ids=["primary_company_disclosure", "official_product_surface", "public_order_proxy", "trusted_external_context"], query_terms=["healthcare distribution", "pharmacy services", "medical products"]),
    _family("V4", "healthcare_facilities_services", "Healthcare Facilities / Services", aliases=["hospital", "behavioral health", "acute care", "healthcare services", "facility", "patient services"], representative_tickers=["UHS", "HCA"], route_ids=["primary_company_disclosure", "official_product_surface", "trusted_external_context"], query_terms=["hospital", "behavioral health", "healthcare services"]),
    _family("V4", "v4_general_healthcare", "General Healthcare Product", aliases=["pharma", "biotech", "medtech", "pipeline"], representative_tickers=[], route_ids=["primary_company_disclosure", "official_product_surface", "regulated_product_context", "trusted_external_context"], query_terms=["pharma product", "pipeline", "clinical"], fallback=True),
    # V5 auto / mobility.
    _family("V5", "ev_vehicle_platform", "EV Vehicle Platform", aliases=["ev", "electric vehicle", "battery electric", "model 3", "model y", "byd"], representative_tickers=["TSLA", "RIVN", "LCID", "1211.HK"], route_ids=["primary_company_disclosure", "official_product_surface", "auto_product_identity_context", "channel_offer_proxy", "trusted_external_context"], query_terms=["EV", "electric vehicle", "vehicle model"]),
    _family("V5", "legacy_oem_vehicle", "Vehicle OEM", aliases=["vehicle", "automotive", "truck", "suv", "ford", "gm", "toyota"], representative_tickers=["GM", "F", "TM"], route_ids=["primary_company_disclosure", "official_product_surface", "auto_product_identity_context", "public_order_proxy"], query_terms=["vehicle model", "automotive", "truck"]),
    _family("V5", "battery_charging_autonomy", "Battery / Charging / Autonomy", aliases=["battery", "charging", "autonomy", "adas", "driver assistance"], representative_tickers=["TSLA", "300750.SZ"], route_ids=["primary_company_disclosure", "official_product_surface", "public_order_proxy", "technology_research_proxy"], query_terms=["battery", "charging", "autonomy"]),
    _family("V5", "mobility_marketplace", "Mobility Marketplace", aliases=["rideshare", "mobility", "delivery", "trips", "bookings", "driver"], representative_tickers=["UBER", "LYFT"], route_ids=["primary_company_disclosure", "official_product_surface", "app_rank_store_proxy", "hiring_capacity_proxy"], query_terms=["rideshare", "mobility marketplace", "delivery"]),
    _family("V5", "v5_general_auto_mobility", "General Auto / Mobility", aliases=["auto", "mobility", "transport"], representative_tickers=[], route_ids=["primary_company_disclosure", "official_product_surface", "auto_product_identity_context"], query_terms=["auto", "mobility"], fallback=True),
    # V6 financials.
    _family("V6", "banking_credit_deposits", "Banking / Credit / Deposits", aliases=["bank", "deposits", "loans", "net interest", "credit"], representative_tickers=["JPM", "BAC", "WFC", "C"], route_ids=["primary_company_disclosure", "official_product_surface", "financial_regulatory_context", "macro_official_context", "trusted_external_context"], query_terms=["deposits", "loans", "net interest income"]),
    _family("V6", "capital_markets_trading", "Capital Markets / Trading", aliases=["trading", "investment banking", "markets", "capital markets"], representative_tickers=["GS", "MS", "CBOE"], route_ids=["primary_company_disclosure", "official_product_surface", "financial_regulatory_context", "trusted_external_context"], query_terms=["trading", "capital markets", "investment banking"]),
    _family("V6", "asset_wealth_management", "Asset / Wealth Management", aliases=["aum", "wealth", "asset management", "advisory"], representative_tickers=["BLK", "SCHW", "MS"], route_ids=["primary_company_disclosure", "official_product_surface", "financial_regulatory_context", "trusted_external_context"], query_terms=["AUM", "wealth management", "asset management"]),
    _family("V6", "v6_general_financials", "General Financials", aliases=["financial", "banking", "capital markets"], representative_tickers=[], route_ids=["primary_company_disclosure", "official_product_surface", "financial_regulatory_context", "macro_official_context"], query_terms=["financial services"], fallback=True),
    # V7 energy / utilities / industrials.
    _family("V7", "upstream_oil_gas", "Upstream Oil / Gas", aliases=["upstream", "oil", "gas", "production", "reserves"], representative_tickers=["XOM", "CVX", "COP"], route_ids=["primary_company_disclosure", "energy_utility_context", "macro_official_context", "trusted_external_context"], query_terms=["oil production", "gas production", "reserves"]),
    _family("V7", "oilfield_services", "Oilfield Services", aliases=["oilfield", "drilling", "services", "completion"], representative_tickers=["SLB", "HAL", "BKR"], route_ids=["primary_company_disclosure", "official_product_surface", "public_order_proxy", "trusted_external_context"], query_terms=["oilfield services", "drilling", "completion"]),
    _family("V7", "midstream_pipeline_lng", "Midstream Pipeline / LNG Infrastructure", aliases=["midstream", "pipeline", "natural gas liquids", "lng", "terminal", "transportation and storage", "gathering"], representative_tickers=["KMI", "OKE", "WMB", "LNG", "TRGP"], route_ids=["primary_company_disclosure", "official_product_surface", "energy_utility_context", "macro_official_context", "trusted_external_context"], query_terms=["pipeline", "midstream", "LNG", "terminal", "natural gas liquids"]),
    _family("V7", "refining_marketing_fuels", "Refining / Marketing / Fuels", aliases=["refining", "refinery", "marketing", "fuels", "midstream and marketing", "retail fuel"], representative_tickers=["MPC", "PSX", "VLO"], route_ids=["primary_company_disclosure", "official_product_surface", "energy_utility_context", "macro_official_context", "trusted_external_context"], query_terms=["refining", "fuels", "marketing", "refinery"]),
    _family("V7", "regulated_utility_power", "Regulated Utility / Power", aliases=["utility", "rate base", "generation", "transmission", "regulated"], representative_tickers=["NEE", "DUK", "SO", "XEL", "ED"], route_ids=["primary_company_disclosure", "energy_utility_context", "macro_official_context", "trusted_external_context"], query_terms=["utility", "rate base", "power generation"]),
    _family("V7", "industrial_equipment", "Industrial Equipment", aliases=["equipment", "machinery", "construction", "agriculture", "engine"], representative_tickers=["CAT", "DE", "GE"], route_ids=["primary_company_disclosure", "official_product_surface", "channel_offer_proxy", "public_order_proxy"], query_terms=["industrial equipment", "machinery", "engine"]),
    _family("V7", "aerospace_defense_industrials", "Aerospace / Defense / Industrial Systems", aliases=["aerospace", "defense", "aircraft", "missile", "avionics", "mission systems", "engineered systems", "commercial engines", "aircraft engines", "jet engines", "aviation services"], representative_tickers=["BA", "LMT", "NOC", "RTX", "LHX", "HON"], route_ids=["primary_company_disclosure", "official_product_surface", "public_order_proxy", "trusted_external_context"], query_terms=["aerospace", "defense", "aircraft", "mission systems", "commercial engines"]),
    _family("V7", "building_construction_services", "Building / Construction Services", aliases=["construction services", "mechanical construction", "electrical construction", "facilities services", "hvac", "building systems"], representative_tickers=["EME", "FIX", "JCI", "TT", "LII"], route_ids=["primary_company_disclosure", "official_product_surface", "public_order_proxy", "hiring_capacity_proxy", "trusted_external_context"], query_terms=["construction services", "building systems", "HVAC", "facilities services"]),
    _family("V7", "real_estate_infrastructure_reit", "Real Estate / Infrastructure REIT", aliases=["reit", "real estate", "property", "tower", "data center", "storage", "self storage", "mall", "apartment", "residential community"], representative_tickers=["AMT", "SBAC", "IRM", "FRT", "CPT"], route_ids=["primary_company_disclosure", "official_product_surface", "macro_official_context", "trusted_external_context"], query_terms=["REIT", "real estate", "tower", "self storage", "properties"]),
    _family("V7", "logistics_transportation", "Logistics / Transportation", aliases=["logistics", "transportation", "freight", "shipping", "courier", "parcel", "package", "rail", "truckload"], representative_tickers=["FDX", "FDXF", "UPS", "JBHT", "CSX"], route_ids=["primary_company_disclosure", "official_product_surface", "public_order_proxy", "trusted_external_context"], query_terms=["logistics", "freight", "shipping", "transportation"]),
    _family("V7", "uranium_nuclear_fuel", "Uranium / Nuclear Fuel", aliases=["uranium", "nuclear fuel", "haleu", "low enriched uranium", "enrichment", "reactor fuel"], representative_tickers=["LEU", "UROY", "CCJ"], route_ids=["primary_company_disclosure", "official_product_surface", "energy_utility_context", "public_order_proxy", "trusted_external_context"], query_terms=["uranium", "nuclear fuel", "HALEU", "enrichment"]),
    _family("V7", "nuclear_power_technology", "Nuclear Power / Reactor Technology", aliases=["advanced nuclear", "small modular reactor", "smr", "reactor", "nuclear components", "nuclear power"], representative_tickers=["OKLO", "SMR", "NNE", "BWXT"], route_ids=["primary_company_disclosure", "official_product_surface", "energy_utility_context", "public_order_proxy", "trusted_external_context"], query_terms=["advanced nuclear", "SMR", "reactor", "nuclear components"]),
    _family("V7", "battery_energy_storage_components", "Battery / Energy Storage Components", aliases=["battery", "energy storage", "lithium", "cathode", "cells", "modules", "storage systems"], representative_tickers=["300750.SZ", "373220.KS", "FLNC", "ALB", "SQM"], route_ids=["primary_company_disclosure", "official_product_surface", "energy_utility_context", "technology_research_proxy", "trusted_external_context"], query_terms=["battery", "energy storage", "lithium", "cells", "modules"]),
    _family("V7", "renewable_power_solar_hydrogen", "Renewable Power / Solar / Hydrogen", aliases=["solar", "renewable", "inverter", "module", "hydrogen", "fuel cell", "tracker", "clean power"], representative_tickers=["ENPH", "FSLR", "JKS", "CSIQ", "PLUG", "BE"], route_ids=["primary_company_disclosure", "official_product_surface", "energy_utility_context", "public_order_proxy", "trusted_external_context"], query_terms=["solar", "renewable power", "hydrogen", "fuel cell", "inverter"]),
    _family("V7", "mining_materials_commodities", "Mining / Materials / Commodities", aliases=["mining", "metals", "copper", "steel", "aluminum", "chemicals", "materials", "aggregates", "cement"], representative_tickers=["FCX", "NUE", "BHP", "RIO", "TECK", "CRH"], route_ids=["primary_company_disclosure", "official_product_surface", "macro_official_context", "trusted_external_context"], query_terms=["mining", "metals", "materials", "chemicals", "aggregates"]),
    _family("V7", "power_semiconductor_components", "Power Semiconductor Components", aliases=["power semiconductor", "power management", "monolithic power", "dc-dc", "regulator", "power module"], representative_tickers=["MPWR"], route_ids=["primary_company_disclosure", "official_product_surface", "technology_research_proxy", "channel_offer_proxy", "trusted_external_context"], query_terms=["power semiconductor", "power management", "DC-DC", "regulator"]),
    _family("V7", "power_grid_cooling", "Power Grid / Datacenter Cooling", aliases=["power", "grid", "cooling", "thermal", "electrical", "datacenter"], representative_tickers=["VRT", "ETN", "PWR", "GE"], route_ids=["primary_company_disclosure", "official_product_surface", "public_order_proxy", "hiring_capacity_proxy", "energy_utility_context"], query_terms=["power grid", "datacenter cooling", "electrical infrastructure"]),
    _family("V7", "v7_general_energy_industrials", "General Energy / Industrials", aliases=["energy", "industrial", "materials"], representative_tickers=[], route_ids=["primary_company_disclosure", "official_product_surface", "energy_utility_context"], query_terms=["energy", "industrial"], fallback=True),
    # V8 retail / CPG / restaurants / travel.
    _family("V8", "mass_retail_grocery", "Mass Retail / Grocery", aliases=["retail", "grocery", "store", "membership", "warehouse"], representative_tickers=["WMT", "COST", "TGT"], route_ids=["primary_company_disclosure", "official_product_surface", "channel_offer_proxy", "platform_review_proxy", "macro_official_context"], query_terms=["retail", "grocery", "store"]),
    _family("V8", "consumer_electronics_retail", "Consumer Electronics Retail", aliases=["consumer electronics retail", "electronics retailer", "appliances", "computing products", "consumer technology"], representative_tickers=["BBY"], route_ids=["primary_company_disclosure", "official_product_surface", "channel_offer_proxy", "platform_review_proxy", "macro_official_context"], query_terms=["consumer electronics retail", "appliances", "computing products"]),
    _family("V8", "auto_aftermarket_retail", "Auto Aftermarket Retail", aliases=["auto parts", "auto aftermarket", "replacement parts", "vehicle maintenance", "automotive retail"], representative_tickers=["AZO", "ORLY", "GPC"], route_ids=["primary_company_disclosure", "official_product_surface", "channel_offer_proxy", "platform_review_proxy", "macro_official_context"], query_terms=["auto parts", "auto aftermarket", "replacement parts"]),
    _family("V8", "farm_ranch_rural_retail", "Farm / Ranch / Rural Lifestyle Retail", aliases=["farm", "ranch", "rural lifestyle", "tractor supply", "livestock", "pet supplies", "lawn and garden", "equine"], representative_tickers=["TSCO"], route_ids=["primary_company_disclosure", "official_product_surface", "channel_offer_proxy", "platform_review_proxy", "macro_official_context"], query_terms=["farm and ranch retail", "rural lifestyle", "livestock", "pet supplies"]),
    _family("V8", "discount_retail_merchandise", "Discount Retail / Merchandise", aliases=["discount retail", "merchandise", "closeout", "off-price", "store", "homegoods", "marmaxx", "dollar"], representative_tickers=["DG", "DLTR", "TJX", "ROST"], route_ids=["primary_company_disclosure", "official_product_surface", "channel_offer_proxy", "platform_review_proxy", "macro_official_context"], query_terms=["discount retail", "merchandise", "off-price", "dollar store"]),
    _family("V8", "apparel_athletic_retail", "Apparel / Athletic Retail", aliases=["apparel", "athletic", "footwear", "fashion", "lululemon", "nike", "brand apparel"], representative_tickers=["LULU", "NKE", "RL"], route_ids=["primary_company_disclosure", "official_product_surface", "channel_offer_proxy", "platform_review_proxy", "macro_official_context"], query_terms=["apparel", "athletic", "fashion", "footwear"]),
    _family("V8", "home_improvement", "Home Improvement", aliases=["home improvement", "building products", "diy"], representative_tickers=["HD", "LOW"], route_ids=["primary_company_disclosure", "official_product_surface", "channel_offer_proxy", "macro_official_context"], query_terms=["home improvement", "building products"]),
    _family("V8", "homebuilding_residential", "Homebuilding / Residential Communities", aliases=["homebuilding", "single-family", "townhomes", "condominiums", "residential", "mortgage banking", "homes"], representative_tickers=["DHI", "LEN", "NVR", "PHM"], route_ids=["primary_company_disclosure", "official_product_surface", "macro_official_context", "trusted_external_context"], query_terms=["homebuilding", "single-family homes", "townhomes", "residential communities"]),
    _family("V8", "consumer_brands_cpg", "Consumer Brands / CPG", aliases=["brand", "beverage", "snacks", "household", "consumer packaged"], representative_tickers=["PG", "KO", "PEP"], route_ids=["primary_company_disclosure", "official_product_surface", "trusted_external_context", "macro_official_context"], query_terms=["consumer brand", "beverage", "household"]),
    _family("V8", "tobacco_nicotine", "Tobacco / Nicotine Products", aliases=["tobacco", "nicotine", "iqos", "heets", "smoke-free", "combustible", "oral nicotine"], representative_tickers=["PM", "MO"], route_ids=["primary_company_disclosure", "official_product_surface", "trusted_external_context", "macro_official_context"], query_terms=["tobacco", "nicotine", "IQOS", "smoke-free products"]),
    _family("V8", "agriculture_commodities_ingredients", "Agriculture Commodities / Ingredients", aliases=["agriculture", "oilseeds", "carbohydrate", "nutrition", "ingredients", "commodities", "grain", "flavors"], representative_tickers=["ADM", "BG"], route_ids=["primary_company_disclosure", "official_product_surface", "trusted_external_context", "macro_official_context"], query_terms=["agriculture", "ingredients", "oilseeds", "nutrition"]),
    _family("V8", "restaurants_menu", "Restaurants / Menu", aliases=["restaurant", "menu", "coffee", "same-store", "franchise"], representative_tickers=["SBUX", "MCD"], route_ids=["primary_company_disclosure", "official_product_surface", "platform_review_proxy", "app_rank_store_proxy", "hiring_capacity_proxy"], query_terms=["restaurant", "menu", "franchise"]),
    _family("V8", "lodging_resorts_cruise", "Lodging / Resorts / Cruise", aliases=["hotel", "lodging", "resort", "casino", "cruise", "room nights", "brand portfolio", "guest loyalty", "properties"], representative_tickers=["HLT", "MAR", "MGM", "LVS", "CCL"], route_ids=["primary_company_disclosure", "official_product_surface", "app_rank_store_proxy", "platform_review_proxy", "macro_official_context"], query_terms=["hotel", "lodging", "resort", "cruise", "casino"]),
    _family("V8", "beauty_personal_care_retail", "Beauty / Personal Care Retail", aliases=["beauty", "personal care", "cosmetics", "fragrance", "salon", "prestige beauty"], representative_tickers=["ULTA", "EL"], route_ids=["primary_company_disclosure", "official_product_surface", "channel_offer_proxy", "platform_review_proxy", "macro_official_context"], query_terms=["beauty", "personal care", "cosmetics", "fragrance"]),
    _family("V8", "ecommerce_marketplace", "E-commerce Marketplace", aliases=["ecommerce", "marketplace", "online marketplace", "seller services", "payments", "commerce platform"], representative_tickers=["EBAY", "MELI", "SE", "SHOP"], route_ids=["primary_company_disclosure", "official_product_surface", "app_rank_store_proxy", "platform_review_proxy", "hiring_capacity_proxy"], query_terms=["e-commerce marketplace", "seller services", "online marketplace"]),
    _family("V8", "local_commerce_delivery", "Local Commerce / Delivery Marketplace", aliases=["delivery", "merchant", "dasher", "commerce platform", "marketplace", "restaurant delivery"], representative_tickers=["DASH", "UBER"], route_ids=["primary_company_disclosure", "official_product_surface", "app_rank_store_proxy", "platform_review_proxy", "hiring_capacity_proxy"], query_terms=["delivery marketplace", "merchant", "local commerce", "restaurant delivery"]),
    _family("V8", "media_entertainment_content", "Media / Entertainment Content", aliases=["media", "news", "broadcast", "streaming", "sports", "content", "advertising"], representative_tickers=["NWSA", "PSKY", "DIS", "NFLX"], route_ids=["primary_company_disclosure", "official_product_surface", "app_rank_store_proxy", "platform_review_proxy", "trusted_external_context"], query_terms=["media", "streaming", "broadcast", "content"]),
    _family("V8", "travel_marketplace", "Travel / Lodging Marketplace", aliases=["travel", "booking", "lodging", "room nights", "airbnb"], representative_tickers=["BKNG", "ABNB"], route_ids=["primary_company_disclosure", "official_product_surface", "app_rank_store_proxy", "platform_review_proxy"], query_terms=["travel", "booking", "lodging"]),
    _family("V8", "v8_general_retail_cpg", "General Retail / CPG", aliases=["retail", "cpg", "restaurant", "travel"], representative_tickers=[], route_ids=["primary_company_disclosure", "official_product_surface", "trusted_external_context"], query_terms=["retail", "CPG"], fallback=True),
)


ROUTE_DEFINITIONS: dict[str, dict[str, Any]] = {
    "primary_company_disclosure": {
        "source_ids": ["company_ir_reports", "company_reported_product_operating_metrics", "sec_edgar_apis", "sec_financial_statement_data_sets"],
        "layer_ids": ["L1"],
        "source_role": "L1 company disclosure",
        "claim_boundary": "Company-disclosed filing/IR facts only after parser, period, unit, value, and citation gates.",
        "forbidden_claims": ["undisclosed_product_kpi", *COMMON_FORBIDDEN_CLAIMS],
    },
    "official_product_surface": {
        "source_ids": [
            "company_product_pages",
            "company_reported_product_operating_metrics",
            "sec_product_taxonomy_normalized",
        ],
        "layer_ids": ["L1", "L2"],
        "source_role": "official product surface",
        "claim_boundary": "Official product existence/spec/taxonomy context; exact product KPI only from company-disclosed metric rows.",
        "forbidden_claims": ["product_revenue_without_company_metric", *COMMON_FORBIDDEN_CLAIMS],
    },
    "trusted_external_context": {
        "source_ids": ["mainstream_financial_news", "industry_association_reports", "official_social_accounts"],
        "layer_ids": ["L2"],
        "source_role": "trusted external context",
        "claim_boundary": "Trusted industry/event context only; not issuer exact values unless independently authoritative.",
        "forbidden_claims": COMMON_FORBIDDEN_CLAIMS,
    },
    "macro_official_context": {
        "source_ids": ["fred_api", "fred_graph_csv", "bls_public_api", "bea_data_api", "census_data_api", "eia_open_data"],
        "layer_ids": ["L2"],
        "source_role": "macro official context",
        "claim_boundary": "Official macro/industry driver context only; no issuer revenue/share inference.",
        "forbidden_claims": COMMON_FORBIDDEN_CLAIMS,
    },
    "supply_chain_official_relationship": {
        "source_ids": ["supplier_customer_official_news", "public_tenders_contracts_orders"],
        "layer_ids": ["L2", "L3"],
        "source_role": "official supply-chain relationship",
        "claim_boundary": "Official supplier/customer/order existence context only; no shipment/allocation/order-volume promotion.",
        "forbidden_claims": ["order_volume_without_disclosure", *COMMON_FORBIDDEN_CLAIMS],
    },
    "official_customer_order_or_deployment_event": {
        "source_ids": ["supplier_customer_official_news"],
        "layer_ids": ["L2", "L3"],
        "source_role": "official customer/order/deployment event",
        "claim_boundary": (
            "Official customer/order/project/deployment/agreement event context only; no revenue, backlog, ASP, "
            "shipment, sell-through, market-share, or complete order-book promotion."
        ),
        "forbidden_claims": ["order_book_from_event", "revenue_from_event", "backlog_from_event", *COMMON_FORBIDDEN_CLAIMS],
    },
    "technical_product_spec": {
        "source_ids": [
            "official_product_datasheets",
            "official_product_spec_pages",
            "official_nvidia_product_page",
            "official_product_spec_parser",
        ],
        "layer_ids": ["L2"],
        "source_role": "technical product spec",
        "claim_boundary": "Official product specification, architecture, feature, configuration, model, or version context only; no sales, revenue, ASP, share, inventory, or sell-through.",
        "forbidden_claims": ["revenue_from_spec", "sales_from_spec", "share_from_spec", *COMMON_FORBIDDEN_CLAIMS],
    },
    "business_asset_profile_spec": {
        "source_ids": [
            "official_business_asset_profile_parser",
            "official_project_pages",
            "energy_utility_context",
        ],
        "layer_ids": ["L2"],
        "source_role": "business/asset profile spec",
        "claim_boundary": "Official business/asset capacity, facility, project, or operating profile context only; no revenue, backlog, order value, utilization, ASP, shipment, or market-share authority.",
        "forbidden_claims": ["revenue_from_profile", "backlog_from_profile", "utilization_from_capacity", *COMMON_FORBIDDEN_CLAIMS],
    },
    "official_product_profile_spec": {
        "source_ids": [
            "sec_product_taxonomy_normalized",
            "official_product_catalog",
            "official_product_profile_parser",
            "clinicaltrials_api",
            "openfda_api",
            "nhtsa_vpic_api",
            "fda_animal_drugs_api",
        ],
        "layer_ids": ["L2"],
        "source_role": "official product/service profile spec",
        "claim_boundary": (
            "Official product, service, regulated product, trial, model, or catalog identity/profile context only; "
            "no revenue, ASP, sales, market-share, sell-through, inventory, backlog, customer order value, or shipment authority."
        ),
        "forbidden_claims": [
            "revenue_from_profile",
            "sales_from_profile",
            "share_from_profile",
            "backlog_from_profile",
            *COMMON_FORBIDDEN_CLAIMS,
        ],
    },
    "business_service_profile_spec": {
        "source_ids": [
            "company_disclosed_business_service_profile_projector",
            "industry_operating_metric_exact_slot",
            "company_product_kpi_facts_structured_metric_parser",
        ],
        "layer_ids": ["L1", "L2"],
        "source_role": "business/service operating profile spec",
        "claim_boundary": (
            "Company-disclosed non-revenue operating/profile context only; supports bounded scale, capacity, "
            "volume, subscriber, AUM, or service-profile analysis without product revenue, ASP, share, backlog, "
            "sell-through, inventory, or customer order value promotion."
        ),
        "forbidden_claims": [
            "revenue_from_profile",
            "asp_from_profile",
            "share_from_profile",
            "backlog_from_profile",
            *COMMON_FORBIDDEN_CLAIMS,
        ],
    },
    "product_generation_edge": {
        "source_ids": [
            "official_product_datasheets",
            "official_product_spec_pages",
            "official_nvidia_product_page",
        ],
        "layer_ids": ["L2"],
        "source_role": "product generation edge",
        "claim_boundary": "Official product-generation or architecture-transition context only; no automatic demand, revenue, margin, or share inference.",
        "forbidden_claims": ["demand_from_generation", "revenue_from_generation", *COMMON_FORBIDDEN_CLAIMS],
    },
    "product_benchmark_proxy": {
        "source_ids": ["official_product_benchmark_page", "trusted_benchmark_database", "official_nvidia_product_page"],
        "layer_ids": ["L2", "L3"],
        "source_role": "product benchmark proxy",
        "claim_boundary": "Benchmark/performance context only; supports product capability comparison, not sales, revenue, market share, or adoption exact.",
        "forbidden_claims": ["sales_from_benchmark", "share_from_benchmark", "adoption_from_benchmark", *COMMON_FORBIDDEN_CLAIMS],
    },
    "customer_deployment_proxy": {
        "source_ids": ["official_customer_deployment_news", "official_nvidia_customer_deployment_news", "supplier_customer_official_news"],
        "layer_ids": ["L2", "L3"],
        "source_role": "customer deployment proxy",
        "claim_boundary": "Official customer deployment/project context only; no order value, revenue contribution, backlog, shipment, ASP, sell-through, or share.",
        "forbidden_claims": ["order_value_from_deployment", "revenue_from_deployment", "backlog_from_deployment", *COMMON_FORBIDDEN_CLAIMS],
    },
    "developer_ecosystem_proxy": {
        "source_ids": ["developer_ecosystem_github_npm_pypi_huggingface"],
        "layer_ids": ["L3"],
        "source_role": "developer ecosystem proxy",
        "claim_boundary": "Developer ecosystem attention/technical proxy only; not revenue, sales, or moat proof.",
        "forbidden_claims": ["revenue_from_developer_activity", *COMMON_FORBIDDEN_CLAIMS],
    },
    "channel_offer_proxy": {
        "source_ids": ["ecommerce_major_platforms", "channel_pricing_quotations"],
        "layer_ids": ["L3"],
        "source_role": "channel offer proxy",
        "claim_boundary": "Public price/configuration/availability context only; no ASP, sell-through, inventory, or share.",
        "forbidden_claims": ["asp_from_channel_offer", "sell_through_from_listing", *COMMON_FORBIDDEN_CLAIMS],
    },
    "app_rank_store_proxy": {
        "source_ids": ["app_store_rankings"],
        "layer_ids": ["L3"],
        "source_role": "app marketplace proxy",
        "claim_boundary": "App metadata/rank/review context only; not app revenue/download/share.",
        "forbidden_claims": ["download_or_revenue_from_rank", *COMMON_FORBIDDEN_CLAIMS],
    },
    "platform_review_proxy": {
        "source_ids": ["platform_reviews_rankings_downloads"],
        "layer_ids": ["L3"],
        "source_role": "platform review proxy",
        "claim_boundary": "Public review/ranking context only; directional attention signal, not sales proof.",
        "forbidden_claims": ["sales_from_reviews", *COMMON_FORBIDDEN_CLAIMS],
    },
    "hiring_capacity_proxy": {
        "source_ids": ["job_postings_hiring_signals"],
        "layer_ids": ["L3"],
        "source_role": "hiring/capacity proxy",
        "claim_boundary": "Hiring/capacity/geography signal only; weak directional evidence unless corroborated.",
        "forbidden_claims": ["demand_or_revenue_from_hiring", *COMMON_FORBIDDEN_CLAIMS],
    },
    "public_order_proxy": {
        "source_ids": ["public_tenders_contracts_orders"],
        "layer_ids": ["L3"],
        "source_role": "public order/procurement proxy",
        "claim_boundary": "Public tender/award/order existence proxy only; no total sales or backlog inference.",
        "forbidden_claims": ["company_backlog_from_public_award", *COMMON_FORBIDDEN_CLAIMS],
    },
    "regulated_product_context": {
        "source_ids": ["clinicaltrials_api", "openfda_api", "cms_public_data", "fda_animal_drugs_api"],
        "layer_ids": ["L2"],
        "source_role": "regulated product context",
        "claim_boundary": "Regulatory/trial/use context only; not approval success, utilization share, prescriptions, or sales proof.",
        "forbidden_claims": ["prescription_or_sales_from_regulatory_status", *COMMON_FORBIDDEN_CLAIMS],
    },
    "auto_product_identity_context": {
        "source_ids": ["nhtsa_vpic_api"],
        "layer_ids": ["L2"],
        "source_role": "auto product identity context",
        "claim_boundary": "Vehicle manufacturer/make/model identity context only; no sales volume or profitability proof.",
        "forbidden_claims": ["registrations_or_sales_from_vpic", *COMMON_FORBIDDEN_CLAIMS],
    },
    "financial_regulatory_context": {
        "source_ids": ["fdic_bankfind_api", "fred_api", "fred_graph_csv"],
        "layer_ids": ["L2"],
        "source_role": "financial regulatory context",
        "claim_boundary": "Bank regulatory and macro context only until institution-to-listed-issuer resolver passes.",
        "forbidden_claims": COMMON_FORBIDDEN_CLAIMS,
    },
    "energy_utility_context": {
        "source_ids": ["eia_open_data", "fred_api", "fred_graph_csv"],
        "layer_ids": ["L2"],
        "source_role": "energy/utility official context",
        "claim_boundary": "Energy/utility official operating context only; no single-company revenue or margin inference.",
        "forbidden_claims": COMMON_FORBIDDEN_CLAIMS,
    },
    "technology_research_proxy": {
        "source_ids": ["openalex_api", "patentsview_api"],
        "layer_ids": ["L3"],
        "source_role": "technology/research proxy",
        "claim_boundary": "Research/IP signal only; not product launch, sales, or durable moat proof.",
        "forbidden_claims": ["moat_or_product_success_from_research_proxy", *COMMON_FORBIDDEN_CLAIMS],
    },
}


TICKER_FAMILY_OVERRIDES: dict[str, list[str]] = {
    "NVDA": ["gpu_accelerator", "networking"],
    "AMD": ["gpu_accelerator"],
    "INTC": ["gpu_accelerator", "foundry"],
    "ASML": ["semicap_equipment"],
    "ACLS": ["semicap_equipment"],
    "AEHR": ["semicap_equipment"],
    "TSM": ["foundry"],
    "AMAT": ["semicap_equipment"],
    "CAMT": ["semicap_equipment"],
    "LRCX": ["semicap_equipment"],
    "KLAC": ["semicap_equipment"],
    "ONTO": ["semicap_equipment"],
    "TER": ["semicap_equipment"],
    "MU": ["memory"],
    "000660.KS": ["memory"],
    "005930.KS": ["memory", "foundry"],
    "ANET": ["networking"],
    "AVGO": ["networking"],
    "MRVL": ["networking"],
    "DELL": ["server_oem"],
    "SMCI": ["server_oem"],
    "HPE": ["server_oem"],
    "2317.TW": ["electronics_manufacturing_services"],
    "2382.TW": ["electronics_manufacturing_services"],
    "3231.TW": ["electronics_manufacturing_services"],
    "6146.T": ["semicap_equipment"],
    "VRT": ["power_cooling", "power_grid_cooling"],
    "ETN": ["power_cooling", "power_grid_cooling"],
    "PWR": ["power_cooling", "power_grid_cooling"],
    "AAPL": ["smartphones_tablets", "pcs_peripherals", "wearables_devices"],
    "MSFT": ["cloud_infrastructure", "ai_platform", "gaming_devices", "pcs_peripherals"],
    "AMZN": ["cloud_infrastructure"],
    "GOOGL": ["cloud_infrastructure", "ai_platform"],
    "CRM": ["saas_crm_workflow", "ai_platform"],
    "SNOW": ["data_observability_security"],
    "DDOG": ["data_observability_security"],
    "NET": ["data_observability_security"],
    "SWKS": ["connectivity_semiconductor_components"],
    "TDY": ["industrial_instrumentation_imaging"],
    "TMUS": ["telecom_connectivity_services"],
    "LLY": ["glp1_metabolic", "oncology_immunology"],
    "NVO": ["glp1_metabolic"],
    "PFE": ["vaccines_infectious", "oncology_immunology"],
    "ISRG": ["medtech_devices"],
    "WST": ["medtech_devices"],
    "ALNY": ["rna_rare_disease_therapeutics"],
    "TECH": ["life_science_tools_diagnostics"],
    "CAH": ["healthcare_distribution_services"],
    "COR": ["healthcare_distribution_services"],
    "HSIC": ["healthcare_distribution_services"],
    "MCK": ["healthcare_distribution_services"],
    "HCA": ["healthcare_facilities_services"],
    "UHS": ["healthcare_facilities_services"],
    "TSLA": ["ev_vehicle_platform", "battery_charging_autonomy"],
    "GM": ["legacy_oem_vehicle"],
    "F": ["legacy_oem_vehicle"],
    "UBER": ["mobility_marketplace"],
    "LYFT": ["mobility_marketplace"],
    "JPM": ["banking_credit_deposits", "capital_markets_trading", "asset_wealth_management"],
    "BAC": ["banking_credit_deposits"],
    "C": ["banking_credit_deposits", "capital_markets_trading"],
    "HOOD": ["capital_markets_trading"],
    "GS": ["capital_markets_trading"],
    "MS": ["capital_markets_trading", "asset_wealth_management"],
    "BLK": ["asset_wealth_management"],
    "XOM": ["upstream_oil_gas"],
    "CVX": ["upstream_oil_gas"],
    "SLB": ["oilfield_services"],
    "NEE": ["regulated_utility_power"],
    "DUK": ["regulated_utility_power"],
    "CAT": ["industrial_equipment"],
    "DE": ["industrial_equipment"],
    "CPT": ["real_estate_infrastructure_reit"],
    "FRT": ["real_estate_infrastructure_reit"],
    "IRM": ["real_estate_infrastructure_reit"],
    "SBAC": ["real_estate_infrastructure_reit"],
    "FDXF": ["logistics_transportation"],
    "LEU": ["uranium_nuclear_fuel"],
    "UROY": ["uranium_nuclear_fuel"],
    "MPWR": ["power_semiconductor_components"],
    "6752.T": ["industrial_equipment"],
    "WMT": ["mass_retail_grocery"],
    "COST": ["mass_retail_grocery"],
    "DG": ["discount_retail_merchandise"],
    "DLTR": ["discount_retail_merchandise"],
    "TJX": ["discount_retail_merchandise"],
    "LULU": ["apparel_athletic_retail"],
    "HD": ["home_improvement"],
    "LOW": ["home_improvement"],
    "DHI": ["homebuilding_residential"],
    "LEN": ["homebuilding_residential"],
    "NVR": ["homebuilding_residential"],
    "ADM": ["agriculture_commodities_ingredients"],
    "BG": ["agriculture_commodities_ingredients"],
    "PG": ["consumer_brands_cpg"],
    "KO": ["consumer_brands_cpg"],
    "PEP": ["consumer_brands_cpg"],
    "CHD": ["consumer_brands_cpg"],
    "CL": ["consumer_brands_cpg"],
    "EL": ["consumer_brands_cpg"],
    "HAS": ["consumer_brands_cpg"],
    "KDP": ["consumer_brands_cpg"],
    "MKC": ["consumer_brands_cpg"],
    "SJM": ["consumer_brands_cpg"],
    "SYY": ["consumer_brands_cpg"],
    "TSN": ["consumer_brands_cpg"],
    "PM": ["tobacco_nicotine"],
    "SBUX": ["restaurants_menu"],
    "MCD": ["restaurants_menu"],
    "DRI": ["restaurants_menu"],
    "CCL": ["lodging_resorts_cruise"],
    "HLT": ["lodging_resorts_cruise"],
    "LVS": ["lodging_resorts_cruise"],
    "MAR": ["lodging_resorts_cruise"],
    "MGM": ["lodging_resorts_cruise"],
    "DASH": ["local_commerce_delivery"],
    "MELI": ["local_commerce_delivery"],
    "NWSA": ["digital_media_content"],
    "PSKY": ["digital_media_content"],
    "BKNG": ["travel_marketplace"],
    "ABNB": ["travel_marketplace"],
}

TICKER_FAMILY_OVERRIDES.update(
    {
        # V1 / semiconductors and AI infrastructure.
        "CDNS": ["eda_ip"],
        "SNPS": ["eda_ip"],
        "DIOD": ["analog_embedded_semiconductors", "power_semiconductor_components"],
        "IFX.DE": ["analog_embedded_semiconductors", "power_semiconductor_components"],
        "WOLF": ["analog_embedded_semiconductors", "power_semiconductor_components"],
        "ADI": ["analog_embedded_semiconductors"],
        "MCHP": ["analog_embedded_semiconductors"],
        "NXPI": ["analog_embedded_semiconductors"],
        "ON": ["analog_embedded_semiconductors"],
        "TXN": ["analog_embedded_semiconductors"],
        "CRDO": ["networking"],
        "RMBS": ["eda_ip"],
        "GFS": ["foundry"],
        "JBL": ["electronics_manufacturing_services"],
        "FORM": ["semicap_equipment"],
        # V3 software, telecom, and media.
        "AKAM": ["data_observability_security"],
        "CRWD": ["data_observability_security"],
        "FTNT": ["data_observability_security"],
        "PANW": ["data_observability_security"],
        "S": ["data_observability_security"],
        "TENB": ["data_observability_security"],
        "MDB": ["data_observability_security"],
        "ESTC": ["data_observability_security"],
        "FIVN": ["saas_crm_workflow"],
        "HUBS": ["saas_crm_workflow"],
        "TEAM": ["saas_crm_workflow"],
        "PATH": ["saas_crm_workflow"],
        "ADP": ["saas_crm_workflow"],
        "ADSK": ["saas_crm_workflow"],
        "BILL": ["saas_crm_workflow"],
        "INTU": ["saas_crm_workflow"],
        "ORCL": ["cloud_infrastructure", "saas_crm_workflow"],
        "PLTR": ["data_observability_security", "ai_platform"],
        "CSGP": ["real_estate_data_marketplace"],
        "SHOP": ["ecommerce_marketplace", "saas_crm_workflow"],
        "CHTR": ["telecom_connectivity_services"],
        "SATS": ["telecom_connectivity_services"],
        "T": ["telecom_connectivity_services"],
        "VZ": ["telecom_connectivity_services"],
        "CMCSA": ["digital_media_content"],
        "DIS": ["digital_media_content"],
        "EA": ["digital_media_content"],
        "FOXA": ["digital_media_content"],
        "LYV": ["digital_media_content"],
        "META": ["digital_media_content", "ai_platform"],
        "NFLX": ["digital_media_content"],
        "OMC": ["digital_media_content"],
        "TKO": ["digital_media_content"],
        "TTD": ["digital_media_content"],
        "TTWO": ["digital_media_content"],
        "WBD": ["digital_media_content"],
        # V7 energy, industrials, utilities, real estate, and materials.
        "APA": ["upstream_oil_gas"],
        "COP": ["upstream_oil_gas"],
        "CTRA": ["upstream_oil_gas"],
        "DVN": ["upstream_oil_gas"],
        "EOG": ["upstream_oil_gas"],
        "EQT": ["upstream_oil_gas"],
        "EXE": ["upstream_oil_gas"],
        "FANG": ["upstream_oil_gas"],
        "OXY": ["upstream_oil_gas"],
        "TPL": ["upstream_oil_gas"],
        "BKR": ["oilfield_services"],
        "HAL": ["oilfield_services"],
        "KMI": ["midstream_pipeline_lng"],
        "LNG": ["midstream_pipeline_lng"],
        "OKE": ["midstream_pipeline_lng"],
        "TRGP": ["midstream_pipeline_lng"],
        "WMB": ["midstream_pipeline_lng"],
        "MPC": ["refining_marketing_fuels"],
        "PSX": ["refining_marketing_fuels"],
        "VLO": ["refining_marketing_fuels"],
        "AEE": ["regulated_utility_power"],
        "AEP": ["regulated_utility_power"],
        "AES": ["regulated_utility_power"],
        "ATO": ["regulated_utility_power"],
        "AWK": ["regulated_utility_power"],
        "CEG": ["regulated_utility_power"],
        "CMS": ["regulated_utility_power"],
        "CNP": ["regulated_utility_power"],
        "D": ["regulated_utility_power"],
        "DTE": ["regulated_utility_power"],
        "ED": ["regulated_utility_power"],
        "EIX": ["regulated_utility_power"],
        "ES": ["regulated_utility_power"],
        "ETR": ["regulated_utility_power"],
        "EVRG": ["regulated_utility_power"],
        "EXC": ["regulated_utility_power"],
        "FE": ["regulated_utility_power"],
        "LNT": ["regulated_utility_power"],
        "NI": ["regulated_utility_power"],
        "NRG": ["regulated_utility_power"],
        "PEG": ["regulated_utility_power"],
        "PNW": ["regulated_utility_power"],
        "PPL": ["regulated_utility_power"],
        "SO": ["regulated_utility_power"],
        "SRE": ["regulated_utility_power"],
        "VST": ["regulated_utility_power"],
        "WEC": ["regulated_utility_power"],
        "AMT": ["real_estate_infrastructure_reit"],
        "ARE": ["real_estate_infrastructure_reit"],
        "AVB": ["real_estate_infrastructure_reit"],
        "BXP": ["real_estate_infrastructure_reit"],
        "CBRE": ["real_estate_infrastructure_reit"],
        "CCI": ["real_estate_infrastructure_reit"],
        "DLR": ["real_estate_infrastructure_reit"],
        "DOC": ["real_estate_infrastructure_reit"],
        "EQIX": ["real_estate_infrastructure_reit"],
        "EQR": ["real_estate_infrastructure_reit"],
        "ESS": ["real_estate_infrastructure_reit"],
        "EXR": ["real_estate_infrastructure_reit"],
        "INVH": ["real_estate_infrastructure_reit"],
        "KIM": ["real_estate_infrastructure_reit"],
        "MAA": ["real_estate_infrastructure_reit"],
        "O": ["real_estate_infrastructure_reit"],
        "PLD": ["real_estate_infrastructure_reit"],
        "PSA": ["real_estate_infrastructure_reit"],
        "REG": ["real_estate_infrastructure_reit"],
        "UDR": ["real_estate_infrastructure_reit"],
        "VICI": ["real_estate_infrastructure_reit"],
        "WELL": ["real_estate_infrastructure_reit"],
        "BA": ["aerospace_defense_industrials"],
        "GD": ["aerospace_defense_industrials"],
        "HII": ["aerospace_defense_industrials"],
        "HWM": ["aerospace_defense_industrials"],
        "HON": ["aerospace_defense_industrials", "building_construction_services"],
        "LHX": ["aerospace_defense_industrials"],
        "LMT": ["aerospace_defense_industrials"],
        "NOC": ["aerospace_defense_industrials"],
        "RTX": ["aerospace_defense_industrials"],
        "TXT": ["aerospace_defense_industrials"],
        "CARR": ["building_construction_services"],
        "EME": ["building_construction_services"],
        "FIX": ["building_construction_services"],
        "JCI": ["building_construction_services"],
        "LII": ["building_construction_services"],
        "OTIS": ["building_construction_services"],
        "TT": ["building_construction_services"],
        "CHRW": ["logistics_transportation"],
        "CSX": ["logistics_transportation"],
        "DAL": ["logistics_transportation"],
        "EXPD": ["logistics_transportation"],
        "FDX": ["logistics_transportation"],
        "JBHT": ["logistics_transportation"],
        "NSC": ["logistics_transportation"],
        "ODFL": ["logistics_transportation"],
        "UNP": ["logistics_transportation"],
        "UPS": ["logistics_transportation"],
        "CMI": ["industrial_equipment"],
        "DOV": ["industrial_equipment"],
        "EMR": ["industrial_equipment"],
        "FTV": ["industrial_equipment"],
        "GE": ["industrial_equipment", "aerospace_defense_industrials"],
        "IEX": ["industrial_equipment"],
        "ITW": ["industrial_equipment"],
        "PH": ["industrial_equipment"],
        "ROK": ["industrial_equipment"],
        "SNA": ["industrial_equipment"],
        "SWK": ["industrial_equipment"],
        "WAB": ["industrial_equipment", "logistics_transportation"],
        "BWXT": ["nuclear_power_technology"],
        "NNE": ["nuclear_power_technology"],
        "OKLO": ["nuclear_power_technology"],
        "SMR": ["nuclear_power_technology"],
        "CCJ": ["uranium_nuclear_fuel"],
        "DNN": ["uranium_nuclear_fuel"],
        "NXE": ["uranium_nuclear_fuel"],
        "300750.SZ": ["battery_energy_storage_components"],
        "373220.KS": ["battery_energy_storage_components"],
        "ALB": ["battery_energy_storage_components", "mining_materials_commodities"],
        "FLNC": ["battery_energy_storage_components"],
        "LAC": ["battery_energy_storage_components"],
        "SQM": ["battery_energy_storage_components", "mining_materials_commodities"],
        "ARRY": ["renewable_power_solar_hydrogen"],
        "BE": ["renewable_power_solar_hydrogen"],
        "CSIQ": ["renewable_power_solar_hydrogen"],
        "DQ": ["renewable_power_solar_hydrogen"],
        "ENLT": ["renewable_power_solar_hydrogen"],
        "ENPH": ["renewable_power_solar_hydrogen"],
        "FSLR": ["renewable_power_solar_hydrogen"],
        "JKS": ["renewable_power_solar_hydrogen"],
        "NXT": ["renewable_power_solar_hydrogen"],
        "PLUG": ["renewable_power_solar_hydrogen"],
        "SEDG": ["renewable_power_solar_hydrogen"],
        "AMCR": ["mining_materials_commodities"],
        "APD": ["mining_materials_commodities"],
        "AVY": ["mining_materials_commodities"],
        "BALL": ["mining_materials_commodities"],
        "BHP": ["mining_materials_commodities"],
        "CE": ["mining_materials_commodities"],
        "CF": ["mining_materials_commodities"],
        "CRH": ["mining_materials_commodities"],
        "CTVA": ["mining_materials_commodities"],
        "DD": ["mining_materials_commodities"],
        "DOW": ["mining_materials_commodities"],
        "ECL": ["mining_materials_commodities"],
        "FCX": ["mining_materials_commodities"],
        "IFF": ["mining_materials_commodities"],
        "IP": ["mining_materials_commodities"],
        "LIN": ["mining_materials_commodities"],
        "LYB": ["mining_materials_commodities"],
        "MLM": ["mining_materials_commodities"],
        "MOS": ["mining_materials_commodities"],
        "MP": ["mining_materials_commodities"],
        "NEM": ["mining_materials_commodities"],
        "NUE": ["mining_materials_commodities"],
        "PPG": ["mining_materials_commodities"],
        "RIO": ["mining_materials_commodities"],
        "SCCO": ["mining_materials_commodities"],
        "SHW": ["mining_materials_commodities"],
        "TECK": ["mining_materials_commodities"],
        "VALE": ["mining_materials_commodities"],
        # V8 consumer and retail.
        "AZO": ["auto_aftermarket_retail"],
        "GPC": ["auto_aftermarket_retail"],
        "ORLY": ["auto_aftermarket_retail"],
        "BBY": ["consumer_electronics_retail"],
        "EBAY": ["ecommerce_marketplace"],
        "SE": ["ecommerce_marketplace"],
        "DECK": ["apparel_athletic_retail"],
        "TPR": ["apparel_athletic_retail"],
        "ULTA": ["beauty_personal_care_retail"],
        "CMG": ["restaurants_menu"],
        "DPZ": ["restaurants_menu"],
        "YUM": ["restaurants_menu"],
        "EXPE": ["travel_marketplace"],
        "NCLH": ["lodging_resorts_cruise"],
        "RCL": ["lodging_resorts_cruise"],
        "WYNN": ["lodging_resorts_cruise"],
        "HST": ["lodging_resorts_cruise"],
        "PHM": ["homebuilding_residential"],
        "CASY": ["mass_retail_grocery"],
        "KR": ["mass_retail_grocery"],
        "TSCO": ["farm_ranch_rural_retail"],
        "PCAR": ["legacy_oem_vehicle"],
        "PCG": ["regulated_utility_power"],
        "RUN": ["renewable_power_solar_hydrogen"],
    }
)

CATEGORY_FAMILY_OVERRIDES: dict[tuple[str, str], list[str]] = {
    ("V1", "analog_power_semiconductors"): ["analog_embedded_semiconductors", "power_semiconductor_components"],
    ("V1", "analog_rf_semiconductors"): ["analog_embedded_semiconductors", "connectivity_semiconductor_components"],
    ("V1", "automotive_industrial_semiconductors"): ["analog_embedded_semiconductors"],
    ("V1", "electronics_manufacturing_services"): ["electronics_manufacturing_services"],
    ("V1", "server_odm"): ["electronics_manufacturing_services", "server_oem"],
    ("V1", "networking_semiconductors"): ["networking"],
    ("V1", "semiconductor/networking"): ["networking"],
    ("V1", "semiconductor_equipment"): ["semicap_equipment"],
    ("V1", "semiconductor_manufacturing_tools"): ["semicap_equipment"],
    ("V1", "semiconductor_test_equipment"): ["semicap_equipment"],
    ("V1", "semiconductor_services"): ["semicap_equipment"],
    ("V1", "semiconductor_ip"): ["eda_ip"],
    ("V1", "memory_semiconductors"): ["memory"],
    ("V1", "memory_foundry_electronics"): ["memory", "foundry"],
    ("V1", "semiconductors"): ["v1_general_ai_infrastructure"],
    ("V3", "cloud_network_security"): ["data_observability_security"],
    ("V3", "cloud_software"): ["data_observability_security"],
    ("V3", "data/cloud software"): ["data_observability_security"],
    ("V3", "search_observability_software"): ["data_observability_security"],
    ("V3", "cybersecurity"): ["data_observability_security"],
    ("V3", "application_software"): ["saas_crm_workflow"],
    ("V3", "automation_software"): ["saas_crm_workflow"],
    ("V3", "collaboration_software"): ["saas_crm_workflow"],
    ("V3", "contact_center_software"): ["saas_crm_workflow"],
    ("V3", "construction_software"): ["saas_crm_workflow"],
    ("V3", "devops_software"): ["saas_crm_workflow"],
    ("V3", "Communication Services"): ["digital_media_content"],
    ("V5", "autos"): ["legacy_oem_vehicle"],
    ("V5", "electric_vehicles"): ["ev_vehicle_platform"],
    ("V5", "autos_batteries"): ["ev_vehicle_platform", "battery_charging_autonomy"],
    ("V7", "Utilities"): ["regulated_utility_power"],
    ("V7", "Real Estate"): ["real_estate_infrastructure_reit"],
    ("V7", "LNG infrastructure"): ["midstream_pipeline_lng"],
    ("V7", "advanced_nuclear"): ["nuclear_power_technology"],
    ("V7", "nuclear_components"): ["nuclear_power_technology"],
    ("V7", "uranium"): ["uranium_nuclear_fuel"],
    ("V7", "nuclear_fuel"): ["uranium_nuclear_fuel"],
    ("V7", "batteries"): ["battery_energy_storage_components"],
    ("V7", "batteries_electronics"): ["battery_energy_storage_components"],
    ("V7", "energy_storage"): ["battery_energy_storage_components"],
    ("V7", "lithium"): ["battery_energy_storage_components"],
    ("V7", "lithium_chemicals"): ["battery_energy_storage_components", "mining_materials_commodities"],
    ("V7", "renewable_power"): ["renewable_power_solar_hydrogen"],
    ("V7", "solar_infrastructure"): ["renewable_power_solar_hydrogen"],
    ("V7", "solar_inverters"): ["renewable_power_solar_hydrogen"],
    ("V7", "solar_materials"): ["renewable_power_solar_hydrogen"],
    ("V7", "fuel_cells_power"): ["renewable_power_solar_hydrogen"],
    ("V7", "hydrogen"): ["renewable_power_solar_hydrogen"],
    ("V7", "mining_metals"): ["mining_materials_commodities"],
    ("V7", "materials"): ["mining_materials_commodities"],
    ("V7", "Materials"): ["mining_materials_commodities"],
    ("V7", "copper"): ["mining_materials_commodities"],
    ("V7", "rare_earths"): ["mining_materials_commodities"],
    ("V7", "display_materials"): ["mining_materials_commodities"],
    ("V7", "power_thermal_components"): ["power_cooling", "power_grid_cooling"],
    ("V8", "ecommerce_fintech"): ["ecommerce_marketplace"],
    ("V8", "Real Estate"): ["lodging_resorts_cruise"],
}

def build_product_family_lane_registry(*, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or _utc_now()
    families = [
        {
            **family,
            "schema_version": "finsight_product_family_lane_definition_v0_1",
            "generated_at": generated_at,
            "routes": [
                {"route_id": route_id, **ROUTE_DEFINITIONS[route_id]}
                for route_id in family["route_ids"]
                if route_id in ROUTE_DEFINITIONS
            ],
        }
        for family in FAMILY_DEFINITIONS
    ]
    validation = validate_product_family_lane_registry(families)
    return {
        "schema_version": PRODUCT_FAMILY_LANE_REGISTRY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "family_count": len(families),
        "lane_count": len({family["lane_id"] for family in families}),
        "summary": {
            "families_by_lane": dict(sorted(Counter(family["lane_id"] for family in families).items())),
            "fallback_family_count": sum(1 for family in families if family.get("fallback")),
        },
        "families": families,
        "route_definitions": ROUTE_DEFINITIONS,
        "validation": validation,
        "policy": "family_scoped_source_routes_before_full_chain_research_v0_1",
    }


def build_company_product_family_assignments(
    *,
    company_assignments: Iterable[Mapping[str, Any]],
    product_nodes: Iterable[Mapping[str, Any]] | None = None,
    product_runtime_rows: Iterable[Mapping[str, Any]] | None = None,
    public_context_rows: Iterable[Mapping[str, Any]] | None = None,
    generated_at: str | None = None,
) -> list[dict[str, Any]]:
    generated_at = generated_at or _utc_now()
    family_by_id = {family["family_id"]: family for family in FAMILY_DEFINITIONS}
    families_by_lane: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for family in FAMILY_DEFINITIONS:
        families_by_lane[str(family["lane_id"])].append(family)
    text_index = _company_text_index(product_nodes or [], product_runtime_rows or [], public_context_rows or [])
    out: list[dict[str, Any]] = []
    for raw_assignment in company_assignments:
        assignment = dict(raw_assignment)
        ticker = str(assignment.get("ticker") or "").upper()
        lane_id = str(assignment.get("primary_lane_id") or "").upper()
        secondary_lanes = [str(item).upper() for item in assignment.get("secondary_lane_ids") or []]
        category = str(assignment.get("category") or "")
        haystack = _company_haystack(assignment, text_index.get(ticker, ""))
        selected = _selected_family_ids(ticker=ticker, lane_id=lane_id, secondary_lanes=secondary_lanes, category=category, haystack=haystack, families_by_lane=families_by_lane)
        for family_id, reason, matched_terms in selected:
            family = family_by_id[family_id]
            evidence_state = _assignment_evidence_state(assignment, reason=reason)
            out.append(
                {
                    "schema_version": COMPANY_PRODUCT_FAMILY_ASSIGNMENT_SCHEMA_VERSION,
                    "generated_at": generated_at,
                    "assignment_id": _stable_id("company_product_family_assignment", [ticker, family_id]),
                    "ticker": ticker,
                    "company_name": assignment.get("company_name") or "",
                    "primary_lane_id": lane_id,
                    "primary_lane_name": assignment.get("primary_lane_name") or "",
                    "secondary_lane_ids": secondary_lanes,
                    "family_id": family_id,
                    "family_name": family["family_name"],
                    "family_lane_id": family["lane_id"],
                    "assignment_reason": reason,
                    "assignment_confidence": _assignment_confidence(reason),
                    "matched_terms": matched_terms,
                    "query_terms": family["query_terms"],
                    "family_aliases": family.get("aliases") or [],
                    "route_ids": family["route_ids"],
                    "evidence_state": evidence_state,
                    "product_taxonomy_status": assignment.get("product_taxonomy_status") or "unknown",
                    "public_data_ceiling": assignment.get("public_data_ceiling") or [],
                    "expected_commercial_gaps": assignment.get("expected_commercial_gaps") or [],
                    "claim_boundary": family["claim_boundary"],
                    "forbidden_claims": family["forbidden_claims"],
                }
            )
    return sorted(out, key=lambda row: (row["ticker"], row["family_lane_id"], row["family_id"]))


def build_family_source_route_plan(
    *,
    family_assignments: Iterable[Mapping[str, Any]],
    product_runtime_rows: Iterable[Mapping[str, Any]] | None = None,
    public_context_rows: Iterable[Mapping[str, Any]] | None = None,
    materialized_product_pages: Iterable[Mapping[str, Any]] | None = None,
    repair_queue_rows: Iterable[Mapping[str, Any]] | None = None,
    generated_at: str | None = None,
) -> list[dict[str, Any]]:
    generated_at = generated_at or _utc_now()
    runtime_rows = [dict(row) for row in [*(product_runtime_rows or []), *(public_context_rows or [])] if isinstance(row, Mapping)]
    product_pages = [dict(row) for row in materialized_product_pages or [] if isinstance(row, Mapping)]
    repair_index = _repair_queue_index(repair_queue_rows or [])
    event_route_tickers = {
        _row_ticker(row)
        for row in runtime_rows
        if _row_ticker(row)
        and str(row.get("source_role") or row.get("requirement_id") or "") == "official_customer_order_or_deployment_event"
    }
    dynamic_route_tickers: dict[str, set[str]] = {
        route_id: {
            _row_ticker(row)
            for row in runtime_rows
            if _row_ticker(row) and str(row.get("source_role") or row.get("requirement_id") or "") == route_id
        }
        for route_id in (
            "technical_product_spec",
            "product_generation_edge",
            "product_benchmark_proxy",
            "customer_deployment_proxy",
        )
    }
    out: list[dict[str, Any]] = []
    for assignment_raw in family_assignments:
        assignment = dict(assignment_raw)
        ticker = str(assignment.get("ticker") or "").upper()
        family_id = str(assignment.get("family_id") or "")
        family = _family_by_id(family_id)
        if not family:
            continue
        aliases = [*family.get("aliases", []), *family.get("query_terms", [])]
        route_ids = list(family.get("route_ids") or [])
        for required_route_id in _default_depth_routes_for_family(family):
            if required_route_id not in route_ids:
                route_ids.append(required_route_id)
        if ticker in event_route_tickers and "official_customer_order_or_deployment_event" not in route_ids:
            route_ids.append("official_customer_order_or_deployment_event")
        for dynamic_route_id, tickers in dynamic_route_tickers.items():
            if ticker in tickers and dynamic_route_id not in route_ids:
                route_ids.append(dynamic_route_id)
        for route_id in route_ids:
            route = ROUTE_DEFINITIONS.get(route_id)
            if not route:
                continue
            row_matches = [
                row
                for row in runtime_rows
                if _row_ticker(row) == ticker and _row_matches_sources(row, route["source_ids"])
            ]
            family_matches = [row for row in row_matches if _text_matches_terms(_row_text(row), aliases)]
            page_matches = (
                [
                    row
                    for row in product_pages
                    if _row_ticker(row) == ticker and _text_matches_terms(_materialized_page_text(row), aliases)
                ]
                if route_id == "official_product_surface"
                else []
            )
            repair_rows = repair_index.get((ticker, route_id), [])
            route_status = _route_status(row_matches=row_matches, family_matches=family_matches, page_matches=page_matches, repair_rows=repair_rows)
            out.append(
                {
                    "schema_version": FAMILY_SOURCE_ROUTE_PLAN_SCHEMA_VERSION,
                    "generated_at": generated_at,
                    "route_plan_id": _stable_id("family_source_route_plan", [ticker, family_id, route_id]),
                    "ticker": ticker,
                    "company_name": assignment.get("company_name") or "",
                    "primary_lane_id": assignment.get("primary_lane_id") or "",
                    "family_lane_id": assignment.get("family_lane_id") or "",
                    "family_id": family_id,
                    "family_name": assignment.get("family_name") or family.get("family_name") or "",
                    "route_id": route_id,
                    "source_role": route["source_role"],
                    "source_ids": route["source_ids"],
                    "layer_ids": route["layer_ids"],
                    "query_terms": _unique_strings([*assignment.get("query_terms", []), *family.get("query_terms", [])]),
                    "allowed_claim_boundary": route["claim_boundary"],
                    "forbidden_claims": route["forbidden_claims"],
                    "route_status": route_status,
                    "runtime_company_row_count": len(row_matches),
                    "runtime_family_row_count": len(family_matches),
                    "materialized_product_page_count": len(page_matches),
                    "repair_queue_count": len(repair_rows),
                    "repair_seed_status": _combined_seed_status(repair_rows),
                    "repair_seed_source_ids": _unique_strings(
                        source_id
                        for row in repair_rows
                        for source_id in (row.get("repair_seed_source_ids") or [])
                    ),
                    "sample_repair_seed_refs": _unique_strings(
                        ref
                        for row in repair_rows
                        for ref in (row.get("sample_repair_seed_refs") or [])
                    )[:10],
                    "sample_evidence_refs": _sample_refs([*family_matches, *row_matches]),
                    "sample_urls": _sample_urls([*family_matches, *row_matches, *page_matches]),
                    "next_action": _route_next_action(route_status, route_id),
                }
            )
    return sorted(out, key=lambda row: (row["ticker"], row["family_id"], row["route_id"]))


def _default_depth_routes_for_family(family: Mapping[str, Any]) -> list[str]:
    lane_id = str(family.get("lane_id") or "")
    family_id = str(family.get("family_id") or "")
    if family.get("fallback") is True:
        return []
    routes: list[str] = []
    family_route_ids = set(family.get("route_ids") or [])
    if "official_product_surface" in family_route_ids:
        routes.append("official_product_profile_spec")
    if lane_id in {"V1", "V2", "V3", "V4", "V5"} and "official_product_surface" in family_route_ids:
        routes.append("technical_product_spec")
    if lane_id in {"V3", "V4", "V5", "V6", "V7", "V8"}:
        routes.append("business_service_profile_spec")
    if lane_id == "V7":
        routes.append("business_asset_profile_spec")
        if family_id in {
            "industrial_equipment",
            "aerospace_defense_industrials",
            "battery_energy_storage_components",
            "renewable_power_solar_hydrogen",
            "power_semiconductor_components",
            "power_grid_cooling",
        }:
            routes.append("technical_product_spec")
    if family_id in {
        "mass_retail_grocery",
        "consumer_electronics_retail",
        "auto_aftermarket_retail",
        "farm_ranch_rural_retail",
        "discount_retail_merchandise",
        "home_improvement",
        "homebuilding_residential",
        "restaurants_menu",
        "lodging_resorts_cruise",
        "beauty_personal_care_retail",
        "travel_marketplace",
    }:
        routes.append("business_asset_profile_spec")
    return routes


def build_family_source_fetch_audit(
    *,
    route_plan_rows: Iterable[Mapping[str, Any]],
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or _utc_now()
    rows = [dict(row) for row in route_plan_rows if isinstance(row, Mapping)]
    by_status = Counter(str(row.get("route_status") or "") for row in rows)
    by_lane: dict[str, dict[str, Any]] = {}
    for row in rows:
        lane = str(row.get("family_lane_id") or row.get("primary_lane_id") or "UNKNOWN")
        item = by_lane.setdefault(lane, {"route_count": 0, "runtime_family_ready": 0, "materialized_only": 0, "seed_only": 0, "missing": 0})
        item["route_count"] += 1
        status = str(row.get("route_status") or "")
        if status == "runtime_family_row_available":
            item["runtime_family_ready"] += 1
        elif status == "materialized_fetch_available":
            item["materialized_only"] += 1
        elif status == "seed_available_not_materialized":
            item["seed_only"] += 1
        elif status == "not_materialized":
            item["missing"] += 1
    validation = validate_family_source_route_plan(rows)
    return {
        "schema_version": FAMILY_SOURCE_FETCH_AUDIT_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "fail" if validation["status"] == "fail" else "gap" if by_status.get("not_materialized") or by_status.get("seed_available_not_materialized") else "pass",
        "route_count": len(rows),
        "summary": {
            "by_route_status": dict(sorted(by_status.items())),
            "by_lane": dict(sorted(by_lane.items())),
            "ticker_count": len({str(row.get("ticker") or "") for row in rows}),
            "family_assignment_count": len({str(row.get("ticker") or "") + "::" + str(row.get("family_id") or "") for row in rows}),
            "runtime_family_ready_route_count": by_status.get("runtime_family_row_available", 0),
            "materialized_fetch_available_route_count": by_status.get("materialized_fetch_available", 0),
            "seed_available_not_materialized_route_count": by_status.get("seed_available_not_materialized", 0),
            "not_materialized_route_count": by_status.get("not_materialized", 0),
        },
        "validation": validation,
        "top_missing_routes": [
            {
                "ticker": row.get("ticker"),
                "family_id": row.get("family_id"),
                "route_id": row.get("route_id"),
                "route_status": row.get("route_status"),
                "next_action": row.get("next_action"),
                "query_terms": row.get("query_terms"),
                "repair_seed_source_ids": row.get("repair_seed_source_ids") or [],
                "sample_repair_seed_refs": row.get("sample_repair_seed_refs") or [],
            }
            for row in rows
            if row.get("route_status") in {"not_materialized", "seed_available_not_materialized"}
        ][:100],
        "boundary": "Fetch audit checks whether family-scoped source routes already have runtime/parser rows or materialized source pages; it does not promote L2/L3 proxies to company exact facts.",
    }


def validate_product_family_lane_registry(families: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    seen: set[str] = set()
    fallback_by_lane = Counter()
    for family in families:
        family_id = str(family.get("family_id") or "")
        lane_id = str(family.get("lane_id") or "")
        if not family_id:
            errors.append({"type": "missing_family_id"})
        elif family_id in seen:
            errors.append({"type": "duplicate_family_id", "family_id": family_id})
        seen.add(family_id)
        if not lane_id:
            errors.append({"type": "missing_lane_id", "family_id": family_id})
        if family.get("fallback"):
            fallback_by_lane[lane_id] += 1
        if not family.get("route_ids"):
            errors.append({"type": "missing_route_ids", "family_id": family_id})
        for route_id in family.get("route_ids") or []:
            if route_id not in ROUTE_DEFINITIONS:
                errors.append({"type": "unknown_route_id", "family_id": family_id, "route_id": route_id})
    for lane_id in {str(family.get("lane_id") or "") for family in families}:
        if fallback_by_lane[lane_id] != 1:
            errors.append({"type": "lane_missing_single_fallback_family", "lane_id": lane_id, "count": fallback_by_lane[lane_id]})
    return {"schema_version": "finsight_product_family_lane_registry_validation_v0_1", "status": "fail" if errors else "pass", "errors": errors}


def validate_family_source_route_plan(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        row_id = str(row.get("route_plan_id") or "")
        if not row_id:
            errors.append({"type": "missing_route_plan_id", "ticker": row.get("ticker")})
        elif row_id in seen:
            errors.append({"type": "duplicate_route_plan_id", "route_plan_id": row_id})
        seen.add(row_id)
        if not row.get("family_id") or not row.get("route_id"):
            errors.append({"type": "missing_family_or_route", "ticker": row.get("ticker")})
        if not row.get("source_ids"):
            errors.append({"type": "missing_source_ids", "route_plan_id": row_id})
        if str(row.get("route_status") or "") not in {
            "runtime_family_row_available",
            "runtime_company_row_available",
            "materialized_fetch_available",
            "seed_available_not_materialized",
            "not_materialized",
        }:
            errors.append({"type": "invalid_route_status", "route_plan_id": row_id, "status": row.get("route_status")})
    return {"schema_version": "finsight_family_source_route_plan_validation_v0_1", "status": "fail" if errors else "pass", "errors": errors}


def write_product_family_route_artifacts(
    *,
    registry: Mapping[str, Any],
    assignments: Sequence[Mapping[str, Any]],
    route_plan: Sequence[Mapping[str, Any]],
    fetch_audit: Mapping[str, Any],
    output_registry_path: str | Path,
    output_assignments_path: str | Path,
    output_route_plan_path: str | Path,
    output_fetch_audit_path: str | Path,
    output_report_path: str | Path,
) -> dict[str, str]:
    registry_path = Path(output_registry_path)
    assignments_path = Path(output_assignments_path)
    route_plan_path = Path(output_route_plan_path)
    fetch_audit_path = Path(output_fetch_audit_path)
    report_path = Path(output_report_path)
    for path in (registry_path, assignments_path, route_plan_path, fetch_audit_path, report_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_jsonl(assignments_path, assignments)
    _write_jsonl(route_plan_path, route_plan)
    fetch_audit_path.write_text(json.dumps(fetch_audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(render_product_family_source_route_report(registry=registry, assignments=assignments, route_plan=route_plan, fetch_audit=fetch_audit), encoding="utf-8")
    return {
        "registry": str(registry_path),
        "assignments": str(assignments_path),
        "route_plan": str(route_plan_path),
        "fetch_audit": str(fetch_audit_path),
        "report": str(report_path),
    }


def render_product_family_source_route_report(
    *,
    registry: Mapping[str, Any],
    assignments: Sequence[Mapping[str, Any]],
    route_plan: Sequence[Mapping[str, Any]],
    fetch_audit: Mapping[str, Any],
) -> str:
    audit_summary = fetch_audit.get("summary") if isinstance(fetch_audit.get("summary"), Mapping) else {}
    lines = [
        "# Product Family Source Route Plan",
        "",
        f"- registry_schema: `{registry.get('schema_version')}`",
        f"- family_count: `{registry.get('family_count')}`",
        f"- assignment_count: `{len(assignments)}`",
        f"- route_plan_count: `{len(route_plan)}`",
        f"- fetch_audit_status: `{fetch_audit.get('status')}`",
        f"- runtime_family_ready_route_count: `{audit_summary.get('runtime_family_ready_route_count')}`",
        f"- materialized_fetch_available_route_count: `{audit_summary.get('materialized_fetch_available_route_count')}`",
        f"- seed_available_not_materialized_route_count: `{audit_summary.get('seed_available_not_materialized_route_count')}`",
        f"- not_materialized_route_count: `{audit_summary.get('not_materialized_route_count')}`",
        "",
        "## Route Status",
        "",
        "| status | count |",
        "| --- | ---: |",
    ]
    for status, count in sorted((audit_summary.get("by_route_status") or {}).items()):
        lines.append(f"| {status} | {count} |")
    lines.extend(["", "## Lane Status", "", "| lane | routes | runtime family | materialized only | seed only | missing |", "| --- | ---: | ---: | ---: | ---: | ---: |"])
    for lane, row in sorted((audit_summary.get("by_lane") or {}).items()):
        if not isinstance(row, Mapping):
            continue
        lines.append(
            f"| {lane} | {row.get('route_count')} | {row.get('runtime_family_ready')} | {row.get('materialized_only')} | {row.get('seed_only')} | {row.get('missing')} |"
        )
    lines.extend(["", "## Top Missing Routes", ""])
    for row in fetch_audit.get("top_missing_routes") or []:
        if not isinstance(row, Mapping):
            continue
        lines.append(
            f"- `{row.get('ticker')}` `{row.get('family_id')}` `{row.get('route_id')}`: "
            f"`{row.get('route_status')}`; next={row.get('next_action')}"
        )
    lines.extend(["", "## Boundary", "", str(fetch_audit.get("boundary") or ""), ""])
    return "\n".join(lines)


def load_jsonl_rows(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    file_path = Path(path)
    if not file_path.exists():
        return rows
    with file_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if text:
                rows.append(json.loads(text))
    return rows


def _company_text_index(*collections: Iterable[Mapping[str, Any]]) -> dict[str, str]:
    out: dict[str, list[str]] = defaultdict(list)
    for rows in collections:
        for row in rows:
            ticker = _row_ticker(row)
            if not ticker:
                continue
            source_ids = _row_source_ids(row)
            if source_ids and not source_ids.intersection(FAMILY_ASSIGNMENT_SOURCE_IDS):
                continue
            values = [
                row.get("company"),
                row.get("company_name"),
                row.get("industry_schema"),
                row.get("evidence_layer"),
                row.get("source_id"),
                row.get("canonical_name"),
                " ".join(row.get("aliases") or []),
                row.get("node_type"),
                row.get("product_family"),
                row.get("product_or_segment"),
                row.get("metric_name"),
                row.get("topic"),
                row.get("title"),
                row.get("preview"),
                row.get("text"),
            ]
            out[ticker].append(" ".join(str(value) for value in values if value))
    return {ticker: " ".join(parts).lower() for ticker, parts in out.items()}


def _company_haystack(assignment: Mapping[str, Any], extra_text: str) -> str:
    product_coverage = assignment.get("product_coverage") if isinstance(assignment.get("product_coverage"), Mapping) else {}
    values = [
        assignment.get("ticker"),
        assignment.get("company_name"),
        " ".join((product_coverage.get("product_sources") or {}).keys()),
        " ".join((product_coverage.get("node_layers") or {}).keys()),
        extra_text,
    ]
    return " ".join(str(value) for value in values if value).lower()


def _selected_family_ids(
    *,
    ticker: str,
    lane_id: str,
    secondary_lanes: Sequence[str],
    category: str,
    haystack: str,
    families_by_lane: Mapping[str, list[dict[str, Any]]],
) -> list[tuple[str, str, list[str]]]:
    lane_ids = [lane_id, *secondary_lanes]
    allowed_families = [family for lane in lane_ids for family in families_by_lane.get(lane, []) if not family.get("fallback")]
    selected: list[tuple[str, str, list[str]]] = []
    override_ids = TICKER_FAMILY_OVERRIDES.get(ticker, [])
    for family_id in override_ids:
        family = _family_by_id(family_id)
        if family:
            selected.append((family_id, "ticker_override", []))
    if selected:
        return selected[:4]
    for family_id in _category_family_ids(lane_id=lane_id, category=category):
        family = _family_by_id(family_id)
        if family and family in allowed_families:
            selected.append((family_id, "category_rule", []))
    if selected:
        return selected[:4]
    for family in allowed_families:
        if any(family["family_id"] == item[0] for item in selected):
            continue
        matches = _family_keyword_matches(family, haystack)
        if matches:
            selected.append((family["family_id"], "keyword_match", matches[:8]))
    if selected:
        return selected[:4]
    fallback = next((family for family in families_by_lane.get(lane_id, []) if family.get("fallback")), None)
    if fallback:
        return [(fallback["family_id"], "lane_fallback_needs_discovery", [])]
    return []


def _assignment_evidence_state(assignment: Mapping[str, Any], *, reason: str) -> str:
    coverage = assignment.get("product_coverage") if isinstance(assignment.get("product_coverage"), Mapping) else {}
    if coverage.get("product_kpi_ready"):
        return "company_disclosed_product_kpi"
    if coverage.get("official_surface_ready"):
        return "official_product_surface_context"
    if reason in {"ticker_override", "keyword_match"}:
        return "taxonomy_inferred_needs_repair"
    return "unknown_needs_discovery"


def _assignment_confidence(reason: str) -> float:
    return {"ticker_override": 0.95, "category_rule": 0.86, "keyword_match": 0.75, "lane_fallback_needs_discovery": 0.35}.get(reason, 0.5)


def _category_family_ids(*, lane_id: str, category: str) -> list[str]:
    category_text = str(category or "").strip()
    if not category_text:
        return []
    lane = str(lane_id or "").upper()
    return (
        CATEGORY_FAMILY_OVERRIDES.get((lane, category_text))
        or CATEGORY_FAMILY_OVERRIDES.get((lane, category_text.lower()))
        or []
    )


def _family_keyword_matches(family: Mapping[str, Any], haystack: str) -> list[str]:
    matches = [alias for alias in family.get("aliases", []) if _term_in_text(alias, haystack)]
    strong_matches = [term for term in matches if _is_strong_family_match_term(term)]
    return strong_matches


def _is_strong_family_match_term(term: str) -> bool:
    term_l = str(term or "").lower().strip()
    if not term_l or term_l in WEAK_FAMILY_MATCH_TERMS:
        return False
    if " " in term_l or "/" in term_l or "-" in term_l:
        return True
    if len(term_l) <= 4:
        return term_l in SHORT_STRONG_FAMILY_MATCH_TERMS
    return True


def _repair_queue_index(rows: Iterable[Mapping[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    out: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        ticker = str(row.get("ticker") or "").upper()
        req = str(row.get("requirement_id") or "")
        if ticker and req:
            out[(ticker, req)].append(dict(row))
    return out


def _route_status(
    *,
    row_matches: Sequence[Mapping[str, Any]],
    family_matches: Sequence[Mapping[str, Any]],
    page_matches: Sequence[Mapping[str, Any]],
    repair_rows: Sequence[Mapping[str, Any]],
) -> str:
    if family_matches:
        return "runtime_family_row_available"
    if row_matches:
        return "runtime_company_row_available"
    if page_matches:
        return "materialized_fetch_available"
    if any(str(row.get("repair_seed_status") or "") == "seed_available" for row in repair_rows):
        return "seed_available_not_materialized"
    return "not_materialized"


def _route_next_action(status: str, route_id: str) -> str:
    if status == "runtime_family_row_available":
        return "ready_for_family_scoped_specialist_input"
    if status == "runtime_company_row_available":
        return "tighten_product_family_binding_or_alias_resolver"
    if status == "materialized_fetch_available":
        return "parse_materialized_source_into_family_bound_runtime_rows"
    if status == "seed_available_not_materialized":
        return "resolve_seed_to_url_or_raw_snapshot_then_fetch_and_parse"
    return f"discover_allowed_source_for_{route_id}_then_fetch_parse_resolve"


def _combined_seed_status(rows: Sequence[Mapping[str, Any]]) -> str:
    if not rows:
        return "not_in_company_repair_queue"
    if any(str(row.get("repair_seed_status") or "") == "seed_available" for row in rows):
        return "seed_available"
    return "seed_missing"


def _family_by_id(family_id: str) -> dict[str, Any] | None:
    for family in FAMILY_DEFINITIONS:
        if family["family_id"] == family_id:
            return family
    return None


def _row_ticker(row: Mapping[str, Any]) -> str:
    direct = str(row.get("ticker") or row.get("issuer_ticker") or "").strip().upper()
    if direct:
        return direct
    binding = row.get("entity_binding") if isinstance(row.get("entity_binding"), Mapping) else {}
    return str(binding.get("issuer_ticker") or "").strip().upper()


def _row_source_ids(row: Mapping[str, Any]) -> set[str]:
    values = {
        str(row.get("source_id") or "").strip(),
        str(row.get("underlying_source_id") or "").strip(),
    }
    if str(row.get("schema_version") or "").startswith("fin_agent_company_product_taxonomy_normalized"):
        values.add("sec_product_taxonomy_normalized")
    source_class = str(row.get("source_class") or "").strip()
    if source_class:
        values.add(SOURCE_CLASS_TO_SOURCE_ID.get(source_class, source_class))
    return {value for value in values if value}


def _row_matches_sources(row: Mapping[str, Any], source_ids: Sequence[str]) -> bool:
    return bool(_row_source_ids(row).intersection({str(source_id) for source_id in source_ids}))


def _row_text(row: Mapping[str, Any]) -> str:
    citation = row.get("citation") if isinstance(row.get("citation"), Mapping) else {}
    values = [
        row.get("product_family"),
        row.get("product_or_segment"),
        row.get("canonical_name"),
        " ".join(row.get("aliases") or []),
        row.get("node_type"),
        row.get("topic"),
        row.get("metric_name"),
        row.get("title"),
        row.get("source_title"),
        row.get("preview"),
        row.get("text"),
        row.get("structured_context_summary"),
        citation.get("title"),
    ]
    return " ".join(str(value) for value in values if value).lower()


def _materialized_page_text(row: Mapping[str, Any]) -> str:
    text_parts = [
        row.get("ticker"),
        row.get("company"),
        row.get("product"),
        row.get("title"),
        row.get("source_url"),
    ]
    clean_path = Path(str(row.get("clean_text_path") or ""))
    if clean_path.exists():
        try:
            text_parts.append(clean_path.read_text(encoding="utf-8", errors="replace")[:5000])
        except OSError:
            pass
    return " ".join(str(value) for value in text_parts if value).lower()


def _text_matches_terms(text: str, terms: Sequence[str]) -> bool:
    return any(_term_in_text(term, text) for term in terms if str(term).strip())


def _term_in_text(term: str, text: str) -> bool:
    term_l = str(term or "").lower().strip()
    if not term_l:
        return False
    if len(term_l) <= 3:
        return re.search(rf"\b{re.escape(term_l)}\b", text) is not None
    return term_l in text


def _sample_refs(rows: Sequence[Mapping[str, Any]], limit: int = 5) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for row in rows:
        ref = str(row.get("evidence_ref") or row.get("evidence_id") or row.get("snapshot_id") or "").strip()
        if ref and ref not in seen:
            out.append(ref)
            seen.add(ref)
        if len(out) >= limit:
            break
    return out


def _sample_urls(rows: Sequence[Mapping[str, Any]], limit: int = 5) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for row in rows:
        citation = row.get("citation") if isinstance(row.get("citation"), Mapping) else {}
        url = str(row.get("source_url") or row.get("url") or row.get("snapshot_url") or citation.get("url") or "").strip()
        if url and url not in seen:
            out.append(url)
            seen.add(url)
        if len(out) >= limit:
            break
    return out


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
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")


def _stable_id(prefix: str, parts: Sequence[str]) -> str:
    digest = hashlib.sha1("::".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}:{digest}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
