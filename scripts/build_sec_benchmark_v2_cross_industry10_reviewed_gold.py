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

CASE_IDS = [
    "JPM_BANK_SEGMENTS_RATE_CREDIT_RISK_2025_001",
    "V_NET_REVENUE_PROCESSED_TRANSACTIONS_2023_2025_001",
    "JNJ_INNOVATIVE_MEDICINE_MEDTECH_SCOPE_2025_001",
    "LLY_REVENUE_RND_PIPELINE_INVESTMENT_2023_2025_001",
    "CAT_SALES_REVENUES_PROFIT_CYCLE_2023_2025_001",
    "GE_RPO_EQUIPMENT_SERVICES_VISIBILITY_2023_2025_001",
    "WMT_NET_SALES_TOTAL_REVENUES_2023_2025_001",
    "PG_NET_SALES_EARNINGS_STAPLES_2023_2025_001",
    "XOM_ENERGY_MARKET_TRANSITION_RISK_2025_001",
    "CVX_UPSTREAM_DOWNSTREAM_COMMODITY_RISK_2025_001",
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


@dataclass(frozen=True)
class EvidenceSpec:
    case_id: str
    evidence_id: str
    gold_role: str
    review_note: str


FACT_SPECS: list[FactSpec] = [
    FactSpec("V_NET_REVENUE_PROCESSED_TRANSACTIONS_2023_2025_001", "V_2023_10K_ITEM8_BLOCK_0001_PART_03_OF_04_METRIC_TABLE_0A107F05", "net_revenue", row_label_override="Net revenues", metric_name_override="Net revenue", review_note="Reviewed Visa net revenue from consolidated statement."),
    FactSpec("V_NET_REVENUE_PROCESSED_TRANSACTIONS_2023_2025_001", "V_2024_10K_ITEM8_BLOCK_0001_PART_03_OF_03_METRIC_TABLE_DAFFCEB2", "net_revenue", row_label_override="Net revenues", metric_name_override="Net revenue", review_note="Reviewed Visa net revenue from consolidated statement; source row uses singular Net revenue."),
    FactSpec("V_NET_REVENUE_PROCESSED_TRANSACTIONS_2023_2025_001", "V_2025_10K_ITEM8_BLOCK_0001_PART_03_OF_03_METRIC_TABLE_463392E5", "net_revenue", row_label_override="Net revenues", metric_name_override="Net revenue", review_note="Reviewed Visa net revenue from consolidated statement; source row uses singular Net revenue."),
    FactSpec("V_NET_REVENUE_PROCESSED_TRANSACTIONS_2023_2025_001", "V_2023_10K_ITEM7_BLOCK_0003_PART_04_OF_04_METRIC_TABLE_E276A218", "processed_transactions", review_note="Reviewed Visa processed transactions from operating metric table; unit follows existing ledger unit convention for in-millions table cells."),
    FactSpec("V_NET_REVENUE_PROCESSED_TRANSACTIONS_2023_2025_001", "V_2024_10K_ITEM7_BLOCK_0003_PART_04_OF_04_METRIC_TABLE_1F404BBD", "processed_transactions", review_note="Reviewed Visa processed transactions from operating metric table; unit follows existing ledger unit convention for in-millions table cells."),
    FactSpec("V_NET_REVENUE_PROCESSED_TRANSACTIONS_2023_2025_001", "V_2025_10K_ITEM7_BLOCK_0003_PART_04_OF_04_METRIC_TABLE_1E6C50B0", "processed_transactions", review_note="Reviewed Visa processed transactions from operating metric table; unit follows existing ledger unit convention for in-millions table cells."),

    FactSpec("LLY_REVENUE_RND_PIPELINE_INVESTMENT_2023_2025_001", "LLY_2023_10K_ITEM8_BLOCK_0001_PART_01_OF_03_METRIC_TABLE_A7C7E3CC", "revenue", row_label_override="Revenue", metric_name_override="Revenue", review_note="Reviewed Eli Lilly revenue from consolidated statements; selected current-year column despite extractor header shift."),
    FactSpec("LLY_REVENUE_RND_PIPELINE_INVESTMENT_2023_2025_001", "LLY_2024_10K_ITEM8_BLOCK_0001_CHUNK_0001_METRIC_TABLE_E5126368", "revenue", row_label_override="Revenue", metric_name_override="Revenue", review_note="Reviewed Eli Lilly revenue from consolidated statements."),
    FactSpec("LLY_REVENUE_RND_PIPELINE_INVESTMENT_2023_2025_001", "LLY_2025_10K_ITEM8_BLOCK_0001_CHUNK_0001_METRIC_TABLE_83109155", "revenue", review_note="Reviewed Eli Lilly revenue from consolidated statements."),
    FactSpec("LLY_REVENUE_RND_PIPELINE_INVESTMENT_2023_2025_001", "LLY_2023_10K_ITEM8_BLOCK_0001_PART_01_OF_03_METRIC_TABLE_B232A7CE", "research_and_development", review_note="Reviewed Eli Lilly research and development expense from consolidated statements; selected current-year column despite extractor header shift."),
    FactSpec("LLY_REVENUE_RND_PIPELINE_INVESTMENT_2023_2025_001", "LLY_2024_10K_ITEM8_BLOCK_0001_CHUNK_0001_METRIC_TABLE_91F9A858", "research_and_development", review_note="Reviewed Eli Lilly research and development expense from consolidated statements."),
    FactSpec("LLY_REVENUE_RND_PIPELINE_INVESTMENT_2023_2025_001", "LLY_2025_10K_ITEM8_BLOCK_0001_CHUNK_0001_METRIC_TABLE_CD1B9413", "research_and_development", review_note="Reviewed Eli Lilly research and development expense from consolidated statements."),

    FactSpec("CAT_SALES_REVENUES_PROFIT_CYCLE_2023_2025_001", "CAT_2023_10K_ITEM8_BLOCK_0001_PART_02_OF_46_METRIC_TABLE_6ED52F26", "total_sales_and_revenues", review_note="Reviewed Caterpillar total sales and revenues from consolidated results."),
    FactSpec("CAT_SALES_REVENUES_PROFIT_CYCLE_2023_2025_001", "CAT_2024_10K_ITEM8_BLOCK_0001_PART_02_OF_47_METRIC_TABLE_D197D298", "total_sales_and_revenues", review_note="Reviewed Caterpillar total sales and revenues from consolidated results."),
    FactSpec("CAT_SALES_REVENUES_PROFIT_CYCLE_2023_2025_001", "CAT_2025_10K_ITEM8_BLOCK_0001_PART_02_OF_46_METRIC_TABLE_FE511FA1", "total_sales_and_revenues", review_note="Reviewed Caterpillar total sales and revenues from consolidated results."),
    FactSpec("CAT_SALES_REVENUES_PROFIT_CYCLE_2023_2025_001", "CAT_2023_10K_ITEM8_BLOCK_0001_PART_02_OF_46_METRIC_TABLE_DB2122D0", "consolidated_profit_before_taxes", review_note="Reviewed Caterpillar consolidated profit before taxes from consolidated results."),
    FactSpec("CAT_SALES_REVENUES_PROFIT_CYCLE_2023_2025_001", "CAT_2024_10K_ITEM8_BLOCK_0001_PART_02_OF_47_METRIC_TABLE_3C7A5636", "consolidated_profit_before_taxes", review_note="Reviewed Caterpillar consolidated profit before taxes from consolidated results."),
    FactSpec("CAT_SALES_REVENUES_PROFIT_CYCLE_2023_2025_001", "CAT_2025_10K_ITEM8_BLOCK_0001_PART_02_OF_46_METRIC_TABLE_D8E62CDC", "consolidated_profit_before_taxes", review_note="Reviewed Caterpillar consolidated profit before taxes from consolidated results."),

    FactSpec("GE_RPO_EQUIPMENT_SERVICES_VISIBILITY_2023_2025_001", "GE_2023_10K_ITEM7_BLOCK_0002_PART_01_OF_02_METRIC_TABLE_0872A819", "equipment_rpo", unit_override="usd_millions", review_note="Reviewed GE equipment RPO from summary RPO table; source table implies dollars in millions."),
    FactSpec("GE_RPO_EQUIPMENT_SERVICES_VISIBILITY_2023_2025_001", "GE_2024_10K_ITEM7_BLOCK_0002_PART_02_OF_02_METRIC_TABLE_1FBF8F02", "equipment_rpo", unit_override="usd_millions", review_note="Reviewed GE equipment RPO from business overview RPO table; source table implies dollars in millions."),
    FactSpec("GE_RPO_EQUIPMENT_SERVICES_VISIBILITY_2023_2025_001", "GE_2025_10K_ITEM7_BLOCK_0002_PART_02_OF_02_METRIC_TABLE_CCD98853", "equipment_rpo", unit_override="usd_millions", review_note="Reviewed GE equipment RPO from business overview RPO table; source table implies dollars in millions."),
    FactSpec("GE_RPO_EQUIPMENT_SERVICES_VISIBILITY_2023_2025_001", "GE_2023_10K_ITEM7_BLOCK_0002_PART_01_OF_02_METRIC_TABLE_02B5C7B5", "services_rpo", unit_override="usd_millions", review_note="Reviewed GE services RPO from summary RPO table; source table implies dollars in millions."),
    FactSpec("GE_RPO_EQUIPMENT_SERVICES_VISIBILITY_2023_2025_001", "GE_2024_10K_ITEM7_BLOCK_0002_PART_02_OF_02_METRIC_TABLE_63A94C31", "services_rpo", unit_override="usd_millions", review_note="Reviewed GE services RPO from business overview RPO table; source table implies dollars in millions."),
    FactSpec("GE_RPO_EQUIPMENT_SERVICES_VISIBILITY_2023_2025_001", "GE_2025_10K_ITEM7_BLOCK_0002_PART_02_OF_02_METRIC_TABLE_1B7CC706", "services_rpo", unit_override="usd_millions", review_note="Reviewed GE services RPO from business overview RPO table; source table implies dollars in millions."),
    FactSpec("GE_RPO_EQUIPMENT_SERVICES_VISIBILITY_2023_2025_001", "GE_2023_10K_ITEM7_BLOCK_0002_PART_01_OF_02_METRIC_TABLE_DDB61DF4", "total_rpo", unit_override="usd_millions", review_note="Reviewed GE total RPO from summary RPO table; source table implies dollars in millions."),
    FactSpec("GE_RPO_EQUIPMENT_SERVICES_VISIBILITY_2023_2025_001", "GE_2024_10K_ITEM7_BLOCK_0002_PART_02_OF_02_METRIC_TABLE_F31BE80B", "total_rpo", unit_override="usd_millions", review_note="Reviewed GE total RPO from business overview RPO table; source table implies dollars in millions."),
    FactSpec("GE_RPO_EQUIPMENT_SERVICES_VISIBILITY_2023_2025_001", "GE_2025_10K_ITEM7_BLOCK_0002_PART_02_OF_02_METRIC_TABLE_D75C5E32", "total_rpo", unit_override="usd_millions", review_note="Reviewed GE total RPO from business overview RPO table; source table implies dollars in millions."),

    FactSpec("WMT_NET_SALES_TOTAL_REVENUES_2023_2025_001", "WMT_2023_10K_ITEM8_BLOCK_0001_PART_02_OF_05_METRIC_TABLE_AB70B0EB", "net_sales", review_note="Reviewed Walmart net sales from consolidated statements; selected current-year column despite extractor header shift."),
    FactSpec("WMT_NET_SALES_TOTAL_REVENUES_2023_2025_001", "WMT_2024_10K_ITEM8_BLOCK_0001_PART_02_OF_05_METRIC_TABLE_3B7F2E5B", "net_sales", review_note="Reviewed Walmart net sales from consolidated statements; selected current-year column despite extractor header shift."),
    FactSpec("WMT_NET_SALES_TOTAL_REVENUES_2023_2025_001", "WMT_2025_10K_ITEM8_BLOCK_0001_PART_02_OF_05_METRIC_TABLE_A5C58B36", "net_sales", review_note="Reviewed Walmart net sales from consolidated statements; selected current-year column despite extractor header shift."),
    FactSpec("WMT_NET_SALES_TOTAL_REVENUES_2023_2025_001", "WMT_2023_10K_ITEM8_BLOCK_0001_PART_02_OF_05_METRIC_TABLE_63C80110", "total_revenues", review_note="Reviewed Walmart total revenues from consolidated statements; selected current-year column despite extractor header shift."),
    FactSpec("WMT_NET_SALES_TOTAL_REVENUES_2023_2025_001", "WMT_2024_10K_ITEM8_BLOCK_0001_PART_02_OF_05_METRIC_TABLE_76DC8559", "total_revenues", review_note="Reviewed Walmart total revenues from consolidated statements; selected current-year column despite extractor header shift."),
    FactSpec("WMT_NET_SALES_TOTAL_REVENUES_2023_2025_001", "WMT_2025_10K_ITEM8_BLOCK_0001_PART_02_OF_05_METRIC_TABLE_EA711A83", "total_revenues", review_note="Reviewed Walmart total revenues from consolidated statements; selected current-year column despite extractor header shift."),

    FactSpec("PG_NET_SALES_EARNINGS_STAPLES_2023_2025_001", "PG_2023_10K_ITEM8_BLOCK_0001_PART_03_OF_06_METRIC_TABLE_5D9983A1", "net_sales", row_label_override="Net sales", metric_name_override="Net sales", review_note="Reviewed Procter & Gamble net sales from consolidated statements; selected current-year column despite extractor header shift."),
    FactSpec("PG_NET_SALES_EARNINGS_STAPLES_2023_2025_001", "PG_2024_10K_ITEM8_BLOCK_0001_PART_03_OF_06_METRIC_TABLE_46FB06CF", "net_sales", row_label_override="Net sales", metric_name_override="Net sales", review_note="Reviewed Procter & Gamble net sales from consolidated statements; selected current-year column despite extractor header shift."),
    FactSpec("PG_NET_SALES_EARNINGS_STAPLES_2023_2025_001", "PG_2025_10K_ITEM8_BLOCK_0001_PART_03_OF_06_METRIC_TABLE_0BEA92C6", "net_sales", row_label_override="Net sales", metric_name_override="Net sales", review_note="Reviewed Procter & Gamble net sales from consolidated statements; selected current-year column despite extractor header shift."),
    FactSpec("PG_NET_SALES_EARNINGS_STAPLES_2023_2025_001", "PG_2023_10K_ITEM8_BLOCK_0001_PART_05_OF_06_METRIC_TABLE_F47AECE4", "net_earnings", row_label_override="Net earnings", metric_name_override="Net earnings", review_note="Reviewed Procter & Gamble net earnings from consolidated statements; selected current-year column despite extractor header shift."),
    FactSpec("PG_NET_SALES_EARNINGS_STAPLES_2023_2025_001", "PG_2024_10K_ITEM8_BLOCK_0001_PART_05_OF_06_METRIC_TABLE_86BCC593", "net_earnings", row_label_override="Net earnings", metric_name_override="Net earnings", review_note="Reviewed Procter & Gamble net earnings from consolidated statements; selected current-year column despite extractor header shift."),
    FactSpec("PG_NET_SALES_EARNINGS_STAPLES_2023_2025_001", "PG_2025_10K_ITEM8_BLOCK_0001_PART_05_OF_06_METRIC_TABLE_3EC7C1CE", "net_earnings", row_label_override="Net earnings", metric_name_override="Net earnings", review_note="Reviewed Procter & Gamble net earnings from consolidated statements; selected current-year column despite extractor header shift."),
]


EVIDENCE_SPECS: list[EvidenceSpec] = [
    EvidenceSpec("JPM_BANK_SEGMENTS_RATE_CREDIT_RISK_2025_001", "JPM_2025_10K_ITEM1_BLOCK_0002_CHUNK_0001", "core", "Reviewed JPM segment-scope text."),
    EvidenceSpec("JPM_BANK_SEGMENTS_RATE_CREDIT_RISK_2025_001", "JPM_2025_10K_ITEM1A_BLOCK_0024_CHUNK_0001", "caveat", "Reviewed JPM interest-rate and credit-spread risk text."),
    EvidenceSpec("JPM_BANK_SEGMENTS_RATE_CREDIT_RISK_2025_001", "JPM_2025_10K_ITEM1A_BLOCK_0034_CHUNK_0001", "caveat", "Reviewed JPM liquidity risk text."),
    EvidenceSpec("JPM_BANK_SEGMENTS_RATE_CREDIT_RISK_2025_001", "JPM_2025_10K_ITEM1_BLOCK_0005_PART_01_OF_02", "support", "Reviewed JPM capital and liquidity requirements text."),

    EvidenceSpec("JNJ_INNOVATIVE_MEDICINE_MEDTECH_SCOPE_2025_001", "JNJ_2025_10K_ITEM1_BLOCK_0001_PART_01_OF_03", "core", "Reviewed JNJ healthcare business description."),
    EvidenceSpec("JNJ_INNOVATIVE_MEDICINE_MEDTECH_SCOPE_2025_001", "JNJ_2025_10K_ITEM7_BLOCK_0001_PART_01_OF_05", "core", "Reviewed JNJ business-segment overview."),
    EvidenceSpec("JNJ_INNOVATIVE_MEDICINE_MEDTECH_SCOPE_2025_001", "JNJ_2025_10K_ITEM7_BLOCK_0001_PART_03_OF_05", "support", "Reviewed JNJ Innovative Medicine product and sales context."),
    EvidenceSpec("JNJ_INNOVATIVE_MEDICINE_MEDTECH_SCOPE_2025_001", "JNJ_2025_10K_ITEM7_BLOCK_0001_PART_05_OF_05", "support", "Reviewed JNJ MedTech product context."),
    EvidenceSpec("JNJ_INNOVATIVE_MEDICINE_MEDTECH_SCOPE_2025_001", "JNJ_2025_10K_ITEM1A_BLOCK_0006_CHUNK_0001", "caveat", "Reviewed JNJ regulatory and legal risk context."),

    EvidenceSpec("XOM_ENERGY_MARKET_TRANSITION_RISK_2025_001", "XOM_2025_10K_ITEM1A_BLOCK_0001_CHUNK_0001", "core", "Reviewed ExxonMobil global oil, gas, petrochemical and lower-emission risk overview."),
    EvidenceSpec("XOM_ENERGY_MARKET_TRANSITION_RISK_2025_001", "XOM_2025_10K_ITEM1A_BLOCK_0002_CHUNK_0001", "caveat", "Reviewed ExxonMobil commodity supply risk text."),
    EvidenceSpec("XOM_ENERGY_MARKET_TRANSITION_RISK_2025_001", "XOM_2025_10K_ITEM1A_BLOCK_0004_PART_02_OF_03", "caveat", "Reviewed ExxonMobil lower-emission and climate technology risk text."),
    EvidenceSpec("XOM_ENERGY_MARKET_TRANSITION_RISK_2025_001", "XOM_2025_10K_ITEM1A_BLOCK_0004_PART_03_OF_03", "caveat", "Reviewed ExxonMobil upstream/product-solutions and emerging investment risk text."),

    EvidenceSpec("CVX_UPSTREAM_DOWNSTREAM_COMMODITY_RISK_2025_001", "CVX_2025_10K_ITEM1_BLOCK_0002_CHUNK_0001", "core", "Reviewed Chevron petroleum industry commodity-price text."),
    EvidenceSpec("CVX_UPSTREAM_DOWNSTREAM_COMMODITY_RISK_2025_001", "CVX_2025_10K_ITEM1A_BLOCK_0001_CHUNK_0001", "caveat", "Reviewed Chevron business and operational risk overview."),
    EvidenceSpec("CVX_UPSTREAM_DOWNSTREAM_COMMODITY_RISK_2025_001", "CVX_2025_10K_ITEM1A_BLOCK_0010_PART_02_OF_03", "caveat", "Reviewed Chevron regulation and climate-related risk text."),
    EvidenceSpec("CVX_UPSTREAM_DOWNSTREAM_COMMODITY_RISK_2025_001", "CVX_2025_10K_ITEM1A_BLOCK_0008_PART_02_OF_03", "support", "Reviewed Chevron upstream/downstream segment earnings context."),
]


CAVEAT_CONTEXT = {
    "V_NET_REVENUE_PROCESSED_TRANSACTIONS_2023_2025_001": "Visa processed transactions are an activity metric and must not be treated as revenue or payments volume dollars.",
    "LLY_REVENUE_RND_PIPELINE_INVESTMENT_2023_2025_001": "Eli Lilly research and development expense is investment evidence, not proof of clinical or commercial pipeline success.",
    "CAT_SALES_REVENUES_PROFIT_CYCLE_2023_2025_001": "Caterpillar sales and profit must be interpreted with machinery, construction, mining, energy, transport, and industrial-cycle exposure caveats.",
    "GE_RPO_EQUIPMENT_SERVICES_VISIBILITY_2023_2025_001": "GE RPO is unfilled customer orders or contract visibility and is not the same as recognized revenue.",
    "WMT_NET_SALES_TOTAL_REVENUES_2023_2025_001": "Walmart total revenues should be kept separate from net sales; total revenues include more than merchandise net sales.",
    "PG_NET_SALES_EARNINGS_STAPLES_2023_2025_001": "Procter & Gamble net earnings are not the same as organic growth or category-share gains.",
}


EXPECTED_FACT_COVERAGE: dict[str, set[tuple[str, int, str]]] = {
    "V_NET_REVENUE_PROCESSED_TRANSACTIONS_2023_2025_001": {("V", year, family) for year in [2023, 2024, 2025] for family in ["net_revenue", "processed_transactions"]},
    "LLY_REVENUE_RND_PIPELINE_INVESTMENT_2023_2025_001": {("LLY", year, family) for year in [2023, 2024, 2025] for family in ["revenue", "research_and_development"]},
    "CAT_SALES_REVENUES_PROFIT_CYCLE_2023_2025_001": {("CAT", year, family) for year in [2023, 2024, 2025] for family in ["total_sales_and_revenues", "consolidated_profit_before_taxes"]},
    "GE_RPO_EQUIPMENT_SERVICES_VISIBILITY_2023_2025_001": {("GE", year, family) for year in [2023, 2024, 2025] for family in ["equipment_rpo", "services_rpo", "total_rpo"]},
    "WMT_NET_SALES_TOTAL_REVENUES_2023_2025_001": {("WMT", year, family) for year in [2023, 2024, 2025] for family in ["net_sales", "total_revenues"]},
    "PG_NET_SALES_EARNINGS_STAPLES_2023_2025_001": {("PG", year, family) for year in [2023, 2024, 2025] for family in ["net_sales", "net_earnings"]},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build reviewed-gold assets for SEC benchmark v2 cross-industry10 seed cases.")
    parser.add_argument("--metrics-path", default="data/processed_private/structured_objects/sec_tech_10k_metrics.jsonl")
    parser.add_argument("--evidence-path", default="data/processed_private/evidence_objects/sec_tech_10k_evidence.jsonl")
    parser.add_argument(
        "--approval-path",
        default="reports/quality/sec_benchmark_v2_cross_industry10_review_approval.json",
    )
    parser.add_argument(
        "--build-report-path",
        default="reports/quality/sec_benchmark_v2_cross_industry10_reviewed_gold_build_report.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    REVIEWED_CONTEXT_DIR.mkdir(parents=True, exist_ok=True)
    REVIEWED_FACTS_DIR.mkdir(parents=True, exist_ok=True)
    QUALITY_DIR.mkdir(parents=True, exist_ok=True)

    metrics_by_id = {str(row.get("object_id") or ""): row for row in _read_jsonl(_resolve(args.metrics_path))}
    evidence_by_id = {str(row.get("evidence_id") or ""): row for row in _read_jsonl(_resolve(args.evidence_path))}

    missing_metrics = [spec.object_id for spec in FACT_SPECS if spec.object_id not in metrics_by_id]
    missing_evidence = [spec.evidence_id for spec in EVIDENCE_SPECS if spec.evidence_id not in evidence_by_id]
    if missing_metrics:
        raise SystemExit(f"Missing MetricObject ids: {missing_metrics}")
    if missing_evidence:
        raise SystemExit(f"Missing EvidenceObject ids: {missing_evidence}")

    facts_by_case: dict[str, list[dict[str, Any]]] = {case_id: [] for case_id in CASE_IDS}
    context_by_case: dict[str, list[dict[str, Any]]] = {case_id: [] for case_id in CASE_IDS}

    for spec in FACT_SPECS:
        facts_by_case[spec.case_id].append(_fact_from_spec(spec, metrics_by_id[spec.object_id]))
    for spec in EVIDENCE_SPECS:
        context_by_case[spec.case_id].append(_context_from_evidence(spec, evidence_by_id[spec.evidence_id]))

    case_summaries = []
    for case_id in CASE_IDS:
        facts = _renumber_facts(case_id, facts_by_case[case_id])
        _assert_case_contract(case_id, facts)
        fact_context = [_context_from_fact(case_id, fact, evidence_by_id) for fact in facts]
        context_rows = fact_context + context_by_case[case_id]
        if CAVEAT_CONTEXT.get(case_id):
            ticker = facts[0]["ticker"] if facts else _case_ticker(case_id)
            fiscal_year = max(int(fact.get("fiscal_year") or 0) for fact in facts) if facts else 2025
            context_rows.append(_review_note_context(case_id, ticker, fiscal_year, CAVEAT_CONTEXT[case_id]))
        case_summaries.append(_write_case(case_id, facts, context_rows))

    approval_path = _resolve(args.approval_path)
    build_report_path = _resolve(args.build_report_path)
    _write_approval(approval_path, case_summaries)
    build_report = {
        "schema_version": "sec_v2_cross_industry10_reviewed_gold_build_report_v0.1",
        "reviewed_case_ids": CASE_IDS,
        "case_count": len(CASE_IDS),
        "fact_count": sum(item["fact_count"] for item in case_summaries),
        "context_row_count": sum(item["context_row_count"] for item in case_summaries),
        "text_only_case_ids": [item["case_id"] for item in case_summaries if item["fact_count"] == 0],
        "numeric_case_ids": [item["case_id"] for item in case_summaries if item["fact_count"] > 0],
        "cases": case_summaries,
        "approval_path": str(approval_path.resolve()),
        "source_policy": "SEC_ONLY",
        "metrics_path": str(_resolve(args.metrics_path).resolve()),
        "evidence_path": str(_resolve(args.evidence_path).resolve()),
        "selection_policy": "explicit_reviewed_metric_object_ids_plus_explicit_text_evidence_for_sparse_or_ambiguous_extractors",
    }
    build_report_path.parent.mkdir(parents=True, exist_ok=True)
    build_report_path.write_text(json.dumps(build_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "reviewed_case_count": len(CASE_IDS),
                "fact_count": build_report["fact_count"],
                "context_row_count": build_report["context_row_count"],
                "text_only_case_count": len(build_report["text_only_case_ids"]),
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
    metric_name = spec.metric_name_override or row_label or record.get("metric_name") or spec.metric_family
    case_id = spec.case_id
    metric_id = f"{case_id}::{record['ticker']}::{period}::{spec.metric_family}::{spec.metric_role}"
    return {
        "schema_version": "sec_gold_fact_reviewed_v0.1",
        "case_id": case_id,
        "fact_id": "",
        "review_status": "reviewed_keep",
        "ticker": record.get("ticker"),
        "fiscal_year": int(record["fiscal_year"]),
        "period": period,
        "source_type": "10-K",
        "section": record.get("section"),
        "subsection": record.get("subsection"),
        "source_url": record.get("source_url"),
        "local_path": record.get("local_path"),
        "object_id": record.get("object_id"),
        "source_evidence_id": record.get("source_evidence_id"),
        "metric_id": metric_id,
        "metric_family": spec.metric_family,
        "metric_role": spec.metric_role,
        "metric_name": metric_name,
        "raw_value": record.get("raw_value"),
        "value": value,
        "unit": unit,
        "display_value_en": _display_value_en(value, unit),
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
        "source_url": evidence.get("source_url") or fact.get("source_url"),
        "local_path": evidence.get("local_path") or fact.get("local_path"),
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


def _context_from_evidence(spec: EvidenceSpec, evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "sec_gold_context_reviewed_v0.1",
        "case_id": spec.case_id,
        "review_status": "reviewed_keep",
        "source_kind": "evidence_object",
        "selection_method": "explicit_cross_industry_review",
        "gold_role": spec.gold_role,
        "evidence_id": evidence.get("evidence_id"),
        "source_evidence_id": evidence.get("evidence_id"),
        "ticker": evidence.get("ticker"),
        "fiscal_year": evidence.get("fiscal_year"),
        "source_type": evidence.get("source_type") or "10-K",
        "section": evidence.get("section"),
        "subsection": evidence.get("subsection"),
        "source_url": evidence.get("source_url"),
        "local_path": evidence.get("local_path"),
        "text": evidence.get("text"),
        "text_truncated": evidence.get("text_truncated"),
        "review_note": spec.review_note,
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
        "review_note": "Manual review caveat for cross-industry10 seed promotion.",
    }


def _write_case(case_id: str, facts: list[dict[str, Any]], context_rows: list[dict[str, Any]]) -> dict[str, Any]:
    _write_jsonl(REVIEWED_CONTEXT_DIR / f"{case_id}.jsonl", context_rows)
    payload = {
        "schema_version": "sec_gold_facts_reviewed_v0.1",
        "case_id": case_id,
        "benchmark_version": "sec_benchmark_v2_cross_industry10",
        "review_status": "reviewed_approved_single_case" if facts else "reviewed_approved_text_only_case",
        "review_scope": {
            "source_policy": "SEC_ONLY",
            "allowed_filing_types": ["10-K"],
            "source_basis": "explicit reviewed SEC MetricObjects and EvidenceObjects from local/cloud-synced 30-company build",
            "numeric_fact_policy": "target_numeric_facts_approved" if facts else "no_target_numeric_facts_approved",
            "companies": sorted({str(fact.get("ticker") or "") for fact in facts}) or [_case_ticker(case_id)],
            "years": sorted({int(fact.get("fiscal_year")) for fact in facts}) or [2025],
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
    expected = EXPECTED_FACT_COVERAGE.get(case_id, set())
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
            "case_count": len(CASE_IDS),
            "reviewed_case_ids": CASE_IDS,
        },
        "review_decision": {
            "overall_status": "approved_for_mainline_scored_benchmark",
            "allowed_next_step": "case_filtered_cross_industry10_gold_gate",
            "blocked_next_step": "unfiltered_expanded_benchmark_mainline_scored_test",
            "reason": (
                "The cross-industry10 seed cases are promoted with explicit reviewed SEC facts or text evidence. "
                "Promotion is case-filtered until they are merged into a broader mixed benchmark approval."
            ),
        },
        "case_reviews": [
            {
                "case_id": item["case_id"],
                "decision": "approved_for_gold_context_mode",
                "mainline_status": "can_enter_case_filtered_scored_gold_context_smoke",
                "evidence_assessment": f"Reviewed SEC evidence built for {item['case_id']} with {item['context_row_count']} context rows.",
                "fact_assessment": (
                    f"Reviewed facts contain {item['fact_count']} target facts across {', '.join(item['metric_families'])}."
                    if item["fact_count"]
                    else "Text-only case: no target numeric facts approved because structured metric extraction is sparse or ambiguous."
                ),
                "required_fix": "Before merged benchmark promotion, rerun exact-value ledger, ledger-unit, caveat/claim, and answer-vs-Judgment-Plan gates on the expanded case package.",
            }
            for item in case_summaries
        ],
        "gate": {
            "can_enter_full_mainline_scored_test": False,
            "can_enter_case_filtered_gold_context_scored_smoke": True,
            "approved_case_ids": CASE_IDS,
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _case_ticker(case_id: str) -> str:
    return case_id.split("_", 1)[0]


def _disallowed_roles(metric_family: str) -> list[str]:
    if metric_family.endswith("_rpo") or metric_family == "processed_transactions":
        return ["recognized_revenue", "profitability"]
    if metric_family in {"net_sales", "total_revenues", "net_revenue", "revenue"}:
        return ["market_share", "durable_demand_proof"]
    return ["unsupported_exact_value", "market_share"]


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


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8")


def _resolve(path: str) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else REPO_ROOT / candidate


if __name__ == "__main__":
    main()
