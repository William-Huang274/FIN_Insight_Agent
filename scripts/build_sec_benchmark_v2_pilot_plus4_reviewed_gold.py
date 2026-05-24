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

from scripts import build_sec_benchmark_v2_pilot_plus3_reviewed_gold as plus3  # noqa: E402


SOURCE_MANIFEST = REPO_ROOT / "eval" / "sec_cases" / "test_cases_v1.jsonl"
BASE_MANIFEST = REPO_ROOT / "eval" / "sec_cases" / "test_cases_v2_pilot_plus3_seed.jsonl"
PLUS4_MANIFEST = REPO_ROOT / "eval" / "sec_cases" / "test_cases_v2_pilot_plus4_seed.jsonl"

AMZN_CASE = "AMZN_AWS_NUMERIC_2023_2025_001"
TRAP_CASE = plus3.TRAP_CASE

BASE_REVIEWED_CASE_IDS = list(plus3.PLUS3_REVIEWED_CASE_IDS)
PLUS4_REVIEWED_CASE_IDS = [*BASE_REVIEWED_CASE_IDS, AMZN_CASE]


def main() -> None:
    reviewed_context_dir = REPO_ROOT / "eval" / "sec_cases" / "reviewed_gold_context"
    reviewed_facts_dir = REPO_ROOT / "eval" / "sec_cases" / "reviewed_gold_facts"
    report_dir = REPO_ROOT / "reports" / "quality"
    report_dir.mkdir(parents=True, exist_ok=True)

    if not BASE_MANIFEST.exists():
        raise SystemExit(f"Missing base plus3 manifest: {BASE_MANIFEST}")

    _assert_reviewed_artifacts_exist(reviewed_context_dir, reviewed_facts_dir)
    _write_manifest()
    amzn_summary = _amzn_summary(reviewed_context_dir, reviewed_facts_dir)

    approval_path = report_dir / "sec_benchmark_v2_pilot_plus4_reviewed_gold_partial_approval.json"
    approval_path.write_text(json.dumps(_approval_payload(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    build_report_path = report_dir / "sec_benchmark_v2_pilot_plus4_reviewed_gold_build_report.json"
    build_report = {
        "schema_version": "sec_v2_pilot_plus4_reviewed_gold_build_report_v0.1",
        "base_manifest": str(BASE_MANIFEST),
        "plus4_manifest": str(PLUS4_MANIFEST),
        "base_reviewed_case_count": len(BASE_REVIEWED_CASE_IDS),
        "plus4_reviewed_case_count": len(PLUS4_REVIEWED_CASE_IDS),
        "trap_case_not_gold_context": TRAP_CASE,
        "approval_path": str(approval_path),
        "new_cases": [amzn_summary],
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
                "plus4_manifest": str(PLUS4_MANIFEST),
                "plus4_reviewed_case_count": len(PLUS4_REVIEWED_CASE_IDS),
                "new_fact_count": amzn_summary["fact_count"],
                "new_context_row_count": amzn_summary["context_row_count"],
                "approval_path": str(approval_path),
                "build_report_path": str(build_report_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def _assert_reviewed_artifacts_exist(reviewed_context_dir: Path, reviewed_facts_dir: Path) -> None:
    missing = [
        path
        for path in [
            reviewed_context_dir / f"{AMZN_CASE}.jsonl",
            reviewed_facts_dir / f"{AMZN_CASE}.json",
        ]
        if not path.exists()
    ]
    if missing:
        raise SystemExit("Missing reviewed AMZN artifacts: " + ", ".join(str(path) for path in missing))


def _write_manifest() -> None:
    rows = _read_jsonl(BASE_MANIFEST)
    replaced = False
    output_rows: list[dict[str, Any]] = []
    for row in rows:
        if str(row.get("case_id") or "") == AMZN_CASE:
            output_rows.append(_amzn_manifest_case())
            replaced = True
        else:
            output_rows.append(row)
    if not replaced:
        output_rows.append(_amzn_manifest_case())
    _write_jsonl(PLUS4_MANIFEST, output_rows)


def _amzn_manifest_case() -> dict[str, Any]:
    case = dict(_source_case())
    case.update(
        {
            "origin": "v2_pilot_plus4_reviewed_expansion",
            "case_family": "v2_pilot_plus4",
            "test_objective": (
                "Promote the reviewed Amazon AWS numeric case into v2 to test segment metric role separation, "
                "year alignment, and YoY-percentage trap handling under BGE-M3 pipeline context."
            ),
            "required_caveats": [
                {
                    "id": "aws_segment_not_consolidated_amazon",
                    "description": "Must state AWS is Amazon's cloud segment and not consolidated Amazon revenue.",
                    "where": "answer",
                    "all_of_any": [
                        ["AWS", "Amazon Web Services"],
                        ["segment", "cloud"],
                        ["not consolidated", "not total Amazon", "separate", "not the same", "不", "不是"],
                    ],
                },
                {
                    "id": "aws_revenue_operating_income_separate",
                    "description": "Must keep AWS net sales/revenue separate from AWS operating income.",
                    "where": "answer",
                    "all_of_any": [
                        ["AWS"],
                        ["revenue", "net sales", "sales"],
                        ["operating income", "income"],
                        ["separate", "different", "not the same", "区分", "不同"],
                    ],
                },
                {
                    "id": "yoy_percentages_not_target_values",
                    "description": "Must not treat YoY percentage growth rows as dollar revenue or operating-income values.",
                    "where": "caveats",
                    "all_of_any": [
                        ["year-over-year", "YoY", "growth", "percentage", "%"],
                        ["revenue", "net sales", "operating income", "dollar"],
                        ["not", "not dollar", "separate", "不是", "不能"],
                    ],
                },
            ],
            "disallowed_claims": [
                {
                    "id": "aws_equals_total_amazon_revenue",
                    "description": "Do not equate AWS segment revenue with consolidated Amazon revenue.",
                    "patterns": [
                        "AWS revenue equals Amazon total revenue",
                        "AWS is Amazon total revenue",
                        "AWS 等同于亚马逊总收入",
                    ],
                    "allow_if_any_near": ["not", "separate", "segment", "不", "不是", "不能"],
                },
                {
                    "id": "yoy_percentage_as_revenue",
                    "description": "Do not use YoY percentages as AWS dollar revenue or operating-income values.",
                    "patterns": [
                        "AWS revenue was 13",
                        "AWS revenue was 19",
                        "AWS revenue was 20",
                        "AWS operating income was 13",
                        "AWS operating income was 19",
                        "AWS operating income was 20",
                    ],
                    "allow_if_any_near": ["%", "growth", "not", "percentage", "不是", "增长"],
                },
                {
                    "id": "operating_income_as_margin",
                    "description": "Do not present AWS operating income dollars as an operating margin percentage.",
                    "patterns": [
                        "operating margin was 24,631",
                        "operating margin was 39,834",
                        "operating margin was 45,606",
                        "利润率为 24,631",
                    ],
                    "allow_if_any_near": ["not", "income", "dollars", "不是", "营业利润"],
                },
                {
                    "id": "non_segment_charge_as_aws_income",
                    "description": "Do not use non-segment charge text as AWS segment operating income.",
                    "patterns": ["FTC", "severance charge", "$2.5 billion charge", "25亿美元费用"],
                    "allow_if_any_near": ["not AWS", "not segment", "not operating income", "不是", "不能"],
                },
            ],
            "hard_gates": _dedupe(
                [
                    *[str(item) for item in case.get("hard_gates") or []],
                    "unsupported_claim_gate",
                    "unit_scale_gate",
                ]
            ),
            "hallucination_traps": _dedupe(
                [
                    *[str(item) for item in case.get("hallucination_traps") or []],
                    "Do not use YoY percentage rows as target dollar facts.",
                    "Do not treat AWS operating income as operating margin.",
                    "Do not treat non-segment charge text as AWS segment operating income.",
                ]
            ),
            "failure_types": _dedupe(
                [
                    *[str(item) for item in case.get("failure_types") or []],
                    "percentage_change_as_absolute_value",
                    "proxy_as_direct_metric",
                    "missing_caveat",
                ]
            ),
        }
    )
    return case


def _source_case() -> dict[str, Any]:
    for row in _read_jsonl(SOURCE_MANIFEST):
        if str(row.get("case_id") or "") == AMZN_CASE:
            return row
    raise SystemExit(f"Missing source case in {SOURCE_MANIFEST}: {AMZN_CASE}")


def _amzn_summary(reviewed_context_dir: Path, reviewed_facts_dir: Path) -> dict[str, Any]:
    facts_path = reviewed_facts_dir / f"{AMZN_CASE}.json"
    context_path = reviewed_context_dir / f"{AMZN_CASE}.jsonl"
    facts_payload = _read_json(facts_path)
    facts = [
        fact
        for fact in facts_payload.get("facts") or []
        if str(fact.get("review_status") or "") == "reviewed_keep"
    ]
    context_rows = _read_jsonl(context_path)
    return {
        "case_id": AMZN_CASE,
        "fact_count": len(facts),
        "context_row_count": len(context_rows),
        "context_path": str(context_path),
        "facts_path": str(facts_path),
        "reuse_policy": "reuse_existing_reviewed_v1_artifacts_with_v2_manifest_contract",
        "metric_families": sorted({str(fact.get("metric_family") or "") for fact in facts if fact.get("metric_family")}),
        "metric_roles": sorted({str(fact.get("metric_role") or "") for fact in facts if fact.get("metric_role")}),
    }


def _approval_payload() -> dict[str, Any]:
    return {
        "schema_version": "sec_gold_manual_review_v0.2",
        "review_scope": {
            "gold_context_dir": "eval/sec_cases/reviewed_gold_context",
            "gold_facts_dir": "eval/sec_cases/reviewed_gold_facts",
            "case_count": len(PLUS4_REVIEWED_CASE_IDS),
            "reviewed_case_ids": PLUS4_REVIEWED_CASE_IDS,
            "pipeline_only_trap_case_ids": [TRAP_CASE],
        },
        "review_decision": {
            "overall_status": "partial_approved_for_mainline_scored_benchmark",
            "allowed_next_step": "case_filtered_gold_context_and_pipeline_plus4_smoke",
            "blocked_next_step": "full_benchmark_mainline_scored_test",
            "reason": (
                "The plus3 reviewed cases remain approved, and the existing reviewed Amazon AWS numeric case is "
                "promoted as a v2 plus4 diagnostic case. The Microsoft/YouTube trap remains pipeline-only."
            ),
        },
        "case_reviews": [
            *_base_case_reviews(),
            {
                "case_id": AMZN_CASE,
                "decision": "approved_for_gold_context_mode",
                "mainline_status": "can_enter_case_filtered_scored_gold_context_smoke",
                "evidence_assessment": (
                    "Reviewed context uses Amazon 2023-2025 10-K MD&A segment tables for AWS net sales and "
                    "operating income, with YoY percentage rows explicitly treated as non-target traps."
                ),
                "fact_assessment": (
                    "Reviewed facts contain 6 role-separated facts: 3 AWS cloud revenue total values and "
                    "3 AWS operating-income total values."
                ),
                "required_fix": (
                    "Before full promotion, pipeline-context run should confirm the answer keeps AWS segment "
                    "revenue, AWS operating income, YoY percentage rows, and non-segment charges separate."
                ),
            },
        ],
        "gate": {
            "can_enter_full_mainline_scored_test": False,
            "can_enter_case_filtered_gold_context_scored_smoke": True,
            "approved_case_ids": PLUS4_REVIEWED_CASE_IDS,
            "pipeline_only_trap_case_ids": [TRAP_CASE],
        },
    }


def _base_case_reviews() -> list[dict[str, Any]]:
    approval_path = REPO_ROOT / "reports" / "quality" / "sec_benchmark_v2_pilot_plus3_reviewed_gold_partial_approval.json"
    approval = _read_json(approval_path)
    keep = set(BASE_REVIEWED_CASE_IDS + [TRAP_CASE])
    return [row for row in approval.get("case_reviews") or [] if str(row.get("case_id") or "") in keep]


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            output.append(item)
    return output


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
