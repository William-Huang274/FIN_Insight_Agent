from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


FULL40_MANIFEST = REPO_ROOT / "eval" / "sec_cases" / "test_cases_v2_full40_seed.jsonl"
OUTPUT_PATH = REPO_ROOT / "reports" / "quality" / "sec_benchmark_v2_full40_partial_review_approval.json"

SOURCE_APPROVAL_PATHS = [
    REPO_ROOT / "reports" / "quality" / "sec_benchmark_v2_full40_text7_reviewed_gold_partial_approval.json",
    REPO_ROOT / "reports" / "quality" / "sec_benchmark_v2_full40_numeric5_reviewed_gold_partial_approval.json",
    REPO_ROOT / "reports" / "quality" / "sec_benchmark_v2_pilot_plus8_reviewed_gold_partial_approval.json",
    REPO_ROOT / "reports" / "quality" / "sec_benchmark_v1_1_reviewed_gold_partial_approval.json",
    REPO_ROOT / "reports" / "quality" / "sec_benchmark_v1_reviewed_gold_partial_approval.json",
    REPO_ROOT / "reports" / "quality" / "sec_benchmark_v1_gold_manual_review.json",
]

NEW_TRAP_REVIEWS = {
    "GOOGL_AWS_OPERATING_INCOME_TRAP_2023_2025_001": {
        "case_id": "GOOGL_AWS_OPERATING_INCOME_TRAP_2023_2025_001",
        "decision": "approved_for_pipeline_trap_smoke",
        "mainline_status": "can_enter_case_filtered_pipeline_trap_smoke",
        "evidence_assessment": (
            "Wrong-attribution trap. Alphabet SEC filings should not be used to answer AWS operating income; "
            "AWS belongs to Amazon, not Alphabet."
        ),
        "fact_assessment": "No target numeric facts are required or approved for this trap.",
        "required_fix": (
            "Pipeline output must refuse the Alphabet/AWS attribution and must not invent AWS operating income "
            "from Alphabet filings."
        ),
    },
    "NVDA_CUDA_SOFTWARE_REVENUE_NOT_FOUND_2023_2025_001": {
        "case_id": "NVDA_CUDA_SOFTWARE_REVENUE_NOT_FOUND_2023_2025_001",
        "decision": "approved_for_pipeline_trap_smoke",
        "mainline_status": "can_enter_case_filtered_pipeline_trap_smoke",
        "evidence_assessment": (
            "Metric-scope not-found trap. NVIDIA SEC filings may discuss Data Center, software, and CUDA context, "
            "but exact CUDA software revenue is not approved as a disclosed metric."
        ),
        "fact_assessment": "No target numeric facts are required or approved for this trap.",
        "required_fix": (
            "Pipeline output must state exact CUDA software revenue is not disclosed and must not substitute "
            "Data Center revenue or other broader NVIDIA metrics."
        ),
    },
}


def main() -> None:
    rows = _read_jsonl(FULL40_MANIFEST)
    reviewed_case_ids = [
        str(row.get("case_id") or "")
        for row in rows
        if str(row.get("reviewed_asset_status") or "") == "reviewed_gold_available"
    ]
    trap_case_ids = [
        str(row.get("case_id") or "")
        for row in rows
        if str(row.get("reviewed_asset_status") or "") in {"pipeline_trap", "pipeline_trap_seed"}
    ]
    seed_blocked_case_ids = [
        str(row.get("case_id") or "")
        for row in rows
        if str(row.get("reviewed_asset_status") or "") == "seed_needs_review"
    ]

    historical_reviews = _load_historical_reviews()
    approved_reviews: list[dict[str, Any]] = []
    missing_reviews = []
    for case_id in reviewed_case_ids:
        review = historical_reviews.get(case_id)
        if not review:
            missing_reviews.append(case_id)
        else:
            approved_reviews.append(review)
    for case_id in trap_case_ids:
        review = historical_reviews.get(case_id) or NEW_TRAP_REVIEWS.get(case_id)
        if not review:
            missing_reviews.append(case_id)
        else:
            approved_reviews.append(review)
    if missing_reviews:
        raise SystemExit(f"Missing historical or trap review rows: {missing_reviews}")

    blocked_reviews = [_blocked_seed_review(case_id) for case_id in seed_blocked_case_ids]
    all_cases_gold_ready = not seed_blocked_case_ids
    payload = {
        "schema_version": "sec_gold_manual_review_v0.2",
        "review_scope": {
            "gold_context_dir": "eval/sec_cases/reviewed_gold_context",
            "gold_facts_dir": "eval/sec_cases/reviewed_gold_facts",
            "full40_manifest": "eval/sec_cases/test_cases_v2_full40_seed.jsonl",
            "case_count": len(rows),
            "approved_reviewed_case_ids": reviewed_case_ids,
            "pipeline_only_trap_case_ids": trap_case_ids,
            "seed_needs_review_case_ids": seed_blocked_case_ids,
        },
        "review_decision": {
            "overall_status": (
                "approved_for_mainline_scored_benchmark"
                if all_cases_gold_ready
                else "partial_approved_for_mainline_scored_benchmark"
            ),
            "allowed_next_step": (
                "full40_gold_gate_then_ledger_and_judgment_plan"
                if all_cases_gold_ready
                else "case_filtered_reviewed_and_trap_gate_smoke"
            ),
            "blocked_next_step": (
                "full40_qwen_pipeline_until_ledger_and_judgment_plan_are_built"
                if all_cases_gold_ready
                else "full40_mainline_scored_test"
            ),
            "reason": _review_decision_reason(len(reviewed_case_ids), len(trap_case_ids), len(seed_blocked_case_ids)),
        },
        "case_reviews": [*approved_reviews, *blocked_reviews],
        "gate": {
            "can_enter_full_mainline_scored_test": all_cases_gold_ready,
            "can_enter_case_filtered_gold_context_scored_smoke": True,
            "can_enter_case_filtered_pipeline_trap_smoke": True,
            "approved_case_ids": reviewed_case_ids,
            "pipeline_only_trap_case_ids": trap_case_ids,
            "blocked_seed_case_ids": seed_blocked_case_ids,
        },
        "source_approval_paths": [str(path) for path in SOURCE_APPROVAL_PATHS],
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output_path": str(OUTPUT_PATH),
                "approved_reviewed_case_count": len(reviewed_case_ids),
                "approved_trap_case_count": len(trap_case_ids),
                "blocked_seed_case_count": len(seed_blocked_case_ids),
                "can_enter_full_mainline_scored_test": all_cases_gold_ready,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def _review_decision_reason(reviewed_count: int, trap_count: int, blocked_seed_count: int) -> str:
    if blocked_seed_count:
        return (
            f"The full40 manifest contains {reviewed_count} cases with reviewed gold artifacts and "
            f"{trap_count} approved pipeline-only traps. The remaining {blocked_seed_count} non-trap seed "
            "cases have review candidates but are not approved for full scored inference."
        )
    return (
        f"The full40 manifest contains {reviewed_count} cases with reviewed gold artifacts and "
        f"{trap_count} approved pipeline-only traps. No seed-only cases remain, so the gold readiness gate "
        "can run over all 40 cases before ledger, Judgment Plan, and Qwen pipeline execution."
    )


def _load_historical_reviews() -> dict[str, dict[str, Any]]:
    reviews: dict[str, dict[str, Any]] = {}
    for path in SOURCE_APPROVAL_PATHS:
        if not path.exists():
            continue
        payload = _read_json(path)
        for review in payload.get("case_reviews") or []:
            case_id = str(review.get("case_id") or "")
            if case_id and case_id not in reviews:
                reviews[case_id] = review
    return reviews


def _blocked_seed_review(case_id: str) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "decision": "seed_needs_review_not_approved",
        "mainline_status": "blocked_from_scored_mainline",
        "evidence_assessment": (
            "A review candidate file exists under eval/sec_cases/full40_review_candidates_context, "
            "but this case has not been promoted to reviewed gold context/facts."
        ),
        "fact_assessment": "Not approved. Candidate facts, if any, remain seed_needs_review.",
        "required_fix": "Promote reviewed context/facts or explicitly convert the case into an approved pipeline trap.",
    }


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


if __name__ == "__main__":
    main()
