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

from scripts import build_sec_benchmark_v2_pilot_plus2_reviewed_gold as plus2  # noqa: E402


BASE_MANIFEST = REPO_ROOT / "eval" / "sec_cases" / "test_cases_v2_pilot_plus2_seed.jsonl"
PLUS3_MANIFEST = REPO_ROOT / "eval" / "sec_cases" / "test_cases_v2_pilot_plus3_seed.jsonl"

SNOW_CASE = "SNOW_NRR_RPO_GROWTH_2023_2025_001"
SNOW_SOURCE_EVIDENCE_ID = "SNOW_2025_10K_ITEM7_BLOCK_0003_PART_01_OF_02"
TRAP_CASE = plus2.TRAP_CASE

BASE_REVIEWED_CASE_IDS = list(plus2.PLUS2_REVIEWED_CASE_IDS)
PLUS3_REVIEWED_CASE_IDS = [*BASE_REVIEWED_CASE_IDS, SNOW_CASE]


SNOW_FACT_SPECS: list[dict[str, Any]] = [
    {
        "period": "2023",
        "metric_name": "Product revenue",
        "metric_family": "product_revenue",
        "metric_role": "total_value",
        "raw_value": "$ 1,938.8",
        "value": 1938.8,
        "unit": "usd_millions",
        "object_id": "SNOW_2025_10K_ITEM7_BLOCK_0003_PART_01_OF_02_METRIC_TABLE_7A4C0776",
        "row_label": "Product revenue (in millions)",
        "column_label": "2023",
    },
    {
        "period": "2024",
        "metric_name": "Product revenue",
        "metric_family": "product_revenue",
        "metric_role": "total_value",
        "raw_value": "$ 2,666.8",
        "value": 2666.8,
        "unit": "usd_millions",
        "object_id": "SNOW_2025_10K_ITEM7_BLOCK_0003_PART_01_OF_02_METRIC_TABLE_8B775A1B",
        "row_label": "Product revenue (in millions)",
        "column_label": "2024",
    },
    {
        "period": "2025",
        "metric_name": "Product revenue",
        "metric_family": "product_revenue",
        "metric_role": "total_value",
        "raw_value": "$ 3,462.4",
        "value": 3462.4,
        "unit": "usd_millions",
        "object_id": "SNOW_2025_10K_ITEM7_BLOCK_0003_PART_01_OF_02_METRIC_TABLE_7FB5C40E",
        "row_label": "Product revenue (in millions)",
        "column_label": "2025",
    },
    {
        "period": "2023",
        "metric_name": "Net revenue retention rate",
        "metric_family": "net_revenue_retention",
        "metric_role": "percentage_rate",
        "raw_value": "158 %",
        "value": 158.0,
        "unit": "percent",
        "object_id": "SNOW_2025_10K_ITEM7_BLOCK_0003_PART_01_OF_02_METRIC_TABLE_C48E894A",
        "row_label": "Net revenue retention rate (4)",
        "column_label": "January 31, 2023",
    },
    {
        "period": "2024",
        "metric_name": "Net revenue retention rate",
        "metric_family": "net_revenue_retention",
        "metric_role": "percentage_rate",
        "raw_value": "131 %",
        "value": 131.0,
        "unit": "percent",
        "object_id": "SNOW_2025_10K_ITEM7_BLOCK_0003_PART_01_OF_02_METRIC_TABLE_DB2C7703",
        "row_label": "Net revenue retention rate (4)",
        "column_label": "January 31, 2024",
    },
    {
        "period": "2025",
        "metric_name": "Net revenue retention rate",
        "metric_family": "net_revenue_retention",
        "metric_role": "percentage_rate",
        "raw_value": "126 %",
        "value": 126.0,
        "unit": "percent",
        "object_id": "SNOW_2025_10K_ITEM7_BLOCK_0003_PART_01_OF_02_METRIC_TABLE_35E7E1BE",
        "row_label": "Net revenue retention rate (4)",
        "column_label": "January 31, 2025",
    },
    {
        "period": "2023",
        "metric_name": "Remaining performance obligations",
        "metric_family": "rpo",
        "metric_role": "total_value",
        "raw_value": "$ 3,660.5",
        "value": 3660.5,
        "unit": "usd_millions",
        "object_id": "SNOW_2025_10K_ITEM7_BLOCK_0003_PART_01_OF_02_METRIC_TABLE_FD0F3333",
        "row_label": "Remaining performance obligations (in millions) (5)",
        "column_label": "January 31, 2023",
    },
    {
        "period": "2024",
        "metric_name": "Remaining performance obligations",
        "metric_family": "rpo",
        "metric_role": "total_value",
        "raw_value": "$ 5,174.7",
        "value": 5174.7,
        "unit": "usd_millions",
        "object_id": "SNOW_2025_10K_ITEM7_BLOCK_0003_PART_01_OF_02_METRIC_TABLE_77427F31",
        "row_label": "Remaining performance obligations (in millions) (5)",
        "column_label": "January 31, 2024",
    },
    {
        "period": "2025",
        "metric_name": "Remaining performance obligations",
        "metric_family": "rpo",
        "metric_role": "total_value",
        "raw_value": "$ 6,867.5",
        "value": 6867.5,
        "unit": "usd_millions",
        "object_id": "SNOW_2025_10K_ITEM7_BLOCK_0003_PART_01_OF_02_METRIC_TABLE_034077CC",
        "row_label": "Remaining performance obligations (in millions) (5)",
        "column_label": "January 31, 2025",
    },
    {
        "period": "2025",
        "metric_name": "RPO expected recognition within next twelve months",
        "metric_family": "rpo_recognition_timing",
        "metric_role": "percentage_rate",
        "raw_value": "48%",
        "value": 48.0,
        "unit": "percent",
        "object_id": "SNOW_2025_10K_ITEM7_BLOCK_0003_PART_01_OF_02_METRIC_SENT_F756A5EA",
        "row_label": "RPO expected recognition",
        "column_label": "twelve months ending January 31, 2026",
    },
]


def main() -> None:
    reviewed_context_dir = REPO_ROOT / "eval" / "sec_cases" / "reviewed_gold_context"
    reviewed_facts_dir = REPO_ROOT / "eval" / "sec_cases" / "reviewed_gold_facts"
    report_dir = REPO_ROOT / "reports" / "quality"
    reviewed_context_dir.mkdir(parents=True, exist_ok=True)
    reviewed_facts_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    if not BASE_MANIFEST.exists():
        raise SystemExit(f"Missing base plus2 manifest: {BASE_MANIFEST}")

    evidence_by_id = plus2._load_evidence_index()
    _write_manifest()
    snow_summary = _write_snow_artifacts(reviewed_context_dir, reviewed_facts_dir, evidence_by_id)

    approval_path = report_dir / "sec_benchmark_v2_pilot_plus3_reviewed_gold_partial_approval.json"
    approval_path.write_text(json.dumps(_approval_payload(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    build_report_path = report_dir / "sec_benchmark_v2_pilot_plus3_reviewed_gold_build_report.json"
    build_report = {
        "schema_version": "sec_v2_pilot_plus3_reviewed_gold_build_report_v0.1",
        "base_manifest": str(BASE_MANIFEST),
        "plus3_manifest": str(PLUS3_MANIFEST),
        "base_reviewed_case_count": len(BASE_REVIEWED_CASE_IDS),
        "plus3_reviewed_case_count": len(PLUS3_REVIEWED_CASE_IDS),
        "trap_case_not_gold_context": TRAP_CASE,
        "approval_path": str(approval_path),
        "new_cases": [snow_summary],
        "bge_m3_policy": {
            "final_context_selector": "BAAI/bge-reranker-v2-m3",
            "bm25_role": "candidate_generator_only",
            "bm25_only_allowed": False,
        },
    }
    build_report_path.write_text(json.dumps(build_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "plus3_manifest": str(PLUS3_MANIFEST),
                "plus3_reviewed_case_count": len(PLUS3_REVIEWED_CASE_IDS),
                "new_fact_count": snow_summary["fact_count"],
                "new_context_row_count": snow_summary["context_row_count"],
                "approval_path": str(approval_path),
                "build_report_path": str(build_report_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def _write_manifest() -> None:
    rows = plus2._read_jsonl(BASE_MANIFEST)
    existing = {str(row.get("case_id") or "") for row in rows}
    additions = [] if SNOW_CASE in existing else [_snow_manifest_case()]
    plus2._write_jsonl(PLUS3_MANIFEST, [*rows, *additions])


def _snow_manifest_case() -> dict[str, Any]:
    return {
        "schema_version": "sec_eval_case_v1",
        "benchmark_version": "sec_benchmark_v1",
        "case_id": SNOW_CASE,
        "origin": "v2_pilot_plus3_reviewed_expansion",
        "case_family": "v2_pilot_plus3",
        "test_objective": (
            "Test Snowflake product revenue growth, NRR, RPO, and consumption-based visibility caveats as an "
            "independent reviewed v2 case."
        ),
        "case_group": "diagnostic_stress",
        "level": "L3",
        "companies": ["SNOW"],
        "years": [2023, 2024, 2025],
        "filing_types": ["10-K"],
        "task_type": "single_company_consumption_visibility_metric_separation",
        "prompt": (
            "Using Snowflake's fiscal 2023-2025 SEC 10-K filings, summarize product revenue growth, net revenue "
            "retention, and remaining performance obligations. Keep product revenue, NRR percentage, RPO, and RPO "
            "recognition timing separate, cite every numeric value, and explain how consumption-based revenue "
            "recognition limits revenue visibility."
        ),
        "allowed_sources": ["SEC"],
        "source_policy": "SEC_ONLY",
        "evaluation_modes": ["gold_context", "pipeline_context"],
        "expected_sections": [
            "Item 7. Management's Discussion and Analysis",
            "Item 8. Financial Statements",
        ],
        "gold_points": [
            "Must cite Snowflake product revenue for 2023, 2024, and 2025.",
            "Must cite net revenue retention rate for 2023, 2024, and 2025.",
            "Must cite RPO for 2023, 2024, and 2025 and the 2025 next-twelve-months recognition percentage.",
            "Must keep product revenue, NRR, RPO, and RPO recognition timing separate.",
            "Must explain that consumption-based recognition limits timing visibility and RPO is not guaranteed recognized revenue.",
        ],
        "numeric_checks": [
            {
                "metric": "Snowflake product revenue",
                "metric_families": ["product_revenue"],
                "metric_roles": ["total_value"],
                "companies": ["SNOW"],
                "years": [2023, 2024, 2025],
            },
            {
                "metric": "Snowflake net revenue retention rate",
                "metric_families": ["net_revenue_retention"],
                "metric_roles": ["percentage_rate"],
                "companies": ["SNOW"],
                "years": [2023, 2024, 2025],
            },
            {
                "metric": "Snowflake RPO",
                "metric_families": ["rpo"],
                "metric_roles": ["total_value"],
                "companies": ["SNOW"],
                "years": [2023, 2024, 2025],
            },
            {
                "metric": "Snowflake 2025 RPO recognition timing",
                "metric_families": ["rpo_recognition_timing"],
                "metric_roles": ["percentage_rate"],
                "companies": ["SNOW"],
                "years": [2025],
            },
        ],
        "required_caveats": [
            {
                "id": "consumption_limits_revenue_visibility",
                "description": "Must state Snowflake recognizes revenue on consumption and has less timing visibility than ratable subscriptions.",
                "where": "answer",
                "all_of_any": [
                    ["consumption", "消费", "usage"],
                    ["visibility", "可见性", "timing"],
                    ["not ratably", "not have", "limit", "限制", "不"],
                ],
            },
            {
                "id": "rpo_not_guaranteed_revenue",
                "description": "Must caveat that RPO is contracted future revenue not yet recognized and not guaranteed recognized revenue.",
                "where": "caveats",
                "all_of_any": [
                    ["RPO", "remaining performance obligations"],
                    ["recognized revenue", "确认收入", "revenue"],
                    ["not", "not yet", "不能", "不是", "不等同"],
                ],
            },
            {
                "id": "nrr_is_percentage_not_revenue",
                "description": "Must keep NRR percentage separate from dollar revenue/RPO amounts.",
                "where": "answer",
                "all_of_any": [
                    ["NRR", "net revenue retention", "留存"],
                    ["percentage", "%", "百分比"],
                    ["revenue", "RPO", "separate", "分开", "不同"],
                ],
            },
        ],
        "disallowed_claims": [
            {
                "id": "rpo_equals_revenue",
                "description": "Do not equate RPO with recognized revenue.",
                "patterns": ["RPO equals revenue", "RPO is recognized revenue", "RPO 等同于收入", "RPO 是确认收入"],
                "allow_if_any_near": ["not", "not yet", "different", "separate", "不", "不能", "不是"],
            },
            {
                "id": "nrr_as_dollar_value",
                "description": "Do not present NRR as a dollar amount.",
                "patterns": ["NRR dollars", "NRR revenue dollars", "NRR 金额", "留存收入金额"],
                "allow_if_any_near": ["not", "percentage", "%", "不", "百分比"],
            },
            {
                "id": "consumption_revenue_ratable_subscription",
                "description": "Do not describe Snowflake product revenue as standard ratable subscription revenue.",
                "patterns": ["standard ratable subscription revenue", "标准订阅收入", "ratably over the term"],
                "allow_if_any_near": ["not", "does not", "不", "不是", "不能"],
            },
        ],
        "hard_gates": [
            "source_resolver",
            "citation_validator",
            "exact_value_ledger",
            "metric_family_context_gate",
            "unsupported_claim_gate",
            "unit_scale_gate",
        ],
        "hallucination_traps": [
            "Do not equate RPO with recognized revenue.",
            "Do not treat NRR as a dollar revenue amount.",
            "Do not describe consumption-based product revenue as standard ratable subscription revenue.",
            "Do not infer guaranteed future revenue from RPO or NRR.",
        ],
        "failure_types": [
            "retrieval_miss",
            "numeric_error",
            "unit_error",
            "metric_role_error",
            "proxy_as_direct_metric",
            "percentage_change_as_absolute_value",
            "missing_caveat",
        ],
        "score_weights": {"retrieval": 2, "factuality": 3, "coverage": 2, "synthesis": 2, "citation": 1},
        "gold_context_status": "needs_annotation",
    }


def _write_snow_artifacts(
    reviewed_context_dir: Path,
    reviewed_facts_dir: Path,
    evidence_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    evidence = evidence_by_id.get(SNOW_SOURCE_EVIDENCE_ID, {})
    facts = [_snow_fact(idx, spec) for idx, spec in enumerate(SNOW_FACT_SPECS, start=1)]
    context_rows = _snow_context_rows(facts, evidence)

    plus2._write_jsonl(reviewed_context_dir / f"{SNOW_CASE}.jsonl", context_rows)
    (reviewed_facts_dir / f"{SNOW_CASE}.json").write_text(
        json.dumps(
            {
                "schema_version": "sec_gold_facts_reviewed_v0.1",
                "case_id": SNOW_CASE,
                "benchmark_version": "sec_benchmark_v2_pilot_plus3",
                "review_status": "reviewed_approved_single_case",
                "review_scope": {
                    "companies": ["SNOW"],
                    "years": [2023, 2024, 2025],
                    "metric_families": ["product_revenue", "net_revenue_retention", "rpo", "rpo_recognition_timing"],
                    "metric_roles": ["total_value", "percentage_rate"],
                    "source_policy": "SEC_ONLY",
                    "allowed_filing_types": ["10-K"],
                    "source_basis": (
                        "reviewed Snowflake fiscal 2025 10-K key business metrics table and consumption/RPO caveat text"
                    ),
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
        "case_id": SNOW_CASE,
        "fact_count": len(facts),
        "context_row_count": len(context_rows),
        "context_path": str(reviewed_context_dir / f"{SNOW_CASE}.jsonl"),
        "facts_path": str(reviewed_facts_dir / f"{SNOW_CASE}.json"),
    }


def _snow_fact(idx: int, spec: dict[str, Any]) -> dict[str, Any]:
    metric_family = str(spec["metric_family"])
    metric_role = str(spec["metric_role"])
    period = str(spec["period"])
    return {
        "fact_id": f"{SNOW_CASE}_FACT_REVIEWED_{idx:04d}",
        "review_status": "reviewed_keep",
        "selection_method": "manual_review_sec_key_business_metrics_table",
        "metric_id": f"SNOW_{period}_{metric_family}_{metric_role}",
        "ticker": "SNOW",
        "fiscal_year": int(period),
        "period": period,
        "metric_name": spec["metric_name"],
        "metric_family": metric_family,
        "metric_role": metric_role,
        "raw_value": spec["raw_value"],
        "value": spec["value"],
        "unit": spec["unit"],
        "display_value_en": plus2._display_value_en(float(spec["value"]), str(spec["unit"])),
        "object_id": spec["object_id"],
        "source_evidence_id": SNOW_SOURCE_EVIDENCE_ID,
        "section": "Item 7. Management's Discussion and Analysis",
        "row_label": spec["row_label"],
        "column_label": spec["column_label"],
        "allowed_claim_roles": [f"{metric_family}_{metric_role}"],
        "disallowed_claim_roles": _snow_disallowed_roles(metric_family, metric_role),
        "review_note": (
            "Reviewed Snowflake key-business-metrics fact. Keep product revenue dollars, NRR percentage, "
            "RPO dollars, and RPO recognition timing percentage separate."
        ),
    }


def _snow_context_rows(facts: list[dict[str, Any]], evidence: dict[str, Any]) -> list[dict[str, Any]]:
    base_source = {
        "source_evidence_id": SNOW_SOURCE_EVIDENCE_ID,
        "ticker": "SNOW",
        "fiscal_year": 2025,
        "source_type": evidence.get("source_type") or "10-K",
        "section": "Item 7. Management's Discussion and Analysis",
        "source_url": evidence.get("source_url"),
        "local_path": evidence.get("local_path"),
    }
    rows: list[dict[str, Any]] = [
        {
            "schema_version": "sec_gold_context_reviewed_v0.1",
            "case_id": SNOW_CASE,
            "review_status": "reviewed_keep",
            "gold_role": "core_key_business_metrics_table",
            "source_kind": "table_object",
            "source_key": "SNOW_2025_key_business_metrics",
            "object_id": "SNOW_2025_10K_ITEM7_BLOCK_0003_PART_01_OF_02_TABLE_0B6858E2",
            **base_source,
            "text": (
                "Snowflake fiscal 2025 10-K key business metrics table. Product revenue (USD millions): "
                "2025: 3,462.4; 2024: 2,666.8; 2023: 1,938.8. Net revenue retention rate: "
                "2025: 126%; 2024: 131%; 2023: 158%. Remaining performance obligations (USD millions): "
                "2025: 6,867.5; 2024: 5,174.7; 2023: 3,660.5."
            ),
            "review_note": "Reviewed compact table source for Snowflake product revenue, NRR, and RPO target cells.",
        }
    ]
    for fact in facts:
        rows.append(
            {
                "schema_version": "sec_gold_context_reviewed_v0.1",
                "case_id": SNOW_CASE,
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
                    f"SNOW fiscal {fact['period']} {fact['metric_name']} "
                    f"({fact['metric_role']}): {fact['raw_value']}; metric_id={fact['metric_id']}."
                ),
            }
        )
    rows.extend(
        [
            {
                "schema_version": "sec_gold_context_reviewed_v0.1",
                "case_id": SNOW_CASE,
                "review_status": "reviewed_keep",
                "gold_role": "rpo_recognition_timing_caveat",
                "source_kind": "reviewed_text_excerpt",
                **base_source,
                "text": (
                    "Snowflake states that as of January 31, 2025 remaining performance obligations were "
                    "approximately $6.9 billion, with approximately 48% expected to be recognized as revenue "
                    "in the twelve months ending January 31, 2026 based on historical customer consumption patterns."
                ),
                "review_note": "Reviewed RPO timing statement for Snowflake v2 plus3.",
            },
            {
                "schema_version": "sec_gold_context_reviewed_v0.1",
                "case_id": SNOW_CASE,
                "review_status": "reviewed_keep",
                "gold_role": "consumption_model_caveat",
                "source_kind": "reviewed_text_excerpt",
                **base_source,
                "text": (
                    "Snowflake states customers have flexibility in consumption and that it generally recognizes "
                    "revenue on consumption, not ratably over the contract term; therefore it does not have the "
                    "visibility into timing of revenue recognition from any particular customer contract that typical "
                    "subscription-based software companies may have."
                ),
                "review_note": "Reviewed consumption-recognition caveat for Snowflake v2 plus3.",
            },
            {
                "schema_version": "sec_gold_context_reviewed_v0.1",
                "case_id": SNOW_CASE,
                "review_status": "reviewed_keep",
                "gold_role": "metric_definition_caveat",
                "source_kind": "reviewed_source_policy_note",
                "source_evidence_id": "REVIEW_NOTE_SNOW_NRR_RPO_METRIC_SEPARATION",
                "ticker": "SNOW",
                "fiscal_year": 2025,
                "source_type": "10-K",
                "section": "review_note",
                "source_url": None,
                "local_path": None,
                "text": (
                    "Reviewed caveat: product revenue is a dollar revenue metric, NRR is a percentage key business "
                    "metric, and RPO is contracted future revenue not yet recognized. These metrics should not be "
                    "treated as interchangeable or as guaranteed future recognized revenue."
                ),
                "review_note": "Reviewed role-separation caveat for Snowflake v2 plus3.",
            },
        ]
    )
    return rows


def _snow_disallowed_roles(metric_family: str, metric_role: str) -> list[str]:
    families = [
        "product_revenue",
        "net_revenue_retention",
        "rpo",
        "rpo_recognition_timing",
        "recognized_revenue",
        "subscription_revenue",
        "arr_or_recurring_proxy",
        "billings",
        "deferred_revenue",
    ]
    roles = ["total_value", "percentage_rate", "period_change_amount"]
    disallowed = [item for item in families if item != metric_family]
    disallowed.extend(role for role in roles if role != metric_role)
    return disallowed


def _approval_payload() -> dict[str, Any]:
    return {
        "schema_version": "sec_gold_manual_review_v0.2",
        "review_scope": {
            "gold_context_dir": "eval/sec_cases/reviewed_gold_context",
            "gold_facts_dir": "eval/sec_cases/reviewed_gold_facts",
            "case_count": len(PLUS3_REVIEWED_CASE_IDS),
            "reviewed_case_ids": PLUS3_REVIEWED_CASE_IDS,
            "pipeline_only_trap_case_ids": [TRAP_CASE],
        },
        "review_decision": {
            "overall_status": "partial_approved_for_mainline_scored_benchmark",
            "allowed_next_step": "case_filtered_gold_context_and_pipeline_plus3_smoke",
            "blocked_next_step": "full_benchmark_mainline_scored_test",
            "reason": (
                "The plus2 reviewed cases remain approved, and one Snowflake NRR/RPO case is approved for a "
                "case-filtered diagnostic smoke. The Microsoft/YouTube trap remains pipeline-only."
            ),
        },
        "case_reviews": [
            *_base_case_reviews(),
            {
                "case_id": SNOW_CASE,
                "decision": "approved_for_gold_context_mode",
                "mainline_status": "can_enter_case_filtered_scored_gold_context_smoke",
                "evidence_assessment": (
                    "Reviewed context uses Snowflake fiscal 2025 10-K key business metrics table and consumption/RPO "
                    "caveat text to cover 2023-2025 product revenue, NRR, RPO, and 2025 RPO recognition timing."
                ),
                "fact_assessment": (
                    "Reviewed facts contain 10 role-separated cells/statements: 3 product revenue dollar cells, "
                    "3 NRR percentage cells, 3 RPO dollar cells, and 1 RPO recognition timing percentage."
                ),
                "required_fix": (
                    "Before promotion, semantic contract gate must catch RPO-as-recognized-revenue and NRR-as-dollar misuse."
                ),
            },
        ],
        "gate": {
            "can_enter_full_mainline_scored_test": False,
            "can_enter_case_filtered_gold_context_scored_smoke": True,
            "approved_case_ids": PLUS3_REVIEWED_CASE_IDS,
            "pipeline_only_trap_case_ids": [TRAP_CASE],
        },
    }


def _base_case_reviews() -> list[dict[str, Any]]:
    approval_path = REPO_ROOT / "reports" / "quality" / "sec_benchmark_v2_pilot_plus2_reviewed_gold_partial_approval.json"
    approval = plus2._read_json(approval_path)
    return [
        row
        for row in approval.get("case_reviews") or []
        if str(row.get("case_id") or "") in set(BASE_REVIEWED_CASE_IDS + [TRAP_CASE])
    ]


if __name__ == "__main__":
    main()
