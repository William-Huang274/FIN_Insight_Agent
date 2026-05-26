from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


STRENGTH_RANK = {"weak": 1, "medium": 2, "strong": 3}
PROXY_CAVEAT_TERMS = (
    "proxy",
    "代理",
    "广义",
    "口径",
    "混合",
    "不能直接",
    "不可直接",
    "not directly",
    "not comparable",
    "用量",
    "usage",
    "不同",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate SEC benchmark final answers against a validated Judgment Plan."
    )
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--judgment-plan-path", required=True)
    parser.add_argument("--output-path", default="")
    parser.add_argument(
        "--allow-plan-evidence-only",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Allow final answers to cite IDs from the Judgment Plan even if those IDs were not in trace topK.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_dir = _resolve(args.run_dir)
    plan_payload = _read_json(_resolve(args.judgment_plan_path))
    plans = {
        str(plan.get("case_id") or ""): plan
        for plan in plan_payload.get("plans") or []
        if isinstance(plan, dict)
    }
    agent_rows = _read_jsonl(run_dir / "agent_outputs.jsonl")
    case_results = [
        _validate_agent_row(row, plans.get(str(row.get("case_id") or "")))
        for row in agent_rows
    ]
    failure_counts = Counter(
        failure.get("type")
        for result in case_results
        for failure in result.get("failures") or []
    )
    warning_counts = Counter(
        warning.get("type")
        for result in case_results
        for warning in result.get("warnings") or []
    )
    fail_by_case = Counter(
        result.get("case_id")
        for result in case_results
        if result.get("status") == "fail"
    )
    report = {
        "schema_version": "sec_benchmark_answer_vs_judgment_plan_gate_v0.1",
        "run_dir": str(run_dir.resolve()),
        "judgment_plan_path": str(_resolve(args.judgment_plan_path).resolve()),
        "can_enter_gate": not failure_counts,
        "summary": {
            "case_count": len(case_results),
            "checked_case_count": sum(result.get("status") != "skipped" for result in case_results),
            "pass_count": sum(result.get("status") == "pass" for result in case_results),
            "fail_count": sum(result.get("status") == "fail" for result in case_results),
            "skip_count": sum(result.get("status") == "skipped" for result in case_results),
            "failure_types": dict(sorted(failure_counts.items())),
            "warning_types": dict(sorted(warning_counts.items())),
            "fail_by_case": dict(sorted(fail_by_case.items())),
        },
        "case_results": case_results,
    }
    output_path = _resolve(args.output_path) if args.output_path else run_dir / "answer_vs_judgment_plan_gate.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output_path": str(output_path),
                "can_enter_gate": report["can_enter_gate"],
                **report["summary"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def _validate_agent_row(agent: dict[str, Any], plan: dict[str, Any] | None) -> dict[str, Any]:
    case_id = str(agent.get("case_id") or "")
    mode = str(agent.get("mode") or "")
    if not plan:
        return _skipped(case_id, mode, "judgment_plan_not_found_for_case")
    if str(agent.get("status") or "") != "answered" or not isinstance(agent.get("answer"), dict):
        return _skipped(case_id, mode, "agent_output_not_answered_or_answer_not_object")

    answer = agent.get("answer") or {}
    failures: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    plan_drivers = [driver for driver in plan.get("drivers") or [] if isinstance(driver, dict)]
    plan_metric_ids = {
        metric_id
        for driver in plan_drivers
        for metric_id in _string_list(driver.get("supporting_metric_ids"))
    }
    plan_evidence_ids = {
        evidence_id
        for driver in plan_drivers
        for evidence_id in _string_list(driver.get("supporting_evidence_ids"))
    }
    plan_by_metric = {
        metric_id: driver
        for driver in plan_drivers
        for metric_id in _string_list(driver.get("supporting_metric_ids"))
    }
    plan_by_evidence = {
        evidence_id: driver
        for driver in plan_drivers
        for evidence_id in _string_list(driver.get("supporting_evidence_ids"))
    }

    answer_drivers = [driver for driver in answer.get("decision_drivers") or [] if isinstance(driver, dict)]
    if len(answer_drivers) > len(plan_drivers):
        failures.append(
            {
                "type": "answer_driver_count_exceeds_plan",
                "answer_driver_count": len(answer_drivers),
                "plan_driver_count": len(plan_drivers),
            }
        )
    for index, driver in enumerate(answer_drivers, start=1):
        _validate_answer_driver(
            driver=driver,
            driver_index=index,
            plan_drivers=plan_drivers,
            plan_metric_ids=plan_metric_ids,
            plan_evidence_ids=plan_evidence_ids,
            failures=failures,
            warnings=warnings,
        )

    for location in _answer_support_locations(answer):
        metric_ids = set(location["metric_ids"])
        evidence_ids = set(location["evidence_ids"])
        unknown_metrics = sorted(metric_ids - plan_metric_ids)
        unknown_evidence = sorted(evidence_ids - plan_evidence_ids)
        if unknown_metrics:
            failures.append(
                {
                    "type": "answer_support_metric_id_not_in_plan",
                    "location": location["location"],
                    "metric_ids": unknown_metrics,
                }
            )
        if unknown_evidence:
            failures.append(
                {
                    "type": "answer_support_evidence_id_not_in_plan",
                    "location": location["location"],
                    "evidence_ids": unknown_evidence,
                }
            )
        if location["location"].startswith("key_points") and not metric_ids and not evidence_ids:
            warnings.append({"type": "key_point_without_plan_support", "location": location["location"]})

    _validate_plan_overstatement(answer, plan, plan_by_metric, plan_by_evidence, failures)
    return {
        "case_id": case_id,
        "mode": mode,
        "status": "fail" if failures else "pass",
        "answer_status": agent.get("answer_status"),
        "plan_driver_count": len(plan_drivers),
        "answer_driver_count": len(answer_drivers),
        "failures": failures,
        "warnings": warnings,
    }


def _validate_answer_driver(
    *,
    driver: dict[str, Any],
    driver_index: int,
    plan_drivers: list[dict[str, Any]],
    plan_metric_ids: set[str],
    plan_evidence_ids: set[str],
    failures: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> None:
    metric_ids = set(_string_list(driver.get("supporting_metric_ids")))
    evidence_ids = set(_string_list(driver.get("supporting_evidence_ids")))
    if not metric_ids and not evidence_ids:
        failures.append({"type": "answer_driver_without_support", "driver_index": driver_index})
        return
    matched = _best_matching_plan_driver(metric_ids, evidence_ids, plan_drivers)
    if not matched:
        failures.append(
            {
                "type": "answer_driver_not_matched_to_plan_driver",
                "driver_index": driver_index,
                "metric_ids": sorted(metric_ids),
                "evidence_ids": sorted(evidence_ids),
            }
        )
        return

    unknown_metrics = sorted(metric_ids - plan_metric_ids)
    unknown_evidence = sorted(evidence_ids - plan_evidence_ids)
    if unknown_metrics:
        failures.append(
            {
                "type": "answer_driver_metric_id_not_in_plan",
                "driver_index": driver_index,
                "metric_ids": unknown_metrics,
            }
        )
    if unknown_evidence:
        failures.append(
            {
                "type": "answer_driver_evidence_id_not_in_plan",
                "driver_index": driver_index,
                "evidence_ids": unknown_evidence,
            }
        )
    matched_metric_ids = set(_string_list(matched.get("supporting_metric_ids")))
    matched_evidence_ids = set(_string_list(matched.get("supporting_evidence_ids")))
    off_driver_metrics = sorted(metric_ids - matched_metric_ids)
    off_driver_evidence = sorted(evidence_ids - matched_evidence_ids)
    if off_driver_metrics:
        failures.append(
            {
                "type": "answer_driver_metric_id_not_in_matched_plan_driver",
                "driver_index": driver_index,
                "matched_plan_rank": matched.get("rank"),
                "metric_ids": off_driver_metrics,
            }
        )
    if off_driver_evidence:
        failures.append(
            {
                "type": "answer_driver_evidence_id_not_in_matched_plan_driver",
                "driver_index": driver_index,
                "matched_plan_rank": matched.get("rank"),
                "evidence_ids": off_driver_evidence,
            }
        )

    answer_strength = str(driver.get("conclusion_strength") or "")
    plan_strength = str(matched.get("conclusion_strength") or "")
    if answer_strength not in STRENGTH_RANK:
        failures.append(
            {"type": "answer_driver_strength_invalid", "driver_index": driver_index, "strength": answer_strength}
        )
    elif STRENGTH_RANK.get(answer_strength, 0) > STRENGTH_RANK.get(plan_strength, 0):
        failures.append(
            {
                "type": "answer_driver_strength_exceeds_plan",
                "driver_index": driver_index,
                "answer_strength": answer_strength,
                "plan_strength": plan_strength,
                "matched_plan_rank": matched.get("rank"),
            }
        )

    caveat = str(driver.get("caveat") or "")
    plan_has_caveat = bool(matched.get("caveats"))
    if plan_has_caveat and not caveat.strip():
        failures.append({"type": "answer_driver_missing_required_caveat", "driver_index": driver_index})
    uses_proxy = any("proxy" in metric_id.lower() for metric_id in metric_ids) or any(
        "proxy" in str(family).lower() for family in matched.get("metric_families") or []
    )
    if uses_proxy:
        if answer_strength == "strong":
            failures.append({"type": "proxy_answer_driver_marked_strong", "driver_index": driver_index})
        if not _contains_any(caveat, PROXY_CAVEAT_TERMS):
            failures.append({"type": "proxy_answer_driver_missing_caveat", "driver_index": driver_index})


def _validate_plan_overstatement(
    answer: dict[str, Any],
    plan: dict[str, Any],
    plan_by_metric: dict[str, dict[str, Any]],
    plan_by_evidence: dict[str, dict[str, Any]],
    failures: list[dict[str, Any]],
) -> None:
    main_strength = str((plan.get("main_judgment") or {}).get("strength") or "")
    answer_text = _answer_text(answer)
    if main_strength in {"weak", "medium"} and re.search(r"(最强|明确赢家|明显优于|simple winner|strong winner)", answer_text, re.I):
        failures.append(
            {
                "type": "answer_main_overstates_plan_strength",
                "plan_strength": main_strength,
            }
        )
    for location in _answer_support_locations(answer):
        related = []
        for metric_id in location["metric_ids"]:
            if metric_id in plan_by_metric:
                related.append(plan_by_metric[metric_id])
        for evidence_id in location["evidence_ids"]:
            if evidence_id in plan_by_evidence:
                related.append(plan_by_evidence[evidence_id])
        if not related:
            continue
        if any(str(driver.get("conclusion_strength") or "") == "weak" for driver in related):
            text = str(location["text"])
            if re.search(r"(强劲|显著|高质量|clear|strong)", text, re.I) and not re.search(
                r"(但|限制|proxy|代理|口径|不能直接|caveat|受限|无法|未提供|缺乏|not disclosed|not found|lacks|limited)",
                text,
                re.I,
            ):
                failures.append(
                    {
                        "type": "weak_plan_support_used_without_local_caveat",
                        "location": location["location"],
                        "near_text": text[:260],
                    }
                )


def _best_matching_plan_driver(
    metric_ids: set[str],
    evidence_ids: set[str],
    plan_drivers: list[dict[str, Any]],
) -> dict[str, Any] | None:
    best = None
    best_score = 0
    for driver in plan_drivers:
        driver_metrics = set(_string_list(driver.get("supporting_metric_ids")))
        driver_evidence = set(_string_list(driver.get("supporting_evidence_ids")))
        score = len(metric_ids & driver_metrics) * 10 + len(evidence_ids & driver_evidence)
        if score > best_score:
            best = driver
            best_score = score
    return best if best_score > 0 else None


def _answer_support_locations(answer: dict[str, Any]) -> list[dict[str, Any]]:
    locations = []
    for index, driver in enumerate(answer.get("decision_drivers") or [], start=1):
        if not isinstance(driver, dict):
            continue
        locations.append(
            {
                "location": f"decision_drivers[{index}]",
                "text": " ".join(
                    str(driver.get(key) or "")
                    for key in ("driver_claim", "why_it_matters", "caveat")
                ),
                "metric_ids": _string_list(driver.get("supporting_metric_ids")),
                "evidence_ids": _string_list(driver.get("supporting_evidence_ids")),
            }
        )
    for index, point in enumerate(answer.get("key_points") or [], start=1):
        if not isinstance(point, dict):
            continue
        locations.append(
            {
                "location": f"key_points[{index}]",
                "text": str(point.get("point") or ""),
                "metric_ids": _string_list(point.get("metric_ids")),
                "evidence_ids": _string_list(point.get("evidence_ids")),
            }
        )
    return locations


def _answer_text(answer: dict[str, Any]) -> str:
    fragments = [str(answer.get("summary") or "")]
    for location in _answer_support_locations(answer):
        fragments.append(str(location["text"]))
    fragments.extend(str(item) for item in answer.get("limitations") or [])
    fragments.extend(str(item) for item in answer.get("not_found") or [])
    return "\n".join(fragments)


def _skipped(case_id: str, mode: str, reason: str) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "mode": mode,
        "status": "skipped",
        "reason": reason,
        "failures": [],
        "warnings": [],
    }


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item or "").strip()]
    if value:
        return [str(value)]
    return []


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(term.lower() in lowered for term in terms)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _resolve(path: str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return REPO_ROOT / candidate


if __name__ == "__main__":
    main()
