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

from scripts import build_sec_benchmark_v2_pilot_plus5_reviewed_gold as plus5  # noqa: E402


BASE_MANIFEST = REPO_ROOT / "eval" / "sec_cases" / "test_cases_v2_pilot_plus5_seed.jsonl"
PLUS6_MANIFEST = REPO_ROOT / "eval" / "sec_cases" / "test_cases_v2_pilot_plus6_seed.jsonl"

BROAD_CLOUD_CASE = plus5.BROAD_CLOUD_CASE
MSFT_CASE = "MSFT_CLOUD_AI_MARGIN_PROXY_2023_2025_001"
TRAP_CASE = plus5.TRAP_CASE

BASE_REVIEWED_CASE_IDS = list(plus5.PLUS5_REVIEWED_CASE_IDS)
PLUS6_REVIEWED_CASE_IDS = [*BASE_REVIEWED_CASE_IDS, MSFT_CASE]
TARGET_TICKERS = {"MSFT"}


def main() -> None:
    reviewed_context_dir = REPO_ROOT / "eval" / "sec_cases" / "reviewed_gold_context"
    reviewed_facts_dir = REPO_ROOT / "eval" / "sec_cases" / "reviewed_gold_facts"
    report_dir = REPO_ROOT / "reports" / "quality"
    reviewed_context_dir.mkdir(parents=True, exist_ok=True)
    reviewed_facts_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    if not BASE_MANIFEST.exists():
        raise SystemExit(f"Missing base plus5 manifest: {BASE_MANIFEST}")

    _assert_source_artifacts_exist(reviewed_context_dir, reviewed_facts_dir)
    _write_manifest()
    case_summary = _write_split_artifacts(reviewed_context_dir, reviewed_facts_dir)

    approval_path = report_dir / "sec_benchmark_v2_pilot_plus6_reviewed_gold_partial_approval.json"
    approval_path.write_text(json.dumps(_approval_payload(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    build_report_path = report_dir / "sec_benchmark_v2_pilot_plus6_reviewed_gold_build_report.json"
    build_report = {
        "schema_version": "sec_v2_pilot_plus6_reviewed_gold_build_report_v0.1",
        "base_manifest": str(BASE_MANIFEST),
        "plus6_manifest": str(PLUS6_MANIFEST),
        "source_broad_case": BROAD_CLOUD_CASE,
        "base_reviewed_case_count": len(BASE_REVIEWED_CASE_IDS),
        "plus6_reviewed_case_count": len(PLUS6_REVIEWED_CASE_IDS),
        "trap_case_not_gold_context": TRAP_CASE,
        "approval_path": str(approval_path),
        "new_cases": [case_summary],
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
                "plus6_manifest": str(PLUS6_MANIFEST),
                "plus6_reviewed_case_count": len(PLUS6_REVIEWED_CASE_IDS),
                "new_fact_count": case_summary["fact_count"],
                "new_context_row_count": case_summary["context_row_count"],
                "approval_path": str(approval_path),
                "build_report_path": str(build_report_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def _assert_source_artifacts_exist(reviewed_context_dir: Path, reviewed_facts_dir: Path) -> None:
    missing = [
        path
        for path in [
            reviewed_context_dir / f"{BROAD_CLOUD_CASE}.jsonl",
            reviewed_facts_dir / f"{BROAD_CLOUD_CASE}.json",
        ]
        if not path.exists()
    ]
    if missing:
        raise SystemExit("Missing reviewed broad cloud artifacts: " + ", ".join(str(path) for path in missing))


def _write_manifest() -> None:
    rows = _read_jsonl(BASE_MANIFEST)
    output_rows: list[dict[str, Any]] = []
    replaced = False
    for row in rows:
        if str(row.get("case_id") or "") == MSFT_CASE:
            output_rows.append(_msft_manifest_case())
            replaced = True
        else:
            output_rows.append(row)
    if not replaced:
        output_rows.append(_msft_manifest_case())
    _write_jsonl(PLUS6_MANIFEST, output_rows)


def _msft_manifest_case() -> dict[str, Any]:
    return {
        "schema_version": "sec_eval_case_v1",
        "benchmark_version": "sec_benchmark_v1",
        "case_id": MSFT_CASE,
        "origin": "v2_pilot_plus6_reviewed_expansion",
        "case_family": "v2_pilot_plus6",
        "test_objective": (
            "Split the reviewed broad cloud profitability case into a Microsoft-only proxy/disclosure-boundary case "
            "that tests Microsoft Cloud broad revenue, Microsoft Cloud gross margin percentage, and AI infrastructure "
            "margin-pressure caveats without treating them as exact Azure or segment operating-income metrics."
        ),
        "case_group": "diagnostic_stress",
        "level": "L3",
        "companies": ["MSFT"],
        "years": [2023, 2024, 2025],
        "filing_types": ["10-K"],
        "task_type": "single_company_cloud_proxy_margin_boundary",
        "prompt": (
            "Using Microsoft's 2023-2025 SEC 10-K evidence, summarize Microsoft Cloud revenue and Microsoft Cloud "
            "gross margin percentage trends, and explain cloud or AI infrastructure margin pressure where disclosed. "
            "Preserve units, fiscal years, and citations for every metric. State clearly that Microsoft Cloud revenue "
            "and gross margin are broad proxy disclosures that include Azure and other commercial cloud properties, "
            "not exact Azure revenue, exact Azure gross margin, or cloud segment operating income."
        ),
        "allowed_sources": ["SEC"],
        "source_policy": "SEC_ONLY",
        "evaluation_modes": ["gold_context", "pipeline_context"],
        "expected_sections": [
            "Item 7. Management's Discussion and Analysis",
            "Item 8. Financial Statements",
            "Segment Information",
        ],
        "gold_points": [
            "Must cite Microsoft Cloud revenue for fiscal 2023, 2024, and 2025.",
            "Must cite Microsoft Cloud gross margin percentage for fiscal 2023, 2024, and 2025.",
            "Must explain that Microsoft Cloud is a broad disclosure including Azure and other commercial cloud properties.",
            "Must not treat Microsoft Cloud revenue as exact Azure revenue.",
            "Must not treat Microsoft Cloud gross margin as exact Azure gross margin or cloud segment operating income.",
            "Must include AI/cloud infrastructure margin-pressure context where supported.",
        ],
        "numeric_checks": [
            {
                "metric": "Microsoft Cloud revenue proxy and Microsoft Cloud gross margin percentage",
                "metric_families": ["cloud_revenue_proxy", "gross_margin"],
                "metric_roles": ["total_value", "percentage_rate"],
                "companies": ["MSFT"],
                "years": [2023, 2024, 2025],
            }
        ],
        "required_caveats": [
            {
                "id": "microsoft_cloud_broad_proxy_not_exact_azure",
                "description": "Must state Microsoft Cloud is a broad proxy including Azure and other commercial cloud properties, not exact Azure revenue.",
                "where": "answer",
                "all_of_any": [
                    ["Microsoft Cloud"],
                    ["Azure", "Microsoft 365", "LinkedIn", "Dynamics"],
                    ["proxy", "broad", "not exact Azure", "not the same", "广义", "口径", "不是", "不等同"],
                ],
            },
            {
                "id": "gross_margin_not_operating_income_or_azure_margin",
                "description": "Must keep Microsoft Cloud gross margin percentage separate from exact Azure gross margin and operating income.",
                "where": "answer",
                "all_of_any": [
                    ["gross margin", "毛利率"],
                    ["Azure gross margin", "operating income", "经营利润", "营业利润"],
                    ["not", "not the same", "separate", "不能", "不是", "不等同", "区分"],
                ],
            },
            {
                "id": "ai_infrastructure_margin_pressure",
                "description": "Must mention AI or cloud infrastructure cost/margin pressure where supported.",
                "where": "answer",
                "all_of_any": [
                    ["AI infrastructure", "cloud infrastructure", "AI 基础设施", "云基础设施"],
                    ["gross margin", "margin", "cost", "毛利率", "成本"],
                    ["pressure", "decrease", "offset", "impact", "压力", "下降", "影响"],
                ],
            },
        ],
        "disallowed_claims": [
            {
                "id": "microsoft_cloud_equals_exact_azure_revenue",
                "description": "Do not treat Microsoft Cloud revenue as exact Azure revenue.",
                "patterns": [
                    "Microsoft Cloud revenue is Azure revenue",
                    "Microsoft Cloud equals Azure revenue",
                    "Azure revenue was $111.6 billion",
                    "Azure revenue was $137.4 billion",
                    "Azure revenue was $168.9 billion",
                    "Azure 收入为 $111.6 billion",
                    "Azure 收入为 $137.4 billion",
                    "Azure 收入为 $168.9 billion",
                ],
                "allow_if_any_near": [
                    "not",
                    "not exact",
                    "not the same",
                    "proxy",
                    "broad",
                    "includes",
                    "不是",
                    "不等同",
                    "广义",
                    "口径",
                    "包含",
                ],
            },
            {
                "id": "microsoft_cloud_gross_margin_equals_azure_margin",
                "description": "Do not treat Microsoft Cloud gross margin percentage as exact Azure gross margin.",
                "patterns": [
                    "Azure gross margin was 72%",
                    "Azure gross margin was 71%",
                    "Azure gross margin was 69%",
                    "Azure 毛利率为 72%",
                    "Azure 毛利率为 71%",
                    "Azure 毛利率为 69%",
                    "Azure gross margin decreased to 69%",
                ],
                "allow_if_any_near": [
                    "not",
                    "not disclosed",
                    "not exact",
                    "Microsoft Cloud",
                    "proxy",
                    "不是",
                    "未披露",
                    "广义",
                    "口径",
                ],
            },
            {
                "id": "gross_margin_as_operating_income",
                "description": "Do not present Microsoft Cloud gross margin percentages as operating income dollars.",
                "patterns": [
                    "Microsoft Cloud operating income was 72%",
                    "Microsoft Cloud operating income was 71%",
                    "Microsoft Cloud operating income was 69%",
                    "Microsoft Cloud 经营利润率为 72%",
                    "Microsoft Cloud 营业利润为 69%",
                ],
                "allow_if_any_near": ["not", "gross margin", "不是", "毛利率", "百分比"],
            },
            {
                "id": "direct_peer_comparability_claim",
                "description": "Do not claim Microsoft Cloud proxy metrics are directly comparable with AWS or Google Cloud segment operating income.",
                "patterns": [
                    "directly comparable to AWS operating income",
                    "directly comparable to Google Cloud operating income",
                    "与 AWS operating income 直接可比",
                    "与 Google Cloud operating income 直接可比",
                    "与 AWS 经营利润直接可比",
                    "与 Google Cloud 经营利润直接可比",
                ],
                "allow_if_any_near": ["not", "not directly", "cannot", "不能", "不可", "不完全", "口径"],
            },
            {
                "id": "market_share_or_customer_growth_claim",
                "description": "Do not infer market share or customer growth from Microsoft Cloud revenue and gross margin alone.",
                "patterns": ["market share", "customer growth", "市场份额", "客户增长"],
                "allow_if_any_near": ["not", "does not prove", "does not represent", "不能", "不证明", "不代表", "未披露"],
            },
        ],
        "hard_gates": [
            "source_resolver",
            "citation_validator",
            "exact_value_ledger",
            "metric_family_context_gate",
            "comparability_gate",
            "conclusion_calibration_gate",
            "unsupported_claim_gate",
            "unit_scale_gate",
        ],
        "hallucination_traps": [
            "Do not treat Microsoft Cloud revenue as exact Azure revenue.",
            "Do not treat Microsoft Cloud gross margin percentage as exact Azure gross margin.",
            "Do not treat Microsoft Cloud gross margin percentage as cloud segment operating income.",
            "Do not directly compare Microsoft proxy metrics to AWS or Google Cloud segment operating income.",
        ],
        "failure_types": [
            "retrieval_miss",
            "numeric_error",
            "unit_error",
            "metric_role_error",
            "proxy_as_direct_metric",
            "non_comparable_metric_comparison",
            "unsupported_claim",
            "missing_caveat",
        ],
        "score_weights": {"retrieval": 2, "factuality": 3, "coverage": 2, "synthesis": 2, "citation": 1},
        "gold_context_status": "needs_annotation",
    }


def _write_split_artifacts(reviewed_context_dir: Path, reviewed_facts_dir: Path) -> dict[str, Any]:
    source_facts_path = reviewed_facts_dir / f"{BROAD_CLOUD_CASE}.json"
    source_context_path = reviewed_context_dir / f"{BROAD_CLOUD_CASE}.jsonl"
    target_facts_path = reviewed_facts_dir / f"{MSFT_CASE}.json"
    target_context_path = reviewed_context_dir / f"{MSFT_CASE}.jsonl"

    source_payload = _read_json(source_facts_path)
    source_facts = [
        fact
        for fact in source_payload.get("facts") or []
        if str(fact.get("review_status") or "") == "reviewed_keep"
        and str(fact.get("ticker") or "").upper() in TARGET_TICKERS
    ]
    source_facts.sort(key=lambda item: (int(item.get("fiscal_year") or 0), str(item.get("metric_family") or "")))

    target_facts = []
    for index, fact in enumerate(source_facts, start=1):
        rewritten = dict(fact)
        rewritten["fact_id"] = f"{MSFT_CASE}_FACT_R{index:04d}"
        rewritten["selection_query"] = "Microsoft Cloud revenue proxy and gross margin percentage"
        rewritten["review_note"] = f"Split from {BROAD_CLOUD_CASE}: {fact.get('review_note')}"
        target_facts.append(rewritten)

    facts_payload = {
        "schema_version": "sec_gold_facts_reviewed_v0.1",
        "case_id": MSFT_CASE,
        "benchmark_version": "sec_benchmark_v1",
        "review_status": "reviewed_approved",
        "review_scope": {
            "source_case_id": BROAD_CLOUD_CASE,
            "split_policy": "MSFT_only_proxy_rows_no_AMZN_GOOGL_segment_rows",
            "target_tickers": sorted(TARGET_TICKERS),
        },
        "numeric_checks": _msft_manifest_case()["numeric_checks"],
        "facts": target_facts,
    }
    target_facts_path.write_text(json.dumps(facts_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    context_rows = [
        row
        for row in _read_jsonl(source_context_path)
        if str(row.get("review_status") or "") == "reviewed_keep"
        and str(row.get("ticker") or "").upper() in TARGET_TICKERS
    ]
    context_rows.sort(
        key=lambda item: (
            int(item.get("fiscal_year") or 0),
            str(item.get("metric_family") or "zz_caveat"),
            str(item.get("gold_role") or ""),
        )
    )
    rewritten_context_rows: list[dict[str, Any]] = []
    for row in context_rows:
        rewritten = dict(row)
        rewritten["case_id"] = MSFT_CASE
        rewritten["review_note"] = f"Split from {BROAD_CLOUD_CASE}: {row.get('review_note')}"
        rewritten_context_rows.append(rewritten)
    _write_jsonl(target_context_path, rewritten_context_rows)

    _assert_split_contract(target_facts, rewritten_context_rows)
    return {
        "case_id": MSFT_CASE,
        "source_case_id": BROAD_CLOUD_CASE,
        "fact_count": len(target_facts),
        "context_row_count": len(rewritten_context_rows),
        "context_path": str(target_context_path),
        "facts_path": str(target_facts_path),
        "split_policy": "strict_MSFT_subset_excluding_AMZN_GOOGL_segment_rows",
        "metric_families": sorted({str(fact.get("metric_family") or "") for fact in target_facts}),
        "metric_roles": sorted({str(fact.get("metric_role") or "") for fact in target_facts}),
        "tickers": sorted({str(fact.get("ticker") or "") for fact in target_facts}),
        "source_evidence_count": len({str(fact.get("source_evidence_id") or "") for fact in target_facts}),
        "comparability_caveat_row_count": sum(
            1 for row in rewritten_context_rows if str(row.get("gold_role") or "") == "comparability_caveat"
        ),
    }


def _assert_split_contract(facts: list[dict[str, Any]], context_rows: list[dict[str, Any]]) -> None:
    expected = {("MSFT", year, family) for year in [2023, 2024, 2025] for family in ["cloud_revenue_proxy", "gross_margin"]}
    actual = {
        (str(fact.get("ticker") or "").upper(), int(fact.get("fiscal_year") or 0), str(fact.get("metric_family") or ""))
        for fact in facts
    }
    if actual != expected:
        raise SystemExit(f"Unexpected MSFT fact coverage. missing={sorted(expected - actual)} extra={sorted(actual - expected)}")
    context_actual = {
        (str(row.get("ticker") or "").upper(), int(row.get("fiscal_year") or 0), str(row.get("metric_family") or ""))
        for row in context_rows
        if row.get("metric_family")
    }
    if context_actual != expected:
        raise SystemExit(
            f"Unexpected MSFT context coverage. missing={sorted(expected - context_actual)} extra={sorted(context_actual - expected)}"
        )
    non_msft_facts = [fact for fact in facts if str(fact.get("ticker") or "").upper() != "MSFT"]
    non_msft_context = [row for row in context_rows if str(row.get("ticker") or "").upper() != "MSFT"]
    if non_msft_facts or non_msft_context:
        raise SystemExit("Split contract violation: non-MSFT rows entered MSFT case.")
    if not any(str(row.get("gold_role") or "") == "comparability_caveat" for row in context_rows):
        raise SystemExit("Split contract violation: MSFT comparability caveat row is missing.")


def _approval_payload() -> dict[str, Any]:
    return {
        "schema_version": "sec_gold_manual_review_v0.2",
        "review_scope": {
            "gold_context_dir": "eval/sec_cases/reviewed_gold_context",
            "gold_facts_dir": "eval/sec_cases/reviewed_gold_facts",
            "case_count": len(PLUS6_REVIEWED_CASE_IDS),
            "reviewed_case_ids": PLUS6_REVIEWED_CASE_IDS,
            "pipeline_only_trap_case_ids": [TRAP_CASE],
        },
        "review_decision": {
            "overall_status": "partial_approved_for_mainline_scored_benchmark",
            "allowed_next_step": "case_filtered_gold_context_and_pipeline_plus6_smoke",
            "blocked_next_step": "full_benchmark_mainline_scored_test",
            "reason": (
                "The plus5 reviewed cases remain approved, and the broad cloud profitability artifact is split into "
                "a Microsoft-only proxy/disclosure-boundary case. AMZN/GOOGL segment rows remain separate."
            ),
        },
        "case_reviews": [
            *_base_case_reviews(),
            {
                "case_id": MSFT_CASE,
                "decision": "approved_for_gold_context_mode",
                "mainline_status": "can_enter_case_filtered_scored_gold_context_smoke",
                "evidence_assessment": (
                    "Reviewed context is the Microsoft subset of the broad cloud profitability artifact: Microsoft Cloud "
                    "revenue, Microsoft Cloud gross margin percentage, AI/cloud infrastructure margin-pressure text, and "
                    "an explicit comparability caveat defining Microsoft Cloud as broad proxy evidence."
                ),
                "fact_assessment": (
                    "Reviewed facts contain 6 facts: Microsoft Cloud revenue proxy total values and Microsoft Cloud gross "
                    "margin percentages for fiscal 2023, 2024, and 2025."
                ),
                "required_fix": (
                    "Before broader promotion, pipeline-context output must not present Microsoft Cloud revenue as exact "
                    "Azure revenue, Microsoft Cloud gross margin as exact Azure gross margin, or gross margin percentages "
                    "as operating-income dollars."
                ),
            },
        ],
        "gate": {
            "can_enter_full_mainline_scored_test": False,
            "can_enter_case_filtered_gold_context_scored_smoke": True,
            "approved_case_ids": PLUS6_REVIEWED_CASE_IDS,
            "pipeline_only_trap_case_ids": [TRAP_CASE],
        },
    }


def _base_case_reviews() -> list[dict[str, Any]]:
    approval_path = REPO_ROOT / "reports" / "quality" / "sec_benchmark_v2_pilot_plus5_reviewed_gold_partial_approval.json"
    approval = _read_json(approval_path)
    keep = set(BASE_REVIEWED_CASE_IDS + [TRAP_CASE])
    return [row for row in approval.get("case_reviews") or [] if str(row.get("case_id") or "") in keep]


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
