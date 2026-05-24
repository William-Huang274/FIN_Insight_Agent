from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from scripts import build_sec_benchmark_v2_pilot_reviewed_gold as base_pilot  # noqa: E402


BASE_MANIFEST = REPO_ROOT / "eval" / "sec_cases" / "test_cases_v2_pilot_seed.jsonl"
PLUS2_MANIFEST = REPO_ROOT / "eval" / "sec_cases" / "test_cases_v2_pilot_plus2_seed.jsonl"

ADBE_CASE = "ADBE_DIGITAL_MEDIA_ARR_REVENUE_GROWTH_2023_2025_001"
PEER_CASE = "GOOGL_META_ADS_AI_INFRA_LOCAL_SUPPORT_2023_2025_001"
SOURCE_PEER_CASE = "ADS_AI_INFRA_GROWTH_QUALITY_2023_2025_DIAG_001"
TRAP_CASE = base_pilot.TRAP_CASE

BASE_REVIEWED_CASE_IDS = list(base_pilot.REVIEWED_CASE_IDS)
PLUS2_REVIEWED_CASE_IDS = [*BASE_REVIEWED_CASE_IDS, ADBE_CASE, PEER_CASE]


ADBE_SOURCES: dict[str, dict[str, Any]] = {
    "ADBE_2023_digital_media": {
        "source_evidence_id": "ADBE_2023_10K_ITEM7_BLOCK_0004_PART_02_OF_03",
        "ticker": "ADBE",
        "fiscal_year": 2023,
        "section": "Item 7. Management's Discussion and Analysis",
        "text": (
            "Adobe fiscal 2023 MD&A: Total Digital Media ARR was approximately $15.17 billion "
            "as of December 1, 2023 and increased by $1.91 billion, or 14%, from fiscal 2022. "
            "Total Digital Media segment revenue grew to $14.22 billion in fiscal 2023."
        ),
    },
    "ADBE_2024_digital_media": {
        "source_evidence_id": "ADBE_2024_10K_ITEM7_BLOCK_0004_PART_02_OF_03",
        "ticker": "ADBE",
        "fiscal_year": 2024,
        "section": "Item 7. Management's Discussion and Analysis",
        "text": (
            "Adobe fiscal 2024 MD&A: Total Digital Media ARR was approximately $17.33 billion "
            "as of November 29, 2024 and increased by $2.00 billion, or 13%, from fiscal 2023. "
            "Total Digital Media segment revenue grew to $15.86 billion in fiscal 2024."
        ),
    },
    "ADBE_2025_digital_media": {
        "source_evidence_id": "ADBE_2025_10K_ITEM7_BLOCK_0004_PART_02_OF_03",
        "ticker": "ADBE",
        "fiscal_year": 2025,
        "section": "Item 7. Management's Discussion and Analysis",
        "text": (
            "Adobe fiscal 2025 MD&A: Digital Media ARR was approximately $19.20 billion "
            "as of November 28, 2025 and increased by 11.5% from fiscal 2024. "
            "Digital Media revenue was $17.65 billion and increased by $1.79 billion, or 11%, "
            "compared to fiscal 2024."
        ),
    },
    "ADBE_2024_subscription_revenue_table": {
        "source_evidence_id": "ADBE_2024_10K_ITEM7_BLOCK_0004_PART_03_OF_03",
        "ticker": "ADBE",
        "fiscal_year": 2024,
        "section": "Item 7. Management's Discussion and Analysis",
        "text": (
            "Adobe fiscal 2024 MD&A subscription table reports Digital Media subscription revenue "
            "of $15,547 million in 2024 and $13,838 million in 2023."
        ),
    },
    "ADBE_2025_subscription_revenue_table": {
        "source_evidence_id": "ADBE_2025_10K_ITEM7_BLOCK_0004_PART_02_OF_03",
        "ticker": "ADBE",
        "fiscal_year": 2025,
        "section": "Item 7. Management's Discussion and Analysis",
        "text": (
            "Adobe fiscal 2025 MD&A revenue table reports subscription revenue of $22,904 million "
            "in 2025, $20,521 million in 2024, and $18,284 million in 2023."
        ),
    },
}


ADBE_FACT_SPECS: list[dict[str, Any]] = [
    {
        "period": "2023",
        "metric_name": "Digital Media ARR",
        "metric_family": "arr_or_recurring_proxy",
        "metric_role": "total_value",
        "raw_value": "$15.17 billion",
        "value": 15.17,
        "unit": "usd_billions",
        "source_key": "ADBE_2023_digital_media",
        "row_label": "Total Digital Media ARR",
        "column_label": "as of December 1, 2023",
    },
    {
        "period": "2023",
        "metric_name": "Digital Media ARR increase",
        "metric_family": "arr_or_recurring_proxy",
        "metric_role": "period_change_amount",
        "raw_value": "$1.91 billion",
        "value": 1.91,
        "unit": "usd_billions",
        "source_key": "ADBE_2023_digital_media",
        "row_label": "Total Digital Media ARR increase",
        "column_label": "increase from fiscal 2022",
    },
    {
        "period": "2023",
        "metric_name": "Digital Media ARR growth rate",
        "metric_family": "arr_or_recurring_proxy",
        "metric_role": "percentage_rate",
        "raw_value": "14%",
        "value": 14.0,
        "unit": "percent",
        "source_key": "ADBE_2023_digital_media",
        "row_label": "Total Digital Media ARR growth",
        "column_label": "growth from fiscal 2022",
    },
    {
        "period": "2023",
        "metric_name": "Digital Media segment revenue",
        "metric_family": "digital_media_revenue",
        "metric_role": "total_value",
        "raw_value": "$14.22 billion",
        "value": 14.22,
        "unit": "usd_billions",
        "source_key": "ADBE_2023_digital_media",
        "row_label": "Total Digital Media segment revenue",
        "column_label": "fiscal 2023",
    },
    {
        "period": "2024",
        "metric_name": "Digital Media ARR",
        "metric_family": "arr_or_recurring_proxy",
        "metric_role": "total_value",
        "raw_value": "$17.33 billion",
        "value": 17.33,
        "unit": "usd_billions",
        "source_key": "ADBE_2024_digital_media",
        "row_label": "Total Digital Media ARR",
        "column_label": "as of November 29, 2024",
    },
    {
        "period": "2024",
        "metric_name": "Digital Media ARR increase",
        "metric_family": "arr_or_recurring_proxy",
        "metric_role": "period_change_amount",
        "raw_value": "$2.00 billion",
        "value": 2.00,
        "unit": "usd_billions",
        "source_key": "ADBE_2024_digital_media",
        "row_label": "Total Digital Media ARR increase",
        "column_label": "increase from fiscal 2023",
    },
    {
        "period": "2024",
        "metric_name": "Digital Media ARR growth rate",
        "metric_family": "arr_or_recurring_proxy",
        "metric_role": "percentage_rate",
        "raw_value": "13%",
        "value": 13.0,
        "unit": "percent",
        "source_key": "ADBE_2024_digital_media",
        "row_label": "Total Digital Media ARR growth",
        "column_label": "growth from fiscal 2023",
    },
    {
        "period": "2024",
        "metric_name": "Digital Media segment revenue",
        "metric_family": "digital_media_revenue",
        "metric_role": "total_value",
        "raw_value": "$15.86 billion",
        "value": 15.86,
        "unit": "usd_billions",
        "source_key": "ADBE_2024_digital_media",
        "row_label": "Total Digital Media segment revenue",
        "column_label": "fiscal 2024",
    },
    {
        "period": "2025",
        "metric_name": "Digital Media ARR",
        "metric_family": "arr_or_recurring_proxy",
        "metric_role": "total_value",
        "raw_value": "$19.20 billion",
        "value": 19.20,
        "unit": "usd_billions",
        "source_key": "ADBE_2025_digital_media",
        "row_label": "Digital Media ARR",
        "column_label": "as of November 28, 2025",
    },
    {
        "period": "2025",
        "metric_name": "Digital Media ARR growth rate",
        "metric_family": "arr_or_recurring_proxy",
        "metric_role": "percentage_rate",
        "raw_value": "11.5%",
        "value": 11.5,
        "unit": "percent",
        "source_key": "ADBE_2025_digital_media",
        "row_label": "Digital Media ARR growth",
        "column_label": "growth from fiscal 2024",
    },
    {
        "period": "2025",
        "metric_name": "Digital Media revenue increase",
        "metric_family": "digital_media_revenue",
        "metric_role": "period_change_amount",
        "raw_value": "$1.79 billion",
        "value": 1.79,
        "unit": "usd_billions",
        "source_key": "ADBE_2025_digital_media",
        "row_label": "Digital Media revenue increase",
        "column_label": "increase from fiscal 2024",
    },
    {
        "period": "2025",
        "metric_name": "Digital Media segment revenue",
        "metric_family": "digital_media_revenue",
        "metric_role": "total_value",
        "raw_value": "$17.65 billion",
        "value": 17.65,
        "unit": "usd_billions",
        "source_key": "ADBE_2025_digital_media",
        "row_label": "Digital Media segment revenue",
        "column_label": "fiscal 2025",
    },
]


def main() -> None:
    reviewed_context_dir = REPO_ROOT / "eval" / "sec_cases" / "reviewed_gold_context"
    reviewed_facts_dir = REPO_ROOT / "eval" / "sec_cases" / "reviewed_gold_facts"
    report_dir = REPO_ROOT / "reports" / "quality"
    reviewed_context_dir.mkdir(parents=True, exist_ok=True)
    reviewed_facts_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    evidence_by_id = _load_evidence_index()
    metric_by_source_raw = _load_metric_index_by_source_raw()
    _write_manifest()
    adbe_summary = _write_adbe_artifacts(
        reviewed_context_dir,
        reviewed_facts_dir,
        evidence_by_id,
        metric_by_source_raw,
    )
    peer_summary = _write_peer_artifacts(reviewed_context_dir, reviewed_facts_dir)

    approval_path = report_dir / "sec_benchmark_v2_pilot_plus2_reviewed_gold_partial_approval.json"
    approval_path.write_text(json.dumps(_approval_payload(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    build_report_path = report_dir / "sec_benchmark_v2_pilot_plus2_reviewed_gold_build_report.json"
    build_report = {
        "schema_version": "sec_v2_pilot_plus2_reviewed_gold_build_report_v0.1",
        "base_manifest": str(BASE_MANIFEST),
        "plus2_manifest": str(PLUS2_MANIFEST),
        "base_reviewed_case_count": len(BASE_REVIEWED_CASE_IDS),
        "plus2_reviewed_case_count": len(PLUS2_REVIEWED_CASE_IDS),
        "trap_case_not_gold_context": TRAP_CASE,
        "approval_path": str(approval_path),
        "new_cases": [adbe_summary, peer_summary],
    }
    build_report_path.write_text(json.dumps(build_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "plus2_manifest": str(PLUS2_MANIFEST),
                "plus2_reviewed_case_count": len(PLUS2_REVIEWED_CASE_IDS),
                "new_fact_count": adbe_summary["fact_count"] + peer_summary["fact_count"],
                "new_context_row_count": adbe_summary["context_row_count"] + peer_summary["context_row_count"],
                "approval_path": str(approval_path),
                "build_report_path": str(build_report_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def _write_manifest() -> None:
    rows = _read_jsonl(BASE_MANIFEST)
    existing = {str(row.get("case_id") or "") for row in rows}
    additions = []
    if ADBE_CASE not in existing:
        additions.append(_adbe_manifest_case())
    if PEER_CASE not in existing:
        additions.append(_peer_manifest_case())
    PLUS2_MANIFEST.write_text(
        "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in [*rows, *additions]),
        encoding="utf-8",
    )


def _adbe_manifest_case() -> dict[str, Any]:
    return {
        "schema_version": "sec_eval_case_v1",
        "benchmark_version": "sec_benchmark_v1",
        "case_id": ADBE_CASE,
        "origin": "v2_pilot_plus2_reviewed_expansion",
        "case_family": "v2_pilot_plus2",
        "test_objective": (
            "Exercise period-change amount and ARR-proxy role separation using reviewed Adobe Digital Media evidence."
        ),
        "case_group": "diagnostic_stress",
        "level": "L3",
        "companies": ["ADBE"],
        "years": [2023, 2024, 2025],
        "filing_types": ["10-K"],
        "task_type": "single_company_arr_revenue_growth_role_separation",
        "prompt": (
            "Using Adobe's 2023-2025 SEC 10-K filings, summarize Digital Media ARR and Digital Media "
            "revenue growth. Keep ARR total values, revenue total values, absolute increase amounts, and "
            "percentage growth rates separate, and state why ARR should not be treated as recognized revenue."
        ),
        "allowed_sources": ["SEC"],
        "source_policy": "SEC_ONLY",
        "evaluation_modes": ["gold_context", "pipeline_context"],
        "expected_sections": ["Item 7. Management's Discussion and Analysis"],
        "gold_points": [
            "Must distinguish Digital Media ARR from Digital Media revenue.",
            "Must distinguish total values from absolute increase amounts.",
            "Must distinguish percentage growth rates from dollar amounts.",
            "Must state ARR is a management performance metric and not recognized revenue, deferred revenue, or RPO.",
        ],
        "numeric_checks": [
            {
                "metric": "Digital Media ARR and Digital Media revenue total values",
                "metric_families": ["arr_or_recurring_proxy", "digital_media_revenue"],
                "metric_roles": ["total_value"],
                "companies": ["ADBE"],
                "years": [2023, 2024, 2025],
                "expected_facts": [
                    {
                        "label": "Digital Media ARR total",
                        "metric_family": "arr_or_recurring_proxy",
                        "metric_role": "total_value",
                    },
                    {
                        "label": "Digital Media revenue total",
                        "metric_family": "digital_media_revenue",
                        "metric_role": "total_value",
                    },
                ],
            },
            {
                "metric": "disclosed absolute increase amounts",
                "metric_families": ["arr_or_recurring_proxy", "digital_media_revenue"],
                "metric_roles": ["period_change_amount"],
                "companies": ["ADBE"],
                "years": [2023, 2024, 2025],
            },
        ],
        "required_caveats": [
            {
                "id": "arr_proxy_not_revenue",
                "description": "Must state ARR is a performance metric/proxy and not recognized revenue.",
                "where": "caveats",
                "all_of_any": [
                    ["ARR"],
                    ["revenue", "recognized revenue", "deferred revenue", "RPO"],
                    ["not", "independently", "separate", "proxy", "performance metric"],
                ],
            },
            {
                "id": "increase_amount_not_level_value",
                "description": "Must keep absolute increase amounts separate from level values.",
                "where": "answer",
                "all_of_any": [
                    ["increase", "increased", "growth"],
                    ["total", "level", "value"],
                    ["separate", "not the same", "different"],
                ],
            },
        ],
        "disallowed_claims": [
            {
                "id": "arr_equals_revenue",
                "description": "Do not equate ARR with recognized revenue.",
                "patterns": ["ARR equals revenue", "ARR is recognized revenue", "ARR 等同于收入"],
                "allow_if_any_near": ["not", "different", "separate", "不", "不能"],
            },
            {
                "id": "increase_amount_as_total_value",
                "description": "Do not present an increase amount as a total level value.",
                "patterns": ["increase amount reached", "increase amount was total revenue", "增长额达到总收入"],
                "allow_if_any_near": ["not", "separate", "不", "不能"],
            },
        ],
        "hard_gates": [
            "source_resolver",
            "citation_validator",
            "exact_value_ledger",
            "metric_family_context_gate",
            "unsupported_claim_gate",
        ],
        "hallucination_traps": [
            "Do not use an ARR increase amount as a total ARR or revenue level.",
            "Do not treat ARR as recognized revenue or RPO.",
            "Do not treat percentage growth as a dollar amount.",
        ],
        "failure_types": [
            "retrieval_miss",
            "numeric_error",
            "unit_error",
            "metric_role_error",
            "proxy_as_direct_metric",
            "prior_period_as_target_value",
            "percentage_change_as_absolute_value",
            "missing_caveat",
        ],
        "score_weights": {"retrieval": 2, "factuality": 3, "coverage": 2, "synthesis": 2, "citation": 1},
        "gold_context_status": "needs_annotation",
    }


def _peer_manifest_case() -> dict[str, Any]:
    return {
        "schema_version": "sec_eval_case_v1",
        "benchmark_version": "sec_benchmark_v1",
        "case_id": PEER_CASE,
        "origin": "v2_pilot_plus2_reviewed_expansion",
        "case_family": "v2_pilot_plus2",
        "test_objective": (
            "Exercise local dual-sided support for Alphabet/Meta advertising and AI infrastructure peer-comparison claims."
        ),
        "case_group": "diagnostic_stress",
        "level": "L4",
        "companies": ["GOOGL", "META"],
        "years": [2023, 2024, 2025],
        "filing_types": ["10-K"],
        "task_type": "peer_comparison_ads_ai_infra_growth_quality",
        "prompt": (
            "Compare Alphabet and Meta from fiscal 2023 to 2025 on advertising recovery, AI or technical "
            "infrastructure investment, and operating leverage. Every peer-comparison conclusion should cite "
            "support for both Alphabet and Meta locally, or be split into separate company-specific statements."
        ),
        "allowed_sources": ["SEC"],
        "source_policy": "SEC_ONLY",
        "evaluation_modes": ["gold_context", "pipeline_context"],
        "expected_sections": [
            "Item 1A. Risk Factors",
            "Item 7. Management's Discussion and Analysis",
            "Item 8. Financial Statements",
        ],
        "gold_points": [
            "Must compare both Alphabet and Meta, not only one side.",
            "Must support peer-comparison sentences with local evidence for both peers or split the sentence.",
            "Must discuss advertising revenue, operating leverage, and infrastructure or AI investment pressure only where supported.",
            "Must not attribute all technical infrastructure capex to advertising products.",
            "Must not claim AI directly caused advertising growth unless SEC evidence states it.",
        ],
        "numeric_checks": [
            {
                "metric": "Alphabet advertising revenue operating income and capex",
                "metric_families": ["advertising_revenue", "operating_income", "capex"],
                "metric_roles": ["total_value"],
                "companies": ["GOOGL"],
                "years": [2023, 2024, 2025],
            },
            {
                "metric": "Meta advertising revenue operating income and capex",
                "metric_families": ["advertising_revenue", "operating_income", "capex"],
                "metric_roles": ["total_value"],
                "companies": ["META"],
                "years": [2023, 2024, 2025],
            },
        ],
        "required_caveats": [
            {
                "id": "local_dual_peer_support",
                "description": "Must locally support peer-comparison conclusions for both peers or split them.",
                "where": "answer",
                "all_of_any": [
                    ["Alphabet", "GOOGL", "Google"],
                    ["Meta", "META"],
                    ["support", "both", "local", "split", "separate"],
                ],
            },
            {
                "id": "ai_not_direct_ad_growth_cause",
                "description": "Must caveat that SEC evidence does not prove AI directly caused advertising growth.",
                "where": "caveats",
                "all_of_any": [
                    ["AI"],
                    ["advertising", "ads"],
                    ["not", "does not prove", "cannot", "no direct"],
                ],
            },
            {
                "id": "technical_infra_capex_not_all_ads",
                "description": "Must caveat that technical infrastructure capex cannot all be attributed to advertising products.",
                "where": "caveats",
                "all_of_any": [
                    ["technical infrastructure", "capex", "capital expenditures"],
                    ["advertising", "ads"],
                    ["not", "cannot", "no direct allocation"],
                ],
            },
        ],
        "disallowed_claims": [
            {
                "id": "external_market_news",
                "description": "Do not use stock-market narrative or external news.",
                "patterns": ["stock-market narrative", "external news", "股价", "新闻报道"],
                "allow_if_any_near": ["not", "do not", "未使用", "不能"],
            },
            {
                "id": "ai_directly_drove_ads",
                "description": "Do not claim AI directly drove ad growth unless SEC evidence states it.",
                "patterns": ["AI directly drove ad growth", "AI 直接驱动了广告增长"],
                "allow_if_any_near": ["not", "cannot", "does not prove", "未", "未证明", "不能"],
            },
            {
                "id": "all_infra_capex_to_ads",
                "description": "Do not attribute all technical infrastructure capex to advertising products.",
                "patterns": ["all technical infrastructure capex to advertising", "全部技术基础设施资本支出归因于广告"],
                "allow_if_any_near": ["not", "cannot", "no direct allocation", "未", "未将", "不能"],
            },
        ],
        "hard_gates": [
            "query_contract",
            "driver_pack",
            "citation_validator",
            "exact_value_ledger",
            "metric_family_context_gate",
            "comparability_gate",
            "conclusion_calibration_gate",
            "unsupported_claim_gate",
        ],
        "hallucination_traps": [
            "Do not use stock-market narrative or external news.",
            "Do not claim AI directly drove ad growth unless SEC evidence states it.",
            "Do not attribute all technical infrastructure capex to advertising products.",
            "Do not make a local peer-comparison sentence with support for only one peer.",
        ],
        "failure_types": [
            "retrieval_miss",
            "numeric_error",
            "unit_error",
            "unsupported_claim",
            "weak_synthesis",
            "missing_required_point",
            "entity_bleed_between_peers",
        ],
        "score_weights": {"retrieval": 2, "factuality": 3, "coverage": 2, "synthesis": 2, "citation": 1},
        "gold_context_status": "needs_annotation",
    }


def _write_adbe_artifacts(
    reviewed_context_dir: Path,
    reviewed_facts_dir: Path,
    evidence_by_id: dict[str, dict[str, Any]],
    metric_by_source_raw: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    facts = []
    for idx, spec in enumerate(ADBE_FACT_SPECS, start=1):
        source = ADBE_SOURCES[str(spec["source_key"])]
        source_metric = metric_by_source_raw.get((str(source["source_evidence_id"]), _normalize_raw_value(spec["raw_value"])))
        facts.append(
            {
                "fact_id": f"{ADBE_CASE}_FACT_REVIEWED_{idx:04d}",
                "review_status": "reviewed_keep",
                "selection_method": "manual_review_sec_mda_statement",
                "metric_id": f"ADBE_{spec['period']}_{spec['metric_family']}_{spec['metric_role']}",
                "ticker": "ADBE",
                "fiscal_year": int(spec["period"]),
                "period": spec["period"],
                "metric_name": spec["metric_name"],
                "metric_family": spec["metric_family"],
                "metric_role": spec["metric_role"],
                "raw_value": spec["raw_value"],
                "value": spec["value"],
                "unit": spec["unit"],
                "display_value_en": _display_value_en(float(spec["value"]), str(spec["unit"])),
                "object_id": (
                    source_metric.get("object_id")
                    if source_metric
                    else f"{source['source_evidence_id']}::reviewed::{spec['metric_family']}::{spec['metric_role']}::{spec['period']}"
                ),
                "source_evidence_id": source["source_evidence_id"],
                "section": source["section"],
                "row_label": spec["row_label"],
                "column_label": spec["column_label"],
                "allowed_claim_roles": [f"{spec['metric_family']}_{spec['metric_role']}"],
                "disallowed_claim_roles": _adbe_disallowed_roles(str(spec["metric_family"]), str(spec["metric_role"])),
                "review_note": (
                    "Reviewed Adobe Digital Media fact. Keep ARR proxy, revenue level, period-change amount, "
                    "and percentage growth roles separate."
                ),
            }
        )
    context_rows = _adbe_context_rows(facts, evidence_by_id)
    _write_jsonl(reviewed_context_dir / f"{ADBE_CASE}.jsonl", context_rows)
    (reviewed_facts_dir / f"{ADBE_CASE}.json").write_text(
        json.dumps(
            {
                "schema_version": "sec_gold_facts_reviewed_v0.1",
                "case_id": ADBE_CASE,
                "benchmark_version": "sec_benchmark_v2_pilot_plus2",
                "review_status": "reviewed_approved_single_case",
                "review_scope": {
                    "companies": ["ADBE"],
                    "years": [2023, 2024, 2025],
                    "metric_families": ["arr_or_recurring_proxy", "digital_media_revenue"],
                    "metric_roles": ["total_value", "period_change_amount", "percentage_rate"],
                    "source_policy": "SEC_ONLY",
                    "allowed_filing_types": ["10-K"],
                    "source_basis": "reviewed Adobe MD&A statements for Digital Media ARR, revenue, increases, and growth rates",
                },
                "facts": facts,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "case_id": ADBE_CASE,
        "fact_count": len(facts),
        "context_row_count": len(context_rows),
        "context_path": str(reviewed_context_dir / f"{ADBE_CASE}.jsonl"),
        "facts_path": str(reviewed_facts_dir / f"{ADBE_CASE}.json"),
    }


def _adbe_context_rows(
    facts: list[dict[str, Any]],
    evidence_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key, source in ADBE_SOURCES.items():
        evidence = evidence_by_id.get(str(source["source_evidence_id"]), {})
        rows.append(
            {
                "schema_version": "sec_gold_context_reviewed_v0.1",
                "case_id": ADBE_CASE,
                "review_status": "reviewed_keep",
                "gold_role": "core_period_change_source" if "digital_media" in key else "support_revenue_definition_source",
                "source_kind": "reviewed_text_excerpt",
                "source_key": key,
                "source_evidence_id": source["source_evidence_id"],
                "ticker": source["ticker"],
                "fiscal_year": source["fiscal_year"],
                "source_type": evidence.get("source_type") or "10-K",
                "section": source["section"],
                "source_url": evidence.get("source_url"),
                "local_path": evidence.get("local_path"),
                "text": source["text"],
                "review_note": "Reviewed compact MD&A source for ADBE v2 pilot plus2.",
            }
        )
    for fact in facts:
        rows.append(
            {
                "schema_version": "sec_gold_context_reviewed_v0.1",
                "case_id": ADBE_CASE,
                "review_status": "reviewed_keep",
                "gold_role": "core_structured_fact",
                "source_kind": "reviewed_metric_statement",
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
                    f"ADBE fiscal {fact['period']} {fact['metric_name']} "
                    f"({fact['metric_role']}): {fact['raw_value']}; metric_id={fact['metric_id']}."
                ),
            }
        )
    rows.append(
        {
            "schema_version": "sec_gold_context_reviewed_v0.1",
            "case_id": ADBE_CASE,
            "review_status": "reviewed_keep",
            "gold_role": "arr_proxy_caveat",
            "source_kind": "reviewed_source_policy_note",
            "source_evidence_id": "REVIEW_NOTE_ADBE_ARR_PROXY_NOT_REVENUE",
            "ticker": "ADBE",
            "fiscal_year": 2025,
            "source_type": "10-K",
            "section": "review_note",
            "source_url": None,
            "local_path": None,
            "text": (
                "Reviewed caveat: Adobe ARR is a management performance metric and should be viewed independently "
                "of revenue, deferred revenue, and remaining performance obligations. Dollar increase amounts are "
                "period-change amounts, not total level values."
            ),
            "review_note": "Reviewed role-separation caveat for ADBE v2 pilot plus2.",
        }
    )
    return rows


def _write_peer_artifacts(reviewed_context_dir: Path, reviewed_facts_dir: Path) -> dict[str, Any]:
    source_facts_path = reviewed_facts_dir / f"{SOURCE_PEER_CASE}.json"
    source_context_path = reviewed_context_dir / f"{SOURCE_PEER_CASE}.jsonl"
    source_payload = _read_json(source_facts_path)
    facts = []
    for idx, fact in enumerate(source_payload.get("facts") or [], start=1):
        cloned = dict(fact)
        cloned["fact_id"] = f"{PEER_CASE}_FACT_REVIEWED_{idx:04d}"
        cloned["selection_method"] = "manual_review_reused_from_v1_1_ads_ai_infra_case"
        cloned["review_note"] = (
            str(cloned.get("review_note") or "")
            + " Reused for v2 pilot plus2 local dual-sided peer support."
        ).strip()
        facts.append(cloned)
    context_rows = []
    for row in _read_jsonl(source_context_path):
        cloned = dict(row)
        cloned["case_id"] = PEER_CASE
        cloned["review_note"] = (
            str(cloned.get("review_note") or "")
            + " Reused for v2 pilot plus2 local dual-sided peer support."
        ).strip()
        context_rows.append(cloned)
    _write_jsonl(reviewed_context_dir / f"{PEER_CASE}.jsonl", context_rows)
    (reviewed_facts_dir / f"{PEER_CASE}.json").write_text(
        json.dumps(
            {
                "schema_version": "sec_gold_facts_reviewed_v0.1",
                "case_id": PEER_CASE,
                "benchmark_version": "sec_benchmark_v2_pilot_plus2",
                "review_status": "reviewed_approved_single_case",
                "review_scope": {
                    "companies": ["GOOGL", "META"],
                    "years": [2023, 2024, 2025],
                    "metric_families": ["advertising_revenue", "operating_income", "capex"],
                    "metric_roles": ["total_value"],
                    "source_policy": "SEC_ONLY",
                    "allowed_filing_types": ["10-K"],
                    "source_basis": "reused reviewed v1.1 ADS/AI infrastructure evidence for stricter v2 peer-support audit",
                },
                "facts": facts,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "case_id": PEER_CASE,
        "fact_count": len(facts),
        "context_row_count": len(context_rows),
        "context_path": str(reviewed_context_dir / f"{PEER_CASE}.jsonl"),
        "facts_path": str(reviewed_facts_dir / f"{PEER_CASE}.json"),
    }


def _approval_payload() -> dict[str, Any]:
    return {
        "schema_version": "sec_gold_manual_review_v0.2",
        "review_scope": {
            "gold_context_dir": "eval/sec_cases/reviewed_gold_context",
            "gold_facts_dir": "eval/sec_cases/reviewed_gold_facts",
            "case_count": len(PLUS2_REVIEWED_CASE_IDS),
            "reviewed_case_ids": PLUS2_REVIEWED_CASE_IDS,
            "pipeline_only_trap_case_ids": [TRAP_CASE],
        },
        "review_decision": {
            "overall_status": "partial_approved_for_mainline_scored_benchmark",
            "allowed_next_step": "case_filtered_gold_context_and_pipeline_plus2_smoke",
            "blocked_next_step": "full_benchmark_mainline_scored_test",
            "reason": (
                "The original five v2 pilot non-trap cases remain approved, and two reviewed plus2 cases are "
                "approved for a case-filtered diagnostic smoke. The Microsoft/YouTube trap remains pipeline-only."
            ),
        },
        "case_reviews": [
            *_base_case_reviews(),
            {
                "case_id": ADBE_CASE,
                "decision": "approved_for_gold_context_mode",
                "mainline_status": "can_enter_case_filtered_scored_gold_context_smoke",
                "evidence_assessment": (
                    "Reviewed context keeps Adobe Digital Media ARR, revenue, absolute increase amounts, percentage "
                    "growth, and ARR role caveats from SEC 10-K MD&A."
                ),
                "fact_assessment": "Reviewed facts contain 12 role-separated cells/statements, including 3 period-change amount rows.",
                "required_fix": (
                    "Before promotion, semantic contract gate must check that period-change amounts are not used as level values."
                ),
            },
            {
                "case_id": PEER_CASE,
                "decision": "approved_for_gold_context_mode",
                "mainline_status": "can_enter_case_filtered_scored_gold_context_smoke",
                "evidence_assessment": (
                    "Reviewed context reuses the v1.1 ADS/AI infrastructure case to test stricter local dual-sided "
                    "support in Alphabet versus Meta peer-comparison conclusions."
                ),
                "fact_assessment": "Reviewed facts contain Alphabet and Meta advertising revenue, operating income, and capex cells.",
                "required_fix": (
                    "Before promotion, answer organization should avoid one-sided local peer-comparison support warnings."
                ),
            },
        ],
        "gate": {
            "can_enter_full_mainline_scored_test": False,
            "can_enter_case_filtered_gold_context_scored_smoke": True,
            "approved_case_ids": PLUS2_REVIEWED_CASE_IDS,
            "pipeline_only_trap_case_ids": [TRAP_CASE],
        },
    }


def _base_case_reviews() -> list[dict[str, Any]]:
    approval_path = REPO_ROOT / "reports" / "quality" / "sec_benchmark_v2_pilot_reviewed_gold_partial_approval.json"
    approval = _read_json(approval_path)
    return [
        row
        for row in approval.get("case_reviews") or []
        if str(row.get("case_id") or "") in set(BASE_REVIEWED_CASE_IDS + [TRAP_CASE])
    ]


def _load_evidence_index() -> dict[str, dict[str, Any]]:
    return base_pilot._load_evidence_index()


def _load_metric_index_by_source_raw() -> dict[tuple[str, str], dict[str, Any]]:
    path = REPO_ROOT / "data" / "processed_private" / "structured_objects" / "sec_tech_10k_metrics.jsonl"
    rows = _read_jsonl(path) if path.exists() else []
    index: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        source_id = str(row.get("source_evidence_id") or "")
        raw = _normalize_raw_value(row.get("raw_value"))
        if not source_id or not raw:
            continue
        index.setdefault((source_id, raw), row)
    return index


def _normalize_raw_value(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split()).lower()


def _adbe_disallowed_roles(metric_family: str, metric_role: str) -> list[str]:
    families = [
        "arr_or_recurring_proxy",
        "digital_media_revenue",
        "subscription_revenue",
        "rpo",
        "deferred_revenue",
        "recognized_revenue",
        "market_share",
    ]
    roles = ["total_value", "period_change_amount", "percentage_rate"]
    disallowed = [item for item in families if item != metric_family]
    disallowed.extend(role for role in roles if role != metric_role)
    return disallowed


def _display_value_en(value: float, unit: str) -> str:
    if unit == "usd_billions":
        return f"${value:.2f} billion"
    if unit == "usd_millions":
        return f"${value / 1000:.3f} billion"
    if unit == "percent":
        return f"{value:g}%"
    return str(value)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
