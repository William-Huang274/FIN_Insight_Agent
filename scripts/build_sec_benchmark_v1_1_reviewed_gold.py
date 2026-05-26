from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


SEMI_CASE = "SEMICONDUCTOR_DURABILITY_2023_2025_DIAG_001"
CAPEX_CASE = "CAPEX_FCF_TABLE_2023_2025_DIAG_001"
SUBSCRIPTION_CASE = "SUBSCRIPTION_VISIBILITY_COMPARISON_2023_2025_DIAG_001"
ADS_CASE = "ADS_AI_INFRA_GROWTH_QUALITY_2023_2025_DIAG_001"


TABLE_SOURCES: dict[str, dict[str, dict[str, Any]]] = {
    SEMI_CASE: {
        "NVDA_2025_compute_networking": {
            "ticker": "NVDA",
            "source_evidence_id": "NVDA_2025_10K_ITEM7_BLOCK_0004_CHUNK_0001",
            "object_id": "NVDA_2025_10K_ITEM7_BLOCK_0004_CHUNK_0001_TABLE_F0B8DEBD",
            "section": "Item 7. Management's Discussion and Analysis",
            "text": (
                "NVIDIA fiscal 2025 10-K Revenue by Reportable Segments table, USD millions. "
                "Compute & Networking revenue: Jan 26 2025: 116,193; Jan 28 2024: 47,405."
            ),
        },
        "NVDA_2024_compute_networking": {
            "ticker": "NVDA",
            "source_evidence_id": "NVDA_2024_10K_ITEM7_BLOCK_0005_CHUNK_0001",
            "object_id": "NVDA_2024_10K_ITEM7_BLOCK_0005_CHUNK_0001_TABLE_5220265F",
            "section": "Item 7. Management's Discussion and Analysis",
            "text": (
                "NVIDIA fiscal 2024 10-K Revenue by Reportable Segments table, USD millions. "
                "Compute & Networking revenue: Jan 28 2024: 47,405; Jan 29 2023: 15,068."
            ),
        },
        "AMD_2025_data_center": {
            "ticker": "AMD",
            "source_evidence_id": "AMD_2025_10K_ITEM8_BLOCK_0005_PART_01_OF_02",
            "object_id": "AMD_2025_10K_ITEM8_BLOCK_0005_PART_01_OF_02_TABLE_78EF91B2",
            "section": "Item 8. Financial Statements and Supplementary Data",
            "text": (
                "AMD fiscal 2025 10-K segment reporting table, USD millions. "
                "Data Center net revenue: 2025: 16,635; 2024: 12,579; 2023: 6,496. "
                "The same note defines Data Center as server CPUs, GPUs, AI accelerators, DPUs, AI NICs, FPGAs, and adaptive SoC products for data centers."
            ),
        },
    },
    CAPEX_CASE: {
        "MSFT_2025_cash_flow": {
            "ticker": "MSFT",
            "source_evidence_id": "MSFT_2025_10K_ITEM8_BLOCK_0002_CHUNK_0001",
            "object_id": "MSFT_2025_10K_ITEM8_BLOCK_0002_CHUNK_0001_TABLE_EAADC44F",
            "section": "Item 8. Financial Statements and Supplementary Data",
            "text": (
                "Microsoft fiscal 2025 10-K consolidated cash-flow table, USD millions. "
                "Net cash from operations: 2025: 136,162; 2024: 118,548; 2023: 87,582. "
                "Additions to property and equipment: 2025: (64,551); 2024: (44,477); 2023: (28,107)."
            ),
        },
        "GOOGL_2025_cash_flow": {
            "ticker": "GOOGL",
            "source_evidence_id": "GOOGL_2025_10K_ITEM8_BLOCK_0001_PART_05_OF_05",
            "object_id": "GOOGL_2025_10K_ITEM8_BLOCK_0001_PART_05_OF_05_TABLE_1EE9E9B4",
            "section": "Item 8. Financial Statements and Supplementary Data",
            "text": (
                "Alphabet fiscal 2025 10-K consolidated cash-flow table, USD millions. "
                "Net cash provided by operating activities: 2023: 101,746; 2024: 125,299; 2025: 164,713. "
                "Purchases of property and equipment: 2023: (32,251); 2024: (52,535); 2025: (91,447)."
            ),
        },
        "META_2025_cash_flow": {
            "ticker": "META",
            "source_evidence_id": "META_2025_10K_ITEM8_BLOCK_0001_PART_05_OF_05",
            "object_id": "META_2025_10K_ITEM8_BLOCK_0001_PART_05_OF_05_TABLE_9AC1A5D6",
            "section": "Item 8. Financial Statements and Supplementary Data",
            "text": (
                "Meta fiscal 2025 10-K consolidated cash-flow table, USD millions. "
                "Net cash provided by operating activities: 2025: 115,800; 2024: 91,328; 2023: 71,113. "
                "Purchases of property and equipment: 2025: (69,691); 2024: (37,256); 2023: (27,045)."
            ),
        },
        "AMZN_2025_cash_flow": {
            "ticker": "AMZN",
            "source_evidence_id": "AMZN_2025_10K_ITEM8_BLOCK_0001_PART_03_OF_04",
            "object_id": "AMZN_2025_10K_ITEM8_BLOCK_0001_PART_03_OF_04_TABLE_14A110BC",
            "section": "Item 8. Financial Statements and Supplementary Data",
            "text": (
                "Amazon fiscal 2025 10-K consolidated cash-flow table, USD millions. "
                "Net cash provided by operating activities: 2023: 84,946; 2024: 115,877; 2025: 139,514. "
                "Purchases of property and equipment: 2023: (52,729); 2024: (82,999); 2025: (131,819)."
            ),
        },
    },
    SUBSCRIPTION_CASE: {
        "ADBE_2025_subscription_revenue": {
            "ticker": "ADBE",
            "source_evidence_id": "ADBE_2025_10K_ITEM8_BLOCK_0001_PART_01_OF_03",
            "object_id": "ADBE_2025_10K_ITEM8_BLOCK_0001_PART_01_OF_03_TABLE_B14EC58B",
            "section": "Item 8. Financial Statements and Supplementary Data",
            "text": (
                "Adobe fiscal 2025 10-K consolidated statements of income table, USD millions. "
                "Subscription revenue: Nov 28 2025: 22,904; Nov 29 2024: 20,521; Dec 1 2023: 18,284."
            ),
        },
        "SNOW_2025_product_revenue": {
            "ticker": "SNOW",
            "source_evidence_id": "SNOW_2025_10K_ITEM8_BLOCK_0002_PART_04_OF_26",
            "object_id": "SNOW_2025_10K_ITEM8_BLOCK_0002_PART_04_OF_26_TABLE_DC9FDF75",
            "section": "Item 8. Financial Statements and Supplementary Data",
            "text": (
                "Snowflake fiscal 2025 10-K revenue disaggregation table, USD thousands. "
                "Product revenue: fiscal 2025: 3,462,422; fiscal 2024: 2,666,849; fiscal 2023: 1,938,783."
            ),
        },
        "PANW_2025_subscription_support_revenue": {
            "ticker": "PANW",
            "source_evidence_id": "PANW_2025_10K_ITEM8_BLOCK_0001_PART_03_OF_21",
            "object_id": "PANW_2025_10K_ITEM8_BLOCK_0001_PART_03_OF_21_TABLE_7BB65710",
            "section": "Item 8. Financial Statements and Supplementary Data",
            "text": (
                "Palo Alto Networks fiscal 2025 10-K consolidated statements of operations table, USD millions. "
                "Subscription and support revenue: fiscal 2025: 7,419.6; fiscal 2024: 6,424.2; fiscal 2023: 5,314.3."
            ),
        },
    },
    ADS_CASE: {
        "GOOGL_2025_advertising_revenue": {
            "ticker": "GOOGL",
            "source_evidence_id": "GOOGL_2025_10K_ITEM8_BLOCK_0003_CHUNK_0001",
            "object_id": "GOOGL_2025_10K_ITEM8_BLOCK_0003_CHUNK_0001_TABLE_528579E1",
            "section": "Item 8. Financial Statements and Supplementary Data",
            "text": (
                "Alphabet fiscal 2025 10-K revenue disaggregation table, USD millions. "
                "Google advertising revenue: 2023: 237,855; 2024: 264,590; 2025: 294,691."
            ),
        },
        "GOOGL_2025_operating_income": {
            "ticker": "GOOGL",
            "source_evidence_id": "GOOGL_2025_10K_ITEM8_BLOCK_0017_CHUNK_0001",
            "object_id": "GOOGL_2025_10K_ITEM8_BLOCK_0017_CHUNK_0001_TABLE_E769DDFE",
            "section": "Item 8. Financial Statements and Supplementary Data",
            "text": (
                "Alphabet fiscal 2025 10-K segment revenue, profitability, and expense table, USD millions. "
                "Total income from operations: 2023: 84,293; 2024: 112,390; 2025: 129,039."
            ),
        },
        "GOOGL_2025_capex": {
            "ticker": "GOOGL",
            "source_evidence_id": "GOOGL_2025_10K_ITEM8_BLOCK_0001_PART_05_OF_05",
            "object_id": "GOOGL_2025_10K_ITEM8_BLOCK_0001_PART_05_OF_05_TABLE_1EE9E9B4",
            "section": "Item 8. Financial Statements and Supplementary Data",
            "text": (
                "Alphabet fiscal 2025 10-K consolidated cash-flow table, USD millions. "
                "Purchases of property and equipment: 2023: (32,251); 2024: (52,535); 2025: (91,447)."
            ),
        },
        "META_2025_advertising_revenue": {
            "ticker": "META",
            "source_evidence_id": "META_2025_10K_ITEM8_BLOCK_0003_CHUNK_0001",
            "object_id": "META_2025_10K_ITEM8_BLOCK_0003_CHUNK_0001_TABLE_4153538C",
            "section": "Item 8. Financial Statements and Supplementary Data",
            "text": (
                "Meta fiscal 2025 10-K revenue disaggregation table, USD millions. "
                "Advertising revenue: 2025: 196,175; 2024: 160,633; 2023: 131,948."
            ),
        },
        "META_2025_operating_income": {
            "ticker": "META",
            "source_evidence_id": "META_2025_10K_ITEM7_BLOCK_0009_PART_01_OF_02",
            "object_id": "META_2025_10K_ITEM7_BLOCK_0009_PART_01_OF_02_TABLE_9C61CACF",
            "section": "Item 7. Management's Discussion and Analysis",
            "text": (
                "Meta fiscal 2025 10-K segment profitability table, USD millions. "
                "Total income from operations: 2025: 83,276; 2024: 69,380; 2023: 46,751."
            ),
        },
        "META_2025_capex": {
            "ticker": "META",
            "source_evidence_id": "META_2025_10K_ITEM8_BLOCK_0001_PART_05_OF_05",
            "object_id": "META_2025_10K_ITEM8_BLOCK_0001_PART_05_OF_05_TABLE_9AC1A5D6",
            "section": "Item 8. Financial Statements and Supplementary Data",
            "text": (
                "Meta fiscal 2025 10-K consolidated cash-flow table, USD millions. "
                "Purchases of property and equipment: 2025: (69,691); 2024: (37,256); 2023: (27,045)."
            ),
        },
    },
}


SEMI_FACTS = [
    ("NVDA", 2023, "compute_revenue", "Compute & Networking revenue", "15,068", 15068.0, "NVDA_2024_compute_networking", "Compute & Networking", "Jan 29, 2023"),
    ("NVDA", 2024, "compute_revenue", "Compute & Networking revenue", "47,405", 47405.0, "NVDA_2025_compute_networking", "Compute & Networking", "Jan 28, 2024"),
    ("NVDA", 2025, "compute_revenue", "Compute & Networking revenue", "116,193", 116193.0, "NVDA_2025_compute_networking", "Compute & Networking", "Jan 26, 2025"),
    ("AMD", 2023, "data_center_revenue", "Data Center net revenue", "6,496", 6496.0, "AMD_2025_data_center", "Data Center", "December 30, 2023"),
    ("AMD", 2024, "data_center_revenue", "Data Center net revenue", "12,579", 12579.0, "AMD_2025_data_center", "Data Center", "December 28, 2024"),
    ("AMD", 2025, "data_center_revenue", "Data Center net revenue", "16,635", 16635.0, "AMD_2025_data_center", "Data Center", "December 27, 2025"),
]


CAPEX_INPUTS: dict[str, dict[int, dict[str, int]]] = {
    "MSFT": {
        2023: {"cash_flow": 87582, "ppe_purchases": -28107},
        2024: {"cash_flow": 118548, "ppe_purchases": -44477},
        2025: {"cash_flow": 136162, "ppe_purchases": -64551},
    },
    "GOOGL": {
        2023: {"cash_flow": 101746, "ppe_purchases": -32251},
        2024: {"cash_flow": 125299, "ppe_purchases": -52535},
        2025: {"cash_flow": 164713, "ppe_purchases": -91447},
    },
    "META": {
        2023: {"cash_flow": 71113, "ppe_purchases": -27045},
        2024: {"cash_flow": 91328, "ppe_purchases": -37256},
        2025: {"cash_flow": 115800, "ppe_purchases": -69691},
    },
    "AMZN": {
        2023: {"cash_flow": 84946, "ppe_purchases": -52729},
        2024: {"cash_flow": 115877, "ppe_purchases": -82999},
        2025: {"cash_flow": 139514, "ppe_purchases": -131819},
    },
}


CAPEX_SOURCE_KEY = {
    "MSFT": "MSFT_2025_cash_flow",
    "GOOGL": "GOOGL_2025_cash_flow",
    "META": "META_2025_cash_flow",
    "AMZN": "AMZN_2025_cash_flow",
}


SUBSCRIPTION_FACTS = [
    ("ADBE", 2023, "subscription_revenue", "Subscription revenue", "$ 18,284", 18284.0, "ADBE_2025_subscription_revenue", "Subscription", "December 1, 2023", "usd_millions"),
    ("ADBE", 2024, "subscription_revenue", "Subscription revenue", "$ 20,521", 20521.0, "ADBE_2025_subscription_revenue", "Subscription", "November 29, 2024", "usd_millions"),
    ("ADBE", 2025, "subscription_revenue", "Subscription revenue", "$ 22,904", 22904.0, "ADBE_2025_subscription_revenue", "Subscription", "November 28, 2025", "usd_millions"),
    ("SNOW", 2023, "product_revenue", "Product revenue", "$ 1,938,783", 1938783.0, "SNOW_2025_product_revenue", "Product revenue", "2023", "usd_thousands"),
    ("SNOW", 2024, "product_revenue", "Product revenue", "$ 2,666,849", 2666849.0, "SNOW_2025_product_revenue", "Product revenue", "2024", "usd_thousands"),
    ("SNOW", 2025, "product_revenue", "Product revenue", "$ 3,462,422", 3462422.0, "SNOW_2025_product_revenue", "Product revenue", "2025", "usd_thousands"),
    ("PANW", 2023, "subscription_revenue", "Subscription and support revenue", "5,314.3", 5314.3, "PANW_2025_subscription_support_revenue", "Subscription and support", "2023", "usd_millions"),
    ("PANW", 2024, "subscription_revenue", "Subscription and support revenue", "6,424.2", 6424.2, "PANW_2025_subscription_support_revenue", "Subscription and support", "2024", "usd_millions"),
    ("PANW", 2025, "subscription_revenue", "Subscription and support revenue", "7,419.6", 7419.6, "PANW_2025_subscription_support_revenue", "Subscription and support", "2025", "usd_millions"),
]


ADS_FACTS = [
    ("GOOGL", 2023, "advertising_revenue", "Google advertising revenue", "237,855", 237855.0, "GOOGL_2025_advertising_revenue", "Google advertising", "2023"),
    ("GOOGL", 2024, "advertising_revenue", "Google advertising revenue", "264,590", 264590.0, "GOOGL_2025_advertising_revenue", "Google advertising", "2024"),
    ("GOOGL", 2025, "advertising_revenue", "Google advertising revenue", "294,691", 294691.0, "GOOGL_2025_advertising_revenue", "Google advertising", "2025"),
    ("GOOGL", 2023, "operating_income", "Total income from operations", "$ 84,293", 84293.0, "GOOGL_2025_operating_income", "Total income from operations", "2023"),
    ("GOOGL", 2024, "operating_income", "Total income from operations", "$ 112,390", 112390.0, "GOOGL_2025_operating_income", "Total income from operations", "2024"),
    ("GOOGL", 2025, "operating_income", "Total income from operations", "$ 129,039", 129039.0, "GOOGL_2025_operating_income", "Total income from operations", "2025"),
    ("GOOGL", 2023, "capex", "Purchases of property and equipment", "( 32,251 )", -32251.0, "GOOGL_2025_capex", "Purchases of property and equipment", "2023"),
    ("GOOGL", 2024, "capex", "Purchases of property and equipment", "( 52,535 )", -52535.0, "GOOGL_2025_capex", "Purchases of property and equipment", "2024"),
    ("GOOGL", 2025, "capex", "Purchases of property and equipment", "( 91,447 )", -91447.0, "GOOGL_2025_capex", "Purchases of property and equipment", "2025"),
    ("META", 2023, "advertising_revenue", "Advertising revenue", "$ 131,948", 131948.0, "META_2025_advertising_revenue", "Advertising", "2023"),
    ("META", 2024, "advertising_revenue", "Advertising revenue", "$ 160,633", 160633.0, "META_2025_advertising_revenue", "Advertising", "2024"),
    ("META", 2025, "advertising_revenue", "Advertising revenue", "$ 196,175", 196175.0, "META_2025_advertising_revenue", "Advertising", "2025"),
    ("META", 2023, "operating_income", "Total income from operations", "$ 46,751", 46751.0, "META_2025_operating_income", "Total income from operations", "2023"),
    ("META", 2024, "operating_income", "Total income from operations", "$ 69,380", 69380.0, "META_2025_operating_income", "Total income from operations", "2024"),
    ("META", 2025, "operating_income", "Total income from operations", "$ 83,276", 83276.0, "META_2025_operating_income", "Total income from operations", "2025"),
    ("META", 2023, "capex", "Purchases of property and equipment", "( 27,045 )", -27045.0, "META_2025_capex", "Purchases of property and equipment", "2023"),
    ("META", 2024, "capex", "Purchases of property and equipment", "( 37,256 )", -37256.0, "META_2025_capex", "Purchases of property and equipment", "2024"),
    ("META", 2025, "capex", "Purchases of property and equipment", "( 69,691 )", -69691.0, "META_2025_capex", "Purchases of property and equipment", "2025"),
]


METRIC_LABELS = {
    "cash_flow": ("net cash provided by operating activities", "cash_flow", "total_value"),
    "ppe_purchases": ("purchases of property and equipment", "ppe_purchases", "total_value"),
    "free_cash_flow_proxy": ("free cash flow proxy", "free_cash_flow_proxy", "derived_value"),
}


TEXT_CONTEXT_ROWS = {
    SEMI_CASE: [
        {
            "ticker": "NVDA",
            "fiscal_year": 2025,
            "source_evidence_id": "NVDA_2025_10K_ITEM7_BLOCK_0001_PART_03_OF_04",
            "section": "Item 7. Management's Discussion and Analysis",
            "gold_role": "growth_driver_context",
            "text": (
                "NVIDIA states that fiscal 2025 Data Center revenue was up 142% from a year ago, driven by demand for its Hopper architecture accelerated-computing platform used for large language models, recommendation engines, and generative AI applications; it also began shipping production systems of the Blackwell architecture in Q4 FY2025."
            ),
        },
        {
            "ticker": "NVDA",
            "fiscal_year": 2025,
            "source_evidence_id": "NVDA_2025_10K_ITEM7_BLOCK_0008_CHUNK_0001",
            "section": "Item 7. Management's Discussion and Analysis",
            "gold_role": "customer_concentration_context",
            "text": (
                "NVIDIA disclosed direct customers representing 10% or more of total revenue in FY2025: Customer A 12%, Customer B 11%, and Customer C 11%, all primarily attributable to Compute & Networking; it also states no customer represented 10% or more of total revenue in FY2023."
            ),
        },
        {
            "ticker": "NVDA",
            "fiscal_year": 2025,
            "source_evidence_id": "NVDA_2025_10K_ITEM1A_BLOCK_0004_PART_01_OF_03",
            "section": "Item 1A. Risk Factors",
            "gold_role": "supply_demand_risk_context",
            "text": (
                "NVIDIA risk factors say long manufacturing lead times, uncertain supply and component availability, and failure to estimate customer demand accurately could lead to supply-demand mismatches; it may pay premiums, deposits, or long-term commitments to secure capacity."
            ),
        },
        {
            "ticker": "NVDA",
            "fiscal_year": 2025,
            "source_evidence_id": "NVDA_2025_10K_ITEM1A_BLOCK_0012_PART_02_OF_03",
            "section": "Item 1A. Risk Factors",
            "gold_role": "export_control_context",
            "text": (
                "NVIDIA risk factors state that export controls on AI-related semiconductors can restrict products and services, disrupt supply and distribution channels, reduce demand in affected markets, and create excess inventory or related supply charges."
            ),
        },
        {
            "ticker": "AMD",
            "fiscal_year": 2025,
            "source_evidence_id": "AMD_2025_10K_ITEM1_BLOCK_0003_PART_01_OF_04",
            "section": "Item 1. Business",
            "gold_role": "segment_definition_context",
            "text": (
                "AMD defines its Data Center segment as server-class CPUs, GPUs, AI accelerators, DPUs, AI NICs, FPGAs, and adaptive SoC products, serving computational, visual data processing, and AI workload acceleration needs in the data center market."
            ),
        },
        {
            "ticker": "AMD",
            "fiscal_year": 2025,
            "source_evidence_id": "AMD_2025_10K_ITEM8_BLOCK_0005_PART_01_OF_02",
            "section": "Item 8. Financial Statements and Supplementary Data",
            "gold_role": "customer_concentration_context",
            "text": (
                "AMD segment reporting note states no customer accounted for at least 10% of consolidated net revenue in fiscal years 2025 and 2024; one Client and Gaming segment customer accounted for 18% in fiscal 2023."
            ),
        },
        {
            "ticker": "AMD",
            "fiscal_year": 2025,
            "source_evidence_id": "AMD_2025_10K_ITEM1A_BLOCK_0003_PART_01_OF_02",
            "section": "Item 1A. Risk Factors",
            "gold_role": "demand_cyclicality_context",
            "text": (
                "AMD risk factors state that the semiconductor industry is cyclical, subject to supply-demand imbalances and rapid product change; AI growth creates pressure to timely design, manufacture, and deliver semiconductor products and solutions for computing power and AI infrastructure."
            ),
        },
        {
            "ticker": "AMD",
            "fiscal_year": 2025,
            "source_evidence_id": "AMD_2025_10K_ITEM1A_BLOCK_0010_PART_01_OF_02",
            "section": "Item 1A. Risk Factors",
            "gold_role": "manufacturing_supply_context",
            "text": (
                "AMD risk factors state it relies on third-party foundries, ATMP partners, and other suppliers; if suppliers cannot meet manufacturing requirements or AMD experiences supply constraints, it may allocate reduced quantities among customers and lose sales."
            ),
        },
    ],
    CAPEX_CASE: [
        {
            "ticker": "ALL",
            "fiscal_year": 2025,
            "source_evidence_id": "REVIEW_NOTE_DERIVED_FCF_PROXY",
            "section": "review_note",
            "gold_role": "derived_metric_definition",
            "text": (
                "For this reviewed case, free cash flow proxy is a deterministic reviewed calculation: net cash provided by operating activities plus the negative cash outflow for purchases/additions of property and equipment. Do not use total investing cash flow as capex, and do not calculate the proxy if either input cell is missing."
            ),
        }
    ],
    SUBSCRIPTION_CASE: [
        {
            "ticker": "ADBE",
            "fiscal_year": 2023,
            "source_evidence_id": "ADBE_2023_10K_ITEM7_BLOCK_0004_PART_01_OF_03",
            "section": "Item 7. Management's Discussion and Analysis",
            "gold_role": "arr_definition_context",
            "text": (
                "Adobe states ARR is a key Digital Media performance metric, should be viewed independently of revenue, deferred revenue, and RPO, and is calculated from Creative ARR plus Document Cloud ARR; fiscal 2023 Digital Media ARR was $15.17 billion."
            ),
        },
        {
            "ticker": "ADBE",
            "fiscal_year": 2023,
            "source_evidence_id": "ADBE_2023_10K_ITEM1A_BLOCK_0016_CHUNK_0001",
            "section": "Item 1A. Risk Factors",
            "gold_role": "subscription_renewal_caveat",
            "text": (
                "Adobe risk factors state subscription revenue is generally recognized ratably over subscription terms, so changes in subscriptions or renewals may not be immediately reflected in reported revenue; renewal rates may decline or fluctuate."
            ),
        },
        {
            "ticker": "SNOW",
            "fiscal_year": 2025,
            "source_evidence_id": "SNOW_2025_10K_ITEM8_BLOCK_0002_PART_03_OF_26",
            "section": "Item 8. Financial Statements and Supplementary Data",
            "gold_role": "consumption_model_caveat",
            "text": (
                "Snowflake states capacity arrangements may be classified between current and non-current deferred revenue using assumed ratable consumption, but revenue is generally recognized on consumption because customers have flexibility in consumption."
            ),
        },
        {
            "ticker": "SNOW",
            "fiscal_year": 2025,
            "source_evidence_id": "SNOW_2025_10K_ITEM8_BLOCK_0002_PART_04_OF_26",
            "section": "Item 8. Financial Statements and Supplementary Data",
            "gold_role": "rpo_consumption_caveat",
            "text": (
                "Snowflake defines RPO as contracted future revenue not yet recognized, excludes on-demand arrangements without minimum commitments, and states timing of revenue recognition depends on future customer consumption and may extend if unused capacity rolls over."
            ),
        },
        {
            "ticker": "PANW",
            "fiscal_year": 2023,
            "source_evidence_id": "PANW_2023_10K_ITEM1A_BLOCK_0005_CHUNK_0001",
            "section": "Item 1A. Risk Factors",
            "gold_role": "subscription_renewal_caveat",
            "text": (
                "Palo Alto Networks states subscription and support revenue is recognized over the relevant service period, typically one to five years; existing customers may not renew or may renew on less favorable or shorter terms."
            ),
        },
        {
            "ticker": "PANW",
            "fiscal_year": 2025,
            "source_evidence_id": "PANW_2025_10K_ITEM8_BLOCK_0001_PART_03_OF_21",
            "section": "Item 8. Financial Statements and Supplementary Data",
            "gold_role": "rpo_deferred_revenue_context",
            "text": (
                "Palo Alto Networks fiscal 2025 10-K reports subscription and support revenue by year, revenue recognized from prior deferred revenue, and remaining performance obligations of $15.8 billion with about $7.0 billion expected over the next 12 months."
            ),
        },
    ],
    ADS_CASE: [
        {
            "ticker": "GOOGL",
            "fiscal_year": 2025,
            "source_evidence_id": "GOOGL_2025_10K_ITEM7_BLOCK_0004_CHUNK_0001",
            "section": "Item 7. Management's Discussion and Analysis",
            "gold_role": "technical_infrastructure_capex_context",
            "text": (
                "Alphabet states it continues to invest in capital expenditures as it scales technical infrastructure, in particular for AI, and expects technical infrastructure costs such as depreciation, energy, equipment, and network capacity to significantly increase as AI offerings require more compute power."
            ),
        },
        {
            "ticker": "GOOGL",
            "fiscal_year": 2025,
            "source_evidence_id": "GOOGL_2025_10K_ITEM1A_BLOCK_0003_PART_01_OF_02",
            "section": "Item 1A. Risk Factors",
            "gold_role": "ads_ai_attribution_caveat",
            "text": (
                "Alphabet risk factors frame AI-optimized infrastructure and AI capabilities as investments across businesses, helpful to users, advertisers, publishers, customers, content providers, and distribution partners; the filing does not attribute all infrastructure investment to advertising products."
            ),
        },
        {
            "ticker": "GOOGL",
            "fiscal_year": 2025,
            "source_evidence_id": "GOOGL_2025_10K_ITEM1A_BLOCK_0004_PART_01_OF_03",
            "section": "Item 1A. Risk Factors",
            "gold_role": "margin_pressure_caveat",
            "text": (
                "Alphabet says revenue growth could decline over time and operating margin may face downward pressure from higher technical infrastructure investment, regulation, competition, lower-margin mix, and costs that may not correlate with revenue."
            ),
        },
        {
            "ticker": "GOOGL",
            "fiscal_year": 2025,
            "source_evidence_id": "GOOGL_2025_10K_ITEM7_BLOCK_0012_CHUNK_0001",
            "section": "Item 7. Management's Discussion and Analysis",
            "gold_role": "cost_structure_context",
            "text": (
                "Alphabet describes other cost of revenues as including depreciation primarily related to technical infrastructure, employee compensation for technical infrastructure and other operations, and energy, equipment, and network capacity costs; TAC rates differ by advertising channel."
            ),
        },
        {
            "ticker": "META",
            "fiscal_year": 2025,
            "source_evidence_id": "META_2025_10K_ITEM7_BLOCK_0005_PART_02_OF_03",
            "section": "Item 7. Management's Discussion and Analysis",
            "gold_role": "ads_monetization_ai_context",
            "text": (
                "Meta states it is investing in Reels and AI initiatives, including an AI-powered discovery engine, and has seen improved user engagement and monetization, while Reels monetizes at a lower rate and Meta cannot precisely quantify which trends drove advertising revenue."
            ),
        },
        {
            "ticker": "META",
            "fiscal_year": 2025,
            "source_evidence_id": "META_2025_10K_ITEM7_BLOCK_0008_PART_02_OF_02",
            "section": "Item 7. Management's Discussion and Analysis",
            "gold_role": "ai_cost_pressure_context",
            "text": (
                "Meta states research and development expenses increased in 2025 mostly due to higher employee compensation and infrastructure costs related to research and development, including AI initiatives."
            ),
        },
        {
            "ticker": "META",
            "fiscal_year": 2025,
            "source_evidence_id": "META_2025_10K_ITEM7_BLOCK_0009_PART_01_OF_02",
            "section": "Item 7. Management's Discussion and Analysis",
            "gold_role": "operating_leverage_context",
            "text": (
                "Meta says 2025 Family of Apps operating income increased, driven by higher advertising revenue and partially offset by increased costs and expenses, including employee compensation, infrastructure costs, partner arrangements, and legal-related costs."
            ),
        },
        {
            "ticker": "META",
            "fiscal_year": 2025,
            "source_evidence_id": "META_2025_10K_ITEM7_BLOCK_0011_CHUNK_0001",
            "section": "Item 7. Management's Discussion and Analysis",
            "gold_role": "infrastructure_ai_commitment_context",
            "text": (
                "Meta states it has increased investments in infrastructure and AI initiatives and expects to continue doing so; disclosed commitments are mostly related to third-party cloud capacity, servers and network infrastructure, data centers, and Reality Labs hardware."
            ),
        },
    ],
}


def main() -> None:
    evidence_by_id = _load_evidence_index()
    reviewed_context_dir = REPO_ROOT / "eval" / "sec_cases" / "reviewed_gold_context"
    reviewed_facts_dir = REPO_ROOT / "eval" / "sec_cases" / "reviewed_gold_facts"
    report_dir = REPO_ROOT / "reports" / "quality"
    reviewed_context_dir.mkdir(parents=True, exist_ok=True)
    reviewed_facts_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    semi_facts = _semi_facts()
    capex_facts = _capex_facts()
    subscription_facts = _subscription_facts()
    ads_facts = _ads_facts()
    _write_case_artifacts(
        SEMI_CASE,
        semi_facts,
        _case_context_rows(SEMI_CASE, semi_facts, evidence_by_id),
        reviewed_context_dir,
        reviewed_facts_dir,
        review_scope={
            "companies": ["NVDA", "AMD"],
            "years": [2023, 2024, 2025],
            "source_policy": "SEC_ONLY",
            "allowed_filing_types": ["10-K"],
            "source_basis": "reviewed NVIDIA Compute & Networking proxy and AMD Data Center segment facts plus SEC risk/caveat context",
        },
    )
    _write_case_artifacts(
        CAPEX_CASE,
        capex_facts,
        _case_context_rows(CAPEX_CASE, capex_facts, evidence_by_id),
        reviewed_context_dir,
        reviewed_facts_dir,
        review_scope={
            "companies": ["MSFT", "GOOGL", "META", "AMZN"],
            "years": [2023, 2024, 2025],
            "source_policy": "SEC_ONLY",
            "allowed_filing_types": ["10-K"],
            "source_basis": "reviewed fiscal 2025 10-K comparative consolidated cash-flow tables and deterministic FCF proxy cells",
        },
    )
    _write_case_artifacts(
        SUBSCRIPTION_CASE,
        subscription_facts,
        _case_context_rows(SUBSCRIPTION_CASE, subscription_facts, evidence_by_id),
        reviewed_context_dir,
        reviewed_facts_dir,
        review_scope={
            "companies": ["ADBE", "SNOW", "PANW"],
            "years": [2023, 2024, 2025],
            "source_policy": "SEC_ONLY",
            "allowed_filing_types": ["10-K"],
            "source_basis": (
                "reviewed fiscal 2025 comparative 10-K tables for Adobe subscription revenue, "
                "Snowflake product revenue, and Palo Alto Networks subscription/support revenue plus SEC caveat context"
            ),
        },
    )
    _write_case_artifacts(
        ADS_CASE,
        ads_facts,
        _case_context_rows(ADS_CASE, ads_facts, evidence_by_id),
        reviewed_context_dir,
        reviewed_facts_dir,
        review_scope={
            "companies": ["GOOGL", "META"],
            "years": [2023, 2024, 2025],
            "source_policy": "SEC_ONLY",
            "allowed_filing_types": ["10-K"],
            "source_basis": (
                "reviewed fiscal 2025 10-K comparative tables for advertising revenue, total income from operations, "
                "and purchases of property and equipment plus SEC text caveats for AI infrastructure, cost pressure, and attribution limits"
            ),
        },
    )
    approval_path = report_dir / "sec_benchmark_v1_1_reviewed_gold_partial_approval.json"
    approval_path.write_text(json.dumps(_approval_payload(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "reviewed_case_count": 4,
                "context_paths": [
                    str(reviewed_context_dir / f"{SEMI_CASE}.jsonl"),
                    str(reviewed_context_dir / f"{CAPEX_CASE}.jsonl"),
                    str(reviewed_context_dir / f"{SUBSCRIPTION_CASE}.jsonl"),
                    str(reviewed_context_dir / f"{ADS_CASE}.jsonl"),
                ],
                "fact_paths": [
                    str(reviewed_facts_dir / f"{SEMI_CASE}.json"),
                    str(reviewed_facts_dir / f"{CAPEX_CASE}.json"),
                    str(reviewed_facts_dir / f"{SUBSCRIPTION_CASE}.json"),
                    str(reviewed_facts_dir / f"{ADS_CASE}.json"),
                ],
                "approval_path": str(approval_path),
                "semi_fact_count": len(semi_facts),
                "capex_fact_count": len(capex_facts),
                "subscription_fact_count": len(subscription_facts),
                "ads_fact_count": len(ads_facts),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def _semi_facts() -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for index, (ticker, year, family, name, raw, value, source_key, row_label, column_label) in enumerate(SEMI_FACTS, 1):
        source = TABLE_SOURCES[SEMI_CASE][source_key]
        facts.append(
            _fact(
                case_id=SEMI_CASE,
                index=index,
                ticker=ticker,
                year=year,
                metric_name=name,
                metric_family=family,
                metric_role="total_value",
                raw_value=raw,
                value=value,
                unit="usd_millions",
                source=source,
                row_label=row_label,
                column_label=column_label,
                review_note=(
                    f"Reviewed {ticker} fiscal {year} {'Compute & Networking proxy' if ticker == 'NVDA' else 'Data Center'} revenue cell. "
                    "For NVIDIA, this is a reportable-segment proxy and must be caveated against AMD's Data Center segment definition."
                ),
            )
        )
    return facts


def _capex_facts() -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    index = 1
    for ticker in ["MSFT", "GOOGL", "META", "AMZN"]:
        source = TABLE_SOURCES[CAPEX_CASE][CAPEX_SOURCE_KEY[ticker]]
        for year in [2023, 2024, 2025]:
            values = CAPEX_INPUTS[ticker][year]
            for family in ["cash_flow", "ppe_purchases"]:
                metric_name, metric_family, metric_role = METRIC_LABELS[family]
                value = float(values[family])
                raw = _raw_currency(value)
                row_label = "Additions to property and equipment" if ticker == "MSFT" and family == "ppe_purchases" else metric_name
                facts.append(
                    _fact(
                        case_id=CAPEX_CASE,
                        index=index,
                        ticker=ticker,
                        year=year,
                        metric_name=metric_name,
                        metric_family=metric_family,
                        metric_role=metric_role,
                        raw_value=raw,
                        value=value,
                        unit="usd_millions",
                        source=source,
                        row_label=row_label,
                        column_label=str(year),
                        review_note=(
                            f"Reviewed {ticker} fiscal {year} cash-flow table input for FCF proxy. "
                            "Do not substitute total investing cash flow or non-cash accrued capex rows."
                        ),
                    )
                )
                index += 1
            fcf_value = float(values["cash_flow"] + values["ppe_purchases"])
            facts.append(
                _fact(
                    case_id=CAPEX_CASE,
                    index=index,
                    ticker=ticker,
                    year=year,
                    metric_name="free cash flow proxy",
                    metric_family="free_cash_flow_proxy",
                    metric_role="derived_value",
                    raw_value=_raw_currency(fcf_value),
                    value=fcf_value,
                    unit="usd_millions",
                    source=source,
                    row_label="net cash provided by operating activities plus purchases/additions of property and equipment",
                    column_label=str(year),
                    review_note=(
                        f"Reviewed derived FCF proxy for {ticker} fiscal {year}: "
                        f"{values['cash_flow']} + ({values['ppe_purchases']}) = {int(fcf_value)} USD millions. "
                        "This is a deterministic proxy, not a company-reported non-GAAP FCF label unless separately disclosed."
                    ),
                )
            )
            facts[-1]["derived_from_metric_families"] = ["cash_flow", "ppe_purchases"]
            index += 1
    return facts


def _subscription_facts() -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for index, (
        ticker,
        year,
        family,
        name,
        raw,
        value,
        source_key,
        row_label,
        column_label,
        unit,
    ) in enumerate(SUBSCRIPTION_FACTS, 1):
        source = TABLE_SOURCES[SUBSCRIPTION_CASE][source_key]
        review_note = (
            f"Reviewed {ticker} fiscal {year} {name} cell for subscription/consumption visibility comparison. "
            "ARR, RPO, billings, deferred revenue, and revenue are kept as separate metrics; this ledger row is the single numeric target for the company-year coverage gate."
        )
        if ticker == "SNOW":
            review_note += " Snowflake product revenue is in USD thousands and must not be described as standard ratable subscription revenue."
        facts.append(
            _fact(
                case_id=SUBSCRIPTION_CASE,
                index=index,
                ticker=ticker,
                year=year,
                metric_name=name,
                metric_family=family,
                metric_role="total_value",
                raw_value=raw,
                value=value,
                unit=unit,
                source=source,
                row_label=row_label,
                column_label=column_label,
                review_note=review_note,
            )
        )
    return facts


def _ads_facts() -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for index, (
        ticker,
        year,
        family,
        name,
        raw,
        value,
        source_key,
        row_label,
        column_label,
    ) in enumerate(ADS_FACTS, 1):
        source = TABLE_SOURCES[ADS_CASE][source_key]
        review_note = (
            f"Reviewed {ticker} fiscal {year} {name} cell for ads, AI infrastructure, and operating leverage comparison. "
            "This fact is a target numeric cell only; do not infer that all infrastructure capex was advertising-specific or that AI directly caused ad growth unless the SEC text supports that causal link."
        )
        facts.append(
            _fact(
                case_id=ADS_CASE,
                index=index,
                ticker=ticker,
                year=year,
                metric_name=name,
                metric_family=family,
                metric_role="total_value",
                raw_value=raw,
                value=value,
                unit="usd_millions",
                source=source,
                row_label=row_label,
                column_label=column_label,
                review_note=review_note,
            )
        )
    return facts


def _fact(
    *,
    case_id: str,
    index: int,
    ticker: str,
    year: int,
    metric_name: str,
    metric_family: str,
    metric_role: str,
    raw_value: str,
    value: float,
    unit: str,
    source: dict[str, Any],
    row_label: str,
    column_label: str,
    review_note: str,
) -> dict[str, Any]:
    metric_id = f"{ticker}_{year}_{metric_family}_{metric_role}"
    return {
        "fact_id": f"{case_id}_FACT_REVIEWED_{index:04d}",
        "review_status": "reviewed_keep",
        "metric_id": metric_id,
        "ticker": ticker,
        "fiscal_year": year,
        "period": str(year),
        "metric_name": metric_name,
        "metric_family": metric_family,
        "metric_role": metric_role,
        "raw_value": raw_value,
        "value": value,
        "unit": unit,
        "display_value_en": _display_value_en(value, unit),
        "display_value_zh": _display_value_zh(value, unit),
        "object_id": source["object_id"],
        "source_evidence_id": source["source_evidence_id"],
        "section": source["section"],
        "row_label": row_label,
        "column_label": column_label,
        "allowed_claim_roles": [f"{metric_family}_{metric_role}"],
        "disallowed_claim_roles": _disallowed_roles(metric_family),
        "review_note": review_note,
    }


def _case_context_rows(
    case_id: str,
    facts: list[dict[str, Any]],
    evidence_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key, source in TABLE_SOURCES[case_id].items():
        evidence = evidence_by_id.get(source["source_evidence_id"], {})
        rows.append(
            {
                "schema_version": "sec_gold_context_reviewed_v0.1",
                "case_id": case_id,
                "review_status": "reviewed_keep",
                "gold_role": "core_table_source",
                "source_kind": "table_object",
                "source_key": key,
                "object_id": source["object_id"],
                "source_evidence_id": source["source_evidence_id"],
                "ticker": source["ticker"],
                "fiscal_year": evidence.get("fiscal_year"),
                "source_type": evidence.get("source_type") or "10-K",
                "section": source["section"],
                "source_url": evidence.get("source_url"),
                "local_path": evidence.get("local_path"),
                "text": source["text"],
                "review_note": "Reviewed compact table source for target numeric cells.",
            }
        )
    for fact in facts:
        source_kind = "reviewed_derived_cell" if fact["metric_role"] == "derived_value" else "reviewed_table_cell"
        rows.append(
            {
                "schema_version": "sec_gold_context_reviewed_v0.1",
                "case_id": case_id,
                "review_status": "reviewed_keep",
                "gold_role": "core_structured_fact",
                "source_kind": source_kind,
                **{key: fact[key] for key in [
                    "object_id",
                    "source_evidence_id",
                    "ticker",
                    "fiscal_year",
                    "section",
                    "metric_name",
                    "metric_family",
                    "metric_role",
                    "raw_value",
                    "value",
                    "unit",
                    "period",
                    "row_label",
                    "column_label",
                    "review_note",
                ]},
                "text": (
                    f"{fact['ticker']} fiscal {fact['period']} {fact['metric_name']}: "
                    f"{fact['raw_value']} USD millions; metric_id={fact['metric_id']}."
                ),
            }
        )
    for row in TEXT_CONTEXT_ROWS.get(case_id, []):
        evidence = evidence_by_id.get(row["source_evidence_id"], {})
        rows.append(
            {
                "schema_version": "sec_gold_context_reviewed_v0.1",
                "case_id": case_id,
                "review_status": "reviewed_keep",
                "gold_role": row["gold_role"],
                "source_kind": "reviewed_text_excerpt",
                "source_evidence_id": row["source_evidence_id"],
                "ticker": row["ticker"],
                "fiscal_year": row["fiscal_year"],
                "source_type": evidence.get("source_type") or "10-K",
                "section": row["section"],
                "source_url": evidence.get("source_url"),
                "local_path": evidence.get("local_path"),
                "text": row["text"],
                "review_note": "Reviewed text/caveat context for this expansion case.",
            }
        )
    return rows


def _write_case_artifacts(
    case_id: str,
    facts: list[dict[str, Any]],
    context_rows: list[dict[str, Any]],
    reviewed_context_dir: Path,
    reviewed_facts_dir: Path,
    *,
    review_scope: dict[str, Any],
) -> None:
    facts_payload = {
        "schema_version": "sec_gold_facts_reviewed_v0.1",
        "case_id": case_id,
        "benchmark_version": "sec_benchmark_v1_1",
        "review_status": "reviewed_approved_single_case",
        "review_scope": review_scope,
        "facts": facts,
    }
    _write_jsonl(reviewed_context_dir / f"{case_id}.jsonl", context_rows)
    (reviewed_facts_dir / f"{case_id}.json").write_text(
        json.dumps(facts_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _approval_payload() -> dict[str, Any]:
    return {
        "schema_version": "sec_gold_manual_review_v0.2",
        "review_scope": {
            "gold_context_dir": "eval/sec_cases/reviewed_gold_context",
            "gold_facts_dir": "eval/sec_cases/reviewed_gold_facts",
            "case_count": 4,
            "reviewed_case_ids": [SEMI_CASE, CAPEX_CASE, SUBSCRIPTION_CASE, ADS_CASE],
        },
        "review_decision": {
            "overall_status": "partial_approved_for_mainline_scored_benchmark",
            "allowed_next_step": "case_filtered_gold_context_scored_smoke",
            "blocked_next_step": "full_benchmark_mainline_scored_test",
            "reason": (
                "Four v1.1 expansion cases are approved for case-filtered gold-context smoke after replacing noisy seed candidates with compact reviewed facts and caveat context. They do not alter the reviewed10 v1 baseline."
            ),
        },
        "case_reviews": [
            {
                "case_id": SEMI_CASE,
                "decision": "approved_for_gold_context_mode",
                "mainline_status": "can_enter_case_filtered_scored_gold_context_smoke",
                "evidence_assessment": (
                    "Reviewed context keeps NVIDIA Compute & Networking proxy revenue, AMD Data Center revenue, and SEC-only context for AI demand, Hopper/Blackwell transition, customer concentration, export controls, supply constraints, and segment-definition caveats."
                ),
                "fact_assessment": (
                    "Reviewed facts contain six target total-value facts: NVIDIA Compute & Networking proxy revenue for fiscal 2023-2025 and AMD Data Center net revenue for fiscal 2023-2025, all in USD millions. NVIDIA facts must be caveated as reportable-segment proxy evidence rather than directly identical to AMD Data Center segment scope."
                ),
                "required_fix": (
                    "Before pipeline promotion, add or confirm abstract rubric coverage for segment comparability, risk-factor calibration, and no market-share inference."
                ),
            },
            {
                "case_id": CAPEX_CASE,
                "decision": "approved_for_gold_context_mode",
                "mainline_status": "can_enter_case_filtered_scored_gold_context_smoke",
                "evidence_assessment": (
                    "Reviewed context keeps fiscal 2025 comparative consolidated cash-flow tables for Microsoft, Alphabet, Meta, and Amazon. It excludes total investing cash flow and non-cash/accrued capex rows as target inputs."
                ),
                "fact_assessment": (
                    "Reviewed facts contain 24 reported input facts for operating cash flow and property/equipment purchases plus 12 deterministic FCF proxy cells. The proxy is calculated as OCF plus the negative capex/PPE cash outflow."
                ),
                "required_fix": (
                    "Before pipeline promotion, run scripts/validate_sec_benchmark_derived_metrics.py to confirm each FCF proxy cell equals OCF plus the cited capex/PPE cash outflow."
                ),
            },
            {
                "case_id": SUBSCRIPTION_CASE,
                "decision": "approved_for_gold_context_mode",
                "mainline_status": "can_enter_case_filtered_scored_gold_context_smoke",
                "evidence_assessment": (
                    "Reviewed context keeps compact SEC-only evidence for Adobe subscription revenue and ARR definition, Snowflake product revenue plus consumption/RPO caveats, and Palo Alto Networks subscription/support revenue plus RPO/deferred-revenue caveats."
                ),
                "fact_assessment": (
                    "Reviewed facts contain nine target total-value facts: Adobe subscription revenue for fiscal 2023-2025, Snowflake product revenue for fiscal 2023-2025 in USD thousands, and Palo Alto Networks subscription and support revenue for fiscal 2023-2025. ARR, RPO, billings, deferred revenue, and revenue are intentionally not collapsed into one metric family."
                ),
                "required_fix": (
                    "Before pipeline promotion, confirm pipeline retrieval keeps BGE-M3 as the final selector and that synthesis preserves Snowflake's consumption-based caveat instead of calling it standard ratable subscription revenue."
                ),
            },
            {
                "case_id": ADS_CASE,
                "decision": "approved_for_gold_context_mode",
                "mainline_status": "can_enter_case_filtered_scored_gold_context_smoke",
                "evidence_assessment": (
                    "Reviewed context keeps Alphabet and Meta advertising revenue, total operating income, and purchases of property/equipment tables plus SEC text that separately covers AI/technical infrastructure investment, cost pressure, operating leverage, and attribution caveats."
                ),
                "fact_assessment": (
                    "Reviewed facts contain 18 target total-value facts: advertising revenue, total income from operations, and capex/PPE purchases for Alphabet and Meta across fiscal 2023-2025, all in USD millions. Capex is retained as company-wide technical infrastructure evidence, not as an ads-only metric."
                ),
                "required_fix": (
                    "Before broader v2 promotion, add required-caveat and disallowed-claim gates so outputs cannot claim AI directly drove ad growth or that all technical infrastructure capex belongs to advertising products."
                ),
            },
        ],
        "gate": {
            "can_enter_full_mainline_scored_test": False,
            "can_enter_case_filtered_gold_context_scored_smoke": True,
            "approved_case_ids": [SEMI_CASE, CAPEX_CASE, SUBSCRIPTION_CASE, ADS_CASE],
        },
    }


def _load_evidence_index() -> dict[str, dict[str, Any]]:
    path = REPO_ROOT / "data" / "processed_private" / "evidence_objects" / "sec_tech_10k_evidence.jsonl"
    rows = {}
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        rows[str(row.get("evidence_id") or "")] = row
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def _raw_currency(value: float) -> str:
    rounded = int(value)
    return f"( {abs(rounded):,} )" if rounded < 0 else f"{rounded:,}"


def _display_value_en(value: float, unit: str) -> str:
    if unit == "usd_millions":
        return f"${value / 1000:.3f} billion"
    if unit == "usd_billions":
        return f"${value:.3f} billion"
    if unit == "usd_thousands":
        return f"${value / 1_000_000:.3f} billion"
    if unit == "percent":
        return f"{value:.1f}%"
    return str(value)


def _display_value_zh(value: float, unit: str) -> str:
    if unit == "usd_millions":
        return f"{value / 100:.2f} 亿美元"
    if unit == "usd_billions":
        return f"{value * 10:.2f} 亿美元"
    if unit == "usd_thousands":
        return f"{value / 100000:.2f} 亿美元"
    if unit == "percent":
        return f"{value:.1f}%"
    return str(value)


def _disallowed_roles(metric_family: str) -> list[str]:
    common = [
        "total_revenue",
        "operating_income",
        "net_income",
        "cash_flow",
        "ppe_purchases",
        "capex",
        "free_cash_flow",
        "segment_revenue",
        "market_share",
    ]
    return [item for item in common if item != metric_family]


if __name__ == "__main__":
    main()
