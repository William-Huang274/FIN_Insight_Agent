from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


PLUS8_MANIFEST = REPO_ROOT / "eval" / "sec_cases" / "test_cases_v2_pilot_plus8_seed.jsonl"
SOURCE_MANIFESTS = [
    REPO_ROOT / "eval" / "sec_cases" / "test_cases_v1_1_gold_expansion.jsonl",
    REPO_ROOT / "eval" / "sec_cases" / "test_cases_v1.jsonl",
]
FULL40_MANIFEST = REPO_ROOT / "eval" / "sec_cases" / "test_cases_v2_full40_seed.jsonl"
REPORT_PATH = REPO_ROOT / "reports" / "quality" / "sec_benchmark_v2_full40_seed_build_report.json"

REVIEWED_CONTEXT_DIR = REPO_ROOT / "eval" / "sec_cases" / "reviewed_gold_context"
REVIEWED_FACTS_DIR = REPO_ROOT / "eval" / "sec_cases" / "reviewed_gold_facts"

BUCKET_L2 = "l2_single_company_single_year_summary"
BUCKET_L3 = "l3_single_company_cross_year_trend"
BUCKET_NUMERIC = "numeric_table_cell_gold"
BUCKET_L4 = "l4_two_company_peer_comparison"
BUCKET_TRAP = "trap_not_found_source_policy"

TARGET_BUCKET_COUNTS = {
    BUCKET_L2: 8,
    BUCKET_L3: 10,
    BUCKET_NUMERIC: 10,
    BUCKET_L4: 6,
    BUCKET_TRAP: 6,
}

PLUS8_BUCKETS = {
    "META_REALITY_LABS_2024_001": BUCKET_L2,
    "PANW_RPO_BILLINGS_NUMERIC_2023_2025_001": BUCKET_NUMERIC,
    "GOOGL_META_ADS_REGULATION_PRIVACY_2023_2025_001": BUCKET_L4,
    "AAPL_PRODUCT_SERVICES_REVENUE_GM_2023_2025_001": BUCKET_NUMERIC,
    "AMD_SEGMENT_MIX_2023_2025_001": BUCKET_L3,
    "MSFT_YOUTUBE_REVENUE_TRAP_001": BUCKET_TRAP,
    "ADBE_DIGITAL_MEDIA_ARR_REVENUE_GROWTH_2023_2025_001": BUCKET_L3,
    "GOOGL_META_ADS_AI_INFRA_LOCAL_SUPPORT_2023_2025_001": BUCKET_L4,
    "SNOW_NRR_RPO_GROWTH_2023_2025_001": BUCKET_NUMERIC,
    "AMZN_AWS_NUMERIC_2023_2025_001": BUCKET_NUMERIC,
    "AMZN_GOOGL_CLOUD_PROFITABILITY_COMPARISON_2023_2025_001": BUCKET_L4,
    "MSFT_CLOUD_AI_MARGIN_PROXY_2023_2025_001": BUCKET_L3,
    "MSFT_AZURE_GROSS_MARGIN_NOT_FOUND_2023_2025_001": BUCKET_TRAP,
    "NVDA_DATACENTER_2023_2025_001": BUCKET_L3,
    "SNOW_RISK_2023_2025_001": BUCKET_L3,
}

PROMOTED_LEGACY_BUCKETS = {
    "AAPL_SERVICES_MARGIN_2023_2025_001": BUCKET_NUMERIC,
    "ADS_AI_INFRA_GROWTH_QUALITY_2023_2025_DIAG_001": BUCKET_L4,
    "CAPEX_FCF_TABLE_2023_2025_DIAG_001": BUCKET_NUMERIC,
    "GOOGL_CLOUD_CONTEXT_ROLE_2025_001": BUCKET_L2,
    "MSFT_AI_CLOUD_2023_2025_001": BUCKET_L3,
    "PANW_SUBSCRIPTION_VISIBILITY_2023_2025_001": BUCKET_L3,
    "REVENUE_INCOME_CFO_TABLE_2023_2025_DIAG_001": BUCKET_NUMERIC,
    "SEMICONDUCTOR_DURABILITY_2023_2025_DIAG_001": BUCKET_L4,
    "SUBSCRIPTION_VISIBILITY_COMPARISON_2023_2025_DIAG_001": BUCKET_L4,
}

DEFERRED_REVIEWED_CASE_IDS = {
    "CLOUD_PROFITABILITY_2023_2025_DIAG_001": (
        "deferred because the broad AMZN/GOOGL/MSFT cloud comparison has known disclosure asymmetry; "
        "plus8 already uses the safer AMZN/GOOGL comparable case plus the MSFT proxy case"
    ),
    "PLATFORM_RECURRING_QUALITY_2023_2025_DIAG_001": (
        "deferred because the 3-company recurring-quality comparison mixes platform and SaaS disclosure "
        "definitions and needs a narrower split before full-v2 promotion"
    ),
}

EXISTING_TRAP_CASE_IDS = ["AAPL_AWS_TRAP_001", "META_LLAMA_COST_TRAP_001"]

SCORE_WEIGHTS = {"retrieval": 2, "factuality": 3, "coverage": 2, "synthesis": 2, "citation": 1}
YEARS_2023_2025 = [2023, 2024, 2025]
FORM_10K = ["10-K"]
SEC_ONLY = ["SEC"]


def main() -> None:
    source_by_id = _source_case_map()
    rows: list[dict[str, Any]] = []

    for row in _read_jsonl(PLUS8_MANIFEST):
        case_id = str(row.get("case_id") or "")
        rows.append(
            _upgrade_existing_case(
                row,
                bucket=PLUS8_BUCKETS[case_id],
                origin="v2_full40_seed_from_plus8_freeze",
                inclusion_role="plus8_frozen_mvp_case",
            )
        )

    for case_id, bucket in PROMOTED_LEGACY_BUCKETS.items():
        rows.append(
            _upgrade_existing_case(
                source_by_id[case_id],
                bucket=bucket,
                origin="v2_full40_seed_promoted_legacy_reviewed",
                inclusion_role="legacy_reviewed_gold_case",
            )
        )

    for case_id in EXISTING_TRAP_CASE_IDS:
        rows.append(
            _upgrade_existing_case(
                source_by_id[case_id],
                bucket=BUCKET_TRAP,
                origin="v2_full40_seed_existing_trap",
                inclusion_role="legacy_pipeline_trap",
            )
        )

    rows.extend(_new_seed_cases())

    _assert_manifest_contract(rows)
    _write_jsonl(FULL40_MANIFEST, rows)
    report = _build_report(rows)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "manifest": str(FULL40_MANIFEST),
                "case_count": len(rows),
                "bucket_counts": report["bucket_counts"],
                "review_status_counts": report["review_status_counts"],
                "deferred_reviewed_case_ids": report["deferred_reviewed_case_ids"],
                "report_path": str(REPORT_PATH),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def _source_case_map() -> dict[str, dict[str, Any]]:
    output = {str(row.get("case_id") or ""): row for row in _read_jsonl(PLUS8_MANIFEST)}
    for path in SOURCE_MANIFESTS:
        for row in _read_jsonl(path):
            output.setdefault(str(row.get("case_id") or ""), row)
    return output


def _upgrade_existing_case(row: dict[str, Any], *, bucket: str, origin: str, inclusion_role: str) -> dict[str, Any]:
    case = dict(row)
    case_id = str(case.get("case_id") or "")
    patch = LEGACY_POLICY_PATCHES.get(case_id, {})
    case.update(
        {
            "origin": origin,
            "case_family": "v2_full40_seed",
            "full40_bucket": bucket,
            "full40_inclusion_role": inclusion_role,
            "reviewed_asset_status": _reviewed_asset_status(case),
        }
    )
    if patch.get("test_objective"):
        case["test_objective"] = patch["test_objective"]
    elif not case.get("test_objective"):
        case["test_objective"] = f"Full40 coverage case for {case_id}."
    if patch.get("prompt"):
        case["prompt"] = patch["prompt"]
    if patch.get("gold_points"):
        case["gold_points"] = patch["gold_points"]
    if not case.get("required_caveats"):
        case["required_caveats"] = patch.get("required_caveats") or _generic_required_caveats(case)
    if not case.get("disallowed_claims"):
        case["disallowed_claims"] = patch.get("disallowed_claims") or _generic_disallowed_claims(case)
    if patch.get("required_not_found"):
        case["required_not_found"] = patch["required_not_found"]
    case["hard_gates"] = _dedupe([*(case.get("hard_gates") or []), *(patch.get("hard_gates") or [])])
    case["failure_types"] = _dedupe([*(case.get("failure_types") or []), *(patch.get("failure_types") or [])])
    case["score_weights"] = dict(case.get("score_weights") or SCORE_WEIGHTS)
    return case


def _new_seed_cases() -> list[dict[str, Any]]:
    return [
        _summary_case(
            case_id="AAPL_SERVICES_REGULATORY_RISK_2025_001",
            bucket=BUCKET_L2,
            company="AAPL",
            year=2025,
            task_type="single_company_services_regulatory_risk_summary",
            prompt=(
                "Using only Apple's fiscal 2025 Form 10-K, summarize how Services, regulatory risk, and "
                "gross-margin context affect Apple's business quality. Keep Products and Services separate."
            ),
            gold_points=[
                "Separates Products from Services.",
                "Mentions regulatory or platform-policy risk only if supported by Apple SEC text.",
                "Does not infer App Store economics beyond disclosed SEC evidence.",
            ],
            expected_sections=["Item 1. Business", "Item 1A. Risk Factors", "Item 7. Management's Discussion and Analysis"],
        ),
        _summary_case(
            case_id="ADBE_DIGITAL_MEDIA_AI_STRATEGY_2025_001",
            bucket=BUCKET_L2,
            company="ADBE",
            year=2025,
            task_type="single_company_digital_media_ai_strategy_summary",
            prompt=(
                "Using only Adobe's fiscal 2025 Form 10-K, summarize Digital Media, AI product strategy, "
                "ARR or subscription context, and the main caveats for interpreting growth quality."
            ),
            gold_points=[
                "Focuses on Adobe's own Digital Media and subscription disclosures.",
                "Labels ARR or deferred revenue as visibility metrics rather than recognized revenue.",
                "Avoids product-level AI revenue claims unless disclosed.",
            ],
            expected_sections=["Item 1. Business", "Item 7. Management's Discussion and Analysis", "Item 8. Financial Statements"],
        ),
        _summary_case(
            case_id="AMZN_AWS_AI_CAPEX_CONTEXT_2025_001",
            bucket=BUCKET_L2,
            company="AMZN",
            year=2025,
            task_type="single_company_aws_ai_capex_context_summary",
            prompt=(
                "Using only Amazon's fiscal 2025 Form 10-K, summarize AWS, AI infrastructure or capex context, "
                "and operating-income quality. Do not use non-SEC cloud market estimates."
            ),
            gold_points=[
                "Keeps AWS segment evidence separate from consolidated Amazon totals.",
                "Mentions capital investment pressure only when supported by SEC evidence.",
                "Does not use market-share or external AI demand estimates.",
            ],
            expected_sections=["Item 1. Business", "Item 7. Management's Discussion and Analysis", "Item 8. Financial Statements"],
        ),
        _summary_case(
            case_id="GOOGL_SEARCH_YOUTUBE_CLOUD_ROLE_2025_001",
            bucket=BUCKET_L2,
            company="GOOGL",
            year=2025,
            task_type="single_company_ads_youtube_cloud_role_summary",
            prompt=(
                "Using only Alphabet's fiscal 2025 Form 10-K, summarize the roles of Search, YouTube, and Google Cloud "
                "in Alphabet's business mix and caveat any comparability limits."
            ),
            gold_points=[
                "Separates Google advertising, YouTube, and Google Cloud.",
                "Does not attribute AWS or Microsoft Azure metrics to Alphabet.",
                "Uses only Alphabet SEC evidence.",
            ],
            expected_sections=["Item 1. Business", "Item 7. Management's Discussion and Analysis", "Item 8. Financial Statements"],
        ),
        _summary_case(
            case_id="MSFT_AI_CAPEX_CLOUD_RISK_2025_001",
            bucket=BUCKET_L2,
            company="MSFT",
            year=2025,
            task_type="single_company_ai_capex_cloud_risk_summary",
            prompt=(
                "Using only Microsoft's fiscal 2025 Form 10-K, summarize AI infrastructure, cloud margin or capex "
                "pressure, and the caveat between Microsoft Cloud and Azure-specific metrics."
            ),
            gold_points=[
                "Labels Microsoft Cloud as a broad company-defined metric.",
                "Does not present Microsoft Cloud gross margin as exact Azure gross margin.",
                "Mentions AI infrastructure/capex risk only from SEC evidence.",
            ],
            expected_sections=["Item 1. Business", "Item 1A. Risk Factors", "Item 7. Management's Discussion and Analysis"],
        ),
        _summary_case(
            case_id="PANW_PLATFORMIZATION_CONTEXT_2025_001",
            bucket=BUCKET_L2,
            company="PANW",
            year=2025,
            task_type="single_company_platformization_visibility_summary",
            prompt=(
                "Using only Palo Alto Networks' fiscal 2025 Form 10-K, summarize platformization, subscription/support "
                "visibility, RPO or billings context, and caveats for using these as revenue-quality signals."
            ),
            gold_points=[
                "Separates revenue, billings, RPO, and deferred revenue definitions.",
                "Does not equate visibility metrics with recognized revenue.",
                "Keeps the answer scoped to PANW SEC evidence.",
            ],
            expected_sections=["Item 1. Business", "Item 7. Management's Discussion and Analysis", "Item 8. Financial Statements"],
        ),
        _trend_case(
            case_id="AMZN_ADS_SUBSCRIPTION_AWS_MIX_2023_2025_001",
            company="AMZN",
            task_type="single_company_revenue_mix_trend",
            prompt=(
                "Using only Amazon's 2023-2025 Form 10-K evidence, compare how AWS, advertising, subscription, "
                "and consolidated revenue signals changed. Keep segment and consolidated measures separate."
            ),
            gold_points=[
                "Distinguishes AWS from consolidated Amazon revenue.",
                "Treats advertising and subscription signals as separate lines when disclosed.",
                "Does not infer profitability for non-AWS revenue lines unless disclosed.",
            ],
            numeric_checks=[
                _numeric_check("AWS revenue", ["AMZN"], YEARS_2023_2025, ["cloud_revenue"], ["total_value"]),
                _numeric_check("advertising revenue", ["AMZN"], YEARS_2023_2025, ["advertising_revenue"], ["total_value"]),
            ],
        ),
        _trend_case(
            case_id="NVDA_INVENTORY_SUPPLY_CONSTRAINT_RISK_2023_2025_001",
            company="NVDA",
            task_type="single_company_inventory_supply_risk_trend",
            prompt=(
                "Using only NVIDIA's 2023-2025 Form 10-K evidence, summarize inventory, supply constraint, "
                "export-control, and demand-risk language across the three years. Do not quantify product-level revenue."
            ),
            gold_points=[
                "Distinguishes risk-language changes across 2023, 2024, and 2025.",
                "Does not invent exact product-level or architecture-level revenue.",
                "Mentions export controls or supply/demand risk only when supported.",
            ],
            numeric_checks=[],
        ),
        _trend_case(
            case_id="SNOW_CONSUMPTION_RPO_CUSTOMER_RISK_2023_2025_001",
            company="SNOW",
            task_type="single_company_consumption_visibility_risk_trend",
            prompt=(
                "Using only Snowflake's 2023-2025 Form 10-K evidence, summarize consumption-model revenue, RPO, "
                "customer usage risk, and any disclosed growth-quality caveats."
            ),
            gold_points=[
                "Explains Snowflake's consumption-based revenue model.",
                "Separates RPO or remaining obligations from recognized revenue.",
                "Does not invent NRR or customer-count values unless disclosed in the cited evidence.",
            ],
            numeric_checks=[
                _numeric_check("remaining performance obligations", ["SNOW"], YEARS_2023_2025, ["rpo"], ["total_value"]),
                _numeric_check("product revenue", ["SNOW"], YEARS_2023_2025, ["product_revenue"], ["total_value"]),
            ],
        ),
        _numeric_table_case(
            case_id="ADBE_REVENUE_DEFERRED_REVENUE_TABLE_2023_2025_001",
            company="ADBE",
            task_type="single_company_revenue_deferred_revenue_table",
            prompt=(
                "Using only Adobe's 2023-2025 Form 10-K evidence, build a compact table for revenue and deferred "
                "revenue or remaining-performance-obligation visibility. Explain why these metrics are not interchangeable."
            ),
            gold_points=[
                "Reports revenue and deferred/obligation metrics only from SEC evidence.",
                "States that deferred revenue or RPO is a visibility metric, not recognized revenue.",
                "Keeps fiscal-year values and units explicit.",
            ],
            numeric_checks=[
                _numeric_check("total revenue", ["ADBE"], YEARS_2023_2025, ["total_revenue"], ["total_value"]),
                _numeric_check("deferred revenue", ["ADBE"], YEARS_2023_2025, ["deferred_revenue"], ["total_value"]),
            ],
        ),
        _numeric_table_case(
            case_id="AMZN_OPERATING_CASH_FLOW_CAPEX_TABLE_2023_2025_001",
            company="AMZN",
            task_type="single_company_cash_flow_capex_table",
            prompt=(
                "Using only Amazon's 2023-2025 Form 10-K evidence, build a compact table for operating cash flow "
                "and property/equipment purchases or capex-like investment. Label any free-cash-flow calculation as a proxy."
            ),
            gold_points=[
                "Uses operating cash flow and property/equipment purchase values from SEC evidence.",
                "Labels any free-cash-flow arithmetic as a proxy calculation.",
                "Does not treat capex as a disclosed standardized FCF metric.",
            ],
            numeric_checks=[
                _numeric_check("operating cash flow", ["AMZN"], YEARS_2023_2025, ["cash_flow"], ["total_value"]),
                _numeric_check("property and equipment purchases", ["AMZN"], YEARS_2023_2025, ["ppe_purchases"], ["total_value"]),
            ],
        ),
        _numeric_table_case(
            case_id="MSFT_OPERATING_CASH_FLOW_CAPEX_TABLE_2023_2025_001",
            company="MSFT",
            task_type="single_company_cash_flow_capex_table",
            prompt=(
                "Using only Microsoft's 2023-2025 Form 10-K evidence, build a compact table for operating cash flow "
                "and capital expenditures or property/equipment additions. Caveat any AI-infrastructure interpretation."
            ),
            gold_points=[
                "Uses Microsoft SEC cash-flow and capex-like values only.",
                "Caveats that capex is not automatically AI-only infrastructure spend.",
                "Keeps fiscal-year values and units explicit.",
            ],
            numeric_checks=[
                _numeric_check("operating cash flow", ["MSFT"], YEARS_2023_2025, ["cash_flow"], ["total_value"]),
                _numeric_check("capital expenditures", ["MSFT"], YEARS_2023_2025, ["ppe_purchases"], ["total_value"]),
            ],
        ),
        _trap_case(
            case_id="GOOGL_AWS_OPERATING_INCOME_TRAP_2023_2025_001",
            company="GOOGL",
            task_type="anti_hallucination_wrong_attribution",
            prompt=(
                "Based only on Alphabet's 2023-2025 Form 10-K evidence, provide AWS operating income for 2023, "
                "2024, and 2025. If AWS is not an Alphabet business, explicitly refuse the attribution."
            ),
            not_found_target="AWS operating income in Alphabet filings",
            target_term="AWS",
            wrong_entity="AWS belongs to Amazon, not Alphabet.",
        ),
        _trap_case(
            case_id="NVDA_CUDA_SOFTWARE_REVENUE_NOT_FOUND_2023_2025_001",
            company="NVDA",
            task_type="anti_hallucination_metric_scope_not_found",
            prompt=(
                "Based only on NVIDIA's 2023-2025 Form 10-K evidence, provide exact CUDA software revenue for each "
                "fiscal year. If exact CUDA software revenue is not disclosed, say so and do not substitute Data Center revenue."
            ),
            not_found_target="exact CUDA software revenue",
            target_term="CUDA",
            wrong_entity="CUDA software revenue is not the same as Data Center revenue.",
        ),
    ]


def _summary_case(
    *,
    case_id: str,
    bucket: str,
    company: str,
    year: int,
    task_type: str,
    prompt: str,
    gold_points: list[str],
    expected_sections: list[str],
) -> dict[str, Any]:
    return _case(
        case_id=case_id,
        bucket=bucket,
        level="L2",
        companies=[company],
        years=[year],
        task_type=task_type,
        prompt=prompt,
        expected_sections=expected_sections,
        gold_points=gold_points,
        numeric_checks=[],
        hard_gates=["source_resolver", "citation_grounding_gate", "unsupported_claim_gate"],
        failure_types=["unsupported_claim", "source_policy_violation", "missing_caveat"],
    )


def _trend_case(
    *,
    case_id: str,
    company: str,
    task_type: str,
    prompt: str,
    gold_points: list[str],
    numeric_checks: list[dict[str, Any]],
) -> dict[str, Any]:
    return _case(
        case_id=case_id,
        bucket=BUCKET_L3,
        level="L3",
        companies=[company],
        years=YEARS_2023_2025,
        task_type=task_type,
        prompt=prompt,
        expected_sections=["Item 1. Business", "Item 1A. Risk Factors", "Item 7. Management's Discussion and Analysis", "Item 8. Financial Statements"],
        gold_points=gold_points,
        numeric_checks=numeric_checks,
        hard_gates=["source_resolver", "citation_grounding_gate", "unsupported_claim_gate"],
        failure_types=["unsupported_claim", "source_policy_violation", "missing_caveat"],
    )


def _numeric_table_case(
    *,
    case_id: str,
    company: str,
    task_type: str,
    prompt: str,
    gold_points: list[str],
    numeric_checks: list[dict[str, Any]],
) -> dict[str, Any]:
    return _case(
        case_id=case_id,
        bucket=BUCKET_NUMERIC,
        level="L3",
        companies=[company],
        years=YEARS_2023_2025,
        task_type=task_type,
        prompt=prompt,
        expected_sections=["Item 7. Management's Discussion and Analysis", "Item 8. Financial Statements"],
        gold_points=gold_points,
        numeric_checks=numeric_checks,
        hard_gates=["source_resolver", "exact_value_ledger_gate", "table_cell_gate", "unsupported_claim_gate"],
        failure_types=["unsupported_claim", "numeric_mismatch", "proxy_as_direct_metric", "missing_caveat"],
    )


def _trap_case(
    *,
    case_id: str,
    company: str,
    task_type: str,
    prompt: str,
    not_found_target: str,
    target_term: str,
    wrong_entity: str,
) -> dict[str, Any]:
    return _case(
        case_id=case_id,
        bucket=BUCKET_TRAP,
        level="L1",
        companies=[company],
        years=YEARS_2023_2025,
        task_type=task_type,
        prompt=prompt,
        expected_sections=[],
        evaluation_modes=["pipeline_context"],
        gold_context_status="not_required_for_trap",
        reviewed_asset_status="pipeline_trap_seed",
        gold_points=[
            f"Must state that {not_found_target} is not available from the scoped SEC evidence.",
            wrong_entity,
            "Must not invent exact values or substitute another company's or broader metric's values.",
        ],
        numeric_checks=[],
        required_not_found=[
            {
                "id": "trap_target_not_found",
                "description": f"Must explicitly refuse or mark not found: {not_found_target}.",
                "all_of_any": [
                    [target_term],
                    ["not found", "not disclosed", "cannot provide", "wrong attribution", "not available"],
                ],
            }
        ],
        required_caveats=[
            {
                "id": "trap_refusal",
                "description": f"Must explicitly refuse or mark not found: {not_found_target}.",
                "where": "answer",
                "all_of_any": [
                    [target_term],
                    ["not found", "not disclosed", "cannot provide", "wrong attribution", "not available"],
                ],
            }
        ],
        disallowed_claims=[
            {
                "id": "invented_trap_value",
                "description": "Do not invent exact values for the trap target.",
                "patterns": ["re:(was|were|is).{0,20}(\\$|\\d{2,}|%)"],
                "allow_if_any_near": ["not found", "not disclosed", "cannot", "not available", "not exact"],
            }
        ],
        hard_gates=["source_resolver", "not_found_gate", "unsupported_claim_gate"],
        failure_types=["unsupported_claim", "hallucination", "not_found_failure", "required_not_found_missing", "source_policy_violation"],
    )


def _case(
    *,
    case_id: str,
    bucket: str,
    level: str,
    companies: list[str],
    years: list[int],
    task_type: str,
    prompt: str,
    expected_sections: list[str],
    gold_points: list[str],
    numeric_checks: list[dict[str, Any]],
    hard_gates: list[str],
    failure_types: list[str],
    evaluation_modes: list[str] | None = None,
    gold_context_status: str = "needs_annotation",
    reviewed_asset_status: str = "seed_needs_review",
    required_not_found: list[dict[str, Any]] | None = None,
    required_caveats: list[dict[str, Any]] | None = None,
    disallowed_claims: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    resolved_reviewed_asset_status = reviewed_asset_status
    if reviewed_asset_status == "seed_needs_review":
        resolved_reviewed_asset_status = _reviewed_asset_status(
            {
                "case_id": case_id,
                "gold_context_status": gold_context_status,
                "task_type": task_type,
            }
        )
    case = {
        "schema_version": "sec_eval_case_v1",
        "benchmark_version": "sec_benchmark_v1",
        "case_id": case_id,
        "origin": "v2_full40_seed_new_case",
        "case_family": "v2_full40_seed",
        "full40_bucket": bucket,
        "full40_inclusion_role": "new_seed_case",
        "reviewed_asset_status": resolved_reviewed_asset_status,
        "test_objective": f"Full40 seed coverage for {task_type}.",
        "case_group": "diagnostic_stress" if bucket == BUCKET_TRAP else "formal_seed",
        "level": level,
        "companies": companies,
        "years": years,
        "filing_types": FORM_10K,
        "task_type": task_type,
        "prompt": prompt,
        "allowed_sources": SEC_ONLY,
        "source_policy": "SEC_ONLY",
        "evaluation_modes": evaluation_modes or ["gold_context", "pipeline_context"],
        "expected_sections": expected_sections,
        "gold_points": gold_points,
        "numeric_checks": numeric_checks,
        "required_caveats": required_caveats or _generic_required_caveats({"companies": companies, "task_type": task_type}),
        "disallowed_claims": disallowed_claims or _generic_disallowed_claims({"companies": companies, "task_type": task_type}),
        "hard_gates": hard_gates,
        "hallucination_traps": [
            "Use SEC evidence only.",
            "Do not invent undisclosed exact values.",
            "Do not substitute peer-company or broader-scope metrics for the requested metric.",
        ],
        "failure_types": failure_types,
        "score_weights": SCORE_WEIGHTS,
        "gold_context_status": gold_context_status,
    }
    if required_not_found:
        case["required_not_found"] = required_not_found
    return case


def _numeric_check(
    metric: str,
    companies: list[str],
    years: list[int],
    metric_families: list[str],
    metric_roles: list[str],
) -> dict[str, Any]:
    return {
        "metric": metric,
        "companies": companies,
        "years": years,
        "metric_families": metric_families,
        "metric_roles": metric_roles,
    }


def _generic_required_caveats(case: dict[str, Any]) -> list[dict[str, Any]]:
    companies = [str(item) for item in case.get("companies") or []]
    first_company = companies[0] if companies else "company"
    return [
        {
            "id": "sec_only_scope",
            "description": "Must keep the answer scoped to SEC filings.",
            "where": "answer",
            "all_of_any": [[first_company], ["SEC", "10-K", "Form 10-K"]],
        },
        {
            "id": "no_unsupported_exact_values",
            "description": "Must caveat that exact values are only reported when disclosed in the scoped evidence.",
            "where": "caveats",
            "all_of_any": [["not disclosed", "if disclosed", "where disclosed", "not found", "not quantified"]],
            "required": False,
        },
    ]


def _generic_disallowed_claims(case: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "id": "non_sec_market_claim",
            "description": "Do not use stock price, analyst, news, or market-share commentary as SEC evidence.",
            "patterns": ["stock price", "analyst target", "news reports", "market share", "market sentiment"],
            "allow_if_any_near": ["not used", "not disclosed", "not SEC evidence", "cannot use"],
        },
        {
            "id": "invented_exact_metric",
            "description": "Do not present undisclosed product or metric values as exact SEC facts.",
            "patterns": ["re:(exact|precise).{0,30}(revenue|margin|income|cost).{0,20}(\\$|\\d)"],
            "allow_if_any_near": ["not disclosed", "not found", "not quantified", "cannot"],
        },
    ]


LEGACY_POLICY_PATCHES: dict[str, dict[str, Any]] = {
    "AAPL_SERVICES_MARGIN_2023_2025_001": {
        "test_objective": "Promote reviewed Apple Services margin evidence into the full40 numeric/table bucket.",
        "required_caveats": [
            {
                "id": "products_services_separation",
                "description": "Must keep Products and Services revenue/gross-margin rows separate.",
                "where": "answer",
                "all_of_any": [["Products", "Services"], ["separate", "different", "not combined", "distinguish"]],
            }
        ],
        "disallowed_claims": [
            {
                "id": "services_as_total_company_margin",
                "description": "Do not treat Services gross margin as total company gross margin.",
                "patterns": ["Services gross margin is Apple's total gross margin", "Services margin equals company margin"],
                "allow_if_any_near": ["not", "different", "separate"],
            }
        ],
        "hard_gates": ["table_cell_gate", "metric_role_gate"],
        "failure_types": ["proxy_as_direct_metric", "missing_caveat"],
    },
    "GOOGL_CLOUD_CONTEXT_ROLE_2025_001": {
        "test_objective": "Promote reviewed Alphabet Cloud context evidence into the full40 L2 bucket.",
        "required_caveats": [
            {
                "id": "google_cloud_not_total_alphabet",
                "description": "Must distinguish Google Cloud from Alphabet consolidated results.",
                "where": "answer",
                "all_of_any": [["Google Cloud"], ["Alphabet", "Google Services", "consolidated"], ["separate", "not total", "distinct"]],
            }
        ],
        "disallowed_claims": [
            {
                "id": "cloud_equals_total_company",
                "description": "Do not treat Google Cloud as total Alphabet.",
                "patterns": ["Google Cloud is Alphabet's total revenue", "Google Cloud equals Alphabet"],
                "allow_if_any_near": ["not", "separate", "distinct"],
            }
        ],
        "hard_gates": ["metric_role_gate", "unsupported_claim_gate"],
        "failure_types": ["proxy_as_direct_metric", "missing_caveat"],
    },
    "MSFT_AI_CLOUD_2023_2025_001": {
        "test_objective": "Promote reviewed Microsoft AI/cloud text evidence into the full40 L3 bucket.",
        "required_caveats": [
            {
                "id": "microsoft_cloud_proxy_boundary",
                "description": "Must distinguish Microsoft Cloud or AI infrastructure context from exact Azure-only metrics.",
                "where": "answer",
                "all_of_any": [["Microsoft Cloud", "Azure"], ["not exact", "proxy", "broader", "separate", "not the same"]],
            }
        ],
        "disallowed_claims": [
            {
                "id": "invented_azure_margin",
                "description": "Do not invent exact Azure gross margin.",
                "patterns": ["re:Azure.{0,30}(gross margin|margin).{0,20}\\d+%"],
                "allow_if_any_near": ["not disclosed", "not exact", "proxy"],
            }
        ],
        "hard_gates": ["unsupported_claim_gate", "proxy_scope_gate"],
        "failure_types": ["proxy_as_direct_metric", "missing_caveat"],
    },
    "PANW_SUBSCRIPTION_VISIBILITY_2023_2025_001": {
        "test_objective": "Promote reviewed Palo Alto subscription visibility evidence into the full40 L3 bucket.",
        "required_caveats": [
            {
                "id": "visibility_metrics_not_revenue",
                "description": "Must separate billings, RPO, deferred revenue, and recognized revenue.",
                "where": "answer",
                "all_of_any": [["billings", "RPO", "deferred revenue"], ["recognized revenue", "revenue"], ["not the same", "separate", "visibility"]],
            }
        ],
        "disallowed_claims": [
            {
                "id": "visibility_metric_equals_revenue",
                "description": "Do not equate RPO, billings, or deferred revenue with recognized revenue.",
                "patterns": ["RPO is recognized revenue", "billings are recognized revenue", "deferred revenue equals revenue"],
                "allow_if_any_near": ["not", "not the same", "separate"],
            }
        ],
        "hard_gates": ["proxy_scope_gate", "unsupported_claim_gate"],
        "failure_types": ["proxy_as_direct_metric", "missing_caveat"],
    },
    "AAPL_AWS_TRAP_001": {
        "test_objective": "Carry forward a wrong-company source-policy trap into full40.",
        "required_not_found": [
            {
                "id": "aws_not_apple",
                "description": "Must refuse AWS attribution to Apple.",
                "all_of_any": [["AWS"], ["Apple", "AAPL"], ["wrong attribution", "not Apple", "not found", "cannot provide"]],
            }
        ],
        "required_caveats": [
            {
                "id": "aws_not_apple",
                "description": "Must refuse AWS attribution to Apple.",
                "where": "answer",
                "all_of_any": [["AWS"], ["Apple", "AAPL"], ["wrong attribution", "not Apple", "not found", "cannot provide"]],
            }
        ],
        "disallowed_claims": [
            {
                "id": "invented_aws_apple_value",
                "description": "Do not provide AWS values as Apple evidence.",
                "patterns": ["re:AWS.{0,30}(revenue|income).{0,20}(\\$|\\d)"],
                "allow_if_any_near": ["not", "not Apple", "wrong attribution", "cannot provide"],
            }
        ],
        "hard_gates": ["source_policy_gate", "not_found_gate"],
        "failure_types": ["source_policy_violation", "required_not_found_missing"],
    },
    "META_LLAMA_COST_TRAP_001": {
        "test_objective": "Carry forward an undisclosed-metric source-policy trap into full40.",
        "required_not_found": [
            {
                "id": "llama_cost_not_disclosed",
                "description": "Must say exact Llama model cost is not disclosed in Meta SEC filings.",
                "all_of_any": [["Llama"], ["cost", "expense"], ["not disclosed", "not found", "cannot provide"]],
            }
        ],
        "required_caveats": [
            {
                "id": "llama_cost_not_disclosed",
                "description": "Must say exact Llama model cost is not disclosed in Meta SEC filings.",
                "where": "answer",
                "all_of_any": [["Llama"], ["cost", "expense"], ["not disclosed", "not found", "cannot provide"]],
            }
        ],
        "disallowed_claims": [
            {
                "id": "invented_llama_cost",
                "description": "Do not invent Llama training or model cost.",
                "patterns": ["re:Llama.{0,40}(cost|expense|training).{0,20}(\\$|\\d)"],
                "allow_if_any_near": ["not disclosed", "not found", "cannot provide"],
            }
        ],
        "hard_gates": ["source_policy_gate", "not_found_gate"],
        "failure_types": ["source_policy_violation", "required_not_found_missing"],
    },
}


def _reviewed_asset_status(case: dict[str, Any]) -> str:
    case_id = str(case.get("case_id") or "")
    if str(case.get("gold_context_status") or "") == "not_required_for_trap" or str(case.get("task_type") or "").startswith("anti_hallucination"):
        return "pipeline_trap"
    if (REVIEWED_CONTEXT_DIR / f"{case_id}.jsonl").exists() and (REVIEWED_FACTS_DIR / f"{case_id}.json").exists():
        return "reviewed_gold_available"
    return "seed_needs_review"


def _assert_manifest_contract(rows: list[dict[str, Any]]) -> None:
    case_ids = [str(row.get("case_id") or "") for row in rows]
    duplicates = sorted(case_id for case_id, count in Counter(case_ids).items() if count > 1)
    if duplicates:
        raise SystemExit(f"Duplicate full40 case ids: {duplicates}")
    if len(rows) != 40:
        raise SystemExit(f"Expected 40 full40 cases, got {len(rows)}")
    bucket_counts = Counter(str(row.get("full40_bucket") or "") for row in rows)
    if dict(bucket_counts) != TARGET_BUCKET_COUNTS:
        raise SystemExit(f"Bucket counts do not match target: {dict(bucket_counts)}")
    missing_bucket = [case_id for case_id, row in zip(case_ids, rows) if not row.get("full40_bucket")]
    if missing_bucket:
        raise SystemExit(f"Missing full40_bucket: {missing_bucket}")


def _build_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    company_counts = Counter(company for row in rows for company in row.get("companies") or [])
    review_status_counts = Counter(str(row.get("reviewed_asset_status") or "") for row in rows)
    bucket_counts = Counter(str(row.get("full40_bucket") or "") for row in rows)
    role_counts = Counter(str(row.get("full40_inclusion_role") or "") for row in rows)
    return {
        "schema_version": "sec_benchmark_v2_full40_seed_build_report_v0.1",
        "manifest": str(FULL40_MANIFEST),
        "base_manifest": str(PLUS8_MANIFEST),
        "case_count": len(rows),
        "bucket_target_counts": TARGET_BUCKET_COUNTS,
        "bucket_counts": dict(sorted(bucket_counts.items())),
        "review_status_counts": dict(sorted(review_status_counts.items())),
        "inclusion_role_counts": dict(sorted(role_counts.items())),
        "company_counts": dict(sorted(company_counts.items())),
        "case_ids": [str(row.get("case_id") or "") for row in rows],
        "deferred_reviewed_case_ids": DEFERRED_REVIEWED_CASE_IDS,
        "governance": {
            "decision_label": "proceed_to_seed_readiness_only",
            "allowed_next_step": "run manifest readiness and retrieval smoke on the 40-case seed",
            "blocked_next_step": (
                "do not run or claim a full40 mainline BGE-M3 + Qwen scored benchmark until seed-only cases "
                "have reviewed gold context/facts or explicit trap approval"
            ),
            "reason": (
                "Only a subset of the 40 cases has reviewed gold artifacts. The full40 seed is useful for source, "
                "schema, retrieval, and coverage pressure-testing before manual review."
            ),
        },
        "bge_m3_policy": {
            "final_context_selector": "BAAI/bge-reranker-v2-m3",
            "bm25_role": "candidate_generator_only",
            "bm25_only_allowed": False,
        },
    }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def _dedupe(items: list[Any]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item)
        if text and text not in seen:
            output.append(text)
            seen.add(text)
    return output


if __name__ == "__main__":
    main()
