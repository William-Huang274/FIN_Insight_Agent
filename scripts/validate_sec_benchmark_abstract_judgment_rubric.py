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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate Chinese abstract-judgment coverage against a manual SEC benchmark rubric."
    )
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--cases-path", default="eval/sec_cases/test_cases_v1.jsonl")
    parser.add_argument(
        "--rubric-path",
        default="eval/sec_cases/abstract_judgment_rubric_v0_1.json",
    )
    parser.add_argument("--output-path", default="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_dir = _resolve(args.run_dir)
    cases_path = _resolve(args.cases_path)
    rubric_path = _resolve(args.rubric_path)
    rubric = _read_json(rubric_path)
    case_task_types = _case_task_types(cases_path)
    rows = _read_jsonl(run_dir / "agent_outputs.jsonl")
    case_results = [
        _validate_agent_row(row, case_task_types.get(str(row.get("case_id") or ""), ""), rubric)
        for row in rows
    ]
    failures = Counter(
        failure.get("type")
        for result in case_results
        for failure in result.get("failures") or []
    )
    warnings = Counter(
        warning.get("type")
        for result in case_results
        for warning in result.get("warnings") or []
    )
    fail_by_case = Counter(
        result.get("case_id")
        for result in case_results
        if result.get("status") == "fail"
    )
    checked = [result for result in case_results if result.get("status") != "skipped"]
    report = {
        "schema_version": "sec_benchmark_abstract_judgment_rubric_gate_v0.1",
        "run_dir": str(run_dir.resolve()),
        "rubric_path": str(rubric_path.resolve()),
        "can_enter_gate": not failures,
        "summary": {
            "case_count": len(case_results),
            "checked_case_count": len(checked),
            "pass_count": sum(result.get("status") == "pass" for result in case_results),
            "fail_count": sum(result.get("status") == "fail" for result in case_results),
            "skip_count": sum(result.get("status") == "skipped" for result in case_results),
            "required_dimension_count": sum(
                int(result.get("required_dimension_count") or 0) for result in checked
            ),
            "covered_required_dimension_count": sum(
                int(result.get("covered_required_dimension_count") or 0) for result in checked
            ),
            "failure_types": dict(sorted(failures.items())),
            "warning_types": dict(sorted(warnings.items())),
            "fail_by_case": dict(sorted(fail_by_case.items())),
        },
        "case_results": case_results,
    }
    output_path = _resolve(args.output_path) if args.output_path else run_dir / "abstract_judgment_gate.json"
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


def _validate_agent_row(row: dict[str, Any], task_type: str, rubric: dict[str, Any]) -> dict[str, Any]:
    case_id = str(row.get("case_id") or "")
    mode = str(row.get("mode") or "")
    answer_status = str(row.get("answer_status") or "")
    case_rubric = (rubric.get("cases") or {}).get(case_id)
    if str(task_type).startswith("anti_hallucination") or answer_status.startswith("answered_contract_fallback"):
        return _skipped_result(case_id, mode, answer_status, "trap_or_contract_fallback")
    if not case_rubric:
        return _skipped_result(case_id, mode, answer_status, "rubric_not_defined")
    if str(row.get("status") or "") != "answered" or not isinstance(row.get("answer"), dict):
        return _skipped_result(case_id, mode, answer_status, "agent_output_not_answered_or_answer_not_object")

    answer = row.get("answer") or {}
    text_blocks = _answer_text_blocks(answer, row.get("claims") or [], row.get("limitations") or [])
    failures: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    global_rules = rubric.get("global_rules") or {}
    failures.extend(_structure_failures(answer, global_rules, case_rubric))

    dimension_results = []
    for dimension in case_rubric.get("dimensions") or []:
        result = _evaluate_dimension(dimension, text_blocks)
        dimension_results.append(result)
        if dimension.get("required", True) and not result["passed"]:
            failures.append(
                {
                    "type": "required_abstract_dimension_missing",
                    "dimension_id": result["dimension_id"],
                    "description": result["description"],
                    "missing_groups": result["missing_groups"],
                }
            )

    calibration_results = []
    for check in case_rubric.get("calibration_checks") or []:
        result = _evaluate_dimension(check, text_blocks)
        calibration_results.append(result)
        if check.get("required", True) and not result["passed"]:
            failures.append(
                {
                    "type": "conclusion_calibration_missing",
                    "dimension_id": result["dimension_id"],
                    "description": result["description"],
                    "missing_groups": result["missing_groups"],
                }
            )

    for forbidden in case_rubric.get("forbidden_claims") or []:
        failures.extend(_forbidden_claim_failures(forbidden, text_blocks["answer"]))

    required_dimension_count = sum(1 for item in dimension_results if item.get("required", True))
    covered_required_dimension_count = sum(
        1 for item in dimension_results if item.get("required", True) and item.get("passed")
    )
    min_ratio = float(case_rubric.get("min_required_coverage_ratio", 1.0))
    coverage_ratio = (
        covered_required_dimension_count / required_dimension_count
        if required_dimension_count
        else 1.0
    )
    if coverage_ratio < min_ratio:
        failures.append(
            {
                "type": "abstract_dimension_coverage_below_threshold",
                "required_coverage_ratio": min_ratio,
                "actual_coverage_ratio": round(coverage_ratio, 4),
            }
        )

    return {
        "case_id": case_id,
        "mode": mode,
        "answer_status": answer_status,
        "status": "fail" if failures else "pass",
        "coverage_ratio": round(coverage_ratio, 4),
        "required_dimension_count": required_dimension_count,
        "covered_required_dimension_count": covered_required_dimension_count,
        "dimension_results": dimension_results,
        "calibration_results": calibration_results,
        "failures": failures,
        "warnings": warnings,
    }


def _structure_failures(answer: dict[str, Any], global_rules: dict[str, Any], case_rubric: dict[str, Any]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    drivers = [item for item in answer.get("decision_drivers") or [] if isinstance(item, dict)]
    max_drivers = int(case_rubric.get("max_decision_drivers", global_rules.get("max_decision_drivers", 3)))
    min_drivers = int(case_rubric.get("min_decision_drivers", global_rules.get("min_decision_drivers", 1)))
    if len(drivers) < min_drivers:
        failures.append(
            {
                "type": "decision_driver_count_below_minimum",
                "expected_min": min_drivers,
                "actual_count": len(drivers),
            }
        )
    if len(drivers) > max_drivers:
        failures.append(
            {
                "type": "decision_driver_count_above_maximum",
                "expected_max": max_drivers,
                "actual_count": len(drivers),
            }
        )
    if bool(case_rubric.get("require_supported_decision_drivers", global_rules.get("require_supported_decision_drivers", True))):
        for index, driver in enumerate(drivers, start=1):
            evidence_ids = _string_list(driver.get("supporting_evidence_ids"))
            metric_ids = _string_list(driver.get("supporting_metric_ids"))
            if not evidence_ids and not metric_ids:
                failures.append(
                    {
                        "type": "decision_driver_without_support",
                        "driver_index": index,
                        "driver_claim": str(driver.get("driver_claim") or "")[:200],
                    }
                )
    return failures


def _evaluate_dimension(dimension: dict[str, Any], text_blocks: dict[str, str]) -> dict[str, Any]:
    where = str(dimension.get("where") or "answer")
    text = text_blocks.get(where, text_blocks["answer"])
    groups = dimension.get("all_of_any") or []
    if not groups and dimension.get("match_any"):
        groups = [dimension.get("match_any") or []]
    missing_groups = []
    matched_groups = []
    for group in groups:
        group_patterns = [str(item) for item in group]
        matched = [pattern for pattern in group_patterns if _pattern_matches(pattern, text)]
        if matched:
            matched_groups.append({"patterns": group_patterns, "matched": matched})
        else:
            missing_groups.append(group_patterns)
    return {
        "dimension_id": str(dimension.get("id") or ""),
        "description": str(dimension.get("description") or ""),
        "where": where,
        "required": bool(dimension.get("required", True)),
        "passed": not missing_groups,
        "missing_groups": missing_groups,
        "matched_groups": matched_groups,
    }


def _forbidden_claim_failures(forbidden: dict[str, Any], text: str) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    patterns = [str(pattern) for pattern in forbidden.get("patterns") or []]
    allow_any = [str(pattern) for pattern in forbidden.get("allow_if_any") or []]
    allow_near = [str(pattern) for pattern in forbidden.get("allow_if_any_near") or []]
    window = int(forbidden.get("near_window_chars", 80))
    for pattern in patterns:
        for match in _pattern_finditer(pattern, text):
            if allow_any and any(_pattern_matches(allow, text) for allow in allow_any):
                continue
            near_text = text[max(0, match.start() - window) : min(len(text), match.end() + window)]
            if allow_near and any(_pattern_matches(allow, near_text) for allow in allow_near):
                continue
            failures.append(
                {
                    "type": "forbidden_abstract_overclaim",
                    "claim_id": str(forbidden.get("id") or ""),
                    "description": str(forbidden.get("description") or ""),
                    "pattern": pattern,
                    "near_text": near_text,
                }
            )
    return failures


def _answer_text_blocks(answer: dict[str, Any], claims: list[Any], outer_limitations: list[Any]) -> dict[str, str]:
    summary = str(answer.get("summary") or "")
    driver_texts: list[str] = []
    caveat_texts: list[str] = []
    for driver in answer.get("decision_drivers") or []:
        if not isinstance(driver, dict):
            continue
        driver_texts.append(
            " ".join(
                str(driver.get(key) or "")
                for key in ("driver_claim", "why_it_matters", "conclusion_strength", "caveat")
            )
        )
        caveat_texts.append(str(driver.get("caveat") or ""))
    key_point_texts = [
        str(item.get("point") or "")
        for item in answer.get("key_points") or []
        if isinstance(item, dict)
    ]
    limitations = [str(item) for item in answer.get("limitations") or []]
    limitations.extend(str(item) for item in outer_limitations or [])
    claim_texts = [
        str(item.get("claim") or "")
        for item in claims
        if isinstance(item, dict)
    ]
    answer_text = "\n".join(
        part
        for part in [
            summary,
            "\n".join(driver_texts),
            "\n".join(key_point_texts),
            "\n".join(limitations),
            "\n".join(claim_texts),
        ]
        if part
    )
    return {
        "answer": answer_text,
        "summary": summary,
        "drivers": "\n".join(driver_texts),
        "key_points": "\n".join(key_point_texts),
        "caveats": "\n".join(caveat_texts + limitations),
        "limitations": "\n".join(limitations),
    }


def _pattern_matches(pattern: str, text: str) -> bool:
    if pattern.startswith("re:"):
        return re.search(pattern[3:], text, flags=re.IGNORECASE) is not None
    return pattern.lower() in text.lower()


def _pattern_finditer(pattern: str, text: str) -> list[re.Match[str]]:
    if pattern.startswith("re:"):
        return list(re.finditer(pattern[3:], text, flags=re.IGNORECASE))
    escaped = re.escape(pattern)
    return list(re.finditer(escaped, text, flags=re.IGNORECASE))


def _case_task_types(cases_path: Path) -> dict[str, str]:
    if not cases_path.exists():
        return {}
    return {str(row.get("case_id") or ""): str(row.get("task_type") or "") for row in _read_jsonl(cases_path)}


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if value is None:
        return []
    text = str(value).strip()
    return [text] if text else []


def _skipped_result(case_id: str, mode: str, answer_status: str, reason: str) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "mode": mode,
        "answer_status": answer_status,
        "status": "skipped",
        "reason": reason,
        "required_dimension_count": 0,
        "covered_required_dimension_count": 0,
        "dimension_results": [],
        "calibration_results": [],
        "failures": [],
        "warnings": [],
    }


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _resolve(path: str) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else REPO_ROOT / candidate


if __name__ == "__main__":
    main()
