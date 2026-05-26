from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


OUTPUT_MANIFEST = REPO_ROOT / "eval" / "sec_cases" / "test_cases_v2_new20_newco_seed.jsonl"
REPORT_PATH = REPO_ROOT / "reports" / "quality" / "sec_benchmark_v2_new20_newco_seed_design_report.json"

SCORE_WEIGHTS = {"retrieval": 2, "factuality": 3, "coverage": 2, "synthesis": 2, "citation": 1}
YEARS_2023_2025 = [2023, 2024, 2025]
SEC_ONLY = ["SEC"]
FORM_10K = ["10-K"]


def main() -> None:
    cases = [_case_from_spec(spec) for spec in _newco_specs()]
    _assert_contract(cases)
    _write_jsonl(OUTPUT_MANIFEST, cases)

    report = {
        "schema_version": "sec_benchmark_v2_new20_newco_seed_design_report_v0.1",
        "manifest": str(OUTPUT_MANIFEST),
        "case_count": len(cases),
        "company_counts": dict(
            sorted(Counter(company for case in cases for company in case["companies"]).items())
        ),
        "review_status_counts": dict(sorted(Counter(case["reviewed_asset_status"] for case in cases).items())),
        "governance": {
            "decision_label": "proceed_to_newco_seed_readiness_only",
            "allowed_next_step": (
                "run source/index readiness and BM25/ObjectBM25 smoke on the new-company seed cases"
            ),
            "blocked_next_step": (
                "do not claim new-company reviewed-gold benchmark quality until reviewed context, "
                "reviewed facts, approval, exact-value ledger, and ledger-unit gates pass"
            ),
            "reason": (
                "The expanded 20-company corpus exists on cloud, but these new-company cases are design seeds. "
                "They intentionally keep reviewed_asset_status=seed_needs_review until fact/context review is built."
            ),
        },
        "bge_m3_policy": {
            "final_context_selector": "BAAI/bge-reranker-v2-m3",
            "bm25_role": "candidate_generator_only",
            "bm25_only_allowed": False,
        },
        "case_ids": [case["case_id"] for case in cases],
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "manifest": str(OUTPUT_MANIFEST),
                "case_count": len(cases),
                "companies": sorted({company for case in cases for company in case["companies"]}),
                "report_path": str(REPORT_PATH),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def _newco_specs() -> list[dict[str, Any]]:
    return [
        {
            "case_id": "AVGO_PRODUCT_SUBSCRIPTION_REVENUE_MIX_2023_2025_001",
            "company": "AVGO",
            "level": "L3",
            "bucket": "newco_single_company_revenue_mix",
            "task_type": "single_company_product_subscription_revenue_mix",
            "test_objective": (
                "Test Broadcom product revenue versus subscriptions and services revenue after VMware mix shift."
            ),
            "prompt": (
                "Using only Broadcom's fiscal 2023-2025 SEC 10-K filings, compare Products revenue with "
                "Subscriptions and services revenue. Explain how the mix changed and caveat why subscriptions "
                "and services should not be treated as pure ARR or standalone SaaS quality."
            ),
            "gold_points": [
                "Must separate Products from Subscriptions and services revenue.",
                "Must preserve fiscal years and units for all numeric cells.",
                "Must caveat that Subscriptions and services is not automatically ARR or pure SaaS revenue.",
                "Must not use market-share, stock, or non-SEC VMware commentary.",
            ],
            "numeric_checks": [
                _numeric_check(
                    "Products revenue",
                    "AVGO",
                    ["products_revenue"],
                    [{"metric_family": "products_revenue", "metric_role": "total_value", "row_label": "Products"}],
                ),
                _numeric_check(
                    "Subscriptions and services revenue",
                    "AVGO",
                    ["subscription_services_revenue"],
                    [
                        {
                            "metric_family": "subscription_services_revenue",
                            "metric_role": "total_value",
                            "row_label": "Subscriptions and services",
                        }
                    ],
                ),
            ],
            "required_caveats": [
                _caveat(
                    "subscription_services_not_arr",
                    "Must state Subscriptions and services is not the same as ARR unless directly disclosed.",
                    [["Subscriptions and services", "subscriptions"], ["ARR", "SaaS", "recurring"], ["not", "not the same", "不能", "并非"]],
                )
            ],
            "disallowed_claims": [
                _disallowed(
                    "subscription_services_as_arr",
                    "Do not call all Broadcom Subscriptions and services revenue ARR.",
                    ["Broadcom ARR", "Subscriptions and services equals ARR", "subscriptions and services is ARR"],
                )
            ],
        },
        {
            "case_id": "CSCO_PRODUCT_SERVICE_RPO_VISIBILITY_2023_2025_001",
            "company": "CSCO",
            "level": "L3",
            "bucket": "newco_visibility_metric_separation",
            "task_type": "single_company_product_service_rpo_visibility",
            "test_objective": "Test Cisco product/service revenue separation and RPO visibility caveats.",
            "prompt": (
                "Using only Cisco's fiscal 2023-2025 SEC 10-K filings, compare Product revenue, Services "
                "revenue, and remaining performance obligations. Explain what RPO adds and why it is not "
                "recognized revenue."
            ),
            "gold_points": [
                "Must separate Product revenue, Services revenue, and RPO.",
                "Must state RPO is a contracted visibility metric, not recognized revenue.",
                "Must cite every numeric value and preserve fiscal-year units.",
            ],
            "numeric_checks": [
                _numeric_check("Product revenue", "CSCO", ["product_revenue"], [{"metric_family": "product_revenue", "metric_role": "total_value", "row_label": "Product"}]),
                _numeric_check("Services revenue", "CSCO", ["services_revenue"], [{"metric_family": "services_revenue", "metric_role": "total_value", "row_label": "Services"}]),
                _numeric_check("Remaining performance obligations", "CSCO", ["rpo"], [{"metric_family": "rpo", "metric_role": "total_value", "row_label": "Remaining performance obligations"}]),
            ],
            "required_caveats": [
                _caveat("rpo_not_revenue", "Must state RPO is not recognized revenue.", [["RPO", "remaining performance obligations"], ["revenue"], ["not", "not the same", "不能", "并非"]])
            ],
            "disallowed_claims": [
                _disallowed("rpo_equals_revenue", "Do not equate RPO with recognized revenue.", ["RPO is revenue", "RPO equals revenue", "RPO 等同于收入"])
            ],
        },
        {
            "case_id": "INTC_REVENUE_GROSS_PROFIT_FOUNDRY_RISK_2023_2025_001",
            "company": "INTC",
            "level": "L3",
            "bucket": "newco_consolidated_profitability_with_scope_caveat",
            "task_type": "single_company_revenue_gross_profit_foundry_risk",
            "test_objective": "Test Intel consolidated revenue/gross profit trend with Foundry and segment-scope caveats.",
            "prompt": (
                "Using only Intel's fiscal 2023-2025 SEC 10-K filings, summarize consolidated net revenue and "
                "gross profit, then explain the Foundry or manufacturing-cost caveats that limit conclusions "
                "about AI or data-center durability."
            ),
            "gold_points": [
                "Must report consolidated net revenue and gross profit separately.",
                "Must caveat that consolidated gross profit is not exact Intel Foundry profitability.",
                "Must avoid claiming durable AI demand from revenue alone.",
            ],
            "numeric_checks": [
                _numeric_check("Net revenue", "INTC", ["net_revenue"], [{"metric_family": "net_revenue", "metric_role": "total_value", "row_label": "Net revenue"}]),
                _numeric_check("Gross profit", "INTC", ["gross_profit"], [{"metric_family": "gross_profit", "metric_role": "total_value", "row_label": "Gross profit"}]),
            ],
            "required_caveats": [
                _caveat("gross_profit_not_foundry_margin", "Must not treat consolidated gross profit as exact Foundry profitability.", [["gross profit", "毛利"], ["Foundry", "foundry"], ["not", "not exact", "不是", "不能"]])
            ],
            "disallowed_claims": [
                _disallowed("revenue_proves_ai_durability", "Do not claim revenue alone proves durable AI demand.", ["revenue proves durable AI demand", "收入证明 AI 需求耐久"])
            ],
        },
        {
            "case_id": "QCOM_HANDSETS_AUTOMOTIVE_REVENUE_MIX_2023_2025_001",
            "company": "QCOM",
            "level": "L3",
            "bucket": "newco_business_line_mix",
            "task_type": "single_company_handsets_automotive_revenue_mix",
            "test_objective": "Test Qualcomm handset versus automotive revenue mix and scope separation.",
            "prompt": (
                "Using only Qualcomm's fiscal 2023-2025 SEC 10-K filings, compare Handsets revenue and "
                "Automotive revenue. Explain why these business lines should not be treated as total Qualcomm "
                "revenue or as proof of market-share gains."
            ),
            "gold_points": [
                "Must separate Handsets and Automotive revenue.",
                "Must not treat either line as total Qualcomm revenue.",
                "Must not infer market share or installed-base growth without SEC support.",
            ],
            "numeric_checks": [
                _numeric_check("Handsets revenue", "QCOM", ["handsets_revenue"], [{"metric_family": "handsets_revenue", "metric_role": "total_value", "row_label": "Handsets"}]),
                _numeric_check("Automotive revenue", "QCOM", ["automotive_revenue"], [{"metric_family": "automotive_revenue", "metric_role": "total_value", "row_label": "Automotive"}]),
            ],
            "required_caveats": [
                _caveat("business_line_not_total_company", "Must distinguish business-line revenue from total company revenue.", [["Handsets", "Automotive"], ["total", "company", "Qualcomm"], ["not", "separate", "不是", "区分"]])
            ],
            "disallowed_claims": [
                _disallowed("market_share_from_revenue", "Do not infer market share from revenue alone.", ["market share", "市场份额"])
            ],
        },
        {
            "case_id": "TXN_ANALOG_EMBEDDED_REVENUE_MIX_2023_2025_001",
            "company": "TXN",
            "level": "L3",
            "bucket": "newco_semiconductor_segment_mix",
            "task_type": "single_company_analog_embedded_revenue_mix",
            "test_objective": "Test Texas Instruments Analog versus Embedded Processing segment revenue trend.",
            "prompt": (
                "Using only Texas Instruments' fiscal 2023-2025 SEC 10-K filings, compare Analog and Embedded "
                "Processing revenue. Explain the industrial or cyclical-demand caveats that limit conclusions "
                "about durable growth."
            ),
            "gold_points": [
                "Must separate Analog and Embedded Processing revenue.",
                "Must preserve years and units.",
                "Must not equate segment revenue with durable end-market demand without caveat.",
            ],
            "numeric_checks": [
                _numeric_check("Analog revenue", "TXN", ["analog_revenue"], [{"metric_family": "analog_revenue", "metric_role": "total_value", "row_label": "Analog"}]),
                _numeric_check("Embedded Processing revenue", "TXN", ["embedded_processing_revenue"], [{"metric_family": "embedded_processing_revenue", "metric_role": "total_value", "row_label": "Embedded Processing"}]),
            ],
            "required_caveats": [
                _caveat("segment_revenue_not_durable_demand", "Must caveat that segment revenue alone does not prove durable demand.", [["revenue", "收入"], ["durable", "耐久", "demand", "需求"], ["not", "不能", "不证明"]])
            ],
            "disallowed_claims": [
                _disallowed("cycle_ignored", "Do not claim cyclicality is absent from revenue alone.", ["no cyclicality", "周期性不存在"])
            ],
        },
        {
            "case_id": "AMAT_SEMICONDUCTOR_SYSTEMS_SERVICES_REVENUE_MIX_2023_2025_001",
            "company": "AMAT",
            "level": "L3",
            "bucket": "newco_semicap_segment_mix",
            "task_type": "single_company_semicap_systems_services_revenue_mix",
            "test_objective": "Test Applied Materials Semiconductor Systems and Applied Global Services revenue separation.",
            "prompt": (
                "Using only Applied Materials' fiscal 2023-2025 SEC 10-K filings, compare Semiconductor Systems "
                "and Applied Global Services revenue. Explain what this does and does not prove about backlog, "
                "wafer-fab equipment cycle, or service visibility."
            ),
            "gold_points": [
                "Must separate Semiconductor Systems from Applied Global Services.",
                "Must not substitute backlog for recognized revenue.",
                "Must caveat equipment-cycle exposure.",
            ],
            "numeric_checks": [
                _numeric_check("Semiconductor Systems revenue", "AMAT", ["semiconductor_systems_revenue"], [{"metric_family": "semiconductor_systems_revenue", "metric_role": "total_value", "row_label": "Semiconductor Systems"}]),
                _numeric_check("Applied Global Services revenue", "AMAT", ["applied_global_services_revenue"], [{"metric_family": "applied_global_services_revenue", "metric_role": "total_value", "row_label": "Applied Global Services"}]),
            ],
            "required_caveats": [
                _caveat("backlog_not_revenue", "Must not treat backlog or orders as recognized revenue.", [["backlog", "orders", "服务可见性"], ["revenue", "收入"], ["not", "不能", "不同"]])
            ],
            "disallowed_claims": [
                _disallowed("backlog_equals_revenue", "Do not equate backlog with recognized revenue.", ["backlog equals revenue", "backlog is revenue", "订单等同于收入"])
            ],
        },
        {
            "case_id": "MU_DRAM_NAND_REVENUE_CYCLE_2023_2025_001",
            "company": "MU",
            "level": "L3",
            "bucket": "newco_memory_product_mix",
            "task_type": "single_company_dram_nand_revenue_cycle",
            "test_objective": "Test Micron DRAM versus NAND revenue mix and memory-cycle caveats.",
            "prompt": (
                "Using only Micron's fiscal 2023-2025 SEC 10-K filings, compare DRAM and NAND revenue. Explain "
                "the memory-cycle caveats and avoid claiming AI demand durability from revenue alone."
            ),
            "gold_points": [
                "Must separate DRAM and NAND revenue.",
                "Must caveat memory cyclicality.",
                "Must not infer AI demand durability without direct SEC support.",
            ],
            "numeric_checks": [
                _numeric_check("DRAM revenue", "MU", ["dram_revenue"], [{"metric_family": "dram_revenue", "metric_role": "total_value", "row_label": "DRAM"}]),
                _numeric_check("NAND revenue", "MU", ["nand_revenue"], [{"metric_family": "nand_revenue", "metric_role": "total_value", "row_label": "NAND"}]),
            ],
            "required_caveats": [
                _caveat("memory_cycle_caveat", "Must caveat memory-industry cyclicality.", [["memory", "DRAM", "NAND"], ["cycle", "cyclical", "周期"], ["risk", "caveat", "风险", "限制"]])
            ],
            "disallowed_claims": [
                _disallowed("ai_demand_proven", "Do not claim revenue alone proves durable AI demand.", ["revenue proves AI demand", "收入证明 AI 需求"])
            ],
        },
        {
            "case_id": "INTU_SMALL_BUSINESS_CONSUMER_CREDIT_KARMA_MIX_2023_2025_001",
            "company": "INTU",
            "level": "L3",
            "bucket": "newco_software_segment_mix",
            "task_type": "single_company_software_segment_revenue_mix",
            "test_objective": "Test Intuit segment revenue mix and segment-definition separation.",
            "prompt": (
                "Using only Intuit's fiscal 2023-2025 SEC 10-K filings, compare Small Business & Self-Employed, "
                "Consumer, and Credit Karma revenue. Keep the segment definitions separate and caveat why this "
                "does not by itself prove recurring-revenue quality."
            ),
            "gold_points": [
                "Must separate Small Business & Self-Employed, Consumer, and Credit Karma.",
                "Must preserve years and units.",
                "Must not call every segment revenue subscription or ARR.",
            ],
            "numeric_checks": [
                _numeric_check("Small Business & Self-Employed revenue", "INTU", ["small_business_revenue"], [{"metric_family": "small_business_revenue", "metric_role": "total_value", "row_label": "Small Business & Self-Employed"}]),
                _numeric_check("Consumer revenue", "INTU", ["consumer_revenue"], [{"metric_family": "consumer_revenue", "metric_role": "total_value", "row_label": "Consumer"}]),
                _numeric_check("Credit Karma revenue", "INTU", ["credit_karma_revenue"], [{"metric_family": "credit_karma_revenue", "metric_role": "total_value", "row_label": "Credit Karma"}]),
            ],
            "required_caveats": [
                _caveat("segment_revenue_not_arr", "Must not treat all segment revenue as ARR.", [["segment", "Small Business", "Consumer", "Credit Karma"], ["ARR", "subscription", "订阅"], ["not", "不能", "并非"]])
            ],
            "disallowed_claims": [
                _disallowed("all_intuit_revenue_arr", "Do not call all Intuit segment revenue ARR.", ["all Intuit revenue is ARR", "全部是 ARR", "全部是订阅收入"])
            ],
        },
        {
            "case_id": "ADP_EMPLOYER_PEO_REVENUE_CLIENT_FUNDS_2023_2025_001",
            "company": "ADP",
            "level": "L3",
            "bucket": "newco_hcm_segment_revenue_and_client_funds",
            "task_type": "single_company_employer_peo_client_funds_revenue",
            "test_objective": "Test ADP Employer Services, PEO Services, and client-funds interest separation.",
            "prompt": (
                "Using only ADP's fiscal 2023-2025 SEC 10-K filings, compare Employer Services revenue, PEO "
                "Services revenue, and interest on funds held for clients. Explain why client-funds interest "
                "should be separated from core service revenue."
            ),
            "gold_points": [
                "Must separate Employer Services and PEO Services.",
                "Must separate interest on funds held for clients from service revenue.",
                "Must preserve fiscal years and units.",
            ],
            "numeric_checks": [
                _numeric_check("Employer Services revenue", "ADP", ["employer_services_revenue"], [{"metric_family": "employer_services_revenue", "metric_role": "total_value", "row_label": "Employer Services"}]),
                _numeric_check("PEO Services revenue", "ADP", ["peo_services_revenue"], [{"metric_family": "peo_services_revenue", "metric_role": "total_value", "row_label": "PEO Services"}]),
                _numeric_check("Interest on funds held for clients", "ADP", ["client_funds_interest"], [{"metric_family": "client_funds_interest", "metric_role": "total_value", "row_label": "Interest on funds held for clients"}]),
            ],
            "required_caveats": [
                _caveat("client_funds_interest_separate", "Must separate client-funds interest from core service revenue.", [["interest on funds", "client funds"], ["revenue", "service"], ["separate", "not", "区分", "不能"]])
            ],
            "disallowed_claims": [
                _disallowed("client_interest_core_subscription", "Do not treat client-funds interest as subscription revenue.", ["client funds interest is subscription revenue", "客户资金利息是订阅收入"])
            ],
        },
        {
            "case_id": "CRWD_ARR_SUBSCRIPTION_GROSS_PROFIT_2023_2025_001",
            "company": "CRWD",
            "level": "L3",
            "bucket": "newco_cybersecurity_arr_profitability",
            "task_type": "single_company_arr_subscription_gross_profit",
            "test_objective": "Test CrowdStrike ARR versus subscription gross profit and revenue-quality caveats.",
            "prompt": (
                "Using only CrowdStrike's fiscal 2023-2025 SEC 10-K filings, compare Annual recurring revenue "
                "and subscription gross profit. Explain why ARR is a visibility metric and not the same as "
                "recognized revenue or gross profit."
            ),
            "gold_points": [
                "Must separate ARR from subscription gross profit.",
                "Must state ARR is not recognized revenue.",
                "Must cite all numeric values and preserve fiscal-year units.",
            ],
            "numeric_checks": [
                _numeric_check("Annual recurring revenue", "CRWD", ["arr"], [{"metric_family": "arr", "metric_role": "total_value", "row_label": "Annual recurring revenue"}]),
                _numeric_check("Subscription gross profit", "CRWD", ["subscription_gross_profit"], [{"metric_family": "subscription_gross_profit", "metric_role": "total_value", "row_label": "Subscription gross profit"}]),
            ],
            "required_caveats": [
                _caveat("arr_not_revenue_or_profit", "Must state ARR is not recognized revenue or gross profit.", [["ARR", "Annual recurring revenue"], ["revenue", "gross profit"], ["not", "not the same", "不能", "不同"]])
            ],
            "disallowed_claims": [
                _disallowed("arr_equals_revenue", "Do not equate ARR with recognized revenue.", ["ARR is revenue", "ARR equals revenue", "ARR 等同于收入"])
            ],
        },
    ]


def _case_from_spec(spec: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "sec_eval_case_v1",
        "benchmark_version": "sec_benchmark_v1",
        "case_id": spec["case_id"],
        "origin": "v2_new20_newco_reviewed_gold_design_seed",
        "case_family": "v2_new20_newco_seed",
        "newco_bucket": spec["bucket"],
        "full40_inclusion_role": "new_company_seed_case",
        "reviewed_asset_status": "seed_needs_review",
        "test_objective": spec["test_objective"],
        "case_group": "formal_seed",
        "level": spec["level"],
        "companies": [spec["company"]],
        "years": YEARS_2023_2025,
        "filing_types": FORM_10K,
        "task_type": spec["task_type"],
        "prompt": spec["prompt"],
        "allowed_sources": SEC_ONLY,
        "source_policy": "SEC_ONLY",
        "evaluation_modes": ["gold_context", "pipeline_context"],
        "expected_sections": [
            "Item 1. Business",
            "Item 7. Management's Discussion and Analysis",
            "Item 8. Financial Statements",
        ],
        "gold_points": spec["gold_points"],
        "numeric_checks": spec["numeric_checks"],
        "required_caveats": spec["required_caveats"],
        "disallowed_claims": spec["disallowed_claims"],
        "hard_gates": [
            "source_resolver",
            "citation_validator",
            "exact_value_ledger",
            "metric_family_context_gate",
            "unsupported_claim_gate",
            "caveat_claim_gate",
        ],
        "hallucination_traps": [
            "Use SEC evidence only.",
            "Do not invent undisclosed exact values.",
            "Do not substitute peer-company, segment, visibility, or broader-scope metrics for the requested metric.",
        ],
        "failure_types": [
            "retrieval_miss",
            "numeric_error",
            "unit_error",
            "metric_role_error",
            "proxy_as_direct_metric",
            "unsupported_claim",
            "missing_caveat",
        ],
        "score_weights": SCORE_WEIGHTS,
        "gold_context_status": "needs_annotation",
    }


def _numeric_check(
    metric: str,
    company: str,
    metric_families: list[str],
    expected_facts: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "metric": metric,
        "metric_families": metric_families,
        "metric_roles": ["total_value"],
        "companies": [company],
        "years": YEARS_2023_2025,
        "expected_facts": expected_facts,
    }


def _caveat(caveat_id: str, description: str, all_of_any: list[list[str]]) -> dict[str, Any]:
    return {
        "id": caveat_id,
        "description": description,
        "where": "answer",
        "all_of_any": all_of_any,
    }


def _disallowed(claim_id: str, description: str, patterns: list[str]) -> dict[str, Any]:
    return {
        "id": claim_id,
        "description": description,
        "patterns": patterns,
        "allow_if_any_near": ["not", "not disclosed", "not the same", "cannot", "不能", "未披露", "不同"],
    }


def _assert_contract(cases: list[dict[str, Any]]) -> None:
    case_ids = [case["case_id"] for case in cases]
    duplicates = sorted(case_id for case_id, count in Counter(case_ids).items() if count > 1)
    if duplicates:
        raise SystemExit(f"Duplicate case ids: {duplicates}")
    if len(cases) != 10:
        raise SystemExit(f"Expected 10 new-company cases, got {len(cases)}")
    companies = sorted(company for case in cases for company in case["companies"])
    expected = ["ADP", "AMAT", "AVGO", "CRWD", "CSCO", "INTC", "INTU", "MU", "QCOM", "TXN"]
    if companies != expected:
        raise SystemExit(f"Unexpected company coverage: {companies}")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
