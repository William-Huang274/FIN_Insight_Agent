from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


SCHEMA_VERSION = "sec_gold_gate_report_v0.1"
SEED_REVIEW_STATUSES = {"seed_needs_review", "seed"}
MAINLINE_ALLOWED_OVERALL_STATUS = "approved_for_mainline_scored_benchmark"
PARTIAL_MAINLINE_ALLOWED_OVERALL_STATUS = "partial_approved_for_mainline_scored_benchmark"
MAINLINE_ALLOWED_CASE_DECISIONS = {
    "approved_for_mainline_scored_benchmark",
    "approved_for_gold_context_mode",
    "approved_for_pipeline_trap_smoke",
}
TRAP_TASK_PREFIX = "anti_hallucination"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate SEC benchmark gold readiness gates.")
    parser.add_argument("--cases-path", default="eval/sec_cases/test_cases_v1.jsonl")
    parser.add_argument("--gold-context-dir", default="eval/sec_cases/gold_context")
    parser.add_argument("--gold-facts-dir", default="eval/sec_cases/gold_facts")
    parser.add_argument(
        "--manual-review-path",
        default="reports/quality/sec_benchmark_v1_gold_manual_review.json",
    )
    parser.add_argument(
        "--gate",
        choices=["context_smoke", "trap_smoke", "mainline_scored"],
        default="mainline_scored",
    )
    parser.add_argument(
        "--case-id",
        action="append",
        default=[],
        help="Optional case_id filter. Repeat for multiple cases.",
    )
    parser.add_argument(
        "--max-mainline-context-rows",
        type=int,
        default=80,
        help="Maximum reviewed gold rows per non-diagnostic case before warning/blocking mainline use.",
    )
    parser.add_argument(
        "--output-path",
        default="reports/quality/sec_benchmark_v1_gold_gate_mainline.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cases = _read_jsonl(REPO_ROOT / args.cases_path)
    requested_case_ids = {str(case_id) for case_id in args.case_id}
    if requested_case_ids:
        cases = [case for case in cases if str(case.get("case_id") or "") in requested_case_ids]
        if not cases:
            raise SystemExit(f"No cases matched --case-id: {', '.join(sorted(requested_case_ids))}")
    manual_review = _read_json(REPO_ROOT / args.manual_review_path)
    review_by_case = {
        str(row.get("case_id")): row for row in manual_review.get("case_reviews") or []
    }

    case_results = [
        _evaluate_case(
            case=case,
            gate=args.gate,
            gold_context_dir=REPO_ROOT / args.gold_context_dir,
            gold_facts_dir=REPO_ROOT / args.gold_facts_dir,
            review=review_by_case.get(str(case.get("case_id") or "")),
            max_mainline_context_rows=args.max_mainline_context_rows,
        )
        for case in cases
    ]

    overall_blockers = _overall_blockers(args.gate, manual_review, requested_case_ids)
    status_counts = Counter(result["status"] for result in case_results)
    blocker_types = Counter(
        blocker.get("type")
        for result in case_results
        for blocker in result.get("blockers") or []
    )
    warning_types = Counter(
        warning.get("type")
        for result in case_results
        for warning in result.get("warnings") or []
    )
    can_enter = not overall_blockers and all(
        result["status"] in {"pass", "skipped_not_applicable"} for result in case_results
    )
    report = {
        "schema_version": SCHEMA_VERSION,
        "gate": args.gate,
        "cases_path": str((REPO_ROOT / args.cases_path).resolve()),
        "gold_context_dir": str((REPO_ROOT / args.gold_context_dir).resolve()),
        "gold_facts_dir": str((REPO_ROOT / args.gold_facts_dir).resolve()),
        "manual_review_path": str((REPO_ROOT / args.manual_review_path).resolve()),
        "case_filter": sorted(requested_case_ids),
        "manual_review_overall_status": manual_review.get("review_decision", {}).get("overall_status"),
        "can_enter_gate": can_enter,
        "overall_blockers": overall_blockers,
        "summary": {
            "case_count": len(case_results),
            "status_counts": dict(sorted(status_counts.items())),
            "blocker_types": dict(sorted(blocker_types.items())),
            "warning_types": dict(sorted(warning_types.items())),
        },
        "case_results": case_results,
    }
    output_path = REPO_ROOT / args.output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "gate": report["gate"],
                "can_enter_gate": report["can_enter_gate"],
                "overall_blocker_count": len(overall_blockers),
                "status_counts": report["summary"]["status_counts"],
                "blocker_types": report["summary"]["blocker_types"],
                "warning_types": report["summary"]["warning_types"],
                "output_path": str(output_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def _evaluate_case(
    case: dict[str, Any],
    gate: str,
    gold_context_dir: Path,
    gold_facts_dir: Path,
    review: dict[str, Any] | None,
    max_mainline_context_rows: int,
) -> dict[str, Any]:
    case_id = str(case.get("case_id") or "")
    task_type = str(case.get("task_type") or "")
    gold_status = str(case.get("gold_context_status") or "")
    context_path = gold_context_dir / f"{case_id}.jsonl"
    facts_path = gold_facts_dir / f"{case_id}.json"
    context_summary = _context_summary(context_path)
    fact_summary = _fact_summary(facts_path)
    review_decision = str((review or {}).get("decision") or "missing_manual_review")

    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    if gate == "trap_smoke":
        if not task_type.startswith(TRAP_TASK_PREFIX):
            return _case_result(
                case,
                review_decision,
                context_summary,
                fact_summary,
                status="skipped_not_applicable",
                blockers=[],
                warnings=[],
            )
        if review_decision != "approved_for_pipeline_trap_smoke":
            blockers.append({"type": "trap_case_not_review_approved", "decision": review_decision})
        return _case_result(
            case,
            review_decision,
            context_summary,
            fact_summary,
            blockers=blockers,
            warnings=warnings,
        )

    if gate == "context_smoke":
        if "gold_context" not in set(case.get("evaluation_modes") or []):
            return _case_result(
                case,
                review_decision,
                context_summary,
                fact_summary,
                status="skipped_not_applicable",
                blockers=[],
                warnings=[],
            )
        if not context_path.exists():
            blockers.append({"type": "gold_context_missing", "expected_path": str(context_path)})
        if context_summary["seed_row_count"]:
            warnings.append(
                {
                    "type": "seed_gold_context_smoke_only",
                    "seed_row_count": context_summary["seed_row_count"],
                }
            )
        if fact_summary["seed_fact_count"]:
            warnings.append(
                {
                    "type": "seed_gold_facts_smoke_only",
                    "seed_fact_count": fact_summary["seed_fact_count"],
                }
            )
        return _case_result(
            case,
            review_decision,
            context_summary,
            fact_summary,
            blockers=blockers,
            warnings=warnings,
        )

    if not review:
        blockers.append({"type": "missing_manual_case_review"})
    if review_decision not in MAINLINE_ALLOWED_CASE_DECISIONS:
        blockers.append({"type": "manual_review_not_mainline_approved", "decision": review_decision})
    if gold_status == "needs_annotation":
        if not context_path.exists():
            blockers.append({"type": "gold_context_missing", "expected_path": str(context_path)})
        if context_summary["seed_row_count"]:
            blockers.append(
                {
                    "type": "seed_gold_context_not_reviewed",
                    "seed_row_count": context_summary["seed_row_count"],
                }
            )
        if fact_summary["seed_fact_count"]:
            blockers.append(
                {
                    "type": "seed_gold_facts_not_reviewed",
                    "seed_fact_count": fact_summary["seed_fact_count"],
                }
            )
        blockers.extend(_numeric_fact_blockers(case, facts_path))
        if context_summary["row_count"] > max_mainline_context_rows:
            blockers.append(
                {
                    "type": "gold_context_too_wide_for_mainline",
                    "row_count": context_summary["row_count"],
                    "max_rows": max_mainline_context_rows,
                }
            )
    elif task_type.startswith(TRAP_TASK_PREFIX):
        if review_decision != "approved_for_pipeline_trap_smoke":
            blockers.append({"type": "trap_case_not_review_approved", "decision": review_decision})
    else:
        blockers.append({"type": "unexpected_gold_context_status", "gold_context_status": gold_status})

    return _case_result(
        case,
        review_decision,
        context_summary,
        fact_summary,
        blockers=blockers,
        warnings=warnings,
    )


def _case_result(
    case: dict[str, Any],
    review_decision: str,
    context_summary: dict[str, Any],
    fact_summary: dict[str, Any],
    blockers: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    status: str | None = None,
) -> dict[str, Any]:
    resolved_status = status or ("fail" if blockers else "pass")
    return {
        "case_id": case.get("case_id"),
        "task_type": case.get("task_type"),
        "level": case.get("level"),
        "review_decision": review_decision,
        "status": resolved_status,
        "blockers": blockers,
        "warnings": warnings,
        "context_summary": context_summary,
        "fact_summary": fact_summary,
    }


def _overall_blockers(
    gate: str,
    manual_review: dict[str, Any],
    requested_case_ids: set[str],
) -> list[dict[str, Any]]:
    if gate != "mainline_scored":
        return []
    overall_status = manual_review.get("review_decision", {}).get("overall_status")
    if overall_status == MAINLINE_ALLOWED_OVERALL_STATUS:
        return []
    if requested_case_ids and overall_status == PARTIAL_MAINLINE_ALLOWED_OVERALL_STATUS:
        return []
    return [
        {
            "type": "manual_review_overall_not_mainline_approved",
            "overall_status": overall_status,
            "required_status": MAINLINE_ALLOWED_OVERALL_STATUS,
            "case_filter_partial_status_allowed": bool(requested_case_ids),
        }
    ]


def _context_summary(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "path": str(path),
            "exists": False,
            "row_count": 0,
            "seed_row_count": 0,
            "review_status_counts": {},
            "source_kind_counts": {},
        }
    rows = _read_jsonl(path)
    review_status_counts = Counter(str(row.get("review_status") or "missing") for row in rows)
    source_kind_counts = Counter(str(row.get("source_kind") or "missing") for row in rows)
    return {
        "path": str(path),
        "exists": True,
        "row_count": len(rows),
        "seed_row_count": sum(count for status, count in review_status_counts.items() if status in SEED_REVIEW_STATUSES),
        "review_status_counts": dict(sorted(review_status_counts.items())),
        "source_kind_counts": dict(sorted(source_kind_counts.items())),
    }


def _fact_summary(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "path": str(path),
            "exists": False,
            "fact_count": 0,
            "seed_fact_count": 0,
            "review_status": None,
            "review_status_counts": {},
        }
    payload = _read_json(path)
    facts = payload.get("facts") or []
    review_status_counts = Counter(str(fact.get("review_status") or "missing") for fact in facts)
    payload_status = str(payload.get("review_status") or "missing")
    seed_fact_count = sum(
        count for status, count in review_status_counts.items() if status in SEED_REVIEW_STATUSES
    )
    if payload_status in SEED_REVIEW_STATUSES and not facts:
        seed_fact_count = len(facts)
    return {
        "path": str(path),
        "exists": True,
        "fact_count": len(facts),
        "seed_fact_count": seed_fact_count,
        "review_status": payload_status,
        "review_status_counts": dict(sorted(review_status_counts.items())),
    }


def _numeric_fact_blockers(case: dict[str, Any], facts_path: Path) -> list[dict[str, Any]]:
    numeric_checks = case.get("numeric_checks") or []
    if not numeric_checks:
        return []
    if not facts_path.exists():
        return [{"type": "reviewed_gold_facts_missing", "expected_path": str(facts_path)}]
    payload = _read_json(facts_path)
    reviewed_facts = [
        fact
        for fact in payload.get("facts") or []
        if str(fact.get("review_status") or "") == "reviewed_keep"
    ]
    blockers: list[dict[str, Any]] = []
    for check in numeric_checks:
        check_companies = {str(item).upper() for item in check.get("companies") or case.get("companies") or []}
        check_years = {int(item) for item in check.get("years") or case.get("years") or []}
        check_families = {str(item) for item in check.get("metric_families") or []}
        check_roles = {str(item) for item in check.get("metric_roles") or []}
        expected_facts = [item for item in check.get("expected_facts") or [] if isinstance(item, dict)]
        metric_text = str(check.get("metric") or "").lower()
        require_each_family = bool(len(check_families) > 1 and " and " in metric_text and " or " not in metric_text)
        for ticker in sorted(check_companies):
            for year in sorted(check_years):
                base_matches = [
                    fact
                    for fact in reviewed_facts
                    if str(fact.get("ticker") or "").upper() == ticker
                    and _int_or_none(fact.get("fiscal_year")) == year
                    and _int_or_none(fact.get("period")) == year
                    and (not check_roles or str(fact.get("metric_role") or "") in check_roles)
                    and str(fact.get("object_id") or "")
                    and str(fact.get("source_evidence_id") or "")
                ]
                if expected_facts:
                    for expected in expected_facts:
                        expected_match_count = int(expected.get("expected_match_count") or 1)
                        matches = [
                            fact
                            for fact in base_matches
                            if _fact_matches_expected(fact, expected, check_roles)
                        ]
                        if len(matches) != expected_match_count:
                            blockers.append(
                                {
                                    "type": "reviewed_numeric_fact_expected_coverage_mismatch",
                                    "metric": check.get("metric"),
                                    "expected_fact": {
                                        key: expected.get(key)
                                        for key in [
                                            "label",
                                            "metric_family",
                                            "metric_role",
                                            "metric_name",
                                            "row_label",
                                            "column_label",
                                            "segment",
                                        ]
                                        if expected.get(key) is not None
                                    },
                                    "ticker": ticker,
                                    "year": year,
                                    "expected_match_count": expected_match_count,
                                    "actual_match_count": len(matches),
                                }
                            )
                elif require_each_family:
                    for family in sorted(check_families):
                        matches = [
                            fact
                            for fact in base_matches
                            if str(fact.get("metric_family") or "") == family
                        ]
                        if len(matches) != 1:
                            blockers.append(
                                {
                                    "type": "reviewed_numeric_fact_coverage_mismatch",
                                    "metric": check.get("metric"),
                                    "metric_family": family,
                                    "ticker": ticker,
                                    "year": year,
                                    "expected_match_count": 1,
                                    "actual_match_count": len(matches),
                                }
                            )
                else:
                    matches = [
                        fact
                        for fact in base_matches
                        if not check_families or str(fact.get("metric_family") or "") in check_families
                    ]
                    if len(matches) != 1:
                        blockers.append(
                            {
                                "type": "reviewed_numeric_fact_coverage_mismatch",
                                "metric": check.get("metric"),
                                "ticker": ticker,
                                "year": year,
                                "expected_match_count": 1,
                                "actual_match_count": len(matches),
                            }
                        )
    return blockers


def _fact_matches_expected(
    fact: dict[str, Any],
    expected: dict[str, Any],
    default_roles: set[str],
) -> bool:
    expected_family = str(expected.get("metric_family") or "")
    if expected_family and str(fact.get("metric_family") or "") != expected_family:
        return False
    expected_role = str(expected.get("metric_role") or "")
    if expected_role:
        if str(fact.get("metric_role") or "") != expected_role:
            return False
    elif default_roles and str(fact.get("metric_role") or "") not in default_roles:
        return False
    for field in ["metric_name", "row_label", "column_label", "segment"]:
        if not _expected_text_match(fact.get(field), expected.get(field)):
            return False
    return True


def _expected_text_match(actual: Any, expected: Any) -> bool:
    if expected is None:
        return True
    if isinstance(expected, list):
        return any(_expected_text_match(actual, item) for item in expected)
    return _normalize_text(actual) == _normalize_text(expected)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").casefold().split())


if __name__ == "__main__":
    main()
