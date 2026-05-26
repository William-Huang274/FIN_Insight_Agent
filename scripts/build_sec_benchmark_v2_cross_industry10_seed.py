from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


OUTPUT_MANIFEST = REPO_ROOT / "eval" / "sec_cases" / "test_cases_v2_cross_industry10_seed.jsonl"
REPORT_PATH = REPO_ROOT / "reports" / "quality" / "sec_benchmark_v2_cross_industry10_seed_design_report.json"

SCORE_WEIGHTS = {"retrieval": 2, "factuality": 3, "coverage": 2, "synthesis": 2, "citation": 1}
YEARS_2023_2025 = [2023, 2024, 2025]
SEC_ONLY = ["SEC"]
FORM_10K = ["10-K"]


def main() -> None:
    cases = [_case_from_spec(spec) for spec in _cross_industry_specs()]
    _assert_contract(cases)
    _write_jsonl(OUTPUT_MANIFEST, cases)

    report = {
        "schema_version": "sec_benchmark_v2_cross_industry10_seed_design_report_v0.1",
        "manifest": str(OUTPUT_MANIFEST),
        "case_count": len(cases),
        "company_counts": dict(
            sorted(Counter(company for case in cases for company in case["companies"]).items())
        ),
        "review_status_counts": dict(sorted(Counter(case["reviewed_asset_status"] for case in cases).items())),
        "governance": {
            "decision_label": "proceed_to_reviewed_gold_gate_only",
            "hypothesis": (
                "The BGE-M3 + Judgment Plan + Qwen9B route should remain stable on a broader SEC disclosure "
                "surface when cases separate strict numeric tasks from text-only scope/risk tasks."
            ),
            "decision_target": (
                "After reviewed-gold and ledger gates pass, cloud pipeline inference should maintain "
                "qwen_answer_ratio=1.0 and deterministic post-gates green on the cross-industry slice."
            ),
            "blocked_next_step": (
                "Do not claim cross-industry pipeline quality until reviewed context, reviewed facts, "
                "exact-value ledger, ledger-unit, Judgment Plan, and cloud post-gates pass."
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


def _cross_industry_specs() -> list[dict[str, Any]]:
    return [
        {
            "case_id": "JPM_BANK_SEGMENTS_RATE_CREDIT_RISK_2025_001",
            "company": "JPM",
            "years": [2025],
            "level": "L2",
            "bucket": "banking_text_risk_scope",
            "task_type": "single_company_bank_segments_rate_credit_risk_summary",
            "test_objective": "Test bank segment scope, rate sensitivity, credit, and liquidity caveats without fragile numeric extraction.",
            "prompt": (
                "Using only JPMorgan Chase's fiscal 2025 Form 10-K, summarize its reportable business segments "
                "and explain how interest-rate, credit, liquidity, and capital risks constrain interpretation of "
                "bank earnings quality. Do not invent exact segment values."
            ),
            "gold_points": [
                "Must identify the bank reportable-segment scope from SEC text.",
                "Must discuss interest-rate, credit, liquidity, and capital caveats.",
                "Must not invent exact segment revenue, net interest income, CET1, or credit-loss values.",
            ],
            "numeric_checks": [],
            "required_caveats": [
                _caveat("bank_risk_scope", "Must include rate, credit, liquidity, or capital risk caveats.", [["interest rate", "rate"], ["credit", "liquidity", "capital"]]),
                _caveat("no_exact_bank_values", "Must not present exact bank metrics unless disclosed in scoped evidence.", [["not disclosed", "not quantified", "without exact", "not enough"]], required=False),
            ],
            "disallowed_claims": [
                _disallowed("invented_bank_exact_values", "Do not invent exact bank segment values.", ["CET1 ratio was", "net interest income was", "credit losses were"]),
            ],
        },
        {
            "case_id": "V_NET_REVENUE_PROCESSED_TRANSACTIONS_2023_2025_001",
            "company": "V",
            "years": YEARS_2023_2025,
            "level": "L3",
            "bucket": "payments_revenue_and_activity",
            "task_type": "single_company_payments_revenue_processed_transactions",
            "test_objective": "Test payments-network revenue and activity metric separation.",
            "prompt": (
                "Using only Visa's fiscal 2023-2025 SEC 10-K filings, compare net revenue with Visa processed "
                "transactions. Explain why processed transactions are an activity metric rather than revenue."
            ),
            "gold_points": [
                "Must separate net revenue from Visa processed transactions.",
                "Must preserve fiscal years and units.",
                "Must state processed transactions are not revenue or payment volume dollars.",
            ],
            "numeric_checks": [
                _numeric_check("Net revenue", "V", ["net_revenue"], [{"metric_family": "net_revenue", "metric_role": "total_value", "row_label": "Net revenues"}]),
                _numeric_check("Visa processed transactions", "V", ["processed_transactions"], [{"metric_family": "processed_transactions", "metric_role": "total_value", "row_label": "Visa processed transactions"}]),
            ],
            "required_caveats": [
                _caveat("transactions_not_revenue", "Must state processed transactions are not revenue.", [["processed transactions"], ["revenue"], ["not", "not the same", "different"]])
            ],
            "disallowed_claims": [
                _disallowed("processed_transactions_as_revenue", "Do not call processed transactions revenue.", ["processed transactions revenue", "transactions are revenue"]),
            ],
        },
        {
            "case_id": "JNJ_INNOVATIVE_MEDICINE_MEDTECH_SCOPE_2025_001",
            "company": "JNJ",
            "years": [2025],
            "level": "L2",
            "bucket": "healthcare_segment_text_scope",
            "task_type": "single_company_healthcare_segment_scope_summary",
            "test_objective": "Test healthcare/pharma/device segment scope and regulatory caveats without ambiguous duplicate numeric rows.",
            "prompt": (
                "Using only Johnson & Johnson's fiscal 2025 Form 10-K, summarize the roles of Innovative "
                "Medicine and MedTech, and explain the regulatory, litigation, product, or R&D caveats that "
                "limit a simple quality conclusion. Do not invent exact segment values."
            ),
            "gold_points": [
                "Must keep Innovative Medicine and MedTech separate.",
                "Must mention regulatory, litigation, product, or R&D caveats if supported.",
                "Must not invent exact segment sales or margin values.",
            ],
            "numeric_checks": [],
            "required_caveats": [
                _caveat("healthcare_regulatory_risk", "Must include regulatory, litigation, product, or R&D caveats.", [["regulatory", "litigation", "R&D", "product"], ["risk", "caveat", "limit"]])
            ],
            "disallowed_claims": [
                _disallowed("invented_jnj_segment_values", "Do not invent exact JNJ segment values.", ["Innovative Medicine sales were", "MedTech sales were"]),
            ],
        },
        {
            "case_id": "LLY_REVENUE_RND_PIPELINE_INVESTMENT_2023_2025_001",
            "company": "LLY",
            "years": YEARS_2023_2025,
            "level": "L3",
            "bucket": "pharma_revenue_rnd",
            "task_type": "single_company_pharma_revenue_rnd_investment",
            "test_objective": "Test pharma revenue and R&D spending separation with pipeline-success caveats.",
            "prompt": (
                "Using only Eli Lilly's fiscal 2023-2025 SEC 10-K filings, compare revenue with research and "
                "development expense. Explain why R&D spending is not proof of pipeline success."
            ),
            "gold_points": [
                "Must report revenue and research and development expense separately.",
                "Must preserve years and units.",
                "Must caveat that R&D spend is not proof of clinical or commercial pipeline success.",
            ],
            "numeric_checks": [
                _numeric_check("Revenue", "LLY", ["revenue"], [{"metric_family": "revenue", "metric_role": "total_value", "row_label": "Revenue"}]),
                _numeric_check("Research and development", "LLY", ["research_and_development"], [{"metric_family": "research_and_development", "metric_role": "total_value", "row_label": "Research and development"}]),
            ],
            "required_caveats": [
                _caveat("rnd_not_pipeline_success", "Must state R&D spending does not prove pipeline success.", [["Research and development", "R&D"], ["pipeline", "success"], ["not", "not proof", "does not prove"]])
            ],
            "disallowed_claims": [
                _disallowed("rnd_proves_pipeline", "Do not claim R&D spend proves pipeline success.", ["R&D proves pipeline success", "research and development proves success"]),
            ],
        },
        {
            "case_id": "CAT_SALES_REVENUES_PROFIT_CYCLE_2023_2025_001",
            "company": "CAT",
            "years": YEARS_2023_2025,
            "level": "L3",
            "bucket": "industrial_sales_profit_cycle",
            "task_type": "single_company_industrial_sales_profit_cycle",
            "test_objective": "Test industrial revenue/profit trend with machinery-cycle caveats.",
            "prompt": (
                "Using only Caterpillar's fiscal 2023-2025 SEC 10-K filings, compare total sales and revenues "
                "with consolidated profit before taxes. Explain why industrial-cycle exposure limits a simple "
                "durability conclusion."
            ),
            "gold_points": [
                "Must separate total sales and revenues from consolidated profit before taxes.",
                "Must preserve years and units.",
                "Must caveat industrial-cycle exposure.",
            ],
            "numeric_checks": [
                _numeric_check("Total sales and revenues", "CAT", ["total_sales_and_revenues"], [{"metric_family": "total_sales_and_revenues", "metric_role": "total_value", "row_label": "Total sales and revenues"}]),
                _numeric_check("Consolidated profit before taxes", "CAT", ["consolidated_profit_before_taxes"], [{"metric_family": "consolidated_profit_before_taxes", "metric_role": "total_value", "row_label": "Consolidated profit before taxes"}]),
            ],
            "required_caveats": [
                _caveat("industrial_cycle_caveat", "Must caveat industrial or equipment-cycle exposure.", [["cycle", "cyclical", "industrial", "equipment"], ["risk", "caveat", "exposure"]])
            ],
            "disallowed_claims": [
                _disallowed("profit_proves_durability", "Do not claim profit alone proves durable demand.", ["profit proves durable demand", "sales prove durability"]),
            ],
        },
        {
            "case_id": "GE_RPO_EQUIPMENT_SERVICES_VISIBILITY_2023_2025_001",
            "company": "GE",
            "years": YEARS_2023_2025,
            "level": "L3",
            "bucket": "aerospace_rpo_visibility",
            "task_type": "single_company_aerospace_rpo_equipment_services",
            "test_objective": "Test aerospace RPO equipment/services separation and RPO caveats.",
            "prompt": (
                "Using only GE's fiscal 2023-2025 SEC 10-K filings, compare equipment RPO, services RPO, "
                "and total RPO. Explain why RPO is backlog/contract visibility and not recognized revenue."
            ),
            "gold_points": [
                "Must separate equipment, services, and total RPO.",
                "Must preserve years and units.",
                "Must state RPO is not recognized revenue.",
            ],
            "numeric_checks": [
                _numeric_check("Equipment RPO", "GE", ["equipment_rpo"], [{"metric_family": "equipment_rpo", "metric_role": "total_value", "row_label": "Equipment"}]),
                _numeric_check("Services RPO", "GE", ["services_rpo"], [{"metric_family": "services_rpo", "metric_role": "total_value", "row_label": "Services"}]),
                _numeric_check("Total RPO", "GE", ["total_rpo"], [{"metric_family": "total_rpo", "metric_role": "total_value", "row_label": "Total RPO"}]),
            ],
            "required_caveats": [
                _caveat("rpo_not_revenue", "Must state RPO is not recognized revenue.", [["RPO"], ["revenue"], ["not", "not the same", "different"]])
            ],
            "disallowed_claims": [
                _disallowed("rpo_equals_revenue", "Do not equate RPO with revenue.", ["RPO is revenue", "RPO equals revenue"]),
            ],
        },
        {
            "case_id": "WMT_NET_SALES_TOTAL_REVENUES_2023_2025_001",
            "company": "WMT",
            "years": YEARS_2023_2025,
            "level": "L3",
            "bucket": "retail_revenue_composition",
            "task_type": "single_company_retail_net_sales_total_revenue",
            "test_objective": "Test retail net sales versus total revenues separation.",
            "prompt": (
                "Using only Walmart's fiscal 2023-2025 SEC 10-K filings, compare net sales with total revenues. "
                "Explain why total revenues should not be treated as only merchandise net sales."
            ),
            "gold_points": [
                "Must separate net sales and total revenues.",
                "Must preserve fiscal years and units.",
                "Must caveat that total revenues include more than net sales.",
            ],
            "numeric_checks": [
                _numeric_check("Net sales", "WMT", ["net_sales"], [{"metric_family": "net_sales", "metric_role": "total_value", "row_label": "Net sales"}]),
                _numeric_check("Total revenues", "WMT", ["total_revenues"], [{"metric_family": "total_revenues", "metric_role": "total_value", "row_label": "Total revenues"}]),
            ],
            "required_caveats": [
                _caveat("total_revenue_not_only_net_sales", "Must state total revenues are not only net sales.", [["Total revenues"], ["net sales"], ["not", "more than", "different"]])
            ],
            "disallowed_claims": [
                _disallowed("total_revenue_equals_net_sales", "Do not equate total revenues with net sales.", ["total revenues equal net sales", "total revenues are net sales"]),
            ],
        },
        {
            "case_id": "PG_NET_SALES_EARNINGS_STAPLES_2023_2025_001",
            "company": "PG",
            "years": YEARS_2023_2025,
            "level": "L3",
            "bucket": "consumer_staples_sales_earnings",
            "task_type": "single_company_consumer_staples_sales_earnings",
            "test_objective": "Test consumer-staples net sales and earnings separation.",
            "prompt": (
                "Using only Procter & Gamble's fiscal 2023-2025 SEC 10-K filings, compare net sales and net "
                "earnings. Explain why earnings trend alone is not the same as organic growth or category share."
            ),
            "gold_points": [
                "Must separate net sales and net earnings.",
                "Must preserve years and units.",
                "Must not infer organic growth or share gains from earnings alone.",
            ],
            "numeric_checks": [
                _numeric_check("Net sales", "PG", ["net_sales"], [{"metric_family": "net_sales", "metric_role": "total_value", "row_label": "Net sales"}]),
                _numeric_check("Net earnings", "PG", ["net_earnings"], [{"metric_family": "net_earnings", "metric_role": "total_value", "row_label": "Net earnings"}]),
            ],
            "required_caveats": [
                _caveat("earnings_not_organic_growth", "Must not treat earnings as organic growth or share gains.", [["earnings"], ["organic growth", "share", "market share"], ["not", "not the same", "cannot"]])
            ],
            "disallowed_claims": [
                _disallowed("earnings_proves_share_gain", "Do not infer share gains from earnings alone.", ["earnings prove share gains", "net earnings prove market share"]),
            ],
        },
        {
            "case_id": "XOM_ENERGY_MARKET_TRANSITION_RISK_2025_001",
            "company": "XOM",
            "years": [2025],
            "level": "L2",
            "bucket": "energy_text_market_transition",
            "task_type": "single_company_energy_market_transition_risk_summary",
            "test_objective": "Test energy commodity, lower-emission, and transition-risk reasoning where structured numeric extraction is sparse.",
            "prompt": (
                "Using only ExxonMobil's fiscal 2025 Form 10-K, summarize the commodity-market and lower-emission "
                "or transition risks that shape interpretation of its business quality. Do not invent exact segment values."
            ),
            "gold_points": [
                "Must discuss commodity-price or supply/demand exposure.",
                "Must discuss lower-emission or transition-risk limits if supported.",
                "Must not invent exact segment or low-carbon revenue values.",
            ],
            "numeric_checks": [],
            "required_caveats": [
                _caveat("commodity_transition_risk", "Must include commodity and transition/lower-emission caveats.", [["commodity", "supply", "demand"], ["lower-emission", "transition", "climate"]])
            ],
            "disallowed_claims": [
                _disallowed("invented_xom_low_carbon_values", "Do not invent low-carbon or segment values.", ["Low Carbon Solutions revenue was", "upstream revenue was"]),
            ],
        },
        {
            "case_id": "CVX_UPSTREAM_DOWNSTREAM_COMMODITY_RISK_2025_001",
            "company": "CVX",
            "years": [2025],
            "level": "L2",
            "bucket": "energy_text_upstream_downstream",
            "task_type": "single_company_energy_upstream_downstream_risk_summary",
            "test_objective": "Test Chevron upstream/downstream scope and commodity-risk caveats without duplicate revenue rows.",
            "prompt": (
                "Using only Chevron's fiscal 2025 Form 10-K, summarize upstream and downstream business exposure "
                "and explain how commodity prices, regulation, and lower-carbon transition issues constrain a simple "
                "quality conclusion. Do not invent exact segment values."
            ),
            "gold_points": [
                "Must separate upstream and downstream exposure.",
                "Must discuss commodity prices, regulation, or lower-carbon transition caveats.",
                "Must not invent exact segment revenue or earnings values.",
            ],
            "numeric_checks": [],
            "required_caveats": [
                _caveat("commodity_regulatory_transition_risk", "Must include commodity, regulatory, or lower-carbon caveats.", [["commodity", "prices"], ["regulation", "lower-carbon", "transition", "climate"]])
            ],
            "disallowed_claims": [
                _disallowed("invented_cvx_segment_values", "Do not invent exact Chevron segment values.", ["upstream earnings were", "downstream revenue was"]),
            ],
        },
    ]


def _case_from_spec(spec: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "sec_eval_case_v1",
        "benchmark_version": "sec_benchmark_v2_cross_industry10",
        "case_id": spec["case_id"],
        "origin": "v2_cross_industry10_reviewed_gold_design_seed",
        "case_family": "v2_cross_industry10_seed",
        "cross_industry_bucket": spec["bucket"],
        "reviewed_asset_status": "seed_needs_review",
        "test_objective": spec["test_objective"],
        "case_group": "formal_seed",
        "level": spec["level"],
        "companies": [spec["company"]],
        "years": spec["years"],
        "filing_types": FORM_10K,
        "task_type": spec["task_type"],
        "prompt": spec["prompt"],
        "allowed_sources": SEC_ONLY,
        "source_policy": "SEC_ONLY",
        "evaluation_modes": ["gold_context", "pipeline_context"],
        "expected_sections": [
            "Item 1. Business",
            "Item 1A. Risk Factors",
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


def _caveat(caveat_id: str, description: str, all_of_any: list[list[str]], required: bool = True) -> dict[str, Any]:
    payload = {
        "id": caveat_id,
        "description": description,
        "where": "answer",
        "all_of_any": all_of_any,
    }
    if not required:
        payload["required"] = False
    return payload


def _disallowed(claim_id: str, description: str, patterns: list[str]) -> dict[str, Any]:
    return {
        "id": claim_id,
        "description": description,
        "patterns": patterns,
        "allow_if_any_near": ["not", "not disclosed", "not the same", "cannot", "without exact", "no SEC support"],
    }


def _assert_contract(cases: list[dict[str, Any]]) -> None:
    case_ids = [case["case_id"] for case in cases]
    duplicates = sorted(case_id for case_id, count in Counter(case_ids).items() if count > 1)
    if duplicates:
        raise SystemExit(f"Duplicate case ids: {duplicates}")
    if len(cases) != 10:
        raise SystemExit(f"Expected 10 cross-industry cases, got {len(cases)}")
    companies = sorted(company for case in cases for company in case["companies"])
    expected = ["CAT", "CVX", "GE", "JNJ", "JPM", "LLY", "PG", "V", "WMT", "XOM"]
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
