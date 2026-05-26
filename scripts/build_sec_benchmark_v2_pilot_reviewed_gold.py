from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


META_CASE = "META_REALITY_LABS_2024_001"
PANW_CASE = "PANW_RPO_BILLINGS_NUMERIC_2023_2025_001"
GOOGL_META_ADS_CASE = "GOOGL_META_ADS_REGULATION_PRIVACY_2023_2025_001"
AAPL_CASE = "AAPL_PRODUCT_SERVICES_REVENUE_GM_2023_2025_001"
AMD_CASE = "AMD_SEGMENT_MIX_2023_2025_001"
TRAP_CASE = "MSFT_YOUTUBE_REVENUE_TRAP_001"

REVIEWED_CASE_IDS = [META_CASE, PANW_CASE, GOOGL_META_ADS_CASE, AAPL_CASE, AMD_CASE]


SOURCE_BY_KEY: dict[str, dict[str, Any]] = {
    "META_2024_segment_results": {
        "case_id": META_CASE,
        "ticker": "META",
        "fiscal_year": 2024,
        "source_evidence_id": "META_2024_10K_ITEM7_BLOCK_0004_CHUNK_0001",
        "object_id": "META_2024_10K_ITEM7_BLOCK_0004_CHUNK_0001_TABLE_D0EB8370",
        "source_kind": "table_object",
        "section": "Item 7. Management's Discussion and Analysis",
        "text": (
            "Meta fiscal 2024 10-K Consolidated and Segment Results table, USD millions. "
            "Family of Apps revenue: 162,355; Family of Apps income from operations: 87,109; "
            "Reality Labs revenue: 2,146; Reality Labs loss from operations: (17,729)."
        ),
    },
    "PANW_2025_subscription_support_revenue": {
        "case_id": PANW_CASE,
        "ticker": "PANW",
        "fiscal_year": 2025,
        "source_evidence_id": "PANW_2025_10K_ITEM8_BLOCK_0001_PART_03_OF_21",
        "object_id": "PANW_2025_10K_ITEM8_BLOCK_0001_PART_03_OF_21_TABLE_7BB65710",
        "source_kind": "table_object",
        "section": "Item 8. Financial Statements and Supplementary Data",
        "text": (
            "Palo Alto Networks fiscal 2025 consolidated statements of operations table, USD millions. "
            "Subscription and support revenue: 2025: 7,419.6; 2024: 6,424.2; 2023: 5,314.3."
        ),
    },
    "PANW_2023_billings": {
        "case_id": PANW_CASE,
        "ticker": "PANW",
        "fiscal_year": 2023,
        "source_evidence_id": "PANW_2023_10K_ITEM7_BLOCK_0006_PART_02_OF_03",
        "object_id": "PANW_2023_10K_ITEM7_BLOCK_0006_PART_02_OF_03_METRIC_TABLE_8D8B2A5D",
        "source_kind": "metric_object",
        "section": "Item 7. Management's Discussion and Analysis",
        "text": "Palo Alto Networks fiscal 2023 key financial metrics table reports billings of $9,194.4 million.",
    },
    "PANW_2024_billings": {
        "case_id": PANW_CASE,
        "ticker": "PANW",
        "fiscal_year": 2024,
        "source_evidence_id": "PANW_2024_10K_ITEM7_BLOCK_0006_PART_02_OF_03",
        "object_id": "PANW_2024_10K_ITEM7_BLOCK_0006_PART_02_OF_03_METRIC_TABLE_7BED558B",
        "source_kind": "metric_object",
        "section": "Item 7. Management's Discussion and Analysis",
        "text": "Palo Alto Networks fiscal 2024 key financial metrics table reports billings of $10,208.1 million.",
    },
    "PANW_2025_rpo": {
        "case_id": PANW_CASE,
        "ticker": "PANW",
        "fiscal_year": 2025,
        "source_evidence_id": "PANW_2025_10K_ITEM7_BLOCK_0004_PART_01_OF_02",
        "object_id": "PANW_2025_10K_ITEM7_BLOCK_0004_PART_01_OF_02_METRIC_TABLE_F8DBAB81",
        "source_kind": "metric_object",
        "section": "Item 7. Management's Discussion and Analysis",
        "text": "Palo Alto Networks fiscal 2025 key financial metrics table reports remaining performance obligations of $15.8 billion.",
    },
    "GOOGL_2025_advertising_revenue": {
        "case_id": GOOGL_META_ADS_CASE,
        "ticker": "GOOGL",
        "fiscal_year": 2025,
        "source_evidence_id": "GOOGL_2025_10K_ITEM8_BLOCK_0003_CHUNK_0001",
        "object_id": "GOOGL_2025_10K_ITEM8_BLOCK_0003_CHUNK_0001_TABLE_528579E1",
        "source_kind": "table_object",
        "section": "Item 8. Financial Statements and Supplementary Data",
        "text": (
            "Alphabet fiscal 2025 revenue disaggregation table, USD millions. "
            "Google advertising revenue: 2023: 237,855; 2024: 264,590; 2025: 294,691."
        ),
    },
    "META_2025_advertising_revenue": {
        "case_id": GOOGL_META_ADS_CASE,
        "ticker": "META",
        "fiscal_year": 2025,
        "source_evidence_id": "META_2025_10K_ITEM8_BLOCK_0003_CHUNK_0001",
        "object_id": "META_2025_10K_ITEM8_BLOCK_0003_CHUNK_0001_TABLE_4153538C",
        "source_kind": "table_object",
        "section": "Item 8. Financial Statements and Supplementary Data",
        "text": (
            "Meta fiscal 2025 revenue disaggregation table, USD millions. "
            "Advertising revenue: 2025: 196,175; 2024: 160,633; 2023: 131,948."
        ),
    },
    "AAPL_2025_products_services_net_sales": {
        "case_id": AAPL_CASE,
        "ticker": "AAPL",
        "fiscal_year": 2025,
        "source_evidence_id": "AAPL_2025_10K_ITEM8_BLOCK_0001_PART_01_OF_03",
        "object_id": "AAPL_2025_10K_ITEM8_BLOCK_0001_PART_01_OF_03_TABLE_35E6E401",
        "source_kind": "table_object",
        "section": "Item 8. Financial Statements and Supplementary Data",
        "text": (
            "Apple fiscal 2025 consolidated statement table, USD millions. "
            "Products net sales: 2025: 307,003; 2024: 294,866; 2023: 298,085. "
            "Services net sales: 2025: 109,158; 2024: 96,169; 2023: 85,200."
        ),
    },
    "AAPL_2025_gross_margin_percentage": {
        "case_id": AAPL_CASE,
        "ticker": "AAPL",
        "fiscal_year": 2025,
        "source_evidence_id": "AAPL_2025_10K_ITEM7_BLOCK_0003_CHUNK_0001",
        "object_id": "AAPL_2025_10K_ITEM7_BLOCK_0003_CHUNK_0001_TABLE_85B38FD4",
        "source_kind": "table_object",
        "section": "Item 7. Management's Discussion and Analysis",
        "text": (
            "Apple fiscal 2025 Products and Services gross margin percentage table. "
            "Products gross margin percentage: 2025: 36.8%; 2024: 37.2%; 2023: 36.5%. "
            "Services gross margin percentage: 2025: 75.4%; 2024: 73.9%; 2023: 70.8%."
        ),
    },
    "AMD_2025_segment_revenue": {
        "case_id": AMD_CASE,
        "ticker": "AMD",
        "fiscal_year": 2025,
        "source_evidence_id": "AMD_2025_10K_ITEM8_BLOCK_0005_PART_01_OF_02",
        "object_id": "AMD_2025_10K_ITEM8_BLOCK_0005_PART_01_OF_02_TABLE_78EF91B2",
        "source_kind": "table_object",
        "section": "Item 8. Financial Statements and Supplementary Data",
        "text": (
            "AMD fiscal 2025 segment table, USD millions. "
            "Data Center net revenue: 2025: 16,635; 2024: 12,579; 2023: 6,496. "
            "Client revenue: 2025: 10,640; 2024: 7,054; 2023: 4,651. "
            "Gaming revenue: 2025: 3,910; 2024: 2,595; 2023: 6,212. "
            "Embedded revenue: 2025: 3,454; 2024: 3,557; 2023: 5,321."
        ),
    },
}


FACT_SPECS: dict[str, list[dict[str, Any]]] = {
    META_CASE: [
        {
            "ticker": "META",
            "fiscal_year": 2024,
            "period": "2024",
            "metric_name": "Family of Apps revenue",
            "metric_family": "segment_revenue",
            "metric_role": "total_value",
            "raw_value": "162,355",
            "value": 162355.0,
            "unit": "usd_millions",
            "source_key": "META_2024_segment_results",
            "row_label": "Family of Apps",
            "column_label": "2024",
        },
        {
            "ticker": "META",
            "fiscal_year": 2024,
            "period": "2024",
            "metric_name": "Reality Labs revenue",
            "metric_family": "segment_revenue",
            "metric_role": "total_value",
            "raw_value": "2,146",
            "value": 2146.0,
            "unit": "usd_millions",
            "source_key": "META_2024_segment_results",
            "row_label": "Reality Labs",
            "column_label": "2024",
        },
        {
            "ticker": "META",
            "fiscal_year": 2024,
            "period": "2024",
            "metric_name": "Family of Apps income from operations",
            "metric_family": "operating_income",
            "metric_role": "total_value",
            "raw_value": "$ 87,109",
            "value": 87109.0,
            "unit": "usd_millions",
            "source_key": "META_2024_segment_results",
            "row_label": "Family of Apps",
            "column_label": "2024",
        },
        {
            "ticker": "META",
            "fiscal_year": 2024,
            "period": "2024",
            "metric_name": "Reality Labs income (loss) from operations",
            "metric_family": "operating_income",
            "metric_role": "total_value",
            "raw_value": "(17,729)",
            "value": -17729.0,
            "unit": "usd_millions",
            "source_key": "META_2024_segment_results",
            "row_label": "Reality Labs",
            "column_label": "2024",
        },
    ],
    PANW_CASE: [
        *[
            {
                "ticker": "PANW",
                "fiscal_year": year,
                "period": str(year),
                "metric_name": "Subscription and support revenue",
                "metric_family": "subscription_revenue",
                "metric_role": "total_value",
                "raw_value": raw,
                "value": value,
                "unit": "usd_millions",
                "source_key": "PANW_2025_subscription_support_revenue",
                "row_label": "Subscription and support",
                "column_label": str(year),
            }
            for year, raw, value in [
                (2023, "5,314.3", 5314.3),
                (2024, "6,424.2", 6424.2),
                (2025, "7,419.6", 7419.6),
            ]
        ],
        {
            "ticker": "PANW",
            "fiscal_year": 2023,
            "period": "2023",
            "metric_name": "Billings",
            "metric_family": "billings",
            "metric_role": "total_value",
            "raw_value": "$ 9,194.4",
            "value": 9194.4,
            "unit": "usd_millions",
            "source_key": "PANW_2023_billings",
            "row_label": "Billings",
            "column_label": "2023",
        },
        {
            "ticker": "PANW",
            "fiscal_year": 2024,
            "period": "2024",
            "metric_name": "Billings",
            "metric_family": "billings",
            "metric_role": "total_value",
            "raw_value": "$ 10,208.1",
            "value": 10208.1,
            "unit": "usd_millions",
            "source_key": "PANW_2024_billings",
            "row_label": "Billings",
            "column_label": "2024",
        },
        {
            "ticker": "PANW",
            "fiscal_year": 2025,
            "period": "2025",
            "metric_name": "Remaining performance obligations",
            "metric_family": "rpo",
            "metric_role": "total_value",
            "raw_value": "$ 15.8",
            "value": 15.8,
            "unit": "usd_billions",
            "source_key": "PANW_2025_rpo",
            "row_label": "Remaining performance obligations",
            "column_label": "2025",
        },
    ],
    GOOGL_META_ADS_CASE: [
        *[
            {
                "ticker": "GOOGL",
                "fiscal_year": year,
                "period": str(year),
                "metric_name": "Google advertising revenue",
                "metric_family": "advertising_revenue",
                "metric_role": "total_value",
                "raw_value": raw,
                "value": value,
                "unit": "usd_millions",
                "source_key": "GOOGL_2025_advertising_revenue",
                "row_label": "Google advertising",
                "column_label": str(year),
            }
            for year, raw, value in [
                (2023, "237,855", 237855.0),
                (2024, "264,590", 264590.0),
                (2025, "294,691", 294691.0),
            ]
        ],
        *[
            {
                "ticker": "META",
                "fiscal_year": year,
                "period": str(year),
                "metric_name": "Advertising revenue",
                "metric_family": "advertising_revenue",
                "metric_role": "total_value",
                "raw_value": raw,
                "value": value,
                "unit": "usd_millions",
                "source_key": "META_2025_advertising_revenue",
                "row_label": "Advertising",
                "column_label": str(year),
            }
            for year, raw, value in [
                (2023, "$ 131,948", 131948.0),
                (2024, "$ 160,633", 160633.0),
                (2025, "$ 196,175", 196175.0),
            ]
        ],
    ],
    AAPL_CASE: [
        *[
            {
                "ticker": "AAPL",
                "fiscal_year": year,
                "period": str(year),
                "metric_name": "Products net sales",
                "metric_family": "product_revenue",
                "metric_role": "total_value",
                "raw_value": raw,
                "value": value,
                "unit": "usd_millions",
                "source_key": "AAPL_2025_products_services_net_sales",
                "row_label": "Products",
                "column_label": str(year),
            }
            for year, raw, value in [
                (2023, "298,085", 298085.0),
                (2024, "294,866", 294866.0),
                (2025, "307,003", 307003.0),
            ]
        ],
        *[
            {
                "ticker": "AAPL",
                "fiscal_year": year,
                "period": str(year),
                "metric_name": "Services net sales",
                "metric_family": "services_revenue",
                "metric_role": "total_value",
                "raw_value": raw,
                "value": value,
                "unit": "usd_millions",
                "source_key": "AAPL_2025_products_services_net_sales",
                "row_label": "Services",
                "column_label": str(year),
            }
            for year, raw, value in [
                (2023, "85,200", 85200.0),
                (2024, "96,169", 96169.0),
                (2025, "109,158", 109158.0),
            ]
        ],
        *[
            {
                "ticker": "AAPL",
                "fiscal_year": year,
                "period": str(year),
                "metric_name": "Gross margin percentage",
                "metric_family": "gross_margin",
                "metric_role": "percentage_rate",
                "raw_value": raw,
                "value": value,
                "unit": "percent",
                "source_key": "AAPL_2025_gross_margin_percentage",
                "row_label": "Products",
                "column_label": str(year),
            }
            for year, raw, value in [
                (2023, "36.5 %", 36.5),
                (2024, "37.2 %", 37.2),
                (2025, "36.8 %", 36.8),
            ]
        ],
        *[
            {
                "ticker": "AAPL",
                "fiscal_year": year,
                "period": str(year),
                "metric_name": "Gross margin percentage",
                "metric_family": "gross_margin",
                "metric_role": "percentage_rate",
                "raw_value": raw,
                "value": value,
                "unit": "percent",
                "source_key": "AAPL_2025_gross_margin_percentage",
                "row_label": "Services",
                "column_label": str(year),
            }
            for year, raw, value in [
                (2023, "70.8 %", 70.8),
                (2024, "73.9 %", 73.9),
                (2025, "75.4 %", 75.4),
            ]
        ],
    ],
    AMD_CASE: [
        *[
            {
                "ticker": "AMD",
                "fiscal_year": year,
                "period": str(year),
                "metric_name": "Data Center net revenue",
                "metric_family": "data_center_revenue",
                "metric_role": "total_value",
                "raw_value": raw,
                "value": value,
                "unit": "usd_millions",
                "source_key": "AMD_2025_segment_revenue",
                "row_label": "Data Center",
                "column_label": str(year),
            }
            for year, raw, value in [
                (2023, "6,496", 6496.0),
                (2024, "12,579", 12579.0),
                (2025, "16,635", 16635.0),
            ]
        ],
        *[
            {
                "ticker": "AMD",
                "fiscal_year": year,
                "period": str(year),
                "metric_name": "Client revenue",
                "metric_family": "client_revenue",
                "metric_role": "total_value",
                "raw_value": raw,
                "value": value,
                "unit": "usd_millions",
                "source_key": "AMD_2025_segment_revenue",
                "row_label": "Client",
                "column_label": str(year),
            }
            for year, raw, value in [
                (2023, "4,651", 4651.0),
                (2024, "7,054", 7054.0),
                (2025, "10,640", 10640.0),
            ]
        ],
        *[
            {
                "ticker": "AMD",
                "fiscal_year": year,
                "period": str(year),
                "metric_name": "Gaming revenue",
                "metric_family": "gaming_revenue",
                "metric_role": "total_value",
                "raw_value": raw,
                "value": value,
                "unit": "usd_millions",
                "source_key": "AMD_2025_segment_revenue",
                "row_label": "Gaming",
                "column_label": str(year),
            }
            for year, raw, value in [
                (2023, "6,212", 6212.0),
                (2024, "2,595", 2595.0),
                (2025, "3,910", 3910.0),
            ]
        ],
        *[
            {
                "ticker": "AMD",
                "fiscal_year": year,
                "period": str(year),
                "metric_name": "Embedded revenue",
                "metric_family": "embedded_revenue",
                "metric_role": "total_value",
                "raw_value": raw,
                "value": value,
                "unit": "usd_millions",
                "source_key": "AMD_2025_segment_revenue",
                "row_label": "Embedded",
                "column_label": str(year),
            }
            for year, raw, value in [
                (2023, "5,321", 5321.0),
                (2024, "3,557", 3557.0),
                (2025, "3,454", 3454.0),
            ]
        ],
    ],
}


TEXT_CONTEXT_ROWS: dict[str, list[dict[str, Any]]] = {
    META_CASE: [
        {
            "gold_role": "source_policy_caveat",
            "source_kind": "reviewed_source_policy_note",
            "source_evidence_id": "REVIEW_NOTE_META_AI_TRAINING_COST_NOT_DISCLOSED",
            "ticker": "META",
            "fiscal_year": 2024,
            "section": "review_note",
            "text": (
                "Reviewed SEC-only context supports Meta segment revenue and operating income/loss, "
                "but does not disclose an exact internal AI, generative AI, or Llama training-cost amount."
            ),
        },
    ],
    PANW_CASE: [
        {
            "gold_role": "revenue_definition_caveat",
            "source_evidence_id": "PANW_2025_10K_ITEM7_BLOCK_0006_CHUNK_0001",
            "ticker": "PANW",
            "fiscal_year": 2025,
            "section": "Item 7. Management's Discussion and Analysis",
            "text": (
                "Palo Alto Networks states revenue consists of product revenue and subscription and support revenue; "
                "revenue is recognized when control of promised products or subscription/support transfers to customers."
            ),
        },
        {
            "gold_role": "rpo_deferred_revenue_context",
            "source_evidence_id": "PANW_2025_10K_ITEM8_BLOCK_0001_PART_03_OF_21",
            "ticker": "PANW",
            "fiscal_year": 2025,
            "section": "Item 8. Financial Statements and Supplementary Data",
            "text": (
                "Palo Alto Networks reports subscription/support revenue by year and remaining performance obligations separately; "
                "visibility metrics such as RPO or billings are not the same as recognized revenue."
            ),
        },
    ],
    GOOGL_META_ADS_CASE: [
        {
            "gold_role": "alphabet_privacy_regulation_caveat",
            "source_evidence_id": "GOOGL_2025_10K_ITEM1A_BLOCK_0008_PART_01_OF_03",
            "ticker": "GOOGL",
            "fiscal_year": 2025,
            "section": "Item 1A. Risk Factors",
            "text": (
                "Alphabet describes AI-enabled products as exposing the company to data privacy, cybersecurity, regulatory action, "
                "legal liability, and reputational risks."
            ),
        },
        {
            "gold_role": "alphabet_growth_quality_caveat",
            "source_evidence_id": "GOOGL_2025_10K_ITEM1A_BLOCK_0004_PART_01_OF_03",
            "ticker": "GOOGL",
            "fiscal_year": 2025,
            "section": "Item 1A. Risk Factors",
            "text": (
                "Alphabet states revenue growth could decline due to demand, competition, product and policy changes, "
                "pricing, regulation, and costs that may not correlate with revenue."
            ),
        },
        {
            "gold_role": "meta_privacy_ads_caveat",
            "source_evidence_id": "META_2025_10K_ITEM1A_BLOCK_0003_PART_02_OF_03",
            "ticker": "META",
            "fiscal_year": 2025,
            "section": "Item 1A. Risk Factors",
            "text": (
                "Meta states ad targeting effectiveness can be affected by user consent choices and privacy or digital-market regulations "
                "including GDPR, ePrivacy Directive, DMA, DMCC, and U.S. state privacy laws."
            ),
        },
        {
            "gold_role": "meta_regulation_enforcement_caveat",
            "source_evidence_id": "META_2025_10K_ITEM1A_BLOCK_0022_PART_02_OF_08",
            "ticker": "META",
            "fiscal_year": 2025,
            "section": "Item 1A. Risk Factors",
            "text": (
                "Meta says laws and regulations central to its business include privacy, data use, data protection, advertising, "
                "AI and machine learning, competition, consumer protection, and related matters."
            ),
        },
    ],
    AAPL_CASE: [
        {
            "gold_role": "services_scope_caveat",
            "source_evidence_id": "AAPL_2025_10K_ITEM1_BLOCK_0002_CHUNK_0001",
            "ticker": "AAPL",
            "fiscal_year": 2025,
            "section": "Item 1. Business",
            "text": (
                "Apple describes Services as including cloud services, digital content platforms, subscription-based services, "
                "and payment services; this does not make all Services revenue pure subscription revenue."
            ),
        },
        {
            "gold_role": "revenue_recognition_caveat",
            "source_evidence_id": "AAPL_2025_10K_ITEM8_BLOCK_0003_CHUNK_0001",
            "ticker": "AAPL",
            "fiscal_year": 2025,
            "section": "Item 8. Financial Statements and Supplementary Data",
            "text": (
                "Apple states product net sales generally transfer when products are shipped, while Services net sales transfer over time as services are delivered."
            ),
        },
        {
            "gold_role": "margin_visibility_caveat",
            "source_kind": "reviewed_source_policy_note",
            "source_evidence_id": "REVIEW_NOTE_AAPL_GROSS_MARGIN_NOT_CONTRACT_VISIBILITY",
            "ticker": "AAPL",
            "fiscal_year": 2025,
            "section": "review_note",
            "text": "Reviewed gross margin percentages are profitability cells; they do not by themselves disclose contract visibility, ARR, retention, or renewal quality.",
        },
    ],
    AMD_CASE: [
        {
            "gold_role": "segment_definition_change_caveat",
            "source_evidence_id": "AMD_2025_10K_ITEM1_BLOCK_0002_PART_02_OF_02",
            "ticker": "AMD",
            "fiscal_year": 2025,
            "section": "Item 1. Business",
            "text": (
                "AMD states that beginning in fiscal 2025 it combined the Client and Gaming segments into one reportable segment "
                "and retrospectively adjusted prior-period segment data."
            ),
        },
        {
            "gold_role": "segment_definition_context",
            "source_evidence_id": "AMD_2025_10K_ITEM1_BLOCK_0003_PART_01_OF_04",
            "ticker": "AMD",
            "fiscal_year": 2025,
            "section": "Item 1. Business",
            "text": (
                "AMD defines Data Center, Client and Gaming, and Embedded as distinct reportable segments with different product scopes."
            ),
        },
        {
            "gold_role": "ai_demand_durability_caveat",
            "source_evidence_id": "AMD_2025_10K_ITEM1A_BLOCK_0003_PART_01_OF_02",
            "ticker": "AMD",
            "fiscal_year": 2025,
            "section": "Item 1A. Risk Factors",
            "text": (
                "AMD says the semiconductor industry is cyclical and subject to supply-demand imbalances; AI growth creates pressure "
                "to timely design, manufacture, and deliver products for computing power and AI infrastructure."
            ),
        },
    ],
}


def main() -> None:
    reviewed_context_dir = REPO_ROOT / "eval" / "sec_cases" / "reviewed_gold_context"
    reviewed_facts_dir = REPO_ROOT / "eval" / "sec_cases" / "reviewed_gold_facts"
    report_dir = REPO_ROOT / "reports" / "quality"
    reviewed_context_dir.mkdir(parents=True, exist_ok=True)
    reviewed_facts_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    evidence_by_id = _load_evidence_index()
    build_summary: list[dict[str, Any]] = []
    for case_id in REVIEWED_CASE_IDS:
        facts = _facts_for_case(case_id)
        context_rows = _context_for_case(case_id, facts, evidence_by_id)
        _write_case_artifacts(
            case_id=case_id,
            facts=facts,
            context_rows=context_rows,
            reviewed_context_dir=reviewed_context_dir,
            reviewed_facts_dir=reviewed_facts_dir,
        )
        build_summary.append(
            {
                "case_id": case_id,
                "fact_count": len(facts),
                "context_row_count": len(context_rows),
                "context_path": str(reviewed_context_dir / f"{case_id}.jsonl"),
                "facts_path": str(reviewed_facts_dir / f"{case_id}.json"),
            }
        )

    approval_path = report_dir / "sec_benchmark_v2_pilot_reviewed_gold_partial_approval.json"
    approval_path.write_text(json.dumps(_approval_payload(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    build_report_path = report_dir / "sec_benchmark_v2_pilot_reviewed_gold_build_report.json"
    build_report = {
        "schema_version": "sec_v2_pilot_reviewed_gold_build_report_v0.1",
        "reviewed_case_count": len(REVIEWED_CASE_IDS),
        "trap_case_not_gold_context": TRAP_CASE,
        "approval_path": str(approval_path),
        "cases": build_summary,
    }
    build_report_path.write_text(json.dumps(build_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "reviewed_case_count": len(REVIEWED_CASE_IDS),
                "total_fact_count": sum(item["fact_count"] for item in build_summary),
                "total_context_row_count": sum(item["context_row_count"] for item in build_summary),
                "approval_path": str(approval_path),
                "build_report_path": str(build_report_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def _facts_for_case(case_id: str) -> list[dict[str, Any]]:
    facts = []
    for idx, spec in enumerate(FACT_SPECS[case_id], start=1):
        source = SOURCE_BY_KEY[spec["source_key"]]
        metric_id = f"{spec['ticker']}_{spec['period']}_{spec['metric_family']}_{spec['metric_role']}"
        review_note = _review_note(case_id, spec)
        facts.append(
            {
                "fact_id": f"{case_id}_FACT_REVIEWED_{idx:04d}",
                "review_status": "reviewed_keep",
                "selection_method": "manual_review_structured_object",
                "metric_id": metric_id,
                "ticker": spec["ticker"],
                "fiscal_year": spec["fiscal_year"],
                "period": spec["period"],
                "metric_name": spec["metric_name"],
                "metric_family": spec["metric_family"],
                "metric_role": spec["metric_role"],
                "raw_value": spec["raw_value"],
                "value": spec["value"],
                "unit": spec["unit"],
                "display_value_en": _display_value_en(float(spec["value"]), str(spec["unit"])),
                "object_id": source["object_id"],
                "source_evidence_id": source["source_evidence_id"],
                "section": source["section"],
                "row_label": spec["row_label"],
                "column_label": spec["column_label"],
                "allowed_claim_roles": [f"{spec['metric_family']}_{spec['metric_role']}"],
                "disallowed_claim_roles": _disallowed_roles(str(spec["metric_family"])),
                "review_note": review_note,
            }
        )
    return facts


def _context_for_case(
    case_id: str,
    facts: list[dict[str, Any]],
    evidence_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen_sources: set[str] = set()
    for spec in FACT_SPECS[case_id]:
        source_key = str(spec["source_key"])
        if source_key in seen_sources:
            continue
        seen_sources.add(source_key)
        source = SOURCE_BY_KEY[source_key]
        evidence = evidence_by_id.get(str(source["source_evidence_id"]), {})
        rows.append(
            {
                "schema_version": "sec_gold_context_reviewed_v0.1",
                "case_id": case_id,
                "review_status": "reviewed_keep",
                "gold_role": "core_table_source" if source["source_kind"] == "table_object" else "core_metric_source",
                "source_kind": source["source_kind"],
                "source_key": source_key,
                "object_id": source["object_id"],
                "source_evidence_id": source["source_evidence_id"],
                "ticker": source["ticker"],
                "fiscal_year": source["fiscal_year"],
                "source_type": evidence.get("source_type") or "10-K",
                "section": source["section"],
                "source_url": evidence.get("source_url"),
                "local_path": evidence.get("local_path"),
                "text": source["text"],
                "review_note": "Reviewed compact structured source for v2 pilot target cells.",
            }
        )
    for fact in facts:
        rows.append(
            {
                "schema_version": "sec_gold_context_reviewed_v0.1",
                "case_id": case_id,
                "review_status": "reviewed_keep",
                "gold_role": "core_structured_fact",
                "source_kind": "reviewed_table_cell",
                **{
                    key: fact[key]
                    for key in [
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
                    ]
                },
                "text": (
                    f"{fact['ticker']} fiscal {fact['period']} {fact['metric_name']} "
                    f"({fact['row_label']}): {fact['raw_value']} {fact['unit']}; metric_id={fact['metric_id']}."
                ),
            }
        )
    for row in TEXT_CONTEXT_ROWS.get(case_id, []):
        evidence = evidence_by_id.get(str(row["source_evidence_id"]), {})
        rows.append(
            {
                "schema_version": "sec_gold_context_reviewed_v0.1",
                "case_id": case_id,
                "review_status": "reviewed_keep",
                "gold_role": row["gold_role"],
                "source_kind": row.get("source_kind") or "reviewed_text_excerpt",
                "source_evidence_id": row["source_evidence_id"],
                "ticker": row["ticker"],
                "fiscal_year": row["fiscal_year"],
                "source_type": evidence.get("source_type") or "10-K",
                "section": row["section"],
                "source_url": evidence.get("source_url"),
                "local_path": evidence.get("local_path"),
                "text": row["text"],
                "review_note": "Reviewed caveat/context row for v2 pilot.",
            }
        )
    return rows


def _write_case_artifacts(
    *,
    case_id: str,
    facts: list[dict[str, Any]],
    context_rows: list[dict[str, Any]],
    reviewed_context_dir: Path,
    reviewed_facts_dir: Path,
) -> None:
    review_scope = _review_scope(case_id)
    facts_payload = {
        "schema_version": "sec_gold_facts_reviewed_v0.1",
        "case_id": case_id,
        "benchmark_version": "sec_benchmark_v2_pilot",
        "review_status": "reviewed_approved_single_case",
        "review_scope": review_scope,
        "facts": facts,
    }
    _write_jsonl(reviewed_context_dir / f"{case_id}.jsonl", context_rows)
    (reviewed_facts_dir / f"{case_id}.json").write_text(
        json.dumps(facts_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _review_scope(case_id: str) -> dict[str, Any]:
    specs = FACT_SPECS[case_id]
    return {
        "companies": sorted({str(item["ticker"]) for item in specs}),
        "years": sorted({int(item["fiscal_year"]) for item in specs}),
        "metric_families": sorted({str(item["metric_family"]) for item in specs}),
        "source_policy": "SEC_ONLY",
        "allowed_filing_types": ["10-K"],
        "source_basis": "compact reviewed v2 pilot SEC 10-K table cells plus caveat text rows",
    }


def _approval_payload() -> dict[str, Any]:
    return {
        "schema_version": "sec_gold_manual_review_v0.2",
        "review_scope": {
            "gold_context_dir": "eval/sec_cases/reviewed_gold_context",
            "gold_facts_dir": "eval/sec_cases/reviewed_gold_facts",
            "case_count": len(REVIEWED_CASE_IDS),
            "reviewed_case_ids": REVIEWED_CASE_IDS,
            "pipeline_only_trap_case_ids": [TRAP_CASE],
        },
        "review_decision": {
            "overall_status": "partial_approved_for_mainline_scored_benchmark",
            "allowed_next_step": "case_filtered_gold_context_scored_smoke",
            "blocked_next_step": "full_benchmark_mainline_scored_test",
            "reason": (
                "Five v2 pilot non-trap cases are approved for case-filtered gold-context smoke. "
                "The Microsoft/YouTube wrong-attribution trap remains pipeline-only and is not gold-context approved."
            ),
        },
        "case_reviews": [
            {
                "case_id": META_CASE,
                "decision": "approved_for_gold_context_mode",
                "mainline_status": "can_enter_case_filtered_scored_gold_context_smoke",
                "evidence_assessment": (
                    "Reviewed context keeps Meta fiscal 2024 Family of Apps and Reality Labs segment revenue and operating income/loss, plus an SEC-only not-disclosed caveat for exact AI or Llama training cost."
                ),
                "fact_assessment": "Reviewed facts contain four target cells: FoA revenue, Reality Labs revenue, FoA operating income, and Reality Labs operating loss for fiscal 2024.",
                "required_fix": "Before pipeline promotion, verify the caveat/claim gate blocks invented AI or Llama training-cost amounts.",
            },
            {
                "case_id": PANW_CASE,
                "decision": "approved_for_gold_context_mode",
                "mainline_status": "can_enter_case_filtered_scored_gold_context_smoke",
                "evidence_assessment": (
                    "Reviewed context keeps PANW subscription/support revenue, billings for 2023-2024, RPO for 2025, and definition caveats separating visibility metrics from recognized revenue."
                ),
                "fact_assessment": "Reviewed facts contain three subscription/support revenue cells plus one visibility metric cell per year.",
                "required_fix": "Before pipeline promotion, confirm output keeps billings, RPO, deferred revenue, and recognized revenue as separate definitions.",
            },
            {
                "case_id": GOOGL_META_ADS_CASE,
                "decision": "approved_for_gold_context_mode",
                "mainline_status": "can_enter_case_filtered_scored_gold_context_smoke",
                "evidence_assessment": (
                    "Reviewed context keeps Alphabet and Meta advertising revenue cells and SEC risk text for privacy, regulation, data-use, ad-targeting, and revenue-growth caveats."
                ),
                "fact_assessment": "Reviewed facts contain six advertising revenue target cells: Alphabet and Meta for fiscal 2023-2025.",
                "required_fix": "Before pipeline promotion, run entity-separation and caveat/claim gates; do not infer market share or durable advertising quality from revenue alone.",
            },
            {
                "case_id": AAPL_CASE,
                "decision": "approved_for_gold_context_mode",
                "mainline_status": "can_enter_case_filtered_scored_gold_context_smoke",
                "evidence_assessment": (
                    "Reviewed context keeps Apple Products and Services net sales, Products and Services gross margin percentages, and caveats that Services is broader than pure subscription revenue and gross margin is not contract visibility."
                ),
                "fact_assessment": "Reviewed facts contain twelve target cells: Products net sales, Services net sales, Products gross margin percentage, and Services gross margin percentage for fiscal 2023-2025.",
                "required_fix": "Before pipeline promotion, table-cell validation must preserve percentage-vs-dollar roles.",
            },
            {
                "case_id": AMD_CASE,
                "decision": "approved_for_gold_context_mode",
                "mainline_status": "can_enter_case_filtered_scored_gold_context_smoke",
                "evidence_assessment": (
                    "Reviewed context keeps AMD fiscal 2025 comparative segment revenue cells for Data Center, Client, Gaming, and Embedded, plus segment-definition-change and AI-demand durability caveats."
                ),
                "fact_assessment": "Reviewed facts contain twelve segment revenue target cells across four segment labels and fiscal 2023-2025.",
                "required_fix": "Before pipeline promotion, output must caveat that Client and Gaming were combined as a reportable segment beginning fiscal 2025.",
            },
            {
                "case_id": TRAP_CASE,
                "decision": "approved_for_pipeline_trap_smoke",
                "mainline_status": "can_enter_case_filtered_pipeline_trap_smoke",
                "evidence_assessment": (
                    "This is a wrong-attribution source-policy trap. It intentionally has no reviewed gold context because Microsoft SEC filings should not be used to answer YouTube revenue."
                ),
                "fact_assessment": "No target numeric facts are required or approved for this trap.",
                "required_fix": "Pipeline output must refuse the Microsoft/YouTube attribution and must not invent YouTube revenue from Microsoft filings.",
            },
        ],
        "gate": {
            "can_enter_full_mainline_scored_test": False,
            "can_enter_case_filtered_gold_context_scored_smoke": True,
            "approved_case_ids": REVIEWED_CASE_IDS,
            "pipeline_only_trap_case_ids": [TRAP_CASE],
        },
    }


def _review_note(case_id: str, spec: dict[str, Any]) -> str:
    metric = str(spec["metric_name"])
    ticker = str(spec["ticker"])
    year = str(spec["period"])
    if case_id == GOOGL_META_ADS_CASE:
        return (
            f"Reviewed {ticker} fiscal {year} advertising revenue target cell. "
            "Do not infer market share, stock causality, or durable advertising quality from revenue alone."
        )
    if case_id == AAPL_CASE:
        return (
            f"Reviewed Apple fiscal {year} {metric} cell. "
            "Keep revenue dollars separate from gross margin percentages and do not treat Services as pure subscription revenue."
        )
    if case_id == AMD_CASE:
        return (
            f"Reviewed AMD fiscal {year} {metric} cell. "
            "Segment trend comparison must include the 2025 Client and Gaming reportable-segment change caveat."
        )
    if case_id == PANW_CASE:
        return (
            f"Reviewed PANW fiscal {year} {metric} cell. "
            "Keep billings/RPO/deferred revenue visibility metrics separate from recognized revenue."
        )
    if case_id == META_CASE:
        return (
            f"Reviewed Meta fiscal {year} {metric} segment cell. "
            "Keep Family of Apps and Reality Labs economics separate and do not invent exact AI training cost."
        )
    return f"Reviewed {ticker} fiscal {year} {metric} target cell."


def _load_evidence_index() -> dict[str, dict[str, Any]]:
    path = REPO_ROOT / "data" / "processed_private" / "evidence_objects" / "sec_tech_10k_evidence.jsonl"
    rows: dict[str, dict[str, Any]] = {}
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


def _display_value_en(value: float, unit: str) -> str:
    if unit == "usd_millions":
        return f"${value / 1000:.3f} billion"
    if unit == "usd_billions":
        return f"${value:.3f} billion"
    if unit == "percent":
        return f"{value:.1f}%"
    return str(value)


def _disallowed_roles(metric_family: str) -> list[str]:
    common = [
        "total_revenue",
        "advertising_revenue",
        "segment_revenue",
        "product_revenue",
        "services_revenue",
        "subscription_revenue",
        "billings",
        "rpo",
        "operating_income",
        "gross_margin",
        "data_center_revenue",
        "client_revenue",
        "gaming_revenue",
        "embedded_revenue",
        "market_share",
        "stock_market_causality",
    ]
    return [item for item in common if item != metric_family]


if __name__ == "__main__":
    main()
