from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


REVIEWED_CONTEXT_DIR = REPO_ROOT / "eval" / "sec_cases" / "reviewed_gold_context"
REVIEWED_FACTS_DIR = REPO_ROOT / "eval" / "sec_cases" / "reviewed_gold_facts"
QUALITY_DIR = REPO_ROOT / "reports" / "quality"

NEW20_CASE_IDS = [
    "AVGO_PRODUCT_SUBSCRIPTION_REVENUE_MIX_2023_2025_001",
    "CSCO_PRODUCT_SERVICE_RPO_VISIBILITY_2023_2025_001",
    "INTC_REVENUE_GROSS_PROFIT_FOUNDRY_RISK_2023_2025_001",
    "QCOM_HANDSETS_AUTOMOTIVE_REVENUE_MIX_2023_2025_001",
    "TXN_ANALOG_EMBEDDED_REVENUE_MIX_2023_2025_001",
    "AMAT_SEMICONDUCTOR_SYSTEMS_SERVICES_REVENUE_MIX_2023_2025_001",
    "MU_DRAM_NAND_REVENUE_CYCLE_2023_2025_001",
    "INTU_SMALL_BUSINESS_CONSUMER_CREDIT_KARMA_MIX_2023_2025_001",
    "ADP_EMPLOYER_PEO_REVENUE_CLIENT_FUNDS_2023_2025_001",
    "CRWD_ARR_SUBSCRIPTION_GROSS_PROFIT_2023_2025_001",
]


@dataclass(frozen=True)
class FactSpec:
    case_id: str
    object_id: str
    metric_family: str
    metric_role: str = "total_value"
    unit_override: str | None = None
    row_label_override: str | None = None
    metric_name_override: str | None = None
    review_note: str = ""


FACT_SPECS: list[FactSpec] = [
    FactSpec("AVGO_PRODUCT_SUBSCRIPTION_REVENUE_MIX_2023_2025_001", "AVGO_2023_10K_ITEM8_BLOCK_0001_PART_02_OF_20_METRIC_TABLE_6D5C66CD", "products_revenue", review_note="Reviewed Broadcom Products revenue from consolidated statement of operations."),
    FactSpec("AVGO_PRODUCT_SUBSCRIPTION_REVENUE_MIX_2023_2025_001", "AVGO_2024_10K_ITEM8_BLOCK_0001_PART_03_OF_24_METRIC_TABLE_A3789DB2", "products_revenue", review_note="Reviewed Broadcom Products revenue from consolidated statement of operations."),
    FactSpec("AVGO_PRODUCT_SUBSCRIPTION_REVENUE_MIX_2023_2025_001", "AVGO_2025_10K_ITEM8_BLOCK_0001_PART_02_OF_22_METRIC_TABLE_F0E47B47", "products_revenue", review_note="Reviewed Broadcom Products revenue from consolidated statement of operations."),
    FactSpec("AVGO_PRODUCT_SUBSCRIPTION_REVENUE_MIX_2023_2025_001", "AVGO_2023_10K_ITEM8_BLOCK_0001_PART_02_OF_20_METRIC_TABLE_DC961B00", "subscription_services_revenue", review_note="Reviewed Broadcom Subscriptions and services revenue from consolidated statement of operations."),
    FactSpec("AVGO_PRODUCT_SUBSCRIPTION_REVENUE_MIX_2023_2025_001", "AVGO_2024_10K_ITEM8_BLOCK_0001_PART_03_OF_24_METRIC_TABLE_6B85F905", "subscription_services_revenue", review_note="Reviewed Broadcom Subscriptions and services revenue from consolidated statement of operations."),
    FactSpec("AVGO_PRODUCT_SUBSCRIPTION_REVENUE_MIX_2023_2025_001", "AVGO_2025_10K_ITEM8_BLOCK_0001_PART_02_OF_22_METRIC_TABLE_D94C7C07", "subscription_services_revenue", review_note="Reviewed Broadcom Subscriptions and services revenue from consolidated statement of operations."),

    FactSpec("CSCO_PRODUCT_SERVICE_RPO_VISIBILITY_2023_2025_001", "CSCO_2023_10K_ITEM7_BLOCK_0004_PART_03_OF_04_METRIC_TABLE_36BA37FE", "product_revenue", review_note="Reviewed Cisco product revenue from product/service revenue breakdown."),
    FactSpec("CSCO_PRODUCT_SERVICE_RPO_VISIBILITY_2023_2025_001", "CSCO_2024_10K_ITEM7_BLOCK_0009_CHUNK_0001_METRIC_TABLE_F1A4E786", "product_revenue", review_note="Reviewed Cisco product revenue from product/service revenue breakdown."),
    FactSpec("CSCO_PRODUCT_SERVICE_RPO_VISIBILITY_2023_2025_001", "CSCO_2025_10K_ITEM7_BLOCK_0010_CHUNK_0001_METRIC_TABLE_3CF4C48D", "product_revenue", review_note="Reviewed Cisco product revenue from product/service revenue breakdown."),
    FactSpec("CSCO_PRODUCT_SERVICE_RPO_VISIBILITY_2023_2025_001", "CSCO_2023_10K_ITEM7_BLOCK_0004_PART_03_OF_04_METRIC_TABLE_E4B59D08", "services_revenue", row_label_override="Services", review_note="Reviewed Cisco service revenue; normalized singular source label Service to benchmark label Services."),
    FactSpec("CSCO_PRODUCT_SERVICE_RPO_VISIBILITY_2023_2025_001", "CSCO_2024_10K_ITEM7_BLOCK_0009_CHUNK_0001_METRIC_TABLE_D6D5570A", "services_revenue", review_note="Reviewed Cisco services revenue from product/service revenue breakdown."),
    FactSpec("CSCO_PRODUCT_SERVICE_RPO_VISIBILITY_2023_2025_001", "CSCO_2025_10K_ITEM7_BLOCK_0010_CHUNK_0001_METRIC_TABLE_794A72FD", "services_revenue", review_note="Reviewed Cisco services revenue from product/service revenue breakdown."),
    FactSpec("CSCO_PRODUCT_SERVICE_RPO_VISIBILITY_2023_2025_001", "CSCO_2023_10K_ITEM7_BLOCK_0002_PART_02_OF_02_METRIC_TABLE_61442917", "rpo", review_note="Reviewed Cisco remaining performance obligations from key financial measures table."),
    FactSpec("CSCO_PRODUCT_SERVICE_RPO_VISIBILITY_2023_2025_001", "CSCO_2024_10K_ITEM7_BLOCK_0004_CHUNK_0001_METRIC_TABLE_6DBC702D", "rpo", review_note="Reviewed Cisco remaining performance obligations from key financial measures table."),
    FactSpec("CSCO_PRODUCT_SERVICE_RPO_VISIBILITY_2023_2025_001", "CSCO_2025_10K_ITEM7_BLOCK_0005_CHUNK_0001_METRIC_TABLE_90830004", "rpo", review_note="Reviewed Cisco remaining performance obligations from key financial measures table."),

    FactSpec("INTC_REVENUE_GROSS_PROFIT_FOUNDRY_RISK_2023_2025_001", "INTC_2023_10K_ITEM8_BLOCK_0001_PART_03_OF_10_METRIC_TABLE_41E8F061", "net_revenue", review_note="Reviewed Intel net revenue from consolidated statement; selected current-year value despite source extractor duplicate column labels."),
    FactSpec("INTC_REVENUE_GROSS_PROFIT_FOUNDRY_RISK_2023_2025_001", "INTC_2024_10K_ITEM8_BLOCK_0001_PART_03_OF_09_METRIC_TABLE_6FF79D3D", "net_revenue", review_note="Reviewed Intel net revenue from consolidated statement; selected current-year value despite source extractor duplicate column labels."),
    FactSpec("INTC_REVENUE_GROSS_PROFIT_FOUNDRY_RISK_2023_2025_001", "INTC_2025_10K_ITEM8_BLOCK_0001_PART_03_OF_10_METRIC_TABLE_E30B0287", "net_revenue", review_note="Reviewed Intel net revenue from consolidated statement; selected current-year value despite source extractor duplicate column labels."),
    FactSpec("INTC_REVENUE_GROSS_PROFIT_FOUNDRY_RISK_2023_2025_001", "INTC_2023_10K_ITEM8_BLOCK_0001_PART_03_OF_10_METRIC_TABLE_0B7BADD6", "gross_profit", row_label_override="Gross profit", metric_name_override="Gross profit", review_note="Reviewed Intel gross margin dollars as gross profit equivalent for benchmark metric coverage."),
    FactSpec("INTC_REVENUE_GROSS_PROFIT_FOUNDRY_RISK_2023_2025_001", "INTC_2024_10K_ITEM8_BLOCK_0001_PART_03_OF_09_METRIC_TABLE_0D9E021F", "gross_profit", row_label_override="Gross profit", metric_name_override="Gross profit", review_note="Reviewed Intel gross margin dollars as gross profit equivalent for benchmark metric coverage."),
    FactSpec("INTC_REVENUE_GROSS_PROFIT_FOUNDRY_RISK_2023_2025_001", "INTC_2025_10K_ITEM8_BLOCK_0001_PART_03_OF_10_METRIC_TABLE_6EA17325", "gross_profit", review_note="Reviewed Intel gross profit from consolidated statement."),

    FactSpec("QCOM_HANDSETS_AUTOMOTIVE_REVENUE_MIX_2023_2025_001", "QCOM_2023_10K_ITEM7_BLOCK_0004_CHUNK_0001_METRIC_TABLE_1446D722", "handsets_revenue", review_note="Reviewed Qualcomm QCT Handsets revenue from segment revenue table."),
    FactSpec("QCOM_HANDSETS_AUTOMOTIVE_REVENUE_MIX_2023_2025_001", "QCOM_2024_10K_ITEM7_BLOCK_0003_PART_02_OF_02_METRIC_TABLE_EC1FD6B5", "handsets_revenue", review_note="Reviewed Qualcomm QCT Handsets revenue from segment revenue table."),
    FactSpec("QCOM_HANDSETS_AUTOMOTIVE_REVENUE_MIX_2023_2025_001", "QCOM_2025_10K_ITEM7_BLOCK_0003_PART_02_OF_02_METRIC_TABLE_8B1F7349", "handsets_revenue", review_note="Reviewed Qualcomm QCT Handsets revenue from segment revenue table."),
    FactSpec("QCOM_HANDSETS_AUTOMOTIVE_REVENUE_MIX_2023_2025_001", "QCOM_2023_10K_ITEM7_BLOCK_0004_CHUNK_0001_METRIC_TABLE_E40F7D11", "automotive_revenue", review_note="Reviewed Qualcomm QCT Automotive revenue from segment revenue table."),
    FactSpec("QCOM_HANDSETS_AUTOMOTIVE_REVENUE_MIX_2023_2025_001", "QCOM_2024_10K_ITEM7_BLOCK_0003_PART_02_OF_02_METRIC_TABLE_2B78F8AB", "automotive_revenue", review_note="Reviewed Qualcomm QCT Automotive revenue from segment revenue table."),
    FactSpec("QCOM_HANDSETS_AUTOMOTIVE_REVENUE_MIX_2023_2025_001", "QCOM_2025_10K_ITEM7_BLOCK_0003_PART_02_OF_02_METRIC_TABLE_BB96FFF7", "automotive_revenue", review_note="Reviewed Qualcomm QCT Automotive revenue from segment revenue table."),

    FactSpec("TXN_ANALOG_EMBEDDED_REVENUE_MIX_2023_2025_001", "TXN_2023_10K_ITEM7_BLOCK_0003_PART_01_OF_02_METRIC_TABLE_9AA4BDB0", "analog_revenue", unit_override="usd_millions", row_label_override="Analog", review_note="Reviewed Texas Instruments Analog segment revenue; source row is Revenue within Analog section."),
    FactSpec("TXN_ANALOG_EMBEDDED_REVENUE_MIX_2023_2025_001", "TXN_2024_10K_ITEM7_BLOCK_0003_PART_01_OF_02_METRIC_TABLE_00EC2147", "analog_revenue", unit_override="usd_millions", row_label_override="Analog", review_note="Reviewed Texas Instruments Analog segment revenue; source row is Revenue within Analog section."),
    FactSpec("TXN_ANALOG_EMBEDDED_REVENUE_MIX_2023_2025_001", "TXN_2025_10K_ITEM7_BLOCK_0003_PART_02_OF_03_METRIC_TABLE_DC804382", "analog_revenue", unit_override="usd_millions", row_label_override="Analog", review_note="Reviewed Texas Instruments Analog segment revenue; source row is Revenue within Analog section."),
    FactSpec("TXN_ANALOG_EMBEDDED_REVENUE_MIX_2023_2025_001", "TXN_2023_10K_ITEM7_BLOCK_0003_PART_01_OF_02_METRIC_TABLE_B0E9404F", "embedded_processing_revenue", unit_override="usd_millions", row_label_override="Embedded Processing", review_note="Reviewed Texas Instruments Embedded Processing segment revenue; source row is Revenue within Embedded Processing section."),
    FactSpec("TXN_ANALOG_EMBEDDED_REVENUE_MIX_2023_2025_001", "TXN_2024_10K_ITEM7_BLOCK_0003_PART_01_OF_02_METRIC_TABLE_CBCC18B6", "embedded_processing_revenue", unit_override="usd_millions", row_label_override="Embedded Processing", review_note="Reviewed Texas Instruments Embedded Processing segment revenue; source row is Revenue within Embedded Processing section."),
    FactSpec("TXN_ANALOG_EMBEDDED_REVENUE_MIX_2023_2025_001", "TXN_2025_10K_ITEM7_BLOCK_0003_PART_02_OF_03_METRIC_TABLE_ECB892C7", "embedded_processing_revenue", unit_override="usd_millions", row_label_override="Embedded Processing", review_note="Reviewed Texas Instruments Embedded Processing segment revenue; source row is Revenue within Embedded Processing section."),

    FactSpec("AMAT_SEMICONDUCTOR_SYSTEMS_SERVICES_REVENUE_MIX_2023_2025_001", "AMAT_2023_10K_ITEM7_BLOCK_0002_PART_02_OF_03_METRIC_TABLE_EE826EFE", "semiconductor_systems_revenue", review_note="Reviewed Applied Materials Semiconductor Systems net sales from segment net sales table."),
    FactSpec("AMAT_SEMICONDUCTOR_SYSTEMS_SERVICES_REVENUE_MIX_2023_2025_001", "AMAT_2024_10K_ITEM7_BLOCK_0002_PART_02_OF_03_METRIC_TABLE_C8D56D00", "semiconductor_systems_revenue", review_note="Reviewed Applied Materials Semiconductor Systems net revenue from segment net revenue table."),
    FactSpec("AMAT_SEMICONDUCTOR_SYSTEMS_SERVICES_REVENUE_MIX_2023_2025_001", "AMAT_2025_10K_ITEM7_BLOCK_0002_PART_02_OF_03_METRIC_TABLE_54234EAE", "semiconductor_systems_revenue", review_note="Reviewed Applied Materials Semiconductor Systems net revenue from segment net revenue table."),
    FactSpec("AMAT_SEMICONDUCTOR_SYSTEMS_SERVICES_REVENUE_MIX_2023_2025_001", "AMAT_2023_10K_ITEM7_BLOCK_0002_PART_02_OF_03_METRIC_TABLE_38860EC6", "applied_global_services_revenue", review_note="Reviewed Applied Global Services net sales from segment net sales table."),
    FactSpec("AMAT_SEMICONDUCTOR_SYSTEMS_SERVICES_REVENUE_MIX_2023_2025_001", "AMAT_2024_10K_ITEM7_BLOCK_0002_PART_02_OF_03_METRIC_TABLE_986152E2", "applied_global_services_revenue", review_note="Reviewed Applied Global Services net revenue from segment net revenue table."),
    FactSpec("AMAT_SEMICONDUCTOR_SYSTEMS_SERVICES_REVENUE_MIX_2023_2025_001", "AMAT_2025_10K_ITEM7_BLOCK_0002_PART_02_OF_03_METRIC_TABLE_9B3BE72D", "applied_global_services_revenue", review_note="Reviewed Applied Global Services net revenue from segment net revenue table."),

    FactSpec("MU_DRAM_NAND_REVENUE_CYCLE_2023_2025_001", "MU_2023_10K_ITEM8_BLOCK_0002_PART_03_OF_10_METRIC_TABLE_6C8BF12A", "dram_revenue", unit_override="usd_millions", review_note="Reviewed Micron DRAM revenue by technology; selected current-year value from comparative table."),
    FactSpec("MU_DRAM_NAND_REVENUE_CYCLE_2023_2025_001", "MU_2024_10K_ITEM8_BLOCK_0002_PART_03_OF_09_METRIC_TABLE_07AC4783", "dram_revenue", unit_override="usd_millions", review_note="Reviewed Micron DRAM revenue by technology; selected current-year value from comparative table."),
    FactSpec("MU_DRAM_NAND_REVENUE_CYCLE_2023_2025_001", "MU_2025_10K_ITEM8_BLOCK_0023_CHUNK_0001_METRIC_TABLE_14CC1B45", "dram_revenue", unit_override="usd_millions", review_note="Reviewed Micron DRAM revenue by technology; selected current-year value from comparative table."),
    FactSpec("MU_DRAM_NAND_REVENUE_CYCLE_2023_2025_001", "MU_2023_10K_ITEM8_BLOCK_0002_PART_03_OF_10_METRIC_TABLE_D515EC32", "nand_revenue", unit_override="usd_millions", review_note="Reviewed Micron NAND revenue by technology; selected current-year value from comparative table."),
    FactSpec("MU_DRAM_NAND_REVENUE_CYCLE_2023_2025_001", "MU_2024_10K_ITEM8_BLOCK_0002_PART_03_OF_09_METRIC_TABLE_4CCC3642", "nand_revenue", unit_override="usd_millions", review_note="Reviewed Micron NAND revenue by technology; selected current-year value from comparative table."),
    FactSpec("MU_DRAM_NAND_REVENUE_CYCLE_2023_2025_001", "MU_2025_10K_ITEM8_BLOCK_0023_CHUNK_0001_METRIC_TABLE_043680AA", "nand_revenue", unit_override="usd_millions", review_note="Reviewed Micron NAND revenue by technology; selected current-year value from comparative table."),

    FactSpec("INTU_SMALL_BUSINESS_CONSUMER_CREDIT_KARMA_MIX_2023_2025_001", "INTU_2023_10K_ITEM8_BLOCK_0001_PART_34_OF_35_METRIC_TABLE_28B203DA", "small_business_revenue", review_note="Reviewed Intuit Small Business & Self-Employed segment net revenue."),
    FactSpec("INTU_SMALL_BUSINESS_CONSUMER_CREDIT_KARMA_MIX_2023_2025_001", "INTU_2024_10K_ITEM8_BLOCK_0001_PART_36_OF_37_METRIC_TABLE_6470E2B5", "small_business_revenue", review_note="Reviewed Intuit Small Business & Self-Employed segment net revenue."),
    FactSpec("INTU_SMALL_BUSINESS_CONSUMER_CREDIT_KARMA_MIX_2023_2025_001", "INTU_2025_10K_ITEM8_BLOCK_0001_PART_35_OF_36_METRIC_TABLE_D3212B37", "small_business_revenue", row_label_override="Global Business Solutions", review_note="Reviewed Intuit Global Business Solutions segment net revenue; this is the fiscal 2025 successor label for the seed case business-line metric."),
    FactSpec("INTU_SMALL_BUSINESS_CONSUMER_CREDIT_KARMA_MIX_2023_2025_001", "INTU_2023_10K_ITEM8_BLOCK_0001_PART_34_OF_35_METRIC_TABLE_951A6A6E", "consumer_revenue", review_note="Reviewed Intuit Consumer segment net revenue."),
    FactSpec("INTU_SMALL_BUSINESS_CONSUMER_CREDIT_KARMA_MIX_2023_2025_001", "INTU_2024_10K_ITEM8_BLOCK_0001_PART_36_OF_37_METRIC_TABLE_5400A1DA", "consumer_revenue", review_note="Reviewed Intuit Consumer segment net revenue."),
    FactSpec("INTU_SMALL_BUSINESS_CONSUMER_CREDIT_KARMA_MIX_2023_2025_001", "INTU_2025_10K_ITEM8_BLOCK_0001_PART_35_OF_36_METRIC_TABLE_C430DAF0", "consumer_revenue", review_note="Reviewed Intuit Consumer segment net revenue."),
    FactSpec("INTU_SMALL_BUSINESS_CONSUMER_CREDIT_KARMA_MIX_2023_2025_001", "INTU_2023_10K_ITEM8_BLOCK_0001_PART_34_OF_35_METRIC_TABLE_2138C69A", "credit_karma_revenue", review_note="Reviewed Intuit Credit Karma segment net revenue; selected current-year value from comparative table."),
    FactSpec("INTU_SMALL_BUSINESS_CONSUMER_CREDIT_KARMA_MIX_2023_2025_001", "INTU_2024_10K_ITEM8_BLOCK_0001_PART_36_OF_37_METRIC_TABLE_9F4D05E0", "credit_karma_revenue", review_note="Reviewed Intuit Credit Karma segment net revenue."),
    FactSpec("INTU_SMALL_BUSINESS_CONSUMER_CREDIT_KARMA_MIX_2023_2025_001", "INTU_2025_10K_ITEM8_BLOCK_0001_PART_35_OF_36_METRIC_TABLE_D3838CE3", "credit_karma_revenue", review_note="Reviewed Intuit Credit Karma segment net revenue."),

    FactSpec("ADP_EMPLOYER_PEO_REVENUE_CLIENT_FUNDS_2023_2025_001", "ADP_2023_10K_ITEM7_BLOCK_0003_PART_02_OF_02_METRIC_TABLE_E18B2781", "employer_services_revenue", unit_override="usd_millions", review_note="Reviewed ADP Employer Services reportable-segment revenue."),
    FactSpec("ADP_EMPLOYER_PEO_REVENUE_CLIENT_FUNDS_2023_2025_001", "ADP_2024_10K_ITEM7_BLOCK_0004_PART_02_OF_02_METRIC_TABLE_957593E5", "employer_services_revenue", unit_override="usd_millions", review_note="Reviewed ADP Employer Services reportable-segment revenue."),
    FactSpec("ADP_EMPLOYER_PEO_REVENUE_CLIENT_FUNDS_2023_2025_001", "ADP_2025_10K_ITEM7_BLOCK_0004_PART_02_OF_02_METRIC_TABLE_AEDD469D", "employer_services_revenue", unit_override="usd_millions", review_note="Reviewed ADP Employer Services reportable-segment revenue."),
    FactSpec("ADP_EMPLOYER_PEO_REVENUE_CLIENT_FUNDS_2023_2025_001", "ADP_2023_10K_ITEM7_BLOCK_0003_PART_02_OF_02_METRIC_TABLE_740B93B5", "peo_services_revenue", unit_override="usd_millions", review_note="Reviewed ADP PEO Services reportable-segment revenue."),
    FactSpec("ADP_EMPLOYER_PEO_REVENUE_CLIENT_FUNDS_2023_2025_001", "ADP_2024_10K_ITEM7_BLOCK_0004_PART_02_OF_02_METRIC_TABLE_2D3CB462", "peo_services_revenue", unit_override="usd_millions", review_note="Reviewed ADP PEO Services reportable-segment revenue."),
    FactSpec("ADP_EMPLOYER_PEO_REVENUE_CLIENT_FUNDS_2023_2025_001", "ADP_2025_10K_ITEM7_BLOCK_0004_PART_02_OF_02_METRIC_TABLE_23156A14", "peo_services_revenue", unit_override="usd_millions", review_note="Reviewed ADP PEO Services reportable-segment revenue."),
    FactSpec("ADP_EMPLOYER_PEO_REVENUE_CLIENT_FUNDS_2023_2025_001", "ADP_2023_10K_ITEM8_BLOCK_0001_PART_02_OF_06_METRIC_TABLE_375FA27E", "client_funds_interest", review_note="Reviewed ADP interest on funds held for clients from consolidated statement of earnings."),
    FactSpec("ADP_EMPLOYER_PEO_REVENUE_CLIENT_FUNDS_2023_2025_001", "ADP_2024_10K_ITEM8_BLOCK_0001_PART_02_OF_06_METRIC_TABLE_3AEF80BA", "client_funds_interest", review_note="Reviewed ADP interest on funds held for clients from consolidated statement of earnings."),
    FactSpec("ADP_EMPLOYER_PEO_REVENUE_CLIENT_FUNDS_2023_2025_001", "ADP_2025_10K_ITEM8_BLOCK_0001_PART_02_OF_06_METRIC_TABLE_B8799F47", "client_funds_interest", review_note="Reviewed ADP interest on funds held for clients from consolidated statement of earnings."),

    FactSpec("CRWD_ARR_SUBSCRIPTION_GROSS_PROFIT_2023_2025_001", "CRWD_2023_10K_ITEM7_BLOCK_0004_PART_01_OF_02_METRIC_TABLE_49995E32", "arr", review_note="Reviewed CrowdStrike annual recurring revenue from ARR table."),
    FactSpec("CRWD_ARR_SUBSCRIPTION_GROSS_PROFIT_2023_2025_001", "CRWD_2024_10K_ITEM7_BLOCK_0003_PART_01_OF_04_METRIC_TABLE_730F1FA6", "arr", review_note="Reviewed CrowdStrike annual recurring revenue from ARR table."),
    FactSpec("CRWD_ARR_SUBSCRIPTION_GROSS_PROFIT_2023_2025_001", "CRWD_2025_10K_ITEM7_BLOCK_0003_PART_01_OF_02_METRIC_TABLE_451AD09F", "arr", review_note="Reviewed CrowdStrike annual recurring revenue from ARR table."),
    FactSpec("CRWD_ARR_SUBSCRIPTION_GROSS_PROFIT_2023_2025_001", "CRWD_2023_10K_ITEM7_BLOCK_0007_PART_02_OF_06_METRIC_TABLE_5392E67B", "subscription_gross_profit", review_note="Reviewed CrowdStrike subscription gross profit from gross profit table."),
    FactSpec("CRWD_ARR_SUBSCRIPTION_GROSS_PROFIT_2023_2025_001", "CRWD_2024_10K_ITEM7_BLOCK_0003_PART_02_OF_04_METRIC_TABLE_19428167", "subscription_gross_profit", review_note="Reviewed CrowdStrike subscription gross profit from gross profit table."),
    FactSpec("CRWD_ARR_SUBSCRIPTION_GROSS_PROFIT_2023_2025_001", "CRWD_2025_10K_ITEM7_BLOCK_0006_PART_02_OF_06_METRIC_TABLE_88D70F60", "subscription_gross_profit", review_note="Reviewed CrowdStrike subscription gross profit from gross profit table."),
]


CAVEAT_CONTEXT = {
    "AVGO_PRODUCT_SUBSCRIPTION_REVENUE_MIX_2023_2025_001": "Broadcom Subscriptions and services revenue is a product/service revenue line and must not be treated as ARR or pure SaaS revenue unless SEC filings explicitly disclose that scope.",
    "CSCO_PRODUCT_SERVICE_RPO_VISIBILITY_2023_2025_001": "Cisco remaining performance obligations are contracted obligations expected to be recognized later; RPO is not the same as recognized revenue.",
    "INTC_REVENUE_GROSS_PROFIT_FOUNDRY_RISK_2023_2025_001": "Intel consolidated gross profit/gross margin dollars do not isolate Intel Foundry profitability and do not prove durable AI demand by themselves.",
    "QCOM_HANDSETS_AUTOMOTIVE_REVENUE_MIX_2023_2025_001": "Qualcomm Handsets and Automotive are QCT business-line revenues, not total Qualcomm revenue or standalone market-share evidence.",
    "TXN_ANALOG_EMBEDDED_REVENUE_MIX_2023_2025_001": "Texas Instruments segment revenue alone does not prove durable end-market demand; cycle and industrial demand context must be kept separate.",
    "AMAT_SEMICONDUCTOR_SYSTEMS_SERVICES_REVENUE_MIX_2023_2025_001": "Applied Materials segment revenue should not be replaced with backlog or orders, and equipment-cycle exposure remains a caveat.",
    "MU_DRAM_NAND_REVENUE_CYCLE_2023_2025_001": "Micron DRAM and NAND revenue must be interpreted with memory-cycle and pricing caveats; revenue alone does not prove durable AI demand.",
    "INTU_SMALL_BUSINESS_CONSUMER_CREDIT_KARMA_MIX_2023_2025_001": "Intuit segment revenue is not all ARR or subscription revenue; segment definitions and the fiscal 2025 Global Business Solutions label must be kept explicit.",
    "ADP_EMPLOYER_PEO_REVENUE_CLIENT_FUNDS_2023_2025_001": "ADP client-funds interest is separate from Employer Services and PEO Services revenue and should not be treated as core subscription/service revenue.",
    "CRWD_ARR_SUBSCRIPTION_GROSS_PROFIT_2023_2025_001": "CrowdStrike ARR is a visibility metric and is not recognized revenue or gross profit.",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build reviewed-gold assets for SEC benchmark v2 new20 new-company seed cases.")
    parser.add_argument("--metrics-path", default="data/processed_private/structured_objects/sec_tech_10k_metrics.jsonl")
    parser.add_argument("--evidence-path", default="data/processed_private/evidence_objects/sec_tech_10k_evidence.jsonl")
    parser.add_argument(
        "--approval-path",
        default="reports/quality/sec_benchmark_v2_new20_newco_reviewed_gold_partial_approval.json",
    )
    parser.add_argument(
        "--build-report-path",
        default="reports/quality/sec_benchmark_v2_new20_newco_reviewed_gold_build_report.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    REVIEWED_CONTEXT_DIR.mkdir(parents=True, exist_ok=True)
    REVIEWED_FACTS_DIR.mkdir(parents=True, exist_ok=True)
    QUALITY_DIR.mkdir(parents=True, exist_ok=True)

    metrics_by_id = {str(row.get("object_id") or ""): row for row in _read_jsonl(_resolve(args.metrics_path))}
    evidence_by_id = {str(row.get("evidence_id") or ""): row for row in _read_jsonl(_resolve(args.evidence_path))}

    missing = [spec.object_id for spec in FACT_SPECS if spec.object_id not in metrics_by_id]
    if missing:
        raise SystemExit(f"Missing MetricObject ids: {missing}")

    facts_by_case: dict[str, list[dict[str, Any]]] = {case_id: [] for case_id in NEW20_CASE_IDS}
    for spec in FACT_SPECS:
        facts_by_case[spec.case_id].append(_fact_from_spec(spec, metrics_by_id[spec.object_id]))

    case_summaries = []
    for case_id in NEW20_CASE_IDS:
        facts = _renumber_facts(case_id, facts_by_case[case_id])
        _assert_case_contract(case_id, facts)
        context_rows = [_context_from_fact(case_id, fact, evidence_by_id) for fact in facts]
        context_rows.append(_review_note_context(case_id, facts[0]["ticker"], 2025, CAVEAT_CONTEXT[case_id]))
        case_summaries.append(_write_case(case_id, facts, context_rows))

    approval_path = _resolve(args.approval_path)
    build_report_path = _resolve(args.build_report_path)
    _write_approval(approval_path, case_summaries)
    build_report = {
        "schema_version": "sec_v2_new20_newco_reviewed_gold_build_report_v0.1",
        "reviewed_case_ids": NEW20_CASE_IDS,
        "case_count": len(NEW20_CASE_IDS),
        "fact_count": sum(item["fact_count"] for item in case_summaries),
        "context_row_count": sum(item["context_row_count"] for item in case_summaries),
        "cases": case_summaries,
        "approval_path": str(approval_path.resolve()),
        "source_policy": "SEC_ONLY",
        "metrics_path": str(_resolve(args.metrics_path).resolve()),
        "evidence_path": str(_resolve(args.evidence_path).resolve()),
        "selection_policy": "explicit_reviewed_metric_object_ids_with_unit_and_label_overrides_for_extractor_alignment_or_source_label_variants",
    }
    build_report_path.parent.mkdir(parents=True, exist_ok=True)
    build_report_path.write_text(json.dumps(build_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "reviewed_case_count": len(NEW20_CASE_IDS),
                "fact_count": build_report["fact_count"],
                "context_row_count": build_report["context_row_count"],
                "approval_path": str(approval_path),
                "build_report_path": str(build_report_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def _fact_from_spec(spec: FactSpec, record: dict[str, Any]) -> dict[str, Any]:
    period = int(record["period"])
    raw_unit = str(record.get("unit") or "")
    unit = spec.unit_override or raw_unit
    value = float(record["value"])
    row_label = spec.row_label_override or record.get("row_label")
    metric_name = spec.metric_name_override or record.get("metric_name")
    fact = {
        "fact_id": "",
        "review_status": "reviewed_keep",
        "selection_method": "manual_review_structured_object_explicit_id",
        "metric_id": f"{record['ticker']}_{period}_{spec.metric_family}_{spec.metric_role}",
        "case_id": spec.case_id,
        "ticker": record["ticker"],
        "fiscal_year": period,
        "period": str(period),
        "metric_name": metric_name,
        "metric_family": spec.metric_family,
        "metric_role": spec.metric_role,
        "raw_value": str(record.get("raw_value") or ""),
        "value": value,
        "unit": unit,
        "display_value_en": _display_value_en(value, unit),
        "object_id": record["object_id"],
        "source_evidence_id": record["source_evidence_id"],
        "section": record.get("section"),
        "row_label": row_label,
        "column_label": record.get("column_label"),
        "source_row_label": record.get("row_label"),
        "source_metric_name": record.get("metric_name"),
        "source_unit": raw_unit or None,
        "source_table_object_id": record.get("table_object_id"),
        "allowed_claim_roles": [f"{spec.metric_family}_{spec.metric_role}"],
        "disallowed_claim_roles": _disallowed_roles(spec.metric_family),
        "review_note": spec.review_note,
    }
    return fact


def _context_from_fact(case_id: str, fact: dict[str, Any], evidence_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    evidence = evidence_by_id.get(str(fact.get("source_evidence_id") or ""), {})
    return {
        "schema_version": "sec_gold_context_reviewed_v0.1",
        "case_id": case_id,
        "review_status": "reviewed_keep",
        "gold_role": "core_structured_fact",
        "source_kind": "reviewed_table_cell",
        "object_id": fact.get("object_id"),
        "source_evidence_id": fact.get("source_evidence_id"),
        "ticker": fact.get("ticker"),
        "fiscal_year": fact.get("fiscal_year"),
        "source_type": evidence.get("source_type") or "10-K",
        "section": fact.get("section"),
        "source_url": evidence.get("source_url"),
        "local_path": evidence.get("local_path"),
        "metric_name": fact.get("metric_name"),
        "metric_family": fact.get("metric_family"),
        "metric_role": fact.get("metric_role"),
        "raw_value": fact.get("raw_value"),
        "value": fact.get("value"),
        "unit": fact.get("unit"),
        "period": fact.get("period"),
        "row_label": fact.get("row_label"),
        "source_row_label": fact.get("source_row_label"),
        "column_label": fact.get("column_label"),
        "text": (
            f"{fact['ticker']} fiscal {fact['period']} {fact['metric_name']} "
            f"({fact.get('row_label')}): {fact['raw_value']} {fact['unit']}; metric_id={fact['metric_id']}."
        ),
        "review_note": fact.get("review_note"),
    }


def _review_note_context(case_id: str, ticker: str, fiscal_year: int, text: str) -> dict[str, Any]:
    return {
        "schema_version": "sec_gold_context_reviewed_v0.1",
        "case_id": case_id,
        "review_status": "reviewed_keep",
        "gold_role": "caveat",
        "source_kind": "reviewed_source_policy_note",
        "source_evidence_id": f"REVIEW_NOTE_{case_id}",
        "ticker": ticker,
        "fiscal_year": fiscal_year,
        "source_type": "review_note",
        "section": "review_note",
        "text": text,
        "review_note": "Manual review caveat for new20 new-company seed promotion.",
    }


def _write_case(case_id: str, facts: list[dict[str, Any]], context_rows: list[dict[str, Any]]) -> dict[str, Any]:
    _write_jsonl(REVIEWED_CONTEXT_DIR / f"{case_id}.jsonl", context_rows)
    payload = {
        "schema_version": "sec_gold_facts_reviewed_v0.1",
        "case_id": case_id,
        "benchmark_version": "sec_benchmark_v2_new20_newco",
        "review_status": "reviewed_approved_single_case",
        "review_scope": {
            "source_policy": "SEC_ONLY",
            "allowed_filing_types": ["10-K"],
            "source_basis": "explicit reviewed structured SEC MetricObjects from cloud 20-company build",
            "companies": sorted({str(fact.get("ticker") or "") for fact in facts}),
            "years": sorted({int(fact.get("fiscal_year")) for fact in facts}),
            "metric_families": sorted({str(fact.get("metric_family") or "") for fact in facts}),
        },
        "facts": facts,
    }
    facts_path = REVIEWED_FACTS_DIR / f"{case_id}.json"
    facts_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "case_id": case_id,
        "fact_count": len(facts),
        "context_row_count": len(context_rows),
        "facts_path": str(facts_path),
        "context_path": str(REVIEWED_CONTEXT_DIR / f"{case_id}.jsonl"),
        "metric_families": sorted({str(fact.get("metric_family") or "") for fact in facts}),
    }


def _assert_case_contract(case_id: str, facts: list[dict[str, Any]]) -> None:
    expected_by_case = {
        "AVGO_PRODUCT_SUBSCRIPTION_REVENUE_MIX_2023_2025_001": {("AVGO", year, family) for year in [2023, 2024, 2025] for family in ["products_revenue", "subscription_services_revenue"]},
        "CSCO_PRODUCT_SERVICE_RPO_VISIBILITY_2023_2025_001": {("CSCO", year, family) for year in [2023, 2024, 2025] for family in ["product_revenue", "services_revenue", "rpo"]},
        "INTC_REVENUE_GROSS_PROFIT_FOUNDRY_RISK_2023_2025_001": {("INTC", year, family) for year in [2023, 2024, 2025] for family in ["net_revenue", "gross_profit"]},
        "QCOM_HANDSETS_AUTOMOTIVE_REVENUE_MIX_2023_2025_001": {("QCOM", year, family) for year in [2023, 2024, 2025] for family in ["handsets_revenue", "automotive_revenue"]},
        "TXN_ANALOG_EMBEDDED_REVENUE_MIX_2023_2025_001": {("TXN", year, family) for year in [2023, 2024, 2025] for family in ["analog_revenue", "embedded_processing_revenue"]},
        "AMAT_SEMICONDUCTOR_SYSTEMS_SERVICES_REVENUE_MIX_2023_2025_001": {("AMAT", year, family) for year in [2023, 2024, 2025] for family in ["semiconductor_systems_revenue", "applied_global_services_revenue"]},
        "MU_DRAM_NAND_REVENUE_CYCLE_2023_2025_001": {("MU", year, family) for year in [2023, 2024, 2025] for family in ["dram_revenue", "nand_revenue"]},
        "INTU_SMALL_BUSINESS_CONSUMER_CREDIT_KARMA_MIX_2023_2025_001": {("INTU", year, family) for year in [2023, 2024, 2025] for family in ["small_business_revenue", "consumer_revenue", "credit_karma_revenue"]},
        "ADP_EMPLOYER_PEO_REVENUE_CLIENT_FUNDS_2023_2025_001": {("ADP", year, family) for year in [2023, 2024, 2025] for family in ["employer_services_revenue", "peo_services_revenue", "client_funds_interest"]},
        "CRWD_ARR_SUBSCRIPTION_GROSS_PROFIT_2023_2025_001": {("CRWD", year, family) for year in [2023, 2024, 2025] for family in ["arr", "subscription_gross_profit"]},
    }
    expected = expected_by_case[case_id]
    actual = {
        (str(fact.get("ticker") or ""), int(fact.get("fiscal_year")), str(fact.get("metric_family") or ""))
        for fact in facts
    }
    if actual != expected:
        raise SystemExit(f"{case_id} fact coverage mismatch: missing={sorted(expected - actual)} extra={sorted(actual - expected)}")


def _renumber_facts(case_id: str, facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(
        facts,
        key=lambda fact: (
            str(fact.get("ticker") or ""),
            int(fact.get("fiscal_year") or 0),
            str(fact.get("metric_family") or ""),
        ),
    )
    for index, fact in enumerate(ordered, start=1):
        fact["fact_id"] = f"{case_id}_FACT_REVIEWED_{index:04d}"
    return ordered


def _write_approval(path: Path, case_summaries: list[dict[str, Any]]) -> None:
    payload = {
        "schema_version": "sec_gold_manual_review_v0.2",
        "review_scope": {
            "gold_context_dir": "eval/sec_cases/reviewed_gold_context",
            "gold_facts_dir": "eval/sec_cases/reviewed_gold_facts",
            "case_count": len(NEW20_CASE_IDS),
            "reviewed_case_ids": NEW20_CASE_IDS,
        },
        "review_decision": {
            "overall_status": "partial_approved_for_mainline_scored_benchmark",
            "allowed_next_step": "case_filtered_new20_newco_gold_gate",
            "blocked_next_step": "unfiltered_full_benchmark_mainline_scored_test",
            "reason": "The ten new-company seed cases are promoted with explicit reviewed SEC numeric/table facts. Promotion is case-filtered until they are merged into a broader full benchmark approval.",
        },
        "case_reviews": [
            {
                "case_id": item["case_id"],
                "decision": "approved_for_gold_context_mode",
                "mainline_status": "can_enter_case_filtered_scored_gold_context_smoke",
                "evidence_assessment": f"Reviewed SEC evidence built for {item['case_id']} with {item['context_row_count']} context rows.",
                "fact_assessment": f"Reviewed facts contain {item['fact_count']} target facts across {', '.join(item['metric_families'])}.",
                "required_fix": "Before merged full-benchmark promotion, rerun exact-value ledger, ledger-unit, caveat/claim, and answer-vs-Judgment-Plan gates on the expanded case package.",
            }
            for item in case_summaries
        ],
        "gate": {
            "can_enter_full_mainline_scored_test": False,
            "can_enter_case_filtered_gold_context_scored_smoke": True,
            "approved_case_ids": NEW20_CASE_IDS,
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8")


def _resolve(path: str) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else REPO_ROOT / candidate


def _display_value_en(value: float, unit: str) -> str:
    if unit == "usd_millions":
        return f"${value / 1000:.3f} billion"
    if unit == "usd_thousands":
        return f"${value / 1000:.3f} million"
    if unit == "usd_billions":
        return f"${value:.3f} billion"
    if unit == "percent":
        return f"{value:.1f}%"
    return str(value)


def _disallowed_roles(metric_family: str) -> list[str]:
    common = [
        "products_revenue",
        "subscription_services_revenue",
        "product_revenue",
        "services_revenue",
        "rpo",
        "net_revenue",
        "gross_profit",
        "handsets_revenue",
        "automotive_revenue",
        "analog_revenue",
        "embedded_processing_revenue",
        "semiconductor_systems_revenue",
        "applied_global_services_revenue",
        "dram_revenue",
        "nand_revenue",
        "small_business_revenue",
        "consumer_revenue",
        "credit_karma_revenue",
        "employer_services_revenue",
        "peo_services_revenue",
        "client_funds_interest",
        "arr",
        "subscription_gross_profit",
        "total_revenue",
        "market_share",
        "stock_market_causality",
        "backlog_as_revenue",
    ]
    return [item for item in common if item != metric_family]


if __name__ == "__main__":
    main()
