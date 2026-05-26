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

from scripts import build_sec_benchmark_v2_pilot_plus4_reviewed_gold as plus4  # noqa: E402


BASE_MANIFEST = REPO_ROOT / "eval" / "sec_cases" / "test_cases_v2_pilot_plus4_seed.jsonl"
PLUS5_MANIFEST = REPO_ROOT / "eval" / "sec_cases" / "test_cases_v2_pilot_plus5_seed.jsonl"

BROAD_CLOUD_CASE = "CLOUD_PROFITABILITY_2023_2025_DIAG_001"
AMZN_GOOGL_CASE = "AMZN_GOOGL_CLOUD_PROFITABILITY_COMPARISON_2023_2025_001"
TRAP_CASE = plus4.TRAP_CASE

BASE_REVIEWED_CASE_IDS = list(plus4.PLUS4_REVIEWED_CASE_IDS)
PLUS5_REVIEWED_CASE_IDS = [*BASE_REVIEWED_CASE_IDS, AMZN_GOOGL_CASE]
TARGET_TICKERS = {"AMZN", "GOOGL"}


def main() -> None:
    reviewed_context_dir = REPO_ROOT / "eval" / "sec_cases" / "reviewed_gold_context"
    reviewed_facts_dir = REPO_ROOT / "eval" / "sec_cases" / "reviewed_gold_facts"
    report_dir = REPO_ROOT / "reports" / "quality"
    reviewed_context_dir.mkdir(parents=True, exist_ok=True)
    reviewed_facts_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    if not BASE_MANIFEST.exists():
        raise SystemExit(f"Missing base plus4 manifest: {BASE_MANIFEST}")

    _assert_source_artifacts_exist(reviewed_context_dir, reviewed_facts_dir)
    _write_manifest()
    case_summary = _write_split_artifacts(reviewed_context_dir, reviewed_facts_dir)

    approval_path = report_dir / "sec_benchmark_v2_pilot_plus5_reviewed_gold_partial_approval.json"
    approval_path.write_text(json.dumps(_approval_payload(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    build_report_path = report_dir / "sec_benchmark_v2_pilot_plus5_reviewed_gold_build_report.json"
    build_report = {
        "schema_version": "sec_v2_pilot_plus5_reviewed_gold_build_report_v0.1",
        "base_manifest": str(BASE_MANIFEST),
        "plus5_manifest": str(PLUS5_MANIFEST),
        "source_broad_case": BROAD_CLOUD_CASE,
        "base_reviewed_case_count": len(BASE_REVIEWED_CASE_IDS),
        "plus5_reviewed_case_count": len(PLUS5_REVIEWED_CASE_IDS),
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
                "plus5_manifest": str(PLUS5_MANIFEST),
                "plus5_reviewed_case_count": len(PLUS5_REVIEWED_CASE_IDS),
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
        if str(row.get("case_id") or "") == AMZN_GOOGL_CASE:
            output_rows.append(_amzn_googl_manifest_case())
            replaced = True
        else:
            output_rows.append(row)
    if not replaced:
        output_rows.append(_amzn_googl_manifest_case())
    _write_jsonl(PLUS5_MANIFEST, output_rows)


def _amzn_googl_manifest_case() -> dict[str, Any]:
    return {
        "schema_version": "sec_eval_case_v1",
        "benchmark_version": "sec_benchmark_v1",
        "case_id": AMZN_GOOGL_CASE,
        "origin": "v2_pilot_plus5_reviewed_expansion",
        "case_family": "v2_pilot_plus5",
        "test_objective": (
            "Split the reviewed broad cloud profitability case into a clean AMZN/GOOGL peer comparison "
            "that tests comparable cloud segment revenue and operating-income evidence without Microsoft proxy asymmetry."
        ),
        "case_group": "diagnostic_stress",
        "level": "L4",
        "companies": ["AMZN", "GOOGL"],
        "years": [2023, 2024, 2025],
        "filing_types": ["10-K"],
        "task_type": "peer_comparison_cloud_profitability_comparable_segments",
        "prompt": (
            "Using Amazon and Alphabet SEC 10-K evidence for fiscal 2023-2025, compare AWS and Google Cloud "
            "revenue and operating income trends. Keep each company, fiscal year, metric, and unit separate; "
            "cite every numeric value; and state the limits of using segment operating income to infer broader "
            "cloud profitability or market-share conclusions."
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
            "Must compare AWS and Google Cloud revenue for fiscal 2023, 2024, and 2025.",
            "Must compare AWS and Google Cloud operating income for fiscal 2023, 2024, and 2025.",
            "Must keep AMZN and GOOGL evidence separate and avoid entity bleed.",
            "Must treat operating income as segment-scope evidence, not product-level margin or market share.",
            "Must avoid external market-share, customer-growth, and simple cloud-winner claims unsupported by SEC evidence.",
        ],
        "numeric_checks": [
            {
                "metric": "AWS and Google Cloud revenue and operating income",
                "metric_families": ["cloud_revenue", "operating_income"],
                "metric_roles": ["total_value"],
                "companies": ["AMZN", "GOOGL"],
                "years": [2023, 2024, 2025],
            }
        ],
        "required_caveats": [
            {
                "id": "segment_scope_only",
                "description": "Must say the comparison is segment-scope only and not product-level margin or total-company profitability.",
                "where": "answer",
                "all_of_any": [
                    ["segment", "AWS", "Google Cloud", "分部"],
                    ["operating income", "profitability", "盈利"],
                    ["not product-level", "not total-company", "scope", "不是", "不能"],
                ],
            },
            {
                "id": "no_market_share_or_customer_growth_proof",
                "description": "Must state SEC segment revenue and operating income do not prove cloud market share or customer-growth claims.",
                "where": "caveats",
                "all_of_any": [
                    ["market share", "customer growth", "市场份额", "客户增长"],
                    ["not prove", "does not prove", "不能证明", "不证明"],
                ],
            },
            {
                "id": "peer_entity_metric_separation",
                "description": "Must explicitly keep AMZN/AWS and GOOGL/Google Cloud metrics separate.",
                "where": "answer",
                "all_of_any": [
                    ["AWS", "AMZN", "Amazon"],
                    ["Google Cloud", "GOOGL", "Alphabet"],
                    ["separate", "respectively", "分别", "区分"],
                ],
            },
        ],
        "disallowed_claims": [
            {
                "id": "simple_cloud_winner_without_caveat",
                "description": "Do not declare a simple cloud winner unless tied to exact segment metrics and caveats.",
                "patterns": [
                    "cloud winner",
                    "winner in cloud",
                    "云业务赢家",
                    "云赢家",
                ],
                "allow_if_any_near": [
                    "segment",
                    "operating income",
                    "revenue",
                    "caveat",
                    "only on",
                    "仅",
                    "基于",
                    "口径",
                ],
            },
            {
                "id": "external_market_share_claim",
                "description": "Do not infer cloud market share from SEC segment revenue alone.",
                "patterns": ["market share", "市场份额"],
                "allow_if_any_near": ["not", "does not prove", "does not represent", "不能", "不证明", "不代表", "未披露"],
            },
            {
                "id": "customer_growth_claim",
                "description": "Do not invent customer-growth claims for AWS or Google Cloud.",
                "patterns": ["customer growth", "客户增长", "客户数增长"],
                "allow_if_any_near": ["not", "not disclosed", "未披露", "不能"],
            },
            {
                "id": "operating_income_as_margin",
                "description": "Do not present operating-income dollars as operating-margin percentages.",
                "patterns": [
                    "operating margin was 24,631",
                    "operating margin was 39,834",
                    "operating margin was 45,606",
                    "operating margin was 1,716",
                    "operating margin was 6,112",
                    "operating margin was 13,910",
                    "利润率为 24,631",
                    "利润率为 1,716",
                ],
                "allow_if_any_near": ["not", "income", "dollars", "不是", "营业利润"],
            },
            {
                "id": "entity_metric_bleed",
                "description": "Do not assign one company's cloud metric to the other company.",
                "patterns": [
                    "Google Cloud AWS",
                    "AWS Google Cloud revenue was 58,705",
                    "Google Cloud revenue was 128,725",
                    "AWS operating income was 13,910",
                    "Google Cloud operating income was 45,606",
                ],
                "allow_if_any_near": ["not", "separate", "different", "不是", "区分"],
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
            "unit_scale_gate",
        ],
        "hallucination_traps": [
            "Do not mix AWS and Google Cloud numeric values.",
            "Do not treat segment operating income as product-level margin or market share.",
            "Do not use Microsoft Cloud proxy metrics in this AMZN/GOOGL comparable segment case.",
            "Do not make external market-share or customer-growth claims from SEC segment rows alone.",
        ],
        "failure_types": [
            "retrieval_miss",
            "numeric_error",
            "unit_error",
            "metric_role_error",
            "unsupported_claim",
            "entity_bleed_between_peers",
            "non_comparable_metric_comparison",
            "missing_caveat",
        ],
        "score_weights": {"retrieval": 2, "factuality": 3, "coverage": 2, "synthesis": 2, "citation": 1},
        "gold_context_status": "needs_annotation",
    }


def _write_split_artifacts(reviewed_context_dir: Path, reviewed_facts_dir: Path) -> dict[str, Any]:
    source_facts_path = reviewed_facts_dir / f"{BROAD_CLOUD_CASE}.json"
    source_context_path = reviewed_context_dir / f"{BROAD_CLOUD_CASE}.jsonl"
    target_facts_path = reviewed_facts_dir / f"{AMZN_GOOGL_CASE}.json"
    target_context_path = reviewed_context_dir / f"{AMZN_GOOGL_CASE}.jsonl"

    source_payload = _read_json(source_facts_path)
    source_facts = [
        fact
        for fact in source_payload.get("facts") or []
        if str(fact.get("review_status") or "") == "reviewed_keep"
        and str(fact.get("ticker") or "").upper() in TARGET_TICKERS
    ]
    source_facts.sort(key=lambda item: (str(item.get("ticker") or ""), int(item.get("fiscal_year") or 0), str(item.get("metric_family") or "")))

    target_facts = []
    for index, fact in enumerate(source_facts, start=1):
        rewritten = dict(fact)
        rewritten["fact_id"] = f"{AMZN_GOOGL_CASE}_FACT_R{index:04d}"
        rewritten["selection_query"] = "AWS and Google Cloud revenue and operating income"
        rewritten["review_note"] = f"Split from {BROAD_CLOUD_CASE}: {fact.get('review_note')}"
        target_facts.append(rewritten)

    facts_payload = {
        "schema_version": "sec_gold_facts_reviewed_v0.1",
        "case_id": AMZN_GOOGL_CASE,
        "benchmark_version": "sec_benchmark_v1",
        "review_status": "reviewed_approved",
        "review_scope": {
            "source_case_id": BROAD_CLOUD_CASE,
            "split_policy": "AMZN_GOOGL_only_no_MSFT_proxy_rows",
            "target_tickers": sorted(TARGET_TICKERS),
        },
        "numeric_checks": _amzn_googl_manifest_case()["numeric_checks"],
        "facts": target_facts,
    }
    target_facts_path.write_text(json.dumps(facts_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    context_rows = [
        row
        for row in _read_jsonl(source_context_path)
        if str(row.get("review_status") or "") == "reviewed_keep"
        and str(row.get("ticker") or "").upper() in TARGET_TICKERS
    ]
    context_rows.sort(key=lambda item: (str(item.get("ticker") or ""), int(item.get("fiscal_year") or 0), str(item.get("metric_family") or "")))
    rewritten_context_rows: list[dict[str, Any]] = []
    for row in context_rows:
        rewritten = dict(row)
        rewritten["case_id"] = AMZN_GOOGL_CASE
        rewritten["review_note"] = f"Split from {BROAD_CLOUD_CASE}: {row.get('review_note')}"
        rewritten_context_rows.append(rewritten)
    _write_jsonl(target_context_path, rewritten_context_rows)

    _assert_split_contract(target_facts, rewritten_context_rows)
    return {
        "case_id": AMZN_GOOGL_CASE,
        "source_case_id": BROAD_CLOUD_CASE,
        "fact_count": len(target_facts),
        "context_row_count": len(rewritten_context_rows),
        "context_path": str(target_context_path),
        "facts_path": str(target_facts_path),
        "split_policy": "strict_AMZN_GOOGL_subset_excluding_MSFT_proxy_rows",
        "metric_families": sorted({str(fact.get("metric_family") or "") for fact in target_facts}),
        "metric_roles": sorted({str(fact.get("metric_role") or "") for fact in target_facts}),
        "tickers": sorted({str(fact.get("ticker") or "") for fact in target_facts}),
        "source_evidence_count": len({str(fact.get("source_evidence_id") or "") for fact in target_facts}),
    }


def _assert_split_contract(facts: list[dict[str, Any]], context_rows: list[dict[str, Any]]) -> None:
    expected = {(ticker, year, family) for ticker in TARGET_TICKERS for year in [2023, 2024, 2025] for family in ["cloud_revenue", "operating_income"]}
    actual = {
        (str(fact.get("ticker") or "").upper(), int(fact.get("fiscal_year") or 0), str(fact.get("metric_family") or ""))
        for fact in facts
    }
    if actual != expected:
        raise SystemExit(f"Unexpected AMZN/GOOGL fact coverage. missing={sorted(expected - actual)} extra={sorted(actual - expected)}")
    context_actual = {
        (str(row.get("ticker") or "").upper(), int(row.get("fiscal_year") or 0), str(row.get("metric_family") or ""))
        for row in context_rows
    }
    if context_actual != expected:
        raise SystemExit(
            f"Unexpected AMZN/GOOGL context coverage. missing={sorted(expected - context_actual)} extra={sorted(context_actual - expected)}"
        )
    msft_facts = [fact for fact in facts if str(fact.get("ticker") or "").upper() == "MSFT"]
    msft_context = [row for row in context_rows if str(row.get("ticker") or "").upper() == "MSFT"]
    if msft_facts or msft_context:
        raise SystemExit("Split contract violation: MSFT rows entered AMZN/GOOGL case.")


def _approval_payload() -> dict[str, Any]:
    return {
        "schema_version": "sec_gold_manual_review_v0.2",
        "review_scope": {
            "gold_context_dir": "eval/sec_cases/reviewed_gold_context",
            "gold_facts_dir": "eval/sec_cases/reviewed_gold_facts",
            "case_count": len(PLUS5_REVIEWED_CASE_IDS),
            "reviewed_case_ids": PLUS5_REVIEWED_CASE_IDS,
            "pipeline_only_trap_case_ids": [TRAP_CASE],
        },
        "review_decision": {
            "overall_status": "partial_approved_for_mainline_scored_benchmark",
            "allowed_next_step": "case_filtered_gold_context_and_pipeline_plus5_smoke",
            "blocked_next_step": "full_benchmark_mainline_scored_test",
            "reason": (
                "The plus4 reviewed cases remain approved, and the broad cloud profitability artifact is split into "
                "a strict AMZN/GOOGL comparable segment case. The Microsoft proxy rows are intentionally excluded."
            ),
        },
        "case_reviews": [
            *_base_case_reviews(),
            {
                "case_id": AMZN_GOOGL_CASE,
                "decision": "approved_for_gold_context_mode",
                "mainline_status": "can_enter_case_filtered_scored_gold_context_smoke",
                "evidence_assessment": (
                    "Reviewed context is a strict AMZN/GOOGL subset of the broad cloud profitability artifact: "
                    "AWS and Google Cloud revenue plus operating income rows for fiscal 2023-2025."
                ),
                "fact_assessment": (
                    "Reviewed facts contain 12 role-separated total-value facts: AMZN and GOOGL cloud revenue "
                    "and operating income for fiscal 2023, 2024, and 2025. Microsoft Cloud proxy and gross-margin "
                    "rows are excluded by construction."
                ),
                "required_fix": (
                    "Before broader promotion, pipeline-context output must preserve peer entity separation, avoid "
                    "market-share/customer-growth claims, and keep segment operating income distinct from margin."
                ),
            },
        ],
        "gate": {
            "can_enter_full_mainline_scored_test": False,
            "can_enter_case_filtered_gold_context_scored_smoke": True,
            "approved_case_ids": PLUS5_REVIEWED_CASE_IDS,
            "pipeline_only_trap_case_ids": [TRAP_CASE],
        },
    }


def _base_case_reviews() -> list[dict[str, Any]]:
    approval_path = REPO_ROOT / "reports" / "quality" / "sec_benchmark_v2_pilot_plus4_reviewed_gold_partial_approval.json"
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
