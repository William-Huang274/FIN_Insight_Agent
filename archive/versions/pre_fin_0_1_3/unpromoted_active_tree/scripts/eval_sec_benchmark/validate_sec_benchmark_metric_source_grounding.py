from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate that metric-backed SEC benchmark answer locations cite "
            "the source evidence or structured object backing each metric_id."
        )
    )
    parser.add_argument("--run-dir", required=True)
    parser.add_argument(
        "--ledger-path",
        default="reports/exact_value_ledgers/sec_benchmark_v1_reviewed_exact_value_ledger.json",
    )
    parser.add_argument("--cases-path", default="eval/sec_cases/test_cases_v1.jsonl")
    parser.add_argument("--output-path", default="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_dir = _resolve(args.run_dir)
    ledger = _read_json(_resolve(args.ledger_path))
    case_task_types = _case_task_types(_resolve(args.cases_path))

    rows_by_case: dict[str, dict[str, dict[str, Any]]] = {}
    for row in ledger.get("rows") or []:
        case_id = str(row.get("case_id") or "")
        metric_id = str(row.get("metric_id") or "")
        if case_id and metric_id:
            rows_by_case.setdefault(case_id, {})[metric_id] = row

    agent_rows = _read_jsonl(run_dir / "agent_outputs.jsonl")
    case_results = [
        _validate_agent_row(
            agent,
            rows_by_case.get(str(agent.get("case_id") or ""), {}),
            case_task_types.get(str(agent.get("case_id") or ""), ""),
        )
        for agent in agent_rows
    ]
    failure_counts = Counter(
        failure.get("type")
        for result in case_results
        for failure in result.get("failures") or []
    )
    fail_by_case = Counter(
        result.get("case_id")
        for result in case_results
        if result.get("status") == "fail"
    )
    report = {
        "schema_version": "sec_benchmark_metric_source_grounding_gate_v0.1",
        "run_dir": str(run_dir.resolve()),
        "ledger_path": str(_resolve(args.ledger_path).resolve()),
        "cases_path": str(_resolve(args.cases_path).resolve()),
        "can_enter_gate": not failure_counts,
        "summary": {
            "case_count": len(case_results),
            "pass_count": sum(result.get("status") == "pass" for result in case_results),
            "fail_count": sum(result.get("status") == "fail" for result in case_results),
            "skip_count": sum(result.get("status") == "skipped" for result in case_results),
            "checked_location_count": sum(int(result.get("checked_location_count") or 0) for result in case_results),
            "metric_reference_count": sum(int(result.get("metric_reference_count") or 0) for result in case_results),
            "failure_types": dict(sorted(failure_counts.items())),
            "fail_by_case": dict(sorted(fail_by_case.items())),
        },
        "case_results": case_results,
    }
    output_path = _resolve(args.output_path) if args.output_path else run_dir / "metric_source_grounding_gate.json"
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


def _validate_agent_row(
    agent: dict[str, Any],
    ledger_by_metric: dict[str, dict[str, Any]],
    task_type: str,
) -> dict[str, Any]:
    case_id = str(agent.get("case_id") or "")
    mode = str(agent.get("mode") or "")
    answer_status = str(agent.get("answer_status") or "")
    if str(task_type).startswith("anti_hallucination") or answer_status.startswith("answered_contract_fallback"):
        return _skipped_result(case_id, mode, answer_status, "trap_or_contract_fallback")
    if str(agent.get("status") or "") != "answered" or not isinstance(agent.get("answer"), dict):
        return _skipped_result(case_id, mode, answer_status, "agent_output_not_answered_or_answer_not_object")

    failures: list[dict[str, Any]] = []
    locations = _metric_locations(agent.get("answer") or {})
    metric_reference_count = 0
    checked_location_count = 0
    for location in locations:
        metric_ids = _string_list(location.get("metric_ids"))
        if not metric_ids:
            continue
        checked_location_count += 1
        cited_ids = set(_string_list(location.get("evidence_ids")))
        metric_reference_count += len(metric_ids)
        if not cited_ids:
            failures.append(
                {
                    "type": "metric_location_missing_evidence_ids",
                    "location": location["location"],
                    "metric_ids": metric_ids,
                    "near_text": str(location.get("text") or "")[:260],
                }
            )
            continue
        for metric_id in metric_ids:
            row = ledger_by_metric.get(metric_id)
            if not row:
                failures.append(
                    {
                        "type": "metric_id_not_found_in_ledger",
                        "location": location["location"],
                        "metric_id": metric_id,
                    }
                )
                continue
            allowed_ids = _ledger_source_ids(row)
            if not allowed_ids:
                failures.append(
                    {
                        "type": "ledger_metric_missing_source_id",
                        "location": location["location"],
                        "metric_id": metric_id,
                    }
                )
                continue
            if cited_ids.isdisjoint(allowed_ids):
                failures.append(
                    {
                        "type": "metric_id_not_grounded_to_source_evidence",
                        "location": location["location"],
                        "metric_id": metric_id,
                        "cited_ids": sorted(cited_ids),
                        "expected_source_ids": sorted(allowed_ids),
                        "near_text": str(location.get("text") or "")[:260],
                    }
                )
    return {
        "case_id": case_id,
        "mode": mode,
        "status": "fail" if failures else "pass",
        "answer_status": answer_status,
        "checked_location_count": checked_location_count,
        "metric_reference_count": metric_reference_count,
        "failures": failures,
        "warnings": [],
    }


def _metric_locations(answer: dict[str, Any]) -> list[dict[str, Any]]:
    locations: list[dict[str, Any]] = []
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


def _ledger_source_ids(row: dict[str, Any]) -> set[str]:
    return {
        str(row.get(key) or "").strip()
        for key in ("source_evidence_id", "object_id")
        if str(row.get(key) or "").strip()
    }


def _case_task_types(cases_path: Path) -> dict[str, str]:
    if not cases_path.exists():
        return {}
    return {str(row.get("case_id") or ""): str(row.get("task_type") or "") for row in _read_jsonl(cases_path)}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    if value is None:
        return []
    return [str(value)]


def _resolve(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return REPO_ROOT / candidate


def _skipped_result(case_id: str, mode: str, answer_status: str, reason: str) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "mode": mode,
        "status": "skipped",
        "answer_status": answer_status,
        "reason": reason,
        "checked_location_count": 0,
        "metric_reference_count": 0,
        "failures": [],
        "warnings": [],
    }


if __name__ == "__main__":
    main()
